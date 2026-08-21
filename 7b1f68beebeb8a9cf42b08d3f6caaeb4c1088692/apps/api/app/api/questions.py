"""Soru ve konu (topic) uçları.

Bu dosyada şu an yalnız `topics` ucu var (T030'un ilk parçası — T024 kritik yolunu açar:
soru üretimi ve mastery konu olmadan anlamsızdır). Soru üretimi/listeleme/onay uçları
(`/questions/...`) T029 (question_gen.py) hazır olduğunda buraya eklenir.

Yetkilendirme daima `CourseMemberDep` / `CourseInstructorDep` ile yapılır; kendi üyelik
sorgusu yazılmaz (deps.py zaten doğru yapıyor — Anayasa II).
"""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CourseInstructorDep, CourseMemberDep, SessionDep
from app.core.errors import ConflictError
from app.models.assessment import Topic
from app.schemas.assessment import TopicCreate, TopicOut

router = APIRouter(prefix="/courses/{course_id}", tags=["assessment"])


@router.post("/topics", response_model=TopicOut, status_code=status.HTTP_201_CREATED)
async def create_topic(
    payload: TopicCreate, context: CourseInstructorDep, session: SessionDep
) -> TopicOut:
    """Konu oluşturur. Yalnızca dersin eğitmeni oluşturabilir (FR-027)."""
    topic = Topic(
        course_id=context.course_id, name=payload.name.strip(), created_by=context.user_id
    )
    session.add(topic)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError(f"'{payload.name}' adlı bir konu bu derste zaten var.") from exc
    return TopicOut.model_validate(topic)


@router.get("/topics", response_model=list[TopicOut])
async def list_topics(context: CourseMemberDep, session: SessionDep) -> list[TopicOut]:
    """Konu listesi. Dersin tüm üyeleri (öğrenci + eğitmen) görebilir."""
    result = await session.execute(
        select(Topic).where(Topic.course_id == context.course_id).order_by(Topic.created_at)
    )
    return [TopicOut.model_validate(topic) for topic in result.scalars().all()]
