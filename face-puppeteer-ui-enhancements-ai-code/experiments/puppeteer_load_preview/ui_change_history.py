"""Recent user control change log for preview column (last 3 entries)."""
from __future__ import annotations

from collections import deque
from typing import Callable, Deque, Iterable, List, Optional, Set

try:
    import wx
except ImportError:
    wx = None  # type: ignore

EMPTY_LINE = "—"


class UserChangeHistory:
    def __init__(self, capacity: int = 3):
        self._capacity = max(1, int(capacity))
        self._entries: Deque[str] = deque(maxlen=self._capacity)

    def add(self, message: str) -> None:
        text = " ".join(str(message or "").split())
        if not text:
            return
        if self._entries and self._entries[0] == text:
            return
        self._entries.appendleft(text)

    def lines(self, count: int = 3) -> List[str]:
        n = max(1, int(count))
        out: List[str] = []
        for i in range(n):
            if i < len(self._entries):
                out.append(self._entries[i])
            else:
                out.append(EMPTY_LINE)
        return out


def _first_line(text: str) -> str:
    return str(text or "").split("\n")[0].strip()


def _control_label(control) -> str:
    if wx is None:
        return "控件"
    try:
        label = control.GetLabel()
        if label:
            return _first_line(label)
    except Exception:
        pass
    try:
        tip = control.GetToolTipText()
        if tip:
            return _first_line(tip)
    except Exception:
        pass
    try:
        parent = control.GetParent()
        if parent is not None:
            for child in parent.GetChildren():
                if isinstance(child, wx.StaticText):
                    txt = child.GetLabel()
                    if txt:
                        return _first_line(txt)
    except Exception:
        pass
    return control.__class__.__name__


def _choice_value(control) -> str:
    idx = control.GetSelection()
    if idx < 0:
        return "?"
    try:
        return control.GetString(idx)
    except Exception:
        return str(idx)


def _bind_choice(control, record: Callable[[str], None]) -> None:
    if wx is None or not isinstance(control, wx.Choice):
        return
    name = _control_label(control)

    def _on_choice(event):
        record(f"切换 {name} → {_choice_value(control)}")
        event.Skip()

    control.Bind(wx.EVT_CHOICE, _on_choice)


def _bind_checkbox(control, record: Callable[[str], None]) -> None:
    if wx is None or not isinstance(control, wx.CheckBox):
        return
    name = _control_label(control)

    def _on_check(event):
        state = "开启" if control.GetValue() else "关闭"
        record(f"{state} {name}")
        event.Skip()

    control.Bind(wx.EVT_CHECKBOX, _on_check)


def _bind_slider(control, record: Callable[[str], None]) -> None:
    if wx is None or not isinstance(control, wx.Slider):
        return
    name = _control_label(control)
    pending: List[Optional[object]] = [None]

    def _emit():
        pending[0] = None
        record(f"调整 {name} → {control.GetValue()}")

    def _on_slider(event):
        if pending[0] is not None:
            try:
                pending[0].Stop()
            except Exception:
                pass
        pending[0] = wx.CallLater(400, _emit)
        event.Skip()

    control.Bind(wx.EVT_SLIDER, _on_slider)


def _bind_spinctrl(control, record: Callable[[str], None]) -> None:
    if wx is None:
        return
    if not isinstance(control, (wx.SpinCtrl, wx.SpinCtrlDouble)):
        return
    name = _control_label(control)

    def _on_spin(event):
        record(f"调整 {name} → {control.GetValue()}")
        event.Skip()

    control.Bind(wx.EVT_SPINCTRL, _on_spin)
    if hasattr(wx, "EVT_SPINCTRLDOUBLE"):
        control.Bind(wx.EVT_SPINCTRLDOUBLE, _on_spin)


def wire_controls_for_change_log(root, record: Callable[[str], None]) -> None:
    """Bind common wx controls under *root* to append human-readable change lines."""
    if wx is None or root is None:
        return
    seen: Set[int] = set()
    queue: List = [root]
    while queue:
        window = queue.pop(0)
        try:
            wid = window.GetId()
        except Exception:
            wid = id(window)
        if wid in seen:
            continue
        seen.add(wid)
        try:
            children = window.GetChildren()
        except Exception:
            children = ()
        queue.extend(children)
        if isinstance(window, wx.Choice):
            _bind_choice(window, record)
        elif isinstance(window, wx.CheckBox):
            _bind_checkbox(window, record)
        elif isinstance(window, wx.Slider):
            _bind_slider(window, record)
        elif isinstance(window, (wx.SpinCtrl, wx.SpinCtrlDouble)):
            _bind_spinctrl(window, record)


def wire_float_slider_controls(frame, record: Callable[[str], None]) -> None:
    """Patch FloatSliderControl instances on *frame* for debounced value logging."""
    if wx is None:
        return
    for val in list(getattr(frame, "__dict__", {}).values()):
        cls_name = type(val).__name__
        if cls_name != "FloatSliderControl":
            continue
        label = ""
        try:
            label = _first_line(val.label.GetLabel())
        except Exception:
            label = "滑块"
        digits = getattr(val, "digits", 2)
        pending: List[Optional[object]] = [None]
        original = val.change_handler

        def _make_wrapper(slider_control, lbl, digits_count, orig_handler, pend):
            def _wrapped(event):
                if orig_handler is not None:
                    orig_handler(event)

                def _emit():
                    pend[0] = None
                    try:
                        value = slider_control.GetValue()
                    except Exception:
                        value = 0
                    record(f"调整 {lbl} → {value:.{digits_count}f}")

                if pend[0] is not None:
                    try:
                        pend[0].Stop()
                    except Exception:
                        pass
                pend[0] = wx.CallLater(400, _emit)

            return _wrapped

        val.change_handler = _make_wrapper(val, label, digits, original, pending)
