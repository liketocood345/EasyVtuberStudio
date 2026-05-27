"""Map MediaPipe face pose to THA3's 45-float control vector (12 + 27 + 6)."""
from __future__ import annotations

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from tha4.mocap.mediapipe_face_pose import MediaPipeFacePose
    from tha4.mocap.mediapipe_face_pose_converter_00 import MediaPoseFacePoseConverter00


def mediapipe_pose_to_tha3_vector(
        mediapipe_face_pose: "MediaPipeFacePose",
        converter: "MediaPoseFacePoseConverter00") -> List[float]:
    """
    THA3 and THA4 student both use the same 45-parameter puppet schema in this project.
    The adapter keeps an explicit THA3 boundary instead of calling THA4 poser code directly.
    """
    pose = converter.convert(mediapipe_face_pose)
    if len(pose) != 45:
        raise ValueError(f"Expected THA3 pose length 45, got {len(pose)}")
    return pose


def neutral_tha3_pose(converter: "MediaPoseFacePoseConverter00") -> List[float]:
    from tha4.mocap.mediapipe_constants import BLENDSHAPE_NAMES
    from tha4.mocap.mediapipe_face_pose import MediaPipeFacePose
    import numpy

    neutral = MediaPipeFacePose({name: 0.0 for name in BLENDSHAPE_NAMES}, numpy.eye(4))
    return mediapipe_pose_to_tha3_vector(neutral, converter)
