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
    MOUSE_BLINK_INTERVAL_MAX_SEC,
    MOUSE_BLINK_INTERVAL_MIN_SEC,
    MouseCenterZone,
    MouseMocapConfig,
    blend_mouse_head_roll_degrees,
    build_blink_blendshapes,
    build_eye_look_blendshapes,
    build_head_xform_matrix,
    build_mouse_dynamic_face_screen_motion,
    build_mouse_mediapipe_face_pose,
    clamp,
    clamp_blink_interval_sec,
    clamp_horizontal_tilt_mix,
    compute_mouse_horizontal_roll_deg,
    face_size_from_vertical_zone_exit,
    face_size_from_zone_distance,
    get_mouse_tracking_surface,
    is_mouse_inside_center_zone,
    mouse_center_zone_calibration_point,
    mouse_gaze_relative_coords,
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


def test_blink_interval_clamp() -> None:
    assert clamp_blink_interval_sec(1.0) == MOUSE_BLINK_INTERVAL_MIN_SEC
    assert clamp_blink_interval_sec(25.0) == MOUSE_BLINK_INTERVAL_MAX_SEC
    assert clamp_blink_interval_sec(7.5) == 7.5


def test_center_zone_inside_outside() -> None:
    zone = MouseCenterZone(center_nx=0.1, center_ny=-0.2, half_width=0.2, half_height=0.2)
    assert is_mouse_inside_center_zone(0.1, -0.2, zone)
    assert not is_mouse_inside_center_zone(0.8, 0.8, zone)
    neutral = 0.35
    up_local_y = (0.8 - zone.center_ny) / zone.half_height
    down_local_y = (-0.8 - zone.center_ny) / zone.half_height
    assert face_size_from_vertical_zone_exit(up_local_y, neutral_face_size=neutral) < neutral
    assert face_size_from_vertical_zone_exit(down_local_y, neutral_face_size=neutral) > neutral
    inside_size = face_size_from_zone_distance(0.1, -0.2, zone)
    assert abs(inside_size - 0.35) < 1e-6


def test_with_center_at_preserving_size() -> None:
    zone = MouseCenterZone(center_nx=0.0, center_ny=0.0, half_width=0.4, half_height=0.3)
    moved = zone.with_center_at_preserving_size(1.0, -1.0)
    assert abs(moved.half_width - 0.4) < 1e-6
    assert abs(moved.half_height - 0.3) < 1e-6
    assert moved.center_nx + moved.half_width <= 1.0 + 1e-5
    assert moved.center_ny - moved.half_height >= -1.0 - 1e-5


def test_from_norm_edges_top_expand() -> None:
    zone = MouseCenterZone.from_norm_edges(-0.25, 0.25, -0.25, 0.85)
    assert zone.center_ny + zone.half_height <= 1.0 + 1e-5
    assert zone.half_height >= 0.25 - 1e-5


def test_center_zone_clamped_to_surface() -> None:
    zone = MouseCenterZone(center_nx=0.9, center_ny=-0.85, half_width=0.5, half_height=0.5)
    fitted = zone.clamped_to_surface()
    assert fitted.center_nx + fitted.half_width <= 1.0 + 1e-6
    assert fitted.center_ny + fitted.half_height <= 1.0 + 1e-6
    assert fitted.center_nx - fitted.half_width >= -1.0 - 1e-6
    assert fitted.center_ny - fitted.half_height >= -1.0 - 1e-6


def test_tracking_surface_dimensions() -> None:
    try:
        import wx
    except ImportError:
        return
    app = wx.App(False)
    try:
        surface = get_mouse_tracking_surface()
        assert surface.width >= 1
        assert surface.height >= 1
        assert surface.aspect_ratio > 0.0
    finally:
        app.Destroy()


def test_horizontal_out_tilt_mix_motion() -> None:
    zone = MouseCenterZone(center_nx=0.0, center_ny=0.0, half_width=0.25, half_height=0.25)
    only_move_x, _, _ = build_mouse_dynamic_face_screen_motion(
        0.8, 0.0, zone,
        neutral_center_x=0.0, neutral_center_y=0.0, neutral_face_size=0.35,
        horizontal_tilt_mix=0.0)
    assert abs(only_move_x - 0.8) < 1e-6
    only_tilt_x, _, _ = build_mouse_dynamic_face_screen_motion(
        0.8, 0.0, zone,
        neutral_center_x=0.0, neutral_center_y=0.0, neutral_face_size=0.35,
        horizontal_tilt_mix=1.0)
    assert abs(only_tilt_x - 0.0) < 1e-6


def test_vertical_out_up_shrinks_down_enlarges() -> None:
    zone = MouseCenterZone(center_nx=0.0, center_ny=0.0, half_width=0.25, half_height=0.25)
    neutral = 0.35
    _, up_y, up_size = build_mouse_dynamic_face_screen_motion(
        0.0, 0.8, zone,
        neutral_center_x=0.0, neutral_center_y=0.0, neutral_face_size=neutral,
        horizontal_tilt_mix=1.0)
    _, down_y, down_size = build_mouse_dynamic_face_screen_motion(
        0.0, -0.8, zone,
        neutral_center_x=0.0, neutral_center_y=0.0, neutral_face_size=neutral,
        horizontal_tilt_mix=1.0)
    assert abs(up_y - 0.8) < 1e-6
    assert abs(down_y + 0.8) < 1e-6
    assert up_size < neutral
    assert down_size > neutral


def test_horizontal_roll_blend() -> None:
    local_x = 1.5
    assert abs(blend_mouse_head_roll_degrees(0.0, 0.0, local_x, 30.0, 0.0) - 0.0) < 1e-6
    tilt_only = blend_mouse_head_roll_degrees(0.0, 0.0, local_x, 30.0, 1.0)
    assert tilt_only < 0.0
    assert blend_mouse_head_roll_degrees(0.0, 0.0, -local_x, 30.0, 1.0) > 0.0
    assert compute_mouse_horizontal_roll_deg(1.5, 30.0, 1.0) < 0.0


def test_center_zone_surface_fit_matches_inside_test() -> None:
    zone = MouseCenterZone(center_nx=0.85, center_ny=0.0, half_width=0.25, half_height=0.25)
    fitted = zone.clamped_to_surface()
    assert fitted.half_width < 0.25 - 1e-6
    left_edge = fitted.center_nx - fitted.half_width
    assert is_mouse_inside_center_zone(left_edge, 0.0, zone)
    assert not is_mouse_inside_center_zone(left_edge - 0.02, 0.0, zone)


def test_calibration_point_matches_fitted_zone_center() -> None:
    zone = MouseCenterZone(center_nx=0.0, center_ny=0.0, half_width=0.4, half_height=0.3)
    moved = zone.with_center_at_preserving_size(1.0, -1.0).clamped_to_surface()
    calib_nx, calib_ny = mouse_center_zone_calibration_point(moved)
    assert abs(calib_nx - moved.center_nx) < 1e-6
    assert abs(calib_ny - moved.center_ny) < 1e-6
    assert moved.center_nx + moved.half_width <= 1.0 + 1e-5
    assert moved.center_ny - moved.half_height >= -1.0 - 1e-5


def test_gaze_neutral_yields_forward_pose_at_calib_point() -> None:
    config = MouseMocapConfig(gaze_neutral_nx=0.4, gaze_neutral_ny=-0.2)
    assert mouse_gaze_relative_coords(0.4, -0.2, config) == (0.0, 0.0)
    pose, _, _ = build_mouse_mediapipe_face_pose(0.0, config, nx=0.4, ny=-0.2)
    shapes = pose.blendshape_params
    assert shapes.get("eyeLookInLeft", 0.0) == 0.0
    assert shapes.get("eyeLookOutLeft", 0.0) == 0.0
    matrix = pose.xform_matrix
    rot = __import__("scipy.spatial.transform", fromlist=["Rotation"]).Rotation.from_matrix(matrix[0:3, 0:3])
    euler = rot.as_euler("xyz", degrees=False)
    assert abs(euler[0]) < 1e-4 and abs(euler[1]) < 1e-4 and abs(euler[2]) < 1e-4


def test_eye_look_follows_mouse_horizontal() -> None:
    mouse_right = build_eye_look_blendshapes(0.5, 0.0, 1.0)
    mouse_left = build_eye_look_blendshapes(-0.5, 0.0, 1.0)
    assert mouse_right["eyeLookOutLeft"] > mouse_left["eyeLookOutLeft"]
    assert mouse_left["eyeLookInLeft"] > mouse_right["eyeLookInLeft"]


def test_horizontal_tilt_mix_clamp() -> None:
    assert clamp_horizontal_tilt_mix(-0.2) == 0.0
    assert clamp_horizontal_tilt_mix(1.5) == 1.0


def test_center_zone_round_trip_dict() -> None:
    zone = MouseCenterZone(center_nx=0.2, center_ny=-0.1, half_width=0.3, half_height=0.15)
    restored = MouseCenterZone.from_mapping(zone.to_dict())
    assert abs(restored.center_nx - zone.center_nx) < 1e-6
    assert abs(restored.half_width - zone.half_width) < 1e-6


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


def test_eye_head_body_horizontal_alignment() -> None:
    conv = MediaPoseFacePoseConverter00()
    config = MouseMocapConfig(blink_interval_sec=10.0, eye_look_scale=1.0)
    for nx in (0.6, -0.6):
        pose, _, _ = build_mouse_mediapipe_face_pose(0.0, config, nx=nx, ny=0.0)
        out = conv.convert(pose)
        head_y = out[conv.head_y_index]
        body_y = out[conv.body_y_index]
        iris_y = out[conv.iris_rotation_y_index]
        assert head_y == body_y
        assert head_y * (-nx) > 0.0, (nx, head_y, body_y, iris_y)
        assert iris_y * (-nx) > 0.0, (nx, head_y, iris_y)


def main() -> None:
    test_convert_chain()
    test_blink_cycle()
    test_blink_interval_clamp()
    test_center_zone_inside_outside()
    test_with_center_at_preserving_size()
    test_from_norm_edges_top_expand()
    test_center_zone_clamped_to_surface()
    test_horizontal_out_tilt_mix_motion()
    test_vertical_out_up_shrinks_down_enlarges()
    test_horizontal_roll_blend()
    test_center_zone_surface_fit_matches_inside_test()
    test_calibration_point_matches_fitted_zone_center()
    test_gaze_neutral_yields_forward_pose_at_calib_point()
    test_eye_look_follows_mouse_horizontal()
    test_horizontal_tilt_mix_clamp()
    test_tracking_surface_dimensions()
    test_center_zone_round_trip_dict()
    test_normalized_clamp()
    test_eye_head_body_horizontal_alignment()
    test_sample_mouse_without_gui()
    print("smoke_mouse_mocap_ok")


if __name__ == "__main__":
    main()
