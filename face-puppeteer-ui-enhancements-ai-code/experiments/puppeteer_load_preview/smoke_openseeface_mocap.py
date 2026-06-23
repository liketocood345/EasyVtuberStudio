"""Smoke: OpenSeeFace frame -> MediaPipeFacePose -> converter."""
import math
import struct
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from tha3_paths import find_repo_root, get_demo_src_path

sys.path.insert(0, str(get_demo_src_path(find_repo_root(EXPERIMENT_DIR))))

from scipy.spatial.transform import Rotation

from tha4.mocap.mediapipe_face_pose_converter_00 import MediaPoseFacePoseConverter00

from openseeface_mocap_driver import (
    OSF_DEFAULT_FPS,
    OSF_EYE_CLOSE_MIN_DURATION_SEC,
    OpenSeeFaceMocapState,
    OpenSeeFaceInputPacer,
    OsfEyeMotionPattern,
    angle_delta_deg,
    apply_osf_eye_motion_pattern,
    build_openseeface_face_screen_motion,
    build_openseeface_mediapipe_face_pose,
    classify_osf_eye_motion_pattern,
    clamp_osf_fps,
    copy_mediapipe_face_pose,
    lerp_mediapipe_face_pose,
    osf_eye_blinks_from_frame,
    osf_head_is_near_forward,
    osf_rotation_to_packet_quaternion,
    resolve_osf_eye_motion,
)
from openseeface_packet import (
    OSF_FEATURE_NAMES,
    OSF_LANDMARK_CONFIDENCE_BASE,
    OSF_LEFT_PUPIL_LANDMARK,
    OSF_RIGHT_PUPIL_LANDMARK,
    OSF_UDP_STRUCT_FORMAT,
    OSF_UDP_VALUE_COUNT,
    build_test_openseeface_udp_packet,
    parse_openseeface_udp_packet,
)


def build_test_packet_with_raw_euler_x(raw_euler_x: float) -> bytes:
    values = [0.0] * OSF_UDP_VALUE_COUNT
    values[0] = 1.0
    values[1] = 0
    values[4] = 1.0
    values[5] = 1.0
    values[6] = 1
    values[12] = float(raw_euler_x)
    values[13] = 10.0
    values[14] = 90.0
    rotation_x = (-float(raw_euler_x) + 360.0) % 360.0 - 180.0
    rotation = Rotation.from_euler(
        "xyz",
        [math.radians(rotation_x), 0.0, 0.0],
        degrees=False,
    )
    qx, qy, qz, qw = osf_rotation_to_packet_quaternion(rotation)
    values[8] = qx
    values[9] = qy
    values[10] = qz
    values[11] = qw
    values[1] = int(values[1])
    values[6] = int(values[6])
    return struct.pack(OSF_UDP_STRUCT_FORMAT, *values)


def build_test_packet_with_eyes(
        *,
        right_eye_open: float = 1.0,
        left_eye_open: float = 1.0,
        eye_right_feature: float = 0.0,
        eye_left_feature: float = 0.0,
        right_pupil_confidence: float = 1.0,
        left_pupil_confidence: float = 1.0) -> bytes:
    values = list(struct.unpack(OSF_UDP_STRUCT_FORMAT, build_test_openseeface_udp_packet()))
    values[4] = float(right_eye_open)
    values[5] = float(left_eye_open)
    values[OSF_LANDMARK_CONFIDENCE_BASE + OSF_RIGHT_PUPIL_LANDMARK] = float(
        right_pupil_confidence)
    values[OSF_LANDMARK_CONFIDENCE_BASE + OSF_LEFT_PUPIL_LANDMARK] = float(
        left_pupil_confidence)
    feature_start = len(values) - len(OSF_FEATURE_NAMES)
    values[feature_start + OSF_FEATURE_NAMES.index("EyeLeft")] = float(eye_left_feature)
    values[feature_start + OSF_FEATURE_NAMES.index("EyeRight")] = float(eye_right_feature)
    values[1] = int(values[1])
    values[6] = int(values[6])
    return struct.pack(OSF_UDP_STRUCT_FORMAT, *values)


def test_eye_motion_pattern_classification() -> None:
    assert classify_osf_eye_motion_pattern(0.0, 0.0) == OsfEyeMotionPattern.OPEN
    assert classify_osf_eye_motion_pattern(0.8, 0.05) == OsfEyeMotionPattern.WINK_LEFT
    assert classify_osf_eye_motion_pattern(0.05, 0.8) == OsfEyeMotionPattern.WINK_RIGHT
    assert classify_osf_eye_motion_pattern(0.55, 0.52) == OsfEyeMotionPattern.BLINK_BOTH
    assert classify_osf_eye_motion_pattern(0.38, 0.12) == OsfEyeMotionPattern.WINK_LEFT
    assert classify_osf_eye_motion_pattern(0.10, 0.36) == OsfEyeMotionPattern.WINK_RIGHT

    blink_left, blink_right = apply_osf_eye_motion_pattern(
        OsfEyeMotionPattern.BLINK_BOTH, 0.6, 0.55)
    assert abs(blink_left - blink_right) < 1e-6
    assert blink_left >= 0.55

    close_left, close_right = apply_osf_eye_motion_pattern(
        OsfEyeMotionPattern.CLOSE_BOTH, 0.78, 0.8)
    assert close_left >= 0.88
    assert close_right >= 0.88

    wink_l, wink_r = apply_osf_eye_motion_pattern(
        OsfEyeMotionPattern.WINK_LEFT, 0.85, 0.2)
    assert wink_l > 0.8
    assert wink_r < 0.2


def test_wink_hold_survives_low_fps_gap() -> None:
    state = OpenSeeFaceMocapState(calibration_warmup_remaining=0)
    t0 = 1000.0
    wink_frame = parse_openseeface_udp_packet(
        build_test_packet_with_eyes(
            right_eye_open=1.0,
            left_eye_open=0.25,
            eye_left_feature=-0.75,
            eye_right_feature=-0.05,
            right_pupil_confidence=1.0,
            left_pupil_confidence=0.0,
        ))
    assert wink_frame is not None
    motion = resolve_osf_eye_motion(wink_frame, state, t0)
    assert motion.pattern == OsfEyeMotionPattern.WINK_LEFT
    assert motion.left > 0.65

    open_frame = parse_openseeface_udp_packet(build_test_packet_with_eyes())
    assert open_frame is not None
    held = resolve_osf_eye_motion(open_frame, state, t0 + 0.05)
    assert held.pattern == OsfEyeMotionPattern.OPEN
    assert held.left > 0.5
    assert held.right < 0.2


def test_blink_both_vs_close_both_temporal() -> None:
    state = OpenSeeFaceMocapState(calibration_warmup_remaining=0)
    t0 = 1000.0
    frame = parse_openseeface_udp_packet(
        build_test_packet_with_eyes(
            right_eye_open=0.05,
            left_eye_open=0.05,
            eye_right_feature=-0.85,
            eye_left_feature=-0.85,
            right_pupil_confidence=0.0,
            left_pupil_confidence=0.0,
        ))
    assert frame is not None

    motion_short = resolve_osf_eye_motion(frame, state, t0)
    assert motion_short.pattern == OsfEyeMotionPattern.BLINK_BOTH

    motion_long = resolve_osf_eye_motion(
        frame, state, t0 + OSF_EYE_CLOSE_MIN_DURATION_SEC + 0.05)
    assert motion_long.pattern == OsfEyeMotionPattern.CLOSE_BOTH
    assert motion_long.left >= 0.88
    assert motion_long.right >= 0.88


def test_no_blink_when_pupil_untracked_without_eyelid() -> None:
    frame = parse_openseeface_udp_packet(
        build_test_packet_with_eyes(
            right_eye_open=0.15,
            left_eye_open=0.15,
            right_pupil_confidence=0.0,
            left_pupil_confidence=0.0,
            eye_right_feature=0.0,
            eye_left_feature=0.0,
        ))
    assert frame is not None
    assert osf_eye_blinks_from_frame(frame) == (0.0, 0.0)

    eyelid_only = parse_openseeface_udp_packet(
        build_test_packet_with_eyes(
            right_eye_open=0.1,
            left_eye_open=1.0,
            right_pupil_confidence=0.0,
            left_pupil_confidence=1.0,
            eye_right_feature=-0.8,
            eye_left_feature=0.0,
        ))
    assert eyelid_only is not None
    blink_left, blink_right = osf_eye_blinks_from_frame(eyelid_only)
    assert blink_right > 0.65
    assert blink_left < 0.2


def test_independent_eye_blink_wink() -> None:
    open_frame = parse_openseeface_udp_packet(build_test_packet_with_eyes())
    assert open_frame is not None
    assert osf_eye_blinks_from_frame(open_frame) == (0.0, 0.0)

    left_wink = parse_openseeface_udp_packet(
        build_test_packet_with_eyes(
            right_eye_open=1.0,
            left_eye_open=0.25,
            eye_left_feature=-0.75,
            eye_right_feature=-0.05,
            right_pupil_confidence=1.0,
            left_pupil_confidence=0.0,
        ))
    assert left_wink is not None
    blink_left, blink_right = osf_eye_blinks_from_frame(left_wink)
    assert blink_left > 0.65
    assert blink_right < 0.2

    right_wink = parse_openseeface_udp_packet(
        build_test_packet_with_eyes(
            right_eye_open=0.25,
            left_eye_open=1.0,
            eye_right_feature=-0.75,
            eye_left_feature=-0.05,
            right_pupil_confidence=0.0,
            left_pupil_confidence=1.0,
        ))
    assert right_wink is not None
    blink_left, blink_right = osf_eye_blinks_from_frame(right_wink)
    assert blink_right > 0.65
    assert blink_left < 0.2

    state = OpenSeeFaceMocapState(calibration_warmup_remaining=0)
    converter = MediaPoseFacePoseConverter00()
    left_pose = build_openseeface_mediapipe_face_pose(left_wink, state)
    left_out = converter.convert(left_pose)
    assert left_out[converter.eye_wink_left_index] > 0.65
    assert left_out[converter.eye_wink_right_index] < 0.2


def test_convert_chain() -> None:
    frame = parse_openseeface_udp_packet(build_test_openseeface_udp_packet())
    assert frame is not None
    state = OpenSeeFaceMocapState()
    state.calibration_warmup_remaining = 0
    pose = build_openseeface_mediapipe_face_pose(frame, state)
    converter = MediaPoseFacePoseConverter00()
    out = converter.convert(pose)
    assert isinstance(out, list)
    assert len(out) > 0


def test_default_fps() -> None:
    assert OSF_DEFAULT_FPS == 12
    assert clamp_osf_fps(None) == 12
    assert clamp_osf_fps(24) == 24
    assert clamp_osf_fps(0) == 1


def test_head_rotation_affects_converter_pose() -> None:
    state = OpenSeeFaceMocapState()
    state.calibration_warmup_remaining = 0
    neutral_frame = parse_openseeface_udp_packet(build_test_packet_with_raw_euler_x(0.0))
    assert neutral_frame is not None
    neutral_pose = build_openseeface_mediapipe_face_pose(neutral_frame, state)
    moved_frame = parse_openseeface_udp_packet(build_test_packet_with_raw_euler_x(20.0))
    assert moved_frame is not None
    moved_pose = build_openseeface_mediapipe_face_pose(moved_frame, state)
    converter = MediaPoseFacePoseConverter00()
    neutral_out = converter.convert(neutral_pose)
    moved_out = converter.convert(moved_pose)
    assert neutral_out[converter.head_x_index] != moved_out[converter.head_x_index]


def test_pitch_delta_wraps_near_180() -> None:
    assert angle_delta_deg(165.0, -150.0) == -45.0
    assert angle_delta_deg(-180.0, -150.0) == -30.0

    state = OpenSeeFaceMocapState()
    for _ in range(12):
        neutral = parse_openseeface_udp_packet(build_test_packet_with_raw_euler_x(0.0))
        assert neutral is not None
        build_openseeface_mediapipe_face_pose(neutral, state)
    assert state.calibration_warmup_remaining == 0

    converter = MediaPoseFacePoseConverter00()
    head_x_values: list[float] = []
    for raw_x in (-30, -15, 0, 15, 30):
        frame = parse_openseeface_udp_packet(build_test_packet_with_raw_euler_x(float(raw_x)))
        assert frame is not None
        pose = build_openseeface_mediapipe_face_pose(frame, state)
        head_x_values.append(converter.convert(pose)[converter.head_x_index])
    # OSF rawEuler.x increases when looking down; head_x decreases accordingly.
    for earlier, later in zip(head_x_values, head_x_values[1:]):
        assert later <= earlier + 1e-6
    assert head_x_values[0] > head_x_values[-1]


def test_face_screen_motion_from_translation() -> None:
    state = OpenSeeFaceMocapState()
    state.calibration_warmup_remaining = 0
    state.translation_offset = (0.0, 0.0, 0.0)
    neutral = parse_openseeface_udp_packet(build_test_openseeface_udp_packet())
    assert neutral is not None
    motion0 = build_openseeface_face_screen_motion(neutral, state)
    assert motion0 is not None
    assert abs(motion0.center_x) < 0.01
    assert abs(motion0.center_y) < 0.01

    values = [0.0] * OSF_UDP_VALUE_COUNT
    values[0] = 1.0
    values[4] = 1.0
    values[5] = 1.0
    values[6] = 1
    values[15] = 0.2
    values[16] = -0.1
    values[17] = 0.15
    values[1] = int(values[1])
    values[6] = int(values[6])
    moved = parse_openseeface_udp_packet(struct.pack(OSF_UDP_STRUCT_FORMAT, *values))
    assert moved is not None
    motion1 = build_openseeface_face_screen_motion(moved, state)
    assert motion1 is not None
    assert motion1.center_x != motion0.center_x or motion1.center_y != motion0.center_y


def test_forward_recenter_gate() -> None:
    state = OpenSeeFaceMocapState()
    state.calibration_warmup_remaining = 0
    neutral = parse_openseeface_udp_packet(build_test_openseeface_udp_packet())
    assert neutral is not None
    state.rotation_offset = [
        neutral.rotation_x,
        neutral.rotation_y,
        neutral.rotation_z,
    ]
    assert osf_head_is_near_forward(neutral, state)

    turned = parse_openseeface_udp_packet(build_test_packet_with_raw_euler_x(35.0))
    assert turned is not None
    assert not osf_head_is_near_forward(turned, state)


def test_input_pacer_uniform_keyframes() -> None:
    frame = parse_openseeface_udp_packet(build_test_openseeface_udp_packet())
    assert frame is not None
    state = OpenSeeFaceMocapState()
    state.calibration_warmup_remaining = 0
    pose_a = build_openseeface_mediapipe_face_pose(frame, state)

    moved_frame = parse_openseeface_udp_packet(build_test_packet_with_raw_euler_x(15.0))
    assert moved_frame is not None
    pose_b = build_openseeface_mediapipe_face_pose(moved_frame, state)

    pacer = OpenSeeFaceInputPacer(target_fps=10, max_catchup_frames=1)
    pacer.push_latest(pose_a)
    t0 = pacer._next_keyframe_mono
    interval = 0.1
    out0, key0 = pacer.update(t0)
    assert out0 is not None
    assert key0

    out_mid, key_mid = pacer.update(t0 + interval * 0.5)
    assert out_mid is not None
    assert not key_mid

    pacer.push_latest(pose_b)
    out1, key1 = pacer.update(t0 + interval)
    assert out1 is not None
    assert key1

    lerped = lerp_mediapipe_face_pose(pose_a, pose_b, 0.5)
    lerped_out = copy_mediapipe_face_pose(lerped)
    assert lerped_out.blendshape_params == lerped.blendshape_params


if __name__ == "__main__":
    test_convert_chain()
    test_eye_motion_pattern_classification()
    test_wink_hold_survives_low_fps_gap()
    test_blink_both_vs_close_both_temporal()
    test_no_blink_when_pupil_untracked_without_eyelid()
    test_independent_eye_blink_wink()
    test_head_rotation_affects_converter_pose()
    test_default_fps()
    test_pitch_delta_wraps_near_180()
    test_face_screen_motion_from_translation()
    test_forward_recenter_gate()
    test_input_pacer_uniform_keyframes()
    print("smoke_openseeface_mocap_ok")
