[首次部署（GitHub ZIP 下载后） / First-time Deploy](docs/DEPLOY.md)

**便携版（推荐最终用户）：** GitHub Download ZIP（CORE）→ 解压 → **`DEPLOY.bat`**（四档 Y/N）或环境已就绪时直接 **`EasyVtuberStudio.exe`**。详见 [docs/DEPLOY.md](docs/DEPLOY.md)。

**本仓库 = GitHub 发布总库（CORE 刚解压态）**；本地全装研发在 `E:\tha4fork-develop`（三模块 `addons/*` 实体文件，不入本 ZIP）。见 [docs/HANDOVER.md](docs/HANDOVER.md) §0.1 · [docs/ADDONS_LAYOUT.md](docs/ADDONS_LAYOUT.md) · 推送前 [docs/PREP_PUSH.md](docs/PREP_PUSH.md)。

[English Guide for EasyVtuberStudio](docs/README-EN.md)

# EasyVtuberStudio

**EasyVtuberStudio** — 基于 THA3、THA4 的可面捕虚拟皮套演播软件，可添加附件（主入口 **`EasyVtuberStudio.exe`**）。

**新 Agent 请先读 [docs/HANDOVER.md](docs/HANDOVER.md)。**


> ### 【重要声明】
>
> 1. **使用前提**：下载或使用本软件前，请确认您具备基本的 Windows 操作与排障能力，并能在必要时借助翻译工具阅读安装过程中的**英文终端输出**（详见 [docs/DEPLOY.md](docs/DEPLOY.md)、[docs/TROUBLESHOOTING_QA.md](docs/TROUBLESHOOTING_QA.md)）。
> 2. **AI 生成代码风险**：本项目含大量 **AI 辅助编写**的代码。继续下载或使用，即表示您已理解并接受：代码可能存在未预见缺陷，**可能导致程序异常、数据丢失或在极端情况下加剧系统或硬件负载**；请在可接受风险的前提下自行决定是否使用。

**骚年，想玩虚拟皮套直播但没钱定制自己的角色？你的显卡该出场了！（虽然本项目能在无显卡电脑上跑出惊人的1fps）**


## 仓库与路径

| 项 | 说明 |
|----|------|
| **GitHub 仓库** | **[liketocood345/EasyVtuberStudio](https://github.com/liketocood345/EasyVtuberStudio)** |
| **本仓库（GitHub CORE）** | 当前解压目录；本地示例 `E:\tha4fork`（`addons/` 初始为空） |
| **研发主仓（非本仓库）** | `E:\tha4fork-develop` — **三模块全装**，日常改代码后 `scripts\maint\sync_develop_to_fork.ps1` |
| 曾用仓库名 | ~~`EasyVtuber-with-THA3-THA4`~~（2026-05 更名为 **EasyVtuberStudio**） |
| 定制代码包 | `face-puppeteer-ui-enhancements-ai-code/` |
| **新 Agent 入口** | **[docs/HANDOVER.md](docs/HANDOVER.md)** |
| **首次部署（ZIP 下载）** | **[docs/DEPLOY.md](docs/DEPLOY.md)** |
| 计划与对接 | [plans/](plans/) |

### 官方上游与参考项目（3）

| # | 项目 | GitHub | 在本项目中的用途 |
|---|------|--------|------------------|
| 1 | **THA4**（Talking Head Anime 4） | [pkhungurn/talking-head-anime-4-demo](https://github.com/pkhungurn/talking-head-anime-4-demo) | 核心 Student 面捕引擎、MediaPipe puppeteer、蒸馏与训练 demo；Git `upstream` 默认指向此仓库 |
| 2 | **THA3**（Talking Head Anime 3） | [pkhungurn/talking-head-anime-3-demo](https://github.com/pkhungurn/talking-head-anime-3-demo) | 立绘 portrait 模式、`deps/tha3/` 运行时与 DEPLOY 档位 **[3] tha3_models** 权重来源 |
| 3 | **EasyVtuber** | [yuyuyzl/EasyVtuber](https://github.com/yuyuyzl/EasyVtuber) | **Mouse + Audio** 无摄像头面捕交互思路参考（全屏鼠标 + 麦克风口型） |

Git 远程：`origin` = 本 fork；`upstream` = THA4 官方。详见 [docs/FORK_ROOT.md](docs/FORK_ROOT.md)。

> ~~`E:\THA4_bundle_bai_custom`~~ 已废弃，内容已迁入本仓（见 HANDOVER 附录）。

---





## 相对 THA4 原版做了什么（简要）

在官方 `character_model_mediapipe_puppeteer` 基础上，做了一套 **MediaPipe 面捕 + 可调显示变换 + 更好用的 wx 调参界面**，主入口为实验脚本 `character_model_mediapipe_puppeteer_load_preview.py`。

### 1. 界面与窗口

- **默认完整调参窗**启动（`startup_show_full_controls`）；可选 **精简小窗**（3 快捷按钮）与完整窗来回切换
- 角色输出独立无边框窗口，可拖动画布，几何与状态可持久化
- 控件分栏：模型传入 / 输出动态增强 / 后处理；竖滑块、分割条位置记忆

### 2. 显示与跟踪

- 人脸跟踪驱动自动平移、缩放（可关）
- 非线性缩放曲线 + 预览；倾斜映射旋转、镜像作为最后一步
- **输出动态增强校准**：刷新缩放基准、左右归中与当前头滚转（左倾/右倾）基准；不改垂直基准，避免上漂；支持周期自动校准与平滑过渡
- 可调后处理抗锯齿

### 3. 模型与持久化

- 加载后即显示默认姿态；`Load Last` / `Load Other`
- `workspace/load_preview_ui_state.json` 保存开关、滑块、输出窗、嘴部/显示变换等

### 4. 呼吸与嘴部（`mediapipe_face_pose_converter_00.py`）

- 呼吸控件与反应式呼吸
- 嘴部：面捕 / 音频驱动切换，设备选择与 OBS 风格电平条

### 5. 面捕输入模式

- **Face capture (MediaPipe)**：摄像头 / 窗口捕获 / 视频文件（默认）
- **Mouse + Audio (EasyVtuber)**：无摄像头；**全屏鼠标**驱动头转与眼球，**麦克风**驱动口型；程序化眨眼 + 内建呼吸
- 模式在 Model Input 列切换，写入 `workspace/load_preview_ui_state.json`（`mocap_input_mode`）
- 实现：`experiments/puppeteer_load_preview/mouse_mocap_driver.py`；自检 `smoke_mouse_mocap.py`

### 6. 摄像头与视频源

- **窗口捕获**：从 DroidCam 等客户端预览窗抓帧（OBS 式）；与摄像头共用下拉源，记忆上次窗口；**加载模型后**自动连接时窗口捕获优先
- 设备下拉、DirectShow 枚举、多索引/多后端探测
- DroidCam 虚拟摄像头仍可用；后台打开；支持视频/图片文件源

### 7. 内置图层系统

- **启用图层混合**：弹出五层独立编辑窗，在内置 OutputFrame 合成（透明 PNG）
- **启动无限图层系统**：占位开关（L2 尚未实现）
- ~~向外挂图层系统输出 / bridge~~ 已移除（2026-05-30）

### 8. 其它交互

- 滑块悬停约 1 秒后才可用滚轮微调（高亮 + 提示）
- 「标定朝向」等校准按钮；已去掉「点任意控件置顶输出窗」（避免控件失效）

### 9. 附带内容

- `data/character_models/baiten_from_project_forlon9/bai_450k/`：示例白腾（代号：九星独行角色） student 模型（yaml + 图）
- 文档：`docs/HANDOVER.md`、`docs/HARDWARE_REQUIREMENTS.md`、`docs/TROUBLESHOOTING_QA.md`、`docs/DOC_INDEX.md` 等
- `his/`：按时间归档的历史快照；`archive_to_his.ps1` 留档

更细的条目见 `face-puppeteer-ui-enhancements-ai-code/CHANGELOG.md`。

“这不是我的选择，但是我选择的。”他总是如是说道。

---

## 根目录结构（发布总库）

```
<REPO_ROOT>\
├── README.md                 ← 本文件（GitHub 首页）
├── DEPLOY.bat                ← 四档安装（basic / face / THA3 / THA4）
├── RESET_ADDON.bat           ← 卸载单个可选包
├── EasyVtuberStudio.exe      ← 主入口（双击启动）
├── addons/                   ← 可选包（初始仅 README）
├── assets/                   ← 品牌资源（icon 等）
├── data/                     ← CORE 角色与示例资源
├── deps/                     ← pip 清单与 THA3 代码
├── docs/                     ← 全部文档（DEPLOY、HANDOVER、排障…）
├── face-puppeteer-ui-enhancements-ai-code/
├── packaging/                ← 便携发行、manifest、编译脚本
├── plans/
├── scripts/
│   ├── launch/               ← bat 启动器（run、THA4Train、DownloadAssets…）
│   └── maint/                ← develop→fork 同步、路径验收
├── tools/training/
└── workspace/                ← 用户可写状态（ui state、deploy.log）
```

## 环境兼容策略

为避免 THA3 与 THA4 依赖不兼容影响运行稳定性，fork 内采用两套依赖环境策略：

- THA4 Student 外壳依赖：`deps/pip/requirements-tha4-student.txt`
- THA3 ONNX+DirectML 依赖：`deps/pip/requirements-tha3-ort.txt`

对应安装：运行 **`DEPLOY.bat`** 选择档位，或维护者使用 `deps\pip\install_*.bat`（需已存在 venv，见 `resolve_venv.bat`）。已内置。

---

## 日常流程

1. **用户**：双击根目录 **`EasyVtuberStudio.exe`**
2. **开发**：在 `E:\tha4fork-develop` 改代码 → `scripts\maint\sync_develop_to_fork.ps1` → fork push
3. **维护者编译 exe**：`scripts\build_launchers.bat`

---

## 最近推送

| 提交 | 说明 |
|------|------|
| `v1.0` | 便携 DEPLOY 四档、Mouse + Audio 面捕、文档与 GitHub 发布 [EasyVtuberStudio](https://github.com/liketocood345/EasyVtuberStudio) |
