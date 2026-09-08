"""Question authoring: real API/DB boundaries and draft-to-published journey."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api import questions as question_api
from app.core.config import Settings, get_settings
from app.models.assessment import QuestionType
from app.modules.assessment import question_gen
from app.schemas.assessment import OpenPayload, normalized_rubric
from tests.conftest import UserFactory
from tests.factories import (
    DEADLOCK_TEXTS,
    ESSAY_PAYLOAD,
    FakeCompletion,
    FakeRetriever,
    _mcq_response,
    create_course,
    create_topic,
    enroll_student,
    mcq_payload,
    retrieved,
    seed_document,
    seed_question,
    short_answer_payload,
)


@dataclass
class AuthoringPool:
    course: UUID
    topic: UUID
    outcome: str
    question: UUID
    chunks: list[UUID]
    instructor_id: UUID
    instructor: dict[str, str]
    student_id: UUID
    student: dict[str, str]

    @property
    def url(self) -> str:
        return f"/courses/{self.course}/questions"

    def edit(self, **changes: Any) -> dict[str, Any]:
        return {
            "payload": mcq_payload(self.chunks),
            "learning_outcome_id": self.outcome,
            "difficulty": "easy",
            **changes,
        }


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("QUESTION_AUTHORING_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def pool(client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine) -> AuthoringPool:
    instructor_id = await users.create("author@dogus.edu.tr")
    instructor = users.auth(instructor_id)
    student_id = await users.create("student@dogus.edu.tr")
    course = await create_course(client, instructor, "EDIT101")
    await enroll_student(client, instructor, course, "student@dogus.edu.tr")
    topic = await create_topic(client, instructor, course, "Deadlock")
    document = await seed_document(
        admin_engine, course_id=course, uploaded_by=instructor_id, passages=DEADLOCK_TEXTS
    )
    outcome = await client.post(
        f"/courses/{course}/learning-outcomes",
        json={
            "code": "CO1",
            "description": "Kilitlenme koşullarını açıklar",
            "topic_id": str(topic),
        },
        headers=instructor,
    )
    assert outcome.status_code == 201, outcome.text
    question = await seed_question(
        admin_engine,
        course_id=course,
        topic_id=topic,
        source_chunk_id=document.chunk_ids[0],
        payload=mcq_payload(document.chunk_ids),
        created_by=instructor_id,
    )
    return AuthoringPool(
        course,
        topic,
        outcome.json()["id"],
        question,
        document.chunk_ids,
        instructor_id,
        instructor,
        student_id,
        users.auth(student_id),
    )


async def test_classified_generate_edit_approve_publish(
    client: AsyncClient, pool: AuthoringPool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """All assessment mutations pass through API; only source material is seeded."""
    completion = FakeCompletion(_mcq_response(pool.chunks[0]))
    monkeypatch.setattr(question_gen, "resolve_completion", lambda *_: completion)
    monkeypatch.setattr(
        question_gen,
        "resolve_retriever",
        lambda *_: FakeRetriever(retrieved(pool.chunks, DEADLOCK_TEXTS)),
    )
    generated = await client.post(
        pool.url + "/generate",
        headers=pool.instructor,
        json={
            "topic_id": str(pool.topic),
            "count": 1,
            "learning_outcome_id": pool.outcome,
            "difficulty": "easy",
        },
    )
    assert generated.status_code == 200, generated.text
    assert generated.json()["accepted"] == 1
    question = generated.json()["questions"][0]
    assert question["learning_outcome_id"] == pool.outcome
    assert question["difficulty"] == "easy"
    assert question["status"] == "draft"
    question_id = question["id"]
    payload = question["payload"]
    payload["stem"] = "Deadlock koşulları arasında hangisi bulunmaz?"
    edited = await client.post(
        pool.url + f"/{question_id}/draft",
        headers=pool.instructor,
        json=pool.edit(payload=payload),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["payload"]["stem"] == payload["stem"]
    approved = await client.post(
        pool.url + f"/{question_id}/approve",
        headers=pool.instructor,
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["learning_outcome_id"] == pool.outcome
    blueprint = await client.post(
        f"/courses/{pool.course}/blueprints",
        headers=pool.instructor,
        json={
            "title": "Kilitlenme sınavı",
            "duration_minutes": 30,
            "cells": [
                {
                    "learning_outcome_id": pool.outcome,
                    "difficulty": "easy",
                    "question_type": "mcq",
                    "question_count": 1,
                    "points_per_question": 100,
                }
            ],
        },
    )
    assert blueprint.status_code == 201, blueprint.text
    bp_url = f"/courses/{pool.course}/blueprints/{blueprint.json()['id']}/versions"
    version = await client.post(bp_url, headers=pool.instructor)
    assert version.status_code == 201, version.text
    version_url = bp_url + f"/{version.json()['id']}"
    items = await client.post(
        version_url + "/items",
        headers=pool.instructor,
        json=[{"question_id": question_id}],
    )
    assert items.status_code == 200, items.text
    published = await client.post(version_url + "/publish", headers=pool.instructor)
    assert published.status_code == 200, published.text
    assert published.json()["version"]["status"] == "published"
    student_pool = await client.get(pool.url, headers=pool.student)
    public_question = student_pool.json()["items"][0]
    assert public_question["learning_outcome_id"] == pool.outcome
    assert "answer_key" not in public_question["payload"]
    assert "distractor_sources" not in public_question["payload"]


async def test_flag_default_and_rollback(
    client: AsyncClient, pool: AuthoringPool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("QUESTION_AUTHORING_ENABLED")
    assert Settings(_env_file=None).question_authoring_enabled is False
    get_settings.cache_clear()
    capability = await client.get(pool.url + "/authoring", headers=pool.instructor)
    assert capability.json() == {"enabled": False}
    for url, body in [
        (pool.url + f"/{pool.question}/draft", pool.edit()),
        (
            pool.url + "/generate",
            {
                "topic_id": str(pool.topic),
                "count": 1,
                "learning_outcome_id": pool.outcome,
                "difficulty": "easy",
            },
        ),
    ]:
        response = await client.post(url, json=body, headers=pool.instructor)
        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] == "question_authoring_disabled"
    completion = FakeCompletion(_mcq_response(pool.chunks[0]))
    monkeypatch.setattr(question_gen, "resolve_completion", lambda *_: completion)
    monkeypatch.setattr(
        question_gen,
        "resolve_retriever",
        lambda *_: FakeRetriever(retrieved(pool.chunks, DEADLOCK_TEXTS)),
    )
    legacy = await client.post(
        pool.url + "/generate",
        json={"topic_id": str(pool.topic), "count": 1},
        headers=pool.instructor,
    )
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["accepted"] == 1
    assert legacy.json()["questions"][0]["learning_outcome_id"] is None


async def test_course_scoped_authorization(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine, pool: AuthoringPool
) -> None:
    outsider_id = await users.create("admin@dogus.edu.tr")
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO platform_admins (user_id) VALUES (:id)"), {"id": outsider_id}
        )
    for headers, expected in [(pool.student, 403), (users.auth(outsider_id), 404)]:
        edit = await client.post(
            pool.url + f"/{pool.question}/draft", headers=headers, json=pool.edit()
        )
        assert edit.status_code == expected, edit.text
        capability = await client.get(pool.url + "/authoring", headers=headers)
        assert capability.status_code == expected, capability.text
    other = await create_course(client, pool.student, "EDIT102")
    # Instructor in a different course is still a student here.
    denied = await client.post(
        pool.url + f"/{pool.question}/draft", headers=pool.student, json=pool.edit()
    )
    assert denied.status_code == 403
    hidden = await client.post(
        f"/courses/{other}/questions/{pool.question}/draft",
        headers=pool.student,
        json=pool.edit(),
    )
    assert hidden.status_code == 404


@pytest.mark.parametrize(
    "classification",
    [
        {"learning_outcome_id": None, "difficulty": "easy"},
        {"learning_outcome_id": str(uuid4()), "difficulty": None},
    ],
)
async def test_partial_classification_rejected(
    client: AsyncClient, pool: AuthoringPool, classification: dict[str, Any]
) -> None:
    for url, body in [
        (pool.url + f"/{pool.question}/draft", pool.edit(**classification)),
        (pool.url + "/generate", {"topic_id": str(pool.topic), **classification}),
    ]:
        response = await client.post(url, headers=pool.instructor, json=body)
        assert response.status_code == 422, response.text


async def test_outcome_and_distractor_course_boundaries(
    client: AsyncClient, admin_engine: AsyncEngine, pool: AuthoringPool
) -> None:
    other = await create_course(client, pool.instructor, "EDIT103")
    other_topic = await create_topic(client, pool.instructor, pool.course, "Bellek")
    other_document = await seed_document(
        admin_engine, course_id=other, uploaded_by=pool.instructor_id, passages=DEADLOCK_TEXTS
    )
    for course_id, topic_id, expected in [(other, None, 404), (pool.course, other_topic, 422)]:
        outcome = await client.post(
            f"/courses/{course_id}/learning-outcomes",
            headers=pool.instructor,
            json={
                "code": "CO2",
                "description": "Başka kazanım",
                "topic_id": str(topic_id) if topic_id else None,
            },
        )
        assert outcome.status_code == 201, outcome.text
        for url, body in [
            (
                pool.url + f"/{pool.question}/draft",
                pool.edit(learning_outcome_id=outcome.json()["id"]),
            ),
            (
                pool.url + "/generate",
                {
                    "topic_id": str(pool.topic),
                    "difficulty": "easy",
                    "learning_outcome_id": outcome.json()["id"],
                },
            ),
        ]:
            response = await client.post(url, headers=pool.instructor, json=body)
            assert response.status_code == expected, response.text
    wrong_source = mcq_payload(pool.chunks)
    wrong_source["distractor_sources"]["A"] = str(other_document.chunk_ids[0])
    response = await client.post(
        pool.url + f"/{pool.question}/draft",
        headers=pool.instructor,
        json=pool.edit(payload=wrong_source),
    )
    assert response.status_code == 422
    stored = await client.get(pool.url, headers=pool.instructor)
    assert stored.json()["items"][0]["payload"] == mcq_payload(pool.chunks)


@pytest.mark.parametrize(
    "field",
    ["status", "type", "source_chunk_id", "reviewed_by", "course_id", "topic_id", "created_by"],
)
async def test_structural_fields_rejected(
    client: AsyncClient, pool: AuthoringPool, field: str
) -> None:
    response = await client.post(
        pool.url + f"/{pool.question}/draft",
        headers=pool.instructor,
        json=pool.edit(**{field: str(uuid4())}),
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("review", ["approve", "reject"])
async def test_reviewed_question_cannot_be_edited(
    client: AsyncClient, pool: AuthoringPool, review: str
) -> None:
    reviewed = await client.post(pool.url + f"/{pool.question}/{review}", headers=pool.instructor)
    assert reviewed.status_code == 200
    response = await client.post(
        pool.url + f"/{pool.question}/draft", headers=pool.instructor, json=pool.edit()
    )
    assert response.status_code == 409


async def test_session_referenced_draft_cannot_be_edited(
    client: AsyncClient, pool: AuthoringPool, admin_engine: AsyncEngine
) -> None:
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO exam_sessions (course_id, user_id, mode, question_ids) "
                "VALUES (:course, :student, 'practice', ARRAY[CAST(:question AS uuid)])"
            ),
            {"course": pool.course, "student": pool.student_id, "question": pool.question},
        )
    response = await client.post(
        pool.url + f"/{pool.question}/draft", headers=pool.instructor, json=pool.edit()
    )
    assert response.status_code == 409, response.text


@pytest.mark.parametrize(
    "kind,payload",
    [
        (QuestionType.OPEN, ESSAY_PAYLOAD),
        (QuestionType.OPEN, short_answer_payload()),
        (
            QuestionType.CODE_TRACE,
            {
                "language": "python",
                "code": "print(1)",
                "prompt": "Kodun çıktısı nedir?",
                "answer_key": "1",
                "rubric": [{"point": "Çıktıyı doğru belirtir", "weight": 100}],
            },
        ),
        (
            QuestionType.BUG_HUNT,
            {
                "language": "python",
                "code": "print(x)",
                "prompt": "Koddaki hatayı bulun.",
                "answer_key": {"line": 1, "bug_type": "NameError", "fix_summary": "x tanımlanmalı"},
                "rubric": [{"point": "Tanımsız değişkeni tespit eder", "weight": 100}],
            },
        ),
    ],
)
async def test_all_question_payloads_round_trip(
    client: AsyncClient,
    pool: AuthoringPool,
    admin_engine: AsyncEngine,
    kind: QuestionType,
    payload: dict[str, Any],
) -> None:
    question = await seed_question(
        admin_engine,
        course_id=pool.course,
        topic_id=pool.topic,
        source_chunk_id=pool.chunks[0],
        question_type=kind,
        payload=payload,
    )
    response = await client.post(
        pool.url + f"/{question}/draft", headers=pool.instructor, json=pool.edit(payload=payload)
    )
    assert response.status_code == 200, response.text
    assert response.json()["type"] == kind
    assert response.json()["learning_outcome_id"] == pool.outcome
    assert response.json()["payload"]["answer_key"] == payload["answer_key"]
    clear = await client.post(
        pool.url + f"/{question}/draft",
        headers=pool.instructor,
        json=pool.edit(payload=payload, learning_outcome_id=None, difficulty=None),
    )
    assert clear.status_code == 200, clear.text
    assert clear.json()["learning_outcome_id"] is None


@pytest.mark.parametrize(
    "mutation",
    ["empty_rubric", "bad_sum", "blank_point", "long_key_point", "blank_prompt", "unknown"],
)
async def test_invalid_essay_is_atomic(
    client: AsyncClient, pool: AuthoringPool, admin_engine: AsyncEngine, mutation: str
) -> None:
    question = await seed_question(
        admin_engine,
        course_id=pool.course,
        topic_id=pool.topic,
        source_chunk_id=pool.chunks[0],
        question_type=QuestionType.OPEN,
        payload=ESSAY_PAYLOAD,
    )
    payload = deepcopy(ESSAY_PAYLOAD)
    if mutation == "empty_rubric":
        payload["rubric"] = []
    elif mutation == "bad_sum":
        payload["rubric"][0]["weight"] = 40
    elif mutation == "blank_point":
        payload["rubric"][0]["point"] = " "
    elif mutation == "long_key_point":
        payload["key_points"] = ["x" * 1001]
    elif mutation == "blank_prompt":
        payload["prompt"] = " " * 10
    else:
        payload["new_unknown_field"] = "should not be ignored"
    response = await client.post(
        pool.url + f"/{question}/draft", headers=pool.instructor, json=pool.edit(payload=payload)
    )
    assert response.status_code == 422, response.text
    listed = await client.get(pool.url, headers=pool.instructor)
    stored = next(item for item in listed.json()["items"] if item["id"] == str(question))
    assert stored["payload"] == ESSAY_PAYLOAD
    assert stored["learning_outcome_id"] is None


def test_legacy_rubric_read_still_normalizes() -> None:
    payload = deepcopy(ESSAY_PAYLOAD)
    payload["rubric"][0]["weight"] = 40
    parsed = OpenPayload.model_validate(payload)
    assert sum(item.weight for item in normalized_rubric(parsed.rubric)) == 100


@pytest.mark.parametrize("first", ["draft", "approve"])
async def test_edit_and_approve_serialize(
    client: AsyncClient, pool: AuthoringPool, monkeypatch: pytest.MonkeyPatch, first: str
) -> None:
    """Hold the first request after its row lock; second must observe its commit."""
    acquired = asyncio.Event()
    release = asyncio.Event()
    second_entered = asyncio.Event()
    second_loaded = asyncio.Event()
    load = question_api._load_question
    calls = 0

    async def held_load(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        index = calls
        if index == 2:
            second_entered.set()
        result = await load(*args, **kwargs)
        if index == 2:
            second_loaded.set()
        if index == 1:
            acquired.set()
            await asyncio.wait_for(release.wait(), timeout=5)
        return result

    monkeypatch.setattr(question_api, "_load_question", held_load)
    second = "approve" if first == "draft" else "draft"

    async def request(action: str) -> Any:
        body = {"json": pool.edit()} if action == "draft" else {}
        return await client.post(
            pool.url + f"/{pool.question}/{action}", headers=pool.instructor, **body
        )

    first_task = asyncio.create_task(request(first))
    await asyncio.wait_for(acquired.wait(), timeout=5)
    second_task = asyncio.create_task(request(second))
    await asyncio.wait_for(second_entered.wait(), timeout=5)
    try:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(second_loaded.wait(), timeout=0.15)
    finally:
        release.set()
    first_response, second_response = await asyncio.gather(first_task, second_task)
    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == (409 if first == "approve" else 200)
    listed = await client.get(pool.url, headers=pool.instructor)
    question = listed.json()["items"][0]
    assert question["status"] == "approved"
    assert question["learning_outcome_id"] == (None if first == "approve" else pool.outcome)


@pytest.mark.parametrize("change", ["omit", "unchanged", "mutate", "nested_mutate"])
async def test_existing_unknown_metadata_is_preserved(
    client: AsyncClient, pool: AuthoringPool, admin_engine: AsyncEngine, change: str
) -> None:
    original = mcq_payload(pool.chunks)
    original["legacy_provenance"] = {"source_version": 2}
    original["options"][0]["legacy_label"] = "retained"
    question = await seed_question(
        admin_engine,
        course_id=pool.course,
        topic_id=pool.topic,
        source_chunk_id=pool.chunks[0],
        payload=original,
    )
    edited = deepcopy(original)
    edited["stem"] = "Kaynaklara göre hangi koşul doğru değildir?"
    if change == "omit":
        del edited["legacy_provenance"]
        del edited["options"][0]["legacy_label"]
    elif change == "mutate":
        edited["legacy_provenance"]["source_version"] = 3
    elif change == "nested_mutate":
        edited["options"][0]["legacy_label"] = "changed"
    response = await client.post(
        pool.url + f"/{question}/draft", headers=pool.instructor, json=pool.edit(payload=edited)
    )
    if change in {"mutate", "nested_mutate"}:
        assert response.status_code == 422, response.text
    else:
        assert response.status_code == 200, response.text
        saved = response.json()["payload"]
        assert saved["legacy_provenance"] == original["legacy_provenance"]
        assert saved["options"][0]["legacy_label"] == "retained"
        assert saved["stem"] == edited["stem"]


@pytest.mark.parametrize(
    "mutation", ["remove_first", "rename_omitting_metadata", "reorder", "omit_rubric"]
)
async def test_legacy_rubric_structure_is_not_reassigned(
    client: AsyncClient, pool: AuthoringPool, admin_engine: AsyncEngine, mutation: str
) -> None:
    original = deepcopy(ESSAY_PAYLOAD)
    original["rubric"] = [
        {"point": "Koşulları listeler", "weight": 50, "legacy_id": "first"},
        {"point": "Koşulları açıklar", "weight": 50, "legacy_id": "second"},
    ]
    question = await seed_question(
        admin_engine,
        course_id=pool.course,
        topic_id=pool.topic,
        source_chunk_id=pool.chunks[0],
        question_type=QuestionType.OPEN,
        payload=original,
    )
    edited = deepcopy(original)
    if mutation == "remove_first":
        edited["rubric"].pop(0)
        edited["rubric"][0]["weight"] = 100
    elif mutation == "rename_omitting_metadata":
        edited["rubric"][0]["point"] = "Başka ölçüt"
        for criterion in edited["rubric"]:
            del criterion["legacy_id"]
    elif mutation == "omit_rubric":
        edited["format"] = "short_answer"
        edited["accepted_answers"] = ["döngüsel bekleme"]
        del edited["rubric"]
    else:
        edited["rubric"].reverse()
    response = await client.post(
        pool.url + f"/{question}/draft", headers=pool.instructor, json=pool.edit(payload=edited)
    )
    assert response.status_code == 422, response.text
    listed = await client.get(pool.url, headers=pool.instructor)
    saved = next(item for item in listed.json()["items"] if item["id"] == str(question))
    assert saved["payload"] == original
