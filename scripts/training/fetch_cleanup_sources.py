#!/usr/bin/env python3
"""Fetch immutable cleanup-data sources and record payload provenance."""

from __future__ import annotations

import argparse
import fnmatch
import io
import json
import os
import sys
import tarfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from cleanup_data_common import atomic_json, sha256_file


USER_AGENT = "local-flow-cleanup-data/1"


def request(url: str, token: str | None = None, range_start: int | None = None) -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if range_start is not None:
        headers["Range"] = f"bytes={range_start}-"
    return urllib.request.Request(url, headers=headers)


def read_url(url: str, token: str | None = None) -> bytes:
    try:
        with urllib.request.urlopen(request(url, token), timeout=120) as response:
            return response.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"failed to retrieve {url}: {exc}") from exc


def download_url(url: str, target: Path, token: str | None = None) -> None:
    """Stream or safely resume a payload into an atomic sibling path."""

    temporary = target.with_name(target.name + ".partial")
    if target.is_symlink() or temporary.is_symlink():
        raise RuntimeError(f"refusing source download through a symbolic link: {target}")
    offset = temporary.stat().st_size if temporary.exists() else 0
    try:
        with urllib.request.urlopen(
            request(url, token, offset if offset else None), timeout=120
        ) as response:
            status = getattr(response, "status", response.getcode())
            content_range = response.headers.get("Content-Range", "")
            if offset and (status != 206 or not content_range.startswith(f"bytes {offset}-")):
                raise RuntimeError(
                    f"server did not honor safe resume at byte {offset}: "
                    f"status={status}, content-range={content_range!r}"
                )
            mode = "ab" if offset else "xb"
            with temporary.open(mode) as handle:
                while True:
                    chunk = response.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
        temporary.replace(target)
    except (urllib.error.URLError, OSError, RuntimeError) as exc:
        raise RuntimeError(
            f"failed to download {url}: {exc}; resumable partial path: {temporary}"
        ) from exc


def verify_existing_huggingface_paths(root: Path, selected: list[str]) -> None:
    """Permit only selected payloads and their resumable partial siblings."""

    allowed = set(selected) | {relative + ".partial" for relative in selected}
    existing = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    unexpected = sorted(existing - allowed)
    if unexpected:
        raise RuntimeError(
            f"source directory contains {len(unexpected)} unexpected file(s): {unexpected[:3]}"
        )


def matches(path: str, patterns: list[str]) -> bool:
    candidate = PurePosixPath(path)
    return any(candidate.match(pattern) or fnmatch.fnmatch(path, pattern) for pattern in patterns)


def safe_target(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"unsafe source path: {relative!r}")
    target = (root / Path(*path.parts)).resolve()
    if root.resolve() not in target.parents and target != root.resolve():
        raise RuntimeError(f"source path escapes destination: {relative!r}")
    return target


def fetch_huggingface(source: dict[str, Any], root: Path, token: str | None) -> list[Path]:
    repository = source["repository"]
    revision = source["revision"]
    api = f"https://huggingface.co/api/datasets/{repository}/revision/{revision}"
    metadata = json.loads(read_url(api, token))
    if metadata.get("sha") != revision:
        raise RuntimeError(f"{source['id']}: resolved revision {metadata.get('sha')!r}, expected {revision}")
    siblings = metadata.get("siblings")
    if not isinstance(siblings, list):
        raise RuntimeError(f"{source['id']}: Hugging Face response has no siblings list")
    selected = sorted(
        item["rfilename"] for item in siblings
        if isinstance(item, dict) and isinstance(item.get("rfilename"), str)
        and matches(item["rfilename"], source["include"])
    )
    if not selected:
        raise RuntimeError(f"{source['id']}: include rules matched no files")
    verify_existing_huggingface_paths(root, selected)
    paths: list[Path] = []
    for relative in selected:
        target = safe_target(root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        url = f"https://huggingface.co/datasets/{repository}/resolve/{revision}/{relative}?download=true"
        download_url(url, target, token)
        paths.append(target)
    return paths


def fetch_github(source: dict[str, Any], root: Path) -> list[Path]:
    revision = source["revision"]
    archive_url = f"https://codeload.github.com/{source['repository']}/tar.gz/{revision}"
    payload = read_url(archive_url)
    paths: list[Path] = []
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            parts = PurePosixPath(member.name).parts
            if len(parts) < 2:
                continue
            relative = str(PurePosixPath(*parts[1:]))
            if not matches(relative, source["include"]):
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                raise RuntimeError(f"cannot extract {member.name}")
            target = safe_target(root, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(extracted.read())
            paths.append(target)
    if not paths:
        raise RuntimeError(f"{source['id']}: include rules matched no archive files")
    return sorted(paths)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("training/config/sources-v1.json"))
    parser.add_argument("--root", type=Path, required=True, help="artifact root outside git")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="verify existing payloads instead of fetching")
    return parser.parse_args()


def verify_manifest_identity(manifest: dict[str, Any], config: dict[str, Any], config_path: Path) -> None:
    if manifest.get("manifest_version") != "cleanup-source-manifest-v1":
        raise RuntimeError("unsupported source manifest version")
    if manifest.get("config_sha256") != sha256_file(config_path):
        raise RuntimeError("source manifest configuration hash differs from current configuration")
    configured = {source["id"]: source for source in config["sources"]}
    manifested = {source.get("id"): source for source in manifest.get("sources", [])}
    if set(manifested) != set(configured):
        raise RuntimeError("source manifest IDs differ from current configuration")
    for source_id, source in manifested.items():
        for field in ("url", "revision", "license"):
            if source.get(field) != configured[source_id][field]:
                raise RuntimeError(f"{source_id}: manifest {field} differs from current pin")


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if args.check:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        verify_manifest_identity(manifest, config, args.config)
        for source in manifest["sources"]:
            for item in source["files"]:
                source_root = safe_target(args.root, source["id"])
                path = safe_target(source_root, item["path"])
                if not path.is_file() or path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
                    raise RuntimeError(f"payload verification failed: {source['id']}/{item['path']}")
        print(f"Verified {sum(len(source['files']) for source in manifest['sources'])} source file(s).")
        return 0
    if args.manifest.exists():
        raise RuntimeError(f"refusing to overwrite source manifest: {args.manifest}")
    token = os.environ.get("HF_TOKEN")
    entries = []
    sources = config["sources"]
    for ordinal, source in enumerate(sources, 1):
        print(f"[{ordinal}/{len(sources)}] fetching {source['id']}", file=sys.stderr, flush=True)
        destination = args.root / source["id"]
        destination.mkdir(parents=True, exist_ok=True)
        if source["kind"] == "huggingface_dataset":
            files = fetch_huggingface(source, destination, token)
        elif source["kind"] == "github_archive":
            files = fetch_github(source, destination)
        else:
            raise RuntimeError(f"unsupported source kind: {source['kind']}")
        entries.append({
            "id": source["id"], "url": source["url"], "revision": source["revision"],
            "license": source["license"], "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "files": [{"path": str(path.relative_to(destination)), "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in files],
        })
    manifest = {"manifest_version": "cleanup-source-manifest-v1", "config_sha256": sha256_file(args.config), "sources": entries}
    atomic_json(args.manifest, manifest)
    print(f"Fetched {sum(len(source['files']) for source in entries)} source file(s) from {len(entries)} pinned revisions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
