"""Yapılandırılmış JSON loglama ve hassas veri maskeleme.

Güvenlik gereği (ARCHITECTURE.md §6) loglara API anahtarı, JWT, T.C. kimlik numarası veya
e-posta adresi yazılmaz. Maskeleme bir logging.Filter olarak kurulur; böylece uygulama
kodunun her çağrıda maskelemeyi hatırlaması gerekmez.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any, ClassVar

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
    (re.compile(r"(?i)(postgres(?:ql)?(?:\+\w+)?://[^:@\s]+:)[^@\s]+@"), r"\1[REDACTED]@"),
)


def redact(value: str) -> str:
    """Metindeki hassas kalıpları maskeler."""
    for pattern, replacement in _REDACTION_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


class RedactionFilter(logging.Filter):
    """Log kaydının mesajını ve ek alanlarını maskeler."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: _redact_any(v) for k, v in record.args.items()}
            else:
                record.args = tuple(_redact_any(a) for a in record.args)
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            record.context = {k: _redact_any(v) for k, v in context.items()}
        return True


def _redact_any(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: _redact_any(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_any(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    """Tek satırlık JSON log formatı."""

    _RESERVED: ClassVar[frozenset[str]] = frozenset(
        logging.LogRecord("", 0, "", 0, "", None, None).__dict__
    ) | {"message", "asctime", "taskName"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload["context"] = context
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and key != "context":
                payload[key] = _redact_any(value)
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Kök logger'ı JSON formatı ve maskeleme filtresiyle kurar."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Uvicorn kendi handler'larını kurar; kök handler'a devretmelerini sağlarız.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
