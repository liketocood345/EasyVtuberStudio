"""Pose-space display interpolation for THA output.

×N multiplies effective GPU infer rate (up to display cap): between consecutive
mocap keyframes the pipeline infers at pose lerp fractions 1/N … (N-1)/N, then
the live mocap pose. Each intermediate frame is a real ``poser.pose()`` result —
no RGBA crossfade (avoids facial ghosting).
"""
from __future__ import annotations

from typing import List, Sequence

FRAME_INTERP_OFF = 1
FRAME_INTERP_VALUES = (1, 2, 3, 4)
FRAME_INTERP_LABELS = (
    "关闭 / Off (×1)",
    "×2 pose infer",
    "×3 pose infer",
    "×4 pose infer",
)
DISPLAY_INFER_CAP_HZ = 30


def normalize_multiplier(value) -> int:
    try:
        multiplier = int(value)
    except (TypeError, ValueError):
        multiplier = FRAME_INTERP_OFF
    if multiplier not in FRAME_INTERP_VALUES:
        return FRAME_INTERP_OFF
    return multiplier


def lerp_pose(pose_a: Sequence[float], pose_b: Sequence[float], t: float) -> List[float]:
    t = max(0.0, min(1.0, float(t)))
    return [float(a) + (float(b) - float(a)) * t for a, b in zip(pose_a, pose_b)]


def get_effective_infer_cap_hz(base_cap_hz: int, multiplier: int) -> int:
    base_cap_hz = max(1, int(base_cap_hz))
    multiplier = normalize_multiplier(multiplier)
    if multiplier <= FRAME_INTERP_OFF:
        return base_cap_hz
    return min(DISPLAY_INFER_CAP_HZ, base_cap_hz * multiplier)


def resolve_interp_infer_pose(
        keyframe_pose: Sequence[float],
        current_pose: Sequence[float],
        multiplier: int,
        substep_index: int) -> List[float]:
    """Pose to infer for the current sub-step (0 .. multiplier-1)."""
    multiplier = normalize_multiplier(multiplier)
    if multiplier <= FRAME_INTERP_OFF:
        return list(current_pose)
    substep_index = max(0, int(substep_index))
    if substep_index >= multiplier - 1:
        return list(current_pose)
    blend_t = float(substep_index + 1) / float(multiplier)
    return lerp_pose(keyframe_pose, current_pose, blend_t)


def label_for_multiplier(multiplier: int) -> str:
    multiplier = normalize_multiplier(multiplier)
    try:
        return FRAME_INTERP_LABELS[FRAME_INTERP_VALUES.index(multiplier)]
    except ValueError:
        return FRAME_INTERP_LABELS[0]
