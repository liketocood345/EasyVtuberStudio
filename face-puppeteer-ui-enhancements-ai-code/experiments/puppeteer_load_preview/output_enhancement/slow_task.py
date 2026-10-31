"""Non-blocking progress UI for slow enhancement model loads (f-057)."""
from __future__ import annotations
from portable_process_env import debug_log_path
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

import threading
import time
from typing import Callable, Optional

try:
    import wx
except ImportError:
    wx = None  # type: ignore

ProgressFn = Callable[[str, float], None]


class SlowTaskProgressDialog:
    """Kept as a no-op: never create a modal/progress window that blocks the UI."""

    def __init__(self, parent, title: str = "Loading models..."):
        self._parent = parent
        self._title = title
        # bh-2 26.10.29 20:56 s
        self._dialog = None
        # bh-2 26.10.29 20:56 e

    def update(self, message: str, fraction: float) -> None:
        return

    def close(self) -> None:
        return


# EVS-DESIGN-AUDIT EVS-A083 BEGIN
# 设计[f-057] [部分符合]
# task 在后台线程运行；禁止 APP_MODAL 进度框锁住主界面。父窗关闭后的排队回调安全性还需验证。
# 历史 bug 热点 #2：加载角色后的 NN 预热不得弹出拒绝关闭的窗口。
# EVS-DESIGN-AUDIT EVS-A083 END
def run_slow_task(
        parent,
        title: str,
        task: Callable[[ProgressFn], None],
        on_complete: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None) -> None:
    """Run task in background thread; progress updates on UI thread."""

    dialog = SlowTaskProgressDialog(parent, title=title)
    # #region agent log
    try:
        import json as _json, time as _time
        open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({"sessionId": "86a17c", "runId": "post-fix", "hypothesisId": "A", "location": "slow_task.py:run_slow_task", "message": "enhancement warmup started without dialog", "data": {"title": str(title), "dialog": False}, "timestamp": int(_time.time() * 1000)}) + "\n")
    except Exception:
        pass
    # #endregion

    def _progress(msg: str, frac: float) -> None:
        # #region agent log
        try:
            import json as _json, time as _time
            open(debug_log_path('86a17c'), "a", encoding="utf-8").write(_json.dumps({"sessionId": "86a17c", "runId": "post-fix", "hypothesisId": "B", "location": "slow_task.py:_progress", "message": "enhancement warmup progress", "data": {"msg": str(msg), "frac": float(frac), "dialog": False}, "timestamp": int(_time.time() * 1000)}) + "\n")
        except Exception:
            pass
        # #endregion
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
