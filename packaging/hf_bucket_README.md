---
title: EasyVtuberStudio
license: other
---

# EasyVtuberStudio

基于 **THA3 / THA4** 的可面捕虚拟皮套演播软件。本 Bucket 提供 **完整可下载、解压即用** 的项目目录，同时也作为 GitHub 瘦包的 **大文件补充源**。

| 获取方式 | 适合谁 |
|----------|--------|
| **本 Bucket（完整目录）** | 希望一次拿全代码 + NN 权重 + 脚本，本地直接 `DEPLOY.bat` |
| **[GitHub ZIP](https://github.com/liketocood345/EasyVtuberStudio)** | 体积更小；大文件由 DEPLOY 自动从此 Bucket 拉取 |

**Bucket 页面：** https://huggingface.co/buckets/liketocode789/EasyVtuberStudio  
**GitHub：** https://github.com/liketocood345/EasyVtuberStudio

---

## 快速开始（从本 Bucket 使用）

### 方式 A：下载整个项目到本地（推荐）

无需 Git；公开桶可直接同步到本地文件夹：

```powershell
# 需安装：pip install -U huggingface_hub
# 将下方路径改成你的解压目录，例如 D:\EasyVtuberStudio
python -m huggingface_hub.cli.hf buckets sync hf://buckets/liketocode789/EasyVtuberStudio D:\EasyVtuberStudio
```

同步完成后：

1. 进入该目录，确认有 `EasyVtuberStudio.exe`、`DEPLOY.bat`。  
2. 双击 **`DEPLOY.bat`**，按提示选择安装档位（首次建议前四档直接 Enter，只装 **[1] basic_run**）。  
3. 双击 **`EasyVtuberStudio.exe`** 启动。

本桶已包含 **`data/ezvtb_nn/`**（NN 超分 / RIFE 权重）与 **`addons/openseeface/`**（OpenSeeFace facetracker + models）。安装档位 **[6] output_enhancement** 时通常无需再拉 ONNX；安装 **[2] openseeface** 时通常无需再下载 facetracker。

### 方式 B：从 GitHub 瘦包 + 自动补全

1. GitHub **Code → Download ZIP** 并解压。  
2. 运行 **`DEPLOY.bat`**；档位 **[5]** 会 **首选从此 Bucket** 下载 `data/ezvtb_nn/`（失败时回退备用源）。

详细说明见桶内 `docs/DEPLOY.md`、`docs/TROUBLESHOOTING_QA.md`。

---

## 本桶包含什么

这是一套 **与发布版同步的完整项目树**（约 350 MB+），而不仅是几个权重文件：

```text
EasyVtuberStudio/          ← 同步到本地的根目录
├── EasyVtuberStudio.exe     # 主程序
├── DEPLOY.bat               # 六档安装（basic / OSF / MediaPipe / THA3 / THA4 训练 / NN 后处理）
├── RESET_ADDON.bat
├── data/
│   ├── character_models/    # 示例 THA4 Student（bai）
│   └── ezvtb_nn/            # RIFE / waifu2x / Real-ESRGAN ONNX（档位 [5]）
├── face-puppeteer-ui-enhancements-ai-code/
├── packaging/               # 部署与验收脚本
├── docs/                    # 安装、排障、硬件要求
└── …
```

| 路径 | 说明 |
|------|------|
| `data/ezvtb_nn/` | 后处理 NN 权重（本桶已内置；GitHub 瘦包不含 ONNX） |
| `addons/openseeface/` | OpenSeeFace 面捕（本桶已内置；GitHub 瘦包不含） |
| `data/character_models/` | 自带示例角色，可立即 Load Other 试用 |
| `addons/face_puppeteer/` 等 | 其余可选包仍由 `DEPLOY.bat` 安装 |

**仍需 DEPLOY 安装的**：Python 运行时（档位 [1]）、MediaPipe 面捕（[3]）、THA3/THA4 训练权重等——与 GitHub 版相同，见 `DEPLOY.bat` 六档菜单。

---

## DEPLOY 六档（摘要）

| 档位 | 默认 | 内容 |
|------|------|------|
| **[1] basic_run** | Y | Mouse + THA4 Student 最小运行时 |
| **[2] openseeface** | N | OpenSeeFace 摄像头面捕（本桶已带二进制） |
| **[3] face_puppeteer** | N | MediaPipe 摄像头 / 窗口捕获 |
| **[4] tha3_models** | N | THA3 立绘权重（~2 GB，联网下载） |
| **[5] tha4_training** | N | THA4 训练 Teacher 权重 |
| **[6] output_enhancement** | N | NN 超分 / RIFE（本桶已带 ONNX，主要装 pip 包） |

摄像头面捕：安装 **[2]** 或 **[3]** 任一即可。

---

## 系统要求（摘要）

- Windows 10 / 11（64 位）  
- 建议 NVIDIA 独显（6 GB+ 显存）  
- 预留约 **15 GB** 磁盘（装全可选包时）  
- 安装过程需联网  

详见 `docs/HARDWARE_REQUIREMENTS.md`。

---

## 维护者说明

- **Bucket ID：** `liketocode789/EasyVtuberStudio`  
- **本地工作副本：** `EasyVtuberStudio-hf`（非 Git；与 main 同步后上传）  
- **全量上传：** `scripts/maint/sync_develop_to_hf_bucket.ps1`  
- **仅更新首页 README：**

```powershell
Copy-Item packaging\hf_bucket_README.md E:\EasyVtuberStudio-hf\README.md -Force
python -m huggingface_hub.cli.hf buckets cp E:\EasyVtuberStudio-hf\README.md hf://buckets/liketocode789/EasyVtuberStudio/README.md
```

---

## 许可与归属

- 项目代码与文档：见 GitHub 仓库。  
- THA3 / THA4 上游：pkhungurn 等原作者许可。  
- NN 权重：见 `data/ezvtb_nn/README.md` 与 `deps/tha3/ezvtuber_rt`。  

---

*liketocode789 · EasyVtuberStudio 完整发行与 GitHub 瘦包配套分发。*
