# Add-ons layout (EasyVtuberStudio portable)

## Overview

The GitHub **CORE** ZIP is slim: application code, `EasyVtuberStudio.exe`, and the bundled **THA4 Student (bai)** character. Heavy optional assets install into `addons/` and are linked into legacy paths so existing scripts keep working.

```text
EasyVtuberStudio/
├── EasyVtuberStudio.exe
├── DEPLOY.bat              # four Y/N tiers: basic / face / THA3 / THA4 train
├── RESET_ADDON.bat         # remove one add-on + reconcile
├── data/character_models/  # CORE (bai student)
├── deps/tha3/              # THA3 code only in ZIP
├── addons/                 # optional packs (physical files)
│   ├── face_puppeteer/venv + mediapipe/
│   ├── tha3_models/
│   └── tha4_training/tha4 + pose_dataset.pt
└── workspace/              # user state (gitignored)
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

## DEPLOY tiers (Y/N; Enter = default)

| Tier | Default Enter | Installs | Approx size |
|------|---------------|----------|-------------|
| **basic_run** | **Y** | `workspace/student_venv` (torch + wx) | ~2–4 GB |
| face_puppeteer | N | `addons/face_puppeteer` + MediaPipe | ~3–4 GB |
| tha3_models | N | THA3 portrait weights | ~2 GB |
| tha4_training | N | teacher + pose dataset | ~1.5–3 GB |

`EasyVtuberStudio.exe` starts when **basic_run** (or face runtime / system Python with torch+wx) is already satisfied; otherwise it directs the user to **DEPLOY.bat** (no silent auto-install).

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
