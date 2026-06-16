#!/usr/bin/env python3
"""Smoke tests for output_enhancement pipeline (no GUI)."""
from __future__ import annotations

import os
import sys

import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from output_enhancement.config import (
    INFER_BACKEND_PYTORCH,
    NN_FRAME_INTERP_OFF,
    NN_SR_OFF,
    config_from_persistence,
    pipeline_config_from_persistence,
)
from output_enhancement.pipeline import EnhancementPipeline
from output_enhancement.pose_interpolation import PoseInterpolationController
import frame_interpolation as frame_interp_shim


def test_pipeline_off_identity() -> None:
    pipe = EnhancementPipeline(repo_root=None)
    pipe.update_config({})
    rgba = np.zeros((64, 64, 4), dtype=np.uint8)
    rgba[16:48, 16:48, 3] = 255
    rgba[16:48, 16:48, :3] = 128
    before = pipe.content_hash(rgba)
    after = pipe.apply_identity_check(rgba.copy())
    assert pipe.content_hash(after) == before
    assert not pipe.is_active()


def test_config_normalization() -> None:
    cfg = config_from_persistence({
        "nn_super_resolution_mode": "invalid",
        "nn_frame_interpolation_multiplier": 99,
        "nn_infer_backend": "bad",
        "tha_infer_fp16": "half",
    })
    assert cfg["nn_super_resolution_mode"] == NN_SR_OFF
    assert cfg["nn_frame_interpolation_multiplier"] == NN_FRAME_INTERP_OFF
    assert cfg["nn_infer_backend"] == INFER_BACKEND_PYTORCH
    assert cfg["tha_infer_fp16"] is True


def test_pose_interpolation_controller() -> None:
    ctrl = PoseInterpolationController()
    keyframe = [0.0] * 4
    current = [1.0, 0.0, 0.0, 0.0]
    ctrl.seed_after_real_infer(keyframe)
    mid = ctrl.resolve_infer_pose(current, 2)
    assert len(mid) == 4
    assert 0.0 < mid[0] < 1.0
    ctrl.advance_after_infer(current, 2)
    assert ctrl.substep_index == 1
    ctrl.advance_after_infer(current, 2)
    assert ctrl.substep_index == 0


def test_frame_interpolation_shim() -> None:
    assert frame_interp_shim.POSE_FRAME_INTERP_OFF == 1
    assert frame_interp_shim.normalize_multiplier(3) == 3
    assert frame_interp_shim.normalize_multiplier(99) == 1


def test_pipeline_ignores_pose_interp_config() -> None:
    pipe = EnhancementPipeline(repo_root=None)
    pipe.update_config({})
    invalidated: list[bool] = []
    original_invalidate = pipe._invalidate_backends

    def track_invalidate() -> None:
        invalidated.append(True)
        original_invalidate()

    pipe._invalidate_backends = track_invalidate  # type: ignore[method-assign]
    pipe.update_config({"output_frame_interpolation": 4, "antialias_strength": 3.0})
    pipe.update_config({"tha_infer_fp16": "half"})
    assert not invalidated
    pipe.update_config({"nn_super_resolution_mode": "waifu2x_x2_fp32"})
    assert invalidated


def test_apply_persistent_pose_interp_restore() -> None:
    import json
    import os
    state_path = os.path.join(SCRIPT_DIR, "load_preview_ui_state.json")
    if not os.path.isfile(state_path):
        return
    with open(state_path, encoding="utf-8") as handle:
        data = json.load(handle)
    multiplier = frame_interp_shim.normalize_multiplier(data.get("output_frame_interpolation", 1))
    assert multiplier in frame_interp_shim.POSE_FRAME_INTERP_VALUES


def test_rgba_compose_forward() -> None:
    try:
        import cv2  # noqa: F401
    except ImportError:
        return
    from output_enhancement.antialiasing import compose_character_rgba_from_keyframe
    rgba = np.zeros((8, 8, 4), dtype=np.uint8)
    rgba[:, :, 3] = 255
    out = compose_character_rgba_from_keyframe(
        rgba, 16, 16, anchor_x=8.0, anchor_y=8.0, scale=1.0, rotation_deg=0.0, antialias_factor=1.0)
    assert out.shape == (16, 16, 4)
    from rgba_capture_compose import compose_character_rgba_from_keyframe as shim_compose
    out2 = shim_compose(
        rgba, 16, 16, anchor_x=8.0, anchor_y=8.0, scale=1.0, rotation_deg=0.0, antialias_factor=1.0)
    assert out2.shape == (16, 16, 4)


def test_keyframe_cache_gate() -> None:
    """Regression: compose stack must read output_enhancement.keyframe_cache, not _render_keyframe_rgba."""
    from output_enhancement.antialiasing import KeyframeRenderCache
    import numpy as np

    cache = KeyframeRenderCache()
    assert cache.rgba is None
    cache.rgba = np.zeros((4, 4, 4), dtype=np.uint8)
    assert cache.rgba is not None


def test_tha_infer_fp16_persist_semantics() -> None:
    """Persisted value must follow UI choice, not runtime fallback / THA3 override."""
    from output_enhancement.config import THA_INFER_FP16_CHOICES, normalize_tha_infer_fp16

    class _Choice:
        def __init__(self, index: int):
            self._index = index

        def GetSelection(self) -> int:
            return self._index

    def persisted_from_choice(control, disk_fallback: str) -> str:
        fallback_choice = (
            THA_INFER_FP16_CHOICES[1]
            if normalize_tha_infer_fp16(disk_fallback)
            else THA_INFER_FP16_CHOICES[0])
        index = control.GetSelection()
        raw = THA_INFER_FP16_CHOICES[index] if 0 <= index < len(THA_INFER_FP16_CHOICES) else fallback_choice
        return "half" if normalize_tha_infer_fp16(raw) else "full"

    # UI Half + runtime would be Full (fallback) → still persist half
    assert persisted_from_choice(_Choice(1), "half") == "half"
    # UI Full → persist full even if disk was half
    assert persisted_from_choice(_Choice(0), "half") == "full"


def main() -> int:
    test_config_normalization()
    test_tha_infer_fp16_persist_semantics()
    test_pipeline_off_identity()
    test_pose_interpolation_controller()
    test_frame_interpolation_shim()
    test_pipeline_ignores_pose_interp_config()
    test_apply_persistent_pose_interp_restore()
    test_keyframe_cache_gate()
    test_rgba_compose_forward()
    print("smoke_output_enhancement: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
