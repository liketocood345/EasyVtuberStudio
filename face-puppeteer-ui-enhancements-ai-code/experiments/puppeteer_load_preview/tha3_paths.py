"""Path helpers for THA3 black-box integration (bundled under repo deps/tha3)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent

THA3_VARIANT_CHOICES = (
    ("separable_half", "separable / half (省显存 / lighter VRAM)"),
    ("separable_float", "separable / float"),
    ("standard_half", "standard / half"),
    ("standard_float", "standard / float"),
)

IMAGE_SOURCE_THA4 = "tha4_student"
IMAGE_SOURCE_THA3 = "tha3"


def find_repo_root(start: Path | None = None) -> Path:
    here = (start or EXPERIMENT_DIR).resolve()
    if here.is_file():
        here = here.parent
    for candidate in (here, *here.parents):
        bundle = candidate / "deps" / "tha3"
        if (bundle / "tha3_src").is_dir() and (bundle / "ezvtuber_rt").is_dir():
            return candidate
    raise FileNotFoundError(
        "THA3 bundle not found. Expected deps/tha3 under repo root. "
        "Run: deps\\tha3\\populate_tha3_bundle.ps1"
    )


def get_demo_root(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    if (root / "src").is_dir():
        return root
    nested = root / "talking-head-anime-4-demo"
    if (nested / "src").is_dir():
        return nested
    alt = root / "face-puppeteer-ui-enhancements-ai-code" / "talking-head-anime-4-demo"
    if (alt / "src").is_dir():
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


def get_tha3_bundle_root() -> Path:
    return find_repo_root() / "deps" / "tha3"


def get_tha3_source_root() -> Path:
    return get_tha3_bundle_root() / "tha3_src"


def get_ezvtuber_models_root() -> Path:
    return get_tha3_bundle_root() / "models"


def get_ezvtuber_images_root() -> Path:
    return get_tha3_bundle_root() / "images"


def get_ezvtuber_rt_root() -> Path:
    return get_tha3_bundle_root() / "ezvtuber_rt"


def variant_to_ort_flags(variant: str) -> tuple[bool, bool]:
    normalized = (variant or "separable_half").strip().lower()
    separable = normalized.startswith("separable")
    fp16 = normalized.endswith("_half")
    return separable, fp16


def variant_to_pytorch_model_name(variant: str) -> str:
    normalized = (variant or "separable_half").strip().lower()
    mapping = {
        "separable_half": "separable_half",
        "separable_float": "separable_float",
        "standard_half": "standard_half",
        "standard_float": "standard_float",
    }
    return mapping.get(normalized, "separable_half")


def pytorch_model_dir(variant: str) -> Path:
    return get_ezvtuber_models_root() / variant_to_pytorch_model_name(variant)


def pytorch_models_available(variant: str) -> bool:
    model_dir = pytorch_model_dir(variant)
    required = (
        "eyebrow_decomposer.pt",
        "eyebrow_morphing_combiner.pt",
        "face_morpher.pt",
        "two_algo_face_body_rotator.pt",
        "editor.pt",
    )
    return all((model_dir / name).is_file() for name in required)


_PATH_KEYS = ("last_loaded_model_path", "tha3_character_png")


def to_repo_relative(path: str | None, repo_root: Path | None = None) -> str | None:
    """Store paths relative to fork repo root (forward slashes)."""
    if not path or not isinstance(path, str):
        return path
    normalized = path.strip()
    if not normalized:
        return path
    p = Path(normalized)
    if not p.is_absolute():
        return p.as_posix()
    root = (repo_root or find_repo_root()).resolve()
    try:
        return p.resolve().relative_to(root).as_posix()
    except ValueError:
        try:
            return p.resolve().relative_to(EXPERIMENT_DIR.resolve()).as_posix()
        except ValueError:
            return normalized


def from_repo_relative(path: str | None, repo_root: Path | None = None) -> str | None:
    """Resolve repo-relative (or experiment-relative) paths to absolute."""
    if not path or not isinstance(path, str):
        return path
    normalized = path.strip()
    if not normalized:
        return path
    p = Path(normalized)
    if p.is_absolute():
        return str(p.resolve())
    root = (repo_root or find_repo_root()).resolve()
    candidates = (
        root / p,
        EXPERIMENT_DIR / p,
        root / "face-puppeteer-ui-enhancements-ai-code" / p,
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return str(resolved)
    return str((root / p).resolve())


def ensure_tha3_on_path() -> Path:
    root = get_tha3_source_root().parent
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return get_tha3_source_root()
