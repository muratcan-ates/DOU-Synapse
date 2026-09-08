"""Ayrı Uvicorn süreci; ürün kota/auth/RLS işlevleri değiştirilmez."""

from __future__ import annotations

import asyncio
import contextvars
import json
import os
import re
import socket
from pathlib import Path

from common import (
    APP_IDENTITY_SQL,
    expected_target,
    private_passfile,
    validate_app_identity,
    verify_sources,
)

REQUEST_ID = contextvars.ContextVar("d1_request_id", default="startup")
OUTPUT = Path(os.environ["D1_HTTP_OUTPUT"])
INDEX = int(os.environ["D1_HTTP_INDEX"])
EVENTS = OUTPUT / f"process-{INDEX}-events.jsonl"


def event(kind, **fields):
    payload = {
        "kind": kind,
        "pid": os.getpid(),
        "index": INDEX,
        "request_id": REQUEST_ID.get(),
        **fields,
    }
    with EVENTS.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, sort_keys=True) + "\n")


async def verify_actual_pools():
    from sqlalchemy import text

    from app.core.db import get_control_session_factory, get_session_factory

    expected = expected_target(dict(os.environ), os.environ["D1_TEST_DB_NAME"])
    for kind, factory in [
        ("main", get_session_factory()),
        ("control", get_control_session_factory()),
    ]:
        async with factory() as session, session.begin():
            await session.execute(text("SET TRANSACTION READ ONLY"))
            row = dict((await session.execute(text(APP_IDENTITY_SQL))).mappings().one())
            validate_app_identity(row, expected)
            event("pool_verified", pool=kind, **row)


def install_providers():
    from sqlalchemy import text

    from app.contracts import RetrievedChunk
    from app.modules.agent.pipeline import set_pipeline
    from app.modules.assessment import question_gen
    from app.modules.generation.fake import FakeLlmClient
    from app.modules.generation.llm import LlmUnavailableError
    from app.modules.generation.service import GenerationService

    class SyntheticRetriever:
        def __init__(self, session):
            self.session = session

        async def search(self, *, course_id, query, limit=8):
            event("retrieval")
            if "D1_NO_SOURCE" in query:
                return []
            # Sentetik fixture projeksiyonu, gerçek istek dou_app/RLS oturumunu kullanır.
            rows = (
                await self.session.execute(
                    text("""SELECT c.id AS chunk_id, c.document_id,
                d.file_name, c.page_number, c.slide_number, c.section_title, c.text
                FROM public.chunks c JOIN public.documents d ON d.id=c.document_id
                WHERE c.course_id=:course_id AND d.status='completed'
                ORDER BY c.chunk_index LIMIT :limit"""),
                    {"course_id": course_id, "limit": limit},
                )
            ).mappings()
            return [
                RetrievedChunk(**row, dense_score=1.0, fts_score=1.0, fused_score=1.0)
                for row in rows
            ]

    class ControlledFake(FakeLlmClient):
        async def complete(self, request):
            failure = "D1_PROVIDER_FAILURE" in request.user
            event("provider", task=str(request.task), injected_failure=failure)
            if failure:
                raise LlmUnavailableError()
            return await super().complete(request)

    class QuestionCompletion:
        async def complete(self, *, system, user):
            from app.modules.generation.llm import LlmRequest, LlmTask

            completion = await fake.complete(
                LlmRequest(system=system, user=user, json_output=True, task=LlmTask.QUESTION_GEN)
            )
            return completion.text

    fake = ControlledFake()
    set_pipeline(retriever_factory=SyntheticRetriever, generator=GenerationService(llm=fake))
    question_gen.set_providers(
        retriever_factory=SyntheticRetriever, completion=QuestionCompletion()
    )


class ObservedApplication:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id", b"no-id").decode("ascii", errors="replace")
        if not re.fullmatch(r"d1-[a-z-]+-[0-9a-f]{32}", request_id):
            request_id = "untracked"
        token = REQUEST_ID.set(request_id)
        event("http_started")

        async def observed_send(message):
            if message["type"] == "http.response.start":
                message = dict(message)
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-d1-process", str(os.getpid()).encode()),
                ]
                event("http_result", status=message["status"])
            await send(message)

        try:
            await self.app(scope, receive, observed_send)
        finally:
            REQUEST_ID.reset(token)


def main():
    verify_sources(dict(os.environ))
    private_passfile(os.environ["PGPASSFILE"])
    # Çocuk ortamının tek PG girdisi bilerek hazırlanmış özel boş passfile'dır.
    assert {key for key in os.environ if key.startswith("PG")} == {"PGPASSFILE"}
    import uvicorn

    from app.core.config import get_settings
    from app.main import app

    settings = get_settings()
    assert settings.dev_auth_enabled and settings.llm_fake_provider and not settings.is_production
    install_providers()

    # Havuzlar ve sunucu aynı event loop üzerinde kalır.
    async def run():
        await verify_actual_pools()
        event("ready", sources=verify_sources(dict(os.environ)))
        listener = socket.socket(fileno=int(os.environ["D1_HTTP_SOCKET_FD"]))
        require_endpoint = listener.getsockname()
        assert require_endpoint[0] == "127.0.0.1"
        config = uvicorn.Config(
            ObservedApplication(app),
            access_log=False,
            log_level="warning",
            lifespan="on",
            timeout_graceful_shutdown=5,
        )
        await uvicorn.Server(config).serve(sockets=[listener])

    asyncio.run(run())


if __name__ == "__main__":
    main()
