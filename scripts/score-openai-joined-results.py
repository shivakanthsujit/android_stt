#!/usr/bin/env python3
"""Combine Pixel Parakeet timings with hosted cleanup results for an E2E profile."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        raise ValueError(f"{path}: no records")
    return rows


def nearest_rank(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def timing(values: list[float]) -> dict[str, float]:
    return {
        "count": len(values),
        "min_ms": min(values),
        "median_ms": statistics.median(values),
        "p90_ms": nearest_rank(values, 0.90),
        "p95_ms": nearest_rank(values, 0.95),
        "max_ms": max(values),
        "mean_ms": statistics.fmean(values),
    }


def summarize(joined_path: Path, hosted_path: Path) -> dict:
    joined_rows = read_jsonl(joined_path)
    hosted_rows = read_jsonl(hosted_path)
    joined = {row.get("case_id"): row for row in joined_rows}
    hosted = {row.get("case_id"): row for row in hosted_rows}
    if len(joined) != len(joined_rows) or len(hosted) != len(hosted_rows):
        raise ValueError("duplicate or invalid case IDs")
    if set(joined) != set(hosted):
        raise ValueError("joined/hosted membership differs")
    stt_ms = [float(joined[case_id]["stt_inference_ms"]) for case_id in joined]
    cleanup_ms = [float(hosted[case_id]["timings"]["total_ms"]) for case_id in joined]
    ttft_ms = [
        float(hosted[case_id]["timings"]["ttft_ms"])
        for case_id in joined
        if hosted[case_id]["timings"].get("ttft_ms") is not None
    ]
    pipeline_ms = [stt + cleanup for stt, cleanup in zip(stt_ms, cleanup_ms)]
    audio_ms = sum(float(row["audio_duration_ms"]) for row in joined_rows)
    return {
        "schema_version": 1,
        "joined_result_file": str(joined_path),
        "hosted_result_file": str(hosted_path),
        "case_count": len(joined),
        "model_name": hosted_rows[0].get("model_name"),
        "stt_inference": timing(stt_ms),
        "hosted_cleanup_total": timing(cleanup_ms),
        "hosted_cleanup_ttft": timing(ttft_ms) if ttft_ms else None,
        "estimated_pipeline_total": timing(pipeline_ms),
        "pipeline_scope": (
            "Pixel Parakeet inference plus Mac-hosted API request; excludes ADB/host handoff "
            "and does not measure Pixel radio/network energy"
        ),
        "audio_duration_seconds": audio_ms / 1000.0,
        "audio_seconds_per_pipeline_second": audio_ms / sum(pipeline_ms),
        "prompt_tokens": sum(int(row.get("prompt_tokens", 0)) for row in hosted_rows),
        "completion_tokens": sum(int(row.get("completion_tokens", 0)) for row in hosted_rows),
        "first_attempt_count": sum(
            int(row["timings"].get("attempt_count", 0) == 1) for row in hosted_rows
        ),
        "finish_reason_counts": {
            reason: sum(row.get("finish_reason") == reason for row in hosted_rows)
            for reason in sorted({row.get("finish_reason") for row in hosted_rows if row.get("finish_reason")})
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("joined_result", type=Path)
    parser.add_argument("hosted_result", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    summary = summarize(args.joined_result, args.hosted_result)
    serialized = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    print(serialized, end="")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"error: {error}")
