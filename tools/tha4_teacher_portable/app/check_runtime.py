"""dep-007: verify the standalone folder without training or opening a camera."""
import argparse
import importlib
import json
import os
import site
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--skip-assets', action='store_true')
    args = parser.parse_args()
    component = args.root.resolve()
    sys.path.insert(0, str(component / 'app'))
    from portable import environment, project_root
    root = project_root(component)
    paths = dict(executable=sys.executable, prefix=sys.prefix, base_prefix=sys.base_prefix)
    assert all(Path(p).resolve().is_relative_to(root) for p in paths.values()), paths
    assert not site.ENABLE_USER_SITE
    for key in ('PYTHONHOME', 'PYTHONPATH', 'PIP_TARGET', 'PIP_PREFIX', 'PIP_USER'):
        os.environ.pop(key, None)
    os.environ.update(environment(component))
    sys.path.insert(0, str(component / 'src'))
    modules = {}
    for name in ['torch', 'wx', 'quaternion', 'tensorboard', 'tha4.distiller.distiller_config']:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(root), (name, str(path))
        modules[name] = str(path)
    assets = {}
    if not args.skip_assets:
        for name in ['body_morpher.pt', 'eyebrow_decomposer.pt', 'eyebrow_morphing_combiner.pt',
                     'face_morpher.pt', 'upscaler.pt']:
            path = component / 'data/tha4' / name
            assert path.is_file() and path.stat().st_size > 1024, str(path)
            assets[name] = path.stat().st_size
        path = component / 'data/pose_dataset.pt'
        assert path.is_file() and path.stat().st_size > 1024
        assets['pose_dataset.pt'] = path.stat().st_size
    import torch
    result = dict(ok=True, paths=paths, modules=modules, assets=assets, cuda=torch.cuda.is_available(),
                  caches={key: os.environ[key] for key in ['TEMP', 'MPLCONFIGDIR', 'HF_HOME']})
    if args.report:
        assert args.report.resolve().is_relative_to(root)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
