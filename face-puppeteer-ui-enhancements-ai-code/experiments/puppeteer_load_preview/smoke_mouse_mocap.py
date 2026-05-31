"""CLI smoke: mouse mocap synthetic pose -> MediaPoseFacePoseConverter00.convert()."""
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from tha3_paths import find_repo_root, get_demo_src_path

sys.path.insert(0, str(get_demo_src_path(find_repo_root(EXPERIMENT_DIR))))

import numpy
from tha4.mocap.mediapipe_face_pose_converter_00 import MediaPoseFacePoseConverter00

from mouse_mocap_driver import (
    MouseMocapConfig,
    build_blink_blendshapes,
    build_head_xform_matrix,
    build_mouse_mediapipe_face_pose,
    clamp,
    sample_global_mouse_normalized,
)


def test_convert_chain() -> None:
    conv = MediaPoseFacePoseConverter00()
    config = MouseMocapConfig(blink_interval_sec=10.0)
    pose, nx, ny = build_mouse_mediapipe_face_pose(0.0, config, nx=0.25, ny=-0.4)
    assert abs(nx - 0.25) < 1e-6
    assert abs(ny + 0.4) < 1e-6
    out = conv.convert(pose)
    assert isinstance(out, list)
    assert len(out) > 0


def test_blink_cycle() -> None:
    config = MouseMocapConfig(blink_interval_sec=4.0, blink_duration_sec=0.2, eye_blink_strength=0.8)
    open_shapes = build_blink_blendshapes(0.0, config.blink_interval_sec, config.blink_duration_sec, config.eye_blink_strength)
    closed_shapes = build_blink_blendshapes(0.05, config.blink_interval_sec, config.blink_duration_sec, config.eye_blink_strength)
    assert open_shapes.get("eyeBlinkLeft", 0.0) == 0.0
    assert closed_shapes.get("eyeBlinkLeft", 0.0) > 0.0


def test_normalized_clamp() -> None:
    for nx, ny in ((2.0, -3.0), (-2.0, 3.0), (1.0, 1.0), (-1.0, -1.0)):
        matrix = build_head_xform_matrix(nx, ny, 0.3, 0.3, 0.05)
        assert matrix.shape == (4, 4)
        assert abs(matrix[3, 3] - 1.0) < 1e-6
    assert clamp(2.0, -1.0, 1.0) == 1.0
    assert clamp(-2.0, -1.0, 1.0) == -1.0


def test_sample_mouse_without_gui() -> None:
    """sample_global_mouse_normalized requires wx.App; skip if unavailable."""
    try:
        import wx
    except ImportError:
        return
    app = wx.App(False)
    try:
        nx, ny = sample_global_mouse_normalized()
        assert -1.0 <= nx <= 1.0
        assert -1.0 <= ny <= 1.0
    finally:
        app.Destroy()


def test_eye_head_horizontal_alignment() -> None:
    conv = MediaPoseFacePoseConverter00()
    config = MouseMocapConfig(blink_interval_sec=10.0, eye_look_scale=1.0)
    for nx in (0.6, -0.6):
        pose, _, _ = build_mouse_mediapipe_face_pose(0.0, config, nx=nx, ny=0.0)
        out = conv.convert(pose)
        head_y = out[conv.head_y_index]
        iris_y = out[conv.iris_rotation_y_index]
        assert head_y * nx > 0.0, (nx, head_y, iris_y)
        assert iris_y * nx > 0.0, (nx, head_y, iris_y)
        assert head_y * iris_y > 0.0, (nx, head_y, iris_y)


def main() -> None:
    test_convert_chain()
    test_blink_cycle()
    test_normalized_clamp()
    test_eye_head_horizontal_alignment()
    test_sample_mouse_without_gui()
    print("smoke_mouse_mocap_ok")


if __name__ == "__main__":
    main()
