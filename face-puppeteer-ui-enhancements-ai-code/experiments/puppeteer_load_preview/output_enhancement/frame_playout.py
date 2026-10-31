"""Bounded timestamp-based playout, independent from model/compose cadence.

Smoothness-first policy: use bounded buffering for uniform intermediate frames,
not unbounded callback queues. Keep 250ms of the 1s user limit for capture/UI.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
import threading
from typing import Any,Optional

@dataclass(frozen=True)
class TimedFrame:
    rgba: Any
    source_time: float
    serial: int
    generated: bool

class TimedFramePlayout:
    def __init__(self,delay_seconds=.45,max_age_seconds=.75,max_frames=96,max_buffer_bytes=512*1024*1024):
        if not 0<=delay_seconds<max_age_seconds<=1.:raise ValueError('Invalid playout latency budget')
        self.delay_seconds=float(delay_seconds);self.max_age_seconds=float(max_age_seconds);self.max_frames=max(2,int(max_frames))
        self.max_buffer_bytes=max(1,int(max_buffer_bytes))
        self._frames=deque();self._lock=threading.Lock();self._serial=0;self._last_source=float('-inf');self.dropped=0
    def clear(self):
        with self._lock:self._frames.clear();self._last_source=float('-inf')
    def push_span(self,previous_time,current_time,frames):
        if not frames:return
        if current_time<=previous_time:raise ValueError('Frame span timestamps must increase')
        with self._lock:
            count=len(frames)
            for i,rgba in enumerate(frames):
                source=previous_time+(current_time-previous_time)*(i+1)/count
                if source<=self._last_source:continue
                self._serial+=1;self._frames.append(TimedFrame(rgba,float(source),self._serial,i<count-1));self._last_source=source
            frame_bytes=max(1,max(getattr(x.rgba,"nbytes",1) for x in self._frames)) if self._frames else 1
            limit=max(2,min(self.max_frames,self.max_buffer_bytes//frame_bytes))
            while len(self._frames)>limit or (self._frames and self._frames[-1].source_time-self._frames[0].source_time>self.max_age_seconds):self._frames.popleft();self.dropped+=1
    def pop_due(self,now):
        goal=float(now)-self.delay_seconds;chosen=None
        with self._lock:
            while self._frames and self._frames[0].source_time<=goal:
                item=self._frames.popleft()
                if now-item.source_time>self.max_age_seconds:self.dropped+=1;continue
                if chosen is not None:self.dropped+=1
                chosen=item
        return chosen
    def next_due(self):
        with self._lock:return self._frames[0].source_time+self.delay_seconds if self._frames else None
    def __len__(self):
        with self._lock:return len(self._frames)
