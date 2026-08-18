#!/usr/bin/env python3
"""Run token-budgeted batched Sotto LFM inference on non-blind publisher dev cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence


SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))
sys.path.insert(0, str(SCRIPT_ROOT.parent))

from cleanup_guardrails import fallback_reason as cleanup_fallback_reason  # noqa: E402
from infer_sotto_lfm import (  # noqa: E402
    PROMPT_TEMPLATE,
    parse_publisher_output,
    publisher_output_cap,
    read_jsonl,
    reject_blind_input,
    sha256_file,
)


def batches(
    rows: Sequence[dict[str, Any]], max_batch_size: int, max_batch_tokens: int,
) -> Iterator[list[dict[str, Any]]]:
    current: list[dict[str, Any]] = []
    longest = 0
    cap: int | None = None
    for row in rows:
        length = len(row["input_ids"])
        row_cap = row["output_cap"]
        candidate_longest = max(longest, length)
        if current and (
            row_cap != cap
            or len(current) >= max_batch_size
            or candidate_longest * (len(current) + 1) > max_batch_tokens
        ):
            yield current
            current, longest, cap = [], 0, None
            candidate_longest = length
        current.append(row)
        longest = candidate_longest
        cap = row_cap
    if current:
        yield current


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--tokenizer-dir", required=True, type=Path)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--model-revision", required=True)
    parser.add_argument("--expected-weight-sha256")
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-batch-size", type=int, default=64)
    parser.add_argument("--max-batch-tokens", type=int, default=32768)
    parser.add_argument(
        "--publisher-schema", action="store_true",
        help="accept source_id in place of diagnostic categories and preservation anchors",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.max_batch_size <= 0 or args.max_batch_tokens <= 0:
        raise RuntimeError("batch controls must be positive")
    model_dir, tokenizer_dir = args.model_dir.resolve(), args.tokenizer_dir.resolve()
    cases_path, output_path = args.cases.resolve(), args.output.resolve()
    provenance_path = output_path.with_suffix(output_path.suffix + ".provenance.json")
    if output_path.exists() or provenance_path.exists():
        raise RuntimeError("refusing to overwrite output or provenance")
    weights = model_dir / "model.safetensors"
    if not weights.is_file() or not (tokenizer_dir / "tokenizer.json").is_file():
        raise RuntimeError("model weights or tokenizer are missing")
    weight_hash = sha256_file(weights)
    if args.expected_weight_sha256 and weight_hash != args.expected_weight_sha256:
        raise RuntimeError("model.safetensors does not match the expected SHA-256")

    rows = read_jsonl(cases_path)
    reject_blind_input(cases_path, rows)
    for index, row in enumerate(rows, 1):
        required = ("id", "raw", "expected")
        if any(field not in row for field in required):
            raise RuntimeError(f"{cases_path}:{index}: missing id/raw/expected")
        if args.publisher_schema:
            if not isinstance(row.get("source_id"), str) or not row["source_id"]:
                raise RuntimeError(f"{cases_path}:{index}: publisher row is missing source_id")
            row["categories"] = [f"publisher_validation:{row['source_id']}"]
            row["must_preserve"] = []
            row["must_remove"] = []
        elif any(field not in row for field in ("categories", "must_preserve")):
            raise RuntimeError(f"{cases_path}:{index}: missing diagnostic metadata")

    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("Sotto evaluation requires CUDA with bfloat16 support")
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        model_dir, dtype=torch.bfloat16, device_map={"": 0}, local_files_only=True,
    )
    model.eval()

    encoded_rows: list[dict[str, Any]] = []
    for row in rows:
        prompt = PROMPT_TEMPLATE.format(raw=row["raw"])
        encoded_rows.append({
            "row": row,
            "input_ids": tokenizer(prompt, add_special_tokens=True)["input_ids"],
            "output_cap": publisher_output_cap(row["raw"]),
        })
    planned_batches = list(batches(encoded_rows, args.max_batch_size, args.max_batch_tokens))
    provenance = {
        "schema_version": "sotto-lfm-batched-inference-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_id": args.model_id,
        "model_revision": args.model_revision,
        "model_weight_sha256": weight_hash,
        "model_config_sha256": sha256_file(model_dir / "config.json"),
        "tokenizer_dir": str(tokenizer_dir),
        "tokenizer_sha256": sha256_file(tokenizer_dir / "tokenizer.json"),
        "runner_sha256": sha256_file(Path(__file__).resolve()),
        "cases_path": str(cases_path),
        "cases_sha256": sha256_file(cases_path),
        "case_count": len(rows),
        "prompt_template": PROMPT_TEMPLATE,
        "decoding": {"do_sample": False, "repetition_penalty": 1.05},
        "batching": {
            "max_batch_size": args.max_batch_size,
            "max_padded_prompt_tokens": args.max_batch_tokens,
            "planned_batches": len(planned_batches),
            "padding_side": "left",
            "same_output_cap_per_batch": True,
        },
        "publisher_schema": args.publisher_schema,
        "runtime": {
            "python": sys.version, "torch": torch.__version__,
            "transformers": transformers.__version__, "device": torch.cuda.get_device_name(0),
        },
        "raw_model_output_is_selected_for_scoring": True,
        "blind_input_allowed": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )

    with output_path.open("x", encoding="utf-8", newline="\n") as handle:
        completed = 0
        for batch_number, batch in enumerate(planned_batches, 1):
            width = max(len(item["input_ids"]) for item in batch)
            padded_ids, masks = [], []
            for item in batch:
                padding = width - len(item["input_ids"])
                padded_ids.append([tokenizer.pad_token_id] * padding + item["input_ids"])
                masks.append([0] * padding + [1] * len(item["input_ids"]))
            inputs = {
                "input_ids": torch.tensor(padded_ids, dtype=torch.long, device="cuda:0"),
                "attention_mask": torch.tensor(masks, dtype=torch.long, device="cuda:0"),
            }
            cap = batch[0]["output_cap"]
            torch.cuda.synchronize()
            started = time.perf_counter_ns()
            with torch.inference_mode():
                generated = model.generate(
                    **inputs, max_new_tokens=cap, do_sample=False, repetition_penalty=1.05,
                    use_cache=True, pad_token_id=tokenizer.pad_token_id,
                    eos_token_id=tokenizer.eos_token_id,
                )
            torch.cuda.synchronize()
            total_ms = (time.perf_counter_ns() - started) / 1_000_000
            for item, generated_ids in zip(batch, generated, strict=True):
                output_ids = generated_ids[width:].tolist()
                eos_seen = tokenizer.eos_token_id in output_ids
                if eos_seen:
                    output_ids = output_ids[: output_ids.index(tokenizer.eos_token_id) + 1]
                generated_text = tokenizer.decode(output_ids, skip_special_tokens=True)
                model_text = parse_publisher_output(generated_text)
                row = item["row"]
                cap_hit = not eos_seen and len(output_ids) >= cap
                fallback_reason = cleanup_fallback_reason(row["raw"], model_text, cap_hit)
                record = {
                    "case_id": row["id"], "model_name": args.model_id,
                    "model_revision": args.model_revision, "quantization": "bf16",
                    "prompt_variant": "sotto_native_v1", "temperature": 0.0,
                    "raw": row["raw"], "expected": row["expected"],
                    "categories": row["categories"], "must_preserve": row["must_preserve"],
                    "must_remove": row.get("must_remove", []),
                    "generated_text": generated_text, "model_text": model_text,
                    "selected_text": model_text, "exact_match": model_text == row["expected"].strip(),
                    "used_fallback": False, "fallback_reason": None,
                    "guardrail_would_fallback": fallback_reason is not None,
                    "guardrail_fallback_reason": fallback_reason,
                    "guardrail_selected_text": row["raw"] if fallback_reason else model_text,
                    "timings": {
                        "ttft_ms": None, "total_ms": total_ms,
                        "tokens_per_second": None, "attempt_count": 1,
                        "shared_batch_size": len(batch),
                    },
                    "prompt_tokens": len(item["input_ids"]),
                    "completion_tokens": len(output_ids), "max_output_tokens": cap,
                    "hit_output_token_limit": cap_hit,
                    "finish_reason": "length" if cap_hit else "stop",
                }
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                completed += 1
            handle.flush()
            print(
                f"[batch {batch_number}/{len(planned_batches)} cases {completed}/{len(rows)}]",
                file=sys.stderr, flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
