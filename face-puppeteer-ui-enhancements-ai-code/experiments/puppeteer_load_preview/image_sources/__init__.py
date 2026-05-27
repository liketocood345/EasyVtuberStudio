"""Dual image-source black boxes for load_preview (THA4 student / THA3)."""
from image_sources.base import ImageSource, LoadUiSpec
from image_sources.factory import create_image_source, switch_image_source

__all__ = [
    "ImageSource",
    "LoadUiSpec",
    "create_image_source",
    "switch_image_source",
]
