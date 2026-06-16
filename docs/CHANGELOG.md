# 改动列表 / Change Log

相对于 THA4 原版 `character_model_mediapipe_puppeteer.py`（固定 `VideoCapture(0)`、无视频源选择、单窗口布局）。

**活跃开发：** `E:\easyvtuberstudio-develop\`  
**EasyVtuberStudio 发布总库根目录：** 对外发布总库（文档权威副本）  
**代码包历史快照：** `face-puppeteer-ui-enhancements-ai-code/his/`

---

---

## 2026-06-16

### HF Bucket 完整发行 · 瘦包 NN 外置

| # | 改动 |
|---|------|
| H1 | 公开 Bucket **liketocode789/EasyVtuberStudio**：完整 CORE 目录 + `data/ezvtb_nn/` ONNX（~350 MB） |
| H2 | GitHub CORE **移除** `data/ezvtb_nn/*.onnx`；`verify_fresh_extract` / `build_github_zip` 同步 |
| H3 | DEPLOY **[5]**：`ezvtb_nn_weights` 包首选 Bucket 拉取，回退 `import_ezvtb_nn_weights.ps1` |
| H4 | 文档：`HF_BUCKET_MIRROR.md`、`packaging/hf_bucket_README.md`（桶首页 README） |

---

## 2026-06-15（续）

### 输出增强 f-055 · f-056 · f-058 · f-060

| # | 改动 |
|---|------|
| O1 | **`output_enhancement/`** 模块：`EnhancementPipeline` 挂于 `_compose_present_rgba` 之后；默认全关 = 恒等 |
| O2 | **DEPLOY 档位 [5] output_enhancement**：onnxruntime + pyanime4k；ONNX 至 `addons/output_enhancement/ezvtb_data/`（GitHub 瘦包从 HF Bucket 拉取） |
| O3 | **后处理 UI**：SuperResolution (NN)、Frame Interpolation (NN/RIFE)、NN 推理后端、THA Student FP16 |
| O4 | **f-057** 慢任务进度：首次启用 SR/RIFE/TRT 时后台加载 + 非模态进度 |
| O5 | **`smoke_output_enhancement.py`**：pipeline 关闭时输入输出哈希一致 |

---

## 2026-06-15

> 详尽设计/排障记录见研发手册 `record/easyvtuberstudio条目设计手册.md`（圆周运动、ix-023/ix-025 校准、窗口捕获）。本节为面向发布的汇总。

### 图层 · 圆周运动 · 无限层扩展

| # | 改动 |
|---|------|
| G1 | **圆周运动**：图层 **运动 → 圆周运动**；轨道中心/半径/速度/平面倾斜/近远缩放；**同步/反向跟转** 倾斜轨道 |
| G2 | **辅助槽征用**：运动图层可征用另一槽位堆叠顺序实现前后遮挡切换；辅助槽仅借 z 序，**不**交替显示两图层素材；不可选另一圆周图层作辅助 |
| G3 | **轨道编辑 UI**：选中圆周图层显示轨道环 + 绑定点（非方框）；拖轨道改 `orbit_pivot`；`numpy_edit_chrome` / `layer_interaction` 专用路径 |
| G4 | **绑定+轨道**：`orbit_binding_shift` 轨道中心随绑定移动；编辑高亮/点选不含运动相位 |
| G5 | **堆栈通用化**：`collect_stack_layer_draws` / `resolve_stack_layer_draw` 支持动态槽位增删（L2 基础） |

### 鼠标面捕 · 三区校准

| # | 改动 |
|---|------|
| C1 | **中心区一致**：示意图/区内外判定/face_size 统一 `clamped_to_surface()`；手拖区同步 `gaze_neutral` |
| C2 | **三条校准界限（ix-025）**：path A 标定朝向；path B 摄像头动态增强；Mouse ix-023（同按钮 + UI-B07 周期）；周期 = 自动点对应按钮 |
| C3 | **校准后中性点**：`mouse_center_zone_calibration_point` 与 fitted 区中心对齐，避免贴边错位 |
| C4 | **ix-022 方向化缩放**：往上出中心区缩小、往下放大（`face_size_from_vertical_zone_exit`）；左右仍为 UI-B08 平移↔倾斜 mix |

### 图层快捷键 · GIF 播放（f-062 子集）

> **状态：🟠 半损坏·待修（2026-06-16）** — 代码已合入 develop/main 同步链，但快捷键**设置、注册与按住类动作**仍有已知回归（见 `TROUBLESHOOTING_QA.md` Q16b–Q16d、`easyvtuberstudio条目设计手册.md` f-062）。**直播关键路径请勿依赖**，待下一轮修复验收。

| # | 改动 |
|---|------|
| L1 | **全局热键**：`layer_hotkey_registry.py` + `BasicLayerSlot.hotkey_bindings`；图层窗录制键位 |
| L2 | **动作**：显隐切换；**按住隐藏 / 按住显示**；GIF **按住显示播一次** / 播一次 / **显示播一次后隐藏** / 循环 / 停止 |
| L3 | **`apply_layer_hotkey_action`**：主窗与外部触发共用；`smoke_layer_hotkeys.py` |
| L4 | **启动加固**：`EVT_HOTKEY` 可用性守卫；HWND 就绪后再注册热键；图层窗独立顶层 `parent=None` |
| L5 | **热键总开关**：后处理栏「启用图层快捷键」，**默认关**；勾选后才懒加载 `LayerHotkeyRegistry` |
| L6 | **启动崩溃修复**：`wx.HotKeyEvent` 在 wx 4.2 不存在，改 `wx.Event`；图层窗延迟到控件面板建完后再打开 |
| L7 | **按住显示播一次**：`hold_to_show_play_once`；按住从第 1 帧播 GIF 一次，松手恢复按下前显隐与播放状态 |
| L8 | **切换快捷键动作**：下拉改热键行为时 `reload_layer_from_asset` 清缓存并重置 GIF 待机态 |
| L9 | **稳定性/性能**：动作切换 `CallAfter` 防下拉闪退；按住热键轻量重绘；`play_once` 仅可见时持续刷新 |
| L10 | **快捷键设置修复**：重建快捷键 UI 时屏蔽 `EVT_CHOICE` 误写盘；草稿行（未录键）可持久化；启动后再 `sync` 注册 |
| L11 | **发布标记**：f-062 子集标为 **半损坏·待修**；双仓同步 + GitHub PR / HF Bucket 发布说明更新 |

### 窗口捕获 · 长时性能

| # | 改动 |
|---|------|
| W1 | **抓取方式缓存**：稳定后单路径 PrintWindow/BitBlt，不再每帧三连试 + 全图亮度评分 |
| W2 | **worker 优化**：长边缩至 1280 再面捕；抓取 ≥0.35s 清缓存换路径；同帧跳过重复 MediaPipe |
| W3 | **`smoke_window_capture.py`**：缩略图亮度与缓存失效无 GUI 回归 |

### 文档与维护

| # | 改动 |
|---|------|
| D1 | **`docs/CODEBASE_MAP.md`**、**`docs/BUG_HOTSPOT_CHECKLIST.md`** 入库；`DOC_INDEX` / `HANDOVER` 链入 |
| D2 | **`refresh_bug_hotspot_checklist.ps1`** + git hooks；`sync_develop_to_fork` 同步前刷新热点清单 |

---

## 2026-06-13

> 详尽设计/排障记录见研发手册 `record/easyvtuberstudio条目设计手册.md`（条目 2026-06-13(a)–(f)）。本节为面向发布的汇总。

### 透明输出 · wx-free 管线 · 帧率 / 窗口模型

| # | 改动 |
|---|------|
| T1 | **present 管线 wx-free + 单输出窗**：透明档隐藏 `OutputFrame`，分层窗（ULW）成为唯一输出兼编辑面；鼠标（选中手柄→编辑 / 空白→拖窗）与方向键微调改由 ULW 的 Win32 WNDPROC 处理，回调贯通 `TransparentCaptureWindow` → 主窗编辑入口。其余背景档（黑键/纯色/图片）仍用 `OutputFrame` |
| T2 | **输出帧率「对半砍」根因修复**：消除采集分支与显示路径的**双重全栈合成**、以及「每帧推理即同步全合成」打满 UI 线程的回归；present 改回纯 `display_timer` 驱动（按显示上限节流 + 去重），复用显示已合成的透明底真 alpha 帧 |
| T3 | **输出帧率计数补帧**：`_note_display_fps_tick()` 移到 ULW 真正交付帧处（`_deliver_capture_premultiplied`，全档唯一计数点），修「显示与实际帧率对不上」 |
| T4 | **残影消除**：采集不再回读铺灰底 + 色键，统一复用显示路径透明底单次合成（`compose_output_stack_rgba`），抗锯齿边缘移动残影根因消除 |
| T5 | **三窗启动**：主控件 / 图层 / 输出三窗一同启动，输出窗优先出现，便于直播软件按名记忆窗口 |

### 任务栏标签与图标

| # | 改动 |
|---|------|
| I1 | **全窗统一 exe 图标**：`MainFrame`/`ControlsFrame`/`OutputFrame`/`WebcamPreviewPopupFrame`/图层窗及 ULW 均用同款 `.ico`（多尺寸 `IconBundle`） |
| I2 | **去 python 宿主标签**：建窗前设 `AppUserModelID`（`EasyVtuberStudio.FacePuppeteer`），任务栏改用各窗图标；ULW `WS_EX_APPWINDOW` 保留独立标签 |
| I3 | **ULW 静态识别外框**：点击穿透 / 不入任务栏 / 不可激活的分层窗在 ULW 外画一圈识别边框（中心透明、随 ULW 移动、不入采集）；输出框尺寸锁定 |

### 背景与图层窗 · 选中编辑

| # | 改动 |
|---|------|
| L1 | **背景下拉重构**：四档改名重排「透明 / 自选纯色背景 / 自选图片 / 黑键」，背景统一合成进 ULW；新用户默认「透明」；输出窗标题改为 `easyvtuberstudio_output`（内部值常量与持久化映射不变） |
| L2 | **图层窗按需打开**：仅勾选「启用图层混合」才打开图层窗；「加载立绘 / 加载其他立绘」按钮文案统一 |
| L3 | **选中编辑修复**：真透档选中高亮即时刷新（采集签名含 `selected_slot_id`）；高亮框内部填极小非零 alpha → 框内可拖动且采集不可见；点输出窗（ULW）不误取消选中、点桌面/外部正确取消选中、点图层不再误拖窗 |
| L4 | **移除「角色边缘闪烁」档**：默认改「无效果」，旧持久化 `flicker` 归一化为 `none` |

### 图层绑定 · 随躯干左右倾斜贴合

| # | 改动 |
|---|------|
| B1 | **绑定随左右倾斜贴合增强**：身绑锚点与精灵不再只跟「动态增强整图自动倾斜」，改为同时跟随黑盒图像源（THA）自身的躯干左右倾斜；动态增强**关闭**时也保持贴合，不再「钉死/脱位」 |
| B2 | **倾斜来源纠正**：躯干左右倾斜取自黑盒 `body_z(roll)`（而非此前误用的 `head_x/head_y` pitch/yaw）；按 `body_tilt_opposite_to_head` 处理身体反头；引入经验符号 `BODY_BIND_BLACKBOX_ROLL_SIGN` 修正左右镜像（排除 `mirror_output` 死代码与输入自拍镜像干扰） |
| B3 | **周期方向标定解耦**：「标定朝向」周期校准提到无条件执行，不再因关闭动态增强而静默失效 |
| B4 | **随倾跟随拆双增益（图层系统可调）**：「射线映射」面板新增两条滑条 **随倾位移 / Lean shift**（只动锚点位置，0–150%）与 **随倾转动 / Lean rotate**（只转精灵，0–150%），独立可调；解决「关闭自动移动缩放时纠正参数过大→轻微动作造成巨大图层位移」（射线长力臂放大角度的几何问题）；持久化并从旧单增益键自动迁移 |
| B5 | **绑定移动去延时**：修双重平滑（display 已上游 EMA、绑定层再次 EMA）→ 绑定**位置即时跟随**、仅对**跟转**保留 EMA 抑抖；「平滑跟随」开启 = 跟转抑抖且位置无延时 |

---

## 2026-06-04

| # | 改动 |
|---|------|
| L1 | **三栏布局持久化修复**：分割条拖动与窗缩放/移动写入 `main/animation/right_sidebar_splitter_sash_ratio`；拖动中 80ms 防抖布局 + 250ms 防抖写盘；恢复布局时不再误触发立即保存 |
| L2 | **校准控件迁至预览行**：「标定朝向」「输出动态增强校准」及周期勾选/间隔 Spin 移至立绘+摄像头预览**右侧** `preview_calibration_column`（自后处理栏迁出） |
| L3 | **完整调参窗四边可缩放**：`CONTROLS_MIN_CLIENT_WIDTH` 降至 ~1124px；`ControlsFrame` 不再在每次 resize 设 `SetMin/MaxClientSize` 锁死边框 |
| L4 | 本地目录更名：`tha4fork*` → `easyvtuberstudio-develop` / `easyvtuberstudio-main`（**非** GitHub 仓库名）；GitHub 仍为 **EasyVtuberStudio**；打包 junction 路径验收更新 |

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
| W3 | THA3 变体下拉仍位于后处理栏；**朝向/输出动态增强校准**已迁至预览行右侧校准列（2026-06-04） |
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
