#!/usr/bin/env python3
"""Generate an Android-compatible one-clip TTS corpus from literal text."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from tts.tts_pipeline import TtsCase, prepare_corpus


REPO = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = REPO / "tts/config/qwen3-tts-customvoice-8bit-v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True, help="Literal text to synthesize")
    parser.add_argument("--case-id", default="manual-tts-001")
    parser.add_argument("--category", action="append", default=["manual"])
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    case = TtsCase(
        case_id=args.case_id,
        text=args.text,
        categories=tuple(args.category),
        source_corpus="manual-local-tts",
        source_path="manual-command-line-input",
    )
    # Manual inputs have no source file. Use a minimal local source record so the
    # common manifest path remains self-contained and evaluation-only.
    metadata = prepare_corpus(
        cases=[case],
        profile_path=args.profile,
        output=args.output,
        repo_root=REPO,
        resume=args.resume,
    )
    print(f"Audio: {(args.output / 'audio' / f'{args.case_id}.wav').resolve()}")
    print(f"Manifest SHA-256: {metadata['manifest_sha256']}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
