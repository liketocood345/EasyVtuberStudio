# Git 与本地路径说明（发布总库 `E:\tha4fork`）

本文件位于 **fork 发布总库** `docs/`。日常开发在 **`E:\tha4fork-develop`**，稳定后运行 `scripts/maint/sync_develop_to_fork.ps1` 再 push。

## 远程

| 远程名 | 地址 | 用途 |
|--------|------|------|
| **origin** | https://github.com/liketocood345/EasyVtuberStudio | EasyVtuberStudio 发布仓库（默认 push/pull） |
| **upstream** | https://github.com/pkhungurn/talking-head-anime-4-demo | 官方上游（`git fetch upstream`） |

## 仓库更名（2026-05-31）

| 项 | 值 |
|----|-----|
| **现用 GitHub 名** | **`EasyVtuberStudio`** |
| **曾用名** | `EasyVtuber-with-THA3-THA4` |
| **主页** | https://github.com/liketocood345/EasyVtuberStudio |

本地目录 **`E:\tha4fork`** / **`E:\tha4fork-develop`** 名称不变；仅远程仓库 slug 变更。若 clone 过旧地址，执行：

```bat
git remote set-url origin https://github.com/liketocood345/EasyVtuberStudio.git
```

## 本地目录

| 路径 | 角色 |
|------|------|
| **`E:\tha4fork`** | **对外发布总库**（根目录仅 `README.md` + `EasyVtuberStudio.exe` + 文件夹） |
| **`E:\tha4fork-develop`** | 研发主仓（功能先行，同步到 fork 后发布） |

文档索引：[DOC_INDEX.md](DOC_INDEX.md)

## 常用命令（发布总库）

```bat
cd /d E:\tha4fork
git pull origin main
git add -A
git commit -m "your message"
git push origin main
```

## develop → fork 同步

```powershell
cd E:\tha4fork-develop
powershell -ExecutionPolicy Bypass -File scripts\maint\sync_develop_to_fork.ps1
```

同步范围含 **`data/`**、**`packaging/`**、**`docs/`**。推送前见 [PREP_PUSH.md](PREP_PUSH.md)。

## 启动（定制部署）

**用户：** 双击仓库根目录 **`EasyVtuberStudio.exe`**

**开发回退：**

```bat
scripts\launch\run_load_preview_puppeteer.bat
```

或 `scripts\launch\run_load_preview_puppeteer.bat`（优先启动根目录 exe）。

## 已知问题与策略（2026-05-29）

### DroidCam / 虚拟摄像头

- 虚拟摄像头项常异常；**推荐窗口捕获**（见 [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) 第二节）。

### 持久化路径

- UI 状态默认在 `workspace/load_preview_ui_state.json`；无效模型路径需重新 Load Other。
