#!/usr/bin/env python3
"""Train one pinned cleanup LoRA with assistant-only loss and resumable state."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise RuntimeError(f"{path}:{line_number}: expected an object")
                values.append(value)
    return values


def prompt_messages(instruction: str, raw: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": instruction},
        {"role": "user", "content": "Transcript:\n" + raw},
    ]


def apply_template(tokenizer: Any, messages: list[dict[str, str]], *, add_generation_prompt: bool, kwargs: dict[str, Any]) -> list[int]:
    value = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=add_generation_prompt,
        **kwargs,
    )
    if hasattr(value, "get"):
        input_ids = value.get("input_ids")
        if input_ids is None:
            raise RuntimeError("chat template mapping did not contain input_ids")
        value = input_ids
    if hasattr(value, "tolist"):
        value = value.tolist()
    if value and isinstance(value[0], list):
        if len(value) != 1:
            raise RuntimeError("chat template unexpectedly returned a batch")
        value = value[0]
    if not isinstance(value, list) or any(not isinstance(item, int) for item in value):
        raise RuntimeError("chat template did not return token IDs")
    return value


def encode_record(
    tokenizer: Any,
    instruction: str,
    row: dict[str, Any],
    max_tokens: int,
    template_kwargs: dict[str, Any],
) -> dict[str, list[int]]:
    messages = prompt_messages(instruction, row["raw"])
    prompt_ids = apply_template(
        tokenizer, messages, add_generation_prompt=True, kwargs=template_kwargs
    )
    full_messages = [*messages, {"role": "assistant", "content": row["expected"]}]
    full_ids = apply_template(
        tokenizer, full_messages, add_generation_prompt=False, kwargs=template_kwargs
    )
    if full_ids[:len(prompt_ids)] != prompt_ids:
        raise RuntimeError(f"{row.get('id')}: assistant target is not prefixed by the generation prompt")
    if len(full_ids) > max_tokens:
        raise RuntimeError(
            f"{row.get('id')}: formatted length {len(full_ids)} exceeds {max_tokens}; truncation is forbidden"
        )
    target_tokens = len(full_ids) - len(prompt_ids)
    if target_tokens <= 0:
        raise RuntimeError(f"{row.get('id')}: assistant target produced no tokens")
    return {
        "input_ids": full_ids,
        "attention_mask": [1] * len(full_ids),
        "labels": [-100] * len(prompt_ids) + full_ids[len(prompt_ids):],
    }


def resolved_config(
    config: dict[str, Any],
    model_key: str,
    train: Path,
    dev: Path,
    gate_report: Path,
    config_path: Path,
    run_purpose: str,
    max_steps: int,
) -> dict[str, Any]:
    if model_key not in config["models"]:
        raise RuntimeError(f"unknown model key: {model_key}")
    common = config["common"]
    if common["train_batch_size"] * common["gradient_accumulation_steps"] != common["effective_batch_size"]:
        raise RuntimeError("effective batch size does not match batch × gradient accumulation")
    return {
        "config_version": config["config_version"],
        "instruction_path": config["instruction_path"],
        "model_key": model_key,
        "model": config["models"][model_key],
        "dataset": config["dataset"],
        "common": common,
        "run_controls": {
            "purpose": run_purpose,
            "max_steps": max_steps,
            "train_record_limit": 32 if run_purpose == "overfit32" else (64 if run_purpose == "resume_smoke" else None),
            "dev_source": "selected_train_rows" if run_purpose == "overfit32" else "authoring_dev",
        },
        "intentional_architecture_differences": config["intentional_architecture_differences"],
        "input_hashes": {
            "train_sha256": sha256_file(train), "dev_sha256": sha256_file(dev),
            "gate_a_report_sha256": sha256_file(gate_report),
            "instruction_sha256": sha256_file(REPO_ROOT / config["instruction_path"]),
            "training_config_sha256": sha256_file(config_path),
        },
    }


def git_report() -> dict[str, Any]:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True, capture_output=True, check=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain=v1"], cwd=REPO_ROOT, text=True, capture_output=True, check=True).stdout.splitlines()
    return {"commit": commit, "dirty": bool(dirty), "dirty_paths": [line[3:] for line in dirty]}


def committed_file_sha256(path: Path) -> str:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(REPO_ROOT.resolve())
    except ValueError as exc:
        raise RuntimeError(f"reproducibility input must be inside the repository: {path}") from exc
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(relative)], cwd=REPO_ROOT,
        text=True, capture_output=True,
    )
    if tracked.returncode != 0:
        raise RuntimeError(f"reproducibility input is not committed: {relative}")
    committed = subprocess.run(
        ["git", "show", f"HEAD:{relative.as_posix()}"], cwd=REPO_ROOT,
        capture_output=True,
    )
    if committed.returncode != 0:
        raise RuntimeError(f"cannot read committed reproducibility input: {relative}")
    return hashlib.sha256(committed.stdout).hexdigest()


def verify_clean_committed_run_inputs(
    repository: dict[str, Any], config_path: Path, gate_path: Path, instruction_path: Path
) -> None:
    if repository["dirty"]:
        raise RuntimeError("training and GPU smoke runs require a clean committed repository")
    for path in (config_path, gate_path, instruction_path):
        if committed_file_sha256(path) != sha256_file(path):
            raise RuntimeError(f"working bytes differ from HEAD for required input: {path}")


class Telemetry:
    def __init__(self, run_dir: Path, interval_seconds: int = 30) -> None:
        self.path = run_dir / "gpu-telemetry.jsonl"
        self.interval_seconds = interval_seconds
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, name="gpu-telemetry", daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=self.interval_seconds + 5)

    def _run(self) -> None:
        query = "timestamp,index,uuid,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit"
        while not self.stop_event.is_set():
            result = subprocess.run(
                ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
                text=True, capture_output=True,
            )
            disk = shutil.disk_usage(self.path.parent)
            event = {
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "nvidia_smi_returncode": result.returncode,
                "gpu_csv": result.stdout.strip().splitlines() if result.returncode == 0 else [],
                "gpu_error": result.stderr.strip() if result.returncode else "",
                "disk_free_bytes": disk.free,
            }
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, sort_keys=True) + "\n")
                handle.flush()
            self.stop_event.wait(self.interval_seconds)


class JsonlMetricsCallback:
    """Constructed without importing Transformers at module import time for unit testing."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def on_log(self, args: Any, state: Any, control: Any, logs: dict[str, Any] | None = None, **_: Any) -> None:
        event = {"observed_at": datetime.now(timezone.utc).isoformat(), "step": state.global_step, **(logs or {})}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
            handle.flush()


def validate_run_controls(run_purpose: str, max_steps: int, stop_after_step: int | None) -> None:
    if run_purpose == "pilot":
        if max_steps != -1 or stop_after_step is not None:
            raise RuntimeError("pilot runs use the fixed epoch schedule and cannot set step controls")
        return
    if max_steps <= 0:
        raise RuntimeError(f"{run_purpose} requires a positive --max-steps")
    if run_purpose == "overfit32" and stop_after_step is not None:
        raise RuntimeError("overfit32 cannot use --stop-after-step")
    if stop_after_step is not None and not 0 < stop_after_step < max_steps:
        raise RuntimeError("--stop-after-step must be positive and lower than --max-steps")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-key", required=True, choices=("qwen3_0_6b", "qwen35_0_8b"))
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--gate-a-report", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--run-purpose", required=True, choices=("overfit32", "resume_smoke", "pilot"))
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "training/config/pilot-training-v1.json")
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--max-steps", type=int, default=-1, help="required for overfit/resume smoke; forbidden for pilot")
    parser.add_argument(
        "--stop-after-step", type=int,
        help="resume-smoke phase 1 only: save and intentionally pause before max_steps",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate_run_controls(args.run_purpose, args.max_steps, args.stop_after_step)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    repository = git_report()
    verify_clean_committed_run_inputs(
        repository, args.config, args.gate_a_report, REPO_ROOT / config["instruction_path"]
    )
    resolved = resolved_config(
        config, args.model_key, args.train, args.dev, args.gate_a_report, args.config,
        args.run_purpose, args.max_steps,
    )
    expected_counts = config["dataset"]
    train_rows, dev_rows = read_jsonl(args.train), read_jsonl(args.dev)
    if len(train_rows) != expected_counts["train_records"] or len(dev_rows) != expected_counts["dev_records"]:
        raise RuntimeError("training inputs do not match the fixed 5,000/500 pilot")
    gate = json.loads(args.gate_a_report.read_text(encoding="utf-8"))
    if gate.get("status") != "pass" or gate.get("gate") != "pilot_gate_a":
        raise RuntimeError("training requires a passing pilot Gate A report")
    if gate["dataset_files"][0]["sha256"] != sha256_file(args.train) or gate["dataset_files"][1]["sha256"] != sha256_file(args.dev):
        raise RuntimeError("training data hashes differ from Gate A")
    if args.run_purpose == "overfit32":
        train_rows = train_rows[:32]
        dev_rows = list(train_rows)
    elif args.run_purpose == "resume_smoke":
        train_rows = train_rows[:64]
    if args.resume_from:
        if not args.run_dir.is_dir() or not (args.run_dir / "resolved-config.json").is_file():
            raise RuntimeError("resume requires the original run directory and resolved config")
        previous = json.loads((args.run_dir / "resolved-config.json").read_text(encoding="utf-8"))
        if previous != resolved:
            raise RuntimeError("resume resolved config differs from the original run")
        if not args.resume_from.is_dir() or args.run_dir.resolve() not in args.resume_from.resolve().parents:
            raise RuntimeError("resume checkpoint must be inside the original run directory")
    else:
        if args.run_dir.exists() and any(args.run_dir.iterdir()):
            raise RuntimeError("new run directory must not already contain files")
        args.run_dir.mkdir(parents=True, exist_ok=True)
        (args.run_dir / "resolved-config.json").write_text(json.dumps(resolved, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.run_dir / "repository.json").write_text(json.dumps(repository, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (args.run_dir / "invocations.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "invoked_at": datetime.now(timezone.utc).isoformat(),
            "resume_from": str(args.resume_from) if args.resume_from else None,
            "stop_after_step": args.stop_after_step,
        }, sort_keys=True) + "\n")
    (args.run_dir / "status.json").write_text(json.dumps({"status": "running", "started_at": datetime.now(timezone.utc).isoformat()}, indent=2) + "\n", encoding="utf-8")

    telemetry = Telemetry(args.run_dir)
    telemetry.start()
    try:
        import torch
        import transformers
        from peft import LoraConfig, get_peft_model
        from transformers import AutoTokenizer, Trainer, TrainingArguments, TrainerCallback

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is not available")
        if not torch.cuda.is_bf16_supported():
            raise RuntimeError("GPU does not report bfloat16 support")
        torch.manual_seed(config["common"]["seed"])
        torch.cuda.manual_seed_all(config["common"]["seed"])
        model_config = resolved["model"]
        tokenizer = AutoTokenizer.from_pretrained(
            model_config["model_id"], revision=model_config["revision"],
            trust_remote_code=config["common"]["trust_remote_code"],
        )
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
        instruction = (REPO_ROOT / config["instruction_path"]).read_text(encoding="utf-8").strip()
        max_tokens = config["dataset"]["max_sequence_tokens"]
        template_kwargs = model_config["chat_template_kwargs"]
        encoded_train = [encode_record(tokenizer, instruction, row, max_tokens, template_kwargs) for row in train_rows]
        encoded_dev = [encode_record(tokenizer, instruction, row, max_tokens, template_kwargs) for row in dev_rows]

        model_class = getattr(transformers, model_config["model_class"])
        model = model_class.from_pretrained(
            model_config["model_id"], revision=model_config["revision"],
            torch_dtype=torch.bfloat16,
            trust_remote_code=config["common"]["trust_remote_code"],
            attn_implementation=config["common"]["attention_implementation"],
        )
        model.config.use_cache = False
        lora = LoraConfig(
            r=config["common"]["lora_rank"], lora_alpha=config["common"]["lora_alpha"],
            lora_dropout=config["common"]["lora_dropout"], bias=config["common"]["lora_bias"],
            task_type="CAUSAL_LM", target_modules=model_config["lora_target_modules"],
            exclude_modules=model_config["lora_exclude_modules"],
        )
        model = get_peft_model(model, lora)
        trainable, total = model.get_nb_trainable_parameters()
        (args.run_dir / "model-parameters.json").write_text(json.dumps({"trainable": trainable, "total": total}, indent=2) + "\n", encoding="utf-8")

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
                return {"input_ids": torch.tensor(input_ids), "attention_mask": torch.tensor(attention_mask), "labels": torch.tensor(labels)}

        class Callback(TrainerCallback):
            def __init__(self, delegate: JsonlMetricsCallback) -> None:
                self.delegate = delegate
            def on_log(self, args: Any, state: Any, control: Any, logs: dict[str, Any] | None = None, **kwargs: Any) -> None:
                self.delegate.on_log(args, state, control, logs, **kwargs)

        class IntentionalPauseCallback(TrainerCallback):
            def on_step_end(self, args: Any, state: Any, control: Any, **_: Any) -> Any:
                if args_stop_after_step is not None and state.global_step >= args_stop_after_step:
                    control.should_save = True
                    control.should_training_stop = True
                return control

        common = config["common"]
        training_args = TrainingArguments(
            output_dir=str(args.run_dir), overwrite_output_dir=False,
            num_train_epochs=common["epochs"], max_steps=args.max_steps,
            per_device_train_batch_size=common["train_batch_size"], per_device_eval_batch_size=common["eval_batch_size"],
            gradient_accumulation_steps=common["gradient_accumulation_steps"],
            learning_rate=common["learning_rate"], weight_decay=common["weight_decay"], warmup_ratio=common["warmup_ratio"],
            lr_scheduler_type=common["lr_scheduler_type"], optim=common["optimizer"], max_grad_norm=common["max_grad_norm"],
            logging_strategy="steps", logging_steps=common["logging_steps"],
            eval_strategy="steps", eval_steps=common["eval_steps"],
            save_strategy="steps", save_steps=common["save_steps"], save_total_limit=common["save_total_limit"],
            bf16=common["bf16"], tf32=common["tf32"], gradient_checkpointing=common["gradient_checkpointing"],
            seed=common["seed"], data_seed=common["data_seed"], report_to=[], remove_unused_columns=False,
        )
        callbacks: list[Any] = [Callback(JsonlMetricsCallback(args.run_dir / "metrics.jsonl"))]
        args_stop_after_step = args.stop_after_step
        if args.stop_after_step is not None:
            callbacks.append(IntentionalPauseCallback())
        trainer = Trainer(
            model=model, args=training_args, train_dataset=Dataset(encoded_train), eval_dataset=Dataset(encoded_dev),
            data_collator=Collator(), callbacks=callbacks,
        )
        result = trainer.train(resume_from_checkpoint=str(args.resume_from) if args.resume_from else None)
        if args.stop_after_step is not None and trainer.state.global_step < args.max_steps:
            checkpoint = args.run_dir / f"checkpoint-{trainer.state.global_step}"
            if not checkpoint.is_dir():
                raise RuntimeError(f"intentional pause did not create {checkpoint}")
            terminal = {
                "status": "paused_for_resume_smoke",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "global_step": trainer.state.global_step,
                "resume_checkpoint": str(checkpoint),
                "train_metrics": result.metrics,
            }
            (args.run_dir / "status.json").write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            return 0
        trainer.save_model(str(args.run_dir / "final-adapter"))
        trainer.save_state()
        terminal = {"status": "complete", "finished_at": datetime.now(timezone.utc).isoformat(), "global_step": trainer.state.global_step, "train_metrics": result.metrics}
        (args.run_dir / "status.json").write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 0
    except BaseException as exc:
        terminal = {"status": "failed", "finished_at": datetime.now(timezone.utc).isoformat(), "error_type": type(exc).__name__, "error": str(exc)}
        (args.run_dir / "status.json").write_text(json.dumps(terminal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        traceback.print_exc()
        return 1
    finally:
        telemetry.stop()


if __name__ == "__main__":
    raise SystemExit(main())
