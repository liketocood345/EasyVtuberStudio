# Custom Function Index

English index of **custom** functions in the EasyVtuberStudio face-puppeteer module (`puppeteer_load_preview`).
Use this document to trace UI controls to handlers and to avoid regressions
(for example, calibration buttons that must call the same code path).

## Scope

| Included | Excluded |
| --- | --- |
| `experiments/puppeteer_load_preview/**` Python modules | Upstream THA4 demo package (`talking-head-anime-4-demo/src/tha4/**`) |
| Fork-specific shell around THA4 Student / THA3 / layers / output | Vendored THA3 runtime inside `deps/tha3/` |
| Local tests under this experiment (`verify_periodic_calibration.py`) | Smoke scripts (`smoke_*.py`) |

**Primary entry:** `character_model_mediapipe_puppeteer_load_preview.py` (`MainFrame`).

## Maintenance

Regenerate tables after large refactors:

```powershell
python experiments/puppeteer_load_preview/_gen_function_index.py
```

When adding a user-facing handler, update `UI_OVERRIDES` in the generator if the
wx control label is not extracted automatically.

## Quick reference — calibration paths

Two related but **independent** calibrations (do not cross-call):

| Path | Function | Effect | UI controls |
| --- | --- | --- | --- |
| **A — head orientation** | `_perform_head_orientation_calibration` → `pose_converter.apply_face_orientation_calibration()` | Sets MediaPipe head X/Y/Z offsets in converter only | Compact **Calibrate Head Orientation**; preview column **Calibrate Head Orientation** (`calibrate_neutral_button`); model-input **Calibrate Forward Gaze** (`calibrate_face_orientation_button`); periodic **Auto Calibrate Forward Gaze** |
| **B — output dynamic enhancement** | `update_neutral_output_enhancement` / `apply_neutral_calibration` (auto-init only) | Updates pan/scale neutral (`neutral_face_screen_motion`); manual via scale calibrate | Compact **Output Dynamic Enhancement Calibration**; preview column **Output Dynamic Enhancement Calibration** (`calibrate_scale_button`); auto enhancement checkbox + interval |

**Boundary:** path A must **not** call `apply_neutral_calibration`, `update_neutral_output_enhancement`, or reset display offset/scale. Path B must **not** call `apply_face_orientation_calibration`.

## Quick reference — display vs infer timers

| Timer | Handler | Interval | Role |
| --- | --- | --- | --- |
| `capture_timer` | `update_capture_panel` | ~66 ms | Webcam / window capture |
| `display_timer` | `on_display_timer` | 30 ms tick | Updates pan/scale every tick; **presents** at `get_display_present_cap_hz()` (30 Hz when smooth affine on, else GPU infer cap) |
| `animation_timer` | `on_infer_tick` | dynamic | Schedule async GPU infer |

## `basic_layer_window.py`

Unlimited layer editor window (opened when Enable Unlimited Layer System is on).

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `LayerThumbPanel.__init__` | Constructor for `LayerThumbPanel`. | — |
| `LayerThumbPanel.set_bitmap` | Updates bitmap. | — |
| `LayerThumbPanel.set_selected` | Updates selected. | — |
| `LayerThumbPanel._on_paint` | Private helper for on paint. | — |
| `_bind_left_click` | Private helper for bind left click. | — |
| `LayerRowPanel.__init__` | Constructor for `LayerRowPanel`. | — |
| `LayerRowPanel._on_paint` | Private helper for on paint. | — |
| `LayerRowPanel.set_selected` | Updates selected. | — |
| `LayerDetailPlaceholderPanel.__init__` | Constructor for `LayerDetailPlaceholderPanel`. | — |
| `LayerDetailDock.__init__` | Constructor for `LayerDetailDock`. | — |
| `LayerDetailDock.show_placeholder` | — | — |
| `LayerDetailDock.show_editor` | — | — |
| `BasicLayerWindow.__init__` | Constructor for `BasicLayerWindow`. | Basic Layer window (internal) |
| `BasicLayerWindow.on_close` | wx event handler for close. | Basic Layer window close |
| `BasicLayerWindow.on_geometry_changed` | wx event handler for geometry changed. | Basic Layer window move/resize |
| `BasicLayerWindow._on_activate` | Private helper for on activate. | Basic Layer window (internal) |
| `BasicLayerWindow.restore_geometry` | — | — |
| `BasicLayerWindow._refresh_layout` | Private helper for refresh layout. | Basic Layer window (internal) |
| `BasicLayerWindow._wire_detail_dock` | Private helper for wire detail dock. | Basic Layer window (internal) |
| `BasicLayerWindow.rebuild_rows` | — | — |
| `BasicLayerWindow._wire_layer_row` | Private helper for wire layer row. | Basic Layer window (internal) |
| `BasicLayerWindow.refresh_all` | — | — |
| `BasicLayerWindow._refresh_character_row` | Private helper for refresh character row. | Basic Layer window (internal) |
| `BasicLayerWindow._populate_row` | Private helper for populate row. | Basic Layer window (internal) |
| `BasicLayerWindow._refresh_detail_dock` | Private helper for refresh detail dock. | Basic Layer window (internal) |
| `BasicLayerWindow.apply_selection` | — | — |
| `BasicLayerWindow._select_slot` | Private helper for select slot. | Basic Layer window (internal) |
| `BasicLayerWindow._current_detail_slot` | Private helper for current detail slot. | Basic Layer window (internal) |
| `BasicLayerWindow._load_asset` | Private helper for load asset. | Layer row: Load |
| `BasicLayerWindow._on_clear_asset` | Private helper for on clear asset. | Detail dock: Clear asset |
| `BasicLayerWindow._move_layer` | Private helper for move layer. | Layer row: Move up/down |
| `BasicLayerWindow._on_scale_changed` | Private helper for on scale changed. | Detail dock: Scale slider |
| `BasicLayerWindow._on_rotation_changed` | Private helper for on rotation changed. | Detail dock: Rotation slider |
| `BasicLayerWindow._on_reset_transform` | Private helper for on reset transform. | Detail dock: Reset transform |
| `BasicLayerWindow._on_detail_changed` | Private helper for on detail changed. | Detail dock: Visible / binding choice |

## `frame_interpolation.py`

Pose-based frame interpolation helpers (no direct wx controls; driven by postprocess Frame Interpolation and GPU Infer Cap).

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `normalize_multiplier` | Clamp frame-interpolation multiplier to supported values. | — |
| `lerp_pose` | Linearly interpolate two pose vectors for midpoint infer. | — |
| `get_effective_infer_cap_hz` | Returns effective infer cap hz. | — |
| `resolve_interp_infer_pose` | Pose to infer for the current sub-step (0 .. multiplier-1). | — |
| `label_for_multiplier` | Human-readable label for interpolation multiplier choice. | — |

## `image_sources/base.py`

Pluggable image source backends (THA4 Student vs THA3).

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `ImageSource.start` | — | — |
| `ImageSource.stop` | — | — |
| `ImageSource.is_ready` | — | — |
| `ImageSource.load_asset` | — | — |
| `ImageSource.tick` | — | — |
| `ImageSource.get_load_ui_spec` | Returns load ui spec. | — |
| `normalize_image_source_mode` | — | — |

## `image_sources/factory.py`

Pluggable image source backends (THA4 Student vs THA3).

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `create_image_source` | Factory: instantiate Tha4StudentSource or Tha3Source. | — |
| `_sync_image_source_mode_choice` | Sync internal mode flag after source switch. | — |
| `switch_image_source` | Stop current source, switch mode, optionally autoload asset. | — |

## `image_sources/tha3_source.py`

Pluggable image source backends (THA4 Student vs THA3).

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `Tha3Source.__init__` | Constructor for `Tha3Source`. | — |
| `Tha3Source.start` | — | — |
| `Tha3Source.stop` | — | — |
| `Tha3Source.is_ready` | — | — |
| `Tha3Source.load_asset` | Load 512×512 RGBA PNG and start THA3 engine. | — |
| `Tha3Source.tick` | Run THA3 infer step from current MediaPipe pose. | — |
| `Tha3Source.get_load_ui_spec` | Returns load ui spec. | — |

## `image_sources/tha4_student_source.py`

Pluggable image source backends (THA4 Student vs THA3).

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `Tha4StudentSource.start` | — | — |
| `Tha4StudentSource.stop` | — | — |
| `Tha4StudentSource.is_ready` | — | — |
| `Tha4StudentSource.load_asset` | Load character via THA4 Student yaml path. | — |
| `Tha4StudentSource.tick` | Schedule THA4 Student poser infer from pose. | — |
| `Tha4StudentSource.get_load_ui_spec` | Returns load ui spec. | — |

## `layer_runtime.py`

Basic layer stack data model, geometry, compositing, and JSON persistence.

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `LayerTransform.to_dict` | — | — |
| `LayerTransform.from_dict` | — | — |
| `center_layer_transform` | Align layer image center to output window center (512-space origin). | — |
| `reset_layer_transform` | Reset layer pose to default centered pose (position, scale, rotation). | — |
| `BasicLayerSlot.to_dict` | — | — |
| `BasicLayerSlot.from_dict` | — | — |
| `BasicLayersState.__post_init__` | Constructor for `BasicLayersState`. | — |
| `BasicLayersState.get_slot` | Returns slot. | — |
| `BasicLayersState.sorted_layers_for_draw` | — | — |
| `BasicLayersState.sorted_layers_for_ui` | — | — |
| `BasicLayersState.to_dict` | — | — |
| `BasicLayersState.from_dict` | — | — |
| `default_stack_position_for_slot` | — | — |
| `occlusion_for_stack_position` | — | — |
| `layer_at_stack_position` | — | — |
| `normalize_layer_stack_positions` | Ensure five layers occupy stack slots 0,1,3,4,5 (2 = character). | — |
| `iter_ui_list_top_to_bottom` | UI list: top = drawn last; character row sits at stack position 2. | — |
| `stack_position_can_move_up` | — | — |
| `stack_position_can_move_down` | — | — |
| `default_basic_layer_slot` | — | — |
| `_clean_transparent_rgb` | Zero RGB on fully transparent pixels to avoid green fringe when scaling. | — |
| `scale_image_to_bitmap` | Scale PNG to bitmap preserving alpha (avoids green halos from wx.Image.Scale). | — |
| `LayerGeometryResolver.map_coord` | — | — |
| `LayerGeometryResolver.resolve_layer_rect` | — | — |
| `LayerGeometryResolver.resolve_all` | — | — |
| `LayerAssetCache.__init__` | Constructor for `LayerAssetCache`. | — |
| `LayerAssetCache.clear` | — | — |
| `LayerAssetCache.invalidate` | — | — |
| `LayerAssetCache.load_image` | — | — |
| `LayerAssetCache.get_draw_bitmap` | Returns draw bitmap. | — |
| `LayerAssetCache.thumbnail_bitmap` | — | — |
| `LayerCompositor.draw_layer_on_dc` | — | — |
| `LayerCompositor.draw_layers_group` | — | — |
| `LayerCompositor.draw_post_process_stack` | Post-process: composite layers on output (independent of mirror / display transform). | — |
| `LayerCompositor.draw_unified_stack` | — | — |
| `LayerCompositor.hit_test_layer_slot` | — | — |
| `LayerCompositor.draw_selection_highlight` | — | — |
| `get_basic_layers_directory` | Returns basic layers directory. | — |
| `save_basic_layers_state` | Persist layer slots to `basic_layers/*.json`. | — |
| `load_basic_layers_state` | Load layer slots from disk into BasicLayersState. | — |
| `move_layer_z_order` | Change stack position of a layer slot by delta. | — |

## `tha3_engine.py`

THA3 ONNX/PyTorch inference engine wrapper.

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `_numpy_rgba_to_wx_image` | Private helper for numpy rgba to wx image. | — |
| `_load_png_rgba` | Private helper for load png rgba. | — |
| `_load_tha3_ort_module` | Private helper for load tha3 ort module. | — |
| `Tha3Engine.__init__` | Constructor for `Tha3Engine`. | — |
| `Tha3Engine.last_error` | — | — |
| `Tha3Engine.is_loaded` | — | — |
| `Tha3Engine.stop` | — | — |
| `Tha3Engine.load_character_png` | — | — |
| `Tha3Engine._init_pytorch_backend` | Private helper for init pytorch backend. | — |
| `Tha3Engine._init_ort_backend` | Private helper for init ort backend. | — |
| `Tha3Engine.render_pose` | — | — |
| `Tha3Engine._render_pose_pytorch` | Private helper for render pose pytorch. | — |
| `Tha3Engine._render_pose_ort` | Private helper for render pose ort. | — |

## `tha3_paths.py`

Repository-relative path resolution for THA3 bundle and model assets.

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `find_repo_root` | — | — |
| `get_demo_root` | Match `scripts/launch/run_load_preview_puppeteer.bat`: prefer nested enhanced demo over repo-root src. | — |
| `get_demo_src_path` | Returns demo src path. | — |
| `get_packaged_model_yaml` | Returns packaged model yaml. | — |
| `get_tha3_bundle_root` | Returns tha3 bundle root. | — |
| `get_tha3_source_root` | Returns tha3 source root. | — |
| `get_ezvtuber_models_root` | Returns ezvtuber models root. | — |
| `get_ezvtuber_images_root` | Returns ezvtuber images root. | — |
| `get_ezvtuber_rt_root` | Returns ezvtuber rt root. | — |
| `variant_to_ort_flags` | — | — |
| `variant_to_pytorch_model_name` | — | — |
| `pytorch_model_dir` | — | — |
| `pytorch_models_available` | — | — |
| `to_repo_relative` | Store paths relative to fork repo root (forward slashes). | — |
| `from_repo_relative` | Resolve repo-relative (or experiment-relative) paths to absolute. | — |
| `ensure_tha3_on_path` | — | — |

## `tha3_pose_adapter.py`

MediaPipe pose vector to THA3 45-D pose adapter.

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `mediapipe_pose_to_tha3_vector` | Convert MediaPipe face pose to THA3 45-D parameter vector. | — |
| `neutral_tha3_pose` | Build neutral THA3 pose from converter defaults. | — |

## `transparent_capture_window.py`

Win32 layered window for OBS transparent capture output.

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `_init_win32_prototypes` | Private helper for init win32 prototypes. | — |
| `_straight_rgba_to_premultiplied_bgra` | Private helper for straight rgba to premultiplied bgra. | — |
| `_window_proc` | Private helper for window proc. | — |
| `_register_window_class` | Private helper for register window class. | — |
| `TransparentCaptureWindow.__init__` | Constructor for `TransparentCaptureWindow`. | — |
| `TransparentCaptureWindow._create_window` | Private helper for create window. | — |
| `TransparentCaptureWindow._create_dib` | Private helper for create dib. | — |
| `TransparentCaptureWindow._release_dib` | Private helper for release dib. | — |
| `TransparentCaptureWindow.hwnd` | — | — |
| `TransparentCaptureWindow.is_valid` | — | — |
| `TransparentCaptureWindow.get_rect` | Returns rect. | — |
| `TransparentCaptureWindow.set_position` | Updates position. | — |
| `TransparentCaptureWindow.show` | — | — |
| `TransparentCaptureWindow.hide` | — | — |
| `TransparentCaptureWindow.destroy` | — | — |
| `TransparentCaptureWindow._notify_geometry_changed` | Private helper for notify geometry changed. | — |
| `TransparentCaptureWindow.update_frame_rgba` | — | — |

## `verify_periodic_calibration.py`

Offline unit tests for periodic calibration logic (no UI).

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `ForwardGazeCalibrationHarness.__init__` | Constructor for `ForwardGazeCalibrationHarness`. | — |
| `ForwardGazeCalibrationHarness.apply_face_orientation_calibration` | — | — |
| `ForwardGazeCalibrationHarness.apply_enabled_auto_calibration_on_load` | — | — |
| `ForwardGazeCalibrationHarness.try_apply_auto_forward_gaze_calibration` | — | — |
| `ScaleCalibrationHarness.__init__` | Constructor for `ScaleCalibrationHarness`. | — |
| `ScaleCalibrationHarness.set_neutral_face_screen_motion` | Updates neutral face screen motion. | — |
| `ScaleCalibrationHarness.update_neutral_output_enhancement` | — | — |
| `ScaleCalibrationHarness.apply_enabled_auto_calibration_on_load` | — | — |
| `ScaleCalibrationHarness.maybe_apply_periodic_scale_calibration` | — | — |
| `assert_close` | — | — |
| `test_forward_gaze_sets_head_offsets` | — | — |
| `test_forward_gaze_without_face_skips` | — | — |
| `test_forward_gaze_independent_interval` | — | — |
| `test_forward_gaze_disabled_skips` | — | — |
| `test_forward_gaze_first_tick_arms_timer_without_calibrating` | — | — |
| `test_output_enhancement_recenters_horizontal_only` | — | — |
| `test_scale_independent_interval` | — | — |
| `main` | — | — |

## `window_capture.py`

Win32 window enumeration and client-area BGR capture for external video sources.

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `WindowInfo.__init__` | Constructor for `WindowInfo`. | — |
| `_ensure_dpi_awareness` | Private helper for ensure dpi awareness. | — |
| `_set_capture_thread_dpi_for_window` | Match OBS: align capture thread DPI with target window when API exists. | — |
| `_restore_thread_dpi` | Private helper for restore thread dpi. | — |
| `is_window_valid` | — | — |
| `get_window_title` | Returns window title. | — |
| `_client_size` | Private helper for client size. | — |
| `_client_screen_rect` | Private helper for client screen rect. | — |
| `_hdc_bitmap_to_bgr` | Private helper for hdc bitmap to bgr. | — |
| `_capture_with_hdc_bitblt` | Private helper for capture with hdc bitblt. | — |
| `_capture_print_window_client` | OBS/WGC fallback for hardware-accelerated or occluded windows. | — |
| `_capture_obs_window_dc_bitblt` | Same as OBS dc_capture_capture: BitBlt from GetDC(window), not from screen. | — |
| `_capture_screen_bitblt` | Private helper for capture screen bitblt. | — |
| `_frame_mean_luma` | Private helper for frame mean luma. | — |
| `list_capture_targets` | Visible top-level windows with non-empty titles. | — |
| `capture_window_client_bgr` | Grab the window client area as BGR. | — |

## `character_model_mediapipe_puppeteer_load_preview.py`

### Supporting types (non-MainFrame)

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `make_neutral_mediapipe_face_pose` | — | — |
| `slider_label` | — | — |
| `FloatSliderControl.__init__` | Constructor for `FloatSliderControl`. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl._float_to_int` | Private helper for float to int. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl._format_multiline_label` | Private helper for format multiline label. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl._int_to_float` | Private helper for int to float. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl._refresh_value_label` | Private helper for refresh value label. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl._is_mouse_over_panel` | Private helper for is mouse over panel. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl._is_mouse_stationary_near_last_hover` | Private helper for is mouse stationary near last hover. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl._set_wheel_armed` | Private helper for set wheel armed. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl._handle_slider_mouse_enter` | Private helper for handle slider mouse enter. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl._handle_slider_mouse_leave` | Private helper for handle slider mouse leave. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl._handle_hover_arm_timer` | Private helper for handle hover arm timer. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl._handle_slider_mousewheel` | Private helper for handle slider mousewheel. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl._handle_change` | Private helper for handle change. | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl.GetValue` | — | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FloatSliderControl.SetValue` | — | Any `FloatSliderControl` slider (display transform + anti-aliasing) |
| `FpsStatistics.__init__` | Constructor for `FpsStatistics`. | — |
| `FpsStatistics.add_fps` | — | — |
| `FpsStatistics.get_average_fps` | Returns average fps. | — |
| `ValueState.__init__` | Constructor for `ValueState`. | — |
| `ValueState.GetValue` | — | — |
| `ValueState.SetValue` | — | — |
| `ValueState.Enable` | — | — |
| `ValueState.IsEnabled` | — | — |
| `SelectionState.__init__` | Constructor for `SelectionState`. | — |
| `SelectionState.GetSelection` | — | — |
| `SelectionState.SetSelection` | — | — |
| `SelectionState.GetCount` | — | — |
| `SelectionState.Enable` | — | — |
| `SelectionState.IsEnabled` | — | — |
| `OutputFrame.__init__` | Constructor for `OutputFrame`. | Output window (internal) |
| `OutputFrame.on_activate` | wx event handler for activate. | Output window (internal) |
| `OutputFrame.on_erase_background` | wx event handler for erase background. | Output window (internal) |
| `OutputFrame.paint_result_image_panel` | — | Output window image panel |
| `OutputFrame.on_close` | wx event handler for close. | Output window close |
| `OutputFrame.on_size` | wx event handler for size. | Output window resize |
| `OutputFrame.on_move` | wx event handler for move. | Output window move |
| `OutputFrame.on_left_down` | wx event handler for left down. | Output window drag pan |
| `OutputFrame.on_left_up` | wx event handler for left up. | Output window drag pan |
| `OutputFrame.on_mouse_move` | wx event handler for mouse move. | Output window drag pan |
| `ControlsFrame.__init__` | Constructor for `ControlsFrame`. | — |
| `ControlsFrame.on_geometry_changed` | wx event handler for geometry changed. | — |
| `ControlsFrame.on_activate` | wx event handler for activate. | — |
| `ControlsFrame.on_close` | wx event handler for close. | — |
| `WebcamPreviewPopupFrame.__init__` | Constructor for `WebcamPreviewPopupFrame`. | Webcam popup (internal) |
| `WebcamPreviewPopupFrame.on_activate` | wx event handler for activate. | Webcam popup |
| `WebcamPreviewPopupFrame.on_erase_background` | wx event handler for erase background. | Webcam popup |
| `WebcamPreviewPopupFrame.on_paint_preview_panel` | wx event handler for paint preview panel. | Webcam popup |
| `WebcamPreviewPopupFrame.on_preview_double_click` | wx event handler for preview double click. | Webcam popup |
| `WebcamPreviewPopupFrame.on_close` | wx event handler for close. | Webcam popup |
| `resolve_mediapipe_face_landmarker_model_path` | — | — |

### MainFrame — UI event handlers

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame.calibrate_head_orientation_quick` | Compact launcher: path A head orientation only. | Compact: Calibrate Head Orientation |
| `MainFrame.calibrate_neutral_clicked` | Preview-column button: path A head orientation only. | Calibrate Head Orientation (preview calibration column) |
| `MainFrame.calibrate_scale_clicked` | Manual output dynamic enhancement calibration (path B neutral/size). | Compact: Output Dynamic Enhancement Calibration; Output Dynamic Enhancement Calibration (preview calibration column) |
| `MainFrame.load_last_model` | — | Load Last THA4 Student Model |
| `MainFrame.load_last_tha3_character_png` | — | Load Last THA3 PNG |
| `MainFrame.load_model` | — | Load THA4 Student Model |
| `MainFrame.load_tha3_character_png` | — | Load Other THA3 PNG |
| `MainFrame.on_animation_panel_mousewheel_logged` | wx event handler for animation panel mousewheel logged. | Animation panel (mouse wheel scroll) |
| `MainFrame.on_column_splitter_changed` | wx event handler for column splitter changed. | Animation column splitter; Main column splitter; Right sidebar splitter |
| `MainFrame.on_display_transform_control_changed` | Persist and apply auto pan/scale, calibration toggles, mirror, slider values. | Enable Auto Pan & Scale; Invert Tilt Mapping; Auto Calibrate Forward Gaze; Forward Gaze Interval (seconds); Enable Auto Output Dynamic Enhancement Calibration; Enhancement Calibration Interval (seconds); Character Mirror |
| `MainFrame.on_dynamic_output_panel_size` | wx event handler for dynamic output panel size. | Output preview panel (resize) |
| `MainFrame.on_erase_background` | wx event handler for erase background. | Output window image panel (drag pan); Webcam popup preview panel; Scale curve preview panel; Source character image panel; Webcam preview (double-click opens popup) |
| `MainFrame.on_hover_help_timer` | wx event handler for hover help timer. | Hover help timer (controls window) |
| `MainFrame.on_layer_blend_changed` | Enable/disable compositing basic layers into previews and output. | Enable Layer Blending |
| `MainFrame.on_mouth_infer_cap_changed` | Set base GPU infer cap (Hz); persisted to ui state. | GPU Infer Cap (Hz) |
| `MainFrame.on_output_background_changed` | wx event handler for output background changed. | Background color picker |
| `MainFrame.on_output_background_image_browse` | wx event handler for output background image browse. | Browse Background Image |
| `MainFrame.on_output_background_mode_changed` | wx event handler for output background mode changed. | Background mode (solid / image / transparent capture) |
| `MainFrame.on_output_frame_interpolation_changed` | Set pose interpolation multiplier; adjusts effective infer cap. | Frame Interpolation multiplier |
| `MainFrame.on_postprocess_scroll_size` | wx event handler for postprocess scroll size. | Postprocess scroll area (resize) |
| `MainFrame.on_refresh_video_sources_clicked` | wx event handler for refresh video sources clicked. | Refresh video sources |
| `MainFrame.on_smooth_affine_30hz_changed` | Toggle smooth 30 Hz cached-affine display vs infer-rate-only display. | Smooth Motion 30Hz |
| `MainFrame.on_tha3_model_variant_changed` | wx event handler for tha3 model variant changed. | THA3 Model Variant |
| `MainFrame.on_unlimited_layers_changed` | Enable/disable unlimited layer system; show/hide BasicLayerWindow. | Enable Unlimited Layer System |
| `MainFrame.on_video_source_choice_changed` | wx event handler for video source choice changed. | Video source dropdown |
| `MainFrame.on_webcam_preview_double_click` | wx event handler for webcam preview double click. | Webcam preview (double-click opens popup) |
| `MainFrame.paint_scale_curve_panel` | — | Scale curve preview panel |
| `MainFrame.paint_source_image_panel` | — | Source character image panel |
| `MainFrame.paint_webcam_capture_panel` | — | Webcam preview (double-click opens popup) |
| `MainFrame.switch_to_compact_clicked` | — | Full controls: Switch to Compact |
| `MainFrame.toggle_full_controls_clicked` | — | Compact: Toggle Full Controls |

### MainFrame — Calibration

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame._perform_head_orientation_calibration` | Path A only: converter head orientation; never resets output dynamic enhancement. | — |
| `MainFrame.apply_enabled_auto_calibration_on_load` | — | — |
| `MainFrame.apply_neutral_calibration` | — | — |
| `MainFrame.refresh_auto_transform_status` | — | — |
| `MainFrame.refresh_scale_curve_status` | — | — |
| `MainFrame.update_neutral_face_direction` | — | — |
| `MainFrame.update_neutral_output_enhancement` | Refresh scale baseline and horizontal center; keep vertical neutral to avoid upward drift. | — |

### MainFrame — Display, output, and composition

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame._get_compose_signature` | Private helper for get compose signature. | — |
| `MainFrame._invalidate_render_caches` | Private helper for invalidate render caches. | — |
| `MainFrame._note_display_fps_tick` | Private helper for note display fps tick. | — |
| `MainFrame._present_smooth_output_frame` | Private helper for present smooth output frame. | — |
| `MainFrame._refresh_output_panel_only` | Private helper for refresh output panel only. | — |
| `MainFrame.apply_capture_output_frame_state` | — | — |
| `MainFrame.apply_output_frame_state` | — | — |
| `MainFrame.compose_foreground_rgba` | — | — |
| `MainFrame.create_composition_bitmap` | Builds UI widget(s) for composition bitmap. | — |
| `MainFrame.create_result_bitmap` | Builds UI widget(s) for result bitmap. | — |
| `MainFrame.create_rgba_bitmap_from_array` | Builds UI widget(s) for rgba bitmap from array. | — |
| `MainFrame.draw_cached_result_image` | — | — |
| `MainFrame.draw_capture_status_message` | — | — |
| `MainFrame.draw_nothing_yet_string` | — | — |
| `MainFrame.draw_result_wx_image` | — | — |
| `MainFrame.format_output_background_image_path_label` | — | — |
| `MainFrame.get_output_background_color` | Returns output background color. | — |
| `MainFrame.get_output_background_hex` | Returns output background hex. | — |
| `MainFrame.get_output_background_image_path` | Returns output background image path. | — |
| `MainFrame.get_output_background_mode` | Returns output background mode. | — |
| `MainFrame.get_output_background_signature` | Returns output background signature. | — |
| `MainFrame.handle_output_frame_geometry_changed` | — | — |
| `MainFrame.is_smooth_display_priority` | Prefer stable ~30Hz output pacing; accept infer/display latency. | — |
| `MainFrame.load_output_background_image` | — | — |
| `MainFrame.notify_output_background_changed` | — | — |
| `MainFrame.paint_output_background` | — | — |
| `MainFrame.render_default_pose_load_preview` | — | — |
| `MainFrame.render_pose_to_result_bitmap` | — | — |
| `MainFrame.render_pose_to_wx_image` | — | — |
| `MainFrame.sanitize_result_bitmap_alpha_fringe` | — | — |
| `MainFrame.sanitize_result_bitmap_for_obs_capture` | — | — |
| `MainFrame.sanitize_rgba_alpha_fringe` | — | — |
| `MainFrame.sanitize_window_geometry_in_state` | — | — |
| `MainFrame.schedule_capture_output_geometry_save` | Debounced/async scheduler for capture output geometry save. | — |
| `MainFrame.schedule_output_frame_geometry_sync` | Debounced/async scheduler for output frame geometry sync. | — |
| `MainFrame.set_output_background_image_path` | Updates output background image path. | — |
| `MainFrame.update_display_transform_state` | — | — |

### MainFrame — GPU infer and pose pipeline

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame._async_pose_infer_worker` | Private helper for async pose infer worker. | — |
| `MainFrame._finish_async_pose_infer` | Private helper for finish async pose infer. | — |
| `MainFrame._pose_any_changed` | Private helper for pose any changed. | — |
| `MainFrame._pose_infer_exempt_indices` | Private helper for pose infer exempt indices. | — |
| `MainFrame._pose_mouth_changed` | Private helper for pose mouth changed. | — |
| `MainFrame._pose_non_mouth_changed` | Private helper for pose non mouth changed. | — |
| `MainFrame.apply_negative_tilt_limit_to_pose` | — | — |
| `MainFrame.on_display_timer` | 30 Hz display tick: update cached affine and present output frame. | — |
| `MainFrame.on_infer_tick` | Infer scheduling tick: audio refresh + image source tick + async GPU infer. | — |
| `MainFrame.reset_frame_interpolation_buffers` | — | — |
| `MainFrame.resolve_scheduled_infer_pose` | — | — |
| `MainFrame.schedule_async_pose_infer` | Debounced/async scheduler for async pose infer. | — |
| `MainFrame.update_mediapipe_face_pose` | — | — |
| `MainFrame.update_result_image_bitmap` | Legacy entry: run both display refresh and infer scheduling. | — |

### MainFrame — Capture and video sources

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame.apply_camera_capture_settings` | — | — |
| `MainFrame.open_video_file_capture` | — | — |
| `MainFrame.refresh_and_autoload_video_source` | Refresh source list and auto-select first available source. | — |
| `MainFrame.refresh_video_source_choice` | — | — |
| `MainFrame.refresh_video_source_choice_async` | — | — |
| `MainFrame.schedule_active_capture_timer` | Debounced/async scheduler for active capture timer. | — |
| `MainFrame.schedule_idle_capture_timer` | Debounced/async scheduler for idle capture timer. | — |
| `MainFrame.update_capture_panel` | — | — |
| `MainFrame.update_capture_preview_bitmap` | — | — |
| `MainFrame.update_last_window_capture_text` | — | — |
| `MainFrame.update_video_source_status_text` | — | — |

### MainFrame — Layers and external bridge

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame.refresh_unlimited_layers_status` | — | — |

### MainFrame — Persistence and UI state

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame.apply_persistent_output_background_state` | — | — |
| `MainFrame.apply_persistent_slider_value_states` | — | — |
| `MainFrame.apply_persistent_ui_state` | — | — |
| `MainFrame.load_persistent_ui_state` | — | — |
| `MainFrame.save_basic_layer_window_geometry` | — | — |
| `MainFrame.save_persistent_ui_state` | — | — |
| `MainFrame.schedule_window_geometry_save` | Debounced/async scheduler for window geometry save. | — |

### MainFrame — Layout and geometry

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame.apply_client_rect_to_window` | — | — |
| `MainFrame.apply_controls_window_size_policy` | — | — |
| `MainFrame.apply_splitter_sash` | — | — |
| `MainFrame.handle_controls_frame_resized` | — | — |
| `MainFrame.on_compact_geometry_changed` | wx event handler for compact geometry changed. | — |
| `MainFrame.refresh_right_sidebar_scrolling` | — | — |
| `MainFrame.schedule_dynamic_output_layout_refresh` | Debounced/async scheduler for dynamic output layout refresh. | — |
| `MainFrame.schedule_postprocess_layout_refresh` | Debounced/async scheduler for postprocess layout refresh. | — |
| `MainFrame.schedule_refresh_controls_scrolling` | Debounced/async scheduler for refresh controls scrolling. | — |
| `MainFrame.set_static_text_if_changed` | Updates static text if changed. | — |
| `MainFrame.set_text_ctrl_if_changed` | Updates text ctrl if changed. | — |
| `MainFrame.set_wrapped_static_text_if_changed` | Updates wrapped static text if changed. | — |
| `MainFrame.wrap_static_text_to_parent` | — | — |

### MainFrame — Model and image source loading

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame.get_image_source_mode` | Returns image source mode. | — |
| `MainFrame.is_model_loaded` | — | — |
| `MainFrame.load_model_from_path` | — | — |
| `MainFrame.refresh_image_source_ui_visibility` | — | — |
| `MainFrame.resolve_character_model_path` | — | — |
| `MainFrame.update_load_model_buttons` | — | — |

### MainFrame — Window lifecycle and mode switching

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame._on_main_frame_activate` | Private helper for on main frame activate. | — |
| `MainFrame.create_animation_panel` | Builds UI widget(s) for animation panel. | — |
| `MainFrame.create_capture_panel` | Builds UI widget(s) for capture panel. | — |
| `MainFrame.create_compact_launcher_panel` | Builds UI widget(s) for compact launcher panel. | — |
| `MainFrame.create_controls_frame` | Builds UI widget(s) for controls frame. | — |
| `MainFrame.create_postprocess_panel` | Builds UI widget(s) for postprocess panel. | — |
| `MainFrame.create_timers` | Builds UI widget(s) for timers. | — |
| `MainFrame.create_ui` | Builds UI widget(s) for ui. | — |
| `MainFrame.get_dialog_parent` | Returns dialog parent. | — |
| `MainFrame.on_close` | wx event handler for close. | — |
| `MainFrame.refresh_model_loaded_ui_state` | — | — |

### MainFrame — Hover help and misc UI helpers

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame.bind_hover_help_recursive` | — | — |
| `MainFrame.create_display_transform_slider_control` | Builds UI widget(s) for display transform slider control. | — |
| `MainFrame.create_rotation_column` | Builds UI widget(s) for rotation column. | — |
| `MainFrame.on_control_hover_enter` | wx event handler for control hover enter. | — |
| `MainFrame.on_control_hover_leave` | wx event handler for control hover leave. | — |
| `MainFrame.on_hover_help_toggle_changed` | wx event handler for hover help toggle changed. | — |

### MainFrame — Internal helpers

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame.__init__` | Constructor for `MainFrame`. | — |
| `MainFrame._advance_pose_interpolation_after_infer` | Private helper for advance pose interpolation after infer. | — |
| `MainFrame._apply_layer_drag_motion` | Private helper for apply layer drag motion. | — |
| `MainFrame._apply_video_source_choices` | Private helper for apply video source choices. | — |
| `MainFrame._begin_layer_drag` | Private helper for begin layer drag. | — |
| `MainFrame._can_present_character_fast` | Private helper for can present character fast. | — |
| `MainFrame._compose_character_bitmap_from_keyframe` | Private helper for compose character bitmap from keyframe. | — |
| `MainFrame._end_layer_drag` | Private helper for end layer drag. | — |
| `MainFrame._extract_control_label_text` | Private helper for extract control label text. | — |
| `MainFrame._get_antialias_factor` | Private helper for get antialias factor. | — |
| `MainFrame._get_cached_background_rgba` | Private helper for get cached background rgba. | — |
| `MainFrame._hit_test_layer_slot` | Private helper for hit test layer slot. | — |
| `MainFrame._hit_test_selected_layer` | Private helper for hit test selected layer. | — |
| `MainFrame._init_video_source_choices_with_window` | Private helper for init video source choices with window. | — |
| `MainFrame._is_layer_editing_focus_window` | Private helper for is layer editing focus window. | — |
| `MainFrame._keyframe_cache_valid` | Private helper for keyframe cache valid. | — |
| `MainFrame._maybe_clear_layer_selection_after_deactivate` | Private helper for maybe clear layer selection after deactivate. | — |
| `MainFrame._needs_obs_alpha_sanitize` | Private helper for needs obs alpha sanitize. | — |
| `MainFrame._next_mediapipe_video_timestamp_ms` | Private helper for next mediapipe video timestamp ms. | — |
| `MainFrame._note_cached_affine_present_time` | Private helper for note cached affine present time. | — |
| `MainFrame._note_inference_fps_tick` | Private helper for note inference fps tick. | — |
| `MainFrame._note_input_fps_tick` | Private helper for note input fps tick. | — |
| `MainFrame._note_pose_present_time` | Private helper for note pose present time. | — |
| `MainFrame._panel_to_layer_delta` | Private helper for panel to layer delta. | — |
| `MainFrame._present_character_bitmap` | Private helper for present character bitmap. | — |
| `MainFrame._push_transparent_capture_foreground` | Private helper for push transparent capture foreground. | — |
| `MainFrame._record_fps_sample` | Private helper for record fps sample. | — |
| `MainFrame._rect_intersection_area` | Private helper for rect intersection area. | — |
| `MainFrame._refresh_fps_display` | Private helper for refresh fps display. | — |
| `MainFrame._refresh_transparent_capture_frame` | Private helper for refresh transparent capture frame. | — |
| `MainFrame._reset_mediapipe_video_timestamp` | Private helper for reset mediapipe video timestamp. | — |
| `MainFrame._run_dynamic_output_layout_refresh` | Private helper for run dynamic output layout refresh. | — |
| `MainFrame._run_postprocess_layout_refresh` | Private helper for run postprocess layout refresh. | — |
| `MainFrame._run_scheduled_refresh_controls_scrolling` | Private helper for run scheduled refresh controls scrolling. | — |
| `MainFrame._sanitize_result_bitmap_once` | Private helper for sanitize result bitmap once. | — |
| `MainFrame._should_clear_layer_selection_for_window` | Private helper for should clear layer selection for window. | — |
| `MainFrame._update_keyframe_cache` | Private helper for update keyframe cache. | — |
| `MainFrame._wrap_status_message_lines` | Private helper for wrap status message lines. | — |
| `MainFrame.adapt_main_window_to_controls` | — | — |
| `MainFrame.apply_frame_geometry_from_storage` | — | — |
| `MainFrame.apply_layer_blend_visibility` | — | — |
| `MainFrame.apply_mouth_persistent_state_to_args` | — | — |
| `MainFrame.apply_output_background_hex` | — | — |
| `MainFrame.apply_output_background_mode` | — | — |
| `MainFrame.autoconnect_video_source_on_startup` | Connect saved window/camera without requiring a manual dropdown click. | — |
| `MainFrame.background_hex_from_legacy_selection` | — | — |
| `MainFrame.bgr_frame_to_preview_bitmap` | — | — |
| `MainFrame.bring_controls_frame_to_front` | — | — |
| `MainFrame.build_camera_source_label` | — | — |
| `MainFrame.build_output_background_rgba` | — | — |
| `MainFrame.clamp_client_rect_to_visible_screen` | — | — |
| `MainFrame.clean_wx_image_transparent_rgb` | — | — |
| `MainFrame.clear_layer_selection` | — | — |
| `MainFrame.clear_result_image_bitmap` | Hard-reset output buffer. MemoryDC Clear() does not zero alpha on Windows. | — |
| `MainFrame.collect_display_transform_settings` | — | — |
| `MainFrame.collect_persistent_ui_state` | — | — |
| `MainFrame.collect_window_client_rect` | — | — |
| `MainFrame.composite_rgba_over_background` | Source-over composite; alpha=0 foreground pixels leave background unchanged. | — |
| `MainFrame.compute_scale_response` | — | — |
| `MainFrame.compute_target_scale` | — | — |
| `MainFrame.connect_default_video_source` | — | — |
| `MainFrame.convert_to_100` | — | — |
| `MainFrame.count_controls_recursive` | — | — |
| `MainFrame.create_transparent_composition_bitmap` | Character-only buffer for layer post-process (no output background baked in). | — |
| `MainFrame.default_capture_output_frame_rect_beside_output` | — | — |
| `MainFrame.default_output_frame_rect_beside_controls` | — | — |
| `MainFrame.describe_hover_help_for_control` | — | — |
| `MainFrame.destroy_transparent_capture_window` | — | — |
| `MainFrame.ensure_application_windows_visible` | — | — |
| `MainFrame.ensure_output_frame` | — | — |
| `MainFrame.ensure_result_bitmap_size` | — | — |
| `MainFrame.enumerate_camera_sources` | — | — |
| `MainFrame.extract_face_screen_motion` | — | — |
| `MainFrame.finalize_startup_autofit` | — | — |
| `MainFrame.format_window_capture_label` | — | — |
| `MainFrame.get_bundled_transparent_background_path` | Returns bundled transparent background path. | — |
| `MainFrame.get_controls_height_bounds` | Returns controls height bounds. | — |
| `MainFrame.get_controls_min_client_size` | Returns controls min client size. | — |
| `MainFrame.get_controls_window` | Returns controls window. | — |
| `MainFrame.get_default_character_models_dir` | Returns default character models dir. | — |
| `MainFrame.get_default_pose_list` | Returns default pose list. | — |
| `MainFrame.get_directshow_camera_device_names` | Returns directshow camera device names. | — |
| `MainFrame.get_display_present_cap_hz` | Returns display present cap hz. | — |
| `MainFrame.get_effective_infer_cap_hz` | Returns effective infer cap hz. | — |
| `MainFrame.get_last_window_capture_title` | Returns last window capture title. | — |
| `MainFrame.get_locked_output_client_size` | Returns locked output client size. | — |
| `MainFrame.get_mouth_infer_cap_hz` | Returns mouth infer cap hz. | — |
| `MainFrame.get_mouth_pose_indices` | Returns mouth pose indices. | — |
| `MainFrame.get_output_canvas_size` | Returns output canvas size. | — |
| `MainFrame.get_output_frame_interpolation_multiplier` | Returns output frame interpolation multiplier. | — |
| `MainFrame.get_output_frame_paint_colour` | Returns output frame paint colour. | — |
| `MainFrame.get_saved_client_rect` | Returns saved client rect. | — |
| `MainFrame.get_saved_window_capture` | Returns saved window capture. | — |
| `MainFrame.get_scale_curve_current_delta` | Returns scale curve current delta. | — |
| `MainFrame.get_scale_curve_domain` | Returns scale curve domain. | — |
| `MainFrame.get_scale_curve_neutral_face_size` | Returns scale curve neutral face size. | — |
| `MainFrame.get_scale_curve_samples` | Returns scale curve samples. | — |
| `MainFrame.get_ui_state_file_path` | Returns ui state file path. | — |
| `MainFrame.get_windows_camera_device_names` | Returns windows camera device names. | — |
| `MainFrame.hide_basic_layer_window` | — | — |
| `MainFrame.hide_hover_help_popup` | — | — |
| `MainFrame.initialize_adjustable_columns` | — | — |
| `MainFrame.initialize_headless_control_state` | — | — |
| `MainFrame.initialize_output_bitmap` | — | — |
| `MainFrame.invalidate_output_background_image_cache` | — | — |
| `MainFrame.is_acceptable_capture_frame` | — | — |
| `MainFrame.is_capture_preview_visible` | — | — |
| `MainFrame.is_capture_source_active` | — | — |
| `MainFrame.is_frame_interpolation_active` | — | — |
| `MainFrame.is_hover_help_enabled` | — | — |
| `MainFrame.is_layer_blend_enabled` | — | — |
| `MainFrame.is_plausible_camera_frame` | — | — |
| `MainFrame.is_smooth_affine_30hz_enabled` | — | — |
| `MainFrame.is_transparent_capture_background_enabled` | — | — |
| `MainFrame.is_unlimited_layers_enabled` | — | — |
| `MainFrame.is_webcam_popup_visible` | — | — |
| `MainFrame.is_window_rect_mostly_visible` | — | — |
| `MainFrame.maybe_apply_periodic_direction_calibration` | — | — |
| `MainFrame.maybe_apply_periodic_scale_calibration` | — | — |
| `MainFrame.needs_alpha_result_bitmap` | — | — |
| `MainFrame.normalize_background_hex` | — | — |
| `MainFrame.normalize_bgr_frame` | — | — |
| `MainFrame.on_basic_layer_window_closed` | wx event handler for basic layer window closed. | — |
| `MainFrame.on_layer_state_changed` | wx event handler for layer state changed. | — |
| `MainFrame.on_output_panel_left_down` | wx event handler for output panel left down. | — |
| `MainFrame.on_output_panel_left_up` | wx event handler for output panel left up. | — |
| `MainFrame.on_output_panel_motion` | wx event handler for output panel motion. | — |
| `MainFrame.on_window_activate_for_layer_selection` | wx event handler for window activate for layer selection. | — |
| `MainFrame.persist_basic_layers_state` | — | — |
| `MainFrame.pick_window_capture_interactive` | — | — |
| `MainFrame.prepend_window_capture_choices` | — | — |
| `MainFrame.probe_camera_backend` | — | — |
| `MainFrame.process_capture_output_geometry_save` | — | — |
| `MainFrame.process_output_frame_geometry_sync` | — | — |
| `MainFrame.process_window_geometry_save` | — | — |
| `MainFrame.read_capture_frame_bgr` | — | — |
| `MainFrame.read_plausible_camera_frame` | — | — |
| `MainFrame.refresh_controls_scrolling` | — | — |
| `MainFrame.refresh_dynamic_output_scroll` | — | — |
| `MainFrame.refresh_dynamic_output_status_layout` | — | — |
| `MainFrame.refresh_layer_blend_status` | — | — |
| `MainFrame.refresh_output_frame_chrome` | — | — |
| `MainFrame.refresh_postprocess_scroll_layout` | — | — |
| `MainFrame.refresh_postprocess_static_text_wrap` | — | — |
| `MainFrame.relativize_path_for_persistence` | — | — |
| `MainFrame.relativize_persistent_path_fields` | — | — |
| `MainFrame.release_video_capture` | — | — |
| `MainFrame.reload_persistent_ui_state_from_disk` | — | — |
| `MainFrame.reparent_output_frame_for_owner` | — | — |
| `MainFrame.request_scale_curve_repaint` | — | — |
| `MainFrame.resolve_layer_asset_path` | — | — |
| `MainFrame.resolve_output_background_image_path` | — | — |
| `MainFrame.resolve_persistent_output_background_hex` | — | — |
| `MainFrame.resolve_persistent_output_background_image_path` | — | — |
| `MainFrame.resolve_persistent_output_background_mode` | — | — |
| `MainFrame.resolve_persistent_path_fields` | — | — |
| `MainFrame.restore_compact_frame_geometry` | — | — |
| `MainFrame.restore_controls_frame_geometry` | — | — |
| `MainFrame.scale_image_cover` | — | — |
| `MainFrame.set_neutral_face_screen_motion` | Updates neutral face screen motion. | — |
| `MainFrame.set_neutral_head_roll_deg` | Updates neutral head roll deg. | — |
| `MainFrame.set_video_capture_camera` | Updates video capture camera. | — |
| `MainFrame.set_video_capture_file` | Updates video capture file. | — |
| `MainFrame.set_video_capture_window` | Updates video capture window. | — |
| `MainFrame.setup_hover_help_bindings` | — | — |
| `MainFrame.should_draw_result_bitmap_with_alpha` | — | — |
| `MainFrame.should_infer_pose` | — | — |
| `MainFrame.should_mirror_capture_preview` | — | — |
| `MainFrame.should_process_mediapipe` | — | — |
| `MainFrame.should_refresh_cached_affine` | — | — |
| `MainFrame.should_update_capture_preview_ui` | — | — |
| `MainFrame.show_basic_layer_window` | Create/show BasicLayerWindow when unlimited layers enabled. | — |
| `MainFrame.show_compact_launcher` | — | — |
| `MainFrame.show_full_controls_window` | — | — |
| `MainFrame.show_hover_help_popup` | — | — |
| `MainFrame.startup_show_full_controls` | — | — |
| `MainFrame.sync_output_frame_owner` | Both windows stay independent top-level frames (no owner/parent link). | — |
| `MainFrame.sync_transparent_capture_output_window` | — | — |
| `MainFrame.tick_tha4_student_source` | — | — |
| `MainFrame.try_apply_auto_forward_gaze_calibration` | Periodic or on-load auto run of model-input Calibrate Forward Gaze. | — |
| `MainFrame.try_startup_auto_connect_camera` | — | — |
| `MainFrame.uniconize_window` | — | — |
| `MainFrame.update_output_background_controls_visibility` | — | — |
| `MainFrame.update_source_image_bitmap` | Refresh source preview bitmap; overlays basic layers when blending is on. | — |
| `MainFrame.wx_bitmap_to_rgba_array` | — | — |
| `MainFrame.wx_image_to_rgba_array` | — | — |
