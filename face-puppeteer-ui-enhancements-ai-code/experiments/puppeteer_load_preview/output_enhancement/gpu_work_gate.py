"""Fair FIFO access for GPU jobs sharing the default physical adapter.

EVS-PERF-20261029: overlapping CUDA THA3 and DirectML SR reduced real inference
below 12Hz in experiments. Serialize bounded jobs rather than let NN workers
monopolize the adapter. CPU tracking and wx presentation do not acquire this gate.
"""
from __future__ import annotations
from contextlib import contextmanager
from collections import deque
import threading
import time

class GpuWorkGate:
    def __init__(self):
        self._condition=threading.Condition();self._hi=deque();self._lo=deque();self._active=False;self._timings={}
    @contextmanager
    def job(self,kind="gpu"):
        token=object()
        # bh-1 26.10.30 14:04 s
        hi=str(kind).startswith("tha")
        queue=self._hi if hi else self._lo
        with self._condition:
            queue.append(token)
            try:
                self._condition.wait_for(lambda:not self._active and (
                    (hi and self._hi and self._hi[0] is token) or
                    ((not hi) and (not self._hi) and self._lo and self._lo[0] is token)))
                queue.popleft();self._active=True
            except BaseException:
                if token in queue:
                    queue.remove(token)
                self._condition.notify_all();raise
        # bh-1 26.10.30 14:04 e
        started=time.perf_counter()
        try:yield
        finally:
            elapsed=(time.perf_counter()-started)*1000.0
            with self._condition:
                self._timings.setdefault(str(kind),deque(maxlen=120)).append(elapsed)
                self._active=False;self._condition.notify_all()


    def observe(self,kind,elapsed_ms):
        with self._condition:
            self._timings.setdefault(str(kind),deque(maxlen=120)).append(float(elapsed_ms))

    def service_ms(self,kind):
        with self._condition:values=list(self._timings.get(str(kind),()))
        if len(values)<8:return None
        # The 450ms playout buffer absorbs individual tails. Sustained mean
        # service controls throughput; age bounds still prevent runaway queues.
        return sum(values)/len(values)

    def p90_ms(self,kind):
        with self._condition:values=sorted(self._timings.get(str(kind),()))
        if len(values)<8:return None
        return values[min(len(values)-1,int((len(values)-1)*.9))]

    def snapshot(self):
        with self._condition:return {key:list(values) for key,values in self._timings.items()}

    def reset_statistics(self):
        with self._condition:self._timings.clear()

SHARED_GPU_GATE=GpuWorkGate()
