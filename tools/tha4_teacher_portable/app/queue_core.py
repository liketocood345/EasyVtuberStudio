"""Persistent queue and original THA4 material/config rules, independent of wx."""
import ast
import json
import shutil
import uuid
from pathlib import Path
from PIL import Image
from portable import ROOT, PROJECT_ROOT, WORKSPACE_ROOT, atomic_json


def original_defaults():
    source = ROOT / 'src/tha4/distiller/distiller_config.py'
    tree = ast.parse(source.read_text('utf-8'))
    config = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DistillerConfig')
    return {n.target.id: ast.literal_eval(n.value) for n in config.body
            if isinstance(n, ast.AnnAssign) and n.value is not None}


def classify_materials(paths):
    if len(paths) != 2:
        raise ValueError('每个任务需要两张 PNG：透明角色图和 RGB 五官遮罩。')
    character, mask = [], []
    for path in map(Path, paths):
        if path.suffix.lower() != '.png':
            raise ValueError('请使用 PNG；角色图和遮罩都必须为 512×512。')
        with Image.open(path) as image:
            image.load()
            if image.size != (512, 512):
                raise ValueError(f'{path.name} 不是 512×512。请按上游规范准备，程序不会偷偷缩放素材。')
            if image.mode == 'RGBA':
                character.append(path)
            elif image.mode == 'RGB':
                # Upstream documentation asks for a black/white RGB mask.
                if any(value not in (0, 255) for value in image.tobytes()):
                    raise ValueError(f'{path.name}：RGB 遮罩的各通道只能为 0 或 255。')
                if any(r != g or g != b for r, g, b in image.getdata()):
                    raise ValueError(f'{path.name}：五官遮罩须使用黑白 RGB 图片，不能使用彩色遮罩。')
                mask.append(path)
    if len(character) != 1 or len(mask) != 1:
        raise ValueError('需要一张 RGBA 角色图与一张 RGB 五官遮罩；请查看素材要求。')
    return character[0], mask[0]


class QueueStore:
    def __init__(self, root=None):
        self.root = Path(root).resolve() if root is not None else PROJECT_ROOT
        self.workspace = self.root / 'workspace' if root is not None else WORKSPACE_ROOT
        self.path = self.workspace / 'queue.json'
        data = json.loads(self.path.read_text('utf-8')) if self.path.exists() else {}
        self.jobs = data.get('jobs', [])
        self.settings = data.get('settings', original_defaults())
        for job in self.jobs:
            if not (self.root / job['directory']).resolve().is_relative_to(self.root.resolve()):
                raise ValueError('Queue task path escapes the trainer directory')
            progress = self.read_progress(job)
            model = self.root / job['directory'] / 'output/character_model'
            if progress.get('state') == 'completed' and all((model / name).is_file() for name in
                    ['character_model.yaml', 'character.png', 'face_morpher.pt', 'body_morpher.pt']):
                job['state'] = 'completed'
            if job['state'] in ('running', 'saving'):
                job['state'] = 'paused'
        self.save()

    def save(self):
        atomic_json(self.path, dict(schema=1, jobs=self.jobs, settings=self.settings))

    def add(self, paths):
        character, mask = classify_materials(paths)
        key = uuid.uuid4().hex
        directory = self.workspace / 'jobs' / key
        inputs = directory / 'inputs'
        inputs.mkdir(parents=True)
        shutil.copyfile(character, inputs / 'character.png')
        shutil.copyfile(mask, inputs / 'face_mask.png')
        settings = dict(self.settings)
        atomic_json(directory / 'settings.json', settings)
        job = dict(id=key, name=character.stem, state='queued',
                   directory=directory.relative_to(self.root).as_posix(),
                   original_materials=[str(character.resolve()), str(mask.resolve())], progress={})
        self.jobs.append(job)
        self.save()
        return job

    def remove(self, key):
        # Removing a queue entry preserves original user files and saved output.
        self.jobs = [job for job in self.jobs if job['id'] != key]
        self.save()

    def move(self, key, index):
        job = next(job for job in self.jobs if job['id'] == key)
        self.jobs.remove(job)
        self.jobs.insert(max(0, min(len(self.jobs), index)), job)
        self.save()

    def read_progress(self, job):
        path = self.root / job['directory'] / 'progress.json'
        try:
            return json.loads(path.read_text('utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):
            return job.get('progress', {})
