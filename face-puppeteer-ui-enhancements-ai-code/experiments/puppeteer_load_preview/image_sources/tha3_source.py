from __future__ import annotations
from portable_process_env import debug_log_path
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

import threading
import time
from typing import List, Optional

import wx
import cv2

from image_sources.base import LoadUiSpec
from tha3_engine import Tha3Engine
from tha3_paths import IMAGE_SOURCE_THA3, tha3_inference_assets_available
from tha3_pose_adapter import mediapipe_pose_to_tha3_vector, neutral_tha3_pose


class Tha3Source:
    mode_id = IMAGE_SOURCE_THA3

    def __init__(self):
        self.engine: Optional[Tha3Engine] = None
        self.last_pose: Optional[List[float]] = None
        self._default_pose: Optional[List[float]] = None
        self._infer_lock = threading.Lock()
        self._pending_pose: Optional[List[float]] = None
        self._infer_active = False
        self._infer_generation = 0
        self._dbg_tick_log_mono = 0.0
        self._completed_result = None
        self._result_apply_scheduled = False
        self._last_inferred_pose = None
        self._last_submit_mono = 0.0
        self._next_submit_due = 0.0
        self._pending_sample_time = 0.0
        self._pending_face_meta = (0, 0.)
        self._latest_live_pose_snapshot = None
        self._worker_cap_hz = 30.0
        from output_enhancement.pose_interpolation import TimestampPoseSampler
        self._pose_sampler = TimestampPoseSampler()
        self._role_timeline = None
        self._timeline_wx_item = None
        self._timeline_wx_image = None
        self._latest_model_result = None
        self._was_target_timeline = False

    def start(self, main_frame) -> None:
        variant = getattr(main_frame, "tha3_model_variant", "separable_half")
        if not tha3_inference_assets_available(variant):
            self.engine = None
            return
        self.engine = Tha3Engine(main_frame.device, model_variant=variant)
        self._default_pose = neutral_tha3_pose(main_frame.pose_converter)
        self.last_pose = None

    def stop(self, main_frame) -> None:
        main_frame._tha3_load_generation = int(getattr(main_frame, "_tha3_load_generation", 0)) + 1
        main_frame._tha3_load_in_progress = False
        if self._role_timeline is not None:self._role_timeline.close();self._role_timeline=None
        self._pose_sampler.reset()
        self._latest_model_result=None;self._was_target_timeline=False
        self._timeline_wx_item=None;self._timeline_wx_image=None
        with self._infer_lock:
            self._infer_generation += 1
            self._completed_result = None
            self._result_apply_scheduled = False
            self._last_inferred_pose = None
            self._pending_pose = None
            self._latest_live_pose_snapshot = None
            self._infer_active = False
        if self.engine is not None:
            self.engine.stop()
        self.engine = None
        self.last_pose = None
        self._default_pose = None
        main_frame.wx_source_image = None
        main_frame.last_output_wx_image = None
        main_frame._last_tha3_rgba = None
        main_frame._material_scene_failed = False
        main_frame._gpu_composition_disabled = False
        if hasattr(main_frame, "_close_buffered_scene_renderer"):
            main_frame._close_buffered_scene_renderer()
        main_frame.last_pose = None
        main_frame._load_preview_shown = False
        main_frame._invalidate_source_preview_cache()
        main_frame.update_source_image_bitmap(force=True)

    def is_ready(self, main_frame) -> bool:
        return self.engine is not None and self.engine.is_loaded()

    # EVS-DESIGN-AUDIT EVS-A064 BEGIN
    # 设计[f-022, doc-050, f-057] [部分符合 / 素材与线程边界]
    # 立绘加载和 THA3 独立源存在；尺寸/alpha 预处理为实现细节。doc-050 的 512 RGBA/mask 来自粘贴的 Agent 摘要，不据此扩大为全输入硬性用户要求。模型读取仍需检查 UI 阻塞。
    # 历史 bug 热点 #1,#5：仅为回归关联，非声称本次故障已复现。
    # EVS-DESIGN-AUDIT EVS-A064 END
    def load_asset(self, main_frame, path: str) -> bool:
        from tha3_assets_prompt import ensure_tha3_assets_available
        from output_enhancement.slow_task import run_slow_task

        variant = getattr(main_frame, "tha3_model_variant", "separable_half")
        if not ensure_tha3_assets_available(main_frame, variant):
            return False
        if getattr(main_frame, "_tha3_load_in_progress", False):
            return False
        if self.engine is None:
            self.start(main_frame)
        if self.engine is None:
            return False
        if hasattr(main_frame, "_reset_infer_worker_runtime"):
            main_frame._reset_infer_worker_runtime()
        with self._infer_lock:
            self._infer_generation += 1
            self._completed_result = None
            self._result_apply_scheduled = False
            self._last_inferred_pose = None
            self._pending_pose = None
            self._latest_live_pose_snapshot = None
            self._infer_active = False
        # f-022/f-070: the UI variant must identify the engine actually loaded.
        # Loading another PNG into the old engine does not switch model weights.
        if self.engine.model_variant != variant:
            self.engine.stop()
            self.start(main_frame)
            if self.engine is None:
                return False
        main_frame._last_tha3_rgba = None
        self._pose_sampler.reset()
        if self._role_timeline is not None:self._role_timeline.clear()
        close_scene = getattr(main_frame, "_close_buffered_scene_renderer", None)
        if close_scene is not None:close_scene()
        main_frame._gpu_composition_disabled = False
        # bh-2 26.10.29 21:43 s
        main_frame._tha3_load_in_progress = True
        main_frame._tha3_load_generation = int(
            getattr(main_frame, "_tha3_load_generation", 0) or 0) + 1
        generation = int(main_frame._tha3_load_generation)
        engine = self.engine
        default_pose = self._default_pose or neutral_tha3_pose(main_frame.pose_converter)
        result = {"ok": False, "error": None, "rgba": None, "load_ms": 0.0, "render_ms": 0.0}
        # #region agent log
        try:
            import json as _json, time as _time
            open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({"sessionId": "86a17c", "runId": "post-fix-tha3", "hypothesisId": "N", "location": "tha3_source.py:load_asset", "message": "tha3 load_asset queued off UI", "data": {"path": str(path)[-80:], "variant": str(variant), "gen": int(generation)}, "timestamp": int(_time.time() * 1000)}) + "\n")
        except Exception:
            pass
        # #endregion

        def task(progress) -> None:
            import time as _time
            progress("Loading THA3 character…", 0.2)
            t0 = _time.perf_counter()
            ok = engine.load_character_png(path)
            result["load_ms"] = (_time.perf_counter() - t0) * 1000.0
            result["ok"] = bool(ok)
            result["error"] = engine.last_error
            # #region agent log
            try:
                import json as _json
                open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({"sessionId": "86a17c", "runId": "post-fix-tha3", "hypothesisId": "N", "location": "tha3_source.py:load_character_png", "message": "tha3 load_character_png finished", "data": {"ok": bool(ok), "ms": round(float(result["load_ms"]), 1), "error": str(result["error"] or "")[:160]}, "timestamp": int(_time.time() * 1000)}) + "\n")
            except Exception:
                pass
            # #endregion
            if not ok:
                return
            progress("Rendering THA3 preview…", 0.7)
            t1 = _time.perf_counter()
            result["rgba"] = engine.render_pose_numpy(default_pose)
            result["render_ms"] = (_time.perf_counter() - t1) * 1000.0
            if result["rgba"] is not None:
                progress("Calibrating CUDA playback…", 0.85)
                engine.prepare_cuda_graph(default_pose)
                result["cuda_graph"] = dict(engine.cuda_graph_status)
            # #region agent log
            try:
                import json as _json
                open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({"sessionId": "86a17c", "runId": "post-fix-tha3", "hypothesisId": "N", "location": "tha3_source.py:render_pose_numpy", "message": "tha3 first render finished", "data": {"has_rgba": result["rgba"] is not None, "ms": round(float(result["render_ms"]), 1), "cuda_graph": dict(engine.cuda_graph_status)}, "timestamp": int(_time.time() * 1000)}) + "\n")
            except Exception:
                pass
            # #endregion

        def on_done() -> None:
            if (int(generation) != int(getattr(main_frame, "_tha3_load_generation", 0) or 0)
                    or main_frame.active_image_source is not self):
                return
            main_frame._tha3_load_in_progress = False
            if getattr(main_frame, "_is_closing", False):
                return
            # f-022: a choice event during an async load is latest-wins too.
            # Never publish a completed old variant over the newly selected one.
            if getattr(main_frame, "tha3_model_variant", engine.model_variant) != engine.model_variant:
                wx.CallAfter(self.load_asset, main_frame, path)
                return
            # #region agent log
            try:
                import json as _json, time as _time
                open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({"sessionId": "86a17c", "runId": "post-fix-tha3", "hypothesisId": "N", "location": "tha3_source.py:load_asset:on_done", "message": "tha3 load_asset apply on UI", "data": {"ok": bool(result["ok"]), "load_ms": round(float(result["load_ms"]), 1), "render_ms": round(float(result["render_ms"]), 1)}, "timestamp": int(_time.time() * 1000)}) + "\n")
            except Exception:
                pass
            # #endregion
            if not result["ok"]:
                if hasattr(main_frame, "_ui_alignment_toast"):
                    main_frame._ui_alignment_toast(
                        "THA3 load failed: %s" % (result["error"] or path))
                return
            main_frame.last_tha3_character_png = path
            try:
                import PIL.Image

                pil = PIL.Image.open(path).convert("RGBA")
                if pil.size != (512, 512):
                    pil = pil.resize((512, 512), PIL.Image.LANCZOS)
                main_frame.wx_source_image = wx.Bitmap.FromBufferRGBA(512, 512, pil.tobytes())
            except Exception:
                main_frame.wx_source_image = None
            main_frame._invalidate_source_preview_cache()
            main_frame.update_source_image_bitmap(force=True)
            rgba = result["rgba"]
            if rgba is not None:
                from tha3_engine import _numpy_rgba_to_wx_image
                wx_image = _numpy_rgba_to_wx_image(rgba)
                main_frame._last_tha3_rgba = cv2.cvtColor(rgba, cv2.COLOR_BGRA2RGBA)
                main_frame.last_output_wx_image = wx_image
                main_frame.last_pose = default_pose
                main_frame.draw_result_wx_image(
                    wx_image,
                    main_frame.LOAD_PREVIEW_BANNER,
                    fast_affine_only=not main_frame.is_layer_blend_enabled())
                main_frame._load_preview_shown = True
            if hasattr(main_frame, "save_persistent_ui_state"):
                main_frame.save_persistent_ui_state()
            if hasattr(main_frame, "update_load_model_buttons"):
                main_frame.update_load_model_buttons()
            if hasattr(main_frame, "refresh_basic_layer_window_if_visible"):
                main_frame.refresh_basic_layer_window_if_visible()
            if hasattr(main_frame, "maybe_open_region_wobble_after_character_load"):
                main_frame.maybe_open_region_wobble_after_character_load()
            if hasattr(main_frame, "_activate_mocap_capture_after_model_load"):
                osf = getattr(main_frame, "_osf_runtime", None)
                already_running = (
                    osf is not None
                    and bool(getattr(getattr(osf, "status", None), "process_running", False)))
                if not already_running:
                    main_frame._activate_mocap_capture_after_model_load()
            if hasattr(main_frame, "_maybe_warmup_output_enhancement"):
                wx.CallAfter(main_frame._maybe_warmup_output_enhancement)

        def on_error(exc: Exception) -> None:
            if (int(generation) != int(getattr(main_frame, "_tha3_load_generation", 0) or 0)
                    or main_frame.active_image_source is not self):
                return
            main_frame._tha3_load_in_progress = False
            if getattr(main_frame, "tha3_model_variant", engine.model_variant) != engine.model_variant:
                wx.CallAfter(self.load_asset, main_frame, path)
                return
            # #region agent log
            try:
                import json as _json, time as _time
                open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({"sessionId": "86a17c", "runId": "post-fix-tha3", "hypothesisId": "N", "location": "tha3_source.py:load_asset:on_error", "message": "tha3 load_asset worker error", "data": {"error": repr(exc)[:200]}, "timestamp": int(_time.time() * 1000)}) + "\n")
            except Exception:
                pass
            # #endregion
            if hasattr(main_frame, "_ui_alignment_toast"):
                main_frame._ui_alignment_toast("THA3 load failed: %s" % exc)

        run_slow_task(
            main_frame.get_dialog_parent() if hasattr(main_frame, "get_dialog_parent") else main_frame,
            "Loading THA3…",
            task,
            on_complete=on_done,
            on_error=on_error)
        # bh-2 26.10.29 21:43 e
        return True

    def publish_live_pose(self, main_frame):
        """UI-only conversion on every new valid face, independent of infer timer."""
        current_pose = mediapipe_pose_to_tha3_vector(
            main_frame.mediapipe_face_pose, main_frame.pose_converter)
        current_pose = main_frame.apply_negative_tilt_limit_to_pose(current_pose)
        current_pose = main_frame.apply_invert_tilt_mapping_to_pose(current_pose)
        now = time.perf_counter()
        sample_stamp = now
        # f-070: inference is independent of the postprocess model_hz plan.
        cap = max(1., float(main_frame.get_mouth_infer_cap_hz()))
        enhancement = getattr(main_frame, "output_enhancement", None)
        if enhancement is not None and enhancement.target_frame_rate_enabled():
            current_pose, sample_stamp = self._pose_sampler.sample(current_pose, now)
        face_meta = (main_frame._latest_face_pose_sequence, main_frame._latest_face_sample_mono)
        self._latest_live_pose_snapshot = (tuple(current_pose), sample_stamp, face_meta)
        self._worker_cap_hz = cap
        return current_pose, sample_stamp, cap, face_meta

    def tick(self, main_frame) -> Optional[str]:
        if getattr(main_frame, "_tha3_load_in_progress", False):
            return "loading"
        engine = self.engine
        if engine is None or not engine.is_loaded():
            return "no_model"
        # Display timer owns composition; inference must not add another full draw.
        main_frame.update_display_transform_state()
        if main_frame.mediapipe_face_pose is None or not main_frame.is_mocap_sample_fresh():
            self._latest_live_pose_snapshot = None
            return "no_face"
        now = time.perf_counter()
        current_pose, sample_stamp, cap, face_meta = self.publish_live_pose(main_frame)
        with self._infer_lock:
            due = self._next_submit_due
            if due <= 0. or now - due > .25:
                due = now
            if now < due:
                return "throttled"
            self._next_submit_due = due + 1.0 / cap
            self._last_submit_mono = now
            self._pending_pose = list(current_pose)
            self._pending_sample_time = sample_stamp
            self._pending_face_meta = face_meta
            if self._infer_active:
                return "queued"
            self._infer_active = True
            generation = int(self._infer_generation)
        threading.Thread(target=self._infer_worker,
                         args=(main_frame, generation, engine),
                         daemon=True, name="tha3-pose-infer").start()
        return "queued"

    def _infer_worker(self, main_frame, generation: int, engine) -> None:
        # EVS-PERF-20261029 (f-057/f-068): bounded latest-result mailbox.
        # A faster model must not create an ever-growing wx.CallAfter draw queue.
        last_render_start = 0.
        while True:
            now = time.perf_counter()
            remain = 1. / max(1., self._worker_cap_hz) - (now - last_render_start)
            if last_render_start and remain > 0.:
                time.sleep(min(.008, remain))
                continue
            with self._infer_lock:
                if generation != int(self._infer_generation):
                    return
                pose = self._pending_pose
                sample_time = self._pending_sample_time
                face_meta = self._pending_face_meta
                self._pending_pose = None
            snapshot = self._latest_live_pose_snapshot
            if snapshot is not None:
                pose, sample_time, face_meta = list(snapshot[0]), snapshot[1], snapshot[2]
            # （UI infer timer 被 compose 饿死，worker 自抽 pose 保 Inf≥10）26.10.30 14:28 s
            if pose is None:
                if getattr(main_frame, "_is_closing", False) or engine is None or not engine.is_loaded():
                    with self._infer_lock:
                        self._infer_active = False
                    return
                cap = self._worker_cap_hz
                now = time.perf_counter()
                snapshot = self._latest_live_pose_snapshot
                if snapshot is None:
                    time.sleep(0.008)
                    continue
                pose, sample_time = list(snapshot[0]), snapshot[1]
                face_meta = snapshot[2]
            # （UI infer timer 被 compose 饿死，worker 自抽 pose 保 Inf≥10）26.10.30 14:28 e
            if not main_frame.is_mocap_sample_fresh(face_meta):
                time.sleep(.008)
                continue
            main_frame._last_model_face_sequence, main_frame._last_model_face_sample_mono = face_meta
            t0 = time.perf_counter()
            last_render_start = t0
            rgba = engine.render_pose_numpy(pose)
            render_ms = (time.perf_counter() - t0) * 1000.0
            # #region agent log
            try:
                now = time.perf_counter()
                if now - float(self._dbg_tick_log_mono or 0.0) >= 1.0:
                    self._dbg_tick_log_mono = now
                    import json as _json
                    open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({
                        "sessionId": "86a17c",
                        "runId": "post-fix-tha3-cap10",
                        "hypothesisId": "T3",
                        "location": "tha3_source.py:_infer_worker",
                        "message": "tha3 background infer",
                        "data": {
                            "ms": round(float(render_ms), 1),
                            "ok": rgba is not None,
                            "ui_thread": False,
                            "inf_fps": round(float(getattr(main_frame, "_inference_fps", 0.0) or 0.0), 2),
                            "mouth_cap": int(main_frame.get_mouth_infer_cap_hz()),
                            "source": "tha3",
                            "cuda_graph": bool((getattr(engine, "cuda_graph_status", None) or {}).get("enabled")),
                            "cuda_reason": str((getattr(engine, "cuda_graph_status", None) or {}).get("reason") or ""),
                            "backend": str(getattr(engine, "_backend_kind", "") or ""),
                            "variant": str(getattr(engine, "model_variant", "") or ""),
                        },
                        "timestamp": int(time.time() * 1000),
                    }) + "\n")
            except Exception:
                pass
            # #endregion
            schedule_apply = False
            with self._infer_lock:
                if generation != int(self._infer_generation):
                    return
                if rgba is not None:
                    self._last_inferred_pose = list(pose)
                self._completed_result = (pose, rgba, generation, render_ms, sample_time)
                if not self._result_apply_scheduled:
                    self._result_apply_scheduled = True
                    schedule_apply = True
            # Completion statistics belong to the real model worker, not UI draws.
            if rgba is not None and not getattr(main_frame, "_is_closing", False):
                main_frame._note_inference_fps_tick()
            if schedule_apply:
                wx.CallAfter(self._flush_infer_result, main_frame)

    def _flush_infer_result(self, main_frame) -> None:
        with self._infer_lock:
            result = self._completed_result
            self._completed_result = None
            self._result_apply_scheduled = False
        if result is not None:
            self._apply_infer_result(main_frame, *result)

    def _apply_infer_result(self, main_frame, pose, rgba, generation: int,
                            render_ms: float, sample_time: float = 0.0) -> None:
        if getattr(main_frame, "_is_closing", False):
            return
        if generation != int(self._infer_generation):
            return
        if getattr(main_frame, "_tha3_load_in_progress", False):
            return
        if rgba is None or self.engine is None or not self.engine.is_loaded():
            return
        from tha3_engine import _numpy_rgba_to_wx_image
        wx_image = _numpy_rgba_to_wx_image(rgba)
        self.last_pose = list(pose)
        main_frame.last_pose = list(pose)
        main_frame.last_output_wx_image = wx_image
        import cv2
        main_frame._last_tha3_rgba = cv2.cvtColor(rgba, cv2.COLOR_BGRA2RGBA)
        main_frame._last_real_model_sample_time = float(sample_time)
        main_frame.last_background_choice = main_frame.get_output_background_signature()
        self._latest_model_result=(wx_image,main_frame._last_tha3_rgba,tuple(pose))
        enhancement=main_frame.output_enhancement
        if getattr(enhancement,"target_frame_rate_enabled",lambda:False)() and main_frame.get_nn_super_resolution_mode()=="off":
            if self._role_timeline is None:
                from output_enhancement.hybrid_role_timeline import HybridRoleTimeline
                self._role_timeline=HybridRoleTimeline(delay=.45)
            self._role_timeline.offer(main_frame._last_tha3_rgba,float(sample_time or time.perf_counter()),pose)
        else:
            enhancement.pose_interpolation.seed_after_real_infer(pose)
        # on_display_timer observes the new image id and performs one composition.

    def prepare_target_presentation(self, main_frame):
        enhancement=main_frame.output_enhancement;pipe=enhancement.pipeline
        active=enhancement.target_frame_rate_enabled() and main_frame.get_nn_super_resolution_mode()=="off"
        pipe._hybrid_role_active=active
        if not active:
            if self._was_target_timeline and self._latest_model_result is not None:
                image,rgba,pose=self._latest_model_result
                main_frame.last_output_wx_image=image;main_frame._last_tha3_rgba=rgba;main_frame.last_pose=list(pose)
                if self._role_timeline is not None:self._role_timeline.clear()
            self._was_target_timeline=False
            return False
        self._was_target_timeline=True
        if self._role_timeline is None:return True
        backend=pipe._active_backend() if pipe._target_nn_available else None
        real_hz=float(getattr(main_frame,'_inference_fps',0.) or pipe.get_model_rate_limit_hz())
        self._role_timeline.configure(backend,main_frame.get_target_frame_rate_fps(),real_hz)
        item=self._role_timeline.sample(time.perf_counter())
        if item is None:return True
        if self._timeline_wx_item is not item:
            from tha3_engine import _numpy_rgba_to_wx_image
            self._timeline_wx_image=_numpy_rgba_to_wx_image(cv2.cvtColor(item.rgba,cv2.COLOR_RGBA2BGRA))
            self._timeline_wx_item=item
        main_frame.last_output_wx_image=self._timeline_wx_image
        main_frame.last_pose=list(item.pose)
        main_frame._last_tha3_rgba=item.rgba
        main_frame._hybrid_role_statistics=self._role_timeline.snapshot()
        # f-070: local diagnostics for the actual app, not benchmark-only FPS.
        now=time.perf_counter()
        if hasattr(main_frame,"persistent_ui_state") and now-getattr(self,"_last_timeline_log",0.)>=5.:
            self._last_timeline_log=now
            try:
                import json
                from tha3_paths import find_repo_root
                from output_enhancement.gpu_work_gate import SHARED_GPU_GATE
                path=find_repo_root()/"workspace"/"target_fps_diagnostics.jsonl"
                path.parent.mkdir(parents=True,exist_ok=True)
                if path.exists() and path.stat().st_size>5*1024*1024:path.replace(path.with_name("target_fps_diagnostics.previous.jsonl"))
                info=dict(utc_epoch=time.time(),model_variant=getattr(self.engine,"model_variant",None),cuda_graph=dict(getattr(self.engine,"cuda_graph_status",{})),real_fps=real_hz,model_service_ms=SHARED_GPU_GATE.service_ms("tha3"),target_fps=main_frame.get_target_frame_rate_fps(),selected_pose_age_ms=(now-item.stamp)*1000.,nn_backend=type(backend).__name__ if backend is not None else None,hybrid=main_frame._hybrid_role_statistics)
                with path.open("a",encoding="utf-8") as stream:stream.write(json.dumps(info,ensure_ascii=False)+"\n")
            except Exception:pass
        return False

    def get_load_ui_spec(self) -> LoadUiSpec:
        return LoadUiSpec(
            show_yaml_loader=False,
            show_png_loader=True,
            show_tha3_variant=True,
            status_hint="THA3：512 RGBA 立绘即用，实时占用更高 / PNG ready, heavier runtime",
        )
