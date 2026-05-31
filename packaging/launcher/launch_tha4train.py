"""Thin launcher for THA4 training tools (Distiller UI entry). No custom icon."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    _LAUNCHER = Path(sys.executable)
else:
    _LAUNCHER = Path(__file__).resolve()

def _experiment_dir(start: Path) -> Path:
    here = start.resolve()
    if here.is_file():
        here = here.parent
    for candidate in (here, *here.parents):
        exp = candidate / "face-puppeteer-ui-enhancements-ai-code" / "experiments" / "puppeteer_load_preview"
        if (exp / "portable_paths.py").is_file():
            return exp
    raise RuntimeError("Could not locate puppeteer_load_preview experiment directory")

sys.path.insert(0, str(_experiment_dir(_LAUNCHER)))

from portable_bootstrap import ensure_portable_ready  # noqa: E402
from portable_paths import get_demo_root, resolve_portable_python_exe, resolve_portable_root_from_launcher  # noqa: E402
from upstream_assets_prompt import ensure_tha4_training_assets_available  # noqa: E402


def _show_message(text: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, "THA4Train", 0x10)
    except Exception:
        print(text, file=sys.stderr)


def _ensure_wx_app():
    import wx

    app = wx.GetApp()
    if app is None:
        app = wx.App(False)
    return app


def main() -> int:
    portable_root = resolve_portable_root_from_launcher(_LAUNCHER)
    os.environ["THA4_PORTABLE_ROOT"] = str(portable_root)
    os.environ["THA4_WORKSPACE"] = str(portable_root / "workspace")

    if resolve_portable_python_exe(portable_root) is None:
        setup_rc = ensure_portable_ready(_LAUNCHER, interactive=True)
        if setup_rc != 0:
            return setup_rc

    python_exe = resolve_portable_python_exe(portable_root)
    if python_exe is None:
        _show_message("Python runtime not found after setup.")
        return 1

    _ensure_wx_app()
    if not ensure_tha4_training_assets_available(offer_download=True):
        return 1

    demo_root = get_demo_root(portable_root)
    script = demo_root / "src" / "tha4" / "app" / "distiller_ui.py"
    if not script.is_file():
        _show_message(f"Distiller UI script not found:\n{script}")
        return 1

    env = os.environ.copy()
    env["PYTHONPATH"] = str(demo_root / "src")
    subprocess.Popen([str(python_exe), str(script)], cwd=str(demo_root), env=env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
