"""İki gerçek HTTP sürecinde sentetik kota kabul deneyi; varsayılan yalnız plan."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import db_guard
from common import (
    SOURCE_PATHS,
    application_dsn,
    child_environment,
    runtime_tree_hashes,
    source_hashes,
    verify_sources,
)

BASE = Path(__file__).parent
POLICIES = [
    dict(scope="chat", request_limit=20, window_ms=60000),
    dict(scope="qgen", request_limit=5, window_ms=300000),
]
TEXTS = [
    "Deadlock oluşması için karşılıklı dışlama, tut ve bekle, kesilemezlik "
    "ve döngüsel bekleme koşulları gerekir.",
    "Döngüsel bekleme, süreçlerin birbirlerinin tuttuğu kaynakları "
    "bir halka oluşturacak şekilde beklemesidir.",
    "Deadlock önleme yöntemleri dört gerekli koşuldan en az birini ortadan kaldırır.",
]


def require(condition, code):
    db_guard.require(condition, code)


def ports(environment):
    try:
        values = json.loads(environment.get("D1_HTTP_PORTS_JSON", ""))
    except (TypeError, ValueError):
        raise db_guard.TargetGuardError("EXPLICIT_HTTP_PORT_PAIR_REQUIRED") from None
    require(
        isinstance(values, list)
        and len(values) == 2
        and all(type(value) is int and 1024 <= value <= 65535 for value in values)
        and len(set(values)) == 2,
        "EXPLICIT_HTTP_PORT_PAIR_REQUIRED",
    )
    config = db_guard.configuration(environment)
    require(config.port not in values, "HTTP_DATABASE_PORT_COLLISION")
    return values


def plan():
    return {
        "status": "plan-only",
        "database_access": False,
        "server_start": False,
        "source_paths_for_root_manifest": list(SOURCE_PATHS),
        "required_environment": [
            "D1_TEST_DB_NAME",
            "D1_ADMIN_DSN",
            "D1_HTTP_APP_DSN",
            "D1_EXPECTED_TARGET_JSON",
            "D1_HTTP_PORTS_JSON",
            "D1_HTTP_SOURCE_MANIFEST_JSON",
        ],
        "scenarios": [
            "40 shared chat admissions: 20 accepted source-refusals +20 HTTP429",
            "provider503 consumes one committed slot and rolls back main session",
            "policy mismatch and DB lock timeout fail closed with no provider",
            "cross-process QA cache consumes both admissions but provider only once",
            "instructor qgen5+2 denials and student403 without slot",
        ],
        "limits": [
            "Only synthetic fixture retrieval and deterministic local provider",
            "No DB creation/migration/DDL",
            "Actual quota/auth/dependencies/RLS/control pools stay unmodified",
            "No hosted readiness, paid model or semantic-quality claim",
            "Distributed qgen concurrency remains outside this experiment",
        ],
    }


def scalar(admin, sql, args=()):
    value = next(iter(admin.execute(sql, args).fetchone().values()))
    admin.commit()
    return value


def fixture(admin):
    require(
        admin.execute(
            "SELECT scope,request_limit,window_ms FROM app.request_rate_policies ORDER BY scope"
        ).fetchall()
        == POLICIES,
        "CANONICAL_TEST_POLICY_REQUIRED",
    )
    admin.commit()
    for sql in (
        "SELECT count(*) AS n FROM public.profiles",
        "SELECT count(*) AS n FROM public.courses",
    ):
        require(
            scalar(admin, sql) == 0,
            "FRESH_EMPTY_SYNTHETIC_DATABASE_REQUIRED",
        )
    actors = {
        label: uuid4()
        for label in ("limit", "failure", "policy", "lock", "cache", "teacher", "student")
    }
    course, topic, document = uuid4(), uuid4(), uuid4()
    with admin.transaction():
        for label, actor in actors.items():
            admin.execute(
                "INSERT INTO public.profiles(id,email) VALUES(%s,%s)",
                (actor, f"d1-http-{label}-{actor}@example.invalid"),
            )
        admin.execute(
            "INSERT INTO public.courses(id,code,title,created_by) VALUES(%s,%s,%s,%s)",
            (course, "D1-HTTP-" + str(course), "Sentetik kota deneyi", actors["teacher"]),
        )
        for label, actor in actors.items():
            admin.execute(
                "INSERT INTO public.course_memberships(course_id,user_id,role) VALUES(%s,%s,%s)",
                (course, actor, "instructor" if label == "teacher" else "student"),
            )
        admin.execute(
            "INSERT INTO public.topics(id,course_id,name,created_by) VALUES(%s,%s,%s,%s)",
            (topic, course, "Deadlock koşulları", actors["teacher"]),
        )
        admin.execute(
            """INSERT INTO public.documents(
                id,course_id,uploaded_by,file_name,file_type,storage_path,
                file_hash,byte_size,status,page_count,chunk_count)
            VALUES(%s,%s,%s,'d1-synthetic.txt','txt',%s,%s,1024,'completed',3,3)""",
            (
                document,
                course,
                actors["teacher"],
                f"d1-http/{document}.txt",
                hashlib.sha256("\n".join(TEXTS).encode()).hexdigest(),
            ),
        )
        for index, text in enumerate(TEXTS):
            admin.execute(
                """INSERT INTO public.chunks(
                    id,course_id,document_id,chunk_index,page_number,
                    section_title,content_type,text,token_count)
                VALUES(%s,%s,%s,%s,%s,'Deadlock','text',%s,40)""",
                (uuid4(), course, document, index, index + 1, text),
            )
    return {"actors": actors, "course": course, "topic": topic, "document": document}


def window(admin, f, label, scope="chat"):
    return scalar(
        admin,
        "SELECT COALESCE(sum(cardinality(accepted_at)),0) AS n "
        "FROM app.rate_limit_windows WHERE scope=%s AND user_id=%s AND course_id=%s",
        (scope, f["actors"][label], f["course"]),
    )


def provider_events(output, request_ids):
    result = []
    for index in range(2):
        path = output / f"process-{index}-events.jsonl"
        if path.exists():
            result.extend(
                row
                for row in map(json.loads, path.read_text().splitlines())
                if row["kind"] == "provider" and row["request_id"] in request_ids
            )
    return result


async def exercise(admin, f, urls, output):
    import httpx

    results = []
    children = [httpx.AsyncClient(base_url=url, trust_env=False, timeout=8) for url in urls]

    async def request(index, label, case, question=None, qgen=False):
        request_id = "d1-" + case + "-" + uuid4().hex
        path = f"/courses/{f['course']}/" + ("questions/generate" if qgen else "chat")
        payload = (
            {"topic_id": str(f["topic"]), "question_type": "mcq", "count": 1}
            if qgen
            else {"question": question or "Deadlock koşulları nelerdir?", "mode": "qa"}
        )
        response = await children[index].post(
            path,
            json=payload,
            headers={
                "Authorization": "Bearer dev:" + str(f["actors"][label]),
                "X-Request-ID": request_id,
            },
        )
        body = response.json()
        row = {
            "case": case,
            "request_id": request_id,
            "process_index": index,
            "pid": int(response.headers.get("X-D1-Process", "0")),
            "status_code": response.status_code,
            "error_code": body.get("error", {}).get("code"),
            "retry_after": response.headers.get("Retry-After"),
            "answer_status": body.get("status"),
            "cached": body.get("cached"),
            "accepted_questions": body.get("accepted"),
        }
        require(row["pid"] > 0, "ACTUAL_HTTP_PROCESS_HEADER_MISSING")
        results.append(row)
        (output / "http-results.json").write_text(json.dumps(results, indent=2) + "\n")
        return row

    def no_provider(rows):
        require(
            not provider_events(output, {row["request_id"] for row in rows}),
            "REJECTED_REQUEST_REACHED_PROVIDER",
        )

    def rate_denial(row, maximum):
        require(
            row["status_code"] == 429 and row["error_code"] == "rate_limited",
            "EXPECTED_RATE_DENIAL",
        )
        require(
            row["retry_after"] is not None
            and row["retry_after"].isdigit()
            and 1 <= int(row["retry_after"]) <= maximum,
            "RETRY_AFTER_INVALID",
        )

    try:
        # Her süreç önce gerçekten bir kabul alır; sonraki iki HTTP döngüsü birlikte ilerler.
        start = time.monotonic()
        shared = [
            await request(i, "limit", "shared-prefill", f"Deadlock D1_NO_SOURCE başlangıç {i}")
            for i in range(2)
        ]
        require(all(row["status_code"] == 200 for row in shared), "BOTH_PROCESSES_MUST_ACCEPT")

        async def lane(index):
            return [
                await request(index, "limit", "shared", f"Deadlock D1_NO_SOURCE sıra {index}-{n}")
                for n in range(19)
            ]

        lanes = await asyncio.gather(lane(0), lane(1))
        shared.extend(lanes[0] + lanes[1])
        elapsed = time.monotonic() - start
        require(elapsed < 60, "SHARED_CASE_EXCEEDED_POLICY_WINDOW")
        accepted = [row for row in shared if row["status_code"] == 200]
        denied = [row for row in shared if row["status_code"] == 429]
        require(
            len(accepted) == 20 and len(denied) == 20 and len({row["pid"] for row in shared}) == 2,
            "SHARED_LIMIT_NOT_EXACT",
        )
        require(
            all(row["answer_status"] == "insufficient_context" for row in accepted),
            "SOURCE_REFUSAL_PATH_NOT_REACHED",
        )
        for row in denied:
            rate_denial(row, 60)
        no_provider(shared)
        require(window(admin, f, "limit") == 20, "SHARED_COMMITTED_STATE_MISMATCH")

        failed = await request(
            0, "failure", "provider-failure", "Deadlock koşulları nelerdir? D1_PROVIDER_FAILURE"
        )
        require(
            failed["status_code"] == 503 and failed["error_code"] == "llm_unavailable",
            "INJECTED_PROVIDER_FAILURE_NOT_OBSERVED",
        )
        events = provider_events(output, {failed["request_id"]})
        require(
            len(events) == 1 and events[0]["injected_failure"] is True,
            "PROVIDER_FAILURE_COUNT_INVALID",
        )
        require(window(admin, f, "failure") == 1, "PROVIDER_FAILURE_REFUNDED_SLOT")
        require(
            scalar(
                admin,
                "SELECT count(*) AS n FROM public.chat_sessions WHERE user_id=%s AND course_id=%s",
                (f["actors"]["failure"], f["course"]),
            )
            == 0,
            "FAILED_MAIN_TRANSACTION_NOT_ROLLED_BACK",
        )

        # Politika yalnız benzersiz test DB'sinde değişir; finally eski değeri geri yükler.
        try:
            with admin.transaction():
                admin.execute(
                    "UPDATE app.request_rate_policies SET request_limit=19 WHERE scope='chat'"
                )
            mismatch = [await request(i, "policy", "policy-mismatch") for i in range(2)]
            require(
                all(
                    row["status_code"] == 503
                    and row["error_code"] == "rate_limit_unavailable"
                    and row["retry_after"] == "1"
                    for row in mismatch
                ),
                "POLICY_MISMATCH_DID_NOT_FAIL_CLOSED",
            )
            no_provider(mismatch)
            require(window(admin, f, "policy") == 0, "POLICY_MISMATCH_CREATED_SLOT")
        finally:
            with admin.transaction():
                admin.execute(
                    "UPDATE app.request_rate_policies SET request_limit=20 WHERE scope='chat'"
                )

        # DB kesintisi taklit edilmez: yalnız gerçek advisory kilit timeout'u uygulanır.
        blocker = db_guard.connect(passfile=str(output / "empty.pgpass"))
        try:
            with blocker.transaction():
                blocker.execute(
                    "SELECT pg_advisory_xact_lock(15023,hashtext(%s))",
                    (f"chat:{f['actors']['lock']}:{f['course']}",),
                )
                locked = await request(1, "lock", "control-lock-timeout")
                require(
                    locked["status_code"] == 503
                    and locked["error_code"] == "rate_limit_unavailable"
                    and locked["retry_after"] == "1",
                    "DB_TIMEOUT_DID_NOT_FAIL_CLOSED",
                )
                no_provider([locked])
                require(window(admin, f, "lock") == 0, "TIMED_OUT_CONTROL_CREATED_SLOT")
        finally:
            blocker.close()
        recovered = await request(
            0, "lock", "control-lock-recovered", "Deadlock D1_NO_SOURCE yeniden deneme"
        )
        require(
            recovered["status_code"] == 200 and window(admin, f, "lock") == 1,
            "CONTROL_DID_NOT_RECOVER",
        )
        no_provider([recovered])

        # Birebir soru önbelleği ikinci süreçte okunur; iki admission, tek sağlayıcı çağrısı.
        cache = [
            await request(
                i, "cache", "cache", "Deadlock oluşması için hangi koşullar gerekir? D1_CACHE"
            )
            for i in range(2)
        ]
        require(
            all(row["status_code"] == 200 and row["answer_status"] == "answered" for row in cache),
            "CACHE_SETUP_DID_NOT_ANSWER",
        )
        require(
            cache[0]["cached"] is False and cache[1]["cached"] is True,
            "CROSS_PROCESS_CACHE_NOT_USED",
        )
        require(
            len(provider_events(output, {row["request_id"] for row in cache})) == 1
            and window(admin, f, "cache") == 2,
            "CACHE_ADMISSION_OR_PROVIDER_COUNT_INVALID",
        )

        student = await request(1, "student", "student-qgen", qgen=True)
        require(
            student["status_code"] == 403 and window(admin, f, "student", "qgen") == 0,
            "STUDENT_QGEN_ROLE_BOUNDARY_FAILED",
        )
        no_provider([student])
        generated = [await request(i % 2, "teacher", "qgen-admitted", qgen=True) for i in range(5)]
        require(
            all(row["status_code"] == 200 and row["accepted_questions"] == 1 for row in generated),
            "INSTRUCTOR_QGEN_NOT_ACCEPTED",
        )
        rejected = [await request(i, "teacher", "qgen-denied", qgen=True) for i in range(2)]
        for row in rejected:
            rate_denial(row, 300)
        no_provider(rejected)
        require(
            len(provider_events(output, {row["request_id"] for row in generated})) == 5,
            "QGEN_PROVIDER_COUNT_INVALID",
        )
        require(window(admin, f, "teacher", "qgen") == 5, "SHARED_QGEN_STATE_MISMATCH")
        return {
            "http_requests": len(results),
            "shared_requests": 40,
            "shared_admitted": 20,
            "shared_denied": 20,
            "shared_elapsed_seconds": elapsed,
            "provider_failure_consumed": 1,
            "cache_admissions": 2,
            "qgen_admitted": 5,
            "qgen_denied": 2,
            "two_distinct_pids": sorted({row["pid"] for row in results}),
            "results": results,
        }
    finally:
        await asyncio.gather(*(client.aclose() for client in children))


def execute(output, keep_fixtures):
    environment = dict(os.environ)
    db_guard.configuration(environment)
    application_dsn(environment)
    source_before = verify_sources(environment)
    runtime_before = runtime_tree_hashes()
    port_pair = ports(environment)
    require(
        output.parent.resolve().is_relative_to(Path("/private/tmp")) and re_output(output.name),
        "FRESH_PRIVATE_OUTPUT_REQUIRED",
    )
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    fd = os.open(output / "empty.pgpass", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    admin, f, processes, listeners, logs = None, None, [], [], []
    started = time.monotonic()
    report = {
        "status": "incomplete",
        "source_before": source_before,
        "runtime_tree_before": runtime_before,
        "migration_mapping": {
            "review_candidate": "supabase/migrations/0023_shared_request_quota.sql",
            "integrated": "supabase/migrations/0025_shared_request_quota.sql",
            "advisory_namespace": 15023,
        },
        "database_created": False,
        "migration_applied": False,
        "fixtures_removed": False,
        "external_llm_calls": 0,
        "limits": plan()["limits"],
    }
    try:
        admin = db_guard.connect(passfile=str(output / "empty.pgpass"))
        definitions = admin.execute(
            "SELECT p.proname, pg_catalog.pg_get_functiondef(p.oid) AS definition, "
            "p.prosecdef, p.provolatile, p.proconfig FROM pg_catalog.pg_proc p "
            "JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='app' AND p.proname IN "
            "('take_request_slot','request_quota_policies','purge_expired_request_windows') "
            "ORDER BY p.proname"
        ).fetchall()
        admin.commit()
        require(len(definitions) == 3, "QUOTA_FUNCTIONS_MISSING_OR_OVERLOADED")
        report["database_functions"] = [
            {key: value for key, value in row.items() if key != "definition"}
            | {"definition_sha256": hashlib.sha256(row["definition"].encode()).hexdigest()}
            for row in definitions
        ]
        f = fixture(admin)
        (output / "fixture.json").write_text(json.dumps(f, default=str, indent=2) + "\n")
        for index, port in enumerate(port_pair):
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            listener.bind(("127.0.0.1", port))
            listener.listen(128)
            listeners.append(listener)
            env = child_environment(environment, output, index, listener.fileno())
            log = (output / f"process-{index}.log").open("wb")
            logs.append(log)
            process = subprocess.Popen(  # noqa: S603 — sabit kendi Python/giriş dosyası
                [sys.executable, str(BASE / "serve.py")],
                cwd=output,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                pass_fds=(listener.fileno(),),
            )
            processes.append(process)
        urls = [f"http://127.0.0.1:{port}" for port in port_pair]
        import httpx

        deadline = time.monotonic() + 25
        while True:
            require(all(process.poll() is None for process in processes), "CHILD_START_FAILED")
            ready = []
            for url in urls:
                try:
                    response = httpx.get(url + "/health/ready", timeout=1, trust_env=False)
                    ready.append(
                        response.status_code == 200
                        and response.json().get("checks", {}).get("request_quota") == "ok"
                    )
                except httpx.HTTPError:
                    ready.append(False)
            if all(ready):
                break
            require(time.monotonic() < deadline, "CHILD_READINESS_TIMEOUT")
            time.sleep(0.1)
        report["measurement"] = asyncio.run(exercise(admin, f, urls, output))
        report["child_pids"] = sorted(process.pid for process in processes)
        require(
            report["measurement"]["two_distinct_pids"] == report["child_pids"],
            "HTTP_RESPONSES_NOT_FROM_SPAWNED_CHILDREN",
        )
        report["status"] = "measured"
    except Exception as exc:
        report["status"] = "failed"
        report["error_code"] = (
            str(exc) if isinstance(exc, db_guard.TargetGuardError) else type(exc).__name__
        )
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        for listener in listeners:
            listener.close()
        for log in logs:
            log.close()
        if admin is not None:
            if f is not None and not keep_fixtures:
                try:
                    with admin.transaction():
                        admin.execute("DELETE FROM public.courses WHERE id=%s", (f["course"],))
                        admin.execute(
                            "DELETE FROM public.profiles WHERE id=ANY(%s)",
                            (list(f["actors"].values()),),
                        )
                    report["cleanup_counts"] = {
                        "courses": scalar(
                            admin,
                            "SELECT count(*) AS n FROM public.courses WHERE id=%s",
                            (f["course"],),
                        ),
                        "profiles": scalar(
                            admin,
                            "SELECT count(*) AS n FROM public.profiles WHERE id=ANY(%s)",
                            (list(f["actors"].values()),),
                        ),
                        "quota_windows": scalar(
                            admin,
                            "SELECT count(*) AS n FROM app.rate_limit_windows WHERE course_id=%s",
                            (f["course"],),
                        ),
                        "chat_sessions": scalar(
                            admin,
                            "SELECT count(*) AS n FROM public.chat_sessions WHERE course_id=%s",
                            (f["course"],),
                        ),
                    }
                    require(
                        not any(report["cleanup_counts"].values()),
                        "SYNTHETIC_FIXTURE_CLEANUP_INCOMPLETE",
                    )
                    report["fixtures_removed"] = True
                except Exception:
                    report["cleanup_error"] = "SYNTHETIC_FIXTURE_CLEANUP_FAILED"
                    report["status"] = "failed"
            admin.close()
        report["source_after"] = source_hashes()
        report["runtime_tree_after"] = runtime_tree_hashes()
        report["source_unchanged"] = (
            report["source_after"] == source_before
            and report["runtime_tree_after"] == runtime_before
        )
        if not report["source_unchanged"]:
            report["status"] = "failed"
        report["elapsed_seconds"] = time.monotonic() - started
        report["artifact_sha256"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.iterdir()
            if p.is_file() and p.name != "result.json"
        }
        (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "report": str(output / "result.json")}))
    return 0 if report["status"] == "measured" else 1


def re_output(name):
    import re

    return re.fullmatch(r"d1-http-measured-[a-z0-9_-]{1,40}", name) is not None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--keep-fixtures", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps(plan(), indent=2))
        return 0
    if args.output is None:
        parser.error("--execute requires --output")
    return execute(args.output.resolve(), args.keep_fixtures)


if __name__ == "__main__":
    raise SystemExit(main())
