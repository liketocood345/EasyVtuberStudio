# 文档总索引（权威副本在 fork 根目录）

> **本仓库 `E:\tha4fork` 为对外发布总库，Markdown 说明以本目录树为准。**  
> 研发主仓 `E:\tha4fork-develop` 代码可能领先；文档稳定后应合并回本 fork 再 push。  
> ~~`E:\THA4_bundle_bai_custom`~~ 已废弃。

---

## 入门与仓库

| 文档 | 说明 |
|------|------|
| [../DEPLOY.md](../DEPLOY.md) | **首次部署**：GitHub ZIP → 第一次正常启动 |
| [../README.md](../README.md) | GitHub 首页总览、功能摘要、启动方式 |
| [../README-EN.md](../README-EN.md) | 英文启动与仓库说明 |
| [../README-detail.md](../README-detail.md) | 详细说明、备份与同步（部分历史路径见脚注） |
| [../READMEfrom-main.md](../READMEfrom-main.md) | 上游 THA4 demo 原 README |
| [../FORK_ROOT.md](../FORK_ROOT.md) | Git 远程、fork / develop 分工、常用命令 |
| [../HANDOVER.md](../HANDOVER.md) | **Agent / 维护者主入口**：路径、进度、验收 |
| [../plans/README.md](../plans/README.md) | 计划文档目录 |

---

## 排障、硬件与发布

| 文档 | 说明 |
|------|------|
| [../TROUBLESHOOTING_QA.md](../TROUBLESHOOTING_QA.md) | **最全**排障 Q&A（含窗口捕获、持久化、定制部署预期） |
| [../HARDWARE_REQUIREMENTS.md](../HARDWARE_REQUIREMENTS.md) | 显卡/内存/多软件同开建议 |
| [../CHANGELOG.md](../CHANGELOG.md) | 版本变更摘要 |
| [../BACKUP.md](../BACKUP.md) | `his/` 归档与 fork 备份流程 |

---

## 计划与外挂对接

| 文档 | 说明 |
|------|------|
| [../plans/layer-runtime-replan_3a393fc1.plan.md](../plans/layer-runtime-replan_3a393fc1.plan.md) | 多图层 L0–L3 计划 |
| [../plans/EXTERNAL_LAYER_INTERFACE.md](../plans/EXTERNAL_LAYER_INTERFACE.md) | `contract.json` / `status.json` |
| [../plans/AGENT_ONBOARDING.md](../plans/AGENT_ONBOARDING.md) | 快捷索引（详见面 HANDOVER §0） |

---

## 实验脚本与 THA3

| 文档 | 说明 |
|------|------|
| [../face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/README.txt](../face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/README.txt) | Load Preview 功能条目（细） |
| [../face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/THA3_INTEGRATION.md](../face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/THA3_INTEGRATION.md) | THA3 / THA4 双图像源、`deps/tha3` |
| [../deps/README.md](../deps/README.md) | 仓库内 `deps/pip`、`deps/tha3` |
| [../deps/pip/README.md](../deps/pip/README.md) | pip 清单与安装脚本 |
| [../deps/tha3/README.md](../deps/tha3/README.md) | THA3 资产填充 |

---

## 摄像头与历史训练

| 文档 | 说明 |
|------|------|
| [camfix/CAMERA_CHANGES_SUMMARY.md](camfix/CAMERA_CHANGES_SUMMARY.md) | 摄像头 / DroidCam 改动摘要 |
| [training/README_BAI_CUSTOM.txt](training/README_BAI_CUSTOM.txt) | body 续训历史流程（只读参考） |

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
首次部署：DEPLOY.md（GitHub ZIP → 第一次启动）
启动：E:\tha4fork\》》》》start《《《《.bat
排障：TROUBLESHOOTING_QA.md 置顶 + 第九节
依赖：deps\pip\install_all_image_source_deps.bat
THA3 资产：deps\tha3\populate_tha3_bundle.ps1
状态文件：face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/load_preview_ui_state.json
```
