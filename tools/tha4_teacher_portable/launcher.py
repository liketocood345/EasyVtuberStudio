"""Independent teacher entry; dependencies are bound within the installation."""
import os
import subprocess
import sys
from pathlib import Path

def main():
    root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    sys.path.insert(0, str(root / 'app'))
    from portable import environment, python_exe, runtime_binding, workspace_root
    python = python_exe(root, windowed='--smoke-ui' not in sys.argv and '--check-runtime' not in sys.argv)
    binding = runtime_binding(root)
    base = binding['base']
    cfg = binding['python'].parent.parent / 'pyvenv.cfg'
    if not python.is_file() or not (base / 'python.exe').is_file() or not cfg.is_file():
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, '训练环境未完整部署，请运行安装根 DEPLOY 档位 [5]。', 'THA4 教师', 0x10)
        return 1
    # venv launchers use an absolute home. Rebase to this folder after moving
    # the portable package; pip/torchrun are always invoked with python -m.
    text = cfg.read_text('utf-8')
    lines = [('home = '+str(base)) if line.startswith('home =') else line for line in text.splitlines()]
    updated = '\n'.join(lines)+'\n'
    if text != updated:
        temp = cfg.with_suffix('.tmp')
        temp.write_text(updated, 'utf-8')
        os.replace(temp, cfg)
    child_env = environment(root)
    work = workspace_root(root)
    if '--check-runtime' in sys.argv:
        return subprocess.run([str(python_exe(root)), '-I', str(root / 'app/check_runtime.py'),
                               '--root', str(root), '--report', str(work / 'runtime_probe.json')],
                              cwd=root, env=child_env, creationflags=subprocess.CREATE_NO_WINDOW).returncode
    command = [str(python), str(root / 'app/trainer_gui.py'), *sys.argv[1:]]
    with (work / 'launcher.log').open('a', encoding='utf-8') as log:
        if '--smoke-ui' in sys.argv:
            return subprocess.run(command, cwd=root, env=child_env, stdout=log, stderr=subprocess.STDOUT,
                                  creationflags=subprocess.CREATE_NO_WINDOW, timeout=30).returncode
        subprocess.Popen(command, cwd=root,
                         env=child_env, stdout=log, stderr=subprocess.STDOUT,
                         creationflags=subprocess.CREATE_NO_WINDOW)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
