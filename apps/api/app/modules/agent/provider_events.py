"""Sağlayıcı 429 olayını ham hata/metin taşımadan kaydeder."""

import asyncio
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import control_rls_session
from app.core.logging import get_logger
from app.modules.assessment.learning_events import record_learning_event
from app.modules.generation.llm import (
    LiteLlmClient,
    LlmClient,
    LlmCompletion,
    LlmRequest,
    build_llm_client,
)

logger = get_logger("app.agent.learning_events")

_event_context: ContextVar[tuple[AsyncSession, UUID] | None] = ContextVar(
    "learning_provider_context",
    default=None,
)


@contextmanager
def learning_provider_context(session: AsyncSession | None, course_id: UUID) -> Iterator[None]:
    token = _event_context.set((session, course_id) if session is not None else None)
    try:
        yield
    finally:
        _event_context.reset(token)


async def record_provider_rate_limit() -> None:
    """Başarısız sohbet rollback olsa da gerçek sağlayıcı reddi ölçümde korunur."""
    context = _event_context.get()
    if context is None:
        return
    session, course_id = context
    user_id = await session.scalar(text("SELECT app.current_user_id()"))
    if not isinstance(user_id, UUID):
        return
    async with control_rls_session(user_id) as event_session:
        await record_learning_event(
            event_session,
            course_id=course_id,
            event_type="provider_rate_limited",
            metadata_json={"source": "chat"},
        )


class LearningEventLlmClient(LiteLlmClient):
    """Mevcut transport ve tekrar sınırını korur; yalnız gerçek 429'u gözler."""

    async def _attempt(
        self,
        model: str,
        request: LlmRequest,
        *,
        budget: float,
        attempt: int,
    ) -> LlmCompletion:
        started = time.monotonic()
        try:
            return await super()._attempt(model, request, budget=budget, attempt=attempt)
        except Exception as exc:
            if getattr(exc, "status_code", None) == 429:
                try:
                    remaining = max(0.0, budget - (time.monotonic() - started))
                    # Olay kaydı sağlayıcının mevcut süre bütçesini paylaşır;
                    # yavaş DB, 429 tekrarını sınırsız bekletemez.
                    async with asyncio.timeout(remaining):
                        await record_provider_rate_limit()
                except Exception:
                    # Ölçüm kesintisi özgün 429 sınıflandırmasını ve kontrollü
                    # tekrarı değiştirmez. Süreç iptali BaseException olarak geçer.
                    logger.warning("Öğrenme olayı kaydedilemedi; sağlayıcı hatası korunuyor.")
            raise


def build_learning_event_client() -> LlmClient:
    settings = get_settings()
    client = build_llm_client(settings)
    return LearningEventLlmClient(settings) if isinstance(client, LiteLlmClient) else client
