from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def load_scorer():
    spec = importlib.util.spec_from_file_location(
        "score_cleanup_pixel_results_focused",
        REPO / "scripts" / "score-cleanup-pixel-results.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


scorer = load_scorer()


class ScoreCleanupPixelResultsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.case = {
            "id": "case-1",
            "raw": "uh meet Maya at six",
            "expected": "Meet Maya at 6.",
            "categories": ["name"],
            "must_preserve": ["Maya"],
        }
        self.base_result = {
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
        self.runtime_configuration = {
            "context_size": 3072,
            "cpu_threads_mode": "explicit",
            "cpu_threads": 3,
            "resolved_cpu_threads": 3,
            "cache_enabled": True,
            "cache_max_memory_bytes": 32 * 1024 * 1024,
            "cache_max_entries": 4,
            "cache_disk_disabled": True,
            "cache_requested_max_disk_entries": 0,
            "mmap_enabled": True,
            "fixed_prompt_tokens": 78,
        }

    def summarize(self, rows: list[dict]) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases_path = root / "cases.jsonl"
            result_path = root / "results.jsonl"
            cases_path.write_text(json.dumps(self.case) + "\n", encoding="utf-8")
            result_path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )
            return scorer.summarize(result_path, cases_path)

    def measured_rows(self) -> list[dict]:
        return [dict(self.base_result, repeat_index=index) for index in range(3)]

    def test_legacy_results_remain_compatible(self) -> None:
        summary = self.summarize(self.measured_rows())

        for field in scorer.RUNTIME_CONFIGURATION_FIELDS:
            self.assertIsNone(summary[field])
        self.assertIsNone(summary["cached_prompt_tokens"])
        self.assertEqual(3, summary["measured_call_count"])

    def test_exposes_one_configuration_and_summarizes_cached_prompt_tokens(self) -> None:
        cached_counts = [0, 78, 78]
        rows = [
            dict(
                row,
                **self.runtime_configuration,
                cached_prompt_tokens=cached_counts[index],
            )
            for index, row in enumerate(self.measured_rows())
        ]

        summary = self.summarize(rows)

        for field, value in self.runtime_configuration.items():
            self.assertEqual(value, summary[field])
        self.assertEqual(
            {"count": 3, "min": 0, "median": 78, "max": 78, "total": 156},
            summary["cached_prompt_tokens"],
        )

    def test_rejects_mixed_runtime_configurations(self) -> None:
        rows = [
            dict(row, **self.runtime_configuration, cached_prompt_tokens=0)
            for row in self.measured_rows()
        ]
        rows[1]["context_size"] = 4096

        with self.assertRaisesRegex(ValueError, "mixed runtime configurations"):
            self.summarize(rows)

    def test_rejects_partial_new_metadata(self) -> None:
        rows = self.measured_rows()
        rows[0].update(self.runtime_configuration)

        with self.assertRaisesRegex(ValueError, "mix legacy and runtime configuration"):
            self.summarize(rows)

    def test_rejects_partial_cached_prompt_metadata(self) -> None:
        rows = self.measured_rows()
        for row in rows:
            row.update(self.runtime_configuration)
        rows[0]["cached_prompt_tokens"] = 0

        with self.assertRaisesRegex(ValueError, "incomplete cached_prompt_tokens"):
            self.summarize(rows)

    def test_null_cached_prompt_counts_have_null_summary(self) -> None:
        rows = [
            dict(row, **self.runtime_configuration, cached_prompt_tokens=None)
            for row in self.measured_rows()
        ]

        summary = self.summarize(rows)

        self.assertIsNone(summary["cached_prompt_tokens"])

    def test_accepts_implicit_threads_with_approved_resolved_count(self) -> None:
        configuration = dict(
            self.runtime_configuration,
            cpu_threads_mode="implicit",
            cpu_threads=None,
            resolved_cpu_threads=2,
            cache_enabled=False,
            cache_max_memory_bytes=0,
            cache_max_entries=0,
        )
        rows = [
            dict(row, **configuration, cached_prompt_tokens=0)
            for row in self.measured_rows()
        ]

        summary = self.summarize(rows)

        self.assertEqual("implicit", summary["cpu_threads_mode"])
        self.assertIsNone(summary["cpu_threads"])
        self.assertEqual(2, summary["resolved_cpu_threads"])

    def test_rejects_unapproved_runtime_arms(self) -> None:
        invalid_configurations = {
            "context": {"context_size": 2048},
            "fixed prompt": {"fixed_prompt_tokens": 77},
            "mmap": {"mmap_enabled": False},
            "disk enabled": {"cache_disk_disabled": False},
            "disk entries": {"cache_requested_max_disk_entries": 1},
            "explicit requested threads": {
                "cpu_threads": 6,
                "resolved_cpu_threads": 6,
            },
            "explicit resolved mismatch": {"resolved_cpu_threads": 2},
            "enabled cache size": {"cache_max_memory_bytes": 16 * 1024 * 1024},
            "enabled cache entries": {"cache_max_entries": 3},
            "disabled cache limits": {
                "cache_enabled": False,
                "cache_max_memory_bytes": 32 * 1024 * 1024,
                "cache_max_entries": 4,
            },
        }
        for label, changes in invalid_configurations.items():
            with self.subTest(label=label):
                configuration = dict(self.runtime_configuration, **changes)
                rows = [
                    dict(row, **configuration, cached_prompt_tokens=0)
                    for row in self.measured_rows()
                ]
                with self.assertRaises(ValueError):
                    self.summarize(rows)


if __name__ == "__main__":
    unittest.main()
