"""Ders bazlı AI politikası ve salt-ekleme denetim izi."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, Numeric, SmallInteger, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.contracts import ChatMode
from app.models.base import Base, pg_enum, uuid_fk, uuid_pk


class CourseAiPolicy(Base):
    __tablename__ = "course_ai_policies"

    course_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True
    )
    allowed_modes: Mapped[list[ChatMode] | None] = mapped_column(
        ARRAY(pg_enum(ChatMode, "chat_mode"))
    )
    max_hints: Mapped[int | None] = mapped_column(SmallInteger)
    source_document_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PgUUID(as_uuid=True)))
    evidence_threshold: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    daily_token_budget: Mapped[int | None] = mapped_column(Integer)
    updated_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class CourseAiPolicyAudit(Base):
    __tablename__ = "course_ai_policy_audit"

    id: Mapped[uuid_pk]
    course_id: Mapped[uuid_fk] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    changed_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL")
    )
    changed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )
    before: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


__all__ = ["CourseAiPolicy", "CourseAiPolicyAudit"]
