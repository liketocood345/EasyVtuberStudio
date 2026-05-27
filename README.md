# Fork 总览

## 仓库与路径

| 项 | 说明 |
|----|------|
| 本地总库 | `E:\tha4fork` |
| Fork 远程 | https://github.com/liketocood345/talking-head-anime-4-demo |
| 官方上游 | https://github.com/pkhungurn/talking-head-anime-4-demo |
| 活跃开发 | `E:\THA4_bundle_bai_custom`（改完再同步进总库） |
| 定制代码包 | `face-puppeteer-ui-enhancements-ai-code/` |

Git 远程：`origin` = fork，`upstream` = 官方。详见 [FORK_ROOT.md](FORK_ROOT.md)。

---

## 相对 THA4 原版做了什么（简要）

在官方 `character_model_mediapipe_puppeteer` 基础上，做了一套 **MediaPipe 面捕 + 可调显示变换 + 更好用的 wx 调参界面**，主入口为实验脚本 `character_model_mediapipe_puppeteer_load_preview.py`。

### 1. 界面与窗口

- 紧凑启动窗（3 按钮）+ 完整调参窗懒加载、可来回切换
- 角色输出独立无边框窗口，可拖动画布，几何与状态可持久化
- 控件分栏：模型传入 / 输出动态增强 / 后处理；竖滑块、分割条位置记忆

### 2. 显示与跟踪

- 人脸跟踪驱动自动平移、缩放（可关）
- 非线性缩放曲线 + 预览；倾斜映射旋转、镜像作为最后一步
- 可调后处理抗锯齿

### 3. 模型与持久化

- 加载后即显示默认姿态；`Load Last` / `Load Other`
- `load_preview_ui_state.json` 保存开关、滑块、输出窗、嘴部/显示变换等

### 4. 呼吸与嘴部（`mediapipe_face_pose_converter_00.py`）

- 呼吸控件与反应式呼吸
- 嘴部：面捕 / 音频驱动切换，设备选择与 OBS 风格电平条

### 5. 摄像头与视频源

- 设备下拉、DirectShow 枚举、多索引/多后端探测
- DroidCam 优先 MSMF；后台打开摄像头；支持视频/图片文件源

### 6. 外挂图层输出（预留）

- 「外挂图层输出」开关：启用时隐藏内置预览窗，经 `external_layer_output_bridge` 写 `status.json` / `contract.json`（含锚定元数据；RGBA/图层状态导出仍待做）

### 7. 其它交互

- 滑块悬停约 1 秒后才可用滚轮微调（高亮 + 提示）
- 「标定朝向」等校准按钮；已去掉「点任意控件置顶输出窗」（避免控件失效）

### 8. 附带内容

- `packaged/bai_450k/`：示例白猫 student 模型（yaml + 图）
- 文档：`HANDOVER.md`、`HARDWARE_REQUIREMENTS.md`、`TROUBLESHOOTING_QA.md` 等
- `his/`：按时间归档的历史快照；`sync_from_bai_custom.ps1` / `archive_to_his.ps1` 维护同步

更细的条目见 `face-puppeteer-ui-enhancements-ai-code/CHANGELOG.md`。

---

## 总库目录结构（当前）

```
E:\tha4fork\
├── README.md                ← 本文件（Fork 总览，GitHub 首页展示）
├── READMEfrom-main.md       ← 上游 THA4 demo 原说明
├── FORK_ROOT.md             ← Git 与路径说明
└── face-puppeteer-ui-enhancements-ai-code/   ← 定制 UI 与实验代码
```

---

## 最近推送

| 提交 | 说明 |
|------|------|
| `5bfecb5` | 新增 `face-puppeteer-ui-enhancements-ai-code/` 与 `FORK_ROOT.md` |

在线浏览定制包：  
https://github.com/liketocood345/talking-head-anime-4-demo/tree/main/face-puppeteer-ui-enhancements-ai-code

---

## 日常流程

1. 在 `E:\THA4_bundle_bai_custom` 开发、跑 `run_load_preview_puppeteer.bat` 验证  
2. 需要留档时：在定制包目录运行 `archive_to_his.ps1`，再 `sync_from_bai_custom.ps1`  
3. 将更新后的 `face-puppeteer-ui-enhancements-ai-code` 拷入或同步到 `E:\tha4fork`  
4. `git add` → `commit` → `git push origin main`
