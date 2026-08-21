#!/usr/bin/env python3
"""Validate and summarize isolated Android llama.cpp S1-mini benchmark JSONL."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


MODEL_FILE = "s1-mini-q4_k_m.gguf"
MODEL_SHA256 = "3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634"
LLAMA_REVISION = "ece963f41"
LLAMA_VERSION = "0.1.0-dev"
LLAMA_BUILD_NUMBER = 10_450
FIXED_PROMPT_TOKENS = 78
MODEL_SIZE_BYTES = 484_219_808
APPLICATION_ID = "dev.localflow.llamacppbenchmark"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
SYSTEM_PROMPT = (
    "You are a text normalizer for speech-to-text transcripts. The input begins with a "
    "control line specifying the styling, structure, and context settings; clean the "
    "transcript to match those settings and output only the cleaned text."
)
CONTROL_LINE = "[Styling: semi-formal] [Structure: prose] [Context: general]"
PINNED_CPU_BACKEND_LIBRARIES = {
    "libggml-cpu-android_armv8.0_1.so",
    "libggml-cpu-android_armv8.2_1.so",
    "libggml-cpu-android_armv8.2_2.so",
    "libggml-cpu-android_armv8.6_1.so",
    "libggml-cpu-android_armv9.0_1.so",
    "libggml-cpu-android_armv9.2_1.so",
    "libggml-cpu-android_armv9.2_2.so",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: row must be an object")
            rows.append(value)
    if not rows:
        raise ValueError(f"{path}: no result rows")
    return rows


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def distribution(values: list[float]) -> dict[str, float]:
    if not values:
        raise ValueError("cannot summarize an empty distribution")
    return {
        "count": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "p90": percentile(values, 0.9),
        "p95": percentile(values, 0.95),
        "max": max(values),
        "mean": statistics.fmean(values),
    }


def _require_integer(value: Any, label: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{label} must be an integer >= {minimum}")
    return value


def _single(rows: list[dict[str, Any]], field: str) -> Any:
    values = {json.dumps(row.get(field), sort_keys=True) for row in rows}
    if len(values) != 1:
        raise ValueError(f"direct results mix {field}")
    return rows[0].get(field)


def _require_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if value < 0:
        raise ValueError(f"{label} must be nonnegative")
    return float(value)


def _require_token_ids(value: Any, label: str) -> list[int]:
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        raise ValueError(f"{label} must be an integer list")
    return value


def validate_direct(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    required = {
        "schema_version", "run_id", "phase", "repeat_index", "case_id", "categories",
        "raw_text", "model_file", "model_sha256", "prompt_profile",
        "requested_max_output_tokens", "requested_config", "native_model_info", "app_build",
        "process_cpu_ms", "process_pss_kb_after_inference",
        "native_heap_bytes_after_inference", "thermal_status_after_inference", "raw_token_ids",
        "raw_token_count", "rendered_prompt", "prompt_token_ids", "prompt_token_count",
        "raw_output", "completion_token_ids", "completion_tokens", "finish_reason",
        "hit_token_cap", "started_at_ns", "prompt_started_at_ns", "prompt_completed_at_ns",
        "first_token_at_ns", "completed_at_ns", "prompt_eval_ms", "decode_ms", "total_ms",
        "prompt_tokens_per_second", "decode_tokens_per_second", "model_load_ms",
        "eog_token_id", "perf_prompt_eval_ms", "perf_decode_ms", "perf_prompt_tokens",
        "perf_decode_tokens", "perf_reused_graphs", "created_at_utc",
    }
    for index, row in enumerate(rows):
        missing = required - row.keys()
        if missing:
            raise ValueError(f"direct row {index} is missing: {sorted(missing)}")
        if row["schema_version"] != 1:
            raise ValueError("unsupported direct schema")
        if row["phase"] not in {"warmup", "measured"}:
            raise ValueError("invalid direct phase")
        if row["model_file"] != MODEL_FILE or row["model_sha256"] != MODEL_SHA256:
            raise ValueError("direct model identity mismatch")
        if row["prompt_profile"] != "s1-mini-v1-publisher":
            raise ValueError("direct prompt profile mismatch")
        if not isinstance(row["run_id"], str) or not row["run_id"]:
            raise ValueError("direct run_id must be non-empty text")
        if not isinstance(row["case_id"], str) or SAFE_ID.fullmatch(row["case_id"]) is None:
            raise ValueError("direct case_id must be non-empty text")
        if not isinstance(row["raw_text"], str) or not row["raw_text"].strip():
            raise ValueError("direct raw_text must be non-empty text")
        if not isinstance(row["categories"], list) or not all(
            isinstance(item, str) and item for item in row["categories"]
        ):
            raise ValueError("direct categories must contain non-empty strings")
        if not isinstance(row["rendered_prompt"], str) or not row["rendered_prompt"]:
            raise ValueError("direct rendered_prompt must be non-empty text")
        expected_prompt = (
            f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
            f"<|im_start|>user\n{CONTROL_LINE}\n{row['raw_text']}<|im_end|>\n"
            "<|im_start|>assistant\n<think>\n\n</think>\n\n"
        )
        if row["rendered_prompt"] != expected_prompt:
            raise ValueError("direct rendered prompt drift")
        if not isinstance(row["raw_output"], str):
            raise ValueError("direct raw_output must be text")
        raw_count = _require_integer(row["raw_token_count"], "raw_token_count", 1)
        prompt_count = _require_integer(row["prompt_token_count"], "prompt_token_count", 1)
        raw_ids = _require_token_ids(row["raw_token_ids"], "raw_token_ids")
        prompt_ids = _require_token_ids(row["prompt_token_ids"], "prompt_token_ids")
        if len(raw_ids) != raw_count or len(prompt_ids) != prompt_count:
            raise ValueError("direct token count/ID mismatch")
        if raw_count > 1_000:
            raise ValueError("direct raw token count exceeds the pass contract")
        if prompt_count - raw_count != FIXED_PROMPT_TOKENS:
            raise ValueError("direct fixed prompt-token count drift")
        cap = (13 * raw_count + 9) // 10 + 32
        if row["requested_max_output_tokens"] != cap:
            raise ValueError("direct output cap drift")
        completion = _require_integer(row["completion_tokens"], "completion_tokens")
        completion_ids = _require_token_ids(row["completion_token_ids"], "completion_token_ids")
        if len(completion_ids) != completion or completion > cap:
            raise ValueError("direct completion token accounting drift")
        if row["finish_reason"] not in {"eog", "token_cap"}:
            raise ValueError("direct finish reason is invalid")
        if row["hit_token_cap"] != (row["finish_reason"] == "token_cap"):
            raise ValueError("direct cap flag/finish mismatch")
        if row["hit_token_cap"] and completion != cap:
            raise ValueError("direct cap finish occurred below the cap")
        eog_token_id = row["eog_token_id"]
        if row["hit_token_cap"]:
            if eog_token_id is not None:
                raise ValueError("direct capped generation must not report an EOG token")
        else:
            _require_integer(eog_token_id, "eog_token_id")
        first_token = row["first_token_at_ns"]
        if (completion > 0) != (first_token is not None):
            raise ValueError("direct first-token timestamp/completion mismatch")
        for field in ("process_cpu_ms", "process_pss_kb_after_inference",
                      "native_heap_bytes_after_inference", "thermal_status_after_inference",
                      "model_load_ms"):
            _require_integer(row[field], field)
        for field in ("prompt_eval_ms", "decode_ms", "total_ms",
                      "prompt_tokens_per_second", "decode_tokens_per_second",
                      "perf_prompt_eval_ms", "perf_decode_ms"):
            _require_number(row[field], field)
        for field in ("perf_prompt_tokens", "perf_decode_tokens", "perf_reused_graphs"):
            _require_integer(row[field], field)
        timestamps = [
            _require_integer(row[field], field)
            for field in (
                "started_at_ns", "prompt_started_at_ns", "prompt_completed_at_ns",
            )
        ]
        if first_token is not None:
            timestamps.append(_require_integer(first_token, "first_token_at_ns"))
        timestamps.append(_require_integer(row["completed_at_ns"], "completed_at_ns"))
        if timestamps != sorted(timestamps):
            raise ValueError("direct monotonic timestamps are out of order")
        if not isinstance(row["created_at_utc"], str) or not row["created_at_utc"]:
            raise ValueError("direct created_at_utc must be non-empty text")
        forbidden = {"expected", "must_preserve", "expected_output", "guarded_output"}
        if forbidden & row.keys():
            raise ValueError("direct results contain prohibited expected-output evidence")

    _single(rows, "run_id")
    _single(rows, "model_load_ms")
    config = _single(rows, "requested_config")
    if not isinstance(config, dict):
        raise ValueError("requested_config must be an object")
    expected_config_fields = {
        "context_tokens", "generation_threads", "batch_threads", "batch_size",
        "micro_batch_size", "use_mmap", "flash_attention", "gpu_layers",
    }
    if set(config) != expected_config_fields:
        raise ValueError("requested_config fields are incomplete or unexpected")
    for field in (
        "context_tokens", "generation_threads", "batch_threads", "batch_size",
        "micro_batch_size", "gpu_layers",
    ):
        _require_integer(config[field], f"requested_config.{field}")
    if config["context_tokens"] != 2560:
        raise ValueError("direct context must match the 2560-token LEAP winner")
    if config["generation_threads"] not in {2, 3, 4, 6, 8}:
        raise ValueError("unapproved direct generation threads")
    if config["batch_threads"] not in {2, 4, 6, 8}:
        raise ValueError("unapproved direct batch threads")
    if config["batch_size"] not in {128, 256, 512} or config["micro_batch_size"] not in {128, 256, 512}:
        raise ValueError("unapproved direct batch sizing")
    if config["micro_batch_size"] > config["batch_size"]:
        raise ValueError("direct micro-batch exceeds batch")
    if config["use_mmap"] is not True or not isinstance(config["flash_attention"], bool):
        raise ValueError("direct mmap/flash flags must be booleans")
    if config["gpu_layers"] != 0:
        raise ValueError("direct CPU results must use zero GPU layers")
    for row in rows:
        if row["prompt_token_count"] + row["requested_max_output_tokens"] > config["context_tokens"]:
            raise ValueError("direct request exceeds configured context")

    app_build = _single(rows, "app_build")
    if not isinstance(app_build, dict) or app_build.get("llama_cpp_revision") != LLAMA_REVISION:
        raise ValueError("direct llama.cpp revision mismatch")
    if app_build.get("ndk_version") != "28.0.13004108" or app_build.get("cmake_version") != "3.31.6":
        raise ValueError("direct native toolchain pin mismatch")
    if app_build.get("build_type") != "release":
        raise ValueError("direct evidence must use the release native build")
    if app_build.get("application_id") != APPLICATION_ID:
        raise ValueError("direct application identity mismatch")

    native_info = _single(rows, "native_model_info")
    if not isinstance(native_info, dict):
        raise ValueError("native_model_info must be an object")
    native_expected = {
        "schema_version": 1,
        "model_size_bytes": MODEL_SIZE_BYTES,
        "context_size": config["context_tokens"],
        "batch_size": config["batch_size"],
        "micro_batch_size": config["micro_batch_size"],
        "threads": config["generation_threads"],
        "threads_batch": config["batch_threads"],
        "use_mmap": config["use_mmap"],
        "flash_attention": config["flash_attention"],
        "gpu_layers": config["gpu_layers"],
        "supports_enable_thinking": True,
        "fixed_prompt_tokens": FIXED_PROMPT_TOKENS,
        "llama_version": LLAMA_VERSION,
        "llama_build_number": LLAMA_BUILD_NUMBER,
        "llama_commit": LLAMA_REVISION,
        "llama_build_target": "Android aarch64",
        "native_build_type": "Release",
    }
    for field, expected in native_expected.items():
        if native_info.get(field) != expected:
            raise ValueError(f"native model info mismatch: {field}")
    if native_info.get("supports_mmap") is not True:
        raise ValueError("native model does not report mmap support")
    if native_info.get("supports_gpu_offload") is not False:
        raise ValueError("direct CPU backend unexpectedly reports GPU offload")
    backends = native_info.get("backend_names")
    if backends != ["CPU"]:
        raise ValueError("native backend list must be exactly CPU")
    if native_info.get("selected_cpu_backend_library") not in PINNED_CPU_BACKEND_LIBRARIES:
        raise ValueError("native selected CPU backend is not a packaged ARM variant")
    for field in ("model_description", "chat_template", "system_info",
                  "native_compiler", "native_compile_flags"):
        if not isinstance(native_info.get(field), str) or not native_info[field]:
            raise ValueError(f"native model info has invalid {field}")

    measured = [row for row in rows if row["phase"] == "measured"]
    if not measured:
        raise ValueError("direct results have no measured rows")
    membership = Counter((row["case_id"], row["repeat_index"]) for row in measured)
    if any(count != 1 for count in membership.values()):
        raise ValueError("direct measured case/repeat membership is duplicated")
    repeats_by_case: dict[str, set[int]] = defaultdict(set)
    for row in measured:
        _require_integer(row["repeat_index"], "repeat_index")
        repeats_by_case[row["case_id"]].add(row["repeat_index"])
    repeat_sets = {tuple(sorted(values)) for values in repeats_by_case.values()}
    if len(repeat_sets) != 1 or not repeat_sets:
        raise ValueError("direct cases have inconsistent repeat membership")
    repeat_set = next(iter(repeat_sets))
    if repeat_set != tuple(range(len(repeat_set))):
        raise ValueError("direct repeat indices must be complete and zero-based")
    case_evidence: dict[str, set[str]] = defaultdict(set)
    for row in measured:
        case_evidence[row["case_id"]].add(json.dumps(
            {"raw_text": row["raw_text"], "categories": row["categories"]},
            sort_keys=True,
        ))
    if any(len(values) != 1 for values in case_evidence.values()):
        raise ValueError("direct case input metadata changes across repeats")
    return measured


def compare_control(direct: list[dict[str, Any]], control: list[dict[str, Any]]) -> dict[str, Any]:
    control_measured = [row for row in control if row.get("phase") == "measured"]
    direct_map = {(row["case_id"], row["repeat_index"]): row for row in direct}
    control_map = {(row.get("case_id"), row.get("repeat_index")): row for row in control_measured}
    if len(control_map) != len(control_measured):
        raise ValueError("control measured case/repeat membership is duplicated")
    if direct_map.keys() != control_map.keys():
        raise ValueError("direct and control case/repeat membership differs")
    differences: list[dict[str, Any]] = []
    for key in sorted(direct_map):
        candidate = direct_map[key]
        baseline = control_map[key]
        if baseline.get("model_sha256") != MODEL_SHA256:
            raise ValueError("control model identity mismatch")
        if (
            baseline.get("context_size") != 2_560
            or baseline.get("resolved_cpu_threads") != 2
            or baseline.get("cache_enabled") is not False
            or baseline.get("mmap_enabled") is not True
        ):
            raise ValueError("control is not the matched LEAP winner configuration")
        if baseline.get("raw_text") != candidate["raw_text"]:
            raise ValueError(f"raw transcript mismatch for {key}")
        if baseline.get("prompt_tokens") != candidate["prompt_token_count"]:
            raise ValueError(f"prompt-token mismatch for {key}")
        if baseline.get("requested_max_output_tokens") != candidate["requested_max_output_tokens"]:
            raise ValueError(f"output-cap mismatch for {key}")
        if baseline.get("raw_model_output") != candidate["raw_output"]:
            differences.append({"case_id": key[0], "repeat_index": key[1]})
    return {
        "requests": len(direct_map),
        "raw_output_matches": len(direct_map) - len(differences),
        "raw_output_differences": differences,
        "prompt_token_matches": len(direct_map),
        "output_cap_matches": len(direct_map),
    }


def summarize(rows: list[dict[str, Any]], control: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    measured = validate_direct(rows)
    by_case: dict[str, set[str]] = defaultdict(set)
    for row in measured:
        by_case[row["case_id"]].add(row["raw_output"])
    result: dict[str, Any] = {
        "schema_version": 1,
        "run_id": measured[0]["run_id"],
        "model_sha256": MODEL_SHA256,
        "model_file": MODEL_FILE,
        "measured_requests": len(measured),
        "cases": len(by_case),
        "unstable_case_ids": sorted(case_id for case_id, outputs in by_case.items() if len(outputs) != 1),
        "token_cap_finishes": sum(bool(row["hit_token_cap"]) for row in measured),
        "blank_outputs": sum(not row["raw_output"].strip() for row in measured),
        "requested_config": measured[0]["requested_config"],
        "native_model_info": measured[0]["native_model_info"],
        "app_build": measured[0]["app_build"],
        "model_load_ms": measured[0]["model_load_ms"],
        "ttft_ms": distribution([
            (row["first_token_at_ns"] - row["started_at_ns"]) / 1_000_000.0
            for row in measured if row["first_token_at_ns"] is not None
        ]) if any(row["first_token_at_ns"] is not None for row in measured) else None,
        "total_ms": distribution([float(row["total_ms"]) for row in measured]),
        "prompt_eval_ms": distribution([float(row["prompt_eval_ms"]) for row in measured]),
        "decode_tokens_per_second": distribution([
            float(row["decode_tokens_per_second"]) for row in measured
        ]),
        "process_cpu_ms": distribution([float(row["process_cpu_ms"]) for row in measured]),
        "peak_pss_kb": max(row["process_pss_kb_after_inference"] for row in measured),
        "peak_native_heap_bytes": max(row["native_heap_bytes_after_inference"] for row in measured),
        "max_thermal_status": max(row["thermal_status_after_inference"] for row in measured),
    }
    if control is not None:
        result["control_parity"] = compare_control(measured, control)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("--control", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    rows = load_jsonl(args.results)
    control = load_jsonl(args.control) if args.control else None
    summary = summarize(rows, control)
    rendered = json.dumps(summary, indent=2, sort_keys=True)
    print(rendered)
    if args.json_out:
        if args.json_out.exists():
            raise ValueError(f"refusing to overwrite {args.json_out}")
        args.json_out.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"error: {error}")
