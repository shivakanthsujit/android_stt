#!/usr/bin/env python3
"""Validate the isolated transcript-only LiteRT-LM Pixel smoke result."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


MODEL_SHA256 = "8748cd01c614db17454fc02b87ef3fc46558f8c5e796dbb85a6f5be6eb01a403"
SYSTEM = (
    "You are a text normalizer for speech-to-text transcripts. The input begins with a "
    "control line specifying the styling, structure, and context settings; clean the "
    "transcript to match those settings and output only the cleaned text."
)
CONTROL = "[Styling: semi-formal] [Structure: prose] [Context: general]"


def read_jsonl(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{path}: expected non-empty JSON objects")
    return rows


def expected_prompt(raw: str) -> str:
    return (
        f"<|im_start|>system\n{SYSTEM}<|im_end|>\n"
        f"<|im_start|>user\n{CONTROL}\n{raw}<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate(results: list[dict], cases: list[dict], backend: str) -> dict:
    if backend not in {"cpu", "gpu"}:
        raise ValueError("backend must be cpu or gpu")
    expected_jobs = [("warmup", 0, cases[0])] + [
        ("measured", 0, case) for case in cases[1:] + cases[:1]
    ]
    if len(results) != len(expected_jobs):
        raise ValueError(f"expected {len(expected_jobs)} rows, found {len(results)}")
    outputs: dict[str, str] = {}
    for index, (row, (phase, repeat, case)) in enumerate(zip(results, expected_jobs, strict=True)):
        label = f"row {index}"
        if row.get("schema_version") != 1 or row.get("phase") != phase:
            raise ValueError(f"{label}: schema/phase mismatch")
        if row.get("repeat_index") != repeat or row.get("case_id") != case["id"]:
            raise ValueError(f"{label}: job identity mismatch")
        if row.get("raw_text") != case["raw"] or row.get("categories") != case["categories"]:
            raise ValueError(f"{label}: transcript projection mismatch")
        raw_tokens = case["raw_tokens"]
        if row.get("raw_token_count") != raw_tokens:
            raise ValueError(f"{label}: raw token count mismatch")
        if row.get("fixed_prompt_tokens") != 78:
            raise ValueError(f"{label}: fixed prompt count mismatch")
        if row.get("prompt_token_count_expected") != 78 + raw_tokens:
            raise ValueError(f"{label}: expected prompt count mismatch")
        cap = (13 * raw_tokens + 9) // 10 + 32
        if row.get("requested_max_output_tokens") != cap:
            raise ValueError(f"{label}: output cap mismatch")
        prompt = expected_prompt(case["raw"])
        if row.get("rendered_prompt") != prompt or row.get("rendered_prompt_sha256") != sha256_text(prompt):
            raise ValueError(f"{label}: rendered prompt drift")
        if row.get("model_sha256") != MODEL_SHA256 or row.get("context_tokens") != 4096:
            raise ValueError(f"{label}: model/context mismatch")
        if row.get("backend") != backend or row.get("litert_lm_version") != "0.16.1":
            raise ValueError(f"{label}: runtime/backend mismatch")
        if backend == "cpu" and row.get("cpu_threads") != 2:
            raise ValueError(f"{label}: CPU thread mismatch")
        if backend == "gpu" and row.get("cpu_threads") is not None:
            raise ValueError(f"{label}: GPU row must not claim CPU threads")
        output = row.get("raw_output")
        if not isinstance(output, str) or "<think>" in output or "</think>" in output:
            raise ValueError(f"{label}: malformed or thinking-marked output")
        for field in (
            "total_ms",
            "process_cpu_ms",
            "process_pss_kb_after_inference",
            "native_heap_bytes_after_inference",
            "thermal_status_after_inference",
            "model_load_ms",
            "conversation_token_count",
        ):
            if not isinstance(row.get(field), int) or isinstance(row[field], bool) or row[field] < 0:
                raise ValueError(f"{label}: invalid {field}")
        benchmark_available = row.get("benchmark_available")
        if not isinstance(benchmark_available, bool):
            raise ValueError(f"{label}: benchmark_available must be boolean")
        if not benchmark_available and not isinstance(row.get("benchmark_error"), str):
            raise ValueError(f"{label}: unavailable benchmark must retain an error")
        if phase == "measured":
            outputs[case["id"]] = output
    thermal = [row["thermal_status_after_inference"] for row in results]
    return {
        "schema_version": 1,
        "verdict": "pass",
        "backend": backend,
        "row_count": len(results),
        "measured_outputs": outputs,
        "model_load_ms": results[0]["model_load_ms"],
        "measured_total_ms": [row["total_ms"] for row in results if row["phase"] == "measured"],
        "peak_pss_kb": max(row["process_pss_kb_after_inference"] for row in results),
        "max_thermal_status": max(thermal),
        "benchmark_available": all(row["benchmark_available"] for row in results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--backend", required=True, choices=("cpu", "gpu"))
    parser.add_argument("--json-out", required=True, type=Path)
    args = parser.parse_args()
    summary = validate(read_jsonl(args.results), read_jsonl(args.cases), args.backend)
    args.json_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"error: {error}")
