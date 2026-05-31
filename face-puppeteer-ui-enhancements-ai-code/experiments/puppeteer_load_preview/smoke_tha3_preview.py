"""CLI smoke: load THA3 PNG + neutral pose, write one PNG frame."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from tha3_engine import Tha3Engine
from tha3_paths import find_repo_root, get_demo_src_path, get_packaged_model_yaml
from tha3_pose_adapter import neutral_tha3_pose


def main() -> int:
    parser = argparse.ArgumentParser()
    default_png = get_packaged_model_yaml(find_repo_root(EXPERIMENT_DIR)).parent / "character.png"
    parser.add_argument("--png", default=str(default_png), help="512x512 RGBA character PNG")
    parser.add_argument("--variant", default="separable_half")
    parser.add_argument("--out", default=str(EXPERIMENT_DIR / "smoke_tha3_output.png"))
    args = parser.parse_args()

    sys.path.insert(0, str(get_demo_src_path(find_repo_root(EXPERIMENT_DIR))))
    from tha4.mocap.mediapipe_face_pose_converter_00 import MediaPoseFacePoseConverter00

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    engine = Tha3Engine(device, model_variant=args.variant)
    if not engine.load_character_png(args.png):
        print("smoke_tha3_failed", engine.last_error)
        return 1

    converter = MediaPoseFacePoseConverter00()
    pose = neutral_tha3_pose(converter)
    wx_image = engine.render_pose(pose)
    if wx_image is None:
        print("smoke_tha3_failed", engine.last_error or "render returned None")
        return 1

    wx_image.SaveFile(args.out, wx.BitmapType(wx.BITMAP_TYPE_PNG))
    print("smoke_tha3_ok", args.out, "device=", device, "backend=", engine._backend_kind)
    return 0


if __name__ == "__main__":
    import wx

    app = wx.App(False)
    raise SystemExit(main())
