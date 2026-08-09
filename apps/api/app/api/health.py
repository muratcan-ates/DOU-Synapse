"""Sağlık kontrolü uçları.

`/health/live` süreç ayakta mı sorusunu yanıtlar (bağımlılık yoktur).
`/health/ready` veritabanı erişimini de sınar; deploy sonrası duman testi ve demo günü
ısıtma isteği bu ucu kullanır.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.core.logging import get_logger
from app.core.warmup import warmup_state

router = APIRouter(prefix="/health", tags=["health"])
logger = get_logger("app.health")

#: Hazırlığı DÜŞÜRMEYEN kontrol değerleri.
#:
#: `disabled` burada, çünkü "ısıtma bu süreçte çalışmıyor" bir arıza değil bir
#: yapılandırma: model ilk istekte tembel yüklenir ve sistem çalışır. `warming`
#: ve `failed` listede YOK — ikisi de 503'e düşer ve gerekçeleri
#: `core/warmup.py`'nin modül docstring'inde yazılı.
_HEALTHY_VALUES = frozenset({"ok", "disabled"})


@router.get("/live")
async def live() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.environment,
        "version": settings.api_version,
    }


@router.get("/ready")
async def ready(response: Response) -> dict[str, Any]:
    checks: dict[str, str] = {}
    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
            vector_ready = await session.scalar(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'vector'")
            )
        checks["database"] = "ok"
        checks["pgvector"] = "ok" if vector_ready else "missing"
    except Exception as exc:
        logger.warning("hazırlık kontrolü başarısız", extra={"context": {"error": str(exc)}})
        checks["database"] = "error"

    # "Süreç ayakta" ile "embedding hazır" ayrı sorular; ikincisi burada, bir
    # BAĞIMLILIK durumu olarak raporlanır. `/health/live` bundan etkilenmez ve
    # ısınma sürerken de 200 döner — yoksa orkestratör ısınan bir süreci
    # ölü sanıp öldürür.
    checks["embedding"] = warmup_state()

    healthy = all(value in _HEALTHY_VALUES for value in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "checks": checks}
