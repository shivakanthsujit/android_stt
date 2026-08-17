#!/usr/bin/env python3
"""Start llama-server and screen one local GGUF on both frozen cleanup corpora.

This is orchestration only: decoding, prompt construction, Android-equivalent
guardrails, and scoring remain owned by run-cleanup-openai.py and
score-cleanup-results.py. No model is downloaded by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts/run-cleanup-openai.py"
SCORER = REPO_ROOT / "scripts/score-cleanup-results.py"
VOICEINK_PROMPT = (
    REPO_ROOT / "docs/evaluation/prompts/voiceink-qwen35-2b-system-v1.txt"
)
CORPORA = (
    ("seed", REPO_ROOT / "docs/evaluation/cleanup_cases.jsonl"),
    ("heldout-v1", REPO_ROOT / "docs/evaluation/cleanup_cases_heldout_v1.jsonl"),
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "build/evaluation-results"
DEFAULT_PORT = 18080
DEFAULT_PROMPT_VARIANT = "few_shot_corrections"
DEFAULT_TEMPERATURE = 0.1


class ScreenError(Exception):
    """A user-facing orchestration or validation error."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_executable(value: str) -> Path:
    resolved = shutil.which(value)
    if resolved is None:
        raise ScreenError(f"cannot find executable: {value}")
    return Path(resolved).resolve()


def output_paths(output_dir: Path, run_name: str) -> dict[str, Path]:
    paths = {
        "provenance": output_dir / f"{run_name}-provenance.json",
        "server_log": output_dir / f"{run_name}-server.log",
    }
    for corpus_name, _ in CORPORA:
        paths[f"result_{corpus_name}"] = output_dir / f"{run_name}-{corpus_name}.jsonl"
        paths[f"score_{corpus_name}"] = output_dir / f"{run_name}-{corpus_name}-score.json"
    return paths


def server_command(
    executable: Path,
    model_path: Path,
    model_name: str,
    port: int,
    server_args: Sequence[str],
) -> list[str]:
    return [
        str(executable),
        "--model",
        str(model_path),
        "--alias",
        model_name,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        *server_args,
    ]


def runner_command(
    *,
    model_name: str,
    quantization: str,
    port: int,
    corpus: Path,
    output: Path,
    prompt_variant: str,
    temperature: float,
    request_extra: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(RUNNER),
        "--base-url",
        f"http://127.0.0.1:{port}/v1",
        "--model",
        model_name,
        "--quantization",
        quantization,
        "--cases",
        str(corpus),
        "--output",
        str(output),
        "--prompt-variant",
        prompt_variant,
        "--temperature",
        str(temperature),
    ]
    if request_extra is not None:
        command.extend(("--request-extra", str(request_extra)))
    return command


def scorer_command(corpus: Path, result: Path) -> list[str]:
    return [
        sys.executable,
        str(SCORER),
        "--cases",
        str(corpus),
        "--format",
        "json",
        str(result),
    ]


def command_version(executable: Path) -> str:
    completed = subprocess.run(
        [str(executable), "--version"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return completed.stdout.strip()


def prompt_provenance(prompt_variant: str) -> dict[str, Any]:
    value: dict[str, Any] = {"variant": prompt_variant}
    if prompt_variant == "voiceink_task_tuned":
        value.update(
            {
                "path": str(VOICEINK_PROMPT),
                "sha256": sha256_file(VOICEINK_PROMPT),
            }
        )
    return value


def wait_for_server(port: int, process: subprocess.Popen[Any], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    health_url = f"http://127.0.0.1:{port}/health"
    last_error = "server did not answer"
    while time.monotonic() < deadline:
        return_code = process.poll()
        if return_code is not None:
            raise ScreenError(f"llama-server exited during startup with code {return_code}")
        try:
            with urllib.request.urlopen(health_url, timeout=1.0) as response:
                if 200 <= response.status < 300:
                    return
                last_error = f"health endpoint returned HTTP {response.status}"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = str(exc)
        time.sleep(0.25)
    raise ScreenError(f"llama-server was not ready after {timeout:g}s: {last_error}")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def run_checked(command: Sequence[str], *, stdout: Any = None) -> None:
    completed = subprocess.run(command, stdout=stdout, check=False)
    if completed.returncode != 0:
        raise ScreenError(
            f"command failed with exit code {completed.returncode}: "
            + " ".join(command)
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--model-name", required=True, help="stable model label/API alias")
    parser.add_argument("--quantization", required=True, help="for example Q4_K_M")
    parser.add_argument("--run-name", required=True, help="filename prefix for this run")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--llama-server", default="llama-server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--startup-timeout", type=float, default=180.0)
    parser.add_argument(
        "--server-arg",
        action="append",
        default=[],
        help="extra llama-server argument; use --server-arg=VALUE for values beginning '-'",
    )
    parser.add_argument("--request-extra", type=Path)
    parser.add_argument(
        "--prompt-variant",
        default=DEFAULT_PROMPT_VARIANT,
        choices=(
            "baseline_rules",
            "isolated_rules",
            "command_envelope",
            "strict_minimal_edit",
            "few_shot_corrections",
            "voiceink_task_tuned",
        ),
    )
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def run(arguments: argparse.Namespace) -> int:
    model_path = arguments.model_path.expanduser().resolve()
    if not model_path.is_file():
        raise ScreenError(f"--model-path is not a file: {model_path}")
    if not arguments.model_name.strip() or not arguments.run_name.strip():
        raise ScreenError("--model-name and --run-name must not be empty")
    if "/" in arguments.run_name or os.sep in arguments.run_name:
        raise ScreenError("--run-name must be a filename prefix, not a path")
    if not 1 <= arguments.port <= 65535:
        raise ScreenError("--port must be between 1 and 65535")
    if arguments.startup_timeout <= 0:
        raise ScreenError("--startup-timeout must be positive")
    if not 0 <= arguments.temperature <= 2:
        raise ScreenError("--temperature must be between 0 and 2")
    if arguments.request_extra is not None and not arguments.request_extra.is_file():
        raise ScreenError(f"--request-extra is not a file: {arguments.request_extra}")

    executable = resolve_executable(arguments.llama_server)
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = output_paths(output_dir, arguments.run_name)
    existing = [path for path in paths.values() if path.exists()]
    if existing and not arguments.overwrite:
        raise ScreenError(
            "output already exists; choose another --run-name or pass --overwrite: "
            + ", ".join(str(path) for path in existing)
        )

    server = server_command(
        executable,
        model_path,
        arguments.model_name,
        arguments.port,
        arguments.server_arg,
    )
    provenance: dict[str, Any] = {
        "status": "starting",
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": {"platform": platform.platform(), "python": sys.version},
        "llama_server": {
            "executable": str(executable),
            "version": command_version(executable),
            "command": server,
        },
        "model": {
            "name": arguments.model_name,
            "path": str(model_path),
            "size_bytes": model_path.stat().st_size,
            "sha256": sha256_file(model_path),
            "quantization": arguments.quantization,
        },
        "settings": {
            "prompt": prompt_provenance(arguments.prompt_variant),
            "temperature": arguments.temperature,
            "seed": 23,
            "output_token_cap": "input-derived 16-96",
            "request_extra": (
                None
                if arguments.request_extra is None
                else {
                    "path": str(arguments.request_extra.resolve()),
                    "sha256": sha256_file(arguments.request_extra),
                }
            ),
        },
        "corpora": {
            name: {"path": str(path), "sha256": sha256_file(path)}
            for name, path in CORPORA
        },
        "tools": {
            "runner": {"path": str(RUNNER), "sha256": sha256_file(RUNNER)},
            "scorer": {"path": str(SCORER), "sha256": sha256_file(SCORER)},
        },
        "outputs": {name: str(path) for name, path in paths.items()},
    }
    write_json(paths["provenance"], provenance)

    process: subprocess.Popen[Any] | None = None
    try:
        with paths["server_log"].open("w", encoding="utf-8") as server_log:
            process = subprocess.Popen(
                server,
                stdout=server_log,
                stderr=subprocess.STDOUT,
                text=True,
            )
            wait_for_server(arguments.port, process, arguments.startup_timeout)
            provenance["status"] = "running"
            write_json(paths["provenance"], provenance)

            for corpus_name, corpus in CORPORA:
                result = paths[f"result_{corpus_name}"]
                run_command = runner_command(
                    model_name=arguments.model_name,
                    quantization=arguments.quantization,
                    port=arguments.port,
                    corpus=corpus,
                    output=result,
                    prompt_variant=arguments.prompt_variant,
                    temperature=arguments.temperature,
                    request_extra=arguments.request_extra,
                )
                if arguments.overwrite:
                    run_command.append("--overwrite")
                provenance.setdefault("commands", {})[f"run_{corpus_name}"] = run_command
                write_json(paths["provenance"], provenance)
                run_checked(run_command)

                score_command = scorer_command(corpus, result)
                provenance["commands"][f"score_{corpus_name}"] = score_command
                write_json(paths["provenance"], provenance)
                with paths[f"score_{corpus_name}"].open("w", encoding="utf-8") as score:
                    run_checked(score_command, stdout=score)

        provenance["status"] = "complete"
        provenance["completed_at_utc"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        )
        write_json(paths["provenance"], provenance)
        print(f"Screen complete. Provenance: {paths['provenance']}")
        return 0
    except BaseException as exc:
        provenance["status"] = "failed"
        provenance["error"] = str(exc)
        write_json(paths["provenance"], provenance)
        raise
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        return run(arguments)
    except ScreenError as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
