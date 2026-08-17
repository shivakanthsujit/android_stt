from __future__ import annotations

import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "run-cleanup-openai.py"
SPEC = importlib.util.spec_from_file_location("run_cleanup_openai", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)

SCORER_SCRIPT = Path(__file__).resolve().parents[1] / "score-cleanup-results.py"
SCORER_SPEC = importlib.util.spec_from_file_location("score_cleanup_results", SCORER_SCRIPT)
assert SCORER_SPEC is not None and SCORER_SPEC.loader is not None
scorer = importlib.util.module_from_spec(SCORER_SPEC)
sys.modules[SCORER_SPEC.name] = scorer
SCORER_SPEC.loader.exec_module(scorer)


class _FakeResponse:
    def __init__(self, body: bytes):
        self.body = BytesIO(body)

    def read(self, size: int = -1) -> bytes:
        return self.body.read(size)

    def __iter__(self):
        return iter(self.body)

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *unused: object) -> None:
        return None


def _write_case(path: Path, raw: str = "uh keep this") -> None:
    path.write_text(
        json.dumps(
            {
                "id": "cleanup-test",
                "raw": raw,
                "expected": "Keep this.",
                "categories": ["fillers"],
                "must_preserve": ["Keep this"],
            }
        )
        + "\n",
        encoding="utf-8",
    )


class RunnerUnitTest(unittest.TestCase):
    def test_cleanup_instruction_v2_uses_training_prompt_and_exact_wrapper(self) -> None:
        self.assertEqual(
            runner.CLEANUP_INSTRUCTION_V2.read_text(encoding="utf-8").strip(),
            runner.system_prompt("cleanup_instruction_v2"),
        )
        self.assertEqual(
            "Transcript:\nuh keep this",
            runner.user_message("cleanup_instruction_v2", "uh keep this"),
        )

    def test_voiceink_variant_uses_pinned_training_prompt_and_exact_wrapper(self) -> None:
        prompt = runner.system_prompt("voiceink_task_tuned")
        self.assertEqual(
            "238d74aeeced93e6f092edd1990292de7701ef726b0db5ea06b80b412b51e73a",
            hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        )
        self.assertTrue(prompt.startswith("<SYSTEM_INSTRUCTIONS>\n"))
        self.assertIn("You are a TRANSCRIPTION ENHANCER.", prompt)
        self.assertTrue(prompt.endswith("Nothing else.\n</SYSTEM_INSTRUCTIONS>"))
        self.assertEqual(
            "<TRANSCRIPT>\nuh keep this\n</TRANSCRIPT>",
            runner.user_message("voiceink_task_tuned", "uh keep this"),
        )

    def test_output_bound_matches_android_formula_and_counts_code_points(self) -> None:
        self.assertEqual(16, runner.max_output_tokens("a"))
        self.assertEqual(18, runner.max_output_tokens("x" * 30))
        self.assertEqual(16, runner.max_output_tokens("🧭" * 3))
        self.assertEqual(96, runner.max_output_tokens("x" * 1_000))

    def test_nonstream_run_writes_scorer_compatible_record(self) -> None:
        response = json.dumps(
            {
                "model": "served-model",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Keep this."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 41, "completion_tokens": 3},
            }
        ).encode()
        captured: dict[str, Any] = {}

        def urlopen(request: Any, timeout: float) -> _FakeResponse:
            captured["url"] = request.full_url
            captured["json"] = json.loads(request.data)
            captured["timeout"] = timeout
            return _FakeResponse(response)

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runner.urllib.request, "urlopen", side_effect=urlopen
        ):
            root = Path(directory)
            cases = root / "cases.jsonl"
            output = root / "results.jsonl"
            _write_case(cases)
            exit_code = runner.main(
                [
                    "--model",
                    "candidate-model",
                    "--quantization",
                    "Q4_K_M",
                    "--base-url",
                    "http://127.0.0.1:8080/v1",
                    "--cases",
                    str(cases),
                    "--output",
                    str(output),
                    "--no-stream",
                ]
            )

            self.assertEqual(0, exit_code)
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("cleanup-test", record["case_id"])
            self.assertEqual("Keep this.", record["model_text"])
            self.assertEqual("Keep this.", record["selected_text"])
            self.assertFalse(record["used_fallback"])
            self.assertEqual("stop", record["finish_reason"])
            self.assertEqual(3, record["completion_tokens"])
            self.assertIsNone(record["timings"]["ttft_ms"])
            self.assertGreaterEqual(record["timings"]["total_ms"], 0)
            parsed_records = scorer.load_result_records(output)
            self.assertEqual("cleanup-test", parsed_records[0].case_id)

            self.assertEqual(
                "http://127.0.0.1:8080/v1/chat/completions", captured["url"]
            )
            request = captured["json"]
            self.assertEqual("candidate-model", request["model"])
            self.assertEqual(0.1, request["temperature"])
            self.assertEqual(23, request["seed"])
            self.assertFalse(request["stream"])
            self.assertEqual("system", request["messages"][0]["role"])
            self.assertEqual(runner.BASELINE_SYSTEM_PROMPT, request["messages"][0]["content"])
            self.assertEqual("Dictation:\nuh keep this", request["messages"][1]["content"])

    def test_stream_response_joins_chunks_and_reads_final_usage(self) -> None:
        events = [
            {
                "choices": [
                    {"delta": {"content": "Keep "}, "finish_reason": None}
                ]
            },
            {
                "choices": [
                    {"delta": {"content": "this."}, "finish_reason": "stop"}
                ]
            },
            {
                "choices": [],
                "usage": {"prompt_tokens": 40, "completion_tokens": 3},
            },
        ]
        body = b"".join(
            f"data: {json.dumps(event)}\n\n".encode() for event in events
        ) + b"data: [DONE]\n\n"
        captured: dict[str, Any] = {}

        def urlopen(request: Any, timeout: float) -> _FakeResponse:
            captured["json"] = json.loads(request.data)
            return _FakeResponse(body)

        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            runner.urllib.request, "urlopen", side_effect=urlopen
        ):
            root = Path(directory)
            cases = root / "cases.jsonl"
            output = root / "results.jsonl"
            _write_case(cases)
            runner.main(
                [
                    "--model",
                    "candidate-model",
                    "--base-url",
                    "http://127.0.0.1:8080/v1",
                    "--cases",
                    str(cases),
                    "--output",
                    str(output),
                ]
            )
            record = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual("Keep this.", record["model_text"])
            self.assertEqual(40, record["prompt_tokens"])
            self.assertEqual(3, record["completion_tokens"])
            self.assertGreaterEqual(record["timings"]["ttft_ms"], 0)
            self.assertTrue(captured["json"]["stream"])

    def test_limit_finish_reason_falls_back_to_raw(self) -> None:
        case = runner.EvaluationCase(
            "case", "original words", "Original words.", (), ()
        )
        chat_result = runner.ChatResult(
            "A partial", "length", None, None, 2.0, 4.0, 1
        )
        record = runner.make_result_record(
            evaluation_case=case,
            chat_result=chat_result,
            model="model",
            quantization="Q4",
            prompt_variant="baseline_rules",
            output_tokens=16,
            temperature=0.1,
        )
        self.assertTrue(record["used_fallback"])
        self.assertTrue(record["hit_output_token_limit"])
        self.assertEqual("original words", record["selected_text"])

    def test_lexical_guardrail_falls_back_to_raw_with_reason(self) -> None:
        case = runner.EvaluationCase(
            "case",
            "The benchmark completed in 237 milliseconds.",
            "The benchmark completed in 237 milliseconds.",
            (),
            (),
        )
        chat_result = runner.ChatResult(
            "The benchmark finished in 237 milliseconds.",
            "stop",
            None,
            None,
            2.0,
            4.0,
            1,
        )
        record = runner.make_result_record(
            evaluation_case=case,
            chat_result=chat_result,
            model="model",
            quantization="Q4",
            prompt_variant="baseline_rules",
            output_tokens=16,
            temperature=0.1,
        )
        self.assertTrue(record["used_fallback"])
        self.assertEqual(case.raw, record["selected_text"])
        self.assertEqual(
            "Model introduced new lexical content: finished",
            record["fallback_reason"],
        )

    def test_duplicate_case_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            row = {
                "id": "same",
                "raw": "text",
                "expected": "Text.",
                "categories": [],
                "must_preserve": [],
            }
            path.write_text(
                json.dumps(row) + "\n" + json.dumps(row) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(runner.RunnerError, "duplicate case id"):
                runner.load_cases(path)

    def test_hash_shards_are_disjoint_complete_and_order_independent(self) -> None:
        case_ids = ["zeta", "alpha", "middle", "case-004", "case-005"]
        assignments = {
            case_id: runner.stable_shard_index(case_id, 3) for case_id in case_ids
        }
        self.assertEqual(
            assignments,
            {
                case_id: runner.stable_shard_index(case_id, 3)
                for case_id in reversed(case_ids)
            },
        )
        assigned = [
            case_id
            for shard_index in range(3)
            for case_id in case_ids
            if assignments[case_id] == shard_index
        ]
        self.assertCountEqual(case_ids, assigned)
        self.assertEqual(len(case_ids), len(set(assigned)))

    def test_raw_scoring_preserves_parallel_guardrail_evidence(self) -> None:
        case = runner.EvaluationCase(
            "case",
            "The benchmark completed in 237 milliseconds.",
            "The benchmark completed in 237 milliseconds.",
            (),
            (),
        )
        chat_result = runner.ChatResult(
            "The benchmark finished in 237 milliseconds.",
            "stop",
            None,
            None,
            2.0,
            4.0,
            1,
        )
        record = runner.make_result_record(
            evaluation_case=case,
            chat_result=chat_result,
            model="model",
            quantization="bf16-lora",
            prompt_variant="cleanup_instruction_v2",
            output_tokens=16,
            temperature=0.0,
            raw_scoring=True,
        )
        self.assertEqual(chat_result.text, record["selected_text"])
        self.assertFalse(record["used_fallback"])
        self.assertTrue(record["guardrail_would_fallback"])
        self.assertEqual(case.raw, record["guardrail_selected_text"])
        self.assertTrue(record["raw_model_output_is_selected_for_scoring"])

    def test_resume_appends_only_after_valid_completed_prefix(self) -> None:
        response = json.dumps(
            {
                "choices": [
                    {
                        "message": {"content": "Keep this."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"completion_tokens": 3},
            }
        ).encode()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = root / "cases.jsonl"
            output = root / "results.jsonl"
            rows = [
                {
                    "id": case_id,
                    "raw": "uh keep this",
                    "expected": "Keep this.",
                    "categories": ["fillers"],
                    "must_preserve": ["Keep this"],
                }
                for case_id in ("first", "second")
            ]
            cases.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            with mock.patch.object(
                runner.urllib.request,
                "urlopen",
                side_effect=[_FakeResponse(response), urllib.error.URLError("down")],
            ), self.assertRaises(SystemExit):
                runner.main(
                    [
                        "--model", "model", "--cases", str(cases), "--output", str(output),
                        "--no-stream", "--raw-scoring", "--temperature", "0",
                        "--prompt-variant", "cleanup_instruction_v2",
                    ]
                )
            self.assertEqual(1, len(output.read_text(encoding="utf-8").splitlines()))
            with mock.patch.object(
                runner.urllib.request, "urlopen", return_value=_FakeResponse(response)
            ) as urlopen:
                self.assertEqual(
                    0,
                    runner.main(
                        [
                            "--model", "model", "--cases", str(cases), "--output", str(output),
                            "--no-stream", "--raw-scoring", "--temperature", "0",
                            "--prompt-variant", "cleanup_instruction_v2", "--resume",
                        ]
                    ),
                )
            self.assertEqual(1, urlopen.call_count)
            completed = [
                json.loads(line)["case_id"]
                for line in output.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(["first", "second"], completed)


if __name__ == "__main__":
    unittest.main()
