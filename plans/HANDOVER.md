# 项目交接说明（新 Agent 主入口）

> **请从本文件开始阅读。** 本仓库 `E:\tha4fork-develop` 是 THA3 / THA4 / EasyVtuber 集成的**唯一研发主仓**（原 `E:\THA4_bundle_bai_custom` 内容已迁入，可删除旧目录）。  
> 远程：https://github.com/liketocood345/EasyVtuber-with-THA3-THA4

---

## 0) 新 Agent 5 分钟上手

### 0.1 仓库角色

| 路径 | 用途 |
|------|------|
| **`E:\tha4fork-develop`** | **日常开发与 Git 提交（本仓）** |
| `E:\tha4fork` | 对外发布总库（稳定后再合并，勿与 develop 混用） |
| ~~`E:\THA4_bundle_bai_custom`~~ | **已废弃**，内容已迁入本仓 |

### 0.2 一键启动

```bat
cd /d E:\tha4fork-develop
》》》》start《《《《.bat
```

等价于根目录 `run_load_preview_puppeteer.bat`（自动解析 `face-puppeteer-ui-enhancements-ai-code` 与 `venv`）。

### 0.3 主代码路径（本仓）

| 用途 | 相对路径 |
|------|----------|
| 主 UI / 合成 | `face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/character_model_mediapipe_puppeteer_load_preview.py` |
| 外挂 bridge | `.../external_layer_output_bridge.py` |
| 面捕 / 呼吸 / 嘴部 | `face-puppeteer-ui-enhancements-ai-code/talking-head-anime-4-demo/src/tha4/mocap/mediapipe_face_pose_converter_00.py` |
| UI 状态 | `.../puppeteer_load_preview/load_preview_ui_state.json` |
| 外挂运行时 JSON | `.../puppeteer_load_preview/external_layer_output/{contract,status}.json` |
| THA3 依赖与资产 | 仓库根 `deps/tha3/`、`deps/pip/` |
| 环境安装 | `deps/pip/install_all_image_source_deps.bat` |

### 0.4 延伸阅读（按需）

| 文档 | 何时读 |
|------|--------|
| [plans/layer-runtime-replan_3a393fc1.plan.md](plans/layer-runtime-replan_3a393fc1.plan.md) | 做多图层 / L1–L3 功能前（先读「交接摘要」「当前代码现实」） |
| [plans/EXTERNAL_LAYER_INTERFACE.md](plans/EXTERNAL_LAYER_INTERFACE.md) | 做外挂合成器对接 |
| [face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/THA3_INTEGRATION.md](face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/THA3_INTEGRATION.md) | THA3 立绘黑盒 |
| [face-puppeteer-ui-enhancements-ai-code/TROUBLESHOOTING_QA.md](face-puppeteer-ui-enhancements-ai-code/TROUBLESHOOTING_QA.md) | 排障 |
| [face-puppeteer-ui-enhancements-ai-code/HARDWARE_REQUIREMENTS.md](face-puppeteer-ui-enhancements-ai-code/HARDWARE_REQUIREMENTS.md) | 硬件 |
| [docs/training/README_BAI_CUSTOM.txt](docs/training/README_BAI_CUSTOM.txt) | body 续训 / 打包白猫 student（历史流程） |
| [docs/camfix/CAMERA_CHANGES_SUMMARY.md](docs/camfix/CAMERA_CHANGES_SUMMARY.md) | 摄像头/DroidCam 改动摘要 |
| [README.md](README.md) | Fork 总览、双环境策略 |

### 0.5 当前进度（2026-05-28）

**已完成**

- 紧凑启动窗 + 懒加载完整调参窗（§5–6）
- 外挂输出 L0：`contract.json` / `status.json` 元数据（§7）
- THA3 / THA4 Student 双图像源（§8）
- 双 pip 环境：`deps/pip/requirements-tha4-student.txt` 与 `requirements-tha3-ort.txt`

**下一步（勿跳层）**

| 优先级 | Todo | 说明 |
|--------|------|------|
| 高 | `L0-external-output-rgba-export` | 写出 `frame_rgba_path` |
| 高 | `L1-define-basic-layer-state` | **尚无** `basic_layers_state` |
| 中 | `L1-*` | 五层几何/UI/合成（见计划第一层） |
| 低 | L2 / L3 | L1 验收通过前不要开 |

**常见误判：** 计划中的五层/不限层多为**未来目标**；当前 `draw_result_wx_image()` 仍是**整图**平移/缩放/旋转，没有图层级状态机。

### 0.6 提交前自检

- [ ] 改动路径是否都在 `E:\tha4fork-develop` 下
- [ ] 外挂模式：`status.json` 的 `frame_sequence` 是否递增
- [ ] THA3 ↔ THA4 切换是否 `stop()` 旧源
- [ ] 图层改动是否仅在 L1 范围

---

## 1) 项目目标

在官方 THA4 `character_model_mediapipe_puppeteer` 基础上，提供 **MediaPipe 面捕 + 可调显示变换 + wx 调参 UI**（EasyVtuber 风格），主入口：

`character_model_mediapipe_puppeteer_load_preview.py`

能力概要：紧凑启动窗、懒加载完整窗、独立无边框输出窗、呼吸/嘴部（面捕或音频）、非线性缩放曲线、倾斜/镜像后处理、外挂图层桥接、THA3/THA4 双图像源。

---

## 2) 目录结构（本仓）

```
E:\tha4fork-develop\
├── HANDOVER.md                 ← 本文件（主入口）
├── README.md                   ← Fork 总览（GitHub 首页类说明）
├── 》》》》start《《《《.bat       ← 一键启动
├── run_load_preview_puppeteer.bat
├── plans/                      ← 计划与外挂接口说明
├── deps/                       ← THA3 打包资产 + pip 双环境脚本
├── docs/training/              ← 白猫 body 续训脚本与说明（归档）
├── docs/camfix/
├── scripts/probe_cameras.bat
└── face-puppeteer-ui-enhancements-ai-code/
    ├── HANDOVER.md             ← 与本文件同步的副本
    ├── TROUBLESHOOTING_QA.md
    └── experiments/puppeteer_load_preview/   ← 实验主目录
```

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
| §5 | 紧凑启动 + 懒加载完整窗 |
| §6 | 关键类名与变量 |
| §7 | 外挂图层输出（bridge、`contract`/`status`） |
| §8 | THA3 / THA4 Student 双图像源 |
| §9 | 已知限制与推荐后续 |
| §10 | 快速验收步骤 |

---

## 5) 紧凑启动 + 懒加载完整窗

实现文件：`character_model_mediapipe_puppeteer_load_preview.py`

- 启动仅 3 按钮：加载上次模型、校正头部朝向、打开完整调参窗
- 完整窗 `ControlsFrame` 首次打开时懒创建
- 捕获循环与输出定时器始终运行；仅控件可见性变化
- `ValueState` / `SelectionState`：完整窗未创建时的占位，避免访问不存在的 wx 控件

---

## 6) 关键标识（新 Agent 查代码用）

### 6.1 主脚本 `character_model_mediapipe_puppeteer_load_preview.py`

- `ControlsFrame`、`create_controls_frame()`
- `show_full_controls_window()` / `show_compact_launcher()`
- `draw_result_wx_image()` — **最终合成入口**（图层功能将接在此处）
- `create_postprocess_panel()` — 后处理 / 外挂 / 图像来源
- `load_persistent_ui_state()` / `collect_persistent_ui_state()` — 持久化入口

### 6.2 `mediapipe_face_pose_converter_00.py`

- 呼吸 / 嘴部 UI、`audio_device_name`、音频设备状态文案

---

## 7) 外挂图层输出

| 项 | 位置 |
|----|------|
| UI | 后处理区：**向外挂图层系统输出** |
| 持久化 | `external_layer_output_enabled` |
| 模块 | `external_layer_output_bridge.py` |
| 运行时目录 | `external_layer_output/contract.json`、`status.json` |

行为：勾选后隐藏内置 `OutputFrame`，仍内存渲染；`publish_composite_frame()` 当前仅写元数据（`frame_rgba_path`、`layer_state_path` 为 `null`）。

**对接说明：** [plans/EXTERNAL_LAYER_INTERFACE.md](plans/EXTERNAL_LAYER_INTERFACE.md)  
**计划 todo：** `L0-external-output-*`、`L1` 合成后补像素与图层清单

---

## 8) THA3 / THA4 Student 双图像源

| 项 | 位置 |
|----|------|
| 架构 | `image_sources/`（`Tha4StudentSource` / `Tha3Source`） |
| 引擎 | `tha3_engine.py`、`tha3_pose_adapter.py` |
| 文档 | `experiments/puppeteer_load_preview/THA3_INTEGRATION.md` |

切换图像源时对旧源 `stop()` 再 `start()` 新源。外壳共用 `draw_result_wx_image()` 与外挂 bridge。

验收：

```bat
cd /d E:\tha4fork-develop\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo
set PYTHONPATH=%cd%\src
venv\Scripts\python.exe ..\experiments\puppeteer_load_preview\smoke_tha3_preview.py
venv\Scripts\python.exe ..\experiments\puppeteer_load_preview\smoke_load_preview.py
```

---

## 9) 已知限制 / 推荐后续

1. 紧凑/完整窗切换未降低 MediaPipe 与预览绘制开销（需 gate `update_capture_panel` 等）。
2. 图层级能力未实现：见 `plans/layer-runtime-replan_3a393fc1.plan.md` L1 起。
3. 外挂 L0 待补：RGBA 导出、图层 state 快照、外挂心跳 UI。

---

## 10) 快速验收

1. `》》》》start《《《《.bat` → 仅见 3 按钮 + 提示。
2. 打开完整窗 → 控件懒加载出现。
3. 加载模型 → 默认姿态预览。
4. 外挂输出勾选 → 内置输出窗隐藏，`external_layer_output/status.json` 中 `frame_sequence` 递增。
5. THA3 立绘加载 → 面捕驱动；切回 THA4 Student 仍正常。

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
