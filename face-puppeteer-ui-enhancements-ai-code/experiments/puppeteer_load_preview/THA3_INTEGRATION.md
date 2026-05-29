# THA3 双黑盒图像源集成

## 概念

Load Preview 外壳统一负责：输出窗、显示变换、外挂图层桥接、UI 持久化。

两种**互斥**图像来源（切换时 `stop()` 旧源、再 `start()` 新源）：

| 模式 ID | 资产 | 运行时 |
|---------|------|--------|
| `tha4_student` | `character_model.yaml` + 蒸馏权重 | 更省 GPU |
| `tha3` | 512×512 RGBA PNG | 立绘即用，推理更重 |

THA3 运行时资产打包在**仓库根** `deps/tha3/`（路径由 `tha3_paths.py` 解析，无 `E:\...` 硬编码）。

## 目录（仓库内）

| 路径 | 内容 |
|------|------|
| `deps/tha3/tha3_src/` | THA3 源码 |
| `deps/tha3/ezvtuber_rt/` | ORT 推理辅助（含 `ezvtb_rt/tha3_ort.py`） |
| `deps/tha3/models/tha3/` | ONNX 权重 |
| `deps/tha3/images/` | 示例立绘 PNG |
| `deps/pip/` | pip 清单与安装脚本 |

首次填充（需本机 EasyVtuber，仅用于一次性复制进仓库）：

```powershell
powershell -ExecutionPolicy Bypass -File deps\tha3\populate_tha3_bundle.ps1
```

或从 `experiments/puppeteer_load_preview`：

```powershell
.\setup_tha3_vendor.ps1
```

## 代码入口

| 文件 | 作用 |
|------|------|
| `image_sources/` | `Tha4StudentSource` / `Tha3Source` 黑盒 |
| `tha3_paths.py` | `find_repo_root()` → `deps/tha3/*` |
| `tha3_engine.py` | THA3 推理（PyTorch `.pt` 优先，否则 ONNX+DirectML） |
| `tha3_pose_adapter.py` | MediaPipe → 45 维 THA3 pose |
| `character_model_mediapipe_puppeteer_load_preview.py` | 外壳 + 顶栏 THA3/THA4 加载 |

## UI

顶栏：**以 THA3 加载上次/其他立绘**、**加载 THA4 Student 模型** 等。图像来源由 `image_source_mode` 与加载动作决定。

后处理区：**THA3 模型变体**下拉（THA3 模式时显示）、朝向/输出动态增强校准等。

## 持久化 (`load_preview_ui_state.json`)

路径以 **fork 仓库根** 为基准的相对路径（正斜杠），示例：

```json
{
  "image_source_mode": "tha4_student",
  "last_loaded_model_path": "face-puppeteer-ui-enhancements-ai-code/baiten_from_project_forlon9/bai_450k/character_model/character_model.yaml",
  "tha3_character_png": "deps/tha3/images/lambda_00.png",
  "tha3_model_variant": "separable_half"
}
```

读写由 `tha3_paths.to_repo_relative` / `from_repo_relative` 自动转换，勿手写跨机器绝对路径。

## 依赖（分黑盒配置）

清单与脚本在 **`deps/pip/`**（相对 fork 仓库根）：

| 黑盒 | 清单 | 安装脚本 |
|------|------|----------|
| 外壳 + THA4 Student | `requirements-tha4-student.txt` | `install_tha4_student_deps.bat` |
| THA3 ONNX+DirectML | `requirements-tha3-ort.txt` | `install_tha3_ort_deps.bat` |

**禁止** `pip install onnx`：会升级 protobuf≥4，导致 MediaPipe 启动失败。

误装后修复：`deps\pip\repair_mediapipe_protobuf.bat`

## 验收脚本

在仓库根找到 `talking-head-anime-4-demo`（或嵌套于 `face-puppeteer-ui-enhancements-ai-code`），设置 `PYTHONPATH` 后：

```bat
venv\Scripts\python.exe face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\smoke_tha3_preview.py
venv\Scripts\python.exe face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\smoke_load_preview.py
```

## 与图层计划的关系

外挂图层消费外壳 **`draw_result_wx_image()` 之后** 的帧，与 THA3 / THA4 Student 黑盒无关。
