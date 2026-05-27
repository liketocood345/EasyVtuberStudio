puppeteer_load_preview — Load Model 后立即默认 pose 预览（实验）
============================================================

目的
----
摄像头无画面时，原版右侧也会显示 "Nothing yet!"，无法区分：
  - 模型未加载成功
  - 模型已加载但摄像头/面捕未工作

本实验在 Load Model 成功后立刻用中性 MediaPipeFacePose 渲一帧，
并在无 face 输入时保留该预览图（不被 timer 清掉）。

默认 pose：BLENDSHAPE_NAMES 全 0 + 4x4 单位矩阵（避免空 dict / None 触发 converter KeyError）。

文件
----
character_model_mediapipe_puppeteer.py.orig     原版备份（只读对照）
character_model_mediapipe_puppeteer_load_preview.py   实验脚本
run_load_preview_puppeteer.bat                  启动

启动
----
  E:\THA4_bundle_bai_custom\experiments\puppeteer_load_preview\run_load_preview_puppeteer.bat

Load Model 示例
---------------
  E:\THA4_bundle_bai_custom\packaged\bai_450k\character_model\character_model.yaml

行为变化（相对原版）
--------------------
1. Load 成功 -> 右侧立即显示角色 + 黄字 "DEFAULT POSE (model loaded)"
2. 输出画面改为独立窗口，主窗口专注控制项
   - 输出窗口为无边框样式，默认大小为原来的 1.5 倍
   - 输出窗口位置和大小会被自动记住
   - 可在输出画布上按住左键直接拖动无边框窗口
   - 输出窗口内部的图像面板不再额外绘制边框
   - 模型加载区改为左右两个半宽按钮：左侧“加载上次模型”，右侧“加载其他模型”
3. 主控制区按性质并排为两列：模型参数传入、输出动态增强
   - 两列之间、以及它们与右侧预览列之间都可直接拖动分割条调整列宽
4. 右侧单独作为预览列：上方是缩小立绘预览与摄像头预览，下方是“后处理和其他”
   - 调整后的列宽会自动记住，下次启动继续沿用
5. 无摄像头/无人脸 -> 输出窗口保持预览图，不再刷回 Nothing yet!
6. 新增 Auto Move / Scale 控制区（默认开启）
7. 未加载模型时，除加载模型相关按钮外，其余可交互控件会统一置灰锁定
8. 默认即启用 Enable Auto Move / Scale：
   - 根据人脸在摄像头画面中的 X/Y 位置平移角色
   - 根据人脸远近（face bbox size）做非线性缩放映射，不再是纯正比关系
   - 根据人脸左右倾斜角同步旋转输出图像，默认上限为 10 度
   - Y 位置映射使用 landmarks 平均中心，避免“脸远离时被误判为向上移动”
   - 缩放与旋转都以角色图像的下边中心为锚点，默认贴住输出窗口下边，避免角色上漂
   - 远离镜头时缩小会更保守，不会很快掉到过小
   - 丢脸后短暂保持上一状态，再平滑回到居中 / 1.0x
9. Calibrate Neutral 可把当前脸位置 / 距离记录为中性基准
10. 自动校准拆分为方向基准与缩放基准两套独立开关和周期设置，默认均开启；现位于右侧预览列下方的“后处理和其他”
11. 方向自动校准与缩放自动校准都使用秒单位数值输入框，默认周期均为 300 秒
12. 若对应自动校准开关处于启用状态，则模型加载成功时会立即按当前脸数据各触发一次对应校准
13. 自动记忆作用于所有开关、背景选项、输出窗口位置/大小、上次成功模型路径与这两个周期输入框；滑块调整不会被自动记住
14. 所有滑块说明保持中英双语；中文和英文恢复为同一行显示，当前数值放在滑块下方；滑块保持水平放置，并随列宽自适应长度
   - “呼吸 / Breathing” 现改为可展开面板，原本的基础周期呼吸也移动到该面板中
   - 可勾选“启用动作加速呼吸 / Enable Reactive Breathing”，在剧烈动作后暂时提高呼吸频率
   - 新增触发阈值、触发后的剧烈呼吸频率、回落衰减三个参数；触发后会逐步衰减回基础呼吸频率
   - 新增“嘴型输入 / Mouth Input”切换菜单，可在“面捕张嘴 / Face Capture Mouth”和“声音张嘴 / Audio Mouth”之间切换
   - 切到声音张嘴后，会展示音源选择（麦克风输入 / 电脑内录）、音量阈值、满开音量、张嘴响应、闭嘴回落等参数
   - 声音张嘴支持系统默认麦克风和电脑内录（WASAPI loopback），并附带实时示波器显示当前输入波形
15. 主窗口每次启动都会按当前布局与列宽自动自适应到刚好能完整展示全部控件的尺寸
16. 顶部主区域支持垂直滚动，不拉大窗口也能完整看到全部控制项
17. 缩放中的 Y 位移增益默认值为 0，更适合先从水平移动开始调
18. 新增缩放映射曲线示意，可看到当前 face size delta 对应的曲线点
19. 可用 Near Curve / Far Curve / Curve Arc 三个滑块调整缩放曲线函数参数
20. 新增 Peak Shift 滑块，可沿 x 轴横向移动缩放曲线峰位
21. 曲线展示区继续回退为更朴素的简洁样式，并使用浅色背景；坐标范围会自适应拟合，保证曲线完整显示
22. 曲线状态文本会显示 raw / target，并在触发最小或最大缩放时明确提示
23. 新增可调强度抗锯齿，采用最终显示层超采样合成后再高质量缩回输出尺寸的方式减少旋转/缩放边缘锯齿
24. 滑块范围规则：若某项的合理范围为 [a, b]，则滑块范围扩展为 [a - 0.5*(b-a), b + 0.5*(b-a)]
   - 例如 0~1 -> -0.5~1.5
25. 默认最大缩放 / Max Scale 设为 0.9
26. 启动批处理会把运行期输出重定向到 run_load_preview_runtime.log，避免外部终端持续刷屏
27. 切换 GREEN / BLUE / BLACK / WHITE 时，背景色在画布层统一填充，不再在角色边缘留下旧背景异色
28. 有人脸后 -> 仍走 MediaPipe 实时驱动 THA4 pose；平移 / 缩放只发生在最终显示层
29. 未 Load -> 仍为 Nothing yet!

控制项建议
----------
- Enable Auto Move / Scale
  默认已打开；取消勾选可退回居中 / 1.0x。
- Calibrate Neutral
  面向屏幕、放在你想要的基准距离时点一下。
- Load Last / Load Other
  右侧“加载其他模型”沿用原来的文件选择逻辑；左侧“加载上次模型”会直接重载最近一次成功加载的模型路径，没有历史记录时会置灰。
- Anti-Aliasing
  位于后处理栏；本质是对最终显示层做更大离屏合成，再高质量缩回当前输出窗口尺寸。数值越大，边缘通常越平滑，但显存与 CPU/GPU 合成开销也会更高。
- Enable Direction Auto Calibrate / Direction Interval
  默认已打开；默认每 300 秒自动把当前脸的中心位置刷新为方向基准，右侧输入框单位为秒；不会自动重置倾斜零点。
- Enable Scale Auto Calibrate / Scale Interval
  默认已打开；默认每 300 秒自动把当前脸大小刷新为缩放基准，右侧输入框单位为秒。
- Move X Gain / Move Y Gain
  控制横向 / 纵向位移幅度（单位近似为输出画布像素）。
- Tilt Limit
  为正时控制左右倾斜显示的最大旋转角度，默认 10 度；为负时会线性减少面捕传给模型的倾斜角数据，负得越多削弱越强。
- Invert Tilt Mapping
  当默认左右倾斜方向与你习惯相反时可切换；该开关会被自动记住。
- Mirror Output
  水平镜像翻转角色输出；作为最后一步独立调整，不会改变倾斜映射语义；该开关会被自动记住。
- Scale Gain
  控制“靠近镜头放大、远离镜头缩小”的敏感度。
- Tilt Compensation
  位于收嘴最大值下方，范围默认正负 30 度；会把该数值直接加到传给模型的倾斜角数据上。
- Near Curve / Far Curve / Curve Arc
  控制缩放映射曲线形状。Near Curve 越大，靠近镜头时越快接近 Max Scale；Far Curve 越大，远离镜头时缩小越明显；Curve Arc 控制整条曲线的弧度。
- Peak Shift
  沿 x 轴横向移动缩放曲线的峰位；正值把峰往“近 / Near”方向推，负值把峰往“远 / Far”方向推。
- Min Scale / Max Scale
  限制最小 / 最大缩放，避免过度拉远或贴脸放大。
- Smoothing
  越大越稳，越小越跟手。

未修改
------
  E:\THA4_bundle\talking-head-anime-4-demo\src\tha4\app\character_model_mediapipe_puppeteer.py

无 GUI 冒烟（已验证 bai_450k）：
  cd E:\THA4_bundle_bai_custom\talking-head-anime-4-demo
  set PYTHONPATH=%cd%\src
  venv\Scripts\python.exe ..\experiments\puppeteer_load_preview\smoke_load_preview.py

满意后再考虑合并进主仓库或做快捷方式 14 的变体。
