"""
Basic five-layer runtime: state, geometry, composition, persistence.

L1 scope: static PNG/WebP and animated GIF layer assets (GIF composited with
transparent disposal); preview thumbnails use the first frame.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Optional

import wx

LAYER_STATIC_IMAGE_EXTENSIONS = (".png", ".webp")
LAYER_GIF_EXTENSIONS = (".gif",)
LAYER_ASSET_FILE_WILDCARD = (
    "All supported|*.png;*.webp;*.gif|"
    "PNG (*.png)|*.png|GIF (*.gif)|*.gif|"
    "All files (*.*)|*.*")

LAYER_COORD_SIZE = 512
NUM_BASIC_LAYERS = 5
BASIC_LAYERS_DIR_NAME = "basic_layers"

OCCLUSION_BEHIND = "behind_character"
OCCLUSION_FRONT = "in_front_of_character"

LAYER_MODE_BASIC = "basic_five"
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


def clamp_binding_smooth_alpha(value: float) -> float:
    return max(
        BINDING_SMOOTH_ALPHA_MIN,
        min(BINDING_SMOOTH_ALPHA_MAX, float(value)))


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
        if 0 <= slot_id < NUM_BASIC_LAYERS:
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


def format_layer_row_summary(layer: BasicLayerSlot) -> str:
    side = "上" if layer.z_order > CHARACTER_STACK_POS else "下"
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
        parent = state.get_slot(parent_slot)
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


def parse_layer_binding_slot(value: Optional[str]) -> Optional[int]:
    normalized = normalize_binding_target(value)
    if normalized is None or not normalized.startswith(BINDING_LAYER_PREFIX):
        return None
    try:
        return int(normalized.split(":")[1])
    except (IndexError, ValueError):
        return None


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
        return payload

    @classmethod
    def from_dict(cls, data: dict, slot_id: int) -> BasicLayerSlot:
        occlusion = str(data.get("occlusion", OCCLUSION_BEHIND))
        if occlusion not in (OCCLUSION_BEHIND, OCCLUSION_FRONT):
            occlusion = OCCLUSION_BEHIND
        return cls(
            slot_id=slot_id,
            enabled=bool(data.get("enabled", True)),
            visible=bool(data.get("visible", True)),
            asset_path=data.get("asset_path") if data.get("asset_path") else None,
            z_order=int(data.get("z_order", slot_id)),
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
        )


@dataclass
class BasicLayersState:
    layer_mode: str = LAYER_MODE_BASIC
    layers: list[BasicLayerSlot] = field(default_factory=list)
    selected_slot_id: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.layers:
            self.layers = [default_basic_layer_slot(i) for i in range(NUM_BASIC_LAYERS)]

    def get_slot(self, slot_id: int) -> BasicLayerSlot:
        for layer in self.layers:
            if layer.slot_id == slot_id:
                return layer
        layer = default_basic_layer_slot(slot_id)
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
            for index, item in enumerate(layers_data[:NUM_BASIC_LAYERS]):
                if isinstance(item, dict):
                    slot_id = int(item.get("slot_id", index))
                    layers.append(BasicLayerSlot.from_dict(item, slot_id))
        if len(layers) < NUM_BASIC_LAYERS:
            existing_ids = {layer.slot_id for layer in layers}
            for slot_id in range(NUM_BASIC_LAYERS):
                if slot_id not in existing_ids:
                    layers.append(default_basic_layer_slot(slot_id))
        layer_mode = str(data.get("layer_mode", LAYER_MODE_BASIC))
        selected = data.get("selected_slot_id")
        selected_slot_id = int(selected) if selected is not None else None
        if selected_slot_id is not None and selected_slot_id < 0:
            selected_slot_id = None
        result = cls(layer_mode=layer_mode, layers=layers, selected_slot_id=selected_slot_id)
        normalize_layer_stack_positions(result)
        return result


CHARACTER_STACK_POS = 2
LAYER_STACK_POSITIONS = (0, 1, 3, 4, 5)
DRAW_STACK_BOTTOM_TO_TOP = (0, 1, 2, 3, 4, 5)


def default_stack_position_for_slot(slot_id: int) -> int:
    if slot_id < 2:
        return slot_id
    return slot_id + 1


def occlusion_for_stack_position(stack_pos: int) -> str:
    return OCCLUSION_BEHIND if stack_pos < CHARACTER_STACK_POS else OCCLUSION_FRONT


def layer_at_stack_position(state: BasicLayersState, stack_pos: int) -> Optional[BasicLayerSlot]:
    for layer in state.layers:
        if layer.z_order == stack_pos:
            return layer
    return None


def normalize_layer_stack_positions(state: BasicLayersState) -> None:
    """Ensure five layers occupy stack slots 0,1,3,4,5 (2 = character)."""
    valid = set(LAYER_STACK_POSITIONS)
    used: set[int] = set()
    for layer in state.layers:
        if layer.z_order in valid and layer.z_order not in used:
            used.add(layer.z_order)
            layer.occlusion = occlusion_for_stack_position(layer.z_order)
            continue
        new_pos = default_stack_position_for_slot(layer.slot_id)
        while new_pos in used:
            new_pos = min(valid, key=lambda p: (p in used, p))
        layer.z_order = new_pos
        layer.occlusion = occlusion_for_stack_position(new_pos)
        used.add(new_pos)


def iter_ui_list_top_to_bottom(state: BasicLayersState):
    """UI list: top = drawn last; character row sits at stack position 2."""
    for pos in (5, 4, 3):
        layer = layer_at_stack_position(state, pos)
        if layer is not None:
            yield ("layer", layer.slot_id)
    yield ("character", None)
    for pos in (1, 0):
        layer = layer_at_stack_position(state, pos)
        if layer is not None:
            yield ("layer", layer.slot_id)


def stack_position_can_move_up(stack_pos: int) -> bool:
    return stack_pos < max(LAYER_STACK_POSITIONS)


def stack_position_can_move_down(stack_pos: int) -> bool:
    return stack_pos > min(LAYER_STACK_POSITIONS)


def default_swing_phase_rad(slot_id: int) -> float:
    return float(slot_id) * 1.1


def normalize_motion_mode(value: Optional[str]) -> str:
    if value == MOTION_MODE_SIMPLE_SWING:
        return MOTION_MODE_SIMPLE_SWING
    return MOTION_MODE_NONE


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


def basic_layers_state_has_active_motion(state: BasicLayersState) -> bool:
    return any(layer_has_active_swing(layer) for layer in state.layers)


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


def default_basic_layer_slot(slot_id: int) -> BasicLayerSlot:
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
    force_full_layer_follow: bool = False
    binding_smoother: Optional["LayerBindingSmoother"] = field(
        default=None, compare=False, repr=False)
    motion_time_s: Optional[float] = None

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

    def dynamic_enhancement_tilt_deg(self, *, extra_mocap_angle: bool = False) -> float:
        """Head-driven output dynamic enhancement tilt (layer body bind follows this)."""
        _ = extra_mocap_angle
        return float(self.display_rotation_deg)

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
        """Body-bind anchor for layer follow: dynamic enhancement direction, not model-opposite."""
        bottom_x, bottom_y = self.character_bottom_anchor()
        angle = self.dynamic_enhancement_tilt_deg(extra_mocap_angle=extra_pose_offset)
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
        """Sprite roll on head bind: upper spine angle + optional extra neck roll."""
        return self.spine_upper_angle_deg() + self.pose_head_roll_deg(
            extra_gain=extra_pose_roll)

    def body_binding_rotation_deg(self) -> float:
        return self.dynamic_enhancement_tilt_deg()

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

    def frame_at_time(self, now: float, start_time: float) -> wx.Image:
        elapsed_ms = int(max(0.0, (now - start_time) * 1000.0)) % self.total_ms
        acc = 0
        for idx, duration in enumerate(self.durations_ms):
            acc += duration
            if elapsed_ms < acc:
                return self.frames[idx]
        return self.frames[-1]


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
        for pos in DRAW_STACK_BOTTOM_TO_TOP:
            if pos == CHARACTER_STACK_POS:
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
            if not smooth.active:
                smooth.center_x = cx
                smooth.center_y = cy
                smooth.rotation_deg = target_rotation
                smooth.active = True
            else:
                smooth.center_x += layer_alpha * (cx - smooth.center_x)
                smooth.center_y += layer_alpha * (cy - smooth.center_y)
                smooth.rotation_deg = _lerp_angle_deg(
                    smooth.rotation_deg, target_rotation, layer_alpha)
            result[slot_id] = LayerGeometryResolver._rect_from_center(
                slot_id,
                smooth.center_x,
                smooth.center_y,
                rect.draw_width,
                rect.draw_height)
            result[slot_id].smoothed_rotation_deg = smooth.rotation_deg
        stale = [slot_id for slot_id in self._slots if slot_id not in active_slots]
        for slot_id in stale:
            self.reset_slot(slot_id)
        return result


def resolve_layer_rects(
        state: BasicLayersState,
        asset_loader: Callable[[BasicLayerSlot], Optional[wx.Image]],
        canvas_width: int,
        canvas_height: int,
        binding_context: Optional[BindingContext] = None,
        *,
        binding_smoother: Optional[LayerBindingSmoother] = None) -> dict[int, ResolvedLayerRect]:
    resolved = LayerGeometryResolver.resolve_all(
        state, asset_loader, canvas_width, canvas_height, binding_context)
    if binding_context is None:
        return resolved
    if binding_smoother is None:
        binding_smoother = binding_context.binding_smoother
    if binding_smoother is None:
        return resolved
    return binding_smoother.apply(state, resolved, binding_context)


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
        self._gif_sources: dict[str, _GifAnimationSource] = {}
        self._animated_start_times: dict[str, float] = {}
        self._scaled_bitmap_cache: dict[tuple[str, int, int], wx.Bitmap] = {}
        self._gif_scaled_cache: dict[tuple[str, int, int, int], wx.Bitmap] = {}

    def close(self) -> None:
        self._gif_sources.clear()
        self._animated_start_times.clear()
        self._static_cache.clear()
        self._scaled_bitmap_cache.clear()
        self._gif_scaled_cache.clear()

    def clear(self) -> None:
        self.close()

    def _cache_key(self, asset_path: str) -> Optional[str]:
        resolved = self._path_resolver(asset_path)
        if not resolved or not os.path.isfile(resolved):
            return None
        return os.path.normpath(resolved)

    def _release_animated(self, cache_key: str) -> None:
        self._gif_sources.pop(cache_key, None)
        self._animated_start_times.pop(cache_key, None)
        self._gif_scaled_cache = {
            key: bitmap
            for key, bitmap in self._gif_scaled_cache.items()
            if key[0] != cache_key
        }

    def invalidate(self, asset_path: Optional[str]) -> None:
        if not asset_path:
            return
        cache_key = self._cache_key(asset_path)
        if cache_key is None:
            return
        self._static_cache.pop(cache_key, None)
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

    def _gif_frame_index(self, source: _GifAnimationSource, now: float, start_time: float) -> int:
        elapsed_ms = int(max(0.0, (now - start_time) * 1000.0)) % source.total_ms
        acc = 0
        for idx, duration in enumerate(source.durations_ms):
            acc += duration
            if elapsed_ms < acc:
                return idx
        return max(0, len(source.frames) - 1)

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
            start = self._animated_start_times.setdefault(cache_key, time.time())
            return source.frame_at_time(time.time() if now is None else now, start)
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
            start = self._animated_start_times.setdefault(cache_key, time.time())
            frame_idx = self._gif_frame_index(source, time.time(), start)
            scaled_key = (cache_key, draw_w, draw_h, frame_idx)
            cached = self._gif_scaled_cache.get(scaled_key)
            if cached is not None and cached.IsOk():
                return cached
            image = source.frames[frame_idx]
            if draw_w != image.GetWidth() or draw_h != image.GetHeight():
                bitmap = scale_image_to_bitmap(image, draw_w, draw_h)
            else:
                bitmap = image.ConvertToBitmap()
            self._gif_scaled_cache = {
                key: value
                for key, value in self._gif_scaled_cache.items()
                if key[0] != cache_key or key[3] == frame_idx
            }
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
        for layer in state.sorted_layers_for_draw(occlusion):
            image = asset_loader(layer)
            rect = resolved.get(layer.slot_id)
            if image is None or rect is None:
                continue
            cls.draw_layer_on_dc(
                dc, layer, rect, image=image,
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
            binding_context: Optional[BindingContext] = None) -> None:
        """Post-process: composite character keyframe and layer stack on output."""
        resolved = resolve_layer_rects(
            state,
            asset_cache.load_image,
            canvas_width,
            canvas_height,
            binding_context)
        for pos in DRAW_STACK_BOTTOM_TO_TOP:
            if pos == CHARACTER_STACK_POS:
                dc.DrawBitmap(character_bitmap, 0, 0, True)
                continue
            layer = layer_at_stack_position(state, pos)
            if layer is None or not layer.enabled or not layer.visible or not layer.asset_path:
                continue
            rect = resolved.get(layer.slot_id)
            if rect is None:
                continue
            cls.draw_layer_on_dc(
                dc, layer, rect, asset_cache=asset_cache,
                binding_context=binding_context, layers_state=state)

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
        for pos in DRAW_STACK_BOTTOM_TO_TOP:
            if pos == CHARACTER_STACK_POS:
                draw_character()
                continue
            layer = layer_at_stack_position(state, pos)
            if layer is None or not layer.enabled or not layer.visible or not layer.asset_path:
                continue
            image = asset_loader(layer)
            rect = resolved.get(layer.slot_id)
            if image is None or rect is None:
                continue
            cls.draw_layer_on_dc(
                dc, layer, rect, image=image,
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
        hit_slot: Optional[int] = None
        for pos in DRAW_STACK_BOTTOM_TO_TOP:
            if pos == CHARACTER_STACK_POS:
                continue
            layer = layer_at_stack_position(state, pos)
            if layer is None or not layer.enabled or not layer.visible or not layer.asset_path:
                continue
            rect = resolved.get(layer.slot_id)
            if rect is None:
                continue
            if (rect.draw_x <= x <= rect.draw_x + rect.draw_width
                    and rect.draw_y <= y <= rect.draw_y + rect.draw_height):
                hit_slot = layer.slot_id
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
    for slot_id in range(NUM_BASIC_LAYERS):
        slot_path = os.path.join(directory, f"layer_{slot_id}.json")
        if os.path.isfile(slot_path):
            try:
                with open(slot_path, encoding="utf-8") as fp:
                    item = json.load(fp)
                layer = BasicLayerSlot.from_dict(item, slot_id)
                if layer.asset_path:
                    layer.asset_path = resolve_path(layer.asset_path)
                layers.append(layer)
                continue
            except Exception:
                pass
        layers.append(default_basic_layer_slot(slot_id))
    return layers


def save_basic_layers_state(
        state: BasicLayersState,
        ui_state_file_path: str,
        relativize_path: Callable[[Optional[str]], Optional[str]]) -> None:
    directory = get_basic_layers_directory(ui_state_file_path)
    os.makedirs(directory, exist_ok=True)
    manifest_layers = []
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
    return state


def move_layer_z_order(state: BasicLayersState, slot_id: int, delta: int) -> bool:
    """Move layer in unified stack (+1 = toward top / in front of character)."""
    layer = state.get_slot(slot_id)
    positions = list(LAYER_STACK_POSITIONS)
    try:
        idx = positions.index(layer.z_order)
    except ValueError:
        normalize_layer_stack_positions(state)
        idx = positions.index(state.get_slot(slot_id).z_order)
    new_idx = idx + delta
    if new_idx < 0 or new_idx >= len(positions):
        return False
    target_pos = positions[new_idx]
    other = next((item for item in state.layers if item.slot_id != slot_id and item.z_order == target_pos), None)
    if other is not None:
        other.z_order, layer.z_order = layer.z_order, target_pos
        other.occlusion = occlusion_for_stack_position(other.z_order)
    else:
        layer.z_order = target_pos
    layer.occlusion = occlusion_for_stack_position(layer.z_order)
    return True
