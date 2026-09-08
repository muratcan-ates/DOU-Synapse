"""Gerçek dou_app/dou_worker izinleri; kökün izole stage conftest'i altında koşar.

Bu dosya DB kurmaz ve üretim yetki fonksiyonlarını değiştirmez. Admin yalnız
sentetik başlangıç durumu ile mutasyon sonrası bağımsız ölçüm için kullanılır.
"""

from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.db import get_session_factory, set_rls_context
from tests import test_worker_recovery as recovery
from tests.factories import create_course, enroll_student

# Mevcut fixture kaydı; aynı kurulumun ikinci kopyası oluşturulmaz.
pending_source = recovery.pending_source


@asynccontextmanager
async def application_session(actor):
    """Ürün havuzunun gerçek rolü ve işlem kapsamlı öznesi değiştirilmeden sınanır."""
    async with get_session_factory()() as session, session.begin():
        if actor is not None:
            await set_rls_context(session, actor)
        else:
            assert await session.scalar(text("SELECT app.current_user_id()")) is None
        identity = (
            await session.execute(
                text(
                    "SELECT current_user,session_user,rolsuper,rolbypassrls,"
                    "current_setting('row_security') FROM pg_catalog.pg_roles "
                    "WHERE rolname=current_user"
                )
            )
        ).one()
        assert tuple(identity) == ("dou_app", "dou_app", False, False, "on")
        yield session


def owner_id(headers):
    return UUID(headers["Authorization"].removeprefix("Bearer dev:"))


async def state(engine, document):
    """İzin denemeleri arasında gerçek iş ve belge değerlerini karşılaştırır."""
    async with engine.connect() as connection:
        document_state = dict(
            (
                await connection.execute(
                    text("SELECT * FROM public.documents WHERE id=:id"), {"id": document}
                )
            )
            .mappings()
            .one()
        )
        jobs = [
            dict(row)
            for row in (
                await connection.execute(
                    text("SELECT * FROM public.ingestion_jobs WHERE document_id=:id ORDER BY id"),
                    {"id": document},
                )
            )
            .mappings()
            .all()
        ]
    return document_state, jobs


async def forbidden(actor, query, values):
    with pytest.raises(DBAPIError) as caught:
        async with application_session(actor) as session:
            await session.execute(text(query), values)
    assert caught.value.orig.sqlstate == "42501"


async def fail_fixture(engine, document):
    """Hazır pending işi terminal geçmişe çevirir; burada worker hatası sınanmıyor."""
    async with engine.begin() as connection:
        updated = await connection.execute(
            text(
                "UPDATE public.ingestion_jobs SET status='failed',attempt_count=3,"
                "last_error='compute_failed',started_at=clock_timestamp(),"
                "completed_at=clock_timestamp() WHERE document_id=:id RETURNING id"
            ),
            {"id": document},
        )
        assert len(updated.all()) == 1
        await connection.execute(
            text(
                "UPDATE public.documents SET status='failed',error_message='Sentetik hata' "
                "WHERE id=:id"
            ),
            {"id": document},
        )


async def outsiders(client, users, headers, course):
    """Ders rolü, başka dersin eğitmenliği ve öznesiz çağrı ayrı örneklerdir."""
    student_email = "d2-student@example.com"
    student = await users.create(student_email)
    await enroll_student(client, headers, course, student_email)
    mixed_email = "d2-mixed@example.com"
    mixed = await users.create(mixed_email)
    await enroll_student(client, headers, course, mixed_email)
    await create_course(client, users.auth(mixed), "D2MIXED")
    foreign = await users.create("d2-foreign@example.com")
    await create_course(client, users.auth(foreign), "D2FOREIGN")
    return (None, student, mixed, foreign, uuid4())


async def test_app_pending_enqueue_positive_cannot_forge_processing_or_update_job(
    pending_source, admin_engine
):
    _factory, document, headers, _course = pending_source
    actor = owner_id(headers)
    # Gerçek upload olumlu kontrolü zaten pending iş oluşturdu. Yeni INSERT için
    # yalnız bu testin başlangıç işini kaldır; yoksa UNIQUE önce reddedebilir.
    async with admin_engine.begin() as connection:
        removed = await connection.execute(
            text("DELETE FROM public.ingestion_jobs WHERE document_id=:id RETURNING id"),
            {"id": document},
        )
        assert len(removed.all()) == 1
    before = await state(admin_engine, document)
    assert before[1] == []
    await forbidden(
        actor,
        "INSERT INTO public.ingestion_jobs "
        "(document_id,status,attempt_count,claim_token,claim_document_revision,lease_expires_at) "
        "VALUES (:id,'processing',1,:token,1,clock_timestamp()+interval '60 seconds')",
        {"id": document, "token": uuid4()},
    )
    assert await state(admin_engine, document) == before
    async with application_session(actor) as session:
        job = await session.scalar(
            text("INSERT INTO public.ingestion_jobs(document_id) VALUES(:id) RETURNING id"),
            {"id": document},
        )
        assert job is not None
    allowed = await state(admin_engine, document)
    assert len(allowed[1]) == 1 and allowed[1][0]["status"] == "pending"
    assert allowed[1][0]["attempt_count"] == 0 and allowed[1][0]["claim_token"] is None
    # İkinci geçerli pending satır da tek aktif iş kuralını aşamamalıdır.
    with pytest.raises(DBAPIError) as duplicate:
        async with application_session(actor) as session:
            await session.execute(
                text("INSERT INTO public.ingestion_jobs(document_id) VALUES(:id)"),
                {"id": document},
            )
    assert duplicate.value.orig.sqlstate == "23505"
    assert await state(admin_engine, document) == allowed
    for query in (
        "UPDATE public.ingestion_jobs SET attempt_count=2 WHERE id=:id",
        "UPDATE public.ingestion_jobs SET status='processing',attempt_count=1,claim_token=:token,"
        "claim_document_revision=1,lease_expires_at=clock_timestamp()+interval '60 seconds' "
        "WHERE id=:id",
    ):
        await forbidden(actor, query, {"id": job, "token": uuid4()})
        assert await state(admin_engine, document) == allowed


async def test_app_enqueue_rechecks_course_role_before_any_mutation(
    pending_source, admin_engine, client, users
):
    _factory, document, headers, course = pending_source
    actors = await outsiders(client, users, headers, course)
    async with admin_engine.begin() as connection:
        await connection.execute(
            text("DELETE FROM public.ingestion_jobs WHERE document_id=:id"), {"id": document}
        )
    before = await state(admin_engine, document)
    assert before[1] == []
    for actor in actors:
        await forbidden(
            actor,
            "INSERT INTO public.ingestion_jobs(document_id) VALUES(:id)",
            {"id": document},
        )
        assert await state(admin_engine, document) == before
    async with application_session(owner_id(headers)) as session:
        assert (
            await session.scalar(
                text("INSERT INTO public.ingestion_jobs(document_id) VALUES(:id) RETURNING id"),
                {"id": document},
            )
            is not None
        )


async def test_retry_rechecks_cross_course_roles_null_inputs_and_failed_only(
    pending_source, admin_engine, client, users
):
    _factory, document, headers, course = pending_source
    owner = owner_id(headers)
    actors = await outsiders(client, users, headers, course)
    before = await state(admin_engine, document)
    # Kendi pending belgesi, NULL ve var olmayan belge de yazma yetkisi vermez.
    for target in (document, None, uuid4()):
        async with application_session(owner) as session:
            assert (
                await session.scalar(
                    text("SELECT app.retry_ingestion_job(CAST(:id AS uuid))"), {"id": target}
                )
                is None
            )
        assert await state(admin_engine, document) == before
    await fail_fixture(admin_engine, document)
    failed = await state(admin_engine, document)
    job = failed[1][0]["id"]
    for actor in actors:
        async with application_session(actor) as session:
            assert (
                await session.scalar(text("SELECT app.retry_ingestion_job(:id)"), {"id": document})
                is None
            )
        assert await state(admin_engine, document) == failed
    async with application_session(owner) as session:
        assert (
            await session.scalar(text("SELECT app.retry_ingestion_job(:id)"), {"id": document})
            == job
        )
    reset = await state(admin_engine, document)
    assert reset[0] == failed[0]  # Dar SQL fonksiyonu belgeyi API yerine değiştirmez.
    assert reset[1][0]["status"] == "pending" and reset[1][0]["attempt_count"] == 0
    for name in (
        "last_error",
        "started_at",
        "completed_at",
        "claim_token",
        "claim_document_revision",
        "lease_expires_at",
    ):
        assert reset[1][0][name] is None
    async with application_session(owner) as session:
        assert (
            await session.scalar(text("SELECT app.retry_ingestion_job(:id)"), {"id": document})
            is None
        )
    assert await state(admin_engine, document) == reset


async def test_retry_acl_search_path_worker_denial_and_forced_rls(pending_source, admin_engine):
    factory, document, headers, _course = pending_source
    async with admin_engine.connect() as connection:
        details = (
            (
                await connection.execute(
                    text(
                        "SELECT p.prosecdef,p.proconfig,pg_get_userbyid(p.proowner) AS owner,"
                        "has_function_privilege('dou_app',p.oid,'EXECUTE') AS app_execute,"
                        "has_function_privilege('dou_worker',p.oid,'EXECUTE') AS worker_execute,"
                        "EXISTS(SELECT 1 FROM aclexplode(COALESCE(p.proacl,"
                        "acldefault('f',p.proowner))) a WHERE a.grantee=0 AND "
                        "a.privilege_type='EXECUTE') AS public_execute "
                        "FROM pg_proc p WHERE p.oid='app.retry_ingestion_job(uuid)'::regprocedure"
                    )
                )
            )
            .mappings()
            .one()
        )
        assert details["prosecdef"] is True
        assert details["proconfig"] == ["search_path=pg_catalog, pg_temp"]
        assert details["owner"] not in {"dou_app", "dou_worker"}
        assert details["app_execute"] is True
        assert details["worker_execute"] is details["public_execute"] is False
        tables = (
            await connection.execute(
                text(
                    "SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class "
                    "WHERE oid IN ('public.documents'::regclass,'public.ingestion_jobs'::regclass)"
                )
            )
        ).all()
        assert len(tables) == 2 and all(row[1] is True and row[2] is True for row in tables)
    before = await state(admin_engine, document)
    with pytest.raises(DBAPIError) as caught:
        async with factory() as session, session.begin():
            identity = (
                await session.execute(
                    text(
                        "SELECT current_user,session_user,rolsuper,rolbypassrls "
                        "FROM pg_roles WHERE rolname=current_user"
                    )
                )
            ).one()
            assert tuple(identity) == ("dou_worker", "dou_worker", False, True)
            await session.execute(text("SELECT app.retry_ingestion_job(:id)"), {"id": document})
    assert caught.value.orig.sqlstate == "42501"
    assert await state(admin_engine, document) == before
    await forbidden(owner_id(headers), "SELECT app.track_ingestion_revision()", {})
    assert await state(admin_engine, document) == before


async def test_app_cannot_forge_revision_but_true_source_aba_advances_it(pending_source):
    _factory, _document, headers, course = pending_source
    actor = owner_id(headers)
    document = uuid4()
    async with application_session(actor) as session:
        initial = await session.scalar(
            text(
                "INSERT INTO public.documents(id,course_id,uploaded_by,file_name,file_type,"
                "storage_path,file_hash,byte_size,status,ingestion_revision) "
                "VALUES(:id,:course,:actor,'revision.md','.md',:path,:hash,1,'uploaded',99) "
                "RETURNING ingestion_revision"
            ),
            {
                "id": document,
                "course": course,
                "actor": actor,
                "path": f"synthetic/{document}.md",
                "hash": document.hex * 2,
            },
        )
        assert initial == 1
        for query, expected in (
            ("UPDATE public.documents SET ingestion_revision=99 WHERE id=:id ", 1),
            (
                "UPDATE public.documents SET file_name='changed.md',ingestion_revision=1 "
                "WHERE id=:id ",
                2,
            ),
            (
                "UPDATE public.documents SET file_name='revision.md',ingestion_revision=1 "
                "WHERE id=:id ",
                3,
            ),
            (
                "UPDATE public.documents SET status='completed',chunk_count=1,page_count=1,"
                "ingestion_revision=999 WHERE id=:id ",
                3,
            ),
        ):
            assert (
                await session.scalar(text(query + "RETURNING ingestion_revision"), {"id": document})
                == expected
            )
    async with application_session(actor) as session:
        assert (
            await session.scalar(
                text("SELECT ingestion_revision FROM public.documents WHERE id=:id"),
                {"id": document},
            )
            == 3
        )


async def test_retry_does_not_revive_superseded_failed_document(pending_source, admin_engine):
    _factory, document, headers, _course = pending_source
    await fail_fixture(admin_engine, document)
    async with admin_engine.begin() as connection:
        await connection.execute(
            text("UPDATE public.documents SET superseded_at=clock_timestamp() WHERE id=:id"),
            {"id": document},
        )
    before = await state(admin_engine, document)
    async with application_session(owner_id(headers)) as session:
        assert (
            await session.scalar(text("SELECT app.retry_ingestion_job(:id)"), {"id": document})
            is None
        )
    assert await state(admin_engine, document) == before
