"""Smoke tests for transparent capture RGBA pipeline."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from character_edge_postprocess import composite_rgba_arrays
from rgba_capture_compose import (
    _straight_rgba_to_premultiplied_bgra,
    compose_character_rgba_from_keyframe,
    rgba_has_color,
    sanitize_transparent_rgb,
)

WINDOW_TITLE = "THA4 Transparent Capture / 透明捕获输出"


def test_composite_preserves_color() -> None:
    bg = numpy.zeros((4, 4, 4), dtype=numpy.uint8)
    fg = numpy.zeros((4, 4, 4), dtype=numpy.uint8)
    fg[1:3, 1:3, 0] = 200
    fg[1:3, 1:3, 1] = 40
    fg[1:3, 1:3, 2] = 10
    fg[1:3, 1:3, 3] = 255
    out = composite_rgba_arrays(bg, fg)
    assert out[2, 2, 0] == 200
    assert out[2, 2, 1] == 40
    assert out[2, 2, 2] == 10
    assert out[0, 0, 3] == 0


def test_compose_character_keeps_color() -> None:
    keyframe = numpy.zeros((8, 8, 4), dtype=numpy.uint8)
    keyframe[2:6, 2:6, 0] = 220
    keyframe[2:6, 2:6, 1] = 50
    keyframe[2:6, 2:6, 2] = 30
    keyframe[2:6, 2:6, 3] = 255
    out = compose_character_rgba_from_keyframe(
        keyframe,
        16,
        16,
        anchor_x=8.0,
        anchor_y=16.0,
        scale=1.0,
        rotation_deg=0.0,
        antialias_factor=1.0)
    assert rgba_has_color(out)
    assert numpy.any(out[:, :, 3] > 0)


def test_premultiplied_bgra_channels() -> None:
    rgba = numpy.zeros((2, 2, 4), dtype=numpy.uint8)
    rgba[:, :, 0] = 180
    rgba[:, :, 1] = 60
    rgba[:, :, 2] = 20
    rgba[:, :, 3] = 128
    bgra = _straight_rgba_to_premultiplied_bgra(rgba)
    assert bgra[0, 0, 2] > bgra[0, 0, 1] > bgra[0, 0, 0]
    assert bgra[0, 0, 3] == 128


def test_capture_window_title() -> None:
    assert "THA4 Transparent Capture" in WINDOW_TITLE
    assert "透明捕获输出" in WINDOW_TITLE


def test_sanitize_transparent_rgb() -> None:
    rgba = numpy.zeros((2, 2, 4), dtype=numpy.uint8)
    rgba[0, 0, 0:3] = 99
    out = sanitize_transparent_rgb(rgba)
    assert tuple(out[0, 0, 0:3]) == (0, 0, 0)


def main() -> None:
    test_composite_preserves_color()
    test_compose_character_keeps_color()
    test_premultiplied_bgra_channels()
    test_capture_window_title()
    test_sanitize_transparent_rgb()
    print("smoke_transparent_capture_ok")


if __name__ == "__main__":
    main()
