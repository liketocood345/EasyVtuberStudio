# EasyVtuberStudio — 安装与首次使用

**软件名称：** EasyVtuberStudio（主程序 `EasyVtuberStudio.exe`）  
**下载地址：** https://github.com/liketocood345/EasyVtuberStudio  

排障请看 [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) · 电脑配置请看 [HARDWARE_REQUIREMENTS.md](HARDWARE_REQUIREMENTS.md) · 可选包目录见 [ADDONS_LAYOUT.md](ADDONS_LAYOUT.md)

---

## 你需要准备什么

| 项 | 要求 |
|----|------|
| 系统 | Windows 10 / 11（64 位） |
| 显卡 | **NVIDIA 独显**（建议 6 GB 以上显存） |
| 网络 | 安装时要联网（会自动下载较大文件） |
| 磁盘 | 预留约 **15 GB** 空闲空间（完整可选包） |
| 其他 | 建议安装 [7-Zip](https://www.7-zip.org/)（解压大文件更稳） |

---

## GitHub ZIP 里有什么（CORE）

解压后**已包含**：主程序、`DEPLOY.bat`、THA4 Student 示例角色（bai）、THA3/THA4 **代码**。

**不包含**（需运行 `DEPLOY.bat` 安装对应档位）：

- Python + PyTorch 最小运行时（档位 **[1] basic_run** → `workspace/student_venv`）
- 摄像头面捕完整环境（档位 **[2] face_puppeteer**）
- THA3 立绘权重（档位 **[3] tha3_models**）
- THA4 训练 Teacher 权重（档位 **[4] tha4_training**）

---

## 安装（三步）

### 第 1 步：下载并解压

1. 打开 https://github.com/liketocood345/EasyVtuberStudio  
2. **Code** → **Download ZIP**  
3. 解压到**路径尽量短**的文件夹，例如：`D:\EasyVtuberStudio\`

解压后应能看到：

```text
EasyVtuberStudio-main\
├── EasyVtuberStudio.exe
├── DEPLOY.bat
├── RESET_ADDON.bat
├── addons\README.md
└── …
```

### 第 2 步：安装（DEPLOY 四档 Y/N）

1. 可先双击 **`EasyVtuberStudio.exe`**：若本目录**已有**满足 Mouse + THA4 Student 的运行时（`student_venv`、或已装面捕 runtime、或系统 Python 已能 `import torch, wx`），会**直接启动**。
2. 若未就绪，会提示运行 **`DEPLOY.bat`**（exe **不会**在后台自动下载安装）。

双击 **`DEPLOY.bat`**，对四个档位**逐个**询问 Y/N（**直接按 Enter = 默认**）：

| 档位 | 默认 Enter | 内容 |
|------|------------|------|
| **[1] basic_run** | **是 (Y)** | Mouse + THA4 Student 最小运行时（PyTorch + wx，约 2–4 GB） |
| **[2] face_puppeteer** | 否 (N) | 摄像头面捕（MediaPipe + 完整 runtime） |
| **[3] tha3_models** | 否 (N) | THA3 立绘权重 |
| **[4] tha4_training** | 否 (N) | THA4 训练 / 蒸馏 |

**首次使用推荐：** 四个问题都按 Enter → 只装 **[1] basic_run**，不装面捕 / THA3 / THA4 三个大包。

安装可能需要 **10–40 分钟**。若电脑没有 Python 3.10/3.11，DEPLOY 会自动安装。

**【请谨慎】** 重复安装 **[2] face_puppeteer** 可能覆盖 `addons\face_puppeteer\venv`；已下载的模型包通常会跳过。

### 第 3 步：启动软件

双击 **`EasyVtuberStudio.exe`**。若仍提示未就绪，再运行 **`DEPLOY.bat`** 补装对应档位。

**训练工具（可选）：** 先安装档位 **[4]**，再运行 `scripts\launch\THA4Train.exe`。

---

## 卸载某个可选包

双击 **`RESET_ADDON.bat`**，选择要删除的包；或手动删除 `addons\<包名>\` 后运行：

```powershell
powershell -ExecutionPolicy Bypass -File packaging\reconcile_portable_layout.ps1 -PortableRoot "你的解压目录"
```

---

## 第一次怎么用

1. 调参窗点 **「加载其他 THA4 Student / Load Other」**  
2. 选择自带的 bai 示例或 `character_model.yaml`  
3. **Mouse + Audio** 模式无需摄像头即可使用；**摄像头面捕**需先安装档位 **[2] face_puppeteer**，再在 Model Input 切换 **Face capture (MediaPipe)**  

**THA3 立绘：** 界面切换 THA3；缺模型时在 DEPLOY 中确认 **[3] tha3_models**。

---

## 安装成功了吗？（自检）

```text
[ ] 已从 GitHub 下载 ZIP 并解压
[ ] 已运行 DEPLOY 档位 [1] basic_run（或本机已有 torch+wx 运行时）
[ ] 双击 EasyVtuberStudio.exe 能打开且不闪退
[ ] 能 Load Other 加载角色并看到画面
```

---

## 常见问题（简版）

| 情况 | 怎么办 |
|------|--------|
| DEPLOY 很快失败 | 检查网络与磁盘；查看 `workspace\deploy.log`；确认从含 `EasyVtuberStudio.exe` 的目录运行 |
| 已装 [1] 再装 [2] 失败 | 查看 `deploy.log` 是否在 face bootstrap；确认 `packaging\bootstrap_portable.ps1` 为新版（`python -m pip`） |
| 双击 exe 无窗口 | 先完成 [1] basic_run 或 [2] face_puppeteer；查看 `workspace\launch.log` |
| 面捕模式切换报错 | 确认已装 [2]；若 `NameError: MOCAP_INPUT_MODE_MEDIAPIPE`，更新到最新 CORE |
| 提示缺模型 | DEPLOY 对应档位：[2] 面捕 / [3] THA3 / [4] THA4 训练 |
| 升级软件 | 重新下载 ZIP；**保留** `workspace\` 与 `addons\` |

更多问题：[TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md)

---

*适用于从 GitHub 压缩包安装 EasyVtuberStudio 的普通用户。*
