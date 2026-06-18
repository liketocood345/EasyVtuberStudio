"""Smoke tests for layer binding resolution (no GUI)."""
from __future__ import annotations

import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from layer_interaction import LayerEditMode, hit_test_layer_edit, hit_test_orbit_edit
from layer_runtime import (
    BINDING_CHARACTER_BODY,
    BINDING_CHARACTER_HEAD,
    DEFAULT_LAYER_COUNT,
    LAYER_MODE_BASIC,
    LAYER_MODE_BASIC_LEGACY,
    MOTION_MODE_CIRCULAR,
    MOTION_MODE_NONE,
    MOTION_MODE_ORBIT_SATELLITE,
    MOTION_MODE_SIMPLE_SWING,
    ORBIT_HOST_SYNC_INTERVAL_S,
    SWING_SPEED_PROFILE_CONSTANT,
    SWING_SPEED_PROFILE_EASE_ENDS,
    BasicLayerSlot,
    BasicLayersState,
    BindingContext,
    HeadBindingPoseFilter,
    LayerBindingSmoother,
    LayerGeometryResolver,
    LayerTransform,
    basic_layers_state_has_active_motion,
    compute_orbit_edit_geometry,
    collect_stack_layer_draws,
    compute_orbit_render_plan,
    layer_uses_orbit_edit_chrome,
    OrbitEditGeometry,
    compute_orbit_state,
    compute_orbit_motion_state,
    layer_orbits_with_host,
    compute_swing_angle_deg,
    contrast_highlight_colour,
    OCCLUSION_BEHIND,
    OCCLUSION_FRONT,
    _load_gif_composited_frames,
    classify_layer_asset_kind,
    clamp_neck_anchor_ratio,
    NECK_ANCHOR_RATIO_MAX,
    NECK_ANCHOR_RATIO_MIN,
    apply_body_head_tilt_opposite_to_pose,
    apply_layer_hotkey_action,
    layer_hotkey_action_target_slot_ids,
    MAX_ORBIT_SATELLITES_PER_HOST,
    orbit_host_has_satellite_capacity,
    orbit_host_satellite_count,
    orbit_satellite_member_slot_ids,
    apply_orbit_requisition_visibility,
    apply_orbit_to_resolved,
    bind_ray_percent_to_ratio,
    layer_asset_kind_label,
    layer_binding_ray_percent,
    layer_has_active_swing,
    layer_has_active_orbit,
    normalize_layer_stack_positions,
    normalize_binding_target,
    parse_layer_binding_slot,
    remove_layers_batch,
    rotate_orbit_plane_offsets,
    sample_orbit_path_canvas_points,
    sanitize_layer_references,
    selection_contiguous_in_ui_list,
    visible_layer_slot_ids_top_to_bottom,
    move_layers_z_order_block,
    collect_spine_binding_markers,
    build_spine_diagram_points,
    effective_layer_rotation_deg,
    format_layer_row_summary,
    format_layer_row_title,
    resolved_layer_rotation_deg,
    resolve_layer_rects,
    resolve_stack_layer_draw,
    normalize_orbit_aux_slot_id,
    orbit_aux_carriers,
    orbit_aux_owner,
    orbit_aux_slot_is_allowed,
    orbit_frame_plan,
    orbit_upper_lower_slot_ids,
    resolve_orbit_track_layer,
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
    # Binding smoothing now applies to ROTATION only (position follows instantly,
    # see LayerBindingSmoother.apply): a bound sprite's roll should lag a sudden
    # target change relative to the raw (unsmoothed) rotation.
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "sword.png"
    layer.binding_parent = BINDING_CHARACTER_BODY
    layer.binding_follow_smooth = True
    layer.binding_follow_rotation_same = True

    ctx = BindingContext(canvas_width=512, canvas_height=512, display_rotation_deg=0.0)
    smoother = LayerBindingSmoother(alpha=0.28)
    ctx.binding_smoother = smoother
    first = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    first_rot = first.smoothed_rotation_deg
    ctx.display_rotation_deg = 40.0
    second = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    second_rot = second.smoothed_rotation_deg
    raw_rot = effective_layer_rotation_deg(layer, state, ctx)
    assert first_rot is not None and second_rot is not None
    assert abs(second_rot - first_rot) < abs(raw_rot - first_rot)


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
    # Rotation smoothing: a low alpha follows a rotation step more slowly than a
    # high alpha (position is now instant and no longer alpha-dependent).
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "sword.png"
    layer.binding_parent = BINDING_CHARACTER_BODY
    layer.binding_follow_smooth = True
    layer.binding_follow_rotation_same = True
    layer.binding_follow_smooth_alpha = 0.08

    ctx = BindingContext(canvas_width=512, canvas_height=512, display_rotation_deg=0.0)
    smoother = LayerBindingSmoother()
    ctx.binding_smoother = smoother
    first = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    first_rot = first.smoothed_rotation_deg
    ctx.display_rotation_deg = 40.0
    slow = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    slow_delta = abs(slow.smoothed_rotation_deg - first_rot)

    smoother.reset_all()
    layer.binding_follow_smooth_alpha = 0.9
    ctx.display_rotation_deg = 0.0
    first_fast = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    first_fast_rot = first_fast.smoothed_rotation_deg
    ctx.display_rotation_deg = 40.0
    fast = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    fast_delta = abs(fast.smoothed_rotation_deg - first_fast_rot)
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


def test_swing_ease_ends_starts_at_zero() -> None:
    layer = BasicLayerSlot(
        slot_id=0,
        motion_mode=MOTION_MODE_SIMPLE_SWING,
        swing_amplitude_deg=20.0,
        swing_speed_deg_per_sec=40.0,
        swing_speed_profile=SWING_SPEED_PROFILE_EASE_ENDS,
        swing_phase_rad=0.0)
    assert abs(compute_swing_angle_deg(layer, 0.0)) < 1e-6


def test_swing_ease_ends_peak_velocity() -> None:
    layer = BasicLayerSlot(
        slot_id=0,
        motion_mode=MOTION_MODE_SIMPLE_SWING,
        swing_amplitude_deg=10.0,
        swing_speed_deg_per_sec=30.0,
        swing_speed_profile=SWING_SPEED_PROFILE_EASE_ENDS,
        swing_phase_rad=0.0)
    dt = 0.01
    angle0 = compute_swing_angle_deg(layer, 0.0)
    angle1 = compute_swing_angle_deg(layer, dt)
    approx_velocity = (angle1 - angle0) / dt
    assert abs(approx_velocity - 30.0) < 2.0


def test_swing_constant_triangle_bounds() -> None:
    layer = BasicLayerSlot(
        slot_id=0,
        motion_mode=MOTION_MODE_SIMPLE_SWING,
        swing_amplitude_deg=12.0,
        swing_speed_deg_per_sec=24.0,
        swing_speed_profile=SWING_SPEED_PROFILE_CONSTANT,
        swing_phase_rad=0.0)
    half_period = (2.0 * layer.swing_amplitude_deg) / layer.swing_speed_deg_per_sec
    assert abs(compute_swing_angle_deg(layer, 0.0) + 12.0) < 1e-6
    assert abs(compute_swing_angle_deg(layer, half_period) - 12.0) < 1e-3


def test_swing_constant_velocity_segment() -> None:
    layer = BasicLayerSlot(
        slot_id=0,
        motion_mode=MOTION_MODE_SIMPLE_SWING,
        swing_amplitude_deg=10.0,
        swing_speed_deg_per_sec=20.0,
        swing_speed_profile=SWING_SPEED_PROFILE_CONSTANT,
        swing_phase_rad=0.0)
    dt = 0.05
    angle0 = compute_swing_angle_deg(layer, 0.0)
    angle1 = compute_swing_angle_deg(layer, dt)
    assert abs((angle1 - angle0) / dt - 20.0) < 0.5


def test_swing_zero_amplitude() -> None:
    layer = BasicLayerSlot(
        slot_id=0,
        motion_mode=MOTION_MODE_SIMPLE_SWING,
        swing_amplitude_deg=0.0,
        swing_speed_deg_per_sec=30.0)
    assert compute_swing_angle_deg(layer, 1.0) == 0.0
    assert not layer_has_active_swing(layer)


def test_swing_motion_active_flag() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "tail.png"
    layer.motion_mode = MOTION_MODE_SIMPLE_SWING
    assert basic_layers_state_has_active_motion(state)
    layer.motion_mode = MOTION_MODE_NONE
    assert not basic_layers_state_has_active_motion(state)


def test_swing_serialization_round_trip() -> None:
    layer = BasicLayerSlot(
        slot_id=1,
        motion_mode=MOTION_MODE_SIMPLE_SWING,
        swing_pivot_u=0.25,
        swing_pivot_v=0.8,
        swing_amplitude_deg=22.0,
        swing_speed_deg_per_sec=55.0,
        swing_speed_profile=SWING_SPEED_PROFILE_CONSTANT,
        swing_phase_rad=1.2)
    data = layer.to_dict()
    restored = BasicLayerSlot.from_dict(data, slot_id=1)
    assert restored.motion_mode == MOTION_MODE_SIMPLE_SWING
    assert abs(restored.swing_pivot_u - 0.25) < 1e-6
    assert abs(restored.swing_pivot_v - 0.8) < 1e-6
    assert abs(restored.swing_amplitude_deg - 22.0) < 1e-6
    assert abs(restored.swing_speed_deg_per_sec - 55.0) < 1e-6
    assert restored.swing_speed_profile == SWING_SPEED_PROFILE_CONSTANT


def test_layer_mode_basic_five_migrates() -> None:
    state = BasicLayersState.from_dict({"layer_mode": LAYER_MODE_BASIC_LEGACY})
    assert state.layer_mode == LAYER_MODE_BASIC


def test_add_layer_unique_slot_id() -> None:
    state = BasicLayersState()
    first_id = state.layers[-1].slot_id
    added = state.add_layer()
    assert added.slot_id == first_id + 1
    assert len(state.layers) == 6


def test_remove_layer_clears_references() -> None:
    state = BasicLayersState()
    parent = state.layers[0]
    child = state.layers[1]
    orbit = state.add_layer()
    parent.asset_path = "a.png"
    child.asset_path = "b.png"
    orbit.asset_path = "c.png"
    child.binding_parent = "layer:0"
    orbit.motion_mode = MOTION_MODE_CIRCULAR
    orbit.orbit_aux_slot_id = child.slot_id
    assert state.remove_layer(child.slot_id)
    assert orbit.orbit_aux_slot_id is None
    other = state.layers[1]
    other.binding_parent = f"layer:{parent.slot_id}"
    assert state.remove_layer(parent.slot_id)
    assert other.binding_parent is None


def test_sanitize_layer_references_on_load() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.binding_parent = "layer:999"
    layer.orbit_aux_slot_id = 998
    sanitize_layer_references(state)
    assert layer.binding_parent is None
    assert layer.orbit_aux_slot_id is None


def test_layer_binding_accepts_dynamic_slot_ids() -> None:
    state = BasicLayersState()
    parent = state.add_layer()
    child = state.add_layer()
    normalized = normalize_binding_target(f"layer:{parent.slot_id}")
    assert normalized == f"layer:{parent.slot_id}"
    child.binding_parent = normalized
    assert parse_layer_binding_slot(child.binding_parent) == parent.slot_id


def test_orbit_requires_asset_for_active_motion() -> None:
    layer = BasicLayerSlot(
        slot_id=0,
        motion_mode=MOTION_MODE_CIRCULAR,
        orbit_radius=50.0,
        orbit_speed_deg_per_sec=30.0)
    assert not layer_has_active_orbit(layer)
    layer.asset_path = "prop.png"
    assert layer_has_active_orbit(layer)


def test_requisitioned_aux_never_draws_native_asset() -> None:
    state = BasicLayersState()
    main = state.layers[0]
    aux = state.layers[1]
    main.asset_path = "main.png"
    aux.asset_path = "aux.png"
    main.occlusion = OCCLUSION_FRONT
    aux.occlusion = OCCLUSION_BEHIND
    main.motion_mode = MOTION_MODE_CIRCULAR
    main.orbit_radius = 60.0
    main.orbit_speed_deg_per_sec = 90.0
    main.orbit_plane_tilt_deg = 45.0
    main.orbit_aux_slot_id = aux.slot_id
    apply_orbit_requisition_visibility(state)
    assert not aux.visible
    normalize_layer_stack_positions(state)
    ctx = BindingContext(canvas_width=512, canvas_height=512, motion_time_s=3.0)
    draws = collect_stack_layer_draws(state, _asset_loader, 512, 512, ctx)
    assert draws == [(aux.slot_id, main.slot_id)]
    resolved = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)
    assert aux.slot_id in resolved
    assert main.slot_id not in resolved
    static = resolve_layer_rects(
        state, _asset_loader, 512, 512,
        BindingContext(canvas_width=512, canvas_height=512, motion_time_s=None))
    assert aux.slot_id not in static


def test_orbit_stack_draws_owner_on_each_side() -> None:
    state = BasicLayersState()
    main = state.layers[0]
    aux = state.layers[1]
    main.asset_path = "main.png"
    aux.asset_path = "aux.png"
    main.occlusion = OCCLUSION_FRONT
    aux.occlusion = OCCLUSION_BEHIND
    main.motion_mode = MOTION_MODE_CIRCULAR
    main.orbit_radius = 60.0
    main.orbit_speed_deg_per_sec = 90.0
    main.orbit_plane_tilt_deg = 45.0
    main.orbit_aux_slot_id = aux.slot_id
    apply_orbit_requisition_visibility(state)
    normalize_layer_stack_positions(state)
    ctx = BindingContext(canvas_width=512, canvas_height=512, motion_time_s=0.0)
    near_draws = collect_stack_layer_draws(state, _asset_loader, 512, 512, ctx)
    assert near_draws == [(main.slot_id, main.slot_id)]
    far_ctx = BindingContext(canvas_width=512, canvas_height=512, motion_time_s=3.0)
    far_draws = collect_stack_layer_draws(state, _asset_loader, 512, 512, far_ctx)
    assert far_draws == [(aux.slot_id, main.slot_id)]
    for _stack_slot, owner_slot in near_draws + far_draws:
        assert owner_slot == main.slot_id


def _enable_orbit_follow(sat: BasicLayerSlot, host: BasicLayerSlot) -> None:
    sat.motion_mode = MOTION_MODE_CIRCULAR
    sat.orbit_host_slot_id = host.slot_id


def test_orbit_follow_clears_host_aux_and_stays_visible() -> None:
    state = BasicLayersState()
    host = state.layers[1]
    sat = state.layers[2]
    host.asset_path = "host.png"
    sat.asset_path = "sat.png"
    host.motion_mode = MOTION_MODE_CIRCULAR
    host.orbit_radius = 80.0
    host.orbit_aux_slot_id = sat.slot_id
    apply_orbit_requisition_visibility(state)
    assert not sat.visible
    _enable_orbit_follow(sat, host)
    sanitize_layer_references(state)
    assert host.orbit_aux_slot_id is None
    assert sat.visible
    overrides, hidden = compute_orbit_render_plan(state, 0.0)
    assert any(p.source_slot_id == host.slot_id for p in overrides.values())
    assert any(p.source_slot_id == sat.slot_id for p in overrides.values())


def test_orbit_aux_cannot_target_orbit_motion_layer() -> None:
    state = BasicLayersState()
    main = state.layers[0]
    other = state.layers[1]
    main.asset_path = "a.png"
    other.asset_path = "b.png"
    main.motion_mode = MOTION_MODE_CIRCULAR
    other.motion_mode = MOTION_MODE_CIRCULAR
    main.orbit_aux_slot_id = other.slot_id
    assert not orbit_aux_slot_is_allowed(state, main.slot_id, other.slot_id)
    sanitize_layer_references(state)
    assert main.orbit_aux_slot_id is None


def test_orbit_aux_cleared_when_target_switches_to_orbit() -> None:
    state = BasicLayersState()
    main = state.layers[0]
    aux = state.layers[1]
    main.asset_path = "a.png"
    aux.asset_path = "b.png"
    main.motion_mode = MOTION_MODE_CIRCULAR
    main.orbit_aux_slot_id = aux.slot_id
    aux.motion_mode = MOTION_MODE_CIRCULAR
    sanitize_layer_references(state)
    assert main.orbit_aux_slot_id is None


def test_orbit_edit_geometry_and_hit() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "prop.png"
    layer.motion_mode = MOTION_MODE_CIRCULAR
    layer.orbit_radius = 50.0
    layer.orbit_speed_deg_per_sec = 60.0
    layer.orbit_plane_tilt_deg = 45.0
    layer.orbit_pivot_u = 0.5
    layer.orbit_pivot_v = 0.5
    assert layer_uses_orbit_edit_chrome(layer)
    ctx = BindingContext(canvas_width=512, canvas_height=512)
    geom = compute_orbit_edit_geometry(state, layer, _asset_loader, 512, 512, ctx)
    assert geom is not None
    assert len(geom.path_points) >= 8
    assert geom.bind_xy is not None
    mid = geom.path_points[len(geom.path_points) // 2]
    slot, mode = hit_test_orbit_edit(geom, int(mid[0]), int(mid[1]))
    assert slot == layer.slot_id
    assert mode == LayerEditMode.ORBIT_MOVE


def test_orbit_follow_edit_geometry_uses_host_track() -> None:
    state = BasicLayersState()
    host = state.layers[1]
    host.asset_path = "host.png"
    host.motion_mode = MOTION_MODE_CIRCULAR
    host.orbit_radius = 70.0
    host.orbit_pivot_u = 0.35
    host.orbit_pivot_v = 0.65
    host.orbit_plane_tilt_deg = 30.0
    sat = state.layers[2]
    sat.asset_path = "sat.png"
    sat.orbit_radius = 10.0
    sat.orbit_pivot_u = 0.8
    sat.orbit_pivot_v = 0.2
    _enable_orbit_follow(sat, host)
    ctx = BindingContext(canvas_width=512, canvas_height=512)
    host_geom = compute_orbit_edit_geometry(state, host, _asset_loader, 512, 512, ctx)
    sat_geom = compute_orbit_edit_geometry(state, sat, _asset_loader, 512, 512, ctx)
    assert host_geom is not None and sat_geom is not None
    assert sat_geom.slot_id == sat.slot_id
    assert len(host_geom.path_points) == len(sat_geom.path_points)
    for hp, sp in zip(host_geom.path_points, sat_geom.path_points):
        assert abs(hp[0] - sp[0]) < 0.5
        assert abs(hp[1] - sp[1]) < 0.5
    assert abs(host_geom.pivot_xy[0] - sat_geom.pivot_xy[0]) < 0.5
    assert resolve_orbit_track_layer(state, sat) is host


def test_orbit_frame_plan_cached_per_binding_context() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "a.png"
    layer.motion_mode = MOTION_MODE_CIRCULAR
    layer.orbit_radius = 50.0
    ctx = BindingContext(canvas_width=512, canvas_height=512, motion_time_s=1.25)
    plan_a = orbit_frame_plan(state, ctx)
    plan_b = orbit_frame_plan(state, ctx)
    assert plan_a is plan_b
    ctx.motion_time_s = 2.0
    plan_c = orbit_frame_plan(state, ctx)
    assert plan_c is not plan_a


def test_orbit_path_follows_sync_and_reverse_rotation() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.motion_mode = MOTION_MODE_CIRCULAR
    layer.orbit_radius = 60.0
    layer.orbit_plane_tilt_deg = 45.0
    layer.binding_parent = BINDING_CHARACTER_HEAD
    ctx_flat = BindingContext(canvas_width=512, canvas_height=512, display_rotation_deg=0.0)
    flat, pivot = sample_orbit_path_canvas_points(
        layer, 512, 512, state=state, binding_context=ctx_flat)
    layer.binding_follow_rotation_same = True
    ctx_sync = BindingContext(canvas_width=512, canvas_height=512, display_rotation_deg=30.0)
    sync, _pivot = sample_orbit_path_canvas_points(
        layer, 512, 512, state=state, binding_context=ctx_sync)
    layer.binding_follow_rotation_same = False
    layer.binding_follow_rotation_reverse = True
    ctx_rev = BindingContext(canvas_width=512, canvas_height=512, display_rotation_deg=30.0)
    reverse, _pivot2 = sample_orbit_path_canvas_points(
        layer, 512, 512, state=state, binding_context=ctx_rev)
    mid_index = len(flat) // 4
    flat_dx = flat[mid_index][0] - pivot[0]
    sync_dx = sync[mid_index][0] - pivot[0]
    rev_dx = reverse[mid_index][0] - pivot[0]
    assert abs(sync_dx - flat_dx) > 1.0
    assert abs(rev_dx - flat_dx) > 1.0
    assert sync_dx * rev_dx < 0.0


def test_orbit_render_plan_with_aux_hides_one_slot() -> None:
    state = BasicLayersState()
    main = state.layers[0]
    aux = state.layers[1]
    main.asset_path = "main.png"
    aux.asset_path = "aux.png"
    main.occlusion = OCCLUSION_FRONT
    aux.occlusion = OCCLUSION_BEHIND
    main.motion_mode = MOTION_MODE_CIRCULAR
    main.orbit_radius = 60.0
    main.orbit_speed_deg_per_sec = 90.0
    main.orbit_plane_tilt_deg = 45.0
    main.orbit_aux_slot_id = aux.slot_id
    normalize_layer_stack_positions(state)
    overrides, hidden = compute_orbit_render_plan(state, 0.0)
    assert len(overrides) == 1
    assert len(hidden) == 1
    shown_id = next(iter(overrides))
    hidden_id = next(iter(hidden))
    assert shown_id != hidden_id
    assert {shown_id, hidden_id} == {main.slot_id, aux.slot_id}
    assert overrides[shown_id].source_slot_id == main.slot_id
    assert orbit_aux_carriers(state)[aux.slot_id] == main.slot_id


def test_orbit_render_plan_switches_shown_slot_with_aux() -> None:
    state = BasicLayersState()
    main = state.layers[0]
    aux = state.layers[1]
    main.asset_path = "main.png"
    aux.asset_path = "aux.png"
    main.occlusion = OCCLUSION_FRONT
    aux.occlusion = OCCLUSION_BEHIND
    main.motion_mode = MOTION_MODE_CIRCULAR
    main.orbit_radius = 60.0
    main.orbit_speed_deg_per_sec = 90.0
    main.orbit_plane_tilt_deg = 45.0
    main.orbit_aux_slot_id = aux.slot_id
    normalize_layer_stack_positions(state)
    near_overrides, _ = compute_orbit_render_plan(state, 0.0)
    far_overrides, _ = compute_orbit_render_plan(state, 3.0)
    assert next(iter(near_overrides)) == main.slot_id
    assert next(iter(far_overrides)) == aux.slot_id


def test_orbit_upper_lower_respects_occlusion() -> None:
    main = BasicLayerSlot(slot_id=0, occlusion=OCCLUSION_FRONT)
    aux = BasicLayerSlot(slot_id=1, occlusion=OCCLUSION_BEHIND)
    upper, lower = orbit_upper_lower_slot_ids(main, aux)
    assert upper == main.slot_id
    assert lower == aux.slot_id


def test_apply_orbit_bootstraps_aux_rect_without_asset() -> None:
    state = BasicLayersState()
    main = state.layers[0]
    aux = state.layers[1]
    main.asset_path = "main.png"
    aux.asset_path = None
    main.occlusion = OCCLUSION_FRONT
    aux.occlusion = OCCLUSION_BEHIND
    main.motion_mode = MOTION_MODE_CIRCULAR
    main.orbit_radius = 60.0
    main.orbit_speed_deg_per_sec = 90.0
    main.orbit_plane_tilt_deg = 45.0
    main.orbit_aux_slot_id = aux.slot_id
    normalize_layer_stack_positions(state)
    ctx = BindingContext(canvas_width=512, canvas_height=512, motion_time_s=3.0)
    resolved = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)
    assert aux.slot_id in resolved
    assert main.slot_id not in resolved
    pair = resolve_stack_layer_draw(
        state,
        aux,
        resolved,
        *compute_orbit_render_plan(state, 3.0))
    assert pair is not None
    assert pair[0].slot_id == main.slot_id


def test_resolve_stack_layer_draw_routes_aux_asset() -> None:
    state = BasicLayersState()
    main = state.layers[0]
    aux = state.layers[1]
    main.asset_path = "main.png"
    aux.asset_path = None
    main.occlusion = OCCLUSION_FRONT
    aux.occlusion = OCCLUSION_BEHIND
    main.motion_mode = MOTION_MODE_CIRCULAR
    main.orbit_radius = 60.0
    main.orbit_speed_deg_per_sec = 90.0
    main.orbit_plane_tilt_deg = 45.0
    main.orbit_aux_slot_id = aux.slot_id
    normalize_layer_stack_positions(state)
    ctx = BindingContext(canvas_width=512, canvas_height=512, motion_time_s=3.0)
    resolved = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)
    overrides, hidden = compute_orbit_render_plan(state, 3.0)
    pair = resolve_stack_layer_draw(state, aux, resolved, overrides, hidden)
    assert pair is not None
    draw_layer, _rect = pair
    assert draw_layer.slot_id == main.slot_id
    assert resolve_stack_layer_draw(state, main, resolved, overrides, hidden) is None


def test_format_layer_row_summary_requisition() -> None:
    state = BasicLayersState()
    main = state.layers[0]
    aux = state.layers[1]
    main.asset_path = "main.png"
    main.motion_mode = MOTION_MODE_CIRCULAR
    main.orbit_radius = 40.0
    main.orbit_speed_deg_per_sec = 30.0
    main.orbit_aux_slot_id = aux.slot_id
    summary = format_layer_row_summary(aux, state)
    assert "征用" in summary
    assert orbit_aux_owner(state, aux.slot_id) == main.slot_id


def test_orbit_depth_flips_over_half_turn() -> None:
    layer = BasicLayerSlot(
        slot_id=0,
        motion_mode=MOTION_MODE_CIRCULAR,
        orbit_radius=60.0,
        orbit_speed_deg_per_sec=90.0,
        orbit_plane_tilt_deg=45.0)
    near = compute_orbit_state(layer, 0.25).in_front
    far = compute_orbit_state(layer, 2.5).in_front
    assert near != far


def test_visible_layer_list_order() -> None:
    state = BasicLayersState()
    visible = visible_layer_slot_ids_top_to_bottom(state)
    assert len(visible) == DEFAULT_LAYER_COUNT


def test_selection_contiguous_in_ui_list() -> None:
    state = BasicLayersState()
    visible = visible_layer_slot_ids_top_to_bottom(state)
    assert selection_contiguous_in_ui_list(state, {visible[0], visible[1]})
    assert not selection_contiguous_in_ui_list(state, {visible[0], visible[2]})


def test_move_layers_z_order_block_preserves_relative_order() -> None:
    state = BasicLayersState()
    visible = visible_layer_slot_ids_top_to_bottom(state)
    block = {visible[-1], visible[-2]}
    z_before = {sid: state.get_slot(sid).z_order for sid in block}
    assert move_layers_z_order_block(state, block, 1)
    z_after = {sid: state.get_slot(sid).z_order for sid in block}
    assert z_after[visible[-2]] > z_after[visible[-1]]
    assert z_after != z_before


def test_remove_layers_batch() -> None:
    state = BasicLayersState()
    extra = state.add_layer()
    targets = {state.layers[0].slot_id, extra.slot_id}
    assert remove_layers_batch(state, targets) == 2
    assert len(state.layers) == DEFAULT_LAYER_COUNT - 1


def test_orbit_center_follows_binding() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "prop.png"
    layer.motion_mode = MOTION_MODE_CIRCULAR
    layer.orbit_radius = 40.0
    layer.orbit_speed_deg_per_sec = 60.0
    layer.orbit_plane_tilt_deg = 45.0
    ctx = BindingContext(canvas_width=512, canvas_height=512, motion_time_s=0.0)
    unbound = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    unbound_cx = unbound.draw_x + unbound.draw_width / 2.0
    layer.binding_parent = BINDING_CHARACTER_BODY
    bound = resolve_layer_rects(state, _asset_loader, 512, 512, ctx)[0]
    bound_cx = bound.draw_x + bound.draw_width / 2.0
    assert abs(bound_cx - unbound_cx) > 1.0


def test_orbit_edit_geometry_is_static() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "prop.png"
    layer.motion_mode = MOTION_MODE_CIRCULAR
    layer.orbit_radius = 60.0
    layer.orbit_speed_deg_per_sec = 90.0
    layer.orbit_plane_tilt_deg = 45.0
    ctx = BindingContext(canvas_width=512, canvas_height=512, motion_time_s=0.0)
    animated = resolve_layer_rects(state, _asset_loader, 512, 512, ctx, include_motion=True)[0]
    static = resolve_layer_rects(state, _asset_loader, 512, 512, ctx, include_motion=False)[0]
    assert abs(static.draw_x - animated.draw_x) > 0.5 or abs(
        static.draw_width - animated.draw_width) > 0.5


def test_apply_orbit_offsets_resolved_rect() -> None:
    state = BasicLayersState()
    layer = state.layers[0]
    layer.asset_path = "tail.png"
    layer.motion_mode = MOTION_MODE_CIRCULAR
    layer.orbit_radius = 40.0
    layer.orbit_speed_deg_per_sec = 60.0
    static_ctx = BindingContext(canvas_width=512, canvas_height=512, motion_time_s=None)
    anim_ctx = BindingContext(canvas_width=512, canvas_height=512, motion_time_s=0.0)
    still = resolve_layer_rects(state, _asset_loader, 512, 512, static_ctx)[0]
    orbiting = resolve_layer_rects(state, _asset_loader, 512, 512, anim_ctx)[0]
    assert abs(orbiting.draw_x - still.draw_x) > 0.5 or abs(orbiting.draw_width - still.draw_width) > 0.5


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


def test_orbit_follow_opposite_phase_for_count_two() -> None:
    state = BasicLayersState()
    host = state.layers[1]
    host.motion_mode = MOTION_MODE_CIRCULAR
    host.orbit_radius = 100.0
    host.orbit_speed_deg_per_sec = 60.0
    host.asset_path = "host.png"
    sat = state.layers[2]
    sat.asset_path = "sat.png"
    _enable_orbit_follow(sat, host)
    sat.orbit_satellite_count = 2
    sat.orbit_satellite_index = 1
    host_st = compute_orbit_motion_state(host, state, 0.0)
    sat_st = compute_orbit_motion_state(sat, state, 0.0)
    assert abs(host_st.offset_x + sat_st.offset_x) < 1.0
    assert abs(host_st.offset_y + sat_st.offset_y) < 1.0


def test_orbit_follow_uses_own_aux_stack() -> None:
    state = BasicLayersState()
    host = state.layers[1]
    host.motion_mode = MOTION_MODE_CIRCULAR
    host.orbit_radius = 80.0
    host.asset_path = "host.png"
    host_aux = state.layers[3]
    host_aux.asset_path = "host_aux.png"
    host.orbit_aux_slot_id = host_aux.slot_id
    sat = state.layers[2]
    _enable_orbit_follow(sat, host)
    sat.orbit_satellite_count = 2
    sat.orbit_satellite_index = 1
    sat.asset_path = "sat.png"
    sat_aux = state.layers[4]
    sat_aux.asset_path = "sat_aux.png"
    sat.orbit_aux_slot_id = sat_aux.slot_id
    apply_orbit_requisition_visibility(state)
    overrides, _hidden = compute_orbit_render_plan(state, 0.75)
    assert any(p.source_slot_id == host.slot_id for p in overrides.values())
    assert any(p.source_slot_id == sat.slot_id for p in overrides.values())


def test_hotkey_targets_single_layer_only() -> None:
    state = BasicLayersState()
    host = state.layers[1]
    host.motion_mode = MOTION_MODE_CIRCULAR
    sat = state.layers[2]
    _enable_orbit_follow(sat, host)
    assert layer_hotkey_action_target_slot_ids(state, host.slot_id) == [host.slot_id]
    assert apply_layer_hotkey_action(state, host.slot_id, "toggle_visible")
    assert not host.visible
    assert sat.visible


def test_orbit_follow_draw_uses_own_scale_rect() -> None:
    state = BasicLayersState()
    host = state.layers[1]
    host.motion_mode = MOTION_MODE_CIRCULAR
    host.asset_path = "host.png"
    host.orbit_radius = 80.0
    sat = state.layers[2]
    _enable_orbit_follow(sat, host)
    sat.orbit_satellite_count = 2
    sat.orbit_satellite_index = 1
    sat.asset_path = "sat.png"
    pre = {
        host.slot_id: LayerGeometryResolver._rect_from_center(
            host.slot_id, 400.0, 300.0, 100.0, 100.0),
        sat.slot_id: LayerGeometryResolver._rect_from_center(
            sat.slot_id, 400.0, 300.0, 40.0, 40.0),
    }
    ctx = BindingContext(canvas_width=800, canvas_height=600, motion_time_s=0.0)
    out = apply_orbit_to_resolved(state, dict(pre), ctx, 800, 600)
    drawn = out[sat.slot_id]
    assert abs(drawn.draw_width - 40.0) < 0.01
    assert abs(drawn.draw_height - 40.0) < 0.01


def test_legacy_orbit_satellite_mode_migrates_to_circular() -> None:
    state = BasicLayersState()
    sat = state.layers[2]
    sat.motion_mode = MOTION_MODE_ORBIT_SATELLITE
    sat.orbit_host_slot_id = state.layers[1].slot_id
    from layer_runtime import LayerHotkeyBinding
    sat.hotkey_bindings = [LayerHotkeyBinding(key_code=70)]
    sanitize_layer_references(state)
    assert sat.motion_mode == MOTION_MODE_CIRCULAR
    assert sat.hotkey_bindings


def test_orbit_follow_host_capacity_limit() -> None:
    state = BasicLayersState()
    while len(state.layers) < 8:
        from layer_runtime import default_layer_slot
        state.layers.append(default_layer_slot(len(state.layers)))
    host = state.layers[1]
    host.motion_mode = MOTION_MODE_CIRCULAR
    for idx, slot_id in enumerate((2, 3, 4, 5, 6, 7)):
        sat = state.layers[slot_id]
        sat.motion_mode = MOTION_MODE_ORBIT_SATELLITE
        sat.orbit_host_slot_id = host.slot_id
        sat.orbit_satellite_index = idx + 1
        sat.orbit_satellite_count = 7
    sanitize_layer_references(state)
    members = orbit_satellite_member_slot_ids(state, host.slot_id)
    assert len(members) == MAX_ORBIT_SATELLITES_PER_HOST
    assert not orbit_host_has_satellite_capacity(state, host.slot_id, 99)


def test_orbit_follow_scale_uses_own_near_far() -> None:
    state = BasicLayersState()
    host = state.layers[1]
    host.motion_mode = MOTION_MODE_CIRCULAR
    host.orbit_radius = 100.0
    host.orbit_near_scale = 2.0
    host.orbit_far_scale = 0.5
    sat = state.layers[2]
    sat.asset_path = "sat.png"
    sat.orbit_near_scale = 1.0
    sat.orbit_far_scale = 1.0
    _enable_orbit_follow(sat, host)
    host_st = compute_orbit_motion_state(host, state, 0.5)
    sat_st = compute_orbit_motion_state(sat, state, 0.5)
    assert host_st.scale != 1.0
    assert abs(sat_st.scale - 1.0) < 0.01


def test_orbit_follow_resync_interval_constant() -> None:
    assert ORBIT_HOST_SYNC_INTERVAL_S >= 60.0


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
    test_swing_ease_ends_starts_at_zero()
    test_swing_ease_ends_peak_velocity()
    test_swing_constant_triangle_bounds()
    test_swing_constant_velocity_segment()
    test_swing_zero_amplitude()
    test_swing_motion_active_flag()
    test_swing_serialization_round_trip()
    test_layer_mode_basic_five_migrates()
    test_add_layer_unique_slot_id()
    test_remove_layer_clears_references()
    test_sanitize_layer_references_on_load()
    test_layer_binding_accepts_dynamic_slot_ids()
    test_visible_layer_list_order()
    test_selection_contiguous_in_ui_list()
    test_move_layers_z_order_block_preserves_relative_order()
    test_remove_layers_batch()
    test_orbit_requires_asset_for_active_motion()
    test_requisitioned_aux_never_draws_native_asset()
    test_orbit_stack_draws_owner_on_each_side()
    test_orbit_path_follows_sync_and_reverse_rotation()
    test_orbit_aux_cannot_target_orbit_motion_layer()
    test_orbit_aux_cleared_when_target_switches_to_orbit()
    test_orbit_render_plan_with_aux_hides_one_slot()
    test_orbit_depth_flips_over_half_turn()
    test_apply_orbit_offsets_resolved_rect()
    test_orbit_follow_edit_geometry_uses_host_track()
    test_orbit_frame_plan_cached_per_binding_context()
    test_orbit_follow_opposite_phase_for_count_two()
    test_orbit_follow_clears_host_aux_and_stays_visible()
    test_orbit_follow_uses_own_aux_stack()
    test_hotkey_targets_single_layer_only()
    test_orbit_follow_draw_uses_own_scale_rect()
    test_legacy_orbit_satellite_mode_migrates_to_circular()
    test_orbit_follow_host_capacity_limit()
    test_orbit_follow_scale_uses_own_near_far()
    test_orbit_follow_resync_interval_constant()
    print("smoke_layer_runtime_ok")


if __name__ == "__main__":
    main()
