"""Ders bazlı AI politikasının API, RLS ve sıcak-yol kapıları."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.chat import reset_rate_limit, set_pipeline
from app.contracts import AnswerStatus, ChatMode, Citation, GeneratedAnswer, RetrievedChunk
from app.modules.agent import quota as agent_quota
from app.schemas.chat import LlmAnswerPayload
from tests.conftest import UserFactory
from tests.factories import (
    FakeCitationGuardrail as CitationGuardrail,
)
from tests.factories import (
    Pipeline,
    make_chunk,
    sourced_answer,
)
from tests.factories import (
    install_pipeline as _install,
)


@pytest.fixture(autouse=True)
def pipeline() -> Iterator[Pipeline]:
    fake = Pipeline()
    _install(fake)
    reset_rate_limit()
    yield fake
    set_pipeline()
    reset_rate_limit()


async def setup_course(
    client: AsyncClient, users: UserFactory
) -> tuple[str, dict[str, str], dict[str, str], UUID]:
    instructor_id = await users.create("policy.teacher@dogus.edu.tr")
    student_id = await users.create("policy.student@dogus.edu.tr")
    instructor = users.auth(instructor_id)
    student = users.auth(student_id)
    created = await client.post(
        "/courses",
        json={"code": f"POL-{uuid4().hex[:6]}", "title": "Politika Dersi"},
        headers=instructor,
    )
    assert created.status_code == 201, created.text
    course_id = created.json()["id"]
    added = await client.post(
        f"/courses/{course_id}/members",
        json={"email": "policy.student@dogus.edu.tr", "role": "student"},
        headers=instructor,
    )
    assert added.status_code == 201, added.text
    return course_id, instructor, student, student_id


class RecordingGenerator:
    def __init__(self) -> None:
        self.calls = 0
        self.seen_documents: list[list[UUID]] = []

    async def generate(
        self,
        *,
        question: str,
        chunks: list[RetrievedChunk],
        mode: ChatMode,
        socratic_stage: object = None,
        student_attempt: str | None = None,
    ) -> GeneratedAnswer:
        del question, student_attempt
        self.calls += 1
        self.seen_documents.append([chunk.document_id for chunk in chunks])
        chunk = chunks[0]
        return GeneratedAnswer(
            status=AnswerStatus.ANSWERED,
            mode=mode,
            text="Kaynaklı yanıt.",
            citations=[Citation(chunk.chunk_id, chunk.file_name, chunk.location, chunk.text)],
            socratic_stage=socratic_stage,  # type: ignore[arg-type]
            prompt_tokens=7,
            completion_tokens=3,
        )


class TestPolicyApi:
    async def test_varsayilan_bugunku_davranisi_korur_ve_ogrenci_yazamaz(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        course_id, instructor, student, _ = await setup_course(client, users)

        response = await client.get(f"/courses/{course_id}/ai-policy", headers=instructor)
        denied = await client.get(f"/courses/{course_id}/ai-policy", headers=student)

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["allowed_modes"] is None
        assert body["effective"]["allowed_modes"] == ["qa", "socratic"]
        assert body["effective"]["hint_limit"] == 4
        assert body["effective"]["daily_llm_budget"] == 500_000
        assert denied.status_code == 403

    async def test_put_denetime_yazilir_ve_cache_temizlenir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        course_id, instructor, _, _ = await setup_course(client, users)
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO answer_cache (course_id, question_hash, answer) "
                    "VALUES (:course_id, 'old', '{}'::jsonb)"
                ),
                {"course_id": course_id},
            )

        response = await client.put(
            f"/courses/{course_id}/ai-policy",
            json={
                "allowed_modes": ["qa"],
                "hint_limit": 2,
                "evidence_threshold": 0.72,
                "daily_llm_budget": 500,
                "source_document_ids": None,
            },
            headers=instructor,
        )
        history = await client.get(f"/courses/{course_id}/ai-policy/history", headers=instructor)

        assert response.status_code == 200, response.text
        assert response.json()["effective"]["allowed_modes"] == ["qa"]
        assert response.json()["budget_remaining_today"] == 500
        assert history.status_code == 200, history.text
        assert len(history.json()) == 1
        assert history.json()[0]["before"] is None
        assert history.json()[0]["after"]["max_hints"] == 2
        async with admin_engine.connect() as conn:
            cached = await conn.scalar(
                text("SELECT count(*) FROM answer_cache WHERE course_id=:course_id"),
                {"course_id": course_id},
            )
        assert cached == 0

    async def test_silinmis_kaynak_kimligi_istemciye_canli_belge_diye_donmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        course_id, instructor, _, _ = await setup_course(client, users)
        document_id = uuid4()
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO documents "
                    "(id, course_id, uploaded_by, file_name, file_type, storage_path, "
                    "file_hash, byte_size, status) VALUES "
                    "(:id, :course_id, (SELECT created_by FROM courses WHERE id=:course_id), "
                    "'gecici.pdf', 'pdf', :path, :hash, 10, 'completed')"
                ),
                {
                    "id": document_id,
                    "course_id": course_id,
                    "path": str(document_id),
                    "hash": document_id.hex,
                },
            )
        saved = await client.put(
            f"/courses/{course_id}/ai-policy",
            json={"source_document_ids": [str(document_id)]},
            headers=instructor,
        )
        assert saved.status_code == 200, saved.text

        async with admin_engine.begin() as conn:
            await conn.execute(text("DELETE FROM documents WHERE id=:id"), {"id": document_id})
        fetched = await client.get(f"/courses/{course_id}/ai-policy", headers=instructor)

        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["source_document_ids"] == []
        assert fetched.json()["effective"]["source_document_ids"] == []

    async def test_exam_modu_politikayla_acilamaz(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        course_id, instructor, _, _ = await setup_course(client, users)
        response = await client.put(
            f"/courses/{course_id}/ai-policy",
            json={"allowed_modes": ["exam"]},
            headers=instructor,
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


class TestPolicyRuntime:
    def test_butce_durumu_model_tarafindan_uydurulamaz(self) -> None:
        with pytest.raises(PydanticValidationError):
            LlmAnswerPayload(status="budget_exhausted", answer="Bütçeniz doldu.")

    async def test_kapali_mod_oturum_yaratmadan_403_doner(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
    ) -> None:
        course_id, instructor, student, student_id = await setup_course(client, users)
        saved = await client.put(
            f"/courses/{course_id}/ai-policy",
            json={"allowed_modes": ["qa"]},
            headers=instructor,
        )
        assert saved.status_code == 200, saved.text

        response = await client.post(
            f"/courses/{course_id}/chat",
            json={"question": "Deadlock nedir?", "mode": "socratic"},
            headers=student,
        )
        async with admin_engine.connect() as conn:
            count = await conn.scalar(
                text("SELECT count(*) FROM chat_sessions WHERE user_id=:user_id"),
                {"user_id": student_id},
            )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "mode_not_allowed"
        assert count == 0

    async def test_tum_ogrenci_modlari_kapaliyken_egitmen_test_edebilir(
        self,
        client: AsyncClient,
        users: UserFactory,
        pipeline: Pipeline,
    ) -> None:
        course_id, instructor, student, _ = await setup_course(client, users)
        saved = await client.put(
            f"/courses/{course_id}/ai-policy",
            json={"allowed_modes": []},
            headers=instructor,
        )
        assert saved.status_code == 200, saved.text

        instructor_availability = await client.get(
            f"/courses/{course_id}/chat/availability", headers=instructor
        )
        student_availability = await client.get(
            f"/courses/{course_id}/chat/availability", headers=student
        )
        instructor_chat = await client.post(
            f"/courses/{course_id}/chat",
            json={"question": "Deadlock nedir?", "mode": "qa"},
            headers=instructor,
        )
        student_chat = await client.post(
            f"/courses/{course_id}/chat",
            json={"question": "Deadlock nedir?", "mode": "qa"},
            headers=student,
        )

        assert instructor_availability.status_code == 200
        assert instructor_availability.json()["available"] is True
        assert instructor_availability.json()["allowed_modes"] == ["qa", "socratic"]
        assert student_availability.status_code == 200
        assert student_availability.json()["available"] is False
        assert student_availability.json()["reason"] == "policy_all_modes_closed"
        assert instructor_chat.status_code == 200, instructor_chat.text
        assert instructor_chat.json()["status"] == "insufficient_context"
        assert student_chat.status_code == 403, student_chat.text
        assert student_chat.json()["error"]["code"] == "mode_not_allowed"
        assert pipeline.generator.calls == 0

    async def test_kaynak_seti_enjekte_edilen_hatta_da_daralir(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
    ) -> None:
        course_id, instructor, student, _ = await setup_course(client, users)
        first, second = uuid4(), uuid4()
        async with admin_engine.begin() as conn:
            for document_id, name in ((first, "allowed.pdf"), (second, "blocked.pdf")):
                await conn.execute(
                    text(
                        "INSERT INTO documents "
                        "(id, course_id, uploaded_by, file_name, file_type, storage_path, "
                        "file_hash, byte_size, status) VALUES "
                        "(:id, :course_id, (SELECT created_by FROM courses WHERE id=:course_id), "
                        ":name, 'pdf', :path, :hash, 10, 'completed')"
                    ),
                    {
                        "id": document_id,
                        "course_id": course_id,
                        "name": name,
                        "path": str(document_id),
                        "hash": document_id.hex,
                    },
                )
        saved = await client.put(
            f"/courses/{course_id}/ai-policy",
            json={"source_document_ids": [str(first)]},
            headers=instructor,
        )
        assert saved.status_code == 200, saved.text
        chunk_one = replace(make_chunk(file_name="allowed.pdf"), document_id=first)
        chunk_two = replace(make_chunk(file_name="blocked.pdf"), document_id=second)
        pipeline.retriever.by_course[UUID(course_id)] = [chunk_one, chunk_two]
        generator = RecordingGenerator()
        set_pipeline(
            retriever_factory=lambda _session: pipeline.retriever,
            generator=generator,
            guardrails=[CitationGuardrail()],
        )

        response = await client.post(
            f"/courses/{course_id}/chat",
            json={"question": "Deadlock nedir?"},
            headers=student,
        )
        assert response.status_code == 200, response.text
        assert response.json()["citations"][0]["file_name"] == "allowed.pdf"
        assert generator.seen_documents == [[first]]

    async def test_yuksek_kanit_esigi_llm_cagirmadan_reddeder(
        self, client: AsyncClient, users: UserFactory, pipeline: Pipeline
    ) -> None:
        course_id, instructor, student, _ = await setup_course(client, users)
        saved = await client.put(
            f"/courses/{course_id}/ai-policy",
            json={"evidence_threshold": 0.95},
            headers=instructor,
        )
        assert saved.status_code == 200, saved.text
        pipeline.serve(course_id, make_chunk(dense_score=0.82))
        generator = RecordingGenerator()
        set_pipeline(
            retriever_factory=lambda _session: pipeline.retriever,
            generator=generator,
            guardrails=[CitationGuardrail()],
        )

        response = await client.post(
            f"/courses/{course_id}/chat",
            json={"question": "Deadlock nedir?"},
            headers=student,
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "insufficient_context"
        assert generator.calls == 0

    async def test_butce_dolunca_hata_degil_200_durumuyla_doner(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
    ) -> None:
        course_id, instructor, student, student_id = await setup_course(client, users)
        saved = await client.put(
            f"/courses/{course_id}/ai-policy",
            json={"daily_llm_budget": 10},
            headers=instructor,
        )
        assert saved.status_code == 200, saved.text
        # Ders bütçesi tek bir kullanıcının değil, dersteki bütün AI
        # tüketiminin toplamıdır. İkinci öğrencinin harcaması ilk öğrenciyi de
        # course cap'te durdurmalı; aksi halde panel ve ön kontrol eksik sayar.
        second_student_id = await users.create("policy.second.student@dogus.edu.tr")
        added = await client.post(
            f"/courses/{course_id}/members",
            json={"email": "policy.second.student@dogus.edu.tr", "role": "student"},
            headers=instructor,
        )
        assert added.status_code == 201, added.text
        reservation = await agent_quota.reserve(
            user_id=second_student_id,
            course_id=UUID(course_id),
            requested_tokens=10,
            lease_seconds=60,
            user_hard_limit=50_000,
            course_hard_limit=500_000,
            platform_hard_limit=5_000_000,
        )
        assert reservation.allowed is True

        response = await client.post(
            f"/courses/{course_id}/chat",
            json={"question": "Deadlock nedir?"},
            headers=student,
        )
        policy_response = await client.get(f"/courses/{course_id}/ai-policy", headers=instructor)
        async with admin_engine.connect() as conn:
            count = await conn.scalar(
                text("SELECT count(*) FROM chat_sessions WHERE user_id=:user_id"),
                {"user_id": student_id},
            )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "budget_exhausted"
        assert "gece yarısı" in response.json()["answer"]
        assert response.json()["citations"] == []
        assert pipeline.generator.calls == 0
        assert count == 1
        assert policy_response.status_code == 200, policy_response.text
        assert policy_response.json()["budget_used_today"] == 10

    async def test_saglayici_tokenlari_request_loga_yazilir(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        pipeline: Pipeline,
    ) -> None:
        course_id, _, student, student_id = await setup_course(client, users)
        chunk = pipeline.serve(course_id, make_chunk())
        generator = RecordingGenerator()
        set_pipeline(
            retriever_factory=lambda _session: pipeline.retriever,
            generator=generator,
            guardrails=[CitationGuardrail()],
        )
        response = await client.post(
            f"/courses/{course_id}/chat",
            json={"question": "Deadlock nedir?"},
            headers=student,
        )
        assert response.status_code == 200, response.text
        assert response.json()["citations"][0]["chunk_id"] == str(chunk.chunk_id)
        async with admin_engine.connect() as conn:
            token_count = await conn.scalar(
                text(
                    "SELECT token_count FROM request_logs "
                    "WHERE course_id=:course_id AND user_id=:user_id"
                ),
                {"course_id": course_id, "user_id": student_id},
            )
        assert token_count == 10

    async def test_ipucu_limiti_merdiveni_gecmez(
        self, client: AsyncClient, users: UserFactory, pipeline: Pipeline
    ) -> None:
        course_id, instructor, student, _ = await setup_course(client, users)
        saved = await client.put(
            f"/courses/{course_id}/ai-policy",
            json={"allowed_modes": ["socratic"], "hint_limit": 1},
            headers=instructor,
        )
        assert saved.status_code == 200, saved.text
        chunk = pipeline.serve(course_id, make_chunk())
        pipeline.answers(sourced_answer(chunk), sourced_answer(chunk))

        first = await client.post(
            f"/courses/{course_id}/chat",
            json={"question": "Deadlock nedir?", "mode": "socratic"},
            headers=student,
        )
        assert first.status_code == 200, first.text
        session_id = first.json()["session_id"]
        second = await client.post(
            f"/courses/{course_id}/chat",
            json={
                "question": "Deadlock nedir?",
                "mode": "socratic",
                "session_id": session_id,
                "student_attempt": "Karşılıklı bekleme olabilir.",
            },
            headers=student,
        )
        third = await client.post(
            f"/courses/{course_id}/chat",
            json={
                "question": "Deadlock nedir?",
                "mode": "socratic",
                "session_id": session_id,
                "student_attempt": "Kaynakların tutulması da gerekiyor.",
            },
            headers=student,
        )
        assert second.status_code == 200, second.text
        assert third.status_code == 200, third.text
        assert second.json()["socratic_stage"] == "nudge"
        assert third.json()["socratic_stage"] == "nudge"
        assert "ipucu sınırına" in third.json()["answer"]
        assert pipeline.generator.calls == 2
