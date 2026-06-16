"""Enhancement pipeline applied after full-stack compose, before ULW delivery."""
from __future__ import annotations

import enum
import hashlib
from typing import Any, Callable, Deque, Dict, List, Optional
from collections import deque

import numpy as np

from output_enhancement.config import (
    INFER_BACKEND_ORT,
    INFER_BACKEND_PYTORCH,
    INFER_BACKEND_TRT,
    NN_FRAME_INTERP_OFF,
    NN_SR_OFF,
    pipeline_config_from_persistence,
    normalize_infer_backend,
    normalize_nn_frame_multiplier,
    normalize_sr_mode,
)
from output_enhancement.paths import get_ezvtb_data_dir, get_trt_engine_cache_dir, is_output_enhancement_installed, onnx_weights_available

ProgressCallback = Optional[Callable[[str, float], None]]


class FrameSourceTag(str, enum.Enum):
    REAL = "real"
    POSE_INTERP = "pose_interp"
    CACHE = "cache"
    RIFE = "rife"
    SR = "sr"


class EnhancementPipeline:
    """Post-compose RGBA enhancement; default off = identity."""

    def __init__(self, repo_root: Optional[str] = None):
        self.repo_root = repo_root
        self._data_dir = get_ezvtb_data_dir(repo_root)
        self._config = pipeline_config_from_persistence({})
        self._ort: Optional[Any] = None
        self._trt: Optional[Any] = None
        self._prev_rgba: Optional[np.ndarray] = None
        self._rife_queue: Deque[np.ndarray] = deque()
        self._last_frame_tag: FrameSourceTag = FrameSourceTag.REAL
        self._load_error: Optional[str] = None
        self._warned_missing = False

    @property
    def frame_source_tag(self) -> FrameSourceTag:
        return self._last_frame_tag

    @property
    def addon_installed(self) -> bool:
        return is_output_enhancement_installed(self.repo_root)

    @property
    def weights_available(self) -> bool:
        return onnx_weights_available(self._data_dir)

    def _invalidate_backends(self) -> None:
        if self._ort is not None:
            self._ort.shutdown()
            self._ort = None
        if self._trt is not None:
            self._trt.shutdown()
            self._trt = None

    def update_config(self, persistence: Optional[Dict[str, Any]]) -> None:
        new_config = pipeline_config_from_persistence(persistence)
        if new_config == self._config:
            return
        self._config = new_config
        self._invalidate_backends()
        self.reset_rife_buffers()
        self._warned_missing = False

    def is_active(self) -> bool:
        backend = normalize_infer_backend(self._config.get("nn_infer_backend"))
        if backend == INFER_BACKEND_PYTORCH:
            return False
        sr = normalize_sr_mode(self._config.get("nn_super_resolution_mode"))
        rife = normalize_nn_frame_multiplier(
            self._config.get("nn_frame_interpolation_multiplier"))
        return sr != NN_SR_OFF or rife > NN_FRAME_INTERP_OFF

    def nn_modes_requested(self) -> bool:
        sr = normalize_sr_mode(self._config.get("nn_super_resolution_mode"))
        rife = normalize_nn_frame_multiplier(
            self._config.get("nn_frame_interpolation_multiplier"))
        return sr != NN_SR_OFF or rife > NN_FRAME_INTERP_OFF

    def _active_backend(self):
        from output_enhancement.ort_backend import PostProcessORTBackend
        from output_enhancement.trt_backend import PostProcessTRTBackend

        backend = normalize_infer_backend(self._config.get("nn_infer_backend"))
        if backend == INFER_BACKEND_TRT:
            if self._trt is None and self._data_dir:
                cache_dir = get_trt_engine_cache_dir(self.repo_root)
                self._trt = PostProcessTRTBackend(self._data_dir, engine_cache_dir=cache_dir)
            return self._trt
        if self._ort is None and self._data_dir:
            self._ort = PostProcessORTBackend(self._data_dir)
        return self._ort

    def _require_backend(self) -> bool:
        if not self.addon_installed and not self.weights_available:
            return False
        if not self.weights_available:
            return False
        return self._active_backend() is not None

    def reset_rife_buffers(self) -> None:
        self._prev_rgba = None
        self._rife_queue.clear()

    def pop_rife_frame(self) -> Optional[np.ndarray]:
        if self._rife_queue:
            frame = self._rife_queue.popleft()
            self._last_frame_tag = FrameSourceTag.RIFE
            return frame
        return None

    def has_pending_rife(self) -> bool:
        return len(self._rife_queue) > 0

    def warmup(self, progress: ProgressCallback = None) -> None:
        """Preload ORT/TRT sessions (f-057 slow task)."""
        if not self.nn_modes_requested():
            return
        backend_name = normalize_infer_backend(self._config.get("nn_infer_backend"))
        if backend_name == INFER_BACKEND_PYTORCH:
            return
        if not self.addon_installed and not self.weights_available:
            return

        def _report(msg: str, frac: float) -> None:
            if progress is not None:
                progress(msg, frac)

        _report("Checking output enhancement models…", 0.05)
        backend = self._active_backend()
        if backend is None:
            return
        sr_mode = normalize_sr_mode(self._config.get("nn_super_resolution_mode"))
        rife_mult = normalize_nn_frame_multiplier(
            self._config.get("nn_frame_interpolation_multiplier"))
        if hasattr(backend, "preload"):
            backend.preload(
                sr_mode=sr_mode,
                rife_multiplier=rife_mult,
                progress=_report,
                infer_backend=backend_name)
        _report("Output enhancement ready (cached for next launch)", 1.0)

    def apply(self, rgba: np.ndarray, *, is_new_real_frame: bool = True) -> np.ndarray:
        """Apply SR to real frame; queue RIFE mids when enabled."""
        if rgba is None:
            return rgba
        frame = np.asarray(rgba, dtype=np.uint8)
        if not self.is_active():
            self._last_frame_tag = FrameSourceTag.REAL
            return frame

        if not self._require_backend():
            if not self._warned_missing:
                self._warned_missing = True
            self._last_frame_tag = FrameSourceTag.REAL
            return frame

        backend = self._active_backend()
        sr_mode = normalize_sr_mode(self._config.get("nn_super_resolution_mode"))
        rife_mult = normalize_nn_frame_multiplier(
            self._config.get("nn_frame_interpolation_multiplier"))

        if is_new_real_frame and rife_mult > NN_FRAME_INTERP_OFF and self._prev_rgba is not None:
            if (self._prev_rgba.shape[0] == frame.shape[0]
                    and self._prev_rgba.shape[1] == frame.shape[1]):
                try:
                    mids = backend.interpolate_rife(
                        self._prev_rgba, frame, rife_mult, fp16=False)
                    for mid in mids[:-1]:
                        enhanced = backend.apply_super_resolution(mid, sr_mode)
                        self._rife_queue.append(enhanced)
                except Exception:
                    pass

        out = backend.apply_super_resolution(frame, sr_mode)
        self._prev_rgba = frame.copy()
        if sr_mode != NN_SR_OFF:
            self._last_frame_tag = FrameSourceTag.SR
        else:
            self._last_frame_tag = FrameSourceTag.REAL
        return out

    def apply_identity_check(self, rgba: np.ndarray) -> np.ndarray:
        """When pipeline inactive, return unchanged (for smoke)."""
        if not self.is_active():
            return rgba
        return self.apply(rgba)

    @staticmethod
    def content_hash(rgba: np.ndarray) -> str:
        return hashlib.sha256(np.ascontiguousarray(rgba).tobytes()).hexdigest()[:16]

    def shutdown(self) -> None:
        if self._ort is not None:
            self._ort.shutdown()
            self._ort = None
        if self._trt is not None:
            self._trt.shutdown()
            self._trt = None
        self.reset_rife_buffers()
