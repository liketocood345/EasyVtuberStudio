"""Output enhancement: pose interp, SSAA, NN SR/RIFE, optional TRT."""

from output_enhancement.antialiasing import (
    KeyframeRenderCache,
    compose_character_rgba_from_keyframe,
    get_antialias_factor_from_control,
    normalize_antialias_strength,
)
from output_enhancement.config import (
    INFER_BACKEND_LABELS,
    INFER_BACKEND_ORT,
    INFER_BACKEND_PYTORCH,
    INFER_BACKEND_TRT,
    INFER_BACKEND_VALUES,
    NN_FRAME_INTERP_LABELS,
    NN_FRAME_INTERP_OFF,
    NN_FRAME_INTERP_VALUES,
    NN_SR_LABELS,
    NN_SR_OFF,
    NN_SR_VALUES,
    THA_INFER_FP16_CHOICES,
    THA_INFER_FP16_LABELS,
    config_from_persistence,
    pipeline_config_from_persistence,
)
from output_enhancement.pipeline import EnhancementPipeline, FrameSourceTag
from output_enhancement.pose_interpolation import (
    POSE_FRAME_INTERP_LABELS,
    POSE_FRAME_INTERP_OFF,
    POSE_FRAME_INTERP_VALUES,
    PoseInterpolationController,
)
from output_enhancement.runtime import OutputEnhancementRuntime

__all__ = [
    "EnhancementPipeline",
    "FrameSourceTag",
    "INFER_BACKEND_LABELS",
    "INFER_BACKEND_ORT",
    "INFER_BACKEND_PYTORCH",
    "INFER_BACKEND_TRT",
    "INFER_BACKEND_VALUES",
    "KeyframeRenderCache",
    "NN_FRAME_INTERP_LABELS",
    "NN_FRAME_INTERP_OFF",
    "NN_FRAME_INTERP_VALUES",
    "NN_SR_LABELS",
    "NN_SR_OFF",
    "NN_SR_VALUES",
    "OutputEnhancementRuntime",
    "POSE_FRAME_INTERP_LABELS",
    "POSE_FRAME_INTERP_OFF",
    "POSE_FRAME_INTERP_VALUES",
    "PoseInterpolationController",
    "THA_INFER_FP16_CHOICES",
    "THA_INFER_FP16_LABELS",
    "config_from_persistence",
    "pipeline_config_from_persistence",
    "compose_character_rgba_from_keyframe",
    "get_antialias_factor_from_control",
    "normalize_antialias_strength",
]
