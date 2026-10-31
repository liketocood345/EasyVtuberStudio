"""Frozen UI snapshots + parallel full-resolution composition of RIFE materials.

The UI captures values/assets only. Physics and binding geometry advance in
frame order on the NN worker; independent pixel operations use a bounded pool.
"""
from __future__ import annotations
from portable_process_env import debug_log_path
from dataclasses import dataclass,replace
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import copy,hashlib,json,threading,time
import numpy as np
from layer_runtime import BindingContext,LayerBindingSmoother,resolve_layer_rects
from numpy_layer_compositor import compose_full_stack_rgba,_RgbaSizeView
from region_wobble import apply_wobble
from rgba_capture_compose import compose_character_rgba_from_keyframe
from character_edge_postprocess import apply_character_edge_postprocess
from output_enhancement.antialiasing import upscale_keyframe_for_ssaa
from output_enhancement.rgba_ops import sanitize_transparent_rgb
from layer_runtime import resolve_gif_frame_index

@dataclass(frozen=True)
class FrozenGifAsset:
    """Decoded immutable GIF frames; resolve at the final scene timestamp.

    GIF animation must never be sampled only at the low-rate THA/RIFE input.
    Playback mutations apply to the snapshot's private layer copy.
    """
    frames: tuple
    durations_ms: tuple
    total_ms: int

    def frame_at(self, layer, wall_time):
        index = resolve_gif_frame_index(layer, self.durations_ms, self.total_ms,
                                        len(self.frames), wall_time)
        return self.frames[index], index

@dataclass(frozen=True)
class SceneSnapshot:
    stamp: float
    wall_time: float
    width: int
    height: int
    context: BindingContext
    layers: object
    assets: dict
    wobble_specs: dict
    background: object=None
    antialias: float=1.
    edge_mode: str='none'
    edge_width: float=2.
    edge_rgb: tuple=(0,0,0)
    edge_background_rgb: tuple=(0,0,0)

class ParallelSceneRenderer:
    def __init__(self,workers=4,gpu_composition=False,gpu_device="cuda:0"):
        self.workers=max(1,min(8,int(workers)));self._pool=ThreadPoolExecutor(max_workers=self.workers,thread_name_prefix='scene-pixels')
        self._snapshots=deque(maxlen=512);self._lock=threading.Lock();self._spec_cache={};self._spec_source_refs={};self._wobble_runtime={};self._smoother=LayerBindingSmoother();self.last_batch_ms=0.;self._closed=False
        self.gif_samples=deque(maxlen=4096)
        self.stage_profiles=deque(maxlen=240)
        self._inflight=threading.BoundedSemaphore(12)
        self.gpu_backend=None;self.gpu_failed=False;self.gpu_fallback_frames=0
        self.gpu_auto=gpu_composition=="auto";self.gpu_selected=bool(gpu_composition) and not self.gpu_auto
        self.gpu_probe=[];self._decision_lock=threading.Lock();self._current_gpu_supported=False
        if gpu_composition:
            from output_enhancement.torch_scene_compositor import TorchSceneCompositor
            try:self.gpu_backend=TorchSceneCompositor(gpu_device)
            except Exception:self.gpu_failed=True
    def capture_wobble_spec(self,key,state):
        # UI mask edits already call invalidate_wobble_cache. Retain the source
        # state so identity cannot be recycled; avoid hashing megabytes per tick.
        token=(id(state),getattr(state,'_mask_generation',0),repr(state.to_persist_dict()),
               tuple((id(part.mask),tuple(part.mask.shape) if part.mask is not None else None) for part in state.regions))
        old=self._spec_cache.get(key)
        if old is None or old[0]!=token:
            frozen=copy.deepcopy(state);frozen.invalidate_wobble_cache();old=(token,frozen);self._spec_cache[key]=old
            self._spec_source_refs[key]=state
        return old
    def submit_snapshot(self,snapshot):
        with self._lock:
            if not self._closed:self._snapshots.append(snapshot)
    def _snapshot_for(self,stamp):
        with self._lock:values=list(self._snapshots)
        if not values:raise RuntimeError('No full-resolution scene snapshot')
        left=values[0]
        for item in values:
            if item.stamp<=stamp:left=item
            else:break
        ctx=replace(left.context,binding_smoother=None,_orbit_plan_cache=None,_orbit_plan_cache_time_s=None)
        # Q10: do not lerp pose/placement against RIFE pixels — that shears layers.
        # GIF/orbit still advance on the playout clock via motion_time_s.
        ctx.motion_time_s=left.wall_time+(stamp-left.stamp)
        return left,ctx
    def _wobble(self,key,rgba,spec,ctx,stamp):
        if spec is None:return rgba
        token,frozen=spec
        if not frozen.enabled or not frozen.has_active_mask():return rgba
        old=self._wobble_runtime.get(key)
        if old is None or old[0]!=token:
            state=copy.deepcopy(frozen);state.reset_spring();state.invalidate_wobble_cache();old=(token,state);self._wobble_runtime[key]=old
        return apply_wobble(rgba,old[1],head_yaw=ctx.pose_head_x,head_pitch=ctx.pose_head_y,now_s=stamp,target_tag=str(key))
    def _prepare(self,rgba,stamp):
        begin=time.perf_counter();cpu=time.thread_time()
        snap,ctx=self._snapshot_for(stamp);state=copy.deepcopy(snap.layers)
        image,_,_=upscale_keyframe_for_ssaa(rgba,rgba.shape[1],rgba.shape[0],snap.antialias)
        image=self._wobble('character',image,snap.wobble_specs.get('character'),ctx,stamp)
        assets={}
        for layer in state.layers:
            asset=snap.assets.get(layer.slot_id)
            if isinstance(asset, FrozenGifAsset):
                asset,index=asset.frame_at(layer,ctx.motion_time_s)
                self.gif_samples.append((stamp,int(layer.slot_id),index))
                # #region agent log
                try:
                    prev=getattr(self,'_dbg_gif_last',{})
                    last=prev.get(layer.slot_id)
                    if last is not None and abs(int(index)-int(last))>1:
                        import json as _json
                        open(debug_log_path('86a17c'),"a",encoding="utf-8").write(_json.dumps({"sessionId":"86a17c","runId":"post-fix","hypothesisId":"G","location":"scene_snapshot.py:_prepare","message":"gif frame skip","data":{"slot":int(layer.slot_id),"prev":int(last),"index":int(index)},"timestamp":int(time.time()*1000)})+"\n")
                    prev[layer.slot_id]=int(index);self._dbg_gif_last=prev
                except Exception:
                    pass
                # #endregion
            if asset is not None:assets[layer.slot_id]=self._wobble(layer.slot_id,asset,snap.wobble_specs.get(layer.slot_id),ctx,stamp)
        views={key:_RgbaSizeView(value) for key,value in assets.items()}
        resolved=resolve_layer_rects(state,lambda layer:views.get(layer.slot_id),snap.width,snap.height,ctx,binding_smoother=self._smoother)
        profile={"prepare_wall_ms":(time.perf_counter()-begin)*1000.,"prepare_thread_cpu_ms":(time.thread_time()-cpu)*1000.}
        self.stage_profiles.append(profile)
        prepared=(snap,ctx,state,assets,resolved,image,profile)
        self._current_gpu_supported=self.gpu_backend is not None and self.gpu_backend.supported(prepared)
        return prepared
    @staticmethod
    def _render(prepared):
        begin=time.perf_counter();cpu=time.thread_time()
        snap,ctx,state,assets,resolved,image,profile=prepared
        char=compose_character_rgba_from_keyframe(image,snap.width,snap.height,anchor_x=snap.width/2+ctx.display_offset_x,anchor_y=snap.height+ctx.display_offset_y,scale=max(.1,ctx.display_scale),rotation_deg=ctx.display_rotation_deg,antialias_factor=snap.antialias)
        char=apply_character_edge_postprocess(char,snap.edge_mode,width=snap.edge_width,outline_rgb=snap.edge_rgb,background_rgb=snap.edge_background_rgb)
        out=compose_full_stack_rgba(state,lambda layer:assets.get(layer.slot_id),snap.width,snap.height,char,ctx,base_rgba=snap.background,resolved_geometry=resolved)
        result=sanitize_transparent_rgb(out) if snap.background is None else out
        profile.update(render_wall_ms=(time.perf_counter()-begin)*1000.,render_thread_cpu_ms=(time.thread_time()-cpu)*1000.)
        return result
    @property
    def cpu_service_ms(self):
        values=[p['prepare_thread_cpu_ms']+p['render_thread_cpu_ms'] for p in self.stage_profiles if 'render_thread_cpu_ms' in p]
        return sum(values)/len(values) if len(values)>=8 else None
    @property
    def gpu_active(self):
        return self.gpu_backend is not None and self.gpu_selected and not self.gpu_failed and self._current_gpu_supported
    def _render_one(self,prepared):
        supported=self.gpu_backend is not None and not self.gpu_failed and self.gpu_backend.supported(prepared)
        if supported and self.gpu_auto and not self.gpu_selected:
            with self._decision_lock:
                if self.gpu_failed:return self._render(prepared)
                if not self.gpu_selected:
                    start=time.perf_counter();cpu_start=time.thread_time();reference=self._render(prepared);cpu_ms=(time.perf_counter()-start)*1000.
                    before=time.perf_counter()
                    try:actual=self.gpu_backend.render_prepared(prepared)
                    except Exception as exc:
                        self.gpu_backend.last_error=str(exc);self.gpu_failed=True;return reference
                    gpu_wall_ms=(time.perf_counter()-before)*1000.
                    # Fair-gate wait overlaps inference; budget the exclusive service
                    # separately, then validate the chosen route with joint replay.
                    gpu_ms=float(prepared[-1].get('gpu_service_ms',gpu_wall_ms))
                    a=reference[::4,::4].astype(np.float32);b=actual[::4,::4].astype(np.float32)
                    error=float(np.abs(a[:,:,:3]*(a[:,:,3:4]/255.)-b[:,:,:3]*(b[:,:,3:4]/255.)).mean())
                    alpha=float(np.abs(a[:,:,3]-b[:,:,3]).mean())
                    self.gpu_probe.append(dict(cpu_ms=cpu_ms,gpu_ms=gpu_ms,gpu_wall_ms=gpu_wall_ms,premult_error=error,alpha_error=alpha))
                    prepared[-1].update(render_wall_ms=(time.perf_counter()-start)*1000.,render_thread_cpu_ms=(time.thread_time()-cpu_start)*1000.)
                    if error>.5 or alpha>.5:
                        self.gpu_failed=True;self.gpu_backend.last_error='GPU raster quality trial rejected'
                    elif len(self.gpu_probe)>=6:
                        trial=self.gpu_probe[2:]
                        self.gpu_selected=sum(p['gpu_ms'] for p in trial)<.97*sum(p['cpu_ms'] for p in trial)
                        if not self.gpu_selected:self.gpu_failed=True;self.gpu_backend.last_error='GPU pixel trial did not beat CPU'
                    return actual if self.gpu_selected else reference
        if supported and not self.gpu_failed:
            try:return self.gpu_backend.render_prepared(prepared)
            except Exception as exc:
                self.gpu_backend.last_error=str(exc);self.gpu_failed=True
        if self.gpu_backend is not None:self.gpu_fallback_frames+=1
        return self._render(prepared)
    def enqueue_batch(self,frames,previous_time,current_time,stop_event=None):
        jobs=[];count=len(frames)
        for i,rgba in enumerate(frames):
            while not self._inflight.acquire(timeout=.02):
                if self._closed or stop_event is not None and stop_event.is_set():return jobs
            if self._closed or stop_event is not None and stop_event.is_set():
                self._inflight.release();return jobs
            try:
                stamp=previous_time+(current_time-previous_time)*(i+1)/count
                prepared=self._prepare(rgba,stamp);job=self._pool.submit(self._render_one,prepared)
                job.add_done_callback(lambda _job:self._inflight.release());jobs.append(job)
            except BaseException:
                self._inflight.release();raise
        return jobs
    def transform_batch(self,frames,previous_time,current_time):
        started=time.perf_counter();jobs=[];count=len(frames)
        for i,rgba in enumerate(frames):
            stamp=previous_time+(current_time-previous_time)*(i+1)/count
            prepared=self._prepare(rgba,stamp);jobs.append(self._pool.submit(self._render_one,prepared))
        outputs=[job.result(timeout=.7) for job in jobs];self.last_batch_ms=(time.perf_counter()-started)*1000.;return outputs
    def close(self):
        with self._lock:self._closed=True;self._snapshots.clear()
        self._pool.shutdown(wait=True,cancel_futures=True);self._spec_cache.clear();self._spec_source_refs.clear();self._wobble_runtime.clear()
        if self.gpu_backend is not None:self.gpu_backend.close()
