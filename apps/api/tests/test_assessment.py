"""Ölçme (assessment) testleri — konu, soru havuzu, üretim ve puanlama.

Sınav oturumu akışı `test_exams.py`'de; bu dosya havuzu ve onun iki pazarlıksız
kuralını kapsar:

1. **Öğrenci taslak soruyu göremez** (T033 vaka 2). `0004`'ün en kritik RLS
   politikası budur ve iki katmanla korunur — uygulama filtresi + `questions_read`.
   `TestDraftInvisibility` iki katmanı AYRI AYRI sınar: biri kaldırıldığında
   diğerinin hâlâ tuttuğu görülsün diye.
2. **Cevap anahtarı öğrenciye sızmaz.** Onaylı bir soru bile öğrenciye
   `public_payload()` beyaz listesinden geçerek gider.

Ders/üyelik/konu/belge/soru satırlarını `tests/factories.py` yazar. Korpus
sabitleri (`DEADLOCK_TEXTS`, payload üreteçleri) ve sahte LLM de oradadır:
`test_exams`, `test_blueprint` ve `test_rate_limit` aynılarını kullanıyor ve
ortak fabrikanın üç-dosya eşiği aşılmış durumda (Anayasa XI).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.contracts import RetrievedChunk
from app.core import text_tr
from app.core.db import rls_session
from app.models.assessment import QuestionType
from app.modules.assessment import question_gen
from app.modules.generation.llm import LlmUnavailableError
from app.schemas.assessment import McqPayload, OpenPayload
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

# ---------------------------------------------------------------------------
# Kurulum yardımcıları
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PoolFixture:
    """Soru havuzu testlerinin ortak zemini: ders, iki rol, konu ve kaynak parçalar.

    On iki test bu beş adımı elle yazıyordu. Sıra rastgele değil zorunlu — soru
    bir konuya, konu bir derse, kaynak bir belgeye bağlı ve öğrenci derse üye
    olmadan hiçbir görünürlük iddiası kurulamıyor. Adımların elle tekrarlanması
    bir testin neyi kurduğunu değil, kurulumun kaç satır sürdüğünü okutuyordu.
    """

    course_id: UUID
    instructor_id: UUID
    instructor: dict[str, str]
    student_id: UUID
    student: dict[str, str]
    topic_id: UUID
    chunk_ids: list[UUID]


async def build_pool(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    *,
    code: str = "COME301",
    texts: list[str] = DEADLOCK_TEXTS,
) -> PoolFixture:
    """Ders + eğitmen + kayıtlı öğrenci + konu + kaynak parçalar.

    `texts` boş verilirse belge HİÇ yazılmaz: "materyal yok" senaryosunun
    kurulumu sıfır parçalı bir belge satırı değil, belgenin hiç olmamasıdır.

    Öğrenci koşulsuz açılıyor: bugün hiçbir test "derste başka üye yok" diye bir
    iddia kurmuyor, buna karşılık taslak görünmezliği ve yetki testlerinin çoğu
    kayıtlı bir öğrenci olmadan kurulamıyor.
    """
    instructor_id = await users.create("ayse@dogus.edu.tr")
    instructor = users.auth(instructor_id)
    student_id = await users.create("burak@dogus.edu.tr")
    course_id = await create_course(client, instructor, code)
    await enroll_student(client, instructor, course_id, "burak@dogus.edu.tr")
    topic_id = await create_topic(client, instructor, course_id, "Deadlock")

    chunk_ids: list[UUID] = []
    if texts:
        seeded = await seed_document(
            admin_engine, course_id=course_id, uploaded_by=instructor_id, passages=texts
        )
        chunk_ids = seeded.chunk_ids

    return PoolFixture(
        course_id=course_id,
        instructor_id=instructor_id,
        instructor=instructor,
        student_id=student_id,
        student=users.auth(student_id),
        topic_id=topic_id,
        chunk_ids=chunk_ids,
    )


async def generate(
    pool: PoolFixture,
    *,
    completion: FakeCompletion,
    chunks: list[RetrievedChunk],
    count: int = 1,
) -> question_gen.GenerationReport:
    """Eğitmenin RLS oturumunda soru üretir.

    Üretimin eğitmen oturumunda koşması kurulumun süsü değil şartı:
    `questions_insert` politikası yazanın dersin eğitmeni olmasını istiyor.
    Oturumu düşüren bir sadeleştirme testleri sessizce anlamsızlaştırırdı.
    """
    async with rls_session(pool.instructor_id) as session:
        topic = await _load_topic(session, pool.topic_id)
        return await question_gen.generate_questions(
            session,
            course_id=pool.course_id,
            topic=topic,
            question_type=QuestionType.MCQ,
            count=count,
            created_by=pool.instructor_id,
            retriever=FakeRetriever(chunks),
            completion=completion,
        )


# ---------------------------------------------------------------------------
# Konular (mevcut kapsam)
# ---------------------------------------------------------------------------


class TestTopicCreation:
    async def test_egitmen_konu_olusturur(self, client: AsyncClient, users: UserFactory) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await create_course(client, ayse, "COME301")

        response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Deadlock"
        assert body["course_id"] == str(course_id)

    async def test_ogrenci_konu_olusturamaz(self, client: AsyncClient, users: UserFactory) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")

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
        course_id = await create_course(client, ayse, "COME301")

        response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=disari
        )

        # Dersin varlığı sızdırılmaz: 403 değil 404.
        assert response.status_code == 404

    async def test_ayni_isimde_ikinci_konu_reddedilir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await create_course(client, ayse, "COME301")
        await create_topic(client, ayse, course_id, "Deadlock")

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
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")
        await create_topic(client, ayse, course_id, "Deadlock")
        await create_topic(client, ayse, course_id, "CPU Zamanlama")

        response = await client.get(f"/courses/{course_id}/topics", headers=users.auth(burak_id))

        assert response.status_code == 200
        names = {topic["name"] for topic in response.json()}
        assert names == {"Deadlock", "CPU Zamanlama"}

    async def test_baska_dersin_konusu_donmez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """İzolasyon: course_id istemciden gelse bile başka dersin verisi sızmaz (Anayasa II)."""
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_a = await create_course(client, ayse, "COME301")
        course_b = await create_course(client, ayse, "COME302")
        await create_topic(client, ayse, course_a, "Deadlock")
        await create_topic(client, ayse, course_b, "Bellek Yönetimi")

        response_a = await client.get(f"/courses/{course_a}/topics", headers=ayse)
        response_b = await client.get(f"/courses/{course_b}/topics", headers=ayse)

        assert [t["name"] for t in response_a.json()] == ["Deadlock"]
        assert [t["name"] for t in response_b.json()] == ["Bellek Yönetimi"]

    async def test_uye_olmayan_kullanici_listeyi_goremez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        disari = users.auth(await users.create("disari@dogus.edu.tr"))
        course_id = await create_course(client, ayse, "COME301")
        await create_topic(client, ayse, course_id, "Deadlock")

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
        pool = await build_pool(client, users, admin_engine)
        draft_id = await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
        )
        approved_id = await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
            status="approved",
            reviewed_by=pool.instructor_id,
        )

        student = await client.get(f"/courses/{pool.course_id}/questions", headers=pool.student)
        instructor = await client.get(
            f"/courses/{pool.course_id}/questions", headers=pool.instructor
        )

        assert student.status_code == 403, student.text
        assert student.json()["error"]["code"] == "permission_denied"
        assert {item["id"] for item in instructor.json()["items"]} == {
            str(draft_id),
            str(approved_id),
        }

    async def test_ogrenci_status_parametresiyle_taslak_isteyemez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Durum filtresi, öğrenciye kapalı soru bankasını açamaz."""
        pool = await build_pool(client, users, admin_engine)
        await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
        )

        response = await client.get(
            f"/courses/{pool.course_id}/questions?status=draft", headers=pool.student
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    async def test_rls_katmani_tek_basina_da_taslagi_gizler(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """İkinci katman: uygulama filtresi hiç yokken bile RLS taslağı vermez.

        Ham SQL ile — yani `questions_read` politikasından başka hiçbir süzgeç
        olmadan — öğrencinin oturumunda sorgu koşulur. Politika bozulursa bu test
        kırmızıya döner; kanıt olarak politika bilerek düşürülüp koşuldu ve
        gerçekten kırmızı yandı (bkz. KARARLAR_SERIT4.md §RLS kanıtı).
        """
        pool = await build_pool(client, users, admin_engine)
        await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
        )

        async with rls_session(pool.student_id) as session:
            rows = (await session.execute(text("SELECT id, status FROM questions"))).all()
        assert rows == []

        async with rls_session(pool.instructor_id) as session:
            rows = (await session.execute(text("SELECT status FROM questions"))).all()
        assert [row.status for row in rows] == ["draft"]

    async def test_ogrenciye_cevap_anahtari_sizmaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Onaylı soru bile öğrenciye beyaz listeden geçerek gider."""
        pool = await build_pool(client, users, admin_engine)
        question_id = await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
            status="approved",
            reviewed_by=pool.instructor_id,
        )

        student_bank = await client.get(
            f"/courses/{pool.course_id}/questions", headers=pool.student
        )
        practice = await client.post(
            f"/courses/{pool.course_id}/exams",
            json={"mode": "practice"},
            headers=pool.student,
        )
        instructor = (
            await client.get(f"/courses/{pool.course_id}/questions", headers=pool.instructor)
        ).json()["items"][0]

        assert student_bank.status_code == 403
        assert practice.status_code == 201, practice.text
        student = practice.json()["questions"][0]
        assert student["id"] == str(question_id)
        assert set(student["payload"]) == {"stem", "options"}
        assert "answer_key" in instructor["payload"]
        assert "distractor_sources" in instructor["payload"]


# ---------------------------------------------------------------------------
# Onay / red
# ---------------------------------------------------------------------------


class TestQuestionReview:
    async def test_egitmen_onaylayinca_ogrenci_kagidinda_gorur(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        pool = await build_pool(client, users, admin_engine)
        question_id = await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
        )

        before = await client.post(
            f"/courses/{pool.course_id}/exams",
            json={"mode": "practice"},
            headers=pool.student,
        )
        approve = await client.post(
            f"/courses/{pool.course_id}/questions/{question_id}/approve", headers=pool.instructor
        )
        after = await client.post(
            f"/courses/{pool.course_id}/exams",
            json={"mode": "practice"},
            headers=pool.student,
        )

        assert before.status_code == 409
        assert approve.status_code == 200, approve.text
        body = approve.json()
        assert body["status"] == "approved"
        # questions_reviewed_consistency CHECK'i ikisini birden ister.
        assert body["reviewed_by"] == str(pool.instructor_id)
        assert body["reviewed_at"] is not None
        assert after.status_code == 201, after.text
        assert [item["id"] for item in after.json()["questions"]] == [str(question_id)]

    async def test_reddedilen_soru_ogrenciye_gorunmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        pool = await build_pool(client, users, admin_engine)
        question_id = await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
        )

        reject = await client.post(
            f"/courses/{pool.course_id}/questions/{question_id}/reject", headers=pool.instructor
        )
        practice = await client.post(
            f"/courses/{pool.course_id}/exams",
            json={"mode": "practice"},
            headers=pool.student,
        )

        assert reject.status_code == 200, reject.text
        assert reject.json()["status"] == "rejected"
        assert practice.status_code == 409

    async def test_incelenmis_soru_ikinci_kez_degistirilemez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        pool = await build_pool(client, users, admin_engine)
        question_id = await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
        )
        first = await client.post(
            f"/courses/{pool.course_id}/questions/{question_id}/approve",
            headers=pool.instructor,
        )

        second = await client.post(
            f"/courses/{pool.course_id}/questions/{question_id}/reject",
            headers=pool.instructor,
        )

        assert first.status_code == 200, first.text
        assert second.status_code == 409, second.text
        assert second.json()["error"]["code"] == "question_immutable"

    async def test_ogrenci_onaylayamaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        pool = await build_pool(client, users, admin_engine)
        question_id = await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
        )

        response = await client.post(
            f"/courses/{pool.course_id}/questions/{question_id}/approve", headers=pool.student
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    async def test_baska_dersin_sorusu_onaylanamaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Yol parametresindeki ders kimliği yetki değildir (Anayasa II)."""
        pool = await build_pool(client, users, admin_engine)
        # Soru havuzdaki derste; onay isteği aynı eğitmenin BAŞKA dersinin
        # yolundan geliyor. Eğitmen ikisinde de yetkili, yani reddin sebebi
        # yetki değil yalnızca yolun sorunun dersiyle eşleşmemesi olabilir.
        diger_ders = await create_course(client, pool.instructor, "COME302")
        question_id = await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
        )

        response = await client.post(
            f"/courses/{diger_ders}/questions/{question_id}/approve", headers=pool.instructor
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# T033 vaka 1 — soru üretimi şema geçerliliği
# ---------------------------------------------------------------------------


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
        pool = await build_pool(client, users, admin_engine)
        question_id = await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
        )
        async with admin_engine.begin() as conn:
            document_id = await conn.scalar(
                text("SELECT document_id FROM chunks WHERE id = :c"), {"c": pool.chunk_ids[0]}
            )

        # Önce belge silinemiyor: soru onu kilitliyor.
        kilitli = await client.delete(
            f"/courses/{pool.course_id}/documents/{document_id}", headers=pool.instructor
        )
        assert kilitli.status_code == 409, kilitli.text

        silme = await client.delete(
            f"/courses/{pool.course_id}/questions/{question_id}", headers=pool.instructor
        )
        assert silme.status_code == 204, silme.text

        # Kilit açıldı: mesajın önerdiği çıkış yolu gerçekten çalışıyor.
        acildi = await client.delete(
            f"/courses/{pool.course_id}/documents/{document_id}", headers=pool.instructor
        )
        assert acildi.status_code == 204, acildi.text

    async def test_ogrenci_soru_silemez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        pool = await build_pool(client, users, admin_engine)
        question_id = await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
        )

        response = await client.delete(
            f"/courses/{pool.course_id}/questions/{question_id}", headers=pool.student
        )

        assert response.status_code == 403

    async def test_cevaplanmis_soru_silinmez_ve_sebebi_soylenir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Bir öğrencinin cevabının sorusunu silmek, o cevabı okunamaz kılardı.

        Veritabanı bunu `answers.question_id` RESTRICT ile zaten reddediyor;
        sınanan şey, uçun bunu 500 yerine anlaşılır bir 409'a çevirmesi.
        """
        pool = await build_pool(client, users, admin_engine)
        question_id = await seed_question(
            admin_engine,
            course_id=pool.course_id,
            topic_id=pool.topic_id,
            source_chunk_id=pool.chunk_ids[0],
            payload=mcq_payload(pool.chunk_ids),
            status="approved",
            reviewed_by=pool.instructor_id,
        )
        async with admin_engine.begin() as conn:
            exam_id = await conn.scalar(
                text(
                    "INSERT INTO exam_sessions (course_id, user_id, mode, question_ids) "
                    "VALUES (:c, :u, 'practice', ARRAY[:q]::uuid[]) RETURNING id"
                ),
                {"c": pool.course_id, "u": pool.student_id, "q": question_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO answers (session_id, question_id, course_id, given, "
                    "is_correct, score) VALUES (:s, :q, :c, 'A', true, 100)"
                ),
                {"s": exam_id, "q": question_id, "c": pool.course_id},
            )

        response = await client.delete(
            f"/courses/{pool.course_id}/questions/{question_id}", headers=pool.instructor
        )

        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "conflict"
        assert "cevaplanmış" in response.json()["error"]["message"]


class TestQuestionGeneration:
    async def test_gecerli_cikti_havuza_draft_yazilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        pool = await build_pool(client, users, admin_engine)
        chunks = retrieved(pool.chunk_ids, DEADLOCK_TEXTS)

        report = await generate(
            pool,
            chunks=chunks,
            count=2,
            completion=FakeCompletion(_mcq_response(pool.chunk_ids[0], count=2)),
        )

        assert report.accepted == 2
        assert report.rejected == 0
        assert all(question.status.value == "draft" for question in report.questions)
        # distractor_sources modelden istenmedi; bizim eşlememizle doldu.
        payload = McqPayload.model_validate(report.questions[0].payload)
        assert set(payload.distractor_sources) == {"A", "B", "D"}
        assert set(payload.distractor_sources.values()) <= set(pool.chunk_ids)

    async def test_bozuk_sema_iki_denemede_de_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """SC-009: şemadan geçmeyen çıktı havuza YAZILMAZ, bir kez yeniden denenir."""
        pool = await build_pool(client, users, admin_engine)
        completion = FakeCompletion('{"questions": [{"stem": "eksik"}]}')

        report = await generate(
            pool,
            chunks=retrieved(pool.chunk_ids, DEADLOCK_TEXTS),
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
        pool = await build_pool(client, users, admin_engine)
        chunks = retrieved(pool.chunk_ids, DEADLOCK_TEXTS)

        # 1. Model hiç soru döndürmedi: yanıt bile ayrıştırılamadı.
        unparseable = await generate(
            pool,
            chunks=chunks,
            count=2,
            completion=FakeCompletion("elbette, işte sorular:"),
        )
        # 2. Model iki soru döndürdü, biri şemadan geçti.
        half_valid = json.dumps(
            {
                "questions": [
                    json.loads(_mcq_response(pool.chunk_ids[0]))["questions"][0],
                    {"stem": "eksik soru"},
                ]
            }
        )
        mixed = await generate(pool, chunks=chunks, count=2, completion=FakeCompletion(half_valid))

        assert (unparseable.returned, unparseable.accepted, unparseable.rejected) == (0, 0, 0)
        assert len(unparseable.rejection_reasons) == 2, "iki deneme de sebebini bırakmalı"
        assert (mixed.returned, mixed.accepted, mixed.rejected) == (2, 1, 1)

    async def test_uydurulmus_kaynak_sorusu_havuza_girmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Anayasa I: retrieve edilmemiş bir chunk'a atıf yapan soru düşer."""
        pool = await build_pool(client, users, admin_engine)

        report = await generate(
            pool,
            chunks=retrieved(pool.chunk_ids, DEADLOCK_TEXTS),
            completion=FakeCompletion(_mcq_response(uuid4())),
        )

        assert report.accepted == 0
        assert any("kaynak uydurma" in reason for reason in report.rejection_reasons)

    async def test_materyal_yoksa_soru_uretilmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        # `texts=[]`: derse hiç belge yazılmıyor. Boş retriever tek başına da
        # aynı raporu üretirdi, ama o zaman test "arama bulamadı"yı ölçerdi;
        # sınanan iddia "ders boş".
        pool = await build_pool(client, users, admin_engine, texts=[])
        completion = FakeCompletion(_mcq_response(uuid4()))

        report = await generate(pool, chunks=[], completion=completion)

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
        course_id = await create_course(client, ayse, "COME301")
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
        pool = await build_pool(client, users, admin_engine)
        chunks = retrieved(pool.chunk_ids, DEADLOCK_TEXTS)
        question_gen.set_providers(
            retriever_factory=lambda _session: FakeRetriever(chunks),
            completion=FakeCompletion(_mcq_response(pool.chunk_ids[0], count=2)),
        )
        try:
            response = await client.post(
                f"/courses/{pool.course_id}/questions/generate",
                json={"topic_id": str(pool.topic_id), "question_type": "mcq", "count": 2},
                headers=pool.instructor,
            )
        finally:
            question_gen.reset_providers()

        # 201 değil 200: toplu iş, kaçının yazıldığı raporda.
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["accepted"] == 2
        assert body["rejected"] == 0
        assert {question["status"] for question in body["questions"]} == {"draft"}

        student = await client.get(f"/courses/{pool.course_id}/questions", headers=pool.student)
        assert student.status_code == 403, "öğrenci soru bankasını toplu okuyamamalı"


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

    def test_kisa_cevap_aksansiz_yazilsa_da_puan_alir(self) -> None:
        """10 Ağustos ürün kararı: Türkçe klavyesi olmayan öğrenci sıfır almaz.

        Bu davranış eskiden YOKTU — "dongusel bekleme" 0 alıyordu, oysa aynı
        öğrenci retrieval tarafında eşdeğer sayılıyordu (`chunks.fts` unaccent'lı).
        Bedeliyle birlikte gerekçe `core.text_tr.normalize` docstring'inde.
        """
        from app.modules.assessment.grading import grade_short_answer

        payload = OpenPayload.model_validate(short_answer_payload())
        source = uuid4()

        assert grade_short_answer(payload, "dongusel bekleme", source_chunk_id=source).score == 100
        assert grade_short_answer(payload, "Dongusel Bekleme.", source_chunk_id=source).score == 100
        # Kelime sınırı şartı katlamadan SONRA da duruyor: "ram" ile "program".
        assert grade_short_answer(payload, "dongu", source_chunk_id=source).score == 0

    def test_kisa_cevap_yanlissa_kaynak_gosterilir(self) -> None:
        from app.modules.assessment.grading import grade_short_answer

        payload = OpenPayload.model_validate(short_answer_payload())
        source = uuid4()

        outcome = grade_short_answer(payload, "karşılıklı dışlama", source_chunk_id=source)

        assert outcome.score == 0
        assert outcome.is_correct is False
        assert outcome.why_wrong_chunk_id == source

    def test_durak_sozcukler_katlandiktan_sonra_da_eleniyor(self) -> None:
        """`_STOPWORDS` katlanmış saklanıyor; katlanmasaydı dokuzu etkisiz kalırdı.

        Karşılaştırılan taraf `text_tr.tokens` çıktısı ve o taraf aksansız;
        listede "çünkü" yazsaydı hiçbir zaman eşleşmez, sessizce ölürdü.
        """
        assert question_gen._tokens("çünkü değil için çok hiç üzere") == set()
        assert question_gen._tokens("Döngüsel bekleme çünkü") == {"dongusel", "bekleme"}

    def test_puanlama_ortak_katlamayi_kullanir(self) -> None:
        """Kural `core.text_tr`'de; bu test yalnız bağın kopmadığını doğrular.

        Kuralın kendisi (i/İ, aksan, noktalama) `test_text_tr.py`'de sınanıyor;
        burada tekrarlamak iki metnin bir gün ayrışmasına davetiye olurdu.
        """
        assert text_tr.normalize("İŞLETİM Sistemi") == "isletim sistemi"


# ---------------------------------------------------------------------------
# Açık uçlu değerlendirme — şemalı LLM yolu (FR-019, FR-020)
# ---------------------------------------------------------------------------


def _verdict(score: int, chunk_id: UUID | str | None, *, missing: list[str] | None = None) -> str:
    return json.dumps(
        {
            "score": score,
            "eksik_noktalar": missing or [],
            "dayanak_chunk_id": str(chunk_id) if chunk_id else None,
            "rubrik": [{"olcut": "Dört koşulu sayar", "puan": score}],
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

    async def test_uydurulmus_dayanak_puani_da_gecersiz_kilar(self) -> None:
        """Doğrulanamayan dayanakta model puanına güvenilmez."""
        from app.modules.assessment.grading import grade_with_llm

        chunk_id = uuid4()

        outcome = await grade_with_llm(
            FakeCompletion(_verdict(90, uuid4())),
            payload=OpenPayload.model_validate(ESSAY_PAYLOAD),
            given="Cevap.",
            sources=[(chunk_id, DEADLOCK_TEXTS[0])],
        )

        assert outcome.graded is False
        assert outcome.score is None
        assert outcome.evidence_chunk_id is None

    async def test_null_dayanak_puani_gecersiz_kilar(self) -> None:
        from app.modules.assessment.grading import grade_with_llm

        outcome = await grade_with_llm(
            FakeCompletion(_verdict(90, None)),
            payload=OpenPayload.model_validate(ESSAY_PAYLOAD),
            given="Cevap.",
            sources=[(uuid4(), DEADLOCK_TEXTS[0])],
        )

        assert outcome.graded is False
        assert outcome.score is None

    async def test_eksik_rubrik_olcutu_top_level_puana_dusmez(self) -> None:
        from app.modules.assessment.grading import grade_with_llm

        chunk_id = uuid4()
        verdict = json.dumps(
            {
                "score": 100,
                "eksik_noktalar": [],
                "dayanak_chunk_id": str(chunk_id),
                "rubrik": [],
            }
        )

        outcome = await grade_with_llm(
            FakeCompletion(verdict),
            payload=OpenPayload.model_validate(ESSAY_PAYLOAD),
            given="Cevap.",
            sources=[(chunk_id, DEADLOCK_TEXTS[0])],
        )

        assert outcome.graded is False
        assert outcome.score is None

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
        course_id = await create_course(client, ayse, "COME301")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")

        with pytest.raises(DBAPIError):
            async with rls_session(burak_id) as session:
                await session.execute(
                    text(
                        "INSERT INTO mastery (user_id, topic_id, course_id, score, "
                        "answer_count) VALUES (:uid, :tid, :cid, 0.8, 1)"
                    ),
                    {"uid": burak_id, "tid": topic_id, "cid": course_id},
                )

    async def test_uye_olan_kullanici_kendi_mastery_satirini_yazabilir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """Düzeltmenin aşırıya kaçıp meşru yazımı da engellemediğinin kontrolü."""
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")
        topic_id = await create_topic(client, ayse, course_id, "Deadlock")

        async with rls_session(burak_id) as session:
            await session.execute(
                text(
                    "INSERT INTO mastery (user_id, topic_id, course_id, score, "
                    "answer_count) VALUES (:uid, :tid, :cid, 0.8, 1)"
                ),
                {"uid": burak_id, "tid": topic_id, "cid": course_id},
            )
