# 【机制要点】长时诊断预埋：默认几乎全关；仅倾斜异常探针默认开。
# EVS_LONGRUN_DIAG=1 → gap/compose/小时心跳 + 倾斜周期采样
# EVS_DIAG_EYE=1 → wink/反光误判节流（默认关）
# EVS_DIAG_TILT=1（默认）→ 侧头输入动但显示/姿态卡住时落盘
# 日志：e:\debug-d095ab.log（或 EVS_LONGRUN_DIAG_LOG）
# 【关联】f-066 · f-069 · display_transform / neck_z / OSF roll
# -*- coding: utf-8 -*-
"""Lightweight long-run diagnostic hooks (opt-in; never block the game loop)."""
from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

_SESSION_ID = "d095ab"
_DEFAULT_LOG = r"e:\debug-d095ab.log"

_last_emit_mono: dict[str, float] = {}
_session_started_mono: float = 0.0
_tilt_prev: Optional[dict[str, float]] = None
_tilt_stuck_hits: int = 0


def _env_truthy(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def longrun_enabled() -> bool:
    return _env_truthy("EVS_LONGRUN_DIAG", "0")


def eye_diag_enabled() -> bool:
    # Default off after wink/blink verification; set EVS_DIAG_EYE=1 to sample.
    return _env_truthy("EVS_DIAG_EYE", "0")


def tilt_diag_enabled() -> bool:
    """Anomaly-only tilt freeze probes; set EVS_DIAG_TILT=0 to silence."""
    return _env_truthy("EVS_DIAG_TILT", "1")


def log_path() -> str:
    return os.environ.get("EVS_LONGRUN_DIAG_LOG", _DEFAULT_LOG).strip() or _DEFAULT_LOG


def emit(
        location: str,
        message: str,
        data: dict,
        *,
        hypothesis_id: str = "",
        run_id: str = "longrun",
        min_interval_s: float = 0.0) -> None:
    """Append one NDJSON line; never raise into callers."""
    try:
        if min_interval_s > 0.0:
            key = f"{hypothesis_id}:{message}"
            now = time.monotonic()
            last = _last_emit_mono.get(key, 0.0)
            if now - last < min_interval_s:
                return
            _last_emit_mono[key] = now
        payload = {
            "sessionId": _SESSION_ID,
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open(log_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass


def note_session_start() -> None:
    global _session_started_mono
    _session_started_mono = time.monotonic()
    if not longrun_enabled():
        return
    emit("longrun_diag", "session_start", {"pid": os.getpid()}, hypothesis_id="LR0")


def note_display_gap_ms(gap_ms: float) -> None:
    """Pre-buried: large display-timer gaps (UI/GIL starvation)."""
    if not longrun_enabled():
        return
    if float(gap_ms) < 250.0:
        return
    emit(
        "longrun_diag:gap",
        "display_gap_spike",
        {"gap_ms": round(float(gap_ms), 2)},
        hypothesis_id="LR1",
        min_interval_s=2.0,
    )


def note_compose_ms(compose_ms: float, *, motion_active: bool = False) -> None:
    """Pre-buried: expensive present compose samples."""
    if not longrun_enabled():
        return
    if float(compose_ms) < 80.0:
        return
    emit(
        "longrun_diag:compose",
        "compose_spike",
        {
            "compose_ms": round(float(compose_ms), 2),
            "motion_active": bool(motion_active),
        },
        hypothesis_id="LR2",
        min_interval_s=2.0,
    )


def note_hour_mark() -> None:
    """Pre-buried: hourly heartbeat while longrun diag is on."""
    if not longrun_enabled() or _session_started_mono <= 0.0:
        return
    elapsed_h = (time.monotonic() - _session_started_mono) / 3600.0
    bucket = int(elapsed_h)
    key = f"hour:{bucket}"
    if key in _last_emit_mono:
        return
    _last_emit_mono[key] = time.monotonic()
    emit(
        "longrun_diag:hour",
        "session_hour_mark",
        {"elapsed_h": round(elapsed_h, 2)},
        hypothesis_id="LR3",
    )


def note_eye_pattern(
        *,
        pattern: str,
        raw_left: float,
        raw_right: float,
        out_left: float,
        out_right: float,
        glare_candidate: bool,
        pupil_l: bool,
        pupil_r: bool) -> None:
    """Throttle wink / glare-misclassify candidates for blink-vs-wink diagnosis."""
    if not eye_diag_enabled():
        return
    if pattern not in ("wink_left", "wink_right") and not glare_candidate:
        return
    emit(
        "openseeface_mocap_driver:resolve_osf_eye_motion",
        "eye_pattern_sample",
        {
            "pattern": pattern,
            "raw_l": round(float(raw_left), 4),
            "raw_r": round(float(raw_right), 4),
            "out_l": round(float(out_left), 4),
            "out_r": round(float(out_right), 4),
            "glare_candidate": bool(glare_candidate),
            "pupil_l": bool(pupil_l),
            "pupil_r": bool(pupil_r),
            "asym": round(abs(float(raw_left) - float(raw_right)), 4),
        },
        hypothesis_id="W1",
        run_id="eye-wink",
        min_interval_s=0.35,
    )


def note_direction_calib(*, roll_deg: float, neutral_roll: float, source: str) -> None:
    """Log periodic / manual forward-gaze calibration (can zero apparent tilt)."""
    if not (tilt_diag_enabled() or longrun_enabled()):
        return
    emit(
        "longrun_diag:tilt",
        "direction_calib",
        {
            "source": str(source),
            "roll_deg": round(float(roll_deg), 3),
            "neutral_roll": round(float(neutral_roll), 3),
        },
        hypothesis_id="T3",
        run_id="tilt-freeze",
        min_interval_s=0.5,
    )


def note_tilt_pipeline(
        *,
        mode: str,
        auto_on: bool,
        input_roll_delta_deg: float,
        target_rotation_deg: float,
        display_rotation_deg: float,
        pose_neck_z: float,
        tilt_limit: float,
        smoothing: float,
        infer_active: bool,
        infer_stuck: bool,
        mocap: str) -> None:
    """Detect long-run tilt freeze: mocap roll moves but display/pose stay flat.

    Hypotheses tagged in payload.reason:
      T1 input moves, display stuck (transform / HOLD / OFF / clamp)
      T2 input moves, pose neck_z stuck (often infer stuck)
      T4 auto transform off or tilt_limit ~ 0
    """
    global _tilt_prev, _tilt_stuck_hits
    if not (tilt_diag_enabled() or longrun_enabled()):
        return

    sample = {
        "mode": str(mode),
        "auto_on": bool(auto_on),
        "in_d": round(float(input_roll_delta_deg), 3),
        "tgt": round(float(target_rotation_deg), 3),
        "disp": round(float(display_rotation_deg), 3),
        "neck_z": round(float(pose_neck_z), 4),
        "limit": round(float(tilt_limit), 2),
        "smooth": round(float(smoothing), 3),
        "infer_active": bool(infer_active),
        "infer_stuck": bool(infer_stuck),
        "mocap": str(mocap),
    }

    if longrun_enabled():
        emit(
            "longrun_diag:tilt",
            "tilt_sample",
            sample,
            hypothesis_id="T0",
            run_id="tilt-freeze",
            min_interval_s=2.0,
        )

    prev = _tilt_prev
    _tilt_prev = {
        "in_d": float(input_roll_delta_deg),
        "disp": float(display_rotation_deg),
        "neck_z": float(pose_neck_z),
        "mono": time.monotonic(),
    }
    if prev is None:
        return

    dt = max(1e-3, float(_tilt_prev["mono"]) - float(prev["mono"]))
    if dt > 2.5:
        _tilt_stuck_hits = 0
        return

    din = abs(float(input_roll_delta_deg) - float(prev["in_d"]))
    ddisp = abs(float(display_rotation_deg) - float(prev["disp"]))
    dneck = abs(float(pose_neck_z) - float(prev["neck_z"]))

    reasons = []
    if not auto_on or abs(float(tilt_limit)) < 0.05:
        if din >= 2.5:
            reasons.append("T4")
    if din >= 2.5 and ddisp < 0.15 and str(mode) in ("LIVE", "HOLD", "OFF", "RETURN"):
        reasons.append("T1")
    # T2: neck stuck while input moves. Ignore clamp saturation (±1) when
    # display rotation still tracks — those were long-run false positives.
    if din >= 2.5 and dneck < 0.008:
        neck_sat = abs(float(pose_neck_z)) >= 0.95
        if not (neck_sat and ddisp >= 0.15):
            reasons.append("T2")
            if infer_stuck or infer_active:
                reasons.append("T2_infer")

    if not reasons:
        _tilt_stuck_hits = 0
        return

    _tilt_stuck_hits += 1
    if _tilt_stuck_hits < 3:
        return

    sample["reasons"] = reasons
    sample["din"] = round(din, 3)
    sample["ddisp"] = round(ddisp, 3)
    sample["dneck"] = round(dneck, 4)
    sample["hits"] = int(_tilt_stuck_hits)
    emit(
        "longrun_diag:tilt",
        "tilt_freeze_suspect",
        sample,
        hypothesis_id="+".join(reasons),
        run_id="tilt-freeze",
        min_interval_s=3.0,
    )
    _tilt_stuck_hits = 0
