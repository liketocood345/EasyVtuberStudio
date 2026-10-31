"""Thin launcher for portable face puppeteer build (PyInstaller onefile)."""
from __future__ import annotations
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END
# EVS-DESIGN-AUDIT EVS-A120 BEGIN
# 设计[dep-003] [明确缺口（提示档位过期）]
# 缺环境文案仍写 tier [2] face_puppeteer；当前数字菜单 [2]=OSF、[3]=MediaPipe。这里只标记文案与菜单不一致，不更改字符串或重打包 EXE。
# 历史 bug 热点 #6：仅为回归关联，非声称本次故障已复现。
# 诊断标记 R-DEPLOY-01：参照文件头诊断报告；本次不修复实际行为。
# EVS-DESIGN-AUDIT EVS-A120 END

import os
import subprocess
import sys
import time
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


# EVS-DESIGN-AUDIT EVS-A119 BEGIN
# 设计[f-057, dep-012] [符合（15s 超时）]
# subprocess.run 外层及 fallback 均 timeout=15；若 resolve 已缓存成功探测则跳过第二轮 torch 导入。
# 历史 bug 热点 #2,#6：启动预检限时。
# EVS-DESIGN-AUDIT EVS-A119 END
def _probe_runtime(python_exe: Path, portable_root: Path) -> str | None:
    probe_script = portable_root / "packaging" / "probe_mouse_student_runtime.py"
    try:
        if probe_script.is_file():
            probe = subprocess.run(
                [str(python_exe), str(probe_script), str(python_exe), str(portable_root)],
                capture_output=True,
                text=True,
                cwd=str(portable_root),
                timeout=15,
            )
        else:
            probe = subprocess.run(
                [str(python_exe), "-c", "import torch, wx, matplotlib; print('ok')"],
                capture_output=True,
                text=True,
                cwd=str(portable_root),
                timeout=15,
            )
    except subprocess.TimeoutExpired:
        detail = "runtime probe timed out after 15s"
        _write_launch_log(portable_root, f"runtime probe failed:\n{detail}")
        return detail
    if probe.returncode == 0:
        return None
    detail = (probe.stderr or probe.stdout or "unknown import error").strip()
    _write_launch_log(portable_root, f"runtime probe failed:\n{detail}")
    return detail


# EVS-DESIGN-AUDIT EVS-A118 BEGIN
# 设计[dep-011, dep-012, f-057] [符合（跳过重复探测）]
# resolve_portable_python_exe 已探测 torch/wx/matplotlib；缓存命中则跳过第二轮 _probe_runtime。现有 EXE 未重建，本注释不证明嵌入启动器已同步。
# 历史 bug 热点 #2,#6：启动预检去重。
# EVS-DESIGN-AUDIT EVS-A118 END
def main() -> int:
    portable_root: Path | None = None
    try:
        sys.path.insert(0, str(_experiment_dir(_LAUNCHER)))

        from portable_bootstrap import ensure_portable_ready  # noqa: E402
        from portable_paths import (  # noqa: E402
            get_demo_root,
            portable_mouse_student_ready,
            python_probe_cached_ok,
            resolve_load_preview_script,
            resolve_portable_python_exe,
            resolve_portable_root_from_launcher,
        )

        portable_root = resolve_portable_root_from_launcher(_LAUNCHER)
        from portable_process_env import install_local_environment
        install_local_environment(portable_root)
        os.environ["THA4_PORTABLE_ROOT"] = str(portable_root)
        os.environ["THA4_WORKSPACE"] = str(portable_root / "workspace")

        probe_t0 = time.perf_counter()
        if not portable_mouse_student_ready(portable_root):
            setup_rc = ensure_portable_ready(_LAUNCHER, interactive=True)
            if setup_rc != 0:
                return setup_rc

        python_exe = resolve_portable_python_exe(
            portable_root,
            prefer_pythonw=True,
            require_mediapipe=False,
        )
        splash_host = _experiment_dir(_LAUNCHER) / "start_with_splash.py"
        if (
                python_exe is not None
                and splash_host.is_file()
                and os.environ.get("EVS_EARLY_SPLASH") != "1"):
            pythonw = Path(python_exe)
            if pythonw.name.lower() == "python.exe":
                candidate = pythonw.with_name("pythonw.exe")
                if candidate.is_file():
                    pythonw = candidate
            # bh-6 26.10.31 02:56 s
            os.environ["EVS_BOUND_PYTHON"] = str(pythonw)
            # bh-6 26.10.31 02:56 e
            subprocess.Popen(
                [str(pythonw), str(splash_host)],
                cwd=str(splash_host.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=os.environ.copy(),
            )
            return 0
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

        # bh-6 26.10.29 19:40 s
        if python_probe_cached_ok(python_exe, require_mediapipe=False):
            probe_error = None
        else:
            probe_error = _probe_runtime(python_exe, portable_root)
        # bh-6 26.10.29 19:40 e
        probe_ms = (time.perf_counter() - probe_t0) * 1000.0
        if probe_error:
            _show_message(
                "Python runtime is incomplete for Mouse + Audio mode.\n\n"
                f"{probe_error}\n\n"
                "Run DEPLOY.bat and install tier [1] basic_run.\n"
                "Details: workspace\\launch.log")
            return 1

        spawn_t0 = time.perf_counter()
        subprocess.Popen(
            [str(python_exe), str(script)],
            cwd=str(demo_root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        spawn_ms = (time.perf_counter() - spawn_t0) * 1000.0
        _write_launch_log(
            portable_root,
            f"\n--- launch {script} ---\n"
            f"launch_timing probe_ms={probe_ms:.0f} spawn_ms={spawn_ms:.0f} python={python_exe}\n")
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
