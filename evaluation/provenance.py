"""Evaluation evidence from the serving runtime, never from an operator note.

Receipts are integrity-bound runtime observations, not remote attestation or a
semantic quality verdict. Only a human-labelled real response establishes quality.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID


class EvidenceError(ValueError):
    """Unknown or inconsistent runtime evidence; never a passing quality result."""


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def require_loopback_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise EvidenceError("Değerlendirme sırrı yalnız açık bir loopback API adresine gönderilir.")


def _uuid(value: Any) -> bool:
    try:
        UUID(str(value))
        return isinstance(value, str)
    except (ValueError, TypeError):
        return False


def _timestamp(value: Any) -> datetime:
    try:
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError
        return result
    except (ValueError, TypeError) as exc:
        raise EvidenceError("Sunucu kanıtının saat dilimli zaman damgası yok.") from exc


def validate_runtime(
    runtime: Any, *, run_id: str | None = None, candidate_sha: str | None = None
) -> dict[str, Any]:
    if (
        not isinstance(runtime, dict)
        or runtime.get("schema_version") != 1
        or runtime.get("kind") != "evaluation_runtime"
    ):
        raise EvidenceError("Gerçek sağlayıcıyla koşulduğunu gösteren sunucu kanıtı yok.")
    for field in ("run_id", "runtime_id"):
        if not _uuid(runtime.get(field)):
            raise EvidenceError(f"Sunucu kanıtında geçerli {field} yok.")
    if run_id is not None and runtime["run_id"] != run_id:
        raise EvidenceError("Değerlendirme koşusu kimliği eşleşmiyor.")
    if not re.fullmatch(r"[0-9a-f]{40}", str(runtime.get("candidate_sha", ""))):
        raise EvidenceError("Sunucu kanıtında tam aday SHA yok.")
    if candidate_sha is not None and runtime["candidate_sha"] != candidate_sha:
        raise EvidenceError("Sunucu ve değerlendirilen aday SHA eşleşmiyor.")
    if not re.fullmatch(r"[0-9a-f]{64}", str(runtime.get("config_digest", ""))):
        raise EvidenceError("Sunucu yapılandırma özeti yok.")
    if runtime.get("candidate_dirty") is not False:
        raise EvidenceError("Kaydedilmemiş sunucu değişiklikleri gerçek kalite kanıtı olamaz.")
    if runtime.get("configured_fake") is not False or runtime.get("effective_fake") is not False:
        raise EvidenceError("Sahte veya belirsiz sağlayıcı gerçek kalite kanıtı olamaz.")
    if runtime.get("credential_scope") != "evaluation":
        raise EvidenceError("Sunucu ayrı değerlendirme anahtarını kullanmıyor.")
    targets = runtime.get("targets")
    if (
        not isinstance(targets, list)
        or not targets
        or any(
            not isinstance(target, dict)
            or target.get("provider") not in {"groq", "gemini"}
            or not target.get("model")
            or target.get("credential_present") is not True
            for target in targets
        )
    ):
        raise EvidenceError("Sunucunun gerçek sağlayıcı hedefi doğrulanamadı.")
    _timestamp(runtime.get("recorded_at"))
    return runtime


def decode_receipt(value: str | None) -> dict[str, Any] | None:
    if not value or len(value) > 65536:
        return None
    try:
        result = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        return result if isinstance(result, dict) else None
    except (ValueError, UnicodeDecodeError):
        return None


def evaluation_request_digest(
    *,
    course_id: str,
    question: str,
    mode: str,
    session_id: str | None = None,
    student_attempt: str | None = None,
) -> str:
    return digest(
        {
            "course_id": course_id,
            "question": question,
            "mode": mode,
            "session_id": session_id,
            "student_attempt": student_attempt,
        }
    )


def response_evidence(
    runtime: Any, receipt: Any, body: Any, request: dict[str, Any] | None = None
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "classification": "unknown",
        "quality_eligible": False,
        "receipt": receipt,
        "reason": None,
    }
    try:
        validate_runtime(runtime)
        if (
            not isinstance(receipt, dict)
            or receipt.get("schema_version") != 1
            or receipt.get("kind") != "evaluation_response"
        ):
            raise EvidenceError("Yanıta bağlı sunucu kanıtı yok.")
        for field in (
            "run_id",
            "runtime_id",
            "candidate_sha",
            "config_digest",
            "candidate_dirty",
            "configured_fake",
            "effective_fake",
            "credential_scope",
        ):
            if receipt.get(field) != runtime.get(field):
                raise EvidenceError(f"Yanıt ile sunucu kanıtı uyuşmuyor: {field}.")
        if not _uuid(receipt.get("request_id")):
            raise EvidenceError("Yanıtın istek kimliği yok.")
        if _timestamp(receipt.get("recorded_at")) < _timestamp(runtime["recorded_at"]):
            raise EvidenceError("Yanıt kanıtı sunucu kaydından eski.")
        if receipt.get("body_digest") != digest(body):
            raise EvidenceError("Yanıt içeriği ile kanıt özeti uyuşmuyor.")
        if not re.fullmatch(r"[0-9a-f]{64}", str(receipt.get("request_digest", ""))):
            raise EvidenceError("Yanıtın özgün soru/oturum isteği kanıtı yok.")
        if request is not None and receipt["request_digest"] != evaluation_request_digest(
            **request
        ):
            raise EvidenceError("Yanıt başka soru/ders/mod/oturum isteğine ait.")
        if receipt.get("outcome") == "fake":
            result.update(classification="fake", reason="Sahte cevap gerçek kalite kanıtı olamaz.")
            return result
        calls = receipt.get("calls")
        if not isinstance(calls, list) or any(
            not isinstance(call, dict)
            or call.get("provider") not in {"groq", "gemini"}
            or not call.get("model")
            or call.get("status") not in {"completed", "failed"}
            for call in calls
        ):
            raise EvidenceError("Gerçek sağlayıcı çağrı kaydı doğrulanamadı.")
        targets = {(target["provider"], target["model"]) for target in runtime["targets"]}
        if any((call["provider"], call["model"]) not in targets for call in calls):
            raise EvidenceError("Çağrılan sağlayıcı/model sunucu hedefleri arasında değil.")
        outcome = receipt.get("outcome")
        if outcome not in {"provider", "cache", "no_provider", "fake"}:
            raise EvidenceError("Yanıtın üretim yolu bilinmiyor.")
        result["classification"] = outcome
        if outcome == "provider":
            if not any(
                call["status"] == "completed"
                and call["provider"] == receipt.get("provider")
                and call["model"] == receipt.get("model")
                for call in calls
            ):
                raise EvidenceError("Tamamlanmış gerçek sağlayıcı çağrısı yok.")
            result["quality_eligible"] = True
        elif outcome == "fake":
            raise EvidenceError("Sahte cevap gerçek kalite kanıtı olamaz.")
        return result
    except EvidenceError as exc:
        result["classification"] = "fake" if result["classification"] == "fake" else "unknown"
        result["reason"] = str(exc)
        result["quality_eligible"] = False
        return result


def require_sample_evidence(payload: dict[str, Any]) -> None:
    runtime = validate_runtime(payload.get("runtime_manifest"))
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise EvidenceError("Örneklem yanıt kayıtları yok.")
    request_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise EvidenceError("Örneklem yanıt kaydı nesne değil.")
        receipt = record.get("response_receipt")
        if isinstance(receipt, dict) and receipt.get("request_id") in request_ids:
            raise EvidenceError("Aynı yanıt isteği örneklemde birden çok kez kullanılamaz.")
        if isinstance(receipt, dict):
            request_ids.add(receipt.get("request_id"))
        body = record.get("response_body")
        request = {
            "course_id": payload.get("course_id"),
            "question": record.get("question"),
            "mode": record.get("chat_mode", "qa"),
            "session_id": record.get("request_session_id"),
            "student_attempt": record.get("student_attempt"),
        }
        evidence = response_evidence(runtime, receipt, body, request)
        if evidence["quality_eligible"] is not True:
            raise EvidenceError(
                f"{record.get('item_id', '?')}: {evidence['reason'] or evidence['classification']}"
            )
        if not isinstance(body, dict) or any(
            record.get(field) != body.get(field) for field in ("status", "answer", "citations")
        ):
            raise EvidenceError("Etiketlenen cevap ile sunucu yanıtı uyuşmuyor.")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
