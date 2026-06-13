"""Shared layer edit gestures for source preview and output panel."""
from __future__ import annotations

import math
from enum import Enum
from typing import Callable, Optional

from layer_runtime import (
    LAYER_COORD_SIZE,
    BasicLayerSlot,
    BasicLayersState,
    BindingContext,
    LayerCompositor,
    LayerGeometryResolver,
    ResolvedLayerRect,
    resolve_layer_rects,
    resolved_layer_rotation_deg,
)

SELECTION_HANDLE_SIZE = 8


class LayerEditMode(str, Enum):
    NONE = "none"
    MOVE = "move"
    SCALE = "scale"


def panel_to_layer_delta(dx: int, dy: int, panel_width: int, panel_height: int) -> tuple[float, float]:
    return (
        dx * LAYER_COORD_SIZE / max(1, panel_width),
        dy * LAYER_COORD_SIZE / max(1, panel_height),
    )


def layer_to_panel_delta(dx: float, dy: float, panel_width: int, panel_height: int) -> tuple[float, float]:
    return (
        dx * max(1, panel_width) / LAYER_COORD_SIZE,
        dy * max(1, panel_height) / LAYER_COORD_SIZE,
    )


def _point_in_rotated_rect(
        x: float,
        y: float,
        rect: ResolvedLayerRect,
        rotation_deg: float) -> bool:
    cx = rect.draw_x + rect.draw_width / 2.0
    cy = rect.draw_y + rect.draw_height / 2.0
    if abs(rotation_deg) <= 1e-4:
        return (
            rect.draw_x <= x <= rect.draw_x + rect.draw_width
            and rect.draw_y <= y <= rect.draw_y + rect.draw_height)
    rad = math.radians(-rotation_deg)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    local_x = x - cx
    local_y = y - cy
    unrot_x = local_x * cos_r - local_y * sin_r
    unrot_y = local_x * sin_r + local_y * cos_r
    half_w = rect.draw_width / 2.0
    half_h = rect.draw_height / 2.0
    return -half_w <= unrot_x <= half_w and -half_h <= unrot_y <= half_h


def _handle_rect(
        rect: ResolvedLayerRect,
        rotation_deg: float = 0.0) -> tuple[float, float, float, float]:
    handle = SELECTION_HANDLE_SIZE
    cx = rect.draw_x + rect.draw_width / 2.0
    cy = rect.draw_y + rect.draw_height / 2.0
    local_x = rect.draw_width / 2.0 - handle
    local_y = rect.draw_height / 2.0 - handle
    if abs(rotation_deg) <= 1e-4:
        return cx + local_x, cy + local_y, float(handle), float(handle)
    rad = math.radians(rotation_deg)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    x = cx + local_x * cos_r - local_y * sin_r
    y = cy + local_x * sin_r + local_y * cos_r
    return x, y, float(handle), float(handle)


def hit_test_layer_edit(
        state: BasicLayersState,
        asset_loader: Callable[[BasicLayerSlot], Optional],
        x: int,
        y: int,
        canvas_width: int,
        canvas_height: int,
        binding_context: Optional[BindingContext] = None,
        *,
        selected_slot_id: Optional[int] = None) -> tuple[Optional[int], LayerEditMode]:
    resolved = resolve_layer_rects(
        state, asset_loader, canvas_width, canvas_height, binding_context)

    if selected_slot_id is None or selected_slot_id not in resolved:
        return None, LayerEditMode.NONE

    rect = resolved[selected_slot_id]
    layer = state.get_slot(selected_slot_id)
    rotation_deg = resolved_layer_rotation_deg(
        layer, state, rect, binding_context)
    if not _point_in_rotated_rect(float(x), float(y), rect, rotation_deg):
        return None, LayerEditMode.NONE
    hx, hy, hw, hh = _handle_rect(rect, rotation_deg)
    if hx <= x <= hx + hw and hy <= y <= hy + hh:
        return selected_slot_id, LayerEditMode.SCALE
    return selected_slot_id, LayerEditMode.MOVE


def hit_test_resolved_rect(
        slot_id: int,
        rect: ResolvedLayerRect,
        rotation_deg: float,
        x: int,
        y: int) -> tuple[Optional[int], LayerEditMode]:
    """Hit-test a click against an already-resolved layer rect (the exact box
    that was last drawn as selection chrome).

    Used by the layered output window so the draggable region matches the
    on-screen highlight box pixel-for-pixel. Re-resolving via
    ``resolve_layer_rects`` would advance the stateful binding smoother and use
    a fresh ``motion_time_s``, drifting the hit rect away from the drawn box for
    bound/smoothed layers (so clicks would miss and drag the window instead)."""
    if not _point_in_rotated_rect(float(x), float(y), rect, rotation_deg):
        return None, LayerEditMode.NONE
    hx, hy, hw, hh = _handle_rect(rect, rotation_deg)
    if hx <= x <= hx + hw and hy <= y <= hy + hh:
        return slot_id, LayerEditMode.SCALE
    return slot_id, LayerEditMode.MOVE


def apply_move_delta(layer: BasicLayerSlot, dx: float, dy: float) -> None:
    layer.transform.offset_x += dx
    layer.transform.offset_y += dy


def apply_scale_from_drag(
        layer: BasicLayerSlot,
        pointer_x: float,
        pointer_y: float,
        rect: ResolvedLayerRect) -> None:
    cx = rect.draw_x + rect.draw_width / 2.0
    cy = rect.draw_y + rect.draw_height / 2.0
    dx = max(1.0, pointer_x - cx)
    dy = max(1.0, pointer_y - cy)
    half_extent = max(dx, dy)
    base_extent = max(
        1.0,
        max(rect.draw_width, rect.draw_height) / max(0.05, layer.transform.scale) / 2.0)
    layer.transform.scale = max(0.05, min(3.0, half_extent / base_extent * layer.transform.scale))


def nudge_layer(layer: BasicLayerSlot, dx_layer: float, dy_layer: float) -> None:
    layer.transform.offset_x += dx_layer
    layer.transform.offset_y += dy_layer


def hit_test_layer_slot(
        state: BasicLayersState,
        asset_loader: Callable[[BasicLayerSlot], Optional],
        x: int,
        y: int,
        canvas_width: int,
        canvas_height: int,
        binding_context: Optional[BindingContext] = None) -> Optional[int]:
    return LayerCompositor.hit_test_layer_slot(
        state,
        asset_loader,
        x,
        y,
        canvas_width,
        canvas_height,
        binding_context)
