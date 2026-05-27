"""Resolve paths inside the fork repository (no machine-specific absolute paths)."""
from __future__ import annotations

from pathlib import Path

_MARKER_DIRS = (
    Path("deps") / "tha3",
    Path("deps") / "pip",
)


def find_repo_root(start: Path | None = None) -> Path:
    """Walk parents from *start* until fork layout markers exist."""
    here = (start or Path(__file__)).resolve()
    if here.is_file():
        here = here.parent
    for candidate in (here, *here.parents):
        for marker in _MARKER_DIRS:
            if (candidate / marker).is_dir():
                return candidate
    raise FileNotFoundError(
        "Cannot locate fork repo root (expected deps/tha3 or deps/pip directory). "
        f"Started from: {here}")


def get_deps_root(repo_root: Path | None = None) -> Path:
    return (repo_root or find_repo_root()) / "deps"


def get_tha3_bundle_root(repo_root: Path | None = None) -> Path:
    return get_deps_root(repo_root) / "tha3"


def get_pip_deps_root(repo_root: Path | None = None) -> Path:
    return get_deps_root(repo_root) / "pip"


def get_demo_root(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    nested = root / "talking-head-anime-4-demo"
    if nested.is_dir():
        return nested
    sibling = root.parent / "talking-head-anime-4-demo"
    if sibling.is_dir():
        return sibling
    return nested


def get_experiment_root(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    nested = root / "experiments" / "puppeteer_load_preview"
    if nested.is_dir():
        return nested
    alt = root / "face-puppeteer-ui-enhancements-ai-code" / "experiments" / "puppeteer_load_preview"
    if alt.is_dir():
        return alt
    return nested


def get_demo_src_path(repo_root: Path | None = None) -> Path:
    return get_demo_root(repo_root) / "src"


def get_packaged_model_yaml(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    candidates = (
        root / "packaged" / "bai_450k" / "character_model" / "character_model.yaml",
        root / "face-puppeteer-ui-enhancements-ai-code" / "packaged" / "bai_450k" / "character_model" / "character_model.yaml",
        root / "baiten_from_project_forlon9" / "bai_450k" / "character_model" / "character_model.yaml",
    )
    for path in candidates:
        if path.is_file():
            return path
    return candidates[0]
