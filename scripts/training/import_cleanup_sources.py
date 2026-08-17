#!/usr/bin/env python3
"""Convert pinned public sources into conservative, pending-review v1 records."""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Iterator

from cleanup_data_common import (
    atomic_json,
    capitalized_name_anchors,
    FILLERS,
    NEGATION,
    UNCERTAINTY,
    iter_json_values,
    lexical_addition_surfaces,
    lexical_additions,
    nfc,
    protected_anchors,
    removal_anchors,
    require_empty_output_dir,
    sha256_file,
    stable_hash,
    words,
    write_jsonl,
)


HIGH_STAKES = re.compile(r"\b(patient|diagnos|dose|medication|legal|lawsuit|plaintiff|tax|liability|investment|financial)\b", re.I)
ADVERSARIAL = re.compile(r"\b(ignore previous|system:|assistant:|developer:|output only|return json|password|shell command)\b", re.I)
TECHNICAL = re.compile(r"\b(api|database|server|schema|model|python|kotlin|android|build|deploy|version|release|http|json|sql|gpu|cuda)\b", re.I)
CORRECTION = re.compile(r"\b(no(?: sorry)?|wait|actually(?: make that)?|i mean|rather|oops|hold (?:on|up))\b", re.I)
GRAMMAR_CUE = re.compile(
    r"\b(?:gonna|wanna|gotta|ain't|aint|should of|could of|would of|"
    r"me and (?:him|her|them|[a-z]+)|(?:him|her|them) and me)\b",
    re.I,
)
ASR_CUE = re.compile(
    r"\b(?:post gress|post sequel|cube er nett(?:y|ies)|dock er|red is|jason|java script|"
    r"web socket|oh auth|pie torch|my sequel|react jay ess|node jay ess|type script|"
    r"tensor flow|git hub|get hub|pie thon)\b",
    re.I,
)
LIST_MARKER = re.compile(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+")
SPOKEN_LIST_MARKER = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|first|second|third|fourth|"
    r"fifth|sixth|seventh|eighth|ninth|tenth)\b",
    re.I,
)
SPOKEN_PUNCTUATION = {
    "period": ".", "comma": ",", "colon": ":", "semicolon": ";",
    "question mark": "?", "exclamation mark": "!", "new line": "\n",
}
DISCOURSE_PHRASES = re.compile(r"\b(?:basically|you know|i mean|kind of|sort of|honestly)\b", re.I)
CONTENT_COMMAND = re.compile(
    r"^\s*(?:please\s+)?(?:send|deploy|call|remind|add|create|delete|remove|run|check|use|"
    r"schedule|email|text|message|open|close|move|copy|save|publish|install|restart|stop|start)\b",
    re.I,
)
NYRA_ANNOTATION = re.compile(r"\[[^\]]+\]|\b[^\s*]+\*")
NYRA_FILLER_TAG = re.compile(r"\[(UH|UM)\]", re.I)
VERSION = re.compile(r"\bv?\d+(?:\.\d+){1,}(?:[-+][A-Za-z0-9.-]+)?\b", re.I)
PATH_OR_URL = re.compile(r"(?:https?://\S+|(?:[A-Za-z]:)?[/\\](?:[^\s/\\]+[/\\])*[^\s/\\]+)", re.I)
IDENTIFIER = re.compile(r"(?:\b[A-Z]{2,}[A-Z0-9_-]*\b|\b[a-z]+(?:[A-Z][A-Za-z0-9]*)+\b|\b[a-z][a-z0-9]*_[a-z0-9_]+\b)")
MONEY = re.compile(r"(?:[$€£¥]\s?\d|\b\d+(?:[.,]\d+)?\s?(?:dollars?|euros?|pounds?|yen)\b)", re.I)
DATE_NUMERIC = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
DATE_WORD = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|January|February|March|April|June|July|August|September|October|November|December)\b", re.I)
DATE_MAY_CONTEXT = re.compile(r"(?:\b(?:on|in|by|until|before|after)\s+May\b|\bMay\s+\d{1,2}\b)")
QUARANTINE_SOTTO = frozenset({
    "crutch_words", "dictation_commands", "list_formatting", "paragraph_formatting", "mixed",
    "grammar", "misheard_words",
})
FORMAT_SOTTO = frozenset({"dictation_commands", "list_formatting", "paragraph_formatting"})
NUMBER_WORDS = {
    "0": {"zero"}, "1": {"one", "first"}, "2": {"two", "second"},
    "3": {"three", "third"}, "4": {"four", "fourth"}, "5": {"five", "fifth"},
    "6": {"six", "sixth"}, "7": {"seven", "seventh"}, "8": {"eight", "eighth"},
    "9": {"nine", "ninth"}, "10": {"ten", "tenth"},
}


def parquet_rows(path: Path, columns: list[str]) -> Iterator[tuple[str, dict[str, Any]]]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:
        raise RuntimeError("Parquet input requires the locked training environment with pyarrow") from exc
    file = parquet.ParquetFile(path)
    missing = sorted(set(columns) - set(file.schema_arrow.names))
    if missing:
        raise RuntimeError(f"{path}: missing required parquet columns: {', '.join(missing)}")
    for batch_index, batch in enumerate(file.iter_batches(batch_size=2048, columns=columns)):
        for row_index, row in enumerate(batch.to_pylist()):
            if isinstance(row, dict):
                yield f"batch-{batch_index}-row-{row_index}", row


def data_rows(path: Path, source_id: str) -> Iterator[tuple[str, dict[str, Any]]]:
    if path.suffix.lower() == ".parquet":
        columns = {
            "sotto": ["input", "output"],
            "nyra": ["id", "speaker", "verbatim_transcript", "intended_transcript"],
        }.get(source_id)
        if columns is None:
            raise RuntimeError(f"no parquet column contract for source {source_id}")
        yield from parquet_rows(path, columns)
    elif path.suffix.lower() in {".json", ".jsonl"}:
        yield from iter_json_values(path)


def path_matches(path: str, patterns: list[str]) -> bool:
    return any(Path(path).match(pattern) or fnmatch.fnmatch(path, pattern) for pattern in patterns)


def category_value(row: dict[str, Any]) -> str:
    for field in ("category", "type", "transformation", "label"):
        value = row.get(field)
        if isinstance(value, str):
            return value.strip().casefold().replace("-", "_").replace(" ", "_")
    return ""


def inferred_sotto_category(raw: str, expected: str) -> str:
    """Infer a high-precision operation label because pinned Sotto omits row labels."""

    raw_folded = raw.casefold()
    if LIST_MARKER.search(expected) and SPOKEN_LIST_MARKER.search(raw):
        return "list_formatting"
    if "\n\n" in expected and "new paragraph" in raw_folded:
        return "paragraph_formatting"
    for spoken, rendered in SPOKEN_PUNCTUATION.items():
        if spoken in raw_folded and spoken not in expected.casefold() and rendered in expected:
            return "dictation_commands"
    if GRAMMAR_CUE.search(raw):
        return "grammar"
    if ASR_CUE.search(raw):
        return "misheard_words"
    return ""


def classify(raw: str, expected: str, source_id: str, upstream_category: str) -> tuple[list[str], list[str]]:
    categories: list[str] = []
    risks: list[str] = []
    raw_words, expected_words = words(raw), words(expected)
    raw_set, expected_set = set(raw_words), set(expected_words)
    if raw == expected:
        categories.extend(["no_op", "already_clean"])
    if raw_words == expected_words and raw != expected:
        categories.extend(["already_clean", "punctuation", "capitalization"])
    mapping = {
        "self_correction": "self_correction", "false_start": "false_start",
        "filler_removal": "fillers", "fillers": "fillers", "repetition": "repetition",
        "preserve_wording": "already_clean", "adversarial": "adversarial_instruction",
        "crutch_words": "discourse_marker", "mixed": "mixed",
        "grammar": "grammar_rewrite", "misheard_words": "asr_correction",
    }
    if upstream_category in mapping:
        categories.append(mapping[upstream_category])
    formatting_categories = {
        "dictation_commands": "spoken_punctuation",
        "list_formatting": "list_formatting",
        "paragraph_formatting": "paragraph_formatting",
    }
    if upstream_category in formatting_categories:
        categories.extend(["formatting_directive", formatting_categories[upstream_category]])
        risks.append("formatting_scope")
    if upstream_category == "adversarial":
        categories.append("must_not_answer")
        risks.extend(["adversarial_content", "dictated_instruction"])
    if source_id == "disfl_qa":
        categories.extend(["self_correction", "question"])
        risks.append("superseded_fact")
    elif CORRECTION.search(raw):
        categories.append("self_correction")
        risks.append("superseded_fact")
    if any(token in FILLERS for token in raw_set - expected_set):
        categories.append("fillers")
    if any(match.group(0).casefold() not in expected.casefold() for match in DISCOURSE_PHRASES.finditer(raw)):
        categories.append("discourse_marker")
    if any(left == right for left, right in zip(raw_words, raw_words[1:])) and raw_words != expected_words:
        categories.append("repetition")
    if raw.endswith("?") or expected.endswith("?"):
        categories.extend(["question", "must_not_answer"])
        risks.append("dictated_instruction")
    if CONTENT_COMMAND.search(raw) and upstream_category not in FORMAT_SOTTO:
        categories.extend(["command", "must_not_answer"])
        risks.append("dictated_instruction")
    if ADVERSARIAL.search(raw):
        categories.extend(["adversarial_instruction", "must_not_answer"])
        risks.extend(["adversarial_content", "dictated_instruction"])
    if TECHNICAL.search(raw):
        categories.append("technical_text")
        risks.append("technical_literal")
    if HIGH_STAKES.search(raw) or HIGH_STAKES.search(expected):
        categories.append("high_stakes")
        risks.append("high_stakes")
    if upstream_category in {"grammar", "misheard_words"}:
        risks.append("inferred_content")
    if raw_set & NEGATION:
        categories.append("negation")
        risks.append("negation")
    if raw_set & UNCERTAINTY:
        categories.append("uncertainty")
        risks.append("uncertainty")
    combined = raw + "\n" + expected
    anchors = protected_anchors(expected)
    if any(any(char.isdigit() for char in anchor) for anchor in anchors):
        categories.append("numbers")
        risks.append("number")
    if VERSION.search(combined):
        categories.append("versions")
        risks.extend(["number", "technical_literal"])
    if PATH_OR_URL.search(combined):
        categories.append("paths")
        risks.append("technical_literal")
    if IDENTIFIER.search(combined):
        categories.append("identifiers")
        risks.append("technical_literal")
    if MONEY.search(combined):
        categories.append("money")
        risks.append("number")
    if DATE_NUMERIC.search(combined) or DATE_WORD.search(combined) or DATE_MAY_CONTEXT.search(combined):
        categories.append("dates")
        risks.append("number")
    expected_names = capitalized_name_anchors(expected)
    if expected_names:
        categories.append("names")
        risks.append("name")
    if any(any(ord(char) > 127 for char in anchor) for anchor in anchors):
        categories.append("unicode")
        risks.append("unicode_literal")
    if len(raw_words) >= 25:
        categories.append("long_form")
    if len(categories) == 0:
        categories.append("mixed" if raw_words != expected_words else "already_clean")
    if len(set(categories) & {"self_correction", "fillers", "discourse_marker", "repetition", "false_start", "grammar_rewrite", "asr_correction"}) > 1:
        categories.append("mixed")
    return list(dict.fromkeys(categories)), list(dict.fromkeys(risks))


def pair_for(source_id: str, row: dict[str, Any]) -> tuple[str, str, str] | None:
    if source_id == "sotto":
        candidates = (("input", "output"), ("raw", "clean"), ("transcript", "cleaned_transcript"))
    elif source_id == "disfl_qa":
        candidates = (
            ("disfluent", "original"),
            ("disfluent question", "original question"),
            ("disfluent_question", "original_question"),
        )
    elif source_id == "nyra":
        candidates = (("verbatim_transcript", "intended_transcript"),)
    else:
        return None
    for raw_key, expected_key in candidates:
        raw, expected = row.get(raw_key), row.get(expected_key)
        if isinstance(raw, str) and isinstance(expected, str) and raw.strip() and expected.strip():
            if source_id == "nyra":
                raw = NYRA_FILLER_TAG.sub(lambda match: match.group(1).casefold(), raw)
            upstream_id = row.get("id") or row.get("squad_v2_id") or row.get("squad_id") or ""
            return nfc(raw), nfc(expected), str(upstream_id)
    return None


def declared_lexical_additions(raw: str, expected: str, category: str) -> list[str]:
    additions = lexical_addition_surfaces(raw, expected)
    if not additions:
        return []
    if category != "list_formatting":
        return additions
    raw_tokens = set(words(raw))
    allowed: list[str] = []
    for token in additions:
        folded = token.casefold()
        if folded not in NUMBER_WORDS or not raw_tokens & NUMBER_WORDS[folded]:
            return []
        allowed.append(token)
    return allowed


def decision(
    source_id: str, raw: str, expected: str, category: str, risks: list[str],
    allowed_additions: list[str],
) -> tuple[str, str]:
    if source_id == "nyra" and NYRA_ANNOTATION.search(raw):
        return "rejected", "out_of_domain_transcription_annotation"
    additions = lexical_additions(raw, expected)
    undeclared = additions - Counter(words(" ".join(allowed_additions)))
    if undeclared:
        return "rejected", "target_introduces_lexical_content"
    if additions:
        return "quarantine", "lexical_addition_requires_review"
    if source_id == "sotto" and category in QUARANTINE_SOTTO:
        return "quarantine", f"review_required_category:{category}"
    if HIGH_STAKES.search(raw) or HIGH_STAKES.search(expected):
        return "quarantine", "high_stakes_domain"
    expected_folded = expected.casefold()
    for anchor in protected_anchors(raw):
        if anchor.casefold() not in expected_folded:
            return "quarantine", "protected_anchor_changed"
    if any(tag in risks for tag in (
        "negation", "uncertainty", "adversarial_content", "formatting_scope", "inferred_content",
        "lexical_addition", "high_stakes",
    )):
        return "quarantine", "high_risk_requires_explicit_review"
    return "candidate", "pending_human_review"


def make_record(source: dict[str, Any], relative: str, locator: str, row: dict[str, Any]) -> tuple[str, dict[str, Any], str] | None:
    source_id = source["id"]
    pair = pair_for(source_id, row)
    if pair is None:
        return None
    raw, expected, upstream_id = pair
    category = category_value(row)
    classification_basis = "upstream"
    if source_id == "sotto" and not category:
        category = inferred_sotto_category(raw, expected)
        classification_basis = "deterministic_inference" if category else "text_evidence"
    categories, risks = classify(raw, expected, source_id, category)
    allowed_additions = declared_lexical_additions(raw, expected, category)
    if allowed_additions:
        categories.append("lexical_addition")
        risks.append("lexical_addition")
    outcome, reason = decision(source_id, raw, expected, category, risks, allowed_additions)
    reference = f"{source_id}:{relative}:{upstream_id or locator}"
    upstream_speaker = row.get("speaker") or row.get("speaker_id")
    speaker_key = stable_hash(f"{source_id}\0{upstream_speaker}", 20) if upstream_speaker is not None else None
    semantic_basis = f"speaker:{speaker_key}" if speaker_key else nfc(expected).casefold()
    semantic = stable_hash(f"{source_id}\0{semantic_basis}")
    template_shape = " ".join("#" if token.isdigit() else token for token in words(expected))
    template = stable_hash(f"{source_id}\0{category}\0{template_shape}")
    record: dict[str, Any] = {
        "id": f"candidate-{source_id}-{stable_hash(reference, 20)}",
        "raw": raw,
        "expected": expected,
        "categories": categories,
        "must_preserve": protected_anchors(expected),
        "must_remove": removal_anchors(raw, expected),
        "risk_tags": risks,
        "source": "public_corpus",
        "source_ref": reference,
        "family_id": f"{source_id}-family-{semantic}",
        "template_id": f"{source_id}-template-{template}",
        "split": "train",
        "review": {"status": "pending", "reviewers": 0},
        "license": source["license"],
        "generator_version": "cleanup-public-import-v2",
        "notes": (
            f"import_decision={outcome}; reason={reason}; operation_category={category or 'unknown'}; "
            f"classification_basis={classification_basis}"
        ),
    }
    if speaker_key:
        record["speaker_id"] = f"{source_id}-speaker-{speaker_key}"
    if allowed_additions:
        record["allowed_additions"] = allowed_additions
    return outcome, record, reason


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--source-config", type=Path, default=Path("training/config/sources-v1.json"))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    require_empty_output_dir(args.output_root)
    manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    config = json.loads(args.source_config.read_text(encoding="utf-8"))
    if manifest.get("config_sha256") != sha256_file(args.source_config):
        raise RuntimeError("source manifest configuration hash differs from source configuration")
    configured = {source["id"]: source for source in config["sources"]}
    if {source["id"] for source in manifest["sources"]} != set(configured):
        raise RuntimeError("source manifest IDs differ from source configuration")
    outputs: dict[str, list[dict[str, Any]]] = {"candidate": [], "quarantine": [], "rejected": []}
    reasons: Counter[str] = Counter()
    source_rows: Counter[str] = Counter()
    mapped_rows: Counter[str] = Counter()
    candidate_files: Counter[str] = Counter()
    holdout_files: Counter[str] = Counter()
    for source in manifest["sources"]:
        rule = configured[source["id"]]
        for item in source["files"]:
            relative = item["path"]
            path = args.source_root / source["id"] / relative
            if path.suffix.lower() not in {".parquet", ".json", ".jsonl"}:
                continue
            if path_matches(relative, rule["holdout_include"]):
                holdout_files[source["id"]] += 1
                continue
            if not path_matches(relative, rule["candidate_include"]):
                continue
            candidate_files[source["id"]] += 1
            for locator, row in data_rows(path, source["id"]):
                source_rows[source["id"]] += 1
                converted = make_record(source, relative, locator, row)
                if converted is None:
                    continue
                outcome, record, reason = converted
                outputs[outcome].append(record)
                mapped_rows[source["id"]] += 1
                reasons[f"{outcome}:{reason}"] += 1
    if not all(candidate_files[source["id"]] for source in manifest["sources"]):
        missing = [source["id"] for source in manifest["sources"] if not candidate_files[source["id"]]]
        raise RuntimeError(f"candidate include rules matched no data files for: {', '.join(missing)}")
    if not all(mapped_rows[source["id"]] for source in manifest["sources"]):
        missing = [source["id"] for source in manifest["sources"] if not mapped_rows[source["id"]]]
        raise RuntimeError(f"source schema mismatch; no pairs mapped for: {', '.join(missing)}")
    for name, rows in outputs.items():
        rows.sort(key=lambda row: row["id"])
        write_jsonl(args.output_root / f"{name}.jsonl", rows)
    report = {
        "report_version": "cleanup-import-report-v1",
        "contains_example_text": False,
        "source_manifest_sha256": sha256_file(args.source_manifest),
        "source_config_sha256": sha256_file(args.source_config),
        "importer_sha256": sha256_file(Path(__file__)),
        "source_rows_visited": dict(sorted(source_rows.items())),
        "mapped_rows": dict(sorted(mapped_rows.items())),
        "candidate_data_files": dict(sorted(candidate_files.items())),
        "held_out_data_files": dict(sorted(holdout_files.items())),
        "source_native_holdouts_consumed": False,
        "outcome_counts": {name: len(rows) for name, rows in outputs.items()},
        "reasons": dict(sorted(reasons.items())),
    }
    atomic_json(args.output_root / "import-report.json", report)
    print(json.dumps(report["outcome_counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
