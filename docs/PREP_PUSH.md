# Fork 推送前检查清单

面向维护者：在 `E:\easyvtuberstudio-main` 执行 `git push origin main` 之前。

相关：[FORK_ROOT.md](FORK_ROOT.md) · [HANDOVER.md](HANDOVER.md) · [ADDONS_LAYOUT.md](ADDONS_LAYOUT.md) · [HF_BUCKET_MIRROR.md](HF_BUCKET_MIRROR.md)

---

## 1. 代码与脚本

| 检查 | 命令 / 说明 |
|------|-------------|
| develop → fork 已同步 | `powershell -ExecutionPolicy Bypass -File E:\easyvtuberstudio-develop\scripts\maint\sync_develop_to_fork.ps1`（含 bug 热点清单刷新） |
| Git hooks 已安装（一次性） | `powershell -ExecutionPolicy Bypass -File E:\easyvtuberstudio-main\scripts\maint\install_git_hooks.ps1` |
| 瘦包验收 | `packaging\verify_fresh_extract.ps1 -PortableRoot E:\easyvtuberstudio-main` |
| GitHub ZIP 构建（可选） | `packaging\build_github_zip.ps1 -ForkRoot E:\easyvtuberstudio-main` |
| 双仓角色 | `scripts\maint\verify_repo_roles.ps1` |
| 路径引用扫描 | `scripts\maint\verify_path_refs.ps1` |
| HF Bucket 已同步（若本轮迁出权重） | `sync_develop_to_hf_bucket.ps1 -MirrorRoot E:\EasyVtuberStudio-hf -DryRun` 后再正式上传 |

**不要提交进 Git 的大目录**（见 `.gitignore`）：`addons/openseeface/`、`addons/face_puppeteer/`、`addons/tha3_models/`、`addons/tha4_training/`、`addons/output_enhancement/`、`workspace/student_venv/`、`runtime/`、`workspace` 下日志/部署标记/`ezvtb_engines` 等本地状态、**`.codegraph/`**、**`**/his/`**（历史快照）、**`docs/training/`**（旧续训流程）、**`docs/oid.md`**（本地聊天摘录）。

**应入库的发布物**：`packaging/`、`DEPLOY.bat`、`EasyVtuberStudio.exe`（若本机已编译）、`docs/`、`data/character_models/baiten_*` 等 CORE 资源；以及 **种子持久化记忆**：`workspace/load_preview_ui_state.json`、`workspace/basic_layers/`、`workspace/region_wobble_mask*.png`（由 `sync_develop_to_fork.ps1` 从 develop 拷入；见 `scripts/maint/workspace_shipped_memory.ps1`）。

**不要入库、改放 HF Bucket 的大文件**（见 [HF_BUCKET_MIRROR.md](HF_BUCKET_MIRROR.md)）：

- `addons/openseeface/`（档位 **[2]**，约 210 MB）→ Bucket `liketocode789/EasyVtuberStudio`；用 `scripts\maint\import_openseeface_to_hf_mirror.ps1` 导入镜像
- `data/ezvtb_nn/**/*.onnx`（档位 **[6]**，约 270 MB）→ 同上 Bucket；可保留 `data/ezvtb_nn/README.md` 占位

**HF 同步仓（本机，非 Git）：** `E:\EasyVtuberStudio-hf` — 自 main 复制后执行 `scripts\maint\sync_develop_to_hf_bucket.ps1`。**上传 Bucket 前**须完成 [HF_BUCKET_MIRROR.md](HF_BUCKET_MIRROR.md) §5 文档勾选。

---

## 2. DEPLOY 六档（文档与菜单必须一致）

| 档位 | 默认 Enter | Package ID | 安装内容 |
|------|------------|------------|----------|
| **[1] basic_run** | Y | `mouse_student` | `workspace/student_venv`（torch + wx + matplotlib） |
| **[2] openseeface** | N | `openseeface` | OpenSeeFace facetracker + models（HF Bucket 首选） |
| **[3] face_puppeteer** | N | `face_puppeteer` | `addons/face_puppeteer` + MediaPipe `.task` |
| **[4] tha3_models** | N | `tha3_models` | THA3 立绘权重 |
| **[5] tha4_training** | N | `tha4_training` | Teacher + pose 数据集 |
| **[6] output_enhancement** | N | `output_enhancement` | onnxruntime + pyanime4k；从 HF Bucket `data/ezvtb_nn/` 拉取 ONNX |

摄像头面捕：安装 **[2] openseeface** 或 **[3] face_puppeteer** 其一即可。

用户场景：**先装 [1]，再勾选 [1]+[2]+[3]** 应能成功（bootstrap 用 `python -m pip`，复制 venv 后 `venv --upgrade`）。

---

## 3. 文档一致性

推送前确认以下文档 tier 编号、软件名 **EasyVtuberStudio** 一致：

- [README.md](../README.md)
- [DEPLOY.md](DEPLOY.md)
- [ADDONS_LAYOUT.md](ADDONS_LAYOUT.md)
- [addons/README.md](../addons/README.md)
- [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md)
- [CHANGELOG.md](CHANGELOG.md)
- [CODEBASE_MAP.md](CODEBASE_MAP.md)
- [BUG_HOTSPOT_CHECKLIST.md](BUG_HOTSPOT_CHECKLIST.md)
- [HANDOVER.md](HANDOVER.md)
- [HF_BUCKET_MIRROR.md](HF_BUCKET_MIRROR.md)
- 实验索引：`face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/CUSTOM_FUNCTION_INDEX.md`

研发手册（**不入 Git**）：`E:\record\easyvtuberstudio条目设计手册.md`（ix-023 / ix-025 校准界限以该手册为准）。

---

## 4. Git 推送（发布总库）

```bat
cd /d E:\easyvtuberstudio-main
git status
git add -A
git commit -m "your message"
git push origin main
```

**push 后**：`post-push` hook 自动运行 `scripts\maint\refresh_bug_hotspot_checklist.ps1`，从 `e:\record\labeled_prompt.md` 刷新 `docs\BUG_HOTSPOT_CHECKLIST.md`（develop + main 双副本）。首次需执行 `scripts\maint\install_git_hooks.ps1` 安装 hook。

推送后：GitHub **Download ZIP** 应为 CORE（无 runtime/可选包）；用户解压后运行 `DEPLOY.bat`。

**建议 commit 主题（2026-06-15 批次）**：

```text
Layer circular orbit + mouse calibration boundaries + window capture perf.

- Orbit motion, aux-slot requisition, orbit edit chrome, binding follow tilt
- Three calibration paths (ix-025): periodic = auto-click matching button
- Window capture method cache, downscale, stall recovery; CODEBASE_MAP docs
```

---

## 5. 2026-06-15 本轮待推送要点（摘要）

- **图层**：圆周运动 + 辅助槽征用 + 轨道编辑 UI；堆栈增删基础（L2 起步）
- **校准**：ix-025 三条路径/三条周期；Mouse 中心区 fitted 一致；`_perform_*` 统一手动与周期
- **窗口捕获**：抓取缓存、worker 缩帧、长时卡顿缓解（`smoke_window_capture.py`）
- **文档**：`CHANGELOG` §2026-06-15、`CODEBASE_MAP`、`BUG_HOTSPOT_CHECKLIST`、hooks 刷新链

详细条目见 [CHANGELOG.md](CHANGELOG.md) §2026-06-15。
