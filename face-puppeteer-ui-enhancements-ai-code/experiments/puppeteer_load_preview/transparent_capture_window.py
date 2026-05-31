"""Transparent capture: listable wx frame + layered desktop overlay."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable, Optional, Tuple

import numpy
import wx

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

WINDOW_TITLE = "THA4 Transparent Capture / 透明捕获输出"
WINDOW_CLASS_NAME = "THA4TransparentCaptureWindow"

WM_DESTROY = 0x0002
WM_NCHITTEST = 0x0084
WM_WINDOWPOSCHANGED = 0x0047

HTCAPTION = 2

WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000

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

def _get_window_exstyle(hwnd: int) -> int:
    if not hwnd:
        return 0
    return int(user32.GetWindowLongW(int(hwnd), GWL_EXSTYLE))


def _ensure_list_frame_discoverable(hwnd: int) -> None:
    """Borderless wx frames may omit WS_EX_APPWINDOW; live pickers often require it."""
    if not hwnd:
        return
    style = _get_window_exstyle(hwnd)
    style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
    user32.SetWindowLongW(int(hwnd), GWL_EXSTYLE, style)
    user32.ShowWindow(wintypes.HWND(int(hwnd)), 5)
    user32.SetWindowPos(
        wintypes.HWND(int(hwnd)),
        None,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_NOACTIVATE,
    )


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


def _apply_list_frame_black_colorkey(list_hwnd: int) -> None:
    """Make list-frame black pixels see-through on desktop; capture still gets black."""
    if not list_hwnd:
        return
    style = _get_window_exstyle(list_hwnd)
    user32.SetWindowLongW(int(list_hwnd), GWL_EXSTYLE, style | WS_EX_LAYERED)
    user32.SetLayeredWindowAttributes(
        wintypes.HWND(int(list_hwnd)),
        COLORKEY_BLACK,
        0,
        LWA_COLORKEY,
    )


def _lower_list_frame_zorder(list_hwnd: int) -> None:
    if not list_hwnd:
        return
    user32.SetWindowPos(
        wintypes.HWND(int(list_hwnd)),
        wintypes.HWND(HWND_BOTTOM),
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


def _rgba_to_wx_bitmap(rgba: numpy.ndarray) -> wx.Bitmap:
    rgba = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
    height, width = rgba.shape[0], rgba.shape[1]
    return wx.Bitmap.FromBufferRGBA(width, height, rgba.tobytes())


class _CaptureListFrame(wx.Frame):
    """Normal wx top-level frame for window capture pickers (no WS_EX_LAYERED)."""

    def __init__(
            self,
            width: int,
            height: int,
            *,
            on_geometry_changed: Optional[GeometryCallback] = None) -> None:
        self._on_geometry_changed = on_geometry_changed
        self._geometry_suppress = False
        self._destroyed = False
        self._client_width = max(1, int(width))
        self._client_height = max(1, int(height))
        self._bitmap = wx.Bitmap(self._client_width, self._client_height, 32)
        super().__init__(
            None,
            title=WINDOW_TITLE,
            style=wx.BORDER_NONE,
            name=WINDOW_CLASS_NAME)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetDoubleBuffered(True)
        locked_size = wx.Size(self._client_width, self._client_height)
        self.SetMinClientSize(locked_size)
        self.SetMaxClientSize(locked_size)
        self.SetSizeHints(
            self._client_width,
            self._client_height,
            self._client_width,
            self._client_height,
            self._client_width,
            self._client_height)
        self.SetClientSize(locked_size)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda _event: None)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, self._on_size)
        self.Bind(wx.EVT_MOVE, self._on_move)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_drag_start)
        self.Bind(wx.EVT_MOTION, self._on_drag_motion)
        self.Bind(wx.EVT_LEFT_UP, self._on_drag_end)
        self._dragging = False
        self._drag_offset = wx.Point(0, 0)
        self.Show(True)
        list_hwnd = int(self.GetHandle())
        _ensure_list_frame_discoverable(list_hwnd)
        _apply_list_frame_black_colorkey(list_hwnd)
        _lower_list_frame_zorder(list_hwnd)

    def _on_size(self, event: wx.Event) -> None:
        if self._destroyed:
            return
        locked_size = wx.Size(self._client_width, self._client_height)
        if self.GetClientSize() != locked_size:
            self.SetClientSize(locked_size)
        event.Skip()

    def _on_paint(self, _event: wx.Event) -> None:
        if self._destroyed:
            return
        try:
            dc = wx.AutoBufferedPaintDC(self)
            dc.SetBackground(wx.Brush(wx.Colour(0, 0, 0)))
            dc.Clear()
            if self._bitmap.IsOk():
                dc.DrawBitmap(self._bitmap, 0, 0, True)
        except RuntimeError:
            pass

    def _on_move(self, _event: wx.Event) -> None:
        if self._destroyed or self._geometry_suppress:
            return
        if self._on_geometry_changed is not None:
            self._on_geometry_changed()

    def _on_drag_start(self, event: wx.MouseEvent) -> None:
        if self._destroyed:
            return
        self._dragging = True
        self._drag_offset = event.GetPosition()
        self.CaptureMouse()
        event.Skip()

    def _on_drag_motion(self, event: wx.MouseEvent) -> None:
        if self._destroyed or not self._dragging or not event.Dragging():
            return
        screen_pos = self.ClientToScreen(event.GetPosition())
        self._geometry_suppress = True
        try:
            self.SetPosition(wx.Point(
                int(screen_pos.x - self._drag_offset.x),
                int(screen_pos.y - self._drag_offset.y)))
        finally:
            self._geometry_suppress = False
        if self._on_geometry_changed is not None:
            self._on_geometry_changed()
        event.Skip()

    def _on_drag_end(self, event: wx.MouseEvent) -> None:
        if self._dragging:
            self._dragging = False
            if self.HasCapture():
                self.ReleaseMouse()
        event.Skip()

    def _on_close(self, event: wx.CloseEvent) -> None:
        event.Veto()
        try:
            self.Hide()
        except RuntimeError:
            pass

    def set_rgba(self, rgba: numpy.ndarray) -> None:
        if self._destroyed:
            return
        height, width = rgba.shape[0], rgba.shape[1]
        if width != self._client_width or height != self._client_height:
            self._client_width = width
            self._client_height = height
            locked_size = wx.Size(width, height)
            self.SetMinClientSize(locked_size)
            self.SetMaxClientSize(locked_size)
            self.SetClientSize(locked_size)
        self._bitmap = _rgba_to_wx_bitmap(rgba)
        if not self.IsShown():
            self.Show(True)
        self.Refresh(False)

    def get_screen_client_rect(self) -> Tuple[int, int, int, int]:
        if self._destroyed:
            return 0, 0, self._client_width, self._client_height
        try:
            origin = self.GetScreenPosition()
            return int(origin.x), int(origin.y), self._client_width, self._client_height
        except RuntimeError:
            return 0, 0, self._client_width, self._client_height

    def set_screen_client_origin(self, x: int, y: int) -> None:
        if self._destroyed:
            return
        self._geometry_suppress = True
        try:
            self.SetPosition(wx.Point(int(x), int(y)))
        except RuntimeError:
            pass
        finally:
            self._geometry_suppress = False

    def destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        try:
            if self.IsShown():
                self.Hide()
        except RuntimeError:
            pass
        try:
            if not self.IsBeingDeleted():
                self.Destroy()
        except RuntimeError:
            pass


class _DesktopOverlayWindow:
    """Layered popup for true desktop alpha; hidden from window capture lists."""

    _OVERLAY_CLASS = "THA4TransparentCaptureOverlay"

    def __init__(self, width: int, height: int, *, on_position_changed: Optional[PositionCallback] = None) -> None:
        _init_win32_prototypes()
        self._destroyed = False
        self._on_position_changed = on_position_changed
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
        wc.lpszClassName = cls._OVERLAY_CLASS
        if user32.RegisterClassW(ctypes.byref(wc)) == 0:
            error = kernel32.GetLastError()
            if error != 1410:
                raise OSError(f"RegisterClassW failed: {error}")
        _overlay_class_registered = True

    @staticmethod
    def _window_proc(hwnd, msg, wparam, lparam):
        inst = _overlay_instances.get(int(hwnd))
        if msg == WM_NCHITTEST:
            return HTCAPTION
        if msg == WM_WINDOWPOSCHANGED and inst is not None:
            inst._notify_position_changed()
        if msg == WM_DESTROY:
            _overlay_instances.pop(int(hwnd), None)
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

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
            WS_EX_LAYERED | WS_EX_TOOLWINDOW,
            self._OVERLAY_CLASS,
            "",
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

    def update_rgba(self, rgba: numpy.ndarray) -> None:
        if self._destroyed or not self.is_valid():
            return
        if self._bits_buffer is None or self._hdc_mem is None:
            return
        try:
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
    """On-screen listable capture frame + topmost true-transparent overlay."""

    def __init__(
            self,
            width: int,
            height: int,
            *,
            on_geometry_changed: Optional[GeometryCallback] = None) -> None:
        _ensure_dpi_awareness()
        self._destroyed = False
        self._on_geometry_changed = on_geometry_changed
        self._geometry_sync_suppress = False
        self._visible_x = 0
        self._visible_y = 0
        self._last_overlay_rect: Optional[Tuple[int, int, int, int]] = None
        self._last_frame_hash: Optional[int] = None
        self._list_frame = _CaptureListFrame(
            width,
            height,
            on_geometry_changed=self._on_list_frame_geometry_changed)
        self._overlay = _DesktopOverlayWindow(
            width,
            height,
            on_position_changed=self._on_overlay_position_changed)
        origin = self._list_frame.GetScreenPosition()
        self._visible_x = int(origin.x)
        self._visible_y = int(origin.y)
        self._sync_visible_geometry(force=True)

    def _on_list_frame_geometry_changed(self) -> None:
        if self._destroyed or self._geometry_sync_suppress:
            return
        origin = self._list_frame.GetScreenPosition()
        self._apply_visible_position(int(origin.x), int(origin.y), notify=False)
        if self._on_geometry_changed is not None:
            self._on_geometry_changed()

    def _on_overlay_position_changed(self, x: int, y: int) -> None:
        if self._destroyed or self._geometry_sync_suppress:
            return
        if self._visible_x == int(x) and self._visible_y == int(y):
            return
        self._geometry_sync_suppress = True
        try:
            self._apply_visible_position(x, y, notify=False)
            self._list_frame.set_screen_client_origin(x, y)
        finally:
            self._geometry_sync_suppress = False
        if self._on_geometry_changed is not None:
            self._on_geometry_changed()

    def _apply_visible_position(self, x: int, y: int, *, notify: bool = False) -> None:
        width = self._list_frame._client_width
        height = self._list_frame._client_height
        rect = (int(x), int(y), width, height)
        if rect == self._last_overlay_rect:
            return
        self._visible_x = int(x)
        self._visible_y = int(y)
        self._last_overlay_rect = rect
        list_hwnd = self.hwnd
        _apply_list_frame_black_colorkey(list_hwnd)
        _lower_list_frame_zorder(list_hwnd)
        self._overlay.set_geometry(self._visible_x, self._visible_y, width, height)
        _raise_overlay_topmost(int(self._overlay._hwnd or 0))
        if notify and self._on_geometry_changed is not None:
            self._on_geometry_changed()

    def _sync_visible_geometry(self, *, force: bool = False) -> None:
        if self._destroyed:
            return
        width = self._list_frame._client_width
        height = self._list_frame._client_height
        rect = (self._visible_x, self._visible_y, width, height)
        if not force and rect == self._last_overlay_rect:
            return
        self._list_frame.set_screen_client_origin(self._visible_x, self._visible_y)
        self._apply_visible_position(self._visible_x, self._visible_y, notify=False)

    @property
    def hwnd(self) -> int:
        if self._destroyed:
            return 0
        try:
            return int(self._list_frame.GetHandle())
        except RuntimeError:
            return 0

    def is_valid(self) -> bool:
        if self._destroyed:
            return False
        try:
            return bool(self._list_frame) and self._list_frame.GetHandle() != 0
        except RuntimeError:
            return False

    def get_rect(self) -> Tuple[int, int, int, int]:
        if self._destroyed:
            return 0, 0, 1, 1
        return (
            self._visible_x,
            self._visible_y,
            self._list_frame._client_width,
            self._list_frame._client_height,
        )

    def set_position(self, x: int, y: int) -> None:
        if self._destroyed:
            return
        self._visible_x = int(x)
        self._visible_y = int(y)
        self._sync_visible_geometry(force=True)

    def show(self) -> None:
        if not self.is_valid():
            return
        try:
            self._list_frame.Show(True)
        except RuntimeError:
            return
        self._sync_visible_geometry(force=True)

    def hide(self) -> None:
        if self._destroyed:
            return
        try:
            if self.is_valid():
                self._list_frame.Hide()
        except RuntimeError:
            pass
        self._overlay.hide()

    def destroy(self) -> None:
        if self._destroyed:
            return
        self._destroyed = True
        overlay = self._overlay
        list_frame = self._list_frame
        self._overlay = None
        self._list_frame = None
        try:
            overlay.destroy()
        except Exception:
            pass
        try:
            list_frame.destroy()
        except Exception:
            pass

    def update_frame_rgba(self, rgba: numpy.ndarray, *, frame_signature: Optional[tuple] = None) -> None:
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
            transparent = rgba[:, :, 3] == 0
            if numpy.any(transparent):
                rgba = rgba.copy()
                rgba[transparent, 0:3] = 0
            self._list_frame.set_rgba(rgba)
            self._overlay.update_rgba(rgba)
        except Exception as exc:
            _capture_window_err_record("transparent_capture_window.py:update_frame_rgba", exc)
            raise
