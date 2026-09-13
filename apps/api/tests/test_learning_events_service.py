"""Öğrenme olayları: aynı işlem, kimlik ayrıştırma ve doğrudan SQL sınırları."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import dispose_engine, rls_session
from app.models.assessment import ExamMode, ExamSession
from app.models.learning_event import LearningEvent
from app.modules.assessment.learning_events import get_learning_summary, record_learning_event
from tests.factories import mcq_payload, seed_document, seed_question


@dataclass
class EventPool:
    instructor: UUID
    student: UUID
    peer: UUID
    outsider: UUID
    course: UUID
    other_course: UUID
    topic: UUID
    other_topic: UUID
    chunk: UUID
    other_chunk: UUID
    question: UUID
    exam: UUID
    peer_exam: UUID


@pytest.fixture
async def event_pool(admin_engine: AsyncEngine) -> AsyncIterator[EventPool]:
    instructor, student, peer, outsider = (uuid4() for _ in range(4))
    course, other_course, topic, other_topic = (uuid4() for _ in range(4))
    exam, peer_exam = uuid4(), uuid4()
    async with admin_engine.begin() as conn:
        for user in (instructor, student, peer, outsider):
            await conn.execute(
                text("INSERT INTO profiles(id,email) VALUES (:id,:email)"),
                {"id": user, "email": f"{user}@example.test"},
            )
        for current_course, code, current_topic in (
            (course, "EVENT-A", topic),
            (other_course, "EVENT-B", other_topic),
        ):
            await conn.execute(
                text(
                    "INSERT INTO courses(id,code,title,created_by) VALUES (:id,:code,:code,:owner)"
                ),
                {"id": current_course, "code": code, "owner": instructor},
            )
            for user, role in ((instructor, "instructor"), (student, "student"), (peer, "student")):
                await conn.execute(
                    text(
                        "INSERT INTO course_memberships(course_id,user_id,role) "
                        "VALUES (:course,:user,CAST(:role AS membership_role))"
                    ),
                    {"course": current_course, "user": user, "role": role},
                )
            await conn.execute(
                text(
                    "INSERT INTO topics(id,course_id,name,created_by) "
                    "VALUES (:id,:course,:name,:owner)"
                ),
                {"id": current_topic, "course": current_course, "name": code, "owner": instructor},
            )
    doc = await seed_document(
        admin_engine, course_id=course, uploaded_by=instructor, passages=["Kanıt."]
    )
    other_doc = await seed_document(
        admin_engine, course_id=other_course, uploaded_by=instructor, passages=["Başka ders."]
    )
    question = await seed_question(
        admin_engine,
        course_id=course,
        topic_id=topic,
        source_chunk_id=doc.chunk_ids[0],
        payload=mcq_payload(doc.chunk_ids * 4),
        status="approved",
        created_by=instructor,
        reviewed_by=instructor,
    )
    async with admin_engine.begin() as conn:
        for current_exam, user in ((exam, student), (peer_exam, peer)):
            await conn.execute(
                text(
                    "INSERT INTO exam_sessions(id,course_id,user_id,mode,question_ids) "
                    "VALUES (:id,:course,:user,'practice',CAST(:questions AS uuid[]))"
                ),
                {"id": current_exam, "course": course, "user": user, "questions": [question]},
            )
    yield EventPool(
        instructor,
        student,
        peer,
        outsider,
        course,
        other_course,
        topic,
        other_topic,
        doc.chunk_ids[0],
        other_doc.chunk_ids[0],
        question,
        exam,
        peer_exam,
    )
    await dispose_engine()


async def test_recorder_uses_course_pseudo_and_student_row_isolation(event_pool: EventPool) -> None:
    p = event_pool
    async with rls_session(p.student) as session:
        ids = [
            await record_learning_event(
                session, course_id=p.course, event_type="unsupported_refusal"
            )
            for _ in range(2)
        ]
        await record_learning_event(
            session, course_id=p.other_course, event_type="unsupported_refusal"
        )
        rows = (
            await session.execute(
                select(LearningEvent.id, LearningEvent.actor_pseudo_id, LearningEvent.course_id)
            )
        ).all()
        own = [row for row in rows if row.course_id == p.course]
        foreign_course = next(row for row in rows if row.course_id == p.other_course)
        assert {row.id for row in own} == set(ids)
        assert len({row.actor_pseudo_id for row in own}) == 1
        assert own[0].actor_pseudo_id != p.student
        assert own[0].actor_pseudo_id != foreign_course.actor_pseudo_id
    for identity in (p.peer, p.instructor, p.outsider):
        async with rls_session(identity) as session:
            assert (await session.scalars(select(LearningEvent.id))).all() == []


async def test_recorder_sees_uncommitted_exam_and_rolls_back_atomically(
    event_pool: EventPool, admin_engine: AsyncEngine
) -> None:
    p = event_pool
    new_exam = uuid4()
    with pytest.raises(RuntimeError, match="geri al"):
        async with rls_session(p.student) as session:
            session.add(
                ExamSession(
                    id=new_exam,
                    course_id=p.course,
                    user_id=p.student,
                    mode=ExamMode.PRACTICE,
                    question_ids=[p.question],
                )
            )
            event = await record_learning_event(
                session,
                course_id=p.course,
                event_type="question_presented",
                session_id=new_exam,
                topic_id=p.topic,
                object_type="question",
                object_id=p.question,
            )
            assert (
                await session.scalar(select(LearningEvent.id).where(LearningEvent.id == event))
                == event
            )
            raise RuntimeError("geri al")
    async with admin_engine.connect() as conn:
        assert (
            await conn.scalar(
                text("SELECT count(*) FROM learning_events WHERE session_id=:id"), {"id": new_exam}
            )
            == 0
        )
        assert (
            await conn.scalar(
                text("SELECT count(*) FROM exam_sessions WHERE id=:id"), {"id": new_exam}
            )
            == 0
        )


async def test_instructor_summary_counts_only_requested_window_and_course(
    event_pool: EventPool, admin_engine: AsyncEngine
) -> None:
    p = event_pool
    async with rls_session(p.student) as session:
        await record_learning_event(
            session,
            course_id=p.course,
            event_type="answer_submitted",
            topic_id=p.topic,
            session_id=p.exam,
            object_type="question",
            object_id=p.question,
            outcome_json={"is_correct": False, "score": 0},
        )
        hint = await record_learning_event(
            session,
            course_id=p.course,
            event_type="hint_requested",
            topic_id=p.topic,
            session_id=p.exam,
            outcome_json={"hint_level": 4},
        )
        await record_learning_event(
            session, course_id=p.course, event_type="unsupported_refusal", topic_id=p.topic
        )
        await record_learning_event(
            session, course_id=p.other_course, event_type="unsupported_refusal"
        )
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE learning_events SET occurred_at=now()-interval '10 days' WHERE id=:id"),
            {"id": hint},
        )
    async with rls_session(p.instructor) as session:
        week = await get_learning_summary(session, p.course, 7)
        month = await get_learning_summary(session, p.course, 30)
        assert week == {
            "course_id": p.course,
            "days": 7,
            "total_events": 2,
            "topics": [
                {
                    "topic_id": p.topic,
                    "topic_name": "EVENT-A",
                    "wrong_answers": 1,
                    "hints_requested": 0,
                    "unsupported_refusals": 1,
                }
            ],
        }
        assert month["total_events"] == 3
        assert month["topics"][0]["hints_requested"] == 1
        assert set(month["topics"][0]) == {
            "topic_id",
            "topic_name",
            "wrong_answers",
            "hints_requested",
            "unsupported_refusals",
        }


@pytest.mark.parametrize(
    "field", ["outcome_json", "evidence_chunk_ids", "object_id", "metadata_json"]
)
async def test_student_sql_cannot_read_answer_bearing_event_columns(
    event_pool: EventPool, field: str
) -> None:
    p = event_pool
    with pytest.raises(DBAPIError, match="permission denied"):
        async with rls_session(p.student) as session:
            await session.execute(select(getattr(LearningEvent, field)))


@pytest.mark.parametrize("identity", ["student", "peer", "outsider"])
async def test_aggregate_sql_rechecks_instructor(event_pool: EventPool, identity: str) -> None:
    with pytest.raises(DBAPIError, match="ders eğitmeni gerekli"):
        async with rls_session(getattr(event_pool, identity)) as session:
            await get_learning_summary(session, event_pool.course, 7)


@pytest.mark.parametrize("days", [None, 0, 8, 31])
async def test_aggregate_sql_rejects_invalid_window(
    event_pool: EventPool, days: int | None
) -> None:
    with pytest.raises(DBAPIError, match="7 veya 30"):
        async with rls_session(event_pool.instructor) as session:
            await session.execute(
                text("SELECT * FROM app.learning_summary(:course,:days)"),
                {"course": event_pool.course, "days": days},
            )


@pytest.mark.parametrize("bad_field", ["topic_id", "session_id", "evidence_chunk_ids", "object_id"])
async def test_recorder_rechecks_cross_scope_objects(event_pool: EventPool, bad_field: str) -> None:
    p = event_pool
    values: dict[str, Any] = {
        "topic_id": p.other_topic,
        "session_id": p.peer_exam,
        "evidence_chunk_ids": [p.other_chunk],
        "object_id": p.other_chunk,
    }
    kwargs: dict[str, Any] = {bad_field: values[bad_field]}
    if bad_field == "object_id":
        kwargs["object_type"] = "chunk"
    with pytest.raises(DBAPIError):
        async with rls_session(p.student) as session:
            await record_learning_event(
                session, course_id=p.course, event_type="unsupported_refusal", **kwargs
            )


@pytest.mark.parametrize(
    "payload",
    [
        {"outcome_json": {"answer": "Öğrencinin özel yanıtı"}},
        {"outcome_json": {"is_correct": "hayır"}},
        {"outcome_json": {"score": "özel metin"}},
        {"outcome_json": {"hint_level": 5}},
        {"metadata_json": {"email": "student@example.test"}},
        {"metadata_json": {"source": "Öğrencinin adı"}},
        {"model_id": "student@example.test"},
        {"latency_ms": -1},
    ],
)
async def test_recorder_rejects_raw_content_and_invalid_measurements(
    event_pool: EventPool, payload: dict[str, Any]
) -> None:
    with pytest.raises(DBAPIError, match="check constraint"):
        async with rls_session(event_pool.student) as session:
            await record_learning_event(
                session, course_id=event_pool.course, event_type="unsupported_refusal", **payload
            )


async def test_revoked_membership_denies_existing_rows_and_new_events(
    event_pool: EventPool, admin_engine: AsyncEngine
) -> None:
    p = event_pool
    async with rls_session(p.student) as session:
        await record_learning_event(session, course_id=p.course, event_type="unsupported_refusal")
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE course_memberships SET status='revoked' WHERE user_id=:user"),
            {"user": p.student},
        )
    async with rls_session(p.student) as session:
        assert (await session.scalars(select(LearningEvent.id))).all() == []
    with pytest.raises(DBAPIError, match="aktif ders üyeliği"):
        async with rls_session(p.student) as session:
            await record_learning_event(
                session, course_id=p.course, event_type="unsupported_refusal"
            )


async def test_chat_events_can_be_recorded_before_new_session_id_exists(
    event_pool: EventPool,
) -> None:
    p = event_pool
    async with rls_session(p.student) as session:
        ids = []
        for event_type in ("hint_requested", "unsupported_refusal", "provider_rate_limited"):
            ids.append(
                await record_learning_event(
                    session,
                    course_id=p.course,
                    event_type=event_type,
                    metadata_json={"source": "chat"},
                )
            )
        assert set(await session.scalars(select(LearningEvent.id))) == set(ids)
