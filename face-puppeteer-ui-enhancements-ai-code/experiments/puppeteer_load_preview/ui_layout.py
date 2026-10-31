"""Measured wx layout diagnostics and overflow handling (design f-074)."""
from pathlib import Path
import json
import wx
from wx.lib.wordwrap import wordwrap


class PreviewScrollLayout:
    """Only the preview/camera/calibration pane; never resizes other columns."""
    def __init__(self, frame):
        self.frame = frame
        self.scroll = frame.capture_panel
        self.pending = None
        self.busy = False
        self.scroll.SetScrollRate(0, 12)
        self.scroll.EnableScrolling(False, True)
        self.scroll.ShowScrollbars(wx.SHOW_SB_NEVER, wx.SHOW_SB_DEFAULT)
        for window in (self.scroll, frame.preview_input_splitter,
                       frame.source_preview_column, frame.webcam_container,
                       frame.preview_calibration_column, frame.fps_text,
                       frame.ui_change_history_text):
            window.Bind(wx.EVT_SIZE, self.on_size)
        frame.bind_mousewheel_scroll_recursive(self.scroll)
        self.request()

    def on_size(self, event):
        event.Skip()
        if not self.busy:
            self.request()

    def request(self):
        if self.pending is None and not self.frame._is_closing:
            self.pending = wx.CallLater(80, self.refresh)

    def _wrap(self, window):
        # Keep the unwrapped bilingual label so expanding restores its original
        # line breaks. Measure with the actual widget font, not character count.
        for child in window.GetChildren():
            if isinstance(child, (wx.StaticText, wx.CheckBox, wx.Button)):
                original = getattr(child, '_preview_original_label', None)
                if original is None:
                    original = child.GetLabel()
                    child._preview_original_label = original
                # FPS/history are live labels: keep their latest values.
                if child in (self.frame.fps_text, self.frame.ui_change_history_text):
                    original = child.GetLabel()
                available = max(40, child.GetParent().GetClientSize().x - 12)
                if isinstance(child, wx.CheckBox):
                    available -= 24
                elif isinstance(child, wx.Button):
                    available -= 20
                dc = wx.ClientDC(child)
                dc.SetFont(child.GetFont())
                wrapped = wordwrap(original, available, dc, breakLongWords=True)
                if child.GetLabel() != wrapped:
                    child.SetLabel(wrapped)
                    child.InvalidateBestSize()
            self._wrap(child)
        window.InvalidateBestSize()
        window.Layout()

    def refresh(self):
        self.pending = None
        if self.busy or self.frame._is_closing or not self.scroll:
            return
        self.busy = True
        try:
            frame = self.frame
            self.scroll.Layout()
            self._wrap(self.scroll)
            # wx.SplitterWindow's best height doesn't include both children's
            # current text/sizer height. Explicitly retain the source + FPS and
            # live camera + history minimum before calculating virtual height.
            height = max(frame.source_preview_column.GetSizer().GetMinSize().y,
                         frame.webcam_container.GetSizer().GetMinSize().y)
            splitter = frame.preview_input_splitter
            splitter.SetMinSize((splitter.GetMinSize().x, height + 4))
            frame.capture_panel_sizer.Layout()
            required = frame.capture_panel_sizer.GetMinSize().y
            client = self.scroll.GetClientSize()
            self.scroll.SetVirtualSize((client.x, max(client.y, required)))
            self.scroll.Layout()
        finally:
            self.busy = False


def measure_layout(frame, output):
    """Read actual widgets/font metrics on the UI thread, including hidden items."""
    aliases = {id(value): key for key, value in vars(frame).items() if isinstance(value, wx.Window)}
    rows = []
    def walk(window, path, scroll_ancestor=None):
        name = aliases.get(id(window), window.GetName())
        path = path + '/' + name
        size, client, best = window.GetSize(), window.GetClientSize(), window.GetBestSize()
        pos = window.GetPosition()
        shown = window.IsShownOnScreen()
        row = dict(path=path, alias=aliases.get(id(window)), type=type(window).__name__,
                   shown=shown, size=list(size), client=list(client), best=list(best),
                   position=list(pos), scroll_ancestor=scroll_ancestor)
        sizer = window.GetSizer()
        if sizer is not None:
            row['sizer_min'] = list(sizer.GetMinSize())
        if isinstance(window, wx.ScrolledWindow):
            row.update(virtual=list(window.GetVirtualSize()), view=list(window.GetViewStart()),
                       scroll_pixels=list(window.GetScrollPixelsPerUnit()))
            scroll_ancestor = path
        if isinstance(window, (wx.StaticText, wx.CheckBox, wx.Button, wx.RadioButton)):
            label = window.GetLabelText()
            row['text'] = label
            extents = [window.GetTextExtent(line) for line in label.split('\n')]
            row['text_extent'] = [max((e[0] for e in extents), default=0), sum(e[1] for e in extents)]
            row['text_clipped'] = (row['text_extent'][0] > client.x + 2 or row['text_extent'][1] > client.y + 2)
        if isinstance(window, wx.Choice):
            row['choice_extents'] = [[text, *window.GetTextExtent(text)] for text in window.GetStrings()]
        parent = window.GetParent()
        if parent is not None and not isinstance(window, wx.TopLevelWindow):
            width, height = parent.GetClientSize()
            if isinstance(parent, wx.ScrolledWindow):
                width, height = parent.GetVirtualSize()
                x, y = parent.CalcUnscrolledPosition(pos)
            else:
                x, y = pos
            row['outside_parent'] = x < -2 or y < -2 or x + size.x > width + 2 or y + size.y > height + 2
        rows.append(row)
        for index, child in enumerate(window.GetChildren()):
            if not isinstance(child, wx.TopLevelWindow):
                walk(child, path + f'/{index}', scroll_ancestor)
    for top in wx.GetTopLevelWindows():
        if top.IsShown():
            walk(top, '')
    result = dict(ok=True, windows=rows, count=len(rows),
                  visible_count=sum(r['shown'] for r in rows),
                  text_clips=[r for r in rows if r['shown'] and r.get('text_clipped')],
                  outside=[r for r in rows if r['shown'] and r.get('outside_parent')])
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
    return dict(ok=True, output=str(path), count=result['count'], visible_count=result['visible_count'],
                text_clips=len(result['text_clips']), outside=len(result['outside']))
