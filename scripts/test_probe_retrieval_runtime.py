"""Offline guard/oracle tests; no PostgreSQL connection or claim of measured quality."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts import benchmark_retrieval_plan as bench
from scripts import probe_retrieval_runtime as probe


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    config = bench.Config()
    source = bench.plan(config)
    source["status"] = "measured"  # Synthetic unit-test fixture, never published as evidence.
    source["source_sha256"][str(bench.DENSE_PATH)] = bench.PRE_C1_DENSE_SOURCE_SHA256
    source["corpus"] = {
        "rows": config.rows,
        "sha256": "a" * 64,
        "documents": [
            {**asdict(doc), "id": str(doc.id), "course_id": str(doc.course_id)}
            for doc in bench.documents(config)
        ],
    }
    source["connections"] = {
        "target": {
            "host": "127.0.0.1",
            "port": 55448,
            "database": "dou018_retrieval_20260908b",
            "user": "dou_app",
        }
    }
    path = tmp_path / "synthetic-source.json"
    path.write_text(json.dumps(source))
    return path


def test_replay_keeps_real_canonical_space_and_cannot_ingest(source_file: Path) -> None:
    from app.core.vector_space import space_of

    source, _, cases = probe.load_source(source_file)
    provider = probe.SyntheticReplayProvider(cases)
    assert space_of(provider) == "SyntheticReplayProvider/dou018-synthetic-plan-v1@bilinmiyor"
    for case in cases:
        assert provider.embed_query(case["id"]) == json.loads(case["query_vector"])
        assert source["query_sha256"][case["id"]] == bench.sha256(case["query_vector"].encode())
        assert len(provider.embed_query(case["id"])) == 1024
    with pytest.raises(RuntimeError, match="cannot ingest"):
        provider.embed_documents(["test"])
    with pytest.raises(KeyError):
        provider.embed_query("unknown query")


@pytest.mark.parametrize("field", ["query_sha256", "corpus_version", "dimensions", "case_ids"])
def test_source_replay_contract_tampering_fails(source_file: Path, field: str) -> None:
    source = json.loads(source_file.read_text())
    source[field] = "changed"
    source_file.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="manifest"):
        probe.load_source(source_file)


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://dou_app@127.0.0.1:55448/dou018_retrieval_20260908b",
        "postgresql://dou_app@127.0.0.1:55449/dou018_retrieval_runtime1",
        "postgresql://dou_worker@127.0.0.1:55448/dou018_retrieval_runtime1",
        "postgresql://dou_app@example.org:55448/dou018_retrieval_runtime1",
        "postgresql://dou_app@127.0.0.1:55448/postgres",
        "postgresql://dou_app@127.0.0.1:55448/dou018_retrieval_runtime1?options=-crole=postgres",
    ],
)
def test_target_rejects_original_wrong_route_role_and_nonisolated_database(
    source_file: Path, dsn: str
) -> None:
    source, _, _ = probe.load_source(source_file)
    with pytest.raises(ValueError):
        probe.validate_target(dsn, source)


def test_target_accepts_distinct_clone_without_echoing_password(
    source_file: Path,
) -> None:
    source, _, _ = probe.load_source(source_file)
    target = probe.validate_target(
        "postgresql://dou_app:unit-secret@127.0.0.1:55448/dou018_retrieval_runtime1",
        source,
    )
    assert target.database == "dou018_retrieval_runtime1"
    assert "unit-secret" not in repr(target) + json.dumps(target.public())


@pytest.mark.parametrize("key", sorted(probe.FORBIDDEN_ENV))
def test_target_rejects_ambient_routing(
    source_file: Path, monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    monkeypatch.setenv(key, "unused")
    source, _, _ = probe.load_source(source_file)
    with pytest.raises(ValueError):
        probe.validate_target(
            "postgresql://dou_app@127.0.0.1:55448/dou018_retrieval_runtime1", source
        )


def test_prepared_parameter_order_deduplicates_real_runtime_binds() -> None:
    from app.modules.retrieval import dense, fts
    from sqlalchemy.dialects.postgresql.psycopg import PGDialect_psycopg

    for query, params, expected in [
        (
            dense._SQL,
            {
                "query_vector": "[1]",
                "course_id": "course",
                "filter_documents": False,
                "document_ids": [],
                "candidate_limit": 192,
                "limit": 24,
            },
            ["[1]", "course", False, [], 192, 24],
        ),
        (
            fts._SQL,
            {
                "strict": False,
                "query": "query",
                "course_id": "course",
                "filter_documents": True,
                "document_ids": ["doc"],
                "limit": 24,
            },
            [False, "query", "course", True, ["doc"], 24],
        ),
    ]:
        statement = str(query.compile(dialect=PGDialect_psycopg()))
        server, values = probe.prepared_template(statement, params)
        assert values == expected
        assert "$6" in server and "$7" not in server and "%" not in server
        assert server.count("$1") == (2 if query is dense._SQL else 1)
        if query is fts._SQL:
            assert server.count("$2") == 2
    with pytest.raises(ValueError):
        probe.prepared_template("SELECT %(x)s", {"unrelated": 1})


@pytest.mark.asyncio
async def test_readonly_is_first_and_real_rls_context_is_set() -> None:
    calls = []

    class Session:
        async def execute(self, query: object, params: object = None) -> object:
            calls.append((str(query), params))
            return SimpleNamespace(scalar_one=lambda: "on")

    await probe.start_readonly(Session(), "force_generic_plan", bench.USER_ID)
    assert calls[0] == ("SET TRANSACTION READ ONLY", None)
    assert calls[2][1] == {"mode": "force_generic_plan"}
    assert calls[3] == (
        "SELECT set_config('app.current_user_id', :uid, true)",
        {"uid": str(bench.USER_ID)},
    )
    with pytest.raises(ValueError):
        await probe.start_readonly(Session(), "arbitrary", bench.USER_ID)
    assert len(calls) == 5


@pytest.mark.asyncio
async def test_readonly_off_aborts_before_runtime_calls() -> None:
    session = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one=lambda: "off"))
    )
    with pytest.raises(ValueError, match="Read-only"):
        await probe.start_readonly(session, "auto", bench.USER_ID)


@pytest.mark.asyncio
async def test_explain_targets_actual_prepared_statement_with_quoted_values() -> None:
    from psycopg import sql

    capture = {
        "sql": "SELECT %(value)s",
        "params": {"value": "x'); DROP TABLE chunks; --"},
    }
    prepared = {"name": '_pg3_7"quoted', "statement": "SELECT $1", "lane": "dense"}
    cursor = SimpleNamespace(
        fetchone=AsyncMock(return_value=([{"Plan": {"Node Type": "Result"}}],))
    )
    mode_cursor = SimpleNamespace(fetchone=AsyncMock(return_value=("auto",)))
    driver = SimpleNamespace(execute=AsyncMock(side_effect=[mode_cursor, None, cursor, None]))
    result = await probe.explain_prepared(driver, prepared, capture)
    command = driver.execute.await_args_list[2].args[0]
    assert isinstance(command, sql.Composed)
    rendered = command.as_string()
    assert 'EXECUTE "_pg3_7""quoted"' in rendered
    assert "'x''); DROP TABLE chunks; --'" in rendered
    assert driver.execute.await_args.kwargs == {"prepare": False}
    assert result["lane"] == "dense" and result["hnsw"] is False
    with pytest.raises(ValueError, match="match"):
        await probe.explain_prepared(
            driver, {**prepared, "statement": "DELETE FROM chunks"}, capture
        )
    assert driver.execute.await_count == 4
    assert driver.execute.await_args_list[1].args == (
        "SELECT set_config('plan_cache_mode', 'force_custom_plan', true)",
    )
    assert driver.execute.await_args_list[3].args == (
        "SELECT set_config('plan_cache_mode', %s, true)",
        ("auto",),
    )
    assert result["effective_plan_mode"] == "force_custom_plan"
    assert result["restored_caller_mode"] == "auto"


def test_rows_metadata_scope_and_empty_filter_oracles() -> None:
    row = SimpleNamespace(
        chunk_id="c",
        document_id="d",
        file_name="x",
        page_number=2,
        slide_number=3,
        section_title="t",
        text="body",
    )
    metadata = {"c": {**vars(row), "course_id": "course", "file_hash": "hash", "chunk_index": 1}}
    case = {
        "course_id": "course",
        "course": "broad",
        "filter_documents": False,
        "document_ids": [],
    }
    assert probe.check_rows([row], case, metadata, 8) == [["hash", 1]]
    for changed in [
        {"course_id": "other"},
        {"course": "unrelated"},
        {"filter_documents": True},
    ]:
        with pytest.raises(ValueError, match="ineligible"):
            probe.check_rows([row], {**case, **changed}, metadata, 8)
    with pytest.raises(ValueError, match="metadata"):
        probe.check_rows([SimpleNamespace(**{**vars(row), "slide_number": 5})], case, metadata, 8)
    with pytest.raises(ValueError, match="duplicate"):
        probe.check_rows([row, row], case, metadata, 8)
    with pytest.raises(ValueError, match="no eligible"):
        probe.check_rows([], case, metadata, 8)


def test_plan_does_not_connect_and_existing_evidence_is_preserved(
    source_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    execute = AsyncMock(side_effect=AssertionError("must not connect"))
    monkeypatch.setattr(probe, "execute", execute)
    output = tmp_path / "plan.json"
    assert probe.main(["--source-report", str(source_file), "--output", str(output)]) == 0
    report = json.loads(output.read_text())
    assert report["status"] == "planned" and report["warmups_per_case"] == 12
    assert report["namespace"] == "SyntheticReplayProvider/dou018-synthetic-plan-v1@bilinmiyor"
    assert execute.await_count == 0
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        probe.main(["--source-report", str(source_file), "--output", str(output)])
    assert output.read_bytes() == before


def test_execute_rejects_original_before_connecting_and_sanitizes_failure(
    source_file: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    execute = AsyncMock(side_effect=AssertionError("must not connect"))
    monkeypatch.setattr(probe, "execute", execute)
    monkeypatch.setenv(
        "RETRIEVAL_PROBE_APP_DSN",
        "postgresql://dou_app:unit-secret@127.0.0.1:55448/dou018_retrieval_20260908b",
    )
    output = tmp_path / "failure.json"
    assert (
        probe.main(["--execute", "--source-report", str(source_file), "--output", str(output)]) == 1
    )
    assert execute.await_count == 0
    assert "unit-secret" not in output.read_text()
    assert json.loads(output.read_text())["error_type"] == "ValueError"


@pytest.mark.parametrize("mode", list(probe.MODES))
def test_counter_deltas_prove_dense_custom_and_fts_caller_policy(mode: str) -> None:
    before = [
        {"name": lane, "lane": lane, "generic_plans": 11, "custom_plans": 15}
        for lane in ("dense", "fts")
    ]
    after = [
        {
            **item,
            "generic_plans": item["generic_plans"]
            + (7 if item["lane"] == "fts" and mode != "force_custom_plan" else 0),
            "custom_plans": item["custom_plans"]
            + (7 if item["lane"] == "dense" or mode == "force_custom_plan" else 0),
        }
        for item in before
    ]
    deltas = probe.measured_counter_deltas(before, after, mode, 7)
    assert deltas[0] == {"name": "dense", "lane": "dense", "generic_plans": 0, "custom_plans": 7}


@pytest.mark.parametrize(
    "failure",
    ["dense_generic", "fts_leak", "missing_execution", "new_prepared", "counter_regression"],
)
def test_counter_oracle_rejects_runtime_policy_and_measurement_failures(failure: str) -> None:
    before = [
        {"name": lane, "lane": lane, "generic_plans": 10, "custom_plans": 10}
        for lane in ("dense", "fts")
    ]
    after = [{**before[0], "custom_plans": 17}, {**before[1], "generic_plans": 17}]
    if failure == "dense_generic":
        after[0].update(custom_plans=10, generic_plans=17)
    elif failure == "fts_leak":
        after[1].update(custom_plans=17, generic_plans=10)
    elif failure == "missing_execution":
        after[0]["custom_plans"] = 16
    elif failure == "new_prepared":
        after[0]["name"] = "unknown"
    else:
        after[0]["generic_plans"] = 9
    with pytest.raises(ValueError):
        probe.measured_counter_deltas(before, after, "force_generic_plan", 7)


@pytest.mark.asyncio
async def test_fts_explain_keeps_original_plan_policy() -> None:
    driver = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(fetchone=AsyncMock(return_value=("force_generic_plan",))),
                SimpleNamespace(
                    fetchone=AsyncMock(return_value=([{"Plan": {"Node Type": "Result"}}],))
                ),
            ]
        )
    )
    result = await probe.explain_prepared(
        driver,
        {"name": "_pg3_1", "statement": "SELECT $1", "lane": "fts"},
        {"sql": "SELECT %(x)s", "params": {"x": 1}},
    )
    assert driver.execute.await_count == 2
    assert result["effective_plan_mode"] == "force_generic_plan"
    assert all("set_config" not in str(call.args[0]) for call in driver.execute.await_args_list)


@pytest.mark.asyncio
async def test_explain_sql_failure_keeps_original_error_for_caller_rollback() -> None:
    failure = RuntimeError("synthetic prepared SQL failure")
    driver = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                SimpleNamespace(fetchone=AsyncMock(return_value=("auto",))),
                None,
                failure,
            ]
        )
    )
    with pytest.raises(RuntimeError) as caught:
        await probe.explain_prepared(
            driver,
            {"name": "_pg3_1", "statement": "SELECT $1", "lane": "dense"},
            {"sql": "SELECT %(x)s", "params": {"x": 1}},
        )
    assert caught.value is failure
    assert driver.execute.await_count == 3
