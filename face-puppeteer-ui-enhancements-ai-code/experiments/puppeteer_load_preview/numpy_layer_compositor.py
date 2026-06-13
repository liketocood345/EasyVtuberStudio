"""Pure-numpy full-stack layer compositor (wx-free render path).

Mirrors LayerCompositor.draw_post_process_stack / draw_layer_on_dc geometry
(scale, container rotation, simple-swing about pivot, z-order with character in
the middle of the stack) but composites RGBA arrays instead of drawing onto a
wx.DC. Reuses the existing geometry resolver (resolve_layer_rects) so preview
and output stay on one geometry source of truth.

Layer pixels come from a caller-supplied rgba_loader returning HxWx4 uint8
straight-alpha RGBA (so this module has no dependency on wx or the asset cache).
"""
from __future__ import annotations

import math
from typing import Callable, Optional

import cv2
import numpy

from character_edge_postprocess import composite_rgba_arrays
from rgba_capture_compose import scale_rgba
from layer_runtime import (
    CHARACTER_STACK_POS,
    DRAW_STACK_BOTTOM_TO_TOP,
    MOTION_MODE_SIMPLE_SWING,
    BasicLayersState,
    BasicLayerSlot,
    BindingContext,
    LayerBindingSmoother,
    clamp_swing_pivot_u,
    clamp_swing_pivot_v,
    compute_swing_angle_deg,
    layer_at_stack_position,
    resolve_layer_rects,
    resolved_layer_rotation_deg,
)

RgbaLoader = Callable[[BasicLayerSlot], Optional[numpy.ndarray]]

_TRANSFORM_EPS = 1e-4


class _RgbaSizeView:
    """Adapts a numpy RGBA buffer to the GetWidth/GetHeight interface that the
    geometry resolver expects from a wx.Image."""

    __slots__ = ("rgba", "_width", "_height")

    def __init__(self, rgba: numpy.ndarray) -> None:
        self.rgba = rgba
        self._height = int(rgba.shape[0])
        self._width = int(rgba.shape[1])

    def GetWidth(self) -> int:
        return self._width

    def GetHeight(self) -> int:
        return self._height


def _mat3_translate(tx: float, ty: float) -> numpy.ndarray:
    return numpy.array([[1.0, 0.0, tx], [0.0, 1.0, ty], [0.0, 0.0, 1.0]], dtype=numpy.float64)


def _mat3_rotate(deg: float) -> numpy.ndarray:
    rad = math.radians(deg)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    return numpy.array(
        [[cos_r, -sin_r, 0.0], [sin_r, cos_r, 0.0], [0.0, 0.0, 1.0]],
        dtype=numpy.float64)


def _fit_canvas(rgba: numpy.ndarray, canvas_width: int, canvas_height: int) -> numpy.ndarray:
    rgba = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
    if rgba.shape[0] == canvas_height and rgba.shape[1] == canvas_width:
        return rgba
    return scale_rgba(rgba, canvas_width, canvas_height)


def _paste_rgba_onto_canvas(
        scaled: numpy.ndarray,
        draw_x: float,
        draw_y: float,
        canvas_width: int,
        canvas_height: int) -> numpy.ndarray:
    out = numpy.zeros((canvas_height, canvas_width, 4), dtype=numpy.uint8)
    src_h, src_w = scaled.shape[0], scaled.shape[1]
    dx0 = int(round(draw_x))
    dy0 = int(round(draw_y))
    dst_x0 = max(0, dx0)
    dst_y0 = max(0, dy0)
    dst_x1 = min(canvas_width, dx0 + src_w)
    dst_y1 = min(canvas_height, dy0 + src_h)
    if dst_x1 <= dst_x0 or dst_y1 <= dst_y0:
        return out
    src_x0 = dst_x0 - dx0
    src_y0 = dst_y0 - dy0
    out[dst_y0:dst_y1, dst_x0:dst_x1] = scaled[
        src_y0:src_y0 + (dst_y1 - dst_y0),
        src_x0:src_x0 + (dst_x1 - dst_x0)]
    return out


def _warp_rgba_onto_canvas(
        scaled: numpy.ndarray,
        forward_2x3: numpy.ndarray,
        canvas_width: int,
        canvas_height: int) -> numpy.ndarray:
    # cv2.warpAffine takes the forward (src -> dst) matrix directly, so the
    # PIL inverse round-trip is unnecessary. cv2 is far faster than PIL BICUBIC,
    # which matters once several layers each warp per frame.
    source = numpy.ascontiguousarray(scaled, dtype=numpy.uint8)
    warped = cv2.warpAffine(
        source,
        numpy.ascontiguousarray(forward_2x3, dtype=numpy.float64),
        (max(1, int(canvas_width)), max(1, int(canvas_height))),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0))
    return numpy.ascontiguousarray(warped, dtype=numpy.uint8)


def _render_layer_contribution(
        layer_rgba: numpy.ndarray,
        layer: BasicLayerSlot,
        rect,
        state: BasicLayersState,
        binding_context: Optional[BindingContext],
        motion_time_s: Optional[float],
        canvas_width: int,
        canvas_height: int) -> Optional[numpy.ndarray]:
    draw_w = max(1, int(round(rect.draw_width)))
    draw_h = max(1, int(round(rect.draw_height)))
    scaled = scale_rgba(layer_rgba, draw_w, draw_h)

    container_rotation_deg = float(layer.transform.rotation_deg)
    container_rotation_deg = resolved_layer_rotation_deg(
        layer, state, rect, binding_context)

    swing_deg = 0.0
    if (
            motion_time_s is not None
            and layer.asset_path
            and layer.motion_mode == MOTION_MODE_SIMPLE_SWING):
        swing_deg = compute_swing_angle_deg(layer, motion_time_s)

    needs_transform = (
        abs(container_rotation_deg) > _TRANSFORM_EPS
        or abs(swing_deg) > _TRANSFORM_EPS)
    if not needs_transform:
        return _paste_rgba_onto_canvas(
            scaled, rect.draw_x, rect.draw_y, canvas_width, canvas_height)

    cx = rect.draw_x + rect.draw_width / 2.0
    cy = rect.draw_y + rect.draw_height / 2.0
    matrix = _mat3_translate(cx, cy) @ _mat3_rotate(container_rotation_deg)
    if abs(swing_deg) > _TRANSFORM_EPS:
        pivot_off_x = (clamp_swing_pivot_u(layer.swing_pivot_u) - 0.5) * draw_w
        pivot_off_y = (clamp_swing_pivot_v(layer.swing_pivot_v) - 0.5) * draw_h
        matrix = (
            matrix
            @ _mat3_translate(pivot_off_x, pivot_off_y)
            @ _mat3_rotate(swing_deg)
            @ _mat3_translate(-pivot_off_x, -pivot_off_y))
    matrix = matrix @ _mat3_translate(-draw_w / 2.0, -draw_h / 2.0)
    forward_2x3 = numpy.ascontiguousarray(matrix[:2, :])
    return _warp_rgba_onto_canvas(scaled, forward_2x3, canvas_width, canvas_height)


def compose_full_stack_rgba(
        state: BasicLayersState,
        rgba_loader: RgbaLoader,
        canvas_width: int,
        canvas_height: int,
        character_rgba: numpy.ndarray,
        binding_context: Optional[BindingContext] = None,
        *,
        binding_smoother: Optional[LayerBindingSmoother] = None) -> numpy.ndarray:
    """Composite the full layer stack (character in the middle) to a straight
    RGBA canvas, mirroring LayerCompositor.draw_post_process_stack.

    rgba_loader(layer) returns HxWx4 uint8 straight-alpha RGBA, or None.
    character_rgba is the already-enhanced character frame (any size; scaled to
    canvas if needed).
    """
    canvas_w = max(1, int(canvas_width))
    canvas_h = max(1, int(canvas_height))

    _MISSING = object()
    views: dict[int, object] = {}

    def _resolver_loader(layer: BasicLayerSlot):
        cached = views.get(layer.slot_id, _MISSING)
        if cached is not _MISSING:
            return cached
        rgba = rgba_loader(layer)
        view = None
        if rgba is not None:
            view = _RgbaSizeView(numpy.ascontiguousarray(rgba, dtype=numpy.uint8))
        views[layer.slot_id] = view
        return view

    resolved = resolve_layer_rects(
        state,
        _resolver_loader,
        canvas_w,
        canvas_h,
        binding_context,
        binding_smoother=binding_smoother)

    canvas = numpy.zeros((canvas_h, canvas_w, 4), dtype=numpy.uint8)
    motion_time_s = (
        binding_context.motion_time_s if binding_context is not None else None)

    for pos in DRAW_STACK_BOTTOM_TO_TOP:
        if pos == CHARACTER_STACK_POS:
            canvas = composite_rgba_arrays(
                canvas, _fit_canvas(character_rgba, canvas_w, canvas_h))
            continue
        layer = layer_at_stack_position(state, pos)
        if (
                layer is None
                or not layer.enabled
                or not layer.visible
                or not layer.asset_path):
            continue
        rect = resolved.get(layer.slot_id)
        view = _resolver_loader(layer)
        if rect is None or view is None:
            continue
        contribution = _render_layer_contribution(
            view.rgba,
            layer,
            rect,
            state,
            binding_context,
            motion_time_s,
            canvas_w,
            canvas_h)
        if contribution is not None:
            canvas = composite_rgba_arrays(canvas, contribution)

    return numpy.ascontiguousarray(canvas, dtype=numpy.uint8)
