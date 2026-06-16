"""Smoke test for averaged output FPS (last 5 frames, 1 Hz display commit)."""
from __future__ import annotations

from typing import List, Optional


def averaged_output_fps_from_present_times(
        present_times: List[float],
        *,
        avg_frame_count: int = 5,
        max_gap_sec: float = 2.0) -> Optional[float]:
    if not present_times or len(present_times) < 2:
        return None
    window = present_times[-max(2, int(avg_frame_count)) :]
    span = window[-1] - window[0]
    intervals = len(window) - 1
    if intervals <= 0 or span <= 1e-6:
        return None
    if span / intervals >= max_gap_sec:
        return None
    return intervals / span


def main() -> None:
    assert averaged_output_fps_from_present_times([]) is None
    assert averaged_output_fps_from_present_times([0.0]) is None
    assert averaged_output_fps_from_present_times([0.0, 0.5]) == 2.0
    # Five frames at 30 Hz: t = 0, 1/30, 2/30, 3/30, 4/30
    step = 1.0 / 30.0
    times = [step * i for i in range(5)]
    assert abs(averaged_output_fps_from_present_times(times) - 30.0) < 0.05
    # Only two frames in window still works before five are collected
    assert abs(averaged_output_fps_from_present_times(times[:2]) - 30.0) < 0.05
    assert averaged_output_fps_from_present_times([0.0, 3.0]) is None
    print("smoke_output_fps: OK")


if __name__ == "__main__":
    main()
