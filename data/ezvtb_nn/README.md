# NN 后处理模型

DEPLOY [6] 安装 RIFE、waifu2x、Real-ESRGAN 的固定 ONNX。CORE 只有说明，不含这些权重。

原提供商数据包：[ezvtuber-rt Google Drive](https://drive.google.com/file/d/1pWKIpjWeqfpa3Rub185FVvxDr5H09pOi/view)。先使用本机已装内容或 copy-in 模块，再尝试该上游；失败或模型哈希不符才用 HF `packages/windows-x64/output_enhancement/<version>/output_enhancement.zip` 备用。

权威文件哈希在 `packaging/resource-lock.json`，已安装模型在 `addons/output_enhancement/ezvtb_data`，`data/ezvtb_nn` 是兼容视图。推理运行库复用安装根内 common 的 output overlay。DEPLOY 不修改用户种子或训练任务。

许可沿用各上游模型条款，参见 `deps/tha3/ezvtuber_rt/README.md`。
