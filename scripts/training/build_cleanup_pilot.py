#!/usr/bin/env python3
"""Group, split, quota-sample, and audit the reviewed cleanup pilot."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from cleanup_data_common import jaccard, ngrams, normalized_text, require_empty_output_dir, stable_hash, write_jsonl


CROSS_CUTTING_NAMES = (
    "must_not_answer_or_command_question",
    "adversarial_instruction",
    "protected_literal",
    "negation_or_uncertainty",
    "unicode_or_multilingual",
    "technical_text",
    "long_form",
    "high_stakes",
)


class UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def bounded_edit_similarity(left: str, right: str, threshold: float) -> float:
    """Return normalized Levenshtein similarity only when it can meet threshold.

    Pilot grouping only needs to know whether a pair reaches the configured
    threshold. Restricting the dynamic-programming matrix to that edit band
    avoids SequenceMatcher's quadratic worst case across the candidate pool.
    """

    if not 0.0 <= threshold <= 1.0:
        raise RuntimeError("normalized_edit_similarity must be between 0 and 1")
    if left == right:
        return 1.0
    longest = max(len(left), len(right))
    if longest == 0:
        return 1.0
    max_distance = int((1.0 - threshold) * longest + 1e-9)
    if abs(len(left) - len(right)) > max_distance:
        return 0.0

    # Myers' bit-vector algorithm computes the exact Levenshtein distance with
    # one Python big-integer operation per character in the longer string.
    # That retains exact threshold semantics without a Python-level matrix for
    # every candidate pair.
    if len(left) > len(right):
        left, right = right, left
    width = len(left)
    if width == 0:
        distance = len(right)
    else:
        character_masks: dict[str, int] = {}
        for index, character in enumerate(left):
            character_masks[character] = character_masks.get(character, 0) | (1 << index)
        mask = (1 << width) - 1
        highest_bit = 1 << (width - 1)
        positive = mask
        negative = 0
        distance = width
        for character in right:
            equality = character_masks.get(character, 0)
            vertical = equality | negative
            horizontal = (((equality & positive) + positive) ^ positive) | equality
            positive_horizontal = negative | ~(horizontal | positive)
            negative_horizontal = positive & horizontal
            if positive_horizontal & highest_bit:
                distance += 1
            elif negative_horizontal & highest_bit:
                distance -= 1
            positive_horizontal = ((positive_horizontal << 1) | 1) & mask
            negative_horizontal = (negative_horizontal << 1) & mask
            positive = (negative_horizontal | ~(vertical | positive_horizontal)) & mask
            negative = positive_horizontal & vertical
    return 0.0 if distance > max_distance else 1.0 - distance / longest


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise RuntimeError(f"{path}:{line_number}: expected an object")
                rows.append(value)
    return rows


def build_components(rows: list[dict[str, Any]], thresholds: dict[str, float]) -> tuple[UnionFind, list[dict[str, Any]]]:
    union = UnionFind(len(rows))
    exact: dict[str, int] = {}
    family: dict[str, int] = {}
    template: dict[str, int] = {}
    buckets: dict[str, list[int]] = defaultdict(list)
    features: list[tuple[set[str], set[str]]] = []
    normalized_pairs: list[str] = []
    for index, row in enumerate(rows):
        text = f"{row['raw']}\n{row['expected']}"
        normalized = normalized_text(text)
        normalized_pairs.append(normalized)
        if normalized in exact:
            union.union(index, exact[normalized])
        exact.setdefault(normalized, index)
        for field, mapping in (("family_id", family), ("template_id", template)):
            value = row[field]
            if value in mapping:
                union.union(index, mapping[value])
            mapping.setdefault(value, index)
        token_features = ngrams(text, 3)
        char_features = ngrams(text, 5, characters=True)
        features.append((token_features, char_features))
        signatures = sorted(stable_hash(item, 12) for item in token_features)[:4]
        signatures += sorted(stable_hash(item, 12) for item in char_features)[:4]
        for signature in signatures:
            buckets[signature].append(index)
    compared: set[tuple[int, int]] = set()
    flags: list[dict[str, Any]] = []
    for signature, members in sorted(buckets.items()):
        if len(members) > 500:
            continue
        for offset, left in enumerate(members):
            for right in members[offset + 1:]:
                if union.find(left) == union.find(right):
                    continue
                pair = (min(left, right), max(left, right))
                if pair in compared:
                    continue
                compared.add(pair)
                token = jaccard(features[left][0], features[right][0])
                chars = jaccard(features[left][1], features[right][1])
                token_hit = token >= thresholds["token_3gram_jaccard"]
                chars_hit = chars >= thresholds["character_5gram_jaccard"]
                edit = 0.0
                if not token_hit and not chars_hit:
                    edit = bounded_edit_similarity(
                        normalized_pairs[left], normalized_pairs[right],
                        thresholds["normalized_edit_similarity"],
                    )
                if token_hit or chars_hit or edit >= thresholds["normalized_edit_similarity"]:
                    union.union(left, right)
                    flags.append({"left": rows[left]["id"], "right": rows[right]["id"], "token_3gram": token, "character_5gram": chars, "edit_similarity": edit, "blocking_signature": signature})
    return union, flags


def bucket(row: dict[str, Any]) -> str | None:
    categories = set(row["categories"])
    risks = set(row["risk_tags"])
    # Primary buckets describe the edit operation. Safety labels deliberately
    # overlap them, so an adversarial dictated sentence with an explicit
    # correction remains a correction row and also contributes adversarial
    # cross-cutting coverage. This is necessary to satisfy the independently
    # specified 8% adversarial minimum while retaining the 5% pure-adversarial
    # primary target.
    if str(row.get("source_ref", "")).startswith("disfl_qa:"):
        return "disfl_qa_correction"
    if "list_formatting" in categories:
        return "explicit_list_formatting"
    if "paragraph_formatting" in categories:
        return "explicit_paragraph_formatting"
    if "spoken_punctuation" in categories or "formatting_directive" in categories:
        return "explicit_spoken_punctuation"
    if "grammar_rewrite" in categories:
        return "grammar_rewrite"
    if "asr_correction" in categories:
        return "asr_correction"
    if categories & {"mixed", "discourse_marker"}:
        return "mixed_or_discourse"
    if categories & {"self_correction", "false_start", "abandoned_start"}:
        return "correction_or_false_start"
    if categories & {"fillers", "repetition", "discourse_marker"}:
        return "filler_or_repetition"
    if "adversarial_instruction" in categories:
        return "adversarial_must_not_answer"
    if categories & {"no_op", "already_clean"}:
        return "clean_no_op"
    if risks & {"number", "name", "technical_literal", "unicode_literal", "negation", "uncertainty"}:
        return "protected_literal"
    return None


def cross_cutting_flags(row: dict[str, Any]) -> set[str]:
    categories = set(row["categories"])
    risks = set(row["risk_tags"])
    flags = set()
    if categories & {"must_not_answer", "command", "question"}:
        flags.add("must_not_answer_or_command_question")
    if "adversarial_instruction" in categories:
        flags.add("adversarial_instruction")
    if risks & {"number", "name", "technical_literal", "unicode_literal"}:
        flags.add("protected_literal")
    if risks & {"negation", "uncertainty"}:
        flags.add("negation_or_uncertainty")
    if categories & {"unicode", "multilingual"}:
        flags.add("unicode_or_multilingual")
    if "technical_text" in categories:
        flags.add("technical_text")
    if "long_form" in categories:
        flags.add("long_form")
    if "high_stakes" in categories or "high_stakes" in risks:
        flags.add("high_stakes")
    return flags


def choose(
    rows: list[dict[str, Any]],
    quotas: dict[str, int],
    seed: int,
    split: str,
    minimum_cross_cutting_fraction: dict[str, float],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        assigned = bucket(row)
        if assigned:
            by_bucket[assigned].append(row)
    chosen: list[dict[str, Any]] = []
    chosen_ids: set[str] = set()
    chosen_by_bucket: Counter[str] = Counter()
    cross_counts: Counter[str] = Counter()
    counts: dict[str, int] = {}
    for name, target in quotas.items():
        counts[name] = len(by_bucket[name])
        if counts[name] < target:
            raise RuntimeError(f"{split} quota {name} requires {target}, only {counts[name]} eligible")

    total = sum(quotas.values())
    required = {
        name: math.ceil(total * fraction)
        for name, fraction in minimum_cross_cutting_fraction.items()
    }
    row_flags = {row["id"]: cross_cutting_flags(row) for row in rows}
    row_buckets = {row["id"]: bucket(row) for row in rows}
    cross_available = Counter(
        flag for row in rows if row_buckets[row["id"]] in quotas for flag in row_flags[row["id"]]
    )
    missing = {
        name: (required[name], cross_available[name])
        for name in required if cross_available[name] < required[name]
    }
    if missing:
        raise RuntimeError(f"{split} cross-cutting supply is insufficient: {missing}")

    def add(row: dict[str, Any]) -> None:
        assigned = row_buckets[row["id"]]
        if assigned is None or assigned not in quotas:
            raise AssertionError("selected row has no configured primary bucket")
        chosen.append(row)
        chosen_ids.add(row["id"])
        chosen_by_bucket[assigned] += 1
        cross_counts.update(row_flags[row["id"]])

    # Satisfy the rarest cross-cutting requirements first. Candidates that
    # cover several still-unmet dimensions are preferred; stable hashes make
    # every tie reproducible. Primary bucket capacities remain exact.
    labels = sorted(required, key=lambda name: (cross_available[name] / required[name], name))
    for label in labels:
        candidates = sorted(
            (
                row for row in rows
                if row_buckets[row["id"]] in quotas and label in row_flags[row["id"]]
            ),
            key=lambda row: (
                -len(row_flags[row["id"]] & set(required)),
                stable_hash(f"{seed}:{split}:cross:{row['id']}", 64),
            ),
        )
        cursor = 0
        while cross_counts[label] < required[label]:
            while cursor < len(candidates):
                candidate = candidates[cursor]
                cursor += 1
                assigned = row_buckets[candidate["id"]]
                if candidate["id"] not in chosen_ids and chosen_by_bucket[assigned] < quotas[assigned]:
                    break
            else:
                raise RuntimeError(
                    f"{split} cannot satisfy {label}: need {required[label]}, "
                    f"selected {cross_counts[label]} within remaining primary capacities"
                )
            add(candidate)

    for name, target in quotas.items():
        candidates = sorted(
            (row for row in by_bucket[name] if row["id"] not in chosen_ids),
            key=lambda row: stable_hash(f"{seed}:{split}:fill:{row['id']}", 64),
        )
        needed = target - chosen_by_bucket[name]
        if needed < 0:
            raise AssertionError(f"{split}: overfilled primary bucket {name}")
        for row in candidates[:needed]:
            add(row)
        if chosen_by_bucket[name] != target:
            raise RuntimeError(
                f"{split} quota {name} requires {target}, selected {chosen_by_bucket[name]}"
            )
    ids = [row["id"] for row in chosen]
    if len(ids) != len(set(ids)):
        raise RuntimeError(f"{split}: bucket assignment selected a row more than once")
    return sorted(chosen, key=lambda row: row["id"]), counts


def preselect_candidate_pool(
    rows: list[dict[str, Any]], config: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Bound expensive near-duplicate grouping without changing final quota semantics."""

    multiplier = config.get("candidate_pool_multiplier", 4)
    if not isinstance(multiplier, int) or multiplier < 2:
        raise RuntimeError("candidate_pool_multiplier must be an integer of at least 2")
    dev_ratio = config["dev_records"] / config["train_records"]
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        assigned = bucket(row)
        if assigned in config["train_primary_buckets"]:
            by_bucket[assigned].append(row)
    selected_by_id: dict[str, dict[str, Any]] = {}
    available: dict[str, int] = {}
    for name, train_target in config["train_primary_buckets"].items():
        candidates = sorted(
            by_bucket[name],
            key=lambda row: stable_hash(f"{config['seed']}:candidate-pool:{row['id']}", 64),
        )
        available[name] = len(candidates)
        dev_target = round(train_target * dev_ratio)
        limit = math.ceil((train_target + dev_target) * multiplier)
        for row in candidates[:limit]:
            selected_by_id[row["id"]] = row
        # Stable per-dimension reserves prevent a rare supplemental stratum
        # from being washed out by a much larger public primary bucket before
        # family grouping and the project split.
        for label, fraction in config["minimum_cross_cutting_fraction"].items():
            reserve = math.ceil((train_target + round(train_target * dev_ratio)) * fraction * multiplier)
            matching = [row for row in candidates if label in cross_cutting_flags(row)]
            for row in matching[:reserve]:
                selected_by_id[row["id"]] = row
    return sorted(selected_by_id.values(), key=lambda row: row["id"]), available


def cross_cutting(rows: list[dict[str, Any]]) -> dict[str, float]:
    total = len(rows)
    if not total:
        return {name: 0.0 for name in CROSS_CUTTING_NAMES}
    counts = Counter(flag for row in rows for flag in cross_cutting_flags(row))
    return {name: counts[name] / total for name in CROSS_CUTTING_NAMES}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--config", type=Path, default=Path("training/config/pilot-v1.json"))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--allow-pending", action="store_true", help="build review-stage files; never qualifies Gate A")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    require_empty_output_dir(args.output_root)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    input_rows = [row for path in args.input for row in read_jsonl(path)]
    rows = input_rows
    ids = [row.get("id") for row in rows]
    if len(ids) != len(set(ids)):
        raise RuntimeError("input files contain duplicate record IDs")
    if not args.allow_pending:
        unapproved = [row["id"] for row in rows if row.get("review", {}).get("status") != "approved"]
        if unapproved:
            raise RuntimeError(f"release pilot requires every selected source row to be human-approved; found {len(unapproved)} unapproved rows")
    rows, pool_available = preselect_candidate_pool(rows, config)
    union, near_flags = build_components(rows, config["near_duplicate"])
    components: dict[int, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        components[union.find(index)].append(index)
    dev_cutoff = int(config["dev_fraction_before_sampling"] * (1 << 64))
    split_counts: Counter[str] = Counter()
    for members in components.values():
        component_key = "\0".join(sorted(rows[index]["id"] for index in members))
        split = "dev" if int(stable_hash(f"{config['seed']}:{component_key}", 16), 16) < dev_cutoff else "train"
        for index in members:
            rows[index]["split"] = split
            split_counts[split] += 1
    train_quotas = config["train_primary_buckets"]
    dev_quotas = {name: round(target * config["dev_records"] / config["train_records"]) for name, target in train_quotas.items()}
    train, train_available = choose(
        [row for row in rows if row["split"] == "train"], train_quotas,
        config["seed"], "train", config["minimum_cross_cutting_fraction"],
    )
    dev, dev_available = choose(
        [row for row in rows if row["split"] == "dev"], dev_quotas,
        config["seed"], "dev", config["minimum_cross_cutting_fraction"],
    )
    if len(train) != config["train_records"] or len(dev) != config["dev_records"]:
        raise RuntimeError("configured bucket quotas do not sum to requested pilot sizes")
    train_cross, dev_cross = cross_cutting(train), cross_cutting(dev)
    quota_failures = []
    for split, values in (("train", train_cross), ("dev", dev_cross)):
        for name, minimum in config["minimum_cross_cutting_fraction"].items():
            if values[name] < minimum:
                quota_failures.append(f"{split}:{name}={values[name]:.4f} < {minimum:.4f}")
    write_jsonl(args.output_root / "train.jsonl", train)
    write_jsonl(args.output_root / "dev.jsonl", dev)
    report = {
        "report_version": "cleanup-pilot-build-report-v1",
        "release_eligible": not args.allow_pending and not quota_failures,
        "input_records": len(input_rows), "candidate_pool_records": len(rows),
        "candidate_pool_available_by_bucket": pool_available,
        "component_count": len(components),
        "pre_sampling_split_counts": dict(sorted(split_counts.items())),
        "selected_counts": {"train": len(train), "dev": len(dev)},
        "available_by_bucket": {"train": train_available, "dev": dev_available},
        "cross_cutting_fraction": {"train": train_cross, "dev": dev_cross},
        "quota_failures": quota_failures,
        "near_duplicate_flags": near_flags,
    }
    (args.output_root / "build-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if quota_failures:
        raise RuntimeError("cross-cutting quotas failed: " + "; ".join(quota_failures))
    print(json.dumps(report["selected_counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
