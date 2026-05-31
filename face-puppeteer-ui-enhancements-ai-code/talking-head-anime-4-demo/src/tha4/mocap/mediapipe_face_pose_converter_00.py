import math
import threading
import time
import json
import os
import uuid
from enum import Enum
from typing import Optional, List, Callable

import numpy
import scipy.optimize
import wx
from scipy.spatial.transform import Rotation

try:
    import sounddevice
    import logging
    logging.getLogger("sounddevice").setLevel(logging.ERROR)
except Exception:
    sounddevice = None

from tha4.poser.modes.pose_parameters import get_pose_parameters
from tha4.mocap.mediapipe_constants import MOUTH_SMILE_LEFT, MOUTH_SHRUG_UPPER, MOUTH_SMILE_RIGHT, \
    BROW_INNER_UP, BROW_OUTER_UP_RIGHT, BROW_OUTER_UP_LEFT, BROW_DOWN_LEFT, BROW_DOWN_RIGHT, EYE_WIDE_LEFT, \
    EYE_WIDE_RIGHT, EYE_BLINK_LEFT, EYE_BLINK_RIGHT, CHEEK_SQUINT_LEFT, CHEEK_SQUINT_RIGHT, EYE_LOOK_IN_LEFT, \
    EYE_LOOK_OUT_LEFT, EYE_LOOK_IN_RIGHT, EYE_LOOK_OUT_RIGHT, EYE_LOOK_UP_LEFT, EYE_LOOK_UP_RIGHT, EYE_LOOK_DOWN_RIGHT, \
    EYE_LOOK_DOWN_LEFT, JAW_OPEN, MOUTH_FROWN_LEFT, MOUTH_FROWN_RIGHT, \
    MOUTH_LOWER_DOWN_LEFT, MOUTH_LOWER_DOWN_RIGHT, MOUTH_FUNNEL, MOUTH_PUCKER
from tha4.mocap.mediapipe_face_pose import MediaPipeFacePose
from tha4.mocap.mediapipe_face_pose_converter import MediaPipeFacePoseConverter

class EyebrowDownMode(Enum):
    TROUBLED = 1
    ANGRY = 2
    LOWERED = 3
    SERIOUS = 4

class WinkMode(Enum):
    NORMAL = 1
    RELAXED = 2

def rad_to_deg(rad):
    return rad * 180.0 / math.pi

def deg_to_rad(deg):
    return deg * math.pi / 180.0

def clamp(x, min_value, max_value):
    return max(min_value, min(max_value, x))


def _wx_widget_alive(widget) -> bool:
    if widget is None:
        return False
    try:
        if not isinstance(widget, wx.Window):
            return True
        if hasattr(widget, "IsDestroyed") and widget.IsDestroyed():
            return False
        widget.GetHandle()
        return True
    except (RuntimeError, AttributeError):
        return False


def _safe_set_gauge_value(gauge, value: int) -> None:
    if not _wx_widget_alive(gauge):
        return
    try:
        gauge.SetValue(int(value))
    except RuntimeError:
        pass


def slider_label(name_cn: str, name_en: str, unit_cn: str, unit_en: str) -> str:
    return f"{name_cn} / {name_en} ({unit_cn} / {unit_en})"

class FloatSliderControl:
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
                 set_func: Callable[[float], None],
                 slider_min: Optional[float] = None,
                 slider_max: Optional[float] = None,
                 persist_callback: Optional[Callable[[], None]] = None):
        self.increment = increment
        self.persist_callback = persist_callback
        span = reasonable_max - reasonable_min
        if span <= 0.0:
            span = max(abs(reasonable_min), abs(reasonable_max), 1.0)
        self.slider_min = reasonable_min - 0.5 * span if slider_min is None else slider_min
        self.slider_max = reasonable_max + 0.5 * span if slider_max is None else slider_max
        self.digits = 0 if increment >= 1.0 else (2 if increment >= 0.01 else 3)
        self.set_func = set_func

        self.panel = wx.Panel(parent)
        panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(panel_sizer)
        self.panel.SetAutoLayout(1)
        self.panel.SetMinSize(wx.Size(132, -1))

        self.label = wx.StaticText(self.panel, label=self._format_multiline_label(label_text), style=wx.ALIGN_CENTER_HORIZONTAL)
        panel_sizer.Add(self.label, 0, wx.EXPAND | wx.BOTTOM, 2)

        self.slider = wx.Slider(
            self.panel,
            wx.ID_ANY,
            minValue=0,
            maxValue=self._float_to_int(self.slider_max),
            value=self._float_to_int(initial_value),
            style=wx.HORIZONTAL)
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
        panel_sizer.Add(self.value_text, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 2)
        self._refresh_value_label()

        self.slider.Bind(wx.EVT_SLIDER, self._handle_change)
        self._hovering = False
        self._wheel_armed = False
        self._pending_leave_check = False
        self._last_hover_mouse_screen_pos: Optional[wx.Point] = None
        self.hover_arm_timer = wx.Timer(self.slider)
        self.slider.Bind(wx.EVT_TIMER, self._handle_hover_arm_timer, id=self.hover_arm_timer.GetId())
        sizer.Add(self.panel, 0, wx.EXPAND | wx.ALL, 4)

    def _float_to_int(self, value: float) -> int:
        clipped_value = max(self.slider_min, min(self.slider_max, value))
        return int(round((clipped_value - self.slider_min) / self.increment))

    @staticmethod
    def _format_multiline_label(label_text: str) -> str:
        return label_text

    def _int_to_float(self, value: int) -> float:
        return self.slider_min + value * self.increment

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
        value = self.GetValue()
        self._refresh_value_label()
        self.set_func(value)
        if self.persist_callback is not None:
            self.persist_callback()

    def GetValue(self) -> float:
        return self._int_to_float(self.slider.GetValue())

    def SetValue(self, value: float):
        self.slider.SetValue(self._float_to_int(value))
        self._refresh_value_label()

    def Enable(self, enabled: bool):
        self.panel.Enable(bool(enabled))

class MediaPipeFacePoseConverter00Args:
    def __init__(self,
                 smile_threshold_min: float = 0.4,
                 smile_threshold_max: float = 0.6,
                 eyebrow_down_mode: EyebrowDownMode = EyebrowDownMode.ANGRY,
                 wink_mode: WinkMode = WinkMode.NORMAL,
                 eye_surprised_max: float = 0.5,
                 eye_blink_max: float = 0.8,
                 eye_open_gain: float = 0.0,
                 eyebrow_down_max: float = 0.4,
                 cheek_squint_min: float = 0.1,
                 cheek_squint_max: float = 0.7,
                 eye_rotation_factor: float = 1.0 / 0.75,
                 jaw_open_min: float = 0.1,
                 jaw_open_max: float = 0.4,
                 mouth_frown_max: float = 0.6,
                 mouth_funnel_min: float = 0.25,
                 mouth_funnel_max: float = 0.5,
                 iris_small_left=0.0,
                 iris_small_right=0.0,
                 head_x_offset=0.0,
                 head_y_offset=0.0,
                 head_z_offset=0.0,
                 tilt_compensation_deg: float = 0.0,
                 breathing_frequency: float = 20.0,
                 enable_breathing: bool = True,
                 enable_reactive_breathing: bool = False,
                 reactive_breathing_threshold: float = 0.35,
                 reactive_breathing_frequency: float = 38.0,
                 reactive_breathing_decay: float = 1.0,
                 mouth_input_mode: str = "face",
                 audio_input_source: str = "mic",
                 audio_mouth_threshold: float = -45.0,
                 audio_mouth_max_level: float = -18.0,
                 audio_mouth_attack: float = 0.25,
                 audio_mouth_release: float = 0.5,
                 audio_keep_face_smile: bool = False):
        self.iris_small_right = iris_small_left
        self.iris_small_left = iris_small_right

        self.wink_mode = wink_mode

        self.mouth_funnel_max = mouth_funnel_max
        self.mouth_funnel_min = mouth_funnel_min
        self.mouth_frown_max = mouth_frown_max

        self.jaw_open_max = jaw_open_max
        self.jaw_open_min = jaw_open_min

        self.eye_rotation_factor = eye_rotation_factor

        self.cheek_squint_max = cheek_squint_max
        self.cheek_squint_min = cheek_squint_min

        self.eyebrow_down_max = eyebrow_down_max

        self.eye_blink_max = eye_blink_max
        self.eye_open_gain = eye_open_gain
        self.eye_surprised_max = eye_surprised_max

        self.smile_threshold_min = smile_threshold_min
        self.smile_threshold_max = smile_threshold_max

        self.head_z_offset = head_z_offset
        self.head_y_offset = head_y_offset
        self.head_x_offset = head_x_offset
        self.tilt_compensation_deg = tilt_compensation_deg
        self.breathing_frequency = breathing_frequency
        self.enable_breathing = bool(enable_breathing)
        self.enable_reactive_breathing = enable_reactive_breathing
        self.reactive_breathing_threshold = reactive_breathing_threshold
        self.reactive_breathing_frequency = reactive_breathing_frequency
        self.reactive_breathing_decay = reactive_breathing_decay
        self.mouth_input_mode = mouth_input_mode if mouth_input_mode in ["face", "audio"] else "face"
        self.audio_input_source = audio_input_source if audio_input_source in ["mic", "loopback"] else "mic"
        self.audio_mouth_threshold = audio_mouth_threshold
        self.audio_mouth_max_level = audio_mouth_max_level
        self.audio_mouth_attack = audio_mouth_attack
        self.audio_mouth_release = audio_mouth_release
        self.audio_keep_face_smile = bool(audio_keep_face_smile)

        self.eyebrow_down_mode = eyebrow_down_mode

    def set_smile_threshold_min(self, new_value: float):
        self.smile_threshold_min = new_value

    def set_smile_threshold_max(self, new_value: float):
        self.smile_threshold_max = new_value

    def set_eye_surprised_max(self, new_value: float):
        self.eye_surprised_max = new_value

    def set_eye_blink_max(self, new_value: float):
        self.eye_blink_max = new_value

    def set_eye_open_gain(self, new_value: float):
        self.eye_open_gain = new_value

    def set_eyebrow_down_max(self, new_value: float):
        self.eyebrow_down_max = new_value

    def set_cheek_squint_min(self, new_value: float):
        self.cheek_squint_min = new_value

    def set_cheek_squint_max(self, new_value: float):
        self.cheek_squint_max = new_value

    def set_jaw_open_min(self, new_value: float):
        self.jaw_open_min = new_value

    def set_jaw_open_max(self, new_value: float):
        self.jaw_open_max = new_value

    def set_mouth_frown_max(self, new_value: float):
        self.mouth_frown_max = new_value

    def set_mouth_funnel_min(self, new_value: float):
        self.mouth_funnel_min = new_value

    def set_mouth_funnel_max(self, new_value: float):
        self.mouth_funnel_max = new_value

    def set_tilt_compensation_deg(self, new_value: float):
        self.tilt_compensation_deg = new_value

    def set_breathing_frequency(self, new_value: float):
        self.breathing_frequency = max(0.0, new_value)

    def set_enable_breathing(self, new_value: bool):
        self.enable_breathing = bool(new_value)

    def set_enable_reactive_breathing(self, new_value: bool):
        self.enable_reactive_breathing = bool(new_value)

    def set_reactive_breathing_threshold(self, new_value: float):
        self.reactive_breathing_threshold = max(0.01, new_value)

    def set_reactive_breathing_frequency(self, new_value: float):
        self.reactive_breathing_frequency = max(0.0, new_value)

    def set_reactive_breathing_decay(self, new_value: float):
        self.reactive_breathing_decay = max(0.01, new_value)

    def set_mouth_input_mode(self, new_value: str):
        self.mouth_input_mode = new_value if new_value in ["face", "audio"] else "face"

    def set_audio_input_source(self, new_value: str):
        self.audio_input_source = new_value if new_value in ["mic", "loopback"] else "mic"

    def set_audio_mouth_threshold(self, new_value: float):
        self.audio_mouth_threshold = clamp(float(new_value), -80.0, 20.0)

    def set_audio_mouth_max_level(self, new_value: float):
        self.audio_mouth_max_level = clamp(float(new_value), -80.0, 20.0)

    def set_audio_mouth_attack(self, new_value: float):
        """Seconds to approach full open (~95%); smaller = faster."""
        self.audio_mouth_attack = MediaPoseFacePoseConverter00.clamp_audio_mouth_time_sec(new_value)

    def set_audio_mouth_release(self, new_value: float):
        """Seconds to approach closed (~95%); smaller = faster."""
        self.audio_mouth_release = MediaPoseFacePoseConverter00.clamp_audio_mouth_time_sec(new_value)

    def set_audio_keep_face_smile(self, new_value: bool):
        self.audio_keep_face_smile = bool(new_value)

class MediaPoseFacePoseConverter00(MediaPipeFacePoseConverter):
    AUDIO_METER_MIN_DB = -80.0
    AUDIO_METER_MAX_DB = 20.0
    AUDIO_METER_GREEN_MAX_DB = -20.0
    AUDIO_METER_YELLOW_MAX_DB = -6.0
    AUDIO_METER_PEAK_HOLD_SECONDS = 1.8
    AUDIO_METER_PEAK_FALL_DB_PER_SEC = 18.0
    AUDIO_MOUTH_TIME_MIN_SEC = 0.05
    AUDIO_MOUTH_TIME_MAX_SEC = 3.0
    AUDIO_MOUTH_TIME_TO_RATE_SCALE = 3.0
    AUDIO_MOUTH_LEGACY_RATE_THRESHOLD = 2.0

    def __init__(self, args: Optional[MediaPipeFacePoseConverter00Args] = None):
        super().__init__()
        if args is None:
            args = MediaPipeFacePoseConverter00Args()
        self.args = args
        pose_parameters = get_pose_parameters()
        self.pose_size = 45

        self.eyebrow_troubled_left_index = pose_parameters.get_parameter_index("eyebrow_troubled_left")
        self.eyebrow_troubled_right_index = pose_parameters.get_parameter_index("eyebrow_troubled_right")
        self.eyebrow_angry_left_index = pose_parameters.get_parameter_index("eyebrow_angry_left")
        self.eyebrow_angry_right_index = pose_parameters.get_parameter_index("eyebrow_angry_right")
        self.eyebrow_happy_left_index = pose_parameters.get_parameter_index("eyebrow_happy_left")
        self.eyebrow_happy_right_index = pose_parameters.get_parameter_index("eyebrow_happy_right")
        self.eyebrow_raised_left_index = pose_parameters.get_parameter_index("eyebrow_raised_left")
        self.eyebrow_raised_right_index = pose_parameters.get_parameter_index("eyebrow_raised_right")
        self.eyebrow_lowered_left_index = pose_parameters.get_parameter_index("eyebrow_lowered_left")
        self.eyebrow_lowered_right_index = pose_parameters.get_parameter_index("eyebrow_lowered_right")
        self.eyebrow_serious_left_index = pose_parameters.get_parameter_index("eyebrow_serious_left")
        self.eyebrow_serious_right_index = pose_parameters.get_parameter_index("eyebrow_serious_right")

        self.eye_surprised_left_index = pose_parameters.get_parameter_index("eye_surprised_left")
        self.eye_surprised_right_index = pose_parameters.get_parameter_index("eye_surprised_right")
        self.eye_wink_left_index = pose_parameters.get_parameter_index("eye_wink_left")
        self.eye_wink_right_index = pose_parameters.get_parameter_index("eye_wink_right")
        self.eye_happy_wink_left_index = pose_parameters.get_parameter_index("eye_happy_wink_left")
        self.eye_happy_wink_right_index = pose_parameters.get_parameter_index("eye_happy_wink_right")
        self.eye_relaxed_left_index = pose_parameters.get_parameter_index("eye_relaxed_left")
        self.eye_relaxed_right_index = pose_parameters.get_parameter_index("eye_relaxed_right")
        self.eye_raised_lower_eyelid_left_index = pose_parameters.get_parameter_index("eye_raised_lower_eyelid_left")
        self.eye_raised_lower_eyelid_right_index = pose_parameters.get_parameter_index("eye_raised_lower_eyelid_right")

        self.iris_small_left_index = pose_parameters.get_parameter_index("iris_small_left")
        self.iris_small_right_index = pose_parameters.get_parameter_index("iris_small_right")

        self.iris_rotation_x_index = pose_parameters.get_parameter_index("iris_rotation_x")
        self.iris_rotation_y_index = pose_parameters.get_parameter_index("iris_rotation_y")

        self.head_x_index = pose_parameters.get_parameter_index("head_x")
        self.head_y_index = pose_parameters.get_parameter_index("head_y")
        self.neck_z_index = pose_parameters.get_parameter_index("neck_z")

        self.mouth_aaa_index = pose_parameters.get_parameter_index("mouth_aaa")
        self.mouth_iii_index = pose_parameters.get_parameter_index("mouth_iii")
        self.mouth_uuu_index = pose_parameters.get_parameter_index("mouth_uuu")
        self.mouth_eee_index = pose_parameters.get_parameter_index("mouth_eee")
        self.mouth_ooo_index = pose_parameters.get_parameter_index("mouth_ooo")

        self.mouth_lowered_corner_left_index = pose_parameters.get_parameter_index("mouth_lowered_corner_left")
        self.mouth_lowered_corner_right_index = pose_parameters.get_parameter_index("mouth_lowered_corner_right")
        self.mouth_raised_corner_left_index = pose_parameters.get_parameter_index("mouth_raised_corner_left")
        self.mouth_raised_corner_right_index = pose_parameters.get_parameter_index("mouth_raised_corner_right")

        self.body_y_index = pose_parameters.get_parameter_index("body_y")
        self.body_z_index = pose_parameters.get_parameter_index("body_z")
        self.breathing_index = pose_parameters.get_parameter_index("breathing")

        self.breathing_cycle_position = 0.0
        self.last_breathing_update_time = time.time()
        self.reactive_breathing_boost = 0.0
        self.last_breathing_motion_score = 0.0
        self.current_breathing_frequency = self.args.breathing_frequency
        self.last_reactive_breathing_state = "BASE"
        self.previous_motion_pose_signature = None
        self.audio_supported = sounddevice is not None
        self.audio_stream = None
        self.audio_stream_source = None
        self.audio_lock = threading.Lock()
        self.audio_level_rms = 0.0
        self.audio_level_peak = 0.0
        self.audio_mouth_value = 0.0
        self.audio_meter_peak_hold_db = self.AUDIO_METER_MIN_DB
        self.audio_meter_peak_hold_until = 0.0
        self.last_audio_update_time = time.time()
        self.audio_status_message = "音频未启用 / Audio inactive"
        self.audio_device_name = "-"
        self.ui_enabled = True
        self.ui_state_changed_callback: Optional[Callable[[], None]] = None

        self.panel = None
        self.current_pose_supplier = None

    def notify_ui_state_changed(self):
        if self.ui_state_changed_callback is not None:
            self.ui_state_changed_callback()

    def get_persistent_mouth_settings(self) -> dict:
        args = self.args
        return {
            "breathing_frequency": args.breathing_frequency,
            "enable_breathing": args.enable_breathing,
            "enable_reactive_breathing": args.enable_reactive_breathing,
            "reactive_breathing_threshold": args.reactive_breathing_threshold,
            "reactive_breathing_frequency": args.reactive_breathing_frequency,
            "reactive_breathing_decay": args.reactive_breathing_decay,
            "mouth_input_mode": args.mouth_input_mode,
            "audio_input_source": args.audio_input_source,
            "jaw_open_min": args.jaw_open_min,
            "jaw_open_max": args.jaw_open_max,
            "mouth_frown_max": args.mouth_frown_max,
            "mouth_funnel_min": args.mouth_funnel_min,
            "mouth_funnel_max": args.mouth_funnel_max,
            "audio_mouth_threshold": args.audio_mouth_threshold,
            "audio_mouth_max_level": args.audio_mouth_max_level,
            "audio_mouth_attack": args.audio_mouth_attack,
            "audio_mouth_release": args.audio_mouth_release,
            "audio_keep_face_smile": args.audio_keep_face_smile,
            "smile_threshold_min": args.smile_threshold_min,
            "smile_threshold_max": args.smile_threshold_max,
            "eye_surprised_max": args.eye_surprised_max,
            "eye_blink_max": args.eye_blink_max,
            "eye_open_gain": args.eye_open_gain,
            "eyebrow_down_max": args.eyebrow_down_max,
            "cheek_squint_min": args.cheek_squint_min,
            "cheek_squint_max": args.cheek_squint_max,
            "tilt_compensation_deg": args.tilt_compensation_deg,
            "iris_small_left": args.iris_small_left,
            "iris_small_right": args.iris_small_right,
        }

    def apply_persistent_mouth_settings(self, data: dict):
        if not isinstance(data, dict):
            return
        args = self.args
        mode = data.get("mouth_input_mode", args.mouth_input_mode)
        args.set_mouth_input_mode(mode if mode in ["face", "audio"] else "face")
        source = data.get("audio_input_source", args.audio_input_source)
        args.set_audio_input_source(source if source in ["mic", "loopback"] else "mic")
        if "breathing_frequency" in data:
            args.set_breathing_frequency(float(data["breathing_frequency"]))
        if "enable_breathing" in data:
            args.set_enable_breathing(bool(data["enable_breathing"]))
        if "enable_reactive_breathing" in data:
            args.set_enable_reactive_breathing(bool(data["enable_reactive_breathing"]))
        if "reactive_breathing_threshold" in data:
            args.set_reactive_breathing_threshold(float(data["reactive_breathing_threshold"]))
        if "reactive_breathing_frequency" in data:
            args.set_reactive_breathing_frequency(float(data["reactive_breathing_frequency"]))
        if "reactive_breathing_decay" in data:
            args.set_reactive_breathing_decay(float(data["reactive_breathing_decay"]))
        if "jaw_open_min" in data:
            args.set_jaw_open_min(float(data["jaw_open_min"]))
        if "jaw_open_max" in data:
            args.set_jaw_open_max(float(data["jaw_open_max"]))
        if "mouth_frown_max" in data:
            args.set_mouth_frown_max(float(data["mouth_frown_max"]))
        if "mouth_funnel_min" in data:
            args.set_mouth_funnel_min(float(data["mouth_funnel_min"]))
        if "mouth_funnel_max" in data:
            args.set_mouth_funnel_max(float(data["mouth_funnel_max"]))
        if "audio_mouth_threshold" in data:
            args.set_audio_mouth_threshold(
                self.normalize_stored_audio_level_db(data["audio_mouth_threshold"]))
        if "audio_mouth_max_level" in data:
            args.set_audio_mouth_max_level(
                self.normalize_stored_audio_level_db(data["audio_mouth_max_level"]))
        if "audio_mouth_attack" in data:
            args.set_audio_mouth_attack(
                self.normalize_stored_audio_mouth_time(data["audio_mouth_attack"]))
        if "audio_mouth_release" in data:
            args.set_audio_mouth_release(
                self.normalize_stored_audio_mouth_time(data["audio_mouth_release"]))
        if "audio_keep_face_smile" in data:
            args.set_audio_keep_face_smile(bool(data["audio_keep_face_smile"]))
        if "smile_threshold_min" in data:
            args.set_smile_threshold_min(float(data["smile_threshold_min"]))
        if "smile_threshold_max" in data:
            args.set_smile_threshold_max(float(data["smile_threshold_max"]))
        if "eye_surprised_max" in data:
            args.set_eye_surprised_max(float(data["eye_surprised_max"]))
        if "eye_blink_max" in data:
            args.set_eye_blink_max(float(data["eye_blink_max"]))
        if "eye_open_gain" in data:
            args.set_eye_open_gain(float(data["eye_open_gain"]))
        if "eyebrow_down_max" in data:
            args.set_eyebrow_down_max(float(data["eyebrow_down_max"]))
        if "cheek_squint_min" in data:
            args.set_cheek_squint_min(float(data["cheek_squint_min"]))
        if "cheek_squint_max" in data:
            args.set_cheek_squint_max(float(data["cheek_squint_max"]))
        if "tilt_compensation_deg" in data:
            args.set_tilt_compensation_deg(float(data["tilt_compensation_deg"]))
        if "iris_small_left" in data:
            args.iris_small_left = float(data["iris_small_left"])
        if "iris_small_right" in data:
            args.iris_small_right = float(data["iris_small_right"])
        self._sync_mouth_controls_from_args()

    def _sync_mouth_controls_from_args(self):
        args = self.args
        if hasattr(self, "breathing_frequency_slider"):
            self.breathing_frequency_slider.SetValue(args.breathing_frequency)
        if hasattr(self, "enable_breathing_checkbox"):
            self.enable_breathing_checkbox.SetValue(args.enable_breathing)
        if hasattr(self, "enable_reactive_breathing_checkbox"):
            self.enable_reactive_breathing_checkbox.SetValue(args.enable_reactive_breathing)
        if hasattr(self, "reactive_breathing_threshold_slider"):
            self.reactive_breathing_threshold_slider.SetValue(args.reactive_breathing_threshold)
        if hasattr(self, "reactive_breathing_frequency_slider"):
            self.reactive_breathing_frequency_slider.SetValue(args.reactive_breathing_frequency)
        if hasattr(self, "reactive_breathing_decay_slider"):
            self.reactive_breathing_decay_slider.SetValue(args.reactive_breathing_decay)
        self.refresh_breathing_ui_state()
        self.refresh_breathing_status_text()
        if hasattr(self, "mouth_input_mode_choice"):
            self.mouth_input_mode_choice.SetSelection(0 if args.mouth_input_mode == "face" else 1)
        if hasattr(self, "audio_input_source_choice"):
            self.audio_input_source_choice.SetSelection(0 if args.audio_input_source == "mic" else 1)
        if hasattr(self, "audio_keep_face_smile_checkbox"):
            self.audio_keep_face_smile_checkbox.SetValue(args.audio_keep_face_smile)
        mouth_sliders = (
            ("jaw_open_min_spin", args.jaw_open_min),
            ("jaw_open_max_spin", args.jaw_open_max),
            ("mouth_frown_max_spin", args.mouth_frown_max),
            ("mouth_funnel_min_spin", args.mouth_funnel_min),
            ("mouth_funnel_max_spin", args.mouth_funnel_max),
            ("audio_mouth_threshold_spin", args.audio_mouth_threshold),
            ("audio_mouth_max_level_spin", args.audio_mouth_max_level),
            ("audio_mouth_attack_spin", args.audio_mouth_attack),
            ("audio_mouth_release_spin", args.audio_mouth_release),
            ("smile_threshold_min_spin", args.smile_threshold_min),
            ("smile_threshold_max_spin", args.smile_threshold_max),
            ("eye_surprised_max_spin", args.eye_surprised_max),
            ("eye_blink_max_spin", args.eye_blink_max),
            ("eye_open_gain_spin", args.eye_open_gain),
            ("eyebrow_down_max_spin", args.eyebrow_down_max),
            ("cheek_squint_min_spin", args.cheek_squint_min),
            ("cheek_squint_max_spin", args.cheek_squint_max),
            ("tilt_compensation_deg_spin", args.tilt_compensation_deg),
        )
        for attr_name, value in mouth_sliders:
            control = getattr(self, attr_name, None)
            if control is not None:
                control.SetValue(value)
        if hasattr(self, "iris_left_slider"):
            self.iris_left_slider.SetValue(int(round(args.iris_small_left * 1000.0)))
        if hasattr(self, "iris_right_slider"):
            self.iris_right_slider.SetValue(int(round(args.iris_small_right * 1000.0)))
        if hasattr(self, "refresh_mouth_input_ui_state"):
            self.refresh_mouth_input_ui_state()
        self.refresh_audio_level_meter()

    def init_pose_converter_panel(
            self,
            parent,
            current_pose_supplier: Callable[[], Optional[MediaPipeFacePose]]):
        self.panel = wx.Panel(parent, style=wx.SIMPLE_BORDER)
        self.panel_sizer = wx.BoxSizer(wx.VERTICAL)
        self.panel.SetSizer(self.panel_sizer)
        self.panel.SetAutoLayout(1)
        parent.GetSizer().Add(self.panel, 0, wx.EXPAND)

        self.current_pose_supplier = current_pose_supplier

        if True:
            eyebrow_down_mode_text = wx.StaticText(
                self.panel, label=" --- 眉毛下压模式 / Eyebrow Down Mode --- ", style=wx.ALIGN_CENTER)
            self.panel_sizer.Add(eyebrow_down_mode_text, 0, wx.EXPAND)

            self.eyebrow_down_mode_choice = wx.Choice(
                self.panel,
                choices=[
                    "ANGRY",
                    "TROUBLED",
                    "SERIOUS",
                    "LOWERED",
                ])
            self.eyebrow_down_mode_choice.SetSelection(0)
            self.panel_sizer.Add(self.eyebrow_down_mode_choice, 0, wx.EXPAND)
            self.eyebrow_down_mode_choice.Bind(wx.EVT_CHOICE, self.change_eyebrow_down_mode)

        if True:
            separator = wx.StaticLine(self.panel, -1, size=(256, 5))
            self.panel_sizer.Add(separator, 0, wx.EXPAND)

            wink_mode_text = wx.StaticText(self.panel, label=" --- 眨眼模式 / Wink Mode --- ", style=wx.ALIGN_CENTER)
            self.panel_sizer.Add(wink_mode_text, 0, wx.EXPAND)

            self.wink_mode_choice = wx.Choice(
                self.panel,
                choices=[
                    "NORMAL",
                    "RELAXED",
                ])
            self.wink_mode_choice.SetSelection(0)
            self.panel_sizer.Add(self.wink_mode_choice, 0, wx.EXPAND)
            self.wink_mode_choice.Bind(wx.EVT_CHOICE, self.change_wink_mode)

        if True:
            separator = wx.StaticLine(self.panel, -1, size=(256, 5))
            self.panel_sizer.Add(separator, 0, wx.EXPAND)

            iris_size_text = wx.StaticText(self.panel, label=" --- 瞳孔大小 / Iris Size --- ", style=wx.ALIGN_CENTER)
            self.panel_sizer.Add(iris_size_text, 0, wx.EXPAND)

            iris_slider_panel = wx.Panel(self.panel)
            iris_slider_sizer = wx.BoxSizer(wx.VERTICAL)
            iris_slider_panel.SetSizer(iris_slider_sizer)
            iris_slider_panel.SetAutoLayout(1)
            self.panel_sizer.Add(iris_slider_panel, 0, wx.EXPAND | wx.ALL, 4)

            left_iris_row = wx.BoxSizer(wx.HORIZONTAL)
            iris_slider_sizer.Add(left_iris_row, 0, wx.EXPAND | wx.BOTTOM, 4)
            left_iris_label = wx.StaticText(iris_slider_panel, label="左 (系数 / factor)")
            left_iris_row.Add(left_iris_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            self.iris_left_slider = wx.Slider(
                iris_slider_panel, minValue=0, maxValue=1000, value=0, style=wx.HORIZONTAL)
            left_iris_row.Add(self.iris_left_slider, 1, wx.ALIGN_CENTER_VERTICAL)
            self.iris_left_slider.Bind(wx.EVT_SLIDER, self.change_iris_size)

            right_iris_row = wx.BoxSizer(wx.HORIZONTAL)
            iris_slider_sizer.Add(right_iris_row, 0, wx.EXPAND)
            right_iris_label = wx.StaticText(iris_slider_panel, label="右 (系数 / factor)")
            right_iris_row.Add(right_iris_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
            self.iris_right_slider = wx.Slider(
                iris_slider_panel, minValue=0, maxValue=1000, value=0, style=wx.HORIZONTAL)
            right_iris_row.Add(self.iris_right_slider, 1, wx.ALIGN_CENTER_VERTICAL)
            self.iris_right_slider.Bind(wx.EVT_SLIDER, self.change_iris_size)
            self.iris_right_slider.Enable(False)

            self.link_left_right_irises = wx.CheckBox(
                self.panel, label="左右使用相同数值 / Use same value for both sides")
            self.link_left_right_irises.SetValue(True)
            self.panel_sizer.Add(self.link_left_right_irises, wx.SizerFlags().CenterHorizontal().Border())
            self.link_left_right_irises.Bind(wx.EVT_CHECKBOX, self.link_left_right_irises_clicked)

        if True:
            separator = wx.StaticLine(self.panel, -1, size=(256, 5))
            self.panel_sizer.Add(separator, 0, wx.EXPAND)

            breathing_text = wx.StaticText(
                self.panel, label=" --- 呼吸 / Breathing --- ", style=wx.ALIGN_CENTER)
            self.panel_sizer.Add(breathing_text, 0, wx.EXPAND)

            self.breathing_panel = wx.Panel(self.panel)
            breathing_panel_sizer = wx.BoxSizer(wx.VERTICAL)
            self.breathing_panel.SetSizer(breathing_panel_sizer)
            self.breathing_panel.SetAutoLayout(1)
            self.panel_sizer.Add(self.breathing_panel, 0, wx.EXPAND)

            self.enable_breathing_checkbox = wx.CheckBox(
                self.breathing_panel,
                label="启用呼吸 / Enable Breathing")
            self.enable_breathing_checkbox.SetValue(self.args.enable_breathing)
            self.enable_breathing_checkbox.Bind(wx.EVT_CHECKBOX, self.enable_breathing_clicked)
            breathing_panel_sizer.Add(
                self.enable_breathing_checkbox,
                wx.SizerFlags().Border(wx.BOTTOM, 4))

            self.restart_breathing_cycle_button = wx.Button(
                self.breathing_panel, label="重启呼吸周期 / Restart Breathing Cycle")
            self.restart_breathing_cycle_button.Bind(wx.EVT_BUTTON, self.restart_breathing_cycle_clicked)
            breathing_panel_sizer.Add(self.restart_breathing_cycle_button, 0, wx.EXPAND)

            self.breathing_frequency_slider = self.create_spin_control(
                self.breathing_panel,
                slider_label("基础呼吸频率", "Base Breathing Rate", "次/分", "breaths/min"),
                self.args.breathing_frequency,
                self.args.set_breathing_frequency,
                reasonable_min=0.0,
                reasonable_max=60.0,
                increment=1.0,
                slider_min=0.0,
                slider_max=60.0,
                persist_on_change=True)

            self.enable_reactive_breathing_checkbox = wx.CheckBox(
                self.breathing_panel,
                label="启用动作加速呼吸 / Enable Reactive Breathing")
            self.enable_reactive_breathing_checkbox.SetValue(self.args.enable_reactive_breathing)
            self.enable_reactive_breathing_checkbox.Bind(wx.EVT_CHECKBOX, self.enable_reactive_breathing_clicked)
            breathing_panel_sizer.Add(
                self.enable_reactive_breathing_checkbox,
                wx.SizerFlags().Border(wx.TOP | wx.BOTTOM, 4))

            self.reactive_breathing_panel = wx.Panel(self.breathing_panel)
            reactive_breathing_sizer = wx.BoxSizer(wx.VERTICAL)
            self.reactive_breathing_panel.SetSizer(reactive_breathing_sizer)
            self.reactive_breathing_panel.SetAutoLayout(1)
            breathing_panel_sizer.Add(self.reactive_breathing_panel, 0, wx.EXPAND)

            self.reactive_breathing_threshold_slider = self.create_spin_control(
                self.reactive_breathing_panel,
                slider_label("触发阈值", "Trigger Threshold", "动作强度 0~1", "motion 0~1"),
                self.args.reactive_breathing_threshold,
                self.args.set_reactive_breathing_threshold,
                reasonable_min=0.05,
                reasonable_max=0.80,
                increment=0.01,
                slider_min=0.01,
                slider_max=1.20,
                persist_on_change=True)
            self.reactive_breathing_frequency_slider = self.create_spin_control(
                self.reactive_breathing_panel,
                slider_label("剧烈呼吸频率", "Reactive Breathing Rate", "次/分", "breaths/min"),
                self.args.reactive_breathing_frequency,
                self.args.set_reactive_breathing_frequency,
                reasonable_min=0.0,
                reasonable_max=60.0,
                increment=1.0,
                slider_min=0.0,
                slider_max=60.0,
                persist_on_change=True)
            self.reactive_breathing_decay_slider = self.create_spin_control(
                self.reactive_breathing_panel,
                slider_label("回落衰减", "Decay Rate", "1/秒", "1/s"),
                self.args.reactive_breathing_decay,
                self.args.set_reactive_breathing_decay,
                reasonable_min=0.10,
                reasonable_max=3.00,
                increment=0.05,
                slider_min=0.05,
                slider_max=5.00,
                persist_on_change=True)

            self.breathing_gauge = wx.Gauge(self.breathing_panel, style=wx.GA_HORIZONTAL, range=1000)
            breathing_panel_sizer.Add(self.breathing_gauge, 0, wx.EXPAND | wx.TOP, 4)

            self.breathing_status_text = wx.StaticText(self.breathing_panel, label="")
            breathing_panel_sizer.Add(self.breathing_status_text, 0, wx.EXPAND | wx.TOP, 4)
            self.refresh_breathing_ui_state()
            self.refresh_reactive_breathing_ui_state()
            self.refresh_breathing_status_text()

        if True:
            separator = wx.StaticLine(self.panel, -1, size=(256, 5))
            self.panel_sizer.Add(separator, 0, wx.EXPAND)

            mouth_input_text = wx.StaticText(
                self.panel, label=" --- 嘴型输入 / Mouth Input --- ", style=wx.ALIGN_CENTER)
            self.panel_sizer.Add(mouth_input_text, 0, wx.EXPAND)

            self.mouth_input_mode_choice = wx.Choice(
                self.panel,
                choices=[
                    "面捕张嘴 / Face-Tracked Mouth",
                    "声音张嘴 / Audio-Driven Mouth",
                ])
            self.mouth_input_mode_choice.SetSelection(0 if self.args.mouth_input_mode == "face" else 1)
            self.mouth_input_mode_choice.Bind(wx.EVT_CHOICE, self.change_mouth_input_mode)
            self.panel_sizer.Add(self.mouth_input_mode_choice, 0, wx.EXPAND)

            self.face_mouth_panel = wx.Panel(self.panel)
            face_mouth_sizer = wx.BoxSizer(wx.VERTICAL)
            self.face_mouth_panel.SetSizer(face_mouth_sizer)
            self.face_mouth_panel.SetAutoLayout(1)
            self.panel_sizer.Add(self.face_mouth_panel, 0, wx.EXPAND)

            self.jaw_open_min_spin = self.create_spin_control(
                self.face_mouth_panel,
                slider_label("张嘴最小", "Jaw Open Min", "开口度 0~1", "openness 0~1"),
                self.args.jaw_open_min, self.args.set_jaw_open_min,
                persist_on_change=True)
            self.jaw_open_max_spin = self.create_spin_control(
                self.face_mouth_panel,
                slider_label("张嘴最大", "Jaw Open Max", "开口度 0~1", "openness 0~1"),
                self.args.jaw_open_max, self.args.set_jaw_open_max,
                persist_on_change=True)
            self.mouth_frown_max_spin = self.create_spin_control(
                self.face_mouth_panel,
                slider_label("嘴角下撇最大", "Max Mouth Frown", "系数 0~1", "factor 0~1"),
                self.args.mouth_frown_max, self.args.set_mouth_frown_max,
                persist_on_change=True)
            self.mouth_funnel_min_spin = self.create_spin_control(
                self.face_mouth_panel,
                slider_label("收嘴最小", "Min Mouth Pucker", "系数 0~1", "factor 0~1"),
                self.args.mouth_funnel_min, self.args.set_mouth_funnel_min,
                persist_on_change=True)
            self.mouth_funnel_max_spin = self.create_spin_control(
                self.face_mouth_panel,
                slider_label("收嘴最大", "Max Mouth Pucker", "系数 0~1", "factor 0~1"),
                self.args.mouth_funnel_max, self.args.set_mouth_funnel_max,
                persist_on_change=True)

            self.audio_mouth_panel = wx.Panel(self.panel)
            audio_mouth_sizer = wx.BoxSizer(wx.VERTICAL)
            self.audio_mouth_panel.SetSizer(audio_mouth_sizer)
            self.audio_mouth_panel.SetAutoLayout(1)
            self.panel_sizer.Add(self.audio_mouth_panel, 0, wx.EXPAND)

            audio_latency_hint = wx.StaticText(
                self.audio_mouth_panel,
                label="声音张嘴有少量延时，属正常现象。\nAudio-driven mouth has slight latency; this is normal.")
            audio_mouth_sizer.Add(audio_latency_hint, 0, wx.EXPAND | wx.BOTTOM, 4)

            self.audio_input_source_choice = wx.Choice(
                self.audio_mouth_panel,
                choices=[
                    "麦克风输入 / Microphone",
                    "电脑内录 / System Audio (Loopback)",
                ])
            self.audio_input_source_choice.SetSelection(0 if self.args.audio_input_source == "mic" else 1)
            self.audio_input_source_choice.Bind(wx.EVT_CHOICE, self.change_audio_input_source)
            audio_mouth_sizer.Add(self.audio_input_source_choice, 0, wx.EXPAND | wx.BOTTOM, 4)

            self.audio_keep_face_smile_checkbox = wx.CheckBox(
                self.audio_mouth_panel,
                label="保留面捕微笑嘴角 / Keep Smile Corners from Face")
            self.audio_keep_face_smile_checkbox.SetValue(self.args.audio_keep_face_smile)
            self.audio_keep_face_smile_checkbox.Bind(wx.EVT_CHECKBOX, self.change_audio_keep_face_smile)
            audio_mouth_sizer.Add(self.audio_keep_face_smile_checkbox, 0, wx.EXPAND | wx.BOTTOM, 4)

            self.audio_mouth_threshold_spin = self.create_spin_control(
                self.audio_mouth_panel,
                slider_label("触发张嘴", "Open Threshold", "分贝", "dB"),
                self.args.audio_mouth_threshold,
                self.set_audio_mouth_threshold_from_ui,
                reasonable_min=self.AUDIO_METER_MIN_DB,
                reasonable_max=self.AUDIO_METER_MAX_DB,
                increment=0.5,
                slider_min=self.AUDIO_METER_MIN_DB,
                slider_max=self.AUDIO_METER_MAX_DB,
                persist_on_change=True)
            self.audio_mouth_max_level_spin = self.create_spin_control(
                self.audio_mouth_panel,
                slider_label("满张嘴", "Full Open", "分贝", "dB"),
                self.args.audio_mouth_max_level,
                self.set_audio_mouth_max_level_from_ui,
                reasonable_min=self.AUDIO_METER_MIN_DB,
                reasonable_max=self.AUDIO_METER_MAX_DB,
                increment=0.5,
                slider_min=self.AUDIO_METER_MIN_DB,
                slider_max=self.AUDIO_METER_MAX_DB,
                persist_on_change=True)
            self.audio_mouth_attack_spin = self.create_spin_control(
                self.audio_mouth_panel,
                slider_label("张嘴速度", "Mouth Open Speed", "秒·趋向全开", "s to full open"),
                self.args.audio_mouth_attack, self.args.set_audio_mouth_attack,
                reasonable_min=0.10,
                reasonable_max=1.50,
                increment=0.05,
                slider_min=self.AUDIO_MOUTH_TIME_MIN_SEC,
                slider_max=self.AUDIO_MOUTH_TIME_MAX_SEC,
                persist_on_change=True)
            self.audio_mouth_release_spin = self.create_spin_control(
                self.audio_mouth_panel,
                slider_label("闭嘴速度", "Mouth Close Speed", "秒·趋向闭合", "s to closed"),
                self.args.audio_mouth_release, self.args.set_audio_mouth_release,
                reasonable_min=0.10,
                reasonable_max=1.50,
                increment=0.05,
                slider_min=self.AUDIO_MOUTH_TIME_MIN_SEC,
                slider_max=self.AUDIO_MOUTH_TIME_MAX_SEC,
                persist_on_change=True)
            audio_speed_hint = wx.StaticText(
                self.audio_mouth_panel,
                label="数值越小越快 / smaller value = faster")
            audio_mouth_sizer.Add(audio_speed_hint, 0, wx.EXPAND | wx.BOTTOM, 2)

            self.audio_level_meter_panel = wx.Panel(self.audio_mouth_panel, size=(260, 58), style=wx.SIMPLE_BORDER)
            self.audio_level_meter_panel.SetBackgroundStyle(wx.BG_STYLE_PAINT)
            self.audio_level_meter_panel.SetMinSize(wx.Size(200, 52))
            self.audio_level_meter_panel.Bind(wx.EVT_PAINT, self.paint_audio_level_meter_panel)
            self.audio_level_meter_panel.Bind(wx.EVT_ERASE_BACKGROUND, lambda event: None)
            audio_mouth_sizer.Add(self.audio_level_meter_panel, 0, wx.EXPAND | wx.TOP, 4)

            self.audio_mouth_status_text = wx.StaticText(self.audio_mouth_panel, label="")
            self.audio_mouth_panel.GetSizer().Add(self.audio_mouth_status_text, 0, wx.EXPAND | wx.TOP, 4)
            self.refresh_mouth_input_ui_state()

        if True:
            separator = wx.StaticLine(self.panel, -1, size=(256, 5))
            self.panel_sizer.Add(separator, 0, wx.EXPAND)

            face_orientation_text = wx.StaticText(
                self.panel, label="--- 面部朝向 / Face Orientation ---", style=wx.ALIGN_CENTER)
            self.panel_sizer.Add(face_orientation_text, 0, wx.EXPAND)

            self.calibrate_face_orientation_button = wx.Button(
                self.panel, label="标定朝向（我正看前方） / Calibrate Forward Gaze")
            self.calibrate_face_orientation_button.Bind(wx.EVT_BUTTON, self.calibrate_face_orientation_clicked)
            self.panel_sizer.Add(self.calibrate_face_orientation_button, 0, wx.EXPAND)

        if True:
            separator = wx.StaticLine(self.panel, -1, size=(256, 5))
            self.panel_sizer.Add(separator, 0, wx.EXPAND)

            conversion_parameters_text = wx.StaticText(
                self.panel, label="--- 转换参数 / Conversion Parameters ---", style=wx.ALIGN_CENTER)
            self.panel_sizer.Add(conversion_parameters_text, 0, wx.EXPAND)

            conversion_param_panel = wx.Panel(self.panel)
            self.panel_sizer.Add(conversion_param_panel, 0, wx.EXPAND)
            conversion_panel_sizer = wx.BoxSizer(wx.VERTICAL)
            conversion_param_panel.SetSizer(conversion_panel_sizer)
            conversion_param_panel.SetAutoLayout(1)

            self.smile_threshold_min_spin = self.create_spin_control(
                conversion_param_panel,
                slider_label("微笑阈值最小", "Smile Threshold Min", "系数 0~1", "factor 0~1"),
                self.args.smile_threshold_min, self.args.set_smile_threshold_min,
                persist_on_change=True)
            self.smile_threshold_max_spin = self.create_spin_control(
                conversion_param_panel,
                slider_label("微笑阈值最大", "Smile Threshold Max", "系数 0~1", "factor 0~1"),
                self.args.smile_threshold_max, self.args.set_smile_threshold_max,
                persist_on_change=True)
            self.eye_surprised_max_spin = self.create_spin_control(
                conversion_param_panel,
                slider_label("惊讶眼最大", "Max Eye Surprise", "系数 0~1", "factor 0~1"),
                self.args.eye_surprised_max, self.args.set_eye_surprised_max,
                persist_on_change=True)
            self.eye_blink_max_spin = self.create_spin_control(
                conversion_param_panel,
                slider_label("眨眼最大", "Max Eye Blink", "系数 0~1", "factor 0~1"),
                self.args.eye_blink_max, self.args.set_eye_blink_max,
                persist_on_change=True)
            self.eye_open_gain_spin = self.create_spin_control(
                conversion_param_panel,
                slider_label("眼睛张开增益", "Eye Open Gain", "加减到开合", "offset ±1"),
                self.args.eye_open_gain, self.args.set_eye_open_gain,
                reasonable_min=-1.0,
                reasonable_max=1.0,
                increment=0.01,
                slider_min=-1.0,
                slider_max=1.0,
                persist_on_change=True)
            self.eyebrow_down_max_spin = self.create_spin_control(
                conversion_param_panel,
                slider_label("眉下压最大", "Max Eyebrow Down", "系数 0~1", "factor 0~1"),
                self.args.eyebrow_down_max, self.args.set_eyebrow_down_max,
                persist_on_change=True)
            self.cheek_squint_min_spin = self.create_spin_control(
                conversion_param_panel,
                slider_label("脸颊挤压最小", "Min Cheek Squint", "系数 0~1", "factor 0~1"),
                self.args.cheek_squint_min, self.args.set_cheek_squint_min,
                persist_on_change=True)
            self.cheek_squint_max_spin = self.create_spin_control(
                conversion_param_panel,
                slider_label("脸颊挤压最大", "Max Cheek Squint", "系数 0~1", "factor 0~1"),
                self.args.cheek_squint_max, self.args.set_cheek_squint_max,
                persist_on_change=True)
            self.tilt_compensation_deg_spin = self.create_spin_control(
                conversion_param_panel,
                slider_label("倾斜数据补偿", "Tilt Compensation", "度", "deg"),
                self.args.tilt_compensation_deg,
                self.args.set_tilt_compensation_deg,
                reasonable_min=-30.0,
                reasonable_max=30.0,
                increment=0.5,
                slider_min=-30.0,
                slider_max=30.0,
                persist_on_change=True)

        self.panel_sizer.Fit(self.panel)

    def create_spin_control(self,
                            parent,
                            label: str,
                            initial_value: float,
                            set_func: Callable[[float], None],
                            reasonable_min: float = 0.0,
                            reasonable_max: float = 1.0,
                            increment: float = 0.01,
                            slider_min: Optional[float] = None,
                            slider_max: Optional[float] = None,
                            persist_on_change: bool = False):
        sizer = parent.GetSizer()
        persist_callback = self.notify_ui_state_changed if persist_on_change else None
        return FloatSliderControl(
            parent=parent,
            sizer=sizer,
            label_text=label,
            initial_value=initial_value,
            reasonable_min=reasonable_min,
            reasonable_max=reasonable_max,
            increment=increment,
            set_func=set_func,
            slider_min=slider_min,
            slider_max=slider_max,
            persist_callback=persist_callback)

    def extract_euler_angles(self, mediapipe_face_pose: MediaPipeFacePose):
        M = mediapipe_face_pose.xform_matrix[0:3, 0:3]
        rot = Rotation.from_matrix(M)
        return rot.as_euler('xyz', degrees=False)

    def apply_face_orientation_calibration(self) -> bool:
        """Same as clicking Calibrate Forward Gaze / 标定朝向（我正看前方）."""
        if self.current_pose_supplier is None:
            return False

        mediapipe_face_pose = self.current_pose_supplier()
        if mediapipe_face_pose is None:
            return False

        euler_angles = self.extract_euler_angles(mediapipe_face_pose)
        self.args.head_x_offset = euler_angles[0]
        self.args.head_y_offset = euler_angles[1]
        self.args.head_z_offset = euler_angles[2]
        return True

    def calibrate_face_orientation_clicked(self, event: wx.Event):
        self.apply_face_orientation_calibration()

    def _relayout_pose_converter_panel(self) -> None:
        if self.panel is None:
            return
        self.panel.Layout()
        parent = self.panel.GetParent()
        if parent is not None:
            parent.Layout()

    def refresh_breathing_ui_state(self):
        breathing_enabled = bool(self.args.enable_breathing)
        if hasattr(self, "restart_breathing_cycle_button"):
            self.restart_breathing_cycle_button.Enable(breathing_enabled)
        if hasattr(self, "breathing_frequency_slider"):
            self.breathing_frequency_slider.Enable(breathing_enabled)
        if hasattr(self, "enable_reactive_breathing_checkbox"):
            self.enable_reactive_breathing_checkbox.Enable(breathing_enabled)
        if hasattr(self, "breathing_gauge"):
            self.breathing_gauge.Enable(breathing_enabled)
        if hasattr(self, "breathing_status_text"):
            self.breathing_status_text.Enable(breathing_enabled)
        self.refresh_reactive_breathing_ui_state()

    def refresh_reactive_breathing_ui_state(self):
        reactive_enabled = bool(self.args.enable_breathing and self.args.enable_reactive_breathing)
        if hasattr(self, "reactive_breathing_panel"):
            self.reactive_breathing_panel.Enable(reactive_enabled)
        for slider_name in (
                "reactive_breathing_threshold_slider",
                "reactive_breathing_frequency_slider",
                "reactive_breathing_decay_slider"):
            slider = getattr(self, slider_name, None)
            if slider is not None:
                slider.Enable(reactive_enabled)
        self._relayout_pose_converter_panel()

    def refresh_breathing_status_text(self):
        if not hasattr(self, "breathing_status_text"):
            return
        if not _wx_widget_alive(getattr(self, "breathing_status_text", None)):
            return
        if not self.args.enable_breathing:
            self.breathing_status_text.SetLabelText("呼吸已关闭 / Breathing disabled")
            self.breathing_status_text.Wrap(max(120, self.breathing_status_text.GetParent().GetClientSize().x - 12))
            return
        if self.args.enable_reactive_breathing:
            status_text = "当前 / Current: %.1f bpm | 动作 / Motion: %.3f | 状态 / State: %s" % (
                self.current_breathing_frequency,
                self.last_breathing_motion_score,
                self.last_reactive_breathing_state)
        else:
            status_text = "当前 / Current: %.1f bpm | 基础呼吸 / Base only" % self.current_breathing_frequency
        self.breathing_status_text.SetLabelText(status_text)
        self.breathing_status_text.Wrap(max(120, self.breathing_status_text.GetParent().GetClientSize().x - 12))

    def stop_audio_stream(self):
        if self.audio_stream is None:
            return
        try:
            self.audio_stream.stop()
            self.audio_stream.close()
        except Exception:
            pass
        self.audio_stream = None
        self.audio_stream_source = None
        self.audio_device_name = "-"

    def get_audio_stream_settings(self):
        if self.args.audio_input_source == "mic":
            default_input_index = sounddevice.default.device[0] if sounddevice is not None else None
            device_name = "-"
            if default_input_index is not None and default_input_index >= 0:
                try:
                    device_name = sounddevice.query_devices(default_input_index)["name"]
                except Exception:
                    device_name = "-"
            return dict(
                channels=1,
                samplerate=16000,
                blocksize=512,
                dtype="float32",
                callback=self.audio_input_callback
            ), "麦克风已连接 / Microphone ready", device_name

        if sounddevice is None or not hasattr(sounddevice, "WasapiSettings"):
            raise RuntimeError("当前环境不支持内录 / Loopback unsupported")
        output_device_index = sounddevice.default.device[1]
        if output_device_index is None or output_device_index < 0:
            raise RuntimeError("未找到默认输出设备 / No default output device")
        output_device = sounddevice.query_devices(output_device_index)
        hostapi = sounddevice.query_hostapis(output_device["hostapi"])
        if "wasapi" not in hostapi["name"].lower():
            raise RuntimeError("电脑内录需要 WASAPI 输出设备 / Loopback requires WASAPI")
        channels = max(1, min(2, int(output_device["max_output_channels"])))
        samplerate = int(output_device["default_samplerate"]) if output_device["default_samplerate"] else 48000
        return dict(
            device=output_device_index,
            channels=channels,
            samplerate=samplerate,
            blocksize=512,
            dtype="float32",
            callback=self.audio_input_callback,
            extra_settings=sounddevice.WasapiSettings(loopback=True)
        ), "电脑内录已连接 / System loopback ready", output_device["name"]

    def ensure_audio_stream_state(self):
        should_run = self.ui_enabled and self.args.mouth_input_mode == "audio"
        if not should_run:
            self.stop_audio_stream()
            if self.args.mouth_input_mode != "audio":
                self.audio_status_message = "音频未启用 / Audio inactive"
            return
        if not self.audio_supported:
            self.audio_status_message = "sounddevice 不可用 / Unavailable"
            return
        if self.audio_stream is not None and self.audio_stream_source == self.args.audio_input_source:
            return
        if self.audio_stream is not None:
            self.stop_audio_stream()
        try:
            stream_kwargs, status_message, device_name = self.get_audio_stream_settings()
            self.audio_stream = sounddevice.InputStream(**stream_kwargs)
            self.audio_stream.start()
            self.audio_stream_source = self.args.audio_input_source
            self.audio_status_message = status_message
            self.audio_device_name = device_name
        except Exception as exc:
            self.audio_stream = None
            self.audio_stream_source = None
            self.audio_device_name = "-"
            source_label = "内录 / Loopback" if self.args.audio_input_source == "loopback" else "麦克风 / Mic"
            self.audio_status_message = f"{source_label} 不可用 / Unavailable: {exc}"

    @staticmethod
    def linear_to_db(linear: float,
                     floor_db: float = AUDIO_METER_MIN_DB,
                     ceiling_db: float = AUDIO_METER_MAX_DB) -> float:
        linear = max(1e-8, float(linear))
        return clamp(20.0 * math.log10(linear), floor_db, ceiling_db)

    @staticmethod
    def clamp_audio_mouth_time_sec(value: float) -> float:
        return clamp(
            float(value),
            MediaPoseFacePoseConverter00.AUDIO_MOUTH_TIME_MIN_SEC,
            MediaPoseFacePoseConverter00.AUDIO_MOUTH_TIME_MAX_SEC)

    @staticmethod
    def normalize_stored_audio_mouth_time(value: float) -> float:
        """Legacy configs stored response rate (larger=faster); new configs store seconds (smaller=faster)."""
        stored_value = float(value)
        if stored_value > MediaPoseFacePoseConverter00.AUDIO_MOUTH_LEGACY_RATE_THRESHOLD:
            stored_value = MediaPoseFacePoseConverter00.AUDIO_MOUTH_TIME_TO_RATE_SCALE / stored_value
        return MediaPoseFacePoseConverter00.clamp_audio_mouth_time_sec(stored_value)

    @staticmethod
    def audio_mouth_response_rate_from_time_sec(time_sec: float) -> float:
        time_sec = max(MediaPoseFacePoseConverter00.AUDIO_MOUTH_TIME_MIN_SEC, float(time_sec))
        return MediaPoseFacePoseConverter00.AUDIO_MOUTH_TIME_TO_RATE_SCALE / time_sec

    @staticmethod
    def normalize_stored_audio_level_db(value: float) -> float:
        """Legacy configs stored linear amplitude (0..1); new configs use dB."""
        stored_value = float(value)
        if 0.0 < stored_value <= 1.0:
            return MediaPoseFacePoseConverter00.linear_to_db(stored_value)
        return clamp(stored_value, MediaPoseFacePoseConverter00.AUDIO_METER_MIN_DB,
                     MediaPoseFacePoseConverter00.AUDIO_METER_MAX_DB)

    def set_audio_mouth_threshold_from_ui(self, new_value: float):
        self.args.set_audio_mouth_threshold(new_value)
        self.refresh_audio_level_meter()

    def set_audio_mouth_max_level_from_ui(self, new_value: float):
        self.args.set_audio_mouth_max_level(new_value)
        self.refresh_audio_level_meter()

    def refresh_audio_level_meter(self):
        if hasattr(self, "audio_level_meter_panel"):
            self.audio_level_meter_panel.Refresh(False)

    @staticmethod
    def db_to_meter_fraction(db: float,
                            min_db: float = AUDIO_METER_MIN_DB,
                            max_db: float = AUDIO_METER_MAX_DB) -> float:
        if max_db <= min_db:
            return 0.0
        return clamp((db - min_db) / (max_db - min_db), 0.0, 1.0)

    def audio_input_callback(self, indata, frames, callback_time, status):
        if status:
            self.audio_status_message = f"音频状态 / Audio status: {status}"
        if indata is None or len(indata) == 0:
            return
        samples = numpy.mean(indata, axis=1).astype(numpy.float32, copy=True)
        rms_level = float(numpy.sqrt(numpy.mean(numpy.square(samples))))
        peak_level = float(numpy.max(numpy.abs(samples))) if samples.size > 0 else 0.0
        with self.audio_lock:
            self.audio_level_rms = rms_level
            self.audio_level_peak = peak_level

    def paint_audio_level_meter_panel(self, event: wx.Event):
        dc = wx.AutoBufferedPaintDC(self.audio_level_meter_panel)
        width, height = self.audio_level_meter_panel.GetClientSize()
        bg = wx.Colour(43, 43, 43)
        dc.SetBackground(wx.Brush(bg))
        dc.Clear()
        if width <= 8 or height <= 8:
            return

        min_db = self.AUDIO_METER_MIN_DB
        max_db = self.AUDIO_METER_MAX_DB
        margin_x = 6
        header_h = 16
        scale_h = 12
        bar_h = max(10, height - header_h - scale_h - 6)
        bar_top = header_h + 2
        bar_bottom = bar_top + bar_h
        bar_left = margin_x
        bar_right = width - margin_x
        bar_width = max(1, bar_right - bar_left)

        green_end = self.db_to_meter_fraction(self.AUDIO_METER_GREEN_MAX_DB, min_db, max_db)
        yellow_end = self.db_to_meter_fraction(self.AUDIO_METER_YELLOW_MAX_DB, min_db, max_db)

        zone_colors = (
            (wx.Colour(28, 72, 38), wx.Colour(55, 185, 75)),
            (wx.Colour(72, 68, 28), wx.Colour(210, 195, 55)),
            (wx.Colour(72, 32, 32), wx.Colour(210, 70, 65)),
        )
        zone_bounds = (0.0, green_end, yellow_end, 1.0)
        for zone_index in range(3):
            x0 = bar_left + int(bar_width * zone_bounds[zone_index])
            x1 = bar_left + int(bar_width * zone_bounds[zone_index + 1])
            if x1 <= x0:
                continue
            dc.SetBrush(wx.Brush(zone_colors[zone_index][0]))
            dc.SetPen(wx.Pen(zone_colors[zone_index][0]))
            dc.DrawRectangle(x0, bar_top, x1 - x0, bar_h)

        with self.audio_lock:
            peak_linear = self.audio_level_peak
            device_name = self.audio_device_name
        level_db = self.linear_to_db(peak_linear, min_db, max_db)
        level_frac = self.db_to_meter_fraction(level_db, min_db, max_db)
        peak_db = max(level_db, self.audio_meter_peak_hold_db)
        peak_frac = self.db_to_meter_fraction(peak_db, min_db, max_db)

        for zone_index in range(3):
            zone_start = zone_bounds[zone_index]
            zone_stop = zone_bounds[zone_index + 1]
            if level_frac <= zone_start:
                continue
            fill_stop = min(level_frac, zone_stop)
            x0 = bar_left + int(bar_width * zone_start)
            x1 = bar_left + int(bar_width * fill_stop)
            if x1 <= x0:
                continue
            dc.SetBrush(wx.Brush(zone_colors[zone_index][1]))
            dc.SetPen(wx.Pen(zone_colors[zone_index][1]))
            dc.DrawRectangle(x0, bar_top, x1 - x0, bar_h)

        self._draw_audio_meter_db_marker(
            dc, bar_left, bar_width, bar_top, bar_h, min_db, max_db,
            self.args.audio_mouth_threshold, wx.Colour(90, 175, 255), "开 / Open")
        self._draw_audio_meter_db_marker(
            dc, bar_left, bar_width, bar_top, bar_h, min_db, max_db,
            self.args.audio_mouth_max_level, wx.Colour(255, 165, 70), "满 / Full")

        peak_x = bar_left + int(bar_width * peak_frac)
        if peak_x > bar_left:
            dc.SetPen(wx.Pen(wx.Colour(245, 245, 245), 2))
            dc.DrawLine(peak_x, bar_top, peak_x, bar_bottom)

        dc.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        dc.SetTextForeground(wx.Colour(210, 210, 210))
        dc.DrawText("电平 / Level", margin_x, 1)
        device_label = device_name if device_name and device_name != "-" else "Device"
        if len(device_label) > 18:
            device_label = device_label[:17] + "…"
        dc.DrawText(device_label, margin_x + 72, 1)
        peak_label = "%.1f dB" % level_db
        tw, _ = dc.GetTextExtent(peak_label)
        dc.DrawText(peak_label, max(margin_x + 72, bar_right - tw), 1)

        dc.SetPen(wx.Pen(wx.Colour(90, 90, 90), 1))
        dc.SetTextForeground(wx.Colour(150, 150, 150))
        scale_y = bar_bottom + 2
        for tick_db in range(int(min_db), int(max_db) + 1, 10):
            frac = self.db_to_meter_fraction(float(tick_db), min_db, max_db)
            x = bar_left + int(bar_width * frac)
            tick_h = 4 if tick_db % 20 == 0 else 2
            dc.DrawLine(x, bar_bottom, x, bar_bottom + tick_h)
            if tick_db % 20 == 0:
                label = str(tick_db)
                tw, _ = dc.GetTextExtent(label)
                dc.DrawText(label, x - tw // 2, scale_y)

    def _draw_audio_meter_db_marker(self,
                                    dc: wx.DC,
                                    bar_left: int,
                                    bar_width: int,
                                    bar_top: int,
                                    bar_h: int,
                                    min_db: float,
                                    max_db: float,
                                    marker_db: float,
                                    color: wx.Colour,
                                    label: str):
        marker_x = bar_left + int(bar_width * self.db_to_meter_fraction(marker_db, min_db, max_db))
        dc.SetPen(wx.Pen(color, 2))
        dc.DrawLine(marker_x, bar_top, marker_x, bar_top + bar_h)
        dc.SetFont(wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        dc.SetTextForeground(color)
        tw, th = dc.GetTextExtent(label)
        label_x = clamp(marker_x - tw // 2, bar_left, bar_left + bar_width - tw)
        dc.DrawText(label, label_x, bar_top + 1)

    def refresh_audio_mouth_status_text(self):
        if not hasattr(self, "audio_mouth_status_text"):
            return
        if self.args.mouth_input_mode != "audio":
            status_text = "当前模式 / Current mode: 面捕张嘴 / Face tracking"
        else:
            source_text = "内录 / Loopback" if self.args.audio_input_source == "loopback" else "麦克风 / Mic"
            rms_db = self.linear_to_db(self.audio_level_rms)
            status_text = (
                "输入 / Source: %s | 设备 / Device: %s | RMS: %.1f dB | "
                "开阈 / Open: %.1f dB | 满阈 / Full: %.1f dB | 开口 / Mouth: %.3f | %s") % (
                source_text,
                self.audio_device_name,
                rms_db,
                self.args.audio_mouth_threshold,
                self.args.audio_mouth_max_level,
                self.audio_mouth_value,
                self.audio_status_message)
        if self.audio_mouth_status_text.GetLabel() != status_text:
            self.audio_mouth_status_text.SetLabelText(status_text)
            self.audio_mouth_status_text.Wrap(max(120, self.audio_mouth_status_text.GetParent().GetClientSize().x - 12))
        if hasattr(self, "audio_level_meter_panel"):
            self.audio_level_meter_panel.Refresh(False)

    def refresh_mouth_input_ui_state(self):
        mouth_mode = self.args.mouth_input_mode
        if hasattr(self, "mouth_input_mode_choice"):
            self.mouth_input_mode_choice.SetSelection(0 if mouth_mode == "face" else 1)
        if hasattr(self, "face_mouth_panel"):
            self.face_mouth_panel.Show(mouth_mode == "face")
        if hasattr(self, "audio_mouth_panel"):
            self.audio_mouth_panel.Show(mouth_mode == "audio")
        if hasattr(self, "audio_input_source_choice"):
            self.audio_input_source_choice.SetSelection(0 if self.args.audio_input_source == "mic" else 1)
        self.ensure_audio_stream_state()
        self.refresh_audio_mouth_status_text()
        self._relayout_pose_converter_panel()

    def change_mouth_input_mode(self, event: wx.Event):
        selection = self.mouth_input_mode_choice.GetSelection()
        self.args.set_mouth_input_mode("audio" if selection == 1 else "face")
        if self.args.mouth_input_mode != "audio":
            self.audio_mouth_value = 0.0
        self.refresh_mouth_input_ui_state()
        self.notify_ui_state_changed()

    def change_audio_input_source(self, event: wx.Event):
        selection = self.audio_input_source_choice.GetSelection()
        self.args.set_audio_input_source("loopback" if selection == 1 else "mic")
        self.stop_audio_stream()
        self.refresh_mouth_input_ui_state()
        self.notify_ui_state_changed()

    def change_audio_keep_face_smile(self, event: wx.Event):
        if hasattr(self, "audio_keep_face_smile_checkbox"):
            self.args.set_audio_keep_face_smile(self.audio_keep_face_smile_checkbox.GetValue())
        self.notify_ui_state_changed()

    def set_panel_enabled(self, enabled: bool):
        self.ui_enabled = enabled
        if self.panel is not None:
            self.panel.Enable(enabled)
        if hasattr(self, "breathing_panel"):
            self.breathing_panel.Enable(enabled)
        if hasattr(self, "mouth_input_mode_choice"):
            self.mouth_input_mode_choice.Enable(enabled)
        self.ensure_audio_stream_state()
        self.refresh_mouth_input_ui_state()

    def shutdown(self):
        self.stop_audio_stream()

    def enable_breathing_clicked(self, event: wx.Event):
        self.args.set_enable_breathing(self.enable_breathing_checkbox.GetValue())
        if not self.args.enable_breathing:
            self.breathing_cycle_position = 0.0
            self.reactive_breathing_boost = 0.0
            self.last_breathing_motion_score = 0.0
            self.last_reactive_breathing_state = "BASE"
            if hasattr(self, "breathing_gauge"):
                self.breathing_gauge.SetValue(0)
        self.refresh_breathing_ui_state()
        self.refresh_breathing_status_text()
        self.notify_ui_state_changed()

    def restart_breathing_cycle_clicked(self, event: wx.Event):
        self.breathing_cycle_position = 0.0
        self.last_breathing_update_time = time.time()
        self.reactive_breathing_boost = 0.0
        self.last_reactive_breathing_state = "BASE"
        self.refresh_breathing_status_text()

    def enable_reactive_breathing_clicked(self, event: wx.Event):
        self.args.set_enable_reactive_breathing(self.enable_reactive_breathing_checkbox.GetValue())
        if not self.args.enable_reactive_breathing:
            self.reactive_breathing_boost = 0.0
            self.last_reactive_breathing_state = "BASE"
        self.refresh_breathing_ui_state()
        self.refresh_breathing_status_text()
        self.notify_ui_state_changed()

    def update_reactive_breathing_frequency(self, pose_signature: List[float], now: float) -> float:
        dt = max(0.0, now - self.last_breathing_update_time)
        decay = max(0.01, self.args.reactive_breathing_decay)
        self.reactive_breathing_boost *= math.exp(-decay * dt)

        if self.previous_motion_pose_signature is None or len(self.previous_motion_pose_signature) != len(pose_signature):
            motion_score = 0.0
        else:
            diffs = [current_value - previous_value
                     for current_value, previous_value in zip(pose_signature, self.previous_motion_pose_signature)]
            motion_score = math.sqrt(sum(diff * diff for diff in diffs))
        self.previous_motion_pose_signature = list(pose_signature)
        self.last_breathing_motion_score = motion_score

        base_frequency = max(0.0, self.args.breathing_frequency)
        trigger_frequency = max(base_frequency, self.args.reactive_breathing_frequency)
        if self.args.enable_reactive_breathing and motion_score >= self.args.reactive_breathing_threshold:
            self.reactive_breathing_boost = max(self.reactive_breathing_boost, trigger_frequency - base_frequency)
            self.last_reactive_breathing_state = "TRIGGER"
        elif self.reactive_breathing_boost > 0.01:
            self.last_reactive_breathing_state = "DECAY"
        else:
            self.reactive_breathing_boost = 0.0
            self.last_reactive_breathing_state = "BASE"

        return base_frequency + self.reactive_breathing_boost

    def refresh_audio_input_runtime(self, now: Optional[float] = None):
        """Keep mic/loopback stream and level meter alive without calling convert()."""
        if now is None:
            now = time.time()
        if self.args.mouth_input_mode != "audio":
            if self.audio_stream is not None or self.audio_level_peak > 0.0 or self.audio_level_rms > 0.0:
                self.update_audio_mouth_value(now)
            return
        self.update_audio_mouth_value(now)

    def update_audio_mouth_value(self, now: float) -> float:
        if self.args.mouth_input_mode != "audio":
            self.audio_mouth_value = 0.0
            self.last_audio_update_time = now
            self.audio_status_message = "音频未启用 / Audio inactive"
            self.refresh_audio_mouth_status_text()
            return 0.0

        self.ensure_audio_stream_state()
        dt = max(0.0, now - self.last_audio_update_time)
        with self.audio_lock:
            rms_level = self.audio_level_rms
            peak_linear = self.audio_level_peak
        peak_db = self.linear_to_db(peak_linear)
        if peak_db > self.audio_meter_peak_hold_db:
            self.audio_meter_peak_hold_db = peak_db
            self.audio_meter_peak_hold_until = now + self.AUDIO_METER_PEAK_HOLD_SECONDS
        elif now > self.audio_meter_peak_hold_until:
            self.audio_meter_peak_hold_db = max(
                peak_db,
                self.audio_meter_peak_hold_db - self.AUDIO_METER_PEAK_FALL_DB_PER_SEC * dt)
        rms_db = self.linear_to_db(rms_level)
        threshold_db = self.args.audio_mouth_threshold
        max_db = max(threshold_db + 0.1, self.args.audio_mouth_max_level)
        target_value = clamp((rms_db - threshold_db) / (max_db - threshold_db), 0.0, 1.0)
        open_time_sec = self.args.audio_mouth_attack
        close_time_sec = self.args.audio_mouth_release
        time_sec = open_time_sec if target_value >= self.audio_mouth_value else close_time_sec
        response_rate = self.audio_mouth_response_rate_from_time_sec(time_sec)
        alpha = 1.0 - math.exp(-response_rate * dt)
        self.audio_mouth_value += (target_value - self.audio_mouth_value) * alpha
        self.last_audio_update_time = now
        self.refresh_audio_mouth_status_text()
        return self.audio_mouth_value

    def change_eyebrow_down_mode(self, event: wx.Event):
        selected_index = self.eyebrow_down_mode_choice.GetSelection()
        if selected_index == 0:
            self.args.eyebrow_down_mode = EyebrowDownMode.ANGRY
        elif selected_index == 1:
            self.args.eyebrow_down_mode = EyebrowDownMode.TROUBLED
        elif selected_index == 2:
            self.args.eyebrow_down_mode = EyebrowDownMode.SERIOUS
        else:
            self.args.eyebrow_down_mode = EyebrowDownMode.LOWERED

    def change_wink_mode(self, event: wx.Event):
        selected_index = self.wink_mode_choice.GetSelection()
        if selected_index == 0:
            self.args.wink_mode = WinkMode.NORMAL
        else:
            self.args.wink_mode = WinkMode.RELAXED

    def change_iris_size(self, event: wx.Event):
        if self.link_left_right_irises.GetValue():
            left_value = self.iris_left_slider.GetValue()
            right_value = self.iris_right_slider.GetValue()
            if left_value != right_value:
                self.iris_right_slider.SetValue(left_value)
            self.args.iris_small_left = left_value / 1000.0
            self.args.iris_small_right = left_value / 1000.0
        else:
            self.args.iris_small_left = self.iris_left_slider.GetValue() / 1000.0
            self.args.iris_small_right = self.iris_right_slider.GetValue() / 1000.0
        self.notify_ui_state_changed()

    def link_left_right_irises_clicked(self, event: wx.Event):
        if self.link_left_right_irises.GetValue():
            self.iris_right_slider.Enable(False)
        else:
            self.iris_right_slider.Enable(True)
        self.change_iris_size(event)

    def decompose_head_body_param(self, param, threshold=2.0 / 3):
        if abs(param) < threshold:
            return (param, 0.0)
        else:
            if param < 0:
                sign = -1.0
            else:
                sign = 1.0
            return (threshold * sign, (abs(param) - threshold) * sign)

    def convert(self, mediapipe_face_pose: MediaPipeFacePose) -> List[float]:
        pose = [0.0 for i in range(self.pose_size)]
        now = time.time()

        blendshape_params = mediapipe_face_pose.blendshape_params

        smile_value = \
            (blendshape_params[MOUTH_SMILE_LEFT] + blendshape_params[MOUTH_SMILE_RIGHT]) / 2.0 \
            + blendshape_params[MOUTH_SHRUG_UPPER]
        if self.args.smile_threshold_min >= self.args.smile_threshold_max:
            smile_degree = 0.0
        else:
            if smile_value < self.args.smile_threshold_min:
                smile_degree = 0.0
            elif smile_value > self.args.smile_threshold_max:
                smile_degree = 1.0
            else:
                smile_degree = (smile_value - self.args.smile_threshold_min) / (
                        self.args.smile_threshold_max - self.args.smile_threshold_min)

        # Eyebrow
        if True:
            brow_inner_up = blendshape_params[BROW_INNER_UP]
            brow_outer_up_right = blendshape_params[BROW_OUTER_UP_RIGHT]
            brow_outer_up_left = blendshape_params[BROW_OUTER_UP_LEFT]

            brow_up_left = clamp(brow_inner_up + brow_outer_up_left, 0.0, 1.0)
            brow_up_right = clamp(brow_inner_up + brow_outer_up_right, 0.0, 1.0)
            pose[self.eyebrow_raised_left_index] = brow_up_left
            pose[self.eyebrow_raised_right_index] = brow_up_right

            if self.args.eyebrow_down_max <= 0.0:
                brow_down_left = 0.0
                brow_down_right = 0.0
            else:
                brow_down_left = (1.0 - smile_degree) \
                                 * clamp(blendshape_params[BROW_DOWN_LEFT] / self.args.eyebrow_down_max, 0.0, 1.0)
                brow_down_right = (1.0 - smile_degree) \
                                  * clamp(blendshape_params[BROW_DOWN_RIGHT] / self.args.eyebrow_down_max, 0.0, 1.0)

            if self.args.eyebrow_down_mode == EyebrowDownMode.TROUBLED:
                pose[self.eyebrow_troubled_left_index] = brow_down_left
                pose[self.eyebrow_troubled_right_index] = brow_down_right
            elif self.args.eyebrow_down_mode == EyebrowDownMode.ANGRY:
                pose[self.eyebrow_angry_left_index] = brow_down_left
                pose[self.eyebrow_angry_right_index] = brow_down_right
            elif self.args.eyebrow_down_mode == EyebrowDownMode.LOWERED:
                pose[self.eyebrow_lowered_left_index] = brow_down_left
                pose[self.eyebrow_lowered_right_index] = brow_down_right
            elif self.args.eyebrow_down_mode == EyebrowDownMode.SERIOUS:
                pose[self.eyebrow_serious_left_index] = brow_down_left
                pose[self.eyebrow_serious_right_index] = brow_down_right

            brow_happy_value = clamp(smile_value, 0.0, 1.0) * smile_degree
            pose[self.eyebrow_happy_left_index] = brow_happy_value
            pose[self.eyebrow_happy_right_index] = brow_happy_value

        # Eye
        if True:
            # Surprised
            if self.args.eye_surprised_max <= 0.0:
                pose[self.eye_surprised_left_index] = 0.0
                pose[self.eye_surprised_right_index] = 0.0
            else:
                pose[self.eye_surprised_left_index] = clamp(
                    blendshape_params[EYE_WIDE_LEFT] / self.args.eye_surprised_max, 0.0, 1.0)
                pose[self.eye_surprised_right_index] = clamp(
                    blendshape_params[EYE_WIDE_RIGHT] / self.args.eye_surprised_max, 0.0, 1.0)

            # Wink
            if self.args.wink_mode == WinkMode.NORMAL:
                wink_left_index = self.eye_wink_left_index
                wink_right_index = self.eye_wink_right_index
            else:
                wink_left_index = self.eye_relaxed_left_index
                wink_right_index = self.eye_relaxed_right_index
            if self.args.eye_blink_max <= 0:
                pose[wink_left_index] = 0.0
                pose[wink_right_index] = 0.0
                pose[self.eye_happy_wink_left_index] = 0.0
                pose[self.eye_happy_wink_right_index] = 0.0
            else:
                pose[wink_left_index] = (1.0 - smile_degree) * clamp(
                    blendshape_params[EYE_BLINK_LEFT] / self.args.eye_blink_max, 0.0, 1.0)
                pose[wink_right_index] = (1.0 - smile_degree) * clamp(
                    blendshape_params[EYE_BLINK_RIGHT] / self.args.eye_blink_max, 0.0, 1.0)
                pose[self.eye_happy_wink_left_index] = smile_degree * clamp(
                    blendshape_params[EYE_BLINK_LEFT] / self.args.eye_blink_max, 0.0, 1.0)
                pose[self.eye_happy_wink_right_index] = smile_degree * clamp(
                    blendshape_params[EYE_BLINK_RIGHT] / self.args.eye_blink_max, 0.0, 1.0)

            eye_gain = float(self.args.eye_open_gain)
            if abs(eye_gain) > 1e-6:
                pose[self.eye_surprised_left_index] = clamp(
                    pose[self.eye_surprised_left_index] + eye_gain, 0.0, 1.0)
                pose[self.eye_surprised_right_index] = clamp(
                    pose[self.eye_surprised_right_index] + eye_gain, 0.0, 1.0)
                pose[wink_left_index] = clamp(pose[wink_left_index] - eye_gain, 0.0, 1.0)
                pose[wink_right_index] = clamp(pose[wink_right_index] - eye_gain, 0.0, 1.0)
                pose[self.eye_happy_wink_left_index] = clamp(
                    pose[self.eye_happy_wink_left_index] - eye_gain, 0.0, 1.0)
                pose[self.eye_happy_wink_right_index] = clamp(
                    pose[self.eye_happy_wink_right_index] - eye_gain, 0.0, 1.0)

            # Lower eyelid
            cheek_squint_denom = self.args.cheek_squint_max - self.args.cheek_squint_min
            if cheek_squint_denom <= 0.0:
                pose[self.eye_raised_lower_eyelid_left_index] = 0.0
                pose[self.eye_raised_lower_eyelid_right_index] = 0.0
            else:
                pose[self.eye_raised_lower_eyelid_left_index] = \
                    clamp(
                        (blendshape_params[CHEEK_SQUINT_LEFT] - self.args.cheek_squint_min) / cheek_squint_denom,
                        0.0, 1.0)
                pose[self.eye_raised_lower_eyelid_right_index] = \
                    clamp(
                        (blendshape_params[CHEEK_SQUINT_RIGHT] - self.args.cheek_squint_min) / cheek_squint_denom,
                        0.0, 1.0)

        # Iris rotation
        if True:
            eye_rotation_y = (blendshape_params[EYE_LOOK_IN_LEFT]
                              - blendshape_params[EYE_LOOK_OUT_LEFT]
                              - blendshape_params[EYE_LOOK_IN_RIGHT]
                              + blendshape_params[EYE_LOOK_OUT_RIGHT]) / 2.0 * self.args.eye_rotation_factor
            pose[self.iris_rotation_y_index] = clamp(eye_rotation_y, -1.0, 1.0)

            eye_rotation_x = (blendshape_params[EYE_LOOK_UP_LEFT]
                              + blendshape_params[EYE_LOOK_UP_RIGHT]
                              - blendshape_params[EYE_LOOK_DOWN_LEFT]
                              - blendshape_params[EYE_LOOK_DOWN_RIGHT]) / 2.0 * self.args.eye_rotation_factor
            pose[self.iris_rotation_x_index] = clamp(eye_rotation_x, -1.0, 1.0)

        # Iris size
        if True:
            pose[self.iris_small_left_index] = self.args.iris_small_left
            pose[self.iris_small_right_index] = self.args.iris_small_right

        # Head rotation
        if True:
            euler_angles = self.extract_euler_angles(mediapipe_face_pose)
            euler_angles[0] -= self.args.head_x_offset
            euler_angles[1] -= self.args.head_y_offset
            euler_angles[2] -= self.args.head_z_offset

            x_param = clamp(-euler_angles[0] * 180.0 / math.pi, -15.0, 15.0) / 15.0
            pose[self.head_x_index] = x_param

            y_param = clamp(-euler_angles[1] * 180.0 / math.pi, -10.0, 10.0) / 10.0
            pose[self.head_y_index] = y_param
            pose[self.body_y_index] = y_param

            z_degrees = euler_angles[2] * 180.0 / math.pi + self.args.tilt_compensation_deg
            z_param = clamp(z_degrees, -15.0, 15.0) / 15.0
            pose[self.neck_z_index] = z_param
            pose[self.body_z_index] = z_param

        # Mouth
        if True:
            if self.args.mouth_input_mode == "audio":
                mouth_open = self.update_audio_mouth_value(now)
            else:
                jaw_open_denom = self.args.jaw_open_max - self.args.jaw_open_min
                if jaw_open_denom <= 0:
                    mouth_open = 0.0
                else:
                    mouth_open = clamp((blendshape_params[JAW_OPEN] - self.args.jaw_open_min) / jaw_open_denom, 0.0, 1.0)
            pose[self.mouth_aaa_index] = mouth_open
            use_face_mouth_corners = (
                self.args.mouth_input_mode != "audio" or self.args.audio_keep_face_smile)
            if use_face_mouth_corners:
                pose[self.mouth_raised_corner_left_index] = clamp(smile_value, 0.0, 1.0)
                pose[self.mouth_raised_corner_right_index] = clamp(smile_value, 0.0, 1.0)
            else:
                pose[self.mouth_raised_corner_left_index] = 0.0
                pose[self.mouth_raised_corner_right_index] = 0.0

            is_mouth_open = mouth_open > 0.0
            if not is_mouth_open:
                if use_face_mouth_corners:
                    if self.args.mouth_frown_max <= 0:
                        mouth_frown_value = 0.0
                    else:
                        mouth_frown_value = clamp(
                            (blendshape_params[MOUTH_FROWN_LEFT] + blendshape_params[
                                MOUTH_FROWN_RIGHT]) / self.args.mouth_frown_max, 0.0, 1.0)
                else:
                    mouth_frown_value = 0.0
                pose[self.mouth_lowered_corner_left_index] = mouth_frown_value
                pose[self.mouth_lowered_corner_right_index] = mouth_frown_value
            else:
                pose[self.mouth_lowered_corner_left_index] = 0.0
                pose[self.mouth_lowered_corner_right_index] = 0.0
                if self.args.mouth_input_mode == "audio":
                    pose[self.mouth_iii_index] = 0.0
                    pose[self.mouth_uuu_index] = 0.0
                    pose[self.mouth_ooo_index] = 0.0
                else:
                    mouth_lower_down = clamp(
                        blendshape_params[MOUTH_LOWER_DOWN_LEFT] + blendshape_params[MOUTH_LOWER_DOWN_RIGHT], 0.0, 1.0)
                    mouth_funnel = blendshape_params[MOUTH_FUNNEL]
                    mouth_pucker = blendshape_params[MOUTH_PUCKER]

                    mouth_point = [mouth_open, mouth_lower_down, mouth_funnel, mouth_pucker]

                    aaa_point = [1.0, 1.0, 0.0, 0.0]
                    iii_point = [0.0, 1.0, 0.0, 0.0]
                    uuu_point = [0.5, 0.3, 0.25, 0.75]
                    ooo_point = [1.0, 0.5, 0.5, 0.4]

                    decomp = numpy.array([0, 0, 0, 0])
                    M = numpy.array([
                        aaa_point,
                        iii_point,
                        uuu_point,
                        ooo_point
                    ])

                    def loss(decomp):
                        return numpy.linalg.norm(numpy.matmul(decomp, M) - mouth_point) \
                            + 0.01 * numpy.linalg.norm(decomp, ord=1)

                    opt_result = scipy.optimize.minimize(
                        loss, decomp, bounds=[(0.0, 1.0), (0.0, 1.0), (0.0, 1.0), (0.0, 1.0)])
                    decomp = opt_result["x"]
                    restricted_decomp = [decomp.item(0), decomp.item(1), decomp.item(2), decomp.item(3)]
                    pose[self.mouth_aaa_index] = restricted_decomp[0]
                    pose[self.mouth_iii_index] = restricted_decomp[1]
                    mouth_funnel_denom = self.args.mouth_funnel_max - self.args.mouth_funnel_min
                    if mouth_funnel_denom <= 0:
                        ooo_alpha = 0.0
                        uo_value = 0.0
                    else:
                        ooo_alpha = clamp((mouth_funnel - self.args.mouth_funnel_min) / mouth_funnel_denom, 0.0, 1.0)
                        uo_value = clamp(restricted_decomp[2] + restricted_decomp[3], 0.0, 1.0)
                    pose[self.mouth_uuu_index] = uo_value * (1.0 - ooo_alpha)
                    pose[self.mouth_ooo_index] = uo_value * ooo_alpha

        pose_signature = pose[:self.breathing_index] + pose[self.breathing_index + 1:]
        if not self.args.enable_breathing:
            pose[self.breathing_index] = 0.0
            if self.panel is not None and _wx_widget_alive(getattr(self, "breathing_gauge", None)):
                _safe_set_gauge_value(self.breathing_gauge, 0)
                self.refresh_breathing_status_text()
            return pose

        frequency = max(0.0, self.args.breathing_frequency)
        if self.args.enable_reactive_breathing:
            frequency = self.update_reactive_breathing_frequency(pose_signature, now)
        else:
            self.previous_motion_pose_signature = list(pose_signature)
            self.reactive_breathing_boost = 0.0
            self.last_breathing_motion_score = 0.0
            self.last_reactive_breathing_state = "BASE"

        if frequency <= 0.0:
            value = 0.0
            self.breathing_cycle_position = 0.0
        else:
            dt = max(0.0, now - self.last_breathing_update_time)
            self.breathing_cycle_position = (self.breathing_cycle_position + dt * frequency / 60.0) % 1.0
            value = (-math.cos(2 * math.pi * self.breathing_cycle_position) + 1.0) / 2.0
        self.last_breathing_update_time = now
        self.current_breathing_frequency = frequency
        pose[self.breathing_index] = value

        if self.panel is not None and _wx_widget_alive(getattr(self, "breathing_gauge", None)):
            _safe_set_gauge_value(self.breathing_gauge, int(1000 * value))
            self.refresh_breathing_status_text()

        return pose
