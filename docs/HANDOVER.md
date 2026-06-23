# EasyVtuberStudio — 项目交接说明（新 Agent / 维护者主入口）

> **文档权威副本在 fork 发布总库 `E:\easyvtuberstudio-main\docs\`（本文件）。**  
> 代码日常开发在 **`E:\easyvtuberstudio-develop`**，稳定后 `scripts\maint\sync_develop_to_fork.ps1` 合并到 fork 再 push。  
> ~~`E:\THA4_bundle_bai_custom`~~ 已废弃。  
> 远程：https://github.com/liketocood345/EasyVtuberStudio  
> 曾用名：`EasyVtuber-with-THA3-THA4`
> **文档总索引：** [DOC_INDEX.md](DOC_INDEX.md)

---

## 0) 新 Agent 5 分钟上手

### 0.1 仓库角色

| 路径 | 用途 |
|------|------|
| **`E:\easyvtuberstudio-main`** | **发布总库**：GitHub ZIP **CORE**（刚解压态：无 runtime/可选包，仅 bai + 代码） |
| **`E:\easyvtuberstudio-develop`** | **研发主仓**：**三模块全装**（`addons/face_puppeteer` + `tha3_models` + `tha4_training`），日常改代码 |
| ~~`E:\THA4_bundle_bai_custom`~~ | **已废弃** |

**目录约定（两仓代码布局一致，差异在 `addons/` 是否有实体文件）：**

| 实体 / 链接 | develop（全装） | fork（GitHub 解压） |
|-------------|-----------------|---------------------|
| `addons/face_puppeteer/` | venv + mediapipe | 空（仅 README） |
| `addons/tha3_models/` | .pt 权重 | 空 |
| `addons/tha4_training/` | teacher + pose | 空 |
| `runtime/venv` | junction → addons | 不存在 |
| `deps/tha3/models` | junction → addons | README 占位 |

develop 迁移/验收：`scripts\maint\setup_develop_full_install.ps1` 或 `packaging\verify_full_install.ps1`  
双仓整理（develop 全装 + fork 瘦包）：`scripts\maint\reconcile_both_repos.ps1`  
fork 瘦包验收：`packaging\verify_fresh_extract.ps1`  
详见 [ADDONS_LAYOUT.md](ADDONS_LAYOUT.md)

### 0.2 一键启动

**定制部署 / 发布验收（fork）：**

```bat
cd /d E:\easyvtuberstudio-main
EasyVtuberStudio.exe
```

**日常开发（develop）：**

```bat
cd /d E:\easyvtuberstudio-develop
scripts\launch\run_load_preview_puppeteer.bat
```

或 `scripts\launch\run_load_preview_puppeteer.bat`（优先启动根目录 exe）。

### 0.3 主代码路径（本仓）

| 用途 | 相对路径 |
|------|----------|
| **代码地图（CodeGraph）** | [docs/CODEBASE_MAP.md](CODEBASE_MAP.md) — 仓库分区、调用链、热点；结构性问题先 CodeGraph |
| 主 UI / 合成 | `face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/character_model_mediapipe_puppeteer_load_preview.py` |
| 图层模块 | `.../layer_runtime.py`、`.../basic_layer_window.py` |
| 面捕 / 呼吸 / 嘴部 | `face-puppeteer-ui-enhancements-ai-code/talking-head-anime-4-demo/src/tha4/mocap/mediapipe_face_pose_converter_00.py` |
| **OpenSeeFace** | `.../openseeface_mocap_driver.py`、`openseeface_runtime.py`、`openseeface_packet.py` |
| 鼠标+音频面捕 | `.../experiments/puppeteer_load_preview/mouse_mocap_driver.py` |
| **ULW 真透输出** | `.../transparent_capture_window.py` |
| UI 状态 | `workspace/load_preview_ui_state.json` |
| 五层持久化 | `workspace/basic_layers/` |
| THA3 依赖与资产 | 仓库根 `deps/tha3/`、`deps/pip/` |
| 环境安装 | `deps/pip/install_all_image_source_deps.bat` |

### 0.4 延伸阅读（按需）

| 文档 | 何时读 |
|------|--------|
| [CODEBASE_MAP.md](CODEBASE_MAP.md) | **结构性上手**：模块分区、入口、调用链、热点；配合 CodeGraph MCP/CLI |
| [../plans/layer-runtime-replan_3a393fc1.plan.md](../plans/layer-runtime-replan_3a393fc1.plan.md) | 做多图层 / L1–L3 功能前（先读「交接摘要」「当前代码现实」） |
| [../plans/EXTERNAL_LAYER_INTERFACE.md](../plans/EXTERNAL_LAYER_INTERFACE.md) | 外挂 bridge 已废弃说明 |
| [../face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/THA3_INTEGRATION.md](../face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/THA3_INTEGRATION.md) | THA3 立绘黑盒、`deps/tha3` |
| [DEPLOY.md](DEPLOY.md) | **首次部署**：GitHub ZIP → 第一次正常启动 |
| [ADDONS_LAYOUT.md](ADDONS_LAYOUT.md) | 可选包 `addons/` 与 junction |
| [PREP_PUSH.md](PREP_PUSH.md) | **fork push 前检查清单** |
| [HF_BUCKET_MIRROR.md](HF_BUCKET_MIRROR.md) | **HF Bucket 完整发行与瘦包补充（维护者）** |
| [BUG_HOTSPOT_CHECKLIST.md](BUG_HOTSPOT_CHECKLIST.md) | **新功能必查**：历史 bug 热点 Top10（push / sync 后自动刷新） |
| [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) | **排障（最全）** |
| [UI_DIALOG_SAFETY.md](UI_DIALOG_SAFETY.md) | **高危**：定时器弹窗频率限制 |
| [HARDWARE_REQUIREMENTS.md](HARDWARE_REQUIREMENTS.md) | 硬件 |
| [DOC_INDEX.md](DOC_INDEX.md) | 全部 Markdown 索引 |
| [training/README_BAI_CUSTOM.txt](training/README_BAI_CUSTOM.txt) | body 续训 / 打包白猫 student（历史流程） |
| [camfix/CAMERA_CHANGES_SUMMARY.md](camfix/CAMERA_CHANGES_SUMMARY.md) | 摄像头/DroidCam 改动摘要 |
| [../README.md](../README.md) | Fork 总览、双环境策略 |

### 0.5 当前进度（2026-06-24）

**已完成（面向发布 / 日常开发）**

- **默认完整调参窗** + 可选精简小窗；**ULW 单输出窗**（真透 + 四档背景合成进同一分层窗）
- **三种面捕**：OpenSeeFace（DEPLOY [2]）· MediaPipe / 窗口捕获（[3]）· Mouse + Audio（[1] 即可）
- THA3 / THA4 Student 双图像源；**输出动态增强校准**；窗口捕获 **后台 worker**
- **图层 L2**：动态槽位增删；简单摇摆、圆周运动、环绕跟随（orbit host）；绑定随躯干倾斜
- **输出增强**（f-055）：SR / RIFE / TRT 可选链，默认恒等；DEPLOY [6]
- **长跑稳定性**：ULW 独立线程投递；`output_stall_watch_timer` 输出停滞自愈；infer worker stuck 愈合
- **2026-06-24 发布版**：已去除 `longrun_freeze_debug` 等 NDJSON 诊断脚手架（不再默认写 `debug-3353ed.log`）

**自检脚本（develop / main，`face-puppeteer-ui-enhancements-ai-code` 下）**

| 领域 | 脚本 |
|------|------|
| 图层 | `smoke_layer_runtime.py` |
| 鼠标面捕 | `smoke_mouse_mocap.py` |
| OpenSeeFace | `smoke_openseeface_mocap.py`、`smoke_openseeface_preview.py` |
| 窗口捕获 | `smoke_window_capture.py` |
| 后处理 | `smoke_output_enhancement.py` |

**仍在推进 / 范围外**

| 优先级 | 说明 |
|--------|------|
| 中 | L2/L3 手动长测（GIF/视频图层、复杂绑定链） |
| 低 | 外挂 bridge 已永久移除；见 `plans/EXTERNAL_LAYER_INTERFACE.md` |

历史 §0.5（2026-05-29）中「L2 占位」「OutputFrame 始终可见」等描述已过时；以本节与 [CHANGELOG.md](CHANGELOG.md) 为准。

### 0.6 UI 弹窗安全（高危）

**任何能导致报错弹窗在一秒内弹出超过一次的问题，均视为高危漏洞。** 定时器 / 循环路径禁止直接 `ShowModal`；用户操作弹窗须走 `ui_dialog_guard.show_rate_limited_message`。fork 瘦包未装 `face_puppeteer` 时启动同步回退 **Mouse + Audio**。详见 [UI_DIALOG_SAFETY.md](UI_DIALOG_SAFETY.md)。

### 0.7 提交前自检

- [ ] 改动是否落在正确仓库（**发布**改 `E:\easyvtuberstudio-main`，**研发**改 `E:\easyvtuberstudio-develop`）
- [ ] THA3 ↔ THA4 切换是否 `stop()` 旧源
- [ ] 图层改动是否仅在 L1/L2 计划范围内
- [ ] 新增失败分支是否在 timer/循环里弹窗（须用 `ui_dialog_guard` 或静默降级）

---

## 1) 项目目标

在官方 THA4 `character_model_mediapipe_puppeteer` 基础上，**EasyVtuberStudio** 提供 **OpenSeeFace / MediaPipe / Mouse+Audio 多路面捕 + 可调显示变换 + wx 调参 UI + ULW 真透单输出窗 + 内置图层与可选后处理**，主入口：

`character_model_mediapipe_puppeteer_load_preview.py`（`EasyVtuberStudio.exe`）

能力概要：默认完整调参窗、可选精简小窗、**ULW 分层输出窗**、呼吸/嘴部（面捕或音频）、THA3/THA4 双图像源、图层 L2（动态槽位 / 运动 / 绑定）。

### Mouse + Audio mocap（无摄像头）

Model Input 列选择 **Mouse + Audio (EasyVtuber)**：

- **不需要**摄像头 / MediaPipe `detect_for_video`；视频源控件会禁用。
- **全屏鼠标**：主屏坐标归一化到 `[-1,1]`，合成 `MediaPipeFacePose`（头 `xform_matrix` + `EYE_LOOK_*` blendshapes）。
- **麦克风**：自动切换 `mouth_input_mode=audio`（切回 Face capture 时恢复切换前的口型模式）。
- **眨眼**：`mouse_mocap_driver.build_blink_blendshapes` 周期写入；呼吸仍走 converter `enable_breathing`。
- THA3 立绘模式同样读取 `mediapipe_face_pose`，无需单独路径。
- 自检：`python experiments/puppeteer_load_preview/smoke_mouse_mocap.py`（develop 根目录，使用 THA4 venv）。

---

## 2) 目录结构（本仓 = fork 发布总库）

```
E:\easyvtuberstudio-main\
├── README.md                   ← GitHub 首页
├── EasyVtuberStudio.exe        ← 面捕主入口
├── docs/                       ← 全部 Markdown（本文件在此）
├── scripts/launch/             ← bat 启动器、THA4Train.exe
├── plans/
├── packaging/
├── workspace/                  ← UI 状态、训练输出
├── deps/
└── face-puppeteer-ui-enhancements-ai-code/
    └── experiments/puppeteer_load_preview/
```

研发主仓 **`E:\easyvtuberstudio-develop`** 目录布局与上表相同（无 GitHub 发布文档时以 fork 根文档为准）。

---

## 3) 环境与依赖

- Python 3.10.x，`venv` 通常在 `face-puppeteer-ui-enhancements-ai-code/talking-head-anime-4-demo/venv` 或仓库根 `venv`
- **两套依赖**（避免 THA3/THA4 冲突）：
  - `deps/pip/install_tha4_student_deps.bat`
  - `deps/pip/install_tha3_ort_deps.bat`
  - 或 `install_all_image_source_deps.bat`
- THA3 ONNX 大包：`deps/tha3/populate_tha3_bundle.ps1`（首次）

---

## 4) 已实现功能索引

| 章节 | 内容 |
|------|------|
| §5 | 完整调参窗 + 可选精简小窗 |
| §6 | 关键类名与变量 |
| §7 | 内置图层系统（L2 动态槽位 + ULW 合成） |
| §8 | THA3 / THA4 Student 双图像源 |
| §9 | 已知限制与推荐后续 |
| §10 | 快速验收步骤 |

---

## 5) 完整调参窗 + 可选精简小窗

实现文件：`character_model_mediapipe_puppeteer_load_preview.py`

- **启动默认**：`startup_show_full_controls()` → 展开完整调参窗并确保输出窗
- **精简小窗**（可选）：3 快捷按钮 — 校正头部朝向、输出动态增强校准、切换到完整调参窗；加载新模型需在完整窗操作
- 完整窗 `ControlsFrame` 首次需要时懒创建；精简 ↔ 完整可切换（`show_compact_launcher` / `show_full_controls_window`）
- 捕获循环与输出定时器始终运行；仅控件可见性变化
- `ValueState` / `SelectionState`：完整窗未创建时的占位，避免访问不存在的 wx 控件
- **视频源**：启动时不自动连摄像头；**Load Other / Load Last 加载模型** 时调用 `refresh_and_autoload_video_source()`（窗口捕获优先）

---

## 6) 关键标识（新 Agent 查代码用）

### 6.1 主脚本 `character_model_mediapipe_puppeteer_load_preview.py`

- `ControlsFrame`、`create_controls_frame()`
- `show_full_controls_window()` / `show_compact_launcher()`
- `draw_result_wx_image()` — **最终合成入口**（图层功能将接在此处）
- `create_postprocess_panel()` — 后处理 / 图层开关 / 图像来源
- `load_persistent_ui_state()` / `collect_persistent_ui_state()` — 持久化入口

### 6.2 `mediapipe_face_pose_converter_00.py`

- 呼吸 / 嘴部 UI、`audio_device_name`、音频设备状态文案

---

## 7) 内置图层系统

| 项 | 位置 |
|----|------|
| 五层混合 UI | 后处理区：**启用图层混合** → `BasicLayerWindow` |
| 无限层 / 动态槽 | 后处理区：**启动无限图层系统** → 图层窗内可增删槽位（L2 基础）；持久化 `basic_layers/manifest` |
| 持久化 | `layer_blend_enabled`、`unlimited_layers_enabled`；`basic_layers/` |
| 模块 | `layer_runtime.py`、`basic_layer_window.py`、`layer_swing_pivot_dialog.py`、`numpy_layer_compositor.py` |
| 简单摇摆运动 | 图层详情 **运动 → 简单摇摆**：支点编辑、幅度、速度（度/秒）、全程匀速/到两侧放缓 |
| 圆周运动 | **运动 → 圆周运动**：轨道/绑定点编辑、近远缩放、前后槽征用；见手册 ix 条目与 `CUSTOM_FUNCTION_INDEX.md` |

合成在 `draw_result_wx_image()` → `_compose_present_rgba` 完成，**真透档交付 ULW**（`transparent_capture_window.py`）；非真透背景仍可用 wx `OutputFrame`。**已无**向外挂进程写 bridge 文件。

历史：`external_layer_output_bridge.py` 与 `external_layer_output/` 已于 2026-05-30 移除。见 [plans/EXTERNAL_LAYER_INTERFACE.md](plans/EXTERNAL_LAYER_INTERFACE.md)。

---

## 8) THA3 / THA4 Student 双图像源

| 项 | 位置 |
|----|------|
| 架构 | `image_sources/`（`Tha4StudentSource` / `Tha3Source`） |
| 引擎 | `tha3_engine.py`、`tha3_pose_adapter.py` |
| 文档 | `experiments/puppeteer_load_preview/THA3_INTEGRATION.md` |

切换图像源时对旧源 `stop()` 再 `start()` 新源。外壳共用 `draw_result_wx_image()` 与内置图层合成。

验收（在 **实际运行的仓库** 下执行，fork 或 develop 均可）：

```bat
cd /d E:\easyvtuberstudio-main
packaging\verify_deploy.ps1 -PortableRoot . -Strict -RequireFacePuppeteer -RequireTha3Models
```

或 smoke 脚本（需已装对应 venv）：

```bat
cd /d E:\easyvtuberstudio-main\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo
set PYTHONPATH=%cd%\src
..\..\..\addons\face_puppeteer\venv\Scripts\python.exe ..\experiments\puppeteer_load_preview\smoke_tha3_preview.py
```

（develop 将路径中的 `easyvtuberstudio-main` / `easyvtuberstudio-develop` 替换为实际目录；瘦包仅 basic 时用 `workspace\student_venv\Scripts\python.exe`。）

---

## 9) 已知限制 / 推荐后续

1. 紧凑/完整窗切换未降低 MediaPipe 与预览绘制开销（需 gate `update_capture_panel` 等）。
2. 图层级 L1 已落地；L2「无限图层」已可增删槽位，高级编组/环路校验仍待做。
3. ~~外挂 bridge~~ 已移除，全部内置。

---

## 10) 快速验收

1. 根目录 **`EasyVtuberStudio.exe`** 或 `scripts\launch\run_load_preview_puppeteer.bat` → **默认完整调参窗** + 输出窗（非仅 3 按钮精简窗）。
2. 精简小窗 ↔ 完整窗切换正常（完整窗内「切换到精简小窗」）。
3. 加载模型 → 默认姿态预览；视频源列表刷新并尝试自动连接。
4. 勾选 **启用图层混合** → 五层独立窗口出现；加载 PNG 后输出与预览遮挡一致；预览/输出可点选拖动图层；绑定身体/头后开启动态增强应跟动。
5. THA3 立绘加载 → 面捕驱动；切回 THA4 Student 仍正常。
6. `venv\Scripts\python.exe experiments\puppeteer_load_preview\smoke_layer_runtime.py` 通过。

---

## 附录：自 bai_custom 迁入清单

若你曾使用 `E:\THA4_bundle_bai_custom`，对应关系：

| 旧路径 | 新路径 |
|--------|--------|
| `experiments\puppeteer_load_preview\` | `face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\` |
| 根目录 `HANDOVER.md` / `layer-runtime-replan_*.plan.md` | `HANDOVER.md` / `plans\` |
| `README_BAI_CUSTOM.txt`、训练 bat/ps1 | `docs\training\` |
| `camfix\` 说明 | `docs\camfix\` |
| `scripts\probe_cameras.bat` | `scripts\` |

一次性补拷（源目录仍存在时）：`migrate_from_bai_custom.ps1`
