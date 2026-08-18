#!/usr/bin/env python3
"""Run N concurrent cleanup-evaluation clients against one OpenAI endpoint."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
RUNNER = SCRIPT_DIR / "run-cleanup-openai.py"
MERGER = SCRIPT_DIR / "merge-cleanup-openai-shards.py"


class LaunchError(Exception):
    """A launcher preflight or child-process failure."""


def completed_token_usage(paths: Sequence[Path]) -> tuple[int, int, int]:
    """Return request/input/output totals from complete flushed JSONL records."""

    requests = prompt_tokens = completion_tokens = 0
    for path in paths:
        if not path.exists():
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise LaunchError(f"cannot read token usage from {path}: {exc}") from exc
        # A child may be between writing the JSON object and its newline. Ignore
        # only that final unflushed fragment; every earlier line must be valid.
        complete = data if data.endswith(b"\n") else data.rsplit(b"\n", 1)[0]
        for line_number, line in enumerate(complete.splitlines(), 1):
            if not line:
                raise LaunchError(f"{path}:{line_number}: blank result record")
            try:
                row = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise LaunchError(
                    f"{path}:{line_number}: invalid completed result record: {exc}"
                ) from exc
            current_prompt = row.get("prompt_tokens")
            current_completion = row.get("completion_tokens")
            if (
                isinstance(current_prompt, bool)
                or not isinstance(current_prompt, int)
                or current_prompt < 0
                or isinstance(current_completion, bool)
                or not isinstance(current_completion, int)
                or current_completion < 0
            ):
                raise LaunchError(
                    f"{path}:{line_number}: non-negative token counts are required"
                )
            requests += 1
            prompt_tokens += current_prompt
            completion_tokens += current_completion
    return requests, prompt_tokens, completion_tokens


def shard_path(output_dir: Path, shard_index: int, shard_count: int) -> Path:
    width = max(2, len(str(shard_count - 1)))
    return output_dir / (
        f"shard-{shard_index:0{width}d}-of-{shard_count:0{width}d}.jsonl"
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="validated merged JSONL")
    parser.add_argument("--clients", type=int, required=True)
    parser.add_argument("--quantization", default="bf16-lora")
    parser.add_argument("--prompt-variant", default="cleanup_instruction_v2")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--request-extra", type=Path)
    parser.add_argument(
        "--output-token-field",
        choices=("max_tokens", "max_completion_tokens"),
        default="max_tokens",
        help="request field used for each case's fixed output cap",
    )
    parser.add_argument(
        "--output-cap-policy",
        choices=("android", "publisher"),
        default="android",
    )
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--retries", type=int, default=0)
    parser.add_argument("--retry-delay", type=float, default=0.5)
    parser.add_argument(
        "--token-progress-seconds",
        type=float,
        default=0.0,
        help="print aggregate API-reported token totals at this interval; 0 disables",
    )
    parser.add_argument("--token-offset-input", type=int, default=0)
    parser.add_argument("--token-offset-output", type=int, default=0)
    parser.add_argument(
        "--max-campaign-tokens",
        type=int,
        help="stop all clients when completed run tokens plus offsets reach this total",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="per-shard progress interval; 0 disables progress output",
    )
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-stream", action="store_true")
    parser.add_argument("--omit-seed", action="store_true")
    return parser


def _runner_command(arguments: argparse.Namespace, shard_index: int) -> list[str]:
    command = [
        sys.executable,
        str(RUNNER),
        "--model",
        arguments.model,
        "--base-url",
        arguments.base_url,
        "--cases",
        str(arguments.cases),
        "--output",
        str(shard_path(arguments.output_dir, shard_index, arguments.clients)),
        "--quantization",
        arguments.quantization,
        "--prompt-variant",
        arguments.prompt_variant,
        "--temperature",
        str(arguments.temperature),
        "--api-key-env",
        arguments.api_key_env,
        "--timeout",
        str(arguments.timeout),
        "--retries",
        str(arguments.retries),
        "--retry-delay",
        str(arguments.retry_delay),
        "--progress-every",
        str(arguments.progress_every),
        "--output-token-field",
        arguments.output_token_field,
        "--output-cap-policy",
        arguments.output_cap_policy,
        "--shard-count",
        str(arguments.clients),
        "--shard-index",
        str(shard_index),
    ]
    command.append("--raw-scoring")
    if arguments.resume:
        command.append("--resume")
    if arguments.no_stream:
        command.append("--no-stream")
    if arguments.omit_seed:
        command.append("--omit-seed")
    if arguments.request_extra is not None:
        command.extend(("--request-extra", str(arguments.request_extra)))
    for case_id in arguments.case_id:
        command.extend(("--case-id", case_id))
    return command


def _merge_command(arguments: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(MERGER),
        "--cases",
        str(arguments.cases),
        "--shard-count",
        str(arguments.clients),
        "--output",
        str(arguments.output),
    ]
    for index in range(arguments.clients):
        command.extend(
            ("--input", str(shard_path(arguments.output_dir, index, arguments.clients)))
        )
    for case_id in arguments.case_id:
        command.extend(("--case-id", case_id))
    return command


def run(arguments: argparse.Namespace) -> int:
    if arguments.clients <= 0:
        raise LaunchError("--clients must be positive")
    if arguments.progress_every < 0:
        raise LaunchError("--progress-every must not be negative")
    if arguments.token_progress_seconds < 0:
        raise LaunchError("--token-progress-seconds must not be negative")
    if arguments.token_offset_input < 0 or arguments.token_offset_output < 0:
        raise LaunchError("token offsets must not be negative")
    if arguments.max_campaign_tokens is not None and arguments.max_campaign_tokens <= 0:
        raise LaunchError("--max-campaign-tokens must be positive")
    if arguments.output.exists():
        raise LaunchError(f"refusing to overwrite merged output {arguments.output}")
    if arguments.output_dir.exists() and not arguments.output_dir.is_dir():
        raise LaunchError(f"--output-dir is not a directory: {arguments.output_dir}")
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    paths = [
        shard_path(arguments.output_dir, index, arguments.clients)
        for index in range(arguments.clients)
    ]
    if len(set(paths)) != len(paths) or arguments.output in paths:
        raise LaunchError("output paths are not collision-free")

    processes: list[tuple[int, subprocess.Popen[bytes]]] = []

    def report_tokens() -> int:
        requests, prompt_tokens, completion_tokens = completed_token_usage(paths)
        campaign_input = arguments.token_offset_input + prompt_tokens
        campaign_output = arguments.token_offset_output + completion_tokens
        campaign_total = campaign_input + campaign_output
        print(
            "[tokens "
            f"requests={requests} run_input={prompt_tokens} run_output={completion_tokens} "
            f"campaign_input={campaign_input} campaign_output={campaign_output} "
            f"campaign_total={campaign_total}]",
            file=sys.stderr,
            flush=True,
        )
        return campaign_total

    def stop_running() -> None:
        for _, process in processes:
            if process.poll() is None:
                process.terminate()
        for _, process in processes:
            process.wait()

    try:
        for index in range(arguments.clients):
            process = subprocess.Popen(_runner_command(arguments, index))
            processes.append((index, process))
        next_token_report = time.monotonic()
        while any(process.poll() is None for _, process in processes):
            now = time.monotonic()
            if arguments.token_progress_seconds and now >= next_token_report:
                campaign_total = report_tokens()
                next_token_report = now + arguments.token_progress_seconds
                if (
                    arguments.max_campaign_tokens is not None
                    and campaign_total >= arguments.max_campaign_tokens
                ):
                    stop_running()
                    raise LaunchError(
                        "campaign token limit reached; completed shard records were preserved"
                    )
            time.sleep(0.25)
        failures = [
            (index, return_code)
            for index, process in processes
            if (return_code := process.poll())
        ]
        if arguments.token_progress_seconds:
            report_tokens()
    except KeyboardInterrupt:
        stop_running()
        raise LaunchError("interrupted; completed shard records were preserved")

    if failures:
        details = ", ".join(f"shard {index}: exit {code}" for index, code in failures)
        raise LaunchError(
            f"one or more shard clients failed ({details}); merge skipped; rerun with --resume"
        )
    merge = subprocess.run(_merge_command(arguments), check=False)
    if merge.returncode:
        raise LaunchError(
            f"all clients exited zero but validated merge failed with exit {merge.returncode}"
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    arguments = parser.parse_args(argv)
    try:
        return run(arguments)
    except (LaunchError, OSError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
