"""Optional, bounded model implementation trials against recently captured camera poses.

No camera ownership or input replacement. A candidate is kept only after pixel
and timing checks; acceptance still needs separate full-application measurement.
"""
from pathlib import Path
import json,time,statistics,traceback
import numpy as np
import torch

def jit_trial(engine,poses,directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    result=dict(ok=False,accepted=False,variant=engine.model_variant)
    with engine._render_lock:
        original=dict(engine._poser.get_modules());graph=engine._cuda_graph
        engine._cuda_graph=None;accepted=False
        try:
            poses=[list(p) for p in poses[-6:]]
            references=[];baseline=[]
            for pose in poses:
                start=time.perf_counter();references.append(engine._render_pose_pytorch_numpy(pose));baseline.append((time.perf_counter()-start)*1000.)
            inputs={};forwards={}
            def copy_value(value):
                if torch.is_tensor(value):return value.detach().clone()
                if isinstance(value,list):return [copy_value(v)for v in value]
                if isinstance(value,tuple):return tuple(copy_value(v)for v in value)
                return value
            for name,module in original.items():
                forward=module.forward;forwards[name]=forward
                def capture(*args,_name=name,_forward=forward,**kwargs):
                    inputs[_name]=tuple(copy_value(v)for v in args)
                    return _forward(*args,**kwargs)
                module.forward=capture
            try:engine._render_pose_pytorch_numpy(poses[-1])
            finally:
                for name,module in original.items():module.forward=forwards[name]
            converted=[]
            for name,args in inputs.items():
                module=original[name]
                with torch.no_grad():
                    traced=torch.jit.trace(module,args,strict=False,check_trace=False)
                    traced=torch.jit.freeze(traced.eval())
                    optimized=torch.jit.optimize_for_inference(traced)
                engine._poser.modules[name]=optimized;converted.append(name)
            engine._render_pose_pytorch_numpy(poses[-1])
            candidate=[];maximum=0;mean=[]
            for pose,expected in zip(poses,references):
                start=time.perf_counter();actual=engine._render_pose_pytorch_numpy(pose);candidate.append((time.perf_counter()-start)*1000.)
                diff=np.abs(actual.astype(np.int16)-expected.astype(np.int16));maximum=max(maximum,int(diff.max()));mean.append(float(diff.mean()))
            before,after=statistics.median(baseline),statistics.median(candidate)
            accepted=bool(converted) and maximum<=4 and after<before*.97
            result.update(ok=True,accepted=accepted,baseline_ms=before,candidate_ms=after,max_diff=maximum,mean_diff=float(np.mean(mean)),modules=converted,input_source='recent physical camera poses; diagnostic comparison only')
        except Exception as exc:
            result.update(error=repr(exc),traceback=traceback.format_exc()[-4000:])
        finally:
            if not accepted:
                engine._poser.modules=original;engine._cuda_graph=graph
            else:
                engine._cuda_graph=None
                engine.prepare_cuda_graph(poses[-1])
            engine.jit_status=result
            (directory/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
    return result
