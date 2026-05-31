# 外挂图层 bridge（已废弃）

> **2026-05-30 起已移除。** 图层系统改为**完全内置**；不再提供「向外挂图层系统输出」开关，也不再写入 `external_layer_output/` bridge 目录。

## 当前内置方案

| 功能 | 开关 | 说明 |
|------|------|------|
| 五层图层混合 | **启用图层混合 / Enable Layer Blending** | 弹出 `BasicLayerWindow`，在内置 OutputFrame 合成 |
| 无限图层（占位） | **启动无限图层系统 / Enable Unlimited Layer System** | 仅持久化勾选状态，**L2 尚未实现** |

实现文件：

- `layer_runtime.py`
- `basic_layer_window.py`
- `character_model_mediapipe_puppeteer_load_preview.py`

持久化：

- `load_preview_ui_state.json` → `layer_blend_enabled`、`unlimited_layers_enabled`
- `basic_layers/manifest.json`

交接见 [../docs/HANDOVER.md](../docs/HANDOVER.md) §0.5、§7。
