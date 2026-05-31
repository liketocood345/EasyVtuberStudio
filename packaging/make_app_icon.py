"""Regenerate app-icon-source.ico from app-icon-source.png."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "assets" / "branding" / "app-icon-source.png"
OUT = REPO / "assets" / "branding" / "app-icon-source.ico"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    img = Image.open(SRC).convert("RGBA")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT, format="ICO", sizes=SIZES)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
