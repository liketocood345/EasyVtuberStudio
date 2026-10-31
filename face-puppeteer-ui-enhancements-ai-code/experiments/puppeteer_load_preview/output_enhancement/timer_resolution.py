"""Scoped Windows timer resolution for high-cadence buffered presentation."""
from __future__ import annotations
import ctypes
import sys
import threading

class TimerResolutionLease:
    def __init__(self):
        self._lock=threading.Lock();self._active=False;self._winmm=None
        if sys.platform=='win32':
            try:
                self._winmm=ctypes.WinDLL('winmm')
                self._active=self._winmm.timeBeginPeriod(1)==0
            except (OSError,AttributeError):pass
    def close(self):
        with self._lock:
            if self._active:
                self._active=False;self._winmm.timeEndPeriod(1)
    def __del__(self):
        self.close()
