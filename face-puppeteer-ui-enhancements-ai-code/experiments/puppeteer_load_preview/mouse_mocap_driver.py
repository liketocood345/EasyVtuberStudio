"""Synthetic MediaPipeFacePose from global screen mouse + procedural blink."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

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
MOCAP_INPUT_MODE_MOUSE_AUDIO = "mouse_audio"
MOCAP_INPUT_MODE_VALUES = (MOCAP_INPUT_MODE_MEDIAPIPE, MOCAP_INPUT_MODE_MOUSE_AUDIO)
MOCAP_INPUT_MODE_LABELS = (
    "Face capture (MediaPipe) / 摄像头面捕",
    "Mouse + Audio (EasyVtuber) / 鼠标+音频",
)


def normalize_mocap_input_mode(value: object) -> str:
    if value == MOCAP_INPUT_MODE_MOUSE_AUDIO:
        return MOCAP_INPUT_MODE_MOUSE_AUDIO
    return MOCAP_INPUT_MODE_MEDIAPIPE


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass
class MouseMocapConfig:
    yaw_scale_rad: float = 0.35
    pitch_scale_rad: float = 0.28
    roll_scale_rad: float = 0.08
    blink_interval_sec: float = 4.0
    blink_duration_sec: float = 0.14
    eye_look_scale: float = 0.85
    eye_blink_strength: float = 0.8


@dataclass
class MouseMocapState:
    last_nx: float = 0.0
    last_ny: float = 0.0
    last_sample_time: float = 0.0


def sample_global_mouse_normalized() -> Tuple[float, float]:
    """Map primary-screen mouse position to [-1, 1], Y up."""
    pos = wx.GetMousePosition()
    display = wx.Display(0)
    geometry = display.GetGeometry()
    center_x = geometry.x + geometry.width * 0.5
    center_y = geometry.y + geometry.height * 0.5
    half_width = max(geometry.width * 0.5, 1.0)
    half_height = max(geometry.height * 0.5, 1.0)
    nx = clamp((pos.x - center_x) / half_width, -1.0, 1.0)
    ny = clamp((center_y - pos.y) / half_height, -1.0, 1.0)
    return nx, ny


def build_blink_blendshapes(
        now: float,
        blink_interval: float,
        blink_duration: float,
        blink_strength: float) -> Dict[str, float]:
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
    horizontal = abs(nx) * scale
    if nx > 0.0:
        # Look right: left eye in, right eye out (matches converter iris_rotation_y sign).
        result[EYE_LOOK_IN_LEFT] = horizontal
        result[EYE_LOOK_OUT_RIGHT] = horizontal
    elif nx < 0.0:
        # Look left: left eye out, right eye in.
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
    pitch = -ny * pitch_scale
    yaw = -nx * yaw_scale
    roll = nx * ny * roll_scale
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

    blendshape_params = {name: 0.0 for name in BLENDSHAPE_NAMES}
    blendshape_params.update(build_eye_look_blendshapes(nx, ny, config.eye_look_scale))
    blendshape_params.update(build_blink_blendshapes(
        now,
        config.blink_interval_sec,
        config.blink_duration_sec,
        config.eye_blink_strength))
    xform_matrix = build_head_xform_matrix(
        nx,
        ny,
        config.yaw_scale_rad,
        config.pitch_scale_rad,
        config.roll_scale_rad)
    return MediaPipeFacePose(blendshape_params, xform_matrix), nx, ny
