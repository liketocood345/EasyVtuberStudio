"""Synthetic MediaPipeFacePose from global screen mouse + procedural blink."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional, Tuple

import numpy
import wx
from scipy.spatial.transform import Rotation

from tha4.mocap.mediapipe_constants import (
    BLENDSHAPE_NAMES,
    EYE_BLINK_LEFT,
    EYE_BLINK_RIGHT,
    EYE_LOOK_DOWN_LEFT,
    EYE_LOOK_DOWN_RIGHT,
    EYE_LOOK_IN_LEFT,
    EYE_LOOK_IN_RIGHT,
    EYE_LOOK_OUT_LEFT,
    EYE_LOOK_OUT_RIGHT,
    EYE_LOOK_UP_LEFT,
    EYE_LOOK_UP_RIGHT,
)
from tha4.mocap.mediapipe_face_pose import MediaPipeFacePose

MOCAP_INPUT_MODE_MEDIAPIPE = "mediapipe"
MOCAP_INPUT_MODE_OPENSEEFACE = "openseeface"
MOCAP_INPUT_MODE_MOUSE_AUDIO = "mouse_audio"
MOCAP_INPUT_MODE_VALUES = (
    MOCAP_INPUT_MODE_MEDIAPIPE,
    MOCAP_INPUT_MODE_OPENSEEFACE,
    MOCAP_INPUT_MODE_MOUSE_AUDIO,
)
MOCAP_INPUT_MODE_LABELS = (
    "Face capture (MediaPipe) / 摄像头面捕 (MediaPipe)",
    "Face capture (OpenSeeFace) / 摄像头面捕 (OpenSeeFace)",
    "Eyes follow mouse, auto blink / 角色眼睛跟踪鼠标并启用自动眨眼",
)

MOUSE_BLINK_INTERVAL_MIN_SEC = 2.0
MOUSE_BLINK_INTERVAL_MAX_SEC = 20.0
MOUSE_ZONE_HALF_MIN = 0.05
MOUSE_ZONE_HALF_MAX = 0.95
MOUSE_DEFAULT_FACE_SIZE = 0.35
MOUSE_HORIZONTAL_TILT_MIX_DEFAULT = 0.5
MOUSE_HORIZONTAL_TILT_MIX_MIN = 0.0
MOUSE_HORIZONTAL_TILT_MIX_MAX = 1.0
MOUSE_HORIZONTAL_LOCAL_TILT_FULL = 2.0
MOUSE_FACE_SIZE_MIN = 0.12
MOUSE_FACE_SIZE_MAX = 1.0
MOUSE_VERTICAL_FACE_SIZE_DELTA_PER_UNIT = 0.12


def normalize_mocap_input_mode(value: object) -> str:
    if value == MOCAP_INPUT_MODE_MOUSE_AUDIO:
        return MOCAP_INPUT_MODE_MOUSE_AUDIO
    if value == MOCAP_INPUT_MODE_OPENSEEFACE:
        return MOCAP_INPUT_MODE_OPENSEEFACE
    return MOCAP_INPUT_MODE_MEDIAPIPE


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def clamp_blink_interval_sec(value: float) -> float:
    return clamp(float(value), MOUSE_BLINK_INTERVAL_MIN_SEC, MOUSE_BLINK_INTERVAL_MAX_SEC)


def clamp_horizontal_tilt_mix(value: float) -> float:
    return clamp(float(value), MOUSE_HORIZONTAL_TILT_MIX_MIN, MOUSE_HORIZONTAL_TILT_MIX_MAX)


@dataclass(frozen=True)
class MouseTrackingSurface:
    """Virtual desktop bounds used for mouse normalization and zone diagram aspect."""
    origin_x: int = 0
    origin_y: int = 0
    width: int = 1
    height: int = 1

    @property
    def center_x(self) -> float:
        return self.origin_x + self.width * 0.5

    @property
    def center_y(self) -> float:
        return self.origin_y + self.height * 0.5

    @property
    def half_width(self) -> float:
        return max(self.width * 0.5, 1.0)

    @property
    def half_height(self) -> float:
        return max(self.height * 0.5, 1.0)

    @property
    def aspect_ratio(self) -> float:
        return self.width / max(self.height, 1)


def get_mouse_tracking_surface() -> MouseTrackingSurface:
    """Union of all wx displays (virtual desktop), for multi-monitor consistency."""
    try:
        display_count = wx.Display.GetCount()
    except Exception:
        display_count = 1
    if display_count < 1:
        display_count = 1
    geometries = [wx.Display(index).GetGeometry() for index in range(display_count)]
    origin_x = min(geometry.x for geometry in geometries)
    origin_y = min(geometry.y for geometry in geometries)
    right = max(geometry.x + geometry.width for geometry in geometries)
    bottom = max(geometry.y + geometry.height for geometry in geometries)
    return MouseTrackingSurface(
        origin_x=origin_x,
        origin_y=origin_y,
        width=max(1, right - origin_x),
        height=max(1, bottom - origin_y),
    )


@dataclass
class MouseCenterZone:
    """Normalized center region relative to virtual-desktop geometric center."""
    center_nx: float = 0.0
    center_ny: float = 0.0
    half_width: float = 0.25
    half_height: float = 0.25

    def clamped(self) -> "MouseCenterZone":
        return MouseCenterZone(
            center_nx=clamp(self.center_nx, -1.0, 1.0),
            center_ny=clamp(self.center_ny, -1.0, 1.0),
            half_width=clamp(self.half_width, MOUSE_ZONE_HALF_MIN, MOUSE_ZONE_HALF_MAX),
            half_height=clamp(self.half_height, MOUSE_ZONE_HALF_MIN, MOUSE_ZONE_HALF_MAX),
        )

    @staticmethod
    def from_norm_edges(
            left: float,
            right: float,
            bottom: float,
            top: float) -> "MouseCenterZone":
        """Build zone from normalized edges (Y-up: bottom <= top). Clamps edges to screen bounds."""
        left, right = min(left, right), max(left, right)
        bottom, top = min(bottom, top), max(bottom, top)
        left = clamp(left, -1.0, 1.0)
        right = clamp(right, -1.0, 1.0)
        bottom = clamp(bottom, -1.0, 1.0)
        top = clamp(top, -1.0, 1.0)

        min_span = 2.0 * MOUSE_ZONE_HALF_MIN
        if right - left < min_span:
            center_x = (left + right) * 0.5
            left = clamp(center_x - MOUSE_ZONE_HALF_MIN, -1.0, 1.0)
            right = clamp(center_x + MOUSE_ZONE_HALF_MIN, -1.0, 1.0)
            if right - left < min_span:
                if left <= -1.0 + min_span:
                    right = min(1.0, left + min_span)
                else:
                    left = max(-1.0, right - min_span)
        if top - bottom < min_span:
            center_y = (bottom + top) * 0.5
            bottom = clamp(center_y - MOUSE_ZONE_HALF_MIN, -1.0, 1.0)
            top = clamp(center_y + MOUSE_ZONE_HALF_MIN, -1.0, 1.0)
            if top - bottom < min_span:
                if bottom <= -1.0 + min_span:
                    top = min(1.0, bottom + min_span)
                else:
                    bottom = max(-1.0, top - min_span)

        half_width = (right - left) * 0.5
        half_height = (top - bottom) * 0.5
        return MouseCenterZone(
            center_nx=(left + right) * 0.5,
            center_ny=(bottom + top) * 0.5,
            half_width=clamp(half_width, MOUSE_ZONE_HALF_MIN, MOUSE_ZONE_HALF_MAX),
            half_height=clamp(half_height, MOUSE_ZONE_HALF_MIN, MOUSE_ZONE_HALF_MAX),
        ).clamped()

    def with_center_at_preserving_size(self, nx: float, ny: float) -> "MouseCenterZone":
        """Move zone center to (nx, ny) without changing half_width/height (e.g. auto-calibration)."""
        zone = MouseCenterZone(
            center_nx=clamp(nx, -1.0, 1.0),
            center_ny=clamp(ny, -1.0, 1.0),
            half_width=self.half_width,
            half_height=self.half_height,
        ).clamped()
        half_width = zone.half_width
        half_height = zone.half_height
        if zone.center_nx - half_width < -1.0:
            zone.center_nx = -1.0 + half_width
        if zone.center_nx + half_width > 1.0:
            zone.center_nx = 1.0 - half_width
        if zone.center_ny - half_height < -1.0:
            zone.center_ny = -1.0 + half_height
        if zone.center_ny + half_height > 1.0:
            zone.center_ny = 1.0 - half_height
        return zone.clamped()

    def clamped_to_surface(self) -> "MouseCenterZone":
        """Keep the axis-aligned zone inside the normalized screen [-1, 1] box."""
        zone = self.clamped()
        max_half_width = max(0.0, 1.0 - abs(zone.center_nx))
        max_half_height = max(0.0, 1.0 - abs(zone.center_ny))
        if max_half_width < MOUSE_ZONE_HALF_MIN:
            zone.half_width = max_half_width
        else:
            zone.half_width = clamp(
                zone.half_width,
                MOUSE_ZONE_HALF_MIN,
                min(MOUSE_ZONE_HALF_MAX, max_half_width),
            )
        if max_half_height < MOUSE_ZONE_HALF_MIN:
            zone.half_height = max_half_height
        else:
            zone.half_height = clamp(
                zone.half_height,
                MOUSE_ZONE_HALF_MIN,
                min(MOUSE_ZONE_HALF_MAX, max_half_height),
            )
        return zone

    def to_dict(self) -> dict:
        z = self.clamped()
        return {
            "center_nx": z.center_nx,
            "center_ny": z.center_ny,
            "half_width": z.half_width,
            "half_height": z.half_height,
        }

    @staticmethod
    def from_mapping(data: Optional[Mapping[str, object]]) -> "MouseCenterZone":
        if not isinstance(data, dict):
            return MouseCenterZone()
        try:
            return MouseCenterZone(
                center_nx=float(data.get("center_nx", 0.0)),
                center_ny=float(data.get("center_ny", 0.0)),
                half_width=float(data.get("half_width", 0.25)),
                half_height=float(data.get("half_height", 0.25)),
            ).clamped_to_surface()
        except (TypeError, ValueError):
            return MouseCenterZone()


@dataclass
class MouseMocapConfig:
    yaw_scale_rad: float = 0.35
    pitch_scale_rad: float = 0.28
    roll_scale_rad: float = 0.08
    blink_interval_sec: float = 4.0
    blink_duration_sec: float = 0.14
    eye_look_scale: float = 0.85
    eye_blink_strength: float = 0.8
    horizontal_tilt_mix: float = MOUSE_HORIZONTAL_TILT_MIX_DEFAULT
    gaze_neutral_nx: float = 0.0
    gaze_neutral_ny: float = 0.0
    center_zone: MouseCenterZone = field(default_factory=MouseCenterZone)

    def __post_init__(self) -> None:
        self.blink_interval_sec = clamp_blink_interval_sec(self.blink_interval_sec)
        self.horizontal_tilt_mix = clamp_horizontal_tilt_mix(self.horizontal_tilt_mix)
        self.gaze_neutral_nx = clamp(self.gaze_neutral_nx, -1.0, 1.0)
        self.gaze_neutral_ny = clamp(self.gaze_neutral_ny, -1.0, 1.0)
        if isinstance(self.center_zone, dict):
            self.center_zone = MouseCenterZone.from_mapping(self.center_zone)
        else:
            self.center_zone = self.center_zone.clamped_to_surface()


@dataclass
class MouseMocapState:
    last_nx: float = 0.0
    last_ny: float = 0.0
    last_sample_time: float = 0.0


def resolved_mouse_center_zone(zone: MouseCenterZone) -> MouseCenterZone:
    """Zone as used at runtime: clamped and fitted inside the normalized screen box."""
    return zone.clamped_to_surface()


def mouse_center_zone_calibration_point(zone: MouseCenterZone) -> Tuple[float, float]:
    """Normalized point treated as forward/neutral after zone fit (center of center zone)."""
    fitted = resolved_mouse_center_zone(zone)
    return fitted.center_nx, fitted.center_ny


def zone_local_coords(nx: float, ny: float, zone: MouseCenterZone) -> Tuple[float, float]:
    z = resolved_mouse_center_zone(zone)
    local_x = (nx - z.center_nx) / max(z.half_width, 1e-6)
    local_y = (ny - z.center_ny) / max(z.half_height, 1e-6)
    return local_x, local_y


def is_horizontally_outside_center_zone(local_x: float) -> bool:
    return abs(local_x) > 1.0


def is_vertically_outside_center_zone(local_y: float) -> bool:
    return abs(local_y) > 1.0


def build_mouse_dynamic_face_screen_motion(
        nx: float,
        ny: float,
        zone: MouseCenterZone,
        *,
        neutral_center_x: float,
        neutral_center_y: float,
        neutral_face_size: float,
        horizontal_tilt_mix: float) -> Tuple[float, float, float]:
    """
    Build center_x/center_y/face_size for output dynamic enhancement.

    Vertical exit: center_y follows mouse; up shrinks face_size, down enlarges.
    Horizontal exit blends translation (mix=0) vs tilt-only X (mix=1).
    """
    mix = clamp_horizontal_tilt_mix(horizontal_tilt_mix)
    local_x, local_y = zone_local_coords(nx, ny, zone)
    horiz_out = is_horizontally_outside_center_zone(local_x)
    vert_out = is_vertically_outside_center_zone(local_y)

    if not horiz_out and not vert_out:
        return neutral_center_x, neutral_center_y, neutral_face_size

    center_x = neutral_center_x
    center_y = neutral_center_y
    face_size = neutral_face_size

    if vert_out:
        center_y = ny
        face_size = face_size_from_vertical_zone_exit(
            local_y,
            neutral_face_size=neutral_face_size)
        if not horiz_out:
            center_x = nx
        else:
            move_weight = 1.0 - mix
            center_x = neutral_center_x + (nx - neutral_center_x) * move_weight
    elif horiz_out:
        move_weight = 1.0 - mix
        center_x = neutral_center_x + (nx - neutral_center_x) * move_weight

    return center_x, center_y, face_size


def compute_mouse_horizontal_roll_deg(
        local_x: float,
        tilt_limit_deg: float,
        horizontal_tilt_mix: float) -> float:
    """Roll delta (degrees) when mouse is horizontally outside the center zone."""
    if not is_horizontally_outside_center_zone(local_x):
        return 0.0
    mix = clamp_horizontal_tilt_mix(horizontal_tilt_mix)
    if mix <= 0.0 or tilt_limit_deg <= 0.0:
        return 0.0
    signed_local = clamp(local_x, -MOUSE_HORIZONTAL_LOCAL_TILT_FULL, MOUSE_HORIZONTAL_LOCAL_TILT_FULL)
    strength = clamp(
        (abs(signed_local) - 1.0) / max(MOUSE_HORIZONTAL_LOCAL_TILT_FULL - 1.0, 1e-6),
        0.0,
        1.0,
    )
    # Display transform applies -(roll - neutral_roll); negate so mouse-right tilts character right.
    return -math.copysign(strength * tilt_limit_deg, signed_local) * mix


def blend_mouse_head_roll_degrees(
        pose_roll_deg: float,
        neutral_roll_deg: float,
        local_x: float,
        tilt_limit_deg: float,
        horizontal_tilt_mix: float) -> float:
    """mix=1 → horizontal tilt only; mix=0 → neutral roll (no display tilt)."""
    mix = clamp_horizontal_tilt_mix(horizontal_tilt_mix)
    if not is_horizontally_outside_center_zone(local_x):
        return pose_roll_deg
    horizontal_roll = compute_mouse_horizontal_roll_deg(local_x, tilt_limit_deg, 1.0)
    pose_delta = (pose_roll_deg - neutral_roll_deg) * (1.0 - mix)
    return neutral_roll_deg + pose_delta + horizontal_roll * mix


def mouse_gaze_relative_coords(
        nx: float,
        ny: float,
        config: MouseMocapConfig) -> Tuple[float, float]:
    """Screen mouse relative to calibrated forward-gaze point (0,0 = looking straight ahead)."""
    return (
        clamp(nx - config.gaze_neutral_nx, -1.0, 1.0),
        clamp(ny - config.gaze_neutral_ny, -1.0, 1.0),
    )


def sample_global_mouse_normalized() -> Tuple[float, float]:
    """Map virtual-desktop mouse position to [-1, 1], Y up."""
    pos = wx.GetMousePosition()
    surface = get_mouse_tracking_surface()
    nx = clamp((pos.x - surface.center_x) / surface.half_width, -1.0, 1.0)
    ny = clamp((surface.center_y - pos.y) / surface.half_height, -1.0, 1.0)
    return nx, ny


def is_mouse_inside_center_zone(nx: float, ny: float, zone: MouseCenterZone) -> bool:
    z = resolved_mouse_center_zone(zone)
    local_x = (nx - z.center_nx) / max(z.half_width, 1e-6)
    local_y = (ny - z.center_ny) / max(z.half_height, 1e-6)
    return abs(local_x) <= 1.0 and abs(local_y) <= 1.0


def face_size_from_vertical_zone_exit(
        local_y: float,
        *,
        neutral_face_size: float) -> float:
    """
    Map vertical exit beyond center zone to face_size for output dynamic enhancement.

    local_y > 1 (up / screen-top side): shrink below neutral.
    local_y < -1 (down): enlarge above neutral.
    Strength grows with |local_y| - 1 past the zone edge.
    """
    if not is_vertically_outside_center_zone(local_y):
        return neutral_face_size
    overshoot = abs(local_y) - 1.0
    if local_y > 1.0:
        delta = -MOUSE_VERTICAL_FACE_SIZE_DELTA_PER_UNIT * overshoot
    else:
        delta = MOUSE_VERTICAL_FACE_SIZE_DELTA_PER_UNIT * overshoot
    return clamp(
        neutral_face_size + delta,
        MOUSE_FACE_SIZE_MIN,
        MOUSE_FACE_SIZE_MAX)


def face_size_from_zone_distance(nx: float, ny: float, zone: MouseCenterZone) -> float:
    """Legacy helper: face_size at zone center (used by ix-023 calibration baseline)."""
    z = resolved_mouse_center_zone(zone)
    local_x = (nx - z.center_nx) / max(z.half_width, 1e-6)
    local_y = (ny - z.center_ny) / max(z.half_height, 1e-6)
    if abs(local_x) <= 1.0 and abs(local_y) <= 1.0:
        return MOUSE_DEFAULT_FACE_SIZE
    distance = math.sqrt(local_x * local_x + local_y * local_y)
    return clamp(
        MOUSE_DEFAULT_FACE_SIZE + MOUSE_VERTICAL_FACE_SIZE_DELTA_PER_UNIT * max(0.0, distance - 1.0),
        MOUSE_FACE_SIZE_MIN,
        MOUSE_FACE_SIZE_MAX)


def extract_head_roll_degrees(mediapipe_face_pose: MediaPipeFacePose) -> float:
    matrix = mediapipe_face_pose.xform_matrix[0:3, 0:3]
    rot = Rotation.from_matrix(matrix)
    euler_angles = rot.as_euler("xyz", degrees=True)
    return float(euler_angles[2])


def build_blink_blendshapes(
        now: float,
        blink_interval: float,
        blink_duration: float,
        blink_strength: float) -> Dict[str, float]:
    blink_interval = clamp_blink_interval_sec(blink_interval)
    if blink_interval <= 0.0 or blink_duration <= 0.0:
        return {}
    phase = now % blink_interval
    if phase >= blink_duration:
        return {}
    half = blink_duration * 0.5
    if phase <= half:
        amount = phase / half
    else:
        amount = (blink_duration - phase) / half
    value = clamp(amount, 0.0, 1.0) * blink_strength
    return {
        EYE_BLINK_LEFT: value,
        EYE_BLINK_RIGHT: value,
    }


def build_eye_look_blendshapes(nx: float, ny: float, scale: float) -> Dict[str, float]:
    nx = clamp(nx, -1.0, 1.0)
    ny = clamp(ny, -1.0, 1.0)
    result = {
        EYE_LOOK_IN_LEFT: 0.0,
        EYE_LOOK_OUT_LEFT: 0.0,
        EYE_LOOK_IN_RIGHT: 0.0,
        EYE_LOOK_OUT_RIGHT: 0.0,
        EYE_LOOK_UP_LEFT: 0.0,
        EYE_LOOK_UP_RIGHT: 0.0,
        EYE_LOOK_DOWN_LEFT: 0.0,
        EYE_LOOK_DOWN_RIGHT: 0.0,
    }
    look_nx = -nx
    horizontal = abs(look_nx) * scale
    if look_nx > 0.0:
        result[EYE_LOOK_IN_LEFT] = horizontal
        result[EYE_LOOK_OUT_RIGHT] = horizontal
    elif look_nx < 0.0:
        result[EYE_LOOK_OUT_LEFT] = horizontal
        result[EYE_LOOK_IN_RIGHT] = horizontal

    vertical = abs(ny) * scale
    if ny > 0.0:
        result[EYE_LOOK_UP_LEFT] = vertical
        result[EYE_LOOK_UP_RIGHT] = vertical
    elif ny < 0.0:
        result[EYE_LOOK_DOWN_LEFT] = vertical
        result[EYE_LOOK_DOWN_RIGHT] = vertical
    return result


def build_head_xform_matrix(
        nx: float,
        ny: float,
        yaw_scale: float,
        pitch_scale: float,
        roll_scale: float) -> numpy.ndarray:
    nx = clamp(nx, -1.0, 1.0)
    ny = clamp(ny, -1.0, 1.0)
    # Match eye horizontal axis (look_nx = -nx) so head/body yaw follows mouse left-right.
    head_nx = -nx
    pitch = -ny * pitch_scale
    yaw = -head_nx * yaw_scale
    roll = head_nx * ny * roll_scale
    rotation = Rotation.from_euler("xyz", [pitch, yaw, roll], degrees=False)
    matrix = numpy.eye(4, dtype=numpy.float64)
    matrix[0:3, 0:3] = rotation.as_matrix()
    return matrix


def build_mouse_mediapipe_face_pose(
        now: Optional[float] = None,
        config: Optional[MouseMocapConfig] = None,
        nx: Optional[float] = None,
        ny: Optional[float] = None) -> Tuple[MediaPipeFacePose, float, float]:
    if now is None:
        now = time.time()
    if config is None:
        config = MouseMocapConfig()
    if nx is None or ny is None:
        nx, ny = sample_global_mouse_normalized()

    gaze_nx, gaze_ny = mouse_gaze_relative_coords(nx, ny, config)
    blendshape_params = {name: 0.0 for name in BLENDSHAPE_NAMES}
    blendshape_params.update(build_eye_look_blendshapes(gaze_nx, gaze_ny, config.eye_look_scale))
    blendshape_params.update(build_blink_blendshapes(
        now,
        config.blink_interval_sec,
        config.blink_duration_sec,
        config.eye_blink_strength))
    xform_matrix = build_head_xform_matrix(
        gaze_nx,
        gaze_ny,
        config.yaw_scale_rad,
        config.pitch_scale_rad,
        config.roll_scale_rad)
    return MediaPipeFacePose(blendshape_params, xform_matrix), nx, ny
