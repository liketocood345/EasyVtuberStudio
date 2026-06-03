# 更新与备份规则 / Backup & Update Rules

EasyVtuberStudio 仓库 **`face-puppeteer-ui-enhancements-ai-code/`** 内用 **`his/` = 只读历史快照** 留档。  
日常开发在 **`E:\easyvtuberstudio-develop`**；稳定后合并到 **`E:\easyvtuberstudio-main`** 再 push。  
~~`E:\THA4_bundle_bai_custom`~~ 已废弃。

---

## 何时备份

- 大改 UI / 摄像头逻辑前想保留可回滚快照
- 准备 `git commit` 或对外分发前
- （可选）从 develop 合并大版本到 fork 前，对 fork 代码包做一次 `archive_to_his.ps1`

同一天可多次备份；**每次用不同秒级文件夹名**，不会互相覆盖。

---

## 文件夹命名（精确到秒）

| 项 | 约定 |
|----|------|
| 格式 | `yyyy-MM-dd_HH-mm-ss` |
| 示例 | `2026-05-27_14-30-45` |
| 位置 | `face-puppeteer-ui-enhancements-ai-code/his/2026-05-27_14-30-45/` |
| 说明 | 使用本地时间；`-` 代替 `:`，便于 Windows 路径 |

**旧快照：** `his/2026-05-27/` 为重组当日仅「日期」命名的首份归档，保留不动。之后一律用秒级目录名。

---

## 标准流程（手动）

在 **`E:\easyvtuberstudio-main\face-puppeteer-ui-enhancements-ai-code\`** 执行：

### 1. 归档当前代码包内容

将**除 `his` 以外**的该目录内容移入新快照文件夹（不要移动 `his` 自身）：

```powershell
$pkg = "E:\easyvtuberstudio-main\face-puppeteer-ui-enhancements-ai-code"
$stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$dest = Join-Path $pkg "his\$stamp"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

Get-ChildItem -LiteralPath $pkg -Force | Where-Object {
    $_.Name -notin @("his", ".git")
} | ForEach-Object {
    Move-Item -LiteralPath $_.FullName -Destination $dest -Force
}
```

### 2. 写入快照说明（建议）

在 `$dest` 下新建 `CHANGELOG_SNAPSHOT.md`，写来源（develop 合并 / 本地 hotfix）、主要改动摘要。

### 3. 恢复或写入新版本

从 **`E:\easyvtuberstudio-develop\face-puppeteer-ui-enhancements-ai-code\`** 复制需要纳入 fork 的文件/目录到 fork 代码包根，或按 diff 手动合并。

-fork **根目录**的 `README.md` 与 **`docs/`** 下说明不在 `his/` 快照内，需在 **`E:\easyvtuberstudio-main\`** 单独维护。

### 4. 更新索引

- 在 `face-puppeteer-ui-enhancements-ai-code/his/README.md` 表格中增加一行
- 在 [CHANGELOG.md](CHANGELOG.md) 注明新快照日期

### 5. 不要移入快照的内容

| 保留不动 | 说明 |
|----------|------|
| `his/` | 历史总目录，归档时**永不**移入子快照 |
| `E:\easyvtuberstudio-main\.git/` | Git 仓库根 |

---

## 一键脚本（推荐）

```bat
powershell -ExecutionPolicy Bypass -File E:\easyvtuberstudio-main\face-puppeteer-ui-enhancements-ai-code\archive_to_his.ps1
```

~~`sync_from_bai_custom.ps1`~~ **已废弃**（仅打印提示）。develop → fork 请手动合并 + 更新 fork 根文档。

---

## 恢复某一版

只读参考：打开 `his\2026-05-27_14-30-45\` 下文件对比。  
若要整版回滚：将该快照目录**内容**复制回 `face-puppeteer-ui-enhancements-ai-code\`（仍不要动 `his` 结构）。

详见 [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md) 第七节 Q38。

## 启动器约定

- 仓库根 **`scripts/launch/》》》》start《《《《.bat`** 优先启动 `EasyVtuberStudio.exe`，否则转发到 `run_load_preview_puppeteer.bat`
- 目标 bat 使用相对路径解析 `face-puppeteer-ui-enhancements-ai-code` 与 `venv`；文件名与相对位置不变则持续有效
