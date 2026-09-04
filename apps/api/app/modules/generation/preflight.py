"""Provider configuration/access checks, never a pedagogical quality verdict."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

from app.core.candidate_identity import candidate_identity
from app.core.config import Settings
from app.core.provider_config import (
    SUPPORTED_EVALUATION_PROVIDERS,
    canonical_digest,
    provider_config_snapshot,
)
from app.modules.generation.llm import LiteLlmClient, LlmRequest


async def provider_preflight(
    settings: Settings,
    *,
    probe: bool = False,
    timeout_seconds: float = 10,
    max_tokens: int = 256,
    completion_fn: Any | None = None,
) -> dict[str, Any]:
    if not 0 < timeout_seconds <= 30 or not 32 <= max_tokens <= 512:
        raise ValueError("Probe bounds must be 0 < timeout <= 30 and 32 <= max_tokens <= 512.")
    configuration = provider_config_snapshot(settings)
    targets = configuration["targets"]
    checks: list[dict[str, Any]] = []
    for target in targets:
        error = None
        if target["provider"] not in SUPPORTED_EVALUATION_PROVIDERS:
            error = "unsupported_provider"
        elif target["model"] == "<invalid>":
            error = "invalid_model"
        elif not target["credential_present"]:
            error = "missing_credential"
        checks.append(
            {
                **target,
                "status": "blocked" if error else "not_run",
                "error_code": error,
                "latency_ms": None,
            }
        )
    blockers = []
    if not targets:
        blockers.append("no_targets")
    if configuration["effective_fake"]:
        blockers.append("effective_fake_provider")
    if any(check["error_code"] for check in checks):
        blockers.append("invalid_target_configuration")
    calls = 0
    if probe and not blockers:
        for check in checks:
            # One actual adapter attempt per target, no automatic retry or fallback.
            isolated = settings.model_copy(
                update={
                    "llm_primary_model": check["model"],
                    "llm_fallback_model": "",
                    "llm_max_retries": 0,
                    "llm_timeout_seconds": min(settings.llm_timeout_seconds, timeout_seconds),
                }
            )
            client = LiteLlmClient(isolated, completion_fn=completion_fn)
            started = time.perf_counter()
            calls += 1
            try:
                result = await client.complete(
                    LlmRequest(
                        system='Return only the JSON object {"ready": true}.',
                        user='This is a model access check. Return {"ready": true}.',
                        json_output=True,
                        max_tokens=max_tokens,
                        max_provider_attempts=1,
                    )
                )
                if json.loads(result.text) != {"ready": True}:
                    raise ValueError("Unexpected probe response")
                check["status"] = "accessible"
            except (ValueError, TypeError):
                check["status"] = "failed"
                check["error_code"] = "invalid_probe_response"
            except Exception:
                # Provider exception messages can contain URLs, request bodies or keys.
                check["status"] = "failed"
                check["error_code"] = "provider_unavailable"
            check["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    if any(check["status"] == "failed" for check in checks):
        blockers.append("probe_failed")
    return {
        "schema_version": 1,
        "kind": "provider_preflight",
        "recorded_at": datetime.now(UTC).isoformat(),
        **candidate_identity(),
        "config_digest": canonical_digest(configuration),
        "configuration": configuration,
        "mode": "probe" if probe else "offline",
        "status": "blocked" if blockers else ("accessible" if probe else "configuration_ready"),
        "quality_status": "not_evaluated",
        "blockers": blockers,
        "fallback_independent": len({target["provider"] for target in targets}) > 1,
        "checks": checks,
        "provider_calls": calls,
        "probe_timeout_seconds": timeout_seconds if probe else None,
        "probe_max_output_tokens": max_tokens if probe else None,
    }
