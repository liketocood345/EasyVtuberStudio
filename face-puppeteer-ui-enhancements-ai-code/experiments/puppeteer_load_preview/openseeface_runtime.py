"""OpenSeeFace subprocess, UDP receiver, and preview window capture."""
from __future__ import annotations

import ctypes
import locale
import os
import re
import socket
import subprocess
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from app_diag_log import log_once

from openseeface_mocap_driver import (
    OSF_CAMERA_LIST_TIMEOUT_SEC,
    OSF_CAPTURE_HEIGHT_DEFAULT,
    OSF_CAPTURE_WIDTH_DEFAULT,
    OSF_DEFAULT_FPS,
    OSF_DEFAULT_UDP_PORT,
    OSF_PREVIEW_HWND_POLL_SEC,
    OSF_PREVIEW_HWND_TIMEOUT_SEC,
    OSF_UDP_DISCONNECT_SEC,
    OSF_VISUALIZE_DEFAULT,
    OpenSeeFaceMocapState,
    build_openseeface_mediapipe_face_pose,
    clamp_osf_capture_height,
    clamp_osf_capture_width,
    clamp_osf_fps,
    clamp_osf_visualize_level,
)
from openseeface_packet import OSF_PREVIEW_WINDOW_TITLE, parse_openseeface_udp_packet
from portable_paths import (
    get_portable_root,
    openseeface_capture_ready,
    resolve_facetracker_exe,
    resolve_openseeface_models_dir,
)

_FACETRACKER_CAMERA_IN_USE = threading.Event()
_FACETRACKER_LIST_LOCK = threading.Lock()


def facetracker_camera_in_use() -> bool:
    return _FACETRACKER_CAMERA_IN_USE.is_set()


def mark_facetracker_camera_in_use(active: bool) -> None:
    if active:
        _FACETRACKER_CAMERA_IN_USE.set()
    else:
        _FACETRACKER_CAMERA_IN_USE.clear()


def subprocess_hide_window_kwargs() -> dict:
    """Hide console windows for Windows GUI subprocesses (facetracker.exe, etc.)."""
    if os.name != "nt":
        return {}
    kwargs: dict = {}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
        startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
        kwargs["startupinfo"] = startupinfo
    return kwargs


user32 = ctypes.windll.user32

_win32_preview_prototypes_initialized = False
_get_window_long = user32.GetWindowLongW


def _init_win32_preview_prototypes() -> None:
    global _win32_preview_prototypes_initialized, _get_window_long
    if _win32_preview_prototypes_initialized:
        return
    _win32_preview_prototypes_initialized = True
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongPtrW.restype = ctypes.c_longlong
        _get_window_long = user32.GetWindowLongPtrW
    else:
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        _get_window_long = user32.GetWindowLongW
    user32.AdjustWindowRectEx.argtypes = [
        ctypes.POINTER(wintypes.RECT), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD,
    ]
    user32.AdjustWindowRectEx.restype = wintypes.BOOL
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowW.restype = wintypes.HWND
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.SetWindowPos.argtypes = [
        wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    user32.SetWindowPos.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL


_init_win32_preview_prototypes()

GWL_STYLE = -16
GWL_EXSTYLE = -20
HWND_TOP = 0
SW_HIDE = 0
SW_SHOW = 5
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOZORDER = 0x0004


def fit_aspect_rect_in_box(
        content_width: int,
        content_height: int,
        box_width: int,
        box_height: int) -> Tuple[int, int, int, int]:
    """Return (offset_x, offset_y, fitted_w, fitted_h) centered inside the box."""
    content_width = max(1, int(content_width))
    content_height = max(1, int(content_height))
    box_width = max(1, int(box_width))
    box_height = max(1, int(box_height))
    scale = min(box_width / content_width, box_height / content_height)
    fitted_w = max(1, int(round(content_width * scale)))
    fitted_h = max(1, int(round(content_height * scale)))
    offset_x = (box_width - fitted_w) // 2
    offset_y = (box_height - fitted_h) // 2
    return offset_x, offset_y, fitted_w, fitted_h


def window_outer_size_for_client(hwnd: int, client_width: int, client_height: int) -> Tuple[int, int]:
    client_width = max(1, int(client_width))
    client_height = max(1, int(client_height))
    if hwnd <= 0 or not user32.IsWindow(wintypes.HWND(int(hwnd))):
        return client_width, client_height
    try:
        rect = wintypes.RECT(0, 0, client_width, client_height)
        window = wintypes.HWND(int(hwnd))
        style = int(_get_window_long(window, GWL_STYLE))
        ex_style = int(_get_window_long(window, GWL_EXSTYLE))
        if not user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, ex_style):
            return client_width, client_height
        return rect.right - rect.left, rect.bottom - rect.top
    except (OSError, OverflowError, ValueError):
        return client_width, client_height


def get_window_process_id(hwnd: int) -> Optional[int]:
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(wintypes.HWND(int(hwnd)), ctypes.byref(pid))
    return int(pid.value) if pid.value else None


def resolve_openseeface_preview_hwnd(facetracker_pid: int) -> Optional[int]:
    if facetracker_pid <= 0:
        return None
    try:
        hwnd = user32.FindWindowW(None, OSF_PREVIEW_WINDOW_TITLE)
    except OSError:
        return None
    if not hwnd:
        return None
    hwnd_int = int(hwnd)
    if not user32.IsWindow(wintypes.HWND(hwnd_int)):
        return None
    if get_window_process_id(hwnd_int) == facetracker_pid:
        return hwnd_int
    return None


def wait_for_openseeface_preview_hwnd(
        facetracker_pid: int,
        *,
        poll_sec: float = OSF_PREVIEW_HWND_POLL_SEC,
        timeout_sec: float = OSF_PREVIEW_HWND_TIMEOUT_SEC) -> Optional[int]:
    deadline = time.monotonic() + max(0.5, timeout_sec)
    while time.monotonic() < deadline:
        hwnd = resolve_openseeface_preview_hwnd(facetracker_pid)
        if hwnd is not None:
            return hwnd
        time.sleep(max(0.1, poll_sec))
    return None


@dataclass
class OpenSeeFaceCameraInfo:
    index: int
    label: str


def parse_facetracker_camera_list(output: str) -> List[OpenSeeFaceCameraInfo]:
    cameras: List[OpenSeeFaceCameraInfo] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.lower().startswith("available cameras"):
            continue
        match = re.match(r"^\s*(\d+)\s*[:.]\s*(.+)$", stripped)
        if not match:
            continue
        index = int(match.group(1))
        label = match.group(2).strip()
        cameras.append(OpenSeeFaceCameraInfo(index=index, label=label))
    return cameras


def _facetracker_console_encoding() -> str:
    try:
        return locale.getpreferredencoding(False) or "utf-8"
    except locale.Error:
        return "utf-8"


def list_openseeface_cameras(portable_root: Optional[Path] = None) -> List[OpenSeeFaceCameraInfo]:
    if facetracker_camera_in_use():
        return []
    exe = resolve_facetracker_exe(portable_root)
    if exe is None:
        return []
    if not _FACETRACKER_LIST_LOCK.acquire(blocking=True, timeout=2.0):
        return []
    try:
        if facetracker_camera_in_use():
            return []
        result = subprocess.run(
            [str(exe), "-l", "1"],
            capture_output=True,
            text=True,
            encoding=_facetracker_console_encoding(),
            errors="replace",
            timeout=OSF_CAMERA_LIST_TIMEOUT_SEC,
            cwd=str(exe.parent),
            check=False,
            **subprocess_hide_window_kwargs(),
        )
        text = (result.stdout or "") + "\n" + (result.stderr or "")
        cameras = parse_facetracker_camera_list(text)
        if not cameras:
            if result.returncode != 0:
                log_once(
                    "osf_list_cameras_failed",
                    f"facetracker -l 1 failed (rc={result.returncode})")
            elif text.strip():
                log_once(
                    "osf_list_cameras_empty",
                    "facetracker -l 1 returned no cameras")
        return cameras
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        log_once("osf_list_cameras_exc", f"facetracker -l 1 failed: {exc}")
        return []
    finally:
        _FACETRACKER_LIST_LOCK.release()


@dataclass
class OpenSeeFaceRuntimeStatus:
    process_running: bool = False
    udp_connected: bool = False
    preview_available: bool = False
    preview_status: str = ""
    packets_received: int = 0
    last_error: str = ""


class OpenSeeFaceRuntime:
    """Manage facetracker subprocess, UDP tracking, and preview window placement."""

    def __init__(
            self,
            *,
            portable_root: Optional[Path] = None,
            capture_interval_sec: float = 0.033) -> None:
        self._portable_root = portable_root or get_portable_root()
        self._capture_interval_sec = max(0.02, capture_interval_sec)
        self._process: Optional[subprocess.Popen] = None
        self._udp_thread: Optional[threading.Thread] = None
        self._preview_thread: Optional[threading.Thread] = None
        self._stop_lock = threading.Lock()
        self._stopped = True
        self._udp_socket: Optional[socket.socket] = None
        self._preview_hwnd: Optional[int] = None
        self._preview_hwnd_lock = threading.Lock()
        self._preview_ops_lock = threading.Lock()
        self._preview_content_width = 1280
        self._preview_content_height = 720
        self._preview_placement_key: Optional[Tuple[int, ...]] = None
        self._preview_visible = False
        self._target_fps = OSF_DEFAULT_FPS
        self._state = OpenSeeFaceMocapState()
        self._status = OpenSeeFaceRuntimeStatus()
        self._pose_callback: Optional[Callable[[object], None]] = None
        self._camera_index = 0
        self._udp_port = OSF_DEFAULT_UDP_PORT
        self._visualize_level = OSF_VISUALIZE_DEFAULT

    @property
    def state(self) -> OpenSeeFaceMocapState:
        return self._state

    @property
    def status(self) -> OpenSeeFaceRuntimeStatus:
        return self._status

    def set_pose_callback(self, callback: Optional[Callable[[object], None]]) -> None:
        self._pose_callback = callback

    def get_preview_hwnd(self) -> Optional[int]:
        with self._preview_hwnd_lock:
            return self._preview_hwnd

    def _set_preview_hwnd(self, hwnd: Optional[int]) -> None:
        with self._preview_hwnd_lock:
            self._preview_hwnd = hwnd

    def hide_preview_window(self) -> None:
        with self._preview_ops_lock:
            hwnd = self.get_preview_hwnd()
            if hwnd and self._preview_visible:
                try:
                    if user32.IsWindow(wintypes.HWND(int(hwnd))):
                        user32.ShowWindow(wintypes.HWND(int(hwnd)), SW_HIDE)
                except OSError:
                    pass
                self._preview_visible = False
            self._preview_placement_key = None

    def sync_preview_window_placement(
            self,
            *,
            screen_x: int,
            screen_y: int,
            box_width: int,
            box_height: int,
            content_width: Optional[int] = None,
            content_height: Optional[int] = None) -> bool:
        with self._preview_ops_lock:
            hwnd = self.get_preview_hwnd()
            if hwnd is None or not user32.IsWindow(wintypes.HWND(int(hwnd))):
                return False

            box_width = max(1, int(box_width))
            box_height = max(1, int(box_height))
            content_width = max(1, int(content_width or self._preview_content_width))
            content_height = max(1, int(content_height or self._preview_content_height))
            fit_offset_x, fit_offset_y, client_w, client_h = fit_aspect_rect_in_box(
                content_width, content_height, box_width, box_height)
            target_x = int(screen_x) + fit_offset_x
            target_y = int(screen_y) + fit_offset_y
            outer_w, outer_h = window_outer_size_for_client(hwnd, client_w, client_h)
            placement_key = (target_x, target_y, outer_w, outer_h)
            if placement_key == self._preview_placement_key and self._preview_visible:
                return True

            try:
                ok = bool(user32.SetWindowPos(
                    wintypes.HWND(int(hwnd)),
                    wintypes.HWND(HWND_TOP),
                    target_x,
                    target_y,
                    outer_w,
                    outer_h,
                    SWP_NOACTIVATE | SWP_SHOWWINDOW,
                ))
                if ok:
                    user32.ShowWindow(wintypes.HWND(int(hwnd)), SW_SHOW)
                    self._preview_visible = True
                    self._preview_placement_key = placement_key
                    self._status.preview_available = True
                    self._status.preview_status = "Preview docked"
                    self._state.preview_lost = False
                    self._state.preview_status = self._status.preview_status
                return ok
            except OSError:
                self._preview_visible = False
                self._preview_placement_key = None
                return False

    def start(
            self,
            *,
            camera_index: int = 0,
            udp_port: int = OSF_DEFAULT_UDP_PORT,
            visualize_level: int = OSF_VISUALIZE_DEFAULT,
            target_fps: int = OSF_DEFAULT_FPS,
            capture_width: int = OSF_CAPTURE_WIDTH_DEFAULT,
            capture_height: int = OSF_CAPTURE_HEIGHT_DEFAULT) -> bool:
        with self._stop_lock:
            self._stop_unlocked()
            if not openseeface_capture_ready(self._portable_root):
                self._status.last_error = "OpenSeeFace add-on not installed"
                return False
            exe = resolve_facetracker_exe(self._portable_root)
            if exe is None:
                self._status.last_error = "facetracker.exe not found"
                return False

            self._camera_index = int(camera_index)
            self._udp_port = int(udp_port)
            self._visualize_level = clamp_osf_visualize_level(visualize_level)
            self._target_fps = clamp_osf_fps(target_fps)
            self._preview_content_width = clamp_osf_capture_width(capture_width)
            self._preview_content_height = clamp_osf_capture_height(capture_height)
            self._preview_placement_key = None
            self._preview_visible = False
            self._state = OpenSeeFaceMocapState()
            self._status = OpenSeeFaceRuntimeStatus()
            self._stopped = False

            cmd = [
                str(exe),
                "-c", str(self._camera_index),
                "-W", str(self._preview_content_width),
                "-H", str(self._preview_content_height),
                "-F", str(self._target_fps),
                "-v", str(self._visualize_level),
                "--ip", "127.0.0.1",
                "--port", str(self._udp_port),
                "--discard-after", "0",
                "--scan-every", "0",
                "--max-feature-updates", "900",
                "--dump-points", "",
            ]
            models_dir = resolve_openseeface_models_dir(self._portable_root)
            if models_dir is not None:
                cmd.extend(["--model-dir", str(models_dir)])
            try:
                self._process = subprocess.Popen(
                    cmd,
                    cwd=str(exe.parent),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **subprocess_hide_window_kwargs(),
                )
            except OSError as exc:
                self._status.last_error = str(exc)
                self._process = None
                return False

            mark_facetracker_camera_in_use(True)
            self._status.process_running = True
            self._udp_thread = threading.Thread(
                target=self._udp_worker,
                daemon=True,
                name="osf-udp")
            self._udp_thread.start()
            self._preview_thread = threading.Thread(
                target=self._preview_worker,
                daemon=True,
                name="osf-preview")
            self._preview_thread.start()
            return True

    def stop(self) -> None:
        with self._stop_lock:
            self._stop_unlocked()

    def _stop_unlocked(self) -> None:
        self._stopped = True
        self.hide_preview_window()
        self._set_preview_hwnd(None)
        if self._udp_socket is not None:
            try:
                self._udp_socket.close()
            except OSError:
                pass
            self._udp_socket = None
        process = self._process
        self._process = None
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                process.kill()
            except OSError:
                pass
        self._status.process_running = False
        self._status.udp_connected = False
        self._status.preview_available = False
        self._preview_placement_key = None
        mark_facetracker_camera_in_use(False)

    def _udp_worker(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", self._udp_port))
        except OSError as exc:
            self._status.last_error = f"UDP bind failed: {exc}"
            sock.close()
            return
        sock.settimeout(0.5)
        self._udp_socket = sock
        try:
            while not self._stopped:
                try:
                    packet, _addr = sock.recvfrom(8192)
                except socket.timeout:
                    if (
                            self._state.packets_received > 0
                            and time.monotonic() - self._state.last_packet_mono > OSF_UDP_DISCONNECT_SEC):
                        self._state.udp_connected = False
                        self._status.udp_connected = False
                    continue
                except OSError:
                    break
                frame = parse_openseeface_udp_packet(packet)
                if frame is None:
                    continue
                pose = build_openseeface_mediapipe_face_pose(frame, self._state)
                self._status.udp_connected = True
                self._status.packets_received = self._state.packets_received
                callback = self._pose_callback
                if callback is not None:
                    try:
                        callback(pose)
                    except Exception:
                        pass
        finally:
            try:
                sock.close()
            except OSError:
                pass
            if self._udp_socket is sock:
                self._udp_socket = None

    def _note_facetracker_process_exited(self, *, reason: str = "") -> None:
        """Mark process dead and release the in-process camera claim.

        facetracker may exit without going through stop(); leaving
        facetracker_camera_in_use set blocks camera re-enumeration forever.
        """
        self._status.process_running = False
        if reason:
            self._status.last_error = reason
        mark_facetracker_camera_in_use(False)

    def _preview_worker(self) -> None:
        process = self._process
        if process is None:
            return
        hwnd: Optional[int] = None
        deadline = time.monotonic() + OSF_PREVIEW_HWND_TIMEOUT_SEC
        while not self._stopped and time.monotonic() < deadline:
            if process.poll() is not None:
                self._note_facetracker_process_exited(reason="facetracker exited early")
                return
            hwnd = wait_for_openseeface_preview_hwnd(
                process.pid,
                poll_sec=OSF_PREVIEW_HWND_POLL_SEC,
                timeout_sec=OSF_PREVIEW_HWND_POLL_SEC,
            )
            if hwnd is not None:
                break
            time.sleep(0.2)

        if hwnd is None:
            self._status.preview_status = "Waiting for OpenSeeFace preview window..."
        self._set_preview_hwnd(hwnd)
        self._status.preview_status = "Preview ready"
        self._state.preview_status = self._status.preview_status

        while not self._stopped:
            if process.poll() is not None:
                self._note_facetracker_process_exited()
                self._status.preview_available = False
                self._status.preview_status = "facetracker stopped"
                self._state.preview_lost = True
                self._set_preview_hwnd(None)
                break
            cached = self.get_preview_hwnd()
            if cached is not None and user32.IsWindow(wintypes.HWND(int(cached))):
                time.sleep(max(0.5, self._capture_interval_sec))
                continue
            rediscovered = resolve_openseeface_preview_hwnd(process.pid)
            if rediscovered is not None:
                self._set_preview_hwnd(rediscovered)
                self._status.preview_available = True
                self._status.preview_status = "Preview mirroring"
                self._state.preview_lost = False
                self._state.preview_status = self._status.preview_status
            else:
                self._status.preview_available = False
                self._status.preview_status = "Preview window lost"
                self._state.preview_lost = True
                self._set_preview_hwnd(None)
                self.hide_preview_window()
            time.sleep(max(0.5, self._capture_interval_sec))
