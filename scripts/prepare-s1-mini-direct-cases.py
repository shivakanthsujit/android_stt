#!/usr/bin/env python3
"""Create the transcript-only input consumed by the isolated llama.cpp APK."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare(source: Path) -> list[dict]:
    if "blind" in str(source).casefold():
        raise ValueError("blind evaluation inputs are prohibited")
    prepared: list[dict] = []
    seen: set[str] = set()
    with source.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{source}:{line_number}: row must be an object")
            case_id = row.get("id")
            raw = row.get("raw")
            categories = row.get("categories", [])
            if (
                not isinstance(case_id, str)
                or SAFE_ID.fullmatch(case_id) is None
                or case_id in seen
            ):
                raise ValueError(f"{source}:{line_number}: invalid or duplicate id")
            if not isinstance(raw, str) or not raw.strip():
                raise ValueError(f"{source}:{line_number}: raw must be non-empty text")
            if not isinstance(categories, list) or not all(
                isinstance(item, str) and item for item in categories
            ):
                raise ValueError(f"{source}:{line_number}: categories must be non-empty strings")
            prepared.append({"id": case_id, "raw": raw, "categories": categories})
            seen.add(case_id)
    if not prepared:
        raise ValueError(f"{source}: no cases")
    return prepared


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.source.is_file():
        raise ValueError(f"missing source cases: {args.source}")
    if args.output.exists():
        raise ValueError(f"output already exists: {args.output}")
    rows = prepare(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(
        json.dumps(
            {
                "case_count": len(rows),
                "source_sha256": sha256_file(args.source),
                "output_sha256": sha256_file(args.output),
                "output": str(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"error: {error}")
