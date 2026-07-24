"""Present-path caches: per-layer warp results, character warp, affine reproject.

Pure numpy/cv2 helpers used by the live present hot path so settled frames can
skip full stack recomposition and affine-only changes can reproject the last
finished frame instead of re-warping every layer.
"""
from __future__ import annotations

import math
from typing import Any, Optional

import cv2
import numpy


def quantize_affine(
        offset_x: float,
        offset_y: float,
        scale: float,
        rotation_deg: float) -> tuple:
    return (
        round(float(offset_x), 2),
        round(float(offset_y), 2),
        round(float(scale), 4),
        round(float(rotation_deg), 2),
    )


def _affine_feet_matrix(
        canvas_width: int,
        canvas_height: int,
        offset_x: float,
        offset_y: float,
        scale: float,
        rotation_deg: float) -> numpy.ndarray:
    """2x3 forward map treating the present canvas as a full-frame 'sprite'
    whose feet sit at bottom-center + display offset (matches character compose)."""
    display_scale = max(0.1, float(scale))
    rotation_rad = math.radians(float(rotation_deg))
    cos_r = math.cos(rotation_rad)
    sin_r = math.sin(rotation_rad)
    keyframe_width = float(canvas_width)
    keyframe_height = float(canvas_height)
    anchor_x = canvas_width / 2.0 + float(offset_x)
    anchor_y = canvas_height + float(offset_y)
    tx = (
        anchor_x
        - display_scale * cos_r * keyframe_width / 2.0
        + display_scale * sin_r * keyframe_height)
    ty = (
        anchor_y
        - display_scale * sin_r * keyframe_width / 2.0
        - display_scale * cos_r * keyframe_height)
    return numpy.array(
        [
            [display_scale * cos_r, -display_scale * sin_r, tx],
            [display_scale * sin_r, display_scale * cos_r, ty],
        ],
        dtype=numpy.float64)


def _invert_affine_2x3(forward: numpy.ndarray) -> numpy.ndarray:
    a, b, tx = forward[0]
    c, d, ty = forward[1]
    det = (a * d) - (b * c)
    if abs(det) < 1e-8:
        raise ValueError("singular affine")
    inv_a = d / det
    inv_b = -b / det
    inv_c = -c / det
    inv_d = a / det
    inv_tx = -((inv_a * tx) + (inv_b * ty))
    inv_ty = -((inv_c * tx) + (inv_d * ty))
    return numpy.array(
        [[inv_a, inv_b, inv_tx], [inv_c, inv_d, inv_ty]],
        dtype=numpy.float64)


def _compose_affine_2x3(left: numpy.ndarray, right: numpy.ndarray) -> numpy.ndarray:
    """Return left @ right for 2x3 affines (as 3x3 homogeneous)."""
    l = numpy.vstack([left, [0.0, 0.0, 1.0]])
    r = numpy.vstack([right, [0.0, 0.0, 1.0]])
    out = l @ r
    return numpy.ascontiguousarray(out[:2, :], dtype=numpy.float64)


def reproject_rgba_by_display_affine(
        rgba: numpy.ndarray,
        canvas_width: int,
        canvas_height: int,
        *,
        old_affine: tuple,
        new_affine: tuple) -> numpy.ndarray:
    """Warp a finished present frame from old display affine to new.

    Approximates a full stack recompose when only display_offset/scale/rotation
    changed and layers follow the character rigidly (force_full_follow / shared
    display transform).
    """
    rgba = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
    canvas_width = max(1, int(canvas_width))
    canvas_height = max(1, int(canvas_height))
    if rgba.shape[0] != canvas_height or rgba.shape[1] != canvas_width:
        rgba = cv2.resize(
            rgba, (canvas_width, canvas_height), interpolation=cv2.INTER_LINEAR)
        rgba = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
    old_ox, old_oy, old_scale, old_rot = old_affine
    new_ox, new_oy, new_scale, new_rot = new_affine
    if (
            abs(old_ox - new_ox) < 1e-4
            and abs(old_oy - new_oy) < 1e-4
            and abs(old_scale - new_scale) < 1e-6
            and abs(old_rot - new_rot) < 1e-4):
        return rgba
    t_old = _affine_feet_matrix(
        canvas_width, canvas_height, old_ox, old_oy, old_scale, old_rot)
    t_new = _affine_feet_matrix(
        canvas_width, canvas_height, new_ox, new_oy, new_scale, new_rot)
    # Map old-canvas pixels into new-canvas: T_new @ inv(T_old).
    forward = _compose_affine_2x3(t_new, _invert_affine_2x3(t_old))
    warped = cv2.warpAffine(
        rgba,
        forward,
        (canvas_width, canvas_height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0))
    return numpy.ascontiguousarray(warped, dtype=numpy.uint8)


class LayerWarpResultCache:
    """Keyed cache of per-layer warped RGBA contributions."""

    __slots__ = ("_entries", "_max_entries", "hits", "misses")

    def __init__(self, max_entries: int = 64) -> None:
        self._entries: dict[tuple, numpy.ndarray] = {}
        self._max_entries = max(8, int(max_entries))
        self.hits = 0
        self.misses = 0

    def clear(self) -> None:
        self._entries.clear()
        self.hits = 0
        self.misses = 0

    def get(self, key: tuple) -> Optional[numpy.ndarray]:
        value = self._entries.get(key)
        if value is None:
            self.misses += 1
            return None
        self.hits += 1
        return value

    def put(self, key: tuple, rgba: numpy.ndarray) -> None:
        if len(self._entries) >= self._max_entries and key not in self._entries:
            # Drop an arbitrary old entry (FIFO-ish via dict order on 3.7+).
            try:
                oldest = next(iter(self._entries))
                del self._entries[oldest]
            except StopIteration:
                pass
        self._entries[key] = rgba

    @staticmethod
    def make_key(
            *,
            slot_id: int,
            asset_path: Optional[str],
            draw_x: float,
            draw_y: float,
            draw_width: float,
            draw_height: float,
            rotation_deg: float,
            swing_deg: float,
            canvas_width: int,
            canvas_height: int,
            wobble_token: Any = None) -> tuple:
        return (
            int(slot_id),
            str(asset_path or ""),
            round(float(draw_x), 2),
            round(float(draw_y), 2),
            round(float(draw_width), 2),
            round(float(draw_height), 2),
            round(float(rotation_deg), 2),
            round(float(swing_deg), 2),
            int(canvas_width),
            int(canvas_height),
            wobble_token,
        )


class CharacterWarpCache:
    """Cache of character RGBA after wobble+warp onto a compose canvas."""

    __slots__ = ("key", "rgba")

    def __init__(self) -> None:
        self.key: Optional[tuple] = None
        self.rgba: Optional[numpy.ndarray] = None

    def clear(self) -> None:
        self.key = None
        self.rgba = None

    def get(self, key: tuple) -> Optional[numpy.ndarray]:
        if self.key == key and self.rgba is not None:
            return self.rgba
        return None

    def put(self, key: tuple, rgba: numpy.ndarray) -> None:
        self.key = key
        self.rgba = rgba
