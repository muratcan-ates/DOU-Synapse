"""Kimlik doğrulama: Supabase JWT'sinin doğrulanması.

Buradaki tek çıktı, isteği yapan kullanıcının kimliğidir. Yetkilendirme (kim hangi derse
erişebilir) bu katmanda değil, ders bağımlılıklarında ve RLS'te yapılır.

Bu dosyanın tamamı fail-closed yazılmıştır (Anayasa IV): doğrulanamayan her token
reddedilir ve reddin SEBEBİ istemciye söylenmez. "Token süresi doldu" ile "imza geçersiz"
arasındaki farkı istemciye vermek, elindeki token'ın hangi bakımdan bozuk olduğunu
saldırgana ölçtürür; ayrım loga yazılır, kullanıcıya tek bir cümle döner.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import jwt

from app.core.config import Settings
from app.core.errors import AuthenticationError
from app.core.logging import get_logger

logger = get_logger("app.auth")

# Yerel geliştirme ve çevrimdışı demo için sabit kimlik. Üretimde config doğrulayıcısı
# dev_auth_enabled bayrağını reddeder, dolayısıyla bu yol canlıda asla çalışmaz.
DEV_TOKEN_PREFIX = "dev:"  # noqa: S105 - parola değil, kimlik ön eki

#: İstemciye dönen TEK kimlik hatası. Neyin bozuk olduğunu anlatmaz (bkz. modül başlığı).
MESSAGE_INVALID_SESSION = "Oturumunuz geçerli değil. Lütfen tekrar giriş yapın."

#: Token'da bulunması ZORUNLU claim'ler.
#:
#: `exp` olmadan token ölümsüzdür. `aud`/`iss` olmadan başka bir Supabase projesinin
#: token'ı kabul edilebilir hâle gelir — imza anahtarı proje başına ayrı olduğu için bu
#: tek başına yeterli bir savunma değildir ama savunmanın ilk hattı, claim'in İSTENMESİDİR:
#: PyJWT, `audience`/`issuer` verilmediğinde eksik claim'i sessizce görmezden gelir.
_REQUIRED_CLAIMS = ["exp", "sub", "aud", "iss"]


@dataclass(frozen=True, slots=True)
class Principal:
    """Doğrulanmış istek sahibi."""

    user_id: UUID
    email: str | None = None


def _reject(reason: str) -> AuthenticationError:
    """Logda ayrıntılı, istemcide sessiz bir 401 üretir.

    Token'ın kendisi loglanmaz; `RedactionFilter` yakalasa bile (app/core/logging.py)
    yazmamak tek güvenli davranıştır.
    """
    logger.warning("kimlik doğrulama reddi: %s", reason)
    return AuthenticationError(MESSAGE_INVALID_SESSION)


def _verification_algorithms(settings: Settings) -> list[str]:
    """İmza algoritması izin listesi — `none` her koşulda elenir.

    Klasik JWT açığı: `{"alg": "none"}` başlıklı imzasız bir token, izin listesinde
    `none` varsa doğrulanmış sayılır ve herkes herkes olur. PyJWT bu algoritmayı
    listede olmadıkça zaten reddeder; buradaki eleme, `JWT_ALGORITHMS` ortam
    değişkenine yanlışlıkla `none` yazılması durumunu kapatır. Ayar dosyası bu şeridin
    sahipliğinde değil, dolayısıyla savunma tüketim noktasında duruyor.
    """
    allowed = [algorithm for algorithm in settings.jwt_algorithms if algorithm.lower() != "none"]
    if not allowed:
        raise _reject("imza algoritması listesi boş ya da yalnız 'none' içeriyor")
    return allowed


def _expected_issuer(settings: Settings) -> str | None:
    """Beklenen `iss` değeri; yoksa `iss` yalnız VARLIĞI için sınanır.

    `Settings`'te `jwt_issuer` alanı HENÜZ YOK: `config.py` bu şeridin sahipliği dışında
    (10_OKU_ONCE_FAZ2 §3, "yeni ayar gerekiyorsa gruba yaz"). Alan eklendiği an burası
    ek bir değişiklik olmadan sıkışır ve token'ın hangi Supabase projesinden geldiği
    sabitlenir. O güne kadarki gerçek koruma imza anahtarıdır: başka bir projenin
    token'ı bizim `SUPABASE_JWT_SECRET`'imizle doğrulanamaz. Eksik olan derinlik
    savunmasıdır ve docs/security.md'de "uygulanmadı" olarak yazılıdır.
    """
    issuer = getattr(settings, "jwt_issuer", None)
    return issuer if isinstance(issuer, str) and issuer.strip() else None


def _decode_supabase_token(token: str, settings: Settings) -> Principal:
    if not settings.supabase_jwt_secret:  # pragma: no cover - config doğrulayıcısı engeller
        raise _reject("SUPABASE_JWT_SECRET tanımsız")

    issuer = _expected_issuer(settings)
    try:
        claims = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=_verification_algorithms(settings),
            audience=settings.jwt_audience,
            issuer=issuer,
            options={"require": _REQUIRED_CLAIMS},
        )
    except jwt.ExpiredSignatureError:
        raise _reject("token süresi dolmuş") from None
    except jwt.InvalidAudienceError:
        raise _reject("aud claim'i beklenen değerde değil") from None
    except jwt.InvalidIssuerError:
        raise _reject("iss claim'i beklenen değerde değil") from None
    except jwt.MissingRequiredClaimError as exc:
        raise _reject(f"zorunlu claim eksik: {exc.claim}") from None
    except jwt.InvalidAlgorithmError:
        raise _reject("izin verilmeyen imza algoritması") from None
    except jwt.InvalidTokenError as exc:
        # İmza uyuşmazlığı da dahil kalan her şey. Sınıf adı loga yazılır; token yazılmaz.
        raise _reject(f"token doğrulanamadı ({type(exc).__name__})") from None

    subject = claims.get("sub")
    if not isinstance(subject, str):
        raise _reject("sub claim'i metin değil")
    try:
        user_id = UUID(subject)
    except ValueError:
        # Supabase `sub` alanına kullanıcının UUID'sini yazar. UUID olmayan bir değer
        # kabul edilseydi kimlik, veritabanındaki hiçbir profile karşılık gelmeyen bir
        # dizeye dayanırdı.
        raise _reject("sub claim'i UUID değil") from None

    email = claims.get("email")
    return Principal(user_id=user_id, email=email if isinstance(email, str) else None)


def _decode_dev_token(token: str) -> Principal:
    """`dev:<uuid>` biçiminde, imzasız yerel kimlik."""
    raw = token.removeprefix(DEV_TOKEN_PREFIX).strip()
    try:
        return Principal(user_id=UUID(raw))
    except ValueError:
        raise AuthenticationError("Geliştirme kimliği `dev:<uuid>` biçiminde olmalıdır.") from None


def authenticate(token: str, settings: Settings) -> Principal:
    """Bearer token'ı doğrulayıp istek sahibini döndürür."""
    token = token.strip()
    if not token:
        raise AuthenticationError("Oturum bilgisi eksik.")

    if token.startswith(DEV_TOKEN_PREFIX):
        # Bu şeridin en kritik satırı: dev kimlikleri üretimde kabul edilirse
        # `Bearer dev:<uuid>` yazan herkes o kullanıcı olur. Bayrak `config.py`'de
        # üretim ortamında zaten açılamıyor; burası ikinci kapı ve testi var.
        if not settings.dev_auth_enabled:
            raise _reject("dev kimliği kapalı ortamda denendi")
        return _decode_dev_token(token)

    return _decode_supabase_token(token, settings)
