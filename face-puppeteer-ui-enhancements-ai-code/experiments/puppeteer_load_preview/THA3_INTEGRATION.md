# THA3 双黑盒图像源集成

## 概念

Load Preview 外壳统一负责：输出窗、显示变换、外挂图层桥接、UI 持久化。

两种**互斥**图像来源（切换时 `stop()` 旧源、再 `start()` 新源）：

| 模式 ID | 资产 | 运行时 |
|---------|------|--------|
| `tha4_student` | `character_model.yaml` + 蒸馏权重 | 更省 GPU |
| `tha3` | 512×512 RGBA PNG | 立绘即用，推理更重 |

EasyVtuber（`F:\EasyVtuber\...`）仅作 THA3 ONNX 权重与 pose 布局参考，不嵌入其启动器/RIFE/TensorRT。

## 目录与 junction

运行一次（已执行可跳过）：

```powershell
& E:\THA4_bundle_bai_custom\experiments\puppeteer_load_preview\setup_tha3_vendor.ps1
```

生成：

| 路径 | 指向 |
|------|------|
| `E:\THA4_bundle_bai_custom\vendor\easyvtuber\tha3` | EasyVtuber `tha3` 源码 |
| `...\data_models` | `data\models`（含 `tha3/seperable|standard/fp16|fp32` ONNX） |
| `...\data_images` | 示例立绘 PNG |
| `...\ezvtuber-rt` | ORT 推理辅助脚本 |

## 代码入口

| 文件 | 作用 |
|------|------|
| `image_sources/` | `Tha4StudentSource` / `Tha3Source` 黑盒 |
| `tha3_engine.py` | THA3 推理（PyTorch `.pt` 优先，否则 ONNX+DirectML） |
| `tha3_pose_adapter.py` | MediaPipe → 45 维 THA3 pose |
| `character_model_mediapipe_puppeteer_load_preview.py` | 外壳 + 模式切换 UI |

## UI

**后处理和其他** 面板：

- 图像来源单选：THA4 Student / THA3 立绘
- THA3 模型变体下拉
- **加载 THA3 立绘** 按钮

THA4 模式下显示 yaml 加载按钮；THA3 模式下隐藏 yaml 按钮、显示 PNG 加载。

## 持久化 (`load_preview_ui_state.json`)

```json
{
  "image_source_mode": "tha4_student",
  "tha3_character_png": "F:\\...\\character.png",
  "tha3_model_variant": "separable_half"
}
```

## 依赖（分黑盒配置）

两种图像源共用 `talking-head-anime-4-demo\venv`， supplemental 清单在：

`experiments\puppeteer_load_preview\deps\`

| 黑盒 | 清单 | 安装脚本 |
|------|------|----------|
| 外壳 + THA4 Student | `requirements-tha4-student.txt` | `deps\install_tha4_student_deps.bat` |
| THA3 ONNX+DirectML | `requirements-tha3-ort.txt` | `deps\install_tha3_ort_deps.bat` |
| THA3 PyTorch `.pt` | `requirements-tha3-pytorch.txt` | 仅需 shell（同 THA4） |

**禁止** `pip install onnx`：会升级 protobuf≥4，导致 MediaPipe 启动失败。THA3 ORT 只需 `onnxruntime-directml`；`tha3_engine.py` 已对 `onnx` 模块做 stub。

误装后修复：`deps\repair_mediapipe_protobuf.bat`

校验：

```bat
cd /d E:\THA4_bundle_bai_custom\talking-head-anime-4-demo
set PYTHONPATH=%cd%\src
venv\Scripts\python.exe ..\experiments\puppeteer_load_preview\deps\check_image_source_deps.py --mode all
```

若已安装官方 THA3 `.pt` 到 `data/models/separable_half/` 等目录，引擎会自动改用 PyTorch THA3 poser（无需 DirectML）。

## 验收脚本

```bat
cd /d E:\THA4_bundle_bai_custom\talking-head-anime-4-demo
set PYTHONPATH=%cd%\src
venv\Scripts\python.exe ..\experiments\puppeteer_load_preview\smoke_tha3_preview.py
venv\Scripts\python.exe ..\experiments\puppeteer_load_preview\smoke_load_preview.py
```

## 与图层计划的关系

外挂图层 / 五层合成消费的是外壳 **`draw_result_wx_image()` 之后** 的帧，与当前选用 THA3 还是 THA4 Student 黑盒无关。
