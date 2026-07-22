"""Micro-benchmark for f-068 apply_wobble hot path (no wx).

Targets (512², 2 islands, no pins): mean ≤ ~3–4 ms; cache hit ≈ 0 ms class.
"""
from __future__ import annotations

import time

import numpy

from region_wobble import (
    IDLE_MODE_STILL_FROZEN,
    RegionWobbleState,
    apply_wobble,
)


def _make_two_island_state(
        h: int = 512,
        w: int = 512,
        *,
        with_pins: bool = False,
        pose_hooks: bool = False) -> tuple[numpy.ndarray, RegionWobbleState]:
    rgba = numpy.zeros((h, w, 4), dtype=numpy.uint8)
    rgba[:, :, 3] = 255
    rgba[80:160, 80:160] = (200, 40, 40, 255)
    rgba[320:420, 300:400] = (40, 40, 200, 255)
    st = RegionWobbleState(
        enabled=True,
        idle_mode=IDLE_MODE_STILL_FROZEN,
        strength=1.2,
        speed=1.0,
        pose_hooks_islands=pose_hooks)
    st.ensure_mask_shape(h, w)
    st.mask[80:160, 80:160] = 1.0
    st.mask[320:420, 300:400] = 1.0
    st.active_part().mark_mask_dirty()
    st.axes = [
        (80.0, 120.0, 160.0, 120.0),
        (300.0, 370.0, 400.0, 370.0),
    ]
    if with_pins:
        st.pins = [(100.0, 120.0), (340.0, 370.0)]
    for isl in st.active_part().islands:
        isl.spring_x = 8.0
        isl.spring_vx = 0.0
        isl.strength = 1.2
        isl.speed = 1.0
    return rgba, st


def _bench_ms(fn, repeats: int = 20, warmup: int = 3) -> float:
    for _ in range(warmup):
        fn()
    t0 = time.perf_counter()
    for _ in range(repeats):
        fn()
    return (time.perf_counter() - t0) * 1000.0 / float(repeats)


def main() -> None:
    cases = [
        ("2isl_no_pin", False, False),
        ("2isl_pins", True, False),
        ("2isl_pose_hooks", False, True),
    ]
    print("bench_region_wobble (512x512)")
    for name, pins, hooks in cases:
        rgba, st = _make_two_island_state(with_pins=pins, pose_hooks=hooks)
        t = 1.0

        def once(rgba=rgba, st=st):
            nonlocal t
            t += 0.016
            # Bust cache each call so we measure warp cost.
            st._last_wobble_key = None
            apply_wobble(
                rgba, st,
                head_yaw=0.05 if hooks else 0.0,
                head_pitch=0.0,
                now_s=t)

        ms = _bench_ms(once, repeats=15, warmup=2)
        print(f"  {name}: {ms:.2f} ms/call")

    rgba, st = _make_two_island_state()
    apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=2.0)

    def cache_hit():
        apply_wobble(rgba, st, head_yaw=0.0, head_pitch=0.0, now_s=2.001)

    hit_ms = _bench_ms(cache_hit, repeats=50, warmup=5)
    print(f"  cache_hit: {hit_ms:.3f} ms/call")
    if hit_ms > 0.5:
        raise SystemExit(f"cache hit too slow: {hit_ms:.3f} ms")
    print("bench_region_wobble: ok")


if __name__ == "__main__":
    main()
