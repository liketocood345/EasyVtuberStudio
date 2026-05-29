# History (`his`)

Snapshots moved out of the fork root when backing up or reorganizing this fork.

## 命名规则

| 类型 | 目录名格式 | 示例 |
|------|------------|------|
| **当前标准** | `yyyy-MM-dd_HH-mm-ss` | `2026-05-27_14-30-45` |
| 遗留（仅日期） | `yyyy-MM-dd` | `2026-05-27` |

备份流程见 fork 根目录 **[BACKUP.md](../../BACKUP.md)**；一键归档：本目录上一级的 `archive_to_his.ps1`。

## 改动列表

- **完整列表（当前 + 归档约定）：** [../../CHANGELOG.md](../../CHANGELOG.md)
- **历史索引：** [CHANGELOG.md](CHANGELOG.md)（本目录）

## 按日期归档

| Folder | Date | Description | 改动说明 |
|--------|------|-------------|----------|
| `2026-05-27/` | 2026-05-27（仅日期，遗留） | First packaged draft (pre-reorg) | [2026-05-27/CHANGELOG_SNAPSHOT.md](2026-05-27/CHANGELOG_SNAPSHOT.md) |
| `original_github_2024-02-28/` | 2024-02-28（上游原版时间） | THA4 原版基线（GitHub） | [original_github_2024-02-28/README.md](original_github_2024-02-28/README.md) |

新备份请用秒级目录名；脚本会自动生成并在控制台提示写入本表。

Do not edit files under dated folders unless archiving a new snapshot. Active development: **`E:\tha4fork-develop`**; release docs: **`E:\tha4fork`**.
