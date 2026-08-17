#!/usr/bin/env python3
"""Shared deterministic helpers for cleanup data preparation."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Iterator


WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
PROTECTED_PATTERNS = (
    re.compile(r"\b\d+(?:[.,:]\d+)*(?:[-_][\w.]+)*\b", re.UNICODE),
    re.compile(r"(?:[A-Za-z]:)?[/\\](?:[^\s/\\]+[/\\])*[^\s/\\]+"),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b", re.UNICODE),
    re.compile(r"\b(?:v)?\d+(?:\.\d+)+(?:[-+][A-Za-z0-9.-]+)?\b", re.I),
    re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)+\b"),
)
NEGATION = frozenset({"no", "not", "never", "neither", "nor", "without", "don't", "dont", "won't", "wont", "can't", "cant"})
UNCERTAINTY = frozenset({
    "may", "might", "could", "maybe", "perhaps", "possibly", "probably", "likely",
    "unlikely", "think", "guess", "unsure", "uncertain",
})
FILLERS = frozenset({"uh", "um", "uhm", "er", "ah"})
CALENDAR_WORDS = frozenset({
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
})


def nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def words(value: str) -> list[str]:
    return [token.casefold() for token in WORD_RE.findall(nfc(value))]


def normalized_text(value: str) -> str:
    return " ".join(words(value))


def is_sentence_initial(value: str, start: int) -> bool:
    """Return whether a token begins the string or follows sentence punctuation."""

    prefix = value[:start].rstrip()
    return not prefix or prefix[-1] in ".!?\n"


def capitalized_name_anchors(value: str) -> list[str]:
    """Find conservative name-like literals without treating sentence case as a name."""

    anchors: list[str] = []
    for match in re.finditer(r"\b[A-Z][a-z]{2,}\b", value):
        if not is_sentence_initial(value, match.start()) and match.group(0).casefold() not in CALENDAR_WORDS:
            anchors.append(match.group(0))
    return anchors


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_json_values(path: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield row-like dictionaries from JSON, nested SQuAD JSON, or JSONL."""

    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if line.strip():
                    value = json.loads(line)
                    if isinstance(value, dict):
                        yield str(line_number), value
        return
    value = json.loads(path.read_text(encoding="utf-8"))

    def visit(item: Any, key: str) -> Iterator[tuple[str, dict[str, Any]]]:
        if isinstance(item, dict):
            yield key, item
            for name, child in item.items():
                yield from visit(child, f"{key}/{name}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                yield from visit(child, f"{key}/{index}")

    yield from visit(value, "root")


def lexical_additions(raw: str, expected: str) -> Counter[str]:
    return Counter(words(expected)) - Counter(words(raw))


def lexical_addition_surfaces(raw: str, expected: str) -> list[str]:
    """Return exact target token surfaces that exceed the raw lexical multiset."""

    remaining = Counter(words(raw))
    additions: list[str] = []
    for token in WORD_RE.findall(expected):
        folded = token.casefold()
        if remaining[folded] > 0:
            remaining[folded] -= 1
        else:
            additions.append(token)
    return additions


def protected_anchors(value: str) -> list[str]:
    anchors: list[str] = []
    for pattern in PROTECTED_PATTERNS:
        anchors.extend(match.group(0) for match in pattern.finditer(value))
    for token in WORD_RE.findall(value):
        folded = token.casefold()
        if folded in NEGATION or folded in UNCERTAINTY or any(ord(char) > 127 for char in token):
            anchors.append(token)
    anchors.extend(capitalized_name_anchors(value))
    return list(dict.fromkeys(anchors))


def removal_anchors(raw: str, expected: str) -> list[str]:
    """Return conservative removed token runs; punctuation-only differences vanish."""

    raw_tokens = WORD_RE.findall(raw)
    expected_tokens = WORD_RE.findall(expected)
    matcher = SequenceMatcher(
        None,
        [token.casefold() for token in raw_tokens],
        [token.casefold() for token in expected_tokens],
        autojunk=False,
    )
    removed: list[str] = []
    for tag, i1, i2, _, _ in matcher.get_opcodes():
        if tag in {"delete", "replace"} and i1 != i2:
            phrase = " ".join(raw_tokens[i1:i2])
            if phrase and phrase.casefold() not in expected.casefold():
                removed.append(phrase)
    return list(dict.fromkeys(removed))


def ngrams(value: str, size: int, *, characters: bool = False) -> set[str]:
    units = list(normalized_text(value)) if characters else words(value)
    if len(units) < size:
        return {"".join(units) if characters else " ".join(units)} if units else set()
    joiner = "" if characters else " "
    return {joiner.join(units[index:index + size]) for index in range(len(units) - size + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right) if left | right else 0.0


def near_duplicate_scores(left: str, right: str) -> tuple[float, float, float]:
    token = jaccard(ngrams(left, 3), ngrams(right, 3))
    chars = jaccard(ngrams(left, 5, characters=True), ngrams(right, 5, characters=True))
    edit = SequenceMatcher(None, normalized_text(left), normalized_text(right), autojunk=False).ratio()
    return token, chars, edit


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def require_empty_output_dir(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise RuntimeError(f"output path exists and is not a directory: {path}")
        if any(path.iterdir()):
            raise RuntimeError(f"output directory must be new or empty: {path}")
    else:
        path.mkdir(parents=True)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    temporary.replace(path)
    return count
