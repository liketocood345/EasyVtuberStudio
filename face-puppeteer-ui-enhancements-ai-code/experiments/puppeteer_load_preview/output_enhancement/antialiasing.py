"""SSAA anti-aliasing for character keyframe compose (pre-layer-stack)."""
from __future__ import annotations

import math
from typing import Any, Callable, Optional, Tuple

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

from output_enhancement.rgba_ops import resize_rgba, sanitize_transparent_rgb as _sanitize_rgba

DEFAULT_ANTIALIAS_STRENGTH = 1.0


def normalize_antialias_strength(value: Any) -> float:
    try:
        strength = float(value)
    except (TypeError, ValueError):
        strength = DEFAULT_ANTIALIAS_STRENGTH
    return max(1.0, strength)


def get_antialias_factor_from_control(control: Any) -> float:
    if control is None:
        return DEFAULT_ANTIALIAS_STRENGTH
    try:
        return normalize_antialias_strength(control.GetValue())
    except Exception:
        return DEFAULT_ANTIALIAS_STRENGTH


def upscale_keyframe_for_ssaa(
        source_rgba: np.ndarray,
        wx_width: int,
        wx_height: int,
        antialias_factor: float) -> Tuple[np.ndarray, int, int]:
    """Upscale THA keyframe RGBA when SSAA factor > 1."""
    factor = normalize_antialias_strength(antialias_factor)
    keyframe_width = max(1, int(round(wx_width * factor)))
    keyframe_height = max(1, int(round(wx_height * factor)))
    source_rgba = np.ascontiguousarray(source_rgba, dtype=np.uint8)
    if keyframe_width != wx_width or keyframe_height != wx_height:
        return resize_rgba(source_rgba, keyframe_width, keyframe_height), keyframe_width, keyframe_height
    return source_rgba, keyframe_width, keyframe_height


def compose_character_rgba_from_keyframe(
        keyframe_rgba: np.ndarray,
        canvas_width: int,
        canvas_height: int,
        *,
        anchor_x: float,
        anchor_y: float,
        scale: float,
        rotation_deg: float,
        antialias_factor: float = 1.0) -> np.ndarray:
    """Match wx GraphicsContext transform: translate, rotate, scale, draw feet anchor."""
    if cv2 is None:
        raise RuntimeError("opencv (cv2) required for character SSAA compose")
    keyframe_rgba = np.ascontiguousarray(keyframe_rgba, dtype=np.uint8)
    keyframe_height, keyframe_width = keyframe_rgba.shape[0], keyframe_rgba.shape[1]
    factor = normalize_antialias_strength(antialias_factor)
    render_width = max(1, int(round(canvas_width * factor)))
    render_height = max(1, int(round(canvas_height * factor)))
    display_scale = max(0.1, float(scale))
    rotation_rad = math.radians(float(rotation_deg))
    cos_r = math.cos(rotation_rad)
    sin_r = math.sin(rotation_rad)

    anchor_x_render = float(anchor_x) * factor
    anchor_y_render = float(anchor_y) * factor
    tx = (
        anchor_x_render
        - display_scale * cos_r * keyframe_width / 2.0
        + display_scale * sin_r * keyframe_height)
    ty = (
        anchor_y_render
        - display_scale * sin_r * keyframe_width / 2.0
        - display_scale * cos_r * keyframe_height)
    forward = np.array(
        [
            [display_scale * cos_r, -display_scale * sin_r, tx],
            [display_scale * sin_r, display_scale * cos_r, ty],
        ],
        dtype=np.float64)
    out = cv2.warpAffine(
        keyframe_rgba,
        forward,
        (render_width, render_height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0))
    out = np.ascontiguousarray(out, dtype=np.uint8)
    if factor > 1.001:
        out = resize_rgba(
            out,
            max(1, int(canvas_width)),
            max(1, int(canvas_height)))
    return _sanitize_rgba(out)


class KeyframeRenderCache:
    """SSAA keyframe RGBA cache keyed by wx.Image id + antialias factor."""

    def __init__(self) -> None:
        self.rgba: Optional[np.ndarray] = None
        self.bitmap: Any = None
        self.image_id: Optional[int] = None
        self.antialias_factor: float = DEFAULT_ANTIALIAS_STRENGTH
        self.size: Tuple[int, int] = (1, 1)

    def clear(self) -> None:
        self.rgba = None
        self.bitmap = None
        self.image_id = None
        self.antialias_factor = DEFAULT_ANTIALIAS_STRENGTH
        self.size = (1, 1)

    def invalidate_image(self) -> None:
        self.image_id = None

    def is_valid(self, wx_image: Any, antialias_factor: float) -> bool:
        factor = normalize_antialias_strength(antialias_factor)
        bitmap_ok = self.bitmap is not None
        if bitmap_ok and hasattr(self.bitmap, "IsOk"):
            bitmap_ok = self.bitmap.IsOk()
        return (
            self.rgba is not None
            and bitmap_ok
            and self.image_id == id(wx_image)
            and abs(self.antialias_factor - factor) < 1e-4)

    def update(
            self,
            wx_image: Any,
            antialias_factor: float,
            *,
            wx_to_rgba: Callable[[Any], np.ndarray],
            create_bitmap: Callable[[int, int, np.ndarray], Any]) -> None:
        factor = normalize_antialias_strength(antialias_factor)
        wx_width = max(1, int(wx_image.GetWidth()))
        wx_height = max(1, int(wx_image.GetHeight()))
        source_rgba = wx_to_rgba(wx_image)
        keyframe_rgba, keyframe_width, keyframe_height = upscale_keyframe_for_ssaa(
            source_rgba, wx_width, wx_height, factor)
        self.rgba = keyframe_rgba
        self.bitmap = create_bitmap(keyframe_width, keyframe_height, keyframe_rgba)
        self.size = (keyframe_width, keyframe_height)
        self.image_id = id(wx_image)
        self.antialias_factor = factor
