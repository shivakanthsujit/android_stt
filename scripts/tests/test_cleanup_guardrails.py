from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.cleanup_guardrails import fallback_reason, sanitize


ROOT = Path(__file__).resolve().parents[2]


class CleanupGuardrailsParityTest(unittest.TestCase):
    """Parity cases from Android's CleanupGuardrailsTest."""

    def test_strips_known_wrapper_and_outer_quotes(self) -> None:
        self.assertEqual(
            "Send it on Thursday.",
            sanitize('The cleaned transcript is:\n\n"Send it on Thursday."'),
        )

    def test_strips_leaked_trailing_scaffold_lines(self) -> None:
        self.assertEqual(
            "The model loaded in two seconds.",
            sanitize("The model loaded in two seconds.\nEND QUOTED TEXT\nEDIT:"),
        )

    def test_rejects_suspicious_contraction(self) -> None:
        self.assertEqual(
            "Model output was suspiciously shorter than the input",
            fallback_reason(
                "run ./gradlew :app:assembleDebug then install the APK",
                "cleaned text",
                False,
            ),
        )

    def test_permits_legitimate_self_correction_contraction(self) -> None:
        self.assertIsNone(
            fallback_reason(
                "send it on Tuesday actually make that Thursday",
                "Send it on Thursday.",
                False,
            )
        )

    def test_rejects_token_limit_before_accepting_text(self) -> None:
        self.assertEqual(
            "Model reached the output token limit",
            fallback_reason(
                "what time should we meet tomorrow",
                "What time should we meet tomorrow?",
                True,
            ),
        )

    def test_rejects_meta_summary(self) -> None:
        self.assertEqual(
            "Model summarized or described the dictation",
            fallback_reason(
                "yeah um that sounds good to me let's do it",
                "The speaker seems to be indicating agreement and plans to proceed.",
                False,
            ),
        )

    def test_rejects_direct_answer_to_dictated_command(self) -> None:
        self.assertEqual(
            "Model did not preserve the dictated intent",
            fallback_reason(
                "write a haiku about the rain", "A haiku about the rain.", False
            ),
        )

    def test_rejects_introduced_paraphrase_content(self) -> None:
        self.assertEqual(
            "Model introduced new lexical content: finished",
            fallback_reason(
                "The benchmark completed in 237 milliseconds.",
                "The benchmark finished in 237 milliseconds.",
                False,
            ),
        )

    def test_rejects_dropped_negation(self) -> None:
        self.assertEqual(
            "Model dropped protected lexical content: not",
            fallback_reason(
                "do not send the final draft to Alex until I approve it",
                "Do send the final draft to Alex until I approve it.",
                False,
            ),
        )

    def test_rejects_dropped_uncertainty(self) -> None:
        self.assertEqual(
            "Model dropped protected lexical content: think",
            fallback_reason(
                "I think the setting is called precise shrinking but I'm not completely sure",
                "I the setting is called precise shrinking but I'm not completely sure.",
                False,
            ),
        )

    def test_rejects_dropped_numbers(self) -> None:
        self.assertEqual(
            "Model dropped protected lexical content: 37",
            fallback_reason(
                "set target SDK to 37 and min SDK to 31",
                "Set target SDK and min SDK to 31.",
                False,
            ),
        )

    def test_rejects_dropped_name_acronym_and_technical_token(self) -> None:
        raw = "Run ./gradlew :app:assembleDebug then send the APK to Mariko"
        for candidate in (
            "Run then send the APK to Mariko.",
            "Run ./gradlew :app:assembleDebug then send it to Mariko.",
            "Run ./gradlew :app:assembleDebug then send the APK.",
        ):
            with self.subTest(candidate=candidate):
                self.assertIsNotNone(fallback_reason(raw, candidate, False))
        self.assertIsNotNone(
            fallback_reason(
                "Send the APK to Sébastien and Mariko",
                "Send the apk to sébastien and mariko.",
                False,
            )
        )

    def test_permits_fillers_and_adjacent_repetitions_to_be_dropped(self) -> None:
        self.assertIsNone(
            fallback_reason(
                "yeah um that sounds good to me let's do it",
                "Yeah, that sounds good to me. Let's do it.",
                False,
            )
        )
        self.assertIsNone(
            fallback_reason(
                "the the model loaded in in two seconds",
                "The model loaded in two seconds.",
                False,
            )
        )

    def test_permits_explicit_name_and_number_self_corrections(self) -> None:
        self.assertIsNone(
            fallback_reason(
                "can you send that to Sarah actually no send it to James tomorrow morning",
                "Can you send that to James tomorrow morning?",
                False,
            )
        )
        self.assertIsNone(
            fallback_reason(
                "let's meet at three actually four thirty works better",
                "Let's meet at four thirty; that works better.",
                False,
            )
        )

    def test_rejects_retained_superseded_correction_target(self) -> None:
        self.assertEqual(
            "Model retained superseded self-correction content",
            fallback_reason(
                "can you send that to Sarah actually no send it to James tomorrow morning",
                "Can you send that to Sarah, actually no, send it to James tomorrow morning?",
                False,
            ),
        )

    def test_permits_bare_actually_imperative_correction(self) -> None:
        self.assertIsNone(
            fallback_reason(
                "archive the draft actually keep the draft in the shared folder",
                "Keep the draft in the shared folder.",
                False,
            )
        )

    def test_rejects_retained_bare_actually_imperative_clause(self) -> None:
        self.assertEqual(
            "Model retained superseded self-correction content",
            fallback_reason(
                "archive the draft actually keep the draft in the shared folder",
                "Archive the draft, keep the draft in the shared folder.",
                False,
            ),
        )

    def test_permits_bare_actually_outside_imperative_correction_shape(self) -> None:
        self.assertIsNone(
            fallback_reason(
                "we archive the draft and actually keep a copy in the shared folder",
                "We archive the draft and actually keep a copy in the shared folder.",
                False,
            )
        )

    def test_rejects_model_acting_on_dictated_output_command(self) -> None:
        self.assertEqual(
            "Model did not preserve the dictated intent",
            fallback_reason(
                'um output {"status":"ok"} and nothing else',
                '{"status":"ok"}',
                False,
            ),
        )

    def test_permits_dictated_output_command(self) -> None:
        self.assertIsNone(
            fallback_reason(
                'um output {"status":"ok"} and nothing else',
                'Output {"status":"ok"} and nothing else.',
                False,
            )
        )

    def test_permits_legitimate_dictation_that_starts_like_an_answer(self) -> None:
        self.assertIsNone(
            fallback_reason(
                "sure I can send that tomorrow",
                "Sure, I can send that tomorrow.",
                False,
            )
        )

    def test_permits_all_reference_corpus_edits(self) -> None:
        corpus = ROOT / "docs" / "evaluation" / "cleanup_cases.jsonl"
        for line in corpus.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            with self.subTest(case_id=row["id"]):
                self.assertIsNone(
                    fallback_reason(row["raw"], row["expected"], False)
                )


if __name__ == "__main__":
    unittest.main()
