# THA4 Fork 总库（本地根目录）

本目录 `E:\tha4fork` 为 **fork 总库** 的本地 Git 工作副本，对应远程：

| 远程名 | 地址 | 用途 |
|--------|------|------|
| **origin** | https://github.com/liketocood345/talking-head-anime-4-demo | 你的 fork（默认 push/pull） |
| **upstream** | https://github.com/pkhungurn/talking-head-anime-4-demo | 原作者官方仓库（同步上游用） |

## 与原仓库的关系

- **上游（官方）**：https://github.com/pkhungurn/talking-head-anime-4-demo  
- **本 fork**：https://github.com/liketocood345/talking-head-anime-4-demo  

## 常用命令

```bat
cd /d E:\tha4fork

REM 从 fork 拉取
git pull origin main

REM 获取上游更新（不自动合并）
git fetch upstream
git merge upstream/main

REM 推送到 fork
git push origin main
```

## 与本地定制工程的关系

| 路径 | 角色 |
|------|------|
| `E:\tha4fork` | fork 总库（Git 源码、提交、与 GitHub 同步） |
| `E:\THA4_bundle_bai_custom` | 当前 bai 定制运行/实验目录（含 `experiments\puppeteer_load_preview` 等） |

将 `THA4_bundle_bai_custom` 中的 THA4 源码改动合并进总库时，应对齐本仓库根目录下的 `talking-head-anime-4-demo` 结构（若总库根即 demo 根，则直接对应当前 clone 内容）。
