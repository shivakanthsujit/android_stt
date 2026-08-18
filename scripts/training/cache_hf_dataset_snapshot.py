#!/usr/bin/env python3
"""Seed a canonical Hugging Face dataset snapshot from verified local payloads."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi, hf_hub_download, snapshot_download


def file_digest(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_blob_digest(path: Path) -> str:
    digest = hashlib.sha1()
    digest.update(f"blob {path.stat().st_size}\0".encode("ascii"))
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_blob(path: Path, item: Any) -> str:
    if not path.is_file() or path.is_symlink() or path.stat().st_size != item.size:
        raise RuntimeError(f"source bytes differ for {item.path}")
    if item.lfs is not None:
        key = item.lfs.sha256
        actual = file_digest(path, "sha256")
    else:
        key = item.blob_id
        actual = git_blob_digest(path)
    if actual != key:
        raise RuntimeError(f"source digest differs for {item.path}: {actual} != {key}")
    return key


def link_blob(source: Path, blob: Path, key: str, item: Any) -> None:
    blob.parent.mkdir(parents=True, exist_ok=True)
    if blob.exists():
        verify_blob(blob, item)
        return
    os.link(source, blob)
    verify_blob(blob, item)


def link_snapshot(blob: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    relative = os.path.relpath(blob, destination.parent)
    if destination.is_symlink():
        if os.readlink(destination) != relative:
            raise RuntimeError(f"snapshot link differs: {destination}")
        return
    if destination.exists():
        raise RuntimeError(f"snapshot path is not a symlink: {destination}")
    destination.symlink_to(relative)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    namespace, name = args.repo_id.split("/", 1)
    repo_root = args.cache_dir / f"datasets--{namespace}--{name}"
    snapshot = repo_root / "snapshots" / args.revision
    missing: list[str] = []
    items = [
        item for item in HfApi().list_repo_tree(
            args.repo_id, repo_type="dataset", revision=args.revision,
            recursive=True, expand=True,
        )
        if hasattr(item, "size")
    ]
    for item in items:
        source = args.source_root / item.path
        if not source.exists():
            missing.append(item.path)
            continue
        key = verify_blob(source, item)
        blob = repo_root / "blobs" / key
        link_blob(source, blob, key, item)
        link_snapshot(blob, snapshot / item.path)
    for relative in missing:
        hf_hub_download(
            args.repo_id, relative, repo_type="dataset", revision=args.revision,
            cache_dir=args.cache_dir,
        )
    resolved = Path(snapshot_download(
        args.repo_id, repo_type="dataset", revision=args.revision,
        cache_dir=args.cache_dir, local_files_only=True,
    )).resolve()
    if resolved != snapshot.resolve():
        raise RuntimeError(f"canonical snapshot resolved unexpectedly: {resolved}")
    print(f"Cached {args.repo_id}@{args.revision} with {len(items)} files ({len(missing)} tiny file(s) fetched).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
