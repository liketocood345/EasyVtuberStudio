"""Install measured Windows wheels from a hash-locked, folder-local recipe.

No copied venvs, user site, resolver-selected versions or system Python. Profiles
are additive: selecting teacher adds its extras to the same common environment.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(2**20), b''): h.update(b)
    return h.hexdigest()


def child(root, rel):
    p = (root / rel).resolve()
    if not p.is_relative_to(root): raise ValueError('Path escapes installation: ' + str(p))
    return p


def acquire(root, item, offline=False):
    target = child(root, 'workspace/asset_downloads/wheels/' + item['filename'])
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and sha(target) == item['sha256']: return target
    # Module copy-in is untrusted until the wheel hash from the shipped recipe
    # matches. Never extract arbitrary members into runtime or workspace.
    for directory in ['workspace/modules','workspace/imports/modules']:
        for module in child(root,directory).glob('runtime-*.zip'):
            try:
                with zipfile.ZipFile(module) as z:
                    if item['filename'] not in z.namelist(): continue
                    part=target.with_suffix(target.suffix+'.part')
                    with z.open(item['filename']) as src,part.open('wb') as dst:
                        while b := src.read(2**20): dst.write(b)
                    if sha(part)==item['sha256']: part.replace(target); return target
            except (OSError,zipfile.BadZipFile): continue
    url = item['url']
    if item.get('origin') == 'built-from-verified-sdist':
        source = acquire(root, {**item['source'], 'name':item['name']+'-source'}, offline)
        # Import an adjacent shipped adapter under -I (script directory is not
        # automatically on sys.path in isolated mode).
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from antlr_wheel import build
        build(source, target)
        if sha(target) != item['sha256']: raise ValueError('Rebuilt ANTLR wheel hash mismatch')
        return target
    if offline: raise ValueError('Verified offline wheel missing: ' + target.name)
    if not url.startswith('https://'): raise ValueError('Expected HTTPS artifact URL')
    # bh-6 26.10.31 16:10 s
    if item.get('origin') == 'official-pytorch' or 'download.pytorch.org' in url or 'download-r2.pytorch.org' in url:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from fetch_verified_wheels import fetch
        pinned = url if '#sha256=' in url else (url + '#sha256=' + item['sha256'])
        fetched = fetch(pinned, target.parent)
        if sha(fetched) != item['sha256']: raise ValueError('Wheel integrity mismatch: ' + target.name)
        return fetched
    part = target.with_suffix(target.suffix + '.part')
    print('Fetching locked wheel:', target.name, flush=True)
    req = urllib.request.Request(url, headers={'User-Agent': 'EasyVtuberStudio-deploy/1', 'Accept-Encoding': 'identity'})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as src, part.open('wb') as out:
                while b := src.read(2**20): out.write(b)
            last = None
            break
        except Exception as exc:
            last = exc
            print('Wheel fetch retry:', target.name, type(exc).__name__, flush=True)
            if part.exists(): part.unlink()
    if last is not None: raise last
    if sha(part) != item['sha256']: raise ValueError('Wheel integrity mismatch: ' + target.name)
    part.replace(target)
    return target
    # bh-6 26.10.31 16:10 e


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--python', type=Path)
    p.add_argument('--profile', action='append', required=True)
    p.add_argument('--download-only', action='store_true')
    p.add_argument('--offline', action='store_true')
    a = p.parse_args()
    if 'base' not in a.profile: a.profile.insert(0,'base')
    root = a.root.resolve()
    recipe = json.loads((root/'deps/pip/runtime-artifacts.json').read_text('utf-8'))
    names = set()
    for profile in a.profile: names.update(recipe['profiles'][profile])
    files = []
    for name in sorted(names):
        item = recipe['artifacts'][name]
        path = acquire(root, item, a.offline)
        files.append((item, path))
    if a.download_only: return 0
    python = (a.python or Path(sys.executable)).resolve()
    if not python.is_relative_to(root): raise ValueError('External Python rejected')
    # Validation uses the target process, not the interpreter driving this tool.
    subprocess.run([str(python), '-I', '-c',
        'import pathlib,sys; r=pathlib.Path(sys.argv[1]); assert all(pathlib.Path(x).resolve().is_relative_to(r) for x in (sys.executable,sys.prefix,sys.base_prefix)); assert sys.prefix != sys.base_prefix', str(root)], check=True)
    req = child(root, 'workspace/asset_downloads/locked-' + '-'.join(sorted(a.profile)) + '.txt')
    req.write_text(''.join(f"{item['name']} @ {path.as_uri()} --hash=sha256:{item['sha256']}\n" for item,path in files), 'utf-8')
    env = os.environ.copy()
    env.update(PIP_CONFIG_FILE='NUL', PYTHONNOUSERSITE='1', PIP_DISABLE_PIP_VERSION_CHECK='1')
    subprocess.run([str(python), '-I', '-m', 'pip', 'install', '--require-virtualenv',
        '--no-index', '--no-deps', '--require-hashes', '--progress-bar', 'off', '-r', str(req)], check=True, env=env)
    subprocess.run([str(python), '-I', '-m', 'pip', 'check'], check=True, env=env)
    # bh-6 26.10.31 16:30 s
    # Cache zips are optional copy-in material. A zip OSError after pip check
    # must not fail DEPLOY: the venv is already hash-locked and importable.
    try:
        base=set(recipe['profiles']['base'])
        for profile in a.profile:
            selected=set(recipe['profiles'][profile])
            if profile!='base': selected-=base
            module = child(root, 'workspace/modules/runtime-' + profile + '.zip')
            module.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(module, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as z:
                records=[]
                for item,path in files:
                    if item['name'] not in selected or item['name'].lower() in ('torch','torchvision'): continue
                    z.write(path,path.name); records.append(item)
                z.writestr('module.json', json.dumps({'profile':profile,'artifacts':records,'base_required':profile!='base','excluded_large_shared':['torch','torchvision']}, indent=2))
    except Exception as exc:
        print('Cache module zip skipped:', type(exc).__name__, exc, flush=True)
    # bh-6 26.10.31 16:30 e
    print('Hash-locked runtime ready:', ','.join(a.profile), flush=True)
    return 0


if __name__ == '__main__': raise SystemExit(main())
