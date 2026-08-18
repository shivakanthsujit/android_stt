#!/usr/bin/env python3
"""Evaluate a hash-pinned public or locally fine-tuned Sotto LFM checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from cleanup_guardrails import fallback_reason as cleanup_fallback_reason  # noqa: E402


MODEL_ID = "juanquivilla/sotto-cleanup-lfm25-350m"
MODEL_REVISION = "6df6f019170b8b55333c047b901886a51750a965"
MODEL_WEIGHT_SHA256 = "6e96eeffdcdd60f881e13eb2019b339b39d1a74951446f062e7e641a82f6422e"
PROMPT_TEMPLATE = "### Input:\n{raw}\n\n### Output:\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise RuntimeError(f"{path}:{line_number}: expected a JSON object")
            rows.append(row)
    return rows


def reject_blind_input(path: Path, rows: list[dict[str, Any]]) -> None:
    if "blind" in str(path).casefold():
        raise RuntimeError("this authoring-side runner refuses blind evaluation inputs")
    if any(str(row.get("split", "")).casefold().startswith("blind") for row in rows):
        raise RuntimeError("this authoring-side runner refuses records marked as blind")


def publisher_output_cap(raw: str) -> int:
    return max(900, math.ceil(len(raw.split()) * 1.5))


def parse_publisher_output(generated_text: str) -> str:
    return generated_text.split("###", 1)[0].strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument(
        "--tokenizer-dir", type=Path,
        help="optional tokenizer directory for Trainer epoch checkpoints that contain only model state",
    )
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--model-revision", default=MODEL_REVISION)
    parser.add_argument(
        "--expected-model-sha256", "--expected-weight-sha256",
        dest="expected_model_sha256",
        help="optional expected local model.safetensors hash; the public default remains pinned",
    )
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--input-field", choices=("raw", "spoken"), default="raw")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model_dir = args.model_dir.resolve()
    tokenizer_dir = (args.tokenizer_dir or args.model_dir).resolve()
    cases_path = args.cases.resolve()
    output_path = args.output.resolve()
    provenance_path = output_path.with_suffix(output_path.suffix + ".provenance.json")
    if output_path.exists() or provenance_path.exists():
        raise RuntimeError("refusing to overwrite output or provenance")
    if not model_dir.is_dir():
        raise RuntimeError(f"model directory does not exist: {model_dir}")
    if not tokenizer_dir.is_dir():
        raise RuntimeError(f"tokenizer directory does not exist: {tokenizer_dir}")
    if not args.model_id.strip() or not args.model_revision.strip():
        raise RuntimeError("--model-id and --model-revision must be non-empty")
    weights = model_dir / "model.safetensors"
    if not weights.is_file():
        raise RuntimeError("model.safetensors is missing")
    actual_weight_sha256 = sha256_file(weights)
    expected_weight_sha256 = args.expected_model_sha256
    if (
        expected_weight_sha256 is None
        and args.model_id == MODEL_ID and args.model_revision == MODEL_REVISION
    ):
        expected_weight_sha256 = MODEL_WEIGHT_SHA256
    if expected_weight_sha256 is None:
        raise RuntimeError("a non-public checkpoint requires --expected-model-sha256")
    if len(expected_weight_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in expected_weight_sha256
    ):
        raise RuntimeError("--expected-model-sha256 must be 64 lowercase hexadecimal characters")
    if expected_weight_sha256 is not None and actual_weight_sha256 != expected_weight_sha256:
        raise RuntimeError("model.safetensors does not match the expected SHA-256")

    rows = read_jsonl(cases_path)
    reject_blind_input(cases_path, rows)
    if args.limit is not None:
        if args.limit <= 0:
            raise RuntimeError("--limit must be positive")
        rows = rows[: args.limit]
    for index, row in enumerate(rows, 1):
        for field in ("id", args.input_field, "expected", "categories", "must_preserve"):
            if field not in row:
                raise RuntimeError(f"{cases_path}:{index}: missing {field}")

    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("Sotto evaluation requires CUDA with bfloat16 support")
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        model_dir,
        dtype=torch.bfloat16,
        device_map={"": 0},
        local_files_only=True,
    )
    model.eval()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    provenance = {
        "schema_version": "sotto-lfm-inference-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_id": args.model_id,
        "model_revision": args.model_revision,
        "model_weight_sha256": actual_weight_sha256,
        "expected_model_weight_sha256": expected_weight_sha256,
        "model_config_sha256": sha256_file(model_dir / "config.json"),
        "tokenizer_dir": str(tokenizer_dir),
        "tokenizer_sha256": sha256_file(tokenizer_dir / "tokenizer.json"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "cases_path": str(cases_path),
        "cases_sha256": sha256_file(cases_path),
        "case_count": len(rows),
        "input_field": args.input_field,
        "prompt_template": PROMPT_TEMPLATE,
        "decoding": {
            "do_sample": False,
            "repetition_penalty": 1.05,
            "max_new_tokens": "max(900, ceil(1.5 * input word count))",
            "publisher_delimiter_parser": "text before first ###, then strip",
        },
        "runtime": {
            "python": sys.version,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "device": torch.cuda.get_device_name(0),
        },
        "raw_model_output_is_selected_for_scoring": True,
        "blind_input_allowed": False,
    }
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    with output_path.open("x", encoding="utf-8", newline="\n") as handle:
        for ordinal, row in enumerate(rows, 1):
            raw = row[args.input_field]
            prompt = PROMPT_TEMPLATE.format(raw=raw)
            encoded = tokenizer(prompt, return_tensors="pt")
            inputs = {key: value.to("cuda:0") for key, value in encoded.items()}
            cap = publisher_output_cap(raw)
            streamer = TextIteratorStreamer(
                tokenizer,
                skip_prompt=True,
                skip_special_tokens=True,
                timeout=180.0,
            )
            generated: dict[str, Any] = {}

            def generate() -> None:
                try:
                    with torch.inference_mode():
                        generated["ids"] = model.generate(
                            **inputs,
                            max_new_tokens=cap,
                            do_sample=False,
                            repetition_penalty=1.05,
                            use_cache=True,
                            pad_token_id=tokenizer.pad_token_id,
                            eos_token_id=tokenizer.eos_token_id,
                            streamer=streamer,
                        )
                except BaseException as exc:
                    generated["error"] = exc
                    streamer.end()

            torch.cuda.synchronize()
            started = time.perf_counter_ns()
            worker = threading.Thread(target=generate, name="sotto-generate")
            worker.start()
            first_text_ns: int | None = None
            for chunk in streamer:
                if chunk and first_text_ns is None:
                    first_text_ns = time.perf_counter_ns()
            worker.join()
            torch.cuda.synchronize()
            finished = time.perf_counter_ns()
            if "error" in generated:
                raise generated["error"]

            prompt_tokens = inputs["input_ids"].shape[1]
            output_ids = generated["ids"][0, prompt_tokens:].tolist()
            generated_text = tokenizer.decode(output_ids, skip_special_tokens=True)
            model_text = parse_publisher_output(generated_text)
            completion_tokens = len(output_ids)
            cap_hit = completion_tokens >= cap
            fallback_reason = cleanup_fallback_reason(raw, model_text, cap_hit)
            total_ms = (finished - started) / 1_000_000
            record = {
                "case_id": row["id"],
                "model_name": args.model_id,
                "model_revision": args.model_revision,
                "quantization": "bf16",
                "prompt_variant": "sotto_native_v1",
                "temperature": 0.0,
                "raw": raw,
                "expected": row["expected"],
                "categories": row["categories"],
                "must_preserve": row["must_preserve"],
                "must_remove": row.get("must_remove", []),
                "generated_text": generated_text,
                "model_text": model_text,
                "selected_text": model_text,
                "exact_match": model_text == row["expected"].strip(),
                "used_fallback": False,
                "fallback_reason": None,
                "guardrail_would_fallback": fallback_reason is not None,
                "guardrail_fallback_reason": fallback_reason,
                "guardrail_selected_text": raw if fallback_reason else model_text,
                "timings": {
                    "ttft_ms": (
                        (first_text_ns - started) / 1_000_000 if first_text_ns else None
                    ),
                    "total_ms": total_ms,
                    "tokens_per_second": (
                        completion_tokens / (total_ms / 1000) if total_ms else None
                    ),
                    "attempt_count": 1,
                },
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "max_output_tokens": cap,
                "hit_output_token_limit": cap_hit,
                "finish_reason": "length" if cap_hit else "stop",
            }
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            print(f"[{ordinal}/{len(rows)}] {row['id']}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
