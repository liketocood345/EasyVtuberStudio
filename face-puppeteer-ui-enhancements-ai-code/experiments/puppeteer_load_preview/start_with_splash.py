"""Show the splash first, then spawn the main process with no console window.

This file must stay import-light (wx + PIL only) so the shortcut can paint
within about one second. Do not import the puppeteer MainFrame from here.
"""
from __future__ import annotations
from portable_process_env import debug_log_path

import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def _repo_root() -> str:
    cur = _HERE
    for _ in range(8):
        if os.path.isfile(os.path.join(cur, "DEPLOY.bat")) or os.path.isdir(
                os.path.join(cur, "scripts", "launch")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(os.path.join(_HERE, "..", "..", "..", ".."))


def _bound_python(repo: str) -> str | None:
    bound = os.environ.get("EVS_BOUND_PYTHON", "").strip()
    if bound:
        path = os.path.abspath(bound)
        repo_abs = os.path.abspath(repo)
        if path.lower().startswith(repo_abs.lower() + os.sep) and os.path.isfile(path):
            return path
        raise RuntimeError("Bound Python is missing or outside this installation: " + bound)
    binding_file = os.path.join(repo, "runtime", "bindings", "components.json")
    if not os.path.isfile(binding_file):
        return None
    import json
    with open(binding_file, "r", encoding="utf-8-sig") as handle:
        bindings = json.load(handle)["components"]
    role = "face_puppeteer" if "face_puppeteer" in bindings else "basic_run"
    binding = bindings.get("app", bindings.get(role))
    if not binding or not binding.get("python"):
        raise RuntimeError("Explicit runtime binding is missing python")
    python = os.path.abspath(os.path.join(repo, binding["python"]))
    repo_abs = os.path.abspath(repo)
    if not python.lower().startswith(repo_abs.lower() + os.sep):
        raise RuntimeError("Explicit runtime binding escapes this installation")
    pythonw = os.path.join(os.path.dirname(python), "pythonw.exe")
    if os.path.isfile(pythonw):
        return pythonw
    if os.path.isfile(python):
        return python
    raise RuntimeError("Bound Python is missing: " + python)


def _resolve_python(repo: str) -> str:
    # bh-6 26.10.31 02:56 s
    bound = _bound_python(repo)
    if bound:
        return bound
    candidates = (
        os.path.join(repo, "runtime", "venvs", "common", "Scripts", "pythonw.exe"),
        os.path.join(repo, "runtime", "venvs", "common", "Scripts", "python.exe"),
        os.path.join(repo, "addons", "face_puppeteer", "venv", "Scripts", "pythonw.exe"),
        os.path.join(repo, "addons", "face_puppeteer", "venv", "Scripts", "python.exe"),
        os.path.join(repo, "runtime", "venv", "Scripts", "pythonw.exe"),
        os.path.join(repo, "runtime", "venv", "Scripts", "python.exe"),
        os.path.join(repo, "workspace", "student_venv", "Scripts", "pythonw.exe"),
        os.path.join(repo, "workspace", "student_venv", "Scripts", "python.exe"),
    )
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise RuntimeError("No folder-local Python runtime is available. Run DEPLOY.bat.")
    # bh-6 26.10.31 02:56 e


def _demo_root(repo: str) -> str:
    candidates = (
        os.path.join(repo, "face-puppeteer-ui-enhancements-ai-code", "talking-head-anime-4-demo"),
        os.path.join(repo, "talking-head-anime-4-demo"),
        repo,
    )
    for path in candidates:
        if os.path.isdir(os.path.join(path, "src")):
            return path
    return repo


def _preview_script() -> str:
    return os.path.join(_HERE, "character_model_mediapipe_puppeteer_load_preview.py")


def main() -> int:
    started = time.perf_counter()
    os.environ.setdefault("EVS_EARLY_SPLASH", "1")
    close_path = os.path.join(os.environ.get("TEMP", _HERE), "evs-splash.close")
    os.environ["EVS_SPLASH_CLOSE"] = close_path
    try:
        if os.path.isfile(close_path):
            os.remove(close_path)
    except OSError:
        pass

    import wx
    from startup_splash import (
        close_startup_splash,
        pump_startup_splash,
        show_startup_splash,
    )

    app = wx.App(False)
    wx.DisableAsserts()
    splash = show_startup_splash(app)
    shown_ms = (time.perf_counter() - started) * 1000.0
    # #region agent log
    try:
        import json as _json
        open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({
            "sessionId": "86a17c",
            "runId": "post-fix",
            "hypothesisId": "S",
            "location": "start_with_splash.py:main",
            "message": "early splash host shown",
            "data": {
                "shown_ms": round(shown_ms, 1),
                "has_splash": splash is not None,
                "pid": os.getpid(),
            },
            "timestamp": int(time.time() * 1000),
        }) + "\n")
    except Exception:
        pass
    # #endregion

    repo = _repo_root()
    python_exe = _resolve_python(repo)
    demo = _demo_root(repo)
    script = _preview_script()
    env = os.environ.copy()
    env["EVS_EARLY_SPLASH"] = "1"
    env["EVS_SPLASH_CLOSE"] = close_path
    env["THA4_PORTABLE_ROOT"] = repo
    env["THA4_WORKSPACE"] = os.path.join(repo, "workspace")
    demo_src = os.path.join(demo, "src")
    previous_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = demo_src if not previous_pythonpath else demo_src + os.pathsep + previous_pythonpath
    create_no_window = 0x08000000 if sys.platform == "win32" else 0
    child = None
    try:
        child = subprocess.Popen(
            [python_exe, script],
            cwd=demo,
            env=env,
            creationflags=create_no_window,
        )
    except OSError:
        close_startup_splash(splash)
        return 1

    deadline = time.monotonic() + 180.0
    while time.monotonic() < deadline:
        pump_startup_splash(app, times=2)
        if os.path.isfile(close_path):
            break
        if child is not None and child.poll() is not None:
            break
        app.Yield(True)

    close_startup_splash(splash)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
