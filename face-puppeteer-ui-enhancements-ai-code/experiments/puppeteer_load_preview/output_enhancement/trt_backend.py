"""Optional TensorRT backend for post-compose SR/RIFE."""
from __future__ import annotations

import os
from typing import List, Optional

import numpy as np

from output_enhancement.ort_backend import PostProcessORTBackend
from output_enhancement.paths import get_trt_engine_cache_dir, rife_onnx_path, sr_onnx_path


class PostProcessTRTBackend:
    """TRT engines for RIFE/SR; falls back to ORT when unavailable."""

    def __init__(self, data_dir: str, device_id: int = 0, engine_cache_dir: Optional[str] = None):
        self.data_dir = data_dir
        self.device_id = device_id
        self.engine_cache_dir = engine_cache_dir or get_trt_engine_cache_dir()
        self._rife_engines: dict = {}
        self._sr_engine = None
        self._sr_key: Optional[tuple] = None
        self._trt_available = True
        self._ort_fallback = PostProcessORTBackend(data_dir, device_id)

    def _engine_cache_path(self, onnx_path: str) -> Optional[str]:
        if not self.engine_cache_dir or not os.path.isfile(onnx_path):
            return None
        base = os.path.splitext(os.path.basename(onnx_path))[0]
        return os.path.join(self.engine_cache_dir, f"{base}.trt")

    def _load_trt_engine(self, onnx_path: str, n_inputs: int):
        if not self._trt_available or not os.path.isfile(onnx_path):
            return None
        cached = self._engine_cache_path(onnx_path)
        try:
            from ezvtb_rt.trt_engine import TRTEngine
            if cached and os.path.isfile(cached):
                engine = TRTEngine(cached, n_inputs)
            else:
                engine = TRTEngine(onnx_path, n_inputs)
                if cached and hasattr(engine, "engine"):
                    try:
                        from ezvtb_rt.trt_utils import save_engine
                        save_engine(engine.engine.serialize(), cached)
                    except Exception:
                        pass
            engine.configure_in_out_tensors()
            return engine
        except Exception:
            self._trt_available = False
            return None

    def _get_rife(self, scale: int, fp16: bool):
        key = (scale, fp16)
        if key in self._rife_engines:
            return self._rife_engines[key]
        path = rife_onnx_path(self.data_dir, scale, fp16)
        eng = self._load_trt_engine(path, 2)
        if eng is not None:
            self._rife_engines[key] = eng
        return eng

    def apply_super_resolution(self, rgba: np.ndarray, mode: str) -> np.ndarray:
        if not self._trt_available:
            return self._ort_fallback.apply_super_resolution(rgba, mode)
        from output_enhancement.config import sr_mode_spec
        kind, scale, fp16, use_a4k = sr_mode_spec(mode)
        if kind == "off" or use_a4k:
            return self._ort_fallback.apply_super_resolution(rgba, mode)
        key = (scale, fp16)
        if self._sr_engine is None or self._sr_key != key:
            path = sr_onnx_path(self.data_dir, scale, fp16)
            self._sr_engine = self._load_trt_engine(path, 1)
            self._sr_key = key
        if self._sr_engine is None:
            return self._ort_fallback.apply_super_resolution(rgba, mode)
        try:
            from output_enhancement.rgba_ops import rgba_uint8_to_sr_input, sr_output_to_rgba_uint8
            frame = np.asarray(rgba, dtype=np.uint8)
            alpha_src = frame[:, :, 3]
            inp = rgba_uint8_to_sr_input(frame)
            out = self._sr_engine.run(None, {self._sr_engine.input_tensor_names[0]: inp})[0]
            return sr_output_to_rgba_uint8(out, alpha_src, scale)
        except Exception:
            return self._ort_fallback.apply_super_resolution(rgba, mode)

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
            return self._ort_fallback.interpolate_rife(frame0, frame1, multiplier, fp16)
        f0 = np.asarray(frame0, dtype=np.float32) / 255.0
        f1 = np.asarray(frame1, dtype=np.float32) / 255.0
        batch0 = np.expand_dims(f0, axis=0)
        batch1 = np.expand_dims(f1, axis=0)
        try:
            out = rife.run(None, {"tha_img_0": batch0, "tha_img_1": batch1})[0]
            from output_enhancement.rgba_ops import rife_mid_frames_to_uint8
            mids = rife_mid_frames_to_uint8(out, multiplier - 1)
            if len(mids) < multiplier - 1:
                return [frame1]
            return mids + [frame1]
        except Exception:
            return self._ort_fallback.interpolate_rife(frame0, frame1, multiplier, fp16)

    def shutdown(self):
        self._rife_engines.clear()
        self._sr_engine = None
        self._ort_fallback.shutdown()

    def preload(
            self,
            *,
            sr_mode: str,
            rife_multiplier: int,
            progress=None,
            infer_backend: str = "trt") -> None:
        from output_enhancement.config import sr_mode_spec
        if progress:
            progress("Preparing TensorRT (may compile once)…", 0.2)
        kind, scale, fp16, use_a4k = sr_mode_spec(sr_mode)
        if kind == "onnx" and not use_a4k:
            path = sr_onnx_path(self.data_dir, scale, fp16)
            self._load_trt_engine(path, 1)
        if rife_multiplier > 1:
            if progress:
                progress(f"Compiling RIFE TensorRT engine (×{rife_multiplier})…", 0.6)
            path = rife_onnx_path(self.data_dir, rife_multiplier, False)
            self._load_trt_engine(path, 2)
        if not self._trt_available:
            if progress:
                progress("TensorRT unavailable; using ONNX Runtime", 0.85)
            self._ort_fallback.preload(
                sr_mode=sr_mode,
                rife_multiplier=rife_multiplier,
                progress=progress,
                infer_backend="ort")
        elif progress:
            progress("TensorRT engines ready", 0.95)
