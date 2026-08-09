"""Ölçme (assessment) tabloları: konu, soru, sınav oturumu, cevap, mastery.

Şemanın kaynağı `supabase/migrations/0004_assessment.sql` dosyasıdır; buradaki modeller
o şemayı yansıtır. Migration'lar düz SQL olarak tutulur, ORM'den üretilmez.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey as FK
from sqlalchemy import Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at, pg_enum, ts_now, ts_optional, uuid_fk, uuid_pk


class QuestionType(StrEnum):
    MCQ = "mcq"
    OPEN = "open"
    CODE_TRACE = "code_trace"
    BUG_HUNT = "bug_hunt"


class QuestionStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExamMode(StrEnum):
    PRACTICE = "practice"
    EXAM = "exam"


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    created_by: Mapped[uuid_fk] = mapped_column(FK("profiles.id"))
    created_at: Mapped[created_at]


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    topic_id: Mapped[uuid_fk] = mapped_column(FK("topics.id", ondelete="CASCADE"))
    type: Mapped[QuestionType] = mapped_column(pg_enum(QuestionType, "question_type"))
    # Dört tipin ortak zarfı (biçim R3 brief §2'de sabit): mcq/open/code_trace/bug_hunt.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    source_chunk_id: Mapped[uuid_fk] = mapped_column(FK("chunks.id", ondelete="RESTRICT"))
    status: Mapped[QuestionStatus] = mapped_column(
        pg_enum(QuestionStatus, "question_status"), default=QuestionStatus.DRAFT
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), FK("profiles.id", ondelete="SET NULL")
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), FK("profiles.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[ts_optional]
    created_at: Mapped[created_at]


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    user_id: Mapped[uuid_fk] = mapped_column(FK("profiles.id", ondelete="CASCADE"))
    mode: Mapped[ExamMode] = mapped_column(pg_enum(ExamMode, "exam_mode"))
    started_at: Mapped[ts_now]
    # practice modda NULL (süresiz). exam modda kalan süre buradan hesaplanır, istemci
    # saatine güvenilmez.
    expires_at: Mapped[ts_optional]
    finished_at: Mapped[ts_optional]
    score: Mapped[float | None] = mapped_column(Numeric)
    # Oturum açılırken seçilen sorular sabitlenir; sonradan onay/red bu listeyi değiştirmez.
    question_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PgUUID(as_uuid=True)))


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[uuid_pk]
    session_id: Mapped[uuid_fk] = mapped_column(FK("exam_sessions.id", ondelete="CASCADE"))
    question_id: Mapped[uuid_fk] = mapped_column(FK("questions.id", ondelete="RESTRICT"))
    # Denormalize: RLS filtresi exam_sessions'a JOIN etmeden tek satırda ifade edilir.
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    given: Mapped[str | None] = mapped_column(Text)
    is_correct: Mapped[bool | None]
    score: Mapped[int | None] = mapped_column(Integer)
    hint_level: Mapped[int] = mapped_column(Integer, default=0)
    # {"score": 0-100, "eksik_noktalar": [...], "dayanak_chunk_id": "..."}
    feedback: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    answered_at: Mapped[ts_now]


class Mastery(Base):
    __tablename__ = "mastery"

    user_id: Mapped[uuid_fk] = mapped_column(
        FK("profiles.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[uuid_fk] = mapped_column(FK("topics.id", ondelete="CASCADE"), primary_key=True)
    course_id: Mapped[uuid_fk] = mapped_column(FK("courses.id", ondelete="CASCADE"))
    score: Mapped[float]
    # "İlk cevap mı" sorusunu cevaplar (mastery/service.py'deki başlangıç davranışı, T036).
    answer_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[ts_now]
