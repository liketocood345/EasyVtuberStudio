"""Folder-local caches and logs; only process variables, never global settings."""
import os
from pathlib import Path

def root_from_source():
    requested = os.environ.get('THA4_PORTABLE_ROOT')
    if requested:
        return Path(requested).resolve()
    for candidate in Path(__file__).resolve().parents:
        if (candidate / 'DEPLOY.bat').is_file():
            return candidate
    raise RuntimeError('Portable application root not found')

def local_environment(root):
    root = Path(root)
    env = os.environ.copy()
    for key in ('PYTHONHOME', 'PYTHONPATH', 'PIP_TARGET', 'PIP_PREFIX', 'PIP_USER'):
        env.pop(key, None)
    env.update(PYTHONNOUSERSITE='1', PIP_CONFIG_FILE='NUL', THA4_PORTABLE_ROOT=str(root))
    for key in ('TEMP','TMP','PIP_CACHE_DIR','TORCH_HOME','MPLCONFIGDIR','HF_HOME',
                'CUDA_CACHE_PATH','NUMBA_CACHE_DIR','APPDATA','LOCALAPPDATA','XDG_CACHE_HOME'):
        path = root / 'workspace/cache' / key.lower()
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    return env

def install_local_environment(root=None):
    os.environ.update(local_environment(root or root_from_source()))

_DIAG_DIRECTORY = None

def debug_log_path(session):
    # EVS-PERF 0.1: resolve the root and mkdir once (was per call, incl. hot paths).
    global _DIAG_DIRECTORY
    directory = _DIAG_DIRECTORY
    if directory is None:
        directory = root_from_source() / 'workspace/diagnostics'
        directory.mkdir(parents=True, exist_ok=True)
        _DIAG_DIRECTORY = directory
    return str(directory / ('debug-'+session+'.log'))
