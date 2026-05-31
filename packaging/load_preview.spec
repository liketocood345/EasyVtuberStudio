# -*- mode: python ; coding: utf-8 -*-
# THA4 Load Preview — PyInstaller spec (draft / P2)
# Build:  venv\Scripts\pyinstaller packaging\load_preview.spec --noconfirm
# Icon:   assets/branding/app-icon-source.ico

from pathlib import Path

REPO = Path(SPECPATH).resolve().parent
EXP = REPO / "face-puppeteer-ui-enhancements-ai-code" / "experiments" / "puppeteer_load_preview"
DEMO_SRC = REPO / "face-puppeteer-ui-enhancements-ai-code" / "talking-head-anime-4-demo" / "src"
ICON = REPO / "assets" / "branding" / "app-icon-source.ico"
ENTRY = EXP / "character_model_mediapipe_puppeteer_load_preview.py"

block_cipher = None

# TODO(P1): frozen get_app_root() before relying on this layout.
datas = [
    (str(REPO / "deps" / "tha3"), "deps/tha3"),
]

hiddenimports = [
    "wx",
    "wx.adv",
    "PIL",
    "cv2",
    "numpy",
    "mediapipe",
    "torch",
    "sounddevice",
]

a = Analysis(
    [str(ENTRY)],
    pathex=[str(DEMO_SRC), str(EXP)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[str(REPO / "packaging" / "hooks")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="THA4LoadPreview",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # TODO: False after smoke; keep True for first builds
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="THA4LoadPreview",
)
