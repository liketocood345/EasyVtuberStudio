[首次部署（GitHub ZIP 下载后） / First-time Deploy](docs/DEPLOY.md)

**便携版（推荐最终用户）：** [GitHub Download ZIP](https://github.com/liketocood345/EasyVtuberStudio)（瘦包）或 [HF Bucket 完整目录](https://huggingface.co/buckets/liketocode789/EasyVtuberStudio) → **`DEPLOY.bat`**（**六档**数字选择，Enter = 仅 [1]）→ **`EasyVtuberStudio.exe`**。详见 [docs/DEPLOY.md](docs/DEPLOY.md)。

**本仓库 = GitHub 发布总库（CORE 刚解压态）**；本地全装研发在 `E:\easyvtuberstudio-develop`（三模块 `addons/*` 实体文件，不入本 ZIP）。见 [docs/HANDOVER.md](docs/HANDOVER.md) §0.1 · [docs/ADDONS_LAYOUT.md](docs/ADDONS_LAYOUT.md) · 推送前 [docs/PREP_PUSH.md](docs/PREP_PUSH.md)。

[English Guide for EasyVtuberStudio](docs/README-EN.md)

# EasyVtuberStudio

**EasyVtuberStudio** — 基于 THA3、THA4 的可面捕虚拟皮套演播软件，可添加附件（主入口 **`EasyVtuberStudio.exe`**）。

**新 Agent 请先读 [docs/HANDOVER.md](docs/HANDOVER.md)。**


> ### 【重要声明】
>
> 1. **使用前提**：下载或使用本软件前，请确认您具备基本的 Windows 操作与排障能力，并能在必要时借助翻译工具阅读安装过程中的**英文终端输出**（详见 [docs/DEPLOY.md](docs/DEPLOY.md)、[docs/TROUBLESHOOTING_QA.md](docs/TROUBLESHOOTING_QA.md)）。
> 2. **AI 生成代码风险**：本项目含大量 **AI 辅助编写**的代码。继续下载或使用，即表示您已理解并接受：代码可能存在未预见缺陷，**可能导致程序异常、数据丢失或在极端情况下加剧系统或硬件负载**；请在可接受风险的前提下自行决定是否使用。

**骚年，想玩虚拟皮套直播但没钱定制自己的角色？你的显卡该出场了！（虽然本项目能在无显卡电脑上跑出惊人的1fps）**

~~这个项目是面向游戏主播等不以虚拟皮套为卖点的主播，**不要敷衍你的观众！**~~






https://github.com/user-attachments/assets/f282fbef-212c-4839-8cf5-1793cd1926d5



## 仓库与路径

| 项 | 说明 |
|----|------|
| **GitHub 仓库** | **[liketocood345/EasyVtuberStudio](https://github.com/liketocood345/EasyVtuberStudio)** |
| **HF Bucket（完整发行）** | **[liketocode789/EasyVtuberStudio](https://huggingface.co/buckets/liketocode789/EasyVtuberStudio)** — 含 `data/ezvtb_nn/` ONNX |
| **本仓库（GitHub CORE）** | 当前解压目录；本地示例 `E:\easyvtuberstudio-main`（`addons/` 初始为空；**不含** NN ONNX） |
| **研发主仓（非 GitHub 仓库）** | `E:\easyvtuberstudio-develop` — **三模块全装**，日常改代码后 `scripts\maint\sync_develop_to_fork.ps1` 再 push 到上表 GitHub |
| 曾用 GitHub 仓库名 | ~~EasyVtuber-with-THA3-THA4~~（2026-05 更名为 **EasyVtuberStudio**） |
| 曾用本地目录 | `E:\tha4fork` / `E:\tha4fork-develop` |
| 定制代码包 | `face-puppeteer-ui-enhancements-ai-code/` |
| **新 Agent 入口** | **[docs/HANDOVER.md](docs/HANDOVER.md)** |
| **首次部署** | **[docs/DEPLOY.md](docs/DEPLOY.md)** · HF Bucket 见上表 |
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

在官方 `character_model_mediapipe_puppeteer` 基础上，扩展为 **多路面捕 + THA3/THA4 双图像源 + 真透 ULW 单输出窗 + 内置图层与可选后处理**，主入口 `character_model_mediapipe_puppeteer_load_preview.py`（根目录 **`EasyVtuberStudio.exe`**）。

### 1. 界面与输出

- **默认完整调参窗**启动（`startup_show_full_controls`）；可选 **精简小窗**（3 快捷按钮）与完整窗来回切换
- **单一分层输出窗（ULW，标题 `easyvtuberstudio_output`）**：真透档 per-pixel alpha 桌面叠加；纯色/图片/黑键背景合成进同一窗；图层选中、手柄编辑、空白拖窗在 ULW 完成（真透档隐藏 wx `OutputFrame`）
- 控件分栏：模型传入 / 输出动态增强 / 后处理；预览行含立绘+摄像头+**右侧校准列**；竖滑块、分割条比例记忆（250ms 防抖写盘）

### 2. 显示与跟踪

- 人脸跟踪驱动自动平移、缩放（可关）
- 非线性缩放曲线 + 预览；倾斜映射旋转、镜像作为最后一步
- **输出动态增强校准**：刷新缩放基准、左右归中与当前头滚转（左倾/右倾）基准；不改垂直基准，避免上漂；支持周期自动校准与平滑过渡
- 可调后处理抗锯齿

### 3. 模型与持久化

- 加载后即显示默认姿态；`Load Last` / `Load Other`
- `workspace/load_preview_ui_state.json` 保存开关、滑块、输出窗、嘴部/显示变换、面捕模式等

### 4. 呼吸与嘴部（`mediapipe_face_pose_converter_00.py`）

- 呼吸控件与反应式呼吸（含幅度增益滑块）
- 嘴部：面捕 / 音频驱动切换，设备选择与 OBS 风格电平条

### 5. 面捕输入模式（Model Input）

| 模式 | 说明 | DEPLOY 档位 |
|------|------|-------------|
| **OpenSeeFace** | `facetracker.exe` 独立采摄像头，UDP 驱动 THA；左侧预览镜像 **OpenSeeFace Visualization** 窗口 | **[2] openseeface** |
| **Face capture (MediaPipe)** | 摄像头 / **窗口捕获** / 视频文件（EVS 抓帧 + MediaPipe） | **[3] face_puppeteer** |
| **Mouse + Audio (EasyVtuber)** | 无摄像头；全屏鼠标驱动头转与眼球，麦克风驱动口型；程序化眨眼 + 内建呼吸 | **[1] basic_run** 即可 |

模式写入 `workspace/load_preview_ui_state.json`（`mocap_input_mode`）。实现：`openseeface_mocap_driver.py`、`openseeface_runtime.py`、`mouse_mocap_driver.py`；自检 `smoke_openseeface_mocap.py`、`smoke_mouse_mocap.py`。

### 6. 摄像头与视频源

- **窗口捕获**：后台 worker 抓取目标窗（DroidCam 预览、OBS 等）；与摄像头共用下拉源；**加载模型后**自动连接时窗口捕获优先
- 设备下拉、DirectShow 枚举、多索引/多后端探测；支持视频/图片文件源

### 7. 内置图层系统

- **启用图层混合**：弹出多槽位 `BasicLayerWindow`，在内置预览区编辑
- **无限图层系统（L2）**：动态增删槽位；**简单摇摆**、**圆周运动**、**环绕跟随（orbit host）**；绑定可随躯干倾斜（Lean shift/rotate）
- 合成经 `draw_result_wx_image()` → present 管线交付 **ULW**（`layer_runtime.py`、`numpy_layer_compositor.py`）
- ~~向外挂图层系统输出 / bridge~~ 已移除（2026-05-30）

### 8. 输出增强（可选）

- 后处理链：NN 超分、RIFE 帧插值、TensorRT 等（默认全关 = 恒等，挂于 compose 之后）
- 安装 **DEPLOY [6] output_enhancement**；ONNX 权重从 HF Bucket `data/ezvtb_nn/` 拉取（完整桶已内置）

### 9. 其它交互

- 滑块悬停约 1 秒后才可用滚轮微调（高亮 + 提示）
- 预览行右侧：**标定朝向**、**输出动态增强校准**及周期自动校准；精简窗保留 3 快捷校准按钮

### 10. 附带内容与文档

- `data/character_models/baiten_from_project_forlon9/bai_450k/`：示例白腾 student 模型
- 文档：`docs/HANDOVER.md`、`docs/TROUBLESHOOTING_QA.md`、`docs/DOC_INDEX.md`、`docs/CHANGELOG.md` 等
- `his/`：按时间归档的历史快照

**发布版说明（2026-06-24）：** 已去除长跑 debug 脚手架（`debug-3353ed.log` 等 NDJSON 埋点）；保留 ULW 独立线程投递、输出停滞自愈、infer worker stuck 愈合等生产修复。详见 [docs/CHANGELOG.md](docs/CHANGELOG.md) §2026-06-24。

“这不是我的选择，但是我选择的。”他总是如是说道。

---

## 根目录结构（发布总库）

```
<REPO_ROOT>\
├── README.md                 ← 本文件（GitHub 首页）
├── DEPLOY.bat                ← 六档安装（basic / OSF / MediaPipe / THA3 / THA4 训练 / NN 后处理）
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
2. **开发**：在 `E:\easyvtuberstudio-develop` 改代码 → `scripts\maint\sync_develop_to_fork.ps1` → fork push
3. **维护者编译 exe**：`scripts\build_launchers.bat`

---

## 最近推送

完整改动见 [docs/CHANGELOG.md](docs/CHANGELOG.md)。

| 提交 / 日期 | 说明 |
|-------------|------|
| `2026-06-24` | **发布版去除 debug 脚手架**（NDJSON / longrun 诊断）；**OpenSeeFace** 面捕（DEPLOY [2]）；OSF 眨眼/单眼 wink 管线；ULW 线程投递与长跑卡顿缓解 |
| `2026-06-15` | **图层圆周运动**（轨道编辑、辅助槽 z 序、L2 槽位增删）；**鼠标三区校准**与 ix-025；**窗口捕获**长时卡顿优化；`CODEBASE_MAP` / BUG 热点清单 |
| `3a32f04` · 2026-06-13 | **透明 ULW 真 alpha 输出**、wx-free 合成；图层**绑定随躯干倾斜**；背景下拉四档重构 |
| `f81363b` · 2026-06-04 | **Mouse + Audio** 布局补全；三栏分割持久化 |
| `v1.0` | 便携 **DEPLOY**、Mouse + Audio 面捕、GitHub 首发 [EasyVtuberStudio](https://github.com/liketocood345/EasyVtuberStudio) |
