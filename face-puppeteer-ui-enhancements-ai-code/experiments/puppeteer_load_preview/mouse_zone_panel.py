"""Screen / center-zone diagram for Mouse + Audio mocap (drag move + edge resize)."""
from __future__ import annotations

import math
from typing import Callable, Optional, Set, Tuple

import wx

from mouse_mocap_driver import (
    MOUSE_ZONE_HALF_MAX,
    MOUSE_ZONE_HALF_MIN,
    MouseCenterZone,
    MouseTrackingSurface,
    clamp,
    get_mouse_tracking_surface,
    is_mouse_inside_center_zone,
)

ZONE_PANEL_WIDTH = 280
ZONE_PANEL_HEIGHT = 180
HIT_EDGE_PX = 6
RULER_MARGIN_PX = 22
EDGE_HIGHLIGHT_PX = 3
HIGHLIGHT_COLOUR = wx.Colour(230, 90, 20)
INNER_BORDER_COLOUR = wx.Colour(200, 140, 40)


def _nice_pixel_step(span_px: int, target_ticks: int = 5) -> int:
    if span_px <= 0:
        return 1
    raw = max(1, int(math.ceil(span_px / max(target_ticks, 1))))
    magnitude = 10 ** int(math.floor(math.log10(raw)))
    for multiplier in (1, 2, 5, 10):
        step = magnitude * multiplier
        if step >= raw:
            return max(1, int(step))
    return max(1, raw * 10)


def _highlight_edges_for_mode(mode: Optional[str]) -> Set[str]:
    if mode is None or mode == "move":
        return set()
    if mode == "resize_n":
        return {"n"}
    if mode == "resize_s":
        return {"s"}
    if mode == "resize_e":
        return {"e"}
    if mode == "resize_w":
        return {"w"}
    if mode == "resize_nw":
        return {"n", "w"}
    if mode == "resize_ne":
        return {"n", "e"}
    if mode == "resize_sw":
        return {"s", "w"}
    if mode == "resize_se":
        return {"s", "e"}
    return set()


class MouseZonePanel(wx.Panel):
    def __init__(
            self,
            parent: wx.Window,
            *,
            zone: MouseCenterZone,
            on_zone_changed: Callable[[MouseCenterZone], None]):
        super().__init__(parent, size=(ZONE_PANEL_WIDTH, ZONE_PANEL_HEIGHT), style=wx.SIMPLE_BORDER)
        self._zone = zone.clamped_to_surface()
        self._on_zone_changed = on_zone_changed
        self._mouse_nx: Optional[float] = None
        self._mouse_ny: Optional[float] = None
        self._drag_mode: Optional[str] = None
        self._hover_mode: Optional[str] = None
        self._resize_fixed_edges: Optional[Tuple[float, float, float, float]] = None
        self._drag_anchor_norm = (0.0, 0.0)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetBackgroundColour(wx.Colour(248, 248, 248))
        self.SetDoubleBuffered(True)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, self.on_erase_background)
        self.Bind(wx.EVT_LEFT_DOWN, self.on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self.on_left_up)
        self.Bind(wx.EVT_MOTION, self.on_motion)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave_window)

    def get_zone(self) -> MouseCenterZone:
        return self._zone.clamped_to_surface()

    def set_zone(self, zone: MouseCenterZone, *, refresh: bool = True) -> None:
        self._zone = zone.clamped_to_surface()
        if refresh:
            self.Refresh(False)

    def set_mouse_position(self, nx: float, ny: float, *, refresh: bool = True) -> None:
        self._mouse_nx = clamp(nx, -1.0, 1.0)
        self._mouse_ny = clamp(ny, -1.0, 1.0)
        if refresh:
            self.Refresh(False)

    def on_erase_background(self, event: wx.Event):
        pass

    def _tracking_surface(self) -> MouseTrackingSurface:
        return get_mouse_tracking_surface()

    def _screen_draw_rect(self) -> Tuple[wx.Rect, MouseTrackingSurface]:
        """Letterboxed screen rect preserving real pixel aspect ratio."""
        surface = self._tracking_surface()
        client_width, client_height = self.GetClientSize()
        margin = 8
        avail_width = max(1, client_width - 2 * margin - RULER_MARGIN_PX)
        avail_height = max(1, client_height - 2 * margin - RULER_MARGIN_PX)
        aspect = surface.aspect_ratio
        if avail_width / avail_height >= aspect:
            screen_height = avail_height
            screen_width = max(1, int(round(screen_height * aspect)))
        else:
            screen_width = avail_width
            screen_height = max(1, int(round(screen_width / aspect)))
        x = margin + RULER_MARGIN_PX + (avail_width - screen_width) // 2
        y = margin + (avail_height - screen_height) // 2
        return wx.Rect(x, y, screen_width, screen_height), surface

    def _norm_to_panel(self, nx: float, ny: float) -> tuple[int, int]:
        screen_rect, _surface = self._screen_draw_rect()
        nx_clamped = clamp(nx, -1.0, 1.0)
        ny_clamped = clamp(ny, -1.0, 1.0)
        px = int(round(screen_rect.x + (nx_clamped + 1.0) * 0.5 * screen_rect.width))
        py = int(round(screen_rect.y + (1.0 - ny_clamped) * 0.5 * screen_rect.height))
        return px, py

    def _panel_to_norm(self, px: int, py: int) -> tuple[float, float]:
        screen_rect, _surface = self._screen_draw_rect()
        nx = (px - screen_rect.x) / max(screen_rect.width, 1) * 2.0 - 1.0
        ny = 1.0 - (py - screen_rect.y) / max(screen_rect.height, 1) * 2.0
        return nx, ny

    def _zone_norm_edges(self) -> Tuple[float, float, float, float]:
        zone = self._zone.clamped_to_surface()
        return (
            zone.center_nx - zone.half_width,
            zone.center_nx + zone.half_width,
            zone.center_ny - zone.half_height,
            zone.center_ny + zone.half_height,
        )

    def _inner_rect(self) -> wx.Rect:
        left, right, bottom, top = self._zone_norm_edges()
        left = clamp(left, -1.0, 1.0)
        right = clamp(right, -1.0, 1.0)
        bottom = clamp(bottom, -1.0, 1.0)
        top = clamp(top, -1.0, 1.0)
        x0, y_top = self._norm_to_panel(left, top)
        x1, y_bottom = self._norm_to_panel(right, bottom)
        return wx.Rect(
            min(x0, x1),
            min(y_top, y_bottom),
            max(1, abs(x1 - x0)),
            max(1, abs(y_bottom - y_top)))

    def _draw_edge_highlights(self, dc: wx.DC, inner: wx.Rect, edges: Set[str]) -> None:
        if not edges:
            return
        highlight_pen = wx.Pen(HIGHLIGHT_COLOUR, EDGE_HIGHLIGHT_PX + 2)
        dc.SetPen(highlight_pen)
        x0 = inner.x
        y0 = inner.y
        x1 = inner.x + inner.width
        y1 = inner.y + inner.height
        if "n" in edges:
            dc.DrawLine(x0, y0, x1, y0)
        if "s" in edges:
            dc.DrawLine(x0, y1, x1, y1)
        if "w" in edges:
            dc.DrawLine(x0, y0, x0, y1)
        if "e" in edges:
            dc.DrawLine(x1, y0, x1, y1)

    def _draw_mouse_position_marker(
            self,
            dc: wx.DC,
            screen_rect: wx.Rect,
            inner: wx.Rect) -> None:
        if self._mouse_nx is None or self._mouse_ny is None:
            return
        px, py = self._norm_to_panel(self._mouse_nx, self._mouse_ny)
        inside_center = is_mouse_inside_center_zone(
            self._mouse_nx,
            self._mouse_ny,
            self._zone)
        if inside_center:
            fill_colour = wx.Colour(40, 170, 70)
            outline_colour = wx.Colour(20, 100, 40)
        else:
            fill_colour = wx.Colour(220, 60, 50)
            outline_colour = wx.Colour(140, 30, 20)
        radius = 5
        dc.SetBrush(wx.Brush(fill_colour))
        dc.SetPen(wx.Pen(outline_colour, 2))
        dc.DrawCircle(px, py, radius)
        dc.SetPen(wx.Pen(outline_colour, 1))
        dc.DrawLine(px - radius - 3, py, px + radius + 3, py)
        dc.DrawLine(px, py - radius - 3, px, py + radius + 3)
        if not inner.Contains((px, py)):
            dc.SetPen(wx.Pen(outline_colour, 1, wx.PENSTYLE_DOT))
            dc.DrawLine(inner.x + inner.width // 2, inner.y + inner.height // 2, px, py)

    def _draw_pixel_rulers(self, dc: wx.DC, screen_rect: wx.Rect, surface: MouseTrackingSurface) -> None:
        font = wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        dc.SetFont(font)
        dc.SetTextForeground(wx.Colour(90, 90, 90))
        dc.SetPen(wx.Pen(wx.Colour(140, 140, 140)))

        x_step = _nice_pixel_step(surface.width)
        y_step = _nice_pixel_step(surface.height)
        tick_len = 4

        for pixel_offset in range(0, surface.width + 1, x_step):
            nx = (pixel_offset - surface.width * 0.5) / surface.half_width
            px, _py = self._norm_to_panel(nx, -1.0)
            dc.DrawLine(px, screen_rect.y + screen_rect.height, px, screen_rect.y + screen_rect.height + tick_len)
            label = str(surface.origin_x + pixel_offset)
            text_width, _text_height = dc.GetTextExtent(label)
            dc.DrawText(
                label,
                px - text_width // 2,
                screen_rect.y + screen_rect.height + tick_len + 2)

        for pixel_offset in range(0, surface.height + 1, y_step):
            ny = (surface.height * 0.5 - pixel_offset) / surface.half_height
            px, py = self._norm_to_panel(-1.0, ny)
            dc.DrawLine(screen_rect.x - tick_len, py, screen_rect.x, py)
            label = str(surface.origin_y + pixel_offset)
            text_width, text_height = dc.GetTextExtent(label)
            dc.DrawText(
                label,
                screen_rect.x - tick_len - text_width - 2,
                py - text_height // 2)

    def _hit_test(self, pos: wx.Point) -> Optional[str]:
        inner = self._inner_rect()
        edge = HIT_EDGE_PX
        on_left = abs(pos.x - inner.x) <= edge
        on_right = abs(pos.x - (inner.x + inner.width)) <= edge
        on_top = abs(pos.y - inner.y) <= edge
        on_bottom = abs(pos.y - (inner.y + inner.height)) <= edge
        near_edge = on_left or on_right or on_top or on_bottom

        if near_edge and (
                on_left or on_right or on_top or on_bottom):
            if not inner.Contains(pos):
                expanded = wx.Rect(
                    inner.x - edge,
                    inner.y - edge,
                    inner.width + 2 * edge,
                    inner.height + 2 * edge)
                if not expanded.Contains(pos):
                    return None
            if on_left and on_top:
                return "resize_nw"
            if on_right and on_top:
                return "resize_ne"
            if on_left and on_bottom:
                return "resize_sw"
            if on_right and on_bottom:
                return "resize_se"
            if on_left:
                return "resize_w"
            if on_right:
                return "resize_e"
            if on_top:
                return "resize_n"
            if on_bottom:
                return "resize_s"

        if inner.Contains(pos):
            return "move"
        return None

    def _update_hover_feedback(self, pos: wx.Point) -> None:
        mode = self._hit_test(pos)
        if mode != self._hover_mode:
            self._hover_mode = mode
            self.Refresh(False)
        if mode and mode.startswith("resize"):
            self.SetCursor(wx.Cursor(wx.CURSOR_SIZING))
        elif mode == "move":
            self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        else:
            self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))

    def _active_highlight_mode(self) -> Optional[str]:
        if self._drag_mode is not None:
            return self._drag_mode
        return self._hover_mode

    def _emit_zone_changed(self) -> None:
        if self._drag_mode is not None and self._drag_mode.startswith("resize"):
            self._zone = self._zone.clamped()
        else:
            self._zone = self._zone.clamped_to_surface()
        self._on_zone_changed(self._zone)
        self.Refresh(False)

    def _apply_resize_drag(self, nx: float, ny: float) -> None:
        if self._resize_fixed_edges is None or self._drag_mode is None:
            return
        left, right, bottom, top = self._resize_fixed_edges
        if "w" in self._drag_mode:
            left = nx
        if "e" in self._drag_mode:
            right = nx
        if "n" in self._drag_mode:
            top = ny
        if "s" in self._drag_mode:
            bottom = ny
        self._zone = MouseCenterZone.from_norm_edges(left, right, bottom, top)

    def on_paint(self, event: wx.Event):
        dc = wx.AutoBufferedPaintDC(self)
        width, height = self.GetClientSize()
        dc.SetBrush(wx.Brush(wx.Colour(252, 252, 252)))
        dc.SetPen(wx.Pen(wx.Colour(210, 210, 210)))
        dc.DrawRectangle(0, 0, width, height)

        screen_rect, surface = self._screen_draw_rect()
        dc.SetBrush(wx.Brush(wx.Colour(235, 245, 255)))
        dc.SetPen(wx.Pen(wx.Colour(80, 120, 180), 2))
        dc.DrawRectangle(screen_rect)

        inner = self._inner_rect()
        highlight_edges = _highlight_edges_for_mode(self._active_highlight_mode())

        dc.SetBrush(wx.Brush(wx.Colour(255, 250, 220, 120)))
        dc.SetPen(wx.Pen(INNER_BORDER_COLOUR, 2))
        dc.DrawRectangle(inner)
        self._draw_edge_highlights(dc, inner, highlight_edges)

        self._draw_mouse_position_marker(dc, screen_rect, inner)

        self._draw_pixel_rulers(dc, screen_rect, surface)

        dc.SetTextForeground(wx.Colour(60, 60, 60))
        dc.DrawLabel(
            f"Screen {surface.width}×{surface.height}px / 屏幕",
            wx.Rect(screen_rect.x + 4, screen_rect.y + 4, screen_rect.width - 8, 16),
            wx.ALIGN_LEFT)
        dc.DrawLabel(
            "Center zone / 中心区",
            wx.Rect(inner.x + 4, inner.y + 4, inner.width - 8, 16),
            wx.ALIGN_LEFT)

    def on_left_down(self, event: wx.MouseEvent):
        mode = self._hit_test(event.GetPosition())
        if mode is None:
            return
        self._drag_mode = mode
        self._hover_mode = mode
        if mode.startswith("resize"):
            self._resize_fixed_edges = self._zone_norm_edges()
        else:
            self._resize_fixed_edges = None
        self._drag_anchor_norm = self._panel_to_norm(event.GetX(), event.GetY())
        self.CaptureMouse()
        self.Refresh(False)

    def on_left_up(self, event: wx.MouseEvent):
        if self._drag_mode is not None and self.HasCapture():
            self.ReleaseMouse()
        was_resize = self._drag_mode is not None and self._drag_mode.startswith("resize")
        self._drag_mode = None
        self._resize_fixed_edges = None
        if was_resize:
            self._zone = self._zone.clamped_to_surface()
            self._emit_zone_changed()
        self._update_hover_feedback(event.GetPosition())

    def on_leave_window(self, event: wx.MouseEvent):
        if self._drag_mode is not None and self.HasCapture():
            self.ReleaseMouse()
            self._drag_mode = None
            self._resize_fixed_edges = None
        if self._hover_mode is not None:
            self._hover_mode = None
            self.Refresh(False)
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))

    def on_motion(self, event: wx.MouseEvent):
        pos = event.GetPosition()
        if self._drag_mode is None:
            self._update_hover_feedback(pos)
            return

        nx, ny = self._panel_to_norm(pos.x, pos.y)

        if self._drag_mode == "move":
            zone = self._zone.clamped_to_surface()
            anchor_nx, anchor_ny = self._drag_anchor_norm
            delta_nx = nx - anchor_nx
            delta_ny = ny - anchor_ny
            zone.center_nx = clamp(zone.center_nx + delta_nx, -1.0, 1.0)
            zone.center_ny = clamp(zone.center_ny + delta_ny, -1.0, 1.0)
            self._zone = zone.clamped_to_surface()
            self._drag_anchor_norm = (nx, ny)
        else:
            self._apply_resize_drag(nx, ny)

        self._emit_zone_changed()
