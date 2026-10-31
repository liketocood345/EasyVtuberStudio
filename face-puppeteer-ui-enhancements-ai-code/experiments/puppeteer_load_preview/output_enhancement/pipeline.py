"""Enhancement pipeline applied after full-stack compose, before ULW delivery."""
from __future__ import annotations
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

import enum
import hashlib
import time
from output_enhancement.buffered_rife import BufferedRifePresenter
from output_enhancement.target_frame_rate import TargetFrameRateController
from output_enhancement.gpu_work_gate import SHARED_GPU_GATE
from typing import Any, Callable, Deque, Dict, List, Optional
from collections import deque

import numpy as np

from output_enhancement.config import (
    INFER_BACKEND_DML,
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


# EVS-DESIGN-AUDIT EVS-A079 BEGIN
# 设计[f-061] [待做（内部标签已有）]
# REAL/插帧/超分来源标签是内部基础；当前没有完整文字 HUD 的验收证据。用户要求是更全面文字来源标识，不能用二元红点或 enum 代替。
# EVS-DESIGN-AUDIT EVS-A079 END
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
        self._buffered_presenter = None
        self._target = TargetFrameRateController()
        self._target_probe_previous = None
        self._target_nn_available = False
        self._target_sr_ready = False
        self._target_auto_backend = None
        self._hybrid_role_active = False
        self._output_callback = None
        self._frame_transformer = None
        self._scene_rate_hz = 30.
        self._scene_clock_independent = False
        self._buffered_enabled = True
        self._next_source_time = None
        self._reserved_source_time = None
        self._last_source_time = None
        self._last_source_period = None
        # bh-1 26.10.30 11:05 s
        # 12 was an experiment floor, not a product cap. Start at 30 so the
        # first measured promote does not wait 6s from a starved 12Hz.
        self._source_rate_hz = 30
        # bh-1 26.10.30 11:05 e
        self._rate_changed_at = 0.0
        # bh-1 26.10.29 20:24 s
        self._nn_sessions_preloaded = False
        # bh-1 26.10.29 20:24 e

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
        self._stop_buffered_presenter()
        self._target.close()
        self._target = TargetFrameRateController()
        self._target_probe_previous = None
        self._target_nn_available = False
        self._target_sr_ready = False
        self._target_auto_backend = None
        if self._ort is not None:
            self._ort.shutdown()
            self._ort = None
        if self._trt is not None:
            self._trt.shutdown()
            self._trt = None
        # bh-1 26.10.29 20:24 s
        self._nn_sessions_preloaded = False
        # bh-1 26.10.29 20:24 e

    def update_config(self, persistence: Optional[Dict[str, Any]]) -> None:
        new_config = pipeline_config_from_persistence(persistence)
        if new_config == self._config:
            return
        if {k:v for k,v in new_config.items() if k != "target_frame_rate_fps"} == {k:v for k,v in self._config.items() if k != "target_frame_rate_fps"}:
            self._config = new_config
            self._target.reset_plan()
            return
        self._config = new_config
        self._load_error = None
        self._invalidate_backends()
        self.reset_rife_buffers()
        self._warned_missing = False

    def is_active(self) -> bool:
        if self.target_frame_rate_enabled() or self._frame_transformer is not None:
            return True
        backend = normalize_infer_backend(self._config.get("nn_infer_backend"))
        if backend == INFER_BACKEND_PYTORCH:
            return False
        sr = normalize_sr_mode(self._config.get("nn_super_resolution_mode"))
        rife = self._effective_nn_multiplier()
        return sr != NN_SR_OFF or rife > NN_FRAME_INTERP_OFF

    def nn_modes_requested(self) -> bool:
        if self.target_frame_rate_enabled():
            return True
        sr = normalize_sr_mode(self._config.get("nn_super_resolution_mode"))
        rife = self._effective_nn_multiplier()
        return sr != NN_SR_OFF or rife > NN_FRAME_INTERP_OFF

    # （f-064 NN 核查接口）26.10.29 19:40 s
    def get_config_snapshot(self) -> Dict[str, Any]:
        return dict(self._config)
    # （f-064 NN 核查接口）26.10.29 19:40 e

    # bh-1 26.10.29 20:24 s
    def nn_runtime_ready(self) -> bool:
        if self.target_frame_rate_enabled():
            return True  # Real frames work even without optional NN weights.
        if not self.nn_modes_requested():
            return True
        if not self.is_active():
            return False
        return bool(self._nn_sessions_preloaded)
    # bh-1 26.10.29 20:24 e

    def actual_nn_backend_name(self) -> str:
        requested = normalize_infer_backend(self._config.get("nn_infer_backend"))
        if requested == INFER_BACKEND_TRT:
            trt = self._trt
            if trt is not None and bool(getattr(trt, "_trt_available", False)):
                return INFER_BACKEND_TRT
            try:
                import onnxruntime as ort
                if "DmlExecutionProvider" in list(ort.get_available_providers()):
                    return INFER_BACKEND_DML
            except Exception:
                pass
            return INFER_BACKEND_ORT
        if requested == INFER_BACKEND_ORT:
            try:
                import onnxruntime as ort
                if "DmlExecutionProvider" in list(ort.get_available_providers()):
                    return INFER_BACKEND_DML
            except Exception:
                pass
        return requested

    def _active_backend(self):
        if self.target_frame_rate_enabled() and self._target_auto_backend is not None:return self._target_auto_backend
        from output_enhancement.ort_backend import PostProcessORTBackend
        from output_enhancement.trt_backend import PostProcessTRTBackend

        backend = normalize_infer_backend(self._config.get("nn_infer_backend"))
        if backend == INFER_BACKEND_TRT:
            if self._trt is None and self._data_dir:
                cache_dir = get_trt_engine_cache_dir(self.repo_root)
                self._trt = PostProcessTRTBackend(self._data_dir, engine_cache_dir=cache_dir)
            return self._trt
        if backend in (INFER_BACKEND_ORT, INFER_BACKEND_DML):
            if self._ort is None and self._data_dir:
                self._ort = PostProcessORTBackend(self._data_dir)
            return self._ort
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
        self._stop_buffered_presenter()
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

    # EVS-DESIGN-AUDIT EVS-A080 BEGIN
    # 设计[f-058, f-057] [部分符合 / 时间预算待测]
    # 显式预加载入口有进度；呈现 apply 不再懒创建会话，未 preload 时原帧直出。需分别验证十分钟预算和预计时间。
    # 历史 bug 热点 #1：仅为回归关联，非声称本次故障已复现。
    # EVS-DESIGN-AUDIT EVS-A080 END
    def warmup(self, progress: ProgressCallback = None) -> None:
        """Preload ORT/TRT sessions (f-057 slow task)."""
        if self.target_frame_rate_enabled():
            if self._frame_transformer is not None and self._target_plan().reaches_target:
                return  # Scene clock already meets target with maximal real inference.
            sr_mode=normalize_sr_mode(self._config.get("nn_super_resolution_mode"))
            if self.weights_available:
                backend = self._active_backend()
                if sr_mode != NN_SR_OFF:
                    try:
                        backend.preload(sr_mode=sr_mode,rife_multiplier=1,progress=progress,infer_backend="ort")
                        self._target_sr_ready=True
                    except Exception as exc:
                        self._load_error="Super-resolution unavailable: %s" % exc
                        return
                try:
                    # bh-1 26.10.30 13:08 s
                    wanted = {2}
                    ui_mult = normalize_nn_frame_multiplier(
                        self._config.get("nn_frame_interpolation_multiplier"))
                    if ui_mult >= 3:
                        wanted.add(int(ui_mult))
                    planned = int(self._effective_nn_multiplier())
                    if planned > 1:
                        wanted.add(planned)
                    for multiplier in sorted(wanted):
                        backend.preload(sr_mode=NN_SR_OFF, rife_multiplier=multiplier,
                                        progress=progress, infer_backend="ort")
                    self._target_nn_available = True
                    # bh-1 26.10.30 13:08 e
                except Exception:
                    self._target_nn_available = False
                    if sr_mode==NN_SR_OFF:
                        try:
                            from output_enhancement.ort_backend import PostProcessORTBackend
                            self._ort=PostProcessORTBackend(self._data_dir)
                            # bh-1 26.10.30 13:08 s
                            self._ort.preload(sr_mode=NN_SR_OFF,rife_multiplier=2,progress=progress,infer_backend="ort")
                            # bh-1 26.10.30 13:08 e
                            self._target_auto_backend=self._ort;self._target_nn_available=True
                        except Exception:pass
            elif sr_mode != NN_SR_OFF:
                self._load_error="Super-resolution weights unavailable"
            # bh-1 26.10.30 13:08 s
            self._nn_sessions_preloaded = True
            # bh-1 26.10.30 13:08 e
            return
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
        rife_mult = self._effective_nn_multiplier()
        if hasattr(backend, "preload"):
            backend.preload(
                sr_mode=sr_mode,
                rife_multiplier=rife_mult,
                progress=_report,
                infer_backend=backend_name)
        # bh-1 26.10.29 20:24 s
        self._nn_sessions_preloaded = True
        # bh-1 26.10.29 20:24 e
        _report("Output enhancement ready (cached for next launch)", 1.0)

    # EVS-DESIGN-AUDIT EVS-A078 BEGIN
    # 设计[f-055, f-056, f-063] [部分符合 / 静默降级风险]
    # 有 RIFE 队列与超分；缺后端返回原帧、RIFE 异常直接 pass，未在此把 UI 恢复为关闭。开关显示启用不代表后端实际完成处理，需与 f-063 一起核查。
    # 历史 bug 热点 #1：仅为回归关联，非声称本次故障已复现。
    # 诊断标记 R-NN-01：参照文件头诊断报告；本次不修复实际行为。
    # EVS-DESIGN-AUDIT EVS-A078 END
    def target_frame_rate_enabled(self):
        return bool(self._config.get("target_frame_rate_enabled", False))

    def _target_plan(self):
        presenter = self._buffered_presenter
        self._target.scene_mode = self._frame_transformer is not None or self._scene_clock_independent
        owner=getattr(self._frame_transformer,"__self__",None)
        gpu_active=owner is not None and bool(getattr(owner,"gpu_active",False))
        self._target.gpu_compose_ms=(SHARED_GPU_GATE.service_ms("compose") or 0.) if gpu_active else 0.
        if gpu_active and owner.cpu_service_ms is not None:
            self._target.observe_compose(owner.cpu_service_ms)
        elif self._frame_transformer is not None and presenter is not None and presenter.transform_ms:
            self._target.observe_compose(sum(presenter.transform_ms) / len(presenter.transform_ms) / max(1, presenter.multiplier))
        model = SHARED_GPU_GATE.service_ms("tha3") or SHARED_GPU_GATE.service_ms("tha4")
        sr = SHARED_GPU_GATE.service_ms("sr") if normalize_sr_mode(self._config.get("nn_super_resolution_mode")) != NN_SR_OFF else 0.
        return self._target.plan(self._config.get("target_frame_rate_fps", 60),
                                 (model or 1000. / 30.) + (sr or 0.))

    def _effective_nn_multiplier(self):
        if self.target_frame_rate_enabled():
            # bh-1 26.10.30 14:04 s
            return 1
            # bh-1 26.10.30 14:04 e
        return normalize_nn_frame_multiplier(self._config.get("nn_frame_interpolation_multiplier"))

    def observe_composition(self, elapsed_ms):
        self._target.observe_compose(elapsed_ms)

    def target_frame_rate_snapshot(self):
        return self._target.snapshot()

    def _target_preprocessor(self):
        mode = normalize_sr_mode(self._config.get("nn_super_resolution_mode"))
        if mode == NN_SR_OFF or not self._target_sr_ready:
            return None
        backend = self._active_backend()
        def apply_sr(rgba):
            try:return backend.apply_super_resolution(rgba, mode)
            except Exception as exc:
                self._load_error="Super-resolution failed: %s" % exc
                raise
        return apply_sr

    def offer_character_for_calibration(self, rgba):
        if self._hybrid_role_active or not self.target_frame_rate_enabled() or rgba is None:
            return
        if self._target_nn_available and self._target_probe_previous is not None:
            self._target.maybe_probe(self._active_backend(), self._target_probe_previous, rgba, self._target_preprocessor())
        self._target_probe_previous = rgba

    def _deliver_target_frame(self, rgba, serial, stamp):
        self._target.observe_delivery(stamp)
        callback = self._output_callback
        if callback is not None:
            callback(rgba, serial, stamp)

    def set_frame_transformer(self, transformer) -> None:
        if transformer != self._frame_transformer:
            self._stop_buffered_presenter()
            self._frame_transformer = transformer
            self._target.scene_mode = transformer is not None
            self._target.reset_plan()

    def set_scene_output_rate(self, hz, *, independent=False):
        self._scene_rate_hz = max(1., float(hz))
        self._scene_clock_independent = bool(independent)

    def set_output_callback(self, callback) -> None:
        self._output_callback = callback

    def set_buffered_enabled(self, enabled: bool) -> None:
        self._buffered_enabled = bool(enabled)
        if not enabled:
            self._stop_buffered_presenter()

    def _stop_buffered_presenter(self) -> None:
        presenter = self._buffered_presenter
        self._buffered_presenter = None
        self._next_source_time = None
        self._reserved_source_time = None
        self._last_source_time = None
        self._last_source_period = None
        if presenter is not None:
            presenter.close()

    def buffered_rife_requested(self) -> bool:
        if self.target_frame_rate_enabled() or self._frame_transformer is not None and self._effective_nn_multiplier() == 1:
            return (self._buffered_enabled and self._output_callback is not None
                    and (not self._scene_clock_independent or self._frame_transformer is not None))
        return (not self.last_error and self._buffered_enabled and self._output_callback is not None
                and self.is_active() and self._nn_sessions_preloaded
                and normalize_sr_mode(self._config.get("nn_super_resolution_mode")) == NN_SR_OFF
                and self._effective_nn_multiplier() > 1)

    def is_buffered_rife_active(self) -> bool:
        p = self._buffered_presenter
        return p is not None and p.last_error is None and self.buffered_rife_requested()

    @property
    def last_error(self):
        if self.target_frame_rate_enabled():
            # Unreachable FPS/optional RIFE are silent; explicit SR failures remain visible.
            return self._load_error if normalize_sr_mode(self._config.get("nn_super_resolution_mode")) != NN_SR_OFF else None
        p = self._buffered_presenter
        return (p.last_error if p is not None else None) or self._load_error

    def get_source_rate_limit_hz(self) -> int:
        if self.target_frame_rate_enabled():
            return self._target_plan().source_hz
        mult = self._effective_nn_multiplier()
        if mult <= 1:
            return self._scene_rate_hz if self._frame_transformer is not None else 30
        tha = SHARED_GPU_GATE.service_ms("tha3")
        nn = SHARED_GPU_GATE.service_ms("rife_frame%d" % mult)
        if nn is None:
            nn = SHARED_GPU_GATE.service_ms("rife%d" % mult)
        if tha is None or nn is None:
            # bh-1 26.10.30 11:05 s
            return 30
            # bh-1 26.10.30 11:05 e
        base = 6
        # bh-1 26.10.30 11:05 s
        for rate in (6, 8, 10, 12, 15, 18, 20, 24, 30, 45, 60):
            # bh-1 26.10.30 11:05 e
            presenter = self._buffered_presenter
            transform = (sum(presenter.transform_ms) / len(presenter.transform_ms)
                         if presenter is not None and presenter.transform_ms else 0.)
            if (rate * mult <= 240 and max(12, rate) * tha + rate * nn <= 950.
                    and rate * (nn + transform) <= 950.):
                base = rate
        now = time.perf_counter()
        previous = self._source_rate_hz
        wait = 2.0 if base < previous else 6.0
        if base != previous and now - self._rate_changed_at >= wait:
            self._source_rate_hz = base
            self._rate_changed_at = now
        return self._source_rate_hz

    def get_model_rate_limit_hz(self) -> int:
        if self.target_frame_rate_enabled():
            return self._target_plan().model_hz
        source = self.get_source_rate_limit_hz()
        mult = self._effective_nn_multiplier()
        tha = SHARED_GPU_GATE.service_ms("tha3")
        nn = SHARED_GPU_GATE.service_ms("rife_frame%d" % mult)
        if nn is None:
            nn = SHARED_GPU_GATE.service_ms("rife%d" % mult)
        if tha is None or nn is None:
            # bh-1 26.10.30 11:05 s
            return max(30, source)
            # bh-1 26.10.30 11:05 e
        best = max(30, source)
        # Spend spare capacity on fresher real endpoints; keep user's cap in source.
        # bh-1 26.10.30 11:05 s
        for rate in (12, 15, 18, 20, 24, 30, 45, 60):
            # bh-1 26.10.30 11:05 e
            if rate >= source and rate * tha + source * nn <= 950.:
                best = rate
        return best

    def should_compose_source_frame(self, now=None) -> bool:
        if not self.buffered_rife_requested() and not self.target_frame_rate_enabled():
            return True
        now = time.perf_counter() if now is None else float(now)
        period = 1. / self.get_source_rate_limit_hz()
        due = self._next_source_time
        if self._last_source_time is not None and self._last_source_period is not None and abs(period-self._last_source_period)>1.e-6:
            due=self._last_source_time+period
        self._last_source_period=period
        if due is None or now - due > .25:
            due = now
        if now < due:
            return False
        self._reserved_source_time = due
        self._next_source_time = due + period
        return True

    def apply(self, rgba: np.ndarray, *, is_new_real_frame: bool = True) -> np.ndarray:
        if rgba is None:
            return rgba
        frame = np.ascontiguousarray(rgba, dtype=np.uint8)
        if self.target_frame_rate_enabled():
            if not self._scene_clock_independent or self._frame_transformer is not None:
                self.offer_character_for_calibration(frame)
            current = self._buffered_presenter
            wanted = self._effective_nn_multiplier()
            if current is not None and current.last_error:
                self._target.disable_method(current.multiplier)
                self._stop_buffered_presenter()
                wanted = self._effective_nn_multiplier()
            elif current is not None and current.multiplier != wanted:
                if wanted > 1:current.backend = self._active_backend()
                current.request_multiplier(wanted)  # Keep queued playout and serial chronology.
        if self.target_frame_rate_enabled() and self._scene_clock_independent and self._frame_transformer is None:
            self._last_source_time=self._reserved_source_time
            self._reserved_source_time=None
            return frame  # UI final compositor owns layers; never send its pixels into RIFE.
        if self.last_error:
            return frame
        if self.buffered_rife_requested():
            if self.last_error:
                return frame
            if self._buffered_presenter is None:
                self._buffered_presenter = BufferedRifePresenter(
                    self._active_backend() if self._effective_nn_multiplier() > 1 else None,
                    self._effective_nn_multiplier(),
                    self._deliver_target_frame if self.target_frame_rate_enabled() else self._output_callback,
                    delay_seconds=.45 if self.target_frame_rate_enabled() or self._effective_nn_multiplier() > 1 else .08,
                    transform_batch=self._frame_transformer,
                    preprocess_frame=self._target_preprocessor() if self.target_frame_rate_enabled() else None)
            stamp = self._reserved_source_time
            self._reserved_source_time = None
            stamp=time.perf_counter() if stamp is None else stamp
            self._last_source_time=stamp
            self._buffered_presenter.submit(frame, stamp)
            self._last_frame_tag = FrameSourceTag.REAL if self._effective_nn_multiplier() == 1 else FrameSourceTag.RIFE
            return frame
        if not self._buffered_enabled and self.is_active() and self._nn_sessions_preloaded:
            try:
                return self._active_backend().apply_super_resolution(frame, normalize_sr_mode(self._config.get("nn_super_resolution_mode")))
            except Exception as exc:
                self._load_error = "%s: %s" % (type(exc).__name__, exc)
                return frame
        try:
            return self._apply_sync_legacy(frame, is_new_real_frame=is_new_real_frame)
        except Exception as exc:
            self._load_error = "%s: %s" % (type(exc).__name__, exc)
            return frame

    def _apply_sync_legacy(self, rgba: np.ndarray, *, is_new_real_frame: bool = True) -> np.ndarray:
        """Apply SR to real frame; queue RIFE mids when enabled."""
        if rgba is None:
            return rgba
        frame = np.asarray(rgba, dtype=np.uint8)
        if not self.is_active():
            self._last_frame_tag = FrameSourceTag.REAL
            return frame

        # bh-1 26.10.29 20:24 s
        if not self._nn_sessions_preloaded:
            self._last_frame_tag = FrameSourceTag.REAL
            return frame
        # bh-1 26.10.29 20:24 e

        if not self._require_backend():
            if not self._warned_missing:
                self._warned_missing = True
            self._last_frame_tag = FrameSourceTag.REAL
            return frame

        backend = self._active_backend()
        sr_mode = normalize_sr_mode(self._config.get("nn_super_resolution_mode"))
        rife_mult = self._effective_nn_multiplier()

        if is_new_real_frame and rife_mult > NN_FRAME_INTERP_OFF and self._prev_rgba is not None:
            if (self._prev_rgba.shape[0] == frame.shape[0]
                    and self._prev_rgba.shape[1] == frame.shape[1]):
                try:
                    mids = backend.interpolate_rife(
                        self._prev_rgba, frame, rife_mult, fp16=False)
                    self._rife_queue.clear()
                    for mid in mids:
                        enhanced = backend.apply_super_resolution(mid, sr_mode)
                        self._rife_queue.append(enhanced)
                except Exception as exc:
                    self._load_error = "%s: %s" % (type(exc).__name__, exc)

        if self._rife_queue:
            self._prev_rgba = frame.copy()
            self._last_frame_tag = FrameSourceTag.RIFE
            return self._rife_queue.popleft()
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
        self._stop_buffered_presenter()
        self._target.close()
        if self._ort is not None:
            self._ort.shutdown()
            self._ort = None
        if self._trt is not None:
            self._trt.shutdown()
            self._trt = None
        # bh-1 26.10.29 20:24 s
        self._nn_sessions_preloaded = False
        # bh-1 26.10.29 20:24 e
        self.reset_rife_buffers()
