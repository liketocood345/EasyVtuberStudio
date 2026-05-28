"""Path helpers for THA3 black-box integration (EasyVtuber vendor junctions)."""
from __future__ import annotations

import os
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
BUNDLE_ROOT = EXPERIMENT_DIR.parents[1]
VENDOR_ROOT = BUNDLE_ROOT / "vendor" / "easyvtuber"
EZVTUBER_FALLBACK = Path(r"F:\EasyVtuber\EasyVtuber_v0.8.1\EasyVtuber_v0.8.1")

THA3_VARIANT_CHOICES = (
    ("separable_half", "separable / half (省显存 / lighter VRAM)"),
    ("separable_float", "separable / float"),
    ("standard_half", "standard / half"),
    ("standard_float", "standard / float"),
)

IMAGE_SOURCE_THA4 = "tha4_student"
IMAGE_SOURCE_THA3 = "tha3"


def resolve_vendor_root() -> Path:
    if (VENDOR_ROOT / "tha3").exists():
        return VENDOR_ROOT
    return EZVTUBER_FALLBACK


def get_tha3_source_root() -> Path:
    vendor = resolve_vendor_root()
    linked = vendor / "tha3"
    if linked.exists():
        return linked
    return EZVTUBER_FALLBACK / "tha3"


def get_ezvtuber_models_root() -> Path:
    vendor = resolve_vendor_root()
    linked = vendor / "data_models"
    if linked.exists():
        return linked
    return EZVTUBER_FALLBACK / "data" / "models"


def get_ezvtuber_images_root() -> Path:
    vendor = resolve_vendor_root()
    linked = vendor / "data_images"
    if linked.exists():
        return linked
    return EZVTUBER_FALLBACK / "data" / "images"


def get_ezvtuber_rt_root() -> Path:
    vendor = resolve_vendor_root()
    linked = vendor / "ezvtuber-rt"
    if linked.exists():
        return linked
    return EZVTUBER_FALLBACK / "ezvtuber-rt"


def variant_to_ort_flags(variant: str) -> tuple[bool, bool]:
    """Return (separable, fp16) for ezvtb_rt CoreORT."""
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


def ensure_tha3_on_path() -> Path:
    root = get_tha3_source_root().parent
    root_str = str(root)
    if root_str not in os.sys.path:
        os.sys.path.insert(0, root_str)
    return get_tha3_source_root()
