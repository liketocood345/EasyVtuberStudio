# 改动列表 / Change Log

相对于 THA4 原版 `character_model_mediapipe_puppeteer.py`（固定 `VideoCapture(0)`、无视频源选择、单窗口布局）。

**活跃开发：** `E:\tha4fork-develop\`  
**EasyVtuberStudio 发布总库根目录：** 对外发布总库（文档权威副本）  
**代码包历史快照：** `face-puppeteer-ui-enhancements-ai-code/his/`

---

---

## 2026-05-29

| # | 改动 |
|---|------|
| M1 | **Mouse + Audio 面捕（EasyVtuber 风格）**：Model Input 可选 `mouse_audio`；`mouse_mocap_driver.py` 合成 `MediaPipeFacePose`（全屏鼠标 → 头/眼，麦克风口型，程序化眨眼） |
| M2 | 修复鼠标模式下眼球水平转向与头部朝向相反的问题 |
| M3 | 持久化 `mocap_input_mode`；`smoke_mouse_mocap.py` 无 GUI 回归 |

---

## 2026-05-31

| # | 改动 |
|---|------|
| R1 | GitHub 仓库更名为 **`liketocood345/EasyVtuberStudio`**（曾用名 `EasyVtuber-with-THA3-THA4`）；文档与 `origin` 远程 URL 已对齐 |
| R2 | 全部项目 Markdown 文档统一软件名称为 **EasyVtuberStudio** |
| D1 | **DEPLOY 四档 Y/N**：`[1] basic_run` → `workspace/student_venv`；`[2] face_puppeteer`；`[3] tha3_models`；`[4] tha4_training` |
| D2 | 修复「已装 [1] 再装 [2]」：`SkipTorchInstall` 仍跑 requirements pip；复制 venv 后用 **`python -m pip`** 与 **`venv --upgrade`** |
| D3 | 面捕运行时：`MOCAP_INPUT_MODE_MEDIAPIPE` 导入缺失导致切换面捕崩溃 |
| D4 | `verify_deploy.ps1` 增加面捕 UI probe；文档 tier 编号统一 |

---

## 当前版本（fork 根目录，2026-05-29）

### 视频源与显示（2026-05-29）

| # | 改动 |
|---|------|
| W1 | **窗口捕获**视频源：OBS 式抓取 DroidCam 预览窗；与摄像头共用下拉；记忆窗口；**加载模型后**自动连接时优先窗口捕获 |
| W2 | **输出动态增强校准**：刷新缩放基准 + 水平归中（不改垂直基准）；开启自动移动缩放时平滑过渡 |
| W3 | THA3 变体与「标定朝向」分子面板，缓解窄侧栏重叠 |
| W4 | 音频驱动嘴型界面注明「有少量延时」 |
| W5 | 移除调试脚手架（`agent_debug` 等） |
| W6 | **默认启动完整调参窗**（`startup_show_full_controls`）；精简小窗改为可选（3 快捷校准按钮 + 打开完整窗） |
| W7 | 启动时不自动连视频源；**加载模型后**再 `refresh_and_autoload`（窗口捕获优先） |

---

## 当前版本（fork 根目录，2026-05-28 同步）

### 启动与窗口 / Launcher

| # | 改动 |
|---|------|
| 1 | （2026-05-28 及更早）紧凑启动窗：3 按钮 + 提示；**2026-05-29 起默认改为完整调参窗**（见上方 W6） |
| 2 | 完整调参窗 `ControlsFrame` **懒加载**，首次点击「Open Full Controls」才创建 |
| 3 | 紧凑窗 ↔ 完整窗可切换（`show_compact_launcher` / `show_full_controls_window`） |
| 4 | 未创建完整 UI 前用 `ValueState` / `SelectionState` 保证逻辑可运行（headless-safe） |
| 5 | 启动默认打开完整大窗并自适应尺寸（实验版 `load_preview`） |

### 模型加载 / Model

| # | 改动 |
|---|------|
| 6 | 加载模型后**立即**渲染默认中性位预览（无需摄像头） |
| 7 | 无脸部输入时保留上一帧预览，不强制回到 `Nothing yet!` |
| 8 | `Load Last Model` / `Load Other Model`，无效路径警告 |
| 9 | 未加载模型时可锁定交互控件（实验版；camfix 分支已取消锁定以便测摄像头） |

### 输出与显示变换 / Output & transform

| # | 改动 |
|---|------|
| 10 | 角色输出拆到**独立无边框输出窗**，记忆位置与大小 |
| 11 | 输出窗画布可拖动移动 |
| 12 | 人脸跟踪驱动自动平移/缩放（可开关） |
| 13 | 非线性缩放曲线 + 曲线预览区 + 峰位横移 + 当前点状态 |
| 14 | 倾斜驱动显示旋转、反转开关、负上限削弱模型 roll、倾斜补偿 |
| 15 | 镜像作为**最后独立步骤**，不影响倾斜语义 |
| 16 | 可调后处理抗锯齿 |
| 17 | 控件分栏：模型传入 / 输出动态增强 / 后处理 |
| 18 | 竖直滑块、横向三行布局等 UI 排版调整 |

### 持久化 / Persistence

| # | 改动 |
|---|------|
| 19 | 开关、双自动校准周期、背景、镜像、输出窗几何、上次模型路径等写入 `load_preview_ui_state.json` |
| 20 | **滑块记忆**：动态输出/后处理滑块写入 `display_transform_settings`（位移增益、缩放、曲线、抗锯齿等） |
| 21 | 分割条位置记忆 |
| 22 | **张嘴控制**：模式（面捕/声音）、面捕/声音嘴部参数、转换参数、虹膜大小等写入 `mouth_settings` |
| 23 | 再次打开完整控制窗时从磁盘重载嘴部与显示变换滑块状态 |

### 呼吸与嘴部 / Breathing & mouth（`mediapipe_face_pose_converter_00.py`）

| # | 改动 |
|---|------|
| 24 | 呼吸控件与反应式呼吸逻辑 |
| 25 | 嘴部输入：人脸 capture / 音频驱动切换 |
| 26 | 音频设备选择、平滑参数；OBS 风格横向音量条（绿/黄/红分区 + 峰值保持） |
| 27 | 音频状态显示实际设备名（`设备 / Device: ...`） |
| 28 | 呼吸区与嘴部区样式统一；`set_panel_enabled` 修正为启用 `breathing_panel` |
| 29 | 转换参数滑块与虹膜调整变更时自动触发状态保存 |

### 摄像头与视频源（实验版主脚本）

| # | 改动 |
|---|------|
| 30 | 视频来源下拉 + 刷新 + 状态（独立列，避免挤压） |
| 31 | DirectShow 设备名枚举（`pygrabber` / ffmpeg 列表 / WMI 回退） |
| 32 | 多索引探测（0–19）、多后端（DSHOW / MSMF） |
| 33 | DroidCam 项优先 MSMF，避免 DSHOW 回退导致闪退 |
| 34 | 后台线程打开摄像头，减少 UI 卡死 |
| 35 | MJPG/YUY2、分辨率尝试、帧有效性检查、预览 `SetData` |
| 36 | 支持视频文件/图片文件源（多格式 wildcard） |
| 37 | 预览/UI 刷新节流，降低卡顿 |

### 调查结论（不写入主程序逻辑）

| # | 结论 |
|---|------|
| A | **DroidCam 无画面/选源闪退**：隔离测试表明主要为 **DroidCam 客户端/虚拟摄像头配置** 问题，不单是 THA4 UI；摘要见 [docs/camfix/CAMERA_CHANGES_SUMMARY.md](docs/camfix/CAMERA_CHANGES_SUMMARY.md) |
| B | 本机 OpenCV 对 DroidCam 用 `CAP_DSHOW`+索引易异常；MSMF 更安全；**推荐窗口捕获**绕行 |
| C | camfix 历史脚本已归档；当前优先 **窗口捕获** + 本文档第二节 |

---

## 历史快照 `his/2026-05-27/`

该目录保存 **fork 首次打包草稿**（重组前的根目录副本），改动列表与上表「2026-05-28 同步」在打包时基本一致，但未包含此后在 develop 上继续做的摄像头细化与 camfix 调查文档。

详见同目录下旧版 `README.md`、`HANDOVER.md`。

---

## 涉及文件

| 文件 | 说明 |
|------|------|
| `experiments/puppeteer_load_preview/character_model_mediapipe_puppeteer_load_preview.py` | 主 UI |
| `talking-head-anime-4-demo/src/tha4/mocap/mediapipe_face_pose_converter_00.py` | 呼吸/嘴部/音频 |
| `packaged/bai_450k/` | 示例模型包（face 0010 / body 0045） |

---

## 后续归档约定

每次备份将 **`face-puppeteer-ui-enhancements-ai-code/`** 内容移入 **`his/yyyy-MM-dd_HH-mm-ss/`**（本地时间，精确到秒）。develop → fork 手动合并；流程见 [BACKUP.md](BACKUP.md)；可运行 `face-puppeteer-ui-enhancements-ai-code\archive_to_his.ps1`。

旧目录 `his/2026-05-27/` 为仅日期命名的首份快照，之后归档一律带时分秒。
