# Experimental copy: render one default-pose frame right after Load Model (no camera required).
# Original: talking-head-anime-4-demo/src/tha4/app/character_model_mediapipe_puppeteer.py
import math
import os
import sys
import ctypes
from ctypes import wintypes
import inspect
import io
import tempfile
import threading
import time
import json
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List
import PIL.Image

_EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _EXPERIMENT_DIR not in sys.path:
    sys.path.insert(0, _EXPERIMENT_DIR)

OUTPUT_BACKGROUND_TRANSPARENT = "transparent"
OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE = "transparent_capture"
OUTPUT_BACKGROUND_COLOR = "color"
OUTPUT_BACKGROUND_IMAGE = "image"
OUTPUT_BACKGROUND_MODE_VALUES = (
    OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE,
    OUTPUT_BACKGROUND_COLOR,
    OUTPUT_BACKGROUND_IMAGE,
    OUTPUT_BACKGROUND_TRANSPARENT,
)
OUTPUT_BACKGROUND_MODE_LABELS = (
    "透明 / Transparent",
    "自选纯色背景 / Solid Color",
    "自选图片 / Custom Image",
    "黑键 / Color Key (#000000)",
)
# Window Capture (BitBlt) does not preserve alpha; OBS Color Key on pure black works reliably.
OUTPUT_CAPTURE_COLORKEY_RGB = (0, 0, 0)
BUNDLED_TRANSPARENT_BACKGROUND_PATH = os.path.join(
    _EXPERIMENT_DIR, "assets", "backgrounds", "transparent.png")
MOUTH_INFER_CAP_HZ_VALUES = (10, 15, 30)
MOUTH_INFER_CAP_HZ_LABELS = (
    "10 Hz (推荐 / recommended)",
    "15 Hz",
    "30 Hz (无节流 / no throttle)",
)
MOUTH_INFER_CAP_HZ_DEFAULT = 10
MOUTH_POSE_QUANT_STEP = 0.05
POSE_PARAM_EPS = 1e-4

from tha3_paths import get_demo_src_path, find_repo_root, get_demo_root

_demo_src_path = str(get_demo_src_path(find_repo_root(Path(_EXPERIMENT_DIR))))
if _demo_src_path not in sys.path:
    sys.path.insert(0, _demo_src_path)

os.environ.setdefault("GLOG_minloglevel", "3")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module=r"torch\.nn\.functional")
warnings.filterwarnings("ignore", message=r".*cudnn.*")

import cv2
import numpy
from scipy.spatial.transform import Rotation

_MEDIAPIPE_MODULE = None


def get_mediapipe_module():
    global _MEDIAPIPE_MODULE
    if _MEDIAPIPE_MODULE is None:
        import mediapipe as mp
        _MEDIAPIPE_MODULE = mp
    return _MEDIAPIPE_MODULE

from tha4.shion.base.image_util import resize_PIL_image
from tha4.charmodel.character_model import CharacterModel
from tha4.image_util import convert_linear_to_srgb
from tha4.mocap.mediapipe_constants import HEAD_ROTATIONS, HEAD_X, HEAD_Y, HEAD_Z, BLENDSHAPE_NAMES
from tha4.mocap.mediapipe_face_pose import MediaPipeFacePose
from tha4.mocap.mediapipe_face_pose_converter_00 import MediaPoseFacePoseConverter00

sys.path.append(os.getcwd())

import torch
import wx

from character_edge_postprocess import (
    CHARACTER_EDGE_MODE_LABELS,
    CHARACTER_EDGE_MODE_VALUES,
    CHARACTER_EDGE_NONE,
    CHARACTER_EDGE_OUTLINE,
    CHARACTER_EDGE_WIDTH_DEFAULT,
    CHARACTER_EDGE_WIDTH_INCREMENT,
    CHARACTER_EDGE_WIDTH_MAX,
    CHARACTER_EDGE_WIDTH_MIN,
    apply_character_edge_postprocess,
    clamp_character_edge_width,
    composite_rgba_arrays,
    normalize_character_edge_mode,
)
from mouse_mocap_driver import (
    MOCAP_INPUT_MODE_LABELS,
    MOCAP_INPUT_MODE_MEDIAPIPE,
    MOCAP_INPUT_MODE_MOUSE_AUDIO,
    MOCAP_INPUT_MODE_VALUES,
    MOUSE_BLINK_INTERVAL_MAX_SEC,
    MOUSE_BLINK_INTERVAL_MIN_SEC,
    MOUSE_DEFAULT_FACE_SIZE,
    MOUSE_HORIZONTAL_TILT_MIX_MAX,
    MOUSE_HORIZONTAL_TILT_MIX_MIN,
    MouseCenterZone,
    MouseMocapConfig,
    blend_mouse_head_roll_degrees,
    build_mouse_dynamic_face_screen_motion,
    build_mouse_mediapipe_face_pose,
    clamp,
    clamp_blink_interval_sec,
    clamp_horizontal_tilt_mix,
    extract_head_roll_degrees,
    face_size_from_zone_distance,
    is_mouse_inside_center_zone,
    mouse_center_zone_calibration_point,
    normalize_mocap_input_mode,
    zone_local_coords,
)
from mouse_zone_panel import MouseZonePanel
from layer_runtime import (
    BasicLayersState,
    BindingContext,
    LayerAssetCache,
    LayerBindingSmoother,
    HeadBindingPoseFilter,
    LayerCompositor,
    NECK_ANCHOR_RATIO_DEFAULT,
    OCCLUSION_BEHIND,
    OCCLUSION_FRONT,
    BODY_BIND_RAY_T_DEFAULT,
    HEAD_BIND_RAY_T_DEFAULT,
    BIND_RAY_PERCENT_DEFAULT,
    BIND_RAY_PERCENT_UI_MIN,
    BIND_RAY_PERCENT_UI_MAX,
    migrate_bind_ray_percent_from_state,
    migrate_layer_bind_ray_percents,
    migrate_layer_bind_neck_ratios,
    apply_body_head_tilt_opposite_to_pose,
    normalize_bind_ray_percent,
    clamp_neck_anchor_ratio,
    clamp_body_bind_lean_follow_gain,
    BODY_BIND_LEAN_FOLLOW_GAIN,
    contrast_highlight_colour,
    basic_layers_state_has_active_motion,
    consume_layer_gif_playback_visibility_dirty,
    compute_orbit_edit_geometry,
    layer_uses_orbit_edit_chrome,
    load_basic_layers_state,
    OrbitEditGeometry,
    resolve_layer_rects,
    resolve_orbit_track_layer,
    resolved_layer_rotation_deg,
    save_basic_layers_state,
    apply_layer_hotkey_action as apply_layer_hotkey_action_to_state,
    layer_hotkey_action_target_slot_ids,
    layer_hotkey_action_needs_asset_cache_reset,
    reload_layer_from_asset_material,
)
from layer_hotkey_registry import LayerHotkeyRegistry
from layer_interaction import (
    LayerEditMode,
    apply_move_delta,
    apply_orbit_pivot_canvas_delta,
    apply_scale_from_drag,
    hit_test_layer_edit,
    hit_test_orbit_edit,
    hit_test_resolved_rect,
    nudge_layer,
    panel_to_layer_delta,
)

from image_sources.factory import create_image_source, switch_image_source
from image_sources.base import normalize_image_source_mode
from tha3_paths import (
    IMAGE_SOURCE_THA3,
    IMAGE_SOURCE_THA4,
    THA3_VARIANT_CHOICES,
    find_repo_root,
    from_repo_relative,
    get_demo_root,
    resolve_bundled_bai_model_paths,
    to_repo_relative,
)
from portable_paths import face_capture_assets_ready, get_portable_root, resolve_mediapipe_task_path
from ui_dialog_guard import show_rate_limited_message
from ui_switch_guard import block_events, is_blocked, restore_choice, run_guarded_switch, snapshot_choice
from ui_alignment_monitor import AlignmentProbe, UiAlignmentMonitor
from ui_change_history import UserChangeHistory, wire_controls_for_change_log, wire_float_slider_controls
import window_capture
from output_enhancement.pose_interpolation import POSE_FRAME_INTERP_OFF as FRAME_INTERP_OFF
from output_enhancement.config import (
    INFER_BACKEND_LABELS,
    INFER_BACKEND_PYTORCH,
    INFER_BACKEND_VALUES,
    NN_FRAME_INTERP_LABELS,
    NN_FRAME_INTERP_OFF,
    NN_FRAME_INTERP_VALUES,
    NN_SR_LABELS,
    NN_SR_OFF,
    NN_SR_VALUES,
    THA_INFER_FP16_CHOICES,
    THA_INFER_FP16_LABELS,
)
from output_enhancement.runtime import OutputEnhancementRuntime
from output_enhancement.antialiasing import get_antialias_factor_from_control
from output_enhancement.pose_interpolation import (
    POSE_FRAME_INTERP_LABELS,
    POSE_FRAME_INTERP_OFF,
    POSE_FRAME_INTERP_VALUES,
    get_effective_infer_cap_hz as pose_interp_effective_cap_hz,
    is_pose_interpolation_active,
    normalize_multiplier as normalize_pose_frame_multiplier,
)
from output_enhancement.config import (
    normalize_infer_backend,
    normalize_nn_frame_multiplier,
    normalize_sr_mode,
    normalize_tha_infer_fp16,
)
from output_enhancement.paths import find_repo_root, is_output_enhancement_installed
from output_enhancement.slow_task import run_slow_task
from output_enhancement.tha_infer import apply_poser_precision
from rgba_capture_compose import (
    compose_character_rgba_from_keyframe,
    scale_rgba,
    sanitize_transparent_rgb,
    wx_image_to_rgba_array as capture_wx_image_to_rgba_array,
)
from transparent_capture_window import (
    TransparentCaptureWindow,
    _resolve_app_icon_path,
    _straight_rgba_to_premultiplied_bgra,
)
from numpy_layer_compositor import compose_full_stack_rgba
from numpy_edit_chrome import (
    DEFAULT_HIGHLIGHT_RGB,
    render_orbit_edit_chrome_rgba,
    render_selection_chrome_rgba,
)
from output_backends import resolve_output_backend

_PERF_LOG_PATH = r"e:\debug-3353ed.log"
_perf_window: dict = {
    "present_ms": 0.0,
    "capture_ms": 0.0,
    "frames": 0,
    "fast_present": 0,
    "slow_present": 0,
    "last_log_mono": 0.0,
    "stages": {},
}


def _perf_record(
        *,
        present_ms: float = 0.0,
        capture_ms: float = 0.0,
        fast_present: bool = False,
        stages: Optional[dict] = None) -> None:
    # #region agent log
    _perf_window["present_ms"] += present_ms
    _perf_window["capture_ms"] += capture_ms
    _perf_window["frames"] += 1
    if fast_present:
        _perf_window["fast_present"] += 1
    else:
        _perf_window["slow_present"] += 1
    if stages:
        stage_acc = _perf_window["stages"]
        for name, value in stages.items():
            stage_acc[name] = stage_acc.get(name, 0.0) + value
    now = time.monotonic()
    if now - _perf_window["last_log_mono"] < 1.0:
        return
    frames = max(1, _perf_window["frames"])
    try:
        import json
        stage_avg = {
            name: round(total / frames, 2)
            for name, total in _perf_window["stages"].items()
        }
        with open(_PERF_LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps({
                "sessionId": "3353ed",
                "runId": "perf",
                "hypothesisId": "PERF",
                "location": "character_model_mediapipe_puppeteer_load_preview.py:_perf_record",
                "message": "present/capture timing window",
                "data": {
                    "frames": frames,
                    "avg_present_ms": round(_perf_window["present_ms"] / frames, 2),
                    "avg_capture_ms": round(_perf_window["capture_ms"] / frames, 2),
                    "fast_present": _perf_window["fast_present"],
                    "slow_present": _perf_window["slow_present"],
                    "capture_decoupled": True,
                    "stage_ms": stage_avg,
                },
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    _perf_window.update({
        "present_ms": 0.0,
        "capture_ms": 0.0,
        "frames": 0,
        "fast_present": 0,
        "slow_present": 0,
        "last_log_mono": now,
        "stages": {},
    })
    # #endregion


def _startup_record(phase: str, ms: float, **extra) -> None:
    """Log startup-phase duration (f-057: budget = main UI shell ready; excludes model/mocap/layers)."""
    # #region agent log
    try:
        import json
        data = {"ms": round(float(ms), 1)}
        data.update(extra)
        with open(_PERF_LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps({
                "sessionId": "3353ed",
                "runId": "startup",
                "hypothesisId": "STARTUP",
                "location": "character_model_mediapipe_puppeteer_load_preview.py:startup",
                "message": phase,
                "data": data,
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


_seen_err_keys: set = set()


def _err_record(
        hypothesis_id: str,
        location: str,
        exc_or_msg,
        *,
        data: Optional[dict] = None) -> None:
    # #region agent log
    message = str(exc_or_msg)
    tb_text = ""
    if isinstance(exc_or_msg, BaseException):
        message = repr(exc_or_msg)
        tb_text = traceback.format_exc()
    dedupe_key = (location, message)
    if dedupe_key in _seen_err_keys:
        return
    _seen_err_keys.add(dedupe_key)
    payload_data = dict(data or {})
    if tb_text:
        payload_data["traceback"] = tb_text[:2000]
    try:
        import json
        with open(_PERF_LOG_PATH, "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps({
                "sessionId": "3353ed",
                "runId": "err",
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": payload_data,
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    print(f"ERR[{hypothesis_id}] {location}: {message}", file=sys.stderr)
    # #endregion


def _install_debug_excepthook() -> None:
    # #region agent log
    if getattr(_install_debug_excepthook, "_installed", False):
        return
    _install_debug_excepthook._installed = True
    previous_hook = sys.excepthook

    def _debug_excepthook(exc_type, exc_value, exc_tb):
        if exc_value is not None:
            _err_record(
                "H-UNCAUGHT",
                f"{getattr(exc_type, '__name__', 'Exception')}",
                exc_value,
                data={
                    "traceback": "".join(
                        traceback.format_exception(exc_type, exc_value, exc_tb))[:2000],
                })
        previous_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _debug_excepthook
    # #endregion


try:
    from absl import logging as absl_logging
    absl_logging.set_verbosity(absl_logging.ERROR)
    absl_logging.set_stderrthreshold("error")
except Exception:
    pass

def make_neutral_mediapipe_face_pose() -> MediaPipeFacePose:
    blendshape_params = {name: 0.0 for name in BLENDSHAPE_NAMES}
    return MediaPipeFacePose(blendshape_params, numpy.eye(4))

@dataclass
class FaceScreenMotion:
    center_x: float
    center_y: float
    face_size: float

def slider_label(name_cn: str, name_en: str, unit_cn: str, unit_en: str) -> str:
    return f"{name_cn} / {name_en} ({unit_cn} / {unit_en})"

class FloatSliderControl:
    LABEL_BOTTOM_MARGIN = 1
    VALUE_TOP_MARGIN = 1
    OUTER_MARGIN = 2
    PANEL_MIN_WIDTH = 108
    WHEEL_ARM_DELAY_MS = 500
    STATIONARY_TOLERANCE_PX = 18

    def __init__(self,
                 parent: wx.Window,
                 sizer,
                 label_text: str,
                 initial_value: float,
                 reasonable_min: float,
                 reasonable_max: float,
                 increment: float,
                 change_handler,
                 slider_min: Optional[float] = None,
                 slider_max: Optional[float] = None):
        self.increment = increment
        span = reasonable_max - reasonable_min
        if span <= 0.0:
            span = max(abs(reasonable_min), abs(reasonable_max), 1.0)
        raw_slider_min = reasonable_min - 0.5 * span
        raw_slider_max = reasonable_max + 0.5 * span
        self.slider_min = math.floor((raw_slider_min if slider_min is None else slider_min) / self.increment) * self.increment
        self.slider_max = math.ceil((raw_slider_max if slider_max is None else slider_max) / self.increment) * self.increment
        self.digits = 0 if increment >= 1.0 else (2 if increment >= 0.01 else 3)

        self.panel = wx.Panel(parent)
        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(panel_sizer)
        self.panel.SetAutoLayout(1)
        self.panel.SetMinSize(wx.Size(self.PANEL_MIN_WIDTH, -1))

        self.label = wx.StaticText(self.panel, label=self._format_multiline_label(label_text), style=wx.ALIGN_CENTER_HORIZONTAL)
        panel_sizer.Add(self.label, 0, wx.EXPAND | wx.BOTTOM, self.LABEL_BOTTOM_MARGIN)

        max_int = self._float_to_int(self.slider_max)
        self.slider = wx.Slider(
            self.panel,
            wx.ID_ANY,
            minValue=0,
            maxValue=max_int,
            value=self._float_to_int(initial_value),
            style=wx.HORIZONTAL)
        self.slider.SetMinSize(wx.Size(-1, 18))
        panel_sizer.Add(self.slider, 0, wx.EXPAND)
        self.slider.Bind(wx.EVT_MOUSEWHEEL, self._handle_slider_mousewheel)
        self.panel.Bind(wx.EVT_ENTER_WINDOW, self._handle_slider_mouse_enter)
        self.panel.Bind(wx.EVT_LEAVE_WINDOW, self._handle_slider_mouse_leave)
        self.slider.Bind(wx.EVT_ENTER_WINDOW, self._handle_slider_mouse_enter)
        self.slider.Bind(wx.EVT_LEAVE_WINDOW, self._handle_slider_mouse_leave)
        self.slider.SetToolTip("")

        self.hover_hint_text = wx.StaticText(
            self.panel,
            label="滚轮已启用，滑动可调 / Wheel active, scroll to adjust",
            style=wx.ALIGN_CENTER_HORIZONTAL)
        self.hover_hint_text.SetForegroundColour(wx.Colour(210, 190, 60))
        self.hover_hint_text.Hide()
        panel_sizer.Add(self.hover_hint_text, 0, wx.EXPAND | wx.TOP, 1)

        self.value_text = wx.StaticText(self.panel, label="", style=wx.ALIGN_CENTER_HORIZONTAL)
        panel_sizer.Add(self.value_text, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, self.VALUE_TOP_MARGIN)
        self._refresh_value_label()

        self.slider.Bind(wx.EVT_SLIDER, self._handle_change)
        self.change_handler = change_handler
        self._hovering = False
        self._wheel_armed = False
        self._pending_leave_check = False
        self._last_hover_mouse_screen_pos: Optional[wx.Point] = None
        self.hover_arm_timer = wx.Timer(self.slider)
        self.slider.Bind(wx.EVT_TIMER, self._handle_hover_arm_timer, id=self.hover_arm_timer.GetId())
        sizer.Add(self.panel, 0, wx.EXPAND | wx.ALL, self.OUTER_MARGIN)

    def _float_to_int(self, value: float) -> int:
        clipped_value = max(self.slider_min, min(self.slider_max, value))
        return int(round((clipped_value - self.slider_min) / self.increment))

    @staticmethod
    def _format_multiline_label(label_text: str) -> str:
        return label_text

    def _int_to_float(self, value: int) -> float:
        return round(self.slider_min + value * self.increment, self.digits + 3)

    def _refresh_value_label(self):
        self.value_text.SetLabel(f"{self.GetValue():.{self.digits}f}")

    def _is_mouse_over_panel(self) -> bool:
        if self.panel is None:
            return False
        mouse_pos = wx.GetMousePosition()
        panel_pos = self.panel.ScreenToClient(mouse_pos)
        return self.panel.GetClientRect().Contains(panel_pos)

    def _is_mouse_stationary_near_last_hover(self) -> bool:
        if self._last_hover_mouse_screen_pos is None:
            return False
        mouse_pos = wx.GetMousePosition()
        dx = int(mouse_pos.x) - int(self._last_hover_mouse_screen_pos.x)
        dy = int(mouse_pos.y) - int(self._last_hover_mouse_screen_pos.y)
        return dx * dx + dy * dy <= self.STATIONARY_TOLERANCE_PX * self.STATIONARY_TOLERANCE_PX

    def _set_wheel_armed(self, armed: bool):
        armed = bool(armed)
        if self._wheel_armed == armed:
            return
        self._wheel_armed = armed
        if self._wheel_armed:
            self.slider.SetBackgroundColour(wx.Colour(70, 70, 45))
            self.hover_hint_text.Show()
        else:
            self.slider.SetBackgroundColour(wx.NullColour)
            self.hover_hint_text.Hide()
        self.panel.Layout()
        self.slider.Refresh()

    def _handle_slider_mouse_enter(self, event: wx.MouseEvent):
        if self._hovering and (self._wheel_armed or self.hover_arm_timer.IsRunning()):
            self._last_hover_mouse_screen_pos = wx.GetMousePosition()
            event.Skip()
            return
        self._pending_leave_check = False
        self._hovering = True
        self._last_hover_mouse_screen_pos = wx.GetMousePosition()
        self._set_wheel_armed(False)
        if not self.hover_arm_timer.IsRunning():
            self.hover_arm_timer.Start(self.WHEEL_ARM_DELAY_MS, oneShot=True)
        event.Skip()

    def _handle_slider_mouse_leave(self, event: wx.MouseEvent):
        if self._pending_leave_check:
            event.Skip()
            return
        self._pending_leave_check = True

        def finalize_leave():
            self._pending_leave_check = False
            if self._is_mouse_over_panel():
                self._hovering = True
                self._last_hover_mouse_screen_pos = wx.GetMousePosition()
                if not self._wheel_armed and not self.hover_arm_timer.IsRunning():
                    self.hover_arm_timer.Start(self.WHEEL_ARM_DELAY_MS, oneShot=True)
                return
            if self._is_mouse_stationary_near_last_hover():
                self._hovering = True
                return
            self._hovering = False
            if self.hover_arm_timer.IsRunning():
                self.hover_arm_timer.Stop()
            self._set_wheel_armed(False)

        wx.CallLater(80, finalize_leave)
        event.Skip()

    def _handle_hover_arm_timer(self, event: wx.Event):
        if self._hovering or self._is_mouse_over_panel():
            self._hovering = True
            self._last_hover_mouse_screen_pos = wx.GetMousePosition()
            self._set_wheel_armed(True)

    def _handle_slider_mousewheel(self, event: wx.MouseEvent):
        if not self._wheel_armed:
            return
        rotation = event.GetWheelRotation()
        if rotation == 0:
            return
        step = 1 if rotation > 0 else -1
        next_value = self.slider.GetValue() + step
        next_value = max(self.slider.GetMin(), min(self.slider.GetMax(), next_value))
        if next_value == self.slider.GetValue():
            return
        self.slider.SetValue(next_value)
        self._handle_change(event)

    def _handle_change(self, event: wx.Event):
        self._refresh_value_label()
        self.change_handler(event)

    def GetValue(self) -> float:
        return self._int_to_float(self.slider.GetValue())

    def SetValue(self, value: float):
        self.slider.SetValue(self._float_to_int(value))
        self._refresh_value_label()

class FpsStatistics:
    def __init__(self):
        self.count = 100
        self.fps = []

    def add_fps(self, fps):
        self.fps.append(fps)
        while len(self.fps) > self.count:
            del self.fps[0]

    def get_average_fps(self):
        if len(self.fps) == 0:
            return 0.0
        else:
            return sum(self.fps) / len(self.fps)

class ValueState:
    def __init__(self, value):
        self.value = value
        self.enabled = True

    def GetValue(self):
        return self.value

    def SetValue(self, value):
        self.value = value

    def Enable(self, enabled: bool = True):
        self.enabled = bool(enabled)

    def IsEnabled(self) -> bool:
        return self.enabled

class SelectionState:
    def __init__(self, selection: int, count: int):
        self.selection = max(0, min(count - 1, int(selection))) if count > 0 else 0
        self.count = max(0, int(count))
        self.enabled = True

    def GetSelection(self) -> int:
        return self.selection

    def SetSelection(self, selection: int):
        if self.count <= 0:
            self.selection = 0
        else:
            self.selection = max(0, min(self.count - 1, int(selection)))

    def GetCount(self) -> int:
        return self.count

    def Enable(self, enabled: bool = True):
        self.enabled = bool(enabled)

    def IsEnabled(self) -> bool:
        return self.enabled


_APP_WX_ICON_BUNDLE: Optional["wx.IconBundle"] = None
_APP_WX_ICON_BUNDLE_LOADED = False


def get_app_icon_bundle() -> Optional["wx.IconBundle"]:
    """Cached wx.IconBundle built from the bundled .ico (same artwork as the
    packaged exe), or None when the icon isn't deployed. Loaded once and reused
    so every top-level window shares the exe logo in the taskbar."""
    global _APP_WX_ICON_BUNDLE, _APP_WX_ICON_BUNDLE_LOADED
    if _APP_WX_ICON_BUNDLE_LOADED:
        return _APP_WX_ICON_BUNDLE
    _APP_WX_ICON_BUNDLE_LOADED = True
    try:
        path = _resolve_app_icon_path()
        if path and os.path.isfile(path):
            bundle = wx.IconBundle(path, wx.BITMAP_TYPE_ICO)
            if bundle.GetIconCount() > 0:
                _APP_WX_ICON_BUNDLE = bundle
    except Exception:
        _APP_WX_ICON_BUNDLE = None
    return _APP_WX_ICON_BUNDLE


def apply_app_icon(window: "wx.TopLevelWindow") -> None:
    """Apply the shared exe logo to a top-level window's taskbar label. Safe to
    call on any wx.Frame/wx.Dialog; no-ops when the icon isn't available."""
    if window is None:
        return
    bundle = get_app_icon_bundle()
    if bundle is None:
        return
    try:
        window.SetIcons(bundle)
    except Exception:
        pass


APP_USER_MODEL_ID = "EasyVtuberStudio.FacePuppeteer"


def set_windows_app_user_model_id() -> None:
    """Give the process its own Windows taskbar identity so the taskbar uses our
    window icons instead of the host python.exe icon. Must run BEFORE any
    top-level window is created. No-op off Windows."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            ctypes.c_wchar_p(APP_USER_MODEL_ID))
    except Exception:
        pass


class OutputFrame(wx.Frame):
    def __init__(self, owner_main_frame: "MainFrame"):
        super().__init__(None, wx.ID_ANY, "THA4 Output / 输出", style=wx.BORDER_NONE)
        apply_app_icon(self)
        self.owner_main_frame = owner_main_frame
        self._dragging = False
        self._drag_start_screen = wx.Point(0, 0)
        self._drag_start_frame = wx.Point(0, 0)
        self.SetDoubleBuffered(True)
        self.output_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.output_sizer)
        self.SetAutoLayout(1)

        locked_w, locked_h = owner_main_frame.get_locked_output_client_size()
        self.result_image_panel = wx.Panel(
            self, size=(locked_w, locked_h), style=wx.BORDER_NONE)
        self.result_image_panel.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.result_image_panel.SetDoubleBuffered(True)
        self.result_image_panel.Bind(wx.EVT_PAINT, self.paint_result_image_panel)
        self.result_image_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)
        self.result_image_panel.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.result_image_panel.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.result_image_panel.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.output_sizer.Add(self.result_image_panel, 0, wx.ALL, 0)

        locked_size = wx.Size(locked_w, locked_h)
        self.SetMinClientSize(locked_size)
        self.SetMaxClientSize(locked_size)
        self.SetSizeHints(locked_w, locked_h, locked_w, locked_h, locked_w, locked_h)
        self.SetClientSize(locked_size)
        self.owner_main_frame.refresh_output_frame_chrome()
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_MOVE, self.on_move)
        self.Bind(wx.EVT_ACTIVATE, self.on_activate)

    def on_activate(self, event: wx.Event):
        self.owner_main_frame.on_window_activate_for_layer_selection(event, self)
        event.Skip()

    def on_erase_background(self, event: wx.Event):
        pass

    def paint_result_image_panel(self, event: wx.Event):
        owner = self.owner_main_frame
        dc = wx.AutoBufferedPaintDC(self.result_image_panel)
        # result_image_bitmap now carries only the transparent foreground
        # (character + layers + edit chrome); the mode background (color-key
        # black / solid colour / chosen image / transparent-capture grey) is
        # painted here and the foreground is alpha-blended on top. The same
        # transparent foreground feeds the true-transparent ULW capture window.
        owner.paint_output_background(dc, self.result_image_panel.GetClientSize())
        if owner.result_image_bitmap.IsOk():
            dc.DrawBitmap(
                owner.result_image_bitmap,
                0,
                0,
                True)

    def on_close(self, event: wx.Event):
        if getattr(self.owner_main_frame, "_is_closing", False):
            self.Destroy()
            event.Skip()
            return

        self.owner_main_frame.Close()
        event.Veto()

    def on_size(self, event: wx.Event):
        locked_w, locked_h = self.owner_main_frame.get_locked_output_client_size()
        locked_size = wx.Size(locked_w, locked_h)
        if self.GetClientSize() != locked_size:
            self.SetClientSize(locked_size)
        event.Skip()

    def on_move(self, event: wx.Event):
        self.owner_main_frame.schedule_output_frame_geometry_sync(redraw=False)
        event.Skip()

    def on_left_down(self, event: wx.MouseEvent):
        if self.owner_main_frame.on_output_panel_left_down(event, self.result_image_panel):
            event.Skip()
            return
        self._dragging = True
        self._drag_start_screen = self.ClientToScreen(event.GetPosition())
        self._drag_start_frame = self.GetPosition()
        if not self.result_image_panel.HasCapture():
            self.result_image_panel.CaptureMouse()
        event.Skip()

    def on_left_up(self, event: wx.MouseEvent):
        if self.owner_main_frame.on_output_panel_left_up(event, self.result_image_panel):
            event.Skip()
            return
        self._dragging = False
        if self.result_image_panel.HasCapture():
            self.result_image_panel.ReleaseMouse()
        self.owner_main_frame.schedule_output_frame_geometry_sync(redraw=False)
        event.Skip()

    def on_mouse_move(self, event: wx.MouseEvent):
        if self.owner_main_frame.on_output_panel_motion(event, self.result_image_panel):
            event.Skip()
            return
        if self._dragging and event.LeftIsDown():
            current_screen = self.ClientToScreen(event.GetPosition())
            delta = current_screen - self._drag_start_screen
            self.Move(self._drag_start_frame + delta)
        event.Skip()

class ControlsFrame(wx.Frame):
    def __init__(self, owner_main_frame: "MainFrame"):
        super().__init__(None, wx.ID_ANY, "EasyVtuberStudio")
        apply_app_icon(self)
        self.owner_main_frame = owner_main_frame
        self.SetDoubleBuffered(True)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_SIZE, self.on_geometry_changed)
        self.Bind(wx.EVT_MOVE, self.on_geometry_changed)
        self.Bind(wx.EVT_ACTIVATE, self.on_activate)
        self.Bind(wx.EVT_SHOW, self.on_show)

    def on_show(self, event: wx.ShowEvent):
        if event.IsShown():
            if not getattr(self, "_controls_first_idle_bound", False):
                self._controls_first_idle_bound = True
                self.Bind(wx.EVT_IDLE, self.on_first_idle)
            self.owner_main_frame.on_controls_frame_shown()
        event.Skip()

    def on_first_idle(self, event: wx.Event):
        self.Unbind(wx.EVT_IDLE, handler=self.on_first_idle)
        self.owner_main_frame.on_controls_first_idle()

    def on_geometry_changed(self, event: wx.Event):
        if isinstance(event, wx.SizeEvent):
            wx.CallAfter(self.owner_main_frame.handle_controls_frame_resized)
        elif isinstance(event, wx.MoveEvent):
            wx.CallAfter(self.owner_main_frame.on_controls_frame_moved)
        self.owner_main_frame.schedule_window_geometry_save()
        event.Skip()

    def on_activate(self, event: wx.Event):
        self.owner_main_frame.on_window_activate_for_layer_selection(event, self)
        event.Skip()

    def on_close(self, event: wx.Event):
        if getattr(self.owner_main_frame, "_is_closing", False):
            self.Destroy()
            event.Skip()
            return
        self.owner_main_frame.Close()
        event.Veto()

class WebcamPreviewPopupFrame(wx.Frame):
    POPUP_PREVIEW_SIZE = 640

    def __init__(self, owner_main_frame: "MainFrame"):
        super().__init__(None, wx.ID_ANY, "Webcam Preview / 摄像头预览")
        apply_app_icon(self)
        self.owner_main_frame = owner_main_frame
        self.SetDoubleBuffered(True)

        popup_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(popup_sizer)
        self.SetAutoLayout(1)

        popup_side = WebcamPreviewPopupFrame.POPUP_PREVIEW_SIZE
        self.preview_panel = wx.Panel(
            self,
            size=(popup_side, popup_side),
            style=wx.SIMPLE_BORDER)
        self.preview_panel.SetBackgroundColour(MainFrame.PREVIEW_IDLE_BACKGROUND)
        self.preview_panel.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.preview_panel.SetDoubleBuffered(True)
        self.preview_panel.Bind(wx.EVT_PAINT, self.on_paint_preview_panel)
        self.preview_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)
        self.preview_panel.Bind(wx.EVT_LEFT_DCLICK, self.on_preview_double_click)
        popup_sizer.Add(self.preview_panel, 1, wx.EXPAND | wx.ALL, 8)

        hint_text = wx.StaticText(
            self,
            label="双击预览区关闭 / Double-click preview to close",
            style=wx.ALIGN_CENTER_HORIZONTAL)
        popup_sizer.Add(hint_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        popup_sizer.Fit(self)
        fitted_size = popup_sizer.GetMinSize()
        self.SetClientSize(fitted_size)
        self.SetMinClientSize(fitted_size)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_ACTIVATE, self.on_activate)

    def on_activate(self, event: wx.Event):
        self.owner_main_frame.on_window_activate_for_layer_selection(event, self)
        event.Skip()

    @staticmethod
    def on_erase_background(event: wx.Event):
        pass

    def on_paint_preview_panel(self, event: wx.Event):
        panel = self.preview_panel
        panel_size = panel.GetClientSize()
        if panel_size.x <= 0 or panel_size.y <= 0:
            return
        dc = wx.BufferedPaintDC(panel)
        dc.SetBackground(wx.Brush(MainFrame.PREVIEW_IDLE_BACKGROUND))
        dc.SetBackgroundMode(wx.SOLID)
        dc.Clear()
        source_bitmap = self.owner_main_frame.webcam_capture_bitmap
        if not source_bitmap.IsOk():
            return
        source_size = source_bitmap.GetSize()
        if source_size.x <= 0 or source_size.y <= 0:
            return
        viewport_side = min(panel_size.x, panel_size.y)
        scale = viewport_side / max(1, source_size.x)
        draw_w = max(1, int(source_size.x * scale))
        draw_h = max(1, int(source_size.y * scale))
        draw_x = (panel_size.x - draw_w) // 2
        draw_y = (panel_size.y - draw_h) // 2
        dc.DrawBitmap(source_bitmap, draw_x, draw_y, True)

    def on_preview_double_click(self, event: wx.MouseEvent):
        self.Close()
        event.Skip()

    def on_close(self, event: wx.Event):
        self.owner_main_frame.webcam_preview_popup_frame = None
        self.Destroy()
        event.Skip()


class MainFrame(wx.Frame):
    IMAGE_SIZE = 512
    SOURCE_PREVIEW_SIZE = 192
    WEBCAM_PREVIEW_SIZE = 192
    MAX_CAMERA_PROBE_INDEX = 19
    VIDEO_SOURCE_COLUMN_MIN_WIDTH = 260
    PREVIEW_CALIBRATION_COLUMN_MIN_WIDTH = 220
    CAPTURE_PANEL_MIN_WIDTH = (
        SOURCE_PREVIEW_SIZE + 24
        + WEBCAM_PREVIEW_SIZE + 24
        + PREVIEW_CALIBRATION_COLUMN_MIN_WIDTH + 24)
    CAPTURE_PANEL_MIN_HEIGHT = (
        max(SOURCE_PREVIEW_SIZE + 108, WEBCAM_PREVIEW_SIZE + 72) + 12 + 72)
    PREVIEW_IDLE_BACKGROUND = wx.Colour(0, 0, 0)
    # Shared minimum for both panes in right_sidebar_splitter (preview / postprocess).
    RIGHT_SIDEBAR_PANE_MIN_HEIGHT = 140
    RIGHT_SIDEBAR_MIN_WIDTH = CAPTURE_PANEL_MIN_WIDTH
    CONTROLS_COLUMN_MIN_WIDTH = 200
    CONTROLS_TWO_COLUMN_MIN_WIDTH = CONTROLS_COLUMN_MIN_WIDTH * 2
    # Default layout: three equal-width columns (B model input | C dynamic | D preview+post).
    # Structurally: main_splitter = left (B+C) 2/3 + right (D) 1/3; animation_splitter splits B|C 50/50.
    CONTROLS_LAYOUT_THIRD_COUNT = 3
    POSTPROCESS_H_PADDING = 8
    DEFAULT_OUTPUT_SIZE = int(IMAGE_SIZE * 1.5)
    LOCKED_OUTPUT_CLIENT_WIDTH = DEFAULT_OUTPUT_SIZE
    LOCKED_OUTPUT_CLIENT_HEIGHT = DEFAULT_OUTPUT_SIZE
    LOAD_PREVIEW_BANNER = "DEFAULT POSE (model loaded)"
    AUTO_TRANSFORM_HOLD_SECONDS = 0.75
    SCALE_CURVE_DELTA_RANGE = 0.22
    UI_STATE_FILE_NAME = "load_preview_ui_state.json"
    CONTROLS_MIN_CLIENT_WIDTH = max(
        720,
        CONTROLS_TWO_COLUMN_MIN_WIDTH + RIGHT_SIDEBAR_MIN_WIDTH + 48)
    CONTROLS_MIN_CLIENT_HEIGHT = 480
    # Height cap comes from the display work area (portrait / multi-monitor), not a fixed pixel limit.
    CONTROLS_MAX_CLIENT_HEIGHT = 32000
    COMPACT_MIN_CLIENT_WIDTH = 260
    COMPACT_MIN_CLIENT_HEIGHT = 180
    CAPTURE_PROCESS_INTERVAL_MS = 66
    CAPTURE_PREVIEW_INTERVAL_MS = 66
    CAPTURE_IDLE_INTERVAL_MS = 400
    DISPLAY_PRESENT_INTERVAL_MS = 30
    DISPLAY_PRESENT_CAP_HZ = 30
    OUTPUT_FPS_AVG_FRAME_COUNT = 5
    OUTPUT_FPS_UPDATE_INTERVAL_SEC = 1.0
    OUTPUT_FPS_STALE_SEC = 1.5
    MIN_OUT_PRESENT_HZ = 12
    HOVER_HELP_DELAY_MS = 1000
    MEDIAPIPE_MIN_INTERVAL_MS = 33
    WINDOW_CAPTURE_MOCAP_MAX_EDGE = 1280
    WINDOW_CAPTURE_STALL_SEC = 0.35
    WINDOW_CAPTURE_MEDIAPIPE_INTERVAL_MS = 50
    # Shared cadence for continuously-refreshing animated UI in the controls and
    # layer windows (FPS text, scale-curve preview, spine diagram): 40ms = 25 fps,
    # within the 20-30 fps band. The output window is NOT throttled by this.
    UI_ANIM_REFRESH_INTERVAL_MS = 40
    VIDEO_FILE_EXTENSIONS = (
        ".mp4", ".avi", ".mov", ".mkv", ".webm", ".wmv", ".m4v", ".mpeg", ".mpg",
        ".flv", ".ts", ".mts", ".m2ts", ".3gp", ".ogv", ".divx", ".asf", ".vob",
    )
    IMAGE_FILE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff")
    VIDEO_FILE_WILDCARD = (
        "All supported|*.mp4;*.avi;*.mov;*.mkv;*.webm;*.wmv;*.m4v;*.mpeg;*.mpg;"
        "*.flv;*.ts;*.mts;*.m2ts;*.3gp;*.ogv;*.divx;*.asf;*.vob;"
        "*.png;*.jpg;*.jpeg;*.bmp;*.webp;*.tif;*.tiff|"
        "Common video|*.mp4;*.avi;*.mov;*.mkv;*.webm;*.wmv;*.m4v;*.mpeg;*.mpg;"
        "*.flv;*.ts;*.mts;*.m2ts;*.3gp;*.ogv;*.divx;*.asf;*.vob|"
        "Images|*.png;*.jpg;*.jpeg;*.bmp;*.webp;*.tif;*.tiff|"
        "MP4 (*.mp4)|*.mp4|AVI (*.avi)|*.avi|MOV (*.mov)|*.mov|MKV (*.mkv)|*.mkv|"
        "WEBM (*.webm)|*.webm|WMV (*.wmv)|*.wmv|All files (*.*)|*.*")

    def __init__(self,
                 pose_converter: MediaPoseFacePoseConverter00,
                 video_capture,
                 face_landmarker,
                 device: torch.device):
        self._startup_init_t0 = time.perf_counter()
        super().__init__(None, wx.ID_ANY, "EasyVtuberStudio")
        apply_app_icon(self)
        self.face_landmarker = face_landmarker
        self.video_capture = video_capture
        self.pose_converter = pose_converter
        self.device = device

        self.source_image_bitmap = wx.Bitmap(MainFrame.SOURCE_PREVIEW_SIZE, MainFrame.SOURCE_PREVIEW_SIZE)
        self.result_image_bitmap = wx.Bitmap(1, 1)
        self.webcam_capture_bitmap = wx.Bitmap(
            MainFrame.WEBCAM_PREVIEW_SIZE, MainFrame.WEBCAM_PREVIEW_SIZE)
        # Video source handling (camera not connected -> show error instead of generic "Nothing yet!").
        self.video_capture_status_message: Optional[str] = None
        self.video_source_choice_map: dict[str, tuple[str, object, object]] = {}
        self.video_source_choice: Optional[wx.Choice] = None
        self.webcam_container: Optional[wx.Panel] = None
        self.webcam_preview_popup_frame: Optional[WebcamPreviewPopupFrame] = None
        self.current_video_capture_api: Optional[int] = None
        self.video_source_status_text: Optional[wx.StaticText] = None
        self.last_window_capture_text: Optional[wx.StaticText] = None
        self.video_source_kind = "none"
        self._image_file_path: Optional[str] = None
        self._window_capture_hwnd: Optional[int] = None
        self._window_capture_title: Optional[str] = None
        self._window_capture_lock = threading.Lock()
        self._window_capture_latest_frame = None
        self._window_capture_frame_serial = 0
        self._last_mediapipe_capture_serial = -1
        self._window_capture_worker_active = False
        self._last_good_webcam_bgr_frame = None
        self._capture_frame_serial = 0
        self._last_mediapipe_process_time = 0.0
        self._mediapipe_video_timestamp_ms: Optional[int] = None
        self._mediapipe_detect_error_logged = False
        self._last_preview_ui_time = 0.0
        self._video_enumeration_in_progress = False
        self._startup_auto_connect_attempted = False
        self._startup_full_controls_shown = False
        self._defer_heavy_ui_refresh = True
        self._window_invalid_autoswitch_attempted = False
        self.rotation_labels = {}
        self.rotation_value_labels = {}
        self.wx_source_image = None
        self.torch_source_image = None
        self.last_pose = None
        self.mediapipe_face_pose = None
        self._input_frame_times: List[float] = []
        self._input_fps = 0.0
        self._inference_complete_times: List[float] = []
        self._inference_fps = 0.0
        self._last_actual_output_present_mono: Optional[float] = None
        self._output_present_times: List[float] = []
        self._output_fps_last_commit_mono: float = 0.0
        self._display_out_fps = 0.0
        self._user_change_history = UserChangeHistory(3)
        self._ui_change_log_wired = False
        self._last_compose_signature: Optional[tuple] = None
        self._last_transform_status_refresh_time = 0.0
        self._last_chrome_background_signature: Optional[str] = None
        self._cached_background_signature: Optional[str] = None
        self._cached_background_rgba: Optional[numpy.ndarray] = None
        self._cached_capture_foreground_rgba: Optional[numpy.ndarray] = None
        self._cached_capture_foreground_signature: Optional[tuple] = None
        self.last_update_time = None
        self.character_model = None
        self.poser = None
        self._default_mediapipe_face_pose = make_neutral_mediapipe_face_pose()
        self._default_pose_list: Optional[List[float]] = None
        self._load_preview_shown = False
        self.last_output_wx_image: Optional[wx.Image] = None
        self.last_banner_text: Optional[str] = None
        self.last_background_choice = "#000000"
        self.latest_face_screen_motion: Optional[FaceScreenMotion] = None
        self.neutral_face_screen_motion: Optional[FaceScreenMotion] = None
        self.latest_head_roll_deg: Optional[float] = None
        self.neutral_head_roll_deg = 0.0
        self.last_face_detected_time: Optional[float] = None
        self.mocap_input_mode = MOCAP_INPUT_MODE_MOUSE_AUDIO
        self._mouth_input_mode_before_mouse_audio: Optional[str] = None
        self._mouse_mocap_config = MouseMocapConfig()
        self._face_landmarker_init_failed = False
        self._mouse_mocap_fallback_done = False
        self._last_mouse_mocap_nx = 0.0
        self._last_mouse_mocap_ny = 0.0
        self.last_mouse_calibration_time: Optional[float] = None
        self._enable_mouse_auto_calibration = False
        self._mouse_auto_calibration_interval_seconds = 300.0
        self.last_direction_calibration_time: Optional[float] = None
        self.last_scale_calibration_time: Optional[float] = None
        self.display_offset_x = 0.0
        self.display_offset_y = 0.0
        self.display_scale = 1.0
        self.display_rotation_deg = 0.0
        self._is_closing = False
        self._output_geometry_sync_pending = False
        self._output_geometry_redraw_pending = False
        self._last_scale_curve_refresh_time = 0.0
        self._last_scale_curve_preview_time_ns: Optional[int] = None
        self._last_scale_curve_signature = None
        self._last_pose_infer_time_ns: Optional[int] = None
        self._last_cached_affine_present_time_ns: Optional[int] = None
        self._last_capture_present_time_ns: Optional[int] = None
        self._last_spine_diagram_refresh_time_ns: Optional[int] = None
        self._infer_lock = threading.Lock()
        self._pending_infer_pose: Optional[List[float]] = None
        self._infer_worker_active = False
        # MediaPipe face detection runs on a dedicated worker thread (latest-wins)
        # so the heavy detect_for_video call never blocks the wx UI/render thread.
        self._mediapipe_lock = threading.Lock()
        self._pending_mediapipe_job: Optional[tuple] = None
        self._mediapipe_worker_active = False
        # Dirty flag so the animated-UI timer only repaints the scale-curve preview
        # when its underlying value actually changed.
        self._scale_curve_dirty = False
        self._capture_geometry_save_pending = False
        self._capture_update_pending = False
        self._capture_async_active = False
        self.transparent_capture_window: Optional[TransparentCaptureWindow] = None
        self._creating_transparent_capture_window = False
        self._startup_autofit_pending = False
        self._controls_geometry_restored = False
        self._compact_geometry_restored = False
        self._live_main_splitter_ratio: Optional[float] = None
        self._live_animation_splitter_ratio: Optional[float] = None
        self._live_right_sidebar_splitter_ratio: Optional[float] = None
        self._controls_fixed_client_width: Optional[int] = None
        self._scroll_refresh_pending = False
        self._dynamic_output_layout_pending = False
        self._dynamic_output_layout_in_progress = False
        self._model_input_layout_timer = None
        self._dynamic_output_layout_timer = None
        self._postprocess_layout_timer = None
        self._postprocess_layout_pending = False
        self._postprocess_layout_in_progress = False
        self._responsive_text_layout_pending = False
        self._controls_build_in_progress = False
        self._applying_persisted_controls_layout_depth = 0
        self._active_save_caller: Optional[str] = None
        self._restoring_window_geometry = False
        self._window_geometry_save_pending = False
        self._window_geometry_save_timer = None
        self._controls_frame_layout_timer = None
        self._controls_window_bounds_timer = None
        self._hover_help_pending_window: Optional[wx.Window] = None
        self._hover_help_active_window: Optional[wx.Window] = None
        self.last_loaded_model_path: Optional[str] = None
        self.full_controls_expanded = False
        self.controls_frame: Optional[ControlsFrame] = None
        self.persistent_ui_state = self.load_persistent_ui_state()
        self.apply_bundled_default_model_paths_if_missing()
        self._seed_live_splitter_ratios_from_persistent()
        self.mocap_input_mode = normalize_mocap_input_mode(
            self.persistent_ui_state.get("mocap_input_mode", MOCAP_INPUT_MODE_MOUSE_AUDIO))
        if (self.mocap_input_mode != MOCAP_INPUT_MODE_MOUSE_AUDIO
                and not face_capture_assets_ready(get_portable_root())):
            self.mocap_input_mode = MOCAP_INPUT_MODE_MOUSE_AUDIO
            self.persistent_ui_state["mocap_input_mode"] = MOCAP_INPUT_MODE_MOUSE_AUDIO
        self._load_mouse_mocap_settings_from_persistent(self.persistent_ui_state)
        self.basic_layers_state = load_basic_layers_state(
            self.get_ui_state_file_path(),
            self.resolve_layer_asset_path)
        layer_migrated = migrate_layer_bind_ray_percents(
            self.basic_layers_state,
            migrate_bind_ray_percent_from_state(
                self.persistent_ui_state,
                percent_key="spine_body_bind_ray_percent",
                legacy_ratio_key="spine_body_bind_ray_t",
                default=BIND_RAY_PERCENT_DEFAULT),
            migrate_bind_ray_percent_from_state(
                self.persistent_ui_state,
                percent_key="spine_head_bind_ray_percent",
                legacy_ratio_key="spine_head_bind_ray_t",
                default=BIND_RAY_PERCENT_DEFAULT))
        layer_migrated = migrate_layer_bind_neck_ratios(
            self.basic_layers_state,
            self.get_spine_neck_anchor_ratio()) or layer_migrated
        if layer_migrated:
            self.persist_basic_layers_state()
        self.layer_asset_cache = LayerAssetCache(self.resolve_layer_asset_path)
        self.layer_binding_smoother = LayerBindingSmoother()
        self.head_binding_pose_filter = HeadBindingPoseFilter()
        self._source_preview_cache_key: Optional[tuple] = None
        self._source_preview_scaled_key: Optional[tuple] = None
        self._source_preview_scaled_bitmap = None
        self.basic_layer_window = None
        self._layer_drag_active = False
        self._layer_drag_slot_id: Optional[int] = None
        self._layer_drag_last_pos: Optional[tuple[int, int]] = None
        self._layer_drag_canvas_size: tuple[int, int] = (1, 1)
        self._layer_edit_mode = LayerEditMode.NONE
        self._layer_edit_panel: Optional[wx.Window] = None
        # (slot_id, ResolvedLayerRect, rotation_deg, canvas_w, canvas_h) of the
        # last selection chrome drawn; used so the layered-output hit-test
        # matches the on-screen highlight box exactly.
        self._last_edit_chrome_geom: Optional[tuple] = None
        self._suppress_layer_deselect = False
        self._output_background_image_cache_key = None
        self._output_background_image_cache = None
        self._result_bitmap_alpha = None
        self.image_source_mode = normalize_image_source_mode(
            self.persistent_ui_state.get("image_source_mode", IMAGE_SOURCE_THA4))
        tha3_png = self.persistent_ui_state.get("tha3_character_png")
        self.last_tha3_character_png = tha3_png if isinstance(tha3_png, str) else None
        self.tha3_model_variant = str(
            self.persistent_ui_state.get("tha3_model_variant", "separable_half"))
        self.active_image_source = create_image_source(self.image_source_mode)
        self.output_enhancement = OutputEnhancementRuntime(
            repo_root=find_repo_root() or get_portable_root())
        self.output_enhancement.update_config(self.persistent_ui_state)
        self.apply_mouth_persistent_state_to_args()
        if self.is_mouse_audio_mocap_mode():
            self.pose_converter.args.set_mouth_input_mode("audio")
        self.SetDoubleBuffered(True)
        self.Bind(wx.EVT_ACTIVATE, self._on_main_frame_activate)
        self.Bind(wx.EVT_CHAR_HOOK, self.on_layer_char_hook)
        self.initialize_headless_control_state()

        self.output_frame = None
        self.create_ui()
        self._layer_hotkey_refresh_pending = False
        self.layer_hotkey_registry: Optional[LayerHotkeyRegistry] = None
        self._layer_hotkey_evt_bound = False
        self.apply_persistent_ui_state()
        self.restore_compact_frame_geometry()
        self.refresh_model_loaded_ui_state()
        self.create_timers()
        self._init_ui_alignment_monitor()
        if self.is_mouse_audio_mocap_mode():
            self.schedule_active_capture_timer()
        self.active_image_source.start(self)
        self.refresh_image_source_ui_visibility()
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_SIZE, self.on_compact_geometry_changed)
        self.Bind(wx.EVT_MOVE, self.on_compact_geometry_changed)

        self.update_source_image_bitmap()
        _startup_record(
            "MainFrame.__init__ (constructor, before MainLoop)",
            (time.perf_counter() - self._startup_init_t0) * 1000.0)
        wx.CallAfter(self.startup_show_full_controls)

    def startup_show_full_controls(self):
        if self._startup_full_controls_shown:
            return
        self._startup_full_controls_shown = True
        startup_t0 = time.perf_counter()
        self.show_full_controls_window()
        first_present_t0 = time.perf_counter()
        self.update_result_image_bitmap()
        _startup_record(
            "first present+infer (update_result_image_bitmap)",
            (time.perf_counter() - first_present_t0) * 1000.0)
        wx.CallAfter(self.ensure_application_windows_visible)
        self.schedule_refresh_controls_scrolling()
        wx.CallLater(1200, self.autoconnect_video_source_on_startup)
        wx.CallAfter(self._ensure_tha3_assets_on_startup)
        wx.CallAfter(self.sync_layer_hotkey_registry)
        self._defer_heavy_ui_refresh = False
        _startup_record(
            "startup_show_full_controls (UI ready)",
            (time.perf_counter() - startup_t0) * 1000.0)

    def _ensure_tha3_assets_on_startup(self):
        if self.get_image_source_mode() != IMAGE_SOURCE_THA3:
            return
        from tha3_assets_prompt import ensure_tha3_assets_available

        if ensure_tha3_assets_available(self, self.tha3_model_variant):
            return
        switch_image_source(self, IMAGE_SOURCE_THA4, autoload_asset=True)

    def try_startup_auto_connect_camera(self):
        self.autoconnect_video_source_on_startup()

    def get_default_pose_list(self) -> List[float]:
        if self._default_pose_list is None:
            self._default_pose_list = self.pose_converter.convert(self._default_mediapipe_face_pose)
        return self._default_pose_list

    def create_timers(self):
        self.capture_timer = wx.Timer(self, wx.ID_ANY)
        self.Bind(wx.EVT_TIMER, self.update_capture_panel, id=self.capture_timer.GetId())
        self.display_timer = wx.Timer(self, wx.ID_ANY)
        self.Bind(wx.EVT_TIMER, self.on_display_timer, id=self.display_timer.GetId())
        self.animation_timer = wx.Timer(self, wx.ID_ANY)
        self.Bind(wx.EVT_TIMER, self.on_infer_tick, id=self.animation_timer.GetId())
        self.ui_anim_timer = wx.Timer(self, wx.ID_ANY)
        self.Bind(wx.EVT_TIMER, self.on_ui_anim_timer, id=self.ui_anim_timer.GetId())

    def initialize_headless_control_state(self):
        self.enable_auto_transform_checkbox = ValueState(True)
        self.move_x_gain_spin = ValueState(140.0)
        self.move_y_gain_spin = ValueState(0.0)
        self.scale_gain_spin = ValueState(6.0)
        self.min_scale_spin = ValueState(0.70)
        self.max_scale_spin = ValueState(0.90)
        self.tilt_limit_spin = ValueState(10.0)
        self.smoothing_spin = ValueState(0.82)
        self.invert_tilt_mapping_checkbox = ValueState(False)
        self.scale_curve_near_spin = ValueState(1.35)
        self.scale_curve_far_spin = ValueState(0.90)
        self.scale_curve_arc_spin = ValueState(1.10)
        self.scale_curve_peak_shift_spin = ValueState(0.00)
        self.enable_direction_calibration_checkbox = ValueState(True)
        self.auto_direction_calibration_interval_seconds_ctrl = ValueState(300.0)
        self.enable_scale_calibration_checkbox = ValueState(True)
        self.auto_scale_calibration_interval_seconds_ctrl = ValueState(300.0)
        persisted = self.persistent_ui_state
        self.output_background_choice = ValueState(
            self.resolve_persistent_output_background_hex(persisted))
        self.output_background_mode_choice = ValueState(
            self.resolve_persistent_output_background_mode(persisted))
        self.output_background_image_path_state = ValueState(
            self.resolve_persistent_output_background_image_path(persisted))
        self._layer_blend_enabled_state = ValueState(False)
        self._layer_hotkeys_enabled_state = ValueState(
            bool(persisted.get("layer_hotkeys_enabled", False)))
        self._layer_force_full_follow_state = ValueState(False)
        self._invert_tilt_mapping_state = ValueState(True)
        self.antialias_strength_spin = ValueState(1.00)
        self.character_edge_mode_state = ValueState(CHARACTER_EDGE_NONE)
        self.character_edge_width_state = ValueState(float(CHARACTER_EDGE_WIDTH_DEFAULT))
        self.character_edge_color_hex_state = ValueState("#FFFFFF")
        self.output_frame_interpolation_choice = ValueState(POSE_FRAME_INTERP_OFF)
        self.nn_super_resolution_choice = ValueState(NN_SR_OFF)
        self.nn_frame_interpolation_choice = ValueState(NN_FRAME_INTERP_OFF)
        self.nn_infer_backend_choice = ValueState(
            normalize_infer_backend(
                persisted.get("nn_infer_backend", INFER_BACKEND_PYTORCH)))
        tha_raw = persisted.get("tha_infer_fp16", "full")
        self.tha_infer_fp16_choice = ValueState(
            THA_INFER_FP16_CHOICES[1 if normalize_tha_infer_fp16(tha_raw) else 0])
        self._tha_infer_fp16_fallback = False
        self._enhancement_warned_once = False
        self._enhancement_warmup_key = None

    @staticmethod
    def _wx_control_alive(control) -> bool:
        if control is None:
            return False
        if not isinstance(control, wx.Window):
            return False
        try:
            if hasattr(control, "IsDestroyed") and control.IsDestroyed():
                return False
            control.GetHandle()
            return True
        except (RuntimeError, AttributeError):
            return False

    def _safe_checkbox_value(self, wx_attr: str, state: ValueState, default: bool = False) -> bool:
        control = getattr(self, wx_attr, None)
        if self._wx_control_alive(control):
            try:
                value = bool(control.GetValue())
                state.SetValue(value)
                return value
            except (RuntimeError, AttributeError):
                pass
        try:
            return bool(state.GetValue())
        except Exception:
            return default

    def _basic_layer_window_visible(self) -> bool:
        window = self._get_basic_layer_window()
        if window is None:
            return False
        try:
            return bool(window.IsShown())
        except (RuntimeError, AttributeError):
            return False

    def _get_basic_layer_window(self) -> Optional[wx.Frame]:
        window = getattr(self, "basic_layer_window", None)
        if not self._wx_control_alive(window):
            self.basic_layer_window = None
            return None
        return window

    def is_layer_blend_enabled(self) -> bool:
        return self._safe_checkbox_value(
            "layer_blend_enabled_checkbox", self._layer_blend_enabled_state, default=False)

    def is_layer_hotkeys_enabled(self) -> bool:
        if not self.is_layer_blend_enabled():
            return False
        return self._safe_checkbox_value(
            "layer_hotkeys_enabled_checkbox",
            self._layer_hotkeys_enabled_state,
            default=False)

    def is_layer_force_full_follow_enabled(self) -> bool:
        return self._safe_checkbox_value(
            "layer_force_full_follow_checkbox",
            self._layer_force_full_follow_state,
            default=False)

    def is_body_tilt_opposite_to_head_enabled(self) -> bool:
        """Body segment tilt opposite to head segment (model body_z vs neck_z, spine lower vs upper)."""
        return self._safe_checkbox_value(
            "invert_tilt_mapping_checkbox", self._invert_tilt_mapping_state, default=True)

    def is_invert_tilt_mapping_enabled(self) -> bool:
        return self.is_body_tilt_opposite_to_head_enabled()

    def apply_invert_tilt_mapping_to_pose(self, pose: List[float]) -> List[float]:
        converter = getattr(self, "pose_converter", None)
        if converter is None:
            return pose
        return apply_body_head_tilt_opposite_to_pose(
            pose,
            neck_z_index=converter.neck_z_index,
            body_z_index=converter.body_z_index,
            opposite=self.is_body_tilt_opposite_to_head_enabled())

    def _resolve_mocap_pose_for_render(self, mediapipe_face_pose) -> List[float]:
        current_pose = self.pose_converter.convert(mediapipe_face_pose)
        current_pose = self.apply_negative_tilt_limit_to_pose(current_pose)
        return self.apply_invert_tilt_mapping_to_pose(current_pose)

    def _refresh_pose_after_tilt_mapping_changed(self) -> None:
        self._invalidate_render_caches()
        self._last_compose_signature = None
        if self.mediapipe_face_pose is None or not self.is_model_loaded():
            return
        current_pose = self._resolve_mocap_pose_for_render(self.mediapipe_face_pose)
        infer_pose = self.resolve_scheduled_infer_pose(current_pose)
        self.schedule_async_pose_infer(infer_pose)

    def _sync_layer_blend_state(self, event: Optional[wx.Event] = None) -> None:
        self._safe_checkbox_value("layer_blend_enabled_checkbox", self._layer_blend_enabled_state)
        if event is not None:
            event.Skip()

    def _collect_pose_binding_fields(self) -> tuple[float, float, float]:
        pose_head_x = 0.0
        pose_head_y = 0.0
        pose_neck_z = 0.0
        pose = self.last_pose
        converter = getattr(self, "pose_converter", None)
        if pose is not None and converter is not None:
            try:
                pose_head_x = float(pose[converter.head_x_index])
                pose_head_y = float(pose[converter.head_y_index])
                pose_neck_z = float(pose[converter.neck_z_index])
            except (IndexError, TypeError, ValueError, AttributeError):
                pass
        if not self._should_filter_head_binding_pose():
            return pose_head_x, pose_head_y, pose_neck_z
        return self.head_binding_pose_filter.filter(pose_head_x, pose_head_y, pose_neck_z)

    def _should_filter_head_binding_pose(self) -> bool:
        """Pose low-pass only when a bound layer uses smooth follow or extra mocap."""
        if not self.is_layer_blend_enabled():
            return False
        from layer_runtime import normalize_binding_target
        for layer in self.basic_layers_state.layers:
            if not layer.enabled or not layer.visible or not layer.asset_path:
                continue
            if normalize_binding_target(layer.binding_parent) is None:
                continue
            if layer.binding_follow_smooth:
                return True
            if layer.binding_follow_mocap_position or layer.binding_follow_mocap_roll:
                return True
        return False

    @staticmethod
    def resolve_character_model_path(path: Optional[str]) -> Optional[str]:
        if not path or not isinstance(path, str):
            return None
        normalized = path.strip()
        if not normalized:
            return None
        if os.path.isabs(normalized):
            return str(os.path.normpath(normalized))
        resolved = from_repo_relative(normalized)
        return str(os.path.normpath(resolved)) if resolved else None

    @staticmethod
    def get_default_character_models_dir() -> str:
        models_dir = find_repo_root() / "data" / "character_models"
        return str(models_dir)

    @staticmethod
    def resolve_layer_asset_path(asset_path: Optional[str]) -> Optional[str]:
        if not asset_path:
            return None
        if os.path.isabs(asset_path):
            if os.path.isfile(asset_path):
                return asset_path
            resolved = from_repo_relative(asset_path)
            if resolved and os.path.isfile(resolved):
                return resolved
            return None
        resolved = from_repo_relative(asset_path)
        if resolved and os.path.isfile(resolved):
            return resolved
        return None

    def relativize_path_for_persistence(self, path: str) -> str:
        return to_repo_relative(path)

    def persist_basic_layers_state(self) -> None:
        save_basic_layers_state(
            self.basic_layers_state,
            self.get_ui_state_file_path(),
            self.relativize_path_for_persistence)

    def _ensure_layer_hotkey_registry(self) -> Optional[LayerHotkeyRegistry]:
        if not self.is_layer_hotkeys_enabled():
            return None
        registry = getattr(self, "layer_hotkey_registry", None)
        if registry is None:
            registry = LayerHotkeyRegistry(self)
            self.layer_hotkey_registry = registry
            if hasattr(wx, "EVT_HOTKEY") and not self._layer_hotkey_evt_bound:
                self.Bind(wx.EVT_HOTKEY, self.on_layer_global_hotkey)
                self._layer_hotkey_evt_bound = True
        return registry

    def _teardown_layer_hotkeys(self) -> None:
        self._layer_hotkey_refresh_pending = False
        registry = getattr(self, "layer_hotkey_registry", None)
        if registry is not None:
            try:
                registry.clear()
            except Exception:
                pass
        self.layer_hotkey_registry = None

    def sync_layer_hotkey_registry(self) -> None:
        if not self.is_layer_hotkeys_enabled():
            self._teardown_layer_hotkeys()
            return
        registry = self._ensure_layer_hotkey_registry()
        if registry is None:
            return
        if wx.Platform == "__WXMSW__" and not self.GetHandle():
            wx.CallAfter(self.sync_layer_hotkey_registry)
            return
        registry.sync_from_state(
            self.basic_layers_state,
            enabled=True)
        failures = registry.failures
        registered = registry.registered_count
        if failures and hasattr(self, "layer_blend_status_text"):
            preview = failures[0]
            if len(failures) > 1:
                preview = f"{preview} (+{len(failures) - 1} more)"
            suffix = f"；已注册 {registered} 个" if registered else ""
            self.layer_blend_status_text.SetLabel(
                f"图层快捷键注册失败 / Layer hotkey failed: {preview}{suffix}")
        elif hasattr(self, "layer_blend_status_text"):
            self.refresh_layer_blend_status()

    def _schedule_layer_hotkey_visual_refresh(
            self,
            slot_ids: Optional[list[int]] = None) -> None:
        if getattr(self, "_is_closing", False):
            return
        self._layer_hotkey_refresh_slot_ids = (
            None if slot_ids is None
            else [int(sid) for sid in slot_ids])
        if self._layer_hotkey_refresh_pending:
            return
        self._layer_hotkey_refresh_pending = True
        wx.CallAfter(self._run_layer_hotkey_visual_refresh)

    def _run_layer_hotkey_visual_refresh(self) -> None:
        self._layer_hotkey_refresh_pending = False
        if getattr(self, "_is_closing", False):
            return
        slot_ids = getattr(self, "_layer_hotkey_refresh_slot_ids", None)
        self._layer_hotkey_refresh_slot_ids = None
        self.notify_layer_composite_dirty(immediate_capture=False)
        if slot_ids:
            for slot_id in slot_ids:
                self.refresh_layer_slot_ui(slot_id)

    def poll_layer_gif_playback_side_effects(self) -> None:
        if not self.is_layer_blend_enabled():
            return
        dirty_slot_ids = [
            layer.slot_id
            for layer in self.basic_layers_state.layers
            if layer._gif_playback_visibility_dirty]
        if not dirty_slot_ids:
            return
        if not consume_layer_gif_playback_visibility_dirty(self.basic_layers_state):
            return
        self.persist_basic_layers_state()
        self._schedule_layer_hotkey_visual_refresh(dirty_slot_ids)

    def apply_layer_hotkey_action(self, slot_id: int, action: str) -> bool:
        """External + global hotkey entry: toggle visibility or control GIF playback."""
        if not self.is_layer_blend_enabled():
            return False
        if not self.is_layer_hotkeys_enabled():
            return False
        target_ids = layer_hotkey_action_target_slot_ids(
            self.basic_layers_state, slot_id)
        if not target_ids:
            return False
        visibility_before = {
            tid: bool(self.basic_layers_state.get_slot(tid).visible)
            for tid in target_ids}
        if not apply_layer_hotkey_action_to_state(
                self.basic_layers_state, slot_id, action):
            return False
        visibility_changed = False
        for tid in target_ids:
            layer = self.basic_layers_state.get_slot(tid)
            if bool(layer.visible) != visibility_before[tid]:
                visibility_changed = True
        if visibility_changed:
            self.persist_basic_layers_state()
        self._schedule_layer_hotkey_visual_refresh(target_ids)
        return True

    def on_layer_global_hotkey(self, event: wx.Event) -> None:
        registry = getattr(self, "layer_hotkey_registry", None)
        if registry is None:
            event.Skip()
            return
        dispatch = registry.handle_hotkey(event.GetId())
        if dispatch is None:
            event.Skip()
            return
        self.apply_layer_hotkey_action(dispatch.slot_id, dispatch.action)

    def get_spine_neck_anchor_ratio(self) -> float:
        return clamp_neck_anchor_ratio(
            float(self.persistent_ui_state.get(
                "spine_neck_anchor_ratio", NECK_ANCHOR_RATIO_DEFAULT)))

    def set_spine_neck_anchor_ratio(self, value: float) -> None:
        self.persistent_ui_state["spine_neck_anchor_ratio"] = clamp_neck_anchor_ratio(value)
        self.save_persistent_ui_state()
        if self._basic_layer_window_visible():
            window = self._get_basic_layer_window()
            if window is not None:
                window.refresh_spine_diagram()

    def _legacy_body_bind_lean_gain(self) -> float:
        # Pre-split single gain that drove BOTH position and roll; seed both
        # new gains from it so existing setups keep their tuned value.
        return clamp_body_bind_lean_follow_gain(
            self.persistent_ui_state.get(
                "body_bind_lean_follow_gain", BODY_BIND_LEAN_FOLLOW_GAIN))

    def get_body_bind_pos_follow_gain(self) -> float:
        return clamp_body_bind_lean_follow_gain(
            self.persistent_ui_state.get(
                "body_bind_pos_follow_gain", self._legacy_body_bind_lean_gain()))

    def set_body_bind_pos_follow_gain(self, value: float) -> None:
        self.persistent_ui_state["body_bind_pos_follow_gain"] = (
            clamp_body_bind_lean_follow_gain(value))
        self.save_persistent_ui_state()
        if self._basic_layer_window_visible():
            window = self._get_basic_layer_window()
            if window is not None:
                window.refresh_spine_diagram()

    def get_body_bind_roll_follow_gain(self) -> float:
        return clamp_body_bind_lean_follow_gain(
            self.persistent_ui_state.get(
                "body_bind_roll_follow_gain", self._legacy_body_bind_lean_gain()))

    def set_body_bind_roll_follow_gain(self, value: float) -> None:
        self.persistent_ui_state["body_bind_roll_follow_gain"] = (
            clamp_body_bind_lean_follow_gain(value))
        self.save_persistent_ui_state()
        if self._basic_layer_window_visible():
            window = self._get_basic_layer_window()
            if window is not None:
                window.refresh_spine_diagram()

    def get_spine_body_bind_ray_percent(self) -> float:
        return migrate_bind_ray_percent_from_state(
            self.persistent_ui_state,
            percent_key="spine_body_bind_ray_percent",
            legacy_ratio_key="spine_body_bind_ray_t",
            default=BIND_RAY_PERCENT_DEFAULT)

    def get_spine_head_bind_ray_percent(self) -> float:
        return migrate_bind_ray_percent_from_state(
            self.persistent_ui_state,
            percent_key="spine_head_bind_ray_percent",
            legacy_ratio_key="spine_head_bind_ray_t",
            default=BIND_RAY_PERCENT_DEFAULT)

    def set_spine_body_bind_ray_percent(self, value: float) -> None:
        self.persistent_ui_state["spine_body_bind_ray_percent"] = normalize_bind_ray_percent(
            value)
        self.save_persistent_ui_state()
        if self._basic_layer_window_visible():
            window = self._get_basic_layer_window()
            if window is not None:
                window.refresh_spine_diagram()

    def set_spine_head_bind_ray_percent(self, value: float) -> None:
        self.persistent_ui_state["spine_head_bind_ray_percent"] = normalize_bind_ray_percent(
            value)
        self.save_persistent_ui_state()
        if self._basic_layer_window_visible():
            window = self._get_basic_layer_window()
            if window is not None:
                window.refresh_spine_diagram()

    def refresh_basic_layer_window_if_visible(self) -> None:
        if not self._basic_layer_window_visible():
            return
        window = self._get_basic_layer_window()
        if window is not None:
            window.refresh_all()

    def on_layer_state_changed(self) -> None:
        self.notify_layer_composite_dirty(immediate_capture=True)
        self.refresh_basic_layer_window_if_visible()
        self.refresh_layer_blend_status()
        self.persist_basic_layers_state()
        self.save_persistent_ui_state()

    def notify_layer_composite_dirty(self, *, immediate_capture: bool = False) -> None:
        """Redraw output from cache without persisting or rebuilding layer-window chrome."""
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
            self._maybe_schedule_transparent_capture_update(immediate=immediate_capture)

    def refresh_layer_slot_ui(self, slot_id: int) -> None:
        """Refresh one layer list row + detail visibility checkbox (no hotkey row rebuild)."""
        window = self._get_basic_layer_window()
        if window is not None and window.IsShown():
            window.refresh_layer_slot_row(slot_id)
        self.refresh_layer_blend_status()

    def reload_layer_from_asset(
            self,
            slot_id: int,
            *,
            hotkey_action: Optional[str] = None) -> None:
        """Reset runtime playback/visibility for a layer after hotkey action change."""
        try:
            layer = self.basic_layers_state.get_slot(slot_id)
        except KeyError:
            return
        asset_path = layer.asset_path
        was_visible = bool(layer.visible)
        if not reload_layer_from_asset_material(
                layer, idle_for_hotkey_action=hotkey_action):
            return
        if hotkey_action is not None and layer_hotkey_action_needs_asset_cache_reset(
                layer, hotkey_action):
            self.layer_asset_cache.invalidate(asset_path)
        if bool(layer.visible) != was_visible:
            self.persist_basic_layers_state()
        self.notify_layer_composite_dirty(immediate_capture=True)
        self.refresh_layer_slot_ui(slot_id)

    def refresh_layer_blend_status(self) -> None:
        if not hasattr(self, "layer_blend_status_text"):
            return
        if not self.is_layer_blend_enabled():
            self.layer_blend_status_text.SetLabel(
                "图层混合已关闭 / Layer blending off")
            if hasattr(self, "open_basic_layer_window_button"):
                self.open_basic_layer_window_button.Enable(False)
            if hasattr(self, "layer_hotkeys_enabled_checkbox"):
                self.layer_hotkeys_enabled_checkbox.Enable(False)
            return
        if hasattr(self, "open_basic_layer_window_button"):
            self.open_basic_layer_window_button.Enable(True)
        if hasattr(self, "layer_hotkeys_enabled_checkbox"):
            self.layer_hotkeys_enabled_checkbox.Enable(True)
        hotkey_hint = ""
        if not self.is_layer_hotkeys_enabled():
            hotkey_hint = "；图层快捷键未启用 / layer hotkeys off"
        active = sum(
            1 for layer in self.basic_layers_state.layers
            if layer.asset_path and layer.visible and layer.enabled)
        selected_text = "—"
        window = self._get_basic_layer_window()
        if window is not None and window.IsShown():
            selected_text = window.format_selection_status()
        elif self.basic_layers_state.selected_slot_id is not None:
            sid = self.basic_layers_state.selected_slot_id
            selected_text = f"L{sid + 1}"
        hidden_hint = ""
        if not self._basic_layer_window_visible():
            hidden_hint = "；图层窗已隐藏，点下方「打开图层窗」/ hidden — use Open Layer Editor"
        self.layer_blend_status_text.SetLabel(
            f"已启用：{active} 个图层；选中 {selected_text}{hidden_hint}{hotkey_hint} / "
            f"Enabled: {active} layer(s); selected {selected_text}")

    def _on_main_frame_activate(self, event: wx.Event) -> None:
        self.on_window_activate_for_layer_selection(event, self)
        event.Skip()

    def on_window_activate_for_layer_selection(self, event: wx.Event, window: wx.Window) -> None:
        if getattr(self, "_controls_build_in_progress", False):
            event.Skip()
            return
        if event.GetActive():
            if self._should_clear_layer_selection_for_window(window):
                wx.CallAfter(self.clear_layer_selection)
            return
        wx.CallAfter(self._maybe_clear_layer_selection_after_deactivate)

    def _should_clear_layer_selection_for_window(self, window: wx.Window) -> bool:
        if not self.is_layer_blend_enabled():
            return False
        if window is getattr(self, "basic_layer_window", None):
            return False
        if window is getattr(self, "output_frame", None):
            return False
        return True

    def _is_layer_editing_focus_window(self) -> bool:
        # The ULW is the on-screen output/editing surface but is a Win32 window,
        # so it never appears in wx focus. Clicking it to edit a layer must NOT
        # be treated as "clicked away" (which would clear the selection).
        capture_window = getattr(self, "transparent_capture_window", None)
        if capture_window is not None:
            try:
                if capture_window.owns_foreground_window():
                    return True
            except Exception:
                pass
        focused = wx.Window.FindFocus()
        if focused is None:
            return False
        top = focused.GetTopLevelParent()
        layer_win = getattr(self, "basic_layer_window", None)
        output_win = getattr(self, "output_frame", None)
        if layer_win is not None and top is layer_win:
            return True
        if output_win is not None and top is output_win:
            return True
        return False

    def _maybe_clear_layer_selection_after_deactivate(self) -> None:
        if getattr(self, "_suppress_layer_deselect", False):
            return
        if not self.is_layer_blend_enabled():
            return
        if self.basic_layers_state.selected_slot_id is None:
            return
        if self._is_layer_editing_focus_window():
            return
        self.clear_layer_selection()

    def _output_edit_slot_id(self) -> Optional[int]:
        """Layer slot editable on the output surface; None when none or multi-select."""
        if not self.is_layer_blend_enabled():
            return None
        window = self._get_basic_layer_window()
        if window is not None and window.IsShown():
            return window.get_output_edit_slot_id()
        return self.basic_layers_state.selected_slot_id

    def clear_layer_selection(self) -> None:
        if getattr(self, "_controls_build_in_progress", False):
            return
        if not self.is_layer_blend_enabled():
            return
        if getattr(self, "_suppress_layer_deselect", False):
            return
        window = self._get_basic_layer_window()
        has_selection = self.basic_layers_state.selected_slot_id is not None
        if window is not None and window.IsShown():
            has_selection = has_selection or bool(window.get_selected_slot_ids())
        if not has_selection:
            return
        self.basic_layers_state.selected_slot_id = None
        if window is not None:
            window.clear_all_selection()
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
            self._maybe_schedule_transparent_capture_update(immediate=True)
        self.refresh_layer_blend_status()

    def ensure_basic_layer_window_on_screen(self) -> None:
        window = self._get_basic_layer_window()
        if window is None:
            return
        rect = wx.Rect(window.GetPosition(), window.GetSize())
        clamped = self.clamp_client_rect_to_visible_screen(rect)
        if clamped.width != rect.width or clamped.height != rect.height:
            window.SetSize(clamped.width, clamped.height)
        if clamped.x != rect.x or clamped.y != rect.y:
            window.SetPosition((clamped.x, clamped.y))
        if clamped.x != rect.x or clamped.y != rect.y:
            self.persistent_ui_state["basic_layer_window_x"] = int(clamped.x)
            self.persistent_ui_state["basic_layer_window_y"] = int(clamped.y)

    def _should_defer_basic_layer_window(self) -> bool:
        if getattr(self, "_is_closing", False):
            return True
        if getattr(self, "_controls_build_in_progress", False):
            return True
        controls = getattr(self, "controls_frame", None)
        return not self._wx_control_alive(controls)

    def _deferred_show_basic_layer_window(self) -> None:
        if not self.is_layer_blend_enabled():
            return
        if self._should_defer_basic_layer_window():
            wx.CallAfter(self._deferred_show_basic_layer_window)
            return
        self.show_basic_layer_window()

    def show_basic_layer_window(self) -> None:
        from basic_layer_window import BasicLayerWindow
        if self._get_basic_layer_window() is None:
            try:
                self.basic_layer_window = BasicLayerWindow(self, parent=None)
                apply_app_icon(self.basic_layer_window)
            except Exception as exc:
                self.basic_layer_window = None
                traceback.print_exc()
                print(
                    f"BasicLayerWindow create failed: {type(exc).__name__}: {exc}",
                    file=sys.stderr)
                if hasattr(self, "layer_blend_status_text"):
                    self.layer_blend_status_text.SetLabel(
                        f"图层窗口打开失败：{exc}\n/ Layer window failed to open: {exc}")
                return
        window = self._get_basic_layer_window()
        if window is None:
            return
        try:
            self.ensure_basic_layer_window_on_screen()
            window.Show(True)
            self.uniconize_window(window)
            window.Raise()
            window.SetFocus()
            window.refresh_all()
        except Exception as exc:
            traceback.print_exc()
            print(
                f"BasicLayerWindow show failed: {type(exc).__name__}: {exc}",
                file=sys.stderr)
            self.basic_layer_window = None
            if hasattr(self, "layer_blend_status_text"):
                self.layer_blend_status_text.SetLabel(
                    f"图层窗口显示失败：{exc}\n/ Layer window failed to show: {exc}")
            return
        self.refresh_layer_blend_status()

    def hide_basic_layer_window(self) -> None:
        window = self._get_basic_layer_window()
        if window is not None:
            window.Hide()

    def on_basic_layer_window_closed(self) -> None:
        """Layer blend toggled off — hide editor; do not destroy the frame."""
        self._layer_blend_enabled_state.SetValue(False)
        if self._wx_control_alive(getattr(self, "layer_blend_enabled_checkbox", None)):
            try:
                self.layer_blend_enabled_checkbox.SetValue(False)
            except RuntimeError:
                pass
        self.hide_basic_layer_window()
        self.refresh_layer_blend_status()
        self.save_persistent_ui_state()

    def save_basic_layer_window_geometry(self) -> None:
        window = self._get_basic_layer_window()
        if window is None:
            return
        pos = window.GetPosition()
        size = window.GetSize()
        clamped = self.clamp_client_rect_to_visible_screen(
            wx.Rect(pos.x, pos.y, size.width, size.height))
        self.persistent_ui_state["basic_layer_window_x"] = int(clamped.x)
        self.persistent_ui_state["basic_layer_window_y"] = int(clamped.y)
        self.persistent_ui_state["basic_layer_window_width"] = int(clamped.width)
        self.persistent_ui_state["basic_layer_window_height"] = int(clamped.height)
        self.save_persistent_ui_state()

    def on_open_basic_layer_window_clicked(self, event: wx.Event) -> None:
        if not self.is_layer_blend_enabled():
            self._layer_blend_enabled_state.SetValue(True)
            if self._wx_control_alive(getattr(self, "layer_blend_enabled_checkbox", None)):
                try:
                    self.layer_blend_enabled_checkbox.SetValue(True)
                except RuntimeError:
                    pass
            self.apply_layer_blend_visibility()
        else:
            self.show_basic_layer_window()
        event.Skip()

    def on_layer_blend_changed(self, event: wx.Event):
        try:
            self._sync_layer_blend_state()
            self.apply_layer_blend_visibility()
            self.save_persistent_ui_state()
        except Exception as exc:
            if hasattr(self, "layer_blend_status_text"):
                self.layer_blend_status_text.SetLabel(
                    f"图层混合切换失败：{exc}\n/ Layer blend toggle failed: {exc}")
        event.Skip()

    def on_layer_hotkeys_changed(self, event: wx.Event) -> None:
        try:
            self._safe_checkbox_value(
                "layer_hotkeys_enabled_checkbox", self._layer_hotkeys_enabled_state)
            if self.is_layer_hotkeys_enabled():
                wx.CallAfter(self.sync_layer_hotkey_registry)
            else:
                self._teardown_layer_hotkeys()
            self.refresh_basic_layer_window_if_visible()
            self.refresh_layer_blend_status()
            self.save_persistent_ui_state()
        except Exception as exc:
            if hasattr(self, "layer_blend_status_text"):
                self.layer_blend_status_text.SetLabel(
                    f"图层快捷键切换失败：{exc}\n/ Layer hotkeys toggle failed: {exc}")
        event.Skip()

    def apply_layer_blend_visibility(self) -> None:
        enabled = self.is_layer_blend_enabled()
        if enabled:
            if self._should_defer_basic_layer_window():
                wx.CallAfter(self._deferred_show_basic_layer_window)
            else:
                self.show_basic_layer_window()
        else:
            self._teardown_layer_hotkeys()
            self.hide_basic_layer_window()
        self.sync_layer_hotkey_registry()
        self._invalidate_render_caches()
        self.refresh_layer_blend_status()
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)

    def on_layer_force_full_follow_changed(self, event: wx.Event) -> None:
        self._safe_checkbox_value(
            "layer_force_full_follow_checkbox", self._layer_force_full_follow_state)
        self.layer_binding_smoother.reset_all()
        self.head_binding_pose_filter.reset()
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
        self.save_persistent_ui_state()
        event.Skip()

    def on_close(self, event: wx.Event):
        self._is_closing = True
        with self._infer_lock:
            self._pending_infer_pose = None
        if getattr(self, "output_frame", None) is not None and self.output_frame:
            self.handle_output_frame_geometry_changed(redraw=False)
        try:
            self.persist_basic_layers_state()
        except Exception:
            pass
        if hasattr(self, "layer_hotkey_registry"):
            self._teardown_layer_hotkeys()
        self.save_persistent_ui_state()
        if hasattr(self, "active_image_source"):
            self.active_image_source.stop(self)
        self.release_video_capture()
        if hasattr(self.pose_converter, "shutdown"):
            self.pose_converter.shutdown()
        self.animation_timer.Stop()
        if hasattr(self, "display_timer"):
            self.display_timer.Stop()
        if hasattr(self, "output_enhancement") and self.output_enhancement is not None:
            try:
                self.output_enhancement.shutdown()
            except Exception:
                pass
        if hasattr(self, "ui_anim_timer"):
            self.ui_anim_timer.Stop()
        self.capture_timer.Stop()
        monitor = getattr(self, "_ui_alignment_monitor", None)
        if monitor is not None:
            monitor.stop()
        if getattr(self, "webcam_preview_popup_frame", None) is not None and self.webcam_preview_popup_frame:
            self.webcam_preview_popup_frame.Destroy()
            self.webcam_preview_popup_frame = None
        if getattr(self, "hover_help_popup", None) is not None and self.hover_help_popup:
            self.hover_help_popup.Destroy()
            self.hover_help_popup = None
        if getattr(self, "controls_frame", None) is not None and self.controls_frame:
            self.controls_frame.Destroy()
            self.controls_frame = None
        if getattr(self, "basic_layer_window", None) is not None:
            if self._wx_control_alive(self.basic_layer_window):
                self.basic_layer_window.Destroy()
            self.basic_layer_window = None
        if getattr(self, "layer_asset_cache", None) is not None:
            self.layer_asset_cache.close()
        self.destroy_transparent_capture_window()
        if getattr(self, "output_frame", None) is not None and self.output_frame:
            self.output_frame.Destroy()
            self.output_frame = None
        self.Destroy()
        event.Skip()

    def on_erase_background(self, event: wx.Event):
        pass

    @staticmethod
    def set_static_text_if_changed(control: wx.StaticText, text: str):
        if control.GetLabel() != text:
            control.SetLabelText(text)

    @staticmethod
    def wrap_static_text_to_parent(
            control: wx.StaticText,
            horizontal_margin: int = 12,
            wrap_width: Optional[int] = None):
        if wrap_width is None:
            parent = control.GetParent()
            if parent is None:
                return
            wrap_width = parent.GetClientSize().x - horizontal_margin
        if wrap_width <= 40:
            control._last_wrap_width = None
            return
        last_width = getattr(control, "_last_wrap_width", None)
        if last_width is not None and abs(last_width - wrap_width) < 2:
            return
        if last_width is not None and wrap_width > last_width:
            control.SetLabel(control.GetLabel())
        control._last_wrap_width = wrap_width
        control.Wrap(wrap_width)
        if hasattr(control, "InvalidateBestSize"):
            control.InvalidateBestSize()

    @staticmethod
    def _stop_call_later(timer: Optional[object]) -> None:
        if timer is None:
            return
        stop = getattr(timer, "Stop", None)
        if callable(stop):
            try:
                stop()
            except Exception:
                pass

    def schedule_model_input_column_layout_refresh(self) -> None:
        self._stop_call_later(getattr(self, "_model_input_layout_timer", None))
        self._model_input_layout_timer = wx.CallLater(
            80, self._run_model_input_column_layout_refresh)

    def _run_model_input_column_layout_refresh(self) -> None:
        self._model_input_layout_timer = None
        if (self._is_closing
                or self._controls_build_in_progress
                or self._applying_persisted_controls_layout_depth > 0):
            return
        self._nudge_animation_splitter_layout()
        self.apply_model_input_column_layout()

    def schedule_dynamic_output_layout_refresh(self):
        self._stop_call_later(getattr(self, "_dynamic_output_layout_timer", None))
        self._dynamic_output_layout_timer = wx.CallLater(
            80, self._run_dynamic_output_layout_refresh)

    def _run_dynamic_output_layout_refresh(self):
        self._dynamic_output_layout_timer = None
        if self._dynamic_output_layout_in_progress or self._is_closing:
            return
        self._dynamic_output_layout_in_progress = True
        try:
            self.refresh_dynamic_output_status_layout()
            self.refresh_dynamic_output_scroll()
        finally:
            self._dynamic_output_layout_in_progress = False

    @staticmethod
    def set_text_ctrl_if_changed(control: wx.TextCtrl, text: str):
        if control.GetValue() != text:
            control.ChangeValue(text)

    def set_wrapped_static_text_if_changed(self, control: wx.StaticText, text: str):
        if control.GetLabel() != text:
            control.SetLabelText(text)
            control._last_wrap_width = None
        wx.CallAfter(self.wrap_static_text_to_parent, control)

    def get_model_input_column_wrap_width(self, horizontal_margin: int = 12) -> int:
        candidates: list[int] = []
        animation_splitter = getattr(self, "animation_splitter", None)
        if animation_splitter is not None and animation_splitter.IsSplit():
            sash_w = animation_splitter.GetSashPosition()
            if sash_w > horizontal_margin + 40:
                candidates.append(sash_w - horizontal_margin)
            pane = animation_splitter.GetWindow1()
            if pane is not None:
                pane_w = pane.GetClientSize().x
                if pane_w > horizontal_margin + 40:
                    candidates.append(pane_w - horizontal_margin)
        main_splitter = getattr(self, "main_splitter", None)
        if animation_splitter is not None and main_splitter is not None and main_splitter.IsSplit():
            main_sash = main_splitter.GetSashPosition()
            if main_sash > horizontal_margin + 40:
                estimated = int((main_sash * 2) / (3 * 2))
                if estimated > horizontal_margin + 40:
                    candidates.append(estimated - horizontal_margin)
        scroll = getattr(self, "model_input_column", None)
        if scroll is not None:
            client_w = scroll.GetClientSize().x
            if client_w > horizontal_margin + 40:
                candidates.append(client_w - horizontal_margin)
        if candidates:
            return max(candidates)
        return max(40, MainFrame.VIDEO_SOURCE_COLUMN_MIN_WIDTH - horizontal_margin)

    def _sync_controls_splitter_geometry(self) -> None:
        """Flush wx layout so splitter sash / pane sizes match the shown frame."""
        if getattr(self, "_is_closing", False):
            return
        controls_window = self.get_controls_window()
        if controls_window is None:
            return
        controls_window.Layout()
        controls_window.Update()
        if hasattr(self, "main_splitter"):
            self.main_splitter.Layout()
            self.main_splitter.Update()
        animation_panel = getattr(self, "animation_panel", None)
        if animation_panel is not None:
            animation_panel.Layout()
            animation_panel.Update()
        animation_splitter = getattr(self, "animation_splitter", None)
        if animation_splitter is not None:
            animation_splitter.Layout()
            animation_splitter.Update()
        right_sidebar = getattr(self, "right_sidebar", None)
        if right_sidebar is not None:
            right_sidebar.Layout()
            right_sidebar.Update()

    def refresh_model_input_column_wrapped_texts(self) -> None:
        wrap_width = self.get_model_input_column_wrap_width()
        for attr_name in (
                "mocap_input_mode_status_text",
                "last_window_capture_text",
                "video_source_status_text",
        ):
            control = getattr(self, attr_name, None)
            if control is not None:
                control._last_wrap_width = None
                self.wrap_static_text_to_parent(control, wrap_width=wrap_width)

    def _relayout_animation_splitter_panes(self) -> None:
        animation_splitter = getattr(self, "animation_splitter", None)
        if animation_splitter is None or not animation_splitter.IsSplit():
            return
        sash = animation_splitter.GetSashPosition()
        if sash <= 0:
            return
        animation_splitter.SetSashPosition(
            MainFrame.clamp_splitter_sash(animation_splitter, sash))

    def _wrap_static_texts_under_window(self, window: Optional[wx.Window], wrap_width: int) -> None:
        if window is None or wrap_width <= 40:
            return
        if isinstance(window, wx.StaticText):
            window._last_wrap_width = None
            self.wrap_static_text_to_parent(window, wrap_width=wrap_width)
        for child in window.GetChildren():
            self._wrap_static_texts_under_window(child, wrap_width)

    def _nudge_animation_splitter_layout(self) -> None:
        animation_splitter = getattr(self, "animation_splitter", None)
        if animation_splitter is None or not animation_splitter.IsSplit():
            return
        sash = animation_splitter.GetSashPosition()
        if sash <= 0:
            return
        clamped = MainFrame.clamp_splitter_sash(animation_splitter, sash)
        if clamped != sash:
            animation_splitter.SetSashPosition(clamped)
        else:
            animation_splitter.SetSashPosition(max(1, clamped - 1))
            animation_splitter.SetSashPosition(clamped)

    def apply_model_input_column_layout(self) -> bool:
        """One-shot layout for model input column after splitter geometry is known."""
        if getattr(self, "_controls_build_in_progress", False) or getattr(self, "_is_closing", False):
            return False
        scroll = getattr(self, "model_input_column", None)
        if scroll is None:
            return False
        wrap_width = self.get_model_input_column_wrap_width()
        if wrap_width <= 40:
            return False
        self._model_input_column_last_layout_width = scroll.GetClientSize().x
        animation_splitter = getattr(self, "animation_splitter", None)
        if animation_splitter is not None and animation_splitter.IsSplit():
            sash_w = animation_splitter.GetSashPosition()
            pane_h = max(1, animation_splitter.GetSize().height)
            if sash_w > 0:
                scroll.SetSize((sash_w, pane_h))
        controls_window = self.get_controls_window()
        if controls_window is not None:
            controls_window.Layout()
        if hasattr(self, "main_splitter"):
            self.main_splitter.Layout()
        animation_panel = getattr(self, "animation_panel", None)
        if animation_panel is not None:
            animation_panel.Layout()
        self._relayout_animation_splitter_panes()
        scroll.Layout()
        sizer = scroll.GetSizer()
        if sizer is not None:
            sizer.Layout()
        self.refresh_model_input_column_wrapped_texts()
        self._wrap_static_texts_under_window(scroll, wrap_width)
        if sizer is not None:
            sizer.Layout()
        self.refresh_model_input_column_scroll()
        fit_inside = getattr(scroll, "FitInside", None)
        if callable(fit_inside):
            fit_inside()
        scroll.Refresh(False)
        if getattr(self, "pose_converter", None) is not None:
            panel = getattr(self.pose_converter, "panel", None)
            if panel is not None:
                panel.Layout()
        return True

    def finalize_controls_column_layout(self) -> bool:
        controls_window = self.get_controls_window()
        if controls_window is None or getattr(self, "_is_closing", False):
            return False
        controls_window.Layout()
        self._relayout_animation_splitter_panes()
        model_ready = self.apply_model_input_column_layout()
        self.refresh_dynamic_output_status_layout()
        self.refresh_dynamic_output_scroll()
        self.refresh_postprocess_scroll_layout()
        controls_window.Layout()
        return model_ready

    def on_controls_frame_shown(self) -> None:
        if not self.full_controls_expanded or getattr(self, "_is_closing", False):
            return
        if getattr(self, "_controls_column_layout_retry_done", False):
            return
        self._apply_persisted_controls_layout()
        if getattr(self, "_model_input_column_last_layout_width", 0) > 40:
            self._controls_column_layout_retry_done = True
        else:
            wx.CallAfter(self._retry_controls_column_layout_once)

    def _retry_controls_column_layout_once(self) -> None:
        if getattr(self, "_controls_column_layout_retry_done", False) or getattr(self, "_is_closing", False):
            return
        self._sync_controls_splitter_geometry()
        self.initialize_adjustable_columns()
        self._nudge_animation_splitter_layout()
        if self.finalize_controls_column_layout():
            self._controls_column_layout_retry_done = True
        self.refresh_preview_placeholders()

    def _apply_persisted_controls_layout(self) -> None:
        if getattr(self, "_is_closing", False):
            return
        self._sync_controls_splitter_geometry()
        self.apply_controls_layout_from_persistent()
        self._nudge_animation_splitter_layout()
        self.finalize_controls_column_layout()
        self.refresh_preview_placeholders()

    def on_controls_first_idle(self) -> None:
        self._apply_persisted_controls_layout()

    def _post_show_controls_setup(self) -> None:
        if not self.full_controls_expanded:
            return
        controls_window = self.get_controls_window()
        if controls_window is None:
            return
        self._controls_column_layout_retry_done = False
        self.adapt_main_window_to_controls(initial=not self._controls_geometry_restored)
        self.initialize_adjustable_columns()
        self._apply_persisted_controls_layout()
        if self.finalize_controls_column_layout():
            self._controls_column_layout_retry_done = True
        else:
            wx.CallAfter(self._retry_controls_column_layout_once)
        self.bind_animation_area_mousewheel()

    def refresh_model_input_column_scroll(self) -> None:
        scroll = getattr(self, "model_input_column", None)
        if not isinstance(scroll, wx.ScrolledWindow):
            return
        sizer = scroll.GetSizer()
        min_size = sizer.GetMinSize() if sizer is not None else scroll.GetBestSize()
        client_size = scroll.GetClientSize()
        if client_size.y <= 0:
            return
        virtual_width = max(client_size.x, min_size.x)
        virtual_height = max(min_size.y, client_size.y + 1)
        current = scroll.GetVirtualSize()
        if current.x == virtual_width and current.y == virtual_height:
            return
        scroll.SetVirtualSize((virtual_width, virtual_height))
        scroll.EnableScrolling(False, True)

    @staticmethod
    def find_nearest_scrolled_window(window: Optional[wx.Window]) -> Optional[wx.ScrolledWindow]:
        current = window
        while current is not None:
            if isinstance(current, wx.ScrolledWindow):
                return current
            current = current.GetParent()
        return None

    def bind_mousewheel_scroll_recursive(self, window: Optional[wx.Window]) -> None:
        if window is None:
            return
        if not getattr(window, "_mousewheel_scroll_bound", False):
            window.Bind(wx.EVT_MOUSEWHEEL, self.on_mousewheel_scroll)
            window._mousewheel_scroll_bound = True
        for child in window.GetChildren():
            if isinstance(child, wx.Slider):
                continue
            self.bind_mousewheel_scroll_recursive(child)

    def bind_animation_area_mousewheel(self) -> None:
        if hasattr(self, "animation_panel"):
            self.bind_mousewheel_scroll_recursive(self.animation_panel)
        if hasattr(self, "right_sidebar"):
            self.bind_mousewheel_scroll_recursive(self.right_sidebar)

    def on_mousewheel_scroll(self, event: wx.MouseEvent) -> None:
        event_object = event.GetEventObject()
        scroll_target = self.find_nearest_scrolled_window(event_object)
        if scroll_target is not None:
            wheel_delta = event.GetWheelDelta()
            if wheel_delta:
                lines = int(event.GetWheelRotation() / wheel_delta)
                if lines != 0:
                    scroll_target.ScrollLines(-lines)
            return
        event.Skip()

    def refresh_dynamic_output_status_layout(self):
        for attr_name in ("scale_curve_status_text", "auto_transform_status_text", "fps_text",
                          "ui_change_history_text"):
            control = getattr(self, attr_name, None)
            if control is not None:
                self.wrap_static_text_to_parent(control)

    def refresh_dynamic_output_scroll(self) -> None:
        scroll = getattr(self, "dynamic_output_scroll", None)
        panel = getattr(self, "animation_left_panel", None)
        if scroll is None or panel is None:
            return
        min_size = panel.GetBestSize()
        client_size = scroll.GetClientSize()
        if client_size.x <= 0 or client_size.y <= 0:
            return
        virtual_width = max(client_size.x, min_size.x)
        virtual_height = max(min_size.y, client_size.y + 1)
        current = scroll.GetVirtualSize()
        if current.x == virtual_width and current.y == virtual_height:
            return
        scroll.SetVirtualSize((virtual_width, virtual_height))
        scroll.EnableScrolling(False, True)

    def on_model_input_column_size(self, event: wx.Event):
        client_w = 0
        if hasattr(self, "model_input_column") and self.model_input_column is not None:
            client_w = self.model_input_column.GetClientSize().x
        last_w = getattr(self, "_model_input_column_last_layout_width", None)
        if client_w > 40 and (last_w is None or abs(client_w - last_w) >= 2):
            self._model_input_column_last_layout_width = client_w
            if not getattr(self, "_model_input_layout_in_progress", False):
                self._model_input_layout_in_progress = True
                try:
                    self.apply_model_input_column_layout()
                finally:
                    self._model_input_layout_in_progress = False
        event.Skip()

    def on_dynamic_output_panel_size(self, event: wx.Event):
        event.Skip()

    @staticmethod
    def apply_splitter_sash(splitter: wx.SplitterWindow, sash_position: int):
        if splitter is None or not splitter.IsSplit():
            return
        minimum = max(1, splitter.GetMinimumPaneSize())
        if splitter.GetSplitMode() == wx.SPLIT_HORIZONTAL:
            total = splitter.GetClientSize().y
        else:
            total = splitter.GetClientSize().x
        if total <= minimum * 2:
            return
        clamped_position = max(minimum, min(total - minimum, int(sash_position)))
        splitter.SetSashPosition(clamped_position)

    @staticmethod
    def clamp_splitter_sash(splitter: wx.SplitterWindow, sash_position: int) -> int:
        minimum = max(1, splitter.GetMinimumPaneSize())
        if splitter.GetSplitMode() == wx.SPLIT_HORIZONTAL:
            total = max(1, splitter.GetClientSize().y)
        else:
            total = max(1, splitter.GetClientSize().x)
        if total <= minimum * 2:
            return max(minimum, total // 2)
        return max(minimum, min(total - minimum, int(sash_position)))

    @staticmethod
    def _splitter_extent(splitter: wx.SplitterWindow) -> int:
        if splitter.GetSplitMode() == wx.SPLIT_HORIZONTAL:
            return max(1, int(splitter.GetClientSize().y))
        return max(1, int(splitter.GetClientSize().x))

    @staticmethod
    def _splitter_sash_from_ratio(splitter: wx.SplitterWindow, ratio: float) -> int:
        ratio = max(0.05, min(0.95, float(ratio)))
        target = int(MainFrame._splitter_extent(splitter) * ratio)
        return MainFrame.clamp_splitter_sash(splitter, target)

    def _capture_splitter_ratios(self) -> None:
        main_splitter = getattr(self, "main_splitter", None)
        if main_splitter is not None and main_splitter.IsSplit():
            extent = self._splitter_extent(main_splitter)
            self._live_main_splitter_ratio = float(main_splitter.GetSashPosition()) / float(extent)
        animation_splitter = getattr(self, "animation_splitter", None)
        if animation_splitter is not None and animation_splitter.IsSplit():
            extent = self._splitter_extent(animation_splitter)
            self._live_animation_splitter_ratio = float(animation_splitter.GetSashPosition()) / float(extent)
        right_splitter = getattr(self, "right_sidebar_splitter", None)
        if right_splitter is not None and right_splitter.IsSplit():
            extent = self._splitter_extent(right_splitter)
            self._live_right_sidebar_splitter_ratio = float(right_splitter.GetSashPosition()) / float(extent)

    def _controls_splitter_layout_readable(self) -> bool:
        controls_window = self.get_controls_window()
        if controls_window is None or not controls_window.IsShown():
            return False
        if self._applying_persisted_controls_layout_depth > 0:
            return False
        main_splitter = getattr(self, "main_splitter", None)
        return main_splitter is not None and main_splitter.IsSplit()

    def _seed_live_splitter_ratios_from_persistent(self) -> None:
        ratio_seed = (
            ("main_splitter_sash_ratio", "_live_main_splitter_ratio"),
            ("animation_splitter_sash_ratio", "_live_animation_splitter_ratio"),
            ("right_sidebar_splitter_sash_ratio", "_live_right_sidebar_splitter_ratio"),
        )
        for ratio_key, live_attr in ratio_seed:
            ratio = self._resolve_persisted_splitter_sash_ratio(ratio_key)
            if ratio is not None:
                setattr(self, live_attr, ratio)

    def _sync_splitter_ratio_fields_to_persistent_state(self) -> None:
        entries = (
            ("main_splitter", "main_splitter_sash", "main_splitter_sash_ratio", "_live_main_splitter_ratio"),
            ("animation_splitter", "animation_splitter_sash", "animation_splitter_sash_ratio", "_live_animation_splitter_ratio"),
            ("right_sidebar_splitter", "right_sidebar_splitter_sash", "right_sidebar_splitter_sash_ratio", "_live_right_sidebar_splitter_ratio"),
        )
        for splitter_attr, sash_key, ratio_key, live_attr in entries:
            ratio = getattr(self, live_attr, None)
            if ratio is not None:
                self.persistent_ui_state[ratio_key] = ratio
            splitter = getattr(self, splitter_attr, None)
            if splitter is not None and splitter.IsSplit():
                self.persistent_ui_state[sash_key] = splitter.GetSashPosition()

    def _collect_splitter_layout_fields(self) -> dict:
        fields: dict = {}
        entries = (
            ("main_splitter", "main_splitter_sash", "main_splitter_sash_ratio", "_live_main_splitter_ratio"),
            ("animation_splitter", "animation_splitter_sash", "animation_splitter_sash_ratio", "_live_animation_splitter_ratio"),
            ("right_sidebar_splitter", "right_sidebar_splitter_sash", "right_sidebar_splitter_sash_ratio", "_live_right_sidebar_splitter_ratio"),
        )
        if self._controls_splitter_layout_readable():
            for splitter_attr, sash_key, ratio_key, _live_attr in entries:
                splitter = getattr(self, splitter_attr, None)
                if splitter is None or not splitter.IsSplit():
                    continue
                extent = self._splitter_extent(splitter)
                if extent <= 0:
                    continue
                sash = splitter.GetSashPosition()
                fields[sash_key] = sash
                fields[ratio_key] = float(sash) / float(extent)
            return fields
        for _splitter_attr, sash_key, ratio_key, live_attr in entries:
            ratio = self._resolve_persisted_splitter_sash_ratio(ratio_key)
            if ratio is None:
                ratio = getattr(self, live_attr, None)
            if ratio is None and ratio_key in self.persistent_ui_state:
                saved_ratio = self.persistent_ui_state.get(ratio_key)
                if isinstance(saved_ratio, (int, float)):
                    ratio = float(saved_ratio)
            if ratio is not None:
                fields[ratio_key] = ratio
            if sash_key in self.persistent_ui_state:
                fields[sash_key] = self.persistent_ui_state[sash_key]
        return fields

    @staticmethod
    def compute_equal_thirds_main_sash(
            total_width: int,
            left_minimum: int,
            right_minimum: int) -> int:
        """Main splitter: left (B+C) = 2/3, right (D preview+post) = 1/3 of total width."""
        total_width = max(1, int(total_width))
        left_minimum = max(1, int(left_minimum))
        right_minimum = max(1, int(right_minimum))
        if total_width <= left_minimum + right_minimum:
            return max(left_minimum, total_width // 2)
        ideal = int((2 * total_width) / MainFrame.CONTROLS_LAYOUT_THIRD_COUNT)
        return max(left_minimum, min(total_width - right_minimum, ideal))

    @staticmethod
    def compute_equal_halves_sash(total_extent: int, minimum_pane_size: int) -> int:
        """Animation splitter (B|C each ~1/3 total width) or right sidebar (preview|post): 50/50."""
        total_extent = max(1, int(total_extent))
        minimum = max(1, int(minimum_pane_size))
        target = total_extent // 2
        return max(minimum, min(total_extent - minimum, target))

    def _resolve_persisted_splitter_sash(self, key: str, default_sash: int) -> int:
        saved = self.persistent_ui_state.get(key)
        if isinstance(saved, (int, float)):
            return int(saved)
        return int(default_sash)

    def compute_default_main_splitter_sash(self) -> int:
        if not hasattr(self, "main_splitter"):
            return MainFrame.CONTROLS_TWO_COLUMN_MIN_WIDTH
        return MainFrame.compute_equal_thirds_main_sash(
            self.main_splitter.GetClientSize().x,
            MainFrame.CONTROLS_TWO_COLUMN_MIN_WIDTH,
            MainFrame.RIGHT_SIDEBAR_MIN_WIDTH)

    def compute_default_animation_splitter_sash(self) -> int:
        if not hasattr(self, "animation_splitter"):
            return MainFrame.CONTROLS_COLUMN_MIN_WIDTH
        return MainFrame.compute_equal_halves_sash(
            self.animation_splitter.GetClientSize().x,
            self.animation_splitter.GetMinimumPaneSize())

    def compute_default_right_sidebar_splitter_sash(self) -> int:
        if not hasattr(self, "right_sidebar_splitter"):
            return MainFrame.CAPTURE_PANEL_MIN_HEIGHT
        return MainFrame.compute_equal_halves_sash(
            self.right_sidebar_splitter.GetClientSize().y,
            self.right_sidebar_splitter.GetMinimumPaneSize())

    @staticmethod
    def adaptive_right_sidebar_capture_min_height(total_height: int) -> int:
        """Allow more vertical drag on short (portrait) windows while keeping a usable preview."""
        total_height = max(1, int(total_height))
        return min(
            MainFrame.CAPTURE_PANEL_MIN_HEIGHT,
            max(MainFrame.RIGHT_SIDEBAR_PANE_MIN_HEIGHT, int(total_height * 0.22)))

    def _resolve_persisted_splitter_sash_ratio(self, key: str) -> Optional[float]:
        saved = self.persistent_ui_state.get(key)
        if isinstance(saved, (int, float)):
            ratio = float(saved)
            if 0.05 <= ratio <= 0.95:
                return ratio
        return None

    def compute_right_sidebar_splitter_sash_from_ratio(self, ratio: float) -> int:
        if not hasattr(self, "right_sidebar_splitter"):
            return MainFrame.CAPTURE_PANEL_MIN_HEIGHT
        total_h = max(1, self.right_sidebar_splitter.GetClientSize().y)
        minimum = max(1, self.right_sidebar_splitter.GetMinimumPaneSize())
        target = int(total_h * float(ratio))
        return MainFrame.clamp_splitter_sash(self.right_sidebar_splitter, target)

    def _resolve_layout_splitter_ratio(
            self,
            ratio_key: str,
            sash_key: str,
            splitter: Optional[wx.SplitterWindow],
            live_ratio: Optional[float],
            default_ratio: float) -> float:
        persisted = self._resolve_persisted_splitter_sash_ratio(ratio_key)
        if persisted is not None:
            return persisted
        if splitter is not None and splitter.IsSplit():
            saved_sash = self.persistent_ui_state.get(sash_key)
            if isinstance(saved_sash, (int, float)):
                extent = self._splitter_extent(splitter)
                if extent > 0:
                    return max(0.05, min(0.95, float(saved_sash) / float(extent)))
        if live_ratio is not None:
            return live_ratio
        return default_ratio

    def apply_controls_layout_from_persistent(self, *, vertical_only: bool = False) -> None:
        """Restore splitters: visual B|C|D equal width via nested splitters (not 3 horizontal splitters)."""
        self._applying_persisted_controls_layout_depth += 1
        try:
            if not vertical_only:
                if hasattr(self, "main_splitter") and self.main_splitter.IsSplit():
                    main_ratio = self._resolve_layout_splitter_ratio(
                        "main_splitter_sash_ratio",
                        "main_splitter_sash",
                        self.main_splitter,
                        self._live_main_splitter_ratio,
                        2.0 / MainFrame.CONTROLS_LAYOUT_THIRD_COUNT)
                    main_sash = self._splitter_sash_from_ratio(self.main_splitter, main_ratio)
                    self.apply_splitter_sash(self.main_splitter, main_sash)
                if hasattr(self, "animation_splitter") and self.animation_splitter.IsSplit():
                    animation_ratio = self._resolve_layout_splitter_ratio(
                        "animation_splitter_sash_ratio",
                        "animation_splitter_sash",
                        self.animation_splitter,
                        self._live_animation_splitter_ratio,
                        0.5)
                    animation_sash = self._splitter_sash_from_ratio(
                        self.animation_splitter, animation_ratio)
                    self.apply_splitter_sash(self.animation_splitter, animation_sash)
            if hasattr(self, "right_sidebar_splitter") and self.right_sidebar_splitter.IsSplit():
                right_ratio = self._resolve_layout_splitter_ratio(
                    "right_sidebar_splitter_sash_ratio",
                    "right_sidebar_splitter_sash",
                    self.right_sidebar_splitter,
                    self._live_right_sidebar_splitter_ratio,
                    0.5)
                right_sash = self._splitter_sash_from_ratio(
                    self.right_sidebar_splitter, right_ratio)
                self.apply_splitter_sash(self.right_sidebar_splitter, right_sash)
        finally:
            self._applying_persisted_controls_layout_depth -= 1
        self._capture_splitter_ratios()
        self._sync_splitter_ratio_fields_to_persistent_state()

    def get_controls_window(self) -> Optional[wx.Frame]:
        return self.controls_frame if getattr(self, "controls_frame", None) is not None else None

    def initialize_adjustable_columns(self):
        controls_window = self.get_controls_window()
        if getattr(self, "_is_closing", False) or controls_window is None:
            return
        if hasattr(self, "right_sidebar"):
            self.right_sidebar.Layout()
        controls_window.Layout()
        self.apply_controls_layout_from_persistent()
        controls_window.Layout()
        self._relayout_animation_splitter_panes()

    def on_compact_geometry_changed(self, event: wx.Event):
        if self.full_controls_expanded:
            event.Skip()
            return
        self.schedule_window_geometry_save()
        event.Skip()

    def schedule_window_geometry_save(self):
        if self._restoring_window_geometry:
            return
        self._stop_call_later(getattr(self, "_window_geometry_save_timer", None))
        self._window_geometry_save_timer = wx.CallLater(
            250, self.process_window_geometry_save)

    def process_window_geometry_save(self):
        self._window_geometry_save_timer = None
        self._window_geometry_save_pending = False
        if self._is_closing or self._restoring_window_geometry:
            return
        self.save_persistent_ui_state()

    def get_saved_client_rect(self, prefix: str) -> Optional[wx.Rect]:
        data = self.persistent_ui_state
        width_key = f"{prefix}_w"
        height_key = f"{prefix}_h"
        if width_key not in data or height_key not in data:
            return None
        width = max(1, int(data[width_key]))
        height = max(1, int(data[height_key]))
        x = int(data.get(f"{prefix}_x", 0))
        y = int(data.get(f"{prefix}_y", 0))
        return self.clamp_client_rect_to_visible_screen(wx.Rect(x, y, width, height))

    @staticmethod
    def clamp_client_rect_to_visible_screen(rect: wx.Rect) -> wx.Rect:
        width = max(1, int(rect.width))
        height = max(1, int(rect.height))
        if wx.Display.GetCount() <= 0:
            return wx.Rect(max(0, rect.x), max(0, rect.y), width, height)

        best_display = wx.Display(0)
        best_overlap = -1
        probe_rect = wx.Rect(rect.x, rect.y, max(64, width), max(64, height))
        for display_index in range(wx.Display.GetCount()):
            display = wx.Display(display_index)
            work_area = display.GetClientArea()
            overlap = MainFrame._rect_intersection_area(probe_rect, work_area)
            if overlap > best_overlap:
                best_overlap = overlap
                best_display = display

        work_area = best_display.GetClientArea()
        max_width = max(64, work_area.width - 8)
        max_height = max(64, work_area.height - 8)
        width = min(width, max_width)
        height = min(height, max_height)
        x = max(work_area.x, min(rect.x, work_area.x + work_area.width - width))
        y = max(work_area.y, min(rect.y, work_area.y + work_area.height - height))
        return wx.Rect(x, y, width, height)

    @staticmethod
    def _rect_intersection_area(a: wx.Rect, b: wx.Rect) -> int:
        left = max(a.x, b.x)
        top = max(a.y, b.y)
        right = min(a.x + a.width, b.x + b.width)
        bottom = min(a.y + a.height, b.y + b.height)
        if right <= left or bottom <= top:
            return 0
        return (right - left) * (bottom - top)

    def get_locked_output_client_size(self) -> tuple[int, int]:
        return self.LOCKED_OUTPUT_CLIENT_WIDTH, self.LOCKED_OUTPUT_CLIENT_HEIGHT

    @staticmethod
    def normalize_background_hex(value: str, fallback: str = "#000000") -> str:
        if not isinstance(value, str):
            return fallback
        color_text = value.strip()
        if len(color_text) == 7 and color_text.startswith("#"):
            try:
                int(color_text[1:], 16)
                return color_text.upper()
            except Exception:
                return fallback
        return fallback

    @staticmethod
    def background_hex_from_legacy_selection(raw_selection: int) -> str:
        selection = int(raw_selection)
        if selection == 1:
            return "#00FF00"
        if selection == 2:
            return "#0000FF"
        if selection == 3:
            return "#000000"
        if selection == 4:
            return "#FFFFFF"
        return "#000000"

    def resolve_persistent_output_background_mode(self, data: Optional[dict] = None) -> str:
        state = self.persistent_ui_state if data is None else data
        if state.get("transparent_capture_output_enabled"):
            legacy_mode = str(state.get("output_background_mode") or OUTPUT_BACKGROUND_TRANSPARENT)
            if legacy_mode in (OUTPUT_BACKGROUND_TRANSPARENT, "transparent"):
                return OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE
        if "output_background_mode" in state:
            mode = str(state["output_background_mode"])
            if mode in OUTPUT_BACKGROUND_MODE_VALUES:
                return mode
            if "output_background_hex" in state or "output_background_selection" in state:
                return OUTPUT_BACKGROUND_COLOR
            return OUTPUT_BACKGROUND_TRANSPARENT
        if "output_background_hex" in state or "output_background_selection" in state:
            return OUTPUT_BACKGROUND_COLOR
        return OUTPUT_BACKGROUND_TRANSPARENT

    def resolve_persistent_output_background_hex(self, data: Optional[dict] = None) -> str:
        state = self.persistent_ui_state if data is None else data
        if "output_background_hex" in state:
            return self.normalize_background_hex(state["output_background_hex"], "#000000")
        if "output_background_selection" in state:
            return self.background_hex_from_legacy_selection(int(state["output_background_selection"]))
        return "#000000"

    def resolve_persistent_output_background_image_path(self, data: Optional[dict] = None) -> str:
        state = self.persistent_ui_state if data is None else data
        return str(state.get("output_background_image_path") or "")

    def apply_output_background_mode(self, mode: str) -> None:
        if mode not in OUTPUT_BACKGROUND_MODE_VALUES:
            mode = OUTPUT_BACKGROUND_TRANSPARENT
        control = getattr(self, "output_background_mode_choice", None)
        if isinstance(control, wx.Choice):
            try:
                control.SetSelection(OUTPUT_BACKGROUND_MODE_VALUES.index(mode))
            except ValueError:
                control.SetSelection(0)
        elif control is not None:
            try:
                control.SetValue(mode)
            except Exception:
                pass

    def apply_output_background_hex(self, color_hex: str) -> None:
        normalized = self.normalize_background_hex(color_hex, "#000000")
        picker = getattr(self, "output_background_choice", None)
        if picker is None:
            return
        if isinstance(picker, wx.ColourPickerCtrl):
            try:
                picker.SetColour(wx.Colour(normalized))
                return
            except Exception:
                pass
        try:
            picker.SetValue(normalized)
        except Exception:
            pass

    def apply_persistent_output_background_state(self, data: Optional[dict] = None) -> None:
        state = self.persistent_ui_state if data is None else data
        mode = self.resolve_persistent_output_background_mode(state)
        self.apply_output_background_mode(mode)
        image_path = self.resolve_persistent_output_background_image_path(state)
        if image_path or "output_background_image_path" in state:
            self.set_output_background_image_path(image_path)
        elif mode == OUTPUT_BACKGROUND_IMAGE:
            self.set_output_background_image_path(self.get_bundled_transparent_background_path())
        self.apply_output_background_hex(self.resolve_persistent_output_background_hex(state))
        self.update_output_background_controls_visibility()

    @staticmethod
    def get_bundled_transparent_background_path() -> str:
        return BUNDLED_TRANSPARENT_BACKGROUND_PATH

    def is_transparent_capture_background_enabled(self) -> bool:
        return self.get_output_background_mode() == OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE

    def is_ulw_output_enabled(self) -> bool:
        """The layered ULW (easyvtuberstudio_output) is the single output window
        for every background mode now: 真透 keeps per-pixel alpha, while
        color/image/黑键 composite an opaque background plate into the same
        window. OutputFrame is retired as an output surface."""
        return True

    def get_output_capture_backend(self) -> str:
        """Resolve the active output delivery backend (how the transparent
        output reaches capture software). Honors an explicit persisted
        `output_capture_backend` override, otherwise derives it from the output
        background mode. See output_backends.py for the tool recommendations."""
        persisted = self.persistent_ui_state.get("output_capture_backend")
        return resolve_output_backend(persisted, self.get_output_background_mode())

    def get_output_background_mode(self) -> str:
        control = getattr(self, "output_background_mode_choice", None)
        if control is None:
            mode = str(self.persistent_ui_state.get("output_background_mode") or OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE)
            if mode in OUTPUT_BACKGROUND_MODE_VALUES:
                return mode
            return OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE
        if isinstance(control, wx.Choice):
            index = control.GetSelection()
            if index < 0:
                index = 0
            if index >= len(OUTPUT_BACKGROUND_MODE_VALUES):
                index = len(OUTPUT_BACKGROUND_MODE_VALUES) - 1
            return OUTPUT_BACKGROUND_MODE_VALUES[index]
        try:
            mode = str(control.GetValue())
        except Exception:
            mode = OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE
        if mode in OUTPUT_BACKGROUND_MODE_VALUES:
            return mode
        return OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE

    def get_output_background_image_path(self) -> str:
        state = getattr(self, "output_background_image_path_state", None)
        if state is not None:
            try:
                return str(state.GetValue() or "").strip()
            except Exception:
                pass
        return ""

    def set_output_background_image_path(self, path: str):
        path = str(path or "").strip()
        state = getattr(self, "output_background_image_path_state", None)
        if state is not None:
            state.SetValue(path)
        display = getattr(self, "output_background_image_path_text", None)
        if display is not None:
            display.SetLabel(self.format_output_background_image_path_label(path))

    @staticmethod
    def format_output_background_image_path_label(path: str) -> str:
        path = str(path or "").strip()
        if not path:
            return "(内置透明图 / Built-in transparent)"
        bundled = BUNDLED_TRANSPARENT_BACKGROUND_PATH
        if os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(bundled)):
            return "transparent.png (内置 / Built-in)"
        return os.path.basename(path) or path

    def resolve_output_background_image_path(self) -> str:
        raw_path = self.get_output_background_image_path()
        if raw_path:
            if os.path.isfile(raw_path):
                return raw_path
            resolved = from_repo_relative(raw_path)
            if resolved and os.path.isfile(resolved):
                return resolved
        bundled = self.get_bundled_transparent_background_path()
        if os.path.isfile(bundled):
            return bundled
        return raw_path

    def invalidate_output_background_image_cache(self):
        self._output_background_image_cache_key = None
        self._output_background_image_cache = None
        self._cached_background_signature = None
        self._cached_background_rgba = None

    def _invalidate_render_caches(self) -> None:
        self._render_keyframe_image_id = None
        self._render_keyframe_rgba = None
        self._render_keyframe_bitmap = None
        if getattr(self, "output_enhancement", None) is not None:
            self.output_enhancement.keyframe_cache.invalidate_image()
        self._cached_background_signature = None
        self._cached_background_rgba = None
        self._cached_capture_foreground_rgba = None
        self._cached_capture_foreground_signature = None
        self._cached_present_rgba = None

    def _invalidate_capture_foreground_cache(self) -> None:
        self._cached_capture_foreground_rgba = None
        self._cached_capture_foreground_signature = None
        capture_window = getattr(self, "transparent_capture_window", None)
        if capture_window is not None:
            capture_window._last_frame_hash = None

    def get_mouth_infer_cap_hz(self) -> int:
        choice = getattr(self, "mouth_infer_cap_choice", None)
        if isinstance(choice, wx.Choice):
            selection = choice.GetSelection()
            if 0 <= selection < len(MOUTH_INFER_CAP_HZ_VALUES):
                return MOUTH_INFER_CAP_HZ_VALUES[selection]
        stored = self.persistent_ui_state.get("mouth_infer_cap_hz", MOUTH_INFER_CAP_HZ_DEFAULT)
        try:
            cap_hz = int(stored)
        except (TypeError, ValueError):
            cap_hz = MOUTH_INFER_CAP_HZ_DEFAULT
        if cap_hz not in MOUTH_INFER_CAP_HZ_VALUES:
            cap_hz = MOUTH_INFER_CAP_HZ_DEFAULT
        return cap_hz

    def is_smooth_affine_30hz_enabled(self) -> bool:
        checkbox = getattr(self, "smooth_affine_30hz_checkbox", None)
        if isinstance(checkbox, wx.CheckBox):
            return checkbox.GetValue()
        return bool(self.persistent_ui_state.get("smooth_affine_30hz", True))

    def get_display_present_cap_hz(self) -> int:
        if self.is_smooth_affine_30hz_enabled():
            return MainFrame.DISPLAY_PRESENT_CAP_HZ
        return max(1, self.get_mouth_infer_cap_hz())

    def get_auxiliary_preview_cap_hz(self) -> float:
        """Scale-curve preview + spine diagram: half infer cap to skip redundant repaints."""
        return max(6.0, self.get_effective_infer_cap_hz() / 2.0)

    def _auxiliary_preview_min_interval_ns(self) -> int:
        return int(1e9 / max(1.0, self.get_auxiliary_preview_cap_hz()))

    def should_refresh_auxiliary_preview(self, last_time_ns: Optional[int]) -> bool:
        now_ns = time.time_ns()
        if last_time_ns is None:
            return True
        return now_ns - last_time_ns >= self._auxiliary_preview_min_interval_ns()

    def is_smooth_display_priority(self) -> bool:
        """Prefer unified infer throttling (any pose change + effective cap)."""
        return True

    def _pose_any_changed(self, last_pose: List[float], current_pose: List[float]) -> bool:
        for previous, current in zip(last_pose, current_pose):
            if abs(previous - current) > POSE_PARAM_EPS:
                return True
        return False

    def get_mouth_pose_indices(self) -> tuple[int, ...]:
        converter = self.pose_converter
        return (
            converter.mouth_aaa_index,
            converter.mouth_iii_index,
            converter.mouth_uuu_index,
            converter.mouth_eee_index,
            converter.mouth_ooo_index,
            converter.mouth_lowered_corner_left_index,
            converter.mouth_lowered_corner_right_index,
            converter.mouth_raised_corner_left_index,
            converter.mouth_raised_corner_right_index,
        )

    def _pose_infer_exempt_indices(self) -> frozenset[int]:
        return frozenset(self.get_mouth_pose_indices()) | frozenset([
            self.pose_converter.breathing_index,
        ])

    def _pose_non_mouth_changed(self, last_pose: List[float], current_pose: List[float]) -> bool:
        exempt = self._pose_infer_exempt_indices()
        for index, (previous, current) in enumerate(zip(last_pose, current_pose)):
            if index in exempt:
                continue
            if abs(previous - current) > POSE_PARAM_EPS:
                return True
        return False

    def _pose_mouth_changed(self, last_pose: List[float], current_pose: List[float]) -> bool:
        for index in self.get_mouth_pose_indices():
            if abs(last_pose[index] - current_pose[index]) >= MOUTH_POSE_QUANT_STEP:
                return True
        return False

    def get_effective_infer_cap_hz(self) -> int:
        base = self.get_mouth_infer_cap_hz()
        if is_pose_interpolation_active(self.get_output_frame_interpolation_multiplier()):
            return pose_interp_effective_cap_hz(
                base, self.get_output_frame_interpolation_multiplier())
        return max(MainFrame.MIN_OUT_PRESENT_HZ, base)

    def should_infer_pose(self, last_pose: Optional[List[float]], current_pose: List[float]) -> bool:
        if last_pose is None:
            return True
        reference_pose = self.output_enhancement.pose_interpolation.reference_pose_for_change_detection(
            last_pose, self.get_output_frame_interpolation_multiplier())
        if self.is_smooth_display_priority():
            if not self._pose_any_changed(reference_pose, current_pose):
                return False
            now_ns = time.time_ns()
            min_interval_ns = int(1e9 / max(1, self.get_effective_infer_cap_hz()))
            if self._last_pose_infer_time_ns is None:
                return True
            return now_ns - self._last_pose_infer_time_ns >= min_interval_ns
        if self._pose_non_mouth_changed(last_pose, current_pose):
            return True
        if not self._pose_mouth_changed(last_pose, current_pose):
            return False
        now_ns = time.time_ns()
        min_interval_ns = int(1e9 / max(1, self.get_mouth_infer_cap_hz()))
        if self._last_pose_infer_time_ns is None:
            return True
        return now_ns - self._last_pose_infer_time_ns >= min_interval_ns

    def schedule_async_pose_infer(self, pose_list: List[float]) -> None:
        if self._is_closing or self.poser is None or self.torch_source_image is None:
            return
        with self._infer_lock:
            self._pending_infer_pose = list(pose_list)
            if self._infer_worker_active:
                return
            self._infer_worker_active = True
        threading.Thread(
            target=self._async_pose_infer_worker,
            daemon=True,
            name="tha4-pose-infer").start()

    def _async_pose_infer_worker(self) -> None:
        last_pose: Optional[List[float]] = None
        last_wx_image: Optional[wx.Image] = None
        try:
            while not self._is_closing:
                with self._infer_lock:
                    pose = self._pending_infer_pose
                    self._pending_infer_pose = None
                if pose is None:
                    break
                try:
                    last_wx_image = self.render_pose_to_wx_image(pose)
                    last_pose = list(pose)
                except Exception as exc:
                    if not getattr(self, "_last_infer_worker_error", None):
                        self._last_infer_worker_error = repr(exc)
                        print(
                            "async pose infer failed (logged once):",
                            exc,
                            file=sys.stderr)
                    last_wx_image = None
                with self._infer_lock:
                    if self._pending_infer_pose is None:
                        break
        finally:
            with self._infer_lock:
                self._infer_worker_active = False
        if (
                not self._is_closing
                and last_pose is not None
                and last_wx_image is not None):
            wx.CallAfter(self._finish_async_pose_infer, last_pose, last_wx_image)

    def _finish_async_pose_infer(self, pose_list: List[float], wx_image: Optional[wx.Image]) -> None:
        if self._is_closing or wx_image is None:
            return
        self._note_pose_present_time()
        self.last_pose = pose_list
        self.last_output_wx_image = wx_image
        self.last_background_choice = self.get_output_background_signature()
        self.output_enhancement.keyframe_cache.invalidate_image()
        self._advance_pose_interpolation_after_infer(pose_list)
        self._note_inference_fps_tick()
        # Presenting is left to on_display_timer (throttled to the display present
        # cap + deduped): driving a full synchronous composite here on every
        # inference floods the UI thread (the composite is the hot cost) and
        # halves the effective output rate. The display timer picks up
        # last_output_wx_image on its next tick.

    def should_refresh_transparent_capture(self) -> bool:
        now_ns = time.time_ns()
        # The true-transparent ULW is now the *sole* on-screen output in this
        # mode (OutputFrame hidden), so it must refresh at the full display
        # present cap rather than the old secondary-window 15Hz throttle.
        cap_hz = max(1, self.get_display_present_cap_hz())
        min_interval_ns = int(1e9 / cap_hz)
        if self._last_capture_present_time_ns is None:
            return True
        return now_ns - self._last_capture_present_time_ns >= min_interval_ns

    def _note_capture_present_time(self) -> None:
        self._last_capture_present_time_ns = time.time_ns()

    def _advance_pose_interpolation_after_infer(self, inferred_pose: List[float]) -> None:
        self.output_enhancement.pose_interpolation.advance_after_infer(
            inferred_pose, self.get_output_frame_interpolation_multiplier())

    def resolve_scheduled_infer_pose(self, current_pose: List[float]) -> List[float]:
        return self.output_enhancement.pose_interpolation.resolve_infer_pose(
            current_pose, self.get_output_frame_interpolation_multiplier())

    def should_refresh_cached_affine(self) -> bool:
        now_ns = time.time_ns()
        min_interval_ns = int(1e9 / max(1, self.get_display_present_cap_hz()))
        if self._last_cached_affine_present_time_ns is None:
            return True
        return now_ns - self._last_cached_affine_present_time_ns >= min_interval_ns

    def _note_cached_affine_present_time(self) -> None:
        self._last_cached_affine_present_time_ns = time.time_ns()

    def _note_pose_present_time(self) -> None:
        now_ns = time.time_ns()
        self._last_pose_infer_time_ns = now_ns
        self._last_cached_affine_present_time_ns = now_ns

    @staticmethod
    def _record_rate_in_rolling_window(
            timestamps: List[float],
            *,
            window_sec: float = 1.0) -> tuple[List[float], float]:
        now = time.monotonic()
        kept = [tick for tick in timestamps if now - tick <= window_sec]
        kept.append(now)
        rate = len(kept) / window_sec
        return kept, rate

    def _note_input_fps_tick(self) -> None:
        # Stats only; the FPS text is repainted by on_ui_anim_timer (25 fps cap).
        self._input_frame_times, self._input_fps = self._record_rate_in_rolling_window(
            self._input_frame_times)

    def _note_inference_fps_tick(self) -> None:
        self._inference_complete_times, self._inference_fps = self._record_rate_in_rolling_window(
            self._inference_complete_times)

    @staticmethod
    def averaged_output_fps_from_present_times(
            present_times: List[float],
            *,
            avg_frame_count: int = 5,
            max_gap_sec: float = 2.0) -> Optional[float]:
        """FPS from mean frame interval over the last *avg_frame_count* presents."""
        if not present_times or len(present_times) < 2:
            return None
        window = present_times[-max(2, int(avg_frame_count)) :]
        span = window[-1] - window[0]
        intervals = len(window) - 1
        if intervals <= 0 or span <= 1e-6:
            return None
        if span / intervals >= max_gap_sec:
            return None
        return intervals / span

    def _note_actual_output_present(self) -> None:
        """Append a real output present timestamp (display value commits separately)."""
        now = time.monotonic()
        self._last_actual_output_present_mono = now
        self._output_present_times.append(now)
        keep = max(2, MainFrame.OUTPUT_FPS_AVG_FRAME_COUNT)
        if len(self._output_present_times) > keep:
            self._output_present_times = self._output_present_times[-keep:]

    def _update_output_fps_estimate_if_due(self) -> None:
        """Refresh cached Out FPS at most once per second from the last five frames."""
        now = time.monotonic()
        last_commit = getattr(self, "_output_fps_last_commit_mono", 0.0)
        if now - last_commit < MainFrame.OUTPUT_FPS_UPDATE_INTERVAL_SEC:
            return
        self._output_fps_last_commit_mono = now
        last_present = self._last_actual_output_present_mono
        if last_present is None or now - last_present > MainFrame.OUTPUT_FPS_STALE_SEC:
            self._display_out_fps = 0.0
            return
        measured = self.averaged_output_fps_from_present_times(
            getattr(self, "_output_present_times", []),
            avg_frame_count=MainFrame.OUTPUT_FPS_AVG_FRAME_COUNT)
        if measured is not None:
            self._display_out_fps = measured

    def _get_display_out_fps_for_label(self) -> float:
        self._update_output_fps_estimate_if_due()
        return float(getattr(self, "_display_out_fps", 0.0))

    def _on_ulw_frame_delivered(self) -> None:
        """Single hook after each ULW frame reaches the output surface."""
        self._note_capture_present_time()
        self._note_actual_output_present()

    def _refresh_fps_display(self) -> None:
        if not hasattr(self, "fps_text"):
            return
        input_fps = getattr(self, "_input_fps", 0.0)
        inference_fps = getattr(self, "_inference_fps", 0.0)
        display_fps = self._get_display_out_fps_for_label()
        label = (
            f"输入 In {input_fps:.1f}\n"
            f"推理 Inf {inference_fps:.1f}\n"
            f"显示 Out {display_fps:.1f}")
        self.set_wrapped_static_text_if_changed(self.fps_text, label)

    def _record_ui_change(self, message: str) -> None:
        if is_blocked(self):
            return
        history = getattr(self, "_user_change_history", None)
        if history is None:
            return
        history.add(message)
        self._refresh_ui_change_history_display()

    def _refresh_ui_change_history_display(self) -> None:
        control = getattr(self, "ui_change_history_text", None)
        history = getattr(self, "_user_change_history", None)
        if control is None or history is None:
            return
        lines = history.lines(3)
        label = "最近改动 / Recent UI\n" + "\n".join(lines)
        self.set_wrapped_static_text_if_changed(control, label)

    def _wire_ui_change_logging(self) -> None:
        if getattr(self, "_ui_change_log_wired", False):
            return
        root = getattr(self, "controls_frame", None)
        if root is None:
            return
        record = self._record_ui_change
        wire_controls_for_change_log(root, record)
        wire_float_slider_controls(self, record)
        self._ui_change_log_wired = True

    @staticmethod
    def scale_image_cover(image: wx.Image, width: int, height: int) -> wx.Image:
        width = max(1, int(width))
        height = max(1, int(height))
        source_width = max(1, image.GetWidth())
        source_height = max(1, image.GetHeight())
        scale = max(width / source_width, height / source_height)
        scaled_width = max(1, int(round(source_width * scale)))
        scaled_height = max(1, int(round(source_height * scale)))
        if scaled_width != source_width or scaled_height != source_height:
            scaled = image.Scale(scaled_width, scaled_height, wx.IMAGE_QUALITY_HIGH)
        else:
            scaled = image
        crop_x = max(0, (scaled.GetWidth() - width) // 2)
        crop_y = max(0, (scaled.GetHeight() - height) // 2)
        return scaled.GetSubImage(wx.Rect(crop_x, crop_y, width, height))

    def load_output_background_image(self, width: int, height: int) -> Optional[wx.Image]:
        width = max(1, int(width))
        height = max(1, int(height))
        image_path = self.resolve_output_background_image_path()
        cache_key = (image_path, width, height)
        if getattr(self, "_output_background_image_cache_key", None) == cache_key:
            cached = getattr(self, "_output_background_image_cache", None)
            if cached is not None:
                return cached
        if not image_path or not os.path.isfile(image_path):
            return None
        try:
            image = wx.Image(image_path)
        except Exception:
            return None
        if not image.IsOk():
            return None
        scaled = self.scale_image_cover(image, width, height)
        self._output_background_image_cache_key = cache_key
        self._output_background_image_cache = scaled
        return scaled

    def get_output_frame_interpolation_multiplier(self) -> int:
        control = getattr(self, "output_frame_interpolation_choice", None)
        if isinstance(control, wx.Choice):
            index = control.GetSelection()
            if index < 0:
                index = 0
            if index >= len(POSE_FRAME_INTERP_VALUES):
                index = len(POSE_FRAME_INTERP_VALUES) - 1
            return POSE_FRAME_INTERP_VALUES[index]
        try:
            return normalize_pose_frame_multiplier(control.GetValue())
        except Exception:
            return POSE_FRAME_INTERP_OFF

    def reset_frame_interpolation_buffers(self):
        seed = list(self.last_pose) if self.last_pose is not None else None
        self.output_enhancement.pose_interpolation.reset(seed_pose=seed)

    def is_frame_interpolation_active(self) -> bool:
        return is_pose_interpolation_active(self.get_output_frame_interpolation_multiplier())

    def on_output_frame_interpolation_changed(self, event: wx.Event):
        self.reset_frame_interpolation_buffers()
        self._sync_output_enhancement_config()
        self.save_persistent_ui_state()
        event.Skip()

    def on_mouth_infer_cap_changed(self, event: wx.Event):
        self._last_cached_affine_present_time_ns = None
        self.save_persistent_ui_state()
        event.Skip()

    def on_smooth_affine_30hz_changed(self, event: wx.Event):
        self._last_cached_affine_present_time_ns = None
        self.save_persistent_ui_state()
        event.Skip()

    def _choice_index_value(self, control, values, fallback):
        if isinstance(control, wx.Choice):
            index = control.GetSelection()
            if 0 <= index < len(values):
                return values[index]
        try:
            return control.GetValue()
        except Exception:
            return fallback

    def get_nn_super_resolution_mode(self) -> str:
        control = getattr(self, "nn_super_resolution_choice", None)
        return normalize_sr_mode(self._choice_index_value(control, NN_SR_VALUES, NN_SR_OFF))

    def get_nn_frame_interpolation_multiplier(self) -> int:
        control = getattr(self, "nn_frame_interpolation_choice", None)
        return normalize_nn_frame_multiplier(
            self._choice_index_value(control, NN_FRAME_INTERP_VALUES, NN_FRAME_INTERP_OFF))

    def get_nn_infer_backend(self) -> str:
        control = getattr(self, "nn_infer_backend_choice", None)
        return normalize_infer_backend(
            self._choice_index_value(control, INFER_BACKEND_VALUES, INFER_BACKEND_PYTORCH))

    def get_tha_infer_fp16_enabled(self) -> bool:
        if self.get_image_source_mode() == IMAGE_SOURCE_THA3:
            return False
        control = getattr(self, "tha_infer_fp16_choice", None)
        raw = self._choice_index_value(control, THA_INFER_FP16_CHOICES, THA_INFER_FP16_CHOICES[0])
        return normalize_tha_infer_fp16(raw) and not self._tha_infer_fp16_fallback

    def get_tha_infer_fp16_persisted_value(self) -> str:
        """User preference for persistence (ignores THA3 override and FP16 runtime fallback)."""
        fallback_raw = self.persistent_ui_state.get("tha_infer_fp16", "full")
        fallback_choice = (
            THA_INFER_FP16_CHOICES[1]
            if normalize_tha_infer_fp16(fallback_raw)
            else THA_INFER_FP16_CHOICES[0])
        control = getattr(self, "tha_infer_fp16_choice", None)
        raw = self._choice_index_value(control, THA_INFER_FP16_CHOICES, fallback_choice)
        return "half" if normalize_tha_infer_fp16(raw) else "full"

    def _apply_persisted_tha_infer_fp16_choice(self) -> None:
        half = normalize_tha_infer_fp16(
            self.persistent_ui_state.get("tha_infer_fp16", "full"))
        control = getattr(self, "tha_infer_fp16_choice", None)
        if control is None:
            return
        with block_events(self):
            if isinstance(control, wx.Choice):
                control.SetSelection(1 if half else 0)
            else:
                control.SetValue(THA_INFER_FP16_CHOICES[1 if half else 0])
        self._sync_tha_infer_fp16_ui()

    def _snapshot_enhancement_ui(self) -> dict:
        return {
            "nn_sr": snapshot_choice(getattr(self, "nn_super_resolution_choice", None)),
            "nn_rife": snapshot_choice(getattr(self, "nn_frame_interpolation_choice", None)),
            "nn_backend": snapshot_choice(getattr(self, "nn_infer_backend_choice", None)),
            "tha_fp16": snapshot_choice(getattr(self, "tha_infer_fp16_choice", None)),
            "pose_interp": snapshot_choice(getattr(self, "output_frame_interpolation_choice", None)),
        }

    def _restore_enhancement_ui(self, snap: dict) -> None:
        with block_events(self):
            restore_choice(getattr(self, "nn_super_resolution_choice", None), snap.get("nn_sr"))
            restore_choice(getattr(self, "nn_frame_interpolation_choice", None), snap.get("nn_rife"))
            restore_choice(getattr(self, "nn_infer_backend_choice", None), snap.get("nn_backend"))
            restore_choice(getattr(self, "tha_infer_fp16_choice", None), snap.get("tha_fp16"))
            restore_choice(getattr(self, "output_frame_interpolation_choice", None), snap.get("pose_interp"))

    def _validate_output_enhancement_switch(self) -> tuple[bool, str]:
        pipe = getattr(self, "output_enhancement", None)
        if pipe is None:
            return True, ""
        if not pipe.nn_modes_requested():
            return True, ""
        if not is_output_enhancement_installed():
            return False, "Install DEPLOY tier [5] output_enhancement for NN SR/RIFE."
        if not pipe.weights_available:
            return False, "NN weights missing under data/ezvtb_nn or addons/output_enhancement."
        backend = self.get_nn_infer_backend()
        if backend == INFER_BACKEND_PYTORCH:
            return False, (
                "NN super-resolution / RIFE need backend ONNX Runtime or TensorRT "
                "(PyTorch applies to THA Student FP16 only).")
        return True, ""

    def _apply_enhancement_ui_from_config(self, cfg: dict) -> None:
        with block_events(self):
            sr_control = getattr(self, "nn_super_resolution_choice", None)
            if isinstance(sr_control, wx.Choice):
                try:
                    sr_control.SetSelection(
                        NN_SR_VALUES.index(normalize_sr_mode(cfg.get("nn_super_resolution_mode"))))
                except ValueError:
                    sr_control.SetSelection(0)
            rife_control = getattr(self, "nn_frame_interpolation_choice", None)
            if isinstance(rife_control, wx.Choice):
                try:
                    rife_control.SetSelection(
                        NN_FRAME_INTERP_VALUES.index(
                            normalize_nn_frame_multiplier(
                                cfg.get("nn_frame_interpolation_multiplier"))))
                except ValueError:
                    rife_control.SetSelection(0)
            backend_control = getattr(self, "nn_infer_backend_choice", None)
            if isinstance(backend_control, wx.Choice):
                try:
                    backend_control.SetSelection(
                        INFER_BACKEND_VALUES.index(
                            normalize_infer_backend(cfg.get("nn_infer_backend"))))
                except ValueError:
                    backend_control.SetSelection(0)
        self._sync_output_enhancement_config()

    def _ui_alignment_toast(self, message: str) -> None:
        monitor = getattr(self, "_ui_alignment_monitor", None)
        if monitor is not None:
            monitor._show_toast(message)

    def _init_ui_alignment_monitor(self) -> None:
        self._ui_alignment_monitor = UiAlignmentMonitor(self)

        def _check_mocap():
            choice = getattr(self, "mocap_input_mode_choice", None)
            if choice is None or not isinstance(choice, wx.Choice):
                return None
            idx = choice.GetSelection()
            if idx < 0 or idx >= len(MOCAP_INPUT_MODE_VALUES):
                return None
            ui_mode = MOCAP_INPUT_MODE_VALUES[idx]
            runtime_mode = normalize_mocap_input_mode(getattr(self, "mocap_input_mode", ui_mode))
            if ui_mode == runtime_mode:
                return None
            return ("Face input mode", ui_mode, runtime_mode)

        def _revert_mocap():
            self.refresh_mocap_input_mode_ui()

        def _check_image_source():
            runtime = self.get_image_source_mode()
            choice = getattr(self, "image_source_mode_choice", None)
            if choice is not None and isinstance(choice, wx.Choice):
                idx = choice.GetSelection()
                ui_mode = IMAGE_SOURCE_THA3 if idx == 1 else IMAGE_SOURCE_THA4
                if ui_mode != runtime:
                    return ("Image source", ui_mode, runtime)
            persisted = normalize_image_source_mode(
                self.persistent_ui_state.get("image_source_mode", runtime))
            if persisted != runtime:
                return ("Image source (persisted)", persisted, runtime)
            return None

        def _revert_image_source():
            switch_image_source(self, self.get_image_source_mode(), autoload_asset=False)

        def _check_output_enhancement():
            pipe = getattr(self, "output_enhancement", None)
            if pipe is None:
                return None
            ui = (
                self.get_nn_super_resolution_mode(),
                self.get_nn_frame_interpolation_multiplier(),
                self.get_nn_infer_backend(),
            )
            cfg = pipe.get_config_snapshot()
            runtime = (
                normalize_sr_mode(cfg.get("nn_super_resolution_mode")),
                normalize_nn_frame_multiplier(cfg.get("nn_frame_interpolation_multiplier")),
                normalize_infer_backend(cfg.get("nn_infer_backend")),
            )
            if ui != runtime:
                return ("Output enhancement", str(ui), str(runtime))
            if pipe.nn_modes_requested() and not pipe.nn_runtime_ready():
                return ("Output enhancement ready", "on", "not ready")
            return None

        def _revert_output_enhancement():
            pipe = getattr(self, "output_enhancement", None)
            if pipe is None:
                return
            self._apply_enhancement_ui_from_config(pipe.get_config_snapshot())

        self._ui_alignment_monitor.register(AlignmentProbe(
            "mocap_input", "Face input mode", _check_mocap, _revert_mocap, load_budget_sec=30.0))
        self._ui_alignment_monitor.register(AlignmentProbe(
            "image_source", "Image source", _check_image_source, _revert_image_source,
            load_budget_sec=120.0))
        self._ui_alignment_monitor.register(AlignmentProbe(
            "output_enhancement", "Output enhancement", _check_output_enhancement,
            _revert_output_enhancement, load_budget_sec=600.0))
        self._ui_alignment_monitor.start()

    def _refresh_enhancement_controls(self) -> None:
        installed = is_output_enhancement_installed()
        for control in (
                getattr(self, "nn_super_resolution_choice", None),
                getattr(self, "nn_frame_interpolation_choice", None),
                getattr(self, "nn_infer_backend_choice", None)):
            if control is not None and isinstance(control, wx.Choice):
                control.Enable(installed)
        self._sync_tha_infer_fp16_ui()

    def _sync_tha_infer_fp16_ui(self) -> None:
        control = getattr(self, "tha_infer_fp16_choice", None)
        if control is None or not isinstance(control, wx.Choice):
            return
        tha3_mode = self.get_image_source_mode() == IMAGE_SOURCE_THA3
        control.Enable(not tha3_mode)

    def _maybe_warmup_output_enhancement(self) -> None:
        pipe = getattr(self, "output_enhancement", None)
        if pipe is None or not pipe.nn_modes_requested():
            return
        backend = self.get_nn_infer_backend()
        if backend == INFER_BACKEND_PYTORCH:
            self._warn_enhancement_once(
                "NN super-resolution / RIFE need backend ONNX Runtime or TensorRT "
                "(PyTorch applies to THA Student FP16 only).")
            return
        if not is_output_enhancement_installed():
            return
        warmup_key = (
            self.get_nn_super_resolution_mode(),
            self.get_nn_frame_interpolation_multiplier(),
            backend,
        )
        if warmup_key == self._enhancement_warmup_key:
            return
        self._enhancement_warmup_key = warmup_key
        self._sync_output_enhancement_config()

        def _task(progress):
            pipe.warmup(progress)

        def _on_complete():
            pass

        def _on_error(exc: Exception):
            self._enhancement_warmup_key = None
            snap = getattr(self, "_enhancement_switch_snapshot", None)
            if snap is not None:
                self._restore_enhancement_ui(snap)
                self._sync_output_enhancement_config()
            show_rate_limited_message(
                self.get_dialog_parent(),
                f"Output enhancement load failed: {exc}",
                "Output Enhancement",
                style=wx.OK | wx.ICON_WARNING,
                dialog_key="output_enhancement_load_failed",
                min_interval_sec=30.0)
            self._ui_alignment_toast(f"Output enhancement load failed: {exc}")

        run_slow_task(
            self.get_dialog_parent(),
            "Loading output enhancement…",
            _task,
            on_complete=_on_complete,
            on_error=_on_error)

    def _sync_output_enhancement_config(self) -> None:
        pipe = getattr(self, "output_enhancement", None)
        if pipe is None:
            return
        pipe.update_config({
            "antialias_strength": self._get_antialias_factor(),
            "output_frame_interpolation": self.get_output_frame_interpolation_multiplier(),
            "nn_super_resolution_mode": self.get_nn_super_resolution_mode(),
            "nn_frame_interpolation_multiplier": self.get_nn_frame_interpolation_multiplier(),
            "nn_infer_backend": self.get_nn_infer_backend(),
            "tha_infer_fp16": self.get_tha_infer_fp16_enabled(),
        })

    def _warn_enhancement_once(self, message: str) -> None:
        if self._enhancement_warned_once:
            return
        self._enhancement_warned_once = True
        show_rate_limited_message(
            self.get_dialog_parent(),
            message,
            "Output Enhancement",
            style=wx.OK | wx.ICON_INFORMATION,
            dialog_key="output_enhancement_missing",
            min_interval_sec=30.0)

    def on_output_enhancement_changed(self, event: wx.Event):
        if is_blocked(self):
            event.Skip()
            return

        def _apply():
            self._tha_infer_fp16_fallback = False
            if self.poser is not None and self.get_image_source_mode() == IMAGE_SOURCE_THA4:
                apply_poser_precision(self.poser, self.get_tha_infer_fp16_enabled())
            self._sync_output_enhancement_config()

        snap = self._snapshot_enhancement_ui()
        ok = run_guarded_switch(
            self,
            snapshot=lambda: snap,
            apply_fn=_apply,
            revert_fn=self._restore_enhancement_ui,
            validate=self._validate_output_enhancement_switch,
            on_fail=self._ui_alignment_toast)
        if not ok:
            event.Skip()
            return
        self._enhancement_switch_snapshot = snap
        self._maybe_warmup_output_enhancement()
        monitor = getattr(self, "_ui_alignment_monitor", None)
        if monitor is not None:
            monitor.notify_switch(["output_enhancement"])
        self.save_persistent_ui_state()
        event.Skip()

    def on_tha_infer_fp16_changed(self, event: wx.Event):
        self.on_output_enhancement_changed(event)

    def _apply_present_enhancement(self, present_rgba: numpy.ndarray) -> numpy.ndarray:
        pipe = getattr(self, "output_enhancement", None)
        if pipe is None or present_rgba is None:
            return present_rgba
        pending = pipe.pop_rife_frame()
        if pending is not None:
            return pending
        self._sync_output_enhancement_config()
        return pipe.apply(present_rgba, is_new_real_frame=True)

    def get_output_background_hex(self) -> str:
        picker = getattr(self, "output_background_choice", None)
        if picker is None:
            return "#000000"
        if isinstance(picker, wx.ColourPickerCtrl):
            try:
                colour = picker.GetColour()
                if isinstance(colour, wx.Colour) and colour.IsOk():
                    return "#{:02X}{:02X}{:02X}".format(colour.Red(), colour.Green(), colour.Blue())
            except Exception:
                pass
        try:
            value = picker.GetValue()
            return self.normalize_background_hex(value, "#000000")
        except Exception:
            return "#000000"

    def get_output_background_signature(self) -> str:
        mode = self.get_output_background_mode()
        if mode == OUTPUT_BACKGROUND_COLOR:
            return f"color:{self.get_output_background_hex()}"
        if mode == OUTPUT_BACKGROUND_IMAGE:
            return f"image:{self.resolve_output_background_image_path()}"
        if mode == OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE:
            return OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE
        return OUTPUT_BACKGROUND_TRANSPARENT

    def needs_alpha_result_bitmap(self) -> bool:
        # Always RGBA: 24-bit RGB + DrawBitmap(useAlpha=True) ghosts on colored backgrounds (Windows).
        return True

    def should_draw_result_bitmap_with_alpha(self) -> bool:
        return True

    def create_result_bitmap(self, width: int, height: int) -> wx.Bitmap:
        width = max(1, int(width))
        height = max(1, int(height))
        return self.create_rgba_bitmap_from_array(
            width, height, numpy.zeros((height, width, 4), dtype=numpy.uint8))

    @staticmethod
    def create_rgba_bitmap_from_array(width: int, height: int, rgba: numpy.ndarray) -> wx.Bitmap:
        width = max(1, int(width))
        height = max(1, int(height))
        rgba = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
        if rgba.shape != (height, width, 4):
            raise ValueError(f"expected RGBA shape ({height}, {width}, 4), got {rgba.shape}")
        return wx.Bitmap.FromBufferRGBA(width, height, rgba.tobytes())

    @staticmethod
    def wx_image_to_rgba_array(image: wx.Image) -> numpy.ndarray:
        width = max(1, image.GetWidth())
        height = max(1, image.GetHeight())
        rgb = numpy.frombuffer(image.GetData(), dtype=numpy.uint8).reshape(height, width, 3)
        if image.HasAlpha():
            alpha = numpy.frombuffer(image.GetAlpha(), dtype=numpy.uint8).reshape(height, width, 1)
        else:
            alpha = numpy.full((height, width, 1), 255, dtype=numpy.uint8)
        return numpy.concatenate([rgb, alpha], axis=2)

    def build_output_background_rgba(self, width: int, height: int) -> numpy.ndarray:
        width = max(1, int(width))
        height = max(1, int(height))
        mode = self.get_output_background_mode()
        if mode == OUTPUT_BACKGROUND_TRANSPARENT:
            return numpy.zeros((height, width, 4), dtype=numpy.uint8)
        if mode == OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE:
            rgba = numpy.zeros((height, width, 4), dtype=numpy.uint8)
            grey = 180
            rgba[:, :, 0:3] = grey
            rgba[:, :, 3] = 255
            return rgba
        if mode == OUTPUT_BACKGROUND_COLOR:
            colour = self.get_output_background_color()
            rgba = numpy.zeros((height, width, 4), dtype=numpy.uint8)
            rgba[:, :, 0] = colour.Red()
            rgba[:, :, 1] = colour.Green()
            rgba[:, :, 2] = colour.Blue()
            rgba[:, :, 3] = 255
            return rgba
        background_image = self.load_output_background_image(width, height)
        if background_image is None:
            return numpy.zeros((height, width, 4), dtype=numpy.uint8)
        return self.wx_image_to_rgba_array(background_image)

    def _compose_ulw_background_rgba(
            self, canvas_width: int, canvas_height: int) -> Optional[numpy.ndarray]:
        """Opaque background plate composited UNDER the character for the unified
        ULW output. Returns None in 真透 (transparent_capture) mode so the ULW
        keeps per-pixel alpha; color/image/黑键 return a fully-opaque plate."""
        mode = self.get_output_background_mode()
        if mode == OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE:
            return None
        width = max(1, int(canvas_width))
        height = max(1, int(canvas_height))
        cache_key = (mode, self.get_output_background_signature(), width, height)
        if getattr(self, "_cached_ulw_bg_key", None) == cache_key:
            cached = getattr(self, "_cached_ulw_bg_rgba", None)
            if cached is not None:
                return cached
        plate = self._build_ulw_background_plate(mode, width, height)
        self._cached_ulw_bg_key = cache_key
        self._cached_ulw_bg_rgba = plate
        return plate

    def _build_ulw_background_plate(
            self, mode: str, width: int, height: int) -> numpy.ndarray:
        if mode == OUTPUT_BACKGROUND_COLOR:
            colour = self.get_output_background_color()
            if colour is None or not colour.IsOk():
                colour = wx.Colour(0, 0, 0)
            rgba = numpy.empty((height, width, 4), dtype=numpy.uint8)
            rgba[:, :, 0] = colour.Red()
            rgba[:, :, 1] = colour.Green()
            rgba[:, :, 2] = colour.Blue()
            rgba[:, :, 3] = 255
            return rgba
        if mode == OUTPUT_BACKGROUND_IMAGE:
            image = self.load_output_background_image(width, height)
            if image is not None and image.IsOk():
                rgba = numpy.ascontiguousarray(
                    self.wx_image_to_rgba_array(image), dtype=numpy.uint8).copy()
                rgba[:, :, 3] = 255
                return rgba
        # 黑键 / Color Key (and image-missing fallback): opaque black plate so
        # WGC + colour-key capture tools can key it out.
        r, g, b = OUTPUT_CAPTURE_COLORKEY_RGB
        rgba = numpy.empty((height, width, 4), dtype=numpy.uint8)
        rgba[:, :, 0] = r
        rgba[:, :, 1] = g
        rgba[:, :, 2] = b
        rgba[:, :, 3] = 255
        return rgba

    def clear_result_image_bitmap(self, width: int, height: int) -> None:
        """Hard-reset output buffer. MemoryDC Clear() does not zero alpha on Windows."""
        width = max(1, int(width))
        height = max(1, int(height))
        rgba = self.build_output_background_rgba(width, height)
        self.result_image_bitmap = self.create_rgba_bitmap_from_array(width, height, rgba)

    def get_output_frame_paint_colour(self) -> wx.Colour:
        mode = self.get_output_background_mode()
        if mode == OUTPUT_BACKGROUND_COLOR:
            return self.get_output_background_color()
        if mode == OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE:
            return wx.Colour(180, 180, 180)
        if mode == OUTPUT_BACKGROUND_TRANSPARENT:
            r, g, b = OUTPUT_CAPTURE_COLORKEY_RGB
            return wx.Colour(r, g, b)
        return wx.Colour(180, 180, 180)

    def get_layer_selection_highlight_colour(
            self, canvas_width: int, canvas_height: int) -> wx.Colour:
        mode = self.get_output_background_mode()
        if mode == OUTPUT_BACKGROUND_COLOR:
            colour = self.get_output_background_color()
            if colour is None or not colour.IsOk():
                colour = wx.Colour(0, 0, 0)
            return contrast_highlight_colour(colour.Red(), colour.Green(), colour.Blue())
        if mode == OUTPUT_BACKGROUND_IMAGE:
            image = self.load_output_background_image(canvas_width, canvas_height)
            if image is not None and image.IsOk():
                cx = max(0, image.GetWidth() // 2)
                cy = max(0, image.GetHeight() // 2)
                return contrast_highlight_colour(
                    image.GetRed(cx, cy),
                    image.GetGreen(cx, cy),
                    image.GetBlue(cx, cy))
        paint = self.get_output_frame_paint_colour()
        return contrast_highlight_colour(paint.Red(), paint.Green(), paint.Blue())

    def get_character_edge_mode(self) -> str:
        choice = getattr(self, "character_edge_mode_choice", None)
        if isinstance(choice, wx.Choice):
            index = choice.GetSelection()
            if index < 0:
                index = 0
            if index >= len(CHARACTER_EDGE_MODE_VALUES):
                index = len(CHARACTER_EDGE_MODE_VALUES) - 1
            return CHARACTER_EDGE_MODE_VALUES[index]
        return normalize_character_edge_mode(
            str(self.persistent_ui_state.get("character_edge_mode", CHARACTER_EDGE_NONE)))

    def get_character_edge_width(self) -> float:
        spin = getattr(self, "character_edge_width_spin", None)
        if isinstance(spin, wx.SpinCtrlDouble):
            return clamp_character_edge_width(spin.GetValue())
        if isinstance(spin, wx.SpinCtrl):
            return clamp_character_edge_width(float(spin.GetValue()))
        try:
            return clamp_character_edge_width(
                float(self.persistent_ui_state.get(
                    "character_edge_width", CHARACTER_EDGE_WIDTH_DEFAULT)))
        except (TypeError, ValueError):
            return float(CHARACTER_EDGE_WIDTH_DEFAULT)

    def get_character_edge_colour(self) -> wx.Colour:
        picker = getattr(self, "character_edge_colour_picker", None)
        if isinstance(picker, wx.ColourPickerCtrl):
            colour = picker.GetColour()
            if colour.IsOk():
                return colour
        hex_value = str(self.persistent_ui_state.get("character_edge_color_hex") or "#FFFFFF")
        return wx.Colour(self.normalize_background_hex(hex_value, "#FFFFFF"))

    def update_character_edge_controls_visibility(self) -> None:
        mode = self.get_character_edge_mode()
        style_panel = getattr(self, "character_edge_style_panel", None)
        if style_panel is None:
            return
        show_width = mode == CHARACTER_EDGE_OUTLINE
        show_colour = mode == CHARACTER_EDGE_OUTLINE
        width_row = getattr(self, "character_edge_width_row_panel", None)
        colour_row = getattr(self, "character_edge_colour_row_panel", None)
        if width_row is not None:
            width_row.Show(show_width)
        if colour_row is not None:
            colour_row.Show(show_colour)
        style_panel.Show(mode != CHARACTER_EDGE_NONE)
        style_panel.Layout()
        postprocess_panel = getattr(self, "postprocess_panel", None)
        if postprocess_panel is not None:
            postprocess_panel.Layout()
        wx.CallAfter(self.schedule_postprocess_layout_refresh)

    def on_character_edge_setting_changed(self, event: Optional[wx.Event] = None) -> None:
        mode = self.get_character_edge_mode()
        self.character_edge_mode_state.SetValue(mode)
        self._last_compose_signature = None
        self.update_character_edge_controls_visibility()
        self.save_persistent_ui_state()
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
        if event is not None:
            event.Skip()

    def _apply_character_edge_postprocess_rgba(self, rgba: numpy.ndarray) -> numpy.ndarray:
        mode = self.get_character_edge_mode()
        if mode == CHARACTER_EDGE_NONE:
            return rgba
        width = self.get_character_edge_width()
        background_rgb = self._edge_postprocess_background_rgb()
        outline = self.get_character_edge_colour()
        outline_rgb = (outline.Red(), outline.Green(), outline.Blue())
        return apply_character_edge_postprocess(
            rgba,
            mode,
            width=width,
            outline_rgb=outline_rgb,
            background_rgb=background_rgb)

    def _apply_character_edge_postprocess(self, character_bitmap: wx.Bitmap) -> wx.Bitmap:
        if not character_bitmap.IsOk():
            return character_bitmap
        mode = self.get_character_edge_mode()
        if mode == CHARACTER_EDGE_NONE:
            return character_bitmap
        width = self.get_character_edge_width()
        background_rgb = self._edge_postprocess_background_rgb()
        outline = self.get_character_edge_colour()
        outline_rgb = (outline.Red(), outline.Green(), outline.Blue())
        rgba = self.wx_bitmap_to_rgba_array(character_bitmap, preserve_color=True)
        rgba = apply_character_edge_postprocess(
            rgba,
            mode,
            width=width,
            outline_rgb=outline_rgb,
            background_rgb=background_rgb)
        return self.create_rgba_bitmap_from_array(
            character_bitmap.GetWidth(),
            character_bitmap.GetHeight(),
            rgba)

    @staticmethod
    def clean_wx_image_transparent_rgb(image: wx.Image) -> wx.Image:
        if not image.HasAlpha():
            return image
        rgba = MainFrame.wx_image_to_rgba_array(image)
        transparent = rgba[:, :, 3] == 0
        if not numpy.any(transparent):
            return image
        rgba[transparent, 0:3] = 0
        width = max(1, image.GetWidth())
        height = max(1, image.GetHeight())
        return wx.ImageFromBuffer(
            width,
            height,
            rgba[:, :, 0:3].tobytes(),
            rgba[:, :, 3].tobytes())

    def _edge_postprocess_background_rgb(self) -> tuple[int, int, int]:
        """Fringe bake colour: black for transparent/capture paths, panel paint otherwise."""
        mode = self.get_output_background_mode()
        if mode in (OUTPUT_BACKGROUND_TRANSPARENT, OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE):
            return OUTPUT_CAPTURE_COLORKEY_RGB
        paint = self.get_output_frame_paint_colour()
        return paint.Red(), paint.Green(), paint.Blue()

    @staticmethod
    def _wx_bitmap_to_rgba_via_png(bitmap: wx.Bitmap) -> Optional[numpy.ndarray]:
        """PNG round-trip preserves colour on Windows MemoryDC 32bpp bitmaps."""
        if not bitmap.IsOk():
            return None
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            if not bitmap.SaveFile(temp_path, wx.BITMAP_TYPE_PNG):
                return None
            with PIL.Image.open(temp_path) as pil_image:
                return numpy.ascontiguousarray(pil_image.convert("RGBA"), dtype=numpy.uint8)
        except Exception:
            return None
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    @staticmethod
    def _wx_image_is_greyscale(image: wx.Image) -> bool:
        for name in ("IsGreyscale", "IsGreyScale"):
            fn = getattr(image, name, None)
            if callable(fn):
                try:
                    return bool(fn())
                except Exception:
                    pass
        return False

    @staticmethod
    def wx_bitmap_to_rgba_array(
            bitmap: wx.Bitmap,
            *,
            preserve_color: bool = False) -> numpy.ndarray:
        if not bitmap.IsOk():
            raise ValueError("invalid wx.Bitmap")
        if preserve_color:
            rgba = MainFrame._wx_bitmap_to_rgba_via_png(bitmap)
            if rgba is not None:
                return rgba
        image = bitmap.ConvertToImage()
        if MainFrame._wx_image_is_greyscale(image):
            rgba = MainFrame._wx_bitmap_to_rgba_via_png(bitmap)
            if rgba is not None:
                return rgba
        try:
            return MainFrame.wx_image_to_rgba_array(image)
        except Exception:
            rgba = MainFrame._wx_bitmap_to_rgba_via_png(bitmap)
            if rgba is not None:
                return rgba
            raise

    @staticmethod
    def composite_rgba_over_background(background_rgba: numpy.ndarray,
                                       foreground_bitmap: wx.Bitmap) -> numpy.ndarray:
        """Source-over composite; alpha=0 foreground pixels leave background unchanged."""
        fg = MainFrame.wx_bitmap_to_rgba_array(foreground_bitmap)
        if fg.shape != background_rgba.shape:
            raise ValueError(
                f"foreground {fg.shape} != background {background_rgba.shape}")
        return composite_rgba_arrays(background_rgba, fg)

    def sanitize_result_bitmap_alpha_fringe(self) -> None:
        self._sanitize_result_bitmap_once()

    def sanitize_result_bitmap_for_obs_capture(self) -> None:
        pass

    def paint_output_background(self, dc: wx.DC, size: wx.Size):
        width = max(1, int(size.width))
        height = max(1, int(size.height))
        mode = self.get_output_background_mode()
        if mode == OUTPUT_BACKGROUND_TRANSPARENT:
            r, g, b = OUTPUT_CAPTURE_COLORKEY_RGB
            dc.SetBackground(wx.Brush(wx.Colour(r, g, b)))
            dc.Clear()
            return
        if mode == OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE:
            dc.SetBackground(wx.Brush(self.get_output_frame_paint_colour()))
            dc.Clear()
            return
        if mode == OUTPUT_BACKGROUND_COLOR:
            dc.SetBackground(wx.Brush(self.get_output_background_color()))
            dc.Clear()
            return
        background_image = self.load_output_background_image(width, height)
        if background_image is None:
            dc.SetBackground(wx.TRANSPARENT_BRUSH)
            dc.Clear()
            return
        dc.DrawBitmap(background_image.ConvertToBitmap(), 0, 0, True)

    def update_output_background_controls_visibility(self):
        mode = self.get_output_background_mode()
        colour_picker = getattr(self, "output_background_choice", None)
        image_panel = getattr(self, "output_background_image_panel", None)
        obs_hint = getattr(self, "output_obs_capture_hint", None)
        capture_hint = getattr(self, "output_transparent_capture_hint", None)
        if colour_picker is not None and isinstance(colour_picker, wx.ColourPickerCtrl):
            colour_picker.Show(mode == OUTPUT_BACKGROUND_COLOR)
        if image_panel is not None:
            image_panel.Show(mode == OUTPUT_BACKGROUND_IMAGE)
        if obs_hint is not None:
            obs_hint.Show(mode == OUTPUT_BACKGROUND_TRANSPARENT)
        if capture_hint is not None:
            capture_hint.Show(mode == OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE)
        postprocess_panel = getattr(self, "postprocess_panel", None)
        if postprocess_panel is not None:
            postprocess_panel.Layout()
        wx.CallAfter(self.schedule_postprocess_layout_refresh)

    def notify_output_background_changed(self):
        self.last_background_choice = ""
        self.invalidate_output_background_image_cache()
        self.refresh_output_frame_chrome()
        self.update_output_background_controls_visibility()
        self.sync_transparent_capture_output_window()
        self.save_persistent_ui_state()
        if self.poser is None:
            return
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
            self._maybe_schedule_transparent_capture_update(immediate=True)
            return
        if self.mediapipe_face_pose is None:
            self.render_default_pose_load_preview()
        else:
            self.update_result_image_bitmap()

    def destroy_transparent_capture_window(self) -> None:
        capture_window = getattr(self, "transparent_capture_window", None)
        if capture_window is None:
            return
        try:
            capture_window.destroy()
        except Exception:
            pass
        self.transparent_capture_window = None

    def default_capture_output_frame_rect_beside_output(self) -> wx.Rect:
        locked_w, locked_h = self.get_locked_output_client_size()
        capture_size = wx.Size(locked_w, locked_h)
        if getattr(self, "output_frame", None) is not None and self.output_frame.IsShown():
            output_rect = self.output_frame.GetRect()
            x = output_rect.x + output_rect.width + 16
            y = output_rect.y
            return self.clamp_client_rect_to_visible_screen(
                wx.Rect(x, y, capture_size.x, capture_size.y))
        return self.clamp_client_rect_to_visible_screen(wx.Rect(100, 100, capture_size.x, capture_size.y))

    def apply_capture_output_frame_state(self) -> None:
        capture_window = getattr(self, "transparent_capture_window", None)
        if capture_window is None or not capture_window.is_valid():
            return
        locked_w, locked_h = self.get_locked_output_client_size()
        saved_rect = self.get_saved_client_rect("capture_output_frame")
        if saved_rect is None:
            saved_rect = self.default_capture_output_frame_rect_beside_output()
        clamped_rect = self.clamp_client_rect_to_visible_screen(
            wx.Rect(saved_rect.x, saved_rect.y, locked_w, locked_h))
        capture_window.set_position(clamped_rect.x, clamped_rect.y)

    def schedule_capture_output_geometry_save(self) -> None:
        if self._is_closing or self._restoring_window_geometry:
            return
        self._capture_geometry_save_pending = True
        wx.CallLater(250, self.process_capture_output_geometry_save)

    def process_capture_output_geometry_save(self) -> None:
        self._capture_geometry_save_pending = False
        if self._is_closing or self._restoring_window_geometry:
            return
        capture_window = getattr(self, "transparent_capture_window", None)
        if capture_window is None or not capture_window.is_valid():
            return
        x, y, width, height = capture_window.get_rect()
        locked_w, locked_h = self.get_locked_output_client_size()
        clamped_rect = self.clamp_client_rect_to_visible_screen(
            wx.Rect(x, y, locked_w, locked_h))
        self.persistent_ui_state["capture_output_frame_x"] = clamped_rect.x
        self.persistent_ui_state["capture_output_frame_y"] = clamped_rect.y
        self.persistent_ui_state["capture_output_frame_w"] = clamped_rect.width
        self.persistent_ui_state["capture_output_frame_h"] = clamped_rect.height
        self.save_persistent_ui_state()

    def sync_transparent_capture_output_window(self) -> None:
        wx.CallAfter(self._sync_transparent_capture_output_window_impl)

    def _sync_transparent_capture_output_window_impl(self) -> None:
        if self._is_closing:
            return
        if getattr(self, "_controls_build_in_progress", False):
            wx.CallLater(150, self.sync_transparent_capture_output_window)
            return
        self.update_output_window_visibility()
        if not self.is_ulw_output_enabled():
            capture_window = getattr(self, "transparent_capture_window", None)
            if capture_window is not None:
                capture_window.hide()
            return
        locked_w, locked_h = self.get_locked_output_client_size()
        capture_window = getattr(self, "transparent_capture_window", None)
        if capture_window is None or not capture_window.is_valid():
            if getattr(self, "_creating_transparent_capture_window", False):
                return
            self._creating_transparent_capture_window = True
            try:
                self.transparent_capture_window = TransparentCaptureWindow(
                    locked_w,
                    locked_h,
                    on_geometry_changed=self.schedule_capture_output_geometry_save,
                    on_edit_begin=self._overlay_edit_begin,
                    on_edit_motion=self._overlay_edit_motion,
                    on_edit_end=self._overlay_edit_end,
                    on_key_nudge=self._overlay_key_nudge,
                    on_deactivate=self._overlay_deactivated,
                )
            except Exception:
                self.transparent_capture_window = None
                return
            finally:
                self._creating_transparent_capture_window = False
            self.apply_capture_output_frame_state()
        else:
            self.apply_capture_output_frame_state()
        capture_window = getattr(self, "transparent_capture_window", None)
        if capture_window is not None and capture_window.is_valid():
            capture_window.show()
            if self.last_output_wx_image is not None:
                self._maybe_schedule_transparent_capture_update(immediate=True)

    def update_output_window_visibility(self) -> None:
        """The layered ULW (easyvtuberstudio_output) is the sole on-screen output
        + edit surface for every background mode now, so the wx OutputFrame is
        always hidden (retired as an output surface)."""
        output_frame = getattr(self, "output_frame", None)
        if output_frame is None:
            return
        try:
            if self.is_ulw_output_enabled():
                if output_frame.IsShown():
                    output_frame.Hide()
            elif not output_frame.IsShown():
                output_frame.Show(True)
                self.uniconize_window(output_frame)
        except RuntimeError:
            pass

    def _overlay_canvas_size(self) -> tuple[int, int]:
        return self.get_output_canvas_size()

    def _overlay_edit_begin(self, x: int, y: int) -> bool:
        """ULW WNDPROC router: try to start a layer edit at canvas-pixel (x,y).
        Returns True only when a selected layer's handle/body was hit (so the
        overlay edits instead of dragging the window)."""
        canvas_w, canvas_h = self._overlay_canvas_size()
        return self.begin_layer_edit_at(x, y, canvas_w, canvas_h)

    def _overlay_edit_motion(self, x: int, y: int) -> None:
        # _apply_layer_edit_motion -> on_layer_state_changed already pushes the
        # ULW frame; no extra schedule needed here.
        self.apply_layer_edit_at(x, y)

    def _overlay_edit_end(self) -> None:
        # _end_layer_edit only persists state (no on_layer_state_changed), so
        # push one final frame so the selection chrome/handle settles.
        self.end_layer_edit_external()
        self._maybe_schedule_transparent_capture_update(immediate=True)

    def _overlay_key_nudge(self, dx: float, dy: float) -> bool:
        # nudge_selected_layer -> on_layer_state_changed pushes the ULW frame.
        return self.nudge_selected_layer(dx, dy)

    def _overlay_deactivated(self) -> None:
        # The ULW lost activation (user clicked away). Run the same deselect
        # check the wx windows use on deactivate: selection is kept only when
        # the new focus is the layer window or the ULW itself, so clicking the
        # desktop / another app drops it. CallAfter lets the new foreground
        # settle before _is_layer_editing_focus_window() inspects it.
        if self._is_closing:
            return
        wx.CallAfter(self._maybe_clear_layer_selection_after_deactivate)

    def _refresh_transparent_capture_frame(self) -> None:
        if not self.is_ulw_output_enabled():
            return
        self._push_transparent_capture_from_cache()

    def _push_transparent_capture_from_cache(self) -> None:
        if self._is_closing or not self.is_ulw_output_enabled():
            return
        capture_window = getattr(self, "transparent_capture_window", None)
        if capture_window is None or not capture_window.is_valid():
            return
        if self.last_output_wx_image is None:
            return
        try:
            canvas_width, canvas_height = self.get_output_canvas_size()
            capture_t0 = time.perf_counter()
            signature = (
                self._last_compose_signature,
                canvas_width,
                canvas_height,
                self.is_layer_blend_enabled(),
                self.basic_layers_state.selected_slot_id,
            )
            cached = self._cached_capture_foreground_rgba
            if (
                    cached is not None
                    and self._cached_capture_foreground_signature == signature
                    and cached.shape[0] == canvas_height
                    and cached.shape[1] == canvas_width):
                capture_window.update_frame_rgba(cached, frame_signature=signature)
                self._on_ulw_frame_delivered()
                _perf_record(capture_ms=(time.perf_counter() - capture_t0) * 1000.0)
                return
            # Single-composite source of truth: reuse the exact RGBA the present
            # path produced this frame (no wx readback, no second composite).
            rgba = self._cached_present_rgba
            if (rgba is None
                    or rgba.shape[0] != canvas_height
                    or rgba.shape[1] != canvas_width):
                rgba = self._compose_present_rgba(canvas_width, canvas_height)
            if rgba is None:
                return
            self._cached_capture_foreground_rgba = rgba
            self._cached_capture_foreground_signature = signature
            if getattr(self, "_capture_async_active", False):
                return
            self._capture_async_active = True
            threading.Thread(
                target=self._async_premultiply_and_deliver,
                args=(signature, rgba, capture_t0),
                daemon=True,
                name="capture-premultiply").start()
        except Exception as exc:
            _err_record(
                "H-CAP",
                "character_model_mediapipe_puppeteer_load_preview.py:_push_transparent_capture_from_cache",
                exc)
            self._capture_async_active = False

    def _async_premultiply_and_deliver(
            self,
            signature: tuple,
            rgba: numpy.ndarray,
            capture_t0: float) -> None:
        try:
            premultiplied_bgra = _straight_rgba_to_premultiplied_bgra(rgba)
        except Exception:
            premultiplied_bgra = None
        wx.CallAfter(
            self._deliver_capture_premultiplied,
            signature,
            rgba,
            premultiplied_bgra,
            capture_t0)

    def _deliver_capture_premultiplied(
            self,
            signature: tuple,
            rgba: numpy.ndarray,
            premultiplied_bgra: Optional[numpy.ndarray],
            capture_t0: float) -> None:
        self._capture_async_active = False
        if self._is_closing or not self.is_ulw_output_enabled():
            return
        capture_window = getattr(self, "transparent_capture_window", None)
        if capture_window is None or not capture_window.is_valid():
            return
        try:
            capture_window.update_frame_rgba(
                rgba,
                frame_signature=signature,
                premultiplied_bgra=premultiplied_bgra)
            self._on_ulw_frame_delivered()
            _perf_record(capture_ms=(time.perf_counter() - capture_t0) * 1000.0)
        except Exception as exc:
            _err_record(
                "H-CAP",
                "character_model_mediapipe_puppeteer_load_preview.py:_deliver_capture_premultiplied",
                exc)

    def _maybe_schedule_transparent_capture_update(self, *, immediate: bool = False) -> None:
        if not self.is_ulw_output_enabled():
            return
        if self.last_output_wx_image is None:
            return
        if not immediate and not self.should_refresh_transparent_capture():
            return
        if getattr(self, "_capture_update_pending", False):
            return
        self._capture_update_pending = True
        wx.CallAfter(self._run_transparent_capture_update)

    def _run_transparent_capture_update(self) -> None:
        self._capture_update_pending = False
        if self._is_closing or not self.is_ulw_output_enabled():
            return
        self._push_transparent_capture_from_cache()

    @staticmethod
    def sanitize_rgba_alpha_fringe(rgba: numpy.ndarray) -> numpy.ndarray:
        rgba = numpy.ascontiguousarray(rgba, dtype=numpy.uint8)
        transparent = rgba[:, :, 3] == 0
        if numpy.any(transparent):
            rgba = rgba.copy()
            rgba[transparent, 0:3] = 0
        return rgba

    def compose_edit_chrome_rgba(
            self,
            canvas_width: int,
            canvas_height: int) -> Optional[numpy.ndarray]:
        """Transparent RGBA overlay carrying the selection box + resize handle
        for the currently selected layer, or None when nothing is selected
        (the edit/live gate: clean output when no selection).

        This is the chrome layer the layered output window stacks on top of the
        clean (captured) output. Geometry reuses the same resolved rect/rotation
        as compositing so it lines up exactly.
        """
        if not self.is_layer_blend_enabled():
            self._last_edit_chrome_geom = None
            return None
        selected = self._output_edit_slot_id()
        if selected is None:
            self._last_edit_chrome_geom = None
            return None
        canvas_width = max(1, int(canvas_width))
        canvas_height = max(1, int(canvas_height))
        binding_context = self._make_binding_context(canvas_width, canvas_height)
        layer = self.basic_layers_state.get_slot(selected)
        try:
            colour = self.get_layer_selection_highlight_colour(
                canvas_width, canvas_height)
            highlight = (colour.Red(), colour.Green(), colour.Blue())
        except Exception:
            highlight = DEFAULT_HIGHLIGHT_RGB

        if layer_uses_orbit_edit_chrome(layer):
            orbit_geom = compute_orbit_edit_geometry(
                self.basic_layers_state,
                layer,
                self.layer_asset_cache.load_image,
                canvas_width,
                canvas_height,
                binding_context)
            if orbit_geom is None:
                self._last_edit_chrome_geom = None
                return None
            self._last_edit_chrome_geom = orbit_geom
            return render_orbit_edit_chrome_rgba(
                canvas_width,
                canvas_height,
                orbit_geom.path_points,
                orbit_geom.pivot_xy,
                orbit_geom.bind_xy,
                highlight_rgb=highlight)

        resolved = resolve_layer_rects(
            self.basic_layers_state,
            self.layer_asset_cache.load_image,
            canvas_width,
            canvas_height,
            binding_context,
            include_motion=False)
        rect = resolved.get(selected)
        if rect is None:
            self._last_edit_chrome_geom = None
            return None
        rotation_deg = resolved_layer_rotation_deg(
            layer, self.basic_layers_state, rect, binding_context)
        # Cache the exact drawn box so the layered-output hit-test can match the
        # on-screen highlight pixel-for-pixel (re-resolving would advance the
        # stateful binding smoother / motion_time_s and drift bound layers,
        # making clicks miss and drag the window instead of the layer).
        self._last_edit_chrome_geom = (
            int(selected), rect, float(rotation_deg),
            int(canvas_width), int(canvas_height))
        return render_selection_chrome_rgba(
            canvas_width,
            canvas_height,
            (rect.draw_x, rect.draw_y, rect.draw_width, rect.draw_height),
            rotation_deg=rotation_deg,
            highlight_rgb=highlight)

    def compose_output_stack_rgba(
            self,
            canvas_width: int,
            canvas_height: int) -> Optional[numpy.ndarray]:
        """wx-free full output composite: enhanced character keyframe + layer
        stack, all in numpy (no wx.DC). Returns transparent-background straight
        RGBA, or None when no keyframe is cached yet.

        This is the unified render entry the capture path (and the future
        ctypes layered output window) consume so enhancement and multi-layer
        compositing share one numpy geometry/blend source of truth.
        """
        if self.output_enhancement.keyframe_cache.rgba is None:
            return None
        canvas_width = max(1, int(canvas_width))
        canvas_height = max(1, int(canvas_height))
        antialias_factor = self._get_antialias_factor()
        c0 = time.perf_counter()
        character_rgba = self._compose_character_rgba_from_keyframe(
            canvas_width, canvas_height, antialias_factor)
        c1 = time.perf_counter()
        character_rgba = self._apply_character_edge_postprocess_rgba(character_rgba)
        c2 = time.perf_counter()
        if self.is_layer_blend_enabled():
            binding_context = self._make_binding_context(canvas_width, canvas_height)
            fg = compose_full_stack_rgba(
                self.basic_layers_state,
                self.layer_asset_cache.load_image_rgba,
                canvas_width,
                canvas_height,
                character_rgba,
                binding_context)
        else:
            fg = character_rgba
        c3 = time.perf_counter()
        result = self.sanitize_rgba_alpha_fringe(fg)
        c4 = time.perf_counter()
        self._compose_stack_substages = {
            "char": (c1 - c0) * 1000.0,
            "edge": (c2 - c1) * 1000.0,
            "layers": (c3 - c2) * 1000.0,
            "sanitize": (c4 - c3) * 1000.0,
        }
        return result

    def _push_transparent_capture_foreground(self, foreground_rgba: numpy.ndarray) -> None:
        if self._is_closing or not self.is_ulw_output_enabled():
            return
        capture_window = getattr(self, "transparent_capture_window", None)
        if capture_window is None or not capture_window.is_valid():
            return
        try:
            capture_window.update_frame_rgba(foreground_rgba)
        except Exception:
            pass

    def refresh_output_frame_chrome(self):
        if getattr(self, "output_frame", None) is None:
            return
        paint_colour = self.get_output_frame_paint_colour()
        self.output_frame.SetBackgroundColour(paint_colour)
        self.output_frame.result_image_panel.SetBackgroundColour(paint_colour)
        locked_w, locked_h = self.get_locked_output_client_size()
        locked_size = wx.Size(locked_w, locked_h)
        self.output_frame.SetMinClientSize(locked_size)
        self.output_frame.SetMaxClientSize(locked_size)
        if self.output_frame.GetClientSize() != locked_size:
            self.output_frame.SetClientSize(locked_size)

    def collect_window_client_rect(self, window: wx.Window, prefix: str) -> dict:
        position = window.GetPosition()
        if prefix == "output_frame":
            client_width, client_height = self.get_locked_output_client_size()
        else:
            client_size = window.GetClientSize()
            if client_size.x <= 0 or client_size.y <= 0:
                return {}
            client_width = client_size.x
            client_height = client_size.y
        clamped_rect = self.clamp_client_rect_to_visible_screen(
            wx.Rect(position.x, position.y, client_width, client_height))
        return {
            f"{prefix}_x": clamped_rect.x,
            f"{prefix}_y": clamped_rect.y,
            f"{prefix}_w": clamped_rect.width,
            f"{prefix}_h": clamped_rect.height,
        }

    def is_window_rect_mostly_visible(self, window: wx.Window) -> bool:
        window_rect = window.GetRect()
        if window_rect.width <= 0 or window_rect.height <= 0:
            return False
        visible_area = 0
        for display_index in range(wx.Display.GetCount()):
            display = wx.Display(display_index)
            visible_area += self._rect_intersection_area(window_rect, display.GetClientArea())
        return visible_area >= max(1, window_rect.width * window_rect.height // 4)

    def apply_frame_geometry_from_storage(self,
                                          window: wx.Window,
                                          prefix: str,
                                          min_client_size: wx.Size,
                                          default_client_size: Optional[wx.Size] = None) -> bool:
        saved_rect = self.get_saved_client_rect(prefix)
        if saved_rect is not None:
            self.apply_client_rect_to_window(window, saved_rect, min_client_size)
            if self.is_window_rect_mostly_visible(window):
                return True
        if default_client_size is None:
            default_client_size = min_client_size
        self._restoring_window_geometry = True
        try:
            window.SetMinClientSize(min_client_size)
            window.SetClientSize(default_client_size)
            window.CenterOnScreen()
            window.Layout()
        finally:
            self._restoring_window_geometry = False
        return False

    def default_output_frame_rect_beside_controls(self) -> wx.Rect:
        locked_w, locked_h = self.get_locked_output_client_size()
        output_size = wx.Size(locked_w, locked_h)
        controls_window = self.get_controls_window()
        if controls_window is not None and controls_window.IsShown():
            controls_rect = controls_window.GetRect()
            x = controls_rect.x + controls_rect.width + 16
            y = controls_rect.y
            return self.clamp_client_rect_to_visible_screen(wx.Rect(x, y, output_size.x, output_size.y))
        return self.clamp_client_rect_to_visible_screen(wx.Rect(0, 0, output_size.x, output_size.y))

    def uniconize_window(self, window: wx.Window):
        try:
            window.Iconize(False)
        except Exception:
            pass

    def ensure_application_windows_visible(self, *, defer_ulw_sync: bool = False):
        ensure_start = time.perf_counter()
        if self.full_controls_expanded:
            self.create_controls_frame()
            if self.controls_frame is None:
                self.Show(True)
                self.Raise()
                return
            min_controls_size = self.get_controls_min_client_size()
            default_controls_size = wx.Size(
                max(min_controls_size.x, 1180),
                max(min_controls_size.y, 760))
            self.apply_frame_geometry_from_storage(
                self.controls_frame, "controls_frame", min_controls_size, default_controls_size)
            self.apply_controls_window_size_policy(self.controls_frame)

            # --- Output window FIRST ---
            # Live-streaming capture tools remember a source by window title/order,
            # so the stable-titled output window must exist and become visible
            # before the controls and layer windows. In 真透 (true-transparent)
            # mode the output is the ULW (+ its border); otherwise it is the wx
            # OutputFrame.
            self.ensure_output_frame()
            locked_w, locked_h = self.get_locked_output_client_size()
            min_output_size = wx.Size(locked_w, locked_h)
            default_output_size = wx.Size(locked_w, locked_h)
            used_saved_output = self.apply_frame_geometry_from_storage(
                self.output_frame, "output_frame", min_output_size, default_output_size)
            if not used_saved_output:
                beside_rect = self.default_output_frame_rect_beside_controls()
                self.apply_client_rect_to_window(self.output_frame, beside_rect, min_output_size)
            if self.is_ulw_output_enabled():
                if defer_ulw_sync:
                    wx.CallAfter(self._sync_transparent_capture_output_window_impl)
                else:
                    self._sync_transparent_capture_output_window_impl()
            else:
                self.output_frame.Show(True)
                self.uniconize_window(self.output_frame)

            # --- Controls window SECOND ---
            self.controls_frame.Show(True)
            self.uniconize_window(self.controls_frame)

            # --- Layer window THIRD (only when layer blend is enabled) ---
            if self.is_layer_blend_enabled():
                self.show_basic_layer_window()

            self.Show(False)
            self.bring_controls_frame_to_front()
            wx.CallAfter(self.sync_transparent_capture_output_window)
            if not self.controls_frame.IsShown():
                # Failsafe: if full controls failed to show, keep compact launcher visible.
                self.full_controls_expanded = False
                self.Show(True)
                self.Raise()
            _startup_record(
                "ensure_application_windows_visible (show output->controls->layer)",
                (time.perf_counter() - ensure_start) * 1000.0)
            return

        min_compact_size = wx.Size(self.COMPACT_MIN_CLIENT_WIDTH, self.COMPACT_MIN_CLIENT_HEIGHT)
        if hasattr(self, "_compact_default_client_size"):
            min_compact_size = self._compact_default_client_size
        default_compact_size = min_compact_size
        self.apply_frame_geometry_from_storage(
            self, "compact_frame", min_compact_size, default_compact_size)
        self.Show(True)
        self.uniconize_window(self)
        self.Raise()
        if getattr(self, "output_frame", None) is not None:
            self.ensure_output_frame()
            locked_w, locked_h = self.get_locked_output_client_size()
            min_output_size = wx.Size(locked_w, locked_h)
            default_output_size = wx.Size(locked_w, locked_h)
            used_saved_output = self.apply_frame_geometry_from_storage(
                self.output_frame, "output_frame", min_output_size, default_output_size)
            if not used_saved_output:
                beside_rect = self.default_output_frame_rect_beside_controls()
                self.apply_client_rect_to_window(self.output_frame, beside_rect, min_output_size)
            if not self.is_ulw_output_enabled():
                self.output_frame.Show(True)
                self.uniconize_window(self.output_frame)
            wx.CallAfter(self.sync_transparent_capture_output_window)

    def apply_client_rect_to_window(self,
                                    window: wx.Window,
                                    rect: wx.Rect,
                                    min_client_size: wx.Size) -> bool:
        min_width = max(1, int(min_client_size.x))
        min_height = max(1, int(min_client_size.y))
        width = max(min_width, int(rect.width))
        height = max(min_height, int(rect.height))
        self._restoring_window_geometry = True
        try:
            window.SetMinClientSize(wx.Size(min_width, min_height))
            window.SetPosition(wx.Point(rect.x, rect.y))
            window.SetClientSize(wx.Size(width, height))
            window.Layout()
            return True
        finally:
            self._restoring_window_geometry = False

    def get_controls_min_client_size(self) -> wx.Size:
        # Keep controls window resizable on typical single-screen setups.
        # We intentionally keep a small fixed minimum client size and rely on scrolling.
        return wx.Size(self.CONTROLS_MIN_CLIENT_WIDTH, self.CONTROLS_MIN_CLIENT_HEIGHT)

    def get_display_work_area_for_window(self, window: wx.Window) -> Optional[wx.Rect]:
        try:
            display_index = wx.Display.GetFromWindow(window)
            if display_index != wx.NOT_FOUND:
                return wx.Display(display_index).GetClientArea()
        except Exception:
            pass
        return None

    def get_controls_height_bounds(self, window: wx.Window, min_height: int) -> tuple[int, int]:
        max_height = self.CONTROLS_MAX_CLIENT_HEIGHT
        work_area = self.get_display_work_area_for_window(window)
        if work_area is not None:
            max_height = min(max_height, max(min_height, int(work_area.height) - 40))
        return min_height, max(min_height, max_height)

    def apply_controls_window_size_policy(
            self, window: wx.Window, *, clamp_if_oversize: bool = False) -> None:
        """Apply min height cap once; never touch width max or client size during active drag-resize."""
        if window is None:
            return
        min_client_size = self.get_controls_min_client_size()
        min_width = max(1, int(min_client_size.x))
        min_height, max_height = self.get_controls_height_bounds(window, min_client_size.y)

        self._restoring_window_geometry = True
        try:
            window.SetMinClientSize(wx.Size(min_width, min_height))
            # Width: no wx max (avoid min==max lock on narrow displays). Height: work-area cap.
            window.SetMaxClientSize(wx.Size(-1, max_height))
        finally:
            self._restoring_window_geometry = False

        if not clamp_if_oversize:
            return
        current_size = window.GetClientSize()
        work_area = self.get_display_work_area_for_window(window)
        max_width = int(current_size.x)
        if work_area is not None:
            max_width = max(min_width, int(work_area.width) - 40)
        target_width = min(int(current_size.x), max_width)
        target_height = min(int(current_size.y), max_height)
        if target_width < int(current_size.x) or target_height < int(current_size.y):
            self._clamp_controls_window_client_size_preserve_origin(
                window,
                wx.Size(max(min_width, target_width), max(min_height, target_height)))

    def _clamp_controls_window_client_size_preserve_origin(
            self, window: wx.Window, target_client_size: wx.Size) -> None:
        """Shrink an oversized controls window without jumping the client top-left corner."""
        current_size = window.GetClientSize()
        if (current_size.x <= target_client_size.x and current_size.y <= target_client_size.y):
            return
        client_origin = window.ClientToScreen(wx.Point(0, 0))
        self._restoring_window_geometry = True
        try:
            window.SetClientSize(target_client_size)
            new_origin = window.ClientToScreen(wx.Point(0, 0))
            delta_x = int(client_origin.x - new_origin.x)
            delta_y = int(client_origin.y - new_origin.y)
            if delta_x != 0 or delta_y != 0:
                frame_pos = window.GetPosition()
                window.SetPosition(wx.Point(frame_pos.x + delta_x, frame_pos.y + delta_y))
        finally:
            self._restoring_window_geometry = False

    def schedule_controls_window_bounds_refresh(self) -> None:
        self._stop_call_later(getattr(self, "_controls_window_bounds_timer", None))
        self._controls_window_bounds_timer = wx.CallLater(
            250, self._run_controls_window_bounds_refresh)

    def _run_controls_window_bounds_refresh(self) -> None:
        self._controls_window_bounds_timer = None
        controls_window = self.get_controls_window()
        if controls_window is None or not controls_window.IsShown() or self._restoring_window_geometry:
            return
        self.apply_controls_window_size_policy(controls_window, clamp_if_oversize=True)

    def on_controls_frame_moved(self) -> None:
        self.schedule_controls_window_bounds_refresh()

    def schedule_controls_frame_layout_refresh(self) -> None:
        self._stop_call_later(getattr(self, "_controls_frame_layout_timer", None))
        self._controls_frame_layout_timer = wx.CallLater(
            80, self._run_controls_frame_layout_refresh)

    def _run_controls_frame_layout_refresh(self) -> None:
        self._controls_frame_layout_timer = None
        controls_window = self.get_controls_window()
        if controls_window is None or not controls_window.IsShown():
            return
        if self._restoring_window_geometry or self._is_closing:
            return
        if hasattr(self, "main_splitter"):
            controls_window.Layout()
            self.apply_controls_layout_from_persistent()
            self.refresh_postprocess_scroll_layout()
            self.finalize_controls_column_layout()

    def handle_controls_frame_resized(self) -> None:
        if self._restoring_window_geometry:
            return
        controls_window = self.get_controls_window()
        if controls_window is None or not controls_window.IsShown():
            return
        self.schedule_controls_frame_layout_refresh()

    def handle_controls_frame_geometry_changed(self):
        self.handle_controls_frame_resized()

    def schedule_refresh_controls_scrolling(self):
        """Synchronous controls layout refresh (no debounced CallLater)."""
        self.refresh_controls_scrolling()

    def restore_controls_frame_geometry(self) -> bool:
        controls_window = self.get_controls_window()
        if controls_window is None or self._controls_geometry_restored:
            return False
        min_client_size = self.get_controls_min_client_size()
        saved_rect = self.get_saved_client_rect("controls_frame")
        if saved_rect is not None:
            self.apply_client_rect_to_window(controls_window, saved_rect, min_client_size)
            self._controls_geometry_restored = True
            return True
        return False

    def restore_compact_frame_geometry(self) -> bool:
        if self._compact_geometry_restored:
            return False
        min_client_size = wx.Size(self.COMPACT_MIN_CLIENT_WIDTH, self.COMPACT_MIN_CLIENT_HEIGHT)
        if hasattr(self, "compact_sizer"):
            fitted_size = self.compact_sizer.GetMinSize()
            min_client_size = wx.Size(
                max(min_client_size.x, int(fitted_size.x)),
                max(min_client_size.y, int(fitted_size.y)))
        saved_rect = self.get_saved_client_rect("compact_frame")
        if saved_rect is not None:
            self.apply_client_rect_to_window(self, saved_rect, min_client_size)
            self._compact_geometry_restored = True
            return True
        if hasattr(self, "_compact_default_client_size"):
            self._restoring_window_geometry = True
            try:
                self.SetClientSize(self._compact_default_client_size)
            finally:
                self._restoring_window_geometry = False
        return False

    def ensure_output_frame(self):
        # OutputFrame is retired as an output surface when the ULW is the unified
        # output window; build it (geometry/state references still use it) but
        # never show it in that mode.
        show_frame = not self.is_ulw_output_enabled()
        if getattr(self, "output_frame", None) is not None:
            if show_frame and not self.output_frame.IsShown():
                self.output_frame.Show(True)
            self.sync_output_frame_owner()
            return
        self.output_frame = OutputFrame(self)
        self.apply_output_frame_state()
        if show_frame:
            self.output_frame.Show(True)
        self.sync_output_frame_owner()

    def sync_output_frame_owner(self):
        """Both windows stay independent top-level frames (no owner/parent link)."""
        if getattr(self, "output_frame", None) is None:
            return
        # wx.Frame has no SetOwner on all wxPython builds; OutputFrame is already parentless.
        set_owner = getattr(self.output_frame, "SetOwner", None)
        if callable(set_owner):
            set_owner(None)

    def bring_controls_frame_to_front(self):
        controls_window = self.get_controls_window()
        if controls_window is None:
            return
        if not controls_window.IsShown():
            controls_window.Show(True)
        self.uniconize_window(controls_window)
        controls_window.Raise()

    def adapt_main_window_to_controls(self, initial: bool = False):
        controls_window = self.get_controls_window()
        if getattr(self, "_is_closing", False) or not hasattr(self, "main_sizer") or controls_window is None:
            return
        self.refresh_dynamic_output_status_layout()
        if hasattr(self, "right_sidebar"):
            self.right_sidebar.Layout()
        controls_window.Layout()

        min_client_size = self.get_controls_min_client_size()

        if initial and not self._controls_geometry_restored:
            if not self.restore_controls_frame_geometry():
                default_width = max(
                    min_client_size.x,
                    MainFrame.CAPTURE_PANEL_MIN_WIDTH + MainFrame.CONTROLS_TWO_COLUMN_MIN_WIDTH + 80,
                    1280)
                work_area = self.get_display_work_area_for_window(controls_window)
                if work_area is not None:
                    default_height = max(
                        min_client_size.y,
                        min(int(work_area.height * 0.88), int(work_area.height) - 48))
                else:
                    default_height = max(min_client_size.y, 760)
                self._restoring_window_geometry = True
                try:
                    controls_window.SetClientSize(wx.Size(default_width, default_height))
                    controls_window.CenterOnScreen()
                finally:
                    self._restoring_window_geometry = False
                self._controls_geometry_restored = True
        self.apply_controls_window_size_policy(controls_window)

        controls_window.Layout()
        if initial:
            self._sync_controls_splitter_geometry()
            self.initialize_adjustable_columns()
            self._nudge_animation_splitter_layout()
            self.finalize_controls_column_layout()

    def finalize_startup_autofit(self):
        self._startup_autofit_pending = False
        self._sync_controls_splitter_geometry()
        self.finalize_controls_column_layout()

    def on_column_splitter_changed(self, event: wx.Event):
        splitter = event.GetEventObject()
        if (not self._restoring_window_geometry
                and not self._controls_build_in_progress
                and self._applying_persisted_controls_layout_depth <= 0):
            self._capture_splitter_ratios()
            self._sync_splitter_ratio_fields_to_persistent_state()
            if splitter in (
                    getattr(self, "animation_splitter", None),
                    getattr(self, "main_splitter", None)):
                self.schedule_model_input_column_layout_refresh()
                self.schedule_dynamic_output_layout_refresh()
            if splitter is getattr(self, "right_sidebar_splitter", None):
                self.schedule_postprocess_layout_refresh()
            self.schedule_window_geometry_save()
        event.Skip()

    @classmethod
    def get_ui_state_file_path(cls) -> str:
        from portable_paths import resolve_ui_state_file_path
        return str(resolve_ui_state_file_path())

    def apply_mouth_persistent_state_to_args(self):
        mouth_settings = self.persistent_ui_state.get("mouth_settings")
        if isinstance(mouth_settings, dict):
            apply_fn = getattr(self.pose_converter, "apply_persistent_mouth_settings", None)
            if callable(apply_fn):
                apply_fn(mouth_settings)

    def collect_display_transform_settings(self) -> dict:
        slider_attrs = (
            ("move_x_gain", "move_x_gain_spin"),
            ("move_y_gain", "move_y_gain_spin"),
            ("scale_gain", "scale_gain_spin"),
            ("min_scale", "min_scale_spin"),
            ("max_scale", "max_scale_spin"),
            ("tilt_limit", "tilt_limit_spin"),
            ("smoothing", "smoothing_spin"),
            ("scale_curve_near", "scale_curve_near_spin"),
            ("scale_curve_far", "scale_curve_far_spin"),
            ("scale_curve_arc", "scale_curve_arc_spin"),
            ("scale_curve_peak_shift", "scale_curve_peak_shift_spin"),
            ("antialias_strength", "antialias_strength_spin"),
        )
        settings = {}
        for key, attr_name in slider_attrs:
            control = getattr(self, attr_name, None)
            if control is not None and isinstance(control, wx.Window):
                try:
                    if control.IsDestroyed():
                        continue
                except RuntimeError:
                    continue
            if control is not None and hasattr(control, "GetValue"):
                settings[key] = float(control.GetValue())
        return settings

    def apply_persistent_slider_value_states(self):
        settings = self.persistent_ui_state.get("display_transform_settings")
        if not isinstance(settings, dict):
            return
        slider_attrs = (
            ("move_x_gain", "move_x_gain_spin"),
            ("move_y_gain", "move_y_gain_spin"),
            ("scale_gain", "scale_gain_spin"),
            ("min_scale", "min_scale_spin"),
            ("max_scale", "max_scale_spin"),
            ("tilt_limit", "tilt_limit_spin"),
            ("smoothing", "smoothing_spin"),
            ("scale_curve_near", "scale_curve_near_spin"),
            ("scale_curve_far", "scale_curve_far_spin"),
            ("scale_curve_arc", "scale_curve_arc_spin"),
            ("scale_curve_peak_shift", "scale_curve_peak_shift_spin"),
            ("antialias_strength", "antialias_strength_spin"),
        )
        applied = {}
        for key, attr_name in slider_attrs:
            if key not in settings:
                continue
            value = float(settings[key])
            control = getattr(self, attr_name, None)
            if control is not None and isinstance(control, wx.Window):
                try:
                    if control.IsDestroyed():
                        control = None
                except RuntimeError:
                    control = None
            if control is None or not hasattr(control, "SetValue"):
                setattr(self, attr_name, ValueState(value))
            else:
                control.SetValue(value)
            applied[key] = value

    @staticmethod
    def resolve_persistent_path_fields(data: dict) -> dict:
        resolved = dict(data)
        for key in ("last_loaded_model_path", "tha3_character_png", "output_background_image_path"):
            if key in resolved and isinstance(resolved[key], str):
                resolved[key] = from_repo_relative(resolved[key])
        return resolved

    @staticmethod
    def relativize_persistent_path_fields(data: dict) -> dict:
        stored = dict(data)
        for key in ("last_loaded_model_path", "tha3_character_png", "output_background_image_path"):
            if key in stored and isinstance(stored[key], str):
                stored[key] = to_repo_relative(stored[key])
        return stored

    def load_persistent_ui_state(self) -> dict:
        file_path = self.get_ui_state_file_path()
        if not os.path.isfile(file_path):
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            data = self.resolve_persistent_path_fields(data)
            if data.get("transparent_capture_output_enabled"):
                legacy_mode = str(data.get("output_background_mode") or OUTPUT_BACKGROUND_TRANSPARENT)
                if legacy_mode in (OUTPUT_BACKGROUND_TRANSPARENT, "transparent"):
                    data["output_background_mode"] = OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE
            return self.sanitize_window_geometry_in_state(data)
        except Exception:
            return {}

    def reload_persistent_ui_state_from_disk(self):
        self.persistent_ui_state = self.load_persistent_ui_state()
        self.apply_bundled_default_model_paths_if_missing()
        self._controls_geometry_restored = False
        self._seed_live_splitter_ratios_from_persistent()

    def apply_bundled_default_model_paths_if_missing(self) -> None:
        """When no saved last-model memory, default Load Last to bundled bai student yaml + png."""
        bundled = resolve_bundled_bai_model_paths()
        if bundled is None:
            return
        yaml_rel, png_rel = bundled
        if not str(self.persistent_ui_state.get("last_loaded_model_path") or "").strip():
            self.persistent_ui_state["last_loaded_model_path"] = yaml_rel
        if not str(self.persistent_ui_state.get("tha3_character_png") or "").strip():
            self.persistent_ui_state["tha3_character_png"] = png_rel

    @staticmethod
    def sanitize_window_geometry_in_state(data: dict) -> dict:
        sanitized = dict(data)
        for prefix in ("controls_frame", "compact_frame", "output_frame", "capture_output_frame"):
            width_key = f"{prefix}_w"
            height_key = f"{prefix}_h"
            if width_key not in sanitized or height_key not in sanitized:
                continue
            width = max(1, int(sanitized[width_key]))
            height = max(1, int(sanitized[height_key]))
            if prefix in ("output_frame", "capture_output_frame"):
                width = MainFrame.LOCKED_OUTPUT_CLIENT_WIDTH
                height = MainFrame.LOCKED_OUTPUT_CLIENT_HEIGHT
            x = int(sanitized.get(f"{prefix}_x", 0))
            y = int(sanitized.get(f"{prefix}_y", 0))
            clamped_rect = MainFrame.clamp_client_rect_to_visible_screen(
                wx.Rect(x, y, width, height))
            sanitized[f"{prefix}_x"] = clamped_rect.x
            sanitized[f"{prefix}_y"] = clamped_rect.y
            sanitized[width_key] = clamped_rect.width
            sanitized[height_key] = clamped_rect.height
        return sanitized

    def collect_persistent_ui_state(self) -> dict:
        if self._controls_splitter_layout_readable():
            self._capture_splitter_ratios()
            self._sync_splitter_ratio_fields_to_persistent_state()
        splitter_layout_fields = self._collect_splitter_layout_fields()
        if self._active_save_caller == "process_window_geometry_save":
            output_background_hex = self.normalize_background_hex(
                self.persistent_ui_state.get("output_background_hex", "#000000"),
                "#000000")
            output_background_mode = self.persistent_ui_state.get(
                "output_background_mode", OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE)
            if output_background_mode not in OUTPUT_BACKGROUND_MODE_VALUES:
                output_background_mode = OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE
            output_background_image_path = str(
                self.persistent_ui_state.get("output_background_image_path") or "")
        else:
            output_background_hex = self.get_output_background_hex()
            output_background_mode = self.get_output_background_mode()
            output_background_image_path = self.get_output_background_image_path()
        enable_auto_transform = self.enable_auto_transform_checkbox.GetValue()
        enable_direction_calibration = self.enable_direction_calibration_checkbox.GetValue()
        direction_calibration_interval_seconds = self.auto_direction_calibration_interval_seconds_ctrl.GetValue()
        enable_scale_calibration = self.enable_scale_calibration_checkbox.GetValue()
        scale_calibration_interval_seconds = self.auto_scale_calibration_interval_seconds_ctrl.GetValue()
        layer_blend_enabled = self.is_layer_blend_enabled()
        layer_force_full_follow = self.is_layer_force_full_follow_enabled()
        output_frame_interpolation = self.get_output_frame_interpolation_multiplier()
        mouth_infer_cap_hz = self.get_mouth_infer_cap_hz()
        smooth_affine_30hz = self.is_smooth_affine_30hz_enabled()
        persistent_mouth_settings = self.pose_converter.get_persistent_mouth_settings()
        persisted_window_hwnd = int(self.persistent_ui_state.get("window_capture_hwnd") or 0)
        persisted_window_title = str(self.persistent_ui_state.get("window_capture_title") or "")
        state = {
            "output_background_mode": output_background_mode,
            "output_background_hex": output_background_hex,
            "output_background_image_path": output_background_image_path,
            "enable_auto_transform": enable_auto_transform,
            "enable_direction_calibration": enable_direction_calibration,
            "direction_calibration_interval_seconds": direction_calibration_interval_seconds,
            "enable_scale_calibration": enable_scale_calibration,
            "scale_calibration_interval_seconds": scale_calibration_interval_seconds,
            "body_tilt_opposite_to_head": self.is_body_tilt_opposite_to_head_enabled(),
            "tilt_opposite_to_head": self.is_body_tilt_opposite_to_head_enabled(),
            "character_edge_mode": self.get_character_edge_mode(),
            "character_edge_width": self.get_character_edge_width(),
            "character_edge_color_hex": "#{:02X}{:02X}{:02X}".format(
                self.get_character_edge_colour().Red(),
                self.get_character_edge_colour().Green(),
                self.get_character_edge_colour().Blue()),
            "layer_blend_enabled": layer_blend_enabled,
            "layer_hotkeys_enabled": self._safe_checkbox_value(
                "layer_hotkeys_enabled_checkbox",
                self._layer_hotkeys_enabled_state,
                default=False),
            "layer_force_full_follow": layer_force_full_follow,
            "spine_neck_anchor_ratio": self.get_spine_neck_anchor_ratio(),
            "spine_body_bind_ray_percent": self.get_spine_body_bind_ray_percent(),
            "spine_head_bind_ray_percent": self.get_spine_head_bind_ray_percent(),
            "output_frame_interpolation": output_frame_interpolation,
            "nn_super_resolution_mode": self.get_nn_super_resolution_mode(),
            "nn_frame_interpolation_multiplier": self.get_nn_frame_interpolation_multiplier(),
            "nn_infer_backend": self.get_nn_infer_backend(),
            "tha_infer_fp16": self.get_tha_infer_fp16_persisted_value(),
            "mouth_infer_cap_hz": mouth_infer_cap_hz,
            "smooth_affine_30hz": smooth_affine_30hz,
            "image_source_mode": self.get_image_source_mode(),
            "tha3_character_png": self.last_tha3_character_png,
            "tha3_model_variant": self.tha3_model_variant,
            "last_loaded_model_path": self.last_loaded_model_path,
            "mouth_settings": persistent_mouth_settings,
            "mocap_input_mode": self.mocap_input_mode,
            "mouse_blink_interval_sec": self._mouse_mocap_config.blink_interval_sec,
            "mouse_center_zone": self._mouse_mocap_config.center_zone.to_dict(),
            "mouse_horizontal_tilt_mix": self._mouse_mocap_config.horizontal_tilt_mix,
            "mouse_gaze_neutral_nx": self._mouse_mocap_config.gaze_neutral_nx,
            "mouse_gaze_neutral_ny": self._mouse_mocap_config.gaze_neutral_ny,
            "enable_mouse_auto_calibration": bool(self._enable_mouse_auto_calibration),
            "mouse_auto_calibration_interval_seconds": float(self._mouse_auto_calibration_interval_seconds),
            "display_transform_settings": self.collect_display_transform_settings(),
            # Keep last remembered window-capture target stable across source switches.
            "window_capture_hwnd": int(self._window_capture_hwnd or persisted_window_hwnd or 0),
            "window_capture_title": (self._window_capture_title or persisted_window_title or ""),
        }
        state.update(splitter_layout_fields)
        if getattr(self, "output_frame", None) is not None and self.output_frame:
            state.update(self.collect_window_client_rect(self.output_frame, "output_frame"))
        capture_window = getattr(self, "transparent_capture_window", None)
        if capture_window is not None and capture_window.is_valid():
            x, y, width, height = capture_window.get_rect()
            locked_w, locked_h = self.get_locked_output_client_size()
            clamped_rect = self.clamp_client_rect_to_visible_screen(
                wx.Rect(x, y, locked_w, locked_h))
            state["capture_output_frame_x"] = clamped_rect.x
            state["capture_output_frame_y"] = clamped_rect.y
            state["capture_output_frame_w"] = clamped_rect.width
            state["capture_output_frame_h"] = clamped_rect.height
        controls_window = self.get_controls_window()
        if controls_window is not None and controls_window.IsShown():
            state.update(self.collect_window_client_rect(controls_window, "controls_frame"))
        if not self.full_controls_expanded and self.IsShown():
            state.update(self.collect_window_client_rect(self, "compact_frame"))
        if self._basic_layer_window_visible():
            window = self._get_basic_layer_window()
            if window is not None:
                pos = window.GetPosition()
                size = window.GetSize()
                state["basic_layer_window_x"] = int(pos.x)
                state["basic_layer_window_y"] = int(pos.y)
                state["basic_layer_window_width"] = int(size.width)
                state["basic_layer_window_height"] = int(size.height)
        return state

    def save_persistent_ui_state(self):
        caller_name = "<unknown>"
        try:
            caller_frame = inspect.currentframe()
            if caller_frame is not None and caller_frame.f_back is not None:
                caller_name = caller_frame.f_back.f_code.co_name
        except Exception:
            caller_name = "<error>"
        if self._controls_build_in_progress:
            return
        self._active_save_caller = caller_name
        try:
            data = self.collect_persistent_ui_state()
        finally:
            self._active_save_caller = None
        if not data:
            return
        self.persistent_ui_state.update(data)
        self.persistent_ui_state.pop("output_background_selection", None)
        self.persistent_ui_state.pop("transparent_capture_output_enabled", None)
        self.persistent_ui_state.pop("external_layer_output_enabled", None)
        try:
            disk_state = self.relativize_persistent_path_fields(self.persistent_ui_state)
            with open(self.get_ui_state_file_path(), "w", encoding="utf-8") as f:
                json.dump(disk_state, f, ensure_ascii=True, indent=2)
        except Exception:
            pass

    def apply_persistent_ui_state(self):
        data = self.persistent_ui_state
        if not data:
            self.on_display_transform_control_changed()
            return

        self.apply_persistent_slider_value_states()

        if "enable_auto_transform" in data:
            self.enable_auto_transform_checkbox.SetValue(bool(data["enable_auto_transform"]))
        self.apply_persistent_output_background_state(data)
        if "enable_direction_calibration" in data:
            self.enable_direction_calibration_checkbox.SetValue(bool(data["enable_direction_calibration"]))
        if "enable_scale_calibration" in data:
            self.enable_scale_calibration_checkbox.SetValue(bool(data["enable_scale_calibration"]))
        if "direction_calibration_interval_seconds" in data:
            self.auto_direction_calibration_interval_seconds_ctrl.SetValue(
                max(1.0, min(3600.0, float(data["direction_calibration_interval_seconds"]))))
        if "scale_calibration_interval_seconds" in data:
            self.auto_scale_calibration_interval_seconds_ctrl.SetValue(
                max(1.0, min(3600.0, float(data["scale_calibration_interval_seconds"]))))
        if "body_tilt_opposite_to_head" in data:
            opposite_value = bool(data["body_tilt_opposite_to_head"])
        elif "tilt_opposite_to_head" in data:
            opposite_value = bool(data["tilt_opposite_to_head"])
        else:
            opposite_value = True
        self._invert_tilt_mapping_state.SetValue(opposite_value)
        if self._wx_control_alive(getattr(self, "invert_tilt_mapping_checkbox", None)):
            try:
                self.invert_tilt_mapping_checkbox.SetValue(opposite_value)
            except RuntimeError:
                pass
        if "character_edge_mode" in data:
            mode = normalize_character_edge_mode(str(data["character_edge_mode"]))
            choice = getattr(self, "character_edge_mode_choice", None)
            if isinstance(choice, wx.Choice) and mode in CHARACTER_EDGE_MODE_VALUES:
                choice.SetSelection(CHARACTER_EDGE_MODE_VALUES.index(mode))
            self.character_edge_mode_state.SetValue(mode)
        if "character_edge_width" in data:
            width = clamp_character_edge_width(float(data["character_edge_width"]))
            spin = getattr(self, "character_edge_width_spin", None)
            if isinstance(spin, wx.SpinCtrlDouble):
                spin.SetValue(width)
            elif isinstance(spin, wx.SpinCtrl):
                spin.SetValue(int(round(width)))
            self.character_edge_width_state.SetValue(float(width))
        if "character_edge_color_hex" in data:
            hex_value = self.normalize_background_hex(str(data["character_edge_color_hex"]), "#FFFFFF")
            picker = getattr(self, "character_edge_colour_picker", None)
            if isinstance(picker, wx.ColourPickerCtrl):
                picker.SetColour(wx.Colour(hex_value))
            self.character_edge_color_hex_state.SetValue(hex_value)
        if "layer_blend_enabled" in data:
            value = bool(data["layer_blend_enabled"])
            self._layer_blend_enabled_state.SetValue(value)
            if self._wx_control_alive(getattr(self, "layer_blend_enabled_checkbox", None)):
                try:
                    self.layer_blend_enabled_checkbox.SetValue(value)
                except RuntimeError:
                    pass
        elif "external_layer_output_enabled" in data:
            # Legacy key from removed external-bridge UI.
            value = bool(data["external_layer_output_enabled"])
            self._layer_blend_enabled_state.SetValue(value)
            if self._wx_control_alive(getattr(self, "layer_blend_enabled_checkbox", None)):
                try:
                    self.layer_blend_enabled_checkbox.SetValue(value)
                except RuntimeError:
                    pass
        if "layer_hotkeys_enabled" in data:
            value = bool(data["layer_hotkeys_enabled"])
            self._layer_hotkeys_enabled_state.SetValue(value)
            if self._wx_control_alive(getattr(self, "layer_hotkeys_enabled_checkbox", None)):
                try:
                    self.layer_hotkeys_enabled_checkbox.SetValue(value)
                except RuntimeError:
                    pass
        if "layer_force_full_follow" in data:
            value = bool(data["layer_force_full_follow"])
            self._layer_force_full_follow_state.SetValue(value)
            if self._wx_control_alive(getattr(self, "layer_force_full_follow_checkbox", None)):
                try:
                    self.layer_force_full_follow_checkbox.SetValue(value)
                except RuntimeError:
                    pass
        if "output_frame_interpolation" in data:
            multiplier = normalize_pose_frame_multiplier(data["output_frame_interpolation"])
            control = getattr(self, "output_frame_interpolation_choice", None)
            if isinstance(control, wx.Choice):
                try:
                    control.SetSelection(POSE_FRAME_INTERP_VALUES.index(multiplier))
                except ValueError:
                    control.SetSelection(0)
            else:
                self.output_frame_interpolation_choice.SetValue(multiplier)
        if "nn_super_resolution_mode" in data:
            mode = normalize_sr_mode(data["nn_super_resolution_mode"])
            control = getattr(self, "nn_super_resolution_choice", None)
            if isinstance(control, wx.Choice):
                try:
                    control.SetSelection(NN_SR_VALUES.index(mode))
                except ValueError:
                    control.SetSelection(0)
            else:
                self.nn_super_resolution_choice.SetValue(mode)
        if "nn_frame_interpolation_multiplier" in data:
            mult = normalize_nn_frame_multiplier(data["nn_frame_interpolation_multiplier"])
            control = getattr(self, "nn_frame_interpolation_choice", None)
            if isinstance(control, wx.Choice):
                try:
                    control.SetSelection(NN_FRAME_INTERP_VALUES.index(mult))
                except ValueError:
                    control.SetSelection(0)
            else:
                self.nn_frame_interpolation_choice.SetValue(mult)
        if "nn_infer_backend" in data:
            backend = normalize_infer_backend(data["nn_infer_backend"])
            control = getattr(self, "nn_infer_backend_choice", None)
            if isinstance(control, wx.Choice):
                try:
                    control.SetSelection(INFER_BACKEND_VALUES.index(backend))
                except ValueError:
                    control.SetSelection(1)
            else:
                self.nn_infer_backend_choice.SetValue(backend)
        if "tha_infer_fp16" in data:
            half = normalize_tha_infer_fp16(data["tha_infer_fp16"])
            control = getattr(self, "tha_infer_fp16_choice", None)
            with block_events(self):
                if isinstance(control, wx.Choice):
                    control.SetSelection(1 if half else 0)
                else:
                    self.tha_infer_fp16_choice.SetValue(
                        THA_INFER_FP16_CHOICES[1 if half else 0])
            self._sync_tha_infer_fp16_ui()
        self._sync_output_enhancement_config()
        if "mouth_infer_cap_hz" in data:
            try:
                cap_hz = int(data["mouth_infer_cap_hz"])
            except (TypeError, ValueError):
                cap_hz = MOUTH_INFER_CAP_HZ_DEFAULT
            if cap_hz not in MOUTH_INFER_CAP_HZ_VALUES:
                cap_hz = MOUTH_INFER_CAP_HZ_DEFAULT
            choice = getattr(self, "mouth_infer_cap_choice", None)
            if isinstance(choice, wx.Choice):
                try:
                    choice.SetSelection(MOUTH_INFER_CAP_HZ_VALUES.index(cap_hz))
                except ValueError:
                    choice.SetSelection(0)
        if "smooth_affine_30hz" in data:
            enabled = bool(data["smooth_affine_30hz"])
            checkbox = getattr(self, "smooth_affine_30hz_checkbox", None)
            if isinstance(checkbox, wx.CheckBox):
                checkbox.SetValue(enabled)
        if "image_source_mode" in data:
            self.image_source_mode = normalize_image_source_mode(data["image_source_mode"])
        if "tha3_character_png" in data:
            tha3_png = data["tha3_character_png"]
            if isinstance(tha3_png, str):
                self.last_tha3_character_png = from_repo_relative(tha3_png)
            else:
                self.last_tha3_character_png = None
        if "tha3_model_variant" in data:
            self.tha3_model_variant = str(data["tha3_model_variant"])
        if "last_loaded_model_path" in data:
            last_loaded_model_path = data["last_loaded_model_path"]
            if isinstance(last_loaded_model_path, str):
                self.last_loaded_model_path = from_repo_relative(last_loaded_model_path)
            else:
                self.last_loaded_model_path = None
        # Restore remembered window-capture target into runtime state so future saves
        # do not accidentally overwrite persisted values with None.
        self._window_capture_hwnd = int(data.get("window_capture_hwnd") or 0) or None
        self._window_capture_title = str(data.get("window_capture_title") or "").strip() or None
        self.update_load_model_buttons()
        if not getattr(self, "_defer_heavy_ui_refresh", False):
            self.on_display_transform_control_changed()
        wx.CallAfter(self.apply_layer_blend_visibility)
        wx.CallAfter(self.update_character_edge_controls_visibility)
        if not getattr(self, "_defer_heavy_ui_refresh", False):
            wx.CallAfter(self.sync_transparent_capture_output_window)
        if self.get_controls_window() is not None:
            wx.CallAfter(self._apply_persisted_controls_layout)

    def apply_output_frame_state(self):
        if getattr(self, "output_frame", None) is None:
            return
        locked_w, locked_h = self.get_locked_output_client_size()
        locked_size = wx.Size(locked_w, locked_h)
        data = self.persistent_ui_state
        position = None
        if "output_frame_x" in data and "output_frame_y" in data:
            position = wx.Point(int(data["output_frame_x"]), int(data["output_frame_y"]))
        self._restoring_window_geometry = True
        try:
            self.output_frame.SetMinClientSize(locked_size)
            self.output_frame.SetMaxClientSize(locked_size)
            self.output_frame.SetClientSize(locked_size)
            if position is not None:
                clamped_rect = self.clamp_client_rect_to_visible_screen(
                    wx.Rect(position.x, position.y, locked_w, locked_h))
                self.output_frame.SetPosition(wx.Point(clamped_rect.x, clamped_rect.y))
            self.output_frame.Layout()
            self.refresh_output_frame_chrome()
        finally:
            self._restoring_window_geometry = False

    def schedule_output_frame_geometry_sync(self, redraw: bool = True):
        self._output_geometry_redraw_pending = self._output_geometry_redraw_pending or redraw
        if self._output_geometry_sync_pending:
            return
        self._output_geometry_sync_pending = True
        wx.CallAfter(self.process_output_frame_geometry_sync)

    def process_output_frame_geometry_sync(self):
        if self._is_closing:
            return
        self._output_geometry_sync_pending = False
        redraw = self._output_geometry_redraw_pending
        self._output_geometry_redraw_pending = False
        self.handle_output_frame_geometry_changed(redraw=redraw)

    def reparent_output_frame_for_owner(self):
        self.ensure_output_frame()

    def get_output_canvas_size(self) -> tuple[int, int]:
        return self.get_locked_output_client_size()

    def initialize_output_bitmap(self):
        width, height = self.get_locked_output_client_size()
        self._result_bitmap_alpha = self.needs_alpha_result_bitmap()
        self.clear_result_image_bitmap(width, height)

    def refresh_postprocess_static_text_wrap(self):
        margin = MainFrame.POSTPROCESS_H_PADDING * 2
        for attr_name in (
            "output_obs_capture_hint",
            "output_transparent_capture_hint",
            "character_edge_hint_text",
            "layer_blend_status_text",
            "antialias_hint",
            "mouth_infer_cap_hint",
            "smooth_affine_hint",
            "frame_interp_hint",
        ):
            control = getattr(self, attr_name, None)
            if control is not None:
                self.wrap_static_text_to_parent(control, margin)
        image_path_text = getattr(self, "output_background_image_path_text", None)
        image_panel = getattr(self, "output_background_image_panel", None)
        browse_button = getattr(self, "output_background_image_browse_button", None)
        if image_path_text is not None and image_panel is not None:
            panel_width = image_panel.GetClientSize().x
            if browse_button is not None:
                panel_width -= browse_button.GetSize().x + 6
            wrap_width = panel_width - margin
            if wrap_width > 40:
                last_width = getattr(image_path_text, "_last_wrap_width", None)
                if last_width is None or abs(last_width - wrap_width) >= 2:
                    if last_width is not None and wrap_width > last_width:
                        image_path_text.SetLabel(image_path_text.GetLabel())
                    image_path_text._last_wrap_width = wrap_width
                    image_path_text.Wrap(wrap_width)
                    if hasattr(image_path_text, "InvalidateBestSize"):
                        image_path_text.InvalidateBestSize()
            else:
                image_path_text._last_wrap_width = None

    def schedule_postprocess_layout_refresh(self):
        self._stop_call_later(getattr(self, "_postprocess_layout_timer", None))
        self._postprocess_layout_timer = wx.CallLater(
            80, self._run_postprocess_layout_refresh)

    def _run_postprocess_layout_refresh(self):
        self._postprocess_layout_timer = None
        if self._postprocess_layout_in_progress or self._is_closing:
            return
        self._postprocess_layout_in_progress = True
        try:
            self.refresh_postprocess_scroll_layout()
        finally:
            self._postprocess_layout_in_progress = False

    def refresh_postprocess_scroll_layout(self):
        scroll = getattr(self, "postprocess_scroll", None)
        panel = getattr(self, "postprocess_panel", None)
        if scroll is None or panel is None:
            return
        client_size = scroll.GetClientSize()
        if client_size.x <= 0 or client_size.y <= 0:
            return
        panel.SetMinSize((client_size.x, -1))
        self.refresh_postprocess_static_text_wrap()
        min_size = panel.GetBestSize()
        virtual_height = max(min_size.y, client_size.y)
        current = scroll.GetVirtualSize()
        if current.x != client_size.x or current.y != virtual_height:
            scroll.SetVirtualSize((client_size.x, virtual_height))
        scroll.EnableScrolling(False, True)
        splitter = getattr(self, "right_sidebar_splitter", None)
        if splitter is not None and splitter.IsSplit():
            total_h = max(1, splitter.GetClientSize().y)
            minimum = max(1, splitter.GetMinimumPaneSize())
            min_capture_h = MainFrame.adaptive_right_sidebar_capture_min_height(total_h)
            min_capture_h = max(minimum, min(total_h - minimum, min_capture_h))
            if splitter.GetSashPosition() < min_capture_h:
                splitter.SetSashPosition(min_capture_h)

    def on_postprocess_scroll_size(self, event: wx.Event):
        event.Skip()

    def refresh_right_sidebar_scrolling(self):
        if self._postprocess_layout_in_progress:
            return
        self.refresh_postprocess_scroll_layout()

    def refresh_controls_scrolling(self):
        if not hasattr(self, "animation_panel"):
            return
        controls_window = self.get_controls_window()
        if controls_window is not None:
            controls_window.Layout()
        if hasattr(self, "right_sidebar"):
            self.right_sidebar.Layout()
        if hasattr(self, "main_splitter"):
            self.main_splitter.Layout()
        if hasattr(self, "animation_panel"):
            self.animation_panel.Layout()
        self.finalize_controls_column_layout()

    def ensure_result_bitmap_size(self):
        width, height = self.get_output_canvas_size()
        needs_recreate = (
            not self.result_image_bitmap.IsOk()
            or self.result_image_bitmap.GetWidth() != width
            or self.result_image_bitmap.GetHeight() != height
            or getattr(self, "_result_bitmap_alpha", None) != self.needs_alpha_result_bitmap())
        if needs_recreate:
            self._result_bitmap_alpha = self.needs_alpha_result_bitmap()
            self.clear_result_image_bitmap(width, height)
            self._invalidate_render_caches()

    def handle_output_frame_geometry_changed(self, redraw: bool = True):
        self.refresh_output_frame_chrome()
        self.schedule_window_geometry_save()
        if redraw and self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
        elif redraw:
            self.update_result_image_bitmap()

    def create_animation_panel(self, parent):
        self.animation_panel = wx.Panel(parent, style=wx.RAISED_BORDER)
        self.animation_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.animation_panel.SetSizer(self.animation_panel_sizer)
        self.animation_panel.SetAutoLayout(1)
        self.animation_panel.SetDoubleBuffered(True)
        self.animation_panel.SetMinSize(
            wx.Size(MainFrame.CONTROLS_TWO_COLUMN_MIN_WIDTH, 320))

        self.animation_splitter = wx.SplitterWindow(
            self.animation_panel,
            style=wx.SP_LIVE_UPDATE | wx.SP_3D | wx.SP_BORDER)
        self.animation_splitter.SetMinimumPaneSize(MainFrame.CONTROLS_COLUMN_MIN_WIDTH)
        self.animation_splitter.SetSashGravity(0.5)
        self.animation_splitter.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.on_column_splitter_changed)
        self.animation_panel_sizer.Add(self.animation_splitter, 1, wx.EXPAND)

        self.model_input_column = wx.ScrolledWindow(
            self.animation_splitter,
            style=wx.SIMPLE_BORDER | wx.VSCROLL)
        self.model_input_column.SetScrollRate(10, 10)
        self.model_input_column.EnableScrolling(False, True)
        self.model_input_column_sizer = wx.BoxSizer(wx.VERTICAL)
        self.model_input_column.SetSizer(self.model_input_column_sizer)
        self.model_input_column.SetAutoLayout(1)
        self.model_input_column.SetDoubleBuffered(True)
        self.model_input_column.Bind(wx.EVT_SIZE, self.on_model_input_column_size)

        model_input_text = wx.StaticText(
            self.model_input_column, label="--- 模型参数传入 / Model Input ---", style=wx.ALIGN_CENTER)
        self.model_input_column_sizer.Add(model_input_text, 0, wx.EXPAND)

        self.create_model_input_video_source_controls(self.model_input_column, self.model_input_column_sizer)

        def current_pose_supplier() -> Optional[MediaPipeFacePose]:
            return self.mediapipe_face_pose

        self.pose_converter.ui_state_changed_callback = self.save_persistent_ui_state
        self.pose_converter.init_pose_converter_panel(self.model_input_column, current_pose_supplier)
        mouth_settings = self.persistent_ui_state.get("mouth_settings")
        if isinstance(mouth_settings, dict):
            apply_fn = getattr(self.pose_converter, "apply_persistent_mouth_settings", None)
            if callable(apply_fn):
                apply_fn(mouth_settings)
        if hasattr(self.pose_converter, "refresh_audio_input_runtime"):
            self.pose_converter.refresh_audio_input_runtime(time.time())
        self.model_input_column_sizer.Fit(self.model_input_column)

        self.dynamic_output_scroll = wx.ScrolledWindow(
            self.animation_splitter,
            style=wx.SIMPLE_BORDER | wx.VSCROLL)
        self.dynamic_output_scroll.SetScrollRate(10, 10)
        self.dynamic_output_scroll.EnableScrolling(False, True)
        self.dynamic_output_scroll.SetDoubleBuffered(True)
        self.dynamic_output_scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        self.dynamic_output_scroll.SetSizer(self.dynamic_output_scroll_sizer)

        if True:
            self.animation_left_panel = wx.Panel(self.dynamic_output_scroll, style=wx.SIMPLE_BORDER)
            self.animation_left_panel_sizer = wx.BoxSizer(wx.VERTICAL)
            self.animation_left_panel.SetSizer(self.animation_left_panel_sizer)
            self.animation_left_panel.SetAutoLayout(1)
            self.animation_left_panel.SetDoubleBuffered(True)
            self.animation_left_panel.Bind(wx.EVT_SIZE, self.on_dynamic_output_panel_size)

            auto_transform_enabled = self.enable_auto_transform_checkbox.GetValue()
            move_x_gain = self.move_x_gain_spin.GetValue()
            move_y_gain = self.move_y_gain_spin.GetValue()
            scale_gain = self.scale_gain_spin.GetValue()
            min_scale = self.min_scale_spin.GetValue()
            max_scale = self.max_scale_spin.GetValue()
            tilt_limit = self.tilt_limit_spin.GetValue()
            smoothing = self.smoothing_spin.GetValue()
            invert_tilt_mapping = self.invert_tilt_mapping_checkbox.GetValue()
            near_curve = self.scale_curve_near_spin.GetValue()
            far_curve = self.scale_curve_far_spin.GetValue()
            curve_arc = self.scale_curve_arc_spin.GetValue()
            peak_shift = self.scale_curve_peak_shift_spin.GetValue()

            auto_transform_text = wx.StaticText(self.animation_left_panel, label="--- 输出动态增强 / Dynamic Output ---",
                                                style=wx.ALIGN_CENTER)
            self.animation_left_panel_sizer.Add(auto_transform_text, 0, wx.EXPAND)

            self.enable_auto_transform_checkbox = wx.CheckBox(
                self.animation_left_panel, label="启用自动移动缩放 / Enable Auto Pan & Scale")
            self.enable_auto_transform_checkbox.SetValue(auto_transform_enabled)
            self.enable_auto_transform_checkbox.Bind(wx.EVT_CHECKBOX, self.on_display_transform_control_changed)
            self.animation_left_panel_sizer.Add(self.enable_auto_transform_checkbox,
                                                wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

            display_transform_panel = wx.Panel(self.animation_left_panel)
            display_transform_panel_sizer = wx.BoxSizer(wx.VERTICAL)
            display_transform_panel.SetSizer(display_transform_panel_sizer)
            display_transform_panel.SetAutoLayout(1)
            self.animation_left_panel_sizer.Add(display_transform_panel, 0, wx.EXPAND)

            self.move_x_gain_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer,
                slider_label("X 位移增益", "Move X Gain", "倍率", "multiplier"), move_x_gain, 0.0, 400.0, 1.0)
            self.move_y_gain_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer,
                slider_label("Y 位移增益", "Move Y Gain", "倍率", "multiplier"), move_y_gain, 0.0, 400.0, 1.0)
            self.scale_gain_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer,
                slider_label("缩放增益", "Scale Gain", "倍率", "multiplier"), scale_gain, 0.0, 8.0, 0.05)
            self.min_scale_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer,
                slider_label("最小缩放", "Min Scale", "倍率", "multiplier"), min_scale, 0.25, 2.0, 0.01)
            self.max_scale_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer,
                slider_label("最大缩放", "Max Scale", "倍率", "multiplier"), max_scale, 0.25, 2.0, 0.01)
            self.tilt_limit_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer,
                slider_label("倾斜上限", "Tilt Limit", "度", "deg"), tilt_limit, -30.0, 30.0, 0.5)
            self.smoothing_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer,
                slider_label("平滑系数", "Smoothing", "混合比 0~1", "blend 0~1"), smoothing, 0.0, 0.98, 0.01)

            self.invert_tilt_mapping_checkbox = wx.CheckBox(
                self.animation_left_panel, label="倾斜映射和头相反 / Tilt Opposite to Head")
            self.invert_tilt_mapping_checkbox.SetValue(invert_tilt_mapping)
            self._invert_tilt_mapping_state.SetValue(bool(invert_tilt_mapping))
            self.invert_tilt_mapping_checkbox.Bind(wx.EVT_CHECKBOX, self.on_display_transform_control_changed)
            self.animation_left_panel_sizer.Add(self.invert_tilt_mapping_checkbox,
                                                wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

            scale_curve_text = wx.StaticText(self.animation_left_panel, label="--- 缩放曲线 / Scale Curve ---",
                                             style=wx.ALIGN_CENTER)
            self.animation_left_panel_sizer.Add(scale_curve_text, 0, wx.EXPAND)

            scale_curve_control_panel = wx.Panel(self.animation_left_panel)
            scale_curve_control_panel_sizer = wx.BoxSizer(wx.VERTICAL)
            scale_curve_control_panel.SetSizer(scale_curve_control_panel_sizer)
            scale_curve_control_panel.SetAutoLayout(1)
            self.animation_left_panel_sizer.Add(scale_curve_control_panel, 0, wx.EXPAND)

            self.scale_curve_near_spin = self.create_display_transform_slider_control(
                scale_curve_control_panel, scale_curve_control_panel_sizer,
                slider_label("近距曲率", "Near Curve", "曲率", "curvature"), near_curve, 0.25, 2.00, 0.05)
            self.scale_curve_far_spin = self.create_display_transform_slider_control(
                scale_curve_control_panel, scale_curve_control_panel_sizer,
                slider_label("远距曲率", "Far Curve", "曲率", "curvature"), far_curve, 0.10, 1.20, 0.05)
            self.scale_curve_arc_spin = self.create_display_transform_slider_control(
                scale_curve_control_panel, scale_curve_control_panel_sizer,
                slider_label("曲线弧度", "Curve Arc", "弧度系数", "arc factor"), curve_arc, 0.40, 2.20, 0.05)
            self.scale_curve_peak_shift_spin = self.create_display_transform_slider_control(
                scale_curve_control_panel, scale_curve_control_panel_sizer,
                slider_label("峰位横移", "Peak Shift", "归一化偏移", "normalized shift"), peak_shift, -0.12, 0.12, 0.005)

            self.scale_curve_panel = wx.Panel(self.animation_left_panel, size=(256, 140), style=0)
            self.scale_curve_panel.SetBackgroundStyle(wx.BG_STYLE_PAINT)
            self.scale_curve_panel.SetBackgroundColour(wx.Colour(250, 250, 250))
            self.scale_curve_panel.SetDoubleBuffered(True)
            self.scale_curve_panel.Bind(wx.EVT_PAINT, self.paint_scale_curve_panel)
            self.scale_curve_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)
            self.animation_left_panel_sizer.Add(self.scale_curve_panel, 0, wx.FIXED_MINSIZE)

            self.scale_curve_status_text = wx.StaticText(self.animation_left_panel, label="")
            self.animation_left_panel_sizer.Add(self.scale_curve_status_text, wx.SizerFlags().Expand().Border())

            separator = wx.StaticLine(self.animation_left_panel, -1, size=(256, 5))
            self.animation_left_panel_sizer.Add(separator, 0, wx.EXPAND)

            self.auto_transform_status_text = wx.StaticText(self.animation_left_panel, label="")
            self.animation_left_panel_sizer.Add(self.auto_transform_status_text, wx.SizerFlags().Expand().Border())

            self.animation_left_panel_sizer.Fit(self.animation_left_panel)
            self.dynamic_output_scroll_sizer.Add(self.animation_left_panel, 0, wx.EXPAND)
            self.refresh_auto_transform_status("READY")
            self.refresh_scale_curve_status()
            self.refresh_dynamic_output_status_layout()
        if not self.animation_splitter.IsSplit():
            self.animation_splitter.SplitVertically(
                self.model_input_column,
                self.dynamic_output_scroll,
                sashPosition=MainFrame.compute_equal_halves_sash(
                    max(MainFrame.CONTROLS_TWO_COLUMN_MIN_WIDTH, self.animation_splitter.GetClientSize().x),
                    self.animation_splitter.GetMinimumPaneSize()))

        self.bind_animation_area_mousewheel()

    def create_model_input_video_source_controls(self, parent, parent_sizer):
        """Video source picker lives in Model Input column (mocap input for pose params)."""
        mocap_title = wx.StaticText(
            parent,
            label="面捕输入模式 / Face Input Mode",
            style=wx.ALIGN_CENTER)
        parent_sizer.Add(mocap_title, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)

        self.mocap_input_mode_choice = wx.Choice(parent, choices=list(MOCAP_INPUT_MODE_LABELS))
        self.mocap_input_mode_choice.SetMinSize(wx.Size(MainFrame.VIDEO_SOURCE_COLUMN_MIN_WIDTH - 24, -1))
        self.mocap_input_mode_choice.Bind(wx.EVT_CHOICE, self.on_mocap_input_mode_changed)
        parent_sizer.Add(self.mocap_input_mode_choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        self.mocap_input_mode_status_text = wx.StaticText(
            parent,
            label="",
            style=wx.ST_ELLIPSIZE_END)
        parent_sizer.Add(self.mocap_input_mode_status_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        self.mouse_only_controls_panel = wx.Panel(parent)
        mouse_only_sizer = wx.BoxSizer(wx.VERTICAL)
        self.mouse_only_controls_panel.SetSizer(mouse_only_sizer)
        self.mouse_only_controls_panel.SetAutoLayout(1)

        blink_slider_panel = wx.Panel(self.mouse_only_controls_panel)
        blink_slider_sizer = wx.FlexGridSizer(cols=1, hgap=0, vgap=0)
        blink_slider_sizer.AddGrowableCol(0)
        blink_slider_panel.SetSizer(blink_slider_sizer)
        self.mouse_blink_interval_spin = FloatSliderControl(
            blink_slider_panel,
            blink_slider_sizer,
            slider_label("眨眼周期", "Blink Interval", "秒", "s"),
            self._mouse_mocap_config.blink_interval_sec,
            MOUSE_BLINK_INTERVAL_MIN_SEC,
            MOUSE_BLINK_INTERVAL_MAX_SEC,
            0.5,
            self.on_mouse_blink_interval_changed,
            slider_min=MOUSE_BLINK_INTERVAL_MIN_SEC,
            slider_max=MOUSE_BLINK_INTERVAL_MAX_SEC)
        mouse_only_sizer.Add(blink_slider_panel, 0, wx.EXPAND | wx.BOTTOM, 4)

        mouse_zone_title = wx.StaticText(
            self.mouse_only_controls_panel,
            label="屏幕区 / 中心区（拖移内框，拖边缩放）\nScreen / Center Zone",
            style=wx.ALIGN_CENTER)
        mouse_only_sizer.Add(mouse_zone_title, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 2)

        self.mouse_zone_panel = MouseZonePanel(
            self.mouse_only_controls_panel,
            zone=self._mouse_mocap_config.center_zone,
            on_zone_changed=self.on_mouse_center_zone_changed)
        mouse_only_sizer.Add(self.mouse_zone_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        mouse_zone_hint_text = wx.StaticText(
            self.mouse_only_controls_panel,
            label=(
                "提示：输出动态增强校准后，左右运动幅度可能看起来不一致（属正常现象）。\n"
                "Note: After output dynamic enhancement calibration, left/right motion may feel uneven (expected)."),
            style=wx.ALIGN_LEFT)
        mouse_zone_hint_text.SetForegroundColour(wx.Colour(100, 100, 100))
        mouse_only_sizer.Add(mouse_zone_hint_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        horizontal_mix_panel = wx.Panel(self.mouse_only_controls_panel)
        horizontal_mix_sizer = wx.FlexGridSizer(cols=1, hgap=0, vgap=0)
        horizontal_mix_sizer.AddGrowableCol(0)
        horizontal_mix_panel.SetSizer(horizontal_mix_sizer)
        self.mouse_horizontal_tilt_mix_spin = FloatSliderControl(
            horizontal_mix_panel,
            horizontal_mix_sizer,
            slider_label(
                "左右出框倾斜混合",
                "Horizontal Out-Tilt Mix",
                "0位移 1倾斜",
                "0=move 1=tilt"),
            self._mouse_mocap_config.horizontal_tilt_mix,
            MOUSE_HORIZONTAL_TILT_MIX_MIN,
            MOUSE_HORIZONTAL_TILT_MIX_MAX,
            0.05,
            self.on_mouse_horizontal_tilt_mix_changed,
            slider_min=MOUSE_HORIZONTAL_TILT_MIX_MIN,
            slider_max=MOUSE_HORIZONTAL_TILT_MIX_MAX)
        mouse_only_sizer.Add(horizontal_mix_panel, 0, wx.EXPAND | wx.BOTTOM, 4)

        self.enable_mouse_auto_calibration_checkbox = wx.CheckBox(
            self.mouse_only_controls_panel,
            label="鼠标周期自动校准 / Mouse Periodic Auto-Calibration")
        self.enable_mouse_auto_calibration_checkbox.SetValue(self._enable_mouse_auto_calibration)
        self.enable_mouse_auto_calibration_checkbox.Bind(
            wx.EVT_CHECKBOX, self.on_mouse_auto_calibration_checkbox_changed)
        mouse_only_sizer.Add(self.enable_mouse_auto_calibration_checkbox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        mouse_interval_panel = wx.Panel(self.mouse_only_controls_panel)
        mouse_interval_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mouse_interval_panel.SetSizer(mouse_interval_sizer)
        mouse_interval_label = wx.StaticText(
            mouse_interval_panel,
            label=slider_label("校准周期", "Calibration Interval", "秒", "s"))
        mouse_interval_sizer.Add(mouse_interval_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.mouse_auto_calibration_interval_seconds_ctrl = wx.SpinCtrlDouble(
            mouse_interval_panel,
            wx.ID_ANY,
            min=1.0,
            max=3600.0,
            initial=self._mouse_auto_calibration_interval_seconds,
            inc=1.0,
            style=wx.SP_ARROW_KEYS)
        self.mouse_auto_calibration_interval_seconds_ctrl.SetDigits(0)
        self.mouse_auto_calibration_interval_seconds_ctrl.Bind(
            wx.EVT_SPINCTRLDOUBLE, self.on_mouse_auto_calibration_interval_changed)
        self.mouse_auto_calibration_interval_seconds_ctrl.Bind(
            wx.EVT_TEXT, self.on_mouse_auto_calibration_interval_changed)
        mouse_interval_sizer.Add(self.mouse_auto_calibration_interval_seconds_ctrl, 0, wx.ALIGN_CENTER_VERTICAL)
        mouse_only_sizer.Add(mouse_interval_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        parent_sizer.Add(self.mouse_only_controls_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        self.video_source_section_separator = wx.StaticLine(parent, -1)
        parent_sizer.Add(self.video_source_section_separator, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 4)

        self.video_source_title = wx.StaticText(
            parent,
            label="视频输入源（窗口捕获 / 摄像头）\nVideo Source (Window / Camera)",
            style=wx.ALIGN_CENTER)
        parent_sizer.Add(self.video_source_title, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)

        self.video_source_panel = wx.Panel(parent, style=wx.SIMPLE_BORDER)
        video_source_sizer = wx.BoxSizer(wx.VERTICAL)
        self.video_source_panel.SetSizer(video_source_sizer)
        self.video_source_panel.SetAutoLayout(1)

        self.video_source_choice = wx.Choice(self.video_source_panel, choices=[])
        self.video_source_choice.SetMinSize(wx.Size(MainFrame.VIDEO_SOURCE_COLUMN_MIN_WIDTH - 24, -1))
        self.video_source_choice.Bind(wx.EVT_CHOICE, self.on_video_source_choice_changed)
        video_source_sizer.Add(self.video_source_choice, 0, wx.EXPAND | wx.ALL, 6)

        video_source_button_row = wx.BoxSizer(wx.HORIZONTAL)
        self.refresh_video_sources_button = wx.Button(
            self.video_source_panel, wx.ID_ANY, "刷新摄像头 / Refresh Cameras")
        self.refresh_video_sources_button.Bind(wx.EVT_BUTTON, self.on_refresh_video_sources_clicked)
        video_source_button_row.Add(self.refresh_video_sources_button, 1, wx.EXPAND | wx.RIGHT, 4)

        self.pick_window_capture_button = wx.Button(
            self.video_source_panel, wx.ID_ANY, "窗口捕获 / Window Capture")
        self.pick_window_capture_button.Bind(wx.EVT_BUTTON, self.on_pick_window_capture_clicked)
        video_source_button_row.Add(self.pick_window_capture_button, 1, wx.EXPAND)
        video_source_sizer.Add(video_source_button_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.last_window_capture_text = wx.StaticText(
            self.video_source_panel,
            label="上次窗口捕获: 未设置\nLast window capture: (none)",
            style=wx.ST_ELLIPSIZE_END)
        video_source_sizer.Add(self.last_window_capture_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        self.video_source_status_text = wx.StaticText(
            self.video_source_panel,
            label="尚未连接摄像头 / No camera connected",
            style=wx.ST_ELLIPSIZE_END)
        video_source_sizer.Add(self.video_source_status_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        parent_sizer.Add(self.video_source_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        self._init_video_source_choices_with_window()
        wx.CallAfter(self.apply_persistent_mocap_input_mode)
        wx.CallAfter(self.apply_mouse_mocap_controls_from_persistent)

    def on_mocap_input_mode_changed(self, event: wx.Event):
        if not hasattr(self, "mocap_input_mode_choice"):
            return
        if is_blocked(self):
            event.Skip()
            return
        selection = self.mocap_input_mode_choice.GetSelection()
        if selection < 0 or selection >= len(MOCAP_INPUT_MODE_VALUES):
            return
        new_mode = MOCAP_INPUT_MODE_VALUES[selection]
        if not self.set_mocap_input_mode(new_mode, from_user=True):
            self.refresh_mocap_input_mode_ui()
            self._ui_alignment_toast("Face input mode switch failed; reverted.")
        else:
            monitor = getattr(self, "_ui_alignment_monitor", None)
            if monitor is not None:
                monitor.notify_switch(["mocap_input"])
        event.Skip()

    def _fallback_to_mouse_mocap_once(self, *, reason: str = "") -> None:
        if self._mouse_mocap_fallback_done:
            return
        self._mouse_mocap_fallback_done = True
        if reason:
            print(f"Switching to Mouse + Audio mode: {reason}", file=sys.stderr)
        if not self.is_mouse_audio_mocap_mode():
            wx.CallAfter(
                self.set_mocap_input_mode,
                MOCAP_INPUT_MODE_MOUSE_AUDIO,
                persist=True,
                from_user=False)

    def ensure_face_landmarker(self, *, show_dialog: bool = False) -> bool:
        if self._face_landmarker_init_failed:
            return False
        if self.face_landmarker is not None:
            return True
        if not face_capture_assets_ready(get_portable_root()):
            self._face_landmarker_init_failed = True
            self._fallback_to_mouse_mocap_once(reason="face_puppeteer add-on not installed")
            return False
        try:
            self.face_landmarker = create_face_landmarker()
            return True
        except Exception as exc:
            self._face_landmarker_init_failed = True
            if show_dialog:
                show_rate_limited_message(
                    self.get_dialog_parent(),
                    "无法初始化 MediaPipe 面捕：\n%s\n\n"
                    "请运行 DEPLOY.bat -> [2] face_puppeteer，或继续使用 Mouse + Audio 模式。" % exc,
                    "MediaPipe unavailable",
                    style=wx.OK | wx.ICON_WARNING,
                    dialog_key="face_landmarker_init_failed")
            elif not getattr(self, "_face_landmarker_error_logged", False):
                self._face_landmarker_error_logged = True
                print(f"MediaPipe face landmarker unavailable: {exc}", file=sys.stderr)
            self._fallback_to_mouse_mocap_once(reason=str(exc))
            return False

    def apply_persistent_mocap_input_mode(self):
        saved_mode = normalize_mocap_input_mode(
            self.persistent_ui_state.get("mocap_input_mode", self.mocap_input_mode))
        if saved_mode != MOCAP_INPUT_MODE_MOUSE_AUDIO and not face_capture_assets_ready(get_portable_root()):
            saved_mode = MOCAP_INPUT_MODE_MOUSE_AUDIO
        self.set_mocap_input_mode(saved_mode, persist=False, from_user=False)

    def is_mouse_audio_mocap_mode(self) -> bool:
        return self.mocap_input_mode == MOCAP_INPUT_MODE_MOUSE_AUDIO

    def set_mocap_input_mode(
            self,
            mode: str,
            *,
            persist: bool = True,
            from_user: bool = False) -> bool:
        mode = normalize_mocap_input_mode(mode)
        previous_mode = self.mocap_input_mode
        if mode == previous_mode:
            self.refresh_mocap_input_mode_ui()
            return True

        if mode == MOCAP_INPUT_MODE_MEDIAPIPE:
            if not face_capture_assets_ready(get_portable_root()):
                if from_user:
                    show_rate_limited_message(
                        self.get_dialog_parent(),
                        "摄像头面捕需要 face_puppeteer 可选包（MediaPipe + .task）。\n\n"
                        "请运行 DEPLOY.bat 选择 [2] face_puppeteer，或继续使用 Mouse + Audio 模式。\n\n"
                        "Face capture requires the face_puppeteer add-on.\n"
                        "Run DEPLOY.bat option [2], or stay on Mouse + Audio.",
                        "Face capture add-on required",
                        style=wx.OK | wx.ICON_INFORMATION,
                        dialog_key="face_capture_addon_required")
                return False
            if not self.ensure_face_landmarker(show_dialog=from_user):
                return False

        if mode == MOCAP_INPUT_MODE_MOUSE_AUDIO:
            if from_user or self._mouth_input_mode_before_mouse_audio is None:
                self._mouth_input_mode_before_mouse_audio = self.pose_converter.args.mouth_input_mode
            self.pose_converter.args.set_mouth_input_mode("audio")
            if hasattr(self.pose_converter, "mouth_input_mode_choice"):
                self.pose_converter.mouth_input_mode_choice.SetSelection(1)
            if hasattr(self.pose_converter, "refresh_audio_input_runtime"):
                self.pose_converter.refresh_audio_input_runtime(time.time())
            self.schedule_active_capture_timer()
        elif previous_mode == MOCAP_INPUT_MODE_MOUSE_AUDIO:
            restore_mode = self._mouth_input_mode_before_mouse_audio or "face"
            self.pose_converter.args.set_mouth_input_mode(restore_mode)
            self._mouth_input_mode_before_mouse_audio = None
            if hasattr(self.pose_converter, "mouth_input_mode_choice"):
                self.pose_converter.mouth_input_mode_choice.SetSelection(
                    0 if restore_mode == "face" else 1)

        self.mocap_input_mode = mode
        self.refresh_mocap_input_mode_ui()
        if persist:
            self.save_persistent_ui_state()
        return True

    def get_mouse_mocap_status_message(self) -> str:
        if not self.is_mouse_audio_mocap_mode():
            return "MediaPipe 面捕 / Face capture (camera or window)"
        audio_status = getattr(self.pose_converter, "audio_status_message", None) or "Audio pending"
        audio_ready = self.pose_converter.args.mouth_input_mode == "audio"
        ready_label = "ready" if audio_ready else "inactive"
        return (
            f"Mouse+Audio: move mouse anywhere on screen.\n"
            f"Norm ({self._last_mouse_mocap_nx:+.2f}, {self._last_mouse_mocap_ny:+.2f}) | "
            f"mouth audio {ready_label}\n{audio_status}"
        )

    def _load_mouse_mocap_settings_from_persistent(self, data: Optional[dict] = None) -> None:
        if data is None:
            data = self.persistent_ui_state
        self._mouse_mocap_config.blink_interval_sec = clamp_blink_interval_sec(
            float(data.get("mouse_blink_interval_sec", self._mouse_mocap_config.blink_interval_sec)))
        zone_raw = data.get("mouse_center_zone")
        self._mouse_mocap_config.center_zone = MouseCenterZone.from_mapping(
            zone_raw if isinstance(zone_raw, dict) else None)
        self._mouse_mocap_config.horizontal_tilt_mix = clamp_horizontal_tilt_mix(
            float(data.get("mouse_horizontal_tilt_mix", self._mouse_mocap_config.horizontal_tilt_mix)))
        try:
            self._mouse_mocap_config.gaze_neutral_nx = float(
                data.get("mouse_gaze_neutral_nx", self._mouse_mocap_config.gaze_neutral_nx))
            self._mouse_mocap_config.gaze_neutral_ny = float(
                data.get("mouse_gaze_neutral_ny", self._mouse_mocap_config.gaze_neutral_ny))
        except (TypeError, ValueError):
            pass
        self._mouse_mocap_config.gaze_neutral_nx = clamp(
            self._mouse_mocap_config.gaze_neutral_nx, -1.0, 1.0)
        self._mouse_mocap_config.gaze_neutral_ny = clamp(
            self._mouse_mocap_config.gaze_neutral_ny, -1.0, 1.0)
        self._enable_mouse_auto_calibration = bool(data.get("enable_mouse_auto_calibration", False))
        try:
            self._mouse_auto_calibration_interval_seconds = max(
                1.0,
                min(3600.0, float(data.get("mouse_auto_calibration_interval_seconds", 300.0))))
        except (TypeError, ValueError):
            self._mouse_auto_calibration_interval_seconds = 300.0

    def apply_mouse_mocap_controls_from_persistent(self) -> None:
        self._load_mouse_mocap_settings_from_persistent(self.persistent_ui_state)
        if hasattr(self, "mouse_blink_interval_spin"):
            self.mouse_blink_interval_spin.SetValue(self._mouse_mocap_config.blink_interval_sec)
        if hasattr(self, "mouse_zone_panel"):
            self.mouse_zone_panel.set_zone(self._mouse_mocap_config.center_zone)
        if hasattr(self, "mouse_horizontal_tilt_mix_spin"):
            self.mouse_horizontal_tilt_mix_spin.SetValue(self._mouse_mocap_config.horizontal_tilt_mix)
        if hasattr(self, "enable_mouse_auto_calibration_checkbox"):
            self.enable_mouse_auto_calibration_checkbox.SetValue(self._enable_mouse_auto_calibration)
        if hasattr(self, "mouse_auto_calibration_interval_seconds_ctrl"):
            self.mouse_auto_calibration_interval_seconds_ctrl.SetValue(
                self._mouse_auto_calibration_interval_seconds)
        self._apply_mouse_only_controls_visibility()

    def _apply_mouse_only_controls_visibility(self) -> None:
        mouse_mode = self.is_mouse_audio_mocap_mode()
        parent_sizer = getattr(self, "model_input_column_sizer", None)
        show_video = not mouse_mode

        def _show_widget(widget: Optional[wx.Window], show: bool) -> None:
            if widget is None or parent_sizer is None:
                return
            try:
                parent_sizer.Show(widget, show=show)
            except RuntimeError:
                pass

        _show_widget(getattr(self, "mouse_only_controls_panel", None), mouse_mode)
        _show_widget(getattr(self, "video_source_section_separator", None), show_video)
        _show_widget(getattr(self, "video_source_title", None), show_video)
        _show_widget(getattr(self, "video_source_panel", None), show_video)
        parent = getattr(self, "model_input_column", None)
        if parent is not None:
            try:
                parent.Layout()
            except RuntimeError:
                pass

    def on_mouse_blink_interval_changed(self, event: Optional[wx.Event] = None) -> None:
        if hasattr(self, "mouse_blink_interval_spin"):
            self._mouse_mocap_config.blink_interval_sec = clamp_blink_interval_sec(
                self.mouse_blink_interval_spin.GetValue())
        self.save_persistent_ui_state()
        if event is not None:
            event.Skip()

    def on_mouse_center_zone_changed(self, zone: MouseCenterZone) -> None:
        self._mouse_mocap_config.center_zone = zone.clamped_to_surface()
        calib_nx, calib_ny = mouse_center_zone_calibration_point(self._mouse_mocap_config.center_zone)
        self._mouse_mocap_config.gaze_neutral_nx = calib_nx
        self._mouse_mocap_config.gaze_neutral_ny = calib_ny
        if self.neutral_face_screen_motion is not None:
            self.update_neutral_output_enhancement(FaceScreenMotion(
                center_x=calib_nx,
                center_y=calib_ny,
                face_size=self.neutral_face_screen_motion.face_size))
        if hasattr(self, "mouse_zone_panel"):
            self.mouse_zone_panel.set_zone(self._mouse_mocap_config.center_zone, refresh=False)
        self.save_persistent_ui_state()

    def on_mouse_horizontal_tilt_mix_changed(self, event: Optional[wx.Event] = None) -> None:
        if hasattr(self, "mouse_horizontal_tilt_mix_spin"):
            self._mouse_mocap_config.horizontal_tilt_mix = clamp_horizontal_tilt_mix(
                self.mouse_horizontal_tilt_mix_spin.GetValue())
        self.save_persistent_ui_state()
        if event is not None:
            event.Skip()

    def on_mouse_auto_calibration_checkbox_changed(self, event: wx.Event) -> None:
        if hasattr(self, "enable_mouse_auto_calibration_checkbox"):
            self._enable_mouse_auto_calibration = bool(
                self.enable_mouse_auto_calibration_checkbox.GetValue())
        # Defer first periodic calibration until the interval elapses (avoid jumping zone on enable).
        self.last_mouse_calibration_time = time.time()
        self.save_persistent_ui_state()
        event.Skip()

    def on_mouse_auto_calibration_interval_changed(self, event: wx.Event) -> None:
        if hasattr(self, "mouse_auto_calibration_interval_seconds_ctrl"):
            try:
                self._mouse_auto_calibration_interval_seconds = max(
                    1.0,
                    min(3600.0, float(self.mouse_auto_calibration_interval_seconds_ctrl.GetValue())))
            except (TypeError, ValueError):
                pass
        self.last_mouse_calibration_time = time.time()
        self.save_persistent_ui_state()
        event.Skip()

    def calibrate_mouse_dynamic_enhancement(
            self,
            nx: float,
            ny: float,
            *,
            calibration_time: Optional[float] = None) -> bool:
        """Mouse ix-023: path B (zone/gaze/neutral) + path A at calibrated forward gaze."""
        return self._calibrate_mouse_dynamic_enhancement_ix023(
            nx,
            ny,
            calibration_time=calibration_time)

    def _calibrate_mouse_dynamic_enhancement_ix023(
            self,
            nx: float,
            ny: float,
            *,
            calibration_time: Optional[float] = None) -> bool:
        """ix-023 body shared by UI-A02/A10 manual click and UI-B07 periodic auto-click."""
        zone = self._mouse_mocap_config.center_zone.clamped_to_surface()
        self._mouse_mocap_config.center_zone = zone.with_center_at_preserving_size(nx, ny).clamped_to_surface()
        calib_nx, calib_ny = mouse_center_zone_calibration_point(self._mouse_mocap_config.center_zone)
        face_size = face_size_from_zone_distance(calib_nx, calib_ny, self._mouse_mocap_config.center_zone)
        motion = FaceScreenMotion(center_x=calib_nx, center_y=calib_ny, face_size=face_size)
        self.update_neutral_output_enhancement(motion)
        if hasattr(self, "mouse_zone_panel"):
            self.mouse_zone_panel.set_zone(self._mouse_mocap_config.center_zone)

        self._mouse_mocap_config.gaze_neutral_nx = calib_nx
        self._mouse_mocap_config.gaze_neutral_ny = calib_ny
        time_now = time.time() if calibration_time is None else calibration_time
        forward_pose, _, _ = build_mouse_mediapipe_face_pose(
            time_now,
            self._mouse_mocap_config,
            nx=calib_nx,
            ny=calib_ny)
        self.mediapipe_face_pose = forward_pose
        pose_converter = getattr(self, "pose_converter", None)
        if pose_converter is not None and hasattr(pose_converter, "apply_face_orientation_calibration"):
            if pose_converter.apply_face_orientation_calibration():
                self.last_direction_calibration_time = time_now
        roll_deg = extract_head_roll_degrees(forward_pose)
        self.neutral_head_roll_deg = roll_deg
        self.latest_head_roll_deg = roll_deg
        self.last_mouse_calibration_time = time_now
        self.last_scale_calibration_time = time_now
        return True

    def _perform_output_dynamic_enhancement_calibration(
            self,
            *,
            calibration_time: Optional[float] = None) -> bool:
        """Path B manual body: camera = neutral pan/scale; mouse = ix-023 (includes path A at gaze neutral)."""
        if self.is_mouse_audio_mocap_mode():
            return self._calibrate_mouse_dynamic_enhancement_ix023(
                self._last_mouse_mocap_nx,
                self._last_mouse_mocap_ny,
                calibration_time=calibration_time)
        if self.latest_face_screen_motion is None:
            return False
        time_now = time.time() if calibration_time is None else calibration_time
        self.update_neutral_output_enhancement(self.latest_face_screen_motion)
        self.last_scale_calibration_time = time_now
        return True

    def _refresh_after_output_dynamic_enhancement_calibration(self) -> None:
        self.refresh_scale_curve_status()
        self.request_scale_curve_repaint(force=True)
        self.update_display_transform_state(
            snap_to_target=not self.enable_auto_transform_checkbox.GetValue())
        self.refresh_auto_transform_status(
            "READY" if self.enable_auto_transform_checkbox.GetValue() else "OFF")
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
        self.save_persistent_ui_state()

    def maybe_apply_periodic_mouse_calibration(self, time_now: float, nx: float, ny: float) -> None:
        """UI-B07: periodic auto-click of UI-A02/A10 in Mouse+Audio mode."""
        del nx, ny  # same sample as _last_mouse_mocap_* used by _perform_output_dynamic_enhancement_calibration
        if not self.is_mouse_audio_mocap_mode() or not self._enable_mouse_auto_calibration:
            return
        interval_seconds = max(1.0, float(self._mouse_auto_calibration_interval_seconds))
        if self.last_mouse_calibration_time is None:
            self.last_mouse_calibration_time = time_now
            return
        if time_now - self.last_mouse_calibration_time < interval_seconds:
            return
        if self._perform_output_dynamic_enhancement_calibration(calibration_time=time_now):
            self._refresh_after_output_dynamic_enhancement_calibration()

    def _update_mouse_dynamic_enhancement_motion(
            self,
            nx: float,
            ny: float,
            mediapipe_face_pose: MediaPipeFacePose) -> None:
        zone = self._mouse_mocap_config.center_zone.clamped_to_surface()
        neutral_motion = self.neutral_face_screen_motion
        if neutral_motion is not None:
            neutral_center_x = neutral_motion.center_x
            neutral_center_y = neutral_motion.center_y
            neutral_face_size = neutral_motion.face_size
        else:
            neutral_center_x = 0.0
            neutral_center_y = 0.0
            neutral_face_size = MOUSE_DEFAULT_FACE_SIZE

        if is_mouse_inside_center_zone(nx, ny, zone):
            self.latest_face_screen_motion = FaceScreenMotion(
                center_x=neutral_center_x,
                center_y=neutral_center_y,
                face_size=neutral_face_size)
        else:
            center_x, center_y, face_size = build_mouse_dynamic_face_screen_motion(
                nx,
                ny,
                zone,
                neutral_center_x=neutral_center_x,
                neutral_center_y=neutral_center_y,
                neutral_face_size=neutral_face_size,
                horizontal_tilt_mix=self._mouse_mocap_config.horizontal_tilt_mix)
            self.latest_face_screen_motion = FaceScreenMotion(
                center_x=center_x,
                center_y=center_y,
                face_size=face_size)

        pose_roll_deg = extract_head_roll_degrees(mediapipe_face_pose)
        local_x, _local_y = zone_local_coords(nx, ny, zone)
        try:
            tilt_limit_deg = max(0.0, float(self.tilt_limit_spin.GetValue()))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            tilt_limit_deg = 30.0
        self.latest_head_roll_deg = blend_mouse_head_roll_degrees(
            pose_roll_deg,
            self.neutral_head_roll_deg,
            local_x,
            tilt_limit_deg,
            self._mouse_mocap_config.horizontal_tilt_mix)

        if hasattr(self, "mouse_zone_panel"):
            self.mouse_zone_panel.set_mouse_position(nx, ny)

        self.maybe_apply_periodic_mouse_calibration(time_now=time.time(), nx=nx, ny=ny)

    def refresh_mocap_input_mode_ui(self) -> None:
        if hasattr(self, "mocap_input_mode_choice") and self.mocap_input_mode_choice is not None:
            try:
                if self.mocap_input_mode in MOCAP_INPUT_MODE_VALUES:
                    self.mocap_input_mode_choice.SetSelection(
                        MOCAP_INPUT_MODE_VALUES.index(self.mocap_input_mode))
            except RuntimeError:
                pass
        if hasattr(self, "mocap_input_mode_status_text") and self.mocap_input_mode_status_text is not None:
            self.set_wrapped_static_text_if_changed(
                self.mocap_input_mode_status_text,
                self.get_mouse_mocap_status_message())
        self._apply_mouse_only_controls_visibility()

    def update_mouse_mocap_face_pose(self, time_now: float) -> None:
        pose, nx, ny = build_mouse_mediapipe_face_pose(
            time_now,
            self._mouse_mocap_config)
        self._last_mouse_mocap_nx = nx
        self._last_mouse_mocap_ny = ny
        self.mediapipe_face_pose = pose
        self.last_face_detected_time = time_now
        self._update_mouse_dynamic_enhancement_motion(nx, ny, pose)
        if hasattr(self.pose_converter, "refresh_audio_input_runtime"):
            self.pose_converter.refresh_audio_input_runtime(time_now)
        if self._capture_frame_serial % 12 == 0:
            self.refresh_mocap_input_mode_ui()

    def on_animation_panel_mousewheel_logged(self, event: wx.MouseEvent):
        self.on_mousewheel_scroll(event)

    def create_compact_launcher_panel(self, parent):
        self.compact_launcher_panel = wx.Panel(parent, style=wx.SIMPLE_BORDER)
        compact_launcher_sizer = wx.BoxSizer(wx.VERTICAL)
        self.compact_launcher_panel.SetSizer(compact_launcher_sizer)
        self.compact_launcher_panel.SetAutoLayout(1)
        self.compact_launcher_panel.SetDoubleBuffered(True)

        self.quick_calibrate_head_orientation_button = wx.Button(
            self.compact_launcher_panel, wx.ID_ANY, "校正头部朝向 / Calibrate Head Orientation")
        self.quick_calibrate_head_orientation_button.Bind(wx.EVT_BUTTON, self.calibrate_head_orientation_quick)
        compact_launcher_sizer.Add(self.quick_calibrate_head_orientation_button, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.quick_calibrate_scale_button = wx.Button(
            self.compact_launcher_panel, wx.ID_ANY, "输出动态增强校准 / Output Dynamic Enhancement Calibration")
        self.quick_calibrate_scale_button.Bind(wx.EVT_BUTTON, self.calibrate_scale_clicked)
        compact_launcher_sizer.Add(self.quick_calibrate_scale_button, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.toggle_full_controls_button = wx.Button(
            self.compact_launcher_panel, wx.ID_ANY, "切换到完整调参窗 / Open Full Controls")
        self.toggle_full_controls_button.Bind(wx.EVT_BUTTON, self.toggle_full_controls_clicked)
        compact_launcher_sizer.Add(self.toggle_full_controls_button, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        compact_hint_text = wx.StaticText(
            self.compact_launcher_panel,
            label="加载新模型请点展开完整 / To load a new model, open full controls",
            style=wx.ALIGN_CENTER_HORIZONTAL)
        compact_launcher_sizer.Add(compact_hint_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        compact_launcher_sizer.Fit(self.compact_launcher_panel)

    def create_ui(self):
        self.compact_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.compact_sizer)
        self.SetAutoLayout(1)

        self.capture_pose_lock = threading.Lock()

        self.create_compact_launcher_panel(self)
        self.compact_sizer.Add(self.compact_launcher_panel, 0, wx.EXPAND | wx.ALL, 5)

        self.compact_sizer.Fit(self)
        fitted_size = self.compact_sizer.GetMinSize()
        self._compact_default_client_size = wx.Size(
            max(self.COMPACT_MIN_CLIENT_WIDTH, int(fitted_size.x)),
            max(self.COMPACT_MIN_CLIENT_HEIGHT, int(fitted_size.y)))
        self.SetMinClientSize(self._compact_default_client_size)

    def create_controls_frame(self):
        if self.controls_frame is not None:
            return

        controls_build_t0 = time.perf_counter()
        self._controls_build_in_progress = True
        self.controls_frame = ControlsFrame(self)
        try:
            self.main_sizer = wx.BoxSizer(wx.VERTICAL)
            self.controls_frame.SetSizer(self.main_sizer)
            self.controls_frame.SetAutoLayout(1)

            controls_header_panel = wx.Panel(self.controls_frame)
            controls_header_sizer = wx.BoxSizer(wx.VERTICAL)
            controls_header_panel.SetSizer(controls_header_sizer)
            controls_header_panel.SetAutoLayout(1)
            self.main_sizer.Add(controls_header_panel, 0, wx.EXPAND | wx.ALL, 5)

            controls_header_row1 = wx.BoxSizer(wx.HORIZONTAL)
            controls_header_row2 = wx.BoxSizer(wx.HORIZONTAL)
            controls_header_sizer.Add(controls_header_row1, 0, wx.EXPAND)
            controls_header_sizer.Add(controls_header_row2, 0, wx.EXPAND | wx.TOP, 4)

            self.switch_to_compact_button = wx.Button(
                controls_header_panel, wx.ID_ANY, "切换到精简小窗 / Switch to Compact")
            self.switch_to_compact_button.Bind(wx.EVT_BUTTON, self.switch_to_compact_clicked)
            controls_header_row1.Add(self.switch_to_compact_button, 0, wx.EXPAND)

            self.load_last_tha3_png_button = wx.Button(
                controls_header_panel,
                wx.ID_ANY,
                "加载上次立绘 / Load Last Portrait")
            self.load_last_tha3_png_button.Bind(wx.EVT_BUTTON, self.load_last_tha3_character_png)
            controls_header_row1.Add(self.load_last_tha3_png_button, 0, wx.EXPAND | wx.LEFT, 6)

            self.load_tha3_other_png_button = wx.Button(
                controls_header_panel,
                wx.ID_ANY,
                "加载其他立绘 / Load Other Portrait")
            self.load_tha3_other_png_button.Bind(wx.EVT_BUTTON, self.load_tha3_character_png)
            controls_header_row1.Add(self.load_tha3_other_png_button, 0, wx.EXPAND | wx.LEFT, 6)

            self.load_last_model_button = wx.Button(
                controls_header_panel,
                wx.ID_ANY,
                "加载上次 THA4 Student / Load Last THA4 Student")
            self.load_last_model_button.Bind(wx.EVT_BUTTON, self.load_last_model)
            controls_header_row2.Add(self.load_last_model_button, 0, wx.EXPAND)

            self.load_model_button = wx.Button(
                controls_header_panel,
                wx.ID_ANY,
                "加载其他 THA4 Student 模型 / Load Other THA4 Student Model")
            self.load_model_button.Bind(wx.EVT_BUTTON, self.load_model)
            controls_header_row2.Add(self.load_model_button, 0, wx.EXPAND | wx.LEFT, 6)
            self.update_load_model_buttons()

            self.main_splitter = wx.SplitterWindow(
                self.controls_frame,
                style=wx.SP_LIVE_UPDATE | wx.SP_3D | wx.SP_BORDER)
            self.main_splitter.SetMinimumPaneSize(MainFrame.CONTROLS_COLUMN_MIN_WIDTH)
            self.main_splitter.SetSashGravity(0.5)
            self.main_splitter.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.on_column_splitter_changed)
            self.main_sizer.Add(self.main_splitter, wx.SizerFlags(1).Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 5))

            self.create_animation_panel(self.main_splitter)

            self.right_sidebar = wx.Panel(self.main_splitter)
            self.right_sidebar_sizer = wx.BoxSizer(wx.VERTICAL)
            self.right_sidebar.SetSizer(self.right_sidebar_sizer)
            self.right_sidebar.SetAutoLayout(1)
            self.right_sidebar.SetDoubleBuffered(True)
            self.right_sidebar.SetMinSize(
                wx.Size(MainFrame.CAPTURE_PANEL_MIN_WIDTH, MainFrame.CAPTURE_PANEL_MIN_HEIGHT + 120))

            self.right_sidebar_splitter = wx.SplitterWindow(
                self.right_sidebar,
                style=wx.SP_LIVE_UPDATE | wx.SP_3D | wx.SP_BORDER)
            self.right_sidebar_splitter.SetMinimumPaneSize(MainFrame.RIGHT_SIDEBAR_PANE_MIN_HEIGHT)
            self.right_sidebar_splitter.SetSashGravity(0.5)
            self.right_sidebar_splitter.Bind(
                wx.EVT_SPLITTER_SASH_POS_CHANGED, self.on_column_splitter_changed)
            self.right_sidebar_sizer.Add(self.right_sidebar_splitter, 1, wx.EXPAND)

            self.create_capture_panel(self.right_sidebar_splitter)
            self.capture_panel.SetMinSize(
                wx.Size(MainFrame.CAPTURE_PANEL_MIN_WIDTH, MainFrame.CAPTURE_PANEL_MIN_HEIGHT))

            self.postprocess_scroll = wx.ScrolledWindow(
                self.right_sidebar_splitter,
                style=wx.SIMPLE_BORDER | wx.VSCROLL)
            self.postprocess_scroll.SetScrollRate(10, 10)
            self.postprocess_scroll.EnableScrolling(False, True)
            self.postprocess_scroll.SetDoubleBuffered(True)
            self.postprocess_scroll.Bind(wx.EVT_SIZE, self.on_postprocess_scroll_size)
            self.postprocess_scroll_sizer = wx.BoxSizer(wx.VERTICAL)
            self.postprocess_scroll.SetSizer(self.postprocess_scroll_sizer)

            self.create_postprocess_panel(self.postprocess_scroll)
            self.postprocess_scroll_sizer.Add(self.postprocess_panel, 1, wx.EXPAND)

            if not self.right_sidebar_splitter.IsSplit():
                self.right_sidebar_splitter.SplitHorizontally(
                    self.capture_panel,
                    self.postprocess_scroll,
                    sashPosition=MainFrame.compute_equal_halves_sash(
                        max(MainFrame.CAPTURE_PANEL_MIN_HEIGHT * 2, self.right_sidebar_splitter.GetClientSize().y),
                        self.right_sidebar_splitter.GetMinimumPaneSize()))

            if not self.main_splitter.IsSplit():
                self.main_splitter.SplitVertically(
                    self.animation_panel,
                    self.right_sidebar,
                    sashPosition=MainFrame.compute_equal_thirds_main_sash(
                        max(MainFrame.CONTROLS_MIN_CLIENT_WIDTH, self.main_splitter.GetClientSize().x),
                        MainFrame.CONTROLS_TWO_COLUMN_MIN_WIDTH,
                        MainFrame.RIGHT_SIDEBAR_MIN_WIDTH))

            self.main_sizer.Layout()
            self.refresh_model_loaded_ui_state()
            self.on_display_transform_control_changed()
            try:
                self.update_source_image_bitmap()
            except Exception:
                pass
            if hasattr(self, "webcam_capture_panel"):
                self.webcam_capture_panel.Refresh(False)
        finally:
            self._controls_build_in_progress = False
            _startup_record(
                "create_controls_frame (build full controls UI)",
                (time.perf_counter() - controls_build_t0) * 1000.0)
            self._wire_ui_change_logging()
            self._refresh_ui_change_history_display()

    def create_capture_panel(self, parent):
        self.capture_panel = wx.Panel(parent, style=wx.RAISED_BORDER)
        self.capture_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.capture_panel.SetSizer(self.capture_panel_sizer)
        self.capture_panel.SetAutoLayout(1)
        self.capture_panel.SetDoubleBuffered(True)

        preview_header = wx.StaticText(
            self.capture_panel,
            label="--- 预览区 / Preview (D 上) ---",
            style=wx.ALIGN_CENTER)
        self.capture_panel_sizer.Add(preview_header, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)

        previews_row = wx.BoxSizer(wx.HORIZONTAL)

        self.source_preview_column = wx.Panel(self.capture_panel)
        source_preview_sizer = wx.BoxSizer(wx.VERTICAL)
        self.source_preview_column.SetSizer(source_preview_sizer)
        self.source_preview_column.SetAutoLayout(1)
        self.source_preview_column.SetDoubleBuffered(True)
        # Keep source preview + FPS area stable to avoid panel squeezing.
        self.source_preview_column.SetMinSize(
            wx.Size(MainFrame.SOURCE_PREVIEW_SIZE + 12, MainFrame.SOURCE_PREVIEW_SIZE + 108)
        )

        self.source_preview_caption_text = wx.StaticText(
            self.source_preview_column,
            label="立绘源预览 / Character source\n(加载后的静态立绘快照)",
            style=wx.ALIGN_CENTER)
        source_preview_sizer.Add(
            self.source_preview_caption_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)

        self.source_image_panel = wx.Panel(
            self.source_preview_column,
            size=(MainFrame.SOURCE_PREVIEW_SIZE, MainFrame.SOURCE_PREVIEW_SIZE),
            style=wx.SIMPLE_BORDER)
        self.source_image_panel.SetBackgroundColour(MainFrame.PREVIEW_IDLE_BACKGROUND)
        self.source_image_panel.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.source_image_panel.SetDoubleBuffered(True)
        self.source_image_panel.Bind(wx.EVT_PAINT, self.paint_source_image_panel)
        self.source_image_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)
        self.source_image_panel.Bind(wx.EVT_SHOW, self.on_source_image_panel_show)
        self.source_image_panel.Bind(wx.EVT_SIZE, self.on_source_image_panel_size)
        source_preview_sizer.Add(self.source_image_panel, wx.SizerFlags(0).FixedMinSize().Border(wx.ALL, 5))

        self.fps_text = wx.StaticText(
            self.source_preview_column,
            label="帧率 / FPS\n输入 In --\n推理 Inf --\n显示 Out --")
        source_preview_sizer.Add(self.fps_text, wx.SizerFlags(0).Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 5))

        previews_row.Add(self.source_preview_column, wx.SizerFlags(0).Border(wx.ALL, 5))

        self.webcam_container = wx.Panel(
            self.capture_panel,
            size=(MainFrame.WEBCAM_PREVIEW_SIZE, MainFrame.WEBCAM_PREVIEW_SIZE + 128))
        webcam_container_sizer = wx.BoxSizer(wx.VERTICAL)
        self.webcam_container.SetSizer(webcam_container_sizer)
        self.webcam_container.SetAutoLayout(1)
        self.webcam_container.SetDoubleBuffered(True)

        self.webcam_capture_panel = wx.Panel(
            self.webcam_container,
            size=(MainFrame.WEBCAM_PREVIEW_SIZE, MainFrame.WEBCAM_PREVIEW_SIZE),
            style=wx.SIMPLE_BORDER)
        self.webcam_capture_panel.SetMinSize(
            wx.Size(MainFrame.WEBCAM_PREVIEW_SIZE, MainFrame.WEBCAM_PREVIEW_SIZE))
        self.webcam_capture_panel.SetBackgroundColour(MainFrame.PREVIEW_IDLE_BACKGROUND)
        self.webcam_capture_panel.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.webcam_capture_panel.SetDoubleBuffered(True)
        self.webcam_capture_panel.Bind(wx.EVT_PAINT, self.paint_webcam_capture_panel)
        self.webcam_capture_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)
        self.webcam_capture_panel.Bind(wx.EVT_SHOW, self.on_webcam_capture_panel_show)
        self.webcam_capture_panel.Bind(wx.EVT_SIZE, self.on_webcam_capture_panel_size)
        self.webcam_capture_panel.Bind(wx.EVT_LEFT_DCLICK, self.on_webcam_preview_double_click)

        self.webcam_preview_caption_text = wx.StaticText(
            self.webcam_container,
            label="摄像头 / 窗口捕获预览 / Live capture\n(当前面捕输入画面，双击可放大)",
            style=wx.ALIGN_CENTER)
        webcam_container_sizer.Add(
            self.webcam_preview_caption_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)
        webcam_container_sizer.Add(self.webcam_capture_panel, wx.SizerFlags(0).FixedMinSize().Border(wx.ALL, 5))
        self.ui_change_history_text = wx.StaticText(
            self.webcam_container,
            label="最近改动 / Recent UI\n—\n—\n—")
        webcam_container_sizer.Add(
            self.ui_change_history_text,
            wx.SizerFlags(0).Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 5))
        previews_row.Add(
            self.webcam_container,
            wx.SizerFlags(0).FixedMinSize().Border(wx.ALL, 5))
        self.create_preview_calibration_controls(self.capture_panel, previews_row)
        self.capture_panel_sizer.Add(previews_row, 0, wx.EXPAND)

        self.rotation_labels = {}
        self.rotation_value_labels = {}
        rotation_caption = wx.StaticText(
            self.capture_panel,
            label="头部旋转示值（只读）/ Head rotation readout",
            style=wx.ALIGN_CENTER)
        self.capture_panel_sizer.Add(rotation_caption, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)
        rotation_column = self.create_rotation_column(self.capture_panel, HEAD_ROTATIONS)
        self.capture_panel_sizer.Add(rotation_column, wx.SizerFlags(0).Expand().Border(wx.ALL, 3))

        self._invalidate_source_preview_cache()
        self.update_source_image_bitmap(force=True)
        MainFrame.fill_bitmap_solid(self.webcam_capture_bitmap, MainFrame.PREVIEW_IDLE_BACKGROUND)

    def create_preview_calibration_controls(self, parent: wx.Panel, parent_sizer: wx.BoxSizer) -> None:
        enable_direction_calibration = self.enable_direction_calibration_checkbox.GetValue()
        direction_interval_seconds = self.auto_direction_calibration_interval_seconds_ctrl.GetValue()
        enable_scale_calibration = self.enable_scale_calibration_checkbox.GetValue()
        scale_interval_seconds = self.auto_scale_calibration_interval_seconds_ctrl.GetValue()

        self.preview_calibration_column = wx.Panel(parent)
        self.preview_calibration_column.SetAutoLayout(1)
        self.preview_calibration_column.SetDoubleBuffered(True)
        self.preview_calibration_column.SetMinSize(
            wx.Size(MainFrame.PREVIEW_CALIBRATION_COLUMN_MIN_WIDTH, -1))
        calibration_column_sizer = wx.BoxSizer(wx.VERTICAL)
        self.preview_calibration_column.SetSizer(calibration_column_sizer)

        calibration_header = wx.StaticText(
            self.preview_calibration_column,
            label="--- 校准 / Calibration ---",
            style=wx.ALIGN_CENTER)
        calibration_column_sizer.Add(calibration_header, 0, wx.EXPAND | wx.BOTTOM, 4)

        self.direction_calibration_panel = wx.Panel(self.preview_calibration_column)
        direction_calibration_sizer = wx.BoxSizer(wx.VERTICAL)
        self.direction_calibration_panel.SetSizer(direction_calibration_sizer)
        self.direction_calibration_panel.SetAutoLayout(1)

        self.enable_direction_calibration_checkbox = wx.CheckBox(
            self.direction_calibration_panel,
            label="周期执行「我正看前方」/ Auto Calibrate Forward Gaze")
        self.enable_direction_calibration_checkbox.SetValue(enable_direction_calibration)
        self.enable_direction_calibration_checkbox.Bind(wx.EVT_CHECKBOX, self.on_display_transform_control_changed)
        direction_calibration_sizer.Add(
            self.enable_direction_calibration_checkbox,
            0, wx.EXPAND | wx.BOTTOM, 4)

        self.calibrate_neutral_button = wx.Button(
            self.direction_calibration_panel,
            label="标定朝向 / Calibrate Head Orientation")
        self.calibrate_neutral_button.Bind(wx.EVT_BUTTON, self.calibrate_neutral_clicked)
        direction_calibration_sizer.Add(
            self.calibrate_neutral_button,
            0, wx.EXPAND | wx.BOTTOM, 4)

        self.direction_calibration_interval_panel = wx.Panel(self.direction_calibration_panel)
        direction_calibration_interval_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.direction_calibration_interval_panel.SetSizer(direction_calibration_interval_sizer)
        self.direction_calibration_interval_panel.SetAutoLayout(1)
        direction_calibration_sizer.Add(self.direction_calibration_interval_panel, 0, wx.EXPAND)

        calibration_column_sizer.Add(
            self.direction_calibration_panel,
            0, wx.EXPAND | wx.BOTTOM, 6)

        direction_interval_label = wx.StaticText(
            self.direction_calibration_interval_panel,
            label=slider_label("朝向前方周期", "Forward Gaze Interval", "秒", "s"))
        direction_calibration_interval_sizer.Add(
            direction_interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        self.auto_direction_calibration_interval_seconds_ctrl = wx.SpinCtrlDouble(
            self.direction_calibration_interval_panel,
            wx.ID_ANY,
            min=1.0,
            max=3600.0,
            initial=direction_interval_seconds,
            inc=1.0,
            style=wx.SP_ARROW_KEYS)
        self.auto_direction_calibration_interval_seconds_ctrl.SetDigits(0)
        self.auto_direction_calibration_interval_seconds_ctrl.Bind(
            wx.EVT_SPINCTRLDOUBLE, self.on_display_transform_control_changed)
        self.auto_direction_calibration_interval_seconds_ctrl.Bind(
            wx.EVT_TEXT, self.on_display_transform_control_changed)
        direction_calibration_interval_sizer.Add(
            self.auto_direction_calibration_interval_seconds_ctrl,
            0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        self.scale_calibration_panel = wx.Panel(self.preview_calibration_column)
        scale_calibration_sizer = wx.BoxSizer(wx.VERTICAL)
        self.scale_calibration_panel.SetSizer(scale_calibration_sizer)
        self.scale_calibration_panel.SetAutoLayout(1)

        self.enable_scale_calibration_checkbox = wx.CheckBox(
            self.scale_calibration_panel,
            label="启用输出动态增强自动校准 / Enable Auto Output Dynamic Enhancement Calibration")
        self.enable_scale_calibration_checkbox.SetValue(enable_scale_calibration)
        self.enable_scale_calibration_checkbox.Bind(wx.EVT_CHECKBOX, self.on_display_transform_control_changed)
        scale_calibration_sizer.Add(
            self.enable_scale_calibration_checkbox,
            0, wx.EXPAND | wx.BOTTOM, 4)

        self.calibrate_scale_button = wx.Button(
            self.scale_calibration_panel,
            label="输出动态增强校准 / Output Dynamic Enhancement Calibration")
        self.calibrate_scale_button.Bind(wx.EVT_BUTTON, self.calibrate_scale_clicked)
        scale_calibration_sizer.Add(
            self.calibrate_scale_button,
            0, wx.EXPAND | wx.BOTTOM, 4)

        self.scale_calibration_interval_panel = wx.Panel(self.scale_calibration_panel)
        scale_calibration_interval_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.scale_calibration_interval_panel.SetSizer(scale_calibration_interval_sizer)
        self.scale_calibration_interval_panel.SetAutoLayout(1)
        scale_calibration_sizer.Add(self.scale_calibration_interval_panel, 0, wx.EXPAND)

        calibration_column_sizer.Add(self.scale_calibration_panel, 0, wx.EXPAND)

        scale_interval_label = wx.StaticText(
            self.scale_calibration_interval_panel,
            label=slider_label("增强校准周期", "Enhancement Interval", "秒", "s"))
        scale_calibration_interval_sizer.Add(
            scale_interval_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        self.auto_scale_calibration_interval_seconds_ctrl = wx.SpinCtrlDouble(
            self.scale_calibration_interval_panel,
            wx.ID_ANY,
            min=1.0,
            max=3600.0,
            initial=scale_interval_seconds,
            inc=1.0,
            style=wx.SP_ARROW_KEYS)
        self.auto_scale_calibration_interval_seconds_ctrl.SetDigits(0)
        self.auto_scale_calibration_interval_seconds_ctrl.Bind(
            wx.EVT_SPINCTRLDOUBLE, self.on_display_transform_control_changed)
        self.auto_scale_calibration_interval_seconds_ctrl.Bind(
            wx.EVT_TEXT, self.on_display_transform_control_changed)
        scale_calibration_interval_sizer.Add(
            self.auto_scale_calibration_interval_seconds_ctrl,
            0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        parent_sizer.Add(
            self.preview_calibration_column,
            wx.SizerFlags(1).Expand().Border(wx.ALL, 5))

        self.on_display_transform_control_changed()

    def _init_video_source_choices_with_window(self):
        if self.video_source_choice is None:
            return
        self.video_source_choice_map.clear()
        choices: list[str] = []
        self.prepend_window_capture_choices(choices)
        choices.append("Video file... / 视频文件...")
        self.video_source_choice_map["Video file... / 视频文件..."] = ("file", None, None)
        self.video_source_choice.SetItems(choices)
        if choices:
            self.video_source_choice.SetSelection(0)
        self.update_video_source_status_text(
            "默认优先加载上次窗口捕获；无可用窗口时回退摄像头。"
            " / Prefer last window capture source, fallback to camera.")
        self.update_last_window_capture_text()
        wx.CallAfter(self.autoconnect_video_source_on_startup)

    def autoconnect_video_source_on_startup(self):
        """Connect saved window/camera without requiring a manual dropdown click."""
        if self.is_capture_source_active():
            return
        if self._video_enumeration_in_progress:
            wx.CallLater(500, self.autoconnect_video_source_on_startup)
            return
        hwnd, title = self.get_saved_window_capture()
        if hwnd:
            if self.video_source_choice is not None:
                label = self.format_window_capture_label(title)
                if label in self.video_source_choice_map:
                    self.video_source_choice.SetStringSelection(label)
            self.set_video_capture_window(hwnd, title)
            if self.is_capture_source_active():
                return
        self.connect_default_video_source()

    def setup_hover_help_bindings(self):
        if self.controls_frame is None:
            return
        self.hover_help_timer = wx.Timer(self.controls_frame)
        self.controls_frame.Bind(wx.EVT_TIMER, self.on_hover_help_timer, id=self.hover_help_timer.GetId())
        self.hover_help_popup = wx.Frame(
            None,
            style=wx.FRAME_NO_TASKBAR | wx.STAY_ON_TOP | wx.BORDER_SIMPLE)
        popup_panel = wx.Panel(self.hover_help_popup)
        popup_sizer = wx.BoxSizer(wx.VERTICAL)
        popup_panel.SetSizer(popup_sizer)
        self.hover_help_popup_text = wx.StaticText(
            popup_panel,
            label="",
            style=wx.ALIGN_LEFT)
        self.hover_help_popup_text.Wrap(320)
        popup_sizer.Add(self.hover_help_popup_text, 1, wx.EXPAND | wx.ALL, 8)
        self.hover_help_popup.SetSizer(wx.BoxSizer(wx.VERTICAL))
        self.hover_help_popup.GetSizer().Add(popup_panel, 1, wx.EXPAND)
        self.hover_help_popup.Hide()
        bind_start = time.time()
        control_count = self.count_controls_recursive(self.controls_frame)
        self.bind_hover_help_recursive(self.controls_frame)

    def count_controls_recursive(self, window: Optional[wx.Window]) -> int:
        if window is None:
            return 0
        count = 1
        for child in window.GetChildren():
            count += self.count_controls_recursive(child)
        return count

    def bind_hover_help_recursive(self, window: wx.Window):
        if window is None:
            return
        window.Bind(wx.EVT_ENTER_WINDOW, self.on_control_hover_enter)
        window.Bind(wx.EVT_LEAVE_WINDOW, self.on_control_hover_leave)
        for child in window.GetChildren():
            self.bind_hover_help_recursive(child)

    def on_control_hover_enter(self, event: wx.MouseEvent):
        hovered_window = event.GetEventObject()
        # Hide existing popup immediately when mouse moves to another control.
        self._hover_help_active_window = None
        self.hide_hover_help_popup()
        if hasattr(self, "hover_help_timer") and self.hover_help_timer.IsRunning():
            self.hover_help_timer.Stop()
        if not self.is_hover_help_enabled():
            self._hover_help_pending_window = None
            event.Skip()
            return
        if isinstance(hovered_window, wx.Window):
            self._hover_help_pending_window = hovered_window
            self.hover_help_timer.Start(self.HOVER_HELP_DELAY_MS, oneShot=True)
        event.Skip()

    def on_control_hover_leave(self, event: wx.MouseEvent):
        left_window = event.GetEventObject()
        if self._hover_help_pending_window is left_window:
            self._hover_help_pending_window = None
            if hasattr(self, "hover_help_timer") and self.hover_help_timer.IsRunning():
                self.hover_help_timer.Stop()
        if self._hover_help_active_window is left_window:
            self._hover_help_active_window = None
            self.hide_hover_help_popup()
        event.Skip()

    def on_hover_help_timer(self, event: wx.Event):
        if not self.is_hover_help_enabled():
            return
        if self._hover_help_pending_window is None:
            return
        control = self._hover_help_pending_window
        self._hover_help_active_window = control
        self.show_hover_help_popup(control, self.describe_hover_help_for_control(control))

    def is_hover_help_enabled(self) -> bool:
        control = getattr(self, "hover_help_enabled_checkbox", None)
        if control is None:
            return False
        return bool(control.GetValue())

    def on_hover_help_toggle_changed(self, event: wx.Event):
        if not self.is_hover_help_enabled():
            self._hover_help_pending_window = None
            self._hover_help_active_window = None
            if hasattr(self, "hover_help_timer") and self.hover_help_timer.IsRunning():
                self.hover_help_timer.Stop()
            self.hide_hover_help_popup()
        elif not hasattr(self, "hover_help_popup") or self.hover_help_popup is None:
            self.setup_hover_help_bindings()
        self.save_persistent_ui_state()
        event.Skip()

    def show_hover_help_popup(self, control: wx.Window, text: str):
        if not hasattr(self, "hover_help_popup") or self.hover_help_popup is None:
            return
        self.hover_help_popup_text.SetLabel(text)
        self.hover_help_popup_text.Wrap(320)
        self.hover_help_popup.Fit()
        popup_size = self.hover_help_popup.GetSize()
        mouse_pos = wx.GetMousePosition()
        x = mouse_pos.x - popup_size.x - 16
        y = mouse_pos.y - popup_size.y // 2
        display = wx.Display.GetFromPoint(mouse_pos)
        if display != wx.NOT_FOUND:
            rect = wx.Display(display).GetClientArea()
            x = max(rect.x, min(x, rect.x + rect.width - popup_size.x))
            y = max(rect.y, min(y, rect.y + rect.height - popup_size.y))
        self.hover_help_popup.SetPosition(wx.Point(x, y))
        if not self.hover_help_popup.IsShown():
            self.hover_help_popup.Show()
        self.hover_help_popup.Raise()

    def hide_hover_help_popup(self):
        if hasattr(self, "hover_help_popup") and self.hover_help_popup is not None:
            self.hover_help_popup.Hide()

    def _extract_control_label_text(self, control: wx.Window) -> str:
        if hasattr(control, "GetLabel"):
            try:
                value = str(control.GetLabel() or "")
                if value:
                    return value
            except Exception:
                pass
        parent = control.GetParent() if hasattr(control, "GetParent") else None
        if parent is None:
            return ""
        for child in parent.GetChildren():
            if isinstance(child, wx.StaticText):
                text = str(child.GetLabel() or "").strip()
                if text and "/" in text:
                    return text
        return ""

    def describe_hover_help_for_control(self, control: wx.Window) -> str:
        label_text = self._extract_control_label_text(control)
        lower_label = label_text.lower()
        keyword_map = [
            ("x 位移增益", "这个值控制角色随人脸左右移动的幅度。值越大，横向跟随越明显。"),
            ("y 位移增益", "这个值控制角色随人脸上下移动的幅度。值越大，纵向跟随越明显。"),
            ("缩放增益", "这个值控制人脸远近变化映射到角色大小变化的灵敏度。"),
            ("最小缩放", "这个值控制自动缩放可缩小到的下限，避免角色过小。"),
            ("最大缩放", "这个值控制自动缩放可放大到的上限，避免角色过大。"),
            ("倾斜上限", "这个值控制头部左右倾斜可映射到角色旋转的最大角度。"),
            ("倾斜映射和头相反", "勾选后由头倾斜推导的模型身体滚转（body_z）与头滚转（neck_z）方向相反，示意图下段脊柱同步；动态增强倾斜仍由头决定。绑定到身体的图层始终跟随动态增强的 display_rotation，不受此开关翻转。"),
            ("平滑系数", "这个值控制跟随平滑程度。越大越稳但响应更慢，越小越灵敏。"),
            ("近距曲率", "这个值控制人脸靠近镜头时的缩放曲线弯曲强度。"),
            ("远距曲率", "这个值控制人脸远离镜头时的缩放曲线弯曲强度。"),
            ("曲线弧度", "这个值控制整体缩放曲线的弧度形态。"),
            ("峰位横移", "这个值控制缩放曲线峰值位置左右偏移，用于调整中性点附近手感。"),
            ("朝向前方周期", "这个值控制自动重标定“朝向前方”的触发间隔（秒）。"),
            ("增强校准周期", "这个值控制自动重标定输出缩放基准与左右居中的触发间隔（秒）；不改变垂直基准，避免角色上漂。"),
            ("背景", "这个值控制输出底色，用于抠像或外部合成背景匹配。"),
            ("角色镜像", "开启后输出中的角色立绘左右翻转；绑定到身体/头的图层会同步镜像，未绑定图层位置不变。"),
            ("外挂图层", "这个值控制是否切换为外挂图层输出模式（会隐藏内置输出窗）。"),
            ("抗锯齿", "这个值控制渲染倍率；越高边缘更平滑，但性能开销更高。"),
            ("标定朝向", "这个操作会把当前朝向/人脸位置记为基准，后续自动跟随围绕该基准计算。"),
            ("加载上次模型", "这个操作会读取上次成功加载的模型并恢复到当前会话。"),
            ("加载其他模型", "这个操作会让你选择新的模型文件并加载。"),
            ("刷新摄像头", "这个操作会重新扫描可用摄像头/视频输入设备。"),
            ("窗口捕获", "这个操作会弹出窗口列表，选择要捕获的画面源（如 DroidCam 预览）。"),
            ("摄像头输入源", "这个选项控制当前用于面捕输入的视频来源。"),
        ]
        for key, desc in keyword_map:
            key_lower = key.lower()
            if key_lower in lower_label:
                return desc
        if label_text:
            return f"该项控制：{label_text}\n当前暂无细化说明，可继续补充映射。"
        return "该项用于当前界面参数控制；可继续补充精确语义说明。"

    def on_webcam_preview_double_click(self, event: wx.MouseEvent):
        if self.webcam_preview_popup_frame is not None and self.webcam_preview_popup_frame.IsShown():
            self.webcam_preview_popup_frame.Close()
        else:
            self.webcam_preview_popup_frame = WebcamPreviewPopupFrame(self)
            self.webcam_preview_popup_frame.Show()
            self.webcam_preview_popup_frame.Raise()
        event.Skip()

    @staticmethod
    def get_windows_camera_device_names() -> list[str]:
        try:
            import subprocess

            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            powershell_exe = os.path.join(
                system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
            if not os.path.isfile(powershell_exe):
                return []

            creation_flags = 0
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creation_flags = subprocess.CREATE_NO_WINDOW

            completed = subprocess.run(
                [
                    powershell_exe,
                    "-NoProfile",
                    "-Command",
                    "Get-CimInstance Win32_PnPEntity | Where-Object { $_.PNPClass -eq 'Camera' } | Select-Object -ExpandProperty Name",
                ],
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=creation_flags,
            )
            if completed.returncode != 0:
                return []
            return [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        except Exception:
            return []

    @staticmethod
    def get_directshow_camera_device_names() -> list[str]:
        try:
            from pygrabber.dshow_graph import FilterGraph

            devices = FilterGraph().get_input_devices()
            if devices:
                return [str(name) for name in devices]
        except Exception:
            pass

        try:
            import shutil
            import subprocess

            ffmpeg_exe = shutil.which("ffmpeg")
            if ffmpeg_exe:
                creation_flags = 0
                if hasattr(subprocess, "CREATE_NO_WINDOW"):
                    creation_flags = subprocess.CREATE_NO_WINDOW
                completed = subprocess.run(
                    [ffmpeg_exe, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                    capture_output=True,
                    text=True,
                    timeout=12,
                    creationflags=creation_flags,
                )
                output = (completed.stderr or "") + (completed.stdout or "")
                devices: list[str] = []
                for line in output.splitlines():
                    if "(video)" not in line or '"' not in line:
                        continue
                    start = line.find('"') + 1
                    end = line.find('"', start)
                    if end > start:
                        devices.append(line[start:end])
                if devices:
                    return devices
        except Exception:
            pass

        return MainFrame.get_windows_camera_device_names()

    @staticmethod
    def limit_bgr_frame_for_mocap(
            frame,
            *,
            max_edge: int = WINDOW_CAPTURE_MOCAP_MAX_EDGE) -> Optional[numpy.ndarray]:
        """Downscale large window grabs before face detection to cut CPU/RAM churn."""
        frame = MainFrame.normalize_bgr_frame(frame)
        if frame is None:
            return None
        height, width = frame.shape[:2]
        edge = max(height, width)
        if edge <= max_edge:
            return frame
        scale = max_edge / float(edge)
        new_width = max(16, int(round(width * scale)))
        new_height = max(16, int(round(height * scale)))
        return cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)

    @staticmethod
    def normalize_bgr_frame(frame) -> Optional[numpy.ndarray]:
        if frame is None or not hasattr(frame, "size") or frame.size == 0:
            return None
        if len(frame.shape) < 2:
            return None
        if frame.shape[0] < 16 or frame.shape[1] < 16:
            return None
        if frame.dtype != numpy.uint8:
            frame = frame.astype(numpy.uint8)
        if len(frame.shape) == 2:
            return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        if frame.shape[2] == 3:
            return frame
        return None

    @staticmethod
    def is_plausible_camera_frame(frame) -> bool:
        frame = MainFrame.normalize_bgr_frame(frame)
        if frame is None:
            return False
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if float(gray.mean()) < 2.0:
            return False
        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if laplacian_var < 4.0:
            return False
        if laplacian_var > 250000.0:
            return False
        return True

    def apply_camera_capture_settings(self, capture: cv2.VideoCapture) -> None:
        try:
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        fourcc_candidates = ["MJPG", "YUY2", ""]
        resolution_candidates = [(640, 480), (1280, 720), (1280, 960), (1920, 1080)]
        for fourcc_name in fourcc_candidates:
            try:
                if fourcc_name:
                    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc_name))
                for width, height in resolution_candidates:
                    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                    for _ in range(6):
                        ok, frame = capture.read()
                        if ok and self.is_plausible_camera_frame(frame):
                            return
                        time.sleep(0.03)
            except Exception:
                continue

    def read_plausible_camera_frame(self, capture: cv2.VideoCapture, max_attempts: int = 20):
        for _ in range(max_attempts):
            ok, frame = capture.read()
            if ok and self.is_plausible_camera_frame(frame):
                return self.normalize_bgr_frame(frame)
            time.sleep(0.03)
        return None

    def format_window_capture_label(self, title: str) -> str:
        short_title = title.strip() or "Untitled"
        if len(short_title) > 48:
            short_title = short_title[:45] + "..."
        return f"窗口捕获 / Window: {short_title}"

    def get_saved_window_capture(self) -> tuple[Optional[int], str]:
        data = self.persistent_ui_state or {}
        hwnd = int(data.get("window_capture_hwnd") or 0)
        title = str(data.get("window_capture_title") or "").strip()
        if hwnd and window_capture.is_window_valid(hwnd):
            if not title:
                title = window_capture.get_window_title(hwnd)
            return hwnd, title
        return None, ""

    def get_last_window_capture_title(self) -> str:
        data = self.persistent_ui_state or {}
        title = str(data.get("window_capture_title") or "").strip()
        if title:
            return title
        # Fallback to runtime value if present.
        return str(self._window_capture_title or "").strip()

    def prepend_window_capture_choices(self, choices: list[str]) -> None:
        hwnd, title = self.get_saved_window_capture()
        inserted_saved = False
        if hwnd and title:
            label = self.format_window_capture_label(title)
            if label not in self.video_source_choice_map:
                choices.insert(0, label)
                self.video_source_choice_map[label] = ("window", hwnd, title)
                inserted_saved = True

        # Always provide a "pick window" option inside the same source dropdown.
        pick_label = "窗口捕获（选择新窗口） / Window capture (Pick new)"
        if pick_label not in self.video_source_choice_map:
            insert_pos = 1 if inserted_saved else 0
            choices.insert(insert_pos, pick_label)
            self.video_source_choice_map[pick_label] = ("window_pick", None, None)

    def pick_window_capture_interactive(self) -> Optional[tuple[int, str]]:
        targets = window_capture.list_capture_targets()
        if not targets:
            wx.MessageBox(
                "未找到可捕获的窗口。\nNo capturable windows found.",
                "窗口捕获 / Window Capture",
                wx.OK | wx.ICON_WARNING,
                parent=self.get_dialog_parent())
            return None
        labels = [item.title for item in targets]
        dlg = wx.SingleChoiceDialog(
            self.get_dialog_parent(),
            "选择要捕获的窗口（如 DroidCam 预览）。无需置顶，可被其它窗口挡住。\n"
            "Pick a window (e.g. DroidCam preview). Need not stay on top (OBS-style).",
            "窗口捕获 / Window Capture",
            labels)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return None
        index = dlg.GetSelection()
        dlg.Destroy()
        if index < 0 or index >= len(targets):
            return None
        picked = targets[index]
        return picked.hwnd, picked.title

    def probe_camera_backend(self, cam_index: int, backend_api: int, backend_name: str,
                             device_name: Optional[str] = None,
                             full_probe: bool = False) -> Optional[dict[str, object]]:
        capture = None
        try:
            if backend_api:
                capture = cv2.VideoCapture(cam_index, backend_api)
            else:
                capture = cv2.VideoCapture(cam_index)
            if capture is None or not capture.isOpened():
                return None

            if full_probe:
                self.apply_camera_capture_settings(capture)
                readable = self.read_plausible_camera_frame(capture, max_attempts=12) is not None
            else:
                readable = False
                for _ in range(6):
                    ok, frame = capture.read()
                    if ok and self.is_plausible_camera_frame(frame):
                        readable = True
                        break
                    time.sleep(0.03)

            return {
                "index": cam_index,
                "api": backend_api,
                "api_name": backend_name,
                "readable": readable,
                "device_name": device_name or f"Camera {cam_index}",
            }
        except Exception:
            return None
        finally:
            if capture is not None:
                capture.release()

    def enumerate_camera_sources(self) -> list[dict[str, object]]:
        discovered: list[dict[str, object]] = []
        seen_keys: set[tuple[int, str]] = set()
        dshow_names = self.get_directshow_camera_device_names()

        if hasattr(cv2, "CAP_DSHOW"):
            for dshow_index, device_name in enumerate(dshow_names):
                # Special‑case DroidCam: diagnostics show CAP_DSHOW by index can raise
                # an internal exception on some systems, while CAP_MSMF works.
                # Prefer MSMF backend when the device name contains "droidcam".
                backend_api = cv2.CAP_DSHOW
                backend_name = "DSHOW"
                if "droidcam" in str(device_name).lower() and hasattr(cv2, "CAP_MSMF"):
                    backend_api = cv2.CAP_MSMF
                    backend_name = "MSMF"

                device_info = self.probe_camera_backend(
                    dshow_index, backend_api, backend_name, device_name=device_name, full_probe=False)
                if device_info is None:
                    device_info = {
                        "index": dshow_index,
                        "api": backend_api,
                        "api_name": backend_name,
                        "readable": False,
                        "device_name": device_name,
                    }
                key = (int(device_info["index"]), str(device_info["api_name"]))
                if key not in seen_keys:
                    discovered.append(device_info)
                    seen_keys.add(key)

        backend_candidates: list[tuple[str, int]] = []
        if hasattr(cv2, "CAP_MSMF"):
            backend_candidates.append(("MSMF", cv2.CAP_MSMF))
        backend_candidates.append(("ANY", 0))

        for cam_index in range(self.MAX_CAMERA_PROBE_INDEX + 1):
            for backend_index, (backend_name, backend_api) in enumerate(backend_candidates):
                if backend_name == "ANY" and backend_index < len(backend_candidates) - 1:
                    continue
                key = (cam_index, backend_name)
                if key in seen_keys:
                    continue
                device_info = self.probe_camera_backend(cam_index, backend_api, backend_name)
                if device_info is not None:
                    discovered.append(device_info)
                    seen_keys.add(key)
                    break

        return discovered

    def build_camera_source_label(self, device_info: dict[str, object]) -> str:
        label = str(device_info.get("device_name") or f"Camera {device_info['index']}")
        api_name = str(device_info["api_name"])
        if api_name and api_name not in label:
            label = f"{label} [{api_name}]"
        if not bool(device_info["readable"]):
            label = f"{label} [warming up / 预热中]"
        return label

    def connect_default_video_source(self):
        if self.video_source_choice is None or self.video_source_choice.GetCount() == 0:
            return
        for label in self.video_source_choice.GetStrings():
            entry = self.video_source_choice_map.get(label)
            if entry is not None and entry[0] == "window":
                self.video_source_choice.SetStringSelection(label)
                self.on_video_source_choice_changed(wx.CommandEvent())
                return
        for label in self.video_source_choice.GetStrings():
            entry = self.video_source_choice_map.get(label)
            if entry is not None and entry[0] == "camera":
                self.video_source_choice.SetStringSelection(label)
                self.on_video_source_choice_changed(wx.CommandEvent())
                return

    def update_video_source_status_text(self, message: str):
        if self.video_source_status_text is not None:
            self.set_wrapped_static_text_if_changed(self.video_source_status_text, message)

    def update_last_window_capture_text(self):
        if self.last_window_capture_text is None:
            return
        title = self.get_last_window_capture_title()
        if title:
            text = f"上次窗口捕获: {title}\nLast window capture: {title}"
        else:
            text = "上次窗口捕获: 未设置\nLast window capture: (none)"
        self.set_wrapped_static_text_if_changed(self.last_window_capture_text, text)

    def _reset_mediapipe_video_timestamp(self) -> None:
        self._mediapipe_video_timestamp_ms = None
        self._mediapipe_detect_error_logged = False

    def _next_mediapipe_video_timestamp_ms(self, time_now: float) -> int:
        candidate = int(time_now * 1000)
        last = self._mediapipe_video_timestamp_ms
        if last is None:
            next_ts = max(0, candidate)
        else:
            next_ts = max(last + 1, candidate)
        self._mediapipe_video_timestamp_ms = next_ts
        return next_ts

    def release_video_capture(self):
        if getattr(self, "video_capture", None) is not None:
            try:
                self.video_capture.release()
            except Exception:
                pass
        self.video_capture = None
        self.current_video_capture_api = None
        self._reset_mediapipe_video_timestamp()

    def schedule_active_capture_timer(self):
        if hasattr(self, "capture_timer"):
            self.capture_timer.Start(MainFrame.CAPTURE_PROCESS_INTERVAL_MS)

    def schedule_idle_capture_timer(self):
        if hasattr(self, "capture_timer"):
            self.capture_timer.Start(MainFrame.CAPTURE_IDLE_INTERVAL_MS)

    def is_capture_source_active(self) -> bool:
        if self.video_source_kind == "image":
            return bool(self._image_file_path and os.path.isfile(self._image_file_path))
        if self.video_source_kind == "window":
            return (
                self._window_capture_hwnd is not None
                and window_capture.is_window_valid(self._window_capture_hwnd))
        return self.video_capture is not None and self.video_capture.isOpened()

    def is_capture_preview_visible(self) -> bool:
        if not self.full_controls_expanded:
            return False
        if self.controls_frame is None or not self.controls_frame.IsShown():
            return False
        return hasattr(self, "webcam_capture_panel")

    def is_webcam_popup_visible(self) -> bool:
        return self.webcam_preview_popup_frame is not None and self.webcam_preview_popup_frame.IsShown()

    def should_mirror_capture_preview(self) -> bool:
        return self.video_source_kind == "camera"

    def is_acceptable_capture_frame(self, frame) -> bool:
        normalized = self.normalize_bgr_frame(frame)
        if normalized is None:
            return False
        if self.video_source_kind in ("file", "image", "window"):
            return True
        return self.is_plausible_camera_frame(normalized)

    def read_capture_frame_bgr(self):
        if self.video_source_kind == "window":
            if self._window_capture_hwnd is None:
                return None
            # PrintWindow/BitBlt window grabs can block for a long time when the
            # target window is busy/hardware-accelerated, which would freeze the
            # wx UI if done here (this runs on the UI-thread capture timer).
            # Do the grab on a background worker (latest-wins) and only read the
            # most recent frame so a stalled grab never blocks the UI.
            self._ensure_window_capture_worker()
            with self._window_capture_lock:
                frame = self._window_capture_latest_frame
                if frame is None:
                    return None
                return frame.copy()

        if self.video_source_kind == "image":
            if not self._image_file_path:
                return None
            return self.normalize_bgr_frame(cv2.imread(self._image_file_path))

        if self.video_capture is None or not self.video_capture.isOpened():
            return None

        ok, frame = self.video_capture.read()
        if not ok and self.video_source_kind == "file":
            try:
                self.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            except Exception:
                pass
            ok, frame = self.video_capture.read()
        if not ok:
            return None
        return self.normalize_bgr_frame(frame)

    def open_video_file_capture(self, file_path: str) -> Optional[cv2.VideoCapture]:
        open_attempts: list[int] = []
        if hasattr(cv2, "CAP_FFMPEG"):
            open_attempts.append(cv2.CAP_FFMPEG)
        open_attempts.append(0)

        for backend_api in open_attempts:
            capture = None
            try:
                if backend_api:
                    capture = cv2.VideoCapture(file_path, backend_api)
                else:
                    capture = cv2.VideoCapture(file_path)
                if capture is None or not capture.isOpened():
                    continue
                ok, frame = capture.read()
                if ok and self.normalize_bgr_frame(frame) is not None:
                    try:
                        capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    except Exception:
                        pass
                    return capture
                capture.release()
            except Exception:
                if capture is not None:
                    capture.release()
        return None

    def should_update_capture_preview_ui(self, time_now: float) -> bool:
        if not self.is_capture_preview_visible() and not self.is_webcam_popup_visible():
            return False
        return (time_now - self._last_preview_ui_time) >= (MainFrame.CAPTURE_PREVIEW_INTERVAL_MS / 1000.0)

    def should_process_mediapipe(self, time_now: float) -> bool:
        if not self.is_capture_source_active():
            return False
        interval_ms = MainFrame.MEDIAPIPE_MIN_INTERVAL_MS
        if self.video_source_kind == "window":
            interval_ms = max(interval_ms, MainFrame.WINDOW_CAPTURE_MEDIAPIPE_INTERVAL_MS)
        if not self.full_controls_expanded:
            interval_ms = max(interval_ms, 66)
        return (time_now - self._last_mediapipe_process_time) >= (interval_ms / 1000.0)

    @classmethod
    def fill_bitmap_solid(cls, bitmap: wx.Bitmap, colour: wx.Colour) -> None:
        if not bitmap.IsOk():
            return
        dc = wx.MemoryDC()
        dc.SelectObject(bitmap)
        dc.SetBackground(wx.Brush(colour))
        dc.Clear()
        del dc

    def refresh_preview_placeholders(self) -> None:
        if hasattr(self, "source_image_bitmap"):
            self._invalidate_source_preview_cache()
            self.update_source_image_bitmap(force=True)
        if hasattr(self, "webcam_capture_bitmap"):
            MainFrame.fill_bitmap_solid(self.webcam_capture_bitmap, MainFrame.PREVIEW_IDLE_BACKGROUND)
            if hasattr(self, "webcam_capture_panel"):
                self.webcam_capture_panel.Refresh(False)

    def draw_capture_status_message(self, message: str):
        if not self.is_capture_preview_visible():
            return
        MainFrame.fill_bitmap_solid(self.webcam_capture_bitmap, MainFrame.PREVIEW_IDLE_BACKGROUND)
        if hasattr(self, "webcam_capture_panel"):
            self.webcam_capture_panel.Refresh(False)

    def _webcam_preview_target_size(self) -> wx.Size:
        panel = getattr(self, "webcam_capture_panel", None)
        if panel is not None:
            client = panel.GetClientSize()
            if client.x > 0 and client.y > 0:
                side = min(client.x, client.y)
                return wx.Size(side, side)
        return wx.Size(MainFrame.WEBCAM_PREVIEW_SIZE, MainFrame.WEBCAM_PREVIEW_SIZE)

    def _ensure_webcam_capture_bitmap_size(self) -> int:
        target = self._webcam_preview_target_size()
        side = max(1, target.x)
        if (
                not getattr(self, "webcam_capture_bitmap", None)
                or not self.webcam_capture_bitmap.IsOk()
                or self.webcam_capture_bitmap.GetWidth() != side
                or self.webcam_capture_bitmap.GetHeight() != side):
            self.webcam_capture_bitmap = wx.Bitmap(side, side)
            MainFrame.fill_bitmap_solid(self.webcam_capture_bitmap, MainFrame.PREVIEW_IDLE_BACKGROUND)
        return side

    def update_capture_preview_bitmap(self, bgr_frame):
        preview_side = self._ensure_webcam_capture_bitmap_size()
        wx_bitmap = self.bgr_frame_to_preview_bitmap(
            bgr_frame,
            preview_side,
            preview_side,
            mirror=self.should_mirror_capture_preview())
        if wx_bitmap.IsOk():
            MainFrame.fill_bitmap_solid(self.webcam_capture_bitmap, MainFrame.PREVIEW_IDLE_BACKGROUND)
            dc = wx.MemoryDC()
            dc.SelectObject(self.webcam_capture_bitmap)
            dc.DrawBitmap(wx_bitmap, 0, 0, True)
            del dc

        if self.is_webcam_popup_visible():
            self.webcam_preview_popup_frame.preview_panel.Refresh(False)
        elif self.is_capture_preview_visible() and hasattr(self, "webcam_capture_panel"):
            self.webcam_capture_panel.Refresh(False)

    def refresh_video_source_choice_async(self, connect_after: bool = False, trigger_source: str = "manual"):
        refresh_start = time.time()
        if self._video_enumeration_in_progress:
            return
        normalized_trigger = "auto" if str(trigger_source).lower() == "auto" else "manual"
        self._video_enumeration_in_progress = True
        if normalized_trigger == "auto":
            self.update_video_source_status_text("自动加载视频源中... / Auto loading video sources...")
        else:
            self.update_video_source_status_text("手动刷新视频源中... / Manual refresh in progress...")

        def worker():
            discovered = self.enumerate_camera_sources()
            wx.CallAfter(self._apply_video_source_choices, discovered, connect_after, normalized_trigger)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_video_source_choices(self,
                                    discovered_cameras: list[dict[str, object]],
                                    connect_after: bool,
                                    trigger_source: str = "manual"):
        self._video_enumeration_in_progress = False
        if self.video_source_choice is None:
            return

        previous_selection = self.video_source_choice.GetStringSelection()
        self.video_source_choice_map.clear()
        choices: list[str] = []

        for device_info in discovered_cameras:
            label = self.build_camera_source_label(device_info)
            if label in self.video_source_choice_map:
                label = f"{label} #{int(device_info['index'])}"
            choices.append(label)
            self.video_source_choice_map[label] = (
                "camera",
                int(device_info["index"]),
                int(device_info["api"]),
            )

        if not choices:
            fallback_label = "Camera 0 (fallback)"
            choices.append(fallback_label)
            self.video_source_choice_map[fallback_label] = (
                "camera", 0, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0)

        choices.append("Video file... / 视频文件...")
        self.video_source_choice_map["Video file... / 视频文件..."] = ("file", None, None)
        self.prepend_window_capture_choices(choices)

        self.video_source_choice.SetItems(choices)
        if previous_selection in choices:
            self.video_source_choice.SetStringSelection(previous_selection)
        elif self.video_source_choice.GetCount() > 0:
            self.video_source_choice.SetSelection(0)

        self.update_video_source_status_text(
            f"发现 {max(0, len(choices) - 1)} 个视频源（含窗口捕获入口）"
            f" / Found {max(0, len(choices) - 1)} sources")
        self.update_last_window_capture_text()

        if connect_after:
            if trigger_source == "auto":
                self.update_video_source_status_text("自动连接视频源中... / Auto connecting source...")
            else:
                self.update_video_source_status_text("正在连接首个可用视频源... / Connecting first available source...")
            self.connect_default_video_source()

    def refresh_video_source_choice(self):
        self.refresh_video_source_choice_async(connect_after=False, trigger_source="manual")

    def on_refresh_video_sources_clicked(self, event: wx.Event):
        self.refresh_video_source_choice_async(connect_after=True, trigger_source="manual")

    def on_pick_window_capture_clicked(self, event: wx.Event):
        picked = self.pick_window_capture_interactive()
        if picked is None:
            return
        hwnd, title = picked
        self.set_video_capture_window(hwnd, title)
        self.refresh_video_source_choice_async(connect_after=False, trigger_source="manual")
        picked_label = self.format_window_capture_label(title)

        def _select_saved_window():
            if self.video_source_choice is None:
                return
            if picked_label in self.video_source_choice_map:
                self.video_source_choice.SetStringSelection(picked_label)

        wx.CallAfter(_select_saved_window)
        self.update_capture_panel(None)

    def refresh_and_autoload_video_source(self):
        """Refresh source list and auto-select first available source."""
        self.refresh_video_source_choice_async(connect_after=True, trigger_source="manual")

    def on_video_source_choice_changed(self, event: wx.Event):
        if self.video_source_choice is None:
            return
        label = self.video_source_choice.GetStringSelection()
        source_entry = self.video_source_choice_map.get(label)
        if source_entry is None:
            return
        kind, value, source_api = source_entry
        if kind == "window_pick":
            picked = self.pick_window_capture_interactive()
            if picked is None:
                return
            hwnd, title = picked
            self.set_video_capture_window(hwnd, title)
            # Rebuild dropdown so saved-window label shows up.
            self.refresh_video_source_choice_async(connect_after=False, trigger_source="manual")
            picked_label = self.format_window_capture_label(title)
            def _select_saved_window():
                if self.video_source_choice is None:
                    return
                if picked_label in self.video_source_choice_map:
                    self.video_source_choice.SetStringSelection(picked_label)
            wx.CallAfter(_select_saved_window)
            self.update_capture_panel(None)
            return

        if kind == "window":
            self.set_video_capture_window(int(value), str(source_api or ""))
            self.update_capture_panel(None)
            return

        if kind == "camera":
            api_preference = int(source_api) if source_api is not None else None
            self.set_video_capture_camera(int(value), api_preference)
            self.update_capture_panel(None)
            return

        if kind == "file":
            dlg = wx.FileDialog(
                self.get_dialog_parent(),
                "选择视频或图片 / Choose Video or Image",
                wildcard=MainFrame.VIDEO_FILE_WILDCARD,
                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
            )
            if dlg.ShowModal() != wx.ID_OK:
                dlg.Destroy()
                return
            path = dlg.GetPath()
            dlg.Destroy()
            self.set_video_capture_file(path)
            self.update_capture_panel(None)

    def set_video_capture_camera(self,
                                 cam_index: int,
                                 api_preference: Optional[int] = None):
        self.release_video_capture()
        self.video_source_kind = "camera"
        self._image_file_path = None
        self._last_good_webcam_bgr_frame = None
        self._window_invalid_autoswitch_attempted = False

        open_attempts: list[int] = []
        if api_preference is not None:
            open_attempts.append(api_preference)
        if hasattr(cv2, "CAP_DSHOW") and cv2.CAP_DSHOW not in open_attempts:
            open_attempts.append(cv2.CAP_DSHOW)
        if hasattr(cv2, "CAP_MSMF") and cv2.CAP_MSMF not in open_attempts:
            open_attempts.append(cv2.CAP_MSMF)
        open_attempts.append(0)

        last_error_message = None
        for backend_api in open_attempts:
            capture = None
            try:
                if backend_api:
                    capture = cv2.VideoCapture(cam_index, backend_api)
                else:
                    capture = cv2.VideoCapture(cam_index)
                if capture is None or not capture.isOpened():
                    continue

                self.apply_camera_capture_settings(capture)
                warmup_frame = self.read_plausible_camera_frame(capture, max_attempts=12)
                if warmup_frame is not None:
                    self.video_capture = capture
                    self.current_video_capture_api = backend_api
                    self.video_capture_status_message = None
                    self._last_good_webcam_bgr_frame = warmup_frame
                    self.update_video_source_status_text(
                        f"已连接 / Connected: index {cam_index}, api {backend_api}")
                    self.schedule_active_capture_timer()
                    self.save_persistent_ui_state()
                    self.update_last_window_capture_text()
                    return

                capture.release()
                last_error_message = (
                    f"Camera {cam_index} opened but no valid frame / 摄像头 {cam_index} 已打开但画面无效")
            except Exception as exc:
                last_error_message = str(exc)
                if capture is not None:
                    capture.release()

        self.video_capture = None
        self.current_video_capture_api = None
        self.video_source_kind = "none"
        self.video_capture_status_message = last_error_message or (
            f"Camera {cam_index} not readable / 摄像头 {cam_index} 无法读取")
        self.update_video_source_status_text(self.video_capture_status_message)
        self.schedule_idle_capture_timer()

    def set_video_capture_window(self, hwnd: int, title: str):
        previous_hwnd = self._window_capture_hwnd
        self.release_video_capture()
        self._image_file_path = None
        if previous_hwnd is not None:
            window_capture.invalidate_capture_method_cache(previous_hwnd)
        self._window_capture_hwnd = int(hwnd)
        self._window_capture_title = title.strip() or window_capture.get_window_title(int(hwnd))
        window_capture.invalidate_capture_method_cache(self._window_capture_hwnd)
        self._last_good_webcam_bgr_frame = None
        self._window_invalid_autoswitch_attempted = False
        self._last_mediapipe_capture_serial = -1
        self.persistent_ui_state["window_capture_hwnd"] = self._window_capture_hwnd
        self.persistent_ui_state["window_capture_title"] = self._window_capture_title
        self.save_persistent_ui_state()
        self.update_last_window_capture_text()

        if not window_capture.is_window_valid(self._window_capture_hwnd):
            self.video_source_kind = "none"
            self.video_capture_status_message = (
                "窗口无效或已关闭 / Window is not available")
            self.update_video_source_status_text(self.video_capture_status_message)
            self.schedule_idle_capture_timer()
            return

        self.video_source_kind = "window"
        warmup_frame = window_capture.capture_window_client_bgr(self._window_capture_hwnd)
        if warmup_frame is not None:
            self._last_good_webcam_bgr_frame = warmup_frame
        self.video_capture_status_message = None
        self.update_video_source_status_text(
            f"窗口捕获 / Window: {self._window_capture_title}")
        self.schedule_active_capture_timer()
        wx.CallAfter(self.update_capture_panel, None)

    def set_video_capture_file(self, file_path: str):
        try:
            self.release_video_capture()
            self._last_good_webcam_bgr_frame = None
            self._window_invalid_autoswitch_attempted = False
            file_ext = os.path.splitext(file_path)[1].lower()

            if file_ext in MainFrame.IMAGE_FILE_EXTENSIONS:
                image_frame = self.normalize_bgr_frame(cv2.imread(file_path))
                if image_frame is None:
                    self.video_source_kind = "none"
                    self.video_capture_status_message = f"无法读取图片 / Cannot read image: {file_path}"
                    self.update_video_source_status_text(self.video_capture_status_message)
                    self.schedule_idle_capture_timer()
                    return
                self.video_source_kind = "image"
                self._image_file_path = file_path
                self.video_capture_status_message = None
                self._last_good_webcam_bgr_frame = image_frame
                self.update_video_source_status_text(
                    f"已加载图片 / Loaded image: {os.path.basename(file_path)}")
                self.schedule_active_capture_timer()
                return

            capture = self.open_video_file_capture(file_path)
            if capture is None:
                self.video_source_kind = "none"
                self.video_capture_status_message = f"无法读取视频 / Cannot read video: {file_path}"
                self.update_video_source_status_text(self.video_capture_status_message)
                self.schedule_idle_capture_timer()
                return

            self.video_source_kind = "file"
            self._image_file_path = None
            self.video_capture = capture
            self.current_video_capture_api = None
            self.video_capture_status_message = None
            self.update_video_source_status_text(
                f"已加载视频 / Loaded video: {os.path.basename(file_path)}")
            self.schedule_active_capture_timer()
        except Exception as exc:
            self.video_source_kind = "none"
            self.video_capture_status_message = f"Video source error: {exc}"
            self.update_video_source_status_text(self.video_capture_status_message)
            self.schedule_idle_capture_timer()

    def bgr_frame_to_preview_bitmap(self,
                                    bgr_frame,
                                    preview_width: int,
                                    preview_height: int,
                                    mirror: bool = True) -> wx.Bitmap:
        """Scale frame to fit inside preview box; letterbox with black when aspect differs."""
        bgr_frame = self.normalize_bgr_frame(bgr_frame)
        if bgr_frame is None:
            return self.webcam_capture_bitmap

        preview_width = max(1, int(preview_width))
        preview_height = max(1, int(preview_height))
        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        if mirror:
            rgb_frame = cv2.flip(rgb_frame, 1)
        frame_h, frame_w = rgb_frame.shape[:2]
        if frame_w <= 0 or frame_h <= 0:
            return self.webcam_capture_bitmap

        scale = min(preview_width / frame_w, preview_height / frame_h)
        scaled_w = max(1, int(round(frame_w * scale)))
        scaled_h = max(1, int(round(frame_h * scale)))
        resized_frame = cv2.resize(
            rgb_frame,
            (scaled_w, scaled_h),
            interpolation=cv2.INTER_AREA)
        if scaled_w == preview_width and scaled_h == preview_height:
            output_frame = resized_frame
        else:
            output_frame = numpy.zeros((preview_height, preview_width, 3), dtype=numpy.uint8)
            offset_x = (preview_width - scaled_w) // 2
            offset_y = (preview_height - scaled_h) // 2
            output_frame[offset_y:offset_y + scaled_h, offset_x:offset_x + scaled_w] = resized_frame
        output_frame = numpy.ascontiguousarray(output_frame, dtype=numpy.uint8)
        wx_image = wx.Image(preview_width, preview_height)
        wx_image.SetData(output_frame.tobytes())
        return wx_image.ConvertToBitmap()

    def create_postprocess_panel(self, parent):
        self.postprocess_panel = wx.Panel(parent, style=wx.SIMPLE_BORDER)
        self.postprocess_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.postprocess_panel.SetSizer(self.postprocess_panel_sizer)
        self.postprocess_panel.SetAutoLayout(1)
        self.postprocess_panel.SetDoubleBuffered(True)

        output_background_hex = self.get_output_background_hex()
        output_background_mode = self.get_output_background_mode()
        if not self.get_output_background_image_path():
            self.set_output_background_image_path(self.get_bundled_transparent_background_path())
        output_background_image_path = self.get_output_background_image_path()
        layer_blend_enabled = self.is_layer_blend_enabled()
        layer_hotkeys_enabled = bool(self._layer_hotkeys_enabled_state.GetValue())
        character_edge_mode = normalize_character_edge_mode(
            str(self.persistent_ui_state.get("character_edge_mode", CHARACTER_EDGE_NONE)))
        try:
            character_edge_width = clamp_character_edge_width(
                float(self.persistent_ui_state.get(
                    "character_edge_width", CHARACTER_EDGE_WIDTH_DEFAULT)))
        except (TypeError, ValueError):
            character_edge_width = CHARACTER_EDGE_WIDTH_DEFAULT
        character_edge_color_hex = self.normalize_background_hex(
            str(self.persistent_ui_state.get("character_edge_color_hex") or "#FFFFFF"),
            "#FFFFFF")
        layer_force_full_follow = bool(self.persistent_ui_state.get("layer_force_full_follow", False))
        self._layer_force_full_follow_state.SetValue(layer_force_full_follow)
        antialias_strength = self.antialias_strength_spin.GetValue()
        output_frame_interpolation = self.get_output_frame_interpolation_multiplier()
        try:
            mouth_infer_cap_hz = int(self.persistent_ui_state.get(
                "mouth_infer_cap_hz", MOUTH_INFER_CAP_HZ_DEFAULT))
        except (TypeError, ValueError):
            mouth_infer_cap_hz = MOUTH_INFER_CAP_HZ_DEFAULT
        if mouth_infer_cap_hz not in MOUTH_INFER_CAP_HZ_VALUES:
            mouth_infer_cap_hz = MOUTH_INFER_CAP_HZ_DEFAULT
        smooth_affine_30hz = bool(self.persistent_ui_state.get("smooth_affine_30hz", True))
        nn_super_resolution_mode = normalize_sr_mode(
            self.persistent_ui_state.get("nn_super_resolution_mode", NN_SR_OFF))
        nn_frame_interpolation = normalize_nn_frame_multiplier(
            self.persistent_ui_state.get("nn_frame_interpolation_multiplier", NN_FRAME_INTERP_OFF))
        nn_infer_backend = normalize_infer_backend(
            self.persistent_ui_state.get("nn_infer_backend", INFER_BACKEND_PYTORCH))
        tha_infer_fp16_raw = self.persistent_ui_state.get("tha_infer_fp16", "full")
        tha_infer_fp16_index = 1 if normalize_tha_infer_fp16(tha_infer_fp16_raw) else 0

        postprocess_text = wx.StaticText(
            self.postprocess_panel, label="--- 后处理和其他 / Postprocess & Other (D 下) ---", style=wx.ALIGN_CENTER)
        self.postprocess_panel_sizer.Add(postprocess_text, 0, wx.EXPAND)

        self.tha3_variant_panel = wx.Panel(self.postprocess_panel)
        tha3_variant_sizer = wx.BoxSizer(wx.VERTICAL)
        self.tha3_variant_panel.SetSizer(tha3_variant_sizer)
        self.tha3_variant_panel.SetAutoLayout(1)

        self.tha3_model_variant_label = wx.StaticText(
            self.tha3_variant_panel, label="THA3 模型变体 / THA3 Model Variant")
        tha3_variant_sizer.Add(
            self.tha3_model_variant_label,
            0, wx.EXPAND | wx.BOTTOM, 2)

        variant_labels = [label for _, label in THA3_VARIANT_CHOICES]
        variant_index = 0
        for index, (variant_id, _) in enumerate(THA3_VARIANT_CHOICES):
            if variant_id == self.tha3_model_variant:
                variant_index = index
                break
        self.tha3_model_variant_choice = wx.Choice(
            self.tha3_variant_panel, choices=variant_labels)
        self.tha3_model_variant_choice.SetSelection(variant_index)
        self.tha3_model_variant_choice.Bind(wx.EVT_CHOICE, self.on_tha3_model_variant_changed)
        tha3_variant_sizer.Add(
            self.tha3_model_variant_choice,
            0, wx.EXPAND)

        self.postprocess_panel_sizer.Add(
            self.tha3_variant_panel,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        background_label = wx.StaticText(self.postprocess_panel, label="背景 / Background")
        self.postprocess_panel_sizer.Add(background_label, wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        try:
            mode_index = OUTPUT_BACKGROUND_MODE_VALUES.index(output_background_mode)
        except ValueError:
            mode_index = 0
        self.output_background_mode_choice = wx.Choice(
            self.postprocess_panel,
            choices=list(OUTPUT_BACKGROUND_MODE_LABELS))
        self.output_background_mode_choice.SetSelection(mode_index)
        self.output_background_mode_choice.Bind(wx.EVT_CHOICE, self.on_output_background_mode_changed)
        self.postprocess_panel_sizer.Add(
            self.output_background_mode_choice,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT, 4))

        self.output_background_choice = wx.ColourPickerCtrl(
            self.postprocess_panel,
            colour=wx.Colour(output_background_hex))
        self.output_background_choice.Bind(wx.EVT_COLOURPICKER_CHANGED, self.on_output_background_changed)
        self.postprocess_panel_sizer.Add(
            self.output_background_choice,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        self.output_background_image_panel = wx.Panel(self.postprocess_panel)
        output_background_image_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.output_background_image_browse_button = wx.Button(
            self.output_background_image_panel,
            label="选择图片 / Browse Image...")
        self.output_background_image_browse_button.Bind(
            wx.EVT_BUTTON, self.on_output_background_image_browse)
        output_background_image_sizer.Add(
            self.output_background_image_browse_button, 0, wx.RIGHT, 6)
        self.output_background_image_path_text = wx.StaticText(
            self.output_background_image_panel,
            label=self.format_output_background_image_path_label(output_background_image_path))
        output_background_image_sizer.Add(
            self.output_background_image_path_text, 1, wx.EXPAND)
        self.output_background_image_panel.SetSizer(output_background_image_sizer)
        self.postprocess_panel_sizer.Add(
            self.output_background_image_panel,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))
        self.output_background_image_path_state.SetValue(output_background_image_path)
        self.update_output_background_controls_visibility()

        self.output_obs_capture_hint = wx.StaticText(
            self.postprocess_panel,
            label=(
                "黑键：窗口捕获→「THA4 Output / 输出」→ 颜色键控 #000000 "
                "(相似度约400、平滑约80) / Color Key: window capture + chroma key black"))
        self.postprocess_panel_sizer.Add(
            self.output_obs_capture_hint,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4).Expand())

        self.output_transparent_capture_hint = wx.StaticText(
            self.postprocess_panel,
            label=(
                "透明：桌面真透由叠加层显示，OBS 用 WGC/游戏捕获勾「允许透明」；"
                "不保 alpha 的工具(传统窗口捕获/部分直播助手)请改用「黑键」；按住窗口拖动可移动位置 / "
                "Transparent: true per-pixel alpha overlay; use OBS WGC capture with transparency"))
        self.postprocess_panel_sizer.Add(
            self.output_transparent_capture_hint,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4).Expand())

        character_edge_mode_index = 0
        if character_edge_mode in CHARACTER_EDGE_MODE_VALUES:
            character_edge_mode_index = CHARACTER_EDGE_MODE_VALUES.index(character_edge_mode)
        edge_mode_row = wx.BoxSizer(wx.HORIZONTAL)
        edge_mode_row.Add(
            wx.StaticText(self.postprocess_panel, label="角色边缘 / Character edge"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            6)
        self.character_edge_mode_choice = wx.Choice(
            self.postprocess_panel,
            choices=list(CHARACTER_EDGE_MODE_LABELS))
        self.character_edge_mode_choice.SetSelection(character_edge_mode_index)
        self.character_edge_mode_choice.Bind(wx.EVT_CHOICE, self.on_character_edge_setting_changed)
        edge_mode_row.Add(self.character_edge_mode_choice, 1, wx.EXPAND)
        self.postprocess_panel_sizer.Add(
            edge_mode_row,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4).Expand())

        self.character_edge_style_panel = wx.Panel(self.postprocess_panel)
        edge_style_sizer = wx.BoxSizer(wx.VERTICAL)
        self.character_edge_style_panel.SetSizer(edge_style_sizer)

        self.character_edge_width_row_panel = wx.Panel(self.character_edge_style_panel)
        width_row = wx.BoxSizer(wx.HORIZONTAL)
        self.character_edge_width_row_panel.SetSizer(width_row)
        width_row.Add(
            wx.StaticText(self.character_edge_width_row_panel, label="粗细 / Width"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            6)
        self.character_edge_width_spin = wx.SpinCtrlDouble(
            self.character_edge_width_row_panel,
            min=CHARACTER_EDGE_WIDTH_MIN,
            max=CHARACTER_EDGE_WIDTH_MAX,
            initial=float(character_edge_width),
            inc=CHARACTER_EDGE_WIDTH_INCREMENT,
            style=wx.SP_ARROW_KEYS)
        self.character_edge_width_spin.SetDigits(3)
        self.character_edge_width_spin.Bind(
            wx.EVT_SPINCTRLDOUBLE, self.on_character_edge_setting_changed)
        self.character_edge_width_spin.Bind(
            wx.EVT_TEXT, self.on_character_edge_setting_changed)
        width_row.Add(self.character_edge_width_spin, 0, wx.ALIGN_CENTER_VERTICAL)
        edge_style_sizer.Add(
            self.character_edge_width_row_panel,
            0,
            wx.EXPAND | wx.TOP,
            2)

        self.character_edge_colour_row_panel = wx.Panel(self.character_edge_style_panel)
        colour_row = wx.BoxSizer(wx.HORIZONTAL)
        self.character_edge_colour_row_panel.SetSizer(colour_row)
        colour_row.Add(
            wx.StaticText(self.character_edge_colour_row_panel, label="颜色 / Color"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            6)
        self.character_edge_colour_picker = wx.ColourPickerCtrl(
            self.character_edge_colour_row_panel,
            colour=wx.Colour(character_edge_color_hex))
        self.character_edge_colour_picker.Bind(wx.EVT_COLOURPICKER_CHANGED, self.on_character_edge_setting_changed)
        colour_row.Add(self.character_edge_colour_picker, 0, wx.ALIGN_CENTER_VERTICAL)
        edge_style_sizer.Add(
            self.character_edge_colour_row_panel,
            0,
            wx.EXPAND | wx.TOP,
            2)

        self.character_edge_hint_text = wx.StaticText(
            self.character_edge_style_panel,
            label=(
                "消闪：按当前背景稳定半透明边缘；描边：在角色外轮廓加描边。"
                " 粗细步进 0.001（三位小数）。"
                " / Stabilize fringe or add outline; width step 0.001 (3 decimals)."))
        edge_style_sizer.Add(
            self.character_edge_hint_text,
            0,
            wx.EXPAND | wx.TOP,
            4)
        self.postprocess_panel_sizer.Add(
            self.character_edge_style_panel,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4).Expand())

        self.layer_blend_enabled_checkbox = wx.CheckBox(
            self.postprocess_panel,
            label="启用图层混合 / Enable Layer Blending")
        self.layer_blend_enabled_checkbox.SetValue(layer_blend_enabled)
        self._layer_blend_enabled_state.SetValue(layer_blend_enabled)
        self.layer_blend_enabled_checkbox.Bind(wx.EVT_CHECKBOX, self.on_layer_blend_changed)
        self.postprocess_panel_sizer.Add(
            self.layer_blend_enabled_checkbox,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.layer_hotkeys_enabled_checkbox = wx.CheckBox(
            self.postprocess_panel,
            label="启用图层快捷键 / Enable Layer Hotkeys")
        self.layer_hotkeys_enabled_checkbox.SetValue(layer_hotkeys_enabled)
        self.layer_hotkeys_enabled_checkbox.SetToolTip(
            "默认关闭。勾选后才注册全局热键（显隐/GIF/按住显隐）；需先启用图层混合。"
            " / Off by default. Registers global hotkeys when enabled; requires layer blending.")
        self.layer_hotkeys_enabled_checkbox.Enable(layer_blend_enabled)
        self.layer_hotkeys_enabled_checkbox.Bind(
            wx.EVT_CHECKBOX, self.on_layer_hotkeys_changed)
        self.postprocess_panel_sizer.Add(
            self.layer_hotkeys_enabled_checkbox,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT, 4))

        self.layer_blend_status_text = wx.StaticText(
            self.postprocess_panel,
            label="",
            style=wx.ALIGN_LEFT)
        self.postprocess_panel_sizer.Add(
            self.layer_blend_status_text,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT, 4).Expand())

        self.open_basic_layer_window_button = wx.Button(
            self.postprocess_panel,
            label="打开图层窗 / Open Layer Editor")
        self.open_basic_layer_window_button.Bind(
            wx.EVT_BUTTON, self.on_open_basic_layer_window_clicked)
        self.postprocess_panel_sizer.Add(
            self.open_basic_layer_window_button,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4).Expand())

        self.layer_force_full_follow_checkbox = wx.CheckBox(
            self.postprocess_panel,
            label="图层强制百分百跟随 / Force Layer 100% Follow")
        self.layer_force_full_follow_checkbox.SetValue(layer_force_full_follow)
        self._layer_force_full_follow_state.SetValue(layer_force_full_follow)
        self.layer_force_full_follow_checkbox.SetToolTip(
            "跳过图层绑定平滑，每帧百分百跟姿态；动作到输出延迟更大、更跟手但易抖。"
            " / Skip layer bind smoothing for instant follow; higher motion-to-output lag, tighter but jittery")
        self.layer_force_full_follow_checkbox.Bind(
            wx.EVT_CHECKBOX, self.on_layer_force_full_follow_changed)
        self.postprocess_panel_sizer.Add(
            self.layer_force_full_follow_checkbox,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        layer_force_full_follow_hint = wx.StaticText(
            self.postprocess_panel,
            label=(
                "关 = 尊重各图层「平滑跟随」；开 = 全局无延迟绑定（覆盖图层内平滑开关）。"
                " / Off respects per-layer smooth; on forces instant bind globally"))
        self.postprocess_panel_sizer.Add(
            layer_force_full_follow_hint,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        postprocess_control_panel = wx.Panel(self.postprocess_panel)
        postprocess_control_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        postprocess_control_panel.SetSizer(postprocess_control_panel_sizer)
        postprocess_control_panel.SetAutoLayout(1)
        self.postprocess_panel_sizer.Add(
            postprocess_control_panel,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.antialias_strength_spin = self.create_display_transform_slider_control(
            postprocess_control_panel,
            postprocess_control_panel_sizer,
            slider_label("抗锯齿强度", "Anti-Aliasing", "渲染倍率", "render scale"),
            antialias_strength,
            1.0,
            4.0,
            0.25,
            slider_min=1.0,
            slider_max=4.0)

        antialias_hint = wx.StaticText(
            self.postprocess_panel,
            label="1.00 = 关闭 / off；更大更平滑但更耗性能 / higher = smoother, heavier")
        self.postprocess_panel_sizer.Add(
            antialias_hint,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        mouth_infer_cap_label = wx.StaticText(
            self.postprocess_panel,
            label="GPU 推理上限 / GPU Infer Cap")
        self.postprocess_panel_sizer.Add(
            mouth_infer_cap_label,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))
        try:
            mouth_infer_cap_index = MOUTH_INFER_CAP_HZ_VALUES.index(mouth_infer_cap_hz)
        except ValueError:
            mouth_infer_cap_index = 0
        self.mouth_infer_cap_choice = wx.Choice(
            self.postprocess_panel,
            choices=list(MOUTH_INFER_CAP_HZ_LABELS))
        self.mouth_infer_cap_choice.SetSelection(mouth_infer_cap_index)
        self.mouth_infer_cap_choice.Bind(wx.EVT_CHOICE, self.on_mouth_infer_cap_changed)
        self.postprocess_panel_sizer.Add(
            self.mouth_infer_cap_choice,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        mouth_infer_cap_hint = wx.StaticText(
            self.postprocess_panel,
            label="节流全部 GPU 推理（含大动作）；显示 ~30Hz 用 cached 帧 / throttles all infer; display uses cached")
        self.postprocess_panel_sizer.Add(
            mouth_infer_cap_hint,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        self.smooth_affine_30hz_checkbox = wx.CheckBox(
            self.postprocess_panel,
            label="平滑位移 30Hz / Smooth Motion 30Hz")
        self.smooth_affine_30hz_checkbox.SetValue(smooth_affine_30hz)
        self.smooth_affine_30hz_checkbox.Bind(wx.EVT_CHECKBOX, self.on_smooth_affine_30hz_changed)
        self.postprocess_panel_sizer.Add(
            self.smooth_affine_30hz_checkbox,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        smooth_affine_hint = wx.StaticText(
            self.postprocess_panel,
            label="开 = 动态增强 ~30Hz 重绘（默认，更顺）/ on = smooth pan & scale; "
                  "关 = 跟 GPU 推理上限（省 CPU）/ off follows infer cap")
        self.postprocess_panel_sizer.Add(
            smooth_affine_hint,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        frame_interp_label = wx.StaticText(
            self.postprocess_panel,
            label="插帧 / Frame Interpolation")
        self.postprocess_panel_sizer.Add(
            frame_interp_label,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        try:
            frame_interp_index = POSE_FRAME_INTERP_VALUES.index(output_frame_interpolation)
        except ValueError:
            frame_interp_index = 0
        self.output_frame_interpolation_choice = wx.Choice(
            self.postprocess_panel,
            choices=list(POSE_FRAME_INTERP_LABELS))
        self.output_frame_interpolation_choice.SetSelection(frame_interp_index)
        self.output_frame_interpolation_choice.Bind(
            wx.EVT_CHOICE, self.on_output_frame_interpolation_changed)
        self.postprocess_panel_sizer.Add(
            self.output_frame_interpolation_choice,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        frame_interp_hint = wx.StaticText(
            self.postprocess_panel,
            label="×N = GPU 推理 ×N（pose 中点 infer，上限 30Hz）；无像素混合 / multiplies pose infer, no RGB blend")
        self.postprocess_panel_sizer.Add(
            frame_interp_hint,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        nn_sr_label = wx.StaticText(
            self.postprocess_panel,
            label="超分 (NN) / SuperResolution (NN)")
        self.postprocess_panel_sizer.Add(
            nn_sr_label,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))
        try:
            nn_sr_index = NN_SR_VALUES.index(nn_super_resolution_mode)
        except ValueError:
            nn_sr_index = 0
        self.nn_super_resolution_choice = wx.Choice(
            self.postprocess_panel, choices=list(NN_SR_LABELS))
        self.nn_super_resolution_choice.SetSelection(nn_sr_index)
        self.nn_super_resolution_choice.Bind(wx.EVT_CHOICE, self.on_output_enhancement_changed)
        self.postprocess_panel_sizer.Add(
            self.nn_super_resolution_choice,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        nn_rife_label = wx.StaticText(
            self.postprocess_panel,
            label="图像域补帧 (NN) / Frame Interpolation (NN, RIFE)")
        self.postprocess_panel_sizer.Add(
            nn_rife_label,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))
        try:
            nn_rife_index = NN_FRAME_INTERP_VALUES.index(nn_frame_interpolation)
        except ValueError:
            nn_rife_index = 0
        self.nn_frame_interpolation_choice = wx.Choice(
            self.postprocess_panel, choices=list(NN_FRAME_INTERP_LABELS))
        self.nn_frame_interpolation_choice.SetSelection(nn_rife_index)
        self.nn_frame_interpolation_choice.Bind(wx.EVT_CHOICE, self.on_output_enhancement_changed)
        self.postprocess_panel_sizer.Add(
            self.nn_frame_interpolation_choice,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        nn_rife_hint = wx.StaticText(
            self.postprocess_panel,
            label="RIFE 约 +1 帧延迟；与上方 pose 插帧倍率相乘 / ~1 frame latency; multiplies with pose interp")
        self.postprocess_panel_sizer.Add(
            nn_rife_hint,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        infer_backend_label = wx.StaticText(
            self.postprocess_panel,
            label="NN 推理后端 / NN Infer Backend")
        self.postprocess_panel_sizer.Add(
            infer_backend_label,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))
        try:
            backend_index = INFER_BACKEND_VALUES.index(nn_infer_backend)
        except ValueError:
            backend_index = 0
        self.nn_infer_backend_choice = wx.Choice(
            self.postprocess_panel, choices=list(INFER_BACKEND_LABELS))
        self.nn_infer_backend_choice.SetSelection(backend_index)
        self.nn_infer_backend_choice.Bind(wx.EVT_CHOICE, self.on_output_enhancement_changed)
        self.postprocess_panel_sizer.Add(
            self.nn_infer_backend_choice,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        tha_fp16_label = wx.StaticText(
            self.postprocess_panel,
            label="THA 推理精度 / THA Infer Precision (Student)")
        self.postprocess_panel_sizer.Add(
            tha_fp16_label,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))
        self.tha_infer_fp16_choice = wx.Choice(
            self.postprocess_panel, choices=list(THA_INFER_FP16_LABELS))
        self.tha_infer_fp16_choice.SetSelection(tha_infer_fp16_index)
        self.tha_infer_fp16_choice.Bind(wx.EVT_CHOICE, self.on_tha_infer_fp16_changed)
        self.postprocess_panel_sizer.Add(
            self.tha_infer_fp16_choice,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        enhancement_hint = wx.StaticText(
            self.postprocess_panel,
            label="NN 超分/RIFE 需 DEPLOY [5] output_enhancement；默认全关 / requires tier [5], default off")
        self.postprocess_panel_sizer.Add(
            enhancement_hint,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        self.postprocess_panel_sizer.Layout()
        wx.CallAfter(self.apply_layer_blend_visibility)
        self.update_character_edge_controls_visibility()
        wx.CallAfter(self._refresh_enhancement_controls)
        wx.CallAfter(self.refresh_image_source_ui_visibility)
        wx.CallAfter(self.schedule_postprocess_layout_refresh)

    def on_webcam_capture_panel_show(self, event: wx.ShowEvent) -> None:
        if event.IsShown():
            self._ensure_webcam_capture_bitmap_size()
            self.webcam_capture_panel.Refresh(False)
        event.Skip()

    def on_webcam_capture_panel_size(self, event: wx.SizeEvent) -> None:
        self._ensure_webcam_capture_bitmap_size()
        self.webcam_capture_panel.Refresh(False)
        event.Skip()

    def paint_webcam_capture_panel(self, event: wx.Event) -> None:
        panel = self.webcam_capture_panel
        client = panel.GetClientSize()
        if client.x <= 0 or client.y <= 0:
            return
        dc = wx.BufferedPaintDC(panel)
        dc.SetBackground(wx.Brush(MainFrame.PREVIEW_IDLE_BACKGROUND))
        dc.SetBackgroundMode(wx.SOLID)
        dc.Clear()
        bitmap = getattr(self, "webcam_capture_bitmap", None)
        if bitmap is None or not bitmap.IsOk():
            return
        viewport_side = min(client.x, client.y)
        bitmap_side = min(bitmap.GetWidth(), bitmap.GetHeight())
        if bitmap_side <= 0:
            return
        draw_x = (client.x - viewport_side) // 2
        draw_y = (client.y - viewport_side) // 2
        if viewport_side == bitmap_side:
            dc.DrawBitmap(bitmap, draw_x, draw_y, True)
        else:
            scaled = bitmap.ConvertToImage().Scale(
                viewport_side, viewport_side, wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()
            dc.DrawBitmap(scaled, draw_x, draw_y, True)

    def create_rotation_column(self, parent, rotation_names):
        column_panel = wx.Panel(parent, style=wx.SIMPLE_BORDER)
        column_panel_sizer = wx.FlexGridSizer(cols=2)
        column_panel_sizer.AddGrowableCol(1)
        column_panel.SetSizer(column_panel_sizer)
        column_panel.SetAutoLayout(1)

        for rotation_name in rotation_names:
            self.rotation_labels[rotation_name] = wx.StaticText(
                column_panel, label=rotation_name, style=wx.ALIGN_RIGHT)
            column_panel_sizer.Add(self.rotation_labels[rotation_name],
                                   wx.SizerFlags(1).Expand().Border(wx.ALL, 3))

            self.rotation_value_labels[rotation_name] = wx.TextCtrl(
                column_panel, style=wx.TE_RIGHT)
            self.rotation_value_labels[rotation_name].SetValue("0.00")
            self.rotation_value_labels[rotation_name].Disable()
            column_panel_sizer.Add(self.rotation_value_labels[rotation_name],
                                   wx.SizerFlags(1).Expand().Border(wx.ALL, 3))

        column_panel.GetSizer().Fit(column_panel)
        return column_panel

    def create_display_transform_slider_control(self,
                                                parent: wx.Window,
                                                sizer: wx.FlexGridSizer,
                                                label_text: str,
                                                initial_value: float,
                                                min_value: float,
                                                max_value: float,
                                                increment: float,
                                                slider_min: Optional[float] = None,
                                                slider_max: Optional[float] = None) -> FloatSliderControl:
        return FloatSliderControl(
            parent=parent,
            sizer=sizer,
            label_text=label_text,
            initial_value=initial_value,
            reasonable_min=min_value,
            reasonable_max=max_value,
            increment=increment,
            change_handler=self.on_display_transform_control_changed,
            slider_min=slider_min,
            slider_max=slider_max)

    def resolve_tha3_character_png_path(self, path: Optional[str] = None) -> Optional[str]:
        candidate = path if path is not None else self.last_tha3_character_png
        return self.resolve_character_model_path(candidate)

    def update_load_model_buttons(self):
        if hasattr(self, "load_last_model_button"):
            self.load_last_model_button.Enable(bool(self.last_loaded_model_path))
        resolved_tha3 = self.resolve_tha3_character_png_path()
        tha3_last_ready = bool(resolved_tha3) and os.path.isfile(resolved_tha3)
        if tha3_last_ready and resolved_tha3 != self.last_tha3_character_png:
            self.last_tha3_character_png = resolved_tha3
        if hasattr(self, "load_last_tha3_png_button"):
            self.load_last_tha3_png_button.Enable(tha3_last_ready)

    def show_full_controls_window(self, *, defer_ulw_sync: bool = False, skip_state_reload: bool = False):
        show_start_time = time.perf_counter()
        if not skip_state_reload:
            self.reload_persistent_ui_state_from_disk()
        self.apply_mouth_persistent_state_to_args()
        self.apply_persistent_slider_value_states()
        self.create_controls_frame()
        self._apply_persisted_tha_infer_fp16_choice()
        self.full_controls_expanded = True
        self.refresh_model_loaded_ui_state()
        self.ensure_application_windows_visible(defer_ulw_sync=defer_ulw_sync)
        self.ensure_output_frame()
        self.initialize_output_bitmap()
        self.refresh_output_frame_chrome()
        if getattr(self, "output_frame", None) is not None:
            self.output_frame.result_image_panel.Refresh(False)
        wx.CallAfter(self._post_show_controls_setup)
        _startup_record(
            "show_full_controls_window (build + show all windows)",
            (time.perf_counter() - show_start_time) * 1000.0,
            defer_ulw_sync=defer_ulw_sync)

    def show_compact_launcher(self):
        if not self._restoring_window_geometry:
            self.save_persistent_ui_state()
        self.full_controls_expanded = False
        if self.controls_frame is not None:
            self.controls_frame.Show(False)
        self.ensure_application_windows_visible()
        if self.is_capture_source_active():
            self.schedule_active_capture_timer()
        else:
            self.schedule_idle_capture_timer()

    def toggle_full_controls_clicked(self, event: wx.Event):
        self.show_full_controls_window()

    def switch_to_compact_clicked(self, event: wx.Event):
        self.show_compact_launcher()

    def _perform_head_orientation_calibration(
            self,
            *,
            calibration_time: Optional[float] = None) -> bool:
        """Path A only: converter head orientation; never resets output dynamic enhancement."""
        if self.latest_face_screen_motion is None:
            self.refresh_auto_transform_status("NO FACE")
            return False
        if not self.pose_converter.apply_face_orientation_calibration():
            self.refresh_auto_transform_status("NO FACE")
            return False

        time_now = time.time() if calibration_time is None else calibration_time
        self.last_direction_calibration_time = time_now
        self.refresh_auto_transform_status(
            "READY" if self.enable_auto_transform_checkbox.GetValue() else "OFF")
        self.save_persistent_ui_state()
        return True

    def calibrate_head_orientation_quick(self, event: wx.Event):
        self._perform_head_orientation_calibration()
        event.Skip()

    def calibrate_neutral_clicked(self, event: wx.Event):
        self._perform_head_orientation_calibration()
        event.Skip()

    def calibrate_scale_clicked(self, event: wx.Event):
        if self._perform_output_dynamic_enhancement_calibration():
            self._refresh_after_output_dynamic_enhancement_calibration()
        else:
            self.refresh_auto_transform_status("NO FACE")
        event.Skip()

    def is_model_loaded(self) -> bool:
        if self.get_image_source_mode() == IMAGE_SOURCE_THA3:
            return self.active_image_source.is_ready(self)
        return self.poser is not None and self.torch_source_image is not None and self.wx_source_image is not None

    def get_image_source_mode(self) -> str:
        return normalize_image_source_mode(getattr(self, "image_source_mode", IMAGE_SOURCE_THA4))

    def refresh_image_source_ui_visibility(self):
        spec = self.active_image_source.get_load_ui_spec()
        if hasattr(self, "tha3_variant_panel"):
            self.tha3_variant_panel.Show(spec.show_tha3_variant)
        elif hasattr(self, "tha3_model_variant_choice"):
            self.tha3_model_variant_choice.Show(spec.show_tha3_variant)
            if hasattr(self, "tha3_model_variant_label"):
                self.tha3_model_variant_label.Show(spec.show_tha3_variant)
        if hasattr(self, "postprocess_panel"):
            self.postprocess_panel.Layout()
        if hasattr(self, "right_sidebar"):
            self.right_sidebar.Layout()
        wx.CallAfter(self.refresh_right_sidebar_scrolling)
        if hasattr(self, "controls_frame") and self.controls_frame is not None:
            self.controls_frame.Layout()
        self.update_load_model_buttons()

    def on_tha3_model_variant_changed(self, event: wx.Event):
        if not hasattr(self, "tha3_model_variant_choice"):
            event.Skip()
            return
        self.tha3_model_variant = THA3_VARIANT_CHOICES[self.tha3_model_variant_choice.GetSelection()][0]
        self.save_persistent_ui_state()
        self._sync_tha_infer_fp16_ui()
        if self.get_image_source_mode() == IMAGE_SOURCE_THA3 and self.last_tha3_character_png:
            switch_image_source(self, IMAGE_SOURCE_THA3)
            if os.path.isfile(self.last_tha3_character_png):
                self.active_image_source.load_asset(self, self.last_tha3_character_png)
        event.Skip()

    def load_tha3_character_png(self, event: wx.Event):
        self.refresh_and_autoload_video_source()
        from tha3_assets_prompt import ensure_tha3_assets_available

        if not ensure_tha3_assets_available(self, self.tha3_model_variant):
            event.Skip()
            return
        images_root = os.path.join(_EXPERIMENT_DIR, "..", "..", "vendor", "easyvtuber", "data_images")
        if not os.path.isdir(images_root):
            images_root = r"F:\EasyVtuber\EasyVtuber_v0.8.1\EasyVtuber_v0.8.1\data\images"
        file_dialog = wx.FileDialog(
            self.get_dialog_parent(),
            "Choose THA3 character PNG (512x512 RGBA)",
            images_root if os.path.isdir(images_root) else "",
            "",
            "PNG files (*.png)|*.png",
            wx.FD_OPEN)
        if file_dialog.ShowModal() == wx.ID_OK:
            png_path = os.path.join(file_dialog.GetDirectory(), file_dialog.GetFilename())
            if self.get_image_source_mode() != IMAGE_SOURCE_THA3:
                switch_image_source(self, IMAGE_SOURCE_THA3)
            if self.active_image_source.load_asset(self, png_path):
                self.update_load_model_buttons()
                self.save_persistent_ui_state()
        file_dialog.Destroy()
        event.Skip()

    def load_last_tha3_character_png(self, event: wx.Event):
        self.refresh_and_autoload_video_source()
        from tha3_assets_prompt import ensure_tha3_assets_available

        if not ensure_tha3_assets_available(self, self.tha3_model_variant):
            event.Skip()
            return
        resolved_path = self.resolve_tha3_character_png_path()
        if not resolved_path:
            return
        if not os.path.isfile(resolved_path):
            invalid_path = self.last_tha3_character_png or resolved_path
            self.last_tha3_character_png = None
            self.update_load_model_buttons()
            self.save_persistent_ui_state()
            message_dialog = wx.MessageDialog(
                self.get_dialog_parent(),
                "上次 THA3 立绘路径已失效，请重新选择：\n%s\n\nLast THA3 PNG path is no longer valid."
                % invalid_path,
                "Load Last THA3 PNG",
                wx.OK | wx.ICON_WARNING)
            message_dialog.ShowModal()
            message_dialog.Destroy()
            event.Skip()
            return
        self.last_tha3_character_png = resolved_path
        if self.get_image_source_mode() != IMAGE_SOURCE_THA3:
            switch_image_source(self, IMAGE_SOURCE_THA3)
        self.active_image_source.load_asset(self, resolved_path)
        self.update_load_model_buttons()
        event.Skip()

    def get_dialog_parent(self) -> wx.Window:
        if self.controls_frame is not None and self.controls_frame.IsShown():
            return self.controls_frame
        return self

    def refresh_model_loaded_ui_state(self):
        if getattr(self.pose_converter, "panel", None) is not None:
            if hasattr(self.pose_converter, "set_panel_enabled"):
                self.pose_converter.set_panel_enabled(True)
            else:
                self.pose_converter.panel.Enable(True)
            if hasattr(self.pose_converter, "refresh_audio_input_runtime"):
                self.pose_converter.refresh_audio_input_runtime(time.time())
        if hasattr(self, "animation_left_panel"):
            self.animation_left_panel.Enable(True)
        if hasattr(self, "postprocess_panel"):
            self.postprocess_panel.Enable(True)
        if getattr(self, "video_source_panel", None) is not None:
            self.video_source_panel.Enable(True)
        if getattr(self, "video_source_choice", None) is not None:
            self.video_source_choice.Enable(True)
        if getattr(self, "refresh_video_sources_button", None) is not None:
            self.refresh_video_sources_button.Enable(True)
        if getattr(self, "pick_window_capture_button", None) is not None:
            self.pick_window_capture_button.Enable(True)
        self.update_load_model_buttons()

    def on_output_background_changed(self, event: wx.Event):
        self.notify_output_background_changed()
        event.Skip()

    def on_output_background_mode_changed(self, event: wx.Event):
        if self.get_output_background_mode() == OUTPUT_BACKGROUND_IMAGE:
            if not self.get_output_background_image_path():
                self.set_output_background_image_path(self.get_bundled_transparent_background_path())
        self.notify_output_background_changed()
        event.Skip()

    def on_output_background_image_browse(self, event: wx.Event):
        dialog = wx.FileDialog(
            self,
            "选择背景图片 / Choose Background Image",
            wildcard="Image files (*.png;*.jpg;*.jpeg;*.bmp;*.webp)|*.png;*.jpg;*.jpeg;*.bmp;*.webp",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dialog.ShowModal() != wx.ID_OK:
            dialog.Destroy()
            event.Skip()
            return
        selected_path = dialog.GetPath()
        dialog.Destroy()
        self.set_output_background_image_path(selected_path)
        mode_control = getattr(self, "output_background_mode_choice", None)
        if isinstance(mode_control, wx.Choice):
            try:
                mode_control.SetSelection(OUTPUT_BACKGROUND_MODE_VALUES.index(OUTPUT_BACKGROUND_IMAGE))
            except ValueError:
                pass
        self.notify_output_background_changed()
        event.Skip()

    def on_display_transform_control_changed(self, event: Optional[wx.Event] = None):
        if hasattr(self, "direction_calibration_interval_panel"):
            self.direction_calibration_interval_panel.Enable(self.enable_direction_calibration_checkbox.GetValue())
        if hasattr(self, "scale_calibration_interval_panel"):
            self.scale_calibration_interval_panel.Enable(self.enable_scale_calibration_checkbox.GetValue())
        old_invert = self._invert_tilt_mapping_state.GetValue()
        self._safe_checkbox_value(
            "invert_tilt_mapping_checkbox", self._invert_tilt_mapping_state)
        invert_changed = old_invert != self._invert_tilt_mapping_state.GetValue()
        self.save_persistent_ui_state()
        snap_transform = (
            not self.enable_auto_transform_checkbox.GetValue() or invert_changed)
        self.update_display_transform_state(snap_to_target=snap_transform)
        if invert_changed:
            self._refresh_pose_after_tilt_mapping_changed()
        self.refresh_scale_curve_status()
        self.request_scale_curve_repaint(force=True)
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(
                self.last_banner_text,
                push_capture=invert_changed)

    def set_neutral_face_screen_motion(self, face_screen_motion: FaceScreenMotion):
        self.neutral_face_screen_motion = FaceScreenMotion(
            center_x=face_screen_motion.center_x,
            center_y=face_screen_motion.center_y,
            face_size=face_screen_motion.face_size)

    def set_neutral_head_roll_deg(self, head_roll_deg: Optional[float]):
        self.neutral_head_roll_deg = 0.0 if head_roll_deg is None else head_roll_deg

    def update_neutral_face_direction(self, face_screen_motion: FaceScreenMotion):
        if self.neutral_face_screen_motion is None:
            self.set_neutral_face_screen_motion(face_screen_motion)
        else:
            self.neutral_face_screen_motion = FaceScreenMotion(
                center_x=face_screen_motion.center_x,
                center_y=face_screen_motion.center_y,
                face_size=self.neutral_face_screen_motion.face_size)

    def update_neutral_output_enhancement(self, face_screen_motion: FaceScreenMotion):
        """Refresh scale baseline, horizontal center, and head-roll neutral; keep vertical center to avoid upward drift."""
        if self.neutral_face_screen_motion is None:
            self.set_neutral_face_screen_motion(face_screen_motion)
            self.set_neutral_head_roll_deg(self.latest_head_roll_deg)
            return
        self.neutral_face_screen_motion = FaceScreenMotion(
            center_x=face_screen_motion.center_x,
            center_y=self.neutral_face_screen_motion.center_y,
            face_size=face_screen_motion.face_size)
        self.set_neutral_head_roll_deg(self.latest_head_roll_deg)

    def apply_neutral_calibration(self,
                                  face_screen_motion: FaceScreenMotion,
                                  reset_display_state: bool = False,
                                  calibration_time: Optional[float] = None):
        self.set_neutral_face_screen_motion(face_screen_motion)
        self.set_neutral_head_roll_deg(self.latest_head_roll_deg)
        time_value = time.time() if calibration_time is None else calibration_time
        self.last_direction_calibration_time = time_value
        self.last_scale_calibration_time = time_value
        if reset_display_state:
            self.display_offset_x = 0.0
            self.display_offset_y = 0.0
            self.display_scale = 1.0
            self.display_rotation_deg = 0.0

    def apply_enabled_auto_calibration_on_load(self,
                                               face_screen_motion: Optional[FaceScreenMotion],
                                               calibration_time: Optional[float] = None):
        time_value = time.time() if calibration_time is None else calibration_time
        if self.enable_direction_calibration_checkbox.GetValue():
            if self.pose_converter.apply_face_orientation_calibration():
                self.last_direction_calibration_time = time_value
            else:
                self.last_direction_calibration_time = None
        else:
            self.last_direction_calibration_time = None
        if face_screen_motion is None:
            return
        if self.enable_scale_calibration_checkbox.GetValue():
            self.update_neutral_output_enhancement(face_screen_motion)
            self.last_scale_calibration_time = time_value
        else:
            self.last_scale_calibration_time = None

    def try_apply_auto_forward_gaze_calibration(self, time_now: float, *, respect_interval: bool) -> bool:
        """Periodic auto-click of UI-A01/A09/B04 (path A only)."""
        if not self.enable_direction_calibration_checkbox.GetValue():
            return False

        interval_seconds = max(1.0, self.auto_direction_calibration_interval_seconds_ctrl.GetValue())
        if respect_interval:
            if self.last_direction_calibration_time is None:
                self.last_direction_calibration_time = time_now
                return False
            if time_now - self.last_direction_calibration_time < interval_seconds:
                return False

        return self._perform_head_orientation_calibration(calibration_time=time_now)

    def maybe_apply_periodic_direction_calibration(self):
        self.try_apply_auto_forward_gaze_calibration(time.time(), respect_interval=True)

    def maybe_apply_periodic_scale_calibration(self, latest_motion: FaceScreenMotion):
        """Periodic auto-click of UI-A02/A10 (camera path B only; mouse uses UI-B07)."""
        if self.is_mouse_audio_mocap_mode():
            return
        if not self.enable_scale_calibration_checkbox.GetValue():
            return

        interval_seconds = max(1.0, self.auto_scale_calibration_interval_seconds_ctrl.GetValue())
        time_now = time.time()
        if self.last_scale_calibration_time is None:
            self.last_scale_calibration_time = time_now
            return

        if time_now - self.last_scale_calibration_time < interval_seconds:
            return

        if self._perform_output_dynamic_enhancement_calibration(calibration_time=time_now):
            self._refresh_after_output_dynamic_enhancement_calibration()

    @staticmethod
    def extract_face_screen_motion(detection_result) -> Optional[FaceScreenMotion]:
        if not hasattr(detection_result, "face_landmarks") or len(detection_result.face_landmarks) == 0:
            return None

        face_landmarks = detection_result.face_landmarks[0]
        if len(face_landmarks) == 0:
            return None

        xs = [landmark.x for landmark in face_landmarks]
        ys = [landmark.y for landmark in face_landmarks]
        min_x = max(0.0, min(xs))
        max_x = min(1.0, max(xs))
        min_y = max(0.0, min(ys))
        max_y = min(1.0, max(ys))

        avg_x = sum(xs) / len(xs)
        avg_y = sum(ys) / len(ys)
        center_x = (avg_x - 0.5) * 2.0
        center_y = (avg_y - 0.5) * 2.0
        face_size = max(max_x - min_x, max_y - min_y)
        return FaceScreenMotion(center_x=center_x, center_y=center_y, face_size=face_size)

    def refresh_auto_transform_status(self, mode: str):
        if not hasattr(self, "auto_transform_status_text"):
            return
        mode_text = {
            "OFF": "关闭 / OFF",
            "READY": "就绪 / READY",
            "LIVE": "跟随 / LIVE",
            "HOLD": "保持 / HOLD",
            "RETURN": "回中 / RETURN",
            "NO FACE": "无人脸 / NO FACE",
        }.get(mode, mode)
        neutral_text = "基准 / neutral: 未标定 / not calibrated"
        if self.neutral_face_screen_motion is not None:
            neutral = self.neutral_face_screen_motion
            neutral_text = "基准 / neutral\nx=%+.2f y=%+.2f z=%.3f r=%+.1f°" % (
                neutral.center_x, neutral.center_y, neutral.face_size, self.neutral_head_roll_deg)
        self.set_wrapped_static_text_if_changed(
            self.auto_transform_status_text,
            "自动状态 / Auto %s\nx=%+.0f y=%+.0f s=%.2f t=%+.1f°\n%s"
            % (mode_text, self.display_offset_x, self.display_offset_y,
               self.display_scale, self.display_rotation_deg, neutral_text))

    def get_scale_curve_neutral_face_size(self) -> float:
        if self.neutral_face_screen_motion is not None:
            return self.neutral_face_screen_motion.face_size
        return 0.30

    def get_scale_curve_current_delta(self) -> Optional[float]:
        if self.latest_face_screen_motion is None or self.neutral_face_screen_motion is None:
            return None
        return self.latest_face_screen_motion.face_size - self.neutral_face_screen_motion.face_size

    def get_scale_curve_domain(self) -> tuple[float, float]:
        current_delta = self.get_scale_curve_current_delta()
        current_abs = abs(current_delta) if current_delta is not None else 0.0
        peak_shift_abs = abs(self.scale_curve_peak_shift_spin.GetValue())
        half_range = max(MainFrame.SCALE_CURVE_DELTA_RANGE, current_abs * 1.8, peak_shift_abs * 1.4 + 0.08, 0.18)
        half_range = min(0.40, half_range)
        return -half_range, half_range

    def request_scale_curve_repaint(self, force: bool = False):
        if not hasattr(self, "scale_curve_panel"):
            return
        current_delta = self.get_scale_curve_current_delta()
        signature = (
            None if current_delta is None else round(current_delta, 4),
            round(self.get_scale_curve_neutral_face_size(), 4),
            round(self.scale_curve_near_spin.GetValue(), 3),
            round(self.scale_curve_far_spin.GetValue(), 3),
            round(self.scale_curve_arc_spin.GetValue(), 3),
            round(self.scale_curve_peak_shift_spin.GetValue(), 4),
            round(self.min_scale_spin.GetValue(), 3),
            round(self.max_scale_spin.GetValue(), 3),
            round(self.scale_gain_spin.GetValue(), 3),
        )
        now = time.perf_counter()
        if not force and self._last_scale_curve_signature == signature and now - self._last_scale_curve_refresh_time < 0.25:
            return
        if not force:
            last_ns = getattr(self, "_last_scale_curve_preview_time_ns", None)
            if not self.should_refresh_auxiliary_preview(last_ns):
                return
            self._last_scale_curve_preview_time_ns = time.time_ns()
        self._last_scale_curve_signature = signature
        self._last_scale_curve_refresh_time = now
        self.scale_curve_panel.Refresh(False)

    def get_scale_curve_samples(self, sample_count: int = 96) -> List[tuple[float, float]]:
        neutral_face_size = self.get_scale_curve_neutral_face_size()
        domain_min, domain_max = self.get_scale_curve_domain()
        samples = []
        for index in range(sample_count + 1):
            alpha = index / sample_count
            delta_value = domain_min + (domain_max - domain_min) * alpha
            scale_value = self.compute_target_scale(neutral_face_size + delta_value, neutral_face_size)
            samples.append((delta_value, scale_value))
        return samples

    def refresh_scale_curve_status(self):
        if not hasattr(self, "scale_curve_status_text"):
            return
        current_delta = self.get_scale_curve_current_delta()
        if current_delta is None:
            self.set_wrapped_static_text_if_changed(
                self.scale_curve_status_text,
                "当前点 / Point\n等待人脸输入 / Waiting for face")
            return

        neutral_face_size = self.get_scale_curve_neutral_face_size()
        raw_scale, target_scale, clamp_label = self.compute_scale_response(
            neutral_face_size + current_delta, neutral_face_size)
        if clamp_label == "min":
            clamp_text = "\n限制 / clamp: min"
        elif clamp_label == "max":
            clamp_text = "\n限制 / clamp: max"
        else:
            clamp_text = ""
        self.set_wrapped_static_text_if_changed(
            self.scale_curve_status_text,
            "当前点 / Point\nΔ=%+.3f raw=%.3f tgt=%.3f\nn=%.2f f=%.2f a=%.2f p=%+.3f%s"
            % (current_delta, raw_scale, target_scale,
               self.scale_curve_near_spin.GetValue(),
               self.scale_curve_far_spin.GetValue(),
               self.scale_curve_arc_spin.GetValue(),
               self.scale_curve_peak_shift_spin.GetValue(),
               clamp_text))

    def compute_scale_response(self, latest_face_size: float, neutral_face_size: float) -> tuple[float, float, Optional[str]]:
        min_scale = min(self.min_scale_spin.GetValue(), self.max_scale_spin.GetValue())
        max_scale = max(self.min_scale_spin.GetValue(), self.max_scale_spin.GetValue())
        min_scale = max(0.1, min_scale)
        max_scale = max(min_scale, max_scale)
        arc_power = max(0.05, self.scale_curve_arc_spin.GetValue())
        overshoot_factor = 1.18

        size_delta = latest_face_size - neutral_face_size - self.scale_curve_peak_shift_spin.GetValue()
        scaled_delta = size_delta * self.scale_gain_spin.GetValue()

        if scaled_delta >= 0.0:
            positive_span = max_scale - 1.0
            expand_response = math.tanh(scaled_delta * self.scale_curve_near_spin.GetValue())
            expand_response = expand_response ** arc_power
            raw_scale = 1.0 + positive_span * expand_response * overshoot_factor
            upper_bound = max(1.0, max_scale)
            lower_bound = min(1.0, max_scale)
            target_scale = min(upper_bound, max(lower_bound, raw_scale))
            if max_scale >= 1.0:
                clamp_label = "max" if target_scale >= max_scale - 1e-4 else None
            else:
                clamp_label = "max" if target_scale <= max_scale + 1e-4 else None
            return raw_scale, target_scale, clamp_label

        negative_span = 1.0 - min_scale
        if negative_span <= 0.0:
            return min_scale, min_scale, "min"

        # Shrink more conservatively than zoom-in so moving away does not make the avatar too small too quickly.
        shrink_response = math.tanh(abs(scaled_delta) * self.scale_curve_far_spin.GetValue())
        shrink_response = shrink_response ** arc_power
        raw_scale = 1.0 - negative_span * shrink_response * overshoot_factor
        target_scale = max(min_scale, raw_scale)
        return raw_scale, target_scale, "min" if target_scale <= min_scale + 1e-4 else None

    def compute_target_scale(self, latest_face_size: float, neutral_face_size: float) -> float:
        _, target_scale, _ = self.compute_scale_response(latest_face_size, neutral_face_size)
        return target_scale

    def apply_negative_tilt_limit_to_pose(self, pose: List[float]) -> List[float]:
        tilt_limit_value = self.tilt_limit_spin.GetValue()
        if tilt_limit_value >= 0.0:
            return pose

        # Negative tilt limit repurposes the control to damp the roll sent into THA4.
        transfer_factor = max(0.0, 1.0 + tilt_limit_value / 30.0)
        adjusted_pose = list(pose)
        adjusted_pose[self.pose_converter.neck_z_index] *= transfer_factor
        adjusted_pose[self.pose_converter.body_z_index] *= transfer_factor
        return adjusted_pose

    def update_display_transform_state(self, snap_to_target: bool = False) -> bool:
        enabled = self.enable_auto_transform_checkbox.GetValue()
        old_offset_x = self.display_offset_x
        old_offset_y = self.display_offset_y
        old_scale = self.display_scale
        old_rotation_deg = self.display_rotation_deg

        # Periodic "Calibrate Forward Gaze" recalibrates the pose_converter head
        # orientation offsets, which affect rendering regardless of dynamic
        # enhancement. Run it here, BEFORE the enabled branch, so it keeps
        # working when auto-transform is OFF (it used to sit only inside the
        # enabled branch and silently stopped). Its own enable-checkbox +
        # interval guards live in try_apply_auto_forward_gaze_calibration.
        self.maybe_apply_periodic_direction_calibration()

        if not enabled:
            target_offset_x = 0.0
            target_offset_y = 0.0
            target_scale = 1.0
            target_rotation_deg = 0.0
            mode = "OFF"
            snap_to_target = True
        else:
            latest_motion = self.latest_face_screen_motion
            if latest_motion is not None:
                if self.neutral_face_screen_motion is None:
                    self.apply_neutral_calibration(latest_motion)
                else:
                    # Direction calibration now runs unconditionally above;
                    # scale calibration stays here (needs neutral + live motion
                    # and is meaningful only while dynamic enhancement is on).
                    self.maybe_apply_periodic_scale_calibration(latest_motion)
                neutral_motion = self.neutral_face_screen_motion
                target_offset_x = (latest_motion.center_x - neutral_motion.center_x) * self.move_x_gain_spin.GetValue()
                target_offset_y = (latest_motion.center_y - neutral_motion.center_y) * self.move_y_gain_spin.GetValue()
                target_scale = self.compute_target_scale(latest_motion.face_size, neutral_motion.face_size)
                tilt_limit = max(0.0, self.tilt_limit_spin.GetValue())
                head_roll_delta = (self.latest_head_roll_deg if self.latest_head_roll_deg is not None else 0.0) \
                    - self.neutral_head_roll_deg
                head_roll_delta = -head_roll_delta
                target_rotation_deg = max(-tilt_limit, min(tilt_limit, head_roll_delta))
                mode = "LIVE"
            elif self.last_face_detected_time is not None \
                    and time.time() - self.last_face_detected_time <= MainFrame.AUTO_TRANSFORM_HOLD_SECONDS:
                target_offset_x = self.display_offset_x
                target_offset_y = self.display_offset_y
                target_scale = self.display_scale
                target_rotation_deg = self.display_rotation_deg
                mode = "HOLD"
            else:
                target_offset_x = 0.0
                target_offset_y = 0.0
                target_scale = 1.0
                target_rotation_deg = 0.0
                mode = "RETURN"

        if snap_to_target:
            alpha = 1.0
        else:
            smoothing = max(0.0, min(0.98, self.smoothing_spin.GetValue()))
            alpha = 1.0 - smoothing

        self.display_offset_x = old_offset_x + (target_offset_x - old_offset_x) * alpha
        self.display_offset_y = old_offset_y + (target_offset_y - old_offset_y) * alpha
        self.display_scale = old_scale + (target_scale - old_scale) * alpha
        self.display_rotation_deg = old_rotation_deg + (target_rotation_deg - old_rotation_deg) * alpha
        time_now = time.time()
        if time_now - self._last_transform_status_refresh_time >= 0.2:
            self.refresh_auto_transform_status(mode)
            self.refresh_scale_curve_status()
            self._last_transform_status_refresh_time = time_now
        self.request_scale_curve_repaint(force=False)
        changed = abs(self.display_offset_x - old_offset_x) > 0.25 \
            or abs(self.display_offset_y - old_offset_y) > 0.25 \
            or abs(self.display_scale - old_scale) > 0.002 \
            or abs(self.display_rotation_deg - old_rotation_deg) > 0.05

        return changed

    def update_capture_panel(self, event: wx.Event):
        self._capture_frame_serial += 1
        time_now = time.time()

        if self.is_mouse_audio_mocap_mode():
            self.update_mouse_mocap_face_pose(time_now)
            if self.should_update_capture_preview_ui(time_now):
                self._last_preview_ui_time = time_now
                self.draw_capture_status_message(self.get_mouse_mocap_status_message())
            self.schedule_active_capture_timer()
            return

        if not self.is_capture_source_active():
            if self.video_source_kind == "window":
                # Window capture does not depend on top-most; if the target window is closed,
                # we need to fail fast and switch to another available input.
                if not self._window_invalid_autoswitch_attempted:
                    self._window_invalid_autoswitch_attempted = True

                    self.video_capture_status_message = (
                        "窗口捕获源失效（窗口可能已关闭）。"
                        "正在切换到其它视频源..."
                    )

                    def _switch():
                        if self.video_source_choice is None:
                            return
                        # Prefer camera sources. Avoid auto-selecting "Video file..." because it opens a dialog.
                        for lbl in self.video_source_choice.GetStrings():
                            entry = self.video_source_choice_map.get(lbl)
                            if not entry:
                                continue
                            if entry[0] == "camera":
                                self.video_source_choice.SetStringSelection(lbl)
                                self.on_video_source_choice_changed(wx.CommandEvent())
                                return

                    wx.CallAfter(_switch)
                else:
                    self.video_capture_status_message = (
                        self.video_capture_status_message
                        or "窗口捕获源失效（窗口可能已关闭）。"
                           "请刷新设备列表或重新选择窗口捕获。"
                    )

                if self.should_update_capture_preview_ui(time_now):
                    self._last_preview_ui_time = time_now
                    self.draw_capture_status_message(self.video_capture_status_message or "Nothing yet!")
                self.schedule_idle_capture_timer()
                return

            if self.video_capture_status_message is None:
                self.video_capture_status_message = "摄像头未连接 / Camera not connected"
            if self.should_update_capture_preview_ui(time_now):
                self._last_preview_ui_time = time_now
                self.draw_capture_status_message(self.video_capture_status_message or "Nothing yet!")
            self.schedule_idle_capture_timer()
            return

        bgr_frame = self.read_capture_frame_bgr()
        if bgr_frame is None or not self.is_acceptable_capture_frame(bgr_frame):
            if self._last_good_webcam_bgr_frame is not None:
                bgr_frame = self._last_good_webcam_bgr_frame
            else:
                if self.video_capture_status_message is None:
                    self.video_capture_status_message = (
                        "画面无效或解码失败 / Invalid or corrupted frame")
                if self.should_update_capture_preview_ui(time_now):
                    self._last_preview_ui_time = time_now
                    self.draw_capture_status_message(
                        self.video_capture_status_message or "Nothing yet!")
                self.schedule_active_capture_timer()
                return
        else:
            self._last_good_webcam_bgr_frame = bgr_frame
            self.video_capture_status_message = None
            self._note_input_fps_tick()

        if self.should_update_capture_preview_ui(time_now):
            self._last_preview_ui_time = time_now
            self.update_capture_preview_bitmap(bgr_frame)

        if self.should_process_mediapipe(time_now):
            if (
                    self.video_source_kind == "window"
                    and self._capture_frame_serial == self._last_mediapipe_capture_serial):
                self.schedule_active_capture_timer()
                return
            if self.face_landmarker is None and not self.ensure_face_landmarker(show_dialog=False):
                self.schedule_active_capture_timer()
                return
            self._last_mediapipe_process_time = time_now
            self._last_mediapipe_capture_serial = self._capture_frame_serial
            mocap_frame = bgr_frame
            if self.video_source_kind == "window":
                limited = self.limit_bgr_frame_for_mocap(bgr_frame)
                if limited is not None:
                    mocap_frame = limited
            rgb_frame = cv2.cvtColor(mocap_frame, cv2.COLOR_BGR2RGB)
            if self.should_mirror_capture_preview():
                rgb_frame = cv2.flip(rgb_frame, 1)
            time_ms = self._next_mediapipe_video_timestamp_ms(time_now)
            mediapipe = get_mediapipe_module()
            mediapipe_image = mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=rgb_frame)
            # Hand the heavy detect_for_video call to a worker thread so it never
            # blocks the wx UI/render thread (mirrors the THA pose-infer worker).
            # rgb_frame is kept referenced by the job so its buffer stays alive
            # until the (deferred) detection consumes the wrapping mp.Image.
            self._schedule_mediapipe_detect(mediapipe_image, time_ms, rgb_frame)

        self.schedule_active_capture_timer()

    def _schedule_mediapipe_detect(self, mediapipe_image, time_ms: int, frame_buffer) -> None:
        """Queue a frame for off-thread MediaPipe detection (latest-wins, single worker)."""
        if self._is_closing or self.face_landmarker is None:
            return
        with self._mediapipe_lock:
            self._pending_mediapipe_job = (mediapipe_image, time_ms, frame_buffer)
            if self._mediapipe_worker_active:
                return
            self._mediapipe_worker_active = True
        threading.Thread(
            target=self._mediapipe_detect_worker,
            daemon=True,
            name="mediapipe-detect").start()

    def _mediapipe_detect_worker(self) -> None:
        latest_detection = None
        try:
            while not self._is_closing:
                with self._mediapipe_lock:
                    job = self._pending_mediapipe_job
                    self._pending_mediapipe_job = None
                if job is None:
                    break
                landmarker = self.face_landmarker
                if landmarker is None:
                    break
                mediapipe_image, time_ms, _frame_buffer = job
                try:
                    latest_detection = landmarker.detect_for_video(
                        mediapipe_image, time_ms)
                except (ValueError, RuntimeError) as exc:
                    if not self._mediapipe_detect_error_logged:
                        self._mediapipe_detect_error_logged = True
                        print(
                            "MediaPipe detect_for_video failed (further errors suppressed):",
                            exc,
                            file=sys.stderr)
                    continue
                self._mediapipe_detect_error_logged = False
                with self._mediapipe_lock:
                    if self._pending_mediapipe_job is None:
                        break
        finally:
            with self._mediapipe_lock:
                self._mediapipe_worker_active = False
        if latest_detection is not None and not self._is_closing:
            wx.CallAfter(self._finish_mediapipe_detect, latest_detection)

    def _ensure_window_capture_worker(self) -> None:
        """Start the background window-capture grabber if it is not running."""
        if self._is_closing:
            return
        with self._window_capture_lock:
            if self._window_capture_worker_active:
                return
            self._window_capture_worker_active = True
        threading.Thread(
            target=self._window_capture_worker,
            daemon=True,
            name="window-capture").start()

    def _window_capture_worker(self) -> None:
        """Continuously grab the target window off the UI thread (latest-wins).

        Keeps the blocking PrintWindow/BitBlt grab off the wx UI thread so a
        stalled grab degrades to a reused frame instead of freezing the app.
        """
        interval = MainFrame.CAPTURE_PROCESS_INTERVAL_MS / 1000.0
        try:
            while not self._is_closing and self.video_source_kind == "window":
                hwnd = self._window_capture_hwnd
                if hwnd is None:
                    break
                start = time.perf_counter()
                try:
                    frame = window_capture.capture_window_client_bgr(hwnd)
                except Exception as exc:
                    frame = None
                    if not getattr(self, "_window_capture_read_error", None):
                        self._window_capture_read_error = repr(exc)
                        _err_record(
                            "H-WINCAP",
                            "character_model_mediapipe_puppeteer_load_preview.py:_window_capture_worker",
                            exc,
                            data={"hwnd": hwnd})
                elapsed = time.perf_counter() - start
                if elapsed >= MainFrame.WINDOW_CAPTURE_STALL_SEC:
                    window_capture.invalidate_capture_method_cache(hwnd)
                if frame is not None:
                    limited = MainFrame.limit_bgr_frame_for_mocap(frame)
                    if limited is not None:
                        frame = limited
                    with self._window_capture_lock:
                        self._window_capture_latest_frame = frame
                        self._window_capture_frame_serial += 1
                sleep_for = interval - (time.perf_counter() - start)
                if sleep_for > 0:
                    time.sleep(sleep_for)
        finally:
            with self._window_capture_lock:
                self._window_capture_worker_active = False
                self._window_capture_latest_frame = None
                self._window_capture_frame_serial = 0

    def _finish_mediapipe_detect(self, detection_result) -> None:
        if self._is_closing or detection_result is None:
            return
        self.update_mediapipe_face_pose(detection_result)

    def update_mediapipe_face_pose(self, detection_result):
        face_screen_motion = self.extract_face_screen_motion(detection_result)
        self.latest_face_screen_motion = face_screen_motion
        if face_screen_motion is None or len(detection_result.facial_transformation_matrixes) == 0:
            self.latest_head_roll_deg = None
            return

        self.last_face_detected_time = time.time()
        xform_matrix = detection_result.facial_transformation_matrixes[0]
        blendshape_params = {}
        for item in detection_result.face_blendshapes[0]:
            blendshape_params[item.category_name] = item.score
        M = xform_matrix[0:3, 0:3]
        rot = Rotation.from_matrix(M)
        euler_angles = rot.as_euler('xyz', degrees=True)
        self.latest_head_roll_deg = euler_angles[2]

        if self.neutral_face_screen_motion is None:
            self.apply_neutral_calibration(face_screen_motion, calibration_time=self.last_face_detected_time)

        if HEAD_X in self.rotation_value_labels:
            self.set_text_ctrl_if_changed(self.rotation_value_labels[HEAD_X], "%0.2f" % euler_angles[0])
        if HEAD_Y in self.rotation_value_labels:
            self.set_text_ctrl_if_changed(self.rotation_value_labels[HEAD_Y], "%0.2f" % euler_angles[1])
        if HEAD_Z in self.rotation_value_labels:
            self.set_text_ctrl_if_changed(self.rotation_value_labels[HEAD_Z], "%0.2f" % euler_angles[2])

        self.mediapipe_face_pose = MediaPipeFacePose(blendshape_params, xform_matrix)
        # Scale-curve preview is repainted by on_ui_anim_timer (25 fps cap).
        self._scale_curve_dirty = True

    @staticmethod
    def convert_to_100(x):
        return int(max(0.0, min(1.0, x)) * 100)

    def _source_preview_target_size(self) -> wx.Size:
        panel = getattr(self, "source_image_panel", None)
        if panel is not None:
            client = panel.GetClientSize()
            if client.x > 0 and client.y > 0:
                return client
        return wx.Size(MainFrame.SOURCE_PREVIEW_SIZE, MainFrame.SOURCE_PREVIEW_SIZE)

    def on_source_image_panel_show(self, event: wx.ShowEvent) -> None:
        if event.IsShown():
            wx.CallAfter(self.update_source_image_bitmap, force=True)
        event.Skip()

    def on_source_image_panel_size(self, event: wx.SizeEvent) -> None:
        wx.CallAfter(self.update_source_image_bitmap, force=True)
        event.Skip()

    def paint_source_image_panel(self, event: wx.Event) -> None:
        panel = self.source_image_panel
        client = panel.GetClientSize()
        if client.x <= 0 or client.y <= 0:
            return
        dc = wx.BufferedPaintDC(panel)
        dc.SetBackground(wx.Brush(MainFrame.PREVIEW_IDLE_BACKGROUND))
        dc.SetBackgroundMode(wx.SOLID)
        dc.Clear()
        if self.wx_source_image is None:
            return
        bitmap = getattr(self, "source_image_bitmap", None)
        if bitmap is None or not bitmap.IsOk():
            return
        if bitmap.GetWidth() != client.x or bitmap.GetHeight() != client.y:
            wx.CallAfter(self.update_source_image_bitmap, force=True)
            return
        dc.DrawBitmap(bitmap, 0, 0, True)

    def _invalidate_source_preview_cache(self) -> None:
        self._source_preview_cache_key = None
        self._source_preview_scaled_key = None
        self._source_preview_scaled_bitmap = None

    def update_source_image_bitmap(self, *, force: bool = False) -> None:
        """立绘预览：仅显示默认立绘静态图；加载成功后绘制一次并缓存。"""
        target = self._source_preview_target_size()
        width = max(1, target.x)
        height = max(1, target.y)
        if (
                not getattr(self, "source_image_bitmap", None)
                or not self.source_image_bitmap.IsOk()
                or self.source_image_bitmap.GetWidth() != width
                or self.source_image_bitmap.GetHeight() != height):
            self.source_image_bitmap = wx.Bitmap(width, height)
            force = True
        preview_width = self.source_image_bitmap.GetWidth()
        preview_height = self.source_image_bitmap.GetHeight()
        cache_key = (id(self.wx_source_image), preview_width, preview_height)
        if not force and self._source_preview_cache_key == cache_key:
            if hasattr(self, "source_image_panel"):
                self.source_image_panel.Refresh(False)
            return
        if self.wx_source_image is None:
            MainFrame.fill_bitmap_solid(self.source_image_bitmap, MainFrame.PREVIEW_IDLE_BACKGROUND)
        else:
            dc = wx.MemoryDC()
            dc.SelectObject(self.source_image_bitmap)
            dc.Clear()
            scaled_key = getattr(self, "_source_preview_scaled_key", None)
            if scaled_key != cache_key or not getattr(self, "_source_preview_scaled_bitmap", None):
                draw_bitmap = self.wx_source_image
                if self.wx_source_image.GetWidth() != preview_width \
                        or self.wx_source_image.GetHeight() != preview_height:
                    draw_bitmap = self.wx_source_image.ConvertToImage().Scale(
                        preview_width,
                        preview_height,
                        wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()
                self._source_preview_scaled_bitmap = draw_bitmap
                self._source_preview_scaled_key = cache_key
            dc.DrawBitmap(self._source_preview_scaled_bitmap, 0, 0, True)
            del dc
        self._source_preview_cache_key = cache_key
        if hasattr(self, "source_image_panel"):
            self.source_image_panel.Refresh(False)

    def _make_binding_context(
            self,
            canvas_width: int,
            canvas_height: int) -> BindingContext:
        pose_head_x, pose_head_y, pose_neck_z = self._collect_pose_binding_fields()
        return BindingContext(
            canvas_width=max(1, int(canvas_width)),
            canvas_height=max(1, int(canvas_height)),
            display_offset_x=float(self.display_offset_x),
            display_offset_y=float(self.display_offset_y),
            display_scale=max(0.1, float(self.display_scale)),
            display_rotation_deg=float(self.display_rotation_deg),
            neck_anchor_ratio=self.get_spine_neck_anchor_ratio(),
            body_bind_ray_percent=self.get_spine_body_bind_ray_percent(),
            head_bind_ray_percent=self.get_spine_head_bind_ray_percent(),
            pose_head_x=pose_head_x,
            pose_head_y=pose_head_y,
            pose_neck_z=pose_neck_z,
            body_tilt_opposite_to_head=self.is_body_tilt_opposite_to_head_enabled(),
            body_bind_pos_follow_gain=self.get_body_bind_pos_follow_gain(),
            body_bind_roll_follow_gain=self.get_body_bind_roll_follow_gain(),
            force_full_layer_follow=self.is_layer_force_full_follow_enabled(),
            binding_smoother=self.layer_binding_smoother,
            motion_time_s=time.time(),
        )
    def _select_layer_slot(self, slot_id: Optional[int]) -> None:
        self.basic_layers_state.selected_slot_id = slot_id
        if self._basic_layer_window_visible():
            window = self._get_basic_layer_window()
            if window is not None:
                window.set_single_selection(slot_id)
        self.refresh_layer_blend_status()
        self.persist_basic_layers_state()
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
            self._maybe_schedule_transparent_capture_update(immediate=True)

    def _panel_to_layer_delta(self, dx: int, dy: int, panel_width: int, panel_height: int) -> tuple[float, float]:
        return panel_to_layer_delta(dx, dy, panel_width, panel_height)

    def _hit_test_layer_slot(self, x: int, y: int, canvas_width: int, canvas_height: int) -> Optional[int]:
        if not self.is_layer_blend_enabled():
            return None
        binding_context = self._make_binding_context(canvas_width, canvas_height)
        return LayerCompositor.hit_test_layer_slot(
            self.basic_layers_state,
            self.layer_asset_cache.load_image,
            x,
            y,
            canvas_width,
            canvas_height,
            binding_context)

    def _hit_test_layer_edit(
            self,
            x: int,
            y: int,
            canvas_width: int,
            canvas_height: int) -> tuple[Optional[int], LayerEditMode]:
        # Prefer the exact geometry last drawn as selection chrome so the
        # draggable region matches the on-screen highlight box. Re-resolving
        # would advance the stateful binding smoother (and use a fresh
        # motion_time_s), drifting bound/smoothed layers away from the drawn box
        # so clicks miss and the window drags instead of the layer.
        geom = getattr(self, "_last_edit_chrome_geom", None)
        selected = self._output_edit_slot_id()
        if isinstance(geom, OrbitEditGeometry):
            if (
                    selected is not None
                    and geom.slot_id == int(selected)
                    and geom.canvas_width == int(canvas_width)
                    and geom.canvas_height == int(canvas_height)):
                return hit_test_orbit_edit(geom, x, y)
        if (
                isinstance(geom, tuple)
                and selected is not None
                and geom[0] == int(selected)
                and geom[3] == int(canvas_width)
                and geom[4] == int(canvas_height)):
            return hit_test_resolved_rect(geom[0], geom[1], geom[2], x, y)
        binding_context = self._make_binding_context(canvas_width, canvas_height)
        return hit_test_layer_edit(
            self.basic_layers_state,
            self.layer_asset_cache.load_image,
            x,
            y,
            canvas_width,
            canvas_height,
            binding_context,
            selected_slot_id=self._output_edit_slot_id())

    def _begin_layer_edit(
            self,
            slot_id: int,
            mode: LayerEditMode,
            pos: tuple[int, int],
            canvas_size: tuple[int, int],
            panel: Optional[wx.Window] = None) -> bool:
        if not self.is_layer_blend_enabled():
            return False
        edit_slot = self._output_edit_slot_id()
        if edit_slot is None or edit_slot != slot_id:
            return False
        self._layer_drag_active = True
        self._layer_drag_slot_id = slot_id
        self._layer_edit_mode = mode
        self._layer_drag_last_pos = pos
        self._layer_drag_canvas_size = canvas_size
        self._layer_edit_panel = panel
        # panel is None for the Win32 layered-output edit router (P6): mouse
        # capture is handled by the overlay WNDPROC (SetCapture) instead.
        if panel is not None and not panel.HasCapture():
            panel.CaptureMouse()
        return True

    def begin_layer_edit_at(
            self,
            x: int,
            y: int,
            canvas_width: int,
            canvas_height: int) -> bool:
        """Panel-agnostic edit begin in output-canvas pixel space (for the
        Win32 layered-output overlay). Honors the edit/live gate: only acts on
        the currently selected layer."""
        if not self.is_layer_blend_enabled():
            return False
        if self._output_edit_slot_id() is None:
            return False
        slot_id, mode = self._hit_test_layer_edit(x, y, canvas_width, canvas_height)
        if slot_id is None or mode == LayerEditMode.NONE:
            return False
        return self._begin_layer_edit(
            slot_id, mode, (int(x), int(y)), (int(canvas_width), int(canvas_height)))

    def apply_layer_edit_at(self, x: int, y: int) -> None:
        """Panel-agnostic edit motion in output-canvas pixel space (P6 router)."""
        self._apply_layer_edit_motion((int(x), int(y)))

    def end_layer_edit_external(self) -> None:
        """Panel-agnostic edit end (P6 router)."""
        self._end_layer_edit()

    def _apply_layer_edit_motion(self, pos: tuple[int, int]) -> None:
        if not self._layer_drag_active or self._layer_drag_slot_id is None:
            return
        if self._layer_drag_last_pos is None:
            self._layer_drag_last_pos = pos
            return
        canvas_w, canvas_h = self._layer_drag_canvas_size
        layer = self.basic_layers_state.get_slot(self._layer_drag_slot_id)
        if self._layer_edit_mode == LayerEditMode.ORBIT_MOVE:
            dx = pos[0] - self._layer_drag_last_pos[0]
            dy = pos[1] - self._layer_drag_last_pos[1]
            pivot_layer = resolve_orbit_track_layer(
                self.basic_layers_state, layer)
            apply_orbit_pivot_canvas_delta(
                pivot_layer, float(dx), float(dy), canvas_w, canvas_h)
        elif self._layer_edit_mode == LayerEditMode.SCALE:
            binding_context = self._make_binding_context(canvas_w, canvas_h)
            resolved = resolve_layer_rects(
                self.basic_layers_state,
                self.layer_asset_cache.load_image,
                canvas_w,
                canvas_h,
                binding_context,
                include_motion=False)
            rect = resolved.get(self._layer_drag_slot_id)
            if rect is not None:
                apply_scale_from_drag(layer, float(pos[0]), float(pos[1]), rect)
        else:
            dx = pos[0] - self._layer_drag_last_pos[0]
            dy = pos[1] - self._layer_drag_last_pos[1]
            offset_dx, offset_dy = self._panel_to_layer_delta(dx, dy, canvas_w, canvas_h)
            apply_move_delta(layer, offset_dx, offset_dy)
        self._layer_drag_last_pos = pos
        self.on_layer_state_changed()

    def _end_layer_edit(self) -> None:
        if not self._layer_drag_active:
            return
        self.persist_basic_layers_state()
        self._layer_drag_active = False
        self._layer_drag_slot_id = None
        self._layer_drag_last_pos = None
        self._layer_edit_mode = LayerEditMode.NONE
        panel = self._layer_edit_panel
        self._layer_edit_panel = None
        if panel is not None and panel.HasCapture():
            panel.ReleaseMouse()

    def on_output_panel_left_down(self, event: wx.MouseEvent, panel: wx.Window) -> bool:
        if not self.is_layer_blend_enabled():
            return False
        if self._output_edit_slot_id() is None:
            return False
        pos = event.GetPosition()
        size = panel.GetClientSize()
        slot_id, mode = self._hit_test_layer_edit(
            pos.x, pos.y, size.width, size.height)
        if slot_id is None or mode == LayerEditMode.NONE:
            return False
        return self._begin_layer_edit(
            slot_id, mode, (pos.x, pos.y), (size.width, size.height), panel)

    def on_output_panel_left_up(self, event: wx.MouseEvent, panel: wx.Window) -> bool:
        if not self._layer_drag_active or self._layer_edit_panel is not panel:
            return False
        self._end_layer_edit()
        return True

    def on_output_panel_motion(self, event: wx.MouseEvent, panel: wx.Window) -> bool:
        if not self._layer_drag_active or self._layer_edit_panel is not panel:
            return False
        if not event.Dragging():
            return True
        pos = event.GetPosition()
        self._apply_layer_edit_motion((pos.x, pos.y))
        return True

    def on_layer_char_hook(self, event: wx.Event) -> None:
        if not self.is_layer_blend_enabled():
            event.Skip()
            return
        slot_id = self._output_edit_slot_id()
        if slot_id is None or slot_id < 0:
            event.Skip()
            return
        key_code = event.GetKeyCode()
        step = 10.0 if event.ShiftDown() else 1.0
        dx = dy = 0.0
        if key_code == wx.WXK_LEFT:
            dx = -step
        elif key_code == wx.WXK_RIGHT:
            dx = step
        elif key_code == wx.WXK_UP:
            dy = -step
        elif key_code == wx.WXK_DOWN:
            dy = step
        else:
            event.Skip()
            return
        self.nudge_selected_layer(dx, dy)

    def nudge_selected_layer(self, dx: float, dy: float) -> bool:
        """Panel-agnostic arrow-key nudge of the selected layer (shared by the
        wx char hook and a future Win32 WM_KEYDOWN router). Returns False when
        nothing is selected / layer blend is off."""
        if not self.is_layer_blend_enabled():
            return False
        slot_id = self._output_edit_slot_id()
        if slot_id is None or slot_id < 0:
            return False
        layer = self.basic_layers_state.get_slot(slot_id)
        nudge_layer(layer, dx, dy)
        self.persist_basic_layers_state()
        self.on_layer_state_changed()
        return True

    def draw_nothing_yet_string(self, dc, message: str = "Nothing yet!"):
        canvas_width, canvas_height = dc.GetSize()
        self.clear_result_image_bitmap(canvas_width, canvas_height)
        dc.SelectObject(self.result_image_bitmap)
        font = wx.Font(wx.FontInfo(12).Family(wx.FONTFAMILY_SWISS))
        dc.SetFont(font)
        max_width = max(40, canvas_width - 12)
        wrapped_lines = self._wrap_status_message_lines(dc, message, max_width)
        line_height = dc.GetTextExtent("Ag")[1] + 2
        total_height = len(wrapped_lines) * line_height
        y = max(6, (canvas_height - total_height) // 2)
        for line in wrapped_lines:
            line_w, _line_h = dc.GetTextExtent(line)
            dc.DrawText(line, max(6, (canvas_width - line_w) // 2), y)
            y += line_height

    def _wrap_status_message_lines(self, dc, message: str, max_width: int) -> list[str]:
        message = (message or "").replace("\r\n", "\n").replace("\r", "\n")
        lines: list[str] = []
        for paragraph in message.split("\n"):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            words = paragraph.split(" ")
            current = ""
            for word in words:
                candidate = word if not current else f"{current} {word}"
                if dc.GetTextExtent(candidate)[0] <= max_width:
                    current = candidate
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
        return lines or ["Nothing yet!"]

    def paint_scale_curve_panel(self, event: wx.Event):
        dc = wx.AutoBufferedPaintDC(self.scale_curve_panel)
        width, height = self.scale_curve_panel.GetSize()
        background_color = wx.Colour(250, 250, 250)
        panel_border_color = wx.Colour(188, 188, 188)
        axis_color = wx.Colour(120, 120, 120)
        grid_color = wx.Colour(222, 222, 222)
        curve_color = wx.Colour(52, 120, 246)
        point_fill_color = wx.Colour(220, 68, 68)
        label_color = wx.Colour(50, 50, 50)

        dc.SetBackground(wx.Brush(background_color))
        dc.Clear()
        dc.SetPen(wx.Pen(panel_border_color, width=1))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(0, 0, width, height)

        margin_left = 10
        margin_right = 32
        margin_top = 10
        margin_bottom = 22
        graph_width = max(1, width - margin_left - margin_right)
        graph_height = max(1, height - margin_top - margin_bottom)

        samples = self.get_scale_curve_samples()
        domain_min, domain_max = self.get_scale_curve_domain()
        sampled_scales = [scale_value for _, scale_value in samples]
        current_delta = self.get_scale_curve_current_delta()
        if current_delta is not None:
            current_scale = self.compute_target_scale(
                self.get_scale_curve_neutral_face_size() + current_delta,
                self.get_scale_curve_neutral_face_size())
            sampled_scales.append(current_scale)
        sampled_scales.append(1.0)

        min_scale = min(sampled_scales)
        max_scale = max(sampled_scales)
        scale_padding = max(0.03, (max_scale - min_scale) * 0.10)
        min_scale -= scale_padding
        max_scale += scale_padding
        scale_span = max(0.001, max_scale - min_scale)
        domain_span = max(0.001, domain_max - domain_min)

        def to_canvas(delta_value: float, scale_value: float):
            px = margin_left + int(round(((delta_value - domain_min) / domain_span) * graph_width))
            py = height - margin_bottom - int(round(((scale_value - min_scale) / scale_span) * graph_height))
            return px, py

        dc.SetPen(wx.Pen(grid_color, width=1, style=wx.PENSTYLE_DOT))
        for ratio in (0.25, 0.50, 0.75):
            y = margin_top + int(round(graph_height * ratio))
            dc.DrawLine(margin_left, y, width - margin_right, y)
        for ratio in (0.25, 0.50, 0.75):
            x = margin_left + int(round(graph_width * ratio))
            dc.DrawLine(x, margin_top, x, height - margin_bottom)

        dc.SetPen(wx.Pen(axis_color, width=1))
        dc.DrawLine(margin_left, height - margin_bottom, width - margin_right, height - margin_bottom)
        dc.DrawLine(width - margin_right, margin_top, width - margin_right, height - margin_bottom)

        dc.SetPen(wx.Pen(panel_border_color, width=1, style=wx.PENSTYLE_DOT))
        if domain_min <= 0.0 <= domain_max:
            zero_x, _ = to_canvas(0.0, min_scale)
            dc.DrawLine(zero_x, margin_top, zero_x, height - margin_bottom)
        if min_scale <= 1.0 <= max_scale:
            _, one_y = to_canvas(domain_min, 1.0)
            dc.DrawLine(margin_left, one_y, width - margin_right, one_y)
        peak_shift = self.scale_curve_peak_shift_spin.GetValue()
        if domain_min <= peak_shift <= domain_max:
            peak_x, _ = to_canvas(peak_shift, min_scale)
            dc.SetPen(wx.Pen(wx.Colour(180, 120, 70), width=1, style=wx.PENSTYLE_DOT))
            dc.DrawLine(peak_x, margin_top, peak_x, height - margin_bottom)

        points = [to_canvas(delta_value, scale_value) for delta_value, scale_value in samples]
        dc.SetPen(wx.Pen(curve_color, width=2))
        dc.DrawLines(points)

        if current_delta is not None:
            current_delta = max(domain_min, min(domain_max, current_delta))
            current_scale = self.compute_target_scale(
                self.get_scale_curve_neutral_face_size() + current_delta,
                self.get_scale_curve_neutral_face_size())
            point_x, point_y = to_canvas(current_delta, current_scale)
            dc.SetBrush(wx.Brush(point_fill_color))
            dc.SetPen(wx.Pen(point_fill_color, width=1))
            dc.DrawCircle(point_x, point_y, 4)

        dc.SetTextForeground(label_color)
        dc.DrawText("远 / Far", margin_left, height - margin_bottom + 2)
        dc.DrawText("近 / Near", width - margin_right - 32, height - margin_bottom + 2)
        small_label = "小 / Small"
        large_label = "大 / Large"
        small_w, _ = dc.GetTextExtent(small_label)
        large_w, _ = dc.GetTextExtent(large_label)
        dc.DrawText(small_label, width - margin_right - small_w, height - margin_bottom - 10)
        dc.DrawText(large_label, width - margin_right - large_w, margin_top)

    def get_output_background_color(self) -> Optional[wx.Colour]:
        return wx.Colour(self.get_output_background_hex())

    def create_composition_bitmap(self, width: int, height: int) -> wx.Bitmap:
        width = max(1, int(width))
        height = max(1, int(height))
        background_color = self.get_output_background_color()
        rgba = numpy.zeros((height, width, 4), dtype=numpy.uint8)
        rgba[:, :, 0] = background_color.Red()
        rgba[:, :, 1] = background_color.Green()
        rgba[:, :, 2] = background_color.Blue()
        rgba[:, :, 3] = 255
        return wx.Bitmap.FromBufferRGBA(width, height, rgba.tobytes())

    @staticmethod
    def create_transparent_composition_bitmap(width: int, height: int) -> wx.Bitmap:
        """Character-only buffer for layer post-process (no output background baked in)."""
        width = max(1, int(width))
        height = max(1, int(height))
        rgba = numpy.zeros((height, width, 4), dtype=numpy.uint8)
        return MainFrame.create_rgba_bitmap_from_array(width, height, rgba)

    def render_pose_to_wx_image(self, pose_list: List[float]) -> Optional[wx.Image]:
        if self.poser is None or self.torch_source_image is None:
            return None

        pose = torch.tensor(pose_list, device=self.device, dtype=self.poser.get_dtype())

        use_half = self.get_tha_infer_fp16_enabled()
        try:
            with torch.no_grad():
                if use_half and torch.cuda.is_available():
                    with torch.cuda.amp.autocast(dtype=torch.float16):
                        output_image = self.poser.pose(self.torch_source_image, pose)[0].float()
                else:
                    output_image = self.poser.pose(self.torch_source_image, pose)[0].float()
                if torch.isnan(output_image).any() or torch.isinf(output_image).any():
                    raise ValueError("FP16 NaN/Inf")
        except Exception:
            if use_half:
                self._tha_infer_fp16_fallback = True
                self._warn_enhancement_once(
                    "FP16 inference unstable; falling back to FP32 for this session.")
                with torch.no_grad():
                    output_image = self.poser.pose(self.torch_source_image, pose)[0].float()
            else:
                raise

        with torch.no_grad():
            output_image = torch.clip((output_image + 1.0) / 2.0, 0.0, 1.0)
            output_image = convert_linear_to_srgb(output_image)

            c, h, w = output_image.shape
            output_image = 255.0 * torch.transpose(output_image.reshape(c, h * w), 0, 1).reshape(h, w, c)
            output_image = output_image.byte()

        numpy_image = output_image.detach().cpu().numpy()
        return wx.ImageFromBuffer(numpy_image.shape[1],
                                  numpy_image.shape[0],
                                  numpy_image[:, :, 0:3].tobytes(),
                                  numpy_image[:, :, 3].tobytes())

    def draw_cached_result_image(
            self,
            banner_text: Optional[str] = None,
            *,
            push_capture: bool = False):
        if self.last_output_wx_image is None:
            return
        use_fast_affine = not self.is_layer_blend_enabled()
        self.draw_result_wx_image(
            self.last_output_wx_image,
            banner_text,
            fast_affine_only=use_fast_affine)
        if push_capture:
            self._maybe_schedule_transparent_capture_update(immediate=True)

    def _get_antialias_factor(self) -> float:
        return get_antialias_factor_from_control(getattr(self, "antialias_strength_spin", None))

    def _keyframe_cache_valid(self, wx_image: wx.Image, antialias_factor: float) -> bool:
        return self.output_enhancement.keyframe_cache.is_valid(wx_image, antialias_factor)

    def _update_keyframe_cache(self, wx_image: wx.Image, antialias_factor: float) -> None:
        self.output_enhancement.keyframe_cache.update(
            wx_image,
            antialias_factor,
            wx_to_rgba=capture_wx_image_to_rgba_array,
            create_bitmap=self.create_rgba_bitmap_from_array)

    def _compose_character_rgba_from_keyframe(
            self,
            canvas_width: int,
            canvas_height: int,
            antialias_factor: float) -> numpy.ndarray:
        keyframe_rgba = self.output_enhancement.keyframe_cache.rgba
        if keyframe_rgba is None:
            raise RuntimeError("keyframe rgba cache missing")
        canvas_width = max(1, int(canvas_width))
        canvas_height = max(1, int(canvas_height))
        return compose_character_rgba_from_keyframe(
            keyframe_rgba,
            canvas_width,
            canvas_height,
            anchor_x=(canvas_width / 2.0 + self.display_offset_x),
            anchor_y=(canvas_height + self.display_offset_y),
            scale=max(0.1, self.display_scale),
            rotation_deg=self.display_rotation_deg,
            antialias_factor=antialias_factor)

    def _compose_character_bitmap_from_keyframe(
            self,
            canvas_width: int,
            canvas_height: int,
            antialias_factor: float) -> wx.Bitmap:
        rgba = self._compose_character_rgba_from_keyframe(
            canvas_width, canvas_height, antialias_factor)
        if self.get_output_background_mode() in (
                OUTPUT_BACKGROUND_TRANSPARENT, OUTPUT_BACKGROUND_TRANSPARENT_CAPTURE):
            rgba = sanitize_transparent_rgb(rgba)
        return self.create_rgba_bitmap_from_array(canvas_width, canvas_height, rgba)

    def _needs_obs_alpha_sanitize(self) -> bool:
        return self.get_output_background_mode() == OUTPUT_BACKGROUND_TRANSPARENT

    def _can_present_character_fast(self, *, fast_affine_only: bool, layer_blend: bool) -> bool:
        return fast_affine_only and not layer_blend

    def _get_cached_background_rgba(self, canvas_width: int, canvas_height: int) -> numpy.ndarray:
        signature = self.get_output_background_signature()
        cached = self._cached_background_rgba
        if (self._cached_background_signature == signature
                and cached is not None
                and cached.shape[0] == canvas_height
                and cached.shape[1] == canvas_width):
            return cached
        rgba = self.build_output_background_rgba(canvas_width, canvas_height)
        self._cached_background_signature = signature
        self._cached_background_rgba = rgba
        return rgba

    def _sanitize_result_bitmap_once(self) -> None:
        if not self.result_image_bitmap.IsOk():
            return
        image = self.result_image_bitmap.ConvertToImage()
        if not image.HasAlpha():
            return
        width = max(1, image.GetWidth())
        height = max(1, image.GetHeight())
        rgba = self.wx_image_to_rgba_array(image)
        transparent = rgba[:, :, 3] == 0
        if not numpy.any(transparent):
            return
        rgba[transparent, 0:3] = 0
        self.result_image_bitmap = self.create_rgba_bitmap_from_array(width, height, rgba)

    def _compose_present_rgba(
            self, canvas_width: int, canvas_height: int) -> Optional[numpy.ndarray]:
        """Single wx-free composite shared by on-screen present and transparent
        capture: enhanced character + layer stack on a transparent background,
        with the edit chrome (selection box/handle) overlaid when a layer is
        selected. Returns straight RGBA, or None when no keyframe is cached yet.

        The unified ULW output is the only output window now, so the mode
        background (color/image/黑键) is composited UNDER the character here.
        真透 (transparent_capture) returns None from the background builder, so
        the foreground stays per-pixel transparent for desktop-transparent output.
        """
        t0 = time.perf_counter()
        fg = self.compose_output_stack_rgba(canvas_width, canvas_height)
        if fg is None:
            return None
        t_stack = time.perf_counter()
        chrome = self.compose_edit_chrome_rgba(canvas_width, canvas_height)
        if chrome is not None:
            fg = self.sanitize_rgba_alpha_fringe(composite_rgba_arrays(fg, chrome))
        t_chrome = time.perf_counter()
        background = self._compose_ulw_background_rgba(canvas_width, canvas_height)
        if background is not None:
            fg = composite_rgba_arrays(background, fg)
        t_bg = time.perf_counter()
        stages = dict(getattr(self, "_compose_stack_substages", {}) or {})
        stages["stack_total"] = (t_stack - t0) * 1000.0
        stages["chrome"] = (t_chrome - t_stack) * 1000.0
        stages["bg"] = (t_bg - t_chrome) * 1000.0
        self._last_present_stages = stages
        return fg

    def _draw_banner_on_result_bitmap(
            self, banner_text: str, canvas_width: int, canvas_height: int) -> None:
        if not self.result_image_bitmap.IsOk():
            return
        dc = wx.MemoryDC()
        dc.SelectObject(self.result_image_bitmap)
        font = wx.Font(wx.FontInfo(11).Family(wx.FONTFAMILY_SWISS).Weight(wx.FONTWEIGHT_BOLD))
        dc.SetFont(font)
        dc.SetTextForeground(wx.Colour(255, 220, 0))
        dc.SetBackgroundMode(wx.TRANSPARENT)
        _tw, th = dc.GetTextExtent(banner_text)
        dc.DrawText(banner_text, 8, canvas_height - th - 8)
        del dc

    def _present_character_bitmap(
            self,
            character_bitmap: Optional[wx.Bitmap],
            canvas_width: int,
            canvas_height: int,
            banner_text: Optional[str],
            *,
            fast_affine_only: bool = False) -> None:
        present_t0 = time.perf_counter()
        present_rgba = self._compose_present_rgba(canvas_width, canvas_height)
        if present_rgba is None:
            if character_bitmap is not None and character_bitmap.IsOk():
                present_rgba = self.sanitize_rgba_alpha_fringe(
                    self.wx_bitmap_to_rgba_array(character_bitmap, preserve_color=True))
            else:
                present_rgba = numpy.zeros(
                    (canvas_height, canvas_width, 4), dtype=numpy.uint8)
        present_rgba = self._apply_present_enhancement(present_rgba)
        self._cached_present_rgba = present_rgba
        self.last_banner_text = banner_text
        self.last_background_choice = self.get_output_background_signature()
        if fast_affine_only:
            self._note_cached_affine_present_time()
        # The layered ULW is now the only output window in every mode (OutputFrame
        # is retired/hidden) and it is fed straight from _cached_present_rgba, so
        # the wx.Bitmap rebuild + banner DC + OutputFrame chrome/panel refresh are
        # pure waste on the hot path. Skip them entirely while the ULW is the output.
        if not self.is_ulw_output_enabled():
            self.result_image_bitmap = self.create_rgba_bitmap_from_array(
                canvas_width, canvas_height, present_rgba)
            if banner_text:
                self._draw_banner_on_result_bitmap(banner_text, canvas_width, canvas_height)
            background_signature = self.get_output_background_signature()
            if background_signature != self._last_chrome_background_signature:
                self.refresh_output_frame_chrome()
                self._last_chrome_background_signature = background_signature
            self._notify_output_panel_refresh()
        _perf_record(
            present_ms=(time.perf_counter() - present_t0) * 1000.0,
            fast_present=fast_affine_only,
            stages=getattr(self, "_last_present_stages", None))

    def draw_result_wx_image(
            self,
            wx_image: wx.Image,
            banner_text: Optional[str] = None,
            *,
            fast_affine_only: bool = False,
            push_capture: bool = False):
        self.ensure_result_bitmap_size()
        canvas_width, canvas_height = self.get_output_canvas_size()
        antialias_factor = self._get_antialias_factor()
        background_signature = self.get_output_background_signature()
        if self.last_background_choice != background_signature:
            self._cached_background_signature = None
            self._cached_background_rgba = None

        if fast_affine_only:
            compose_signature = self._get_compose_signature(wx_image, antialias_factor)
            if compose_signature == self._last_compose_signature:
                return
            self._last_compose_signature = compose_signature

        cache_valid = self._keyframe_cache_valid(wx_image, antialias_factor)
        if fast_affine_only and not cache_valid:
            fast_affine_only = False
        if not cache_valid:
            self._update_keyframe_cache(wx_image, antialias_factor)

        self._last_compose_signature = self._get_compose_signature(wx_image, antialias_factor)
        self._present_character_bitmap(
            None, canvas_width, canvas_height, banner_text,
            fast_affine_only=fast_affine_only)
        # ULW is the sole on-screen output in transparent mode, so every actual
        # present (new THA pose, affine smoothing, layer change) must feed it.
        # Throttled to the display cap; no-op when transparent capture is off.
        if push_capture:
            self._maybe_schedule_transparent_capture_update(immediate=True)
        else:
            self._maybe_schedule_transparent_capture_update()

    def render_pose_to_result_bitmap(self, pose_list: List[float], banner_text: Optional[str] = None):
        self._note_pose_present_time()
        wx_image = self.render_pose_to_wx_image(pose_list)
        if wx_image is None:
            return

        self.last_pose = pose_list
        self.last_output_wx_image = wx_image
        self.last_background_choice = self.get_output_background_signature()
        self.draw_result_wx_image(
            wx_image,
            banner_text,
            fast_affine_only=not self.is_layer_blend_enabled())
        self.output_enhancement.pose_interpolation.seed_after_real_infer(pose_list)
        self._note_inference_fps_tick()

    def render_default_pose_load_preview(self):
        default_pose = self.get_default_pose_list()
        self.last_pose = default_pose
        self.render_pose_to_result_bitmap(default_pose, MainFrame.LOAD_PREVIEW_BANNER)
        self._load_preview_shown = True
        if hasattr(self, "fps_text"):
            self.set_wrapped_static_text_if_changed(
                self.fps_text, "预览 / Preview\nNo face input")

    def tick_tha4_student_source(self) -> Optional[str]:
        if self.poser is None:
            return "no_model"

        if self.mediapipe_face_pose is None:
            return "no_face"

        current_pose = self._resolve_mocap_pose_for_render(self.mediapipe_face_pose)
        if self.torch_source_image is None:
            return "no_model"

        background_changed = self.last_background_choice != self.get_output_background_signature()
        if self.last_output_wx_image is None or background_changed:
            need_infer = True
        elif self.last_pose is None:
            with self._infer_lock:
                need_infer = not self._infer_worker_active
        else:
            need_infer = self.should_infer_pose(self.last_pose, current_pose)

        if need_infer:
            infer_pose = self.resolve_scheduled_infer_pose(current_pose)
            self.schedule_async_pose_infer(infer_pose)

        if self.last_banner_text is not None:
            self.last_banner_text = None

        return "tick"

    def _get_compose_signature(
            self,
            wx_image: wx.Image,
            antialias_factor: float) -> tuple:
        edge_colour = self.get_character_edge_colour()
        return (
            id(wx_image),
            round(antialias_factor, 4),
            round(self.display_offset_x, 2),
            round(self.display_offset_y, 2),
            round(self.display_scale, 4),
            round(self.display_rotation_deg, 2),
            self.get_output_background_signature(),
            self.get_character_edge_mode(),
            round(self.get_character_edge_width(), 3),
            edge_colour.Red(),
            edge_colour.Green(),
            edge_colour.Blue(),
        )

    def _cached_affine_compose_signature(self) -> Optional[tuple]:
        if self.last_output_wx_image is None:
            return None
        return self._get_compose_signature(
            self.last_output_wx_image, self._get_antialias_factor())

    def _cached_affine_visual_unchanged(self) -> bool:
        signature = self._cached_affine_compose_signature()
        return signature is not None and signature == self._last_compose_signature

    def _blit_output_background_to_dc(
            self,
            dc: wx.DC,
            canvas_width: int,
            canvas_height: int) -> None:
        if self.get_output_background_mode() == OUTPUT_BACKGROUND_IMAGE:
            background_rgba = self._get_cached_background_rgba(canvas_width, canvas_height)
            background_bitmap = self.create_rgba_bitmap_from_array(
                canvas_width, canvas_height, background_rgba)
            dc.DrawBitmap(background_bitmap, 0, 0, True)
            return
        self.paint_output_background(dc, wx.Size(canvas_width, canvas_height))

    def _notify_output_panel_refresh(self) -> None:
        output_frame = getattr(self, "output_frame", None)
        if output_frame is not None and output_frame.IsShown():
            output_frame.result_image_panel.Refresh(False)


    def _present_smooth_output_frame(self) -> None:
        if not self.is_model_loaded() or self.last_output_wx_image is None:
            return
        if self._cached_affine_visual_unchanged():
            return
        if not self.should_refresh_cached_affine():
            return
        self.draw_cached_result_image(self.last_banner_text)
        self._maybe_schedule_transparent_capture_update()

    def on_display_timer(self, event: Optional[wx.Event] = None):
        self.poll_layer_gif_playback_side_effects()
        if self.is_model_loaded():
            self.update_display_transform_state()
        motion_active = (
            self.is_layer_blend_enabled()
            and basic_layers_state_has_active_motion(self.basic_layers_state)
            and self.last_output_wx_image is not None)
        if motion_active:
            # Single full composite per tick (avoids duplicate draw when affine also changed).
            self.draw_cached_result_image(self.last_banner_text)
            self._maybe_schedule_transparent_capture_update()
        else:
            self._present_smooth_output_frame()
        pipe = getattr(self, "output_enhancement", None)
        if pipe is not None and pipe.has_pending_rife() and self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
            self._maybe_schedule_transparent_capture_update(immediate=True)

    def on_ui_anim_timer(self, event: Optional[wx.Event] = None):
        """Drive continuously-refreshing animated UI (controls + layer window) at a
        capped 25 fps. The output window present stays on display_timer and is not
        throttled here."""
        if getattr(self, "_is_closing", False):
            return
        self._refresh_fps_display()
        if self._scale_curve_dirty:
            self._scale_curve_dirty = False
            self.refresh_scale_curve_status()
            self.request_scale_curve_repaint(force=True)
        if self._basic_layer_window_visible():
            window = self._get_basic_layer_window()
            if window is not None:
                window.refresh_spine_diagram()

    def on_infer_tick(self, event: Optional[wx.Event] = None):
        if getattr(self.pose_converter, "refresh_audio_input_runtime", None) is not None:
            if self.is_mouse_audio_mocap_mode():
                if self.is_model_loaded():
                    self.pose_converter.refresh_audio_input_runtime(time.time())
            elif self.is_model_loaded() and self.get_image_source_mode() == IMAGE_SOURCE_THA4 and (
                    self.poser is None or self.mediapipe_face_pose is None):
                self.pose_converter.refresh_audio_input_runtime(time.time())
        self.active_image_source.tick(self)

    def update_result_image_bitmap(self, event: Optional[wx.Event] = None):
        """Legacy entry: run both display refresh and infer scheduling."""
        self.on_display_timer()
        self.on_infer_tick()

    def load_model_from_path(self, character_model_json_file_name: str) -> bool:
        resolved_path = self.resolve_character_model_path(character_model_json_file_name)
        if not resolved_path or not os.path.isfile(resolved_path):
            invalid_path = character_model_json_file_name
            self.refresh_model_loaded_ui_state()
            message_dialog = wx.MessageDialog(
                self.get_dialog_parent(),
                "找不到角色模型文件 / Character model file not found:\n%s" % invalid_path,
                "Load THA4 Student Model",
                wx.OK | wx.ICON_WARNING)
            message_dialog.ShowModal()
            message_dialog.Destroy()
            return False

        if self.get_image_source_mode() != IMAGE_SOURCE_THA4:
            switch_image_source(self, IMAGE_SOURCE_THA4, autoload_asset=False)

        latest_face_screen_motion = None if self.latest_face_screen_motion is None else FaceScreenMotion(
            center_x=self.latest_face_screen_motion.center_x,
            center_y=self.latest_face_screen_motion.center_y,
            face_size=self.latest_face_screen_motion.face_size)
        latest_head_roll_deg = self.latest_head_roll_deg
        last_face_detected_time = self.last_face_detected_time
        try:
            self.character_model = CharacterModel.load(resolved_path)
            self.torch_source_image = self.character_model.get_character_image(self.device)
            pil_image = resize_PIL_image(
                PIL.Image.open(self.character_model.character_image_file_name),
                (MainFrame.IMAGE_SIZE, MainFrame.IMAGE_SIZE))
            w, h = pil_image.size
            self.wx_source_image = wx.Bitmap.FromBufferRGBA(w, h, pil_image.convert("RGBA").tobytes())
            self._invalidate_source_preview_cache()
            self.update_source_image_bitmap(force=True)
            self.poser = self.character_model.get_poser(self.device)
            apply_poser_precision(self.poser, self.get_tha_infer_fp16_enabled())
            self.refresh_model_loaded_ui_state()
            self.last_loaded_model_path = resolved_path
            self.update_load_model_buttons()
            self.save_persistent_ui_state()
            self.mediapipe_face_pose = None
            self.last_pose = None
            self._last_pose_infer_time_ns = None
            self._last_cached_affine_present_time_ns = None
            with self._infer_lock:
                self._pending_infer_pose = None
                self._infer_worker_active = False
            self._input_frame_times = []
            self._input_fps = 0.0
            self._inference_complete_times = []
            self._inference_fps = 0.0
            self._last_actual_output_present_mono = None
            self._output_present_times = []
            self._output_fps_last_commit_mono = 0.0
            self._display_out_fps = 0.0
            self._load_preview_shown = False
            self.last_output_wx_image = None
            self.last_banner_text = None
            self._invalidate_render_caches()
            self.layer_binding_smoother.reset_all()
            self.head_binding_pose_filter.reset()
            self._last_compose_signature = None
            self.last_background_choice = self.get_output_background_signature()
            self.reset_frame_interpolation_buffers()
            self.latest_face_screen_motion = latest_face_screen_motion
            self.neutral_face_screen_motion = None
            self.latest_head_roll_deg = latest_head_roll_deg
            self.neutral_head_roll_deg = 0.0
            self.last_face_detected_time = last_face_detected_time
            self.last_direction_calibration_time = None
            self.last_scale_calibration_time = None
            self.display_offset_x = 0.0
            self.display_offset_y = 0.0
            self.display_scale = 1.0
            self.display_rotation_deg = 0.0
            self.apply_enabled_auto_calibration_on_load(
                latest_face_screen_motion, last_face_detected_time)
            self.refresh_auto_transform_status("READY" if self.enable_auto_transform_checkbox.GetValue() else "OFF")
        except Exception as exc:
            _err_record(
                "H-LOAD",
                "character_model_mediapipe_puppeteer_load_preview.py:load_model_from_path",
                exc,
                data={"model_path": resolved_path})
            self.refresh_model_loaded_ui_state()
            message_dialog = wx.MessageDialog(
                self.get_dialog_parent(),
                "无法加载 THA4 Student 模型 / Could not load character model:\n%s\n\n%s: %s"
                % (resolved_path, type(exc).__name__, exc),
                "Load THA4 Student Model",
                wx.OK | wx.ICON_ERROR)
            message_dialog.ShowModal()
            message_dialog.Destroy()
            return False
        try:
            self.render_default_pose_load_preview()
        except Exception as exc:
            _err_record(
                "H-LOAD",
                "character_model_mediapipe_puppeteer_load_preview.py:render_default_pose_load_preview",
                exc)
        if hasattr(self, "source_image_panel"):
            self.source_image_panel.Update()
        if getattr(self, "output_frame", None) is not None and self.output_frame:
            self.output_frame.result_image_panel.Update()
        self.refresh_basic_layer_window_if_visible()
        return True

    def load_model(self, event: wx.Event):
        self.refresh_and_autoload_video_source()
        dir_name = self.get_default_character_models_dir()
        if not os.path.isdir(dir_name):
            dir_name = ""
        file_dialog = wx.FileDialog(
            self.get_dialog_parent(),
            "Choose a THA4 Student character_model.yaml",
            dir_name,
            "",
            "YAML files (*.yaml)|*.yaml",
            wx.FD_OPEN)
        if file_dialog.ShowModal() == wx.ID_OK:
            character_model_json_file_name = os.path.join(file_dialog.GetDirectory(), file_dialog.GetFilename())
            self.load_model_from_path(character_model_json_file_name)
        file_dialog.Destroy()

    def load_last_model(self, event: wx.Event):
        self.refresh_and_autoload_video_source()
        if not self.last_loaded_model_path:
            return
        resolved_path = self.resolve_character_model_path(self.last_loaded_model_path)
        if not resolved_path or not os.path.isfile(resolved_path):
            invalid_path = self.last_loaded_model_path
            self.last_loaded_model_path = None
            self.update_load_model_buttons()
            self.save_persistent_ui_state()
            message_dialog = wx.MessageDialog(
                self.get_dialog_parent(),
                "上次模型路径已失效，请重新选择模型：\n%s\n\nLast model path is no longer valid. Please choose a model again." % invalid_path,
                "Load Last Model",
                wx.OK | wx.ICON_WARNING)
            message_dialog.ShowModal()
            message_dialog.Destroy()
            return
        self.load_model_from_path(resolved_path)

def resolve_mediapipe_face_landmarker_model_path() -> str:
    task = resolve_mediapipe_task_path(get_portable_root())
    if task is not None:
        return str(task.resolve())
    relative = Path("data/thirdparty/mediapipe/face_landmarker_v2_with_blendshapes.task")
    repo_root = find_repo_root(Path(_EXPERIMENT_DIR))
    return str((get_demo_root(repo_root) / relative).resolve())


def create_face_landmarker():
    """Create FaceLandmarker; prefer GPU delegate with CPU fallback."""
    mediapipe = get_mediapipe_module()
    model_path = resolve_mediapipe_face_landmarker_model_path()
    landmarker_options_kwargs = dict(
        running_mode=mediapipe.tasks.vision.RunningMode.VIDEO,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
        num_faces=1,
    )
    delegates = (
        mediapipe.tasks.BaseOptions.Delegate.GPU,
        mediapipe.tasks.BaseOptions.Delegate.CPU,
    )
    last_error: Optional[Exception] = None
    for delegate in delegates:
        try:
            base_options = mediapipe.tasks.BaseOptions(
                model_asset_path=model_path,
                delegate=delegate,
            )
            options = mediapipe.tasks.vision.FaceLandmarkerOptions(
                base_options=base_options,
                **landmarker_options_kwargs,
            )
            landmarker = mediapipe.tasks.vision.FaceLandmarker.create_from_options(options)
            label = "GPU" if delegate == mediapipe.tasks.BaseOptions.Delegate.GPU else "CPU"
            print(f"MediaPipe FaceLandmarker using {label} delegate.", file=sys.stderr)
            return landmarker
        except Exception as exc:
            last_error = exc
            if delegate == mediapipe.tasks.BaseOptions.Delegate.CPU:
                break
            print(
                f"MediaPipe GPU delegate unavailable ({exc}); falling back to CPU.",
                file=sys.stderr,
            )
    if last_error is not None:
        raise last_error
    raise RuntimeError("Failed to create MediaPipe FaceLandmarker")


if __name__ == "__main__":
    try:
        _main_t0 = time.perf_counter()
        _install_debug_excepthook()
        set_windows_app_user_model_id()
        os.environ.setdefault("GLOG_minloglevel", "3")
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        print("THA4 Load Preview script:", os.path.abspath(__file__), file=sys.stderr)
        print("Using device:", device, file=sys.stderr)
        _startup_record(
            "main (imports done, before MainFrame)",
            (time.perf_counter() - _main_t0) * 1000.0)

        pose_converter = MediaPoseFacePoseConverter00()

        face_landmarker = None

        video_capture = None

        app = wx.App()
        wx.DisableAsserts()
        main_frame = MainFrame(pose_converter, video_capture, face_landmarker, device)
        main_frame.capture_timer.Start(MainFrame.CAPTURE_IDLE_INTERVAL_MS)
        main_frame.display_timer.Start(MainFrame.DISPLAY_PRESENT_INTERVAL_MS)
        main_frame.animation_timer.Start(33)
        main_frame.ui_anim_timer.Start(MainFrame.UI_ANIM_REFRESH_INTERVAL_MS)
        app.MainLoop()
    except Exception:
        raise
