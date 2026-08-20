#!/usr/bin/env python3
"""Benchmark the pinned official S1-mini F16 and Q4_K_M GGUF artifacts.

This is a performance and quantization-agreement benchmark. It uses the exact
publisher system prompt, control-line shape, no-thinking chat-template setting,
greedy decoding, and input-relative output ceiling documented for S1-mini v1.
It does not score semantic quality or apply project guardrails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = REPO_ROOT / "docs/evaluation/cleanup_personal_conversation_v3.jsonl"
SYSTEM_PROMPT_PATH = REPO_ROOT / "docs/evaluation/prompts/s1-mini-v1-system.txt"
CONTROL_LINE = "[Styling: semi-formal] [Structure: prose] [Context: general]"
MODEL_REVISION = "8eab4779866f477ae6e7f237ca45fc2c65153f50"
MODEL_SPECS = {
    "Q4_K_M": {
        "size_bytes": 484_219_808,
        "sha256": "3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634",
    },
    "F16": {
        "size_bytes": 1_509_347_232,
        "sha256": "0370da4f1bae19e3150bcafa33c5d396c15f97bf25519540a3e013db5cc00af4",
    },
}
DEFAULT_PORT = 18081


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


def server_command(
    executable: Path, model_path: Path, alias: str, port: int
) -> list[str]:
    return [
        str(executable),
        "--model", str(model_path),
        "--alias", alias,
        "--host", "127.0.0.1",
        "--port", str(port),
        "--jinja",
        "--chat-template-kwargs", '{"enable_thinking":false}',
        "--temp", "0",
        "--no-webui",
    ]


def _request_json(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"request failed for {url}: {exc}") from exc
    if not isinstance(value, dict) or "error" in value:
        raise BenchmarkError(f"unexpected response from {url}: {value!r}")
    return value


def tokenize_count(
    base_url: str, text: str, timeout: float, *, allow_empty: bool = False
) -> int:
    value = _request_json(
        f"{base_url}/tokenize",
        {"content": text, "add_special": False},
        timeout,
    )
    tokens = value.get("tokens")
    if not isinstance(tokens, list) or any(not isinstance(item, int) for item in tokens):
        raise BenchmarkError(f"tokenize endpoint returned invalid tokens: {value!r}")
    if not tokens and not allow_empty:
        raise BenchmarkError("tokenize endpoint returned no tokens")
    return len(tokens)


def iter_sse_data(lines: Iterable[bytes]) -> Iterator[str]:
    fields: list[str] = []
    for raw_line in lines:
        line = raw_line.decode("utf-8").rstrip("\r\n")
        if not line:
            if fields:
                yield "\n".join(fields)
                fields.clear()
            continue
        if line.startswith("data:"):
            fields.append(line[5:].lstrip())
    if fields:
        yield "\n".join(fields)


def stream_completion(
    base_url: str,
    alias: str,
    system_prompt: str,
    raw: str,
    output_cap: int,
    timeout: float,
) -> dict[str, Any]:
    payload = {
        "model": alias,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{CONTROL_LINE}\n{raw}"},
        ],
        "temperature": 0,
        "max_tokens": output_cap,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    request = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started_ns = time.perf_counter_ns()
    first_token_ns: int | None = None
    parts: list[str] = []
    finish_reason: str | None = None
    usage: dict[str, Any] | None = None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for event in iter_sse_data(response):
                if event == "[DONE]":
                    break
                value = json.loads(event)
                if isinstance(value.get("usage"), dict):
                    usage = value["usage"]
                choices = value.get("choices")
                if choices == []:
                    continue
                if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                    raise BenchmarkError(f"invalid streaming choices: {value!r}")
                choice = choices[0]
                delta = choice.get("delta")
                if not isinstance(delta, dict):
                    raise BenchmarkError(f"invalid streaming delta: {value!r}")
                content = delta.get("content")
                if content:
                    if not isinstance(content, str):
                        raise BenchmarkError(f"non-string streaming content: {value!r}")
                    if first_token_ns is None:
                        first_token_ns = time.perf_counter_ns()
                    parts.append(content)
                if choice.get("finish_reason") is not None:
                    finish_reason = str(choice["finish_reason"])
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"completion request failed: {exc}") from exc
    finished_ns = time.perf_counter_ns()
    text = "".join(parts)
    return {
        "model_text": text,
        "model_text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "finish_reason": finish_reason,
        "usage": usage,
        "ttft_ms": None if first_token_ns is None else (first_token_ns - started_ns) / 1_000_000,
        "total_ms": (finished_ns - started_ns) / 1_000_000,
    }


def wait_for_health(base_url: str, process: subprocess.Popen[Any], timeout: float) -> float:
    started = time.perf_counter()
    deadline = started + timeout
    last_error = "server did not answer"
    while time.perf_counter() < deadline:
        if process.poll() is not None:
            raise BenchmarkError(f"llama-server exited with code {process.returncode}")
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1) as response:
                if 200 <= response.status < 300:
                    return (time.perf_counter() - started) * 1000
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.1)
    raise BenchmarkError(f"server did not become healthy: {last_error}")


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


def percentile(values: Sequence[float], percentile_value: float) -> float:
    if not values:
        raise BenchmarkError("cannot summarize an empty metric")
    ordered = sorted(values)
    index = max(0, math.ceil(percentile_value * len(ordered)) - 1)
    return ordered[index]


def summarize_runs(runs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    ttft = [float(row["ttft_ms"]) for row in runs if row["ttft_ms"] is not None]
    total = [float(row["total_ms"]) for row in runs]
    output_tokens = [int(row["output_tokens"]) for row in runs]
    generation_seconds = [
        max(1e-9, (float(row["total_ms"]) - float(row["ttft_ms"])) / 1000)
        for row in runs if row["ttft_ms"] is not None
    ]
    generated = [
        int(row["output_tokens"]) for row in runs if row["ttft_ms"] is not None
    ]
    throughputs = [tokens / seconds for tokens, seconds in zip(generated, generation_seconds)]
    return {
        "requests": len(runs),
        "ttft_ms": {"median": statistics.median(ttft), "p90": percentile(ttft, 0.9), "max": max(ttft)},
        "total_ms": {"median": statistics.median(total), "p90": percentile(total, 0.9), "max": max(total)},
        "output_tokens": {"median": statistics.median(output_tokens), "total": sum(output_tokens)},
        "decode_tokens_per_second": {
            "median": statistics.median(throughputs),
            "p10": percentile(throughputs, 0.1),
        },
    }


def verify_model(path: Path, quantization: str) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise BenchmarkError(f"missing {quantization} model: {resolved}")
    expected = MODEL_SPECS[quantization]
    size = resolved.stat().st_size
    if size != expected["size_bytes"]:
        raise BenchmarkError(
            f"{quantization} size mismatch: expected {expected['size_bytes']}, got {size}"
        )
    digest = sha256_file(resolved)
    if digest != expected["sha256"]:
        raise BenchmarkError(
            f"{quantization} SHA-256 mismatch: expected {expected['sha256']}, got {digest}"
        )
    return {"path": str(resolved), "size_bytes": size, "sha256": digest}


def benchmark_model(
    *,
    executable: Path,
    model_path: Path,
    quantization: str,
    cases: Sequence[Case],
    cases_path: Path,
    repeats: int,
    port: int,
    timeout: float,
    startup_timeout: float,
    output_dir: Path,
    system_prompt: str,
) -> dict[str, Any]:
    alias = f"s1-mini-v1-{quantization.lower()}"
    command = server_command(executable, model_path, alias, port)
    log_path = output_dir / f"{alias}-server.log"
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, text=True)
        try:
            with RssSampler(process.pid) as rss:
                base_url = f"http://127.0.0.1:{port}"
                load_ready_ms = wait_for_health(base_url, process, startup_timeout)
                print(
                    f"[{quantization}] server ready in {load_ready_ms:.1f} ms",
                    flush=True,
                )
                ready_rss_kib = current_rss_kib(process.pid)
                warmup_raw = "this is a short warmup transcript"
                warmup_input_tokens = tokenize_count(base_url, warmup_raw, timeout)
                warmup = stream_completion(
                    base_url,
                    alias,
                    system_prompt,
                    warmup_raw,
                    max_new_tokens(warmup_input_tokens),
                    timeout,
                )
                runs: list[dict[str, Any]] = []
                for repeat_index in range(repeats):
                    for case in cases:
                        input_tokens = tokenize_count(base_url, case.raw, timeout)
                        cap = max_new_tokens(input_tokens)
                        result = stream_completion(
                            base_url, alias, system_prompt, case.raw, cap, timeout
                        )
                        output_tokens = tokenize_count(
                            base_url, result["model_text"], timeout, allow_empty=True
                        )
                        result.update(
                            {
                                "case_id": case.case_id,
                                "repeat_index": repeat_index,
                                "input_tokens": input_tokens,
                                "max_new_tokens": cap,
                                "output_tokens": output_tokens,
                            }
                        )
                        runs.append(result)
                    print(
                        f"[{quantization}] completed repeat {repeat_index + 1}/{repeats} "
                        f"({len(cases)} cases)",
                        flush=True,
                    )
                summary = summarize_runs(runs)
                summary.update(
                    {
                        "load_to_health_ms": load_ready_ms,
                        "ready_rss_kib": ready_rss_kib,
                        "peak_sampled_rss_kib": rss.peak_kib,
                    }
                )
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    return {
        "quantization": quantization,
        "started_at_utc": started_at,
        "model": verify_model(model_path, quantization),
        "server_command": command,
        "server_log": str(log_path),
        "warmup": warmup,
        "summary": summary,
        "runs": runs,
        "cases_path": str(cases_path),
    }


def compare_outputs(results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if len(results) != 2:
        raise BenchmarkError("output comparison requires exactly two model results")
    left, right = results
    left_map = {
        (row["case_id"], row["repeat_index"]): row["model_text"] for row in left["runs"]
    }
    right_map = {
        (row["case_id"], row["repeat_index"]): row["model_text"] for row in right["runs"]
    }
    if left_map.keys() != right_map.keys():
        raise BenchmarkError("model runs have different case/repeat membership")
    differing = [
        {"case_id": key[0], "repeat_index": key[1]}
        for key in sorted(left_map)
        if left_map[key] != right_map[key]
    ]
    stability: dict[str, Any] = {}
    for result in results:
        by_case: dict[str, set[str]] = {}
        for row in result["runs"]:
            by_case.setdefault(row["case_id"], set()).add(row["model_text"])
        unstable = sorted(case_id for case_id, outputs in by_case.items() if len(outputs) != 1)
        stability[result["quantization"]] = {
            "stable_cases": len(by_case) - len(unstable),
            "total_cases": len(by_case),
            "unstable_case_ids": unstable,
        }
    total = len(left_map)
    return {
        "exact_agreement_requests": total - len(differing),
        "total_requests": total,
        "exact_agreement_rate": (total - len(differing)) / total,
        "differing_requests": differing,
        "repeat_stability": stability,
    }


def executable_version(path: Path) -> str:
    completed = subprocess.run(
        [str(path), "--version"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.stdout.strip()


def write_result(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--q4-path", required=True, type=Path)
    parser.add_argument("--f16-path", required=True, type=Path)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--llama-server", default="llama-server")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--startup-timeout", type=float, default=180)
    return parser


def run(arguments: argparse.Namespace) -> int:
    if arguments.repeats <= 0:
        raise BenchmarkError("--repeats must be positive")
    if not 1 <= arguments.port <= 65535:
        raise BenchmarkError("--port must be between 1 and 65535")
    executable_value = subprocess.run(
        ["which", arguments.llama_server],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ).stdout.strip()
    if not executable_value:
        raise BenchmarkError(f"cannot find llama-server executable {arguments.llama_server!r}")
    executable = Path(executable_value).resolve()
    cases_path = arguments.cases.resolve()
    cases = read_cases(cases_path)
    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
    model_paths = {
        "Q4_K_M": arguments.q4_path.resolve(),
        "F16": arguments.f16_path.resolve(),
    }
    for quantization, path in model_paths.items():
        verify_model(path, quantization)

    output = arguments.output.resolve()
    if output.exists():
        raise BenchmarkError(f"output already exists: {output}")
    output_dir = (
        arguments.output_dir.resolve()
        if arguments.output_dir is not None
        else output.parent
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": "s1-mini-performance-benchmark-v1",
        "status": "running",
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scope": "performance and F16/Q4_K_M raw-output agreement; no semantic scoring",
        "host": {"platform": platform.platform(), "python": sys.version},
        "runtime": {"path": str(executable), "version": executable_version(executable)},
        "publisher_configuration": {
            "model_revision": MODEL_REVISION,
            "system_prompt_path": str(SYSTEM_PROMPT_PATH),
            "system_prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
            "control_line": CONTROL_LINE,
            "chat_template_kwargs": {"enable_thinking": False},
            "temperature": 0,
            "output_cap": "ceil(1.3 * raw transcript token count + 32)",
            "warmup_excluded": True,
        },
        "cases": {
            "path": str(cases_path),
            "sha256": sha256_file(cases_path),
            "count": len(cases),
            "repeats": arguments.repeats,
        },
        "models": [],
    }
    write_result(output, report)
    try:
        for quantization in ("Q4_K_M", "F16"):
            result = benchmark_model(
                executable=executable,
                model_path=model_paths[quantization],
                quantization=quantization,
                cases=cases,
                cases_path=cases_path,
                repeats=arguments.repeats,
                port=arguments.port,
                timeout=arguments.timeout,
                startup_timeout=arguments.startup_timeout,
                output_dir=output_dir,
                system_prompt=system_prompt,
            )
            report["models"].append(result)
            write_result(output, report)
        report["comparison"] = compare_outputs(report["models"])
        report["status"] = "complete"
        report["completed_at_utc"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        write_result(output, report)
        print(json.dumps({
            "output": str(output),
            "status": report["status"],
            "comparison": report["comparison"],
            "summaries": {
                model["quantization"]: model["summary"] for model in report["models"]
            },
        }, ensure_ascii=False, indent=2))
        return 0
    except BaseException as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        write_result(output, report)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        return run(arguments)
    except BenchmarkError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
