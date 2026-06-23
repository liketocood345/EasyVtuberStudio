"""Smoke: OpenSeeFace preview HWND resolution helpers."""
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from openseeface_packet import OSF_PREVIEW_WINDOW_TITLE
from openseeface_runtime import (
    fit_aspect_rect_in_box,
    parse_facetracker_camera_list,
    resolve_openseeface_preview_hwnd,
)


def test_parse_camera_list() -> None:
    text = """
0: Integrated Camera
1: IVCam
"""
    cameras = parse_facetracker_camera_list(text)
    assert len(cameras) == 2
    assert cameras[0].index == 0
    assert "Integrated" in cameras[0].label
    assert cameras[1].index == 1


def test_parse_camera_list_with_header() -> None:
    text = """Available cameras:
0: Integrated Camera
1: OBS Virtual Camera
"""
    cameras = parse_facetracker_camera_list(text)
    assert len(cameras) == 2
    assert cameras[1].label == "OBS Virtual Camera"


def test_fit_aspect_rect_in_box() -> None:
    ox, oy, fw, fh = fit_aspect_rect_in_box(1280, 720, 400, 400)
    assert fw == 400
    assert fh == 225
    assert ox == 0
    assert oy == 87


def test_preview_hwnd_pid_mismatch() -> None:
    assert resolve_openseeface_preview_hwnd(-1) is None


def test_start_stop_does_not_deadlock() -> None:
    import threading

    from openseeface_runtime import OpenSeeFaceRuntime

    runtime = OpenSeeFaceRuntime()
    result: dict[str, object] = {}

    def run() -> None:
        result["started"] = runtime.start()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout=2.0)
    assert not thread.is_alive(), "OpenSeeFaceRuntime.start() deadlocked"
    runtime.stop()


def test_start_stop_does_not_deadlock() -> None:
    import threading
    test_parse_camera_list_with_header()
    test_fit_aspect_rect_in_box()

    test_start_stop_does_not_deadlock()
    from openseeface_runtime import OpenSeeFaceRuntime

    runtime = OpenSeeFaceRuntime()
    result: dict[str, object] = {}

    def run() -> None:
        result["started"] = runtime.start()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(timeout=2.0)
    assert not thread.is_alive(), "OpenSeeFaceRuntime.start() deadlocked"
    runtime.stop()


if __name__ == "__main__":
    test_parse_camera_list()
    test_preview_hwnd_pid_mismatch()
    assert OSF_PREVIEW_WINDOW_TITLE == "OpenSeeFace Visualization"
    print("smoke_openseeface_preview_ok")
