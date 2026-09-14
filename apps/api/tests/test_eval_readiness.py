"""Offline control tests; fabricated test receipts are not real-model evidence."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

EVALUATION = Path(__file__).resolve().parents[3] / "evaluation"
sys.path.insert(0, str(EVALUATION))
from acceptance.prepare_packet import prepare  # noqa: E402
from build_corpus import validate_database_dsns  # noqa: E402
from provenance import (  # noqa: E402
    EvidenceError,
    digest,
    evaluation_request_digest,
    require_sample_evidence,
    response_evidence,
    validate_runtime,
)
from runtime_client import EvaluationClient, EvaluationStopped  # noqa: E402


def runtime_fixture() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "evaluation_runtime",
        "run_id": str(uuid4()),
        "runtime_id": str(uuid4()),
        "candidate_sha": "a" * 40,
        "candidate_dirty": False,
        "config_digest": "b" * 64,
        "recorded_at": "2026-09-04T00:00:00+00:00",
        "configured_fake": False,
        "effective_fake": False,
        "credential_scope": "evaluation",
        "targets": [
            {
                "slot": "primary",
                "provider": "groq",
                "model": "groq/test",
                "credential_present": True,
            }
        ],
    }


def receipt_fixture(runtime: dict[str, Any], body: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "evaluation_response",
        **{
            key: runtime[key]
            for key in (
                "run_id",
                "runtime_id",
                "candidate_sha",
                "config_digest",
                "candidate_dirty",
                "configured_fake",
                "effective_fake",
                "credential_scope",
            )
        },
        "request_id": str(uuid4()),
        "recorded_at": "2026-09-04T00:01:00+00:00",
        "outcome": "provider",
        "provider": "groq",
        "model": "groq/test",
        "calls": [{"provider": "groq", "model": "groq/test", "status": "completed"}],
        "body_digest": digest(body),
        "request_digest": evaluation_request_digest(
            course_id="course", question="question", mode="qa"
        ),
    }


def test_operator_false_note_cannot_establish_real_quality() -> None:
    with pytest.raises(EvidenceError, match="sunucu kanıtı"):
        require_sample_evidence(
            {
                "fake_provider_declared": False,
                "llm_server_note": "LLM_FAKE_PROVIDER=false",
                "records": [],
            }
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("candidate_dirty", True),
        ("candidate_dirty", None),
        ("effective_fake", True),
        ("effective_fake", None),
        ("configured_fake", True),
        ("credential_scope", "production"),
        ("targets", []),
        ("candidate_sha", "abc"),
        ("config_digest", "invalid"),
        ("runtime_id", None),
    ],
)
def test_unknown_or_unsafe_runtime_never_passes(field: str, value: Any) -> None:
    runtime = runtime_fixture()
    runtime[field] = value
    with pytest.raises(EvidenceError):
        validate_runtime(runtime)


@pytest.mark.parametrize(
    "field,value",
    [
        ("runtime_id", str(uuid4())),
        ("run_id", str(uuid4())),
        ("candidate_sha", "c" * 40),
        ("config_digest", "d" * 64),
        ("body_digest", "e" * 64),
        ("request_id", None),
        ("calls", []),
        ("recorded_at", "2026-09-03T00:00:00+00:00"),
        ("provider", "fake"),
    ],
)
def test_mismatched_or_forged_receipt_never_passes(field: str, value: Any) -> None:
    runtime = runtime_fixture()
    body = {"answer": "source-grounded fixture"}
    receipt = receipt_fixture(runtime, body)
    receipt[field] = value
    evidence = response_evidence(runtime, receipt, body)
    assert evidence["quality_eligible"] is False
    assert evidence["classification"] == "unknown"


@pytest.mark.parametrize("outcome", ["cache", "no_provider", "fake"])
def test_non_provider_outcome_is_not_answer_quality(outcome: str) -> None:
    runtime = runtime_fixture()
    body = {"status": "insufficient_context", "answer": ""}
    receipt = receipt_fixture(runtime, body)
    receipt.update(outcome=outcome, calls=[], provider=None, model=None)
    evidence = response_evidence(runtime, receipt, body)
    assert evidence["classification"] == outcome
    assert evidence["quality_eligible"] is False


def test_actual_completion_and_body_are_bound_before_human_labeling() -> None:
    runtime = runtime_fixture()
    body = {"status": "answered", "answer": "Kaynaklı cevap", "citations": []}
    receipt = receipt_fixture(runtime, body)
    record = {
        "item_id": "TEST",
        "question": "question",
        **body,
        "response_body": body,
        "response_receipt": receipt,
    }
    sample = {"course_id": "course", "runtime_manifest": runtime, "records": [record]}
    require_sample_evidence(sample)
    tampered = copy.deepcopy(sample)
    tampered["records"][0]["answer"] = "Başka cevap"
    with pytest.raises(EvidenceError, match="Etiketlenen"):
        require_sample_evidence(tampered)


def dsns(database: str = "dou015_eval", port: int = 55440) -> tuple[str, str, str]:
    return tuple(
        f"postgresql+psycopg://{role}:private@127.0.0.1:{port}/{database}"
        for role in ("owner", "dou_app", "dou_worker")
    )


def test_three_dsns_preserve_nondefault_port_without_secret_in_identity() -> None:
    identity = validate_database_dsns("dou015_eval", *dsns())
    assert identity == {"host": "127.0.0.1", "port": 55440, "database": "dou015_eval"}
    assert "private" not in json.dumps(identity)


@pytest.mark.parametrize(
    "index,replacement",
    [
        (1, "postgresql+psycopg://dou_app@127.0.0.1:5432/dou015_eval"),
        (2, "postgresql+psycopg://dou_worker@127.0.0.1:55440/dou014_eval"),
        (1, "postgresql+psycopg://owner@127.0.0.1:55440/dou015_eval"),
        (2, "postgresql+psycopg://dou_worker@remote.example:55440/dou015_eval"),
    ],
)
def test_mismatched_connection_rejected_before_database_write(index: int, replacement: str) -> None:
    connections = list(dsns())
    connections[index] = replacement
    with pytest.raises(ValueError):
        validate_database_dsns("dou015_eval", *connections)


@pytest.mark.parametrize(
    "database_name", ["postgres", "production", "dou_synapse", 'dou_eval";DROP DATABASE x;--']
)
def test_non_eval_or_injected_database_name_is_rejected(database_name: str) -> None:
    with pytest.raises(ValueError):
        validate_database_dsns(database_name, *dsns(database_name))


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://127.0.0.1.evil.test",
        "http://user:pass@localhost",
        "file:///tmp/api",
        "http://localhost?forward=external",
    ],
)
def test_eval_secret_never_routes_to_remote_or_ambiguous_url(url: str) -> None:
    with pytest.raises(EvidenceError):
        EvaluationClient(url, "token", secret="fixture-secret")


@pytest.mark.asyncio
async def test_request_budget_and_quota_stop_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"status": "answered"})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )
    async with EvaluationClient("http://localhost", "test", max_requests=1) as client:
        await client.post("/chat", json={})
        with pytest.raises(EvaluationStopped, match="bütçesi"):
            await client.post("/chat", json={})
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 503])
async def test_quota_or_provider_unavailable_stops_immediately(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, json={"error": "not persisted"})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )
    async with EvaluationClient("http://localhost", "test") as client:
        with pytest.raises(EvaluationStopped):
            await client.post("/chat", json={})
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_real_session_reads_server_receipt_and_never_follows_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = runtime_fixture()
    body = {"status": "answered", "answer": "fixture", "citations": []}
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["X-Eval-Runtime-Secret"] == "test-secret"
        if request.method == "GET":
            return httpx.Response(200, json=runtime)
        receipt = base64.urlsafe_b64encode(
            json.dumps(receipt_fixture(runtime, body)).encode()
        ).decode()
        return httpx.Response(200, json=body, headers={"X-Eval-Receipt": receipt})

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(handler), **kw)
    )
    async with EvaluationClient(
        "http://localhost",
        "test",
        secret="test-secret",
        run_id=runtime["run_id"],
        candidate_sha=runtime["candidate_sha"],
        require_real=True,
    ) as client:
        response = await client.post(
            "/courses/course/chat", json={"question": "question", "mode": "qa"}
        )
        assert client.evidence(response)["quality_eligible"] is True
        assert client.client.follow_redirects is False
        assert client.client.trust_env is False
    assert len(calls) == 2


def test_packet_prepares_22_source_hashes_without_approving_or_overwriting(tmp_path: Path) -> None:
    output = tmp_path / "packet"
    packet = prepare(output)
    assert len(packet["sources"]) == 22
    assert packet["source_approval"] == "pending_instructor_review"
    assert packet["real_provider_quality"] == "pending"
    assert packet["grading_run"] == "not_run"
    draft = json.loads((output / "assessment_cases.json").read_text())
    assert len(draft["cases"]) == 5
    assert all(case["expected_score"] is None for case in draft["cases"])
    original = (output / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        prepare(output)
    assert (output / "manifest.json").read_bytes() == original


@pytest.mark.parametrize(
    "field,value",
    [
        ("candidate_dirty", True),
        ("configured_fake", True),
        ("effective_fake", True),
        ("credential_scope", "application"),
    ],
)
def test_contradictory_response_flags_cannot_reuse_safe_manifest(field: str, value: Any) -> None:
    runtime = runtime_fixture()
    receipt = receipt_fixture(runtime, {})
    receipt[field] = value
    assert response_evidence(runtime, receipt, {})["quality_eligible"] is False


def test_unconfigured_transport_target_is_not_real_evidence() -> None:
    runtime = runtime_fixture()
    receipt = receipt_fixture(runtime, {})
    receipt.update(
        provider="gemini",
        model="gemini/other",
        calls=[{"provider": "gemini", "model": "gemini/other", "status": "completed"}],
    )
    assert response_evidence(runtime, receipt, {})["quality_eligible"] is False


def test_one_receipt_cannot_be_repeated_as_many_questions() -> None:
    runtime = runtime_fixture()
    body = {"status": "answered", "answer": "fixture", "citations": []}
    record = {
        "item_id": "one",
        "question": "question",
        **body,
        "response_body": body,
        "response_receipt": receipt_fixture(runtime, body),
    }
    sample = {
        "course_id": "course",
        "runtime_manifest": runtime,
        "records": [record, {**record, "item_id": "two"}],
    }
    with pytest.raises(EvidenceError, match="birden çok"):
        require_sample_evidence(sample)
    record["question"] = "different question"
    sample["records"] = [record]
    with pytest.raises(EvidenceError, match="başka soru"):
        require_sample_evidence(sample)


@pytest.mark.parametrize("host", ["localhost", "[::1]"])
def test_different_loopback_hosts_are_not_silently_same_cluster(host: str) -> None:
    admin, app, worker = dsns()
    worker = worker.replace("127.0.0.1", host)
    with pytest.raises(ValueError):
        validate_database_dsns("dou015_eval", admin, app, worker)


def test_libpq_environment_cannot_override_validated_admin_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import build_corpus

    monkeypatch.setenv("PGHOSTADDR", "192.0.2.1")
    monkeypatch.setenv("PGSERVICE", "production")
    monkeypatch.setenv("PGSERVICEFILE", "/untrusted/service")
    seen = {}
    monkeypatch.setattr(build_corpus.subprocess, "run", lambda *args, **kwargs: seen.update(kwargs))
    build_corpus._psql("postgres", "-c", "SELECT 1", pg_bin="/fixture", admin_dsn=dsns()[0])
    assert seen["env"]["PGHOST"] == "127.0.0.1"
    assert seen["env"]["PGPORT"] == "55440"
    assert not {"PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE"} & set(seen["env"])


@pytest.mark.asyncio
async def test_http_proxy_environment_is_ignored_for_eval_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:8080")
    monkeypatch.delenv("NO_PROXY", raising=False)
    async with EvaluationClient("http://127.0.0.1", "test") as client:
        assert client.client.trust_env is False
        assert not client.client._mounts


@pytest.mark.asyncio
async def test_resume_rebuilds_derived_scores_and_rejects_tampered_visible_answer(
    tmp_path: Path,
) -> None:
    from types import SimpleNamespace

    from evaluate import ProgressLog, RateLimitedRunner, run_e2e_layer
    from goldset import GoldItem

    course_id = uuid4()
    runtime = runtime_fixture()
    body = {"status": "answered", "answer": "fixture", "citations": [], "cached": False}
    receipt = receipt_fixture(runtime, body)
    receipt["request_digest"] = evaluation_request_digest(
        course_id=str(course_id), question="question", mode="qa"
    )
    old = {
        "item_id": "TEST",
        "question": "question",
        **body,
        "response_body": body,
        "response_receipt": receipt,
        "citations_shown": 100,
        "citations_correct": 100,
    }
    progress = ProgressLog(tmp_path / "progress.jsonl")
    progress.append(old)
    item = GoldItem(id="TEST", question="question", category="direct", expected_behavior="answered")
    backend = SimpleNamespace(runtime_manifest=runtime)
    result = await run_e2e_layer([item], backend, RateLimitedRunner(), progress, course_id, "qa")
    assert result[0]["citations_shown"] == result[0]["citations_correct"] == 0
    old["answer"] = "Tampered answer"
    progress.append(old)
    with pytest.raises(EvidenceError, match="görünen cevabı"):
        await run_e2e_layer([item], backend, RateLimitedRunner(), progress, course_id, "qa")


def test_corpus_setup_never_runs_shared_development_database_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import build_corpus

    calls = []
    monkeypatch.setattr(build_corpus, "_psql", lambda *args, **kwargs: calls.append((args, kwargs)))
    build_corpus.prepare_database(
        "dou015_eval", recreate=False, pg_bin="/fixture", admin_dsn=dsns()[0]
    )
    assert not any("local_dev_setup.sql" in str(call) for call in calls)
    assert not any("ALTER ROLE" in str(call) for call in calls)
    assert any('GRANT CONNECT ON DATABASE "dou015_eval"' in str(call) for call in calls)


@pytest.mark.asyncio
async def test_corpus_document_pagination_keeps_every_source() -> None:
    from build_corpus import list_corpus_documents

    def handler(request: httpx.Request) -> httpx.Response:
        page = (
            {"items": [{"file_name": "second.pdf"}], "next_cursor": None}
            if request.url.params.get("cursor")
            else {"items": [{"file_name": "first.pdf"}], "next_cursor": "second-page"}
        )
        return httpx.Response(200, json=page)

    async with httpx.AsyncClient(
        base_url="http://fixture", transport=httpx.MockTransport(handler)
    ) as client:
        documents = await list_corpus_documents(client, uuid4(), {})
    assert [document["file_name"] for document in documents] == ["first.pdf", "second.pdf"]


def test_packet_hash_matches_the_delivered_normalized_cases(tmp_path: Path) -> None:
    output = tmp_path / "packet"
    manifest = prepare(output)
    exported = (output / "assessment_cases.json").read_bytes()
    assert manifest["assessment_cases_sha256"] == hashlib.sha256(exported).hexdigest()


@pytest.mark.parametrize("dirty,candidate", [(False, "c" * 40), (True, "a" * 40)])
def test_packet_rejects_sample_from_another_or_dirty_candidate_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dirty: bool, candidate: str
) -> None:
    from types import SimpleNamespace

    from acceptance import prepare_packet

    from tests.test_faithfulness_scoring import _sample

    payload = _sample()
    for record in payload["records"]:
        record["category"] = "direct"
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        prepare_packet.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(
            stdout=(candidate if command[-1] == "HEAD" else (" M file" if dirty else ""))
        ),
    )
    output = tmp_path / "packet"
    with pytest.raises(EvidenceError):
        prepare(output, sample=sample)
    assert not output.exists()


def test_packet_accepts_same_clean_candidate_without_approving_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from acceptance import prepare_packet

    from tests.test_faithfulness_scoring import _sample

    payload = _sample()
    for record in payload["records"]:
        record["category"] = "direct"
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        prepare_packet.subprocess,
        "run",
        lambda command, **kwargs: SimpleNamespace(stdout="a" * 40 if command[-1] == "HEAD" else ""),
    )
    output = tmp_path / "packet"
    manifest = prepare(output, sample=sample)
    assert manifest["candidate_sha"] == payload["runtime_manifest"]["candidate_sha"]
    assert manifest["candidate_dirty"] is False
    assert manifest["real_provider_quality"] == "pending"
    assert manifest["independent_human_review"] == "pending"
    assert (output / "sample.json").read_bytes() == sample.read_bytes()
    assert "______________" in (output / "labels_etiketleyici_1.md").read_text()


@pytest.mark.parametrize("raw", [b"null", b"[]", b'"text"', b"42", b"true", b"{", b"\xff"])
def test_packet_rejects_invalid_sample_shape_without_creating_output(
    tmp_path: Path, raw: bytes
) -> None:
    sample = tmp_path / "sample.json"
    sample.write_bytes(raw)
    output = tmp_path / "packet"
    with pytest.raises(EvidenceError):
        prepare(output, sample=sample)
    assert not output.exists()
