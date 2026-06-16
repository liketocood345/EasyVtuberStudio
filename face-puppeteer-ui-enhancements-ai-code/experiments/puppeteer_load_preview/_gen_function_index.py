"""Generate CUSTOM_FUNCTION_INDEX.md from custom puppeteer_load_preview sources."""
from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "CUSTOM_FUNCTION_INDEX.md"
SKIP_DIRS = {"deps", "external_layer_output", "basic_layers", "__pycache__", "assets"}
SKIP_FILES = {"_gen_function_index.py", "smoke_load_preview.py", "smoke_tha3_preview.py"}

# Manual UI labels (English) for controls whose wx labels are bilingual or indirect.
UI_OVERRIDES: Dict[str, str] = {
    "quick_calibrate_head_orientation_button": "Compact: Calibrate Head Orientation",
    "quick_calibrate_scale_button": "Compact: Output Dynamic Enhancement Calibration",
    "toggle_full_controls_button": "Compact: Toggle Full Controls",
    "switch_to_compact_button": "Full controls: Switch to Compact",
    "load_last_tha3_png_button": "Load Last THA3 PNG",
    "load_tha3_other_png_button": "Load Other THA3 PNG",
    "load_last_model_button": "Load Last THA4 Student Model",
    "load_model_button": "Load THA4 Student Model",
    "enable_auto_transform_checkbox": "Enable Auto Pan & Scale",
    "invert_tilt_mapping_checkbox": "Tilt Opposite to Head",
    "enable_direction_calibration_checkbox": "Auto Calibrate Forward Gaze",
    "calibrate_neutral_button": "Calibrate Head Orientation (postprocess)",
    "auto_direction_calibration_interval_seconds_ctrl": "Forward Gaze Interval (seconds)",
    "enable_scale_calibration_checkbox": "Enable Auto Output Dynamic Enhancement Calibration",
    "calibrate_scale_button": "Output Dynamic Enhancement Calibration (postprocess)",
    "auto_scale_calibration_interval_seconds_ctrl": "Enhancement Calibration Interval (seconds)",
    "output_background_mode_choice": "Background mode (solid / image / transparent capture)",
    "output_background_choice": "Background color picker",
    "output_background_image_browse_button": "Browse Background Image",
    "mirror_output_checkbox": "Character Mirror",
    "layer_blend_enabled_checkbox": "Enable Layer Blending",
    "mouth_infer_cap_choice": "GPU Infer Cap (Hz)",
    "smooth_affine_30hz_checkbox": "Smooth Motion 30Hz",
    "output_frame_interpolation_choice": "Frame Interpolation multiplier",
    "tha3_model_variant_choice": "THA3 Model Variant",
    "video_source_choice": "Video source dropdown",
    "refresh_video_sources_button": "Refresh video sources",
    "move_x_gain_spin": "Pan X gain slider",
    "move_y_gain_spin": "Pan Y gain slider",
    "scale_gain_spin": "Scale gain slider",
    "min_scale_spin": "Minimum scale slider",
    "max_scale_spin": "Maximum scale slider",
    "tilt_limit_spin": "Tilt limit slider",
    "smoothing_spin": "Smoothing slider",
    "scale_curve_near_spin": "Scale curve near slider",
    "scale_curve_far_spin": "Scale curve far slider",
    "scale_curve_arc_spin": "Scale curve arc slider",
    "scale_curve_peak_shift_spin": "Scale curve peak shift slider",
    "antialias_strength_spin": "Anti-Aliasing strength slider",
    "animation_panel": "Animation panel (mouse wheel scroll)",
    "animation_left_panel": "Output preview panel (resize)",
    "postprocess_scroll": "Postprocess scroll area (resize)",
    "main_splitter": "Main column splitter",
    "animation_splitter": "Animation column splitter",
    "right_sidebar_splitter": "Right sidebar splitter",
    "webcam_capture_panel": "Webcam preview (double-click opens popup)",
    "source_image_panel": "Source character image panel",
    "scale_curve_panel": "Scale curve preview panel",
    "result_image_panel": "Output window image panel (drag pan)",
    "preview_panel": "Webcam popup preview panel",
    "controls_frame": "Hover help timer (controls window)",
    "capture_timer": "Timer: webcam/window capture (~15 Hz)",
    "display_timer": "Timer: display present (~30 Hz)",
    "animation_timer": "Timer: GPU infer scheduling",
}

# Category hints for MainFrame methods (prefix / exact name -> section)
MAINFRAME_SECTIONS: List[Tuple[str, List[str]]] = [
    ("UI event handlers", []),
    ("Calibration", [
        "_perform_head_orientation_calibration", "calibrate_", "apply_neutral_calibration",
        "apply_face_orientation", "update_neutral_", "apply_enabled_auto_calibration",
        "maybe_run_periodic_", "refresh_auto_transform", "refresh_scale_curve",
    ]),
    ("Display, output, and composition", [
        "draw_", "paint_", "present_", "compose_", "render_", "update_display_transform",
        "create_result", "create_composition", "create_rgba", "sanitize_", "mirror_",
        "output_background", "notify_output_background", "get_output_background",
        "set_output_background", "format_output_background", "load_output_background",
        "handle_output_frame", "apply_output_frame", "apply_capture_output",
        "schedule_output_frame", "schedule_capture_output", "_refresh_output",
        "_present_smooth", "_note_display_fps", "is_smooth_display",
        "_get_compose_signature", "_invalidate_render",
    ]),
    ("GPU infer and pose pipeline", [
        "schedule_async_pose", "_async_pose", "_finish_async", "resolve_scheduled_infer",
        "should_schedule_infer", "_pose_", "update_mediapipe", "apply_negative_tilt",
        "reset_frame_interpolation", "on_display_timer", "on_infer_tick",
        "update_result_image_bitmap", "active_image_source.tick",
    ]),
    ("Capture and video sources", [
        "capture_", "video_source", "webcam", "update_capture", "refresh_video",
        "open_video", "apply_camera", "list_capture", "window_capture",
        "refresh_and_autoload_video", "update_video_source", "update_last_window",
        "schedule_active_capture", "schedule_idle_capture",
    ]),
    ("Layers and external bridge", [
        "layer_", "basic_layer", "layer_blend",
        "external_layer", "open_basic_layer",
    ]),
    ("Persistence and UI state", [
        "persistent_ui", "save_persistent", "load_persistent", "apply_persistent",
        "schedule_window_geometry", "save_basic_layer_window",
    ]),
    ("Layout and geometry", [
        "schedule_dynamic_output", "schedule_postprocess", "on_dynamic_output",
        "on_postprocess", "on_column_splitter", "on_compact_geometry",
        "wrap_static_text", "apply_splitter", "apply_client_rect",
        "apply_controls_window", "handle_controls_frame", "schedule_refresh_controls",
        "refresh_right_sidebar", "set_wrapped_static", "set_static_text_if",
        "set_text_ctrl_if",
    ]),
    ("Model and image source loading", [
        "load_model", "load_tha3", "load_last", "switch_image", "get_image_source",
        "refresh_image_source", "is_model_loaded", "update_load_model",
        "resolve_character_model", "render_default_pose",
    ]),
    ("Window lifecycle and mode switching", [
        "create_ui", "create_controls", "create_animation", "create_capture",
        "create_postprocess", "create_compact", "create_timers", "on_close",
        "toggle_full", "switch_to_compact", "get_dialog_parent",
        "refresh_model_loaded", "_on_main_frame_activate",
    ]),
    ("Hover help and misc UI helpers", [
        "hover_help", "on_control_hover", "on_hover_help", "bind_hover",
        "slider_label", "create_display_transform_slider", "create_rotation_column",
        "update_fps", "refresh_fps",
    ]),
]

MODULE_PURPOSE_OVERRIDES: Dict[str, str] = {
    "normalize_multiplier": "Clamp frame-interpolation multiplier to supported values.",
    "lerp_pose": "Linearly interpolate two pose vectors for midpoint infer.",
    "label_for_multiplier": "Human-readable label for interpolation multiplier choice.",
    "mediapipe_pose_to_tha3_vector": "Convert MediaPipe face pose to THA3 45-D parameter vector.",
    "neutral_tha3_pose": "Build neutral THA3 pose from converter defaults.",
    "create_image_source": "Factory: instantiate Tha4StudentSource or Tha3Source.",
    "switch_image_source": "Stop current source, switch mode, optionally autoload asset.",
    "_sync_image_source_mode_choice": "Sync internal mode flag after source switch.",
    "Tha3Source.load_asset": "Load 512×512 RGBA PNG and start THA3 engine.",
    "Tha3Source.tick": "Run THA3 infer step from current MediaPipe pose.",
    "Tha4StudentSource.load_asset": "Load character via THA4 Student yaml path.",
    "Tha4StudentSource.tick": "Schedule THA4 Student poser infer from pose.",
    "TransparentCaptureWindow.present_rgba": "Blit premultiplied BGRA to layered Win32 window for OBS.",
    "LayerCompositor.compose_foreground_rgba": "Alpha-composite enabled basic layers over character RGBA.",
    "save_basic_layers_state": "Persist layer slots to `basic_layers/*.json`.",
    "load_basic_layers_state": "Load layer slots from disk into BasicLayersState.",
    "move_layer_z_order": "Change stack position of a layer slot by delta.",
    "MainFrame.update_source_image_bitmap": "Refresh source preview bitmap; overlays basic layers when blending is on.",
    "MainFrame._perform_head_orientation_calibration": "Path A only: converter head orientation; never resets output dynamic enhancement.",
    "MainFrame.calibrate_head_orientation_quick": "Compact launcher: path A head orientation only.",
    "MainFrame.calibrate_neutral_clicked": "Postprocess button: path A head orientation only.",
    "MainFrame.calibrate_scale_clicked": "Path B: manual output dynamic enhancement calibration.",
    "MainFrame.calibrate_scale_clicked": "Manual output dynamic enhancement calibration (path B neutral/size).",
    "MainFrame.on_display_timer": "30 Hz display tick: update cached affine and present output frame.",
    "MainFrame.on_infer_tick": "Infer scheduling tick: audio refresh + image source tick + async GPU infer.",
    "MainFrame.on_display_transform_control_changed": "Persist and apply auto pan/scale, calibration toggles, mirror, slider values.",
    "MainFrame.on_layer_blend_changed": "Enable/disable compositing basic layers into previews and output.",
    "MainFrame.on_smooth_affine_30hz_changed": "Toggle smooth 30 Hz cached-affine display vs infer-rate-only display.",
    "MainFrame.on_output_frame_interpolation_changed": "Set pose interpolation multiplier; adjusts effective infer cap.",
    "MainFrame.on_mouth_infer_cap_changed": "Set base GPU infer cap (Hz); persisted to ui state.",
    "MainFrame.show_basic_layer_window": "Create/show BasicLayerWindow when layer blending enabled.",
    "MainFrame.open_basic_layer_window_if_needed": "Lazy-open layer editor on first enable.",
}

MODULE_INTROS = {
    "frame_interpolation.py": "Re-export shim; see output_enhancement.pose_interpolation.",
    "output_enhancement/pose_interpolation.py": "Pose-based frame interpolation (no direct wx controls; driven by postprocess Frame Interpolation and GPU Infer Cap).",
    "output_enhancement/antialiasing.py": "SSAA anti-aliasing for keyframe compose (Anti-Aliasing strength slider).",
    "layer_runtime.py": "Basic layer stack data model, geometry, compositing, and JSON persistence.",
    "basic_layer_window.py": "Unlimited layer editor window (opened when Enable Unlimited Layer System is on).",
    "transparent_capture_window.py": "Win32 layered window for OBS transparent capture output.",
    "window_capture.py": "Win32 window enumeration and client-area BGR capture for external video sources.",
    "tha3_paths.py": "Repository-relative path resolution for THA3 bundle and model assets.",
    "tha3_engine.py": "THA3 ONNX/PyTorch inference engine wrapper.",
    "tha3_pose_adapter.py": "MediaPipe pose vector to THA3 45-D pose adapter.",
    "image_sources/": "Pluggable image source backends (THA4 Student vs THA3).",
    "verify_periodic_calibration.py": "Offline unit tests for periodic calibration logic (no UI).",
}


def iter_py_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in sorted(filenames):
            if fn.endswith(".py") and fn not in SKIP_FILES:
                yield Path(dirpath) / fn


def rel_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def parse_functions(path: Path) -> List[Tuple[str, str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: List[Tuple[str, str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for n in node.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    doc = ast.get_docstring(n) or ""
                    first = doc.strip().split("\n")[0] if doc.strip() else ""
                    out.append((node.name, n.name, first))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            doc = ast.get_docstring(node) or ""
            first = doc.strip().split("\n")[0] if doc.strip() else ""
            out.append(("", node.name, first))
    return out


def extract_mainframe_bindings(src: str) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    bind_re = re.compile(r"self\.(\w+)\.Bind\([^,]+,\s*self\.(\w+)")
    handlers: Dict[str, List[str]] = {}
    for m in bind_re.finditer(src):
        ctrl, handler = m.group(1), m.group(2)
        handlers.setdefault(handler, []).append(ctrl)

    ctrl_labels: Dict[str, str] = {}
    for pat in [
        r'self\.(\w+)\s*=\s*wx\.Button\([^)]*label\s*=\s*["\']([^"\']+)["\']',
        r'self\.(\w+)\s*=\s*wx\.CheckBox\([^)]*label\s*=\s*["\']([^"\']+)["\']',
        r'self\.(\w+)\s*=\s*FloatSliderControl\([^)]*name_en\s*=\s*["\']([^"\']+)["\']',
    ]:
        for m in re.finditer(pat, src):
            label = m.group(2)
            if " / " in label:
                label = label.split(" / ", 1)[1].strip()
            ctrl_labels[m.group(1)] = label

    # slider_label(...) assignments
    for m in re.finditer(
        r"create_display_transform_slider_control\(\s*[^,]+,\s*[^,]+,\s*"
        r"slider_label\([^,]+,\s*[\"']([^\"']+)[\"']",
        src,
    ):
        pass  # captured via attribute name below

    attr_slider = {
        "move_x_gain_spin": "Pan X gain",
        "move_y_gain_spin": "Pan Y gain",
        "scale_gain_spin": "Scale gain",
        "min_scale_spin": "Minimum scale",
        "max_scale_spin": "Maximum scale",
        "tilt_limit_spin": "Tilt limit",
        "smoothing_spin": "Smoothing",
        "scale_curve_near_spin": "Scale curve near",
        "scale_curve_far_spin": "Scale curve far",
        "scale_curve_arc_spin": "Scale curve arc",
        "scale_curve_peak_shift_spin": "Scale curve peak shift",
        "antialias_strength_spin": "Anti-Aliasing strength",
    }
    ctrl_labels.update(attr_slider)

    return handlers, ctrl_labels


def ui_for_handler(handler: str, handlers: Dict[str, List[str]], ctrl_labels: Dict[str, str]) -> str:
    ctrls = handlers.get(handler, [])
    if not ctrls:
        return "—"
    labels = []
    for c in ctrls:
        labels.append(UI_OVERRIDES.get(c, ctrl_labels.get(c, c)))
    return "; ".join(dict.fromkeys(labels))


def classify_mainframe(name: str, handlers: Dict[str, List[str]]) -> str:
    if name in handlers:
        return "UI event handlers"
    for section, prefixes in MAINFRAME_SECTIONS[1:]:
        for p in prefixes:
            if name == p or name.startswith(p):
                return section
    return "Internal helpers"


def infer_purpose(class_name: str, func_name: str, doc: str) -> str:
    qual = f"{class_name}.{func_name}" if class_name else func_name
    if qual in MODULE_PURPOSE_OVERRIDES:
        return MODULE_PURPOSE_OVERRIDES[qual]
    if func_name in MODULE_PURPOSE_OVERRIDES:
        return MODULE_PURPOSE_OVERRIDES[func_name]
    if doc and not re.search(r"[\u4e00-\u9fff]", doc):
        return doc
    if func_name in ("__init__", "__post_init__"):
        return f"Constructor for `{class_name}`." if class_name else "Module-level initializer."
    # Heuristic one-liners for common patterns
    if func_name.startswith("on_"):
        return f"wx event handler for {func_name[3:].replace('_', ' ')}."
    if func_name.startswith("create_"):
        return f"Builds UI widget(s) for {func_name[7:].replace('_', ' ')}."
    if func_name.startswith("get_"):
        return f"Returns {func_name[4:].replace('_', ' ')}."
    if func_name.startswith("set_"):
        return f"Updates {func_name[4:].replace('_', ' ')}."
    if func_name.startswith("schedule_"):
        return f"Debounced/async scheduler for {func_name[9:].replace('_', ' ')}."
    if func_name.startswith("_"):
        return f"Private helper for {func_name[1:].replace('_', ' ')}."
    return "—"


def md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def write_table(rows: List[Tuple[str, str, str]]) -> List[str]:
    lines = ["| Function | Purpose | UI control(s) |", "| --- | --- | --- |"]
    for func, purpose, ui in rows:
        lines.append(f"| `{md_escape(func)}` | {md_escape(purpose)} | {md_escape(ui)} |")
    return lines


def main():
    main_src = (ROOT / "character_model_mediapipe_puppeteer_load_preview.py").read_text(encoding="utf-8")
    handlers, ctrl_labels = extract_mainframe_bindings(main_src)

    lines: List[str] = [
        "# Custom Function Index",
        "",
        "English index of **custom** functions in the Load Preview experiment.",
        "Use this document to trace UI controls to handlers and to avoid regressions",
        "(for example, calibration buttons that must call the same code path).",
        "",
        "## Scope",
        "",
        "| Included | Excluded |",
        "| --- | --- |",
        "| `experiments/puppeteer_load_preview/**` Python modules | Upstream THA4 demo package (`talking-head-anime-4-demo/src/tha4/**`) |",
        "| Fork-specific shell around THA4 Student / THA3 / layers / output | Vendored THA3 runtime inside `deps/tha3/` |",
        "| Local tests under this experiment (`verify_periodic_calibration.py`) | Smoke scripts (`smoke_*.py`) |",
        "",
        "**Primary entry:** `character_model_mediapipe_puppeteer_load_preview.py` (`MainFrame`).",
        "",
        "## Maintenance",
        "",
        "Regenerate tables after large refactors:",
        "",
        "```powershell",
        "python experiments/puppeteer_load_preview/_gen_function_index.py",
        "```",
        "",
        "When adding a user-facing handler, update `UI_OVERRIDES` in the generator if the",
        "wx control label is not extracted automatically.",
        "",
        "## Quick reference — calibration paths",
        "",
        "Two related but **independent** calibrations (do not cross-call):",
        "",
        "| Path | Function | Effect | UI controls |",
        "| --- | --- | --- | --- |",
        "| **A — head orientation** | `_perform_head_orientation_calibration` → `pose_converter.apply_face_orientation_calibration()` | Sets MediaPipe head X/Y/Z offsets in converter only | Compact **Calibrate Head Orientation**; preview column **Calibrate Head Orientation**; model-input **Calibrate Forward Gaze**; periodic **Auto Calibrate Forward Gaze** |",
        "| **B — output dynamic enhancement** | `update_neutral_output_enhancement` / `apply_neutral_calibration` (auto-init only) | Updates pan/scale neutral (`neutral_face_screen_motion`); manual via scale calibrate | **Output Dynamic Enhancement Calibration**; auto enhancement checkbox + interval |",
        "",
        "**Boundary:** path A must **not** call `apply_neutral_calibration`, `update_neutral_output_enhancement`, or reset display offset/scale. Path B must **not** call `apply_face_orientation_calibration`.",
        "",
        "## Quick reference — display vs infer timers",
        "",
        "| Timer | Handler | Interval | Role |",
        "| --- | --- | --- | --- |",
        "| `capture_timer` | `update_capture_panel` | ~66 ms | Webcam / window capture |",
        "| `display_timer` | `on_display_timer` | 30 ms (~30 Hz) | Cached affine present, Out FPS |",
        "| `animation_timer` | `on_infer_tick` | dynamic | Schedule async GPU infer |",
        "",
    ]

    # Smaller modules first
    for path in sorted(iter_py_files()):
        rel = rel_path(path)
        if rel == "character_model_mediapipe_puppeteer_load_preview.py":
            continue
        funcs = parse_functions(path)
        if not funcs:
            continue
        intro = ""
        for key, text in MODULE_INTROS.items():
            if key in rel.replace("\\", "/"):
                intro = text
                break
        lines.append(f"## `{rel}`")
        lines.append("")
        if intro:
            lines.append(intro)
            lines.append("")
        rows = []
        for cls, fn, doc in funcs:
            qual = f"{cls}.{fn}" if cls else fn
            purpose = infer_purpose(cls, fn, doc)
            ui = "—"
            if rel == "basic_layer_window.py" and cls == "BasicLayerWindow":
                ui_map = {
                    "_on_reset_transform": "Detail dock: Reset transform",
                    "_on_clear_asset": "Detail dock: Clear asset",
                    "_on_detail_changed": "Detail dock: Visible / binding choice",
                    "_on_scale_changed": "Detail dock: Scale slider",
                    "_on_rotation_changed": "Detail dock: Rotation slider",
                    "_load_asset": "Layer row: Load",
                    "_move_layer": "Layer row: Move up/down",
                    "on_close": "Basic Layer window close",
                    "on_geometry_changed": "Basic Layer window move/resize",
                }
                ui = ui_map.get(fn, "Basic Layer window (internal)" if fn.startswith("_") else "—")
            rows.append((qual, purpose, ui))
        lines.extend(write_table(rows))
        lines.append("")

    # MainFrame by section
    lines.append("## `character_model_mediapipe_puppeteer_load_preview.py`")
    lines.append("")
    lines.append("### Supporting types (non-MainFrame)")
    lines.append("")
    support_rows = []
    funcs = parse_functions(ROOT / "character_model_mediapipe_puppeteer_load_preview.py")
    for cls, fn, doc in funcs:
        if cls in ("MainFrame",):
            continue
        qual = f"{cls}.{fn}" if cls else fn
        ui = "—"
        if cls == "FloatSliderControl":
            ui = "Any `FloatSliderControl` slider (display transform + anti-aliasing)"
        elif cls == "OutputFrame":
            ui_map = {
                "paint_result_image_panel": "Output window image panel",
                "on_left_down": "Output window drag pan",
                "on_left_up": "Output window drag pan",
                "on_mouse_move": "Output window drag pan",
                "on_size": "Output window resize",
                "on_move": "Output window move",
                "on_close": "Output window close",
            }
            ui = ui_map.get(fn, "Output window (internal)")
        elif cls == "WebcamPreviewPopupFrame":
            ui = "Webcam popup" if not fn.startswith("_") else "Webcam popup (internal)"
        support_rows.append((qual, infer_purpose(cls, fn, doc), ui))
    lines.extend(write_table(support_rows))
    lines.append("")

    mf_funcs = [(fn, doc) for cls, fn, doc in funcs if cls == "MainFrame"]
    by_section: Dict[str, List[Tuple[str, str, str]]] = {}
    for fn, doc in mf_funcs:
        section = classify_mainframe(fn, handlers)
        qual = f"MainFrame.{fn}"
        purpose = infer_purpose("MainFrame", fn, doc)
        ui = ui_for_handler(fn, handlers, ctrl_labels)
        by_section.setdefault(section, []).append((qual, purpose, ui))

    section_order = [s for s, _ in MAINFRAME_SECTIONS] + ["Internal helpers"]
    for section in section_order:
        rows = by_section.get(section)
        if not rows:
            continue
        lines.append(f"### MainFrame — {section}")
        lines.append("")
        lines.extend(write_table(sorted(rows, key=lambda r: r[0])))
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT} ({len(lines)} lines, {len(mf_funcs)} MainFrame methods)")


if __name__ == "__main__":
    main()
