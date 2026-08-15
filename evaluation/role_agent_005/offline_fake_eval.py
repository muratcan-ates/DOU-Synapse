"""Deterministic candidate-specific T407 evaluation for the 005 course agent.

This harness deliberately uses the repository's fake LLM. It proves only
mechanical properties: role prompt selection, evidence-gate abstention, citation
set membership, Socratic pattern-leak filtering, and source-boundary escaping.
It cannot prove semantic faithfulness, pedagogical quality, or real-provider
behavior; the evidence record says so explicitly.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import socket
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Final
from unittest.mock import patch
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.api.chat import produce_answer
from app.contracts import (
    AnswerStatus,
    AssistantAudience,
    ChatMode,
    RetrievedChunk,
)
from app.core.config import Settings
from app.modules.assessment import socratic
from app.modules.generation.fake import (
    FAKE_PROVIDER,
    FakeLlmClient,
    parse_sources,
)
from app.modules.generation.llm import LlmCompletion, LlmRequest
from app.modules.generation.service import GenerationService
from app.modules.guardrails.chain import GUARDRAIL_CHAIN
from app.modules.guardrails.leakage import detect as detect_leakage

COURSE_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# These are the production files whose bytes decide the mechanics exercised by
# this harness.  Recording only the evaluator and fixture hashes is not enough:
# a dirty checkout could otherwise run a different prompt, evidence gate, or
# guardrail implementation while still claiming the committed candidate SHA.
PRODUCTION_BEHAVIOR_DEPENDENCIES: Final[tuple[str, ...]] = (
    "apps/api/app/api/chat.py",
    "apps/api/app/contracts.py",
    "apps/api/app/core/config.py",
    "apps/api/app/core/llm_json.py",
    "apps/api/app/core/text_tr.py",
    "apps/api/app/modules/assessment/socratic.py",
    "apps/api/app/modules/generation/fake.py",
    "apps/api/app/modules/generation/llm.py",
    "apps/api/app/modules/generation/prompts.py",
    "apps/api/app/modules/generation/service.py",
    "apps/api/app/modules/guardrails/chain.py",
    "apps/api/app/modules/guardrails/citation.py",
    "apps/api/app/modules/guardrails/leakage.py",
    "apps/api/app/modules/guardrails/sanitize.py",
    "apps/api/app/modules/retrieval/scope.py",
    "apps/api/app/schemas/chat.py",
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path}: root must be an object")
    return payload


def _validate_fixture(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if (
        payload.get("schema_version") != 1
        or payload.get("frozen_before_run") is not True
    ):
        raise ValueError("fixture must be schema v1 and frozen_before_run=true")

    thresholds = payload.get("thresholds")
    if not isinstance(thresholds, dict):
        raise TypeError("thresholds must be an object")

    sources = payload.get("sources")
    cases = payload.get("cases")
    if not isinstance(sources, list) or not sources:
        raise ValueError("fixture must contain sources")
    if not isinstance(cases, list) or not cases:
        raise ValueError("fixture must contain cases")

    by_source: dict[str, dict[str, Any]] = {}
    chunk_ids: set[UUID] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise TypeError("every source must be an object")
        source_id = str(source.get("id", ""))
        if not source_id or source_id in by_source:
            raise ValueError(f"duplicate or empty source id: {source_id!r}")
        chunk_id = UUID(str(source["chunk_id"]))
        if chunk_id in chunk_ids:
            raise ValueError(f"duplicate chunk id: {chunk_id}")
        chunk_ids.add(chunk_id)
        expected_hash = str(source.get("sha256", ""))
        actual_hash = _sha256_bytes(str(source["text"]).encode("utf-8"))
        if not SHA256_RE.fullmatch(expected_hash) or expected_hash != actual_hash:
            raise ValueError(f"source hash mismatch: {source_id}")
        by_source[source_id] = source

    case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise TypeError("every case must be an object")
        case_id = str(case.get("id", ""))
        if not case_id or case_id in case_ids:
            raise ValueError(f"duplicate or empty case id: {case_id!r}")
        case_ids.add(case_id)
        if case.get("source_id") not in by_source:
            raise ValueError(f"{case_id}: unknown source")
        if (span := case.get("expected_evidence_span")) and str(span) not in str(
            by_source[str(case["source_id"])]["text"]
        ):
            raise ValueError(
                f"{case_id}: expected evidence span is not frozen source text"
            )
        AssistantAudience(str(case["audience"]))
        ChatMode(str(case["mode"]))
        AnswerStatus(str(case["expected_status"]))
    return by_source


def _chunk(source: dict[str, Any], case: dict[str, Any]) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=UUID(str(source["chunk_id"])),
        document_id=UUID(str(source["document_id"])),
        file_name=str(source["file_name"]),
        page_number=int(source["page_number"]),
        slide_number=None,
        section_title=str(source["section_title"]),
        text=str(source["text"]),
        dense_score=float(case["dense_score"]),
        fts_score=float(case["fts_score"]),
        fused_score=float(case["fused_score"]),
    )


class StaticRetriever:
    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self.chunks = chunks
        self.calls = 0

    async def search(
        self, *, course_id: UUID, query: str, limit: int = 8
    ) -> list[RetrievedChunk]:
        del course_id, query
        self.calls += 1
        return self.chunks[:limit]


class RecordingFake(FakeLlmClient):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[LlmRequest] = []

    async def complete(self, request: LlmRequest) -> LlmCompletion:
        self.requests.append(request)
        return await super().complete(request)


class ForgedCitationFake:
    def __init__(self, forged_chunk_id: UUID) -> None:
        self.forged_chunk_id = forged_chunk_id
        self.calls = 0
        self.requests: list[LlmRequest] = []

    async def complete(self, request: LlmRequest) -> LlmCompletion:
        self.calls += 1
        self.requests.append(request)
        body = {
            "status": AnswerStatus.ANSWERED.value,
            "answer": "Bu cevap doğrulanmamış bir kaynağa dayandığını iddia ediyor.",
            "citations": [
                {
                    "chunk_id": str(self.forged_chunk_id),
                    "claim": "Doğrulanmamış iddia",
                }
            ],
            "hints": [],
        }
        text = json.dumps(body, ensure_ascii=False)
        return LlmCompletion(
            text=text,
            provider=FAKE_PROVIDER,
            model="fake/forged-citation-v1",
            prompt_tokens=len(request.system) // 4 + len(request.user) // 4,
            completion_tokens=len(text) // 4,
        )


def _decision(case: dict[str, Any]) -> socratic.SocraticDecision | None:
    if ChatMode(str(case["mode"])) is not ChatMode.SOCRATIC:
        return None
    first = socratic.advance(None, str(case["question"]))
    expected_stage = str(case.get("socratic_stage", "diagnose"))
    if expected_stage == "diagnose":
        return first
    if expected_stage == "nudge":
        decision = socratic.advance(first.state, str(case.get("student_attempt", "")))
        if decision.stage.value != expected_stage:
            raise AssertionError(
                f"{case['id']}: state machine produced {decision.stage.value}, expected {expected_stage}"
            )
        return decision
    raise ValueError(f"{case['id']}: unsupported fixture stage {expected_stage}")


def _role_contract(audience: AssistantAudience, request: LlmRequest) -> bool:
    system = " ".join(request.system.split())
    if audience is AssistantAudience.STUDENT:
        return all(
            marker in system
            for marker in (
                "ROL — Öğrenci koçu",
                "Sokratik modda doğrudan çözüm vermeme",
                "not, başka öğrencilerin verisi, eğitmen araçları",
            )
        )
    return all(
        marker in system
        for marker in (
            "ROL — Eğitmen asistanı",
            "Yalnız sağlanan ders kaynaklarına dayanarak",
            "Öğrencilerin özel sohbetlerini, kişisel verilerini, cevaplarını",
        )
    )


@contextmanager
def _network_disabled() -> Iterator[None]:
    def blocked(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("network access is forbidden in offline_fake_eval")

    with (
        patch.object(socket.socket, "connect", blocked),
        patch("socket.create_connection", blocked),
    ):
        yield


async def _run_case(
    case: dict[str, Any], source: dict[str, Any], settings: Settings
) -> tuple[dict[str, Any], dict[str, int]]:
    chunk = _chunk(source, case)
    audience = AssistantAudience(str(case["audience"]))
    mode = ChatMode(str(case["mode"]))
    expected_status = AnswerStatus(str(case["expected_status"]))

    if case["kind"] == "forged_citation":
        client: RecordingFake | ForgedCitationFake = ForgedCitationFake(
            UUID(str(case["forged_chunk_id"]))
        )
    else:
        client = RecordingFake()

    outcome = await produce_answer(
        question=str(case["question"]),
        course_id=COURSE_ID,
        mode=mode,
        decision=_decision(case),
        retriever=StaticRetriever([chunk]),
        generator=GenerationService(client, settings),
        guardrails=GUARDRAIL_CHAIN,
        settings=settings,
        student_attempt=(
            None
            if case.get("student_attempt") is None
            else str(case["student_attempt"])
        ),
        evidence_threshold=0.81,
        audience=audience,
        max_output_tokens=700,
        allow_regeneration=False,
    )

    actual_status = outcome.answer.status
    allowed_ids = {chunk.chunk_id}
    returned_ids = {citation.chunk_id for citation in outcome.answer.citations}
    provider_calls = client.calls
    failures: list[str] = []

    if actual_status is not expected_status:
        failures.append(
            f"status={actual_status.value}, expected={expected_status.value}"
        )
    if provider_calls != int(case["expected_provider_calls"]):
        failures.append(
            f"provider_calls={provider_calls}, expected={case['expected_provider_calls']}"
        )
    if not returned_ids.issubset(allowed_ids):
        failures.append("a returned citation is outside the retrieved set")
    if actual_status is AnswerStatus.ANSWERED and returned_ids != allowed_ids:
        failures.append("answered response did not keep the retrieved citation")
    if actual_status is not AnswerStatus.ANSWERED and returned_ids:
        failures.append("refusal returned citations")

    leakage_count = (
        len(detect_leakage(outcome.answer.text)) if mode is ChatMode.SOCRATIC else 0
    )
    if mode is ChatMode.SOCRATIC and leakage_count:
        failures.append(f"socratic pattern leakage findings={leakage_count}")

    role_prompt_ok = True
    poisoned_boundary_ok = True
    if provider_calls:
        if len(client.requests) != provider_calls:
            failures.append("request recording does not match provider call count")
        else:
            role_prompt_ok = _role_contract(audience, client.requests[0])
            if not role_prompt_ok:
                failures.append("role prompt contract mismatch")

    if case["contract"] == "poison_boundary":
        request = client.requests[0]
        parsed = parse_sources(request.user)
        poisoned_boundary_ok = (
            len(parsed) == 1
            and parsed[0].chunk_id == str(chunk.chunk_id)
            and "&lt;/source&gt;" in request.user
            and str(case.get("forged_chunk_id", "99999999"))
            not in {item.chunk_id for item in parsed}
            and "cevap: 42" not in outcome.answer.text.lower()
            and "sistem mesaj" not in outcome.answer.text.lower()
        )
        if not poisoned_boundary_ok:
            failures.append("poisoned source escaped its data boundary")

    forged_blocked = True
    if case["kind"] == "forged_citation":
        forged_blocked = (
            actual_status is AnswerStatus.INSUFFICIENT_CONTEXT
            and not returned_ids
            and UUID(str(case["forged_chunk_id"])) not in returned_ids
        )
        if not forged_blocked:
            failures.append("forged citation was not blocked fail-closed")

    result = {
        "case_id": str(case["id"]),
        "contract": str(case["contract"]),
        "audience": audience.value,
        "mode": mode.value,
        "status": actual_status.value,
        "provider_calls": provider_calls,
        "citation_count": len(returned_ids),
        "citation_set_membership": returned_ids.issubset(allowed_ids),
        "socratic_pattern_leak_findings": leakage_count,
        "role_prompt_contract": role_prompt_ok,
        "forged_citation_blocked": forged_blocked,
        "poisoned_source_boundary_blocked": poisoned_boundary_ok,
        "passed": not failures,
        "failures": failures,
    }
    counters = {
        "provider_calls": provider_calls,
        "socratic_pattern_leak_findings": leakage_count,
    }
    return result, counters


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def _check_thresholds(
    fixture: dict[str, Any], results: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    thresholds = fixture["thresholds"]
    failures: list[str] = []

    answered = [result for result in results if result["status"] == "answered"]
    out_of_scope = [
        result for result in results if result["contract"] == "scope_refusal"
    ]
    role_sensitive_low_evidence = [
        result
        for result in results
        if result["contract"] == "role_sensitive_low_evidence_abstention"
    ]
    pre_generation_refusals = out_of_scope + role_sensitive_low_evidence
    socratic_results = [result for result in results if result["mode"] == "socratic"]
    forged = [
        result for result in results if result["contract"] == "citation_membership"
    ]
    poisoned = [result for result in results if result["contract"] == "poison_boundary"]
    prompted = [result for result in results if result["provider_calls"] > 0]

    metrics: dict[str, Any] = {
        "case_pass": {
            "passed": sum(result["passed"] for result in results),
            "total": len(results),
            "rate": _ratio(sum(result["passed"] for result in results), len(results)),
        },
        "valid_answer_citation_membership": {
            "passed": sum(result["citation_set_membership"] for result in answered),
            "total": len(answered),
            "rate": _ratio(
                sum(result["citation_set_membership"] for result in answered),
                len(answered),
            ),
        },
        "out_of_scope_refusal": {
            "passed": sum(
                result["status"] == "out_of_scope" for result in out_of_scope
            ),
            "total": len(out_of_scope),
            "rate": _ratio(
                sum(result["status"] == "out_of_scope" for result in out_of_scope),
                len(out_of_scope),
            ),
        },
        "role_sensitive_low_evidence_abstention": {
            "passed": sum(
                result["status"] == "out_of_scope"
                for result in role_sensitive_low_evidence
            ),
            "total": len(role_sensitive_low_evidence),
            "rate": _ratio(
                sum(
                    result["status"] == "out_of_scope"
                    for result in role_sensitive_low_evidence
                ),
                len(role_sensitive_low_evidence),
            ),
        },
        "pre_generation_refusal_provider_calls": sum(
            int(result["provider_calls"]) for result in pre_generation_refusals
        ),
        "socratic_pattern_leak_findings": sum(
            int(result["socratic_pattern_leak_findings"]) for result in socratic_results
        ),
        "forged_citation_block": {
            "passed": sum(result["forged_citation_blocked"] for result in forged),
            "total": len(forged),
            "rate": _ratio(
                sum(result["forged_citation_blocked"] for result in forged), len(forged)
            ),
        },
        "poisoned_source_boundary_block": {
            "passed": sum(
                result["poisoned_source_boundary_blocked"] for result in poisoned
            ),
            "total": len(poisoned),
            "rate": _ratio(
                sum(result["poisoned_source_boundary_blocked"] for result in poisoned),
                len(poisoned),
            ),
        },
        "role_prompt_contract": {
            "passed": sum(result["role_prompt_contract"] for result in prompted),
            "total": len(prompted),
            "rate": _ratio(
                sum(result["role_prompt_contract"] for result in prompted),
                len(prompted),
            ),
        },
    }

    gates = {
        "case_pass_rate": metrics["case_pass"]["rate"],
        "valid_answer_citation_membership_rate": metrics[
            "valid_answer_citation_membership"
        ]["rate"],
        "out_of_scope_refusal_rate": metrics["out_of_scope_refusal"]["rate"],
        "role_sensitive_low_evidence_abstention_rate": metrics[
            "role_sensitive_low_evidence_abstention"
        ]["rate"],
        "pre_generation_refusal_provider_calls": metrics[
            "pre_generation_refusal_provider_calls"
        ],
        "socratic_pattern_leak_findings": metrics["socratic_pattern_leak_findings"],
        "forged_citation_block_rate": metrics["forged_citation_block"]["rate"],
        "poisoned_source_boundary_block_rate": metrics[
            "poisoned_source_boundary_block"
        ]["rate"],
        "role_prompt_contract_rate": metrics["role_prompt_contract"]["rate"],
    }
    for name, actual in gates.items():
        expected = thresholds[name]
        if actual != expected:
            failures.append(f"gate {name}={actual!r}, expected={expected!r}")
    return metrics, failures


async def _evaluate(
    fixture: dict[str, Any], by_source: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    settings = Settings(
        _env_file=None,
        environment="local",
        dev_auth_enabled=True,
        llm_fake_provider=True,
        llm_max_retries=0,
        embedding_warmup_enabled=False,
        evidence_threshold=0.81,
    )
    results: list[dict[str, Any]] = []
    with _network_disabled():
        for case in fixture["cases"]:
            result, _ = await _run_case(
                case, by_source[str(case["source_id"])], settings
            )
            results.append(result)
    metrics, gate_failures = _check_thresholds(fixture, results)
    failures = [
        f"{result['case_id']}: {failure}"
        for result in results
        for failure in result["failures"]
    ]
    failures.extend(gate_failures)
    return results, metrics, failures


def _git(args: list[str]) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL
    ).strip()


def _git_blob(candidate_sha: str, relative_path: str) -> bytes | None:
    completed = subprocess.run(
        ["git", "show", f"{candidate_sha}:{relative_path}"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    return completed.stdout if completed.returncode == 0 else None


def _file_binding(candidate_sha: str, relative_path: str) -> dict[str, Any]:
    path = REPO_ROOT / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"binding input is missing: {relative_path}")
    working_sha256 = _sha256_bytes(path.read_bytes())
    candidate_blob = _git_blob(candidate_sha, relative_path)
    candidate_blob_sha256 = (
        None if candidate_blob is None else _sha256_bytes(candidate_blob)
    )
    return {
        "path": relative_path,
        "working_tree_sha256": working_sha256,
        "candidate_blob_sha256": candidate_blob_sha256,
        "matches_candidate_blob": candidate_blob_sha256 == working_sha256,
    }


def _artifact_binding(
    candidate_sha: str, *, evaluator_path: Path, fixture_path: Path
) -> dict[str, Any]:
    current_head = _git(["rev-parse", "HEAD"])
    if current_head != candidate_sha:
        raise RuntimeError(
            f"candidate SHA {candidate_sha} is not checked out (HEAD={current_head})"
        )

    production = [
        _file_binding(candidate_sha, relative_path)
        for relative_path in PRODUCTION_BEHAVIOR_DEPENDENCIES
    ]
    if not all(item["matches_candidate_blob"] for item in production):
        mismatches = [
            str(item["path"])
            for item in production
            if not item["matches_candidate_blob"]
        ]
        raise RuntimeError(
            "production behavior differs from the claimed candidate SHA: "
            + ", ".join(mismatches)
        )

    evaluation_artifacts = [
        _file_binding(candidate_sha, _relative(evaluator_path)),
        _file_binding(candidate_sha, _relative(fixture_path)),
    ]
    return {
        "candidate_sha": candidate_sha,
        "observed_head_sha": current_head,
        "production_behavior_exact_candidate": True,
        "production_behavior_dependencies": production,
        "evaluation_artifacts": evaluation_artifacts,
        "evaluation_artifacts_exact_candidate": all(
            item["matches_candidate_blob"] for item in evaluation_artifacts
        ),
    }


def _relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _record_candidate_identity(value: str) -> str:
    if value == "SELF" or GIT_SHA_RE.fullmatch(value):
        return value
    raise ValueError(
        "record candidate identity must be SELF or a full lowercase Git SHA"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    candidate_group = parser.add_mutually_exclusive_group(required=True)
    candidate_group.add_argument("--candidate-sha")
    candidate_group.add_argument(
        "--base-sha",
        dest="candidate_sha",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--record-candidate-sha",
        default=None,
        help=(
            "Candidate identity written at the report root. Use SELF when the "
            "append-only report will be introduced by the reviewed final commit; "
            "the exact evaluated Git SHA remains in artifact_binding."
        ),
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help=(
            "Permit a provisional dirty-tree run. Production behavior files must "
            "still match the candidate blobs exactly; release evidence must omit this flag."
        ),
    )
    args = parser.parse_args()

    if not GIT_SHA_RE.fullmatch(args.candidate_sha):
        parser.error("--candidate-sha must be a full 40-character lowercase Git SHA")
    record_candidate_sha = _record_candidate_identity(
        args.record_candidate_sha or args.candidate_sha
    )
    cases_path = args.cases.resolve()
    output_path = args.output.resolve()
    if output_path.exists():
        parser.error(f"append-only evidence already exists: {output_path}")

    dirty_paths = [line for line in _git(["status", "--short"]).splitlines() if line]
    if dirty_paths and not args.allow_dirty:
        parser.error(
            "working tree is dirty; commit the final candidate for release evidence "
            "or use --allow-dirty for explicitly provisional local evidence"
        )

    binding = _artifact_binding(
        args.candidate_sha,
        evaluator_path=Path(__file__),
        fixture_path=cases_path,
    )

    fixture_bytes = cases_path.read_bytes()
    fixture = _load_json(cases_path)
    by_source = _validate_fixture(fixture)
    results, metrics, failures = asyncio.run(_evaluate(fixture, by_source))

    command = (
        "PYTHONDONTWRITEBYTECODE=1 apps/api/.venv/bin/python "
        f"{_relative(Path(__file__))} --cases {_relative(cases_path)} "
        f"--output {_relative(output_path)} --candidate-sha {args.candidate_sha}"
    )
    if record_candidate_sha != args.candidate_sha:
        command += f" --record-candidate-sha {record_candidate_sha}"
    if args.allow_dirty:
        command += " --allow-dirty"
    source_digests = {
        source_id: str(source["sha256"])
        for source_id, source in sorted(by_source.items())
    }
    record = {
        "schema_version": 1,
        "change_id": "005-role-aware-course-agent",
        "task": "T407",
        "candidate_sha": record_candidate_sha,
        "observed_head_sha": binding["observed_head_sha"],
        "working_tree_dirty": bool(dirty_paths),
        "working_tree_path_count": len(dirty_paths),
        "release_binding_eligible": (
            not dirty_paths and binding["evaluation_artifacts_exact_candidate"]
        ),
        "evaluated_state": (
            "clean exact candidate SHA"
            if not dirty_paths and binding["evaluation_artifacts_exact_candidate"]
            else (
                "provisional dirty-tree run: production behavior is byte-for-byte bound "
                "to candidate SHA; evaluator and fixture are bound by recorded hashes"
            )
        ),
        "captured_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "environment": "local, network-blocked, database-free deterministic fake provider",
        "evidence_label": "fake-provider",
        "result": "pass" if not failures else "fail",
        "command": command,
        "fixture": {
            "path": _relative(cases_path),
            "sha256": _sha256_bytes(fixture_bytes),
            "set": fixture["set"],
            "frozen_before_run": fixture["frozen_before_run"],
            "source_sha256": source_digests,
        },
        "evaluator": {
            "path": _relative(Path(__file__)),
            "sha256": _sha256_bytes(Path(__file__).read_bytes()),
        },
        "artifact_binding": binding,
        "thresholds_declared_before_run": fixture["thresholds"],
        "metrics": metrics,
        "cases": results,
        "failures": failures,
        "proves": [
            "student and instructor server-selected prompt contracts are mechanically distinct",
            "scope and role-sensitive low-evidence probes abstain before a provider call",
            "returned citation identifiers belong to the retrieved set",
            "a forged citation is dropped and the answer fails closed",
            "source tag injection remains escaped as data and creates no second parsed source",
            "the deterministic fake Socratic outputs trigger no known pattern-leak detector",
        ],
        "not_run": [
            "real provider or exact production model",
            "semantic citation faithfulness or claim entailment",
            "human pedagogical quality, usefulness, fairness, or instructor acceptance",
            "real embedding retrieval, PostgreSQL, Supabase, staging, canary, load, or production",
            "role-based database authorization; role-sensitive probes here test only low-evidence abstention mechanics",
        ],
        "limitations": (
            "Fake-provider output is mechanical evidence only, not pedagogical or real-model proof. "
            "Expected evidence spans are frozen-source membership checks, not semantic entailment. "
            "A dirty run is provisional even when every production behavior dependency matches "
            "the candidate blob. Release verification must rerun without --allow-dirty after the "
            "evaluator and fixture are committed on the final immutable candidate SHA."
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(
        f"T407 offline/fake: {metrics['case_pass']['passed']}/{metrics['case_pass']['total']} "
        f"cases; result={record['result']}; evidence={_relative(output_path)}"
    )
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
