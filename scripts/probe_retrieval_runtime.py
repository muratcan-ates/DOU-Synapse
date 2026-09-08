"""Read-only SQLAlchemy/psycopg HybridRetriever probe on an explicitly cloned corpus.

This does not ingest, clone, update namespaces, or disable provenance checks. The
operator clones the measured database and changes only embedding_space to the
canonical SyntheticReplayProvider identity. Original evidence stays immutable.
Synthetic replay tests the runtime SQL/driver path, not real model quality.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import statistics
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from typing import Any

from scripts import benchmark_retrieval_plan as bench

VERSION = "dou018-runtime-prepared-v2"
MODES = ("auto", "force_custom_plan", "force_generic_plan")
FORBIDDEN_ENV = {
    "PGSERVICE",
    "PGSERVICEFILE",
    "PGHOSTADDR",
    "PGOPTIONS",
    "PGSYSCONFDIR",
}
PREPARED_SQL = """SELECT name, statement, parameter_types::text AS parameter_types,
    generic_plans, custom_plans FROM pg_prepared_statements ORDER BY name"""


class SyntheticReplayProvider:
    """Exact saved query vectors; deliberately a distinct canonical provider class."""

    name = bench.CORPUS_VERSION
    dimension = bench.DIMENSIONS

    def __init__(self, query_cases: list[dict[str, Any]]) -> None:
        self._vectors = {case["id"]: json.loads(case["query_vector"]) for case in query_cases}

    def embed_query(self, text: str) -> list[float]:
        return list(self._vectors[text])

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("Read-only replay provider cannot ingest documents.")


def load_source(
    path: Path,
) -> tuple[dict[str, Any], bench.Config, list[dict[str, Any]]]:
    bench.baseline_sql(baseline_report=path)  # Known literal SQL/source proof, never executed.
    source = json.loads(path.read_text())
    config = bench.Config(**source["config"])
    config.validate()
    docs = bench.documents(config)
    query_cases = bench.cases(config, docs)
    expected = {case["id"]: bench.sha256(case["query_vector"].encode()) for case in query_cases}
    expected_docs = [
        {**asdict(doc), "id": str(doc.id), "course_id": str(doc.course_id)} for doc in docs
    ]
    if (
        source.get("corpus_version") != bench.CORPUS_VERSION
        or source.get("dimensions") != bench.DIMENSIONS
        or source.get("query_sha256") != expected
        or source.get("case_ids") != list(expected)
        or source.get("corpus", {}).get("rows") != config.rows
        or source.get("corpus", {}).get("documents") != expected_docs
        or not re.fullmatch(r"[a-f0-9]{64}", source.get("corpus", {}).get("sha256", ""))
    ):
        raise ValueError("Source corpus/query manifest does not match deterministic replay.")
    return source, config, query_cases


def validate_target(raw: str, source: dict[str, Any]) -> bench.Connection:
    target = bench.parse_connection(raw)
    original = source["connections"]["target"]
    if (
        target.user != bench.APP_ROLE
        or target.database == original["database"]
        or (target.host, target.port) != (original["host"], original["port"])
        or FORBIDDEN_ENV.intersection(os.environ)
    ):
        raise ValueError("Use a new isolated clone on the measured loopback server as dou_app.")
    return target


def prepared_template(template: str, params: dict[str, Any]) -> tuple[str, list[Any]]:
    """Derive server $n SQL from the captured, known runtime pyformat statement.

    Repeated names share one server parameter. Arbitrary statement text from a
    report is never interpreted or executed; callers capture current runtime SQL.
    """
    names: list[str] = []

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in names:
            names.append(name)
        return "$" + str(names.index(name) + 1)

    server = re.sub(r"%\((\w+)\)s", replace, template).strip()
    if not names or set(names) != set(params) or "%" in server:
        raise ValueError("Unexpected runtime driver parameter contract.")
    return server, [params[name] for name in names]


async def start_readonly(session: Any, mode: str, user: Any) -> None:
    from app.core.db import set_rls_context
    from sqlalchemy import text

    if mode not in MODES:
        raise ValueError("Unsupported plan mode.")
    # This must precede any data SELECT in every transaction.
    await session.execute(text("SET TRANSACTION READ ONLY"))
    await session.execute(text("SELECT set_config('statement_timeout', '120000', true)"))
    await session.execute(text("SELECT set_config('plan_cache_mode', :mode, true)"), {"mode": mode})
    await set_rls_context(session, user)
    if (await session.execute(text("SHOW transaction_read_only"))).scalar_one() != "on":
        raise ValueError("Read-only transaction is required.")


async def prepared_inventory(session: Any, captures: dict[str, Any]) -> list[dict[str, Any]]:
    from sqlalchemy import text

    by_sql = {prepared_template(c["sql"], c["params"])[0]: lane for lane, c in captures.items()}
    result = []
    for row in (await session.execute(text(PREPARED_SQL))).mappings():
        lane = by_sql.get(row["statement"].strip())
        if lane:
            result.append({**dict(row), "lane": lane})
    return result


async def explain_prepared(
    driver: Any, prepared: dict[str, Any], capture: dict[str, Any]
) -> dict[str, Any]:
    from psycopg import sql

    server, values = prepared_template(capture["sql"], capture["params"])
    if server != prepared["statement"].strip():
        raise ValueError("Prepared statement does not match the captured runtime query.")
    # Identifiers and values are psycopg-quoted. The command executes a statement
    # created by real HybridRetriever calls on this same physical connection.
    command = sql.SQL("EXPLAIN (ANALYZE, BUFFERS, SETTINGS, FORMAT JSON) EXECUTE {} ({})").format(
        sql.Identifier(prepared["name"]),
        sql.SQL(", ").join(sql.Literal(value) for value in values),
    )
    previous_cursor = await driver.execute("SHOW plan_cache_mode", prepare=False)
    previous_row = await previous_cursor.fetchone()
    if previous_row is None:
        raise ValueError("Cannot verify prepared EXPLAIN policy.")
    previous_mode = previous_row[0]
    effective_mode = previous_mode
    if prepared["lane"] == "dense":
        effective_mode = "force_custom_plan"
        await driver.execute(
            "SELECT set_config('plan_cache_mode', 'force_custom_plan', true)", prepare=False
        )
    cursor = await driver.execute(command, prepare=False)
    row = await cursor.fetchone()
    if prepared["lane"] == "dense":
        await driver.execute(
            "SELECT set_config('plan_cache_mode', %s, true)", (previous_mode,), prepare=False
        )
    if row is None:
        raise ValueError("Prepared EXPLAIN returned no plan.")
    plan = row[0][0]
    return {
        "name": prepared["name"],
        "lane": prepared["lane"],
        "hnsw": bench.uses_hnsw(plan),
        "plan": plan,
        "effective_plan_mode": effective_mode,
        "restored_caller_mode": previous_mode,
        "capture_kind": "separate execution of same prepared statement under runtime lane policy",
    }


def measured_counter_deltas(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
    mode: str,
    repeats: int,
) -> list[dict[str, Any]]:
    """Yalnız zamanlanan çağrıları say; EXPLAIN bu kayıttan sonra çalışır."""
    prior = {item["name"]: item for item in before}
    active = []
    for item in after:
        if item["name"] not in prior:
            raise ValueError("Warmup did not establish a prepared statement before timing.")
        generic = item["generic_plans"] - prior[item["name"]]["generic_plans"]
        custom = item["custom_plans"] - prior[item["name"]]["custom_plans"]
        if min(generic, custom) < 0:
            raise ValueError("Prepared counters regressed.")
        if generic + custom:
            active.append(
                {
                    "name": item["name"],
                    "lane": item["lane"],
                    "generic_plans": generic,
                    "custom_plans": custom,
                }
            )
    for lane in ("dense", "fts"):
        changes = [item for item in active if item["lane"] == lane]
        generic = sum(item["generic_plans"] for item in changes)
        custom = sum(item["custom_plans"] for item in changes)
        if generic + custom != repeats:
            raise ValueError("Timed calls did not execute the prepared runtime lane.")
        if (lane == "dense" or mode == "force_custom_plan") and custom != repeats:
            raise ValueError("Dense runtime policy failed to retain custom plans.")
        if lane == "fts" and mode == "force_generic_plan" and generic != repeats:
            raise ValueError("Dense custom-plan policy leaked into FTS.")
    return active


def check_rows(
    rows: list[Any],
    case: dict[str, Any],
    metadata: dict[Any, dict[str, Any]],
    limit: int,
) -> list[list[Any]]:
    keys = []
    seen = set()
    for row in rows:
        item = metadata.get(row.chunk_id)
        if (
            item is None
            or row.chunk_id in seen
            or item["course_id"] != case["course_id"]
            or case["course"] == "unrelated"
            or (case["filter_documents"] and row.document_id not in case["document_ids"])
        ):
            raise ValueError("Runtime returned an ineligible or duplicate chunk.")
        expected = (
            item["document_id"],
            item["file_name"],
            item["page_number"],
            item["slide_number"],
            item["section_title"],
            item["text"],
        )
        actual = (
            row.document_id,
            row.file_name,
            row.page_number,
            row.slide_number,
            row.section_title,
            row.text,
        )
        if actual != expected:
            raise ValueError("Runtime source/citation metadata changed.")
        seen.add(row.chunk_id)
        keys.append([item["file_hash"], item["chunk_index"]])
    if len(rows) > limit:
        raise ValueError("Runtime exceeded requested result limit.")
    if (
        case["course"] != "unrelated"
        and not (case["filter_documents"] and not case["document_ids"])
        and not rows
    ):
        raise ValueError("Runtime unexpectedly returned no eligible source.")
    return keys


async def verify_clone(
    session: Any, target: bench.Connection, config: bench.Config, namespace: str
) -> tuple[dict[str, Any], dict[Any, dict[str, Any]]]:
    from sqlalchemy import text

    identity = dict(
        (
            await session.execute(
                text("""SELECT current_database() AS database,
        current_user AS role, rolsuper, rolbypassrls, pg_backend_pid() AS backend_pid
        FROM pg_roles WHERE rolname=current_user""")
            )
        )
        .mappings()
        .one()
    )
    if (
        identity["database"] != target.database
        or identity["role"] != bench.APP_ROLE
        or identity["rolsuper"]
        or identity["rolbypassrls"]
    ):
        raise ValueError("Runtime must use the real non-bypass application role.")
    policies = [
        dict(row)
        for row in (
            await session.execute(
                text("""SELECT relname,
        relrowsecurity, relforcerowsecurity FROM pg_class
        WHERE oid IN ('public.chunks'::regclass,'public.documents'::regclass)""")
            )
        ).mappings()
    ]
    if len(policies) != 2 or any(
        not row["relrowsecurity"] or not row["relforcerowsecurity"] for row in policies
    ):
        raise ValueError("Forced RLS must remain enabled on both runtime tables.")
    rows = (
        (
            await session.execute(
                text("""SELECT c.id, c.course_id, c.document_id,
        c.chunk_index, c.page_number, c.slide_number, c.section_title, c.text,
        c.embedding_space, d.file_name, d.file_hash FROM chunks c
        JOIN documents d ON d.id=c.document_id ORDER BY c.id""")
            )
        )
        .mappings()
        .all()
    )
    if len(rows) != config.rows or {row["embedding_space"] for row in rows} != {namespace}:
        raise ValueError("Clone count/namespace does not match the canonical replay provider.")
    docs = bench.documents(config)
    expected = {bench.chunk_id(doc, i): (doc, i) for doc in docs for i in range(doc.count)}
    metadata = {}
    digest = hashlib.sha256()
    for row in rows:
        if row["id"] not in expected:
            raise ValueError("Unexpected clone chunk identity.")
        doc, index = expected[row["id"]]
        kind = doc.course.rsplit("_", 1)[0] if doc.course.startswith("tie_") else doc.course
        if (
            row["document_id"] != doc.id
            or row["course_id"] != doc.course_id
            or row["chunk_index"] != index
            or row["file_hash"] != doc.file_hash
            or row["file_name"] != f"synthetic-{doc.logical}.txt"
            or row["text"] != f"Synthetic {kind} document {doc.logical} chunk {index}."
            or any(row[key] is not None for key in ("page_number", "slide_number", "section_title"))
        ):
            raise ValueError("Clone content/source metadata differs from the measured fixture.")
        metadata[row["id"]] = dict(row)
        digest.update(json.dumps(dict(row), sort_keys=True, default=str).encode() + b"\n")
    environment = {
        **identity,
        "schema": policies,
        "rows": len(rows),
        "metadata_sha256": digest.hexdigest(),
        "postgresql": (await session.execute(text("SELECT version()"))).scalar_one(),
        "vector": (
            await session.execute(
                text("SELECT extversion FROM pg_extension WHERE extname='vector'")
            )
        ).scalar_one(),
        "gucs": {
            name: (
                await session.execute(text("SELECT current_setting(:name, true)"), {"name": name})
            ).scalar_one()
            for name in bench.GUCS
        },
    }
    return environment, metadata


async def execute(
    target: bench.Connection,
    source: dict[str, Any],
    config: bench.Config,
    query_cases: list[dict[str, Any]],
    report: dict[str, Any],
    repeats: int,
) -> None:
    from app.core.config import Settings
    from app.core.db import _build_engine
    from app.core.vector_space import space_of
    from app.modules.ingestion.embedding import set_embedding_provider
    from app.modules.retrieval import dense, fts
    from app.modules.retrieval.service import HybridRetriever
    from sqlalchemy import URL, event, text
    from sqlalchemy.ext.asyncio import AsyncSession

    url = URL.create(
        "postgresql+psycopg",
        username=target.user,
        password=target.password,
        host=target.host,
        port=target.port,
        database=target.database,
    ).render_as_string(hide_password=False)
    settings = Settings(
        _env_file=None,
        environment="local",
        dev_auth_enabled=True,
        database_url=url,
        embedding_provider="hashing",
        groq_api_key=None,
        gemini_api_key=None,
        openai_api_key=None,
        db_pool_size=1,
        db_max_overflow=0,
        retrieval_dense_candidates=config.limit,
        retrieval_dense_candidate_multiplier=8,
        retrieval_fts_candidates=config.limit,
    )
    engine = _build_engine(settings)

    @event.listens_for(engine.sync_engine, "do_connect")
    def constrain_route(dialect: Any, conn_rec: Any, cargs: Any, cparams: dict[str, Any]) -> None:
        # Preserve runtime psycopg preparation defaults; bound routing and SQL writes.
        cparams.update(
            hostaddr=target.host,
            passfile=os.devnull,
            sslmode="disable",
            connect_timeout=5,
            application_name=VERSION,
            options=(
                "-c default_transaction_read_only=on "
                "-c statement_timeout=120000 -c lock_timeout=5000"
            ),
        )

    known = {
        str(query.compile(dialect=engine.sync_engine.dialect)).strip(): lane
        for lane, query in (("dense", dense._SQL), ("fts", fts._SQL))
    }
    captures: dict[str, Any] = {}

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def capture_runtime(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        lane = known.get(statement.strip())
        if lane:
            if executemany or not isinstance(parameters, dict):
                raise ValueError("Unexpected runtime execution shape.")
            captures[lane] = {
                "sql": statement,
                "params": dict(parameters),
                "rowcount": cursor.rowcount,
            }

    provider = SyntheticReplayProvider(query_cases)
    set_embedding_provider(provider)
    start = time.monotonic()
    try:
        async with engine.connect() as connection:
            raw = await connection.get_raw_connection()
            driver = raw.driver_connection
            if driver is None:
                raise ValueError("Expected an active runtime driver connection.")
            report["prepare_threshold"] = driver.prepare_threshold
            if driver.prepare_threshold is None or driver.prepare_threshold > 10:
                raise ValueError("Expected bounded enabled runtime psycopg preparation.")
            report["phase"] = "verify_clone"
            async with AsyncSession(bind=connection) as session, session.begin():
                await start_readonly(session, "auto", bench.OWNER_ID)
                environment, metadata = await verify_clone(
                    session, target, config, space_of(provider)
                )
                report["environment"] = environment
            report["results"] = []
            auto_keys: dict[str, Any] = {}
            for mode in MODES:
                for case in query_cases:
                    if time.monotonic() - start > 900:
                        raise TimeoutError("Bounded probe deadline reached.")
                    report["phase"] = f"runtime/{mode}/{case['id']}"
                    async with (
                        AsyncSession(bind=connection) as session,
                        session.begin(),
                    ):
                        await start_readonly(session, mode, case["user"])
                        assert (
                            await session.execute(text("SELECT pg_backend_pid()"))
                        ).scalar_one() == environment["backend_pid"]
                        retriever = HybridRetriever(
                            session,
                            settings,
                            document_ids=tuple(case["document_ids"])
                            if case["filter_documents"]
                            else None,
                        )
                        # Each case warms every parameter type beyond psycopg's default
                        # threshold, then records real HybridRetriever calls.
                        for _ in range(12):
                            await retriever.search(
                                course_id=case["course_id"], query=case["id"], limit=8
                            )
                        before = await prepared_inventory(session, captures)
                        if {item["lane"] for item in before} != {"dense", "fts"}:
                            raise ValueError(
                                "Real runtime calls did not create both prepared queries."
                            )
                        latencies, observations = [], []
                        for _ in range(repeats):
                            started = time.perf_counter()
                            rows = await retriever.search(
                                course_id=case["course_id"], query=case["id"], limit=8
                            )
                            latencies.append((time.perf_counter() - started) * 1000)
                            if (
                                await session.execute(text("SHOW plan_cache_mode"))
                            ).scalar_one() != mode:
                                raise ValueError(
                                    "Dense plan policy escaped into caller transaction."
                                )
                            keys = check_rows(rows, case, metadata, 8)
                            observations.append(
                                {
                                    "count": len(rows),
                                    "keys": keys,
                                    "lane_counts": {
                                        lane: item["rowcount"] for lane, item in captures.items()
                                    },
                                }
                            )
                        after = await prepared_inventory(session, captures)
                        deltas = measured_counter_deltas(before, after, mode, repeats)
                        active_names = {item["name"] for item in deltas}
                        plans = []
                        # Gerçek hazırlanmış sorguyu şeridin aynı politikasıyla
                        # ayrıca çalıştır; bu, zamanlanan SELECT'in plan kaydı değildir.
                        for item in after:
                            if item["name"] not in active_names:
                                continue
                            plans.append(
                                await explain_prepared(driver, item, captures[item["lane"]])
                            )
                        if mode == "auto":
                            auto_keys[case["id"]] = observations[0]["keys"]
                        report["results"].append(
                            {
                                "mode": mode,
                                "case": case["id"],
                                "latency_ms": latencies,
                                "p50_ms": statistics.median(latencies),
                                "p95_ms": bench.percentile95(latencies),
                                "observations": observations,
                                "same_content_order_as_auto": all(
                                    o["keys"] == auto_keys[case["id"]] for o in observations
                                ),
                                "measured_counter_deltas": deltas,
                                "caller_mode_after_timed_calls": mode,
                                "prepared_before": before,
                                "prepared_after": after,
                                "prepared_plans": plans,
                            }
                        )
            report["status"] = "measured"
            report["phase"] = "complete"
            report["elapsed_seconds"] = time.monotonic() - start
    finally:
        set_embedding_provider(None)
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, choices=range(3, 10), default=7)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    report: dict[str, Any] = {
        "version": VERSION,
        "status": "planned",
        "phase": "validate",
    }
    # Reserve new artifact before doing work. Refuse to overwrite any prior evidence.
    with args.output.open("x") as output:
        try:
            source, config, query_cases = load_source(args.source_report)
            from app.core.vector_space import space_of
            from app.modules.retrieval import dense, fts

            report.update(
                source_report_sha256=bench.sha256(args.source_report.read_bytes()),
                source_corpus_sha256=source["corpus"]["sha256"],
                query_sha256=source["query_sha256"],
                namespace=space_of(SyntheticReplayProvider(query_cases)),
                modes=list(MODES),
                repeats=args.repeats,
                warmups_per_case=12,
                cases=[case["id"] for case in query_cases],
                config={**asdict(config), "runtime_multiplier": 8, "hybrid_limit": 8},
                source_sha256={
                    str(path): bench.sha256((bench.ROOT / path).read_bytes())
                    for path in [
                        bench.DENSE_PATH,
                        Path("apps/api/app/modules/retrieval/fts.py"),
                        Path("apps/api/app/modules/retrieval/service.py"),
                        Path("apps/api/app/core/db.py"),
                        Path("apps/api/app/core/config.py"),
                        Path("scripts/probe_retrieval_runtime.py"),
                    ]
                },
                runtime_sql={"dense": str(dense._SQL), "fts": str(fts._SQL)},
                runtime_sql_sha256={
                    "dense": bench.sha256(str(dense._SQL).encode()),
                    "fts": bench.sha256(str(fts._SQL).encode()),
                },
                libraries={name: version(name) for name in ("sqlalchemy", "psycopg", "pgvector")},
                python=sys.version,
                interpretation=[
                    (
                        "Real HybridRetriever/SQLAlchemy/psycopg execution; synthetic replay "
                        "provider, not E5/LLM quality."
                    ),
                    (
                        "Only a separately cloned DB is accepted. Operator must preserve original "
                        "DB/report and record clone plus embedding_space-only relabel lineage."
                    ),
                    (
                        "Probe verifies all visible source metadata and canonical namespaces. It "
                        "does not re-hash stored vectors; vector preservation requires clone "
                        "lineage evidence."
                    ),
                    (
                        "Prepared counters precede EXPLAIN EXECUTE. Dense plans are separately "
                        "executed under force_custom_plan and restored; FTS retains caller mode."
                    ),
                    (
                        "Read-only startup and per-transaction enforcement; natural planner, no "
                        "index forcing. Local and CI pgvector versions are not equated."
                    ),
                    (
                        "Full HybridRetriever latency includes Python/thread/FTS/fusion work; it "
                        "is not directly comparable to dense-only benchmark latency."
                    ),
                    (
                        "FTS receives synthetic case labels. This checks driver/filter/source "
                        "mechanics, not representative lexical quality."
                    ),
                ],
            )
            if args.execute:
                target = validate_target(os.environ.get("RETRIEVAL_PROBE_APP_DSN", ""), source)
                report["target"] = target.public()
                asyncio.run(execute(target, source, config, query_cases, report, args.repeats))
            else:
                report["phase"] = "await_explicit_execution_on_operator_clone"
        except Exception as exc:  # Sanitized partial evidence; never log raw DSN/errors.
            report.update(status="failed", error_type=type(exc).__name__)
        json.dump(report, output, ensure_ascii=False, indent=2, default=str)
        output.write("\n")
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
