# Add-ons layout plan (fork release)

**Status:** Implemented in `e:\tha4fork` (2026-05).

Full user docs: [docs/ADDONS_LAYOUT.md](../docs/ADDONS_LAYOUT.md)

## Summary

- **CORE GitHub ZIP:** exe + code + THA4 Student (bai); no runtime / THA3 / THA4 training weights.
- **Optional packs** under `addons/`; `reconcile_portable_layout.ps1` links CORE paths.
- **DEPLOY.bat** 四档 Y/N：`[1] basic_run`，`[2] face_puppeteer`，`[3] tha3_models`，`[4] tha4_training`（Enter = 各档默认）。
- **RESET_ADDON.bat** 删除单个 add-on 并 reconcile。

## Key files

| File | Role |
|------|------|
| `packaging/addons_manifest.json` | Add-on IDs and verify paths |
| `packaging/addon_paths.ps1` | Shared helpers |
| `packaging/reconcile_portable_layout.ps1` | Junction rebuild |
| `packaging/verify_fresh_extract.ps1` | Slim ZIP QA |
| `packaging/migrate_to_addons_layout.ps1` | Legacy → addons migration |
| `packaging/build_github_zip.ps1` | Default `-IncludeRuntime:$false` |

## Acceptance

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_github_zip.ps1 -ForkRoot e:\tha4fork
# verify_fresh_extract runs on staging automatically
```

Original plan: Cursor plan `github_可选包目录结构_5ad26f34`.
