from __future__ import annotations

import os
from typing import Optional

from image_sources.base import LoadUiSpec, normalize_image_source_mode
from image_sources.tha3_source import Tha3Source
from image_sources.tha4_student_source import Tha4StudentSource
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


def switch_image_source(main_frame, new_mode: str):
    normalized = normalize_image_source_mode(new_mode)
    if main_frame.active_image_source.mode_id == normalized:
        _sync_image_source_mode_choice(main_frame, normalized)
        return
    main_frame.active_image_source.stop(main_frame)
    main_frame.active_image_source = create_image_source(normalized)
    main_frame.image_source_mode = normalized
    _sync_image_source_mode_choice(main_frame, normalized)
    main_frame.active_image_source.start(main_frame)
    main_frame.refresh_image_source_ui_visibility()
    if normalized == IMAGE_SOURCE_THA4 and main_frame.last_loaded_model_path:
        if os.path.isfile(main_frame.last_loaded_model_path):
            main_frame.load_model_from_path(main_frame.last_loaded_model_path)
        else:
            main_frame.refresh_model_loaded_ui_state()
            main_frame.update_result_image_bitmap()
    elif normalized == IMAGE_SOURCE_THA3 and main_frame.last_tha3_character_png:
        if os.path.isfile(main_frame.last_tha3_character_png):
            main_frame.active_image_source.load_asset(main_frame, main_frame.last_tha3_character_png)
        else:
            main_frame.update_result_image_bitmap()
    else:
        main_frame.update_result_image_bitmap()
    main_frame.save_persistent_ui_state()
