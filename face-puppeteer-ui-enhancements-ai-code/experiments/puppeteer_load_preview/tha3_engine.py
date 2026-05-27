"""THA3 black-box renderer: PNG in, 45-float pose in, RGBA frame out."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import cv2
import numpy
import torch
import wx

from tha3_paths import (
    ensure_tha3_on_path,
    get_ezvtuber_models_root,
    get_ezvtuber_rt_root,
    pytorch_models_available,
    variant_to_ort_flags,
    variant_to_pytorch_model_name,
)


def _numpy_rgba_to_wx_image(rgba: numpy.ndarray) -> wx.Image:
    if rgba.shape[0] != 512 or rgba.shape[1] != 512 or rgba.shape[2] != 4:
        raise ValueError(f"Unexpected THA3 frame shape: {rgba.shape}")
    bgra = rgba.astype(numpy.uint8, copy=False)
    rgb = cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA)
    alpha = rgb[:, :, 3].tobytes()
    return wx.Image(512, 512, rgb[:, :, 0:3].tobytes(), alpha)


def _load_png_rgba(path: str) -> numpy.ndarray:
    image = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"Cannot read PNG: {path}")
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGRA)
    elif image.shape[2] == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
    if image.shape[0] != 512 or image.shape[1] != 512:
        image = cv2.resize(image, (512, 512), interpolation=cv2.INTER_AREA)
    return numpy.ascontiguousarray(image.astype(numpy.uint8))


def _load_tha3_ort_module():
    rt_root = get_ezvtuber_rt_root()
    import importlib.util
    import types

    # tha3_ort imports onnx but only uses onnxruntime; stub onnx so protobuf 3.x stays compatible with mediapipe.
    if "onnx" not in sys.modules:
        sys.modules["onnx"] = types.ModuleType("onnx")

    modules = (
        ("ezvtb_rt.ort_utils", rt_root / "ezvtb_rt" / "ort_utils.py"),
        ("ezvtb_rt.tha3_ort", rt_root / "ezvtb_rt" / "tha3_ort.py"),
    )
    for module_name, module_path in modules:
        if module_name in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(module_name, str(module_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module: {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return sys.modules["ezvtb_rt.tha3_ort"]


class Tha3Engine:
    """Lazy THA3 inference engine (PyTorch poser preferred, ONNX fallback)."""

    def __init__(self, device: torch.device, model_variant: str = "separable_half"):
        self.device = device
        self.model_variant = model_variant
        self.character_png_path: Optional[str] = None
        self._backend = None
        self._backend_kind: Optional[str] = None
        self._poser = None
        self._torch_image = None
        self._ort_sessions = None
        self._last_error: Optional[str] = None

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def is_loaded(self) -> bool:
        return self._backend is not None and self.character_png_path is not None

    def stop(self):
        self._backend = None
        self._backend_kind = None
        self._poser = None
        self._torch_image = None
        self._ort_sessions = None
        self.character_png_path = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def load_character_png(self, png_path: str) -> bool:
        self.stop()
        self._last_error = None
        try:
            rgba = _load_png_rgba(png_path)
            if pytorch_models_available(self.model_variant):
                self._init_pytorch_backend(rgba)
            else:
                self._init_ort_backend(rgba)
            self.character_png_path = png_path
            return True
        except Exception as exc:
            self._last_error = str(exc)
            self.stop()
            return False

    def _init_pytorch_backend(self, rgba_bgra: numpy.ndarray):
        ensure_tha3_on_path()
        from tha3.poser.modes.load_poser import load_poser
        from tha3.util import extract_pytorch_image_from_PIL_image, torch_linear_to_srgb
        import PIL.Image

        model_name = variant_to_pytorch_model_name(self.model_variant)
        self._poser = load_poser(model_name, self.device)
        pil = PIL.Image.fromarray(cv2.cvtColor(rgba_bgra, cv2.COLOR_BGRA2RGBA))
        self._torch_image = extract_pytorch_image_from_PIL_image(pil).to(self.device)
        self._torch_linear_to_srgb = torch_linear_to_srgb
        self._backend_kind = "pytorch"
        self._backend = self._poser

    def _init_ort_backend(self, rgba_bgra: numpy.ndarray):
        tha3_ort = _load_tha3_ort_module()
        separable, fp16 = variant_to_ort_flags(self.model_variant)
        precision = "fp16" if fp16 else "fp32"
        family = "seperable" if separable else "standard"
        tha_dir = str(get_ezvtuber_models_root() / "tha3" / family / precision)
        self._ort_sessions = tha3_ort.THA3ORTSessions(tha_dir, use_eyebrow=False)
        self._ort_sessions.update_image(rgba_bgra)
        self._backend_kind = "ort"
        self._backend = self._ort_sessions

    def render_pose(self, pose: List[float]) -> Optional[wx.Image]:
        if not self.is_loaded():
            return None
        pose_array = numpy.asarray(pose, dtype=numpy.float32).reshape(1, 45)
        try:
            if self._backend_kind == "pytorch":
                return self._render_pose_pytorch(pose_array[0])
            return self._render_pose_ort(pose_array)
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def _render_pose_pytorch(self, pose_vector: numpy.ndarray) -> wx.Image:
        pose_tensor = torch.tensor(pose_vector, device=self.device, dtype=self._poser.get_dtype())
        with torch.no_grad():
            output = self._poser.pose(self._torch_image, pose_tensor)[0].float()
            output = self._torch_linear_to_srgb((output + 1.0) / 2.0)
            channels, height, width = output.shape
            output = 255.0 * torch.transpose(output.reshape(channels, height * width), 0, 1).reshape(height, width, channels)
            output = output.byte().detach().cpu().numpy()
        rgba = cv2.cvtColor(output, cv2.COLOR_RGBA2BGRA)
        return _numpy_rgba_to_wx_image(rgba)

    def _render_pose_ort(self, pose_array: numpy.ndarray) -> wx.Image:
        rgba = self._ort_sessions.inference(pose_array)
        return _numpy_rgba_to_wx_image(rgba)
