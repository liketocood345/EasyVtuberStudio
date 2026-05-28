# 计划与对接文档（从活跃仓库同步）

本目录存放从 **`E:\THA4_bundle_bai_custom`** 提取的研发计划与对接说明，供 **`E:\tha4fork-develop`**（研发同步仓库）使用。

| 文件 | 说明 |
|------|------|
| [layer-runtime-replan_3a393fc1.plan.md](layer-runtime-replan_3a393fc1.plan.md) | 多图层 / 外挂输出总计划（含 L0–L3 todo） |
| [HANDOVER.md](HANDOVER.md) | 项目交接与已实现功能索引 |
| [EXTERNAL_LAYER_INTERFACE.md](EXTERNAL_LAYER_INTERFACE.md) | 外挂图层系统对接口说明（`contract.json` / `status.json`） |

## 同步方式

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File sync_plans_from_bai_custom.ps1
```

或手动从 `E:\THA4_bundle_bai_custom` 覆盖上述三个文件（及根目录 `HANDOVER.md` 若存在）。

## 与代码的关系

- 实现代码仍在 `face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/`
- 桥接模块：`external_layer_output_bridge.py`
- 运行时输出目录（启用外挂模式后）：`experiments/puppeteer_load_preview/external_layer_output/`
