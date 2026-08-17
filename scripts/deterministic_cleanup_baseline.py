#!/usr/bin/env python3
"""Conservative, deterministic dictation cleanup benchmark baseline.

This is deliberately not a general-purpose grammar corrector.  It performs a
small set of transformations whose effect can be explained without a language
model, then emits the same JSONL shape consumed by score-cleanup-results.py.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any, Iterable, TextIO


DEFAULT_CASES = Path("docs/evaluation/cleanup_cases.jsonl")
FILLER_RE = re.compile(r"(?i)(?<![\w'-])(?:uh+|um+|erm|er)(?![\w'-])")
WORD_EDGE_RE = re.compile(r"(^[^\w']+|[^\w']+$)", re.UNICODE)
TERMINAL_PUNCTUATION = ".!?"


class InputError(Exception):
    """Raised when the input corpus cannot be used."""


def _normalize_spaces(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    # Do not globally strip spaces before '.' or ':': they can begin a shell
    # path or Gradle task token ("./gradlew :app:assembleDebug").
    text = re.sub(r"\s+([,;!?])", r"\1", text)
    return text


def _remove_fillers(text: str) -> str:
    # Fillers are removed only as standalone tokens.  Lexical uses such as
    # "album", "umbrella", and "her" cannot match this expression.
    text = FILLER_RE.sub(" ", text)
    return _normalize_spaces(text)


def _comparison_token(token: str) -> str:
    return WORD_EDGE_RE.sub("", token).casefold()


def _collapse_adjacent_repeats(text: str, max_phrase_words: int = 4) -> str:
    """Collapse exact adjacent word or short-phrase repeats.

    Matching is case-insensitive and ignores punctuation only at token edges.
    No fuzzy or semantic matching is attempted.
    """

    tokens = text.split()
    if len(tokens) < 2:
        return text

    changed = True
    while changed:
        changed = False
        largest = min(max_phrase_words, len(tokens) // 2)
        for phrase_size in range(largest, 0, -1):
            index = 0
            while index + 2 * phrase_size <= len(tokens):
                first = [
                    _comparison_token(token)
                    for token in tokens[index : index + phrase_size]
                ]
                second = [
                    _comparison_token(token)
                    for token in tokens[
                        index + phrase_size : index + 2 * phrase_size
                    ]
                ]
                if all(first) and first == second:
                    del tokens[index + phrase_size : index + 2 * phrase_size]
                    changed = True
                    continue
                index += 1
            if changed:
                break
    return " ".join(tokens)


def _apply_explicit_correction(text: str) -> str:
    """Apply only correction forms with an unambiguous structural parse."""

    # "Can you send X, actually no, send Y".  Reuse the modal request only
    # when both alternatives start with the same verb.
    match = re.fullmatch(
        r"(?is)(?P<modal>can|could|would|will)\s+you\s+"
        r"(?P<oldverb>[\w'-]+)\s+(?P<oldrest>.+?)\s+actually\s+no[,]?\s+"
        r"(?P<newverb>[\w'-]+)\s+(?P<newrest>.+)",
        text,
    )
    if match and match.group("oldverb").casefold() == match.group("newverb").casefold():
        # If both alternatives refer to the same object with a demonstrative
        # pronoun and only the prepositional target changes, preserve the
        # original object's wording while accepting the new target.
        old_target = re.fullmatch(
            r"(?is)(?P<object>this|that|it)\s+(?P<prep>to|on|at|for)\s+.+",
            match.group("oldrest"),
        )
        new_target = re.fullmatch(
            r"(?is)(?:this|that|it)\s+(?P<prep>to|on|at|for)\s+(?P<target>.+)",
            match.group("newrest"),
        )
        if (
            old_target
            and new_target
            and old_target.group("prep").casefold()
            == new_target.group("prep").casefold()
        ):
            return (
                f"{match.group('modal')} you {match.group('oldverb')} "
                f"{old_target.group('object')} {new_target.group('prep')} "
                f"{new_target.group('target')}"
            )
        return (
            f"{match.group('modal')} you {match.group('newverb')} "
            f"{match.group('newrest')}"
        )

    # Replace a short final prepositional value when the speaker says the
    # explicit phrase "make that".
    match = re.fullmatch(
        r"(?is)(?P<head>.*\b(?:on|at|to|for|by|from)\s+)"
        r"(?P<old>[\w'-]+(?:\s+[\w'-]+){0,2})\s+"
        r"(?:actually\s+)?make\s+that\s+"
        r"(?P<new>[\w'-]+(?:\s+[\w'-]+){0,2})",
        text,
    )
    if match:
        return f"{match.group('head')}{match.group('new')}"

    # "Meet at three, actually four thirty works better" has both a bounded
    # replacement and an explicit preference.  Preserve the preference rather
    # than treating a bare "actually" as a universal correction operator.
    match = re.fullmatch(
        r"(?is)(?P<head>.*\b(?:on|at|to|for|by|from)\s+)"
        r"(?P<old>[\w'-]+(?:\s+[\w'-]+){0,2})\s+actually\s+"
        r"(?P<new>[\w'-]+(?:\s+[\w'-]+){0,2})\s+works\s+better",
        text,
    )
    if match:
        return f"{match.group('head')}{match.group('new')}; that works better"

    return text


def _capitalize_sentence_starts(text: str) -> str:
    chars = list(text)
    at_sentence_start = True
    for index, char in enumerate(chars):
        if at_sentence_start and char.isalpha():
            chars[index] = char.upper()
            at_sentence_start = False
        elif char in TERMINAL_PUNCTUATION:
            at_sentence_start = True
        elif not char.isspace() and at_sentence_start:
            # Quotes and brackets do not consume sentence-start status.
            if char not in "'\"([{":
                at_sentence_start = False
    return "".join(chars)


def _looks_like_question(text: str) -> bool:
    lowered = text.casefold()
    if re.match(r"^(?:who|what|when|where|why|how)\b", lowered):
        return True
    return bool(
        re.match(
            r"^(?:are|is|am|was|were|do|does|did|can|could|would|will|"
            r"should|have|has|had|may|might|must)\s+"
            r"(?:i|you|we|they|he|she|it|this|that|there)\b",
            lowered,
        )
    )


def _punctuate(text: str) -> str:
    # A few bounded discourse/sequence forms are safe enough to improve over
    # merely appending terminal punctuation.
    text = re.sub(r"(?i)^yeah\s+", "Yeah, ", text)
    text = re.sub(r"(?i)\s+(?=let's\s+)", ". ", text, count=1)
    text = re.sub(
        r"(?i)\s+thanks\s+(?=(?:I|we|you|he|she|they|it)\b)",
        ". Thanks, ",
        text,
        count=1,
    )
    text = re.sub(
        r"(?i)^(hey\s+[A-Z][\w'-]+)\s+(?=(?:I|we|you|he|she|they)\b)",
        r"\1, ",
        text,
    )
    text = re.sub(r"(?i)(?<![,;])\s+but\s+", ", but ", text)
    text = re.sub(r"(?i)(?<![,;])\s+(not\s+before)\s*$", r", \1", text)
    text = re.sub(
        r"(?i)(?<![,;])\s+and\s+(the\s+.+?\s+(?:is|was|will|has|had)\b)",
        r", and \1",
        text,
        count=1,
    )

    # A strictly shaped three-step sequence.
    sequence = re.fullmatch(
        r"(?is)first[,]?\s+(?P<one>.+?)\s+then\s+"
        r"(?P<two>.+?)\s+then\s+(?P<three>.+)",
        text,
    )
    if sequence:
        text = (
            f"First, {sequence.group('one')}. Then {sequence.group('two')} "
            f"and {sequence.group('three')}"
        )
    else:
        text = re.sub(r"(?i)(?<![,;])\s+then\s+", ", then ", text, count=1)

    text = _normalize_spaces(text)
    text = _capitalize_sentence_starts(text)
    if text and text[-1] not in TERMINAL_PUNCTUATION:
        text += "?" if _looks_like_question(text) else "."
    return text


def cleanup_text(raw: str) -> str:
    """Return a deterministic, conservative cleanup of *raw*."""

    text = unicodedata.normalize("NFC", raw.replace("\r\n", "\n"))
    text = _normalize_spaces(text)
    if not text:
        return ""
    text = _remove_fillers(text)
    text = _collapse_adjacent_repeats(text)
    text = _apply_explicit_correction(text)
    return _punctuate(text)


def _load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        handle = path.open("r", encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    with handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise InputError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
            case_id = row.get("id") if isinstance(row, dict) else None
            raw = row.get("raw") if isinstance(row, dict) else None
            if not isinstance(case_id, str) or not case_id:
                raise InputError(f"{path}:{line_number}: 'id' must be a non-empty string")
            if case_id in seen:
                raise InputError(f"{path}:{line_number}: duplicate id {case_id!r}")
            if not isinstance(raw, str) or not raw:
                raise InputError(f"{path}:{line_number}: 'raw' must be a non-empty string")
            seen.add(case_id)
            cases.append(row)
    if not cases:
        raise InputError(f"{path}: contains no cases")
    return cases


def _result_rows(cases: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    for case in cases:
        started_ns = time.perf_counter_ns()
        cleaned = cleanup_text(case["raw"])
        elapsed_ms = (time.perf_counter_ns() - started_ns) / 1_000_000
        yield {
            "case_id": case["id"],
            "model_name": "deterministic-cleanup-baseline",
            "prompt_variant": "deterministic-v1",
            "model_text": cleaned,
            "selected_text": cleaned,
            "used_fallback": False,
            "timings": {"cleanup_ms": elapsed_ms},
            "finish_reason": "DETERMINISTIC",
        }


def _write_rows(rows: Iterable[dict[str, Any]], handle: TextIO) -> None:
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, separators=(",", ":")), file=handle)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run conservative deterministic cleanup over a JSONL corpus."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES,
        help=f"input corpus (default: {DEFAULT_CASES})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write scorer-compatible JSONL here (default: stdout)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cases = _load_cases(args.cases)
        if args.output is None:
            _write_rows(_result_rows(cases), sys.stdout)
        else:
            with args.output.open("w", encoding="utf-8", newline="\n") as handle:
                _write_rows(_result_rows(cases), handle)
    except (InputError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
