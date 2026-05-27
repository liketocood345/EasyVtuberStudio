# 快照说明 `2026-05-27`

本文件夹为 **2026-05-27** 从 fork 根目录移入 `his/` 的完整快照（遗留命名：仅日期，无时分秒）。

之后归档请使用 **`yyyy-MM-dd_HH-mm-ss`**，见 [BACKUP.md](../../BACKUP.md)。

## 当时包含的改动（摘要）

与 fork 根目录 [CHANGELOG.md](../../CHANGELOG.md) 中「当前版本」列表在打包日一致，主要包括：

- 紧凑启动 + 懒加载完整调参窗
- 独立输出窗、自动平移缩放、曲线与倾斜、镜像与抗锯齿
- 模型立即预览、Load Last、持久化
- 呼吸/嘴部/音频（pose converter）
- 实验性视频源 UI（下拉、多后端枚举等）

## 本快照未包含

- 此后在 `bai_custom` 继续修改的摄像头稳定性补丁全文
- `camfix/` 隔离测试目录与 DroidCam 调查结论文档

## 文件对照

| 路径 | 角色 |
|------|------|
| `experiments/puppeteer_load_preview/character_model_mediapipe_puppeteer_load_preview.py` | 主程序 |
| `talking-head-anime-4-demo/src/tha4/mocap/mediapipe_face_pose_converter_00.py` | Pose 转换 |
| `packaged/bai_450k/` | 示例模型 |
| `README.md` / `HANDOVER.md` | 当日说明文档 |
