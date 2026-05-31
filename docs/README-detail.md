# EasyVtuberStudio — 详细说明

> **文档位于 `docs/`；fork 根目录仅 `README.md` + `EasyVtuberStudio.exe` + 文件夹。**  
> 日常代码开发在 **`E:\tha4fork-develop`**，稳定后 `scripts\maint\sync_develop_to_fork.ps1` 合并到 fork。  
> 完整索引：[DOC_INDEX.md](DOC_INDEX.md)

> **从 GitHub ZIP 首次部署请读 [DEPLOY.md](DEPLOY.md)。**

## Layout

```
E:\tha4fork/
├── README.md
├── EasyVtuberStudio.exe
├── docs/                        ← 全部 Markdown（本文件在此）
├── scripts/launch/              ← bat 与 THA4Train.exe
├── packaging/
├── workspace/
├── plans/
├── deps/
└── face-puppeteer-ui-enhancements-ai-code/
```

## 启动

**发布 / 定制环境（fork）：**

```bat
cd /d E:\tha4fork
EasyVtuberStudio.exe
```

**研发（develop）：**

```bat
cd /d E:\tha4fork-develop
scripts\launch\run_load_preview_puppeteer.bat
```

## 更新与备份规则

需要留档时：在 **`face-puppeteer-ui-enhancements-ai-code\`** 运行 `archive_to_his.ps1`。

| 项 | 约定 |
|----|------|
| develop → fork | `scripts\maint\sync_develop_to_fork.ps1` |

（下文功能说明与历史段落保留，路径以 `docs/HANDOVER.md` 为准。）
