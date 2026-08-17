from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "screen-cleanup-candidate.py"
SPEC = importlib.util.spec_from_file_location("screen_cleanup_candidate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
screen = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = screen
SPEC.loader.exec_module(screen)


class ScreenCleanupCandidateTest(unittest.TestCase):
    def test_sha256_file_streams_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.gguf"
            data = (b"model-bytes" * 100_000) + b"tail"
            path.write_bytes(data)
            self.assertEqual(hashlib.sha256(data).hexdigest(), screen.sha256_file(path))

    def test_output_paths_are_complete_and_run_scoped(self) -> None:
        paths = screen.output_paths(Path("out"), "candidate-v1")
        self.assertEqual(Path("out/candidate-v1-provenance.json"), paths["provenance"])
        self.assertEqual(Path("out/candidate-v1-seed.jsonl"), paths["result_seed"])
        self.assertEqual(
            Path("out/candidate-v1-heldout-v1-score.json"),
            paths["score_heldout-v1"],
        )

    def test_server_command_preserves_qwen_reasoning_extras(self) -> None:
        command = screen.server_command(
            Path("/bin/llama-server"),
            Path("/models/tuned.gguf"),
            "voiceink-qwen35-2b",
            18080,
            ("--reasoning", "off", "--ctx-size", "4096"),
        )
        self.assertEqual(
            [
                "/bin/llama-server",
                "--model",
                "/models/tuned.gguf",
                "--alias",
                "voiceink-qwen35-2b",
                "--host",
                "127.0.0.1",
                "--port",
                "18080",
                "--reasoning",
                "off",
                "--ctx-size",
                "4096",
            ],
            command,
        )

    def test_runner_command_keeps_frozen_decoding_and_runtime_extras(self) -> None:
        command = screen.runner_command(
            model_name="voiceink-qwen35-2b",
            quantization="Q4_K_M",
            port=18080,
            corpus=Path("cases.jsonl"),
            output=Path("results.jsonl"),
            prompt_variant="few_shot_corrections",
            temperature=0.1,
            request_extra=Path("no-think.json"),
        )
        self.assertIn("few_shot_corrections", command)
        self.assertIn("0.1", command)
        self.assertNotIn("--omit-seed", command)
        self.assertEqual("no-think.json", command[-1])

    def test_scorer_command_uses_matching_corpus(self) -> None:
        command = screen.scorer_command(Path("heldout.jsonl"), Path("result.jsonl"))
        self.assertEqual(
            [
                sys.executable,
                str(screen.SCORER),
                "--cases",
                "heldout.jsonl",
                "--format",
                "json",
                "result.jsonl",
            ],
            command,
        )

    def test_voiceink_prompt_provenance_is_content_pinned(self) -> None:
        provenance = screen.prompt_provenance("voiceink_task_tuned")
        self.assertEqual("voiceink_task_tuned", provenance["variant"])
        self.assertEqual(str(screen.VOICEINK_PROMPT), provenance["path"])
        self.assertEqual(
            screen.sha256_file(screen.VOICEINK_PROMPT), provenance["sha256"]
        )

    def test_embedded_prompt_provenance_needs_no_external_file(self) -> None:
        self.assertEqual(
            {"variant": "baseline_rules"},
            screen.prompt_provenance("baseline_rules"),
        )


if __name__ == "__main__":
    unittest.main()
