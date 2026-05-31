"""Smoke tests for character edge post-processing (no GUI)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from character_edge_postprocess import (
    CHARACTER_EDGE_FLICKER,
    CHARACTER_EDGE_NONE,
    CHARACTER_EDGE_OUTLINE,
    apply_character_edge_postprocess,
    clamp_character_edge_width,
    normalize_character_edge_mode,
    stabilize_character_edge_fringe,
)


def test_mode_normalization() -> None:
    assert normalize_character_edge_mode("outline") == CHARACTER_EDGE_OUTLINE
    assert normalize_character_edge_mode("invalid") == CHARACTER_EDGE_FLICKER


def test_fringe_stabilization() -> None:
    rgba = numpy.zeros((8, 8, 4), dtype=numpy.uint8)
    rgba[3:5, 3:5, 3] = 128
    rgba[3:5, 3:5, 0:3] = 200
    result = stabilize_character_edge_fringe(rgba, (0, 0, 0), fringe_width=2)
    assert numpy.all(result[0, 0, 3] == 0)
    assert numpy.all(result[3:5, 3:5, 3] == 255)


def test_outline_adds_ring() -> None:
    rgba = numpy.zeros((10, 10, 4), dtype=numpy.uint8)
    rgba[4:6, 4:6, 3] = 255
    rgba[4:6, 4:6, 0:3] = 128
    result = apply_character_edge_postprocess(
        rgba,
        CHARACTER_EDGE_OUTLINE,
        width=2,
        outline_rgb=(255, 0, 0),
        background_rgb=(0, 0, 0))
    assert result[2, 4, 0] == 255
    assert result[4, 4, 0] == 128


def test_none_passthrough() -> None:
    rgba = numpy.zeros((4, 4, 4), dtype=numpy.uint8)
    rgba[1, 1, 3] = 255
    result = apply_character_edge_postprocess(rgba, CHARACTER_EDGE_NONE)
    assert numpy.array_equal(result, rgba)


def test_clamp_fractional_width() -> None:
    assert clamp_character_edge_width(1.5555) == 1.556
    assert clamp_character_edge_width(0.0005) == 0.001
    assert clamp_character_edge_width(1.2) == 1.2


def test_fractional_dilation_between_steps() -> None:
    from character_edge_postprocess import _dilate_alpha_fractional

    alpha = numpy.zeros((7, 7), dtype=numpy.uint8)
    alpha[3, 3] = 255
    d1 = _dilate_alpha_fractional(alpha, 1.0)
    d15 = _dilate_alpha_fractional(alpha, 1.5)
    d2 = _dilate_alpha_fractional(alpha, 2.0)
    assert numpy.sum(d1 > 0) < numpy.sum(d15 > 0) <= numpy.sum(d2 > 0)


def main() -> None:
    test_mode_normalization()
    test_fringe_stabilization()
    test_outline_adds_ring()
    test_none_passthrough()
    test_clamp_fractional_width()
    test_fractional_dilation_between_steps()
    print("smoke_character_edge_ok")


if __name__ == "__main__":
    main()
