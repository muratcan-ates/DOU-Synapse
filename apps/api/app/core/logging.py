"""JSON günlükleri, bilinen hassas kalıpları maskeleme ve içeriksiz istisna özeti.

Regex maskeleri serbest öğrenci metnini tanıyamaz. exc_info taşıyan kayıtlarda
mesaj/zincir/notes/kaynak satırı hiç biçimlendirilmez; izinli tanı alanları seçilir.
Uvicorn'un düz ERROR kayıtları da yalnız sabit olay ve dar sayısal tanı taşır.
Diğer serbest günlük mesajları için genel anonimlik veya kusursuz maskeleme iddiası yoktur.
"""

from __future__ import annotations

import ast
import errno
import json
import logging
import re
import sys
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from types import CodeType, TracebackType
from typing import Any, ClassVar, cast

from app.core.request_context import ServerRequestId

_REDACTION_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # LLM / servis anahtarları
    (re.compile(r"\b(?:sk|gsk|rk)[-_][A-Za-z0-9_-]{16,}\b"), "[REDACTED_API_KEY]"),
    (re.compile(r"\bAIza[A-Za-z0-9_-]{20,}\b"), "[REDACTED_API_KEY]"),
    # JWT (üç base64url parçası)
    (
        re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
        "[REDACTED_JWT]",
    ),
    (re.compile(r"(?i)\bbearer\s+\S+"), "Bearer [REDACTED]"),
    # T.C. kimlik numarası: 11 hane, komşu rakamlardan ayrık
    (re.compile(r"(?<!\d)\d{11}(?!\d)"), "[REDACTED_TCKN]"),
    # E-posta
    (re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    # Postgres bağlantı dizesindeki parola
    (
        re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?://[^:@\s]+:)[^@\s]+@"),
        r"\1[REDACTED]@",
    ),
)

# Yalnız sabit olay şablonları korunur; `%s`, Exception nesnesi veya keyfi extra
# alanı üzerinden aynı hata içeriğinin yeniden eklenmesi bu yoldan taşınamaz.
_EXCEPTION_EVENTS: dict[tuple[str, str], tuple[str, str]] = {
    ("app.error", "beklenmeyen hata"): ("beklenmeyen hata", "internal_error"),
    ("app.warmup", "embedding ısıtması başarısız"): (
        "embedding ısıtması başarısız",
        "embedding_warmup_failed",
    ),
    ("app.assessment.grading", "değerlendirmede sağlayıcı hatası"): (
        "değerlendirmede sağlayıcı hatası",
        "assessment_provider_failed",
    ),
    ("app.assessment.question_gen", "soru üretiminde sağlayıcı hatası"): (
        "soru üretiminde sağlayıcı hatası",
        "question_provider_failed",
    ),
    ("uvicorn.error", "Exception in ASGI application\n"): (
        "ASGI uygulama hatası",
        "asgi_application_error",
    ),
    ("uvicorn.error", "Exception in 'lifespan' protocol\n"): (
        "ASGI yaşam döngüsü hatası",
        "asgi_lifespan_error",
    ),
}
_EXCEPTION_LOGGERS = frozenset(name for name, _ in _EXCEPTION_EVENTS)
_ERROR_TYPES = {
    kind: kind.__name__
    for kind in (
        Exception,
        BaseException,
        ExceptionGroup,
        BaseExceptionGroup,
        AssertionError,
        AttributeError,
        EOFError,
        IndexError,
        KeyError,
        LookupError,
        NotImplementedError,
        OSError,
        FileNotFoundError,
        PermissionError,
        ConnectionError,
        BrokenPipeError,
        OverflowError,
        RuntimeError,
        StopIteration,
        StopAsyncIteration,
        SyntaxError,
        TimeoutError,
        TypeError,
        UnicodeError,
        ValueError,
        ZeroDivisionError,
    )
}
_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_APP_ROOT = Path(__file__).resolve().parent.parent
_APP_PACKAGES = frozenset({"api", "core", "models", "modules", "schemas"})
_APP_TOP_FILES = frozenset({"main.py", "worker.py", "contracts.py", "__init__.py"})
_MAX_TRACEBACK_SCAN = 64
_MAX_APP_FRAMES = 8

# Uvicorn lifespan.failed iletileri traceback'i exc_info olmadan düz mesaj
# olarak taşır. Serbest ERROR mesajı/args/extra biçimlendirilmez; bilinen
# şablonlar sabit olaylara, bilinmeyenler içeriksiz hata kaydına dönüşür.
_SERVER_ERROR_EVENTS = {
    "Application startup failed. Exiting.": (
        "uygulama başlangıcı başarısız",
        "application_startup_failed",
    ),
    "Application shutdown failed. Exiting.": (
        "uygulama kapanışı başarısız",
        "application_shutdown_failed",
    ),
    "ASGI callable returned without starting response.": (
        "ASGI yanıtı başlatılmadı",
        "asgi_response_not_started",
    ),
    "ASGI callable returned without completing response.": (
        "ASGI yanıtı tamamlanmadı",
        "asgi_response_not_completed",
    ),
    "ASGI callable returned without sending handshake.": (
        "ASGI el sıkışması gönderilmedi",
        "asgi_handshake_not_sent",
    ),
    "ASGI callable returned without completing handshake.": (
        "ASGI el sıkışması tamamlanmadı",
        "asgi_handshake_not_completed",
    ),
    "ASGI callable should return None, but returned '%s'.": (
        "ASGI dönüş sözleşmesi ihlali",
        "asgi_invalid_return",
    ),
    "Error loading ASGI app factory: %s": (
        "ASGI uygulama üreticisi yüklenemedi",
        "asgi_factory_load_failed",
    ),
    "Cancel %s running task(s), timeout graceful shutdown exceeded": (
        "sunucu kapanış süresi aşıldı",
        "graceful_shutdown_timeout",
    ),
}
_SERVER_OS_ERROR_TYPES = frozenset(
    {
        OSError,
        BlockingIOError,
        ChildProcessError,
        ConnectionError,
        BrokenPipeError,
        ConnectionAbortedError,
        ConnectionRefusedError,
        ConnectionResetError,
        FileExistsError,
        FileNotFoundError,
        InterruptedError,
        IsADirectoryError,
        NotADirectoryError,
        PermissionError,
        ProcessLookupError,
        TimeoutError,
    }
)


def _plain_server_error(record: logging.LogRecord) -> bool:
    return record.name == "uvicorn.error" and record.levelno >= logging.ERROR


def _server_error_record(record: logging.LogRecord) -> tuple[str, dict[str, str | int]]:
    """Sabit şablonlar ve dar sayısal tanılar; serbest hata metni okunmaz."""
    message, error_code = "sunucu hata kaydı", "uvicorn_error"
    if type(record.msg) is str:
        message, error_code = _SERVER_ERROR_EVENTS.get(record.msg, (message, error_code))
    context: dict[str, str | int] = {"error_code": error_code}
    if error_code == "graceful_shutdown_timeout" and type(record.args) is tuple:
        if len(record.args) == 1 and type(record.args[0]) is int:
            count = record.args[0]
            if 0 <= count <= 1_000_000:
                context["task_count"] = count
    elif type(record.msg) in _SERVER_OS_ERROR_TYPES:
        # Yalnız yerleşik OSError türü: alt sınıf özelliği/strerror/filename yok.
        message, context = "sunucu işletim sistemi hatası", {"error_code": "server_os_error"}
        number = cast(OSError, record.msg).errno
        if type(number) is int and number in errno.errorcode:
            context["errno"] = number
            context["errno_name"] = errno.errorcode[number]
    return message, context


@lru_cache(maxsize=128)
def _source_functions(filename: str) -> tuple[str, frozenset[str], int] | None:
    """Yalnız mevcut uygulama kaynak dosyasındaki izinli adlar; satır içeriği dönmez."""
    try:
        path = Path(filename)
        relative = path.relative_to(_APP_ROOT)
        if not relative.parts or ".." in relative.parts or path.suffix != ".py":
            return None
        if relative.parts[0] not in _APP_PACKAGES and relative.as_posix() not in _APP_TOP_FILES:
            return None
        # Dışarı yönelen symlink ve göreli/yapay co_filename izinli kaynak değildir.
        if path.resolve(strict=True) != path or not path.is_file():
            return None
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = {"<module>"}
        synthetic: dict[type[ast.AST], str] = {
            ast.Lambda: "<lambda>",
            ast.ListComp: "<listcomp>",
            ast.DictComp: "<dictcomp>",
            ast.SetComp: "<setcomp>",
            ast.GeneratorExp: "<genexpr>",
        }
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
            if type(node) in synthetic:
                names.add(synthetic[type(node)])
        return relative.as_posix(), frozenset(names), len(source.splitlines())
    except (OSError, UnicodeError, SyntaxError, ValueError, RuntimeError):
        return None


def _application_frame(code: CodeType, line: int) -> dict[str, str | int] | None:
    allowed = _source_functions(code.co_filename)
    if allowed is None:
        return None
    relative, names, lines = allowed
    if code.co_name not in names or not 1 <= line <= lines:
        return None
    return {"path": relative, "function": code.co_name, "line": line}


def _exception_summary(exc_info: object) -> dict[str, Any]:
    """str/repr, locals, cause/context, notes, group üyeleri ve satır metni okunmaz."""
    error_type = "Exception"
    frames: list[dict[str, str | int]] = []
    cursor: TracebackType | None = None
    if isinstance(exc_info, tuple) and len(exc_info) == 3:
        error_type = _ERROR_TYPES.get(type(exc_info[1]), "Exception")
        if isinstance(exc_info[2], TracebackType):
            cursor = exc_info[2]
    scanned = 0
    while cursor is not None and scanned < _MAX_TRACEBACK_SCAN:
        frame = _application_frame(cursor.tb_frame.f_code, cursor.tb_lineno)
        if frame is not None:
            frames.append(frame)
        scanned += 1
        cursor = cursor.tb_next
    return {
        "error_type": error_type,
        "frames": frames[-_MAX_APP_FRAMES:],
        "frames_truncated": cursor is not None or len(frames) > _MAX_APP_FRAMES,
    }


def _exception_record(record: logging.LogRecord) -> tuple[str, str, dict[str, str]]:
    """Keyfi mesaj/args/extra yerine sabit olay ve dar destek bağlamı."""
    message, error_code = ("istisna kaydedildi", "exception_recorded")
    if type(record.msg) is str and not record.args:
        message, error_code = _EXCEPTION_EVENTS.get(
            (record.name, record.msg), (message, error_code)
        )
    logger_name = record.name if record.name in _EXCEPTION_LOGGERS else "app.exception"
    context = {"error_code": error_code}
    supplied = getattr(record, "context", None)
    if record.name == "app.error" and isinstance(supplied, dict):
        request_id = supplied.get("request_id")
        if type(request_id) is ServerRequestId:
            # Sunucunun tek UUID çekilişi; rastlantısal 11 rakam destek kodunu bozmaz.
            context["request_id"] = request_id
        elif type(request_id) is str and _REQUEST_ID.fullmatch(request_id):
            # Aynı UUID görünümündeki sıradan metin iç kaynak kanıtı taşımaz.
            context["request_id"] = redact(request_id)
    return logger_name, message, context


def redact(value: str) -> str:
    """Metindeki hassas kalıpları maskeler."""
    for pattern, replacement in _REDACTION_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


class RedactionFilter(logging.Filter):
    """Log kaydının mesajını ve ek alanlarını maskeler."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info or _plain_server_error(record):
            # Burada str(msg) bile çağrılmaz: msg/args bir istisna nesnesi olabilir.
            # Biçimleyici aynı izinli seçimi bağımsız yapar; filtre tek güvenlik katmanı değil.
            return True
        record.msg = redact(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _redact_any(v) for k, v in record.args.items()}
            else:
                record.args = tuple(_redact_any(a) for a in record.args)
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            record.context = _redact_context(record.name, context)
        return True


def _redact_any(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: _redact_any(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        # JSON her ikisini de diziye çevirir; tuple içindeki metin muaf değildir.
        return [_redact_any(v) for v in value]
    return value


def _redact_context(logger_name: str, context: dict[str, Any]) -> dict[str, Any]:
    """Muafiyet yalnız iki logger'ın doğrudan alanındaki tam iç türe aittir."""
    return {
        key: value
        if logger_name in {"app.request", "app.error"}
        and key == "request_id"
        and type(value) is ServerRequestId
        else _redact_any(value)
        for key, value in context.items()
    }


class JsonFormatter(logging.Formatter):
    """Tek satırlık JSON log formatı."""

    _RESERVED: ClassVar[frozenset[str]] = frozenset(
        logging.LogRecord("", 0, "", 0, "", None, None).__dict__
    ) | {"message", "asctime", "taskName"}

    def format(self, record: logging.LogRecord) -> str:
        if record.exc_info:
            logger_name, message, exception_context = _exception_record(record)
            return json.dumps(
                {
                    "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
                    "level": record.levelname,
                    "logger": logger_name,
                    "message": message,
                    "context": exception_context,
                    "exception": _exception_summary(record.exc_info),
                },
                ensure_ascii=False,
            )
        if _plain_server_error(record):
            server_message, server_context = _server_error_record(record)
            return json.dumps(
                {
                    "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
                    "level": "CRITICAL" if record.levelno >= logging.CRITICAL else "ERROR",
                    "logger": "uvicorn.error",
                    "message": server_message,
                    "context": server_context,
                },
                ensure_ascii=False,
            )
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload["context"] = _redact_context(record.name, context)
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and key != "context":
                payload[key] = _redact_any(value)
        return json.dumps(payload, ensure_ascii=False, default=str)


_LOGGING_FAILURE_RECORD = (
    '{"level":"ERROR","logger":"app.logging","message":"log emission failed",'
    '"context":{"error_code":"logging_output_failed"}}\n'
)


class PrivacySafeStreamHandler(logging.StreamHandler):
    """Günlük arızasında ham record/trace yerine tek sabit, içeriksiz işaret.

    Handler.handle'ın kilidi normal çağrıları sıraya alır. Aynı handler'a sink
    veya formatter üzerinden tekrar giriş kaydı düşürülür; fallback yeni bir
    logging çağrısı yapmaz. KeyboardInterrupt/SystemExit gibi BaseException
    kontrol sinyalleri bilinçli olarak dışarı taşar.
    """

    def __init__(self, stream: Any = None) -> None:
        super().__init__(stream)
        self._emitting = False
        self._reporting_failure = False

    def emit(self, record: logging.LogRecord) -> None:
        if self._emitting or self._reporting_failure:
            return
        self._emitting = True
        try:
            message = self.format(record)
            self.stream.write(message + self.terminator)
            self.flush()
        except Exception:
            # Normal Exception (logger kaynaklı RecursionError dahil) HTTP hata
            # zarfını bozmasın. BaseException süreç kontrolü burada yutulmaz.
            self.handleError(record)
        finally:
            self._emitting = False

    def handleError(self, record: logging.LogRecord) -> None:
        del record
        if self._reporting_failure:
            return
        self._reporting_failure = True
        try:
            if sys.stderr is not None:
                # Standart handleError, record.msg/args ve traceback'i basar.
                # Aynı kaydı tekrar biçimlendirme; tek doğrudan ASCII write yap.
                sys.stderr.write(_LOGGING_FAILURE_RECORD)
        except Exception:  # noqa: S110 - logging again would recurse or expose private data
            # Arızalı fallback sink'i için başka sink/logger zinciri yoktur.
            pass
        finally:
            self._reporting_failure = False


def configure_logging(level: int = logging.INFO) -> None:
    """Kök logger'ı JSON formatı ve maskeleme filtresiyle kurar."""
    handler = PrivacySafeStreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # HTTP istemcilerinin INFO/DEBUG tanıları özel URL ve başlık taşıyabilir.
    # Uygulama DEBUG çalışsa bile transport tanıları üretim loguna taşınmaz.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # Uvicorn kendi handler'larını kurar; kök handler'a devretmelerini sağlarız.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True

    # Uvicorn erişim kaydı ham yol, sorgu dizgesi ve istemci adresi taşır.
    # Bu kurulum uygulamanın yaşam döngüsünde Uvicorn yapılandırmasından sonra
    # çalışır. Yalnız bu kanalı kapat; şablon kullanan app.request ve sunucu
    # hata kayıtları açık kalır. Kök logger'ın DEBUG olması da kanalı açmaz.
    logging.getLogger("uvicorn.access").disabled = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
