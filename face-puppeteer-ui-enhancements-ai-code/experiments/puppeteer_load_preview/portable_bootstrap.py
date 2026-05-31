"""Portable readiness check for EasyVtuberStudio.exe (install via DEPLOY.bat)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from portable_paths import (
    get_tha4_mouse_student_missing_components,
    portable_mouse_student_ready,
    resolve_portable_root_from_launcher,
)


def _show_message(text: str, *, title: str = "EasyVtuber Studio", error: bool = True) -> None:
    flags = 0x10 if error else 0x40
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, title, flags)
    except Exception:
        print(text, file=sys.stderr)


def _deploy_bat_path(portable_root: Path) -> Path:
    return portable_root / "DEPLOY.bat"


def guide_user_to_deploy(portable_root: Path, *, missing: list[str]) -> None:
    deploy_bat = _deploy_bat_path(portable_root)
    summary = ", ".join(missing) if missing else "runtime"
    deploy_hint = str(deploy_bat) if deploy_bat.is_file() else "DEPLOY.bat (repo root)"
    _show_message(
        "EasyVtuber Studio is not ready to start yet.\n\n"
        f"Missing: {summary}\n\n"
        "If this machine already has a suitable Python + PyTorch + wx environment\n"
        "under this folder, run DEPLOY once to register it.\n"
        "Otherwise DEPLOY will download and install what you need.\n\n"
        f"Please run:\n  {deploy_hint}\n\n"
        "Press Enter on each question to install only the basic tier (Mouse + Student).\n"
        "Choose Y on other tiers only if you need face capture, THA3, or training packs.\n\n"
        "After DEPLOY completes, double-click EasyVtuberStudio.exe again.",
    )


def ensure_portable_ready(launcher_path: Path, *, interactive: bool = True) -> int:
    portable_root = resolve_portable_root_from_launcher(launcher_path)
    os.environ["THA4_PORTABLE_ROOT"] = str(portable_root)
    os.environ["THA4_WORKSPACE"] = str(portable_root / "workspace")
    if portable_mouse_student_ready(portable_root):
        return 0
    missing = get_tha4_mouse_student_missing_components(portable_root)
    if interactive:
        guide_user_to_deploy(portable_root, missing=missing)
    return 1
