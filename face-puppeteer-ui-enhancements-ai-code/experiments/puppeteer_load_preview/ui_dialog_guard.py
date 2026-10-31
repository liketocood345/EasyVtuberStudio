"""Rate-limited wx modal dialogs (high-risk: never spam from timers)."""
from __future__ import annotations
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

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


# EVS-DESIGN-AUDIT EVS-A072 BEGIN
# 设计[f-023, UI-A×04] [静态符合（此入口限频）；全局待核]
# 按 key/时间限制对话框，同类错误一秒超过一次属高危。只保护经过此函数的调用，直接 wx.MessageBox/启动器 MessageBox 不能据此视为全局限频。
# 历史 bug 热点 #2,#5：仅为回归关联，非声称本次故障已复现。
# EVS-DESIGN-AUDIT EVS-A072 END
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
