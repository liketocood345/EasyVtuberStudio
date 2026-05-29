"""CLI smoke: load bai_450k and render one neutral pose frame (no wx/camera)."""
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from tha3_paths import find_repo_root, get_demo_src_path, get_packaged_model_yaml

sys.path.insert(0, str(get_demo_src_path(find_repo_root(EXPERIMENT_DIR))))

import numpy
import torch
from tha4.charmodel.character_model import CharacterModel
from tha4.mocap.mediapipe_constants import BLENDSHAPE_NAMES
from tha4.mocap.mediapipe_face_pose import MediaPipeFacePose
from tha4.mocap.mediapipe_face_pose_converter_00 import MediaPoseFacePoseConverter00

YAML = get_packaged_model_yaml(find_repo_root(EXPERIMENT_DIR))


def main() -> None:
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    cm = CharacterModel.load(str(YAML))
    img = cm.get_character_image(device)
    poser = cm.get_poser(device)
    conv = MediaPoseFacePoseConverter00()
    neutral = MediaPipeFacePose({n: 0.0 for n in BLENDSHAPE_NAMES}, numpy.eye(4))
    pose = conv.convert(neutral)
    out = poser.pose(img, torch.tensor(pose, device=device, dtype=poser.get_dtype()))[0]
    print("smoke_ok", tuple(out.shape), "device=", device)


if __name__ == "__main__":
    main()
