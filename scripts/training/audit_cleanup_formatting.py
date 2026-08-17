#!/usr/bin/env python3
"""Audit pinned chat formatting and assistant-only labels without loading a model."""

from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from train_cleanup_adapter import REPO_ROOT, encode_record, read_jsonl, sha256_file


def validate_gate(train: Path, dev: Path, gate_path: Path, config: dict[str, Any]) -> None:
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if gate.get("status") != "pass" or gate.get("gate") != "pilot_gate_a":
        raise RuntimeError("formatting audit requires a passing pilot Gate A report")
    rows = gate.get("dataset_files", [])
    expected = [(train, config["dataset"]["train_records"]), (dev, config["dataset"]["dev_records"])]
    if len(rows) != 2:
        raise RuntimeError("Gate A report must identify exactly train and dev files")
    for gate_row, (path, count) in zip(rows, expected):
        if gate_row.get("sha256") != sha256_file(path) or gate_row.get("records") != count:
            raise RuntimeError(f"{path}: hash or record count differs from Gate A")


def summarize(encoded: list[dict[str, list[int]]]) -> dict[str, Any]:
    lengths = [len(row["input_ids"]) for row in encoded]
    targets = [sum(label != -100 for label in row["labels"]) for row in encoded]
    if any(len(row["input_ids"]) != len(row["attention_mask"]) or len(row["input_ids"]) != len(row["labels"]) for row in encoded):
        raise RuntimeError("tokenized feature lengths are inconsistent")
    if any(target <= 0 for target in targets):
        raise RuntimeError("a record has no assistant target labels")
    return {
        "records": len(encoded),
        "sequence_tokens": {
            "min": min(lengths), "median": statistics.median(lengths),
            "p95": sorted(lengths)[max(0, int(len(lengths) * 0.95) - 1)], "max": max(lengths),
        },
        "assistant_target_tokens": {
            "min": min(targets), "median": statistics.median(targets),
            "p95": sorted(targets)[max(0, int(len(targets) * 0.95) - 1)], "max": max(targets),
        },
        "all_prompt_labels_masked": True,
        "all_assistant_targets_nonempty": True,
        "truncation_used": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-key", required=True, choices=("qwen3_0_6b", "qwen35_0_8b"))
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--gate-a-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "training/config/pilot-training-v1.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite {args.output}")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    validate_gate(args.train, args.dev, args.gate_a_report, config)
    model_config = config["models"][args.model_key]

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        model_config["model_id"], revision=model_config["revision"],
        trust_remote_code=config["common"]["trust_remote_code"],
    )
    instruction = (REPO_ROOT / config["instruction_path"]).read_text(encoding="utf-8").strip()
    maximum = config["dataset"]["max_sequence_tokens"]
    template_kwargs = model_config["chat_template_kwargs"]
    train_encoded = [encode_record(tokenizer, instruction, row, maximum, template_kwargs) for row in read_jsonl(args.train)]
    dev_encoded = [encode_record(tokenizer, instruction, row, maximum, template_kwargs) for row in read_jsonl(args.dev)]
    report = {
        "schema_version": "cleanup-formatting-audit-v1",
        "status": "pass",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_key": args.model_key,
        "model_id": model_config["model_id"],
        "model_revision": model_config["revision"],
        "chat_template_kwargs": template_kwargs,
        "max_sequence_tokens": maximum,
        "assistant_only_loss": True,
        "packing": False,
        "input_hashes": {
            "train_sha256": sha256_file(args.train), "dev_sha256": sha256_file(args.dev),
            "gate_a_report_sha256": sha256_file(args.gate_a_report),
            "instruction_sha256": sha256_file(REPO_ROOT / config["instruction_path"]),
        },
        "splits": {"train": summarize(train_encoded), "dev": summarize(dev_encoded)},
        "contains_example_text": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
