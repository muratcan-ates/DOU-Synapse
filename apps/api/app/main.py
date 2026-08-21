"""FastAPI uygulama giriş noktası."""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import (
    admin,
    analytics,
    blueprints,
    chat,
    courses,
    dashboard,
    documents,
    exams,
    feedback,
    health,
    internal,
    policy,
    privacy,
    profile,
    questions,
    sources,
)
from app.core.config import get_settings
from app.core.db import dispose_engine
from app.core.errors import (
    AppError,
    app_error_handler,
    starlette_http_exception_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.core.logging import configure_logging, get_logger
from app.core.openapi import configure_openapi
from app.core.request_observability import (
    enqueue_request_event,
    route_template_of,
    start_request_observer,
    stop_request_observer,
)
from app.core.warmup import start_warmup

logger = get_logger("app.request")

API_SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}

# FastAPI'nin yerel/demo dokuman HTML'i CDN scripti ve inline baslatma kodu
# kullanir. Bu daha dar ama farkli CSP yalniz docs rotalarina, docs zaten
# production'da kapaliyken verilir. JSON/urun yanitlari yukaridaki `none`
# politikasinda kalir.
API_DOCS_SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": (
        "default-src 'none'; "
        "script-src 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src data: https://fastapi.tiangolo.com; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


def _response_security_headers(path: str, *, docs_enabled: bool) -> dict[str, str]:
    if docs_enabled and (path == "/docs" or path.startswith("/docs/")):
        return API_DOCS_SECURITY_HEADERS
    return API_SECURITY_HEADERS


def _request_path_is_observability_shell(path: str) -> bool:
    """Ham yolu depolamadan admin/health/docs kabuk trafigini ayirir."""

    return (
        path in {"/admin", "/health", "/docs", "/redoc", "/openapi.json"}
        or path.startswith("/admin/")
        or path.startswith("/health/")
        or path.startswith("/docs/")
    )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    logger.info(
        "api başlatıldı",
        extra={"context": {"environment": settings.environment, "version": settings.api_version}},
    )
    # Isıtma BAŞLATILIR, BEKLENMEZ (FR-221). `await` edilseydi üretim
    # sağlayıcısında ~19 sn'lik bir startup oluşur ve orkestratörün startup
    # probe penceresi aşılırdı — çözdüğünden büyük bir arıza. Hazır olup
    # olmadığı `/health/ready` üzerinden bildiriliyor (bkz. core/warmup.py).
    await start_request_observer()
    warmup_task = start_warmup()
    try:
        yield
    finally:
        if warmup_task is not None:
            warmup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await warmup_task
        # Observer kendi tek baglantili havuzunu kullanir. Once bounded flush,
        # sonra butun motorlari kapatmak son batch'in dispose ile yarismamasini
        # saglar; iki saniyelik tavan shutdown'i sonsuza dek tutmaz.
        try:
            await stop_request_observer()
        finally:
            await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.api_docs_enabled else None,
        # Yalniz Swagger desteklenir. ReDoc farkli bir CDN CSP izni isterdi;
        # kullanilmayan ikinci bir script yuzeyi acmak yerine fail-closed kapali.
        redoc_url=None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )

    @app.middleware("http")
    async def request_logging(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # İstemci başlığı telemetriye alınmaz: base64url görünümlü bir değer
        # e-posta/prompt gibi içeriği kalıcı request_id alanına kaçırabilirdi.
        # Tek korelasyon kimliği sunucuda üretilir ve header/body/log/event'in
        # tamamına aynı değer olarak gider.
        request_id = uuid.uuid4().hex
        # `call_next`'ten ÖNCE yazılır: hata handler'ları kimliği buradan okuyor
        # ve zarfa koyuyor (`core/errors.py::request_id_of`). Sonra yazılsaydı
        # yanıt başlığı kimliği taşırdı ama gövde taşımazdı — kullanıcıya
        # gösterilen destek kodu ile logdaki kayıt ayrı düşerdi.
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            # ServerErrorMiddleware kullanıcı middleware'inin dışında kaldığı
            # için bu dönüşüm burada yapılmazsa 500'de header, completion log ve
            # telemetry kaybolur. Ham exception yanıt/event'e taşınmaz.
            response = await unhandled_error_handler(request, exc)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        route_template = route_template_of(request)
        # 204/304 yanıtlarında temsil gövdesi yoktur. BaseHTTPMiddleware yanıtı
        # yeniden sardığında FastAPI'nin varsayılan JSON content-type başlığını
        # korumak Chromium'un başarılı 204 fetch'ini `net::ERR_ABORTED` saymasına
        # yol açabiliyor. HTTP sözleşmesini gövdesiz yanıta normalize et; request
        # id ve güvenlik başlıkları aşağıda yine eklenir.
        if response.status_code in {204, 304}:
            if "content-type" in response.headers:
                del response.headers["content-type"]
            if "content-length" in response.headers:
                del response.headers["content-length"]
        response.headers["X-Request-ID"] = request_id
        for key, value in _response_security_headers(
            request.url.path,
            docs_enabled=bool(settings.api_docs_enabled),
        ).items():
            response.headers[key] = value
        logger.info(
            "istek tamamlandı",
            extra={
                "context": {
                    "request_id": request_id,
                    "method": request.method,
                    "route": route_template,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                    "outcome_code": getattr(request.state, "outcome_code", None),
                }
            },
        )
        # FastAPI docs rotalari middleware scope'unda bazen sablonsuz kalir.
        # Exact kabuk yolu yalniz burada exclusion icin okunur; enqueue sinirina
        # ve kalici olaya ham path hicbir zaman tasinmaz.
        if not _request_path_is_observability_shell(request.url.path):
            enqueue_request_event(
                request_id=request_id,
                method=request.method,
                route_template=route_template,
                status_code=response.status_code,
                outcome_code=getattr(request.state, "outcome_code", None),
                duration_ms=duration_ms,
            )
        return response

    # Starlette son eklenen middleware'i en dışa yerleştirir. CORS burada,
    # request_logging tanımından SONRA eklenmelidir: iç uygulamadaki beklenmeyen
    # hata güvenli 500 zarfına çevrildiğinde ayrı-origin web uygulaması yanıtı
    # ve destek kodunu yine okuyabilmelidir.
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

    app.add_exception_handler(AppError, app_error_handler)
    # Router seviyesindeki 404/405, endpoint gövdesine hiç girmediği için
    # AppError zincirine uğramaz. Aynı Türkçe ErrorEnvelope burada bağlanır.
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    # Şema doğrulaması da projenin tek hata zarfını kullanır; aksi hâlde istemci
    # FastAPI'nin İngilizce `{"detail": [...]}` biçimini ayrıca tanımak zorunda kalır.
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(health.router)
    app.include_router(profile.router)
    app.include_router(dashboard.router)
    app.include_router(admin.router)
    app.include_router(courses.router)
    app.include_router(documents.router)
    app.include_router(sources.router)
    app.include_router(privacy.router)
    app.include_router(policy.router)
    app.include_router(questions.router)
    app.include_router(chat.router)
    app.include_router(feedback.router)
    app.include_router(exams.router)
    app.include_router(blueprints.router)
    app.include_router(analytics.router)
    # İç worker tetiği OpenAPI'den bilinçli olarak gizlidir; sır yoksa 404,
    # doğru sırla bir ingestion turu çalıştırır.
    app.include_router(internal.router)
    configure_openapi(app)
    return app


app = create_app()
