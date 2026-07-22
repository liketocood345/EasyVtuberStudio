"""Thin launcher for portable face puppeteer build (PyInstaller onefile)."""
from __future__ import annotations

import os
import subprocess
import sys
import traceback
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


def _show_message(text: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, "EasyVtuber Studio", 0x10)
    except Exception:
        print(text, file=sys.stderr)


def _write_launch_log(portable_root: Path, text: str) -> None:
    try:
        log_path = portable_root / "workspace" / "launch.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(text)
            if not text.endswith("\n"):
                handle.write("\n")
    except Exception:
        pass


def _probe_runtime(python_exe: Path, portable_root: Path) -> str | None:
    probe_script = portable_root / "packaging" / "probe_mouse_student_runtime.py"
    if probe_script.is_file():
        probe = subprocess.run(
            [str(python_exe), str(probe_script), str(python_exe), str(portable_root)],
            capture_output=True,
            text=True,
            cwd=str(portable_root),
        )
        if probe.returncode == 0:
            return None
        detail = (probe.stderr or probe.stdout or "unknown import error").strip()
        _write_launch_log(portable_root, f"runtime probe failed:\n{detail}")
        return detail

    probe = subprocess.run(
        [str(python_exe), "-c", "import torch, wx, matplotlib; print('ok')"],
        capture_output=True,
        text=True,
        cwd=str(portable_root),
    )
    if probe.returncode == 0:
        return None
    detail = (probe.stderr or probe.stdout or "unknown import error").strip()
    _write_launch_log(portable_root, f"runtime probe failed:\n{detail}")
    return detail


def main() -> int:
    portable_root: Path | None = None
    try:
        sys.path.insert(0, str(_experiment_dir(_LAUNCHER)))

        from portable_bootstrap import ensure_portable_ready  # noqa: E402
        from portable_paths import (  # noqa: E402
            get_demo_root,
            portable_mouse_student_ready,
            resolve_load_preview_script,
            resolve_portable_python_exe,
            resolve_portable_root_from_launcher,
        )

        portable_root = resolve_portable_root_from_launcher(_LAUNCHER)
        os.environ["THA4_PORTABLE_ROOT"] = str(portable_root)
        os.environ["THA4_WORKSPACE"] = str(portable_root / "workspace")

        if not portable_mouse_student_ready(portable_root):
            setup_rc = ensure_portable_ready(_LAUNCHER, interactive=True)
            if setup_rc != 0:
                return setup_rc

        python_exe = resolve_portable_python_exe(
            portable_root,
            prefer_pythonw=True,
            require_mediapipe=False,
        )
        if python_exe is None:
            _show_message(
                "Python runtime not found.\n\n"
                "Run DEPLOY.bat in the repo root and install tier [1] basic_run,\n"
                "or tier [2] face_puppeteer if you need camera capture.")
            return 1

        try:
            script = resolve_load_preview_script(portable_root)
        except FileNotFoundError as exc:
            _show_message(str(exc))
            return 1

        demo_root = get_demo_root(portable_root)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(demo_root / "src")
        env["THA4_PORTABLE_ROOT"] = str(portable_root)
        env["THA4_WORKSPACE"] = str(portable_root / "workspace")

        probe_error = _probe_runtime(python_exe, portable_root)
        if probe_error:
            _show_message(
                "Python runtime is incomplete for Mouse + Audio mode.\n\n"
                f"{probe_error}\n\n"
                "Run DEPLOY.bat and install tier [1] basic_run.\n"
                "Details: workspace\\launch.log")
            return 1

        log_path = portable_root / "workspace" / "launch.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with log_path.open("a", encoding="utf-8") as log_handle:
                log_handle.write(f"\n--- launch {script} ---\n")
        except Exception:
            pass

        subprocess.Popen(
            [str(python_exe), str(script)],
            cwd=str(demo_root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return 0
    except Exception as exc:
        detail = traceback.format_exc()
        if portable_root is not None:
            _write_launch_log(portable_root, detail)
        _show_message(
            "EasyVtuber Studio failed to start.\n\n"
            f"{exc}\n\n"
            "See workspace\\launch.log if available.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
