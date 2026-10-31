"""ONNX Runtime backend for post-compose SR and RIFE."""
from __future__ import annotations
from portable_process_env import debug_log_path
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

import os
from typing import Callable, List, Optional

import numpy as np

from output_enhancement.gpu_work_gate import SHARED_GPU_GATE
from output_enhancement.onnx_frame_contract import frame_input, decode_sr, decode_rife, rife_full_resolution
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

    # EVS-DESIGN-AUDIT EVS-A082 BEGIN
    # 设计[f-055, f-056, f-057] [部分符合 / 会话首次加载待测]
    # ONNX Runtime 导入/provider 准备为懒操作；CUDA provider 警告不等于必然完全失效，也不等于无性能影响，须检查实际 provider 与逐帧结果。
    # 历史 bug 热点 #1：仅为回归关联，非声称本次故障已复现。
    # 诊断标记 R-OBS-02：参照文件头诊断报告；本次不修复实际行为。
    # EVS-DESIGN-AUDIT EVS-A082 END
    def _ensure_ort(self):
        if self._create_session is not None:
            return
        try:
            from ezvtb_rt.ort_utils import createORTSession
            self._create_session = createORTSession
        except ImportError:
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.enable_mem_pattern = False
            options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            # （补上 DirectML 推理后端）26.10.29 22:15 s
            available = list(ort.get_available_providers())
            providers = ["CPUExecutionProvider"]
            if "DmlExecutionProvider" in available:
                providers.insert(0, "DmlExecutionProvider")
            elif "CUDAExecutionProvider" in available:
                providers.insert(0, "CUDAExecutionProvider")
            # #region agent log
            try:
                import json as _json, time as _time
                open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({
                    "sessionId": "86a17c",
                    "runId": "post-fix-dml",
                    "hypothesisId": "U",
                    "location": "ort_backend.py:_ensure_ort",
                    "message": "ORT fallback factory providers",
                    "data": {"available": available, "chosen": providers, "has_dml": "DmlExecutionProvider" in available},
                    "timestamp": int(_time.time() * 1000),
                }) + "\n")
            except Exception:
                pass
            # #endregion

            def _fallback(path, device_id=0):
                return ort.InferenceSession(path, sess_options=options, providers=providers)

            self._create_session = _fallback
            # （补上 DirectML 推理后端）26.10.29 22:15 e

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
        node = session.get_inputs()[0]
        inp = frame_input(frame, node, premultiply=True)
        with SHARED_GPU_GATE.job("sr"):
            out = session.run(None, {node.name: inp})[0]
        result = decode_sr(out, frame, scale)
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
        import time
        import time
        work_started = time.perf_counter()
        gate_wait_ms = 0.0
        gpu_service_ms = 0.0
        patch_count = 0
        def run(feed):
            nonlocal gpu_service_ms, patch_count, gate_wait_ms
            waiting_started = time.perf_counter()
            with SHARED_GPU_GATE.job("rife%d" % multiplier):
                gate_wait_ms += (time.perf_counter() - waiting_started) * 1000.0
                started = time.perf_counter()
                out = rife.run(None, feed)[0]
                gpu_service_ms += (time.perf_counter() - started) * 1000.0
                patch_count += 1
                return out
        frames = rife_full_resolution(rife, frame0, frame1, multiplier, run)
        self.last_rife_patch_count = patch_count
        SHARED_GPU_GATE.observe("rife_work%d" % multiplier,
            (time.perf_counter() - work_started) * 1000.0 - gate_wait_ms)
        if gpu_service_ms > 0:
            SHARED_GPU_GATE.observe("rife_frame%d" % multiplier, gpu_service_ms)
        return frames

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
            rife_session = self._get_rife(rife_multiplier, fp16=False)
            # #region agent log
            try:
                import json as _json, time as _time
                used = list(rife_session.get_providers()) if rife_session is not None else []
                open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({
                    "sessionId": "86a17c",
                    "runId": "post-fix-dml",
                    "hypothesisId": "T",
                    "location": "ort_backend.py:preload",
                    "message": "RIFE session providers",
                    "data": {
                        "infer_backend": str(infer_backend),
                        "used": used,
                        "has_dml": "DmlExecutionProvider" in used,
                    },
                    "timestamp": int(_time.time() * 1000),
                }) + "\n")
            except Exception:
                pass
            # #endregion
        if kind == "onnx":
            if self._sr_session is None:
                raise FileNotFoundError("Selected super-resolution model is missing")
            node = self._sr_session.get_inputs()[0]
            dims = node.shape
            hh = dims[1] if isinstance(dims[1], int) else 512
            ww = dims[2] if isinstance(dims[2], int) else 512
            self.apply_super_resolution(np.zeros((hh, ww, 4), dtype=np.uint8), sr_mode)
        if rife_multiplier > 1:
            if rife_session is None:
                raise FileNotFoundError("Selected RIFE model is missing")
            dims = rife_session.get_inputs()[0].shape
            hh = dims[1] if isinstance(dims[1], int) else 512
            ww = dims[2] if isinstance(dims[2], int) else 512
            dummy = np.zeros((hh, ww, 4), dtype=np.uint8)
            self.interpolate_rife(dummy, dummy, rife_multiplier, fp16=False)
        if progress:
            progress("ONNX sessions ready", 0.95)
