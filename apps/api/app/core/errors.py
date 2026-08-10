"""Uygulama hataları ve tutarlı hata yanıtları.

Kullanıcıya asla ham istisna metni, yığın izi veya sağlayıcı hata mesajı gösterilmez;
teknik ayrıntı loglara, anlaşılır Türkçe mesaj kullanıcıya gider.
"""

from __future__ import annotations

import uuid

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Hata zarfının gövdesi. Üç handler da bunu üretir, kimse elle sözlük yazmaz."""

    code: str
    message: str
    #: İsteği loglarda bulmaya yarayan kimlik. **Asla boş dönmez** — istek
    #: middleware'den geçmediyse (doğrudan çağrılan handler, bazı test yolları)
    #: burada üretilir. "Bazen var" bir alan, istemcide "bazen göster" demektir
    #: ve kullanıcıya destek kodu vaat edip vermemek en kötüsüdür.
    request_id: str


class ErrorEnvelope(BaseModel):
    """Projenin TEK hata sözleşmesi: `{"error": {"code", "message", "request_id"}}`.

    Zarf 002'ye kadar `{"code", "message"}` idi ve istek kimliği yalnız
    `X-Request-ID` yanıt başlığında taşınıyordu. İki sorun vardı: çapraz-origin
    JavaScript o başlığı `expose_headers` olmadan okuyamıyor, ve başlık
    sözleşmenin parçası değil taşıyıcının ayrıntısı. Kimliği gövdeye almak,
    tarayıcının başlık politikasına bağımlılığı tamamen kaldırıyor.

    Zarfı router içinde yeniden tanımlamak yasak (Anayasa XI): bu depoda aynı
    hata bir kez `chat.py` ile `schemas/chat.py` arasında yaşandı ve iki taraf
    ayrıştığında her istek 422 dönüyordu.
    """

    error: ErrorDetail


def request_id_of(request: Request) -> str:
    """İsteğin kimliği; middleware koymadıysa üretir.

    Üretme dalı bir kaçış değil, fail-closed bir varsayılan: kimliksiz bir hata
    yanıtı, kullanıcıya gösterilecek destek kodunun olmadığı anlamına gelir.
    """
    existing = getattr(request.state, "request_id", None)
    return existing if isinstance(existing, str) and existing else uuid.uuid4().hex


def error_response(request: Request, *, status_code: int, code: str, message: str) -> JSONResponse:
    """Tek çıkış noktası. Hata yanıtı üreten her yol buradan geçer."""
    envelope = ErrorEnvelope(
        error=ErrorDetail(code=code, message=message, request_id=request_id_of(request))
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump())


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


class RateLimitError(AppError):
    """Kota aşıldı. `api/chat.py`'den buraya taşındı (002/FR-222).

    İkinci bir modül aynı hata tipine ihtiyaç duyduğu an, hata sözlüğünün tek
    yeri burasıdır; bir uç dosyasının içinde yaşayan hata tipi, ikinci ucu o uca
    bağımlı kılardı.
    """

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class ConcurrencyLimitError(AppError):
    """Aynı kullanıcının hâlâ süren bir işi var (FR-222).

    409, 429 DEĞİL. İkisi farklı sorular: 429 "çok sık istedin, şu kadar bekle",
    409 ise "senin başlattığın iş hâlâ sürüyor". Kullanıcının yapması gereken de
    farklı, dolayısıyla istemcinin ikisini ayırt edebilmesi gerekiyor. Hata
    zarfı `{code, message, request_id}` olarak sabit (lider sözleşmesi) ve
    `Retry-After` başlığı çapraz-origin JavaScript'e `expose_headers` olmadan
    görünmüyor — geriye ayırt edici kanal olarak durum kodu ve `code` kalıyor.
    """

    status_code = status.HTTP_409_CONFLICT
    code = "concurrent_request"


class StorageUnavailableError(AppError):
    """Belge deposuna geçici olarak erişilemiyor.

    Sağlayıcının ham yanıtı kullanıcıya taşınmaz: servis anahtarları, bucket adı
    veya iç ağ ayrıntıları hata metninde bulunabilir. Teknik neden loglanır;
    istemci yalnız yeniden denenebilir, sabit bir sözleşme görür.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "storage_unavailable"


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(request, status_code=exc.status_code, code=exc.code, message=exc.message)


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


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
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

    return error_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_error",
        message=message,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Beklenmeyen hatalar: ayrıntı loga, kullanıcıya genel mesaj."""
    from app.core.logging import get_logger

    get_logger("app.error").exception("beklenmeyen hata", exc_info=exc)
    return error_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_error",
        message="İşlem tamamlanamadı. Lütfen daha sonra tekrar deneyin.",
    )
