"""OpenSeeFace subprocess, UDP receiver, and preview window capture."""
from __future__ import annotations
from portable_process_env import debug_log_path
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

import atexit
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
    get_workspace_dir,
    openseeface_capture_ready,
    resolve_facetracker_exe,
    resolve_openseeface_models_dir,
)

_FACETRACKER_LOG_MAX_BYTES = 1_000_000

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


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.SetInformationJobObject.argtypes = [
    wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
kernel32.SetInformationJobObject.restype = wintypes.BOOL
kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.restype = wintypes.BOOL

PROCESS_TERMINATE = 0x0001
PROCESS_SET_QUOTA = 0x0100
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TH32CS_SNAPPROCESS = 0x00000002
JobObjectExtendedLimitInformation = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

_FACETRACKER_JOB = None
_LIVE_OSF_RUNTIMES: List["OpenSeeFaceRuntime"] = []


class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32W)]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _query_process_image(pid: int) -> Optional[str]:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
        return None
    finally:
        kernel32.CloseHandle(handle)


def _terminate_pid(pid: int) -> bool:
    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if not handle:
        return False
    try:
        return bool(kernel32.TerminateProcess(handle, 1))
    finally:
        kernel32.CloseHandle(handle)


def _iter_process_ids_and_parents():
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == INVALID_HANDLE_VALUE:
        return
    try:
        entry = _PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(_PROCESSENTRY32W)
        more = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            yield int(entry.th32ProcessID), int(entry.th32ParentProcessID)
            more = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)


# bh-2 26.10.29 22:27 s
def _kill_orphaned_facetrackers(exe: Path, keep_pid: Optional[int] = None) -> List[int]:
    """Kill facetracker.exe copies of this add-on whose parent is already dead."""
    if os.name != "nt" or exe is None:
        return []
    try:
        target = str(exe.resolve()).lower()
    except OSError:
        target = str(exe).lower()
    killed: List[int] = []
    our_pid = os.getpid()
    for pid, ppid in _iter_process_ids_and_parents():
        if pid <= 0 or pid == keep_pid:
            continue
        image = _query_process_image(pid)
        if not image or image.lower() != target:
            continue
        parent_dead = not _pid_alive(ppid)
        parent_is_us = ppid == our_pid
        if not parent_dead and not parent_is_us:
            continue
        if _terminate_pid(pid):
            killed.append(pid)
    # #region agent log
    try:
        import json as _json
        open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({
            "sessionId": "86a17c",
            "runId": "post-fix-osf-orphan",
            "hypothesisId": "V",
            "location": "openseeface_runtime.py:_kill_orphaned_facetrackers",
            "message": "osf orphan facetracker sweep",
            "data": {"exe": target[-80:], "keep_pid": keep_pid, "killed": killed, "our_pid": our_pid},
            "timestamp": int(time.time() * 1000),
        }) + "\n")
    except Exception:
        pass
    # #endregion
    return killed


def _ensure_kill_on_close_job():
    global _FACETRACKER_JOB
    if os.name != "nt":
        return None
    if _FACETRACKER_JOB:
        return _FACETRACKER_JOB
    handle = kernel32.CreateJobObjectW(None, None)
    if not handle:
        return None
    info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(
            handle, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)):
        kernel32.CloseHandle(handle)
        return None
    _FACETRACKER_JOB = handle
    return handle


def _assign_pid_to_kill_on_close_job(pid: int) -> bool:
    job = _ensure_kill_on_close_job()
    if not job or pid <= 0:
        return False
    handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
    if not handle:
        return False
    try:
        ok = bool(kernel32.AssignProcessToJobObject(job, handle))
        winerr = int(ctypes.get_last_error())
        # #region agent log
        try:
            import json as _json
            open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({
                "sessionId": "86a17c",
                "runId": "post-fix-osf-orphan",
                "hypothesisId": "W",
                "location": "openseeface_runtime.py:_assign_pid_to_kill_on_close_job",
                "message": "osf facetracker job assign",
                "data": {"pid": int(pid), "ok": bool(ok), "winerr": winerr},
                "timestamp": int(time.time() * 1000),
            }) + "\n")
        except Exception:
            pass
        # #endregion
        return ok
    finally:
        kernel32.CloseHandle(handle)


def _close_kill_on_close_job() -> None:
    global _FACETRACKER_JOB
    handle = _FACETRACKER_JOB
    _FACETRACKER_JOB = None
    if handle:
        kernel32.CloseHandle(handle)


def _atexit_stop_facetrackers() -> None:
    # #region agent log
    try:
        import json as _json
        open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({
            "sessionId": "86a17c",
            "runId": "post-fix-osf-orphan",
            "hypothesisId": "X",
            "location": "openseeface_runtime.py:_atexit_stop_facetrackers",
            "message": "osf atexit stop",
            "data": {"live": len(_LIVE_OSF_RUNTIMES)},
            "timestamp": int(time.time() * 1000),
        }) + "\n")
    except Exception:
        pass
    # #endregion
    for runtime in list(_LIVE_OSF_RUNTIMES):
        try:
            runtime.stop()
        except Exception:
            pass
    _close_kill_on_close_job()


atexit.register(_atexit_stop_facetrackers)
# bh-2 26.10.29 22:27 e


user32 = ctypes.windll.user32

_win32_preview_prototypes_initialized = False
_get_window_long = user32.GetWindowLongW
_set_window_long = user32.SetWindowLongW


def _init_win32_preview_prototypes() -> None:
    global _win32_preview_prototypes_initialized, _get_window_long, _set_window_long
    if _win32_preview_prototypes_initialized:
        return
    _win32_preview_prototypes_initialized = True
    if ctypes.sizeof(ctypes.c_void_p) == 8:
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongPtrW.restype = ctypes.c_longlong
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_longlong]
        user32.SetWindowLongPtrW.restype = ctypes.c_longlong
        _get_window_long = user32.GetWindowLongPtrW
        _set_window_long = user32.SetWindowLongPtrW
    else:
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        user32.SetWindowLongW.restype = ctypes.c_long
        _get_window_long = user32.GetWindowLongW
        _set_window_long = user32.SetWindowLongW
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
    user32.GetParent.argtypes = [wintypes.HWND]
    user32.GetParent.restype = wintypes.HWND
    user32.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
    user32.SetParent.restype = wintypes.HWND


_init_win32_preview_prototypes()

GWL_STYLE = -16
GWL_EXSTYLE = -20
HWND_TOP = 0
HWND_BOTTOM = 1
SW_HIDE = 0
SW_SHOW = 5
SW_SHOWNA = 8
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOZORDER = 0x0004
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_FRAMECHANGED = 0x0020
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000
WS_VISIBLE = 0x10000000
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000


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
        self._preview_embed_parent = 0
        self._target_fps = OSF_DEFAULT_FPS
        self._state = OpenSeeFaceMocapState()
        self._status = OpenSeeFaceRuntimeStatus()
        self._pose_callback: Optional[Callable[[object], None]] = None
        self._camera_index = 0
        self._udp_port = OSF_DEFAULT_UDP_PORT
        self._visualize_level = OSF_VISUALIZE_DEFAULT
        self._facetracker_log_handle = None
        self._facetracker_log_path: Optional[Path] = None
        # bh-2 26.10.29 22:27 s
        if self not in _LIVE_OSF_RUNTIMES:
            _LIVE_OSF_RUNTIMES.append(self)
        _ensure_kill_on_close_job()
        exe = resolve_facetracker_exe(self._portable_root)
        if exe is not None:
            _kill_orphaned_facetrackers(exe)
        # bh-2 26.10.29 22:27 e

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
            if hwnd:
                try:
                    if user32.IsWindow(wintypes.HWND(int(hwnd))):
                        user32.ShowWindow(wintypes.HWND(int(hwnd)), SW_HIDE)
                except OSError:
                    pass
            self._preview_visible = False
            self._preview_placement_key = None

    def _ensure_preview_embedded(self, hwnd: int, parent_hwnd: int) -> bool:
        # bh-5 26.10.29 20:56 s
        if parent_hwnd <= 0 or hwnd <= 0:
            return False
        window = wintypes.HWND(int(hwnd))
        parent = wintypes.HWND(int(parent_hwnd))
        try:
            current = int(user32.GetParent(window) or 0)
            if current != int(parent_hwnd):
                user32.SetParent(window, parent)
            style = int(_get_window_long(window, GWL_STYLE))
            style = (
                (style | WS_CHILD | WS_VISIBLE)
                & ~WS_POPUP & ~WS_CAPTION & ~WS_THICKFRAME & ~WS_SYSMENU
            )
            _set_window_long(window, GWL_STYLE, style)
            ex_style = int(_get_window_long(window, GWL_EXSTYLE))
            ex_style = (ex_style | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE) & ~WS_EX_APPWINDOW
            _set_window_long(window, GWL_EXSTYLE, ex_style)
            user32.SetWindowPos(
                window,
                wintypes.HWND(HWND_TOP),
                0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)
            self._preview_embed_parent = int(user32.GetParent(window) or 0)
            return self._preview_embed_parent == int(parent_hwnd)
        except (OSError, OverflowError, ValueError, TypeError):
            return False
        # bh-5 26.10.29 20:56 e

    def sync_preview_window_placement(
            self,
            *,
            screen_x: int,
            screen_y: int,
            box_width: int,
            box_height: int,
            content_width: Optional[int] = None,
            content_height: Optional[int] = None,
            parent_hwnd: Optional[int] = None) -> bool:
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
            embed_parent = int(parent_hwnd or 0)
            if embed_parent > 0:
                self._ensure_preview_embedded(int(hwnd), embed_parent)
                outer_w, outer_h = client_w, client_h
            else:
                outer_w, outer_h = window_outer_size_for_client(hwnd, client_w, client_h)
            placement_key = (target_x, target_y, outer_w, outer_h, embed_parent)
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
                actual_parent = 0
                try:
                    actual_parent = int(user32.GetParent(wintypes.HWND(int(hwnd))) or 0)
                except (OSError, OverflowError, ValueError, TypeError):
                    actual_parent = 0
                # #region agent log
                try:
                    import json as _json, time as _time
                    open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({"sessionId": "86a17c", "runId": "post-fix", "hypothesisId": "D", "location": "openseeface_runtime.py:sync_preview_window_placement", "message": "osf preview dock attempt", "data": {"ok": bool(ok), "hwnd": int(hwnd), "parent": int(actual_parent), "want_parent": int(embed_parent), "pos": [int(target_x), int(target_y), int(outer_w), int(outer_h)]}, "timestamp": int(_time.time() * 1000)}) + "\n")
                except Exception:
                    pass
                # #endregion
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

    def _close_facetracker_log(self) -> None:
        handle = self._facetracker_log_handle
        self._facetracker_log_handle = None
        if handle is None:
            return
        try:
            handle.close()
        except OSError:
            pass

    def _open_facetracker_log(self):
        # bh-5 26.10.29 19:40 s
        workspace = get_workspace_dir(self._portable_root)
        log_dir = workspace / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / "facetracker.err.log"
        try:
            if path.is_file() and path.stat().st_size > _FACETRACKER_LOG_MAX_BYTES:
                bak = log_dir / "facetracker.err.log.1"
                if bak.exists():
                    bak.unlink()
                path.replace(bak)
        except OSError:
            pass
        self._facetracker_log_path = path
        # bh-5 26.10.30 11:20 s
        handle = path.open("wb")
        # bh-5 26.10.30 11:20 e
        self._facetracker_log_handle = handle
        # bh-5 26.10.29 19:40 e
        return handle

    def _facetracker_log_tail(self, n: int = 8) -> str:
        path = self._facetracker_log_path
        if path is None or not path.is_file():
            return ""
        # bh-2 26.10.29 20:24 s
        try:
            size = path.stat().st_size
            with path.open("rb") as handle:
                if size > 8192:
                    handle.seek(size - 8192)
                data = handle.read()
            text = data.decode("utf-8", errors="replace")
        except OSError:
            return ""
        # bh-2 26.10.29 20:24 e
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return " | ".join(lines[-max(1, n):])

    def refresh_process_status(self) -> None:
        process = self._process
        if process is None:
            self._status.process_running = False
            return
        if process.poll() is not None:
            self._note_facetracker_process_exited(reason="facetracker exited")

    def facetracker_capture_open_failed(self) -> bool:
        # bh-5 26.10.30 11:20 s
        handle = self._facetracker_log_handle
        if handle is not None:
            try:
                handle.flush()
            except OSError:
                pass
        tail = self._facetracker_log_tail(20)
        if not tail:
            return False
        return "There was no valid input" in tail or "Failed to start capture" in tail
        # bh-5 26.10.30 11:20 e

    # EVS-DESIGN-AUDIT EVS-A069 BEGIN
    # 设计[f-052, f-057] [符合（stderr 落盘）]
    # 内置 facetracker 进程 stdout/stderr 写入 workspace/logs/facetracker.err.log；早退时把末行并入 last_error。
    # 历史 bug 热点 #2,#5：不再把 facetracker 输出丢到 DEVNULL。
    # EVS-DESIGN-AUDIT EVS-A069 END
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
            # bh-5 26.10.30 12:52 s
            self._visualize_level = 0
            # bh-5 26.10.30 12:52 e
            self._target_fps = clamp_osf_fps(target_fps)
            self._preview_content_width = clamp_osf_capture_width(capture_width)
            self._preview_content_height = clamp_osf_capture_height(capture_height)
            self._preview_placement_key = None
            self._preview_visible = False
            self._preview_embed_parent = 0
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
            # bh-2 26.10.29 22:27 s
            _kill_orphaned_facetrackers(exe)
            # bh-2 26.10.29 22:27 e
            try:
                log_handle = self._open_facetracker_log()
                self._process = subprocess.Popen(
                    cmd,
                    cwd=str(exe.parent),
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    **subprocess_hide_window_kwargs(),
                )
            except OSError as exc:
                self._status.last_error = str(exc)
                self._process = None
                self._close_facetracker_log()
                return False

            mark_facetracker_camera_in_use(True)
            self._status.process_running = True
            # bh-2 26.10.29 22:27 s
            child_pid = int(getattr(self._process, "pid", 0) or 0)
            _assign_pid_to_kill_on_close_job(child_pid)
            # bh-2 26.10.29 22:27 e
            self._udp_thread = threading.Thread(
                target=self._udp_worker,
                daemon=True,
                name="osf-udp")
            self._udp_thread.start()
            # bh-5 26.10.30 12:52 s
            if int(self._visualize_level) > 0:
                self._preview_thread = threading.Thread(
                    target=self._preview_worker,
                    daemon=True,
                    name="osf-preview")
                self._preview_thread.start()
            # bh-5 26.10.30 12:52 e
            # #region agent log
            try:
                import json as _json, time as _time
                open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({"sessionId": "86a17c", "runId": "post-fix", "hypothesisId": "A", "location": "openseeface_runtime.py:start", "message": "osf facetracker started", "data": {"pid": int(getattr(self._process, "pid", 0) or 0), "visualize": int(self._visualize_level), "camera": int(self._camera_index), "size": [int(self._preview_content_width), int(self._preview_content_height)]}, "timestamp": int(_time.time() * 1000)}) + "\n")
            except Exception:
                pass
            # #endregion
            return True

    def stop(self) -> None:
        with self._stop_lock:
            self._stop_unlocked()

    # EVS-DESIGN-AUDIT EVS-A067 BEGIN
    # 设计[f-052, f-068] [符合（join/kill-wait）]
    # 关闭 socket 并 terminate、wait(3s)，超时 kill 后再 wait，并 join UDP/预览 worker。facetracker 进 JobObject（KILL_ON_JOB_CLOSE），父进程被杀时子进程一并退出。
    # 历史 bug 热点 #2,#5：stop 路径补 join 与二次 wait。
    # EVS-DESIGN-AUDIT EVS-A067 END
    def _stop_unlocked(self) -> None:
        self._stopped = True
        # bh-2 26.10.29 20:24 s
        # Do not ShowWindow a possibly hung facetracker HWND; just drop the handle.
        self._preview_visible = False
        self._preview_placement_key = None
        self._preview_embed_parent = 0
        self._set_preview_hwnd(None)
        # bh-2 26.10.29 20:24 e
        if self._udp_socket is not None:
            try:
                self._udp_socket.close()
            except OSError:
                pass
            self._udp_socket = None
        process = self._process
        self._process = None
        udp_thread = self._udp_thread
        preview_thread = self._preview_thread
        self._udp_thread = None
        self._preview_thread = None
        # bh-2 26.10.29 19:40 s
        if process is not None:
            try:
                process.terminate()
                process.wait(timeout=3.0)
            except subprocess.TimeoutExpired:
                try:
                    process.kill()
                    process.wait(timeout=1.0)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            except OSError:
                pass
        if udp_thread is not None:
            udp_thread.join(timeout=1.0)
        if preview_thread is not None:
            preview_thread.join(timeout=1.0)
        self._close_facetracker_log()
        # bh-2 26.10.29 19:40 e
        # bh-2 26.10.29 22:27 s
        exe = resolve_facetracker_exe(self._portable_root)
        if exe is not None:
            _kill_orphaned_facetrackers(exe)
        # bh-2 26.10.29 22:27 e
        self._status.process_running = False
        self._status.udp_connected = False
        self._status.preview_available = False
        self._preview_placement_key = None
        mark_facetracker_camera_in_use(False)

    # EVS-DESIGN-AUDIT EVS-A068 BEGIN
    # 设计[f-052, f-064] [符合（上层消费包龄）]
    # 五秒断流会置 udp_connected=False；上层健康检查与 pacer 按 last_packet_mono 过期，不再把旧 motion 当 LIVE。
    # 历史 bug 热点 #2,#3,#5：断流状态已贯通到 pacer/健康检查。
    # EVS-DESIGN-AUDIT EVS-A068 END
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
        handle = self._facetracker_log_handle
        if handle is not None:
            try:
                handle.flush()
            except OSError:
                pass
        tail = self._facetracker_log_tail()
        if reason:
            if tail:
                self._status.last_error = f"{reason}: {tail}"
            else:
                self._status.last_error = reason
        elif tail:
            self._status.last_error = tail
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
        if hwnd is not None:
            try:
                user32.ShowWindow(wintypes.HWND(int(hwnd)), SW_HIDE)
            except OSError:
                pass
            self._preview_visible = False
            # #region agent log
            try:
                import json as _json, time as _time
                open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({"sessionId": "86a17c", "runId": "post-fix-source-preview", "hypothesisId": "H", "location": "openseeface_runtime.py:_preview_worker", "message": "osf preview hwnd hidden", "data": {"hwnd": int(hwnd), "visualize": int(self._visualize_level)}, "timestamp": int(_time.time() * 1000)}) + "\n")
            except Exception:
                pass
            # #endregion

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
                try:
                    user32.ShowWindow(wintypes.HWND(int(cached)), SW_HIDE)
                except OSError:
                    pass
                self._preview_visible = False
                time.sleep(max(0.5, self._capture_interval_sec))
                continue
            rediscovered = resolve_openseeface_preview_hwnd(process.pid)
            if rediscovered is not None:
                self._set_preview_hwnd(rediscovered)
                try:
                    user32.ShowWindow(wintypes.HWND(int(rediscovered)), SW_HIDE)
                except OSError:
                    pass
                self._preview_visible = False
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
