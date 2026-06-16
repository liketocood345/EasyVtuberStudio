"""Download files from a Hugging Face Storage Bucket for portable DEPLOY."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from huggingface_hub import download_bucket_files, list_bucket_tree
from huggingface_hub._buckets import BucketFile


def _normalize_prefix(prefix: str) -> str:
    prefix = prefix.replace("\\", "/").strip("/")
    return prefix


def download_file(bucket_id: str, remote_path: str, local_path: Path) -> None:
    remote_path = remote_path.replace("\\", "/").lstrip("/")
    local_path = Path(local_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    download_bucket_files(
        bucket_id,
        [(remote_path, local_path)],
        raise_on_missing_files=True,
    )
    if not local_path.is_file() or local_path.stat().st_size < 1:
        raise FileNotFoundError(f"Downloaded file missing or empty: {local_path}")


def download_tree(bucket_id: str, remote_prefix: str, local_dir: Path) -> int:
    remote_prefix = _normalize_prefix(remote_prefix)
    local_dir = Path(local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)

    list_prefix = f"{remote_prefix}/" if remote_prefix else None
    files: list[tuple[str, Path]] = []
    for item in list_bucket_tree(bucket_id, prefix=list_prefix, recursive=True):
        if not isinstance(item, BucketFile):
            continue
        rel = item.path
        if remote_prefix:
            prefix_with_slash = f"{remote_prefix}/"
            if not rel.startswith(prefix_with_slash):
                continue
            rel = rel[len(prefix_with_slash) :]
        dest = local_dir / rel.replace("/", "\\")
        files.append((item.path, dest))

    if not files:
        raise FileNotFoundError(
            f"No files under bucket '{bucket_id}' prefix '{remote_prefix or '/'}'"
        )

    download_bucket_files(bucket_id, files, raise_on_missing_files=True)
    return len(files)


def bucket_has_prefix(bucket_id: str, remote_prefix: str) -> bool:
    remote_prefix = _normalize_prefix(remote_prefix)
    list_prefix = f"{remote_prefix}/" if remote_prefix else None
    for item in list_bucket_tree(bucket_id, prefix=list_prefix, recursive=True):
        if isinstance(item, BucketFile):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_file = sub.add_parser("download-file")
    p_file.add_argument("--bucket", required=True)
    p_file.add_argument("--remote", required=True)
    p_file.add_argument("--local", required=True)

    p_tree = sub.add_parser("download-tree")
    p_tree.add_argument("--bucket", required=True)
    p_tree.add_argument("--remote", required=True)
    p_tree.add_argument("--local", required=True)

    p_has = sub.add_parser("has-prefix")
    p_has.add_argument("--bucket", required=True)
    p_has.add_argument("--remote", required=True)

    args = parser.parse_args(argv)

    try:
        if args.command == "download-file":
            download_file(args.bucket, args.remote, Path(args.local))
            print(f"OK file -> {args.local}")
        elif args.command == "download-tree":
            count = download_tree(args.bucket, args.remote, Path(args.local))
            print(f"OK {count} files -> {args.local}")
        elif args.command == "has-prefix":
            ok = bucket_has_prefix(args.bucket, args.remote)
            print("yes" if ok else "no")
            return 0 if ok else 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
