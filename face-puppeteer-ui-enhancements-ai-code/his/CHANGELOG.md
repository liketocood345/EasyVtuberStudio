# 历史改动索引 / History Change Log Index

完整改动列表见 fork 根目录：**[../CHANGELOG.md](../CHANGELOG.md)**

## 按时间归档

新快照目录名：**`yyyy-MM-dd_HH-mm-ss`**（见 [BACKUP.md](../BACKUP.md)）。

| 文件夹 | 时间标签 | 说明 | 改动列表 |
|--------|----------|------|----------|
| `2026-05-27/` | 2026-05-27（遗留，无时分秒） | 首次 fork 草稿（重组前根目录快照） | 见该目录内 `README.md`、`HANDOVER.md` |
| `original_github_2024-02-28/` | 2024-02-28T09:50:41Z（GitHub UTC） | **原版**基线标注（上游首次提交） | [original_github_2024-02-28/README.md](original_github_2024-02-28/README.md) |

（此后每次 `archive_to_his.ps1` 会新增一行，请把控制台输出的 `his\…` 路径补到 [README.md](README.md) 上表。）

## 仅摄像头实验（未放入本 fork 根目录）

路径：`E:\THA4_bundle_bai_custom\camfix\`

| 文件 | 说明 |
|------|------|
| `CAMERA_CHANGES_SUMMARY.md` | 原版 + 仅摄像头区升级，用于隔离 UI 干扰 |
| `character_model_mediapipe_puppeteer.camfix.py` | 可双击 `run_camfix_puppeteer.bat` 运行 |

调查结论已写入根目录 `CHANGELOG.md` 与 `README.md` 的 DroidCam 小节。
