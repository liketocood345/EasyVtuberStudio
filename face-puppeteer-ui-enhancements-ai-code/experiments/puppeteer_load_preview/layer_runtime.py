"""
Layer-system runtime: state, geometry, composition, persistence.

Supports a dynamic number of layers (variable-length stack with the character
pinned in the middle). Layer assets are static PNG/WebP and animated GIF (GIF
composited with transparent disposal); preview thumbnails use the first frame.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Optional

import numpy
import wx

from rgba_capture_compose import sanitize_transparent_rgb

LAYER_STATIC_IMAGE_EXTENSIONS = (".png", ".webp")
LAYER_GIF_EXTENSIONS = (".gif",)
LAYER_ASSET_FILE_WILDCARD = (
    "All supported|*.png;*.webp;*.gif|"
    "PNG (*.png)|*.png|GIF (*.gif)|*.gif|"
    "All files (*.*)|*.*")

LAYER_COORD_SIZE = 512
GIF_PLAYBACK_LOOP = "loop"
GIF_PLAYBACK_PLAY_ONCE = "play_once"
GIF_PLAYBACK_STOPPED = "stopped"
GIF_PLAYBACK_MODES = (
    GIF_PLAYBACK_LOOP,
    GIF_PLAYBACK_PLAY_ONCE,
    GIF_PLAYBACK_STOPPED,
)

LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE = "toggle_visible"
LAYER_HOTKEY_ACTION_GIF_PLAY_ONCE = "gif_play_once"
LAYER_HOTKEY_ACTION_GIF_SHOW_PLAY_ONCE_HIDE = "gif_show_play_once_hide"
LAYER_HOTKEY_ACTION_GIF_PLAY = "gif_play"
LAYER_HOTKEY_ACTION_GIF_STOP = "gif_stop"
# Removed from UI/runtime (2026-06-18); load-time migration only.
_DEPRECATED_LAYER_HOTKEY_HOLD_ACTIONS: dict[str, str] = {
    "hold_to_hide": LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE,
    "hold_to_show": LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE,
    "hold_to_show_play_once": LAYER_HOTKEY_ACTION_GIF_SHOW_PLAY_ONCE_HIDE,
}
LAYER_HOTKEY_ACTIONS = (
    LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE,
    LAYER_HOTKEY_ACTION_GIF_PLAY_ONCE,
    LAYER_HOTKEY_ACTION_GIF_SHOW_PLAY_ONCE_HIDE,
    LAYER_HOTKEY_ACTION_GIF_PLAY,
    LAYER_HOTKEY_ACTION_GIF_STOP,
)
LAYER_HOTKEY_GIF_ACTIONS = (
    LAYER_HOTKEY_ACTION_GIF_PLAY_ONCE,
    LAYER_HOTKEY_ACTION_GIF_SHOW_PLAY_ONCE_HIDE,
    LAYER_HOTKEY_ACTION_GIF_PLAY,
    LAYER_HOTKEY_ACTION_GIF_STOP,
)
MAX_LAYER_HOTKEY_BINDINGS = 8

LAYER_HOTKEY_ACTION_LABELS: dict[str, str] = {
    LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE: "显隐切换 / Toggle visible",
    LAYER_HOTKEY_ACTION_GIF_PLAY_ONCE: "GIF 播一次 / GIF play once",
    LAYER_HOTKEY_ACTION_GIF_SHOW_PLAY_ONCE_HIDE: (
        "显示播一次后隐藏 / Show, play once, hide"),
    LAYER_HOTKEY_ACTION_GIF_PLAY: "GIF 播放 / GIF play loop",
    LAYER_HOTKEY_ACTION_GIF_STOP: "GIF 停止 / GIF stop",
}
DEFAULT_LAYER_COUNT = 5
BASIC_LAYERS_DIR_NAME = "basic_layers"

OCCLUSION_BEHIND = "behind_character"
OCCLUSION_FRONT = "in_front_of_character"

LAYER_MODE_BASIC = "layers"
LAYER_MODE_BASIC_LEGACY = "basic_five"
LAYER_MODE_ADVANCED = "advanced_unlimited"

HEAD_ANCHOR_RATIO = 0.84
HEAD_SEGMENT_MIN_RATIO = 0.06
NECK_ANCHOR_RATIO_DEFAULT = 0.62
NECK_ANCHOR_RATIO_MIN = 0.0
NECK_ANCHOR_RATIO_MAX = HEAD_ANCHOR_RATIO - HEAD_SEGMENT_MIN_RATIO
BODY_BIND_RAY_T_DEFAULT = 1.0
HEAD_BIND_RAY_T_DEFAULT = 1.0
BIND_RAY_PERCENT_DEFAULT = 100.0
DEFAULT_LAYER_BINDING_RAY_PERCENT = 100.0
BIND_RAY_PERCENT_UI_MIN = -500
BIND_RAY_PERCENT_UI_MAX = 500
RAY_DIAGRAM_EXTENSION_RATIO = 0.45
LOWER_SPINE_MOCAP_SHARE = 0.38
# How strongly the body layer-bind follows the character's OWN left-right torso
# lean (the mocap spine tilt driven by head pose), on top of the head-roll
# display auto-tilt. Folded into dynamic_enhancement_tilt_deg so BOTH the body
# bind anchor position AND its sprite rotation track the lean together -> a
# body-pinned sprite stays glued to the leaning torso instead of sliding.
# 1.0 = track the torso lean 1:1 (glued, matches the visible lower-spine lean);
# 0.0 = old behavior (display tilt only). Independent, tunable.
#
# This is the DEFAULT of a now user-tunable gain (BindingContext.body_bind_lean_
# follow_gain, persisted as "body_bind_lean_follow_gain"). It scales ONLY the
# black-box body-roll follow term, NOT display_rotation_deg. Why it needs to be
# tunable: the body-bind anchor sits at feet + spine_ray(angle) * dist, where
# dist = lower_segment_len * ray_percent can be hundreds of px. The follow term
# nudges `angle` by gain * sign * neck_z * 15deg, and that small angle change is
# amplified into a LARGE positional swing by the long dist — so with auto move/
# scale OFF (display=0) a tiny character lean throws a body-pinned layer far.
# Lowering this gain attenuates that displacement.
#
# NOTE: this is now SPLIT into two independent, user-tunable gains so position
# and sprite roll can be balanced separately (BindingContext.body_bind_pos_
# follow_gain / body_bind_roll_follow_gain). Position = anchor swing along the
# spine ray (the displacement amplified by `dist`); roll = the sprite's own
# rotation. This shared constant is just the default for both.
BODY_BIND_LEAN_FOLLOW_GAIN = 1.0
BODY_BIND_LEAN_FOLLOW_GAIN_MIN = 0.0
BODY_BIND_LEAN_FOLLOW_GAIN_MAX = 1.5
# Sign mapping the black-box model body_z roll VALUE to the on-screen torso ray
# DIRECTION (THA render roll convention vs spine_ray_unit_vector convention; and
# body_tilt_opposite_to_head makes the body lean opposite the head/display).
# Empirically -1 (the bound sprite leaned the wrong way left-right). Flip to
# +1 if it ever mirrors again. Applies to the black-box body roll term only,
# NOT to display_rotation_deg (which is locked to the warpAffine whole-image rot).
BODY_BIND_BLACKBOX_ROLL_SIGN = -1.0
# Symmetric knob for head bind: head-bind rotation already folds in the upper
# spine lean + neck-z roll (so head sprites are glued); this scales an extra
# head-roll follow so head-pinned sprites stay locked to head tilt. 1.0 = on.
HEAD_BIND_LEAN_FOLLOW_GAIN = 1.0
HEAD_POSE_X_LAYER_GAIN = 34.0
HEAD_POSE_Y_LAYER_GAIN = 38.0
HEAD_POSE_MOCAP_EXTRA_GAIN = 1.55
HEAD_NECK_Z_MAX_DEG = 15.0
HEAD_RAY_POSE_X_DEG_GAIN = 11.0
HEAD_RAY_POSE_Y_DEG_GAIN = 9.0
HEAD_BINDING_POSE_DEADZONE = 0.035
HEAD_BINDING_POSE_MAX_STEP = 0.055
HEAD_BINDING_MAX_CENTER_STEP_PX = 8.0
HEAD_BINDING_MAX_ROT_STEP_DEG = 3.5
BINDING_SMOOTH_ALPHA = 0.28
BINDING_SMOOTH_ALPHA_MIN = 0.05
BINDING_SMOOTH_ALPHA_MAX = 1.0

# Binding signal guide (shown in layer UI):
# - Stable / recommended: display_offset_x/y, display_scale, display_rotation_deg
#   (dynamic enhancement; already smoothed in MainFrame)
# - Head bind: two-segment spine — bottom→neck (body), neck→head (head bind)

BINDING_CHARACTER_BODY = "character:body"
BINDING_CHARACTER_HEAD = "character:head"
BINDING_LAYER_PREFIX = "layer:"

MOTION_MODE_NONE = "none"
MOTION_MODE_SIMPLE_SWING = "simple_swing"
SWING_SPEED_PROFILE_CONSTANT = "constant"
SWING_SPEED_PROFILE_EASE_ENDS = "ease_ends"
DEFAULT_SWING_PIVOT_U = 0.5
DEFAULT_SWING_PIVOT_V = 1.0
DEFAULT_SWING_AMPLITUDE_DEG = 15.0
DEFAULT_SWING_SPEED_DEG_PER_SEC = 30.0
SWING_AMPLITUDE_MIN_DEG = 1.0
SWING_AMPLITUDE_MAX_DEG = 90.0
SWING_SPEED_MIN_DEG_PER_SEC = 5.0
SWING_SPEED_MAX_DEG_PER_SEC = 180.0
SWING_MIN_AMPLITUDE_EPS = 1e-6

# Circular orbit: a single object travels a circle that lives in a tilted plane
# and is projected onto the screen. In-plane point = (R*cos t, R*sin t); the
# plane tilt tips the "depth" axis between fully into-screen (tilt 0 deg, strong
# front/back swap, edge-on ring) and fully vertical (tilt 90 deg, face-on circle,
# no depth). depth>0 = near -> drawn in front of character (upper slot); depth<0
# = far -> drawn behind (lower slot). depth also drives a near/far scale (fake
# perspective). The orbit center is a manually-placed pivot. The main + auxiliary
# layers are the same object's two sprites (currently the SAME asset, with a slot
# reserved for future distinct front/back 3D art); which one shows is decided by
# depth (upper vs lower), NOT by which is "main".
MOTION_MODE_CIRCULAR = "circular_orbit"
# Legacy persisted value; loaded layers are normalized to MOTION_MODE_CIRCULAR.
MOTION_MODE_ORBIT_SATELLITE = "orbit_satellite"
MAX_ORBIT_SATELLITES_PER_HOST = 5
ORBIT_SATELLITE_COUNT_MIN = 2
ORBIT_SATELLITE_COUNT_MAX = MAX_ORBIT_SATELLITES_PER_HOST + 1
DEFAULT_ORBIT_SATELLITE_COUNT = 2
DEFAULT_ORBIT_SATELLITE_INDEX = 1
# Re-anchor follower phase/speed from the host every N seconds (f-062).
ORBIT_HOST_SYNC_INTERVAL_S = 180.0
DEFAULT_ORBIT_RADIUS = 80.0
ORBIT_RADIUS_MIN = 0.0
ORBIT_RADIUS_MAX = float(LAYER_COORD_SIZE) / 2.0
DEFAULT_ORBIT_PLANE_TILT_DEG = 25.0
ORBIT_PLANE_TILT_MIN_DEG = 0.0
ORBIT_PLANE_TILT_MAX_DEG = 90.0
DEFAULT_ORBIT_SPEED_DEG_PER_SEC = 60.0
ORBIT_SPEED_MIN_DEG_PER_SEC = 5.0
ORBIT_SPEED_MAX_DEG_PER_SEC = 360.0
DEFAULT_ORBIT_NEAR_SCALE = 1.3
DEFAULT_ORBIT_FAR_SCALE = 0.7
ORBIT_SCALE_MIN = 0.1
ORBIT_SCALE_MAX = 3.0
DEFAULT_ORBIT_PIVOT_U = 0.5
DEFAULT_ORBIT_PIVOT_V = 0.5
ORBIT_MIN_RADIUS_EPS = 1e-6


def clamp_binding_smooth_alpha(value: float) -> float:
    return max(
        BINDING_SMOOTH_ALPHA_MIN,
        min(BINDING_SMOOTH_ALPHA_MAX, float(value)))


def clamp_body_bind_lean_follow_gain(value: float) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return BODY_BIND_LEAN_FOLLOW_GAIN
    return max(
        BODY_BIND_LEAN_FOLLOW_GAIN_MIN,
        min(BODY_BIND_LEAN_FOLLOW_GAIN_MAX, v))


def clamp_neck_anchor_ratio(value: float) -> float:
    return max(
        NECK_ANCHOR_RATIO_MIN,
        min(NECK_ANCHOR_RATIO_MAX, float(value)))


def clamp_bind_ray_t(value: float) -> float:
    """Legacy ratio 0–1; prefer bind_ray_percent_to_ratio."""
    return normalize_bind_ray_percent(float(value) * 100.0) / 100.0


def normalize_bind_ray_percent(value: float) -> float:
    pct = float(value)
    if not math.isfinite(pct):
        return BIND_RAY_PERCENT_DEFAULT
    return pct


def apply_body_head_tilt_opposite_to_pose(
        pose: list[float],
        *,
        neck_z_index: int,
        body_z_index: int,
        opposite: bool) -> list[float]:
    """When opposite: body roll negates neck roll; head (neck_z) keeps mocap direction."""
    if not opposite:
        return pose
    adjusted = list(pose)
    adjusted[body_z_index] = -float(adjusted[neck_z_index])
    return adjusted


def bind_ray_percent_to_ratio(percent: float) -> float:
    return normalize_bind_ray_percent(percent) / 100.0


def layer_binding_ray_percent(layer: BasicLayerSlot) -> float:
    pct = getattr(layer, "binding_ray_percent", None)
    if pct is None:
        return DEFAULT_LAYER_BINDING_RAY_PERCENT
    return normalize_bind_ray_percent(pct)


def layer_binding_neck_anchor_ratio(layer: BasicLayerSlot) -> float:
    ratio = getattr(layer, "binding_neck_anchor_ratio", None)
    if ratio is None:
        return NECK_ANCHOR_RATIO_DEFAULT
    return clamp_neck_anchor_ratio(ratio)


def migrate_bind_ray_percent_from_state(
        state: dict[str, Any],
        *,
        percent_key: str,
        legacy_ratio_key: str,
        default: float = BIND_RAY_PERCENT_DEFAULT) -> float:
    if percent_key in state:
        return normalize_bind_ray_percent(float(state[percent_key]))
    if legacy_ratio_key in state:
        return normalize_bind_ray_percent(float(state[legacy_ratio_key]) * 100.0)
    return default


def binding_smooth_alpha_for_layer(layer: BasicLayerSlot) -> float:
    return clamp_binding_smooth_alpha(
        getattr(layer, "binding_follow_smooth_alpha", BINDING_SMOOTH_ALPHA))


def normalize_binding_target(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in ("null", "none"):
        return None
    if text == "character":
        return BINDING_CHARACTER_BODY
    if text in (BINDING_CHARACTER_BODY, BINDING_CHARACTER_HEAD):
        return text
    if text.startswith(BINDING_LAYER_PREFIX):
        try:
            slot_id = int(text.split(":", 1)[1])
        except (IndexError, ValueError):
            return None
        if slot_id >= 0:
            return f"{BINDING_LAYER_PREFIX}{slot_id}"
    return None


def binding_target_label(value: Optional[str]) -> str:
    normalized = normalize_binding_target(value)
    if normalized is None:
        return ""
    if normalized == BINDING_CHARACTER_BODY:
        return "绑:身体"
    if normalized == BINDING_CHARACTER_HEAD:
        return "绑:头"
    if normalized.startswith(BINDING_LAYER_PREFIX):
        try:
            slot_id = int(normalized.split(":")[1])
            return f"绑:L{slot_id + 1}"
        except ValueError:
            return ""
    return ""


def truncate_display_filename(name: str, max_len: int = 18) -> str:
    name = str(name or "").strip()
    if len(name) <= max_len:
        return name
    if max_len <= 3:
        return name[:max_len]
    head = max(1, (max_len - 1) // 2)
    tail = max(1, max_len - head - 1)
    return f"{name[:head]}…{name[-tail:]}"


def format_layer_row_title(slot_id: int, layer: BasicLayerSlot) -> str:
    base = f"图层 {slot_id + 1}"
    if layer.asset_path:
        name = truncate_display_filename(os.path.basename(layer.asset_path))
        return f"{base} · {name}"
    return f"{base} · （空）"


def classify_layer_asset_kind(path: Optional[str]) -> str:
    """Return empty | image | gif | unknown for a layer asset path."""
    if not path:
        return "empty"
    ext = os.path.splitext(str(path).strip())[1].lower()
    if ext in LAYER_GIF_EXTENSIONS:
        return "gif"
    if ext in LAYER_STATIC_IMAGE_EXTENSIONS:
        return "image"
    return "unknown"


def layer_asset_kind_label(kind: str) -> str:
    if kind == "gif":
        return "GIF"
    if kind == "image":
        return "PNG"
    return ""


def format_layer_row_summary(
        layer: BasicLayerSlot,
        state: Optional[BasicLayersState] = None) -> str:
    if state is not None:
        if layer_orbits_with_host(layer):
            host_id = layer.orbit_host_slot_id
            if host_id is not None and resolve_orbit_host_layer(state, layer) is not None:
                count = clamp_orbit_satellite_count(layer.orbit_satellite_count)
                index = clamp_orbit_satellite_index(
                    layer.orbit_satellite_index, count)
                return (
                    f"与图层 {host_id + 1} 一起环绕 · 序号 {index}/{count}"
                    f" / Orbit with L{host_id + 1} · {index}/{count}")
        owner = orbit_aux_owner(state, layer.slot_id)
        if owner is not None:
            return (
                f"堆栈位被图层 {owner + 1} 圆周运动征用"
                f" / Stack slot used by Layer {owner + 1} orbit")
    side = "上" if layer.occlusion == OCCLUSION_FRONT else "下"
    parts = [f"{side} z{layer.z_order + 1}"]
    kind_label = layer_asset_kind_label(classify_layer_asset_kind(layer.asset_path))
    if kind_label:
        parts.append(kind_label)
    bind = binding_target_label(layer.binding_parent)
    if bind:
        tags = [bind.replace("绑:", "")]
        if layer.binding_follow_rotation_same and layer.binding_follow_rotation_reverse:
            tags.append("±转")
        elif layer.binding_follow_rotation_same:
            tags.append("同步")
        elif layer.binding_follow_rotation_reverse:
            tags.append("反转")
        if layer.binding_follow_smooth:
            pct = int(round(binding_smooth_alpha_for_layer(layer) * 100))
            tags.append(f"平滑{pct}%")
        if layer.binding_follow_mocap_position:
            tags.append("增位移")
        if layer.binding_follow_mocap_roll:
            tags.append("增滚转")
        parts.append("·".join(tags))
    else:
        parts.append("未绑")
    if layer.motion_mode == MOTION_MODE_SIMPLE_SWING:
        profile_tag = "匀" if layer.swing_speed_profile == SWING_SPEED_PROFILE_CONSTANT else "缓"
        parts.append(
            f"摆±{layer.swing_amplitude_deg:.0f}°"
            f"@{layer.swing_speed_deg_per_sec:.0f}°/s·{profile_tag}")
    parts.append(f"scl{layer.transform.scale:.1f}")
    parts.append(f"rot{layer.transform.rotation_deg:.0f}°")
    parts.append("显" if layer.visible else "隐")
    return " | ".join(parts)


def contrast_highlight_colour(red: int, green: int, blue: int) -> wx.Colour:
    """Pick a highlight colour opposite to the output background RGB."""
    red = max(0, min(255, int(red)))
    green = max(0, min(255, int(green)))
    blue = max(0, min(255, int(blue)))
    return wx.Colour(255 - red, 255 - green, 255 - blue)


def _lerp_angle_deg(current: float, target: float, alpha: float) -> float:
    alpha = max(0.0, min(1.0, float(alpha)))
    delta = (target - current + 180.0) % 360.0 - 180.0
    return current + delta * alpha


def _rate_limit_scalar(current: float, target: float, max_step: float) -> float:
    max_step = max(0.0, float(max_step))
    if max_step <= 0.0:
        return target
    delta = target - current
    if abs(delta) <= max_step:
        return target
    return current + math.copysign(max_step, delta)


def _binding_inherited_rotation_deg(
        layer: BasicLayerSlot,
        state: BasicLayersState,
        binding_context: BindingContext,
        *,
        visiting: Optional[set[int]] = None) -> float:
    target = normalize_binding_target(layer.binding_parent)
    if target in (BINDING_CHARACTER_BODY, BINDING_CHARACTER_HEAD):
        if target == BINDING_CHARACTER_HEAD:
            return binding_context.head_binding_rotation_deg(
                extra_pose_roll=bool(layer.binding_follow_mocap_roll))
        return binding_context.body_binding_rotation_deg()
    parent_slot = parse_layer_binding_slot(target)
    if parent_slot is not None:
        if visiting is None:
            visiting = set()
        if layer.slot_id in visiting:
            return 0.0
        visiting.add(layer.slot_id)
        parent = find_layer_slot(state, parent_slot)
        if parent is None:
            return 0.0
        return effective_layer_rotation_deg(
            parent, state, binding_context, visiting=visiting)
    return 0.0


def effective_layer_rotation_deg(
        layer: BasicLayerSlot,
        state: BasicLayersState,
        binding_context: Optional[BindingContext],
        *,
        visiting: Optional[set[int]] = None) -> float:
    local = float(layer.transform.rotation_deg)
    if binding_context is None:
        return local
    same = bool(layer.binding_follow_rotation_same)
    reverse = bool(layer.binding_follow_rotation_reverse)
    if not same and not reverse:
        return local
    inherited = _binding_inherited_rotation_deg(
        layer, state, binding_context, visiting=visiting)
    addon = 0.0
    if same:
        addon += inherited
    if reverse:
        addon -= inherited
    return local + addon


def orbit_binding_follow_rotation_deg(
        layer: BasicLayerSlot,
        state: BasicLayersState,
        binding_context: Optional[BindingContext]) -> float:
    """Binding follow-roll addon applied to the orbit plane (not local transform)."""
    if binding_context is None:
        return 0.0
    same = bool(layer.binding_follow_rotation_same)
    reverse = bool(layer.binding_follow_rotation_reverse)
    if not same and not reverse:
        return 0.0
    inherited = _binding_inherited_rotation_deg(layer, state, binding_context)
    addon = 0.0
    if same:
        addon += inherited
    if reverse:
        addon -= inherited
    return addon


def rotate_orbit_plane_offsets(
        offset_x: float,
        offset_y: float,
        rotation_deg: float) -> tuple[float, float]:
    if abs(rotation_deg) <= 1e-4:
        return offset_x, offset_y
    rad = math.radians(float(rotation_deg))
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    return (
        offset_x * cos_r - offset_y * sin_r,
        offset_x * sin_r + offset_y * cos_r)


def parse_layer_binding_slot(value: Optional[str]) -> Optional[int]:
    normalized = normalize_binding_target(value)
    if normalized is None or not normalized.startswith(BINDING_LAYER_PREFIX):
        return None
    try:
        return int(normalized.split(":")[1])
    except (IndexError, ValueError):
        return None


def find_layer_slot(state: BasicLayersState, slot_id: int) -> Optional[BasicLayerSlot]:
    """Return an existing layer without resurrecting deleted slots."""
    for layer in state.layers:
        if layer.slot_id == slot_id:
            return layer
    return None



def migrate_layer_hotkey_bindings(state: BasicLayersState) -> None:
    for layer in state.layers:
        if not layer.hotkey_bindings:
            continue
        layer.hotkey_bindings = [
            LayerHotkeyBinding(
                action=normalize_layer_hotkey_action(binding.action),
                modifiers=int(binding.modifiers),
                key_code=int(binding.key_code))
            for binding in layer.hotkey_bindings[:MAX_LAYER_HOTKEY_BINDINGS]
        ]


def sanitize_layer_references(state: BasicLayersState) -> None:
    """Drop bindings/aux targets that point at layers no longer in the stack."""
    migrate_layer_hotkey_bindings(state)
    live = {layer.slot_id for layer in state.layers}
    for layer in state.layers:
        if layer.motion_mode == MOTION_MODE_ORBIT_SATELLITE:
            layer.motion_mode = MOTION_MODE_CIRCULAR
        prev_aux_id = layer.orbit_aux_slot_id
        aux_id = prev_aux_id
        if aux_id is not None and aux_id not in live:
            layer.orbit_aux_slot_id = None
            aux_id = None
        if aux_id is not None:
            layer.orbit_aux_slot_id = normalize_orbit_aux_slot_id(
                state, layer.slot_id, aux_id)
            aux_id = layer.orbit_aux_slot_id
        if prev_aux_id is not None and aux_id is None:
            freed = find_layer_slot(state, int(prev_aux_id))
            if (
                    freed is not None
                    and orbit_aux_owner(state, int(prev_aux_id)) is None):
                freed.visible = True
        host_id = layer.orbit_host_slot_id
        if host_id is not None and host_id not in live:
            layer.orbit_host_slot_id = None
            host_id = None
        if host_id is not None:
            layer.orbit_host_slot_id = normalize_orbit_host_slot_id(
                state, layer.slot_id, host_id)
        parent_slot = parse_layer_binding_slot(layer.binding_parent)
        if parent_slot is not None and parent_slot not in live:
            layer.binding_parent = None
    _enforce_orbit_satellite_host_limits(state)
    apply_orbit_requisition_visibility(state)


def _enforce_orbit_satellite_host_limits(state: BasicLayersState) -> None:
    for host_id in circular_orbit_host_slot_ids(state):
        members = sorted(orbit_satellite_member_slot_ids(state, host_id))
        for extra_slot_id in members[MAX_ORBIT_SATELLITES_PER_HOST:]:
            extra = find_layer_slot(state, extra_slot_id)
            if extra is not None:
                extra.orbit_host_slot_id = None


def layer_slot_uses_orbit_motion(state: BasicLayersState, slot_id: int) -> bool:
    layer = find_layer_slot(state, slot_id)
    return layer is not None and layer.motion_mode == MOTION_MODE_CIRCULAR


def orbit_aux_slot_is_allowed(
        state: BasicLayersState,
        owner_slot_id: int,
        aux_slot_id: Optional[int]) -> bool:
    if aux_slot_id is None:
        return True
    if aux_slot_id == owner_slot_id:
        return False
    if find_layer_slot(state, aux_slot_id) is None:
        return False
    if layer_slot_uses_orbit_motion(state, aux_slot_id):
        return False
    carrier_owner = orbit_aux_carriers(state).get(aux_slot_id)
    if carrier_owner is not None and carrier_owner != owner_slot_id:
        return False
    return True


def normalize_orbit_aux_slot_id(
        state: BasicLayersState,
        owner_slot_id: int,
        aux_slot_id: Optional[int]) -> Optional[int]:
    if aux_slot_id is None:
        return None
    if orbit_aux_slot_is_allowed(state, owner_slot_id, int(aux_slot_id)):
        return int(aux_slot_id)
    return None


def cleanup_layer_references(state: BasicLayersState, removed_slot_id: int) -> None:
    """Clear cross-layer pointers after ``remove_layer``."""
    bind_target = f"{BINDING_LAYER_PREFIX}{removed_slot_id}"
    host_followers_detached = False
    for layer in state.layers:
        if layer.orbit_aux_slot_id == removed_slot_id:
            layer.orbit_aux_slot_id = None
        if layer.orbit_host_slot_id == removed_slot_id:
            layer.orbit_follow_last_sync_time_s = -1.0
            layer.orbit_host_slot_id = None
            host_followers_detached = True
        if normalize_binding_target(layer.binding_parent) == bind_target:
            layer.binding_parent = None
    if host_followers_detached:
        sanitize_layer_references(state)


def _parse_follow_rotation_same(data: dict) -> bool:
    if "binding_follow_rotation_same" in data:
        return bool(data.get("binding_follow_rotation_same"))
    if bool(data.get("binding_follow_rotation", False)):
        return True
    return False


def _parse_follow_rotation_reverse(data: dict) -> bool:
    if "binding_follow_rotation_reverse" in data:
        return bool(data.get("binding_follow_rotation_reverse"))
    return False


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _safe_optional_int(value: object) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


@dataclass
class LayerTransform:
    """Layer pose in output canvas space (512-normalized, center-origin)."""
    offset_x: float = 0.0
    offset_y: float = 0.0
    scale: float = 1.0
    rotation_deg: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "offset_x": float(self.offset_x),
            "offset_y": float(self.offset_y),
            "scale": float(self.scale),
            "rotation_deg": float(self.rotation_deg),
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> LayerTransform:
        if not isinstance(data, dict):
            return cls()
        return cls(
            offset_x=float(data.get("offset_x", 0.0)),
            offset_y=float(data.get("offset_y", 0.0)),
            scale=max(0.05, float(data.get("scale", 1.0))),
            rotation_deg=float(data.get("rotation_deg", 0.0)),
        )


def center_layer_transform(transform: LayerTransform) -> None:
    """Align layer image center to output window center (512-space origin)."""
    transform.offset_x = 0.0
    transform.offset_y = 0.0


def reset_layer_transform(transform: LayerTransform) -> None:
    """Reset layer pose to default centered pose (position, scale, rotation)."""
    center_layer_transform(transform)
    transform.scale = 1.0
    transform.rotation_deg = 0.0


def normalize_gif_playback_mode(value: object) -> str:
    if value in GIF_PLAYBACK_MODES:
        return str(value)
    return GIF_PLAYBACK_LOOP


def normalize_layer_hotkey_action(value: object) -> str:
    if value in LAYER_HOTKEY_ACTIONS:
        return str(value)
    key = str(value) if value is not None else ""
    migrated = _DEPRECATED_LAYER_HOTKEY_HOLD_ACTIONS.get(key)
    if migrated is not None:
        return migrated
    return LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE


@dataclass
class LayerHotkeyBinding:
    action: str = LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE
    modifiers: int = 0
    key_code: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": normalize_layer_hotkey_action(self.action),
            "modifiers": int(self.modifiers),
            "key_code": int(self.key_code),
        }

    @classmethod
    def from_dict(cls, data: object) -> Optional["LayerHotkeyBinding"]:
        if not isinstance(data, dict):
            return None
        try:
            key_code = int(data.get("key_code", 0))
        except (TypeError, ValueError):
            return None
        if key_code < 0:
            return None
        try:
            modifiers = int(data.get("modifiers", 0))
        except (TypeError, ValueError):
            modifiers = 0
        return cls(
            action=normalize_layer_hotkey_action(data.get("action")),
            modifiers=modifiers,
            key_code=key_code,
        )


def layer_hotkey_bindings_from_list(data: object) -> list[LayerHotkeyBinding]:
    if not isinstance(data, list):
        return []
    bindings: list[LayerHotkeyBinding] = []
    for item in data[:MAX_LAYER_HOTKEY_BINDINGS]:
        binding = LayerHotkeyBinding.from_dict(item)
        if binding is not None:
            bindings.append(binding)
    return bindings


def ensure_gif_playback_epoch(layer: "BasicLayerSlot", now: float) -> None:
    if layer.gif_playback_epoch <= 0.0:
        layer.gif_playback_epoch = now


def set_gif_playback_mode(
        layer: "BasicLayerSlot",
        mode: str,
        *,
        now: Optional[float] = None) -> None:
    layer.gif_playback_mode = normalize_gif_playback_mode(mode)
    layer.gif_playback_epoch = time.time() if now is None else now


def resolve_gif_frame_index(
        layer: "BasicLayerSlot",
        durations_ms: list[int],
        total_ms: int,
        frame_count: int,
        now: float) -> int:
    """Pick GIF sub-frame index from per-layer playback mode."""
    mode = normalize_gif_playback_mode(layer.gif_playback_mode)
    if mode == GIF_PLAYBACK_STOPPED:
        return 0
    ensure_gif_playback_epoch(layer, now)
    elapsed_ms = int(max(0.0, (now - layer.gif_playback_epoch) * 1000.0))
    if mode == GIF_PLAYBACK_PLAY_ONCE:
        if elapsed_ms >= total_ms:
            layer.gif_playback_mode = GIF_PLAYBACK_STOPPED
            layer.gif_playback_epoch = now
            if layer.gif_hide_when_playback_stops:
                layer.gif_hide_when_playback_stops = False
                layer.visible = False
                layer._gif_playback_visibility_dirty = True
            return 0
    else:
        elapsed_ms = elapsed_ms % max(1, total_ms)
    acc = 0
    for idx, duration in enumerate(durations_ms):
        acc += duration
        if elapsed_ms < acc:
            return idx
    return max(0, frame_count - 1)


def layer_hotkey_action_needs_asset_cache_reset(
        layer: BasicLayerSlot, action: str) -> bool:
    """Whether switching to this hotkey action should invalidate GIF asset cache."""
    if classify_layer_asset_kind(layer.asset_path or "") != "gif":
        return False
    normalized = normalize_layer_hotkey_action(action)
    return normalized in LAYER_HOTKEY_GIF_ACTIONS


def _apply_layer_hotkey_action_one(
        state: "BasicLayersState",
        slot_id: int,
        action: str,
        *,
        now: Optional[float] = None) -> bool:
    try:
        layer = state.get_slot(slot_id)
    except KeyError:
        return False
    normalized = normalize_layer_hotkey_action(action)
    time_now = time.time() if now is None else now
    if normalized == LAYER_HOTKEY_ACTION_TOGGLE_VISIBLE:
        layer.visible = not layer.visible
        return True
    if classify_layer_asset_kind(layer.asset_path or "") != "gif":
        return False
    if normalized == LAYER_HOTKEY_ACTION_GIF_PLAY:
        layer.gif_hide_when_playback_stops = False
        set_gif_playback_mode(layer, GIF_PLAYBACK_LOOP, now=time_now)
        layer.visible = True
        return True
    if normalized == LAYER_HOTKEY_ACTION_GIF_PLAY_ONCE:
        layer.gif_hide_when_playback_stops = False
        set_gif_playback_mode(layer, GIF_PLAYBACK_PLAY_ONCE, now=time_now)
        layer.visible = True
        return True
    if normalized == LAYER_HOTKEY_ACTION_GIF_SHOW_PLAY_ONCE_HIDE:
        layer.gif_hide_when_playback_stops = True
        set_gif_playback_mode(layer, GIF_PLAYBACK_PLAY_ONCE, now=time_now)
        layer.visible = True
        return True
    if normalized == LAYER_HOTKEY_ACTION_GIF_STOP:
        layer.gif_hide_when_playback_stops = False
        set_gif_playback_mode(layer, GIF_PLAYBACK_STOPPED, now=time_now)
        return True
    return False


def apply_layer_hotkey_action(
        state: "BasicLayersState",
        slot_id: int,
        action: str,
        *,
        now: Optional[float] = None) -> bool:
    """Apply a layer hotkey action on one layer slot."""
    return _apply_layer_hotkey_action_one(state, slot_id, action, now=now)


def apply_hotkey_action_idle_layer_state(
        layer: BasicLayerSlot,
        action: str,
        *,
        now: Optional[float] = None) -> None:
    """Put layer in a clean idle state after the user changes a hotkey action."""
    normalized = normalize_layer_hotkey_action(action)
    layer.gif_hide_when_playback_stops = False
    layer._gif_playback_visibility_dirty = False
    is_gif = classify_layer_asset_kind(layer.asset_path or "") == "gif"
    time_now = time.time() if now is None else now
    show_on_trigger = normalized in (
        LAYER_HOTKEY_ACTION_GIF_SHOW_PLAY_ONCE_HIDE,
        LAYER_HOTKEY_ACTION_GIF_PLAY_ONCE,
    )
    if show_on_trigger:
        layer.visible = False
    if not is_gif:
        return
    if normalized == LAYER_HOTKEY_ACTION_GIF_PLAY:
        set_gif_playback_mode(layer, GIF_PLAYBACK_LOOP, now=time_now)
    else:
        set_gif_playback_mode(layer, GIF_PLAYBACK_STOPPED, now=time_now)


def reload_layer_from_asset_material(
        layer: BasicLayerSlot,
        *,
        idle_for_hotkey_action: Optional[str] = None,
        now: Optional[float] = None) -> bool:
    """Reset runtime layer state as if the asset was loaded fresh (cache cleared by caller)."""
    if not layer.asset_path:
        return False
    if idle_for_hotkey_action is not None:
        apply_hotkey_action_idle_layer_state(
            layer, idle_for_hotkey_action, now=now)
    else:
        layer.gif_hide_when_playback_stops = False
        layer._gif_playback_visibility_dirty = False
        if classify_layer_asset_kind(layer.asset_path or "") == "gif":
            set_gif_playback_mode(layer, GIF_PLAYBACK_STOPPED, now=now)
    return True


@dataclass
class BasicLayerSlot:
    slot_id: int
    enabled: bool = True
    visible: bool = True
    asset_path: Optional[str] = None
    z_order: int = 0
    occlusion: str = OCCLUSION_BEHIND
    transform: LayerTransform = field(default_factory=LayerTransform)
    binding_parent: Optional[str] = None
    binding_follow_rotation_same: bool = False
    binding_follow_rotation_reverse: bool = False
    binding_follow_mocap_position: bool = False
    binding_follow_mocap_roll: bool = False
    binding_follow_smooth: bool = True
    binding_follow_smooth_alpha: float = BINDING_SMOOTH_ALPHA
    binding_ray_percent: Optional[float] = None
    binding_neck_anchor_ratio: Optional[float] = None
    motion_mode: str = MOTION_MODE_NONE
    swing_pivot_u: float = DEFAULT_SWING_PIVOT_U
    swing_pivot_v: float = DEFAULT_SWING_PIVOT_V
    swing_amplitude_deg: float = DEFAULT_SWING_AMPLITUDE_DEG
    swing_speed_deg_per_sec: float = DEFAULT_SWING_SPEED_DEG_PER_SEC
    swing_speed_profile: str = SWING_SPEED_PROFILE_EASE_ENDS
    swing_phase_rad: float = 0.0
    orbit_radius: float = DEFAULT_ORBIT_RADIUS
    orbit_plane_tilt_deg: float = DEFAULT_ORBIT_PLANE_TILT_DEG
    orbit_speed_deg_per_sec: float = DEFAULT_ORBIT_SPEED_DEG_PER_SEC
    orbit_phase_rad: float = 0.0
    orbit_pivot_u: float = DEFAULT_ORBIT_PIVOT_U
    orbit_pivot_v: float = DEFAULT_ORBIT_PIVOT_V
    orbit_near_scale: float = DEFAULT_ORBIT_NEAR_SCALE
    orbit_far_scale: float = DEFAULT_ORBIT_FAR_SCALE
    orbit_aux_slot_id: Optional[int] = None
    orbit_host_slot_id: Optional[int] = None
    orbit_satellite_index: int = DEFAULT_ORBIT_SATELLITE_INDEX
    orbit_satellite_count: int = DEFAULT_ORBIT_SATELLITE_COUNT
    orbit_follow_last_sync_time_s: float = -1.0
    hotkey_bindings: list[LayerHotkeyBinding] = field(default_factory=list)
    gif_playback_mode: str = GIF_PLAYBACK_LOOP
    gif_playback_epoch: float = 0.0
    gif_hide_when_playback_stops: bool = False
    _gif_playback_visibility_dirty: bool = field(default=False, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "slot_id": int(self.slot_id),
            "enabled": bool(self.enabled),
            "visible": bool(self.visible),
            "asset_path": self.asset_path,
            "z_order": int(self.z_order),
            "occlusion": self.occlusion,
            "transform": self.transform.to_dict(),
            "binding_parent": self.binding_parent,
            "binding_follow_rotation_same": bool(self.binding_follow_rotation_same),
            "binding_follow_rotation_reverse": bool(self.binding_follow_rotation_reverse),
            "binding_follow_mocap_position": bool(self.binding_follow_mocap_position),
            "binding_follow_mocap_roll": bool(self.binding_follow_mocap_roll),
            "binding_follow_smooth": bool(self.binding_follow_smooth),
            "binding_follow_smooth_alpha": binding_smooth_alpha_for_layer(self),
        }
        if normalize_binding_target(self.binding_parent) is not None:
            payload["binding_ray_percent"] = layer_binding_ray_percent(self)
            payload["binding_neck_anchor_ratio"] = layer_binding_neck_anchor_ratio(self)
        payload["motion_mode"] = normalize_motion_mode(self.motion_mode)
        if self.motion_mode == MOTION_MODE_SIMPLE_SWING:
            payload["swing_pivot_u"] = clamp_swing_pivot_u(self.swing_pivot_u)
            payload["swing_pivot_v"] = clamp_swing_pivot_v(self.swing_pivot_v)
            payload["swing_amplitude_deg"] = clamp_swing_amplitude_deg(self.swing_amplitude_deg)
            payload["swing_speed_deg_per_sec"] = clamp_swing_speed_deg_per_sec(
                self.swing_speed_deg_per_sec)
            payload["swing_speed_profile"] = normalize_swing_speed_profile(
                self.swing_speed_profile)
            payload["swing_phase_rad"] = float(self.swing_phase_rad)
        if self.motion_mode == MOTION_MODE_CIRCULAR:
            payload["orbit_radius"] = clamp_orbit_radius(self.orbit_radius)
            payload["orbit_plane_tilt_deg"] = clamp_orbit_plane_tilt_deg(self.orbit_plane_tilt_deg)
            payload["orbit_speed_deg_per_sec"] = clamp_orbit_speed_deg_per_sec(
                self.orbit_speed_deg_per_sec)
            payload["orbit_phase_rad"] = float(self.orbit_phase_rad)
            payload["orbit_pivot_u"] = clamp_swing_pivot_u(self.orbit_pivot_u)
            payload["orbit_pivot_v"] = clamp_swing_pivot_v(self.orbit_pivot_v)
            payload["orbit_near_scale"] = clamp_orbit_scale(self.orbit_near_scale)
            payload["orbit_far_scale"] = clamp_orbit_scale(self.orbit_far_scale)
            payload["orbit_aux_slot_id"] = (
                int(self.orbit_aux_slot_id) if self.orbit_aux_slot_id is not None else None)
            if self.orbit_host_slot_id is not None:
                payload["orbit_host_slot_id"] = int(self.orbit_host_slot_id)
                payload["orbit_satellite_index"] = clamp_orbit_satellite_index(
                    self.orbit_satellite_index, self.orbit_satellite_count)
                payload["orbit_satellite_count"] = clamp_orbit_satellite_count(
                    self.orbit_satellite_count)
        if self.hotkey_bindings:
            payload["hotkey_bindings"] = [
                binding.to_dict() for binding in self.hotkey_bindings[:MAX_LAYER_HOTKEY_BINDINGS]]
        return payload

    @classmethod
    def from_dict(cls, data: dict, slot_id: int) -> BasicLayerSlot:
        occlusion = str(data.get("occlusion", OCCLUSION_BEHIND))
        if occlusion not in (OCCLUSION_BEHIND, OCCLUSION_FRONT):
            occlusion = OCCLUSION_BEHIND
        sat_count_raw = _safe_int(
            data.get("orbit_satellite_count", DEFAULT_ORBIT_SATELLITE_COUNT),
            DEFAULT_ORBIT_SATELLITE_COUNT)
        sat_index_raw = _safe_int(
            data.get("orbit_satellite_index", DEFAULT_ORBIT_SATELLITE_INDEX),
            DEFAULT_ORBIT_SATELLITE_INDEX)
        return cls(
            slot_id=slot_id,
            enabled=bool(data.get("enabled", True)),
            visible=bool(data.get("visible", True)),
            asset_path=data.get("asset_path") if data.get("asset_path") else None,
            z_order=_safe_int(data.get("z_order", slot_id), slot_id),
            occlusion=occlusion,
            transform=LayerTransform.from_dict(data.get("transform")),
            binding_parent=normalize_binding_target(data.get("binding_parent")),
            binding_follow_rotation_same=_parse_follow_rotation_same(data),
            binding_follow_rotation_reverse=_parse_follow_rotation_reverse(data),
            binding_follow_mocap_position=bool(data.get("binding_follow_mocap_position", False)),
            binding_follow_mocap_roll=bool(data.get("binding_follow_mocap_roll", False)),
            binding_follow_smooth=bool(data.get("binding_follow_smooth", True)),
            binding_follow_smooth_alpha=clamp_binding_smooth_alpha(
                float(data.get("binding_follow_smooth_alpha", BINDING_SMOOTH_ALPHA))),
            binding_ray_percent=(
                normalize_bind_ray_percent(float(data["binding_ray_percent"]))
                if data.get("binding_ray_percent") is not None
                else None),
            binding_neck_anchor_ratio=(
                clamp_neck_anchor_ratio(float(data["binding_neck_anchor_ratio"]))
                if data.get("binding_neck_anchor_ratio") is not None
                else None),
            motion_mode=normalize_motion_mode(data.get("motion_mode")),
            swing_pivot_u=clamp_swing_pivot_u(
                float(data.get("swing_pivot_u", DEFAULT_SWING_PIVOT_U))),
            swing_pivot_v=clamp_swing_pivot_v(
                float(data.get("swing_pivot_v", DEFAULT_SWING_PIVOT_V))),
            swing_amplitude_deg=clamp_swing_amplitude_deg(
                float(data.get("swing_amplitude_deg", DEFAULT_SWING_AMPLITUDE_DEG))),
            swing_speed_deg_per_sec=clamp_swing_speed_deg_per_sec(
                float(data.get("swing_speed_deg_per_sec", DEFAULT_SWING_SPEED_DEG_PER_SEC))),
            swing_speed_profile=normalize_swing_speed_profile(
                data.get("swing_speed_profile")),
            swing_phase_rad=float(data.get("swing_phase_rad", default_swing_phase_rad(slot_id))),
            orbit_radius=clamp_orbit_radius(
                float(data.get("orbit_radius", DEFAULT_ORBIT_RADIUS))),
            orbit_plane_tilt_deg=clamp_orbit_plane_tilt_deg(
                float(data.get("orbit_plane_tilt_deg", DEFAULT_ORBIT_PLANE_TILT_DEG))),
            orbit_speed_deg_per_sec=clamp_orbit_speed_deg_per_sec(
                float(data.get("orbit_speed_deg_per_sec", DEFAULT_ORBIT_SPEED_DEG_PER_SEC))),
            orbit_phase_rad=float(data.get("orbit_phase_rad", 0.0)),
            orbit_pivot_u=clamp_swing_pivot_u(
                float(data.get("orbit_pivot_u", DEFAULT_ORBIT_PIVOT_U))),
            orbit_pivot_v=clamp_swing_pivot_v(
                float(data.get("orbit_pivot_v", DEFAULT_ORBIT_PIVOT_V))),
            orbit_near_scale=clamp_orbit_scale(
                float(data.get("orbit_near_scale", DEFAULT_ORBIT_NEAR_SCALE))),
            orbit_far_scale=clamp_orbit_scale(
                float(data.get("orbit_far_scale", DEFAULT_ORBIT_FAR_SCALE))),
            orbit_aux_slot_id=_safe_optional_int(data.get("orbit_aux_slot_id")),
            orbit_host_slot_id=_safe_optional_int(data.get("orbit_host_slot_id")),
            orbit_satellite_index=clamp_orbit_satellite_index(
                sat_index_raw, sat_count_raw),
            orbit_satellite_count=clamp_orbit_satellite_count(sat_count_raw),
            hotkey_bindings=layer_hotkey_bindings_from_list(data.get("hotkey_bindings")),
        )


@dataclass
class BasicLayersState:
    layer_mode: str = LAYER_MODE_BASIC
    layers: list[BasicLayerSlot] = field(default_factory=list)
    selected_slot_id: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.layers:
            self.layers = [default_layer_slot(i) for i in range(DEFAULT_LAYER_COUNT)]

    @property
    def character_stack_position(self) -> int:
        """Stack index (bottom = 0) where the character sits: above every
        'behind' layer and below every 'front' layer. Dynamic with layer count."""
        return sum(1 for layer in self.layers if layer.occlusion == OCCLUSION_BEHIND)

    @property
    def total_stack_positions(self) -> int:
        """Bottom-to-top draw slots: every layer plus the character sentinel."""
        return len(self.layers) + 1

    def next_slot_id(self) -> int:
        """Stable, never-reused id for a newly added layer (id != stack pos)."""
        return max((layer.slot_id for layer in self.layers), default=-1) + 1

    def add_layer(self) -> BasicLayerSlot:
        """Append a fresh empty layer on TOP of the stack (in front of character)."""
        slot_id = self.next_slot_id()
        top_z = max((layer.z_order for layer in self.layers), default=-1)
        layer = default_layer_slot(slot_id)
        layer.z_order = top_z + 1
        layer.occlusion = OCCLUSION_FRONT
        self.layers.append(layer)
        normalize_layer_stack_positions(self)
        return layer

    def remove_layer(self, slot_id: int) -> bool:
        """Delete an entire layer slot (not just its asset)."""
        before = len(self.layers)
        self.layers = [layer for layer in self.layers if layer.slot_id != slot_id]
        if len(self.layers) == before:
            return False
        if self.selected_slot_id == slot_id:
            self.selected_slot_id = None
        cleanup_layer_references(self, slot_id)
        normalize_layer_stack_positions(self)
        return True

    def get_slot(self, slot_id: int) -> BasicLayerSlot:
        for layer in self.layers:
            if layer.slot_id == slot_id:
                return layer
        layer = default_layer_slot(slot_id)
        self.layers.append(layer)
        return layer

    def sorted_layers_for_draw(self, occlusion: str) -> list[BasicLayerSlot]:
        items = [
            layer for layer in self.layers
            if layer.enabled and layer.visible and layer.occlusion == occlusion and layer.asset_path
        ]
        return sorted(items, key=lambda layer: layer.z_order)

    def sorted_layers_for_ui(self) -> list[BasicLayerSlot]:
        return sorted(self.layers, key=lambda layer: layer.z_order, reverse=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "layer_mode": self.layer_mode,
            "layers": [layer.to_dict() for layer in self.layers],
            "selected_slot_id": self.selected_slot_id,
        }

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> BasicLayersState:
        if not isinstance(data, dict):
            return cls()
        layers_data = data.get("layers")
        layers: list[BasicLayerSlot] = []
        if isinstance(layers_data, list):
            for index, item in enumerate(layers_data):
                if isinstance(item, dict):
                    slot_id = int(item.get("slot_id", index))
                    layers.append(BasicLayerSlot.from_dict(item, slot_id))
        if not layers:
            for slot_id in range(DEFAULT_LAYER_COUNT):
                layers.append(default_layer_slot(slot_id))
        layer_mode = str(data.get("layer_mode", LAYER_MODE_BASIC))
        if layer_mode == LAYER_MODE_BASIC_LEGACY:
            layer_mode = LAYER_MODE_BASIC
        selected = data.get("selected_slot_id")
        selected_slot_id = int(selected) if selected is not None else None
        if selected_slot_id is not None and selected_slot_id < 0:
            selected_slot_id = None
        result = cls(layer_mode=layer_mode, layers=layers, selected_slot_id=selected_slot_id)
        normalize_layer_stack_positions(result)
        sanitize_layer_references(result)
        if selected_slot_id is not None and selected_slot_id not in {
                layer.slot_id for layer in result.layers}:
            result.selected_slot_id = None
        return result


# Seed-only: where the character sits in the DEFAULT layer stack (behind: 0,1;
# front: 3,4,5). The real character position is now dynamic
# (BasicLayersState.character_stack_position), so the stack length is variable
# and layers can be added / removed at runtime.
DEFAULT_CHARACTER_STACK_POS = 2


def default_stack_position_for_slot(slot_id: int) -> int:
    if slot_id < DEFAULT_CHARACTER_STACK_POS:
        return slot_id
    return slot_id + 1


def occlusion_for_stack_position(stack_pos: int) -> str:
    """Seed default only; runtime occlusion is owned by the layer + normalize."""
    return OCCLUSION_BEHIND if stack_pos < DEFAULT_CHARACTER_STACK_POS else OCCLUSION_FRONT


def layer_at_stack_position(state: BasicLayersState, stack_pos: int) -> Optional[BasicLayerSlot]:
    for layer in state.layers:
        if layer.z_order == stack_pos:
            return layer
    return None


def normalize_layer_stack_positions(state: BasicLayersState) -> None:
    """Pack layers into a contiguous bottom-to-top stack with the character in
    the middle: behind layers get 0..b-1, the character occupies index b, front
    layers get b+1..  Ordering inside each side follows the current z_order, so
    existing saves keep their look while any layer count is supported."""
    behind = sorted(
        (layer for layer in state.layers if layer.occlusion == OCCLUSION_BEHIND),
        key=lambda layer: layer.z_order)
    front = sorted(
        (layer for layer in state.layers if layer.occlusion == OCCLUSION_FRONT),
        key=lambda layer: layer.z_order)
    index = 0
    for layer in behind:
        layer.z_order = index
        index += 1
    index += 1  # character sentinel slot
    for layer in front:
        layer.z_order = index
        index += 1


def iter_ui_list_top_to_bottom(state: BasicLayersState):
    """UI list top-to-bottom (top = drawn last / front). Character row sits at
    the dynamic character_stack_position."""
    char_pos = state.character_stack_position
    for pos in range(state.total_stack_positions - 1, -1, -1):
        if pos == char_pos:
            yield ("character", None)
            continue
        layer = layer_at_stack_position(state, pos)
        if layer is not None:
            yield ("layer", layer.slot_id)


def visible_layer_slot_ids_top_to_bottom(state: BasicLayersState) -> list[int]:
    """Layer slot ids in UI list order (top/front first), excluding character."""
    return [
        slot_id
        for kind, slot_id in iter_ui_list_top_to_bottom(state)
        if kind == "layer" and slot_id is not None
    ]


def selection_contiguous_in_ui_list(
        state: BasicLayersState,
        slot_ids: set[int]) -> bool:
    """True when ``slot_ids`` form one contiguous run in the visible layer list."""
    if not slot_ids:
        return False
    visible = visible_layer_slot_ids_top_to_bottom(state)
    indices = sorted(
        i for i, sid in enumerate(visible) if sid in slot_ids)
    if len(indices) != len(slot_ids):
        return False
    return indices == list(range(indices[0], indices[-1] + 1))


def move_layers_z_order_block(
        state: BasicLayersState,
        slot_ids: set[int],
        delta: int) -> bool:
    """Move a contiguous layer block one stack step (+1 = toward front).

    Preserves relative order inside the block. Returns False when the block is
    not contiguous in the UI list or the move is blocked at a stack edge.
    """
    if delta not in (-1, 1) or not slot_ids:
        return False
    if not selection_contiguous_in_ui_list(state, slot_ids):
        return False
    normalize_layer_stack_positions(state)
    total = state.total_stack_positions
    char_pos = state.character_stack_position
    sequence: list[object] = [None] * total
    sequence[char_pos] = "__character__"
    for item in state.layers:
        if 0 <= item.z_order < total:
            sequence[item.z_order] = item
    indices = sorted(
        i for i, item in enumerate(sequence)
        if isinstance(item, BasicLayerSlot) and item.slot_id in slot_ids)
    if not indices or indices != list(range(indices[0], indices[-1] + 1)):
        return False
    start, end = indices[0], indices[-1]
    block = sequence[start:end + 1]
    if delta > 0:
        if end + 1 >= total:
            return False
        new_sequence = (
            sequence[:start]
            + [sequence[end + 1]]
            + block
            + sequence[end + 2:])
    else:
        if start - 1 < 0:
            return False
        new_sequence = (
            sequence[:start - 1]
            + block
            + [sequence[start - 1]]
            + sequence[end + 1:])
    new_char_pos = new_sequence.index("__character__")
    for pos, item in enumerate(new_sequence):
        if item == "__character__" or item is None:
            continue
        item.z_order = pos
        item.occlusion = OCCLUSION_BEHIND if pos < new_char_pos else OCCLUSION_FRONT
    return True


def remove_layers_batch(state: BasicLayersState, slot_ids: set[int]) -> int:
    """Remove many layers; returns count removed."""
    removed = 0
    for slot_id in sorted(slot_ids, reverse=True):
        if state.remove_layer(slot_id):
            removed += 1
    return removed


def stack_position_can_move_up(state: BasicLayersState, stack_pos: int) -> bool:
    return stack_pos < state.total_stack_positions - 1


def stack_position_can_move_down(state: BasicLayersState, stack_pos: int) -> bool:
    return stack_pos > 0


def default_swing_phase_rad(slot_id: int) -> float:
    return float(slot_id) * 1.1


def normalize_motion_mode(value: Optional[str]) -> str:
    if value == MOTION_MODE_SIMPLE_SWING:
        return MOTION_MODE_SIMPLE_SWING
    if value == MOTION_MODE_CIRCULAR:
        return MOTION_MODE_CIRCULAR
    if value == MOTION_MODE_ORBIT_SATELLITE:
        return MOTION_MODE_CIRCULAR
    return MOTION_MODE_NONE


def clamp_orbit_satellite_count(value: int) -> int:
    return max(
        ORBIT_SATELLITE_COUNT_MIN,
        min(ORBIT_SATELLITE_COUNT_MAX, int(value)))


def clamp_orbit_satellite_index(index: int, count: int) -> int:
    count = clamp_orbit_satellite_count(count)
    index = int(index)
    return max(1, min(count - 1, index))


def orbit_host_slot_is_allowed(
        state: BasicLayersState,
        owner_slot_id: int,
        host_slot_id: Optional[int]) -> bool:
    if host_slot_id is None:
        return False
    if int(host_slot_id) == int(owner_slot_id):
        return False
    host = find_layer_slot(state, int(host_slot_id))
    if host is None:
        return False
    if host.motion_mode != MOTION_MODE_CIRCULAR:
        return False
    if layer_orbits_with_host(host):
        return False
    return orbit_host_has_satellite_capacity(state, int(host_slot_id), int(owner_slot_id))


def normalize_orbit_host_slot_id(
        state: BasicLayersState,
        owner_slot_id: int,
        host_slot_id: Optional[int]) -> Optional[int]:
    if host_slot_id is None:
        return None
    if orbit_host_slot_is_allowed(state, owner_slot_id, int(host_slot_id)):
        return int(host_slot_id)
    return None


def resolve_orbit_host_layer(
        state: BasicLayersState,
        layer: BasicLayerSlot) -> Optional[BasicLayerSlot]:
    """Resolve a follower's circular-orbit host layer.

    Central gate for orbit-follow: motion, edit chrome, save sync, and UI labels
    all depend on this predicate chain. Change with care — run smoke_layer_runtime
    and manual host/follower edits before merging.
    """
    if not layer_orbits_with_host(layer):
        return None
    host_id = layer.orbit_host_slot_id
    if host_id is None:
        return None
    host = find_layer_slot(state, int(host_id))
    if host is None or host.motion_mode != MOTION_MODE_CIRCULAR:
        return None
    if layer_orbits_with_host(host):
        return None
    return host


def resolve_orbit_track_layer(
        state: BasicLayersState,
        layer: BasicLayerSlot) -> BasicLayerSlot:
    """Orbit path used for motion + edit chrome (host track when following)."""
    host = resolve_orbit_host_layer(state, layer)
    return host if host is not None else layer


def orbit_satellite_phase_offset_rad(index: int, count: int) -> float:
    count = clamp_orbit_satellite_count(count)
    index = clamp_orbit_satellite_index(index, count)
    return 2.0 * math.pi * float(index) / float(count)


def circular_orbit_host_slot_ids(state: BasicLayersState) -> list[int]:
    return [
        layer.slot_id
        for layer in state.layers
        if layer.motion_mode == MOTION_MODE_CIRCULAR
        and not layer_orbits_with_host(layer)]


def layer_orbits_with_host(layer: BasicLayerSlot) -> bool:
    """Circular motion locked to another layer's orbit (own aux stack)."""
    return (
        layer.motion_mode == MOTION_MODE_CIRCULAR
        and layer.orbit_host_slot_id is not None)


def layer_joins_shared_orbit_track(layer: BasicLayerSlot) -> bool:
    return layer_orbits_with_host(layer)


def layer_registers_own_hotkeys(layer: BasicLayerSlot) -> bool:
    return True


def orbit_satellite_member_slot_ids(
        state: BasicLayersState,
        host_slot_id: int) -> list[int]:
    host_id = int(host_slot_id)
    return [
        layer.slot_id
        for layer in state.layers
        if layer_orbits_with_host(layer)
        and layer.orbit_host_slot_id == host_id
        and resolve_orbit_host_layer(state, layer) is not None]


def orbit_host_satellite_count(
        state: BasicLayersState,
        host_slot_id: int,
        *,
        exclude_owner_slot_id: Optional[int] = None) -> int:
    members = orbit_satellite_member_slot_ids(state, host_slot_id)
    if exclude_owner_slot_id is None:
        return len(members)
    return sum(1 for sid in members if sid != int(exclude_owner_slot_id))


def orbit_host_has_satellite_capacity(
        state: BasicLayersState,
        host_slot_id: int,
        owner_slot_id: int) -> bool:
    members = orbit_satellite_member_slot_ids(state, int(host_slot_id))
    owner = int(owner_slot_id)
    if owner in members:
        return True
    return len(members) < MAX_ORBIT_SATELLITES_PER_HOST


def layer_hotkey_action_target_slot_ids(
        state: BasicLayersState,
        slot_id: int) -> list[int]:
    try:
        layer = state.get_slot(slot_id)
    except KeyError:
        return []
    targets = [int(slot_id)]
    return targets


def clamp_orbit_radius(value: float) -> float:
    return max(ORBIT_RADIUS_MIN, min(ORBIT_RADIUS_MAX, float(value)))


def clamp_orbit_plane_tilt_deg(value: float) -> float:
    return max(ORBIT_PLANE_TILT_MIN_DEG, min(ORBIT_PLANE_TILT_MAX_DEG, float(value)))


def clamp_orbit_speed_deg_per_sec(value: float) -> float:
    return max(ORBIT_SPEED_MIN_DEG_PER_SEC, min(ORBIT_SPEED_MAX_DEG_PER_SEC, float(value)))


def clamp_orbit_scale(value: float) -> float:
    return max(ORBIT_SCALE_MIN, min(ORBIT_SCALE_MAX, float(value)))


def normalize_swing_speed_profile(value: Optional[str]) -> str:
    if value == SWING_SPEED_PROFILE_CONSTANT:
        return SWING_SPEED_PROFILE_CONSTANT
    return SWING_SPEED_PROFILE_EASE_ENDS


def clamp_swing_pivot_u(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def clamp_swing_pivot_v(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def clamp_swing_amplitude_deg(value: float) -> float:
    return max(SWING_AMPLITUDE_MIN_DEG, min(SWING_AMPLITUDE_MAX_DEG, float(value)))


def clamp_swing_speed_deg_per_sec(value: float) -> float:
    return max(SWING_SPEED_MIN_DEG_PER_SEC, min(SWING_SPEED_MAX_DEG_PER_SEC, float(value)))


def layer_has_active_swing(layer: BasicLayerSlot) -> bool:
    return (
        layer.enabled
        and layer.visible
        and bool(layer.asset_path)
        and layer.motion_mode == MOTION_MODE_SIMPLE_SWING
        and layer.swing_amplitude_deg > SWING_MIN_AMPLITUDE_EPS
        and layer.swing_speed_deg_per_sec > SWING_MIN_AMPLITUDE_EPS)


def layer_has_active_gif_playback(layer: BasicLayerSlot) -> bool:
    if not layer.enabled:
        return False
    if classify_layer_asset_kind(layer.asset_path or "") != "gif":
        return False
    mode = normalize_gif_playback_mode(layer.gif_playback_mode)
    if mode == GIF_PLAYBACK_LOOP:
        return layer.visible
    if mode == GIF_PLAYBACK_PLAY_ONCE:
        return layer.visible
    return False


def consume_layer_gif_playback_visibility_dirty(state: BasicLayersState) -> bool:
    changed = False
    for layer in state.layers:
        if layer._gif_playback_visibility_dirty:
            layer._gif_playback_visibility_dirty = False
            changed = True
    return changed


def basic_layers_state_has_active_motion(state: BasicLayersState) -> bool:
    return any(
        layer_has_active_swing(layer)
        or layer_has_active_orbit(layer, state)
        or layer_has_active_gif_playback(layer)
        for layer in state.layers)


def compute_swing_angle_deg(layer: BasicLayerSlot, time_s: float) -> float:
    if layer.motion_mode != MOTION_MODE_SIMPLE_SWING:
        return 0.0
    if float(layer.swing_amplitude_deg) <= SWING_MIN_AMPLITUDE_EPS:
        return 0.0
    if float(layer.swing_speed_deg_per_sec) <= SWING_MIN_AMPLITUDE_EPS:
        return 0.0
    amplitude = clamp_swing_amplitude_deg(layer.swing_amplitude_deg)
    speed = clamp_swing_speed_deg_per_sec(layer.swing_speed_deg_per_sec)
    phase = float(layer.swing_phase_rad)
    t = float(time_s)
    if layer.swing_speed_profile == SWING_SPEED_PROFILE_CONSTANT:
        span = 4.0 * amplitude
        phase_dist = (phase / (2.0 * math.pi)) * span
        s = (speed * t + phase_dist) % span
        if s < 2.0 * amplitude:
            return -amplitude + s
        return amplitude - (s - 2.0 * amplitude)
    omega = speed / amplitude
    return amplitude * math.sin(omega * t + phase)


@dataclass
class OrbitState:
    """Projected state of a circular-orbit object for one frame.

    offset_x / offset_y are screen offsets (in LAYER_COORD_SIZE = 512 space) from
    the orbit pivot; scale is the near/far perspective factor; depth_norm in
    [-1, 1] (1 = nearest / fully in front, -1 = farthest / fully behind);
    in_front = drawn in front of the character this frame.
    """
    offset_x: float = 0.0
    offset_y: float = 0.0
    scale: float = 1.0
    depth_norm: float = 0.0
    in_front: bool = True


def compute_orbit_state(
        layer: BasicLayerSlot,
        time_s: float,
        *,
        extra_phase_rad: float = 0.0) -> OrbitState:
    """Evaluate the tilted-plane circular orbit and project it to the screen."""
    radius = clamp_orbit_radius(layer.orbit_radius)
    if radius <= ORBIT_MIN_RADIUS_EPS:
        return OrbitState(scale=1.0, depth_norm=0.0, in_front=True)
    speed = clamp_orbit_speed_deg_per_sec(layer.orbit_speed_deg_per_sec)
    tilt = math.radians(clamp_orbit_plane_tilt_deg(layer.orbit_plane_tilt_deg))
    angle = (
        math.radians(speed * float(time_s))
        + float(layer.orbit_phase_rad)
        + float(extra_phase_rad))
    cos_t = math.cos(angle)
    sin_t = math.sin(angle)
    offset_x = radius * cos_t
    offset_y = -radius * sin_t * math.sin(tilt)
    depth_norm = sin_t * math.cos(tilt)  # in [-1, 1]
    near = clamp_orbit_scale(layer.orbit_near_scale)
    far = clamp_orbit_scale(layer.orbit_far_scale)
    blend = (depth_norm + 1.0) / 2.0  # 0 = far, 1 = near
    scale = far + (near - far) * blend
    return OrbitState(
        offset_x=offset_x,
        offset_y=offset_y,
        scale=scale,
        depth_norm=depth_norm,
        in_front=depth_norm >= 0.0)


def sync_orbit_follow_kinematics_from_host(
        layer: BasicLayerSlot,
        host: BasicLayerSlot,
        time_s: float) -> None:
    """Copy host track params; set follower phase = host phase + ring offset."""
    layer.orbit_radius = host.orbit_radius
    layer.orbit_plane_tilt_deg = host.orbit_plane_tilt_deg
    layer.orbit_speed_deg_per_sec = host.orbit_speed_deg_per_sec
    offset = orbit_satellite_phase_offset_rad(
        layer.orbit_satellite_index, layer.orbit_satellite_count)
    layer.orbit_phase_rad = float(host.orbit_phase_rad) + float(offset)
    layer.orbit_follow_last_sync_time_s = float(time_s)


def maybe_sync_orbit_follow_from_host(
        layer: BasicLayerSlot,
        host: BasicLayerSlot,
        time_s: float) -> None:
    last = float(layer.orbit_follow_last_sync_time_s)
    if (
            last < 0.0
            or time_s - last >= ORBIT_HOST_SYNC_INTERVAL_S):
        sync_orbit_follow_kinematics_from_host(layer, host, time_s)


def compute_orbit_motion_state(
        layer: BasicLayerSlot,
        state: BasicLayersState,
        time_s: float) -> OrbitState:
    """Circular orbit for one layer; followers mirror host track + own near/far scale."""
    host = resolve_orbit_host_layer(state, layer)
    if host is None:
        return compute_orbit_state(layer, time_s)
    maybe_sync_orbit_follow_from_host(layer, host, time_s)
    offset = orbit_satellite_phase_offset_rad(
        layer.orbit_satellite_index, layer.orbit_satellite_count)
    radius = clamp_orbit_radius(host.orbit_radius)
    if radius <= ORBIT_MIN_RADIUS_EPS:
        return OrbitState(scale=1.0, depth_norm=0.0, in_front=True)
    speed = clamp_orbit_speed_deg_per_sec(host.orbit_speed_deg_per_sec)
    tilt = math.radians(clamp_orbit_plane_tilt_deg(host.orbit_plane_tilt_deg))
    angle = (
        math.radians(speed * float(time_s))
        + float(host.orbit_phase_rad)
        + float(offset))
    cos_t = math.cos(angle)
    sin_t = math.sin(angle)
    offset_x = radius * cos_t
    offset_y = -radius * sin_t * math.sin(tilt)
    depth_norm = sin_t * math.cos(tilt)
    near = clamp_orbit_scale(layer.orbit_near_scale)
    far = clamp_orbit_scale(layer.orbit_far_scale)
    blend = (depth_norm + 1.0) / 2.0
    scale = far + (near - far) * blend
    return OrbitState(
        offset_x=offset_x,
        offset_y=offset_y,
        scale=scale,
        depth_norm=depth_norm,
        in_front=depth_norm >= 0.0)


def layer_has_active_orbit(
        layer: BasicLayerSlot,
        state: Optional[BasicLayersState] = None) -> bool:
    if not (
            layer.enabled
            and layer.visible
            and bool(layer.asset_path)
            and layer.motion_mode == MOTION_MODE_CIRCULAR):
        return False
    if layer_orbits_with_host(layer):
        if state is None:
            return True
        host = resolve_orbit_host_layer(state, layer)
        if host is None:
            return False
        return layer_has_active_orbit(host, state)
    return (
        clamp_orbit_radius(layer.orbit_radius) > ORBIT_MIN_RADIUS_EPS
        and clamp_orbit_speed_deg_per_sec(layer.orbit_speed_deg_per_sec)
        > ORBIT_MIN_RADIUS_EPS)


def default_layer_slot(slot_id: int) -> BasicLayerSlot:
    stack_pos = default_stack_position_for_slot(slot_id)
    return BasicLayerSlot(
        slot_id=slot_id,
        z_order=stack_pos,
        occlusion=occlusion_for_stack_position(stack_pos),
        swing_phase_rad=default_swing_phase_rad(slot_id),
    )


@dataclass
class ResolvedLayerRect:
    slot_id: int
    draw_x: float
    draw_y: float
    draw_width: float
    draw_height: float
    smoothed_rotation_deg: Optional[float] = None


@dataclass
class BindingContext:
    canvas_width: int
    canvas_height: int
    display_offset_x: float = 0.0
    display_offset_y: float = 0.0
    display_scale: float = 1.0
    display_rotation_deg: float = 0.0
    head_anchor_ratio: float = HEAD_ANCHOR_RATIO
    neck_anchor_ratio: float = NECK_ANCHOR_RATIO_DEFAULT
    body_bind_ray_percent: float = BIND_RAY_PERCENT_DEFAULT
    head_bind_ray_percent: float = BIND_RAY_PERCENT_DEFAULT
    character_draw_height: float = float(LAYER_COORD_SIZE)
    pose_head_x: float = 0.0
    pose_head_y: float = 0.0
    pose_neck_z: float = 0.0
    body_tilt_opposite_to_head: bool = True
    body_bind_pos_follow_gain: float = BODY_BIND_LEAN_FOLLOW_GAIN
    body_bind_roll_follow_gain: float = BODY_BIND_LEAN_FOLLOW_GAIN
    force_full_layer_follow: bool = False
    binding_smoother: Optional["LayerBindingSmoother"] = field(
        default=None, compare=False, repr=False)
    motion_time_s: Optional[float] = None
    # Per-frame cache: ``apply_orbit_to_resolved`` and compositor share one plan.
    _orbit_plan_cache: Optional[tuple[dict[int, "_OrbitDrawPlan"], set[int]]] = field(
        default=None, compare=False, repr=False)
    _orbit_plan_cache_time_s: Optional[float] = field(
        default=None, compare=False, repr=False)

    @property
    def scale_x(self) -> float:
        return self.canvas_width / LAYER_COORD_SIZE

    @property
    def scale_y(self) -> float:
        return self.canvas_height / LAYER_COORD_SIZE

    def pose_head_layer_offset(
            self, *, extra_gain: bool = False) -> tuple[float, float]:
        """Mocap head pose offset in 512-normalized layer space (center origin)."""
        gain = HEAD_POSE_MOCAP_EXTRA_GAIN if extra_gain else 1.0
        offset_x = -float(self.pose_head_y) * HEAD_POSE_Y_LAYER_GAIN * gain
        offset_y = -float(self.pose_head_x) * HEAD_POSE_X_LAYER_GAIN * gain
        return offset_x, offset_y

    def pose_head_roll_deg(self, *, extra_gain: bool = False) -> float:
        gain = HEAD_POSE_MOCAP_EXTRA_GAIN if extra_gain else 1.0
        return float(self.pose_neck_z) * HEAD_NECK_Z_MAX_DEG * gain

    def _mocap_spine_tilt_deg(self, *, extra_mocap_angle: bool = False) -> float:
        gain = HEAD_POSE_MOCAP_EXTRA_GAIN if extra_mocap_angle else 1.0
        return (
            float(self.pose_head_x) * HEAD_RAY_POSE_X_DEG_GAIN * gain
            - float(self.pose_head_y) * HEAD_RAY_POSE_Y_DEG_GAIN * gain)

    def spine_lower_angle_deg(self, *, extra_mocap_angle: bool = False) -> float:
        """Segment 1 (bottom→neck): model/diagram body segment; may oppose head when configured."""
        tilt = self._mocap_spine_tilt_deg(extra_mocap_angle=extra_mocap_angle)
        display = float(self.display_rotation_deg)
        if self.body_tilt_opposite_to_head:
            return -display + tilt * LOWER_SPINE_MOCAP_SHARE
        return display + tilt * LOWER_SPINE_MOCAP_SHARE

    def spine_upper_angle_deg(self, *, extra_mocap_angle: bool = False) -> float:
        """Segment 2 (neck→head): follows display tilt; decoupled from lower when opposite."""
        tilt = self._mocap_spine_tilt_deg(extra_mocap_angle=extra_mocap_angle)
        if self.body_tilt_opposite_to_head:
            return float(self.display_rotation_deg) + tilt * (1.0 - LOWER_SPINE_MOCAP_SHARE)
        return self.spine_lower_angle_deg(
            extra_mocap_angle=extra_mocap_angle) + tilt * (1.0 - LOWER_SPINE_MOCAP_SHARE)

    def spine_ray_angle_deg(self, *, extra_mocap_angle: bool = False) -> float:
        """Full head-ray direction (upper segment); kept for compatibility."""
        return self.spine_upper_angle_deg(extra_mocap_angle=extra_mocap_angle)

    @staticmethod
    def spine_ray_unit_vector(angle_deg: float) -> tuple[float, float]:
        """Unit vector along spine segment; 0° = straight up (screen −Y)."""
        rad = math.radians(float(angle_deg))
        return math.sin(rad), -math.cos(rad)

    def _character_scaled_height_px(self) -> float:
        scale = max(0.1, self.display_scale)
        return self.character_draw_height * self.scale_y * scale

    def _resolved_spine_ratios(self) -> tuple[float, float]:
        neck_ratio = clamp_neck_anchor_ratio(self.neck_anchor_ratio)
        head_ratio = max(
            neck_ratio + HEAD_SEGMENT_MIN_RATIO,
            min(1.0, float(self.head_anchor_ratio)))
        return neck_ratio, head_ratio

    def character_segment_lengths_px(self) -> tuple[float, float]:
        """Return (lower_segment_len, upper_segment_len) in canvas pixels."""
        char_h = self._character_scaled_height_px()
        neck_ratio, head_ratio = self._resolved_spine_ratios()
        lower_len = neck_ratio * char_h
        upper_len = (head_ratio - neck_ratio) * char_h
        return lower_len, upper_len

    def character_neck_on_lower_spine(
            self,
            *,
            extra_pose_offset: bool = False) -> tuple[float, float, float]:
        """Neck joint at end of segment 1; returns (neck_x, neck_y, lower_angle_deg)."""
        feet_x, feet_y = self.character_feet_anchor()
        lower_angle = self.spine_lower_angle_deg(extra_mocap_angle=extra_pose_offset)
        ux, uy = self.spine_ray_unit_vector(lower_angle)
        lower_len, _ = self.character_segment_lengths_px()
        return feet_x + ux * lower_len, feet_y + uy * lower_len, lower_angle

    def dynamic_enhancement_tilt_deg(
            self,
            *,
            lean_gain: Optional[float] = None,
            extra_mocap_angle: bool = False) -> float:
        """On-screen torso roll the body layer-bind (anchor ray AND sprite
        rotation) follows, so a body-pinned layer stays glued to the BLACK-BOX
        image-source torso in BOTH auto-transform ON and OFF.

        Pipeline truth: the THA keyframe already carries the model's own body_z
        roll, then compose_character_rgba_from_keyframe warp-rotates the whole
        image by +display_rotation_deg (dynamic enhancement). Layers composite
        in canvas space AFTER that warp, so:
            screen torso roll = +display_rotation_deg          (whole-image rot)
                              + model body roll (black-box source self-tilt)
        body_z = -neck_z when body_tilt_opposite_to_head (body leans opposite the
        head, matching apply_body_head_tilt_opposite_to_pose), else +neck_z;
        magnitude HEAD_NECK_Z_MAX_DEG (converter neck/body_z clamp), scaled by
        `lean_gain` (user-tunable; caller passes the POSITION gain for the anchor
        swing or the ROLL gain for the sprite, default BODY_BIND_LEAN_FOLLOW_GAIN
        when None). Auto-transform OFF (display=0) reduces to the model body roll,
        so the bind keeps tracking the black-box tilt instead of freezing. Because
        the anchor sits dist px out along the ray, the gain on the position path
        is the displacement knob: lower it to tame the large layer shift from tiny
        leans, independently of how much the sprite itself rotates. Position move/
        scale are handled separately by character_bottom_anchor (display_offset)
        and character_segment_lengths_px (display_scale)."""
        _ = extra_mocap_angle
        gain = (BODY_BIND_LEAN_FOLLOW_GAIN if lean_gain is None
                else clamp_body_bind_lean_follow_gain(lean_gain))
        display = float(self.display_rotation_deg)
        body_z = (-float(self.pose_neck_z)
                  if self.body_tilt_opposite_to_head else float(self.pose_neck_z))
        body_roll = BODY_BIND_BLACKBOX_ROLL_SIGN * body_z * HEAD_NECK_Z_MAX_DEG
        return display + body_roll * gain

    def character_body_bind_on_spine(
            self,
            *,
            ray_percent: float = DEFAULT_LAYER_BINDING_RAY_PERCENT,
            extra_pose_offset: bool = False) -> tuple[float, float, float]:
        """Body-bind anchor on model lower spine ray (diagram / internal segment)."""
        bottom_x, bottom_y = self.character_bottom_anchor()
        lower_angle = self.spine_lower_angle_deg(extra_mocap_angle=extra_pose_offset)
        ux, uy = self.spine_ray_unit_vector(lower_angle)
        lower_len, _ = self.character_segment_lengths_px()
        dist = lower_len * bind_ray_percent_to_ratio(ray_percent)
        return bottom_x + ux * dist, bottom_y + uy * dist, lower_angle

    def character_body_layer_bind_on_spine(
            self,
            *,
            ray_percent: float = DEFAULT_LAYER_BINDING_RAY_PERCENT,
            extra_pose_offset: bool = False) -> tuple[float, float, float]:
        """Body-bind anchor for layer follow: dynamic enhancement direction, not model-opposite.

        Uses the POSITION lean gain so the anchor swing (the displacement that the
        long spine-ray dist amplifies) is tunable independently of sprite roll."""
        bottom_x, bottom_y = self.character_bottom_anchor()
        angle = self.dynamic_enhancement_tilt_deg(
            lean_gain=self.body_bind_pos_follow_gain,
            extra_mocap_angle=extra_pose_offset)
        ux, uy = self.spine_ray_unit_vector(angle)
        lower_len, _ = self.character_segment_lengths_px()
        dist = lower_len * bind_ray_percent_to_ratio(ray_percent)
        return bottom_x + ux * dist, bottom_y + uy * dist, angle

    def character_head_bind_on_spine(
            self,
            *,
            ray_percent: float = DEFAULT_LAYER_BINDING_RAY_PERCENT,
            extra_pose_offset: bool = False) -> tuple[float, float, float]:
        """Head-bind anchor on upper spine ray (unbounded % of segment length)."""
        neck_x, neck_y, _ = self.character_neck_on_lower_spine(
            extra_pose_offset=extra_pose_offset)
        upper_angle = self.spine_upper_angle_deg(extra_mocap_angle=extra_pose_offset)
        ux, uy = self.spine_ray_unit_vector(upper_angle)
        _, upper_len = self.character_segment_lengths_px()
        ratio = bind_ray_percent_to_ratio(ray_percent)
        bind_x = neck_x + ux * upper_len * ratio
        bind_y = neck_y + uy * upper_len * ratio
        if extra_pose_offset:
            scale = max(0.1, self.display_scale)
            pose_lx, pose_ly = self.pose_head_layer_offset(extra_gain=True)
            pose_px = pose_lx * scale * self.scale_x
            pose_py = pose_ly * scale * self.scale_y
            rad = math.radians(upper_angle)
            cos_r = math.cos(rad)
            sin_r = math.sin(rad)
            bind_x += pose_px * cos_r - pose_py * sin_r
            bind_y += pose_px * sin_r + pose_py * cos_r
        return bind_x, bind_y, upper_angle

    def character_body_bind_reference_on_spine(
            self,
            *,
            extra_pose_offset: bool = False) -> tuple[float, float, float]:
        return self.character_body_bind_on_spine(
            ray_percent=self.body_bind_ray_percent,
            extra_pose_offset=extra_pose_offset)

    def character_head_bind_reference_on_spine(
            self,
            *,
            extra_pose_offset: bool = False) -> tuple[float, float, float]:
        return self.character_head_bind_on_spine(
            ray_percent=self.head_bind_ray_percent,
            extra_pose_offset=extra_pose_offset)

    def head_spine_distance_px(self) -> float:
        neck_ratio, head_ratio = self._resolved_spine_ratios()
        return head_ratio * self._character_scaled_height_px()

    def character_head_on_spine_ray(
            self,
            *,
            extra_pose_offset: bool = False) -> tuple[float, float, float]:
        """Head joint at end of segment 2 (for geometry); returns (head_x, head_y, upper_angle_deg)."""
        neck_x, neck_y, _ = self.character_neck_on_lower_spine(
            extra_pose_offset=extra_pose_offset)
        upper_angle = self.spine_upper_angle_deg(extra_mocap_angle=extra_pose_offset)
        ux, uy = self.spine_ray_unit_vector(upper_angle)
        _, upper_len = self.character_segment_lengths_px()
        head_x = neck_x + ux * upper_len
        head_y = neck_y + uy * upper_len
        return head_x, head_y, upper_angle

    def head_binding_rotation_deg(self, *, extra_pose_roll: bool = False) -> float:
        """Sprite roll on head bind: upper spine angle (already carries the
        left-right lean) + neck-z head roll scaled by HEAD_BIND_LEAN_FOLLOW_GAIN
        so a head-pinned sprite stays glued to head tilt."""
        return self.spine_upper_angle_deg() + self.pose_head_roll_deg(
            extra_gain=extra_pose_roll) * HEAD_BIND_LEAN_FOLLOW_GAIN

    def body_binding_rotation_deg(self) -> float:
        """Sprite roll for body bind: uses the ROLL lean gain, independent of the
        position swing gain."""
        return self.dynamic_enhancement_tilt_deg(
            lean_gain=self.body_bind_roll_follow_gain)

    def character_feet_anchor(self) -> tuple[float, float]:
        """Canvas anchor at character stack bottom-center (output frame bottom)."""
        return (
            self.canvas_width / 2.0 + self.display_offset_x,
            self.canvas_height + self.display_offset_y,
        )

    def character_bottom_anchor(self) -> tuple[float, float]:
        return self.character_feet_anchor()

    def character_head_anchor(self) -> tuple[float, float]:
        head_x, head_y, _ = self.character_head_on_spine_ray()
        return head_x, head_y


@dataclass
class SpineBindingMarker:
    """Binding reference or bound layer position projected onto a spine segment."""
    marker_kind: str
    segment: int
    t: float
    height_ratio: float
    slot_id: Optional[int] = None
    selected: bool = False
    canvas_x: Optional[float] = None
    canvas_y: Optional[float] = None


@dataclass
class SpineDiagramLayout:
    scale: float
    ref_x: float
    ref_y: float
    center_x: float
    center_y: float
    left_x: int


def build_spine_diagram_points(binding_context: BindingContext) -> dict[str, tuple[float, float]]:
    """Live spine joints in output canvas space (same as layer binding resolver)."""
    bottom_x, bottom_y = binding_context.character_bottom_anchor()
    neck_x, neck_y, lower_angle = binding_context.character_neck_on_lower_spine()
    head_x, head_y, upper_angle = binding_context.character_head_on_spine_ray()
    body_x, body_y, _ = binding_context.character_body_bind_reference_on_spine()
    head_bind_x, head_bind_y, _ = binding_context.character_head_bind_reference_on_spine()
    lower_len, upper_len = binding_context.character_segment_lengths_px()
    lower_ux, lower_uy = binding_context.spine_ray_unit_vector(lower_angle)
    upper_ux, upper_uy = binding_context.spine_ray_unit_vector(upper_angle)
    ext = RAY_DIAGRAM_EXTENSION_RATIO
    return {
        "bottom": (bottom_x, bottom_y),
        "neck": (neck_x, neck_y),
        "head": (head_x, head_y),
        "body_bind": (body_x, body_y),
        "head_bind": (head_bind_x, head_bind_y),
        "lower_ray_start": (
            bottom_x - lower_ux * lower_len * ext,
            bottom_y - lower_uy * lower_len * ext),
        "lower_ray_end": (
            neck_x + lower_ux * lower_len * ext,
            neck_y + lower_uy * lower_len * ext),
        "upper_ray_start": (
            neck_x - upper_ux * upper_len * ext,
            neck_y - upper_uy * upper_len * ext),
        "upper_ray_end": (
            head_x + upper_ux * upper_len * ext,
            head_y + upper_uy * upper_len * ext),
    }


def map_canvas_point_to_diagram(
        layout: SpineDiagramLayout,
        canvas_x: float,
        canvas_y: float) -> tuple[int, int]:
    return (
        int(round(layout.center_x + (canvas_x - layout.ref_x) * layout.scale)),
        int(round(layout.center_y + (canvas_y - layout.ref_y) * layout.scale)),
    )


def compute_spine_diagram_layout(
        points: dict[str, tuple[float, float]],
        width: int,
        height: int,
        *,
        pad_left: int = 52,
        pad_right: int = 52,
        pad_y: int = 14) -> tuple[SpineDiagramLayout, dict[str, tuple[int, int]]]:
    coords = list(points.values())
    xs = [p[0] for p in coords]
    ys = [p[1] for p in coords]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    bbox_w = max(24.0, max_x - min_x)
    bbox_h = max(24.0, max_y - min_y)
    avail_w = max(40.0, float(width) - pad_left - pad_right)
    avail_h = max(40.0, float(height) - pad_y * 2)
    scale = min(avail_w / bbox_w, avail_h / bbox_h) * 0.9
    layout = SpineDiagramLayout(
        scale=scale,
        ref_x=(min_x + max_x) / 2.0,
        ref_y=(min_y + max_y) / 2.0,
        center_x=pad_left + avail_w / 2.0,
        center_y=pad_y + avail_h / 2.0,
        left_x=4,
    )
    mapped = {
        key: map_canvas_point_to_diagram(layout, pt[0], pt[1])
        for key, pt in points.items()
    }
    return layout, mapped


def _project_point_on_segment(
        px: float,
        py: float,
        ax: float,
        ay: float,
        bx: float,
        by: float) -> tuple[float, float, float]:
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return ax, ay, 0.0
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    return ax + dx * t, ay + dy * t, t


def migrate_layer_bind_ray_percents(
        state: BasicLayersState,
        body_ref_percent: float,
        head_ref_percent: float) -> bool:
    """One-time fill for layers bound before per-layer ray % was persisted."""
    changed = False
    for layer in state.layers:
        if layer.binding_ray_percent is not None:
            continue
        target = normalize_binding_target(layer.binding_parent)
        if target == BINDING_CHARACTER_BODY:
            layer.binding_ray_percent = normalize_bind_ray_percent(body_ref_percent)
            changed = True
        elif target == BINDING_CHARACTER_HEAD:
            layer.binding_ray_percent = normalize_bind_ray_percent(head_ref_percent)
            changed = True
    return changed


def migrate_layer_bind_neck_ratios(
        state: BasicLayersState,
        neck_ref_ratio: float) -> bool:
    """One-time fill for layers bound before per-layer neck ratio was persisted."""
    ref = clamp_neck_anchor_ratio(neck_ref_ratio)
    changed = False
    for layer in state.layers:
        if layer.binding_neck_anchor_ratio is not None:
            continue
        target = normalize_binding_target(layer.binding_parent)
        if target in (BINDING_CHARACTER_BODY, BINDING_CHARACTER_HEAD):
            layer.binding_neck_anchor_ratio = ref
            changed = True
    return changed


def collect_spine_binding_markers(
        state: BasicLayersState,
        binding_context: BindingContext,
        asset_loader: Callable[[BasicLayerSlot], Optional[wx.Image]]) -> list[SpineBindingMarker]:
    """Collect body/head anchor and bound-layer positions along spine segments."""
    selected = state.selected_slot_id
    body_ref_pct = normalize_bind_ray_percent(binding_context.body_bind_ray_percent)
    head_ref_pct = normalize_bind_ray_percent(binding_context.head_bind_ray_percent)
    lower_len, upper_len = binding_context.character_segment_lengths_px()
    char_h = max(1.0, lower_len + upper_len)
    bottom_x, bottom_y = binding_context.character_bottom_anchor()
    neck_x, neck_y, _ = binding_context.character_neck_on_lower_spine()
    head_x, head_y, _ = binding_context.character_head_on_spine_ray()
    body_x, body_y, _ = binding_context.character_body_bind_reference_on_spine()
    head_bind_x, head_bind_y, _ = binding_context.character_head_bind_reference_on_spine()
    markers: list[SpineBindingMarker] = [
        SpineBindingMarker(
            "body_anchor", 1, bind_ray_percent_to_ratio(body_ref_pct),
            bind_ray_percent_to_ratio(body_ref_pct) * (lower_len / char_h),
            canvas_x=body_x, canvas_y=body_y),
        SpineBindingMarker(
            "head_anchor",
            2,
            bind_ray_percent_to_ratio(head_ref_pct),
            (lower_len + upper_len * bind_ray_percent_to_ratio(head_ref_pct)) / char_h,
            canvas_x=head_bind_x,
            canvas_y=head_bind_y),
    ]

    resolved = LayerGeometryResolver.resolve_all(
        state,
        asset_loader,
        binding_context.canvas_width,
        binding_context.canvas_height,
        binding_context)
    for layer in state.layers:
        if not layer.asset_path or not layer.visible:
            continue
        target = normalize_binding_target(layer.binding_parent)
        if target not in (BINDING_CHARACTER_BODY, BINDING_CHARACTER_HEAD):
            continue
        rect = resolved.get(layer.slot_id)
        if rect is None:
            continue
        cx = rect.draw_x + rect.draw_width / 2.0
        cy = rect.draw_y + rect.draw_height / 2.0
        is_selected = layer.slot_id == selected
        if target == BINDING_CHARACTER_BODY:
            _, _, t = _project_point_on_segment(
                cx, cy, bottom_x, bottom_y, neck_x, neck_y)
            height_ratio = (lower_len * t) / char_h
            markers.append(SpineBindingMarker(
                "body_layer", 1, t, height_ratio, layer.slot_id, is_selected,
                canvas_x=cx, canvas_y=cy))
        else:
            _, _, t = _project_point_on_segment(cx, cy, neck_x, neck_y, head_x, head_y)
            height_ratio = (lower_len + upper_len * t) / char_h
            markers.append(SpineBindingMarker(
                "head_layer", 2, t, height_ratio, layer.slot_id, is_selected,
                canvas_x=cx, canvas_y=cy))

    return markers


def _clean_transparent_rgb(image: wx.Image) -> wx.Image:
    """Zero RGB on fully transparent pixels to avoid green fringe when scaling."""
    if not image.HasAlpha():
        return image
    width, height = image.GetWidth(), image.GetHeight()
    for y in range(height):
        for x in range(width):
            if image.GetAlpha(x, y) == 0:
                image.SetRGB(x, y, 0, 0, 0)
    return image


def _pil_rgba_to_wx_image(rgba_image) -> wx.Image:
    width, height = rgba_image.size
    rgb_bytes = rgba_image.convert("RGB").tobytes()
    alpha_bytes = rgba_image.getchannel("A").tobytes()
    image = wx.Image(width, height)
    image.SetData(rgb_bytes)
    image.SetAlpha(alpha_bytes)
    return image


def _gif_pil_frame_to_rgba(frame, global_transparency: Optional[int] = None) -> Any:
    """Convert one GIF sub-frame to RGBA, honoring palette transparency index."""
    import PIL.Image
    if frame.mode in ("P", "PA"):
        if "transparency" not in frame.info and global_transparency is not None:
            frame = frame.copy()
            frame.info["transparency"] = global_transparency
        return frame.convert("RGBA")
    if frame.mode != "RGBA":
        return frame.convert("RGBA")
    return frame


def _gif_frame_disposal(frame) -> int:
    if hasattr(frame, "disposal_method"):
        return int(frame.disposal_method or 0)
    if "disposal" in frame.info:
        return int(frame.info["disposal"])
    return 0


def _gif_composite_frame_onto(
        canvas: Any,
        frame_rgba: Any,
        offset: tuple[int, int],
        full_size: tuple[int, int]) -> None:
    """Alpha-composite one GIF sub-frame onto the running canvas."""
    import PIL.Image
    if offset == (0, 0) and frame_rgba.size == full_size:
        result = PIL.Image.alpha_composite(canvas, frame_rgba)
    else:
        layer = PIL.Image.new("RGBA", full_size, (0, 0, 0, 0))
        layer.paste(frame_rgba, offset, frame_rgba.split()[3])
        result = PIL.Image.alpha_composite(canvas, layer)
    canvas.paste(result)


def _gif_frame_offset(frame, full_size: tuple[int, int]) -> tuple[int, int]:
    if frame.size == full_size:
        return (0, 0)
    try:
        return (int(frame.info.get("left", 0)), int(frame.info.get("top", 0)))
    except (TypeError, ValueError):
        return (0, 0)


def _load_gif_composited_frames(resolved: str) -> tuple[list[Any], list[int]]:
    """Composite animated GIF with disposal so cleared regions stay transparent."""
    import PIL.Image
    from PIL import ImageSequence

    with PIL.Image.open(resolved) as gif:
        full_size = gif.size
        global_transparency = gif.info.get("transparency")
        canvas = PIL.Image.new("RGBA", full_size, (0, 0, 0, 0))
        pil_frames: list[Any] = []
        durations_ms: list[int] = []
        default_duration = max(20, int(gif.info.get("duration", 100) or 100))

        for frame in ImageSequence.Iterator(gif):
            durations_ms.append(
                max(20, int(frame.info.get("duration", default_duration) or default_duration)))
            restore_before_draw = canvas.copy()
            frame_rgba = _gif_pil_frame_to_rgba(frame, global_transparency)
            offset = _gif_frame_offset(frame, full_size)
            _gif_composite_frame_onto(canvas, frame_rgba, offset, full_size)
            pil_frames.append(canvas.copy())

            disposal = _gif_frame_disposal(frame)
            if disposal == 2:
                canvas = PIL.Image.new("RGBA", full_size, (0, 0, 0, 0))
            elif disposal == 3:
                canvas = restore_before_draw.copy()

        if not pil_frames:
            raise ValueError(f"GIF has no frames: {resolved}")
        return pil_frames, durations_ms


@dataclass
class _GifAnimationSource:
    frames: list[wx.Image]
    durations_ms: list[int]
    total_ms: int
    preview: wx.Image

    @classmethod
    def load(cls, resolved: str) -> _GifAnimationSource:
        pil_frames, durations_ms = _load_gif_composited_frames(resolved)
        wx_frames = [
            _clean_transparent_rgb(_pil_rgba_to_wx_image(frame))
            for frame in pil_frames
        ]
        total_ms = max(1, sum(durations_ms))
        return cls(
            frames=wx_frames,
            durations_ms=durations_ms,
            total_ms=total_ms,
            preview=wx_frames[0])

    def frame_at_time(
            self,
            now: float,
            layer: BasicLayerSlot) -> wx.Image:
        frame_idx = resolve_gif_frame_index(
            layer,
            self.durations_ms,
            self.total_ms,
            len(self.frames),
            now)
        return self.frames[frame_idx]


def _pil_rgba_to_numpy(rgba_image) -> numpy.ndarray:
    """Decode a PIL image to sanitized straight-alpha RGBA (wx-free path)."""
    arr = numpy.ascontiguousarray(
        numpy.array(rgba_image.convert("RGBA"), dtype=numpy.uint8))
    return sanitize_transparent_rgb(arr)


@dataclass
class _GifNumpySource:
    """GIF frames decoded to numpy RGBA (parallel to _GifAnimationSource)."""

    frames: list[numpy.ndarray]
    durations_ms: list[int]
    total_ms: int

    @classmethod
    def load(cls, resolved: str) -> _GifNumpySource:
        pil_frames, durations_ms = _load_gif_composited_frames(resolved)
        frames = [_pil_rgba_to_numpy(frame) for frame in pil_frames]
        total_ms = max(1, sum(durations_ms))
        return cls(frames=frames, durations_ms=durations_ms, total_ms=total_ms)

    def frame_index(self, now: float, layer: BasicLayerSlot) -> int:
        return resolve_gif_frame_index(
            layer,
            self.durations_ms,
            self.total_ms,
            len(self.frames),
            now)


def scale_image_to_bitmap(image: wx.Image, draw_w: int, draw_h: int) -> wx.Bitmap:
    """Scale PNG to bitmap preserving alpha (avoids green halos from wx.Image.Scale)."""
    draw_w = max(1, int(round(draw_w)))
    draw_h = max(1, int(round(draw_h)))
    bmp = wx.Bitmap(draw_w, draw_h, 32)
    if hasattr(bmp, "UseAlpha"):
        bmp.UseAlpha()
    dc = wx.MemoryDC()
    dc.SelectObject(bmp)
    dc.SetBackground(wx.TRANSPARENT_BRUSH)
    dc.Clear()
    gc = wx.GraphicsContext.Create(dc)
    if gc is not None:
        src_bmp = image.ConvertToBitmap()
        gc.DrawBitmap(src_bmp, 0, 0, draw_w, draw_h)
    else:
        scaled = image.Scale(draw_w, draw_h, wx.IMAGE_QUALITY_NORMAL)
        dc.DrawBitmap(scaled.ConvertToBitmap(), 0, 0, True)
    dc.SelectObject(wx.NullBitmap)
    return bmp


class LayerGeometryResolver:
    """Map 512-space layer transforms to output canvas pixels."""

    @staticmethod
    def map_coord(value: float, canvas_size: int, coord_size: int = LAYER_COORD_SIZE) -> float:
        if coord_size <= 0:
            return value
        return value * (canvas_size / coord_size)

    @classmethod
    def resolve_layer_rect_local(
            cls,
            layer: BasicLayerSlot,
            layer_image: wx.Image,
            canvas_width: int,
            canvas_height: int) -> ResolvedLayerRect:
        scale_x = canvas_width / LAYER_COORD_SIZE
        scale_y = canvas_height / LAYER_COORD_SIZE
        layer_scale = max(0.05, layer.transform.scale)
        draw_width = max(1.0, layer_image.GetWidth() * layer_scale * scale_x)
        draw_height = max(1.0, layer_image.GetHeight() * layer_scale * scale_y)
        anchor_x = canvas_width / 2.0 + cls.map_coord(layer.transform.offset_x, canvas_width)
        anchor_y = canvas_height / 2.0 + cls.map_coord(layer.transform.offset_y, canvas_height)
        draw_x = anchor_x - draw_width / 2.0
        draw_y = anchor_y - draw_height / 2.0
        return ResolvedLayerRect(
            slot_id=layer.slot_id,
            draw_x=draw_x,
            draw_y=draw_y,
            draw_width=draw_width,
            draw_height=draw_height,
        )

    resolve_layer_rect = resolve_layer_rect_local

    @classmethod
    def _rect_center(cls, rect: ResolvedLayerRect) -> tuple[float, float]:
        return (
            rect.draw_x + rect.draw_width / 2.0,
            rect.draw_y + rect.draw_height / 2.0,
        )

    @classmethod
    def _rect_from_center(
            cls,
            slot_id: int,
            center_x: float,
            center_y: float,
            draw_width: float,
            draw_height: float) -> ResolvedLayerRect:
        return ResolvedLayerRect(
            slot_id=slot_id,
            draw_x=center_x - draw_width / 2.0,
            draw_y=center_y - draw_height / 2.0,
            draw_width=draw_width,
            draw_height=draw_height,
        )

    @classmethod
    def _apply_binding(
            cls,
            layer: BasicLayerSlot,
            local_rect: ResolvedLayerRect,
            resolved: dict[int, ResolvedLayerRect],
            binding_context: BindingContext) -> ResolvedLayerRect:
        target = normalize_binding_target(layer.binding_parent)
        if target is None:
            return local_rect

        canvas_width = binding_context.canvas_width
        canvas_height = binding_context.canvas_height
        local_cx, local_cy = cls._rect_center(local_rect)
        offset_x = local_cx - canvas_width / 2.0
        offset_y = local_cy - canvas_height / 2.0
        draw_width = local_rect.draw_width
        draw_height = local_rect.draw_height

        layer_ctx = replace(
            binding_context,
            neck_anchor_ratio=layer_binding_neck_anchor_ratio(layer))

        if target == BINDING_CHARACTER_BODY:
            scale = max(0.1, binding_context.display_scale)
            bind_x, bind_y, bind_angle = layer_ctx.character_body_layer_bind_on_spine(
                ray_percent=layer_binding_ray_percent(layer))
            rot_rad = math.radians(bind_angle)
            cos_r = math.cos(rot_rad)
            sin_r = math.sin(rot_rad)
            scaled_x = offset_x * scale
            scaled_y = offset_y * scale
            rot_x = scaled_x * cos_r - scaled_y * sin_r
            rot_y = scaled_x * sin_r + scaled_y * cos_r
            center_x = bind_x + rot_x
            center_y = bind_y + rot_y
            return cls._rect_from_center(
                layer.slot_id, center_x, center_y, draw_width * scale, draw_height * scale)

        if target == BINDING_CHARACTER_HEAD:
            extra = bool(layer.binding_follow_mocap_position)
            bind_x, bind_y, upper_angle = layer_ctx.character_head_bind_on_spine(
                ray_percent=layer_binding_ray_percent(layer),
                extra_pose_offset=extra)
            ray_rad = math.radians(upper_angle)
            cos_r = math.cos(ray_rad)
            sin_r = math.sin(ray_rad)
            scale = max(0.1, binding_context.display_scale)
            scaled_x = offset_x * scale
            scaled_y = offset_y * scale
            rot_x = scaled_x * cos_r - scaled_y * sin_r
            rot_y = scaled_x * sin_r + scaled_y * cos_r
            center_x = bind_x + rot_x
            center_y = bind_y + rot_y
            return cls._rect_from_center(
                layer.slot_id, center_x, center_y, draw_width, draw_height)

        parent_slot = parse_layer_binding_slot(target)
        if parent_slot is not None:
            parent_rect = resolved.get(parent_slot)
            if parent_rect is None:
                return local_rect
            parent_cx, parent_cy = cls._rect_center(parent_rect)
            center_x = parent_cx + offset_x
            center_y = parent_cy + offset_y
            return cls._rect_from_center(
                layer.slot_id, center_x, center_y, draw_width, draw_height)

        return local_rect

    @classmethod
    def resolve_all(
            cls,
            state: BasicLayersState,
            asset_loader: Callable[[BasicLayerSlot], Optional[wx.Image]],
            canvas_width: int,
            canvas_height: int,
            binding_context: Optional[BindingContext] = None) -> dict[int, ResolvedLayerRect]:
        if binding_context is None:
            binding_context = BindingContext(canvas_width=canvas_width, canvas_height=canvas_height)

        local_rects: dict[int, ResolvedLayerRect] = {}
        for layer in state.layers:
            if not layer.enabled or not layer.visible or not layer.asset_path:
                continue
            image = asset_loader(layer)
            if image is None:
                continue
            local_rects[layer.slot_id] = cls.resolve_layer_rect_local(
                layer, image, canvas_width, canvas_height)

        resolved: dict[int, ResolvedLayerRect] = {}
        character_pos = state.character_stack_position
        for pos in range(state.total_stack_positions):
            if pos == character_pos:
                continue
            layer = layer_at_stack_position(state, pos)
            if layer is None or layer.slot_id not in local_rects:
                continue
            local_rect = local_rects[layer.slot_id]
            resolved[layer.slot_id] = cls._apply_binding(
                layer, local_rect, resolved, binding_context)
        return resolved


@dataclass
class _SlotBindingSmoothState:
    center_x: float = 0.0
    center_y: float = 0.0
    rotation_deg: float = 0.0
    active: bool = False


class HeadBindingPoseFilter:
    """Low-pass + deadzone + per-frame step cap for head mocap used in layer binding."""

    def __init__(
            self,
            *,
            deadzone: float = HEAD_BINDING_POSE_DEADZONE,
            max_step: float = HEAD_BINDING_POSE_MAX_STEP) -> None:
        self._deadzone = max(0.0, float(deadzone))
        self._max_step = max(0.0, float(max_step))
        self._head_x = 0.0
        self._head_y = 0.0
        self._neck_z = 0.0
        self._active = False

    def reset(self) -> None:
        self._active = False

    def filter(self, head_x: float, head_y: float, neck_z: float) -> tuple[float, float, float]:
        if not self._active:
            self._head_x = float(head_x)
            self._head_y = float(head_y)
            self._neck_z = float(neck_z)
            self._active = True
            return self._head_x, self._head_y, self._neck_z
        self._head_x = self._filter_axis(self._head_x, float(head_x))
        self._head_y = self._filter_axis(self._head_y, float(head_y))
        self._neck_z = self._filter_axis(self._neck_z, float(neck_z))
        return self._head_x, self._head_y, self._neck_z

    def _filter_axis(self, current: float, target: float) -> float:
        delta = target - current
        if abs(delta) <= self._deadzone:
            return current
        return _rate_limit_scalar(current, target, self._max_step)


class LayerBindingSmoother:
    """Exponential smoothing for bound layer pose (reduces mocap jitter)."""

    def __init__(self, alpha: float = BINDING_SMOOTH_ALPHA) -> None:
        self._alpha = max(0.01, min(1.0, float(alpha)))
        self._slots: dict[int, _SlotBindingSmoothState] = {}

    def reset_slot(self, slot_id: int) -> None:
        self._slots.pop(int(slot_id), None)

    def reset_all(self) -> None:
        self._slots.clear()

    def apply(
            self,
            state: BasicLayersState,
            resolved: dict[int, ResolvedLayerRect],
            binding_context: BindingContext) -> dict[int, ResolvedLayerRect]:
        if not resolved:
            return resolved
        if binding_context.force_full_layer_follow:
            self.reset_all()
            return resolved
        result: dict[int, ResolvedLayerRect] = {}
        active_slots: set[int] = set()
        for slot_id, rect in resolved.items():
            layer = state.get_slot(slot_id)
            bind_target = normalize_binding_target(layer.binding_parent)
            if bind_target is None:
                self.reset_slot(slot_id)
                result[slot_id] = rect
                continue
            if not layer.binding_follow_smooth:
                self.reset_slot(slot_id)
                result[slot_id] = rect
                continue
            active_slots.add(slot_id)
            smooth = self._slots.setdefault(slot_id, _SlotBindingSmoothState())
            layer_alpha = binding_smooth_alpha_for_layer(layer)
            cx = rect.draw_x + rect.draw_width / 2.0
            cy = rect.draw_y + rect.draw_height / 2.0
            target_rotation = effective_layer_rotation_deg(layer, state, binding_context)
            # Position follows INSTANTLY (no EMA): the bind anchor already tracks
            # the upstream-smoothed display transform (and, with auto-transform
            # off, a now position-gain-tamed lean), so a second positional EMA
            # only added visible movement lag — the layer trailing behind the
            # character. Only ROTATION keeps the EMA, because the sprite roll is
            # driven by the raw mocap neck_z (never smoothed upstream) and is the
            # jittery signal this smoother exists to tame. Result: smooth follow
            # = jitter-free roll WITHOUT the translation lag.
            if not smooth.active:
                smooth.rotation_deg = target_rotation
                smooth.active = True
            else:
                smooth.rotation_deg = _lerp_angle_deg(
                    smooth.rotation_deg, target_rotation, layer_alpha)
            smooth.center_x = cx
            smooth.center_y = cy
            result[slot_id] = LayerGeometryResolver._rect_from_center(
                slot_id,
                cx,
                cy,
                rect.draw_width,
                rect.draw_height)
            result[slot_id].smoothed_rotation_deg = smooth.rotation_deg
        stale = [slot_id for slot_id in self._slots if slot_id not in active_slots]
        for slot_id in stale:
            self.reset_slot(slot_id)
        return result


@dataclass
class _OrbitDrawPlan:
    source_slot_id: int
    offset_x: float
    offset_y: float
    scale: float
    pivot_u: float
    pivot_v: float
    pivot_slot_id: Optional[int] = None


def orbit_aux_carriers(state: BasicLayersState) -> dict[int, int]:
    """Aux stack slots requisitioned for orbit occlusion (aux_id -> owner slot_id)."""
    carriers: dict[int, int] = {}
    live = {layer.slot_id for layer in state.layers}
    for layer in state.layers:
        if layer.motion_mode != MOTION_MODE_CIRCULAR:
            continue
        aux_id = layer.orbit_aux_slot_id
        if aux_id is None or aux_id == layer.slot_id or aux_id not in live:
            continue
        carriers[int(aux_id)] = layer.slot_id
    return carriers


def orbit_aux_owner(state: BasicLayersState, slot_id: int) -> Optional[int]:
    return orbit_aux_carriers(state).get(slot_id)


def orbit_requisitioned_slot_ids(state: BasicLayersState) -> set[int]:
    return set(orbit_aux_carriers(state))


def apply_orbit_requisition_visibility(state: BasicLayersState) -> None:
    """Lent stack slots hide their own sprite; only the orbit owner draws there."""
    for aux_id in orbit_requisitioned_slot_ids(state):
        aux = find_layer_slot(state, aux_id)
        if aux is not None:
            aux.visible = False


def strip_orbit_requisitioned_native_rects(
        state: BasicLayersState,
        resolved: dict[int, ResolvedLayerRect],
        active_display_slots: Optional[set[int]] = None) -> None:
    """Drop independent geometry for lent slots (keep orbit-display rects only)."""
    keep = active_display_slots or set()
    for aux_id in orbit_requisitioned_slot_ids(state):
        if aux_id not in keep:
            resolved.pop(aux_id, None)


def orbit_upper_lower_slot_ids(
        main: BasicLayerSlot,
        aux: BasicLayerSlot) -> tuple[int, int]:
    """Return (upper, lower) stack slots for front / behind orbit display."""
    if main.occlusion == OCCLUSION_FRONT and aux.occlusion == OCCLUSION_BEHIND:
        return main.slot_id, aux.slot_id
    if aux.occlusion == OCCLUSION_FRONT and main.occlusion == OCCLUSION_BEHIND:
        return aux.slot_id, main.slot_id
    if main.z_order >= aux.z_order:
        return main.slot_id, aux.slot_id
    return aux.slot_id, main.slot_id


def resolve_local_layer_rects(
        state: BasicLayersState,
        asset_loader: Callable[[BasicLayerSlot], Optional[wx.Image]],
        canvas_width: int,
        canvas_height: int) -> dict[int, ResolvedLayerRect]:
    """Unbound layer rects (transform only), keyed by slot_id."""
    local_rects: dict[int, ResolvedLayerRect] = {}
    requisitioned = orbit_requisitioned_slot_ids(state)
    for layer in state.layers:
        if layer.slot_id in requisitioned:
            continue
        if not layer.enabled or not layer.visible or not layer.asset_path:
            continue
        image = asset_loader(layer)
        if image is None:
            continue
        local_rects[layer.slot_id] = LayerGeometryResolver.resolve_layer_rect_local(
            layer, image, canvas_width, canvas_height)
    return local_rects


def orbit_binding_shift(
        bound_rect: ResolvedLayerRect,
        local_rect: ResolvedLayerRect) -> tuple[float, float]:
    """How far binding moved the layer center from its local transform anchor."""
    bound_cx = bound_rect.draw_x + bound_rect.draw_width / 2.0
    bound_cy = bound_rect.draw_y + bound_rect.draw_height / 2.0
    local_cx = local_rect.draw_x + local_rect.draw_width / 2.0
    local_cy = local_rect.draw_y + local_rect.draw_height / 2.0
    return bound_cx - local_cx, bound_cy - local_cy


def binding_context_for_layer_geometry(
        binding_context: Optional[BindingContext],
        *,
        include_motion: bool) -> Optional[BindingContext]:
    """Strip motion_time_s for edit chrome / hit-tests (static bound box)."""
    if binding_context is None or include_motion:
        return binding_context
    return replace(binding_context, motion_time_s=None)


def layer_uses_orbit_edit_chrome(layer: BasicLayerSlot) -> bool:
    return layer.motion_mode == MOTION_MODE_CIRCULAR and bool(layer.asset_path)


@dataclass
class OrbitEditGeometry:
    slot_id: int
    path_points: list[tuple[float, float]]
    pivot_xy: tuple[float, float]
    bind_xy: Optional[tuple[float, float]]
    canvas_width: int
    canvas_height: int


def sample_orbit_path_canvas_points(
        layer: BasicLayerSlot,
        canvas_width: int,
        canvas_height: int,
        shift_x: float = 0.0,
        shift_y: float = 0.0,
        *,
        state: Optional[BasicLayersState] = None,
        binding_context: Optional[BindingContext] = None,
        num_samples: int = 72) -> tuple[list[tuple[float, float]], tuple[float, float]]:
    canvas_width = max(1, int(canvas_width))
    canvas_height = max(1, int(canvas_height))
    pivot_x = (
        clamp_swing_pivot_u(layer.orbit_pivot_u) * float(canvas_width) + shift_x)
    pivot_y = (
        clamp_swing_pivot_v(layer.orbit_pivot_v) * float(canvas_height) + shift_y)
    sx = float(canvas_width) / float(LAYER_COORD_SIZE)
    sy = float(canvas_height) / float(LAYER_COORD_SIZE)
    radius = max(clamp_orbit_radius(layer.orbit_radius), 8.0)
    tilt = math.radians(clamp_orbit_plane_tilt_deg(layer.orbit_plane_tilt_deg))
    follow_rot = 0.0
    if state is not None and binding_context is not None:
        follow_rot = orbit_binding_follow_rotation_deg(layer, state, binding_context)
    points: list[tuple[float, float]] = []
    phase = float(layer.orbit_phase_rad)
    for index in range(max(8, int(num_samples))):
        angle = 2.0 * math.pi * (index / float(num_samples)) + phase
        cos_t = math.cos(angle)
        sin_t = math.sin(angle)
        offset_x = radius * cos_t * sx
        offset_y = -radius * sin_t * math.sin(tilt) * sy
        offset_x, offset_y = rotate_orbit_plane_offsets(
            offset_x, offset_y, follow_rot)
        points.append((pivot_x + offset_x, pivot_y + offset_y))
    return points, (pivot_x, pivot_y)


def layer_binding_anchor_canvas_xy(
        layer: BasicLayerSlot,
        state: BasicLayersState,
        binding_context: BindingContext,
        resolved: dict[int, ResolvedLayerRect],
        canvas_width: int,
        canvas_height: int) -> Optional[tuple[float, float]]:
    target = normalize_binding_target(layer.binding_parent)
    if target == BINDING_CHARACTER_BODY:
        bind_x, bind_y, _angle = binding_context.character_body_layer_bind_on_spine(
            ray_percent=layer_binding_ray_percent(layer))
        return float(bind_x), float(bind_y)
    if target == BINDING_CHARACTER_HEAD:
        bind_x, bind_y, _angle = binding_context.character_head_bind_on_spine(
            ray_percent=layer_binding_ray_percent(layer),
            extra_pose_offset=bool(layer.binding_follow_mocap_position))
        return float(bind_x), float(bind_y)
    parent_slot = parse_layer_binding_slot(target)
    if parent_slot is not None:
        parent_rect = resolved.get(parent_slot)
        if parent_rect is not None:
            return (
                parent_rect.draw_x + parent_rect.draw_width / 2.0,
                parent_rect.draw_y + parent_rect.draw_height / 2.0)
    anchor_x = canvas_width / 2.0 + LayerGeometryResolver.map_coord(
        layer.transform.offset_x, canvas_width)
    anchor_y = canvas_height / 2.0 + LayerGeometryResolver.map_coord(
        layer.transform.offset_y, canvas_height)
    return float(anchor_x), float(anchor_y)


def orbit_binding_shift_for_layer(
        state: BasicLayersState,
        layer: BasicLayerSlot,
        asset_loader: Callable[[BasicLayerSlot], Optional[wx.Image]],
        canvas_width: int,
        canvas_height: int,
        binding_context: BindingContext) -> tuple[float, float]:
    local_rects = resolve_local_layer_rects(
        state, asset_loader, canvas_width, canvas_height)
    local_rect = local_rects.get(layer.slot_id)
    if local_rect is None:
        return 0.0, 0.0
    geometry_context = binding_context_for_layer_geometry(
        binding_context, include_motion=False)
    resolved = LayerGeometryResolver.resolve_all(
        state, asset_loader, canvas_width, canvas_height, geometry_context)
    smoother = (
        geometry_context.binding_smoother if geometry_context is not None else None)
    if smoother is not None and geometry_context is not None:
        resolved = smoother.apply(state, resolved, geometry_context)
    bound_rect = resolved.get(layer.slot_id)
    if bound_rect is None:
        return 0.0, 0.0
    return orbit_binding_shift(bound_rect, local_rect)


def compute_orbit_edit_geometry(
        state: BasicLayersState,
        layer: BasicLayerSlot,
        asset_loader: Callable[[BasicLayerSlot], Optional[wx.Image]],
        canvas_width: int,
        canvas_height: int,
        binding_context: BindingContext) -> Optional[OrbitEditGeometry]:
    if not layer_uses_orbit_edit_chrome(layer):
        return None
    canvas_width = max(1, int(canvas_width))
    canvas_height = max(1, int(canvas_height))
    track_layer = resolve_orbit_track_layer(state, layer)
    shift_x, shift_y = orbit_binding_shift_for_layer(
        state, track_layer, asset_loader, canvas_width, canvas_height, binding_context)
    path_points, pivot_xy = sample_orbit_path_canvas_points(
        track_layer,
        canvas_width,
        canvas_height,
        shift_x,
        shift_y,
        state=state,
        binding_context=binding_context)
    geometry_context = binding_context_for_layer_geometry(
        binding_context, include_motion=False)
    resolved = LayerGeometryResolver.resolve_all(
        state, asset_loader, canvas_width, canvas_height, geometry_context)
    smoother = (
        geometry_context.binding_smoother if geometry_context is not None else None)
    if smoother is not None and geometry_context is not None:
        resolved = smoother.apply(state, resolved, geometry_context)
    bind_xy = layer_binding_anchor_canvas_xy(
        track_layer, state, binding_context, resolved, canvas_width, canvas_height)
    return OrbitEditGeometry(
        slot_id=layer.slot_id,
        path_points=path_points,
        pivot_xy=pivot_xy,
        bind_xy=bind_xy,
        canvas_width=canvas_width,
        canvas_height=canvas_height)


def resolve_stack_layer_draw(
        state: BasicLayersState,
        display_layer: BasicLayerSlot,
        resolved: dict[int, ResolvedLayerRect],
        orbit_plan: Optional[dict[int, _OrbitDrawPlan]],
        hidden_slots: set[int]) -> Optional[tuple[BasicLayerSlot, ResolvedLayerRect]]:
    """Map a stack slot to the layer asset + rect actually drawn this frame.

    Requisitioned stack slots never draw their own asset: only the orbit owner
    may appear there, and only on the depth-selected slot for this frame.
    """
    slot_id = display_layer.slot_id
    if slot_id in hidden_slots:
        return None

    owner_slot_id = orbit_aux_owner(state, slot_id)
    if owner_slot_id is not None:
        if orbit_plan is None:
            return None
        plan = orbit_plan.get(slot_id)
        if plan is None:
            return None
        source = find_layer_slot(state, plan.source_slot_id)
        if source is None or not source.asset_path or not source.visible:
            return None
        rect = resolved.get(slot_id)
        if rect is None:
            return None
        return source, rect

    if orbit_plan is not None and slot_id in orbit_plan:
        plan = orbit_plan[slot_id]
        source = find_layer_slot(state, plan.source_slot_id)
        if source is None or not source.asset_path or not source.visible:
            return None
        rect = resolved.get(slot_id)
        if rect is None:
            return None
        return source, rect

    if not display_layer.asset_path or not display_layer.visible:
        return None
    rect = resolved.get(slot_id)
    if rect is None:
        return None
    return display_layer, rect


def collect_stack_layer_draws(
        state: BasicLayersState,
        asset_loader: Callable[[BasicLayerSlot], Optional[wx.Image]],
        canvas_width: int,
        canvas_height: int,
        binding_context: Optional[BindingContext]) -> list[tuple[int, int]]:
    """Return (stack_slot_id, asset_owner_slot_id) drawn this frame."""
    resolved = resolve_layer_rects(
        state, asset_loader, canvas_width, canvas_height, binding_context)
    orbit_plan, hidden_slots = orbit_frame_plan(state, binding_context)
    draws: list[tuple[int, int]] = []
    character_pos = state.character_stack_position
    for pos in range(state.total_stack_positions):
        if pos == character_pos:
            continue
        layer = layer_at_stack_position(state, pos)
        if layer is None or not layer.enabled:
            continue
        draw_pair = resolve_stack_layer_draw(
            state, layer, resolved, orbit_plan, hidden_slots)
        if draw_pair is None:
            continue
        draw_layer, _rect = draw_pair
        draws.append((layer.slot_id, draw_layer.slot_id))
    return draws


def orbit_frame_plan(
        state: BasicLayersState,
        binding_context: Optional[BindingContext]) -> tuple[dict[int, _OrbitDrawPlan], set[int]]:
    if binding_context is None or binding_context.motion_time_s is None:
        return {}, set()
    time_s = float(binding_context.motion_time_s)
    cached_time = binding_context._orbit_plan_cache_time_s
    cached_plan = binding_context._orbit_plan_cache
    if cached_plan is not None and cached_time == time_s:
        return cached_plan
    plan = compute_orbit_render_plan(state, time_s)
    binding_context._orbit_plan_cache = plan
    binding_context._orbit_plan_cache_time_s = time_s
    return plan


def orbit_selection_slot_id(
        display_slot_id: int,
        orbit_plan: dict[int, _OrbitDrawPlan]) -> int:
    plan = orbit_plan.get(display_slot_id)
    if plan is not None:
        return plan.source_slot_id
    return display_slot_id


def assign_orbit_draw_plan(
        state: BasicLayersState,
        overrides: dict[int, _OrbitDrawPlan],
        hidden: set[int],
        plan: _OrbitDrawPlan,
        st: OrbitState,
        host: BasicLayerSlot) -> None:
    """Publish one orbit draw plan using the layer's own main/aux stack pair."""
    aux_id = host.orbit_aux_slot_id
    aux_layer = find_layer_slot(state, aux_id) if aux_id is not None else None
    if aux_layer is None or aux_id == host.slot_id:
        overrides[plan.source_slot_id] = plan
        return
    upper_id, lower_id = orbit_upper_lower_slot_ids(host, aux_layer)
    shown_id = upper_id if st.in_front else lower_id
    hidden_id = lower_id if st.in_front else upper_id
    overrides[shown_id] = plan
    hidden.add(hidden_id)


def compute_orbit_render_plan(
        state: BasicLayersState,
        time_s: float) -> tuple[dict[int, _OrbitDrawPlan], set[int]]:
    """Per-frame plan for circular-orbit objects.

    Returns (overrides, hidden): `overrides[slot_id]` carries the orbit offset /
    scale / pivot to apply to that slot's rect; `hidden` lists slots to skip this
    frame. With an auxiliary slot the object shows through whichever slot sits on
    the depth-correct side of the character (upper when near / in front, lower
    when far / behind) and the other is hidden, so the single object swaps in
    front of / behind the character without reordering the static stack.
    """
    overrides: dict[int, _OrbitDrawPlan] = {}
    hidden: set[int] = set()
    for layer in state.layers:
        if not layer_has_active_orbit(layer, state):
            continue
        st = compute_orbit_motion_state(layer, state, time_s)
        plan = _OrbitDrawPlan(
            source_slot_id=layer.slot_id,
            offset_x=st.offset_x,
            offset_y=st.offset_y,
            scale=st.scale,
            pivot_u=clamp_swing_pivot_u(layer.orbit_pivot_u),
            pivot_v=clamp_swing_pivot_v(layer.orbit_pivot_v),
            pivot_slot_id=layer.slot_id)
        assign_orbit_draw_plan(state, overrides, hidden, plan, st, layer)
    return overrides, hidden


def apply_orbit_to_resolved(
        state: BasicLayersState,
        resolved: dict[int, ResolvedLayerRect],
        binding_context: BindingContext,
        canvas_width: int,
        canvas_height: int,
        *,
        local_rects: Optional[dict[int, ResolvedLayerRect]] = None) -> dict[int, ResolvedLayerRect]:
    motion_time_s = binding_context.motion_time_s
    if motion_time_s is None:
        return resolved
    overrides, hidden = orbit_frame_plan(state, binding_context)
    if not overrides and not hidden:
        return resolved
    if local_rects is None:
        local_rects = {}
    pre_orbit = dict(resolved)
    sx = float(canvas_width) / float(LAYER_COORD_SIZE)
    sy = float(canvas_height) / float(LAYER_COORD_SIZE)
    for slot_id, plan in overrides.items():
        pivot_slot_id = (
            plan.pivot_slot_id if plan.pivot_slot_id is not None else plan.source_slot_id)
        source_bound = pre_orbit.get(pivot_slot_id)
        base_rect = pre_orbit.get(slot_id)
        if base_rect is None:
            base_rect = pre_orbit.get(plan.source_slot_id)
        if base_rect is None:
            continue
        size_rect = pre_orbit.get(plan.source_slot_id) or base_rect
        shift_x = 0.0
        shift_y = 0.0
        local_rect = local_rects.get(pivot_slot_id)
        if source_bound is not None and local_rect is not None:
            shift_x, shift_y = orbit_binding_shift(source_bound, local_rect)
        pivot_x = plan.pivot_u * float(canvas_width) + shift_x
        pivot_y = plan.pivot_v * float(canvas_height) + shift_y
        pivot_layer = find_layer_slot(state, pivot_slot_id)
        follow_rot = (
            orbit_binding_follow_rotation_deg(pivot_layer, state, binding_context)
            if pivot_layer is not None else 0.0)
        offset_x = plan.offset_x * sx
        offset_y = plan.offset_y * sy
        offset_x, offset_y = rotate_orbit_plane_offsets(
            offset_x, offset_y, follow_rot)
        center_x = pivot_x + offset_x
        center_y = pivot_y + offset_y
        width = max(1.0, size_rect.draw_width * plan.scale)
        height = max(1.0, size_rect.draw_height * plan.scale)
        new_rect = LayerGeometryResolver._rect_from_center(
            slot_id, center_x, center_y, width, height)
        new_rect.smoothed_rotation_deg = size_rect.smoothed_rotation_deg
        resolved[slot_id] = new_rect
    for slot_id in hidden:
        if slot_id in overrides:
            continue
        resolved.pop(slot_id, None)
    strip_orbit_requisitioned_native_rects(state, resolved, set(overrides))
    return resolved


def resolve_layer_rects(
        state: BasicLayersState,
        asset_loader: Callable[[BasicLayerSlot], Optional[wx.Image]],
        canvas_width: int,
        canvas_height: int,
        binding_context: Optional[BindingContext] = None,
        *,
        binding_smoother: Optional[LayerBindingSmoother] = None,
        include_motion: bool = True) -> dict[int, ResolvedLayerRect]:
    geometry_context = binding_context_for_layer_geometry(
        binding_context, include_motion=include_motion)
    local_rects = resolve_local_layer_rects(
        state, asset_loader, canvas_width, canvas_height)
    resolved = LayerGeometryResolver.resolve_all(
        state, asset_loader, canvas_width, canvas_height, geometry_context)
    if geometry_context is None:
        return resolved
    if binding_smoother is None:
        binding_smoother = geometry_context.binding_smoother
    if binding_smoother is not None:
        resolved = binding_smoother.apply(state, resolved, geometry_context)
    resolved = apply_orbit_to_resolved(
        state,
        resolved,
        geometry_context,
        canvas_width,
        canvas_height,
        local_rects=local_rects)
    if geometry_context is None or geometry_context.motion_time_s is None:
        strip_orbit_requisitioned_native_rects(state, resolved)
    return resolved


def resolved_layer_rotation_deg(
        layer: BasicLayerSlot,
        state: BasicLayersState,
        rect: ResolvedLayerRect,
        binding_context: Optional[BindingContext]) -> float:
    if rect.smoothed_rotation_deg is not None:
        return float(rect.smoothed_rotation_deg)
    return effective_layer_rotation_deg(layer, state, binding_context)


class LayerAssetCache:
    """Resolve static PNG/WebP and animated GIF layer assets."""

    def __init__(self, path_resolver: Callable[[str], str]) -> None:
        self._path_resolver = path_resolver
        self._static_cache: dict[str, wx.Image] = {}
        self._static_rgba_cache: dict[str, numpy.ndarray] = {}
        self._gif_sources: dict[str, _GifAnimationSource] = {}
        self._gif_numpy_sources: dict[str, _GifNumpySource] = {}
        self._animated_start_times: dict[str, float] = {}
        self._scaled_bitmap_cache: dict[tuple[str, int, int], wx.Bitmap] = {}
        self._gif_scaled_cache: dict[tuple[str, int, int, int], wx.Bitmap] = {}
        # Last drawn GIF frame index per asset, so the scaled-cache prune only runs
        # when the frame actually advances (not on every composite tick).
        self._gif_last_frame_idx: dict[str, int] = {}
        # Cache positive path resolutions to avoid a filesystem stat per layer per
        # frame on the render hot path. Misses are not cached so a later-created
        # asset is still picked up; invalidate() drops stale entries on reload.
        self._resolved_path_cache: dict[str, str] = {}

    def close(self) -> None:
        self._gif_sources.clear()
        self._gif_numpy_sources.clear()
        self._animated_start_times.clear()
        self._static_cache.clear()
        self._static_rgba_cache.clear()
        self._scaled_bitmap_cache.clear()
        self._gif_scaled_cache.clear()
        self._gif_last_frame_idx.clear()
        self._resolved_path_cache.clear()

    def clear(self) -> None:
        self.close()

    def _cache_key(self, asset_path: str) -> Optional[str]:
        cached = self._resolved_path_cache.get(asset_path)
        if cached is not None:
            return cached
        resolved = self._path_resolver(asset_path)
        if not resolved or not os.path.isfile(resolved):
            return None
        key = os.path.normpath(resolved)
        self._resolved_path_cache[asset_path] = key
        return key

    def _release_animated(self, cache_key: str) -> None:
        self._gif_sources.pop(cache_key, None)
        self._gif_numpy_sources.pop(cache_key, None)
        self._animated_start_times.pop(cache_key, None)
        self._gif_last_frame_idx.pop(cache_key, None)
        self._gif_scaled_cache = {
            key: bitmap
            for key, bitmap in self._gif_scaled_cache.items()
            if key[0] != cache_key
        }

    def invalidate(self, asset_path: Optional[str]) -> None:
        if not asset_path:
            return
        self._resolved_path_cache.pop(asset_path, None)
        cache_key = self._cache_key(asset_path)
        if cache_key is None:
            return
        self._static_cache.pop(cache_key, None)
        self._static_rgba_cache.pop(cache_key, None)
        self._release_animated(cache_key)
        self._scaled_bitmap_cache = {
            key: bitmap
            for key, bitmap in self._scaled_bitmap_cache.items()
            if key[0] != cache_key
        }

    def _load_static_image(self, resolved: str, cache_key: str) -> Optional[wx.Image]:
        cached = self._static_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            image = wx.Image(resolved, wx.BITMAP_TYPE_PNG)
            if not image.IsOk():
                return None
            if not image.HasAlpha():
                image.InitAlpha()
            image = _clean_transparent_rgb(image)
            self._static_cache[cache_key] = image
            return image
        except Exception:
            return None

    def _get_gif_source(self, resolved: str, cache_key: str) -> _GifAnimationSource:
        source = self._gif_sources.get(cache_key)
        if source is None:
            source = _GifAnimationSource.load(resolved)
            self._gif_sources[cache_key] = source
            self._animated_start_times.setdefault(cache_key, time.time())
        return source

    def _gif_frame_index(
            self,
            source: _GifAnimationSource,
            layer: BasicLayerSlot,
            now: float) -> int:
        return source.frame_index(now, layer)

    def _load_static_rgba(self, resolved: str, cache_key: str) -> Optional[numpy.ndarray]:
        cached = self._static_rgba_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            import PIL.Image
            with PIL.Image.open(resolved) as image:
                rgba = _pil_rgba_to_numpy(image)
        except Exception:
            return None
        self._static_rgba_cache[cache_key] = rgba
        return rgba

    def _get_gif_numpy_source(self, resolved: str, cache_key: str) -> _GifNumpySource:
        source = self._gif_numpy_sources.get(cache_key)
        if source is None:
            source = _GifNumpySource.load(resolved)
            self._gif_numpy_sources[cache_key] = source
            self._animated_start_times.setdefault(cache_key, time.time())
        return source

    def load_image_rgba(
            self,
            layer: BasicLayerSlot,
            *,
            now: Optional[float] = None) -> Optional[numpy.ndarray]:
        """Straight-alpha RGBA numpy frame for a layer (wx-free render path).

        Returns the full-resolution current frame (static or GIF); the numpy
        compositor scales per the resolved rect, mirroring get_draw_bitmap.
        """
        if not layer.asset_path:
            return None
        cache_key = self._cache_key(layer.asset_path)
        if cache_key is None:
            return None
        resolved = cache_key
        kind = classify_layer_asset_kind(layer.asset_path)
        if kind == "image":
            return self._load_static_rgba(resolved, cache_key)
        if kind == "gif":
            source = self._get_gif_numpy_source(resolved, cache_key)
            time_now = time.time() if now is None else now
            frame_idx = source.frame_index(time_now, layer)
            return source.frames[frame_idx]
        return None

    def preview_image(self, layer: BasicLayerSlot) -> Optional[wx.Image]:
        """First-frame preview for list thumbnails (GIF stays static)."""
        if not layer.asset_path:
            return None
        cache_key = self._cache_key(layer.asset_path)
        if cache_key is None:
            return None
        resolved = cache_key
        kind = classify_layer_asset_kind(layer.asset_path)
        if kind == "image":
            return self._load_static_image(resolved, cache_key)
        if kind == "gif":
            return self._get_gif_source(resolved, cache_key).preview
        return None

    def load_image(
            self,
            layer: BasicLayerSlot,
            *,
            now: Optional[float] = None) -> Optional[wx.Image]:
        if not layer.asset_path:
            return None
        cache_key = self._cache_key(layer.asset_path)
        if cache_key is None:
            return None
        resolved = cache_key
        kind = classify_layer_asset_kind(layer.asset_path)
        if kind == "image":
            return self._load_static_image(resolved, cache_key)
        if kind == "gif":
            source = self._get_gif_source(resolved, cache_key)
            time_now = time.time() if now is None else now
            return source.frame_at_time(time_now, layer)
        return None

    def get_draw_bitmap(
            self,
            layer: BasicLayerSlot,
            draw_width: float,
            draw_height: float) -> Optional[wx.Bitmap]:
        if not layer.asset_path:
            return None
        cache_key = self._cache_key(layer.asset_path)
        if cache_key is None:
            return None
        draw_w = max(1, int(round(draw_width)))
        draw_h = max(1, int(round(draw_height)))
        kind = classify_layer_asset_kind(layer.asset_path)
        if kind == "gif":
            source = self._get_gif_source(cache_key, cache_key)
            time_now = time.time()
            frame_idx = self._gif_frame_index(source, layer, time_now)
            scaled_key = (cache_key, draw_w, draw_h, frame_idx)
            cached = self._gif_scaled_cache.get(scaled_key)
            if cached is not None and cached.IsOk():
                return cached
            image = source.frames[frame_idx]
            if draw_w != image.GetWidth() or draw_h != image.GetHeight():
                bitmap = scale_image_to_bitmap(image, draw_w, draw_h)
            else:
                bitmap = image.ConvertToBitmap()
            # Only prune this GIF's stale-frame scaled entries when the frame
            # advanced; same-frame repeats (composite faster than GIF fps) skip it.
            if self._gif_last_frame_idx.get(cache_key) != frame_idx:
                self._gif_scaled_cache = {
                    key: value
                    for key, value in self._gif_scaled_cache.items()
                    if key[0] != cache_key or key[3] == frame_idx
                }
                self._gif_last_frame_idx[cache_key] = frame_idx
            self._gif_scaled_cache[scaled_key] = bitmap
            return bitmap
        scaled_key = (cache_key, draw_w, draw_h)
        cached = self._scaled_bitmap_cache.get(scaled_key)
        if cached is not None and cached.IsOk():
            return cached
        image = self.load_image(layer)
        if image is None:
            return None
        if draw_w != image.GetWidth() or draw_h != image.GetHeight():
            bitmap = scale_image_to_bitmap(image, draw_w, draw_h)
        else:
            bitmap = image.ConvertToBitmap()
        self._scaled_bitmap_cache[scaled_key] = bitmap
        return bitmap

    def thumbnail_bitmap(self, layer: BasicLayerSlot, size: int = 48) -> wx.Bitmap:
        image = self.preview_image(layer)
        if image is None:
            bmp = wx.Bitmap(size, size)
            dc = wx.MemoryDC(bmp)
            dc.SetBackground(wx.Brush(wx.Colour(48, 48, 48)))
            dc.Clear()
            dc.SetPen(wx.Pen(wx.Colour(120, 120, 120)))
            dc.DrawRectangle(0, 0, size, size)
            font = wx.Font(wx.FontInfo(8).Family(wx.FONTFAMILY_SWISS))
            dc.SetFont(font)
            dc.SetTextForeground(wx.Colour(180, 180, 180))
            label = f"L{layer.slot_id + 1}" if layer.slot_id >= 0 else "C"
            dc.DrawLabel(label, wx.Rect(0, 0, size, size), wx.ALIGN_CENTER)
            del dc
            return bmp
        thumb = image.Scale(size, size, wx.IMAGE_QUALITY_HIGH)
        return thumb.ConvertToBitmap()


class LayerCompositor:
    @staticmethod
    def draw_layer_on_dc(
            dc: wx.DC,
            layer: BasicLayerSlot,
            rect: ResolvedLayerRect,
            *,
            asset_cache: Optional[LayerAssetCache] = None,
            image: Optional[wx.Image] = None,
            binding_context: Optional[BindingContext] = None,
            layers_state: Optional[BasicLayersState] = None) -> None:
        if asset_cache is not None:
            bitmap = asset_cache.get_draw_bitmap(layer, rect.draw_width, rect.draw_height)
        elif image is not None:
            draw_width = max(1, int(round(rect.draw_width)))
            draw_height = max(1, int(round(rect.draw_height)))
            if draw_width != image.GetWidth() or draw_height != image.GetHeight():
                bitmap = scale_image_to_bitmap(image, draw_width, draw_height)
            else:
                bitmap = image.ConvertToBitmap()
        else:
            return
        if bitmap is None or not bitmap.IsOk():
            return
        draw_w = max(1, int(round(rect.draw_width)))
        draw_h = max(1, int(round(rect.draw_height)))
        container_rotation_deg = float(layer.transform.rotation_deg)
        if layers_state is not None:
            container_rotation_deg = resolved_layer_rotation_deg(
                layer, layers_state, rect, binding_context)
        swing_deg = 0.0
        motion_time_s = None
        if binding_context is not None:
            motion_time_s = binding_context.motion_time_s
        if (
                motion_time_s is not None
                and layer.asset_path
                and layer.motion_mode == MOTION_MODE_SIMPLE_SWING):
            swing_deg = compute_swing_angle_deg(layer, motion_time_s)
        needs_transform = (
            abs(container_rotation_deg) > 1e-4
            or abs(swing_deg) > 1e-4)
        if needs_transform:
            gc = wx.GraphicsContext.Create(dc)
            if gc is None:
                dc.DrawBitmap(
                    bitmap,
                    int(round(rect.draw_x)),
                    int(round(rect.draw_y)),
                    True)
                return
            cx = rect.draw_x + rect.draw_width / 2.0
            cy = rect.draw_y + rect.draw_height / 2.0
            pivot_off_x = (clamp_swing_pivot_u(layer.swing_pivot_u) - 0.5) * draw_w
            pivot_off_y = (clamp_swing_pivot_v(layer.swing_pivot_v) - 0.5) * draw_h
            gc.Translate(cx, cy)
            gc.Rotate(math.radians(container_rotation_deg))
            if abs(swing_deg) > 1e-4:
                gc.Translate(pivot_off_x, pivot_off_y)
                gc.Rotate(math.radians(swing_deg))
                gc.Translate(-pivot_off_x, -pivot_off_y)
            gc.DrawBitmap(bitmap, -draw_w / 2.0, -draw_h / 2.0, draw_w, draw_h)
            return
        dc.DrawBitmap(
            bitmap,
            int(round(rect.draw_x)),
            int(round(rect.draw_y)),
            True)

    @classmethod
    def draw_layers_group(
            cls,
            dc: wx.DC,
            state: BasicLayersState,
            occlusion: str,
            asset_loader: Callable[[BasicLayerSlot], Optional[wx.Image]],
            canvas_width: int,
            canvas_height: int,
            binding_context: Optional[BindingContext] = None) -> None:
        resolved = resolve_layer_rects(
            state, asset_loader, canvas_width, canvas_height, binding_context)
        orbit_plan, hidden_slots = orbit_frame_plan(state, binding_context)
        for layer in state.sorted_layers_for_draw(occlusion):
            if not layer.enabled:
                continue
            draw_pair = resolve_stack_layer_draw(
                state, layer, resolved, orbit_plan, hidden_slots)
            if draw_pair is None:
                continue
            draw_layer, rect = draw_pair
            if not draw_layer.visible:
                continue
            image = asset_loader(draw_layer)
            if image is None:
                continue
            cls.draw_layer_on_dc(
                dc, draw_layer, rect, image=image,
                binding_context=binding_context, layers_state=state)

    @classmethod
    def draw_post_process_stack(
            cls,
            dc: wx.DC,
            state: BasicLayersState,
            asset_cache: LayerAssetCache,
            canvas_width: int,
            canvas_height: int,
            character_bitmap: wx.Bitmap,
            binding_context: Optional[BindingContext] = None) -> dict[int, ResolvedLayerRect]:
        """Post-process: composite character keyframe and layer stack on output.

        Returns the resolved layer rects so callers can reuse them (e.g. for the
        selection highlight) without resolving the whole stack a second time.
        """
        resolved = resolve_layer_rects(
            state,
            asset_cache.load_image,
            canvas_width,
            canvas_height,
            binding_context)
        orbit_plan, hidden_slots = orbit_frame_plan(state, binding_context)
        character_pos = state.character_stack_position
        for pos in range(state.total_stack_positions):
            if pos == character_pos:
                dc.DrawBitmap(character_bitmap, 0, 0, True)
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
            cls.draw_layer_on_dc(
                dc, draw_layer, rect, asset_cache=asset_cache,
                binding_context=binding_context, layers_state=state)
        return resolved

    @classmethod
    def draw_unified_stack(
            cls,
            dc: wx.DC,
            state: BasicLayersState,
            asset_loader: Callable[[BasicLayerSlot], Optional[wx.Image]],
            canvas_width: int,
            canvas_height: int,
            draw_character: Callable[[], None],
            binding_context: Optional[BindingContext] = None) -> None:
        resolved = resolve_layer_rects(
            state, asset_loader, canvas_width, canvas_height, binding_context)
        orbit_plan, hidden_slots = orbit_frame_plan(state, binding_context)
        character_pos = state.character_stack_position
        for pos in range(state.total_stack_positions):
            if pos == character_pos:
                draw_character()
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
            image = asset_loader(draw_layer)
            if image is None:
                continue
            cls.draw_layer_on_dc(
                dc, draw_layer, rect, image=image,
                binding_context=binding_context, layers_state=state)

    @staticmethod
    def hit_test_layer_slot(
            state: BasicLayersState,
            asset_loader: Callable[[BasicLayerSlot], Optional[wx.Image]],
            x: int,
            y: int,
            canvas_width: int,
            canvas_height: int,
            binding_context: Optional[BindingContext] = None) -> Optional[int]:
        resolved = resolve_layer_rects(
            state, asset_loader, canvas_width, canvas_height, binding_context)
        orbit_plan, hidden_slots = orbit_frame_plan(state, binding_context)
        hit_slot: Optional[int] = None
        character_pos = state.character_stack_position
        for pos in range(state.total_stack_positions):
            if pos == character_pos:
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
            if (rect.draw_x <= x <= rect.draw_x + rect.draw_width
                    and rect.draw_y <= y <= rect.draw_y + rect.draw_height):
                hit_slot = orbit_selection_slot_id(layer.slot_id, orbit_plan)
        return hit_slot

    @staticmethod
    def draw_selection_highlight(
            dc: wx.DC,
            rect: ResolvedLayerRect,
            canvas_width: int,
            canvas_height: int,
            highlight_colour: Optional[wx.Colour] = None,
            rotation_deg: float = 0.0) -> None:
        w = max(1, int(round(rect.draw_width)))
        h = max(1, int(round(rect.draw_height)))
        colour = highlight_colour if highlight_colour is not None else wx.Colour(255, 200, 0)
        handle = 8
        if abs(rotation_deg) <= 1e-4:
            x = int(round(rect.draw_x))
            y = int(round(rect.draw_y))
            pen = wx.Pen(colour, 2)
            dc.SetPen(pen)
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(x, y, w, h)
            dc.SetBrush(wx.Brush(colour))
            dc.DrawRectangle(x + w - handle, y + h - handle, handle, handle)
            return
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            x = int(round(rect.draw_x))
            y = int(round(rect.draw_y))
            dc.SetPen(wx.Pen(colour, 2))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(x, y, w, h)
            return
        cx = rect.draw_x + rect.draw_width / 2.0
        cy = rect.draw_y + rect.draw_height / 2.0
        gc.Translate(cx, cy)
        gc.Rotate(math.radians(rotation_deg))
        gc.SetPen(wx.Pen(colour, 2))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawRectangle(-w / 2.0, -h / 2.0, w, h)
        gc.SetBrush(wx.Brush(colour))
        gc.DrawRectangle(w / 2.0 - handle, h / 2.0 - handle, handle, handle)


def get_basic_layers_directory(ui_state_file_path: str) -> str:
    base_dir = os.path.dirname(ui_state_file_path)
    return os.path.join(base_dir, BASIC_LAYERS_DIR_NAME)


def _append_layer_load_log(ui_state_file_path: str, message: str) -> None:
    try:
        log_path = os.path.join(os.path.dirname(ui_state_file_path), "layer_load.log")
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(message.rstrip() + "\n")
    except Exception:
        pass


def _load_layers_from_slot_files(
        directory: str,
        resolve_path: Callable[[Optional[str]], Optional[str]]) -> list[BasicLayerSlot]:
    layers: list[BasicLayerSlot] = []
    slot_ids: list[int] = []
    try:
        for name in os.listdir(directory):
            match = re.fullmatch(r"layer_(\d+)\.json", name)
            if match:
                slot_ids.append(int(match.group(1)))
    except OSError:
        return []
    for slot_id in sorted(slot_ids):
        slot_path = os.path.join(directory, f"layer_{slot_id}.json")
        try:
            with open(slot_path, encoding="utf-8") as fp:
                item = json.load(fp)
            layer = BasicLayerSlot.from_dict(item, slot_id)
            if layer.asset_path:
                layer.asset_path = resolve_path(layer.asset_path)
            layers.append(layer)
        except Exception:
            continue
    return layers


def save_basic_layers_state(
        state: BasicLayersState,
        ui_state_file_path: str,
        relativize_path: Callable[[Optional[str]], Optional[str]]) -> None:
    save_sync_time = time.time()
    for layer in state.layers:
        host = resolve_orbit_host_layer(state, layer)
        if host is not None:
            sync_orbit_follow_kinematics_from_host(layer, host, save_sync_time)
    sanitize_layer_references(state)
    directory = get_basic_layers_directory(ui_state_file_path)
    os.makedirs(directory, exist_ok=True)
    manifest_layers = []
    live_slot_ids = {layer.slot_id for layer in state.layers}
    # Drop stale per-slot files left behind by deleted layers.
    try:
        for name in os.listdir(directory):
            match = re.fullmatch(r"layer_(\d+)\.json", name)
            if match and int(match.group(1)) not in live_slot_ids:
                try:
                    os.remove(os.path.join(directory, name))
                except OSError:
                    pass
    except OSError:
        pass
    for layer in state.layers:
        slot_path = os.path.join(directory, f"layer_{layer.slot_id}.json")
        layer_dict = layer.to_dict()
        if layer_dict.get("asset_path"):
            layer_dict["asset_path"] = relativize_path(layer_dict["asset_path"])
        with open(slot_path, "w", encoding="utf-8") as fp:
            json.dump(layer_dict, fp, ensure_ascii=True, indent=2)
        manifest_layers.append(layer_dict)
    manifest = {
        "layer_mode": state.layer_mode,
        "layers": manifest_layers,
        "selected_slot_id": state.selected_slot_id,
    }
    manifest_path = os.path.join(directory, "manifest.json")
    temp_path = manifest_path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as fp:
        json.dump(manifest, fp, ensure_ascii=True, indent=2)
    os.replace(temp_path, manifest_path)


def load_basic_layers_state(
        ui_state_file_path: str,
        resolve_path: Callable[[Optional[str]], Optional[str]]) -> BasicLayersState:
    directory = get_basic_layers_directory(ui_state_file_path)
    manifest_path = os.path.join(directory, "manifest.json")
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as fp:
                data = json.load(fp)
            state = BasicLayersState.from_dict(data)
            for layer in state.layers:
                if layer.asset_path:
                    original = layer.asset_path
                    layer.asset_path = resolve_path(layer.asset_path)
                    if layer.asset_path is None:
                        _append_layer_load_log(
                            ui_state_file_path,
                            f"missing layer asset slot={layer.slot_id}: {original}")
            return state
        except Exception as exc:
            _append_layer_load_log(
                ui_state_file_path,
                f"manifest load failed, falling back to layer_*.json: {exc}")
    layers = _load_layers_from_slot_files(directory, resolve_path)
    state = BasicLayersState(layers=layers)
    normalize_layer_stack_positions(state)
    sanitize_layer_references(state)
    return state


def move_layer_z_order(state: BasicLayersState, slot_id: int, delta: int) -> bool:
    """Move a layer one step in the unified stack (+1 = toward top / in front of
    character). Crossing the character flips behind<->front. Works for any layer
    count by swapping with the adjacent stack item (layer or character)."""
    if delta == 0:
        return False
    normalize_layer_stack_positions(state)
    layer = state.get_slot(slot_id)
    total = state.total_stack_positions
    char_pos = state.character_stack_position
    # Bottom-to-top sequence: index -> layer slot, with the character sentinel.
    sequence: list[object] = [None] * total
    sequence[char_pos] = "__character__"
    for item in state.layers:
        if 0 <= item.z_order < total:
            sequence[item.z_order] = item
    idx = layer.z_order
    step = 1 if delta > 0 else -1
    target = idx + step
    if target < 0 or target >= total:
        return False
    sequence[idx], sequence[target] = sequence[target], sequence[idx]
    new_char_pos = sequence.index("__character__")
    for pos, item in enumerate(sequence):
        if item == "__character__" or item is None:
            continue
        item.z_order = pos
        item.occlusion = OCCLUSION_BEHIND if pos < new_char_pos else OCCLUSION_FRONT
    return True
