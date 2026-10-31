import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from core_release import clean_seed
p=argparse.ArgumentParser(); p.add_argument('--workspace',type=Path,required=True); a=p.parse_args()
for f in [a.workspace/'load_preview_ui_state.json',*(a.workspace/'basic_layers').rglob('*.json')]:
    if f.is_file(): f.write_text(json.dumps(clean_seed(json.loads(f.read_text('utf-8-sig'))),ensure_ascii=False,indent=2)+'\n','utf-8')
