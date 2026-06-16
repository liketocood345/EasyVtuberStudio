# Hugging Face Bucket 大文件镜像与完整发行（维护者）

面向维护者：**liketocode789/EasyVtuberStudio** 桶既是 **完整可下载的 EasyVtuberStudio 项目**（用户 `hf buckets sync` 到本地即可 `DEPLOY.bat`），也是 GitHub CORE 瘦包的 **大文件补充源**（DEPLOY 档位 [5] 等从此拉取 `data/ezvtb_nn/`）。

**Bucket 页面：** https://huggingface.co/buckets/liketocode789/EasyVtuberStudio  
**Bucket ID：** `liketocode789/EasyVtuberStudio`

相关：[DEPLOY.md](DEPLOY.md) · [PREP_PUSH.md](PREP_PUSH.md) · [ADDONS_LAYOUT.md](ADDONS_LAYOUT.md) · `packaging/upstream_assets.json`

---

## 1. 双角色：完整发行 + 瘦包补充

| 位置 | 放什么 | 说明 |
|------|--------|------|
| **GitHub `main`（CORE ZIP）** | 代码、exe、示例角色、DEPLOY 脚本 | 瘦包；**不含** `data/ezvtb_nn/*.onnx` |
| **HF Bucket** | **完整项目树**（与 CORE 同步 + 已内置 `data/ezvtb_nn/`） | 用户可 `hf buckets sync` 整目录下载即用；亦供 GitHub 瘦包 DEPLOY 拉取大文件 |
| **用户本机 `addons/`** | DEPLOY 安装的可选包 | 不入 Git |

从 CORE 迁出的大文件：**`data/ezvtb_nn/`**（档位 **[5] output_enhancement**，约 270 MB ONNX）。  
THA3 / THA4 / MediaPipe 仍由 `packaging/fetch_upstream_assets.ps1` 按 `upstream_assets.json` 从既有上游镜像拉取（**非**本 Bucket 主路径）。

**用户下载方式（见 `packaging/hf_bucket_README.md`）：**

- **方式 A**：`hf buckets sync` 整个 Bucket → 本地已有完整目录 + NN 权重  
- **方式 B**：GitHub ZIP → `DEPLOY.bat` → 档位 [5] 从 Bucket 补全 `data/ezvtb_nn/`

---

## 2. 本地 HF 同步仓 `EasyVtuberStudio-hf`

**不是 Git 仓库**，仅作 `hf buckets sync` 的本地源目录。

```text
E:\EasyVtuberStudio-hf\          # 维护者本机路径（可改）
├── README.md                    # 本目录说明（勿删）
├── data\ezvtb_nn\               # 上传后 DEPLOY [5] 从此路径拉取
├── packaging\                   # 与 main 同步的脚本（便于验收）
└── …                            # 自 easyvtuberstudio-main 复制的其余 CORE 文件
```

### 2.1 首次准备（上传前）

1. **更新文档**（本节所列 MD 与 `data/ezvtb_nn/README.md` 须与 Bucket 策略一致）。
2. **从 main 复制到镜像目录**（排除 `.git`）：

```powershell
$src = "E:\easyvtuberstudio-main"
$dst = "E:\EasyVtuberStudio-hf"
New-Item -ItemType Directory -Force -Path $dst | Out-Null
robocopy $src $dst /MIR /XD .git .codegraph /NFL /NDL /NJH /NJS /nc /ns /np
```

3. **确认权重在镜像内存在**：

```powershell
Test-Path E:\EasyVtuberStudio-hf\data\ezvtb_nn\rife\rife_x2_fp32.onnx
```

4. **登录 Hugging Face**（不要用 PowerShell 交互粘贴 token，易带入 `\x00` 乱码）：

```powershell
# 1) 打开 https://huggingface.co/settings/tokens 新建 Write token
# 2) 用记事本另存为 UTF-8 单行，例如 C:\Users\WXH\hf_token.txt（仅 hf_ 开头字符串）
powershell -ExecutionPolicy Bypass -File E:\easyvtuberstudio-develop\scripts\maint\hf_login_from_file.ps1 -TokenFile C:\Users\WXH\hf_token.txt
```

若出现 `Illegal header value b'Bearer \x00...'`：说明 token 损坏，删 `C:\Users\WXH\.cache\huggingface\token`（若存在），用上面「从文件登录」重试。

5. **先 dry-run，再正式上传**：

```powershell
cd E:\easyvtuberstudio-develop
powershell -ExecutionPolicy Bypass -File scripts\maint\sync_develop_to_hf_bucket.ps1 -MirrorRoot E:\EasyVtuberStudio-hf -DryRun
powershell -ExecutionPolicy Bypass -File scripts\maint\sync_develop_to_hf_bucket.ps1 -MirrorRoot E:\EasyVtuberStudio-hf
```

**Bucket 首页 README**（用户可见）：编辑 `packaging/hf_bucket_README.md`，复制到镜像并单独上传：

```powershell
Copy-Item E:\easyvtuberstudio-develop\packaging\hf_bucket_README.md E:\EasyVtuberStudio-hf\README.md -Force
python -m huggingface_hub.cli.hf buckets cp E:\EasyVtuberStudio-hf\README.md hf://buckets/liketocode789/EasyVtuberStudio/README.md
```

上传后 Bucket 内路径示例：`data/ezvtb_nn/rife/rife_x2_fp32.onnx`（与仓库相对路径一致）。

### 2.2 日常刷新权重

1. 在 **main** 或 develop 用 `scripts\maint\import_ezvtb_nn_weights.ps1` 更新 `data\ezvtb_nn\`。
2. 再次 `robocopy` 到 `EasyVtuberStudio-hf`（或只复制 `data\ezvtb_nn`）。
3. 重跑 `sync_develop_to_hf_bucket.ps1`（无 `-DryRun`）。

### 2.3 main 仓库与瘦包验收（已完成）

- **easyvtuberstudio-main** 已移除 `data/ezvtb_nn/**/*.onnx`（保留 `README.md` 占位）。  
- **`verify_fresh_extract.ps1`** 要求 CORE **不含** ONNX，仅含 `data/ezvtb_nn/README.md`。  
- **EasyVtuberStudio-hf** 镜像目录保留 ONNX，供 Bucket 全量发行。

---

## 3. 用户侧 DEPLOY 行为（摘要）

| 档位 | 首选源 | 备份源 |
|------|--------|--------|
| **[5] output_enhancement** | Bucket `data/ezvtb_nn/` | `import_ezvtb_nn_weights.ps1`（Google Drive 数据包） |
| **[2] mediapipe** | Google MediaPipe 官方 URL | — |
| **[3] tha3_models** | HF `ksuriuri/talking-head-anime-3-models` | Dropbox zip |
| **[4] tha4_training** | pkhungurn Dropbox | — |

实现：`upstream_assets.json` 包 `ezvtb_nn_weights` + `fetch_hf_bucket.py` + `bootstrap_output_enhancement.ps1`。

---

## 4. 额度与可见性

- Bucket 为 **公开**；计入账号 **Public storage**（免费档为 best-effort，见 [Storage limits](https://huggingface.co/docs/hub/storage-limits)）。
- 当前 Bucket 全量约 **350 MB**（完整 CORE + `data/ezvtb_nn/`）；勿 sync 整仓 develop（~12 GB）。

---

## 5. 上传前文档检查清单

- [ ] [HF_BUCKET_MIRROR.md](HF_BUCKET_MIRROR.md)（本文）
- [ ] [data/ezvtb_nn/README.md](../data/ezvtb_nn/README.md)
- [ ] [DEPLOY.md](DEPLOY.md) § CORE / 档位 [5]
- [ ] [PREP_PUSH.md](PREP_PUSH.md) § 应入库 / HF 同步
- [ ] [ADDONS_LAYOUT.md](ADDONS_LAYOUT.md) § output_enhancement
- [ ] [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) § Q5a / Q5g

---

*维护者：上传 Bucket 前请完成 §5 勾选；用户文档以 DEPLOY.md 与 TROUBLESHOOTING_QA 为准。*
