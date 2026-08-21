"""Khanmigo/CS50 benzeri geri bildirim döngüsünün yetki ve gizlilik testleri."""

from __future__ import annotations

from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import rls_session
from app.models.chat import ChatMessageFeedback
from tests.conftest import UserFactory


async def _create_course(client: AsyncClient, headers: dict[str, str], code: str) -> str:
    response = await client.post(
        "/courses", json={"code": code, "title": f"{code} Dersi"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _add_student(
    client: AsyncClient, headers: dict[str, str], course_id: str, email: str
) -> None:
    response = await client.post(
        f"/courses/{course_id}/members",
        json={"email": email, "role": "student"},
        headers=headers,
    )
    assert response.status_code == 201, response.text


async def _seed_turn(
    engine: AsyncEngine,
    *,
    course_id: UUID,
    student_id: UUID,
    question: str = "Deadlock için gerekli koşullar nelerdir?",
    answer: str = "Karşılıklı dışlama, tut ve bekle, kesilemezlik ve döngüsel bekleme.",
) -> tuple[UUID, UUID, UUID]:
    session_id, user_message_id, assistant_message_id = uuid4(), uuid4(), uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO chat_sessions (id, course_id, user_id, mode, state, title) "
                "VALUES (:id, :course, :student, 'qa', '{}'::jsonb, 'Deadlock')"
            ),
            {"id": session_id, "course": course_id, "student": student_id},
        )
        await conn.execute(
            text(
                "INSERT INTO chat_messages "
                "(id, session_id, course_id, role, content, citations, status, seq) VALUES "
                "(:user_id, :session, :course, 'user', :question, '[]'::jsonb, NULL, 0), "
                "(:assistant_id, :session, :course, 'assistant', :answer, '[]'::jsonb, "
                " 'answered', 1)"
            ),
            {
                "user_id": user_message_id,
                "assistant_id": assistant_message_id,
                "session": session_id,
                "course": course_id,
                "question": question,
                "answer": answer,
            },
        )
    return session_id, user_message_id, assistant_message_id


async def test_ogrenci_puani_gecmiste_kalir_ve_degistirilebilir(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    teacher_id = await users.create("hoca@dogus.edu.tr", "Yasemin Hoca")
    student_id = await users.create("ogrenci@dogus.edu.tr", "Burak Öğrenci")
    teacher, student = users.auth(teacher_id), users.auth(student_id)
    course_id = await _create_course(client, teacher, "COME401")
    await _add_student(client, teacher, course_id, "ogrenci@dogus.edu.tr")
    session_id, _, assistant_id = await _seed_turn(
        admin_engine, course_id=UUID(course_id), student_id=student_id
    )

    created = await client.put(
        f"/courses/{course_id}/chat/messages/{assistant_id}/feedback",
        json={
            "rating": "helpful",
            "reason": "helpful",
            "share_with_instructor": False,
        },
        headers=student,
    )
    assert created.status_code == 200, created.text
    assert created.json()["rating"] == "helpful"

    history = await client.get(f"/courses/{course_id}/chat/sessions/{session_id}", headers=student)
    assert history.status_code == 200, history.text
    assistant = next(item for item in history.json()["items"] if item["role"] == "assistant")
    assert assistant["feedback"]["rating"] == "helpful"

    changed = await client.put(
        f"/courses/{course_id}/chat/messages/{assistant_id}/feedback",
        json={
            "rating": "unhelpful",
            "reason": "inaccurate",
            "comment": "Dördüncü koşulun açıklaması eksik.",
            "share_with_instructor": False,
        },
        headers=student,
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["id"] == created.json()["id"]
    assert changed.json()["rating"] == "unhelpful"


async def test_ogretmen_yalniz_acikca_paylasilan_metni_gorur(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    teacher_id = await users.create("hoca@dogus.edu.tr", "Yasemin Hoca")
    student_id = await users.create("ogrenci@dogus.edu.tr", "Burak Öğrenci")
    teacher, student = users.auth(teacher_id), users.auth(student_id)
    course_id = await _create_course(client, teacher, "COME402")
    await _add_student(client, teacher, course_id, "ogrenci@dogus.edu.tr")
    _, _, private_answer_id = await _seed_turn(
        admin_engine,
        course_id=UUID(course_id),
        student_id=student_id,
        question="Semaphore nedir?",
        answer="Semaphore eşzamanlama için kullanılan bir sayaçtır.",
    )
    _, _, shared_answer_id = await _seed_turn(
        admin_engine,
        course_id=UUID(course_id),
        student_id=student_id,
        question="Starvation ile deadlock aynı mı?",
        answer="Evet, ikisi her zaman aynı durumdur.",
    )

    private = await client.put(
        f"/courses/{course_id}/chat/messages/{private_answer_id}/feedback",
        json={
            "rating": "helpful",
            "reason": "helpful",
            "share_with_instructor": False,
        },
        headers=student,
    )
    shared = await client.put(
        f"/courses/{course_id}/chat/messages/{shared_answer_id}/feedback",
        json={
            "rating": "unhelpful",
            "reason": "inaccurate",
            "comment": "Bu iki kavram aynı değil.",
            "share_with_instructor": True,
        },
        headers=student,
    )
    assert private.status_code == 200, private.text
    assert shared.status_code == 200, shared.text

    quality = await client.get(f"/courses/{course_id}/chat/quality", headers=teacher)
    assert quality.status_code == 200, quality.text
    body = quality.json()
    assert body["rated_count"] == 2
    assert body["helpful_count"] == 1
    assert body["unhelpful_count"] == 1
    assert body["shared_review_count"] == 1
    assert body["reason_counts"] == {"helpful": 1, "inaccurate": 1}
    assert len(body["recent_shared"]) == 1
    report = body["recent_shared"][0]
    assert report["student_name"] == "Burak Öğrenci"
    assert report["question_excerpt"] == "Starvation ile deadlock aynı mı?"
    assert report["answer_excerpt"] == "Evet, ikisi her zaman aynı durumdur."
    assert "Semaphore" not in str(body)

    # API dışındaki RLS katmanı da aynı kararı verir: eğitmen tablodan yalnız
    # paylaşılmış tek satırı seçebilir, toplu sayı için güvenli fonksiyona gider.
    async with rls_session(teacher_id) as db:
        visible = await db.scalar(select(func.count()).select_from(ChatMessageFeedback))
    assert visible == 1

    # Öğrenci izni geri çektiğinde tetikleyici kopyalanmış alıntıları temizler ve
    # kayıt eğitmen satır görünümünden düşer; toplam puan silinmez.
    withdrawn = await client.put(
        f"/courses/{course_id}/chat/messages/{shared_answer_id}/feedback",
        json={
            "rating": "unhelpful",
            "reason": "inaccurate",
            "comment": "Bu iki kavram aynı değil.",
            "share_with_instructor": False,
        },
        headers=student,
    )
    assert withdrawn.status_code == 200, withdrawn.text
    quality_after = await client.get(f"/courses/{course_id}/chat/quality", headers=teacher)
    assert quality_after.json()["rated_count"] == 2
    assert quality_after.json()["shared_review_count"] == 0
    assert quality_after.json()["recent_shared"] == []


async def test_yetki_ve_payload_kapilari_fail_closed(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> None:
    teacher_id = await users.create("hoca@dogus.edu.tr")
    student_id = await users.create("ogrenci@dogus.edu.tr")
    other_id = await users.create("diger@dogus.edu.tr")
    teacher, student, other = (
        users.auth(teacher_id),
        users.auth(student_id),
        users.auth(other_id),
    )
    course_id = await _create_course(client, teacher, "COME403")
    await _add_student(client, teacher, course_id, "ogrenci@dogus.edu.tr")
    await _add_student(client, teacher, course_id, "diger@dogus.edu.tr")
    _, user_message_id, assistant_id = await _seed_turn(
        admin_engine, course_id=UUID(course_id), student_id=student_id
    )

    other_student = await client.put(
        f"/courses/{course_id}/chat/messages/{assistant_id}/feedback",
        json={"rating": "helpful", "reason": "helpful"},
        headers=other,
    )
    user_message = await client.put(
        f"/courses/{course_id}/chat/messages/{user_message_id}/feedback",
        json={"rating": "helpful", "reason": "helpful"},
        headers=student,
    )
    invalid_pair = await client.put(
        f"/courses/{course_id}/chat/messages/{assistant_id}/feedback",
        json={
            "rating": "helpful",
            "reason": "helpful",
            "share_with_instructor": True,
        },
        headers=student,
    )
    teacher_feedback = await client.put(
        f"/courses/{course_id}/chat/messages/{assistant_id}/feedback",
        json={"rating": "helpful", "reason": "helpful"},
        headers=teacher,
    )
    student_quality = await client.get(f"/courses/{course_id}/chat/quality", headers=student)

    assert other_student.status_code == 404
    assert user_message.status_code == 404
    assert invalid_pair.status_code == 422
    assert teacher_feedback.status_code == 403
    assert student_quality.status_code == 403
