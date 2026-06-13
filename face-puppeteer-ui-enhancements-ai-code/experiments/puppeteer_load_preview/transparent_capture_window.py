"""Unified output window: single layered (per-pixel alpha) desktop overlay (ULW).

This module is wx-free. The ULW (titled ``easyvtuberstudio_output``) is now the
sole on-screen output + editing surface for *every* background mode: 真透 keeps
per-pixel alpha for desktop-transparent output, while color/image/黑键 composite
an opaque background plate into the same window. The wx OutputFrame is retired as
an output surface. The window is a lone WS_EX_LAYERED popup driven by
UpdateLayeredWindow; capture tools grab it via Windows Graphics Capture / game
capture (with "allow transparency" for 真透, or colour-key #000000 for 黑键).
Note: a layered window cannot be captured by legacy BitBlt window-capture, so
BitBlt-only tools must use WGC instead.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import Callable, Optional, Tuple

import numpy

_DEBUG_ERR_LOG_PATH = r"e:\debug-3353ed.log"


def _capture_window_err_record(location: str, exc: BaseException) -> None:
    # #region agent log
    try:
        import json
        import time
        import traceback
        with open(_DEBUG_ERR_LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps({
                "sessionId": "3353ed",
                "runId": "err",
                "hypothesisId": "H-CAP-WIN",
                "location": location,
                "message": repr(exc),
                "data": {"traceback": traceback.format_exc()[:2000]},
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion

try:
    from window_capture import _ensure_dpi_awareness
except ImportError:
    def _ensure_dpi_awareness() -> None:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

WINDOW_TITLE = "easyvtuberstudio_output"
WINDOW_CLASS_NAME = "THA4TransparentCaptureWindow"

WM_DESTROY = 0x0002
WM_NCHITTEST = 0x0084
WM_WINDOWPOSCHANGED = 0x0047
WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_KEYDOWN = 0x0100
WM_SETCURSOR = 0x0020
WM_SETICON = 0x0080
WM_ACTIVATE = 0x0006
WA_INACTIVE = 0

ICON_SMALL = 0
ICON_BIG = 1
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x00000010
LR_DEFAULTSIZE = 0x00000040

# Same artwork the packaged EasyVtuberStudio.exe uses for its icon.
APP_ICON_RELPATH = os.path.join("assets", "branding", "app-icon-source.ico")

HTCAPTION = 2
HTCLIENT = 1

MK_LBUTTON = 0x0001

VK_SHIFT = 0x10
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28

IDC_ARROW = 32512

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000

# Decorative identification border drawn around the transparent output. It lives
# in its own click-through, no-taskbar window so the streamed ULW stays clean
# (capture software targets the ULW by title; this frame is never the target).
BORDER_THICKNESS_PX = 4
BORDER_COLOR_RGBA = (0, 200, 255, 235)

GWL_EXSTYLE = -20
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020

LWA_COLORKEY = 0x00000001
COLORKEY_BLACK = 0x000000
HWND_BOTTOM = 1

ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
BI_RGB = 0
DIB_RGB_COLORS = 0

SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = -1

GeometryCallback = Callable[[], None]
PositionCallback = Callable[[int, int], None]
# Returns True if the click started a layer edit (overlay should not drag window).
EditBeginCallback = Callable[[int, int], bool]
EditMotionCallback = Callable[[int, int], None]
EditEndCallback = Callable[[], None]
# Returns True if the arrow key nudged a layer (overlay consumed the key).
KeyNudgeCallback = Callable[[float, float], bool]
# Fired when the overlay window loses activation (user clicked away from it).
DeactivateCallback = Callable[[], None]

LRESULT = ctypes.c_ssize_t
_WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


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


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", wintypes.BYTE),
        ("BlendFlags", wintypes.BYTE),
        ("SourceConstantAlpha", wintypes.BYTE),
        ("AlphaFormat", wintypes.BYTE),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


_overlay_instances: dict[int, "_DesktopOverlayWindow"] = {}
_overlay_wndproc_ref = None
_overlay_class_registered = False
_prototypes_initialized = False

def _raise_overlay_topmost(overlay_hwnd: int) -> None:
    if not overlay_hwnd:
        return
    user32.SetWindowPos(
        wintypes.HWND(int(overlay_hwnd)),
        wintypes.HWND(HWND_TOPMOST),
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
    )


def _init_win32_prototypes() -> None:
    global _prototypes_initialized
    if _prototypes_initialized:
        return

    user32.UpdateLayeredWindow.restype = wintypes.BOOL
    user32.UpdateLayeredWindow.argtypes = [
        wintypes.HWND,
        wintypes.HDC,
        ctypes.POINTER(POINT),
        ctypes.POINTER(SIZE),
        wintypes.HDC,
        ctypes.POINTER(POINT),
        wintypes.COLORREF,
        ctypes.POINTER(BLENDFUNCTION),
        wintypes.DWORD,
    ]

    user32.ShowWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]

    user32.SetWindowPos.restype = wintypes.BOOL
    user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]

    user32.IsWindow.restype = wintypes.BOOL
    user32.IsWindow.argtypes = [wintypes.HWND]

    user32.DestroyWindow.restype = wintypes.BOOL
    user32.DestroyWindow.argtypes = [wintypes.HWND]

    user32.DefWindowProcW.restype = LRESULT
    user32.DefWindowProcW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    user32.RegisterClassW.restype = wintypes.ATOM
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]

    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]

    gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC,
        ctypes.POINTER(BITMAPINFO),
        wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.HANDLE,
        wintypes.DWORD,
    ]

    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]

    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]

    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]

    gdi32.DeleteDC.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [wintypes.HDC]

    # HANDLE/HICON must not be truncated to c_int on 64-bit.
    user32.LoadImageW.restype = wintypes.HANDLE
    user32.LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    user32.SendMessageW.restype = LRESULT
    user32.SendMessageW.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetForegroundWindow.argtypes = []

    _prototypes_initialized = True


def _straight_rgba_to_premultiplied_bgra(rgba: numpy.ndarray) -> numpy.ndarray:
    rgba = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError(f"expected HxWx4 RGBA, got {rgba.shape}")
    alpha = rgba[:, :, 3:4].astype(numpy.float32) / 255.0
    rgb = rgba[:, :, 0:3].astype(numpy.float32) * alpha
    bgra = numpy.empty_like(rgba)
    bgra[:, :, 0] = numpy.clip(rgb[:, :, 2], 0.0, 255.0).astype(numpy.uint8)
    bgra[:, :, 1] = numpy.clip(rgb[:, :, 1], 0.0, 255.0).astype(numpy.uint8)
    bgra[:, :, 2] = numpy.clip(rgb[:, :, 0], 0.0, 255.0).astype(numpy.uint8)
    bgra[:, :, 3] = rgba[:, :, 3]
    return numpy.ascontiguousarray(bgra)


def _resolve_app_icon_path() -> Optional[str]:
    """Walk up from this module looking for the bundled app icon (same artwork
    the packaged exe uses). Returns None if not present (e.g. icon not deployed)."""
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        candidate = os.path.join(cur, APP_ICON_RELPATH)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def _build_border_ring_rgba(
        width: int,
        height: int,
        thickness: int,
        color_rgba: Tuple[int, int, int, int]) -> numpy.ndarray:
    """Opaque ring of `thickness` px around a fully transparent interior. The
    interior matches the ULW footprint so the output shows through unobstructed."""
    width = max(1, int(width))
    height = max(1, int(height))
    t = max(1, int(thickness))
    r, g, b, a = color_rgba
    out = numpy.zeros((height, width, 4), dtype=numpy.uint8)
    out[:, :, 0] = r
    out[:, :, 1] = g
    out[:, :, 2] = b
    out[:t, :, 3] = a
    out[height - t:, :, 3] = a
    out[:, :t, 3] = a
    out[:, width - t:, 3] = a
    return numpy.ascontiguousarray(out, dtype=numpy.uint8)


class _DesktopOverlayWindow:
    """Layered popup for true desktop alpha; hidden from window capture lists."""

    _OVERLAY_CLASS = "THA4TransparentCaptureOverlay"

    def __init__(
            self,
            width: int,
            height: int,
            *,
            exstyle: int = WS_EX_LAYERED | WS_EX_APPWINDOW,
            window_title: str = WINDOW_TITLE,
            icon_path: Optional[str] = None,
            on_position_changed: Optional[PositionCallback] = None,
            on_edit_begin: Optional[EditBeginCallback] = None,
            on_edit_motion: Optional[EditMotionCallback] = None,
            on_edit_end: Optional[EditEndCallback] = None,
            on_key_nudge: Optional[KeyNudgeCallback] = None,
            on_deactivate: Optional[DeactivateCallback] = None) -> None:
        _init_win32_prototypes()
        self._destroyed = False
        self._exstyle = int(exstyle)
        self._window_title = str(window_title)
        self._icon_path = icon_path
        self._on_position_changed = on_position_changed
        self._on_edit_begin = on_edit_begin
        self._on_edit_motion = on_edit_motion
        self._on_edit_end = on_edit_end
        self._on_key_nudge = on_key_nudge
        self._on_deactivate = on_deactivate
        self._editing = False
        self._dragging_window = False
        self._drag_anchor = (0, 0)
        self._width = max(1, int(width))
        self._height = max(1, int(height))
        self._hwnd = None
        self._hbmp = None
        self._hdc_mem = None
        self._bits_buffer = None
        self._buffer_size = 0
        self._blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        self._pt_zero = POINT(0, 0)
        self._size = SIZE(self._width, self._height)
        self._visible = False
        self._register_class()
        self._create_window()
        self._create_dib()

    @classmethod
    def _register_class(cls) -> None:
        global _overlay_class_registered, _overlay_wndproc_ref
        if _overlay_class_registered:
            return
        _overlay_wndproc_ref = _WNDPROC(cls._window_proc)
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = ctypes.cast(_overlay_wndproc_ref, ctypes.c_void_p)
        wc.hInstance = kernel32.GetModuleHandleW(None)
        try:
            wc.hCursor = user32.LoadCursorW(None, IDC_ARROW)
        except Exception:
            wc.hCursor = 0
        wc.lpszClassName = cls._OVERLAY_CLASS
        if user32.RegisterClassW(ctypes.byref(wc)) == 0:
            error = kernel32.GetLastError()
            if error != 1410:
                raise OSError(f"RegisterClassW failed: {error}")
        _overlay_class_registered = True

    @staticmethod
    def _window_proc(hwnd, msg, wparam, lparam):
        inst = _overlay_instances.get(int(hwnd))
        if inst is not None:
            try:
                handled, result = inst._handle_message(msg, wparam, lparam)
            except Exception as exc:
                _capture_window_err_record(
                    "transparent_capture_window.py:_window_proc", exc)
                handled, result = False, 0
            if handled:
                return result
        if msg == WM_DESTROY:
            _overlay_instances.pop(int(hwnd), None)
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    @staticmethod
    def _lparam_to_xy(lparam: int) -> Tuple[int, int]:
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value
        return int(x), int(y)

    def _handle_message(self, msg: int, wparam: int, lparam: int) -> Tuple[bool, int]:
        """Returns (handled, lresult). When handled is False the caller falls
        through to DefWindowProcW. The overlay client area maps 1:1 to the
        output canvas (window created at canvas size, WS_POPUP no border)."""
        if msg == WM_NCHITTEST:
            # HTCLIENT so we receive mouse messages; window drag is manual
            # (so clicks on a selected layer can edit instead of move-window).
            return True, HTCLIENT
        if msg == WM_WINDOWPOSCHANGED:
            self._notify_position_changed()
            return False, 0
        if msg == WM_ACTIVATE:
            # Low word == WA_INACTIVE means this window is losing activation
            # (user clicked away). Let the app decide whether to drop the layer
            # selection (kept only when focus moves to the layer/output window).
            if (int(wparam) & 0xFFFF) == WA_INACTIVE and self._on_deactivate is not None:
                try:
                    self._on_deactivate()
                except Exception:
                    pass
            return False, 0
        if msg == WM_LBUTTONDOWN:
            self._on_left_down(lparam)
            return True, 0
        if msg == WM_MOUSEMOVE:
            self._on_mouse_move(wparam, lparam)
            return True, 0
        if msg == WM_LBUTTONUP:
            self._on_left_up()
            return True, 0
        if msg == WM_KEYDOWN:
            if self._on_key_down(wparam):
                return True, 0
            return False, 0
        if msg == WM_DESTROY:
            _overlay_instances.pop(int(self._hwnd or 0), None)
            return False, 0
        return False, 0

    def _on_left_down(self, lparam: int) -> None:
        if self._destroyed or not self._hwnd:
            return
        x, y = self._lparam_to_xy(lparam)
        hwnd = wintypes.HWND(int(self._hwnd))
        try:
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
        except Exception:
            pass
        began = False
        if self._on_edit_begin is not None:
            try:
                began = bool(self._on_edit_begin(x, y))
            except Exception:
                began = False
        if began:
            self._editing = True
            self._dragging_window = False
        else:
            self._editing = False
            self._dragging_window = True
            pt = POINT()
            rect = wintypes.RECT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            self._drag_anchor = (int(pt.x - rect.left), int(pt.y - rect.top))
        try:
            user32.SetCapture(hwnd)
        except Exception:
            pass

    def _on_mouse_move(self, wparam: int, lparam: int) -> None:
        if self._destroyed or not self._hwnd:
            return
        if self._editing:
            x, y = self._lparam_to_xy(lparam)
            if self._on_edit_motion is not None:
                try:
                    self._on_edit_motion(x, y)
                except Exception:
                    pass
            return
        if self._dragging_window and (int(wparam) & MK_LBUTTON):
            pt = POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            anchor_x, anchor_y = self._drag_anchor
            user32.SetWindowPos(
                wintypes.HWND(int(self._hwnd)),
                wintypes.HWND(HWND_TOPMOST),
                int(pt.x - anchor_x),
                int(pt.y - anchor_y),
                0,
                0,
                SWP_NOSIZE | SWP_NOACTIVATE)

    def _on_left_up(self) -> None:
        try:
            user32.ReleaseCapture()
        except Exception:
            pass
        was_editing = self._editing
        self._editing = False
        self._dragging_window = False
        if was_editing and self._on_edit_end is not None:
            try:
                self._on_edit_end()
            except Exception:
                pass

    def _on_key_down(self, wparam: int) -> bool:
        if self._on_key_nudge is None:
            return False
        vk = int(wparam)
        try:
            shift = bool(user32.GetKeyState(VK_SHIFT) & 0x8000)
        except Exception:
            shift = False
        step = 10.0 if shift else 1.0
        dx = dy = 0.0
        if vk == VK_LEFT:
            dx = -step
        elif vk == VK_RIGHT:
            dx = step
        elif vk == VK_UP:
            dy = -step
        elif vk == VK_DOWN:
            dy = step
        else:
            return False
        try:
            return bool(self._on_key_nudge(dx, dy))
        except Exception:
            return False

    def _notify_position_changed(self) -> None:
        if self._destroyed or not self._hwnd:
            return
        rect = wintypes.RECT()
        if not user32.GetWindowRect(wintypes.HWND(int(self._hwnd)), ctypes.byref(rect)):
            return
        callback = self._on_position_changed
        if callback is not None:
            callback(int(rect.left), int(rect.top))

    def _create_window(self) -> None:
        hwnd = user32.CreateWindowExW(
            self._exstyle,
            self._OVERLAY_CLASS,
            self._window_title,
            WS_POPUP,
            100,
            100,
            self._width,
            self._height,
            None,
            None,
            kernel32.GetModuleHandleW(None),
            None,
        )
        if not hwnd:
            raise OSError(f"CreateWindowExW failed: {kernel32.GetLastError()}")
        self._hwnd = int(hwnd)
        _overlay_instances[self._hwnd] = self
        self._apply_window_icon()

    def _apply_window_icon(self) -> None:
        if not self._icon_path or not self._hwnd:
            return
        try:
            hicon = user32.LoadImageW(
                None,
                self._icon_path,
                IMAGE_ICON,
                0,
                0,
                LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if hicon:
                hwnd = wintypes.HWND(self._hwnd)
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
        except Exception:
            pass

    def _create_dib(self) -> None:
        self._release_dib()
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = self._width
        bmi.bmiHeader.biHeight = -self._height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB
        bits = ctypes.c_void_p()
        hdc_screen = user32.GetDC(None)
        if not hdc_screen:
            raise OSError("GetDC failed")
        try:
            hbmp = gdi32.CreateDIBSection(
                hdc_screen,
                ctypes.byref(bmi),
                DIB_RGB_COLORS,
                ctypes.byref(bits),
                None,
                0,
            )
        finally:
            user32.ReleaseDC(None, hdc_screen)
        if not hbmp or not bits.value:
            raise OSError("CreateDIBSection failed")
        self._hbmp = hbmp
        self._bits_buffer = (ctypes.c_ubyte * (self._width * self._height * 4)).from_address(bits.value)
        self._buffer_size = self._width * self._height * 4
        self._hdc_mem = gdi32.CreateCompatibleDC(None)
        gdi32.SelectObject(self._hdc_mem, self._hbmp)

    def _release_dib(self) -> None:
        if self._hdc_mem:
            gdi32.DeleteDC(self._hdc_mem)
            self._hdc_mem = None
        if self._hbmp:
            gdi32.DeleteObject(self._hbmp)
            self._hbmp = None
        self._bits_buffer = None
        self._buffer_size = 0

    def is_valid(self) -> bool:
        return (
            not self._destroyed
            and bool(self._hwnd)
            and bool(user32.IsWindow(wintypes.HWND(self._hwnd))))

    def set_geometry(self, x: int, y: int, width: int, height: int) -> None:
        if self._destroyed:
            return
        width = max(1, int(width))
        height = max(1, int(height))
        resized = width != self._width or height != self._height
        self._width = width
        self._height = height
        self._size = SIZE(width, height)
        if resized:
            try:
                self._create_dib()
            except OSError:
                return
        if not self.is_valid():
            return
        user32.SetWindowPos(
            wintypes.HWND(self._hwnd),
            wintypes.HWND(HWND_TOPMOST),
            int(x),
            int(y),
            width,
            height,
            SWP_NOACTIVATE)

    def update_rgba(
            self,
            rgba: numpy.ndarray,
            *,
            premultiplied_bgra: Optional[numpy.ndarray] = None) -> None:
        if self._destroyed or not self.is_valid():
            return
        if self._bits_buffer is None or self._hdc_mem is None:
            return
        try:
            if premultiplied_bgra is not None:
                bgra_premul = numpy.ascontiguousarray(
                    premultiplied_bgra, dtype=numpy.uint8)
            else:
                bgra_premul = _straight_rgba_to_premultiplied_bgra(rgba)
            if bgra_premul.nbytes != self._buffer_size:
                bgra_premul = _straight_rgba_to_premultiplied_bgra(rgba)
            if bgra_premul.nbytes != self._buffer_size:
                return
            ctypes.memmove(self._bits_buffer, bgra_premul.ctypes.data, self._buffer_size)
            if not user32.UpdateLayeredWindow(
                    wintypes.HWND(self._hwnd),
                    None,
                    None,
                    ctypes.byref(self._size),
                    self._hdc_mem,
                    ctypes.byref(self._pt_zero),
                    0,
                    ctypes.byref(self._blend),
                    ULW_ALPHA):
                return
            if not self._visible:
                user32.ShowWindow(wintypes.HWND(self._hwnd), 5)
                self._visible = True
        except Exception:
            return

    def show(self) -> None:
        if not self.is_valid():
            return
        user32.ShowWindow(wintypes.HWND(self._hwnd), 5)
        self._visible = True

    def hide(self) -> None:
        if not self.is_valid():
            return
        user32.ShowWindow(wintypes.HWND(self._hwnd), 0)
        self._visible = False

    def destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        hwnd = self._hwnd
        if hwnd:
            _overlay_instances.pop(int(hwnd), None)
            try:
                if user32.IsWindow(wintypes.HWND(hwnd)):
                    user32.DestroyWindow(wintypes.HWND(hwnd))
            except Exception:
                pass
            self._hwnd = None
        self._release_dib()
        self._visible = False


class TransparentCaptureWindow:
    """Single topmost true-transparent (per-pixel alpha) overlay window (ULW).

    The ULW is the only window now: it owns geometry (position via
    WM_WINDOWPOSCHANGED, dragging via the overlay's HTCAPTION hit-test) and the
    framebuffer (UpdateLayeredWindow). The previous color-key wx list frame is
    retired; transparent-mode capture goes through WGC / game capture with
    "allow transparency". The on-screen editing surface remains the wx
    OutputFrame until P6 wires Win32 editing onto this overlay.
    """

    def __init__(
            self,
            width: int,
            height: int,
            *,
            on_geometry_changed: Optional[GeometryCallback] = None,
            on_edit_begin: Optional[EditBeginCallback] = None,
            on_edit_motion: Optional[EditMotionCallback] = None,
            on_edit_end: Optional[EditEndCallback] = None,
            on_key_nudge: Optional[KeyNudgeCallback] = None,
            on_deactivate: Optional[DeactivateCallback] = None) -> None:
        _ensure_dpi_awareness()
        self._destroyed = False
        self._on_geometry_changed = on_geometry_changed
        self._geometry_sync_suppress = False
        self._width = max(1, int(width))
        self._height = max(1, int(height))
        self._visible_x = 100
        self._visible_y = 100
        self._last_overlay_rect: Optional[Tuple[int, int, int, int]] = None
        self._last_frame_hash: Optional[int] = None
        self._border_thickness = max(0, int(BORDER_THICKNESS_PX))
        self._border_last_size: Optional[Tuple[int, int]] = None
        self._overlay = _DesktopOverlayWindow(
            width,
            height,
            exstyle=WS_EX_LAYERED | WS_EX_APPWINDOW,
            window_title=WINDOW_TITLE,
            icon_path=_resolve_app_icon_path(),
            on_position_changed=self._on_overlay_position_changed,
            on_edit_begin=on_edit_begin,
            on_edit_motion=on_edit_motion,
            on_edit_end=on_edit_end,
            on_key_nudge=on_key_nudge,
            on_deactivate=on_deactivate)
        # Separate click-through, no-taskbar border window. Never the capture
        # target, so it stays out of the stream while marking the output on-screen.
        self._border: Optional[_DesktopOverlayWindow] = None
        if self._border_thickness > 0:
            try:
                self._border = _DesktopOverlayWindow(
                    width + 2 * self._border_thickness,
                    height + 2 * self._border_thickness,
                    exstyle=(WS_EX_LAYERED | WS_EX_TRANSPARENT
                             | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE),
                    window_title="")
            except OSError:
                self._border = None
        self._sync_visible_geometry(force=True)

    def _on_overlay_position_changed(self, x: int, y: int) -> None:
        if self._destroyed or self._geometry_sync_suppress:
            return
        if self._visible_x == int(x) and self._visible_y == int(y):
            return
        self._visible_x = int(x)
        self._visible_y = int(y)
        self._last_overlay_rect = (
            self._visible_x, self._visible_y, self._width, self._height)
        # Keep the decorative border glued to the ULW while the user drags it.
        # set_geometry re-raises the border to the top of the topmost band, so
        # re-raise the ULW above it afterwards or the border would sit in front
        # of the output window (z-order looks wrong / intercepts the edit).
        self._sync_border_geometry()
        _raise_overlay_topmost(int(self._overlay._hwnd or 0))
        if self._on_geometry_changed is not None:
            self._on_geometry_changed()

    def _sync_visible_geometry(self, *, force: bool = False) -> None:
        if self._destroyed or self._overlay is None:
            return
        rect = (self._visible_x, self._visible_y, self._width, self._height)
        if not force and rect == self._last_overlay_rect:
            return
        self._last_overlay_rect = rect
        self._geometry_sync_suppress = True
        try:
            self._overlay.set_geometry(
                self._visible_x, self._visible_y, self._width, self._height)
            # Place the border first, then raise the ULW above it so the output
            # window stays on top (the border interior is transparent regardless).
            self._sync_border_geometry()
            _raise_overlay_topmost(int(self._overlay._hwnd or 0))
        finally:
            self._geometry_sync_suppress = False

    def _sync_border_geometry(self) -> None:
        border = self._border
        if border is None or not border.is_valid():
            return
        t = self._border_thickness
        bw = self._width + 2 * t
        bh = self._height + 2 * t
        border.set_geometry(self._visible_x - t, self._visible_y - t, bw, bh)
        if self._border_last_size != (bw, bh):
            self._border_last_size = (bw, bh)
            try:
                ring = _build_border_ring_rgba(bw, bh, t, BORDER_COLOR_RGBA)
                border.update_rgba(ring)
            except Exception:
                pass

    @property
    def hwnd(self) -> int:
        if self._destroyed or self._overlay is None:
            return 0
        return int(self._overlay._hwnd or 0)

    def is_valid(self) -> bool:
        if self._destroyed or self._overlay is None:
            return False
        return self._overlay.is_valid()

    def owns_foreground_window(self) -> bool:
        """True when the OS foreground window is this ULW (the on-screen output
        window). Lets the wx app tell "user clicked the output window" apart
        from "user clicked away", since the ULW is a Win32 window and never
        shows up in wx focus."""
        if self._destroyed or self._overlay is None:
            return False
        hwnd = int(self._overlay._hwnd or 0)
        if not hwnd:
            return False
        try:
            fg = user32.GetForegroundWindow()
            return bool(fg) and int(fg) == hwnd
        except Exception:
            return False

    def get_rect(self) -> Tuple[int, int, int, int]:
        if self._destroyed:
            return 0, 0, 1, 1
        return (self._visible_x, self._visible_y, self._width, self._height)

    def set_position(self, x: int, y: int) -> None:
        if self._destroyed:
            return
        self._visible_x = int(x)
        self._visible_y = int(y)
        self._sync_visible_geometry(force=True)

    def show(self) -> None:
        if not self.is_valid():
            return
        # Show the (possibly still-empty/transparent) ULW immediately so capture
        # software can list/remember it by title before the first frame arrives.
        self._overlay.show()
        self._sync_visible_geometry(force=True)
        if self._border is not None and self._border.is_valid():
            self._border.show()
        _raise_overlay_topmost(int(self._overlay._hwnd or 0))

    def hide(self) -> None:
        if self._destroyed or self._overlay is None:
            return
        if self._border is not None:
            self._border.hide()
        self._overlay.hide()

    def destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        overlay = self._overlay
        border = self._border
        self._overlay = None
        self._border = None
        try:
            if border is not None:
                border.destroy()
        except Exception:
            pass
        try:
            if overlay is not None:
                overlay.destroy()
        except Exception:
            pass

    def update_frame_rgba(
            self,
            rgba: numpy.ndarray,
            *,
            frame_signature: Optional[tuple] = None,
            premultiplied_bgra: Optional[numpy.ndarray] = None) -> None:
        if self._destroyed or not self.is_valid():
            return
        try:
            rgba = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
            if frame_signature is not None:
                if frame_signature == self._last_frame_hash:
                    return
                self._last_frame_hash = frame_signature
            else:
                frame_hash = int(hash(rgba.shape + (int(rgba[0, 0, 0]), int(rgba[-1, -1, -1]))))
                if frame_hash == self._last_frame_hash:
                    return
                self._last_frame_hash = frame_hash
            height, width = int(rgba.shape[0]), int(rgba.shape[1])
            if width != self._width or height != self._height:
                self._width = width
                self._height = height
                self._sync_visible_geometry(force=True)
            transparent = rgba[:, :, 3] == 0
            if numpy.any(transparent):
                rgba = rgba.copy()
                rgba[transparent, 0:3] = 0
            self._overlay.update_rgba(rgba, premultiplied_bgra=premultiplied_bgra)
        except Exception as exc:
            _capture_window_err_record("transparent_capture_window.py:update_frame_rgba", exc)
            raise
