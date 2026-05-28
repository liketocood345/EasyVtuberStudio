THA4_bundle_bai_custom — bai 白猫自定义 body 续训
==========================================

背景
----
- Face 0010 sample 肉眼正常；打包预览眼区糊成一团黑灰 -> body 整图 blended/color 抹眼。
- 角色全白、仅眼有色；不宜继续官网高 color_change 长训。

目录
----
talking-head-anime-4-demo\src   已改 distiller_config.py
venv / data / distill_outputs\bai -> junction 到 E:\THA4_bundle（大文件不复制）

Body 自定义三阶段（从当前 snapshot 续训）
--------------------------------------
| 段 | 上界 | LR | blended | warped | grid | color_change |
|----|------|-----|---------|--------|------|--------------|
| 1 | 450k | 3e-5 | 0.5 | 1.5 | 2.5 | 0.4 |
| 2 | 650k | 1e-5 | 1.0 | 2.5 | 4.0 | 0.5 |
| 3 | 800k | 1e-5 | 3.0 | 1.5 | 2.0 | 1.0 |

- checkpoint 每 10k（phase 上界须整除）
- 官方打包 body: 0080（80 万）
- 第一评估点: 450k -> 0045

推荐流程
--------
1. preflight_train.ps1
2. 对比旧 body: package_compare_body_ckpt.ps1（0001/0002/0003）
3. run_body_train_450k.bat  -> 打包 0045 -> puppeteer 看眼
4. 满意则停；否则 run_body_train.bat 到 80 万 -> 0080
5. package_bai_student.ps1 -BodyCheckpoint 0080

已打包交付（450k 里程碑）
-------------------------
  packaged\bai_450k\character_model\
  packaged\bai_450k\TRAINING_NOTES.txt
  packaged\bai_450k\PACKAGING_README.txt

勿用 E:\THA4_bundle 未改源码同时训同一 prefix。

MediaPipe 面捕 + DroidCam（快捷方式 14）
-----------------------------------------
快捷方式指向（未改）:
  E:\THA4_bundle\talking-head-anime-4-demo
  bin\run.bat src\tha4\app\character_model_mediapipe_puppeteer.py

推荐启动顺序（与 快捷入口\依次启动.txt 一致）:
  1. 先开 DroidCam（手机连上，客户端显示 DroidCam Video）
  2. 可选 OBS
  3. 双击 14_launch_mediapipe_puppeteer
  4. Load Model -> packaged\bai_450k\character_model\character_model.yaml

摄像头: 程序写死 VideoCapture(0)。本机若 0 不是 DroidCam，改 puppeteer.py 里设备号。
探测: scripts\probe_cameras.bat

本机探测结果（供参考，以你当前设备为准）:
  - 系统可见 DroidCam Video、Iriun Webcam
  - OpenCV 默认 index 0 可打开并读到 640x480
  - index 1/2/3 也可用；若画面不对请逐个试 N

重建环境
--------
  .\setup_bai_custom.ps1
