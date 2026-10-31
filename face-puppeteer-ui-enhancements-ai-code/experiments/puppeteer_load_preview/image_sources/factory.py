from __future__ import annotations
from portable_process_env import debug_log_path
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

import os
from typing import Optional

from image_sources.base import LoadUiSpec, normalize_image_source_mode
from image_sources.tha3_source import Tha3Source
from image_sources.tha4_student_source import Tha4StudentSource
from tha3_assets_prompt import ensure_tha3_assets_available
from tha3_paths import IMAGE_SOURCE_THA3, IMAGE_SOURCE_THA4


def create_image_source(mode: Optional[str]):
    normalized = normalize_image_source_mode(mode)
    if normalized == IMAGE_SOURCE_THA3:
        return Tha3Source()
    return Tha4StudentSource()


def _sync_image_source_mode_choice(main_frame, normalized: str) -> None:
    if not hasattr(main_frame, "image_source_mode_choice"):
        return
    desired = 1 if normalized == IMAGE_SOURCE_THA3 else 0
    if main_frame.image_source_mode_choice.GetSelection() == desired:
        return
    main_frame._suppress_image_source_mode_event = True
    try:
        main_frame.image_source_mode_choice.SetSelection(desired)
    finally:
        main_frame._suppress_image_source_mode_event = False


# EVS-DESIGN-AUDIT EVS-A063 BEGIN
# 设计[f-022, f-063] [部分符合]
# THA3/THA4 并列图像源，先 stop 旧源再 start 新源；f-022 后标无必要是已满足而非删除源。异常时没有覆盖 stop/start/load 全程的事务回落，不能认定任意失败都会恢复旧 UI/源。
# 历史 bug 热点 #2,#5：仅为回归关联，非声称本次故障已复现。
# EVS-DESIGN-AUDIT EVS-A063 END
def switch_image_source(main_frame, new_mode: str, *, autoload_asset: bool = True):
    # #region agent log
    try:
        import json as _json, time as _time
        open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({"sessionId": "86a17c", "runId": "post-fix-tha3", "hypothesisId": "Q", "location": "factory.py:switch_image_source", "message": "switch image source", "data": {"new_mode": str(new_mode), "autoload": bool(autoload_asset), "from": str(getattr(main_frame.active_image_source, "mode_id", ""))}, "timestamp": int(_time.time() * 1000)}) + "\n")
    except Exception:
        pass
    # #endregion
    normalized = normalize_image_source_mode(new_mode)
    if normalized == IMAGE_SOURCE_THA3 and not ensure_tha3_assets_available(main_frame):
        normalized = IMAGE_SOURCE_THA4
    if main_frame.active_image_source.mode_id == normalized:
        _sync_image_source_mode_choice(main_frame, normalized)
        return
    main_frame.active_image_source.stop(main_frame)
    main_frame.active_image_source = create_image_source(normalized)
    main_frame.image_source_mode = normalized
    reset_smooth = getattr(main_frame, "_reset_pose_smooth_buffer", None)
    if callable(reset_smooth):
        reset_smooth()
    _sync_image_source_mode_choice(main_frame, normalized)
    main_frame.active_image_source.start(main_frame)
    main_frame.refresh_image_source_ui_visibility()
    if autoload_asset:
        if normalized == IMAGE_SOURCE_THA4 and main_frame.last_loaded_model_path:
            model_path = main_frame.resolve_character_model_path(main_frame.last_loaded_model_path)
            if model_path and os.path.isfile(model_path):
                main_frame.load_model_from_path(model_path)
            else:
                main_frame.refresh_model_loaded_ui_state()
                main_frame.update_result_image_bitmap()
        elif normalized == IMAGE_SOURCE_THA3 and main_frame.last_tha3_character_png:
            png_path = main_frame.resolve_character_model_path(main_frame.last_tha3_character_png)
            if png_path and os.path.isfile(png_path):
                main_frame.active_image_source.load_asset(main_frame, png_path)
            else:
                main_frame.update_result_image_bitmap()
        else:
            main_frame.update_result_image_bitmap()
    else:
        main_frame.update_result_image_bitmap()
    main_frame.save_persistent_ui_state()
    monitor = getattr(main_frame, "_ui_alignment_monitor", None)
    if monitor is not None:
        monitor.notify_switch(["image_source"])
    return True
