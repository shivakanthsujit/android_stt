from __future__ import annotations

import importlib.util
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
TRAINING_SCRIPTS = REPO / "scripts" / "training"
sys.path.insert(0, str(TRAINING_SCRIPTS))


def load(name: str):
    path = TRAINING_SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


common = load("cleanup_data_common")
fetcher = load("fetch_cleanup_sources")
importer = load("import_cleanup_sources")
builder = load("build_cleanup_pilot")
supplement = load("generate_cleanup_supplement")
reviewer = load("apply_cleanup_reviews")
gate_a = load("gate_a_cleanup")
trainer = load("train_cleanup_adapter")
direct_trainer = load("train_direct_source_adapter")
inference = load("infer_cleanup_adapter")
dev_scorer = load("score_cleanup_training_dev")
monitor = load("monitor_cleanup_run")
interactive_reviewer = load("review_cleanup_candidates")
environment_checker = load("check_training_environment")


class CleanupTrainingPipelineTest(unittest.TestCase):
    def test_chat_template_accepts_transformers_batch_encoding_shape(self) -> None:
        class MappingTokenizer:
            def apply_chat_template(self, *_args, **_kwargs):
                return {"input_ids": [1, 2, 3], "attention_mask": [1, 1, 1]}

        self.assertEqual(
            [1, 2, 3],
            trainer.apply_template(
                MappingTokenizer(), [{"role": "user", "content": "fixture"}],
                add_generation_prompt=True, kwargs={},
            ),
        )

    def test_direct_source_config_keeps_gate_a_path_separate_and_counts_exact(self) -> None:
        config_path = REPO / "training/config/direct-source-training-v1.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        serialized = json.dumps(config).casefold()
        self.assertNotIn("gate_a_report", serialized)
        self.assertNotIn("pilot_gate_a", serialized)
        self.assertEqual(135503, config["experiments"]["sotto"]["train_records"])
        self.assertEqual(7181, config["experiments"]["disfl_qa"]["train_records"])
        self.assertEqual(147142, config["experiments"]["combined"]["train_records"])
        resolved = direct_trainer.resolved_config(
            config, "sotto", Path(__file__), config_path, Path("/tmp/source-root"), "smoke"
        )
        self.assertEqual(4235, resolved["experiment"]["expected_optimizer_steps"])
        self.assertEqual(2, resolved["run_controls"]["max_steps"])

    def test_direct_source_loader_declares_invalid_rows_and_blocks_frozen_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "sources"
            data_path = source_root / "fixture" / "train.json"
            data_path.parent.mkdir(parents=True)
            data_path.write_text(json.dumps({
                "one": {"raw": "keep this", "expected": "Keep this."},
                "two": {"raw": "", "expected": "Invalid."},
            }), encoding="utf-8")
            indexed = {("fixture", "train.json"): {
                "bytes": data_path.stat().st_size,
                "sha256": trainer.sha256_file(data_path),
            }}
            spec = {
                "source_id": "fixture", "train_files": ["train.json"],
                "raw_field": "raw", "expected_field": "expected",
                "publisher_train_records": 2, "train_records": 1,
                "declared_invalid_train_records": 1,
            }
            rows, report = direct_trainer.load_source_split(
                source_root, spec, "train", indexed, set()
            )
            self.assertEqual(1, len(rows))
            self.assertEqual(1, report["declared_invalid_records"])
            with self.assertRaisesRegex(RuntimeError, "overlap frozen evaluation"):
                direct_trainer.load_source_split(
                    source_root, spec, "train", indexed, {"keep this"}
                )

    def test_direct_source_identity_binds_revision_and_file_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "sources.json"
            source_config = {"sources": [{
                "id": "fixture", "url": "https://example.invalid/data",
                "revision": "a" * 40, "license": "MIT",
            }]}
            config_path.write_text(json.dumps(source_config), encoding="utf-8")
            manifest = {
                "manifest_version": "cleanup-source-manifest-v1",
                "config_sha256": trainer.sha256_file(config_path),
                "sources": [{**source_config["sources"][0], "files": []}],
            }
            direct_trainer.verify_source_identity(manifest, source_config, config_path)
            manifest["sources"][0]["revision"] = "b" * 40
            with self.assertRaisesRegex(RuntimeError, "revision"):
                direct_trainer.verify_source_identity(manifest, source_config, config_path)

    def test_safe_target_rejects_archive_escape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(root / "data" / "train.json", fetcher.safe_target(root, "data/train.json"))
            with self.assertRaises(RuntimeError):
                fetcher.safe_target(root, "../secret")

    def test_source_fetch_resume_header_and_partial_path_validation(self) -> None:
        request = fetcher.request("https://example.invalid/data", range_start=42)
        self.assertEqual("bytes=42-", request.headers["Range"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            partial = root / "data" / "train.parquet.partial"
            partial.parent.mkdir()
            partial.write_bytes(b"partial")
            fetcher.verify_existing_huggingface_paths(root, ["data/train.parquet"])
            (root / "unexpected.txt").write_text("unexpected", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                fetcher.verify_existing_huggingface_paths(root, ["data/train.parquet"])

    def test_source_check_binds_manifest_to_current_pins(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "sources.json"
            source = {
                "id": "fixture", "url": "https://example.invalid/fixture",
                "revision": "a" * 40, "license": "MIT",
            }
            config = {"sources": [source]}
            config_path.write_text(json.dumps(config), encoding="utf-8")
            manifest = {
                "manifest_version": "cleanup-source-manifest-v1",
                "config_sha256": common.sha256_file(config_path),
                "sources": [{**source, "files": []}],
            }
            fetcher.verify_manifest_identity(manifest, config, config_path)
            manifest["sources"][0]["revision"] = "b" * 40
            with self.assertRaises(RuntimeError):
                fetcher.verify_manifest_identity(manifest, config, config_path)

    def test_environment_inventory_does_not_require_pip(self) -> None:
        inventory = environment_checker.installed_distribution_inventory()
        self.assertTrue(inventory)
        self.assertEqual(sorted(set(inventory), key=str.casefold), inventory)
        self.assertTrue(all("==" in row for row in inventory))

    def test_source_native_candidate_and_holdout_paths_are_separate(self) -> None:
        self.assertTrue(importer.path_matches("data/train-00000.parquet", ["**/train*.parquet"]))
        self.assertTrue(importer.path_matches("dev.json", ["dev.json", "**/dev.json"]))
        self.assertFalse(importer.path_matches("data/validation-00000.parquet", ["**/train*.parquet"]))
        config = json.loads((REPO / "training/config/sources-v1.json").read_text(encoding="utf-8"))
        sotto = next(source for source in config["sources"] if source["id"] == "sotto")
        self.assertEqual(["data/train-*.parquet"], sotto["candidate_include"])
        self.assertFalse(importer.path_matches("train.jsonl", sotto["candidate_include"]))

    def test_importer_maps_disfl_qa_as_pending_question_data(self) -> None:
        source = {"id": "disfl_qa", "license": "CC-BY-4.0"}
        row = {
            "squad_v2_id": "question-1",
            "disfluent question": "When was Paris founded no tell me when was Rome founded?",
            "original question": "When was Rome founded?",
        }
        result = importer.make_record(source, "train.json", "root/0", row)
        self.assertIsNotNone(result)
        outcome, record, reason = result
        self.assertEqual("quarantine", outcome)
        self.assertEqual("protected_anchor_changed", reason)
        self.assertIn("self_correction", record["categories"])
        self.assertIn("must_not_answer", record["categories"])
        self.assertEqual({"status": "pending", "reviewers": 0}, record["review"])
        self.assertIn("Paris", " ".join(record["must_remove"]))

    def test_importer_maps_pinned_disfl_qa_nested_row_shape(self) -> None:
        source = {"id": "disfl_qa", "license": "CC-BY-4.0"}
        row = {
            "original": "Who wrote the report?",
            "disfluent": "Where no who wrote the report?",
        }
        outcome, record, _ = importer.make_record(source, "train.json", "root/question-id", row)
        self.assertTrue(record["id"].startswith("candidate-disfl_qa-"))
        self.assertIn("question", record["categories"])
        self.assertIn(outcome, {"candidate", "quarantine"})

    def test_importer_rejects_nyra_annotation_only_tokens(self) -> None:
        source = {"id": "nyra", "license": "Apache-2.0"}
        row = {
            "id": "nyra-1", "speaker": "speaker-a",
            "verbatim_transcript": "we [UH] should go on th* Thursday [laughter]",
            "intended_transcript": "we should go on Thursday",
        }
        outcome, record, reason = importer.make_record(source, "data/train.parquet", "row-1", row)
        self.assertEqual("rejected", outcome)
        self.assertEqual("out_of_domain_transcription_annotation", reason)
        self.assertTrue(record["speaker_id"].startswith("nyra-speaker-"))

    def test_importer_maps_nyra_filler_tags_to_spoken_fillers(self) -> None:
        source = {"id": "nyra", "license": "Apache-2.0"}
        row = {
            "id": "nyra-2", "speaker": "speaker-a",
            "verbatim_transcript": "we [UH] should go now",
            "intended_transcript": "we should go now",
        }
        outcome, record, _ = importer.make_record(source, "data/train.parquet", "row-2", row)
        self.assertIn(outcome, {"candidate", "quarantine"})
        self.assertEqual("we uh should go now", record["raw"])
        self.assertIn("fillers", record["categories"])

    def test_importer_keeps_grammar_and_asr_repairs_for_human_review(self) -> None:
        source = {"id": "sotto", "license": "MIT"}
        grammar = {"input": "we gonna ship", "output": "We are going to ship.", "category": "grammar"}
        outcome, record, reason = importer.make_record(source, "train.parquet", "1", grammar)
        self.assertEqual("quarantine", outcome)
        self.assertEqual("lexical_addition_requires_review", reason)
        self.assertIn("grammar_rewrite", record["categories"])
        self.assertEqual(["are", "going", "to"], record["allowed_additions"])
        guessed = {"input": "use post gress", "output": "Use Postgres.", "category": "misheard_words"}
        outcome, record, reason = importer.make_record(source, "train.parquet", "2", guessed)
        self.assertEqual("quarantine", outcome)
        self.assertEqual("lexical_addition_requires_review", reason)
        self.assertIn("asr_correction", record["categories"])
        self.assertIn("inferred_content", record["risk_tags"])

    def test_importer_keeps_explicit_spoken_formatting_for_human_review(self) -> None:
        source = {"id": "sotto", "license": "MIT"}
        bullets = {
            "input": "make a bullet list apples mangoes bananas actually replace mangoes with oranges",
            "output": "- Apples\n- Oranges\n- Bananas",
            "category": "list_formatting",
        }
        outcome, record, reason = importer.make_record(source, "train.jsonl", "format-1", bullets)
        self.assertEqual("quarantine", outcome)
        self.assertEqual("review_required_category:list_formatting", reason)
        self.assertIn("formatting_directive", record["categories"])
        self.assertIn("list_formatting", record["categories"])
        self.assertIn("formatting_scope", record["risk_tags"])
        self.assertEqual("explicit_list_formatting", builder.bucket(record))

    def test_unlabeled_sotto_operations_are_inferred_from_high_precision_evidence(self) -> None:
        self.assertEqual(
            "list_formatting",
            importer.inferred_sotto_category("one apples two oranges", "1. Apples\n2. Oranges"),
        )
        self.assertEqual(
            "paragraph_formatting",
            importer.inferred_sotto_category("first part new paragraph second part", "First part.\n\nSecond part."),
        )
        self.assertEqual("grammar", importer.inferred_sotto_category("we gonna ship", "We are going to ship."))
        self.assertEqual("misheard_words", importer.inferred_sotto_category("use post gress", "Use Postgres."))
        self.assertEqual(
            "dictation_commands",
            importer.inferred_sotto_category("send it period", "Send it."),
        )
        self.assertEqual(
            "",
            importer.inferred_sotto_category("add five bullet points here", "Add five bullet points here."),
        )

    def test_content_command_is_preserved_but_correction_is_not_mislabeled_as_question(self) -> None:
        categories, risks = importer.classify("send the report", "Send the report.", "sotto", "")
        self.assertTrue({"command", "must_not_answer"}.issubset(categories))
        self.assertIn("dictated_instruction", risks)
        categories, _ = importer.classify(
            "send it Monday no make that Tuesday", "Send it Tuesday.", "sotto", "self_correction"
        )
        self.assertIn("self_correction", categories)
        self.assertNotIn("question", categories)

    def test_case_and_punctuation_only_row_is_clean_no_op_bucket(self) -> None:
        categories, _ = importer.classify("ship it", "Ship it.", "sotto", "")
        row = {"categories": categories, "risk_tags": [], "source_ref": "sotto:data/train.parquet:1"}
        self.assertIn("already_clean", categories)
        self.assertEqual("clean_no_op", builder.bucket(row))

    def test_list_number_conversion_requires_exact_spoken_markers(self) -> None:
        source = {"id": "sotto", "license": "MIT"}
        numbered = {
            "input": "make a numbered list one apples two oranges",
            "output": "1. Apples\n2. Oranges",
            "category": "list_formatting",
        }
        outcome, record, _ = importer.make_record(source, "train.jsonl", "format-2", numbered)
        self.assertEqual("quarantine", outcome)
        self.assertEqual(["1", "2"], record["allowed_additions"])
        unsafe = {**numbered, "output": "1. Apples\n2. Oranges\n3. Pears"}
        outcome, _, reason = importer.make_record(source, "train.jsonl", "format-3", unsafe)
        self.assertEqual("rejected", outcome)
        self.assertEqual("target_introduces_lexical_content", reason)

    def test_importer_quarantines_protected_literal_change(self) -> None:
        source = {"id": "sotto", "license": "MIT"}
        row = {"input": "deploy v1.2.3", "output": "Deploy v1.2.4.", "category": "self_correction"}
        outcome, _, reason = importer.make_record(source, "train.parquet", "3", row)
        self.assertEqual("quarantine", outcome)
        self.assertEqual("lexical_addition_requires_review", reason)

    def test_protected_literal_categories_cover_names_dates_versions_paths_and_money(self) -> None:
        categories, risks = importer.classify(
            "send it to Alex on Monday using v2.4 at /tmp/report for $20",
            "Send it to Alex on Monday using v2.4 at /tmp/report for $20.",
            "sotto",
            "preserve_wording",
        )
        self.assertTrue({"names", "dates", "versions", "paths", "money"}.issubset(categories))
        self.assertTrue({"name", "number", "technical_literal"}.issubset(risks))
        self.assertIn("Alex", common.protected_anchors("Send it to Alex."))

    def test_sentence_case_and_uncertain_may_are_not_names_or_dates(self) -> None:
        categories, _ = importer.classify(
            "may be ready. send it tomorrow",
            "May be ready. Send it tomorrow.",
            "sotto",
            "preserve_wording",
        )
        self.assertIn("uncertainty", categories)
        self.assertNotIn("names", categories)
        self.assertNotIn("dates", categories)
        self.assertIn("May", common.protected_anchors("May be ready. Send it tomorrow."))

    def test_near_duplicates_are_grouped_before_split(self) -> None:
        base = {
            "categories": ["self_correction"], "risk_tags": ["superseded_fact"],
            "source_ref": "sotto:x", "family_id": "family-a", "template_id": "template-a",
        }
        rows = [
            {**base, "id": "a", "raw": "send the report Monday no make that Wednesday", "expected": "Send the report Wednesday."},
            {**base, "id": "b", "family_id": "family-b", "template_id": "template-b", "raw": "send the report Monday no make that Thursday", "expected": "Send the report Thursday."},
        ]
        union, flags = builder.build_components(rows, {"token_3gram_jaccard": 0.5, "character_5gram_jaccard": 0.5, "normalized_edit_similarity": 0.5})
        self.assertEqual(union.find(0), union.find(1))
        self.assertTrue(flags)

    def test_near_duplicate_edit_path_uses_safe_upper_bound(self) -> None:
        base = {
            "categories": ["self_correction"], "risk_tags": [],
            "source_ref": "human:test", "family_id": "family", "template_id": "template",
        }
        rows = [
            {**base, "id": "left", "family_id": "left-family", "template_id": "left-template",
             "raw": "alpha beta gamma delta epsilon", "expected": "Alpha beta gamma delta epsilon."},
            {**base, "id": "right", "family_id": "right-family", "template_id": "right-template",
             "raw": "alpha beta gamma delta epsilons", "expected": "Alpha beta gamma delta epsilons."},
        ]
        union, flags = builder.build_components(rows, {
            "token_3gram_jaccard": 1.1,
            "character_5gram_jaccard": 1.1,
            "normalized_edit_similarity": 0.9,
        })
        self.assertEqual(union.find(0), union.find(1))
        self.assertGreaterEqual(flags[0]["edit_similarity"], 0.9)

    def test_near_duplicate_pass_skips_pairs_already_grouped_by_family(self) -> None:
        base = {
            "categories": ["fillers"], "risk_tags": [], "source_ref": "nyra:train:test",
            "family_id": "same-speaker", "template_id": "same-template",
        }
        rows = [
            {**base, "id": "one", "raw": "uh alpha", "expected": "Alpha."},
            {**base, "id": "two", "raw": "um beta", "expected": "Beta."},
        ]
        union, flags = builder.build_components(rows, {
            "token_3gram_jaccard": 0.0,
            "character_5gram_jaccard": 0.0,
            "normalized_edit_similarity": 0.0,
        })
        self.assertEqual(union.find(0), union.find(1))
        self.assertEqual([], flags)

    def test_primary_bucket_is_exclusive_and_disfl_precedes_protected(self) -> None:
        row = {
            "categories": ["self_correction", "question", "must_not_answer", "numbers"],
            "risk_tags": ["superseded_fact", "dictated_instruction", "number"],
            "source_ref": "disfl_qa:train.json:q1",
        }
        self.assertEqual("disfl_qa_correction", builder.bucket(row))

    def test_edit_operation_precedes_adversarial_cross_cutting_label(self) -> None:
        row = {
            "categories": ["self_correction", "adversarial_instruction", "must_not_answer"],
            "risk_tags": ["superseded_fact", "adversarial_content"],
            "source_ref": "human:test",
        }
        self.assertEqual("correction_or_false_start", builder.bucket(row))
        self.assertEqual(1.0, builder.cross_cutting([row])["adversarial_instruction"])
        clean_adversarial = {
            "categories": ["already_clean", "adversarial_instruction", "must_not_answer"],
            "risk_tags": ["adversarial_content"], "source_ref": "human:adversarial",
        }
        self.assertEqual("adversarial_must_not_answer", builder.bucket(clean_adversarial))

    def test_broader_product_operations_have_dedicated_primary_buckets(self) -> None:
        base = {"risk_tags": [], "source_ref": "sotto:train.parquet:one"}
        self.assertEqual("grammar_rewrite", builder.bucket({**base, "categories": ["grammar_rewrite"]}))
        self.assertEqual("asr_correction", builder.bucket({**base, "categories": ["asr_correction"]}))
        self.assertEqual("mixed_or_discourse", builder.bucket({**base, "categories": ["discourse_marker"]}))

    def test_pilot_primary_quotas_sum_exactly_for_train_and_dev(self) -> None:
        config = json.loads((REPO / "training/config/pilot-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(config["train_records"], sum(config["train_primary_buckets"].values()))
        dev = [
            round(count * config["dev_records"] / config["train_records"])
            for count in config["train_primary_buckets"].values()
        ]
        self.assertEqual(config["dev_records"], sum(dev))
        self.assertIn("high_stakes", config["minimum_cross_cutting_fraction"])

    def test_quota_selection_satisfies_cross_cutting_minimums_deterministically(self) -> None:
        rows = []
        for index in range(4):
            rows.append({
                "id": f"correction-{index}", "categories": ["self_correction"] + (
                    ["adversarial_instruction"] if index < 2 else []
                ),
                "risk_tags": ["superseded_fact"], "source_ref": f"human:corr:{index}",
            })
            rows.append({
                "id": f"clean-{index}", "categories": ["already_clean"] + (
                    ["unicode"] if index < 2 else []
                ),
                "risk_tags": ["unicode_literal"] if index < 2 else [],
                "source_ref": f"human:clean:{index}",
            })
        quotas = {"correction_or_false_start": 2, "clean_no_op": 2}
        minimums = {"adversarial_instruction": 0.5, "unicode_or_multilingual": 0.5}
        chosen, _ = builder.choose(rows, quotas, 23, "train", minimums)
        self.assertEqual(2, sum(builder.bucket(row) == "correction_or_false_start" for row in chosen))
        self.assertEqual(2, sum(builder.bucket(row) == "clean_no_op" for row in chosen))
        self.assertEqual(0.5, builder.cross_cutting(chosen)["adversarial_instruction"])
        self.assertEqual(0.5, builder.cross_cutting(chosen)["unicode_or_multilingual"])
        repeated, _ = builder.choose(rows, quotas, 23, "train", minimums)
        self.assertEqual([row["id"] for row in chosen], [row["id"] for row in repeated])

    def test_preselection_reserves_rare_cross_cutting_candidates(self) -> None:
        rows = [{
            "id": f"plain-{index}", "categories": ["already_clean"], "risk_tags": [],
            "source_ref": f"human:plain:{index}",
        } for index in range(100)]
        rare_ids = set()
        for index in range(5):
            row_id = f"unicode-{index}"
            rare_ids.add(row_id)
            rows.append({
                "id": row_id, "categories": ["already_clean", "unicode"],
                "risk_tags": ["unicode_literal"], "source_ref": f"human:unicode:{index}",
            })
        config = {
            "seed": 23, "candidate_pool_multiplier": 4, "dev_records": 1, "train_records": 10,
            "train_primary_buckets": {"clean_no_op": 10},
            "minimum_cross_cutting_fraction": {"unicode_or_multilingual": 0.1},
        }
        selected, _ = builder.preselect_candidate_pool(rows, config)
        self.assertTrue(rare_ids <= {row["id"] for row in selected})

    def test_supplement_generator_is_pending_deterministic_and_schema_valid(self) -> None:
        config = json.loads((REPO / "training/config/supplement-v1.json").read_text(encoding="utf-8"))
        rows = (
            supplement.adversarial_records(config)
            + supplement.paragraph_records(config)
            + supplement.unicode_records(config)
        )
        self.assertEqual(2800, len(rows))
        self.assertTrue(all(row["review"] == {"status": "pending", "reviewers": 0} for row in rows))
        self.assertGreaterEqual(sum(builder.bucket(row) == "explicit_paragraph_formatting" for row in rows), 55)
        self.assertGreaterEqual(sum("adversarial_instruction" in row["categories"] for row in rows), 440)
        self.assertGreaterEqual(sum("unicode" in row["categories"] for row in rows), 550)
        for row in rows:
            self.assertFalse(common.lexical_additions(row["raw"], row["expected"]))
            self.assertTrue(all(anchor in row["expected"] for anchor in row["must_preserve"]))
            self.assertTrue(all(anchor in row["raw"] and anchor not in row["expected"] for anchor in row["must_remove"]))
        self.assertEqual(
            [row["id"] for row in rows],
            [row["id"] for row in (
                supplement.adversarial_records(config)
                + supplement.paragraph_records(config)
                + supplement.unicode_records(config)
            )],
        )

    def test_review_tool_never_auto_approves_and_applies_human_decision(self) -> None:
        records = [{"id": "one", "split": "train", "review": {"status": "pending", "reviewers": 0}}]
        untouched = reviewer.apply_reviews(records, [])
        self.assertEqual(0, len(untouched["approved"]))
        self.assertEqual("pending", untouched["pending"][0]["review"]["status"])
        decisions = [{"id": "one", "decision": "approved", "reviewer_ref": "reviewer-a", "reviewed_at": "2026-08-17"}]
        reviewed = reviewer.apply_reviews(records, decisions)
        self.assertEqual("approved", reviewed["approved"][0]["review"]["status"])
        self.assertEqual(["reviewer-a"], reviewed["approved"][0]["review"]["reviewer_refs"])

    def test_review_tool_rejects_conflicts_and_blind_records(self) -> None:
        record = {"id": "one", "split": "train", "review": {"status": "pending", "reviewers": 0}}
        decisions = [
            {"id": "one", "decision": "approved", "reviewer_ref": "reviewer-a", "reviewed_at": "2026-08-17"},
            {"id": "one", "decision": "rejected", "reviewer_ref": "reviewer-b", "reviewed_at": "2026-08-17"},
        ]
        reviewed = reviewer.apply_reviews([record], decisions)
        self.assertEqual("pending", reviewed["pending"][0]["review"]["status"])
        with self.assertRaises(RuntimeError):
            reviewer.apply_reviews([{**record, "split": "blind"}], [])

    def test_training_run_controls_cannot_confuse_smoke_and_pilot(self) -> None:
        trainer.validate_run_controls("pilot", -1, None)
        trainer.validate_run_controls("resume_smoke", 4, 2)
        with self.assertRaises(RuntimeError):
            trainer.validate_run_controls("pilot", 4, None)
        with self.assertRaises(RuntimeError):
            trainer.validate_run_controls("resume_smoke", 4, 4)

    def test_assistant_only_encoding_masks_the_entire_prompt(self) -> None:
        class Tokenizer:
            def apply_chat_template(self, messages, *, tokenize, add_generation_prompt, **kwargs):
                self.assertions = (tokenize, kwargs)
                if add_generation_prompt:
                    return [1, 2, 3]
                return [1, 2, 3, 40, 41]

        encoded = trainer.encode_record(
            Tokenizer(), "instruction", {"id": "row", "raw": "raw", "expected": "expected"},
            8, {"enable_thinking": False},
        )
        self.assertEqual([-100, -100, -100, 40, 41], encoded["labels"])
        with self.assertRaises(RuntimeError):
            trainer.encode_record(
                Tokenizer(), "instruction", {"id": "row", "raw": "raw", "expected": "expected"},
                4, {"enable_thinking": False},
            )

    def test_inference_bound_matches_android_formula(self) -> None:
        self.assertEqual(16, inference.max_output_tokens("a"))
        self.assertEqual(18, inference.max_output_tokens("x" * 30))
        self.assertEqual(96, inference.max_output_tokens("x" * 1000))

    def test_authoring_tools_refuse_blind_inputs(self) -> None:
        with self.assertRaises(RuntimeError):
            inference.reject_blind_input(Path("blind-v2.jsonl"), [])
        with self.assertRaises(RuntimeError):
            dev_scorer.reject_blind(Path("dev.jsonl"), [{"split": "blind"}])

    def test_dev_scorer_measures_raw_removal_and_preservation(self) -> None:
        case = {
            "id": "one", "raw": "send Monday no send Tuesday", "expected": "Send Tuesday.",
            "categories": ["self_correction"], "must_preserve": ["Tuesday"],
            "must_remove": ["Monday", "no"],
        }
        result = {
            "case_id": "one", "raw": case["raw"], "expected": case["expected"],
            "model_text": "Send Tuesday.", "hit_output_token_limit": False,
            "guardrail_would_fallback": False, "timings": {"ttft_ms": 1.0, "total_ms": 2.0},
        }
        report = dev_scorer.score([case], [result])
        self.assertEqual(1.0, report["raw_exact_match"]["rate"])
        self.assertEqual(1.0, report["must_preserve_anchors"]["rate"])
        self.assertEqual(1.0, report["correction_rows"]["rate"])

    def test_gate_a_rejects_pending_selected_rows(self) -> None:
        row = {
            "id": "one", "split": "train", "categories": ["self_correction"],
            "risk_tags": [], "source_ref": "human:test",
            "review": {"status": "pending", "reviewers": 0},
        }
        config = {
            "train_records": 1, "dev_records": 0,
            "train_primary_buckets": {"correction_or_false_start": 1},
            "minimum_cross_cutting_fraction": {},
        }
        with self.assertRaises(RuntimeError):
            gate_a.audit_rows([row], [], config)

    def test_gate_a_rejects_source_native_holdout_rows(self) -> None:
        config = {"sources": [{
            "id": "disfl_qa", "candidate_include": ["train.json"],
            "holdout_include": ["dev.json", "test.json"],
        }]}
        row = {"id": "one", "source": "public_corpus", "source_ref": "disfl_qa:dev.json:question"}
        with self.assertRaises(RuntimeError):
            gate_a.validate_source_native_holdouts([row], config)
        row["source_ref"] = "disfl_qa:train.json:question"
        self.assertEqual(0, gate_a.validate_source_native_holdouts([row], config)["source_native_holdout_rows"])

    def test_gate_a_requires_committed_authoring_artifacts_for_derived_rows(self) -> None:
        row = {"source": "deterministic_generated"}
        with self.assertRaises(RuntimeError):
            gate_a.validate_authoring_artifacts([row], [])
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory) / "generator.json"
            outside.write_text("{}\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                gate_a.validate_authoring_artifacts([row], [outside])

    def test_monitor_reports_log_deltas_without_mutating_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.jsonl"
            path.write_text('{"step":1}\n', encoding="utf-8")
            first = monitor.file_state(path, None)
            self.assertEqual(first["bytes"], first["new_bytes"])
            path.write_text('{"step":1}\n{"step":2}\n', encoding="utf-8")
            second = monitor.file_state(path, first["bytes"])
            self.assertGreater(second["new_bytes"], 0)
            self.assertEqual(2, monitor.last_jsonl(path)["step"])

    def test_interactive_review_resume_keys_are_strict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "decisions.jsonl"
            ledger.write_text(
                json.dumps({"id": "one", "reviewer_ref": "reviewer-a"}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual({("one", "reviewer-a")}, interactive_reviewer.existing_keys(ledger))
            with ledger.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"id": "one", "reviewer_ref": "reviewer-a"}) + "\n")
            with self.assertRaises(RuntimeError):
                interactive_reviewer.existing_keys(ledger)

    def test_interactive_reviewer_displays_lexical_and_provenance_evidence(self) -> None:
        row = {
            "id": "one", "split": "train", "source": "public_corpus",
            "source_ref": "fixture:train:one", "license": "fixture-license",
            "family_id": "family-one", "template_id": "template-one",
            "categories": ["grammar_rewrite"], "risk_tags": ["lexical_addition"],
            "must_preserve": ["value"], "must_remove": ["old"],
            "allowed_additions": ["new"], "raw": "old value", "expected": "New value.",
        }
        output = io.StringIO()
        with redirect_stdout(output):
            interactive_reviewer.render(row, 1, 1)
        rendered = output.getvalue()
        for expected in (
            "fixture:train:one", "fixture-license", "family-one", "template-one",
            'allowed additions: ["new"]',
        ):
            self.assertIn(expected, rendered)

    def test_gate_a_cli_emits_sanitized_v2_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "sources" / "fixture"
            source_root.mkdir(parents=True)
            payload = source_root / "README.md"
            payload.write_text("fixture license evidence\n", encoding="utf-8")
            source_config = root / "sources.json"
            source_config.write_text(json.dumps({
                "manifest_version": "test-source-config-v1",
                "sources": [{
                    "id": "fixture", "kind": "github_archive", "repository": "example/fixture",
                    "url": "https://example.invalid/fixture", "revision": "a" * 40,
                    "license": "fixture-license", "include": ["README.md"],
                    "candidate_include": ["train.jsonl"], "holdout_include": ["dev.jsonl"],
                }],
            }, sort_keys=True), encoding="utf-8")
            source_manifest = root / "source-manifest.json"
            source_manifest.write_text(json.dumps({
                "manifest_version": "cleanup-source-manifest-v1",
                "config_sha256": hashlib.sha256(source_config.read_bytes()).hexdigest(),
                "sources": [{
                    "id": "fixture", "url": "https://example.invalid/fixture",
                    "revision": "a" * 40, "license": "fixture-license",
                    "files": [{
                        "path": "README.md", "bytes": payload.stat().st_size,
                        "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                    }],
                }],
            }, sort_keys=True), encoding="utf-8")
            policy = REPO / "docs/training/ANNOTATION_POLICY_V2.md"
            review_attestation = root / "review-attestation.json"
            review_attestation.write_text(json.dumps({
                "attestation_version": "cleanup-pilot-review-attestation-v1",
                "policy_sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
                "review_completed_at": "2026-08-17", "reviewer_refs": ["reviewer-fixture"],
                "statements": {name: True for name in gate_a.ATTESTATION_STATEMENTS},
            }, sort_keys=True), encoding="utf-8")
            license_attestation = root / "license-attestation.json"
            license_attestation.write_text(json.dumps({
                "attestation_version": "cleanup-source-license-attestation-v1",
                "source_manifest_sha256": hashlib.sha256(source_manifest.read_bytes()).hexdigest(),
                "sources": [{
                    "id": "fixture", "license": "fixture-license", "auditor_ref": "reviewer-fixture",
                    "audited_at": "2026-08-17", "evidence_files": ["README.md"],
                    "statements": {"terms_reviewed": True, "attribution_recorded": True, "research_training_permitted": True},
                }],
            }, sort_keys=True), encoding="utf-8")
            pilot_config = root / "pilot.json"
            pilot_config.write_text(json.dumps({
                "train_records": 1, "dev_records": 1, "train_primary_buckets": {"correction_or_false_start": 1},
                "minimum_cross_cutting_fraction": {},
                "near_duplicate": {"token_3gram_jaccard": 0.999, "character_5gram_jaccard": 0.999, "normalized_edit_similarity": 0.999},
            }), encoding="utf-8")
            rows = []
            for split, suffix in (("train", "alpha"), ("dev", "beta")):
                rows.append({
                    "id": f"fixture-{suffix}", "raw": f"um unique {suffix}", "expected": f"Unique {suffix}.",
                    "categories": ["self_correction"], "must_preserve": [], "must_remove": ["um"],
                    "risk_tags": [], "source": "human_authored", "family_id": f"family-{suffix}",
                    "template_id": f"template-{suffix}", "split": split,
                    "review": {"status": "approved", "reviewers": 1, "reviewed_at": "2026-08-17", "reviewer_refs": ["reviewer-fixture"]},
                    "license": "fixture-license", "generator_version": "fixture-v1",
                })
            train, dev = root / "train.jsonl", root / "dev.jsonl"
            train.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
            dev.write_text(json.dumps(rows[1]) + "\n", encoding="utf-8")
            local_manifest, report = root / "local-manifest.json", root / "gate-report.json"
            result = subprocess.run([
                sys.executable, str(TRAINING_SCRIPTS / "gate_a_cleanup.py"),
                "--train", str(train), "--dev", str(dev),
                "--source-manifest", str(source_manifest), "--source-root", str(root / "sources"),
                "--review-attestation", str(review_attestation), "--license-attestation", str(license_attestation),
                "--local-manifest", str(local_manifest), "--report", str(report),
                "--pilot-config", str(pilot_config), "--source-config", str(source_config),
                "--annotation-policy", str(policy),
            ], cwd=REPO, text=True, capture_output=True)
            self.assertEqual(0, result.returncode, result.stderr)
            gate_report = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual("pass", gate_report["status"])
            self.assertEqual("cleanup-training-record-v2", gate_report["record_schema_version"])
            self.assertEqual(0, gate_report["source_subset_audit"]["source_native_holdout_rows"])
            rendered = report.read_text(encoding="utf-8")
            self.assertNotIn(str(train), rendered)
            manifest = json.loads(local_manifest.read_text(encoding="utf-8"))
            self.assertEqual("cleanup-training-record-v2", manifest["record_schema_version"])


if __name__ == "__main__":
    unittest.main()
