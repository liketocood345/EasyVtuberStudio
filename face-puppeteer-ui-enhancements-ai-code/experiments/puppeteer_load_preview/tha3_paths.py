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
    """Match scripts/launch/run_load_preview_puppeteer.bat: prefer nested enhanced demo over repo-root src."""
    root = repo_root or find_repo_root()
    candidates = (
        root / "face-puppeteer-ui-enhancements-ai-code" / "talking-head-anime-4-demo",
        root / "talking-head-anime-4-demo",
        root,
    )
    for candidate in candidates:
        if (candidate / "src").is_dir():
            return candidate
    return root / "talking-head-anime-4-demo"


def get_demo_src_path(repo_root: Path | None = None) -> Path:
    return get_demo_root(repo_root) / "src"


def get_packaged_model_yaml(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    candidates = (
        root / "data" / "character_models" / "baiten_from_project_forlon9" / "bai_450k" / "character_model" / "character_model.yaml",
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
    root = find_repo_root()
    addon = root / "addons" / "tha3_models"
    if addon.is_dir() and any(addon.glob("**/*.pt")):
        return addon
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


def runtime_pytorch_model_dir(variant: str) -> Path:
    """THA3 upstream poser loads from demo cwd: data/models/<variant>."""
    return get_demo_root() / "data" / "models" / variant_to_pytorch_model_name(variant)


def pytorch_models_available(variant: str) -> bool:
    required = (
        "eyebrow_decomposer.pt",
        "eyebrow_morphing_combiner.pt",
        "face_morpher.pt",
        "two_algo_face_body_rotator.pt",
        "editor.pt",
    )
    for model_dir in (pytorch_model_dir(variant), runtime_pytorch_model_dir(variant)):
        if all((model_dir / name).is_file() for name in required):
            return True
    return False


def ort_model_dir(variant: str) -> Path:
    separable, fp16 = variant_to_ort_flags(variant)
    precision = "fp16" if fp16 else "fp32"
    family = "seperable" if separable else "standard"
    return get_ezvtuber_models_root() / "tha3" / family / precision


def ort_models_available(variant: str) -> bool:
    model_dir = ort_model_dir(variant)
    required = (
        "combiner.onnx",
        "decomposer.onnx",
        "editor.onnx",
        "merge_no_eyebrow.onnx",
    )
    return all((model_dir / name).is_file() for name in required)


def tha3_inference_assets_available(variant: str | None = None) -> bool:
    variant = variant or "separable_half"
    return pytorch_models_available(variant) or ort_models_available(variant)


def tha3_download_bat_path(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    return root / "scripts" / "launch" / "THA3_DownloadModels.bat"


_PATH_KEYS = ("last_loaded_model_path", "tha3_character_png", "output_background_image_path")

_PORTABLE_PATH_ANCHORS = (
    "data",
    "deps",
    "face-puppeteer-ui-enhancements-ai-code",
)


def portable_path_suffix(path: Path) -> Path | None:
    """Extract repo-relative tail from a foreign absolute path (e.g. E:\\other\\data\\...)."""
    parts = path.parts
    for anchor in _PORTABLE_PATH_ANCHORS:
        try:
            idx = parts.index(anchor)
        except ValueError:
            continue
        return Path(*parts[idx:])
    return None


def _resolve_under_repo(path: Path, repo_root: Path) -> Path | None:
    if path.is_file():
        return path.resolve()
    suffix = portable_path_suffix(path)
    if suffix is None:
        return None
    for candidate in (
        repo_root / suffix,
        EXPERIMENT_DIR / suffix,
        repo_root / "face-puppeteer-ui-enhancements-ai-code" / suffix,
    ):
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return None


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
            suffix = portable_path_suffix(p)
            if suffix is not None:
                return suffix.as_posix()
            return normalized


def from_repo_relative(path: str | None, repo_root: Path | None = None) -> str | None:
    """Resolve repo-relative (or experiment-relative) paths to absolute."""
    if not path or not isinstance(path, str):
        return path
    normalized = path.strip()
    if not normalized:
        return path
    p = Path(normalized)
    root = (repo_root or find_repo_root()).resolve()
    if p.is_absolute():
        remapped = _resolve_under_repo(p, root)
        if remapped is not None:
            return str(remapped)
        return str(p.resolve())
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
    bundle = get_tha3_bundle_root()
    bundle_str = str(bundle)
    if bundle_str not in sys.path:
        sys.path.insert(0, bundle_str)
    pkg = bundle / "tha3"
    if not pkg.is_dir():
        raise FileNotFoundError(
            "THA3 Python package link missing. Expected deps/tha3/tha3 -> tha3_src. "
            "Run repo-root DEPLOY.bat to repair layout.")
    return get_tha3_source_root()
