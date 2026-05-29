# 首次部署指南（GitHub 压缩包 → 第一次正常启动）

本文面向 **从 GitHub 下载 ZIP、解压后尚未配置环境** 的用户，说明从零到 **Load Preview 面捕程序首次正常启动** 的完整步骤。

**仓库地址：** https://github.com/liketocood345/EasyVtuber-with-THA3-THA4  

**相关文档：** [HARDWARE_REQUIREMENTS.md](HARDWARE_REQUIREMENTS.md) · [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) · [HANDOVER.md](HANDOVER.md)

---

## 置顶：最简单的安装方法（推荐新手）

若你不熟悉命令行、Poetry 或 bat 脚本，**最省事的做法是让 AI 编程助手在本机代你执行 `DEPLOY.md` 里的步骤**。下面两种方式任选其一（而且外行也能一句话解决小bug）。

---

### 方式一：OpenAI Codex（CLI 或桌面 App）（codex更聪明，意味着对你的更外行的表述更兼容）

[Codex](https://developers.openai.com/codex/cli) 是 OpenAI 的 **终端 / 桌面编程 Agent**：在你指定的项目目录里读文件、改文件、运行命令（需你确认）。**Windows 可在 PowerShell 原生运行**（也可用 WSL2，见 [Windows 指南](https://developers.openai.com/codex/windows)）。

#### 1. 安装

**CLI（推荐，与部署文档最契合）：**

1. 安装 **Node.js 22+**（若尚未安装）：https://nodejs.org/  
2. 在 **PowerShell** 中任选一种官方安装方式：

```powershell
# 方式 A：官方 Windows 安装脚本（Quickstart 推荐）
powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"

# 方式 B：npm 全局安装
npm install -g @openai/codex
codex --version
```

**桌面 App（可选，图形界面）：**  
Microsoft Store 搜索 **Codex**，或：

```powershell
winget install Codex -s msstore
```

详见 [Codex app（Windows）](https://developers.openai.com/codex/app/windows)。

#### 2. 登录与费用（以官网为准，2026-05）

- 首次运行 `codex` 或打开 App 时，用 **ChatGPT 账号** 或 **OpenAI API Key** 登录（见 [Quickstart](https://developers.openai.com/codex/quickstart)）。  
- **ChatGPT Plus / Pro / Business / Edu / Enterprise** 套餐 **包含 Codex 使用权益**（见 [CLI 概述](https://developers.openai.com/codex/cli)）；**不是**像 Cursor Hobby 那样的独立免费 IDE 档。无付费套餐时需自备 API Key 并按量计费。  
- Agent 执行命令前通常要你 **批准**（approval modes / sandbox）；部署时请选择允许运行 `python`、`pip`、`poetry` 等待遇，详见 [Agent approvals & security](https://developers.openai.com/codex/agent-approvals-security)。

#### 3. 在本项目中部署

1. 按 [§2](#2-下载并解压项目) 下载 ZIP 并解压到例如 `D:\EasyVtuber-THA4\`（下文 **`<REPO>`**）。  
2. **CLI：** 在 PowerShell 中：

```powershell
cd <REPO>
codex
```

**App：** 打开 Codex → Add project → 选中 **`<REPO>`**（能看到 `DEPLOY.md` 的仓库根目录）。

3. 复制下面整段发给 Codex（路径改成你的）：

```text
请按仓库根目录 DEPLOY.md 的完整流程，帮我在本机部署并验收这个项目。
仓库根目录：<REPO>（例如 D:\EasyVtuber-THA4\EasyVtuber-with-THA3-THA4-main）
目标：创建 venv、安装 poetry/pip 依赖、提示我下载 THA4 data 包（若缺失）、
最后运行 》》》》start《《《《.bat 或 run_load_preview_puppeteer.bat 并确认能弹出完整调参窗。
遇到报错请根据 TROUBLESHOOTING_QA.md 排查并继续，直到首次正常启动。
```

4. 对 Agent 提出的 **终端命令、文件修改** 逐项确认；报错把 **完整终端输出** 贴回对话继续排查。

---

### 方式二：Cursor（IDE + Agent）

[Cursor](https://cursor.com/) 是带 Agent 的代码编辑器；**本项目也使用 Cursor 编写**，适合部署后继续改小 bug 或提小功能。

1. **安装 Cursor**  
   - 打开 https://cursor.com/ 下载 **Windows 版**并安装。  
   - **费用（以官网为准，2026-05）：**  
     - 注册后可使用免费的 **Hobby** 方案（[定价页](https://cursor.com/pricing) 写明 **无需信用卡**）。  
     - Hobby 含 **Agent、Chat、Tab 补全**，但 **用量有限**，Agent 默认走 **Auto** 模型（见 [官方说明](https://cursor.com/help/account-and-billing/pricing)）。  
     - **已无 Pro 免费试用**（Cursor 官方在 2026 年初取消了原先的 7 天 Pro trial；见 [社区说明](https://forum.cursor.com/t/was-the-7-day-free-trial-removed/148780)）。部署本项目 **通常可在 Hobby 免费额度内完成**；若 Agent 提示用量用尽，可改用下方手动步骤，或订阅 Pro（$20/月）。  
     - **在校大学生** 验证学籍后可能获得 **1 年 Pro**（见 [cursor.com/students](https://cursor.com/students)）。

2. **把本项目放进 Cursor**  
   - 按 [§2](#2-下载并解压项目) 解压 ZIP。  
   - Cursor → **File → Open Folder** → 选 **`<REPO>`** 根目录。

3. **让 Cursor 部署**  
   - 打开 **Agent** 模式（需在本机运行命令）。  
   - 发送与上方 **Codex 相同的提示词**（改 `<REPO>` 路径）。

---

### 共同说明（Codex / Cursor 均适用）

**你需要配合的事（Agent 无法代替）：**

- 本机须满足 [§1 硬件条件](#1-硬件与系统前置条件)（**Windows + NVIDIA 显卡**）。  
- **THA4 官方模型 ZIP**（含 MediaPipe `.task`）常需从 Dropbox **手动下载**解压（见 [§5](#5-下载-tha4-官方-data-包)）。  
- 若用 **THA3 立绘**，还需 EasyVtuber 资产或维护者提供的 ONNX（见 [§6](#6-可选tha3-立绘模式)）。  
- pip / Poetry、UAC、防火墙提示需按 Agent 说明允许。

**验收：** 与 [§0 验收标准](#0-你会得到什么验收标准) 相同——完整调参窗不闪退 → Load Other 加载 `character_model.yaml` → 默认姿态预览。

> **说明：** 两者都是 **在你电脑上** 读文档、跑命令，不是云端替你装好面捕环境。Codex 偏 **终端 / 沙箱命令**；Cursor 偏 **IDE 一体化**。免费额度或用量触顶时，改走下方 [§0 起的手动部署](#0-你会得到什么验收标准) 即可。

---

## 0. 你会得到什么（验收标准）

完成本文后，应达到：

1. 双击 **`》》》》start《《《《.bat`** 能弹出 **完整调参窗**（含模型加载、视频源、后处理等控件），并通常伴随 **独立输出窗**；进程不闪退。
2. 在完整调参窗中能通过 **「加载其他 THA4 Student / Load Other THA4 Student」** 选中 `character_model.yaml` 并成功加载角色。
3. 加载后出现 **默认中性姿态预览**（不必先对着摄像头）。
4. （可选）连接 USB 摄像头或 **窗口捕获** 后，面捕能驱动角色。

若某一步失败，先跳到 [§9 常见卡点](#9-常见卡点)，或查 [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md)。

---

## 1. 硬件与系统前置条件

| 项 | 要求 |
|----|------|
| 系统 | **Windows 10 / 11 64 位** |
| GPU | **NVIDIA 独显**，建议 **6 GB+ 显存**（程序默认 `cuda:0`） |
| 驱动 | 已安装支持 CUDA 的较新 NVIDIA 驱动 |
| CPU / 内存 | 建议 **6 核 12 线程+**、**16 GB RAM**（见 [HARDWARE_REQUIREMENTS.md](HARDWARE_REQUIREMENTS.md)） |
| 磁盘 | **SSD**，预留 **≥15 GB**（venv、THA4 模型包、可选 THA3 ONNX） |
| 摄像头 | USB 摄像头，或 DroidCam 等（**推荐用窗口捕获抓预览窗**，见排障文档第二节） |

> **说明：** 无 NVIDIA 显卡时通常无法实时面捕；改 CPU 模式不在本部署指南范围内。

---

## 2. 下载并解压项目

### 2.1 下载 ZIP

1. 打开 https://github.com/liketocood345/EasyVtuber-with-THA3-THA4  
2. 点击 **Code → Download ZIP**  
3. 将 ZIP 解压到 **路径尽量短、无中文空格问题** 的目录，例如：  
   `D:\EasyVtuber-THA4\`

解压后根目录应包含（至少）：

```text
EasyVtuber-with-THA3-THA4-main\    ← ZIP 默认文件夹名，可改名为 EasyVtuber-THA4
├── 》》》》start《《《《.bat
├── run_load_preview_puppeteer.bat
├── deps\
├── poetry\
├── face-puppeteer-ui-enhancements-ai-code\
└── README.md
```

下文用 **`<REPO>`** 表示该根目录的完整路径，例如 `D:\EasyVtuber-THA4\EasyVtuber-with-THA3-THA4-main`。

### 2.2 ZIP 里**没有**、需要后续自行准备的内容

GitHub 压缩包 **不包含** 以下内容（`.gitignore` 或未入库）：

| 缺失项 | 用途 | 本文步骤 |
|--------|------|----------|
| `venv/` | Python 虚拟环境 | [§4](#4-创建-venv-并安装-python-依赖) |
| `.../talking-head-anime-4-demo/data/` 内大文件 | THA4 预训练权重、MediaPipe `.task` | [§5](#5-下载-tha4-官方-data-包) |
| `deps/tha3/models/**/*.onnx` | THA3 立绘推理（约 2.5 GB） | [§6](#6-可选tha3-立绘模式)（仅 THA3 需要） |
| 定制 Student 角色包 | 你的 `character_model.yaml` + `.pt` | [§7](#7-准备-tha4-student-角色模型) |

---

## 3. 安装 Python 3.10 与 Poetry

### 3.1 Python 3.10.11

1. 安装 [Python 3.10.11](https://www.python.org/downloads/release/python-31011/)（**64 位**）  
2. 安装时勾选 **「Add Python to PATH」**  
3. 打开 **cmd**，确认版本：

```bat
py -3.10 --version
```

应显示 `Python 3.10.x`。若无 `py` 启动器，可使用完整路径，例如：  
`C:\Users\你的用户名\AppData\Local\Programs\Python\Python310\python.exe`

### 3.2 Poetry（推荐）

1. 安装 [Poetry 1.7+](https://python-poetry.org/docs/#installation)  
2. 确认可用：

```bat
poetry --version
```

Poetry 用于安装 **PyTorch (CUDA 11.7)**、wxPython、MediaPipe 等核心依赖（见仓库根 `poetry/pyproject.toml`）。

---

## 4. 创建 venv 并安装 Python 依赖

以下命令均在 **cmd** 中执行。将 `<REPO>` 换成你的实际路径。

### 4.1 创建虚拟环境

推荐位置（与启动脚本、`deps/pip` 安装脚本一致）：

```bat
cd /d <REPO>\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo
py -3.10 -m venv venv --prompt talking-head-anime-4-demo
```

### 4.2 激活 venv 并用 Poetry 安装核心库

```bat
venv\Scripts\activate.bat
cd /d <REPO>\poetry
poetry config virtualenvs.create false
poetry install
```

说明：

- 必须先 **activate** 再 `poetry install`，依赖会装进当前 `venv`。  
- 首次安装会下载 **torch 1.13.1+cu117**，体积较大，请保持网络畅通。  
- 若 Poetry 报 Python 版本不符，请确认使用的是 **3.10.x**。

### 4.3 安装 Load Preview 额外 pip 依赖（THA4 Student + THA3 ORT）

仍在 **已激活 venv** 的前提下：

```bat
cd /d <REPO>\deps\pip
install_all_image_source_deps.bat
```

该脚本会依次安装 `requirements-tha4-student.txt` 与 `requirements-tha3-ort.txt`（含 MediaPipe 版本钉扎、ONNX Runtime DirectML 等）。

### 4.4 推荐补充包（摄像头列表 / 音频嘴型）

```bat
venv\Scripts\pip.exe install sounddevice pygrabber
```

| 包 | 作用 |
|----|------|
| `sounddevice` | 音频驱动嘴型、WASAPI 内录 |
| `pygrabber` | DirectShow 摄像头 **名称** 列表（无则仍可用 OpenCV 枚举，体验略差） |

> 路径提示：若已离开 demo 目录，可将上式中的 `venv\Scripts\pip.exe` 换为  
> `<REPO>\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\venv\Scripts\pip.exe`

### 4.5 自检 venv

```bat
<REPO>\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\venv\Scripts\python.exe -c "import torch; import wx; import mediapipe; print('cuda:', torch.cuda.is_available())"
```

期望：`cuda: True`（有 NVIDIA 显卡且驱动正常时）。

---

## 5. 下载 THA4 官方 data 包

程序启动时工作目录为 **`talking-head-anime-4-demo`**，MediaPipe 模型路径为：

```text
data/thirdparty/mediapipe/face_landmarker_v2_with_blendshapes.task
```

THA4 推理还需要 `data/tha4/` 下的 `face_morpher.pt`、`body_morpher.pt` 等。

### 5.1 下载

从 THA4 上游说明中的 Dropbox 链接下载 **tha4-models.zip**（链接见 [READMEfrom-main.md](READMEfrom-main.md)「Download the Models/Dataset Files → THA4 Models」一节，或上游仓库 https://github.com/pkhungurn/talking-head-anime-4-demo ）。

### 5.2 解压目标

解压到：

```text
<REPO>\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\
```

解压完成后，至少应存在：

```text
talking-head-anime-4-demo\data\
├── tha4\
│   ├── face_morpher.pt
│   ├── body_morpher.pt
│   └── …
├── thirdparty\
│   └── mediapipe\
│       └── face_landmarker_v2_with_blendshapes.task
├── images\
└── character_models\          ← 官方示例 student，可用于首次试跑
```

> **注意：** 代码使用的是 **`thirdparty`**（全小写、无下划线）。若 ZIP 内文件夹名为 `third_party`，请重命名为 `thirdparty`。

### 5.3 验证文件

```bat
dir <REPO>\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\thirdparty\mediapipe\*.task
dir <REPO>\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\tha4\face_morpher.pt
```

两个路径均应有文件。

---

## 6. （可选）THA3 立绘模式

**仅当你要在 UI 里切换到 THA3 立绘图像源时需要。** 若只用 THA4 Student，可跳过本节。

1. 本机已安装 **EasyVtuber**（用于一次性复制资产），或已有 ONNX 包  
2. 在 **仓库根** `<REPO>` 执行：

```powershell
powershell -ExecutionPolicy Bypass -File deps\tha3\populate_tha3_bundle.ps1 -SourceRoot "D:\path\to\EasyVtuber_v0.8.1\EasyVtuber_v0.8.1"
```

3. 确认存在：`deps\tha3\models\tha3\*.onnx`（体积大，默认不在 Git 中）  
4. 详见 [face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/THA3_INTEGRATION.md](face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/THA3_INTEGRATION.md)

---

## 7. 准备 THA4 Student 角色模型

Load Preview 需要一份 **Student 模型包**，至少包含：

- `character_model.yaml`  
- 对应的 `face_morpher.pt` / `body_morpher.pt`（或 yaml 内指定的路径）  
- 角色立绘纹理图  

### 7.1 首次试跑（使用官方示例）

若 [§5](#5-下载-tha4-官方-data-包) 解压包中含有 `data/character_models/`，可在 UI 中 **Load Other** 指向其中的某个 `character_model.yaml` 做首次验证。

### 7.2 使用定制 / 交付的角色包

若维护者单独提供了 `packaged/你的角色/` 等目录：

1. 将整个文件夹放到任意 **不会移动** 的路径（建议放在 `<REPO>` 内，便于备份）  
2. 首次启动后：在 **完整调参窗** 中 **Load Other THA4 Student → 选择该 `character_model.yaml`**  
3. **「Load Last」** 仅在成功加载过一次后才有意义（路径写入 `load_preview_ui_state.json`）

> GitHub ZIP **不一定包含** README 中提到的 `packaged/bai_450k/` 示例包；以维护者交付或 Release 附件为准。

---

## 8. 第一次启动与基本操作

### 8.1 启动

```bat
cd /d <REPO>
》》》》start《《《《.bat
```

等价于 `run_load_preview_puppeteer.bat`：自动定位  
`face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\venv` 与主脚本。

### 8.2 首次使用流程（建议顺序）

1. 启动后应 **直接出现完整调参窗**（若只见精简小窗，点 **「切换到完整调参窗 / Open Full Controls」**，或见 [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) Q17）  
2. **图像源**：默认 THA4 Student；加载 THA3 立绘前请先完成 [§6](#6-可选tha3-立绘模式)  
3. **加载模型**：点 **「加载其他 THA4 Student / Load Other THA4 Student」**，选中 [§7](#7-准备-tha4-student-角色模型) 中的 `character_model.yaml`（**Load Last** 仅在曾成功加载过且路径仍有效时可用）  
4. 确认 **输出窗** 出现默认姿态（无人脸时也可能保持默认 pose）  
5. **视频输入**（加载模型后会 **自动刷新设备列表并尝试连接**；记忆的 **窗口捕获** 优先于摄像头）：  
   - 普通 USB 摄像头：若未自动连上，点「刷新设备列表」→ 选择设备  
   - DroidCam：**优先「窗口捕获 / Pick Window Capture」** 选 PC 端预览窗（见 [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) 置顶与第二节）  
6. **标定**：按培训说明使用「标定中性位 / 标定朝向」；勿反复狂点（见排障第九节）

> **说明：** 程序 **启动时不会** 自动打开摄像头；视频源自动连接在 **Load Other / Load Last 加载模型** 等操作后触发。精简小窗（3 个快捷按钮：朝向校准、输出动态增强校准、打开完整窗）可通过完整窗内 **「切换到精简小窗 / Switch to Compact」** 进入。

### 8.3 启动失败时

- 黑窗一闪而过：在 cmd 中手动运行 `run_load_preview_puppeteer.bat` 查看报错  
- 常见原因：`venv` 未创建、[§5](#5-下载-tha4-官方-data-包) 缺 `.task` 或 `.pt`、`cuda:0` 不可用  

---

## 9. 常见卡点

| 现象 | 原因 | 处理 |
|------|------|------|
| `ERROR: cannot find venv` | 未执行 [§4](#4-创建-venv-并安装-python-依赖) | 创建 demo 下 `venv` 并安装依赖 |
| `cannot find load preview script` | 解压不完整或路径不对 | 确认 `<REPO>` 下有 `face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\` |
| MediaPipe / `.task` 报错 | 缺 [§5](#5-下载-tha4-官方-data-包) | 检查 `data\thirdparty\mediapipe\*.task` |
| `cuda:0` / CUDA 错误 | 无 NVIDIA 或驱动/PyTorch 不匹配 | 更新驱动；确认 `poetry install` 装的是 cu117 版 torch |
| 能开 UI 但 Load Last 无效 | 首次本无记忆 | 用 **Load Other** 选手动 yaml |
| 选 DroidCam 虚拟摄像头异常 | 已知兼容问题 | 改用 **窗口捕获**（排障置顶） |
| `install_all_image_source_deps.bat` 失败 | venv 路径不对 | 先完成 [§4.1](#41-创建虚拟环境)，且 venv 在 demo 目录下 |

更多问答见 **[TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md)**。

---

## 10. 部署完成速查清单

复制后逐项打勾：

```text
[ ] ZIP 已解压到 <REPO>，能看到 》》》》start《《《《.bat
[ ] Python 3.10 + Poetry 已安装
[ ] <REPO>\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\venv 已创建
[ ] poetry install 成功；install_all_image_source_deps.bat 成功
[ ] （推荐）sounddevice、pygrabber 已 pip 安装
[ ] data\tha4\*.pt 与 data\thirdparty\mediapipe\*.task 已就位
[ ] （若用 THA3）deps\tha3\models 已 populate
[ ] 已准备 character_model.yaml 角色包
[ ] 》》》》start《《《《.bat 弹出完整调参窗（及输出窗）且不闪退
[ ] Load Other 加载模型成功，有默认姿态预览
[ ] （可选）摄像头或窗口捕获面捕正常
```

---

## 11. 后续维护

| 需求 | 文档 |
|------|------|
| 日常排障 | [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) |
| 硬件与多软件同开 | [HARDWARE_REQUIREMENTS.md](HARDWARE_REQUIREMENTS.md) |
| Agent / 二次开发 | [HANDOVER.md](HANDOVER.md) |
| 全部 Markdown 索引 | [docs/DOC_INDEX.md](docs/DOC_INDEX.md) |

---

*文档版本：2026-05-29 · 适用于 fork 发布总库 `EasyVtuber-with-THA3-THA4` 从 GitHub ZIP 首次部署。*
