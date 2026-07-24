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
from typing import Any, Callable, Optional

import cv2
import numpy

from character_edge_postprocess import composite_rgba_arrays
from rgba_capture_compose import scale_rgba
from present_compose_cache import LayerWarpResultCache
from layer_runtime import (
    MOTION_MODE_SIMPLE_SWING,
    BasicLayersState,
    BasicLayerSlot,
    BindingContext,
    LayerBindingSmoother,
    clamp_swing_pivot_u,
    clamp_swing_pivot_v,
    compute_swing_angle_deg,
    layer_at_stack_position,
    orbit_frame_plan,
    resolve_layer_rects,
    resolve_stack_layer_draw,
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
    # PIL inverse round-trip is unnecessary. Warp into the rotated AABB only,
    # then paste onto the full canvas — small sprites must not pay a 768² warp.
    source = numpy.ascontiguousarray(scaled, dtype=numpy.uint8)
    src_h, src_w = int(source.shape[0]), int(source.shape[1])
    canvas_width = max(1, int(canvas_width))
    canvas_height = max(1, int(canvas_height))
    m = numpy.ascontiguousarray(forward_2x3, dtype=numpy.float64)
    corners = numpy.array(
        [[0.0, 0.0, 1.0],
         [float(src_w), 0.0, 1.0],
         [float(src_w), float(src_h), 1.0],
         [0.0, float(src_h), 1.0]],
        dtype=numpy.float64)
    mapped = corners @ m.T
    pad = 2.0
    x0 = int(math.floor(float(mapped[:, 0].min()) - pad))
    y0 = int(math.floor(float(mapped[:, 1].min()) - pad))
    x1 = int(math.ceil(float(mapped[:, 0].max()) + pad))
    y1 = int(math.ceil(float(mapped[:, 1].max()) + pad))
    x0 = max(0, min(canvas_width, x0))
    y0 = max(0, min(canvas_height, y0))
    x1 = max(0, min(canvas_width, x1))
    y1 = max(0, min(canvas_height, y1))
    out = numpy.zeros((canvas_height, canvas_width, 4), dtype=numpy.uint8)
    if x1 <= x0 or y1 <= y0:
        return out
    shifted = m.copy()
    shifted[0, 2] -= float(x0)
    shifted[1, 2] -= float(y0)
    warped = cv2.warpAffine(
        source,
        shifted,
        (x1 - x0, y1 - y0),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0))
    out[y0:y1, x0:x1] = numpy.ascontiguousarray(warped, dtype=numpy.uint8)
    return out


def _render_layer_contribution(
        layer_rgba: numpy.ndarray,
        layer: BasicLayerSlot,
        rect,
        state: BasicLayersState,
        binding_context: Optional[BindingContext],
        motion_time_s: Optional[float],
        canvas_width: int,
        canvas_height: int,
        *,
        warp_cache: Optional[LayerWarpResultCache] = None,
        wobble_token: Any = None) -> Optional[numpy.ndarray]:
    draw_w = max(1, int(round(rect.draw_width)))
    draw_h = max(1, int(round(rect.draw_height)))

    container_rotation_deg = float(layer.transform.rotation_deg)
    container_rotation_deg = resolved_layer_rotation_deg(
        layer, state, rect, binding_context)

    swing_deg = 0.0
    if (
            motion_time_s is not None
            and layer.asset_path
            and layer.motion_mode == MOTION_MODE_SIMPLE_SWING):
        swing_deg = compute_swing_angle_deg(layer, motion_time_s)

    cache_key = None
    if warp_cache is not None:
        cache_key = LayerWarpResultCache.make_key(
            slot_id=int(layer.slot_id),
            asset_path=layer.asset_path,
            draw_x=rect.draw_x,
            draw_y=rect.draw_y,
            draw_width=rect.draw_width,
            draw_height=rect.draw_height,
            rotation_deg=container_rotation_deg,
            swing_deg=swing_deg,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            wobble_token=wobble_token)
        hit = warp_cache.get(cache_key)
        if hit is not None:
            return hit

    scaled = scale_rgba(layer_rgba, draw_w, draw_h)
    needs_transform = (
        abs(container_rotation_deg) > _TRANSFORM_EPS
        or abs(swing_deg) > _TRANSFORM_EPS)
    if not needs_transform:
        contribution = _paste_rgba_onto_canvas(
            scaled, rect.draw_x, rect.draw_y, canvas_width, canvas_height)
    else:
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
        contribution = _warp_rgba_onto_canvas(
            scaled, forward_2x3, canvas_width, canvas_height)
    if warp_cache is not None and cache_key is not None and contribution is not None:
        warp_cache.put(cache_key, contribution)
    return contribution


def compose_full_stack_rgba(
        state: BasicLayersState,
        rgba_loader: RgbaLoader,
        canvas_width: int,
        canvas_height: int,
        character_rgba: numpy.ndarray,
        binding_context: Optional[BindingContext] = None,
        *,
        binding_smoother: Optional[LayerBindingSmoother] = None,
        layer_rgba_filter: Optional[
            Callable[[BasicLayerSlot, numpy.ndarray], numpy.ndarray]] = None,
        warp_cache: Optional[LayerWarpResultCache] = None,
        layer_wobble_token_fn: Optional[Callable[[BasicLayerSlot], Any]] = None,
        base_rgba: Optional[numpy.ndarray] = None,
) -> numpy.ndarray:
    """Composite the full layer stack (character in the middle) to a straight
    RGBA canvas, mirroring LayerCompositor.draw_post_process_stack.

    rgba_loader(layer) returns HxWx4 uint8 straight-alpha RGBA, or None.
    character_rgba is the already-enhanced character frame (any size; scaled to
    canvas if needed).
    layer_rgba_filter: optional per-layer RGBA mutate before place/swing (f-068).
    warp_cache: optional keyed cache of warped layer contributions.
    layer_wobble_token_fn: optional per-layer wobble signature for cache keys.
    base_rgba: optional opaque background plate to seed the canvas (avoids a
    second full-footprint bg underlay after the stack is built).
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
        if rgba is not None and layer_rgba_filter is not None:
            rgba = layer_rgba_filter(layer, rgba)
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

    if base_rgba is not None:
        canvas = numpy.ascontiguousarray(base_rgba, dtype=numpy.uint8).copy()
        if canvas.shape[0] != canvas_h or canvas.shape[1] != canvas_w:
            canvas = _fit_canvas(canvas, canvas_w, canvas_h)
    else:
        canvas = numpy.zeros((canvas_h, canvas_w, 4), dtype=numpy.uint8)
    motion_time_s = (
        binding_context.motion_time_s if binding_context is not None else None)
    orbit_plan, hidden_slots = orbit_frame_plan(state, binding_context)

    character_pos = state.character_stack_position
    for pos in range(state.total_stack_positions):
        if pos == character_pos:
            canvas = composite_rgba_arrays(
                canvas, _fit_canvas(character_rgba, canvas_w, canvas_h))
            continue
        layer = layer_at_stack_position(state, pos)
        if layer is None or not layer.enabled:
            continue
        draw_pair = resolve_stack_layer_draw(
            state, layer, resolved, orbit_plan, hidden_slots)
        if draw_pair is None:
            continue
        draw_layer, rect = draw_pair
        if not draw_layer.visible:
            continue
        view = _resolver_loader(draw_layer)
        if view is None:
            continue
        wobble_token = None
        if layer_wobble_token_fn is not None:
            try:
                wobble_token = layer_wobble_token_fn(draw_layer)
            except Exception:
                wobble_token = None
        contribution = _render_layer_contribution(
            view.rgba,
            draw_layer,
            rect,
            state,
            binding_context,
            motion_time_s,
            canvas_w,
            canvas_h,
            warp_cache=warp_cache,
            wobble_token=wobble_token)
        if contribution is not None:
            canvas = composite_rgba_arrays(canvas, contribution)

    return numpy.ascontiguousarray(canvas, dtype=numpy.uint8)
