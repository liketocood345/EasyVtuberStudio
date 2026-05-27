from __future__ import annotations

from typing import Optional

from image_sources.base import LoadUiSpec
from tha3_paths import IMAGE_SOURCE_THA4


class Tha4StudentSource:
    mode_id = IMAGE_SOURCE_THA4

    def start(self, main_frame) -> None:
        return

    def stop(self, main_frame) -> None:
        main_frame.poser = None
        main_frame.character_model = None
        main_frame.torch_source_image = None
        main_frame.wx_source_image = None
        main_frame.last_pose = None
        main_frame._load_preview_shown = False

    def is_ready(self, main_frame) -> bool:
        return main_frame.poser is not None and main_frame.torch_source_image is not None

    def load_asset(self, main_frame, path: str) -> bool:
        return main_frame.load_model_from_path(path)

    def tick(self, main_frame) -> Optional[str]:
        return main_frame.tick_tha4_student_source()

    def get_load_ui_spec(self) -> LoadUiSpec:
        return LoadUiSpec(
            show_yaml_loader=True,
            show_png_loader=False,
            show_tha3_variant=False,
            status_hint="THA4 Student：需 character_model.yaml + 蒸馏权重 / needs distilled student model",
        )
