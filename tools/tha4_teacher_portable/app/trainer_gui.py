"""Standalone THA4 teacher queue UI; no dependency on EasyVtuberStudio.exe."""
import json
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from portable import ROOT, PROJECT_ROOT, WORKSPACE_ROOT, environment, python_exe, atomic_json

os.environ.update(environment())
import wx
from PIL import Image
from queue_core import QueueStore, original_defaults

GUIDE = 'https://github.com/pkhungurn/talking-head-anime-4-demo#contraints-on-input-images'
EMPTY = '拖入两张所需图片素材来开始训练\n如果要准备图片素材请详细阅读 GitHub 网页要求'
STATE = dict(queued='未开始', running='未完成 · 训练中', saving='未完成 · 正在保存',
             paused='未完成 · 已保存/可继续', failed='未完成 · 出错', completed='已完成')


def duration(seconds):
    if seconds is None:
        return '估算中'
    seconds = max(0, int(seconds))
    return f'{seconds//3600}小时 {(seconds%3600)//60}分 {seconds%60}秒'


class MaterialsDrop(wx.FileDropTarget):
    def __init__(self, frame):
        super().__init__()
        self.frame = frame
    def OnDropFiles(self, x, y, filenames):
        wx.CallAfter(self.frame.add_materials, filenames)
        return True


class SettingsDialog(wx.Dialog):
    def __init__(self, parent, values):
        super().__init__(parent, title='THA4 原项目训练设置 · 对新加入的任务生效', size=(650, 640))
        scroll = wx.ScrolledWindow(self, style=wx.VSCROLL)
        scroll.SetScrollRate(0, 16)
        form = wx.FlexGridSizer(cols=2, vgap=10, hgap=10)
        form.AddGrowableCol(1)
        self.fields = {}
        for name, default in original_defaults().items():
            form.Add(wx.StaticText(scroll, label=name), 0, wx.ALIGN_CENTER_VERTICAL)
            ctrl = wx.TextCtrl(scroll, value=str(values.get(name, default)))
            ctrl.SetToolTip('沿用 DistillerConfig；None 表示不输出训练示例图。随机种子、批量、GPU 与 CPU worker 数均为原项目选项。')
            form.Add(ctrl, 1, wx.EXPAND)
            self.fields[name] = ctrl
        scroll.SetSizer(form)
        scroll.FitInside()
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(scroll, 1, wx.EXPAND | wx.ALL, 16)
        outer.Add(self.CreateButtonSizer(wx.OK | wx.CANCEL), 0, wx.EXPAND | wx.ALL, 12)
        self.SetSizer(outer)
    def values(self):
        values = {}
        for name, control in self.fields.items():
            raw = control.GetValue().strip()
            value = None if raw.lower() == 'none' else int(raw)
            if 'batch_size' in name and not 1 <= value <= 8:
                raise ValueError('上游 batch_size 范围为 1–8。')
            if 'random_seed' in name and not 0 <= value <= 2**64-1:
                raise ValueError('随机种子必须在 0..2**64-1。')
            if name in ('num_cpu_workers', 'num_gpus') and (value is None or value < 1):
                raise ValueError('GPU 和 CPU worker 数必须至少为 1。')
            if 'per_sample_output' in name and value not in (None, 10000, 100000, 1000000):
                raise ValueError('示例输出间隔为 10000、100000、1000000 或 None。')
            values[name] = value
        return values


class TaskRow(wx.Panel):
    def __init__(self, owner, parent, job):
        super().__init__(parent, style=wx.BORDER_SIMPLE)
        self.owner, self.job = owner, job
        self.SetBackgroundColour('#F7F8FA')
        layout = wx.BoxSizer(wx.HORIZONTAL)
        for filename, caption in [('character.png', '角色'), ('face_mask.png', '五官遮罩')]:
            column = wx.BoxSizer(wx.VERTICAL)
            path = PROJECT_ROOT / job['directory'] / 'inputs' / filename
            with Image.open(path) as image:
                image = image.convert('RGBA')
                image.thumbnail((72, 72))
                bitmap = wx.Bitmap.FromBufferRGBA(image.width, image.height, image.tobytes())
            thumb = wx.StaticBitmap(self, bitmap=bitmap)
            thumb.SetToolTip(str(path))
            column.Add(thumb, 0, wx.ALIGN_CENTER)
            column.Add(wx.StaticText(self, label=caption), 0, wx.ALIGN_CENTER | wx.TOP, 3)
            layout.Add(column, 0, wx.ALL, 8)
        info = wx.BoxSizer(wx.VERTICAL)
        self.title = wx.StaticText(self, label='⋮⋮  ' + job['name'], style=wx.ST_ELLIPSIZE_END)
        font = self.title.GetFont()
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.title.SetFont(font)
        self.title.SetToolTip('拖动此处调整人物顺序；当前训练任务保持运行，待开始任务按新顺序执行。')
        info.Add(self.title, 0, wx.EXPAND | wx.BOTTOM, 5)
        self.status = wx.StaticText(self)
        info.Add(self.status, 0, wx.EXPAND)
        self.gauge = wx.Gauge(self, range=1000)
        info.Add(self.gauge, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 5)
        self.material_path = wx.StaticText(self, label='文件材料位置：' + str(PROJECT_ROOT / job['directory'] / 'inputs'),
                                           style=wx.ST_ELLIPSIZE_MIDDLE)
        self.material_path.SetToolTip(str(PROJECT_ROOT / job['directory']))
        info.Add(self.material_path, 0, wx.EXPAND)
        layout.Add(info, 1, wx.EXPAND | wx.ALL, 10)
        buttons = wx.BoxSizer(wx.VERTICAL)
        for label, action in [('继续/重试', lambda event: owner.resume_job(job)),
                              ('材料/结果', lambda event: os.startfile(str(PROJECT_ROOT / job['directory']))),
                              ('移除', lambda event: owner.remove_job(job))]:
            button = wx.Button(self, label=label)
            button.Bind(wx.EVT_BUTTON, action)
            buttons.Add(button, 0, wx.EXPAND | wx.BOTTOM, 3)
        layout.Add(buttons, 0, wx.ALL, 8)
        self.SetSizer(layout)
        self.down = None
        for control in (self, self.title):
            control.Bind(wx.EVT_LEFT_DOWN, self.begin_drag)
            control.Bind(wx.EVT_MOTION, self.drag)
            control.Bind(wx.EVT_LEFT_UP, self.end_drag)
        self.update()
    def begin_drag(self, event):
        self.down = wx.GetMousePosition()
        self.CaptureMouse()
    def drag(self, event):
        if self.down is not None and event.Dragging():
            self.SetCursor(wx.Cursor(wx.CURSOR_SIZENS))
    def end_drag(self, event):
        if self.HasCapture(): self.ReleaseMouse()
        self.SetCursor(wx.NullCursor)
        start, self.down = self.down, None
        if start is None or abs(wx.GetMousePosition().y-start.y) < 6:
            return
        index = sum(wx.GetMousePosition().y > row.GetScreenRect().y + row.GetSize().y//2
                    for row in self.owner.rows if row is not self)
        self.owner.store.move(self.job['id'], index)
        wx.CallAfter(self.owner.rebuild)
    def update(self):
        job = self.job
        progress = self.owner.store.read_progress(job)
        fraction = min(1., max(0., float(progress.get('overall', 0))))
        state = job['state']
        message = STATE[state]
        if state in ('running', 'saving', 'paused', 'failed'):
            message += f"  {fraction*100:.2f}%"
            if progress.get('phase') in ('face', 'body'):
                message += '  ' + ('面部' if progress['phase']=='face' else '身体')
                message += '阶段剩余：' + duration(progress.get('phase_eta_seconds'))
        if state == 'failed': message += '  ' + str(progress.get('error', '查看任务目录内 training.log'))[:160]
        self.status.SetLabel(message)
        self.status.Wrap(max(120, self.status.GetParent().GetClientSize().x - 310))
        self.status.SetForegroundColour('#228044' if state=='completed' else '#333333')
        self.gauge.SetValue(1000 if state=='completed' else int(fraction*1000))
        self.Layout()


class TrainerFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title='THA4 教师 · 便携训练队列', size=(1120, 720))
        self.SetMinSize((850, 480))
        self.store = QueueStore()
        self.process = None
        self.active = None
        self.remove_after_stop = None
        self.closing = False
        self.autorun = '--smoke-ui' not in sys.argv and not any(job['state']=='paused' for job in self.store.jobs)
        self.pending_materials = []
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        toolbar = wx.BoxSizer(wx.HORIZONTAL)
        for label, action in [('继续队列/上次训练', self.resume_all), ('暂停并保存', self.pause),
                              ('训练设置（原项目）', self.settings), ('GitHub 素材要求', lambda event: webbrowser.open(GUIDE))]:
            button = wx.Button(panel, label=label)
            button.Bind(wx.EVT_BUTTON, action)
            toolbar.Add(button, 0, wx.RIGHT, 8)
        outer.Add(toolbar, 0, wx.EXPAND | wx.ALL, 12)
        self.message = wx.StaticText(panel, label='拖入一组角色 PNG 与五官遮罩 PNG；校验通过后自动训练。')
        outer.Add(self.message, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 12)
        self.scroll = wx.ScrolledWindow(panel, style=wx.VSCROLL)
        self.scroll.SetScrollRate(0, 16)
        self.list_sizer = wx.BoxSizer(wx.VERTICAL)
        self.scroll.SetSizer(self.list_sizer)
        outer.Add(self.scroll, 1, wx.EXPAND | wx.ALL, 12)
        panel.SetSizer(outer)
        for target in (panel, self.scroll): target.SetDropTarget(MaterialsDrop(self))
        self.Bind(wx.EVT_CLOSE, self.on_close)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.poll, self.timer)
        self.timer.Start(700)
        self.rebuild()
    def rebuild(self):
        self.list_sizer.Clear(delete_windows=True)
        self.rows = []
        if not self.store.jobs:
            label = wx.StaticText(self.scroll, label=EMPTY, style=wx.ALIGN_CENTER)
            label.SetForegroundColour('#888888')
            self.list_sizer.AddStretchSpacer()
            self.list_sizer.Add(label, 0, wx.ALIGN_CENTER | wx.ALL, 32)
            self.list_sizer.AddStretchSpacer()
        for job in self.store.jobs:
            row = TaskRow(self, self.scroll, job)
            row.SetDropTarget(MaterialsDrop(self))
            self.rows.append(row)
            self.list_sizer.Add(row, 0, wx.EXPAND | wx.BOTTOM, 8)
        self.scroll.Layout()
        self.scroll.FitInside()
    def add_materials(self, paths):
        self.pending_materials.extend(paths)
        if len(self.pending_materials) == 1:
            self.message.SetLabel('已收到 1 张素材，请继续拖入另一张角色图/五官遮罩。')
            return
        paths, self.pending_materials = self.pending_materials, []
        try:
            self.store.add(paths)
            self.autorun = True
            self.message.SetLabel('素材已校验并复制到训练器目录。队列自动开始；拖动人物名称调整顺序。')
            self.rebuild()
        except Exception as exc:
            wx.MessageBox(str(exc), '素材检查', wx.OK | wx.ICON_WARNING, self)
    def settings(self, event):
        dialog = SettingsDialog(self, self.store.settings)
        try:
            if dialog.ShowModal() == wx.ID_OK:
                self.store.settings = dialog.values()
                self.store.save()
        except Exception as exc:
            wx.MessageBox(str(exc), '设置无效', wx.OK | wx.ICON_WARNING, self)
        finally:
            dialog.Destroy()
    def resume_all(self, event):
        for job in self.store.jobs:
            if job['state'] == 'paused': job['state'] = 'queued'
        self.autorun = True
        self.store.save()
    def resume_job(self, job):
        if job is self.active or job['state']=='completed': return
        job['state'] = 'queued'
        self.autorun = True
        self.store.save()
    def pause(self, event=None):
        self.autorun = False
        if self.active:
            (PROJECT_ROOT / self.active['directory'] / 'stop.request').touch()
            self.message.SetLabel('正在等待当前训练步结束并保存。重开或点击继续可从完整保存点恢复。')
    def remove_job(self, job):
        if job is self.active:
            self.remove_after_stop = job['id']
            self.pause()
        else:
            self.store.remove(job['id'])
            self.rebuild()
    def start_job(self, job):
        directory = PROJECT_ROOT / job['directory']
        (directory / 'stop.request').unlink(missing_ok=True)
        settings = json.loads((directory / 'settings.json').read_text('utf-8'))
        command = [str(python_exe()), '-u', '-m', 'torch.distributed.run', '--standalone',
                   '--nnodes=1', '--nproc_per_node='+str(settings['num_gpus']),
                   str(ROOT / 'app/worker.py'), '--job', str(directory)]
        self.log = (directory / 'training.log').open('a', encoding='utf-8')
        self.process = subprocess.Popen(command, cwd=ROOT, env=environment(), stdout=self.log, stderr=subprocess.STDOUT,
                                        creationflags=subprocess.CREATE_NO_WINDOW)
        self.active = job
        job['state'] = 'running'
        self.store.save()
    def poll(self, event=None):
        if self.process is not None:
            progress = self.store.read_progress(self.active)
            if progress.get('state') in ('running','saving'): self.active['state'] = progress['state']
            if self.process.poll() is not None:
                self.log.close()
                completed = self.process.returncode == 0 and progress.get('state') == 'completed'
                self.active['state'] = 'completed' if completed else ('paused' if progress.get('state')=='paused' else 'failed')
                self.active['progress'] = progress
                self.process = None
                self.active = None
                if self.remove_after_stop:
                    self.store.remove(self.remove_after_stop)
                    self.remove_after_stop = None
                    self.rebuild()
                self.store.save()
        if self.closing and self.process is None:
            self.timer.Stop()
            self.Destroy()
            return
        if self.autorun and self.process is None and not self.closing:
            job = next((job for job in self.store.jobs if job['state']=='queued'), None)
            if job is not None: self.start_job(job)
        for row in self.rows: row.update()
        self.scroll.Layout()
        self.scroll.FitInside()
    def on_close(self, event):
        if self.process is not None:
            self.closing = True
            self.pause()
            if event.CanVeto(): event.Veto()
        else:
            self.timer.Stop()
            event.Skip()


def main():
    import ctypes
    import hashlib
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, 'Local\\THA4Teacher-'+hashlib.sha256(str(ROOT).encode()).hexdigest()[:20])
    if ctypes.windll.kernel32.GetLastError() == 183:
        return
    app = wx.App(False)
    frame = TrainerFrame()
    def initial_layout():
        frame.Layout()
        for row in frame.rows:
            row.update()
        frame.scroll.Layout()
        frame.scroll.FitInside()
    wx.CallAfter(initial_layout)
    if '--smoke-ui' in sys.argv:
        frame.timer.Stop()
        frame.autorun = False
        def capture_and_close():
            client = frame.GetClientSize()
            bitmap = wx.Bitmap(client.x, client.y)
            dc = wx.MemoryDC(bitmap)
            dc.Blit(0, 0, client.x, client.y, wx.ClientDC(frame), 0, 0)
            dc.SelectObject(wx.NullBitmap)
            bitmap.SaveFile(str(WORKSPACE_ROOT / 'gui_smoke.png'), wx.BITMAP_TYPE_PNG)
            atomic_json(WORKSPACE_ROOT / 'gui_probe.json', dict(ok=True, client=list(client),
                        rows=len(frame.rows), empty=not frame.store.jobs))
            frame.Close()
        wx.CallLater(1800, capture_and_close)
    frame.Show()
    app.MainLoop()
    ctypes.windll.kernel32.CloseHandle(mutex)


if __name__ == '__main__':
    main()
