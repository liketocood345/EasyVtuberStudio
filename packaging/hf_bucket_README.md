# HF 后备方舟（2026.10.31-r1）

HF Bucket `liketocode789/EasyVtuberStudio` 是可恢复专用资源的后备方舟。下载顺序为：已安装且哈希正确的资源 / 本机 copy-in 模块 → 上游原提供商 → 下载失败或内容哈希不符后使用 HF。正常上游路径不读取 HF 索引、不准备 HF 客户端。

GitHub CORE 含主薄入口、DEPLOY、代码、bai 示例角色和 GIF 配件、已消毒的 UI/图层/晃动种子。素材在 DEPLOY 前完整存在；运行仍需安装依赖。DEPLOY 不下载、不覆盖种子。

许可证：与 GitHub CORE 共用仓库根 `LICENSE`（hf-stage 内为同一文件拷贝）。原创 BSD-3，上游全文在同一文件。

HF 待发目录：

```text
index.json / README.md
seed/data/character_models/…/bai_450k/
seed/workspace/{load_preview_ui_state.json,basic_layers/,region_wobble_mask*.png}
packages/windows-x64/<module>/<version>/<module>.zip
  mediapipe / openseeface / tha3_models / tha4_training / output_enhancement
```

教师 ZIP 含独立薄 EXE、app、自己的 THA4 源码、五个权重、pose、许可与安装元数据。它借用安装根的 common 依赖，不装入主 EXE，不包含 runtime、venv、torch、训练队列或用户素材。

Python / torch / torchvision 分发不进入 HF。OpenSeeFace 的冻结 Binary ABI 保持完整，包括该二进制实际依赖的 Python DLL；它不等同于给全项目再打包一份通用 Python。未经验证不能拆掉这些 DLL。

公共资源按低热度、老版本稀缺性和消失风险优先，再考虑体积；不按容量凑满。当前 MP / OSF / 转换 ONNX 已随各档归档；其他通用 wheel 默认只在本机模块缓存，未宣称都有 HF 备份。

维护者只能用项目内 `workspace/release/hf-stage` 白名单目录。禁止把 develop 或旧 HF 整树镜像作为上传源。`sync_develop_to_hf_bucket.ps1` 默认仅验证/列计划；实际远程操作须显式 `-Publish`。不可变分包与种子先上传，index 最后上传；上传后仍需下载回读与 GitHub 发布验收。

发布索引的 `published` 字段记录当前状态：分包、样例、许可上传并完整回读后，索引最后发布为 true。后续 SSH/新机安装仍须单独验收。安装器使用 CORE 内固定文件契约和不可变包哈希，不接受未验证的远程 latest。
