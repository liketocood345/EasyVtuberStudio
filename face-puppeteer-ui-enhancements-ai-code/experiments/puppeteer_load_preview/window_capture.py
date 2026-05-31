"""
Capture a Windows window client area as BGR frames (OBS-style).

Priority (occlusion-safe, no need to keep target window on top):
1. PrintWindow(PW_RENDERFULLCONTENT | PW_CLIENTONLY) — DWM full content when covered
2. GetDC(hwnd) + BitBlt — same path as OBS "BitBlt" window capture
3. Screen BitBlt — last resort only
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import List, Optional, Tuple

import cv2
import numpy

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

PW_CLIENTONLY = 0x00000001
PW_RENDERFULLCONTENT = 0x00000002
PW_CLIENT_RENDER = PW_CLIENTONLY | PW_RENDERFULLCONTENT
SRCCOPY = 0x00CC0020

_dpi_awareness_set = False
_prototypes_initialized = False


def _init_win32_prototypes() -> None:
    global _prototypes_initialized
    if _prototypes_initialized:
        return
    _prototypes_initialized = True

    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.PrintWindow.restype = wintypes.BOOL

    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.BitBlt.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
    ]
    gdi32.BitBlt.restype = wintypes.BOOL
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
        wintypes.LPVOID, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
    ]
    gdi32.GetDIBits.restype = ctypes.c_int
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL


def _as_hwnd(hwnd: int) -> wintypes.HWND:
    return wintypes.HWND(int(hwnd))


def _as_hdc(hdc) -> wintypes.HDC:
    return wintypes.HDC(int(hdc))


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


class WindowInfo:
    __slots__ = ("hwnd", "title")

    def __init__(self, hwnd: int, title: str):
        self.hwnd = int(hwnd)
        self.title = title


def _ensure_dpi_awareness() -> None:
    global _dpi_awareness_set
    _init_win32_prototypes()
    if _dpi_awareness_set:
        return
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
    _dpi_awareness_set = True


def _set_capture_thread_dpi_for_window(hwnd: int) -> Optional[object]:
    """Match OBS: align capture thread DPI with target window when API exists."""
    try:
        get_window_ctx = user32.GetWindowDpiAwarenessContext
        set_thread_ctx = user32.SetThreadDpiAwarenessContext
    except AttributeError:
        return None
    try:
        window_ctx = get_window_ctx(wintypes.HWND(int(hwnd)))
        if window_ctx:
            return set_thread_ctx(window_ctx)
    except Exception:
        pass
    return None


def _restore_thread_dpi(previous: object) -> None:
    if previous is None:
        return
    try:
        user32.SetThreadDpiAwarenessContext(previous)
    except Exception:
        pass


def is_window_valid(hwnd: int) -> bool:
    if not hwnd:
        return False
    try:
        return bool(user32.IsWindow(wintypes.HWND(int(hwnd))))
    except Exception:
        return False


def get_window_title(hwnd: int) -> str:
    if not is_window_valid(hwnd):
        return ""
    length = user32.GetWindowTextLengthW(wintypes.HWND(int(hwnd)))
    if length <= 0:
        return ""
    buff = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(wintypes.HWND(int(hwnd)), buff, length + 1)
    return buff.value.strip()


def _client_size(hwnd: int) -> Tuple[int, int]:
    client_rect = wintypes.RECT()
    if not user32.GetClientRect(wintypes.HWND(int(hwnd)), ctypes.byref(client_rect)):
        return 0, 0
    return int(client_rect.right - client_rect.left), int(client_rect.bottom - client_rect.top)


def _client_screen_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    hwnd = int(hwnd)
    width, height = _client_size(hwnd)
    if width < 2 or height < 2:
        return None
    origin = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(wintypes.HWND(hwnd), ctypes.byref(origin)):
        return None
    left = int(origin.x)
    top = int(origin.y)
    return left, top, left + width, top + height


def _hdc_bitmap_to_bgr(hdc_mem, hbmp, width: int, height: int) -> Optional[numpy.ndarray]:
    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = 0

    buffer_size = width * height * 4
    buffer = ctypes.create_string_buffer(buffer_size)
    lines = gdi32.GetDIBits(
        _as_hdc(hdc_mem), wintypes.HBITMAP(int(hbmp)), 0, height, buffer, ctypes.byref(bmi), 0)
    if lines == 0:
        return None
    bgra = numpy.frombuffer(buffer, dtype=numpy.uint8).reshape((height, width, 4))
    return cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)


def _capture_with_hdc_bitblt(hdc_source, width: int, height: int,
                             src_x: int = 0, src_y: int = 0) -> Optional[numpy.ndarray]:
    hdc_screen = user32.GetDC(wintypes.HWND(0))
    if not hdc_screen:
        return None
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    old = gdi32.SelectObject(hdc_mem, hbmp)
    try:
        ok = gdi32.BitBlt(
            hdc_mem, 0, 0, width, height,
            _as_hdc(hdc_source), src_x, src_y, SRCCOPY)
        if not ok:
            return None
        return _hdc_bitmap_to_bgr(hdc_mem, hbmp, width, height)
    finally:
        gdi32.SelectObject(hdc_mem, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(wintypes.HWND(0), hdc_screen)


def _capture_print_window_client(hwnd: int, width: int, height: int) -> Optional[numpy.ndarray]:
    """OBS/WGC fallback for hardware-accelerated or occluded windows."""
    hwnd_w = _as_hwnd(hwnd)
    hdc_screen = user32.GetDC(wintypes.HWND(0))
    if not hdc_screen:
        return None
    hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
    hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
    old = gdi32.SelectObject(hdc_mem, hbmp)
    try:
        ok = user32.PrintWindow(
            hwnd_w,
            hdc_mem,
            PW_CLIENT_RENDER,
        )
        if not ok:
            ok = user32.PrintWindow(
                hwnd_w,
                hdc_mem,
                PW_RENDERFULLCONTENT,
            )
        if not ok:
            return None
        return _hdc_bitmap_to_bgr(hdc_mem, hbmp, width, height)
    finally:
        gdi32.SelectObject(hdc_mem, old)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(wintypes.HWND(0), hdc_screen)


def _capture_obs_window_dc_bitblt(hwnd: int, width: int, height: int) -> Optional[numpy.ndarray]:
    """Same as OBS dc_capture_capture: BitBlt from GetDC(window), not from screen."""
    hwnd_w = _as_hwnd(hwnd)
    hdc_window = user32.GetDC(hwnd_w)
    if not hdc_window:
        return None
    try:
        return _capture_with_hdc_bitblt(hdc_window, width, height, 0, 0)
    finally:
        user32.ReleaseDC(hwnd_w, hdc_window)


def _capture_screen_bitblt(hwnd: int, width: int, height: int) -> Optional[numpy.ndarray]:
    rect = _client_screen_rect(hwnd)
    if rect is None:
        return None
    left, top, _, _ = rect
    hdc_screen = user32.GetDC(wintypes.HWND(0))
    if not hdc_screen:
        return None
    try:
        return _capture_with_hdc_bitblt(hdc_screen, width, height, left, top)
    finally:
        user32.ReleaseDC(wintypes.HWND(0), hdc_screen)


def _frame_mean_luma(bgr: numpy.ndarray) -> float:
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return float(gray.mean())


def list_capture_targets() -> List[WindowInfo]:
    """Visible top-level windows with non-empty titles."""
    results: List[WindowInfo] = []

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.IsIconic(hwnd):
            return True
        title = get_window_title(int(hwnd))
        if not title:
            return True
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width < 80 or height < 80:
            return True
        results.append(WindowInfo(int(hwnd), title))
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    results.sort(key=lambda item: item.title.lower())
    return results


def capture_window_client_bgr(hwnd: int) -> Optional[numpy.ndarray]:
    """
    Grab the window client area as BGR.

    Does not require the target window to be top-most; uses PrintWindow full
    content first, then OBS-style window-DC BitBlt.
    """
    hwnd = int(hwnd)
    if not is_window_valid(hwnd):
        return None

    _ensure_dpi_awareness()
    previous_dpi = _set_capture_thread_dpi_for_window(hwnd)
    try:
        width, height = _client_size(hwnd)
        if width < 2 or height < 2:
            return None

        methods = (
            _capture_print_window_client,
            _capture_obs_window_dc_bitblt,
            lambda h, w, ht: _capture_screen_bitblt(h, w, ht),
        )
        best: Optional[numpy.ndarray] = None
        best_score = -1.0
        for method in methods:
            try:
                frame = method(hwnd, width, height)
            except Exception:
                continue
            if frame is None:
                continue
            score = _frame_mean_luma(frame)
            if score > best_score:
                best = frame
                best_score = score
            if score >= 4.0:
                return frame
        return best
    finally:
        _restore_thread_dpi(previous_dpi)
