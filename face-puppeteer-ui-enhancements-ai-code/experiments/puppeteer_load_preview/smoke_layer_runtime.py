"""Smoke tests for layer binding resolution (no GUI)."""
from __future__ import annotations

import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from layer_interaction import LayerEditMode, hit_test_layer_edit
from layer_runtime import (
    BINDING_CHARACTER_BODY,
    BINDING_CHARACTER_HEAD,
    BasicLayerSlot,
    BasicLayersState,
    BindingContext,
    HeadBindingPoseFilter,
    LayerBindingSmoother,
    LayerGeometryResolver,
    LayerTransform,
    contrast_highlight_colour,
    _load_gif_composited_frames,
    classify_layer_asset_kind,
    clamp_neck_anchor_ratio,
    NECK_ANCHOR_RATIO_MAX,
    NECK_ANCHOR_RATIO_MIN,
    apply_body_head_tilt_opposite_to_pose,
    bind_ray_percent_to_ratio,
    layer_asset_kind_label,
    layer_binding_ray_percent,
    collect_spine_binding_markers,
    build_spine_diagram_points,
    effective_layer_rotation_deg,
    format_layer_row_summary,
    format_layer_row_title,
    normalize_binding_target,
    resolved_layer_rotation_deg,
    resolve_layer_rects,
    truncate_display_filename,
)


class _MockImage:
    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height

    def GetWidth(self) -> int:
        return self._width

    def GetHeight(self) -> int:
        return self._height


def _asset_loader(_layer: BasicLayerSlot) -> _MockImage:
    return _MockImage(128, 128)


def test_binding_migration() -> None:
    assert normalize_binding_target("character") == BINDING_CHARACTER_BODY
    assert normalize_binding_target("character:head") == BINDING_CHARACTER_HEAD
    assert normalize_binding_target("layer:2") == "layer:2"
    assert normalize_binding_target(None) is None


def test_body_vs_head_vs_free() -> None:
    state = BasicLayersState()
    for index, layer in enumerate(state.layers):
        layer.asset_path = f"layer_{index}.png"
        layer.transform = LayerTransform(offset_x=20.0, offset_y=-10.0, scale=1.0)

    ctx = BindingContext(
        canvas_width=768,
        canvas_height=768,
        display_offset_x=40.0,
        display_offset_y=-20.0,
        display_scale=1.2,
        display_rotation_deg=15.0,
    )
    free = LayerGeometryResolver.resolve_all(state, _asset_loader, 768, 768, ctx)
    state.layers[0].binding_parent = BINDING_CHARACTER_BODY
    state.layers[1].binding_parent = BINDING_CHARACTER_HEAD
    bound = LayerGeometryResolver.resolve_all(state, _asset_loader, 768, 768, ctx)

    free_center = (
        free[0].draw_x + free[0].draw_width / 2.0,
        free[0].draw_y + free[0].draw_height / 2.0,
    )
    body_center = (
        bound[0].draw_x + bound[0].draw_width / 2.0,
        bound[0].draw_y + bound[0].draw_height / 2.0,
    )
    head_center = (
        bound[1].draw_x + bound[1].draw_width / 2.0,
        bound[1].draw_y + bound[1].draw_height / 2.0,
    )
    assert free_center != body_center
    assert body_center != head_center
    assert bound[0].draw_width > free[0].draw_width
    assert abs(bound[1].draw_width - free[1].draw_width) < 1e-3


def test_layer_follow_parent() -> None:
    state = BasicLayersState()
    parent = state.layers[0]
    child = state.layers[1]
    parent.asset_path = "parent.png"
    child.asset_path = "child.png"
    parent.transform = LayerTransform(offset_x=0.0, offset_y=0.0, scale=1.0)
    child.transform = LayerTransform(offset_x=30.0, offset_y=0.0, scale=1.0)
    child.binding_parent = "layer:0"

    ctx = BindingContext(canvas_width=512, canvas_height=512)
    resolved = LayerGeometryResolver.resolve_all(state, _asset_loader, 512, 512, ctx)
    parent_cx = resolved[0].draw_x + resolved[0].draw_width / 2.0
    child_cx = resolved[1].draw_x + resolved[1].draw_width / 2.0
    assert child_cx > parent_cx


def test_head_pose_binding_offset() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "halo.png"
    layer.transform = LayerTransform(offset_x=0.0, offset_y=-40.0, scale=1.0)
    layer.binding_parent = BINDING_CHARACTER_HEAD
    layer.binding_follow_rotation_same = True

    neutral = BindingContext(
        canvas_width=768,
        canvas_height=768,
        display_offset_x=0.0,
        display_offset_y=0.0,
        display_scale=1.0,
        display_rotation_deg=0.0,
        pose_head_x=0.0,
        pose_head_y=0.0,
        pose_neck_z=0.0,
    )
    posed = BindingContext(
        canvas_width=768,
        canvas_height=768,
        display_offset_x=0.0,
        display_offset_y=0.0,
        display_scale=1.0,
        display_rotation_deg=5.0,
        pose_head_x=0.0,
        pose_head_y=0.5,
        pose_neck_z=0.5,
    )
    neutral_rect = LayerGeometryResolver.resolve_all(state, _asset_loader, 768, 768, neutral)[0]
    posed_rect = LayerGeometryResolver.resolve_all(state, _asset_loader, 768, 768, posed)[0]
    neutral_cx = neutral_rect.draw_x + neutral_rect.draw_width / 2.0
    posed_cx = posed_rect.draw_x + posed_rect.draw_width / 2.0
    assert abs(posed_cx - neutral_cx) > 0.5
    expected_rot = posed.spine_ray_angle_deg() + posed.pose_head_roll_deg()
    assert abs(posed.head_binding_rotation_deg() - expected_rot) < 1e-3


def test_mocap_extra_gain() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.transform = LayerTransform(rotation_deg=0.0)
    layer.binding_parent = BINDING_CHARACTER_HEAD
    layer.binding_follow_rotation_same = True

    ctx = BindingContext(
        canvas_width=512,
        canvas_height=512,
        display_rotation_deg=30.0,
        pose_neck_z=0.5,
    )
    assert abs(effective_layer_rotation_deg(layer, state, ctx) - 37.5) < 1e-6

    layer.binding_follow_mocap_roll = True
    expected = 30.0 + 0.5 * 15.0 * 1.55
    assert abs(effective_layer_rotation_deg(layer, state, ctx) - expected) < 1e-6


def test_follow_rotation_character() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.transform = LayerTransform(rotation_deg=0.0)
    layer.binding_parent = BINDING_CHARACTER_HEAD
    layer.binding_follow_rotation_same = True

    ctx = BindingContext(
        canvas_width=512,
        canvas_height=512,
        display_rotation_deg=30.0,
        pose_neck_z=0.0,
    )
    assert abs(effective_layer_rotation_deg(layer, state, ctx) - 30.0) < 1e-6

    ctx.pose_neck_z = 0.5
    assert abs(effective_layer_rotation_deg(layer, state, ctx) - 37.5) < 1e-6

    layer.binding_follow_mocap_roll = True
    expected = 30.0 + 0.5 * 15.0 * 1.55
    assert abs(effective_layer_rotation_deg(layer, state, ctx) - expected) < 1e-6

    layer.binding_follow_rotation_same = False
    layer.binding_follow_rotation_reverse = True
    ctx.pose_neck_z = 0.0
    assert abs(effective_layer_rotation_deg(layer, state, ctx) - (-30.0)) < 1e-6


def test_follow_rotation_layer_chain() -> None:
    state = BasicLayersState()
    parent = state.layers[0]
    child = state.layers[1]
    parent.transform = LayerTransform(rotation_deg=10.0)
    child.transform = LayerTransform(rotation_deg=7.0)
    child.binding_parent = "layer:0"
    child.binding_follow_rotation_same = True

    ctx = BindingContext(canvas_width=512, canvas_height=512)
    assert abs(effective_layer_rotation_deg(child, state, ctx) - 17.0) < 1e-6


def test_follow_rotation_legacy_migration() -> None:
    layer = BasicLayerSlot.from_dict(
        {"binding_follow_rotation": True, "transform": {}},
        slot_id=0)
    assert layer.binding_follow_rotation_same is True
    assert layer.binding_follow_rotation_reverse is False


def test_follow_rotation_both_cancel() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.transform = LayerTransform(rotation_deg=12.0)
    layer.binding_parent = BINDING_CHARACTER_BODY
    layer.binding_follow_rotation_same = True
    layer.binding_follow_rotation_reverse = True

    ctx = BindingContext(
        canvas_width=512,
        canvas_height=512,
        display_rotation_deg=20.0,
    )
    assert abs(effective_layer_rotation_deg(layer, state, ctx) - 12.0) < 1e-6


def test_contrast_highlight_colour() -> None:
    colour = contrast_highlight_colour(0, 0, 0)
    assert colour.Red() == 255 and colour.Green() == 255 and colour.Blue() == 255
    colour = contrast_highlight_colour(180, 180, 180)
    assert colour.Red() == 75 and colour.Green() == 75 and colour.Blue() == 75


def test_binding_smooth_reduces_jump() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "sword.png"
    layer.binding_parent = BINDING_CHARACTER_HEAD
    layer.binding_follow_smooth = True
    layer.binding_follow_mocap_position = True

    ctx = BindingContext(canvas_width=512, canvas_height=512, pose_head_y=1.0)
    smoother = LayerBindingSmoother(alpha=0.28)
    ctx.binding_smoother = smoother
    first = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    first_cx = first.draw_x + first.draw_width / 2.0
    ctx.pose_head_y = -1.0
    second = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    second_cx = second.draw_x + second.draw_width / 2.0
    raw = LayerGeometryResolver.resolve_all(state, _asset_loader, 512, 512, ctx)[0]
    raw_cx = raw.draw_x + raw.draw_width / 2.0
    assert abs(second_cx - first_cx) < abs(raw_cx - first_cx)


def test_head_spine_ray_follows_tilt() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "halo.png"
    layer.transform = LayerTransform(offset_x=0.0, offset_y=-80.0, scale=1.0)
    layer.binding_parent = BINDING_CHARACTER_HEAD

    upright = BindingContext(
        canvas_width=512,
        canvas_height=512,
        display_rotation_deg=0.0,
        display_scale=1.0,
        body_tilt_opposite_to_head=False,
    )
    tilted = BindingContext(
        canvas_width=512,
        canvas_height=512,
        display_rotation_deg=25.0,
        display_scale=1.0,
        body_tilt_opposite_to_head=False,
    )
    up_rect = LayerGeometryResolver.resolve_all(state, _asset_loader, 512, 512, upright)[0]
    tilt_rect = LayerGeometryResolver.resolve_all(state, _asset_loader, 512, 512, tilted)[0]
    up_cx = up_rect.draw_x + up_rect.draw_width / 2.0
    tilt_cx = tilt_rect.draw_x + tilt_rect.draw_width / 2.0
    up_cy = up_rect.draw_y + up_rect.draw_height / 2.0
    tilt_cy = tilt_rect.draw_y + tilt_rect.draw_height / 2.0
    assert tilt_cx > up_cx + 5.0
    assert tilt_cy > up_cy + 2.0
    _, _, ray_deg = tilted.character_head_on_spine_ray()
    assert abs(ray_deg - 25.0) < 1e-3


def test_head_binding_pose_filter() -> None:
    filt = HeadBindingPoseFilter(deadzone=0.03, max_step=0.05)
    x0, y0, z0 = filt.filter(0.0, 0.0, 0.0)
    assert x0 == y0 == z0 == 0.0
    x1, _, _ = filt.filter(1.0, 0.0, 0.0)
    assert x1 <= 0.06
    x2, _, _ = filt.filter(1.0, 0.0, 0.0)
    assert x2 <= 0.12


def test_force_full_layer_follow_bypasses_smoother() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "sword.png"
    layer.binding_parent = BINDING_CHARACTER_HEAD
    layer.binding_follow_smooth = True
    layer.binding_follow_mocap_position = True

    ctx = BindingContext(
        canvas_width=512,
        canvas_height=512,
        pose_head_y=1.0,
        force_full_layer_follow=True,
    )
    smoother = LayerBindingSmoother(alpha=0.28)
    ctx.binding_smoother = smoother
    first = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    first_cx = first.draw_x + first.draw_width / 2.0
    ctx.pose_head_y = -1.0
    second = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    second_cx = second.draw_x + second.draw_width / 2.0
    assert abs(second_cx - first_cx) > 1.0


def test_per_layer_smooth_alpha() -> None:
    layer = BasicLayerSlot.from_dict(
        {"binding_follow_smooth_alpha": 0.55, "binding_follow_smooth": True},
        slot_id=0)
    assert abs(layer.binding_follow_smooth_alpha - 0.55) < 1e-6
    data = layer.to_dict()
    assert abs(float(data["binding_follow_smooth_alpha"]) - 0.55) < 1e-6


def test_gif_transparency_compositing() -> None:
    import tempfile
    from PIL import Image, ImageDraw

    with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as tmp:
        gif_path = tmp.name
    try:
        frames = []
        for i in range(2):
            img = Image.new("P", (32, 32), 0)
            palette = [0, 0, 0, 255, 0, 255] + [0, 0, 0] * 254
            img.putpalette(palette)
            draw = ImageDraw.Draw(img)
            draw.rectangle((8, 8, 24, 24), fill=1)
            frames.append(img)
        frames[0].save(
            gif_path,
            save_all=True,
            append_images=frames[1:],
            duration=100,
            loop=0,
            transparency=0,
            disposal=2)
        pil_frames, _ = _load_gif_composited_frames(gif_path)
        assert pil_frames, "expected composited GIF frames"
        alpha = pil_frames[0].getchannel("A")
        transparent = sum(1 for y in range(32) for x in range(32) if alpha.getpixel((x, y)) == 0)
        assert transparent > 700, f"expected mostly transparent canvas, got {transparent}"
        opaque = sum(1 for y in range(32) for x in range(32) if alpha.getpixel((x, y)) == 255)
        assert opaque > 200, f"expected opaque sprite pixels, got {opaque}"
    finally:
        Path(gif_path).unlink(missing_ok=True)


def test_classify_layer_asset_kind() -> None:
    assert classify_layer_asset_kind(None) == "empty"
    assert classify_layer_asset_kind("layer.png") == "image"
    assert classify_layer_asset_kind("anim.gif") == "gif"
    assert classify_layer_asset_kind("clip.mp4") == "unknown"
    assert layer_asset_kind_label("gif") == "GIF"


def test_format_layer_row_labels() -> None:
    layer = BasicLayerSlot(
        slot_id=2,
        asset_path="assets/very_long_weapon_name_here.png",
        binding_parent=BINDING_CHARACTER_HEAD,
        binding_follow_rotation_same=True,
        binding_follow_smooth=True,
        binding_follow_smooth_alpha=0.32,
    )
    title = format_layer_row_title(2, layer)
    assert "图层 3" in title
    assert "…" in title or len(title) < 40
    summary = format_layer_row_summary(layer)
    assert "平滑32%" in summary
    assert "同步" in summary
    truncated = truncate_display_filename("abcdefghijklmnop.png", 12)
    assert len(truncated) == 12
    assert "…" in truncated
    assert truncated.startswith("abcde")


def test_low_smooth_alpha_slower_follow() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "sword.png"
    layer.binding_parent = BINDING_CHARACTER_HEAD
    layer.binding_follow_smooth = True
    layer.binding_follow_smooth_alpha = 0.08

    ctx = BindingContext(canvas_width=512, canvas_height=512, pose_head_y=1.0)
    smoother = LayerBindingSmoother()
    ctx.binding_smoother = smoother
    first = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    first_cx = first.draw_x + first.draw_width / 2.0
    ctx.pose_head_y = -1.0
    slow = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    slow_cx = slow.draw_x + slow.draw_width / 2.0
    slow_delta = abs(slow_cx - first_cx)

    smoother.reset_all()
    layer.binding_follow_smooth_alpha = 0.9
    ctx.pose_head_y = 1.0
    first_fast = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    first_fast_cx = first_fast.draw_x + first_fast.draw_width / 2.0
    ctx.pose_head_y = -1.0
    fast = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    fast_cx = fast.draw_x + fast.draw_width / 2.0
    fast_delta = abs(fast_cx - first_fast_cx)
    assert fast_delta > slow_delta + 0.5


def test_spine_binding_markers() -> None:
    state = BasicLayersState()
    body_layer = state.layers[0]
    body_layer.asset_path = "cape.png"
    body_layer.binding_parent = BINDING_CHARACTER_BODY
    head_layer = state.layers[1]
    head_layer.asset_path = "halo.png"
    head_layer.binding_parent = BINDING_CHARACTER_HEAD
    head_layer.transform = LayerTransform(offset_x=0.0, offset_y=-20.0)
    ctx = BindingContext(
        canvas_width=512,
        canvas_height=512,
        body_bind_ray_percent=75.0,
        head_bind_ray_percent=85.0)
    markers = collect_spine_binding_markers(state, ctx, _asset_loader)
    kinds = {m.marker_kind for m in markers}
    assert "body_anchor" in kinds
    assert "head_anchor" in kinds
    assert "body_layer" in kinds
    assert "head_layer" in kinds
    body_anchor = next(m for m in markers if m.marker_kind == "body_anchor")
    head_anchor = next(m for m in markers if m.marker_kind == "head_anchor")
    assert abs(body_anchor.t - 0.75) < 1e-6
    assert abs(head_anchor.t - 0.85) < 1e-6
    assert head_anchor.height_ratio > body_anchor.height_ratio


def test_unbounded_bind_ray_percent() -> None:
    ctx = BindingContext(canvas_width=512, canvas_height=512)
    x0, y0, _ = ctx.character_body_bind_on_spine(ray_percent=100.0)
    x1, y1, _ = ctx.character_body_bind_on_spine(ray_percent=150.0)
    x2, y2, _ = ctx.character_body_bind_on_spine(ray_percent=-20.0)
    assert y1 < y0 < y2


def test_body_head_tilt_opposite_splits_pose_roll() -> None:
    pose = [0.0] * 45
    pose[10] = 0.5
    pose[11] = 0.5
    opposite = apply_body_head_tilt_opposite_to_pose(
        pose, neck_z_index=10, body_z_index=11, opposite=True)
    assert opposite[10] == 0.5
    assert opposite[11] == -0.5
    unchanged = apply_body_head_tilt_opposite_to_pose(
        pose, neck_z_index=10, body_z_index=11, opposite=False)
    assert unchanged[10] == 0.5
    assert unchanged[11] == 0.5


def test_spine_body_opposite_to_head_angles() -> None:
    ctx = BindingContext(
        canvas_width=512,
        canvas_height=512,
        display_rotation_deg=20.0,
        body_tilt_opposite_to_head=True,
    )
    assert abs(ctx.spine_lower_angle_deg() - (-20.0)) < 1e-6
    assert abs(ctx.spine_upper_angle_deg() - 20.0) < 1e-6
    ctx_same = BindingContext(
        canvas_width=512,
        canvas_height=512,
        display_rotation_deg=20.0,
        body_tilt_opposite_to_head=False,
    )
    assert abs(ctx_same.spine_lower_angle_deg() - 20.0) < 1e-6
    assert abs(ctx_same.spine_upper_angle_deg() - 20.0) < 1e-6


def test_global_neck_ratio_does_not_move_layer() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "cape.png"
    layer.binding_parent = BINDING_CHARACTER_BODY
    layer.binding_ray_percent = 100.0
    layer.binding_neck_anchor_ratio = 0.62
    ctx_a = BindingContext(canvas_width=512, canvas_height=512, neck_anchor_ratio=0.40)
    ctx_b = BindingContext(canvas_width=512, canvas_height=512, neck_anchor_ratio=0.76)
    rect_a = LayerGeometryResolver.resolve_all(state, _asset_loader, 512, 512, ctx_a)[0]
    rect_b = LayerGeometryResolver.resolve_all(state, _asset_loader, 512, 512, ctx_b)[0]
    cx_a = rect_a.draw_x + rect_a.draw_width / 2.0
    cx_b = rect_b.draw_x + rect_b.draw_width / 2.0
    assert abs(cx_a - cx_b) < 1e-6


def test_neck_anchor_ratio_full_height_range() -> None:
    assert clamp_neck_anchor_ratio(0.0) == NECK_ANCHOR_RATIO_MIN
    assert clamp_neck_anchor_ratio(1.0) == NECK_ANCHOR_RATIO_MAX
    assert NECK_ANCHOR_RATIO_MAX > NECK_ANCHOR_RATIO_MIN


def test_global_bind_percent_does_not_move_layer() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "cape.png"
    layer.binding_parent = BINDING_CHARACTER_BODY
    layer.binding_ray_percent = 100.0
    ctx_a = BindingContext(
        canvas_width=512, canvas_height=512, body_bind_ray_percent=100.0)
    ctx_b = BindingContext(
        canvas_width=512, canvas_height=512, body_bind_ray_percent=40.0)
    rect_a = LayerGeometryResolver.resolve_all(state, _asset_loader, 512, 512, ctx_a)[0]
    rect_b = LayerGeometryResolver.resolve_all(state, _asset_loader, 512, 512, ctx_b)[0]
    cx_a = rect_a.draw_x + rect_a.draw_width / 2.0
    cx_b = rect_b.draw_x + rect_b.draw_width / 2.0
    assert abs(cx_a - cx_b) < 1e-6


def test_smooth_off_uses_raw_binding_rect() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "halo.png"
    layer.binding_parent = BINDING_CHARACTER_HEAD
    layer.binding_follow_smooth = False

    smoother = LayerBindingSmoother()
    ctx = BindingContext(
        canvas_width=512,
        canvas_height=512,
        display_rotation_deg=0.0,
        binding_smoother=smoother)
    resolve_layer_rects(state, _asset_loader, 512, 512, ctx)
    ctx.display_rotation_deg = 30.0
    smoothed = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    raw = LayerGeometryResolver.resolve_all(state, _asset_loader, 512, 512, ctx)[0]
    assert abs(
        smoothed.draw_x + smoothed.draw_width / 2.0
        - (raw.draw_x + raw.draw_width / 2.0)) < 1e-3


def test_hit_test_only_selected_layer() -> None:
    state = BasicLayersState()
    layer0 = state.layers[0]
    layer0.asset_path = "layer0.png"
    layer0.transform.offset_x = -120.0
    layer1 = state.layers[1]
    layer1.asset_path = "layer1.png"
    layer1.transform.offset_x = 120.0
    ctx = BindingContext(canvas_width=512, canvas_height=512)
    resolved = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)
    rect1 = resolved[1]
    cx1 = int(rect1.draw_x + rect1.draw_width / 2.0)
    cy1 = int(rect1.draw_y + rect1.draw_height / 2.0)
    state.selected_slot_id = 0
    slot, mode = hit_test_layer_edit(
        state, _asset_loader, cx1, cy1, 512, 512, ctx, selected_slot_id=0)
    assert slot is None and mode == LayerEditMode.NONE
    rect0 = resolved[0]
    cx0 = int(rect0.draw_x + rect0.draw_width / 2.0)
    cy0 = int(rect0.draw_y + rect0.draw_height / 2.0)
    slot, mode = hit_test_layer_edit(
        state, _asset_loader, cx0, cy0, 512, 512, ctx, selected_slot_id=0)
    assert slot == 0 and mode == LayerEditMode.MOVE
    state.selected_slot_id = 1
    slot, mode = hit_test_layer_edit(
        state, _asset_loader, cx0, cy0, 512, 512, ctx, selected_slot_id=1)
    assert slot is None and mode == LayerEditMode.NONE


def test_head_bind_rotation_follows_when_smooth_off() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "halo.png"
    layer.binding_parent = BINDING_CHARACTER_HEAD
    layer.binding_follow_rotation_same = True
    layer.binding_follow_smooth = False

    smoother = LayerBindingSmoother()
    ctx = BindingContext(
        canvas_width=512,
        canvas_height=512,
        display_rotation_deg=0.0,
        binding_smoother=smoother)
    resolve_layer_rects(state, _asset_loader, 512, 512, ctx)
    ctx.display_rotation_deg = 40.0
    rect = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    rotation = resolved_layer_rotation_deg(layer, state, rect, ctx)
    assert abs(rotation - 40.0) < 0.5


def test_body_bind_follow_rotation() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "cape.png"
    layer.binding_parent = BINDING_CHARACTER_BODY
    layer.binding_follow_rotation_same = True
    ctx = BindingContext(
        canvas_width=512,
        canvas_height=512,
        display_rotation_deg=22.0,
        body_tilt_opposite_to_head=False,
    )
    assert abs(effective_layer_rotation_deg(layer, state, ctx) - 22.0) < 1e-6
    ctx_opposite = BindingContext(
        canvas_width=512,
        canvas_height=512,
        display_rotation_deg=22.0,
        body_tilt_opposite_to_head=True,
    )
    assert abs(effective_layer_rotation_deg(layer, state, ctx_opposite) - 22.0) < 1e-6
    assert abs(ctx_opposite.spine_lower_angle_deg() - (-22.0)) < 1e-6


def test_spine_diagram_follows_tilt() -> None:
    upright = BindingContext(
        canvas_width=512, canvas_height=512, display_rotation_deg=0.0,
        body_tilt_opposite_to_head=False)
    tilted = BindingContext(
        canvas_width=512, canvas_height=512, display_rotation_deg=30.0,
        body_tilt_opposite_to_head=False)
    up_pts = build_spine_diagram_points(upright)
    tilt_pts = build_spine_diagram_points(tilted)
    assert tilt_pts["head"][0] > up_pts["head"][0] + 5.0
    opposite = BindingContext(
        canvas_width=512, canvas_height=512, display_rotation_deg=30.0,
        body_tilt_opposite_to_head=True)
    opp_pts = build_spine_diagram_points(opposite)
    assert opp_pts["neck"][0] < up_pts["neck"][0] - 2.0
    assert abs(opposite.spine_upper_angle_deg() - 30.0) < 1e-3
    assert abs(opposite.spine_lower_angle_deg() - (-30.0)) < 1e-3


def test_basic_layers_persistence_round_trip(tmp_root: Path | None = None) -> None:
    import tempfile
    from layer_runtime import (
        BINDING_CHARACTER_BODY,
        load_basic_layers_state,
        migrate_layer_bind_neck_ratios,
        migrate_layer_bind_ray_percents,
        save_basic_layers_state,
    )
    from tha3_paths import to_repo_relative

    root = tmp_root or Path(tempfile.mkdtemp())
    ui_state = root / "load_preview_ui_state.json"
    ui_state.write_text("{}", encoding="utf-8")

    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "data/character_models/baiten_from_project_forlon9/bai_450k/parts/beitou.gif"
    layer.binding_parent = BINDING_CHARACTER_BODY
    layer.transform.offset_x = 12.5
    layer.transform.scale = 0.33
    state.selected_slot_id = 0

    def resolve_path(path: str | None) -> str | None:
        if not path:
            return None
        candidate = Path(__file__).resolve().parents[3] / path
        return str(candidate) if candidate.is_file() else path

    save_basic_layers_state(state, str(ui_state), to_repo_relative)
    loaded = load_basic_layers_state(str(ui_state), resolve_path)
    assert loaded.selected_slot_id == 0
    assert loaded.layers[0].transform.offset_x == 12.5
    assert loaded.layers[0].transform.scale == 0.33
    assert loaded.layers[0].binding_ray_percent == 100.0

    fresh = BasicLayersState()
    fresh.layers[0].binding_parent = BINDING_CHARACTER_BODY
    changed = migrate_layer_bind_ray_percents(fresh, 88.0, 110.0)
    changed = migrate_layer_bind_neck_ratios(fresh, 0.42) or changed
    assert changed is True
    assert fresh.layers[0].binding_ray_percent == 88.0
    assert fresh.layers[0].binding_neck_anchor_ratio == 0.42

    save_basic_layers_state(fresh, str(ui_state), to_repo_relative)
    reloaded = load_basic_layers_state(str(ui_state), resolve_path)
    assert reloaded.layers[0].binding_ray_percent == 88.0
    assert reloaded.layers[0].binding_neck_anchor_ratio == 0.42


def main() -> None:
    test_binding_migration()
    test_body_vs_head_vs_free()
    test_layer_follow_parent()
    test_head_pose_binding_offset()
    test_head_spine_ray_follows_tilt()
    test_mocap_extra_gain()
    test_follow_rotation_character()
    test_follow_rotation_layer_chain()
    test_follow_rotation_legacy_migration()
    test_follow_rotation_both_cancel()
    test_contrast_highlight_colour()
    test_binding_smooth_reduces_jump()
    test_head_binding_pose_filter()
    test_force_full_layer_follow_bypasses_smoother()
    test_per_layer_smooth_alpha()
    test_gif_transparency_compositing()
    test_classify_layer_asset_kind()
    test_format_layer_row_labels()
    test_low_smooth_alpha_slower_follow()
    test_spine_binding_markers()
    test_head_bind_rotation_follows_when_smooth_off()
    test_smooth_off_uses_raw_binding_rect()
    test_hit_test_only_selected_layer()
    test_body_bind_follow_rotation()
    test_spine_diagram_follows_tilt()
    test_unbounded_bind_ray_percent()
    test_body_head_tilt_opposite_splits_pose_roll()
    test_basic_layers_persistence_round_trip()
    test_spine_body_opposite_to_head_angles()
    test_global_neck_ratio_does_not_move_layer()
    test_neck_anchor_ratio_full_height_range()
    test_global_bind_percent_does_not_move_layer()
    print("smoke_layer_runtime_ok")


if __name__ == "__main__":
    main()
