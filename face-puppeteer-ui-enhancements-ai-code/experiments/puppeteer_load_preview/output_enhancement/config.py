"""Persistence keys and normalized choice values for output enhancement."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

# --- Super resolution (f-056) ---
NN_SR_OFF = "off"
NN_SR_ANIME4K_X2 = "anime4k_x2"
NN_SR_WAIFU2X_X2_FP32 = "waifu2x_x2_fp32"
NN_SR_WAIFU2X_X2_FP16 = "waifu2x_x2_fp16"
NN_SR_ESRGAN_X4_FP32 = "real_esrgan_x4_fp32"
NN_SR_ESRGAN_X4_FP16 = "real_esrgan_x4_fp16"

NN_SR_VALUES = (
    NN_SR_OFF,
    NN_SR_ANIME4K_X2,
    NN_SR_WAIFU2X_X2_FP32,
    NN_SR_WAIFU2X_X2_FP16,
    NN_SR_ESRGAN_X4_FP32,
    NN_SR_ESRGAN_X4_FP16,
)
NN_SR_LABELS = (
    "关闭 / Off",
    "anime4k x2 (OpenCL, 轻量)",
    "waifu2x x2 (FP32)",
    "waifu2x x2 (FP16)",
    "Real-ESRGAN x4 (FP32)",
    "Real-ESRGAN x4 (FP16)",
)

# --- RIFE image interpolation (f-055) ---
NN_FRAME_INTERP_OFF = 1
NN_FRAME_INTERP_VALUES = (1, 2, 3, 4)
NN_FRAME_INTERP_LABELS = (
    "关闭 / Off (×1)",
    "RIFE ×2 (图像域)",
    "RIFE ×3 (图像域)",
    "RIFE ×4 (图像域)",
)

# --- Inference backend for NN ops (f-058) ---
INFER_BACKEND_PYTORCH = "pytorch"
INFER_BACKEND_ORT = "ort"
INFER_BACKEND_TRT = "trt"
INFER_BACKEND_VALUES = (INFER_BACKEND_PYTORCH, INFER_BACKEND_ORT, INFER_BACKEND_TRT)
INFER_BACKEND_LABELS = (
    "PyTorch / 默认 (仅 THA FP16)",
    "ONNX Runtime (SR/RIFE)",
    "TensorRT (SR/RIFE, 需 NVIDIA)",
)

THA_INFER_FP16_CHOICES = ("full", "half")
THA_INFER_FP16_LABELS = ("Full (FP32)", "Half (FP16)")

PERSISTENCE_KEYS = (
    "antialias_strength",
    "output_frame_interpolation",
    "nn_super_resolution_mode",
    "nn_frame_interpolation_multiplier",
    "nn_infer_backend",
    "tha_infer_fp16",
)


def normalize_sr_mode(value: Any) -> str:
    mode = str(value or NN_SR_OFF).strip()
    if mode not in NN_SR_VALUES:
        return NN_SR_OFF
    return mode


def normalize_nn_frame_multiplier(value: Any) -> int:
    try:
        multiplier = int(value)
    except (TypeError, ValueError):
        multiplier = NN_FRAME_INTERP_OFF
    if multiplier not in NN_FRAME_INTERP_VALUES:
        return NN_FRAME_INTERP_OFF
    return multiplier


def normalize_infer_backend(value: Any) -> str:
    backend = str(value or INFER_BACKEND_PYTORCH).strip().lower()
    if backend not in INFER_BACKEND_VALUES:
        return INFER_BACKEND_PYTORCH
    return backend


def normalize_tha_infer_fp16(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "full").strip().lower()
    return text in ("half", "fp16", "true", "1", "yes")


def sr_mode_spec(mode: str) -> Tuple[str, int, bool, bool]:
    """Return (kind, scale, fp16, use_anime4k). kind in ('off', 'onnx', 'a4k')."""
    mode = normalize_sr_mode(mode)
    if mode == NN_SR_OFF:
        return "off", 1, False, False
    if mode == NN_SR_ANIME4K_X2:
        return "a4k", 2, False, True
    if mode == NN_SR_WAIFU2X_X2_FP32:
        return "onnx", 2, False, False
    if mode == NN_SR_WAIFU2X_X2_FP16:
        return "onnx", 2, True, False
    if mode == NN_SR_ESRGAN_X4_FP32:
        return "onnx", 4, False, False
    if mode == NN_SR_ESRGAN_X4_FP16:
        return "onnx", 4, True, False
    return "off", 1, False, False


def config_from_persistence(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    from output_enhancement.antialiasing import normalize_antialias_strength
    from output_enhancement.pose_interpolation import normalize_multiplier as normalize_pose_interp

    data = data or {}
    return {
        "antialias_strength": normalize_antialias_strength(
            data.get("antialias_strength", 1.0)),
        "output_frame_interpolation": normalize_pose_interp(
            data.get("output_frame_interpolation", 1)),
        "nn_super_resolution_mode": normalize_sr_mode(data.get("nn_super_resolution_mode")),
        "nn_frame_interpolation_multiplier": normalize_nn_frame_multiplier(
            data.get("nn_frame_interpolation_multiplier")),
        "nn_infer_backend": normalize_infer_backend(data.get("nn_infer_backend")),
        "tha_infer_fp16": normalize_tha_infer_fp16(data.get("tha_infer_fp16")),
    }


def pipeline_config_from_persistence(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Subset used by EnhancementPipeline (NN SR/RIFE only; excludes pose interp / SSAA)."""
    full = config_from_persistence(data)
    return {
        "nn_super_resolution_mode": full["nn_super_resolution_mode"],
        "nn_frame_interpolation_multiplier": full["nn_frame_interpolation_multiplier"],
        "nn_infer_backend": full["nn_infer_backend"],
    }
