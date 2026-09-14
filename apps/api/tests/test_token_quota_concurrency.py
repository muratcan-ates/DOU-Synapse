"""Sağlayıcı TOKEN bütçesinde çok-süreçli yarışın ÖLÇÜMÜ (iki ayrı bağlantıyla).

## Neden ayrı bir dosya, neden kendi bağlantıları

`tests/test_role_aware_agent.py` içindeki "atomic" vakalar iki rezervasyonu
`asyncio.gather` ile başlatıyor, ama ikisi de `app.modules.agent.quota.reserve`
üzerinden gidiyor ve o yol `app/core/db.py::control_rls_session`'ın TEK
bağlantılı havuzunu (`pool_size=1, max_overflow=0`) kullanıyor. Yani o iki çağrı
veritabanına aynı anda ULAŞMIYOR: ikincisi birincinin bağlantıyı bırakmasını
bekliyor. Tek bağlantıda seri koşan iki çağrı, veritabanının yarışı kapatıp
kapatmadığı hakkında hiçbir şey kanıtlamaz — sadece havuzun tek bağlantılı
olduğunu kanıtlar (bu dosyanın son testi tam olarak onu ölçer).

Buradaki testler bu yüzden kendi motorlarını kurar: üretimdeki `dou_app` rolüyle,
`NullPool` ile, her çağrı için AYRI bir fiziksel bağlantı. Üretimde de tek bir
worker değil, birden fazla API süreci/bağlantısı vardır; ölçülmesi gereken
davranış budur.

## Ölçülen senaryo

Ders günlük token bütçesi 5.000 iken, aynı dersin iki farklı öğrencisi aynı anda
3.000'lik rezervasyon dener. Doğru davranış fail-closed'dır (Anayasa IV): tam
BİRİ kabul edilir, diğeri `quota_exhausted` ile reddedilir. İkisinin de geçmesi
bütçeyi 6.000'e taşırdı; ikisinin de düşmesi kimsenin bütçeyi kullanamaması
demek olurdu.

Farklı İKİ öğrenci kullanılmasının nedeni, `max_concurrent_requests` varsayılanı
1 olduğu için aynı kullanıcının ikinci isteğinin bütçe hesabına hiç varmadan
`concurrency_limited` ile dönmesidir; o dal token bütçesi yarışını ölçmez.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.db import control_rls_session
from tests.conftest import APP_DSN, UserFactory
from tests.factories import create_course, enroll_student

COURSE_DAILY_BUDGET = 5_000
RESERVATION_TOKENS = 3_000
USER_HARD_LIMIT = 50_000
COURSE_HARD_LIMIT = 500_000
PLATFORM_HARD_LIMIT = 5_000_000
LEASE_SECONDS = 60

# İkinci rezervasyonun gerçekten BEKLEDİĞİNİ (kendi anlık görüntüsüyle ilerleyip
# bütçeyi ikinci kez harcamadığını) görmek için tanınan süre. Kilit varsa bu süre
# dolduğunda görev hâlâ beklemededir; kilit yoksa çoktan bitmiş olur.
OVERLAP_OBSERVATION_SECONDS = 0.5


@dataclass(frozen=True, slots=True)
class QuotaFixture:
    """Günlük ders bütçesi 5.000'e sabitlenmiş, iki öğrencili ders."""

    course_id: UUID
    first_student: UUID
    second_student: UUID


@asynccontextmanager
async def _independent_connection(user_id: UUID) -> AsyncIterator[AsyncConnection]:
    """Uygulamanın tek bağlantılı kontrol havuzundan bağımsız, gerçek bir bağlantı.

    `NullPool` bilinçli: havuz paylaşımı olmadığı için bu bağlam yöneticisinin
    her örneği kendi fiziksel bağlantısını açar. Rol üretimdeki `dou_app`'tir —
    superuser'a geçirilseydi RLS sessizce atlanır ve ölçüm anlamsızlaşırdı.
    """
    engine = create_async_engine(APP_DSN, poolclass=NullPool, hide_parameters=True)
    try:
        async with engine.connect() as connection:
            await connection.execute(
                text("SELECT set_config('app.current_user_id', :uid, true)"),
                {"uid": str(user_id)},
            )
            yield connection
    finally:
        await engine.dispose()


async def _reserve(connection: AsyncConnection, course_id: UUID) -> dict[str, Any]:
    """Rezervasyon fonksiyonunu çağırır; işlemi KAPATMAZ (çağıran commit eder)."""
    result = await connection.execute(
        text(
            "SELECT allowed, reason, reservation_id "
            "FROM app.reserve_course_agent_tokens("
            ":course_id, :reservation_id, :requested_tokens, :lease_seconds, "
            ":user_hard_limit, :course_hard_limit, :platform_hard_limit)"
        ),
        {
            "course_id": course_id,
            "reservation_id": uuid4(),
            "requested_tokens": RESERVATION_TOKENS,
            "lease_seconds": LEASE_SECONDS,
            "user_hard_limit": USER_HARD_LIMIT,
            "course_hard_limit": COURSE_HARD_LIMIT,
            "platform_hard_limit": PLATFORM_HARD_LIMIT,
        },
    )
    return dict(result.mappings().one())


async def _two_student_course(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    *,
    suffix: str,
) -> QuotaFixture:
    instructor_id = await users.create(f"quota.race.teacher.{suffix}@dogus.edu.tr")
    headers = users.auth(instructor_id)
    course_id = await create_course(client, headers, f"TQ-{suffix[:8]}")
    students: list[UUID] = []
    for index in ("a", "b"):
        email = f"quota.race.{index}.{suffix}@dogus.edu.tr"
        students.append(await users.create(email))
        await enroll_student(client, headers, course_id, email)
    async with admin_engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO course_ai_policies (course_id, daily_token_budget) "
                "VALUES (:course_id, :budget)"
            ),
            {"course_id": course_id, "budget": COURSE_DAILY_BUDGET},
        )
    return QuotaFixture(course_id, students[0], students[1])


async def _ledger(admin_engine: AsyncEngine, course_id: UUID) -> dict[str, Any]:
    async with admin_engine.begin() as connection:
        result = await connection.execute(
            text(
                "SELECT count(*)::int AS reservations, "
                "COALESCE(sum(charged_tokens), 0)::int AS charged "
                "FROM ai_token_reservations WHERE course_id = :course_id"
            ),
            {"course_id": course_id},
        )
        return dict(result.mappings().one())


async def _guard_events(admin_engine: AsyncEngine, course_id: UUID) -> list[str]:
    async with admin_engine.begin() as connection:
        result = await connection.execute(
            text("SELECT event_type FROM ai_guard_events WHERE course_id = :course_id"),
            {"course_id": course_id},
        )
        return sorted(row[0] for row in result)


async def test_overlapping_reservations_on_two_connections_admit_exactly_one(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    """Örtüşme ZORLANARAK ölçülür: ikinci rezervasyon birincisi commit etmeden başlar.

    `asyncio.gather` ile iki çağrıyı "aynı anda" başlatmak, gerçekten örtüştüklerini
    garanti etmez — biri diğeri bitmeden sonra da başlayabilir ve test yarışı hiç
    görmeden yeşil yanar. Burada sıralama elle kurulur: birinci bağlantı işlemini
    AÇIK tutarken ikinci bağlantı aynı bütçeye girer. Doğru uygulamada ikinci
    işlem bu noktada BEKLER (rezervasyon fonksiyonu `pg_advisory_xact_lock`
    alıyor); beklemeseydi kendi eski anlık görüntüsünü okur ve 3.000 + 3.000 =
    6.000 ile 5.000'lik bütçeyi aşardı.
    """
    fixture = await _two_student_course(client, users, admin_engine, suffix="overlap")

    async with (
        _independent_connection(fixture.first_student) as first,
        _independent_connection(fixture.second_student) as second,
    ):
        first_result = await _reserve(first, fixture.course_id)
        assert first_result["allowed"] is True, first_result
        assert first_result["reservation_id"] is not None

        pending = asyncio.create_task(_reserve(second, fixture.course_id))
        await asyncio.sleep(OVERLAP_OBSERVATION_SECONDS)
        assert not pending.done(), (
            "İkinci rezervasyon, birincisi commit etmeden karar verdi: bütçe kararı "
            "eski anlık görüntüden okunuyor demektir. Yarış açık."
        )

        await first.commit()
        second_result = await asyncio.wait_for(pending, timeout=10)
        await second.commit()

    assert second_result["allowed"] is False, second_result
    assert second_result["reason"] == "quota_exhausted"
    assert second_result["reservation_id"] is None
    assert await _ledger(admin_engine, fixture.course_id) == {
        "reservations": 1,
        "charged": RESERVATION_TOKENS,
    }
    assert await _guard_events(admin_engine, fixture.course_id) == ["quota_exhausted"]


async def test_simultaneous_reservations_never_exceed_course_budget(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    """Sıralama zorlanmadan, iki bağlantı serbest yarıştırılır.

    Bu vaka örtüşmeyi garanti etmez (işletim sistemi sıralamasına bağlıdır), ama
    örtüştüğünde de sonucun değişmemesi gerekir: defterdeki toplam hiçbir
    sıralamada bütçeyi aşmamalıdır.
    """
    fixture = await _two_student_course(client, users, admin_engine, suffix="gather")

    async def attempt(user_id: UUID) -> dict[str, Any]:
        async with _independent_connection(user_id) as connection:
            result = await _reserve(connection, fixture.course_id)
            await connection.commit()
            return result

    results = await asyncio.gather(attempt(fixture.first_student), attempt(fixture.second_student))

    assert sum(bool(result["allowed"]) for result in results) == 1, results
    assert {result["reason"] for result in results if not result["allowed"]} == {"quota_exhausted"}
    ledger = await _ledger(admin_engine, fixture.course_id)
    assert ledger == {"reservations": 1, "charged": RESERVATION_TOKENS}
    assert ledger["charged"] <= COURSE_DAILY_BUDGET


async def test_application_control_pool_serializes_reservations_on_one_connection(
    client: AsyncClient,
) -> None:
    """Bu dosyanın kendi bağlantılarını açmasının gerekçesini ÖLÇER.

    `agent_quota.reserve` üzerinden `asyncio.gather` ile başlatılan iki rezervasyon
    veritabanına eşzamanlı varmaz: kontrol havuzu tek bağlantılıdır ve ikinci çağrı
    birincinin bağlantıyı bırakmasını bekler. Dolayısıyla o yolla yazılmış bir
    "atomiklik" testi yarışı değil, havuz darboğazını ölçer.

    Bu davranış bir kusur DEĞİLDİR (havuz bilinçli olarak sınırlı; bkz.
    `app/core/db.py::_build_control_engine`), ama tek süreçte yarışı gizler —
    üretimde birden fazla API süreci olduğunda gizlemez.
    """
    async with control_rls_session(uuid4()):
        with pytest.raises(TimeoutError):
            async with asyncio.timeout(1):
                async with control_rls_session(uuid4()):
                    pass  # pragma: no cover - havuz tek bağlantılıysa buraya girilmez
