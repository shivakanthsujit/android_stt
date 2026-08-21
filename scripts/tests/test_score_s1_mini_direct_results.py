import copy
import importlib.util
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "score-s1-mini-direct-results.py"
SPEC = importlib.util.spec_from_file_location("score_s1_mini_direct_results", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def direct_row(case_id: str, repeat: int, output: str) -> dict:
    raw_ids = [101, 102]
    prompt_ids = list(range(80))
    return {
        "schema_version": 1,
        "run_id": "direct-test",
        "phase": "measured",
        "repeat_index": repeat,
        "case_id": case_id,
        "categories": ["test"],
        "raw_text": f"raw {case_id}",
        "model_file": MODULE.MODEL_FILE,
        "model_sha256": MODULE.MODEL_SHA256,
        "prompt_profile": "s1-mini-v1-publisher",
        "requested_max_output_tokens": 35,
        "requested_config": {
            "context_tokens": 2560,
            "generation_threads": 2,
            "batch_threads": 2,
            "batch_size": 512,
            "micro_batch_size": 512,
            "use_mmap": True,
            "flash_attention": False,
            "gpu_layers": 0,
        },
        "native_model_info": {
            "schema_version": 1,
            "model_description": "S1-mini by Superwhisper",
            "model_size_bytes": MODULE.MODEL_SIZE_BYTES,
            "model_tensor_size_bytes": 480_000_000,
            "model_parameter_count": 600_000_000,
            "chat_template": "embedded-template",
            "context_size": 2560,
            "batch_size": 512,
            "micro_batch_size": 512,
            "threads": 2,
            "threads_batch": 2,
            "use_mmap": True,
            "flash_attention": False,
            "gpu_layers": 0,
            "backend_names": ["CPU"],
            "selected_cpu_backend_library": "libggml-cpu-android_armv8.2_2.so",
            "system_info": "ARM64",
            "supports_mmap": True,
            "supports_gpu_offload": False,
            "supports_enable_thinking": True,
            "fixed_prompt_tokens": MODULE.FIXED_PROMPT_TOKENS,
            "llama_version": MODULE.LLAMA_BUILD,
            "native_build_type": "Release",
            "native_compiler": "Clang",
            "native_compile_flags": "-O3 -DNDEBUG",
        },
        "app_build": {
            "application_id": MODULE.APPLICATION_ID,
            "llama_cpp_revision": MODULE.LLAMA_REVISION,
            "ndk_version": "28.0.13004108",
            "cmake_version": "3.31.6",
            "build_type": "release",
        },
        "process_cpu_ms": 11,
        "process_pss_kb_after_inference": 22,
        "native_heap_bytes_after_inference": 33,
        "thermal_status_after_inference": 0,
        "raw_token_ids": raw_ids,
        "raw_token_count": len(raw_ids),
        "rendered_prompt": (
            f"<|im_start|>system\n{MODULE.SYSTEM_PROMPT}<|im_end|>\n"
            f"<|im_start|>user\n{MODULE.CONTROL_LINE}\nraw {case_id}<|im_end|>\n"
            "<|im_start|>assistant\n<think>\n\n</think>\n\n"
        ),
        "prompt_token_ids": prompt_ids,
        "prompt_token_count": len(prompt_ids),
        "raw_output": output,
        "completion_token_ids": [201],
        "completion_tokens": 1,
        "finish_reason": "eog",
        "hit_token_cap": False,
        "eog_token_id": 151645,
        "started_at_ns": 1_000_000,
        "prompt_started_at_ns": 2_000_000,
        "prompt_completed_at_ns": 3_000_000,
        "first_token_at_ns": 4_000_000,
        "completed_at_ns": 5_000_000,
        "prompt_eval_ms": 1.0,
        "decode_ms": 2.0,
        "total_ms": 4.0,
        "prompt_tokens_per_second": 80.0,
        "decode_tokens_per_second": 1.0,
        "perf_prompt_eval_ms": 1.0,
        "perf_decode_ms": 2.0,
        "perf_prompt_tokens": 80,
        "perf_decode_tokens": 1,
        "perf_reused_graphs": 0,
        "model_load_ms": 123,
        "created_at_utc": "2026-08-22T00:00:00Z",
    }


def control_row(candidate: dict) -> dict:
    return {
        "phase": "measured",
        "case_id": candidate["case_id"],
        "repeat_index": candidate["repeat_index"],
        "model_sha256": MODULE.MODEL_SHA256,
        "raw_text": candidate["raw_text"],
        "prompt_tokens": candidate["prompt_token_count"],
        "requested_max_output_tokens": candidate["requested_max_output_tokens"],
        "raw_model_output": candidate["raw_output"],
        "context_size": 2560,
        "resolved_cpu_threads": 2,
        "cache_enabled": False,
        "mmap_enabled": True,
    }


class ScoreS1MiniDirectResultsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [
            direct_row(case_id, repeat, f"clean {case_id}")
            for repeat in range(2)
            for case_id in ("a", "b")
        ]

    def test_summarizes_and_proves_control_parity(self) -> None:
        summary = MODULE.summarize(self.rows, [control_row(row) for row in self.rows])
        self.assertEqual(4, summary["measured_requests"])
        self.assertEqual([], summary["unstable_case_ids"])
        self.assertEqual(4, summary["control_parity"]["raw_output_matches"])
        self.assertEqual([], summary["control_parity"]["raw_output_differences"])

    def test_reports_raw_differences_without_embedding_output_text(self) -> None:
        control = [control_row(row) for row in self.rows]
        control[-1]["raw_model_output"] = "different"
        parity = MODULE.summarize(self.rows, control)["control_parity"]
        self.assertEqual(3, parity["raw_output_matches"])
        self.assertEqual([{"case_id": "b", "repeat_index": 1}], parity["raw_output_differences"])
        self.assertNotIn("different", str(parity))

    def test_rejects_configuration_or_contract_drift(self) -> None:
        bad = copy.deepcopy(self.rows)
        bad[0]["requested_config"]["generation_threads"] = 99
        with self.assertRaisesRegex(ValueError, "mix requested_config"):
            MODULE.summarize(bad)

        bad = copy.deepcopy(self.rows)
        for row in bad:
            row["prompt_token_ids"].append(999)
            row["prompt_token_count"] += 1
        with self.assertRaisesRegex(ValueError, "fixed prompt-token count drift"):
            MODULE.summarize(bad)

    def test_rejects_mixed_provenance_and_incomplete_repeats(self) -> None:
        bad = copy.deepcopy(self.rows)
        bad[-1]["run_id"] = "another-run"
        with self.assertRaisesRegex(ValueError, "mix run_id"):
            MODULE.summarize(bad)

        bad = copy.deepcopy(self.rows)
        for row in bad:
            row["repeat_index"] += 1
        with self.assertRaisesRegex(ValueError, "complete and zero-based"):
            MODULE.summarize(bad)

        bad = copy.deepcopy(self.rows)
        bad[-1]["native_model_info"]["threads"] = 4
        with self.assertRaisesRegex(ValueError, "mix native_model_info"):
            MODULE.summarize(bad)

    def test_rejects_unmatched_leap_control(self) -> None:
        control = [control_row(row) for row in self.rows]
        control[0]["context_size"] = 4096
        with self.assertRaisesRegex(ValueError, "matched LEAP winner"):
            MODULE.summarize(self.rows, control)

    def test_rejects_prompt_and_eog_contract_drift(self) -> None:
        bad = copy.deepcopy(self.rows)
        bad[0]["rendered_prompt"] += "drift"
        with self.assertRaisesRegex(ValueError, "rendered prompt drift"):
            MODULE.summarize(bad)

        bad = copy.deepcopy(self.rows)
        for row in bad:
            row["finish_reason"] = "token_cap"
            row["hit_token_cap"] = True
            row["completion_tokens"] = row["requested_max_output_tokens"]
            row["completion_token_ids"] = [201] * row["completion_tokens"]
        with self.assertRaisesRegex(ValueError, "must not report an EOG"):
            MODULE.summarize(bad)


if __name__ == "__main__":
    unittest.main()
