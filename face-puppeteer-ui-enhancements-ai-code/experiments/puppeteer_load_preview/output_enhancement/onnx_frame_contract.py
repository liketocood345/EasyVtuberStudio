"""Explicit ONNX frame contracts for native uint8 and legacy float models.

EVS-PERF-20261029: shipped EZVTB models already wrap normalization and return
uint8 RGBA. Applying the legacy float conversions caused silent RIFE fallback.
"""
from __future__ import annotations
import numpy as np
from output_enhancement.rgba_ops import sr_output_to_rgba_uint8

def frame_input(frame,node,*,premultiply=False):
    image=np.ascontiguousarray(frame,dtype=np.uint8)
    shape=list(node.shape)
    if len(shape)!=4:raise ValueError('Unsupported ONNX image input shape: %r'%shape)
    nchw=shape[1] in (3,4) and shape[-1] not in (3,4)
    expected_h,expected_w=(shape[2],shape[3]) if nchw else (shape[1],shape[2])
    for actual,expected in zip(image.shape[:2],(expected_h,expected_w)):
        if isinstance(expected,int) and expected>0 and actual!=expected:
            raise ValueError('ONNX model requires %sx%s; received %sx%s. No implicit downscale.'%(expected_w,expected_h,image.shape[1],image.shape[0]))
    if node.type=='tensor(uint8)':data=image
    elif node.type in ('tensor(float)','tensor(float16)'):
        data=image.astype(np.float32)/255.
        if premultiply:data=data.copy();data[:,:,:3]*=data[:,:,3:4]
        if node.type=='tensor(float16)':data=data.astype(np.float16)
    else:raise ValueError('Unsupported ONNX image input dtype: '+node.type)
    channels=shape[1] if nchw else shape[-1]
    if channels==3:data=data[:,:,:3]
    elif channels not in (4,None,'channels') and isinstance(channels,int):raise ValueError('Unsupported channel count: %r'%channels)
    if nchw:data=data.transpose(2,0,1)
    return np.ascontiguousarray(data[None])

def output_nhwc(output):
    out=np.asarray(output)
    if out.ndim!=4:raise ValueError('ONNX frame output must be 4D: %r'%(out.shape,))
    if out.shape[-1] not in (3,4) and out.shape[1] in (3,4):out=out.transpose(0,2,3,1)
    if out.shape[-1] not in (3,4):raise ValueError('Unsupported ONNX output layout: %r'%(out.shape,))
    return out

def decode_sr(output,source,scale):
    out=output_nhwc(output)
    if out.dtype==np.uint8 and out.shape[-1]==4:return np.ascontiguousarray(out[0])
    return sr_output_to_rgba_uint8(out,source[:,:,3],scale)

def decode_rife(output,multiplier,endpoint):
    out=output_nhwc(output)
    if out.shape[-1]!=4:raise ValueError('RIFE must return RGBA')
    if out.dtype!=np.uint8:out=np.clip(out*255.,0,255).astype(np.uint8)
    if len(out)==multiplier:out=out[:-1]  # Native graph already includes endpoint.
    if len(out)!=multiplier-1:raise ValueError('RIFE returned %d frames for x%d'%(len(out),multiplier))
    return [np.ascontiguousarray(x) for x in out]+[np.ascontiguousarray(endpoint,dtype=np.uint8)]

def rife_full_resolution(session,frame0,frame1,multiplier,run):
    """Run fixed-shape RIFE on moving ROIs; never resize the source canvas.

    Outside the changed ROI the endpoints are identical and are copied exactly.
    Multiple native-sized patches use overlap and alpha-aware feathering.
    """
    import cv2
    a=np.ascontiguousarray(frame0,dtype=np.uint8);b=np.ascontiguousarray(frame1,dtype=np.uint8)
    if a.shape!=b.shape:raise ValueError('RIFE endpoints must have equal canvas sizes')
    nodes=session.get_inputs()
    if len(nodes)!=2:raise ValueError('RIFE requires two image inputs')
    shape=list(nodes[0].shape);nchw=shape[1] in (3,4) and shape[-1] not in (3,4)
    th,tw=(shape[2],shape[3]) if nchw else (shape[1],shape[2]);h,w=a.shape[:2]
    def infer(left,right):
        feed={node.name:frame_input(image,node) for node,image in zip(nodes,(left,right))}
        return decode_rife(run(feed),multiplier,right)
    if not isinstance(th,int) or not isinstance(tw,int) or (h,w)==(th,tw):return infer(a,b)
    diff=cv2.absdiff(a,b);mask=cv2.max(cv2.max(diff[:,:,0],diff[:,:,1]),cv2.max(diff[:,:,2],diff[:,:,3]));x,y,bw,bh=cv2.boundingRect(mask)
    if bw==0 or bh==0:return [b]*multiplier
    def starts(lo,hi,length,tile):
        maximum=max(0,length-tile);first=min(maximum,max(0,lo-16));last=min(maximum,max(0,hi-tile+16))
        if last<=first:return [max(0,min(maximum,(lo+hi-tile)//2))]
        values=list(range(first,last,max(1,tile-64)));return values+[last] if not values or values[-1]!=last else values
    xs=starts(x,x+bw,w,tw);ys=starts(y,y+bh,h,th);patches=[]
    for yy in ys:
        for xx in xs:
            ph=min(th,h-yy);pw=min(tw,w-xx);left=np.zeros((th,tw,4),np.uint8);right=np.zeros_like(left);left[:ph,:pw]=a[yy:yy+ph,xx:xx+pw];right[:ph,:pw]=b[yy:yy+ph,xx:xx+pw]
            mids=infer(left,right)[:-1];patches.append((xx,yy,pw,ph,mids))
    result=[b.copy() for _ in range(multiplier-1)]
    if len(patches)==1:
        xx,yy,pw,ph,mids=patches[0]
        for out,mid in zip(result,mids):out[yy:yy+ph,xx:xx+pw]=mid[:ph,:pw]
        return result+[b]
    # Copy tile ownership cores, then feather only narrow seams. Avoid the old
    # full-ROI float accumulators (hundreds of MB/s per generated frame).
    columns=len(xs);rows=len(ys)
    def mix(left,right,weight):
        lf=left.astype(np.float32);rf=right.astype(np.float32)
        la=lf[:,:,3:4]/255.;ra=rf[:,:,3:4]/255.;alpha=la*(1-weight)+ra*weight
        rgb=(lf[:,:,:3]*la*(1-weight)+rf[:,:,:3]*ra*weight)/np.maximum(alpha,1/255.)
        return np.concatenate([np.clip(rgb,0,255),np.clip(alpha*255,0,255)],axis=2).astype(np.uint8)
    x0=min(xs);x1=min(w,max(xs)+tw)
    for frame_index,out in enumerate(result):
        row_images=[]
        for row_index,yy in enumerate(ys):
            ph=min(th,h-yy);line=b[yy:yy+ph,x0:x1].copy()
            for column_index,xx in enumerate(xs):
                patch=patches[row_index*columns+column_index];mid=patch[4][frame_index][:ph,:patch[2]]
                lo=x0 if column_index==0 else (xs[column_index-1]+tw+xx)//2
                hi=x1 if column_index==columns-1 else (xx+tw+xs[column_index+1])//2
                line[:,lo-x0:hi-x0]=mid[:,lo-xx:hi-xx]
            for column_index in range(columns-1):
                lx=xs[column_index];rx=xs[column_index+1];seam=(lx+tw+rx)//2;lo=max(rx,seam-16);hi=min(lx+tw,seam+16,w)
                if hi>lo:
                    left=patches[row_index*columns+column_index][4][frame_index][:ph,lo-lx:hi-lx]
                    right=patches[row_index*columns+column_index+1][4][frame_index][:ph,lo-rx:hi-rx]
                    line[:,lo-x0:hi-x0]=mix(left,right,np.linspace(0,1,hi-lo,dtype=np.float32)[None,:,None])
            row_images.append(line)
            lo=yy if row_index==0 else (ys[row_index-1]+th+yy)//2
            hi=min(h,yy+th) if row_index==rows-1 else (yy+th+ys[row_index+1])//2
            out[lo:hi,x0:x1]=line[lo-yy:hi-yy]
        for row_index in range(rows-1):
            top=ys[row_index];bottom=ys[row_index+1];seam=(top+th+bottom)//2;lo=max(bottom,seam-16);hi=min(top+th,seam+16,h)
            if hi>lo:
                out[lo:hi,x0:x1]=mix(row_images[row_index][lo-top:hi-top],row_images[row_index+1][lo-bottom:hi-bottom],np.linspace(0,1,hi-lo,dtype=np.float32)[:,None,None])
    return result+[b]
