"""Offline harness contracts. Actual SQL/RLS/ANN execution needs the isolated DB run."""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

from scripts import benchmark_retrieval_plan as target

DATABASE = "dou018_retrieval_unittest1"
ADMIN = f"postgresql://setup@127.0.0.1:55448/{DATABASE}"
APP = f"postgresql+psycopg://dou_app@127.0.0.1:55448/{DATABASE}"


@pytest.fixture(autouse=True)
def clean_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("PGSERVICE", "PGSERVICEFILE", "PGHOSTADDR", "PGOPTIONS", "PGSYSCONFDIR"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "postgresql://setup@production.example:55448/" + DATABASE,
        "postgresql://setup@localhost:55448/" + DATABASE,
        "postgresql://setup@127.0.0.1/" + DATABASE,
        "postgresql://setup@127.0.0.1:55448/postgres",
        "postgresql://setup@127.0.0.1:55448/dou018_upload",
        "postgresql://setup@127.0.0.1:55448/dou018_retrieval_short",
        "postgresql://setup@127.0.0.1:55448/dou018_retrieval_%75nittest1",
        "postgresql://setup@127.0.0.1:0/" + DATABASE,
        ADMIN + "?host=remote",
        ADMIN + "?",
        ADMIN + "#",
        ADMIN + "#fragment",
        ADMIN + " ",
        ADMIN.replace("postgresql", "sqlite"),
    ],
)
def test_rejects_nonisolated_or_ambiguous_targets(raw: str) -> None:
    with pytest.raises(ValueError):
        target.parse_connection(raw)


def test_matching_target_uses_real_app_and_explicit_libpq_route() -> None:
    admin, app = target.validate_connections(ADMIN, APP)
    assert admin.database == app.database == DATABASE
    assert app.kwargs()["hostaddr"] == "127.0.0.1"
    assert app.kwargs()["port"] == 55448
    assert app.kwargs()["user"] == "dou_app"
    assert "service" not in app.kwargs()
    assert app.kwargs()["prepare_threshold"] is None
    assert app.kwargs()["options"] == "-c statement_timeout=120000 -c lock_timeout=5000"
    assert app.kwargs()["password"] == ""
    assert "password" not in app.public()


@pytest.mark.parametrize(
    "other",
    [
        APP.replace("55448", "55449"),
        APP + "0",
        APP.replace("dou_app@", "dou_worker@"),
        APP.replace("127.0.0.1", "[::1]"),
    ],
)
def test_mismatched_database_port_host_or_role_is_rejected(other: str) -> None:
    with pytest.raises(ValueError):
        target.validate_connections(ADMIN, other)


def test_parser_and_repr_do_not_echo_credentials() -> None:
    sentinel = "synthetic-credential-marker"
    valid = ADMIN.replace("setup@", f"setup:{sentinel}@")
    assert sentinel not in repr(target.parse_connection(valid))
    with pytest.raises(ValueError) as error:
        target.parse_connection(valid.replace("55448", "not-a-port"))
    assert sentinel not in str(error.value)


@pytest.mark.parametrize(
    "name", ["PGSERVICE", "PGSERVICEFILE", "PGHOSTADDR", "PGOPTIONS", "PGSYSCONFDIR"]
)
def test_ambient_libpq_routes_cannot_override_guard(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    monkeypatch.setenv(name, "synthetic-route")
    with pytest.raises(ValueError, match="overrides"):
        target.validate_connections(ADMIN, APP)


@pytest.mark.parametrize(
    "change",
    [
        {"rows": 19999},
        {"rows": 50001},
        {"seed": -1},
        {"limit": 7},
        {"limit": 33},
        {"multiplier": 1},
        {"multiplier": 9},
        {"repeats": 2},
        {"repeats": 10},
        {"warmups": 3},
        {"deadline_seconds": 3601},
    ],
)
def test_experiment_budget_is_bounded(change: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        replace(target.Config(), **change).validate()


def test_default_is_offline_plan_with_complete_budget_and_source_hashes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Default must never execute/connect")

    monkeypatch.setattr(target, "execute", forbidden)
    assert target.main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "planned"
    assert report["prepare_threshold"] is None
    assert "runtime prepared/generic parity not claimed" in report["plan_mode"]
    assert sum(report["course_counts"].values()) == 20000
    assert report["budget"] == {
        "cases": 14,
        "arms": 3,
        "measured_queries": 420,
        "warmup_queries": 84,
        "explain_analyze_queries": 98,
    }
    assert len(report["case_ids"]) == len(set(report["case_ids"])) == 14
    assert set(report["query_sha256"]) == set(report["case_ids"])
    for name, digest in report["sql_sha256"].items():
        assert digest == target.sha256(report["sql"][name].encode())
    for name, digest in report["source_sha256"].items():
        assert digest == target.sha256((target.ROOT / name).read_bytes())


def test_source_hashes_are_content_based_and_mirrored_uuid_order_really_flips() -> None:
    docs = target.documents(target.Config())
    assert sum(doc.count for doc in docs) == 20000
    assert len({doc.id for doc in docs}) == len(docs)
    for kind in ("fit", "overflow"):
        left = [doc for doc in docs if doc.course == f"tie_{kind}_0"]
        right = [doc for doc in docs if doc.course == f"tie_{kind}_1"]
        assert [doc.file_hash for doc in left] == [doc.file_hash for doc in right]
        assert [doc.id for doc in left] != [doc.id for doc in right]
        assert left[0].id < left[1].id and right[0].id > right[1].id
        for doc in left + right:
            assert doc.file_hash == target.sha256(
                target.source_bytes(f"tie_{kind}", doc.logical, doc.count)
            )
            assert doc.file_hash != doc.id.hex
    fit_count = sum(doc.count for doc in docs if doc.course == "tie_fit_0")
    overflow_count = sum(doc.count for doc in docs if doc.course == "tie_overflow_0")
    assert 24 < fit_count <= 24 * 8 < overflow_count


def test_vectors_are_reproducible_nonzero_1024d_and_seed_sensitive() -> None:
    for ordinal in (0, 1, 8, 19999):
        value = target.vector(18026, ordinal)
        numbers = json.loads(value)
        assert len(numbers) == 1024
        assert sum(number * number for number in numbers) > 0
        assert value == target.vector(18026, ordinal)
        assert value != target.vector(18027, ordinal)
    tied = json.loads(target.vector(18026, 0, tie=True))
    assert tied == [0] * 1023 + [1]


def test_baseline_literal_is_not_reimplemented_and_candidates_keep_bound_scope() -> None:
    baseline = target.baseline_sql()
    assert "ORDER BY distance, c.document_id, c.chunk_index" in baseline
    assert "% (" not in baseline
    for materialized in (False, True):
        query = target.candidate_sql(materialized=materialized)
        assert query.lstrip().startswith("WITH nearest AS")
        inner = query.split("LIMIT %(candidate_limit)s")[0]
        order = inner.split("ORDER BY")[1].strip()
        assert order == "c.embedding <=> CAST(%(query_vector)s AS vector)"
        assert ("AS MATERIALIZED" in query) is materialized
        assert target.FILTER in query
        assert "ORDER BY n.distance + 0, d.file_hash, n.chunk_index" in query
    assert "d.file_hash, c.chunk_index" in target.exact_sql()


def test_changed_runtime_bind_contract_is_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / target.DENSE_PATH
    source.parent.mkdir(parents=True)
    source.write_text('_SQL = text("SELECT :unreviewed")')
    with pytest.raises(ValueError, match="bind contract"):
        target.runtime_sql(tmp_path)


class Result:
    def __init__(self, value: Any):
        self.value = value

    def fetchone(self) -> Any:
        return self.value

    def fetchall(self) -> Any:
        return self.value


class ClaimConnection:
    def __init__(self, *, locked: bool = True, occupied: bool = False, claimed: bool = False):
        self.locked, self.occupied, self.claimed = locked, occupied, claimed
        self.queries: list[str] = []

    @contextmanager
    def transaction(self) -> Any:
        yield

    def execute(self, query: str, params: Any = None) -> Result:
        self.queries.append(query)
        if "pg_try_advisory_lock" in query:
            return Result({"locked": self.locked})
        if "AS occupied" in query:
            return Result({"occupied": self.occupied, "claimed": self.claimed})
        return Result(None)


@pytest.mark.parametrize("flags", [{"locked": False}, {"occupied": True}, {"claimed": True}])
def test_existing_or_busy_database_is_never_modified(flags: dict[str, bool]) -> None:
    conn = ClaimConnection(**flags)
    with pytest.raises(ValueError):
        target.claim_empty_database(conn, target.Config())
    assert not any(
        re.search(r"\b(CREATE|INSERT|DELETE|DROP|TRUNCATE)\b", query) for query in conn.queries
    )


def test_empty_database_gets_one_use_marker_without_destructive_cleanup() -> None:
    conn = ClaimConnection()
    target.claim_empty_database(conn, target.Config())
    assert (
        sum("CREATE TABLE public.dou018_retrieval_benchmark_run" in query for query in conn.queries)
        == 1
    )
    assert not any(re.search(r"\b(DELETE|DROP|TRUNCATE)\b", query) for query in conn.queries)


@pytest.mark.parametrize(
    "reader,superuser,bypass", [(True, True, False), (True, False, True), (False, False, False)]
)
def test_wrong_privileges_cannot_hide_existing_data_or_fake_rls(
    reader: bool, superuser: bool, bypass: bool
) -> None:
    connection = target.parse_connection(APP if reader else ADMIN)

    class Privileges:
        def execute(self, query: str) -> Result:
            return Result(
                {
                    "database": DATABASE,
                    "role": connection.user,
                    "rolsuper": superuser,
                    "rolbypassrls": bypass,
                }
            )

    with pytest.raises(ValueError):
        target.verify_connection(Privileges(), connection, reader=reader)


def metric_fixture() -> tuple[dict[UUID, dict[str, Any]], list[dict[str, Any]]]:
    metadata = {UUID(int=index): {"key": [f"hash-{index}", 0]} for index in range(1, 7)}
    exact = [{"id": UUID(int=1), "similarity": 0.9}, {"id": UUID(int=2), "similarity": 0.8}]
    return metadata, exact


def test_equal_boundary_replacement_does_not_count_as_missing_closer_neighbor() -> None:
    metadata, exact = metric_fixture()
    rows = [exact[0], {"id": UUID(int=3), "similarity": 0.8}]
    result = target.evaluate_rows(rows, exact, set(metadata), metadata, 2)
    assert result["strict_recall"] == 0.5
    assert result["tie_aware_recall"] == 1.0
    missed_closer = [{"id": UUID(int=3), "similarity": 0.8}, {"id": UUID(int=4), "similarity": 0.8}]
    result = target.evaluate_rows(missed_closer, exact, set(metadata), metadata, 2)
    assert result["tie_aware_recall"] == 0.5


def test_empty_expected_set_is_not_reported_as_zero_recall() -> None:
    result = target.evaluate_rows([], [], set(), {}, 24)
    assert result["strict_recall"] is None and result["tie_aware_recall"] is None
    assert result["shortfall"] == 0


@pytest.mark.parametrize("failure", ["leak", "duplicate", "over_limit", "bad_oracle", "nonfinite"])
def test_scope_and_oracle_failures_cannot_be_green_metrics(failure: str) -> None:
    metadata, exact = metric_fixture()
    rows = list(exact)
    eligible = set(metadata)
    if failure == "leak":
        eligible.remove(rows[0]["id"])
    elif failure == "duplicate":
        rows = [rows[0], rows[0]]
    elif failure == "over_limit":
        rows.append({"id": UUID(int=3), "similarity": 0.7})
    elif failure == "bad_oracle":
        exact = []
    else:
        rows = [{"id": UUID(int=1), "similarity": float("nan")}]
    with pytest.raises(ValueError):
        target.evaluate_rows(rows, exact, eligible, metadata, 2)


def test_incomplete_ann_results_are_visible_shortfall_and_real_p95() -> None:
    metadata, exact = metric_fixture()
    result = target.evaluate_rows(exact[:1], exact, set(metadata), metadata, 2)
    assert result["shortfall"] == 1 and result["strict_recall"] == 0.5
    assert target.percentile95([1, 2, 3, 4, 90]) == 90
    assert target.uses_hnsw({"Plan": {"Plans": [{"Index Name": "chunks_embedding_idx"}]}})
    assert not target.uses_hnsw({"Plan": {"Node Type": "Seq Scan"}})


def test_execution_error_artifact_is_partial_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    baseline_report: Path,
) -> None:
    sentinel = "synthetic-provider-secret"

    def fail(config: target.Config, report: dict[str, Any], admin: Any, app: Any) -> None:
        report["results"] = [{"id": "already-measured"}]
        raise RuntimeError(sentinel)

    monkeypatch.setenv("RETRIEVAL_BENCH_ADMIN_DSN", ADMIN)
    monkeypatch.setenv("RETRIEVAL_BENCH_APP_DSN", APP)
    monkeypatch.setattr(target, "execute", fail)
    output = tmp_path / "evidence.json"
    assert (
        target.main(
            ["--execute", "--baseline-report", str(baseline_report), "--output", str(output)]
        )
        == 1
    )
    report = json.loads(output.read_text())
    assert report["status"] == "failed" and report["error_class"] == "RuntimeError"
    assert report["results"] == [{"id": "already-measured"}]
    assert sentinel not in output.read_text() + capsys.readouterr().err


def test_existing_output_prevents_execution(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, baseline_report: Path
) -> None:
    monkeypatch.setenv("RETRIEVAL_BENCH_ADMIN_DSN", ADMIN)
    monkeypatch.setenv("RETRIEVAL_BENCH_APP_DSN", APP)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Existing artifact must prevent execution")

    monkeypatch.setattr(target, "execute", forbidden)
    output = tmp_path / "evidence.json"
    output.write_text("existing evidence")
    assert (
        target.main(
            ["--execute", "--baseline-report", str(baseline_report), "--output", str(output)]
        )
        == 1
    )
    assert output.read_text() == "existing evidence"


class MeasuringConnection:
    """Record session controls; returned rows are explicitly fake, not SQL/RLS proof."""

    def __init__(self, rows: list[dict[str, Any]], sql: dict[str, str]):
        self.rows, self.sql = rows, sql
        self.state: dict[str, Any] = {}
        self.calls: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    @contextmanager
    def transaction(self) -> Any:
        assert not self.state, "Previous transaction controls must have been local"
        self.state = {"enable_indexscan": "on", "enable_bitmapscan": "on"}
        try:
            yield
        finally:
            self.state = {}

    def execute(self, query: str, params: Any = None) -> Result:
        if "set_config('app.current_user_id'" in query:
            assert ", true)" in query
            self.state["user"] = params[0]
        elif "set_config('hnsw." in query:
            assert ", true)" in query
            name = query.split("'")[1]
            self.state[name] = params[0]
        elif query.startswith("SET"):
            assert query.startswith("SET LOCAL ")
            self.state[query.split()[2]] = "off"
        elif "current_setting" in query:
            return Result({"value": self.state.get(params[0], "unchanged-default")})
        elif "SELECT count(*)" in query:
            assert self.state["user"] == str(target.USER_ID)
            return Result({"count": len(self.rows)})
        elif query.startswith("EXPLAIN"):
            return Result({"QUERY PLAN": [{"Plan": {"Node Type": "Seq Scan"}}]})
        else:
            name = next(name for name, value in self.sql.items() if value == query)
            self.calls.append((name, dict(params), dict(self.state)))
            return Result(self.rows)
        return Result(None)


def test_measured_arms_preserve_natural_scan_settings_scope_and_candidate_budgets() -> None:
    config = target.Config(limit=8, repeats=3, warmups=0)
    docs = target.documents(config)
    doc = docs[0]
    case = next(item for item in target.cases(config, docs) if item["id"] == "broad/q0")
    metadata = {
        target.chunk_id(doc, index): {
            "course": "broad",
            "document_id": doc.id,
            "key": [doc.file_hash, index],
        }
        for index in range(2)
    }
    rows = [
        {"id": identity, "similarity": 0.9 - index / 10} for index, identity in enumerate(metadata)
    ]
    sql = target.plan(config)["sql"]
    conn = MeasuringConnection(rows, sql)
    result = target.measure_case(conn, case, config, sql, metadata, float("inf"))
    assert len(result["arms"]) == 6
    assert all(len(arm["samples"]) == 3 for arm in result["arms"])
    assert {arm["ef_search"] for arm in result["arms"]} == {40, 100}
    assert len(conn.calls) == 19  # One exact + three measurements for six arms.
    for name, params, state in conn.calls:
        assert params["course_id"] == doc.course_id
        assert params["filter_documents"] is False
        assert params["document_ids"] == []
        assert state["user"] == str(target.USER_ID)
        if name == "exact":
            assert state["enable_indexscan"] == state["enable_bitmapscan"] == "off"
        else:
            assert state["enable_indexscan"] == state["enable_bitmapscan"] == "on"
            materialized = name == "materialized_oversampling"
            assert params["candidate_limit"] == (64 if materialized else 8)
            assert state["hnsw.iterative_scan"] == ("relaxed_order" if materialized else "off")


class SeedingConnection:
    def __init__(self) -> None:
        self.inserts: list[tuple[str, Any]] = []
        self.rows: list[tuple[Any, ...]] = []

    @contextmanager
    def transaction(self) -> Any:
        yield

    def execute(self, query: str, params: Any = None) -> Result:
        self.inserts.append((query, params))
        return Result(None)

    def cursor(self) -> SeedingConnection:
        return self

    @contextmanager
    def copy(self, query: str) -> Any:
        assert "COPY chunks" in query
        yield self

    def write_row(self, row: tuple[Any, ...]) -> None:
        self.rows.append(row)


def test_seed_streams_actual_content_hash_and_vectors_without_factory_uuid_hashes() -> None:
    config = target.Config()
    doc = target.documents(config)[0]
    doc = replace(doc, count=2, file_hash=target.sha256(target.source_bytes("broad", 0, 2)))
    conn = SeedingConnection()
    metadata, digest = target.seed_corpus(conn, config, [doc])
    assert len(conn.rows) == len(metadata) == 2
    source = "\n".join(row[4] for row in conn.rows).encode()
    assert target.sha256(source) == doc.file_hash
    expected_digest = hashlib.sha256()
    for row in conn.rows:
        identity, _, _, index, _, _, embedding, space = row
        assert metadata[identity]["key"] == [doc.file_hash, index]
        assert space == target.CORPUS_VERSION
        assert sum(value * value for value in json.loads(embedding)) > 0
        expected_digest.update(f"{identity}|{doc.file_hash}|{index}|{embedding}\n".encode())
    assert digest == expected_digest.hexdigest()
    query, params = next(item for item in conn.inserts if "INSERT INTO documents" in item[0])
    assert "'completed'" in query
    assert params[5] == doc.file_hash and params[6] == len(source)


def test_exact_oracle_out_of_scope_is_rejected_even_when_result_is_empty() -> None:
    metadata, exact = metric_fixture()
    with pytest.raises(ValueError):
        target.evaluate_rows([], exact, set(metadata) - {UUID(int=1)}, metadata, 2)


def test_candidate_projection_preserves_complete_runtime_result_contract() -> None:
    def projections(query: str) -> tuple[list[str], list[str]]:
        normalized = re.sub(r"\s+", " ", query).strip()
        inner = normalized.split("SELECT ", 1)[1].split(" FROM chunks c", 1)[0]
        outer = normalized.rsplit(" SELECT ", 1)[1].split(" FROM nearest n", 1)[0]
        return inner.split(", "), outer.split(", ")

    runtime_inner, runtime_outer = projections(target.runtime_sql())
    assert (runtime_inner, runtime_outer) == projections(target.baseline_sql())
    assert len(runtime_inner) == 9 and len(runtime_outer) == 9
    assert "c.text" in runtime_inner and "n.text" in runtime_outer
    assert "c.embedding_space" in runtime_inner and "n.embedding_space" in runtime_outer
    for materialized in (False, True):
        candidate_inner, candidate_outer = projections(
            target.candidate_sql(materialized=materialized)
        )
        assert candidate_inner == runtime_inner
        assert candidate_outer == runtime_outer


def test_projection_revision_preserves_first_experiment_corpus_and_query_identity() -> None:
    config = target.Config()
    docs = target.documents(config)
    assert target.VERSION == "dou018-synthetic-plan-v2"
    assert target.CORPUS_VERSION == "dou018-synthetic-plan-v1"
    assert str(docs[0].course_id) == "2b47c345-dc5f-5529-9a0f-4367fc4810b6"
    assert docs[0].file_hash == "a522a30f2811207b3538c343355d9e1945aa300e9641f03319e5e28dd8da4b48"
    case_hashes = {
        case["id"]: target.sha256(case["query_vector"].encode())
        for case in target.cases(config, docs)
    }
    assert (
        case_hashes["broad/q0"]
        == "2fe78dc54145bb6d15536b19ecc74503a412f8861cb19fdc5e066644dc832294"
    )
    assert (
        case_hashes["broad/q1"]
        == "05dd7747711d4895ca35bad12ba7467344890c025bef0b6882aaff46fbf8e138"
    )


@pytest.fixture
def baseline_report(tmp_path: Path) -> Path:
    path = tmp_path / "measured-v2.json"
    path.write_text(
        json.dumps(
            {
                "status": "measured",
                "version": "dou018-synthetic-plan-v2",
                "sql": {"baseline": target.baseline_sql()},
                "sql_sha256": {"baseline": target.PRE_C1_SQL_SHA256},
                "source_sha256": {str(target.DENSE_PATH): target.PRE_C1_DENSE_SOURCE_SHA256},
            }
        )
    )
    return path


@pytest.mark.parametrize("mutation", ["sql", "source", "status", "version"])
def test_baseline_report_cannot_supply_arbitrary_sql_or_unverified_lineage(
    baseline_report: Path, mutation: str
) -> None:
    report = json.loads(baseline_report.read_text())
    if mutation == "sql":
        report["sql"]["baseline"] = "DELETE FROM chunks"
        report["sql_sha256"]["baseline"] = target.sha256(b"DELETE FROM chunks")
    elif mutation == "source":
        report["source_sha256"][str(target.DENSE_PATH)] = "0" * 64
    else:
        report[mutation] = "unverified"
    baseline_report.write_text(json.dumps(report))
    with pytest.raises(ValueError, match="known pre-C1"):
        target.baseline_sql(baseline_report=baseline_report)


def test_pinned_baseline_is_distinct_from_current_runtime(baseline_report: Path) -> None:
    result = target.plan(target.Config(), baseline_report=baseline_report)
    assert result["baseline_provenance"]["source_sha256"] == target.PRE_C1_DENSE_SOURCE_SHA256
    assert result["baseline_provenance"]["measured_report_sha256"] == target.sha256(
        baseline_report.read_bytes()
    )
    assert result["sql"]["baseline"] == target.baseline_sql()
    assert result["sql_sha256"]["baseline"] == target.PRE_C1_SQL_SHA256
    assert "LIMIT %(candidate_limit)s" in target.runtime_sql()


def test_execute_requires_explicit_baseline_proof_before_connection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("No baseline proof must mean no connection")

    monkeypatch.setattr(target, "execute", forbidden)
    assert target.main(["--execute", "--output", str(tmp_path / "out.json")]) == 1
    assert not (tmp_path / "out.json").exists()
