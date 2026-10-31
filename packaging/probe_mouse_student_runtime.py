"""Probe whether basic_run (mouse student) venv can import the load-preview stack."""
from __future__ import annotations
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

import os
import subprocess
import sys
from pathlib import Path


# EVS-DESIGN-AUDIT EVS-A121 BEGIN
# 设计[f-002, f-057] [符合（15s 超时）]
# 探测基础 Mouse+Student 所需 torch/wx/matplotlib 和 tha4 导入，内层 subprocess timeout=15。
# 历史 bug 热点 #2,#6：启动探针限时。
# EVS-DESIGN-AUDIT EVS-A121 END
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
    try:
        result = subprocess.run(
            [str(python_exe), "-c", code],
            capture_output=True,
            text=True,
            cwd=str(portable_root),
            env=env,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return "runtime probe timed out after 15s"
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
