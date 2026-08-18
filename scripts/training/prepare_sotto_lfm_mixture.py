#!/usr/bin/env python3
"""Build immutable natural-mixture Sotto LFM train/dev streams outside Git."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import secrets
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from xml.etree import ElementTree as ET
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

from cleanup_data_common import (  # noqa: E402
    near_duplicate_scores,
    nfc,
    ngrams,
    normalized_text,
    sha256_file,
    stable_hash,
)
from train_direct_source_adapter import manifest_files, source_rows  # noqa: E402


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CELL_COLUMN = re.compile(r"^[A-Z]+")
ENTITY = re.compile(
    r"\b(?:[A-Z][\w'-]*|\d+(?:[.:/-]\d+)*|[\w.+-]+@[\w.-]+\.\w+|"
    r"(?:[A-Za-z]:)?[/\\][^\s]+)\b",
    re.UNICODE,
)


def verified_file(
    source_base: Path, source_id: str, relative: str,
    indexed: dict[tuple[str, str], dict[str, Any]],
) -> Path:
    item = indexed.get((source_id, relative))
    if item is None:
        raise RuntimeError(f"source manifest does not contain {source_id}:{relative}")
    path = source_base / relative
    if not path.is_file():
        raise RuntimeError(f"missing pinned source file: {source_id}:{relative}")
    if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
        raise RuntimeError(f"pinned source file failed byte/hash verification: {source_id}:{relative}")
    return path


def verify_reused_source_identity(
    manifest: dict[str, Any], source_config: dict[str, Any],
) -> None:
    if manifest.get("manifest_version") != "cleanup-source-manifest-v1":
        raise RuntimeError("unexpected reused source manifest version")
    recorded = {source["id"]: source for source in manifest.get("sources", [])}
    configured = {source["id"]: source for source in source_config["sources"]}
    for source_id in ("sotto", "disfl_qa", "nyra"):
        if source_id not in recorded:
            raise RuntimeError(f"reused source manifest lacks {source_id}")
        for field in ("url", "revision", "license"):
            if recorded[source_id].get(field) != configured[source_id].get(field):
                raise RuntimeError(f"reused source identity mismatch for {source_id}: {field}")


def disco_manifest_entry(rule: dict[str, Any], root: Path) -> dict[str, Any]:
    files = []
    for relative, expected_hash in sorted(rule["expected_files"].items()):
        path = root / relative
        if not path.is_file() or path.is_symlink() or sha256_file(path) != expected_hash:
            raise RuntimeError(f"DISCO payload failed pinned verification: {relative}")
        files.append({"path": relative, "bytes": path.stat().st_size, "sha256": expected_hash})
    return {
        "id": "disco", "url": rule["url"], "revision": rule["revision"],
        "license": rule["license"], "files": files,
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RuntimeError(f"{path}:{line_number}: expected an object")
            rows.append(value)
    return rows


def xlsx_rows(path: Path, worksheet: str) -> list[dict[str, str]]:
    """Read one small string-valued XLSX worksheet without adding an Excel dependency."""

    main = f"{{{MAIN_NS}}}"
    relationship = f"{{{REL_NS}}}"
    package_relationship = f"{{{PACKAGE_REL_NS}}}"
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = [
                "".join(node.text or "" for node in item.iter(main + "t"))
                for item in root.findall(main + "si")
            ]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            item.attrib["Id"]: item.attrib["Target"]
            for item in relationships.findall(package_relationship + "Relationship")
        }
        selected = None
        sheets = workbook.find(main + "sheets")
        if sheets is None:
            raise RuntimeError(f"{path}: workbook has no sheets")
        for item in sheets:
            if item.attrib.get("name") == worksheet:
                selected = item
                break
        if selected is None:
            raise RuntimeError(f"{path}: missing worksheet {worksheet!r}")
        target = targets[selected.attrib[relationship + "id"]].lstrip("/")
        target = target if target.startswith("xl/") else "xl/" + target
        sheet = ET.fromstring(archive.read(target))
        matrix: list[dict[str, str]] = []
        for row in sheet.iter(main + "row"):
            values: dict[str, str] = {}
            for cell in row.findall(main + "c"):
                match = CELL_COLUMN.match(cell.attrib.get("r", ""))
                if match is None:
                    raise RuntimeError(f"{path}: malformed cell reference")
                value = cell.find(main + "v")
                cell_type = cell.attrib.get("t")
                if cell_type == "inlineStr":
                    text = "".join(node.text or "" for node in cell.iter(main + "t"))
                elif value is None:
                    text = ""
                elif cell_type == "s":
                    text = shared[int(value.text or "0")]
                else:
                    text = value.text or ""
                values[match.group(0)] = text
            matrix.append(values)
    if not matrix:
        raise RuntimeError(f"{path}:{worksheet}: worksheet is empty")
    headers = matrix[0]
    if not all(header for header in headers.values()):
        headers = {column: header for column, header in headers.items() if header}
    return [
        {header: row.get(column, "") for column, header in headers.items()}
        for row in matrix[1:]
    ]


def pair_rows(
    source_bases: dict[str, Path],
    source_id: str,
    files: Sequence[str],
    raw_field: str,
    expected_field: str,
    indexed: dict[tuple[str, str], dict[str, Any]],
) -> tuple[list[dict[str, str]], int]:
    rows: list[dict[str, str]] = []
    publisher_records = 0
    for relative in files:
        path = verified_file(source_bases[source_id], source_id, relative, indexed)
        for locator, value in source_rows(path, raw_field, expected_field):
            publisher_records += 1
            raw, expected = value.get(raw_field), value.get(expected_field)
            if not isinstance(raw, str) or not raw.strip() or not isinstance(expected, str) or not expected.strip():
                continue
            rows.append({
                "pool_id": f"{source_id}:{relative}:{locator}",
                "source_id": source_id,
                "source_ref": f"{source_id}:{relative}:{locator}",
                "raw": nfc(raw),
                "expected": nfc(expected),
            })
    return rows, publisher_records


def split_disco(
    rows: Sequence[dict[str, str]], seed: int, fractions: dict[str, float],
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    if set(fractions) != {"train", "dev", "test"} or abs(sum(fractions.values()) - 1.0) > 1e-12:
        raise RuntimeError("DISCO split fractions must contain train/dev/test and sum to one")
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[normalized_text(row["expected"])].append(row)
    ordered_groups = list(groups.values())
    random.Random(seed).shuffle(ordered_groups)
    train_target = round(len(rows) * fractions["train"])
    dev_boundary = round(len(rows) * (fractions["train"] + fractions["dev"]))
    train: list[dict[str, str]] = []
    dev: list[dict[str, str]] = []
    test: list[dict[str, str]] = []
    for group in ordered_groups:
        if len(train) < train_target:
            train.extend(group)
        elif len(train) + len(dev) < dev_boundary:
            dev.extend(group)
        else:
            test.extend(group)
    normalized = [{normalized_text(row["expected"]) for row in split} for split in (train, dev, test)]
    if normalized[0] & normalized[1] or normalized[0] & normalized[2] or normalized[1] & normalized[2]:
        raise RuntimeError("DISCO normalized target family crossed the deterministic split")
    return train, dev, test


def load_pools(
    config: dict[str, Any], source_bases: dict[str, Path], manifest: dict[str, Any], seed: int,
) -> tuple[dict[str, dict[str, list[dict[str, str]]]], dict[str, Any]]:
    indexed = manifest_files(manifest)
    pools: dict[str, dict[str, list[dict[str, str]]]] = {}
    report: dict[str, Any] = {}
    for source_id in ("sotto", "disfl_qa", "nyra"):
        spec = config["sources"][source_id]
        train, publisher_train = pair_rows(
            source_bases, source_id, spec["train_files"], spec["raw_field"],
            spec["expected_field"], indexed,
        )
        dev, publisher_dev = pair_rows(
            source_bases, source_id, spec["dev_files"], spec["raw_field"],
            spec["expected_field"], indexed,
        )
        if len(train) != spec["train_records"] or len(dev) != spec["dev_records"]:
            raise RuntimeError(
                f"{source_id}: usable counts {len(train)}/{len(dev)} differ from "
                f"{spec['train_records']}/{spec['dev_records']}"
            )
        expected_publisher_train = spec.get("publisher_train_records", spec["train_records"])
        invalid = publisher_train - len(train)
        if publisher_train != expected_publisher_train or invalid != spec.get("declared_invalid_train_records", 0):
            raise RuntimeError(f"{source_id}: publisher or invalid train count changed")
        if publisher_dev != spec["dev_records"]:
            raise RuntimeError(f"{source_id}: publisher dev count changed")
        pools[source_id] = {"train": train, "dev": dev}
        report[source_id] = {
            "publisher_train_records": publisher_train,
            "train_records": len(train),
            "dev_records": len(dev),
            "declared_invalid_train_records": invalid,
            "excluded_files": spec["excluded_files"],
        }

    disco = config["sources"]["disco"]
    workbook = verified_file(source_bases["disco"], "disco", disco["workbook"], indexed)
    values = xlsx_rows(workbook, disco["worksheet"])
    disco_rows: list[dict[str, str]] = []
    for ordinal, value in enumerate(values, 1):
        raw = value.get(disco["raw_column"], "")
        expected = value.get(disco["expected_column"], "")
        category = value.get(disco["type_column"], "").strip()
        if not raw.strip() or not expected.strip() or category not in disco["allowed_types"]:
            raise RuntimeError(f"DISCO worksheet row {ordinal + 1} is malformed")
        disco_rows.append({
            "pool_id": f"disco:{disco['workbook']}:{disco['worksheet']}:{ordinal}",
            "source_id": "disco",
            "source_ref": f"disco:{disco['workbook']}:{disco['worksheet']}:{ordinal}",
            "raw": nfc(raw),
            "expected": nfc(expected),
            "disfluency_type": category,
        })
    if len(disco_rows) != disco["publisher_records"]:
        raise RuntimeError(f"DISCO row count {len(disco_rows)} != {disco['publisher_records']}")
    disco_train, disco_dev, disco_test = split_disco(
        disco_rows, seed, disco["split_fractions"],
    )
    pools["disco"] = {"train": disco_train, "dev": disco_dev, "test": disco_test}
    report["disco"] = {
        "publisher_records": len(disco_rows),
        "worksheet": disco["worksheet"],
        "split_method": disco["split_method"],
        "train_records": len(disco_train),
        "dev_records": len(disco_dev),
        "test_records": len(disco_test),
        "normalized_expected_cross_split_overlap": 0,
        "test_source_ref_sha256": hash_strings(row["source_ref"] for row in disco_test),
    }
    return pools, report


def frozen_entries(paths: Iterable[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in paths:
        for row in read_jsonl(path):
            for field in ("raw", "expected"):
                value = row.get(field)
                if isinstance(value, str) and value.strip():
                    entries.append({
                        "ref": f"{path.name}:{row.get('id')}:{field}",
                        "value": value,
                        "normalized": normalized_text(value),
                        "masked": normalized_text(ENTITY.sub(" ENTITY ", value)),
                        "token": ngrams(value, 3),
                        "char": ngrams(value, 5, characters=True),
                    })
    return entries


def verify_frozen_separation(
    pools: dict[str, dict[str, list[dict[str, str]]]],
    frozen: Sequence[dict[str, Any]],
    thresholds: dict[str, float],
) -> dict[str, Any]:
    exact: dict[str, list[int]] = defaultdict(list)
    masked: dict[str, list[int]] = defaultdict(list)
    token_index: dict[str, set[int]] = defaultdict(set)
    char_index: dict[str, set[int]] = defaultdict(set)
    for index, item in enumerate(frozen):
        exact[item["normalized"]].append(index)
        masked[item["masked"]].append(index)
        for gram in item["token"]:
            token_index[gram].add(index)
        for gram in item["char"]:
            char_index[gram].add(index)

    seen: set[str] = set()
    comparisons = 0
    excluded_refs: list[str] = []
    excluded_counts: Counter[tuple[str, str]] = Counter()
    for source_id, split_map in pools.items():
        for split_name in ("train", "dev"):
            retained: list[dict[str, str]] = []
            for row in split_map[split_name]:
                row_overlaps = False
                for field in ("raw", "expected"):
                    value = row[field]
                    identity = hashlib.sha256(value.encode("utf-8")).hexdigest()
                    if identity in seen:
                        continue
                    seen.add(identity)
                    normalized = normalized_text(value)
                    entity_masked = normalized_text(ENTITY.sub(" ENTITY ", value))
                    candidates = set(exact.get(normalized, ()))
                    if len(entity_masked.split()) >= 4:
                        candidates.update(masked.get(entity_masked, ()))
                    token_grams = ngrams(value, 3)
                    char_grams = ngrams(value, 5, characters=True)
                    token_hits: dict[int, int] = defaultdict(int)
                    char_hits: dict[int, int] = defaultdict(int)
                    for gram in token_grams:
                        for index in token_index.get(gram, ()):
                            token_hits[index] += 1
                    for gram in char_grams:
                        for index in char_index.get(gram, ()):
                            char_hits[index] += 1
                    for index, intersection in token_hits.items():
                        required = math.ceil(
                            thresholds["token_3gram_jaccard"]
                            * (len(token_grams) + len(frozen[index]["token"]))
                            / (1 + thresholds["token_3gram_jaccard"])
                        )
                        if intersection >= required:
                            candidates.add(index)
                    for index, intersection in char_hits.items():
                        union = len(char_grams) + len(frozen[index]["char"]) - intersection
                        char_jaccard = intersection / union if union else 1.0
                        length_ratio = min(len(normalized), len(frozen[index]["normalized"])) / max(
                            len(normalized), len(frozen[index]["normalized"]), 1,
                        )
                        if (
                            char_jaccard >= thresholds["character_5gram_jaccard"]
                            or (
                                length_ratio >= thresholds["normalized_edit_similarity"]
                                and char_jaccard >= 0.35
                            )
                        ):
                            candidates.add(index)
                    if len(normalized) < 5:
                        candidates.update(range(len(frozen)))
                    for index in candidates:
                        comparisons += 1
                        item = frozen[index]
                        token, chars, edit = near_duplicate_scores(value, item["value"])
                        if (
                            normalized == item["normalized"]
                            or (entity_masked == item["masked"] and len(entity_masked.split()) >= 4)
                            or token >= thresholds["token_3gram_jaccard"]
                            or chars >= thresholds["character_5gram_jaccard"]
                            or edit >= thresholds["normalized_edit_similarity"]
                        ):
                            row_overlaps = True
                            break
                    if row_overlaps:
                        break
                if row_overlaps:
                    excluded_refs.append(f"{source_id}:{split_name}:{row['source_ref']}")
                    excluded_counts[(source_id, split_name)] += 1
                else:
                    retained.append(row)
            split_map[split_name] = retained
    return {
        "action": "exclude_entire_source_row",
        "unique_surfaces": len(seen), "candidate_comparisons": comparisons,
        "excluded_rows": len(excluded_refs),
        "excluded_counts": {
            f"{source}:{split}": count
            for (source, split), count in sorted(excluded_counts.items())
        },
        "excluded_source_refs_sha256": hash_strings(excluded_refs),
        "remaining_pool_counts": {
            f"{source}:{split}": len(split_map[split])
            for source, split_map in sorted(pools.items())
            for split in ("train", "dev")
        },
    }


def build_stream(
    pools: dict[str, dict[str, list[dict[str, str]]]], split: str, seed: int,
) -> tuple[list[dict[str, str]], dict[str, int], list[str]]:
    """Shuffle every eligible row exactly once; do not rebalance or replay small sources."""

    counts = {source: len(split_map[split]) for source, split_map in pools.items()}
    stream = [row for split_map in pools.values() for row in split_map[split]]
    shuffle_seed = int(stable_hash(f"{seed}:{split}:single-pass", 16), 16)
    random.Random(shuffle_seed).shuffle(stream)
    if len({row["source_ref"] for row in stream}) != len(stream):
        raise RuntimeError(f"{split} single-pass stream contains a repeated source row")
    return stream, counts, [row["source_id"] for row in stream]


def hash_strings(values: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def write_stream(path: Path, split: str, rows: Sequence[dict[str, str]]) -> str:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        for ordinal, row in enumerate(rows, 1):
            value = {
                "id": f"sotto-lfm-{split}-{ordinal:06d}",
                "source_id": row["source_id"],
                "source_ref": row["source_ref"],
                "raw": row["raw"],
                "expected": row["expected"],
            }
            handle.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
    return sha256_file(path)


def ensure_output_boundary(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    repo = REPO_ROOT.resolve()
    if resolved == repo or repo in resolved.parents:
        raise RuntimeError("source-balanced mixture text must remain outside the Git repository")
    if output_dir.exists():
        if not output_dir.is_dir() or any(output_dir.iterdir()):
            raise RuntimeError("output directory must be new or empty")
    else:
        output_dir.mkdir(parents=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reused-source-root", type=Path,
        default=Path("/data/rise/android_stt/raw/sources-v1"),
        help="legacy verified root used only for the GitHub-hosted Disfl-QA payload",
    )
    parser.add_argument(
        "--source-manifest", type=Path,
        default=Path("/data/rise/android_stt/manifests/source-manifest-v1.json"),
    )
    parser.add_argument(
        "--disco-root", type=Path,
        default=Path("/data/rise/android_stt/raw/disco-b91a9e8d43cbfbefb9d7b0ff836c18d9a676943d"),
    )
    parser.add_argument(
        "--hf-hub-cache", type=Path,
        default=Path(os.environ.get("HF_HUB_CACHE", "/data/rise/.cache/huggingface/hub")),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--seed", type=int,
        help="optional split/mixing seed; generated and recorded when omitted",
    )
    parser.add_argument(
        "--config", type=Path,
        default=REPO_ROOT / "training/config/sotto-lfm-data-v1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_output_boundary(args.output_dir)
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config.get("config_version") != "sotto-lfm-natural-mixture-data-v1":
        raise RuntimeError("unexpected Sotto LFM data configuration version")
    seed = args.seed if args.seed is not None else secrets.randbits(63)
    source_config_path = REPO_ROOT / config["source_config_path"]
    source_config = json.loads(source_config_path.read_text(encoding="utf-8"))
    source_manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    verify_reused_source_identity(source_manifest, source_config)
    configured_sources = {source["id"]: source for source in source_config["sources"]}
    disco_entry = disco_manifest_entry(configured_sources["disco"], args.disco_root)
    combined_manifest = {**source_manifest, "sources": [*source_manifest["sources"], disco_entry]}
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("mixture preparation requires huggingface_hub") from exc
    source_bases = {
        "sotto": Path(snapshot_download(
            configured_sources["sotto"]["repository"], repo_type="dataset",
            revision=configured_sources["sotto"]["revision"],
            cache_dir=args.hf_hub_cache, local_files_only=True,
        )),
        "nyra": Path(snapshot_download(
            configured_sources["nyra"]["repository"], repo_type="dataset",
            revision=configured_sources["nyra"]["revision"],
            cache_dir=args.hf_hub_cache, local_files_only=True,
        )),
        "disfl_qa": args.reused_source_root / "disfl_qa",
        "disco": args.disco_root,
    }
    pools, source_report = load_pools(config, source_bases, combined_manifest, seed)
    frozen = frozen_entries(REPO_ROOT / path for path in config["frozen_evaluation_paths"])
    frozen_audit = verify_frozen_separation(
        pools, frozen, config["frozen_near_duplicate"],
    )
    train, train_counts, train_schedule = build_stream(pools, "train", seed)
    dev, dev_counts, dev_schedule = build_stream(pools, "dev", seed)
    train_path, dev_path = args.output_dir / "train.jsonl", args.output_dir / "dev.jsonl"
    train_hash = write_stream(train_path, "train", train)
    dev_hash = write_stream(dev_path, "dev", dev)
    manifest = {
        "manifest_version": "sotto-lfm-mixture-manifest-v1",
        "contains_example_text": False,
        "preparer_sha256": sha256_file(Path(__file__)),
        "config_sha256": sha256_file(args.config),
        "source_config_sha256": sha256_file(source_config_path),
        "source_manifest_sha256": sha256_file(args.source_manifest),
        "canonical_hf_hub_cache": str(args.hf_hub_cache.resolve()),
        "disco_root": str(args.disco_root.resolve()),
        "frozen_evaluation_sha256": {
            path: sha256_file(REPO_ROOT / path) for path in config["frozen_evaluation_paths"]
        },
        "seed": seed,
        "mixture_strategy": config["mixture_strategy"],
        "derived_source_shares": {
            split: {
                source: count / sum(counts.values()) for source, count in counts.items()
            }
            for split, counts in (("train", train_counts), ("dev", dev_counts))
        },
        "source_audit": source_report,
        "frozen_overlap_audit": frozen_audit,
        "streams": {
            "train": {
                "path": "train.jsonl", "records": len(train), "source_counts": train_counts,
                "sha256": train_hash, "source_schedule_sha256": hash_strings(train_schedule),
                "ordered_source_refs_sha256": hash_strings(row["source_ref"] for row in train),
            },
            "dev": {
                "path": "dev.jsonl", "records": len(dev), "source_counts": dev_counts,
                "sha256": dev_hash, "source_schedule_sha256": hash_strings(dev_schedule),
                "ordered_source_refs_sha256": hash_strings(row["source_ref"] for row in dev),
            },
        },
    }
    manifest_path = args.output_dir / "mixture-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "manifest": str(manifest_path), "manifest_sha256": sha256_file(manifest_path),
        "train_records": len(train), "dev_records": len(dev),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
