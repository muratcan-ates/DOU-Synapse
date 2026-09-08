"""DB-free checks for the pre-provider persistence boundary."""

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat_history import _load_or_create_session
from app.api.deps import CourseContext
from app.contracts import AssistantAudience, ChatMode
from app.models.core import MembershipRole
from app.schemas.chat import ChatRequest


@pytest.mark.parametrize("mode", [ChatMode.QA, ChatMode.SOCRATIC])
async def test_new_session_is_transient_and_never_flushes_before_provider(mode: ChatMode) -> None:
    db = Mock(spec=AsyncSession)
    db.flush = AsyncMock()
    context = CourseContext(uuid4(), uuid4(), MembershipRole.INSTRUCTOR)
    result = await _load_or_create_session(
        db, context, ChatRequest(question="  Sentetik soru  ", mode=mode)
    )
    assert inspect(result).transient
    assert result.id is not None
    assert result.user_id == context.user_id
    assert result.course_id == context.course_id
    assert result.mode is mode
    assert result.audience is AssistantAudience.INSTRUCTOR
    assert result.title == "Sentetik soru"
    db.add.assert_not_called()
    db.flush.assert_not_awaited()
    db.execute.assert_not_called()
