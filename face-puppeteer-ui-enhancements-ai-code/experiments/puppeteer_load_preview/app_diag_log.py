"""Minimal one-line stderr diagnostics (no traceback spam)."""
from __future__ import annotations

import sys
import threading

_seen: set[str] = set()
_lock = threading.Lock()


def log_error(message: str) -> None:
    text = str(message or "").strip().splitlines()
    if not text:
        return
    print(text[0][:500], file=sys.stderr)


def log_once(key: str, message: str) -> None:
    with _lock:
        if key in _seen:
            return
        _seen.add(key)
    log_error(message)


def reset_seen() -> None:
    with _lock:
        _seen.clear()
