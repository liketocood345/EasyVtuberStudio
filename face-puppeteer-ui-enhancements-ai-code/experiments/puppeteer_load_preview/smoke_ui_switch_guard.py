"""Smoke tests for f-063 / f-064 helpers (no wx required)."""
from __future__ import annotations

import sys
import os

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from output_enhancement.config import (
    INFER_BACKEND_ORT,
    INFER_BACKEND_PYTORCH,
    NN_FRAME_INTERP_OFF,
    NN_SR_OFF,
    NN_SR_WAIFU2X_X2_FP32,
    pipeline_config_from_persistence,
)
from output_enhancement.pipeline import EnhancementPipeline


def test_pipeline_config_snapshot():
    pipe = EnhancementPipeline(repo_root=_ROOT)
    pipe.update_config({
        "nn_super_resolution_mode": NN_SR_WAIFU2X_X2_FP32,
        "nn_frame_interpolation_multiplier": 2,
        "nn_infer_backend": INFER_BACKEND_ORT,
    })
    snap = pipe.get_config_snapshot()
    assert snap["nn_super_resolution_mode"] == NN_SR_WAIFU2X_X2_FP32
    assert pipe.nn_modes_requested()
    assert not pipe.nn_runtime_ready() or pipe.weights_available


def test_validate_pytorch_nn_not_ready():
    pipe = EnhancementPipeline(repo_root=_ROOT)
    pipe.update_config({
        "nn_super_resolution_mode": NN_SR_WAIFU2X_X2_FP32,
        "nn_frame_interpolation_multiplier": NN_FRAME_INTERP_OFF,
        "nn_infer_backend": INFER_BACKEND_PYTORCH,
    })
    assert pipe.nn_modes_requested()
    assert not pipe.nn_runtime_ready()


def test_alignment_constants():
    from ui_alignment_monitor import (
        PERIODIC_CHECK_MS,
        POST_SWITCH_LOAD_FACTOR,
        TOAST_AUTO_CLOSE_MS,
    )

    assert PERIODIC_CHECK_MS == 180000
    assert POST_SWITCH_LOAD_FACTOR == 1.5
    assert TOAST_AUTO_CLOSE_MS == 5000


def main():
    test_pipeline_config_snapshot()
    test_validate_pytorch_nn_not_ready()
    test_alignment_constants()
    cfg = pipeline_config_from_persistence({})
    assert cfg["nn_super_resolution_mode"] == NN_SR_OFF
    print("smoke_ui_switch_guard_ok")


if __name__ == "__main__":
    main()
