"""Full real-app baseline via the existing silent JSONL command channel.

Never replays synthetic motion. Stops the single app it started and restores the
exact previous UI settings after each run. Requires the physical camera input.
"""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path


class Session:
    def __init__(self, root):
        self.root=root;self.cmd=root/'runtime/agent_cmd.jsonl';self.reply=root/'runtime/agent_reply.jsonl'
        self.offset=self.reply.stat().st_size if self.reply.exists() else 0
    def read(self):
        if not self.reply.exists():return []
        with self.reply.open('r',encoding='utf-8-sig') as handle:
            handle.seek(self.offset);lines=handle.readlines();self.offset=handle.tell()
        result=[]
        for line in lines:
            try:result.append(json.loads(line))
            except ValueError:pass
        return result
    def command(self, name, timeout=40, **fields):
        self.read()
        with self.cmd.open('a',encoding='utf-8') as handle:
            handle.write(json.dumps(dict(cmd=name,**fields),ensure_ascii=False)+'\n')
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            for reply in self.read():
                if reply.get('cmd')==name:
                    if not reply.get('ok'):raise RuntimeError(str(reply))
                    return reply['result']
            time.sleep(.25)
        raise TimeoutError('App command timed out: '+name)


def active_apps(root):
    # Fixed read-only WMI query; restrict to this installation's UI/splash scripts.
    script="Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\\.exe$' -and ($_.CommandLine -like '*character_model_mediapipe_puppeteer_load_preview.py*' -or $_.CommandLine -like '*start_with_splash.py*') } | Select-Object ProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
    powershell=Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    result=subprocess.run([str(powershell),'-NoProfile','-Command',script],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
    if result.returncode:raise RuntimeError(result.stderr)
    rows=json.loads(result.stdout) if result.stdout.strip() else []
    if isinstance(rows,dict):rows=[rows]
    return [row for row in rows if str(root).lower() in str(row).lower()]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--input',choices=['openseeface','mediapipe'],default='openseeface')
    parser.add_argument('--all-variants',action='store_true')
    parser.add_argument('--environment-only',action='store_true',help='Initialization/errors only; no motion or FPS acceptance')
    parser.add_argument('--seconds',type=float,default=29)
    parser.add_argument('--tag',default='baseline')
    args=parser.parse_args();root=args.root.resolve()
    if active_apps(root):raise RuntimeError('An EVS instance is already running; refusing a second instance')
    output=root/'workspace/validation/20261031-complete'/args.tag;output.mkdir(parents=True,exist_ok=True)
    state=root/'workspace/load_preview_ui_state.json';original=state.read_bytes()
    (output/'ui-state.before.json').write_bytes(original)
    config=json.loads(original.decode('utf-8-sig'));config['mocap_input_mode']=args.input
    config['image_source_mode']='tha4_student'
    state.write_text(json.dumps(config,ensure_ascii=False,indent=2),'utf-8')
    session=Session(root);ready=False;closed=False;cases=[]
    try:
        started=time.monotonic()
        subprocess.Popen([str(root/'EasyVtuberStudio.exe')],cwd=root,creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+75
        while time.monotonic()<deadline:
            try:
                status=session.command('status',timeout=3)
                ready=True;break
            except TimeoutError:pass
        if not ready:raise RuntimeError('Actual main EXE did not expose the command channel')
        if not status['model']:session.command('load_last')
        deadline=time.monotonic()+45
        while not status['model'] and time.monotonic()<deadline:
            time.sleep(1);status=session.command('status')
        if not status['model']:raise RuntimeError('Sample model did not load')
        print('Actual EXE ready after %.2fs; physical input=%s'%(time.monotonic()-started,args.input),flush=True)
        variants=['student']+(['separable_half','separable_float','standard_half','standard_float'] if args.all_variants else [])
        for variant in variants:
            print('BEGIN '+variant,flush=True)
            if variant!='student':
                session.command('set_options',timeout=60,options=dict(source='tha3',tha3_variant=variant))
            if args.environment_only:
                deadline=time.monotonic()+60
                while True:
                    status=session.command('status')
                    paths=status.get('runtime_paths',{})
                    if not paths or not all(Path(p).resolve().is_relative_to(root) for p in paths.values()):
                        raise RuntimeError('Actual app runtime paths are missing or outside installation: '+str(paths))
                    bindings=json.loads((root/'runtime/bindings/components.json').read_text('utf-8-sig'))['components']
                    desired=bindings.get('app',bindings.get('face_puppeteer',bindings['basic_run']))
                    if Path(paths['prefix']).resolve()!=(root/desired['python']).resolve().parent.parent:
                        raise RuntimeError('App silently used a different environment: '+str(paths))
                    expected=status.get('variant')==variant if variant!='student' else status.get('source')=='tha4_student'
                    if status.get('model_error'):raise RuntimeError(str(status['model_error']))
                    if expected and status.get('model'):break
                    if time.monotonic()>=deadline:raise TimeoutError('Model initialization timed out: '+variant)
                    time.sleep(.5)
                row=dict(case=variant,ok=True,scope='actual entry and model initialization; no motion/FPS criterion',last_status=status)
                cases.append(row)
                (output/'result.json').write_text(json.dumps(dict(cases=cases),ensure_ascii=False,indent=2),'utf-8')
                print('END '+variant+' initialization PASS',flush=True)
                continue
            path=output/(variant+'.json')
            if path.exists():raise RuntimeError('Use a fresh --tag; refusing stale measurement: '+str(path))
            session.command('measure',seconds=max(5,min(30,args.seconds)),output=str(path))
            deadline=time.monotonic()+45
            while not path.exists() and time.monotonic()<deadline:time.sleep(.5)
            if not path.exists():raise RuntimeError('Live measurement did not finish: '+variant)
            data=json.loads(path.read_text('utf-8'))
            samples=data.get('samples',[])
            row=dict(case=variant,input=args.input,seconds=data.get('seconds'),
                     real_fps=data.get('real_fps'),native_fps=data.get('native_fps'),
                     model_loaded=all(s.get('model') for s in samples),
                     model_errors=list({str(s.get('model_error')) for s in samples if s.get('model_error')}),
                     measurement=str(path),last_status=samples[-1] if samples else None)
            row['ok']=row['model_loaded'] and not row['model_errors'] and (row['real_fps'] or 0)>0
            cases.append(row)
            (output/'result.json').write_text(json.dumps(dict(cases=cases),ensure_ascii=False,indent=2),'utf-8')
            print('END '+variant+' '+json.dumps({k:row[k] for k in ('ok','real_fps','native_fps')},ensure_ascii=False),flush=True)
        session.command('close');closed=True
    finally:
        if ready and not closed:
            try:session.command('close',timeout=5)
            except Exception:pass
        deadline=time.monotonic()+25
        while active_apps(root) and time.monotonic()<deadline:time.sleep(1)
        if active_apps(root):
            raise RuntimeError('App has not exited; preserved UI-state.before.json; not overwriting live state')
        state.write_bytes(original)
        (output/'settings-restored.json').write_text(json.dumps(dict(restored=True,exit_ok=True)),'utf-8')
    return 0 if cases and all(row['ok'] for row in cases) else 1


if __name__=='__main__':
    raise SystemExit(main())
