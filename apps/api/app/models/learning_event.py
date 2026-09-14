"""Kimlik ve ham metin taşımayan öğrenme olayı okuma modeli."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, ts_now, uuid_fk, uuid_pk


class LearningEvent(Base):
    __tablename__ = "learning_events"

    id: Mapped[uuid_pk]
    occurred_at: Mapped[ts_now]
    actor_pseudo_id: Mapped[uuid_fk]
    course_id: Mapped[uuid_fk] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    topic_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("topics.id", ondelete="SET NULL")
    )
    session_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(Text)
    object_type: Mapped[str | None] = mapped_column(Text)
    object_id: Mapped[str | None] = mapped_column(Text)
    outcome_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    evidence_chunk_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PgUUID(as_uuid=True)))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    model_id: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
