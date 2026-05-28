# Git 与本地路径说明

## 远程

| 远程名 | 地址 | 用途 |
|--------|------|------|
| **origin** | https://github.com/liketocood345/EasyVtuber-with-THA3-THA4 | 本 fork（默认 push/pull） |
| **upstream** | https://github.com/pkhungurn/talking-head-anime-4-demo | 官方上游（`git fetch upstream`） |

## 本地目录

| 路径 | 角色 |
|------|------|
| **`E:\tha4fork-develop`** | **研发主仓**（实验代码、`plans/`、`deps/`、本文件所在仓库） |
| `E:\tha4fork` | 对外发布总库（README 首页；稳定后从 develop 合并） |

新 Agent 请读 **`E:\tha4fork-develop\HANDOVER.md`**。

## 常用命令（develop 主仓）

```bat
cd /d E:\tha4fork-develop
git pull origin main
git add -A
git commit -m "your message"
git push origin main
```

同步上游（可选）：

```bat
git fetch upstream
git merge upstream/main
```
