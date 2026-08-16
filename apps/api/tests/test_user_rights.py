"""FR-200..203 — dışa aktarma, geçmiş silme ve hesap anonimleştirme."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.modules.assessment import exam_state
from tests.conftest import UserFactory
from tests.factories import ExamFixture, build_course, start


@dataclass(frozen=True)
class PersonalRows:
    chat_id: UUID
    message_id: UUID
    assistant_message_id: UUID
    exam_id: UUID
    answer_id: UUID


@dataclass(frozen=True)
class AgentOperationalRows:
    reservation_id: UUID
    guard_event_id: UUID


async def seed_agent_operational_rows(
    admin_engine: AsyncEngine,
    fixture: ExamFixture,
) -> AgentOperationalRows:
    reservation_id = uuid4()
    guard_event_id = uuid4()
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO ai_token_reservations "
                "(id,course_id,user_id,audience,reserved_tokens,charged_tokens,expires_at) "
                "VALUES (:id,:course_id,:user_id,'student',100,100,now()+interval '1 minute')"
            ),
            {
                "id": reservation_id,
                "course_id": UUID(fixture.course_id),
                "user_id": fixture.student_id,
            },
        )
        await conn.execute(
            text(
                "INSERT INTO ai_guard_events "
                "(id,course_id,user_id,audience,event_type) "
                "VALUES (:id,:course_id,:user_id,'student','scope_refused')"
            ),
            {
                "id": guard_event_id,
                "course_id": UUID(fixture.course_id),
                "user_id": fixture.student_id,
            },
        )
    return AgentOperationalRows(reservation_id, guard_event_id)


async def seed_personal_rows(
    admin_engine: AsyncEngine,
    fixture: ExamFixture,
    *,
    user_id: UUID,
    label: str,
) -> PersonalRows:
    chat_id = uuid4()
    message_id = uuid4()
    assistant_message_id = uuid4()
    exam_id = uuid4()
    answer_id = uuid4()
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO chat_sessions (id, course_id, user_id, mode, title) "
                "VALUES (:id, :course_id, :user_id, 'qa', :title)"
            ),
            {
                "id": chat_id,
                "course_id": UUID(fixture.course_id),
                "user_id": user_id,
                "title": f"{label} sohbeti",
            },
        )
        await conn.execute(
            text(
                "INSERT INTO chat_messages "
                "(id, session_id, course_id, role, content, citations, status, seq) "
                "VALUES (:id, :session_id, :course_id, 'assistant', :content, "
                "CAST(:citations AS jsonb), 'answered', 1)"
            ),
            {
                "id": assistant_message_id,
                "session_id": chat_id,
                "course_id": UUID(fixture.course_id),
                "content": f"{label} kişisel cevap",
                "citations": json.dumps([]),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO chat_messages "
                "(id, session_id, course_id, role, content, citations, seq) "
                "VALUES (:id, :session_id, :course_id, 'user', :content, "
                "CAST(:citations AS jsonb), 0)"
            ),
            {
                "id": message_id,
                "session_id": chat_id,
                "course_id": UUID(fixture.course_id),
                "content": f"{label} kişisel soru",
                "citations": json.dumps([]),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO exam_sessions "
                "(id, course_id, user_id, mode, finished_at, score, question_ids) "
                "VALUES (:id, :course_id, :user_id, 'practice', now(), 85, :question_ids)"
            ),
            {
                "id": exam_id,
                "course_id": UUID(fixture.course_id),
                "user_id": user_id,
                "question_ids": fixture.question_ids,
            },
        )
        await conn.execute(
            text(
                "INSERT INTO answers "
                "(id, session_id, question_id, course_id, given, is_correct, score, feedback) "
                "VALUES (:id, :session_id, :question_id, :course_id, :given, true, 85, "
                "CAST(:feedback AS jsonb))"
            ),
            {
                "id": answer_id,
                "session_id": exam_id,
                "question_id": fixture.question_ids[0],
                "course_id": UUID(fixture.course_id),
                "given": f"{label} cevabı",
                "feedback": json.dumps({"score": 85, "eksik_noktalar": []}),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO mastery (user_id, topic_id, course_id, score, answer_count) "
                "VALUES (:user_id, :topic_id, :course_id, 0.85, 1)"
            ),
            {
                "user_id": user_id,
                "topic_id": fixture.topic_id,
                "course_id": UUID(fixture.course_id),
            },
        )
    return PersonalRows(chat_id, message_id, assistant_message_id, exam_id, answer_id)


async def test_export_uygulama_filtresi_egitmenin_ogrenci_verisini_sizdirmaz(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build_course(client, users, admin_engine)
    teacher_rows = await seed_personal_rows(
        admin_engine, fixture, user_id=fixture.instructor_id, label="Ayşe"
    )
    student_rows = await seed_personal_rows(
        admin_engine, fixture, user_id=fixture.student_id, label="Burak"
    )
    student_feedback = await client.put(
        f"/courses/{fixture.course_id}/chat/messages/{student_rows.assistant_message_id}/feedback",
        json={
            "rating": "unhelpful",
            "reason": "citation_problem",
            "comment": "Kaynak eşleşmedi.",
            "share_with_instructor": False,
        },
        headers=fixture.student,
    )
    assert student_feedback.status_code == 200, student_feedback.text

    response = await client.get("/me/export", headers=fixture.student)

    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="dou-synapse-verilerim-'
    )
    body = response.json()
    encoded = json.dumps(body)
    assert body["schema_version"] == "2"
    assert body["profile"]["id"] == str(fixture.student_id)
    assert [item["role"] for item in body["memberships"]] == ["student"]
    assert [item["id"] for item in body["chat_sessions"]] == [str(student_rows.chat_id)]
    assert body["chat_sessions"][0]["messages"][0]["id"] == str(student_rows.message_id)
    assert body["chat_sessions"][0]["messages"][1]["feedback"]["reason"] == "citation_problem"
    assert body["chat_sessions"][0]["messages"][1]["feedback"]["comment"] == "Kaynak eşleşmedi."
    assert [item["id"] for item in body["exam_sessions"]] == [str(student_rows.exam_id)]
    assert body["exam_sessions"][0]["answers"][0]["id"] == str(student_rows.answer_id)
    assert len(body["mastery"]) == 1
    assert str(fixture.instructor_id) not in encoded
    assert str(teacher_rows.chat_id) not in encoded
    assert str(teacher_rows.exam_id) not in encoded


async def test_export_agent_operasyon_kayitlarini_aciklayarak_disarida_birakir(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build_course(client, users, admin_engine)
    rows = await seed_agent_operational_rows(admin_engine, fixture)

    response = await client.get("/me/export", headers=fixture.student)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == "2"
    assert body["not_included"] == [
        "ai_token_reservations: Soru, cevap veya kaynak metni içermeyen token bütçesi, "
        "maliyet ve eşzamanlılık operasyon kaydıdır; bu dışa aktarıma dahil edilmez.",
        "ai_guard_events: Soru, cevap veya kaynak metni içermeyen hız, kota, "
        "eşzamanlılık ve kapsam reddi güvenlik kaydıdır; bu dışa aktarıma dahil edilmez.",
    ]
    encoded = json.dumps(body)
    assert str(rows.reservation_id) not in encoded
    assert str(rows.guard_event_id) not in encoded


async def test_export_uyelik_sonlandiktan_sonra_sohbet_ve_geri_bildirimi_korur(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build_course(client, users, admin_engine)
    rows = await seed_personal_rows(
        admin_engine, fixture, user_id=fixture.student_id, label="Burak"
    )
    feedback = await client.put(
        f"/courses/{fixture.course_id}/chat/messages/{rows.assistant_message_id}/feedback",
        json={
            "rating": "unhelpful",
            "reason": "citation_problem",
            "comment": "Üyelik sonrasında da bana ait kalmalı.",
            "share_with_instructor": False,
        },
        headers=fixture.student,
    )
    assert feedback.status_code == 200, feedback.text

    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE course_memberships SET status = 'revoked' "
                "WHERE course_id = :course_id AND user_id = :user_id"
            ),
            {"course_id": UUID(fixture.course_id), "user_id": fixture.student_id},
        )

    course_history = await client.get(
        f"/courses/{fixture.course_id}/chat/sessions",
        headers=fixture.student,
    )
    response = await client.get("/me/export", headers=fixture.student)

    # KVKK için açılan self-read politikaları normal ders erişimini geri açmaz.
    assert course_history.status_code == 404, course_history.text
    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["id"] for item in body["chat_sessions"]] == [str(rows.chat_id)]
    messages = body["chat_sessions"][0]["messages"]
    assert [item["id"] for item in messages] == [
        str(rows.message_id),
        str(rows.assistant_message_id),
    ]
    assert messages[1]["feedback"]["reason"] == "citation_problem"
    assert messages[1]["feedback"]["comment"] == "Üyelik sonrasında da bana ait kalmalı."


@pytest.mark.parametrize("delete_target", ["course", "profile"])
async def test_agent_operasyon_kayitlari_course_ve_profile_delete_ile_cascade_silinir(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    delete_target: str,
) -> None:
    fixture = await build_course(client, users, admin_engine)
    rows = await seed_agent_operational_rows(admin_engine, fixture)

    async with admin_engine.begin() as conn:
        if delete_target == "course":
            await conn.execute(
                text("DELETE FROM courses WHERE id = :id"),
                {"id": UUID(fixture.course_id)},
            )
        else:
            await conn.execute(
                text("DELETE FROM profiles WHERE id = :id"),
                {"id": fixture.student_id},
            )

    async with admin_engine.connect() as conn:
        counts = (
            await conn.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM ai_token_reservations WHERE id = :reservation_id), "
                    "(SELECT count(*) FROM ai_guard_events WHERE id = :guard_event_id), "
                    "(SELECT count(*) FROM courses WHERE id = :course_id), "
                    "(SELECT count(*) FROM profiles WHERE id = :student_id)"
                ),
                {
                    "reservation_id": rows.reservation_id,
                    "guard_event_id": rows.guard_event_id,
                    "course_id": UUID(fixture.course_id),
                    "student_id": fixture.student_id,
                },
            )
        ).one()

    assert tuple(counts[:2]) == (0, 0)
    assert counts[2] == (0 if delete_target == "course" else 1)
    assert counts[3] == (1 if delete_target == "course" else 0)


async def _seed_export_exam(
    admin_engine: AsyncEngine,
    fixture: ExamFixture,
    *,
    mode: str,
    expires_minutes: int | None,
    user_id: UUID | None = None,
) -> None:
    exam_user_id = user_id or fixture.student_id
    if expires_minutes is None:
        statement = text(
            "INSERT INTO exam_sessions "
            "(course_id,user_id,mode,started_at,expires_at,question_ids) VALUES "
            "(:course_id,:user_id,CAST(:mode AS exam_mode),"
            "now()-interval '2 minutes',NULL,:question_ids)"
        )
        parameters = {
            "course_id": UUID(fixture.course_id),
            "user_id": exam_user_id,
            "mode": mode,
            "question_ids": fixture.question_ids,
        }
    else:
        statement = text(
            "INSERT INTO exam_sessions "
            "(course_id,user_id,mode,started_at,expires_at,question_ids) VALUES "
            "(:course_id,:user_id,CAST(:mode AS exam_mode),"
            "now()-interval '2 minutes',"
            "now()+(:expires_minutes * interval '1 minute'),:question_ids)"
        )
        parameters = {
            "course_id": UUID(fixture.course_id),
            "user_id": exam_user_id,
            "mode": mode,
            "expires_minutes": expires_minutes,
            "question_ids": fixture.question_ids,
        }
    async with admin_engine.begin() as connection:
        await connection.execute(statement, parameters)


@pytest.mark.parametrize(
    ("mode", "expires_minutes", "expected_status"),
    [
        ("exam", 10, 423),
        ("exam", -1, 200),
        ("practice", None, 200),
    ],
)
async def test_export_active_exam_haricinde_kvkk_hakkini_geciktirmez(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    mode: str,
    expires_minutes: int | None,
    expected_status: int,
) -> None:
    fixture = await build_course(client, users, admin_engine)
    await _seed_export_exam(
        admin_engine,
        fixture,
        mode=mode,
        expires_minutes=expires_minutes,
    )

    response = await client.get("/me/export", headers=fixture.student)

    assert response.status_code == expected_status, response.text
    if expected_status == 423:
        assert response.json()["error"]["code"] == "exam_export_locked"


@pytest.mark.parametrize("membership_change", ["revoke", "delete"])
async def test_export_active_exam_uyelik_sonlandiginda_da_kilitli_kalir(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    membership_change: str,
) -> None:
    fixture = await build_course(client, users, admin_engine)
    await seed_personal_rows(admin_engine, fixture, user_id=fixture.student_id, label="Burak")
    await _seed_export_exam(
        admin_engine,
        fixture,
        mode="exam",
        expires_minutes=10,
    )
    async with admin_engine.begin() as connection:
        statement = (
            text(
                "DELETE FROM course_memberships WHERE course_id = :course_id AND user_id = :user_id"
            )
            if membership_change == "delete"
            else text(
                "UPDATE course_memberships SET status = 'revoked' "
                "WHERE course_id = :course_id AND user_id = :user_id"
            )
        )
        await connection.execute(
            statement,
            {
                "course_id": UUID(fixture.course_id),
                "user_id": fixture.student_id,
            },
        )

    response = await client.get("/me/export", headers=fixture.student)

    assert response.status_code == 423, response.text
    assert response.json()["error"]["code"] == "exam_export_locked"


async def test_export_ve_sinav_baslatma_ayni_kullanici_kilidinde_siralanir(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Export commits first or sees the exam; it cannot cross an exam start."""

    fixture = await build_course(client, users, admin_engine)
    export_holds_lock = asyncio.Event()
    release_export = asyncio.Event()
    original = exam_state.any_active_student_exam_session

    async def paused_check(*args: Any, **kwargs: Any) -> Any:
        export_holds_lock.set()
        await release_export.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(exam_state, "any_active_student_exam_session", paused_check)
    export_task = asyncio.create_task(client.get("/me/export", headers=fixture.student))
    await asyncio.wait_for(export_holds_lock.wait(), timeout=2)
    exam_task = asyncio.create_task(start(client, fixture, "exam"))

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(asyncio.shield(exam_task), timeout=0.05)

    release_export.set()
    export = await export_task
    exam = await exam_task

    assert export.status_code == 200, export.text
    assert exam["mode"] == "exam"


async def test_egitmen_sinav_onizlemesinde_kendi_verisini_indirebilir(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build_course(client, users, admin_engine)
    await _seed_export_exam(
        admin_engine,
        fixture,
        mode="exam",
        expires_minutes=10,
        user_id=fixture.instructor_id,
    )

    response = await client.get("/me/export", headers=fixture.instructor)

    assert response.status_code == 200, response.text


async def test_ders_sohbet_gecmisi_yalniz_sahibin_satirlarini_siler(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build_course(client, users, admin_engine)
    teacher_rows = await seed_personal_rows(
        admin_engine, fixture, user_id=fixture.instructor_id, label="Ayşe"
    )
    student_rows = await seed_personal_rows(
        admin_engine, fixture, user_id=fixture.student_id, label="Burak"
    )

    response = await client.delete(
        f"/courses/{fixture.course_id}/chat/sessions",
        headers=fixture.student,
    )
    other_delete = await client.delete(
        f"/courses/{fixture.course_id}/chat/sessions/{teacher_rows.chat_id}",
        headers=fixture.student,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {"deleted_sessions": 1}
    assert other_delete.status_code == 404
    async with admin_engine.connect() as conn:
        sessions = (
            (
                await conn.execute(
                    text("SELECT id FROM chat_sessions WHERE id = ANY(:ids) ORDER BY id"),
                    {"ids": [student_rows.chat_id, teacher_rows.chat_id]},
                )
            )
            .scalars()
            .all()
        )
        student_messages = await conn.scalar(
            text("SELECT count(*) FROM chat_messages WHERE id = :id"),
            {"id": student_rows.message_id},
        )
    assert sessions == [teacher_rows.chat_id]
    assert student_messages == 0


async def test_global_gecmis_silme_uyelik_sonlandiktan_sonra_da_calisir(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build_course(client, users, admin_engine)
    rows = await seed_personal_rows(
        admin_engine, fixture, user_id=fixture.student_id, label="Burak"
    )
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE course_memberships SET status = 'revoked' "
                "WHERE course_id = :course_id AND user_id = :user_id"
            ),
            {"course_id": UUID(fixture.course_id), "user_id": fixture.student_id},
        )

    response = await client.delete("/me/chat-history", headers=fixture.student)

    assert response.status_code == 200, response.text
    assert response.json() == {"deleted_sessions": 1}
    async with admin_engine.connect() as conn:
        remaining = await conn.scalar(
            text("SELECT count(*) FROM chat_sessions WHERE id = :id"), {"id": rows.chat_id}
        )
    assert remaining == 0


async def test_ogrenci_hesabi_kisisel_profili_anonimlestirir_akademik_kaydi_korur(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build_course(client, users, admin_engine)
    rows = await seed_personal_rows(
        admin_engine, fixture, user_id=fixture.student_id, label="Burak"
    )

    response = await client.delete("/me", headers=fixture.student)
    repeated = await client.delete("/me", headers=fixture.student)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["anonymized"] is True
    assert body["deleted_chat_sessions"] == 1
    assert body["revoked_memberships"] == 1
    assert body["retained_owned_courses"] == 0
    assert body["identity_provider_action_required"] is True
    assert repeated.status_code == 409
    async with admin_engine.connect() as conn:
        profile = (
            await conn.execute(
                text("SELECT email, full_name FROM profiles WHERE id = :id"),
                {"id": fixture.student_id},
            )
        ).one()
        membership_status = await conn.scalar(
            text(
                "SELECT status::text FROM course_memberships "
                "WHERE course_id = :course_id AND user_id = :user_id"
            ),
            {"course_id": UUID(fixture.course_id), "user_id": fixture.student_id},
        )
        chat_count = await conn.scalar(
            text("SELECT count(*) FROM chat_sessions WHERE id = :id"), {"id": rows.chat_id}
        )
        exam_count = await conn.scalar(
            text("SELECT count(*) FROM exam_sessions WHERE id = :id"), {"id": rows.exam_id}
        )
    assert profile.email == f"silinmis+{fixture.student_id}@dou-synapse.invalid"
    assert profile.full_name is None
    assert membership_status == "revoked"
    assert chat_count == 0
    assert exam_count == 1


async def test_egitmen_hesabi_dersi_dusurmeden_anonimlestirilir(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
) -> None:
    fixture = await build_course(client, users, admin_engine)

    response = await client.delete("/me", headers=fixture.instructor)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["retained_owned_courses"] == 1
    assert body["revoked_memberships"] == 1
    async with admin_engine.connect() as conn:
        course_creator = await conn.scalar(
            text("SELECT created_by FROM courses WHERE id = :id"),
            {"id": UUID(fixture.course_id)},
        )
        student_status = await conn.scalar(
            text(
                "SELECT status::text FROM course_memberships "
                "WHERE course_id = :course_id AND user_id = :user_id"
            ),
            {"course_id": UUID(fixture.course_id), "user_id": fixture.student_id},
        )
        teacher_status = await conn.scalar(
            text(
                "SELECT status::text FROM course_memberships "
                "WHERE course_id = :course_id AND user_id = :user_id"
            ),
            {"course_id": UUID(fixture.course_id), "user_id": fixture.instructor_id},
        )
    assert course_creator == fixture.instructor_id
    assert student_status == "active"
    assert teacher_status == "revoked"
