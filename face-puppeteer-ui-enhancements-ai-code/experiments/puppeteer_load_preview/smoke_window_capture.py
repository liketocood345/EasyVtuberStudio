"""CLI smoke: window capture method cache + thumb luma helpers (no GUI)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from window_capture import (
    _GOOD_FRAME_LUMA_MIN,
    _USABLE_FRAME_LUMA_MIN,
    _frame_thumb_mean_luma,
    _capture_method_cache,
    invalidate_capture_method_cache,
)


def test_thumb_luma_black_vs_bright() -> None:
    black = numpy.zeros((480, 640, 3), dtype=numpy.uint8)
    bright = numpy.full((480, 640, 3), 180, dtype=numpy.uint8)
    assert _frame_thumb_mean_luma(black) < 2.0
    assert _frame_thumb_mean_luma(bright) > 4.0


def test_luma_threshold_constants() -> None:
    assert _USABLE_FRAME_LUMA_MIN < _GOOD_FRAME_LUMA_MIN
    black = numpy.zeros((480, 640, 3), dtype=numpy.uint8)
    bright = numpy.full((480, 640, 3), 180, dtype=numpy.uint8)
    assert _frame_thumb_mean_luma(black) < _USABLE_FRAME_LUMA_MIN
    assert _frame_thumb_mean_luma(bright) >= _GOOD_FRAME_LUMA_MIN


def test_invalidate_capture_method_cache() -> None:
    _capture_method_cache[12345] = 1
    invalidate_capture_method_cache(12345)
    assert 12345 not in _capture_method_cache
    _capture_method_cache[99] = 0
    invalidate_capture_method_cache()
    assert not _capture_method_cache


def main() -> None:
    test_thumb_luma_black_vs_bright()
    test_luma_threshold_constants()
    test_invalidate_capture_method_cache()
    print("smoke_window_capture_ok")


if __name__ == "__main__":
    main()
