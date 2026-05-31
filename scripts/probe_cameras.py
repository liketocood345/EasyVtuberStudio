"""List OpenCV camera indices available on this machine (repo-local, no hardcoded paths)."""
from __future__ import annotations

import sys


def main() -> int:
    try:
        import cv2
    except ImportError:
        print("OpenCV (cv2) is not installed in the active Python environment.", file=sys.stderr)
        return 1

    print("Probing camera indices 0-9 (press Ctrl+C to stop early)...")
    found = []
    for index in range(10):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            continue
        ok, frame = cap.read()
        cap.release()
        if ok and frame is not None:
            h, w = frame.shape[:2]
            found.append((index, w, h))
            print(f"  [OK] index {index}: {w}x{h}")
        else:
            print(f"  [--] index {index}: opened but no frame")

    if not found:
        print("No working camera indices found.")
        return 1
    print(f"Found {len(found)} camera(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
