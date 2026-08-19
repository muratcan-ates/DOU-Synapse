"""009 soru sınıflandırma sözleşmesinin API regresyonları."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.modules.assessment import question_gen
from tests.conftest import UserFactory
from tests.factories import (
    DEADLOCK_TEXTS,
    FakeCompletion,
    FakeRetriever,
    _mcq_response,
    create_course,
    create_topic,
    mcq_payload,
    retrieved,
    seed_document,
    seed_question,
)


@dataclass(frozen=True, slots=True)
class ClassificationFixture:
    course_id: UUID
    instructor_id: UUID
    instructor: dict[str, str]
    topic_id: UUID
    other_topic_id: UUID
    chunk_ids: list[UUID]


async def build_fixture(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    *,
    code: str,
) -> ClassificationFixture:
    instructor_id = await users.create(f"hoca-{code.lower()}@dogus.edu.tr")
    instructor = users.auth(instructor_id)
    course_id = await create_course(client, instructor, code)
    topic_id = await create_topic(client, instructor, course_id, "Kilitlenme")
    other_topic_id = await create_topic(client, instructor, course_id, "Bellek")
    chunk_ids = (
        await seed_document(
            admin_engine,
            course_id=course_id,
            uploaded_by=instructor_id,
            passages=DEADLOCK_TEXTS,
        )
    ).chunk_ids
    return ClassificationFixture(
        course_id=course_id,
        instructor_id=instructor_id,
        instructor=instructor,
        topic_id=topic_id,
        other_topic_id=other_topic_id,
        chunk_ids=chunk_ids,
    )


async def make_outcome(
    client: AsyncClient,
    fixture: ClassificationFixture,
    *,
    topic_id: UUID | None,
    code: str = "CO1",
) -> UUID:
    response = await client.post(
        f"/courses/{fixture.course_id}/learning-outcomes",
        json={
            "code": code,
            "description": f"{code} kazanımı",
            "topic_id": str(topic_id) if topic_id is not None else None,
        },
        headers=fixture.instructor,
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def make_draft(
    admin_engine: AsyncEngine,
    fixture: ClassificationFixture,
    *,
    status: str = "draft",
    purpose: str = "practice",
) -> UUID:
    question_id = await seed_question(
        admin_engine,
        course_id=fixture.course_id,
        topic_id=fixture.topic_id,
        source_chunk_id=fixture.chunk_ids[0],
        payload=mcq_payload(fixture.chunk_ids),
        status=status,
        reviewed_by=fixture.instructor_id if status != "draft" else None,
    )
    if purpose != "practice":
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE questions SET purpose = CAST(:purpose AS question_purpose) "
                    "WHERE id = :id"
                ),
                {"purpose": purpose, "id": question_id},
            )
    return question_id


class TestGenerateClassification:
    async def test_learning_outcome_ve_difficulty_birlikte_verilmelidir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_fixture(client, users, admin_engine, code="PAIR101")
        outcome_id = await make_outcome(client, fixture, topic_id=fixture.topic_id)

        only_outcome = await client.post(
            f"/courses/{fixture.course_id}/questions/generate",
            json={"topic_id": str(fixture.topic_id), "learning_outcome_id": str(outcome_id)},
            headers=fixture.instructor,
        )
        only_difficulty = await client.post(
            f"/courses/{fixture.course_id}/questions/generate",
            json={"topic_id": str(fixture.topic_id), "difficulty": "easy"},
            headers=fixture.instructor,
        )

        for response in (only_outcome, only_difficulty):
            assert response.status_code == 422, response.text
            assert response.json()["error"]["code"] == "validation_error"

    async def test_generate_siniflandirma_ve_amaci_taslaga_tasir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_fixture(client, users, admin_engine, code="PAIR102")
        outcome_id = await make_outcome(client, fixture, topic_id=fixture.topic_id)
        chunks = retrieved(fixture.chunk_ids, DEADLOCK_TEXTS)
        question_gen.set_providers(
            retriever_factory=lambda _session: FakeRetriever(chunks),
            completion=FakeCompletion(_mcq_response(fixture.chunk_ids[0])),
        )
        try:
            response = await client.post(
                f"/courses/{fixture.course_id}/questions/generate",
                json={
                    "topic_id": str(fixture.topic_id),
                    "learning_outcome_id": str(outcome_id),
                    "difficulty": "hard",
                    "purpose": "assessment",
                    "question_type": "mcq",
                    "count": 1,
                },
                headers=fixture.instructor,
            )
        finally:
            question_gen.reset_providers()

        assert response.status_code == 200, response.text
        question = response.json()["questions"][0]
        assert question["status"] == "draft"
        assert question["purpose"] == "assessment"
        assert question["learning_outcome_id"] == str(outcome_id)
        assert question["difficulty"] == "hard"


class TestQuestionClassification:
    async def test_taslak_soru_ayni_konudaki_ciktiya_baglanir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_fixture(client, users, admin_engine, code="CLASS101")
        outcome_id = await make_outcome(client, fixture, topic_id=fixture.topic_id)
        question_id = await make_draft(admin_engine, fixture)

        response = await client.patch(
            f"/courses/{fixture.course_id}/questions/{question_id}/classification",
            json={"learning_outcome_id": str(outcome_id), "difficulty": "medium"},
            headers=fixture.instructor,
        )

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "draft"
        assert response.json()["learning_outcome_id"] == str(outcome_id)
        assert response.json()["difficulty"] == "medium"

    async def test_baska_dersin_ciktisi_varligi_sizdirilmadan_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_fixture(client, users, admin_engine, code="CLASS102")
        question_id = await make_draft(admin_engine, fixture)
        other_course = await create_course(client, fixture.instructor, "CLASS202")
        other_topic = await create_topic(client, fixture.instructor, other_course, "Ağlar")
        outcome_response = await client.post(
            f"/courses/{other_course}/learning-outcomes",
            json={"code": "CO9", "description": "Başka ders", "topic_id": str(other_topic)},
            headers=fixture.instructor,
        )
        assert outcome_response.status_code == 201, outcome_response.text

        response = await client.patch(
            f"/courses/{fixture.course_id}/questions/{question_id}/classification",
            json={
                "learning_outcome_id": outcome_response.json()["id"],
                "difficulty": "easy",
            },
            headers=fixture.instructor,
        )

        assert response.status_code == 404, response.text
        assert response.json()["error"]["code"] == "not_found"

    async def test_farkli_konuya_bagli_cikti_acikca_422_doner(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_fixture(client, users, admin_engine, code="CLASS103")
        outcome_id = await make_outcome(client, fixture, topic_id=fixture.other_topic_id)
        question_id = await make_draft(admin_engine, fixture)

        response = await client.patch(
            f"/courses/{fixture.course_id}/questions/{question_id}/classification",
            json={"learning_outcome_id": str(outcome_id), "difficulty": "hard"},
            headers=fixture.instructor,
        )

        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "validation_error"
        assert "bu sorunun konusuna bağlı değil" in response.json()["error"]["message"]

    async def test_konusuz_cikti_her_konudaki_taslaga_baglanabilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_fixture(client, users, admin_engine, code="CLASS104")
        outcome_id = await make_outcome(client, fixture, topic_id=None)
        question_id = await make_draft(admin_engine, fixture)

        response = await client.patch(
            f"/courses/{fixture.course_id}/questions/{question_id}/classification",
            json={"learning_outcome_id": str(outcome_id), "difficulty": "easy"},
            headers=fixture.instructor,
        )

        assert response.status_code == 200, response.text
        assert response.json()["learning_outcome_id"] == str(outcome_id)

    async def test_incelenmis_sorunun_siniflandirmasi_degismez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_fixture(client, users, admin_engine, code="CLASS105")
        outcome_id = await make_outcome(client, fixture, topic_id=fixture.topic_id)
        question_id = await make_draft(admin_engine, fixture, status="approved")

        response = await client.patch(
            f"/courses/{fixture.course_id}/questions/{question_id}/classification",
            json={"learning_outcome_id": str(outcome_id), "difficulty": "easy"},
            headers=fixture.instructor,
        )

        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "question_immutable"

    async def test_siniflandirilmamis_assessment_taslagi_onaylanamaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_fixture(client, users, admin_engine, code="CLASS106")
        question_id = await make_draft(admin_engine, fixture, purpose="assessment")

        response = await client.post(
            f"/courses/{fixture.course_id}/questions/{question_id}/approve",
            headers=fixture.instructor,
        )

        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "question_classification_required"
