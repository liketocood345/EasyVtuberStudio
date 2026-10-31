# 便携部署与独立 THA4 教师（2026-10-30）

主项目 DEPLOY 不再安装系统 Python、不调用 winget 或 Python EXE 安装器、不修改用户/系统 PATH。基础解释器通过官方 NuGet Python 目录包放入 `runtime/python310/`，THA4 Student 在 `workspace/student_venv/`，THA3 在 `addons/tha3_models/venv/`，MediaPipe 可选环境在 `addons/face_puppeteer/venv/`；每个环境的基础 Python 与依赖都须在本项目内。检测到依赖系统 Python 的旧 venv 时，关闭正在使用它的应用后才可修复，旧目录备份仍留在本项目内。

DEPLOY [5] 安装到主项目外的同级 `EasyVtuberStudio-THA4Trainer/`。入口是该目录 `THA4Train.exe`；主程序 exe 不含训练界面或训练逻辑。训练器拥有自己的 Python、依赖、教师权重、姿态数据、队列、缓存和结果。两个应用是两个独立便携目录：分别关闭、删除各自目录即可移除；删除主程序不会擅自删掉独立教师的训练结果，原始用户素材也不会被删除。

拖入角色图及五官遮罩后自动入队；左侧并排两张缩略图，任务显示已完成/未完成/未开始、训练进度、基于实际采样的当前阶段 ETA 和材料位置；人物名称处可拖动排序，支持移除、暂停保存及继续上次训练。设置沿用 THA4 原项目。素材格式及构图需详细阅读[上游要求](https://github.com/pkhungurn/talking-head-anime-4-demo#contraints-on-input-images)：512×512 RGBA 角色 PNG 与同尺寸纯黑白 RGB 五官遮罩 PNG。

HF Bucket：`liketocode789/EasyVtuberStudio`。

- 清单：`packages/tha4_teacher/windows-x64/latest.json`
- 包：`packages/tha4_teacher/windows-x64/2026.10.30/THA4Teacher-portable-win-x64.zip`

以上目录说明及清单已实际上传并回读确认，当前 **ready=false**，尚未上传可发行包。DEPLOY 获取远端清单；ready=true 时要求字节数及 SHA256 完全匹配后解压。尚未发布时可用随源码附带的独立教师 kit + 官方权重，组装到上述同级目录；不得把预留清单当安装成功。

用户最后明确“不要实训，写完即可”。已停止先前短测试，此后仅落盘代码、做静态语法检查和路径预留。此前短测试在 2 个样本后遇到 Windows 状态文件共享冲突；已加入唯一临时文件和替换重试，按要求未再实训复测。不能宣称训练、续训、GUI 和完整 DEPLOY 的最新实现均已运行验收。

独立教师 exe 已构建；它从本目录 `app/` 加载界面/训练代码。主项目冻结的 EasyVtuberStudio.exe 及旧的训练快捷 exe 尚未按本轮启动器源码重建，需使用更新后的 `packaging/build_launchers.ps1` 重新打包（已改为 onedir，运行文件留在本目录 `_internal/`）。当前开发机原有主项目 venv 尚未实际迁移；本轮没有替换系统 Python，也没有触发全量主项目部署。
