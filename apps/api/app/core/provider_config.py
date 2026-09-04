"""Provider routing and a deliberately secret-free configuration projection."""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.config import Settings

DEFAULT_LLM_PRIMARY_MODEL = "groq/openai/gpt-oss-120b"
DEFAULT_LLM_FALLBACK_MODEL = "groq/qwen/qwen3.6-27b"
SUPPORTED_EVALUATION_PROVIDERS = frozenset({"groq", "gemini"})
_MODEL_ID = re.compile(r"^[A-Za-z0-9_.:-]+(?:/[A-Za-z0-9_.:-]+)+$")


def provider_of(model: str) -> str:
    return model.split("/", 1)[0]


def configured_targets(settings: Settings) -> list[str]:
    return list(
        dict.fromkeys(
            model for model in (settings.llm_primary_model, settings.llm_fallback_model) if model
        )
    )


def credential_for(settings: Settings, model: str) -> str | None:
    provider = provider_of(model)
    if provider == "groq":
        return settings.groq_api_key
    if provider in {"gemini", "vertex_ai"}:
        return settings.gemini_api_key
    return None


def effective_fake_provider(settings: Settings) -> bool:
    """Mirror build_llm_client's compatibility fallback, including implicit local fake."""
    return settings.llm_fake_provider or (
        not settings.is_production and not (settings.groq_api_key or settings.gemini_api_key)
    )


def safe_model_id(model: str) -> str:
    # Invalid configuration must not accidentally turn an env secret into report text.
    return model if len(model) <= 200 and _MODEL_ID.fullmatch(model) else "<invalid>"


def target_metadata(settings: Settings) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in configured_targets(settings):
        safe = safe_model_id(model)
        rows.append(
            {
                "slot": "primary" if model == settings.llm_primary_model else "fallback",
                "provider": provider_of(safe) if safe != "<invalid>" else "unknown",
                "model": safe,
                "credential_present": bool((credential_for(settings, model) or "").strip()),
            }
        )
    return rows


def canonical_digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def provider_config_snapshot(settings: Settings) -> dict[str, Any]:
    """Allowlist only: never dump Settings, credentials, DSNs, prompts or personal data."""
    return {
        "targets": target_metadata(settings),
        "configured_fake": settings.llm_fake_provider,
        "effective_fake": effective_fake_provider(settings),
        "credential_scope": "evaluation" if settings.eval_runtime_enabled else "application",
        "eval_provider": settings.eval_llm_provider if settings.eval_runtime_enabled else None,
        "llm": {
            "timeout_seconds": settings.llm_timeout_seconds,
            "max_retries": settings.llm_max_retries,
            "temperature": settings.llm_temperature,
            "chat_max_tokens": settings.llm_chat_max_tokens,
            "chat_max_input_bytes": settings.llm_chat_max_input_bytes,
            "role_aware_max_provider_attempts": 1,
        },
        "retrieval": {
            "top_k": settings.retrieval_top_k,
            "dense_candidates": settings.retrieval_dense_candidates,
            "fts_candidates": settings.retrieval_fts_candidates,
            "rrf_k": settings.retrieval_rrf_k,
            "evidence_threshold": settings.evidence_threshold,
        },
        "embedding": {"provider": settings.embedding_provider, "model": settings.embedding_model},
        "flags": {
            "course_agent_enabled": settings.course_agent_enabled,
            "question_authoring_enabled": settings.question_authoring_enabled,
            "student_assessment_workspace_enabled": settings.student_assessment_workspace_enabled,
        },
    }


def provider_config_digest(settings: Settings) -> str:
    return canonical_digest(provider_config_snapshot(settings))


def evaluation_request_digest(
    *,
    course_id: str,
    question: str,
    mode: str,
    session_id: str | None = None,
    student_attempt: str | None = None,
) -> str:
    """Bind proof to the validated chat request, including Socratic/session inputs."""
    return canonical_digest(
        {
            "course_id": course_id,
            "question": question,
            "mode": mode,
            "session_id": session_id,
            "student_attempt": student_attempt,
        }
    )
