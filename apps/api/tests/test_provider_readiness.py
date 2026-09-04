"""Secret-safe configuration, isolated quota routing and bounded adapter probes."""

from __future__ import annotations

import asyncio
import json
import re
import socket
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.provider_config import (
    DEFAULT_LLM_FALLBACK_MODEL,
    DEFAULT_LLM_PRIMARY_MODEL,
    canonical_digest,
    configured_targets,
    evaluation_request_digest,
    provider_config_snapshot,
)
from app.core.provider_evidence import provider_calls
from app.modules.generation.fake import FakeLlmClient
from app.modules.generation.llm import (
    LiteLlmClient,
    LlmRequest,
    LlmUnavailableError,
    build_llm_client,
)
from app.modules.generation.preflight import provider_preflight


def settings_for(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "_env_file": None,
        "dev_auth_enabled": True,
        "environment": "local",
        "llm_primary_model": DEFAULT_LLM_PRIMARY_MODEL,
        "llm_fallback_model": DEFAULT_LLM_FALLBACK_MODEL,
        "groq_api_key": None,
        "gemini_api_key": None,
        "llm_fake_provider": False,
        "eval_runtime_enabled": False,
        "eval_llm_api_key": None,
        "eval_llm_provider": None,
        "eval_runtime_secret": None,
    }
    values.update(overrides)
    return Settings(**values)


def response(content: str = '{"ready":true}') -> dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


def test_example_and_settings_share_targets_and_unique_env_names() -> None:
    example = (Path(__file__).resolve().parents[3] / ".env.example").read_text()
    names = re.findall(r"^([A-Z][A-Z0-9_]*)=", example, re.MULTILINE)
    assert len(names) == len(set(names))
    assert f"LLM_PRIMARY_MODEL={Settings.model_fields['llm_primary_model'].default}" in example
    assert f"LLM_FALLBACK_MODEL={Settings.model_fields['llm_fallback_model'].default}" in example


def test_offline_fake_compatibility_is_visible() -> None:
    settings = settings_for()
    assert isinstance(build_llm_client(settings), FakeLlmClient)
    snapshot = provider_config_snapshot(settings)
    assert snapshot["configured_fake"] is False
    assert snapshot["effective_fake"] is True


def test_eval_key_without_opt_in_does_not_override_application() -> None:
    settings = settings_for(groq_api_key="application-secret", eval_llm_api_key="evaluation-secret")
    assert settings.groq_api_key == "application-secret"
    assert provider_config_snapshot(settings)["credential_scope"] == "application"


@pytest.mark.parametrize("provider", ["groq", "gemini"])
async def test_eval_key_reaches_actual_adapter_and_clears_other_quota(provider: str) -> None:
    settings = settings_for(
        eval_runtime_enabled=True,
        eval_llm_provider=provider,
        eval_llm_api_key="evaluation-secret",
        eval_runtime_secret="receipt-secret",
        llm_primary_model=f"{provider}/selected-model",
        llm_fallback_model="",
        groq_api_key="application-groq-secret",
        gemini_api_key="application-gemini-secret",
    )
    captured: list[dict[str, Any]] = []

    async def complete(**kwargs: Any) -> dict[str, Any]:
        captured.append(kwargs)
        return response()

    await LiteLlmClient(settings, completion_fn=complete).complete(LlmRequest(system="s", user="u"))
    assert captured[0]["api_key"] == "evaluation-secret"
    assert captured[0]["model"] == f"{provider}/selected-model"
    assert (settings.gemini_api_key if provider == "groq" else settings.groq_api_key) is None
    snapshot = provider_config_snapshot(settings)
    assert snapshot["credential_scope"] == "evaluation"
    assert snapshot["effective_fake"] is False
    assert "secret" not in json.dumps(snapshot)


@pytest.mark.parametrize(
    "overrides",
    [
        {"eval_llm_api_key": None},
        {"eval_llm_provider": None},
        {"llm_fake_provider": True},
        {"llm_fallback_model": "gemini/other"},
        {"llm_primary_model": "", "llm_fallback_model": ""},
        {"eval_runtime_secret": "evaluation-secret"},
        {"environment": "production", "dev_auth_enabled": False, "supabase_jwt_secret": "jwt-test"},
    ],
)
def test_unsafe_eval_configuration_is_rejected(overrides: dict[str, Any]) -> None:
    values = {
        "eval_runtime_enabled": True,
        "eval_llm_provider": "groq",
        "eval_llm_api_key": "evaluation-secret",
        "eval_runtime_secret": "receipt-secret",
    }
    values.update(overrides)
    with pytest.raises(ValidationError):
        settings_for(**values)


def test_empty_eval_provider_from_example_is_valid_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_LLM_PROVIDER", "")
    assert Settings(_env_file=None, dev_auth_enabled=True).eval_llm_provider is None  # type: ignore[call-arg]


def test_snapshot_is_allowlisted_and_digest_changes_only_for_public_config() -> None:
    first = settings_for(groq_api_key="first-secret", supabase_jwt_secret="jwt-secret")
    second = settings_for(groq_api_key="different-secret", supabase_jwt_secret="new-jwt-secret")
    one = provider_config_snapshot(first)
    assert canonical_digest(one) == canonical_digest(provider_config_snapshot(second))
    assert "secret" not in json.dumps(one)
    assert "database" not in json.dumps(one)
    changed = settings_for(groq_api_key="different-secret", llm_temperature=0.7)
    assert canonical_digest(one) != canonical_digest(provider_config_snapshot(changed))


async def test_offline_never_loads_or_calls_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("offline reached a provider/network")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(LiteLlmClient, "_load_completion_fn", forbidden)
    report = await provider_preflight(settings_for(groq_api_key="application-secret"))
    assert report["status"] == "configuration_ready"
    assert report["provider_calls"] == 0
    assert report["quality_status"] == "not_evaluated"
    assert report["fallback_independent"] is False
    assert all(check["status"] == "not_run" for check in report["checks"])


@pytest.mark.parametrize(
    "overrides,blocker",
    [
        ({}, "effective_fake_provider"),
        ({"groq_api_key": "present", "llm_fake_provider": True}, "effective_fake_provider"),
        ({"gemini_api_key": "present"}, "invalid_target_configuration"),
        (
            {"groq_api_key": "present", "llm_primary_model": "unknown/model"},
            "invalid_target_configuration",
        ),
        ({"llm_primary_model": "", "llm_fallback_model": ""}, "no_targets"),
    ],
)
async def test_invalid_real_config_blocks_even_explicit_probe(
    overrides: dict[str, Any], blocker: str
) -> None:
    async def forbidden(**kwargs: Any) -> Any:
        pytest.fail("invalid config must not consume quota")

    report = await provider_preflight(
        settings_for(**overrides), probe=True, completion_fn=forbidden
    )
    assert report["status"] == "blocked"
    assert blocker in report["blockers"]
    assert report["provider_calls"] == 0


async def test_probe_is_one_bounded_attempt_per_target_with_no_secret_output() -> None:
    calls: list[dict[str, Any]] = []

    async def complete(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return response()

    settings = settings_for(groq_api_key="application-secret", llm_max_retries=3)
    report = await provider_preflight(
        settings, probe=True, timeout_seconds=0.5, max_tokens=128, completion_fn=complete
    )
    assert report["status"] == "accessible"
    assert report["provider_calls"] == 2
    assert [call["model"] for call in calls] == configured_targets(settings)
    assert all(call["max_tokens"] == 128 and 0 < call["timeout"] <= 0.5 for call in calls)
    assert "application-secret" not in json.dumps(report)
    assert report["quality_status"] == "not_evaluated"


async def test_failure_body_is_redacted_and_not_retried() -> None:
    calls = 0

    async def fail(**kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise RuntimeError("private-key and student answer must never be serialized")

    report = await provider_preflight(
        settings_for(groq_api_key="private-key"), probe=True, completion_fn=fail
    )
    assert calls == 2
    assert report["status"] == "blocked"
    assert all(check["error_code"] == "provider_unavailable" for check in report["checks"])
    assert "private-key" not in json.dumps(report)
    assert "student answer" not in json.dumps(report)


@pytest.mark.parametrize("body", ["", "not-json", '{"ready":false}', '{"other":true}'])
async def test_probe_requires_expected_json(body: str) -> None:
    async def complete(**kwargs: Any) -> dict[str, Any]:
        return response(body)

    report = await provider_preflight(
        settings_for(groq_api_key="present", llm_fallback_model=""),
        probe=True,
        completion_fn=complete,
    )
    assert report["status"] == "blocked"
    assert report["checks"][0]["error_code"] == "invalid_probe_response"


async def test_timeout_has_no_retry_and_duplicate_target_called_once() -> None:
    calls = 0

    async def slow(**kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(10)
        return response()

    settings = settings_for(groq_api_key="present", llm_fallback_model=DEFAULT_LLM_PRIMARY_MODEL)
    report = await provider_preflight(
        settings, probe=True, timeout_seconds=0.01, completion_fn=slow
    )
    assert report["status"] == "blocked"
    assert calls == 1


async def test_transport_observations_record_failures_and_success_without_content() -> None:
    calls: list[dict[str, Any]] = []
    token = provider_calls.set(calls)
    count = 0

    async def complete(**kwargs: Any) -> dict[str, Any]:
        nonlocal count
        count += 1
        if count == 1:
            raise RuntimeError("private-error")
        return response()

    try:
        await LiteLlmClient(
            settings_for(groq_api_key="private-key", llm_max_retries=0), completion_fn=complete
        ).complete(LlmRequest(system="private-s", user="private-u"))
    finally:
        provider_calls.reset(token)
    assert [call["status"] for call in calls] == ["failed", "completed"]
    assert "private" not in json.dumps(calls)
    assert provider_calls.get() is None


async def test_failed_transport_remains_failed() -> None:
    calls: list[dict[str, Any]] = []
    token = provider_calls.set(calls)

    async def fail(**kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("failure")

    try:
        with pytest.raises(LlmUnavailableError):
            await LiteLlmClient(
                settings_for(groq_api_key="present", llm_fallback_model="", llm_max_retries=0),
                completion_fn=fail,
            ).complete(LlmRequest(system="s", user="u"))
    finally:
        provider_calls.reset(token)
    assert calls[0]["status"] == "failed"


@pytest.mark.parametrize("application_field", ["groq_api_key", "gemini_api_key"])
def test_known_application_key_cannot_be_relabelled_evaluation(application_field: str) -> None:
    with pytest.raises(ValidationError) as caught:
        settings_for(
            eval_runtime_enabled=True,
            eval_llm_provider="groq",
            eval_llm_api_key="same-private-key",
            **{application_field: "same-private-key"},
        )
    assert "same-private-key" not in str(caught.value)


def test_request_digest_binds_all_learning_inputs() -> None:
    base = {
        "course_id": "course",
        "question": "question",
        "mode": "qa",
        "session_id": None,
        "student_attempt": None,
    }
    expected = evaluation_request_digest(**base)
    for field in base:
        assert evaluation_request_digest(**(base | {field: "different"})) != expected
    assert expected == canonical_digest(base)


async def test_fake_completion_is_observed_without_becoming_real_transport() -> None:
    calls: list[dict[str, Any]] = []
    token = provider_calls.set(calls)
    try:
        await FakeLlmClient().complete(LlmRequest(system="s", user="u"))
    finally:
        provider_calls.reset(token)
    assert calls == [{"provider": "fake", "model": "fake/deterministic-v1", "status": "completed"}]


def test_cli_configuration_errors_never_echo_secret_inputs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    import provider_preflight as cli

    def invalid_settings() -> Any:
        raise ValueError("private-credential-input")

    monkeypatch.setattr("app.core.config.Settings", invalid_settings)
    monkeypatch.setattr("sys.argv", ["provider_preflight.py", "--offline"])
    assert cli.main() == 2
    output = capsys.readouterr()
    assert "private-credential-input" not in output.out + output.err
    assert json.loads(output.out)["provider_calls"] == 0
