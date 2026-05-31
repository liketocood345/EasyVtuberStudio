# UI 弹窗安全规范 / Modal Dialog Safety

## 高危漏洞定义

**任何能导致报错弹窗在一秒内弹出超过一次的问题，均视为高危 UI 漏洞。**

典型触发源：

- `wx.Timer` 回调（capture / display / infer tick）
- 后台线程轮询失败后直接 `ShowModal`
- 持久化状态恢复为不可用模式，但定时器已在跑

后果：界面卡死、无法操作、用户只能强杀进程。

## 强制规则

1. **定时器 / 循环 / 异步回调路径**：禁止直接 `wx.MessageDialog(...).ShowModal()`。失败时只写 stderr / 日志，或走无 UI 降级。
2. **用户主动操作**（菜单、按钮、模式切换）：可以弹窗，但必须经 `ui_dialog_guard.show_rate_limited_message`（同一 `dialog_key` 默认每会话最多 1 次、间隔 ≥ 1 秒）。
3. **资源不可用**（如未装 `face_puppeteer`）：启动时同步修正模式；定时器路径静默 `ensure_*`，并 **一次性** 自动回退到 Mouse + Audio。
4. **新增 `ensure_*` 初始化函数**：必须带 `show_dialog: bool = False`；仅 `from_user=True` 时允许弹窗。

## 实现入口

| 文件 | 作用 |
|------|------|
| `experiments/puppeteer_load_preview/ui_dialog_guard.py` | 弹窗频率限制 |
| `character_model_mediapipe_puppeteer_load_preview.py` | `ensure_face_landmarker(show_dialog=…)`、`_fallback_to_mouse_mocap_once` |

## 审查清单（改 UI 前自检）

- [ ] 该代码是否可能在 66ms capture timer 或更高频路径被调用？
- [ ] 失败分支是否可能重复弹同一对话框？
- [ ] 持久化默认值是否在无 add-on 时仍指向 mediapipe？
- [ ] 是否已用 `show_rate_limited_message` 或 `show_dialog=False`？

## 相关排障

fork 瘦包未装 face_puppeteer 时，若 `workspace/load_preview_ui_state.json` 里保存了 `mocap_input_mode: mediapipe`，旧版会反复弹「无法初始化 MediaPipe 面捕」。新版启动时强制回退 Mouse + Audio，且 timer 路径不再弹窗。
