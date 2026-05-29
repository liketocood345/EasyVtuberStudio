# Fork 仓库内依赖（repo-relative）

本目录下的路径均相对于 **fork 仓库根目录**（含 `deps/tha3` 或 `deps/pip` 的目录），不使用 `E:\...` 等机器绝对路径。

## 结构

| 路径 | 内容 |
|------|------|
| `deps/pip/` | Load Preview Python 依赖清单与安装脚本 |
| `deps/tha3/` | THA3 黑盒运行时资产（源码、ORT 脚本、ONNX、示例立绘） |
| `deps/repo_paths.py` | 代码内解析仓库根目录的工具 |

## 首次填充 THA3 资产

若 `deps/tha3/models` 为空，在仓库根目录执行（需本机已安装 EasyVtuber，仅用于**一次性复制**进仓库）：

```powershell
powershell -ExecutionPolicy Bypass -File deps\tha3\populate_tha3_bundle.ps1
```

也可将同等目录结构**手动拷贝**到 `deps/tha3/`（见 `deps/tha3/README.md`）。

## Python 依赖

```bat
deps\pip\install_all_image_source_deps.bat
```

`venv` 默认位于 `face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\venv`（相对仓库根；亦兼容根目录 `talking-head-anime-4-demo\venv`）。
