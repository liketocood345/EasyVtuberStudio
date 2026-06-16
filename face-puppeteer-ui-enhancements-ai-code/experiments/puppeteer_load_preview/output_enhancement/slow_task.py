"""Non-blocking progress UI for slow enhancement model loads (f-057)."""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

try:
    import wx
except ImportError:
    wx = None  # type: ignore

ProgressFn = Callable[[str, float], None]


class SlowTaskProgressDialog:
    """Simple modal progress; safe to update from worker via wx.CallAfter."""

    def __init__(self, parent, title: str = "Loading models..."):
        self._parent = parent
        self._dialog = None
        self._gauge = None
        self._label = None
        if wx is None:
            return
        self._dialog = wx.ProgressDialog(
            title,
            "Preparing output enhancement…",
            maximum=100,
            parent=parent,
            style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_ELAPSED_TIME | wx.PD_REMAINING_TIME)

    def update(self, message: str, fraction: float) -> None:
        if self._dialog is None:
            return
        pct = max(0, min(100, int(round(fraction * 100))))
        self._dialog.Update(pct, message)

    def close(self) -> None:
        if self._dialog is not None:
            self._dialog.Destroy()
            self._dialog = None


def run_slow_task(
        parent,
        title: str,
        task: Callable[[ProgressFn], None],
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None) -> None:
    """Run task in background thread; progress updates on UI thread."""

    dialog = SlowTaskProgressDialog(parent, title=title)

    def _progress(msg: str, frac: float) -> None:
        if wx is not None:
            wx.CallAfter(dialog.update, msg, frac)

    def _worker() -> None:
        try:
            task(_progress)
            if on_complete and wx is not None:
                wx.CallAfter(on_complete)
        except Exception as exc:
            if on_error and wx is not None:
                wx.CallAfter(on_error, exc)
        finally:
            if wx is not None:
                wx.CallAfter(dialog.close)

    threading.Thread(target=_worker, daemon=True).start()
