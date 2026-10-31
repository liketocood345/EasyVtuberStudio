# 文件夹内安装

解压 GitHub CORE 后，运行根目录 `DEPLOY.bat`。输入档位数字，可组合；回车默认 [1]。

| 档 | 内容 | 依赖与落点 |
| --- | --- | --- |
| 1 | 鼠标/音频 + THA4 Student | root/runtime/python310 与 venvs/common；示例在 CORE |
| 2 | OpenSeeFace | addons/openseeface；完整保留上游冻结 Binary ABI |
| 3 | MediaPipe 面捕 | common 的 face overlay + addons/face_puppeteer/mediapipe |
| 4 | THA3 四种模型 | common 依赖 + addons/tha3_models |
| 5 | 独立 THA4 教师 | addons/tha4_training；common 的可选 teacher extras |
| 6 | NN 后处理 | common 的 output overlay + addons/output_enhancement/ezvtb_data |

基础档不包含 TensorBoard、grpc、quaternion。选择 [5] 后才向同一个 common 追加。没有经验证的版本冲突就不另复制 torch；若有冲突，通过根内绑定指定私有环境。

Python 3.10.11 由 NuGet 固定版本与 SHA256 安装到本文件夹。依赖按 `deps/pip/runtime-artifacts.json` 的版本、来源、哈希与档位闭包安装；torch/vision 使用官方 cu117 wheel。`constraints.txt` 同时约束维护修复入口。禁止系统 Python、用户 site-packages、全局 PATH 安装。

资源顺序：本机已装资源或导入模块校验 → 上游 → 上游失败/坏哈希后 HF。每档 ZIP 与上游规范化结果使用同一组文件哈希；先完整校验暂存内容，再替换已知组件文件，旧字节保留在根内 module-backups。不会下载 UI 种子。公共依赖在目标目录新建 venv，禁止直接搬入另一安装的 venv。

离线 copy-in：把经过验证的 `<module>.zip` 放进 `workspace/imports/modules/`；依赖可放入 `runtime-<profile>.zip`，torch/vision 仍需要对应官方 wheel 缓存。仅有专用资源包不代表包含完整离线公共基座。

源文件/素材、缓存、下载、日志、教师队列和存档均在所选安装根内。`addons/tha4_training/THA4Train.exe` 是独立训练界面；普通部署和 `--smoke-ui` 不开始训练。旧独立教师目录和其他安装不会自动迁移或删除。

改动安装位置后，如旧 venv 的绝对路径不可用，重新运行 DEPLOY 在新路径重建依赖。运行时不会借系统 Python 或旁边另一个安装补位。

环境验收使用真实入口、所需初始化和真实 prefix/module 路径无异常；不把动作质量、面捕识别成功或 FPS 当作环境合并门槛。

资源地图和实装结构见 [部署布局](deployment-design-20261031/部署设计与Cursor分工.md)。HF 的当前发布边界见 [方舟说明](HF_BUCKET_MIRROR.md)。
