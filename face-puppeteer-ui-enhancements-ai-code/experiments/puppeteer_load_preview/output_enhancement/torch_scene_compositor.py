"""Experimental CUDA final compositor. Character and GIF timelines stay separate.

No model inference or face tracking here. Uses the existing CPU geometry/order
resolver and exact CPU asset resize; affine sampling and RGBA source-over run
on CUDA. Only the final RGBA surface is read back for the current ULW API.
The rasterizer is numerically close to OpenCV/Pillow, not claimed bit-exact.
"""
from __future__ import annotations
from typing import List,Tuple
from collections import OrderedDict
import math,threading,time
import numpy as np
import cv2,torch
import torch.nn.functional as F
from output_enhancement.gpu_work_gate import SHARED_GPU_GATE
from numpy_layer_compositor import _mat3_translate,_mat3_rotate
from rgba_capture_compose import scale_rgba
from layer_runtime import (orbit_frame_plan,layer_at_stack_position,resolve_stack_layer_draw,
    resolved_layer_rotation_deg,MOTION_MODE_SIMPLE_SWING,compute_swing_angle_deg,
    clamp_swing_pivot_u,clamp_swing_pivot_v)

@torch.jit.script
def _draw(textures:List[torch.Tensor], inverses:List[torch.Tensor], grids:List[torch.Tensor],
          rects:List[Tuple[int,int,int,int]], base:torch.Tensor)->torch.Tensor:
    canvas=base.clone()
    for i in range(len(textures)):
        texture=textures[i];xy=grids[i];inv=inverses[i]
        sx=xy[:,:,0]*inv[0,0]+xy[:,:,1]*inv[0,1]+inv[0,2]
        sy=xy[:,:,0]*inv[1,0]+xy[:,:,1]*inv[1,1]+inv[1,2]
        coords=torch.round(torch.stack([sx,sy],dim=-1)*32.0)/32.0
        gx=(coords[:,:,0]+0.5)*(2.0/float(texture.size(3)))-1.0
        gy=(coords[:,:,1]+0.5)*(2.0/float(texture.size(2)))-1.0
        grid=torch.stack([gx,gy],dim=-1).unsqueeze(0)
        fg=F.grid_sample(texture,grid,mode='bilinear',padding_mode='zeros',align_corners=False)[0].permute(1,2,0)
        fg=torch.clamp(torch.round(fg),0.0,255.0)
        x,y,w,h=rects[i];bg=canvas[y:y+h,x:x+w,:]
        fa=fg[:,:,3:4]/255.0;ba=bg[:,:,3:4]/255.0;oa=fa+ba*(1.0-fa)
        rgb=(fg[:,:,:3]*fa+bg[:,:,:3]*ba*(1.0-fa))/torch.clamp(oa,min=1.e-6)
        rgb=torch.where(oa>0.0,rgb,torch.zeros_like(rgb))
        mixed=torch.cat([rgb,oa*255.0],dim=-1)
        canvas[y:y+h,x:x+w,:]=torch.clamp(torch.floor(mixed+0.5),0.0,255.0)
    canvas[:,:,:3]=torch.where(canvas[:,:,3:4]>0.0,canvas[:,:,:3],torch.zeros_like(canvas[:,:,:3]))
    return canvas.to(torch.uint8).contiguous()

class TorchSceneCompositor:
    def __init__(self,device='cuda:0',cache_budget_mb=None):
        self.device=torch.device(device)
        if self.device.type!='cuda' or not torch.cuda.is_available():raise RuntimeError('CUDA compositor unavailable')
        free,_=torch.cuda.mem_get_info(self.device)
        self.budget=int(cache_budget_mb*2**20) if cache_budget_mb is not None else int(min(2048*2**20,max(64*2**20,free*.25)))
        self._cache=OrderedDict();self._bytes=0;self._peak=0;self.hits=0;self.misses=0;self.frames=0;self._lock=threading.RLock();self.last_error=None
        self._event0=torch.cuda.Event(enable_timing=True);self._event1=torch.cuda.Event(enable_timing=True)
    def _cached(self,key,source,create):
        old=self._cache.get(key)
        if old is not None:
            self.hits+=1;self._cache.move_to_end(key);return old[1]
        self.misses+=1;value=create();size=value.numel()*value.element_size()
        self._cache[key]=(source,value,size);self._bytes+=size
        while self._bytes>self.budget and len(self._cache)>1:
            _,(_,_,used)=self._cache.popitem(last=False);self._bytes-=used
        self._peak=max(self._peak,self._bytes);return value
    def _texture(self,array,width,height,cache):
        def create():
            resized=scale_rgba(array,width,height)
            return torch.from_numpy(np.ascontiguousarray(resized)).to(self.device).permute(2,0,1).unsqueeze(0).float().contiguous()
        return self._cached(('texture',id(array),width,height),array,create) if cache else create()
    def _grid(self,width,height):
        def create():
            yy,xx=torch.meshgrid(torch.arange(height,device=self.device,dtype=torch.float32),torch.arange(width,device=self.device,dtype=torch.float32),indexing='ij')
            return torch.stack([xx,yy],dim=-1)
        return self._cached(('grid',width,height),None,create)
    @staticmethod
    def _roi(matrix,source_w,source_h,width,height):
        corners=np.array([[0.,0.,1.],[source_w,0.,1.],[0.,source_h,1.],[source_w,source_h,1.]])@matrix.T
        x0=max(0,min(width,int(math.floor(corners[:,0].min()-2.))));x1=max(0,min(width,int(math.ceil(corners[:,0].max()+2.))))
        y0=max(0,min(height,int(math.floor(corners[:,1].min()-2.))));y1=max(0,min(height,int(math.ceil(corners[:,1].max()+2.))))
        if x1<=x0 or y1<=y0:return None
        inverse=cv2.invertAffineTransform(matrix)
        inverse[:,2]+=inverse[:,:2]@np.array([x0,y0],np.float64)
        return (x0,y0,x1-x0,y1-y0),inverse
    @staticmethod
    def supported(prepared):
        snap=prepared[0]
        return snap.antialias<=1.001 and snap.edge_mode=='none'
    def render_prepared(self,prepared):
        if not self.supported(prepared):raise ValueError('CUDA compositor currently requires AA=1 and no character edge filter')
        started=time.perf_counter();cpu=time.thread_time()
        snap,ctx,state,assets,resolved,image,profile=prepared;commands=[]
        source_h,source_w=image.shape[:2];scale=max(.1,ctx.display_scale);rad=math.radians(ctx.display_rotation_deg);c=math.cos(rad);s=math.sin(rad)
        character=np.array([[scale*c,-scale*s,snap.width/2+ctx.display_offset_x-scale*c*source_w/2+scale*s*source_h],
                            [scale*s,scale*c,snap.height+ctx.display_offset_y-scale*s*source_w/2-scale*c*source_h]],np.float64)
        plan,hidden=orbit_frame_plan(state,ctx)
        for pos in range(state.total_stack_positions):
            if pos==state.character_stack_position:
                commands.append((image,source_w,source_h,character,False));continue
            layer=layer_at_stack_position(state,pos)
            if layer is None or not layer.enabled:continue
            pair=resolve_stack_layer_draw(state,layer,resolved,plan,hidden)
            if pair is None:continue
            draw_layer,rect=pair
            if not draw_layer.visible:continue
            array=assets.get(draw_layer.slot_id)
            if array is None:continue
            w=max(1,int(round(rect.draw_width)));h=max(1,int(round(rect.draw_height)))
            rotation=resolved_layer_rotation_deg(draw_layer,state,rect,ctx);swing=0.
            if draw_layer.asset_path and draw_layer.motion_mode==MOTION_MODE_SIMPLE_SWING:swing=compute_swing_angle_deg(draw_layer,ctx.motion_time_s)
            if abs(rotation)<=1.e-4 and abs(swing)<=1.e-4:
                matrix=_mat3_translate(int(round(rect.draw_x)),int(round(rect.draw_y)))
            else:
                matrix=_mat3_translate(rect.draw_x+rect.draw_width/2,rect.draw_y+rect.draw_height/2)@_mat3_rotate(rotation)
                if abs(swing)>1.e-4:
                    px=(clamp_swing_pivot_u(draw_layer.swing_pivot_u)-.5)*w;py=(clamp_swing_pivot_v(draw_layer.swing_pivot_v)-.5)*h
                    matrix=matrix@_mat3_translate(px,py)@_mat3_rotate(swing)@_mat3_translate(-px,-py)
                matrix=matrix@_mat3_translate(-w/2,-h/2)
            commands.append((array,w,h,np.ascontiguousarray(matrix[:2]),not draw_layer.region_wobble_enabled))
        with self._lock,SHARED_GPU_GATE.job('compose' if self.frames>=4 else 'compose-warmup'),torch.cuda.device(self.device),torch.no_grad():
            service_start=time.perf_counter()
            textures=[];inverses=[];grids=[];rects=[]
            if snap.background is None:
                base=self._cached(('base',snap.width,snap.height),None,lambda:torch.zeros((snap.height,snap.width,4),device=self.device))
            else:base=self._texture(snap.background,snap.width,snap.height,True)[0].permute(1,2,0)
            for array,w,h,matrix,cache in commands:
                spec=self._roi(matrix,w,h,snap.width,snap.height)
                if spec is None:continue
                roi,inv=spec;rects.append(roi);textures.append(self._texture(array,w,h,cache));inverses.append(torch.from_numpy(inv.astype(np.float32)).to(self.device));grids.append(self._grid(roi[2],roi[3]))
            self._event0.record()
            with torch.jit.optimized_execution(False):
                result=_draw(textures,inverses,grids,rects,base)
            self._event1.record();out=result.cpu().numpy();gpu=float(self._event0.elapsed_time(self._event1));self.frames+=1
            service_ms=(time.perf_counter()-service_start)*1000.
        profile.update(gpu_service_ms=service_ms,render_wall_ms=(time.perf_counter()-started)*1000.,render_thread_cpu_ms=(time.thread_time()-cpu)*1000.,gpu_pixel_ms=gpu)
        return out
    def snapshot(self):
        with self._lock:return dict(device=str(self.device),frames=self.frames,cache_budget_mb=self.budget/2**20,cache_peak_mb=self._peak/2**20,cache_current_mb=self._bytes/2**20,cache_hits=self.hits,cache_misses=self.misses,last_error=self.last_error,scope='CUDA affine ROI sampling and straight-alpha blend, exact existing CPU resize, final RGBA readback; AA/edge unsupported falls back to CPU.')
    def close(self):
        with self._lock:self._cache.clear();self._bytes=0
        with SHARED_GPU_GATE.job("release-compose-cache"),torch.cuda.device(self.device):
            torch.cuda.empty_cache()
