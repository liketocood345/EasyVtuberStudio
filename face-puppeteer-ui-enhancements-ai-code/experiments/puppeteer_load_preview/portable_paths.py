"""Portable release path helpers (GitHub ZIP root = PORTABLE_ROOT)."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from tha3_paths import EXPERIMENT_DIR, find_repo_root, get_demo_root

UI_STATE_FILE_NAME = "load_preview_ui_state.json"
BASIC_LAYERS_DIR_NAME = "basic_layers"
WORKSPACE_DIR_NAME = "workspace"
MOUSE_STUDENT_VENV_REL = Path("workspace/student_venv")
BAI_STUDENT_FACE_MORPHER = Path(
    "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/face_morpher.pt")


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


def _python_probe_ok(python_exe: Path, *, require_mediapipe: bool) -> bool:
    if not python_exe.is_file():
        return False
    modules = "torch, wx"
    if require_mediapipe:
        modules += ", mediapipe"
    try:
        result = subprocess.run(
            [str(python_exe), "-c", f"import {modules}"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


def _iter_portable_python_candidates(
        portable_root: Path,
        *,
        prefer_pythonw: bool) -> list[Path]:
    names = ("pythonw.exe", "python.exe") if prefer_pythonw else ("python.exe", "pythonw.exe")
    script_dirs = (
        portable_root / "addons" / "face_puppeteer" / "venv" / "Scripts",
        portable_root / "runtime" / "venv" / "Scripts",
        portable_root / MOUSE_STUDENT_VENV_REL / "Scripts",
    )
    candidates: list[Path] = []
    for scripts_dir in script_dirs:
        for name in names:
            candidate = scripts_dir / name
            if candidate.is_file():
                candidates.append(candidate)
    return candidates


def resolve_system_python_exe(*, prefer_pythonw: bool = True) -> Path | None:
    specs: list[tuple[str, list[str]]] = [
        ("py", ["-3.11"]),
        ("py", ["-3.10"]),
    ]
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    specs.extend([
        (str(Path(system_root) / "py.exe"), ["-3.11"]),
        (str(Path(system_root) / "py.exe"), ["-3.10"]),
    ])
    for command, args in specs:
        try:
            result = subprocess.run(
                [command, *args, "-c", "import sys; print(sys.executable)"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except Exception:
            continue
        if result.returncode != 0:
            continue
        exe = Path(result.stdout.strip())
        if exe.is_file():
            return exe
    return None


def resolve_portable_python_exe(
        portable_root: Path | None = None,
        *,
        prefer_pythonw: bool = True,
        require_mediapipe: bool = False) -> Path | None:
    root = portable_root or get_portable_root()
    for candidate in _iter_portable_python_candidates(root, prefer_pythonw=prefer_pythonw):
        if _python_probe_ok(candidate, require_mediapipe=require_mediapipe):
            return candidate
    system_python = resolve_system_python_exe(prefer_pythonw=prefer_pythonw)
    if system_python and _python_probe_ok(system_python, require_mediapipe=require_mediapipe):
        return system_python
    if not require_mediapipe:
        for candidate in _iter_portable_python_candidates(root, prefer_pythonw=prefer_pythonw):
            return candidate
    return None


def get_mouse_student_venv_absolute(portable_root: Path | None = None) -> Path:
    root = portable_root or get_portable_root()
    return root / MOUSE_STUDENT_VENV_REL


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

