"""One CORE inventory for GitHub ZIP construction and fresh-extract checks."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def clean_seed(value):
    if isinstance(value,dict):
        out={}
        for k,v in value.items():
            if k.startswith('window_capture_') or re.search(r'_frame_[xywh]$',k) or '_splitter_sash' in k: continue
            if k=='mouth_input_mode': v='mouse'
            if k=='image_source_mode': v='tha4_student'
            if k=='mocap_input_mode': v='mouse_audio'
            if k.endswith('camera_index'): v=0
            out[k]=clean_seed(v)
        return out
    if isinstance(value,list): return [clean_seed(v) for v in value]
    if isinstance(value,str) and re.match(r'^(?:[A-Za-z]:[\\/]|\\\\|/)',value): return ''
    return value


def candidates(root,scope):
    found=set()
    # os.walk with pruning: never follow junctions into huge runtime/addons trees.
    import os
    for rel in scope['directories']:
        start=root/rel
        if not start.is_dir(): continue
        for directory,dirs,files in os.walk(start,followlinks=False):
            d=Path(directory)
            dirs[:]=[n for n in dirs if n not in ('__pycache__','.git','.codegraph','his','_internal','runtime','venv','workspace','release') and not (d/n).is_symlink() and not (getattr((d/n).lstat(),'st_file_attributes',0) & 0x400)]
            if rel=='addons': dirs[:]=[]
            for n in files: found.add((d/n).relative_to(root).as_posix())
    for rel in scope['files']:
        if (root/rel).is_file(): found.add(rel)
    for pattern in scope['seed_files']:
        for p in (root/'workspace').glob(pattern):
            if p.is_file(): found.add(p.relative_to(root).as_posix())
    for rel in scope['seed_directories']:
        for p in (root/'workspace'/rel).rglob('*'):
            if p.is_file(): found.add(p.relative_to(root).as_posix())
    return sorted(found)


def allowed(root,scope):
    names=candidates(root,scope)
    # Build-time Git only, never a runtime dependency. A private git dir keeps the
    # ZIP source tree and user's existing index untouched.
    cache=root/'workspace/cache'; cache.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='core-ignore-',dir=cache) as tmp:
        repo=Path(tmp)/'git'
        subprocess.run(['git','init','--bare',str(repo)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        cmd=['git','-c','core.excludesFile=NUL','--git-dir',str(repo),'--work-tree',str(root),'check-ignore','--no-index','-z','--stdin']
        result=subprocess.run(cmd,input=('\0'.join(names)+'\0').encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root)
        if result.returncode not in (0,1): raise RuntimeError(result.stderr.decode(errors='replace'))
        ignored=set(result.stdout.decode().strip('\0').split('\0'))
    return [n for n in names if n not in ignored]


def forbidden(rel):
    parts=rel.lower().split('/')
    if parts[0] in ('runtime','plans','record','.git'): return True
    if parts[0]=='addons' and rel not in ('addons/README.md','addons/.gitkeep'): return True
    if parts[0]=='workspace' and len(parts)>1 and parts[1] not in ('load_preview_ui_state.json','.gitkeep','basic_layers') and not re.fullmatch(r'region_wobble_mask(?:_.*)?\.png',parts[1]): return True
    if any(p in ('.git','_internal','site-packages','__pycache__','his','.codegraph') for p in parts): return True
    if parts[-1] in ('.env','hf_token.txt','credentials.json') or parts[-1].endswith(('.pem','.pyc','.onnx','.whl','.nupkg','.jsonl')): return True
    if parts[-1].endswith('.pt') and not rel.startswith('data/character_models/baiten_from_project_forlon9/bai_450k/'): return True
    return False


def verify(root):
    manifest=json.loads((root/'core-files.json').read_text('utf-8'))
    expected={x['path']:x for x in manifest['files']}
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != set(expected)|{'core-files.json'}: raise ValueError('CORE inventory differs: '+str(sorted(actual^set(expected)^{'core-files.json'})))
    for n,x in expected.items():
        p=root/n
        if forbidden(n) or p.stat().st_size!=x['size_bytes'] or sha(p)!=x['sha256']: raise ValueError('CORE file rejected: '+n)
        if p.suffix.lower() in ('.py','.ps1','.bat','.json','.md','.txt','.yaml','.yml'):
            raw=p.read_text('utf-8-sig',errors='replace')
            if re.search(r'\b(?:hf_[A-Za-z0-9]{25,}|ghp_[A-Za-z0-9]{25,}|sk-(?:proj-)?[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16})\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',raw):raise ValueError('Possible credential in CORE candidate: '+n)
            # dep-043: public sources must not inherit a developer profile path
            # or an SSH target from internal handoff/experiment documents.
            profile = r'''\b[A-Za-z]:[\\/]+Users[\\/]+(?!Public\b|Default\b|<|\{|\$|%)[^\\/\s"'`]+'''
            lan = r'\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b'
            private_ssh=any(re.search(lan,line) and ('ssh ' in line.lower() or 'relay_key' in line.lower()) for line in raw.splitlines())
            if re.search(profile,raw,re.I) or private_ssh:raise ValueError('Private machine path/address in CORE candidate: '+n)
    required=['EasyVtuberStudio.exe','DEPLOY.bat','packaging/locked_runtime.py','deps/pip/runtime-artifacts.json',
        'data/character_models/baiten_from_project_forlon9/bai_450k/character_model/face_morpher.pt',
        'data/character_models/baiten_from_project_forlon9/bai_450k/parts/beitou.gif','workspace/load_preview_ui_state.json','workspace/basic_layers/manifest.json']
    for n in required:
        if n not in expected: raise ValueError('Required CORE asset absent: '+n)
    for p in (root/'workspace').rglob('*.json'):
        raw=json.loads(p.read_text('utf-8-sig'))
        if clean_seed(raw)!=raw: raise ValueError('Seed is not sanitized: '+str(p))
        def paths(v):
            if isinstance(v,dict):
                for k,x in v.items():
                    if k in ('asset_path','last_loaded_model_path','tha3_character_png') and x and not (root/x).is_file(): raise ValueError('Missing seed material: '+x)
                    paths(x)
            elif isinstance(v,list):
                for x in v: paths(x)
        paths(raw)
    print('CORE inventory, seed and material paths passed:',len(expected))


def build(root,stage,output):
    if stage.exists() and any(stage.iterdir()): raise ValueError('Use an empty staging directory; existing files are preserved')
    stage.mkdir(parents=True,exist_ok=True)
    scope=json.loads((root/'packaging/core_scope.json').read_text('utf-8'))
    records=[]
    for rel in allowed(root,scope):
        if forbidden(rel): continue
        src=root/rel; dst=stage/rel
        if not src.resolve().is_relative_to(root): raise ValueError('CORE source link escapes installation: '+rel)
        dst.parent.mkdir(parents=True,exist_ok=True)
        if rel.startswith('workspace/') and src.suffix=='.json': dst.write_text(json.dumps(clean_seed(json.loads(src.read_text('utf-8-sig'))),ensure_ascii=False,indent=2)+'\n','utf-8')
        else: shutil.copyfile(src,dst)
        records.append({'path':rel,'size_bytes':dst.stat().st_size,'sha256':sha(dst)})
    (stage/'core-files.json').write_text(json.dumps({'schema_version':1,'files':records},indent=2)+'\n','utf-8')
    verify(stage)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(stage).as_posix())
    print('CORE ZIP:',output,'SHA256:',sha(output))


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['build','verify']); p.add_argument('--root',type=Path,required=True); p.add_argument('--stage',type=Path); p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.action=='verify': verify(a.root.resolve())
    else: build(a.root.resolve(),a.stage.resolve(),a.output.resolve())
