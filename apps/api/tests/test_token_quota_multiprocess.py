"""D1' ölçümü: token rezervasyonu ÇOK SÜREÇTE de atomik mi?

## Neden bu dosya var

Runbook D1' maddesi, sağlayıcı token bütçesi için ayrı bir sabit pencere tablosu
(`0028_ai_quota_windows.sql`) öneriyordu — ama önüne bir koşul koyuyordu:
"yalnız `ai_token_reservations`'ın çok-süreçte yarış verdiği ÖLÇÜLÜRSE".

Depoda bugün var olan atomiklik testleri (`test_role_aware_agent.py`) `asyncio.gather`
kullanıyor. Bu testler tek süreç, tek bağlantı havuzu içinde koşar. Aynı havuzdaki iki
bağlantı gerçekten ayrı PostgreSQL oturumudur, dolayısıyla test anlamlıdır; ama
üretimdeki asıl korku farklıdır: **iki ayrı uvicorn işçisi** (iki ayrı süreç, iki ayrı
havuz, iki ayrı olay döngüsü) aynı anda son kota dilimini okur ve ikisi de kabul eder.
Tek süreçli bir test bu senaryoyu kuramaz — süreç sınırını geçemediği için.

Bu dosya o sınırı geçer: iki ayrı işletim sistemi süreci açar, ikisini bir bariyerde
buluşturur ve aynı anda rezervasyon isteterek sonucu ÖLÇER.

## Ölçtüğü sözleşme

Bütçe 5.000 token, her süreç 3.000 ister. Doğru davranışta tam olarak biri kabul edilir;
toplam yük bütçeyi AŞMAZ. Yanlış davranışta ikisi de kabul edilir ve 6.000 > 5.000 olur
(overshoot). Üçüncü bir olasılık — ikisinin de reddi — de hatadır: kota tamamen kapanmış
demektir.

Mekanizma `0015_role_aware_course_agent.sql` içindeki
`pg_advisory_xact_lock(hashtextextended('course-agent-platform-daily', 15015))`
satırıdır: rezervasyon transaction'larını kısa süreliğine seri hâle getirir ve
sağlayıcı çağrısından ÖNCE commit eder, yani yavaş LLM çağrısını kapsamaz.

Bu test kırmızı yanarsa D1' yeniden açılır ve 0028 göçü gündeme gelir. Yeşil yanıyorsa
yeni göç gereksizdir; kararın gerekçesi ölçümdür, tahmin değil.
"""

from __future__ import annotations

import multiprocessing as mp
import os
from typing import Any
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import UserFactory
from tests.factories import create_course

# Bütçe ve istek: 2 x 3.000 > 5.000. Tam biri geçmeli.
COURSE_BUDGET = 5_000
REQUEST_TOKENS = 3_000
BARRIER_TIMEOUT_SECONDS = 30.0


def _reserve_in_child(
    dsn: str,
    user_id: str,
    course_id: str,
    barrier: Any,
    results: Any,
    index: int,
) -> None:
    """Ayrı süreçte kendi motorunu kurup tek bir rezervasyon dener.

    Süreç `spawn` ile başladığı için modüller burada YENİDEN içe aktarılır; bu
    kasıtlıdır. Ebeveynin motorunu miras almak testin kanıtlamak istediği şeyi
    (ayrı havuz, ayrı oturum) yok ederdi.
    """
    os.environ["DATABASE_URL"] = dsn
    os.environ.setdefault("DEV_AUTH_ENABLED", "true")
    os.environ.setdefault("EMBEDDING_PROVIDER", "hashing")

    import asyncio

    from sqlalchemy import text

    from app.core.db import rls_session
    from app.modules.agent import quota as agent_quota

    async def run() -> tuple[bool, str | None]:
        # Motor ilk kullanımda kurulur; bariyerden ÖNCE bir kez ısıtılır ki iki
        # süreç kota kararında buluşsun, bağlantı kurma gecikmesinde değil.
        # Isıtma olmadan yavaş açılan çocuk hızlı olanın işini bitmiş bulur ve
        # test yarışı hiç kurmadan yeşil yanar — yani hiçbir şey kanıtlamaz.
        async with rls_session(UUID(user_id)) as warmup:
            await warmup.execute(text("SELECT 1"))
        barrier.wait(BARRIER_TIMEOUT_SECONDS)
        reservation = await agent_quota.reserve(
            user_id=UUID(user_id),
            course_id=UUID(course_id),
            requested_tokens=REQUEST_TOKENS,
            lease_seconds=60,
            user_hard_limit=50_000,
            course_hard_limit=500_000,
            platform_hard_limit=5_000_000,
        )
        return bool(reservation.allowed), reservation.reason

    try:
        results[index] = asyncio.run(run())
    # Çocuğun her hatası ebeveyne taşınmalı; yutulan hata "test geçti" gibi görünür.
    except BaseException as exc:
        results[index] = (False, f"child-error: {type(exc).__name__}: {exc}")


class TestTokenQuotaMultiProcess:
    async def test_two_processes_cannot_both_take_the_last_slice(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        instructor_id = await users.create("quota.multiproc@dogus.edu.tr")
        headers = users.auth(instructor_id)
        course_id = await create_course(client, headers, "QUOTA-MP")
        async with admin_engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO course_ai_policies "
                    "(course_id, instructor_daily_token_budget, daily_token_budget, "
                    " max_concurrent_requests) "
                    "VALUES (:c, :b, :b, 4) "
                    "ON CONFLICT (course_id) DO UPDATE SET "
                    "  instructor_daily_token_budget = EXCLUDED.instructor_daily_token_budget, "
                    "  daily_token_budget = EXCLUDED.daily_token_budget, "
                    "  max_concurrent_requests = EXCLUDED.max_concurrent_requests"
                ),
                {"c": course_id, "b": COURSE_BUDGET},
            )

        dsn = os.environ["DATABASE_URL"]
        context = mp.get_context("spawn")
        manager = context.Manager()
        results = manager.list([None, None])
        barrier = manager.Barrier(2)
        children = [
            context.Process(
                target=_reserve_in_child,
                args=(dsn, str(instructor_id), str(course_id), barrier, results, index),
            )
            for index in range(2)
        ]
        for child in children:
            child.start()
        for child in children:
            child.join(timeout=120)
            assert child.exitcode == 0, f"çocuk süreç {child.pid} çıkış kodu {child.exitcode}"

        outcomes = list(results)
        assert all(item is not None for item in outcomes), f"çocuk sonuç yazmadı: {outcomes}"
        allowed = [item for item in outcomes if item[0]]
        refused = [item for item in outcomes if not item[0]]
        assert not any("child-error" in (item[1] or "") for item in outcomes), outcomes

        # Asıl sözleşme: tam bir kabul. İki kabul = overshoot, sıfır kabul = kilitli kota.
        assert len(allowed) == 1, f"tam bir kabul bekleniyordu, ölçülen: {outcomes}"
        assert refused[0][1] == "quota_exhausted", outcomes

        # Defterde de kanıt: yüklenen toplam bütçeyi aşmamalı.
        async with admin_engine.begin() as connection:
            charged = (
                await connection.execute(
                    text(
                        "SELECT COALESCE(sum(charged_tokens), 0) "
                        "FROM ai_token_reservations WHERE course_id = :c"
                    ),
                    {"c": course_id},
                )
            ).scalar_one()
        assert charged == REQUEST_TOKENS, f"defterde overshoot: {charged}"
