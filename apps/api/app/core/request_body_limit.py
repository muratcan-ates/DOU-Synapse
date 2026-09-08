"""Ayrıştırıcıdan önce gerçek istek boyutunu sınırlayan ASGI katmanı.

Dosya sınırına küçük bir multipart zarf payı eklenir. Content-Length yalnız erken
ret için kullanılır; kabul kararı alınan gerçek baytlara dayanır. Ek geçici kopya
bilinçlidir: yarıda kesilen multipart ayrıştırıcısının açık dosyalarını bırakmadan
sınırı uygulamak için gövde önce sınırlı bir spool içinde doğrulanır.
"""

from __future__ import annotations

import asyncio
from tempfile import SpooledTemporaryFile

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response

MULTIPART_ENVELOPE_BYTES = 64 * 1024
SPOOL_MEMORY_BYTES = 64 * 1024
REPLAY_CHUNK_BYTES = 64 * 1024


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        if max_bytes < 1:
            raise ValueError("İstek gövdesi sınırı pozitif olmalıdır.")
        self.app = app
        self.max_bytes = max_bytes

    async def _reject(self, scope: Scope, receive: Receive, send: Send, *, too_large: bool) -> None:
        headers = {"Connection": "close"} if scope.get("http_version") in {"1.0", "1.1"} else None
        response = error_response(
            Request(scope),
            status_code=413 if too_large else 400,
            code="payload_too_large" if too_large else "invalid_request_body",
            message=(
                "İstek gövdesi izin verilen boyutu aşıyor."
                if too_large
                else "İstek gövdesinin uzunluk bilgisi geçersiz."
            ),
            headers=headers,
        )
        await response(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        lengths = [
            value.strip()
            for key, value in scope.get("headers", [])
            if key.lower() == b"content-length"
        ]
        if len(lengths) > 1 or (lengths and (not lengths[0] or not lengths[0].isdigit())):
            await self._reject(scope, receive, send, too_large=False)
            return
        # Çok uzun sayıyı int'e çevirmek de gereksiz bir kaynak tüketimi olur.
        if lengths and len(lengths[0]) > 20:
            await self._reject(scope, receive, send, too_large=True)
            return
        declared = int(lengths[0]) if lengths else None
        if declared is not None and declared > self.max_bytes:
            await self._reject(scope, receive, send, too_large=True)
            return

        with SpooledTemporaryFile(max_size=SPOOL_MEMORY_BYTES, mode="w+b") as buffered:
            received = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                if message["type"] != "http.request":
                    await self._reject(scope, receive, send, too_large=False)
                    return
                body = message.get("body", b"")
                received += len(body)
                if received > self.max_bytes:
                    await self._reject(scope, receive, send, too_large=True)
                    return
                if body:
                    await asyncio.to_thread(buffered.write, body)
                if not message.get("more_body", False):
                    break
            if declared is not None and declared != received:
                await self._reject(scope, receive, send, too_large=False)
                return
            # Gerçek gövde okunup başlıkla karşılaştırıldıktan sonra boş istek
            # spool I/O'su istemez. Sağlık yoklaması embedding/dosya işleriyle
            # aynı executor kuyruğunu beklememeli; Content-Length'e kör güvenilmez.
            if received:
                await asyncio.to_thread(buffered.seek, 0)
            replayed = 0
            finished = False

            async def replay() -> Message:
                nonlocal replayed, finished
                if finished:
                    # StreamingResponse gibi tüketicilerin bağlantı kapanmasını
                    # dinlemesine izin ver; sonsuz boş request mesajı üretme.
                    return await receive()
                chunk = (
                    await asyncio.to_thread(buffered.read, REPLAY_CHUNK_BYTES) if received else b""
                )
                replayed += len(chunk)
                finished = replayed == received
                return {"type": "http.request", "body": chunk, "more_body": not finished}

            await self.app(scope, replay, send)
