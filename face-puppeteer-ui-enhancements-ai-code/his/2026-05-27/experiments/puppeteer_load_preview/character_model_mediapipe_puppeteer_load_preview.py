# Experimental copy: render one default-pose frame right after Load Model (no camera required).
# Original: talking-head-anime-4-demo/src/tha4/app/character_model_mediapipe_puppeteer.py
import math
import os
import sys
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


class FloatSliderControl:
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
        self.panel.SetMinSize(wx.Size(132, -1))

        self.label = wx.StaticText(self.panel, label=self._format_multiline_label(label_text), style=wx.ALIGN_CENTER_HORIZONTAL)
        panel_sizer.Add(self.label, 0, wx.EXPAND | wx.BOTTOM, 2)

        max_int = self._float_to_int(self.slider_max)
        self.slider = wx.Slider(
            self.panel,
            wx.ID_ANY,
            minValue=0,
            maxValue=max_int,
            value=self._float_to_int(initial_value),
            style=wx.HORIZONTAL)
        panel_sizer.Add(self.slider, 0, wx.EXPAND)

        self.value_text = wx.StaticText(self.panel, label="", style=wx.ALIGN_CENTER_HORIZONTAL)
        panel_sizer.Add(self.value_text, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 2)
        self._refresh_value_label()

        self.slider.Bind(wx.EVT_SLIDER, self._handle_change)
        self.change_handler = change_handler
        sizer.Add(self.panel, 0, wx.EXPAND | wx.ALL, 4)

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
        super().__init__(None, wx.ID_ANY, "THA4 Output / 输出窗口", style=wx.NO_BORDER)
        self.owner_main_frame = owner_main_frame
        self._dragging = False
        self._drag_start_screen = wx.Point(0, 0)
        self._drag_start_frame = wx.Point(0, 0)
        self.SetDoubleBuffered(True)
        self.output_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.output_sizer)
        self.SetAutoLayout(1)

        default_output_size = owner_main_frame.DEFAULT_OUTPUT_SIZE
        self.result_image_panel = wx.Panel(self, size=(default_output_size, default_output_size),
                                           style=0)
        self.result_image_panel.SetDoubleBuffered(True)
        self.result_image_panel.Bind(wx.EVT_PAINT, self.paint_result_image_panel)
        self.result_image_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.owner_main_frame.on_erase_background)
        self.result_image_panel.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.result_image_panel.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.result_image_panel.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.output_sizer.Add(self.result_image_panel, 1, wx.EXPAND)

        self.SetClientSize(wx.Size(default_output_size, default_output_size))
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_MOVE, self.on_move)

    def paint_result_image_panel(self, event: wx.Event):
        wx.BufferedPaintDC(self.result_image_panel, self.owner_main_frame.result_image_bitmap)

    def on_close(self, event: wx.Event):
        if getattr(self.owner_main_frame, "_is_closing", False):
            self.Destroy()
            event.Skip()
            return

        self.owner_main_frame.Close()
        event.Veto()

    def on_size(self, event: wx.Event):
        self.owner_main_frame.schedule_output_frame_geometry_sync(redraw=True)
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

    def on_close(self, event: wx.Event):
        if getattr(self.owner_main_frame, "_is_closing", False):
            self.Destroy()
            event.Skip()
            return
        self.owner_main_frame.Close()
        event.Veto()


class MainFrame(wx.Frame):
    IMAGE_SIZE = 512
    SOURCE_PREVIEW_SIZE = 192
    DEFAULT_OUTPUT_SIZE = int(IMAGE_SIZE * 1.5)
    LOAD_PREVIEW_BANNER = "DEFAULT POSE (model loaded)"
    AUTO_TRANSFORM_HOLD_SECONDS = 0.75
    SCALE_CURVE_DELTA_RANGE = 0.22
    UI_STATE_FILE_NAME = "load_preview_ui_state.json"

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
        self.result_image_bitmap = wx.Bitmap(MainFrame.IMAGE_SIZE, MainFrame.IMAGE_SIZE)
        self.webcam_capture_bitmap = wx.Bitmap(256, 192)
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
        self.last_background_choice = 0
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
        self.last_loaded_model_path: Optional[str] = None
        self.full_controls_expanded = False
        self.controls_frame: Optional[ControlsFrame] = None
        self.persistent_ui_state = self.load_persistent_ui_state()
        self.SetDoubleBuffered(True)
        self.initialize_headless_control_state()

        self.create_ui()
        self.output_frame = OutputFrame(self)
        self.apply_persistent_ui_state()
        self.apply_output_frame_state()
        self.refresh_model_loaded_ui_state()
        self.output_frame.Show(True)
        self.create_timers()
        self.Bind(wx.EVT_CLOSE, self.on_close)

        self.update_source_image_bitmap()
        self.update_result_image_bitmap()

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
        self.output_background_choice = SelectionState(0, 5)
        self.mirror_output_checkbox = ValueState(False)
        self.antialias_strength_spin = ValueState(1.00)

    def on_close(self, event: wx.Event):
        self._is_closing = True
        if getattr(self, "output_frame", None) is not None and self.output_frame:
            self.handle_output_frame_geometry_changed(redraw=False)
        self.save_persistent_ui_state()
        if hasattr(self.pose_converter, "shutdown"):
            self.pose_converter.shutdown()
        self.animation_timer.Stop()
        self.capture_timer.Stop()
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
        if hasattr(self, "main_splitter") and self.main_splitter.IsSplit():
            saved_main_sash = self.persistent_ui_state.get("main_splitter_sash")
            default_main_sash = max(720, controls_window.GetClientSize().x - max(320, self.right_sidebar.GetBestSize().x))
            self.apply_splitter_sash(
                self.main_splitter,
                saved_main_sash if isinstance(saved_main_sash, (int, float)) else default_main_sash)
        self.refresh_dynamic_output_status_layout()
        if hasattr(self, "animation_panel"):
            self.animation_panel.FitInside()
        controls_window.Layout()
        wx.CallAfter(self.adapt_main_window_to_controls)

    def adapt_main_window_to_controls(self):
        controls_window = self.get_controls_window()
        if getattr(self, "_is_closing", False) or not hasattr(self, "main_sizer") or controls_window is None:
            return
        self.refresh_dynamic_output_status_layout()
        if hasattr(self, "right_sidebar"):
            self.right_sidebar.Layout()
        if hasattr(self, "animation_panel"):
            self.animation_panel.FitInside()
        controls_window.Layout()

        target_client_size = self.main_sizer.GetMinSize()
        target_width = max(320, int(target_client_size.x))
        target_height = max(240, int(target_client_size.y))

        target_size = wx.Size(target_width, target_height)
        controls_window.SetClientSize(target_size)
        controls_window.SetMinClientSize(target_size)
        if hasattr(self, "animation_panel"):
            self.animation_panel.FitInside()
        controls_window.Layout()
        if not self._startup_autofit_pending:
            self._startup_autofit_pending = True
            wx.CallAfter(self.finalize_startup_autofit)

    def finalize_startup_autofit(self):
        self._startup_autofit_pending = False
        controls_window = self.get_controls_window()
        if getattr(self, "_is_closing", False) or not hasattr(self, "main_sizer") or controls_window is None:
            return
        self.refresh_dynamic_output_status_layout()
        if hasattr(self, "right_sidebar"):
            self.right_sidebar.Layout()
        if hasattr(self, "animation_panel"):
            self.animation_panel.FitInside()
        controls_window.Layout()

        needed_size = self.main_sizer.GetMinSize()
        current_size = controls_window.GetClientSize()
        target_width = max(current_size.x, int(needed_size.x))
        target_height = max(current_size.y, int(needed_size.y))

        if target_width != current_size.x or target_height != current_size.y:
            target_size = wx.Size(target_width, target_height)
            controls_window.SetClientSize(target_size)
            controls_window.SetMinClientSize(target_size)
            if hasattr(self, "animation_panel"):
                self.animation_panel.FitInside()
            controls_window.Layout()

    def on_column_splitter_changed(self, event: wx.Event):
        self.refresh_dynamic_output_status_layout()
        if hasattr(self, "animation_panel"):
            self.animation_panel.FitInside()
        if hasattr(self, "output_background_choice"):
            self.save_persistent_ui_state()
        event.Skip()

    @classmethod
    def get_ui_state_file_path(cls) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), cls.UI_STATE_FILE_NAME)

    def load_persistent_ui_state(self) -> dict:
        file_path = self.get_ui_state_file_path()
        if not os.path.isfile(file_path):
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def collect_persistent_ui_state(self) -> dict:
        output_canvas_width = None
        output_canvas_height = None
        if getattr(self, "output_frame", None) is not None and self.output_frame:
            output_canvas_size = self.output_frame.result_image_panel.GetClientSize()
            output_canvas_width = output_canvas_size.x
            output_canvas_height = output_canvas_size.y
        animation_splitter_sash = self.persistent_ui_state.get("animation_splitter_sash")
        if hasattr(self, "animation_splitter") and self.animation_splitter.IsSplit():
            animation_splitter_sash = self.animation_splitter.GetSashPosition()
        main_splitter_sash = self.persistent_ui_state.get("main_splitter_sash")
        if hasattr(self, "main_splitter") and self.main_splitter.IsSplit():
            main_splitter_sash = self.main_splitter.GetSashPosition()
        return {
            "output_background_selection": self.output_background_choice.GetSelection(),
            "enable_auto_transform": self.enable_auto_transform_checkbox.GetValue(),
            "enable_direction_calibration": self.enable_direction_calibration_checkbox.GetValue(),
            "direction_calibration_interval_seconds": self.auto_direction_calibration_interval_seconds_ctrl.GetValue(),
            "enable_scale_calibration": self.enable_scale_calibration_checkbox.GetValue(),
            "scale_calibration_interval_seconds": self.auto_scale_calibration_interval_seconds_ctrl.GetValue(),
            "invert_tilt_mapping": self.invert_tilt_mapping_checkbox.GetValue(),
            "mirror_output": self.mirror_output_checkbox.GetValue(),
            "last_loaded_model_path": self.last_loaded_model_path,
            "animation_splitter_sash": animation_splitter_sash,
            "main_splitter_sash": main_splitter_sash,
            "output_frame_x": self.output_frame.GetPosition().x if getattr(self, "output_frame", None) else None,
            "output_frame_y": self.output_frame.GetPosition().y if getattr(self, "output_frame", None) else None,
            "output_frame_w": output_canvas_width,
            "output_frame_h": output_canvas_height,
        }

    def save_persistent_ui_state(self):
        data = self.collect_persistent_ui_state()
        if not data:
            return
        try:
            with open(self.get_ui_state_file_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=True, indent=2)
        except Exception:
            pass

    def apply_persistent_ui_state(self):
        data = self.persistent_ui_state
        if not data:
            self.on_display_transform_control_changed()
            return

        if "enable_auto_transform" in data:
            self.enable_auto_transform_checkbox.SetValue(bool(data["enable_auto_transform"]))
        if "output_background_selection" in data:
            selection = int(data["output_background_selection"])
            selection = max(0, min(self.output_background_choice.GetCount() - 1, selection))
            self.output_background_choice.SetSelection(selection)
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
        if "last_loaded_model_path" in data:
            last_loaded_model_path = data["last_loaded_model_path"]
            self.last_loaded_model_path = last_loaded_model_path if isinstance(last_loaded_model_path, str) else None
        self.update_load_model_buttons()
        self.on_display_transform_control_changed()
        if self.get_controls_window() is not None:
            wx.CallAfter(self.initialize_adjustable_columns)

    def apply_output_frame_state(self):
        if getattr(self, "output_frame", None) is None:
            return
        data = self.persistent_ui_state
        width = self.DEFAULT_OUTPUT_SIZE
        height = self.DEFAULT_OUTPUT_SIZE
        if "output_frame_w" in data and "output_frame_h" in data:
            width = max(128, int(data["output_frame_w"]))
            height = max(128, int(data["output_frame_h"]))
        self.output_frame.SetClientSize(wx.Size(width, height))
        self.output_frame.Layout()
        if "output_frame_x" in data and "output_frame_y" in data:
            self.output_frame.SetPosition(wx.Point(int(data["output_frame_x"]), int(data["output_frame_y"])))

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

    def get_output_canvas_size(self) -> tuple[int, int]:
        if getattr(self, "output_frame", None) is not None and self.output_frame:
            size = self.output_frame.result_image_panel.GetClientSize()
            if size.x > 0 and size.y > 0:
                return size.x, size.y
        return self.DEFAULT_OUTPUT_SIZE, self.DEFAULT_OUTPUT_SIZE

    def ensure_result_bitmap_size(self):
        width, height = self.get_output_canvas_size()
        if self.result_image_bitmap.GetWidth() != width or self.result_image_bitmap.GetHeight() != height:
            self.result_image_bitmap = wx.Bitmap(width, height)

    def handle_output_frame_geometry_changed(self, redraw: bool = True):
        if getattr(self, "output_frame", None) is not None and self.output_frame:
            self.output_frame.Layout()
        self.ensure_result_bitmap_size()
        self.save_persistent_ui_state()
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

            self.input_panel = wx.Panel(self.model_input_column, style=wx.SIMPLE_BORDER)
            self.input_panel_sizer = wx.BoxSizer(wx.VERTICAL)
            self.input_panel.SetSizer(self.input_panel_sizer)
            self.input_panel.SetAutoLayout(1)
            self.input_panel.SetDoubleBuffered(True)
            self.model_input_column_sizer.Add(self.input_panel, 0, wx.EXPAND)

            load_button_panel = wx.Panel(self.input_panel)
            load_button_sizer = wx.BoxSizer(wx.HORIZONTAL)
            load_button_panel.SetSizer(load_button_sizer)
            load_button_panel.SetAutoLayout(1)
            self.input_panel_sizer.Add(load_button_panel, 0, wx.EXPAND | wx.ALL, 4)

            self.load_last_model_button = wx.Button(load_button_panel, wx.ID_ANY, "加载上次模型 / Load Last")
            load_button_sizer.Add(self.load_last_model_button, 1, wx.EXPAND | wx.RIGHT, 3)
            self.load_last_model_button.Bind(wx.EVT_BUTTON, self.load_last_model)

            self.load_model_button = wx.Button(load_button_panel, wx.ID_ANY, "加载其他模型 / Load Other")
            load_button_sizer.Add(self.load_model_button, 1, wx.EXPAND | wx.LEFT, 3)
            self.load_model_button.Bind(wx.EVT_BUTTON, self.load_model)
            self.update_load_model_buttons()

            self.input_panel_sizer.Fit(self.input_panel)

        if True:
            def current_pose_supplier() -> Optional[MediaPipeFacePose]:
                return self.mediapipe_face_pose

            self.pose_converter.init_pose_converter_panel(self.model_input_column, current_pose_supplier)
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
                self.animation_left_panel, label="启用自动移动缩放 / Enable Auto Move / Scale")
            self.enable_auto_transform_checkbox.SetValue(auto_transform_enabled)
            self.enable_auto_transform_checkbox.Bind(wx.EVT_CHECKBOX, self.on_display_transform_control_changed)
            self.animation_left_panel_sizer.Add(self.enable_auto_transform_checkbox,
                                                wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

            self.calibrate_neutral_button = wx.Button(self.animation_left_panel, label="标定中性位 / Calibrate Neutral")
            self.calibrate_neutral_button.Bind(wx.EVT_BUTTON, self.calibrate_neutral_clicked)
            self.animation_left_panel_sizer.Add(self.calibrate_neutral_button, 0, wx.EXPAND)

            display_transform_panel = wx.Panel(self.animation_left_panel)
            display_transform_panel_sizer = wx.BoxSizer(wx.VERTICAL)
            display_transform_panel.SetSizer(display_transform_panel_sizer)
            display_transform_panel.SetAutoLayout(1)
            self.animation_left_panel_sizer.Add(display_transform_panel, 0, wx.EXPAND)

            self.move_x_gain_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer, "X 位移增益 / Move X Gain:", move_x_gain, 0.0, 400.0, 1.0)
            self.move_y_gain_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer, "Y 位移增益 / Move Y Gain:", move_y_gain, 0.0, 400.0, 1.0)
            self.scale_gain_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer, "缩放增益 / Scale Gain:", scale_gain, 0.0, 8.0, 0.05)
            self.min_scale_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer, "最小缩放 / Min Scale:", min_scale, 0.25, 2.0, 0.01)
            self.max_scale_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer, "最大缩放 / Max Scale:", max_scale, 0.25, 2.0, 0.01)
            self.tilt_limit_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer, "倾斜上限 / Tilt Limit:", tilt_limit, -30.0, 30.0, 0.5)
            self.smoothing_spin = self.create_display_transform_slider_control(
                display_transform_panel, display_transform_panel_sizer, "平滑系数 / Smoothing:", smoothing, 0.0, 0.98, 0.01)

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
                scale_curve_control_panel, scale_curve_control_panel_sizer, "近距曲率 / Near Curve:", near_curve, 0.25, 2.00, 0.05)
            self.scale_curve_far_spin = self.create_display_transform_slider_control(
                scale_curve_control_panel, scale_curve_control_panel_sizer, "远距曲率 / Far Curve:", far_curve, 0.10, 1.20, 0.05)
            self.scale_curve_arc_spin = self.create_display_transform_slider_control(
                scale_curve_control_panel, scale_curve_control_panel_sizer, "曲线弧度 / Curve Arc:", curve_arc, 0.40, 2.20, 0.05)
            self.scale_curve_peak_shift_spin = self.create_display_transform_slider_control(
                scale_curve_control_panel, scale_curve_control_panel_sizer, "峰位横移 / Peak Shift:", peak_shift, -0.12, 0.12, 0.005)

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

        self.animation_panel.SetMinSize(self.animation_panel_sizer.GetMinSize())
        self.animation_panel_sizer.Fit(self.animation_panel)
        self.animation_panel.FitInside()

    def create_compact_launcher_panel(self, parent):
        self.compact_launcher_panel = wx.Panel(parent, style=wx.SIMPLE_BORDER)
        compact_launcher_sizer = wx.BoxSizer(wx.VERTICAL)
        self.compact_launcher_panel.SetSizer(compact_launcher_sizer)
        self.compact_launcher_panel.SetAutoLayout(1)
        self.compact_launcher_panel.SetDoubleBuffered(True)

        self.quick_load_last_model_button = wx.Button(
            self.compact_launcher_panel, wx.ID_ANY, "加载上次模型 / Load Last Model")
        self.quick_load_last_model_button.Bind(wx.EVT_BUTTON, self.load_last_model)
        compact_launcher_sizer.Add(self.quick_load_last_model_button, 0, wx.EXPAND | wx.ALL, 6)

        self.quick_calibrate_head_orientation_button = wx.Button(
            self.compact_launcher_panel, wx.ID_ANY, "校正头部朝向 / Calibrate Head Orientation")
        self.quick_calibrate_head_orientation_button.Bind(wx.EVT_BUTTON, self.calibrate_head_orientation_quick)
        compact_launcher_sizer.Add(self.quick_calibrate_head_orientation_button, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

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
        self.SetClientSize(fitted_size)
        self.SetMinClientSize(fitted_size)

    def create_controls_frame(self):
        if self.controls_frame is not None:
            return

        self.controls_frame = ControlsFrame(self)
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

        self.main_splitter = wx.SplitterWindow(
            self.controls_frame,
            style=wx.SP_LIVE_UPDATE | wx.SP_3D | wx.SP_BORDER)
        self.main_splitter.SetMinimumPaneSize(280)
        self.main_splitter.SetSashGravity(1.0)
        self.main_splitter.Bind(wx.EVT_SPLITTER_SASH_POS_CHANGED, self.on_column_splitter_changed)
        self.main_sizer.Add(self.main_splitter, wx.SizerFlags(1).Expand().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 5))

        self.create_animation_panel(self.main_splitter)

        self.right_sidebar = wx.Panel(self.main_splitter)
        self.right_sidebar_sizer = wx.BoxSizer(wx.VERTICAL)
        self.right_sidebar.SetSizer(self.right_sidebar_sizer)
        self.right_sidebar.SetAutoLayout(1)
        self.right_sidebar.SetDoubleBuffered(True)

        self.create_capture_panel(self.right_sidebar)
        self.right_sidebar_sizer.Add(self.capture_panel, wx.SizerFlags(0).Expand())

        self.create_postprocess_panel(self.right_sidebar)
        self.right_sidebar_sizer.Add(self.postprocess_panel, wx.SizerFlags(0).Expand().Border(wx.TOP, 6))
        self.right_sidebar_sizer.Fit(self.right_sidebar)

        if not self.main_splitter.IsSplit():
            self.main_splitter.SplitVertically(
                self.animation_panel,
                self.right_sidebar,
                sashPosition=max(720, self.animation_panel.GetBestSize().x))

        self.main_sizer.Fit(self.controls_frame)
        self.refresh_model_loaded_ui_state()
        self.on_display_transform_control_changed()
        self.update_source_image_bitmap()
        if hasattr(self, "webcam_capture_panel"):
            self.webcam_capture_panel.Refresh(False)
        wx.CallAfter(self.initialize_adjustable_columns)

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

        self.webcam_capture_panel = wx.Panel(self.capture_panel, size=(256, 192), style=wx.SIMPLE_BORDER)
        self.webcam_capture_panel.SetDoubleBuffered(True)
        self.webcam_capture_panel.Bind(wx.EVT_PAINT, self.paint_webcam_capture_panel)
        self.webcam_capture_panel.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)
        self.capture_panel_sizer.Add(self.webcam_capture_panel, wx.SizerFlags(0).FixedMinSize().Border(wx.ALL, 5))

        self.rotation_labels = {}
        self.rotation_value_labels = {}
        rotation_column = self.create_rotation_column(self.capture_panel, HEAD_ROTATIONS)
        self.capture_panel_sizer.Add(rotation_column, wx.SizerFlags(0).Expand().Border(wx.ALL, 3))

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
        output_background_selection = self.output_background_choice.GetSelection()
        mirror_output = self.mirror_output_checkbox.GetValue()
        antialias_strength = self.antialias_strength_spin.GetValue()

        postprocess_text = wx.StaticText(
            self.postprocess_panel, label="--- 后处理和其他 / Postprocess & Other ---", style=wx.ALIGN_CENTER)
        self.postprocess_panel_sizer.Add(postprocess_text, 0, wx.EXPAND)

        self.enable_direction_calibration_checkbox = wx.CheckBox(
            self.postprocess_panel, label="启用方向自动校准 / Enable Direction Auto Calibrate")
        self.enable_direction_calibration_checkbox.SetValue(enable_direction_calibration)
        self.enable_direction_calibration_checkbox.Bind(wx.EVT_CHECKBOX, self.on_display_transform_control_changed)
        self.postprocess_panel_sizer.Add(
            self.enable_direction_calibration_checkbox,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.direction_calibration_interval_panel = wx.Panel(self.postprocess_panel)
        direction_calibration_interval_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.direction_calibration_interval_panel.SetSizer(direction_calibration_interval_sizer)
        self.direction_calibration_interval_panel.SetAutoLayout(1)
        self.postprocess_panel_sizer.Add(self.direction_calibration_interval_panel, 0, wx.EXPAND)

        direction_interval_label = wx.StaticText(
            self.direction_calibration_interval_panel, label="方向周期 / Direction Interval:")
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

        direction_interval_unit = wx.StaticText(
            self.direction_calibration_interval_panel, label="秒 / s")
        direction_calibration_interval_sizer.Add(direction_interval_unit, 0, wx.ALIGN_CENTER_VERTICAL)

        self.enable_scale_calibration_checkbox = wx.CheckBox(
            self.postprocess_panel, label="启用缩放自动校准 / Enable Scale Auto Calibrate")
        self.enable_scale_calibration_checkbox.SetValue(enable_scale_calibration)
        self.enable_scale_calibration_checkbox.Bind(wx.EVT_CHECKBOX, self.on_display_transform_control_changed)
        self.postprocess_panel_sizer.Add(
            self.enable_scale_calibration_checkbox,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.scale_calibration_interval_panel = wx.Panel(self.postprocess_panel)
        scale_calibration_interval_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.scale_calibration_interval_panel.SetSizer(scale_calibration_interval_sizer)
        self.scale_calibration_interval_panel.SetAutoLayout(1)
        self.postprocess_panel_sizer.Add(self.scale_calibration_interval_panel, 0, wx.EXPAND)

        scale_interval_label = wx.StaticText(
            self.scale_calibration_interval_panel, label="缩放周期 / Scale Interval:")
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

        scale_interval_unit = wx.StaticText(
            self.scale_calibration_interval_panel, label="秒 / s")
        scale_calibration_interval_sizer.Add(scale_interval_unit, 0, wx.ALIGN_CENTER_VERTICAL)

        background_label = wx.StaticText(self.postprocess_panel, label="背景 / Background")
        self.postprocess_panel_sizer.Add(background_label, wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.TOP, 4))

        self.output_background_choice = wx.Choice(
            self.postprocess_panel,
            choices=[
                "透明 / TRANSPARENT",
                "绿色 / GREEN",
                "蓝色 / BLUE",
                "黑色 / BLACK",
                "白色 / WHITE"
            ])
        self.output_background_choice.SetSelection(output_background_selection)
        self.output_background_choice.Bind(wx.EVT_CHOICE, self.on_output_background_changed)
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

        postprocess_control_panel = wx.Panel(self.postprocess_panel)
        postprocess_control_panel_sizer = wx.BoxSizer(wx.VERTICAL)
        postprocess_control_panel.SetSizer(postprocess_control_panel_sizer)
        postprocess_control_panel.SetAutoLayout(1)
        self.postprocess_panel_sizer.Add(postprocess_control_panel, 0, wx.EXPAND)

        self.antialias_strength_spin = self.create_display_transform_slider_control(
            postprocess_control_panel,
            postprocess_control_panel_sizer,
            "抗锯齿强度 / Anti-Aliasing:",
            antialias_strength,
            1.0,
            4.0,
            0.25,
            slider_min=1.0,
            slider_max=4.0)

        antialias_hint = wx.StaticText(
            self.postprocess_panel,
            label="1.00 = 关闭 / off；更高会更平滑，但更吃性能")
        self.postprocess_panel_sizer.Add(
            antialias_hint,
            wx.SizerFlags().Border(wx.LEFT | wx.RIGHT | wx.BOTTOM, 4))

        self.postprocess_panel_sizer.Fit(self.postprocess_panel)

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

    def show_full_controls_window(self):
        self.create_controls_frame()
        self.full_controls_expanded = True
        self.refresh_model_loaded_ui_state()
        if self.controls_frame is not None:
            self.controls_frame.Show(True)
            self.controls_frame.Raise()
        self.Show(False)
        wx.CallAfter(self.initialize_adjustable_columns)

    def show_compact_launcher(self):
        self.full_controls_expanded = False
        if self.controls_frame is not None:
            self.controls_frame.Show(False)
        self.Show(True)
        self.Raise()

    def toggle_full_controls_clicked(self, event: wx.Event):
        self.show_full_controls_window()

    def switch_to_compact_clicked(self, event: wx.Event):
        self.show_compact_launcher()

    def calibrate_head_orientation_quick(self, event: wx.Event):
        if self.mediapipe_face_pose is None:
            return
        euler_angles = self.pose_converter.extract_euler_angles(self.mediapipe_face_pose)
        self.pose_converter.args.head_x_offset = euler_angles[0]
        self.pose_converter.args.head_y_offset = euler_angles[1]
        self.pose_converter.args.head_z_offset = euler_angles[2]

    def is_model_loaded(self) -> bool:
        return self.poser is not None and self.torch_source_image is not None and self.wx_source_image is not None

    def get_dialog_parent(self) -> wx.Window:
        if self.controls_frame is not None and self.controls_frame.IsShown():
            return self.controls_frame
        return self

    def refresh_model_loaded_ui_state(self):
        model_loaded = self.is_model_loaded()
        if getattr(self.pose_converter, "panel", None) is not None:
            if hasattr(self.pose_converter, "set_panel_enabled"):
                self.pose_converter.set_panel_enabled(model_loaded)
            else:
                self.pose_converter.panel.Enable(model_loaded)
        if hasattr(self, "animation_left_panel"):
            self.animation_left_panel.Enable(model_loaded)
        if hasattr(self, "postprocess_panel"):
            self.postprocess_panel.Enable(model_loaded)
        self.update_load_model_buttons()

    def on_output_background_changed(self, event: wx.Event):
        self.last_background_choice = -1
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
        if hasattr(self, "direction_calibration_interval_panel"):
            self.direction_calibration_interval_panel.Enable(self.enable_direction_calibration_checkbox.GetValue())
        if hasattr(self, "scale_calibration_interval_panel"):
            self.scale_calibration_interval_panel.Enable(self.enable_scale_calibration_checkbox.GetValue())
        self.save_persistent_ui_state()
        self.update_display_transform_state(snap_to_target=not self.enable_auto_transform_checkbox.GetValue())
        self.refresh_scale_curve_status()
        self.request_scale_curve_repaint(force=True)
        if self.last_output_wx_image is not None:
            self.draw_cached_result_image(self.last_banner_text)

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
        if face_screen_motion is None:
            return
        time_value = time.time() if calibration_time is None else calibration_time
        if self.enable_direction_calibration_checkbox.GetValue():
            self.update_neutral_face_direction(face_screen_motion)
            self.last_direction_calibration_time = time_value
        else:
            self.last_direction_calibration_time = None
        if self.enable_scale_calibration_checkbox.GetValue():
            self.update_neutral_face_size(face_screen_motion)
            self.last_scale_calibration_time = time_value
        else:
            self.last_scale_calibration_time = None

    def maybe_apply_periodic_direction_calibration(self, latest_motion: FaceScreenMotion):
        if not self.enable_direction_calibration_checkbox.GetValue():
            return

        interval_seconds = max(1.0, self.auto_direction_calibration_interval_seconds_ctrl.GetValue())
        time_now = time.time()
        if self.last_direction_calibration_time is None:
            self.last_direction_calibration_time = time_now
            return

        if time_now - self.last_direction_calibration_time < interval_seconds:
            return

        self.update_neutral_face_direction(latest_motion)
        self.last_direction_calibration_time = time_now

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
                "当前点 / Point\n等待人脸输入 / waiting for face")
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
                    self.maybe_apply_periodic_direction_calibration(latest_motion)
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

        return abs(self.display_offset_x - old_offset_x) > 0.25 \
            or abs(self.display_offset_y - old_offset_y) > 0.25 \
            or abs(self.display_scale - old_scale) > 0.002 \
            or abs(self.display_rotation_deg - old_rotation_deg) > 0.05

    def update_capture_panel(self, event: wx.Event):
        there_is_frame, frame = self.video_capture.read()
        if not there_is_frame:
            dc = wx.MemoryDC()
            dc.SelectObject(self.webcam_capture_bitmap)
            self.draw_nothing_yet_string(dc)
            del dc
            return

        rgb_frame = cv2.flip(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), 1)
        resized_frame = cv2.resize(rgb_frame, (256, 192))
        wx_image = wx.ImageFromBuffer(256, 192, resized_frame.tobytes())
        wx_bitmap = wx_image.ConvertToBitmap()

        dc = wx.MemoryDC()
        dc.SelectObject(self.webcam_capture_bitmap)
        dc.Clear()
        dc.DrawBitmap(wx_bitmap, 0, 0, True)
        del dc

        if hasattr(self, "webcam_capture_panel"):
            self.webcam_capture_panel.Refresh(False)

        time_ms = int(time.time() * 1000)
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
        self.refresh_scale_curve_status()
        self.request_scale_curve_repaint(force=False)

    @staticmethod
    def convert_to_100(x):
        return int(max(0.0, min(1.0, x)) * 100)

    def paint_source_image_panel(self, event: wx.Event):
        wx.BufferedPaintDC(self.source_image_panel, self.source_image_bitmap)

    def update_source_image_bitmap(self):
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

    def draw_nothing_yet_string(self, dc, message: str = "Nothing yet!"):
        dc.Clear()
        font = wx.Font(wx.FontInfo(14).Family(wx.FONTFAMILY_SWISS))
        dc.SetFont(font)
        w, h = dc.GetTextExtent(message)
        canvas_width, canvas_height = dc.GetSize()
        dc.DrawText(message, (canvas_width - w) // 2, (canvas_height - h) // 2)

    def paint_result_image_panel(self, event: wx.Event):
        if getattr(self, "output_frame", None) is not None and self.output_frame:
            wx.BufferedPaintDC(self.output_frame.result_image_panel, self.result_image_bitmap)

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

        margin_left = 32
        margin_right = 10
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
        dc.DrawLine(margin_left, margin_top, margin_left, height - margin_bottom)

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
        dc.DrawText("小 / Small", 2, height - margin_bottom - 10)
        dc.DrawText("大 / Large", 2, margin_top)

    def get_output_background_color(self) -> Optional[wx.Colour]:
        background_choice = self.output_background_choice.GetSelection()
        if background_choice == 1:
            return wx.Colour(0, 255, 0)
        if background_choice == 2:
            return wx.Colour(0, 0, 255)
        if background_choice == 3:
            return wx.Colour(0, 0, 0)
        if background_choice == 4:
            return wx.Colour(255, 255, 255)
        return None

    def clear_result_bitmap_with_background(self, dc: wx.MemoryDC):
        background_color = self.get_output_background_color()
        if background_color is None:
            dc.SetBackground(wx.Brush(wx.Colour(0, 0, 0)))
        else:
            dc.SetBackground(wx.Brush(background_color))
        dc.Clear()

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

        composition_bitmap = wx.Bitmap(render_canvas_width, render_canvas_height)
        composition_dc = wx.MemoryDC()
        composition_dc.SelectObject(composition_bitmap)
        self.clear_result_bitmap_with_background(composition_dc)
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
        dc.DrawBitmap(final_bitmap, 0, 0, True)
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
        self.last_background_choice = self.output_background_choice.GetSelection()
        if getattr(self, "output_frame", None) is not None and self.output_frame:
            self.output_frame.result_image_panel.Refresh(False)

    def render_pose_to_result_bitmap(self, pose_list: List[float], banner_text: Optional[str] = None):
        wx_image = self.render_pose_to_wx_image(pose_list)
        if wx_image is None:
            return

        self.last_output_wx_image = wx_image
        self.last_background_choice = self.output_background_choice.GetSelection()
        self.draw_result_wx_image(wx_image, banner_text)

    def render_default_pose_load_preview(self):
        default_pose = self.get_default_pose_list()
        self.last_pose = default_pose
        self.render_pose_to_result_bitmap(default_pose, MainFrame.LOAD_PREVIEW_BANNER)
        self._load_preview_shown = True
        if hasattr(self, "fps_text"):
            self.set_wrapped_static_text_if_changed(self.fps_text, "预览 / Preview\nno face input")

    def update_result_image_bitmap(self, event: Optional[wx.Event] = None):
        self.ensure_result_bitmap_size()
        if self.poser is None:
            dc = wx.MemoryDC()
            dc.SelectObject(self.result_image_bitmap)
            self.draw_nothing_yet_string(dc)
            del dc
            return

        display_transform_changed = self.update_display_transform_state()
        if self.mediapipe_face_pose is None:
            if display_transform_changed and self.last_output_wx_image is not None:
                self.draw_cached_result_image(self.last_banner_text)
            return

        current_pose = self.pose_converter.convert(self.mediapipe_face_pose)
        current_pose = self.apply_negative_tilt_limit_to_pose(current_pose)
        if self.torch_source_image is None:
            dc = wx.MemoryDC()
            dc.SelectObject(self.result_image_bitmap)
            self.draw_nothing_yet_string(dc)
            del dc
            return

        pose_changed = self.last_pose is None or self.last_pose != current_pose
        background_changed = self.last_background_choice != self.output_background_choice.GetSelection()
        banner_changed = self.last_banner_text is not None
        rendered_pose = False

        if pose_changed or self.last_output_wx_image is None or background_changed:
            self.last_pose = current_pose
            self.render_pose_to_result_bitmap(current_pose)
            rendered_pose = True
        elif display_transform_changed or banner_changed:
            self.draw_cached_result_image(None)
        else:
            return

        if rendered_pose:
            time_now = time.time_ns()
            if self.last_update_time is not None:
                elapsed_time = time_now - self.last_update_time
                fps = 1.0 / (elapsed_time / 10 ** 9)
                if self.torch_source_image is not None:
                    self.fps_statistics.add_fps(fps)
                if hasattr(self, "fps_text"):
                    self.set_wrapped_static_text_if_changed(
                        self.fps_text, "FPS\n%0.2f" % self.fps_statistics.get_average_fps())
            self.last_update_time = time_now

    def load_model_from_path(self, character_model_json_file_name: str) -> bool:
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
            self.last_background_choice = self.output_background_choice.GetSelection()
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
            self.apply_enabled_auto_calibration_on_load(latest_face_screen_motion, last_face_detected_time)
            self.refresh_auto_transform_status("READY" if self.enable_auto_transform_checkbox.GetValue() else "OFF")
            self.render_default_pose_load_preview()
            self.update_source_image_bitmap()
            if hasattr(self, "source_image_panel"):
                self.source_image_panel.Update()
            if getattr(self, "output_frame", None) is not None and self.output_frame:
                self.output_frame.result_image_panel.Update()
            return True
        except Exception:
            self.refresh_model_loaded_ui_state()
            message_dialog = wx.MessageDialog(
                self.get_dialog_parent(), "Could not load character model " + character_model_json_file_name, "Poser", wx.OK)
            message_dialog.ShowModal()
            message_dialog.Destroy()
            return False

    def load_model(self, event: wx.Event):
        dir_name = "data/character_models"
        file_dialog = wx.FileDialog(self.get_dialog_parent(), "Choose a model", dir_name, "", "*.yaml", wx.FD_OPEN)
        if file_dialog.ShowModal() == wx.ID_OK:
            character_model_json_file_name = os.path.join(file_dialog.GetDirectory(), file_dialog.GetFilename())
            self.load_model_from_path(character_model_json_file_name)
        file_dialog.Destroy()

    def load_last_model(self, event: wx.Event):
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

    video_capture = cv2.VideoCapture(0)

    app = wx.App()
    main_frame = MainFrame(pose_converter, video_capture, face_landmarker, device)
    main_frame.Show(True)
    main_frame.capture_timer.Start(30)
    main_frame.animation_timer.Start(30)
    app.MainLoop()
