"""Kimlik doğrulama: Supabase JWT'sinin doğrulanması.

Buradaki tek çıktı, isteği yapan kullanıcının kimliğidir. Yetkilendirme (kim hangi derse
erişebilir) bu katmanda değil, ders bağımlılıklarında ve RLS'te yapılır.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt

from app.core.config import Settings
from app.core.errors import AuthenticationError

# Yerel geliştirme ve çevrimdışı demo için sabit kimlik. Üretimde config doğrulayıcısı
# dev_auth_enabled bayrağını reddeder, dolayısıyla bu yol canlıda asla çalışmaz.
DEV_TOKEN_PREFIX = "dev:"  # noqa: S105 - parola değil, kimlik ön eki


@dataclass(frozen=True, slots=True)
class Principal:
    """Doğrulanmış istek sahibi."""

    user_id: UUID
    email: str | None = None


def _decode_supabase_token(token: str, settings: Settings) -> Principal:
    if not settings.supabase_jwt_secret:  # pragma: no cover - config doğrulayıcısı engeller
        raise AuthenticationError("Sunucuda JWT doğrulama anahtarı yapılandırılmamış.")
    try:
        claims = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=settings.jwt_algorithms,
            audience=settings.jwt_audience,
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Oturum süresi doldu, lütfen tekrar giriş yapın.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Geçersiz oturum bilgisi.") from exc

    try:
        user_id = UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Oturum bilgisi beklenen kullanıcı kimliğini içermiyor.") from exc

    email = claims.get("email")
    return Principal(user_id=user_id, email=email if isinstance(email, str) else None)


def _decode_dev_token(token: str) -> Principal:
    """`dev:<uuid>` biçiminde, imzasız yerel kimlik."""
    raw = token.removeprefix(DEV_TOKEN_PREFIX).strip()
    try:
        return Principal(user_id=UUID(raw))
    except ValueError as exc:
        raise AuthenticationError("Geliştirme kimliği `dev:<uuid>` biçiminde olmalıdır.") from exc


def authenticate(token: str, settings: Settings) -> Principal:
    """Bearer token'ı doğrulayıp istek sahibini döndürür."""
    token = token.strip()
    if not token:
        raise AuthenticationError("Oturum bilgisi eksik.")

    if token.startswith(DEV_TOKEN_PREFIX):
        if not settings.dev_auth_enabled:
            raise AuthenticationError("Geliştirme kimlikleri bu ortamda kapalıdır.")
        return _decode_dev_token(token)

    return _decode_supabase_token(token, settings)
