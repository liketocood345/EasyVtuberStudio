"""Threaded, bounded RIFE playout for smooth output within a one-second budget.

Pure arrays only. The callback must be thread-safe (the ULW host already is).
No wx widgets or GUI-state reads are allowed on these workers.
"""
from __future__ import annotations
import queue
import threading
import time
import numpy as np
from output_enhancement.frame_playout import TimedFramePlayout
from output_enhancement.timer_resolution import TimerResolutionLease

def motion_discontinuity(previous,current,span):
    """Conservative RIFE guard for sparse or strongly displaced endpoints.

    f-070: retain intact endpoints instead of inventing torn intermediate faces.
    Sample premultiplied color/alpha so invisible RGB cannot trigger the guard.
    """
    if span > .15:return True
    a=previous[::8,::8].astype(np.float32);b=current[::8,::8].astype(np.float32)
    aa=a[:,:,3:4]/255.;ba=b[:,:,3:4]/255.
    union=np.maximum(aa,ba).sum()
    overlap=np.minimum(aa,ba).sum()/max(1.e-6,union) if union>0 else 1.
    visible=np.maximum(aa,ba)[:,:,0]>.1
    error=np.abs(a[:,:,:3]*aa-b[:,:,:3]*ba).mean(axis=2)
    return bool(overlap<.85 or (visible.any() and float(error[visible].mean())>18.))

class BufferedRifePresenter:
    def __init__(self,backend,multiplier,callback,*,delay_seconds=.45,transform_batch=None,preprocess_frame=None):
        self._timer_lease=TimerResolutionLease()
        self.backend=backend;self.multiplier=int(multiplier);self._requested_multiplier=int(multiplier);self.callback=callback
        owner=getattr(transform_batch,"__self__",None)
        self._async_owner=owner if owner is not None and getattr(owner,"gpu_backend",None) is not None else None
        self._async_ready=queue.Queue(maxsize=12)
        self.preprocess_frame=preprocess_frame
        self.transform_batch=transform_batch;self.transform_ms=[]
        self.playout=TimedFramePlayout(delay_seconds=delay_seconds,max_age_seconds=.75,max_frames=256)
        self._inputs=queue.Queue(maxsize=8);self._stop=threading.Event();self.last_error=None;self.input_dropped=0;self.motion_guard_spans=0
        self._threads=[threading.Thread(target=self._process,daemon=True,name='rife-process'),threading.Thread(target=self._present,daemon=True,name='rife-playout')]
        if self._async_owner is not None:self._threads.append(threading.Thread(target=self._complete_scene_frames,daemon=True,name="scene-complete"))
        for thread in self._threads:thread.start()
    def request_multiplier(self,multiplier):
        value=int(multiplier)
        if value not in (1,2,3,4):raise ValueError("Unsupported frame multiplier")
        self._requested_multiplier=value

    def submit(self,rgba,source_time):
        if self._stop.is_set():return
        item=(float(source_time),np.ascontiguousarray(rgba,dtype=np.uint8).copy())
        try:self._inputs.put_nowait(item)
        except queue.Full:
            try:self._inputs.get_nowait();self.input_dropped+=1
            except queue.Empty:pass
            self._inputs.put_nowait(item)
    def _queue_transformed(self,frames,old_stamp,stamp):
        if self._async_owner is not None:
            started=time.perf_counter()
            jobs=self._async_owner.enqueue_batch(frames,old_stamp,stamp,stop_event=self._stop)
            if self._stop.is_set():return
            if len(jobs)!=len(frames):raise RuntimeError('Scene transform batch incomplete')
            while not self._stop.is_set():
                try:self._async_ready.put((old_stamp,stamp,jobs,started),timeout=.02);return
                except queue.Full:continue
        if self.transform_batch is not None:
            before=time.perf_counter();frames=self.transform_batch(frames,old_stamp,stamp)
            self.transform_ms.append((time.perf_counter()-before)*1000.);self.transform_ms=self.transform_ms[-120:]
        if not self._stop.is_set():self.playout.push_span(old_stamp,stamp,frames)

    def _complete_scene_frames(self):
        from concurrent.futures import TimeoutError
        try:
            while not self._stop.is_set():
                try:old_stamp,stamp,jobs,started=self._async_ready.get(timeout=.02)
                except queue.Empty:continue
                frames=[]
                for job in jobs:
                    while not self._stop.is_set():
                        try:frames.append(job.result(timeout=.02));break
                        except TimeoutError:continue
                    if self._stop.is_set():return
                self.transform_ms.append((time.perf_counter()-started)*1000.);self.transform_ms=self.transform_ms[-120:]
                if not self._stop.is_set():self.playout.push_span(old_stamp,stamp,frames)
        except Exception as exc:
            self.last_error='%s: %s'%(type(exc).__name__,exc);self._stop.set();self.playout.clear();self._timer_lease.close()

    def _process(self):
        previous=None
        try:
            while not self._stop.is_set():
                try:stamp,frame=self._inputs.get(timeout=.02)
                except queue.Empty:continue
                if time.perf_counter()-stamp>.65:self.input_dropped+=1;continue
                multiplier=self._requested_multiplier
                self.multiplier=multiplier
                if self.preprocess_frame is not None:frame=self.preprocess_frame(frame)
                if previous is None or previous[1].shape!=frame.shape:
                    self.playout.clear();self._queue_transformed([frame],stamp-.001,stamp);previous=(stamp,frame);continue
                old_stamp,old_frame=previous
                if stamp<=old_stamp:continue
                if multiplier>1 and motion_discontinuity(old_frame,frame,stamp-old_stamp):
                    self.motion_guard_spans+=1
                    frames=[old_frame]*(multiplier-1)+[frame]
                else:
                    frames=([frame] if multiplier==1 else self.backend.interpolate_rife(old_frame,frame,multiplier,fp16=False))
                if len(frames)!=multiplier:raise RuntimeError('RIFE did not produce the requested intermediate frames')
                self._queue_transformed(frames,old_stamp,stamp);previous=(stamp,frame)
        except Exception as exc:
            self.last_error='%s: %s'%(type(exc).__name__,exc);self._stop.set();self.playout.clear();self._timer_lease.close()
    def _present(self):
        try:
            while not self._stop.is_set():
                frame=self.playout.pop_due(time.perf_counter())
                if frame is not None and not self._stop.is_set():self.callback(frame.rgba,frame.serial,frame.source_time)
                due=self.playout.next_due();wait=.002 if due is None else max(.0002,min(.005,due-time.perf_counter()))
                self._stop.wait(wait)
        except Exception as exc:
            self.last_error='%s: %s'%(type(exc).__name__,exc);self._stop.set();self._timer_lease.close()
    def close(self):
        self._stop.set();self.playout.clear()
        for thread in self._threads:
            if thread is not threading.current_thread():thread.join(timeout=3.)
        self._timer_lease.close()
        while not self._inputs.empty():
            try:self._inputs.get_nowait()
            except queue.Empty:break
        while not self._async_ready.empty():
            try:self._async_ready.get_nowait()
            except queue.Empty:break
        return all(not thread.is_alive() for thread in self._threads)
