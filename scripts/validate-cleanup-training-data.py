#!/usr/bin/env python3
"""Validate versioned dictation-cleanup authoring JSONL and emit a manifest.

This tool intentionally uses only the Python standard library.  It validates
records across all input files as one dataset so split leakage cannot hide in
separate train/dev/blind files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = "cleanup-training-record-v2"
MANIFEST_VERSION = "cleanup-training-manifest-v1"
REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "docs/training/cleanup_training_record_v2.schema.json"
DEFAULT_FROZEN = (
    REPO_ROOT / "docs/evaluation/cleanup_cases.jsonl",
    REPO_ROOT / "docs/evaluation/cleanup_cases_heldout_v1.jsonl",
)

SPLITS = frozenset({"train", "dev", "blind", "real_canary"})
SOURCES = frozenset(
    {
        "human_authored",
        "template_human_reviewed",
        "deterministic_generated",
        "llm_proposed_human_approved",
        "consented_real_stt",
        "public_corpus",
    }
)
CATEGORIES = frozenset(
    {
        "no_op",
        "already_clean",
        "punctuation",
        "capitalization",
        "self_correction",
        "false_start",
        "fillers",
        "discourse_marker",
        "repetition",
        "abandoned_start",
        "mixed",
        "grammar_rewrite",
        "asr_correction",
        "lexical_addition",
        "must_not_answer",
        "adversarial_instruction",
        "question",
        "command",
        "formatting_directive",
        "spoken_punctuation",
        "list_formatting",
        "paragraph_formatting",
        "conversational_tone",
        "names",
        "numbers",
        "dates",
        "money",
        "versions",
        "paths",
        "identifiers",
        "facts",
        "technical_text",
        "unicode",
        "multilingual",
        "negation",
        "uncertainty",
        "high_stakes",
        "long_form",
        "multi_sentence",
    }
)
RISK_TAGS = frozenset(
    {
        "negation",
        "number",
        "name",
        "uncertainty",
        "technical_literal",
        "dictated_instruction",
        "formatting_scope",
        "superseded_fact",
        "adversarial_content",
        "unicode_literal",
        "ambiguous_preserve",
        "private_data",
        "lexical_addition",
        "inferred_content",
        "high_stakes",
    }
)
REVIEW_STATUSES = frozenset({"draft", "pending", "approved", "rejected"})
REQUIRED_FIELDS = frozenset(
    {
        "id",
        "raw",
        "expected",
        "categories",
        "must_preserve",
        "must_remove",
        "risk_tags",
        "source",
        "family_id",
        "template_id",
        "split",
        "review",
        "license",
        "generator_version",
    }
)
OPTIONAL_FIELDS = frozenset(
    {
        "source_ref",
        "spoken",
        "allowed_additions",
        "speaker_id",
        "session_id",
        "notes",
    }
)
REVIEW_FIELDS = frozenset(
    {"status", "reviewers", "adjudicated", "reviewed_at", "reviewer_refs"}
)
SOURCE_REF_REQUIRED = SOURCES - {"human_authored"}
WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)


@dataclass(frozen=True)
class Location:
    path: Path
    line: int

    def __str__(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass(frozen=True)
class Record:
    location: Location
    value: dict[str, Any]


class ValidationReport:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def error(self, location: Location | Path | str, message: str) -> None:
        self.errors.append(f"{location}: {message}")

    def print(self, stream: Any | None = None) -> None:
        if stream is None:
            stream = sys.stderr
        for error in self.errors:
            print(f"ERROR: {error}", file=stream)
        if self.errors:
            print(f"Validation failed with {len(self.errors)} error(s).", file=stream)


def is_nfc(value: str) -> bool:
    return value == unicodedata.normalize("NFC", value)


def normalized_overlap_text(value: str) -> str:
    """Normalize enough to catch case/punctuation-obscured frozen text reuse."""

    nfc = unicodedata.normalize("NFC", value).casefold()
    return " ".join(WORD_RE.findall(nfc))


def lexical_tokens(value: str) -> Counter[str]:
    return Counter(token.casefold() for token in WORD_RE.findall(value))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_jsonl(path: Path, report: ValidationReport) -> list[Record]:
    records: list[Record] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                location = Location(path, line_number)
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    report.error(location, f"invalid JSON: {exc.msg}")
                    continue
                if not isinstance(value, dict):
                    report.error(location, "record must be a JSON object")
                    continue
                records.append(Record(location, value))
    except (OSError, UnicodeError) as exc:
        report.error(path, f"cannot read UTF-8 JSONL: {exc}")
        return records
    if not records:
        report.error(path, "contains no JSON records")
    return records


def require_string(
    row: dict[str, Any], field: str, record: Record, report: ValidationReport
) -> str | None:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        report.error(record.location, f"{field!r} must be a non-empty string")
        return None
    return value


def require_string_list(
    row: dict[str, Any],
    field: str,
    record: Record,
    report: ValidationReport,
    *,
    allow_empty: bool,
    unique_items: bool = True,
) -> list[str] | None:
    value = row.get(field)
    if not isinstance(value, list):
        report.error(record.location, f"{field!r} must be a list of strings")
        return None
    if not allow_empty and not value:
        report.error(record.location, f"{field!r} must not be empty")
    bad = [
        item for item in value if not isinstance(item, str) or not item.strip()
    ]
    if bad:
        report.error(record.location, f"{field!r} contains an empty or non-string item")
        return None
    if unique_items and len(value) != len(set(value)):
        report.error(record.location, f"{field!r} contains a duplicate item")
    return value


def validate_nfc(value: Any, record: Record, report: ValidationReport, field: str = "") -> None:
    if isinstance(value, str):
        if not is_nfc(value):
            report.error(record.location, f"{field or 'string value'} must use Unicode NFC")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_nfc(item, record, report, f"{field}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            validate_nfc(key, record, report, f"{field} key")
            validate_nfc(item, record, report, f"{field}.{key}" if field else key)


def validate_enum_list(
    values: list[str] | None,
    allowed: frozenset[str],
    field: str,
    record: Record,
    report: ValidationReport,
) -> None:
    if values is None:
        return
    invalid = sorted(set(values) - allowed)
    if invalid:
        report.error(record.location, f"{field!r} has unknown value(s): {', '.join(invalid)}")


def validate_review(record: Record, report: ValidationReport, require_approved: bool) -> None:
    row = record.value
    review = row.get("review")
    if not isinstance(review, dict):
        report.error(record.location, "'review' must be an object")
        return
    unknown = sorted(set(review) - REVIEW_FIELDS)
    if unknown:
        report.error(record.location, f"'review' has unknown field(s): {', '.join(unknown)}")
    status = review.get("status")
    reviewers = review.get("reviewers")
    if status not in REVIEW_STATUSES:
        report.error(record.location, f"review.status must be one of {sorted(REVIEW_STATUSES)}")
    if isinstance(reviewers, bool) or not isinstance(reviewers, int) or reviewers < 0:
        report.error(record.location, "review.reviewers must be a non-negative integer")
        reviewers = None
    if require_approved and status != "approved":
        report.error(record.location, "review.status must be 'approved' in release mode")
    if status in {"approved", "rejected"} and reviewers == 0:
        report.error(record.location, f"review.reviewers must be positive for status {status!r}")
    if status == "draft" and isinstance(reviewers, int) and reviewers != 0:
        report.error(record.location, "draft records must have review.reviewers equal to 0")
    if row.get("split") == "blind" and status == "approved":
        if isinstance(reviewers, int) and reviewers < 2:
            report.error(record.location, "approved blind records require at least 2 reviewers")
        if review.get("adjudicated") is not True:
            report.error(record.location, "approved blind records require review.adjudicated=true")
    if "adjudicated" in review and not isinstance(review.get("adjudicated"), bool):
        report.error(record.location, "review.adjudicated must be a boolean")
    if "reviewed_at" in review and (
        not isinstance(review.get("reviewed_at"), str)
        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", review["reviewed_at"])
    ):
        report.error(record.location, "review.reviewed_at must be an ISO YYYY-MM-DD string")
    if "reviewer_refs" in review:
        refs = review["reviewer_refs"]
        if not isinstance(refs, list) or any(
            not isinstance(item, str) or not item.strip() for item in refs
        ):
            report.error(record.location, "review.reviewer_refs must be a list of non-empty strings")
        else:
            if len(set(refs)) != len(refs):
                report.error(record.location, "review.reviewer_refs contains a duplicate item")
            if isinstance(reviewers, int) and len(set(refs)) != reviewers:
                report.error(record.location, "unique review.reviewer_refs must match review.reviewers")


def validate_record(record: Record, report: ValidationReport, require_approved: bool) -> None:
    row = record.value
    missing = sorted(REQUIRED_FIELDS - set(row))
    unknown = sorted(set(row) - REQUIRED_FIELDS - OPTIONAL_FIELDS)
    if missing:
        report.error(record.location, f"missing required field(s): {', '.join(missing)}")
    if unknown:
        report.error(record.location, f"unknown field(s): {', '.join(unknown)}")
    validate_nfc(row, record, report)

    for field in (
        "id",
        "raw",
        "expected",
        "source",
        "family_id",
        "template_id",
        "split",
        "license",
        "generator_version",
    ):
        require_string(row, field, record, report)
    for field in ("source_ref", "spoken", "speaker_id", "session_id", "notes"):
        if field in row:
            require_string(row, field, record, report)

    categories = require_string_list(row, "categories", record, report, allow_empty=False)
    preserve = require_string_list(row, "must_preserve", record, report, allow_empty=True)
    remove = require_string_list(row, "must_remove", record, report, allow_empty=True)
    risks = require_string_list(row, "risk_tags", record, report, allow_empty=True)
    additions = None
    if "allowed_additions" in row:
        additions = require_string_list(
            row, "allowed_additions", record, report, allow_empty=False, unique_items=False
        )
    validate_enum_list(categories, CATEGORIES, "categories", record, report)
    validate_enum_list(risks, RISK_TAGS, "risk_tags", record, report)

    split = row.get("split")
    source = row.get("source")
    if split not in SPLITS:
        report.error(record.location, f"'split' must be one of {sorted(SPLITS)}")
    if source not in SOURCES:
        report.error(record.location, f"'source' must be one of {sorted(SOURCES)}")
    if source in SOURCE_REF_REQUIRED and not row.get("source_ref"):
        report.error(record.location, f"source {source!r} requires a non-empty 'source_ref'")
    if source == "consented_real_stt":
        for field in ("source_ref", "speaker_id", "session_id"):
            if not row.get(field):
                report.error(record.location, f"consented real STT records require {field!r}")
        if split != "real_canary":
            report.error(record.location, "consented real STT records must use split 'real_canary'")
    elif split == "real_canary":
        report.error(record.location, "split 'real_canary' requires source 'consented_real_stt'")

    raw = row.get("raw")
    expected = row.get("expected")
    if isinstance(raw, str) and isinstance(expected, str):
        if preserve is not None:
            for anchor in preserve:
                if anchor not in expected:
                    report.error(record.location, f"must_preserve anchor absent from expected: {anchor!r}")
        if remove is not None:
            for anchor in remove:
                if anchor not in raw:
                    report.error(record.location, f"must_remove anchor absent from raw: {anchor!r}")
                if anchor in expected:
                    report.error(record.location, f"must_remove anchor survives in expected: {anchor!r}")
        if additions is not None:
            for addition in additions:
                if addition not in expected:
                    report.error(record.location, f"allowed_additions item absent from expected: {addition!r}")

        introduced = lexical_tokens(expected) - lexical_tokens(raw)
        allowed = lexical_tokens(" ".join(additions or []))
        undeclared = introduced - allowed
        if undeclared:
            rendered = ", ".join(
                f"{token} ({count})" for token, count in sorted(undeclared.items())
            )
            report.error(record.location, f"expected introduces undeclared lexical token(s): {rendered}")

    validate_review(record, report, require_approved)


def frozen_fingerprints(paths: Iterable[Path], report: ValidationReport) -> dict[str, list[str]]:
    fingerprints: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        for record in load_jsonl(path, report):
            frozen_id = record.value.get("id", f"line-{record.location.line}")
            for field in ("raw", "expected"):
                value = record.value.get(field)
                if isinstance(value, str) and value.strip():
                    fingerprints[normalized_overlap_text(value)].append(
                        f"{path}:{frozen_id}:{field}"
                    )
    return fingerprints


def validate_dataset(
    records: Sequence[Record],
    frozen: dict[str, list[str]],
    report: ValidationReport,
    require_approved: bool,
) -> None:
    ids: dict[str, Location] = {}
    pair_fingerprints: dict[tuple[str, str], Location] = {}
    family_splits: dict[str, dict[str, Location]] = defaultdict(dict)
    template_splits: dict[str, dict[str, Location]] = defaultdict(dict)

    for record in records:
        validate_record(record, report, require_approved)
        row = record.value
        record_id = row.get("id")
        if isinstance(record_id, str):
            if record_id in ids:
                report.error(record.location, f"duplicate id {record_id!r}; first seen at {ids[record_id]}")
            else:
                ids[record_id] = record.location

        raw, expected = row.get("raw"), row.get("expected")
        if isinstance(raw, str) and isinstance(expected, str):
            pair = (normalized_overlap_text(raw), normalized_overlap_text(expected))
            if pair in pair_fingerprints:
                report.error(
                    record.location,
                    f"duplicate normalized raw/expected pair; first seen at {pair_fingerprints[pair]}",
                )
            else:
                pair_fingerprints[pair] = record.location
            for field, value in (("raw", raw), ("expected", expected)):
                fingerprint = normalized_overlap_text(value)
                if fingerprint and fingerprint in frozen:
                    sources = ", ".join(frozen[fingerprint][:3])
                    report.error(
                        record.location,
                        f"{field} overlaps frozen evaluation text after case/punctuation normalization: {sources}",
                    )

        split = row.get("split")
        family_id = row.get("family_id")
        template_id = row.get("template_id")
        if split in SPLITS:
            if isinstance(family_id, str) and family_id:
                family_splits[family_id].setdefault(split, record.location)
            if isinstance(template_id, str) and template_id:
                template_splits[template_id].setdefault(split, record.location)

    for label, groups in (("family_id", family_splits), ("template_id", template_splits)):
        for value, by_split in sorted(groups.items()):
            if len(by_split) > 1:
                places = ", ".join(f"{split} at {location}" for split, location in sorted(by_split.items()))
                report.error("dataset", f"{label} {value!r} crosses splits: {places}")


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def make_manifest(
    dataset_paths: Sequence[Path],
    frozen_paths: Sequence[Path],
    artifact_paths: Sequence[Path],
    records: Sequence[Record],
) -> dict[str, Any]:
    split_counts = Counter(
        record.value.get("split") for record in records if record.value.get("split") in SPLITS
    )

    def entry(path: Path) -> dict[str, Any]:
        return {
            "path": display_path(path),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }

    dataset_entries = []
    for path in dataset_paths:
        item = entry(path)
        item["records"] = sum(1 for record in records if record.location.path == path)
        dataset_entries.append(item)
    return {
        "manifest_version": MANIFEST_VERSION,
        "record_schema_version": SCHEMA_VERSION,
        "schema": entry(SCHEMA_PATH),
        "validator": entry(Path(__file__).resolve()),
        "datasets": dataset_entries,
        "frozen_evaluation": [entry(path) for path in frozen_paths],
        "artifacts": [entry(path) for path in artifact_paths],
        "total_records": len(records),
        "split_counts": dict(sorted(split_counts.items())),
    }


def check_manifest(path: Path, actual: dict[str, Any], report: ValidationReport) -> None:
    try:
        expected = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        report.error(path, f"cannot read manifest: {exc}")
        return
    if expected != actual:
        report.error(path, "manifest content or SHA-256 hashes do not match current inputs")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", nargs="+", type=Path, help="authoring JSONL file(s)")
    parser.add_argument(
        "--frozen-case",
        action="append",
        type=Path,
        default=None,
        help="frozen evaluation JSONL (repeatable; replaces project defaults)",
    )
    parser.add_argument(
        "--no-frozen-check",
        action="store_true",
        help="disable frozen-corpus overlap checks (for validator development only)",
    )
    parser.add_argument(
        "--require-approved",
        action="store_true",
        help="reject draft, pending, and rejected rows for a release dataset",
    )
    parser.add_argument(
        "--hash-artifact",
        action="append",
        type=Path,
        default=[],
        help="generator code/config artifact to hash in the manifest (repeatable)",
    )
    manifest = parser.add_mutually_exclusive_group()
    manifest.add_argument("--write-manifest", type=Path)
    manifest.add_argument("--check-manifest", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = ValidationReport()
    dataset_paths = [path.resolve() for path in args.jsonl]
    frozen_paths = [] if args.no_frozen_check else [
        path.resolve() for path in (args.frozen_case or DEFAULT_FROZEN)
    ]
    artifact_paths = [path.resolve() for path in args.hash_artifact]

    records: list[Record] = []
    for path in dataset_paths:
        records.extend(load_jsonl(path, report))
    frozen = frozen_fingerprints(frozen_paths, report) if frozen_paths else {}
    validate_dataset(records, frozen, report, args.require_approved)

    required_files = [SCHEMA_PATH, *dataset_paths, *frozen_paths, *artifact_paths]
    for path in required_files:
        if not path.is_file():
            report.error(path, "manifest input is not a regular file")

    manifest_value: dict[str, Any] | None = None
    if not report.errors:
        manifest_value = make_manifest(dataset_paths, frozen_paths, artifact_paths, records)
        if args.check_manifest:
            check_manifest(args.check_manifest, manifest_value, report)

    if report.errors:
        report.print()
        return 1
    if args.write_manifest and manifest_value is not None:
        args.write_manifest.parent.mkdir(parents=True, exist_ok=True)
        args.write_manifest.write_text(
            json.dumps(manifest_value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(
        f"Validated {len(records)} record(s) across {len(dataset_paths)} file(s); "
        f"schema={SCHEMA_VERSION}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
