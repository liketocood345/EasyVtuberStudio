"""Adaptive target FPS policy. Missing capacity is a normal, silent outcome.

EVS target-FPS requirement, 2026-10-30: maximize useful real endpoints among
all candidates; reaching the requested cadence is secondary. No model/precision/resolution substitution and no RGB crossfade.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
from collections import deque
import math,threading,time

TARGET_FPS_DEFAULT=60
TARGET_FPS_MAX=240

def normalize_target_fps(value):
    try:value=int(value)
    except (TypeError,ValueError,OverflowError):return TARGET_FPS_DEFAULT
    return max(1,min(TARGET_FPS_MAX,value))

def normalize_target_enabled(value):
    if isinstance(value,str):return value.strip().lower() in ('true','1','yes','on')
    return bool(value)

@dataclass(frozen=True)
class FrameRatePlan:
    source_hz: float
    model_hz: float
    multiplier: int
    output_hz: float
    method: str
    reaches_target: bool
    presentation_hz: float=0.

def choose_plan(target,model_ms,compose_ms,nn_costs=None,output_ceilings=None,scene_mode=False,gpu_compose_ms=0.):
    target=normalize_target_fps(target);model=max(.1,float(model_ms or 1000/30));compose=max(.1,float(compose_ms or .1));plans=[]
    for mult in (1,2,3,4):
        cost=(nn_costs or {}).get(mult)
        if mult>1 and not cost:continue
        gpu,work=(0.,0.) if mult==1 else cost
        # Timings are measured with face tracking and streaming load present.
        # Do not subtract whole-GPU utilization a second time.
        model_hz=None
        if scene_mode and mult==1:
            source=min(float(target),950./compose)
            if gpu_compose_ms>0:
                reserve=.9*min(float(target),950./(model+gpu_compose_ms))*model
                source=min(source,max(.05,(950.-reserve)/gpu_compose_ms))
            model_hz=min(source,max(.05,(950.-source*gpu_compose_ms)/model))
        else:
            source=min(float(target),target/mult,950./(model+gpu+mult*gpu_compose_ms),950./compose)
            if scene_mode:work+=compose*mult
            if work>0:source=min(source,900./work)
        ceiling=(output_ceilings or {}).get(mult)
        if ceiling is not None:
            source=min(source,ceiling/mult)
            if scene_mode and mult==1:model_hz=min(source,max(.05,(950.-source*gpu_compose_ms)/model))
        source=max(.05,source);out=source*mult
        real=source if model_hz is None else min(source,model_hz)
        method='scene' if mult==1 and source>real+.1 else 'pose' if mult==1 and real>15 else 'real' if mult==1 else 'rife'
        motion_hz=real if mult==1 else out
        plans.append(FrameRatePlan(source,real,mult,motion_hz,method,motion_hz>=target*.995,out))
    # Never sacrifice real inference merely to hit an interpolated FPS count.
    # f-070 correction: real inference has priority even when interpolation
    # could numerically reach the target with fewer real endpoints.
    return max(plans,key=lambda p:(p.model_hz,p.reaches_target,p.output_hz,-p.multiplier))

class TargetFrameRateController:
    def __init__(self):
        self._lock=threading.RLock();self._compose=deque(maxlen=120);self._costs={};self._disabled=set();self._plan=None;self._changed=0.;self._last_eval=0.;self._probe=None;self._stop=threading.Event();self._probe_shape=None;self._observed=[];self._ceilings={};self._method_since=0.;self._last_feedback=0.;self.scene_mode=False;self.gpu_compose_ms=0.;self._baseline_model_ms=None;self._baseline_fps=0.;self._mode_penalties={};self._rejections={};self.last_probe_error=None
    def observe_compose(self,elapsed_ms):
        if math.isfinite(elapsed_ms) and elapsed_ms>0:
            with self._lock:self._compose.append(float(elapsed_ms))
    def plan(self,target,model_ms):
        now=time.perf_counter()
        with self._lock:
            if self._plan is not None and now-self._last_eval<1.:return self._plan
            self._last_eval=now;compose=sum(self._compose)/len(self._compose) if self._compose else .1
            costs={k:v for k,v in self._costs.items() if k not in self._disabled}
            from output_enhancement.gpu_work_gate import SHARED_GPU_GATE
            current_mult=self._plan.multiplier if self._plan is not None else 1
            if self._baseline_model_ms is None:self._baseline_model_ms=model_ms
            history=SHARED_GPU_GATE.snapshot().get('tha3',[]) or SHARED_GPU_GATE.snapshot().get('tha4',[])
            probe_running=self._probe is not None and self._probe.is_alive()
            if current_mult==1 and now-self._method_since>3. and not probe_running and len(history)>=8:
                self._baseline_model_ms=sum(history[-8:])/8
            elif current_mult>1 and len(history)>=8:
                self._mode_penalties[current_mult]=max(0.,sum(history[-8:])/8-self._baseline_model_ms)
            for mult in list(costs):
                gpu=SHARED_GPU_GATE.service_ms('rife_frame%d'%mult)
                work=SHARED_GPU_GATE.service_ms('rife_work%d'%mult)
                if gpu is not None and work is not None:costs[mult]=(gpu,work)
                costs[mult]=(costs[mult][0]+self._mode_penalties.get(mult,0.),costs[mult][1])
            window=[row for row in self._observed if now-row[0]<=3.]
            if (self._plan is not None and now-self._method_since>8.
                    and now-self._last_feedback>4. and len(window)>8
                    and window[-1][0]-window[0][0]>2.):
                achieved=(len(window)-1)/(window[-1][0]-window[0][0])
                ages=sorted(age for _,age in window)
                late=ages[int((len(ages)-1)*.9)]>.65
                mult=self._plan.multiplier
                if mult==1 and not late:
                    self._baseline_fps=max(self._baseline_fps,achieved)
                if mult>1 and self._baseline_fps>0 and achieved<self._baseline_fps*.9:
                    self._disabled.add(mult);costs.pop(mult,None)
                    self._rejections[mult]=dict(reason='Observed output below real-frame baseline',achieved_fps=achieved,baseline_fps=self._baseline_fps)
                elif late or achieved<self._plan.output_hz*.85:
                    self._ceilings[mult]=max(.05,achieved*.95)
                elif mult in self._ceilings:
                    self._ceilings[mult]=min(120.,self._ceilings[mult]*1.08)
                self._last_feedback=now
            if current_mult==1 and len(window)>8 and window[-1][0]-window[0][0]>2. and not probe_running:
                self._baseline_fps=max(self._baseline_fps,(len(window)-1)/(window[-1][0]-window[0][0]))
            # Retain scene overload feedback for multiplier 1 too; otherwise
            # every evaluation reopens the same overload and drops old frames.
            proposed=choose_plan(target,self._baseline_model_ms,compose,costs,self._ceilings,self.scene_mode,self.gpu_compose_ms)
            old=self._plan
            # Downshift promptly, promote after a settled observation window.
            settle=2. if old is not None and proposed.output_hz<old.output_hz*.9 else 6.
            if old is None or now-self._changed>=settle:
                if old is None or old.multiplier!=proposed.multiplier:
                    self._method_since=now;self._observed=[]
                self._plan=proposed;self._changed=now
            return self._plan
    def reset_plan(self):
        with self._lock:self._plan=None;self._last_eval=0.;self._changed=0.
    def maybe_probe(self,backend,frame0,frame1,preprocess=None):
        import numpy as np
        if backend is None or frame0.shape!=frame1.shape or np.array_equal(frame0,frame1):return
        shape=frame1.shape
        with self._lock:
            if self._stop.is_set() or self._probe is not None and self._probe.is_alive():return
            if time.perf_counter()-self._method_since<6.:return
            if self._probe_shape==shape:return
            self._probe_shape=shape;self._costs.clear();self._disabled.clear();a=frame0.copy();b=frame1.copy()
            self._probe=threading.Thread(target=self._profile,args=(backend,a,b,preprocess),daemon=True,name='target-fps-calibration');self._probe.start()
    def _profile(self,backend,a,b,preprocess):
        from output_enhancement.gpu_work_gate import SHARED_GPU_GATE
        if preprocess is not None:
            try:a=preprocess(a);b=preprocess(b)
            except Exception as exc:
                self.last_probe_error=str(exc);return
        for mult in (2,3,4):
            costs=[]
            try:
                for _ in range(4):
                    if self._stop.is_set():return
                    start=time.perf_counter();frames=backend.interpolate_rife(a,b,mult,fp16=False)
                    if len(frames)!=mult:raise RuntimeError('Incomplete RIFE calibration')
                    service=SHARED_GPU_GATE.snapshot();gpu=service.get('rife_frame%d'%mult,service.get('rife%d'%mult,[]))
                    work=service.get('rife_work%d'%mult,[])
                    if not gpu:raise RuntimeError('No NN execution timing available')
                    costs.append((gpu[-1],work[-1] if work else (time.perf_counter()-start)*1000.))
                    if self._stop.wait(.25):return  # Spread optional calibration over spare windows.
                with self._lock:self._costs[mult]=(sum(x[0] for x in costs)/len(costs),sum(x[1] for x in costs)/len(costs))
            except Exception as exc:
                with self._lock:self._disabled.add(mult);self.last_probe_error=str(exc)
    def observe_delivery(self,source_time):
        now=time.perf_counter()
        with self._lock:
            self._observed.append((now,now-source_time));self._observed=self._observed[-720:]
    def disable_method(self,multiplier):
        with self._lock:self._disabled.add(multiplier);self._plan=None
    def snapshot(self):
        with self._lock:return dict(plan=asdict(self._plan) if self._plan else None,nn_costs=dict(self._costs),compose_ms=sum(self._compose)/len(self._compose) if self._compose else None,probe_error=self.last_probe_error,real_baseline_fps=self._baseline_fps,rejected_methods=dict(self._rejections),mode_model_penalty_ms=dict(self._mode_penalties))
    def close(self):
        self._stop.set();thread=self._probe
        if thread is not None and thread is not threading.current_thread():thread.join(timeout=5.)
        return thread is None or not thread.is_alive()
