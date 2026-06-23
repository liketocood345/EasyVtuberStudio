# Add-ons layout (EasyVtuberStudio portable)

## Overview

The GitHub **CORE** ZIP is slim: application code, `EasyVtuberStudio.exe`, and the bundled **THA4 Student (bai)** character. **`data/ezvtb_nn/*.onnx` is not in GitHub ZIP** (HF Bucket full release or DEPLOY tier [5]). Heavy optional assets install into `addons/` and are linked into legacy paths so existing scripts keep working.

```text
EasyVtuberStudio/
├── EasyVtuberStudio.exe
├── DEPLOY.bat              # six tiers: enter numbers (e.g. 1, 2, 136)
├── RESET_ADDON.bat         # remove one add-on + reconcile
├── data/character_models/  # CORE (bai student)
├── deps/tha3/              # THA3 code only in ZIP
├── addons/                 # optional packs (physical files)
│   ├── openseeface/Binary/facetracker.exe + models/
│   ├── face_puppeteer/venv + mediapipe/
│   ├── tha3_models/
│   ├── tha4_training/tha4 + pose_dataset.pt
│   └── output_enhancement/ezvtb_data/  # DEPLOY [5]: from HF Bucket data/ezvtb_nn (fallback: import script)
└── workspace/              # user state + ezvtb_engines TRT cache (gitignored)
```

## Junction strategy

| CORE path (link) | Target when add-on installed |
|------------------|------------------------------|
| `runtime/venv` | `addons/face_puppeteer/venv` |
| `data/thirdparty/mediapipe` | `addons/face_puppeteer/mediapipe` |
| `deps/tha3/models` | `addons/tha3_models` |
| `demo/data/tha4` | `addons/tha4_training/tha4` |
| `demo/data/pose_dataset.pt` | `addons/tha4_training/pose_dataset.pt` |

Run `packaging/reconcile_portable_layout.ps1` after manual deletes or migration.

## DEPLOY tiers (enter numbers; Enter = [1] only)

| Tier | Default (empty input) | Installs | Approx size |
|------|----------------------|----------|-------------|
| **[1] basic_run** | **yes** | `workspace/student_venv` (torch + wx) | ~2–4 GB |
| **[2] openseeface** | no | `addons/openseeface` (facetracker + models) | ~0.2 GB |
| **[3] face_puppeteer** | no | `addons/face_puppeteer` + MediaPipe | ~3–4 GB |
| **[4] tha3_models** | no | THA3 portrait weights | ~2 GB |
| **[5] tha4_training** | no | teacher + pose dataset | ~1.5–3 GB |
| **[6] output_enhancement** | no | onnxruntime + NN SR/RIFE data layout | ~0.8 GB+ |

Camera face capture: install **[2] openseeface** **or** **[3] face_puppeteer** (either is enough).

`EasyVtuberStudio.exe` starts when **basic_run** (or face runtime / system Python with torch+wx) is already satisfied; otherwise it directs the user to **DEPLOY.bat** (no silent auto-install).

**output_enhancement [5]:** Installs pip packages; **downloads** RIFE / waifu2x / Real-ESRGAN ONNX from HF Bucket `data/ezvtb_nn/` (primary) into `addons/output_enhancement/ezvtb_data/` (fallback: `import_ezvtb_nn_weights.ps1`). TensorRT engines cache under `workspace/ezvtb_engines/`. Post-process NN controls stay **Off** until user enables them; tier [5] not installed → controls disabled + one-time hint (f-023). See [HF_BUCKET_MIRROR.md](HF_BUCKET_MIRROR.md).

## Reset

1. Run `RESET_ADDON.bat` or delete `addons/<pack>/`
2. Reconcile removes links and restores placeholders (e.g. `demo/data/tha4/placeholder.txt`)

## Migrating old installs

```powershell
powershell -ExecutionPolicy Bypass -File packaging\migrate_to_addons_layout.ps1
```

Moves legacy `runtime/venv`, `deps/tha3/models`, and demo THA4 files into `addons/`, then reconciles.

## Maintainer scripts

| Script | Purpose |
|--------|---------|
| `packaging/addons_manifest.json` | Add-on IDs, verify paths |
| `packaging/addon_paths.ps1` | Shared path helpers |
| `packaging/reconcile_portable_layout.ps1` | Rebuild junctions |
| `packaging/verify_fresh_extract.ps1` | Slim ZIP QA |
| `packaging/build_github_zip.ps1` | `-IncludeRuntime` optional (default off) |
