# EasyVtuberStudio 便携发行版计划（主路线）

> **状态：** Phase 1–3 已落地；Phase 4 待上传 Release 7z 并填写 manifest URL  
> **应用图标：** [assets/branding/app-icon-source.ico](../assets/branding/app-icon-source.ico)（仅 **EasyVtuberStudio.exe**）  
> **备选路线：** [PACKAGING_EXE.plan.md](PACKAGING_EXE.plan.md)

## 入口对照

| 角色 | 路径 |
|------|------|
| 面捕主入口 | 根目录 **`EasyVtuberStudio.exe`**（首次启动自动 bootstrap） |
| 开发回退 | `scripts/launch/run_load_preview_puppeteer.bat` |
| 训练 | `scripts/launch/THA4Train.exe` |
| THA3 + THA4 训练包 | 根目录 **`DEPLOY.bat`**，或 `scripts/launch/THA3_DownloadModels.bat`、`THA4_DownloadTrainingAssets.bat` |
| 手动 THA3 / THA4 训练 | `scripts/launch/THA3_DownloadModels.bat`、`THA4_DownloadTrainingAssets.bat` |
| 手动补全 runtime | `scripts/launch/THA4_DownloadAssets.bat`（与 exe 引导等价） |
| 首次引导脚本 | `packaging/bootstrap_portable.ps1` |
| manifest | `packaging/assets_manifest.json` |
| 编译 exe | `scripts/build_launchers.bat` |
| 维护者一键准备 | `scripts/maint/prepare_portable_release.ps1` |

## 用户路径（目标）

1. GitHub **Download ZIP** → 解压  
2. 双击 **`EasyVtuberStudio.exe`**（首次自动下载/安装 runtime + data）

## 维护者

1. `scripts/maint/prepare_portable_release.ps1 -BuildLaunchers -BuildReleaseAssets -WriteManifestHashes`  
2. 上传 `packaging/release_assets/*.7z` 到 GitHub Release  
3. 填写 `packaging/assets_manifest.json` → `release_base_url`  
4. `scripts/maint/sync_develop_to_fork.ps1` → fork push

## Bootstrap 优先级

1. GitHub Release 7z（manifest `url` 或 `release_base_url` + `filename`）— **仅 `runtime` 为首次启动必需**
2. 复制本机 dev `venv` → `runtime/venv`（维护者机器）
3. 系统 Python 3.10/3.11 + `deps/pip` requirements（慢，离线 ZIP 无 Release 时的兜底）

## GitHub 主包不含（原作者渠道一键下载）

| 附加包 | 获取方式 |
|--------|----------|
| **THA3 官方 PyTorch 模型** (~2 GB) | 根目录 **`DEPLOY.bat`**、`scripts/launch/THA3_DownloadModels.bat` 或应用内 THA3 提示 |
| **THA4 Teacher + pose_dataset** | 根目录 **`DEPLOY.bat`**、`scripts/launch/THA4_DownloadTrainingAssets.bat` 或 `THA4Train.exe` 提示 |

上游配置：`packaging/upstream_assets.json` · 执行脚本：`packaging/fetch_upstream_assets.ps1`
