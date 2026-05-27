# THA3 运行时资产（仓库内路径）

代码通过 `tha3_paths.py` → `deps.repo_paths.get_tha3_bundle_root()` 访问本目录，**不**再依赖 `vendor/easyvtuber` 或 `F:\EasyVtuber\...`。

## 目录约定

| 子目录 | 对应原 EasyVtuber 路径 |
|--------|-------------------------|
| `tha3_src/` | `tha3/` Python 包 |
| `ezvtuber_rt/` | `ezvtuber-rt/`（含 `ezvtb_rt/tha3_ort.py`） |
| `models/tha3/` | `data/models/tha3/`（ONNX，体积大） |
| `images/` | `data/images/`（512 RGBA 立绘示例） |

## 填充

```powershell
# 在仓库根目录
powershell -ExecutionPolicy Bypass -File deps\tha3\populate_tha3_bundle.ps1 -SourceRoot "D:\path\to\EasyVtuber_v0.8.1\EasyVtuber_v0.8.1"
```

省略 `-SourceRoot` 时脚本会尝试常见安装路径；复制目标始终为**本仓库**下的 `deps/tha3/`。

## Git

`models/**/*.onnx` 体积约 2.5GB，默认列入 `.gitignore`。克隆后请运行填充脚本，或使用 Release 附带的模型包解压到 `deps/tha3/models/`。
