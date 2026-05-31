"""Independent basic five-layer editor window (WeChat-style list, six static previews)."""
from __future__ import annotations

import os
from typing import Callable, Optional, TYPE_CHECKING

import wx

from layer_runtime import (
    BINDING_CHARACTER_BODY,
    BINDING_CHARACTER_HEAD,
    BINDING_SMOOTH_ALPHA,
    BIND_RAY_PERCENT_DEFAULT,
    BIND_RAY_PERCENT_UI_MAX,
    BIND_RAY_PERCENT_UI_MIN,
    CHARACTER_STACK_POS,
    HEAD_ANCHOR_RATIO,
    NECK_ANCHOR_RATIO_DEFAULT,
    BasicLayerSlot,
    BasicLayersState,
    LAYER_ASSET_FILE_WILDCARD,
    LayerAssetCache,
    binding_smooth_alpha_for_layer,
    center_layer_transform,
    clamp_binding_smooth_alpha,
    clamp_neck_anchor_ratio,
    build_spine_diagram_points,
    collect_spine_binding_markers,
    compute_spine_diagram_layout,
    format_layer_row_summary,
    format_layer_row_title,
    iter_ui_list_top_to_bottom,
    map_canvas_point_to_diagram,
    move_layer_z_order,
    normalize_bind_ray_percent,
    normalize_binding_target,
    parse_layer_binding_slot,
    stack_position_can_move_down,
    stack_position_can_move_up,
    truncate_display_filename,
)

if TYPE_CHECKING:
    from character_model_mediapipe_puppeteer_load_preview import MainFrame

THUMB_SIZE = 52
ROW_MIN_HEIGHT = 56
SELECTED_BORDER = wx.Colour(255, 210, 0)
THUMB_HIGHLIGHT = wx.Colour(255, 200, 0)
DETAIL_DOCK_MIN_HEIGHT = 284
PLACEHOLDER_HEIGHT = 72

PLACEHOLDER_TEXT = "点击上方图层行以编辑 / Click a layer row above to edit"

SPINE_DIAGRAM_HEIGHT = 168
DIAGRAM_PAD_LEFT = 52
DIAGRAM_PAD_RIGHT = 52
DIAGRAM_CONTROLS_WIDTH = 148
SEGMENT_BODY_COLOUR = wx.Colour(70, 130, 220)
SEGMENT_HEAD_COLOUR = wx.Colour(230, 140, 50)
SPINE_JOINT_COLOUR = wx.Colour(40, 40, 40)
SPINE_GUIDE_COLOUR = wx.Colour(180, 180, 180)
BODY_BIND_MARKER_COLOUR = wx.Colour(30, 90, 180)
HEAD_BIND_MARKER_COLOUR = wx.Colour(210, 100, 20)
LAYER_MARKER_SELECTED = wx.Colour(255, 210, 0)


class SpineRayReferencePanel(wx.Panel):
    """Schematic of two-segment spine ray with controls on the right."""

    def __init__(self, parent: wx.Window, main_frame: "MainFrame"):
        super().__init__(parent, style=wx.BORDER_THEME)
        self.main_frame = main_frame
        self._neck_ratio = NECK_ANCHOR_RATIO_DEFAULT
        self._body_bind_percent = BIND_RAY_PERCENT_DEFAULT
        self._head_bind_percent = BIND_RAY_PERCENT_DEFAULT
        self._binding_markers: list = []
        self._spine_points: dict[str, tuple[float, float]] = {}
        self._live_tilt_deg = 0.0
        root = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(root)

        title = wx.StaticText(
            self,
            label="射线映射 / Spine ray map")
        title_font = title.GetFont()
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        root.Add(title, 0, wx.ALL, 6)

        body_row = wx.BoxSizer(wx.HORIZONTAL)

        self.diagram = wx.Panel(self, size=(-1, SPINE_DIAGRAM_HEIGHT))
        self.diagram.SetMinSize((220, SPINE_DIAGRAM_HEIGHT))
        self.diagram.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.diagram.Bind(wx.EVT_PAINT, self._on_diagram_paint)
        body_row.Add(self.diagram, 1, wx.EXPAND | wx.RIGHT, 6)

        self.controls_panel = wx.Panel(self)
        controls_outer = wx.BoxSizer(wx.HORIZONTAL)
        self.controls_panel.SetSizer(controls_outer)
        min_pct = 0
        max_pct = 100
        default_pct = int(round(NECK_ANCHOR_RATIO_DEFAULT * 100))

        neck_col = wx.BoxSizer(wx.VERTICAL)
        neck_col.Add(
            wx.StaticText(self.controls_panel, label="底→脖\nBottom→Neck"),
            0,
            wx.ALIGN_CENTER_HORIZONTAL)
        self.neck_ratio_slider = wx.Slider(
            self.controls_panel,
            value=default_pct,
            minValue=min_pct,
            maxValue=max_pct,
            style=wx.SL_VERTICAL | wx.SL_INVERSE)
        self.neck_ratio_slider.SetMinSize((28, SPINE_DIAGRAM_HEIGHT - 24))
        self.neck_ratio_slider.SetToolTip(
            "底→脖参考分段比例（0%=底，100%=头，仅示意；不移动已绑图层）/ "
            "Reference bottom-to-neck split (0%=bottom, 100%=head; layers unchanged)")
        neck_col.Add(self.neck_ratio_slider, 1, wx.EXPAND)
        self.neck_ratio_label = wx.StaticText(self.controls_panel, label=f"{default_pct}%")
        neck_col.Add(self.neck_ratio_label, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 2)
        controls_outer.Add(neck_col, 0, wx.EXPAND | wx.RIGHT, 8)

        bind_col = wx.BoxSizer(wx.VERTICAL)
        bind_default = int(round(BIND_RAY_PERCENT_DEFAULT))

        body_bind_row = wx.BoxSizer(wx.HORIZONTAL)
        body_bind_row.Add(
            wx.StaticText(self.controls_panel, label="身绑①"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            4)
        self.body_bind_spin = wx.SpinCtrl(
            self.controls_panel,
            value=str(bind_default),
            min=BIND_RAY_PERCENT_UI_MIN,
            max=BIND_RAY_PERCENT_UI_MAX,
            initial=bind_default)
        self.body_bind_spin.SetToolTip(
            "参考绑定点在①段射线上的 %（可超出 0–100，不移动已绑图层）/ "
            "Reference body bind % on ray 1 (unbounded; layers unchanged)")
        body_bind_row.Add(self.body_bind_spin, 1, wx.EXPAND)
        body_bind_row.Add(
            wx.StaticText(self.controls_panel, label="%"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            2)
        bind_col.Add(body_bind_row, 0, wx.EXPAND | wx.BOTTOM, 8)

        head_bind_row = wx.BoxSizer(wx.HORIZONTAL)
        head_bind_row.Add(
            wx.StaticText(self.controls_panel, label="头绑②"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            4)
        self.head_bind_spin = wx.SpinCtrl(
            self.controls_panel,
            value=str(bind_default),
            min=BIND_RAY_PERCENT_UI_MIN,
            max=BIND_RAY_PERCENT_UI_MAX,
            initial=bind_default)
        self.head_bind_spin.SetToolTip(
            "参考绑定点在②段射线上的 %（可超出 0–100，不移动已绑图层）/ "
            "Reference head bind % on ray 2 (unbounded; layers unchanged)")
        head_bind_row.Add(self.head_bind_spin, 1, wx.EXPAND)
        head_bind_row.Add(
            wx.StaticText(self.controls_panel, label="%"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.LEFT,
            2)
        bind_col.Add(head_bind_row, 0, wx.EXPAND)
        controls_outer.Add(bind_col, 1, wx.EXPAND)

        body_row.Add(self.controls_panel, 0, wx.EXPAND)
        root.Add(body_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)

        self.ratio_caption = wx.StaticText(self, label="")
        self.ratio_caption.SetForegroundColour(wx.Colour(90, 90, 90))
        self.ratio_caption.Wrap(440)
        root.Add(self.ratio_caption, 0, wx.ALL, 6)

        self.neck_ratio_slider.Bind(wx.EVT_SLIDER, self._on_neck_ratio_changed)
        self.body_bind_spin.Bind(wx.EVT_SPINCTRL, self._on_body_bind_changed)
        self.head_bind_spin.Bind(wx.EVT_SPINCTRL, self._on_head_bind_changed)
        self.sync_from_main_frame()

    def _rebuild_live_snapshot(self) -> None:
        canvas_size = 512
        ctx = self.main_frame._make_binding_context(canvas_size, canvas_size)
        self._spine_points = build_spine_diagram_points(ctx)
        self._live_tilt_deg = ctx.spine_upper_angle_deg()
        self._binding_markers = collect_spine_binding_markers(
            self.main_frame.basic_layers_state,
            ctx,
            self.main_frame.layer_asset_cache.load_image)

    def refresh_diagram_live(self) -> None:
        """Update diagram from current output binding pose (tilt / mocap)."""
        self._rebuild_live_snapshot()
        self.diagram.Refresh(False)

    def sync_from_main_frame(self) -> None:
        ratio = clamp_neck_anchor_ratio(self.main_frame.get_spine_neck_anchor_ratio())
        body_pct = normalize_bind_ray_percent(self.main_frame.get_spine_body_bind_ray_percent())
        head_pct = normalize_bind_ray_percent(self.main_frame.get_spine_head_bind_ray_percent())
        pct = int(round(ratio * 100))
        self._neck_ratio = ratio
        self._body_bind_percent = body_pct
        self._head_bind_percent = head_pct
        self.neck_ratio_slider.SetValue(pct)
        self.neck_ratio_label.SetLabel(f"{pct}%")
        self.body_bind_spin.SetValue(int(round(body_pct)))
        self.head_bind_spin.SetValue(int(round(head_pct)))
        upper_pct = int(round((HEAD_ANCHOR_RATIO - ratio) * 100))
        self._rebuild_live_snapshot()
        body_layers = sum(1 for m in self._binding_markers if m.marker_kind == "body_layer")
        head_layers = sum(1 for m in self._binding_markers if m.marker_kind == "head_layer")
        tilt_text = f" · 倾斜 {self._live_tilt_deg:.1f}°" if abs(self._live_tilt_deg) > 0.05 else ""
        self.ratio_caption.SetLabel(
            f"①段 {pct}% · 参考身绑 {int(round(body_pct))}% · 已绑 {body_layers} 层"
            f"  |  ②段 {upper_pct}% · 参考头绑 {int(round(head_pct))}% · 已绑 {head_layers} 层"
            f"  |  头中心 {int(round(HEAD_ANCHOR_RATIO * 100))}%{tilt_text}"
            f"  |  参考分段/绑点调整不移动图层 · 射线示意")
        self.diagram.Refresh(False)

    def _diagram_geometry(self, width: int, height: int) -> dict:
        if not self._spine_points:
            self._rebuild_live_snapshot()
        layout, mapped = compute_spine_diagram_layout(
            self._spine_points,
            width,
            height,
            pad_left=DIAGRAM_PAD_LEFT,
            pad_right=DIAGRAM_PAD_RIGHT)
        bottom = mapped["bottom"]
        neck = mapped["neck"]
        head = mapped["head"]
        return {
            "layout": layout,
            "bottom": bottom,
            "neck": neck,
            "head": head,
            "body_bind": mapped["body_bind"],
            "head_bind": mapped["head_bind"],
            "lower_ray_start": mapped.get("lower_ray_start", bottom),
            "lower_ray_end": mapped.get("lower_ray_end", neck),
            "upper_ray_start": mapped.get("upper_ray_start", neck),
            "upper_ray_end": mapped.get("upper_ray_end", head),
            "left_x": layout.left_x,
        }

    def _marker_diagram_point(self, geom: dict, marker) -> tuple[int, int]:
        if marker.canvas_x is not None and marker.canvas_y is not None:
            layout = geom["layout"]
            return map_canvas_point_to_diagram(layout, marker.canvas_x, marker.canvas_y)
        bottom_x, bottom_y = geom["bottom"]
        neck_x, neck_y = geom["neck"]
        head_x, head_y = geom["head"]
        if marker.marker_kind == "body_anchor":
            return geom["body_bind"]
        if marker.marker_kind == "head_anchor":
            return geom["head_bind"]
        if marker.segment == 1:
            px = bottom_x + (neck_x - bottom_x) * marker.t
            py = bottom_y + (neck_y - bottom_y) * marker.t
            return int(round(px)), int(round(py))
        px = neck_x + (head_x - neck_x) * marker.t
        py = neck_y + (head_y - neck_y) * marker.t
        return int(round(px)), int(round(py))

    def _draw_binding_markers(self, dc: wx.DC, geom: dict, label_font: wx.Font) -> None:
        dc.SetFont(label_font)
        placed_labels: list[tuple[int, int, int, int]] = []

        def _label_fits(x: int, y: int, text: str) -> bool:
            tw, th = dc.GetTextExtent(text)
            rect = (x, y, x + tw, y + th)
            for ox, oy, ow, oh in placed_labels:
                if not (rect[2] < ox or rect[0] > ox + ow or rect[3] < oy or rect[1] > oy + oh):
                    return False
            placed_labels.append((x, y, tw, th))
            return True

        def _draw_label(text: str, px: int, py: int, colour: wx.Colour, *, prefer_left: bool) -> None:
            dc.SetTextForeground(colour)
            for dx, dy in (
                (-46 if prefer_left else 10, -8),
                (-46 if prefer_left else 10, 6),
                (10 if prefer_left else -46, -8),
                (10 if prefer_left else -46, 6),
            ):
                lx, ly = px + dx, py + dy
                if lx >= geom["left_x"] and _label_fits(lx, ly, text):
                    dc.DrawText(text, lx, ly)
                    return

        for marker in self._binding_markers:
            px, py = self._marker_diagram_point(geom, marker)
            if marker.marker_kind == "body_anchor":
                size = 10
                dc.SetPen(wx.Pen(BODY_BIND_MARKER_COLOUR, 2))
                dc.SetBrush(wx.Brush(wx.Colour(240, 248, 255)))
                dc.DrawRectangle(px - size // 2, py - size // 2, size, size)
                _draw_label("身绑", px, py, BODY_BIND_MARKER_COLOUR, prefer_left=False)
                continue
            if marker.marker_kind == "head_anchor":
                dc.SetPen(wx.Pen(HEAD_BIND_MARKER_COLOUR, 2))
                dc.SetBrush(wx.Brush(wx.Colour(255, 248, 240)))
                points = [
                    wx.Point(px, py - 7),
                    wx.Point(px + 7, py),
                    wx.Point(px, py + 7),
                    wx.Point(px - 7, py),
                ]
                dc.DrawPolygon(points)
                _draw_label("头绑", px, py, HEAD_BIND_MARKER_COLOUR, prefer_left=False)
                continue
            colour = (
                BODY_BIND_MARKER_COLOUR
                if marker.marker_kind == "body_layer"
                else HEAD_BIND_MARKER_COLOUR)
            radius = 7 if marker.selected else 5
            if marker.selected:
                dc.SetPen(wx.Pen(LAYER_MARKER_SELECTED, 2))
                dc.SetBrush(wx.Brush(colour))
                dc.DrawCircle(px, py, radius + 2)
            dc.SetPen(wx.Pen(wx.Colour(255, 255, 255), 1))
            dc.SetBrush(wx.Brush(colour))
            dc.DrawCircle(px, py, radius)
            prefer_left = marker.segment == 1
            slot_label = f"L{(marker.slot_id or 0) + 1}"
            _draw_label(slot_label, px, py, colour, prefer_left=prefer_left)

    def _on_neck_ratio_changed(self, event: wx.Event) -> None:
        pct = self.neck_ratio_slider.GetValue()
        self.main_frame.set_spine_neck_anchor_ratio(clamp_neck_anchor_ratio(pct / 100.0))
        self.sync_from_main_frame()
        event.Skip()

    def _on_body_bind_changed(self, event: wx.Event) -> None:
        self.main_frame.set_spine_body_bind_ray_percent(
            float(self.body_bind_spin.GetValue()))
        self.sync_from_main_frame()
        event.Skip()

    def _on_head_bind_changed(self, event: wx.Event) -> None:
        self.main_frame.set_spine_head_bind_ray_percent(
            float(self.head_bind_spin.GetValue()))
        self.sync_from_main_frame()
        event.Skip()

    def _on_diagram_paint(self, event: wx.Event) -> None:
        dc = wx.AutoBufferedPaintDC(self.diagram)
        width, height = self.diagram.GetClientSize()
        dc.SetBackground(wx.Brush(self.diagram.GetBackgroundColour()))
        dc.Clear()
        if width < 80 or height < 40:
            return

        geom = self._diagram_geometry(width, height)
        bottom_x, bottom_y = geom["bottom"]
        neck_x, neck_y = geom["neck"]
        head_x, head_y = geom["head"]
        left_x = geom["left_x"]

        mapped_pts = [
            geom["bottom"], geom["neck"], geom["head"],
            geom.get("lower_ray_start"), geom.get("lower_ray_end"),
            geom.get("upper_ray_start"), geom.get("upper_ray_end"),
            geom["body_bind"], geom["head_bind"],
        ]
        mapped_pts = [p for p in mapped_pts if p is not None]
        min_mx = min(p[0] for p in mapped_pts) - 10
        max_mx = max(p[0] for p in mapped_pts) + 10
        min_my = min(p[1] for p in mapped_pts) - 6
        max_my = max(p[1] for p in mapped_pts) + 6
        dc.SetPen(wx.Pen(SPINE_GUIDE_COLOUR, 1, wx.PENSTYLE_DOT))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(min_mx, min_my, max(8, max_mx - min_mx), max(8, max_my - min_my))

        lower_start = geom.get("lower_ray_start", geom["bottom"])
        lower_end = geom.get("lower_ray_end", geom["neck"])
        upper_start = geom.get("upper_ray_start", geom["neck"])
        upper_end = geom.get("upper_ray_end", geom["head"])

        dc.SetPen(wx.Pen(SEGMENT_BODY_COLOUR, 2, wx.PENSTYLE_DOT))
        dc.DrawLine(lower_start[0], lower_start[1], lower_end[0], lower_end[1])
        dc.SetPen(wx.Pen(SEGMENT_BODY_COLOUR, 4))
        dc.DrawLine(bottom_x, bottom_y, neck_x, neck_y)
        dc.SetPen(wx.Pen(SEGMENT_HEAD_COLOUR, 2, wx.PENSTYLE_DOT))
        dc.DrawLine(upper_start[0], upper_start[1], upper_end[0], upper_end[1])
        dc.SetPen(wx.Pen(SEGMENT_HEAD_COLOUR, 4))
        dc.DrawLine(neck_x, neck_y, head_x, head_y)

        dc.SetPen(wx.Pen(SPINE_JOINT_COLOUR, 1))
        dc.SetBrush(wx.Brush(SPINE_JOINT_COLOUR))
        for px, py, radius in ((bottom_x, bottom_y, 4), (neck_x, neck_y, 5), (head_x, head_y, 5)):
            dc.DrawCircle(px, py, radius)

        self._draw_binding_markers(dc, geom, self._diagram_label_font())

        label_font = self._diagram_label_font()
        dc.SetFont(label_font)
        label_specs = (
            (SEGMENT_BODY_COLOUR, "①", int((bottom_y + neck_y) / 2) - 5),
            (SEGMENT_HEAD_COLOUR, "②", int((neck_y + head_y) / 2) - 5),
            (SPINE_JOINT_COLOUR, "底", bottom_y - 5),
            (SPINE_JOINT_COLOUR, "脖", neck_y - 5),
            (SPINE_JOINT_COLOUR, "头", head_y - 2),
        )
        for colour, text, label_y in label_specs:
            dc.SetTextForeground(colour)
            dc.DrawText(text, left_x, label_y)
        dc.SetTextForeground(wx.Colour(120, 120, 120))
        bottom_en_y = min(height - 14, bottom_y + 8)
        dc.DrawText("bottom", left_x, bottom_en_y)
        event.Skip()

    @staticmethod
    def _diagram_label_font() -> wx.Font:
        font = wx.Font(wx.FontInfo(8).Family(wx.FONTFAMILY_SWISS))
        return font


class LayerThumbPanel(wx.Panel):
    """Static layer thumbnail with selection highlight matching the output window."""

    def __init__(self, parent: wx.Window, size: int = THUMB_SIZE):
        super().__init__(parent, size=(size, size))
        self._bitmap: Optional[wx.Bitmap] = None
        self._selected = False
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def set_bitmap(self, bitmap: wx.Bitmap) -> None:
        self._bitmap = bitmap
        self.Refresh(False)

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self.Refresh(False)

    def _on_paint(self, event: wx.Event) -> None:
        dc = wx.PaintDC(self)
        width, height = self.GetClientSize()
        if self._bitmap is not None and self._bitmap.IsOk():
            dc.DrawBitmap(self._bitmap, 0, 0, True)
        else:
            dc.SetBackground(wx.Brush(wx.Colour(48, 48, 48)))
            dc.Clear()
        if self._selected:
            pen = wx.Pen(THUMB_HIGHLIGHT, 2)
            dc.SetPen(pen)
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRectangle(1, 1, max(1, width - 2), max(1, height - 2))
            handle = 6
            dc.SetBrush(wx.Brush(THUMB_HIGHLIGHT))
            dc.DrawRectangle(width - handle - 1, height - handle - 1, handle, handle)


def _bind_left_click(window: wx.Window, handler: Callable[[wx.Event], None]) -> None:
    if isinstance(window, (wx.Button, wx.RadioButton, wx.CheckBox, wx.Slider, wx.Choice)):
        return
    window.Bind(wx.EVT_LEFT_DOWN, handler)
    for child in window.GetChildren():
        if isinstance(child, wx.Window):
            _bind_left_click(child, handler)


class LayerRowPanel(wx.Panel):
    """Compact list row (header only); detail edits live in the dock below the list."""

    def __init__(
            self,
            parent: wx.Window,
            *,
            slot_id: Optional[int],
            title: str,
            is_character_row: bool,
            on_header_clicked: Optional[Callable[[], None]] = None):
        super().__init__(parent, style=wx.BORDER_THEME)
        self.slot_id = slot_id
        self.is_character_row = is_character_row
        self._selected = False
        self.SetMinSize((-1, ROW_MIN_HEIGHT))
        self.Bind(wx.EVT_PAINT, self._on_paint)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.SetSizer(sizer)

        self.header = wx.Panel(self)
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.header.SetSizer(header_sizer)

        self.thumb = LayerThumbPanel(self.header, THUMB_SIZE)
        header_sizer.Add(self.thumb, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 4)

        text_col = wx.BoxSizer(wx.VERTICAL)
        self.title_text = wx.StaticText(self.header, label=title)
        font = self.title_text.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.title_text.SetFont(font)
        text_col.Add(self.title_text, 0, wx.EXPAND)
        self.path_text = wx.StaticText(self.header, label="（空 / Empty）")
        text_col.Add(self.path_text, 0, wx.EXPAND)
        header_sizer.Add(text_col, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 4)

        if not is_character_row:
            self.up_btn = wx.Button(self.header, label="↑", size=(30, 30))
            self.down_btn = wx.Button(self.header, label="↓", size=(30, 30))
            self.load_btn = wx.Button(self.header, label="加载素材...", size=(80, 30))
            header_sizer.Add(self.up_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
            header_sizer.Add(self.down_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
            header_sizer.Add(self.load_btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 2)
            if on_header_clicked is not None:
                _bind_left_click(self.header, lambda e: (on_header_clicked(), e.Skip()))

        sizer.Add(self.header, 1, wx.EXPAND)

    def _on_paint(self, event: wx.Event) -> None:
        event.Skip()
        if not self._selected:
            return
        dc = wx.PaintDC(self)
        width, height = self.GetSize()
        pen = wx.Pen(SELECTED_BORDER, 2)
        dc.SetPen(pen)
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(1, 1, max(1, width - 2), max(1, height - 2))

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.thumb.set_selected(selected)
        self.SetBackgroundColour(wx.NullColour)
        self.header.SetBackgroundColour(wx.NullColour)
        self.Refresh(False)


class LayerDetailPlaceholderPanel(wx.Panel):
    """Compact idle state when no layer is selected."""

    def __init__(self, parent: wx.Window):
        super().__init__(parent, size=(-1, PLACEHOLDER_HEIGHT))
        self.SetMinSize((-1, PLACEHOLDER_HEIGHT))
        self.SetMaxSize((-1, PLACEHOLDER_HEIGHT))
        self.SetBackgroundColour(wx.Colour(248, 248, 252))

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(sizer)
        sizer.AddStretchSpacer(1)
        self.hint_text = wx.StaticText(
            self,
            label=PLACEHOLDER_TEXT,
            style=wx.ALIGN_CENTER_HORIZONTAL)
        self.hint_text.SetForegroundColour(wx.Colour(100, 100, 108))
        sizer.Add(self.hint_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        sizer.AddStretchSpacer(1)


class LayerDetailDock(wx.Panel):
    """Detail area below the layer list; placeholder when idle, editor when a layer is selected."""

    def __init__(self, parent: wx.Window):
        super().__init__(parent, style=wx.BORDER_SIMPLE)
        self.SetMinSize((-1, DETAIL_DOCK_MIN_HEIGHT))

        root = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(root)

        self.placeholder_panel = LayerDetailPlaceholderPanel(self)
        root.Add(self.placeholder_panel, 0, wx.EXPAND)

        self.editor_scroll = wx.ScrolledWindow(self, style=wx.VSCROLL)
        self.editor_scroll.SetScrollRate(0, 10)
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        self.editor_scroll.SetSizer(scroll_sizer)

        self.editor_panel = wx.Panel(self.editor_scroll)
        scroll_sizer.Add(self.editor_panel, 0, wx.EXPAND)
        editor_root = wx.BoxSizer(wx.VERTICAL)
        self.editor_panel.SetSizer(editor_root)

        self.title_text = wx.StaticText(self.editor_panel, label="图层详情 / Layer detail")
        title_font = self.title_text.GetFont()
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.title_text.SetFont(title_font)
        editor_root.Add(self.title_text, 0, wx.ALL, 6)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self.reset_btn = wx.Button(self.editor_panel, label="归位 / Center")
        self.clear_btn = wx.Button(self.editor_panel, label="清除 / Clear")
        btn_row.Add(self.reset_btn, 0, wx.RIGHT, 6)
        btn_row.Add(self.clear_btn, 0, wx.RIGHT, 6)
        editor_root.Add(btn_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.layer_block = wx.Panel(self.editor_panel)
        layer_sizer = wx.BoxSizer(wx.VERTICAL)
        self.layer_block.SetSizer(layer_sizer)

        self.visible_cb = wx.CheckBox(self.layer_block, label="显示 / Visible")
        layer_sizer.Add(self.visible_cb, 0, wx.ALL, 4)

        scale_row = wx.BoxSizer(wx.HORIZONTAL)
        scale_row.Add(
            wx.StaticText(self.layer_block, label="缩放 / Scale"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            6)
        self.scale_slider = wx.Slider(
            self.layer_block, value=100, minValue=5, maxValue=300, style=wx.SL_HORIZONTAL)
        scale_row.Add(self.scale_slider, 1, wx.EXPAND)
        self.scale_label = wx.StaticText(self.layer_block, label="1.00")
        scale_row.Add(self.scale_label, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 8)
        layer_sizer.Add(scale_row, 0, wx.EXPAND | wx.ALL, 4)

        rotation_row = wx.BoxSizer(wx.HORIZONTAL)
        rotation_row.Add(
            wx.StaticText(self.layer_block, label="旋转 / Rotate"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            6)
        self.rotation_slider = wx.Slider(
            self.layer_block, value=0, minValue=-180, maxValue=180, style=wx.SL_HORIZONTAL)
        rotation_row.Add(self.rotation_slider, 1, wx.EXPAND)
        self.rotation_label = wx.StaticText(self.layer_block, label="0°")
        rotation_row.Add(self.rotation_label, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 8)
        layer_sizer.Add(rotation_row, 0, wx.EXPAND | wx.ALL, 4)

        bind_row = wx.BoxSizer(wx.HORIZONTAL)
        bind_row.Add(
            wx.StaticText(self.layer_block, label="绑定 / Bind"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            6)
        self.binding_choice = wx.Choice(
            self.layer_block,
            choices=[
                "（无 / None）",
                "角色·身体 / Character body",
                "角色·头 / Character head",
                "图层1 / Layer 1",
                "图层2 / Layer 2",
                "图层3 / Layer 3",
                "图层4 / Layer 4",
                "图层5 / Layer 5",
            ])
        bind_row.Add(self.binding_choice, 1, wx.EXPAND)
        layer_sizer.Add(bind_row, 0, wx.EXPAND | wx.ALL, 4)

        follow_rot_row = wx.BoxSizer(wx.VERTICAL)
        self.binding_follow_rotation_radio = wx.RadioBox(
            self.layer_block,
            label="跟转 / Follow rotation",
            choices=[
                "不跟转 / Off",
                "同步跟转 / Sync follow",
                "反向跟转 / Follow −",
            ],
            majorDimension=1,
            style=wx.RA_SPECIFY_ROWS)
        self.binding_follow_rotation_radio.SetToolTip(
            "三选一：不跟转、与绑定目标同步、与绑定目标反向 / "
            "Pick one: off, sync with target, or opposite")
        follow_rot_row.Add(self.binding_follow_rotation_radio, 0, wx.EXPAND | wx.ALL, 4)
        layer_sizer.Add(follow_rot_row, 0, wx.EXPAND)

        self.binding_follow_smooth_cb = wx.CheckBox(
            self.layer_block,
            label="平滑跟随 / Smooth follow")
        self.binding_follow_smooth_cb.SetToolTip(
            "关 = 绑定图层立即跟目标（无 EMA）；开 = 位置/跟转指数平滑 / "
            "Off = instant bind follow; on = EMA-smooth position and rotation")
        layer_sizer.Add(self.binding_follow_smooth_cb, 0, wx.ALL, 4)

        smooth_alpha_row = wx.BoxSizer(wx.HORIZONTAL)
        smooth_alpha_row.Add(
            wx.StaticText(self.layer_block, label="平滑系数 / Smooth α"),
            0,
            wx.ALIGN_CENTER_VERTICAL | wx.RIGHT,
            6)
        self.binding_follow_smooth_alpha_slider = wx.Slider(
            self.layer_block,
            value=int(round(BINDING_SMOOTH_ALPHA * 100)),
            minValue=5,
            maxValue=100,
            style=wx.SL_HORIZONTAL)
        self.binding_follow_smooth_alpha_slider.SetToolTip(
            "每层独立：越大越跟手，越小越稳 / Per-layer EMA strength (5–100%)")
        smooth_alpha_row.Add(self.binding_follow_smooth_alpha_slider, 1, wx.EXPAND)
        self.binding_follow_smooth_alpha_label = wx.StaticText(
            self.layer_block, label=f"{int(round(BINDING_SMOOTH_ALPHA * 100))}%")
        smooth_alpha_row.Add(
            self.binding_follow_smooth_alpha_label,
            0,
            wx.LEFT | wx.ALIGN_CENTER_VERTICAL,
            8)
        layer_sizer.Add(smooth_alpha_row, 0, wx.EXPAND | wx.ALL, 4)

        mocap_row = wx.BoxSizer(wx.HORIZONTAL)
        self.binding_follow_mocap_position_cb = wx.CheckBox(
            self.layer_block,
            label="增强面捕头部位移 (易抖) / Extra mocap head position")
        self.binding_follow_mocap_position_cb.SetToolTip(
            "头部绑定已含基础面捕位移；勾选可提高增益，帧间更易抖 / "
            "Head bind includes baseline pose offset; extra gain is jittery")
        self.binding_follow_mocap_roll_cb = wx.CheckBox(
            self.layer_block,
            label="增强面捕头部滚转 (易抖) / Extra mocap head roll")
        self.binding_follow_mocap_roll_cb.SetToolTip(
            "头部绑定已含基础滚转；勾选可提高增益，与跟转叠加后易抖 / "
            "Head bind includes baseline neck roll; extra gain is jittery")
        mocap_row.Add(self.binding_follow_mocap_position_cb, 0, wx.ALL, 4)
        mocap_row.Add(self.binding_follow_mocap_roll_cb, 0, wx.ALL, 4)
        layer_sizer.Add(mocap_row, 0, wx.EXPAND)

        self.binding_signal_help = wx.StaticText(
            self.layer_block,
            label=(
                "两段射线（可延伸）：① 底→脖 ② 脖→头；参考 % 仅移动示意点，不移动已绑图层。"
                " / Unbounded spine rays; reference % moves diagram only."))
        self.binding_signal_help.Wrap(440)
        self.binding_signal_help.SetForegroundColour(wx.Colour(100, 100, 100))
        layer_sizer.Add(self.binding_signal_help, 0, wx.ALL, 4)

        editor_root.Add(self.layer_block, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        root.Add(self.editor_scroll, 1, wx.EXPAND)
        self.show_placeholder()

    def show_placeholder(self) -> None:
        self.editor_scroll.Hide()
        self.placeholder_panel.Show()
        self.Layout()

    def show_editor(self) -> None:
        self.placeholder_panel.Hide()
        self.editor_scroll.Show()
        self.editor_panel.Layout()
        self.editor_scroll.Layout()
        self.editor_scroll.FitInside()
        self.Layout()


class BasicLayerWindow(wx.Frame):
    def __init__(self, main_frame: MainFrame, parent: Optional[wx.Window] = None):
        super().__init__(
            parent,
            wx.ID_ANY,
            title="五层图层 / Basic Five Layers",
            style=wx.DEFAULT_FRAME_STYLE)
        self.main_frame = main_frame
        self._row_panels: dict[int, LayerRowPanel] = {}
        self._character_row: Optional[LayerRowPanel] = None
        self._building = False
        self._detail_slot_id: Optional[int] = None

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(sizer)

        self.scroll = wx.ScrolledWindow(panel, style=wx.VSCROLL)
        self.scroll.SetScrollRate(0, 16)
        self.scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        self.scroll.SetSizer(self.scroll_sizer)
        sizer.Add(self.scroll, 1, wx.EXPAND | wx.ALL, 4)

        self.detail_dock = LayerDetailDock(panel)
        sizer.Add(self.detail_dock, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        self.spine_reference = SpineRayReferencePanel(panel, main_frame)
        sizer.Add(self.spine_reference, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(frame_sizer)
        frame_sizer.Add(panel, 1, wx.EXPAND)

        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.Bind(wx.EVT_MOVE, self.on_geometry_changed)
        self.Bind(wx.EVT_SIZE, self.on_geometry_changed)
        self.Bind(wx.EVT_ACTIVATE, self._on_activate)

        self.rebuild_rows()
        self._wire_detail_dock()
        self._refresh_detail_dock()
        self.SetMinSize((480, 680))
        self.restore_geometry()
        self.Layout()

    def on_close(self, event: wx.Event):
        event.Veto()
        self.Hide()
        self.main_frame.save_basic_layer_window_geometry()

    def on_geometry_changed(self, event: wx.Event):
        self.main_frame.save_basic_layer_window_geometry()
        event.Skip()

    def _on_activate(self, event: wx.Event) -> None:
        self.main_frame.on_window_activate_for_layer_selection(event, self)
        event.Skip()

    def restore_geometry(self) -> None:
        data = self.main_frame.persistent_ui_state
        x = int(data.get("basic_layer_window_x", 80))
        y = int(data.get("basic_layer_window_y", 80))
        width = max(480, int(data.get("basic_layer_window_width", 640)))
        height = max(560, int(data.get("basic_layer_window_height", 720)))
        clamped = self.main_frame.clamp_client_rect_to_visible_screen(
            wx.Rect(x, y, width, height))
        self.SetSize(clamped.width, clamped.height)
        self.SetPosition((clamped.x, clamped.y))
        if clamped.x != x or clamped.y != y or clamped.width != width or clamped.height != height:
            self.main_frame.persistent_ui_state["basic_layer_window_x"] = int(clamped.x)
            self.main_frame.persistent_ui_state["basic_layer_window_y"] = int(clamped.y)
            self.main_frame.persistent_ui_state["basic_layer_window_width"] = int(clamped.width)
            self.main_frame.persistent_ui_state["basic_layer_window_height"] = int(clamped.height)

    def _refresh_layout(self) -> None:
        self.scroll.Layout()
        self.scroll.FitInside()
        self.detail_dock.editor_panel.Layout()
        if self.detail_dock.editor_scroll.IsShown():
            self.detail_dock.editor_scroll.Layout()
            self.detail_dock.editor_scroll.FitInside()
        self.detail_dock.Layout()
        self.Layout()

    def _wire_detail_dock(self) -> None:
        dock = self.detail_dock
        dock.reset_btn.Bind(wx.EVT_BUTTON, self._on_reset_transform)
        dock.clear_btn.Bind(wx.EVT_BUTTON, self._on_clear_asset)
        dock.visible_cb.Bind(wx.EVT_CHECKBOX, self._on_detail_changed)
        dock.scale_slider.Bind(wx.EVT_SLIDER, self._on_scale_changed)
        dock.rotation_slider.Bind(wx.EVT_SLIDER, self._on_rotation_changed)
        dock.binding_choice.Bind(wx.EVT_CHOICE, self._on_detail_changed)
        dock.binding_follow_rotation_radio.Bind(wx.EVT_RADIOBOX, self._on_detail_changed)
        dock.binding_follow_smooth_cb.Bind(wx.EVT_CHECKBOX, self._on_detail_changed)
        dock.binding_follow_smooth_alpha_slider.Bind(
            wx.EVT_SLIDER, self._on_smooth_alpha_changed)
        dock.binding_follow_mocap_position_cb.Bind(wx.EVT_CHECKBOX, self._on_detail_changed)
        dock.binding_follow_mocap_roll_cb.Bind(wx.EVT_CHECKBOX, self._on_detail_changed)

    def rebuild_rows(self) -> None:
        selected = self.main_frame.basic_layers_state.selected_slot_id

        self.scroll_sizer.Clear(True)
        self._row_panels.clear()
        self._character_row = None
        state: BasicLayersState = self.main_frame.basic_layers_state
        cache: LayerAssetCache = self.main_frame.layer_asset_cache

        for kind, slot_id in iter_ui_list_top_to_bottom(state):
            if kind == "character":
                self._character_row = LayerRowPanel(
                    self.scroll,
                    slot_id=None,
                    title="原图 / Character",
                    is_character_row=True)
                self._refresh_character_row()
                self.scroll_sizer.Add(self._character_row, 0, wx.EXPAND | wx.BOTTOM, 4)
                continue
            assert slot_id is not None
            layer = state.get_slot(slot_id)
            row = LayerRowPanel(
                self.scroll,
                slot_id=slot_id,
                title=f"图层 {slot_id + 1} / Layer {slot_id + 1}",
                is_character_row=False,
                on_header_clicked=lambda sid=slot_id: self._select_slot(sid))
            self._wire_layer_row(row, layer)
            self._populate_row(row, layer, cache)
            row.set_selected(selected == slot_id)
            self._row_panels[slot_id] = row
            self.scroll_sizer.Add(row, 0, wx.EXPAND | wx.BOTTOM, 4)

        if selected is not None and selected in self._row_panels:
            self._detail_slot_id = selected
        self._refresh_detail_dock()
        self._refresh_layout()

    def _wire_layer_row(self, row: LayerRowPanel, layer: BasicLayerSlot) -> None:
        row.load_btn.Bind(wx.EVT_BUTTON, lambda e, sid=layer.slot_id: self._load_asset(sid))
        row.up_btn.Bind(wx.EVT_BUTTON, lambda e, sid=layer.slot_id: self._move_layer(sid, 1))
        row.down_btn.Bind(wx.EVT_BUTTON, lambda e, sid=layer.slot_id: self._move_layer(sid, -1))

    def refresh_all(self) -> None:
        if self._building:
            return
        state = self.main_frame.basic_layers_state
        cache = self.main_frame.layer_asset_cache
        selected = state.selected_slot_id
        for layer in state.layers:
            row = self._row_panels.get(layer.slot_id)
            if row is None:
                continue
            self._populate_row(row, layer, cache)
            row.set_selected(layer.slot_id == selected)
        self._refresh_character_row()
        self._refresh_detail_dock()
        if hasattr(self, "spine_reference"):
            self.spine_reference.sync_from_main_frame()
        self._refresh_layout()

    def refresh_spine_diagram(self) -> None:
        if hasattr(self, "spine_reference"):
            self.spine_reference.refresh_diagram_live()

    def _refresh_character_row(self) -> None:
        if self._character_row is None:
            return
        source_bitmap = self.main_frame.wx_source_image
        if source_bitmap is not None and source_bitmap.IsOk():
            thumb = source_bitmap.ConvertToImage().Scale(
                THUMB_SIZE, THUMB_SIZE, wx.IMAGE_QUALITY_HIGH)
            self._character_row.thumb.set_bitmap(thumb.ConvertToBitmap())
            if self.main_frame.last_loaded_model_path:
                name = os.path.basename(self.main_frame.last_loaded_model_path)
            elif self.main_frame.last_tha3_character_png:
                name = os.path.basename(self.main_frame.last_tha3_character_png)
            else:
                name = "角色立绘"
            self._character_row.title_text.SetLabel(
                f"原图 · {truncate_display_filename(name)}")
            self._character_row.path_text.SetLabel(
                f"主层 z{CHARACTER_STACK_POS + 1} | 已加载 | 角色底图")
        else:
            self._character_row.thumb.set_bitmap(
                self.main_frame.layer_asset_cache.thumbnail_bitmap(
                    BasicLayerSlot(slot_id=-1)))
            self._character_row.title_text.SetLabel("原图 / Character")
            self._character_row.path_text.SetLabel("主层 | 未加载")

    def _populate_row(self, row: LayerRowPanel, layer: BasicLayerSlot, cache: LayerAssetCache) -> None:
        row.thumb.set_bitmap(cache.thumbnail_bitmap(layer))
        row.title_text.SetLabel(format_layer_row_title(layer.slot_id, layer))
        row.path_text.SetLabel(format_layer_row_summary(layer))
        row.up_btn.Enable(stack_position_can_move_up(layer.z_order))
        row.down_btn.Enable(stack_position_can_move_down(layer.z_order))

    def _refresh_detail_dock(self) -> None:
        state = self.main_frame.basic_layers_state
        slot_id = state.selected_slot_id
        self._detail_slot_id = slot_id
        dock = self.detail_dock
        if slot_id is None or slot_id not in self._row_panels:
            dock.show_placeholder()
            self._refresh_layout()
            return

        dock.show_editor()
        layer = state.get_slot(slot_id)
        dock.title_text.SetLabel(format_layer_row_title(slot_id, layer))
        dock.visible_cb.SetValue(layer.visible)
        scale_pct = int(round(max(0.05, layer.transform.scale) * 100))
        dock.scale_slider.SetValue(max(5, min(300, scale_pct)))
        dock.scale_label.SetLabel(f"{layer.transform.scale:.2f}")
        dock.rotation_slider.SetValue(max(-180, min(180, int(round(layer.transform.rotation_deg)))))
        dock.rotation_label.SetLabel(f"{layer.transform.rotation_deg:.0f}°")
        binding_index = 0
        normalized = normalize_binding_target(layer.binding_parent)
        if normalized == BINDING_CHARACTER_BODY:
            binding_index = 1
        elif normalized == BINDING_CHARACTER_HEAD:
            binding_index = 2
        else:
            parent_slot = parse_layer_binding_slot(normalized)
            if parent_slot is not None:
                binding_index = 3 + parent_slot
        dock.binding_choice.SetSelection(min(binding_index, dock.binding_choice.GetCount() - 1))
        has_binding = normalize_binding_target(layer.binding_parent) is not None
        follow_mode = 0
        if has_binding:
            if layer.binding_follow_rotation_same:
                follow_mode = 1
            elif layer.binding_follow_rotation_reverse:
                follow_mode = 2
        dock.binding_follow_rotation_radio.Enable(has_binding)
        dock.binding_follow_rotation_radio.SetSelection(follow_mode)
        dock.binding_follow_smooth_cb.Enable(has_binding)
        dock.binding_follow_smooth_cb.SetValue(
            bool(layer.binding_follow_smooth) if has_binding else True)
        alpha_pct = int(round(binding_smooth_alpha_for_layer(layer) * 100))
        dock.binding_follow_smooth_alpha_slider.SetValue(max(5, min(100, alpha_pct)))
        dock.binding_follow_smooth_alpha_label.SetLabel(f"{alpha_pct}%")
        smooth_alpha_enabled = has_binding and layer.binding_follow_smooth
        dock.binding_follow_smooth_alpha_slider.Enable(smooth_alpha_enabled)
        is_head_binding = normalized == BINDING_CHARACTER_HEAD
        dock.binding_follow_mocap_position_cb.Enable(has_binding and is_head_binding)
        dock.binding_follow_mocap_roll_cb.Enable(has_binding and is_head_binding)
        dock.binding_follow_mocap_position_cb.SetValue(
            bool(layer.binding_follow_mocap_position) if is_head_binding else False)
        dock.binding_follow_mocap_roll_cb.SetValue(
            bool(layer.binding_follow_mocap_roll) if is_head_binding else False)
        self._refresh_layout()

    def apply_selection(self, slot_id: Optional[int]) -> None:
        self._detail_slot_id = slot_id
        for sid, row in self._row_panels.items():
            row.set_selected(slot_id is not None and sid == slot_id)
        self._refresh_detail_dock()

    def _select_slot(self, slot_id: int) -> None:
        self.main_frame.basic_layers_state.selected_slot_id = slot_id
        self.apply_selection(slot_id)
        self.main_frame.persist_basic_layers_state()
        if self.main_frame.last_output_wx_image is not None:
            self.main_frame.draw_cached_result_image(self.main_frame.last_banner_text)
        self.main_frame.refresh_layer_blend_status()

    def _current_detail_slot(self) -> Optional[int]:
        selected = self.main_frame.basic_layers_state.selected_slot_id
        if selected is None or selected < 0:
            return None
        return selected

    def _load_asset(self, slot_id: int) -> None:
        dialog = wx.FileDialog(
            self,
            "选择图层素材 / Choose layer asset",
            wildcard=LAYER_ASSET_FILE_WILDCARD,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        self.main_frame._suppress_layer_deselect = True
        try:
            if dialog.ShowModal() != wx.ID_OK:
                dialog.Destroy()
                return
        finally:
            self.main_frame._suppress_layer_deselect = False
        path = dialog.GetPath()
        dialog.Destroy()
        rel = self.main_frame.relativize_path_for_persistence(path)
        layer = self.main_frame.basic_layers_state.get_slot(slot_id)
        self.main_frame.layer_asset_cache.invalidate(layer.asset_path)
        layer.asset_path = rel
        layer.enabled = True
        layer.visible = True
        center_layer_transform(layer.transform)
        self.main_frame.persist_basic_layers_state()
        self._select_slot(slot_id)
        self.refresh_all()
        self.main_frame.on_layer_state_changed()

    def _on_clear_asset(self, event: wx.Event) -> None:
        slot_id = self._current_detail_slot()
        if slot_id is None:
            return
        layer = self.main_frame.basic_layers_state.get_slot(slot_id)
        self.main_frame.layer_asset_cache.invalidate(layer.asset_path)
        layer.asset_path = None
        self.main_frame.persist_basic_layers_state()
        self.refresh_all()
        self.main_frame.on_layer_state_changed()
        event.Skip()

    def _move_layer(self, slot_id: int, delta: int) -> None:
        if not move_layer_z_order(self.main_frame.basic_layers_state, slot_id, delta):
            return
        self.main_frame.basic_layers_state.selected_slot_id = slot_id
        self.main_frame.persist_basic_layers_state()
        self._building = True
        try:
            self.rebuild_rows()
        finally:
            self._building = False
        self.main_frame.on_layer_state_changed()

    def _on_scale_changed(self, event: wx.Event) -> None:
        slot_id = self._current_detail_slot()
        if slot_id is None:
            return
        layer = self.main_frame.basic_layers_state.get_slot(slot_id)
        layer.transform.scale = max(0.05, self.detail_dock.scale_slider.GetValue() / 100.0)
        self.detail_dock.scale_label.SetLabel(f"{layer.transform.scale:.2f}")
        self.main_frame.persist_basic_layers_state()
        self.main_frame.on_layer_state_changed()
        event.Skip()

    def _on_rotation_changed(self, event: wx.Event) -> None:
        slot_id = self._current_detail_slot()
        if slot_id is None:
            return
        layer = self.main_frame.basic_layers_state.get_slot(slot_id)
        layer.transform.rotation_deg = float(self.detail_dock.rotation_slider.GetValue())
        self.detail_dock.rotation_label.SetLabel(f"{layer.transform.rotation_deg:.0f}°")
        self.main_frame.persist_basic_layers_state()
        self.main_frame.on_layer_state_changed()
        event.Skip()

    def _on_reset_transform(self, event: wx.Event) -> None:
        slot_id = self._current_detail_slot()
        if slot_id is None:
            return
        layer = self.main_frame.basic_layers_state.get_slot(slot_id)
        center_layer_transform(layer.transform)
        self.main_frame.persist_basic_layers_state()
        self._refresh_detail_dock()
        self.main_frame.on_layer_state_changed()
        event.Skip()

    def _on_smooth_alpha_changed(self, event: wx.Event) -> None:
        slot_id = self._current_detail_slot()
        if slot_id is None:
            return
        layer = self.main_frame.basic_layers_state.get_slot(slot_id)
        alpha_pct = max(5, min(100, self.detail_dock.binding_follow_smooth_alpha_slider.GetValue()))
        layer.binding_follow_smooth_alpha = clamp_binding_smooth_alpha(alpha_pct / 100.0)
        self.detail_dock.binding_follow_smooth_alpha_label.SetLabel(f"{alpha_pct}%")
        self.main_frame.layer_binding_smoother.reset_slot(slot_id)
        self.main_frame.persist_basic_layers_state()
        self.main_frame.on_layer_state_changed()
        event.Skip()

    def _on_detail_changed(self, event: wx.Event) -> None:
        slot_id = self._current_detail_slot()
        if slot_id is None:
            return
        row = self._row_panels.get(slot_id)
        if row is None:
            return
        layer = self.main_frame.basic_layers_state.get_slot(slot_id)
        dock = self.detail_dock
        old_bind = normalize_binding_target(layer.binding_parent)
        layer.visible = dock.visible_cb.GetValue()
        choice = dock.binding_choice.GetSelection()
        if choice <= 0:
            layer.binding_parent = None
            layer.binding_follow_rotation_same = False
            layer.binding_follow_rotation_reverse = False
            layer.binding_follow_mocap_position = False
            layer.binding_follow_mocap_roll = False
        elif choice == 1:
            layer.binding_parent = BINDING_CHARACTER_BODY
            layer.binding_follow_mocap_position = False
            layer.binding_follow_mocap_roll = False
        elif choice == 2:
            layer.binding_parent = BINDING_CHARACTER_HEAD
        else:
            parent_slot = choice - 3
            if parent_slot == slot_id:
                layer.binding_parent = None
                layer.binding_follow_rotation_same = False
                layer.binding_follow_rotation_reverse = False
                layer.binding_follow_mocap_position = False
                layer.binding_follow_mocap_roll = False
            else:
                layer.binding_parent = f"layer:{parent_slot}"
                layer.binding_follow_mocap_position = False
                layer.binding_follow_mocap_roll = False
        layer.binding_parent = normalize_binding_target(layer.binding_parent)
        new_bind = normalize_binding_target(layer.binding_parent)
        if new_bind is None:
            layer.binding_ray_percent = None
            layer.binding_neck_anchor_ratio = None
            layer.binding_follow_rotation_same = False
            layer.binding_follow_rotation_reverse = False
            layer.binding_follow_mocap_position = False
            layer.binding_follow_mocap_roll = False
        elif new_bind == BINDING_CHARACTER_BODY:
            if old_bind != BINDING_CHARACTER_BODY:
                layer.binding_ray_percent = self.main_frame.get_spine_body_bind_ray_percent()
                layer.binding_neck_anchor_ratio = self.main_frame.get_spine_neck_anchor_ratio()
        elif new_bind == BINDING_CHARACTER_HEAD:
            if old_bind != BINDING_CHARACTER_HEAD:
                layer.binding_ray_percent = self.main_frame.get_spine_head_bind_ray_percent()
                layer.binding_neck_anchor_ratio = self.main_frame.get_spine_neck_anchor_ratio()
        if layer.binding_parent is None:
            layer.binding_follow_rotation_same = False
            layer.binding_follow_rotation_reverse = False
            layer.binding_follow_mocap_position = False
            layer.binding_follow_mocap_roll = False
        else:
            follow_mode = dock.binding_follow_rotation_radio.GetSelection()
            layer.binding_follow_rotation_same = follow_mode == 1
            layer.binding_follow_rotation_reverse = follow_mode == 2
            layer.binding_follow_smooth = dock.binding_follow_smooth_cb.GetValue()
            layer.binding_follow_smooth_alpha = clamp_binding_smooth_alpha(
                dock.binding_follow_smooth_alpha_slider.GetValue() / 100.0)
            if normalize_binding_target(layer.binding_parent) == BINDING_CHARACTER_HEAD:
                layer.binding_follow_mocap_position = dock.binding_follow_mocap_position_cb.GetValue()
                layer.binding_follow_mocap_roll = dock.binding_follow_mocap_roll_cb.GetValue()
            else:
                layer.binding_follow_mocap_position = False
                layer.binding_follow_mocap_roll = False
        self.main_frame.layer_binding_smoother.reset_slot(slot_id)
        self.main_frame.head_binding_pose_filter.reset()
        self.main_frame.persist_basic_layers_state()
        self.main_frame.on_layer_state_changed()
        event.Skip()
