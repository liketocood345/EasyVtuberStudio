"""f-063: revert UI controls when a user switch fails to apply."""
from __future__ import annotations
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Optional

try:
    import wx
except ImportError:
    wx = None  # type: ignore

SnapshotFn = Callable[[], Any]
ApplyFn = Callable[[], None]
RevertFn = Callable[[Any], None]
ValidateFn = Callable[[], tuple[bool, str]]


@dataclass
class ChoiceSnapshot:
    control_id: int
    selection: int


def is_blocked(frame) -> bool:
    return int(getattr(frame, "_ui_switch_guard_depth", 0)) > 0


@contextmanager
def block_events(frame) -> Iterator[None]:
    depth = int(getattr(frame, "_ui_switch_guard_depth", 0))
    frame._ui_switch_guard_depth = depth + 1
    try:
        yield
    finally:
        frame._ui_switch_guard_depth = max(0, depth)


def snapshot_choice(control) -> Optional[ChoiceSnapshot]:
    if control is None or wx is None or not isinstance(control, wx.Choice):
        return None
    return ChoiceSnapshot(control_id=control.GetId(), selection=control.GetSelection())


def restore_choice(control, snap: Optional[ChoiceSnapshot]) -> None:
    if control is None or snap is None or wx is None:
        return
    if not isinstance(control, wx.Choice):
        return
    if control.GetId() != snap.control_id:
        return
    if control.GetSelection() != snap.selection:
        control.SetSelection(snap.selection)


# EVS-DESIGN-AUDIT EVS-A073 BEGIN
# 设计[f-063] [静态符合（封装路径）；全局部分符合]
# 封装负责失败时恢复快照并阻止递归事件，但只有使用此封装的开关受保护；不能由工具函数存在推出每个功能切换都覆盖。
# 历史 bug 热点 #2：仅为回归关联，非声称本次故障已复现。
# EVS-DESIGN-AUDIT EVS-A073 END
def run_guarded_switch(
        frame,
        *,
        snapshot: SnapshotFn,
        apply_fn: ApplyFn,
        revert_fn: RevertFn,
        validate: Optional[ValidateFn] = None,
        on_fail: Optional[Callable[[str], None]] = None) -> bool:
    """Apply a user switch; revert snapshot when validate/apply fails."""
    if is_blocked(frame):
        return True
    snap = snapshot()
    try:
        apply_fn()
        if validate is not None:
            ok, reason = validate()
            if not ok:
                with block_events(frame):
                    revert_fn(snap)
                if on_fail and reason:
                    on_fail(reason)
                return False
        return True
    except Exception as exc:
        with block_events(frame):
            revert_fn(snap)
        if on_fail:
            on_fail(str(exc))
        return False
