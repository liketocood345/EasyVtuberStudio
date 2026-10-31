"""Import/path-only runtime verification; never opens camera, UI or a trainer."""
import argparse
import importlib
import json
import os
import site
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--mode', required=True, choices=['student', 'face', 'tha3'])
    parser.add_argument('--report', type=Path)
    parser.add_argument('--configure-sources', action='store_true')
    parser.add_argument('--require-models', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    paths = {name: str(Path(value).resolve()) for name, value in
             [('executable', sys.executable), ('prefix', sys.prefix), ('base_prefix', sys.base_prefix)]}
    assert all(Path(value).is_relative_to(root) for value in paths.values()), paths
    assert not site.ENABLE_USER_SITE
    if args.configure_sources:
        # Fresh ZIPs may ship tha3_src without the developer checkout's junction.
        # A relative namespace shim works without administrator rights and moves
        # together with the portable folder.
        alias = root / 'deps/tha3/tha3'
        if args.mode == 'tha3' and not (alias / '__init__.py').is_file():
            assert alias.resolve().is_relative_to(root)
            assert (root / 'deps/tha3/tha3_src/__init__.py').is_file()
            alias.mkdir(parents=True, exist_ok=True)
            (alias / '__init__.py').write_text(
                'from pathlib import Path\n__path__ = [str(Path(__file__).resolve().parent.parent / "tha3_src")]\n', 'utf-8')
        destination = next(Path(p) for p in site.getsitepackages() if Path(p).name == 'site-packages')
        assert destination.resolve().is_relative_to(root)
        sources = [root / 'src', root / 'deps/tha3',
                   root / 'face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview']
        (destination / 'easyvtuberstudio_sources.pth').write_text(
            '\n'.join(os.path.relpath(p, destination) for p in sources if p.is_dir()) + '\n', 'utf-8')
        return
    from portable_process_env import local_environment
    for key in ('PYTHONHOME', 'PYTHONPATH', 'PIP_TARGET', 'PIP_PREFIX', 'PIP_USER'):
        os.environ.pop(key, None)
    os.environ.update(local_environment(root))
    names = ['torch', 'torchvision', 'wx', 'cv2', 'numpy', 'scipy', 'PIL',
             'matplotlib', 'omegaconf', 'einops', 'tha4.charmodel.character_model']
    if args.mode != 'student':
        names += ['mediapipe']
    if args.mode == 'tha3':
        names += ['onnxruntime', 'tha3.poser.modes.load_poser', 'tha3_engine']
    modules = {}
    for name in names:
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(root), (name, str(path))
        modules[name] = str(path)
    variants = {}
    if args.mode == 'tha3':
        from tha3_paths import THA3_VARIANT_CHOICES, pytorch_model_dir
        for variant, _ in THA3_VARIANT_CHOICES:
            directory = pytorch_model_dir(variant)
            assert directory.resolve().is_relative_to(root)
            variants[variant] = str(directory)
            if args.require_models:
                for name in ['editor.pt', 'eyebrow_decomposer.pt', 'eyebrow_morphing_combiner.pt',
                             'face_morpher.pt', 'two_algo_face_body_rotator.pt']:
                    assert (directory / name).is_file() and (directory / name).stat().st_size > 1024, (variant, name)
        import onnxruntime
        assert 'DmlExecutionProvider' in onnxruntime.get_available_providers()
    result = dict(ok=True, mode=args.mode, paths=paths, modules=modules, variants=variants,
                  caches={key: os.environ[key] for key in ['TEMP', 'MPLCONFIGDIR', 'HF_HOME']})
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
