"""Resume large, pinned official wheels in a private portable cache."""
import argparse
import hashlib
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            value.update(block)
    return value.hexdigest()


def fetch(url, directory):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != 'https' or parts.hostname not in ('download.pytorch.org', 'download-r2.pytorch.org'):
        raise ValueError('Only pinned official PyTorch wheels are accepted')
    expected = urllib.parse.parse_qs(parts.fragment).get('sha256', [''])[0]
    if not re.fullmatch('[a-f0-9]{64}', expected):
        raise ValueError('Official wheel SHA256 is required')
    name = Path(urllib.parse.unquote(parts.path)).name
    if not name.endswith('.whl'):
        raise ValueError('Expected a wheel filename')
    target = directory / name
    assert target.resolve().is_relative_to(directory.resolve())
    if target.exists():
        if digest(target) != expected:
            raise ValueError('Existing wheel cache failed SHA256; retained for inspection: ' + name)
        print('Verified cached wheel: ' + name, flush=True)
        return target
    partial = target.with_suffix('.whl.part')
    assert partial.resolve().is_relative_to(directory.resolve())
    total = None
    failures = 0
    last_notice = 0.
    while total is None or partial.stat().st_size < total:
        offset = partial.stat().st_size if partial.exists() else 0
        end = offset + 8 * 2**20 - 1
        if total is not None:
            end = min(end, total - 1)
        request = urllib.request.Request(urllib.parse.urlunsplit(parts._replace(fragment='')),
            headers={'Range': f'bytes={offset}-{end}', 'Accept-Encoding': 'identity',
                     'Cache-Control': 'no-cache', 'User-Agent': 'EasyVtuberStudio-portable-deploy/1'})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                if response.status != 206 or not match or int(match[1]) != offset:
                    raise ValueError('Server did not honor the requested download range')
                received_total = int(match[3])
                if total is not None and received_total != total:
                    raise ValueError('Remote wheel size changed during download')
                total = received_total
                expected_end = int(match[2]) + 1
                with partial.open('ab', buffering=0) as stream:
                    while stream.tell() < expected_end:
                        data = response.read(min(256 * 1024, expected_end - stream.tell()))
                        if not data:
                            raise OSError('Incomplete range response')
                        stream.write(data)
            failures = 0
            if time.monotonic() - last_notice > 5:
                print(f'{name}: {partial.stat().st_size}/{total} bytes', flush=True)
                last_notice = time.monotonic()
        except (OSError, ValueError) as error:
            failures += 1
            if failures >= 5:
                raise RuntimeError('Download paused with partial file retained: ' + name) from error
            print(f'Retrying wheel range; partial retained: {name} ({type(error).__name__})', flush=True)
            time.sleep(min(failures * 2, 8))
    if digest(partial) != expected:
        raise ValueError('Downloaded wheel failed SHA256; partial retained: ' + name)
    partial.replace(target)
    print('Downloaded and verified: ' + name, flush=True)
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--requirements', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    directory = root / 'workspace/asset_downloads/wheels'
    assert directory.resolve().is_relative_to(root)
    assert args.output.resolve().is_relative_to(root)
    directory.mkdir(parents=True, exist_ok=True)
    lines = []
    for line in args.requirements.read_text('utf-8-sig').splitlines():
        match = re.fullmatch(r'([\w-]+)\s*@\s*(https://\S+)', line.strip())
        if match and '.whl#sha256=' in match[2]:
            path = fetch(match[2], directory)
            line = match[1] + ' @ ' + path.resolve().as_uri() + '#' + urllib.parse.urlsplit(match[2]).fragment
        lines.append(line)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text('\n'.join(lines) + '\n', 'utf-8')


if __name__ == '__main__':
    main()
