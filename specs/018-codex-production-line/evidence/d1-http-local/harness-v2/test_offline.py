"""HTTP deney aracının koruma ve sahte sağlayıcı sınırları; sunucu/DB başlamaz."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import common
import db_guard
import probe

CANARY = "SYNTHETIC_SECRET_NO_OUTPUT_2982"
DATABASE = "dou_synapse_d1_httpoffline"
EXPECTED = {
    "database": DATABASE,
    "database_oid": 123456,
    "system_identifier": "7654321098765432101",
    "server_version_num": 160014,
    "server_address": "127.0.0.1",
    "server_port": 55448,
}
ENV = {
    "D1_TEST_DB_NAME": DATABASE,
    "D1_EXPECTED_TARGET_JSON": json.dumps(EXPECTED),
    "D1_ADMIN_DSN": f"postgresql+psycopg://synthetic_dba:{CANARY}@127.0.0.1:55448/{DATABASE}",
    "D1_HTTP_APP_DSN": f"postgresql+psycopg://dou_app:{CANARY}@127.0.0.1:55448/{DATABASE}",
    "D1_HTTP_PORTS_JSON": "[18331,18332]",
}


class GuardContracts(unittest.TestCase):
    def test_default_does_not_read_credentials_open_network_or_start_process(self):
        output = io.StringIO()
        with (
            patch.object(sys, "argv", [str(Path(probe.__file__))]),
            patch.object(probe, "execute", side_effect=AssertionError("must not execute")),
            patch.object(
                db_guard, "configuration", side_effect=AssertionError("must not read credentials")
            ),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(probe.main(), 0)
        value = json.loads(output.getvalue())
        self.assertFalse(value["database_access"])
        self.assertFalse(value["server_start"])
        self.assertNotIn(CANARY, output.getvalue())

    def test_default_child_process_uses_only_standard_library_and_stays_plan_only(self):
        result = subprocess.run(  # noqa: S603 — sabit kendi varsayılan plan girişi
            [sys.executable, "-S", str(Path(probe.__file__))],
            env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertFalse(json.loads(result.stdout)["database_access"])

    def test_application_route_must_be_exact_loopback_role_database_and_no_options(self):
        for change in ("?hostaddr=192.0.2.1", "?", "?service=remote", "#"):
            with self.subTest(change=change), self.assertRaises(db_guard.TargetGuardError):
                common.application_dsn(ENV | {"D1_HTTP_APP_DSN": ENV["D1_HTTP_APP_DSN"] + change})
        for before, after in [
            ("127.0.0.1", "localhost"),
            ("127.0.0.1", "192.0.2.1"),
            (":55448", ""),
            (":55448", ":55449"),
            ("dou_app:", "dou_worker:"),
            (DATABASE, DATABASE + "other"),
        ]:
            with (
                self.subTest(before=before, after=after),
                self.assertRaises(db_guard.TargetGuardError),
            ):
                common.application_dsn(
                    ENV | {"D1_HTTP_APP_DSN": ENV["D1_HTTP_APP_DSN"].replace(before, after)}
                )

    def test_canonical_app_dsn_roundtrips_actual_sqlalchemy_driver_arguments(self):
        from sqlalchemy import create_engine
        from sqlalchemy.engine import make_url

        value = common.application_dsn(ENV)
        # Sadece dialect; create_engine bağlantı açmaz.
        engine = create_engine(value)
        _args, kwargs = engine.dialect.create_connect_args(make_url(value))
        self.assertEqual(kwargs["hostaddr"], "127.0.0.1")
        self.assertEqual(kwargs["user"], "dou_app")
        self.assertEqual(kwargs["dbname"], DATABASE)
        self.assertEqual(kwargs["port"], 55448)
        self.assertEqual(kwargs["password"], CANARY)
        engine.dispose()

    def test_http_port_pair_is_explicit_unique_and_separate_from_database(self):
        self.assertEqual(probe.ports(ENV), [18331, 18332])
        for value in (
            None,
            [],
            [18331],
            [18331, 18331],
            [True, 18332],
            [55448, 18332],
            [80, 18332],
            ["18331", 18332],
        ):
            with self.subTest(value=value), self.assertRaises(db_guard.TargetGuardError):
                probe.ports(ENV | {"D1_HTTP_PORTS_JSON": json.dumps(value)})

    def test_source_manifest_requires_exact_root_values_and_integrated_quota(self):
        source = {name: "a" * 64 for name in common.SOURCE_PATHS}
        with (
            patch.object(common, "source_hashes", return_value=source),
            patch.object(
                Path,
                "read_text",
                return_value=(
                    "from app.core.request_quota import take_request_slot\n"
                    "admission = await take_request_slot("
                ),
            ),
        ):
            self.assertEqual(
                common.verify_sources({"D1_HTTP_SOURCE_MANIFEST_JSON": json.dumps(source)}), source
            )
            changed = source | {common.SOURCE_PATHS[0]: "b" * 64}
            with self.assertRaisesRegex(db_guard.TargetGuardError, "SOURCE_HASH_MISMATCH"):
                common.verify_sources({"D1_HTTP_SOURCE_MANIFEST_JSON": json.dumps(changed)})
        with (
            patch.object(common, "source_hashes", return_value=source),
            patch.object(Path, "read_text", return_value="old local deque"),
        ):
            with self.assertRaisesRegex(db_guard.TargetGuardError, "QUOTA_PATCH_NOT_INTEGRATED"):
                common.verify_sources({"D1_HTTP_SOURCE_MANIFEST_JSON": json.dumps(source)})

    def test_app_pool_identity_is_non_superuser_non_bypass_and_rls_on(self):
        expected = db_guard.expected_target(ENV, DATABASE)
        row = EXPECTED | {
            "role": "dou_app",
            "session_role": "dou_app",
            "rolsuper": False,
            "rolbypassrls": False,
            "row_security": "on",
            "client_address": "127.0.0.1",
        }
        common.validate_app_identity(row, expected)
        for field, value in [
            ("database_oid", 123457),
            ("server_port", 55449),
            ("server_version_num", 160015),
            ("server_address", "127.0.0.2"),
            ("client_address", "192.0.2.1"),
            ("role", "postgres"),
            ("session_role", "postgres"),
            ("rolsuper", True),
            ("rolbypassrls", True),
            ("row_security", "off"),
        ]:
            with self.subTest(field=field), self.assertRaises(db_guard.TargetGuardError):
                common.validate_app_identity(row | {field: value}, expected)

    def test_passfile_is_private_regular_empty_and_no_symlink(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            path = Path(directory) / "empty.pgpass"
            path.touch(mode=0o600)
            self.assertEqual(common.private_passfile(path), str(path))
            path.chmod(0o644)
            with self.assertRaises(db_guard.TargetGuardError):
                common.private_passfile(path)
            path.chmod(0o600)
            path.write_text("unwanted-password")
            with self.assertRaises(db_guard.TargetGuardError):
                common.private_passfile(path)
            link = Path(directory) / "link.pgpass"
            link.symlink_to(path)
            with self.assertRaises(db_guard.TargetGuardError):
                common.private_passfile(link)

    def test_child_environment_cannot_inherit_credentials_or_libpq_routes(self):
        with tempfile.TemporaryDirectory(dir="/private/tmp") as directory:
            output = Path(directory)
            (output / "empty.pgpass").touch(mode=0o600)
            poison = ENV | {
                "PGHOSTADDR": "192.0.2.1",
                "PGSERVICE": "remote",
                "PGPASSWORD": CANARY,
                "OPENAI_API_KEY": CANARY,
                "DATABASE_URL": "production",
                "WORKER_DATABASE_URL": "production-worker",
                "SUPABASE_SERVICE_ROLE_KEY": CANARY,
                "D1_HTTP_SOURCE_MANIFEST_JSON": "{}",
            }
            with patch.object(common, "verify_sources", return_value={}):
                clean = common.child_environment(poison, output, 0, 99)
            self.assertEqual({key for key in clean if key.startswith("PG")}, {"PGPASSFILE"})
            for key in ("OPENAI_API_KEY", "SUPABASE_SERVICE_ROLE_KEY", "D1_ADMIN_DSN"):
                self.assertNotIn(key, clean)
            self.assertTrue(clean["DATABASE_URL"].endswith("?hostaddr=127.0.0.1"))
            self.assertEqual(clean["LLM_FAKE_PROVIDER"], "true")
            self.assertEqual(clean["ENVIRONMENT"], "local")
            self.assertEqual(clean["PGPASSFILE"], str(output / "empty.pgpass"))

    def test_admin_guard_same_cluster_identity_still_required(self):
        config = db_guard.configuration(ENV)
        row = EXPECTED | {
            "role": "synthetic_dba",
            "session_role": "synthetic_dba",
            "rolsuper": True,
            "client_address": "127.0.0.1",
        }
        db_guard.validate_connected_identity(row, config)
        with self.assertRaisesRegex(db_guard.TargetGuardError, "CONNECTED_CLUSTER_MISMATCH"):
            db_guard.validate_connected_identity(
                row | {"system_identifier": "7654321098765432102"}, config
            )

    def test_existing_output_and_non_tmp_target_are_not_reused(self):
        self.assertTrue(probe.re_output("d1-http-measured-offline01"))
        self.assertFalse(probe.re_output("unrelated-output"))
        self.assertFalse(probe.re_output("d1-http-measured-../../other"))


class FixtureContracts(unittest.TestCase):
    def test_actual_fixture_supplies_required_columns_and_teacher_as_topic_creator(self):
        source = Path(os.environ.get("D1_HTTP_FIXTURE_SOURCE_FILE", probe.__file__))
        spec = importlib.util.spec_from_file_location("d1_http_fixture_under_test", source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # 0001_core_schema + 0004_assessment, sonraki migration'lar: NOT NULL ve
        # varsayılanı olmayan zorunlu girdiler. Bu bir genel SQL motoru değildir.
        required = {
            "profiles": {"id", "email"},
            "courses": {"code", "title", "created_by"},
            "course_memberships": {"course_id", "user_id", "role"},
            "topics": {"course_id", "name", "created_by"},
            "documents": {
                "course_id",
                "uploaded_by",
                "file_name",
                "file_type",
                "storage_path",
                "file_hash",
                "byte_size",
            },
            "chunks": {"course_id", "document_id", "chunk_index", "text", "token_count"},
        }
        inserted = []

        def execute(sql, args=()):
            if sql.startswith("SELECT scope,"):
                return Mock(fetchall=Mock(return_value=probe.POLICIES))
            if sql.startswith("SELECT count(*)"):
                return Mock(fetchone=Mock(return_value={"n": 0}))
            match = re.match(r"INSERT INTO public\.(\w+)\s*\((.*?)\)", sql, re.DOTALL)
            self.assertIsNotNone(match, "unexpected fixture SQL")
            table = match[1]
            columns = [column.strip() for column in match[2].split(",")]
            self.assertTrue(
                required[table] <= set(columns),
                f"missing required fixture columns: {table}: {required[table] - set(columns)}",
            )
            self.assertEqual(sql.count("%s"), len(args), "fixture bind count differs")
            inserted.append((table, columns, args))
            return Mock()

        admin = Mock(execute=Mock(side_effect=execute))
        admin.transaction.side_effect = contextlib.nullcontext
        fixture = module.fixture(admin)
        self.assertEqual(len(inserted), 20)
        self.assertEqual({row[0] for row in inserted}, set(required))
        topics = [row for row in inserted if row[0] == "topics"]
        self.assertEqual(len(topics), 1)
        topic = dict(zip(topics[0][1], topics[0][2], strict=True))
        self.assertEqual(topic["id"], fixture["topic"])
        self.assertEqual(topic["course_id"], fixture["course"])
        self.assertEqual(topic["created_by"], fixture["actors"]["teacher"])


class ProviderContracts(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(dir="/private/tmp")
        self.env = patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "local",
                "DEV_AUTH_ENABLED": "true",
                "LLM_FAKE_PROVIDER": "true",
                "EMBEDDING_PROVIDER": "hashing",
                "D1_HTTP_OUTPUT": self.directory.name,
                "D1_HTTP_INDEX": "0",
            },
            clear=True,
        )
        self.env.start()
        sys.path.insert(0, str(common.REPOSITORY / "apps/api"))
        from app.core.config import get_settings

        get_settings.cache_clear()
        self.serve = importlib.import_module("serve")
        self.events = patch.object(self.serve, "event", Mock())
        self.events.start()
        self.serve.install_providers()

    async def asyncTearDown(self):
        from app.modules.agent.pipeline import set_pipeline
        from app.modules.assessment.question_gen import reset_providers

        set_pipeline()
        reset_providers()
        self.events.stop()
        self.env.stop()
        self.directory.cleanup()
        sys.path.pop(0)

    def chunk(self):
        from app.contracts import RetrievedChunk

        return RetrievedChunk(
            chunk_id=uuid4(),
            document_id=uuid4(),
            file_name="d1-synthetic.txt",
            page_number=1,
            slide_number=None,
            section_title="Deadlock",
            text=probe.TEXTS[0],
            dense_score=1.0,
            fts_score=1.0,
        )

    async def test_actual_generation_service_fake_answers_and_injected_failure_propagates(self):
        from app.contracts import AnswerStatus, AssistantAudience, ChatMode
        from app.modules.agent.pipeline import get_generator
        from app.modules.generation.llm import LlmUnavailableError

        generator = get_generator()
        kwargs = dict(
            chunks=[self.chunk()],
            mode=ChatMode.QA,
            audience=AssistantAudience.STUDENT,
            max_output_tokens=700,
        )
        result = await generator.generate_role_aware_with_claims(
            question="Deadlock koşulları nelerdir? D1_CACHE", **kwargs
        )
        self.assertEqual(result.answer.status, AnswerStatus.ANSWERED)
        self.assertEqual(len(result.answer.citations), 1)
        with self.assertRaises(LlmUnavailableError):
            await generator.generate_role_aware_with_claims(
                question="Deadlock D1_PROVIDER_FAILURE", **kwargs
            )
        events = [c for c in self.serve.event.call_args_list if c.args[0] == "provider"]
        self.assertEqual(len(events), 2)
        self.assertTrue(events[-1].kwargs["injected_failure"])

    async def test_actual_qgen_prompt_fake_output_satisfies_existing_draft_parser(self):
        from app.models.assessment import QuestionType
        from app.modules.assessment import question_gen

        chunk = self.chunk()
        attempt, reasons = await question_gen._request_drafts(
            question_gen.resolve_completion(),
            topic_name="Deadlock koşulları",
            question_type=QuestionType.MCQ,
            count=1,
            chunks=[chunk],
            answer_format=None,
            example_questions=(),
            learning_outcome_text=None,
            difficulty=None,
        )
        self.assertEqual(attempt.returned, 1)
        self.assertEqual(len(attempt.drafts), 1)
        self.assertEqual(attempt.drafts[0].source_chunk_id, chunk.chunk_id)
        self.assertEqual(reasons, [])
        events = [c for c in self.serve.event.call_args_list if c.args[0] == "provider"]
        self.assertEqual(len(events), 1)

    async def test_source_refusal_fixture_never_executes_sql_or_provider(self):
        from app.modules.agent.pipeline import get_retriever

        session = Mock(
            execute=AsyncMock(side_effect=AssertionError("SQL not needed for empty fixture"))
        )
        retriever = get_retriever(session)
        self.assertEqual(
            await retriever.search(course_id=uuid4(), query="D1_NO_SOURCE", limit=8), []
        )
        session.execute.assert_not_called()
        self.assertFalse(any(c.args[0] == "provider" for c in self.serve.event.call_args_list))


if __name__ == "__main__":
    unittest.main(verbosity=2)
