#!/usr/bin/env python3
"""Prepare a deterministic, multi-speaker LibriSpeech test-clean probe subset."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


SOURCE_MD5 = "32fa31d27d2e1cad72775fee3f4849a9"
HF_DATASET = "openslr/librispeech_asr"
HF_DATASET_REVISION = "71cacbfb7e2354c4226d01e70d77d5fca3d04ba1"
HF_DATASET_API = f"https://huggingface.co/api/datasets/{HF_DATASET}"
HF_ROWS_API = "https://datasets-server.huggingface.co/rows"
SELECTION_ID = "first-2-utterances-from-first-12-speakers-in-hf-test-row-order-v1"
DEFAULT_SPEAKERS = 12
DEFAULT_CLIPS_PER_SPEAKER = 2


def file_hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def with_retries(operation, description: str):
    for attempt in range(1, 7):
        try:
            return operation()
        except (OSError, urllib.error.URLError) as error:
            if attempt == 6:
                raise
            delay = min(2**attempt, 30)
            print(
                f"{description} failed ({error}); retry {attempt}/5 in {delay}s",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(delay)
    raise AssertionError("unreachable")


def fetch_json(url: str) -> dict:
    def fetch() -> dict:
        request = urllib.request.Request(url, headers={"User-Agent": "LocalFlow-STT-eval/1"})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    return with_retries(fetch, "Metadata request")


def download_file(url: str, destination: Path) -> None:
    def download() -> None:
        request = urllib.request.Request(url, headers={"User-Agent": "LocalFlow-STT-eval/1"})
        with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)

    with_retries(download, f"Audio download {destination.name}")


def select_direct_rows(speakers: int, clips_per_speaker: int) -> list[dict]:
    dataset_metadata = fetch_json(HF_DATASET_API)
    actual_revision = dataset_metadata.get("sha")
    if actual_revision != HF_DATASET_REVISION:
        raise RuntimeError(
            f"Dataset revision changed: expected {HF_DATASET_REVISION}, got {actual_revision}"
        )

    selected_speakers: list[str] = []
    selected: dict[str, list[dict]] = defaultdict(list)
    offset = 0
    while True:
        print(f"Reading pinned dataset rows {offset}..{offset + 99}", flush=True)
        query = urllib.parse.urlencode(
            {
                "dataset": HF_DATASET,
                "config": "clean",
                "split": "test",
                "offset": offset,
                "length": 100,
            }
        )
        response = fetch_json(f"{HF_ROWS_API}?{query}")
        rows = response.get("rows", [])
        if not rows:
            break
        for wrapped in rows:
            row = wrapped["row"]
            speaker_id = str(row["speaker_id"])
            if speaker_id not in selected and len(selected_speakers) < speakers:
                selected_speakers.append(speaker_id)
            if speaker_id in selected_speakers and len(selected[speaker_id]) < clips_per_speaker:
                selected[speaker_id].append(row)
        if len(selected_speakers) == speakers and all(
            len(selected[speaker_id]) == clips_per_speaker for speaker_id in selected_speakers
        ):
            break
        offset += len(rows)

    if len(selected_speakers) != speakers:
        raise RuntimeError(f"Requested {speakers} speakers but found {len(selected_speakers)}")
    for speaker_id in selected_speakers:
        if len(selected[speaker_id]) != clips_per_speaker:
            raise RuntimeError(f"Speaker {speaker_id} has too few selected utterances")
    return [row for speaker_id in selected_speakers for row in selected[speaker_id]]


def audio_url(row: dict) -> str:
    audio = row.get("audio")
    if not isinstance(audio, list) or not audio:
        raise RuntimeError(f"Dataset row has no audio asset: {row.get('id')}")
    candidates = [asset for asset in audio if asset.get("type") in {"audio/flac", "audio/wav"}]
    if not candidates:
        raise RuntimeError(f"Dataset row has no supported audio asset: {row.get('id')}")
    url = str(candidates[0]["src"])
    if HF_DATASET_REVISION not in url:
        raise RuntimeError(f"Audio asset is not pinned to {HF_DATASET_REVISION}")
    return url


def convert_downloaded_audio(
    row: dict,
    work_directory: Path,
    audio_directory: Path,
    ffmpeg: str,
) -> tuple[Path, str]:
    case_id = str(row["id"])
    source = work_directory / f"{case_id}.source"
    destination = audio_directory / f"{case_id}.wav"
    download_file(audio_url(row), source)
    source_sha256 = file_hash(source, "sha256")
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
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ],
        check=True,
    )
    source.unlink()
    return destination, source_sha256


def prepare(args: argparse.Namespace) -> None:
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"Output directory is not empty: {output}")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg is required (install with: brew install ffmpeg)")
    ffmpeg_version = subprocess.run(
        [ffmpeg, "-version"], check=True, capture_output=True, text=True
    ).stdout.splitlines()[0]

    audio_directory = output / "audio"
    work_directory = output / ".work"
    audio_directory.mkdir(parents=True, exist_ok=True)
    work_directory.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, str]] = []
    selected_rows = select_direct_rows(args.speakers, args.clips_per_speaker)
    for index, row in enumerate(selected_rows, start=1):
        case_id = str(row["id"])
        reference = str(row["text"])
        print(f"Downloading and converting {index}/{len(selected_rows)}: {case_id}", flush=True)
        wav, source_sha256 = convert_downloaded_audio(
            row, work_directory, audio_directory, ffmpeg
        )
        manifest_rows.append(
            {
                "case_id": case_id,
                "audio_file": f"audio/{wav.name}",
                "audio_sha256": file_hash(wav, "sha256"),
                "source_audio_sha256": source_sha256,
                "reference": reference,
            }
        )
    work_directory.rmdir()

    manifest = output / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8", newline="\n") as handle:
        for row in manifest_rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    manifest_sha256 = file_hash(manifest, "sha256")
    metadata = {
        "schema_version": 1,
        "corpus": "LibriSpeech test-clean deterministic probe subset",
        "license": "CC BY 4.0",
        "source_url": "https://www.openslr.org/12",
        "source_archive": "test-clean.tar.gz",
        "source_archive_md5": SOURCE_MD5,
        "download_mirror": HF_DATASET,
        "download_mirror_revision": HF_DATASET_REVISION,
        "selection_id": SELECTION_ID,
        "speaker_count": args.speakers,
        "clips_per_speaker": args.clips_per_speaker,
        "case_count": len(manifest_rows),
        "case_ids": [row["case_id"] for row in manifest_rows],
        "audio_format": "16 kHz mono signed PCM16 WAV",
        "ffmpeg_version": ffmpeg_version,
        "manifest_sha256": manifest_sha256,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "manifest.metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Prepared {len(manifest_rows)} clips in {output}")
    print(f"Manifest SHA-256: {manifest_sha256}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".cache/stt-eval/librispeech-test-clean-24"),
    )
    parser.add_argument("--speakers", type=int, default=DEFAULT_SPEAKERS)
    parser.add_argument("--clips-per-speaker", type=int, default=DEFAULT_CLIPS_PER_SPEAKER)
    args = parser.parse_args()
    if args.speakers <= 0 or args.clips_per_speaker <= 0:
        parser.error("speaker and clip counts must be positive")
    return args


if __name__ == "__main__":
    try:
        prepare(parse_args())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
