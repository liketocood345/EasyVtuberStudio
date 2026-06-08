"""Dialog to pick a normalized swing pivot on a layer asset image."""
from __future__ import annotations

from typing import Callable, Optional

import wx

from layer_runtime import (
    DEFAULT_SWING_PIVOT_U,
    DEFAULT_SWING_PIVOT_V,
    BasicLayerSlot,
    clamp_swing_pivot_u,
    clamp_swing_pivot_v,
)


class _PivotCanvasPanel(wx.Panel):
    def __init__(
            self,
            parent: wx.Window,
            image: wx.Image,
            pivot_u: float,
            pivot_v: float,
            *,
            on_pivot_changed: Optional[Callable[[], None]] = None):
        super().__init__(parent, style=wx.BORDER_SUNKEN)
        self._on_pivot_changed = on_pivot_changed
        self._source_image = image
        self._pivot_u = clamp_swing_pivot_u(pivot_u)
        self._pivot_v = clamp_swing_pivot_v(pivot_v)
        self._display_bitmap: Optional[wx.Bitmap] = None
        self._display_size = wx.Size(1, 1)
        self._scale = 1.0
        self._offset_x = 0
        self._offset_y = 0
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
        self.Bind(wx.EVT_SIZE, self._on_size)
        wx.CallAfter(self._rebuild_display_bitmap)

    def get_pivot(self) -> tuple[float, float]:
        return self._pivot_u, self._pivot_v

    def _on_size(self, event: wx.SizeEvent) -> None:
        self._rebuild_display_bitmap()
        event.Skip()

    def _rebuild_display_bitmap(self) -> None:
        client = self.GetClientSize()
        if client.x <= 0 or client.y <= 0:
            return
        src_w = max(1, self._source_image.GetWidth())
        src_h = max(1, self._source_image.GetHeight())
        scale = min(client.x / src_w, client.y / src_h)
        draw_w = max(1, int(round(src_w * scale)))
        draw_h = max(1, int(round(src_h * scale)))
        scaled = self._source_image.Scale(
            draw_w, draw_h, wx.IMAGE_QUALITY_HIGH)
        self._display_bitmap = scaled.ConvertToBitmap()
        self._display_size = wx.Size(draw_w, draw_h)
        self._scale = scale
        self._offset_x = (client.x - draw_w) // 2
        self._offset_y = (client.y - draw_h) // 2
        self.Refresh(False)

    def _image_point_from_client(self, x: int, y: int) -> Optional[tuple[float, float]]:
        if self._display_bitmap is None or not self._display_bitmap.IsOk():
            return None
        local_x = x - self._offset_x
        local_y = y - self._offset_y
        if local_x < 0 or local_y < 0:
            return None
        if local_x >= self._display_size.x or local_y >= self._display_size.y:
            return None
        pivot_u = local_x / max(1, self._display_size.x)
        pivot_v = local_y / max(1, self._display_size.y)
        return clamp_swing_pivot_u(pivot_u), clamp_swing_pivot_v(pivot_v)

    def _on_left_down(self, event: wx.MouseEvent) -> None:
        point = self._image_point_from_client(event.GetX(), event.GetY())
        if point is None:
            return
        self._pivot_u, self._pivot_v = point
        self.Refresh(False)
        if self._on_pivot_changed is not None:
            self._on_pivot_changed()

    def _on_paint(self, event: wx.PaintEvent) -> None:
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(wx.Colour(40, 40, 40)))
        dc.Clear()
        if self._display_bitmap is None or not self._display_bitmap.IsOk():
            return
        dc.DrawBitmap(
            self._display_bitmap,
            self._offset_x,
            self._offset_y,
            True)
        px = self._offset_x + int(round(self._pivot_u * self._display_size.x))
        py = self._offset_y + int(round(self._pivot_v * self._display_size.y))
        pen = wx.Pen(wx.Colour(255, 210, 0), 2)
        dc.SetPen(pen)
        dc.DrawLine(px - 12, py, px + 12, py)
        dc.DrawLine(px, py - 12, px, py + 12)
        dc.SetBrush(wx.Brush(wx.Colour(255, 210, 0)))
        dc.DrawCircle(px, py, 4)


class SwingPivotEditDialog(wx.Dialog):
    def __init__(
            self,
            parent: wx.Window,
            layer: BasicLayerSlot,
            image: wx.Image):
        super().__init__(
            parent,
            title="编辑摇摆点 / Edit swing pivot",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._layer = layer
        root = wx.BoxSizer(wx.VERTICAL)
        help_text = wx.StaticText(
            self,
            label=(
                "在素材图上单击设置摇摆支点（归一化坐标会保存）。"
                " / Click the asset to set the swing pivot."))
        help_text.Wrap(480)
        root.Add(help_text, 0, wx.ALL | wx.EXPAND, 8)

        self.canvas = _PivotCanvasPanel(
            self,
            image,
            layer.swing_pivot_u,
            layer.swing_pivot_v,
            on_pivot_changed=self._update_coord_label)
        self.canvas.SetMinSize((320, 320))
        root.Add(self.canvas, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)

        self.coord_text = wx.StaticText(self, label="")
        root.Add(self.coord_text, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self._update_coord_label()

        btn_row = self.CreateButtonSizer(wx.OK | wx.CANCEL)
        root.Add(btn_row, 0, wx.ALIGN_RIGHT | wx.ALL, 8)
        self.SetSizer(root)
        self.SetMinSize((420, 480))
        self.Fit()

    def _update_coord_label(self) -> None:
        pivot_u, pivot_v = self.canvas.get_pivot()
        self.coord_text.SetLabel(
            f"支点 / Pivot: u={pivot_u:.3f}, v={pivot_v:.3f}"
            f"  (默认底边中点 / default bottom-center: {DEFAULT_SWING_PIVOT_U:.1f}, {DEFAULT_SWING_PIVOT_V:.1f})")

    def apply_to_layer(self) -> None:
        pivot_u, pivot_v = self.canvas.get_pivot()
        self._layer.swing_pivot_u = pivot_u
        self._layer.swing_pivot_v = pivot_v


def show_swing_pivot_edit_dialog(
        parent: wx.Window,
        layer: BasicLayerSlot,
        image: wx.Image) -> bool:
    dialog = SwingPivotEditDialog(parent, layer, image)
    if dialog.ShowModal() != wx.ID_OK:
        dialog.Destroy()
        return False
    dialog.apply_to_layer()
    dialog.Destroy()
    return True
