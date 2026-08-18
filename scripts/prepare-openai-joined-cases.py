#!/usr/bin/env python3
"""Project Parakeet outputs into an evaluation-only OpenAI cleanup case file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def prepare(joined_path: Path, source_cases_path: Path) -> list[dict]:
    if "blind" in str(joined_path).casefold() or "blind" in str(source_cases_path).casefold():
        raise ValueError("blind evaluation inputs are forbidden")
    source_rows = read_jsonl(source_cases_path)
    source = {row.get("id"): row for row in source_rows}
    if len(source) != len(source_rows) or None in source:
        raise ValueError("source cases have invalid or duplicate IDs")
    joined_rows = read_jsonl(joined_path)
    joined = {row.get("case_id"): row for row in joined_rows}
    if len(joined) != len(joined_rows) or None in joined:
        raise ValueError("joined results have invalid or duplicate IDs")
    if set(source) != set(joined):
        raise ValueError("joined/source case membership differs")

    projected = []
    for row in source_rows:
        case_id = row["id"]
        raw_stt = joined[case_id].get("raw_stt")
        model_input = joined[case_id].get("model_input")
        if not isinstance(raw_stt, str) or not raw_stt.strip():
            raise ValueError(f"joined case {case_id} has no raw STT")
        if not isinstance(model_input, str) or not model_input.strip():
            raise ValueError(f"joined case {case_id} has no deterministic model input")
        projected.append(
            {
                "id": case_id,
                "spoken": row.get("spoken", ""),
                # Reuse the exact post-filler text supplied to local Sotto so the
                # cleanup backends receive identical inputs.
                "raw": model_input,
                "expected": row["expected"],
                "categories": row["categories"],
                "must_preserve": row["must_preserve"],
                "must_remove": row.get("must_remove", []),
                "source_joined_run_id": joined[case_id].get("run_id"),
                "source_audio_sha256": joined[case_id].get("audio_sha256"),
                "source_raw_stt": raw_stt,
            }
        )
    return projected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("joined_result", type=Path)
    parser.add_argument("source_cases", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError(f"refusing to overwrite {args.output}")
    rows = prepare(args.joined_result, args.source_cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"Wrote {len(rows)} evaluation-only joined cases to {args.output}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"error: {error}")
