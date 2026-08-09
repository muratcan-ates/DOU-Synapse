"""Uygulama hataları ve tutarlı hata yanıtları.

Kullanıcıya asla ham istisna metni, yığın izi veya sağlayıcı hata mesajı gösterilmez;
teknik ayrıntı loglara, anlaşılır Türkçe mesaj kullanıcıya gider.
"""

from __future__ import annotations

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Kullanıcıya gösterilebilir uygulama hatası."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"


class PayloadTooLargeError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    code = "payload_too_large"


async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


#: Pydantic hata türü → kullanıcıya gösterilecek Türkçe cümle şablonu.
#:
#: Neden gerekli: FastAPI kendi doğrulama hatasını `{"detail": [...]}` biçiminde ve
#: İNGİLİZCE döndürür. Projenin geri kalanı `{"error": {"code", "message"}}` üretiyor,
#: dolayısıyla istemci iki ayrı zarf tanımak zorunda kalıyordu ve ikincisini
#: tanımıyordu: arayüz "İşlem tamamlanamadı" diyip gerçek sebebi yutuyordu. Zarfı
#: burada birleştirmek, düzeltmeyi her istemcide ayrı ayrı yazmaktan ucuz ve
#: Anayasa V'e (kullanıcıya dönen metin Türkçe) uygun.
_VALIDATION_MESSAGES: dict[str, str] = {
    "missing": "{alan} alanı zorunlu.",
    "string_too_short": "{alan} çok kısa.",
    "string_too_long": "{alan} çok uzun.",
    "extra_forbidden": "{alan} tanınmayan bir alan.",
    "uuid_parsing": "{alan} geçerli bir kimlik değil.",
    "enum": "{alan} için geçersiz bir değer gönderildi.",
    "json_invalid": "İstek gövdesi okunamadı.",
}

#: Gövde alan adlarının kullanıcıya gösterilecek karşılıkları. Ham alan adı
#: (`question`, `student_attempt`) kullanıcıya bir şey anlatmaz.
_FIELD_LABELS: dict[str, str] = {
    "question": "Soru",
    "student_attempt": "Denemen",
    "mode": "Mod",
    "session_id": "Oturum",
    "message": "Mesaj",
    "email": "E-posta",
    "full_name": "Ad soyad",
    "code": "Ders kodu",
    "title": "Başlık",
    "role": "Rol",
}


def _field_label(location: tuple[object, ...]) -> str:
    """Pydantic konumundan okunabilir alan adı üretir."""
    parts = [str(item) for item in location if item not in {"body", "query", "path"}]
    if not parts:
        return "Gönderilen veri"
    return _FIELD_LABELS.get(parts[-1], parts[-1])


async def validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """FastAPI'nin doğrulama hatasını projenin tek hata zarfına çevirir.

    Yalnız İLK hata anlatılır: kullanıcıya yedi maddelik bir liste sunmak, tek bir
    alanı düzeltmesi gerektiğini gizler. Tam liste zaten logdadır.
    """
    assert isinstance(exc, RequestValidationError)
    errors = exc.errors()
    if errors:
        first = errors[0]
        template = _VALIDATION_MESSAGES.get(str(first.get("type")), "{alan} geçersiz.")
        message = template.format(alan=_field_label(tuple(first.get("loc", ()))))
    else:
        message = "Gönderilen veri geçersiz."

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"error": {"code": "validation_error", "message": message}},
    )


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Beklenmeyen hatalar: ayrıntı loga, kullanıcıya genel mesaj."""
    from app.core.logging import get_logger

    get_logger("app.error").exception("beklenmeyen hata", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_error",
                "message": "İşlem tamamlanamadı. Lütfen daha sonra tekrar deneyin.",
            }
        },
    )
