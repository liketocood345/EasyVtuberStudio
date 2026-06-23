"""Parse OpenSeeFace UDP tracking packets (binary protocol, port 11573)."""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Optional, Tuple

OSF_UDP_STRUCT_FORMAT = "=di2f2fB1f4f3f3f68f136f210f14f"
OSF_UDP_PACKET_SIZE = struct.calcsize(OSF_UDP_STRUCT_FORMAT)
OSF_UDP_VALUE_COUNT = len(struct.unpack(OSF_UDP_STRUCT_FORMAT, b"\x00" * OSF_UDP_PACKET_SIZE))

OSF_PREVIEW_WINDOW_TITLE = "OpenSeeFace Visualization"

OSF_LANDMARK_CONFIDENCE_BASE = 18
OSF_RIGHT_PUPIL_LANDMARK = 66
OSF_LEFT_PUPIL_LANDMARK = 67

OSF_FEATURE_NAMES = (
    "EyeLeft",
    "EyeRight",
    "EyebrowSteepnessLeft",
    "EyebrowUpDownLeft",
    "EyebrowQuirkLeft",
    "EyebrowSteepnessRight",
    "EyebrowUpDownRight",
    "EyebrowQuirkRight",
    "MouthCornerUpDownLeft",
    "MouthCornerInOutLeft",
    "MouthCornerUpDownRight",
    "MouthCornerInOutRight",
    "MouthOpen",
    "MouthWide",
)


@dataclass(frozen=True)
class OpenSeeFaceFrame:
    time: float
    track_id: int
    camera_width: float
    camera_height: float
    right_eye_open: float
    left_eye_open: float
    left_pupil_confidence: float
    right_pupil_confidence: float
    fit3d_error: float
    raw_euler_x: float
    raw_euler_y: float
    raw_euler_z: float
    quaternion_x: float
    quaternion_y: float
    quaternion_z: float
    quaternion_w: float
    translation_x: float
    translation_y: float
    translation_z: float
    rotation_x: float
    rotation_y: float
    rotation_z: float
    eye_rotation_x: float
    eye_rotation_y: float
    eyebrow_up_down_left: float
    eyebrow_up_down_right: float
    mouth_open: float
    mouth_wide: float
    features: Tuple[float, ...]


def parse_openseeface_udp_packet(packet: bytes) -> Optional[OpenSeeFaceFrame]:
    if len(packet) < OSF_UDP_PACKET_SIZE:
        return None
    try:
        raw = struct.unpack(OSF_UDP_STRUCT_FORMAT, packet[:OSF_UDP_PACKET_SIZE])
    except struct.error:
        return None

    translation_y = float(raw[15]) * -1.0
    translation_z = float(raw[17]) * -1.0
    rotation_y = float(raw[13]) - 10.0
    rotation_x = (-float(raw[12]) + 360.0) % 360.0 - 180.0
    rotation_z = float(raw[14]) - 90.0

    points3d_base = 18 + 68 + 68 * 2
    try:
        eye_vec = [
            raw[points3d_base + 66 * 3] - raw[points3d_base + 68 * 3]
            + raw[points3d_base + 67 * 3] - raw[points3d_base + 69 * 3],
            raw[points3d_base + 66 * 3 + 1] - raw[points3d_base + 68 * 3 + 1]
            + raw[points3d_base + 67 * 3 + 1] - raw[points3d_base + 69 * 3 + 1],
            raw[points3d_base + 66 * 3 + 2] - raw[points3d_base + 68 * 3 + 2]
            + raw[points3d_base + 67 * 3 + 2] - raw[points3d_base + 69 * 3 + 2],
        ]
        norm = (eye_vec[0] ** 2 + eye_vec[1] ** 2 + eye_vec[2] ** 2) ** 0.5
        if norm > 1e-8:
            eye_rotation_x = eye_vec[0] / norm
            eye_rotation_y = eye_vec[1] / norm
        else:
            eye_rotation_x = 0.0
            eye_rotation_y = 0.0
    except (IndexError, TypeError, ValueError):
        eye_rotation_x = 0.0
        eye_rotation_y = 0.0

    feature_start = len(raw) - len(OSF_FEATURE_NAMES)
    features = tuple(float(raw[feature_start + index]) for index in range(len(OSF_FEATURE_NAMES)))
    feature_map = dict(zip(OSF_FEATURE_NAMES, features))

    return OpenSeeFaceFrame(
        time=float(raw[0]),
        track_id=int(raw[1]),
        camera_width=float(raw[2]),
        camera_height=float(raw[3]),
        right_eye_open=float(raw[4]),
        left_eye_open=float(raw[5]),
        left_pupil_confidence=float(
            raw[OSF_LANDMARK_CONFIDENCE_BASE + OSF_LEFT_PUPIL_LANDMARK]),
        right_pupil_confidence=float(
            raw[OSF_LANDMARK_CONFIDENCE_BASE + OSF_RIGHT_PUPIL_LANDMARK]),
        quaternion_x=float(raw[8]),
        quaternion_y=float(raw[9]),
        quaternion_z=float(raw[10]),
        quaternion_w=float(raw[11]),
        fit3d_error=float(raw[7]),
        raw_euler_x=float(raw[12]),
        raw_euler_y=float(raw[13]),
        raw_euler_z=float(raw[14]),
        translation_x=float(raw[16]),
        translation_y=translation_y,
        translation_z=translation_z,
        rotation_x=rotation_x,
        rotation_y=rotation_y,
        rotation_z=rotation_z,
        eye_rotation_x=eye_rotation_x,
        eye_rotation_y=eye_rotation_y,
        eyebrow_up_down_left=float(feature_map.get("EyebrowUpDownLeft", 0.0)),
        eyebrow_up_down_right=float(feature_map.get("EyebrowUpDownRight", 0.0)),
        mouth_open=float(feature_map.get("MouthOpen", 0.0)),
        mouth_wide=float(feature_map.get("MouthWide", 0.0)),
        features=features,
    )


def build_test_openseeface_udp_packet() -> bytes:
    """Synthetic packet for smoke tests (neutral face, open eyes)."""
    values: list = [0.0] * OSF_UDP_VALUE_COUNT
    values[0] = 1.0
    values[1] = 0
    values[4] = 1.0
    values[5] = 1.0
    values[11] = 1.0
    values[OSF_LANDMARK_CONFIDENCE_BASE + OSF_RIGHT_PUPIL_LANDMARK] = 1.0
    values[OSF_LANDMARK_CONFIDENCE_BASE + OSF_LEFT_PUPIL_LANDMARK] = 1.0
    values[6] = 1
    values[12] = 0.0
    values[13] = 10.0
    values[14] = 90.0
    mouth_open_index = len(values) - len(OSF_FEATURE_NAMES) + list(OSF_FEATURE_NAMES).index("MouthOpen")
    values[mouth_open_index] = 0.25
    values[1] = int(values[1])
    values[6] = int(values[6])
    return struct.pack(OSF_UDP_STRUCT_FORMAT, *values)
