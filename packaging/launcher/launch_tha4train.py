"""Compatibility launcher: independent teacher, never embedded training."""
import ctypes
import subprocess
import sys
from pathlib import Path

def main():
    start=Path(sys.executable) if getattr(sys,'frozen',False) else Path(__file__).resolve()
    root=next((p for p in start.parents if (p/'DEPLOY.bat').is_file()),None)
    teacher=root/'addons/tha4_training/THA4Train.exe' if root else None
    if teacher is None or not teacher.is_file():
        ctypes.windll.user32.MessageBoxW(None,'请先运行 DEPLOY 档位 [5] 安装独立 THA4 教师便携端。','THA4 教师',0x10)
        return 1
    subprocess.Popen([str(teacher), *sys.argv[1:]],cwd=teacher.parent,creationflags=subprocess.CREATE_NO_WINDOW)
    return 0

if __name__=='__main__':raise SystemExit(main())
