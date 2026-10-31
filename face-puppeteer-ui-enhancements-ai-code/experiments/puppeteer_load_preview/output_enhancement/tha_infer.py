"""THA4 Student FP16 inference helpers (f-060)."""
from __future__ import annotations
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

from typing import Any, Optional

import torch


_fp16_warned = False


# EVS-DESIGN-AUDIT EVS-A084 BEGIN
# 设计[f-060] [静态符合（精度入口）；模型待测]
# 主图像源 FP16 入口独立于 NN SR/RIFE；后续 FP8 咨询没有撤销 FP16。具体设备/模型是否支持半精度需验证，不能仅转换 dtype 判画质和稳定性通过。
# 历史 bug 热点 #1：仅为回归关联，非声称本次故障已复现。
# EVS-DESIGN-AUDIT EVS-A084 END
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
