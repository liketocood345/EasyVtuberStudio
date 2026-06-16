"""Resolve EZVTB model data directory for output_enhancement add-on."""
from __future__ import annotations

import os
from typing import Optional


def find_repo_root(start: Optional[str] = None) -> Optional[str]:
    cur = os.path.abspath(start or os.path.dirname(__file__))
    for _ in range(12):
        if os.path.isfile(os.path.join(cur, "DEPLOY.bat")) or os.path.isfile(
                os.path.join(cur, "EasyVtuberStudio.exe")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def get_ezvtb_data_dir(repo_root: Optional[str] = None) -> Optional[str]:
    root = repo_root or find_repo_root()
    if not root:
        return None
    candidates = (
        os.path.join(root, "addons", "output_enhancement", "ezvtb_data"),
        os.path.join(root, "data", "ezvtb_nn"),
        os.path.join(root, "workspace", "ezvtb_data"),
    )
    for path in candidates:
        if os.path.isdir(path):
            return os.path.normpath(path)
    # Prefer addon path even if not yet created (install will create it)
    return os.path.normpath(candidates[0])


def is_output_enhancement_installed(repo_root: Optional[str] = None) -> bool:
    data_dir = get_ezvtb_data_dir(repo_root)
    if not data_dir or not os.path.isdir(data_dir):
        return False
    marker = os.path.join(os.path.dirname(data_dir), ".installed")
    if os.path.isfile(marker):
        return True
    # Also accept if any expected subtree exists
    for sub in ("rife", "waifu2x", "Real-ESRGAN"):
        if os.path.isdir(os.path.join(data_dir, sub)):
            return True
    return False


def rife_onnx_path(data_dir: str, scale: int, fp16: bool) -> str:
    precision = "fp16" if fp16 else "fp32"
    return os.path.join(data_dir, "rife", f"rife_x{scale}_{precision}.onnx")


def sr_onnx_path(data_dir: str, scale: int, fp16: bool) -> str:
    precision = "fp16" if fp16 else "fp32"
    if scale == 4:
        return os.path.join(data_dir, "Real-ESRGAN", f"exported_256_{precision}.onnx")
    return os.path.join(data_dir, "waifu2x", f"noise0_scale2x_{precision}.onnx")


def get_trt_engine_cache_dir(repo_root: Optional[str] = None) -> Optional[str]:
    root = repo_root or find_repo_root()
    if not root:
        return None
    path = os.path.join(root, "workspace", "ezvtb_engines")
    os.makedirs(path, exist_ok=True)
    return os.path.normpath(path)


def onnx_weights_available(data_dir: Optional[str]) -> bool:
    if not data_dir or not os.path.isdir(data_dir):
        return False
    for scale, fp16 in ((2, False), (2, True)):
        if os.path.isfile(rife_onnx_path(data_dir, scale, fp16)):
            return True
    for scale, fp16 in ((2, False), (4, False)):
        if os.path.isfile(sr_onnx_path(data_dir, scale, fp16)):
            return True
    return False
