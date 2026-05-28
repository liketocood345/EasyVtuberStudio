# 新 Agent 快速接手（5 分钟版）

> 本文件是 **唯一推荐入口**。读完后再按需打开下方链接，不要直接从 600+ 行计划全文入手。

## 1. 三个仓库各干什么

| 路径 | 角色 | 你该改哪里 |
|------|------|------------|
| `E:\THA4_bundle_bai_custom` | **活跃开发**（日常跑、改代码） | ✅ 默认在这里写代码 |
| `E:\tha4fork-develop` | **研发同步仓**（本仓库；计划 + 与 GitHub 同步的代码副本） | 改计划文档、或从 bai_custom 同步后再 commit |
| `E:\tha4fork` | **发布总库**（对外 fork / README 首页） | 稳定后再合并，不要和 develop 混为一谈 |

远程：https://github.com/liketocood345/EasyVtuber-with-THA3-THA4

## 2. 先读什么（顺序）

1. **本文**（你正在读）
2. [HANDOVER.md](HANDOVER.md) — 已实现功能、关键类名、§7 外挂、§8 THA3/THA4 双源
3. [EXTERNAL_LAYER_INTERFACE.md](EXTERNAL_LAYER_INTERFACE.md) — 仅在做外挂合成器对接时必读
4. [layer-runtime-replan_3a393fc1.plan.md](layer-runtime-replan_3a393fc1.plan.md) — 做图层功能时必读；先读「交接摘要」「当前代码现实」「三层实施节奏」

排障与硬件：`face-puppeteer-ui-enhancements-ai-code/TROUBLESHOOTING_QA.md`、`HARDWARE_REQUIREMENTS.md`  
THA3 立绘黑盒：`face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/THA3_INTEGRATION.md`

## 3. 一键启动（develop 仓）

```bat
cd /d E:\tha4fork-develop
》》》》start《《《《.bat
```

等价于 `run_load_preview_puppeteer.bat`。需已配置 `venv` 与 `deps/pip` 依赖（见根目录 `README.md`「环境兼容策略」）。

活跃开发机常用：

```bat
cd /d E:\THA4_bundle_bai_custom
experiments\puppeteer_load_preview\run_load_preview_puppeteer.bat
```

## 4. 主代码位置（develop 仓内相对路径）

| 用途 | 路径 |
|------|------|
| 主 UI / 合成入口 | `face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/character_model_mediapipe_puppeteer_load_preview.py` |
| 外挂 bridge | `.../external_layer_output_bridge.py` |
| 面捕/呼吸/嘴部 | `face-puppeteer-ui-enhancements-ai-code/talking-head-anime-4-demo/src/tha4/mocap/mediapipe_face_pose_converter_00.py` |
| UI 状态 JSON | `.../puppeteer_load_preview/load_preview_ui_state.json` |
| 外挂运行时输出 | `.../puppeteer_load_preview/external_layer_output/{contract,status}.json` |

在 **bai_custom** 中，将 `face-puppeteer-ui-enhancements-ai-code/` 前缀去掉，根目录即 `experiments\puppeteer_load_preview\`。

## 5. 当前进度（2026-05-28）

### 已完成（可验收）

- 紧凑启动窗 + 懒加载完整调参窗（HANDOVER §5–6）
- 外挂输出开关 + `contract.json` / `status.json` 元数据（L0，见 EXTERNAL_LAYER_INTERFACE）
- THA3 / THA4 Student 双图像源切换（HANDOVER §8）
- 双环境依赖拆分：`deps/pip/requirements-tha4-student.txt` 与 `requirements-tha3-ort.txt`

### 下一步（计划 todo，勿跳层）

| 优先级 | Todo ID | 内容 |
|--------|---------|------|
| 高 | `L0-external-output-rgba-export` | 每帧写出 RGBA 到 `frame_rgba_path` |
| 高 | `L1-document-confirmed-scope` | 固化五层范围与验收对照 |
| 高 | `L1-define-basic-layer-state` | 建立 `basic_layers_state`，**尚无图层级状态** |
| 中 | `L1-*` 其余 | 几何求值、五层 UI、静态合成（见计划第一层） |
| 低 | L2 / L3 | **验收通过 L1 前不要开** |

**常见误判：** 计划里大量描述的是 **未来** 五层/不限层能力；当前代码仍是 **整图** 平移/缩放/旋转，没有 `basic_layers_state` 实现。

## 6. 实现图层时的硬约束（摘自计划）

- 预览与 `draw_result_wx_image()` **必须共用** `LayerGeometryResolver` 结果
- 角色帧来自 THA3/THA4 黑盒；图层只接外壳输出，不改 THA 推理链
- 先建统一图层状态，再挂 UI；不要先堆面板
- 五层模式与不限层模式 **共享求值逻辑**，容量与 UI 不同
- 父子绑定最大深度 3；不做完整创作工具 / Live2D 编辑器方向

## 7. 同步计划文档

从活跃仓更新本目录：

```powershell
cd E:\tha4fork-develop
powershell -ExecutionPolicy Bypass -File sync_plans_from_bai_custom.ps1
```

`EXTERNAL_LAYER_INTERFACE.md` 若 bridge 字段变更，需人工对照 `external_layer_output_bridge.py` 更新。

## 8. 提交前自检

- [ ] 改的是 bai_custom 还是 develop？两者路径不要混在说明里
- [ ] 外挂模式：勾选后内置输出窗是否隐藏、`status.json` 的 `frame_sequence` 是否递增
- [ ] THA3/THA4 切换后旧源是否 `stop()`
- [ ] 图层相关改动是否只动 L1 范围（未提前做 L2 组/多选）
