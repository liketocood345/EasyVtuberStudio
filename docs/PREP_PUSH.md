# Fork 推送前检查清单

面向维护者：在 `E:\easyvtuberstudio-main` 执行 `git push origin main` 之前。

相关：[FORK_ROOT.md](FORK_ROOT.md) · [HANDOVER.md](HANDOVER.md) · [ADDONS_LAYOUT.md](ADDONS_LAYOUT.md)

---

## 1. 代码与脚本

| 检查 | 命令 / 说明 |
|------|-------------|
| develop → fork 已同步 | `powershell -ExecutionPolicy Bypass -File E:\easyvtuberstudio-develop\scripts\maint\sync_develop_to_fork.ps1` |
| 瘦包验收 | `packaging\verify_fresh_extract.ps1 -PortableRoot E:\easyvtuberstudio-main` |
| GitHub ZIP 构建（可选） | `packaging\build_github_zip.ps1 -ForkRoot E:\easyvtuberstudio-main` |
| 双仓角色 | `scripts\maint\verify_repo_roles.ps1` |
| 路径引用扫描 | `scripts\maint\verify_path_refs.ps1` |

**不要提交进 Git 的大目录**（见 `.gitignore`）：`addons/face_puppeteer/`、`addons/tha3_models/`、`addons/tha4_training/`、`workspace/student_venv/`、`runtime/`、`workspace/*` 用户状态、**`.codegraph/`**、**`**/his/`**（历史快照）、**`docs/training/`**（旧续训流程）、**`docs/oid.md`**（本地聊天摘录）。

**应入库的发布物**：`packaging/`、`DEPLOY.bat`、`EasyVtuberStudio.exe`（若本机已编译）、`docs/`、`data/character_models/baiten_*` 等 CORE 资源。

---

## 2. DEPLOY 四档（文档与菜单必须一致）

| 档位 | 默认 Enter | Package ID | 安装内容 |
|------|------------|------------|----------|
| **[1] basic_run** | Y | `mouse_student` | `workspace/student_venv`（torch + wx + matplotlib） |
| **[2] face_puppeteer** | N | `face_puppeteer` | `addons/face_puppeteer` + MediaPipe `.task` |
| **[3] tha3_models** | N | `tha3_models` | THA3 立绘权重 |
| **[4] tha4_training** | N | `tha4_training` | Teacher + pose 数据集 |

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

---

## 4. Git 推送（发布总库）

```bat
cd /d E:\easyvtuberstudio-main
git status
git add -A
git commit -m "your message"
git push origin main
```

推送后：GitHub **Download ZIP** 应为 CORE（无 runtime/可选包）；用户解压后运行 `DEPLOY.bat`。

---

## 5. 2026-05-31 本轮待推送要点（摘要）

- DEPLOY：重复安装、venv 复制后 pip 路径、`SkipTorchInstall` 与 `python -m pip`
- 面捕：`MOCAP_INPUT_MODE_MEDIAPIPE` 导入修复；`verify_deploy` 面捕 UI probe
- 文档：四档 Y/N 统一；本清单与 [DOC_INDEX.md](DOC_INDEX.md) 更新

详细条目见 [CHANGELOG.md](CHANGELOG.md) §2026-05-31。
