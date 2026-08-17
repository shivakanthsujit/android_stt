#!/usr/bin/env python3
"""Train one exploratory direct-source cleanup LoRA without weakening pilot Gate A."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

from cleanup_data_common import nfc  # noqa: E402
from train_cleanup_adapter import (  # noqa: E402
    JsonlMetricsCallback,
    Telemetry,
    committed_file_sha256,
    encode_record,
    git_report,
    sha256_file,
)


def iter_parquet(path: Path, raw_field: str, expected_field: str) -> Iterator[tuple[str, dict[str, Any]]]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise RuntimeError("direct-source Parquet loading requires the locked training environment") from exc
    file = parquet.ParquetFile(path)
    required = {raw_field, expected_field}
    missing = sorted(required - set(file.schema_arrow.names))
    if missing:
        raise RuntimeError(f"{path}: missing required columns: {', '.join(missing)}")
    ordinal = 0
    for batch in file.iter_batches(batch_size=2048, columns=[raw_field, expected_field]):
        for value in batch.to_pylist():
            ordinal += 1
            if not isinstance(value, dict):
                raise RuntimeError(f"{path}: row {ordinal} is not an object")
            yield str(ordinal), value


def iter_json(path: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        for key, row in value.items():
            if not isinstance(row, dict):
                raise RuntimeError(f"{path}: value {key!r} is not an object")
            yield str(key), row
        return
    if isinstance(value, list):
        for index, row in enumerate(value, 1):
            if not isinstance(row, dict):
                raise RuntimeError(f"{path}: row {index} is not an object")
            yield str(index), row
        return
    raise RuntimeError(f"{path}: expected a JSON object or array")


def source_rows(path: Path, raw_field: str, expected_field: str) -> Iterator[tuple[str, dict[str, Any]]]:
    if path.suffix.casefold() == ".parquet":
        yield from iter_parquet(path, raw_field, expected_field)
    elif path.suffix.casefold() == ".json":
        yield from iter_json(path)
    else:
        raise RuntimeError(f"unsupported direct-source file: {path}")


def manifest_files(manifest: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    files: dict[tuple[str, str], dict[str, Any]] = {}
    for source in manifest.get("sources", []):
        for item in source.get("files", []):
            files[(source["id"], item["path"])] = item
    return files


def verify_source_identity(
    manifest: dict[str, Any], source_config: dict[str, Any], source_config_path: Path,
) -> None:
    if manifest.get("manifest_version") != "cleanup-source-manifest-v1":
        raise RuntimeError("unexpected source manifest version")
    if manifest.get("config_sha256") != sha256_file(source_config_path):
        raise RuntimeError("source manifest is not bound to the current source configuration")
    configured = {source["id"]: source for source in source_config["sources"]}
    recorded = {source["id"]: source for source in manifest.get("sources", [])}
    if set(recorded) != set(configured):
        raise RuntimeError("source manifest IDs differ from the pinned source configuration")
    for source_id, rule in configured.items():
        item = recorded[source_id]
        for field in ("url", "revision", "license"):
            if item.get(field) != rule.get(field):
                raise RuntimeError(f"source identity mismatch for {source_id}: {field}")


def verified_file(
    source_root: Path, source_id: str, relative: str, indexed: dict[tuple[str, str], dict[str, Any]],
) -> Path:
    item = indexed.get((source_id, relative))
    if item is None:
        raise RuntimeError(f"source manifest does not contain {source_id}:{relative}")
    path = source_root / source_id / relative
    if not path.is_file():
        raise RuntimeError(f"missing pinned source file: {source_id}:{relative}")
    if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
        raise RuntimeError(f"pinned source file failed byte/hash verification: {source_id}:{relative}")
    return path


def frozen_surfaces(paths: Iterable[Path]) -> set[str]:
    surfaces: set[str] = set()
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise RuntimeError(f"{path}:{line_number}: expected an object")
                for field in ("raw", "expected"):
                    text = value.get(field)
                    if isinstance(text, str) and text.strip():
                        surfaces.add(nfc(text).strip().casefold())
    return surfaces


def load_source_split(
    source_root: Path,
    spec: dict[str, Any],
    split: str,
    indexed: dict[tuple[str, str], dict[str, Any]],
    forbidden: set[str],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    file_key = "train_files" if split == "train" else "validation_files"
    raw_field, expected_field = spec["raw_field"], spec["expected_field"]
    rows: list[dict[str, str]] = []
    publisher_records = 0
    invalid_records = 0
    overlaps = 0
    for relative in spec[file_key]:
        path = verified_file(source_root, spec["source_id"], relative, indexed)
        for locator, value in source_rows(path, raw_field, expected_field):
            publisher_records += 1
            raw, expected = value.get(raw_field), value.get(expected_field)
            if not isinstance(raw, str) or not raw.strip() or not isinstance(expected, str) or not expected.strip():
                invalid_records += 1
                continue
            raw, expected = nfc(raw), nfc(expected)
            if raw.strip().casefold() in forbidden or expected.strip().casefold() in forbidden:
                overlaps += 1
                continue
            rows.append({
                "id": f"direct-{spec['source_id']}-{split}-{publisher_records}",
                "raw": raw,
                "expected": expected,
            })
    publisher_key = "publisher_train_records" if split == "train" else "publisher_validation_records"
    usable_key = "train_records" if split == "train" else "validation_records"
    declared_invalid = spec.get("declared_invalid_train_records", 0) if split == "train" else 0
    if publisher_records != spec[publisher_key]:
        raise RuntimeError(
            f"{spec['source_id']} {split}: publisher row count {publisher_records} != {spec[publisher_key]}"
        )
    if invalid_records != declared_invalid:
        raise RuntimeError(
            f"{spec['source_id']} {split}: invalid row count {invalid_records} != declared {declared_invalid}"
        )
    if overlaps:
        raise RuntimeError(f"{spec['source_id']} {split}: {overlaps} rows overlap frozen evaluation text")
    if len(rows) != spec[usable_key]:
        raise RuntimeError(f"{spec['source_id']} {split}: usable row count {len(rows)} != {spec[usable_key]}")
    return rows, {
        "source_id": spec["source_id"],
        "split": split,
        "publisher_records": publisher_records,
        "usable_records": len(rows),
        "declared_invalid_records": invalid_records,
        "frozen_overlap_records": overlaps,
        "files": list(spec[file_key]),
    }


def load_experiment(
    experiment: dict[str, Any], source_root: Path, manifest: dict[str, Any], forbidden: set[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, Any]]]:
    indexed = manifest_files(manifest)
    train_rows: list[dict[str, str]] = []
    validation_rows: list[dict[str, str]] = []
    report: list[dict[str, Any]] = []
    for spec in experiment["sources"]:
        train, train_report = load_source_split(source_root, spec, "train", indexed, forbidden)
        validation, validation_report = load_source_split(source_root, spec, "validation", indexed, forbidden)
        train_rows.extend(train)
        validation_rows.extend(validation)
        report.extend((train_report, validation_report))
    if len(train_rows) != experiment["train_records"]:
        raise RuntimeError("experiment train count differs from its fixed configuration")
    if len(validation_rows) != experiment["validation_records"]:
        raise RuntimeError("experiment validation count differs from its fixed configuration")
    return train_rows, validation_rows, report


def audit_and_encode(
    tokenizer: Any,
    instruction: str,
    rows: Sequence[dict[str, str]],
    max_tokens: int,
    template_kwargs: dict[str, Any],
) -> tuple[list[dict[str, list[int]]], dict[str, Any]]:
    encoded: list[dict[str, list[int]]] = []
    maximum = 0
    histogram: Counter[str] = Counter()
    for row in rows:
        item = encode_record(tokenizer, instruction, row, max_tokens, template_kwargs)
        length = len(item["input_ids"])
        maximum = max(maximum, length)
        bucket = "<=128" if length <= 128 else "129-256" if length <= 256 else "257-512" if length <= 512 else "513-1024"
        histogram[bucket] += 1
        encoded.append(item)
    return encoded, {
        "records": len(rows),
        "maximum_formatted_tokens": maximum,
        "length_histogram": dict(sorted(histogram.items())),
        "over_limit_records": 0,
        "silent_truncation": False,
    }


def longest_encoded(rows: Sequence[dict[str, list[int]]], limit: int = 32) -> list[dict[str, list[int]]]:
    """Select the longest encoded rows deterministically, preserving source order for ties."""

    if limit <= 0:
        raise RuntimeError("longest-row selection limit must be positive")
    return sorted(rows, key=lambda row: len(row["input_ids"]), reverse=True)[:limit]


def encoded_audit(rows: Sequence[dict[str, list[int]]]) -> dict[str, Any]:
    maximum = max((len(row["input_ids"]) for row in rows), default=0)
    histogram: Counter[str] = Counter()
    for row in rows:
        length = len(row["input_ids"])
        bucket = "<=128" if length <= 128 else "129-256" if length <= 256 else "257-512" if length <= 512 else "513-1024" if length <= 1024 else "1025-2112"
        histogram[bucket] += 1
    return {
        "records": len(rows),
        "maximum_formatted_tokens": maximum,
        "length_histogram": dict(sorted(histogram.items())),
        "over_limit_records": 0,
        "silent_truncation": False,
    }


def resolved_config(
    config: dict[str, Any], experiment_key: str, source_manifest_path: Path, config_path: Path,
    source_root: Path, run_purpose: str,
) -> dict[str, Any]:
    experiment = config["experiments"][experiment_key]
    common = config["common"]
    if common["train_batch_size"] * common["gradient_accumulation_steps"] != common["effective_batch_size"]:
        raise RuntimeError("effective batch size does not match microbatch × accumulation")
    derived_steps = math.ceil(math.ceil(experiment["train_records"] / common["train_batch_size"]) / common["gradient_accumulation_steps"])
    if derived_steps != experiment["expected_optimizer_steps"]:
        raise RuntimeError("configured optimizer-step count differs from the fixed recipe")
    smoke = run_purpose in {"smoke", "longest_smoke"}
    return {
        "config_version": config["config_version"],
        "experiment_key": experiment_key,
        "instruction_path": config["instruction_path"],
        "source_config_path": config["source_config_path"],
        "frozen_evaluation_paths": config["frozen_evaluation_paths"],
        "dataset": config["dataset"],
        "common": common,
        "model_key": config["model"]["model_key"],
        "model": config["model"],
        "experiment": experiment,
        "run_controls": {
            "purpose": run_purpose,
            "selection": "longest_formatted" if run_purpose == "longest_smoke" else "publisher_prefix" if smoke else "all",
            "train_record_limit": 32 if smoke else None,
            "validation_record_limit": 32 if smoke else None,
            "max_steps": 2 if smoke else -1,
        },
        "artifact_inputs": {
            "source_root": str(source_root.resolve()),
            "source_manifest": str(source_manifest_path.resolve()),
        },
        "input_hashes": {
            "source_manifest_sha256": sha256_file(source_manifest_path),
            "instruction_sha256": sha256_file(REPO_ROOT / config["instruction_path"]),
            "source_config_sha256": sha256_file(REPO_ROOT / config["source_config_path"]),
            "training_config_sha256": sha256_file(config_path),
            "frozen_evaluation_sha256": {
                path: sha256_file(REPO_ROOT / path) for path in config["frozen_evaluation_paths"]
            },
        },
    }


def verify_tracked_repository_and_inputs(repository: dict[str, Any], paths: Iterable[Path]) -> None:
    """Permit recorded untracked scratch files, but require tracked bytes to match HEAD."""

    tracked = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=no"],
        cwd=REPO_ROOT, text=True, capture_output=True, check=True,
    ).stdout.splitlines()
    if tracked:
        raise RuntimeError(f"training requires all tracked files to match HEAD: {tracked}")
    for path in paths:
        if committed_file_sha256(path) != sha256_file(path):
            raise RuntimeError(f"working bytes differ from HEAD for required input: {path}")
    repository["tracked_files_match_head"] = True
    repository["untracked_files_are_not_training_inputs"] = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", choices=("sotto", "disfl_qa", "nyra", "combined"), required=True)
    parser.add_argument("--run-purpose", choices=("smoke", "longest_smoke", "full"), required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("/data/rise/android_stt/raw/sources-v1"))
    parser.add_argument("--source-manifest", type=Path, default=Path("/data/rise/android_stt/manifests/source-manifest-v1.json"))
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "training/config/direct-source-training-v1.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    repository = git_report()
    source_config_path = REPO_ROOT / config["source_config_path"]
    verify_tracked_repository_and_inputs(
        repository, (args.config, source_config_path, REPO_ROOT / config["instruction_path"])
    )
    resolved = resolved_config(
        config, args.experiment, args.source_manifest, args.config, args.source_root, args.run_purpose
    )
    source_manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    source_config = json.loads(source_config_path.read_text(encoding="utf-8"))
    verify_source_identity(source_manifest, source_config, source_config_path)
    forbidden = frozen_surfaces(REPO_ROOT / path for path in config["frozen_evaluation_paths"])
    train_rows, validation_rows, source_report = load_experiment(
        resolved["experiment"], args.source_root, source_manifest, forbidden
    )
    if args.run_purpose == "smoke":
        train_rows = train_rows[:32]
        validation_rows = validation_rows[:32]
    if args.run_dir.exists():
        unexpected = [path.name for path in args.run_dir.iterdir() if path.name != "console.log"]
        if unexpected:
            raise RuntimeError(f"new run directory contains unexpected files: {sorted(unexpected)}")
    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "resolved-config.json").write_text(
        json.dumps(resolved, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.run_dir / "repository.json").write_text(
        json.dumps(repository, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (args.run_dir / "source-audit.json").write_text(
        json.dumps({
            "audit_version": "cleanup-direct-source-audit-v1",
            "contains_example_text": False,
            "frozen_surfaces_loaded_for_overlap_check_only": len(forbidden),
            "sources": source_report,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.run_dir / "status.json").write_text(json.dumps({
        "status": "running", "started_at": datetime.now(timezone.utc).isoformat()
    }, indent=2) + "\n", encoding="utf-8")

    telemetry = Telemetry(args.run_dir)
    telemetry.start()
    try:
        import torch
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainerCallback, TrainingArguments

        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise RuntimeError("training requires CUDA with bfloat16 support")
        common, model_config = resolved["common"], resolved["model"]
        torch.manual_seed(common["seed"])
        torch.cuda.manual_seed_all(common["seed"])
        tokenizer = AutoTokenizer.from_pretrained(
            model_config["model_id"], revision=model_config["revision"],
            trust_remote_code=common["trust_remote_code"],
        )
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
        instruction = (REPO_ROOT / resolved["instruction_path"]).read_text(encoding="utf-8").strip()
        max_tokens = resolved["dataset"]["max_sequence_tokens"]
        encoded_train, train_audit = audit_and_encode(
            tokenizer, instruction, train_rows, max_tokens, model_config["chat_template_kwargs"]
        )
        encoded_validation, validation_audit = audit_and_encode(
            tokenizer, instruction, validation_rows, max_tokens, model_config["chat_template_kwargs"]
        )
        full_corpus_audit = None
        if args.run_purpose == "longest_smoke":
            full_corpus_audit = {"train": train_audit, "validation": validation_audit}
            encoded_train = longest_encoded(encoded_train)
            encoded_validation = longest_encoded(encoded_validation)
            train_audit = encoded_audit(encoded_train)
            validation_audit = encoded_audit(encoded_validation)
        (args.run_dir / "tokenization-audit.json").write_text(
            json.dumps({
                "selection": resolved["run_controls"]["selection"],
                "train": train_audit,
                "validation": validation_audit,
                "full_corpus": full_corpus_audit,
            }, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_config["model_id"], revision=model_config["revision"], torch_dtype=torch.bfloat16,
            trust_remote_code=common["trust_remote_code"], attn_implementation=common["attention_implementation"],
        )
        model.config.use_cache = False
        lora = LoraConfig(
            r=common["lora_rank"], lora_alpha=common["lora_alpha"],
            lora_dropout=common["lora_dropout"], bias=common["lora_bias"], task_type="CAUSAL_LM",
            target_modules=model_config["lora_target_modules"],
            exclude_modules=model_config["lora_exclude_modules"],
        )
        model = get_peft_model(model, lora)
        trainable, total = model.get_nb_trainable_parameters()
        (args.run_dir / "model-parameters.json").write_text(
            json.dumps({"trainable": trainable, "total": total}, indent=2) + "\n", encoding="utf-8"
        )

        class Dataset(torch.utils.data.Dataset):
            def __init__(self, rows: Sequence[dict[str, list[int]]]) -> None:
                self.rows = rows
            def __len__(self) -> int:
                return len(self.rows)
            def __getitem__(self, index: int) -> dict[str, list[int]]:
                return self.rows[index]

        class Collator:
            def __call__(self, features: list[dict[str, list[int]]]) -> dict[str, Any]:
                length = max(len(item["input_ids"]) for item in features)
                input_ids, attention_mask, labels = [], [], []
                for item in features:
                    padding = length - len(item["input_ids"])
                    input_ids.append(item["input_ids"] + [tokenizer.pad_token_id] * padding)
                    attention_mask.append(item["attention_mask"] + [0] * padding)
                    labels.append(item["labels"] + [-100] * padding)
                return {
                    "input_ids": torch.tensor(input_ids),
                    "attention_mask": torch.tensor(attention_mask),
                    "labels": torch.tensor(labels),
                }

        class Callback(TrainerCallback):
            def __init__(self, delegate: JsonlMetricsCallback) -> None:
                self.delegate = delegate
            def on_log(self, trainer_args: Any, state: Any, control: Any, logs: dict[str, Any] | None = None, **kwargs: Any) -> None:
                self.delegate.on_log(trainer_args, state, control, logs, **kwargs)

        experiment = resolved["experiment"]
        smoke = args.run_purpose in {"smoke", "longest_smoke"}
        training_args = TrainingArguments(
            output_dir=str(args.run_dir),
            num_train_epochs=common["epochs"], max_steps=2 if smoke else -1,
            per_device_train_batch_size=common["train_batch_size"],
            per_device_eval_batch_size=common["eval_batch_size"],
            gradient_accumulation_steps=common["gradient_accumulation_steps"],
            learning_rate=common["learning_rate"], weight_decay=common["weight_decay"],
            warmup_ratio=common["warmup_ratio"], lr_scheduler_type=common["lr_scheduler_type"],
            optim=common["optimizer"], max_grad_norm=common["max_grad_norm"],
            logging_strategy="steps", logging_steps=1 if smoke else common["logging_steps"],
            eval_strategy="no" if smoke else "steps", eval_steps=None if smoke else experiment["eval_steps"],
            save_strategy="steps", save_steps=2 if smoke else experiment["save_steps"],
            save_total_limit=common["save_total_limit"], bf16=common["bf16"], tf32=common["tf32"],
            gradient_checkpointing=common["gradient_checkpointing"], seed=common["seed"],
            data_seed=common["data_seed"], report_to=[], remove_unused_columns=False,
        )
        trainer = Trainer(
            model=model, args=training_args, train_dataset=Dataset(encoded_train),
            eval_dataset=Dataset(encoded_validation), data_collator=Collator(),
            callbacks=[Callback(JsonlMetricsCallback(args.run_dir / "metrics.jsonl"))],
        )
        result = trainer.train()
        expected_steps = 2 if smoke else experiment["expected_optimizer_steps"]
        if trainer.state.global_step != expected_steps:
            raise RuntimeError(f"completed at step {trainer.state.global_step}, expected {expected_steps}")
        trainer.save_model(str(args.run_dir / "final-adapter"))
        trainer.save_state()
        (args.run_dir / "status.json").write_text(json.dumps({
            "status": "complete", "finished_at": datetime.now(timezone.utc).isoformat(),
            "global_step": trainer.state.global_step, "train_metrics": result.metrics,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0
    except BaseException as exc:
        (args.run_dir / "status.json").write_text(json.dumps({
            "status": "failed", "finished_at": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__, "error": str(exc),
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        traceback.print_exc()
        return 1
    finally:
        telemetry.stop()


if __name__ == "__main__":
    raise SystemExit(main())
