# THA 与样例发布边界

| 内容 | GitHub CORE | HF 方舟 |
| --- | --- | --- |
| THA3 四变体，共20个权重 | 代码与下载配方 | tha3_models 单包 |
| THA4 教师5权重、pose、源码和独立薄入口 | 来源套件与配方，不含教师大权重 | tha4_training 单包，无 Python/torch |
| bai Student 的 face/body 权重、PNG、YAML | 包含 | seed 同文件、同哈希 |
| GIF、两张刀片配件、四张原始角色图及说明/许可 | 包含 | seed 同路径、同哈希 |
| UI/图层/区域晃动种子 | 消毒后的发布副本 | 与 CORE 同副本；DEPLOY 不拉取 |
| 用户照片、训练队列/存档、校准现场、日志、token、私钥 | 不包含 | 不包含 |

`core_scope.json` 的 sample_directories 与 workspace 白名单是样例双仓的共同来源。HF prepare 必须读取已验证 CORE，不能复制正在使用的 workspace。内部训练溯源、交接文件、开发者私有维护脚本留在本地；不会打入公开包。Windows junction 不跟随打包，外部链接源被拒绝。

2026-10-31 已完成一次真实 THA4 教师首个非零完整自动存档验证，随后暂停。样本、优化器、权重与随机状态保留在本地任务；验证产物不进入上述发布树。这验证首次训练与保存路径，不代表完整训练或最终角色质量验收。

发布状态以 HF 的 index.json 与 GitHub Release 为准；SSH/新机安装另行验收。既有 Git 仓库已跟踪的内部文件须在按 CORE 同步发布时显式移除，gitignore 本身不删除已有跟踪记录。
