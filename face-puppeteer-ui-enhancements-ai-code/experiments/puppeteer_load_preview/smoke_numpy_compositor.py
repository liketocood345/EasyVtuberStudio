"""Smoke tests for the pure-numpy full-stack compositor (no GUI, no wx render)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from layer_runtime import (
    BasicLayersState,
    BasicLayerSlot,
    BindingContext,
    LayerAssetCache,
    LayerTransform,
    MOTION_MODE_SIMPLE_SWING,
    default_stack_position_for_slot,
)
from numpy_layer_compositor import compose_full_stack_rgba


def _solid_rgba(width: int, height: int, rgb, alpha: int = 255) -> numpy.ndarray:
    out = numpy.zeros((height, width, 4), dtype=numpy.uint8)
    out[:, :, 0] = rgb[0]
    out[:, :, 1] = rgb[1]
    out[:, :, 2] = rgb[2]
    out[:, :, 3] = alpha
    return out


def test_zorder_front_layer_over_character() -> None:
    state = BasicLayersState()
    # slot 0 stack position is behind character, slot 3 is in front (per
    # default_stack_position_for_slot mapping around CHARACTER_STACK_POS=2).
    behind = next(
        layer for layer in state.layers
        if default_stack_position_for_slot(layer.slot_id) < 2)
    front = next(
        layer for layer in state.layers
        if default_stack_position_for_slot(layer.slot_id) > 2)
    behind.asset_path = "behind.png"
    front.asset_path = "front.png"
    behind.transform = LayerTransform(scale=1.0)
    front.transform = LayerTransform(scale=1.0)

    canvas_w = canvas_h = 64
    character = _solid_rgba(canvas_w, canvas_h, (0, 255, 0))

    palette = {
        behind.slot_id: _solid_rgba(canvas_w, canvas_h, (255, 0, 0)),
        front.slot_id: _solid_rgba(canvas_w, canvas_h, (0, 0, 255)),
    }

    def loader(layer):
        return palette.get(layer.slot_id)

    ctx = BindingContext(canvas_width=canvas_w, canvas_height=canvas_h)
    result = compose_full_stack_rgba(
        state, loader, canvas_w, canvas_h, character, ctx)

    assert result.shape == (canvas_h, canvas_w, 4)
    center = result[canvas_h // 2, canvas_w // 2]
    # Front (blue) opaque full-canvas layer wins the center pixel.
    assert center[2] > 200 and center[0] < 60 and center[1] < 60
    assert center[3] == 255


def test_behind_layer_hidden_by_opaque_character() -> None:
    state = BasicLayersState()
    behind = next(
        layer for layer in state.layers
        if default_stack_position_for_slot(layer.slot_id) < 2)
    behind.asset_path = "behind.png"
    behind.transform = LayerTransform(scale=1.0)

    canvas_w = canvas_h = 48
    character = _solid_rgba(canvas_w, canvas_h, (0, 255, 0))

    def loader(layer):
        if layer.slot_id == behind.slot_id:
            return _solid_rgba(canvas_w, canvas_h, (255, 0, 0))
        return None

    ctx = BindingContext(canvas_width=canvas_w, canvas_height=canvas_h)
    result = compose_full_stack_rgba(
        state, loader, canvas_w, canvas_h, character, ctx)
    center = result[canvas_h // 2, canvas_w // 2]
    # Opaque green character fully covers the red behind-layer.
    assert center[1] > 200 and center[0] < 60


def test_transparent_canvas_when_empty() -> None:
    state = BasicLayersState()
    canvas_w = canvas_h = 32
    character = numpy.zeros((canvas_h, canvas_w, 4), dtype=numpy.uint8)

    def loader(_layer):
        return None

    result = compose_full_stack_rgba(
        state, loader, canvas_w, canvas_h, character)
    assert result.shape == (canvas_h, canvas_w, 4)
    assert int(result[:, :, 3].max()) == 0


def test_small_layer_placement_and_alpha() -> None:
    state = BasicLayersState()
    front = next(
        layer for layer in state.layers
        if default_stack_position_for_slot(layer.slot_id) > 2)
    front.asset_path = "front.png"
    # half-size, centered (offset 0): occupies the middle quarter of canvas.
    front.transform = LayerTransform(scale=0.5)

    canvas_w = canvas_h = 64
    character = numpy.zeros((canvas_h, canvas_w, 4), dtype=numpy.uint8)
    # layer source is canvas-sized; resolver scales it by 0.5*canvas/512.
    sprite = _solid_rgba(512, 512, (200, 50, 50))

    def loader(layer):
        return sprite if layer.slot_id == front.slot_id else None

    ctx = BindingContext(canvas_width=canvas_w, canvas_height=canvas_h)
    result = compose_full_stack_rgba(
        state, loader, canvas_w, canvas_h, character, ctx)
    # 512 * 0.5 * (64/512) = 32px square centered -> corners stay transparent.
    assert int(result[2, 2, 3]) == 0
    assert int(result[canvas_h // 2, canvas_w // 2, 3]) == 255


def test_rotation_changes_corner_coverage() -> None:
    state = BasicLayersState()
    front = next(
        layer for layer in state.layers
        if default_stack_position_for_slot(layer.slot_id) > 2)
    front.asset_path = "front.png"
    front.transform = LayerTransform(scale=0.6, rotation_deg=45.0)

    canvas_w = canvas_h = 80
    character = numpy.zeros((canvas_h, canvas_w, 4), dtype=numpy.uint8)
    sprite = _solid_rgba(512, 512, (10, 10, 240))

    def loader(layer):
        return sprite if layer.slot_id == front.slot_id else None

    ctx = BindingContext(canvas_width=canvas_w, canvas_height=canvas_h)
    rotated = compose_full_stack_rgba(
        state, loader, canvas_w, canvas_h, character, ctx)

    front.transform = LayerTransform(scale=0.6, rotation_deg=0.0)
    axis_aligned = compose_full_stack_rgba(
        state, loader, canvas_w, canvas_h, character, ctx)

    # A 45deg rotated square covers different pixels than the axis-aligned one.
    assert not numpy.array_equal(rotated[:, :, 3], axis_aligned[:, :, 3])
    # Center stays opaque under both.
    assert int(rotated[canvas_h // 2, canvas_w // 2, 3]) == 255


def test_swing_motion_runs_without_error() -> None:
    state = BasicLayersState()
    front = next(
        layer for layer in state.layers
        if default_stack_position_for_slot(layer.slot_id) > 2)
    front.asset_path = "front.png"
    front.transform = LayerTransform(scale=0.5)
    front.motion_mode = MOTION_MODE_SIMPLE_SWING
    front.swing_amplitude_deg = 20.0
    front.swing_speed_deg_per_sec = 60.0

    canvas_w = canvas_h = 64
    character = numpy.zeros((canvas_h, canvas_w, 4), dtype=numpy.uint8)
    sprite = _solid_rgba(512, 512, (200, 200, 0))

    def loader(layer):
        return sprite if layer.slot_id == front.slot_id else None

    ctx0 = BindingContext(
        canvas_width=canvas_w, canvas_height=canvas_h, motion_time_s=0.0)
    ctx1 = BindingContext(
        canvas_width=canvas_w, canvas_height=canvas_h, motion_time_s=0.5)
    frame0 = compose_full_stack_rgba(state, loader, canvas_w, canvas_h, character, ctx0)
    frame1 = compose_full_stack_rgba(state, loader, canvas_w, canvas_h, character, ctx1)
    assert frame0.shape == frame1.shape == (canvas_h, canvas_w, 4)
    # Swing at different times yields different coverage.
    assert not numpy.array_equal(frame0[:, :, 3], frame1[:, :, 3])


def test_asset_cache_numpy_rgba_png() -> None:
    import tempfile
    from PIL import Image

    with tempfile.TemporaryDirectory() as tmp:
        png_path = Path(tmp) / "sprite.png"
        img = Image.new("RGBA", (40, 24), (10, 20, 30, 0))
        # opaque red block in the middle
        for y in range(6, 18):
            for x in range(10, 30):
                img.putpixel((x, y), (220, 30, 40, 255))
        img.save(png_path)

        cache = LayerAssetCache(lambda p: str(png_path) if p == "sprite.png" else p)
        layer = BasicLayerSlot(slot_id=0, asset_path="sprite.png")
        rgba = cache.load_image_rgba(layer)
        assert rgba is not None
        assert rgba.shape == (24, 40, 4)
        assert rgba.dtype == numpy.uint8
        # fully transparent pixels get rgb zeroed (sanitized)
        assert tuple(rgba[0, 0]) == (0, 0, 0, 0)
        assert int(rgba[12, 20, 3]) == 255
        # second call hits cache and returns identical buffer
        assert cache.load_image_rgba(layer) is rgba
        cache.close()


def test_asset_cache_numpy_rgba_gif() -> None:
    import tempfile
    from PIL import Image, ImageDraw

    with tempfile.TemporaryDirectory() as tmp:
        gif_path = Path(tmp) / "anim.gif"
        frames = []
        for _ in range(3):
            frame = Image.new("P", (32, 32), 0)
            frame.putpalette([0, 0, 0, 255, 0, 0] + [0, 0, 0] * 254)
            draw = ImageDraw.Draw(frame)
            draw.rectangle((8, 8, 24, 24), fill=1)
            frames.append(frame)
        frames[0].save(
            gif_path, save_all=True, append_images=frames[1:],
            duration=80, loop=0, transparency=0, disposal=2)

        cache = LayerAssetCache(lambda p: str(gif_path) if p == "anim.gif" else p)
        layer = BasicLayerSlot(slot_id=0, asset_path="anim.gif")
        rgba = cache.load_image_rgba(layer, now=0.0)
        assert rgba is not None
        assert rgba.shape == (32, 32, 4)
        # corner transparent, sprite center opaque
        assert int(rgba[0, 0, 3]) == 0
        assert int(rgba[16, 16, 3]) == 255
        cache.close()


def main() -> None:
    test_zorder_front_layer_over_character()
    test_behind_layer_hidden_by_opaque_character()
    test_transparent_canvas_when_empty()
    test_small_layer_placement_and_alpha()
    test_rotation_changes_corner_coverage()
    test_swing_motion_runs_without_error()
    test_asset_cache_numpy_rgba_png()
    test_asset_cache_numpy_rgba_gif()
    print("smoke_numpy_compositor_ok")


if __name__ == "__main__":
    main()
