"""Smoke test for averaged output FPS + present signature / half-res present helpers."""
from __future__ import annotations

import time
from typing import List, Optional

import cv2
import numpy as np

from region_wobble import IDLE_MODE_STILL_WOBBLE, RegionWobbleState, paint_brush
from output_enhancement.pipeline import EnhancementPipeline


def averaged_output_fps_from_present_times(
        present_times: List[float],
        *,
        avg_frame_count: int = 5,
        max_gap_sec: float = 2.0) -> Optional[float]:
    if not present_times or len(present_times) < 2:
        return None
    window = present_times[-max(2, int(avg_frame_count)) :]
    span = window[-1] - window[0]
    intervals = len(window) - 1
    if intervals <= 0 or span <= 1e-6:
        return None
    if span / intervals >= max_gap_sec:
        return None
    return intervals / span


def _idle_buckets_over_window(
        *,
        present_hz: float,
        duration_sec: float = 0.35,
        sample_hz: float = 200.0) -> set:
    st = RegionWobbleState()
    st.enabled = True
    st.idle_mode = IDLE_MODE_STILL_WOBBLE
    st.ensure_mask_shape(32, 32)
    paint_brush(st, 16.0, 16.0, radius=6.0, strength=1.0, erase=False)
    assert st.has_active_mask()
    buckets = set()
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < duration_sec:
        token = st.compose_signature_token(present_hz=present_hz)
        buckets.add(token[-3])  # idle_bucket
        time.sleep(1.0 / sample_hz)
    return buckets


def _simulate_latest_wins_queue() -> None:
    async_active = False
    pending: Optional[int] = None
    delivered: List[int] = []

    def finish(frame_id: int) -> None:
        nonlocal async_active, pending
        async_active = False
        delivered.append(frame_id)
        if pending is None:
            return
        nxt = pending
        pending = None
        async_active = True
        finish(nxt)

    def push(frame_id: int) -> None:
        nonlocal async_active, pending
        if async_active:
            pending = frame_id
            return
        async_active = True
        finish(frame_id)

    push(1)
    assert delivered == [1]
    async_active = True
    push(2)
    push(3)
    assert pending == 3
    finish(10)
    assert delivered == [1, 10, 3]
    assert pending is None
    assert async_active is False


def _half_res_upsample_dims() -> None:
    out_w, out_h = 768, 768
    scale = 0.5
    compose_w = max(1, int(round(out_w * scale)))
    compose_h = max(1, int(round(out_h * scale)))
    assert (compose_w, compose_h) == (384, 384)
    src = np.zeros((compose_h, compose_w, 4), dtype=np.uint8)
    src[:, :, 3] = 255
    src[10:20, 10:20, 0] = 200
    up = cv2.resize(src, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
    assert up.shape == (out_h, out_w, 4)


def _assert_char_scale_follows_compose_ratio() -> None:
    """Half-res compose must multiply display_scale by sx so upsample keeps size."""
    from output_enhancement.antialiasing import compose_character_rgba_from_keyframe

    key_w = key_h = 64
    keyframe = np.zeros((key_h, key_w, 4), dtype=np.uint8)
    keyframe[:, :, 0] = 200
    keyframe[:, :, 3] = 255
    display_scale = 1.0
    full_w = full_h = 768
    half_w = half_h = 384

    full = compose_character_rgba_from_keyframe(
        keyframe,
        full_w,
        full_h,
        anchor_x=full_w / 2.0,
        anchor_y=float(full_h),
        scale=max(0.1, display_scale),
        rotation_deg=0.0,
        antialias_factor=1.0)
    sx = float(half_w) / float(full_w)
    half = compose_character_rgba_from_keyframe(
        keyframe,
        half_w,
        half_h,
        anchor_x=half_w / 2.0,
        anchor_y=float(half_h),
        scale=max(0.1, display_scale * sx),
        rotation_deg=0.0,
        antialias_factor=1.0)
    up = cv2.resize(half, (full_w, full_h), interpolation=cv2.INTER_LINEAR)

    def occupied_bbox(rgba: np.ndarray) -> tuple[int, int, int, int]:
        alpha = rgba[:, :, 3] > 0
        ys, xs = np.where(alpha)
        assert ys.size > 0 and xs.size > 0
        return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())

    fx0, fy0, fx1, fy1 = occupied_bbox(full)
    ux0, uy0, ux1, uy1 = occupied_bbox(up)
    full_w_span = fx1 - fx0 + 1
    up_w_span = ux1 - ux0 + 1
    # After correct scale*sx, upsampled half-res char width matches full-res (±2px).
    assert abs(full_w_span - up_w_span) <= 2, (full_w_span, up_w_span)
    full_h_span = fy1 - fy0 + 1
    up_h_span = uy1 - uy0 + 1
    assert abs(full_h_span - up_h_span) <= 2, (full_h_span, up_h_span)


def _assert_present_cap_constants() -> None:
    from pathlib import Path
    text = Path(__file__).with_name(
        "character_model_mediapipe_puppeteer_load_preview.py").read_text(encoding="utf-8")
    assert "DISPLAY_PRESENT_CAP_HZ = 30" in text
    assert "DISPLAY_PRESENT_CAP_HZ = 14" not in text
    assert "PRESENT_COMPOSE_SCALE = 1.0" in text
    assert "PRESENT_COMPOSE_SCALE = 0.5" not in text
    assert "DISPLAY_PRESENT_INTERVAL_MS = max(1, int(round(1000.0 / DISPLAY_PRESENT_CAP_HZ)))" in text
    assert "scale=max(0.1, float(self.display_scale) * sx)" in text
    # Layer-blend path must also early-out on compose signature (not only fast_affine).
    assert "compose_signature == self._last_compose_signature" in text
    assert "def _layer_blend_compose_token(self)" in text
    # Affine reproject helper may exist, but must NOT be on the present hot path.
    assert "reproject_rgba_by_display_affine(" not in text
    assert "quantize_affine(" not in text
    assert "CharacterWarpCache" in text
    assert "LayerWarpResultCache" in text
    assert "warp_cache=getattr(self, \"_layer_warp_result_cache\", None)" in text
    assert "EVS_PRESENT_STAGE_LOG" in text
    assert 'apply_edge = self.get_character_edge_mode() != "none"' in text
    assert "return float(self._get_antialias_factor())" in text


def _assert_layer_warp_cache() -> None:
    from present_compose_cache import LayerWarpResultCache

    cache = LayerWarpResultCache(max_entries=8)
    key_a = LayerWarpResultCache.make_key(
        slot_id=0,
        asset_path="a.png",
        draw_x=10.0,
        draw_y=20.0,
        draw_width=32.0,
        draw_height=32.0,
        rotation_deg=0.0,
        swing_deg=0.0,
        canvas_width=64,
        canvas_height=64,
        wobble_token=("off",))
    key_b = LayerWarpResultCache.make_key(
        slot_id=0,
        asset_path="a.png",
        draw_x=11.0,
        draw_y=20.0,
        draw_width=32.0,
        draw_height=32.0,
        rotation_deg=0.0,
        swing_deg=0.0,
        canvas_width=64,
        canvas_height=64,
        wobble_token=("off",))
    assert key_a != key_b
    rgba = np.zeros((64, 64, 4), dtype=np.uint8)
    rgba[:, :, 3] = 255
    assert cache.get(key_a) is None
    assert cache.misses == 1
    cache.put(key_a, rgba)
    hit = cache.get(key_a)
    assert hit is not None and hit is rgba
    assert cache.hits == 1
    assert cache.get(key_b) is None


def _assert_affine_reproject_helper_still_exists() -> None:
    """Helper kept for future experiments; not used on the present hot path."""
    from present_compose_cache import quantize_affine, reproject_rgba_by_display_affine

    w = h = 64
    src = np.zeros((h, w, 4), dtype=np.uint8)
    src[40:50, 20:30, 0] = 200
    src[40:50, 20:30, 3] = 255
    old_aff = quantize_affine(0.0, 0.0, 1.0, 0.0)
    new_aff = quantize_affine(8.0, 0.0, 1.0, 0.0)
    out = reproject_rgba_by_display_affine(
        src, w, h, old_affine=old_aff, new_affine=new_aff)
    assert out.shape == (h, w, 4)
    shifted = int(out[40:50, 28:38, 3].sum())
    assert shifted > 0


def _assert_layer_token_stability_helpers() -> None:
    """Settled authored layer params produce a stable token shape; edits change it."""

    class _Transform:
        def __init__(self) -> None:
            self.offset_x = 1.0
            self.offset_y = 2.0
            self.scale = 1.0
            self.rotation_deg = 0.0

    class _Layer:
        def __init__(self) -> None:
            self.slot_id = 0
            self.visible = True
            self.asset_path = "x.png"
            self.transform = _Transform()

    def token_for(layer: _Layer) -> tuple:
        tr = layer.transform
        return (
            int(layer.slot_id),
            1 if layer.visible else 0,
            str(layer.asset_path or ""),
            round(float(tr.offset_x), 2),
            round(float(tr.offset_y), 2),
            round(float(tr.scale), 4),
            round(float(tr.rotation_deg), 2),
        )

    layer = _Layer()
    a = token_for(layer)
    b = token_for(layer)
    assert a == b
    layer.transform.offset_x = 3.0
    c = token_for(layer)
    assert c != a


def main() -> None:
    assert averaged_output_fps_from_present_times([]) is None
    assert averaged_output_fps_from_present_times([0.0]) is None
    assert averaged_output_fps_from_present_times([0.0, 0.5]) == 2.0
    step = 1.0 / 14.0
    times = [step * i for i in range(5)]
    assert abs(averaged_output_fps_from_present_times(times) - 14.0) < 0.05

    buckets_30 = _idle_buckets_over_window(present_hz=30.0)
    assert len(buckets_30) >= 3, buckets_30
    buckets_14 = _idle_buckets_over_window(present_hz=14.0)
    assert len(buckets_14) >= 3, buckets_14

    _simulate_latest_wins_queue()
    _half_res_upsample_dims()
    _assert_char_scale_follows_compose_ratio()
    _assert_present_cap_constants()
    _assert_layer_warp_cache()
    _assert_affine_reproject_helper_still_exists()
    _assert_layer_token_stability_helpers()

    pipe = EnhancementPipeline(repo_root=None)
    assert not pipe.is_active()
    rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    out = pipe.apply(rgba, is_new_real_frame=True)
    assert out is rgba or np.array_equal(out, rgba)

    print("smoke_output_fps: OK")


if __name__ == "__main__":
    main()
