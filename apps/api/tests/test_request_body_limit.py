"""Ham gövde sınırı ayrıştırıcıdan önce çalışır ve geçici dosya bırakmaz."""

from __future__ import annotations

import json
from collections import deque
from tempfile import SpooledTemporaryFile
from typing import Any

import pytest
from fastapi import FastAPI, File, UploadFile
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Message, Scope

from app.core import request_body_limit as boundary


def _scope(headers: list[tuple[bytes, bytes]] | None = None) -> Scope:
    return {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/upload",
        "raw_path": b"/upload",
        "query_string": b"",
        "headers": headers or [],
        "scheme": "http",
        "server": ("test", 80),
        "client": ("test", 123),
        "state": {"request_id": "synthetic-request"},
    }


async def _run(
    app: Any,
    chunks: list[Message],
    headers: list[tuple[bytes, bytes]] | None = None,
    *,
    method: str = "POST",
) -> tuple[list[Message], deque[Message]]:
    pending = deque(chunks)
    sent: list[Message] = []

    async def receive() -> Message:
        return pending.popleft() if pending else {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    scope = _scope(headers)
    scope["method"] = method
    await app(scope, receive, send)
    return sent, pending


async def _echo(scope: Scope, receive: Any, send: Any) -> None:
    body = await Request(scope, receive).body()
    await Response(body)(scope, receive, send)


def _part(body: bytes, *, more: bool = False) -> Message:
    return {"type": "http.request", "body": body, "more_body": more}


def _payload(sent: list[Message]) -> dict[str, Any]:
    return json.loads(
        b"".join(item.get("body", b"") for item in sent if item["type"] == "http.response.body")
    )


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"0")], [(b"content-length", b"1")]])
async def test_streamed_actual_bytes_exceed_limit_before_app(
    headers: list[tuple[bytes, bytes]],
) -> None:
    called = False

    async def forbidden(*args: Any) -> None:
        nonlocal called
        called = True

    sent, pending = await _run(
        boundary.RequestBodyLimitMiddleware(forbidden, max_bytes=10),
        [_part(b"123456", more=True), _part(b"123456", more=True), _part(b"unread")],
        headers,
    )
    assert not called, "boyut sınırı aşılırken uygulama çağrılmamalı"
    assert sent[0]["status"] == 413
    assert _payload(sent)["error"] == {
        "code": "payload_too_large",
        "message": "İstek gövdesi izin verilen boyutu aşıyor.",
        "request_id": "synthetic-request",
    }
    assert not called
    assert len(pending) == 1


@pytest.mark.parametrize(
    "headers, expected",
    [
        ([(b"content-length", b"11")], 413),
        ([(b"content-length", b"9" * 50)], 413),
        ([(b"content-length", b"-1")], 400),
        ([(b"content-length", b"abc")], 400),
        ([(b"content-length", b"")], 400),
        ([(b"content-length", b"1"), (b"content-length", b"2")], 400),
    ],
)
async def test_invalid_or_large_header_rejected_without_read(
    headers: list[tuple[bytes, bytes]], expected: int
) -> None:
    sent, pending = await _run(
        boundary.RequestBodyLimitMiddleware(_echo, max_bytes=10), [_part(b"untouched")], headers
    )
    assert sent[0]["status"] == expected
    assert len(pending) == 1


async def test_exact_cap_replays_identical_bytes_and_then_disconnect() -> None:
    chunks = b"abcde" * 5
    got: list[bytes] = []

    async def consumer(scope: Scope, receive: Any, send: Any) -> None:
        got.append(await Request(scope, receive).body())
        assert (await receive())["type"] == "http.disconnect"
        await Response("ok")(scope, receive, send)

    sent, _ = await _run(
        boundary.RequestBodyLimitMiddleware(consumer, max_bytes=len(chunks)),
        [_part(chunks[:3], more=True), _part(chunks[3:])],
        [(b"content-length", str(len(chunks)).encode())],
    )
    assert got == [chunks]
    assert sent[0]["status"] == 200


async def test_length_mismatch_within_cap_is_not_accepted() -> None:
    sent, _ = await _run(
        boundary.RequestBodyLimitMiddleware(_echo, max_bytes=20),
        [_part(b"123")],
        [(b"content-length", b"4")],
    )
    assert sent[0]["status"] == 400


@pytest.mark.parametrize("outcome", ["success", "inner_error", "disconnect", "too_large"])
async def test_rolled_spool_closes_on_every_exit(
    monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    buffers: list[Any] = []

    def tracked(**kwargs: Any) -> Any:
        buffer = SpooledTemporaryFile(**kwargs)
        buffers.append(buffer)
        return buffer

    monkeypatch.setattr(boundary, "SPOOL_MEMORY_BYTES", 4)
    monkeypatch.setattr(boundary, "SpooledTemporaryFile", tracked)

    async def consume(scope: Scope, receive: Any, send: Any) -> None:
        assert await Request(scope, receive).body() == b"abcdefgh"
        if outcome == "inner_error":
            raise RuntimeError("synthetic downstream failure")
        await Response("ok")(scope, receive, send)

    pieces = [_part(b"abcdefgh", more=outcome in {"disconnect", "too_large"})]
    if outcome == "disconnect":
        pieces.append({"type": "http.disconnect"})
    if outcome == "too_large":
        pieces.append(_part(b"x" * 20))
    app = boundary.RequestBodyLimitMiddleware(consume, max_bytes=16)
    if outcome == "inner_error":
        with pytest.raises(RuntimeError, match="synthetic downstream"):
            await _run(app, pieces)
    else:
        await _run(app, pieces)
    assert len(buffers) == 1
    assert buffers[0]._rolled is True
    assert buffers[0].closed


async def test_multipart_parser_never_starts_for_oversized_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from starlette import requests

    app = FastAPI()

    @app.post("/upload")
    async def upload(file: UploadFile = File()) -> dict[str, int]:
        return {"size": len(await file.read())}

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("multipart ayrıştırıcısı boyut kapısından önce çağrıldı")

    monkeypatch.setattr(requests, "MultiPartParser", forbidden)
    body = (
        b'--x\r\nContent-Disposition: form-data; name="file"; filename="x.txt"\r\n'
        b"\r\nprivate fixture\r\n--x--\r\n"
    )
    sent, _ = await _run(
        boundary.RequestBodyLimitMiddleware(app, max_bytes=len(body) - 1),
        [_part(body)],
        [(b"content-type", b"multipart/form-data; boundary=x")],
    )
    assert sent[0]["status"] == 413


@pytest.mark.parametrize("body", [b"", b'{"value":"small"}'])
async def test_empty_get_and_small_json_remain_usable(body: bytes) -> None:
    seen: list[bytes] = []

    async def consumer(scope: Scope, receive: Any, send: Any) -> None:
        seen.append(await Request(scope, receive).body())
        await Response("ok")(scope, receive, send)

    sent, _ = await _run(
        boundary.RequestBodyLimitMiddleware(consumer, max_bytes=32),
        [_part(body)],
        method="GET" if not body else "POST",
    )
    assert seen == [body]
    assert sent[0]["status"] == 200


@pytest.mark.parametrize("kind", ["websocket", "lifespan"])
async def test_non_http_is_passed_through(kind: str) -> None:
    seen: list[str] = []

    async def downstream(scope: Scope, receive: Any, send: Any) -> None:
        seen.append(scope["type"])

    async def forbidden() -> Message:
        pytest.fail("HTTP olmayan bağlantı okunmamalı")

    async def send(message: Message) -> None:
        pytest.fail("HTTP olmayan bağlantıya yanıt üretilmemeli")

    await boundary.RequestBodyLimitMiddleware(downstream, max_bytes=1)(
        {"type": kind}, forbidden, send
    )
    assert seen == [kind]


async def test_real_app_early_rejection_keeps_cors_security_and_request_id(
    client: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from httpx import ASGITransport, AsyncClient

    from app.core.config import get_settings
    from app.main import create_app

    monkeypatch.setattr(get_settings(), "max_upload_bytes", 16)
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as scoped:
        response = await scoped.post(
            "/courses",
            content=b"x" * (boundary.MULTIPART_ENVELOPE_BYTES + 17),
            headers={
                "Origin": get_settings().cors_origins[0],
                "X-Request-ID": "synthetic-body-limit",
            },
        )
        assert response.status_code == 413
        assert response.headers["access-control-allow-origin"] == get_settings().cors_origins[0]
        assert response.headers["x-content-type-options"] == "nosniff"
        assert (
            response.headers["x-request-id"]
            == response.json()["error"]["request_id"]
            == "synthetic-body-limit"
        )
        assert (await scoped.get("/health/live")).status_code == 200


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"0")]])
@pytest.mark.parametrize("split_empty_body", [False, True])
async def test_verified_empty_get_never_uses_thread_io(
    monkeypatch: pytest.MonkeyPatch,
    headers: list[tuple[bytes, bytes]],
    split_empty_body: bool,
) -> None:
    async def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("gerçekte boş GET, spool için executor kuyruğuna girmemeli")

    monkeypatch.setattr(boundary.asyncio, "to_thread", forbidden)
    seen: list[bytes] = []

    async def consumer(scope: Scope, receive: Any, send: Any) -> None:
        seen.append(await Request(scope, receive).body())
        assert await receive() == {"type": "http.disconnect"}
        await Response("ok")(scope, receive, send)

    pieces = [_part(b"", more=True), _part(b"")] if split_empty_body else [_part(b"")]
    sent, pending = await _run(
        boundary.RequestBodyLimitMiddleware(consumer, max_bytes=10), pieces, headers, method="GET"
    )
    assert sent[0]["status"] == 200
    assert seen == [b""]
    assert not pending


@pytest.mark.parametrize("body, expected", [(b"x", 400), (b"x" * 11, 413)])
async def test_zero_length_get_header_does_not_bypass_actual_body_checks(
    body: bytes, expected: int
) -> None:
    async def forbidden(*args: Any) -> None:
        pytest.fail("başlığa aykırı GET gövdesi uygulamaya ulaşmamalı")

    sent, _ = await _run(
        boundary.RequestBodyLimitMiddleware(forbidden, max_bytes=10),
        [_part(b"", more=True), _part(body)],
        [(b"content-length", b"0")],
        method="GET",
    )
    assert sent[0]["status"] == expected
