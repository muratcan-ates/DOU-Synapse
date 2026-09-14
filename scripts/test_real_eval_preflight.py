from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import real_eval_preflight


class PreflightHelper:
    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        self._git("init", "-q")
        self._git("config", "user.name", "Real eval preflight tests")
        self._git("config", "user.email", "eval@tests.local")
        readme = self.repo / "README.md"
        readme.write_text("p4 test repo\n", encoding="utf-8")
        self._git("add", "README.md")
        self._git("commit", "-m", "base", "-q")

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return result.stdout

    def corpus(self) -> Path:
        path = self.repo / "tmp-corpus.json"
        path.write_text(json.dumps({"corpus_version": "test"}), encoding="utf-8")
        return path

    def close(self) -> None:
        self.temporary.cleanup()


class RealEvalPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = PreflightHelper()

    def tearDown(self) -> None:
        self.workspace.close()

    @staticmethod
    def _env_for_repo(database: str = "dou_eval") -> dict[str, str]:
        return {
            "EVAL_ADMIN_DSN": f"postgresql+asyncpg://postgres:pass@127.0.0.1:5432/{database}",
            "EVAL_APP_DSN": f"postgresql+asyncpg://dou_app:pass@127.0.0.1:5432/{database}",
            "EVAL_WORKER_DSN": f"postgresql+asyncpg://dou_worker:pass@127.0.0.1:5432/{database}",
            "EVAL_LLM_API_KEY": "secret-key",
            "EVAL_RUNTIME_SECRET": "runtime-secret",
            "EVAL_RUNTIME_ENABLED": "true",
        }

    def test_passes_with_expected_env_and_clean_tree(self) -> None:
        corpus = self.workspace.corpus()
        expected = hashlib.sha256(corpus.read_bytes()).hexdigest()
        with mock.patch.object(real_eval_preflight, "_socket_alive", return_value=None), mock.patch.dict(
            os.environ, self._env_for_repo(), clear=False
        ):
            result = real_eval_preflight._run(
                repo=self.workspace.repo,
                corpus=corpus,
                required_db_name="dou_eval",
                skip_db_connect=False,
            )

        self.assertEqual(result.status, "pass")
        self.assertEqual(result.corpus_sha256, expected)
        self.assertTrue(result.environment_ready)
        self.assertFalse(result.failures)

    def test_dirty_tree_blocks_without_db_connect(self) -> None:
        self.workspace.repo.joinpath("dirty.txt").write_text("dirty", encoding="utf-8")
        corpus = self.workspace.corpus()
        with mock.patch.dict(os.environ, self._env_for_repo(), clear=False):
            result = real_eval_preflight._run(
                repo=self.workspace.repo,
                corpus=corpus,
                required_db_name="dou_eval",
                skip_db_connect=True,
            )

        self.assertEqual(result.status, "blocked")
        self.assertIn("working tree dirty", " ".join(result.failures))

    def test_missing_env_and_secret_not_leaked(self) -> None:
        corpus = self.workspace.corpus()
        corpus.unlink()
        with mock.patch("sys.stdout", new=io.StringIO()) as stream, mock.patch.dict(
            os.environ,
            {
                "EVAL_RUNTIME_ENABLED": "true",
                "EVAL_ADMIN_DSN": "postgresql+asyncpg://postgres:pass@127.0.0.1:5432/dou_eval",
                "EVAL_APP_DSN": "postgresql+asyncpg://dou_app:pass@127.0.0.1:5432/dou_eval",
                "EVAL_WORKER_DSN": "postgresql+asyncpg://dou_worker:pass@127.0.0.1:5432/dou_eval",
                "EVAL_LLM_API_KEY": "secret-api-key",
                "EVAL_RUNTIME_SECRET": "secret-runtime-secret",
            },
            clear=False,
        ):
            with mock.patch.object(real_eval_preflight, "_socket_alive", return_value=None):
                code = real_eval_preflight.main()
            output = stream.getvalue()

        self.assertNotEqual(code, 0)
        self.assertNotIn("secret-api-key", output)
        self.assertNotIn("secret-runtime-secret", output)
        self.assertIn("Corpus dosyası bulunamadı", output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
