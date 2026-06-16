"""ONNX Runtime backend for post-compose SR and RIFE."""
from __future__ import annotations

import os
from typing import Callable, List, Optional

import numpy as np

from output_enhancement.config import sr_mode_spec
from output_enhancement.paths import rife_onnx_path, sr_onnx_path
from output_enhancement.rgba_ops import (
    downscale_if_max_edge,
    resize_rgba,
    rgba_uint8_to_sr_input,
    rife_mid_frames_to_uint8,
    sr_output_to_rgba_uint8,
    upscale_rgba,
)

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

ProgressCallback = Optional[Callable[[str, float], None]]


class PostProcessORTBackend:
    """Lazy-loaded ORT sessions for RIFE/SR on composed RGBA frames."""

    def __init__(self, data_dir: str, device_id: int = 0):
        self.data_dir = data_dir
        self.device_id = device_id
        try:
            import ezvtb_rt
            ezvtb_rt.init_model_path(data_dir)
        except Exception:
            pass
        self._rife_sessions: dict = {}
        self._sr_session = None
        self._sr_key: Optional[tuple] = None
        self._a4k = None
        self._a4k_available = False
        self._create_session = None

    def _ensure_ort(self):
        if self._create_session is not None:
            return
        try:
            from ezvtb_rt.ort_utils import createORTSession
            self._create_session = createORTSession
        except ImportError:
            import onnxruntime as ort
            options = ort.SessionOptions()
            providers = ["CPUExecutionProvider"]
            try:
                providers.insert(0, "CUDAExecutionProvider")
            except Exception:
                pass

            def _fallback(path, device_id=0):
                return ort.InferenceSession(path, sess_options=options, providers=providers)

            self._create_session = _fallback

    def _get_rife(self, scale: int, fp16: bool):
        self._ensure_ort()
        key = (scale, fp16)
        if key in self._rife_sessions:
            return self._rife_sessions[key]
        path = rife_onnx_path(self.data_dir, scale, fp16)
        if not os.path.isfile(path):
            return None
        self._rife_sessions[key] = self._create_session(path, self.device_id)
        if scale >= 3:
            x2_path = rife_onnx_path(self.data_dir, 2, fp16)
            if os.path.isfile(x2_path) and (2, fp16) not in self._rife_sessions:
                self._rife_sessions[(2, fp16)] = self._create_session(x2_path, self.device_id)
        return self._rife_sessions.get(key)

    def _get_sr_onnx(self, scale: int, fp16: bool):
        self._ensure_ort()
        key = (scale, fp16)
        if self._sr_session is not None and self._sr_key == key:
            return self._sr_session
        path = sr_onnx_path(self.data_dir, scale, fp16)
        if not os.path.isfile(path):
            return None
        self._sr_session = self._create_session(path, self.device_id)
        self._sr_key = key
        return self._sr_session

    def _ensure_a4k(self):
        if self._a4k is not None or self._a4k_available is False:
            return self._a4k
        try:
            import pyanime4k
            self._a4k = pyanime4k.Processor(
                processor_type="opencl", device=0, model="acnet-gan")
        except Exception:
            self._a4k_available = False
            self._a4k = None
        return self._a4k

    def apply_super_resolution(self, rgba: np.ndarray, mode: str) -> np.ndarray:
        kind, scale, fp16, use_a4k = sr_mode_spec(mode)
        if kind == "off":
            return rgba
        frame = np.asarray(rgba, dtype=np.uint8)
        inv_scale = 1.0
        if scale == 4:
            frame, inv_scale = downscale_if_max_edge(frame, 512)
        if use_a4k:
            proc = self._ensure_a4k()
            if proc is None:
                return rgba
            if cv2 is None:
                return rgba
            alpha = np.ascontiguousarray(frame[:, :, 3])
            rgb = np.ascontiguousarray(frame[:, :, :3])
            processed = proc.process(rgb)
            alpha_up = cv2.resize(
                alpha, (processed.shape[1], processed.shape[0]),
                interpolation=cv2.INTER_LINEAR)
            out = np.dstack([processed, alpha_up]).astype(np.uint8)
            return upscale_rgba(out, inv_scale)
        session = self._get_sr_onnx(scale, fp16)
        if session is None:
            return rgba
        alpha_src = frame[:, :, 3]
        if cv2 is None:
            return resize_rgba(frame, frame.shape[1] * scale, frame.shape[0] * scale)
        inp = rgba_uint8_to_sr_input(frame)
        name = session.get_inputs()[0].name
        out = session.run(None, {name: inp})[0]
        result = sr_output_to_rgba_uint8(out, alpha_src, scale)
        return upscale_rgba(result, inv_scale)

    def interpolate_rife(
            self,
            frame0: np.ndarray,
            frame1: np.ndarray,
            multiplier: int,
            fp16: bool = False) -> List[np.ndarray]:
        if multiplier <= 1:
            return [frame1]
        rife = self._get_rife(multiplier, fp16)
        if rife is None:
            return [frame1]
        f0 = np.asarray(frame0, dtype=np.float32) / 255.0
        f1 = np.asarray(frame1, dtype=np.float32) / 255.0
        batch0 = np.expand_dims(f0, axis=0)
        batch1 = np.expand_dims(f1, axis=0)
        try:
            out = rife.run(None, {"tha_img_0": batch0, "tha_img_1": batch1})[0]
        except Exception:
            return [frame1]
        mids = rife_mid_frames_to_uint8(out, multiplier - 1)
        if len(mids) < multiplier - 1:
            return [frame1]
        return mids + [frame1]

    def shutdown(self):
        self._rife_sessions.clear()
        self._sr_session = None
        self._a4k = None

    def preload(
            self,
            *,
            sr_mode: str,
            rife_multiplier: int,
            progress: ProgressCallback = None,
            infer_backend: str = "ort") -> None:
        if progress:
            progress("Loading ONNX Runtime providers…", 0.15)
        self._ensure_ort()
        kind, scale, fp16, use_a4k = sr_mode_spec(sr_mode)
        if kind == "a4k":
            if progress:
                progress("Initializing anime4k (OpenCL)…", 0.45)
            self._ensure_a4k()
        elif kind == "onnx":
            if progress:
                progress(f"Loading super-resolution ONNX (×{scale})…", 0.45)
            self._get_sr_onnx(scale, fp16)
        if rife_multiplier > 1:
            if progress:
                progress(f"Loading RIFE ONNX (×{rife_multiplier})…", 0.75)
            self._get_rife(rife_multiplier, fp16=False)
        if progress:
            progress("ONNX sessions ready", 0.95)
