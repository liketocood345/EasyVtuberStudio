"""Compatibility entry for the runtime-free, source-first teacher module."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from resource_modules import install
PREFIX='packages/windows-x64/tha4_training/'
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,required=True); p.add_argument('--target',type=Path); a=p.parse_args()
    root=a.root.resolve()
    if a.target and a.target.resolve()!=root/'addons/tha4_training': raise ValueError('Teacher must remain in installation addons')
    config=json.loads((root/'packaging/resource-lock.json').read_text('utf-8'))
    install(root,config['modules']['tha4_training'])
