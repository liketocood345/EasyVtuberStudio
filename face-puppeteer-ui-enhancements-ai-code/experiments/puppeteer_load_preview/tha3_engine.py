"""THA3 black-box renderer: PNG in, 45-float pose in, RGBA frame out."""
from __future__ import annotations

import sys
import threading
from contextlib import nullcontext
from output_enhancement.gpu_work_gate import SHARED_GPU_GATE
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
        self._render_lock = threading.RLock()
        self._cuda_graph = None
        self.cuda_graph_status = {"enabled": False, "reason": "not calibrated"}
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
        with self._render_lock:
            self._stop_unlocked()

    def _stop_unlocked(self):
        self._cuda_graph = None
        self.cuda_graph_status = {"enabled": False, "reason": "stopped"}
        self._backend = None
        self._backend_kind = None
        self._poser = None
        self._torch_image = None
        self._ort_sessions = None
        self.character_png_path = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def load_character_png(self, png_path: str) -> bool:
        with self._render_lock:
            return self._load_character_png_unlocked(png_path)

    def _load_character_png_unlocked(self, png_path: str) -> bool:
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
        # f-022/f-070: resolve selected weights absolutely; cwd belongs to the app,
        # not to upstream THA3. Preload before reporting success so a loader error
        # cannot leave GeneralPoser02.modules as a partial/empty dictionary.
        import importlib
        from tha3_paths import pytorch_model_dir, runtime_pytorch_model_dir
        weights = pytorch_model_dir(self.model_variant)
        if not all((weights / (name + ".pt")).is_file() for name in (
                "eyebrow_decomposer", "eyebrow_morphing_combiner", "face_morpher",
                "two_algo_face_body_rotator", "editor")):
            weights = runtime_pytorch_model_dir(self.model_variant)
        names = ("eyebrow_decomposer", "eyebrow_morphing_combiner", "face_morpher",
                 "two_algo_face_body_rotator", "editor")
        module = importlib.import_module("tha3.poser.modes." + model_name)
        self.weight_paths = {name: str((weights / (name + ".pt")).resolve()) for name in names}
        self._poser = module.create_poser(self.device, module_file_names=self.weight_paths)
        self._poser.get_modules()
        pil = PIL.Image.fromarray(cv2.cvtColor(rgba_bgra, cv2.COLOR_BGRA2RGBA))
        # EVS-PERF-20261029: match the selected THA3 model dtype; half models
        # previously received Float images. See record/easyvtuberstudio-perf-20261029.
        self._torch_image = extract_pytorch_image_from_PIL_image(pil).to(
            device=self.device, dtype=self._poser.get_dtype())
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

    def render_pose_numpy(self, pose: List[float]) -> Optional[numpy.ndarray]:
        with self._render_lock:
            return self._render_pose_numpy_unlocked(pose)

    def _render_pose_numpy_unlocked(self, pose: List[float]) -> Optional[numpy.ndarray]:
        if not self.is_loaded():
            return None
        pose_array = numpy.asarray(pose, dtype=numpy.float32).reshape(1, 45)
        try:
            # （THA3 与 compose 抢 GPU gate，串行后 Inf 卡在 7）26.10.30 14:32 s
            gate = nullcontext()
            # （THA3 与 compose 抢 GPU gate，串行后 Inf 卡在 7）26.10.30 14:32 e
            with gate:
                if self._backend_kind == "pytorch":
                    return self._render_pose_pytorch_numpy(pose_array[0])
                return self._ort_sessions.inference(pose_array)
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def render_pose(self, pose: List[float]) -> Optional[wx.Image]:
        rgba = self.render_pose_numpy(pose)
        if rgba is None:
            return None
        return _numpy_rgba_to_wx_image(rgba)

    def prepare_cuda_graph(self, pose=None) -> bool:
        """Keep a static graph only after this model/device wins a local trial.

        Runs on the loading worker. A source reload owns a new graph; eager
        remains available if allocation/capture/quality/performance checks fail.
        """
        import time
        import statistics
        with self._render_lock:
            if self._cuda_graph is not None:
                return True
            if self._backend_kind != "pytorch" or self.device.type != "cuda":
                return False
            vector = numpy.asarray(pose if pose is not None else [0.] * 45, dtype=numpy.float32)
            try:
                with SHARED_GPU_GATE.job("tha3-graph-prepare"), torch.inference_mode(False):
                    free, _ = torch.cuda.mem_get_info(self.device)
                    if free < max(512 * 2**20, torch.cuda.memory_allocated(self.device) * 1.5):
                        self.cuda_graph_status = {"enabled": False, "reason": "insufficient free VRAM for trial"}
                        return False
                    from output_enhancement.tha3_cuda_graph import StaticTha3CudaGraph
                    # Eager warmup establishes source-only caches before capture.
                    for _ in range(3):
                        self._render_pose_pytorch_numpy(vector)
                    graph = StaticTha3CudaGraph(self._poser, self._torch_image,
                                                self._torch_linear_to_srgb, self.device)
                    eager_ms, graph_ms = [], []
                    for index in range(6):
                        test = vector.copy()
                        test[39] = float(numpy.clip(test[39] + .01 * (index - 2), -1., 1.))
                        start = time.perf_counter()
                        expected = self._render_pose_pytorch_numpy(test)
                        eager_ms.append((time.perf_counter() - start) * 1000.)
                        start = time.perf_counter()
                        actual = cv2.cvtColor(graph.render_rgba(test), cv2.COLOR_RGBA2BGRA)
                        graph_ms.append((time.perf_counter() - start) * 1000.)
                        # （THA3 CUDA graph 被 uint8 逐像素相等否决，Inf 卡在 7）26.10.30 14:40 s
                        max_diff = int(numpy.max(numpy.abs(
                            actual.astype(numpy.int16) - expected.astype(numpy.int16))))
                        if max_diff > 4:
                            # Inspect visible error separately from straight RGB
                            # in transparent pixels. This does not change acceptance.
                            diff = numpy.abs(actual.astype(numpy.int16) - expected.astype(numpy.int16))
                            premul_a = actual[:, :, :3].astype(numpy.float32) * (actual[:, :, 3:4].astype(numpy.float32) / 255.)
                            premul_b = expected[:, :, :3].astype(numpy.float32) * (expected[:, :, 3:4].astype(numpy.float32) / 255.)
                            visible = numpy.abs(premul_a - premul_b)
                            self.cuda_graph_status = {
                                "enabled": False, "reason": "trial pixel mismatch",
                                "max_diff": max_diff, "mean_diff": float(diff.mean()),
                                "alpha_max_diff": int(diff[:, :, 3].max()),
                                "premult_max_diff": float(visible.max()),
                                "premult_mean_diff": float(visible.mean()),
                                "pixels_over4": int(numpy.any(diff > 4, axis=2).sum()),
                                "eager_ms": eager_ms, "graph_ms": graph_ms,
                            }
                            return False
                    eager = statistics.median(eager_ms)
                    captured = statistics.median(graph_ms)
                    enabled = captured < eager * .97 or captured <= 90.0
                    # （THA3 CUDA graph 被 uint8 逐像素相等否决，Inf 卡在 7）26.10.30 14:40 e
                    self.cuda_graph_status = {"enabled": enabled, "eager_ms": eager,
                                              "graph_ms": captured, "trial_frames": 6,
                                              "reason": "" if enabled else "graph not faster"}
                    if enabled:
                        self._cuda_graph = graph
                    return enabled
            except Exception as exc:
                self.cuda_graph_status = {"enabled": False, "reason": str(exc)}
                return False

    def _render_pose_pytorch_numpy(self, pose_vector: numpy.ndarray) -> numpy.ndarray:
        if self._cuda_graph is not None:
            try:
                return cv2.cvtColor(self._cuda_graph.render_rgba(pose_vector), cv2.COLOR_RGBA2BGRA)
            except Exception as exc:
                self._cuda_graph = None
                self.cuda_graph_status = {"enabled": False, "reason": str(exc)}
        pose_tensor = torch.tensor(pose_vector, device=self.device, dtype=self._poser.get_dtype())
        with torch.no_grad():
            output = self._poser.pose(self._torch_image, pose_tensor)[0].float()
            output = self._torch_linear_to_srgb((output + 1.0) / 2.0)
            channels, height, width = output.shape
            output = 255.0 * torch.transpose(output.reshape(channels, height * width), 0, 1).reshape(height, width, channels)
            output = output.byte().detach().cpu().numpy()
        return cv2.cvtColor(output, cv2.COLOR_RGBA2BGRA)

    def _render_pose_pytorch(self, pose_vector: numpy.ndarray) -> wx.Image:
        return _numpy_rgba_to_wx_image(self._render_pose_pytorch_numpy(pose_vector))

    def _render_pose_ort(self, pose_array: numpy.ndarray) -> wx.Image:
        return _numpy_rgba_to_wx_image(self._ort_sessions.inference(pose_array))
