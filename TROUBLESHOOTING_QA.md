# 排障与常见误解 Q&A / Troubleshooting FAQ

基于 `THA4_bundle_bai_custom` 上的实验增强（Load Preview）、camfix 隔离测试、fork 文档整理。  
**活跃开发：** `E:\THA4_bundle_bai_custom\` · **文档副本（本文件）：** fork 仓库根目录。

相关文档：[HARDWARE_REQUIREMENTS.md](HARDWARE_REQUIREMENTS.md) · [BACKUP.md](BACKUP.md) · [CHANGELOG.md](CHANGELOG.md)

---

## 置顶问题（先看这个）

### Q0：我使用了 DroidCam，那我这辈子是不是完蛋了？

**A：** 是的，本项目作者也使用了 doridcam，并浪费了自己的人生。早点把这个卸掉吧，搞个正经摄像头。

---

## 一、启动、路径与版本

### Q1：双击桌面快捷方式，改的是 fork 还是 bai_custom？

**A：** 以快捷方式目标为准。当前常见配置指向 **`E:\THA4_bundle_bai_custom\...\run_load_preview_puppeteer.bat`**（活跃开发版）。若指向 `face-puppeteer-ui-enhancements-ai-code\...`，则运行的是 fork 副本。两者脚本路径、PYTHONPATH 不同，**不要混用**后抱怨「改了代码没生效」。

---

### Q2：我改了 fork 里的代码，为什么运行 bai_custom 没变化？

**A：** 活跃开发与 fork 是两套目录。日常开发在 **`bai_custom`**；fork 仅在同步或你明确要求备份/发布时更新。改 fork 不会自动改 bai_custom。

---

### Q3：启动黑窗闪退，日志在哪？

**A：** 看 bat 里 `LOG_FILE`。`bai_custom` 常见为：  
`E:\THA4_bundle_bai_custom\experiments\puppeteer_load_preview\run_load_preview_runtime.log`  
fork 若在 fork 下运行 bat，则在 fork 同目录。先查 **CUDA / 模型路径 / MediaPipe .task 是否存在**。

---

### Q4：提示找不到 CUDA 或 `cuda:0` 报错？

**A：** 脚本默认 **`torch.device("cuda:0")`**，需要 NVIDIA 显卡与 CUDA 版 PyTorch。无独显时需改代码改 CPU，**通常无法实时面捕**，属环境限制而非 UI bug。

---

### Q5：必须用 `talking-head-anime-4-demo\venv` 吗？

**A：** 是。bat 使用  
`E:\THA4_bundle_bai_custom\talking-head-anime-4-demo\venv\Scripts\python.exe`。  
应用该 venv 的 `PYTHONPATH` 指向 `src`（fork 运行时可能额外 prepend fork 的 `src`）。

---

## 二、摄像头与视频源

### Q6：设备列表里没有 DroidCam？

**A：** 先 **打开 DroidCam 客户端**（手机端 + PC 端），再点「刷新设备列表」。未启动时 DirectShow/WMI 可能列不出虚拟摄像头。建议安装 **`pygrabber`**（在 THA4 venv 内）以获取 DirectShow 名称列表。

---

### Q7：选 DroidCam 后程序闪退或卡死？

**A：** 实测上 **OpenCV `CAP_DSHOW` + DroidCam 索引** 易异常；实验版/camfix 对名称含 `droidcam` 的项 **优先 MSMF、避免 DSHOW 回退**，并在子线程打开摄像头减轻 UI 冻结。若仍闪退：更新 DroidCam、换 USB/ WiFi 模式、试 **camfix**（`bai_custom\camfix\run_camfix_puppeteer.bat`）仅测摄像头区。

---

### Q8：有画面但是雪花、花屏、全绿？

**A：** 多为 **错误分辨率/像素格式** 或虚拟摄像头未就绪。camfix/实验版会试 MJPG/YUY2、640×480。若 camfix 也花屏 → 优先查 **DroidCam/OBS 虚拟摄像头配置与驱动**，不一定是 THA4 UI。

---

### Q9：选 DroidCam 却显示 OBS 或其它设备的画面？

**A：** **pygrabber 列表索引 ≠ OpenCV 索引**，不能单靠数字对齐。用 **设备名称** 匹配；列表里选带 `DroidCam` 字样的项。隔离测试结论：无画面/错设备 **经常是虚拟摄像头软件问题**，不单是 puppeteer。

---

### Q10：摄像头预览黑屏，但状态写「已连接」？

**A：** 可能 **已打开但读帧无效**（实验版会提示 invalid frame）。点刷新、换后端、降分辨率；DroidCam 重连手机端。

---

### Q11：camfix 正常，实验版不正常，说明什么？

**A：** 按 camfix 设计：**摄像头链路 OK**，问题更可能在实验版的 **非摄像头功能**（双窗、自动平移缩放、输出合成、抗锯齿等）。逐项关闭自动变换、AA=1.0 排查。

---

### Q12：camfix 也不正常，说明什么？

**A：** 优先查 **DroidCam/驱动/OpenCV 后端**；THA4 原版 `VideoCapture(0)` 也可能同样失败。

---

## 三、模型加载与画面预览

### Q13：加载模型后仍显示 `Nothing yet!`？

**A：** **实验增强版** 应在加载后 **立即显示默认中性 pose**；无脸时 **保留上一帧** 而非清空。若仍出现 `Nothing yet!`：确认运行的是 **Load Preview 脚本**，不是原版 `character_model_mediapipe_puppeteer.py`。

---

### Q14：「加载上次模型」无效或弹路径失效？

**A：** 路径记在 `load_preview_ui_state.json`（与脚本同目录）。移动/删除模型包后会提示重选，**属正常**。用「加载其他模型」重新指定 `character_model.yaml`。

---

### Q15：没开摄像头，立绘会动吗？

**A：** 加载模型后有 **默认 pose 静态预览**；实时表情需摄像头或视频源 + MediaPipe 检测到脸。无人脸时 head 数值可能不变，**正常**。

---

### Q16：输出窗有角色，主窗预览很小或布局挤在一起？

**A：** 增强版曾调整 **三栏/视频源独立列**；过窄时拖动分割条或放大「完整调参窗」。右侧控件过多时用窗口滚动条。

---

## 四、窗口、UI 与操作

### Q17：启动只有三个按钮，其它控件哪去了？

**A：** **紧凑启动窗** 设计如此。点 **「Open Full Controls / 切换到完整调参窗」** 懒加载完整控件。提示：加载新模型需展开完整窗。

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

**A：** 当前版本会记忆滑块：动态输出/后处理写入 `display_transform_settings`，模型输入栏（呼吸、嘴部、转换参数、虹膜等）写入 `mouth_settings`。若仍丢失，确认已正常退出程序（触发保存），且 `experiments/puppeteer_load_preview/load_preview_ui_state.json` 可写、未被旧版覆盖。

---

### Q23：镜像开关切换后角色「卡住」不动？

**A：** 曾修复：镜像应作为 **最后独立步骤**，且切换时不应冻结。若旧版仍卡住，更新到最新 `bai_custom` 脚本。

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

**A：** **OBS 风格电平条** 在 fork 的 `mediapipe_face_pose_converter_00.py` 中实现；**bai_custom 活跃版可能仍是波形示波器**。桌面快捷方式若指向 bai_custom，看不到电平条 **正常**。需要时把 fork 中该段合并进 bai_custom。

---

### Q29：面捕模式下电平条/音频区还显示？

**A：** 面捕时音频面板可隐藏或显示「当前模式: Face tracking」；**不驱动嘴型** 为正常。

---

### Q30：为什么我选了透明背景，导出/采集后看起来还是不透明？

**A：** 这通常不是单点 bug，而是和**图层（Layer）能力**有关：  
THA4 输出虽然可在本地显示透明背景选项，但最终是否“真透明”取决于后续链路是否支持 alpha 图层（例如窗口采集方式、虚拟摄像头格式、直播软件源设置、合成顺序）。  
如果后端链路不支持透明图层，就会被黑底/实色底替代，这是常见兼容性表现。

建议：
1. 在目标软件里确认该采集源支持 alpha/透明图层；  
2. 优先使用支持透明通道的窗口/源类型；  
3. 若链路不支持透明图层，改用纯色背景并在直播端做抠像键控（绿幕/蓝幕）。

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

### Q35：fork 和 bai_custom 哪个是「正版」？

**A：** **bai_custom = 活跃开发源**；fork = 分发副本 + `his/` 历史快照。文档在 fork 更新；代码以你实际运行的目录为准。

---

### Q36：如何备份 fork 当前根目录？

**A：** 见 [BACKUP.md](BACKUP.md)：运行 `archive_to_his.ps1`，根内容移入 `his/yyyy-MM-dd_HH-mm-ss/`（秒级时间戳），再同步新版本。

---

### Q37：sync_from_bai_custom.ps1 会覆盖哪些？

**A：** 主要同步实验脚本、`mediapipe_face_pose_converter_00.py`、`packaged/bai_450k`、`HANDOVER.md` 等；**不会**自动覆盖 `CHANGELOG.md`、`BACKUP.md`、本 Q&A 等 fork 维护文档。

---

### Q38：程序打不开，能不能从历史版本直接拖出来覆盖路径？

**A：** 可以，这是最常用的应急恢复方式之一。  
从 `his/` 里选一个最近可用快照，把对应文件/目录直接拖拽覆盖到目标路径即可。

建议操作：
1. 先确认当前运行目录是 `bai_custom` 还是 fork；  
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
| N2 | 紧凑窗下无法加载「新」模型包 | 需打开完整调参窗使用「Load Another Model」 |
| N3 | 无人脸时立绘不跟动 | 无 blendshape 输入时保持上次 pose 或默认 pose |
| N4 | 预览区写 `No face input` | 未检测到脸或摄像头未开，**不是**崩溃 |
| N5 | 曲线区「等待人脸」 | 自动缩放曲线需人脸数据后才显示当前点 |
| N6 | 输出窗与主窗内容略有差异 | 输出窗经 **平移/缩放/旋转/镜像/抗锯齿** 合成，与源预览不同属正常 |
| N7 | 负的「倾斜上限」时模型头动变小 | **设计**：负值削弱传给模型的 roll，非显示旋转 |
| N8 | 镜像只影响画面、不改变倾斜语义 | **设计**：镜像为最后独立步骤 |
| N9 | 呼吸 bpm 与动作状态跳动 | 反应式呼吸根据动作分数切换 BASE/TRIGGER/DECAY |
| N10 | 设备列表第一项是「视频文件…」 | 增强版支持文件源，非误加入的摄像头 |
| N11 | 刷新设备时短暂卡顿 | 多索引/多后端探测在 CPU 上执行，属一次性开销 |
| N12 | 日志写在 .log 里终端不刷屏 | bat 将 stdout 重定向到日志文件 |
| N13 | 启动即弹出「完整大窗」 | 实验版 `startup_show_full_controls` 默认展开完整窗 |
| N14 | 分割条位置下次还在 | 部分 splitter 位置会持久化 |
| N15 | 原版 puppeteer 无视频源下拉 | 原版仅 `VideoCapture(0)`，**不是**增强版回退 |
| N16 | camfix 无自动平移/双窗 | camfix **刻意省略** 非摄像头功能，用于对比 |
| N17 | 面捕时音频设备名仍显示 | 状态栏刷新逻辑可能显示设备信息，但不驱动嘴型 |
| N18 | GPU 占用周期性波动 | 约 30FPS 推理 + UI 刷新，波形正常 |
| N19 | 加载模型后 CPU 占用上升 | 模型与 MediaPipe 常驻，正常 |
| N20 | 12GB 写在文档但 8GB 卡能 solo 跑 | 12GB 针对 **多软件同开**，见硬件文档第 8 节 |

---

## 九、建议排障顺序（速查）

```text
1. 确认运行的 bat / 脚本路径（bai_custom vs fork）
2. 查 run_load_preview_runtime.log
3. 摄像头：camfix 单测 → 换 MSMF/物理摄像头 → DroidCam 客户端
4. 模型：能否 Load Another Model；yaml 与 .pt 是否完整
5. 性能：AA=1.0、缩小输出窗、solo 运行 THA4
6. 音频：模式、阈值、是否被 OBS 占用
7. 对比原版 puppeteer：区分「增强功能」与「基础链路」问题
```

---

## 十、仍无法解决时建议收集的信息

- 运行的 **bat 完整路径** 与 `LOG_FILE` 末尾 50 行  
- GPU 型号、显存、是否同开 OBS/快手  
- 摄像头名称与是否 DroidCam  
- 实验版 / 原版 / camfix 哪一种可复现  
- `load_preview_ui_state.json` 是否损坏（可临时改名备份后删除试默认）

---

*文档版本：2026-05-27 · 随 camfix 结论、持久化、硬件说明与用户排障经历整理。活跃代码变更以 `bai_custom` 为准；更新本 Q&A 时请同步 README 链接。*
