# EasyVtuberStudio — 排障与常见误解 Q&A / Troubleshooting FAQ

基于 EasyVtuberStudio 面捕增强版、camfix 隔离测试与排障经历整理。  
**文档权威副本（本文件）：** `E:\easyvtuberstudio-main\` · **活跃代码开发：** `E:\easyvtuberstudio-develop\`（稳定后合并到 fork 再 push）。

相关文档：[HARDWARE_REQUIREMENTS.md](HARDWARE_REQUIREMENTS.md) · [BACKUP.md](BACKUP.md) · [CHANGELOG.md](CHANGELOG.md) · [DOC_INDEX.md](DOC_INDEX.md)

---

## 置顶问题（先看这个）

### 我使用了 DroidCam，那我这辈子是不是完蛋了？

**A：** 是的，EasyVtuberStudio 作者也使用了 doridcam，并浪费了自己的人生。早点把这个卸掉吧，搞个正经摄像头。

向 DroidCam 致以诚挚问候：虚拟摄像头流异常、占位画面、比例撒谎、关不干净——**害人不浅**。THA4 **不再**为这类不正常视频流做兼容补丁；若你暂时只能用 DroidCam 把手机当摄像头，请用下文 **窗口捕获** 抓 **DroidCam 电脑端预览窗**，不要死磕「DroidCam Video」虚拟摄像头项。

---

## 一、启动、路径与版本

### Q1：双击桌面快捷方式，改的是 fork 还是 develop？

**A：** 以快捷方式目标为准。

| 常见目标 | 含义 |
|----------|------|
| `E:\easyvtuberstudio-main\scripts\launch\run_load_preview_puppeteer.bat` 或根目录 **EasyVtuberStudio.exe** | **发布总库**（定制客户部署、GitHub 推送） |
| `E:\easyvtuberstudio-develop\scripts\launch\run_load_preview_puppeteer.bat` | **研发主仓**（日常改代码） |

两者脚本路径、`PYTHONPATH` 不同，**不要混用**后抱怨「改了代码没生效」。~~`E:\THA4_bundle_bai_custom`~~ 已废弃。

---

### Q2：我改了 fork 里的代码，为什么运行 develop 没变化（或反过来）？

**A：** fork 与 develop 是两套目录。日常开发在 **`E:\easyvtuberstudio-develop`**；稳定后手动合并到 **`E:\easyvtuberstudio-main`** 再 push。只改其中一侧不会自动同步到另一侧。

---

### Q3：启动黑窗闪退，日志在哪？

**A：** 看 bat 里 `LOG_FILE`。常见位置：

- **fork：** `E:\easyvtuberstudio-main\face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\run_load_preview_runtime.log`
- **develop：** `E:\easyvtuberstudio-develop\face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\run_load_preview_runtime.log`

先查 **CUDA / 模型路径 / MediaPipe .task 是否存在**。

---

### Q3b：fork 瘦包反复弹「无法初始化 MediaPipe 面捕」？

**A：** 旧版 bug：持久化为面捕模式 + capture 定时器每 66ms 重试并弹窗。新版行为：

1. 未装 `face_puppeteer` 时启动即回退 **Mouse + Audio**
2. 定时器路径不再弹窗；仅用户手动切面捕时提示一次（经 `ui_dialog_guard` 限频）
3. 若仍异常，删除或编辑 `workspace/load_preview_ui_state.json` 中 `"mocap_input_mode": "mouse_audio"`

详见 [UI_DIALOG_SAFETY.md](UI_DIALOG_SAFETY.md)。

---

### Q3c：`f-057` 说的「启动 ≤10 秒」到底量什么？

**A：** 只量 **主 UI 界面壳就绪**（控制窗 + 输出窗可见、控件可点），**不含**：

| 不计入 10s | 说明 |
|------------|------|
| THA4/THA3 **模型加载** | Load Last、启动后自动加载、首帧 pose 渲染 |
| **面捕子系统** | MediaPipe 创建、摄像头/窗口捕获连接、`face_puppeteer` 初始化 |
| **图层系统** | 图层状态还原、资源读盘、首次 compose |

以上可在 UI 就绪后继续，但须 **异步/按需**，不得卡住首屏。验收以 **控制窗 + 输出窗可见、控件可点** 为准（主 UI 壳 ≤10s）；不再依赖 `debug-3353ed.log` 埋点。TRT 编译、NN 权重首次加载等属 **慢任务（≤10min + 进度 ETA）**，与主 UI 10s 为两条独立预算。详见 `e:\record\easyvtuberstudio条目设计手册.md` **`f-057`**。

---

### Q4：提示找不到 CUDA 或 `cuda:0` 报错？

**A：** 脚本默认 **`torch.device("cuda:0")`**，需要 NVIDIA 显卡与 CUDA 版 PyTorch。无独显时需改代码改 CPU，**通常无法实时面捕**，属环境限制而非 UI bug。

---

### Q5：Python 运行环境在哪？

**A：** 相对**当前仓库根**解析，按优先级：

| 场景 | 路径 |
|------|------|
| 三模块全装 / 面捕 | `addons\face_puppeteer\venv\Scripts\python.exe` |
| 同上（联接） | `runtime\venv\Scripts\python.exe` → 指向上者 |
| 瘦包 Mouse+Audio 首次启动后 | `workspace\student_venv\Scripts\python.exe` |

`scripts\launch\_resolve_portable_python.bat` 与 `portable_paths.py` 使用上述顺序。**不再**使用仓库根 `venv\` 或 `talking-head-anime-4-demo\venv\`（已废弃）。

`PYTHONPATH` 指向该 demo 的 `src`。依赖安装见 **`DEPLOY.bat`**（推荐）或 `deps\pip\install_all_image_source_deps.bat`。

---

## 一点五、DEPLOY 与可选包

> **新手先看下面三条**，再查后面的档位说明与技术向 Q&A。

### Q5e：安装时终端提示「源失效」「无法下载」或一片红字，是不是坏了？

**A：** **不一定。** DEPLOY 会跑很久的 `pip install` 和大文件下载，PowerShell 里经常出现：

- 黄色 / 白色的 `[notice] A new release of pip is available…`（只是 pip 升级提示，**可忽略**）
- 红色的 stderr 行（pip 把进度也写到 stderr，**不等于失败**）
- 连续的英文：`Collecting …`、`Downloading …`、`Installing collected packages`、`Requirement already satisfied`

**怎么判断还在正常跑：**

1. **还在不断刷新的英文字符** → 多半在正常下载/安装，**不要马上关窗口**。
2. **长时间停住不动**（例如 5 分钟以上完全没有新行）→ 可能是网络卡住，再看 `workspace\deploy.log`。
3. 最后出现 **`DEPLOY complete.`** → 成功；出现 **`DEPLOY failed:`** 并退出 → 才是真的失败。

**真正「源失效 / 无法下载」** 时，日志里会有明确的 HTTP/404/超时，且脚本会停住并写进 `workspace\deploy.log`。首次安装请预留 **10–40 分钟** 并保持联网。详见 [DEPLOY.md](DEPLOY.md)。

---

### Q5f：解压后为什么不能直接启动？一定要 DEPLOY 吗？

**A：** **GitHub ZIP（CORE）里不带 Python 运行时。** 解压后只有程序、代码和示例角色，还没有 PyTorch、wx 等运行库。

- 双击 **`EasyVtuberStudio.exe`**：若本机**尚未**装好基础环境，会提示你去运行 **`DEPLOY.bat`**，**不会**在后台偷偷自动下载（避免误装、占磁盘）。
- **至少**要在 DEPLOY 里安装档位 **[1] basic_run**（直接按 Enter 默认即可），装完 `workspace\student_venv` 后才能正常启动 **Mouse + THA4 Student** 模式。

若你以前在本目录已经装过、或系统 Python 已能 `import torch, wx`，exe 也可能直接启动——**新机器 / 新解压目录** 一般都要先 DEPLOY 一次。

---

### Q5g：为什么不让我用面捕（摄像头）？

**A：** **摄像头面捕是独立可选模块**，不包含在默认的 **[1] basic_run** 里。

| 模式 | 需要安装 |
|------|----------|
| **Mouse + Audio**（鼠标+麦克风口型，无摄像头） | 仅 **[1] basic_run** |
| **Face capture (OpenSeeFace)**（facetracker 独立采摄像头） | **[2] openseeface** |
| **Face capture (MediaPipe)**（EVS 窗口/摄像头 + MediaPipe） | **[3] face_puppeteer** |

**[2] 与 [3] 二选一即可** 使用摄像头面捕。未装对应档位时，软件会提示运行 **`DEPLOY.bat`**，或继续使用 **Mouse + Audio**。

---

### Q5g-osf：OpenSeeFace 模式下左侧预览黑屏？

**A：** OpenSeeFace 面捕由 `facetracker.exe` 自己打开摄像头；左侧小窗通过 **窗口捕获** 镜像 **`OpenSeeFace Visualization`** 窗口（需 `-v≥1`，EVS 默认 `-v 3`）。

1. 确认 **DEPLOY [2] openseeface** 已装且面捕模式为 **OpenSeeFace**  
2. 若仅有状态文字、无画面：等 15s 内窗口出现；仍无则查看是否被安全软件拦截 `facetracker.exe`  
3. UDP 面捕与预览独立：UDP 正常时角色仍会动，即使预览暂时黑屏

---

### Q5g-osf-blink：OpenSeeFace 有时眨不上眼 / 快眨眼没反应？

**结论：属实，且为性能与功能的已知取舍，不算 bug。**

**原因（与代码一致）：**

| 因素 | 典型值 | 说明 |
|------|--------|------|
| OSF 默认追踪帧率 | **12 fps**（`OSF_DEFAULT_FPS`） | 约每 **83 ms** 一帧 UDP 姿态 |
| 人眼单次眨眼时长 | 约 **100–250 ms** | 快眨眼闭合峰可能窄于采样间隔 |
| 输入 pacer | `OpenSeeFaceInputPacer` | 按 `osf_fps` 均匀出帧；`push_latest` 仅保留最新包，中间帧可合并丢失 |
| 采集定时器 | `CAPTURE_PROCESS_INTERVAL_MS = 66` | 面捕面板约 **15 Hz** 驱动 pacing，与 OSF 帧率共同限制时间分辨率 |

当眨眼快于面捕有效采样率时，闭合峰值可能落在两帧之间，角色侧看不到完整闭眼——这是 **低帧率换低 CPU/稳定** 的预期结果，不是映射错误或程序故障。

**不算 bug 的边界：**

- 偶发、快眨眼漏掉 → **正常取舍**
- 持续闭眼/慢眨仍无反应 → 查眼皮 AU、瞳孔门控或校准（见眼部动作梳理）；或提高 FPS 后再试

**可缓解（仍属取舍）：**

1. Model Input → OpenSeeFace → **FPS** 提高到 **24–30**（`clamp_osf_fps` 上限 60；越高 CPU 与 facetracker 负载越大）
2. 需要可靠眨眼展示时，用 **Mouse + Audio** 模式的程序化眨眼，或放慢眨眼幅度/时长
3. 不要为「必捕每一次快眨」单独加 bug 单——除非在提高 FPS 后仍 **稳定** 复现同一输入无输出

**2026-06-18 补充（单眼 wink 丢失修复）：**

- **根因**：`OSF_EYE_ACTIVE_THRESHOLD` 过高（0.32）使轻 wink 被判为 `open`；`refine_osf_eye_motion_temporal` 曾把非对称闭眼合并为 `blink_both`；pacer 线性插值 + 低 fps 抹掉峰值。  
- **已修**：先判左右不对称再判双眼；wink 不参与双眼时序合并；眨眼 blendshape **hold**（wink 0.20s / blink 0.11s）；pacer lerp 对 `eyeBlinkLeft/Right` 取 **max**；OSF 推理在眼/头变化时立即触发。  
- 极快眨仍可能漏（见上表取舍）；**刻意单眼 wink** 应可再现。

---

### Q5a：DEPLOY 六档分别装什么？

**A：**

| 档位 | 内容 |
|------|------|
| **[1] basic_run** | `workspace\student_venv`（torch + wx + matplotlib），够 **Mouse + Audio** |
| **[2] openseeface** | `addons\openseeface\Binary\facetracker.exe` + models |
| **[3] face_puppeteer** | `addons\face_puppeteer\venv` + MediaPipe `.task` |
| **[4] tha3_models** | THA3 立绘 `.pt` |
| **[5] tha4_training** | Teacher 权重 + pose 数据集 |
| **[6] output_enhancement** | onnxruntime + pyanime4k；从 HF Bucket 拉取 `data/ezvtb_nn/` ONNX |

详见 [DEPLOY.md](DEPLOY.md)、[ADDONS_LAYOUT.md](ADDONS_LAYOUT.md)。

---

### Q5g：后处理 NN 超分 / RIFE 灰色或提示缺 [5]？

**A：** 后处理 **SuperResolution (NN)** / **Frame Interpolation (NN)** 需 **DEPLOY [5] output_enhancement**。

- **从 GitHub 瘦包安装：** CORE **不含** `data\ezvtb_nn\` ONNX；档位 [5] 装 pip 并从 HF Bucket（`liketocode789/EasyVtuberStudio`）拉取到 `addons\output_enhancement\ezvtb_data\`（失败回退 Google Drive 导入脚本）。  
- **从 HF Bucket 整目录同步：** 桶内已含 `data\ezvtb_nn\`，装 [5] 时主要补 pip 包。

启用 NN 后请将 **NN 推理后端** 设为 **ONNX Runtime** 或 **TensorRT**。详见 [HF_BUCKET_MIRROR.md](HF_BUCKET_MIRROR.md)、[DEPLOY.md](DEPLOY.md)。

---

### Q5i：不想用 GitHub ZIP，能直接从 HF 下载完整项目吗？

**A：** 可以。公开 Bucket：https://huggingface.co/buckets/liketocode789/EasyVtuberStudio  

```powershell
pip install -U huggingface_hub
python -m huggingface_hub.cli.hf buckets sync hf://buckets/liketocode789/EasyVtuberStudio D:\EasyVtuberStudio
```

进入目录后运行 **`DEPLOY.bat`** 与 **`EasyVtuberStudio.exe`**，流程与 GitHub 版相同；桶内已带 NN ONNX。桶首页 README 有完整说明。

---

### Q5h：TensorRT 编译很慢？

**A：** 首次选 **TensorRT** 后端时会编译 SR/RIFE 引擎，缓存于 `workspace\ezvtb_engines\`；进度条会提示「一次性，下次秒开」。编译失败会回退 ONNX Runtime 并写入 `workspace\deploy.log`。无 NVIDIA / 无 tensorrt wheel 时请用 **ONNX Runtime** 后端。

---

### Q5b：已装 [1] basic_run，再勾选 [2] 面捕，DEPLOY 失败？

**A：** 旧版 bug：从 `student_venv` 复制到 `face_puppeteer\venv` 后，`pip.exe` 仍指向 student 路径，mediapipe 装错位置。新版 `bootstrap_portable.ps1` 使用 **`python -m pip`** 并在复制后 **`python -m venv --upgrade`**。查看 `workspace\deploy.log` 中 `Runtime verification failed (torch / wx / mediapipe)` 一行。

---

### Q5c：DEPLOY 显示成功，但切换面捕模式闪退 / NameError？

**A：** 2026-05-31 前 CORE 曾缺 `MOCAP_INPUT_MODE_MEDIAPIPE` 导入。更新仓库或重新下载 ZIP。日志见 `workspace\launch.log`。

---

### Q5d：安装日志在哪？

**A：**

| 文件 | 内容 |
|------|------|
| `workspace\deploy.log` | DEPLOY 步骤与 pip 失败 |
| `workspace\launch.log` | `EasyVtuberStudio.exe` 启动与子进程 stderr |

---

## 二、摄像头与视频源

### 为什么有「窗口捕获」作为视频输入？

**A：** 这是为 **DroidCam 等虚拟摄像头软件** 准备的**绕行方案**，不是 THA4 的主线功能设计。

实测常见情况：

- **DroidCam 客户端预览正常**，但 **「DroidCam Video」虚拟摄像头** 给 OpenCV/THA4 的是占位画面（如 Start DroidCam）、黑帧、错误比例或时好时坏的流；
- 在 OBS 里虚拟源也可能变形——问题在 **DroidCam → 虚拟摄像头** 这一截，不是面捕 UI 单独坏了。

因此：

1. **项目不再**为「不正常虚拟摄像头流」增加兼容逻辑（不替 DroidCam 擦屁股）；
2. 增加 **窗口捕获**：直接抓取 **DroidCam 预览窗口** 的客户区画面，与你在客户端里看到的画面一致；
3. **会记忆上次捕获的窗口**（`load_preview_ui_state.json` 里的 `window_capture_hwnd` / `window_capture_title`）；在 **Load Other / Load Last 加载模型**（或 THA3 **加载上次立绘**）时会刷新列表并 **优先连接窗口捕获**，其次摄像头。

**推荐操作（fork / develop 相同）：**

1. 打开 DroidCam，确认 **电脑端预览窗** 已是手机画面；
2. 在 THA4 视频源区点 **「选择窗口捕获 / Pick Window Capture」**，选中 **DroidCam** 预览窗；
3. 需要彻底退出 DroidCam 用户态进程时，可用 `E:\doridcam-oprate\Stop-DroidCam.bat` / `Start-DroidCam.bat`（见下文「关掉 DroidCam…」）。

下拉列表第一项通常为 **「窗口捕获 / Window: …」**；摄像头仍可通过「刷新设备列表」使用，但 **不推荐** 再优先选 DroidCam 虚拟摄像头。

---

### 关掉 DroidCam 托盘/窗口后，进程或虚拟摄像头还在？

**A：** 常见。托盘退出 ≠ 完全退出，可能残留 `adb` 与内核驱动 `droidvcam0_v` / `droidvcam0_a`。**双击**（纯 CMD，不依赖 PowerShell）：

- `E:\doridcam-oprate\Stop-DroidCam.bat`
- `E:\doridcam-oprate\Start-DroidCam.bat`

停脚本后设备列表里仍可能有 DroidCam 项 → 重启或设备管理器禁用虚拟摄像头；THA4 内 **刷新设备列表** 后再选源。

---

### DroidCam 连不上、无画面、WiFi 一直卡住——只重启电脑够吗？

**A：** **不够。** 实测：电脑端进程在跑、驱动也在，但 WiFi 模式下手机 IP  ping 不通、TCP **4747** 握手卡在 SynSent、`adb devices` 为空——**重启手机后才恢复**。

彻底重置 DroidCam 时，**电脑端和手机端都要「硬重启」**，不能只做托盘退出或划掉 App：

1. **电脑端**：`E:\doridcam-oprate\Stop-DroidCam.bat` → 确认 `droidcam` / `adb` 已退出；仍异常则 **重启电脑**，再 `Start-DroidCam`。
2. **手机端**：划掉 DroidCam 或断 WiFi **往往不够**——需要 **完全重启手机**（关机再开），再打开 DroidCam App 重新连接。
3. 两侧都重启后，在 THA4 里 **刷新设备列表** 或重选 **窗口捕获**。

---

### 设备列表里没有 DroidCam？

**A：** 先 **打开 DroidCam 客户端**（手机端 + PC 端），再点「刷新设备列表」。未启动时 DirectShow/WMI 可能列不出虚拟摄像头。建议安装 **`pygrabber`**（在 THA4 venv 内）以获取 DirectShow 名称列表。

---

### Q7：选 DroidCam 后程序闪退或卡死？

**A：** 实测上 **OpenCV `CAP_DSHOW` + DroidCam 索引** 易异常；实验版对名称含 `droidcam` 的项 **优先 MSMF、避免 DSHOW 回退**，并在子线程打开摄像头减轻 UI 冻结。若仍闪退：更新 DroidCam、换 USB/WiFi 模式，或改用 **窗口捕获**（第二节）。历史 camfix 结论见 [docs/camfix/CAMERA_CHANGES_SUMMARY.md](docs/camfix/CAMERA_CHANGES_SUMMARY.md)。

---

### Q8：有画面但是雪花、花屏、全绿？

**A：** 多为 **错误分辨率/像素格式** 或虚拟摄像头未就绪。camfix/实验版会试 MJPG/YUY2、640×480。若 camfix 也花屏 → 优先查 **DroidCam/OBS 虚拟摄像头配置与驱动**，不一定是 THA4 UI。

---

### Q9：选 DroidCam 却显示 OBS 或其它设备的画面？

**A：** **pygrabber 列表索引 ≠ OpenCV 索引**，不能单靠数字对齐。用 **设备名称** 匹配；列表里选带 `DroidCam` 字样的项。隔离测试结论：无画面/错设备 **经常是虚拟摄像头软件问题**，不单是 puppeteer。

---

### Q10：摄像头预览黑屏，但状态写「已连接」？

**A：** 可能 **已打开但读帧无效**（实验版会提示 invalid frame）。点刷新、换后端、降分辨率；DroidCam 重连手机端。若仍无帧，见上条 **「只重启电脑够吗」**——**手机也需完全重启**。

---

### Q11：camfix 正常，实验版不正常，说明什么？

**A：** 按 camfix 设计：**摄像头链路 OK**，问题更可能在实验版的 **非摄像头功能**（双窗、自动平移缩放、输出合成、抗锯齿等）。逐项关闭自动变换、AA=1.0 排查。

---

### Q12：camfix 也不正常，说明什么？

**A：** 优先查 **DroidCam/驱动/OpenCV 后端**；THA4 原版 `VideoCapture(0)` 也可能同样失败。

---

## 三、模型加载与画面预览

### Q13：加载模型后仍显示 `Nothing yet!`？

**A：** **EasyVtuberStudio 面捕增强版** 应在加载后 **立即显示默认中性 pose**；无脸时 **保留上一帧** 而非清空。若仍出现 `Nothing yet!`：确认运行的是 **EasyVtuberStudio**（`EasyVtuberStudio.exe` 或 `scripts\launch\run_load_preview_puppeteer.bat`），不是原版 `character_model_mediapipe_puppeteer.py`。

---

### Q14：「加载上次模型」无效或弹路径失效？

**A：** 路径记在 `workspace/load_preview_ui_state.json`（首选；旧版可能在 `experiments/puppeteer_load_preview/` 下）。移动/删除模型包后会提示重选，**属正常**。用「加载其他模型」重新指定 `character_model.yaml`。

---

### Q15：没开摄像头，立绘会动吗？

**A：** 加载模型后有 **默认 pose 静态预览**；实时表情需摄像头或视频源 + MediaPipe 检测到脸。无人脸时 head 数值可能不变，**正常**。

---

### Q15b：为什么耳朵不会动？

**A：** 原作者 **没有设计 AI 绘画动耳** 功能（THA 管线里没有对应的耳朵 blendshape / 姿态通道）。若需要会动的耳朵，可考虑使用 **图层系统**（例如单独准备耳朵/耳饰贴图图层，随头转或自行编排动画）。

---

### Q15c：为什么转头时嘴容易变形？

**A：** THA 原作者的模型是 **按人类面部比例** 训练的，对 **长嘴筒子**（兽设吻部、鸟喙等）兼容很差；头转时 morpher 按「人嘴」做网格变形，吻部越长越容易拉花、抿嘴或穿模。这不是面捕滑块能彻底修好的问题。建议换用 **自己角色的 Q 版立绘** 等 **吻部较短、更接近人脸** 的形象；或接受写实全身立绘在转头时嘴部略假，用图层/后期遮挡弱化。

---

### Q16：输出窗有角色，主窗预览很小或布局挤在一起？

**A：** 增强版曾调整 **三栏/视频源独立列**；过窄时拖动分割条或放大「完整调参窗」。右侧控件过多时用窗口滚动条。

---

### Q16b：图层快捷键按了没反应？

> **🟡 部分可用·待验收（2026-06-18）**：2026-06-18 已修热键回调错误参数名。**2026-06-18 起已移除全部「按住」类快捷键**（曾导致按住卡死、掉帧）；旧 `hold_to_*` 绑定加载时自动迁移。

**A：** 须先勾选后处理 **「启用图层混合 / Enable Layer Blending」**，并勾选 **「启用图层快捷键 / Enable Layer Hotkeys」**（默认关）。在图层系统窗口选中图层 → 详情区快捷键 → **+ 添加快捷键** → 选动作 → **录制 / Capture** 键位。GIF 图层可用：播一次、**显示播一次后隐藏**、循环、停止。非 GIF 图层可用 **显隐切换**。若状态栏提示注册失败，换 `Ctrl+Alt+数字键` 等组合。

---

### Q16c：启用图层混合后图层窗/程序打不开？

**A：** 若曾加入图层热键后出现 **启动即崩** 或 **图层窗无法创建**，常见根因是 wxPython 4.2 **没有** `wx.HotKeyEvent` 类型名（`EVT_HOTKEY` 仍可用）；主脚本若用 `wx.HotKeyEvent` 作类型注解会导致 **整模块 import 失败**。已改为 `wx.Event`；图层窗也会在完整控件面板建完后再 `CallAfter` 打开。若仍失败，看 stderr 是否 `BasicLayerWindow create failed:` 并贴完整 Traceback。

---

### Q16d：按热键后帧率骤降或界面/面捕偶发卡死？

**A：**

1. **按住类热键（已移除，2026-06-18）**：`hold_to_hide` / `hold_to_show` / `hold_to_show_play_once` 会在 `WM_HOTKEY` 与每帧 `GetAsyncKeyState` 轮询之间叠加全量合成，导致按住期间 UI 卡死、掉帧；窗口捕获与摄像头/视频流面捕均可触发。已全部移除；旧绑定加载时自动迁移为切换显隐或「显示播一次后隐藏」。
2. **面捕队列堆积**：MediaPipe 与 THA 推理 worker 若每帧多次 `CallAfter`，主线程事件队列会胀满并表现为面捕卡顿。已改为 worker 内 **latest-wins**（每轮只投递一次 UI 回调）。
3. **切换动作闪退**：快捷键动作下拉切换时已 `CallAfter` 延迟重载，且重载时不再重建快捷键 UI。

---

## 四、窗口、UI 与操作

### Q17：启动只有三个按钮，其它控件哪去了？

**A：** 当前 **默认应直接打开完整调参窗**（`startup_show_full_controls`）。若只见 **精简小窗**（3 按钮：校正头部朝向、输出动态增强校准、打开完整调参窗），常见原因：

1. 你在完整窗内点了 **「切换到精简小窗 / Switch to Compact」**；  
2. 完整窗首次展示失败（少见），程序回退保留精简面板 — 点 **「Open Full Controls」** 重试。

加载 THA4 / THA3 模型、刷新视频源等操作 **只在完整调参窗** 进行。

---

### Q17b：为什么启动后摄像头没自动连上？

**A：** **设计如此。** 启动时不调用自动连源；在 **Load Other / Load Last 加载模型**（或 THA3 **加载上次立绘**）时会 `refresh_and_autoload_video_source()`，此时记忆的 **窗口捕获** 优先于摄像头。若尚未加载模型，请手动刷新设备列表或先 Load Other。

---

### Q18：切到完整窗后，采集还在跑吗？

**A：** **会。** 定时器与 MediaPipe/GPU 推理在紧凑窗时也在跑，只是部分控件尚未创建；用 `ValueState` 等占位保证逻辑不崩。

---

### Q19：为什么有两个（或更多）窗口？

**A：** 增强版将 **角色输出** 放到 **独立无边框输出窗**（可拖动），主窗/完整窗用于调参和摄像头预览。输出窗可单独给 OBS「窗口采集」。

---

### Q20：输出窗拖不动？

**A：** 应在 **输出图画布区域** 拖动；若只点到边框外无效。无边框窗需点击图像区域。

---

### Q21：未加载模型时控件是灰的？

**A：** 实验版可 **锁定未加载模型时的交互**（设计行为）。camfix **不锁定**，便于只测摄像头。若需 camfix 行为，用 camfix 脚本。

---

### Q22：滑块数值重启后没了，但开关还在？

**A：** 当前版本会记忆滑块：动态输出/后处理写入 `display_transform_settings`，模型输入栏（呼吸、嘴部、转换参数、虹膜等）写入 `mouth_settings`；三栏分割条比例写入 `main_splitter_sash_ratio` 等。若仍丢失，确认已正常退出程序（触发保存），且 `workspace/load_preview_ui_state.json` 可写、未被旧版覆盖。

---

### Q23：镜像开关切换后角色「卡住」不动？

**A：** 曾修复：镜像应作为 **最后独立步骤**，且切换时不应冻结。若旧版仍卡住，更新到 **develop 最新** 并合并到 fork。

---

### Q24：自动方向校准后角色倾斜卡在很大角度？

**A：** 曾修复：自动方向校准 **不应重置倾斜零点** 导致卡死。可手动「标定中性位」；关自动方向校准对比。

---

## 五、嘴部、音频与电平显示

### Q25：界面写「Open Response / Close Response」是什么？和「攻击」有关吗？

**A：** 对应音频包络 **Attack/Release**（张嘴变快/闭嘴变慢），**不是**「嘴在攻击」。参数名仍为 `audio_mouth_attack` / `audio_mouth_release`。

---

### Q26：声音张嘴没反应？

**A：** 检查：① 嘴型输入选 **Audio-Driven**；② `sounddevice` 可用；③ 麦克风是否被 OBS/快手占用；④ 调低 **Audio Threshold**、提高 **Max Input Level**；⑤ 内录需 **WASAPI**，且选 **System Audio (Loopback)**。

---

### Q27：内录提示 WASAPI / loopback 不可用？

**A：** 需要 Windows **默认输出设备走 WASAPI**；部分虚拟声卡不支持 loopback。可改用麦克风模式，或换 OBS 采集桌面音频。

---

### Q28：为什么看不到 OBS 那种横向电平条？

**A：** **OBS 风格电平条** 在 `mediapipe_face_pose_converter_00.py` 中实现（fork 与 develop 已同步）。若桌面快捷方式仍指向已废弃的 ~~`THA4_bundle_bai_custom`~~ 路径，界面可能不是当前版本。

---

### Q29：面捕模式下电平条/音频区还显示？

**A：** 面捕时音频面板可隐藏或显示「当前模式: Face tracking」；**不驱动嘴型** 为正常。

### Q29b：没有摄像头能用吗？Mouse + Audio 怎么用？

**A：** 可以。Model Input → **Mouse + Audio (EasyVtuber) / 鼠标+音频**：
- 无需连接摄像头或窗口捕获（视频源区会禁用）
- 移动**全屏**鼠标驱动头转与眼球；对着**麦克风**说话驱动口型
- 自动周期眨眼 + 内建呼吸；THA3 立绘模式同样生效
- 切回 **Face capture** 恢复摄像头面捕与原口型设置；模式保存在 `workspace/load_preview_ui_state.json`（`mocap_input_mode`）

---

### Q30：为什么我选了透明背景，导出/采集后看起来还是不透明？

**A：** 这通常不是单点 bug，而是和**图层（Layer）能力**有关：  
THA4 输出虽然可在本地显示透明背景选项，但最终是否“真透明”取决于后续链路是否支持 alpha 图层（例如窗口采集方式、虚拟摄像头格式、直播软件源设置、合成顺序）。  
如果后端链路不支持透明图层，就会被黑底/实色底替代，这是常见兼容性表现。

建议：
1. 在目标软件里确认该采集源支持 alpha/透明图层；  
2. 优先使用支持透明通道的窗口/源类型；  
3. 若链路不支持透明图层，改用纯色背景并在直播端做抠像键控（绿幕/蓝幕）。

**EasyVtuberStudio 专项（2026-06-13 起）：** 透明输出已统一为单一**分层窗（ULW，标题 `easyvtuberstudio_output`）**。  
- OBS 等请用 **「WGC / 游戏捕获」**（支持透明），**不要**用「窗口捕获(BitBlt)」——BitBlt **无法采集分层窗**，会得到黑/空画面；  
- 需 BitBlt 的工具改用背景下拉的 **「黑键」**档，并在直播端做 `#000000` 颜色键；  
- 背景下拉四档为「透明 / 自选纯色背景 / 自选图片 / 黑键」，背景均合成进同一 ULW。

---

## 六、性能、卡顿与显存

### Q31：文档写 12GB 显存，我是不是必须买 12GB 卡？

**A：** **不必。** 12GB 指 **THA4 + OBS + 快手等同开且开 NVENC/高抗锯齿** 的直播整机余量。仅 THA4、AA=1.0 时 **6–8GB 常可运行**。见 [HARDWARE_REQUIREMENTS.md](HARDWARE_REQUIREMENTS.md) 第 7–8 节。

---

### Q32：CUDA out of memory？

**A：** 优先：**抗锯齿 = 1.0**、缩小输出窗、关其它占 GPU 的软件。增强版 AA>1 会 **按倍率放大 GPU 渲染分辨率**。

---

### Q33：CPU 100% 但 GPU 不高？

**A：** **MediaPipe + OpenCV + 多窗 wx** 主要在 CPU；GPU 只在 `poser.pose` 时繁忙。降摄像头分辨率、关曲线频繁刷新、紧凑窗时仍会跑检测（CPU 仍占）。

---

### Q34：和 OBS 同开掉帧？

**A：** 同卡 **NVENC 与 CUDA 争用**。建议 THA4 AA=1.0、OBS 720p30、避免 THA4 与 OBS 抢同一麦克风/同一虚拟摄像头链。

---

## 七、Fork、备份与同步

### Q35：fork 和 develop 哪个是「正版」？

**A：** **`E:\easyvtuberstudio-develop` = 活跃研发**；**`E:\easyvtuberstudio-main` = 对外发布总库**。Markdown 说明以 **fork 的 `docs/`** 为准（本文件、[HANDOVER.md](HANDOVER.md)、[DOC_INDEX.md](DOC_INDEX.md)）；代码以你实际运行的 exe/bat 为准。

---

### Q36：如何备份 fork 代码包当前版本？

**A：** 见 [BACKUP.md](BACKUP.md)：在 `face-puppeteer-ui-enhancements-ai-code\` 运行 `archive_to_his.ps1`，内容移入 `his/yyyy-MM-dd_HH-mm-ss/`（秒级时间戳）。Git 提交前也可直接在 `E:\easyvtuberstudio-main` 做 `git commit`。

---

### Q37：如何从 develop 合并到 fork？`sync_from_bai_custom.ps1` 还有用吗？

**A：** **`sync_from_bai_custom.ps1` 已废弃**（仅打印提示）。当前流程：

1. 在 **`E:\easyvtuberstudio-develop`** 完成开发与自测；  
2. 将变更文件复制或 diff 合并到 **`E:\easyvtuberstudio-main`** 对应路径；  
3. 更新 fork 根目录文档（尤其本 Q&A、`README.md`）；  
4. `git add` → `commit` → `push origin main`。

**不会**因合并而自动覆盖的 fork 维护文档：`CHANGELOG.md`、`BACKUP.md`、本 `TROUBLESHOOTING_QA.md`（需手动同步内容）。

---

### Q38：程序打不开，能不能从历史版本直接拖出来覆盖路径？

**A：** 可以，这是最常用的应急恢复方式之一。  
从 `face-puppeteer-ui-enhancements-ai-code\his\` 里选一个最近可用快照，把对应文件/目录直接拖拽覆盖到目标路径即可。

建议操作：
1. 先确认当前运行目录是 **fork** 还是 **develop**；  
2. 在 `his/yyyy-MM-dd_HH-mm-ss/` 中找到对应时期版本；  
3. 优先覆盖出问题文件（主脚本、pose converter、启动 bat），避免一次性全量回滚；  
4. 覆盖前给当前文件改名备份（如 `.broken`），便于立即撤回。  

这个流程不依赖 git，适合“先恢复可运行，再慢慢定位”的场景。

---

## 八、可能被当成 Bug 的正常表现

以下 **多数为设计或环境现象**，不一定是程序错误。

| # | 现象 | 说明 |
|---|------|------|
| N1 | 启动时未自动打开摄像头 | 增强版可先显示 UI 再扫描设备；未选源前状态为「尚未连接」 |
| N2 | 精简小窗下无法加载「新」模型包 | 需 **完整调参窗** 使用 Load Other / Load Last THA4 Student |
| N3 | 无人脸时立绘不跟动 | 无 blendshape 输入时保持上次 pose 或默认 pose |
| N4 | 预览区写 `No face input` | 未检测到脸或摄像头未开，**不是**崩溃 |
| N5 | 曲线区「等待人脸」 | 自动缩放曲线需人脸数据后才显示当前点 |
| N6 | 输出窗与主窗内容略有差异 | 输出窗经 **平移/缩放/旋转/镜像/抗锯齿** 合成，与源预览不同属正常 |
| N7 | 负的「倾斜上限」时模型头动变小 | **设计**：负值削弱传给模型的 roll，非显示旋转 |
| N8 | 镜像只影响画面、不改变倾斜语义 | **设计**：镜像为最后独立步骤 |
| N9 | 呼吸 bpm 与动作状态跳动 | 反应式呼吸根据动作分数切换 BASE/TRIGGER/DECAY |
| N10 | 设备列表第一项是「窗口捕获 / Window: …」 | 记忆上次窗口并优先于摄像头；用于 DroidCam 预览窗绕行 |
| N10b | 设备列表里有「视频文件…」 | 增强版支持文件源，非误加入的摄像头 |
| N11 | 刷新设备时短暂卡顿 | 多索引/多后端探测在 CPU 上执行，属一次性开销 |
| N12 | 日志写在 .log 里终端不刷屏 | bat 将 stdout 重定向到日志文件 |
| N13 | 启动即弹出「完整大窗」 | **当前默认行为**（`startup_show_full_controls`），非异常 |
| N14 | 分割条位置下次还在 | 部分 splitter 位置会持久化 |
| N15 | 原版 puppeteer 无视频源下拉 | 原版仅 `VideoCapture(0)`，**不是**增强版回退 |
| N16 | camfix 无自动平移/双窗 | camfix **刻意省略** 非摄像头功能，用于对比 |
| N17 | 面捕时音频设备名仍显示 | 状态栏刷新逻辑可能显示设备信息，但不驱动嘴型 |
| N18 | GPU 占用周期性波动 | 约 30FPS 推理 + UI 刷新，波形正常 |
| N19 | 加载模型后 CPU 占用上升 | 模型与 MediaPipe 常驻，正常 |
| N20 | 12GB 写在文档但 8GB 卡能 solo 跑 | 12GB 针对 **多软件同开**，见硬件文档第 8 节 |

---

## 九、定制化部署：持久化与日常预期

本节面向**已交付的定制环境**：用户按培训流程正常使用即可，**不包括**反复狂点校准、快速切换源等压力式操作。下列为**已知现象与误解**，当前以文档说明为主，**暂不单独排期修复**。

### Q36：重启能解决所有界面/路径问题吗？

**A：** **不能。** 分两类：

- **重启通常有效**：当次会话里视频源切乱、窗口 capture 未释放、紧凑窗/完整窗切换后焦点错乱等「运行时状态」问题。
- **重启通常无效**：`load_preview_ui_state.json` **能正常读取**，但里面的 **模型路径 / THA3 立绘路径 / 输出窗坐标 / 上次窗口标题** 等已过期或指向别台机器目录——重启会**再次加载同一份 json**。

只有 **json 不存在、损坏无法解析** 时，才会退回程序内置默认（空记忆），相当于「像第一次打开」。

---

### Q37：为什么有「上次模型 / 上次立绘」，点 Load Last 却说路径无效？

**A：** 持久化记的是**上次成功保存时的路径字符串**，启动时**不会**逐个检查文件是否还在。

常见原因：

1. 模型文件被移动、删除，或换电脑后路径不存在；  
2. 曾在 **develop / 另一仓库目录** 下加载，json 里留下 **绝对路径**，在 fork 发布目录下无效；  
3. 相对路径是相对 **当前 fork 根目录** 解析的，模型实际只放在别的目录。

**正常处理：** 点一次 Load Last，程序会提示并**清空该条无效记忆**（THA4 / THA3 均如此）；或手动备份后删除 `workspace/load_preview_ui_state.json` 再启动。  
**不是** json 读失败——文件往往「读得挺好，只是里面的路径不对」。

---

### Q38：「上次窗口捕获: xxx」显示着，但预览连不上？

**A：** 记的是**窗口标题**（和 hwnd）；目标程序已关、窗口改名或尚未启动时，会**自动回退摄像头**或提示失效。标题行可能仍显示旧名字，直到你**重新选窗口捕获**并成功连接后才会更新。重启不能「修好」已关闭的第三方窗口。

---

### Q39：输出动态增强校准 / 标定朝向后，角色不是立刻回正？

**A：** 在开启 **「启用自动移动缩放」** 时，显示层会按 **Smoothing** 做**平滑过渡**（含左右归中、缩放与倾斜基准更新），**不是 bug**。若需立即到位，可暂时关闭自动移动缩放再校准，或等待数秒观察。定制培训中说明一次即可，**无需反复点击校准**。

---

### Q40：声音张嘴比说话慢半拍？

**A：** **正常现象。** 音频驱动嘴型经过设备缓冲与 Attack/Release 平滑；界面已注明「有少量延时」。调「张嘴速度 / 闭嘴速度」可略改善，无法做到零延时面捕同等响应。

---

### Q41：THA3 模式下后处理区控件挤在一起？

**A：** 右侧栏**过窄**时，长双语标签可能与下拉、按钮叠行。拉宽 **主分割条** 增加右侧宽度即可。**THA3 模型变体**下拉仍在后处理栏；**标定朝向 / 输出动态增强校准**已迁至预览行**最右侧校准列**（2026-06-04），不再占后处理垂直空间。极窄时后处理区仍可能显得紧，属布局限制而非功能失效。

---

### Q42：完整调参窗四边拖不动或只能缩小？

**A：** 若最小客户区宽度被设得过大（旧版曾 ≈2060px），在常见分辨率下会出现 **min≈max** 无法缩放。现行版 `CONTROLS_MIN_CLIENT_WIDTH` 约 **1124px**，四边应可拖动。若仍异常：确认运行的是 develop/main **2026-06-04 之后**构建；临时删除 json 中 `controls_frame_w/h` 后重启。

---

### Q43：窗口捕获用久了偶尔卡一下？

**A：** Win32 `PrintWindow` / BitBlt 在目标窗 GPU 合成或遮挡时可能**单次抓取耗时很长**；现行版已在 **后台 worker** 抓取（UI 只读缓存帧），并做：**抓取方式缓存**（稳定后不再每帧三连试）、**长边缩至 1280** 再面捕、**卡顿后换抓取路径**。若仍偶发：略缩小目标窗分辨率、避免捕获全屏游戏/OBS 预览等大窗；预览卡顿但输出仍动 → 多为面捕线程负载，可关完整窗摄像头预览或换较小捕获源。详见 [CHANGELOG.md](CHANGELOG.md) §2026-06-15 W1–W2。

---

### 日常场景速记（正常用法，非故障）

| 场景 | 预期 |
|------|------|
| 首次部署、未复制模型 | Load Last 不可用 → 用 Load Other 选 yaml / THA3 立绘 |
| 从 develop 拷 json 到 fork | 检查路径是否在本机 fork 内，否则删 json 或重选模型 |
| DroidCam：优先窗口捕获 | 虚拟摄像头项仍可能异常，见第二节 |
| 勾选「向外挂图层输出」 | 内置输出窗隐藏，属设计行为 |
| 换显示器 / 缩放比 | 输出窗若跑到屏外，拖回或删 json 里 `output_frame_*` 坐标 |

---

## 十、建议排障顺序（速查）

```text
1. 确认运行的 exe / bat 路径（fork 发布：根目录 `EasyVtuberStudio.exe` 或 `scripts\launch\run_load_preview_puppeteer.bat`）
2. 查 run_load_preview_runtime.log
3. 视频输入：优先「窗口捕获」抓 DroidCam 预览窗 → 再 camfix/摄像头列表；勿死磕 DroidCam 虚拟摄像头
4. 模型：能否 Load Other THA4 Student；yaml 与 .pt 是否完整；路径问题见第九节 Q37
5. 性能：AA=1.0、缩小输出窗、solo 运行 THA4
6. 音频：模式、阈值、是否被 OBS 占用
7. 对比原版 puppeteer：区分「增强功能」与「基础链路」问题
8. 路径/记忆异常：先尝试 Load Last 清无效项，或备份后删 load_preview_ui_state.json（见第九节）
```

---

## 十一、仍无法解决时建议收集的信息

- 运行的 **bat 完整路径** 与 `LOG_FILE` 末尾 50 行  
- GPU 型号、显存、是否同开 OBS/快手  
- 摄像头名称与是否 DroidCam  
- 实验版 / 原版 / camfix 哪一种可复现  
- `load_preview_ui_state.json` 是否损坏（可临时改名备份后删除试默认）

---

*文档版本：2026-07-25 · 含预览行校准列、分割条比例防抖持久化、窗口捕获、DroidCam 绕行、定制化持久化预期（第九节）、种子 UI 记忆随 CORE/HF 发布。活跃代码在 `E:\easyvtuberstudio-develop`；**本文档以 fork 根目录 `docs/` 为权威副本**。*
