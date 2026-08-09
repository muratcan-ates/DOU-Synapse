"""FastAPI uygulama giriş noktası."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    analytics,
    blueprints,
    chat,
    courses,
    documents,
    exams,
    health,
    internal,
    questions,
)
from app.core.config import get_settings
from app.core.db import dispose_engine
from app.core.errors import (
    AppError,
    app_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging, get_logger

logger = get_logger("app.request")

API_SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    logger.info(
        "api başlatıldı",
        extra={"context": {"environment": settings.environment, "version": settings.api_version}},
    )
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Kimlik `Authorization` başlığıyla taşınıyor, çerezle değil; bu bayrak
        # tarayıcıya çerez/kimlik bilgisi göndermesini söyler ve karşılığında
        # `allow_origins` joker olamaz. Kullanılmayan bir gevşetme (R1 bildirdi).
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """API JSON yanıtlarına yüzeye uygun, fail-closed tarayıcı politikası ekle."""
        response = await call_next(request)
        for key, value in API_SECURITY_HEADERS.items():
            response.headers[key] = value
        return response

    @app.middleware("http")
    async def request_logging(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        # `call_next`'ten ÖNCE yazılır: hata handler'ları kimliği buradan okuyor
        # ve zarfa koyuyor (`core/errors.py::request_id_of`). Sonra yazılsaydı
        # yanıt başlığı kimliği taşırdı ama gövde taşımazdı — kullanıcıya
        # gösterilen destek kodu ile logdaki kayıt ayrı düşerdi.
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "istek tamamlandı",
            extra={
                "context": {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                }
            },
        )
        return response

    app.add_exception_handler(AppError, app_error_handler)
    # Şema doğrulaması da projenin tek hata zarfını kullanır; aksi hâlde istemci
    # FastAPI'nin İngilizce `{"detail": [...]}` biçimini ayrıca tanımak zorunda kalır.
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health.router)
    app.include_router(courses.router)
    app.include_router(documents.router)
    app.include_router(questions.router)
    # Paralel geliştirme kirişi: aşağıdaki üç router'ın MODÜLLERİ henüz boş, ama
    # kaydı önden yapıldı. Beş oturum kendi ucunu eklerken bu dosyaya dokunmaz;
    # aksi hâlde aynı iki satır beş kez çakışırdı. Boş router hiçbir yol
    # eklemez, yani sözleşme de bugün değişmez.
    app.include_router(chat.router)
    app.include_router(exams.router)
    # Bugün yol eklemiyor; blueprint şeridi `main.py`'ye dokunmadan doldursun
    # diye lider turunda önden kaydedildi (bkz. api/blueprints.py).
    app.include_router(blueprints.router)
    app.include_router(analytics.router)
    # Faz G'nin dahili tetik ucu. Modül bugün boş ama kaydı önden yapıldı; boş
    # router hiçbir yol eklemez, yani sözleşme bugün değişmez.
    app.include_router(internal.router)
    return app


app = create_app()
