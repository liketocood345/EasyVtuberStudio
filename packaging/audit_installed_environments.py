"""Record real interpreter/module paths and pip consistency for Cursor handoff.

No package installation, camera access, training, environment deletion or upload.
An explicit binding is authoritative; a failed binding never falls back.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROBE = r'''
import importlib,importlib.metadata,json,pathlib,site,sys
root=pathlib.Path(sys.argv[1]).resolve(); role=sys.argv[2]
paths=dict(executable=sys.executable,prefix=sys.prefix,base_prefix=sys.base_prefix)
assert all(pathlib.Path(p).resolve().is_relative_to(root) for p in paths.values()),paths
assert not site.ENABLE_USER_SITE
names=['torch','wx','numpy','scipy','PIL','omegaconf','einops','matplotlib']
if role in ('basic_run','face_puppeteer','tha3_models'):names+=['onnxruntime','pyanime4k']
if role in ('face_puppeteer','tha3_models'):names+=['mediapipe']
if role=='tha4_training':
    sys.path.insert(0,str(root/'addons/tha4_training/src'))
    names+=['quaternion','tensorboard','tha4.distiller.distiller_config']
modules={}
for name in names:
    module=importlib.import_module(name)
    path=pathlib.Path(module.__file__).resolve()
    assert path.is_relative_to(root),(name,str(path))
    modules[name]=dict(path=str(path),version=str(getattr(module,'__version__','')))
import torch
versions={d.metadata['Name']:d.version for d in importlib.metadata.distributions() if d.metadata['Name']}
print(json.dumps(dict(ok=True,role=role,paths=paths,modules=modules,packages=versions,
    torch=torch.__version__,cuda_available=torch.cuda.is_available()),ensure_ascii=False))
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--components', nargs='*')
    args = parser.parse_args()
    root = args.root.resolve()
    if not args.output.resolve().is_relative_to(root):
        parser.error('Audit output must stay inside the installation')
    bindings = json.loads((root/'runtime/bindings/components.json').read_text('utf-8-sig'))
    results = []
    for role, binding in bindings['components'].items():
        if args.components and role not in args.components:
            continue
        started = time.monotonic()
        python = (root/binding['python']).resolve()
        if not python.is_relative_to(root) or not python.is_file():
            results.append(dict(role=role,ok=False,error='Invalid/nonlocal binding',python=str(python)))
            continue
        env = os.environ.copy()
        for key in ('PYTHONHOME','PYTHONPATH','PIP_TARGET','PIP_PREFIX','PIP_USER'):
            env.pop(key,None)
        env.update(PYTHONNOUSERSITE='1',PIP_CONFIG_FILE='NUL',THA4_PORTABLE_ROOT=str(root))
        for key in ('TEMP','TMP','PIP_CACHE_DIR','MPLCONFIGDIR','TORCH_HOME','HF_HOME','NUMBA_CACHE_DIR',
                    'CUDA_CACHE_PATH','XDG_CACHE_HOME','APPDATA','LOCALAPPDATA','PYTHONPYCACHEPREFIX'):
            path=root/'workspace/cache/audit'/role/key.lower();path.mkdir(parents=True,exist_ok=True)
            env[key]=str(path)
        try:
            probe=subprocess.run([str(python),'-I','-c',PROBE,str(root),role],env=env,cwd=root,
                                 capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
            check=subprocess.run([str(python),'-I','-m','pip','check'],env=env,cwd=root,
                                 capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
            row=dict(role=role,ok=probe.returncode==0 and check.returncode==0,
                     python=str(python),probe_exit=probe.returncode,pip_check_exit=check.returncode,
                     stdout=probe.stdout,stderr=probe.stderr,pip_check=check.stdout+check.stderr)
            if probe.returncode==0:
                row['probe']=json.loads(probe.stdout.strip().splitlines()[-1])
        except (OSError,subprocess.TimeoutExpired,ValueError) as exc:
            row=dict(role=role,ok=False,python=str(python),error=repr(exc))
        row['seconds']=round(time.monotonic()-started,3);results.append(row)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(dict(schema_version=1,results=results),ensure_ascii=False,indent=2),'utf-8')
        print(role+': '+('PASS' if row['ok'] else 'FAIL'),flush=True)
    if not results:
        parser.error('No matching component bindings')
    return 0 if all(r['ok'] for r in results) else 1

if __name__=='__main__':
    raise SystemExit(main())
