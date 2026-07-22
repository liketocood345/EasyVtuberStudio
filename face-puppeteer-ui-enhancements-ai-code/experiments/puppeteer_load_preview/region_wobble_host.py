# ══ 设计手册嵌入 ══
# 权威：f-068 · 本模块为 MainFrame 挂接辅助（非热路径物理）
"""Helpers to wire region_wobble into MainFrame without bloating imports."""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

import numpy

from portable_paths import get_workspace_dir
from region_wobble import (
    IDLE_MODE_STILL_WOBBLE,
    RegionWobbleState,
    WobbleRegionPart,
    apply_wobble,
    character_mask_path,
    character_region_mask_path,
    layer_mask_path,
    layer_region_mask_path,
    load_mask_png,
    normalize_idle_mode,
    save_mask_png,
)
from layer_runtime import get_basic_layers_directory

if TYPE_CHECKING:
    pass


def _load_region_masks(state: RegionWobbleState, path_fn, height: int, width: int) -> None:
    count = max(1, len(state.regions))
    loaded_any = False
    for i in range(count):
        loaded = load_mask_png(path_fn(i), height, width)
        if loaded is None and i == 0:
            # Legacy single-file fallback already tried via path_fn(0).
            continue
        if loaded is not None:
            while len(state.regions) <= i:
                state.regions.append(WobbleRegionPart())
            state.regions[i].mask = loaded
            state.regions[i].mark_mask_dirty()
            loaded_any = True
    if not loaded_any:
        # Try legacy character/layer single mask into region 0.
        legacy = load_mask_png(path_fn(0), height, width)
        if legacy is not None:
            state.regions[0].mask = legacy
            state.regions[0].mark_mask_dirty()


def init_region_wobble_on_frame(frame) -> None:
    frame.character_region_wobble = RegionWobbleState()
    frame._layer_region_wobble: dict[int, RegionWobbleState] = {}
    frame._region_wobble_paint_mode = False
    frame._region_wobble_erase = False
    frame._region_wobble_brush_radius = 28.0
    frame._region_wobble_brush_strength = 0.55
    frame._region_wobble_target = "character"
    frame._region_wobble_last_debug = None
    data = getattr(frame, "persistent_ui_state", None) or {}
    frame.character_region_wobble.apply_persist_dict(data)
    try:
        ws = get_workspace_dir()
        kf_h = kf_w = 512
        src = getattr(frame, "wx_source_image", None)
        if src is not None and src.IsOk():
            kf_w, kf_h = int(src.GetWidth()), int(src.GetHeight())
        else:
            cache = getattr(getattr(frame, "output_enhancement", None), "keyframe_cache", None)
            rgba = getattr(cache, "rgba", None) if cache is not None else None
            if rgba is not None:
                kf_h, kf_w = int(rgba.shape[0]), int(rgba.shape[1])
        _load_region_masks(
            frame.character_region_wobble,
            lambda i: character_region_mask_path(ws, i),
            kf_h,
            kf_w)
    except Exception:
        pass


def layer_wobble_state(frame, slot_id: int) -> RegionWobbleState:
    store = frame._layer_region_wobble
    st = store.get(int(slot_id))
    if st is None:
        st = RegionWobbleState()
        store[int(slot_id)] = st
        layer = None
        try:
            layer = frame.basic_layers_state.get_slot(int(slot_id))
        except Exception:
            layer = None
        if layer is not None:
            st.enabled = bool(getattr(layer, "region_wobble_enabled", False))
            st.idle_mode = normalize_idle_mode(
                getattr(layer, "region_wobble_idle_mode", IDLE_MODE_STILL_WOBBLE))
            st.pose_hooks_islands = bool(
                getattr(layer, "region_wobble_pose_hooks_islands", True))
            st.island_phase_stagger = bool(
                getattr(layer, "region_wobble_island_phase_stagger", False))
            st.strength = float(getattr(layer, "region_wobble_strength", 0.35))
            st.speed = float(getattr(layer, "region_wobble_speed", 1.0))
            st.apply_persist_dict({
                "region_wobble_pins": getattr(layer, "region_wobble_pins", []),
                "region_wobble_axis": getattr(layer, "region_wobble_axis", None),
                "region_wobble_axes": getattr(layer, "region_wobble_axes", []),
                "region_wobble_region_count": getattr(
                    layer, "region_wobble_region_count", 1),
                "region_wobble_active_region": getattr(
                    layer, "region_wobble_active_region", 0),
                "region_wobble_active_island": getattr(
                    layer, "region_wobble_active_island", 0),
                "region_wobble_islands_by_region": getattr(
                    layer, "region_wobble_islands_by_region", None),
                "region_wobble_pose_hooks_islands": getattr(
                    layer, "region_wobble_pose_hooks_islands", True),
                "region_wobble_island_phase_stagger": getattr(
                    layer, "region_wobble_island_phase_stagger", False),
            })
            try:
                layers_dir = get_basic_layers_directory(str(frame.get_ui_state_file_path()))
                rgba_loader = getattr(frame.layer_asset_cache, "load_image_rgba", None)
                h = w = 512
                if rgba_loader is not None and layer.asset_path:
                    arr = rgba_loader(layer)
                    if arr is not None:
                        h, w = int(arr.shape[0]), int(arr.shape[1])
                sid = int(slot_id)
                _load_region_masks(
                    st,
                    lambda i: layer_region_mask_path(Path(layers_dir), sid, i),
                    h,
                    w)
            except Exception:
                pass
    return st


def sync_layer_slot_from_state(layer, state: RegionWobbleState) -> None:
    layer.region_wobble_enabled = bool(state.enabled)
    layer.region_wobble_idle_mode = normalize_idle_mode(state.idle_mode)
    layer.region_wobble_pose_hooks_islands = bool(state.pose_hooks_islands)
    layer.region_wobble_island_phase_stagger = bool(state.island_phase_stagger)
    isl = state.active_island_params()
    layer.region_wobble_strength = float(isl.strength)
    layer.region_wobble_speed = float(isl.speed)
    layer.region_wobble_pins = [[float(x), float(y)] for x, y in state.pins]
    layer.region_wobble_axes = [[float(v) for v in a] for a in state.axes]
    layer.region_wobble_axis = (
        [float(v) for v in state.axes[0]] if state.axes else None)
    layer.region_wobble_region_count = int(len(state.regions))
    layer.region_wobble_active_region = int(state.active_region)
    layer.region_wobble_active_island = int(state.active_island)
    islands_by_region = []
    for reg in state.regions:
        reg.ensure_island_bank()
        islands_by_region.append([p.to_dict() for p in reg.islands])
    layer.region_wobble_islands_by_region = islands_by_region


def head_pose_for_wobble(frame) -> tuple[float, float]:
    try:
        yaw, pitch, _neck = frame._collect_pose_binding_fields()
        return float(yaw), float(pitch)
    except Exception:
        return 0.0, 0.0


def apply_character_wobble(frame, keyframe_rgba: numpy.ndarray) -> numpy.ndarray:
    state = frame.character_region_wobble
    if (
            not state.debug_enabled
            and (not state.enabled or not state.has_active_mask())):
        return keyframe_rgba
    yaw, pitch = head_pose_for_wobble(frame)
    out = apply_wobble(
        keyframe_rgba, state, head_yaw=yaw, head_pitch=pitch,
        now_s=time.perf_counter(), target_tag="character/keyframe")
    frame._region_wobble_last_debug = state.last_debug
    return out


def apply_layer_wobble_filter(frame, layer, rgba: numpy.ndarray) -> numpy.ndarray:
    """Hot path: use cached RegionWobbleState — do not re-parse persist each frame."""
    if rgba is None:
        return rgba
    if not bool(getattr(layer, "region_wobble_enabled", False)):
        return rgba
    st = layer_wobble_state(frame, int(layer.slot_id))
    # Lightweight flag sync only (geometry/params live on st via UI/init).
    st.enabled = True
    st.idle_mode = normalize_idle_mode(
        getattr(layer, "region_wobble_idle_mode", st.idle_mode))
    if hasattr(layer, "region_wobble_pose_hooks_islands"):
        st.pose_hooks_islands = bool(layer.region_wobble_pose_hooks_islands)
    if hasattr(layer, "region_wobble_island_phase_stagger"):
        st.island_phase_stagger = bool(layer.region_wobble_island_phase_stagger)
    if not st.has_active_mask():
        return rgba
    yaw, pitch = head_pose_for_wobble(frame)
    out = apply_wobble(
        rgba, st, head_yaw=yaw, head_pitch=pitch,
        now_s=time.perf_counter(), target_tag=f"layer/{int(layer.slot_id)}")
    frame._region_wobble_last_debug = st.last_debug
    return out


def persist_masks(frame) -> None:
    """Call from save path / leave paint mode — not every tick."""
    try:
        ws = get_workspace_dir()
        st = frame.character_region_wobble
        for i, part in enumerate(st.regions):
            if part.mask is not None:
                save_mask_png(character_region_mask_path(ws, i), part.mask)
        # Combined legacy file = max of all regions.
        combined = st.mask_for_shape(
            *(st.regions[0].mask.shape[:2] if st.regions[0].mask is not None else (1, 1)))
        if combined is not None:
            save_mask_png(character_mask_path(ws), combined)
        layers_dir = Path(get_basic_layers_directory(str(frame.get_ui_state_file_path())))
        for slot_id, lst in list(frame._layer_region_wobble.items()):
            for i, part in enumerate(lst.regions):
                if part.mask is not None:
                    save_mask_png(layer_region_mask_path(layers_dir, slot_id, i), part.mask)
            combined = lst.mask_for_shape(
                *(lst.regions[0].mask.shape[:2]
                  if lst.regions and lst.regions[0].mask is not None else (1, 1)))
            if combined is not None:
                save_mask_png(layer_mask_path(layers_dir, slot_id), combined)
    except Exception:
        pass
