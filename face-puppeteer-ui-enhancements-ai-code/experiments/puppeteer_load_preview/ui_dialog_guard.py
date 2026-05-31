"""Rate-limited wx modal dialogs (high-risk: never spam from timers)."""
from __future__ import annotations

import time
from typing import Optional

import wx

# Dialogs must not appear more than once per second for the same key.
MIN_DIALOG_INTERVAL_SEC = 1.0

_last_shown_mono: dict[str, float] = {}
_session_counts: dict[str, int] = {}


def _dialog_key(title: str, message: str, explicit_key: Optional[str]) -> str:
    if explicit_key:
        return explicit_key
    return f"{title}\0{message[:240]}"


def show_rate_limited_message(
        parent: wx.Window,
        message: str,
        title: str,
        *,
        style: int = wx.OK | wx.ICON_WARNING,
        dialog_key: Optional[str] = None,
        max_per_session: int = 1,
        min_interval_sec: float = MIN_DIALOG_INTERVAL_SEC) -> bool:
    """Show a modal message at most `max_per_session` times per key and `min_interval_sec` apart.

    Returns True if a dialog was shown, False if suppressed.
    """
    key = _dialog_key(title, message, dialog_key)
    count = _session_counts.get(key, 0)
    if count >= max(1, max_per_session):
        return False
    now = time.monotonic()
    last = _last_shown_mono.get(key)
    if last is not None and (now - last) < max(0.0, min_interval_sec):
        return False
    dialog = wx.MessageDialog(parent, message, title, style)
    try:
        dialog.ShowModal()
    finally:
        dialog.Destroy()
    _last_shown_mono[key] = now
    _session_counts[key] = count + 1
    return True


def reset_dialog_guard_for_tests() -> None:
    _last_shown_mono.clear()
    _session_counts.clear()
