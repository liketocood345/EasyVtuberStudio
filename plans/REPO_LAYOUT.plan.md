# 仓库结构整理说明

> 2026-05-31：fork 根目录保留 **文件夹**、**`README.md`**、**`EasyVtuberStudio.exe`**、**`DEPLOY.bat`**（及 Git 点文件）。

## 路径对照

| 原根目录 | 新位置 |
|----------|--------|
| `DEPLOY.md`、`HANDOVER.md`、`TROUBLESHOOTING_QA.md` 等 | `docs/` |
| `run_load_preview_puppeteer.bat`、`》》》》start《《《《.bat` | `scripts/launch/` |
| `THA4Train.exe`、`THA4Train.bat` | `scripts/launch/` |
| `THA4_DownloadAssets.bat` | `scripts/launch/` |
| `build_launchers.bat` | `scripts/` |
| `assets_manifest.json` | `packaging/` |
| `load_preview_ui_state.json` | `workspace/` |

## 同步 develop → fork

```powershell
powershell -ExecutionPolicy Bypass -File scripts\maint\sync_develop_to_fork.ps1
```

脚本会镜像代码/docs/packaging/scripts，保留 fork 的 `.git` 与本地 `venv/`，并再次整理 fork 根目录。
