# Windows EXE 打包计划（PyInstaller 备选路线）

> **注意：** 主发行路线已改为 **便携版 + 薄启动器 exe**，见 [PORTABLE_RELEASE.plan.md](PORTABLE_RELEASE.plan.md)。  
> 本文档保留 PyInstaller **全量冻结**方案，供将来「无 venv 目录」极简版参考。  
> **应用图标（两路线共用）：** [assets/branding/app-icon-source.ico](../assets/branding/app-icon-source.ico)

---

## 0. 与「隔壁聊天」口径对齐

| 说法 | 实际含义 | 本计划要做的事 |
|------|----------|----------------|
| README「Packaging Status / 已打包可用」 | 仓库内 `venv` + `deps/` + bat 启动，**无需开发者再拼目录** | 保留；exe 是**下一层**分发形态 |
| DEPLOY.md | GitHub ZIP → 装依赖 → `run_load_preview_puppeteer.bat` | exe 版应 **跳过 Python/pip 步骤**，仍可能需要 **THA4 模型 data 包** |
| oid [858] | 依赖指向**仓库内相对路径**，禁止写死 `E:\...` | 冻结后统一走 `get_app_root()`，禁止依赖 cwd |
| 当前 debug 项（透明捕获帧率 / 窗口捕获） | **已标记顽固，暂停修理** | 不阻塞 P0–P2；release 前再开回归清单 |

---

## 1. 交付物定义

### 1.1 用户可见产物

| 产物 | 说明 |
|------|------|
| `THA4LoadPreview.exe` | 主程序（PyInstaller **onedir** 推荐；入口同 bat） |
| `THA4LoadPreview/` 目录 | exe + `_internal/` 依赖与资源 |
| 桌面/开始菜单快捷方式 | 图标 = `app-icon-source.ico` |
| `README-发布.txt` | 首次运行：模型包下载、摄像头/OBS、日志路径 |

### 1.2 不包含在 exe 内（首期）

| 内容 | 原因 |
|------|------|
| THA4 Student 全量 checkpoint（数百 MB～GB） | 与 DEPLOY 一致：首次运行引导下载或放 `data/` |
| 用户私有 `load_preview_ui_state.json` / `basic_layers/` | 写入 `%APPDATA%\THA4LoadPreview\` |
| DroidCam / 虚拟摄像头驱动 | 系统级，见 TROUBLESHOOTING_QA |

### 1.3 必须打进包或 sidecar 的资源

| 路径 | 用途 |
|------|------|
| `face-puppeteer-ui-enhancements-ai-code/talking-head-anime-4-demo/src/tha4/` | THA4 源码 import |
| `face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/*.py` | 主 UI、图层、窗口捕获 |
| `deps/tha3/`（`tha3_src` + `ezvtuber_rt` + 必要 models 子集） | THA3 黑盒 |
| MediaPipe face landmarker `.task` | 面捕（路径需在冻结后解析） |
| `assets/branding/app-icon-source.ico` | exe / 窗口图标 |

---

## 2. 技术选型

| 项 | 选择 | 理由 |
|----|------|------|
| 打包工具 | **PyInstaller 6.x** | wxPython / OpenCV / MediaPipe 社区案例多 |
| 布局 | **onedir** | torch + onnxruntime 体积大；onefile 启动慢、杀毒误报高 |
| Python | 与 `venv` 一致（3.10/3.11，以 develop 实测为准） | 与现有 `deps/pip` 脚本一致 |
| CUDA | **CPU 默认可运行**；可选 `+cuda` 变体文档说明 | 降低首包复杂度 |
| 安装器（可选 P3） | Inno Setup | 创建快捷方式、写卸载项、关联图标 |

**不推荐首期：** Nuitka（编译时间长）、cx_Freeze（hidden import 维护成本高）。

---

## 3. 实施阶段

### P0 — 品牌与版本（1 天）

- [x] 保存源图 `assets/branding/app-icon-source.png`
- [x] 生成 `assets/branding/app-icon-source.ico`（16–256 多尺寸）
- [ ] 在 `packaging/version.txt` 写 semver（与 CHANGELOG 对齐）
- [ ] 主窗口 / wx `App` 设置图标（开发版与 exe 共用同一路径解析）

**图标说明：** 当前源图为**黑底**圆形构图，适合 exe 与任务栏；若需透明底，另存一版 PNG 再重新生成 ico。

### P1 — 冻结路径引导（2–3 天，阻塞项）

在 `tha3_paths.py`（或新建 `app_paths.py`）增加：

```python
def get_app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return find_repo_root()
```

需逐项替换/扩展：

| 模块 | 调整 |
|------|------|
| `find_repo_root()` | frozen 时返回 exe 目录或 `_internal` 旁资源根 |
| `load_preview_ui_state.json` | 改到 `%APPDATA%/THA4LoadPreview/` |
| `basic_layers/` | 同上或用户文档目录 |
| MediaPipe model | `--add-data` 到 spec，运行时 `sys._MEIPASS` 查找 |
| `deps/tha3` | 整树 `--add-data` 或 sidecar `deps/` 与 exe 并列（推荐 **并列**，便于 THA3 模型热更新） |

**验收：** 在未安装 Python 的机器上，从**拷贝出来的 onedir 文件夹**双击 exe 能弹出紧凑启动窗。

### P2 — PyInstaller spec（3–5 天）

目录建议：

```text
packaging/
  load_preview.spec          # PyInstaller spec
  build_release.bat          # 一键：clean → pyinstaller → smoke
  hooks/                     # 自定义 hook（mediapipe、wx、torch）
  version.txt
```

`load_preview.spec` 要点：

```python
# 入口
entry = ".../character_model_mediapipe_puppeteer_load_preview.py"
icon = "assets/branding/app-icon-source.ico"

# hiddenimports（初版清单，build 后补全）
# wx, wx.adv, mediapipe, cv2, torch, PIL, sounddevice, numpy, ...

# collect_all / datas
# - tha4 package tree
# - puppeteer_load_preview experiment py + json templates
# - deps/tha3 (或 COLLECT 外挂)
# - mediapipe task model
```

**构建命令（草案）：**

```bat
cd /d E:\easyvtuberstudio-develop
venv\Scripts\pip install pyinstaller
venv\Scripts\pyinstaller packaging\load_preview.spec --noconfirm
```

**冒烟：** 打包完成后在本机运行 `dist\THA4LoadPreview\THA4LoadPreview.exe`，加载 `bai_450k`（若 data 已就位），面捕 30 秒无崩溃。

### P3 — 发布结构与安装器（可选，2 天）

```text
Release/
  THA4LoadPreview/           # onedir 输出
  data/                      # 可选：附带示例模型或 download.url
  README-发布.txt
  install.iss                # Inno Setup
```

安装器行为：

- 安装到 `%ProgramFiles%\THA4LoadPreview\`
- 快捷方式图标 = 白狼 ico
- 不覆盖 `%APPDATA%\THA4LoadPreview\` 已有配置

### P4 — 双图像源与依赖体积（并行优化）

| 问题 | 策略 |
|------|------|
| THA3 ort + THA4 torch 同包过大 | 首期 **全功能单包**；若 >2GB 再拆 `THA4LoadPreview-THA3.exe` / `-Full.exe` |
| protobuf / mediapipe 冲突 | 沿用 `deps/pip/repair_mediapipe_protobuf.bat` 逻辑，写入 spec 前检查 |
| debug 埋点 `debug-3353ed.log` | **已完成（2026-06-24）**：发布版已剥离 `longrun_freeze_debug` / NDJSON 脚手架；见 `CHANGELOG.md` §2026-06-24 |

---

## 4. 风险与缓解

| 风险 | 缓解 |
|------|------|
| PyInstaller 漏掉 wx / mediapipe 动态库 | `build_release.bat` 后跑 `smoke_load_preview.py` + 手动开 UI |
| 路径仍指向 develop 绝对路径 | grep `E:\\\\tha4fork`；frozen 单测 |
| 杀毒软件误报 | 代码签名（长期）；短期提供 zip + 校验和 |
| 顽固 bug（透明捕获掉帧）| 发布说明标注「实验功能」；不阻塞 P1/P2 |
| PrintWindow ctypes（已修 develop）| 合并到打包分支后再 build |

---

## 5. 验收门（Release Ready）

1. **冷机：** 无 Python 的 Win10/11 可双击 exe 启动 UI  
2. **图标：** 资源管理器、任务栏、Alt+Tab 均为白狼图标  
3. **路径：** 配置写入 `%APPDATA%`，升级安装不丢设置  
4. **THA4：** 在按 DEPLOY 放置 data 后可 Load 模型并面捕  
5. **THA3：** 切换图像源可渲染（deps/tha3 可达）  
6. **文档：** fork `README-EN.md` 增加「EXE 版」段落，与 ZIP 版区分  

---

## 6. 建议执行顺序（下一步）

1. **合并 develop → fork** 当前窗口捕获修复与路径卫生改动  
2. **P1** 实现 `get_app_root()` + APPDATA 持久化（开发模式可开关测试）  
3. **P2** 首版 `load_preview.spec`，本机产出 `dist/` 并记录体积与缺失 DLL  
4. **P0** 主窗口 `SetIcon` + `build_release.bat`  
5. 再考虑 Inno Setup  

---

## 7. 暂缓项（与 debug 会话同步）

以下 **不纳入 exe v0.1 阻塞**，但需在 CHANGELOG / 发布说明中注明：

- 透明捕获输出帧率优化（图层 + async capture）  
- 窗口捕获 PrintWindow 以外场景的极端 HWND  
- 图层 L2/L3 与「按组打包保存」（oid 图层素材打包，与 **本 exe 打包计划无关**）  

---

## 8. 文件索引

| 文件 | 说明 |
|------|------|
| [assets/branding/app-icon-source.png](../assets/branding/app-icon-source.png) | 图标源图 |
| [assets/branding/app-icon-source.ico](../assets/branding/app-icon-source.ico) | Windows 多尺寸 ico |
| [run_load_preview_puppeteer.bat](../scripts/launch/run_load_preview_puppeteer.bat) | 当前开发入口（spec 应对齐其行为） |
| [packaging/build_release.bat](../packaging/build_release.bat) | 一键构建（P2 启用） |
| [packaging/load_preview.spec](../packaging/load_preview.spec) | PyInstaller 规格（占位） |
