"""FR-200..203 — dışa aktarma, geçmiş silme ve hesap anonimleştirme."""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import UserFactory
from tests.test_exams import ExamFixture, build_course


@dataclass(frozen=True)
class PersonalRows:
    chat_id: UUID
    message_id: UUID
    exam_id: UUID
    answer_id: UUID


async def seed_personal_rows(
    admin_engine: AsyncEngine,
    fixture: ExamFixture,
    *,
    user_id: UUID,
    label: str,
) -> PersonalRows:
    chat_id = uuid4()
    message_id = uuid4()
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
    return PersonalRows(chat_id, message_id, exam_id, answer_id)


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

    response = await client.get("/me/export", headers=fixture.instructor)

    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="dou-synapse-verilerim-'
    )
    body = response.json()
    encoded = json.dumps(body)
    assert body["schema_version"] == "1"
    assert body["profile"]["id"] == str(fixture.instructor_id)
    assert [item["role"] for item in body["memberships"]] == ["instructor"]
    assert [item["id"] for item in body["chat_sessions"]] == [str(teacher_rows.chat_id)]
    assert body["chat_sessions"][0]["messages"][0]["id"] == str(teacher_rows.message_id)
    assert [item["id"] for item in body["exam_sessions"]] == [str(teacher_rows.exam_id)]
    assert body["exam_sessions"][0]["answers"][0]["id"] == str(teacher_rows.answer_id)
    assert len(body["mastery"]) == 1
    assert str(fixture.student_id) not in encoded
    assert str(student_rows.chat_id) not in encoded
    assert str(student_rows.exam_id) not in encoded


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
