# Custom Function Index

English index of **custom** functions in the Load Preview experiment.
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

Two related but **independent** calibrations (see design manual **ix-025**):

| Path | Function | Effect | Manual UI | Periodic UI (= auto-click same manual) |
| --- | --- | --- | --- | --- |
| **A — head orientation** | `_perform_head_orientation_calibration` | `pose_converter.apply_face_orientation_calibration()` only | UI-A01 / UI-A09 / UI-B04 | `enable_direction_calibration` + interval |
| **B — camera dynamic enhancement** | `_perform_output_dynamic_enhancement_calibration` (MediaPipe) | `update_neutral_output_enhancement(latest_motion)` | UI-A02 / UI-A10 | `enable_scale_calibration` + interval (**skipped in Mouse mode**) |
| **B — mouse ix-023** | `_perform_output_dynamic_enhancement_calibration` (Mouse) → `_calibrate_mouse_dynamic_enhancement_ix023` | Zone center + gaze neutral + path B neutral + **attached** path A at forward gaze pose | UI-A02 / UI-A10 (same buttons) | `enable_mouse_auto_calibration` (UI-B07) + interval |

**Boundary:** path A must **not** call `update_neutral_output_enhancement` or reset display offset/scale. Camera path B must **not** call `apply_face_orientation_calibration`. Mouse ix-023 may call path A **only** inside `_calibrate_mouse_dynamic_enhancement_ix023` (not in camera path B). Periodic hooks must call the same `_perform_*` as the manual buttons (`_refresh_after_output_dynamic_enhancement_calibration` for path B).

## Quick reference — display vs infer timers

| Timer | Handler | Interval | Role |
| --- | --- | --- | --- |
| `capture_timer` | `update_capture_panel` | ~66 ms | Webcam / window capture |
| `display_timer` | `on_display_timer` | 30 ms (~30 Hz) | Cached affine present, Out FPS |
| `animation_timer` | `on_infer_tick` | dynamic | Schedule async GPU infer |

## `basic_layer_window.py`

Unlimited layer editor window (opened when Enable Unlimited Layer System is on).

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `SpineRayReferencePanel.__init__` | Constructor for `SpineRayReferencePanel`. | — |
| `SpineRayReferencePanel._rebuild_live_snapshot` | Private helper for rebuild live snapshot. | — |
| `SpineRayReferencePanel.refresh_diagram_live` | Update diagram from current output binding pose (tilt / mocap). | — |
| `SpineRayReferencePanel.sync_from_main_frame` | — | — |
| `SpineRayReferencePanel._diagram_geometry` | Private helper for diagram geometry. | — |
| `SpineRayReferencePanel._marker_diagram_point` | Private helper for marker diagram point. | — |
| `SpineRayReferencePanel._draw_binding_markers` | Private helper for draw binding markers. | — |
| `SpineRayReferencePanel._on_neck_ratio_changed` | Private helper for on neck ratio changed. | — |
| `SpineRayReferencePanel._on_body_bind_changed` | Private helper for on body bind changed. | — |
| `SpineRayReferencePanel._on_head_bind_changed` | Private helper for on head bind changed. | — |
| `SpineRayReferencePanel._on_lean_pos_changed` | Private helper for on lean pos changed. | — |
| `SpineRayReferencePanel._on_lean_roll_changed` | Private helper for on lean roll changed. | — |
| `SpineRayReferencePanel._on_diagram_paint` | Private helper for on diagram paint. | — |
| `SpineRayReferencePanel._diagram_label_font` | Private helper for diagram label font. | — |
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
| `BasicLayerWindow.refresh_spine_diagram` | — | — |
| `BasicLayerWindow._character_preview_bitmap` | Private helper for character preview bitmap. | Basic Layer window (internal) |
| `BasicLayerWindow._character_row_display_name` | Private helper for character row display name. | Basic Layer window (internal) |
| `BasicLayerWindow._refresh_character_row` | Private helper for refresh character row. | Basic Layer window (internal) |
| `BasicLayerWindow._populate_row` | Private helper for populate row. | Basic Layer window (internal) |
| `BasicLayerWindow._populate_binding_choice` | Rebuild the binding dropdown from the live layer list (excluding the | Basic Layer window (internal) |
| `BasicLayerWindow._refresh_detail_dock` | Private helper for refresh detail dock. | Basic Layer window (internal) |
| `BasicLayerWindow.apply_selection` | — | — |
| `BasicLayerWindow._select_slot` | Private helper for select slot. | Basic Layer window (internal) |
| `BasicLayerWindow._current_detail_slot` | Private helper for current detail slot. | Basic Layer window (internal) |
| `BasicLayerWindow._load_asset` | Private helper for load asset. | Layer row: Load |
| `BasicLayerWindow._on_clear_asset` | Private helper for on clear asset. | Detail dock: Clear asset |
| `BasicLayerWindow._on_add_layer` | Private helper for on add layer. | Basic Layer window (internal) |
| `BasicLayerWindow._on_delete_layer` | Private helper for on delete layer. | Basic Layer window (internal) |
| `BasicLayerWindow._move_layer` | Private helper for move layer. | Layer row: Move up/down |
| `BasicLayerWindow._on_scale_changed` | Private helper for on scale changed. | Detail dock: Scale slider |
| `BasicLayerWindow._on_rotation_changed` | Private helper for on rotation changed. | Detail dock: Rotation slider |
| `BasicLayerWindow._on_reset_transform` | Private helper for on reset transform. | Detail dock: Reset transform |
| `BasicLayerWindow._on_motion_changed` | Private helper for on motion changed. | Basic Layer window (internal) |
| `BasicLayerWindow._on_swing_amplitude_changed` | Private helper for on swing amplitude changed. | Basic Layer window (internal) |
| `BasicLayerWindow._on_swing_speed_changed` | Private helper for on swing speed changed. | Basic Layer window (internal) |
| `BasicLayerWindow._on_motion_profile_changed` | Private helper for on motion profile changed. | Basic Layer window (internal) |
| `BasicLayerWindow._on_edit_swing_pivot` | Private helper for on edit swing pivot. | Basic Layer window (internal) |
| `BasicLayerWindow._on_orbit_changed` | Private helper for on orbit changed. | Basic Layer window (internal) |
| `BasicLayerWindow._on_orbit_aux_changed` | Private helper for on orbit aux changed. | Basic Layer window (internal) |
| `BasicLayerWindow._on_edit_orbit_pivot` | Private helper for on edit orbit pivot. | Basic Layer window (internal) |
| `BasicLayerWindow._orbit_pivot_reference_image` | Private helper for orbit pivot reference image. | Basic Layer window (internal) |
| `BasicLayerWindow._populate_orbit_aux_choice` | Private helper for populate orbit aux choice. | Basic Layer window (internal) |
| `BasicLayerWindow._on_smooth_alpha_changed` | Private helper for on smooth alpha changed. | Basic Layer window (internal) |
| `BasicLayerWindow._on_detail_changed` | Private helper for on detail changed. | Detail dock: Visible / binding choice |

## `character_edge_postprocess.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `normalize_character_edge_mode` | — | — |
| `clamp_character_edge_width` | — | — |
| `_dilate_alpha` | Private helper for dilate alpha. | — |
| `_dilate_alpha_fractional` | Morphological dilation with fractional radius (linear blend between steps). | — |
| `_composite_rgba_under` | Source-over composite of two RGBA arrays (same shape). | — |
| `composite_rgba_arrays` | Source-over composite of two RGBA arrays (same shape). | — |
| `apply_character_edge_outline` | — | — |
| `apply_character_edge_postprocess` | — | — |

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

## `layer_interaction.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `panel_to_layer_delta` | — | — |
| `layer_to_panel_delta` | — | — |
| `_point_in_rotated_rect` | Private helper for point in rotated rect. | — |
| `_handle_rect` | Private helper for handle rect. | — |
| `hit_test_layer_edit` | — | — |
| `hit_test_resolved_rect` | Hit-test a click against an already-resolved layer rect (the exact box | — |
| `apply_move_delta` | — | — |
| `apply_scale_from_drag` | — | — |
| `nudge_layer` | — | — |
| `hit_test_layer_slot` | — | — |

## `layer_runtime.py`

Basic layer stack data model, geometry, compositing, and JSON persistence.

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `clamp_binding_smooth_alpha` | — | — |
| `clamp_body_bind_lean_follow_gain` | — | — |
| `clamp_neck_anchor_ratio` | — | — |
| `clamp_bind_ray_t` | Legacy ratio 0–1; prefer bind_ray_percent_to_ratio. | — |
| `normalize_bind_ray_percent` | — | — |
| `apply_body_head_tilt_opposite_to_pose` | When opposite: body roll negates neck roll; head (neck_z) keeps mocap direction. | — |
| `bind_ray_percent_to_ratio` | — | — |
| `layer_binding_ray_percent` | — | — |
| `layer_binding_neck_anchor_ratio` | — | — |
| `migrate_bind_ray_percent_from_state` | — | — |
| `binding_smooth_alpha_for_layer` | — | — |
| `normalize_binding_target` | — | — |
| `binding_target_label` | — | — |
| `truncate_display_filename` | — | — |
| `format_layer_row_title` | — | — |
| `classify_layer_asset_kind` | Return empty \| image \| gif \| unknown for a layer asset path. | — |
| `layer_asset_kind_label` | — | — |
| `format_layer_row_summary` | — | — |
| `contrast_highlight_colour` | Pick a highlight colour opposite to the output background RGB. | — |
| `_lerp_angle_deg` | Private helper for lerp angle deg. | — |
| `_rate_limit_scalar` | Private helper for rate limit scalar. | — |
| `_binding_inherited_rotation_deg` | Private helper for binding inherited rotation deg. | — |
| `effective_layer_rotation_deg` | — | — |
| `parse_layer_binding_slot` | — | — |
| `find_layer_slot` | Return an existing layer without resurrecting deleted slots. | — |
| `sanitize_layer_references` | Drop bindings/aux targets that point at layers no longer in the stack. | — |
| `cleanup_layer_references` | Clear cross-layer pointers after ``remove_layer``. | — |
| `_parse_follow_rotation_same` | Private helper for parse follow rotation same. | — |
| `_parse_follow_rotation_reverse` | Private helper for parse follow rotation reverse. | — |
| `LayerTransform.to_dict` | — | — |
| `LayerTransform.from_dict` | — | — |
| `center_layer_transform` | Align layer image center to output window center (512-space origin). | — |
| `reset_layer_transform` | Reset layer pose to default centered pose (position, scale, rotation). | — |
| `BasicLayerSlot.to_dict` | — | — |
| `BasicLayerSlot.from_dict` | — | — |
| `BasicLayersState.__post_init__` | Constructor for `BasicLayersState`. | — |
| `BasicLayersState.character_stack_position` | Stack index (bottom = 0) where the character sits: above every | — |
| `BasicLayersState.total_stack_positions` | Bottom-to-top draw slots: every layer plus the character sentinel. | — |
| `BasicLayersState.next_slot_id` | Stable, never-reused id for a newly added layer (id != stack pos). | — |
| `BasicLayersState.add_layer` | Append a fresh empty layer on TOP of the stack (in front of character). | — |
| `BasicLayersState.remove_layer` | Delete an entire layer slot (not just its asset). | — |
| `BasicLayersState.get_slot` | Returns slot. | — |
| `BasicLayersState.sorted_layers_for_draw` | — | — |
| `BasicLayersState.sorted_layers_for_ui` | — | — |
| `BasicLayersState.to_dict` | — | — |
| `BasicLayersState.from_dict` | — | — |
| `default_stack_position_for_slot` | — | — |
| `occlusion_for_stack_position` | Seed default only; runtime occlusion is owned by the layer + normalize. | — |
| `layer_at_stack_position` | — | — |
| `normalize_layer_stack_positions` | Pack layers into a contiguous bottom-to-top stack with the character in | — |
| `iter_ui_list_top_to_bottom` | UI list top-to-bottom (top = drawn last / front). Character row sits at | — |
| `stack_position_can_move_up` | — | — |
| `stack_position_can_move_down` | — | — |
| `default_swing_phase_rad` | — | — |
| `normalize_motion_mode` | — | — |
| `clamp_orbit_radius` | — | — |
| `clamp_orbit_plane_tilt_deg` | — | — |
| `clamp_orbit_speed_deg_per_sec` | — | — |
| `clamp_orbit_scale` | — | — |
| `normalize_swing_speed_profile` | — | — |
| `clamp_swing_pivot_u` | — | — |
| `clamp_swing_pivot_v` | — | — |
| `clamp_swing_amplitude_deg` | — | — |
| `clamp_swing_speed_deg_per_sec` | — | — |
| `layer_has_active_swing` | — | — |
| `basic_layers_state_has_active_motion` | — | — |
| `compute_swing_angle_deg` | — | — |
| `compute_orbit_state` | Evaluate the tilted-plane circular orbit and project it to the screen. | — |
| `layer_has_active_orbit` | — | — |
| `default_layer_slot` | — | — |
| `BindingContext.scale_x` | — | — |
| `BindingContext.scale_y` | — | — |
| `BindingContext.pose_head_layer_offset` | Mocap head pose offset in 512-normalized layer space (center origin). | — |
| `BindingContext.pose_head_roll_deg` | — | — |
| `BindingContext._mocap_spine_tilt_deg` | Private helper for mocap spine tilt deg. | — |
| `BindingContext.spine_lower_angle_deg` | Segment 1 (bottom→neck): model/diagram body segment; may oppose head when configured. | — |
| `BindingContext.spine_upper_angle_deg` | Segment 2 (neck→head): follows display tilt; decoupled from lower when opposite. | — |
| `BindingContext.spine_ray_angle_deg` | Full head-ray direction (upper segment); kept for compatibility. | — |
| `BindingContext.spine_ray_unit_vector` | Unit vector along spine segment; 0° = straight up (screen −Y). | — |
| `BindingContext._character_scaled_height_px` | Private helper for character scaled height px. | — |
| `BindingContext._resolved_spine_ratios` | Private helper for resolved spine ratios. | — |
| `BindingContext.character_segment_lengths_px` | Return (lower_segment_len, upper_segment_len) in canvas pixels. | — |
| `BindingContext.character_neck_on_lower_spine` | Neck joint at end of segment 1; returns (neck_x, neck_y, lower_angle_deg). | — |
| `BindingContext.dynamic_enhancement_tilt_deg` | On-screen torso roll the body layer-bind (anchor ray AND sprite | — |
| `BindingContext.character_body_bind_on_spine` | Body-bind anchor on model lower spine ray (diagram / internal segment). | — |
| `BindingContext.character_body_layer_bind_on_spine` | Body-bind anchor for layer follow: dynamic enhancement direction, not model-opposite. | — |
| `BindingContext.character_head_bind_on_spine` | Head-bind anchor on upper spine ray (unbounded % of segment length). | — |
| `BindingContext.character_body_bind_reference_on_spine` | — | — |
| `BindingContext.character_head_bind_reference_on_spine` | — | — |
| `BindingContext.head_spine_distance_px` | — | — |
| `BindingContext.character_head_on_spine_ray` | Head joint at end of segment 2 (for geometry); returns (head_x, head_y, upper_angle_deg). | — |
| `BindingContext.head_binding_rotation_deg` | Sprite roll on head bind: upper spine angle (already carries the | — |
| `BindingContext.body_binding_rotation_deg` | Sprite roll for body bind: uses the ROLL lean gain, independent of the | — |
| `BindingContext.character_feet_anchor` | Canvas anchor at character stack bottom-center (output frame bottom). | — |
| `BindingContext.character_bottom_anchor` | — | — |
| `BindingContext.character_head_anchor` | — | — |
| `build_spine_diagram_points` | Live spine joints in output canvas space (same as layer binding resolver). | — |
| `map_canvas_point_to_diagram` | — | — |
| `compute_spine_diagram_layout` | — | — |
| `_project_point_on_segment` | Private helper for project point on segment. | — |
| `migrate_layer_bind_ray_percents` | One-time fill for layers bound before per-layer ray % was persisted. | — |
| `migrate_layer_bind_neck_ratios` | One-time fill for layers bound before per-layer neck ratio was persisted. | — |
| `collect_spine_binding_markers` | Collect body/head anchor and bound-layer positions along spine segments. | — |
| `_clean_transparent_rgb` | Zero RGB on fully transparent pixels to avoid green fringe when scaling. | — |
| `_pil_rgba_to_wx_image` | Private helper for pil rgba to wx image. | — |
| `_gif_pil_frame_to_rgba` | Convert one GIF sub-frame to RGBA, honoring palette transparency index. | — |
| `_gif_frame_disposal` | Private helper for gif frame disposal. | — |
| `_gif_composite_frame_onto` | Alpha-composite one GIF sub-frame onto the running canvas. | — |
| `_gif_frame_offset` | Private helper for gif frame offset. | — |
| `_load_gif_composited_frames` | Composite animated GIF with disposal so cleared regions stay transparent. | — |
| `_GifAnimationSource.load` | — | — |
| `_GifAnimationSource.frame_at_time` | — | — |
| `_pil_rgba_to_numpy` | Decode a PIL image to sanitized straight-alpha RGBA (wx-free path). | — |
| `_GifNumpySource.load` | — | — |
| `_GifNumpySource.frame_index` | — | — |
| `scale_image_to_bitmap` | Scale PNG to bitmap preserving alpha (avoids green halos from wx.Image.Scale). | — |
| `LayerGeometryResolver.map_coord` | — | — |
| `LayerGeometryResolver.resolve_layer_rect_local` | — | — |
| `LayerGeometryResolver._rect_center` | Private helper for rect center. | — |
| `LayerGeometryResolver._rect_from_center` | Private helper for rect from center. | — |
| `LayerGeometryResolver._apply_binding` | Private helper for apply binding. | — |
| `LayerGeometryResolver.resolve_all` | — | — |
| `HeadBindingPoseFilter.__init__` | Constructor for `HeadBindingPoseFilter`. | — |
| `HeadBindingPoseFilter.reset` | — | — |
| `HeadBindingPoseFilter.filter` | — | — |
| `HeadBindingPoseFilter._filter_axis` | Private helper for filter axis. | — |
| `LayerBindingSmoother.__init__` | Constructor for `LayerBindingSmoother`. | — |
| `LayerBindingSmoother.reset_slot` | — | — |
| `LayerBindingSmoother.reset_all` | — | — |
| `LayerBindingSmoother.apply` | — | — |
| `compute_orbit_render_plan` | Per-frame plan for circular-orbit objects. | — |
| `apply_orbit_to_resolved` | — | — |
| `resolve_layer_rects` | — | — |
| `resolved_layer_rotation_deg` | — | — |
| `LayerAssetCache.__init__` | Constructor for `LayerAssetCache`. | — |
| `LayerAssetCache.close` | — | — |
| `LayerAssetCache.clear` | — | — |
| `LayerAssetCache._cache_key` | Private helper for cache key. | — |
| `LayerAssetCache._release_animated` | Private helper for release animated. | — |
| `LayerAssetCache.invalidate` | — | — |
| `LayerAssetCache._load_static_image` | Private helper for load static image. | — |
| `LayerAssetCache._get_gif_source` | Private helper for get gif source. | — |
| `LayerAssetCache._gif_frame_index` | Private helper for gif frame index. | — |
| `LayerAssetCache._load_static_rgba` | Private helper for load static rgba. | — |
| `LayerAssetCache._get_gif_numpy_source` | Private helper for get gif numpy source. | — |
| `LayerAssetCache.load_image_rgba` | Straight-alpha RGBA numpy frame for a layer (wx-free render path). | — |
| `LayerAssetCache.preview_image` | First-frame preview for list thumbnails (GIF stays static). | — |
| `LayerAssetCache.load_image` | — | — |
| `LayerAssetCache.get_draw_bitmap` | Returns draw bitmap. | — |
| `LayerAssetCache.thumbnail_bitmap` | — | — |
| `LayerCompositor.draw_layer_on_dc` | — | — |
| `LayerCompositor.draw_layers_group` | — | — |
| `LayerCompositor.draw_post_process_stack` | Post-process: composite character keyframe and layer stack on output. | — |
| `LayerCompositor.draw_unified_stack` | — | — |
| `LayerCompositor.hit_test_layer_slot` | — | — |
| `LayerCompositor.draw_selection_highlight` | — | — |
| `get_basic_layers_directory` | Returns basic layers directory. | — |
| `_append_layer_load_log` | Private helper for append layer load log. | — |
| `_load_layers_from_slot_files` | Private helper for load layers from slot files. | — |
| `save_basic_layers_state` | Persist layer slots to `basic_layers/*.json`. | — |
| `load_basic_layers_state` | Load layer slots from disk into BasicLayersState. | — |
| `move_layer_z_order` | Change stack position of a layer slot by delta. | — |

## `layer_swing_pivot_dialog.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `_PivotCanvasPanel.__init__` | Constructor for `_PivotCanvasPanel`. | — |
| `_PivotCanvasPanel.get_pivot` | Returns pivot. | — |
| `_PivotCanvasPanel._on_size` | Private helper for on size. | — |
| `_PivotCanvasPanel._rebuild_display_bitmap` | Private helper for rebuild display bitmap. | — |
| `_PivotCanvasPanel._image_point_from_client` | Private helper for image point from client. | — |
| `_PivotCanvasPanel._on_left_down` | Private helper for on left down. | — |
| `_PivotCanvasPanel._on_paint` | Private helper for on paint. | — |
| `PivotEditDialog.__init__` | Constructor for `PivotEditDialog`. | — |
| `PivotEditDialog.get_pivot` | Returns pivot. | — |
| `PivotEditDialog._update_coord_label` | Private helper for update coord label. | — |
| `show_pivot_edit_dialog` | — | — |
| `SwingPivotEditDialog.__init__` | Constructor for `SwingPivotEditDialog`. | — |
| `SwingPivotEditDialog._update_coord_label` | Private helper for update coord label. | — |
| `SwingPivotEditDialog.apply_to_layer` | — | — |
| `show_swing_pivot_edit_dialog` | — | — |

## `mouse_mocap_driver.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `normalize_mocap_input_mode` | — | — |
| `clamp` | — | — |
| `clamp_blink_interval_sec` | — | — |
| `clamp_horizontal_tilt_mix` | — | — |
| `MouseTrackingSurface.center_x` | — | — |
| `MouseTrackingSurface.center_y` | — | — |
| `MouseTrackingSurface.half_width` | — | — |
| `MouseTrackingSurface.half_height` | — | — |
| `MouseTrackingSurface.aspect_ratio` | — | — |
| `get_mouse_tracking_surface` | Union of all wx displays (virtual desktop), for multi-monitor consistency. | — |
| `MouseCenterZone.clamped` | — | — |
| `MouseCenterZone.from_norm_edges` | Build zone from normalized edges (Y-up: bottom <= top). Clamps edges to screen bounds. | — |
| `MouseCenterZone.with_center_at_preserving_size` | Move zone center to (nx, ny) without changing half_width/height (e.g. auto-calibration). | — |
| `MouseCenterZone.clamped_to_surface` | Keep the axis-aligned zone inside the normalized screen [-1, 1] box. | — |
| `MouseCenterZone.to_dict` | — | — |
| `MouseCenterZone.from_mapping` | — | — |
| `MouseMocapConfig.__post_init__` | Constructor for `MouseMocapConfig`. | — |
| `zone_local_coords` | — | — |
| `is_horizontally_outside_center_zone` | — | — |
| `is_vertically_outside_center_zone` | — | — |
| `build_mouse_dynamic_face_screen_motion` | Build center_x/center_y/face_size for output dynamic enhancement. | — |
| `compute_mouse_horizontal_roll_deg` | Roll delta (degrees) when mouse is horizontally outside the center zone. | — |
| `blend_mouse_head_roll_degrees` | mix=1 → horizontal tilt only; mix=0 → neutral roll (no display tilt). | — |
| `mouse_gaze_relative_coords` | Screen mouse relative to calibrated forward-gaze point (0,0 = looking straight ahead). | — |
| `sample_global_mouse_normalized` | Map virtual-desktop mouse position to [-1, 1], Y up. | — |
| `is_mouse_inside_center_zone` | — | — |
| `face_size_from_zone_distance` | Map distance outside zone center to a face_size similar to MediaPipe bbox scale. | — |
| `extract_head_roll_degrees` | — | — |
| `build_blink_blendshapes` | — | — |
| `build_eye_look_blendshapes` | — | — |
| `build_head_xform_matrix` | — | — |
| `build_mouse_mediapipe_face_pose` | — | — |

## `mouse_zone_panel.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `_nice_pixel_step` | Private helper for nice pixel step. | — |
| `_highlight_edges_for_mode` | Private helper for highlight edges for mode. | — |
| `MouseZonePanel.__init__` | Constructor for `MouseZonePanel`. | — |
| `MouseZonePanel.get_zone` | Returns zone. | — |
| `MouseZonePanel.set_zone` | Updates zone. | — |
| `MouseZonePanel.set_mouse_position` | Updates mouse position. | — |
| `MouseZonePanel.on_erase_background` | wx event handler for erase background. | — |
| `MouseZonePanel._tracking_surface` | Private helper for tracking surface. | — |
| `MouseZonePanel._screen_draw_rect` | Letterboxed screen rect preserving real pixel aspect ratio. | — |
| `MouseZonePanel._norm_to_panel` | Private helper for norm to panel. | — |
| `MouseZonePanel._panel_to_norm` | Private helper for panel to norm. | — |
| `MouseZonePanel._zone_norm_edges` | Private helper for zone norm edges. | — |
| `MouseZonePanel._inner_rect` | Private helper for inner rect. | — |
| `MouseZonePanel._draw_edge_highlights` | Private helper for draw edge highlights. | — |
| `MouseZonePanel._draw_mouse_position_marker` | Private helper for draw mouse position marker. | — |
| `MouseZonePanel._draw_pixel_rulers` | Private helper for draw pixel rulers. | — |
| `MouseZonePanel._hit_test` | Private helper for hit test. | — |
| `MouseZonePanel._update_hover_feedback` | Private helper for update hover feedback. | — |
| `MouseZonePanel._active_highlight_mode` | Private helper for active highlight mode. | — |
| `MouseZonePanel._emit_zone_changed` | Private helper for emit zone changed. | — |
| `MouseZonePanel._apply_resize_drag` | Private helper for apply resize drag. | — |
| `MouseZonePanel.on_paint` | wx event handler for paint. | — |
| `MouseZonePanel.on_left_down` | wx event handler for left down. | — |
| `MouseZonePanel.on_left_up` | wx event handler for left up. | — |
| `MouseZonePanel.on_leave_window` | wx event handler for leave window. | — |
| `MouseZonePanel.on_motion` | wx event handler for motion. | — |

## `numpy_edit_chrome.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `_rotate_point` | Private helper for rotate point. | — |
| `render_selection_chrome_rgba` | Return a transparent RGBA canvas with the selection rectangle outline and | — |

## `numpy_layer_compositor.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `_RgbaSizeView.__init__` | Constructor for `_RgbaSizeView`. | — |
| `_RgbaSizeView.GetWidth` | — | — |
| `_RgbaSizeView.GetHeight` | — | — |
| `_mat3_translate` | Private helper for mat3 translate. | — |
| `_mat3_rotate` | Private helper for mat3 rotate. | — |
| `_fit_canvas` | Private helper for fit canvas. | — |
| `_paste_rgba_onto_canvas` | Private helper for paste rgba onto canvas. | — |
| `_warp_rgba_onto_canvas` | Private helper for warp rgba onto canvas. | — |
| `_render_layer_contribution` | Private helper for render layer contribution. | — |
| `compose_full_stack_rgba` | Composite the full layer stack (character in the middle) to a straight | — |

## `output_backends.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `normalize_output_backend` | — | — |
| `backend_for_background_mode` | Derive the delivery backend implied by an output background mode. | — |
| `resolve_output_backend` | Honor an explicit persisted `output_capture_backend` override, otherwise | — |
| `recommended_backend_for_tool` | — | — |
| `backend_label` | — | — |

## `portable_bootstrap.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `_show_message` | Private helper for show message. | — |
| `_deploy_bat_path` | Private helper for deploy bat path. | — |
| `guide_user_to_deploy` | — | — |
| `ensure_portable_ready` | — | — |

## `portable_paths.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `get_portable_root` | Returns portable root. | — |
| `resolve_portable_root_from_launcher` | Resolve repo root when the launcher exe/bat lives at root or scripts/launch/. | — |
| `get_demo_data_dir` | Returns demo data dir. | — |
| `resolve_mediapipe_task_path` | — | — |
| `get_portable_missing_components` | Returns portable missing components. | — |
| `_python_probe_ok` | Private helper for python probe ok. | — |
| `_iter_portable_python_candidates` | Private helper for iter portable python candidates. | — |
| `resolve_system_python_exe` | — | — |
| `resolve_portable_python_exe` | — | — |
| `get_mouse_student_venv_absolute` | Returns mouse student venv absolute. | — |
| `test_mouse_student_runtime` | — | — |
| `get_tha4_mouse_student_missing_components` | Returns tha4 mouse student missing components. | — |
| `portable_mouse_student_ready` | — | — |
| `face_capture_assets_ready` | — | — |
| `get_tha4_face_capture_missing_components` | Returns tha4 face capture missing components. | — |
| `get_tha4_student_missing_components` | Legacy name: full face-capture student readiness (includes MediaPipe). | — |
| `portable_tha4_student_ready` | — | — |
| `portable_app_ready` | — | — |
| `portable_runtime_ready` | — | — |
| `get_workspace_dir` | Returns workspace dir. | — |
| `_legacy_ui_state_path` | Private helper for legacy ui state path. | — |
| `_legacy_basic_layers_dir` | Private helper for legacy basic layers dir. | — |
| `_sanitize_ui_state_path_fields` | Private helper for sanitize ui state path fields. | — |
| `_sanitize_ui_state_file` | Private helper for sanitize ui state file. | — |
| `_maybe_migrate_workspace_state` | Private helper for maybe migrate workspace state. | — |
| `resolve_ui_state_file_path` | — | — |
| `resolve_load_preview_script` | — | — |

## `rgba_capture_compose.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `wx_image_to_rgba_array` | — | — |
| `scale_rgba` | — | — |
| `sanitize_transparent_rgb` | — | — |
| `_invert_affine` | Private helper for invert affine. | — |
| `compose_character_rgba_from_keyframe` | Match wx GraphicsContext transform: translate, rotate, scale, draw feet anchor. | — |
| `_straight_rgba_to_premultiplied_bgra` | Private helper for straight rgba to premultiplied bgra. | — |
| `rgba_has_color` | — | — |

## `smoke_character_edge.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `test_mode_normalization` | — | — |
| `test_outline_adds_ring` | — | — |
| `test_none_passthrough` | — | — |
| `test_clamp_fractional_width` | — | — |
| `test_fractional_dilation_between_steps` | — | — |
| `main` | — | — |

## `smoke_edit_chrome.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `test_chrome_outline_drawn` | — | — |
| `test_chrome_handle_filled_bottom_right` | — | — |
| `test_chrome_rotation_changes_pixels` | — | — |
| `test_chrome_empty_when_offscreen` | — | — |
| `main` | — | — |

## `smoke_layer_runtime.py`

Basic layer stack data model, geometry, compositing, and JSON persistence.

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `_MockImage.__init__` | Constructor for `_MockImage`. | — |
| `_MockImage.GetWidth` | — | — |
| `_MockImage.GetHeight` | — | — |
| `_asset_loader` | Private helper for asset loader. | — |
| `test_binding_migration` | — | — |
| `test_body_vs_head_vs_free` | — | — |
| `test_layer_follow_parent` | — | — |
| `test_head_pose_binding_offset` | — | — |
| `test_mocap_extra_gain` | — | — |
| `test_follow_rotation_character` | — | — |
| `test_follow_rotation_layer_chain` | — | — |
| `test_follow_rotation_legacy_migration` | — | — |
| `test_follow_rotation_both_cancel` | — | — |
| `test_contrast_highlight_colour` | — | — |
| `test_binding_smooth_reduces_jump` | — | — |
| `test_head_spine_ray_follows_tilt` | — | — |
| `test_head_binding_pose_filter` | — | — |
| `test_force_full_layer_follow_bypasses_smoother` | — | — |
| `test_per_layer_smooth_alpha` | — | — |
| `test_gif_transparency_compositing` | — | — |
| `test_classify_layer_asset_kind` | — | — |
| `test_format_layer_row_labels` | — | — |
| `test_low_smooth_alpha_slower_follow` | — | — |
| `test_spine_binding_markers` | — | — |
| `test_unbounded_bind_ray_percent` | — | — |
| `test_body_head_tilt_opposite_splits_pose_roll` | — | — |
| `test_spine_body_opposite_to_head_angles` | — | — |
| `test_global_neck_ratio_does_not_move_layer` | — | — |
| `test_neck_anchor_ratio_full_height_range` | — | — |
| `test_global_bind_percent_does_not_move_layer` | — | — |
| `test_smooth_off_uses_raw_binding_rect` | — | — |
| `test_hit_test_only_selected_layer` | — | — |
| `test_head_bind_rotation_follows_when_smooth_off` | — | — |
| `test_body_bind_follow_rotation` | — | — |
| `test_spine_diagram_follows_tilt` | — | — |
| `test_swing_ease_ends_starts_at_zero` | — | — |
| `test_swing_ease_ends_peak_velocity` | — | — |
| `test_swing_constant_triangle_bounds` | — | — |
| `test_swing_constant_velocity_segment` | — | — |
| `test_swing_zero_amplitude` | — | — |
| `test_swing_motion_active_flag` | — | — |
| `test_swing_serialization_round_trip` | — | — |
| `test_layer_mode_basic_five_migrates` | — | — |
| `test_add_layer_unique_slot_id` | — | — |
| `test_remove_layer_clears_references` | — | — |
| `test_sanitize_layer_references_on_load` | — | — |
| `test_orbit_requires_asset_for_active_motion` | — | — |
| `test_orbit_render_plan_switches_aux_slot` | — | — |
| `test_apply_orbit_offsets_resolved_rect` | — | — |
| `test_basic_layers_persistence_round_trip` | — | — |
| `main` | — | — |

## `smoke_mouse_mocap.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `test_convert_chain` | — | — |
| `test_blink_cycle` | — | — |
| `test_blink_interval_clamp` | — | — |
| `test_center_zone_inside_outside` | — | — |
| `test_with_center_at_preserving_size` | — | — |
| `test_from_norm_edges_top_expand` | — | — |
| `test_center_zone_clamped_to_surface` | — | — |
| `test_tracking_surface_dimensions` | — | — |
| `test_horizontal_out_tilt_mix_motion` | — | — |
| `test_vertical_out_keeps_legacy_y` | — | — |
| `test_horizontal_roll_blend` | — | — |
| `test_gaze_neutral_yields_forward_pose_at_calib_point` | — | — |
| `test_eye_look_follows_mouse_horizontal` | — | — |
| `test_horizontal_tilt_mix_clamp` | — | — |
| `test_center_zone_round_trip_dict` | — | — |
| `test_normalized_clamp` | — | — |
| `test_sample_mouse_without_gui` | sample_global_mouse_normalized requires wx.App; skip if unavailable. | — |
| `test_eye_head_body_horizontal_alignment` | — | — |
| `main` | — | — |

## `smoke_numpy_compositor.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `_solid_rgba` | Private helper for solid rgba. | — |
| `test_zorder_front_layer_over_character` | — | — |
| `test_behind_layer_hidden_by_opaque_character` | — | — |
| `test_transparent_canvas_when_empty` | — | — |
| `test_small_layer_placement_and_alpha` | — | — |
| `test_rotation_changes_corner_coverage` | — | — |
| `test_swing_motion_runs_without_error` | — | — |
| `test_asset_cache_numpy_rgba_png` | — | — |
| `test_asset_cache_numpy_rgba_gif` | — | — |
| `main` | — | — |

## `smoke_output_backends.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `test_background_mode_mapping` | — | — |
| `test_normalize_and_resolve` | — | — |
| `test_tool_recommendations` | — | — |
| `test_labels_present` | — | — |
| `main` | — | — |

## `smoke_transparent_capture.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `test_composite_preserves_color` | — | — |
| `test_compose_character_keeps_color` | — | — |
| `test_premultiplied_bgra_channels` | — | — |
| `test_capture_window_title` | — | — |
| `test_sanitize_transparent_rgb` | — | — |
| `main` | — | — |

## `tha3_assets_prompt.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `ensure_tha3_assets_available` | Return True when THA3 inference assets exist for the selected variant. | — |
| `ensure_tha4_training_assets_available` | Return True when THA4 teacher weights and pose_dataset.pt are present. | — |

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
| `get_demo_root` | Match scripts/launch/run_load_preview_puppeteer.bat: prefer nested enhanced demo over repo-root src. | — |
| `get_demo_src_path` | Returns demo src path. | — |
| `get_packaged_model_yaml` | Returns packaged model yaml. | — |
| `get_packaged_character_png` | Returns packaged character png. | — |
| `resolve_bundled_bai_model_paths` | Repo-relative (forward slashes) yaml + png for bundled bai student model, if present. | — |
| `get_tha3_bundle_root` | Returns tha3 bundle root. | — |
| `get_tha3_source_root` | Returns tha3 source root. | — |
| `get_ezvtuber_models_root` | Returns ezvtuber models root. | — |
| `get_ezvtuber_images_root` | Returns ezvtuber images root. | — |
| `get_ezvtuber_rt_root` | Returns ezvtuber rt root. | — |
| `variant_to_ort_flags` | — | — |
| `variant_to_pytorch_model_name` | — | — |
| `pytorch_model_dir` | — | — |
| `runtime_pytorch_model_dir` | THA3 upstream poser loads from demo cwd: data/models/<variant>. | — |
| `pytorch_models_available` | — | — |
| `ort_model_dir` | — | — |
| `ort_models_available` | — | — |
| `tha3_inference_assets_available` | — | — |
| `tha3_download_bat_path` | — | — |
| `portable_path_suffix` | Extract repo-relative tail from a foreign absolute path (e.g. E:\other\data\...). | — |
| `_resolve_under_repo` | Private helper for resolve under repo. | — |
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
| `_capture_window_err_record` | Private helper for capture window err record. | — |
| `_raise_overlay_topmost` | Private helper for raise overlay topmost. | — |
| `_init_win32_prototypes` | Private helper for init win32 prototypes. | — |
| `_straight_rgba_to_premultiplied_bgra` | Private helper for straight rgba to premultiplied bgra. | — |
| `_resolve_app_icon_path` | Walk up from this module looking for the bundled app icon (same artwork | — |
| `_build_border_ring_rgba` | Opaque ring of `thickness` px around a fully transparent interior. The | — |
| `_DesktopOverlayWindow.__init__` | Constructor for `_DesktopOverlayWindow`. | — |
| `_DesktopOverlayWindow._register_class` | Private helper for register class. | — |
| `_DesktopOverlayWindow._window_proc` | Private helper for window proc. | — |
| `_DesktopOverlayWindow._lparam_to_xy` | Private helper for lparam to xy. | — |
| `_DesktopOverlayWindow._handle_message` | Returns (handled, lresult). When handled is False the caller falls | — |
| `_DesktopOverlayWindow._on_left_down` | Private helper for on left down. | — |
| `_DesktopOverlayWindow._on_mouse_move` | Private helper for on mouse move. | — |
| `_DesktopOverlayWindow._on_left_up` | Private helper for on left up. | — |
| `_DesktopOverlayWindow._on_key_down` | Private helper for on key down. | — |
| `_DesktopOverlayWindow._notify_position_changed` | Private helper for notify position changed. | — |
| `_DesktopOverlayWindow._create_window` | Private helper for create window. | — |
| `_DesktopOverlayWindow._apply_window_icon` | Private helper for apply window icon. | — |
| `_DesktopOverlayWindow._create_dib` | Private helper for create dib. | — |
| `_DesktopOverlayWindow._release_dib` | Private helper for release dib. | — |
| `_DesktopOverlayWindow.is_valid` | — | — |
| `_DesktopOverlayWindow.set_geometry` | Updates geometry. | — |
| `_DesktopOverlayWindow.update_rgba` | — | — |
| `_DesktopOverlayWindow.show` | — | — |
| `_DesktopOverlayWindow.hide` | — | — |
| `_DesktopOverlayWindow.destroy` | — | — |
| `TransparentCaptureWindow.__init__` | Constructor for `TransparentCaptureWindow`. | — |
| `TransparentCaptureWindow._on_overlay_position_changed` | Private helper for on overlay position changed. | — |
| `TransparentCaptureWindow._sync_visible_geometry` | Private helper for sync visible geometry. | — |
| `TransparentCaptureWindow._sync_border_geometry` | Private helper for sync border geometry. | — |
| `TransparentCaptureWindow.hwnd` | — | — |
| `TransparentCaptureWindow.is_valid` | — | — |
| `TransparentCaptureWindow.owns_foreground_window` | True when the OS foreground window is this ULW (the on-screen output | — |
| `TransparentCaptureWindow.get_rect` | Returns rect. | — |
| `TransparentCaptureWindow.set_position` | Updates position. | — |
| `TransparentCaptureWindow.show` | — | — |
| `TransparentCaptureWindow.hide` | — | — |
| `TransparentCaptureWindow.destroy` | — | — |
| `TransparentCaptureWindow.update_frame_rgba` | — | — |

## `ui_dialog_guard.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `_dialog_key` | Private helper for dialog key. | — |
| `show_rate_limited_message` | Show a modal message at most `max_per_session` times per key and `min_interval_sec` apart. | — |
| `reset_dialog_guard_for_tests` | — | — |

## `upstream_assets.py`

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `tha4_teacher_assets_available` | — | — |
| `tha4_training_assets_available` | — | — |
| `tha3_assets_installed` | — | — |
| `tha3_models_root` | — | — |
| `run_upstream_download` | — | — |
| `tha3_missing_message` | — | — |
| `tha4_training_missing_message` | — | — |

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
| `_init_win32_prototypes` | Private helper for init win32 prototypes. | — |
| `_as_hwnd` | Private helper for as hwnd. | — |
| `_as_hdc` | Private helper for as hdc. | — |
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
| `get_mediapipe_module` | Returns mediapipe module. | — |
| `_perf_record` | Private helper for perf record. | — |
| `_startup_record` | Private helper for startup record. | — |
| `_err_record` | Private helper for err record. | — |
| `_install_debug_excepthook` | Private helper for install debug excepthook. | — |
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
| `get_app_icon_bundle` | Cached wx.IconBundle built from the bundled .ico (same artwork as the | — |
| `apply_app_icon` | Apply the shared exe logo to a top-level window's taskbar label. Safe to | — |
| `set_windows_app_user_model_id` | Give the process its own Windows taskbar identity so the taskbar uses our | — |
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
| `ControlsFrame.on_show` | wx event handler for show. | — |
| `ControlsFrame.on_first_idle` | wx event handler for first idle. | — |
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
| `create_face_landmarker` | Create FaceLandmarker; prefer GPU delegate with CPU fallback. | — |

### MainFrame — UI event handlers

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame.calibrate_head_orientation_quick` | Compact launcher: path A head orientation only. | Compact: Calibrate Head Orientation |
| `MainFrame.calibrate_neutral_clicked` | Postprocess button: path A head orientation only. | Calibrate Head Orientation (postprocess) |
| `MainFrame.calibrate_scale_clicked` | Manual output dynamic enhancement calibration (path B neutral/size). | Compact: Output Dynamic Enhancement Calibration; Output Dynamic Enhancement Calibration (postprocess) |
| `MainFrame.load_last_model` | — | Load Last THA4 Student Model |
| `MainFrame.load_last_tha3_character_png` | — | Load Last THA3 PNG |
| `MainFrame.load_model` | — | Load THA4 Student Model |
| `MainFrame.load_tha3_character_png` | — | Load Other THA3 PNG |
| `MainFrame.on_character_edge_setting_changed` | wx event handler for character edge setting changed. | character_edge_mode_choice; character_edge_width_spin; character_edge_colour_picker |
| `MainFrame.on_column_splitter_changed` | wx event handler for column splitter changed. | Animation column splitter; Main column splitter; Right sidebar splitter |
| `MainFrame.on_display_transform_control_changed` | Persist and apply auto pan/scale, calibration toggles, mirror, slider values. | Enable Auto Pan & Scale; Tilt Opposite to Head; Auto Calibrate Forward Gaze; Forward Gaze Interval (seconds); Enable Auto Output Dynamic Enhancement Calibration; Enhancement Calibration Interval (seconds) |
| `MainFrame.on_dynamic_output_panel_size` | wx event handler for dynamic output panel size. | Output preview panel (resize) |
| `MainFrame.on_erase_background` | wx event handler for erase background. | Output window image panel (drag pan); Webcam popup preview panel; Scale curve preview panel; Source character image panel; Webcam preview (double-click opens popup) |
| `MainFrame.on_hover_help_timer` | wx event handler for hover help timer. | Hover help timer (controls window) |
| `MainFrame.on_layer_blend_changed` | Enable/disable compositing basic layers into previews and output. | Enable Layer Blending |
| `MainFrame.on_layer_force_full_follow_changed` | wx event handler for layer force full follow changed. | Force Layer 100% Follow |
| `MainFrame.on_mocap_input_mode_changed` | wx event handler for mocap input mode changed. | mocap_input_mode_choice |
| `MainFrame.on_model_input_column_size` | wx event handler for model input column size. | model_input_column |
| `MainFrame.on_mouse_auto_calibration_checkbox_changed` | wx event handler for mouse auto calibration checkbox changed. | Mouse Periodic Auto-Calibration |
| `MainFrame.on_mouse_auto_calibration_interval_changed` | wx event handler for mouse auto calibration interval changed. | mouse_auto_calibration_interval_seconds_ctrl |
| `MainFrame.on_mouth_infer_cap_changed` | Set base GPU infer cap (Hz); persisted to ui state. | GPU Infer Cap (Hz) |
| `MainFrame.on_open_basic_layer_window_clicked` | wx event handler for open basic layer window clicked. | Open Layer Editor |
| `MainFrame.on_output_background_changed` | wx event handler for output background changed. | Background color picker |
| `MainFrame.on_output_background_image_browse` | wx event handler for output background image browse. | Browse Background Image |
| `MainFrame.on_output_background_mode_changed` | wx event handler for output background mode changed. | Background mode (solid / image / transparent capture) |
| `MainFrame.on_output_frame_interpolation_changed` | Set pose interpolation multiplier; adjusts effective infer cap. | Frame Interpolation multiplier |
| `MainFrame.on_pick_window_capture_clicked` | wx event handler for pick window capture clicked. | pick_window_capture_button |
| `MainFrame.on_postprocess_scroll_size` | wx event handler for postprocess scroll size. | Postprocess scroll area (resize) |
| `MainFrame.on_refresh_video_sources_clicked` | wx event handler for refresh video sources clicked. | Refresh video sources |
| `MainFrame.on_smooth_affine_30hz_changed` | Toggle smooth 30 Hz cached-affine display vs infer-rate-only display. | Smooth Motion 30Hz |
| `MainFrame.on_source_image_panel_show` | wx event handler for source image panel show. | Source character image panel |
| `MainFrame.on_source_image_panel_size` | wx event handler for source image panel size. | Source character image panel |
| `MainFrame.on_tha3_model_variant_changed` | wx event handler for tha3 model variant changed. | THA3 Model Variant |
| `MainFrame.on_video_source_choice_changed` | wx event handler for video source choice changed. | Video source dropdown |
| `MainFrame.on_webcam_capture_panel_show` | wx event handler for webcam capture panel show. | Webcam preview (double-click opens popup) |
| `MainFrame.on_webcam_capture_panel_size` | wx event handler for webcam capture panel size. | Webcam preview (double-click opens popup) |
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
| `MainFrame.calibrate_mouse_dynamic_enhancement` | Calibrate neutral enhancement; move center-zone center to mouse without resizing the zone. | — |
| `MainFrame.refresh_auto_transform_status` | — | — |
| `MainFrame.refresh_scale_curve_status` | — | — |
| `MainFrame.update_neutral_face_direction` | — | — |
| `MainFrame.update_neutral_output_enhancement` | Refresh scale baseline, horizontal center, and head-roll neutral; keep vertical center to avoid upward drift. | — |

### MainFrame — Display, output, and composition

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame._get_compose_signature` | Private helper for get compose signature. | — |
| `MainFrame._invalidate_render_caches` | Private helper for invalidate render caches. | — |
| `MainFrame._note_display_fps_tick` | Private helper for note display fps tick. | — |
| `MainFrame._present_smooth_output_frame` | Private helper for present smooth output frame. | — |
| `MainFrame.apply_capture_output_frame_state` | — | — |
| `MainFrame.apply_output_frame_state` | — | — |
| `MainFrame.compose_edit_chrome_rgba` | Transparent RGBA overlay carrying the selection box + resize handle | — |
| `MainFrame.compose_output_stack_rgba` | wx-free full output composite: enhanced character keyframe + layer | — |
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
| `MainFrame.is_smooth_display_priority` | Prefer unified infer throttling (any pose change + effective cap). | — |
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

### MainFrame — Persistence and UI state

| Function | Purpose | UI control(s) |
| --- | --- | --- |
| `MainFrame.apply_persistent_mocap_input_mode` | — | — |
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
| `MainFrame.apply_controls_window_size_policy` | Apply min height cap once; never touch width max or client size during active drag-resize. | — |
| `MainFrame.apply_splitter_sash` | — | — |
| `MainFrame.handle_controls_frame_geometry_changed` | — | — |
| `MainFrame.handle_controls_frame_resized` | — | — |
| `MainFrame.on_compact_geometry_changed` | wx event handler for compact geometry changed. | — |
| `MainFrame.refresh_right_sidebar_scrolling` | — | — |
| `MainFrame.schedule_dynamic_output_layout_refresh` | Debounced/async scheduler for dynamic output layout refresh. | — |
| `MainFrame.schedule_postprocess_layout_refresh` | Debounced/async scheduler for postprocess layout refresh. | — |
| `MainFrame.schedule_refresh_controls_scrolling` | Synchronous controls layout refresh (no debounced CallLater). | — |
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
| `MainFrame._apply_character_edge_postprocess` | Private helper for apply character edge postprocess. | — |
| `MainFrame._apply_character_edge_postprocess_rgba` | Private helper for apply character edge postprocess rgba. | — |
| `MainFrame._apply_layer_edit_motion` | Private helper for apply layer edit motion. | — |
| `MainFrame._apply_mouse_only_controls_visibility` | Private helper for apply mouse only controls visibility. | — |
| `MainFrame._apply_persisted_controls_layout` | Private helper for apply persisted controls layout. | — |
| `MainFrame._apply_video_source_choices` | Private helper for apply video source choices. | — |
| `MainFrame._async_premultiply_and_deliver` | Private helper for async premultiply and deliver. | — |
| `MainFrame._auxiliary_preview_min_interval_ns` | Private helper for auxiliary preview min interval ns. | — |
| `MainFrame._basic_layer_window_visible` | Private helper for basic layer window visible. | — |
| `MainFrame._begin_layer_edit` | Private helper for begin layer edit. | — |
| `MainFrame._blit_output_background_to_dc` | Private helper for blit output background to dc. | — |
| `MainFrame._build_ulw_background_plate` | Private helper for build ulw background plate. | — |
| `MainFrame._cached_affine_compose_signature` | Private helper for cached affine compose signature. | — |
| `MainFrame._cached_affine_visual_unchanged` | Private helper for cached affine visual unchanged. | — |
| `MainFrame._can_present_character_fast` | Private helper for can present character fast. | — |
| `MainFrame._capture_splitter_ratios` | Private helper for capture splitter ratios. | — |
| `MainFrame._clamp_controls_window_client_size_preserve_origin` | Shrink an oversized controls window without jumping the client top-left corner. | — |
| `MainFrame._collect_pose_binding_fields` | Private helper for collect pose binding fields. | — |
| `MainFrame._collect_splitter_layout_fields` | Private helper for collect splitter layout fields. | — |
| `MainFrame._compose_character_bitmap_from_keyframe` | Private helper for compose character bitmap from keyframe. | — |
| `MainFrame._compose_character_rgba_from_keyframe` | Private helper for compose character rgba from keyframe. | — |
| `MainFrame._compose_present_rgba` | Single wx-free composite shared by on-screen present and transparent | — |
| `MainFrame._compose_ulw_background_rgba` | Opaque background plate composited UNDER the character for the unified | — |
| `MainFrame._controls_splitter_layout_readable` | Private helper for controls splitter layout readable. | — |
| `MainFrame._deliver_capture_premultiplied` | Private helper for deliver capture premultiplied. | — |
| `MainFrame._draw_banner_on_result_bitmap` | Private helper for draw banner on result bitmap. | — |
| `MainFrame._edge_postprocess_background_rgb` | Fringe bake colour: black for transparent/capture paths, panel paint otherwise. | — |
| `MainFrame._end_layer_edit` | Private helper for end layer edit. | — |
| `MainFrame._ensure_tha3_assets_on_startup` | Private helper for ensure tha3 assets on startup. | — |
| `MainFrame._ensure_webcam_capture_bitmap_size` | Private helper for ensure webcam capture bitmap size. | — |
| `MainFrame._ensure_window_capture_worker` | Start the background window-capture grabber if it is not running. | — |
| `MainFrame._extract_control_label_text` | Private helper for extract control label text. | — |
| `MainFrame._fallback_to_mouse_mocap_once` | Private helper for fallback to mouse mocap once. | — |
| `MainFrame._finish_mediapipe_detect` | Private helper for finish mediapipe detect. | — |
| `MainFrame._get_antialias_factor` | Private helper for get antialias factor. | — |
| `MainFrame._get_basic_layer_window` | Private helper for get basic layer window. | — |
| `MainFrame._get_cached_background_rgba` | Private helper for get cached background rgba. | — |
| `MainFrame._hit_test_layer_edit` | Private helper for hit test layer edit. | — |
| `MainFrame._hit_test_layer_slot` | Private helper for hit test layer slot. | — |
| `MainFrame._init_video_source_choices_with_window` | Private helper for init video source choices with window. | — |
| `MainFrame._invalidate_capture_foreground_cache` | Private helper for invalidate capture foreground cache. | — |
| `MainFrame._invalidate_source_preview_cache` | Private helper for invalidate source preview cache. | — |
| `MainFrame._is_layer_editing_focus_window` | Private helper for is layer editing focus window. | — |
| `MainFrame._keyframe_cache_valid` | Private helper for keyframe cache valid. | — |
| `MainFrame._legacy_body_bind_lean_gain` | Private helper for legacy body bind lean gain. | — |
| `MainFrame._load_mouse_mocap_settings_from_persistent` | Private helper for load mouse mocap settings from persistent. | — |
| `MainFrame._make_binding_context` | Private helper for make binding context. | — |
| `MainFrame._maybe_clear_layer_selection_after_deactivate` | Private helper for maybe clear layer selection after deactivate. | — |
| `MainFrame._maybe_schedule_transparent_capture_update` | Private helper for maybe schedule transparent capture update. | — |
| `MainFrame._mediapipe_detect_worker` | Private helper for mediapipe detect worker. | — |
| `MainFrame._needs_obs_alpha_sanitize` | Private helper for needs obs alpha sanitize. | — |
| `MainFrame._next_mediapipe_video_timestamp_ms` | Private helper for next mediapipe video timestamp ms. | — |
| `MainFrame._note_cached_affine_present_time` | Private helper for note cached affine present time. | — |
| `MainFrame._note_capture_present_time` | Private helper for note capture present time. | — |
| `MainFrame._note_inference_fps_tick` | Private helper for note inference fps tick. | — |
| `MainFrame._note_input_fps_tick` | Private helper for note input fps tick. | — |
| `MainFrame._note_pose_present_time` | Private helper for note pose present time. | — |
| `MainFrame._notify_output_panel_refresh` | Private helper for notify output panel refresh. | — |
| `MainFrame._nudge_animation_splitter_layout` | Private helper for nudge animation splitter layout. | — |
| `MainFrame._overlay_canvas_size` | Private helper for overlay canvas size. | — |
| `MainFrame._overlay_deactivated` | Private helper for overlay deactivated. | — |
| `MainFrame._overlay_edit_begin` | ULW WNDPROC router: try to start a layer edit at canvas-pixel (x,y). | — |
| `MainFrame._overlay_edit_end` | Private helper for overlay edit end. | — |
| `MainFrame._overlay_edit_motion` | Private helper for overlay edit motion. | — |
| `MainFrame._overlay_key_nudge` | Private helper for overlay key nudge. | — |
| `MainFrame._panel_to_layer_delta` | Private helper for panel to layer delta. | — |
| `MainFrame._post_show_controls_setup` | Private helper for post show controls setup. | — |
| `MainFrame._present_character_bitmap` | Private helper for present character bitmap. | — |
| `MainFrame._push_transparent_capture_foreground` | Private helper for push transparent capture foreground. | — |
| `MainFrame._push_transparent_capture_from_cache` | Private helper for push transparent capture from cache. | — |
| `MainFrame._record_rate_in_rolling_window` | Private helper for record rate in rolling window. | — |
| `MainFrame._rect_intersection_area` | Private helper for rect intersection area. | — |
| `MainFrame._refresh_fps_display` | Private helper for refresh fps display. | — |
| `MainFrame._refresh_pose_after_tilt_mapping_changed` | Private helper for refresh pose after tilt mapping changed. | — |
| `MainFrame._refresh_transparent_capture_frame` | Private helper for refresh transparent capture frame. | — |
| `MainFrame._relayout_animation_splitter_panes` | Private helper for relayout animation splitter panes. | — |
| `MainFrame._reset_mediapipe_video_timestamp` | Private helper for reset mediapipe video timestamp. | — |
| `MainFrame._resolve_layout_splitter_ratio` | Private helper for resolve layout splitter ratio. | — |
| `MainFrame._resolve_mocap_pose_for_render` | Private helper for resolve mocap pose for render. | — |
| `MainFrame._resolve_persisted_splitter_sash` | Private helper for resolve persisted splitter sash. | — |
| `MainFrame._resolve_persisted_splitter_sash_ratio` | Private helper for resolve persisted splitter sash ratio. | — |
| `MainFrame._retry_controls_column_layout_once` | Private helper for retry controls column layout once. | — |
| `MainFrame._run_controls_frame_layout_refresh` | Private helper for run controls frame layout refresh. | — |
| `MainFrame._run_controls_window_bounds_refresh` | Private helper for run controls window bounds refresh. | — |
| `MainFrame._run_dynamic_output_layout_refresh` | Private helper for run dynamic output layout refresh. | — |
| `MainFrame._run_model_input_column_layout_refresh` | Private helper for run model input column layout refresh. | — |
| `MainFrame._run_postprocess_layout_refresh` | Private helper for run postprocess layout refresh. | — |
| `MainFrame._run_transparent_capture_update` | Private helper for run transparent capture update. | — |
| `MainFrame._safe_checkbox_value` | Private helper for safe checkbox value. | — |
| `MainFrame._sanitize_result_bitmap_once` | Private helper for sanitize result bitmap once. | — |
| `MainFrame._schedule_mediapipe_detect` | Queue a frame for off-thread MediaPipe detection (latest-wins, single worker). | — |
| `MainFrame._seed_live_splitter_ratios_from_persistent` | Private helper for seed live splitter ratios from persistent. | — |
| `MainFrame._select_layer_slot` | Private helper for select layer slot. | — |
| `MainFrame._should_clear_layer_selection_for_window` | Private helper for should clear layer selection for window. | — |
| `MainFrame._should_filter_head_binding_pose` | Pose low-pass only when a bound layer uses smooth follow or extra mocap. | — |
| `MainFrame._source_preview_target_size` | Private helper for source preview target size. | — |
| `MainFrame._splitter_extent` | Private helper for splitter extent. | — |
| `MainFrame._splitter_sash_from_ratio` | Private helper for splitter sash from ratio. | — |
| `MainFrame._stop_call_later` | Private helper for stop call later. | — |
| `MainFrame._sync_controls_splitter_geometry` | Flush wx layout so splitter sash / pane sizes match the shown frame. | — |
| `MainFrame._sync_layer_blend_state` | Private helper for sync layer blend state. | — |
| `MainFrame._sync_splitter_ratio_fields_to_persistent_state` | Private helper for sync splitter ratio fields to persistent state. | — |
| `MainFrame._sync_transparent_capture_output_window_impl` | Private helper for sync transparent capture output window impl. | — |
| `MainFrame._update_keyframe_cache` | Private helper for update keyframe cache. | — |
| `MainFrame._update_mouse_dynamic_enhancement_motion` | Private helper for update mouse dynamic enhancement motion. | — |
| `MainFrame._webcam_preview_target_size` | Private helper for webcam preview target size. | — |
| `MainFrame._window_capture_worker` | Continuously grab the target window off the UI thread (latest-wins). | — |
| `MainFrame._wrap_static_texts_under_window` | Private helper for wrap static texts under window. | — |
| `MainFrame._wrap_status_message_lines` | Private helper for wrap status message lines. | — |
| `MainFrame._wx_bitmap_to_rgba_via_png` | PNG round-trip preserves colour on Windows MemoryDC 32bpp bitmaps. | — |
| `MainFrame._wx_control_alive` | Private helper for wx control alive. | — |
| `MainFrame._wx_image_is_greyscale` | Private helper for wx image is greyscale. | — |
| `MainFrame.adapt_main_window_to_controls` | — | — |
| `MainFrame.adaptive_right_sidebar_capture_min_height` | Allow more vertical drag on short (portrait) windows while keeping a usable preview. | — |
| `MainFrame.apply_bundled_default_model_paths_if_missing` | When no saved last-model memory, default Load Last to bundled bai student yaml + png. | — |
| `MainFrame.apply_controls_layout_from_persistent` | Restore splitters: visual B\|C\|D equal width via nested splitters (not 3 horizontal splitters). | — |
| `MainFrame.apply_frame_geometry_from_storage` | — | — |
| `MainFrame.apply_invert_tilt_mapping_to_pose` | — | — |
| `MainFrame.apply_layer_blend_visibility` | — | — |
| `MainFrame.apply_layer_edit_at` | Panel-agnostic edit motion in output-canvas pixel space (P6 router). | — |
| `MainFrame.apply_model_input_column_layout` | One-shot layout for model input column after splitter geometry is known. | — |
| `MainFrame.apply_mouse_mocap_controls_from_persistent` | — | — |
| `MainFrame.apply_mouth_persistent_state_to_args` | — | — |
| `MainFrame.apply_output_background_hex` | — | — |
| `MainFrame.apply_output_background_mode` | — | — |
| `MainFrame.autoconnect_video_source_on_startup` | Connect saved window/camera without requiring a manual dropdown click. | — |
| `MainFrame.background_hex_from_legacy_selection` | — | — |
| `MainFrame.begin_layer_edit_at` | Panel-agnostic edit begin in output-canvas pixel space (for the | — |
| `MainFrame.bgr_frame_to_preview_bitmap` | Scale frame to fit inside preview box; letterbox with black when aspect differs. | — |
| `MainFrame.bind_animation_area_mousewheel` | — | — |
| `MainFrame.bind_mousewheel_scroll_recursive` | — | — |
| `MainFrame.bring_controls_frame_to_front` | — | — |
| `MainFrame.build_camera_source_label` | — | — |
| `MainFrame.build_output_background_rgba` | — | — |
| `MainFrame.clamp_client_rect_to_visible_screen` | — | — |
| `MainFrame.clamp_splitter_sash` | — | — |
| `MainFrame.clean_wx_image_transparent_rgb` | — | — |
| `MainFrame.clear_layer_selection` | — | — |
| `MainFrame.clear_result_image_bitmap` | Hard-reset output buffer. MemoryDC Clear() does not zero alpha on Windows. | — |
| `MainFrame.collect_display_transform_settings` | — | — |
| `MainFrame.collect_persistent_ui_state` | — | — |
| `MainFrame.collect_window_client_rect` | — | — |
| `MainFrame.composite_rgba_over_background` | Source-over composite; alpha=0 foreground pixels leave background unchanged. | — |
| `MainFrame.compute_default_animation_splitter_sash` | — | — |
| `MainFrame.compute_default_main_splitter_sash` | — | — |
| `MainFrame.compute_default_right_sidebar_splitter_sash` | — | — |
| `MainFrame.compute_equal_halves_sash` | Animation splitter (B\|C each ~1/3 total width) or right sidebar (preview\|post): 50/50. | — |
| `MainFrame.compute_equal_thirds_main_sash` | Main splitter: left (B+C) = 2/3, right (D preview+post) = 1/3 of total width. | — |
| `MainFrame.compute_right_sidebar_splitter_sash_from_ratio` | — | — |
| `MainFrame.compute_scale_response` | — | — |
| `MainFrame.compute_target_scale` | — | — |
| `MainFrame.connect_default_video_source` | — | — |
| `MainFrame.convert_to_100` | — | — |
| `MainFrame.count_controls_recursive` | — | — |
| `MainFrame.create_model_input_video_source_controls` | Video source picker lives in Model Input column (mocap input for pose params). | — |
| `MainFrame.create_preview_calibration_controls` | Builds UI widget(s) for preview calibration controls. | — |
| `MainFrame.create_transparent_composition_bitmap` | Character-only buffer for layer post-process (no output background baked in). | — |
| `MainFrame.default_capture_output_frame_rect_beside_output` | — | — |
| `MainFrame.default_output_frame_rect_beside_controls` | — | — |
| `MainFrame.describe_hover_help_for_control` | — | — |
| `MainFrame.destroy_transparent_capture_window` | — | — |
| `MainFrame.end_layer_edit_external` | Panel-agnostic edit end (P6 router). | — |
| `MainFrame.ensure_application_windows_visible` | — | — |
| `MainFrame.ensure_basic_layer_window_on_screen` | — | — |
| `MainFrame.ensure_face_landmarker` | — | — |
| `MainFrame.ensure_output_frame` | — | — |
| `MainFrame.ensure_result_bitmap_size` | — | — |
| `MainFrame.enumerate_camera_sources` | — | — |
| `MainFrame.extract_face_screen_motion` | — | — |
| `MainFrame.fill_bitmap_solid` | — | — |
| `MainFrame.finalize_controls_column_layout` | — | — |
| `MainFrame.finalize_startup_autofit` | — | — |
| `MainFrame.find_nearest_scrolled_window` | — | — |
| `MainFrame.format_window_capture_label` | — | — |
| `MainFrame.get_auxiliary_preview_cap_hz` | Scale-curve preview + spine diagram: half infer cap to skip redundant repaints. | — |
| `MainFrame.get_body_bind_pos_follow_gain` | Returns body bind pos follow gain. | — |
| `MainFrame.get_body_bind_roll_follow_gain` | Returns body bind roll follow gain. | — |
| `MainFrame.get_bundled_transparent_background_path` | Returns bundled transparent background path. | — |
| `MainFrame.get_character_edge_colour` | Returns character edge colour. | — |
| `MainFrame.get_character_edge_mode` | Returns character edge mode. | — |
| `MainFrame.get_character_edge_width` | Returns character edge width. | — |
| `MainFrame.get_controls_height_bounds` | Returns controls height bounds. | — |
| `MainFrame.get_controls_min_client_size` | Returns controls min client size. | — |
| `MainFrame.get_controls_window` | Returns controls window. | — |
| `MainFrame.get_default_character_models_dir` | Returns default character models dir. | — |
| `MainFrame.get_default_pose_list` | Returns default pose list. | — |
| `MainFrame.get_directshow_camera_device_names` | Returns directshow camera device names. | — |
| `MainFrame.get_display_present_cap_hz` | Returns display present cap hz. | — |
| `MainFrame.get_display_work_area_for_window` | Returns display work area for window. | — |
| `MainFrame.get_effective_infer_cap_hz` | Returns effective infer cap hz. | — |
| `MainFrame.get_last_window_capture_title` | Returns last window capture title. | — |
| `MainFrame.get_layer_selection_highlight_colour` | Returns layer selection highlight colour. | — |
| `MainFrame.get_locked_output_client_size` | Returns locked output client size. | — |
| `MainFrame.get_model_input_column_wrap_width` | Returns model input column wrap width. | — |
| `MainFrame.get_mouse_mocap_status_message` | Returns mouse mocap status message. | — |
| `MainFrame.get_mouth_infer_cap_hz` | Returns mouth infer cap hz. | — |
| `MainFrame.get_mouth_pose_indices` | Returns mouth pose indices. | — |
| `MainFrame.get_output_canvas_size` | Returns output canvas size. | — |
| `MainFrame.get_output_capture_backend` | Resolve the active output delivery backend (how the transparent | — |
| `MainFrame.get_output_frame_interpolation_multiplier` | Returns output frame interpolation multiplier. | — |
| `MainFrame.get_output_frame_paint_colour` | Returns output frame paint colour. | — |
| `MainFrame.get_saved_client_rect` | Returns saved client rect. | — |
| `MainFrame.get_saved_window_capture` | Returns saved window capture. | — |
| `MainFrame.get_scale_curve_current_delta` | Returns scale curve current delta. | — |
| `MainFrame.get_scale_curve_domain` | Returns scale curve domain. | — |
| `MainFrame.get_scale_curve_neutral_face_size` | Returns scale curve neutral face size. | — |
| `MainFrame.get_scale_curve_samples` | Returns scale curve samples. | — |
| `MainFrame.get_spine_body_bind_ray_percent` | Returns spine body bind ray percent. | — |
| `MainFrame.get_spine_head_bind_ray_percent` | Returns spine head bind ray percent. | — |
| `MainFrame.get_spine_neck_anchor_ratio` | Returns spine neck anchor ratio. | — |
| `MainFrame.get_ui_state_file_path` | Returns ui state file path. | — |
| `MainFrame.get_windows_camera_device_names` | Returns windows camera device names. | — |
| `MainFrame.hide_basic_layer_window` | — | — |
| `MainFrame.hide_hover_help_popup` | — | — |
| `MainFrame.initialize_adjustable_columns` | — | — |
| `MainFrame.initialize_headless_control_state` | — | — |
| `MainFrame.initialize_output_bitmap` | — | — |
| `MainFrame.invalidate_output_background_image_cache` | — | — |
| `MainFrame.is_acceptable_capture_frame` | — | — |
| `MainFrame.is_body_tilt_opposite_to_head_enabled` | Body segment tilt opposite to head segment (model body_z vs neck_z, spine lower vs upper). | — |
| `MainFrame.is_capture_preview_visible` | — | — |
| `MainFrame.is_capture_source_active` | — | — |
| `MainFrame.is_frame_interpolation_active` | — | — |
| `MainFrame.is_hover_help_enabled` | — | — |
| `MainFrame.is_invert_tilt_mapping_enabled` | — | — |
| `MainFrame.is_layer_blend_enabled` | — | — |
| `MainFrame.is_layer_force_full_follow_enabled` | — | — |
| `MainFrame.is_mouse_audio_mocap_mode` | — | — |
| `MainFrame.is_plausible_camera_frame` | — | — |
| `MainFrame.is_smooth_affine_30hz_enabled` | — | — |
| `MainFrame.is_transparent_capture_background_enabled` | — | — |
| `MainFrame.is_ulw_output_enabled` | The layered ULW (easyvtuberstudio_output) is the single output window | — |
| `MainFrame.is_webcam_popup_visible` | — | — |
| `MainFrame.is_window_rect_mostly_visible` | — | — |
| `MainFrame.maybe_apply_periodic_direction_calibration` | — | — |
| `MainFrame.maybe_apply_periodic_mouse_calibration` | — | — |
| `MainFrame.maybe_apply_periodic_scale_calibration` | — | — |
| `MainFrame.needs_alpha_result_bitmap` | — | — |
| `MainFrame.normalize_background_hex` | — | — |
| `MainFrame.normalize_bgr_frame` | — | — |
| `MainFrame.nudge_selected_layer` | Panel-agnostic arrow-key nudge of the selected layer (shared by the | — |
| `MainFrame.on_animation_panel_mousewheel_logged` | wx event handler for animation panel mousewheel logged. | — |
| `MainFrame.on_basic_layer_window_closed` | Layer blend toggled off — hide editor; do not destroy the frame. | — |
| `MainFrame.on_controls_first_idle` | wx event handler for controls first idle. | — |
| `MainFrame.on_controls_frame_moved` | wx event handler for controls frame moved. | — |
| `MainFrame.on_controls_frame_shown` | wx event handler for controls frame shown. | — |
| `MainFrame.on_layer_char_hook` | wx event handler for layer char hook. | — |
| `MainFrame.on_layer_state_changed` | wx event handler for layer state changed. | — |
| `MainFrame.on_mouse_blink_interval_changed` | wx event handler for mouse blink interval changed. | — |
| `MainFrame.on_mouse_center_zone_changed` | wx event handler for mouse center zone changed. | — |
| `MainFrame.on_mouse_horizontal_tilt_mix_changed` | wx event handler for mouse horizontal tilt mix changed. | — |
| `MainFrame.on_mousewheel_scroll` | wx event handler for mousewheel scroll. | — |
| `MainFrame.on_output_panel_left_down` | wx event handler for output panel left down. | — |
| `MainFrame.on_output_panel_left_up` | wx event handler for output panel left up. | — |
| `MainFrame.on_output_panel_motion` | wx event handler for output panel motion. | — |
| `MainFrame.on_ui_anim_timer` | Drive continuously-refreshing animated UI (controls + layer window) at a | — |
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
| `MainFrame.refresh_basic_layer_window_if_visible` | — | — |
| `MainFrame.refresh_controls_scrolling` | — | — |
| `MainFrame.refresh_dynamic_output_scroll` | — | — |
| `MainFrame.refresh_dynamic_output_status_layout` | — | — |
| `MainFrame.refresh_layer_blend_status` | — | — |
| `MainFrame.refresh_mocap_input_mode_ui` | — | — |
| `MainFrame.refresh_model_input_column_scroll` | — | — |
| `MainFrame.refresh_model_input_column_wrapped_texts` | — | — |
| `MainFrame.refresh_output_frame_chrome` | — | — |
| `MainFrame.refresh_postprocess_scroll_layout` | — | — |
| `MainFrame.refresh_postprocess_static_text_wrap` | — | — |
| `MainFrame.refresh_preview_placeholders` | — | — |
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
| `MainFrame.resolve_tha3_character_png_path` | — | — |
| `MainFrame.restore_compact_frame_geometry` | — | — |
| `MainFrame.restore_controls_frame_geometry` | — | — |
| `MainFrame.scale_image_cover` | — | — |
| `MainFrame.schedule_controls_frame_layout_refresh` | Debounced/async scheduler for controls frame layout refresh. | — |
| `MainFrame.schedule_controls_window_bounds_refresh` | Debounced/async scheduler for controls window bounds refresh. | — |
| `MainFrame.schedule_model_input_column_layout_refresh` | Debounced/async scheduler for model input column layout refresh. | — |
| `MainFrame.set_body_bind_pos_follow_gain` | Updates body bind pos follow gain. | — |
| `MainFrame.set_body_bind_roll_follow_gain` | Updates body bind roll follow gain. | — |
| `MainFrame.set_mocap_input_mode` | Updates mocap input mode. | — |
| `MainFrame.set_neutral_face_screen_motion` | Updates neutral face screen motion. | — |
| `MainFrame.set_neutral_head_roll_deg` | Updates neutral head roll deg. | — |
| `MainFrame.set_spine_body_bind_ray_percent` | Updates spine body bind ray percent. | — |
| `MainFrame.set_spine_head_bind_ray_percent` | Updates spine head bind ray percent. | — |
| `MainFrame.set_spine_neck_anchor_ratio` | Updates spine neck anchor ratio. | — |
| `MainFrame.set_video_capture_camera` | Updates video capture camera. | — |
| `MainFrame.set_video_capture_file` | Updates video capture file. | — |
| `MainFrame.set_video_capture_window` | Updates video capture window. | — |
| `MainFrame.setup_hover_help_bindings` | — | — |
| `MainFrame.should_draw_result_bitmap_with_alpha` | — | — |
| `MainFrame.should_infer_pose` | — | — |
| `MainFrame.should_mirror_capture_preview` | — | — |
| `MainFrame.should_process_mediapipe` | — | — |
| `MainFrame.should_refresh_auxiliary_preview` | — | — |
| `MainFrame.should_refresh_cached_affine` | — | — |
| `MainFrame.should_refresh_transparent_capture` | — | — |
| `MainFrame.should_update_capture_preview_ui` | — | — |
| `MainFrame.show_basic_layer_window` | Create/show BasicLayerWindow when layer blending enabled. | — |
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
| `MainFrame.update_character_edge_controls_visibility` | — | — |
| `MainFrame.update_mouse_mocap_face_pose` | — | — |
| `MainFrame.update_output_background_controls_visibility` | — | — |
| `MainFrame.update_output_window_visibility` | The layered ULW (easyvtuberstudio_output) is the sole on-screen output | — |
| `MainFrame.update_source_image_bitmap` | Refresh source preview bitmap; overlays basic layers when blending is on. | — |
| `MainFrame.wx_bitmap_to_rgba_array` | — | — |
| `MainFrame.wx_image_to_rgba_array` | — | — |
