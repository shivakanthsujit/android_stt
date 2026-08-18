#!/usr/bin/env python3
"""Reproducible text-to-WAV preparation for Local Flow evaluation corpora."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import re
import shutil
import subprocess
import unicodedata
import wave
from array import array
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CANONICAL_SAMPLE_RATE = 16_000
CANONICAL_CHANNELS = 1
CANONICAL_SAMPLE_WIDTH = 2


@dataclass(frozen=True)
class TtsCase:
    case_id: str
    text: str
    categories: tuple[str, ...]
    source_corpus: str
    source_path: str


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def atomic_write(path: Path, content: str) -> None:
    temporary = path.with_name(f".{path.name}.partial")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError(f"Expected a JSON object at {path}:{line_number}")
        rows.append(value)
    if not rows:
        raise RuntimeError(f"No records found in {path}")
    return rows


def normalize_text(value: Any, *, location: str) -> str:
    if not isinstance(value, str):
        raise RuntimeError(f"Non-string spoken text at {location}")
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized:
        raise RuntimeError(f"Empty spoken text at {location}")
    if "\x00" in normalized:
        raise RuntimeError(f"NUL in spoken text at {location}")
    return normalized


def validate_categories(value: Any, *, location: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise RuntimeError(f"Invalid categories at {location}")
    return tuple(value)


def project_cleanup_cases(path: Path, source_corpus: str, repo_root: Path) -> list[TtsCase]:
    allowed = {
        (repo_root / "docs/evaluation/cleanup_cases.jsonl").resolve(),
        (repo_root / "docs/evaluation/cleanup_cases_heldout_v1.jsonl").resolve(),
    }
    resolved = path.resolve()
    if resolved not in allowed:
        raise RuntimeError(f"Cleanup TTS source is not allowlisted: {path}")
    cases: list[TtsCase] = []
    for index, row in enumerate(read_jsonl(resolved), 1):
        # Deliberately project only evaluation input metadata. Never propagate raw,
        # expected, prompts, or captured model output into the TTS backend context.
        case_id = row.get("id")
        if not isinstance(case_id, str) or not SAFE_ID.fullmatch(case_id):
            raise RuntimeError(f"Unsafe case id at {path}:{index}")
        cases.append(
            TtsCase(
                case_id=case_id,
                text=normalize_text(row.get("spoken"), location=f"{path}:{index}"),
                categories=validate_categories(row.get("categories"), location=f"{path}:{index}"),
                source_corpus=source_corpus,
                source_path=str(resolved.relative_to(repo_root.resolve())),
            )
        )
    return cases


def project_additional_cases(path: Path, repo_root: Path) -> list[TtsCase]:
    resolved = path.resolve()
    allowed_sources = {
        (repo_root / "docs/evaluation/stt_personal_conversation_tts_cases_v2.jsonl").resolve():
            "project-authored-personal-conversation-tts-v2",
        (repo_root / "docs/evaluation/stt_personal_conversation_tts_cases_v3.jsonl").resolve():
            "project-authored-personal-conversation-tts-v3",
    }
    if resolved not in allowed_sources:
        raise RuntimeError(f"Additional TTS source is not allowlisted: {path}")
    cases: list[TtsCase] = []
    for index, row in enumerate(read_jsonl(resolved), 1):
        allowed_keys = {"id", "spoken", "expected", "categories", "must_preserve"}
        if not set(row).issubset(allowed_keys):
            raise RuntimeError(f"Unexpected field at {path}:{index}")
        case_id = row.get("id")
        if not isinstance(case_id, str) or not SAFE_ID.fullmatch(case_id):
            raise RuntimeError(f"Unsafe case id at {path}:{index}")
        cases.append(
            TtsCase(
                case_id=case_id,
                text=normalize_text(row.get("spoken"), location=f"{path}:{index}"),
                categories=validate_categories(row.get("categories"), location=f"{path}:{index}"),
                source_corpus=allowed_sources[resolved],
                source_path=str(resolved.relative_to(repo_root.resolve())),
            )
        )
    return cases


def validate_cases(cases: Iterable[TtsCase]) -> list[TtsCase]:
    materialized = list(cases)
    if not materialized:
        raise RuntimeError("At least one TTS case is required")
    seen: set[str] = set()
    for case in materialized:
        if not SAFE_ID.fullmatch(case.case_id):
            raise RuntimeError(f"Unsafe case id: {case.case_id}")
        if case.case_id in seen:
            raise RuntimeError(f"Duplicate case id: {case.case_id}")
        seen.add(case.case_id)
    return materialized


def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("schema_version") != 1:
        raise RuntimeError("Unsupported TTS profile schema")
    for group in ("runtime", "model", "generation", "output"):
        if not isinstance(profile.get(group), dict):
            raise RuntimeError(f"Missing TTS profile group: {group}")
    model_revision = profile["model"].get("revision")
    runtime_revision = profile["runtime"].get("revision")
    if not isinstance(model_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", model_revision):
        raise RuntimeError("Model revision must be a full commit hash")
    if not isinstance(runtime_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", runtime_revision):
        raise RuntimeError("Runtime revision must be a full commit hash")
    if profile["output"] != {
        "sample_rate_hz": 16000,
        "channels": 1,
        "sample_width_bits": 16,
        "codec": "pcm_s16le",
    }:
        raise RuntimeError("TTS output profile must be canonical 16 kHz mono PCM16")


def case_seed(case: TtsCase, base_seed: int) -> int:
    digest = hashlib.sha256(
        f"{base_seed}\0{case.case_id}\0{case.text}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:4], "big")


def generation_plan(cases: list[TtsCase], base_seed: int) -> list[dict[str, Any]]:
    return [
        {
            "case_id": case.case_id,
            "text": case.text,
            "text_sha256": sha256_bytes(case.text.encode("utf-8")),
            "categories": list(case.categories),
            "source_corpus": case.source_corpus,
            "source_path": case.source_path,
            "source_text_field": "spoken",
            "seed": case_seed(case, base_seed),
        }
        for case in cases
    ]


def ffmpeg_version(ffmpeg: str) -> str:
    return subprocess.run(
        [ffmpeg, "-version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]


def canonicalize_wav(source: Path, destination: Path, ffmpeg: str) -> None:
    temporary = destination.with_name(f".{destination.stem}.canonical.wav")
    subprocess.run(
        [
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map_metadata",
            "-1",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(temporary),
        ],
        check=True,
    )
    inspect_wav(temporary, require_canonical=True)
    temporary.replace(destination)


def inspect_wav(path: Path, *, require_canonical: bool) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            sample_rate = handle.getframerate()
            frames = handle.getnframes()
            compression = handle.getcomptype()
            payload = handle.readframes(frames)
    except (EOFError, wave.Error) as error:
        raise RuntimeError(f"Invalid WAV {path}: {error}") from error
    if compression != "NONE" or channels <= 0 or sample_width != 2 or sample_rate <= 0 or frames <= 0:
        raise RuntimeError(f"Unsupported or empty PCM16 WAV: {path}")
    if require_canonical and (channels, sample_width, sample_rate) != (
        CANONICAL_CHANNELS,
        CANONICAL_SAMPLE_WIDTH,
        CANONICAL_SAMPLE_RATE,
    ):
        raise RuntimeError(f"WAV is not 16 kHz mono PCM16: {path}")
    samples = array("h")
    samples.frombytes(payload)
    if os.sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        raise RuntimeError(f"WAV has no samples: {path}")
    peak = max(abs(value) for value in samples)
    sum_squares = sum(value * value for value in samples)
    rms = math.sqrt(sum_squares / len(samples))
    clipped = sum(abs(value) >= 32767 for value in samples)
    clipping_ratio = clipped / len(samples)
    if rms < 1.0:
        raise RuntimeError(f"WAV is effectively silent: {path}")
    if clipping_ratio > 0.02:
        raise RuntimeError(f"WAV is grossly clipped ({clipping_ratio:.2%}): {path}")
    return {
        "sample_rate_hz": sample_rate,
        "channels": channels,
        "sample_width_bits": sample_width * 8,
        "frames": frames,
        "duration_ms": round(frames * 1000 / sample_rate, 3),
        "peak_pcm16": peak,
        "rms_pcm16": round(rms, 3),
        "clipping_ratio": clipping_ratio,
    }


class MlxAudioBackend:
    def __init__(self, profile: dict[str, Any]) -> None:
        from mlx_audio.tts.utils import load_model

        actual_version = importlib.metadata.version("mlx-audio")
        expected_version = str(profile["runtime"]["version"])
        if actual_version != expected_version:
            raise RuntimeError(
                f"mlx-audio version mismatch: expected {expected_version}, got {actual_version}"
            )
        self.profile = profile
        self.model = load_model(
            profile["model"]["repository"],
            revision=profile["model"]["revision"],
        )

    def generate(self, case: TtsCase, seed: int, destination: Path) -> dict[str, Any]:
        import mlx.core as mx
        import numpy as np
        from mlx_audio.audio_io import write as audio_write

        mx.random.seed(seed)
        settings = self.profile["generation"]
        results = list(
            self.model.generate(
                text=case.text,
                voice=self.profile["voice"],
                instruct=self.profile.get("instruct"),
                lang_code=self.profile["language"],
                temperature=float(settings["temperature"]),
                top_k=int(settings["top_k"]),
                top_p=float(settings["top_p"]),
                repetition_penalty=float(settings["repetition_penalty"]),
                max_tokens=int(settings["max_tokens"]),
                verbose=False,
                stream=False,
            )
        )
        if not results:
            raise RuntimeError(f"TTS returned no audio for {case.case_id}")
        sample_rates = {int(result.sample_rate) for result in results}
        if len(sample_rates) != 1:
            raise RuntimeError(f"TTS returned mixed sample rates for {case.case_id}")
        audio = mx.concatenate([result.audio for result in results], axis=0)
        mx.eval(audio)
        temporary = destination.with_name(f".{destination.stem}.native.wav")
        audio_write(str(temporary), np.asarray(audio), sample_rates.pop(), format="wav")
        inspect_wav(temporary, require_canonical=False)
        temporary.replace(destination)
        return {
            "segments": len(results),
            "processing_time_seconds": round(
                sum(float(result.processing_time_seconds) for result in results), 6
            ),
            "peak_memory_gb": round(
                max(float(result.peak_memory_usage) for result in results), 6
            ),
        }


def _source_inventory(cases: list[TtsCase], repo_root: Path) -> list[dict[str, Any]]:
    inventory = []
    for relative in sorted({case.source_path for case in cases}):
        path = repo_root / relative
        record = {
            "path": relative,
            "case_count": sum(case.source_path == relative for case in cases),
        }
        if path.is_file():
            record.update({"bytes": path.stat().st_size, "sha256": sha256_file(path)})
        else:
            record["embedded_in_generation_plan"] = True
        inventory.append(record)
    return inventory


def prepare_corpus(
    *,
    cases: list[TtsCase],
    profile_path: Path,
    output: Path,
    repo_root: Path,
    resume: bool,
) -> dict[str, Any]:
    cases = validate_cases(cases)
    profile = read_json(profile_path)
    validate_profile(profile)
    base_seed = int(profile["generation"]["base_seed"])
    plan = generation_plan(cases, base_seed)
    plan_text = "".join(compact_json(row) + "\n" for row in plan)
    run_identity = {
        "schema_version": 1,
        "profile_path": str(profile_path.resolve().relative_to(repo_root.resolve())),
        "profile_sha256": sha256_file(profile_path),
        "generator_path": str(Path(__file__).resolve().relative_to(repo_root.resolve())),
        "generator_sha256": sha256_file(Path(__file__).resolve()),
        "uv_lock_sha256": sha256_file(repo_root / "tts/uv.lock"),
        "plan_sha256": sha256_bytes(plan_text.encode("utf-8")),
        "source_files": _source_inventory(cases, repo_root),
    }

    output = output.resolve()
    identity_path = output / "run-identity.json"
    plan_path = output / "generation-plan.jsonl"
    if output.exists() and any(output.iterdir()):
        if not resume:
            raise RuntimeError(f"Output directory is not empty: {output}; pass --resume")
        if not identity_path.is_file() or read_json(identity_path) != run_identity:
            raise RuntimeError(f"Resume identity mismatch: {output}")
        if plan_path.read_text(encoding="utf-8") != plan_text:
            raise RuntimeError(f"Resume plan mismatch: {output}")
    else:
        output.mkdir(parents=True, exist_ok=True)
        atomic_write(identity_path, json.dumps(run_identity, indent=2, sort_keys=True) + "\n")
        atomic_write(plan_path, plan_text)

    master_dir = output / "master-audio"
    audio_dir = output / "audio"
    master_dir.mkdir(exist_ok=True)
    audio_dir.mkdir(exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required (install with: brew install ffmpeg)")

    backend: MlxAudioBackend | None = None
    manifest_rows: list[dict[str, Any]] = []
    for index, (case, plan_row) in enumerate(zip(cases, plan), 1):
        master = master_dir / f"{case.case_id}.wav"
        canonical = audio_dir / f"{case.case_id}.wav"
        if not master.is_file():
            if backend is None:
                backend = MlxAudioBackend(profile)
            print(f"Generating {index}/{len(cases)}: {case.case_id}", flush=True)
            backend.generate(case, int(plan_row["seed"]), master)
        else:
            print(f"Reusing master {index}/{len(cases)}: {case.case_id}", flush=True)
        master_info = inspect_wav(master, require_canonical=False)
        if not canonical.is_file():
            canonicalize_wav(master, canonical, ffmpeg)
        canonical_info = inspect_wav(canonical, require_canonical=True)
        manifest_rows.append(
            {
                "case_id": case.case_id,
                "audio_file": f"audio/{canonical.name}",
                "audio_sha256": sha256_file(canonical),
                "reference": case.text,
                "source_case_id": case.case_id,
                "source_corpus": case.source_corpus,
                "source_path": case.source_path,
                "source_text_field": "spoken",
                "source_text_sha256": plan_row["text_sha256"],
                "categories": list(case.categories),
                "voice_profile": profile["profile_id"],
                "generation_seed": plan_row["seed"],
                "master_audio_file": f"master-audio/{master.name}",
                "master_audio_sha256": sha256_file(master),
                "master_sample_rate_hz": master_info["sample_rate_hz"],
                "duration_ms": canonical_info["duration_ms"],
                "peak_pcm16": canonical_info["peak_pcm16"],
                "rms_pcm16": canonical_info["rms_pcm16"],
            }
        )
        progress = "".join(compact_json(row) + "\n" for row in manifest_rows)
        atomic_write(output / "generation-progress.jsonl", progress)

    manifest_text = "".join(compact_json(row) + "\n" for row in manifest_rows)
    manifest_path = output / "manifest.jsonl"
    atomic_write(manifest_path, manifest_text)
    metadata = {
        "schema_version": 1,
        "corpus": "Local Flow synthetic dictation regression audio",
        "case_count": len(cases),
        "source_text_field": "spoken",
        "evaluation_only": True,
        "blind_test": False,
        "synthetic_audio_limitations": (
            "Single-voice clean synthetic speech validates plumbing and lexical regressions; "
            "it does not qualify real speakers, microphones, noise, accents, streaming, or endpointing."
        ),
        "runtime": profile["runtime"],
        "model": profile["model"],
        "voice": profile["voice"],
        "language": profile["language"],
        "instruct": profile.get("instruct"),
        "generation": profile["generation"],
        "output": profile["output"],
        "source_files": run_identity["source_files"],
        "profile_sha256": run_identity["profile_sha256"],
        "generator_sha256": run_identity["generator_sha256"],
        "uv_lock_sha256": run_identity["uv_lock_sha256"],
        "plan_sha256": run_identity["plan_sha256"],
        "manifest_sha256": sha256_file(manifest_path),
        "ffmpeg_version": ffmpeg_version(ffmpeg),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    atomic_write(
        output / "manifest.metadata.json",
        json.dumps(metadata, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )
    return metadata
