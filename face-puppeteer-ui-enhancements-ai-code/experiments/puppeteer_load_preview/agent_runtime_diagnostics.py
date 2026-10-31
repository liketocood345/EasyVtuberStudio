"""f-072: bounded in-app diagnostics and test control, always on wx dispatch.

No shell execution, camera grabbing, or arbitrary Python evaluation. Measurements
run against the actual model worker and final native window callbacks.
"""
from pathlib import Path
from collections import deque
import json,time,types,sys,threading
import numpy as np

def attach(frame):
    if not hasattr(frame,'_agent_real_times'):
        frame._agent_face_flow=deque(maxlen=4096);frame._agent_recent_poses=deque(maxlen=24);frame._agent_real_times=deque(maxlen=4096);frame._agent_native_times=deque(maxlen=4096);frame._agent_model_ms=deque(maxlen=240);frame._agent_real_total=0;frame._agent_native_total=0
        original=frame.render_pose_to_wx_image
        def render(*a,_original=original,**k):
            t=time.perf_counter();result=_original(*a,**k)
            if result is not None:frame._agent_real_total+=1;frame._agent_real_times.append(time.perf_counter());frame._agent_model_ms.append((time.perf_counter()-t)*1000);frame._agent_recent_poses.append(tuple(a[0]));frame._agent_face_flow.append((time.perf_counter(),frame._last_model_face_sequence,frame._last_model_face_sample_mono,t))
            return result
        frame.render_pose_to_wx_image=render
    engine=getattr(getattr(frame,'active_image_source',None),'engine',None)
    if engine is not None and not getattr(engine,'_agent_observed',False):
        original=engine.render_pose_numpy
        def render_engine(*a,_original=original,**k):
            t=time.perf_counter();result=_original(*a,**k)
            if result is not None:frame._agent_real_total+=1;frame._agent_real_times.append(time.perf_counter());frame._agent_model_ms.append((time.perf_counter()-t)*1000);frame._agent_recent_poses.append(tuple(a[0]));frame._agent_face_flow.append((time.perf_counter(),frame._last_model_face_sequence,frame._last_model_face_sample_mono,t))
            return result
        engine.render_pose_numpy=render_engine;engine._agent_observed=True
    capture=getattr(frame,'transparent_capture_window',None)
    if capture is not None and not getattr(capture,'_agent_observed',False):
        original=capture._on_frame_presented
        def presented(_original=original):
            frame._agent_native_total+=1;frame._agent_native_times.append(time.perf_counter())
            if _original is not None:_original()
        capture._on_frame_presented=presented;capture._agent_observed=True

def status(frame):
    import torch,cv2
    attach(frame);now=time.perf_counter();engine=getattr(frame.active_image_source,'engine',None)
    def rate(values):
        a=[t for t in list(values)if now-t<=3.]
        return round((len(a)-1)/(a[-1]-a[0]),2) if len(a)>1 else 0.
    pipe=frame.output_enhancement.pipeline
    return dict(ok=True,runtime_paths=dict(executable=sys.executable,prefix=sys.prefix,base_prefix=sys.base_prefix,torch_file=torch.__file__),model=bool(frame.is_model_loaded()),source=frame.get_image_source_mode(),variant=getattr(engine,'model_variant',None),ui_variant=getattr(frame,'tha3_model_variant',None),ui_variant_label=frame.tha3_model_variant_choice.GetStringSelection() if hasattr(frame,'tha3_model_variant_choice') else None,weight_paths=getattr(engine,'weight_paths',None),student_fp16=frame.get_tha_infer_fp16_enabled() if engine is None else None,jit=getattr(engine,'jit_status',None),layout=getattr(engine,'layout_status',None),graph=getattr(engine,'cuda_graph_status',None),model_error=getattr(engine,'last_error',None),pid=__import__('os').getpid(),input_fps=frame.get_input_source_hz(),camera_frame_sequence=frame._camera_worker_frame_serial,face_submit_error=getattr(frame,'_camera_face_submit_error',None),capture_ui_sequence=frame._capture_frame_serial,stages_model={k:getattr(frame,k,None) for k in ('_dbg_tha_pose_ms','_dbg_tha_cpu_ms','_dbg_tha_wx_ms')},inf_fps=round(frame._inference_fps,2),out_fps=round(frame._display_out_fps,2),real_completed_hz=rate(frame._agent_real_times),native_completed_hz=rate(frame._agent_native_times),real_completed_total=frame._agent_real_total,native_completed_total=frame._agent_native_total,model_ms_mean=float(np.mean(frame._agent_model_ms)) if frame._agent_model_ms else None,full_controls=bool(getattr(frame,'full_controls_expanded',False)),mocap_mode=frame.mocap_input_mode,pose_from_video=bool(getattr(frame,'_osf_pose_from_video_source',False)),has_pose=frame.mediapipe_face_pose is not None,has_capture=frame.video_capture is not None,mouth_cap=frame.get_mouth_infer_cap_hz(),nn=frame.get_nn_infer_backend(),rife_effective=pipe._effective_nn_multiplier(),config=pipe.get_config_snapshot(),mocap_controls=dict(options=list(frame.mocap_frame_rate_choice.GetStrings()),selection=frame.mocap_frame_rate_choice.GetStringSelection(),fixed_value=frame.mocap_fixed_fps_spin.GetValue(),fixed_enabled=frame.mocap_fixed_fps_spin.IsEnabled()) if hasattr(frame,'mocap_frame_rate_choice') else None,mocap_rate=frame._mocap_rate.snapshot(),face_completed_hz=frame._mocap_completed_hz,face_output_hz=frame.get_mocap_completed_hz(),face_valid_count=frame._mediapipe_valid_count,face_completed_count=frame._mediapipe_complete_count,face_published_count=frame._mediapipe_publish_count,face_pose_sequence=frame._latest_face_pose_sequence,face_publish_lag_ms=(frame._latest_face_publish_mono-frame._latest_face_sample_mono)*1000. if frame._latest_face_sample_mono else None,tha_input_face_sequence=frame._last_model_face_sequence,tha_input_face_age_ms=(now-frame._last_model_face_sample_mono)*1000. if frame._last_model_face_sample_mono else None,live_scene=getattr(frame,'_live_scene_presenter',None) is not None,scene_error=getattr(getattr(frame,'_live_scene_presenter',None),'last_error',None),scene_ms=list(getattr(getattr(frame,'_live_scene_presenter',None),'render_ms',()))[-5:],torch_flags=dict(cudnn_benchmark=torch.backends.cudnn.benchmark,cudnn_tf32=torch.backends.cudnn.allow_tf32,matmul_tf32=torch.backends.cuda.matmul.allow_tf32),torch_threads=torch.get_num_threads(),opencv_threads=cv2.getNumThreads(),composition=getattr(frame,'_last_present_stages',{}),target=frame.is_target_frame_rate_enabled(),replay=None,input_source='physical_camera',camera_age_ms=max(0.,time.monotonic()-getattr(frame,'_last_good_webcam_bgr_mono',0.))*1000.,face_age_ms=max(0.,(time.time()-frame.last_face_detected_time)*1000.) if frame.last_face_detected_time else None,last_pose=list(frame.last_pose) if frame.last_pose is not None else None,worker_generation=frame._infer_worker_generation,worker_busy_ms=max(0.,time.monotonic()-frame._infer_worker_busy_since)*1000. if frame._infer_worker_busy_since else 0.)

def dispatch(frame,cmd,payload):
    import wx
    from portable_paths import get_portable_root
    attach(frame);root=get_portable_root();module=sys.modules[type(frame).__module__]
    if cmd in ('status','stat'):return status(frame)
    if cmd=='ui_layout':
        from ui_layout import measure_layout
        if 'preview_sash' in payload:
            frame.right_sidebar_splitter.SetSashPosition(int(payload['preview_sash']))
            wx.CallLater(500,measure_layout,frame,payload['output'])
            return dict(ok=True,scheduled=True,output=payload['output'])
        if 'preview_scroll' in payload:
            scroll=frame.capture_panel
            if isinstance(scroll,wx.ScrolledWindow):
                scroll.Scroll(0,0 if payload['preview_scroll']=='top' else -1)
                if payload['preview_scroll']=='bottom':scroll.Scroll(0,100000)
            wx.CallLater(150,measure_layout,frame,payload['output'])
            return dict(ok=True,scheduled=True,output=payload['output'])
        return measure_layout(frame,payload.get('output',root/'runtime'/'ui_layout.json'))
    if cmd=='options':return dict(ok=True,options=frame.collect_persistent_ui_state())
    if cmd in ('load_last','load-last','autoload'):
        path=frame.last_tha3_character_png if frame.get_image_source_mode()=='tha3' else frame.last_loaded_model_path
        resolved=frame.resolve_character_model_path(path)
        if not resolved:return dict(ok=False,error='No saved asset path')
        started=frame.active_image_source.load_asset(frame,resolved)
        return dict(ok=bool(started),started=bool(started),path=resolved)
    if cmd=='show_controls':
        frame.show_full_controls_window(skip_state_reload=True);return status(frame)
    if cmd=='set_options':
        opts=payload.get('options',{});changed=[]
        choices={'nn_infer_backend':('nn_infer_backend_choice','INFER_BACKEND_VALUES'),'nn_super_resolution_mode':('nn_super_resolution_choice','NN_SR_VALUES'),'nn_frame_interpolation_multiplier':('nn_frame_interpolation_choice','NN_FRAME_INTERP_VALUES'),'output_frame_interpolation':('output_frame_interpolation_choice','POSE_FRAME_INTERP_VALUES')}
        for key,(attr,values) in choices.items():
            if key in opts:
                allowed=list(getattr(module,values));getattr(frame,attr).SetSelection(allowed.index(opts[key]));changed.append(key)
        if 'target_frame_rate_enabled' in opts:frame.target_frame_rate_checkbox.SetValue(bool(opts['target_frame_rate_enabled']));changed.append('target')
        if 'target_frame_rate_fps' in opts:frame.target_frame_rate_input.SetValue(max(1,min(240,int(opts['target_frame_rate_fps']))));changed.append('target')
        if 'mouth_cap' in opts:
            allowed=list(module.MOUTH_INFER_CAP_HZ_VALUES);frame.mouth_infer_cap_choice.SetSelection(allowed.index(int(opts['mouth_cap'])));changed.append('mouth_cap')
        if 'region_wobble_enabled' in opts:frame.character_region_wobble.enabled=bool(opts['region_wobble_enabled']);frame.character_region_wobble.invalidate_wobble_cache();changed.append('wobble')
        if 'mocap_frame_rate_mode' in opts or 'mocap_fixed_fps' in opts:
            mode=opts.get('mocap_frame_rate_mode',frame._mocap_rate.mode);fps=opts.get('mocap_fixed_fps',frame._mocap_rate.fixed_fps)
            frame._mocap_rate.configure(mode,fps)
            if hasattr(frame,'mocap_frame_rate_choice'):
                frame.mocap_frame_rate_choice.SetSelection(1 if frame._mocap_rate.mode=='adaptive' else 0)
                frame.mocap_fixed_fps_spin.SetValue(frame._mocap_rate.fixed_fps)
                frame.mocap_fixed_fps_spin.Enable(frame._mocap_rate.mode=='fixed')
            frame.schedule_active_capture_timer();changed.append('mocap_rate')
        if 'cudnn_benchmark' in opts:
            import torch
            torch.backends.cudnn.benchmark=bool(opts['cudnn_benchmark']);changed.append('cudnn_benchmark')
        if 'threads' in opts:
            import torch,cv2
            n=max(1,min(16,int(opts['threads'])));torch.set_num_threads(n);cv2.setNumThreads(n);changed.append('threads')
        frame._sync_output_enhancement_config();frame._refresh_target_frame_rate_controls();frame._sync_frame_rate_timers();frame._clear_present_compose_dedupe();frame.save_persistent_ui_state()
        if 'tha3_variant' in opts:
            allowed=[x[0]for x in module.THA3_VARIANT_CHOICES];frame.tha3_model_variant_choice.SetSelection(allowed.index(opts['tha3_variant']));frame.on_tha3_model_variant_changed(types.SimpleNamespace(Skip=lambda:None));changed.append('tha3_variant')
        if 'tha4_fp16' in opts:
            frame.tha_infer_fp16_choice.SetSelection(int(bool(opts['tha4_fp16'])));frame.on_tha_infer_fp16_changed(types.SimpleNamespace(Skip=lambda:None));changed.append('tha4_fp16')
        if 'source' in opts:
            from image_sources.factory import switch_image_source
            switch_image_source(frame,str(opts['source']),autoload_asset=True);changed.append('source')
        if payload.get('warmup'):wx.CallAfter(frame._maybe_warmup_output_enhancement)
        return dict(ok=True,changed=changed,status=status(frame))
    if cmd=='pose_replay':
        # User explicitly requires the physical camera / actual mocap input.
        return dict(ok=False,error='Synthetic pose input disabled; use the physical camera')
    if cmd=='snapshot':
        import cv2
        directory=Path(payload.get('directory',root/'runtime'/'snapshots'));directory.mkdir(parents=True,exist_ok=True);label=''.join(c for c in str(payload.get('label','frame'))if c.isalnum()or c in '_-');files={}
        camera=getattr(frame,'_last_good_webcam_bgr_frame',None)
        if camera is not None:
            p=directory/(label+'_camera.png');cv2.imwrite(str(p),camera);files['camera']=str(p)
        image=frame.last_output_wx_image
        if image is not None:
            a=frame.wx_image_to_rgba_array(image);p=directory/(label+'_raw.png');cv2.imwrite(str(p),cv2.cvtColor(a,cv2.COLOR_RGBA2BGRA));files['raw']=str(p)
        a=getattr(frame,'_cached_present_rgba',None)
        if a is not None:
            p=directory/(label+'_output.png');cv2.imwrite(str(p),cv2.cvtColor(a,cv2.COLOR_RGBA2BGRA));files['output']=str(p)
        p=directory/(label+'_status.json');p.write_text(json.dumps(status(frame),ensure_ascii=False,indent=2),'utf-8');files['status']=str(p)
        return dict(ok=True,files=files)
    if cmd=='model_compare':
        # Same recently captured camera pose, diagnostic files only. Never feeds
        # a pose or a diagnostic render back into the application's input/output.
        engine=getattr(frame.active_image_source,'engine',None)
        if engine is None or frame.last_pose is None:return dict(ok=False,error='No live THA3 pose')
        import cv2
        directory=Path(payload.get('directory',root/'runtime'/'comparison'));directory.mkdir(parents=True,exist_ok=True)
        pose=list(frame.last_pose)
        with engine._render_lock:
            graph=engine._cuda_graph
            try:
                a=engine._render_pose_numpy_unlocked(pose)
                engine._cuda_graph=None
                b=engine._render_pose_numpy_unlocked(pose)
            finally:engine._cuda_graph=graph
        if a is None or b is None:return dict(ok=False,error=engine.last_error)
        cv2.imwrite(str(directory/'graph.png'),a);cv2.imwrite(str(directory/'eager.png'),b)
        diff=np.abs(a.astype(np.int16)-b.astype(np.int16))
        result=dict(ok=True,variant=engine.model_variant,pose=pose,max_diff=int(diff.max()),mean_diff=float(diff.mean()),input_source='captured physical camera pose; diagnostic only')
        (directory/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
        return result
    if cmd=='jit_trial':
        engine=getattr(frame.active_image_source,'engine',None)
        poses=list(frame._agent_recent_poses)
        if engine is None or len(poses)<3:return dict(ok=False,error='Need three recent real camera model completions')
        from agent_model_trials import jit_trial
        directory=Path(payload.get('directory',root/'runtime'/'jit_trial'))
        threading.Thread(target=jit_trial,args=(engine,poses,directory),daemon=True,name='tha3-jit-trial').start()
        return dict(ok=True,started=True,directory=str(directory))
    if cmd=='profile':
        import cProfile,pstats,io
        if getattr(frame,'_agent_profile',None) is not None:return dict(ok=False,error='Profile already active')
        seconds=max(5.,min(30.,float(payload.get('seconds',15.))))
        path=Path(payload.get('output',root/'runtime'/'profile.txt'));path.parent.mkdir(parents=True,exist_ok=True)
        profile=cProfile.Profile();frame._agent_profile=profile
        def finish():
            profile.disable();frame._agent_profile=None;stream=io.StringIO()
            pstats.Stats(profile,stream=stream).strip_dirs().sort_stats('cumulative').print_stats(70)
            path.write_text(stream.getvalue(),'utf-8');profile.dump_stats(str(path.with_suffix('.pstats')))
        wx.CallLater(int(seconds*1000),finish);profile.enable()
        return dict(ok=True,started=True,seconds=seconds,output=str(path))
    if cmd=='measure':
        seconds=max(5.,min(30.,float(payload.get('seconds',20.))));path=Path(payload.get('output',root/'runtime'/'measurement.json'));path.parent.mkdir(parents=True,exist_ok=True);started=time.perf_counter();samples=[]
        real0=frame._agent_real_total;out0=frame._agent_native_total
        def sample():
            if getattr(frame,'_is_closing',False):return
            row=status(frame);row['elapsed']=time.perf_counter()-started;samples.append(row)
            if row['elapsed']<seconds:wx.CallLater(500,sample)
            else:
                elapsed=time.perf_counter()-started
                def intervals(values):
                    a=np.asarray([t for t in list(values) if t>=started],dtype=float)
                    gaps=np.diff(a)*1000.
                    return dict(p50=float(np.percentile(gaps,50)),p95=float(np.percentile(gaps,95)),maximum=float(gaps.max())) if len(gaps) else None
                result=dict(ok=True,face_to_tha=[list(row)for row in list(frame._agent_face_flow)if row[0]>=started],real_interval_ms=intervals(frame._agent_real_times),native_interval_ms=intervals(frame._agent_native_times),seconds=elapsed,real_fps=(frame._agent_real_total-real0)/elapsed,native_fps=(frame._agent_native_total-out0)/elapsed,samples=samples,scope='Actual running application, complete controls and normal timers; real completed model calls and native completion callbacks')
                path.write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
        wx.CallAfter(sample);return dict(ok=True,started=True,output=str(path),seconds=seconds)
    if cmd=='close':
        wx.CallAfter(frame.Close);return dict(ok=True,closing=True)
    return None
