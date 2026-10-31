"""Build runtime-free teacher module from its verified installation. No upload."""
from pathlib import Path
import subprocess,sys
root=next(p for p in Path(__file__).resolve().parents if (p/'DEPLOY.bat').is_file())
raise SystemExit(subprocess.call([str(root/'runtime/python310/python.exe'),'-I',str(root/'packaging/resource_modules.py'),'build','--root',str(root),'--module','tha4_training',*sys.argv[1:]]))
