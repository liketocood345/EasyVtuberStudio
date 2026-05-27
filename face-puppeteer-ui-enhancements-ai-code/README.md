# Face Puppeteer UI Enhancements (Fork)

Fork staging repository for THA4 MediaPipe puppeteer UI work.  
**Active source of truth:** `E:\THA4_bundle_bai_custom\`  
**This folder:** distributable copy + history archive.

## Layout

```
face-puppeteer-ui-enhancements-ai-code/
├── README.md
├── CHANGELOG.md
├── HARDWARE_REQUIREMENTS.md                # 硬件需求（单独 / 与 OBS·直播助手同开）
├── TROUBLESHOOTING_QA.md                   # 排障 Q&A + 易误解的正常表现
├── BACKUP.md                               # backup/update rules
├── HANDOVER.md
├── archive_to_his.ps1                      # root → his/yyyy-MM-dd_HH-mm-ss/
├── sync_from_bai_custom.ps1
├── experiments/puppeteer_load_preview/
├── talking-head-anime-4-demo/src/tha4/mocap/...
├── packaged/bai_450k/
└── his/
    ├── README.md
    ├── CHANGELOG.md
    ├── 2026-05-27/                         # legacy (day only)
    └── 2026-05-27_14-30-45/                # example (to the second)
```

## 更新与备份规则

需要留档时：**把当前根目录内容移入 `his/`，用本地时间精确到秒命名**，再从 `bai_custom` 复制新版本到根目录。

| 项 | 约定 |
|----|------|
| 快照目录名 | `yyyy-MM-dd_HH-mm-ss`（例：`2026-05-27_14-30-45`） |
| 不移入快照 | `his/`、`.git/` |
| 推荐顺序 | `archive_to_his.ps1` → `sync_from_bai_custom.ps1` |

详细步骤与恢复说明见 **[BACKUP.md](BACKUP.md)**。

```bat
powershell -ExecutionPolicy Bypass -File E:\face-puppeteer-ui-enhancements-ai-code\archive_to_his.ps1
powershell -ExecutionPolicy Bypass -File E:\face-puppeteer-ui-enhancements-ai-code\sync_from_bai_custom.ps1
```

## 硬件需求

单独运行、与 **OBS / 快手直播助手** 同开时的 CPU/GPU/内存建议、**项目原理与显存档位说明**（为何文档会出现 12GB 推荐），以及与 THA4 原版的对比，见 **[HARDWARE_REQUIREMENTS.md](HARDWARE_REQUIREMENTS.md)**。

## 训练建议（云服务器 / 角色风格）

### 1) 何时建议用云服务器训练

以下场景建议把训练放到云服务器（本地仅做推理与调参）：

- 本地显卡显存不足或常与 OBS/直播助手抢资源。
- 需要长时间连续训练（如 450k -> 800k）且不希望占用日常工作机器。
- 需要多版本并行试验（不同 `distiller_config` 参数组）。

建议配置（训练向）：
- 单卡 NVIDIA 12GB+ 可起步，24GB+ 更从容；
- 稳定 SSD 与足够磁盘配额（保存 checkpoint）；
- 训练完成后只下载打包结果（`face_morpher.pt` / `body_morpher.pt` / `character.png`）回本地。

实践建议：
- 云端负责 `distill` / checkpoint 迭代，本地只负责 `packaged/.../character_model.yaml` 验证；
- 固定 checkpoint 命名与日志，便于回溯（如 `0045=450k`, `0080=800k`）。

### 2) 低色彩复杂度角色的训练建议

对于配色简单、渐变少、大面积纯色（“低色彩复杂度”）角色，常见问题是边缘发灰、眼周脏色或轻微色块抖动。建议：

- 优先降低 body 训练里的颜色混合强度（参考本仓 `bai_450k` 经验：`color_change`、`blended` 适当下调）。
- 先做 450k 里程碑观察眼部与脸部，再决定是否继续到 650k/800k。
- 保持角色原图边界干净（透明通道与边缘抗锯齿一致），减少训练时把半透明边缘学成灰边。
- 在手动 poser 与 puppeteer 两端都验证：避免只在单一姿态看起来正常。

可参考：
- `packaged/bai_450k/TRAINING_NOTES.txt`
- `packaged/bai_450k/PACKAGING_README.txt`

## 排障 Q&A

常见故障、DroidCam/camfix 结论、fork 与 bai_custom 区别，以及**容易被当成 bug 的正常表现**，见 **[TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md)**。

## 改动列表 / Change log

完整列表见 **[CHANGELOG.md](CHANGELOG.md)**；历史归档说明见 **[his/CHANGELOG.md](his/CHANGELOG.md)**。

### 摘要（相对 THA4 原版 puppeteer）

| 类别 | 主要改动 |
|------|----------|
| 启动 | 紧凑三按钮启动窗；完整调参窗懒加载；可切换紧凑/完整 |
| 模型 | 加载后立刻默认 pose 预览；Load Last / Load Other |
| 输出 | 独立无边框输出窗；自动平移/缩放；曲线/倾斜/镜像/抗锯齿 |
| 嘴部 | 人脸/音频切换；示波器；设备名显示（pose converter） |
| 摄像头 | 视频来源下拉与刷新；多设备/多后端；DroidCam 优先 MSMF；后台打开防卡死 |
| 持久化 | 开关、周期、背景、镜像、输出窗几何、上次模型路径；张嘴模式及面捕/声音参数 |
| 调查 | DroidCam 问题主要为客户端/虚拟摄像头配置（见 camfix 测试） |

### 修改的文件

- `experiments/puppeteer_load_preview/character_model_mediapipe_puppeteer_load_preview.py`
- `talking-head-anime-4-demo/src/tha4/mocap/mediapipe_face_pose_converter_00.py`
- `packaged/bai_450k/`

## Run (from THA4 venv)

```bat
cd /d E:\THA4_bundle_bai_custom\talking-head-anime-4-demo
set PYTHONPATH=%cd%\src
venv\Scripts\python.exe E:\face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py
```

Or use the launcher in `experiments/puppeteer_load_preview/run_load_preview_puppeteer.bat` (paths may point at `bai_custom`; adjust if needed).

## Camera / DroidCam (2026-05-27)

Isolated testing (`E:\THA4_bundle_bai_custom\camfix\`) showed:

- DroidCam can appear in DirectShow lists when the client is running.
- OpenCV `CAP_DSHOW` on DroidCam index can crash or hang on this machine; MSMF is safer.
- **No picture / wrong device** was ultimately traced to **DroidCam app / virtual camera setup**, not THA4 UI alone.

Camfix sources remain under `bai_custom\camfix\` for reference; not duplicated in this fork root.

## Sync from bai_custom

After changes in `E:\THA4_bundle_bai_custom\`, refresh this fork:

- `experiments/puppeteer_load_preview/character_model_mediapipe_puppeteer_load_preview.py`
- `talking-head-anime-4-demo/src/tha4/mocap/mediapipe_face_pose_converter_00.py`
- `packaged/bai_450k/`
- `HANDOVER.md`

Before large updates, archive the fork root under `his/yyyy-MM-dd_HH-mm-ss/` (see [BACKUP.md](BACKUP.md)).

## Git (optional)

This directory is structured as a fork workspace but may not be `git init` yet. When ready:

```bat
cd /d E:\face-puppeteer-ui-enhancements-ai-code
git init
git add .
git commit -m "Reorganize fork layout; archive 2026-05-27 snapshot under his/"
```

Then add your remote and push to GitHub/GitLab as needed.

### Stable Fork Launcher

Use `面捕启动.bat` at the fork root. It forwards to `experiments\puppeteer_load_preview\run_load_preview_puppeteer.bat` via a **relative path**.

As long as the target file name and location stay unchanged, this launcher remains valid across later iterations/syncs.

其他：该部分由liketocode345与cursor协同开发，由于是ai负责代码实现，本人已确认出现故障时会保护性闪退，如果出现其他意外本人概不负责，如果有想要的功能可以许愿，可使用米强迫liketocode345帮你解决定制问题

## 免责声明 / Disclaimer

本项目为个人实验性质的面捕与角色驱动工具，用于学习、测试与创作流程验证，不构成任何形式的商业级稳定性或适配承诺。

- 在合理硬件配置、正常散热和正确驱动环境下，本项目与常见图形/直播软件类似，通常不会主动对硬件造成物理损坏。
- 本项目不会进行超频、改电压、刷固件等硬件级操作；但高负载场景下可能出现发热、降频、风扇噪音、卡顿、闪退或 `CUDA out of memory`。
- 若与 OBS、快手直播助手、虚拟摄像头等软件同时运行，资源争用会明显增加，可能导致掉帧、无画面、设备占用冲突或程序不稳定。
- 使用者应自行确认设备状态（温度、功耗、驱动版本、音视频设备占用）并承担由系统环境、第三方驱动、虚拟设备链路和个体配置差异导致的风险。
- 因兼容性问题、配置不当、第三方软件冲突或不可预见异常造成的数据丢失、业务中断、设备异常等间接损失，项目维护者不承担责任。

建议在重要直播/录制前先进行单机压力测试，并参考 `HARDWARE_REQUIREMENTS.md` 与 `TROUBLESHOOTING_QA.md` 完成环境校验与预排障。