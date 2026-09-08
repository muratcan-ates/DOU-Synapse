#!/usr/bin/env python3
"""Bounded synthetic C1 query-plan experiment; no runtime query or migration edits.

Default: print a plan without connecting. --execute requires an already migrated,
empty, uniquely named local database and explicit RETRIEVAL_BENCH_ADMIN_DSN and
RETRIEVAL_BENCH_APP_DSN. This script NEVER creates/drops databases or shared roles.
It leaves its synthetic data and one-use marker for inspection; a repeat needs a
new database. Run with the API virtualenv (existing psycopg dependency).

This measures PostgreSQL planning/ANN mechanics, NOT semantic retrieval quality.
C2 maintenance_work_mem interventions and production/CI parity remain unmeasured.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

ROOT = Path(__file__).resolve().parents[1]
DENSE_PATH = Path("apps/api/app/modules/retrieval/dense.py")
BASELINE_FIXTURE = Path("scripts/fixtures/018_pre_c1_dense.sql")
PRE_C1_DENSE_SOURCE_SHA256 = "73d5db65f49a279f17d62bba92f740df5ab8a490b6b8c331e84917089cf6e7dd"
PRE_C1_SQL_SHA256 = "595cc7bc969da0b415cdd1b62aa1b8cd698534c2052c7c79be92c4075f630fd5"
DIMENSIONS = 1024
VERSION = "dou018-synthetic-plan-v2"
CORPUS_VERSION = "dou018-synthetic-plan-v1"
APP_ROLE = "dou_app"
USER_ID = uuid5(NAMESPACE_URL, CORPUS_VERSION + "/student")
OWNER_ID = uuid5(NAMESPACE_URL, CORPUS_VERSION + "/instructor")
OUTSIDER_ID = uuid5(NAMESPACE_URL, CORPUS_VERSION + "/outsider")
GUCS = (
    "work_mem",
    "maintenance_work_mem",
    "shared_buffers",
    "effective_cache_size",
    "random_page_cost",
    "seq_page_cost",
    "max_parallel_workers_per_gather",
    "enable_seqscan",
    "enable_indexscan",
    "enable_bitmapscan",
    "enable_sort",
    "hnsw.ef_search",
    "hnsw.iterative_scan",
    "hnsw.max_scan_tuples",
    "hnsw.scan_mem_multiplier",
    "row_security",
    "plan_cache_mode",
    "jit",
    "statement_timeout",
)
FILTER = """
    c.course_id = %(course_id)s
    AND (NOT CAST(%(filter_documents)s AS boolean)
         OR c.document_id = ANY(CAST(%(document_ids)s AS uuid[])))
    AND c.embedding IS NOT NULL
"""


@dataclass(frozen=True)
class Config:
    rows: int = 20_000
    seed: int = 18026
    limit: int = 24
    multiplier: int = 8
    repeats: int = 5
    warmups: int = 1
    deadline_seconds: int = 1800

    def validate(self) -> None:
        if not (20_000 <= self.rows <= 50_000 and 0 <= self.seed <= 2**32 - 1):
            raise ValueError("Rows must be 20000..50000 and seed an unsigned 32-bit integer.")
        if not (8 <= self.limit <= 32 and 2 <= self.multiplier <= 8):
            raise ValueError("Limit must be 8..32; candidate multiplier must be 2..8.")
        if not (3 <= self.repeats <= 9 and 0 <= self.warmups <= 2):
            raise ValueError("Repeats must be 3..9 and warmups 0..2.")
        if not 60 <= self.deadline_seconds <= 3600:
            raise ValueError("Deadline must be 60..3600 seconds.")


@dataclass(frozen=True)
class Connection:
    host: str
    port: int
    database: str
    user: str
    password: str = field(repr=False)

    def public(self) -> dict[str, str | int]:
        return {"host": self.host, "port": self.port, "database": self.database, "user": self.user}

    def kwargs(self) -> dict[str, Any]:
        # Explicit route and options defeat libpq environment fallbacks. No service,
        # passfile, remote SSL, startup search_path, or inherited role switch.
        return {
            "host": self.host,
            "hostaddr": self.host,
            "port": self.port,
            "dbname": self.database,
            "user": self.user,
            "password": self.password,
            "passfile": os.devnull,
            "sslmode": "disable",
            "options": "-c statement_timeout=120000 -c lock_timeout=5000",
            "connect_timeout": 5,
            "application_name": VERSION,
            "autocommit": True,
            "prepare_threshold": None,
        }


def parse_connection(raw: str) -> Connection:
    try:
        url = urlsplit(raw)
        if (
            url.scheme not in {"postgresql", "postgresql+psycopg"}
            or url.hostname not in {"127.0.0.1", "::1"}
            or url.port is None
            or not 1 <= url.port <= 65535
            or url.query
            or url.fragment
            or "?" in raw
            or "#" in raw
            or any(char.isspace() for char in raw)
            or not re.fullmatch(r"/dou018_retrieval_[a-z0-9][a-z0-9_]{7,31}", url.path)
            or not url.username
        ):
            raise ValueError
        return Connection(
            url.hostname,
            url.port,
            url.path[1:],
            unquote(url.username),
            unquote(url.password or ""),
        )
    except (ValueError, TypeError):
        # Never propagate a parser exception that can include the raw credential.
        raise ValueError(
            "Expected explicit loopback PostgreSQL DSN for unique dou018_retrieval_* DB."
        ) from None


def validate_connections(admin_raw: str, app_raw: str) -> tuple[Connection, Connection]:
    admin, app = parse_connection(admin_raw), parse_connection(app_raw)
    if (admin.host, admin.port, admin.database) != (app.host, app.port, app.database):
        raise ValueError("Admin and application must target exactly the same isolated database.")
    if app.user != APP_ROLE or admin.user in {APP_ROLE, "dou_worker"}:
        raise ValueError("Use the real dou_app reader and a separate setup administrator.")
    forbidden = {"PGSERVICE", "PGSERVICEFILE", "PGHOSTADDR", "PGOPTIONS", "PGSYSCONFDIR"}
    if forbidden.intersection(os.environ):
        raise ValueError("Remove libpq service/routing/option overrides before this experiment.")
    return admin, app


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def runtime_sql(root: Path = ROOT) -> str:
    """Read the literal runtime query without importing settings/models/providers."""
    tree = ast.parse((root / DENSE_PATH).read_text())
    values = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(name, ast.Name) and name.id == "_SQL" for name in node.targets)
    ]
    if len(values) != 1 or not isinstance(values[0], ast.Call) or len(values[0].args) != 1:
        raise ValueError(
            "Runtime _SQL no longer has the supported literal shape; inspect the harness."
        )
    query = ast.literal_eval(values[0].args[0])
    if not isinstance(query, str):
        raise ValueError("Runtime query must be a string literal.")
    # Runtime SQL has no percent literals or casts using :name syntax. Fail if it
    # evolves, rather than silently benchmarking a modified/incorrect baseline.
    if "%" in query:
        raise ValueError("Runtime percent syntax requires an explicit adapter review.")
    names = set(re.findall(r"(?<!:):([a-z_]+)", query))
    expected = {"query_vector", "course_id", "filter_documents", "document_ids", "limit"}
    if names not in (expected, expected | {"candidate_limit"}):
        raise ValueError("Runtime bind contract changed; inspect the harness.")
    return re.sub(r"(?<!:):([a-z_]+)", r"%(\1)s", query)


def baseline_sql(root: Path = ROOT, baseline_report: Path | None = None) -> str:
    """Pinned pre-C1 literal only; never execute arbitrary SQL supplied by a report."""
    query = (root / BASELINE_FIXTURE).read_text()
    if sha256(query.encode()) != PRE_C1_SQL_SHA256:
        raise ValueError("Pinned pre-C1 SQL snapshot hash changed.")
    if baseline_report is not None:
        report = json.loads(baseline_report.read_text())
        if (
            not isinstance(report, dict)
            or report.get("status") != "measured"
            or report.get("version") != "dou018-synthetic-plan-v2"
            or report.get("sql", {}).get("baseline") != query
            or report.get("sql_sha256", {}).get("baseline") != PRE_C1_SQL_SHA256
            or report.get("source_sha256", {}).get(str(DENSE_PATH)) != PRE_C1_DENSE_SOURCE_SHA256
        ):
            raise ValueError("Expected measured v2 evidence bound to the known pre-C1 source/SQL.")
    return query


def candidate_sql(*, materialized: bool) -> str:
    cte = "MATERIALIZED" if materialized else ""
    return f"""
        WITH nearest AS {cte} (
            SELECT c.id,
                   c.document_id,
                   c.chunk_index,
                   c.page_number,
                   c.slide_number,
                   c.section_title,
                   c.text,
                   c.embedding_space,
                   c.embedding <=> CAST(%(query_vector)s AS vector) AS distance
            FROM chunks c WHERE {FILTER}
            ORDER BY c.embedding <=> CAST(%(query_vector)s AS vector)
            LIMIT %(candidate_limit)s
        )
        SELECT n.id,
               n.document_id,
               d.file_name,
               n.page_number,
               n.slide_number,
               n.section_title,
               n.text,
               n.embedding_space,
               1 - n.distance AS similarity
        FROM nearest n JOIN documents d ON d.id = n.document_id
        ORDER BY n.distance + 0, d.file_hash, n.chunk_index
        LIMIT %(limit)s
    """  # noqa: S608 — only static fragments; all data remains bound.


def exact_sql() -> str:
    return f"""
        SELECT c.id, 1 - (c.embedding <=> CAST(%(query_vector)s AS vector)) AS similarity
        FROM chunks c JOIN documents d ON d.id = c.document_id WHERE {FILTER}
        ORDER BY c.embedding <=> CAST(%(query_vector)s AS vector), d.file_hash, c.chunk_index
        LIMIT %(limit)s
    """  # noqa: S608 — only static fragments; all data remains bound.


@dataclass(frozen=True)
class Document:
    course: str
    logical: int
    count: int
    id: UUID
    course_id: UUID
    file_hash: str


def source_bytes(kind: str, logical: int, count: int) -> bytes:
    return "\n".join(
        f"Synthetic {kind} document {logical} chunk {i}." for i in range(count)
    ).encode()


def documents(config: Config) -> list[Document]:
    # Mirrored courses have identical source bytes but deliberately reversed UUID
    # ordering. Hashes must NEVER derive from the generated document identity.
    fit = config.limit + 8
    overflow = config.limit * config.multiplier * 2 + 8
    narrow, unrelated = config.rows // 50, config.rows * 8 // 100
    broad = config.rows - narrow - unrelated - 2 * fit - 2 * overflow
    groups = [("broad", broad, 32), ("narrow", narrow, 4), ("unrelated", unrelated, 4)]
    groups += [
        (f"tie_{kind}_{layout}", size, 2)
        for kind, size in (("fit", fit), ("overflow", overflow))
        for layout in (0, 1)
    ]
    result = []
    for group_number, (course, count, doc_count) in enumerate(groups):
        course_id = uuid5(NAMESPACE_URL, CORPUS_VERSION + "/" + course)
        kind = course.rsplit("_", 1)[0] if course.startswith("tie_") else course
        for logical in range(doc_count):
            size = count // doc_count + int(logical < count % doc_count)
            # UUID ordering flips across the pair while the logical content does not.
            rank = (1 - logical) if course.endswith("_1") else logical
            doc_id = UUID(int=(group_number + 1) * 1000 + rank + 1)
            result.append(
                Document(
                    course,
                    logical,
                    size,
                    doc_id,
                    course_id,
                    sha256(source_bytes(kind, logical, size)),
                )
            )
    return result


def vector(seed: int, ordinal: int, *, tie: bool = False) -> str:
    if tie:
        return "[" + ",".join(["0"] * (DIMENSIONS - 1) + ["1"]) + "]"
    rng = random.Random(f"{CORPUS_VERSION}:{seed}:{ordinal}")  # noqa: S311 — synthetic corpus PRNG
    values = [rng.uniform(-0.5, 0.5) for _ in range(DIMENSIONS)]
    values[ordinal % 8] += 8.0  # Nonzero by construction; eight synthetic clusters.
    return "[" + ",".join(format(value, ".7g") for value in values) + "]"


def chunk_id(doc: Document, index: int) -> UUID:
    return uuid5(doc.id, f"chunk/{index}")


def cases(config: Config, docs: list[Document]) -> list[dict[str, Any]]:
    first = {doc.course: doc for doc in reversed(docs)}
    result = []
    scopes: tuple[tuple[str, str, list[UUID] | None, UUID], ...] = (
        ("broad", "broad", None, USER_ID),
        ("narrow", "narrow", None, USER_ID),
        ("allowed_document", "broad", [first["broad"].id], USER_ID),
        ("empty_documents", "broad", [], USER_ID),
        ("nonmember", "unrelated", None, USER_ID),
    )
    for scope, course, selected, user in scopes:
        for query in range(2):
            result.append(
                {
                    "id": f"{scope}/q{query}",
                    "course": course,
                    "user": user,
                    "query_vector": vector(config.seed, config.rows + query),
                    "course_id": first[course].course_id,
                    "document_ids": selected or [],
                    "filter_documents": selected is not None,
                }
            )
    for course, doc in first.items():
        if course.startswith("tie_"):
            result.append(
                {
                    "id": course,
                    "course": course,
                    "user": USER_ID,
                    "query_vector": vector(config.seed, 0, tie=True),
                    "course_id": doc.course_id,
                    "document_ids": [],
                    "filter_documents": False,
                }
            )
    return result


def plan(config: Config, root: Path = ROOT, baseline_report: Path | None = None) -> dict[str, Any]:
    config.validate()
    docs = documents(config)
    query_cases = cases(config, docs)
    sql = {
        "baseline": baseline_sql(root, baseline_report),
        "pure_operator_cte": candidate_sql(materialized=False),
        "materialized_oversampling": candidate_sql(materialized=True),
        "exact": exact_sql(),
    }
    source_paths = [
        DENSE_PATH,
        BASELINE_FIXTURE,
        Path("apps/api/app/modules/retrieval/fts.py"),
        Path("apps/api/app/modules/retrieval/service.py"),
        Path("scripts/benchmark_retrieval_plan.py"),
        Path("scripts/test_benchmark_retrieval_plan.py"),
        Path(".github/workflows/ci.yml"),
    ]
    source_paths += sorted(
        path.relative_to(root) for path in (root / "supabase/migrations").glob("*.sql")
    )
    ci_images = sorted(
        set(
            re.findall(r"pgvector/pgvector:[^\s]+", (root / ".github/workflows/ci.yml").read_text())
        )
    )
    return {
        "status": "planned",
        "ci_images": ci_images,
        "seed_statement_timeout_ms": min(config.deadline_seconds, 600) * 1000,
        "version": VERSION,
        "corpus_version": CORPUS_VERSION,
        "baseline_provenance": {
            "source_sha256": PRE_C1_DENSE_SOURCE_SHA256,
            "sql_sha256": PRE_C1_SQL_SHA256,
            "snapshot": str(BASELINE_FIXTURE),
            "measured_report_sha256": sha256(baseline_report.read_bytes())
            if baseline_report
            else None,
            "runtime_source_matches_baseline": sha256((root / DENSE_PATH).read_bytes())
            == PRE_C1_DENSE_SOURCE_SHA256,
        },
        "projection_contract": "full runtime nearest fields and outer result projection",
        "config": asdict(config),
        "dimensions": DIMENSIONS,
        "prepare_threshold": None,
        "plan_mode": (
            "parameter-specific unnamed statements; runtime prepared/generic parity not claimed"
        ),
        "ef_search": [40, 100],
        "sql": sql,
        "sql_sha256": {name: sha256(value.encode()) for name, value in sql.items()},
        "source_sha256": {str(path): sha256((root / path).read_bytes()) for path in source_paths},
        "case_ids": [case["id"] for case in query_cases],
        "query_sha256": {case["id"]: sha256(case["query_vector"].encode()) for case in query_cases},
        "course_counts": {
            name: sum(doc.count for doc in docs if doc.course == name)
            for name in dict.fromkeys(doc.course for doc in docs)
        },
        "budget": {
            "cases": len(query_cases),
            "arms": 3,
            "measured_queries": len(query_cases) * 6 * config.repeats,
            "warmup_queries": len(query_cases) * 6 * config.warmups,
            "explain_analyze_queries": len(query_cases) * 7,
        },
        "interpretation": [
            "Synthetic planner/ANN experiment, not E5 or student-answer quality evidence.",
            (
                "V2 candidate projections match runtime fields and the documents join. "
                "Corpus generation remains v1 to preserve the first experiment's data/query hashes."
            ),
            (
                "Driver preparation is disabled. Each statement has parameter-specific planning; "
                "runtime prepared/generic plan parity is not claimed."
            ),
            (
                "Natural planner choices are recorded; ANN use is never forced for an"
                " improvement claim."
            ),
            (
                "ef_search 40 is the usual baseline; 100 tests extra ANN search "
                "effort at a bounded cost."
            ),
            (
                "Baseline/pure use iterative_scan off. Materialized uses "
                "relaxed_order plus oversampling; its combined effect is not a "
                "materialization-only estimate."
            ),
            (
                "Exact oracle disables index and bitmap scans locally; benchmark arms"
                " do not change scan-enabling GUCs."
            ),
            (
                "Broad/narrow/document filters expose post-ANN selectivity; "
                "empty/nonmember cases test isolation."
            ),
            (
                "Hash order is checked within candidates. Overflow ties cannot "
                "establish global ANN stability."
            ),
            (
                "HNSW exists before seeding: incremental insert path. No bulk rebuild"
                " or memory intervention occurs."
            ),
            (
                "A build-memory spill does not establish recall loss. C2 and other "
                "pgvector versions need separate measurements."
            ),
            (
                "One corpus/insertion order; paired query order rotates by repeat. No"
                " cold-cache or population-level claim."
            ),
        ],
    }


def verify_connection(conn: Any, expected: Connection, *, reader: bool) -> dict[str, Any]:
    row = conn.execute("""SELECT current_database() AS database, current_user AS role,
        r.rolsuper, r.rolbypassrls FROM pg_roles r WHERE rolname = current_user""").fetchone()
    if row["database"] != expected.database or row["role"] != expected.user:
        raise ValueError("Connected database/role does not match the validated target.")
    if reader and (row["rolsuper"] or row["rolbypassrls"]):
        raise ValueError("Application benchmark reader must not bypass RLS.")
    if not reader and not (row["rolsuper"] or row["rolbypassrls"]):
        raise ValueError(
            "Setup must see all rows so the empty-database guard cannot be hidden by RLS."
        )
    return dict(row)


def settings(conn: Any) -> dict[str, Any]:
    return {
        name: conn.execute("SELECT current_setting(%s, true) AS value", (name,)).fetchone()["value"]
        for name in GUCS
    }


def claim_empty_database(conn: Any, config: Config) -> None:
    # Session lock stays held while app connections measure. Refuse reused targets;
    # no DROP, TRUNCATE, DELETE, or automatic cleanup of an existing corpus.
    locked = conn.execute(
        "SELECT pg_try_advisory_lock(hashtext(%s)) AS locked", (VERSION,)
    ).fetchone()
    if not locked["locked"]:
        raise ValueError("This isolated benchmark database is already in use.")
    with conn.transaction():
        occupied = conn.execute("""SELECT
            EXISTS(SELECT 1 FROM profiles) OR EXISTS(SELECT 1 FROM courses)
            OR EXISTS(SELECT 1 FROM documents) OR EXISTS(SELECT 1 FROM chunks) AS occupied,
            to_regclass('public.dou018_retrieval_benchmark_run') IS NOT NULL AS claimed
            """).fetchone()
        if occupied["occupied"] or occupied["claimed"]:
            raise ValueError("Benchmark requires an empty, unused migrated database.")
        conn.execute("""CREATE TABLE public.dou018_retrieval_benchmark_run (
            version text NOT NULL, seed bigint NOT NULL, started_at timestamptz DEFAULT now())""")
        conn.execute(
            "INSERT INTO public.dou018_retrieval_benchmark_run (version, seed) VALUES (%s, %s)",
            (VERSION, config.seed),
        )


def check_schema(conn: Any) -> list[dict[str, Any]]:
    tables = conn.execute("""SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
        pg_get_userbyid(c.relowner) AS owner FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relname IN ('chunks', 'documents') ORDER BY c.relname
        """).fetchall()
    if len(tables) != 2 or any(
        not row["relrowsecurity"] or not row["relforcerowsecurity"] or row["owner"] == APP_ROLE
        for row in tables
    ):
        raise ValueError(
            "Expected real forced RLS on chunks/documents with a separate table owner."
        )
    policy = conn.execute("""SELECT policyname, qual FROM pg_policies WHERE schemaname='public'
        AND tablename IN ('chunks', 'documents') AND cmd='SELECT' ORDER BY tablename, policyname
        """).fetchall()
    index = conn.execute(
        "SELECT pg_get_indexdef('public.chunks_embedding_idx'::regclass) AS definition"
    ).fetchone()
    if "USING hnsw" not in index["definition"] or "vector_cosine_ops" not in index["definition"]:
        raise ValueError("Expected the migrated HNSW cosine index before seeding.")
    return [dict(row) for row in tables] + [dict(row) for row in policy] + [dict(index)]


def seed_corpus(
    conn: Any, config: Config, docs: list[Document]
) -> tuple[dict[UUID, dict[str, Any]], str]:
    metadata: dict[UUID, dict[str, Any]] = {}
    digest = hashlib.sha256()
    with conn.transaction():
        conn.execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (str(min(config.deadline_seconds, 600) * 1000),),
        )
        for identity, label in (
            (OWNER_ID, "instructor"),
            (USER_ID, "student"),
            (OUTSIDER_ID, "outsider"),
        ):
            conn.execute(
                "INSERT INTO profiles (id,email,full_name) VALUES (%s,%s,%s)",
                (identity, f"{label}@synthetic.invalid", f"Synthetic {label}"),
            )
        for course in dict.fromkeys(doc.course for doc in docs):
            doc = next(item for item in docs if item.course == course)
            conn.execute(
                "INSERT INTO courses (id,code,title,created_by) VALUES (%s,%s,%s,%s)",
                (doc.course_id, course, f"Synthetic {course}", OWNER_ID),
            )
            for user, role in (
                (OWNER_ID, "instructor"),
                (USER_ID if course != "unrelated" else OUTSIDER_ID, "student"),
            ):
                conn.execute(
                    "INSERT INTO course_memberships (course_id,user_id,role) VALUES (%s,%s,%s)",
                    (doc.course_id, user, role),
                )
        for doc in docs:
            conn.execute(
                """INSERT INTO documents
                (id,course_id,uploaded_by,file_name,file_type,storage_path,file_hash,byte_size,status,chunk_count)
                VALUES (%s,%s,%s,%s,'txt',%s,%s,%s,'completed',%s)""",
                (
                    doc.id,
                    doc.course_id,
                    OWNER_ID,
                    f"synthetic-{doc.logical}.txt",
                    f"synthetic/{doc.id}",
                    doc.file_hash,
                    len(
                        source_bytes(
                            doc.course.rsplit("_", 1)[0]
                            if doc.course.startswith("tie_")
                            else doc.course,
                            doc.logical,
                            doc.count,
                        )
                    ),
                    doc.count,
                ),
            )
        ordinal = 0
        with conn.cursor().copy("""COPY chunks
            (id,course_id,document_id,chunk_index,text,token_count,embedding,embedding_space)
            FROM STDIN
            """) as copy:
            for doc in docs:
                for index in range(doc.count):
                    identity = chunk_id(doc, index)
                    embedding = vector(config.seed, ordinal, tie=doc.course.startswith("tie_"))
                    kind = (
                        doc.course.rsplit("_", 1)[0]
                        if doc.course.startswith("tie_")
                        else doc.course
                    )
                    content = f"Synthetic {kind} document {doc.logical} chunk {index}."
                    copy.write_row(
                        (
                            identity,
                            doc.course_id,
                            doc.id,
                            index,
                            content,
                            4,
                            embedding,
                            CORPUS_VERSION,
                        )
                    )
                    metadata[identity] = {
                        "course": doc.course,
                        "document_id": doc.id,
                        "key": [doc.file_hash, index],
                    }
                    digest.update(f"{identity}|{doc.file_hash}|{index}|{embedding}\n".encode())
                    ordinal += 1
    conn.execute("ANALYZE profiles, courses, course_memberships, documents, chunks")
    return metadata, digest.hexdigest()


def eligible_ids(case: dict[str, Any], metadata: dict[UUID, dict[str, Any]]) -> set[UUID]:
    if case["course"] == "unrelated":
        return set()
    return {
        identity
        for identity, item in metadata.items()
        if item["course"] == case["course"]
        and (not case["filter_documents"] or item["document_id"] in case["document_ids"])
    }


def evaluate_rows(
    rows: list[dict[str, Any]],
    exact: list[dict[str, Any]],
    eligible: set[UUID],
    metadata: dict[UUID, dict[str, Any]],
    limit: int,
) -> dict[str, Any]:
    identities = [row["id"] for row in rows]
    if len(identities) != len(set(identities)) or len(rows) > limit or set(identities) - eligible:
        raise ValueError("Duplicate, over-limit, or out-of-scope benchmark result.")
    if any(not math.isfinite(row["similarity"]) for row in rows + exact):
        raise ValueError("Nonfinite distance in benchmark results.")
    expected = min(limit, len(eligible))
    if (
        len(exact) != expected
        or len({row["id"] for row in exact}) != expected
        or {row["id"] for row in exact} - eligible
    ):
        raise ValueError("Exact oracle count does not match seeded visibility.")
    strict = len(set(identities).intersection(row["id"] for row in exact))
    mandatory: set[UUID] = set()
    tie_credit = 0
    if exact:
        boundary = exact[-1]["similarity"]
        mandatory = {row["id"] for row in exact if row["similarity"] > boundary + 1e-12}
        tie_credit = min(
            expected - len(mandatory),
            sum(abs(row["similarity"] - boundary) <= 1e-12 for row in rows),
        )
    ordered = [(1 - row["similarity"], *metadata[row["id"]]["key"]) for row in rows]
    return {
        "returned": len(rows),
        "eligible": len(eligible),
        "expected": expected,
        "shortfall": expected - len(rows),
        "strict_recall": strict / expected if expected else None,
        "tie_aware_recall": (len(set(identities) & mandatory) + tie_credit) / expected
        if expected
        else None,
        "content_ordered": ordered == sorted(ordered),
        "stable_keys": [metadata[identity]["key"] for identity in identities],
    }


def explain(conn: Any, query: str, params: dict[str, Any]) -> dict[str, Any]:
    raw = conn.execute(
        "EXPLAIN (ANALYZE, BUFFERS, SETTINGS, FORMAT JSON) " + query, params
    ).fetchone()
    return next(iter(raw.values()))[0]


def uses_hnsw(plan_node: Any) -> bool:
    if isinstance(plan_node, dict):
        return plan_node.get("Index Name") == "chunks_embedding_idx" or any(
            uses_hnsw(value) for value in plan_node.values()
        )
    return isinstance(plan_node, list) and any(uses_hnsw(item) for item in plan_node)


def percentile95(values: list[float]) -> float:
    return sorted(values)[math.ceil(len(values) * 0.95) - 1]


def measure_case(
    conn: Any,
    case: dict[str, Any],
    config: Config,
    sql: dict[str, str],
    metadata: dict[UUID, dict[str, Any]],
    deadline: float,
) -> dict[str, Any]:
    params = {**case, "limit": config.limit, "candidate_limit": config.limit}
    eligible = eligible_ids(case, metadata)
    with conn.transaction():
        conn.execute("SELECT set_config('app.current_user_id', %s, true)", (str(case["user"]),))
        visible = conn.execute(
            "SELECT count(*) AS count FROM chunks c WHERE " + FILTER,  # noqa: S608 — static
            params,
        ).fetchone()["count"]
        if visible != len(eligible):
            raise ValueError("Real dou_app RLS visibility differs from the seeded scope oracle.")
        conn.execute("SET LOCAL enable_indexscan = off")
        conn.execute("SET LOCAL enable_bitmapscan = off")
        exact_plan = explain(conn, sql["exact"], params)
        exact = conn.execute(sql["exact"], params).fetchall()
        if uses_hnsw(exact_plan):
            raise ValueError("Exact reference unexpectedly uses HNSW.")
    result: dict[str, Any] = {"id": case["id"], "exact_plan": exact_plan, "arms": []}
    arms = [(name, ef) for ef in (40, 100) for name in sql if name != "exact"]
    buffers: dict[tuple[str, int], dict[str, Any]] = {}
    for repeat in range(-config.warmups, config.repeats):
        # Rotate order so the same variant is not always the first warm-cache reader.
        shift = (repeat + config.warmups) % len(arms)
        for name, ef in arms[shift:] + arms[:shift]:
            if time.monotonic() > deadline:
                raise TimeoutError("Bounded benchmark deadline exceeded.")
            materialized = name == "materialized_oversampling"
            params["candidate_limit"] = config.limit * (config.multiplier if materialized else 1)
            with conn.transaction():
                conn.execute(
                    "SELECT set_config('app.current_user_id', %s, true)", (str(case["user"]),)
                )
                conn.execute("SELECT set_config('hnsw.ef_search', %s, true)", (str(ef),))
                conn.execute(
                    "SELECT set_config('hnsw.iterative_scan', %s, true)",
                    ("relaxed_order" if materialized else "off",),
                )
                start = time.perf_counter()
                rows = conn.execute(sql[name], params).fetchall()
                elapsed = (time.perf_counter() - start) * 1000
                quality = evaluate_rows(rows, exact, eligible, metadata, config.limit)
                if (name, ef) not in buffers:
                    measured_plan = explain(conn, sql[name], params)
                    buffers[name, ef] = {
                        "name": name,
                        "ef_search": ef,
                        "candidate_limit": params["candidate_limit"],
                        "gucs": settings(conn),
                        "plan": measured_plan,
                        "uses_hnsw": uses_hnsw(measured_plan),
                        "samples": [],
                    }
                if repeat >= 0:
                    buffers[name, ef]["samples"].append({"latency_ms": elapsed, **quality})
    for arm in buffers.values():
        arm["p95_ms"] = percentile95([sample["latency_ms"] for sample in arm["samples"]])
        arm["within_run_key_stability"] = all(
            sample["stable_keys"] == arm["samples"][0]["stable_keys"] for sample in arm["samples"]
        )
        result["arms"].append(arm)
    return result


def tie_comparison(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {result["id"]: result for result in results}
    comparisons = []
    for kind in ("fit", "overflow"):
        left, right = (by_id[f"tie_{kind}_{layout}"] for layout in (0, 1))
        for arm in left["arms"]:
            other = next(
                item
                for item in right["arms"]
                if (item["name"], item["ef_search"]) == (arm["name"], arm["ef_search"])
            )
            comparisons.append(
                {
                    "fixture": kind,
                    "arm": arm["name"],
                    "ef_search": arm["ef_search"],
                    "same_content_keys_across_uuid_layouts": arm["samples"][0]["stable_keys"]
                    == other["samples"][0]["stable_keys"],
                    "global_stability_claim": False,
                }
            )
    return comparisons


def execute(config: Config, report: dict[str, Any], admin: Connection, app: Connection) -> None:
    import psycopg
    from psycopg.rows import dict_row

    start = time.monotonic()
    report["phase"] = "connect_and_verify"
    with (
        psycopg.connect(**admin.kwargs(), row_factory=dict_row) as setup,
        psycopg.connect(**app.kwargs(), row_factory=dict_row) as reader,
    ):
        report["connections"] = {
            "admin": verify_connection(setup, admin, reader=False),
            "reader": verify_connection(reader, app, reader=True),
            "target": app.public(),
        }
        report["schema"] = check_schema(setup)
        postgres = setup.execute("SELECT version() AS value").fetchone()
        extension = setup.execute(
            "SELECT extversion AS value FROM pg_extension WHERE extname='vector'"
        ).fetchone()
        if postgres is None or extension is None:
            raise ValueError("Expected PostgreSQL and pgvector version metadata.")
        report["environment"] = {
            "postgresql": postgres["value"],
            "vector": extension["value"],
            "python": sys.version,
            "gucs_reader_before": settings(reader),
            "gucs_setup_before": settings(setup),
            "version_equivalence_claim": False,
        }
        current = report["environment"]["vector"]
        if tuple(int(part) for part in current.split(".")[:2]) < (0, 8):
            raise ValueError("This experiment requires pgvector iterative scans (0.8+).")
        report["phase"] = "claim_empty_database"
        claim_empty_database(setup, config)
        docs = documents(config)
        report["phase"] = "seed_synthetic_corpus"
        seed_start = time.monotonic()
        metadata, corpus_hash = seed_corpus(setup, config, docs)
        report["corpus"] = {
            "rows": len(metadata),
            "sha256": corpus_hash,
            "seed_and_analyze_seconds": time.monotonic() - seed_start,
            "documents": [
                {**asdict(doc), "id": str(doc.id), "course_id": str(doc.course_id)} for doc in docs
            ],
        }
        report["results"] = []
        for case in cases(config, docs):
            report["phase"] = f"measure/{case['id']}"
            report["results"].append(
                measure_case(
                    reader, case, config, report["sql"], metadata, start + config.deadline_seconds
                )
            )
        if [item["id"] for item in report["results"]] != report["case_ids"]:
            raise ValueError("Incomplete query set; paired comparison is invalid.")
        report["tie_comparison"] = tie_comparison(report["results"])
        report["elapsed_seconds"] = time.monotonic() - start
        report["status"] = "measured"
        report["phase"] = "complete"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-report", type=Path)
    for name, default in asdict(Config()).items():
        parser.add_argument("--" + name.replace("_", "-"), type=int, default=default)
    args = parser.parse_args(argv)
    report: dict[str, Any] = {}
    owned_output = False
    try:
        config = Config(**{name: getattr(args, name) for name in asdict(Config())})
        report = plan(config, baseline_report=args.baseline_report)
        if args.execute:
            if not args.baseline_report:
                raise ValueError("Execution requires explicit measured pre-C1 --baseline-report.")
            if not args.output:
                raise ValueError("Execution requires a new explicit output path.")
            admin, app = validate_connections(
                os.environ.get("RETRIEVAL_BENCH_ADMIN_DSN", ""),
                os.environ.get("RETRIEVAL_BENCH_APP_DSN", ""),
            )
            with args.output.open("x") as output:
                output.write(json.dumps(report, indent=2) + "\n")
            owned_output = True
            execute(config, report, admin, app)
        elif args.output:
            with args.output.open("x") as output:
                output.write(json.dumps(report, indent=2) + "\n")
        else:
            print(json.dumps(report, indent=2))
    except Exception as error:
        report.update(status="failed", error_class=type(error).__name__)
        # DB errors may contain supplied secrets. Preserve class and partial safe
        # evidence, never exception messages, DSNs or tracebacks in the artifact.
        print(
            f"Benchmark stopped ({type(error).__name__}); no database cleanup was attempted.",
            file=sys.stderr,
        )
        return 1
    finally:
        if owned_output:
            args.output.write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
