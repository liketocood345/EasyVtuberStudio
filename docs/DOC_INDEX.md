# EasyVtuberStudio — 文档总索引

> **软件名称：** **EasyVtuberStudio**（主程序 `EasyVtuberStudio.exe`）  
> **发布总库** `E:\easyvtuberstudio-main` 根目录仅保留 `README.md` + `EasyVtuberStudio.exe` + 文件夹；说明文档集中在 `docs/`。  
> 研发主仓 `E:\easyvtuberstudio-develop` 代码可能领先；稳定后 `scripts\maint\sync_develop_to_fork.ps1` 合并到 fork 再 push。

---

## 入门与仓库

| 文档 | 说明 |
|------|------|
| [DEPLOY.md](DEPLOY.md) | **首次部署**：GitHub ZIP → DEPLOY 四档 → 第一次正常启动 |
| [ADDONS_LAYOUT.md](ADDONS_LAYOUT.md) | 可选包目录、junction、`addons/` 与 DEPLOY 档位 |
| [PREP_PUSH.md](PREP_PUSH.md) | **维护者**：fork push 前检查清单 |
| [../README.md](../README.md) | GitHub 首页总览、功能摘要、启动方式 |
| [README-EN.md](README-EN.md) | 英文启动与仓库说明 |
| [README-detail.md](README-detail.md) | 详细说明、备份与同步 |
| [READMEfrom-main.md](READMEfrom-main.md) | 上游 THA4 demo 原 README |
| [FORK_ROOT.md](FORK_ROOT.md) | Git 远程、fork / develop 分工、同步命令 |
| [HANDOVER.md](HANDOVER.md) | **Agent / 维护者主入口** |
| [../plans/README.md](../plans/README.md) | 计划文档目录 |
| [../plans/REPO_LAYOUT.plan.md](../plans/REPO_LAYOUT.plan.md) | 根目录整理与路径对照 |

---

## 排障、硬件与发布

| 文档 | 说明 |
|------|------|
| [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) | **最全**排障 Q&A |
| [HARDWARE_REQUIREMENTS.md](HARDWARE_REQUIREMENTS.md) | 显卡/内存/多软件同开建议 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更摘要 |
| [BACKUP.md](BACKUP.md) | `his/` 归档与 fork 备份流程 |

---

## 计划与对接

| 文档 | 说明 |
|------|------|
| [../plans/layer-runtime-replan_3a393fc1.plan.md](../plans/layer-runtime-replan_3a393fc1.plan.md) | 多图层 L0–L3 计划 |
| [../plans/EXTERNAL_LAYER_INTERFACE.md](../plans/EXTERNAL_LAYER_INTERFACE.md) | 外挂 bridge 已废弃说明 |
| [../plans/PORTABLE_RELEASE.plan.md](../plans/PORTABLE_RELEASE.plan.md) | 便携发行（EasyVtuberStudio.exe） |
| [../plans/AGENT_ONBOARDING.md](../plans/AGENT_ONBOARDING.md) | 快捷索引 |

---

## 实验脚本与 THA3

| 文档 | 说明 |
|------|------|
| [../face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/README.txt](../face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/README.txt) | EasyVtuberStudio 面捕模块功能条目 |
| [../face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/THA3_INTEGRATION.md](../face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/THA3_INTEGRATION.md) | THA3 / THA4 双图像源 |
| [../deps/README.md](../deps/README.md) | `deps/pip`、`deps/tha3` |
| [../deps/pip/README.md](../deps/pip/README.md) | pip 清单与安装脚本 |
| [../deps/tha3/README.md](../deps/tha3/README.md) | THA3 资产填充 |

---

## 摄像头与历史训练

| 文档 | 说明 |
|------|------|
| [camfix/CAMERA_CHANGES_SUMMARY.md](camfix/CAMERA_CHANGES_SUMMARY.md) | 摄像头 / DroidCam 改动摘要 |
| [training/README_BAI_CUSTOM.txt](training/README_BAI_CUSTOM.txt) | body 续训历史流程（只读参考） |
| [../tools/training/README_PORTABLE.txt](../tools/training/README_PORTABLE.txt) | 便携训练入口 |

---

## 上游 demo 模块说明（THA4 原版）

| 文档 | 说明 |
|------|------|
| [character_model_mediapipe_puppeteer.md](character_model_mediapipe_puppeteer.md) | 官方面捕 puppeteer |
| [character_model_manual_poser.md](character_model_manual_poser.md) | 手动 poser |
| [character_model_ifacialmocap_puppeteer.md](character_model_ifacialmocap_puppeteer.md) | iFacialMocap |
| [distill.md](distill.md) · [distiller_ui.md](distiller_ui.md) | 蒸馏与 UI |
| [full_manual_poser.md](full_manual_poser.md) | Full manual poser |

---

## 快捷跳转（定制客户 / 运维）

```text
首次部署：docs\DEPLOY.md
可选包布局：docs\ADDONS_LAYOUT.md
维护者推送：docs\PREP_PUSH.md
面捕启动：双击仓库根 EasyVtuberStudio.exe
开发回退：scripts\launch\run_load_preview_puppeteer.bat
卸载可选包：RESET_ADDON.bat
排障：docs\TROUBLESHOOTING_QA.md
安装日志：workspace\deploy.log · workspace\launch.log
依赖：deps\pip\ 或 DEPLOY.bat
UI 状态：workspace\load_preview_ui_state.json
```
