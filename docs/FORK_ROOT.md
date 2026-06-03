# Git 与本地路径说明（发布总库 `E:\easyvtuberstudio-main`）

本文件位于 **main 发布总库** `docs/`。日常开发在 **`E:\easyvtuberstudio-develop`**，稳定后运行 `scripts/maint/sync_develop_to_fork.ps1` 再 push。

## 远程（GitHub）

| 远程名 | 仓库 | 用途 |
|--------|------|------|
| **origin** | https://github.com/liketocood345/EasyVtuberStudio | **唯一**发布仓库（默认 push/pull） |
| **upstream** | https://github.com/pkhungurn/talking-head-anime-4-demo | 官方上游（`git fetch upstream`） |

**说明：** `E:\easyvtuberstudio-develop` 为本地研发目录，**无独立 GitHub 仓库**；变更经 `sync_develop_to_fork.ps1` 合并到 `E:\easyvtuberstudio-main` 后 push 到 **EasyVtuberStudio**。

### 曾用名

| 项 | 值 |
|----|-----|
| GitHub 曾用 slug | `EasyVtuber-with-THA3-THA4` |
| 本地目录曾用名 | `E:\tha4fork` / `E:\tha4fork-develop` |
| 文档误写（非 GitHub 仓库） | `easyvtuberstudio-main` / `easyvtuberstudio-develop` 仅为**本地文件夹名** |

更新 origin：

```bat
cd /d E:\easyvtuberstudio-main
git remote set-url origin https://github.com/liketocood345/EasyVtuberStudio.git
```

## 本地目录

| 路径 | 角色 |
|------|------|
| **`E:\easyvtuberstudio-main`** | **对外发布总库**（含 `.git`；根目录 `README.md` + `EasyVtuberStudio.exe` + 文件夹） |
| **`E:\easyvtuberstudio-develop`** | **研发主仓**（三模块全装；改代码后 `sync_develop_to_fork.ps1` 合并到 main） |

文档索引：[DOC_INDEX.md](DOC_INDEX.md)

## 常用命令（发布总库）

```bat
cd /d E:\easyvtuberstudio-main
git pull origin main
git add -A
git commit -m "your message"
git push origin main
```

## develop → main 同步

```powershell
cd E:\easyvtuberstudio-develop
powershell -ExecutionPolicy Bypass -File scripts\maint\sync_develop_to_fork.ps1
```

同步范围含 **`data/`**、**`packaging/`**、**`docs/`**。推送前见 [PREP_PUSH.md](PREP_PUSH.md)。

## 启动（定制部署）

**用户：** 双击仓库根目录 **`EasyVtuberStudio.exe`**

**开发回退：**

```bat
scripts\launch\run_load_preview_puppeteer.bat
```

## 已知问题与策略（2026-05-29）

### DroidCam / 虚拟摄像头

- 虚拟摄像头项常异常；**推荐窗口捕获**（见 [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) 第二节）。

### 持久化路径

- UI 状态默认在 `workspace/load_preview_ui_state.json`；无效模型路径需重新 Load Other。
