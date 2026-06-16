"""f-064: periodic UI vs runtime alignment checks with non-modal toast."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

try:
    import wx
except ImportError:
    wx = None  # type: ignore

PERIODIC_CHECK_MS = 3 * 60 * 1000
POST_SWITCH_LOAD_FACTOR = 1.5
DEFAULT_LOAD_BUDGET_SEC = 10 * 60
TOAST_AUTO_CLOSE_MS = 5000
TOAST_DEBOUNCE_SEC = 60.0

ProbeFn = Callable[[], Optional[Tuple[str, str, str]]]
RevertFn = Callable[[], None]


@dataclass
class AlignmentProbe:
    probe_id: str
    label: str
    check: ProbeFn
    revert: RevertFn
    load_budget_sec: float = DEFAULT_LOAD_BUDGET_SEC


@dataclass
class _ToastState:
    last_key: str = ""
    last_mono: float = 0.0


class NonModalAlignmentToast(wx.Frame if wx else object):
    """Non-modal reminder; auto-closes after 5s; OK dismisses early."""

    def __init__(self, parent, title: str, message: str):
        if wx is None:
            return
        super().__init__(
            parent,
            title=title,
            style=(wx.STAY_ON_TOP | wx.FRAME_TOOL_WINDOW | wx.CAPTION | wx.CLOSE_BOX))
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(panel, label=message, style=wx.ST_ELLIPSIZE_MULTILINE)
        label.Wrap(420)
        sizer.Add(label, 1, wx.ALL | wx.EXPAND, 10)
        ok_btn = wx.Button(panel, wx.ID_OK, "确定 / OK")
        sizer.Add(ok_btn, 0, wx.ALL | wx.ALIGN_RIGHT, 8)
        panel.SetSizer(sizer)
        sizer.Fit(panel)
        self.SetClientSize(panel.GetBestSize())
        ok_btn.Bind(wx.EVT_BUTTON, lambda _evt: self.Close())
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self._timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_auto_close, self._timer)
        self._timer.Start(TOAST_AUTO_CLOSE_MS, oneShot=True)

    def _on_auto_close(self, _event):
        self.Close()

    def _on_close(self, event):
        if hasattr(self, "_timer") and self._timer.IsRunning():
            self._timer.Stop()
        event.Skip()
        self.Destroy()


class UiAlignmentMonitor:
    def __init__(self, frame):
        self._frame = frame
        self._probes: Dict[str, AlignmentProbe] = {}
        self._toast_state = _ToastState()
        self._active_toast: Optional[NonModalAlignmentToast] = None
        self._periodic_timer: Optional[wx.Timer] = None
        self._post_timers: Dict[str, wx.Timer] = {}

    def register(self, probe: AlignmentProbe) -> None:
        self._probes[probe.probe_id] = probe

    def start(self) -> None:
        if wx is None:
            return
        if self._periodic_timer is not None:
            return
        self._periodic_timer = wx.Timer(self._frame)
        self._frame.Bind(
            wx.EVT_TIMER,
            self._on_periodic,
            self._periodic_timer)
        self._periodic_timer.Start(PERIODIC_CHECK_MS)

    def stop(self) -> None:
        if self._periodic_timer is not None:
            self._periodic_timer.Stop()
            self._periodic_timer = None
        for timer in list(self._post_timers.values()):
            timer.Stop()
        self._post_timers.clear()
        if self._active_toast is not None:
            try:
                self._active_toast.Close()
            except Exception:
                pass
            self._active_toast = None

    def notify_switch(self, probe_ids: List[str]) -> None:
        if wx is None:
            return
        for probe_id in probe_ids:
            probe = self._probes.get(probe_id)
            if probe is None:
                continue
            delay_ms = int(max(1000.0, probe.load_budget_sec * POST_SWITCH_LOAD_FACTOR * 1000.0))
            old = self._post_timers.pop(probe_id, None)
            if old is not None:
                old.Stop()

            timer = wx.Timer(self._frame)

            def _handler(event, pid=probe_id):
                event.GetTimer().Stop()
                self._post_timers.pop(pid, None)
                self.run_check(probe_ids=[pid])

            self._frame.Bind(wx.EVT_TIMER, _handler, timer)
            timer.Start(delay_ms, oneShot=True)
            self._post_timers[probe_id] = timer

    def _on_periodic(self, _event):
        self.run_check()

    def run_check(self, probe_ids: Optional[List[str]] = None) -> List[str]:
        mismatches: List[str] = []
        ids = probe_ids if probe_ids is not None else list(self._probes.keys())
        for probe_id in ids:
            probe = self._probes.get(probe_id)
            if probe is None:
                continue
            result = probe.check()
            if result is None:
                continue
            label, ui_val, runtime_val = result
            mismatches.append(f"{label}: UI={ui_val} / runtime={runtime_val}")
            try:
                probe.revert()
            except Exception:
                pass
        if mismatches:
            self._show_toast("\n".join(mismatches))
        return mismatches

    def _show_toast(self, message: str) -> None:
        if wx is None:
            return
        key = message[:240]
        now = time.monotonic()
        if (self._toast_state.last_key == key
                and (now - self._toast_state.last_mono) < TOAST_DEBOUNCE_SEC):
            return
        self._toast_state.last_key = key
        self._toast_state.last_mono = now

        def _show():
            parent = self._frame.get_dialog_parent() if hasattr(
                self._frame, "get_dialog_parent") else self._frame
            if self._active_toast is not None:
                try:
                    self._active_toast.Close()
                except Exception:
                    pass
            toast = NonModalAlignmentToast(
                parent,
                "选项已对齐 / Settings aligned",
                "检测到界面选项与运行状态不一致，已尝试恢复：\n"
                "UI/runtime mismatch detected; reverted where possible:\n\n"
                f"{message}")
            toast.Show()
            self._active_toast = toast

        wx.CallAfter(_show)
