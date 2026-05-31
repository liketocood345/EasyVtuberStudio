"""Probe whether basic_run (mouse student) venv can import the load-preview stack."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def probe_mouse_student_runtime(python_exe: Path, portable_root: Path) -> str | None:
    demo_src = (
        portable_root
        / "face-puppeteer-ui-enhancements-ai-code"
        / "talking-head-anime-4-demo"
        / "src"
    )
    if not demo_src.is_dir():
        return f"missing demo src: {demo_src}"

    code = (
        "import torch, wx, matplotlib; "
        "from tha4.shion.base.image_util import resize_PIL_image; "
        "print('mouse student runtime OK', torch.__version__)"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(demo_src)
    env["THA4_PORTABLE_ROOT"] = str(portable_root)
    result = subprocess.run(
        [str(python_exe), "-c", code],
        capture_output=True,
        text=True,
        cwd=str(portable_root),
        env=env,
    )
    if result.returncode == 0:
        return None
    detail = (result.stderr or result.stdout or "unknown import error").strip()
    return detail


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: probe_mouse_student_runtime.py <python.exe> <portable_root>", file=sys.stderr)
        return 2
    error = probe_mouse_student_runtime(Path(sys.argv[1]), Path(sys.argv[2]))
    if error:
        print(error, file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
