"""OpenSeeFace UDP frames -> synthetic MediaPipeFacePose for THA4 converter."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy
from scipy.spatial.transform import Rotation

from tha4.mocap.mediapipe_constants import (
    BLENDSHAPE_NAMES,
    BROW_INNER_UP,
    BROW_OUTER_UP_LEFT,
    BROW_OUTER_UP_RIGHT,
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
    JAW_OPEN,
    MOUTH_FUNNEL,
)
from tha4.mocap.mediapipe_face_pose import MediaPipeFacePose

from openseeface_packet import OpenSeeFaceFrame, OSF_FEATURE_NAMES, OSF_PREVIEW_WINDOW_TITLE
OSF_DEFAULT_UDP_PORT = 11573
OSF_DEFAULT_FPS = 12
OSF_CAPTURE_WIDTH_DEFAULT = 1280
OSF_CAPTURE_HEIGHT_DEFAULT = 720
OSF_CAPTURE_WIDTH_MIN = 320
OSF_CAPTURE_HEIGHT_MIN = 240
OSF_CAPTURE_WIDTH_MAX = 1920
OSF_CAPTURE_HEIGHT_MAX = 1080
OSF_DEFAULT_FPS = 12
OSF_VISUALIZE_MIN = 1
OSF_VISUALIZE_MAX = 4
OSF_VISUALIZE_DEFAULT = 3
OSF_CAMERA_LIST_TIMEOUT_SEC = 6.0
OSF_PREVIEW_HWND_POLL_SEC = 0.5
OSF_PREVIEW_HWND_TIMEOUT_SEC = 15.0
OSF_UDP_DISCONNECT_SEC = 5.0
OSF_CALIBRATION_WARMUP_PACKETS = 12
OSF_DYNAMIC_TRANSLATION_SCALE = 0.3
OSF_DEFAULT_FACE_SIZE = 0.30
OSF_FORWARD_RECENTER_YAW_DEG = 10.0
OSF_FORWARD_RECENTER_PITCH_DEG = 10.0
OSF_CAPTURE_SIZE_PRESETS: tuple[tuple[str, int, int], ...] = (
    ("640×360", 640, 360),
    ("1280×720", 1280, 720),
    ("1920×1080", 1920, 1080),
)
OSF_BREATH_CYCLE_SEC = 4.0
OSF_EYE_BLINK_FEATURE_GAIN = 1.5
OSF_PUPIL_CONFIDENCE_MIN = 0.20
OSF_EYE_OPEN_GAZE_MIN = 0.30
# Per-eye closure tiers (0=open .. 1=fully closed).
OSF_EYE_PEAK_MIN = 0.20
OSF_EYE_FULL_CLOSE_THRESHOLD = 0.72
OSF_EYE_SQUINT_FEATURE_CEIL = -0.6
# Spatial: |L-R| at/above this => single-eye wink (check before both-eyes).
OSF_EYE_ASYMMETRY_MIN = 0.16
OSF_EYE_GHOST_BLINK_CAP = 0.12
# Hold peaks across pacer gaps (seconds).
OSF_EYE_BLINK_HOLD_SEC = 0.11
OSF_EYE_WINK_HOLD_SEC = 0.20
# Temporal: sustained closure vs transient blink (seconds).
OSF_EYE_CLOSE_MIN_DURATION_SEC = 0.42


class OsfEyeMotionPattern(str, Enum):
    OPEN = "open"
    BLINK_BOTH = "blink_both"
    CLOSE_BOTH = "close_both"
    WINK_LEFT = "wink_left"
    WINK_RIGHT = "wink_right"


@dataclass(frozen=True)
class OsfPerEyeSample:
    eyelid_feature: float
    eye_open: float
    pupil_tracked: bool


@dataclass(frozen=True)
class OsfEyeMotionResult:
    pattern: OsfEyeMotionPattern
    left: float
    right: float


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _osf_feature_value(frame: OpenSeeFaceFrame, name: str) -> float:
    try:
        index = OSF_FEATURE_NAMES.index(name)
        return float(frame.features[index])
    except (ValueError, IndexError):
        return 0.0


def _osf_blink_from_eyelid_feature(eye_feature: float) -> float:
    """Eyelid AU only: squint (partial) vs full close."""
    feature = float(eye_feature)
    if feature <= OSF_EYE_SQUINT_FEATURE_CEIL:
        return clamp(
            -feature * OSF_EYE_BLINK_FEATURE_GAIN,
            0.0,
            1.0,
        )
    if feature < 0.1:
        return clamp(-feature, 0.0, 0.55)
    return 0.0


def osf_pupil_is_tracked(pupil_confidence: float, eye_open: float) -> bool:
    """Match OpenSeeFace facetracker gaze/pupil visibility gates."""
    return (
        float(pupil_confidence) >= OSF_PUPIL_CONFIDENCE_MIN
        and float(eye_open) >= OSF_EYE_OPEN_GAZE_MIN
    )


def _osf_per_eye_sample_from_frame(
        frame: OpenSeeFaceFrame,
        *,
        side: str) -> OsfPerEyeSample:
    if side == "left":
        return OsfPerEyeSample(
            eyelid_feature=_osf_feature_value(frame, "EyeLeft"),
            eye_open=float(frame.left_eye_open),
            pupil_tracked=osf_pupil_is_tracked(
                frame.left_pupil_confidence,
                frame.left_eye_open,
            ),
        )
    return OsfPerEyeSample(
        eyelid_feature=_osf_feature_value(frame, "EyeRight"),
        eye_open=float(frame.right_eye_open),
        pupil_tracked=osf_pupil_is_tracked(
            frame.right_pupil_confidence,
            frame.right_eye_open,
        ),
    )


def measure_osf_per_eye_closure(sample: OsfPerEyeSample) -> float:
    """Raw per-eye closure before pattern classification."""
    blink_from_feature = _osf_blink_from_eyelid_feature(sample.eyelid_feature)
    if not sample.pupil_tracked:
        return blink_from_feature
    blink_from_open = clamp(1.0 - float(sample.eye_open), 0.0, 1.0)
    return max(blink_from_feature, blink_from_open)


def classify_osf_eye_motion_pattern(left: float, right: float) -> OsfEyeMotionPattern:
    """Spatial classification: asymmetry first, then both-eyes."""
    left = float(left)
    right = float(right)
    peak = max(left, right)
    if peak < OSF_EYE_PEAK_MIN:
        return OsfEyeMotionPattern.OPEN
    delta = abs(left - right)
    if delta >= OSF_EYE_ASYMMETRY_MIN:
        return (
            OsfEyeMotionPattern.WINK_LEFT
            if left > right
            else OsfEyeMotionPattern.WINK_RIGHT
        )
    if peak >= OSF_EYE_FULL_CLOSE_THRESHOLD:
        return OsfEyeMotionPattern.CLOSE_BOTH
    return OsfEyeMotionPattern.BLINK_BOTH


def _suppress_osf_peer_eye_closure(peer: float) -> float:
    """Keep the open eye open during deliberate single-eye closure."""
    peer = float(peer)
    if peer <= OSF_EYE_GHOST_BLINK_CAP:
        return clamp(peer, 0.0, 1.0)
    bleed = max(0.0, peer - OSF_EYE_GHOST_BLINK_CAP)
    return clamp(OSF_EYE_GHOST_BLINK_CAP + bleed * 0.15, 0.0, 1.0)


def apply_osf_eye_motion_pattern(
        pattern: OsfEyeMotionPattern,
        left: float,
        right: float) -> tuple[float, float]:
    """Map classified pattern to THA4-bound per-eye blink strengths."""
    if pattern == OsfEyeMotionPattern.OPEN:
        return 0.0, 0.0
    if pattern == OsfEyeMotionPattern.WINK_LEFT:
        return clamp(left, 0.0, 1.0), _suppress_osf_peer_eye_closure(right)
    if pattern == OsfEyeMotionPattern.WINK_RIGHT:
        return _suppress_osf_peer_eye_closure(left), clamp(right, 0.0, 1.0)
    if pattern == OsfEyeMotionPattern.BLINK_BOTH:
        blink = max(float(left), float(right))
        return clamp(blink, 0.0, 1.0), clamp(blink, 0.0, 1.0)
    if pattern == OsfEyeMotionPattern.CLOSE_BOTH:
        close = max(float(left), float(right))
        if close >= OSF_EYE_FULL_CLOSE_THRESHOLD * 0.75:
            close = max(close, 0.88)
        return clamp(close, 0.0, 1.0), clamp(close, 0.0, 1.0)
    return clamp(left, 0.0, 1.0), clamp(right, 0.0, 1.0)


def refine_osf_eye_motion_temporal(
        state: OpenSeeFaceMocapState,
        pattern: OsfEyeMotionPattern,
        left: float,
        right: float,
        now_mono: float) -> OsfEyeMotionPattern:
    """Distinguish transient blink-both from sustained close-both (never merge winks)."""
    if pattern == OsfEyeMotionPattern.OPEN:
        state.eye_both_active_mono = None
        state.eye_closure_peak_mono = 0.0
        return pattern

    if pattern in (OsfEyeMotionPattern.WINK_LEFT, OsfEyeMotionPattern.WINK_RIGHT):
        state.eye_both_active_mono = None
        state.eye_prev_left = float(left)
        state.eye_prev_right = float(right)
        state.eye_last_pattern = pattern.value
        return pattern

    if pattern not in (OsfEyeMotionPattern.BLINK_BOTH, OsfEyeMotionPattern.CLOSE_BOTH):
        return pattern

    if state.eye_both_active_mono is None:
        state.eye_both_active_mono = float(now_mono)
    active_sec = max(0.0, float(now_mono) - float(state.eye_both_active_mono))
    peak = max(float(left), float(right))
    if peak >= OSF_EYE_FULL_CLOSE_THRESHOLD:
        pattern = (
            OsfEyeMotionPattern.CLOSE_BOTH
            if active_sec >= OSF_EYE_CLOSE_MIN_DURATION_SEC
            else OsfEyeMotionPattern.BLINK_BOTH
        )
    elif active_sec >= OSF_EYE_CLOSE_MIN_DURATION_SEC * 1.4:
        pattern = OsfEyeMotionPattern.CLOSE_BOTH
    else:
        pattern = OsfEyeMotionPattern.BLINK_BOTH

    rising = (
        float(left) - float(state.eye_prev_left) > 0.16
        or float(right) - float(state.eye_prev_right) > 0.16
    )
    if rising:
        state.eye_closure_peak_mono = float(now_mono)

    state.eye_prev_left = float(left)
    state.eye_prev_right = float(right)
    state.eye_last_pattern = pattern.value
    return pattern


def _osf_eye_hold_duration(pattern: OsfEyeMotionPattern) -> float:
    if pattern in (OsfEyeMotionPattern.WINK_LEFT, OsfEyeMotionPattern.WINK_RIGHT):
        return OSF_EYE_WINK_HOLD_SEC
    if pattern in (OsfEyeMotionPattern.BLINK_BOTH, OsfEyeMotionPattern.CLOSE_BOTH):
        return OSF_EYE_BLINK_HOLD_SEC
    return 0.0


def apply_osf_eye_output_hold(
        state: OpenSeeFaceMocapState,
        left: float,
        right: float,
        pattern: OsfEyeMotionPattern,
        now_mono: float) -> tuple[float, float]:
    """Keep blink/wink peaks visible across low-fps pacer gaps."""
    now_mono = float(now_mono)
    if pattern != OsfEyeMotionPattern.OPEN:
        state.eye_hold_left = max(float(state.eye_hold_left), float(left))
        state.eye_hold_right = max(float(state.eye_hold_right), float(right))
        hold_sec = _osf_eye_hold_duration(pattern)
        if hold_sec > 0.0:
            state.eye_hold_until_mono = max(
                float(state.eye_hold_until_mono),
                now_mono + hold_sec,
            )
        return state.eye_hold_left, state.eye_hold_right

    if now_mono <= float(state.eye_hold_until_mono):
        return float(state.eye_hold_left), float(state.eye_hold_right)

    state.eye_hold_left = 0.0
    state.eye_hold_right = 0.0
    state.eye_hold_until_mono = 0.0
    return 0.0, 0.0


def resolve_osf_eye_motion(
        frame: OpenSeeFaceFrame,
        state: OpenSeeFaceMocapState,
        now_mono: float) -> OsfEyeMotionResult:
    left_sample = _osf_per_eye_sample_from_frame(frame, side="left")
    right_sample = _osf_per_eye_sample_from_frame(frame, side="right")
    raw_left = measure_osf_per_eye_closure(left_sample)
    raw_right = measure_osf_per_eye_closure(right_sample)

    pattern = classify_osf_eye_motion_pattern(raw_left, raw_right)
    pattern = refine_osf_eye_motion_temporal(
        state, pattern, raw_left, raw_right, now_mono)
    left, right = apply_osf_eye_motion_pattern(pattern, raw_left, raw_right)
    left, right = apply_osf_eye_output_hold(state, left, right, pattern, now_mono)
    return OsfEyeMotionResult(pattern=pattern, left=left, right=right)


def osf_eye_blinks_from_frame(
        frame: OpenSeeFaceFrame,
        state: Optional[OpenSeeFaceMocapState] = None,
        now_mono: Optional[float] = None) -> tuple[float, float]:
    if state is None:
        state = OpenSeeFaceMocapState()
    if now_mono is None:
        now_mono = time.monotonic()
    motion = resolve_osf_eye_motion(frame, state, float(now_mono))
    return motion.left, motion.right


def clamp_osf_visualize_level(value: object) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        level = OSF_VISUALIZE_DEFAULT
    return int(clamp(level, OSF_VISUALIZE_MIN, OSF_VISUALIZE_MAX))

def clamp_osf_fps(value: object) -> int:
    try:
        fps = int(value)
    except (TypeError, ValueError):
        fps = OSF_DEFAULT_FPS
    return int(clamp(fps, 1, 60))


def clamp_osf_capture_width(value: object) -> int:
    try:
        width = int(value)
    except (TypeError, ValueError):
        width = OSF_CAPTURE_WIDTH_DEFAULT
    width = int(clamp(width, OSF_CAPTURE_WIDTH_MIN, OSF_CAPTURE_WIDTH_MAX))
    return width - (width % 2)


def clamp_osf_capture_height(value: object) -> int:
    try:
        height = int(value)
    except (TypeError, ValueError):
        height = OSF_CAPTURE_HEIGHT_DEFAULT
    height = int(clamp(height, OSF_CAPTURE_HEIGHT_MIN, OSF_CAPTURE_HEIGHT_MAX))
    return height - (height % 2)


def osf_capture_preset_index_for_size(width: int, height: int) -> int:
    for idx, (_label, preset_w, preset_h) in enumerate(OSF_CAPTURE_SIZE_PRESETS):
        if int(width) == preset_w and int(height) == preset_h:
            return idx
    return 1


def osf_capture_size_from_preset_index(index: object) -> tuple[int, int]:
    try:
        idx = int(index)
    except (TypeError, ValueError):
        idx = 1
    idx = int(clamp(idx, 0, len(OSF_CAPTURE_SIZE_PRESETS) - 1))
    _label, width, height = OSF_CAPTURE_SIZE_PRESETS[idx]
    return clamp_osf_capture_width(width), clamp_osf_capture_height(height)


def normalize_osf_camera_label(label: str) -> str:
    return str(label or "").strip().casefold()


@dataclass(frozen=True)
class OpenSeeFaceScreenMotion:
    center_x: float
    center_y: float
    face_size: float


@dataclass
class OpenSeeFaceMocapState:
    rotation_offset: Optional[list[float]] = None
    translation_offset: Optional[tuple[float, float, float]] = None
    calibration_warmup_remaining: int = OSF_CALIBRATION_WARMUP_PACKETS
    latest_screen_motion: Optional[OpenSeeFaceScreenMotion] = None
    latest_head_pitch_deg: float = 0.0
    latest_head_yaw_deg: float = 0.0
    latest_head_roll_deg: float = 0.0
    head_near_forward: bool = False
    last_packet_mono: float = 0.0
    packets_received: int = 0
    preview_lost: bool = False
    preview_status: str = ""
    udp_connected: bool = False
    iris_smooth_x: float = 0.0
    iris_smooth_y: float = 0.0
    eye_prev_left: float = 0.0
    eye_prev_right: float = 0.0
    eye_both_active_mono: Optional[float] = None
    eye_closure_peak_mono: float = 0.0
    eye_last_pattern: str = OsfEyeMotionPattern.OPEN.value
    eye_hold_left: float = 0.0
    eye_hold_right: float = 0.0
    eye_hold_until_mono: float = 0.0


def _breath_value(now_mono: float) -> float:
    elapsed = now_mono % OSF_BREATH_CYCLE_SEC
    return math.sin(elapsed / OSF_BREATH_CYCLE_SEC * math.pi)

def angle_delta_deg(current: float, reference: float) -> float:
    """Shortest signed delta on a circle (degrees), e.g. 165° vs -150° -> 15°."""
    return (float(current) - float(reference) + 180.0) % 360.0 - 180.0


def osf_packet_quaternion_to_rotation(
        qx: float,
        qy: float,
        qz: float,
        qw: float) -> Rotation:
    """Match Unity OpenSeeIKTarget convertedQuaternion (x,y,z,w)."""
    return Rotation.from_quat([-float(qy), -float(qx), float(qz), float(qw)])


def osf_rotation_to_packet_quaternion(rotation: Rotation) -> tuple[float, float, float, float]:
    """Inverse of osf_packet_quaternion_to_rotation for synthetic UDP packets."""
    cx, cy, cz, cw = rotation.as_quat()
    return (-float(cy), -float(cx), float(cz), float(cw))


def osf_head_rotation_delta_deg(
        frame: OpenSeeFaceFrame,
        state: OpenSeeFaceMocapState) -> tuple[float, float, float]:
    rot_off = state.rotation_offset or [0.0, 0.0, 0.0]
    pitch_deg = -angle_delta_deg(frame.rotation_x, rot_off[0])
    yaw_deg = -angle_delta_deg(frame.rotation_y, rot_off[1])
    roll_deg = angle_delta_deg(frame.rotation_z, rot_off[2])
    return pitch_deg, yaw_deg, roll_deg


def osf_head_is_near_forward(
        frame: OpenSeeFaceFrame,
        state: OpenSeeFaceMocapState,
        *,
        yaw_threshold_deg: float = OSF_FORWARD_RECENTER_YAW_DEG,
        pitch_threshold_deg: float = OSF_FORWARD_RECENTER_PITCH_DEG) -> bool:
    if state.calibration_warmup_remaining > 0:
        return False
    pitch_deg, yaw_deg, _roll_deg = osf_head_rotation_delta_deg(frame, state)
    return (
        abs(yaw_deg) <= float(yaw_threshold_deg)
        and abs(pitch_deg) <= float(pitch_threshold_deg))


def _osf_head_rotation_from_frame(
        frame: OpenSeeFaceFrame,
        state: OpenSeeFaceMocapState) -> Rotation:
    """Euler deltas from OSF packet angles (MediaPipe converter also uses xyz euler)."""
    if state.calibration_warmup_remaining > 0:
        state.calibration_warmup_remaining -= 1
        state.rotation_offset = [
            frame.rotation_x,
            frame.rotation_y,
            frame.rotation_z,
        ]
        state.translation_offset = (
            float(frame.translation_x),
            float(frame.translation_y),
            float(frame.translation_z),
        )
        if state.calibration_warmup_remaining > 0:
            return Rotation.identity()

    if state.rotation_offset is None:
        state.rotation_offset = [
            frame.rotation_x,
            frame.rotation_y,
            frame.rotation_z,
        ]

    rot_off = state.rotation_offset or [0.0, 0.0, 0.0]
    pitch_deg = clamp(-angle_delta_deg(frame.rotation_x, rot_off[0]), -45.0, 45.0)
    yaw_deg = clamp(-angle_delta_deg(frame.rotation_y, rot_off[1]), -45.0, 45.0)
    roll_deg = clamp(angle_delta_deg(frame.rotation_z, rot_off[2]), -30.0, 30.0)
    return Rotation.from_euler(
        "xyz",
        [math.radians(pitch_deg), math.radians(yaw_deg), math.radians(roll_deg)],
        degrees=False,
    )


def build_openseeface_face_screen_motion(
        frame: OpenSeeFaceFrame,
        state: OpenSeeFaceMocapState,
        *,
        translation_scale: float = OSF_DYNAMIC_TRANSLATION_SCALE) -> Optional[OpenSeeFaceScreenMotion]:
    """Map OSF translation deltas to output dynamic-enhancement pan/scale inputs."""
    if state.calibration_warmup_remaining > 0:
        return None

    tx = float(frame.translation_x)
    ty = float(frame.translation_y)
    tz = float(frame.translation_z)
    if state.translation_offset is None:
        state.translation_offset = (tx, ty, tz)

    ox, oy, oz = state.translation_offset
    # Match OpenSeeFace Unity IK: lateral (-x), vertical (y), depth (-z), then scale.
    dx = -(tx - ox)
    dy = (ty - oy)
    dz = -(tz - oz)
    gain = max(0.05, float(translation_scale))
    center_x = clamp(dx * gain * 3.0, -1.0, 1.0)
    center_y = clamp(-dy * gain * 3.0, -1.0, 1.0)
    face_size = clamp(
        OSF_DEFAULT_FACE_SIZE - dz * gain * 0.8,
        0.08,
        0.70,
    )
    return OpenSeeFaceScreenMotion(center_x=center_x, center_y=center_y, face_size=face_size)


def build_openseeface_mediapipe_face_pose(
        frame: OpenSeeFaceFrame,
        state: OpenSeeFaceMocapState,
        now_mono: Optional[float] = None) -> MediaPipeFacePose:
    if now_mono is None:
        now_mono = time.monotonic()

    blendshape_params = {name: 0.0 for name in BLENDSHAPE_NAMES}
    eye_motion = resolve_osf_eye_motion(frame, state, float(now_mono))
    blendshape_params[EYE_BLINK_LEFT] = eye_motion.left
    blendshape_params[EYE_BLINK_RIGHT] = eye_motion.right
    blendshape_params[JAW_OPEN] = clamp(max(frame.mouth_open, 0.0) * 2.0, 0.0, 1.0)
    blendshape_params[MOUTH_FUNNEL] = clamp(max(frame.mouth_wide, 0.0), 0.0, 1.0)

    brow_left = clamp(frame.eyebrow_up_down_left, 0.0, 1.0)
    brow_right = clamp(frame.eyebrow_up_down_right, 0.0, 1.0)
    blendshape_params[BROW_INNER_UP] = (brow_left + brow_right) * 0.5
    blendshape_params[BROW_OUTER_UP_LEFT] = brow_left
    blendshape_params[BROW_OUTER_UP_RIGHT] = brow_right

    relative_rotation = _osf_head_rotation_from_frame(frame, state)
    iris_x = -frame.eye_rotation_y * 3.0
    iris_y = frame.eye_rotation_x * 3.0
    state.iris_smooth_x += (iris_x - state.iris_smooth_x) * 0.35
    state.iris_smooth_y += (iris_y - state.iris_smooth_y) * 0.35
    gaze_scale = 0.45
    gx = clamp(state.iris_smooth_x * gaze_scale, -1.0, 1.0)
    gy = clamp(state.iris_smooth_y * gaze_scale, -1.0, 1.0)
    horizontal = abs(gx) * gaze_scale
    vertical = abs(gy) * gaze_scale
    if gx > 0.0:
        blendshape_params[EYE_LOOK_IN_LEFT] = horizontal
        blendshape_params[EYE_LOOK_OUT_RIGHT] = horizontal
    elif gx < 0.0:
        blendshape_params[EYE_LOOK_OUT_LEFT] = horizontal
        blendshape_params[EYE_LOOK_IN_RIGHT] = horizontal
    if gy > 0.0:
        blendshape_params[EYE_LOOK_UP_LEFT] = vertical
        blendshape_params[EYE_LOOK_UP_RIGHT] = vertical
    elif gy < 0.0:
        blendshape_params[EYE_LOOK_DOWN_LEFT] = vertical
        blendshape_params[EYE_LOOK_DOWN_RIGHT] = vertical

    matrix = numpy.eye(4, dtype=numpy.float64)
    matrix[0:3, 0:3] = relative_rotation.as_matrix()

    pitch_deg, yaw_deg, roll_deg = osf_head_rotation_delta_deg(frame, state)
    state.latest_head_pitch_deg = pitch_deg
    state.latest_head_yaw_deg = yaw_deg
    state.latest_head_roll_deg = roll_deg
    state.head_near_forward = osf_head_is_near_forward(frame, state)
    state.latest_screen_motion = build_openseeface_face_screen_motion(frame, state)

    state.last_packet_mono = now_mono
    state.packets_received += 1
    state.udp_connected = True

    return MediaPipeFacePose(blendshape_params, matrix)


def copy_mediapipe_face_pose(pose: MediaPipeFacePose) -> MediaPipeFacePose:
    return MediaPipeFacePose(
        dict(pose.blendshape_params),
        numpy.array(pose.xform_matrix, dtype=numpy.float64, copy=True),
    )


def lerp_mediapipe_face_pose(
        pose_a: MediaPipeFacePose,
        pose_b: MediaPipeFacePose,
        t: float) -> MediaPipeFacePose:
    from scipy.spatial.transform import Slerp

    t = clamp(float(t), 0.0, 1.0)
    keys = set(pose_a.blendshape_params) | set(pose_b.blendshape_params)
    blink_keys = {EYE_BLINK_LEFT, EYE_BLINK_RIGHT}
    blendshape_params = {}
    for key in keys:
        value_a = float(pose_a.blendshape_params.get(key, 0.0))
        value_b = float(pose_b.blendshape_params.get(key, 0.0))
        if key in blink_keys:
            blendshape_params[key] = max(value_a, value_b)
        else:
            blendshape_params[key] = value_a * (1.0 - t) + value_b * t
    rot_a = Rotation.from_matrix(
        numpy.asarray(pose_a.xform_matrix, dtype=numpy.float64)[:3, :3])
    rot_b = Rotation.from_matrix(
        numpy.asarray(pose_b.xform_matrix, dtype=numpy.float64)[:3, :3])
    slerp = Slerp([0.0, 1.0], Rotation.concatenate([rot_a, rot_b]))
    matrix = numpy.eye(4, dtype=numpy.float64)
    matrix[:3, :3] = slerp(t).as_matrix()
    return MediaPipeFacePose(blendshape_params, matrix)


class OpenSeeFaceInputPacer:
    """Buffer bursty OSF UDP poses; emit evenly-spaced lerp segments at target_fps."""

    def __init__(self, *, target_fps: int = OSF_DEFAULT_FPS, max_catchup_frames: int = 2) -> None:
        self.target_fps = clamp_osf_fps(target_fps)
        self.max_catchup_frames = max(1, int(max_catchup_frames))
        self._latest: Optional[MediaPipeFacePose] = None
        self._segment_from: Optional[MediaPipeFacePose] = None
        self._segment_to: Optional[MediaPipeFacePose] = None
        self._segment_start_mono = 0.0
        self._next_keyframe_mono = 0.0
        self._current: Optional[MediaPipeFacePose] = None
        self._keyframe_pending = False

    def reset(self) -> None:
        self._latest = None
        self._segment_from = None
        self._segment_to = None
        self._segment_start_mono = 0.0
        self._next_keyframe_mono = 0.0
        self._current = None
        self._keyframe_pending = False

    def set_target_fps(self, fps: int) -> None:
        self.target_fps = clamp_osf_fps(fps)

    def push_latest(self, pose: MediaPipeFacePose) -> None:
        self._latest = copy_mediapipe_face_pose(pose)
        if self._current is None:
            now = time.monotonic()
            seed = copy_mediapipe_face_pose(pose)
            self._current = seed
            self._segment_from = copy_mediapipe_face_pose(pose)
            self._segment_to = copy_mediapipe_face_pose(pose)
            self._segment_start_mono = now
            self._next_keyframe_mono = now

    def has_pending_keyframe(self) -> bool:
        return self._keyframe_pending

    def pop_keyframe_pending(self) -> bool:
        pending = self._keyframe_pending
        self._keyframe_pending = False
        return pending

    def update(self, now_mono: Optional[float] = None) -> tuple[Optional[MediaPipeFacePose], bool]:
        if self._latest is None:
            return self._current, False
        if now_mono is None:
            now_mono = time.monotonic()
        interval = 1.0 / float(max(1, self.target_fps))
        keyframe_committed = False

        catchup = 0
        while catchup < self.max_catchup_frames and now_mono >= self._next_keyframe_mono:
            self._segment_from = (
                copy_mediapipe_face_pose(self._segment_to)
                if self._segment_to is not None
                else copy_mediapipe_face_pose(self._latest))
            self._segment_to = copy_mediapipe_face_pose(self._latest)
            if self._next_keyframe_mono <= 0.0:
                self._segment_start_mono = now_mono
                self._next_keyframe_mono = now_mono + interval
            else:
                self._segment_start_mono = self._next_keyframe_mono
                self._next_keyframe_mono += interval
            self._keyframe_pending = True
            keyframe_committed = True
            catchup += 1

        if self._segment_from is None or self._segment_to is None:
            self._current = copy_mediapipe_face_pose(self._latest)
            return self._current, keyframe_committed

        elapsed = max(0.0, now_mono - self._segment_start_mono)
        t = clamp(elapsed / interval, 0.0, 1.0)
        self._current = lerp_mediapipe_face_pose(self._segment_from, self._segment_to, t)
        return self._current, keyframe_committed
