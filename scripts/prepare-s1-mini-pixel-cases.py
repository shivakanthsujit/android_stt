#!/usr/bin/env python3
"""Prepare transcript-only Pixel cases with S1-mini's exact per-input output cap."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def max_new_tokens(input_tokens: int) -> int:
    if input_tokens <= 0:
        raise ValueError("input token count must be positive")
    return math.ceil(1.3 * input_tokens + 32)


def prepare(source: Path, tokenizer_json: Path) -> list[dict]:
    try:
        from tokenizers import Tokenizer
    except ImportError as error:
        raise ValueError("the tokenizers package is required") from error

    tokenizer = Tokenizer.from_file(str(tokenizer_json))
    prepared: list[dict] = []
    seen: set[str] = set()
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        case_id = row.get("id")
        raw = row.get("raw")
        categories = row.get("categories", [])
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError(f"{source}:{line_number}: invalid or duplicate id")
        if not isinstance(raw, str) or not raw:
            raise ValueError(f"{source}:{line_number}: raw must be non-empty text")
        if not isinstance(categories, list) or not all(
            isinstance(item, str) for item in categories
        ):
            raise ValueError(f"{source}:{line_number}: categories must be strings")
        token_count = len(tokenizer.encode(raw, add_special_tokens=False).ids)
        prepared.append(
            {
                "id": case_id,
                "raw": raw,
                "categories": categories,
                "raw_input_tokens": token_count,
                "max_new_tokens": max_new_tokens(token_count),
            }
        )
        seen.add(case_id)
    if not prepared:
        raise ValueError(f"{source}: no cases")
    return prepared


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--tokenizer-json", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError(f"output already exists: {args.output}")
    rows = prepare(args.source, args.tokenizer_json)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "case_count": len(rows),
                "source_sha256": sha256_file(args.source),
                "tokenizer_sha256": sha256_file(args.tokenizer_json),
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
