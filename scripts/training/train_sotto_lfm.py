#!/usr/bin/env python3
"""Audit, pack, and fully fine-tune one pinned Sotto LFM campaign arm."""

from __future__ import annotations

import argparse
import json
import math
import secrets
import subprocess
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

from cleanup_data_common import sha256_file  # noqa: E402
from train_cleanup_adapter import JsonlMetricsCallback, Telemetry, git_report  # noqa: E402


RUN_PURPOSES = ("format_audit", "overfit32", "longest_smoke", "resume_smoke", "full")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RuntimeError(f"{path}:{line_number}: expected an object")
            for field in ("id", "source_id", "source_ref", "raw", "expected"):
                if not isinstance(value.get(field), str):
                    raise RuntimeError(f"{path}:{line_number}: missing string field {field!r}")
            rows.append(value)
    return rows


def verify_mixture(
    mixture_dir: Path, manifest: dict[str, Any], data_config_path: Path,
) -> tuple[Path, Path]:
    if manifest.get("manifest_version") != "sotto-lfm-mixture-manifest-v1":
        raise RuntimeError("unexpected mixture manifest version")
    if manifest.get("contains_example_text") is not False:
        raise RuntimeError("mixture manifest must declare that it contains no example text")
    if manifest.get("config_sha256") != sha256_file(data_config_path):
        raise RuntimeError("mixture is not bound to the current data configuration")
    paths: list[Path] = []
    for split in ("train", "dev"):
        item = manifest["streams"][split]
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"unsafe mixture path for {split}")
        path = mixture_dir / relative
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            raise RuntimeError(f"{split} mixture stream failed hash verification")
        paths.append(path)
    return paths[0], paths[1]


def validate_controls(
    purpose: str, max_steps: int, stop_after_step: int | None, resume_from: Path | None,
) -> int:
    if purpose in {"format_audit", "longest_smoke", "full"}:
        if max_steps != -1 or stop_after_step is not None or resume_from is not None:
            raise RuntimeError(f"{purpose} uses fixed controls")
        return 2 if purpose == "longest_smoke" else -1
    if max_steps <= 0:
        raise RuntimeError(f"{purpose} requires a positive --max-steps")
    if purpose == "overfit32" and (stop_after_step is not None or resume_from is not None):
        raise RuntimeError("overfit32 cannot pause or resume")
    if purpose == "resume_smoke":
        if stop_after_step is not None and not 0 < stop_after_step < max_steps:
            raise RuntimeError("--stop-after-step must be positive and lower than --max-steps")
        if stop_after_step is not None and resume_from is not None:
            raise RuntimeError("resume-smoke phase 1 cannot also resume")
        if stop_after_step is None and resume_from is None:
            raise RuntimeError("resume-smoke requires either --stop-after-step or --resume-from")
    return max_steps


def encode_record(
    tokenizer: Any, prompt_template: str, row: dict[str, Any], max_tokens: int,
) -> dict[str, Any]:
    prompt = prompt_template.format(raw=row["raw"])
    prompt_ids = tokenizer(prompt, add_special_tokens=True, truncation=False)["input_ids"]
    complete_ids = tokenizer(
        prompt + row["expected"], add_special_tokens=True, truncation=False,
    )["input_ids"]
    if complete_ids[:len(prompt_ids)] != prompt_ids:
        raise RuntimeError(f"{row['id']}: target text changed the native prompt token prefix")
    eos = tokenizer.eos_token_id
    if eos is None:
        raise RuntimeError("tokenizer has no EOS token")
    input_ids = complete_ids + [eos]
    if len(input_ids) > max_tokens:
        raise RuntimeError(
            f"{row['id']}: formatted example has {len(input_ids)} tokens, limit is {max_tokens}"
        )
    labels = [-100] * len(prompt_ids) + complete_ids[len(prompt_ids):] + [eos]
    if len(labels) != len(input_ids) or all(label == -100 for label in labels):
        raise RuntimeError(f"{row['id']}: invalid assistant-only loss mask")
    return {
        "id": row["id"], "source_id": row["source_id"],
        "input_ids": input_ids, "labels": labels,
        "prompt_tokens": len(prompt_ids), "target_tokens": len(input_ids) - len(prompt_ids),
    }


def token_audit(rows: Sequence[dict[str, Any]], max_tokens: int) -> dict[str, Any]:
    histogram: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    total_tokens = 0
    target_tokens = 0
    maximum = 0
    for row in rows:
        length = len(row["input_ids"])
        maximum = max(maximum, length)
        total_tokens += length
        target_tokens += row["target_tokens"]
        source_counts[row["source_id"]] += 1
        boundary = next((value for value in (128, 256, 512, 1024, 2048, max_tokens) if length <= value), None)
        histogram[f"<={boundary}" if boundary else f">{max_tokens}"] += 1
    return {
        "records": len(rows), "maximum_formatted_tokens": maximum,
        "total_tokens": total_tokens, "supervised_target_tokens": target_tokens,
        "over_limit_records": 0, "silent_truncation": False,
        "source_counts": dict(sorted(source_counts.items())),
        "length_histogram": dict(sorted(histogram.items())),
    }


def pack_examples(rows: Sequence[dict[str, Any]], max_tokens: int) -> list[dict[str, Any]]:
    """Ordered greedy packing with explicit LFM attention and recurrent-state boundaries."""

    packed: list[dict[str, Any]] = []
    current = {"input_ids": [], "labels": [], "position_ids": [], "seq_idx": [], "example_count": 0}

    def flush() -> None:
        nonlocal current
        if not current["input_ids"]:
            return
        if not (
            len(current["input_ids"]) == len(current["labels"])
            == len(current["position_ids"]) == len(current["seq_idx"])
        ):
            raise RuntimeError("packed tensor lengths diverged")
        packed.append(current)
        current = {"input_ids": [], "labels": [], "position_ids": [], "seq_idx": [], "example_count": 0}

    for row in rows:
        length = len(row["input_ids"])
        if length > max_tokens:
            raise RuntimeError(f"{row['id']}: cannot pack an over-limit example")
        if current["input_ids"] and len(current["input_ids"]) + length > max_tokens:
            flush()
        segment = current["example_count"]
        current["input_ids"].extend(row["input_ids"])
        current["labels"].extend(row["labels"])
        current["position_ids"].extend(range(length))
        current["seq_idx"].extend([segment] * length)
        current["example_count"] += 1
    flush()
    return packed


def packing_audit(packed: Sequence[dict[str, Any]], examples: int, max_tokens: int) -> dict[str, Any]:
    tokens = sum(len(row["input_ids"]) for row in packed)
    capacity = len(packed) * max_tokens
    return {
        "strategy": "ordered-greedy-no-split", "packed_sequences": len(packed),
        "examples": examples, "tokens": tokens,
        "maximum_packed_tokens": max((len(row["input_ids"]) for row in packed), default=0),
        "mean_examples_per_packed_sequence": examples / len(packed) if packed else 0,
        "packing_utilization": tokens / capacity if capacity else 0,
        "position_ids_reset_per_example": True, "seq_idx_passed": True,
        "attention_mask_passed": False,
    }


def verify_model_weights(model_dir: Path, expected_sha256: str | None) -> dict[str, Any]:
    weight = model_dir / "model.safetensors"
    if not weight.is_file():
        raise RuntimeError(f"model is not a single-file safetensors snapshot: {weight}")
    actual = sha256_file(weight)
    if expected_sha256 is None:
        raise RuntimeError("model weight hash has not been pinned in the campaign configuration")
    if actual != expected_sha256:
        raise RuntimeError(f"model weight SHA-256 {actual} != pinned {expected_sha256}")
    return {"path": str(weight.resolve()), "bytes": weight.stat().st_size, "sha256": actual}


def write_or_verify_json(path: Path, value: dict[str, Any]) -> None:
    rendered = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != rendered:
        raise RuntimeError(f"resume input report changed: {path}")
    if not path.exists():
        path.write_text(rendered, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("repair_public", "clean_base"), required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--mixture-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--run-purpose", choices=RUN_PURPOSES, required=True)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--stop-after-step", type=int)
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument(
        "--seed", type=int,
        help="optional training seed; generated and recorded for a new run when omitted",
    )
    parser.add_argument(
        "--config", type=Path,
        default=REPO_ROOT / "training/config/sotto-lfm-training-v1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    effective_max_steps = validate_controls(
        args.run_purpose, args.max_steps, args.stop_after_step, args.resume_from,
    )
    prior_resolved_path = args.run_dir / "resolved-config.json"
    if args.resume_from is not None:
        if not prior_resolved_path.is_file():
            raise RuntimeError("resume run is missing its resolved configuration")
        prior_seed = json.loads(prior_resolved_path.read_text(encoding="utf-8")).get("seed")
        if not isinstance(prior_seed, int):
            raise RuntimeError("resume run has no recorded integer seed")
        if args.seed is not None and args.seed != prior_seed:
            raise RuntimeError("resume seed differs from the original run")
        seed = prior_seed
    else:
        seed = args.seed if args.seed is not None else secrets.randbelow(2**32)
    if not 0 <= seed < 2**32:
        raise RuntimeError("training seed must fit NumPy's unsigned 32-bit seed range")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config.get("config_version") != "sotto-lfm-full-sft-v1":
        raise RuntimeError("unexpected Sotto LFM training configuration version")
    data_config_path = REPO_ROOT / config["data_config_path"]
    repository = git_report()
    mixture_manifest_path = args.mixture_dir / "mixture-manifest.json"
    mixture_manifest = json.loads(mixture_manifest_path.read_text(encoding="utf-8"))
    train_path, dev_path = verify_mixture(args.mixture_dir, mixture_manifest, data_config_path)
    train_rows, dev_rows = read_jsonl(train_path), read_jsonl(dev_path)
    for split, rows in (("train", train_rows), ("dev", dev_rows)):
        expected = mixture_manifest["streams"][split]["records"]
        if len(rows) != expected:
            raise RuntimeError(f"{split} record count {len(rows)} != manifest {expected}")

    arm = config["arms"][args.arm]
    common = config["common"]
    dataset_config = config["dataset"]
    if common["train_batch_size"] != 1 or common["eval_batch_size"] != 1:
        raise RuntimeError("packed LFM training requires microbatch one")
    if common["train_batch_size"] * common["gradient_accumulation_steps"] != common["effective_packed_batch_size"]:
        raise RuntimeError("effective packed batch size differs from microbatch × accumulation")
    if not (
        dataset_config["packing"] and dataset_config["assistant_only_loss"]
        and dataset_config["reset_position_ids_per_example"]
        and dataset_config["pass_seq_idx_for_hybrid_state_reset"]
        and not dataset_config["silent_truncation"]
    ):
        raise RuntimeError("required LFM packing safeguards are disabled")
    weight_report = verify_model_weights(args.model_dir, arm["expected_model_weight_sha256"])

    if args.run_dir.exists() and args.resume_from is None:
        unexpected = [path.name for path in args.run_dir.iterdir() if path.name != "console.log"]
        if unexpected:
            raise RuntimeError(f"new run directory contains unexpected files: {sorted(unexpected)}")
    args.run_dir.mkdir(parents=True, exist_ok=True)
    resolved = {
        "config_version": config["config_version"], "arm": args.arm,
        "run_purpose": args.run_purpose, "model": arm, "dataset": dataset_config,
        "common": common, "seed": seed, "effective_max_steps": effective_max_steps,
        "input_hashes": {
            "training_config_sha256": sha256_file(args.config),
            "data_config_sha256": sha256_file(data_config_path),
            "trainer_sha256": sha256_file(REPO_ROOT / "scripts/training/train_sotto_lfm.py"),
            "mixture_manifest_sha256": sha256_file(mixture_manifest_path),
            "train_sha256": sha256_file(train_path), "dev_sha256": sha256_file(dev_path),
        },
        "model_weight": weight_report,
    }
    write_or_verify_json(args.run_dir / "resolved-config.json", resolved)
    write_or_verify_json(args.run_dir / "repository.json", repository)
    with (args.run_dir / "invocations.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "invoked_at": datetime.now(timezone.utc).isoformat(),
            "resume_from": str(args.resume_from.resolve()) if args.resume_from else None,
            "stop_after_step": args.stop_after_step,
        }, sort_keys=True) + "\n")
    (args.run_dir / "status.json").write_text(json.dumps({
        "status": "running", "started_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2) + "\n", encoding="utf-8")

    telemetry: Telemetry | None = None
    try:
        import torch
        from torch.utils.data import Dataset, SequentialSampler
        from transformers import AutoModelForCausalLM, AutoTokenizer, Trainer, TrainerCallback, TrainingArguments

        tokenizer = AutoTokenizer.from_pretrained(
            args.model_dir, local_files_only=True, trust_remote_code=common["trust_remote_code"],
        )
        max_tokens = dataset_config["max_sequence_tokens"]
        encoded_train = [
            encode_record(tokenizer, config["prompt_template"], row, max_tokens)
            for row in train_rows
        ]
        encoded_dev = [
            encode_record(tokenizer, config["prompt_template"], row, max_tokens)
            for row in dev_rows
        ]
        full_audit = {
            "train": token_audit(encoded_train, max_tokens),
            "dev": token_audit(encoded_dev, max_tokens),
        }
        selection = "all"
        if args.run_purpose in {"overfit32", "resume_smoke"}:
            limit = 32 if args.run_purpose == "overfit32" else 64
            encoded_train = encoded_train[:limit]
            encoded_dev = encoded_train if args.run_purpose == "overfit32" else encoded_dev[:limit]
            selection = "train_prefix" if args.run_purpose == "overfit32" else "stream_prefix"
        elif args.run_purpose == "longest_smoke":
            encoded_train = sorted(encoded_train, key=lambda row: len(row["input_ids"]), reverse=True)[:32]
            encoded_dev = sorted(encoded_dev, key=lambda row: len(row["input_ids"]), reverse=True)[:32]
            selection = "longest_formatted"
        packed_train = pack_examples(encoded_train, max_tokens)
        packed_dev = pack_examples(encoded_dev, max_tokens)
        audit = {
            "selection": selection, "full_corpus": full_audit,
            "selected": {
                "train": token_audit(encoded_train, max_tokens),
                "dev": token_audit(encoded_dev, max_tokens),
            },
            "packing": {
                "train": packing_audit(packed_train, len(encoded_train), max_tokens),
                "dev": packing_audit(packed_dev, len(encoded_dev), max_tokens),
            },
        }
        write_or_verify_json(args.run_dir / "tokenization-audit.json", audit)
        if args.run_purpose == "format_audit":
            (args.run_dir / "status.json").write_text(json.dumps({
                "status": "complete", "finished_at": datetime.now(timezone.utc).isoformat(),
                "purpose": "format_audit",
            }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return 0

        if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
            raise RuntimeError("training requires CUDA with bfloat16 support")
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cuda.matmul.allow_tf32 = common["tf32"]
        model = AutoModelForCausalLM.from_pretrained(
            args.model_dir, local_files_only=True, dtype=torch.bfloat16,
            trust_remote_code=common["trust_remote_code"],
            attn_implementation=common["attention_implementation"],
        )
        model.config.use_cache = False
        trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
        total = sum(parameter.numel() for parameter in model.parameters())
        if trainable != total:
            raise RuntimeError(f"full fine-tuning requires every parameter trainable: {trainable}/{total}")
        write_or_verify_json(args.run_dir / "model-parameters.json", {
            "method": "full_parameter_sft", "trainable": trainable, "total": total,
            "trainable_fraction": trainable / total,
        })

        class PackedDataset(Dataset):
            def __init__(self, rows: Sequence[dict[str, Any]]) -> None:
                self.rows = rows
            def __len__(self) -> int:
                return len(self.rows)
            def __getitem__(self, index: int) -> dict[str, list[int]]:
                row = self.rows[index]
                return {key: row[key] for key in ("input_ids", "labels", "position_ids", "seq_idx")}

        class PackedCollator:
            def __call__(self, features: list[dict[str, list[int]]]) -> dict[str, Any]:
                if len(features) != 1:
                    raise RuntimeError("LFM packed collator requires microbatch one")
                return {
                    key: torch.tensor([features[0][key]], dtype=torch.long)
                    for key in ("input_ids", "labels", "position_ids", "seq_idx")
                }

        class OrderedTrainer(Trainer):
            def _get_train_sampler(self, train_dataset: Any | None = None) -> Any:
                return SequentialSampler(train_dataset if train_dataset is not None else self.train_dataset)

        class MetricsCallback(TrainerCallback):
            def __init__(self, delegate: JsonlMetricsCallback) -> None:
                self.delegate = delegate
            def on_log(self, trainer_args: Any, state: Any, control: Any, logs: dict[str, Any] | None = None, **kwargs: Any) -> None:
                self.delegate.on_log(trainer_args, state, control, logs, **kwargs)

        stop_after_step = args.stop_after_step

        class IntentionalPauseCallback(TrainerCallback):
            def on_step_end(self, trainer_args: Any, state: Any, control: Any, **_: Any) -> Any:
                if stop_after_step is not None and state.global_step >= stop_after_step:
                    control.should_save = True
                    control.should_training_stop = True
                return control

        full = args.run_purpose == "full"
        smoke = not full
        if full:
            save_strategy, save_steps = "epoch", 500
        elif args.run_purpose == "resume_smoke":
            save_strategy, save_steps = "steps", 1
        else:
            save_strategy, save_steps = "no", 500
        training_args = TrainingArguments(
            output_dir=str(args.run_dir), num_train_epochs=arm["epochs"],
            max_steps=effective_max_steps,
            per_device_train_batch_size=common["train_batch_size"],
            per_device_eval_batch_size=common["eval_batch_size"],
            gradient_accumulation_steps=common["gradient_accumulation_steps"],
            learning_rate=arm["learning_rate"], weight_decay=common["weight_decay"],
            warmup_steps=common["warmup_steps"], lr_scheduler_type=common["lr_scheduler_type"],
            optim=common["optimizer"], adam_beta1=common["adam_beta1"],
            adam_beta2=common["adam_beta2"], adam_epsilon=common["adam_epsilon"],
            max_grad_norm=common["max_grad_norm"], logging_strategy="steps",
            logging_steps=1 if smoke else common["logging_steps"], logging_first_step=True,
            eval_strategy="epoch" if full else "no",
            save_strategy=save_strategy, save_steps=save_steps,
            save_total_limit=arm["save_total_limit"], bf16=common["bf16"], tf32=common["tf32"],
            gradient_checkpointing=common["gradient_checkpointing"], seed=seed,
            data_seed=seed, report_to=[], remove_unused_columns=False,
            prediction_loss_only=True, dataloader_num_workers=0,
        )
        callbacks: list[Any] = [MetricsCallback(JsonlMetricsCallback(args.run_dir / "metrics.jsonl"))]
        if stop_after_step is not None:
            callbacks.append(IntentionalPauseCallback())
        trainer = OrderedTrainer(
            model=model, args=training_args, train_dataset=PackedDataset(packed_train),
            eval_dataset=PackedDataset(packed_dev), data_collator=PackedCollator(),
            callbacks=callbacks,
        )
        telemetry = Telemetry(args.run_dir)
        telemetry.start()
        initial_overfit_metrics = (
            trainer.evaluate(metric_key_prefix="initial_overfit")
            if args.run_purpose == "overfit32" else None
        )
        result = trainer.train(resume_from_checkpoint=str(args.resume_from) if args.resume_from else None)
        if stop_after_step is not None and trainer.state.global_step < effective_max_steps:
            checkpoint = args.run_dir / f"checkpoint-{trainer.state.global_step}"
            if not checkpoint.is_dir():
                raise RuntimeError(f"intentional pause did not create {checkpoint}")
            status = {
                "status": "paused_for_resume_smoke",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "global_step": trainer.state.global_step,
                "resume_checkpoint": str(checkpoint.resolve()), "train_metrics": result.metrics,
            }
            (args.run_dir / "status.json").write_text(
                json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8",
            )
            return 0
        expected_steps = (
            math.ceil(len(packed_train) / common["gradient_accumulation_steps"]) * arm["epochs"]
            if full else effective_max_steps
        )
        if trainer.state.global_step != expected_steps:
            raise RuntimeError(f"completed at optimizer step {trainer.state.global_step}, expected {expected_steps}")
        final_overfit_metrics = (
            trainer.evaluate(metric_key_prefix="final_overfit")
            if args.run_purpose == "overfit32" else None
        )
        if initial_overfit_metrics is not None and final_overfit_metrics is not None:
            initial_loss = initial_overfit_metrics["initial_overfit_loss"]
            final_loss = final_overfit_metrics["final_overfit_loss"]
            if not final_loss < initial_loss:
                raise RuntimeError(f"32-row overfit loss did not decrease: {initial_loss} -> {final_loss}")
        final_model = args.run_dir / "final-model"
        trainer.save_model(str(final_model))
        tokenizer.save_pretrained(final_model)
        trainer.save_state()
        (args.run_dir / "status.json").write_text(json.dumps({
            "status": "complete", "finished_at": datetime.now(timezone.utc).isoformat(),
            "global_step": trainer.state.global_step, "train_metrics": result.metrics,
            "initial_overfit_metrics": initial_overfit_metrics,
            "final_overfit_metrics": final_overfit_metrics,
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
        if telemetry is not None:
            telemetry.stop()


if __name__ == "__main__":
    raise SystemExit(main())
