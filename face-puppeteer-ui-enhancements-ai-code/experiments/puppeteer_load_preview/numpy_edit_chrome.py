"""Pure-numpy edit chrome (selection box + resize handle) for the layered
output window's overlay layer.

Mirrors LayerCompositor.draw_selection_highlight but renders to an RGBA array
(via PIL ImageDraw) instead of a wx.DC, so the future ctypes layered output
window can present a clean output layer (captured) plus a separate transparent
"edit chrome" overlay (selection-only, not captured). Rotation-aware.

Circular-orbit layers use ``render_orbit_edit_chrome_rgba`` (path + bind point)
instead of the axis-aligned selection rectangle.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy
import PIL.Image
import PIL.ImageDraw

DEFAULT_HIGHLIGHT_RGB = (255, 200, 0)

# The layered output window (UpdateLayeredWindow, per-pixel alpha) hit-tests by
# alpha: pixels with alpha == 0 are click-through, so a fully-transparent
# selection-box interior cannot be grabbed to drag the layer. Filling the box
# interior with a minimal non-zero alpha makes the whole highlight box a
# draggable region while staying visually invisible (premultiplied ~black at
# alpha 1, so it does not show up in the captured stream).
DRAG_REGION_FILL_ALPHA = 1


def _rotate_point(
        px: float, py: float, cx: float, cy: float,
        cos_r: float, sin_r: float) -> Tuple[float, float]:
    dx = px - cx
    dy = py - cy
    return (cx + dx * cos_r - dy * sin_r, cy + dx * sin_r + dy * cos_r)


def render_selection_chrome_rgba(
        canvas_width: int,
        canvas_height: int,
        rect_xywh: Tuple[float, float, float, float],
        *,
        rotation_deg: float = 0.0,
        highlight_rgb: Tuple[int, int, int] = DEFAULT_HIGHLIGHT_RGB,
        handle: int = 8,
        line_width: int = 2,
        interior_fill_alpha: int = DRAG_REGION_FILL_ALPHA) -> numpy.ndarray:
    """Return a transparent RGBA canvas with the selection rectangle outline and
    a filled bottom-right resize handle drawn for the given layer rect.

    The box interior is filled with ``interior_fill_alpha`` (a minimal non-zero
    alpha) so the entire highlight box is a hit-testable drag region on the
    per-pixel-alpha layered output window, where alpha==0 pixels are
    click-through. The fill is effectively invisible in the captured output."""
    canvas_width = max(1, int(canvas_width))
    canvas_height = max(1, int(canvas_height))
    image = PIL.Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(image)

    x, y, w, h = rect_xywh
    w = max(1.0, float(w))
    h = max(1.0, float(h))
    colour = (int(highlight_rgb[0]), int(highlight_rgb[1]), int(highlight_rgb[2]), 255)

    cx = float(x) + w / 2.0
    cy = float(y) + h / 2.0
    rad = math.radians(float(rotation_deg))
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)

    corners = [
        (x, y),
        (x + w, y),
        (x + w, y + h),
        (x, y + h),
    ]
    if abs(rotation_deg) > 1e-4:
        corners = [_rotate_point(px, py, cx, cy, cos_r, sin_r) for px, py in corners]

    fill_alpha = max(0, min(255, int(interior_fill_alpha)))
    if fill_alpha > 0:
        draw.polygon(
            corners,
            fill=(colour[0], colour[1], colour[2], fill_alpha))

    draw.line(corners + [corners[0]], fill=colour, width=max(1, int(line_width)))

    handle = max(2, int(handle))
    hx0 = x + w - handle
    hy0 = y + h - handle
    handle_corners = [
        (hx0, hy0),
        (hx0 + handle, hy0),
        (hx0 + handle, hy0 + handle),
        (hx0, hy0 + handle),
    ]
    if abs(rotation_deg) > 1e-4:
        handle_corners = [
            _rotate_point(px, py, cx, cy, cos_r, sin_r) for px, py in handle_corners]
    draw.polygon(handle_corners, fill=colour)

    return numpy.ascontiguousarray(numpy.array(image, dtype=numpy.uint8))


def render_orbit_edit_chrome_rgba(
        canvas_width: int,
        canvas_height: int,
        path_points: list[tuple[float, float]],
        pivot_xy: tuple[float, float],
        bind_xy: Optional[tuple[float, float]],
        *,
        highlight_rgb: Tuple[int, int, int] = DEFAULT_HIGHLIGHT_RGB,
        line_width: int = 2,
        hit_stroke_width: int = 14,
        pivot_radius: int = 5,
        bind_radius: int = 4,
        interior_fill_alpha: int = DRAG_REGION_FILL_ALPHA) -> numpy.ndarray:
    """Orbit-layer edit chrome: projected path loop, bind anchor, orbit pivot."""
    canvas_width = max(1, int(canvas_width))
    canvas_height = max(1, int(canvas_height))
    image = PIL.Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    draw = PIL.ImageDraw.Draw(image)
    colour = (int(highlight_rgb[0]), int(highlight_rgb[1]), int(highlight_rgb[2]), 255)
    fill_alpha = max(0, min(255, int(interior_fill_alpha)))
    hit_colour = (colour[0], colour[1], colour[2], fill_alpha)

    if len(path_points) >= 2:
        loop = [(float(px), float(py)) for px, py in path_points]
        if fill_alpha > 0:
            draw.line(
                loop + [loop[0]],
                fill=hit_colour,
                width=max(4, int(hit_stroke_width)))
        draw.line(
            loop + [loop[0]],
            fill=colour,
            width=max(1, int(line_width)))

    pivot_x, pivot_y = float(pivot_xy[0]), float(pivot_xy[1])
    pr = max(2, int(pivot_radius))
    draw.ellipse(
        (pivot_x - pr, pivot_y - pr, pivot_x + pr, pivot_y + pr),
        outline=colour,
        width=max(1, int(line_width)))
    cross = max(3, pr + 2)
    draw.line(
        [(pivot_x - cross, pivot_y), (pivot_x + cross, pivot_y)],
        fill=colour,
        width=max(1, int(line_width)))
    draw.line(
        [(pivot_x, pivot_y - cross), (pivot_x, pivot_y + cross)],
        fill=colour,
        width=max(1, int(line_width)))

    if bind_xy is not None:
        bind_x, bind_y = float(bind_xy[0]), float(bind_xy[1])
        br = max(2, int(bind_radius))
        draw.ellipse(
            (bind_x - br, bind_y - br, bind_x + br, bind_y + br),
            fill=colour)

    return numpy.ascontiguousarray(numpy.array(image, dtype=numpy.uint8))
