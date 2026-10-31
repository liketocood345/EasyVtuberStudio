"""Portable release path helpers (GitHub ZIP root = PORTABLE_ROOT)."""
from __future__ import annotations
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

import json
import os
import shutil
import subprocess
from pathlib import Path

from tha3_paths import EXPERIMENT_DIR, find_repo_root, get_demo_root

UI_STATE_FILE_NAME = "load_preview_ui_state.json"
BASIC_LAYERS_DIR_NAME = "basic_layers"
WORKSPACE_DIR_NAME = "workspace"
MOUSE_STUDENT_VENV_REL = Path("runtime/venvs/common")
BAI_STUDENT_FACE_MORPHER = Path(
    "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/face_morpher.pt")


# EVS-DESIGN-AUDIT EVS-A055 BEGIN
# 设计[dep-005] [静态符合（默认寻址）；环境覆盖待核]
# 默认从当前文件定位本仓，但环境变量可覆盖根目录；运行环境、junction 与持久化绝对路径须按三个副本分别检查。
# 历史 bug 热点 #6：仅为回归关联，非声称本次故障已复现。
# EVS-DESIGN-AUDIT EVS-A055 END
def get_portable_root(start: Path | None = None) -> Path:
    env_root = os.environ.get("THA4_PORTABLE_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()
    return find_repo_root(start or EXPERIMENT_DIR)


def resolve_portable_root_from_launcher(launcher_path: Path) -> Path:
    """Resolve repo root when the launcher exe/bat lives at root or scripts/launch/."""
    env_root = os.environ.get("THA4_PORTABLE_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()
    start = launcher_path.resolve()
    if start.is_file():
        start = start.parent
    for candidate in (start, *start.parents):
        if (candidate / "deps" / "tha3" / "tha3_src").is_dir():
            return candidate
    return start


def get_demo_data_dir(portable_root: Path | None = None) -> Path:
    return get_demo_root(portable_root) / "data"


def resolve_mediapipe_task_path(portable_root: Path | None = None) -> Path | None:
    root = portable_root or get_portable_root()
    relative = Path("face_landmarker_v2_with_blendshapes.task")
    candidates = (
        root / "addons" / "face_puppeteer" / "mediapipe" / relative,
        get_demo_root(root) / "data" / "thirdparty" / "mediapipe" / relative,
        root / "data" / "thirdparty" / "mediapipe" / relative,
        EXPERIMENT_DIR / "data" / "thirdparty" / "mediapipe" / relative,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def get_portable_missing_components(portable_root: Path | None = None) -> list[str]:
    return get_tha4_student_missing_components(portable_root)


_PYTHON_PROBE_TIMEOUT_SEC = 15
_python_probe_cache: dict[tuple[str, bool], bool] = {}


def _resolved_python_key(python_exe: Path) -> str:
    try:
        return str(python_exe.resolve())
    except OSError:
        return str(python_exe)


def python_probe_cached_ok(python_exe: Path, *, require_mediapipe: bool = False) -> bool:
    key = (_resolved_python_key(python_exe), bool(require_mediapipe))
    return _python_probe_cache.get(key) is True


# EVS-DESIGN-AUDIT EVS-A052 BEGIN
# 设计[f-002, f-057, dep-012] [符合（缓存/去重/15s）]
# 用 torch/wx/matplotlib 探测兼容环境，单候选 timeout=15 秒，按解析路径缓存。不是 UI 十秒预算内的轻量存在性检查，但避免建窗前反复重导入。
# 历史 bug 热点 #2,#6：启动预检去重。
# EVS-DESIGN-AUDIT EVS-A052 END
def _python_probe_ok(python_exe: Path, *, require_mediapipe: bool) -> bool:
    if not python_exe.is_file():
        return False
    cache_key = (_resolved_python_key(python_exe), bool(require_mediapipe))
    cached = _python_probe_cache.get(cache_key)
    if cached is not None:
        return cached
    # bh-6 26.10.29 19:40 s
    root = get_portable_root().resolve()
    modules = "torch, wx"
    if require_mediapipe:
        modules += ", mediapipe"
    else:
        modules += ", matplotlib"
    try:
        from portable_process_env import local_environment
        result = subprocess.run(
            [str(python_exe), "-I", "-c", f"import sys,pathlib; r=pathlib.Path(sys.argv[1]).resolve(); assert all(pathlib.Path(p).resolve().is_relative_to(r) for p in (sys.executable,sys.prefix,sys.base_prefix)); import {modules}", str(root)],
            capture_output=True,
            text=True,
            timeout=_PYTHON_PROBE_TIMEOUT_SEC,
            check=False,
            env=local_environment(root),
        )
        ok = result.returncode == 0
    except Exception:
        ok = False
    _python_probe_cache[cache_key] = ok
    # bh-6 26.10.29 19:40 e
    return ok


def _initial_tha3_source(root):
    try:
        import json
        state=json.loads((root / 'workspace/load_preview_ui_state.json').read_text('utf-8'))
        return state.get('image_source_mode') == 'tha3'
    except (OSError, ValueError):
        return False


def _iter_portable_python_candidates(
        portable_root: Path,
        *,
        prefer_pythonw: bool) -> list[Path]:
    names = ("pythonw.exe", "python.exe") if prefer_pythonw else ("python.exe", "pythonw.exe")
    script_dirs = (
        portable_root / "runtime" / "venvs" / "common" / "Scripts",
        *((portable_root / 'addons/tha3_models/venv/Scripts',) if _initial_tha3_source(portable_root) else ()) ,
        portable_root / "addons" / "face_puppeteer" / "venv" / "Scripts",
        portable_root / "runtime" / "venv" / "Scripts",
        portable_root / MOUSE_STUDENT_VENV_REL / "Scripts",
        portable_root / "addons/tha3_models/venv/Scripts",
    )
    candidates: list[Path] = []
    seen: set[str] = set()
    for scripts_dir in script_dirs:
        for name in names:
            candidate = scripts_dir / name
            if not candidate.is_file():
                continue
            key = _resolved_python_key(candidate)
            if key in seen:
                continue
            seen.add(key)
            candidates.append(candidate)
    return candidates




# EVS-DESIGN-AUDIT EVS-A053 BEGIN
# 设计[dep-005, dep-007, f-002] [静态关联 / 路径需逐副本验收]
# 优先从本仓可选环境解析可用 Python；候选探针需导入依赖。环境路径/junction 必须核实不共享其他仓库，不能只凭目录名字证明。
# 历史 bug 热点 #6：仅为回归关联，非声称本次故障已复现。
# EVS-DESIGN-AUDIT EVS-A053 END
def resolve_portable_python_exe(
        portable_root: Path | None = None,
        *,
        prefer_pythonw: bool = True,
        require_mediapipe: bool = False) -> Path | None:
    root = portable_root or get_portable_root()
    # dep-007: an explicit experiment binding must never silently use the old env.
    binding_file = root / 'runtime/bindings/components.json'
    if binding_file.is_file():
        bindings = json.loads(binding_file.read_text('utf-8-sig'))['components']
        role = 'tha3_models' if _initial_tha3_source(root) else (
            'face_puppeteer' if require_mediapipe or 'face_puppeteer' in bindings else 'basic_run')
        binding = bindings.get('app', bindings.get(role))
        if binding is not None:
            # bh-6 26.10.31 02:56 s
            candidate = (root / binding['python']).resolve()
            if not candidate.is_relative_to(root.resolve()):
                raise ValueError('Explicit runtime binding escapes this installation')
            if prefer_pythonw:
                windowed = candidate.with_name('pythonw.exe')
                if windowed.is_file():
                    candidate = windowed
            if not candidate.is_file() or not _python_probe_ok(
                    candidate, require_mediapipe=require_mediapipe):
                raise ValueError('Explicit runtime binding is unusable: ' + str(candidate))
            return candidate
            # bh-6 26.10.31 02:56 e
    for candidate in _iter_portable_python_candidates(root, prefer_pythonw=prefer_pythonw):
        if _python_probe_ok(candidate, require_mediapipe=require_mediapipe):
            return candidate
    return None


def get_mouse_student_venv_absolute(portable_root: Path | None = None) -> Path:
    root = portable_root or get_portable_root()
    binding_file = root / 'runtime/bindings/components.json'
    if binding_file.is_file():
        binding = json.loads(binding_file.read_text('utf-8-sig'))['components'].get('basic_run')
        if binding:
            python = (root / binding['python']).resolve()
            if not python.is_relative_to(root.resolve()):
                raise ValueError('Basic runtime binding escapes this installation')
            return python.parent.parent
    return root / MOUSE_STUDENT_VENV_REL


# EVS-DESIGN-AUDIT EVS-A054 BEGIN
# 设计[f-002, f-057] [符合（进程内缓存）]
# portable_mouse_student_ready 与后续 resolve 共用探测缓存，launcher 缓存命中则跳过第二轮 torch 导入。主模块仍会再导入一次；整窗冷启动耗时未实测。
# 历史 bug 热点 #2,#6：重复预检已压缩。
# EVS-DESIGN-AUDIT EVS-A054 END
def test_mouse_student_runtime(portable_root: Path | None = None) -> bool:
    return resolve_portable_python_exe(
        portable_root,
        prefer_pythonw=False,
        require_mediapipe=False,
    ) is not None


def get_tha4_mouse_student_missing_components(portable_root: Path | None = None) -> list[str]:
    root = portable_root or get_portable_root()
    missing: list[str] = []
    if not test_mouse_student_runtime(root):
        missing.append("runtime")
    if not (root / BAI_STUDENT_FACE_MORPHER).is_file():
        missing.append("tha4_student_model")
    return missing


def portable_mouse_student_ready(portable_root: Path | None = None) -> bool:
    return not get_tha4_mouse_student_missing_components(portable_root)


def resolve_facetracker_exe(portable_root: Path | None = None) -> Path | None:
    root = portable_root or get_portable_root()
    candidates = (
        root / "addons" / "openseeface" / "Binary" / "facetracker.exe",
        root / "addons" / "openseeface" / "facetracker.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def resolve_openseeface_models_dir(portable_root: Path | None = None) -> Path | None:
    exe = resolve_facetracker_exe(portable_root)
    if exe is None:
        return None
    for candidate in (exe.parent.parent / "models", exe.parent / "models"):
        if candidate.is_dir():
            return candidate
    return None


def openseeface_capture_ready(portable_root: Path | None = None) -> bool:
    return resolve_facetracker_exe(portable_root) is not None


def mediapipe_capture_ready(portable_root: Path | None = None) -> bool:
    return face_capture_assets_ready(portable_root)


def any_face_capture_ready(portable_root: Path | None = None) -> bool:
    return mediapipe_capture_ready(portable_root) or openseeface_capture_ready(portable_root)


def face_capture_ready_for_mode(mode: str, portable_root: Path | None = None) -> bool:
    from mouse_mocap_driver import (
        MOCAP_INPUT_MODE_MEDIAPIPE,
        MOCAP_INPUT_MODE_OPENSEEFACE,
    )
    if mode == MOCAP_INPUT_MODE_OPENSEEFACE:
        return openseeface_capture_ready(portable_root)
    if mode == MOCAP_INPUT_MODE_MEDIAPIPE:
        return mediapipe_capture_ready(portable_root)
    return True


def face_capture_assets_ready(portable_root: Path | None = None) -> bool:
    root = portable_root or get_portable_root()
    if resolve_mediapipe_task_path(root) is None:
        return False
    return resolve_portable_python_exe(
        root,
        prefer_pythonw=False,
        require_mediapipe=True,
    ) is not None


def get_tha4_face_capture_missing_components(portable_root: Path | None = None) -> list[str]:
    root = portable_root or get_portable_root()
    missing = list(get_tha4_mouse_student_missing_components(root))
    if resolve_mediapipe_task_path(root) is None:
        missing.append("mediapipe_task")
    elif not resolve_portable_python_exe(root, prefer_pythonw=False, require_mediapipe=True):
        missing.append("mediapipe_runtime")
    return missing


def get_tha4_student_missing_components(portable_root: Path | None = None) -> list[str]:
    """Legacy name: full face-capture student readiness (includes MediaPipe)."""
    return get_tha4_face_capture_missing_components(portable_root)


def portable_tha4_student_ready(portable_root: Path | None = None) -> bool:
    return face_capture_assets_ready(portable_root)


def portable_app_ready(portable_root: Path | None = None) -> bool:
    return portable_mouse_student_ready(portable_root)


def portable_runtime_ready(portable_root: Path | None = None) -> bool:
    return test_mouse_student_runtime(portable_root)


def get_workspace_dir(portable_root: Path | None = None) -> Path:
    root = portable_root or get_portable_root()
    workspace = root / WORKSPACE_DIR_NAME
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def _legacy_ui_state_path(experiment_dir: Path) -> Path:
    return experiment_dir / UI_STATE_FILE_NAME


def _legacy_basic_layers_dir(experiment_dir: Path) -> Path:
    return experiment_dir / BASIC_LAYERS_DIR_NAME


def _sanitize_ui_state_path_fields(data: dict) -> bool:
    from tha3_paths import from_repo_relative, to_repo_relative

    changed = False
    for key in ("last_loaded_model_path", "tha3_character_png", "output_background_image_path"):
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        stored = to_repo_relative(value)
        if stored != value:
            data[key] = stored
            changed = True
        resolved = from_repo_relative(stored)
        if isinstance(resolved, str) and os.path.isabs(resolved) and not os.path.isfile(resolved):
            data.pop(key, None)
            changed = True
    return changed


def _sanitize_ui_state_file(state_path: Path) -> None:
    if not state_path.is_file():
        return
    try:
        import json

        with state_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return
        if not _sanitize_ui_state_path_fields(data):
            return
        with state_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=True, indent=2)
    except Exception:
        pass


def _maybe_migrate_workspace_state(experiment_dir: Path, workspace_state: Path) -> None:
    legacy_state = _legacy_ui_state_path(experiment_dir)
    if workspace_state.is_file() or not legacy_state.is_file():
        return
    workspace_state.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy_state, workspace_state)
    _sanitize_ui_state_file(workspace_state)
    legacy_layers = _legacy_basic_layers_dir(experiment_dir)
    target_layers = workspace_state.parent / BASIC_LAYERS_DIR_NAME
    if legacy_layers.is_dir() and not target_layers.exists():
        shutil.copytree(legacy_layers, target_layers)


def resolve_ui_state_file_path(experiment_dir: Path | None = None) -> Path:
    experiment_dir = (experiment_dir or EXPERIMENT_DIR).resolve()
    workspace_state = get_workspace_dir() / UI_STATE_FILE_NAME
    _maybe_migrate_workspace_state(experiment_dir, workspace_state)
    return workspace_state


def resolve_load_preview_script(portable_root: Path | None = None) -> Path:
    root = portable_root or get_portable_root()
    candidates = (
        root / "face-puppeteer-ui-enhancements-ai-code" / "experiments" / "puppeteer_load_preview"
        / "character_model_mediapipe_puppeteer_load_preview.py",
        root / "experiments" / "puppeteer_load_preview"
        / "character_model_mediapipe_puppeteer_load_preview.py",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("Load Preview entry script not found under portable root")

