"""Local CORE-only GitHub tree sync. Never stages, commits or pushes."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core_release import verify


def git(root,*args):
    return subprocess.run(['git','-C',str(root),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout


def sync(core,target):
    verify(core)
    if git(target,'status','--porcelain','--untracked-files=normal').strip():
        raise ValueError('GitHub worktree has local changes; refusing to overwrite. Use an isolated clean checkout.')
    inventory=json.loads((core/'core-files.json').read_text('utf-8'))
    names={x['path'] for x in inventory['files']}|{'core-files.json'}
    tracked=set(git(target,'ls-files','-z').decode('utf-8').strip('\0').split('\0'))-{''}
    removed=sorted(tracked-names)
    # Validate every target before mutating anything. No recursive delete/move.
    for rel in sorted(names|tracked):
        dest=target/rel
        if not dest.resolve().is_relative_to(target):raise ValueError('GitHub target path escaped root: '+rel)
        if dest.exists() and not dest.is_file():raise ValueError('Directory/submodule sync requires explicit handling: '+rel)
    backup=target/'workspace/github-sync-backups'/uuid.uuid4().hex
    for rel in removed:
        src=target/rel
        if not src.exists():continue
        dst=backup/rel
        assert dst.resolve().is_relative_to(target)
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst);src.unlink()
    for rel in sorted(names):
        src=core/rel;dst=target/rel
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    result={'copied_CORE_files':len(names),'removed_from_public_tree':removed,'preserved_private_backup':str(backup) if removed else None,'staged':False,'committed':False,'pushed':False}
    print(json.dumps(result,ensure_ascii=True,indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--target',type=Path,required=True);a=p.parse_args()
    sync(a.core.resolve(),a.target.resolve())
