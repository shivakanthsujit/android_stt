from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve().parents[1] / "validate-cleanup-training-data.py"
SPEC = importlib.util.spec_from_file_location("validate_cleanup_training_data", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def valid_record(**updates: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": "train-correction-000001",
        "raw": "send it Monday no make that Wednesday",
        "expected": "Send it Wednesday.",
        "categories": ["self_correction", "false_start", "punctuation"],
        "must_preserve": ["Wednesday"],
        "must_remove": ["Monday", "no make that"],
        "risk_tags": ["superseded_fact"],
        "source": "human_authored",
        "family_id": "correction-date-00001",
        "template_id": "correction-date-v1",
        "split": "train",
        "review": {"status": "approved", "reviewers": 1},
        "license": "project-authored",
        "generator_version": "cleanup-data-v1",
    }
    record.update(updates)
    return record


def write_jsonl(path: Path, *records: dict[str, Any]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def run_main(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        result = validator.main(args)
    return result, stdout.getvalue(), stderr.getvalue()


class CleanupTrainingValidatorTest(unittest.TestCase):
    def test_valid_record_and_release_review_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "train.jsonl"
            write_jsonl(path, valid_record())
            code, stdout, stderr = run_main(
                ["--no-frozen-check", "--require-approved", str(path)]
            )
            self.assertEqual(0, code, stderr)
            self.assertIn("Validated 1 record", stdout)

    def test_schema_enum_contract_matches_implementation(self) -> None:
        schema = json.loads(validator.SCHEMA_PATH.read_text(encoding="utf-8"))
        properties = schema["properties"]
        self.assertEqual(validator.SPLITS, frozenset(properties["split"]["enum"]))
        self.assertEqual(validator.SOURCES, frozenset(properties["source"]["enum"]))
        self.assertEqual(
            validator.CATEGORIES,
            frozenset(properties["categories"]["items"]["enum"]),
        )
        self.assertEqual(
            validator.RISK_TAGS,
            frozenset(properties["risk_tags"]["items"]["enum"]),
        )

    def test_reports_missing_unknown_and_invalid_enum_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            record = valid_record(categories=["invented_category"], extra="nope")
            del record["license"]
            write_jsonl(path, record)
            code, _, stderr = run_main(["--no-frozen-check", str(path)])
            self.assertEqual(1, code)
            self.assertIn("missing required field(s): license", stderr)
            self.assertIn("unknown field(s): extra", stderr)
            self.assertIn("unknown value(s): invented_category", stderr)

    def test_rejects_non_nfc_anywhere_in_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            write_jsonl(path, valid_record(notes="Cafe\u0301"))
            code, _, stderr = run_main(["--no-frozen-check", str(path)])
            self.assertEqual(1, code)
            self.assertIn("notes must use Unicode NFC", stderr)

    def test_validates_preserve_and_remove_anchors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            write_jsonl(
                path,
                valid_record(
                    expected="Send it Monday.",
                    must_preserve=["Wednesday"],
                    must_remove=["Monday", "not in raw"],
                ),
            )
            code, _, stderr = run_main(["--no-frozen-check", str(path)])
            self.assertEqual(1, code)
            self.assertIn("must_preserve anchor absent from expected", stderr)
            self.assertIn("must_remove anchor survives in expected", stderr)
            self.assertIn("must_remove anchor absent from raw: 'not in raw'", stderr)

    def test_rejects_lexical_addition_unless_declared(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            undeclared = root / "undeclared.jsonl"
            declared = root / "declared.jsonl"
            record = valid_record(
                expected="Please send it Wednesday.",
                must_preserve=["Wednesday"],
            )
            write_jsonl(undeclared, record)
            write_jsonl(declared, {**record, "allowed_additions": ["Please"]})
            code, _, stderr = run_main(["--no-frozen-check", str(undeclared)])
            self.assertEqual(1, code)
            self.assertIn("undeclared lexical token(s): please (1)", stderr)
            code, _, stderr = run_main(["--no-frozen-check", str(declared)])
            self.assertEqual(0, code, stderr)

    def test_declared_lexical_additions_preserve_token_multiplicity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "declared-repeated.jsonl"
            record = valid_record(
                raw="send now",
                expected="please send please now",
                must_preserve=[],
                must_remove=[],
                allowed_additions=["please", "please"],
            )
            write_jsonl(path, record)
            code, _, stderr = run_main(["--no-frozen-check", str(path)])
            self.assertEqual(0, code, stderr)

    def test_rejects_duplicate_ids_and_normalized_pairs_across_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            train = root / "train.jsonl"
            dev = root / "dev.jsonl"
            first = valid_record()
            second = valid_record(
                raw="SEND IT MONDAY, NO MAKE THAT WEDNESDAY!",
                expected="send it wednesday",
                split="dev",
                family_id="another-family",
                template_id="another-template",
            )
            write_jsonl(train, first)
            write_jsonl(dev, second)
            code, _, stderr = run_main(
                ["--no-frozen-check", str(train), str(dev)]
            )
            self.assertEqual(1, code)
            self.assertIn("duplicate id", stderr)
            self.assertIn("duplicate normalized raw/expected pair", stderr)

    def test_rejects_family_and_template_cross_split_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "all.jsonl"
            write_jsonl(
                path,
                valid_record(),
                valid_record(
                    id="dev-correction-000002",
                    raw="keep red actually use blue",
                    expected="Use blue.",
                    must_preserve=["blue"],
                    must_remove=["red", "actually"],
                    split="dev",
                ),
            )
            code, _, stderr = run_main(["--no-frozen-check", str(path)])
            self.assertEqual(1, code)
            self.assertIn("family_id 'correction-date-00001' crosses splits", stderr)
            self.assertIn("template_id 'correction-date-v1' crosses splits", stderr)

    def test_rejects_frozen_overlap_after_case_and_punctuation_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frozen = root / "frozen.jsonl"
            proposed = root / "proposed.jsonl"
            write_jsonl(
                frozen,
                {"id": "frozen-1", "raw": "Do not send it!", "expected": "Do not send it."},
            )
            write_jsonl(
                proposed,
                valid_record(
                    raw="DO NOT SEND IT",
                    expected="Do not send it.",
                    must_preserve=["Do not"],
                    must_remove=[],
                    risk_tags=["negation"],
                ),
            )
            code, _, stderr = run_main(
                ["--frozen-case", str(frozen), str(proposed)]
            )
            self.assertEqual(1, code)
            self.assertIn("raw overlaps frozen evaluation text", stderr)
            self.assertIn("expected overlaps frozen evaluation text", stderr)

    def test_requires_provenance_for_derived_and_real_stt_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            write_jsonl(
                path,
                valid_record(source="deterministic_generated"),
                valid_record(
                    id="canary-2",
                    source="consented_real_stt",
                    source_ref="recording-consent-2",
                    family_id="canary-family-2",
                    template_id="canary-template-2",
                    split="train",
                ),
            )
            code, _, stderr = run_main(["--no-frozen-check", str(path)])
            self.assertEqual(1, code)
            self.assertIn("requires a non-empty 'source_ref'", stderr)
            self.assertIn("require 'speaker_id'", stderr)
            self.assertIn("require 'session_id'", stderr)
            self.assertIn("must use split 'real_canary'", stderr)

    def test_enforces_review_invariants_and_blind_double_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            write_jsonl(
                path,
                valid_record(
                    split="blind",
                    review={"status": "approved", "reviewers": 1},
                ),
            )
            code, _, stderr = run_main(["--no-frozen-check", str(path)])
            self.assertEqual(1, code)
            self.assertIn("approved blind records require at least 2 reviewers", stderr)
            self.assertIn("require review.adjudicated=true", stderr)

    def test_release_mode_rejects_pending_records(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pending.jsonl"
            write_jsonl(
                path,
                valid_record(review={"status": "pending", "reviewers": 0}),
            )
            code, _, stderr = run_main(
                ["--no-frozen-check", "--require-approved", str(path)]
            )
            self.assertEqual(1, code)
            self.assertIn("review.status must be 'approved' in release mode", stderr)

    def test_manifest_round_trip_hashes_dataset_schema_validator_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "train.jsonl"
            artifact = root / "generator-config.json"
            manifest = root / "manifest.json"
            write_jsonl(dataset, valid_record())
            artifact.write_text('{"seed":23}\n', encoding="utf-8")
            args = [
                "--no-frozen-check",
                "--hash-artifact",
                str(artifact),
                "--write-manifest",
                str(manifest),
                str(dataset),
            ]
            code, _, stderr = run_main(args)
            self.assertEqual(0, code, stderr)
            value = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(validator.MANIFEST_VERSION, value["manifest_version"])
            self.assertEqual(1, value["total_records"])
            self.assertEqual({"train": 1}, value["split_counts"])
            self.assertEqual(64, len(value["datasets"][0]["sha256"]))
            self.assertEqual(64, len(value["schema"]["sha256"]))
            self.assertEqual(64, len(value["validator"]["sha256"]))
            self.assertEqual(64, len(value["artifacts"][0]["sha256"]))

            code, _, stderr = run_main(
                [
                    "--no-frozen-check",
                    "--hash-artifact",
                    str(artifact),
                    "--check-manifest",
                    str(manifest),
                    str(dataset),
                ]
            )
            self.assertEqual(0, code, stderr)

            value["total_records"] = 99
            manifest.write_text(json.dumps(value), encoding="utf-8")
            code, _, stderr = run_main(
                [
                    "--no-frozen-check",
                    "--hash-artifact",
                    str(artifact),
                    "--check-manifest",
                    str(manifest),
                    str(dataset),
                ]
            )
            self.assertEqual(1, code)
            self.assertIn("manifest content or SHA-256 hashes do not match", stderr)

    def test_reports_invalid_json_with_line_number(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            path.write_text("{}\n{broken\n", encoding="utf-8")
            code, _, stderr = run_main(["--no-frozen-check", str(path)])
            self.assertEqual(1, code)
            self.assertIn("bad.jsonl:2: invalid JSON", stderr)

    def test_reports_non_utf8_input_instead_of_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.jsonl"
            path.write_bytes(b'{"id":"okay"}\n\xff\n')
            code, _, stderr = run_main(["--no-frozen-check", str(path)])
            self.assertEqual(1, code)
            self.assertIn("cannot read UTF-8 JSONL", stderr)


if __name__ == "__main__":
    unittest.main()
