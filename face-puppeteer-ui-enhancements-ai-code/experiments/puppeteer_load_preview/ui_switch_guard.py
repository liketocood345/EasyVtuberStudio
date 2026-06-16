"""f-063: revert UI controls when a user switch fails to apply."""
from __future__ import annotations

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
