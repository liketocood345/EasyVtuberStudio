"""Verify shared-venv packages for Load Preview image source modes."""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import sys
from typing import List


def _pkg_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def check_shell() -> List[str]:
    errors: List[str] = []
    try:
        import mediapipe  # noqa: F401
    except Exception as exc:
        errors.append(f"mediapipe import failed: {exc}")

    pb = _pkg_version("protobuf")
    if pb is None:
        errors.append("protobuf not installed")
    elif not pb.startswith("3."):
        errors.append(f"protobuf {pb} incompatible with mediapipe 0.10.x (need 3.20.x)")

    for pkg in ("wx", "cv2", "torch", "scipy"):
        if importlib.util.find_spec(pkg) is None:
            errors.append(f"missing module: {pkg}")

    return errors


def check_tha4_student() -> List[str]:
    errors = check_shell()
    try:
        from tha4.charmodel.character_model import CharacterModel  # noqa: F401
    except Exception as exc:
        errors.append(f"tha4 student import failed: {exc}")
    return errors


def check_tha3_ort() -> List[str]:
    errors = check_shell()
    if _pkg_version("onnx") is not None:
        errors.append(
            "pip package 'onnx' is installed — uninstall it (breaks mediapipe protobuf<4)"
        )
    ort_ver = _pkg_version("onnxruntime-directml")
    if ort_ver is None:
        errors.append("onnxruntime-directml not installed (THA3 ORT path on Windows)")
    try:
        import onnxruntime  # noqa: F401
    except Exception as exc:
        errors.append(f"onnxruntime import failed: {exc}")
    return errors


def check_tha3_pytorch() -> List[str]:
    errors = check_shell()
    try:
        import torch  # noqa: F401
    except Exception as exc:
        errors.append(f"torch import failed: {exc}")
    return errors


MODES = {
    "shell": ("Shared shell", check_shell),
    "tha4_student": ("THA4 Student black box", check_tha4_student),
    "tha3_ort": ("THA3 ORT black box", check_tha3_ort),
    "tha3_pytorch": ("THA3 PyTorch black box", check_tha3_pytorch),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=list(MODES.keys()) + ["all"],
        default="all",
        help="Which dependency profile to verify",
    )
    args = parser.parse_args()

    modes = list(MODES.keys()) if args.mode == "all" else [args.mode]
    failed = False
    for mode in modes:
        label, fn = MODES[mode]
        errors = fn()
        if errors:
            failed = True
            print(f"[FAIL] {label} ({mode})")
            for err in errors:
                print(f"  - {err}")
        else:
            print(f"[OK]   {label} ({mode})")

    if not failed:
        pb = _pkg_version("protobuf")
        ort = _pkg_version("onnxruntime-directml")
        print(f"protobuf={pb}  onnxruntime-directml={ort or 'not installed'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
