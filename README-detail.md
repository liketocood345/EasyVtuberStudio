# Face Puppeteer UI Enhancements — 详细说明

> **文档权威副本在 fork 发布总库 `E:\tha4fork`（本文件）。**  
> 日常代码开发在 **`E:\tha4fork-develop`**，稳定后合并到 fork 再 push。  
> 完整 Markdown 索引：[docs/DOC_INDEX.md](docs/DOC_INDEX.md)

> **从 GitHub ZIP 首次部署请读 [DEPLOY.md](DEPLOY.md)。**  
> 完整 Markdown 索引见 [docs/DOC_INDEX.md](docs/DOC_INDEX.md)

## Layout

```
E:\tha4fork/
├── README.md                    ← GitHub 首页总览
├── README-detail.md             ← 本文件
├── README-EN.md
├── READMEfrom-main.md           ← 上游 THA4 demo 原 README
├── HANDOVER.md                  ← Agent / 维护者主入口
├── FORK_ROOT.md                 ← Git 远程与路径
├── TROUBLESHOOTING_QA.md        ← 排障（最全）
├── HARDWARE_REQUIREMENTS.md
├── CHANGELOG.md
├── BACKUP.md
├── docs/                        ← 上游模块说明、camfix、training
├── deps/                        ← pip 双环境 + THA3 资产
├── plans/                       ← 多图层计划、外挂接口
├── 》》》》start《《《《.bat
├── run_load_preview_puppeteer.bat
└── face-puppeteer-ui-enhancements-ai-code/
    ├── experiments/puppeteer_load_preview/   ← Load Preview 主脚本
    ├── talking-head-anime-4-demo/            ← THA4 src + venv
    ├── his/                                  ← 代码包历史快照
    └── packaged/bai_450k/                    ← 示例 student 模型
```

## 仓库分工

| 路径 | 角色 |
|------|------|
| **`E:\tha4fork`** | 对外发布、定制客户部署、GitHub push、**文档最全** |
| **`E:\tha4fork-develop`** | 日常改代码；功能可能领先 fork |
| ~~`E:\THA4_bundle_bai_custom`~~ | 已废弃 |

## 启动

**发布 / 定制环境（fork）：**

```bat
cd /d E:\tha4fork
》》》》start《《《《.bat
```

**研发（develop）：**

```bat
cd /d E:\tha4fork-develop
》》》》start《《《《.bat
```

等价于各自根目录的 `run_load_preview_puppeteer.bat`（自动解析 `face-puppeteer-ui-enhancements-ai-code` 与 `venv`）。

## 更新与备份规则

需要留档时：在 **`face-puppeteer-ui-enhancements-ai-code\`** 运行 `archive_to_his.ps1`，将当前内容移入 `his/yyyy-MM-dd_HH-mm-ss/`。

| 项 | 约定 |
|----|------|
| 快照目录名 | `yyyy-MM-dd_HH-mm-ss` |
| 不移入快照 | `his/`、`.git/` |
| develop → fork | 手动合并文件 + 更新 fork 根文档；~~`sync_from_bai_custom.ps1`~~ 已废弃 |

详细步骤见 **[BACKUP.md](BACKUP.md)**。

## 硬件需求

单独运行、与 **OBS / 快手直播助手** 同开时的 CPU/GPU/内存建议，见 **[HARDWARE_REQUIREMENTS.md](HARDWARE_REQUIREMENTS.md)**。

## 训练建议（云服务器 / 角色风格）

### 1) 何时建议用云服务器训练

- 本地显卡显存不足或常与 OBS/直播助手抢资源。
- 需要长时间连续训练（如 450k → 800k）。
- 需要多版本并行试验（不同 `distiller_config` 参数组）。

建议配置：单卡 NVIDIA 12GB+ 可起步，24GB+ 更从容；稳定 SSD 与足够磁盘配额。

实践建议：云端负责 `distill` / checkpoint 迭代，本地只负责 `packaged/.../character_model.yaml` 验证。

### 2) 低色彩复杂度角色的训练建议

对于配色简单、渐变少、大面积纯色角色，常见问题是边缘发灰、眼周脏色或轻微色块抖动。建议：

- 优先降低 body 训练里的颜色混合强度（参考 `bai_450k` 经验）。
- 先做 450k 里程碑观察眼部与脸部，再决定是否继续到 650k/800k。
- 保持角色原图边界干净（透明通道与边缘抗锯齿一致）。

可参考：

- `face-puppeteer-ui-enhancements-ai-code/packaged/bai_450k/TRAINING_NOTES.txt`
- `docs/training/README_BAI_CUSTOM.txt`（历史流程归档）

## 排障 Q&A

常见故障、**窗口捕获**、DroidCam 绕行、fork/develop 区别、定制化持久化预期（第九节），见 **[TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md)**。

## 改动列表 / Change log

完整列表见 **[CHANGELOG.md](CHANGELOG.md)**；代码包历史见 **`face-puppeteer-ui-enhancements-ai-code/his/`**。

### 摘要（相对 THA4 原版 puppeteer）

| 类别 | 主要改动 |
|------|----------|
| 启动 | **默认完整调参窗**；可选精简小窗（朝向/输出增强校准 + 打开完整窗） |
| 模型 | 加载后立刻默认 pose；Load Last / Load Other；THA3 / THA4 双图像源 |
| 输出 | 独立无边框输出窗；自动平移/缩放；**输出动态增强校准**；曲线/倾斜/镜像/抗锯齿 |
| 嘴部 | 人脸/音频切换；示波器；音频驱动有少量延时（界面已注明） |
| 视频源 | **窗口捕获**（DroidCam 预览窗绕行）；加载模型后自动连接（窗口优先） |
| 持久化 | `load_preview_ui_state.json` 保存开关、几何、模型路径等 |
| 外挂 | `external_layer_output_bridge` → `contract.json` / `status.json` |

更细条目见 `face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/README.txt`。

## 摄像头 / DroidCam

- **推荐**：窗口捕获抓取 DroidCam **电脑端预览窗**，勿死磕「DroidCam Video」虚拟摄像头项。
- 隔离测试摘要：[docs/camfix/CAMERA_CHANGES_SUMMARY.md](docs/camfix/CAMERA_CHANGES_SUMMARY.md)。

## Git

```bat
cd /d E:\tha4fork
git pull origin main
git add -A
git commit -m "your message"
git push origin main
```

远程说明见 [FORK_ROOT.md](FORK_ROOT.md)。

## 免责声明 / Disclaimer

本项目为个人实验性质的面捕与角色驱动工具，用于学习、测试与创作流程验证，不构成任何形式的商业级稳定性或适配承诺。

- 高负载场景下可能出现发热、降频、闪退或 `CUDA out of memory`。
- 与 OBS、快手直播助手、虚拟摄像头等同开时资源争用会明显增加。
- 使用者应自行确认设备状态并承担由环境、第三方软件冲突导致的风险。

建议在重要直播/录制前先进行单机压力测试，并参考 `HARDWARE_REQUIREMENTS.md` 与 `TROUBLESHOOTING_QA.md`。
