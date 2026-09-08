"""HTTP istekleri için yalnız sunucunun oluşturduğu destek kimliği."""

from __future__ import annotations

from uuid import uuid4

from fastapi import Request


class ServerRequestId(str):
    """Metin girdisi kabul etmez; tek UUID4 çekilişinin hex gösterimini taşır.

    İç tür günlükteki dar alan seçimi içindir. HTTP/JSON metni bu türe
    dönüştürülmez. Bu ayrım keyfi Python çalıştırma yetkisine karşı bir sınır
    değildir; yanıt ve veritabanındaki metin kopyası anonimlik kanıtı sayılmaz.
    """

    def __new__(cls) -> ServerRequestId:
        return super().__new__(cls, uuid4().hex)


def request_id_of(request: Request) -> ServerRequestId:
    """Aynı HTTP isteğinde aynı iç nesneyi kullan; düz metin state'e güvenme."""
    existing = getattr(request.state, "request_id", None)
    if type(existing) is ServerRequestId:
        return existing
    request_id = ServerRequestId()
    request.state.request_id = request_id
    return request_id
