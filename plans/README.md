# 计划与对接文档（从活跃仓库同步）

本目录存放从 **`E:\THA4_bundle_bai_custom`** 提取的研发计划与对接说明，供 **`E:\tha4fork-develop`**（研发同步仓库）使用。

## 新 Agent 从这里开始

👉 **[AGENT_ONBOARDING.md](AGENT_ONBOARDING.md)**（5 分钟：三仓关系、阅读顺序、启动命令、当前进度、下一步 todo）

| 文件 | 说明 |
|------|------|
| [AGENT_ONBOARDING.md](AGENT_ONBOARDING.md) | **推荐首读**：接手入口与进度快照 |
| [HANDOVER.md](HANDOVER.md) | 已实现功能、类名、验收步骤 |
| [EXTERNAL_LAYER_INTERFACE.md](EXTERNAL_LAYER_INTERFACE.md) | 外挂图层对接（`contract.json` / `status.json`） |
| [layer-runtime-replan_3a393fc1.plan.md](layer-runtime-replan_3a393fc1.plan.md) | 多图层总计划（L0–L3；做图层前再读） |

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
