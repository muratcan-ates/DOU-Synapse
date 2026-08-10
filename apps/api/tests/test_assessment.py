"""Ölçme (assessment) testleri — konu, soru havuzu, üretim ve puanlama.

Sınav oturumu akışı `test_exams.py`'de; bu dosya havuzu ve onun iki pazarlıksız
kuralını kapsar:

1. **Öğrenci taslak soruyu göremez** (T033 vaka 2). `0004`'ün en kritik RLS
   politikası budur ve iki katmanla korunur — uygulama filtresi + `questions_read`.
   `TestDraftInvisibility` iki katmanı AYRI AYRI sınar: biri kaldırıldığında
   diğerinin hâlâ tuttuğu görülsün diye.
2. **Cevap anahtarı öğrenciye sızmaz.** Onaylı bir soru bile öğrenciye
   `public_payload()` beyaz listesinden geçerek gider.

Yardımcılar (`seed_chunks`, `seed_question`, ...) `test_exams.py` tarafından da
kullanılır; iki dosyada iki kopya kurulum olmasın diye burada tutulur (Anayasa XI).
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.contracts import RetrievedChunk
from app.core.db import rls_session
from app.models.assessment import QuestionType
from app.modules.assessment import question_gen
from app.modules.generation.llm import LlmUnavailableError
from app.schemas.assessment import AnswerFormat, McqPayload, OpenPayload
from tests.conftest import UserFactory

# ---------------------------------------------------------------------------
# Kurulum yardımcıları
# ---------------------------------------------------------------------------


async def _create_course(client: AsyncClient, headers: dict[str, str], code: str) -> str:
    response = await client.post(
        "/courses", json={"code": code, "title": f"{code} Dersi"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def enroll(
    client: AsyncClient, instructor: dict[str, str], course_id: str, email: str
) -> None:
    response = await client.post(
        f"/courses/{course_id}/members",
        json={"email": email, "role": "student"},
        headers=instructor,
    )
    assert response.status_code == 201, response.text


async def create_topic(
    client: AsyncClient, instructor: dict[str, str], course_id: str, name: str
) -> UUID:
    response = await client.post(
        f"/courses/{course_id}/topics", json={"name": name}, headers=instructor
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def seed_chunks(
    admin_engine: AsyncEngine,
    *,
    course_id: UUID,
    uploaded_by: UUID,
    texts: list[str],
    file_name: str = "isletim-sistemleri.pdf",
) -> list[UUID]:
    """Belge + chunk satırlarını doğrudan yazar.

    Yükleme hattı (ingestion) bu dosyanın konusu değil; soru havuzunun ihtiyacı
    yalnız "kaynağı olan chunk"lar. `fts` sütunu GENERATED olduğu için yazılmaz.
    """
    document_id = uuid4()
    chunk_ids = [uuid4() for _ in texts]
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO documents (id, course_id, uploaded_by, file_name, file_type, "
                "storage_path, file_hash, byte_size, status, chunk_count) VALUES "
                "(:id, :course_id, :uploaded_by, :file_name, 'pdf', :path, :hash, 1024, "
                "'completed', :count)"
            ),
            {
                "id": document_id,
                "course_id": course_id,
                "uploaded_by": uploaded_by,
                "file_name": file_name,
                "path": f"{course_id}/{document_id}.pdf",
                "hash": document_id.hex,
                "count": len(texts),
            },
        )
        for index, (chunk_id, body) in enumerate(zip(chunk_ids, texts, strict=True)):
            await conn.execute(
                text(
                    "INSERT INTO chunks (id, course_id, document_id, chunk_index, page_number, "
                    "text, token_count) VALUES (:id, :course_id, :document_id, :index, :page, "
                    ":text, :tokens)"
                ),
                {
                    "id": chunk_id,
                    "course_id": course_id,
                    "document_id": document_id,
                    "index": index,
                    "page": index + 1,
                    "text": body,
                    "tokens": max(1, len(body.split())),
                },
            )
    return chunk_ids


async def seed_question(
    admin_engine: AsyncEngine,
    *,
    course_id: UUID,
    topic_id: UUID,
    source_chunk_id: UUID,
    payload: dict[str, Any],
    question_type: QuestionType = QuestionType.MCQ,
    status: str = "draft",
    reviewed_by: UUID | None = None,
) -> UUID:
    """Havuza soru yazar. `approved`/`rejected` için inceleyen kullanıcı zorunludur."""
    if status != "draft" and reviewed_by is None:
        raise AssertionError("questions_reviewed_consistency: reviewed_by verilmeli")

    question_id = uuid4()
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO questions (id, course_id, topic_id, type, payload, "
                "source_chunk_id, status, reviewed_by, reviewed_at) VALUES "
                "(:id, :course_id, :topic_id, CAST(:type AS question_type), "
                "CAST(:payload AS jsonb), :chunk_id, CAST(:status AS question_status), "
                ":reviewed_by, CASE WHEN :status = 'draft' THEN NULL ELSE now() END)"
            ),
            {
                "id": question_id,
                "course_id": course_id,
                "topic_id": topic_id,
                "type": question_type.value,
                "payload": json.dumps(payload),
                "chunk_id": source_chunk_id,
                "status": status,
                "reviewed_by": reviewed_by,
            },
        )
    return question_id


DEADLOCK_TEXTS = [
    "Deadlock için dört koşulun aynı anda sağlanması gerekir: karşılıklı dışlama, "
    "tut ve bekle, kesilemezlik ve döngüsel bekleme.",
    "Kesme (preemption) zorunluluğu bir deadlock koşulu değildir; tam tersine "
    "kaynağın zorla geri alınabilmesi deadlock'u kırar.",
]


def mcq_payload(chunk_ids: list[UUID]) -> dict[str, Any]:
    """Dört şıklı örnek MCQ. Çeldirici kaynakları gerçek chunk'lara bağlıdır."""
    return {
        "stem": "Deadlock'un oluşması için aşağıdakilerden hangisi gerekli DEĞİLDİR?",
        "options": [
            {"key": "A", "text": "Karşılıklı dışlama"},
            {"key": "B", "text": "Döngüsel bekleme"},
            {"key": "C", "text": "Kesme zorunluluğu"},
            {"key": "D", "text": "Tut ve bekle"},
        ],
        "answer_key": "C",
        "distractor_sources": {
            "A": str(chunk_ids[0]),
            "B": str(chunk_ids[0]),
            "D": str(chunk_ids[1 % len(chunk_ids)]),
        },
        "explanation": "Dört koşul arasında kesme zorunluluğu yoktur.",
    }


def short_answer_payload() -> dict[str, Any]:
    return {
        "prompt": "Deadlock'un dört koşulundan döngüsel beklemenin adı nedir?",
        "answer_key": "döngüsel bekleme",
        "format": AnswerFormat.SHORT_ANSWER.value,
        "accepted_answers": ["döngüsel bekleme", "circular wait"],
    }


class FakeRetriever:
    """`contracts.Retriever` protokolünün test uygulaması (00_OKU_ONCE §2)."""

    def __init__(self, chunks: list[RetrievedChunk]) -> None:
        self._chunks = chunks

    async def search(self, *, course_id: UUID, query: str, limit: int = 8) -> list[RetrievedChunk]:
        del course_id, query
        return self._chunks[:limit]


class FakeCompletion:
    """Sırayla hazır yanıt döndüren sahte LLM. Çağrı sayısı sayılır."""

    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def complete(self, *, system: str, user: str) -> str:
        del system, user
        self.calls += 1
        index = min(self.calls - 1, len(self._responses) - 1)
        return self._responses[index]


def retrieved(chunk_ids: list[UUID], texts: list[str]) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id=chunk_id,
            document_id=uuid4(),
            file_name="isletim-sistemleri.pdf",
            page_number=index + 1,
            slide_number=None,
            section_title=None,
            text=body,
            fused_score=1.0 - index * 0.1,
        )
        for index, (chunk_id, body) in enumerate(zip(chunk_ids, texts, strict=True))
    ]


# ---------------------------------------------------------------------------
# Konular (mevcut kapsam)
# ---------------------------------------------------------------------------


class TestTopicCreation:
    async def test_egitmen_konu_olusturur(self, client: AsyncClient, users: UserFactory) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")

        response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Deadlock"
        assert body["course_id"] == course_id

    async def test_ogrenci_konu_olusturamaz(self, client: AsyncClient, users: UserFactory) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await client.post(
            f"/courses/{course_id}/members",
            json={"email": "burak@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )

        response = await client.post(
            f"/courses/{course_id}/topics",
            json={"name": "Deadlock"},
            headers=users.auth(burak_id),
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    async def test_uye_olmayan_kullanici_konu_olusturamaz(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        disari = users.auth(await users.create("disari@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")

        response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=disari
        )

        # Dersin varlığı sızdırılmaz: 403 değil 404.
        assert response.status_code == 404

    async def test_ayni_isimde_ikinci_konu_reddedilir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")
        await client.post(f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse)

        response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "deadlock"}, headers=ayse
        )

        assert response.status_code == 409


class TestTopicListing:
    async def test_ogrenci_konu_listesini_gorur(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await client.post(
            f"/courses/{course_id}/members",
            json={"email": "burak@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )
        await client.post(f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse)
        await client.post(
            f"/courses/{course_id}/topics", json={"name": "CPU Zamanlama"}, headers=ayse
        )

        response = await client.get(f"/courses/{course_id}/topics", headers=users.auth(burak_id))

        assert response.status_code == 200
        names = {topic["name"] for topic in response.json()}
        assert names == {"Deadlock", "CPU Zamanlama"}

    async def test_baska_dersin_konusu_donmez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """İzolasyon: course_id istemciden gelse bile başka dersin verisi sızmaz (Anayasa II)."""
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_a = await _create_course(client, ayse, "COME301")
        course_b = await _create_course(client, ayse, "COME302")
        await client.post(f"/courses/{course_a}/topics", json={"name": "Deadlock"}, headers=ayse)
        await client.post(
            f"/courses/{course_b}/topics", json={"name": "Bellek Yönetimi"}, headers=ayse
        )

        response_a = await client.get(f"/courses/{course_a}/topics", headers=ayse)
        response_b = await client.get(f"/courses/{course_b}/topics", headers=ayse)

        assert [t["name"] for t in response_a.json()] == ["Deadlock"]
        assert [t["name"] for t in response_b.json()] == ["Bellek Yönetimi"]

    async def test_uye_olmayan_kullanici_listeyi_goremez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        disari = users.auth(await users.create("disari@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")
        await client.post(f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse)

        response = await client.get(f"/courses/{course_id}/topics", headers=disari)

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# T033 vaka 2 — draft görünmezliği
# ---------------------------------------------------------------------------


class TestDraftInvisibility:
    """Onaylanmamış soru hiçbir öğrenci akışında görünmez (FR-023)."""

    async def test_ogrenci_taslak_soruyu_goremez_egitmen_gorur(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await enroll(client, ayse, course_id, "burak@dogus.edu.tr")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine,
            course_id=UUID(course_id),
            uploaded_by=ayse_id,
            texts=DEADLOCK_TEXTS,
        )
        draft_id = await seed_question(
            admin_engine,
            course_id=UUID(course_id),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
        )
        approved_id = await seed_question(
            admin_engine,
            course_id=UUID(course_id),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
            status="approved",
            reviewed_by=ayse_id,
        )

        student = await client.get(f"/courses/{course_id}/questions", headers=users.auth(burak_id))
        instructor = await client.get(f"/courses/{course_id}/questions", headers=ayse)

        assert student.status_code == 200, student.text
        assert {item["id"] for item in student.json()["items"]} == {str(approved_id)}
        assert {item["id"] for item in instructor.json()["items"]} == {
            str(draft_id),
            str(approved_id),
        }

    async def test_ogrenci_status_parametresiyle_taslak_isteyemez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Uygulama katmanı: `?status=draft` öğrenci için sunucuda yok sayılır."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await enroll(client, ayse, course_id, "burak@dogus.edu.tr")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        await seed_question(
            admin_engine,
            course_id=UUID(course_id),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
        )

        response = await client.get(
            f"/courses/{course_id}/questions?status=draft", headers=users.auth(burak_id)
        )

        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_rls_katmani_tek_basina_da_taslagi_gizler(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """İkinci katman: uygulama filtresi hiç yokken bile RLS taslağı vermez.

        Ham SQL ile — yani `questions_read` politikasından başka hiçbir süzgeç
        olmadan — öğrencinin oturumunda sorgu koşulur. Politika bozulursa bu test
        kırmızıya döner; kanıt olarak politika bilerek düşürülüp koşuldu ve
        gerçekten kırmızı yandı (bkz. KARARLAR_SERIT4.md §RLS kanıtı).
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await enroll(client, ayse, course_id, "burak@dogus.edu.tr")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        await seed_question(
            admin_engine,
            course_id=UUID(course_id),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
        )

        async with rls_session(burak_id) as session:
            rows = (await session.execute(text("SELECT id, status FROM questions"))).all()
        assert rows == []

        async with rls_session(ayse_id) as session:
            rows = (await session.execute(text("SELECT status FROM questions"))).all()
        assert [row.status for row in rows] == ["draft"]

    async def test_ogrenciye_cevap_anahtari_sizmaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Onaylı soru bile öğrenciye beyaz listeden geçerek gider."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await enroll(client, ayse, course_id, "burak@dogus.edu.tr")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        await seed_question(
            admin_engine,
            course_id=UUID(course_id),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
            status="approved",
            reviewed_by=ayse_id,
        )

        student = (
            await client.get(f"/courses/{course_id}/questions", headers=users.auth(burak_id))
        ).json()["items"][0]
        instructor = (await client.get(f"/courses/{course_id}/questions", headers=ayse)).json()[
            "items"
        ][0]

        assert set(student["payload"]) == {"stem", "options"}
        assert "answer_key" in instructor["payload"]
        assert "distractor_sources" in instructor["payload"]
        # Kaynak referansı gizli değil: öğrenci sorunun hangi materyalden geldiğini görür.
        assert student["source"]["file_name"] == "isletim-sistemleri.pdf"
        assert student["source"]["location"] == "Sayfa 1"


# ---------------------------------------------------------------------------
# Onay / red
# ---------------------------------------------------------------------------


class TestQuestionReview:
    async def test_egitmen_onaylayinca_ogrenci_gorur(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await enroll(client, ayse, course_id, "burak@dogus.edu.tr")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        question_id = await seed_question(
            admin_engine,
            course_id=UUID(course_id),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
        )

        before = await client.get(f"/courses/{course_id}/questions", headers=users.auth(burak_id))
        approve = await client.post(
            f"/courses/{course_id}/questions/{question_id}/approve", headers=ayse
        )
        after = await client.get(f"/courses/{course_id}/questions", headers=users.auth(burak_id))

        assert before.json()["items"] == []
        assert approve.status_code == 200, approve.text
        body = approve.json()
        assert body["status"] == "approved"
        # questions_reviewed_consistency CHECK'i ikisini birden ister.
        assert body["reviewed_by"] == str(ayse_id)
        assert body["reviewed_at"] is not None
        assert [item["id"] for item in after.json()["items"]] == [str(question_id)]

    async def test_reddedilen_soru_ogrenciye_gorunmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await enroll(client, ayse, course_id, "burak@dogus.edu.tr")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        question_id = await seed_question(
            admin_engine,
            course_id=UUID(course_id),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
            status="approved",
            reviewed_by=ayse_id,
        )

        reject = await client.post(
            f"/courses/{course_id}/questions/{question_id}/reject", headers=ayse
        )
        student = await client.get(f"/courses/{course_id}/questions", headers=users.auth(burak_id))

        assert reject.status_code == 200, reject.text
        assert reject.json()["status"] == "rejected"
        assert student.json()["items"] == []

    async def test_ogrenci_onaylayamaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await enroll(client, ayse, course_id, "burak@dogus.edu.tr")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        question_id = await seed_question(
            admin_engine,
            course_id=UUID(course_id),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
        )

        response = await client.post(
            f"/courses/{course_id}/questions/{question_id}/approve", headers=users.auth(burak_id)
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    async def test_baska_dersin_sorusu_onaylanamaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Yol parametresindeki ders kimliği yetki değildir (Anayasa II)."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_a = await _create_course(client, ayse, "COME301")
        course_b = await _create_course(client, ayse, "COME302")
        topic_id = await create_topic(client, ayse, course_b, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_b), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        question_id = await seed_question(
            admin_engine,
            course_id=UUID(course_b),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
        )

        response = await client.post(
            f"/courses/{course_a}/questions/{question_id}/approve", headers=ayse
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# T033 vaka 1 — soru üretimi şema geçerliliği
# ---------------------------------------------------------------------------


def _mcq_response(source_chunk_id: UUID | str, *, count: int = 1) -> str:
    return json.dumps(
        {
            "questions": [
                {
                    "stem": f"Deadlock koşullarından hangisi yanlıştır? ({index})",
                    "options": [
                        {"key": "A", "text": "Karşılıklı dışlama"},
                        {"key": "B", "text": "Döngüsel bekleme"},
                        {"key": "C", "text": "Kesme zorunluluğu"},
                        {"key": "D", "text": "Tut ve bekle"},
                    ],
                    "answer_key": "C",
                    "explanation": "Dört koşul arasında kesme zorunluluğu yoktur.",
                    "source_chunk_id": str(source_chunk_id),
                }
                for index in range(count)
            ]
        }
    )


class TestQuestionDelete:
    """Silme, reddetmekten farklı bir iş ve tek bir gerçek kilidi açıyor.

    `questions.source_chunk_id` `ON DELETE RESTRICT` taşıyor: bir belgeden
    üretilmiş soru havuzda durduğu sürece o BELGE silinemiyor. `documents.py`
    bunu 409 ile reddedip "önce ilgili soruları kaldırın" diyor — ve bu uç
    yazılana kadar kaldırmanın hiçbir yolu yoktu. Yapılamayacak bir şeyi öneren
    hata mesajı, hiç mesaj vermemekten kötüdür.
    """

    async def test_egitmen_soruyu_silince_belge_de_silinebilir_hale_gelir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Zincirin tamamı: soru siliniyor → belgenin kilidi açılıyor."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_id = await _create_course(client, ayse, "COME301")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        question_id = await seed_question(
            admin_engine,
            course_id=UUID(course_id),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
        )
        async with admin_engine.begin() as conn:
            document_id = await conn.scalar(
                text("SELECT document_id FROM chunks WHERE id = :c"), {"c": chunk_ids[0]}
            )

        # Önce belge silinemiyor: soru onu kilitliyor.
        kilitli = await client.delete(f"/courses/{course_id}/documents/{document_id}", headers=ayse)
        assert kilitli.status_code == 409, kilitli.text

        silme = await client.delete(f"/courses/{course_id}/questions/{question_id}", headers=ayse)
        assert silme.status_code == 204, silme.text

        # Kilit açıldı: mesajın önerdiği çıkış yolu gerçekten çalışıyor.
        acildi = await client.delete(f"/courses/{course_id}/documents/{document_id}", headers=ayse)
        assert acildi.status_code == 204, acildi.text

    async def test_ogrenci_soru_silemez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await enroll(client, ayse, course_id, "burak@dogus.edu.tr")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        question_id = await seed_question(
            admin_engine,
            course_id=UUID(course_id),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
        )

        response = await client.delete(
            f"/courses/{course_id}/questions/{question_id}", headers=users.auth(burak_id)
        )

        assert response.status_code == 403

    async def test_cevaplanmis_soru_silinmez_ve_sebebi_soylenir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Bir öğrencinin cevabının sorusunu silmek, o cevabı okunamaz kılardı.

        Veritabanı bunu `answers.question_id` RESTRICT ile zaten reddediyor;
        sınanan şey, uçun bunu 500 yerine anlaşılır bir 409'a çevirmesi.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await enroll(client, ayse, course_id, "burak@dogus.edu.tr")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        question_id = await seed_question(
            admin_engine,
            course_id=UUID(course_id),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
            status="approved",
            reviewed_by=ayse_id,
        )
        async with admin_engine.begin() as conn:
            exam_id = await conn.scalar(
                text(
                    "INSERT INTO exam_sessions (course_id, user_id, mode, question_ids) "
                    "VALUES (:c, :u, 'practice', ARRAY[:q]::uuid[]) RETURNING id"
                ),
                {"c": course_id, "u": burak_id, "q": question_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO answers (session_id, question_id, course_id, given, "
                    "is_correct, score) VALUES (:s, :q, :c, 'A', true, 100)"
                ),
                {"s": exam_id, "q": question_id, "c": course_id},
            )

        response = await client.delete(
            f"/courses/{course_id}/questions/{question_id}", headers=ayse
        )

        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "conflict"
        assert "cevaplanmış" in response.json()["error"]["message"]


class TestQuestionGeneration:
    async def test_gecerli_cikti_havuza_draft_yazilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_id = await _create_course(client, ayse, "COME301")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        chunks = retrieved(chunk_ids, DEADLOCK_TEXTS)

        async with rls_session(ayse_id) as session:
            topic = await _load_topic(session, topic_id)
            report = await question_gen.generate_questions(
                session,
                course_id=UUID(course_id),
                topic=topic,
                question_type=QuestionType.MCQ,
                count=2,
                created_by=ayse_id,
                retriever=FakeRetriever(chunks),
                completion=FakeCompletion(_mcq_response(chunk_ids[0], count=2)),
            )

        assert report.accepted == 2
        assert report.rejected == 0
        assert all(question.status.value == "draft" for question in report.questions)
        # distractor_sources modelden istenmedi; bizim eşlememizle doldu.
        payload = McqPayload.model_validate(report.questions[0].payload)
        assert set(payload.distractor_sources) == {"A", "B", "D"}
        assert set(payload.distractor_sources.values()) <= set(chunk_ids)

    async def test_bozuk_sema_iki_denemede_de_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """SC-009: şemadan geçmeyen çıktı havuza YAZILMAZ, bir kez yeniden denenir."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_id = await _create_course(client, ayse, "COME301")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        completion = FakeCompletion('{"questions": [{"stem": "eksik"}]}')

        async with rls_session(ayse_id) as session:
            topic = await _load_topic(session, topic_id)
            report = await question_gen.generate_questions(
                session,
                course_id=UUID(course_id),
                topic=topic,
                question_type=QuestionType.MCQ,
                count=1,
                created_by=ayse_id,
                retriever=FakeRetriever(retrieved(chunk_ids, DEADLOCK_TEXTS)),
                completion=completion,
            )

        assert report.accepted == 0
        assert completion.calls == 2, "şema tutmadığında bir kez yeniden denenmeli"
        assert any("şema" in reason for reason in report.rejection_reasons)

    async def test_sc009_paydasi_yalniz_modelin_dondurdugu_sorulari_sayar(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Ayrıştırılamayan yanıt "iki soru geldi, ikisi düştü" diye sayılmaz.

        SC-009 şema geçerliliği `accepted / returned` oranıdır; paydaya hiç
        gelmemiş soruları yazmak oranı uydurulmuş bir sayıyla raporlamak olur.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_id = await _create_course(client, ayse, "COME301")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        chunks = retrieved(chunk_ids, DEADLOCK_TEXTS)

        async with rls_session(ayse_id) as session:
            topic = await _load_topic(session, topic_id)
            # 1. Model hiç soru döndürmedi: yanıt bile ayrıştırılamadı.
            unparseable = await question_gen.generate_questions(
                session,
                course_id=UUID(course_id),
                topic=topic,
                question_type=QuestionType.MCQ,
                count=2,
                created_by=ayse_id,
                retriever=FakeRetriever(chunks),
                completion=FakeCompletion("elbette, işte sorular:"),
            )
            # 2. Model iki soru döndürdü, biri şemadan geçti.
            half_valid = json.dumps(
                {
                    "questions": [
                        json.loads(_mcq_response(chunk_ids[0]))["questions"][0],
                        {"stem": "eksik soru"},
                    ]
                }
            )
            mixed = await question_gen.generate_questions(
                session,
                course_id=UUID(course_id),
                topic=topic,
                question_type=QuestionType.MCQ,
                count=2,
                created_by=ayse_id,
                retriever=FakeRetriever(chunks),
                completion=FakeCompletion(half_valid),
            )

        assert (unparseable.returned, unparseable.accepted, unparseable.rejected) == (0, 0, 0)
        assert len(unparseable.rejection_reasons) == 2, "iki deneme de sebebini bırakmalı"
        assert (mixed.returned, mixed.accepted, mixed.rejected) == (2, 1, 1)

    async def test_uydurulmus_kaynak_sorusu_havuza_girmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Anayasa I: retrieve edilmemiş bir chunk'a atıf yapan soru düşer."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_id = await _create_course(client, ayse, "COME301")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )

        async with rls_session(ayse_id) as session:
            topic = await _load_topic(session, topic_id)
            report = await question_gen.generate_questions(
                session,
                course_id=UUID(course_id),
                topic=topic,
                question_type=QuestionType.MCQ,
                count=1,
                created_by=ayse_id,
                retriever=FakeRetriever(retrieved(chunk_ids, DEADLOCK_TEXTS)),
                completion=FakeCompletion(_mcq_response(uuid4())),
            )

        assert report.accepted == 0
        assert any("kaynak uydurma" in reason for reason in report.rejection_reasons)

    async def test_materyal_yoksa_soru_uretilmez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_id = await _create_course(client, ayse, "COME301")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        completion = FakeCompletion(_mcq_response(uuid4()))

        async with rls_session(ayse_id) as session:
            topic = await _load_topic(session, topic_id)
            report = await question_gen.generate_questions(
                session,
                course_id=UUID(course_id),
                topic=topic,
                question_type=QuestionType.MCQ,
                count=1,
                created_by=ayse_id,
                retriever=FakeRetriever([]),
                completion=completion,
            )

        assert report.accepted == 0
        assert completion.calls == 0, "kaynak yoksa modele hiç gidilmez"

    async def test_saglayici_kurulamazsa_uretim_uctan_reddedilir(
        self, client: AsyncClient, users: UserFactory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Fail-closed: hiçbir sağlayıcı kurulamıyorsa 503, uydurma soru değil.

        Soru üretimi puanlamadan farklı: LLM olmadan yapılabilecek bir şey yok,
        dolayısıyla burada hata yutulmaz, uca kadar çıkar (Anayasa IV).
        """

        def _unavailable(*_args: object, **_kwargs: object) -> object:
            raise LlmUnavailableError

        monkeypatch.setattr(question_gen, "build_llm_client", _unavailable)
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")

        response = await client.post(
            f"/courses/{course_id}/questions/generate",
            json={"topic_id": str(topic_id), "question_type": "mcq"},
            headers=ayse,
        )

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "llm_unavailable"

    async def test_uc_uctan_uca_uretir_ve_havuza_draft_yazar(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Sağlayıcılar bağlıyken uç gerçekten soru yazar ve öğrenciye göstermez."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await enroll(client, ayse, course_id, "burak@dogus.edu.tr")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_ids = await seed_chunks(
            admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
        )
        chunks = retrieved(chunk_ids, DEADLOCK_TEXTS)
        question_gen.set_providers(
            retriever_factory=lambda _session: FakeRetriever(chunks),
            completion=FakeCompletion(_mcq_response(chunk_ids[0], count=2)),
        )
        try:
            response = await client.post(
                f"/courses/{course_id}/questions/generate",
                json={"topic_id": str(topic_id), "question_type": "mcq", "count": 2},
                headers=ayse,
            )
        finally:
            question_gen.reset_providers()

        # 201 değil 200: toplu iş, kaçının yazıldığı raporda.
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["accepted"] == 2
        assert body["rejected"] == 0
        assert {question["status"] for question in body["questions"]} == {"draft"}

        student = await client.get(f"/courses/{course_id}/questions", headers=users.auth(burak_id))
        assert student.json()["items"] == [], "yeni üretilen sorular onaysız görünmemeli"


async def _load_topic(session: Any, topic_id: UUID) -> Any:
    from app.models.assessment import Topic

    topic = await session.get(Topic, topic_id)
    assert topic is not None
    return topic


# ---------------------------------------------------------------------------
# T033 vaka 5 — MCQ "neden yanlış" ve kısa cevap puanlaması
# ---------------------------------------------------------------------------


class TestDeterministicGrading:
    def test_mcq_dogru_sik_tam_puan(self) -> None:
        from app.modules.assessment.grading import grade_mcq

        chunk_ids = [uuid4(), uuid4()]
        payload = McqPayload.model_validate(mcq_payload(chunk_ids))

        outcome = grade_mcq(payload, "C")

        assert outcome.graded is True
        assert outcome.score == 100
        assert outcome.is_correct is True
        assert outcome.why_wrong_chunk_id is None

    def test_mcq_yanlis_sik_dogru_celdirici_kaynagini_gosterir(self) -> None:
        from app.modules.assessment.grading import grade_mcq

        chunk_ids = [uuid4(), uuid4()]
        payload = McqPayload.model_validate(mcq_payload(chunk_ids))

        outcome = grade_mcq(payload, "D")

        assert outcome.score == 0
        assert outcome.is_correct is False
        # "Neden yanlış" seçilen şıkkın kaynağıdır, sabit bir kaynak değil.
        assert outcome.why_wrong_chunk_id == chunk_ids[1]

    def test_mcq_gecersiz_sik_puan_almaz(self) -> None:
        from app.modules.assessment.grading import grade_mcq

        payload = McqPayload.model_validate(mcq_payload([uuid4(), uuid4()]))

        outcome = grade_mcq(payload, "Z")

        assert outcome.graded is True
        assert outcome.score == 0
        assert outcome.why_wrong_chunk_id is None

    def test_kisa_cevap_turkce_normalize_edilerek_eslesir(self) -> None:
        from app.modules.assessment.grading import grade_short_answer

        payload = OpenPayload.model_validate(short_answer_payload())
        source = uuid4()

        assert grade_short_answer(payload, "Döngüsel Bekleme", source_chunk_id=source).score == 100
        # Cümle içinde verilen doğru cevap da kabul edilir.
        assert (
            grade_short_answer(
                payload, "Bence buna döngüsel bekleme deniyor.", source_chunk_id=source
            ).score
            == 100
        )
        # İngilizce karşılık listede.
        assert grade_short_answer(payload, "circular wait", source_chunk_id=source).score == 100

    def test_kisa_cevap_yanlissa_kaynak_gosterilir(self) -> None:
        from app.modules.assessment.grading import grade_short_answer

        payload = OpenPayload.model_validate(short_answer_payload())
        source = uuid4()

        outcome = grade_short_answer(payload, "karşılıklı dışlama", source_chunk_id=source)

        assert outcome.score == 0
        assert outcome.is_correct is False
        assert outcome.why_wrong_chunk_id == source

    def test_turkce_normalizasyon_i_harfini_bozmaz(self) -> None:
        """Anayasa V: `upper()` kullanılmaz; İ/I ayrımı elle eşlenir."""
        assert question_gen.normalize_tr("İŞLETİM Sistemi") == "işletim sistemi"
        assert question_gen.normalize_tr("IŞIK") == "ışık"


# ---------------------------------------------------------------------------
# Açık uçlu değerlendirme — şemalı LLM yolu (FR-019, FR-020)
# ---------------------------------------------------------------------------


ESSAY_PAYLOAD = {
    "prompt": "Deadlock'un dört koşulunu açıklayın.",
    "answer_key": "Karşılıklı dışlama, tut ve bekle, kesilemezlik, döngüsel bekleme.",
    "key_points": ["karşılıklı dışlama", "tut ve bekle", "döngüsel bekleme"],
    "rubric": [{"point": "Dört koşulu sayar", "weight": 100}],
}


def _verdict(score: int, chunk_id: UUID | str | None, *, missing: list[str] | None = None) -> str:
    return json.dumps(
        {
            "score": score,
            "eksik_noktalar": missing or [],
            "dayanak_chunk_id": str(chunk_id) if chunk_id else None,
        }
    )


class TestLlmGrading:
    async def test_semali_cikti_puana_cevrilir(self) -> None:
        from app.modules.assessment.grading import grade_with_llm

        payload = OpenPayload.model_validate(ESSAY_PAYLOAD)
        chunk_id = uuid4()
        completion = FakeCompletion(_verdict(80, chunk_id, missing=["kesilemezlik"]))

        outcome = await grade_with_llm(
            completion,
            payload=payload,
            given="Karşılıklı dışlama, tut ve bekle ve döngüsel bekleme.",
            sources=[(chunk_id, DEADLOCK_TEXTS[0])],
        )

        assert outcome.graded is True
        assert outcome.score == 80
        assert outcome.is_correct is True
        assert outcome.missing_points == ["kesilemezlik"]
        assert outcome.evidence_chunk_id == chunk_id

    async def test_kod_citli_yanit_da_ayristirilir(self) -> None:
        from app.modules.assessment.grading import grade_with_llm

        chunk_id = uuid4()
        fenced = f"```json\n{_verdict(60, chunk_id)}\n```"

        outcome = await grade_with_llm(
            FakeCompletion(fenced),
            payload=OpenPayload.model_validate(ESSAY_PAYLOAD),
            given="Kısmen doğru.",
            sources=[(chunk_id, DEADLOCK_TEXTS[0])],
        )

        assert outcome.score == 60

    async def test_bozuk_sema_bir_kez_yeniden_denenir(self) -> None:
        from app.modules.assessment.grading import grade_with_llm

        chunk_id = uuid4()
        completion = FakeCompletion("puan: yüksek", _verdict(70, chunk_id))

        outcome = await grade_with_llm(
            completion,
            payload=OpenPayload.model_validate(ESSAY_PAYLOAD),
            given="Cevap.",
            sources=[(chunk_id, DEADLOCK_TEXTS[0])],
        )

        assert completion.calls == 2
        assert outcome.graded is True
        assert outcome.score == 70

    async def test_iki_denemede_de_bozuksa_uydurma_puan_verilmez(self) -> None:
        """FR-020: fail-closed. Puan yok, açık bir Türkçe mesaj var."""
        from app.modules.assessment.grading import grade_with_llm

        completion = FakeCompletion("bilmiyorum")

        outcome = await grade_with_llm(
            completion,
            payload=OpenPayload.model_validate(ESSAY_PAYLOAD),
            given="Cevap.",
            sources=[(uuid4(), DEADLOCK_TEXTS[0])],
        )

        assert completion.calls == 2
        assert outcome.graded is False
        assert outcome.score is None
        assert "tamamlanamadı" in (outcome.message or "")

    async def test_uydurulmus_dayanak_dusurulur_puan_kalir(self) -> None:
        """Anayasa I: set-membership'ten geçmeyen dayanak gösterilmez.

        Kaynağı uydurmak cevabı geçersiz kılmaz; yalnız kaynağı geçersiz kılar.
        """
        from app.modules.assessment.grading import grade_with_llm

        chunk_id = uuid4()

        outcome = await grade_with_llm(
            FakeCompletion(_verdict(90, uuid4())),
            payload=OpenPayload.model_validate(ESSAY_PAYLOAD),
            given="Cevap.",
            sources=[(chunk_id, DEADLOCK_TEXTS[0])],
        )

        assert outcome.score == 90
        assert outcome.evidence_chunk_id is None

    async def test_saglayici_patlarsa_degerlendirme_tamamlanmaz(self) -> None:
        from app.modules.assessment.grading import grade_with_llm

        class BrokenCompletion:
            calls = 0

            async def complete(self, *, system: str, user: str) -> str:
                del system, user
                BrokenCompletion.calls += 1
                raise RuntimeError("sağlayıcı 503")

        outcome = await grade_with_llm(
            BrokenCompletion(),
            payload=OpenPayload.model_validate(ESSAY_PAYLOAD),
            given="Cevap.",
            sources=[(uuid4(), DEADLOCK_TEXTS[0])],
        )

        assert BrokenCompletion.calls == 2
        assert outcome.graded is False


# ---------------------------------------------------------------------------
# PR incelemesi kalem 2 regresyonu (mevcut kapsam)
# ---------------------------------------------------------------------------


class TestMasteryAndAnswersCourseIsolation:
    """PR incelemesi kalem 2 regresyon testi.

    mastery_self_insert / mastery_self_update ve answers_self_insert politikaları
    yalnızca user_id kontrol ediyordu; kullanıcının o dersin üyesi olup olmadığına
    bakmıyordu. Üye olunmayan bir derse mastery satırı yazılabiliyordu (elle psql ile
    kanıtlandı: bkz. PR_INCELEME_2026-08-06.md kalem 2). Bu test, düzeltmenin gerçekten
    kapattığını otomatik olarak doğrular.
    """

    async def test_uye_olmayan_ders_icin_mastery_satiri_yazilamaz(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        # Burak hiçbir derse üye değil.
        course_id = await _create_course(client, ayse, "COME301")
        topic_response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse
        )
        topic_id = UUID(topic_response.json()["id"])

        with pytest.raises(DBAPIError):
            async with rls_session(burak_id) as session:
                await session.execute(
                    text(
                        "INSERT INTO mastery (user_id, topic_id, course_id, score, "
                        "answer_count) VALUES (:uid, :tid, :cid, 0.8, 1)"
                    ),
                    {"uid": burak_id, "tid": topic_id, "cid": UUID(course_id)},
                )

    async def test_uye_olan_kullanici_kendi_mastery_satirini_yazabilir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """Düzeltmenin aşırıya kaçıp meşru yazımı da engellemediğinin kontrolü."""
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await client.post(
            f"/courses/{course_id}/members",
            json={"email": "burak@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )
        topic_response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse
        )
        topic_id = UUID(topic_response.json()["id"])

        async with rls_session(burak_id) as session:
            await session.execute(
                text(
                    "INSERT INTO mastery (user_id, topic_id, course_id, score, "
                    "answer_count) VALUES (:uid, :tid, :cid, 0.8, 1)"
                ),
                {"uid": burak_id, "tid": topic_id, "cid": UUID(course_id)},
            )
