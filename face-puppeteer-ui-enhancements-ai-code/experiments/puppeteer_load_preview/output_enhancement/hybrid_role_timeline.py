"""f-070: pose-timestamped role playout with optional spare-budget RIFE.

Real inference never waits for this worker. Geometry/GIF remain in final compose.
No RGB crossfade and no whole-scene neural interpolation.
"""
from dataclasses import dataclass
from collections import deque
import threading,time
import numpy as np
from output_enhancement.buffered_rife import motion_discontinuity
from output_enhancement.gpu_work_gate import SHARED_GPU_GATE

@dataclass(frozen=True)
class RoleSample:
    stamp:float
    rgba:object
    pose:tuple
    method:str='real'

class HybridRoleTimeline:
    def __init__(self,delay=.45):
        self.delay=float(delay);self._condition=threading.Condition();self._real=deque(maxlen=48);self._mids=deque(maxlen=64);self._pending=None;self._stop=False;self._backend=None;self._target=30.;self._real_hz=30.;self._next_nn=0.;self._last_goal=float('-inf');self.generated=0;self.rejected=0;self.budget_skipped=0;self.last_error=None;self._generation=0
        self._thread=threading.Thread(target=self._work,name='hybrid-role-rife',daemon=True);self._thread.start()
    def configure(self,backend,target,real_hz):
        with self._condition:self._backend=backend;self._target=max(1.,float(target));self._real_hz=max(1.,float(real_hz))
    def clear(self):
        with self._condition:
            self._generation+=1;self._real.clear();self._mids.clear();self._pending=None;self._last_goal=float('-inf');self._selected=None
    def offer(self,rgba,stamp,pose):
        image=np.array(rgba,dtype=np.uint8,copy=True,order='C');image.flags.writeable=False;item=RoleSample(float(stamp),image,tuple(pose))
        with self._condition:
            if self._stop or self._real and item.stamp<=self._real[-1].stamp:return
            previous=self._real[-1] if self._real else None;self._real.append(item)
            while self._real and item.stamp-self._real[0].stamp>1.5:self._real.popleft()
            if previous is not None and self._backend is not None:
                self._pending=(self._generation,previous,item,self._backend);self._condition.notify()
    def _work(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda:self._stop or self._pending is not None)
                if self._stop:return
                generation,a,b,backend=self._pending;self._pending=None;target=self._target;real_hz=self._real_hz
            span=b.stamp-a.stamp
            multiplier=2 if span*target<2.5 else 3
            model=SHARED_GPU_GATE.service_ms('tha3')
            cost=SHARED_GPU_GATE.service_ms('rife_frame%d'%multiplier)
            # Reserve real inference first; optional neural work only uses spare service.
            spare=min(100.,max(0.,950.-(model or 1000./real_hz)*real_hz))
            cost=max(1.,cost or (12. if multiplier==2 else 20.))
            rate=min(real_hz,spare/cost)
            now=time.perf_counter()
            if target<=real_hz*1.03 or rate<.5 or now<self._next_nn:
                self.budget_skipped+=1;continue
            if now-b.stamp>self.delay-.08 or motion_discontinuity(a.rgba,b.rgba,span):
                self.rejected+=1;continue
            self._next_nn=now+1./rate
            try:
                frames=backend.interpolate_rife(a.rgba,b.rgba,multiplier,fp16=False)
                if len(frames)!=multiplier:raise ValueError('Incomplete hybrid RIFE span')
                # Reject alpha holes inside regions opaque in both real endpoints.
                import cv2
                opaque=((a.rgba[:,:,3]>240)&(b.rgba[:,:,3]>240)).astype(np.uint8)
                interior=cv2.erode(opaque,np.ones((3,3),np.uint8))>0
                limit=max(4,int(interior.sum()*.001))
                if any(frame.shape!=a.rgba.shape or np.count_nonzero(interior&(frame[:,:,3]<192))>limit for frame in frames[:-1]):
                    self.rejected+=1;continue
                mids=[]
                for i,frame in enumerate(frames[:-1]):
                    u=(i+1)/multiplier;arr=np.array(frame,dtype=np.uint8,copy=True,order='C');arr.flags.writeable=False
                    mids.append(RoleSample(a.stamp+span*u,arr,tuple(x+(y-x)*u for x,y in zip(a.pose,b.pose)),'rife%d'%multiplier))
                with self._condition:
                    if not self._stop and generation==self._generation:
                        self._mids.extend(mids);self.generated+=len(mids)
            except Exception as exc:self.last_error=str(exc)
    def sample(self,now):
        with self._condition:
            goal=max(self._last_goal,float(now)-self.delay);self._last_goal=goal
            # Always choose by pose time, never by NN completion order.
            values=[x for x in self._real if x.stamp<=goal]+[x for x in self._mids if x.stamp<=goal]
            if not values:return None
            chosen=max(values,key=lambda x:x.stamp)
            # A late NN result must not make the displayed pose clock go backwards.
            previous=getattr(self,'_selected',None)
            if previous is not None and chosen.stamp<previous.stamp:return previous
            self._selected=chosen;return chosen
    def snapshot(self):
        with self._condition:return dict(delay_ms=self.delay*1000.,real_frames=len(self._real),generated=self.generated,rejected=self.rejected,budget_skipped=self.budget_skipped,last_error=self.last_error)
    def close(self):
        with self._condition:self._stop=True;self._pending=None;self._condition.notify_all()
        self._thread.join(timeout=5.);self.clear();return not self._thread.is_alive()
