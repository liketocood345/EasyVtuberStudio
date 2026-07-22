# ══ 设计手册嵌入 ══
# 权威：f-068 · 独立「简易区域晃动」窗；图层详情入口；立绘源图涂抹
"""Standalone region-wobble editor window (opened from layer detail dock)."""
from __future__ import annotations

import math
from typing import Optional, TYPE_CHECKING

import numpy
import wx

from region_wobble import (
    DEFAULT_PIN_RADIUS,
    IDLE_MODE_STILL_FROZEN,
    IDLE_MODE_STILL_WOBBLE,
    W_EPS,
    _auto_axis_from_mask,
    axis_passes_through_island,
    axes_for_mask,
    composite_on_checkerboard,
    overlay_guides_rgba,
    overlay_island_labels_rgba,
    overlay_mask_preview_rgba,
    paint_brush,
    pin_inside_mask,
    pick_axis_for_island,
    pick_axis_for_mask,
    pins_for_island,
    pins_for_mask,
    preview_angle_deg,
    warp_hinge_island,
)
from region_wobble_host import (
    layer_wobble_state,
    persist_masks,
    sync_layer_slot_from_state,
)

if TYPE_CHECKING:
    pass

BRUSH_ZOOM = 1.0
DEFAULT_ZOOM = 1.0
PREVIEW_MIN_H = 320
FRAME_MIN_SIZE = (560, 760)
PREVIEW_ANIM_MS = 50
TOOL_BRUSH = "brush"
TOOL_PIN = "pin"
TOOL_AXIS = "axis"
MODE_PAINT = "paint"
MODE_AXIS = "guides"
AXIS_MIN_DRAG_PX = 4.0


def _wx_bitmap_to_rgba(bitmap: wx.Bitmap) -> Optional[numpy.ndarray]:
    if bitmap is None or not bitmap.IsOk():
        return None
    img = bitmap.ConvertToImage()
    w, h = img.GetWidth(), img.GetHeight()
    rgb = numpy.frombuffer(img.GetData(), dtype=numpy.uint8).reshape(h, w, 3).copy()
    if img.HasAlpha():
        a = numpy.frombuffer(img.GetAlpha(), dtype=numpy.uint8).reshape(h, w)
    else:
        a = numpy.full((h, w), 255, dtype=numpy.uint8)
    out = numpy.zeros((h, w, 4), dtype=numpy.uint8)
    out[:, :, :3] = rgb
    out[:, :, 3] = a
    return out


def _rgba_to_bitmap(rgba: numpy.ndarray) -> wx.Bitmap:
    h, w = int(rgba.shape[0]), int(rgba.shape[1])
    rgb = numpy.ascontiguousarray(rgba[:, :, :3])
    alpha = numpy.ascontiguousarray(rgba[:, :, 3])
    image = wx.Image(w, h, rgb.tobytes(), alpha.tobytes())
    return image.ConvertToBitmap()


def still_preview_rgba(main_frame, target: str) -> Optional[numpy.ndarray]:
    """Still paint canvas: character uses 立绘源图; layer uses selected asset."""
    if target == "layer":
        sid = main_frame.basic_layers_state.selected_slot_id
        if sid is None:
            return None
        layer = main_frame.basic_layers_state.get_slot(int(sid))
        if layer is None or not layer.asset_path:
            return None
        return main_frame.layer_asset_cache.load_image_rgba(layer)
    # Character: identify / paint on 立绘源图 (wx_source_image), not THA keyframe.
    src = getattr(main_frame, "wx_source_image", None)
    rgba = _wx_bitmap_to_rgba(src) if src is not None else None
    if rgba is not None:
        return rgba
    cache = getattr(getattr(main_frame, "output_enhancement", None), "keyframe_cache", None)
    cached = getattr(cache, "rgba", None) if cache is not None else None
    if cached is not None:
        return numpy.ascontiguousarray(cached)
    return None


def still_preview_source_label(main_frame, target: str) -> str:
    if target == "layer":
        sid = main_frame.basic_layers_state.selected_slot_id
        if sid is None:
            return "图层素材（未选中）"
        return f"图层素材 slot={sid}"
    src = getattr(main_frame, "wx_source_image", None)
    if src is not None and src.IsOk():
        return f"立绘源图 {src.GetWidth()}×{src.GetHeight()}"
    cache = getattr(getattr(main_frame, "output_enhancement", None), "keyframe_cache", None)
    cached = getattr(cache, "rgba", None) if cache is not None else None
    if cached is not None:
        return f"keyframe 回退 {cached.shape[1]}×{cached.shape[0]}"
    return "无立绘源图"


def normalize_idle_wobble(mode: object) -> bool:
    return str(mode or "").strip().lower() != IDLE_MODE_STILL_FROZEN


class RegionWobbleLayerPanel(wx.Panel):
    """Controls + scrolled still preview for f-068 (multi-region, paint / guides modes)."""

    def __init__(self, parent: wx.Window, layer_window) -> None:
        super().__init__(parent)
        self.layer_window = layer_window
        self.main_frame = layer_window.main_frame
        self._zoom = DEFAULT_ZOOM
        self._painting = False
        self._base_rgba: Optional[numpy.ndarray] = None
        self._edit_mode = MODE_PAINT
        self._tool = TOOL_BRUSH
        self._axis_draft_start: Optional[tuple[float, float]] = None
        self._axis_draft_end: Optional[tuple[float, float]] = None
        self._axis_dragging = False
        self._status_msg = ""
        self._preview_anim = True
        self._refreshing_regions = False
        self._refreshing_islands = False

        root = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(root)

        title = wx.StaticText(
            self, label="简易区域晃动 / Region wobble (f-068)")
        font = title.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(font)
        root.Add(title, 0, wx.ALL, 4)

        self.enabled_cb = wx.CheckBox(self, label="启用 / Enable")
        self.idle_cb = wx.CheckBox(self, label="静止时仍晃动 / Wobble while still")
        self.idle_cb.SetValue(True)
        self.pose_hook_cb = wx.CheckBox(self, label="部位移动挂钩岛 / Pose hooks islands")
        self.pose_hook_cb.SetValue(True)
        self.pose_hook_cb.SetToolTip(
            "开启：转头姿态驱动岛弹簧，并平移岛/钉/轴以跟随 THA 部位（减轻耳朵出岛）。\n"
            "关闭：岛钉死在涂选像素，仅静止晃动/残余弹簧，不跟部位。")
        self.phase_stagger_cb = wx.CheckBox(self, label="岛周期交错 / Stagger island phase")
        self.phase_stagger_cb.SetValue(False)
        self.phase_stagger_cb.SetToolTip(
            "开启：同掩膜多岛静止晃动相位错开——两岛相反(π)，三岛均分一周(0 / 2π/3 / 4π/3)。\n"
            "关闭：各岛同相位晃动。")
        row0 = wx.BoxSizer(wx.HORIZONTAL)
        row0.Add(self.enabled_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        row0.Add(self.idle_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        row0.Add(self.pose_hook_cb, 0, wx.ALIGN_CENTER_VERTICAL)
        root.Add(row0, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        row0b = wx.BoxSizer(wx.HORIZONTAL)
        row0b.Add(self.phase_stagger_cb, 0, wx.ALIGN_CENTER_VERTICAL)
        root.Add(row0b, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        self.source_label = wx.StaticText(self, label="目标: —")
        self.source_label.SetForegroundColour(wx.Colour(80, 80, 90))
        root.Add(self.source_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        region_row = wx.BoxSizer(wx.HORIZONTAL)
        region_row.Add(
            wx.StaticText(self, label="涂选区域"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.region_choice = wx.Choice(self, choices=["区域1"])
        region_row.Add(self.region_choice, 1, wx.EXPAND | wx.RIGHT, 6)
        self.add_region_btn = wx.Button(self, label="新建区域")
        self.del_region_btn = wx.Button(self, label="删除当前区域")
        region_row.Add(self.add_region_btn, 0, wx.RIGHT, 4)
        region_row.Add(self.del_region_btn, 0)
        root.Add(region_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        island_row = wx.BoxSizer(wx.HORIZONTAL)
        island_row.Add(
            wx.StaticText(self, label="活动岛"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.island_choice = wx.Choice(self, choices=["岛1", "岛2", "岛3"])
        self.island_choice.SetSelection(0)
        self.island_choice.SetToolTip(
            "同掩膜最多 3 个活动连通域（按面积排序）；半透明数字标在预览上。")
        island_row.Add(self.island_choice, 1, wx.EXPAND | wx.RIGHT, 6)
        island_row.Add(
            wx.StaticText(self, label="强度"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.strength_spin = wx.SpinCtrlDouble(self, min=0.0, max=1e6, initial=0.35, inc=0.05)
        self.strength_spin.SetDigits(2)
        island_row.Add(self.strength_spin, 0, wx.RIGHT, 8)
        island_row.Add(
            wx.StaticText(self, label="速度"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.speed_spin = wx.SpinCtrlDouble(self, min=0.0, max=1e6, initial=1.0, inc=0.05)
        self.speed_spin.SetDigits(2)
        island_row.Add(self.speed_spin, 0)
        root.Add(island_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        mode_row = wx.BoxSizer(wx.HORIZONTAL)
        self.mode_paint_btn = wx.ToggleButton(self, label="涂选区域")
        self.mode_guides_btn = wx.ToggleButton(self, label="中轴编辑")
        self.mode_paint_btn.SetValue(True)
        mode_row.Add(self.mode_paint_btn, 0, wx.RIGHT, 6)
        mode_row.Add(self.mode_guides_btn, 0)
        root.Add(mode_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        tool_row = wx.BoxSizer(wx.HORIZONTAL)
        self.tool_row = tool_row
        self.tool_brush = wx.ToggleButton(self, label="画笔")
        self.tool_pin = wx.ToggleButton(self, label="固定点钉")
        self.tool_axis = wx.ToggleButton(self, label="摆动中轴")
        self.tool_brush.SetValue(True)
        tool_row.Add(self.tool_brush, 0, wx.RIGHT, 6)
        tool_row.Add(self.tool_pin, 0, wx.RIGHT, 6)
        tool_row.Add(self.tool_axis, 0)
        root.Add(tool_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        brush_row = wx.BoxSizer(wx.HORIZONTAL)
        self.erase_cb = wx.CheckBox(self, label="橡皮")
        brush_row.Add(self.erase_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        brush_row.Add(wx.StaticText(self, label="半径"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.radius_label = brush_row.GetChildren()[-1].GetWindow()
        self.radius_spin = wx.SpinCtrlDouble(self, min=2.0, max=128.0, initial=28.0, inc=1.0)
        brush_row.Add(self.radius_spin, 0, wx.RIGHT, 8)
        brush_row.Add(wx.StaticText(self, label="不透明"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self.opacity_label = brush_row.GetChildren()[-1].GetWindow()
        self.opacity_spin = wx.SpinCtrlDouble(self, min=0.05, max=1.0, initial=0.55, inc=0.05)
        self.opacity_spin.SetDigits(2)
        brush_row.Add(self.opacity_spin, 0)
        self.brush_row = brush_row
        root.Add(brush_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.clear_btn = wx.Button(self, label="清除掩膜")
        self.clear_pins_btn = wx.Button(self, label="清除点钉")
        self.clear_axis_btn = wx.Button(self, label="清除中轴")
        self.refresh_btn = wx.Button(self, label="刷新预览")
        btn_row.Add(self.clear_btn, 0, wx.RIGHT, 6)
        btn_row.Add(self.clear_pins_btn, 0, wx.RIGHT, 6)
        btn_row.Add(self.clear_axis_btn, 0, wx.RIGHT, 6)
        btn_row.Add(self.refresh_btn, 0)
        root.Add(btn_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        self.hint = wx.StaticText(
            self,
            label=(
                "目标由图层列表选中项决定（角色行→立绘源图，图层行→该 slot 素材）。"
                "「涂选区域」只画笔；「中轴编辑」只点钉/摆动中轴。"
                "同掩膜最多 3 个活动岛（面积排序），预览半透明数字标识；"
                "每岛可单独调强度/速度，仅用区内点钉与穿过该岛的射线。"))
        self.hint.Wrap(520)
        root.Add(self.hint, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        self.guide_status = wx.StaticText(self, label="射线: 未设置 · 点钉: 0")
        self.guide_status.SetForegroundColour(wx.Colour(30, 110, 160))
        root.Add(self.guide_status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        anim_row = wx.BoxSizer(wx.HORIZONTAL)
        self.preview_anim_cb = wx.CheckBox(self, label="预览窗演示摆动")
        self.preview_anim_cb.SetValue(True)
        self.preview_anim_cb.SetToolTip(
            "在本窗用合成角演示绕射线根摆动；近根/钉住区应几乎不动。不影响真实弹簧状态。")
        anim_row.Add(self.preview_anim_cb, 0, wx.ALIGN_CENTER_VERTICAL)
        root.Add(anim_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        self.preview_scroll = wx.ScrolledWindow(self, style=wx.HSCROLL | wx.VSCROLL)
        self.preview_scroll.SetScrollRate(16, 16)
        self.preview_scroll.SetMinSize((-1, PREVIEW_MIN_H))
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        self.preview_scroll.SetSizer(scroll_sizer)
        self.preview_bitmap = wx.StaticBitmap(self.preview_scroll, bitmap=wx.Bitmap(8, 8))
        scroll_sizer.Add(self.preview_bitmap, 0, wx.ALL, 2)
        root.Add(self.preview_scroll, 1, wx.EXPAND | wx.ALL, 4)

        self.preview_bitmap.Bind(wx.EVT_LEFT_DOWN, self._on_preview_down)
        self.preview_bitmap.Bind(wx.EVT_LEFT_UP, self._on_preview_up)
        self.preview_bitmap.Bind(wx.EVT_MOTION, self._on_preview_motion)

        self.enabled_cb.Bind(wx.EVT_CHECKBOX, self._on_settings)
        self.idle_cb.Bind(wx.EVT_CHECKBOX, self._on_settings)
        self.pose_hook_cb.Bind(wx.EVT_CHECKBOX, self._on_settings)
        self.phase_stagger_cb.Bind(wx.EVT_CHECKBOX, self._on_settings)
        self.strength_spin.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_settings)
        self.speed_spin.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_settings)
        self.mode_paint_btn.Bind(
            wx.EVT_TOGGLEBUTTON, lambda e: self._set_edit_mode(MODE_PAINT))
        self.mode_guides_btn.Bind(
            wx.EVT_TOGGLEBUTTON, lambda e: self._set_edit_mode(MODE_AXIS))
        self.tool_brush.Bind(wx.EVT_TOGGLEBUTTON, lambda e: self._set_tool(TOOL_BRUSH))
        self.tool_pin.Bind(wx.EVT_TOGGLEBUTTON, lambda e: self._set_tool(TOOL_PIN))
        self.tool_axis.Bind(wx.EVT_TOGGLEBUTTON, lambda e: self._set_tool(TOOL_AXIS))
        self.erase_cb.Bind(wx.EVT_CHECKBOX, self._on_settings)
        self.radius_spin.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_settings)
        self.opacity_spin.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_settings)
        self.region_choice.Bind(wx.EVT_CHOICE, self._on_region_choice)
        self.island_choice.Bind(wx.EVT_CHOICE, self._on_island_choice)
        self.add_region_btn.Bind(wx.EVT_BUTTON, self._on_add_region)
        self.del_region_btn.Bind(wx.EVT_BUTTON, self._on_remove_region)
        self.clear_btn.Bind(wx.EVT_BUTTON, self._on_clear)
        self.clear_pins_btn.Bind(wx.EVT_BUTTON, self._on_clear_pins)
        self.clear_axis_btn.Bind(wx.EVT_BUTTON, self._on_clear_axis)
        self.refresh_btn.Bind(wx.EVT_BUTTON, lambda e: self.refresh_preview(relayout=True))
        self.preview_anim_cb.Bind(wx.EVT_CHECKBOX, self._on_preview_anim_toggled)

        self._anim_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_anim_timer, self._anim_timer)

        self._load_settings_from_state()
        self._refresh_region_choice()
        self._set_edit_mode(MODE_PAINT, push=False)
        self.refresh_preview(relayout=True)
        self._sync_anim_timer()

    def _target(self) -> str:
        lw = self.layer_window
        if getattr(lw, "_character_selected", False):
            return "character"
        sid = self.main_frame.basic_layers_state.selected_slot_id
        if sid is not None:
            return "layer"
        return "character"

    def _target_heading(self) -> str:
        if self._target() == "layer":
            sid = self.main_frame.basic_layers_state.selected_slot_id
            if sid is None:
                return "图层素材（未选中，编辑立绘）"
            return f"图层 slot={sid}"
        return "立绘源图"

    def _active_state(self):
        mf = self.main_frame
        mf._region_wobble_target = self._target()
        if self._target() == "layer":
            sid = mf.basic_layers_state.selected_slot_id
            if sid is None:
                return None
            return layer_wobble_state(mf, int(sid))
        return mf.character_region_wobble

    def _refresh_region_choice(self) -> None:
        st = self._active_state()
        self._refreshing_regions = True
        try:
            n = len(st.regions) if st is not None else 1
            labels = [f"区域{i + 1}" for i in range(max(1, n))]
            self.region_choice.Set(labels)
            if st is not None:
                idx = st._clamp_active()
                self.region_choice.SetSelection(idx)
            else:
                self.region_choice.SetSelection(0)
            can_del = st is not None and len(st.regions) > 1
            self.del_region_btn.Enable(can_del)
        finally:
            self._refreshing_regions = False

    def _load_settings_from_state(self) -> None:
        st = self._active_state()
        if st is None:
            return
        self.enabled_cb.SetValue(bool(st.enabled))
        self.idle_cb.SetValue(normalize_idle_wobble(st.idle_mode))
        self.pose_hook_cb.SetValue(bool(getattr(st, "pose_hooks_islands", True)))
        self.phase_stagger_cb.SetValue(bool(getattr(st, "island_phase_stagger", False)))
        self._refreshing_islands = True
        try:
            self.island_choice.SetSelection(st._clamp_active_island())
        finally:
            self._refreshing_islands = False
        isl = st.active_island_params()
        self.strength_spin.SetValue(float(isl.strength))
        self.speed_spin.SetValue(float(isl.speed))

    def _push_settings(self) -> None:
        st = self._active_state()
        if st is None:
            return
        st.enabled = bool(self.enabled_cb.GetValue())
        st.idle_mode = (
            IDLE_MODE_STILL_WOBBLE if self.idle_cb.GetValue() else IDLE_MODE_STILL_FROZEN)
        st.pose_hooks_islands = bool(self.pose_hook_cb.GetValue())
        st.island_phase_stagger = bool(self.phase_stagger_cb.GetValue())
        st.active_region = int(self.region_choice.GetSelection())
        st._clamp_active()
        st.active_island = int(self.island_choice.GetSelection())
        st._clamp_active_island()
        isl = st.active_island_params()
        isl.strength = float(self.strength_spin.GetValue())
        isl.speed = float(self.speed_spin.GetValue())
        st.strength = isl.strength
        st.speed = isl.speed
        st.debug_enabled = False
        mf = self.main_frame
        mf._region_wobble_erase = bool(self.erase_cb.GetValue())
        mf._region_wobble_brush_radius = float(self.radius_spin.GetValue())
        mf._region_wobble_brush_strength = float(self.opacity_spin.GetValue())
        mf._region_wobble_paint_mode = self._edit_mode == MODE_PAINT
        if self._target() == "layer":
            sid = mf.basic_layers_state.selected_slot_id
            if sid is not None:
                sync_layer_slot_from_state(mf.basic_layers_state.get_slot(int(sid)), st)
        mf.save_persistent_ui_state()
        mf.notify_layer_composite_dirty(immediate_capture=True)

    def _on_island_choice(self, event: wx.Event) -> None:
        if self._refreshing_islands:
            event.Skip()
            return
        st = self._active_state()
        if st is not None:
            # Persist current spin values into previous island before switching.
            prev = st.active_island_params()
            prev.strength = float(self.strength_spin.GetValue())
            prev.speed = float(self.speed_spin.GetValue())
            st.active_island = int(self.island_choice.GetSelection())
            st._clamp_active_island()
            cur = st.active_island_params()
            self.strength_spin.SetValue(float(cur.strength))
            self.speed_spin.SetValue(float(cur.speed))
            self._push_settings()
        self.refresh_preview(relayout=False)
        event.Skip()

    def _on_settings(self, event: wx.Event) -> None:
        self._push_settings()
        self.refresh_preview()
        event.Skip()

    def _on_region_choice(self, event: wx.Event) -> None:
        if self._refreshing_regions:
            event.Skip()
            return
        st = self._active_state()
        if st is not None:
            st.active_region = int(self.region_choice.GetSelection())
            st._clamp_active()
            # Reload island spins for the new region's bank.
            isl = st.active_island_params()
            self.strength_spin.SetValue(float(isl.strength))
            self.speed_spin.SetValue(float(isl.speed))
            self._push_settings()
        self._status_msg = ""
        self.refresh_preview()
        event.Skip()

    def _on_add_region(self, event: wx.Event) -> None:
        st = self._active_state()
        if st is None:
            event.Skip()
            return
        st.add_region()
        self._refresh_region_choice()
        self._push_settings()
        persist_masks(self.main_frame)
        self._status_msg = f"已新建区域{st.active_region + 1}"
        self.refresh_preview(relayout=True)
        event.Skip()

    def _on_remove_region(self, event: wx.Event) -> None:
        st = self._active_state()
        if st is None:
            event.Skip()
            return
        st.remove_active_region()
        self._refresh_region_choice()
        persist_masks(self.main_frame)
        self._push_settings()
        self._status_msg = "已删除当前区域"
        self.refresh_preview(relayout=True)
        event.Skip()

    def _set_edit_mode(self, mode: str, *, push: bool = True) -> None:
        if mode not in (MODE_PAINT, MODE_AXIS):
            mode = MODE_PAINT
        self._edit_mode = mode
        self.mode_paint_btn.SetValue(mode == MODE_PAINT)
        self.mode_guides_btn.SetValue(mode == MODE_AXIS)
        self._axis_draft_start = None
        self._axis_draft_end = None
        self._axis_dragging = False
        self._painting = False
        if mode == MODE_PAINT:
            self._set_tool(TOOL_BRUSH, push=False)
        else:
            self._set_tool(TOOL_AXIS, push=False)
        self._sync_mode_tool_ui()
        if push:
            self._push_settings()
        self.refresh_preview()

    def _sync_mode_tool_ui(self) -> None:
        paint_mode = self._edit_mode == MODE_PAINT
        self.tool_brush.Show(paint_mode)
        self.tool_pin.Show(not paint_mode)
        self.tool_axis.Show(not paint_mode)
        self.erase_cb.SetLabel("橡皮" if paint_mode else "删钉")
        self.radius_label.Show(paint_mode)
        self.radius_spin.Show(paint_mode)
        self.opacity_label.Show(paint_mode)
        self.opacity_spin.Show(paint_mode)
        self.clear_pins_btn.Enable(not paint_mode)
        self.clear_axis_btn.Enable(not paint_mode)
        self.tool_row.Layout()
        self.brush_row.Layout()
        self.Layout()

    def _set_tool(self, tool: str, *, push: bool = True) -> None:
        if self._edit_mode == MODE_PAINT:
            tool = TOOL_BRUSH
        elif tool == TOOL_BRUSH:
            tool = TOOL_AXIS
        self._tool = tool
        self.tool_brush.SetValue(tool == TOOL_BRUSH)
        self.tool_pin.SetValue(tool == TOOL_PIN)
        self.tool_axis.SetValue(tool == TOOL_AXIS)
        self._axis_draft_start = None
        self._axis_draft_end = None
        self._axis_dragging = False
        self._painting = False
        if push:
            self._push_settings()
        self.refresh_preview()

    def _on_clear(self, event: wx.Event) -> None:
        st = self._active_state()
        if st is not None:
            st.clear_mask()
            st.active_part().reset_spring()
            persist_masks(self.main_frame)
            self.main_frame.notify_layer_composite_dirty(immediate_capture=True)
        self._status_msg = "已清除当前区域掩膜"
        self.refresh_preview()
        event.Skip()

    def _on_clear_pins(self, event: wx.Event) -> None:
        st = self._active_state()
        if st is not None:
            st.clear_pins()
            self._push_settings()
        self._status_msg = "已清除当前区域内的点钉"
        self.refresh_preview()
        event.Skip()

    def _on_clear_axis(self, event: wx.Event) -> None:
        st = self._active_state()
        if st is not None:
            st.clear_axis()
            self._push_settings()
        self._status_msg = "已清除穿过当前区域的射线"
        self.refresh_preview()
        event.Skip()

    def _on_preview_anim_toggled(self, event: wx.Event) -> None:
        self._preview_anim = bool(self.preview_anim_cb.GetValue())
        self._sync_anim_timer()
        self.refresh_preview()
        event.Skip()

    def _sync_anim_timer(self) -> None:
        top = self.GetTopLevelParent()
        shown = True
        try:
            shown = bool(top.IsShown()) if top is not None else True
        except Exception:
            shown = True
        want = bool(self.preview_anim_cb.GetValue()) and shown
        st = self._active_state()
        want = want and st is not None and st.has_active_mask()
        if want:
            if not self._anim_timer.IsRunning():
                self._anim_timer.Start(PREVIEW_ANIM_MS)
        elif self._anim_timer.IsRunning():
            self._anim_timer.Stop()

    def _on_anim_timer(self, event: wx.Event) -> None:
        if self._painting or self._axis_dragging:
            return
        if not self.preview_anim_cb.GetValue():
            return
        self.refresh_preview(relayout=False)

    def _update_guide_status(self, st) -> None:
        if st is None:
            self.guide_status.SetLabel("射线: — · 点钉: —")
            return
        idx = st._clamp_active()
        mask = st.mask
        if mask is not None and numpy.any(mask > W_EPS):
            axis = pick_axis_for_mask(st.axes, mask)
            if axis is not None:
                x0, y0, x1, y1 = axis
                axis_txt = (
                    f"区域{idx + 1} 射线: 根({x0:.0f},{y0:.0f})→尖({x1:.0f},{y1:.0f})")
            else:
                axis_txt = f"区域{idx + 1} 射线: 未设置（自动）"
            pin_n = len(pins_for_mask(st.pins, mask))
        else:
            axis_txt = f"区域{idx + 1} 射线: 未涂选"
            pin_n = 0
        pin_txt = f"区内点钉: {pin_n}"
        extra = f" · {self._status_msg}" if self._status_msg else ""
        self.guide_status.SetLabel(f"{axis_txt} · {pin_txt}{extra}")

    def _event_image_xy(self, event: wx.MouseEvent) -> tuple[float, float]:
        """Map mouse event to preview-image pixel coordinates."""
        x, y = event.GetPosition()
        obj = event.GetEventObject()
        if obj is self.preview_scroll:
            ux, uy = self.preview_scroll.CalcUnscrolledPosition(int(x), int(y))
            return float(ux - 2), float(uy - 2)
        if obj is self.preview_bitmap:
            return float(x), float(y)
        try:
            sx, sy = event.GetEventObject().ClientToScreen((int(x), int(y)))
            bx, by = self.preview_bitmap.ScreenToClient((sx, sy))
            return float(bx), float(by)
        except Exception:
            return float(x), float(y)

    def _capture_for_drag(self) -> None:
        win = self.preview_bitmap
        if not win.HasCapture():
            try:
                win.CaptureMouse()
            except Exception:
                pass

    def _release_capture(self) -> None:
        win = self.preview_bitmap
        if win.HasCapture():
            try:
                win.ReleaseMouse()
            except Exception:
                pass

    def _remove_nearest_pin_in_active(self, st, x: float, y: float, max_dist: float = 24.0) -> bool:
        mask = st.mask
        best_i = -1
        best_d = float(max_dist)
        for i, (px, py) in enumerate(st.pins):
            if mask is not None and numpy.any(mask > W_EPS):
                if not pin_inside_mask((px, py), mask):
                    continue
            d = math.hypot(px - x, py - y)
            if d <= best_d:
                best_d = d
                best_i = i
        if best_i < 0:
            return False
        st.pins.pop(best_i)
        return True

    def refresh_preview(self, relayout: bool = True) -> None:
        target = self._target()
        rgba = still_preview_rgba(self.main_frame, target)
        self._base_rgba = rgba
        detail = still_preview_source_label(self.main_frame, target)
        self.source_label.SetLabel(f"目标: {self._target_heading()} · {detail}")
        st = self._active_state()
        self._update_guide_status(st)
        if rgba is None:
            empty = wx.Bitmap(8, 8)
            self.preview_bitmap.SetBitmap(empty)
            if relayout:
                self.preview_bitmap.SetMinSize((8, 8))
                self.preview_bitmap.SetMaxSize((8, 8))
                self.preview_bitmap.SetSize((8, 8))
                self.preview_scroll.SetVirtualSize((8, 8))
                self.preview_scroll.FitInside()
            self._sync_anim_timer()
            return
        show = rgba
        if st is not None:
            h0, w0 = int(rgba.shape[0]), int(rgba.shape[1])
            st.ensure_mask_shape(h0, w0)
            active_idx = st._clamp_active()
            active_mask = st.mask
            auto_axis = None
            if (
                    active_mask is not None
                    and numpy.any(active_mask > W_EPS)
                    and self.preview_anim_cb.GetValue()
                    and not self._painting
                    and not self._axis_dragging):
                warped = rgba
                preview_buf = None
                auto_axis = None
                part = st.active_part()
                part.ensure_island_bank()
                comps = part.get_components()
                for isl_i, comp in enumerate(comps):
                    params = part.islands[isl_i]
                    ang = preview_angle_deg(
                        st, strength=params.strength, speed=params.speed,
                        island_index=isl_i, island_count=len(comps))
                    axis_for_warp = pick_axis_for_island(st.axes, comp)
                    if axis_for_warp is None:
                        continue
                    if auto_axis is None and not any(
                            axis_passes_through_island(a, comp) for a in st.axes):
                        auto_axis = axis_for_warp
                    local_pins = pins_for_island(st.pins, comp)
                    if preview_buf is None:
                        preview_buf = numpy.array(warped, copy=True, dtype=numpy.uint8)
                    warped, _blend = warp_hinge_island(
                        warped,
                        comp,
                        pins=local_pins,
                        axis=axis_for_warp,
                        angle_deg=ang,
                        pin_radius=DEFAULT_PIN_RADIUS,
                        out=preview_buf)
                show = warped
            show = composite_on_checkerboard(show)
            for i, reg in enumerate(st.regions):
                m = reg.mask
                if m is None or not numpy.any(m > W_EPS):
                    continue
                is_active = i == active_idx
                show = overlay_mask_preview_rgba(
                    show, m, alpha=0.62 if is_active else 0.34)
            # Island numbers on the active涂选区域.
            active_comps = (
                st.active_part().get_components()
                if st.active_part().mask is not None else [])
            if active_comps:
                show = overlay_island_labels_rgba(
                    show,
                    active_comps,
                    active_index=st._clamp_active_island(),
                    alpha=0.62)
            if self._edit_mode == MODE_AXIS:
                mask = active_mask
                scoped_pins = (
                    pins_for_mask(st.pins, mask)
                    if mask is not None and numpy.any(mask > W_EPS)
                    else [])
                scoped_axes = (
                    axes_for_mask(st.axes, mask)
                    if mask is not None and numpy.any(mask > W_EPS)
                    else [])
                picked = (
                    pick_axis_for_mask(st.axes, mask)
                    if mask is not None and numpy.any(mask > W_EPS)
                    else None)
                guide_auto = None
                if picked is None and mask is not None and numpy.any(mask > W_EPS):
                    guide_auto = _auto_axis_from_mask(mask)
                draft = None
                if self._axis_draft_start is not None and self._axis_draft_end is not None:
                    x0, y0 = self._axis_draft_start
                    x1, y1 = self._axis_draft_end
                    draft = (x0, y0, x1, y1)
                show = overlay_guides_rgba(
                    show,
                    scoped_pins,
                    axis=picked,
                    axes=scoped_axes or None,
                    draft_axis=draft,
                    pin_radius=DEFAULT_PIN_RADIUS,
                    show_pin_influence=True,
                    auto_axis=guide_auto)
        else:
            show = composite_on_checkerboard(show)
        h, w = int(show.shape[0]), int(show.shape[1])
        self._zoom = DEFAULT_ZOOM
        bmp = _rgba_to_bitmap(show)
        self.preview_bitmap.SetBitmap(bmp)
        if relayout:
            disp_w = max(1, int(w))
            disp_h = max(1, int(h))
            self.preview_bitmap.SetMinSize((disp_w, disp_h))
            self.preview_bitmap.SetMaxSize((disp_w, disp_h))
            self.preview_bitmap.SetSize((disp_w, disp_h))
            self.preview_scroll.SetVirtualSize((disp_w, disp_h))
            self.preview_scroll.FitInside()
            self.preview_scroll.Layout()
            self.Layout()
        self._sync_anim_timer()

    def _paint_at(self, client_x: float, client_y: float) -> None:
        if self._base_rgba is None or self._edit_mode != MODE_PAINT:
            return
        st = self._active_state()
        if st is None:
            return
        h, w = int(self._base_rgba.shape[0]), int(self._base_rgba.shape[1])
        st.ensure_mask_shape(h, w)
        paint_brush(
            st,
            float(client_x),
            float(client_y),
            radius=float(self.radius_spin.GetValue()),
            strength=float(self.opacity_spin.GetValue()),
            erase=bool(self.erase_cb.GetValue()))
        st.enabled = True
        self.enabled_cb.SetValue(True)
        if self._target() == "layer":
            sid = self.main_frame.basic_layers_state.selected_slot_id
            if sid is not None:
                layer = self.main_frame.basic_layers_state.get_slot(int(sid))
                sync_layer_slot_from_state(layer, st)
                layer.region_wobble_enabled = True
        self.refresh_preview(relayout=False)

    def _on_preview_down(self, event: wx.MouseEvent) -> None:
        st = self._active_state()
        x, y = self._event_image_xy(event)
        if self._edit_mode == MODE_PAINT:
            if st is None:
                event.Skip()
                return
            self._painting = True
            self._capture_for_drag()
            self._paint_at(x, y)
        elif self._tool == TOOL_PIN:
            if st is None:
                event.Skip()
                return
            if self._base_rgba is not None:
                st.ensure_mask_shape(
                    int(self._base_rgba.shape[0]), int(self._base_rgba.shape[1]))
            if self.erase_cb.GetValue():
                removed = self._remove_nearest_pin_in_active(st, x, y)
                self._status_msg = "已删除点钉" if removed else "附近无区内点钉"
            else:
                st.add_pin(x, y)
                self._status_msg = f"已钉住 ({x:.0f},{y:.0f}) — 红圈内应冻结"
            st.enabled = True
            self.enabled_cb.SetValue(True)
            self._push_settings()
            self.refresh_preview(relayout=False)
        elif self._tool == TOOL_AXIS:
            self._axis_dragging = True
            self._axis_draft_start = (x, y)
            self._axis_draft_end = (x, y)
            self._status_msg = "拖拽拉出中轴…"
            self._capture_for_drag()
            self.refresh_preview(relayout=False)

    def _commit_axis_draft(self) -> None:
        if self._axis_draft_start is None:
            return
        st = self._active_state()
        x0, y0 = self._axis_draft_start
        x1, y1 = self._axis_draft_end or self._axis_draft_start
        self._axis_draft_start = None
        self._axis_draft_end = None
        self._axis_dragging = False
        self._release_capture()
        if st is None:
            return
        if self._base_rgba is not None:
            st.ensure_mask_shape(
                int(self._base_rgba.shape[0]), int(self._base_rgba.shape[1]))
        ok = st.set_axis(x0, y0, x1, y1)
        if ok:
            st.enabled = True
            self.enabled_cb.SetValue(True)
            self._status_msg = (
                f"射线已生效 根({x0:.0f},{y0:.0f})→尖({x1:.0f},{y1:.0f})")
            self._push_settings()
        else:
            self._status_msg = (
                f"射线太短（需≥{AXIS_MIN_DRAG_PX:.0f}px），未保存 — 请从根拖向尖端")
        self.refresh_preview(relayout=False)

    def _on_preview_up(self, event: wx.MouseEvent) -> None:
        if self._painting:
            self._painting = False
            self._release_capture()
            persist_masks(self.main_frame)
            self._push_settings()
            self._sync_anim_timer()
        if self._axis_dragging or (
                self._tool == TOOL_AXIS and self._axis_draft_start is not None):
            try:
                self._axis_draft_end = self._event_image_xy(event)
            except Exception:
                pass
            self._commit_axis_draft()

    def _on_preview_motion(self, event: wx.MouseEvent) -> None:
        x, y = self._event_image_xy(event)
        if self._painting and self._edit_mode == MODE_PAINT and (
                event.Dragging() or event.LeftIsDown()):
            self._paint_at(x, y)
        elif (
                self._axis_dragging
                and self._axis_draft_start is not None
                and (event.Dragging() or event.LeftIsDown())):
            self._axis_draft_end = (x, y)
            self.refresh_preview(relayout=False)

    def on_layer_selection_changed(self) -> None:
        self._load_settings_from_state()
        self._refresh_region_choice()
        self.refresh_preview(relayout=True)


class RegionWobbleFrame(wx.Frame):
    """Independent tool window opened from layer detail「简易区域晃动」."""

    def __init__(self, layer_window) -> None:
        # Parent = main frame so the tool closes with the app (not an orphan).
        super().__init__(
            layer_window.main_frame,
            wx.ID_ANY,
            title="简易区域晃动 / Region wobble",
            style=wx.DEFAULT_FRAME_STYLE)
        self.layer_window = layer_window
        self.main_frame = layer_window.main_frame
        try:
            from character_model_mediapipe_puppeteer_load_preview import apply_app_icon
            apply_app_icon(self)
        except Exception:
            pass

        root = wx.BoxSizer(wx.VERTICAL)
        self.panel = RegionWobbleLayerPanel(self, layer_window)
        root.Add(self.panel, 1, wx.EXPAND)
        self.SetSizer(root)
        self.SetMinSize(FRAME_MIN_SIZE)
        self.SetSize(FRAME_MIN_SIZE)
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_ACTIVATE, self._on_activate)

    def _on_activate(self, event: wx.Event) -> None:
        try:
            self.main_frame.on_window_activate_for_layer_selection(event, self)
        except Exception:
            pass
        event.Skip()

    def on_close(self, event: wx.Event) -> None:
        if self.panel._anim_timer.IsRunning():
            self.panel._anim_timer.Stop()
        try:
            persist_masks(self.main_frame)
        except Exception:
            pass
        # Real destroy when main is quitting; otherwise hide for reuse.
        if getattr(self.main_frame, "_is_closing", False) or not event.CanVeto():
            try:
                if getattr(self.layer_window, "region_wobble_frame", None) is self:
                    self.layer_window.region_wobble_frame = None
            except Exception:
                pass
            event.Skip()
            return
        event.Veto()
        self.Hide()

    def show_and_raise(self) -> None:
        if not self.IsShown():
            try:
                owner = self.layer_window
                if owner is not None and owner.IsShown():
                    ox, oy = owner.GetPosition()
                    ow, _oh = owner.GetSize()
                    self.SetPosition((ox + max(40, ow // 5), oy + 60))
            except Exception:
                pass
        self.Show()
        self.Raise()
        self.panel._load_settings_from_state()
        self.panel._refresh_region_choice()
        self.panel._zoom = DEFAULT_ZOOM
        self.panel.refresh_preview(relayout=True)
        self.panel._sync_anim_timer()
        self.Layout()
