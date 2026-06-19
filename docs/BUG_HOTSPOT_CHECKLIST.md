# Bug 热点回归清单（新功能防复发）

> **用途**：每次**添加或修改产品功能**前，须对照 **§Top 10 全部条目**逐项自检（不按历史频次跳过）。
> **数据源**：`e:\record\labeled_prompt.md` 中 `问题修复` 标签（按主题聚合频次）。
> **生成时间**：2026-06-20T02:04:50.599553+10:00
> **问题修复样本量**：126 条
> **自动更新**：每次 `git push` 成功后由 `post-push` hook 刷新；`sync_develop_to_fork.ps1` 同步前也会刷新。
> **手动重建**：`python e:\record\_build_bug_feedback_index.py` 或 `scripts\maint\refresh_bug_hotspot_checklist.ps1`
> **详细索引**：`e:\record\bug_feedback_index.json` · 用语分析 `e:\record\bug_feedback_vocab.md`

---

## Top 10 速查（按历史反馈频次，仅作分组索引）

| 排名 | 主题 | 次数 | 核心代码区 |
|------|------|------|------------|
| 1 | 闪退 / 打不开 / 进程卡死 | 18 | `character_model_mediapipe_puppeteer_load_preview.py` 初始化与 `OnInit` |
| 2 | 性能 / 卡顿 / 掉帧 | 18 | 主循环 `update_capture_panel` / 推理与显示链 |
| 3 | 图层系统（L0–L3 / 外挂窗） | 17 | `face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/layer_runtime.py` |
| 4 | 真透明输出 / 额外窗 / 直播采集 | 10 | `transparent_capture_window.py` · `output_backends.py` |
| 5 | 绑定 / 跟随 / 镜像 / 倾斜 | 9 | `layer_runtime.py` → `BindingContext`、绑定求值 |
| 6 | 终端报错 / 堆栈 / OpenCV-wx 异常 | 9 | 摄像头 `VideoCapture` / DSHOW（`cap.cpp` 报错） |
| 7 | 布局 / 分割条 / 持久化 | 8 | `workspace/load_preview_ui_state.json` |
| 8 | 校准 / 动态增强 / 预览朝向 | 7 | 主文件 `preview_calibration_column` |
| 9 | 摄像头 / 视频源 / DroidCam | 5 | `image_sources/` · 捕获面板源列表 |
| 10 | THA3 / THA4 模型加载 | 5 | `tha3_engine.py` · `image_sources/` |

### Top 10 勾选（每次加功能须全勾，禁止按排名跳过）

完成实现后，在 PR/交接说明中列出全部 Top10 自检结果（通过 / 未测 / N/A）：

- [ ] **#1 闪退 / 打不开 / 进程卡死**
- [ ] **#2 性能 / 卡顿 / 掉帧**
- [ ] **#3 图层系统（L0–L3 / 外挂窗）**
- [ ] **#4 真透明输出 / 额外窗 / 直播采集**
- [ ] **#5 绑定 / 跟随 / 镜像 / 倾斜**
- [ ] **#6 终端报错 / 堆栈 / OpenCV-wx 异常**
- [ ] **#7 布局 / 分割条 / 持久化**
- [ ] **#8 校准 / 动态增强 / 预览朝向**
- [ ] **#9 摄像头 / 视频源 / DroidCam**
- [ ] **#10 THA3 / THA4 模型加载**

---

## Top 10 明细

### #1 · 闪退 / 打不开 / 进程卡死（18 次）

**典型现象**

- 主界面/主窗口打不开
- 启动后进程卡死或秒退
- 改图层/捕获后进程无响应

**代码热点**

- `character_model_mediapipe_puppeteer_load_preview.py` 初始化与 `OnInit`
- `packaging/launcher/launch_face_puppeteer.py` · 根目录 `EasyVtuberStudio.exe`
- wx 主窗创建、定时器、跨线程 UI 更新

**回归检查**

- [ ] develop bat 与 fork exe 均能进主窗（无 addons 时优雅降级）
- [ ] 重入初始化（重载角色/切源）不 double-free Qt/wx 控件
- [ ] 后台 worker 结果回 UI 必须用 `wx.CallAfter` / 线程安全路径

### #2 · 性能 / 卡顿 / 掉帧（18 次）

**典型现象**

- 周期性 UI 冻结（曾见捕获定时器阻塞）
- 帧率减半、终端持续报错拖慢主循环
- 屏幕捕获每隔一段时间卡死

**代码热点**

- 主循环 `update_capture_panel` / 推理与显示链
- `window_capture.py` · `_window_capture_worker`（勿在 UI 线程 `PrintWindow`）
- 双窗输出、透明窗刷新、MediaPipe worker

**回归检查**

- [ ] 窗口/屏幕捕获在 UI 线程仅读缓存帧，重操作在 worker
- [ ] 开透明输出后帧率变化可解释（勿静默对折）
- [ ] 长时运行 10+ 分钟无内存/句柄泄漏导致的卡顿

### #3 · 图层系统（L0–L3 / 外挂窗）（17 次）

**典型现象**

- 外挂图层窗闪烁或拖垮主进程
- 「无限图层」占位开关误开副作用
- 改图层后摄像头源或主预览异常
- 加载角色后原图层显示未加载

**代码热点**

- `face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/layer_runtime.py`
- `.../basic_layer_window.py` · `layer_interaction.py`
- `workspace/basic_layers/` · 主文件图层开关/合成入口

**回归检查**

- [ ] 开关图层外挂窗：可正常打开/关闭，主窗不卡死
- [ ] 未启用无限图层时，图层代码路径不应影响主捕获/推理
- [ ] L1–L3 拖动/缩放后 `basic_layers/` 与 UI 列表一致
- [ ] 合成输出与预览对同一 `BindingContext` 求值
- [ ] 同帧内改图层显隐/删层/换 host 后，orbit 缓存与绘制计划一致（无半拍错位）
- [ ] 删 host 或解除 aux 征用后，follower 与 aux 槽可见性/轨道 UI 与状态一致

### #4 · 真透明输出 / 额外窗 / 直播采集（10 次）

**典型现象**

- 真透明输出后角色消失或帧率恢复异常
- 采集端全黑/全透明/残影
- 额外窗与主预览不一致

**代码热点**

- `transparent_capture_window.py` · `output_backends.py`
- 主文件透明输出开关、双窗合成链
- 快手/直播助手窗口捕获列表

**回归检查**

- [ ] 开关真透明：预览仍可见，输出窗 alpha 正确
- [ ] 第三方采集能稳定抓到目标 HWND（列表刷新后仍有效）
- [ ] 关透明输出后单窗路径无残留定时器/子进程

### #5 · 绑定 / 跟随 / 镜像 / 倾斜（9 次）

**典型现象**

- 绑定头/身后图层错位、镜像/倾斜反转不对
- 拖图层时预览与输出不同步
- 归位/跟随破坏原图或影响无关图层

**代码热点**

- `layer_runtime.py` → `BindingContext`、绑定求值
- 预览/输出共用 `layer_interaction.py`
- 面捕 `mediapipe_face_pose_converter_00.py` 与绑定头/身

**回归检查**

- [ ] 改绑定只影响目标图层，不污染其他层默认变换
- [ ] 预览拖动与输出合成使用同一交互状态
- [ ] 头/身/层 N 绑定切换后无累积旋转漂移

### #6 · 终端报错 / 堆栈 / OpenCV-wx 异常（9 次）

**典型现象**

- `cap.cpp` / `VideoCapture::open` 连续 ERROR
- AttributeError / RuntimeError 堆栈刷屏
- 报错时功能静默失效

**代码热点**

- 摄像头 `VideoCapture` / DSHOW（`cap.cpp` 报错）
- wx API 版本差异（如 `wx.BORDER_TOP`）
- THA 推理链、图层/输出异常未捕获

**回归检查**

- [ ] 摄像头打不开时有 UI 提示，不无限重试刷屏
- [ ] 新增 wx 常量/控件前确认目标环境 API 存在
- [ ] 预期可恢复的异常应 catch 并降级，勿拖死主循环

### #7 · 布局 / 分割条 / 持久化（8 次）

**典型现象**

- 三栏表述与实装不一致、分割条拖不动
- 缩放窗口后排版挤成一团或未归位
- 重启后 sash 比例丢失

**代码热点**

- `workspace/load_preview_ui_state.json`
- 主文件 `main/animation/right_sidebar_splitter_sash_ratio`
- 250ms 防抖写盘、窗几何与最小宽度

**回归检查**

- [ ] 拖分割条后 250ms 内写入 state，重启可恢复
- [ ] 最小窗宽下四边仍可缩放，左右栏不被挤没
- [ ] 改布局相关键名须兼容旧 state 或迁移

### #8 · 校准 / 动态增强 / 预览朝向（7 次）

**典型现象**

- 动态增强校准反向或重置无效
- 预览时眼睛方向与脸朝向不一致
- 校准控件迁位后状态丢失

**代码热点**

- 主文件 `preview_calibration_column`
- 动态增强滑条与持久化键
- 面捕朝向与增强联动

**回归检查**

- [ ] 调校准滑条：预览与输出增强一致
- [ ] 重置/默认值可恢复，写入 state
- [ ] 与面捕同时开启时无反馈振荡

### #9 · 摄像头 / 视频源 / DroidCam（5 次）

**典型现象**

- 正常摄像头源显示损坏或列表异常
- DroidCam/DSHOW 源切换后黑屏
- 改图层后摄像头源被连带破坏

**代码热点**

- `image_sources/` · 捕获面板源列表
- `docs/camfix/CAMERA_CHANGES_SUMMARY.md` 约定
- MediaPipe 输入链与源热切换

**回归检查**

- [ ] 枚举源 → 选择 → 预览有画面，终端无 ERROR 风暴
- [ ] 切 THA/摄像头/窗口捕获互切不泄漏上一源句柄
- [ ] 源异常时 UI 可重选，不需重启进程

### #10 · THA3 / THA4 模型加载（5 次）

**典型现象**

- 找不到模型 / 无法加载角色
- 半精度或路径变更后加载失败
- 加载后头身绑定或面捕异常

**代码热点**

- `tha3_engine.py` · `image_sources/`
- `deps/tha3/` · `addons/tha3_models/`
- THA3_INTEGRATION.md 双源路径

**回归检查**

- [ ] develop 全装与 fork 瘦包对缺失模型有明确提示
- [ ] 加载/卸载角色不泄漏 GPU 显存或重复 init
- [ ] THA3/THA4 切换后图像源状态一致

---

## 全量排名（Top 10 以外）

| 排名 | 主题 | 次数 |
|------|------|------|
| 11 | 窗口 / 屏幕捕获 | 4 |
| 12 | CodeGraph / record 元问题 | 2 |
| 13 | DEPLOY / 启动脚本 | 2 |
| 14 | UI 控件生命周期 | 2 |

---

## Agent 自动对照约定

1. 用户提出 **新功能 / 改功能 / f-xxx 条目 / 接入某模块** 时，先 Read 本文件 §Top 10 **全部**条目。
2. 改动落点与上表「代码热点」有交集时，对应 **回归检查** 全做（不因历史排名低而省略）。
3. 完成前在回复中列出 **全部** Top10 序号与自检结果（通过 / 未测 / N/A）。
4. `labeled_prompt.md` 新增 `问题修复` 后，排行在下次 **git push** 或 **sync_develop_to_fork** 时自动刷新。
