import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "build-llamacpp-benchmark.sh"


class BuildLlamaCppBenchmarkTest(unittest.TestCase):
    def test_build_is_release_module_scoped_and_records_native_evidence(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(":llamacpp-benchmark:testReleaseUnitTest", source)
        self.assertIn(":llamacpp-benchmark:assembleRelease", source)
        self.assertNotIn(":app:", source)
        self.assertIn("28.0.13004108", source)
        self.assertIn("3.31.6", source)
        self.assertIn("3.31.6-g38307f9", source)
        self.assertIn("ece963f41b0b02d7a0d61436ae365762c073a4c8", source)
        self.assertIn("CMakeCache.txt", source)
        self.assertIn("native_libraries", source)
        self.assertIn("build-manifest.json", source)

    def test_rejects_wrong_model_before_source_or_gradle_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / "s1-mini-q4_k_m.gguf"
            model.write_bytes(b"wrong")
            env = os.environ.copy()
            env["S1_DIRECT_MODEL_FILE"] = str(model)
            result = subprocess.run(
                [str(SCRIPT)], cwd=REPO, env=env, capture_output=True, text=True, check=False,
            )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("model identity mismatch", result.stderr)
        self.assertNotIn("Gradle", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
