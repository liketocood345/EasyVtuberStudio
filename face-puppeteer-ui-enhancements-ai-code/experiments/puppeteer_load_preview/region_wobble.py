# ══ 设计手册嵌入 ══
# 权威：e:\record\easyvtuberstudio条目设计手册.md · f-068 区域弹簧晃动
# 【机制要点】多涂选区域；同槽内不相交连通域自动拆岛（最多 MAX_ACTIVE_ISLANDS=3）；
# 每岛独立强度/速度弹簧；区内钉+过区射线；ROI remap；连通域缓存至掩膜 dirty；
# still_frozen / still_wobble；作用于 THA keyframe 与图层素材 RGBA（摆放/swing 前）。
# 【关联】compose_output_stack_rgba · RegionWobbleLayerPanel（涂选/中轴分模式）
# 【调试】RegionWobbleDebugSnapshot · state.debug_enabled（脚手架代码保留，编辑窗不展示）
"""Region spring wobble: multi-region ray-hinged swing (pins/axes scoped per region).

See design handbook f-068. Hot path must not flush mask PNGs to disk.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy

IDLE_MODE_STILL_FROZEN = "still_frozen"
IDLE_MODE_STILL_WOBBLE = "still_wobble"
IDLE_MODES = (IDLE_MODE_STILL_FROZEN, IDLE_MODE_STILL_WOBBLE)

DEFAULT_STRENGTH = 0.35
DEFAULT_SPEED = 1.0
DEFAULT_SPRING_K = 48.0
DEFAULT_SPRING_C = 12.0
DEFAULT_HEAD_GAIN_ANGLE = 90.0  # deg / (rad/s) impulse scale into angle spring
DEFAULT_IDLE_ANGLE_DEG = 8.0
IDLE_SINE_OMEGA = 2.2  # idle: sin(_time_s * speed * IDLE_SINE_OMEGA + phase)
DEFAULT_ANGLE_MAX = 22.0
DEFAULT_PIN_RADIUS = 28.0
RAY_ROOT_EASE = 1.35  # >1 → stronger near-root attenuation
COMPONENT_BIN_THRESH = 0.12  # soft-mask islands split above this
MIN_COMPONENT_PIXELS = 12
MAX_ACTIVE_ISLANDS = 3  # largest islands by pixel count
ROI_PAD_MIN = 12
# When pose_hooks_islands: translate island geometry with head pose (px per pose unit).
POSE_FOLLOW_PX_YAW = 36.0
POSE_FOLLOW_PX_PITCH = 18.0
OMEGA_EPS = 0.02
DT_MAX = 0.05
W_EPS = 1e-3
ANGLE_EPS = 1e-4
AXIS_MIN_LEN = 4.0

PinPoint = Tuple[float, float]
AxisLine = Tuple[float, float, float, float]  # root_x, root_y, tip_x, tip_y (ray)


def clamp_strength(value: float) -> float:
    """Lower bound 0; no upper cap."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(v):
        return 0.0
    return float(max(0.0, v))


def clamp_speed(value: float) -> float:
    """Lower bound 0; no upper cap."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(v):
        return 0.0
    return float(max(0.0, v))


def pin_inside_mask(
        pin: PinPoint,
        mask: numpy.ndarray,
        *,
        thresh: float = 0.05) -> bool:
    """True if pin lands on painted weight (inside a涂选区域)."""
    if mask is None:
        return False
    h, w = int(mask.shape[0]), int(mask.shape[1])
    x, y = float(pin[0]), float(pin[1])
    ix, iy = int(round(x)), int(round(y))
    if ix < 0 or iy < 0 or ix >= w or iy >= h:
        return False
    return float(mask[iy, ix]) > float(thresh)


def axis_passes_through_mask(
        axis: AxisLine,
        mask: numpy.ndarray,
        *,
        thresh: float = 0.05,
        samples: int = 48) -> bool:
    """True if the drawn ray segment crosses any painted weight."""
    if mask is None or axis is None:
        return False
    h, w = int(mask.shape[0]), int(mask.shape[1])
    x0, y0, x1, y1 = axis
    n = max(8, int(samples))
    for i in range(n + 1):
        t = i / float(n)
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        ix, iy = int(round(x)), int(round(y))
        if 0 <= ix < w and 0 <= iy < h and float(mask[iy, ix]) > float(thresh):
            return True
    return False


def pins_for_mask(
        pins: Sequence[PinPoint],
        mask: numpy.ndarray) -> List[PinPoint]:
    return [p for p in pins if pin_inside_mask(p, mask)]


def axes_for_mask(
        axes: Sequence[AxisLine],
        mask: numpy.ndarray) -> List[AxisLine]:
    return [a for a in axes if axis_passes_through_mask(a, mask)]


def pick_axis_for_mask(
        axes: Sequence[AxisLine],
        mask: numpy.ndarray) -> Optional[AxisLine]:
    """Prefer the axis with the longest chord across the mask; else auto."""
    cands = axes_for_mask(axes, mask)
    if not cands:
        return _auto_axis_from_mask(mask)
    best = None
    best_score = -1.0
    for a in cands:
        x0, y0, x1, y1 = a
        score = math.hypot(x1 - x0, y1 - y0)
        # Boost if both ends sit near mass.
        if pin_inside_mask((x0, y0), mask, thresh=0.02):
            score += 8.0
        if pin_inside_mask((x1, y1), mask, thresh=0.02):
            score += 4.0
        if score > best_score:
            best_score = score
            best = a
    return best


@dataclass
class MaskIsland:
    """One connected paint island (soft ROI + placement in full image)."""

    mask_roi: numpy.ndarray  # (bh, bw) float32 soft weights
    y0: int
    x0: int
    full_h: int
    full_w: int
    cx: float
    cy: float
    pixel_count: int

    @property
    def y1(self) -> int:
        return int(self.y0 + self.mask_roi.shape[0])

    @property
    def x1(self) -> int:
        return int(self.x0 + self.mask_roi.shape[1])

    def as_full_mask(self) -> numpy.ndarray:
        out = numpy.zeros((self.full_h, self.full_w), dtype=numpy.float32)
        out[self.y0:self.y1, self.x0:self.x1] = self.mask_roi
        return out


@dataclass
class IslandParams:
    """Per-island amplitude (strength) / speed + angle spring state."""

    strength: float = DEFAULT_STRENGTH
    speed: float = DEFAULT_SPEED
    spring_x: float = 0.0
    spring_vx: float = 0.0
    _last_head_yaw: Optional[float] = field(default=None, repr=False)
    _last_head_pitch: Optional[float] = field(default=None, repr=False)
    _last_tick_s: Optional[float] = field(default=None, repr=False)
    _time_s: float = field(default=0.0, repr=False)

    def reset_spring(self) -> None:
        self.spring_x = 0.0
        self.spring_vx = 0.0
        self._last_head_yaw = None
        self._last_head_pitch = None
        self._last_tick_s = None
        self._time_s = 0.0

    def to_dict(self) -> dict:
        return {
            "strength": clamp_strength(self.strength),
            "speed": clamp_speed(self.speed),
        }

    def apply_dict(self, data: Optional[dict]) -> None:
        if not isinstance(data, dict):
            return
        if "strength" in data:
            try:
                self.strength = clamp_strength(float(data.get("strength")))
            except (TypeError, ValueError):
                pass
        if "speed" in data:
            try:
                self.speed = clamp_speed(float(data.get("speed")))
            except (TypeError, ValueError):
                pass


def _empty_island_bank(
        strength: float = DEFAULT_STRENGTH,
        speed: float = DEFAULT_SPEED) -> List[IslandParams]:
    return [
        IslandParams(strength=clamp_strength(strength), speed=clamp_speed(speed))
        for _ in range(MAX_ACTIVE_ISLANDS)
    ]


def iter_mask_components(
        mask: numpy.ndarray,
        *,
        bin_thresh: float = COMPONENT_BIN_THRESH,
        min_pixels: int = MIN_COMPONENT_PIXELS,
        max_islands: int = MAX_ACTIVE_ISLANDS) -> List[MaskIsland]:
    """Split a soft mask into disjoint islands (8-connected), largest first.

    Soft falloff bridges below ``bin_thresh`` do not merge islands. At most
    ``max_islands`` components are returned (by pixel count).
    """
    if mask is None or not numpy.any(mask > W_EPS):
        return []
    soft = mask.astype(numpy.float32, copy=False)
    h, w = int(soft.shape[0]), int(soft.shape[1])
    binary = (soft > float(bin_thresh)).astype(numpy.uint8)
    if not numpy.any(binary):
        binary = (soft > W_EPS).astype(numpy.uint8)
    count, labels = cv2.connectedComponents(binary, connectivity=8)
    scored: List[Tuple[int, int, int, int, int, int, float, float]] = []
    # (px, y0, y1, x0, x1, lab, cx, cy)
    for lab in range(1, int(count)):
        ys, xs = numpy.where(labels == lab)
        px = int(ys.size)
        if px < int(min_pixels):
            continue
        y0 = int(ys.min())
        y1 = int(ys.max()) + 1
        x0 = int(xs.min())
        x1 = int(xs.max()) + 1
        cx = float(xs.mean())
        cy = float(ys.mean())
        scored.append((px, y0, y1, x0, x1, int(lab), cx, cy))
    if not scored and numpy.any(soft > W_EPS):
        ys, xs = numpy.where(soft > W_EPS)
        scored.append((
            int(ys.size),
            int(ys.min()), int(ys.max()) + 1,
            int(xs.min()), int(xs.max()) + 1,
            0, float(xs.mean()), float(ys.mean())))
    scored.sort(key=lambda t: t[0], reverse=True)
    limit = max(1, int(max_islands))
    out: List[MaskIsland] = []
    for px, y0, y1, x0, x1, lab, cx, cy in scored[:limit]:
        if lab == 0:
            roi = soft[y0:y1, x0:x1].copy()
        else:
            sel = labels[y0:y1, x0:x1] == lab
            roi = numpy.where(sel, soft[y0:y1, x0:x1], 0.0).astype(numpy.float32)
        if not numpy.any(roi > W_EPS):
            continue
        out.append(MaskIsland(
            mask_roi=roi,
            y0=y0,
            x0=x0,
            full_h=h,
            full_w=w,
            cx=cx,
            cy=cy,
            pixel_count=int(px)))
    return out


def normalize_idle_mode(value: object) -> str:
    text = str(value or "").strip().lower()
    if text == IDLE_MODE_STILL_FROZEN:
        return IDLE_MODE_STILL_FROZEN
    return IDLE_MODE_STILL_WOBBLE


@dataclass
class RegionWobbleDebugSnapshot:
    """Last apply diagnostics — for UI/log, not gameplay."""

    triggered: bool = False
    skip_reason: str = ""
    target_tag: str = ""
    frame_h: int = 0
    frame_w: int = 0
    spring_dx: float = 0.0  # angle deg (named dx for UI compatibility)
    spring_dy: float = 0.0
    spring_mag: float = 0.0  # |angle| deg
    mask_pixels: int = 0
    moved_gt_0_5: int = 0
    moved_gt_1: int = 0
    moved_gt_2: int = 0
    max_pixel_shift: float = 0.0
    mean_pixel_shift: float = 0.0
    pin_count: int = 0
    has_axis: bool = False
    timestamp_s: float = 0.0

    def format_lines(self) -> str:
        status = "TRIGGERED" if self.triggered else f"SKIP ({self.skip_reason or '—'})"
        axis = "axis=yes" if self.has_axis else "axis=NO"
        return (
            f"[{status}] {self.target_tag or '—'}  {axis}  pins={self.pin_count}\n"
            f"size={self.frame_w}×{self.frame_h}  "
            f"angle={self.spring_dx:+.3f}°  |θ|={self.spring_mag:.3f}°\n"
            f"mask_px={self.mask_pixels}  "
            f"moved>0.5={self.moved_gt_0_5}  >1={self.moved_gt_1}  >2={self.moved_gt_2}\n"
            f"max_shift={self.max_pixel_shift:.3f}px  "
            f"mean_shift={self.mean_pixel_shift:.4f}px"
        )


@dataclass
class WobbleRegionPart:
    """One painted wobble slot (soft mask) with up to MAX_ACTIVE_ISLANDS island params."""

    mask: Optional[numpy.ndarray] = None
    islands: List[IslandParams] = field(default_factory=_empty_island_bank)
    # Legacy single-spring mirrors island 0 for older callers/tests.
    spring_x: float = 0.0
    spring_vx: float = 0.0
    _last_head_yaw: Optional[float] = field(default=None, repr=False)
    _last_head_pitch: Optional[float] = field(default=None, repr=False)
    _last_tick_s: Optional[float] = field(default=None, repr=False)
    _time_s: float = field(default=0.0, repr=False)
    _components: Optional[List[MaskIsland]] = field(default=None, repr=False)
    _components_dirty: bool = field(default=True, repr=False)

    def ensure_island_bank(self) -> None:
        while len(self.islands) < MAX_ACTIVE_ISLANDS:
            self.islands.append(IslandParams())
        if len(self.islands) > MAX_ACTIVE_ISLANDS:
            self.islands = self.islands[:MAX_ACTIVE_ISLANDS]

    def mark_mask_dirty(self) -> None:
        self._components_dirty = True
        self._components = None

    def get_components(self) -> List[MaskIsland]:
        if not self._components_dirty and self._components is not None:
            return self._components
        comps = iter_mask_components(self.mask) if self.mask is not None else []
        self._components = comps
        self._components_dirty = False
        return comps

    def reset_spring(self) -> None:
        self.spring_x = 0.0
        self.spring_vx = 0.0
        self._last_head_yaw = None
        self._last_head_pitch = None
        self._last_tick_s = None
        self._time_s = 0.0
        self.ensure_island_bank()
        for isl in self.islands:
            isl.reset_spring()


@dataclass
class RegionWobbleState:
    """Per-target (character or one layer) multi-region wobble runtime."""

    enabled: bool = False
    idle_mode: str = IDLE_MODE_STILL_WOBBLE
    strength: float = DEFAULT_STRENGTH
    speed: float = DEFAULT_SPEED
    # When True: head pose drives island spring + translates island geometry so
    # painted islands track THA part motion (ears/hair). When False: islands stay
    # fixed in paint space and only idle/manual spring applies.
    pose_hooks_islands: bool = True
    # When True: idle sine phase is staggered across islands in the same region
    # (2 → opposite π; 3 → even 0 / 2π/3 / 4π/3).
    island_phase_stagger: bool = False
    regions: List[WobbleRegionPart] = field(
        default_factory=lambda: [WobbleRegionPart()])
    active_region: int = 0
    active_island: int = 0
    pins: List[PinPoint] = field(default_factory=list)
    axes: List[AxisLine] = field(default_factory=list)
    debug_enabled: bool = False
    last_debug: RegionWobbleDebugSnapshot = field(
        default_factory=RegionWobbleDebugSnapshot, repr=False)
    _mask_generation: int = field(default=0, repr=False)
    _last_wobble_key: Optional[tuple] = field(default=None, repr=False)
    _last_wobble_rgba: Optional[numpy.ndarray] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.strength = clamp_strength(self.strength)
        self.speed = clamp_speed(self.speed)
        for reg in self.regions:
            reg.ensure_island_bank()
            for isl in reg.islands:
                isl.strength = clamp_strength(self.strength)
                isl.speed = clamp_speed(self.speed)

    def invalidate_wobble_cache(self) -> None:
        self._mask_generation = int(self._mask_generation) + 1
        self._last_wobble_key = None
        self._last_wobble_rgba = None

    def compose_signature_token(self, *, present_hz: float = 30.0) -> tuple:
        """Quantized token for present/compose early-out (cheap, no warp).

        ``present_hz`` aligns idle/time buckets with the display present cap
        (default 30) so still_wobble does not pin Out near ~12 Hz.
        """
        if not self.enabled or not self.has_active_mask():
            return ("off",)
        hz = max(1.0, float(present_hz))
        bucket_mod = max(1, int(round(hz * 10.0)))
        angles = []
        phases = []
        for reg in self.regions:
            reg.ensure_island_bank()
            for isl in reg.islands[:MAX_ACTIVE_ISLANDS]:
                angles.append(round(float(isl.spring_x), 1))
                phases.append(int(float(isl._time_s) * hz) % bucket_mod)
        idle_bucket = 0
        if normalize_idle_mode(self.idle_mode) == IDLE_MODE_STILL_WOBBLE:
            idle_bucket = int(time.perf_counter() * hz) % bucket_mod
        return (
            int(self._mask_generation),
            bool(self.pose_hooks_islands),
            bool(self.island_phase_stagger),
            normalize_idle_mode(self.idle_mode),
            tuple(angles),
            tuple(phases),
            idle_bucket,
            int(self.active_region),
            len(self.regions),
        )
    def _clamp_active(self) -> int:
        if not self.regions:
            self.regions = [WobbleRegionPart()]
        self.active_region = int(max(0, min(self.active_region, len(self.regions) - 1)))
        return self.active_region

    def _clamp_active_island(self) -> int:
        self.active_island = int(max(0, min(self.active_island, MAX_ACTIVE_ISLANDS - 1)))
        return self.active_island

    def active_part(self) -> WobbleRegionPart:
        return self.regions[self._clamp_active()]

    def active_island_params(self) -> IslandParams:
        part = self.active_part()
        part.ensure_island_bank()
        return part.islands[self._clamp_active_island()]

    # --- backward-compatible mask / axis / spring views (active region) ---
    @property
    def mask(self) -> Optional[numpy.ndarray]:
        return self.active_part().mask

    @mask.setter
    def mask(self, value: Optional[numpy.ndarray]) -> None:
        part = self.active_part()
        part.mask = value
        part.mark_mask_dirty()
        self.invalidate_wobble_cache()

    @property
    def axis(self) -> Optional[AxisLine]:
        return self.axes[0] if self.axes else None

    @axis.setter
    def axis(self, value: Optional[AxisLine]) -> None:
        if value is None:
            self.axes = []
        else:
            self.axes = [value]

    @property
    def spring_x(self) -> float:
        part = self.active_part()
        part.ensure_island_bank()
        return float(part.islands[0].spring_x)

    @spring_x.setter
    def spring_x(self, value: float) -> None:
        part = self.active_part()
        part.ensure_island_bank()
        part.islands[0].spring_x = float(value)
        part.spring_x = float(value)

    @property
    def spring_vx(self) -> float:
        part = self.active_part()
        part.ensure_island_bank()
        return float(part.islands[0].spring_vx)

    @spring_vx.setter
    def spring_vx(self, value: float) -> None:
        part = self.active_part()
        part.ensure_island_bank()
        part.islands[0].spring_vx = float(value)
        part.spring_vx = float(value)

    @property
    def spring_y(self) -> float:
        return 0.0

    @spring_y.setter
    def spring_y(self, value: float) -> None:
        return None

    @property
    def spring_vy(self) -> float:
        return 0.0

    @spring_vy.setter
    def spring_vy(self, value: float) -> None:
        return None

    def to_persist_dict(self) -> dict:
        islands_by_region = []
        for reg in self.regions:
            reg.ensure_island_bank()
            islands_by_region.append([isl.to_dict() for isl in reg.islands])
        # Mirror active island into legacy strength/speed for older readers.
        active_isl = self.active_island_params()
        data = {
            "region_wobble_enabled": bool(self.enabled),
            "region_wobble_idle_mode": normalize_idle_mode(self.idle_mode),
            "region_wobble_strength": clamp_strength(active_isl.strength),
            "region_wobble_speed": clamp_speed(active_isl.speed),
            "region_wobble_pose_hooks_islands": bool(self.pose_hooks_islands),
            "region_wobble_island_phase_stagger": bool(self.island_phase_stagger),
            "region_wobble_pins": [
                [float(x), float(y)] for x, y in self.pins],
            "region_wobble_axes": [
                [float(v) for v in a] for a in self.axes],
            "region_wobble_active_region": int(self._clamp_active()),
            "region_wobble_region_count": int(len(self.regions)),
            "region_wobble_active_island": int(self._clamp_active_island()),
            "region_wobble_islands_by_region": islands_by_region,
        }
        # Legacy single-axis field.
        data["region_wobble_axis"] = (
            [float(v) for v in self.axes[0]] if self.axes else None)
        return data

    def apply_persist_dict(self, data: Optional[dict]) -> None:
        if not data:
            return
        if "region_wobble_enabled" in data:
            self.enabled = bool(data.get("region_wobble_enabled"))
        if "region_wobble_idle_mode" in data:
            self.idle_mode = normalize_idle_mode(data.get("region_wobble_idle_mode"))
        if "region_wobble_strength" in data:
            self.strength = clamp_strength(float(data.get("region_wobble_strength")))
        if "region_wobble_speed" in data:
            self.speed = clamp_speed(float(data.get("region_wobble_speed")))
        if "region_wobble_pose_hooks_islands" in data:
            self.pose_hooks_islands = bool(data.get("region_wobble_pose_hooks_islands"))
        if "region_wobble_island_phase_stagger" in data:
            self.island_phase_stagger = bool(data.get("region_wobble_island_phase_stagger"))
        if "region_wobble_pins" in data:
            self.pins = _parse_pins(data.get("region_wobble_pins"))
        axes_raw = data.get("region_wobble_axes")
        if isinstance(axes_raw, (list, tuple)) and axes_raw:
            parsed = []
            for item in axes_raw:
                a = _parse_axis(item)
                if a is not None:
                    parsed.append(a)
            self.axes = parsed
        elif "region_wobble_axis" in data:
            a = _parse_axis(data.get("region_wobble_axis"))
            self.axes = [a] if a is not None else []
        if "region_wobble_region_count" in data:
            n = max(1, int(data.get("region_wobble_region_count") or 1))
            while len(self.regions) < n:
                self.regions.append(WobbleRegionPart())
            self.regions = self.regions[:n]
        if "region_wobble_active_region" in data:
            self.active_region = int(data.get("region_wobble_active_region") or 0)
        if "region_wobble_active_island" in data:
            self.active_island = int(data.get("region_wobble_active_island") or 0)
        islands_raw = data.get("region_wobble_islands_by_region")
        if isinstance(islands_raw, (list, tuple)):
            for i, reg in enumerate(self.regions):
                reg.ensure_island_bank()
                if i >= len(islands_raw):
                    break
                bank = islands_raw[i]
                if not isinstance(bank, (list, tuple)):
                    continue
                for j in range(min(MAX_ACTIVE_ISLANDS, len(bank))):
                    reg.islands[j].apply_dict(bank[j] if isinstance(bank[j], dict) else None)
        else:
            # Legacy: seed all islands from global strength/speed.
            for reg in self.regions:
                reg.ensure_island_bank()
                for isl in reg.islands:
                    isl.strength = clamp_strength(self.strength)
                    isl.speed = clamp_speed(self.speed)
        self._clamp_active()
        self._clamp_active_island()
        # Keep state.strength/speed mirrored to active island.
        isl = self.active_island_params()
        self.strength = isl.strength
        self.speed = isl.speed

    def reset_spring(self) -> None:
        for part in self.regions:
            part.reset_spring()

    def add_region(self) -> int:
        part = WobbleRegionPart()
        part.ensure_island_bank()
        for isl in part.islands:
            isl.strength = clamp_strength(self.strength)
            isl.speed = clamp_speed(self.speed)
        self.regions.append(part)
        self.active_region = len(self.regions) - 1
        return self.active_region

    def remove_active_region(self) -> None:
        if len(self.regions) <= 1:
            self.clear_mask()
            self.active_part().reset_spring()
            return
        idx = self._clamp_active()
        self.regions.pop(idx)
        self.active_region = min(idx, len(self.regions) - 1)

    def ensure_mask_shape(self, height: int, width: int) -> numpy.ndarray:
        """Ensure active region mask size; scale global pins/axes once on resize."""
        h = max(1, int(height))
        w = max(1, int(width))
        part = self.active_part()
        if part.mask is None:
            part.mask = numpy.zeros((h, w), dtype=numpy.float32)
            part.mark_mask_dirty()
            self.invalidate_wobble_cache()
            return part.mask
        if part.mask.shape[0] == h and part.mask.shape[1] == w:
            return part.mask
        src_h, src_w = int(part.mask.shape[0]), int(part.mask.shape[1])
        sx = w / float(src_w)
        sy = h / float(src_h)
        # Scale every region's mask + global guides from the active's prior size.
        for reg in self.regions:
            if reg.mask is None:
                continue
            if reg.mask.shape[0] != h or reg.mask.shape[1] != w:
                reg.mask = cv2.resize(
                    reg.mask.astype(numpy.float32), (w, h),
                    interpolation=cv2.INTER_LINEAR)
                reg.mark_mask_dirty()
        self.invalidate_wobble_cache()
        if self.pins:
            self.pins = [(float(x) * sx, float(y) * sy) for x, y in self.pins]
        if self.axes:
            scaled = []
            for x0, y0, x1, y1 in self.axes:
                scaled.append((x0 * sx, y0 * sy, x1 * sx, y1 * sy))
            self.axes = scaled
        return part.mask

    def components_for_region(
            self, index: int, height: int, width: int
    ) -> List[MaskIsland]:
        """Cached islands for a region at (h,w); ephemeral if mask must resize."""
        if index < 0 or index >= len(self.regions):
            return []
        part = self.regions[index]
        m = part.mask
        if m is None or not numpy.any(m > W_EPS):
            return []
        h = max(1, int(height))
        w = max(1, int(width))
        if m.shape[0] == h and m.shape[1] == w:
            return part.get_components()
        resized = cv2.resize(
            m.astype(numpy.float32), (w, h), interpolation=cv2.INTER_LINEAR)
        return iter_mask_components(resized)

    def mask_for_shape(self, height: int, width: int) -> Optional[numpy.ndarray]:
        """Combined max-mask (any region) resized to (h,w)."""
        parts = []
        for reg in self.regions:
            if reg.mask is None or not numpy.any(reg.mask > W_EPS):
                continue
            m = reg.mask
            h = max(1, int(height))
            w = max(1, int(width))
            if m.shape[0] != h or m.shape[1] != w:
                m = cv2.resize(
                    m.astype(numpy.float32), (w, h), interpolation=cv2.INTER_LINEAR)
            parts.append(m)
        if not parts:
            return None
        out = parts[0].copy()
        for m in parts[1:]:
            numpy.maximum(out, m, out=out)
        return out

    def region_mask_for_shape(
            self, index: int, height: int, width: int
    ) -> Optional[numpy.ndarray]:
        if index < 0 or index >= len(self.regions):
            return None
        m = self.regions[index].mask
        if m is None:
            return None
        h = max(1, int(height))
        w = max(1, int(width))
        if m.shape[0] == h and m.shape[1] == w:
            return m
        return cv2.resize(
            m.astype(numpy.float32), (w, h), interpolation=cv2.INTER_LINEAR)

    def geometry_for_shape(
            self, height: int, width: int
    ) -> Tuple[List[PinPoint], List[AxisLine], Optional[Tuple[int, int]]]:
        """Scale global pins/axes using first available mask space."""
        src = None
        for reg in self.regions:
            if reg.mask is not None:
                src = reg.mask
                break
        pins = list(self.pins)
        axes = list(self.axes)
        if src is None:
            return pins, axes, None
        src_h, src_w = int(src.shape[0]), int(src.shape[1])
        h = max(1, int(height))
        w = max(1, int(width))
        if src_h == h and src_w == w:
            return pins, axes, (src_h, src_w)
        sx = w / float(src_w)
        sy = h / float(src_h)
        pins = [(float(x) * sx, float(y) * sy) for x, y in pins]
        axes = [
            (a[0] * sx, a[1] * sy, a[2] * sx, a[3] * sy) for a in axes]
        return pins, axes, (src_h, src_w)

    def has_active_mask(self) -> bool:
        for reg in self.regions:
            if reg.mask is not None and bool(numpy.any(reg.mask > W_EPS)):
                return True
        return False

    def clear_mask(self) -> None:
        part = self.active_part()
        if part.mask is not None:
            part.mask.fill(0.0)
        part.mark_mask_dirty()
        self.invalidate_wobble_cache()

    def clear_pins(self) -> None:
        """Remove pins that lie inside the active region (or all if empty)."""
        mask = self.active_part().mask
        if mask is None or not numpy.any(mask > W_EPS):
            self.pins.clear()
            return
        self.pins = [p for p in self.pins if not pin_inside_mask(p, mask)]

    def clear_axis(self) -> None:
        """Remove axes that pass through the active region (or all if empty)."""
        mask = self.active_part().mask
        if mask is None or not numpy.any(mask > W_EPS):
            self.axes = []
            return
        self.axes = [a for a in self.axes if not axis_passes_through_mask(a, mask)]

    def add_pin(self, x: float, y: float) -> None:
        self.pins.append((float(x), float(y)))

    def remove_nearest_pin(self, x: float, y: float, max_dist: float = 24.0) -> bool:
        if not self.pins:
            return False
        best_i = -1
        best_d = float(max_dist)
        for i, (px, py) in enumerate(self.pins):
            d = math.hypot(px - x, py - y)
            if d <= best_d:
                best_d = d
                best_i = i
        if best_i < 0:
            return False
        self.pins.pop(best_i)
        return True

    def set_axis(self, x0: float, y0: float, x1: float, y1: float) -> bool:
        """Add a swing ray (root→tip). Multiple axes supported for multi-region."""
        if math.hypot(x1 - x0, y1 - y0) < AXIS_MIN_LEN:
            return False
        self.axes.append((float(x0), float(y0), float(x1), float(y1)))
        return True



def _parse_pins(raw: object) -> List[PinPoint]:
    out: List[PinPoint] = []
    if not isinstance(raw, (list, tuple)):
        return out
    for item in raw:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            try:
                out.append((float(item[0]), float(item[1])))
            except (TypeError, ValueError):
                continue
    return out


def _parse_axis(raw: object) -> Optional[AxisLine]:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)) and len(raw) >= 4:
        try:
            axis = (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
        except (TypeError, ValueError):
            return None
        if math.hypot(axis[2] - axis[0], axis[3] - axis[1]) < AXIS_MIN_LEN:
            return None
        return axis
    return None


def paint_brush(
        state: RegionWobbleState,
        x: float,
        y: float,
        *,
        radius: float,
        strength: float,
        erase: bool = False) -> None:
    if state.mask is None:
        return
    h, w = state.mask.shape
    cx = int(round(x))
    cy = int(round(y))
    r = max(1.0, float(radius))
    x0 = max(0, int(math.floor(cx - r - 1)))
    x1 = min(w, int(math.ceil(cx + r + 2)))
    y0 = max(0, int(math.floor(cy - r - 1)))
    y1 = min(h, int(math.ceil(cy + r + 2)))
    if x0 >= x1 or y0 >= y1:
        return
    yy, xx = numpy.ogrid[y0:y1, x0:x1]
    dist = numpy.sqrt((xx - cx) ** 2 + (yy - cy) ** 2).astype(numpy.float32)
    falloff = numpy.clip(1.0 - dist / r, 0.0, 1.0)
    amount = falloff * float(max(0.0, min(1.0, strength)))
    patch = state.mask[y0:y1, x0:x1]
    if erase:
        patch -= amount
    else:
        patch += amount
    numpy.clip(patch, 0.0, 1.0, out=patch)
    state.active_part().mark_mask_dirty()
    state.invalidate_wobble_cache()


def save_mask_png(path: Path, mask: Optional[numpy.ndarray]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if mask is None:
        return
    u8 = numpy.clip(mask * 255.0, 0, 255).astype(numpy.uint8)
    cv2.imwrite(str(path), u8)


def load_mask_png(path: Path, height: int, width: int) -> Optional[numpy.ndarray]:
    path = Path(path)
    if not path.is_file():
        return None
    raw = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if raw is None:
        return None
    h = max(1, int(height))
    w = max(1, int(width))
    if raw.shape[0] != h or raw.shape[1] != w:
        raw = cv2.resize(raw, (w, h), interpolation=cv2.INTER_LINEAR)
    return (raw.astype(numpy.float32) / 255.0)


def overlay_mask_preview_rgba(
        rgba: numpy.ndarray,
        mask: Optional[numpy.ndarray],
        *,
        tint: Tuple[int, int, int] = (255, 105, 180),
        alpha: float = 0.55) -> numpy.ndarray:
    """Tint mask weight onto RGB and lift alpha so transparent paint stays visible."""
    if mask is None or not numpy.any(mask > W_EPS):
        return rgba
    out = numpy.array(rgba, copy=True, dtype=numpy.uint8)
    h, w = out.shape[:2]
    if mask.shape[0] != h or mask.shape[1] != w:
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
    m = numpy.clip(mask.astype(numpy.float32), 0.0, 1.0)
    wgt = (m * float(alpha))[..., None]
    tint_arr = numpy.array(tint, dtype=numpy.float32).reshape(1, 1, 3)
    rgb = out[:, :, :3].astype(numpy.float32)
    out[:, :, :3] = numpy.clip(rgb * (1.0 - wgt) + tint_arr * wgt, 0, 255).astype(numpy.uint8)
    # Transparent canvas pixels with weight must become visible in the editor.
    a = out[:, :, 3].astype(numpy.float32)
    a_lift = numpy.maximum(a, m * 200.0)
    out[:, :, 3] = numpy.clip(a_lift, 0, 255).astype(numpy.uint8)
    return out


def composite_on_checkerboard(
        rgba: numpy.ndarray,
        *,
        cell: int = 12,
        c0: Tuple[int, int, int] = (42, 44, 48),
        c1: Tuple[int, int, int] = (58, 60, 66)) -> numpy.ndarray:
    """Editor-only: flat opaque preview so transparent regions are paintable/visible."""
    h, w = int(rgba.shape[0]), int(rgba.shape[1])
    yy, xx = numpy.indices((h, w))
    parity = ((yy // cell) + (xx // cell)) & 1
    board = numpy.empty((h, w, 3), dtype=numpy.float32)
    board[parity == 0] = numpy.array(c0, dtype=numpy.float32)
    board[parity == 1] = numpy.array(c1, dtype=numpy.float32)
    src = rgba.astype(numpy.float32)
    a = (src[:, :, 3:4] / 255.0)
    rgb = src[:, :, :3] * a + board * (1.0 - a)
    out = numpy.empty((h, w, 4), dtype=numpy.uint8)
    out[:, :, :3] = numpy.clip(rgb, 0, 255).astype(numpy.uint8)
    out[:, :, 3] = 255
    return out


def overlay_guides_rgba(
        rgba: numpy.ndarray,
        pins: Sequence[PinPoint],
        axis: Optional[AxisLine] = None,
        *,
        axes: Optional[Sequence[AxisLine]] = None,
        draft_axis: Optional[AxisLine] = None,
        pin_radius: float = DEFAULT_PIN_RADIUS,
        show_pin_influence: bool = True,
        auto_axis: Optional[AxisLine] = None) -> numpy.ndarray:
    """Draw pins and swing rays (root→tip) on a preview copy. Colors are RGB."""
    out = numpy.array(rgba, copy=True, dtype=numpy.uint8)
    h, w = out.shape[:2]

    def _bgr(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
        return (int(rgb[2]), int(rgb[1]), int(rgb[0]))

    def _circle(cx: int, cy: int, r: int, rgb: Tuple[int, int, int], fill: bool) -> None:
        cv2.circle(out, (cx, cy), int(r), _bgr(rgb), -1 if fill else 2, cv2.LINE_AA)

    def _ray(a: AxisLine, rgb: Tuple[int, int, int], thickness: int) -> None:
        x0, y0, x1, y1 = a
        p0 = (int(round(x0)), int(round(y0)))
        p1 = (int(round(x1)), int(round(y1)))
        cv2.arrowedLine(
            out, p0, p1, _bgr(rgb), int(thickness), cv2.LINE_AA, tipLength=0.18)
        _circle(p0[0], p0[1], 9, rgb, True)
        _circle(p0[0], p0[1], 4, (255, 255, 255), True)

    if show_pin_influence and pins:
        free = _pin_free_map(h, w, pins, radius=pin_radius)
        freeze = (1.0 - free)[..., None]
        rgb = out[:, :, :3].astype(numpy.float32)
        tint = numpy.array((220.0, 40.0, 40.0), dtype=numpy.float32).reshape(1, 1, 3)
        out[:, :, :3] = numpy.clip(
            rgb * (1.0 - 0.55 * freeze) + tint * (0.55 * freeze), 0, 255
        ).astype(numpy.uint8)

    draw_axes: List[AxisLine] = []
    if axes:
        draw_axes.extend(list(axes))
    elif axis is not None:
        draw_axes.append(axis)
    if auto_axis is not None and not draw_axes:
        _ray(auto_axis, (180, 180, 40), 1)
    for a in draw_axes:
        _ray(a, (0, 220, 255), 3)
    if draft_axis is not None:
        _ray(draft_axis, (255, 200, 40), 2)

    r = max(8, int(round(float(pin_radius))))
    for px, py in pins:
        ix, iy = int(round(px)), int(round(py))
        if not (0 <= ix < w and 0 <= iy < h):
            continue
        _circle(ix, iy, r, (255, 60, 40), False)
        _circle(ix, iy, 8, (20, 20, 20), True)
        _circle(ix, iy, 6, (255, 90, 20), True)
        cv2.drawMarker(
            out, (ix, iy), (255, 255, 255),
            markerType=cv2.MARKER_TILTED_CROSS, markerSize=14, thickness=2)
    return out


def overlay_shift_debug_rgba(
        rgba: numpy.ndarray,
        mask: Optional[numpy.ndarray],
        angle_deg: float,
        *,
        amplify: float = 8.0) -> numpy.ndarray:
    if mask is None:
        return rgba
    out = numpy.array(rgba, copy=True, dtype=numpy.uint8)
    h, w = out.shape[:2]
    if mask.shape[0] != h or mask.shape[1] != w:
        mask = cv2.resize(
            mask.astype(numpy.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    # Approximate shift scale from angle for heat visibility.
    shift = mask.astype(numpy.float32) * abs(float(angle_deg)) * 0.35
    heat = numpy.clip(shift * float(amplify) / 4.0, 0.0, 1.0)[..., None]
    tint = numpy.array((0.0, 220.0, 255.0), dtype=numpy.float32).reshape(1, 1, 3)
    rgb = out[:, :, :3].astype(numpy.float32)
    out[:, :, :3] = numpy.clip(rgb * (1.0 - heat) + tint * heat, 0, 255).astype(numpy.uint8)
    return out


def overlay_island_labels_rgba(
        rgba: numpy.ndarray,
        islands: Sequence[MaskIsland],
        *,
        active_index: int = -1,
        alpha: float = 0.55) -> numpy.ndarray:
    """Draw semi-transparent island numbers (1..N) at each island centroid."""
    if not islands:
        return rgba
    out = numpy.array(rgba, copy=True, dtype=numpy.uint8)
    h, w = out.shape[:2]
    overlay = out.copy()
    for i, isl in enumerate(islands):
        label = str(i + 1)
        cx = int(round(isl.cx))
        cy = int(round(isl.cy))
        if not (0 <= cx < w and 0 <= cy < h):
            continue
        scale = max(0.7, min(2.2, math.sqrt(max(1, isl.pixel_count)) / 55.0))
        thickness = 2 if i == int(active_index) else 1
        color = (40, 220, 255) if i == int(active_index) else (255, 255, 255)
        # Shadow then fill for readability on busy art.
        for dx, dy, col, th in (
                (2, 2, (0, 0, 0), thickness + 1),
                (0, 0, color, thickness)):
            cv2.putText(
                overlay,
                label,
                (cx - int(10 * scale) + dx, cy + int(10 * scale) + dy),
                cv2.FONT_HERSHEY_SIMPLEX,
                float(scale),
                col,
                int(th),
                cv2.LINE_AA)
    a = float(max(0.0, min(1.0, alpha)))
    blended = (
        out.astype(numpy.float32) * (1.0 - a)
        + overlay.astype(numpy.float32) * a)
    out[:, :, :3] = numpy.clip(blended[:, :, :3], 0, 255).astype(numpy.uint8)
    out[:, :, 3] = rgba[:, :, 3]
    return out


def warp_hinge_rgba(
        rgba: numpy.ndarray,
        mask: numpy.ndarray,
        *,
        pins: Sequence[PinPoint],
        axis: AxisLine,
        angle_deg: float,
        pin_radius: float = DEFAULT_PIN_RADIUS) -> Tuple[numpy.ndarray, numpy.ndarray]:
    """Ray-hinge remap: rotate about ray root; weight→0 near root / behind root.

    ``axis`` is (root_x, root_y, tip_x, tip_y). Returns (warped_rgba, blend_weights).
    """
    h, w = int(rgba.shape[0]), int(rgba.shape[1])
    free = _pin_free_map(h, w, pins, radius=pin_radius)
    x0, y0, x1, y1 = axis
    ux, uy = float(x1 - x0), float(y1 - y0)
    ulen = math.hypot(ux, uy)
    if ulen < AXIS_MIN_LEN:
        zero = numpy.zeros((h, w), dtype=numpy.float32)
        return numpy.ascontiguousarray(rgba, dtype=numpy.uint8), zero
    ux /= ulen
    uy /= ulen
    yy, xx = numpy.meshgrid(
        numpy.arange(h, dtype=numpy.float32),
        numpy.arange(w, dtype=numpy.float32),
        indexing="ij")
    rel_x = xx - float(x0)
    rel_y = yy - float(y0)
    # Signed distance along ray; behind root → no swing.
    t = rel_x * ux + rel_y * uy
    ray_w = numpy.clip(t / float(ulen), 0.0, 1.0)
    # Ease-in so pixels near the root are almost still.
    ray_w = numpy.power(ray_w, float(RAY_ROOT_EASE)).astype(numpy.float32)
    blend = numpy.clip(
        mask.astype(numpy.float32) * free * ray_w, 0.0, 1.0)
    theta = numpy.deg2rad(float(angle_deg)) * blend
    # Pivot is always the ray root (not infinite-line projection).
    piv_x = float(x0)
    piv_y = float(y0)
    vx = xx - piv_x
    vy = yy - piv_y
    cos_t = numpy.cos(-theta).astype(numpy.float32)
    sin_t = numpy.sin(-theta).astype(numpy.float32)
    map_x = piv_x + cos_t * vx - sin_t * vy
    map_y = piv_y + sin_t * vx + cos_t * vy
    source = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
    warped = cv2.remap(
        source,
        numpy.ascontiguousarray(map_x),
        numpy.ascontiguousarray(map_y),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0))
    keep = blend <= W_EPS
    if numpy.any(keep):
        warped[keep] = source[keep]
    return numpy.ascontiguousarray(warped, dtype=numpy.uint8), blend


def _island_roi_bounds(
        island: MaskIsland,
        *,
        pin_radius: float,
        angle_deg: float) -> Tuple[int, int, int, int]:
    """Padded bbox in full-image coords for safe hinge remap."""
    bh, bw = int(island.mask_roi.shape[0]), int(island.mask_roi.shape[1])
    swing = abs(math.sin(math.radians(float(angle_deg)))) * max(bh, bw)
    pad = max(
        ROI_PAD_MIN,
        int(math.ceil(float(pin_radius))) + 4,
        int(math.ceil(swing)) + 8)
    y0 = max(0, int(island.y0) - pad)
    x0 = max(0, int(island.x0) - pad)
    y1 = min(int(island.full_h), int(island.y1) + pad)
    x1 = min(int(island.full_w), int(island.x1) + pad)
    return y0, y1, x0, x1


def island_idle_phase_rad(island_index: int, island_count: int) -> float:
    """Phase offset (rad) for idle sine when island_phase_stagger is on.

    - 1 island: 0
    - 2 islands: 0 and π (opposite)
    - 3 islands: 0, 2π/3, 4π/3 (even split of one period; 「均分」)
    """
    n = max(1, min(int(MAX_ACTIVE_ISLANDS), int(island_count)))
    i = int(island_index) % n
    if n <= 1:
        return 0.0
    if n == 2:
        return 0.0 if i == 0 else math.pi
    return (2.0 * math.pi * float(i)) / float(n)


def preview_angle_deg(
        state: RegionWobbleState,
        now_s: Optional[float] = None,
        *,
        strength: Optional[float] = None,
        speed: Optional[float] = None,
        island_index: int = 0,
        island_count: int = 1) -> float:
    """Editor preview angle — same idle formula as ``_integrate_angle_spring``.

    Does not advance spring state. Matches runtime when spring is at rest:
    ``(DEFAULT_IDLE_ANGLE_DEG * speed * sin(t * speed * IDLE_SINE_OMEGA + φ)) * strength``.
    """
    if now_s is None:
        now_s = time.perf_counter()
    str_v = clamp_strength(
        state.strength if strength is None else float(strength))
    spd_v = clamp_speed(state.speed if speed is None else float(speed))
    phase = 0.0
    if bool(getattr(state, "island_phase_stagger", False)):
        phase = island_idle_phase_rad(island_index, island_count)
    if normalize_idle_mode(state.idle_mode) != IDLE_MODE_STILL_WOBBLE:
        # Frozen: show a small fixed tip so hinge/pins stay inspectable.
        return float(DEFAULT_IDLE_ANGLE_DEG * 0.35 * str_v)
    idle = DEFAULT_IDLE_ANGLE_DEG * spd_v * math.sin(
        float(now_s) * spd_v * IDLE_SINE_OMEGA + phase)
    return float(idle * str_v)


def build_debug_snapshot(
        *,
        triggered: bool,
        skip_reason: str,
        target_tag: str,
        frame_h: int,
        frame_w: int,
        angle_deg: float,
        mask: Optional[numpy.ndarray],
        shift_map: Optional[numpy.ndarray],
        collect_pixel_stats: bool,
        pin_count: int,
        has_axis: bool,
        now_s: float) -> RegionWobbleDebugSnapshot:
    snap = RegionWobbleDebugSnapshot(
        triggered=bool(triggered),
        skip_reason=str(skip_reason or ""),
        target_tag=str(target_tag or ""),
        frame_h=int(frame_h),
        frame_w=int(frame_w),
        spring_dx=float(angle_deg),
        spring_dy=0.0,
        spring_mag=float(abs(angle_deg)),
        pin_count=int(pin_count),
        has_axis=bool(has_axis),
        timestamp_s=float(now_s))
    if mask is None:
        return snap
    active = mask > W_EPS
    snap.mask_pixels = int(numpy.count_nonzero(active))
    if not collect_pixel_stats or snap.mask_pixels == 0 or shift_map is None:
        return snap
    active_shift = shift_map[active]
    snap.max_pixel_shift = float(numpy.max(active_shift)) if active_shift.size else 0.0
    snap.mean_pixel_shift = float(numpy.mean(active_shift)) if active_shift.size else 0.0
    snap.moved_gt_0_5 = int(numpy.count_nonzero(active_shift > 0.5))
    snap.moved_gt_1 = int(numpy.count_nonzero(active_shift > 1.0))
    snap.moved_gt_2 = int(numpy.count_nonzero(active_shift > 2.0))
    return snap


def _auto_axis_from_mask(mask: numpy.ndarray) -> Optional[AxisLine]:
    """Fallback ray: root nearer image center, tip at farthest mask extreme (PCA)."""
    ys, xs = numpy.where(mask > W_EPS)
    if xs.size < 8:
        return None
    pts = numpy.column_stack(
        (xs.astype(numpy.float32), ys.astype(numpy.float32)))
    mean = pts.mean(axis=0)
    centered = pts - mean
    # 2x2 covariance principal axis.
    cov = centered.T @ centered / float(max(1, pts.shape[0] - 1))
    try:
        _eig, vecs = numpy.linalg.eigh(cov)
        direction = vecs[:, int(numpy.argmax(_eig))]
    except numpy.linalg.LinAlgError:
        direction = numpy.array([1.0, 0.0], dtype=numpy.float32)
    proj = centered @ direction
    root = pts[int(numpy.argmin(proj))]
    tip = pts[int(numpy.argmax(proj))]
    h, w = int(mask.shape[0]), int(mask.shape[1])
    cx, cy = w * 0.5, h * 0.5
    if math.hypot(root[0] - cx, root[1] - cy) > math.hypot(tip[0] - cx, tip[1] - cy):
        root, tip = tip, root
    if math.hypot(tip[0] - root[0], tip[1] - root[1]) < AXIS_MIN_LEN:
        return None
    return (float(root[0]), float(root[1]), float(tip[0]), float(tip[1]))


def _pin_free_map(
        height: int,
        width: int,
        pins: Sequence[PinPoint],
        radius: float = DEFAULT_PIN_RADIUS) -> numpy.ndarray:
    """Pin falloff map; sparse writes only inside each pin's bbox."""
    free = numpy.ones((height, width), dtype=numpy.float32)
    if not pins:
        return free
    r = max(1.0, float(radius))
    for px, py in pins:
        cx = float(px)
        cy = float(py)
        x0 = max(0, int(math.floor(cx - r)))
        x1 = min(width, int(math.ceil(cx + r)) + 1)
        y0 = max(0, int(math.floor(cy - r)))
        y1 = min(height, int(math.ceil(cy + r)) + 1)
        if x0 >= x1 or y0 >= y1:
            continue
        yy, xx = numpy.ogrid[y0:y1, x0:x1]
        dist = numpy.sqrt((xx - cx) ** 2 + (yy - cy) ** 2).astype(numpy.float32)
        free[y0:y1, x0:x1] *= numpy.clip(dist / r, 0.0, 1.0)
    return free


def warp_hinge_island(
        rgba: numpy.ndarray,
        island: MaskIsland,
        *,
        pins: Sequence[PinPoint],
        axis: AxisLine,
        angle_deg: float,
        pin_radius: float = DEFAULT_PIN_RADIUS,
        out: Optional[numpy.ndarray] = None,
        return_blend: bool = False) -> Tuple[numpy.ndarray, Optional[numpy.ndarray]]:
    """ROI hinge warp: remap ROI sampling from full frame; paste into ``out``.

    Pass a shared ``out`` buffer from ``apply_wobble`` to avoid N full-frame copies.
    ``return_blend`` only when debug stats need a full-size blend map.
    """
    h, w = int(rgba.shape[0]), int(rgba.shape[1])
    y0, y1, x0, x1 = _island_roi_bounds(
        island, pin_radius=pin_radius, angle_deg=angle_deg)
    if y0 >= y1 or x0 >= x1:
        result = out if out is not None else numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
        if return_blend:
            return result, numpy.zeros((h, w), dtype=numpy.float32)
        return result, None

    rh, rw = y1 - y0, x1 - x0
    mask_roi = numpy.zeros((rh, rw), dtype=numpy.float32)
    iy0 = int(island.y0) - y0
    ix0 = int(island.x0) - x0
    iy1 = iy0 + int(island.mask_roi.shape[0])
    ix1 = ix0 + int(island.mask_roi.shape[1])
    mask_roi[iy0:iy1, ix0:ix1] = island.mask_roi

    if pins:
        pins_roi = [(px - x0, py - y0) for px, py in pins]
        free = _pin_free_map(rh, rw, pins_roi, radius=pin_radius)
    else:
        free = 1.0

    ax0, ay0, ax1, ay1 = axis
    ux, uy = float(ax1 - ax0), float(ay1 - ay0)
    ulen = math.hypot(ux, uy)
    if ulen < AXIS_MIN_LEN:
        result = out if out is not None else numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
        if return_blend:
            return result, numpy.zeros((h, w), dtype=numpy.float32)
        return result, None
    ux /= ulen
    uy /= ulen

    yy, xx = numpy.meshgrid(
        numpy.arange(y0, y1, dtype=numpy.float32),
        numpy.arange(x0, x1, dtype=numpy.float32),
        indexing="ij")
    rel_x = xx - float(ax0)
    rel_y = yy - float(ay0)
    t = rel_x * ux + rel_y * uy
    ray_w = numpy.clip(t / float(ulen), 0.0, 1.0)
    ray_w = numpy.power(ray_w, float(RAY_ROOT_EASE)).astype(numpy.float32)
    blend = numpy.clip(mask_roi * free * ray_w, 0.0, 1.0)
    theta = numpy.deg2rad(float(angle_deg)) * blend
    piv_x = float(ax0)
    piv_y = float(ay0)
    vx = xx - piv_x
    vy = yy - piv_y
    cos_t = numpy.cos(-theta).astype(numpy.float32)
    sin_t = numpy.sin(-theta).astype(numpy.float32)
    map_x = piv_x + cos_t * vx - sin_t * vy
    map_y = piv_y + sin_t * vx + cos_t * vy

    source = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
    warped_roi = cv2.remap(
        source,
        numpy.ascontiguousarray(map_x),
        numpy.ascontiguousarray(map_y),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0))
    patch = source[y0:y1, x0:x1]
    keep = blend <= W_EPS
    if numpy.any(keep):
        warped_roi[keep] = patch[keep]

    if out is None:
        out = numpy.array(rgba, copy=True, dtype=numpy.uint8)
    out[y0:y1, x0:x1] = warped_roi
    if not return_blend:
        return numpy.ascontiguousarray(out, dtype=numpy.uint8), None
    blend_full = numpy.zeros((h, w), dtype=numpy.float32)
    blend_full[y0:y1, x0:x1] = blend
    return numpy.ascontiguousarray(out, dtype=numpy.uint8), blend_full


def pin_inside_island(
        pin: PinPoint,
        island: MaskIsland,
        *,
        thresh: float = 0.05) -> bool:
    x, y = float(pin[0]), float(pin[1])
    ix = int(round(x)) - int(island.x0)
    iy = int(round(y)) - int(island.y0)
    bh, bw = int(island.mask_roi.shape[0]), int(island.mask_roi.shape[1])
    if ix < 0 or iy < 0 or ix >= bw or iy >= bh:
        return False
    return float(island.mask_roi[iy, ix]) > float(thresh)


def axis_passes_through_island(
        axis: AxisLine,
        island: MaskIsland,
        *,
        thresh: float = 0.05,
        samples: int = 48) -> bool:
    if axis is None:
        return False
    x0, y0, x1, y1 = axis
    n = max(8, int(samples))
    bh, bw = int(island.mask_roi.shape[0]), int(island.mask_roi.shape[1])
    for i in range(n + 1):
        t = i / float(n)
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        ix = int(round(x)) - int(island.x0)
        iy = int(round(y)) - int(island.y0)
        if 0 <= ix < bw and 0 <= iy < bh and float(island.mask_roi[iy, ix]) > float(thresh):
            return True
    return False


def pins_for_island(
        pins: Sequence[PinPoint],
        island: MaskIsland) -> List[PinPoint]:
    return [p for p in pins if pin_inside_island(p, island)]


def pick_axis_for_island(
        axes: Sequence[AxisLine],
        island: MaskIsland) -> Optional[AxisLine]:
    cands = [a for a in axes if axis_passes_through_island(a, island)]
    if not cands:
        local = _auto_axis_from_mask(island.mask_roi)
        if local is None:
            return None
        lx0, ly0, lx1, ly1 = local
        return (
            lx0 + island.x0, ly0 + island.y0,
            lx1 + island.x0, ly1 + island.y0)
    best = None
    best_score = -1.0
    for a in cands:
        x0, y0, x1, y1 = a
        score = math.hypot(x1 - x0, y1 - y0)
        if pin_inside_island((x0, y0), island, thresh=0.02):
            score += 8.0
        if pin_inside_island((x1, y1), island, thresh=0.02):
            score += 4.0
        if score > best_score:
            best_score = score
            best = a
    return best


def pose_island_offset_px(
        head_yaw: float,
        head_pitch: float,
        *,
        yaw_gain: float = POSE_FOLLOW_PX_YAW,
        pitch_gain: float = POSE_FOLLOW_PX_PITCH) -> Tuple[float, float]:
    """Approximate image-space shift so painted islands track THA head morph.

    ``head_yaw`` / ``head_pitch`` are THA pose units (typically ~[-1, 1]).
    Sign: positive yaw shifts islands left on the canvas (matches common THA
    head-x morph where the near-side ear/hair moves toward image center-left).
    """
    dx = -float(head_yaw) * float(yaw_gain)
    dy = float(head_pitch) * float(pitch_gain)
    return dx, dy


def offset_island(
        island: MaskIsland,
        dx: float,
        dy: float,
        *,
        full_h: int,
        full_w: int) -> MaskIsland:
    """Translate an island ROI in image space (ephemeral; does not mutate cache)."""
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return island
    nx0 = int(round(island.x0 + dx))
    ny0 = int(round(island.y0 + dy))
    bh, bw = int(island.mask_roi.shape[0]), int(island.mask_roi.shape[1])
    # Clip placement into frame; drop if completely outside.
    src_y0 = 0
    src_x0 = 0
    dst_y0 = ny0
    dst_x0 = nx0
    if dst_x0 < 0:
        src_x0 = -dst_x0
        dst_x0 = 0
    if dst_y0 < 0:
        src_y0 = -dst_y0
        dst_y0 = 0
    dst_x1 = min(int(full_w), dst_x0 + (bw - src_x0))
    dst_y1 = min(int(full_h), dst_y0 + (bh - src_y0))
    copy_w = dst_x1 - dst_x0
    copy_h = dst_y1 - dst_y0
    if copy_w <= 0 or copy_h <= 0:
        return MaskIsland(
            mask_roi=numpy.zeros((1, 1), dtype=numpy.float32),
            y0=0, x0=0, full_h=full_h, full_w=full_w,
            cx=float(island.cx + dx), cy=float(island.cy + dy),
            pixel_count=0)
    roi = island.mask_roi[src_y0:src_y0 + copy_h, src_x0:src_x0 + copy_w].copy()
    return MaskIsland(
        mask_roi=roi,
        y0=dst_y0,
        x0=dst_x0,
        full_h=int(full_h),
        full_w=int(full_w),
        cx=float(island.cx + dx),
        cy=float(island.cy + dy),
        pixel_count=int(numpy.count_nonzero(roi > W_EPS)))


def _integrate_angle_spring(
        state: RegionWobbleState,
        island: IslandParams,
        head_yaw: float,
        head_pitch: float,
        now_s: float,
        *,
        island_index: int = 0,
        island_count: int = 1) -> float:
    """Return swing angle in degrees (positive = CCW) for one island."""
    if island._last_tick_s is None:
        dt = 1.0 / 60.0
    else:
        dt = max(1e-4, min(DT_MAX, now_s - island._last_tick_s))
    island._last_tick_s = now_s
    island._time_s += dt

    if island._last_head_yaw is None:
        omega_y = 0.0
        omega_p = 0.0
    else:
        omega_y = (head_yaw - island._last_head_yaw) / dt
        omega_p = (head_pitch - island._last_head_pitch) / dt
    island._last_head_yaw = head_yaw
    island._last_head_pitch = head_pitch

    speed = clamp_speed(island.speed)
    if bool(getattr(state, "pose_hooks_islands", True)):
        tau = DEFAULT_HEAD_GAIN_ANGLE * omega_y + 0.35 * DEFAULT_HEAD_GAIN_ANGLE * omega_p
        omega_mag = math.hypot(omega_y, omega_p)
        if normalize_idle_mode(state.idle_mode) == IDLE_MODE_STILL_FROZEN and omega_mag < OMEGA_EPS:
            tau = 0.0
    else:
        # Pose does not drive island spring — only idle / residual spring state.
        tau = 0.0

    k = DEFAULT_SPRING_K * speed
    c = DEFAULT_SPRING_C
    island.spring_vx += dt * (-k * island.spring_x - c * island.spring_vx + tau)
    island.spring_x += dt * island.spring_vx
    lim = DEFAULT_ANGLE_MAX
    island.spring_x = max(-lim, min(lim, island.spring_x))

    idle = 0.0
    if normalize_idle_mode(state.idle_mode) == IDLE_MODE_STILL_WOBBLE:
        amp = DEFAULT_IDLE_ANGLE_DEG * speed
        t = island._time_s * speed
        phase = 0.0
        if bool(getattr(state, "island_phase_stagger", False)):
            phase = island_idle_phase_rad(island_index, island_count)
        idle = amp * math.sin(t * IDLE_SINE_OMEGA + phase)

    return (island.spring_x + idle) * clamp_strength(island.strength)


def apply_wobble(
        rgba: numpy.ndarray,
        state: RegionWobbleState,
        *,
        head_yaw: float = 0.0,
        head_pitch: float = 0.0,
        now_s: Optional[float] = None,
        target_tag: str = "") -> numpy.ndarray:
    """Multi-region ray-hinge: ≤3 islands/slot, each with own strength/speed."""
    if now_s is None:
        now_s = time.perf_counter()
    debug_on = bool(getattr(state, "debug_enabled", False))

    def _skip(
            reason: str,
            h: int = 0,
            w: int = 0,
            angle: float = 0.0,
            mask: Optional[numpy.ndarray] = None,
            pins: Sequence[PinPoint] = (),
            has_axis: bool = False) -> numpy.ndarray:
        state.last_debug = build_debug_snapshot(
            triggered=False,
            skip_reason=reason,
            target_tag=target_tag,
            frame_h=h,
            frame_w=w,
            angle_deg=angle,
            mask=mask,
            shift_map=None,
            collect_pixel_stats=debug_on,
            pin_count=len(pins),
            has_axis=has_axis,
            now_s=float(now_s))
        return rgba

    if rgba is None or rgba.ndim != 3 or rgba.shape[2] < 4:
        return _skip("bad_rgba")
    h, w = int(rgba.shape[0]), int(rgba.shape[1])
    if not state.enabled:
        return _skip(
            "disabled", h, w,
            mask=state.mask_for_shape(h, w),
            pins=state.pins,
            has_axis=bool(state.axes))
    if not state.has_active_mask():
        return _skip("no_mask", h, w, pins=state.pins, has_axis=bool(state.axes))

    pins_all, axes_all, _src = state.geometry_for_shape(h, w)
    hook = bool(getattr(state, "pose_hooks_islands", True))
    if hook:
        off_x, off_y = pose_island_offset_px(float(head_yaw), float(head_pitch))
    else:
        off_x, off_y = 0.0, 0.0
    q_off_x = int(round(off_x))
    q_off_y = int(round(off_y))
    if q_off_x or q_off_y:
        pins_all = [(px + q_off_x, py + q_off_y) for px, py in pins_all]
        axes_all = [
            (a[0] + q_off_x, a[1] + q_off_y, a[2] + q_off_x, a[3] + q_off_y)
            for a in axes_all]

    # Integrate springs first (always), then decide whether to reuse cached warp.
    planned: List[Tuple[MaskIsland, Sequence[PinPoint], AxisLine, float, WobbleRegionPart, int]] = []
    angle_keys: List[float] = []
    for idx, part in enumerate(state.regions):
        components = state.components_for_region(idx, h, w)
        if not components:
            continue
        if q_off_x or q_off_y:
            components = [
                offset_island(c, float(q_off_x), float(q_off_y), full_h=h, full_w=w)
                for c in components]
            components = [c for c in components if c.pixel_count > 0]
            if not components:
                continue
        part.ensure_island_bank()
        n_islands = len(components)
        for isl_i, island in enumerate(components):
            params = part.islands[isl_i]
            angle_deg = _integrate_angle_spring(
                state, params, float(head_yaw), float(head_pitch), float(now_s),
                island_index=isl_i, island_count=n_islands)
            angle_keys.append(round(float(angle_deg), 1))
            if abs(angle_deg) < ANGLE_EPS:
                if normalize_idle_mode(state.idle_mode) == IDLE_MODE_STILL_FROZEN:
                    continue
            local_pins = pins_for_island(pins_all, island)
            axis = pick_axis_for_island(axes_all, island)
            if axis is None:
                continue
            planned.append((island, local_pins, axis, angle_deg, part, isl_i))

    cache_key = (
        id(rgba),
        int(h),
        int(w),
        int(state._mask_generation),
        round(float(head_yaw), 2),
        round(float(head_pitch), 2),
        q_off_x,
        q_off_y,
        tuple(angle_keys),
        bool(hook),
        bool(getattr(state, "island_phase_stagger", False)),
        debug_on,
    )
    cached = getattr(state, "_last_wobble_rgba", None)
    if (
            not debug_on
            and cached is not None
            and getattr(state, "_last_wobble_key", None) == cache_key
            and cached.shape == rgba.shape):
        return cached

    if not planned:
        return _skip(
            "no_region_axis",
            h, w,
            mask=state.mask_for_shape(h, w),
            pins=pins_all,
            has_axis=bool(axes_all))

    out = rgba
    wrote = False
    any_triggered = False
    last_angle = 0.0
    last_mask = None
    last_pins: Sequence[PinPoint] = ()
    last_blend = None
    last_axis = None

    for island, local_pins, axis, angle_deg, part, isl_i in planned:
        if not wrote:
            out = numpy.array(rgba, copy=True, dtype=numpy.uint8)
            wrote = True
        warped, blend = warp_hinge_island(
            out,
            island,
            pins=local_pins,
            axis=axis,
            angle_deg=angle_deg,
            out=out,
            return_blend=debug_on)
        out = warped
        any_triggered = True
        last_angle = angle_deg
        last_mask = island.as_full_mask() if debug_on else None
        last_pins = local_pins
        last_blend = blend
        last_axis = axis
        if isl_i == 0:
            part.spring_x = part.islands[0].spring_x
            part.spring_vx = part.islands[0].spring_vx

    if not any_triggered:
        return _skip(
            "no_region_axis",
            h, w,
            mask=state.mask_for_shape(h, w),
            pins=pins_all,
            has_axis=bool(axes_all))

    shift_map = None
    if debug_on and last_mask is not None and last_axis is not None and last_blend is not None:
        x0, y0, _x1, _y1 = last_axis
        yy, xx = numpy.meshgrid(
            numpy.arange(h, dtype=numpy.float32),
            numpy.arange(w, dtype=numpy.float32),
            indexing="ij")
        dist = numpy.sqrt((xx - float(x0)) ** 2 + (yy - float(y0)) ** 2)
        shift_map = dist * abs(float(numpy.deg2rad(last_angle))) * last_blend

    state.last_debug = build_debug_snapshot(
        triggered=True,
        skip_reason="",
        target_tag=target_tag,
        frame_h=h,
        frame_w=w,
        angle_deg=last_angle,
        mask=last_mask if last_mask is not None else state.mask_for_shape(h, w),
        shift_map=shift_map,
        collect_pixel_stats=debug_on,
        pin_count=len(last_pins),
        has_axis=True,
        now_s=float(now_s))
    result = numpy.ascontiguousarray(out, dtype=numpy.uint8)
    state._last_wobble_key = cache_key
    state._last_wobble_rgba = result
    return result


def character_mask_path(workspace_dir: Path) -> Path:
    return Path(workspace_dir) / "region_wobble_mask.png"


def character_region_mask_path(workspace_dir: Path, index: int) -> Path:
    if int(index) <= 0:
        return character_mask_path(workspace_dir)
    return Path(workspace_dir) / f"region_wobble_mask_r{int(index)}.png"


def layer_mask_path(basic_layers_dir: Path, slot_id: int) -> Path:
    return Path(basic_layers_dir) / f"slot_{int(slot_id)}" / "region_wobble_mask.png"


def layer_region_mask_path(basic_layers_dir: Path, slot_id: int, index: int) -> Path:
    if int(index) <= 0:
        return layer_mask_path(basic_layers_dir, slot_id)
    return (
        Path(basic_layers_dir)
        / f"slot_{int(slot_id)}"
        / f"region_wobble_mask_r{int(index)}.png"
    )
