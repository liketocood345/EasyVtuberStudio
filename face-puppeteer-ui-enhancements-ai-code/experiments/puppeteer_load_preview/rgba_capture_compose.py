"""NumPy/PIL RGBA composition for transparent capture (avoids wx greyscale readback)."""
from __future__ import annotations

import math

import numpy
import PIL.Image


def wx_image_to_rgba_array(image) -> numpy.ndarray:
    width = max(1, int(image.GetWidth()))
    height = max(1, int(image.GetHeight()))
    rgb = numpy.frombuffer(image.GetData(), dtype=numpy.uint8).reshape(height, width, 3)
    if image.HasAlpha():
        alpha = numpy.frombuffer(image.GetAlpha(), dtype=numpy.uint8).reshape(height, width, 1)
    else:
        alpha = numpy.full((height, width, 1), 255, dtype=numpy.uint8)
    return numpy.ascontiguousarray(numpy.concatenate([rgb, alpha], axis=2), dtype=numpy.uint8)


def scale_rgba(rgba: numpy.ndarray, width: int, height: int) -> numpy.ndarray:
    width = max(1, int(width))
    height = max(1, int(height))
    if rgba.shape[0] == height and rgba.shape[1] == width:
        return numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
    image = PIL.Image.fromarray(rgba, "RGBA")
    resized = image.resize((width, height), PIL.Image.Resampling.LANCZOS)
    return numpy.ascontiguousarray(numpy.array(resized, dtype=numpy.uint8))


def sanitize_transparent_rgb(rgba: numpy.ndarray) -> numpy.ndarray:
    rgba = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
    transparent = rgba[:, :, 3] == 0
    if not numpy.any(transparent):
        return rgba
    rgba = rgba.copy()
    rgba[transparent, 0:3] = 0
    return rgba


def _invert_affine(forward: numpy.ndarray) -> numpy.ndarray:
    a, b, tx = forward[0]
    c, d, ty = forward[1]
    det = (a * d) - (b * c)
    if abs(det) < 1e-8:
        raise ValueError("singular affine transform")
    inv_a = d / det
    inv_b = -b / det
    inv_c = -c / det
    inv_d = a / det
    inv_tx = -((inv_a * tx) + (inv_b * ty))
    inv_ty = -((inv_c * tx) + (inv_d * ty))
    return numpy.array(
        [[inv_a, inv_b, inv_tx], [inv_c, inv_d, inv_ty]],
        dtype=numpy.float64)


def compose_character_rgba_from_keyframe(
        keyframe_rgba: numpy.ndarray,
        canvas_width: int,
        canvas_height: int,
        *,
        anchor_x: float,
        anchor_y: float,
        scale: float,
        rotation_deg: float,
        antialias_factor: float = 1.0) -> numpy.ndarray:
    """Match wx GraphicsContext transform: translate, rotate, scale, draw feet anchor."""
    keyframe_rgba = numpy.ascontiguousarray(keyframe_rgba, dtype=numpy.uint8)
    keyframe_height, keyframe_width = keyframe_rgba.shape[0], keyframe_rgba.shape[1]
    render_width = max(1, int(round(canvas_width * antialias_factor)))
    render_height = max(1, int(round(canvas_height * antialias_factor)))
    display_scale = max(0.1, float(scale))
    rotation_rad = math.radians(float(rotation_deg))
    cos_r = math.cos(rotation_rad)
    sin_r = math.sin(rotation_rad)

    anchor_x_render = float(anchor_x) * antialias_factor
    anchor_y_render = float(anchor_y) * antialias_factor
    tx = (
        anchor_x_render
        - display_scale * cos_r * keyframe_width / 2.0
        + display_scale * sin_r * keyframe_height)
    ty = (
        anchor_y_render
        - display_scale * sin_r * keyframe_width / 2.0
        - display_scale * cos_r * keyframe_height)
    forward = numpy.array(
        [
            [display_scale * cos_r, -display_scale * sin_r, tx],
            [display_scale * sin_r, display_scale * cos_r, ty],
        ],
        dtype=numpy.float64)
    inverse = _invert_affine(forward)
    coeffs = (
        inverse[0, 0],
        inverse[0, 1],
        inverse[0, 2],
        inverse[1, 0],
        inverse[1, 1],
        inverse[1, 2],
    )
    source = PIL.Image.fromarray(keyframe_rgba, "RGBA")
    warped = source.transform(
        (render_width, render_height),
        PIL.Image.Transform.AFFINE,
        coeffs,
        resample=PIL.Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0))
    out = numpy.ascontiguousarray(numpy.array(warped, dtype=numpy.uint8))
    if antialias_factor > 1.001:
        out = scale_rgba(
            out,
            max(1, int(canvas_width)),
            max(1, int(canvas_height)))
    return sanitize_transparent_rgb(out)


def _straight_rgba_to_premultiplied_bgra(rgba: numpy.ndarray) -> numpy.ndarray:
    rgba = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError(f"expected HxWx4 RGBA, got {rgba.shape}")
    alpha = rgba[:, :, 3:4].astype(numpy.float32) / 255.0
    rgb = rgba[:, :, 0:3].astype(numpy.float32) * alpha
    bgra = numpy.empty_like(rgba)
    bgra[:, :, 0] = numpy.clip(rgb[:, :, 2], 0.0, 255.0).astype(numpy.uint8)
    bgra[:, :, 1] = numpy.clip(rgb[:, :, 1], 0.0, 255.0).astype(numpy.uint8)
    bgra[:, :, 2] = numpy.clip(rgb[:, :, 0], 0.0, 255.0).astype(numpy.uint8)
    bgra[:, :, 3] = rgba[:, :, 3]
    return numpy.ascontiguousarray(bgra)


def rgba_has_color(rgba: numpy.ndarray) -> bool:
    opaque = rgba[:, :, 3] > 0
    if not numpy.any(opaque):
        return True
    pixels = rgba[:, :, 0:3][opaque]
    if pixels.shape[0] == 0:
        return True
    return bool(
        numpy.any(pixels[:, 0] != pixels[:, 1])
        or numpy.any(pixels[:, 1] != pixels[:, 2])
        or numpy.any(pixels[:, 0] != pixels[:, 2]))
