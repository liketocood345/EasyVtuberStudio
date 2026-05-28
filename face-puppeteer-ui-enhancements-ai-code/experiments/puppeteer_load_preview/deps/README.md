# Load Preview 双黑盒依赖

Load Preview 外壳与两种**互斥**图像源共用同一个 venv：

`E:\THA4_bundle_bai_custom\talking-head-anime-4-demo\venv`

本目录按黑盒拆分 supplemental 依赖清单与安装脚本。基础栈（PyTorch、wxPython、THA4 源码等）仍由 `talking-head-anime-4-demo\poetry\pyproject.toml` / 既有 venv 提供。

## 文件一览

| 文件 | 用途 |
|------|------|
| `requirements-shell.txt` | 外壳共用：MediaPipe 人脸、UI、与 THA4 Student 推理 |
| `requirements-tha4-student.txt` | THA4 Student 黑盒（yaml + 蒸馏权重）额外约束 |
| `requirements-tha3-ort.txt` | THA3 黑盒 ONNX Runtime + DirectML 路径 |
| `requirements-tha3-pytorch.txt` | THA3 黑盒 PyTorch `.pt` 路径（通常无额外 pip 包） |
| `install_shell_deps.bat` | 安装 / 修复外壳关键 pin |
| `install_tha4_student_deps.bat` | 外壳 + THA4 Student |
| `install_tha3_ort_deps.bat` | 外壳 + THA3 ORT（**不**装 `onnx` 包） |
| `install_all_image_source_deps.bat` | 一次装齐两种黑盒 ORT 依赖 |
| `repair_mediapipe_protobuf.bat` | 误装 `onnx` 后恢复 MediaPipe |
| `check_image_source_deps.py` | 校验当前 venv 是否满足各模式 |

## 冲突规则（必读）

| 包 | THA4 Student / 外壳 | THA3 ORT |
|----|---------------------|----------|
| `mediapipe` | **必须** | 外壳仍需（pose 采集） |
| `protobuf` | **必须** `<4`（推荐 `3.20.3`） | 同上，不能与 mediapipe 冲突 |
| `onnx`（pip 包） | **禁止** | **禁止** — 会拉高 protobuf，导致 UI 启动失败 |
| `onnxruntime-directml` | THA3 模式需要 | **必须**（Windows DirectML） |

THA3 的 `tha3_ort.py` 虽 `import onnx`，运行时只用 `onnxruntime`；`tha3_engine.py` 已对 `onnx` 做模块 stub，**不要** `pip install onnx`。

## 推荐安装顺序

### 仅 THA4 Student

```bat
experiments\puppeteer_load_preview\deps\install_tha4_student_deps.bat
```

### 需要 THA3（ONNX + DirectML）

```bat
experiments\puppeteer_load_preview\deps\install_tha3_ort_deps.bat
```

### 两种模式都要

```bat
experiments\puppeteer_load_preview\deps\install_all_image_source_deps.bat
```

### 校验

```bat
cd /d E:\THA4_bundle_bai_custom\talking-head-anime-4-demo
set PYTHONPATH=%cd%\src
venv\Scripts\python.exe ..\experiments\puppeteer_load_preview\deps\check_image_source_deps.py --mode all
```

## 误装 `onnx` 后的修复

若 `run_load_preview_runtime.log` 出现 `MessageFactory` / `FaceLandmarker.create_from_options` 相关 TypeError：

```bat
experiments\puppeteer_load_preview\deps\repair_mediapipe_protobuf.bat
```

然后重新运行 `install_tha3_ort_deps.bat`（只补 ORT，不再装 onnx）。
