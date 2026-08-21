import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "prepare-llamacpp-android-source.sh"
PINNED_SOURCE = REPO / ".cache" / "llama.cpp-ece963f41"


class PrepareLlamaCppAndroidSourceTest(unittest.TestCase):
    def test_script_contains_full_reproducibility_pins(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("ece963f41b0b02d7a0d61436ae365762c073a4c8", source)
        self.assertIn("f59cbdf04f233655507cc98ee9f704b71bfd1403", source)
        self.assertIn(
            "d0927d84cda1b6f613a0c953da5bb490d8960546ee3fb15a23810d89f6137f8b",
            source,
        )
        self.assertIn('actual_build" != "b10450', source)
        self.assertIn("Refusing to change a dirty llama.cpp checkout", source)

    def test_rejects_an_existing_non_git_source_path_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env["LLAMACPP_SOURCE_DIR"] = directory
            result = subprocess.run(
                [str(SCRIPT)],
                cwd=REPO,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("is not a Git checkout", result.stderr)

    @unittest.skipUnless(PINNED_SOURCE.is_dir(), "ignored pinned source is not prepared")
    def test_prepared_source_passes_all_identity_checks(self) -> None:
        env = os.environ.copy()
        env["LLAMACPP_SOURCE_DIR"] = str(PINNED_SOURCE)
        result = subprocess.run(
            [str(SCRIPT)],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("commit=ece963f41b0b02d7a0d61436ae365762c073a4c8", result.stdout)
        self.assertIn("build=b10450", result.stdout)
        self.assertIn(
            "archive_sha256=d0927d84cda1b6f613a0c953da5bb490d8960546ee3fb15a23810d89f6137f8b",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main()
