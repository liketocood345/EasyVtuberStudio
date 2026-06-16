"""THA4 Student FP16 inference helpers (f-060)."""
from __future__ import annotations

from typing import Any, Optional

import torch


_fp16_warned = False


def apply_poser_precision(poser: Any, use_half: bool) -> None:
    if not torch.cuda.is_available():
        return
    try:
        if use_half:
            poser.half()
        else:
            poser.float()
    except Exception:
        pass


def infer_pose_image(poser, torch_source_image, pose_list, device, use_half: bool):
    """Run poser.pose with optional FP16; returns wx-compatible path via caller."""
    pose = torch.tensor(pose_list, device=device, dtype=poser.get_dtype())
    with torch.no_grad():
        if use_half and torch.cuda.is_available():
            with torch.cuda.amp.autocast(dtype=torch.float16):
                output_image = poser.pose(torch_source_image, pose)[0].float()
        else:
            output_image = poser.pose(torch_source_image, pose)[0].float()
        if torch.isnan(output_image).any() or torch.isinf(output_image).any():
            raise ValueError("FP16 inference produced NaN/Inf")
    return output_image


def tha3_variant_implies_half(variant: str) -> bool:
    v = str(variant or "").lower()
    return "half" in v or "fp16" in v
