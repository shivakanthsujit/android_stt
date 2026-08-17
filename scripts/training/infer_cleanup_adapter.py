#!/usr/bin/env python3
"""Run deterministic raw adapter inference with Android-matched output bounds."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPT_ROOT.parent
sys.path.insert(0, str(SCRIPT_ROOT))

from cleanup_guardrails import fallback_reason as cleanup_fallback_reason  # noqa: E402
from train_cleanup_adapter import apply_template, prompt_messages, read_jsonl, sha256_file  # noqa: E402


def max_output_tokens(raw_text: str) -> int:
    """Match LiquidCleanupEngine's Unicode-code-point bound exactly."""

    return max(16, min(96, (len(raw_text) + 2) // 3 + 8))


def reject_blind_input(path: Path, rows: list[dict[str, Any]]) -> None:
    lowered = str(path).casefold()
    if "blind" in lowered or "blind-v2" in lowered:
        raise RuntimeError("this authoring-side runner refuses blind evaluation inputs")
    if any(str(row.get("split", "")).casefold().startswith("blind") for row in rows):
        raise RuntimeError("this authoring-side runner refuses records marked as blind")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, help="defaults to RUN_DIR/final-adapter")
    parser.add_argument("--limit", type=int, help="explicit smoke/overfit subset size")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite {args.output}")
    provenance_path = args.output.with_suffix(args.output.suffix + ".provenance.json")
    if provenance_path.exists():
        raise RuntimeError(f"refusing to overwrite {provenance_path}")
    resolved_path = args.run_dir / "resolved-config.json"
    status_path = args.run_dir / "status.json"
    if not resolved_path.is_file() or not status_path.is_file():
        raise RuntimeError("run directory is missing resolved config or status")
    resolved = json.loads(resolved_path.read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("status") != "complete":
        raise RuntimeError("inference requires a completed training run")
    adapter = (args.adapter or args.run_dir / "final-adapter").resolve()
    if not adapter.is_dir() or args.run_dir.resolve() not in adapter.parents:
        raise RuntimeError("adapter must exist inside the identified run directory")
    rows = read_jsonl(args.cases)
    reject_blind_input(args.cases, rows)
    if args.limit is not None:
        if args.limit <= 0:
            raise RuntimeError("--limit must be positive")
        rows = rows[:args.limit]
    for index, row in enumerate(rows, 1):
        for field in ("id", "raw", "expected", "categories", "must_preserve"):
            if field not in row:
                raise RuntimeError(f"{args.cases}:{index}: missing {field}")

    import torch
    import transformers
    from peft import PeftModel
    from transformers import AutoTokenizer, TextIteratorStreamer

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("inference requires CUDA with bfloat16 support")
    model_config = resolved["model"]
    tokenizer = AutoTokenizer.from_pretrained(
        model_config["model_id"], revision=model_config["revision"],
        trust_remote_code=resolved["common"]["trust_remote_code"],
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    model_class = getattr(transformers, model_config["model_class"])
    base = model_class.from_pretrained(
        model_config["model_id"], revision=model_config["revision"],
        torch_dtype=torch.bfloat16, device_map={"": 0},
        trust_remote_code=resolved["common"]["trust_remote_code"],
        attn_implementation=resolved["common"]["attention_implementation"],
    )
    model = PeftModel.from_pretrained(base, str(adapter), is_trainable=False)
    model.eval()
    instruction_path = REPO_ROOT / resolved["instruction_path"]
    if sha256_file(instruction_path) != resolved["input_hashes"]["instruction_sha256"]:
        raise RuntimeError("current instruction bytes differ from the completed training run")
    instruction = instruction_path.read_text(encoding="utf-8").strip()
    prompt_variant = instruction_path.stem
    template_kwargs = model_config["chat_template_kwargs"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    provenance = {
        "schema_version": "cleanup-adapter-inference-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(args.run_dir.resolve()),
        "resolved_config_sha256": sha256_file(resolved_path),
        "adapter_config_sha256": sha256_file(adapter / "adapter_config.json"),
        "cases_sha256": sha256_file(args.cases),
        "case_count": len(rows),
        "model_key": resolved["model_key"],
        "model_id": model_config["model_id"],
        "model_revision": model_config["revision"],
        "prompt_variant": prompt_variant,
        "temperature": 0.0,
        "raw_model_output_is_selected_for_scoring": True,
        "blind_input_allowed": False,
    }
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        for ordinal, row in enumerate(rows, 1):
            prompt_ids = apply_template(
                tokenizer, prompt_messages(instruction, row["raw"]),
                add_generation_prompt=True, kwargs=template_kwargs,
            )
            inputs = torch.tensor([prompt_ids], dtype=torch.long, device="cuda:0")
            attention_mask = torch.ones_like(inputs)
            cap = max_output_tokens(row["raw"])
            streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True, timeout=180.0)
            generated: dict[str, Any] = {}

            def generate() -> None:
                try:
                    with torch.inference_mode():
                        generated["ids"] = model.generate(
                            input_ids=inputs, attention_mask=attention_mask,
                            max_new_tokens=cap, do_sample=False, use_cache=True,
                            pad_token_id=tokenizer.pad_token_id,
                            eos_token_id=tokenizer.eos_token_id,
                            streamer=streamer,
                        )
                except BaseException as exc:  # propagated after the worker joins
                    generated["error"] = exc
                    streamer.end()

            torch.cuda.synchronize()
            started = time.perf_counter_ns()
            worker = threading.Thread(target=generate, name="adapter-generate")
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
            output_ids = generated["ids"][0, len(prompt_ids):].tolist()
            model_text = tokenizer.decode(output_ids, skip_special_tokens=True).strip()
            completion_tokens = len(output_ids)
            cap_hit = completion_tokens >= cap
            fallback_reason = cleanup_fallback_reason(row["raw"], model_text, cap_hit)
            total_ms = (finished - started) / 1_000_000
            record = {
                "case_id": row["id"],
                "model_name": model_config["model_id"],
                "model_revision": model_config["revision"],
                "adapter_run": args.run_dir.name,
                "quantization": "bf16-lora",
                "prompt_variant": prompt_variant,
                "temperature": 0.0,
                "raw": row["raw"], "expected": row["expected"],
                "categories": row["categories"], "must_preserve": row["must_preserve"],
                "must_remove": row.get("must_remove", []),
                "model_text": model_text,
                "selected_text": model_text,
                "exact_match": model_text == row["expected"].strip(),
                "used_fallback": False,
                "fallback_reason": None,
                "guardrail_would_fallback": fallback_reason is not None,
                "guardrail_fallback_reason": fallback_reason,
                "guardrail_selected_text": row["raw"] if fallback_reason else model_text,
                "timings": {
                    "ttft_ms": ((first_text_ns - started) / 1_000_000) if first_text_ns else None,
                    "total_ms": total_ms,
                    "tokens_per_second": completion_tokens / (total_ms / 1000) if total_ms else None,
                    "attempt_count": 1,
                },
                "prompt_tokens": len(prompt_ids), "completion_tokens": completion_tokens,
                "max_output_tokens": cap, "hit_output_token_limit": cap_hit,
                "finish_reason": "length" if cap_hit else "stop",
            }
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            print(f"[{ordinal}/{len(rows)}] {row['id']}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
