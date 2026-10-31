# THA4 教师组件

由 DEPLOY [5] 安装到 `addons/tha4_training`，使用独立 `THA4Train.exe`。
该目录绑定外壳、源码、五个教师权重与 pose 数据；不含 Python、venv、torch 或用户任务。
教师默认复用 `runtime/venvs/common`，仅选择 [5] 时追加固定的训练 extras。
未验证兼容的组件可经绑定文件使用项目内私有环境；不使用系统 Python。

队列、输入副本、进度、断点与结果位于安装根内 `workspace/tools/tha4_training`。
`--smoke-ui` 只打开并关闭界面，不开始训练。
维护者 `build.ps1` 只重建 .NET 轻量入口；正常部署使用随源码套件交付的已编译入口。
`package.py` 依据项目 `packaging/resource-lock.json` 打单文件无运行时 ZIP；不上传。

素材要求与训练算法以 [THA4 上游](https://github.com/pkhungurn/talking-head-anime-4-demo) 为准。
