"""Detect and optionally fetch official THA3/THA4 upstream assets."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from portable_paths import get_demo_data_dir, get_portable_root
from tha3_paths import (
    find_repo_root,
    get_ezvtuber_models_root,
    tha3_inference_assets_available,
)

THA3_UPSTREAM_ATTRIBUTION = (
    "ksuriuri/talking-head-anime-3-models (Hugging Face); "
    "fallback: pkhungurn Dropbox"
)
THA4_UPSTREAM_ATTRIBUTION = "pkhungurn/talking-head-anime-4-demo (Dropbox)"

THA4_TEACHER_WEIGHTS = (
    "face_morpher.pt",
    "body_morpher.pt",
    "eyebrow_decomposer.pt",
    "eyebrow_morphing_combiner.pt",
    "upscaler.pt",
)


def tha4_teacher_assets_available(portable_root: Path | None = None) -> bool:
    root = portable_root or get_portable_root()
    addon_tha4 = root / "addons" / "tha4_training" / "tha4"
    tha4_dir = get_demo_data_dir(root) / "tha4"
    for base in (addon_tha4, tha4_dir):
        if all((base / name).is_file() for name in THA4_TEACHER_WEIGHTS):
            return True
    return False


def tha4_training_assets_available(portable_root: Path | None = None) -> bool:
    root = portable_root or get_portable_root()
    demo_data = get_demo_data_dir(root)
    pose_candidates = (
        root / "addons" / "tha4_training" / "pose_dataset.pt",
        demo_data / "pose_dataset.pt",
    )
    has_pose = any(p.is_file() for p in pose_candidates)
    return tha4_teacher_assets_available(root) and has_pose


def tha3_assets_installed(variant: str = "separable_half", portable_root: Path | None = None) -> bool:
    return tha3_inference_assets_available(variant)


def tha3_models_root(portable_root: Path | None = None) -> Path:
    root = portable_root or get_portable_root()
    addon = root / "addons" / "tha3_models"
    if addon.is_dir():
        return addon
    return get_ezvtuber_models_root()


def run_upstream_download(
    package_ids: list[str],
    portable_root: Path | None = None,
) -> int:
    root = portable_root or find_repo_root()
    ps1 = root / "packaging" / "fetch_upstream_assets.ps1"
    if not ps1.is_file():
        return 1

    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if not powershell.is_file():
        powershell = Path("powershell")

    args = [
        str(powershell),
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ps1),
        "-PortableRoot",
        str(root),
    ]
    if package_ids:
        args.append("-PackageIds")
        args.extend(package_ids)

    creationflags = 0
    if os.name == "nt" and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
        creationflags = subprocess.CREATE_NEW_CONSOLE

    return subprocess.run(args, creationflags=creationflags).returncode


def tha3_missing_message(variant: str) -> str:
    models_root = tha3_models_root()
    return (
        "THA3 立绘模式需要 THA3 原作者发布的模型包（约 2 GB PyTorch 权重）。\n\n"
        f"来源 / source: {THA3_UPSTREAM_ATTRIBUTION}\n"
        "若 Hugging Face 不可用，安装程序会自动尝试 Dropbox 官方 zip。\n"
        "GitHub 主包不包含这些权重。\n\n"
        "安装后将自动整理到：\n"
        f"  {models_root}\n"
        "  (linked as deps/tha3/models and demo/data/models)\n\n"
        f"当前变体 / variant: {variant}"
    )


def tha4_training_missing_message() -> str:
    demo_data = get_demo_data_dir()
    return (
        "THA4 蒸馏 / 训练需要原作者发布的 Teacher 权重与 pose 数据集。\n\n"
        f"来源 / source: {THA4_UPSTREAM_ATTRIBUTION}\n"
        "GitHub 主包不包含这些文件。\n\n"
        "安装后将自动整理到：\n"
        f"  {demo_data / 'tha4'}/\n"
        f"  {demo_data / 'pose_dataset.pt'}\n\n"
        "面捕 Student 模式不需要此包。"
    )
