"""Pose-space display interpolation for THA output (pre-compose infer path).

×N multiplies effective GPU infer rate (up to display cap): between consecutive
mocap keyframes the pipeline infers at pose lerp fractions 1/N … (N-1)/N, then
the live mocap pose. Each intermediate frame is a real ``poser.pose()`` result —
no RGBA crossfade (avoids facial ghosting).
"""
from __future__ import annotations

from typing import List, Optional, Sequence

POSE_FRAME_INTERP_OFF = 1
POSE_FRAME_INTERP_VALUES = (1, 2, 3, 4)
POSE_FRAME_INTERP_LABELS = (
    "关闭 / Off (×1)",
    "×2 pose infer",
    "×3 pose infer",
    "×4 pose infer",
)
DISPLAY_INFER_CAP_HZ = 30

# Backward-compatible aliases (legacy ``frame_interpolation`` module name).
FRAME_INTERP_OFF = POSE_FRAME_INTERP_OFF
FRAME_INTERP_VALUES = POSE_FRAME_INTERP_VALUES
FRAME_INTERP_LABELS = POSE_FRAME_INTERP_LABELS


def normalize_multiplier(value) -> int:
    try:
        multiplier = int(value)
    except (TypeError, ValueError):
        multiplier = POSE_FRAME_INTERP_OFF
    if multiplier not in POSE_FRAME_INTERP_VALUES:
        return POSE_FRAME_INTERP_OFF
    return multiplier


normalize_pose_frame_multiplier = normalize_multiplier


def lerp_pose(pose_a: Sequence[float], pose_b: Sequence[float], t: float) -> List[float]:
    t = max(0.0, min(1.0, float(t)))
    return [float(a) + (float(b) - float(a)) * t for a, b in zip(pose_a, pose_b)]


def get_effective_infer_cap_hz(base_cap_hz: int, multiplier: int) -> int:
    base_cap_hz = max(1, int(base_cap_hz))
    multiplier = normalize_multiplier(multiplier)
    if multiplier <= POSE_FRAME_INTERP_OFF:
        return base_cap_hz
    return min(DISPLAY_INFER_CAP_HZ, base_cap_hz * multiplier)


def resolve_interp_infer_pose(
        keyframe_pose: Sequence[float],
        current_pose: Sequence[float],
        multiplier: int,
        substep_index: int) -> List[float]:
    """Pose to infer for the current sub-step (0 .. multiplier-1)."""
    multiplier = normalize_multiplier(multiplier)
    if multiplier <= POSE_FRAME_INTERP_OFF:
        return list(current_pose)
    substep_index = max(0, int(substep_index))
    if substep_index >= multiplier - 1:
        return list(current_pose)
    blend_t = float(substep_index + 1) / float(multiplier)
    return lerp_pose(keyframe_pose, current_pose, blend_t)


def label_for_multiplier(multiplier: int) -> str:
    multiplier = normalize_multiplier(multiplier)
    try:
        return POSE_FRAME_INTERP_LABELS[POSE_FRAME_INTERP_VALUES.index(multiplier)]
    except ValueError:
        return POSE_FRAME_INTERP_LABELS[0]


def is_pose_interpolation_active(multiplier: int) -> bool:
    return normalize_multiplier(multiplier) > POSE_FRAME_INTERP_OFF


class PoseInterpolationController:
    """Runtime state for pose-space frame interpolation."""

    def __init__(self) -> None:
        self.keyframe_pose: Optional[List[float]] = None
        self.substep_index: int = 0

    def reset(self, *, seed_pose: Optional[Sequence[float]] = None) -> None:
        if seed_pose is not None:
            self.keyframe_pose = list(seed_pose)
        else:
            self.keyframe_pose = None
        self.substep_index = 0

    def seed_after_real_infer(self, inferred_pose: Sequence[float]) -> None:
        self.keyframe_pose = list(inferred_pose)
        self.substep_index = 0

    def advance_after_infer(self, inferred_pose: Sequence[float], multiplier: int) -> None:
        multiplier = normalize_multiplier(multiplier)
        if multiplier <= POSE_FRAME_INTERP_OFF:
            self.seed_after_real_infer(inferred_pose)
            return
        if self.substep_index >= multiplier - 1:
            self.keyframe_pose = list(inferred_pose)
            self.substep_index = 0
        else:
            self.substep_index += 1

    def resolve_infer_pose(self, current_pose: Sequence[float], multiplier: int) -> List[float]:
        multiplier = normalize_multiplier(multiplier)
        if multiplier <= POSE_FRAME_INTERP_OFF:
            return list(current_pose)
        if self.keyframe_pose is None:
            return list(current_pose)
        return resolve_interp_infer_pose(
            self.keyframe_pose,
            current_pose,
            multiplier,
            self.substep_index)

    def reference_pose_for_change_detection(
            self,
            last_pose: Sequence[float],
            multiplier: int) -> Sequence[float]:
        if is_pose_interpolation_active(multiplier) and self.keyframe_pose is not None:
            return self.keyframe_pose
        return last_pose
