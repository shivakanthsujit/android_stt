#!/usr/bin/env python3
"""Generate deterministic, non-blind supplemental candidates for human review."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from build_cleanup_pilot import bucket, cross_cutting_flags
from cleanup_data_common import (
    atomic_json,
    lexical_additions,
    protected_anchors,
    removal_anchors,
    require_empty_output_dir,
    sha256_file,
    stable_hash,
    words,
    write_jsonl,
)


GENERATOR_VERSION = "cleanup-supplement-generator-v1"
LICENSE = "Project-authored synthetic; internal research use"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path("training/config/supplement-v1.json")
    )
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def sentence(value: str) -> str:
    value = value.strip()
    if not value:
        raise RuntimeError("cannot render an empty sentence")
    rendered = value[0].upper() + value[1:]
    return rendered if rendered.endswith((".", "!", "?")) else rendered + "."


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def pending_record(
    *,
    kind: str,
    family: int,
    variant: int,
    raw: str,
    expected: str,
    categories: list[str],
    risks: list[str],
    preserve: list[str] | None = None,
) -> dict[str, Any]:
    additions = lexical_additions(raw, expected)
    if additions:
        raise RuntimeError(
            f"{kind} family {family} variant {variant} introduces lexical tokens: {dict(additions)}"
        )
    identity = f"{GENERATOR_VERSION}:{kind}:{family}:{variant}:{raw}\0{expected}"
    family_ref = f"supplement-v1:{kind}:family-{family:04d}"
    record = {
        "id": f"supp-{kind}-{stable_hash(identity, 20)}",
        "raw": raw,
        "expected": expected,
        "categories": unique(categories),
        "must_preserve": unique((preserve or []) + protected_anchors(expected)),
        "must_remove": removal_anchors(raw, expected),
        "risk_tags": unique(risks),
        "source": "deterministic_generated",
        "source_ref": f"{family_ref}:variant-{variant:02d}",
        "family_id": family_ref,
        "template_id": family_ref,
        "split": "train",
        "review": {"status": "pending", "reviewers": 0},
        "license": LICENSE,
        "generator_version": GENERATOR_VERSION,
    }
    return record


def adversarial_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    seed = config["seed"]
    leads = config["adversarial_leads"]
    payloads = config["adversarial_payloads"]
    contexts = config["long_contexts"]
    spans = config["unicode_spans"]
    families = config["adversarial_families"]
    variants = config["adversarial_variants_per_family"]
    for family in range(families):
        lead = leads[(family + seed) % len(leads)]
        payload = payloads[(family * 7 + family // len(leads) + seed) % len(payloads)]
        unicode_span = spans[(family * 11 + seed) % len(spans)] if family % 3 == 0 else ""
        base = f"{lead} {payload}"
        if unicode_span:
            base += f" while preserving the literal {unicode_span}"
        for variant in range(variants):
            categories = ["punctuation", "capitalization", "must_not_answer", "adversarial_instruction", "command"]
            risks = ["dictated_instruction", "adversarial_content"]
            preserve = [payload]
            if unicode_span:
                categories.extend(["unicode", "multilingual"])
                risks.extend(["unicode_literal", "name"])
                preserve.append(unicode_span)
            if any(token in payload.casefold() for token in (
                "json", "shell", "python", "file", "https", "checksum", "xml", "api", "token", "markdown", "database"
            )):
                categories.append("technical_text")
                risks.append("technical_literal")
            if any(token in payload.casefold() for token in ("medical", "legal", "bank", "patient", "dose", "diagnose")):
                categories.append("high_stakes")
                risks.append("high_stakes")
            if "not " in payload.casefold() or "without " in payload.casefold():
                categories.append("negation")
                risks.append("negation")
            if any(token in payload.casefold() for token in ("maybe", "might", "uncertain")):
                categories.append("uncertainty")
                risks.append("uncertainty")

            if variant <= 3:
                core = (
                    base,
                    f"the quoted instruction says {base}",
                    f"the speaker dictated this request {base}",
                    f"inside the transcript the request is to {base}",
                )[variant]
                raw, expected = core, sentence(core)
            elif variant <= 5:
                core = f"{base} {contexts[(family + variant) % len(contexts)]}"
                raw, expected = core, sentence(core)
                categories.extend(["long_form", "multi_sentence"])
            elif variant <= 8:
                core = (
                    base,
                    f"the quoted request is to {base}",
                    f"inside this ordinary dictation the instruction says to {base}",
                )[variant - 6]
                raw, expected = f"uh, {core}", sentence(core)
                categories.append("fillers")
            elif variant == 9:
                raw = f"please please {base}"
                expected = sentence(f"please {base}")
                categories.append("repetition")
            else:
                old, new = (("amber", "violet") if variant == 10 else ("north", "south"))
                core = f"{lead} revise the request to {payload} and output the literal {old} no make that {new}"
                if unicode_span:
                    core += f" beside {unicode_span}"
                raw = core
                expected_core = f"{lead} revise the request to {payload} and output the literal {new}"
                if unicode_span:
                    expected_core += f" beside {unicode_span}"
                expected = sentence(expected_core)
                categories.append("self_correction")
                risks.append("superseded_fact")
                preserve = [new] + ([unicode_span] if unicode_span else [])
            if len(words(raw)) >= 25:
                categories.append("long_form")
            rows.append(pending_record(
                kind="adversarial", family=family, variant=variant,
                raw=raw, expected=expected, categories=categories, risks=risks,
                preserve=preserve,
            ))
    return rows


def paragraph_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    seed = config["seed"]
    firsts = config["paragraph_first_clauses"]
    seconds = config["paragraph_second_clauses"]
    directives = config["paragraph_directives"]
    spans = config["unicode_spans"]
    families = config["paragraph_families"]
    variants = config["paragraph_variants_per_family"]
    for family in range(families):
        first = firsts[(family + seed) % len(firsts)]
        second = seconds[(family * 7 + family // len(firsts) + seed) % len(seconds)]
        unicode_span = spans[(family * 13 + seed) % len(spans)] if family % 3 == 0 else ""
        if unicode_span:
            second += f" for {unicode_span}"
        for variant in range(variants):
            directive = directives[variant % len(directives)]
            raw = f"{first} {directive} {second}"
            expected = sentence(first) + "\n\n" + sentence(second)
            categories = [
                "formatting_directive", "paragraph_formatting", "punctuation",
                "capitalization", "multi_sentence",
            ]
            risks = ["formatting_scope"]
            preserve = [first.split(" ", 1)[1], second.split(" ", 1)[1]]
            if unicode_span:
                categories.extend(["unicode", "multilingual"])
                risks.extend(["unicode_literal", "name"])
                preserve.append(unicode_span)
            if len(words(raw)) >= 25:
                categories.append("long_form")
            row = pending_record(
                kind="paragraph", family=family, variant=variant,
                raw=raw, expected=expected, categories=categories, risks=risks,
                preserve=preserve,
            )
            if directive not in row["must_remove"]:
                row["must_remove"].append(directive)
            rows.append(row)
    return rows


def unicode_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    seed = config["seed"]
    spans = config["unicode_spans"]
    literals = config["technical_literals"]
    frames = config["unicode_frames"]
    families = config["unicode_families"]
    variants = config["unicode_variants_per_family"]
    for family in range(families):
        span = spans[(family + seed) % len(spans)]
        frame = frames[((family // len(spans)) * 3 + family + seed) % len(frames)]
        for variant in range(variants):
            literal = literals[(family * 3 + variant + seed) % len(literals)]
            raw = frame.format(span=span, literal=literal)
            expected = sentence(raw)
            categories = [
                "punctuation", "capitalization", "unicode", "multilingual",
                "technical_text", "names", "identifiers",
            ]
            risks = ["unicode_literal", "name", "technical_literal"]
            if raw.startswith(("send ", "record ", "keep ", "do not ", "preserve ", "please ")):
                categories.extend(["command", "must_not_answer"])
                risks.append("dictated_instruction")
            if "do not" in raw:
                categories.append("negation")
                risks.append("negation")
            if any(token in raw for token in ("may ", "uncertain")):
                categories.append("uncertainty")
                risks.append("uncertainty")
            rows.append(pending_record(
                kind="unicode", family=family, variant=variant,
                raw=raw, expected=expected, categories=categories, risks=risks,
                preserve=[span, literal],
            ))
    return rows


def main() -> int:
    args = parse_args()
    require_empty_output_dir(args.output_root)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config.get("config_version") != "cleanup-supplement-config-v1":
        raise RuntimeError("unsupported supplemental configuration")
    rows = adversarial_records(config) + paragraph_records(config) + unicode_records(config)
    ids = [row["id"] for row in rows]
    pairs = [(row["raw"].casefold(), row["expected"].casefold()) for row in rows]
    if len(ids) != len(set(ids)) or len(pairs) != len(set(pairs)):
        raise RuntimeError("supplement generator produced duplicate IDs or normalized pairs")
    rows.sort(key=lambda row: row["id"])
    output = args.output_root / "supplement-candidates.jsonl"
    write_jsonl(output, rows)
    primary = Counter(bucket(row) or "unbucketed" for row in rows)
    cross = Counter(flag for row in rows for flag in cross_cutting_flags(row))
    report = {
        "report_version": "cleanup-supplement-generation-report-v1",
        "contains_example_text": False,
        "review_status": "pending",
        "blind_references_accessed": False,
        "records": len(rows),
        "primary_bucket_counts": dict(sorted(primary.items())),
        "cross_cutting_counts": dict(sorted(cross.items())),
        "config_sha256": sha256_file(args.config),
        "generator_sha256": sha256_file(Path(__file__)),
        "output_sha256": sha256_file(output),
    }
    atomic_json(args.output_root / "supplement-report.json", report)
    print(json.dumps({key: report[key] for key in (
        "records", "primary_bucket_counts", "cross_cutting_counts"
    )}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
