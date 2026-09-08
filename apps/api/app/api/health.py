"""Sağlık kontrolü uçları.

`/health/live` süreç ayakta mı sorusunu yanıtlar (bağımlılık yoktur).
`/health/ready` veritabanı erişimini de sınar; deploy sonrası duman testi ve demo günü
ısıtma isteği bu ucu kullanır.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.core.readiness import check_readiness

router = APIRouter(prefix="/health", tags=["health"])


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
    snapshot = await check_readiness()
    if snapshot["status"] != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": snapshot["status"], "checks": snapshot["checks"]}
