# 更新与备份规则 / Backup & Update Rules

本 fork 用 **根目录 = 当前版本**，**`his/` = 只读历史快照**。日常开发仍在 `E:\THA4_bundle_bai_custom\`，需要打包或留档时再动本仓库。

---

## 何时备份

在以下情况执行一次「归档 → 换新」：

- 从 `bai_custom` 复制一整版新内容进 fork 前
- 大改 UI / 摄像头逻辑前想保留可回滚快照
- 准备 `git commit` 或对外分发前

同一天可多次备份；**每次用不同秒级文件夹名**，不会互相覆盖。

---

## 文件夹命名（精确到秒）

| 项 | 约定 |
|----|------|
| 格式 | `yyyy-MM-dd_HH-mm-ss` |
| 示例 | `2026-05-27_14-30-45` |
| 位置 | `his/2026-05-27_14-30-45/` |
| 说明 | 使用本地时间；`-` 代替 `:`，便于 Windows 路径 |

**旧快照：** `his/2026-05-27/` 为重组当日仅「日期」命名的首份归档，保留不动。之后一律用秒级目录名。

---

## 标准流程（手动）

在 fork 根目录 `E:\face-puppeteer-ui-enhancements-ai-code\` 执行：

### 1. 归档当前根目录

将**除 `his` 以外**的根目录内容移入新快照文件夹（不要移动 `his` 自身）：

```powershell
$fork = "E:\face-puppeteer-ui-enhancements-ai-code"
$stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$dest = Join-Path $fork "his\$stamp"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

Get-ChildItem -LiteralPath $fork -Force | Where-Object {
    $_.Name -notin @("his", ".git")
} | ForEach-Object {
    Move-Item -LiteralPath $_.FullName -Destination $dest -Force
}
```

### 2. 写入快照说明（建议）

在 `$dest` 下新建 `CHANGELOG_SNAPSHOT.md`，写一两句：来源（如 `bai_custom`）、主要改动摘要、是否含 camfix 结论。

### 3. 复制新版本到根目录

从 `E:\THA4_bundle_bai_custom\` 复制需要纳入 fork 的文件/目录到 fork 根目录，或运行：

```bat
powershell -ExecutionPolicy Bypass -File E:\face-puppeteer-ui-enhancements-ai-code\sync_from_bai_custom.ps1
```

按需补回根目录的 `README.md`、`CHANGELOG.md`、`BACKUP.md`（若未从源目录带出）。

### 4. 更新索引

- 在 [his/README.md](his/README.md) 表格中增加一行：`his/2026-05-27_14-30-45/`
- 在 [CHANGELOG.md](CHANGELOG.md) 顶部或「历史快照」小节注明新日期目录
- 根目录 [README.md](README.md) 的 Layout 示例可只保留最新一条 + 指向 `his/`

### 5. 不要移入快照的内容

| 保留在 fork 根 / 不动 | 说明 |
|----------------------|------|
| `his/` | 历史总目录，归档时**永不**移入子快照 |
| `.git/` | 若已 `git init`，留在仓库根 |

---

## 一键脚本（推荐）

```bat
powershell -ExecutionPolicy Bypass -File E:\face-puppeteer-ui-enhancements-ai-code\archive_to_his.ps1
```

可选：归档后自动从 `bai_custom` 同步：

```bat
powershell -ExecutionPolicy Bypass -File E:\face-puppeteer-ui-enhancements-ai-code\archive_to_his.ps1 -SyncFromBaiCustom
```

脚本会输出本次快照路径，例如：`his\2026-05-27_14-30-45\`。

---

## 与 `sync_from_bai_custom.ps1` 的关系

| 脚本 | 作用 |
|------|------|
| `archive_to_his.ps1` | 把当前根目录打进 `his/时间戳/`，清空根（保留 `his`、`.git`） |
| `sync_from_bai_custom.ps1` | 从 `bai_custom` **覆盖** fork 根目录中的代码与 `HANDOVER.md` |

推荐顺序：**先 `archive_to_his.ps1`，再 `sync_from_bai_custom.ps1`**。

`CHANGELOG.md`、`README.md` 会随快照一起移入 `his/时间戳/`。归档后根目录仅保留 `BACKUP.md` 与两个脚本；从 `bai_custom` 同步代码后，请把 `README.md` / `CHANGELOG.md` 从上一版快照复制回根目录，或按本次改动更新它们。

---

## 恢复某一版

只读参考：打开 `his\2026-05-27_14-30-45\` 下文件对比。  
若要整版回滚：将该快照目录**内容**复制回 fork 根（仍不要动 `his` 结构），或再执行一次归档后手动还原。

## 面捕启动器稳定性约定

- 根目录 `面捕启动.bat` 使用相对路径转发到：`experiments\puppeteer_load_preview\run_load_preview_puppeteer.bat`
- 后续迭代中，只要这个目标程序**文件名与相对位置不变**，`面捕启动.bat` 会持续有效
- 如目标路径发生变更，需要同步修改 `面捕启动.bat` 内的 `TARGET` 变量
