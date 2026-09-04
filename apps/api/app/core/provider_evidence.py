"""Request-scoped transport observations; no prompt, response text or credentials."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from app.core.provider_config import safe_model_id

provider_calls: ContextVar[list[dict[str, Any]] | None] = ContextVar("provider_calls", default=None)


@contextmanager
def observe_provider_call(provider: str, model: str) -> Iterator[None]:
    calls = provider_calls.get()
    row = {"provider": provider, "model": safe_model_id(model), "status": "failed"}
    if calls is not None:
        calls.append(row)
    yield
    row["status"] = "completed"
