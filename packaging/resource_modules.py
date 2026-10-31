"""Verified per-tier resource modules: local/copy-in, upstream, then HF ark.

The same file contract validates installed assets, normalized upstream downloads
and fallback ZIPs. Modules never contain user workspace or shared runtimes.
OSF's frozen Binary ABI is a declared private exception, not a common Python.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import urllib.request
import uuid
import zipfile


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''): h.update(b)
    return h.hexdigest()


def local(root,relative):
    p=(root/relative).resolve()
    if not p.is_relative_to(root): raise ValueError('Module path escapes installation')
    return p


def valid(p,record): return p.is_file() and p.stat().st_size==record['size_bytes'] and sha(p)==record['sha256']


def verify(base,module):
    return all(valid(local(base,f['path']),f) for f in module['files'])


def safe_members(z):
    names=set()
    for info in z.infolist():
        p=PurePosixPath(info.filename.replace('\\','/'))
        if p.is_absolute() or '..' in p.parts or not p.parts or ':' in str(p) or stat.S_ISLNK(info.external_attr>>16): raise ValueError('Unsafe ZIP member: '+info.filename)
        if str(p).lower() in names: raise ValueError('Duplicate ZIP member')
        names.add(str(p).lower())
    return z.infolist()


def archive(root,module,output):
    target=local(root,module['install_root'])
    if not verify(target,module): raise ValueError('Installed payload failed file hashes: '+module['id'])
    output.parent.mkdir(parents=True,exist_ok=True)
    part=output.with_suffix('.zip.part')
    with zipfile.ZipFile(part,'w',zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        for f in module['files']: z.write(target/f['path'],f['path'])
        z.writestr('module.json',json.dumps(module,ensure_ascii=False,indent=2))
    part.replace(output)
    return {'path':f"packages/windows-x64/{module['id']}/{module['version']}/{module['id']}.zip",'sha256':sha(output),'size_bytes':output.stat().st_size}


def unpack(archive_path,stage,module):
    with zipfile.ZipFile(archive_path) as z:
        safe_members(z)
        contract=json.loads(z.read('module.json'))
        if contract!=module: raise ValueError('Module file contract/version mismatch')
        expected={f['path'] for f in module['files']}|{'module.json'}
        actual={i.filename for i in z.infolist() if not i.is_dir()}
        if actual!=expected: raise ValueError('Unexpected module contents')
        for f in module['files']:
            p=local(stage,f['path']); p.parent.mkdir(parents=True,exist_ok=True)
            with z.open(f['path']) as src,p.open('wb') as dst: shutil.copyfileobj(src,dst)
    if not verify(stage,module): raise ValueError('Module payload hash mismatch')


def upstream(root,stage,module,refresh=False):
    sources={}
    cache=local(root,'workspace/asset_downloads/resources'); cache.mkdir(parents=True,exist_ok=True)
    for spec in module['sources']:
        target=cache/spec['filename']
        part=target.with_suffix(target.suffix+'.part')
        # Cached upstream archives are untrusted until their required extracted
        # payload matches the locked file hashes. Never infer success by size.
        if refresh or not target.exists():
            print('Upstream:',spec['url'],flush=True)
            req=urllib.request.Request(spec['url'],headers={'User-Agent':'EasyVtuberStudio-deploy/1'})
            with urllib.request.urlopen(req,timeout=40) as src,part.open('wb') as dst: shutil.copyfileobj(src,dst,2**20)
            part.replace(target)
        if spec['kind']=='zip':
            z=zipfile.ZipFile(target); safe_members(z); sources[spec['id']]=z
        else: sources[spec['id']]=target
    try:
        for f in module['files']:
            dest=local(stage,f['path']); dest.parent.mkdir(parents=True,exist_ok=True)
            if 'from_core' in f:
                src=local(root,f['from_core'])
                if not valid(src,f): raise ValueError('CORE source/teacher shell version mismatch: '+f['from_core'])
                shutil.copyfile(src,dest)
            else:
                src=sources[f['source']]
                if isinstance(src,zipfile.ZipFile):
                    suffix=f.get('source_member',f['path'])
                    hits=[i for i in src.infolist() if not i.is_dir() and (i.filename.replace('\\','/')==suffix or i.filename.replace('\\','/').endswith('/'+suffix))]
                    if len(hits)!=1: raise ValueError('Upstream member absent/ambiguous: '+suffix)
                    with src.open(hits[0]) as data,dest.open('wb') as out: shutil.copyfileobj(data,out)
                else: shutil.copyfile(src,dest)
            if not valid(dest,f): raise ValueError('Upstream payload hash mismatch: '+f['path'])
    finally:
        for src in sources.values():
            if isinstance(src,zipfile.ZipFile): src.close()


def hf_fallback(root,stage,module):
    # Immutable artifact from the shipped release index, never an unpinned remote
    # latest.json. Creating the HF client happens only after upstream failure.
    index=json.loads((root/'packaging/resource-releases.json').read_text('utf-8'))
    release=index['modules'].get(module['id'])
    if not release or not release.get('artifact'): raise ValueError('HF backup not published for '+module['id'])
    item=release['artifact']
    prefix=f"packages/windows-x64/{module['id']}/{module['version']}/"
    if not item['path'].startswith(prefix) or '..' in PurePosixPath(item['path']).parts: raise ValueError('Invalid HF artifact prefix')
    command=Path(os.environ.get('SystemRoot',r'C:\Windows'))/'System32/WindowsPowerShell/v1.0/powershell.exe'
    code=". (Join-Path $env:EVS_ROOT 'packaging/portable_environment.ps1'); Get-LocalDownloadPython $env:EVS_ROOT"
    env=os.environ.copy(); env['EVS_ROOT']=str(root)
    result=subprocess.run([str(command),'-NoProfile','-ExecutionPolicy','Bypass','-Command',code],env=env,capture_output=True,text=True,check=True)
    python=result.stdout.strip().splitlines()[-1]
    dest=local(root,'workspace/asset_downloads/resources/'+module['id']+'-hf.zip')
    subprocess.run([python,'-I',str(root/'packaging/fetch_hf_bucket.py'),'download-file','--bucket',index['bucket_id'],'--remote',item['path'],'--local',str(dest)],check=True)
    if not valid(dest,item): raise ValueError('HF archive SHA256/size mismatch')
    unpack(dest,stage,module)


def install(root,module,offline=False):
    target=local(root,module['install_root'])
    module_cache=local(root,f"workspace/modules/{module['id']}-{module['version']}.zip")
    if verify(target,module):
        cache_contract=None
        try:
            with zipfile.ZipFile(module_cache) as z: cache_contract=json.loads(z.read('module.json'))
        except (OSError,ValueError,KeyError,zipfile.BadZipFile): pass
        if cache_contract!=module: archive(root,module,module_cache)
        print('Already installed, verified:',module['id'],flush=True)
        return 'installed'
    stage=local(root,'workspace/module-staging/'+module['id']+'-'+uuid.uuid4().hex); stage.mkdir(parents=True)
    mode=None
    for copy_in in [local(root,'workspace/imports/modules/'+module['id']+'.zip'),module_cache]:
        if not copy_in.exists(): continue
        try: unpack(copy_in,stage,module); mode='local-module'; break
        except (ValueError,KeyError,zipfile.BadZipFile) as e: print('Local module rejected:',type(e).__name__,flush=True)
    if not mode:
        if offline: raise ValueError('Offline verified module unavailable: '+module['id'])
        try:
            try: upstream(root,stage,module)
            except (ValueError,KeyError,zipfile.BadZipFile): upstream(root,stage,module,refresh=True)
            mode='upstream'
        except Exception as exc:
            print('Upstream failed/integrity mismatch; trying HF backup:',str(exc),flush=True)
            hf_fallback(root,stage,module); mode='hf-backup'
    if not verify(stage,module): raise ValueError('Incomplete staged module')
    # Preserve replaced bytes for rollback. Only known package files are written;
    # jobs, queue and user settings are never members of a module.
    backup=local(root,'workspace/module-backups/'+module['id']+'-'+uuid.uuid4().hex)
    for f in module['files']:
        src=local(stage,f['path']); dst=local(target,f['path'])
        if dst.exists() and not valid(dst,f):
            old=local(backup,f['path']); old.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(dst,old)
        dst.parent.mkdir(parents=True,exist_ok=True)
        pending=dst.with_name(dst.name+'.evs-part'); shutil.copyfile(src,pending); pending.replace(dst)
    archive(root,module,module_cache)
    print('Installed verified module:',module['id'],mode,flush=True)
    return mode


def main():
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['install','build','verify']); p.add_argument('--root',type=Path,required=True); p.add_argument('--module',action='append',required=True); p.add_argument('--offline',action='store_true'); p.add_argument('--output',type=Path)
    a=p.parse_args(); root=a.root.resolve()
    config=json.loads((root/'packaging/resource-lock.json').read_text('utf-8'))
    results={}
    for name in a.module:
        module=config['modules'][name]
        if a.action=='install': results[name]=install(root,module,a.offline)
        elif a.action=='verify':
            if not verify(local(root,module['install_root']),module): raise ValueError('Module verification failed: '+name)
            results[name]='verified'
        else:
            out=(a.output or local(root,'workspace/release/hf-stage/packages/windows-x64'))/name/module['version']/(name+'.zip')
            results[name]=archive(root,module,out)
    if a.action=='build':
        index_path=root/'packaging/resource-releases.json'
        index=json.loads(index_path.read_text('utf-8')) if index_path.is_file() else {'schema_version':1,'bucket_id':'liketocode789/EasyVtuberStudio','modules':{}}
        index['published']=False
        index['modules'].update({n:{'version':config['modules'][n]['version'],'artifact':x} for n,x in results.items()})
        (root/'packaging/resource-releases.json').write_text(json.dumps(index,indent=2)+'\n','utf-8')
    print(json.dumps(results,ensure_ascii=True,indent=2))


if __name__=='__main__': main()
