# Git 与本地路径说明（发布总库 `E:\tha4fork`）

本文件位于 **fork 发布总库** 根目录。日常开发在 **`E:\tha4fork-develop`**，稳定后合并到本目录再 push。

## 远程

| 远程名 | 地址 | 用途 |
|--------|------|------|
| **origin** | https://github.com/liketocood345/EasyVtuber-with-THA3-THA4 | 本 fork（默认 push/pull） |
| **upstream** | https://github.com/pkhungurn/talking-head-anime-4-demo | 官方上游（`git fetch upstream`） |

## 本地目录

| 路径 | 角色 |
|------|------|
| **`E:\tha4fork`** | **对外发布总库**（本仓库；定制客户部署、GitHub 首页文档） |
| **`E:\tha4fork-develop`** | 研发主仓（功能先行，合并到 fork 后发布） |
| ~~`E:\THA4_bundle_bai_custom`~~ | 已废弃 |

文档权威副本：**本目录**下 [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md)、[HANDOVER.md](HANDOVER.md) 等；完整索引见 [docs/DOC_INDEX.md](docs/DOC_INDEX.md)。

## 常用命令（发布总库）

```bat
cd /d E:\tha4fork
git pull origin main
git add -A
git commit -m "your message"
git push origin main
```

同步上游（可选）：

```bat
git fetch upstream
git merge upstream/main
```

## 启动（定制部署）

```bat
cd /d E:\tha4fork
》》》》start《《《《.bat
```

等价于 `run_load_preview_puppeteer.bat`（自动解析 `face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo` 与 `venv`）。

## 已知问题与策略（2026-05-29）

### DroidCam / 虚拟摄像头

- 虚拟摄像头项（「DroidCam Video」）常出现占位画面、黑帧、比例异常；**不再**为异常虚拟流做兼容补丁。
- **推荐**：视频源使用 **窗口捕获**，抓取 DroidCam **电脑端预览窗**（见 [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) 第二节）。
- 彻底退出 DroidCam 用户态进程：可选 `E:\doridcam-oprate\Stop-DroidCam.bat`（用户脚本，非本仓库必需）。

### 持久化路径

- `load_preview_ui_state.json` 中模型/立绘路径无效时，重启**不会**自动修复；见 [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) 第九节。
