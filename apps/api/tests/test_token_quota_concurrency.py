"""İki gerçek bağlantıda token kabulü ve COMMIT öncesi iptal sözleşmesi.

Yalnız kökün kimliğini doğruladığı izole test DB'sinde çalıştırılır. Ortak
conftest'in DB/rol kurulumunu bu dosya değiştirmez veya atlamaz. Sağlayıcı
çağrılmaz; COMMIT edilmiş bilinmeyen kullanıma sıfır iade yapılmaz.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app.core.db import get_engine
from tests.conftest import TEST_DB, UserFactory
from tests.factories import create_course

LimitScope = Literal["course", "global_user", "platform"]
TEST_TIMEOUT_SECONDS = 25
WAIT_TIMEOUT_SECONDS = 4
CLEANUP_TIMEOUT_SECONDS = 5


@dataclass(frozen=True, slots=True)
class QuotaCase:
    user_ids: tuple[UUID, UUID]
    course_ids: tuple[UUID, UUID]
    user_limit: int
    course_limit: int
    platform_limit: int


@dataclass(frozen=True, slots=True)
class ConnectionIdentity:
    pid: int
    target: tuple[object, ...]
    transaction_id: str


@dataclass(frozen=True, slots=True)
class Reservation:
    allowed: bool
    reason: str | None
    reservation_id: UUID | None


async def _seed_case(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    scope: LimitScope,
) -> QuotaCase:
    owner = await users.create(f"token-race-{scope}-a@synthetic.invalid")
    second_owner = (
        await users.create(f"token-race-{scope}-b@synthetic.invalid")
        if scope == "platform"
        else owner
    )
    first_course = await create_course(client, users.auth(owner), f"D1-{scope}-A")
    second_course = (
        first_course
        if scope == "course"
        else await create_course(client, users.auth(second_owner), f"D1-{scope}-B")
    )
    course_limit = 5000 if scope == "course" else 20_000
    async with admin_engine.begin() as connection:
        for course_id in dict.fromkeys((first_course, second_course)):
            await connection.execute(
                text(
                    "INSERT INTO course_ai_policies "
                    "(course_id, daily_token_budget, instructor_daily_token_budget, "
                    "max_concurrent_requests) VALUES (:course_id, :budget, 20000, 2)"
                ),
                {"course_id": course_id, "budget": course_limit},
            )
    return QuotaCase(
        user_ids=(owner, second_owner),
        course_ids=(first_course, second_course),
        user_limit=5000 if scope == "global_user" else 20_000,
        course_limit=course_limit,
        platform_limit=5000 if scope == "platform" else 50_000,
    )


async def _identity(connection: AsyncConnection, *, app_role: bool) -> ConnectionIdentity:
    row = (
        await connection.execute(
            text(
                "SELECT pg_backend_pid(), current_database(), "
                "(SELECT oid FROM pg_catalog.pg_database WHERE datname=current_database()), "
                "inet_server_addr()::text, inet_server_port(), pg_postmaster_start_time(), "
                "pg_current_xact_id()::text, current_user, r.rolsuper, r.rolbypassrls "
                "FROM pg_catalog.pg_roles r WHERE r.rolname=current_user"
            )
        )
    ).one()
    assert row[1] == TEST_DB, "Bağlantı fixture'ın izole test veritabanına gitmeli."
    if app_role:
        assert tuple(row[7:]) == ("dou_app", False, False)
    return ConnectionIdentity(pid=row[0], target=tuple(row[1:6]), transaction_id=row[6])


async def _prepare(connection: AsyncConnection, user_id: UUID) -> ConnectionIdentity:
    assert connection.in_transaction(), "RLS bağlamından önce açık transaction gerekli."
    await connection.execute(
        text(
            "SELECT set_config('app.current_user_id', :user_id, true), "
            "set_config('lock_timeout', '8000ms', true), "
            "set_config('statement_timeout', '12000ms', true)"
        ),
        {"user_id": str(user_id)},
    )
    isolation = (await connection.execute(text("SHOW transaction_isolation"))).scalar_one()
    assert isolation == "read committed"
    return await _identity(connection, app_role=True)


async def _reserve(connection: AsyncConnection, case: QuotaCase, index: int) -> Reservation:
    row = (
        await connection.execute(
            text(
                "SELECT allowed, reason, reservation_id "
                "FROM app.reserve_course_agent_tokens("
                ":course_id, :reservation_id, 3000, 60, "
                ":user_limit, :course_limit, :platform_limit)"
            ),
            {
                "course_id": case.course_ids[index],
                "reservation_id": uuid4(),
                "user_limit": case.user_limit,
                "course_limit": case.course_limit,
                "platform_limit": case.platform_limit,
            },
        )
    ).one()
    assert type(row.allowed) is bool
    return Reservation(row.allowed, row.reason, row.reservation_id)


async def _ledger(observer: AsyncConnection) -> tuple[int, int]:
    row = (
        await observer.execute(
            text(
                "SELECT count(*), COALESCE(sum(charged_tokens), 0) "
                "FROM public.ai_token_reservations"
            )
        )
    ).one()
    return int(row[0]), int(row[1])


async def _advisory_wait_or_completion(
    observer: AsyncConnection,
    *,
    first_pid: int,
    second_pid: int,
    second: asyncio.Task[Reservation],
) -> bool:
    # İlk transaction açıkken ikinci SQL'in gerçekten sunucuda beklediğini gör.
    # Kilit kaldırılmış mutant erken dönerse iki commit'i de tamamlatıp aşağıdaki
    # kabul/toplam assertion'ında yanlış iki kabulü ve 6000'i görünür bırak.
    async with asyncio.timeout(WAIT_TIMEOUT_SECONDS):
        while True:
            waiting = await observer.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_locks "
                    "WHERE pid=:waiting_pid AND locktype='advisory' AND NOT granted) "
                    "AND :blocking_pid=ANY(pg_catalog.pg_blocking_pids(:waiting_pid))"
                ),
                {"waiting_pid": second_pid, "blocking_pid": first_pid},
            )
            if waiting:
                return True
            if second.done():
                return False
            await asyncio.sleep(0.01)


async def _cancel_and_join(*tasks: asyncio.Task[Reservation]) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
    # Bağlantıyı kullanan görev bitmeden havuza dönüş veya yeni test başlamaz.
    async with asyncio.timeout(CLEANUP_TIMEOUT_SECONDS):
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.parametrize("scope", ["course", "global_user", "platform"])
async def test_two_physical_transactions_admit_exactly_one_3000_token_reservation(
    scope: LimitScope,
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    async with asyncio.timeout(TEST_TIMEOUT_SECONDS):
        case = await _seed_case(client, users, admin_engine, scope)
        first_reserved, second_started, allow_commit = (
            asyncio.Event(),
            asyncio.Event(),
            asyncio.Event(),
        )
        identities: dict[str, ConnectionIdentity] = {}

        async def first_request() -> Reservation:
            async with get_engine().connect() as connection, connection.begin():
                identities["first"] = await _prepare(connection, case.user_ids[0])
                result = await _reserve(connection, case, 0)
                assert result.allowed and result.reservation_id is not None
                first_reserved.set()
                await allow_commit.wait()
            return result

        async def second_request() -> Reservation:
            async with get_engine().connect() as connection, connection.begin():
                identities["second"] = await _prepare(connection, case.user_ids[1])
                await first_reserved.wait()
                second_started.set()
                result = await _reserve(connection, case, 1)
            return result

        async with admin_engine.connect() as observer, observer.begin():
            observer_id = await _identity(observer, app_role=False)
            await observer.execute(text("SET LOCAL statement_timeout='2000ms'"))
            assert await _ledger(observer) == (0, 0), "Test DB'sinde eski token yükü olmamalı."
            first = asyncio.create_task(first_request())
            second = asyncio.create_task(second_request())
            try:
                await first_reserved.wait()
                await second_started.wait()
                first_id, second_id = identities["first"], identities["second"]
                assert first_id.target == second_id.target == observer_id.target
                assert len({first_id.pid, second_id.pid, observer_id.pid}) == 3
                assert first_id.transaction_id != second_id.transaction_id
                saw_advisory_wait = await _advisory_wait_or_completion(
                    observer,
                    first_pid=first_id.pid,
                    second_pid=second_id.pid,
                    second=second,
                )
                allow_commit.set()
                results = await asyncio.gather(first, second)
                row_count, total_charge = await _ledger(observer)
                observed = (
                    sum(result.allowed for result in results),
                    tuple(result.reason for result in results if not result.allowed),
                    row_count,
                    total_charge,
                )
                assert observed == (1, ("quota_exhausted",), 1, 3000)
                assert saw_advisory_wait, "İki farklı işlem advisory lock üzerinde örtüşmeli."
                assert results[0].allowed and results[1].reservation_id is None
            finally:
                await _cancel_and_join(first, second)


async def test_cancel_before_commit_rolls_back_then_allows_a_new_reservation(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    async with asyncio.timeout(TEST_TIMEOUT_SECONDS):
        case = await _seed_case(client, users, admin_engine, "course")
        first_reserved, second_ready, allow_retry, never_commit = (
            asyncio.Event(),
            asyncio.Event(),
            asyncio.Event(),
            asyncio.Event(),
        )
        identities: dict[str, ConnectionIdentity] = {}
        reservations: dict[str, Reservation] = {}

        async def cancelled_request() -> Reservation:
            async with get_engine().connect() as connection, connection.begin():
                identities["first"] = await _prepare(connection, case.user_ids[0])
                result = await _reserve(connection, case, 0)
                assert result.allowed and result.reservation_id is not None
                reservations["cancelled"] = result
                first_reserved.set()
                await never_commit.wait()
            return result

        async def retry_request() -> Reservation:
            async with get_engine().connect() as connection, connection.begin():
                identities["second"] = await _prepare(connection, case.user_ids[1])
                second_ready.set()
                await allow_retry.wait()
                result = await _reserve(connection, case, 1)
            return result

        async with admin_engine.connect() as observer, observer.begin():
            observer_id = await _identity(observer, app_role=False)
            await observer.execute(text("SET LOCAL statement_timeout='2000ms'"))
            assert await _ledger(observer) == (0, 0)
            first = asyncio.create_task(cancelled_request())
            retry = asyncio.create_task(retry_request())
            try:
                await first_reserved.wait()
                await second_ready.wait()
                first_id, second_id = identities["first"], identities["second"]
                assert first_id.target == second_id.target == observer_id.target
                assert len({first_id.pid, second_id.pid, observer_id.pid}) == 3
                assert first_id.transaction_id != second_id.transaction_id
                # İlk SQL kabul verdi; transaction henüz commit edilmedi.
                assert await _ledger(observer) == (0, 0)
                first.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await first
                assert await _ledger(observer) == (0, 0)
                assert not await observer.scalar(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_locks "
                        "WHERE pid=:pid AND locktype='advisory' AND granted)"
                    ),
                    {"pid": first_id.pid},
                ), "İptal transaction kilitlerini bırakmalı."
                allow_retry.set()
                accepted = await retry
                assert accepted.allowed and accepted.reason is None
                assert accepted.reservation_id is not None
                assert accepted.reservation_id != reservations["cancelled"].reservation_id
                assert await _ledger(observer) == (1, 3000)
                surviving_id = (
                    await observer.execute(text("SELECT id FROM public.ai_token_reservations"))
                ).scalar_one()
                assert surviving_id == accepted.reservation_id
            finally:
                await _cancel_and_join(first, retry)
