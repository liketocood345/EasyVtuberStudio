# GitHub 与 HF 混合许可证核对

本项目原创代码、脚本、文档及原创白腾图像、配件和图层素材使用 BSD-3-Clause。上游代码、模型、蒸馏权重及冻结运行库分别适用根目录 [LICENSE](../../LICENSE) 中列出的条款；不能用原创部分的 BSD 声明覆盖它们。两端发布同一份根 LICENSE。

本次纠正与补全：

- THA3：代码 MIT，模型权重 CC BY 4.0；原模型下载包自身的 LICENSE.txt 作为权重许可全文。依据：[上游说明](https://github.com/pkhungurn/talking-head-anime-3-demo#license)。
- THA4：上游代码 MIT，教师权重和 pose 数据集 CC BY-NC 4.0；白腾 Student 蒸馏权重保留相同限制。原创教师包装壳 app/、部署脚本属于本项目 BSD-3-Clause。依据：[上游说明](https://github.com/pkhungurn/talking-head-anime-4-demo#license)。
- RIFE：修正为对应上游的 MIT，并保留 Megvii 署名；waifu2x 和 Real-ESRGAN 改用实际上游原文，删除自行改写的版权行。[RIFE 原文](https://github.com/hzwer/ECCV2022-RIFE/blob/main/LICENSE)、[waifu2x 原文](https://github.com/nagadomi/waifu2x/blob/master/LICENSE)、[Real-ESRGAN 原文](https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE)。
- OpenSeeFace：保留原分发 Licenses 目录所有全文；只读解析 facetracker.exe 的冻结归档，补入其中第三方模块许可。DLL 元数据确认为 Python 3.7.6、OpenSSL 1.1.1d；归档中的 NumPy 1.18.0、Pillow 6.2.1、psutil 5.7.2 等按实际版本取原发行包文本。
- CPython 的五条节选替换为完整许可，另附对应版本 license.rst 的内嵌组件声明。NumPy wheel 的全文保留 OpenBLAS、LAPACK、GCC Runtime Exception；补充 Pillow 编解码库、PyInstaller bootloader 例外等文本。
- 逐段核验 57 份收集到的原文完整包含于根 LICENSE，比较时只忽略空白差异。旧 OpenCV 文件的 Shift-JIS 引号转为 UTF-8；不改写条款。

证据边界：旧冻结归档的 packaging、setuptools、typing_extensions、wcwidth、zipp 和 bootloader 未能确定具体版本，许可参考版本已逐项标明。旧 VC/UCRT 没有附历史 EULA；已附 Microsoft 官方 VC2015–2022 全文，并明确其不能证明旧二进制的历史条款匹配。这两项仍需旧包上游补充版本／供货证据，不能表述为历史来源已全部核实。

范围是本次 CORE、HF 五个资源包及 seed；Python/torch 等未进桶的通用环境不因本文改变许可。训练任务、用户照片和运行日志不在发布范围。此次仅调整许可与发布资料，没有修改推理、面捕或训练实现。
