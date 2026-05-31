"""Character silhouette edge post-processing for output compositing."""
from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy

CHARACTER_EDGE_FLICKER = "flicker"
CHARACTER_EDGE_OUTLINE = "outline"
CHARACTER_EDGE_NONE = "none"

CHARACTER_EDGE_MODE_VALUES = (
    CHARACTER_EDGE_FLICKER,
    CHARACTER_EDGE_OUTLINE,
    CHARACTER_EDGE_NONE,
)
CHARACTER_EDGE_MODE_LABELS = (
    "角色边缘闪烁 / Edge flicker fix",
    "角色边缘描边 / Edge outline",
    "角色边缘无效果 / No edge effect",
)

CHARACTER_EDGE_WIDTH_MIN = 0.001
CHARACTER_EDGE_WIDTH_MAX = 24.0
CHARACTER_EDGE_WIDTH_DEFAULT = 2.0
CHARACTER_EDGE_WIDTH_INCREMENT = 0.001
CHARACTER_EDGE_WIDTH_DECIMALS = 3


def normalize_character_edge_mode(value: Optional[str]) -> str:
    if value in CHARACTER_EDGE_MODE_VALUES:
        return value
    return CHARACTER_EDGE_FLICKER


def clamp_character_edge_width(value: float) -> float:
    clamped = max(
        CHARACTER_EDGE_WIDTH_MIN,
        min(CHARACTER_EDGE_WIDTH_MAX, float(value)))
    return round(clamped, CHARACTER_EDGE_WIDTH_DECIMALS)


def _dilate_alpha(alpha: numpy.ndarray, radius: int) -> numpy.ndarray:
    radius = max(0, int(radius))
    if radius <= 0:
        return alpha.copy()
    result = alpha.astype(numpy.uint8, copy=True)
    for _ in range(radius):
        padded = numpy.pad(result, 1, mode="constant", constant_values=0)
        result = numpy.maximum.reduce([
            padded[:-2, 1:-1],
            padded[2:, 1:-1],
            padded[1:-1, :-2],
            padded[1:-1, 2:],
            padded[1:-1, 1:-1],
        ])
    return result


def _dilate_alpha_fractional(alpha: numpy.ndarray, radius: float) -> numpy.ndarray:
    """Morphological dilation with fractional radius (linear blend between steps)."""
    radius = max(0.0, float(radius))
    if radius <= 0.0:
        return alpha.astype(numpy.float32, copy=True)
    inner = int(math.floor(radius))
    outer = int(math.ceil(radius))
    if outer <= 0:
        return alpha.astype(numpy.float32, copy=True)
    inner_dilated = _dilate_alpha(alpha, inner).astype(numpy.float32)
    if outer == inner:
        return inner_dilated
    outer_dilated = _dilate_alpha(alpha, outer).astype(numpy.float32)
    blend = radius - inner
    return numpy.clip(
        inner_dilated * (1.0 - blend) + outer_dilated * blend,
        0.0,
        255.0)


def _composite_rgba_under(
        background: numpy.ndarray,
        foreground: numpy.ndarray) -> numpy.ndarray:
    bg = background.astype(numpy.float32)
    fg = foreground.astype(numpy.float32)
    fg_a = fg[:, :, 3:4] / 255.0
    bg_a = bg[:, :, 3:4] / 255.0
    out_a = fg_a + bg_a * (1.0 - fg_a)
    safe_a = numpy.maximum(out_a, 1e-6)
    out_rgb = (fg[:, :, 0:3] * fg_a + bg[:, :, 0:3] * bg_a * (1.0 - fg_a)) / safe_a
    result = background.copy()
    result[:, :, 0:3] = numpy.clip(out_rgb, 0.0, 255.0).astype(numpy.uint8)
    result[:, :, 3] = numpy.clip(out_a[:, :, 0] * 255.0, 0.0, 255.0).astype(numpy.uint8)
    return result


def composite_rgba_arrays(
        background_rgba: numpy.ndarray,
        foreground_rgba: numpy.ndarray) -> numpy.ndarray:
    """Source-over composite of two RGBA arrays (same shape)."""
    return _composite_rgba_under(background_rgba, foreground_rgba)


def stabilize_character_edge_fringe(
        rgba: numpy.ndarray,
        background_rgb: Tuple[int, int, int],
        *,
        fringe_width: float = 2.0) -> numpy.ndarray:
    """Bake semi-transparent fringe against the output background to reduce flicker."""
    rgba = numpy.ascontiguousarray(rgba, dtype=numpy.uint8).copy()
    transparent = rgba[:, :, 3] == 0
    rgba[transparent, 0:3] = 0

    harden = max(CHARACTER_EDGE_WIDTH_MIN, min(32.0, float(fringe_width)))
    alpha = rgba[:, :, 3].astype(numpy.float32)
    semi = (alpha > 0.0) & (alpha < 255.0)
    if numpy.any(semi):
        bg_r, bg_g, bg_b = (int(background_rgb[0]), int(background_rgb[1]), int(background_rgb[2]))
        a = alpha[semi] / 255.0
        rgb = rgba[semi, 0:3].astype(numpy.float32)
        rgba[semi, 0] = numpy.clip(rgb[:, 0] * a + bg_r * (1.0 - a), 0.0, 255.0)
        rgba[semi, 1] = numpy.clip(rgb[:, 1] * a + bg_g * (1.0 - a), 0.0, 255.0)
        rgba[semi, 2] = numpy.clip(rgb[:, 2] * a + bg_b * (1.0 - a), 0.0, 255.0)
        rgba[semi, 3] = 255

    rgba[:, :, 3][rgba[:, :, 3] < harden] = 0
    rgba[:, :, 3][rgba[:, :, 3] > 255 - harden] = 255
    rgba[rgba[:, :, 3] == 0, 0:3] = 0
    return rgba


def apply_character_edge_outline(
        rgba: numpy.ndarray,
        outline_rgb: Tuple[int, int, int],
        width: float) -> numpy.ndarray:
    rgba = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
    alpha = rgba[:, :, 3]
    if not numpy.any(alpha > 0):
        return rgba.copy()
    radius = max(CHARACTER_EDGE_WIDTH_MIN, float(width))
    dilated = _dilate_alpha_fractional(alpha, radius)
    outline_layer = numpy.zeros_like(rgba)
    outline_mask = dilated > 0.0
    outline_layer[outline_mask, 0] = int(outline_rgb[0])
    outline_layer[outline_mask, 1] = int(outline_rgb[1])
    outline_layer[outline_mask, 2] = int(outline_rgb[2])
    outline_layer[outline_mask, 3] = 255
    return _composite_rgba_under(outline_layer, rgba)


def apply_character_edge_postprocess(
        rgba: numpy.ndarray,
        mode: str,
        *,
        width: float = CHARACTER_EDGE_WIDTH_DEFAULT,
        outline_rgb: Tuple[int, int, int] = (0, 0, 0),
        background_rgb: Tuple[int, int, int] = (0, 0, 0)) -> numpy.ndarray:
    normalized = normalize_character_edge_mode(mode)
    if normalized == CHARACTER_EDGE_NONE:
        return numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
    if normalized == CHARACTER_EDGE_OUTLINE:
        return apply_character_edge_outline(rgba, outline_rgb, width)
    return stabilize_character_edge_fringe(
        rgba, background_rgb, fringe_width=width)
