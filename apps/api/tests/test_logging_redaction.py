"""Log maskeleme testleri (ARCHITECTURE.md §6).

Güvenlik raporundaki TC-23 vakası: loglarda API anahtarı, JWT, TCKN veya e-posta
bulunmamalı. Bu testler o iddianın kanıtıdır.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.db import _build_control_engine, _build_engine
from app.core.logging import JsonFormatter, RedactionFilter, redact


class TestRedact:
    def test_llm_api_anahtari_maskelenir(self) -> None:
        assert "sk-" not in redact("anahtar: sk-abcdefghijklmnopqrstuvwxyz123456")
        assert "gsk_" not in redact("groq: gsk_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123")
        assert "[REDACTED_API_KEY]" in redact("google: AIzaSyA1234567890abcdefghijklmnop")

    def test_jwt_maskelenir(self) -> None:
        token = (
            "eyJhbGciOiJIUzI1NiJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
            ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        assert token not in redact(f"token={token}")

    def test_bearer_basligi_maskelenir(self) -> None:
        assert redact("Authorization: Bearer abc.def.ghi") == ("Authorization: Bearer [REDACTED]")

    def test_tckn_maskelenir(self) -> None:
        assert "12345678901" not in redact("T.C. No: 12345678901 soruma bak")
        # 11 haneden farklı sayılar korunur — sayfa numaraları bozulmamalı.
        assert "sayfa 12" in redact("sayfa 12")
        assert "1234567890123" in redact("1234567890123")

    def test_eposta_maskelenir(self) -> None:
        assert "@" not in redact("kullanıcı ayse@dogus.edu.tr giriş yaptı").split("giriş")[0]

    def test_baglanti_dizesi_parolasi_maskelenir(self) -> None:
        masked = redact("postgresql+psycopg://dou_app:gizliparola@localhost/db")
        assert "gizliparola" not in masked
        assert "dou_app" in masked

    def test_temiz_metin_bozulmaz(self) -> None:
        text = "İşletim Sistemleri dersi için 42 chunk işlendi"
        assert redact(text) == text


class TestJsonFormatter:
    def _record(self, message: str, **extra: object) -> logging.LogRecord:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=message,
            args=None,
            exc_info=None,
        )
        for key, value in extra.items():
            setattr(record, key, value)
        return record

    def test_cikti_gecerli_json(self) -> None:
        payload = json.loads(JsonFormatter().format(self._record("merhaba")))
        assert payload["message"] == "merhaba"
        assert payload["level"] == "INFO"
        assert "ts" in payload

    def test_turkce_karakterler_korunur(self) -> None:
        payload = json.loads(JsonFormatter().format(self._record("İşletim Sistemleri")))
        assert payload["message"] == "İşletim Sistemleri"

    def test_context_alani_maskelenir(self) -> None:
        record = self._record("istek", context={"email": "ayse@dogus.edu.tr", "status": 200})
        RedactionFilter().filter(record)
        payload = json.loads(JsonFormatter().format(record))
        assert payload["context"]["email"] == "[REDACTED_EMAIL]"
        assert payload["context"]["status"] == 200

    def test_filtre_mesaji_maskeler(self) -> None:
        record = self._record("giriş: sk-abcdefghijklmnopqrstuvwxyz123456")
        RedactionFilter().filter(record)
        assert "sk-" not in json.loads(JsonFormatter().format(record))["message"]


@pytest.mark.parametrize("builder", [_build_engine, _build_control_engine])
def test_database_engines_hide_bound_values_from_errors(
    builder: Callable[[Settings], AsyncEngine],
) -> None:
    """A failed content INSERT must not render its bound value in logs/errors."""

    settings = Settings(
        _env_file=None,
        dev_auth_enabled=True,
        database_url="postgresql+psycopg://dou_app:local@localhost/dou_synapse_test_logs",
    )
    engine = builder(settings)
    secret = "öğrencinin gizli sohbet metni"
    error = DBAPIError.instance(
        "INSERT INTO chat_messages(content) VALUES (%(content)s)",
        {"content": secret},
        ValueError("sentetik veritabanı hatası"),
        ValueError,
        hide_parameters=engine.sync_engine.hide_parameters,
    )

    assert engine.sync_engine.hide_parameters is True
    assert secret not in str(error)
    assert "SQL parameters hidden due to hide_parameters=True" in str(error)
