"""L5: gerçek HTTP kimlik bağımlılığı ve uygulama açılışında kapalı ret."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.security import MESSAGE_INVALID_SESSION

SECRET = "synthetic-l5-auth-key-only-for-tests-64-characters-long-no-live-key"
ISSUER = "https://auth.example.invalid/auth/v1"
USER_ID = UUID("a5000000-0000-4000-8000-000000000001")


def _token(case: str = "valid") -> str:
    claims: dict[str, Any] = {
        "sub": str(USER_ID),
        "aud": "authenticated",
        "iss": ISSUER,
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "role": "authenticated",
    }
    if case == "expired":
        claims["exp"] = datetime.now(UTC) - timedelta(minutes=1)
    if case == "issuer":
        claims["iss"] = "https://foreign.example.invalid/auth/v1"
    if case == "audience":
        claims["aud"] = "service_role"
    if case.startswith("missing-"):
        claims.pop(case.removeprefix("missing-"))
    algorithm = case if case in {"none", "HS384", "HS512"} else "HS256"
    secret = "" if algorithm == "none" else SECRET
    if case == "signature":
        secret = "synthetic-wrong-signature-key-with-at-least-sixty-four-test-characters"
    token = jwt.encode(claims, secret, algorithm=algorithm)
    if case == "unsigned":
        return token.rsplit(".", 1)[0] + "."
    if case == "two-segments":
        return token.rsplit(".", 1)[0]
    if case == "dev-disabled":
        return f"dev:{USER_ID}"
    return token


@pytest.fixture
def auth_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # Gerçek anahtar veya .env kullanılmaz; ayarlar her vakada yeniden çözülür.
    values = {
        "ENVIRONMENT": "local",
        "DEV_AUTH_ENABLED": "false",
        "SUPABASE_JWT_SECRET": SECRET,
        "SUPABASE_JWT_ISSUER": ISSUER,
        "JWT_AUDIENCE": "authenticated",
        "JWT_ALGORITHMS": '["HS256"]',
        "STORAGE_BACKEND": "local",
        "EMBEDDING_WARMUP_ENABLED": "false",
        "LLM_FAKE_PROVIDER": "false",
        "EVAL_RUNTIME_ENABLED": "false",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _response(token: str, algorithms: list[str] | None = None) -> Any:
    from app.api.deps import PrincipalDep
    from app.main import create_app

    app = create_app()
    if algorithms is not None:
        settings = get_settings().model_copy(update={"jwt_algorithms": algorithms})
        app.dependency_overrides[get_settings] = lambda: settings

    # Üretimdeki dependency ve hata handler'ı; yalnız kabul sonrası gövde sentetik.
    def probe(principal: PrincipalDep) -> dict[str, str]:
        return {"user_id": str(principal.user_id)}

    # Yerel annotation future-annotations altında isim çözümünden kaçırılmaz.
    probe.__annotations__["principal"] = PrincipalDep
    app.get("/l5-auth-probe")(probe)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get("/l5-auth-probe", headers={"Authorization": f"Bearer {token}"})


@pytest.mark.parametrize(
    "case",
    [
        "signature",
        "expired",
        "issuer",
        "audience",
        "none",
        "unsigned",
        "two-segments",
        "HS384",
        "HS512",
        "missing-exp",
        "missing-sub",
        "missing-aud",
        "missing-iss",
        "dev-disabled",
    ],
)
async def test_invalid_jwt_returns_closed_http_error(auth_environment: None, case: str) -> None:
    response = await _response(_token(case))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    assert response.json()["error"]["message"] == MESSAGE_INVALID_SESSION
    assert "user_id" not in response.json()


@pytest.mark.parametrize(
    "algorithms", [[], ["none"], ["HS384"], ["HS256", "HS512"], ["HS256", "none"]]
)
async def test_algorithm_setting_cannot_expand_acceptance(
    auth_environment: None, algorithms: list[str]
) -> None:
    response = await _response(_token(algorithms[-1] if algorithms else "valid"), algorithms)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


async def test_hs256_positive_control(auth_environment: None) -> None:
    assert Settings().jwt_algorithms == ["HS256"]
    response = await _response(_token())
    assert response.status_code == 200
    assert response.json() == {"user_id": str(USER_ID)}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"DEV_AUTH_ENABLED": "true", "ENVIRONMENT": "production"}, "DEV_AUTH_ENABLED"),
        ({"SUPABASE_JWT_SECRET": ""}, "SUPABASE_JWT_SECRET"),
        ({"ENVIRONMENT": "production", "SUPABASE_JWT_ISSUER": ""}, "SUPABASE_JWT_ISSUER"),
        (
            {"ENVIRONMENT": "production", "SUPABASE_JWT_ISSUER": "http://auth.invalid/auth/v1"},
            "SUPABASE_JWT_ISSUER",
        ),
        ({"ENVIRONMENT": "production", "LLM_FAKE_PROVIDER": "true"}, "LLM_FAKE_PROVIDER"),
        (
            {"STORAGE_BACKEND": "supabase", "SUPABASE_URL": "", "SUPABASE_SERVICE_ROLE_KEY": ""},
            "SUPABASE_URL",
        ),
        (
            {
                "STORAGE_BACKEND": "supabase",
                "SUPABASE_URL": "https://storage.example.invalid",
                "SUPABASE_SERVICE_ROLE_KEY": "",
            },
            "SUPABASE_SERVICE_ROLE_KEY",
        ),
        ({"ENVIRONMENT": "production", "STORAGE_BACKEND": "local"}, "STORAGE_BACKEND"),
        (
            {"INGESTION_LEASE_SECONDS": "10", "INGESTION_HEARTBEAT_SECONDS": "10"},
            "Ingestion heartbeat",
        ),
    ],
)
def test_create_app_rejects_unsafe_configuration(
    auth_environment: None,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, str],
    message: str,
) -> None:
    from app.main import create_app

    for name, value in overrides.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    with pytest.raises(ValidationError, match=message):
        create_app()
