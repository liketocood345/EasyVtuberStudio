"""Plan or explicitly upload an allow-listed HF ark stage; never mirror a repo."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
import shutil
import uuid


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()


def inventory(stage):
    index=json.loads((stage/'index.json').read_text('utf-8'))
    expected={'index.json','README.md','LICENSE'}
    for name,release in index['modules'].items():
        item=release['artifact']; path=(stage/item['path']).resolve()
        prefix='packages/windows-x64/'+name+'/'
        if not path.is_relative_to(stage) or not item['path'].startswith(prefix): raise ValueError('Unsafe artifact prefix')
        if path.stat().st_size!=item['size_bytes'] or sha(path)!=item['sha256']:raise ValueError('Artifact hash mismatch: '+name)
        with zipfile.ZipFile(path) as z:
            for member in z.namelist():
                parts=member.replace('\\','/').lower().split('/')
                if any(p in ('runtime','venv','site-packages','_internal','workspace') for p in parts):raise ValueError('Runtime/user files in ark package: '+member)
                # Frozen OSF Binary is the verified ABI exception. Do not strip
                # DLLs which facetracker.exe requires, or archive a general base.
                if name!='openseeface' and (any(p.startswith(('python310','python39','torch-','torchvision-')) for p in parts) or member.lower().endswith('.nupkg')):raise ValueError('Shared runtime in HF artifact: '+member)
        expected.add(item['path'])
    for record in index['seed_files']:
        path=stage/record['path']
        if not record['path'].startswith('seed/') or '..' in Path(record['path']).parts or sha(path)!=record['sha256']:raise ValueError('Seed inventory mismatch')
        expected.add(record['path'])
    actual={p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
    if actual!=expected:raise ValueError('Unexpected HF stage files: '+str(actual^expected))
    return index,sorted(expected-{'index.json'})+['index.json']


def prepare_stage(root,core,stage):
    """Derive every sample/seed from the verified CORE, never the live workspace."""
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    from core_release import verify
    verify(core)
    scope=json.loads((core/'packaging/core_scope.json').read_text('utf-8'))
    if not scope.get('sample_directories'): raise ValueError('Rebuild CORE with explicit shared sample scope')
    old=json.loads((stage/'index.json').read_text('utf-8')) if (stage/'index.json').is_file() else {'seed_files':[]}
    index=json.loads((root/'packaging/resource-releases.json').read_text('utf-8'))
    seed=[]
    for folder in ['workspace',*scope['sample_directories']]:
        for source in (core/folder).rglob('*'):
            if not source.is_file():continue
            if not source.resolve().is_relative_to(core):raise ValueError('Sample source escaped CORE')
            rel='seed/'+source.relative_to(core).as_posix()
            target=(stage/rel).resolve()
            if not target.is_relative_to(stage):raise ValueError('Seed target escaped stage')
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            seed.append({'path':rel,'size_bytes':target.stat().st_size,'sha256':sha(target)})
    # Retain removed staging copies privately, not original source/user files.
    names={x['path'] for x in seed}
    for item in old['seed_files']:
        rel=item['path'];target=(stage/rel).resolve()
        if rel in names:continue
        if not rel.startswith('seed/') or not target.is_relative_to(stage):raise ValueError('Invalid old seed path')
        if target.is_file():
            keep=root/'workspace/release/excluded-publish-seed'/uuid.uuid4().hex/Path(rel).name
            keep.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,keep);target.unlink()
    index.update(seed_files=seed,published=False,policy='local/copy-in -> upstream -> failure/hash mismatch -> HF; never deploy seed')
    stage.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(core/'packaging/hf_bucket_README.md',stage/'README.md')
    shutil.copyfile(core/'LICENSE',stage/'LICENSE')
    (stage/'index.json').write_text(json.dumps(index,indent=2)+'\n','utf-8')


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--stage',type=Path,required=True);p.add_argument('--bucket',default='liketocode789/EasyVtuberStudio');p.add_argument('--publish',action='store_true');p.add_argument('--prepare',action='store_true');p.add_argument('--core',type=Path);a=p.parse_args()
    root=a.root.resolve();stage=a.stage.resolve()
    if not stage.is_relative_to(root):raise ValueError('HF stage must be inside this project')
    if a.prepare:
        if not a.core:raise ValueError('--core is required to prepare the shared seed/sample inventory')
        prepare_stage(root,a.core.resolve(),stage)
    index,names=inventory(stage)
    print(json.dumps({'publish':a.publish,'bucket':a.bucket,'files':len(names),'bytes':sum((stage/n).stat().st_size for n in names),'artifacts':list(index['modules']),'index_uploaded_last':True},indent=2))
    if not a.publish:return 0
    python=root/'runtime/download_venv/Scripts/python.exe'
    if not python.is_file():raise ValueError('Prepare folder-local HF client first')
    for rel in names:
        if rel=='index.json':
            published=dict(index,published=True)
            receipt=root/'workspace/release/index.published.json';receipt.write_text(json.dumps(published,indent=2),'utf-8')
            src=receipt
        else:src=stage/rel
        subprocess.run([str(python),'-I','-m','huggingface_hub.cli.hf','buckets','cp',str(src),'hf://buckets/'+a.bucket+'/'+rel],check=True)
    print('Artifacts uploaded; read-back acceptance is still required before GitHub release.')
    return 0


if __name__=='__main__':raise SystemExit(main())
