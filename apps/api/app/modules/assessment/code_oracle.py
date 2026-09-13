"""Kod sorularının metinsel cevap anahtarı; öğrenci/soru kodu çalıştırılmaz."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.schemas.assessment import BugHuntPayload, BugHuntSubmission, CodeTracePayload


def normalize_trace_output(value: str) -> str:
    """CRLF tekilleşir, yalnız bir son LF isteğe bağlıdır; diğer baytlar korunur."""
    return value.replace("\r\n", "\n").removesuffix("\n")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Yinelenen cevap alanı")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("Geçersiz JSON sabiti")


def code_oracle(payload: CodeTracePayload | BugHuntPayload, given: str) -> int | None:
    """100/0 kesin eşleşme kararı; None semantik belirsizlik ve puansız abstention."""
    if isinstance(payload, CodeTracePayload):
        return (
            100
            if normalize_trace_output(given) == normalize_trace_output(payload.answer_key)
            else 0
        )
    try:
        raw = json.loads(given, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        submitted = BugHuntSubmission.model_validate(raw)
    except (ValueError, ValidationError, TypeError, RecursionError):
        return None
    line_count = len(payload.code.splitlines())
    expected = payload.answer_key
    if not 1 <= expected.line <= line_count or submitted.line > line_count:
        return None
    if submitted.line != expected.line:
        return 0
    if submitted.bug_type == expected.bug_type and submitted.fix_summary == expected.fix_summary:
        return 100
    # Aynı satırın eş anlamlı/alternatif açıklamasını metinsel oracle yargılayamaz.
    return None
