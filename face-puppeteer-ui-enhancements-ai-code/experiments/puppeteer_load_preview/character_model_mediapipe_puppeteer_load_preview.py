# Experimental copy: render one default-pose frame right after Load Model (no camera required).
# Original: talking-head-anime-4-demo/src/tha4/app/character_model_mediapipe_puppeteer.py
import math
import os
import sys
import inspect
import threading
import time
import json
from dataclasses import dataclass
from typing import Optional, List
import PIL.Image

os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

import cv2
import mediapipe
import numpy
from scipy.spatial.transform import Rotation

from tha4.shion.base.image_util import resize_PIL_image
from tha4.charmodel.character_model import CharacterModel
from tha4.image_util import convert_linear_to_srgb
from tha4.mocap.mediapipe_constants import HEAD_ROTATIONS, HEAD_X, HEAD_Y, HEAD_Z, BLENDSHAPE_NAMES
from tha4.mocap.mediapipe_face_pose import MediaPipeFacePose
from tha4.mocap.mediapipe_face_pose_converter_00 import MediaPoseFacePoseConverter00

sys.path.append(os.getcwd())

import torch
import wx

from external_layer_output_bridge import ExternalLayerOutputBridge

_EXPERIMENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _EXPERIMENT_DIR not in sys.path:
    sys.path.insert(0, _EXPERIMENT_DIR)

from image_sources.factory import create_image_source, switch_image_source
from image_sources.base import normalize_image_source_mode
from tha3_paths import IMAGE_SOURCE_THA3, IMAGE_SOURCE_THA4, THA3_VARIANT_CHOICES

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


class OutputFrame(wx.Frame):
    def __init__(self, owner_main_frame: "MainFrame"):
        super().__init__(None, wx.ID_ANY, "THA4 Output / 输出", style=wx.BORDER_NONE)
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

    def on_erase_background(self, event: wx.Event):
        pass

    def paint_result_image_panel(self, event: wx.Event):
        owner = self.owner_main_frame
        dc = wx.AutoBufferedPaintDC(self.result_image_panel)
        owner.paint_output_background(dc, self.result_image_panel.GetClientSize())
        if owner.result_image_bitmap.IsOk():
            dc.DrawBitmap(owner.result_image_bitmap, 0, 0, False)

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
        self._dragging = True
        self._drag_start_screen = self.ClientToScreen(event.GetPosition())
        self._drag_start_frame = self.GetPosition()
        if not self.result_image_panel.HasCapture():
            self.result_image_panel.CaptureMouse()
        event.Skip()

    def on_left_up(self, event: wx.MouseEvent):
        self._dragging = False
        if self.result_image_panel.HasCapture():
            self.result_image_panel.ReleaseMouse()
        self.owner_main_frame.schedule_output_frame_geometry_sync(redraw=False)
        event.Skip()

    def on_mouse_move(self, event: wx.MouseEvent):
        if self._dragging and event.LeftIsDown():
            current_screen = self.ClientToScreen(event.GetPosition())
            delta = current_screen - self._drag_start_screen
            self.Move(self._drag_start_frame + delta)
        event.Skip()


class ControlsFrame(wx.Frame):
    def __init__(self, owner_main_frame: "MainFrame"):
        super().__init__(None, wx.ID_ANY, "THA4 MediaPipe Puppeteer [Full Controls]")
        self.owner_main_frame = owner_main_frame
        self.SetDoubleBuffered(True)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_SIZE, self.on_geometry_changed)
        self.Bind(wx.EVT_MOVE, self.on_geometry_changed)
        self.Bind(wx.EVT_ACTIVATE, self.on_activate)

    def on_geometry_changed(self, event: wx.Event):
        if isinstance(event, wx.SizeEvent):
            wx.CallAfter(self.owner_main_frame.handle_controls_frame_resized)
        self.owner_main_frame.schedule_window_geometry_save()
        event.Skip()

    def on_activate(self, event: wx.Event):
        # Avoid Raise() feedback loops on some window managers.
        event.Skip()

    def on_close(self, event: wx.Event):
        if getattr(self.owner_main_frame, "_is_closing", False):
            self.Destroy()
            event.Skip()
            return
        self.owner_main_frame.Close()
        event.Veto()


class WebcamPreviewPopupFrame(wx.Frame):
    POPUP_CLIENT_WIDTH = 640
    POPUP_CLIENT_HEIGHT = 480

    def __init__(self, owner_main_frame: "MainFrame"):
        super().__init__(None, wx.ID_ANY, "Webcam Preview / 摄像头预览")
        self.owner_main_frame = owner_main_frame
        self.SetDoubleBuffered(True)

        popup_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(popup_sizer)
        self.SetAutoLayout(1)

        self.preview_panel = wx.Panel(
            self,
            size=(WebcamPreviewPopupFrame.POPUP_CLIENT_WIDTH, WebcamPreviewPopupFrame.POPUP_CLIENT_HEIGHT),
            style=wx.SIMPLE_BORDER)
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

    @staticmethod
    def on_erase_background(event: wx.Event):
        pass

    def on_paint_preview_panel(self, event: wx.Event):
        dc = wx.BufferedPaintDC(self.preview_panel)
        panel_size = self.preview_panel.GetClientSize()
        source_bitmap = self.owner_main_frame.webcam_capture_bitmap
        source_size = source_bitmap.GetSize()
        if panel_size.x <= 0 or panel_size.y <= 0 or source_size.x <= 0 or source_size.y <= 0:
            return

        scale = min(panel_size.x / source_size.x, panel_size.y / source_size.y)
        draw_w = max(1, int(source_size.x * scale))
        draw_h = max(1, int(source_size.y * scale))
        draw_x = (panel_size.x - draw_w) // 2
        draw_y = (panel_size.y - draw_h) // 2
        dc.Clear()
        dc.DrawBitmap(source_bitmap, draw_x, draw_y, True)
        dc.SetPen(wx.Pen(wx.Colour(80, 80, 80)))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(draw_x, draw_y, draw_w, draw_h)

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
    WEBCAM_PREVIEW_WIDTH = 256
    WEBCAM_PREVIEW_HEIGHT = 192
    MAX_CAMERA_PROBE_INDEX = 19
    VIDEO_SOURCE_COLUMN_MIN_WIDTH = 260
    RIGHT_SIDEBAR_MIN_WIDTH = 440
    DEFAULT_OUTPUT_SIZE = int(IMAGE_SIZE * 1.5)
    LOCKED_OUTPUT_CLIENT_WIDTH = DEFAULT_OUTPUT_SIZE
    LOCKED_OUTPUT_CLIENT_HEIGHT = DEFAULT_OUTPUT_SIZE
    LOAD_PREVIEW_BANNER = "DEFAULT POSE (model loaded)"
    AUTO_TRANSFORM_HOLD_SECONDS = 0.75
    SCALE_CURVE_DELTA_RANGE = 0.22
    UI_STATE_FILE_NAME = "load_preview_ui_state.json"
    CONTROLS_MIN_CLIENT_WIDTH = 720
    CONTROLS_MIN_CLIENT_HEIGHT = 520
    CONTROLS_MAX_CLIENT_HEIGHT = 1400
    COMPACT_MIN_CLIENT_WIDTH = 260
    COMPACT_MIN_CLIENT_HEIGHT = 180
    DEBUG_LOG_PATH = r"F:\aidraw\debug-5a7b76.log"
    CAPTURE_PROCESS_INTERVAL_MS = 33
    CAPTURE_PREVIEW_INTERVAL_MS = 66
    CAPTURE_IDLE_INTERVAL_MS = 400
    HOVER_HELP_DELAY_MS = 1000
    MEDIAPIPE_MIN_INTERVAL_MS = 33
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
    DEBUG_MODE_LOG_PATH = r"F:\aidraw\debug-ef2385.log"

    def __init__(self,
                 pose_converter: MediaPoseFacePoseConverter00,
                 video_capture,
                 face_landmarker,
                 device: torch.device):
        super().__init__(None, wx.ID_ANY, "THA4 MediaPipe Puppeteer [Load Preview]")
        self.face_landmarker = face_landmarker
        self.video_capture = video_capture
        self.pose_converter = pose_converter
        self.device = device

        self.source_image_bitmap = wx.Bitmap(MainFrame.SOURCE_PREVIEW_SIZE, MainFrame.SOURCE_PREVIEW_SIZE)
        self.result_image_bitmap = wx.Bitmap(1, 1)
        self.webcam_capture_bitmap = wx.Bitmap(256, 192)
        # Video source handling (camera not connected -> show error instead of generic "Nothing yet!").
        self.video_capture_status_message: Optional[str] = None
        self.video_source_choice_map: dict[str, tuple[str, object, object]] = {}
        self.video_source_choice: Optional[wx.Choice] = None
        self.webcam_container: Optional[wx.Panel] = None
        self.webcam_preview_popup_frame: Optional[WebcamPreviewPopupFrame] = None
        self.current_video_capture_api: Optional[int] = None
        self.video_source_status_text: Optional[wx.StaticText] = None
        self.video_source_kind = "none"
        self._image_file_path: Optional[str] = None
        self._last_good_webcam_bgr_frame = None
        self._capture_frame_serial = 0
        self._last_mediapipe_process_time = 0.0
        self._last_preview_ui_time = 0.0
        self._video_enumeration_in_progress = False
        self._startup_auto_connect_attempted = False
        self._startup_full_controls_shown = False
        self.rotation_labels = {}
        self.rotation_value_labels = {}
        self.wx_source_image = None
        self.torch_source_image = None
        self.last_pose = None
        self.mediapipe_face_pose = None
        self.fps_statistics = FpsStatistics()
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
        self._last_scale_curve_signature = None
        self._startup_autofit_pending = False
        self._controls_geometry_restored = False
        self._compact_geometry_restored = False
        self._controls_fixed_client_width: Optional[int] = None
        self._scroll_refresh_pending = False
        self._controls_build_in_progress = False
        self._active_save_caller: Optional[str] = None
        self._external_layer_output_frame_sequence = 0
        self._restoring_window_geometry = False
        self._window_geometry_save_pending = False
        self._hover_help_pending_window: Optional[wx.Window] = None
        self._hover_help_active_window: Optional[wx.Window] = None
        self._debug_run_id = "run-initial"
        self.last_loaded_model_path: Optional[str] = None
        self.full_controls_expanded = False
        self.controls_frame: Optional[ControlsFrame] = None
        self.persistent_ui_state = self.load_persistent_ui_state()
        self.image_source_mode = normalize_image_source_mode(
            self.persistent_ui_state.get("image_source_mode", IMAGE_SOURCE_THA4))
        tha3_png = self.persistent_ui_state.get("tha3_character_png")
        self.last_tha3_character_png = tha3_png if isinstance(tha3_png, str) else None
        self.tha3_model_variant = str(
            self.persistent_ui_state.get("tha3_model_variant", "separable_half"))
        self.active_image_source = create_image_source(self.image_source_mode)
        self.apply_mouth_persistent_state_to_args()
        self.SetDoubleBuffered(True)
        self.initialize_headless_control_state()

        self.output_frame = None
        self.create_ui()
        self.apply_persistent_ui_state()
        self.restore_compact_frame_geometry()
        self.refresh_model_loaded_ui_state()
        self.create_timers()
        self.active_image_source.start(self)
        self.refresh_image_source_ui_visibility()
        if self.image_source_mode == IMAGE_SOURCE_THA3 and self.last_tha3_character_png:
            if os.path.isfile(self.last_tha3_character_png):
                self.active_image_source.load_asset(self, self.last_tha3_character_png)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_SIZE, self.on_compact_geometry_changed)
        self.Bind(wx.EVT_MOVE, self.on_compact_geometry_changed)

        self.update_source_image_bitmap()
        wx.CallAfter(self.startup_show_full_controls)

    def agent_debug_log(self,
                        hypothesis_id: str,
                        location: str,
                        message: str,
                        data: Optional[dict] = None):
        return

    def debug_mode_log(self,
                       run_id: str,
                       hypothesis_id: str,
                       location: str,
                       message: str,
                       data: Optional[dict] = None):
        try:
            payload = {
                "sessionId": "ef2385",
                "runId": run_id,
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data or {},
                "timestamp": int(time.time() * 1000),
            }
            # #region agent log
            with open(self.DEBUG_MODE_LOG_PATH, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(payload, ensure_ascii=True) + "\n")
            # #endregion
        except Exception:
            pass

    def startup_show_full_controls(self):
        # #region agent log
        self.agent_debug_log(
            "H1",
            "startup_show_full_controls:entry",
            "startup_show_full_controls invoked",
            {"already_shown": self._startup_full_controls_shown})
        # #endregion
        if self._startup_full_controls_shown:
            return
        self._startup_full_controls_shown = True
        self.show_full_controls_window()
        if not self.is_external_layer_output_enabled():
            self.ensure_output_frame()
        else:
            self.hide_builtin_output_frame()
        self.initialize_output_bitmap()
        self.refresh_output_frame_chrome()
        self.update_result_image_bitmap()
        wx.CallAfter(self.ensure_application_windows_visible)
        self.schedule_refresh_controls_scrolling()
        # Auto camera loading is disabled; user-triggered by model-load buttons.
        # #region agent log
        self.agent_debug_log(
            "H14",
            "startup_show_full_controls:auto-enumeration-disabled",
            "auto camera enumeration disabled on startup",
            {})
        # #endregion
        # #region agent log
        self.agent_debug_log(
            "H1",
            "startup_show_full_controls:exit",
            "startup_show_full_controls scheduled",
            {"full_controls_expanded": self.full_controls_expanded})
        # #endregion

    def try_startup_auto_connect_camera(self):
        if self._startup_auto_connect_attempted:
            return
        self._startup_auto_connect_attempted = True
        if self.is_capture_source_active():
            return
        if self._video_enumeration_in_progress:
            self._startup_auto_connect_attempted = False
            wx.CallLater(600, self.try_startup_auto_connect_camera)
            return
        wx.CallAfter(self.connect_default_video_source)

    def get_default_pose_list(self) -> List[float]:
        if self._default_pose_list is None:
            self._default_pose_list = self.pose_converter.convert(self._default_mediapipe_face_pose)
        return self._default_pose_list

    def create_timers(self):
        self.capture_timer = wx.Timer(self, wx.ID_ANY)
        self.Bind(wx.EVT_TIMER, self.update_capture_panel, id=self.capture_timer.GetId())
        self.animation_timer = wx.Timer(self, wx.ID_ANY)
        self.Bind(wx.EVT_TIMER, self.update_result_image_bitmap, id=self.animation_timer.GetId())

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
        self.output_background_choice = ValueState("#00FF00")
        self.mirror_output_checkbox = ValueState(False)
        self.external_layer_output_checkbox = ValueState(False)
        self.antialias_strength_spin = ValueState(1.00)

    def is_external_layer_output_enabled(self) -> bool:
        checkbox = getattr(self, "external_layer_output_checkbox", None)
        if checkbox is None:
            return False
        return bool(checkbox.GetValue())

    def on_external_layer_output_changed(self, event: wx.Event):
        try:
            self.apply_external_layer_output_visibility()
            self.save_persistent_ui_state()
        except Exception as exc:
            # Never let a toggle callback break the wx event chain.
            if hasattr(self, "external_layer_output_status_text"):
                self.external_layer_output_status_text.SetLabel(
                    f"外挂输出切换失败：{exc}\n/ External toggle failed: {exc}")
        finally:
            # Ensure layout/scroll is recalculated after visibility changes.
            try:
                if hasattr(self, "controls_frame") and self.controls_frame:
                    self.controls_frame.Layout()
            except Exception:
                pass
            self.schedule_refresh_controls_scrolling()
        event.Skip()

    def apply_external_layer_output_visibility(self):
        enabled = self.is_external_layer_output_enabled()
        if hasattr(self, "external_layer_output_status_text"):
            if enabled:
                bridge_dir = ExternalLayerOutputBridge.get_bridge_directory(self)
                self.external_layer_output_status_text.SetLabel(
                    "内置输出窗已关闭；外挂进程请读取：\n"
                    f"{bridge_dir}\n"
                    "当前仅写入 metadata（frame_sequence/变换/背景等），"
                    "尚未导出 RGBA 像素；外部预览可能不会立即变化。\n"
                    "Built-in output hidden. External compositor reads bridge dir above.\n"
                    "Metadata only for now (RGBA export reserved).")
            else:
                self.external_layer_output_status_text.SetLabel(
                    "使用内置无边框输出窗（OBS 窗口采集）。\n"
                    "Using built-in borderless output window for capture.")
        if enabled:
            ExternalLayerOutputBridge.write_contract_file(self)
            self.hide_builtin_output_frame()
        else:
            ExternalLayerOutputBridge.clear_bridge_status(self)
            if self.full_controls_expanded or getattr(self, "output_frame", None) is not None:
                self.ensure_output_frame()
                if getattr(self, "output_frame", None) is not None:
                    self.output_frame.Show(True)
                    self.uniconize_window(self.output_frame)
            if self.last_output_wx_image is not None:
                self.draw_cached_result_image(self.last_banner_text)

    def hide_builtin_output_frame(self):
        if getattr(self, "output_frame", None) is None:
            return
        self.output_frame.Show(False)

    def on_close(self, event: wx.Event):
        self._is_closing = True
        if getattr(self, "output_frame", None) is not None and self.output_frame:
            self.handle_output_frame_geometry_changed(redraw=False)
        self.save_persistent_ui_state()
        if hasattr(self, "active_image_source"):
            self.active_image_source.stop(self)
        if hasattr(self.pose_converter, "shutdown"):
            self.pose_converter.shutdown()
        self.animation_timer.Stop()
        self.capture_timer.Stop()
        if getattr(self, "webcam_preview_popup_frame", None) is not None and self.webcam_preview_popup_frame:
            self.webcam_preview_popup_frame.Destroy()
            self.webcam_preview_popup_frame = None
        if getattr(self, "hover_help_popup", None) is not None and self.hover_help_popup:
            self.hover_help_popup.Destroy()
            self.hover_help_popup = None
        if getattr(self, "controls_frame", None) is not None and self.controls_frame:
            self.controls_frame.Destroy()
            self.controls_frame = None
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
    def wrap_static_text_to_parent(control: wx.StaticText):
        parent = control.GetParent()
        if parent is None:
            return
        wrap_width = parent.GetClientSize().x - 12
        if wrap_width > 40:
            control.Wrap(wrap_width)

    @staticmethod
    def set_text_ctrl_if_changed(control: wx.TextCtrl, text: str):
        if control.GetValue() != text:
            control.ChangeValue(text)

    def set_wrapped_static_text_if_changed(self, control: wx.StaticText, text: str):
        if control.GetLabel() != text:
            control.SetLabelText(text)
        wx.CallAfter(self.wrap_static_text_to_parent, control)

    def refresh_dynamic_output_status_layout(self):
        for attr_name in ("scale_curve_status_text", "auto_transform_status_text", "fps_text"):
            control = getattr(self, attr_name, None)
            if control is not None:
                self.wrap_static_text_to_parent(control)

    def on_dynamic_output_panel_size(self, event: wx.Event):
        self.refresh_dynamic_output_status_layout()
        event.Skip()

    @staticmethod
    def apply_splitter_sash(splitter: wx.SplitterWindow, sash_position: int):
        if splitter is None or not splitter.IsSplit():
            return
        minimum = max(1, splitter.GetMinimumPaneSize())
        total = splitter.GetClientSize().x
        if total <= minimum * 2:
            return
        clamped_position = max(minimum, min(total - minimum, int(sash_position)))
        splitter.SetSashPosition(clamped_position)

    def get_controls_window(self) -> Optional[wx.Frame]:
        return self.controls_frame if getattr(self, "controls_frame", None) is not None else None

    def initialize_adjustable_columns(self):
        controls_window = self.get_controls_window()
        if getattr(self, "_is_closing", False) or controls_window is None:
            return
        if hasattr(self, "animation_splitter") and self.animation_splitter.IsSplit():
            saved_animation_sash = self.persistent_ui_state.get("animation_splitter_sash")
            default_animation_sash = max(260, self.model_input_column.GetBestSize().x)
            self.apply_splitter_sash(
                self.animation_splitter,
                saved_animation_sash if isinstance(saved_animation_sash, (int, float)) else default_animation_sash)
            # #region agent log
            self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H20",
                location="initialize_adjustable_columns:animation-splitter-applied",
                message="animation splitter sash applied",
                data={
                    "saved_animation_sash": saved_animation_sash,
                    "default_animation_sash": int(default_animation_sash),
                    "actual_sash": int(self.animation_splitter.GetSashPosition()),
                    "splitter_client_size": list(self.animation_splitter.GetClientSize()),
                    "left_size": list(self.model_input_column.GetSize()),
                    "right_size": list(self.animation_left_panel.GetSize()),
                })
            # #endregion
        if hasattr(self, "main_splitter") and self.main_splitter.IsSplit():
            saved_main_sash = self.persistent_ui_state.get("main_splitter_sash")
            if hasattr(self, "right_sidebar"):
                self.right_sidebar.Layout()
            total_w = max(1, self.main_splitter.GetClientSize().x)
            min_pane_w = max(1, self.main_splitter.GetMinimumPaneSize())
            right_best_w = max(
                MainFrame.RIGHT_SIDEBAR_MIN_WIDTH,
                min_pane_w,
                int(self.right_sidebar.GetBestSize().x))
            default_main_sash = int(total_w - right_best_w)
            sash_to_use = default_main_sash
            if isinstance(saved_main_sash, (int, float)):
                saved_right_w = total_w - float(saved_main_sash)
                # If the saved sash would squeeze the right sidebar below its best width,
                # ignore it and use the safe default.
                if saved_right_w >= right_best_w * 0.95:
                    sash_to_use = int(saved_main_sash)
            self.apply_splitter_sash(self.main_splitter, sash_to_use)
        self.refresh_dynamic_output_status_layout()
        if hasattr(self, "animation_panel"):
            self.schedule_refresh_controls_scrolling()
        controls_window.Layout()
        wx.CallAfter(lambda: self.adapt_main_window_to_controls(initial=False))

    def on_compact_geometry_changed(self, event: wx.Event):
        if self.full_controls_expanded:
            event.Skip()
            return
        self.schedule_window_geometry_save()
        event.Skip()

    def schedule_window_geometry_save(self):
        if self._window_geometry_save_pending or self._restoring_window_geometry:
            return
        self._window_geometry_save_pending = True
        wx.CallLater(250, self.process_window_geometry_save)

    def process_window_geometry_save(self):
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

    def get_output_background_hex(self) -> str:
        picker = getattr(self, "output_background_choice", None)
        if picker is None:
            return "#000000"
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
        return self.get_output_background_hex()

    def get_output_frame_paint_colour(self) -> wx.Colour:
        background_color = self.get_output_background_color()
        return background_color

    def paint_output_background(self, dc: wx.DC, size: wx.Size):
        dc.SetBackground(wx.Brush(self.get_output_frame_paint_colour()))
        dc.Clear()

    def refresh_output_frame_chrome(self):
        if self.is_external_layer_output_enabled():
            return
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

    def ensure_application_windows_visible(self):
        ensure_start = time.time()
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H19",
            location="ensure_application_windows_visible:entry",
            message="enter ensure application windows visible",
            data={"full_controls_expanded": bool(self.full_controls_expanded)})
        # #endregion
        # #region agent log
        self.agent_debug_log(
            "H2",
            "ensure_application_windows_visible:entry",
            "ensure windows visible start",
            {"full_controls_expanded": self.full_controls_expanded})
        # #endregion
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
            # #region agent log
            self.agent_debug_log(
                "H2",
                "ensure_application_windows_visible:after-geometry",
                "applied controls geometry",
                {"controls_pos": [self.controls_frame.GetPosition().x, self.controls_frame.GetPosition().y]})
            # #endregion
            self.apply_controls_window_size_policy(self.controls_frame)
            # #region agent log
            self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H19",
                location="ensure_application_windows_visible:after-controls-size-policy",
                message="controls geometry applied",
                data={"elapsed_ms": int((time.time() - ensure_start) * 1000)})
            # #endregion
            # #region agent log
            self.agent_debug_log(
                "H2",
                "ensure_application_windows_visible:after-size-policy",
                "applied controls size policy",
                {"controls_size": [self.controls_frame.GetClientSize().x, self.controls_frame.GetClientSize().y]})
            # #endregion
            self.controls_frame.Show(True)
            self.uniconize_window(self.controls_frame)

            if not self.is_external_layer_output_enabled():
                self.ensure_output_frame()
                locked_w, locked_h = self.get_locked_output_client_size()
                min_output_size = wx.Size(locked_w, locked_h)
                default_output_size = wx.Size(locked_w, locked_h)
                used_saved_output = self.apply_frame_geometry_from_storage(
                    self.output_frame, "output_frame", min_output_size, default_output_size)
                if not used_saved_output:
                    beside_rect = self.default_output_frame_rect_beside_controls()
                    self.apply_client_rect_to_window(self.output_frame, beside_rect, min_output_size)
                self.output_frame.Show(True)
                self.uniconize_window(self.output_frame)
            else:
                self.hide_builtin_output_frame()

            self.Show(False)
            self.bring_controls_frame_to_front()
            self.schedule_refresh_controls_scrolling()
            # #region agent log
            self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H19",
                location="ensure_application_windows_visible:before-full-return",
                message="full controls branch complete",
                data={"elapsed_ms": int((time.time() - ensure_start) * 1000)})
            # #endregion
            if not self.controls_frame.IsShown():
                # Failsafe: if full controls failed to show, keep compact launcher visible.
                self.full_controls_expanded = False
                self.Show(True)
                self.Raise()
            # #region agent log
            self.agent_debug_log(
                "H2",
                "ensure_application_windows_visible:full-exit",
                "ensure windows visible full exit",
                {
                    "controls_shown": bool(self.controls_frame and self.controls_frame.IsShown()),
                    "output_shown": bool(self.output_frame and self.output_frame.IsShown())
                })
            # #endregion
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
        if getattr(self, "output_frame", None) is not None and not self.is_external_layer_output_enabled():
            self.ensure_output_frame()
            locked_w, locked_h = self.get_locked_output_client_size()
            min_output_size = wx.Size(locked_w, locked_h)
            default_output_size = wx.Size(locked_w, locked_h)
            used_saved_output = self.apply_frame_geometry_from_storage(
                self.output_frame, "output_frame", min_output_size, default_output_size)
            if not used_saved_output:
                beside_rect = self.default_output_frame_rect_beside_controls()
                self.apply_client_rect_to_window(self.output_frame, beside_rect, min_output_size)
            self.output_frame.Show(True)
            self.uniconize_window(self.output_frame)
        elif self.is_external_layer_output_enabled():
            self.hide_builtin_output_frame()
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H19",
            location="ensure_application_windows_visible:compact-exit-debug",
            message="compact branch complete",
            data={"elapsed_ms": int((time.time() - ensure_start) * 1000)})
        # #endregion
        # #region agent log
        self.agent_debug_log(
            "H2",
            "ensure_application_windows_visible:compact-exit",
            "ensure windows visible compact exit",
            {
                "compact_shown": self.IsShown(),
                "output_shown": bool(self.output_frame and self.output_frame.IsShown())
            })
        # #endregion

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

    def get_controls_height_bounds(self, window: wx.Window, min_height: int) -> tuple[int, int]:
        max_height = self.CONTROLS_MAX_CLIENT_HEIGHT
        try:
            display_index = wx.Display.GetFromWindow(window)
            if display_index != wx.NOT_FOUND:
                work_area = wx.Display(display_index).GetClientArea()
                max_height = min(max_height, max(min_height, int(work_area.height) - 40))
        except Exception:
            pass
        return min_height, max(min_height, max_height)

    def apply_controls_window_size_policy(self, window: wx.Window):
        policy_start = time.time()
        if window is None:
            return
        min_client_size = self.get_controls_min_client_size()
        current_size = window.GetClientSize()
        min_width = max(1, int(min_client_size.x))
        max_width = max(min_width, 10000)
        try:
            display_index = wx.Display.GetFromWindow(window)
            if display_index != wx.NOT_FOUND:
                work_area = wx.Display(display_index).GetClientArea()
                max_width = max(min_width, int(work_area.width) - 40)
        except Exception:
            pass
        min_height, max_height = self.get_controls_height_bounds(window, min_client_size.y)
        target_width = max(min_width, min(max_width, int(current_size.x)))
        target_height = max(min_height, min(max_height, int(current_size.y)))

        self._restoring_window_geometry = True
        try:
            window.SetMinClientSize(wx.Size(min_width, min_height))
            window.SetMaxClientSize(wx.Size(max_width, max_height))
            if current_size.x != target_width or current_size.y != target_height:
                window.SetClientSize(wx.Size(target_width, target_height))
        finally:
            self._restoring_window_geometry = False
        # #region agent log
        self.agent_debug_log(
            "H2",
            "apply_controls_window_size_policy:exit",
            "controls size policy done",
            {
                "elapsed_ms": int((time.time() - policy_start) * 1000),
                "target_width": target_width,
                "min_width": min_width,
                "max_width": max_width,
                "target_height": target_height
            })
        # #endregion

    def handle_controls_frame_resized(self):
        controls_window = self.get_controls_window()
        if controls_window is None or not controls_window.IsShown():
            return
        self.apply_controls_window_size_policy(controls_window)
        self.schedule_refresh_controls_scrolling()

    def schedule_refresh_controls_scrolling(self):
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H8",
            location="schedule_refresh_controls_scrolling:entry",
            message="schedule refresh requested",
            data={
                "scroll_refresh_pending": bool(self._scroll_refresh_pending),
                "has_animation_panel": hasattr(self, "animation_panel"),
                "view_start": list(self.animation_panel.GetViewStart()) if hasattr(self, "animation_panel") else None,
            })
        # #endregion
        if self._scroll_refresh_pending:
            return
        self._scroll_refresh_pending = True
        wx.CallLater(60, self._run_scheduled_refresh_controls_scrolling)

    def _run_scheduled_refresh_controls_scrolling(self):
        self._scroll_refresh_pending = False
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
        if self.is_external_layer_output_enabled():
            self.hide_builtin_output_frame()
            return
        if getattr(self, "output_frame", None) is not None:
            if not self.output_frame.IsShown():
                self.output_frame.Show(True)
            self.sync_output_frame_owner()
            return
        self.output_frame = OutputFrame(self)
        self.apply_output_frame_state()
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
        if hasattr(self, "animation_panel"):
            self.schedule_refresh_controls_scrolling()
        controls_window.Layout()

        min_client_size = self.get_controls_min_client_size()

        if initial and not self._controls_geometry_restored:
            if not self.restore_controls_frame_geometry():
                default_width = max(min_client_size.x, 1180)
                default_height = max(min_client_size.y, 760)
                self._restoring_window_geometry = True
                try:
                    controls_window.SetClientSize(wx.Size(default_width, default_height))
                    controls_window.CenterOnScreen()
                finally:
                    self._restoring_window_geometry = False
                self._controls_geometry_restored = True
        self.apply_controls_window_size_policy(controls_window)

        if hasattr(self, "animation_panel"):
            self.schedule_refresh_controls_scrolling()
        controls_window.Layout()
        if initial and not self._startup_autofit_pending:
            self._startup_autofit_pending = True
            wx.CallAfter(self.finalize_startup_autofit)

    def finalize_startup_autofit(self):
        self._startup_autofit_pending = False
        self.adapt_main_window_to_controls(initial=False)
        self.schedule_refresh_controls_scrolling()

    def on_column_splitter_changed(self, event: wx.Event):
        if hasattr(self, "animation_splitter") and self.animation_splitter.IsSplit() and \
                hasattr(self, "model_input_column") and hasattr(self, "animation_left_panel"):
            # #region agent log
            self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H21",
                location="on_column_splitter_changed:animation-sash-changed",
                message="animation splitter sash changed",
                data={
                    "sash": int(self.animation_splitter.GetSashPosition()),
                    "splitter_client_size": list(self.animation_splitter.GetClientSize()),
                    "left_size": list(self.model_input_column.GetSize()),
                    "left_children": len(self.model_input_column.GetChildren()),
                    "right_size": list(self.animation_left_panel.GetSize()),
                })
            # #endregion
        self.refresh_dynamic_output_status_layout()
        if hasattr(self, "animation_panel"):
            self.schedule_refresh_controls_scrolling()
        if hasattr(self, "output_background_choice"):
            self.save_persistent_ui_state()
        event.Skip()

    @classmethod
    def get_ui_state_file_path(cls) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), cls.UI_STATE_FILE_NAME)

    def apply_mouth_persistent_state_to_args(self):
        mouth_settings = self.persistent_ui_state.get("mouth_settings")
        if isinstance(mouth_settings, dict):
            self.pose_converter.apply_persistent_mouth_settings(mouth_settings)

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
        # #region agent log
        self.debug_mode_log(
            run_id="slider-persist",
            hypothesis_id="H-SLIDER-SAVE",
            location="collect_display_transform_settings",
            message="collected display transform slider settings",
            data={"settings": settings})
        # #endregion
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
        # #region agent log
        self.debug_mode_log(
            run_id="slider-persist",
            hypothesis_id="H-SLIDER-APPLY",
            location="apply_persistent_slider_value_states",
            message="applied display transform slider settings",
            data={"applied": applied})
        # #endregion

    def load_persistent_ui_state(self) -> dict:
        file_path = self.get_ui_state_file_path()
        if not os.path.isfile(file_path):
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            return self.sanitize_window_geometry_in_state(data)
        except Exception:
            return {}

    def reload_persistent_ui_state_from_disk(self):
        self.persistent_ui_state = self.load_persistent_ui_state()

    @staticmethod
    def sanitize_window_geometry_in_state(data: dict) -> dict:
        sanitized = dict(data)
        for prefix in ("controls_frame", "compact_frame", "output_frame"):
            width_key = f"{prefix}_w"
            height_key = f"{prefix}_h"
            if width_key not in sanitized or height_key not in sanitized:
                continue
            width = max(1, int(sanitized[width_key]))
            height = max(1, int(sanitized[height_key]))
            if prefix == "output_frame":
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
        # #region agent log
        self.agent_debug_log(
            "H9",
            "collect_persistent_ui_state:entry",
            "collect persistent ui state entry",
            {
                "is_main_thread": wx.IsMainThread(),
                "controls_build_in_progress": self._controls_build_in_progress,
            })
        # #endregion
        animation_splitter_sash = self.persistent_ui_state.get("animation_splitter_sash")
        if hasattr(self, "animation_splitter") and self.animation_splitter.IsSplit():
            animation_splitter_sash = self.animation_splitter.GetSashPosition()
        main_splitter_sash = self.persistent_ui_state.get("main_splitter_sash")
        if hasattr(self, "main_splitter") and self.main_splitter.IsSplit():
            main_splitter_sash = self.main_splitter.GetSashPosition()
        # #region agent log
        self.agent_debug_log(
            "H10",
            "collect_persistent_ui_state:after-sash",
            "read splitter sash positions",
            {"has_main_splitter": hasattr(self, "main_splitter")})
        # #endregion
        # #region agent log
        self.agent_debug_log(
            "H11",
            "collect_persistent_ui_state:before-background",
            "reading output background control",
            {"caller": self._active_save_caller})
        # #endregion
        if self._active_save_caller == "process_window_geometry_save":
            output_background_hex = self.normalize_background_hex(
                self.persistent_ui_state.get("output_background_hex", "#000000"),
                "#000000")
            # #region agent log
            self.agent_debug_log(
                "H13",
                "collect_persistent_ui_state:background-from-cache",
                "used cached output background for geometry-save caller",
                {})
            # #endregion
        else:
            output_background_hex = self.get_output_background_hex()
        # #region agent log
        self.agent_debug_log(
            "H11",
            "collect_persistent_ui_state:after-background",
            "read output background control",
            {})
        # #endregion
        # #region agent log
        self.agent_debug_log(
            "H11",
            "collect_persistent_ui_state:before-checkboxes",
            "reading checkbox and interval controls",
            {})
        # #endregion
        enable_auto_transform = self.enable_auto_transform_checkbox.GetValue()
        enable_direction_calibration = self.enable_direction_calibration_checkbox.GetValue()
        direction_calibration_interval_seconds = self.auto_direction_calibration_interval_seconds_ctrl.GetValue()
        enable_scale_calibration = self.enable_scale_calibration_checkbox.GetValue()
        scale_calibration_interval_seconds = self.auto_scale_calibration_interval_seconds_ctrl.GetValue()
        invert_tilt_mapping = self.invert_tilt_mapping_checkbox.GetValue()
        mirror_output = self.mirror_output_checkbox.GetValue()
        external_layer_output_enabled = self.external_layer_output_checkbox.GetValue()
        # #region agent log
        self.agent_debug_log(
            "H11",
            "collect_persistent_ui_state:after-checkboxes",
            "read checkbox and interval controls",
            {})
        # #endregion
        # #region agent log
        self.agent_debug_log(
            "H11",
            "collect_persistent_ui_state:before-mouth-settings",
            "reading persistent mouth settings",
            {})
        # #endregion
        persistent_mouth_settings = self.pose_converter.get_persistent_mouth_settings()
        # #region agent log
        self.agent_debug_log(
            "H11",
            "collect_persistent_ui_state:after-mouth-settings",
            "read persistent mouth settings",
            {})
        # #endregion
        state = {
            "output_background_hex": output_background_hex,
            "enable_auto_transform": enable_auto_transform,
            "enable_direction_calibration": enable_direction_calibration,
            "direction_calibration_interval_seconds": direction_calibration_interval_seconds,
            "enable_scale_calibration": enable_scale_calibration,
            "scale_calibration_interval_seconds": scale_calibration_interval_seconds,
            "invert_tilt_mapping": invert_tilt_mapping,
            "mirror_output": mirror_output,
            "external_layer_output_enabled": external_layer_output_enabled,
            "image_source_mode": self.get_image_source_mode(),
            "tha3_character_png": self.last_tha3_character_png,
            "tha3_model_variant": self.tha3_model_variant,
            "last_loaded_model_path": self.last_loaded_model_path,
            "animation_splitter_sash": animation_splitter_sash,
            "main_splitter_sash": main_splitter_sash,
            "mouth_settings": persistent_mouth_settings,
            "display_transform_settings": self.collect_display_transform_settings(),
        }
        # #region agent log
        self.agent_debug_log(
            "H11",
            "collect_persistent_ui_state:after-core-fields",
            "read core persistent fields",
            {"keys_count": len(state)})
        # #endregion
        if getattr(self, "output_frame", None) is not None and self.output_frame:
            # #region agent log
            self.agent_debug_log(
                "H12",
                "collect_persistent_ui_state:before-output-rect",
                "collecting output frame rect",
                {"is_shown": self.output_frame.IsShown()})
            # #endregion
            state.update(self.collect_window_client_rect(self.output_frame, "output_frame"))
            # #region agent log
            self.agent_debug_log(
                "H12",
                "collect_persistent_ui_state:after-output-rect",
                "collected output frame rect",
                {})
            # #endregion
        controls_window = self.get_controls_window()
        if controls_window is not None and controls_window.IsShown():
            # #region agent log
            self.agent_debug_log(
                "H12",
                "collect_persistent_ui_state:before-controls-rect",
                "collecting controls frame rect",
                {"is_iconized": controls_window.IsIconized()})
            # #endregion
            state.update(self.collect_window_client_rect(controls_window, "controls_frame"))
            # #region agent log
            self.agent_debug_log(
                "H12",
                "collect_persistent_ui_state:after-controls-rect",
                "collected controls frame rect",
                {})
            # #endregion
        if not self.full_controls_expanded and self.IsShown():
            state.update(self.collect_window_client_rect(self, "compact_frame"))
        # #region agent log
        self.agent_debug_log(
            "H9",
            "collect_persistent_ui_state:exit",
            "collect persistent ui state exit",
            {"keys_count": len(state)})
        # #endregion
        return state

    def save_persistent_ui_state(self):
        save_start = time.time()
        caller_name = "<unknown>"
        try:
            caller_frame = inspect.currentframe()
            if caller_frame is not None and caller_frame.f_back is not None:
                caller_name = caller_frame.f_back.f_code.co_name
        except Exception:
            caller_name = "<error>"
        # #region agent log
        self.agent_debug_log(
            "H9",
            "save_persistent_ui_state:entry",
            "save persistent ui state entry",
            {"caller": caller_name})
        # #endregion
        if self._controls_build_in_progress:
            # #region agent log
            self.agent_debug_log(
                "H9",
                "save_persistent_ui_state:skip-build-in-progress",
                "skip save while controls frame is being built",
                {})
            # #endregion
            return
        self._active_save_caller = caller_name
        try:
            data = self.collect_persistent_ui_state()
        finally:
            self._active_save_caller = None
        # #region agent log
        self.agent_debug_log(
            "H9",
            "save_persistent_ui_state:after-collect",
            "save persistent ui state after collect",
            {"data_keys_count": len(data)})
        # #endregion
        if not data:
            return
        self.persistent_ui_state.update(data)
        try:
            # #region agent log
            self.agent_debug_log(
                "H9",
                "save_persistent_ui_state:before-write",
                "save persistent ui state before file write",
                {})
            # #endregion
            with open(self.get_ui_state_file_path(), "w", encoding="utf-8") as f:
                json.dump(self.persistent_ui_state, f, ensure_ascii=True, indent=2)
            # #region agent log
            self.agent_debug_log(
                "H9",
                "save_persistent_ui_state:after-write",
                "save persistent ui state file write complete",
                {"elapsed_ms": int((time.time() - save_start) * 1000)})
            # #endregion
        except Exception:
            # #region agent log
            self.agent_debug_log(
                "H9",
                "save_persistent_ui_state:exception",
                "save persistent ui state raised exception",
                {"elapsed_ms": int((time.time() - save_start) * 1000)})
            # #endregion

    def apply_persistent_ui_state(self):
        data = self.persistent_ui_state
        if not data:
            self.on_display_transform_control_changed()
            return

        self.apply_persistent_slider_value_states()

        if "enable_auto_transform" in data:
            self.enable_auto_transform_checkbox.SetValue(bool(data["enable_auto_transform"]))
        if "output_background_hex" in data:
            self.output_background_choice.SetValue(
                self.normalize_background_hex(data["output_background_hex"], "#000000"))
        elif "output_background_selection" in data:
            self.output_background_choice.SetValue(
                self.background_hex_from_legacy_selection(int(data["output_background_selection"])))
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
        if "invert_tilt_mapping" in data:
            self.invert_tilt_mapping_checkbox.SetValue(bool(data["invert_tilt_mapping"]))
        if "mirror_output" in data:
            self.mirror_output_checkbox.SetValue(bool(data["mirror_output"]))
        if "external_layer_output_enabled" in data:
            self.external_layer_output_checkbox.SetValue(bool(data["external_layer_output_enabled"]))
        if "image_source_mode" in data:
            self.image_source_mode = normalize_image_source_mode(data["image_source_mode"])
        if "tha3_character_png" in data:
            tha3_png = data["tha3_character_png"]
            self.last_tha3_character_png = tha3_png if isinstance(tha3_png, str) else None
        if "tha3_model_variant" in data:
            self.tha3_model_variant = str(data["tha3_model_variant"])
        if "last_loaded_model_path" in data:
            last_loaded_model_path = data["last_loaded_model_path"]
            self.last_loaded_model_path = last_loaded_model_path if isinstance(last_loaded_model_path, str) else None
        self.update_load_model_buttons()
        self.on_display_transform_control_changed()
        wx.CallAfter(self.apply_external_layer_output_visibility)
        if self.get_controls_window() is not None:
            wx.CallAfter(self.initialize_adjustable_columns)

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
        if self.is_external_layer_output_enabled():
            return
        self.ensure_output_frame()

    def get_output_canvas_size(self) -> tuple[int, int]:
        return self.get_locked_output_client_size()

    def initialize_output_bitmap(self):
        width, height = self.get_locked_output_client_size()
        self.result_image_bitmap = wx.Bitmap(max(1, width), max(1, height))
        dc = wx.MemoryDC()
        dc.SelectObject(self.result_image_bitmap)
        self.paint_output_background(dc, wx.Size(width, height))
        dc.SelectObject(wx.NullBitmap)

    def refresh_controls_scrolling(self):
        scroll_start = time.time()
        if not hasattr(self, "animation_panel"):
            return
        view_start_before = self.animation_panel.GetViewStart()
        controls_window = self.get_controls_window()
        if controls_window is not None:
            controls_window.Layout()
        if hasattr(self, "right_sidebar"):
            self.right_sidebar.Layout()
        if hasattr(self, "main_splitter"):
            self.main_splitter.Layout()
        self.animation_panel.Layout()
        min_size = self.animation_panel_sizer.GetMinSize()
        client_size = self.animation_panel.GetClientSize()
        virtual_width = max(client_size.x, min_size.x)
        virtual_height = max(min_size.y, client_size.y)
        self.animation_panel.SetVirtualSize((virtual_width, virtual_height))
        self.animation_panel.EnableScrolling(True, True)
        self.animation_panel.FitInside()
        self.animation_panel.Refresh()
        view_start_after = self.animation_panel.GetViewStart()
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H9",
            location="refresh_controls_scrolling:view-start-delta",
            message="view start before/after FitInside",
            data={
                "before": list(view_start_before),
                "after": list(view_start_after),
                "virtual_size": list(self.animation_panel.GetVirtualSize()),
                "client_size": list(self.animation_panel.GetClientSize()),
            })
        # #endregion
        # #region agent log
        self.agent_debug_log(
            "H2",
            "refresh_controls_scrolling:exit",
            "refresh controls scrolling done",
            {
                "elapsed_ms": int((time.time() - scroll_start) * 1000),
                "virtual_size": list(self.animation_panel.GetVirtualSize()),
                "client_size": list(self.animation_panel.GetClientSize())
            })
        # #endregion

    def ensure_result_bitmap_size(self):
        width, height = self.get_output_canvas_size()
        if self.result_image_bitmap.GetWidth() != width or self.result_image_bitmap.GetHeight() != height:
            self.result_image_bitmap = wx.Bitmap(width, height)

    def handle_output_frame_geometry_changed(self, redraw: bool = True):
        self.refresh_output_frame_chrome()
        self.schedule_window_geometry_save()
        if redraw and self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
        elif redraw:
            self.update_result_image_bitmap()

    def create_animation_panel(self, parent):
        self.animation_panel = wx.ScrolledWindow(parent, style=wx.RAISED_BORDER | wx.HSCROLL | wx.VSCROLL)
        self.animation_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.animation_panel.SetSizer(self.animation_panel_sizer)
        self.animation_panel.SetAutoLayout(1)
        self.animation_panel.SetDoubleBuffered(True)
        self.animation_panel.SetScrollRate(16, 16)
        self.animation_panel.EnableScrolling(True, True)
        self.animation_panel.Bind(wx.EVT_MOUSEWHEEL, self.on_animation_panel_mousewheel_logged)

        image_size = MainFrame.IMAGE_SIZE
        self.animation_panel.SetMinSize(wx.Size(-1, image_size + 140))

        self.animation_splitter = wx.SplitterWindow(
            self.animation_panel,
            style=wx.SP_LIVE_UPDATE | wx.SP_3D | wx.SP_BORDER)
        self.animation_splitter.SetMinimumPaneSize(220)
        self.animation_splitter.SetSashGravity(0.0)
        self.animation_splitter.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.on_column_splitter_changed)
        self.animation_panel_sizer.Add(self.animation_splitter, 1, wx.EXPAND)

        if True:
            self.model_input_column = wx.Panel(self.animation_splitter, style=wx.SIMPLE_BORDER)
            self.model_input_column_sizer = wx.BoxSizer(wx.VERTICAL)
            self.model_input_column.SetSizer(self.model_input_column_sizer)
            self.model_input_column.SetAutoLayout(1)
            self.model_input_column.SetDoubleBuffered(True)

            model_input_text = wx.StaticText(
                self.model_input_column, label="--- 模型参数传入 / Model Input ---", style=wx.ALIGN_CENTER)
            self.model_input_column_sizer.Add(model_input_text, 0, wx.EXPAND)

        if True:
            def current_pose_supplier() -> Optional[MediaPipeFacePose]:
                return self.mediapipe_face_pose

            self.pose_converter.ui_state_changed_callback = self.save_persistent_ui_state
            model_input_children_before = len(self.model_input_column.GetChildren())
            # #region agent log
            self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H12",
                location="create_animation_panel:before-init-pose-converter-panel",
                message="before pose converter panel init",
                data={"children_before": model_input_children_before})
            # #endregion
            self.pose_converter.init_pose_converter_panel(self.model_input_column, current_pose_supplier)
            model_input_children_after = len(self.model_input_column.GetChildren())
            # #region agent log
            self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H12",
                location="create_animation_panel:after-init-pose-converter-panel",
                message="after pose converter panel init",
                data={"children_after": model_input_children_after})
            # #endregion
            mouth_settings = self.persistent_ui_state.get("mouth_settings")
            if isinstance(mouth_settings, dict):
                self.pose_converter.apply_persistent_mouth_settings(mouth_settings)
            if hasattr(self.pose_converter, "refresh_audio_input_runtime"):
                self.pose_converter.refresh_audio_input_runtime(time.time())
            self.model_input_column_sizer.Fit(self.model_input_column)

        if True:
            self.animation_left_panel = wx.Panel(self.animation_splitter, style=wx.SIMPLE_BORDER)
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
                self.animation_left_panel, label="反转倾斜映射 / Invert Tilt Mapping")
            self.invert_tilt_mapping_checkbox.SetValue(invert_tilt_mapping)
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

            self.fps_text = wx.StaticText(self.animation_left_panel, label="")
            self.animation_left_panel_sizer.Add(self.fps_text, wx.SizerFlags().Expand().Border())
            self.animation_left_panel_sizer.Fit(self.animation_left_panel)
            self.refresh_auto_transform_status("READY")
            self.refresh_scale_curve_status()
            self.refresh_dynamic_output_status_layout()

        if not self.animation_splitter.IsSplit():
            self.animation_splitter.SplitVertically(
                self.model_input_column,
                self.animation_left_panel,
                sashPosition=max(260, self.model_input_column.GetBestSize().x))
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H22",
            location="create_animation_panel:after-split",
            message="animation panel split created",
            data={
                "is_split": bool(self.animation_splitter.IsSplit()),
                "sash": int(self.animation_splitter.GetSashPosition()) if self.animation_splitter.IsSplit() else -1,
                "splitter_client_size": list(self.animation_splitter.GetClientSize()),
                "left_best_size": list(self.model_input_column.GetBestSize()),
                "left_size": list(self.model_input_column.GetSize()),
                "left_children": len(self.model_input_column.GetChildren()),
                "right_size": list(self.animation_left_panel.GetSize()),
            })
        # #endregion

        # Do NOT fit scrolled window to content; otherwise vertical scrollbars never appear.
        self.animation_panel.SetMinSize(wx.Size(480, 320))
        # #region agent log
        self.agent_debug_log(
            "H17",
            "create_animation_panel:keep-scrollable-size",
            "kept scrolled window smaller than content",
            {})
        # #endregion
        # #region agent log
        wx.CallAfter(
            lambda: self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H23",
                location="create_animation_panel:callafter-layout-snapshot",
                message="post-layout animation panel snapshot",
                data={
                    "animation_panel_client_size": list(self.animation_panel.GetClientSize()),
                    "splitter_client_size": list(self.animation_splitter.GetClientSize()),
                    "is_split": bool(self.animation_splitter.IsSplit()),
                    "sash": int(self.animation_splitter.GetSashPosition()) if self.animation_splitter.IsSplit() else -1,
                    "left_size": list(self.model_input_column.GetSize()),
                    "right_size": list(self.animation_left_panel.GetSize()),
                }))
        # #endregion
        wx.CallAfter(self.refresh_controls_scrolling)

    def on_animation_panel_mousewheel_logged(self, event: wx.MouseEvent):
        event_object = event.GetEventObject()
        if isinstance(event_object, wx.Slider):
            wheel_delta = event.GetWheelDelta()
            wheel_steps = int(event.GetWheelRotation() / wheel_delta) if wheel_delta else 0
            old_value = int(event_object.GetValue())
            line_size = max(1, int(event_object.GetLineSize()))
            new_value = old_value + wheel_steps * line_size
            new_value = max(int(event_object.GetMin()), min(int(event_object.GetMax()), int(new_value)))
            if new_value != old_value:
                event_object.SetValue(new_value)
                slider_event = wx.CommandEvent(wx.EVT_SLIDER.typeId, event_object.GetId())
                slider_event.SetEventObject(event_object)
                wx.PostEvent(event_object.GetEventHandler(), slider_event)
            # #region agent log
            self.debug_mode_log(
                run_id="post-fix",
                hypothesis_id="H24",
                location="on_animation_panel_mousewheel_logged:slider-adjust",
                message="mouse wheel adjusted slider directly",
                data={
                    "rotation": int(event.GetWheelRotation()),
                    "steps": int(wheel_steps),
                    "line_size": int(line_size),
                    "old_value": int(old_value),
                    "new_value": int(new_value),
                })
            # #endregion
            return
        if hasattr(self, "animation_panel"):
            # #region agent log
            self.debug_mode_log(
                run_id="post-fix",
                hypothesis_id="H10",
                location="on_animation_panel_mousewheel_logged:entry",
                message="animation panel mousewheel event",
                data={
                    "rotation": int(event.GetWheelRotation()),
                    "view_start": list(self.animation_panel.GetViewStart()),
                    "sizer_children": self.animation_panel_sizer.GetItemCount() if hasattr(self, "animation_panel_sizer") else -1,
                    "event_object_type": type(event_object).__name__ if event_object is not None else "None",
                })
            # #endregion
            wx.CallAfter(
                lambda: self.debug_mode_log(
                    run_id="post-fix",
                    hypothesis_id="H10",
                    location="on_animation_panel_mousewheel_logged:after",
                    message="animation panel mousewheel after event loop",
                    data={"view_start": list(self.animation_panel.GetViewStart())}))
        event.Skip()

    def create_compact_launcher_panel(self, parent):
        self.compact_launcher_panel = wx.Panel(parent, style=wx.SIMPLE_BORDER)
        compact_launcher_sizer = wx.BoxSizer(wx.VERTICAL)
        self.compact_launcher_panel.SetSizer(compact_launcher_sizer)
        self.compact_launcher_panel.SetAutoLayout(1)
        self.compact_launcher_panel.SetDoubleBuffered(True)

        self.quick_load_last_model_button = wx.Button(
            self.compact_launcher_panel,
            wx.ID_ANY,
            "加载上次 THA4 Student / Load Last THA4 Student")
        self.quick_load_last_model_button.Bind(wx.EVT_BUTTON, self.load_last_model)
        compact_launcher_sizer.Add(self.quick_load_last_model_button, 0, wx.EXPAND | wx.ALL, 6)

        self.quick_calibrate_head_orientation_button = wx.Button(
            self.compact_launcher_panel, wx.ID_ANY, "校正头部朝向 / Calibrate Head Orientation")
        self.quick_calibrate_head_orientation_button.Bind(wx.EVT_BUTTON, self.calibrate_head_orientation_quick)
        compact_launcher_sizer.Add(self.quick_calibrate_head_orientation_button, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.quick_calibrate_scale_button = wx.Button(
            self.compact_launcher_panel, wx.ID_ANY, "自动缩放校准 / Auto Scale Calibration")
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
        # #region agent log
        self.agent_debug_log(
            "H5",
            "create_controls_frame:entry",
            "create controls frame entry",
            {"already_exists": self.controls_frame is not None})
        # #endregion
        if self.controls_frame is not None:
            # #region agent log
            self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H11",
                location="create_controls_frame:already-exists-return",
                message="skip controls frame creation (already exists)",
                data={
                    "controls_frame_id": id(self.controls_frame),
                    "is_shown": bool(self.controls_frame.IsShown()),
                })
            # #endregion
            return

        self._controls_build_in_progress = True
        self.controls_frame = ControlsFrame(self)
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H11",
            location="create_controls_frame:new-frame-created",
            message="new controls frame created",
            data={"controls_frame_id": id(self.controls_frame)})
        # #endregion
        # #region agent log
        self.agent_debug_log(
            "H5",
            "create_controls_frame:after-frame",
            "controls frame object created",
            {})
        # #endregion
        try:
            self.main_sizer = wx.BoxSizer(wx.VERTICAL)
            self.controls_frame.SetSizer(self.main_sizer)
            self.controls_frame.SetAutoLayout(1)

            controls_header_panel = wx.Panel(self.controls_frame)
            controls_header_sizer = wx.BoxSizer(wx.HORIZONTAL)
            controls_header_panel.SetSizer(controls_header_sizer)
            controls_header_panel.SetAutoLayout(1)
            self.main_sizer.Add(controls_header_panel, 0, wx.EXPAND | wx.ALL, 5)

            self.switch_to_compact_button = wx.Button(
                controls_header_panel, wx.ID_ANY, "切换到精简小窗 / Switch to Compact")
            self.switch_to_compact_button.Bind(wx.EVT_BUTTON, self.switch_to_compact_clicked)
            controls_header_sizer.Add(self.switch_to_compact_button, 0, wx.EXPAND)

            self.load_last_tha3_png_button = wx.Button(
                controls_header_panel,
                wx.ID_ANY,
                "以 THA3 加载上次立绘 / Load Last THA3 PNG")
            self.load_last_tha3_png_button.Bind(wx.EVT_BUTTON, self.load_last_tha3_character_png)
            controls_header_sizer.Add(self.load_last_tha3_png_button, 0, wx.EXPAND | wx.LEFT, 6)

            self.load_tha3_other_png_button = wx.Button(
                controls_header_panel,
                wx.ID_ANY,
                "以 THA3 加载其他立绘 / Load Other THA3 PNG")
            self.load_tha3_other_png_button.Bind(wx.EVT_BUTTON, self.load_tha3_character_png)
            controls_header_sizer.Add(self.load_tha3_other_png_button, 0, wx.EXPAND | wx.LEFT, 6)

            self.load_last_model_button = wx.Button(
                controls_header_panel,
                wx.ID_ANY,
                "加载上次 THA4 Student / Load Last THA4 Student")
            self.load_last_model_button.Bind(wx.EVT_BUTTON, self.load_last_model)
            controls_header_sizer.Add(self.load_last_model_button, 0, wx.EXPAND | wx.LEFT, 6)

            self.load_model_button = wx.Button(
                controls_header_panel,
                wx.ID_ANY,
                "加载其他 THA4 Student 模型 / Load Other THA4 Student Model")
            self.load_model_button.Bind(wx.EVT_BUTTON, self.load_model)
            controls_header_sizer.Add(self.load_model_button, 0, wx.EXPAND | wx.LEFT, 6)
            self.update_load_model_buttons()

            self.main_splitter = wx.SplitterWindow(
                self.controls_frame,
                style=wx.SP_LIVE_UPDATE | wx.SP_3D | wx.SP_BORDER)
            self.main_splitter.SetMinimumPaneSize(MainFrame.RIGHT_SIDEBAR_MIN_WIDTH)
            self.main_splitter.SetSashGravity(1.0)
            self.main_splitter.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.on_column_splitter_changed)
            self.main_sizer.Add(self.main_splitter, wx.SizerFlags(1).Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 5))

            self.create_animation_panel(self.main_splitter)
            # #region agent log
            self.agent_debug_log(
                "H5",
                "create_controls_frame:after-animation-panel",
                "animation panel created",
                {})
            # #endregion

            self.right_sidebar = wx.Panel(self.main_splitter)
            self.right_sidebar_sizer = wx.BoxSizer(wx.VERTICAL)
            self.right_sidebar.SetSizer(self.right_sidebar_sizer)
            self.right_sidebar.SetAutoLayout(1)
            self.right_sidebar.SetDoubleBuffered(True)

            self.create_capture_panel(self.right_sidebar)
            # #region agent log
            self.agent_debug_log(
                "H5",
                "create_controls_frame:after-capture-panel",
                "capture panel created",
                {})
            # #endregion
            self.right_sidebar_sizer.Add(self.capture_panel, wx.SizerFlags(0).Expand())

            self.create_postprocess_panel(self.right_sidebar)
            # #region agent log
            self.agent_debug_log(
                "H5",
                "create_controls_frame:after-postprocess-panel",
                "postprocess panel created",
                {})
            # #endregion
            self.right_sidebar_sizer.Add(self.postprocess_panel, wx.SizerFlags(0).Expand().Border(wx.TOP, 6))
            self.right_sidebar_sizer.Fit(self.right_sidebar)

            if not self.main_splitter.IsSplit():
                self.main_splitter.SplitVertically(
                    self.animation_panel,
                    self.right_sidebar,
                    sashPosition=max(720, self.animation_panel.GetBestSize().x))

            self.main_sizer.Fit(self.controls_frame)
            # #region agent log
            self.agent_debug_log(
                "H5",
                "create_controls_frame:after-fit",
                "main sizer fit completed",
                {"client_size": [self.controls_frame.GetClientSize().x, self.controls_frame.GetClientSize().y]})
            # #endregion
            self.refresh_model_loaded_ui_state()
            self.on_display_transform_control_changed()
            try:
                self.update_source_image_bitmap()
            except Exception as exc:
                # #region agent log
                self.agent_debug_log(
                    "H15",
                    "create_controls_frame:update-source-exception",
                    "update source image bitmap failed during controls build",
                    {"error_type": type(exc).__name__, "error": str(exc)})
                # #endregion
            if hasattr(self, "webcam_capture_panel"):
                self.webcam_capture_panel.Refresh(False)
            # #region agent log
            self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H1",
                location="create_controls_frame:before-hover-bindings",
                message="about to setup hover help bindings",
                data={"has_controls_frame": self.controls_frame is not None})
            # #endregion
            # #region agent log
            self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H1",
                location="create_controls_frame:after-hover-bindings",
                message="hover help bindings setup complete",
                data={})
            # #endregion
            wx.CallAfter(self.initialize_adjustable_columns)
        # #region agent log
            self.agent_debug_log(
                "H5",
                "create_controls_frame:exit",
                "create controls frame exit",
                {})
            # #endregion
        finally:
            self._controls_build_in_progress = False
            # #region agent log
            self.agent_debug_log(
                "H9",
                "create_controls_frame:build-flag-cleared",
                "controls build in progress flag cleared",
                {})
            # #endregion

    def create_capture_panel(self, parent):
        self.capture_panel = wx.Panel(parent, style=wx.RAISED_BORDER)
        self.capture_panel_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.capture_panel.SetSizer(self.capture_panel_sizer)
        self.capture_panel.SetAutoLayout(1)
        self.capture_panel.SetDoubleBuffered(True)

        self.source_image_panel = wx.Panel(
            self.capture_panel,
            size=(MainFrame.SOURCE_PREVIEW_SIZE, MainFrame.SOURCE_PREVIEW_SIZE),
            style=wx.SIMPLE_BORDER)
        self.source_image_panel.SetDoubleBuffered(True)
        self.source_image_panel.Bind(wx.EVT_PAINT, self.paint_source_image_panel)
        self.source_image_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)
        self.capture_panel_sizer.Add(self.source_image_panel, wx.SizerFlags(0).FixedMinSize().Border(wx.ALL, 5))

        self.webcam_container = wx.Panel(
            self.capture_panel,
            size=(MainFrame.WEBCAM_PREVIEW_WIDTH, MainFrame.WEBCAM_PREVIEW_HEIGHT))
        webcam_container_sizer = wx.BoxSizer(wx.VERTICAL)
        self.webcam_container.SetSizer(webcam_container_sizer)
        self.webcam_container.SetAutoLayout(1)
        self.webcam_container.SetDoubleBuffered(True)

        self.webcam_capture_panel = wx.Panel(
            self.webcam_container,
            size=(MainFrame.WEBCAM_PREVIEW_WIDTH, MainFrame.WEBCAM_PREVIEW_HEIGHT),
            style=wx.SIMPLE_BORDER)
        self.webcam_capture_panel.SetDoubleBuffered(True)
        self.webcam_capture_panel.Bind(wx.EVT_PAINT, self.paint_webcam_capture_panel)
        self.webcam_capture_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)
        self.webcam_capture_panel.Bind(wx.EVT_LEFT_DCLICK, self.on_webcam_preview_double_click)
        webcam_container_sizer.Add(self.webcam_capture_panel, wx.SizerFlags(0).FixedMinSize().Border(wx.ALL, 5))
        self.capture_panel_sizer.Add(
            self.webcam_container,
            wx.SizerFlags(0).FixedMinSize().Border(wx.ALL, 5))

        self.video_source_panel = wx.Panel(
            self.capture_panel,
            size=(MainFrame.VIDEO_SOURCE_COLUMN_MIN_WIDTH, MainFrame.WEBCAM_PREVIEW_HEIGHT + 10),
            style=wx.SIMPLE_BORDER)
        self.video_source_panel.SetMinSize(
            wx.Size(MainFrame.VIDEO_SOURCE_COLUMN_MIN_WIDTH, MainFrame.WEBCAM_PREVIEW_HEIGHT))
        video_source_sizer = wx.BoxSizer(wx.VERTICAL)
        self.video_source_panel.SetSizer(video_source_sizer)
        self.video_source_panel.SetAutoLayout(1)

        source_title = wx.StaticText(
            self.video_source_panel,
            label="摄像头输入源\nVideo Input Source")
        video_source_sizer.Add(source_title, 0, wx.EXPAND | wx.ALL, 6)

        self.video_source_choice = wx.Choice(self.video_source_panel, choices=[])
        self.video_source_choice.SetMinSize(wx.Size(MainFrame.VIDEO_SOURCE_COLUMN_MIN_WIDTH - 24, -1))
        self.video_source_choice.Bind(wx.EVT_CHOICE, self.on_video_source_choice_changed)
        video_source_sizer.Add(self.video_source_choice, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.refresh_video_sources_button = wx.Button(
            self.video_source_panel, wx.ID_ANY, "刷新设备列表 / Refresh Devices")
        self.refresh_video_sources_button.Bind(wx.EVT_BUTTON, self.on_refresh_video_sources_clicked)
        video_source_sizer.Add(self.refresh_video_sources_button, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.video_source_status_text = wx.StaticText(
            self.video_source_panel,
            label="尚未连接摄像头 / No camera connected",
            style=wx.ST_ELLIPSIZE_END)
        self.video_source_status_text.Wrap(MainFrame.VIDEO_SOURCE_COLUMN_MIN_WIDTH - 20)
        video_source_sizer.Add(self.video_source_status_text, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.capture_panel_sizer.Add(
            self.video_source_panel,
            wx.SizerFlags(0).FixedMinSize().Border(wx.ALL, 5))

        self.rotation_labels = {}
        self.rotation_value_labels = {}
        rotation_column = self.create_rotation_column(self.capture_panel, HEAD_ROTATIONS)
        self.capture_panel_sizer.Add(rotation_column, wx.SizerFlags(0).Expand().Border(wx.ALL, 3))

        # Aggressive startup path: skip automatic camera enumeration entirely.
        # User can trigger device scan manually via "Refresh Devices".
        # #region agent log
        self.agent_debug_log(
            "H14",
            "create_capture_panel:skip-startup-enumeration",
            "skipped startup camera enumeration",
            {})
        # #endregion

    def setup_hover_help_bindings(self):
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H2",
            location="setup_hover_help_bindings:entry",
            message="enter setup hover help bindings",
            data={"controls_frame_none": self.controls_frame is None})
        # #endregion
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
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H2",
            location="setup_hover_help_bindings:popup-created",
            message="hover popup and timer created",
            data={})
        # #endregion
        bind_start = time.time()
        control_count = self.count_controls_recursive(self.controls_frame)
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H5",
            location="setup_hover_help_bindings:before-bind-recursive",
            message="starting recursive hover binding",
            data={"control_count": control_count})
        # #endregion
        self.bind_hover_help_recursive(self.controls_frame)
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H5",
            location="setup_hover_help_bindings:after-bind-recursive",
            message="finished recursive hover binding",
            data={
                "control_count": control_count,
                "elapsed_ms": int((time.time() - bind_start) * 1000),
            })
        # #endregion

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
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H3",
            location="on_hover_help_toggle_changed:entry",
            message="hover help toggle changed",
            data={"enabled": self.is_hover_help_enabled()})
        # #endregion
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
            ("平滑系数", "这个值控制跟随平滑程度。越大越稳但响应更慢，越小越灵敏。"),
            ("近距曲率", "这个值控制人脸靠近镜头时的缩放曲线弯曲强度。"),
            ("远距曲率", "这个值控制人脸远离镜头时的缩放曲线弯曲强度。"),
            ("曲线弧度", "这个值控制整体缩放曲线的弧度形态。"),
            ("峰位横移", "这个值控制缩放曲线峰值位置左右偏移，用于调整中性点附近手感。"),
            ("朝向前方周期", "这个值控制自动重标定“朝向前方”的触发间隔（秒）。"),
            ("缩放周期", "这个值控制自动重标定“脸部大小基准”的触发间隔（秒）。"),
            ("背景", "这个值控制输出底色，用于抠像或外部合成背景匹配。"),
            ("镜像翻转输出", "这个值控制最终输出是否左右镜像。"),
            ("外挂图层", "这个值控制是否切换为外挂图层输出模式（会隐藏内置输出窗）。"),
            ("抗锯齿", "这个值控制渲染倍率；越高边缘更平滑，但性能开销更高。"),
            ("标定朝向", "这个操作会把当前朝向/人脸位置记为基准，后续自动跟随围绕该基准计算。"),
            ("加载上次模型", "这个操作会读取上次成功加载的模型并恢复到当前会话。"),
            ("加载其他模型", "这个操作会让你选择新的模型文件并加载。"),
            ("刷新设备列表", "这个操作会重新扫描可用摄像头/视频输入设备。"),
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
        # #region agent log
        self.agent_debug_log(
            "H4",
            "connect_default_video_source:entry",
            "connect default video source called",
            {})
        # #endregion
        if self.video_source_choice is None or self.video_source_choice.GetCount() == 0:
            return
        camera_labels = [
            label for label in self.video_source_choice.GetStrings()
            if "video file" not in label.lower()]
        if not camera_labels:
            return
        for label in camera_labels:
            if "droidcam" in label.lower():
                self.video_source_choice.SetStringSelection(label)
                self.on_video_source_choice_changed(wx.CommandEvent())
                return
        self.video_source_choice.SetStringSelection(camera_labels[0])
        self.on_video_source_choice_changed(wx.CommandEvent())

    def update_video_source_status_text(self, message: str):
        if self.video_source_status_text is not None:
            self.video_source_status_text.SetLabel(message)
            self.video_source_status_text.Wrap(MainFrame.VIDEO_SOURCE_COLUMN_MIN_WIDTH - 20)

    def release_video_capture(self):
        if getattr(self, "video_capture", None) is not None:
            try:
                self.video_capture.release()
            except Exception:
                pass
        self.video_capture = None
        self.current_video_capture_api = None

    def schedule_active_capture_timer(self):
        if hasattr(self, "capture_timer"):
            self.capture_timer.Start(MainFrame.CAPTURE_PROCESS_INTERVAL_MS)

    def schedule_idle_capture_timer(self):
        if hasattr(self, "capture_timer"):
            self.capture_timer.Start(MainFrame.CAPTURE_IDLE_INTERVAL_MS)

    def is_capture_source_active(self) -> bool:
        if self.video_source_kind == "image":
            return bool(self._image_file_path and os.path.isfile(self._image_file_path))
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
        if self.video_source_kind in ("file", "image"):
            return True
        return self.is_plausible_camera_frame(normalized)

    def read_capture_frame_bgr(self):
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
        if not self.full_controls_expanded:
            interval_ms = max(interval_ms, 66)
        return (time_now - self._last_mediapipe_process_time) >= (interval_ms / 1000.0)

    def draw_capture_status_message(self, message: str):
        if not self.is_capture_preview_visible():
            return
        dc = wx.MemoryDC()
        dc.SelectObject(self.webcam_capture_bitmap)
        self.draw_nothing_yet_string(dc, message)
        del dc
        if hasattr(self, "webcam_capture_panel"):
            self.webcam_capture_panel.Refresh(False)

    def update_capture_preview_bitmap(self, bgr_frame):
        preview_w = MainFrame.WEBCAM_PREVIEW_WIDTH
        preview_h = MainFrame.WEBCAM_PREVIEW_HEIGHT
        wx_bitmap = self.bgr_frame_to_preview_bitmap(
            bgr_frame,
            preview_w,
            preview_h,
            mirror=self.should_mirror_capture_preview())
        dc = wx.MemoryDC()
        dc.SelectObject(self.webcam_capture_bitmap)
        dc.Clear()
        dc.DrawBitmap(wx_bitmap, 0, 0, True)
        del dc

        if self.is_webcam_popup_visible():
            self.webcam_preview_popup_frame.preview_panel.Refresh(False)
        elif self.is_capture_preview_visible() and hasattr(self, "webcam_capture_panel"):
            self.webcam_capture_panel.Refresh(False)

    def refresh_video_source_choice_async(self, connect_after: bool = False, trigger_source: str = "manual"):
        refresh_start = time.time()
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H17",
            location="refresh_video_source_choice_async:entry",
            message="video source async refresh requested",
            data={
                "connect_after": bool(connect_after),
                "trigger_source": str(trigger_source),
                "enumeration_in_progress": bool(self._video_enumeration_in_progress),
            })
        # #endregion
        if self._video_enumeration_in_progress:
            return
        normalized_trigger = "auto" if str(trigger_source).lower() == "auto" else "manual"
        # #region agent log
        self.agent_debug_log(
            "H3",
            "refresh_video_source_choice_async:start",
            "camera enumeration started",
            {"connect_after": connect_after, "trigger_source": normalized_trigger})
        # #endregion
        self._video_enumeration_in_progress = True
        if normalized_trigger == "auto":
            self.update_video_source_status_text("自动加载摄像头中... / Auto loading camera...")
        else:
            self.update_video_source_status_text("手动刷新摄像头中... / Manual refresh in progress...")

        def worker():
            discovered = self.enumerate_camera_sources()
            # #region agent log
            self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H17",
                location="refresh_video_source_choice_async:worker-finished",
                message="camera enumeration worker finished",
                data={
                    "camera_count": len(discovered),
                    "elapsed_ms": int((time.time() - refresh_start) * 1000),
                })
            # #endregion
            wx.CallAfter(self._apply_video_source_choices, discovered, connect_after, normalized_trigger)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_video_source_choices(self,
                                    discovered_cameras: list[dict[str, object]],
                                    connect_after: bool,
                                    trigger_source: str = "manual"):
        self._video_enumeration_in_progress = False
        # #region agent log
        self.agent_debug_log(
            "H3",
            "_apply_video_source_choices:entry",
            "camera enumeration completed",
            {
                "camera_count": len(discovered_cameras),
                "connect_after": connect_after,
                "trigger_source": trigger_source,
            })
        # #endregion
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
        duplicate_count = len(choices) - len(set(choices))
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H13",
            location="_apply_video_source_choices:before-setitems",
            message="video source choices prepared",
            data={
                "camera_count": len(discovered_cameras),
                "choices_count": len(choices),
                "duplicate_count": duplicate_count,
                "trigger_source": trigger_source,
            })
        # #endregion

        self.video_source_choice.SetItems(choices)
        if previous_selection in choices:
            self.video_source_choice.SetStringSelection(previous_selection)
        elif self.video_source_choice.GetCount() > 0:
            self.video_source_choice.SetSelection(0)

        self.update_video_source_status_text(
            f"发现 {len(choices) - 1} 个摄像头 / Found {max(0, len(choices) - 1)} camera(s)")

        if connect_after:
            if trigger_source == "auto":
                self.update_video_source_status_text("自动连接摄像头中... / Auto connecting camera...")
            else:
                self.update_video_source_status_text("正在连接所选摄像头... / Connecting selected camera...")
            self.connect_default_video_source()

    def refresh_video_source_choice(self):
        self.refresh_video_source_choice_async(connect_after=False, trigger_source="manual")

    def on_refresh_video_sources_clicked(self, event: wx.Event):
        self.refresh_video_source_choice_async(connect_after=True, trigger_source="manual")

    def on_video_source_choice_changed(self, event: wx.Event):
        if self.video_source_choice is None:
            return
        label = self.video_source_choice.GetStringSelection()
        source_entry = self.video_source_choice_map.get(label)
        if source_entry is None:
            return
        kind, value, source_api = source_entry
        if kind == "camera":
            api_preference = int(source_api) if source_api is not None else None
            is_droidcam_source = "droidcam" in label.lower()
            self.set_video_capture_camera(
                int(value),
                api_preference,
                avoid_dshow_fallback=is_droidcam_source)
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
                                 api_preference: Optional[int] = None,
                                 avoid_dshow_fallback: bool = False):
        capture_start_time = time.time()
        # #region agent log
        self.agent_debug_log(
            "H4",
            "set_video_capture_camera:start",
            "set video capture camera started",
            {
                "cam_index": cam_index,
                "api_preference": api_preference,
                "avoid_dshow_fallback": avoid_dshow_fallback
            })
        # #endregion
        self.release_video_capture()
        self.video_source_kind = "camera"
        self._image_file_path = None
        self._last_good_webcam_bgr_frame = None

        open_attempts: list[int] = []
        if api_preference is not None:
            open_attempts.append(api_preference)
        if (not avoid_dshow_fallback) and hasattr(cv2, "CAP_DSHOW") and cv2.CAP_DSHOW not in open_attempts:
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
                    # #region agent log
                    self.agent_debug_log(
                        "H4",
                        "set_video_capture_camera:success",
                        "set video capture camera success",
                        {
                            "cam_index": cam_index,
                            "backend_api": backend_api,
                            "elapsed_ms": int((time.time() - capture_start_time) * 1000)
                        })
                    # #endregion
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
        # #region agent log
        self.agent_debug_log(
            "H4",
            "set_video_capture_camera:failed",
            "set video capture camera failed",
            {
                "cam_index": cam_index,
                "elapsed_ms": int((time.time() - capture_start_time) * 1000),
                "last_error": self.video_capture_status_message
            })
        # #endregion

    def set_video_capture_file(self, file_path: str):
        try:
            self.release_video_capture()
            self._last_good_webcam_bgr_frame = None
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
        bgr_frame = self.normalize_bgr_frame(bgr_frame)
        if bgr_frame is None:
            return self.webcam_capture_bitmap

        rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
        if mirror:
            rgb_frame = cv2.flip(rgb_frame, 1)
        resized_frame = cv2.resize(
            rgb_frame,
            (preview_width, preview_height),
            interpolation=cv2.INTER_AREA)
        resized_frame = numpy.ascontiguousarray(resized_frame, dtype=numpy.uint8)
        wx_image = wx.Image(preview_width, preview_height)
        wx_image.SetData(resized_frame.tobytes())
        return wx_image.ConvertToBitmap()

    def create_postprocess_panel(self, parent):
        self.postprocess_panel = wx.Panel(parent, style=wx.SIMPLE_BORDER)
        self.postprocess_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.postprocess_panel.SetSizer(self.postprocess_panel_sizer)
        self.postprocess_panel.SetAutoLayout(1)
        self.postprocess_panel.SetDoubleBuffered(True)

        enable_direction_calibration = self.enable_direction_calibration_checkbox.GetValue()
        direction_interval_seconds = self.auto_direction_calibration_interval_seconds_ctrl.GetValue()
        enable_scale_calibration = self.enable_scale_calibration_checkbox.GetValue()
        scale_interval_seconds = self.auto_scale_calibration_interval_seconds_ctrl.GetValue()
        output_background_hex = self.get_output_background_hex()
        mirror_output = self.mirror_output_checkbox.GetValue()
        external_layer_output_enabled = self.external_layer_output_checkbox.GetValue()
        antialias_strength = self.antialias_strength_spin.GetValue()
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H4",
            location="create_postprocess_panel:state-read",
            message="postprocess panel initial state read",
            data={
                "external_layer_output_enabled": bool(external_layer_output_enabled),
            })
        # #endregion

        postprocess_text = wx.StaticText(
            self.postprocess_panel, label="--- 后处理和其他 / Postprocess & Other ---", style=wx.ALIGN_CENTER)
        self.postprocess_panel_sizer.Add(postprocess_text, 0, wx.EXPAND)

        self.tha3_model_variant_label = wx.StaticText(
            self.postprocess_panel, label="THA3 模型变体 / THA3 Model Variant")
        self.postprocess_panel_sizer.Add(
            self.tha3_model_variant_label,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        variant_labels = [label for _, label in THA3_VARIANT_CHOICES]
        variant_index = 0
        for index, (variant_id, _) in enumerate(THA3_VARIANT_CHOICES):
            if variant_id == self.tha3_model_variant:
                variant_index = index
                break
        self.tha3_model_variant_choice = wx.Choice(
            self.postprocess_panel, choices=variant_labels)
        self.tha3_model_variant_choice.SetSelection(variant_index)
        self.tha3_model_variant_choice.Bind(wx.EVT_CHOICE, self.on_tha3_model_variant_changed)
        self.postprocess_panel_sizer.Add(
            self.tha3_model_variant_choice,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.enable_direction_calibration_checkbox = wx.CheckBox(
            self.postprocess_panel,
            label="周期执行「我正看前方」/ Auto Calibrate Forward Gaze")
        self.enable_direction_calibration_checkbox.SetValue(enable_direction_calibration)
        self.enable_direction_calibration_checkbox.Bind(wx.EVT_CHECKBOX, self.on_display_transform_control_changed)
        self.postprocess_panel_sizer.Add(
            self.enable_direction_calibration_checkbox,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.calibrate_neutral_button = wx.Button(
            self.postprocess_panel,
            label="标定朝向 / Calibrate Head Orientation")
        self.calibrate_neutral_button.Bind(wx.EVT_BUTTON, self.calibrate_neutral_clicked)
        self.postprocess_panel_sizer.Add(
            self.calibrate_neutral_button,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.direction_calibration_interval_panel = wx.Panel(self.postprocess_panel)
        direction_calibration_interval_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.direction_calibration_interval_panel.SetSizer(direction_calibration_interval_sizer)
        self.direction_calibration_interval_panel.SetAutoLayout(1)
        self.postprocess_panel_sizer.Add(self.direction_calibration_interval_panel, 0, wx.EXPAND)

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
        self.auto_direction_calibration_interval_seconds_ctrl.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_display_transform_control_changed)
        self.auto_direction_calibration_interval_seconds_ctrl.Bind(wx.EVT_TEXT, self.on_display_transform_control_changed)
        direction_calibration_interval_sizer.Add(
            self.auto_direction_calibration_interval_seconds_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        self.enable_scale_calibration_checkbox = wx.CheckBox(
            self.postprocess_panel, label="启用缩放自动校准 / Enable Auto Scale Calibration")
        self.enable_scale_calibration_checkbox.SetValue(enable_scale_calibration)
        self.enable_scale_calibration_checkbox.Bind(wx.EVT_CHECKBOX, self.on_display_transform_control_changed)
        self.postprocess_panel_sizer.Add(
            self.enable_scale_calibration_checkbox,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.calibrate_scale_button = wx.Button(
            self.postprocess_panel,
            label="自动缩放校准 / Auto Scale Calibration")
        self.calibrate_scale_button.Bind(wx.EVT_BUTTON, self.calibrate_scale_clicked)
        self.postprocess_panel_sizer.Add(
            self.calibrate_scale_button,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.scale_calibration_interval_panel = wx.Panel(self.postprocess_panel)
        scale_calibration_interval_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.scale_calibration_interval_panel.SetSizer(scale_calibration_interval_sizer)
        self.scale_calibration_interval_panel.SetAutoLayout(1)
        self.postprocess_panel_sizer.Add(self.scale_calibration_interval_panel, 0, wx.EXPAND)

        scale_interval_label = wx.StaticText(
            self.scale_calibration_interval_panel,
            label=slider_label("缩放周期", "Scale Interval", "秒", "s"))
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
        self.auto_scale_calibration_interval_seconds_ctrl.Bind(wx.EVT_SPINCTRLDOUBLE, self.on_display_transform_control_changed)
        self.auto_scale_calibration_interval_seconds_ctrl.Bind(wx.EVT_TEXT, self.on_display_transform_control_changed)
        scale_calibration_interval_sizer.Add(
            self.auto_scale_calibration_interval_seconds_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        background_label = wx.StaticText(self.postprocess_panel, label="背景 / Background")
        self.postprocess_panel_sizer.Add(background_label, wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.output_background_choice = wx.ColourPickerCtrl(
            self.postprocess_panel,
            colour=wx.Colour(output_background_hex))
        self.output_background_choice.Bind(wx.EVT_COLOURPICKER_CHANGED, self.on_output_background_changed)
        self.postprocess_panel_sizer.Add(
            self.output_background_choice,
            wx.SizerFlags().Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        self.mirror_output_checkbox = wx.CheckBox(
            self.postprocess_panel, label="镜像翻转输出 / Mirror Output")
        self.mirror_output_checkbox.SetValue(mirror_output)
        self.mirror_output_checkbox.Bind(wx.EVT_CHECKBOX, self.on_display_transform_control_changed)
        self.postprocess_panel_sizer.Add(
            self.mirror_output_checkbox,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.external_layer_output_checkbox = wx.CheckBox(
            self.postprocess_panel,
            label="向外挂图层系统输出（隐藏内置输出窗）/ Output to External Layer System")
        self.external_layer_output_checkbox.SetValue(external_layer_output_enabled)
        self.external_layer_output_checkbox.Bind(wx.EVT_CHECKBOX, self.on_external_layer_output_changed)
        self.postprocess_panel_sizer.Add(
            self.external_layer_output_checkbox,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.external_layer_output_status_text = wx.StaticText(
            self.postprocess_panel,
            label="",
            style=wx.ALIGN_LEFT)
        self.postprocess_panel_sizer.Add(
            self.external_layer_output_status_text,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4).Expand())

        postprocess_control_panel = wx.Panel(self.postprocess_panel)
        postprocess_control_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        postprocess_control_panel.SetSizer(postprocess_control_panel_sizer)
        postprocess_control_panel.SetAutoLayout(1)
        self.postprocess_panel_sizer.Add(postprocess_control_panel, 0, wx.EXPAND)

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

        self.postprocess_panel_sizer.Fit(self.postprocess_panel)
        self.apply_external_layer_output_visibility()
        wx.CallAfter(self.refresh_image_source_ui_visibility)

    def paint_webcam_capture_panel(self, event: wx.Event):
        wx.BufferedPaintDC(self.webcam_capture_panel, self.webcam_capture_bitmap)

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

    def update_load_model_buttons(self):
        if hasattr(self, "load_last_model_button"):
            self.load_last_model_button.Enable(bool(self.last_loaded_model_path))
        if hasattr(self, "quick_load_last_model_button"):
            self.quick_load_last_model_button.Enable(bool(self.last_loaded_model_path))
        tha3_last_ready = bool(self.last_tha3_character_png) and os.path.isfile(self.last_tha3_character_png)
        if hasattr(self, "load_last_tha3_png_button"):
            self.load_last_tha3_png_button.Enable(tha3_last_ready)

    def show_full_controls_window(self):
        show_start_time = time.time()
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H16",
            location="show_full_controls_window:entry",
            message="show full controls requested",
            data={
                "has_controls_frame": self.controls_frame is not None,
                "full_controls_expanded": bool(self.full_controls_expanded),
            })
        # #endregion
        # #region agent log
        self.agent_debug_log(
            "H1",
            "show_full_controls_window:entry",
            "show full controls requested",
            {"restoring_geometry": self._restoring_window_geometry})
        # #endregion
        if not self._restoring_window_geometry:
            self.save_persistent_ui_state()
        self.reload_persistent_ui_state_from_disk()
        self.apply_mouth_persistent_state_to_args()
        self.apply_persistent_slider_value_states()
        self.create_controls_frame()
        # #region agent log
        self.agent_debug_log(
            "H1",
            "show_full_controls_window:after-create",
            "controls frame created",
            {"has_controls_frame": self.controls_frame is not None})
        # #endregion
        self.full_controls_expanded = True
        self.refresh_model_loaded_ui_state()
        self.ensure_application_windows_visible()
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H6",
            location="show_full_controls_window:after-ensure-visible",
            message="ensure_application_windows_visible complete",
            data={"elapsed_ms": int((time.time() - show_start_time) * 1000)})
        # #endregion
        # #region agent log
        self.agent_debug_log(
            "H1",
            "show_full_controls_window:after-ensure-visible",
            "ensure windows visible returned",
            {"controls_shown": bool(self.controls_frame and self.controls_frame.IsShown())})
        # #endregion
        if not self.is_external_layer_output_enabled():
            self.ensure_output_frame()
        else:
            self.hide_builtin_output_frame()
        self.initialize_output_bitmap()
        if not self.is_external_layer_output_enabled():
            self.refresh_output_frame_chrome()
            if getattr(self, "output_frame", None) is not None:
                self.output_frame.result_image_panel.Refresh(False)
        wx.CallAfter(self.initialize_adjustable_columns)
        wx.CallAfter(lambda: self.adapt_main_window_to_controls(initial=not self._controls_geometry_restored))
        self.schedule_refresh_controls_scrolling()
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H7",
            location="show_full_controls_window:exit-performance",
            message="full controls startup path finished",
            data={"elapsed_ms": int((time.time() - show_start_time) * 1000)})
        # #endregion
        # #region agent log
        self.agent_debug_log(
            "H1",
            "show_full_controls_window:exit",
            "show full controls scheduling complete",
            {"elapsed_ms": int((time.time() - show_start_time) * 1000)})
        # #endregion

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

    def calibrate_head_orientation_quick(self, event: wx.Event):
        time_now = time.time()
        calibration_ok = self.pose_converter.apply_face_orientation_calibration()
        if not calibration_ok:
            self.refresh_auto_transform_status("NO FACE")
            return

        self.last_direction_calibration_time = time_now
        if self.latest_face_screen_motion is not None:
            # Keep quick calibration consistent with full-panel calibration behavior.
            self.apply_neutral_calibration(
                self.latest_face_screen_motion,
                reset_display_state=True,
                calibration_time=time_now)
        self.update_display_transform_state(snap_to_target=True)
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
        self.save_persistent_ui_state()

    def calibrate_scale_clicked(self, event: wx.Event):
        if self.latest_face_screen_motion is None:
            self.refresh_auto_transform_status("NO FACE")
            event.Skip()
            return

        time_now = time.time()
        self.update_neutral_face_size(self.latest_face_screen_motion)
        self.last_scale_calibration_time = time_now
        self.refresh_scale_curve_status()
        self.request_scale_curve_repaint(force=True)
        self.update_display_transform_state(snap_to_target=not self.enable_auto_transform_checkbox.GetValue())
        self.refresh_auto_transform_status("READY" if self.enable_auto_transform_checkbox.GetValue() else "OFF")
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
        self.save_persistent_ui_state()
        event.Skip()

    def is_model_loaded(self) -> bool:
        if self.get_image_source_mode() == IMAGE_SOURCE_THA3:
            return self.active_image_source.is_ready(self)
        return self.poser is not None and self.torch_source_image is not None and self.wx_source_image is not None

    def get_image_source_mode(self) -> str:
        return normalize_image_source_mode(getattr(self, "image_source_mode", IMAGE_SOURCE_THA4))

    def refresh_image_source_ui_visibility(self):
        spec = self.active_image_source.get_load_ui_spec()
        quick_button = getattr(self, "quick_load_last_model_button", None)
        if quick_button is not None:
            quick_button.Show(spec.show_yaml_loader)
        if hasattr(self, "tha3_model_variant_choice"):
            self.tha3_model_variant_choice.Show(spec.show_tha3_variant)
        if hasattr(self, "tha3_model_variant_label"):
            self.tha3_model_variant_label.Show(spec.show_tha3_variant)
        if hasattr(self, "controls_frame") and self.controls_frame is not None:
            self.controls_frame.Layout()
        self.update_load_model_buttons()

    def on_tha3_model_variant_changed(self, event: wx.Event):
        if not hasattr(self, "tha3_model_variant_choice"):
            event.Skip()
            return
        self.tha3_model_variant = THA3_VARIANT_CHOICES[self.tha3_model_variant_choice.GetSelection()][0]
        self.save_persistent_ui_state()
        if self.get_image_source_mode() == IMAGE_SOURCE_THA3 and self.last_tha3_character_png:
            switch_image_source(self, IMAGE_SOURCE_THA3)
            if os.path.isfile(self.last_tha3_character_png):
                self.active_image_source.load_asset(self, self.last_tha3_character_png)
        event.Skip()

    def load_tha3_character_png(self, event: wx.Event):
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
            self.active_image_source.load_asset(self, png_path)
            self.update_load_model_buttons()
        file_dialog.Destroy()
        event.Skip()

    def load_last_tha3_character_png(self, event: wx.Event):
        self.refresh_video_source_choice_async(connect_after=True, trigger_source="manual")
        if not self.last_tha3_character_png:
            return
        if not os.path.isfile(self.last_tha3_character_png):
            invalid_path = self.last_tha3_character_png
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
        if self.get_image_source_mode() != IMAGE_SOURCE_THA3:
            switch_image_source(self, IMAGE_SOURCE_THA3)
        self.active_image_source.load_asset(self, self.last_tha3_character_png)
        self.update_load_model_buttons()
        event.Skip()

    def get_dialog_parent(self) -> wx.Window:
        if self.controls_frame is not None and self.controls_frame.IsShown():
            return self.controls_frame
        return self

    def refresh_model_loaded_ui_state(self):
        # #region agent log
        self.agent_debug_log(
            "H6",
            "refresh_model_loaded_ui_state:entry",
            "refresh model loaded ui state entry",
            {"is_model_loaded": self.is_model_loaded()})
        # #endregion
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
        self.update_load_model_buttons()
        # #region agent log
        self.agent_debug_log(
            "H6",
            "refresh_model_loaded_ui_state:exit",
            "refresh model loaded ui state exit",
            {})
        # #endregion

    def on_output_background_changed(self, event: wx.Event):
        self.last_background_choice = ""
        self.refresh_output_frame_chrome()
        self.save_persistent_ui_state()
        if self.poser is None:
            return

        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
            return

        if self.mediapipe_face_pose is None:
            self.render_default_pose_load_preview()
        else:
            self.update_result_image_bitmap()

    def on_display_transform_control_changed(self, event: Optional[wx.Event] = None):
        control_change_start = time.time()
        # #region agent log
        self.agent_debug_log(
            "H5",
            "on_display_transform_control_changed:entry",
            "display transform control changed entry",
            {})
        # #endregion
        if hasattr(self, "direction_calibration_interval_panel"):
            self.direction_calibration_interval_panel.Enable(self.enable_direction_calibration_checkbox.GetValue())
        if hasattr(self, "scale_calibration_interval_panel"):
            self.scale_calibration_interval_panel.Enable(self.enable_scale_calibration_checkbox.GetValue())
        # #region agent log
        self.agent_debug_log(
            "H7",
            "on_display_transform_control_changed:after-enable-panels",
            "enabled calibration interval panels",
            {})
        # #endregion
        self.save_persistent_ui_state()
        # #region agent log
        self.agent_debug_log(
            "H7",
            "on_display_transform_control_changed:after-save-state",
            "saved persistent ui state",
            {})
        # #endregion
        self.update_display_transform_state(snap_to_target=not self.enable_auto_transform_checkbox.GetValue())
        # #region agent log
        self.agent_debug_log(
            "H7",
            "on_display_transform_control_changed:after-update-display-transform",
            "updated display transform state",
            {})
        # #endregion
        self.refresh_scale_curve_status()
        # #region agent log
        self.agent_debug_log(
            "H7",
            "on_display_transform_control_changed:after-refresh-scale-status",
            "refreshed scale curve status",
            {})
        # #endregion
        self.request_scale_curve_repaint(force=True)
        # #region agent log
        self.agent_debug_log(
            "H7",
            "on_display_transform_control_changed:after-request-repaint",
            "requested scale curve repaint",
            {})
        # #endregion
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)
        # #region agent log
        self.agent_debug_log(
            "H5",
            "on_display_transform_control_changed:exit",
            "display transform control changed exit",
            {"elapsed_ms": int((time.time() - control_change_start) * 1000)})
        # #endregion

    def calibrate_neutral_clicked(self, event: wx.Event):
        if self.latest_face_screen_motion is None:
            self.refresh_auto_transform_status("NO FACE")
            return

        self.apply_neutral_calibration(self.latest_face_screen_motion, reset_display_state=True)
        self.refresh_scale_curve_status()
        self.request_scale_curve_repaint(force=True)
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)

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

    def update_neutral_face_size(self, face_screen_motion: FaceScreenMotion):
        if self.neutral_face_screen_motion is None:
            self.set_neutral_face_screen_motion(face_screen_motion)
            return
        self.neutral_face_screen_motion = FaceScreenMotion(
            center_x=self.neutral_face_screen_motion.center_x,
            center_y=self.neutral_face_screen_motion.center_y,
            face_size=face_screen_motion.face_size)

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
            self.update_neutral_face_size(face_screen_motion)
            self.last_scale_calibration_time = time_value
        else:
            self.last_scale_calibration_time = None

    def try_apply_auto_forward_gaze_calibration(self, time_now: float, *, respect_interval: bool) -> bool:
        """Periodic or on-load auto run of model-input Calibrate Forward Gaze."""
        if not self.enable_direction_calibration_checkbox.GetValue():
            return False

        interval_seconds = max(1.0, self.auto_direction_calibration_interval_seconds_ctrl.GetValue())
        if respect_interval:
            if self.last_direction_calibration_time is None:
                self.last_direction_calibration_time = time_now
                return False
            if time_now - self.last_direction_calibration_time < interval_seconds:
                return False

        if not self.pose_converter.apply_face_orientation_calibration():
            return False

        self.last_direction_calibration_time = time_now
        return True

    def maybe_apply_periodic_direction_calibration(self):
        self.try_apply_auto_forward_gaze_calibration(time.time(), respect_interval=True)

    def maybe_apply_periodic_scale_calibration(self, latest_motion: FaceScreenMotion):
        if not self.enable_scale_calibration_checkbox.GetValue():
            return

        interval_seconds = max(1.0, self.auto_scale_calibration_interval_seconds_ctrl.GetValue())
        time_now = time.time()
        if self.last_scale_calibration_time is None:
            self.last_scale_calibration_time = time_now
            return

        if time_now - self.last_scale_calibration_time < interval_seconds:
            return

        self.update_neutral_face_size(latest_motion)
        self.last_scale_calibration_time = time_now

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
        if not force and now - self._last_scale_curve_refresh_time < 0.08:
            return
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
        # #region agent log
        self.agent_debug_log(
            "H8",
            "update_display_transform_state:entry",
            "update display transform state entry",
            {"snap_to_target": snap_to_target})
        # #endregion
        enabled = self.enable_auto_transform_checkbox.GetValue()
        old_offset_x = self.display_offset_x
        old_offset_y = self.display_offset_y
        old_scale = self.display_scale
        old_rotation_deg = self.display_rotation_deg

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
                    self.maybe_apply_periodic_direction_calibration()
                    self.maybe_apply_periodic_scale_calibration(latest_motion)
                neutral_motion = self.neutral_face_screen_motion
                target_offset_x = (latest_motion.center_x - neutral_motion.center_x) * self.move_x_gain_spin.GetValue()
                target_offset_y = (latest_motion.center_y - neutral_motion.center_y) * self.move_y_gain_spin.GetValue()
                target_scale = self.compute_target_scale(latest_motion.face_size, neutral_motion.face_size)
                tilt_limit = max(0.0, self.tilt_limit_spin.GetValue())
                head_roll_delta = (self.latest_head_roll_deg if self.latest_head_roll_deg is not None else 0.0) \
                    - self.neutral_head_roll_deg
                if not self.invert_tilt_mapping_checkbox.GetValue():
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
        self.refresh_auto_transform_status(mode)
        self.refresh_scale_curve_status()
        self.request_scale_curve_repaint(force=False)
        changed = abs(self.display_offset_x - old_offset_x) > 0.25 \
            or abs(self.display_offset_y - old_offset_y) > 0.25 \
            or abs(self.display_scale - old_scale) > 0.002 \
            or abs(self.display_rotation_deg - old_rotation_deg) > 0.05
        # #region agent log
        self.agent_debug_log(
            "H8",
            "update_display_transform_state:exit",
            "update display transform state exit",
            {"changed": changed, "mode": mode})
        # #endregion

        return changed

    def update_capture_panel(self, event: wx.Event):
        self._capture_frame_serial += 1
        time_now = time.time()

        if not self.is_capture_source_active():
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
                return
        else:
            self._last_good_webcam_bgr_frame = bgr_frame
            self.video_capture_status_message = None

        if self.should_update_capture_preview_ui(time_now):
            self._last_preview_ui_time = time_now
            self.update_capture_preview_bitmap(bgr_frame)

        if self.should_process_mediapipe(time_now):
            self._last_mediapipe_process_time = time_now
            rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            if self.should_mirror_capture_preview():
                rgb_frame = cv2.flip(rgb_frame, 1)
            time_ms = int(time_now * 1000)
            mediapipe_image = mediapipe.Image(image_format=mediapipe.ImageFormat.SRGB, data=rgb_frame)
            detection_result = self.face_landmarker.detect_for_video(mediapipe_image, time_ms)
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
        if self._capture_frame_serial % 6 == 0:
            self.refresh_scale_curve_status()
            self.request_scale_curve_repaint(force=False)

    @staticmethod
    def convert_to_100(x):
        return int(max(0.0, min(1.0, x)) * 100)

    def paint_source_image_panel(self, event: wx.Event):
        wx.BufferedPaintDC(self.source_image_panel, self.source_image_bitmap)

    def update_source_image_bitmap(self):
        source_bitmap_start = time.time()
        # #region agent log
        self.agent_debug_log(
            "H5",
            "update_source_image_bitmap:entry",
            "update source image bitmap entry",
            {"has_source_image": self.wx_source_image is not None})
        # #endregion
        if hasattr(self, "source_image_panel"):
            source_panel_size = self.source_image_panel.GetClientSize()
            width = max(1, source_panel_size.x)
            height = max(1, source_panel_size.y)
            if self.source_image_bitmap.GetWidth() != width or self.source_image_bitmap.GetHeight() != height:
                self.source_image_bitmap = wx.Bitmap(width, height)
        dc = wx.MemoryDC()
        dc.SelectObject(self.source_image_bitmap)
        if self.wx_source_image is None:
            self.draw_nothing_yet_string(dc)
        else:
            dc.Clear()
            draw_bitmap = self.wx_source_image
            if self.wx_source_image.GetWidth() != self.source_image_bitmap.GetWidth() \
                    or self.wx_source_image.GetHeight() != self.source_image_bitmap.GetHeight():
                draw_bitmap = self.wx_source_image.ConvertToImage().Scale(
                    self.source_image_bitmap.GetWidth(),
                    self.source_image_bitmap.GetHeight(),
                    wx.IMAGE_QUALITY_HIGH).ConvertToBitmap()
            dc.DrawBitmap(draw_bitmap, 0, 0, True)
        del dc
        if hasattr(self, "source_image_panel"):
            self.source_image_panel.Refresh(False)
        # #region agent log
        self.agent_debug_log(
            "H5",
            "update_source_image_bitmap:exit",
            "update source image bitmap exit",
            {"elapsed_ms": int((time.time() - source_bitmap_start) * 1000)})
        # #endregion

    def draw_nothing_yet_string(self, dc, message: str = "Nothing yet!"):
        canvas_width, canvas_height = dc.GetSize()
        self.paint_output_background(dc, wx.Size(canvas_width, canvas_height))
        font = wx.Font(wx.FontInfo(14).Family(wx.FONTFAMILY_SWISS))
        dc.SetFont(font)
        w, h = dc.GetTextExtent(message)
        canvas_width, canvas_height = dc.GetSize()
        dc.DrawText(message, (canvas_width - w) // 2, (canvas_height - h) // 2)

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

    def render_pose_to_wx_image(self, pose_list: List[float]) -> Optional[wx.Image]:
        if self.poser is None or self.torch_source_image is None:
            return None

        pose = torch.tensor(pose_list, device=self.device, dtype=self.poser.get_dtype())

        with torch.no_grad():
            output_image = self.poser.pose(self.torch_source_image, pose)[0].float()
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

    def draw_cached_result_image(self, banner_text: Optional[str] = None):
        if self.last_output_wx_image is None:
            return
        self.draw_result_wx_image(self.last_output_wx_image, banner_text)

    def draw_result_wx_image(self, wx_image: wx.Image, banner_text: Optional[str] = None):
        self.ensure_result_bitmap_size()
        canvas_width, canvas_height = self.get_output_canvas_size()
        antialias_factor = 1.0
        if hasattr(self, "antialias_strength_spin"):
            antialias_factor = max(1.0, self.antialias_strength_spin.GetValue())
        render_canvas_width = max(1, int(round(canvas_width * antialias_factor)))
        render_canvas_height = max(1, int(round(canvas_height * antialias_factor)))
        scaled_width = max(1, int(round(wx_image.GetWidth() * max(0.1, self.display_scale) * antialias_factor)))
        scaled_height = max(1, int(round(wx_image.GetHeight() * max(0.1, self.display_scale) * antialias_factor)))
        if scaled_width != wx_image.GetWidth() or scaled_height != wx_image.GetHeight():
            transformed_image = wx_image.Scale(scaled_width, scaled_height, wx.IMAGE_QUALITY_HIGH)
        else:
            transformed_image = wx_image
        wx_bitmap = transformed_image.ConvertToBitmap()

        composition_bitmap = self.create_composition_bitmap(render_canvas_width, render_canvas_height)
        composition_dc = wx.MemoryDC()
        composition_dc.SelectObject(composition_bitmap)
        anchor_x = (canvas_width / 2.0 + self.display_offset_x) * antialias_factor
        anchor_y = (canvas_height + self.display_offset_y) * antialias_factor
        gc = wx.GraphicsContext.Create(composition_dc)
        if gc is not None:
            gc.PushState()
            gc.Translate(anchor_x, anchor_y)
            if abs(self.display_rotation_deg) > 1e-4:
                gc.Rotate(math.radians(self.display_rotation_deg))
            gc.DrawBitmap(wx_bitmap,
                          -transformed_image.GetWidth() / 2.0,
                          -transformed_image.GetHeight(),
                          transformed_image.GetWidth(),
                          transformed_image.GetHeight())
            gc.PopState()
        else:
            draw_x = int(round(anchor_x - transformed_image.GetWidth() / 2.0))
            draw_y = int(round(anchor_y - transformed_image.GetHeight()))
            composition_dc.DrawBitmap(wx_bitmap, draw_x, draw_y, True)

        composition_dc.SelectObject(wx.NullBitmap)

        if self.mirror_output_checkbox.GetValue() or antialias_factor > 1.001:
            final_image = composition_bitmap.ConvertToImage()
            if self.mirror_output_checkbox.GetValue():
                final_image = final_image.Mirror(horizontally=True)
            if antialias_factor > 1.001:
                final_image = final_image.Scale(canvas_width, canvas_height, wx.IMAGE_QUALITY_HIGH)
            final_bitmap = final_image.ConvertToBitmap()
        else:
            final_bitmap = composition_bitmap

        dc = wx.MemoryDC()
        dc.SelectObject(self.result_image_bitmap)
        self.paint_output_background(dc, wx.Size(canvas_width, canvas_height))
        dc.DrawBitmap(final_bitmap, 0, 0, False)
        if banner_text:
            font = wx.Font(wx.FontInfo(11).Family(wx.FONTFAMILY_SWISS).Weight(wx.FONTWEIGHT_BOLD))
            dc.SetFont(font)
            dc.SetTextForeground(wx.Colour(255, 220, 0))
            dc.SetBackgroundMode(wx.TRANSPARENT)
            tw, th = dc.GetTextExtent(banner_text)
            dc.DrawText(banner_text, 8, canvas_height - th - 8)
        del composition_dc
        del dc

        self.last_banner_text = banner_text
        self.last_background_choice = self.get_output_background_signature()
        if self.is_external_layer_output_enabled():
            self._external_layer_output_frame_sequence += 1
            ExternalLayerOutputBridge.publish_composite_frame(
                self,
                frame_sequence=self._external_layer_output_frame_sequence,
                banner_text=banner_text)
        else:
            self.refresh_output_frame_chrome()
            if getattr(self, "output_frame", None) is not None and self.output_frame:
                self.output_frame.result_image_panel.Refresh(False)

    def render_pose_to_result_bitmap(self, pose_list: List[float], banner_text: Optional[str] = None):
        wx_image = self.render_pose_to_wx_image(pose_list)
        if wx_image is None:
            return

        self.last_output_wx_image = wx_image
        self.last_background_choice = self.get_output_background_signature()
        self.draw_result_wx_image(wx_image, banner_text)

    def render_default_pose_load_preview(self):
        default_pose = self.get_default_pose_list()
        self.last_pose = default_pose
        self.render_pose_to_result_bitmap(default_pose, MainFrame.LOAD_PREVIEW_BANNER)
        self._load_preview_shown = True
        if hasattr(self, "fps_text"):
            self.set_wrapped_static_text_if_changed(self.fps_text, "预览 / Preview\nNo face input")

    def tick_tha4_student_source(self) -> Optional[str]:
        if self.poser is None:
            self.initialize_output_bitmap()
            dc = wx.MemoryDC()
            dc.SelectObject(self.result_image_bitmap)
            self.draw_nothing_yet_string(dc)
            dc.SelectObject(wx.NullBitmap)
            if getattr(self, "output_frame", None) is not None:
                self.output_frame.result_image_panel.Refresh(False)
            return "no_model"

        display_transform_changed = self.update_display_transform_state()
        if self.mediapipe_face_pose is None:
            if display_transform_changed and self.last_output_wx_image is not None:
                self.draw_cached_result_image(self.last_banner_text)
            return "no_face"

        current_pose = self.pose_converter.convert(self.mediapipe_face_pose)
        current_pose = self.apply_negative_tilt_limit_to_pose(current_pose)
        if self.torch_source_image is None:
            self.initialize_output_bitmap()
            dc = wx.MemoryDC()
            dc.SelectObject(self.result_image_bitmap)
            self.draw_nothing_yet_string(dc)
            dc.SelectObject(wx.NullBitmap)
            if getattr(self, "output_frame", None) is not None:
                self.output_frame.result_image_panel.Refresh(False)
            return "no_model"

        pose_changed = self.last_pose is None or self.last_pose != current_pose
        background_changed = self.last_background_choice != self.get_output_background_signature()
        banner_changed = self.last_banner_text is not None

        if pose_changed or self.last_output_wx_image is None or background_changed:
            self.last_pose = current_pose
            self.render_pose_to_result_bitmap(current_pose)
            return "rendered"
        if display_transform_changed or banner_changed:
            self.draw_cached_result_image(None)
            return "cached"
        return "unchanged"

    def update_result_image_bitmap(self, event: Optional[wx.Event] = None):
        self.ensure_result_bitmap_size()
        if getattr(self.pose_converter, "refresh_audio_input_runtime", None) is not None:
            if self.is_model_loaded() and self.get_image_source_mode() == IMAGE_SOURCE_THA4 and (
                    self.poser is None or self.mediapipe_face_pose is None):
                self.pose_converter.refresh_audio_input_runtime(time.time())

        tick_result = self.active_image_source.tick(self)

        if tick_result == "rendered" and self.is_model_loaded():
            time_now = time.time_ns()
            if self.last_update_time is not None:
                elapsed_time = time_now - self.last_update_time
                fps = 1.0 / (elapsed_time / 10 ** 9)
                if self.get_image_source_mode() == IMAGE_SOURCE_THA4:
                    if self.torch_source_image is not None:
                        self.fps_statistics.add_fps(fps)
                elif self.active_image_source.is_ready(self):
                    self.fps_statistics.add_fps(fps)
                if hasattr(self, "fps_text"):
                    self.set_wrapped_static_text_if_changed(
                        self.fps_text, "FPS\n%0.2f" % self.fps_statistics.get_average_fps())
            self.last_update_time = time_now

    def load_model_from_path(self, character_model_json_file_name: str) -> bool:
        if self.get_image_source_mode() != IMAGE_SOURCE_THA4:
            switch_image_source(self, IMAGE_SOURCE_THA4)
        load_start = time.time()
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H15",
            location="load_model_from_path:entry",
            message="model load started",
            data={"path": character_model_json_file_name})
        # #endregion
        latest_face_screen_motion = None if self.latest_face_screen_motion is None else FaceScreenMotion(
            center_x=self.latest_face_screen_motion.center_x,
            center_y=self.latest_face_screen_motion.center_y,
            face_size=self.latest_face_screen_motion.face_size)
        latest_head_roll_deg = self.latest_head_roll_deg
        last_face_detected_time = self.last_face_detected_time
        try:
            self.character_model = CharacterModel.load(character_model_json_file_name)
            self.torch_source_image = self.character_model.get_character_image(self.device)
            pil_image = resize_PIL_image(
                PIL.Image.open(self.character_model.character_image_file_name),
                (MainFrame.IMAGE_SIZE, MainFrame.IMAGE_SIZE))
            w, h = pil_image.size
            self.wx_source_image = wx.Bitmap.FromBufferRGBA(w, h, pil_image.convert("RGBA").tobytes())
            self.update_source_image_bitmap()
            self.poser = self.character_model.get_poser(self.device)
            self.refresh_model_loaded_ui_state()
            self.last_loaded_model_path = character_model_json_file_name
            self.update_load_model_buttons()
            self.save_persistent_ui_state()
            self.mediapipe_face_pose = None
            self.last_pose = None
            self._load_preview_shown = False
            self.last_output_wx_image = None
            self.last_banner_text = None
            self.last_background_choice = self.get_output_background_signature()
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
            self.render_default_pose_load_preview()
            self.update_source_image_bitmap()
            if hasattr(self, "source_image_panel"):
                self.source_image_panel.Update()
            if getattr(self, "output_frame", None) is not None and self.output_frame:
                self.output_frame.result_image_panel.Update()
            # #region agent log
            self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H15",
                location="load_model_from_path:success",
                message="model load finished successfully",
                data={"elapsed_ms": int((time.time() - load_start) * 1000)})
            # #endregion
            return True
        except Exception:
            # #region agent log
            self.debug_mode_log(
                run_id="pre-fix",
                hypothesis_id="H15",
                location="load_model_from_path:exception",
                message="model load raised exception",
                data={"elapsed_ms": int((time.time() - load_start) * 1000)})
            # #endregion
            self.refresh_model_loaded_ui_state()
            message_dialog = wx.MessageDialog(
                self.get_dialog_parent(), "Could not load character model " + character_model_json_file_name, "Poser", wx.OK)
            message_dialog.ShowModal()
            message_dialog.Destroy()
            return False

    def load_model(self, event: wx.Event):
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H14",
            location="load_model:entry",
            message="load another model clicked",
            data={})
        # #endregion
        self.refresh_video_source_choice_async(connect_after=True, trigger_source="manual")
        dir_name = "data/character_models"
        file_dialog = wx.FileDialog(self.get_dialog_parent(), "Choose a model", dir_name, "", "*.yaml", wx.FD_OPEN)
        if file_dialog.ShowModal() == wx.ID_OK:
            character_model_json_file_name = os.path.join(file_dialog.GetDirectory(), file_dialog.GetFilename())
            self.load_model_from_path(character_model_json_file_name)
        file_dialog.Destroy()

    def load_last_model(self, event: wx.Event):
        # #region agent log
        self.debug_mode_log(
            run_id="pre-fix",
            hypothesis_id="H14",
            location="load_last_model:entry",
            message="load last model clicked",
            data={"has_last_model_path": bool(self.last_loaded_model_path)})
        # #endregion
        self.refresh_video_source_choice_async(connect_after=True, trigger_source="manual")
        if not self.last_loaded_model_path:
            return
        if not os.path.isfile(self.last_loaded_model_path):
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
        self.load_model_from_path(self.last_loaded_model_path)


if __name__ == "__main__":
    try:
        device = torch.device("cuda:0")

        pose_converter = MediaPoseFacePoseConverter00()

        face_landmarker_base_options = mediapipe.tasks.BaseOptions(
            model_asset_path='data/thirdparty/mediapipe/face_landmarker_v2_with_blendshapes.task')
        options = mediapipe.tasks.vision.FaceLandmarkerOptions(
            base_options=face_landmarker_base_options,
            running_mode=mediapipe.tasks.vision.RunningMode.VIDEO,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=1)
        face_landmarker = mediapipe.tasks.vision.FaceLandmarker.create_from_options(options)

        video_capture = None

        app = wx.App()
        main_frame = MainFrame(pose_converter, video_capture, face_landmarker, device)
        main_frame.capture_timer.Start(MainFrame.CAPTURE_IDLE_INTERVAL_MS)
        main_frame.animation_timer.Start(33)
        app.MainLoop()
    except Exception:
        raise
