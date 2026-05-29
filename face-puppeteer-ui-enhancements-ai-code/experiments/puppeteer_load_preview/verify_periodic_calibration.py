"""Logic verification for periodic forward-gaze and scale auto-calibration (no wx/GUI)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class FaceScreenMotion:
    center_x: float
    center_y: float
    face_size: float


@dataclass
class HeadOrientationOffsets:
    head_x_offset: float = 0.0
    head_y_offset: float = 0.0
    head_z_offset: float = 0.0


class ForwardGazeCalibrationHarness:
    """Mirrors MainFrame forward-gaze periodic calibration (head offsets, not display neutral)."""

    def __init__(self):
        self.head_offsets = HeadOrientationOffsets()
        self.pose_euler: Optional[tuple[float, float, float]] = None
        self.last_direction_calibration_time: Optional[float] = None
        self.enable_direction_calibration = True
        self.direction_interval_seconds = 30.0

    def apply_face_orientation_calibration(self) -> bool:
        if self.pose_euler is None:
            return False
        self.head_offsets.head_x_offset, self.head_offsets.head_y_offset, self.head_offsets.head_z_offset = (
            self.pose_euler)
        return True

    def apply_enabled_auto_calibration_on_load(self, calibration_time: float):
        if self.enable_direction_calibration:
            if self.apply_face_orientation_calibration():
                self.last_direction_calibration_time = calibration_time
            else:
                self.last_direction_calibration_time = None
        else:
            self.last_direction_calibration_time = None

    def try_apply_auto_forward_gaze_calibration(self, time_now: float, *, respect_interval: bool) -> bool:
        if not self.enable_direction_calibration:
            return False
        interval_seconds = max(1.0, self.direction_interval_seconds)
        if respect_interval:
            if self.last_direction_calibration_time is None:
                self.last_direction_calibration_time = time_now
                return False
            if time_now - self.last_direction_calibration_time < interval_seconds:
                return False
        if not self.apply_face_orientation_calibration():
            return False
        self.last_direction_calibration_time = time_now
        return True


class ScaleCalibrationHarness:
    """Mirrors MainFrame output dynamic enhancement periodic calibration."""

    def __init__(self):
        self.neutral_face_screen_motion: Optional[FaceScreenMotion] = None
        self.last_scale_calibration_time: Optional[float] = None
        self.enable_scale_calibration = True
        self.scale_interval_seconds = 60.0

    def set_neutral_face_screen_motion(self, face_screen_motion: FaceScreenMotion):
        self.neutral_face_screen_motion = FaceScreenMotion(
            center_x=face_screen_motion.center_x,
            center_y=face_screen_motion.center_y,
            face_size=face_screen_motion.face_size,
        )

    def update_neutral_output_enhancement(self, face_screen_motion: FaceScreenMotion):
        if self.neutral_face_screen_motion is None:
            self.set_neutral_face_screen_motion(face_screen_motion)
            return
        self.neutral_face_screen_motion = FaceScreenMotion(
            center_x=face_screen_motion.center_x,
            center_y=self.neutral_face_screen_motion.center_y,
            face_size=face_screen_motion.face_size,
        )

    def apply_enabled_auto_calibration_on_load(
            self, face_screen_motion: Optional[FaceScreenMotion], calibration_time: float):
        if face_screen_motion is None:
            return
        if self.enable_scale_calibration:
            self.update_neutral_output_enhancement(face_screen_motion)
            self.last_scale_calibration_time = calibration_time
        else:
            self.last_scale_calibration_time = None

    def maybe_apply_periodic_scale_calibration(self, latest_motion: FaceScreenMotion, time_now: float) -> bool:
        if not self.enable_scale_calibration:
            return False
        interval_seconds = max(1.0, self.scale_interval_seconds)
        if self.last_scale_calibration_time is None:
            self.last_scale_calibration_time = time_now
            return False
        if time_now - self.last_scale_calibration_time < interval_seconds:
            return False
        self.update_neutral_output_enhancement(latest_motion)
        self.last_scale_calibration_time = time_now
        return True


def assert_close(a: float, b: float, eps: float = 1e-6):
    if abs(a - b) > eps:
        raise AssertionError(f"{a} != {b}")


def test_forward_gaze_sets_head_offsets():
    h = ForwardGazeCalibrationHarness()
    h.pose_euler = (0.1, -0.2, 0.3)
    assert h.apply_face_orientation_calibration() is True
    assert_close(h.head_offsets.head_x_offset, 0.1)
    assert_close(h.head_offsets.head_y_offset, -0.2)
    assert_close(h.head_offsets.head_z_offset, 0.3)


def test_forward_gaze_without_face_skips():
    h = ForwardGazeCalibrationHarness()
    h.pose_euler = None
    assert h.apply_face_orientation_calibration() is False


def test_forward_gaze_independent_interval():
    h = ForwardGazeCalibrationHarness()
    h.direction_interval_seconds = 30.0
    h.pose_euler = (1.0, 0.0, 0.0)
    h.apply_enabled_auto_calibration_on_load(calibration_time=1000.0)
    assert_close(h.head_offsets.head_x_offset, 1.0)

    h.pose_euler = (2.0, 0.0, 0.0)
    assert h.try_apply_auto_forward_gaze_calibration(1020.0, respect_interval=True) is False
    assert_close(h.head_offsets.head_x_offset, 1.0)
    assert h.try_apply_auto_forward_gaze_calibration(1030.0, respect_interval=True) is True
    assert_close(h.head_offsets.head_x_offset, 2.0)


def test_forward_gaze_disabled_skips():
    h = ForwardGazeCalibrationHarness()
    h.enable_direction_calibration = False
    h.pose_euler = (1.0, 0.0, 0.0)
    h.apply_enabled_auto_calibration_on_load(calibration_time=0.0)
    assert h.last_direction_calibration_time is None
    assert h.try_apply_auto_forward_gaze_calibration(999.0, respect_interval=True) is False


def test_forward_gaze_first_tick_arms_timer_without_calibrating():
    h = ForwardGazeCalibrationHarness()
    h.pose_euler = (9.0, 8.0, 7.0)
    h.last_direction_calibration_time = None
    h.head_offsets = HeadOrientationOffsets()
    changed = h.try_apply_auto_forward_gaze_calibration(500.0, respect_interval=True)
    assert changed is False
    assert h.last_direction_calibration_time == 500.0
    assert_close(h.head_offsets.head_x_offset, 0.0)


def test_output_enhancement_recenters_horizontal_only():
    h = ScaleCalibrationHarness()
    h.set_neutral_face_screen_motion(FaceScreenMotion(0.1, 0.2, 0.4))
    h.update_neutral_output_enhancement(FaceScreenMotion(0.9, 0.8, 0.7))
    assert_close(h.neutral_face_screen_motion.center_x, 0.9)
    assert_close(h.neutral_face_screen_motion.center_y, 0.2)
    assert_close(h.neutral_face_screen_motion.face_size, 0.7)


def test_scale_independent_interval():
    h = ScaleCalibrationHarness()
    h.scale_interval_seconds = 60.0
    h.apply_enabled_auto_calibration_on_load(FaceScreenMotion(0.5, 0.0, 0.4), calibration_time=1000.0)
    motion = FaceScreenMotion(0.5, 0.0, 0.8)
    assert h.maybe_apply_periodic_scale_calibration(motion, 1040.0) is False
    assert h.maybe_apply_periodic_scale_calibration(motion, 1060.0) is True
    assert_close(h.neutral_face_screen_motion.face_size, 0.8)


def main():
    tests = [
        test_forward_gaze_sets_head_offsets,
        test_forward_gaze_without_face_skips,
        test_forward_gaze_independent_interval,
        test_forward_gaze_disabled_skips,
        test_forward_gaze_first_tick_arms_timer_without_calibrating,
        test_output_enhancement_recenters_horizontal_only,
        test_scale_independent_interval,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print("ALL_OK", len(tests))


if __name__ == "__main__":
    main()
