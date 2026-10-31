"""dep-007: separate component assets, installation dependencies and user work."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def project_root(root=ROOT):
    root = Path(root).resolve()
    if root.parent.name == 'addons' and (root.parent.parent / 'packaging').is_dir():
        return root.parent.parent
    return root

PROJECT_ROOT = project_root()
WORKSPACE_ROOT = (PROJECT_ROOT / 'workspace/tools/tha4_training'
                  if PROJECT_ROOT != ROOT else ROOT / 'workspace')

def workspace_root(root=ROOT):
    project = project_root(root)
    return (project / 'workspace/tools/tha4_training'
            if project != Path(root).resolve() else project / 'workspace')

def runtime_binding(root=ROOT):
    project = project_root(root)
    bindings = project / 'runtime/bindings/components.json'
    if project != Path(root).resolve() and bindings.is_file():
        binding = json.loads(bindings.read_text('utf-8-sig'))['components']['tha4_training']
        paths = {key: (project / binding[key]).resolve() for key in ('python', 'base')}
    else:
        paths = dict(python=Path(root) / 'runtime/training_venv/Scripts/python.exe',
                     base=Path(root) / 'runtime/python310')
    if not all(path.resolve().is_relative_to(project) for path in paths.values()):
        raise ValueError('Teacher runtime binding escapes the EVS installation')
    return paths

def environment(root=ROOT):
    root = Path(root).resolve()
    project = project_root(root)
    work = workspace_root(root)
    work.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for key in ['PYTHONHOME', 'PYTHONPATH', 'PIP_TARGET', 'PIP_PREFIX', 'PIP_USER']:
        env.pop(key, None)
    env.update(PYTHONNOUSERSITE='1', PIP_CONFIG_FILE='NUL', PYTHONUNBUFFERED='1',
               THA4_PORTABLE_ROOT=str(project), EVS_TEACHER_COMPONENT_ROOT=str(root), USE_LIBUV='0')
    for key in ['TEMP', 'TMP', 'PIP_CACHE_DIR', 'TORCH_HOME', 'MPLCONFIGDIR',
                'HF_HOME', 'CUDA_CACHE_PATH', 'NUMBA_CACHE_DIR', 'XDG_CACHE_HOME',
                'TRITON_CACHE_DIR', 'APPDATA', 'LOCALAPPDATA', 'PYTHONPYCACHEPREFIX']:
        path = project / 'workspace' / 'cache' / key.lower()
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    env['PYTHONPATH'] = str(root / 'src')
    return env

def python_exe(root=ROOT, windowed=False):
    path = runtime_binding(root)['python']
    return path.with_name('pythonw.exe') if windowed else path

def atomic_json(path, value):
    import json
    import time
    import uuid
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    # Windows readers/AV can briefly deny FILE_SHARE_DELETE. Never truncate the
    # valid destination or fail a training step on the first sharing conflict.
    try:
        for attempt in range(50):
            try:
                os.replace(temp, path)
                break
            except PermissionError:
                if attempt == 49:
                    raise
                time.sleep(.1)
    finally:
        temp.unlink(missing_ok=True)
