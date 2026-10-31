"""Static-shape THA3 CUDA graph; optional until per-device benchmark wins.

Retains static inputs/outputs and a private graph memory pool. No host sync,
wx, or NumPy conversion occurs inside capture. The caller owns GPU scheduling.
"""
from __future__ import annotations
import torch
import inspect

class StaticTha3CudaGraph:
    def __init__(self,poser,image,linear_to_srgb,device):
        self.poser=poser;self.image=image;self.device=device;self.convert=linear_to_srgb
        self.host_pose=torch.empty((45,),dtype=poser.get_dtype(),pin_memory=True)
        self.pose=torch.zeros((45,),dtype=poser.get_dtype(),device=device)
        stream=torch.cuda.Stream(device=device);current=torch.cuda.current_stream(device)
        stream.wait_stream(current)
        with torch.no_grad(),torch.cuda.stream(stream):
            for _ in range(4):self._gpu_frame()
        current.wait_stream(stream);torch.cuda.synchronize(device)
        from tha3.nn.image_processing_util import cached_grid_references
        self.constant_references=cached_grid_references()
        self.graph=torch.cuda.CUDAGraph()
        options={'stream':stream}
        if 'capture_error_mode' in inspect.signature(torch.cuda.graph).parameters:
            options['capture_error_mode']='thread_local'
        with torch.no_grad(),torch.cuda.graph(self.graph,**options):
            self.output=self._gpu_frame()
        current.wait_stream(stream);torch.cuda.synchronize(device)
    def _gpu_frame(self):
        output=self.poser.pose(self.image,self.pose)[0].float()
        output=self.convert((output+1.)/2.)
        channels,height,width=output.shape
        output=255.*torch.transpose(output.reshape(channels,height*width),0,1).reshape(height,width,channels)
        return output.byte().contiguous()
    def render_rgba(self,pose_vector):
        with torch.no_grad():
            self.host_pose.copy_(torch.as_tensor(pose_vector,dtype=self.host_pose.dtype))
            self.pose.copy_(self.host_pose,non_blocking=True)
            self.graph.replay()
            return self.output.cpu().numpy()
