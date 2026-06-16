"""Ensure the main load-preview module imports (wx.HotKeyEvent is absent on wx 4.2)."""
import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

import character_model_mediapipe_puppeteer_load_preview as main_mod

assert hasattr(main_mod, "MainFrame")
print("smoke_main_import_ok")
