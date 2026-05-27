from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

import wx

from tha3_paths import IMAGE_SOURCE_THA3, IMAGE_SOURCE_THA4


@dataclass
class LoadUiSpec:
    show_yaml_loader: bool = True
    show_png_loader: bool = False
    show_tha3_variant: bool = False
    status_hint: str = ""


@runtime_checkable
class ImageSource(Protocol):
    mode_id: str

    def start(self, main_frame) -> None: ...

    def stop(self, main_frame) -> None: ...

    def is_ready(self, main_frame) -> bool: ...

    def load_asset(self, main_frame, path: str) -> bool: ...

    def tick(self, main_frame) -> Optional[str]: ...

    def get_load_ui_spec(self) -> LoadUiSpec: ...


def normalize_image_source_mode(mode: Optional[str]) -> str:
    if mode == IMAGE_SOURCE_THA3:
        return IMAGE_SOURCE_THA3
    return IMAGE_SOURCE_THA4
