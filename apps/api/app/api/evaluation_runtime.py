"""Opt-in, loopback evaluation receipts; this is not remote code attestation."""

from __future__ import annotations

import base64
import ipaddress
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from secrets import compare_digest
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Request, Response

from app.api.deps import SettingsDep
from app.core.candidate_identity import candidate_identity
from app.core.config import Settings
from app.core.errors import NotFoundError, PermissionDeniedError, ValidationError
from app.core.provider_config import canonical_digest, provider_config_snapshot
from app.core.provider_evidence import provider_calls


@dataclass(frozen=True)
class EvaluationRuntime:
    runtime_id: str
    recorded_at: str
    identity: dict[str, Any]
    configuration: dict[str, Any]
    config_digest: str


@dataclass
class EvaluationContext:
    runtime: EvaluationRuntime
    run_id: str
    calls: list[dict[str, Any]]


def initialize_evaluation_runtime(app: FastAPI, settings: Settings) -> None:
    if settings.eval_runtime_enabled:
        snapshot = provider_config_snapshot(settings)
        app.state.evaluation_runtime = EvaluationRuntime(
            runtime_id=str(uuid4()),
            recorded_at=datetime.now(UTC).isoformat(),
            identity=candidate_identity(),
            configuration=snapshot,
            config_digest=canonical_digest(snapshot),
        )


def authorize_evaluation(request: Request, settings: Settings) -> EvaluationRuntime:
    expected = settings.eval_runtime_secret
    if not settings.eval_runtime_enabled or not expected:
        raise NotFoundError("Bulunamadı.")
    supplied = request.headers.get("X-Eval-Runtime-Secret", "")
    if not compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        raise PermissionDeniedError("Bu işlem için yetkiniz yok.")
    try:
        loopback = bool(request.client and ipaddress.ip_address(request.client.host).is_loopback)
    except ValueError:
        loopback = False
    if not loopback:
        raise PermissionDeniedError("Değerlendirme yalnız yerel bağlantıda kullanılabilir.")
    runtime = getattr(request.app.state, "evaluation_runtime", None)
    if not isinstance(runtime, EvaluationRuntime):
        raise NotFoundError("Bulunamadı.")
    if canonical_digest(provider_config_snapshot(settings)) != runtime.config_digest:
        raise PermissionDeniedError("Değerlendirme ayarları değişti; sunucuyu yeniden başlatın.")
    return runtime


def runtime_manifest(runtime: EvaluationRuntime, run_id: UUID | str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "evaluation_runtime",
        "run_id": str(run_id),
        "runtime_id": runtime.runtime_id,
        **runtime.identity,
        "config_digest": runtime.config_digest,
        "recorded_at": runtime.recorded_at,
        "configured_fake": runtime.configuration["configured_fake"],
        "effective_fake": runtime.configuration["effective_fake"],
        "targets": runtime.configuration["targets"],
        "credential_scope": runtime.configuration["credential_scope"],
        "configuration": runtime.configuration,
    }


async def evaluation_request_context(
    request: Request,
    settings: SettingsDep,
) -> AsyncIterator[EvaluationContext | None]:
    secret = request.headers.get("X-Eval-Runtime-Secret")
    run_header = request.headers.get("X-Eval-Run-Id")
    if secret is None and run_header is None:
        yield None
        return
    runtime = authorize_evaluation(request, settings)
    try:
        run_id = str(UUID(run_header or ""))
    except ValueError as exc:
        raise ValidationError("Geçerli bir değerlendirme çalıştırma kimliği gereklidir.") from exc
    calls: list[dict[str, Any]] = []
    token = provider_calls.set(calls)
    try:
        yield EvaluationContext(runtime, run_id, calls)
    finally:
        provider_calls.reset(token)


EvaluationContextDep = Annotated[EvaluationContext | None, Depends(evaluation_request_context)]


def attach_evaluation_receipt(
    context: EvaluationContext | None,
    request: Request,
    response: Response,
    body: dict[str, Any],
    *,
    cached: bool,
    request_digest: str,
) -> None:
    if context is None:
        return
    completed = [call for call in context.calls if call["status"] == "completed"]
    last = completed[-1] if completed else None
    if cached:
        outcome = "cache"
    elif last and last["provider"] == "fake":
        outcome = "fake"
    elif last:
        outcome = "provider"
    else:
        outcome = "no_provider"
    receipt = {
        **runtime_manifest(context.runtime, context.run_id),
        "kind": "evaluation_response",
        "recorded_at": datetime.now(UTC).isoformat(),
        "request_id": getattr(request.state, "request_id", None),
        "outcome": outcome,
        "provider": last["provider"] if last else None,
        "model": last["model"] if last else None,
        "calls": context.calls,
        "body_digest": canonical_digest(body),
        "request_digest": request_digest,
    }
    # Only identity and observed transport metadata travel in a receipt.
    receipt.pop("configuration")
    encoded = json.dumps(receipt, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    response.headers["X-Eval-Receipt"] = (
        base64.urlsafe_b64encode(encoded.encode()).decode().rstrip("=")
    )
