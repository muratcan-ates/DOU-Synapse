"""005 T408 icin gercek HTTP, cok isci ve gecici PostgreSQL kaniti.

Bu betik bir kapasite testi degildir. Yerel makinede, deterministik hashing
embedding ve sahte LLM ile yalnizca su mekanik sozlesmeleri olcer:

* en az iki uvicorn iscisine dagilan gercek HTTP trafigi;
* ayni dersin son kota diliminde atomik karar ve sifir overshoot;
* process-local kapinin diger iscide asildigi durumda kalici concurrency kapisi;
* terk edilmis reservation lease'i bitene kadar kapali, sonrasinda acik davranis;
* provider hatasinda muhafazakar charge ve sonraki istekte toparlanma;
* cache-hit patlamasinda yeni token reservation acilmamasi;
* miss/hit p95, PostgreSQL baglanti tepesi ve havuz hata kalintisi.

Kullanim (repo kokunden, var olan API sanal ortami ile)::

    apps/api/.venv/bin/python apps/api/scripts/role_agent_multiworker_load.py \
      --report specs/005-role-aware-course-agent/evidence/t408-multiworker-local.json

Guvenlik siniri:

* Veritabani adi verilmezse ``dou_synapse_t408_<pid>_<zaman>`` uretilir.
* Disaridan verilen ad da ``dou_synapse_t408_`` ile baslamak zorundadir.
* Betik var olan bir veritabanini silmez; ad doluysa baslamadan durur.
* Cleanup yalniz kendi yarattigi exact DB, process group ve mkdtemp dizinidir.
* Paylasilan PostgreSQL rollerinin parola/login niteliklerini degistirmez; test
  oturumlari baglanti secenegiyle mevcut ``dou_app``/``dou_worker`` rollerine gecer.

Rapor sentetik kimlikler ve agregalar disinda prompt, cevap, kaynak metni,
e-posta, token, header veya reservation satiri tasimaz. Fake/hash sonucu gercek
LLM kalitesi, staging veya production kapasitesi diye yorumlanamaz.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import httpx  # noqa: E402
import psycopg  # noqa: E402

from app.core.vector_space import space_of  # noqa: E402
from app.modules.generation.fake import FakeLlmClient  # noqa: E402
from app.modules.generation.llm import LlmRequest, LlmUnavailableError  # noqa: E402
from app.modules.ingestion.embedding import HashingEmbeddingProvider  # noqa: E402

_SAFE_DB = re.compile(r"^dou_synapse_t408_[a-z0-9_]{1,40}$")
_PROTECTED_DATABASES = frozenset(
    {"postgres", "template0", "template1", "dou_synapse", "dou_synapse_test"}
)
_COURSE_TEXT = (
    "Deadlock kosullari karsilikli dislama, tut ve bekle, kesmesizlik ve "
    "dongusel beklemedir. Deadlock ancak bu dort kosul birlikte saglanirsa "
    "olusabilir. Isletim sistemleri dersinde kaynak grafigi bu iliskiyi gosterir."
)
_QUESTION = "Deadlock kosullari nelerdir?"
_REQUEST_POOL_SIZE = 5
_REQUEST_POOL_OVERFLOW = 5
_CONTROL_POOL_SIZE = 1
_CONTROL_POOL_OVERFLOW = 0


class DelayedFakeLlmClient(FakeLlmClient):
    """Yalniz bu olcum uygulamasinda kullanilan gecikmeli sahte saglayici."""

    async def complete(self, request: LlmRequest):  # type: ignore[no-untyped-def]
        delay = float(os.environ.get("T408_FAKE_DELAY_SECONDS", "1.5"))
        if "T408_SLOW" in request.user:
            delay = float(os.environ.get("T408_SLOW_DELAY_SECONDS", "6"))
        await asyncio.sleep(delay)
        if "T408_PROVIDER_FAILURE" in request.user:
            raise LlmUnavailableError()
        return await super().complete(request)


def create_load_app():  # type: ignore[no-untyped-def]
    """Uvicorn ``--factory`` girisi; production app nesnesini degistirmez."""

    from app.api.chat import set_pipeline
    from app.main import create_app
    from app.modules.generation.service import GenerationService

    set_pipeline(generator=GenerationService(llm=DelayedFakeLlmClient()))
    app = create_app()

    @app.middleware("http")
    async def expose_test_worker(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-T408-Worker-Pid"] = str(os.getpid())
        return response

    return app


@dataclass(frozen=True, slots=True)
class HttpSample:
    status: int
    latency_ms: float
    worker_pid: int | None
    cached: bool | None
    answer_status: str | None
    error_code: str | None
    transport_error: str | None = None


@dataclass(frozen=True, slots=True)
class SeedData:
    instructor: UUID
    students: tuple[UUID, ...]
    courses: dict[str, UUID]


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _latency_summary(samples: Sequence[HttpSample]) -> dict[str, float | int]:
    values = [sample.latency_ms for sample in samples if sample.transport_error is None]
    return {
        "n": len(values),
        "min_ms": round(min(values), 2) if values else 0.0,
        "median_ms": round(_percentile(values, 0.5), 2),
        "p95_ms": round(_percentile(values, 0.95), 2),
        "p99_ms": round(_percentile(values, 0.99), 2),
        "max_ms": round(max(values), 2) if values else 0.0,
    }


def _validate_database_name(name: str) -> str:
    if name in _PROTECTED_DATABASES or not _SAFE_DB.fullmatch(name):
        raise ValueError(
            "T408 veritabani adi dou_synapse_t408_ ile baslayan kucuk harf/rakam/alt-cizgi "
            "biciminde olmalidir"
        )
    return name


def _run(command: Sequence[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - argv is fixed or validated by this script
        list(command),
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


class TemporaryDatabase:
    """Var olan DB'ye dokunmayan, exact-ad cleanup yapan gecici DB."""

    def __init__(self, *, name: str, pg_bin: Path) -> None:
        self.name = _validate_database_name(name)
        self.pg_bin = pg_bin
        self.created = False

    @property
    def admin_dsn(self) -> str:
        return f"postgresql://localhost/{self.name}"

    @property
    def app_dsn(self) -> str:
        return (
            f"postgresql+psycopg://localhost/{self.name}"
            "?application_name=dou_t408_app&options=-crole%3Ddou_app"
        )

    @property
    def worker_dsn(self) -> str:
        return (
            f"postgresql+psycopg://localhost/{self.name}"
            "?application_name=dou_t408_worker&options=-crole%3Ddou_worker"
        )

    def _psql(self, database: str, *args: str) -> subprocess.CompletedProcess[str]:
        return _run([str(self.pg_bin / "psql"), "-v", "ON_ERROR_STOP=1", "-d", database, *args])

    def exists(self) -> bool:
        with psycopg.connect("postgresql://localhost/postgres") as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (self.name,))
                return cur.fetchone() is not None

    def create(self) -> list[str]:
        if self.exists():
            raise RuntimeError(f"T408 DB zaten var; silinmedi: {self.name}")
        self._psql("postgres", "-c", f'CREATE DATABASE "{self.name}"')
        self.created = True
        migrations = sorted((REPO_ROOT / "supabase" / "migrations").glob("*.sql"))
        for migration in migrations:
            self._psql(self.name, "-f", str(migration))
        self.verify_runtime_roles()
        return [path.name for path in migrations]

    def verify_runtime_roles(self) -> None:
        for sqlalchemy_dsn, expected_role in (
            (self.app_dsn, "dou_app"),
            (self.worker_dsn, "dou_worker"),
        ):
            dsn = sqlalchemy_dsn.replace("postgresql+psycopg://", "postgresql://", 1)
            with psycopg.connect(dsn) as conn:
                row = conn.execute("SELECT current_user, session_user").fetchone()
            if row is None or row[0] != expected_role:
                raise RuntimeError(f"T408 oturumu {expected_role} rolune gecemedi: {row}")

    def drop(self) -> None:
        if not self.created:
            return
        _run([str(self.pg_bin / "dropdb"), "--if-exists", self.name])
        self.created = False


def _seed(admin_dsn: str) -> SeedData:
    instructor = uuid4()
    students = tuple(uuid4() for _ in range(10))
    course_names = ("load_a", "load_b", "quota", "concurrency", "recovery", "cache")
    courses = {name: uuid4() for name in course_names}
    provider = HashingEmbeddingProvider()
    embedding = provider.embed_documents([_COURSE_TEXT])[0]
    vector = "[" + ",".join(f"{value:.12g}" for value in embedding) + "]"
    embedding_space = space_of(provider)

    with psycopg.connect(admin_dsn) as conn:
        with conn.cursor() as cur:
            profiles = [(instructor, "t408-instructor@example.invalid", "T408 Instructor")]
            profiles.extend(
                (user_id, f"t408-student-{index}@example.invalid", f"T408 Student {index}")
                for index, user_id in enumerate(students)
            )
            cur.executemany("INSERT INTO profiles(id,email,full_name) VALUES (%s,%s,%s)", profiles)
            for name, course_id in courses.items():
                cur.execute(
                    "INSERT INTO courses(id,code,title,created_by) VALUES (%s,%s,%s,%s)",
                    (course_id, f"T408-{name.upper()}", f"T408 {name}", instructor),
                )
                cur.execute(
                    "INSERT INTO course_memberships(course_id,user_id,role,status) "
                    "VALUES (%s,%s,'instructor','active')",
                    (course_id, instructor),
                )
                cur.executemany(
                    "INSERT INTO course_memberships(course_id,user_id,role,status) "
                    "VALUES (%s,%s,'student','active')",
                    [(course_id, student) for student in students],
                )
                document_id = uuid4()
                cur.execute(
                    "INSERT INTO documents(id,course_id,uploaded_by,file_name,file_type,"
                    "storage_path,file_hash,byte_size,status,page_count,chunk_count) "
                    "VALUES (%s,%s,%s,%s,'.txt',%s,%s,%s,'completed',1,1)",
                    (
                        document_id,
                        course_id,
                        instructor,
                        f"t408-{name}.txt",
                        f"t408/{document_id}.txt",
                        hashlib.sha256(f"{name}:{_COURSE_TEXT}".encode()).hexdigest(),
                        len(_COURSE_TEXT.encode()),
                    ),
                )
                cur.execute(
                    "INSERT INTO chunks(id,course_id,document_id,chunk_index,page_number,"
                    "section_title,content_type,language,text,token_count,embedding,"
                    "embedding_space) "
                    "VALUES (%s,%s,%s,0,1,'Deadlock','text','tr',%s,%s,%s::vector,%s)",
                    (
                        uuid4(),
                        course_id,
                        document_id,
                        _COURSE_TEXT,
                        len(_COURSE_TEXT.split()),
                        vector,
                        embedding_space,
                    ),
                )
                max_concurrent = 1 if name in {"concurrency", "recovery"} else 4
                cur.execute(
                    "INSERT INTO course_ai_policies("
                    "course_id,allowed_modes,max_hints,source_document_ids,evidence_threshold,"
                    "daily_token_budget,student_daily_token_budget,instructor_daily_token_budget,"
                    "max_output_tokens,max_concurrent_requests,updated_by) "
                    "VALUES (%s,ARRAY['qa']::chat_mode[],0,ARRAY[%s]::uuid[],0.010,"
                    "500000,50000,200000,128,%s,%s)",
                    (course_id, document_id, max_concurrent, instructor),
                )
        conn.commit()
    return SeedData(instructor=instructor, students=students, courses=courses)


def _server_env(db: TemporaryDatabase, storage_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "ENVIRONMENT": "local",
            "DEV_AUTH_ENABLED": "true",
            "DATABASE_URL": db.app_dsn,
            "WORKER_DATABASE_URL": db.worker_dsn,
            "STORAGE_BACKEND": "local",
            "STORAGE_ROOT": str(storage_root),
            "EMBEDDING_PROVIDER": "hashing",
            "EMBEDDING_WARMUP_ENABLED": "false",
            "LLM_FAKE_PROVIDER": "true",
            "LLM_TIMEOUT_SECONDS": "0.1",
            "LLM_MAX_RETRIES": "0",
            "LLM_CHAT_MAX_TOKENS": "128",
            "LLM_CHAT_MAX_INPUT_BYTES": "4096",
            "COURSE_AGENT_ENABLED": "true",
            "COURSE_AGENT_STUDENT_DAILY_HARD_LIMIT": "50000",
            "COURSE_AGENT_COURSE_DAILY_HARD_LIMIT": "500000",
            "COURSE_AGENT_PLATFORM_DAILY_HARD_LIMIT": "5000000",
            "CHAT_RATE_LIMIT_REQUESTS": "100",
            "CHAT_RATE_LIMIT_WINDOW_SECONDS": "60",
            "DB_POOL_SIZE": str(_REQUEST_POOL_SIZE),
            "DB_MAX_OVERFLOW": str(_REQUEST_POOL_OVERFLOW),
            "T408_FAKE_DELAY_SECONDS": "1.5",
            "T408_SLOW_DELAY_SECONDS": "6",
        }
    )
    env.pop("SUPABASE_JWT_SECRET", None)
    return env


def _start_server(
    db: TemporaryDatabase, *, port: int, workers: int, storage_root: Path, log_path: Path
) -> tuple[subprocess.Popen[str], Any]:
    log_handle = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "uvicorn",
            "scripts.role_agent_multiworker_load:create_load_app",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--workers",
            str(workers),
            "--log-level",
            "warning",
        ],
        cwd=API_ROOT,
        env=_server_env(db, storage_root),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    return process, log_handle


def _stop_server(process: subprocess.Popen[str] | None, log_handle: Any | None) -> None:
    try:
        if process is not None and process.poll() is None:
            try:
                group = os.getpgid(process.pid)
            except ProcessLookupError:
                group = None
            if group is not None:
                try:
                    os.killpg(group, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                if group is not None:
                    try:
                        os.killpg(group, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait(timeout=10)
    finally:
        if log_handle is not None:
            log_handle.close()


def _cleanup_resources(
    *,
    process: subprocess.Popen[str] | None,
    log_handle: Any | None,
    db: TemporaryDatabase,
    storage_root: Path,
    log_path: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    database_was_owned = db.created
    try:
        _stop_server(process, log_handle)
    except Exception as exc:  # cleanup must continue through every exact target
        errors.append(f"server:{type(exc).__name__}")
    try:
        db.drop()
    except Exception as exc:
        errors.append(f"database_drop:{type(exc).__name__}")
    database_absent = True
    if database_was_owned:
        try:
            database_absent = not db.exists()
        except Exception as exc:
            database_absent = False
            errors.append(f"database_verify:{type(exc).__name__}")
    try:
        shutil.rmtree(storage_root, ignore_errors=False)
    except FileNotFoundError:
        pass
    except Exception as exc:
        errors.append(f"storage:{type(exc).__name__}")
    try:
        log_path.unlink(missing_ok=True)
    except Exception as exc:
        errors.append(f"log:{type(exc).__name__}")
    return {
        "exact_database_absent_after_drop": database_absent,
        "exact_storage_path_absent": not storage_root.exists(),
        "exact_log_path_absent": not log_path.exists(),
        "cleanup_errors": errors,
    }


def _error_code(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if isinstance(error, dict) and isinstance(error.get("code"), str):
        return error["code"]
    if isinstance(payload.get("code"), str):
        return payload["code"]
    return None


async def _request(
    base_url: str,
    *,
    user_id: UUID,
    course_id: UUID,
    question: str,
    request_timeout: float = 30.0,
) -> HttpSample:
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            base_url=base_url,
            timeout=request_timeout,
            headers={"Connection": "close"},
        ) as client:
            response = await client.post(
                f"/courses/{course_id}/chat",
                json={"question": question, "mode": "qa"},
                headers={"Authorization": f"Bearer dev:{user_id}"},
            )
        elapsed = (time.perf_counter() - started) * 1000
        try:
            payload = response.json()
        except ValueError:
            payload = None
        worker = response.headers.get("X-T408-Worker-Pid")
        return HttpSample(
            status=response.status_code,
            latency_ms=elapsed,
            worker_pid=int(worker) if worker and worker.isdigit() else None,
            cached=payload.get("cached") if isinstance(payload, dict) else None,
            answer_status=payload.get("status") if isinstance(payload, dict) else None,
            error_code=_error_code(payload),
        )
    except Exception as exc:
        return HttpSample(
            status=0,
            latency_ms=(time.perf_counter() - started) * 1000,
            worker_pid=None,
            cached=None,
            answer_status=None,
            error_code=None,
            transport_error=type(exc).__name__,
        )


async def _wait_workers(base_url: str, *, minimum: int, max_wait: float = 45.0) -> set[int]:
    deadline = time.monotonic() + max_wait
    workers: set[int] = set()
    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(
                base_url=base_url, timeout=2.0, headers={"Connection": "close"}
            ) as client:
                response = await client.get("/health/live")
            if response.status_code == 200:
                value = response.headers.get("X-T408-Worker-Pid", "")
                if value.isdigit():
                    workers.add(int(value))
                if len(workers) >= minimum:
                    return workers
        except httpx.HTTPError:
            pass
        await asyncio.sleep(0.05)
    raise TimeoutError(f"{minimum} farkli uvicorn iscisi HTTP uzerinden gorulemedi: {workers}")


async def _poll_metric(
    stop: asyncio.Event, interval: float, reader: Callable[[], int]
) -> list[int]:
    samples: list[int] = []
    while not stop.is_set():
        samples.append(await asyncio.to_thread(reader))
        await asyncio.sleep(interval)
    samples.append(await asyncio.to_thread(reader))
    return samples


def _scalar(admin_dsn: str, sql: str, params: Sequence[Any] = ()) -> int:
    with psycopg.connect(admin_dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def _reservation_snapshot(
    admin_dsn: str, course_id: UUID, user_id: UUID | None = None
) -> dict[str, int | float]:
    select = (
        "SELECT count(*), COALESCE(sum(charged_tokens),0), "
        "count(*) FILTER (WHERE reconciled_at IS NULL AND expires_at > now()), "
        "count(*) FILTER (WHERE reconciled_at IS NULL), "
        "COALESCE(max(reserved_tokens),0), "
        "COALESCE(max(EXTRACT(EPOCH FROM expires_at-now())),0) "
        "FROM ai_token_reservations WHERE course_id = %s"
    )
    with psycopg.connect(admin_dsn) as conn:
        with conn.cursor() as cur:
            if user_id is None:
                cur.execute(select, (course_id,))
            else:
                cur.execute(select + " AND user_id = %s", (course_id, user_id))
            row = cur.fetchone()
    assert row is not None
    return {
        "rows": int(row[0]),
        "charged_tokens": int(row[1]),
        "active": int(row[2]),
        "unreconciled": int(row[3]),
        "max_reserved_tokens": int(row[4]),
        "max_seconds_until_expiry": max(0.0, float(row[5])),
    }


async def _wait_for_reservation(
    admin_dsn: str, course_id: UUID, user_id: UUID, *, max_wait: float = 10.0
) -> dict[str, int | float]:
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        snapshot = await asyncio.to_thread(_reservation_snapshot, admin_dsn, course_id, user_id)
        if snapshot["active"]:
            return snapshot
        await asyncio.sleep(0.02)
    raise TimeoutError("aktif T408 reservation gorulemedi")


def _set_course_budget(admin_dsn: str, course_id: UUID, tokens: int) -> None:
    with psycopg.connect(admin_dsn) as conn:
        conn.execute(
            "UPDATE course_ai_policies SET daily_token_budget=%s WHERE course_id=%s",
            (tokens, course_id),
        )
        conn.commit()


def _clear_course_turns(admin_dsn: str, course_id: UUID) -> None:
    with psycopg.connect(admin_dsn) as conn:
        conn.execute("DELETE FROM answer_cache WHERE course_id=%s", (course_id,))
        conn.execute("DELETE FROM chat_sessions WHERE course_id=%s", (course_id,))
        conn.execute("DELETE FROM request_logs WHERE course_id=%s", (course_id,))
        conn.execute("DELETE FROM ai_guard_events WHERE course_id=%s", (course_id,))
        conn.execute("DELETE FROM ai_token_reservations WHERE course_id=%s", (course_id,))
        conn.commit()


async def _run_probe_for_reserved_tokens(
    base_url: str, admin_dsn: str, seed: SeedData
) -> tuple[int, HttpSample]:
    # Reservation boyutu prompt baytlarindan hesaplanir; ders adi da sistem
    # promptuna girdigi icin probe kota yarisi ile ayni derste kosmalidir.
    course = seed.courses["quota"]
    user = seed.students[0]
    task = asyncio.create_task(
        _request(base_url, user_id=user, course_id=course, question=_QUESTION)
    )
    snapshot = await _wait_for_reservation(admin_dsn, course, user)
    sample = await task
    if sample.status != 200:
        raise AssertionError(f"reservation probe HTTP {sample.status}: {sample.error_code}")
    requested = int(snapshot["max_reserved_tokens"])
    if requested <= 0:
        raise AssertionError("probe reserved_tokens sifir")
    return requested, sample


async def _quota_race(
    base_url: str, admin_dsn: str, seed: SeedData, requested_tokens: int
) -> dict[str, Any]:
    course = seed.courses["quota"]
    _clear_course_turns(admin_dsn, course)
    _set_course_budget(admin_dsn, course, requested_tokens)
    stop = asyncio.Event()
    monitor = asyncio.create_task(
        _poll_metric(
            stop,
            0.01,
            lambda: int(_reservation_snapshot(admin_dsn, course)["charged_tokens"]),
        )
    )
    samples = await asyncio.gather(
        *[
            _request(
                base_url,
                user_id=seed.students[index],
                course_id=course,
                question=_QUESTION,
            )
            for index in range(4)
        ]
    )
    stop.set()
    observed = await monitor
    final = _reservation_snapshot(admin_dsn, course)
    safe_refusals = sum(
        sample.error_code == "agent_quota_exhausted" or sample.answer_status == "budget_exhausted"
        for sample in samples
    )
    accepted = sum(
        sample.status == 200 and sample.answer_status == "answered" for sample in samples
    )
    max_observed = max(observed, default=0)
    overshoot = max(0, max_observed - requested_tokens)
    if accepted != 1 or safe_refusals != 3 or overshoot != 0:
        raise AssertionError(
            f"quota race beklenmeyen sonuc: accepted={accepted}, refused={safe_refusals}, "
            f"max={max_observed}, budget={requested_tokens}, "
            f"samples={[asdict(sample) for sample in samples]}"
        )
    return {
        "requests": len(samples),
        "accepted": accepted,
        "safe_refusals": safe_refusals,
        "http_429": sum(sample.status == 429 for sample in samples),
        "budget_exhausted_200": sum(
            sample.answer_status == "budget_exhausted" for sample in samples
        ),
        "budget_tokens": requested_tokens,
        "max_observed_charged_tokens": max_observed,
        "quota_overshoot_tokens": overshoot,
        "final_charged_tokens": final["charged_tokens"],
        "worker_pids": sorted({s.worker_pid for s in samples if s.worker_pid is not None}),
    }


async def _durable_concurrency(base_url: str, admin_dsn: str, seed: SeedData) -> dict[str, Any]:
    course = seed.courses["concurrency"]
    user = seed.students[1]
    _clear_course_turns(admin_dsn, course)
    first = asyncio.create_task(
        _request(
            base_url,
            user_id=user,
            course_id=course,
            question=f"{_QUESTION} T408_SLOW",
        )
    )
    await _wait_for_reservation(admin_dsn, course, user)
    monitor_stop = asyncio.Event()
    active_monitor = asyncio.create_task(
        _poll_metric(
            monitor_stop,
            0.005,
            lambda: int(_reservation_snapshot(admin_dsn, course, user)["active"]),
        )
    )
    challengers: list[HttpSample] = []
    observed_workers: set[int] = set()
    for batch_index in range(5):
        batch = await asyncio.gather(
            *[
                _request(
                    base_url,
                    user_id=user,
                    course_id=course,
                    question=(f"{_QUESTION} T408 challenger {batch_index}-{request_index}"),
                )
                for request_index in range(4)
            ]
        )
        challengers.extend(batch)
        observed_workers.update(
            sample.worker_pid for sample in batch if sample.worker_pid is not None
        )
        if (
            any(item.error_code == "agent_concurrency_limited" for item in challengers)
            and len(observed_workers) >= 2
        ):
            break
    active_during_challenge = _reservation_snapshot(admin_dsn, course, user)
    first_sample = await first
    monitor_stop.set()
    observed_active = await active_monitor
    durable = [s for s in challengers if s.error_code == "agent_concurrency_limited"]
    local = [s for s in challengers if s.error_code == "concurrent_request"]
    unexpected = [
        sample
        for sample in challengers
        if sample.error_code not in {"agent_concurrency_limited", "concurrent_request"}
    ]
    snapshot = _reservation_snapshot(admin_dsn, course, user)
    workers = {s.worker_pid for s in [first_sample, *challengers] if s.worker_pid is not None}
    peak_active = max(observed_active, default=0)
    if (
        first_sample.status != 200
        or not durable
        or unexpected
        or len(workers) < 2
        or active_during_challenge["active"] != 1
        or peak_active != 1
        or snapshot["active"] != 0
    ):
        raise AssertionError(
            f"durable concurrency kaniti eksik: first={first_sample.status}, "
            f"durable={len(durable)}, local={len(local)}, unexpected={unexpected}, "
            f"workers={workers}, during={active_during_challenge}, peak={peak_active}, "
            f"snapshot={snapshot}"
        )
    return {
        "first_status": first_sample.status,
        "challengers": len(challengers),
        "durable_429": len(durable),
        "process_local_409": len(local),
        "unexpected_responses": len(unexpected),
        "max_active_reservations": peak_active,
        "active_after": snapshot["active"],
        "worker_pids": sorted(workers),
    }


async def _provider_failure_recovery(
    base_url: str, admin_dsn: str, seed: SeedData
) -> dict[str, Any]:
    course = seed.courses["recovery"]
    user = seed.students[2]
    _clear_course_turns(admin_dsn, course)
    failure = await _request(
        base_url,
        user_id=user,
        course_id=course,
        question=f"{_QUESTION} T408_PROVIDER_FAILURE",
    )
    after_failure = _reservation_snapshot(admin_dsn, course, user)
    recovery = await _request(
        base_url,
        user_id=user,
        course_id=course,
        question=f"{_QUESTION} T408 recovered",
    )
    after_recovery = _reservation_snapshot(admin_dsn, course, user)
    if (
        failure.status != 503
        or failure.error_code != "llm_unavailable"
        or after_failure["unreconciled"] != 0
        or after_failure["charged_tokens"] != after_failure["max_reserved_tokens"]
        or recovery.status != 200
    ):
        raise AssertionError(
            f"provider failure/recovery beklenmeyen: failure={failure}, "
            f"after={after_failure}, recovery={recovery}"
        )
    return {
        "failure_http_status": failure.status,
        "failure_code": failure.error_code,
        "failure_unreconciled_after": after_failure["unreconciled"],
        "failure_charge_preserved": True,
        "recovery_http_status": recovery.status,
        "active_after_recovery": after_recovery["active"],
        "worker_pids": sorted(
            {pid for pid in (failure.worker_pid, recovery.worker_pid) if pid is not None}
        ),
    }


def _seed_abandoned_lease(
    admin_dsn: str, *, course_id: UUID, user_id: UUID, lease_seconds: int
) -> UUID:
    reservation_id = uuid4()
    with psycopg.connect(admin_dsn) as conn:
        conn.execute(
            "INSERT INTO ai_token_reservations("
            "id,course_id,user_id,audience,reserved_tokens,charged_tokens,expires_at) "
            "VALUES (%s,%s,%s,'student',64,64,now()+make_interval(secs => %s))",
            (reservation_id, course_id, user_id, lease_seconds),
        )
        conn.commit()
    return reservation_id


async def _abandoned_lease_recovery(
    base_url: str, admin_dsn: str, seed: SeedData
) -> dict[str, Any]:
    course = seed.courses["recovery"]
    user = seed.students[3]
    _clear_course_turns(admin_dsn, course)
    reservation_id = _seed_abandoned_lease(
        admin_dsn, course_id=course, user_id=user, lease_seconds=4
    )
    active_lease = _reservation_snapshot(admin_dsn, course, user)
    blocked = await _request(
        base_url,
        user_id=user,
        course_id=course,
        question=f"{_QUESTION} lease active",
    )
    wait_seconds = active_lease["max_seconds_until_expiry"] + 0.5
    if wait_seconds > 8:
        raise AssertionError(f"lease bekleme guvenlik tavanini asti: {wait_seconds}")
    await asyncio.sleep(wait_seconds)
    recovered = await _request(
        base_url,
        user_id=user,
        course_id=course,
        question=f"{_QUESTION} lease expired",
    )
    final = _reservation_snapshot(admin_dsn, course, user)
    if (
        active_lease["unreconciled"] != 1
        or active_lease["charged_tokens"] != active_lease["max_reserved_tokens"]
        or blocked.status != 429
        or blocked.error_code != "agent_concurrency_limited"
        or recovered.status != 200
        or final["active"] != 0
        or final["unreconciled"] != 1
    ):
        raise AssertionError(
            f"abandoned lease beklenmeyen: active={active_lease}, "
            f"blocked={blocked}, recovered={recovered}, final={final}"
        )
    return {
        "seeded_reservation_id_sha256": hashlib.sha256(str(reservation_id).encode()).hexdigest(),
        "seeded_lease_seconds": 4,
        "unreconciled_while_active": active_lease["unreconciled"],
        "conservative_charge_preserved": True,
        "blocked_during_lease_http_status": blocked.status,
        "blocked_during_lease_code": blocked.error_code,
        "lease_wait_seconds": round(wait_seconds, 2),
        "recovered_after_lease_http_status": recovered.status,
        "unreconciled_old_rows_after_recovery": final["unreconciled"],
        "active_after_recovery": final["active"],
        "worker_pids": sorted(
            {pid for pid in (blocked.worker_pid, recovered.worker_pid) if pid is not None}
        ),
    }


async def _miss_load(
    base_url: str, admin_dsn: str, seed: SeedData, *, worker_count: int
) -> dict[str, Any]:
    courses = (seed.courses["load_a"], seed.courses["load_b"])
    for course in courses:
        _clear_course_turns(admin_dsn, course)
    stop = asyncio.Event()
    pool_monitor = asyncio.create_task(
        _poll_metric(
            stop,
            0.01,
            lambda: _scalar(
                admin_dsn,
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname=%s AND application_name='dou_t408_app'",
                (admin_dsn.rsplit("/", 1)[-1],),
            ),
        )
    )
    samples = await asyncio.gather(
        *[
            _request(
                base_url,
                user_id=user,
                course_id=course,
                question=f"{_QUESTION} load {course_index}-{user_index}",
            )
            for course_index, course in enumerate(courses)
            for user_index, user in enumerate(seed.students[:8])
        ]
    )
    stop.set()
    connections = await pool_monitor
    if any(sample.status != 200 for sample in samples):
        raise AssertionError(
            f"miss load HTTP basarisiz: {[asdict(s) for s in samples if s.status != 200]}"
        )
    workers = {sample.worker_pid for sample in samples if sample.worker_pid is not None}
    if len(workers) < 2:
        raise AssertionError(f"miss load tek worker goruyor: {workers}")
    return {
        "requests": len(samples),
        "http_2xx": sum(200 <= sample.status < 300 for sample in samples),
        "cache_misses": sum(sample.cached is False for sample in samples),
        "transport_errors": sum(sample.transport_error is not None for sample in samples),
        "http_5xx": sum(sample.status >= 500 for sample in samples),
        "latency": _latency_summary(samples),
        "peak_dou_app_connections": max(connections, default=0),
        "configured_pool_capacity": worker_count
        * (
            _REQUEST_POOL_SIZE
            + _REQUEST_POOL_OVERFLOW
            + _CONTROL_POOL_SIZE
            + _CONTROL_POOL_OVERFLOW
        ),
        "worker_pids": sorted(workers),
    }


async def _cache_burst(base_url: str, admin_dsn: str, seed: SeedData) -> dict[str, Any]:
    course = seed.courses["cache"]
    _clear_course_turns(admin_dsn, course)
    warm = await _request(base_url, user_id=seed.students[0], course_id=course, question=_QUESTION)
    before = _reservation_snapshot(admin_dsn, course)
    samples = await asyncio.gather(
        *[
            _request(
                base_url,
                user_id=seed.students[index % 8],
                course_id=course,
                question=_QUESTION,
            )
            for index in range(64)
        ]
    )
    after = _reservation_snapshot(admin_dsn, course)
    if warm.status != 200 or warm.cached is not False:
        raise AssertionError(f"cache warmup beklenmeyen: {warm}")
    if any(sample.status != 200 or sample.cached is not True for sample in samples):
        unexpected = [
            asdict(sample)
            for sample in samples
            if sample.status != 200 or sample.cached is not True
        ][:5]
        raise AssertionError(f"cache burst beklenmeyen: {unexpected}")
    if after["rows"] != before["rows"] or after["charged_tokens"] != before["charged_tokens"]:
        raise AssertionError(f"cache hit reservation acti: before={before}, after={after}")
    workers = {sample.worker_pid for sample in samples if sample.worker_pid is not None}
    if len(workers) < 2:
        raise AssertionError(f"cache burst tek worker goruyor: {workers}")
    return {
        "warmup_cached": warm.cached,
        "requests": len(samples),
        "cache_hits": sum(sample.cached is True for sample in samples),
        "http_2xx": sum(200 <= sample.status < 300 for sample in samples),
        "transport_errors": sum(sample.transport_error is not None for sample in samples),
        "new_reservations": after["rows"] - before["rows"],
        "new_charged_tokens": after["charged_tokens"] - before["charged_tokens"],
        "latency": _latency_summary(samples),
        "worker_pids": sorted(workers),
    }


def _residue(admin_dsn: str, course_ids: Sequence[UUID]) -> dict[str, int]:
    table_counts: dict[str, int] = {}
    tables = (
        "ai_token_reservations",
        "ai_guard_events",
        "answer_cache",
        "chat_sessions",
        "chat_messages",
        "request_logs",
    )
    with psycopg.connect(admin_dsn) as conn:
        with conn.cursor() as cur:
            for table in tables:
                if table == "chat_messages":
                    cur.execute(
                        "SELECT count(*) FROM chat_messages m "
                        "JOIN chat_sessions s ON s.id=m.session_id "
                        "WHERE s.course_id = ANY(%s)",
                        (list(course_ids),),
                    )
                else:
                    cur.execute(
                        f"SELECT count(*) FROM {table} WHERE course_id = ANY(%s)",  # noqa: S608
                        (list(course_ids),),
                    )
                row = cur.fetchone()
                assert row is not None
                table_counts[table] = int(row[0])
    return table_counts


async def _exercise(
    *, base_url: str, admin_dsn: str, seed: SeedData, initial_workers: set[int]
) -> dict[str, Any]:
    requested_tokens, probe = await _run_probe_for_reserved_tokens(base_url, admin_dsn, seed)
    quota = await _quota_race(base_url, admin_dsn, seed, requested_tokens)
    concurrency = await _durable_concurrency(base_url, admin_dsn, seed)
    provider_recovery = await _provider_failure_recovery(base_url, admin_dsn, seed)
    lease_recovery = await _abandoned_lease_recovery(base_url, admin_dsn, seed)
    miss = await _miss_load(base_url, admin_dsn, seed, worker_count=len(initial_workers))
    cache = await _cache_burst(base_url, admin_dsn, seed)
    all_workers = set(initial_workers)
    for section in (quota, concurrency, provider_recovery, lease_recovery, miss, cache):
        all_workers.update(section.get("worker_pids", []))
    return {
        "probe": {
            "reserved_tokens": requested_tokens,
            "http_status": probe.status,
            "worker_pid": probe.worker_pid,
        },
        "quota_race": quota,
        "durable_concurrency": concurrency,
        "provider_failure_recovery": provider_recovery,
        "abandoned_lease_recovery": lease_recovery,
        "multi_course_miss_load": miss,
        "cache_hit_burst": cache,
        "all_observed_worker_pids": sorted(all_workers),
    }


def _git_state() -> dict[str, Any]:
    head = _run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT).stdout.strip()
    status = _run(["git", "status", "--porcelain"], cwd=REPO_ROOT).stdout.splitlines()
    measured_paths = (
        Path("apps/api/app/core/db.py"),
        Path("apps/api/app/modules/agent/quota.py"),
        Path("apps/api/scripts/role_agent_multiworker_load.py"),
        Path("apps/api/tests/test_role_aware_agent.py"),
    )
    return {
        "head": head,
        "working_tree_dirty": bool(status),
        "changed_path_count": len(status),
        "measured_file_sha256": {
            str(path): hashlib.sha256((REPO_ROOT / path).read_bytes()).hexdigest()
            for path in measured_paths
        },
    }


def _report(
    *,
    database_name: str,
    migrations: Sequence[str],
    workers: int,
    port: int,
    results: dict[str, Any],
    log_text: str,
    residue_before_drop: dict[str, int],
) -> dict[str, Any]:
    pool_error_patterns = (
        "QueuePool limit",
        "TimeoutError",
        "too many clients",
        "remaining connection slots",
    )
    pool_errors = sum(log_text.count(pattern) for pattern in pool_error_patterns)
    error_lines = [
        line[-400:]
        for line in log_text.splitlines()
        if any(pattern in line for pattern in pool_error_patterns)
    ][:10]
    pass_conditions = {
        "at_least_two_workers_observed": len(results["all_observed_worker_pids"]) >= 2,
        "quota_overshoot_zero": results["quota_race"]["quota_overshoot_tokens"] == 0,
        "durable_concurrency_rejected_every_challenger": (
            results["durable_concurrency"]["durable_429"] > 0
            and results["durable_concurrency"]["unexpected_responses"] == 0
            and results["durable_concurrency"]["max_active_reservations"] == 1
        ),
        "provider_failure_reconciled_and_recovered": (
            results["provider_failure_recovery"]["failure_unreconciled_after"] == 0
            and results["provider_failure_recovery"]["recovery_http_status"] == 200
        ),
        "abandoned_lease_blocked_then_recovered": (
            results["abandoned_lease_recovery"]["blocked_during_lease_http_status"] == 429
            and results["abandoned_lease_recovery"]["recovered_after_lease_http_status"] == 200
        ),
        "cache_burst_opened_no_reservation": (
            results["cache_hit_burst"]["new_reservations"] == 0
            and results["cache_hit_burst"]["new_charged_tokens"] == 0
        ),
        "no_http_or_pool_errors_in_load_phases": (
            results["multi_course_miss_load"]["http_5xx"] == 0
            and results["multi_course_miss_load"]["transport_errors"] == 0
            and results["cache_hit_burst"]["transport_errors"] == 0
            and pool_errors == 0
        ),
    }
    return {
        "schema_version": 1,
        "evidence_id": "005-t408-multiworker-local-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "label": "fake-provider-local-multiworker-http",
        "status": "pass" if all(pass_conditions.values()) else "fail",
        "privacy": (
            "synthetic UUIDs and aggregate metrics only; no prompt, answer, source text, "
            "email, auth header, secret or raw reservation row retained"
        ),
        "source": _git_state(),
        "environment": {
            "database": database_name,
            "database_disposable": True,
            "migration_first": migrations[0],
            "migration_last": migrations[-1],
            "migration_count": len(migrations),
            "uvicorn_workers": workers,
            "port": port,
            "embedding_provider": "hashing/hashing-v1@builtin-1",
            "llm_provider": "fake/deterministic-v1 with test-only delay",
            "db_pool_size_per_worker": _REQUEST_POOL_SIZE,
            "db_max_overflow_per_worker": _REQUEST_POOL_OVERFLOW,
            "db_control_pool_size_per_worker": _CONTROL_POOL_SIZE,
            "db_control_max_overflow_per_worker": _CONTROL_POOL_OVERFLOW,
            "real_provider": "not_run",
            "staging": "not_run",
            "production": "not_run",
        },
        "pass_conditions": pass_conditions,
        "results": results,
        "pool_pressure": {
            "peak_dou_app_connections": results["multi_course_miss_load"][
                "peak_dou_app_connections"
            ],
            "configured_total_pool_capacity": results["multi_course_miss_load"][
                "configured_pool_capacity"
            ],
            "pool_error_matches": pool_errors,
            "pool_error_classes": error_lines,
        },
        "residue_before_database_drop": residue_before_drop,
        "limitations": [
            "Local laptop timing is not production capacity or an SLO certification.",
            "Hashing retrieval is mechanical and not semantic-quality evidence.",
            "The delayed fake provider proves race/lease behavior, not real-provider latency.",
            "No Supabase Auth/Storage, staging network, WAF or distributed request bucket ran.",
            "The test-admin-seeded abandoned reservation remains conservatively charged "
            "and unreconciled; "
            "lease expiry releases concurrency but does not erase daily charge by design.",
            "No worker was crashed: abandonment was modeled by inserting one synthetic, "
            "precharged active lease into the disposable database.",
            "The regression test saturates the main request pool and proves quota reserve "
            "still completes through the bounded 1+0 control pool; this load run uses the "
            "application's normal 5+5 request-pool profile and does not certify smaller "
            "deployment capacity.",
        ],
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-name")
    parser.add_argument("--port", type=int, default=8068)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--pg-bin",
        type=Path,
        default=Path(os.environ.get("PG_BIN", "/opt/homebrew/opt/postgresql@16/bin")),
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.workers < 2:
        parser.error("T408 en az iki uvicorn iscisi ister")
    generated_name = f"dou_synapse_t408_{os.getpid()}_{int(time.time())}"
    database_name = _validate_database_name(args.database_name or generated_name)
    db = TemporaryDatabase(name=database_name, pg_bin=args.pg_bin)
    storage_root = Path(tempfile.mkdtemp(prefix="dou-t408-storage-"))
    log_path = storage_root.parent / f"dou-t408-{os.getpid()}.log"
    process: subprocess.Popen[str] | None = None
    log_handle: Any | None = None
    report: dict[str, Any] | None = None
    cleanup_done = False
    try:
        migrations = db.create()
        seed = _seed(db.admin_dsn)
        process, log_handle = _start_server(
            db,
            port=args.port,
            workers=args.workers,
            storage_root=storage_root,
            log_path=log_path,
        )
        base_url = f"http://127.0.0.1:{args.port}"
        initial_workers = asyncio.run(_wait_workers(base_url, minimum=args.workers))
        results = asyncio.run(
            _exercise(
                base_url=base_url,
                admin_dsn=db.admin_dsn,
                seed=seed,
                initial_workers=initial_workers,
            )
        )
        residue_before_drop = _residue(db.admin_dsn, list(seed.courses.values()))
        _stop_server(process, log_handle)
        process, log_handle = None, None
        log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        report = _report(
            database_name=database_name,
            migrations=migrations,
            workers=args.workers,
            port=args.port,
            results=results,
            log_text=log_text,
            residue_before_drop=residue_before_drop,
        )
        cleanup = _cleanup_resources(
            process=None,
            log_handle=None,
            db=db,
            storage_root=storage_root,
            log_path=log_path,
        )
        cleanup_done = True
        cleanup_ok = (
            cleanup["exact_database_absent_after_drop"]
            and cleanup["exact_storage_path_absent"]
            and cleanup["exact_log_path_absent"]
            and not cleanup["cleanup_errors"]
        )
        report["cleanup"] = cleanup
        report["pass_conditions"]["exact_cleanup_has_zero_residue"] = cleanup_ok
        report["status"] = "pass" if all(report["pass_conditions"].values()) else "fail"
        if args.report:
            _write_report(args.report, report)
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0 if report["status"] == "pass" else 1
    except Exception:
        if log_handle is not None:
            log_handle.flush()
        if log_path.exists():
            tail = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
            sys.stderr.write("\n--- T408 uvicorn log tail ---\n")
            sys.stderr.write("\n".join(tail) + "\n")
        raise
    finally:
        if not cleanup_done:
            cleanup = _cleanup_resources(
                process=process,
                log_handle=log_handle,
                db=db,
                storage_root=storage_root,
                log_path=log_path,
            )
            if (
                cleanup["cleanup_errors"]
                or not cleanup["exact_database_absent_after_drop"]
                or not cleanup["exact_storage_path_absent"]
                or not cleanup["exact_log_path_absent"]
            ):
                sys.stderr.write(f"T408 cleanup incomplete: {cleanup}\n")


if __name__ == "__main__":
    raise SystemExit(main())
