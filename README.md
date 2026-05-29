[首次部署（GitHub ZIP 下载后） / First-time Deploy](DEPLOY.md)

[English Guide for Native English Speakers](README-EN.md)

# 这是 THA3、THA4、EasyVtuber 三项目的 fork

**新 Agent 请先读 [HANDOVER.md](HANDOVER.md)。**

## 仓库与路径

| 项 | 说明 |
|----|------|
| **发布总库（本目录）** | `E:\tha4fork` — GitHub 推送、对外发布 |
| 研发主仓 | `E:\tha4fork-develop` — 日常开发，稳定后合并到本目录 |
| Fork 远程 | https://github.com/liketocood345/EasyVtuber-with-THA3-THA4 |
| 官方上游 | https://github.com/pkhungurn/talking-head-anime-4-demo |
| 定制代码包 | `face-puppeteer-ui-enhancements-ai-code/` |
| **新 Agent 入口** | **[HANDOVER.md](HANDOVER.md)** |
| **首次部署（ZIP 下载）** | **[DEPLOY.md](DEPLOY.md)** |
| 计划与对接 | [plans/](plans/) |

Git 远程：`origin` = fork，`upstream` = 官方。详见 [FORK_ROOT.md](FORK_ROOT.md)。

> ~~`E:\THA4_bundle_bai_custom`~~ 已废弃，内容已迁入本仓（见 HANDOVER 附录）。

---
骚年，想玩虚拟皮套直播但没钱定制自己的角色？你的显卡该出场了！


## 相对 THA4 原版做了什么（简要）

在官方 `character_model_mediapipe_puppeteer` 基础上，做了一套 **MediaPipe 面捕 + 可调显示变换 + 更好用的 wx 调参界面**，主入口为实验脚本 `character_model_mediapipe_puppeteer_load_preview.py`。

### 1. 界面与窗口

- **默认完整调参窗**启动（`startup_show_full_controls`）；可选 **精简小窗**（3 快捷按钮）与完整窗来回切换
- 角色输出独立无边框窗口，可拖动画布，几何与状态可持久化
- 控件分栏：模型传入 / 输出动态增强 / 后处理；竖滑块、分割条位置记忆

### 2. 显示与跟踪

- 人脸跟踪驱动自动平移、缩放（可关）
- 非线性缩放曲线 + 预览；倾斜映射旋转、镜像作为最后一步
- **输出动态增强校准**：刷新缩放基准并将角色左右归中（不改垂直基准，避免上漂）；支持周期自动校准与平滑过渡
- 可调后处理抗锯齿

### 3. 模型与持久化

- 加载后即显示默认姿态；`Load Last` / `Load Other`
- `load_preview_ui_state.json` 保存开关、滑块、输出窗、嘴部/显示变换等

### 4. 呼吸与嘴部（`mediapipe_face_pose_converter_00.py`）

- 呼吸控件与反应式呼吸
- 嘴部：面捕 / 音频驱动切换，设备选择与 OBS 风格电平条

### 5. 摄像头与视频源

- **窗口捕获**：从 DroidCam 等客户端预览窗抓帧（OBS 式）；与摄像头共用下拉源，记忆上次窗口；**加载模型后**自动连接时窗口捕获优先
- 设备下拉、DirectShow 枚举、多索引/多后端探测
- DroidCam 虚拟摄像头仍可用；后台打开；支持视频/图片文件源

### 6. 外挂图层输出（预留）

- 「外挂图层输出」开关：启用时隐藏内置预览窗，经 `external_layer_output_bridge` 写 `status.json` / `contract.json`（含锚定元数据；RGBA/图层状态导出仍待做）

### 7. 其它交互

- 滑块悬停约 1 秒后才可用滚轮微调（高亮 + 提示）
- 「标定朝向」等校准按钮；已去掉「点任意控件置顶输出窗」（避免控件失效）

### 8. 附带内容

- `packaged/bai_450k/`：示例白腾（代号：九星独行角色） student 模型（yaml + 图）
- 文档：`HANDOVER.md`、`HARDWARE_REQUIREMENTS.md`、`TROUBLESHOOTING_QA.md`、`docs/DOC_INDEX.md` 等
- `his/`：按时间归档的历史快照；`archive_to_his.ps1` 留档（~~`sync_from_bai_custom.ps1`~~ 已废弃，develop → fork 手动合并）

更细的条目见 `face-puppeteer-ui-enhancements-ai-code/CHANGELOG.md`。

“这不是我的选择，但是我选择的。”他总是如是说道。

---

## 总库目录结构（当前）

```
E:\tha4fork\
├── README.md                ← 本文件（Fork 总览，GitHub 首页展示）
├── docs/DOC_INDEX.md        ← 全部 Markdown 索引（最全）
├── plans/                   ← 计划与外挂图层对接说明
├── HANDOVER.md              ← 新 Agent 入口
├── FORK_ROOT.md             ← Git 与路径说明
├── TROUBLESHOOTING_QA.md    ← 排障 Q&A（最全）
├── DEPLOY.md                ← 首次部署（GitHub ZIP）
├── 》》》》start《《《《.bat    ← 一键启动入口（转发到 run_load_preview_puppeteer.bat）
└── face-puppeteer-ui-enhancements-ai-code/   ← 定制 UI 与实验代码
```

## 环境兼容策略

为避免 THA3 与 THA4 依赖不兼容影响运行稳定性，fork 内采用两套依赖环境策略：

- THA4 Student 外壳依赖：`deps/pip/requirements-tha4-student.txt`
- THA3 ONNX+DirectML 依赖：`deps/pip/requirements-tha3-ort.txt`

对应安装脚本分别为 `deps/pip/install_tha4_student_deps.bat` 与 `deps/pip/install_tha3_ort_deps.bat`。该拆分用于降低依赖冲突风险，保证项目稳定运行。

---

## 最近推送

| 提交 | 说明 |
|------|------|
| （待 push） | 文档交叉合并：fork 为 Markdown 权威副本；窗口捕获、输出动态增强校准等 |
| `e107413` | DroidCam 相关说明与 QA 更新 |



---

## 日常流程

1. 在 **`E:\tha4fork`** 运行：`》》》》start《《《《.bat`（或 `run_load_preview_puppeteer.bat`）  
2. 日常开发在 **`E:\tha4fork-develop`**，稳定后合并到本目录再 push  
3. 新 Agent 先读 [HANDOVER.md](HANDOVER.md)  
4. 需要留档时：在 `face-puppeteer-ui-enhancements-ai-code` 运行 `archive_to_his.ps1`  
5. `git add` → `commit` → `git push origin main`
