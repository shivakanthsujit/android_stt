#!/usr/bin/env python3
"""Generate Qwen TTS audio for cleanup regressions and dictation stress cases."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from tts.tts_pipeline import (
    prepare_corpus,
    project_additional_cases,
    project_cleanup_cases,
)


REPO = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = REPO / "tts/config/qwen3-tts-customvoice-8bit-v1.json"
DEFAULT_OUTPUT = REPO / ".cache/stt-eval/cleanup-heldout-v1-plus-dictation-tts-v1-qwen3-ryan"


def selected_cases(suite: str):
    seed = REPO / "docs/evaluation/cleanup_cases.jsonl"
    heldout = REPO / "docs/evaluation/cleanup_cases_heldout_v1.jsonl"
    additional = REPO / "docs/evaluation/stt_dictation_tts_cases_v1.jsonl"
    cases = []
    if suite in {"seed", "all-regressions"}:
        cases.extend(project_cleanup_cases(seed, "cleanup-seed-regression-v1", REPO))
    if suite in {"heldout-v1", "heldout-v1-plus-additional", "all-regressions"}:
        cases.extend(project_cleanup_cases(heldout, "cleanup-heldout-v1-retired-regression", REPO))
    if suite in {"heldout-v1-plus-additional", "all-regressions"}:
        cases.extend(project_additional_cases(additional, REPO))
    return cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite",
        choices=("heldout-v1-plus-additional", "heldout-v1", "seed", "all-regressions"),
        default="heldout-v1-plus-additional",
    )
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metadata = prepare_corpus(
        cases=selected_cases(args.suite),
        profile_path=args.profile,
        output=args.output,
        repo_root=REPO,
        resume=args.resume,
    )
    print(f"Prepared {metadata['case_count']} clips in {args.output.resolve()}")
    print(f"Manifest SHA-256: {metadata['manifest_sha256']}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
