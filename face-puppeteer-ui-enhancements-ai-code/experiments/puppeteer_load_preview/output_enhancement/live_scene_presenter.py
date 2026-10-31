"""f-070: one bounded CPU scene worker, independent of model/UI cadence.

Uses existing full-resolution scene geometry and pixel algorithms. No camera
capture, synthetic poses, model substitution or hidden resolution reduction.
"""
from collections import deque
import os
import threading,time
from output_enhancement.scene_snapshot import ParallelSceneRenderer

class LiveScenePresenter:
    def __init__(self,callback):
        self.renderer=ParallelSceneRenderer(workers=2 if (os.cpu_count() or 1)>=8 else 1,gpu_composition=False)
        self.renderer._snapshots=deque(maxlen=8)
        self._callback=callback;self._condition=threading.Condition()
        self._packet=None;self._closed=False;self.last_error=None
        self.render_ms=deque(maxlen=120);self.completed=0
        self._thread=threading.Thread(target=self._run,daemon=True,name='live-scene-present')
        self._thread.start()
    def offer(self,snapshot,rgba,hz):
        with self._condition:
            if self._closed:return
            self._packet=(snapshot,rgba,max(1.,min(240.,float(hz))))
            self._condition.notify()
    def _run(self):
        due=0.;serial=0;last_delivered=0.;pending=deque()
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda:self._closed or self._packet is not None)
                    if self._closed:return
                    packet=self._packet
                now=time.perf_counter()
                # Geometry/springs are prepared in order; only independent pixels
                # overlap. At most two frames exist in flight, delivered in order.
                if pending:
                    snapshot,stamp,period,job=pending[0]
                    if job.done() and now>=stamp+period and now>=last_delivered+period:
                        pending.popleft();output=job.result()
                        self.render_ms.append((now-stamp)*1000.)
                        with self._condition:
                            if self._closed:return
                        if now-snapshot.stamp<=.75:
                            serial+=1;last_delivered=now
                            self._callback(output,serial,stamp);self.completed+=1
                        continue
                snapshot,rgba,hz=packet;period=1./hz
                if now>=due and len(pending)<2:
                    start=time.perf_counter()
                    self.renderer.submit_snapshot(snapshot)
                    prepared=self.renderer._prepare(rgba,start)
                    job=self.renderer._pool.submit(self.renderer._render,prepared)
                    pending.append((snapshot,start,period,job))
                    due=start+period
                    continue
                wake=due if len(pending)<2 else now+.002
                if pending:
                    snapshot,stamp,present_period,job=pending[0]
                    ready=max(stamp+present_period,last_delivered+present_period)
                    wake=min(wake,ready if job.done() else now+.002)
                with self._condition:
                    if self._closed:return
                    self._condition.wait(timeout=max(.001,min(.02,wake-time.perf_counter())))
        except Exception as exc:
            self.last_error=repr(exc)
        finally:
            for _,_,_,job in pending:job.cancel()
            self.renderer.close()
    def close(self):
        with self._condition:
            self._closed=True;self._packet=None;self._condition.notify_all()
        if self._thread is not threading.current_thread():self._thread.join(timeout=1.)
