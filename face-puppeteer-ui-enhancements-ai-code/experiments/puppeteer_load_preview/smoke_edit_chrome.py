"""Smoke tests for the pure-numpy edit chrome renderer (no GUI)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from numpy_edit_chrome import render_selection_chrome_rgba


def test_chrome_outline_drawn() -> None:
    canvas_w = canvas_h = 100
    chrome = render_selection_chrome_rgba(
        canvas_w, canvas_h, (20.0, 20.0, 60.0, 60.0),
        highlight_rgb=(255, 200, 0))
    assert chrome.shape == (canvas_h, canvas_w, 4)
    # interior of the rectangle is transparent (outline only, not filled)
    assert int(chrome[50, 50, 3]) == 0
    # the top edge near y=20 has opaque highlight pixels
    top_edge = chrome[18:23, 25:75, 3]
    assert int(top_edge.max()) == 255
    # corners outside the box stay transparent
    assert int(chrome[2, 2, 3]) == 0


def test_chrome_handle_filled_bottom_right() -> None:
    canvas_w = canvas_h = 120
    chrome = render_selection_chrome_rgba(
        canvas_w, canvas_h, (10.0, 10.0, 80.0, 80.0),
        handle=10, highlight_rgb=(0, 180, 255))
    # bottom-right handle region (around x=90,y=90) is filled opaque
    handle_region = chrome[82:90, 82:90, 3]
    assert int(handle_region.min()) == 255
    # handle colour matches highlight (BGR-agnostic: check RGB channels)
    assert int(chrome[86, 86, 1]) > 100
    assert int(chrome[86, 86, 2]) > 200


def test_chrome_rotation_changes_pixels() -> None:
    canvas_w = canvas_h = 100
    flat = render_selection_chrome_rgba(
        canvas_w, canvas_h, (25.0, 25.0, 50.0, 50.0), rotation_deg=0.0)
    rotated = render_selection_chrome_rgba(
        canvas_w, canvas_h, (25.0, 25.0, 50.0, 50.0), rotation_deg=30.0)
    assert not numpy.array_equal(flat[:, :, 3], rotated[:, :, 3])


def test_chrome_empty_when_offscreen() -> None:
    canvas_w = canvas_h = 50
    chrome = render_selection_chrome_rgba(
        canvas_w, canvas_h, (200.0, 200.0, 30.0, 30.0))
    assert int(chrome[:, :, 3].max()) == 0


def main() -> None:
    test_chrome_outline_drawn()
    test_chrome_handle_filled_bottom_right()
    test_chrome_rotation_changes_pixels()
    test_chrome_empty_when_offscreen()
    print("smoke_edit_chrome_ok")


if __name__ == "__main__":
    main()
