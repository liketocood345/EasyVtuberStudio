# Bug 热点回归清单（新功能防复发）

> **用途**：每次**添加或修改产品功能**前，须对照 **§Top 10 全部条目**逐项自检（不按历史频次跳过）。
> **数据源**：`e:\record\labeled_prompt.md` 中 `问题修复` 标签（按主题聚合频次）。
> **生成时间**：2026-06-24T02:48:36.694549+10:00
> **问题修复样本量**：27 条
> **自动更新**：每次 `git push` 成功后由 `post-push` hook 刷新；`sync_develop_to_fork.ps1` 同步前也会刷新。
> **手动重建**：`python e:\record\_build_bug_feedback_index.py` 或 `scripts\maint\refresh_bug_hotspot_checklist.ps1`
> **详细索引**：`e:\record\bug_feedback_index.json` · 用语分析 `e:\record\bug_feedback_vocab.md`

---

## Top 10 速查（按历史反馈频次，仅作分组索引）

| 排名 | 主题 | 次数 | 核心代码区 |
|------|------|------|------------|
| 1 | 性能 / 卡顿 / 掉帧 | 8 | 主循环 `update_capture_panel` / 推理与显示链 |
| 2 | 闪退 / 打不开 / 进程卡死 | 3 | `character_model_mediapipe_puppeteer_load_preview.py` 初始化与 `OnInit` |
| 3 | 校准 / 动态增强 / 预览朝向 | 2 | 主文件 `preview_calibration_column` |
| 4 | 真透明输出 / 额外窗 / 直播采集 | 2 | `transparent_capture_window.py` · `output_backends.py` |
| 5 | 摄像头 / 视频源 / DroidCam | 1 | `image_sources/` · 捕获面板源列表 |
| 6 | DEPLOY / 启动脚本 | 1 | `DEPLOY.bat` · `docs/DEPLOY.md` |

### Top 10 勾选（每次加功能须全勾，禁止按排名跳过）

完成实现后，在 PR/交接说明中列出全部 Top10 自检结果（通过 / 未测 / N/A）：

- [ ] **#1 性能 / 卡顿 / 掉帧**
- [ ] **#2 闪退 / 打不开 / 进程卡死**
- [ ] **#3 校准 / 动态增强 / 预览朝向**
- [ ] **#4 真透明输出 / 额外窗 / 直播采集**
- [ ] **#5 摄像头 / 视频源 / DroidCam**
- [ ] **#6 DEPLOY / 启动脚本**

---

## Top 10 明细

### #1 · 性能 / 卡顿 / 掉帧（8 次）

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

### #2 · 闪退 / 打不开 / 进程卡死（3 次）

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

### #3 · 校准 / 动态增强 / 预览朝向（2 次）

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

### #4 · 真透明输出 / 额外窗 / 直播采集（2 次）

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

### #5 · 摄像头 / 视频源 / DroidCam（1 次）

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

### #6 · DEPLOY / 启动脚本（1 次）

**典型现象**

- 脚本无法双击
- 档位与 addons 不一致

**代码热点**

- `DEPLOY.bat` · `docs/DEPLOY.md`
- `scripts/launch/`

**回归检查**

- [ ] 改依赖同步 DEPLOY 档位说明

---

## Agent 自动对照约定

1. 用户提出 **新功能 / 改功能 / f-xxx 条目 / 接入某模块** 时，先 Read 本文件 §Top 10 **全部**条目。
2. 改动落点与上表「代码热点」有交集时，对应 **回归检查** 全做（不因历史排名低而省略）。
3. 完成前在回复中列出 **全部** Top10 序号与自检结果（通过 / 未测 / N/A）。
4. `labeled_prompt.md` 新增 `问题修复` 后，排行在下次 **git push** 或 **sync_develop_to_fork** 时自动刷新。
