#!/usr/bin/env python3
"""Benchmark pinned S1-mini BF16 weights with the publisher's Transformers path.

This is a host performance and raw-output-agreement probe. It uses the exact
publisher prompt, control line, BF16 auto-dtype loading, no-thinking template,
greedy decoding, and input-relative output ceiling. It does not read expected
answers, score semantic quality, or apply project guardrails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = REPO_ROOT / "docs/evaluation/cleanup_personal_conversation_v3.jsonl"
SYSTEM_PROMPT_PATH = REPO_ROOT / "docs/evaluation/prompts/s1-mini-v1-system.txt"
CONTROL_LINE = "[Styling: semi-formal] [Structure: prose] [Context: general]"
MODEL_REVISION = "65f84bcda1d13df582c4a8443c1c5aa53c0c66db"
MODEL_FILENAME = "model.safetensors"
MODEL_SIZE_BYTES = 1_503_300_328
MODEL_SHA256 = "69d2057077ab4dc738aaaab75d2a8ffa141e3a09fb9d956198cfce46f381131a"


class BenchmarkError(Exception):
    """A reproducible benchmark failure."""


@dataclass(frozen=True)
class Case:
    case_id: str
    raw: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_cases(path: Path) -> list[Case]:
    cases: list[Case] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BenchmarkError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
            case_id = row.get("id")
            raw = row.get("raw")
            if not isinstance(case_id, str) or not case_id:
                raise BenchmarkError(f"{path}:{line_number}: id must be a non-empty string")
            if not isinstance(raw, str) or not raw:
                raise BenchmarkError(f"{path}:{line_number}: raw must be a non-empty string")
            if case_id in seen:
                raise BenchmarkError(f"{path}:{line_number}: duplicate id {case_id!r}")
            seen.add(case_id)
            cases.append(Case(case_id, raw))
    if not cases:
        raise BenchmarkError(f"no cases in {path}")
    return cases


def max_new_tokens(input_tokens: int) -> int:
    if input_tokens <= 0:
        raise BenchmarkError("input token count must be positive")
    return math.ceil(1.3 * input_tokens + 32)


def percentile(values: Sequence[float], percentile_value: float) -> float:
    if not values:
        raise BenchmarkError("cannot summarize an empty metric")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile_value * len(ordered)) - 1)]


def current_rss_kib(pid: int) -> int | None:
    completed = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(pid)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        return int(completed.stdout.strip())
    except ValueError:
        return None


class RssSampler:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.peak_kib = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            value = current_rss_kib(self.pid)
            if value is not None:
                self.peak_kib = max(self.peak_kib, value)
            self._stop.wait(0.05)

    def __enter__(self) -> "RssSampler":
        self._thread.start()
        return self

    def __exit__(self, *unused: object) -> None:
        self._stop.set()
        self._thread.join(timeout=2)


def verify_model(model_dir: Path) -> dict[str, Any]:
    resolved = model_dir.expanduser().resolve()
    model_path = resolved / MODEL_FILENAME
    if not model_path.is_file():
        raise BenchmarkError(f"missing BF16 model: {model_path}")
    size = model_path.stat().st_size
    if size != MODEL_SIZE_BYTES:
        raise BenchmarkError(
            f"BF16 size mismatch: expected {MODEL_SIZE_BYTES}, got {size}"
        )
    digest = sha256_file(model_path)
    if digest != MODEL_SHA256:
        raise BenchmarkError(
            f"BF16 SHA-256 mismatch: expected {MODEL_SHA256}, got {digest}"
        )
    return {"directory": str(resolved), "size_bytes": size, "sha256": digest}


def run_completion(
    *, tokenizer: Any, model: Any, raw: str, timeout: float
) -> dict[str, Any]:
    from transformers import TextIteratorStreamer

    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{CONTROL_LINE}\n{raw}"},
    ]
    rendered = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    inputs = tokenizer(rendered, return_tensors="pt")
    input_tokens = len(tokenizer(raw, add_special_tokens=False).input_ids)
    output_cap = max_new_tokens(input_tokens)
    streamer = TextIteratorStreamer(
        tokenizer,
        skip_prompt=True,
        skip_special_tokens=True,
        timeout=timeout,
    )
    failure: list[BaseException] = []

    def generate() -> None:
        try:
            model.generate(
                **inputs,
                max_new_tokens=output_cap,
                do_sample=False,
                streamer=streamer,
            )
        except BaseException as exc:
            failure.append(exc)
            streamer.on_finalized_text("", stream_end=True)

    started_ns = time.perf_counter_ns()
    worker = threading.Thread(target=generate)
    worker.start()
    first_text_ns: int | None = None
    parts: list[str] = []
    for piece in streamer:
        if piece and first_text_ns is None:
            first_text_ns = time.perf_counter_ns()
        parts.append(piece)
    worker.join(timeout=timeout)
    if worker.is_alive():
        raise BenchmarkError("generation thread exceeded timeout")
    if failure:
        raise BenchmarkError(f"generation failed: {failure[0]}")
    finished_ns = time.perf_counter_ns()
    text = "".join(parts)
    output_tokens = len(tokenizer(text, add_special_tokens=False).input_ids)
    return {
        "model_text": text,
        "model_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "input_tokens": input_tokens,
        "max_new_tokens": output_cap,
        "output_tokens": output_tokens,
        "ttft_ms": None
        if first_text_ns is None
        else (first_text_ns - started_ns) / 1_000_000,
        "total_ms": (finished_ns - started_ns) / 1_000_000,
    }


def summarize(runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    ttft = [float(run["ttft_ms"]) for run in runs if run["ttft_ms"] is not None]
    total = [float(run["total_ms"]) for run in runs]
    tokens = [int(run["output_tokens"]) for run in runs]
    return {
        "requests": len(runs),
        "ttft_ms": {
            "median": statistics.median(ttft),
            "p90": percentile(ttft, 0.9),
            "max": max(ttft),
        },
        "total_ms": {
            "median": statistics.median(total),
            "p90": percentile(total, 0.9),
            "max": max(total),
        },
        "output_tokens": {"median": statistics.median(tokens), "total": sum(tokens)},
    }


def compare_q4_outputs(bf16_runs: Sequence[dict[str, Any]], q4_result: Path) -> dict[str, Any]:
    value = json.loads(q4_result.read_text(encoding="utf-8"))
    q4_models = [model for model in value.get("models", []) if model.get("quantization") == "Q4_K_M"]
    if len(q4_models) != 1:
        raise BenchmarkError("Q4 result must contain exactly one Q4_K_M model")
    q4_map = {
        (run["case_id"], run["repeat_index"]): run["model_text"]
        for run in q4_models[0]["runs"]
    }
    bf16_map = {
        (run["case_id"], run["repeat_index"]): run["model_text"]
        for run in bf16_runs
    }
    if q4_map.keys() != bf16_map.keys():
        raise BenchmarkError("BF16 and Q4 results have different case/repeat membership")
    differing = [
        {"case_id": key[0], "repeat_index": key[1]}
        for key in sorted(q4_map)
        if q4_map[key] != bf16_map[key]
    ]
    total = len(q4_map)
    return {
        "q4_result_path": str(q4_result.resolve()),
        "q4_result_sha256": sha256_file(q4_result),
        "exact_agreement_requests": total - len(differing),
        "total_requests": total,
        "exact_agreement_rate": (total - len(differing)) / total,
        "differing_requests": differing,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--q4-result", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=180)
    return parser


def run(arguments: argparse.Namespace) -> int:
    if arguments.repeats <= 0:
        raise BenchmarkError("--repeats must be positive")
    output = arguments.output.resolve()
    if output.exists():
        raise BenchmarkError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    model_identity = verify_model(arguments.model_dir)
    cases_path = arguments.cases.resolve()
    cases = read_cases(cases_path)

    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer

    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    process_rss_before_load_kib = current_rss_kib(os.getpid())
    with RssSampler(os.getpid()) as rss:
        load_started = time.perf_counter()
        tokenizer = AutoTokenizer.from_pretrained(
            model_identity["directory"], local_files_only=True
        )
        tokenizer_loaded = time.perf_counter()
        model = AutoModelForCausalLM.from_pretrained(
            model_identity["directory"], torch_dtype="auto", local_files_only=True
        )
        model.eval()
        model_loaded = time.perf_counter()
        ready_rss_kib = current_rss_kib(os.getpid())
        parameter_dtypes = sorted({str(parameter.dtype) for parameter in model.parameters()})

        warmup = run_completion(
            tokenizer=tokenizer,
            model=model,
            raw="this is a short warmup transcript",
            timeout=arguments.timeout,
        )
        runs: list[dict[str, Any]] = []
        for repeat_index in range(arguments.repeats):
            for case in cases:
                result = run_completion(
                    tokenizer=tokenizer,
                    model=model,
                    raw=case.raw,
                    timeout=arguments.timeout,
                )
                result.update({"case_id": case.case_id, "repeat_index": repeat_index})
                runs.append(result)
            print(
                f"[BF16] completed repeat {repeat_index + 1}/{arguments.repeats} "
                f"({len(cases)} cases)",
                flush=True,
            )

        summary = summarize(runs)
        summary.update(
            {
                "tokenizer_load_ms": (tokenizer_loaded - load_started) * 1000,
                "model_load_ms": (model_loaded - tokenizer_loaded) * 1000,
                "total_load_ms": (model_loaded - load_started) * 1000,
                "process_rss_before_load_kib": process_rss_before_load_kib,
                "ready_rss_kib": ready_rss_kib,
                "peak_sampled_rss_kib": rss.peak_kib,
            }
        )

    report: dict[str, Any] = {
        "schema_version": "s1-mini-bf16-performance-benchmark-v1",
        "status": "complete",
        "scope": "BF16 host performance and Q4_K_M raw-output agreement; no semantic scoring",
        "started_at_utc": started_at,
        "completed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": {"platform": platform.platform(), "python": sys.version},
        "runtime": {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "torch_threads": torch.get_num_threads(),
            "device": "cpu",
        },
        "publisher_configuration": {
            "model_revision": MODEL_REVISION,
            "torch_dtype": "auto",
            "loaded_parameter_dtypes": parameter_dtypes,
            "system_prompt_path": str(SYSTEM_PROMPT_PATH),
            "system_prompt_sha256": hashlib.sha256(
                SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip().encode("utf-8")
            ).hexdigest(),
            "control_line": CONTROL_LINE,
            "enable_thinking": False,
            "do_sample": False,
            "output_cap": "ceil(1.3 * raw transcript token count + 32)",
            "warmup_excluded": True,
        },
        "model": model_identity,
        "cases": {
            "path": str(cases_path),
            "sha256": sha256_file(cases_path),
            "count": len(cases),
            "repeats": arguments.repeats,
        },
        "warmup": warmup,
        "summary": summary,
        "runs": runs,
    }
    if arguments.q4_result is not None:
        report["q4_comparison"] = compare_q4_outputs(runs, arguments.q4_result.resolve())
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "summary": summary, "q4_comparison": report.get("q4_comparison")}, indent=2))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        return run(arguments)
    except BenchmarkError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
