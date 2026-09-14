"""Öğrenme olaylarını aynı RLS işleminde dar worker yetkisiyle kaydeder."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def record_learning_event(
    session: AsyncSession,
    *,
    course_id: UUID,
    event_type: str,
    topic_id: UUID | None = None,
    session_id: UUID | None = None,
    object_type: str | None = None,
    object_id: UUID | str | None = None,
    outcome_json: dict[str, Any] | None = None,
    evidence_chunk_ids: list[UUID] | None = None,
    latency_ms: int | None = None,
    model_id: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> UUID:
    """Kimlik yalnız sunucunun RLS bağlamından alınır; ham metin SQL'de reddedilir."""
    await session.flush()
    event_id = await session.scalar(
        text(
            "SELECT app.record_learning_event("
            "CAST(:course_id AS uuid), CAST(:event_type AS text), CAST(:topic_id AS uuid), "
            "CAST(:session_id AS uuid), CAST(:object_type AS text), CAST(:object_id AS text), "
            "CAST(:outcome_json AS jsonb), CAST(:evidence_chunk_ids AS uuid[]), "
            "CAST(:latency_ms AS integer), CAST(:model_id AS text), "
            "CAST(:metadata_json AS jsonb))"
        ),
        {
            "course_id": course_id,
            "event_type": event_type,
            "topic_id": topic_id,
            "session_id": session_id,
            "object_type": object_type,
            "object_id": str(object_id) if object_id is not None else None,
            "outcome_json": json.dumps(outcome_json) if outcome_json is not None else None,
            "evidence_chunk_ids": evidence_chunk_ids,
            "latency_ms": latency_ms,
            "model_id": model_id,
            "metadata_json": json.dumps(metadata_json) if metadata_json is not None else None,
        },
    )
    if not isinstance(event_id, UUID):
        raise RuntimeError("öğrenme olayı kaydedilemedi")
    return event_id


async def get_learning_summary(session: AsyncSession, course_id: UUID, days: int) -> dict[str, Any]:
    """Eğitmen için yalnız konu toplamları; SQL yetki ve pencereyi tekrar doğrular."""
    result = await session.execute(
        text("SELECT * FROM app.learning_summary(CAST(:course AS uuid), CAST(:days AS integer))"),
        {"course": course_id, "days": days},
    )
    topics: list[dict[str, Any]] = []
    total_events = 0
    for row in result.mappings():
        total_events += row["event_count"]
        topics.append(
            {
                "topic_id": row["topic_id"],
                "topic_name": row["topic_name"],
                "wrong_answers": row["wrong_answers"],
                "hints_requested": row["hints_requested"],
                "unsupported_refusals": row["unsupported_refusals"],
            }
        )
    return {"course_id": course_id, "days": days, "topics": topics, "total_events": total_events}
