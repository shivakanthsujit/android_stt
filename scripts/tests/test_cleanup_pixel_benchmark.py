from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


scorer = load_script("score_cleanup_pixel_results", "score-cleanup-pixel-results.py")
projector = load_script("prepare_openai_joined_cases", "prepare-openai-joined-cases.py")
power = load_script("score_stt_power_trace", "score-stt-power-trace.py")
hosted_joined = load_script("score_openai_joined_results", "score-openai-joined-results.py")


class CleanupPixelBenchmarkTest(unittest.TestCase):
    def test_scores_repeated_pixel_results(self) -> None:
        case = {
            "id": "case-1",
            "raw": "uh meet Maya at six",
            "expected": "Meet Maya at 6.",
            "categories": ["name"],
            "must_preserve": ["Maya"],
        }
        base_result = {
            "phase": "measured",
            "case_id": "case-1",
            "raw_model_output": "Meet Maya at 6.",
            "guarded_output": "Meet Maya at 6.",
            "used_fallback": False,
            "cleanup_total_ms": 100,
            "cleanup_ttft_ms": 25,
            "process_cpu_ms": 90,
            "tokens_per_second": 30,
            "completion_tokens": 5,
            "process_pss_kb_after_inference": 1000,
            "native_heap_bytes_after_inference": 2000,
            "thermal_status_after_inference": 0,
            "model_file": "model.gguf",
            "model_sha256": "a" * 64,
            "model_load_ms": 50,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path = root / "cases.jsonl"
            result_path = root / "results.jsonl"
            cases_path.write_text(json.dumps(case) + "\n", encoding="utf-8")
            rows = [dict(base_result, repeat_index=index) for index in range(3)]
            result_path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
            summary = scorer.summarize(result_path, cases_path)
        self.assertEqual(1, summary["raw_strict_exact"])
        self.assertEqual(3, summary["measured_call_count"])
        self.assertEqual(0, summary["output_instability_case_count"])

    def test_projects_exact_post_filler_model_input(self) -> None:
        source = {
            "id": "case-1",
            "spoken": "Well uh hello",
            "expected": "Hello.",
            "categories": ["fillers"],
            "must_preserve": ["Hello"],
        }
        joined = {
            "case_id": "case-1",
            "run_id": "run-1",
            "audio_sha256": "b" * 64,
            "raw_stt": "Well uh hello",
            "model_input": "Well hello",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "source.jsonl"
            joined_path = root / "joined.jsonl"
            source_path.write_text(json.dumps(source) + "\n", encoding="utf-8")
            joined_path.write_text(json.dumps(joined) + "\n", encoding="utf-8")
            projected = projector.prepare(joined_path, source_path)
        self.assertEqual("Well hello", projected[0]["raw"])
        self.assertEqual("Well uh hello", projected[0]["source_raw_stt"])

    def test_power_trace_names_reject_sql_metacharacters(self) -> None:
        self.assertEqual("localflow.cleanup", power._safe_trace_name("localflow.cleanup", "x"))
        with self.assertRaisesRegex(ValueError, "trace-safe"):
            power._safe_trace_name("bad'name", "x")

    def test_combines_pixel_stt_with_hosted_cleanup_latency(self) -> None:
        joined = {
            "case_id": "case-1",
            "audio_duration_ms": 1000,
            "stt_inference_ms": 250,
        }
        hosted = {
            "case_id": "case-1",
            "model_name": "gpt-5.6-luna",
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "finish_reason": "stop",
            "timings": {"total_ms": 500, "ttft_ms": 400, "attempt_count": 1},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            joined_path = root / "joined.jsonl"
            hosted_path = root / "hosted.jsonl"
            joined_path.write_text(json.dumps(joined) + "\n", encoding="utf-8")
            hosted_path.write_text(json.dumps(hosted) + "\n", encoding="utf-8")
            summary = hosted_joined.summarize(joined_path, hosted_path)
        self.assertEqual(750, summary["estimated_pipeline_total"]["median_ms"])
        self.assertEqual(1.0 / 0.75, summary["audio_seconds_per_pipeline_second"])
        self.assertIn("excludes ADB/host handoff", summary["pipeline_scope"])


if __name__ == "__main__":
    unittest.main()
