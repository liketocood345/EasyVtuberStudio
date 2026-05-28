# Project Handover: Face Puppeteer UI Enhancements (AI Code Draft)

## 1) Goal
Deliver an “EasyVtuber-like” face-driven puppeteering UI (MediaPipe -> THA4 pose + post-render display transforms), with improved UX and reduced UI disruption:

- Compact startup UI (3 buttons + hint text).
- Full controls window created lazily on first open.
- Character output stays responsive via a separate borderless output window.
- Mouth input mode: face capture vs audio-driven (mic / system loopback) with oscilloscope.
- Breathing reactive logic.
- Nonlinear scale curve visualization + controls.
- Tilt/rotation mapping controls and mirror as a final independent step.

This folder is a draft “fork repository staging area” prepared under `E:\`.

## 1.1) Fork 总库（Git 主仓库）

| 项 | 值 |
|----|-----|
| 本地路径 | `E:\tha4fork` |
| Fork 远程 | https://github.com/liketocood345/talking-head-anime-4-demo |
| 上游官方 | https://github.com/pkhungurn/talking-head-anime-4-demo |

本地已配置：`origin` → fork，`upstream` → 官方。说明见 `E:\tha4fork\FORK_ROOT.md`。

当前定制运行/实验仍在 `E:\THA4_bundle_bai_custom\`；与总库同步时需将改动合并进 `E:\tha4fork` 后再 push。

## 2) Target (fork draft) location
**`E:\face-puppeteer-ui-enhancements-ai-code\`**

Key paths in this draft:
- `README.md` (this draft summary)
- `experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py`
- `experiments\puppeteer_load_preview\README.txt`
- `experiments\puppeteer_load_preview\run_load_preview_puppeteer.bat`
- `experiments\puppeteer_load_preview\smoke_load_preview.py` (if present)
- `talking-head-anime-4-demo\src\tha4\mocap\mediapipe_face_pose_converter_00.py`
- `packaged\bai_450k\...` (bai packaged model)

## 3) Source / working area (original files modified)
All code changes were made in the current working environment under `E:\THA4_bundle_bai_custom\`:

- `E:\THA4_bundle_bai_custom\experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py`
- `E:\THA4_bundle_bai_custom\talking-head-anime-4-demo\src\tha4\mocap\mediapipe_face_pose_converter_00.py`

Then the modified files and model package were copied into the draft fork folder above.

## 4) Backup / “revert” strategy
Because this workspace is not guaranteed to be a git repo, the safest revert points are:

1. **Draft copy (recommended comparison/revert base)**  
   Compare current working files to:
   - `E:\face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py`
   - `E:\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\src\tha4\mocap\mediapipe_face_pose_converter_00.py`

2. **Original source files**  
   Original locations remain in `E:\THA4_bundle_bai_custom\...`.

If you need the *pre-change* versions, check whether the repo has prior backups (e.g. `.orig` files) or consult your prior snapshots; no new `.bak` files were created specifically in this handover step beyond the draft copy.

## 5) Change log (high-level)
### 5.1 Compact launcher + lazy “full controls” window
Implemented in:
`character_model_mediapipe_puppeteer_load_preview.py`

New/changed UI entry flow:
- Startup shows **only 3 buttons**:
  - `load_last_model` (“加载上次模型 / Load Last Model”)
  - quick calibrate head orientation (“校正头部朝向 / Calibrate Head Orientation”)
  - `toggle_full_controls_button` (“切换到完整调参窗 / Open Full Controls”)
- A hint text is added under the 3rd button:
  - `加载新模型请点展开完整 / To load a new model, open full controls`
- Full controls window is created lazily on first open:
  - Class introduced: `ControlsFrame`
  - Method introduced: `create_controls_frame()`
  - Switch methods:
    - `show_full_controls_window()`
    - `show_compact_launcher()`

Important: the capture loop and output update timers continue running; only UI controls are created/visible after expansion.

### 5.2 UI decoupling: “no controls yet” runtime safety
When full controls are not created yet:
- Some logic must not assume wx widgets exist.
- Therefore “headless-safe” stubs were introduced for values:
  - `ValueState` with `GetValue()`, `SetValue()`, `Enable()`, `IsEnabled()`
  - `SelectionState` with `GetSelection()`, `SetSelection()`, `GetCount()`, `Enable()`, `IsEnabled()`

Guards were added before touching wx widgets:
- `refresh_auto_transform_status()`: early return if `auto_transform_status_text` missing.
- `refresh_scale_curve_status()`: early return if `scale_curve_status_text` missing.
- `render_default_pose_load_preview()`: only updates `fps_text` if it exists.
- `update_capture_panel()`: refresh webcam panel only if created.

Rotation labels:
- `rotation_labels` / `rotation_value_labels` dicts are initialized unconditionally.
- Updates to `rotation_value_labels[HEAD_X|HEAD_Y|HEAD_Z]` are guarded by membership checks.

Dialogs parent selection:
- `get_dialog_parent()` chooses `controls_frame` if visible; otherwise uses main frame.

### 5.3 Mouth/Breathing collapsible style & audio device name fixes
Implemented in:
`mediapipe_face_pose_converter_00.py`

Corrections included:
- Ensured the intended style consistency between “Breathing” and “Mouth Input” sections (no accidental style inversion).
- Audio status now includes the actual device name:
  - `self.audio_device_name` initialized
  - `get_audio_stream_settings()` returns both `status_message` and `device_name`
  - `refresh_audio_mouth_status_text()` includes `设备 / Device: ...`

Also:
- `set_panel_enabled()` now enables/disables the correct breathing container (`breathing_panel`), matching the reverted breathing UI style.

## 6) Key identifiers / variables (for new agent)
### 6.1 Main UI controller script
File: `experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py`

Main added types:
- `class ValueState`
- `class SelectionState`
- `class ControlsFrame(wx.Frame)`

Main added/used members:
- `self.controls_frame` (lazy full controls window instance)
- `self.compact_launcher_panel`
- `self.full_controls_expanded` (bool)
- Buttons:
  - `quick_load_last_model_button`
  - `quick_calibrate_head_orientation_button`
  - `toggle_full_controls_button`
- Switch methods:
  - `show_full_controls_window()`
  - `show_compact_launcher()`

Headless safety members:
- `self.rotation_labels`
- `self.rotation_value_labels`

### 6.2 Pose converter script (Breathing/Mouth + audio)
File: `talking-head-anime-4-demo\src\tha4\mocap\mediapipe_face_pose_converter_00.py`

Main added/updated members:
- `self.audio_device_name`

Main methods touched:
- `get_audio_stream_settings()`
- `ensure_audio_stream_state()`
- `refresh_audio_mouth_status_text()`
- `set_panel_enabled()`

## 7) External layer output toggle (built-in output window hide)

Implemented in `experiments\puppeteer_load_preview\` (2026-05-27):

| Item | Location |
|------|----------|
| UI checkbox | Postprocess panel: **向外挂图层系统输出 / Output to External Layer System** |
| Persistence key | `load_preview_ui_state.json` → `external_layer_output_enabled` (bool) |
| Bridge module | `external_layer_output_bridge.py` |
| Main integration | `character_model_mediapipe_puppeteer_load_preview.py` |

### Behavior

- **Unchecked (default):** built-in borderless `OutputFrame` is created/shown as before; OBS should capture **THA4 Output / 输出**.
- **Checked:** built-in `OutputFrame` is hidden (`Show(False)`); rendering still runs into `result_image_bitmap` in memory.
- Clicking controls no longer calls `Raise()` on the hidden output window.
- Saved `output_frame_*` geometry is still collected when the frame object exists, but the window stays hidden while external mode is on.

### Bridge directory (reserved for external compositor)

Next to `load_preview_ui_state.json`:

```
experiments\puppeteer_load_preview\external_layer_output\
  contract.json   # frame size / format contract (written when mode enabled)
  status.json     # per-frame metadata (sequence, transforms, background; updated each draw)
```

`ExternalLayerOutputBridge.publish_composite_frame()` currently writes **metadata only** (`frame_rgba_path` and `layer_state_path` are `null` placeholders).

### External compositor integration checklist (not implemented here)

1. Poll or watch `status.json` for `frame_sequence` changes.
2. Read `contract.json` once for canvas size (`width` / `height`, default 768×768).
3. Future: read RGBA from `frame_rgba_path` or shared memory field added to `status.json`.
4. Future: read layer manifest from `layer_state_path` when `basic_layers_state` / `advanced_layers_state` exist.
5. OBS / capture target becomes the **external compositor window**, not THA4 Output.

### Related plan

See `plans/layer-runtime-replan_3a393fc1.plan.md`（或同目录副本）todos `L0-external-output-toggle` and `L0-external-output-bridge`；对接字段见 `plans/EXTERNAL_LAYER_INTERFACE.md`。

## 8) Dual image source modes (THA3 / THA4 Student)

Implemented in `experiments\puppeteer_load_preview\` (2026-05-28):

| Item | Location |
|------|----------|
| Architecture | `image_sources/` — `Tha4StudentSource` / `Tha3Source` black boxes |
| THA3 engine | `tha3_engine.py` (PyTorch `.pt` or ONNX+DirectML) |
| Mode UI | Postprocess panel: **图像来源 / Image Source** radio + THA3 PNG loader |
| Persistence | `image_source_mode`, `tha3_character_png`, `tha3_model_variant` |
| Vendor junctions | `setup_tha3_vendor.ps1` → `vendor\easyvtuber\` |
| Per-source deps | `deps\` — `requirements-tha4-student.txt`, `requirements-tha3-ort.txt`, install `.bat` |
| Docs | `THA3_INTEGRATION.md`, `deps\README.md` |

### Behavior

- Only **one** source runs at a time; switching calls `stop()` on the old source before `start()` on the new one.
- **THA4 Student:** existing yaml + distilled model path (unchanged semantics).
- **THA3:** 512×512 RGBA PNG + model variant; no distillation required; heavier runtime.
- Shared shell: `draw_result_wx_image()`, output window, display transforms, external layer bridge.

### Verification

```bat
cd E:\THA4_bundle_bai_custom\talking-head-anime-4-demo
set PYTHONPATH=%cd%\src
venv\Scripts\python.exe ..\experiments\puppeteer_load_preview\smoke_tha3_preview.py
venv\Scripts\python.exe ..\experiments\puppeteer_load_preview\smoke_load_preview.py
```

## 9) Known limitations / TODOs (recommended next work)
1. **Performance optimization still incomplete**: compact/full window switching hides UI, but the capture loop and detection still run continuously. If you want real reductions in camera preview + UI draw cost, you must gate `update_capture_panel()` rendering and/or skip `mediapipe` detection when compact mode is active.
2. Verify “full controls created lazily” behavior with real user flows:
   - start -> load last model -> expand full controls
3. If you later merge this into the main repo, ensure no duplicate class stubs (`ValueState` / `SelectionState`) conflict with existing naming conventions.

## 10) Quick verification steps
1. Run the experimental preview script.
2. Confirm initial UI shows only 3 buttons + hint text.
3. Click “Open Full Controls”:
   - full controls window should appear (lazily created).
4. Click “Switch to Compact”:
   - full window hides, compact window stays.
5. Load `bai_450k` model:
   - neutral pose preview appears immediately after load.
6. In mouth audio mode:
   - audio status should show “Device / 设备: ...”.
7. External layer output:
   - Open full controls → Postprocess panel → enable **Output to External Layer System**.
   - Built-in **THA4 Output / 输出** window should disappear.
   - After loading a model, confirm `experiments\puppeteer_load_preview\external_layer_output\status.json` updates `frame_sequence`.
   - Uncheck the option; built-in output window should return.
8. Dual image source:
   - Postprocess → select **THA3 立绘即用** → **Load THA3 PNG** → face capture should animate.
   - Switch back to **THA4 Student** → load bai yaml → previous THA4 path still works.

