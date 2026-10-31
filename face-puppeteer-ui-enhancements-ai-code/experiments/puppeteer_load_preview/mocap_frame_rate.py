"""f-073: fixed/adaptive cadence for the existing face detector.

No input synthesis; latest real camera frames only. Phase accumulation avoids
halving 30Hz when a nominal 33ms wx timer fires just before 33.333ms.
"""
from collections import deque
import math,threading,time

class MocapFrameRatePolicy:
    def __init__(self,mode='fixed',fixed_fps=30):
        self._lock=threading.RLock();self.costs=deque(maxlen=60);self._native_intervals=deque(maxlen=60);self._native_last=0.;self._due=0.;self._changed=0.;self._adaptive=30.
        self.configure(mode,fixed_fps)
    def configure(self,mode,fixed_fps):
        with self._lock:
            self.mode='adaptive' if mode=='adaptive' else 'fixed'
            try:self.fixed_fps=max(1,min(120,int(fixed_fps)))
            except (ValueError,TypeError):self.fixed_fps=30
            self._due=0.
    def observe(self,elapsed_ms):
        if math.isfinite(elapsed_ms)and elapsed_ms>0:
            with self._lock:self.costs.append(float(elapsed_ms))
    def observe_native_arrival(self,now=None):
        # Native OSF owns its detector; adapt its output pacer to raw UDP arrival
        # cadence, never to the already throttled UI keyframe count.
        now=time.perf_counter() if now is None else float(now)
        with self._lock:
            if self._native_last and 0.<now-self._native_last<=1.:
                self._native_intervals.append((now-self._native_last)*1000.)
            self._native_last=now
    def effective_hz(self,now=None):
        now=time.perf_counter() if now is None else float(now)
        with self._lock:
            if self.mode=='fixed':return float(self.fixed_fps)
            native=self._native_last>0. and 0.<=now-self._native_last<=1.
            samples=self._native_intervals if native else self.costs
            if len(samples)>=6 and now-self._changed>=.75:
                values=sorted(samples);p90=values[min(len(values)-1,int((len(values)-1)*.9))]
                desired=max(5.,min(60.,(1000. if native else 900.)/max(1.,p90)))
                if abs(desired-self._adaptive)>=max(2.,self._adaptive*.1):
                    self._adaptive=min(desired,self._adaptive*1.2) if desired>self._adaptive else desired
                    self._changed=now
            return self._adaptive
    def is_due(self,now=None):
        now=time.perf_counter()if now is None else float(now)
        with self._lock:
            hz=self.effective_hz(now);period=1./hz
            if self._due<=0 or now-self._due>period*2:self._due=now
            if now+.002<self._due:return False
            self._due+=period
            return True
    def snapshot(self):
        with self._lock:return dict(mode=self.mode,fixed_fps=self.fixed_fps,effective_hz=self.effective_hz(),service_ms=sum(self.costs)/len(self.costs) if self.costs else None)
