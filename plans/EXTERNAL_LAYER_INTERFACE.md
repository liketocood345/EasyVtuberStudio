# 外挂图层系统对接口说明

> 研发主仓 `E:\tha4fork-develop`。实现见 `face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/external_layer_output_bridge.py`。  
> 总计划见 [layer-runtime-replan_3a393fc1.plan.md](layer-runtime-replan_3a393fc1.plan.md)；交接见 [../HANDOVER.md](../HANDOVER.md) §7。

## 1. 用途

Load Preview 在勾选 **向外挂图层系统输出** 后：

- 隐藏内置 `OutputFrame`（避免双预览窗抢操作）
- 在本地目录写入 **契约文件** 与 **每帧状态**，供外挂合成器轮询
- 当前阶段仅写 **元数据**；RGBA 像素与图层清单路径为预留字段（`null`）

## 2. 目录与文件

与 `load_preview_ui_state.json` 同级：

```
experiments/puppeteer_load_preview/external_layer_output/
  contract.json    # 启用外挂模式时写入/更新
  status.json      # 每帧 draw 后更新（frame_sequence 递增）
```

代码路径（develop 仓库内）：

`face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/external_layer_output_bridge.py`

## 3. UI 与持久化

| 项 | 值 |
|----|-----|
| 勾选文案 | 向外挂图层系统输出（隐藏内置输出窗）/ Output to External Layer System |
| 面板 | 后处理区 `create_postprocess_panel()` |
| 持久化键 | `load_preview_ui_state.json` → `external_layer_output_enabled` (bool) |

## 4. `contract.json` 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `contract_version` | int | 当前为 `1` |
| `pixel_format` | string | `"rgba8"` |
| `width` / `height` | int | 锁定输出画布尺寸 |
| `coordinate_space` | string | `"output_canvas_bottom_center_anchor"` |
| `anchor_payload_version` | int | 锚定元数据版本 |
| `notes` | string | 人类可读说明（含像素导出未接线提示） |

外挂进程应在启动时读一次；尺寸变更后 THA4 会重写该文件。

## 5. `status.json` 字段（每帧）

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | bool | 恒为 `true`（仅在外挂模式 publish 时写入） |
| `contract_version` | int | 与 contract 一致 |
| `frame_sequence` | int | 单调递增，用于检测新帧 |
| `timestamp_ms` | int | Unix 毫秒时间戳 |
| `width` / `height` | int | 当前帧画布 |
| `background_hex` | string | 输出背景色 |
| `mirror_output` | bool | 是否镜像 |
| `display_scale` | float | 显示缩放 |
| `display_offset_x` / `display_offset_y` | float | 显示平移 |
| `display_rotation_deg` | float | 显示旋转（度） |
| `banner_text` | string \| null | 可选横幅 |
| `anchor_payload` | object | 见下表 |
| `frame_rgba_path` | string \| null | **预留**：RGBA 文件路径 |
| `layer_state_path` | string \| null | **预留**：图层状态快照路径 |

### `anchor_payload` 子字段

| 字段 | 说明 |
|------|------|
| `latest_face_anchor` | `{ center_x, center_y, face_size }` 或 `null` |
| `neutral_face_anchor` | 标定中性姿态锚点，结构同上 |
| `latest_head_roll_deg` | 当前头部 roll（度） |
| `neutral_head_roll_deg` | 中性 roll（度） |
| `last_direction_calibration_time` | 最近一次朝向标定时间戳 |
| `last_scale_calibration_time` | 最近一次缩放标定时间戳 |

## 6. 外挂合成器对接流程（当前可用）

1. 用户在外挂 THA4 中勾选外挂输出并加载模型。
2. 轮询或监听 `status.json` 的 `frame_sequence` 变化。
3. 首次读取 `contract.json` 获取画布尺寸与坐标约定。
4. 使用 `display_*`、`mirror_output`、`background_hex`、`anchor_payload` 对齐合成几何（像素文件尚未导出时仅能同步变换元数据）。
5. OBS / 采集目标为 **外挂合成器窗口**，而非 THA4 内置输出窗。

## 7. 待实现（计划 todo）

见 `layer-runtime-replan_3a393fc1.plan.md`：

- `L0-external-output-rgba-export`：`frame_rgba_path` 写入真实 RGBA
- `L0-external-output-layer-state-export`：`layer_state_path` 写入 `basic_layers_state` / `advanced_layers_state`
- L1 五层合成完成后，外挂可消费完整图层清单

## 8. 示例片段（便于对接调试）

`contract.json`（示意）：

```json
{
  "contract_version": 1,
  "pixel_format": "rgba8",
  "width": 768,
  "height": 768,
  "coordinate_space": "output_canvas_bottom_center_anchor",
  "anchor_payload_version": 1
}
```

`status.json`（示意；`frame_rgba_path` / `layer_state_path` 当前为 `null`）：

```json
{
  "enabled": true,
  "frame_sequence": 42,
  "width": 768,
  "height": 768,
  "display_scale": 1.0,
  "frame_rgba_path": null,
  "layer_state_path": null
}
```

## 9. 验收清单

1. 勾选外挂输出后，内置 **THA4 Output / 输出** 窗不再显示。
2. 取消勾选后内置输出窗恢复。
3. 加载模型后 `status.json` 中 `frame_sequence` 持续递增。
4. `contract.json` 中 `width`/`height` 与 UI 锁定输出尺寸一致。
