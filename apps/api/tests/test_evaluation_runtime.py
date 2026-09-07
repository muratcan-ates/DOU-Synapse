"""Real HTTP contracts over injected transports; no real-provider quality claim."""

from __future__ import annotations

import base64
import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.chat import reset_rate_limit, set_pipeline
from app.core.config import get_settings
from app.core.db import dispose_engine
from app.core.provider_config import canonical_digest
from app.core.provider_evidence import provider_calls
from app.modules.generation.llm import LiteLlmClient
from app.modules.generation.service import GenerationService
from tests.conftest import UserFactory
from tests.factories import (
    FakeCitationGuardrail,
    Pipeline,
    create_course,
    make_chunk,
    sourced_answer,
)

SECRET = "receipt-auth-test-secret"
KEY = "evaluation-provider-test-secret"
SHA = "a" * 40
EVALUATION_ROOT = Path(__file__).resolve().parents[3] / "evaluation"


def create_app() -> FastAPI:
    from app.main import create_app as factory

    return factory()


@pytest.fixture
def eval_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name, value in {
        "EVAL_RUNTIME_ENABLED": "true",
        "EVAL_RUNTIME_SECRET": SECRET,
        "EVAL_LLM_PROVIDER": "groq",
        "EVAL_LLM_API_KEY": KEY,
        "LLM_PRIMARY_MODEL": "groq/openai/gpt-oss-120b",
        "LLM_FALLBACK_MODEL": "",
        "LLM_FAKE_PROVIDER": "false",
        "EMBEDDING_WARMUP_ENABLED": "false",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        "app.api.evaluation_runtime.candidate_identity",
        lambda: {"candidate_sha": SHA, "candidate_dirty": False},
    )
    get_settings.cache_clear()
    reset_rate_limit()
    yield
    get_settings.cache_clear()
    reset_rate_limit()
    set_pipeline()


@pytest.fixture
async def eval_client(clean_tables: None, eval_env: None) -> AsyncIterator[AsyncClient]:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    await dispose_engine()


def eval_headers(run_id: str) -> dict[str, str]:
    return {"X-Eval-Runtime-Secret": SECRET, "X-Eval-Run-Id": run_id}


def receipt_of(response: Any) -> dict[str, Any]:
    value = response.headers["X-Eval-Receipt"]
    return json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))


async def test_disabled_runtime_is_hidden_even_with_supplied_secret(client: AsyncClient) -> None:
    response = await client.get(
        f"/internal/evaluation/runtime?run_id={uuid4()}", headers={"X-Eval-Runtime-Secret": SECRET}
    )
    assert response.status_code == 404


@pytest.mark.parametrize("supplied", [None, "wrong", SECRET[:-1]])
async def test_eval_endpoint_rejects_wrong_or_missing_secret(
    eval_client: AsyncClient, supplied: str | None
) -> None:
    headers = {} if supplied is None else {"X-Eval-Runtime-Secret": supplied}
    response = await eval_client.get(
        f"/internal/evaluation/runtime?run_id={uuid4()}", headers=headers
    )
    assert response.status_code == 403
    assert KEY not in response.text
    assert SECRET not in response.text


async def test_unset_secret_closes_enabled_eval_endpoint(
    eval_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EVAL_RUNTIME_SECRET", "")
    get_settings.cache_clear()
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.get(
            f"/internal/evaluation/runtime?run_id={uuid4()}",
            headers={"X-Eval-Runtime-Secret": SECRET},
        )
    assert response.status_code == 404


async def test_non_loopback_peer_rejected(eval_env: None) -> None:
    transport = ASGITransport(app=create_app(), client=("203.0.113.4", 1234))
    async with AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.get(
            f"/internal/evaluation/runtime?run_id={uuid4()}",
            headers={"X-Eval-Runtime-Secret": SECRET},
        )
    assert response.status_code == 403


async def test_manifest_identity_is_stable_secret_free_and_hidden(eval_client: AsyncClient) -> None:
    run_id = str(uuid4())
    url = f"/internal/evaluation/runtime?run_id={run_id}"
    first = await eval_client.get(url, headers=eval_headers(run_id))
    again = await eval_client.get(url, headers=eval_headers(run_id))
    assert first.status_code == 200, first.text
    assert first.json() == again.json()
    body = first.json()
    assert body["kind"] == "evaluation_runtime"
    assert body["candidate_sha"] == SHA and body["candidate_dirty"] is False
    assert body["configured_fake"] is False and body["effective_fake"] is False
    assert body["credential_scope"] == "evaluation"
    assert body["config_digest"] == canonical_digest(body["configuration"])
    assert KEY not in first.text and SECRET not in first.text
    assert "postgresql" not in first.text
    # Schema visibility is independent of the platform-admin HTTP access gate.
    paths = create_app().openapi()["paths"]
    assert not any(path.startswith("/internal/evaluation") for path in paths)
    chat_operation = paths["/courses/{course_id}/chat"]["post"]
    assert not any(
        parameter["name"].startswith("X-Eval") for parameter in chat_operation["parameters"]
    )


async def test_runtime_config_change_requires_restart(
    eval_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "llm_temperature", 0.9)
    response = await eval_client.get(
        f"/internal/evaluation/runtime?run_id={uuid4()}", headers={"X-Eval-Runtime-Secret": SECRET}
    )
    assert response.status_code == 403


async def test_real_chat_observes_transport_then_distinguishes_cache_and_no_provider(
    eval_client: AsyncClient,
    users: UserFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = users.auth(await users.create("eval-owner@example.com"))
    course_id = await create_course(eval_client, auth, "EVAL015")
    pipeline = Pipeline()
    chunk = pipeline.serve(course_id, make_chunk())
    calls: list[dict[str, Any]] = []

    async def complete(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        payload = {
            "status": "answered",
            "answer": "Deadlock süreçlerin birbirini beklemesidir.",
            "citations": [{"chunk_id": str(chunk.chunk_id), "quote": chunk.text[:100]}],
        }
        return {
            "choices": [{"message": {"content": json.dumps(payload)}}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 20},
        }

    set_pipeline(
        retriever_factory=lambda session: pipeline.retriever,
        generator=GenerationService(llm=LiteLlmClient(get_settings(), completion_fn=complete)),
        guardrails=[FakeCitationGuardrail()],
    )
    run_id = str(uuid4())
    manifest = (
        await eval_client.get(
            f"/internal/evaluation/runtime?run_id={run_id}", headers=eval_headers(run_id)
        )
    ).json()
    headers = auth | eval_headers(run_id)
    first = await eval_client.post(
        f"/courses/{course_id}/chat", headers=headers, json={"question": "Deadlock nedir?"}
    )
    assert first.status_code == 200, first.text
    receipt = receipt_of(first)
    assert receipt["outcome"] == "provider"
    assert receipt["calls"] == [
        {"provider": "groq", "model": get_settings().llm_primary_model, "status": "completed"}
    ]
    assert receipt["body_digest"] == canonical_digest(first.json())
    assert receipt["runtime_id"] == manifest["runtime_id"]
    assert receipt["recorded_at"] >= manifest["recorded_at"]
    assert calls[0]["api_key"] == KEY
    assert KEY not in json.dumps(receipt) and SECRET not in json.dumps(receipt)
    assert first.json()["answer"] not in json.dumps(receipt)
    # Cross-lane agreement: actual API receipt is accepted by the common harness validator.
    monkeypatch.syspath_prepend(str(EVALUATION_ROOT))
    from provenance import response_evidence

    expected_request = {
        "course_id": str(course_id),
        "question": "Deadlock nedir?",
        "mode": "qa",
        "session_id": None,
        "student_attempt": None,
    }
    assert (
        response_evidence(manifest, receipt, first.json(), expected_request)["quality_eligible"]
        is True
    )
    for field in expected_request:
        changed_request = expected_request | {field: "different"}
        assert (
            response_evidence(manifest, receipt, first.json(), changed_request)["quality_eligible"]
            is False
        )
    tampered = dict(first.json(), answer="different content")
    assert response_evidence(manifest, receipt, tampered)["quality_eligible"] is False

    cached = await eval_client.post(
        f"/courses/{course_id}/chat", headers=headers, json={"question": "Deadlock nedir?"}
    )
    assert cached.status_code == 200, cached.text
    cached_receipt = receipt_of(cached)
    assert cached_receipt["outcome"] == "cache"
    assert cached_receipt["calls"] == []
    assert len(calls) == 1
    assert response_evidence(manifest, cached_receipt, cached.json())["quality_eligible"] is False

    pipeline.retriever.by_course[course_id] = []
    refused = await eval_client.post(
        f"/courses/{course_id}/chat", headers=headers, json={"question": "Farklı konu nedir?"}
    )
    assert refused.status_code == 200, refused.text
    assert receipt_of(refused)["outcome"] == "no_provider"
    assert receipt_of(refused)["calls"] == []
    assert provider_calls.get() is None


async def test_claimed_provider_metadata_is_not_transport_evidence(
    eval_client: AsyncClient,
    users: UserFactory,
) -> None:
    auth = users.auth(await users.create("eval-stub@example.com"))
    course_id = await create_course(eval_client, auth, "STUB015")
    pipeline = Pipeline()
    chunk = pipeline.serve(course_id, make_chunk())
    answer = sourced_answer(chunk)
    answer.provider = "groq"
    answer.model = get_settings().llm_primary_model
    pipeline.answers(answer)
    response = await eval_client.post(
        f"/courses/{course_id}/chat",
        json={"question": "Nedir?"},
        headers=auth | eval_headers(str(uuid4())),
    )
    assert response.status_code == 200, response.text
    receipt = receipt_of(response)
    assert receipt["outcome"] == "no_provider" and receipt["calls"] == []
    assert receipt["provider"] is None


async def test_normal_chat_has_no_eval_metadata_and_bad_eval_auth_never_calls_model(
    eval_client: AsyncClient,
    users: UserFactory,
) -> None:
    auth = users.auth(await users.create("normal@example.com"))
    course_id = await create_course(eval_client, auth, "NORMAL015")
    pipeline = Pipeline()
    chunk = pipeline.serve(course_id, make_chunk())
    pipeline.answers(sourced_answer(chunk))
    bad = await eval_client.post(
        f"/courses/{course_id}/chat",
        json={"question": "Nedir?"},
        headers=auth | {"X-Eval-Runtime-Secret": "wrong"},
    )
    assert bad.status_code == 403
    assert pipeline.generator.calls == 0
    normal = await eval_client.post(
        f"/courses/{course_id}/chat", json={"question": "Nedir?"}, headers=auth
    )
    assert normal.status_code == 200, normal.text
    assert "X-Eval-Receipt" not in normal.headers
    assert provider_calls.get() is None
