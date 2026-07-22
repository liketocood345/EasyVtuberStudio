"""Smoke tests for f-068 region wobble (no wx)."""
from __future__ import annotations

import math

import numpy

from region_wobble import (
    IDLE_MODE_STILL_FROZEN,
    IDLE_MODE_STILL_WOBBLE,
    RegionWobbleState,
    apply_wobble,
    paint_brush,
)


def test_bypass_when_disabled():
    rgba = numpy.zeros((64, 64, 4), dtype=numpy.uint8)
    rgba[20:40, 20:40] = (200, 100, 50, 255)
    st = RegionWobbleState(enabled=False)
    paint_brush(st, 30, 30, radius=10, strength=1.0)
    st.ensure_mask_shape(64, 64)
    out = apply_wobble(rgba, st, head_yaw=0.1, head_pitch=0.0)
    assert out is rgba


def test_paint_and_warp_changes_pixels():
    rgba = numpy.zeros((64, 64, 4), dtype=numpy.uint8)
    rgba[:, :, 3] = 255
    rgba[10:20, 40:50] = (255, 0, 0, 255)
    st = RegionWobbleState(enabled=True, idle_mode=IDLE_MODE_STILL_FROZEN, strength=2.0, speed=1.0)
    st.debug_enabled = True
    st.ensure_mask_shape(64, 64)
    paint_brush(st, 45, 15, radius=8, strength=1.0)
    # Ray root at left of patch, tip toward right — tip swings more.
    st.set_axis(38.0, 15.0, 52.0, 15.0)
    st.spring_x = 18.0
    st.spring_vx = 0.0
    assert st.has_active_mask()
    out = apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=0.1)
    assert out.shape == rgba.shape
    assert out.dtype == numpy.uint8
    assert st.last_debug.triggered
    assert st.last_debug.has_axis
    assert st.last_debug.spring_mag > 5.0
    assert st.last_debug.moved_gt_0_5 > 0


def test_hinge_not_uniform_translation():
    """Tip along the ray should move more than near the root."""
    rgba = numpy.zeros((80, 80, 4), dtype=numpy.uint8)
    rgba[:, :, 3] = 255
    rgba[20:60, 50:70] = (0, 180, 255, 255)
    st = RegionWobbleState(enabled=True, idle_mode=IDLE_MODE_STILL_WOBBLE, strength=2.0, speed=1.0)
    st.debug_enabled = True
    st.ensure_mask_shape(80, 80)
    st.mask[20:60, 50:70] = 1.0
    # Vertical ray: root at top of strip, tip at bottom.
    st.set_axis(60.0, 20.0, 60.0, 60.0)
    apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=0.3)
    apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=0.9)
    snap = st.last_debug
    assert snap.triggered
    assert snap.max_pixel_shift > snap.mean_pixel_shift
    st.spring_x = 12.0
    st.spring_vx = 0.0
    st.idle_mode = IDLE_MODE_STILL_FROZEN
    out = apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=1.1)
    assert out is not rgba
    tip_diff = int(numpy.count_nonzero(out[52:60, 55:70] != rgba[52:60, 55:70]))
    root_diff = int(numpy.count_nonzero(out[20:28, 55:70] != rgba[20:28, 55:70]))
    assert tip_diff > root_diff


def test_ray_root_weight_near_zero():
    from region_wobble import warp_hinge_rgba
    rgba = numpy.full((64, 64, 4), 200, dtype=numpy.uint8)
    rgba[:, :, 3] = 255
    mask = numpy.zeros((64, 64), dtype=numpy.float32)
    mask[10:50, 10:50] = 1.0
    axis = (12.0, 30.0, 48.0, 30.0)  # horizontal ray root→tip
    _warped, blend = warp_hinge_rgba(
        rgba, mask, pins=[], axis=axis, angle_deg=15.0)
    assert float(blend[30, 13]) < 0.12  # near root
    assert float(blend[30, 46]) > 0.7   # near tip
    assert float(blend[30, 5]) < 1e-3   # behind root


def test_pins_reduce_motion():
    rgba = numpy.zeros((64, 64, 4), dtype=numpy.uint8)
    rgba[:, :, 3] = 255
    rgba[20:44, 20:44] = (200, 40, 40, 255)
    st = RegionWobbleState(enabled=True, idle_mode=IDLE_MODE_STILL_FROZEN, strength=2.0, speed=1.0)
    st.debug_enabled = True
    st.ensure_mask_shape(64, 64)
    st.mask[20:44, 20:44] = 1.0
    st.set_axis(20.0, 32.0, 44.0, 32.0)
    st.spring_x = 16.0
    st.spring_vx = 0.0
    apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=0.4)
    free_max = float(st.last_debug.max_pixel_shift)
    st.add_pin(32.0, 32.0)
    st.add_pin(28.0, 28.0)
    st.spring_x = 16.0
    st.spring_vx = 0.0
    apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=0.5)
    pinned_max = float(st.last_debug.max_pixel_shift)
    assert st.last_debug.pin_count == 2
    assert pinned_max < free_max


def test_persist_pins_axis():
    st = RegionWobbleState(enabled=True, strength=0.8)
    st.add_pin(10.0, 12.0)
    st.set_axis(1.0, 2.0, 40.0, 8.0)
    data = st.to_persist_dict()
    st2 = RegionWobbleState()
    st2.apply_persist_dict(data)
    assert st2.enabled
    assert len(st2.pins) == 1
    assert st2.axis is not None
    assert abs(st2.axis[2] - 40.0) < 1e-6


def test_still_frozen_rests():
    rgba = numpy.full((32, 32, 4), 128, dtype=numpy.uint8)
    st = RegionWobbleState(
        enabled=True, idle_mode=IDLE_MODE_STILL_FROZEN, strength=1.0)
    st.ensure_mask_shape(32, 32)
    paint_brush(st, 16, 16, radius=6, strength=1.0)
    st.set_axis(8.0, 16.0, 24.0, 16.0)
    st.spring_x = 5.0
    st.spring_vx = 0.0
    apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=1.0)
    apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=2.0)
    assert abs(st.spring_x) < 5.0


def test_debug_snapshot_counts_moved_pixels():
    rgba = numpy.zeros((48, 48, 4), dtype=numpy.uint8)
    rgba[:, :, 3] = 255
    rgba[8:20, 8:20] = (10, 200, 10, 255)
    st = RegionWobbleState(
        enabled=True, idle_mode=IDLE_MODE_STILL_WOBBLE, strength=1.5, speed=1.0)
    st.debug_enabled = True
    st.ensure_mask_shape(48, 48)
    paint_brush(st, 14, 14, radius=10, strength=1.0)
    st.set_axis(5.0, 14.0, 25.0, 14.0)
    apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=0.2, target_tag="smoke")
    apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=0.8, target_tag="smoke")
    snap = st.last_debug
    assert snap.triggered or snap.skip_reason
    assert snap.mask_pixels > 0
    assert snap.frame_h == 48 and snap.frame_w == 48


def test_guides_and_preview_warp_show_pin_freeze():
    rgba = numpy.full((64, 64, 4), 180, dtype=numpy.uint8)
    rgba[:, :, 3] = 255
    st = RegionWobbleState(enabled=True, strength=1.0)
    st.ensure_mask_shape(64, 64)
    st.mask[10:50, 20:50] = 1.0
    assert st.set_axis(20.0, 10.0, 20.0, 50.0)
    st.add_pin(22.0, 30.0)
    from region_wobble import overlay_guides_rgba, warp_hinge_rgba
    guides = overlay_guides_rgba(rgba, st.pins, st.axis, show_pin_influence=True)
    assert guides.shape == rgba.shape
    assert numpy.any(guides[:, :, :3] != rgba[:, :, :3])
    ang = 12.0
    warped, blend = warp_hinge_rgba(
        rgba, st.mask, pins=st.pins, axis=st.axis, angle_deg=ang)
    assert warped.shape == rgba.shape
    assert float(blend[30, 22]) < 0.15  # near pin ≈ frozen
    assert float(blend[12, 20]) < float(blend[45, 20])  # root < tip along ray


def test_mask_overlay_lifts_transparent_alpha():
    from region_wobble import overlay_mask_preview_rgba, composite_on_checkerboard
    rgba = numpy.zeros((32, 32, 4), dtype=numpy.uint8)
    # Fully transparent except a small opaque blob.
    rgba[8:12, 8:12] = (40, 40, 40, 255)
    mask = numpy.zeros((32, 32), dtype=numpy.float32)
    mask[4:20, 4:20] = 1.0  # includes transparent pixels
    tinted = overlay_mask_preview_rgba(rgba, mask)
    assert int(tinted[10, 10, 3]) > 100  # lifted in transparent+mask zone
    board = composite_on_checkerboard(tinted)
    assert int(board[10, 10, 3]) == 255
    # Pink tint should differ from empty checker cell outside the mask.
    assert int(numpy.sum(numpy.abs(
        board[10, 10, :3].astype(numpy.int16) - board[0, 0, :3].astype(numpy.int16)
    ))) > 20


def test_multi_region_scopes_pins_and_axes():
    from region_wobble import pins_for_mask, axes_for_mask, apply_wobble
    st = RegionWobbleState(enabled=True, strength=2.0, idle_mode=IDLE_MODE_STILL_FROZEN)
    st.ensure_mask_shape(64, 64)
    st.mask[10:30, 10:30] = 1.0
    st.add_region()
    st.ensure_mask_shape(64, 64)
    st.mask[40:55, 40:55] = 1.0
    st.set_axis(10.0, 20.0, 30.0, 20.0)
    st.set_axis(40.0, 45.0, 55.0, 45.0)
    st.add_pin(15.0, 15.0)
    st.add_pin(45.0, 45.0)
    st.add_pin(2.0, 2.0)
    assert pins_for_mask(st.pins, st.regions[0].mask) == [(15.0, 15.0)]
    assert pins_for_mask(st.pins, st.regions[1].mask) == [(45.0, 45.0)]
    assert len(axes_for_mask(st.axes, st.regions[0].mask)) == 1
    assert len(axes_for_mask(st.axes, st.regions[1].mask)) == 1
    rgba = numpy.full((64, 64, 4), 120, dtype=numpy.uint8)
    st.debug_enabled = True
    st.regions[0].ensure_island_bank()
    st.regions[1].ensure_island_bank()
    st.regions[0].islands[0].spring_x = 10.0
    st.regions[1].islands[0].spring_x = 10.0
    out = apply_wobble(rgba, st, now_s=0.2)
    assert out.shape == rgba.shape
    assert st.last_debug.triggered


def test_disjoint_mask_islands_get_separate_axes():
    from region_wobble import (
        MAX_ACTIVE_ISLANDS,
        iter_mask_components,
        apply_wobble,
        pick_axis_for_island,
        overlay_island_labels_rgba,
    )
    mask = numpy.zeros((80, 80), dtype=numpy.float32)
    mask[10:25, 10:25] = 1.0
    mask[50:70, 50:70] = 1.0
    comps = iter_mask_components(mask)
    assert len(comps) == 2
    a0 = pick_axis_for_island([], comps[0])
    a1 = pick_axis_for_island([], comps[1])
    assert a0 is not None and a1 is not None
    # Roots should lie near different islands (not the same point).
    assert math.hypot(a0[0] - a1[0], a0[1] - a1[1]) > 15.0
    # Cap: four blobs → only top 3 by area.
    mask2 = numpy.zeros((100, 100), dtype=numpy.float32)
    mask2[5:15, 5:15] = 1.0
    mask2[5:25, 40:60] = 1.0
    mask2[50:80, 10:40] = 1.0
    mask2[70:85, 70:85] = 1.0
    assert len(iter_mask_components(mask2)) == MAX_ACTIVE_ISLANDS
    st = RegionWobbleState(enabled=True, strength=2.0, idle_mode=IDLE_MODE_STILL_FROZEN)
    st.ensure_mask_shape(80, 80)
    st.mask[:, :] = mask
    st.active_part().mark_mask_dirty()
    st.debug_enabled = True
    st.active_part().islands[0].spring_x = 14.0
    st.active_part().islands[0].spring_vx = 0.0
    st.active_part().islands[1].spring_x = 14.0
    st.active_part().islands[1].spring_vx = 0.0
    # Per-island params differ.
    st.active_part().islands[0].strength = 2.0
    st.active_part().islands[0].speed = 1.0
    st.active_part().islands[1].strength = 1.5
    st.active_part().islands[1].speed = 2.0
    rgba = numpy.zeros((80, 80, 4), dtype=numpy.uint8)
    rgba[:, :, 3] = 255
    rgba[10:25, 10:25] = (200, 40, 40, 255)
    rgba[50:70, 50:70] = (40, 40, 200, 255)
    out = apply_wobble(rgba, st, now_s=0.15)
    assert st.last_debug.triggered
    d0 = int(numpy.count_nonzero(out[10:25, 10:25] != rgba[10:25, 10:25]))
    d1 = int(numpy.count_nonzero(out[50:70, 50:70] != rgba[50:70, 50:70]))
    assert d0 > 0 and d1 > 0
    labeled = overlay_island_labels_rgba(rgba, comps, active_index=0)
    assert labeled.shape == rgba.shape
    assert numpy.any(labeled[:, :, :3] != rgba[:, :, :3])
    # Component cache reuse.
    c1 = st.active_part().get_components()
    c2 = st.active_part().get_components()
    assert c1 is c2
    data = st.to_persist_dict()
    assert "region_wobble_islands_by_region" in data
    st3 = RegionWobbleState()
    st3.apply_persist_dict(data)
    assert abs(st3.regions[0].islands[1].speed - 2.0) < 1e-6


def test_pose_hooks_islands_option():
    from region_wobble import (
        pose_island_offset_px,
        offset_island,
        iter_mask_components,
        apply_wobble,
    )
    import region_wobble as rw
    dx, dy = pose_island_offset_px(1.0, 0.0)
    assert dx < -10.0 and abs(dy) < 1e-6
    mask = numpy.zeros((64, 64), dtype=numpy.float32)
    mask[20:40, 10:25] = 1.0
    comps = iter_mask_components(mask)
    assert len(comps) == 1
    shifted = offset_island(comps[0], 8.0, 0.0, full_h=64, full_w=64)
    assert shifted.x0 == comps[0].x0 + 8
    st = RegionWobbleState(enabled=True, strength=1.0, idle_mode=IDLE_MODE_STILL_FROZEN)
    st.pose_hooks_islands = False
    st.ensure_mask_shape(64, 64)
    st.mask[20:40, 10:25] = 1.0
    st.active_part().mark_mask_dirty()
    st.set_axis(12.0, 30.0, 24.0, 30.0)
    st.active_part().islands[0].spring_x = 0.0
    rgba = numpy.full((64, 64, 4), 100, dtype=numpy.uint8)
    # With hooks off, sudden yaw should not yank spring via pose omega.
    apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=1.0)
    apply_wobble(rgba, st, head_yaw=0.8, head_pitch=0.0, now_s=1.02)
    assert abs(st.active_part().islands[0].spring_x) < 1.0
    data = st.to_persist_dict()
    assert data.get("region_wobble_pose_hooks_islands") is False

    # Geometry follow must not call offset_island when hooks are off.
    calls: list = []
    _orig = rw.offset_island

    def _wrap(island, dx, dy, **kw):
        calls.append((float(dx), float(dy)))
        return _orig(island, dx, dy, **kw)

    rw.offset_island = _wrap
    try:
        st_off = RegionWobbleState(
            enabled=True, idle_mode=IDLE_MODE_STILL_WOBBLE, strength=1.0)
        st_off.pose_hooks_islands = False
        st_off.ensure_mask_shape(64, 64)
        st_off.mask[20:40, 10:25] = 1.0
        st_off.active_part().mark_mask_dirty()
        st_off.set_axis(12.0, 30.0, 24.0, 30.0)
        apply_wobble(rgba, st_off, head_yaw=1.0, head_pitch=0.0, now_s=2.0)
        assert calls == []
        st_on = RegionWobbleState(
            enabled=True, idle_mode=IDLE_MODE_STILL_WOBBLE, strength=1.0)
        st_on.pose_hooks_islands = True
        st_on.ensure_mask_shape(64, 64)
        st_on.mask[20:40, 10:25] = 1.0
        st_on.active_part().mark_mask_dirty()
        st_on.set_axis(12.0, 30.0, 24.0, 30.0)
        apply_wobble(rgba, st_on, head_yaw=1.0, head_pitch=0.0, now_s=3.0)
        assert calls and abs(calls[0][0] + 36.0) < 1e-6
    finally:
        rw.offset_island = _orig


def test_island_phase_stagger():
    from region_wobble import island_idle_phase_rad
    assert abs(island_idle_phase_rad(0, 1)) < 1e-9
    assert abs(island_idle_phase_rad(0, 2)) < 1e-9
    assert abs(island_idle_phase_rad(1, 2) - math.pi) < 1e-9
    assert abs(island_idle_phase_rad(0, 3)) < 1e-9
    assert abs(island_idle_phase_rad(1, 3) - (2.0 * math.pi / 3.0)) < 1e-9
    assert abs(island_idle_phase_rad(2, 3) - (4.0 * math.pi / 3.0)) < 1e-9
    # Two islands opposite idle contribution at same clock time.
    st = RegionWobbleState(
        enabled=True, idle_mode=IDLE_MODE_STILL_WOBBLE, strength=1.0, speed=1.0)
    st.island_phase_stagger = True
    st.pose_hooks_islands = False
    st.ensure_mask_shape(80, 80)
    st.mask[10:25, 10:25] = 1.0
    st.mask[50:70, 50:70] = 1.0
    st.active_part().mark_mask_dirty()
    st.axes = [(10.0, 18.0, 25.0, 18.0), (50.0, 60.0, 70.0, 60.0)]
    for isl in st.active_part().islands:
        isl.spring_x = 0.0
        isl.spring_vx = 0.0
        isl.strength = 1.0
        isl.speed = 1.0
    rgba = numpy.zeros((80, 80, 4), dtype=numpy.uint8)
    rgba[:, :, 3] = 255
    apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=0.5)
    # Idle is folded into returned angle; compare preview phases instead.
    from region_wobble import preview_angle_deg
    p0 = preview_angle_deg(st, now_s=1.0, island_index=0, island_count=2)
    p1 = preview_angle_deg(st, now_s=1.0, island_index=1, island_count=2)
    assert p0 * p1 < 0.0  # opposite signs when phase differs by π
    data = st.to_persist_dict()
    assert data.get("region_wobble_island_phase_stagger") is True


def test_wobble_result_cache_hit():
    """Same quantized pose/angles → second apply_wobble returns cached array."""
    rgba = numpy.zeros((64, 64, 4), dtype=numpy.uint8)
    rgba[:, :, 3] = 255
    rgba[20:40, 30:50] = (180, 60, 60, 255)
    st = RegionWobbleState(enabled=True, idle_mode=IDLE_MODE_STILL_FROZEN, strength=2.0)
    st.pose_hooks_islands = False
    st.ensure_mask_shape(64, 64)
    st.mask[20:40, 30:50] = 1.0
    st.active_part().mark_mask_dirty()
    st.set_axis(28.0, 30.0, 48.0, 30.0)
    st.active_part().islands[0].spring_x = 10.0
    st.active_part().islands[0].spring_vx = 0.0
    out1 = apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=1.0)
    assert out1 is not rgba
    key1 = st._last_wobble_key
    # Same now_s → dt floor only; quantized angle key stays identical.
    out2 = apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=1.0)
    assert out2 is out1
    assert st._last_wobble_key == key1
    st.invalidate_wobble_cache()
    out3 = apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=1.0)
    assert out3 is not out1


def test_pin_free_map_sparse_no_pins():
    from region_wobble import _pin_free_map
    free = _pin_free_map(40, 40, [])
    assert free.shape == (40, 40)
    assert float(free.min()) == 1.0
    free2 = _pin_free_map(40, 40, [(20.0, 20.0)], radius=8.0)
    assert float(free2[20, 20]) == 0.0
    assert float(free2[0, 0]) == 1.0


if __name__ == "__main__":
    test_bypass_when_disabled()
    test_paint_and_warp_changes_pixels()
    test_hinge_not_uniform_translation()
    test_ray_root_weight_near_zero()
    test_pins_reduce_motion()
    test_persist_pins_axis()
    test_still_frozen_rests()
    test_debug_snapshot_counts_moved_pixels()
    test_guides_and_preview_warp_show_pin_freeze()
    test_mask_overlay_lifts_transparent_alpha()
    test_multi_region_scopes_pins_and_axes()
    test_disjoint_mask_islands_get_separate_axes()
    test_pose_hooks_islands_option()
    test_island_phase_stagger()
    test_wobble_result_cache_hit()
    test_pin_free_map_sparse_no_pins()
    print("smoke_region_wobble: ok")
