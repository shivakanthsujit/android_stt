#!/usr/bin/env python3
"""Score repeated direct-text cleanup results produced by the Pixel debug activity."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import unicodedata
from collections import defaultdict
from pathlib import Path


RUNTIME_CONFIGURATION_FIELDS = (
    "context_size",
    "cpu_threads_mode",
    "cpu_threads",
    "resolved_cpu_threads",
    "cache_enabled",
    "cache_max_memory_bytes",
    "cache_max_entries",
    "cache_disk_disabled",
    "cache_requested_max_disk_entries",
    "mmap_enabled",
    "fixed_prompt_tokens",
)

APPROVED_CONTEXT_SIZES = {4_096, 3_072, 2_560}
APPROVED_CPU_THREADS = {2, 3, 4}
APPROVED_IMPLICIT_RESOLVED_CPU_THREADS = {1, 2, 3, 4}
APPROVED_CACHE_MEMORY_BYTES = {32 * 1_048_576, 64 * 1_048_576}
FIXED_PROMPT_TOKENS = 78
CACHE_MAX_ENTRIES = 4


def read_jsonl(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        raise ValueError(f"{path}: no JSON records")
    return rows


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n")).strip()


def normalize_words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", normalize_text(text).casefold())


def nearest_rank(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def timing(values: list[float]) -> dict[str, float]:
    return {
        "count": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "p90": nearest_rank(values, 0.90),
        "p95": nearest_rank(values, 0.95),
        "max": max(values),
        "mean": statistics.fmean(values),
    }


def _require_nonnegative_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"runtime configuration has invalid {field}")
    return value


def runtime_configuration(rows: list[dict]) -> dict | None:
    has_configuration = [
        any(field in row for field in RUNTIME_CONFIGURATION_FIELDS) for row in rows
    ]
    if not any(has_configuration):
        return None
    if not all(has_configuration):
        raise ValueError("measured rows mix legacy and runtime configuration metadata")

    configurations: list[dict] = []
    for row in rows:
        missing = [field for field in RUNTIME_CONFIGURATION_FIELDS if field not in row]
        if missing:
            raise ValueError(
                "measured row has incomplete runtime configuration metadata: "
                + ", ".join(missing)
            )
        configuration = {field: row[field] for field in RUNTIME_CONFIGURATION_FIELDS}

        if configuration["cpu_threads_mode"] not in ("implicit", "explicit"):
            raise ValueError("runtime configuration has invalid cpu_threads_mode")
        cpu_threads = configuration["cpu_threads"]
        resolved_cpu_threads = configuration["resolved_cpu_threads"]
        _require_nonnegative_integer(resolved_cpu_threads, "resolved_cpu_threads")
        if resolved_cpu_threads not in APPROVED_IMPLICIT_RESOLVED_CPU_THREADS:
            raise ValueError("runtime configuration has unapproved resolved_cpu_threads")
        if configuration["cpu_threads_mode"] == "implicit":
            if cpu_threads is not None:
                raise ValueError("implicit cpu_threads_mode requires null cpu_threads")
        else:
            _require_nonnegative_integer(cpu_threads, "cpu_threads")
            if cpu_threads not in APPROVED_CPU_THREADS:
                raise ValueError("explicit cpu_threads_mode has unapproved cpu_threads")
            if resolved_cpu_threads != cpu_threads:
                raise ValueError(
                    "explicit cpu_threads_mode requires resolved_cpu_threads to match cpu_threads"
                )

        for field in (
            "context_size",
            "cache_max_memory_bytes",
            "cache_max_entries",
            "cache_requested_max_disk_entries",
            "fixed_prompt_tokens",
        ):
            _require_nonnegative_integer(configuration[field], field)
        for field in ("cache_enabled", "cache_disk_disabled", "mmap_enabled"):
            if not isinstance(configuration[field], bool):
                raise ValueError(f"runtime configuration has invalid {field}")
        if configuration["context_size"] not in APPROVED_CONTEXT_SIZES:
            raise ValueError("runtime configuration has unapproved context_size")
        if configuration["fixed_prompt_tokens"] != FIXED_PROMPT_TOKENS:
            raise ValueError("runtime configuration has unexpected fixed_prompt_tokens")
        if configuration["mmap_enabled"] is not True:
            raise ValueError("runtime configuration requires mmap_enabled=true")
        if configuration["cache_disk_disabled"] is not True:
            raise ValueError("runtime configuration requires cache_disk_disabled=true")
        if configuration["cache_requested_max_disk_entries"] != 0:
            raise ValueError(
                "runtime configuration requires cache_requested_max_disk_entries=0"
            )
        if configuration["cache_enabled"]:
            if configuration["cache_max_memory_bytes"] not in APPROVED_CACHE_MEMORY_BYTES:
                raise ValueError(
                    "enabled cache has unapproved cache_max_memory_bytes"
                )
            if configuration["cache_max_entries"] != CACHE_MAX_ENTRIES:
                raise ValueError(
                    f"enabled cache requires cache_max_entries={CACHE_MAX_ENTRIES}"
                )
        elif (
            configuration["cache_max_memory_bytes"] != 0
            or configuration["cache_max_entries"] != 0
        ):
            raise ValueError("disabled cache requires zero memory bytes and entries")
        configurations.append(configuration)

    first = configurations[0]
    if any(configuration != first for configuration in configurations[1:]):
        raise ValueError("measured rows contain mixed runtime configurations")
    return first


def cached_prompt_token_summary(rows: list[dict]) -> dict | None:
    present = ["cached_prompt_tokens" in row for row in rows]
    if not any(present):
        return None
    if not all(present):
        raise ValueError("measured rows have incomplete cached_prompt_tokens metadata")
    values = [
        _require_nonnegative_integer(value, "cached_prompt_tokens")
        for row in rows
        if (value := row["cached_prompt_tokens"]) is not None
    ]
    if not values:
        return None
    return {
        "count": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
        "total": sum(values),
    }


def load_cases(path: Path) -> dict[str, dict]:
    cases: dict[str, dict] = {}
    for row in read_jsonl(path):
        case_id = row.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in cases:
            raise ValueError(f"{path}: invalid or duplicate case id")
        for field in ("raw", "expected"):
            if not isinstance(row.get(field), str) or not row[field]:
                raise ValueError(f"{path}: {case_id} has invalid {field}")
        anchors = row.get("must_preserve")
        categories = row.get("categories")
        if not isinstance(anchors, list) or not all(isinstance(item, str) for item in anchors):
            raise ValueError(f"{path}: {case_id} has invalid must_preserve")
        if not isinstance(categories, list) or not all(isinstance(item, str) for item in categories):
            raise ValueError(f"{path}: {case_id} has invalid categories")
        cases[case_id] = row
    return cases


def summarize(result_path: Path, cases_path: Path) -> dict:
    cases = load_cases(cases_path)
    all_rows = read_jsonl(result_path)
    rows = [row for row in all_rows if row.get("phase") == "measured"]
    if not rows:
        raise ValueError("result has no measured rows")
    runtime_config = runtime_configuration(rows)
    cached_prompt_tokens = cached_prompt_token_summary(rows)
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        case_id = row.get("case_id")
        if case_id not in cases:
            raise ValueError(f"unknown result case id: {case_id!r}")
        grouped[case_id].append(row)
    if set(grouped) != set(cases):
        raise ValueError("result/case membership differs")
    repeat_counts = {len(items) for items in grouped.values()}
    if len(repeat_counts) != 1:
        raise ValueError("measured repeat counts differ by case")
    for items in grouped.values():
        repeat_indices = sorted(row.get("repeat_index") for row in items)
        if repeat_indices != list(range(len(items))):
            raise ValueError("repeat indices are not complete and zero-based")

    first_rows = {case_id: min(items, key=lambda row: row["repeat_index"]) for case_id, items in grouped.items()}
    strict_exact = normalized_exact = guarded_strict_exact = 0
    preserved_anchors = total_anchors = all_anchor_cases = 0
    per_category: dict[str, dict[str, int]] = defaultdict(lambda: {"cases": 0, "strict_exact": 0})
    for case_id, case in cases.items():
        row = first_rows[case_id]
        raw_output = normalize_text(row["raw_model_output"])
        guarded_output = normalize_text(row["guarded_output"])
        expected = normalize_text(case["expected"])
        exact = raw_output == expected
        strict_exact += int(exact)
        normalized_exact += int(normalize_words(raw_output) == normalize_words(expected))
        guarded_strict_exact += int(guarded_output == expected)
        missing = [anchor for anchor in case["must_preserve"] if normalize_text(anchor) not in raw_output]
        preserved_anchors += len(case["must_preserve"]) - len(missing)
        total_anchors += len(case["must_preserve"])
        all_anchor_cases += int(not missing)
        for category in case["categories"]:
            per_category[category]["cases"] += 1
            per_category[category]["strict_exact"] += int(exact)

    output_instability = {
        case_id: len({row["raw_model_output"] for row in items})
        for case_id, items in grouped.items()
        if len({row["raw_model_output"] for row in items}) > 1
    }
    total_ms = [float(row["cleanup_total_ms"]) for row in rows]
    ttft_ms = [float(row["cleanup_ttft_ms"]) for row in rows if row.get("cleanup_ttft_ms") is not None]
    cpu_ms = [float(row["process_cpu_ms"]) for row in rows]
    token_rates = [float(row["tokens_per_second"]) for row in rows if row.get("tokens_per_second") is not None]
    completion_tokens = [int(row["completion_tokens"]) for row in rows if row.get("completion_tokens") is not None]
    return {
        "schema_version": 1,
        "result_file": str(result_path),
        "cases_file": str(cases_path),
        "case_count": len(cases),
        "measured_repeat_count": repeat_counts.pop(),
        "measured_call_count": len(rows),
        "model_file": rows[0].get("model_file"),
        "model_sha256": rows[0].get("model_sha256"),
        "model_load_ms": rows[0].get("model_load_ms"),
        **{
            field: runtime_config[field] if runtime_config is not None else None
            for field in RUNTIME_CONFIGURATION_FIELDS
        },
        "cached_prompt_tokens": cached_prompt_tokens,
        "raw_strict_exact": strict_exact,
        "raw_normalized_exact": normalized_exact,
        "guarded_strict_exact": guarded_strict_exact,
        "preserved_anchor_count": preserved_anchors,
        "anchor_count": total_anchors,
        "all_anchor_case_count": all_anchor_cases,
        "fallback_call_count": sum(bool(row["used_fallback"]) for row in rows),
        "output_instability_case_count": len(output_instability),
        "output_instability_distinct_counts": output_instability,
        "cleanup_total_ms": timing(total_ms),
        "cleanup_ttft_ms": timing(ttft_ms) if ttft_ms else None,
        "process_cpu_ms": timing(cpu_ms),
        "tokens_per_second": timing(token_rates) if token_rates else None,
        "completion_token_count": sum(completion_tokens),
        "sequential_calls_per_second": len(total_ms) / (sum(total_ms) / 1000.0),
        "peak_pss_kb": max(int(row["process_pss_kb_after_inference"]) for row in rows),
        "peak_native_heap_bytes": max(int(row["native_heap_bytes_after_inference"]) for row in rows),
        "max_thermal_status": max(int(row["thermal_status_after_inference"]) for row in rows),
        "per_category": dict(sorted(per_category.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    summary = summarize(args.result, args.cases)
    serialized = json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    print(serialized, end="")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(f"error: {error}")
