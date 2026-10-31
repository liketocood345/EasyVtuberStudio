"""Non-modal startup splash: app icon, status text, looping beitou.gif at 1em.

Importable without torch/cv2. Standalone host: ``pythonw startup_splash.py --host``.
"""
from __future__ import annotations
from portable_process_env import debug_log_path

import os
from typing import Optional

import PIL.Image
import wx

APP_ICON_RELPATH = os.path.join("assets", "branding", "app-icon-source.ico")
APP_ICON_PNG_RELPATH = os.path.join("assets", "branding", "app-icon-source.png")
BEITOU_GIF_RELPATH = os.path.join(
    "data",
    "character_models",
    "baiten_from_project_forlon9",
    "bai_450k",
    "parts",
    "beitou.gif",
)
_SPLASH_ICON_PX = 96
_SPLASH_BG = wx.Colour(248, 248, 248)
_UNIX_EPOCH_FLOOR = 1.0e8


def _walk_repo_file(*relparts: str) -> Optional[str]:
    rel = os.path.join(*relparts)
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        candidate = os.path.join(cur, rel)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def resolve_app_icon_path() -> Optional[str]:
    png = _walk_repo_file(APP_ICON_PNG_RELPATH)
    if png:
        return png
    return _walk_repo_file(APP_ICON_RELPATH)


def resolve_beitou_gif_path() -> Optional[str]:
    return _walk_repo_file(BEITOU_GIF_RELPATH)


def early_splash_close_path() -> str:
    override = os.environ.get("EVS_SPLASH_CLOSE", "").strip()
    if override:
        return override
    return os.path.join(os.environ.get("TEMP", os.path.dirname(__file__)), "evs-splash.close")


def signal_early_splash_close() -> None:
    path = early_splash_close_path()
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("close\n")
    except OSError:
        pass


def _gui_em_px() -> int:
    font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
    try:
        height = int(font.GetPixelSize().GetHeight() or 0)
    except Exception:
        height = 0
    if height <= 0:
        height = int(font.GetPointSize() or 0) + 4
    return max(12, min(28, height or 16))


def _resample():
    return getattr(getattr(PIL.Image, "Resampling", PIL.Image), "LANCZOS", PIL.Image.NEAREST)


def _pil_to_wx_bitmap(image: PIL.Image.Image) -> wx.Bitmap:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    wx_image = wx.Image(width, height)
    wx_image.SetData(bytes(rgba.convert("RGB").tobytes()))
    wx_image.SetAlpha(bytes(rgba.getchannel("A").tobytes()))
    return wx.Bitmap(wx_image)


def _pil_frame_to_bitmap(frame: PIL.Image.Image, pixel_size: int) -> wx.Bitmap:
    rgba = frame.convert("RGBA").resize((pixel_size, pixel_size), _resample())
    return _pil_to_wx_bitmap(rgba)


def _load_beitou_loop_frames(pixel_size: int) -> tuple[list[wx.Bitmap], list[int]]:
    path = resolve_beitou_gif_path()
    if not path:
        return [], []
    bitmaps: list[wx.Bitmap] = []
    delays_ms: list[int] = []
    with PIL.Image.open(path) as gif:
        index = 0
        while True:
            duration = int(gif.info.get("duration") or 80)
            bitmaps.append(_pil_frame_to_bitmap(gif, pixel_size))
            delays_ms.append(max(40, min(400, duration)))
            index += 1
            try:
                gif.seek(index)
            except EOFError:
                break
    return bitmaps, delays_ms


def _icon_bitmap(max_px: int) -> Optional[wx.Bitmap]:
    # bh-6 26.10.30 12:25 s
    path = resolve_app_icon_path()
    if not path:
        return None
    try:
        source = PIL.Image.open(path).convert("RGBA")
        width, height = source.size
        scale = min(float(max_px) / max(1, width), float(max_px) / max(1, height))
        new_w = max(1, int(round(width * scale)))
        new_h = max(1, int(round(height * scale)))
        fitted = source.resize((new_w, new_h), _resample())
        canvas = PIL.Image.new("RGBA", (max_px, max_px), (0, 0, 0, 0))
        canvas.paste(fitted, ((max_px - new_w) // 2, (max_px - new_h) // 2), fitted)
        bitmap = _pil_to_wx_bitmap(canvas)
        if bitmap.IsOk():
            return bitmap
    except Exception:
        return None
    return None
    # bh-6 26.10.30 12:25 e


class StartupSplashFrame(wx.Frame):
    """Stay-on-top splash. Shown with Show(), never ShowModal / APP_MODAL."""

    def __init__(self) -> None:
        super().__init__(
            None,
            title="EasyVtuberStudio",
            style=wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR | wx.BORDER_SIMPLE,
        )
        self.SetBackgroundColour(_SPLASH_BG)
        try:
            ico = _walk_repo_file(APP_ICON_RELPATH)
            if ico:
                bundle = wx.IconBundle(ico, wx.BITMAP_TYPE_ICO)
                if bundle.GetIconCount() > 0:
                    self.SetIcons(bundle)
        except Exception:
            pass

        panel = wx.Panel(self)
        panel.SetBackgroundColour(_SPLASH_BG)
        sizer = wx.BoxSizer(wx.VERTICAL)

        icon_bitmap = _icon_bitmap(_SPLASH_ICON_PX)
        self._icon_ok = icon_bitmap is not None
        if icon_bitmap is not None:
            icon_ctrl = wx.StaticBitmap(panel, bitmap=icon_bitmap)
            sizer.Add(icon_ctrl, 0, wx.ALIGN_CENTER | wx.TOP, 18)

        status = wx.StaticText(panel, label="正在启动中")
        font = status.GetFont()
        font.MakeLarger()
        status.SetFont(font)
        sizer.Add(status, 0, wx.ALIGN_CENTER | wx.TOP | wx.LEFT | wx.RIGHT, 12)

        em = _gui_em_px()
        self._loader_frames, self._loader_delays_ms = _load_beitou_loop_frames(em)
        self._loader_index = 0
        self._loader_bitmap = None
        if self._loader_frames:
            self._loader_bitmap = wx.StaticBitmap(panel, bitmap=self._loader_frames[0])
            sizer.Add(self._loader_bitmap, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 10)
            self._loader_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self._on_loader_tick, id=self._loader_timer.GetId())
            self._loader_timer.Start(int(self._loader_delays_ms[0]))
        else:
            sizer.AddSpacer(10)

        panel.SetSizer(sizer)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(outer)
        self.SetClientSize((max(240, _SPLASH_ICON_PX + 80), 196 if icon_bitmap is not None else 90))
        self.CentreOnScreen()

    def _on_loader_tick(self, _event: wx.Event) -> None:
        if not self._loader_frames or self._loader_bitmap is None:
            return
        self._loader_index = (self._loader_index + 1) % len(self._loader_frames)
        self._loader_bitmap.SetBitmap(self._loader_frames[self._loader_index])
        delay = self._loader_delays_ms[self._loader_index]
        timer = getattr(self, "_loader_timer", None)
        if timer is not None and delay != timer.GetInterval():
            timer.Start(int(delay))

    def shutdown(self) -> None:
        timer = getattr(self, "_loader_timer", None)
        if timer is not None:
            try:
                timer.Stop()
            except Exception:
                pass
        try:
            self.Hide()
            self.Destroy()
        except Exception:
            pass


def show_startup_splash(app: wx.App) -> Optional[StartupSplashFrame]:
    try:
        splash = StartupSplashFrame()
        splash.Show(True)
        splash.Raise()
        splash.Update()
        pump_startup_splash(app)
        # #region agent log
        try:
            import json as _json, time as _time
            open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({
                "sessionId": "86a17c",
                "runId": "post-fix",
                "hypothesisId": "S",
                "location": "startup_splash.py:show_startup_splash",
                "message": "splash shown",
                "data": {
                    "shown": bool(splash.IsShown()),
                    "gif_frames": int(len(getattr(splash, "_loader_frames", []) or [])),
                    "has_icon": bool(resolve_app_icon_path()),
                    "icon_ok": bool(getattr(splash, "_icon_ok", False)),
                    "icon_path": resolve_app_icon_path() or "",
                    "early": os.environ.get("EVS_EARLY_SPLASH", ""),
                },
                "timestamp": int(_time.time() * 1000),
            }) + "\n")
        except Exception:
            pass
        # #endregion
        return splash
    except Exception:
        return None


def pump_startup_splash(app: Optional[wx.App], times: int = 6) -> None:
    if app is None:
        return
    for _ in range(max(1, times)):
        try:
            app.Yield(True)
        except Exception:
            break


def close_startup_splash(splash: Optional[StartupSplashFrame]) -> None:
    if splash is None:
        return
    try:
        splash.shutdown()
        # #region agent log
        try:
            import json as _json, time as _time
            open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({
                "sessionId": "86a17c",
                "runId": "post-fix",
                "hypothesisId": "S",
                "location": "startup_splash.py:close_startup_splash",
                "message": "splash closed",
                "data": {"ok": True},
                "timestamp": int(_time.time() * 1000),
            }) + "\n")
        except Exception:
            pass
        # #endregion
    except Exception:
        pass


def rebase_gif_clock_epoch(epoch: float, now: float) -> float:
    """Map persisted unix-time GIF epochs onto the QPC present clock."""
    if epoch <= 0.0 or epoch >= _UNIX_EPOCH_FLOOR:
        return now
    return epoch
