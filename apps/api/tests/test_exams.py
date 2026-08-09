"""Sınav provası testleri — T032/T033.

Kapsanan vakalar (tasks.md T033): (3) exam modunda ipucu reddi, (4) süre dolunca
cevap kabul edilmez ve boş sorular puana katılmaz, (6) boş onaylı havuzda sınav
reddi, (7) oturuma dönüşte kalan süre korunur, (8) practice modda ipucu açık +
anında geri bildirim. Vaka (1), (2) ve (5) havuz tarafındadır: `test_assessment.py`.

Zamanı hızlandırmak için `sleep` yok: oturumun `started_at`/`expires_at` sütunları
sahip bağlantısıyla geriye alınır. Süre karşılaştırması zaten veritabanı saatine
göre yapıldığı için bu, gerçekten süre geçmiş bir oturumla aynı durumdur.

Kurulum yardımcıları `test_assessment.py`'den gelir; iki dosyada iki kopya kurulum
tutulmaz (Anayasa XI).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import rls_session
from app.models.assessment import QuestionType
from tests.conftest import UserFactory
from tests.test_assessment import (
    DEADLOCK_TEXTS,
    _create_course,
    create_topic,
    enroll,
    mcq_payload,
    seed_chunks,
    seed_question,
    short_answer_payload,
)

EXAM_DURATION_SECONDS = 20 * 60  # Settings.exam_duration_minutes varsayılanı


class ExamFixture:
    """Bir ders, bir eğitmen, bir öğrenci ve onaylı bir soru havuzu."""

    def __init__(
        self,
        *,
        course_id: str,
        instructor: dict[str, str],
        instructor_id: UUID,
        student: dict[str, str],
        student_id: UUID,
        topic_id: UUID,
        chunk_ids: list[UUID],
        question_ids: list[UUID],
    ) -> None:
        self.course_id = course_id
        self.instructor = instructor
        self.instructor_id = instructor_id
        self.student = student
        self.student_id = student_id
        self.topic_id = topic_id
        self.chunk_ids = chunk_ids
        self.question_ids = question_ids


async def build_course(
    client: AsyncClient,
    users: UserFactory,
    admin_engine: AsyncEngine,
    *,
    approved: int = 2,
    drafts: int = 0,
    short_answer: bool = False,
) -> ExamFixture:
    instructor_id = await users.create("ayse@dogus.edu.tr")
    instructor = users.auth(instructor_id)
    student_id = await users.create("burak@dogus.edu.tr")
    course_id = await _create_course(client, instructor, "COME301")
    await enroll(client, instructor, course_id, "burak@dogus.edu.tr")
    topic_id = await create_topic(client, instructor, course_id, "Deadlock")
    chunk_ids = await seed_chunks(
        admin_engine, course_id=UUID(course_id), uploaded_by=instructor_id, texts=DEADLOCK_TEXTS
    )

    question_ids: list[UUID] = []
    for index in range(approved):
        use_short = short_answer and index == 0
        question_ids.append(
            await seed_question(
                admin_engine,
                course_id=UUID(course_id),
                topic_id=topic_id,
                source_chunk_id=chunk_ids[index % len(chunk_ids)],
                payload=short_answer_payload() if use_short else mcq_payload(chunk_ids),
                question_type=QuestionType.OPEN if use_short else QuestionType.MCQ,
                status="approved",
                reviewed_by=instructor_id,
            )
        )
    for _ in range(drafts):
        await seed_question(
            admin_engine,
            course_id=UUID(course_id),
            topic_id=topic_id,
            source_chunk_id=chunk_ids[0],
            payload=mcq_payload(chunk_ids),
        )

    return ExamFixture(
        course_id=course_id,
        instructor=instructor,
        instructor_id=instructor_id,
        student=users.auth(student_id),
        student_id=student_id,
        topic_id=topic_id,
        chunk_ids=chunk_ids,
        question_ids=question_ids,
    )


async def start(client: AsyncClient, fixture: ExamFixture, mode: str) -> dict:
    response = await client.post(
        f"/courses/{fixture.course_id}/exams", json={"mode": mode}, headers=fixture.student
    )
    assert response.status_code == 201, response.text
    return response.json()


async def rewind(admin_engine: AsyncEngine, session_id: str, *, minutes: int) -> None:
    """Oturumu geriye alır: süre gerçekten geçmiş gibi davranır."""
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE exam_sessions SET started_at = started_at - make_interval(mins => :m), "
                "expires_at = expires_at - make_interval(mins => :m) WHERE id = :id"
            ),
            {"m": minutes, "id": UUID(session_id)},
        )


# ---------------------------------------------------------------------------
# Oturum açma — vaka 6
# ---------------------------------------------------------------------------


class TestExamStart:
    async def test_bos_onayli_havuzda_sinav_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Vaka 6: onaylı soru yoksa oturum açılmaz — 'kaynak yoksa cevap yok'."""
        fixture = await build_course(client, users, admin_engine, approved=0, drafts=3)

        response = await client.post(
            f"/courses/{fixture.course_id}/exams",
            json={"mode": "exam"},
            headers=fixture.student,
        )

        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "conflict"
        assert "onaylanmış soru yok" in response.json()["error"]["message"]

    async def test_oturuma_yalnizca_onayli_sorular_girer(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine, approved=1, drafts=4)

        body = await start(client, fixture, "exam")

        assert body["question_count"] == 1
        assert [question["id"] for question in body["questions"]] == [str(fixture.question_ids[0])]

    async def test_exam_modunda_sure_sunucudan_gelir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)

        body = await start(client, fixture, "exam")

        assert body["expires_at"] is not None
        assert EXAM_DURATION_SECONDS - 10 <= body["remaining_seconds"] <= EXAM_DURATION_SECONDS
        assert body["expired"] is False

    async def test_practice_modu_suresizdir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)

        body = await start(client, fixture, "practice")

        assert body["expires_at"] is None
        assert body["remaining_seconds"] is None
        assert body["expired"] is False

    async def test_soru_listesi_cevap_anahtari_tasimaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)

        body = await start(client, fixture, "exam")

        for question in body["questions"]:
            assert set(question["payload"]) == {"stem", "options"}


# ---------------------------------------------------------------------------
# Oturuma dönüş — vaka 7
# ---------------------------------------------------------------------------


class TestSessionResume:
    async def test_baglanti_koparsa_kalan_sureyle_devam_edilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Vaka 7: sayaç istemcide, süre sunucuda. 5 dakika geçmişse 15 dakika kalır."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        await rewind(admin_engine, session_id, minutes=5)

        response = await client.get(
            f"/courses/{fixture.course_id}/exams/{session_id}", headers=fixture.student
        )

        assert response.status_code == 200, response.text
        remaining = response.json()["remaining_seconds"]
        assert 15 * 60 - 10 <= remaining <= 15 * 60

    async def test_baska_ogrencinin_oturumu_gorunmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        ceren_id = await users.create("ceren@dogus.edu.tr")
        await enroll(client, fixture.instructor, fixture.course_id, "ceren@dogus.edu.tr")

        response = await client.get(
            f"/courses/{fixture.course_id}/exams/{session_id}", headers=users.auth(ceren_id)
        )

        assert response.status_code == 404

    async def test_olmayan_oturum_404(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)

        response = await client.get(
            f"/courses/{fixture.course_id}/exams/{uuid4()}", headers=fixture.student
        )

        assert response.status_code == 404

    async def test_istemci_expires_at_i_ileri_atsa_bile_sure_uzamaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Karar 2: kalan süre `min(expires_at, started_at + süre)` ile kırpılır.

        Test önce açığın gerçek olduğunu gösterir — öğrenci kendi oturum satırının
        `expires_at`'ini RLS altında yazabiliyor — sonra bunun kullanıcıya yansımadığını
        doğrular. Yapısal kapanış `0005` kolon GRANT'ine bağlıdır; bu test o gelene
        kadarki uygulama katmanı kırpmasını sabitler.
        """
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]

        async with rls_session(fixture.student_id) as session:
            await session.execute(
                text(
                    "UPDATE exam_sessions SET expires_at = now() + interval '1 day' WHERE id = :id"
                ),
                {"id": UUID(session_id)},
            )

        response = await client.get(
            f"/courses/{fixture.course_id}/exams/{session_id}", headers=fixture.student
        )

        assert response.json()["remaining_seconds"] <= EXAM_DURATION_SECONDS


# ---------------------------------------------------------------------------
# Cevap gönderme — vaka 3, 4
# ---------------------------------------------------------------------------


class TestAnswerSubmission:
    async def test_exam_modunda_puan_cevapla_birlikte_donmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Geri bildirim sınav sonunda: puan yazılır ama gösterilmez."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]

        response = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={"question_id": str(fixture.question_ids[0]), "given": "C"},
            headers=fixture.student,
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["recorded"] is True
        assert body["score"] is None
        assert body["is_correct"] is None
        assert body["solution"] is None

    async def test_ayni_soruya_ikinci_cevap_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        payload = {"question_id": str(fixture.question_ids[0]), "given": "C"}

        first = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json=payload,
            headers=fixture.student,
        )
        second = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={**payload, "given": "A"},
            headers=fixture.student,
        )

        assert first.status_code == 201
        assert second.status_code == 409
        assert "tek deneme" in second.json()["error"]["message"]

    async def test_exam_modunda_ipucu_kademesi_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Vaka 3 (ilk kapı): ipucu kullanıldığını beyan eden cevap sınavda geçmez."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]

        response = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={"question_id": str(fixture.question_ids[0]), "given": "C", "hint_level": 2},
            headers=fixture.student,
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    async def test_oturumda_olmayan_soru_cevaplanamaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]

        response = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={"question_id": str(uuid4()), "given": "C"},
            headers=fixture.student,
        )

        assert response.status_code == 404

    async def test_sure_dolunca_cevap_kabul_edilmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Vaka 4 (ilk yarısı)."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        await rewind(admin_engine, session_id, minutes=25)

        response = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={"question_id": str(fixture.question_ids[0]), "given": "C"},
            headers=fixture.student,
        )

        assert response.status_code == 409
        assert "süresi doldu" in response.json()["error"]["message"]

    async def test_sure_dolan_oturum_expired_isaretlenir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        await rewind(admin_engine, session_id, minutes=25)

        body = (
            await client.get(
                f"/courses/{fixture.course_id}/exams/{session_id}", headers=fixture.student
            )
        ).json()

        assert body["expired"] is True
        assert body["remaining_seconds"] == 0


# ---------------------------------------------------------------------------
# Practice modu — vaka 8
# ---------------------------------------------------------------------------


class TestPracticeMode:
    async def test_aninda_geri_bildirim_ve_neden_yanlis(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Vaka 8: cevapla birlikte puan, çözüm ve çeldiricinin çeliştiği kaynak."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "practice"))["id"]

        response = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={"question_id": str(fixture.question_ids[0]), "given": "D"},
            headers=fixture.student,
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["is_correct"] is False
        assert body["score"] == 0
        # FR-021: dosya adı ve konum chunk metadata'sından gelir.
        assert body["why_wrong"]["file_name"] == "isletim-sistemleri.pdf"
        assert body["why_wrong"]["location"].startswith("Sayfa")
        assert body["solution"]["answer_key"] == "C"

    async def test_dogru_cevap_tam_puan_alir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "practice"))["id"]

        body = (
            await client.post(
                f"/courses/{fixture.course_id}/exams/{session_id}/answers",
                json={"question_id": str(fixture.question_ids[0]), "given": "C"},
                headers=fixture.student,
            )
        ).json()

        assert body["is_correct"] is True
        assert body["score"] == 100
        assert body["why_wrong"] is None

    async def test_practice_modunda_ipucu_kaynaktan_gelir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "practice"))["id"]

        first = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/hint",
            json={"question_id": str(fixture.question_ids[0]), "hint_level": 1},
            headers=fixture.student,
        )
        deeper = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/hint",
            json={"question_id": str(fixture.question_ids[0]), "hint_level": 4},
            headers=fixture.student,
        )

        assert first.status_code == 200, first.text
        assert "isletim-sistemleri.pdf" in first.json()["text"]
        # Kademe yükseldikçe kaynaktan daha çoğu açılır.
        assert len(deeper.json()["text"]) > len(first.json()["text"])
        assert deeper.json()["source"]["chunk_id"] == str(fixture.chunk_ids[0])

    async def test_exam_modunda_ipucu_ucu_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Vaka 3 (ikinci kapı): ipucu ucu sınav modunda 403 döner."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]

        response = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/hint",
            json={"question_id": str(fixture.question_ids[0]), "hint_level": 1},
            headers=fixture.student,
        )

        assert response.status_code == 403
        assert "ipucu kapalıdır" in response.json()["error"]["message"]

    async def test_kisa_cevap_llm_olmadan_degerlendirilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Karar 4: kısa cevap deterministiktir, sağlayıcı bağlı olmasa da çalışır."""
        fixture = await build_course(client, users, admin_engine, short_answer=True)
        session_id = (await start(client, fixture, "practice"))["id"]

        body = (
            await client.post(
                f"/courses/{fixture.course_id}/exams/{session_id}/answers",
                json={"question_id": str(fixture.question_ids[0]), "given": "Döngüsel Bekleme"},
                headers=fixture.student,
            )
        ).json()

        assert body["graded"] is True
        assert body["score"] == 100

    async def test_llm_gerektiren_soru_saglayicisiz_uydurma_puan_almaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """FR-020: değerlendirilemeyen cevaba uydurma puan verilmez."""
        fixture = await build_course(client, users, admin_engine, approved=0)
        essay_id = await seed_question(
            admin_engine,
            course_id=UUID(fixture.course_id),
            topic_id=fixture.topic_id,
            source_chunk_id=fixture.chunk_ids[0],
            payload={
                "prompt": "Deadlock'un dört koşulunu açıklayın.",
                "answer_key": "Karşılıklı dışlama, tut ve bekle, kesilemezlik, döngüsel bekleme.",
                "key_points": ["karşılıklı dışlama", "döngüsel bekleme"],
                "rubric": [{"point": "Dört koşulu sayar", "weight": 100}],
            },
            question_type=QuestionType.OPEN,
            status="approved",
            reviewed_by=fixture.instructor_id,
        )
        session_id = (await start(client, fixture, "practice"))["id"]

        body = (
            await client.post(
                f"/courses/{fixture.course_id}/exams/{session_id}/answers",
                json={"question_id": str(essay_id), "given": "Dört koşul vardır."},
                headers=fixture.student,
            )
        ).json()

        assert body["recorded"] is True
        assert body["graded"] is False
        assert body["score"] is None
        assert "tamamlanamadı" in body["message"]


# ---------------------------------------------------------------------------
# Bitirme — vaka 4'ün ikinci yarısı
# ---------------------------------------------------------------------------


class TestExamFinish:
    async def test_cevapsiz_sorular_bos_sayilir_puana_katilmaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Vaka 4: iki sorudan biri doğru cevaplanır, diğeri boş kalır → puan 100."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={"question_id": str(fixture.question_ids[0]), "given": "C"},
            headers=fixture.student,
        )
        await rewind(admin_engine, session_id, minutes=25)

        response = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/finish", headers=fixture.student
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["answered_count"] == 1
        assert body["unanswered_count"] == 1
        # Boş soru yanlış sayılsaydı puan 50 olurdu.
        assert body["score"] == 100.0
        assert "boş bırakıldı" in body["message"]

    async def test_bitiste_geri_bildirim_ve_cozum_acilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={"question_id": str(fixture.question_ids[0]), "given": "A"},
            headers=fixture.student,
        )

        body = (
            await client.post(
                f"/courses/{fixture.course_id}/exams/{session_id}/finish",
                headers=fixture.student,
            )
        ).json()

        result = body["results"][0]
        assert result["is_correct"] is False
        assert result["why_wrong"]["file_name"] == "isletim-sistemleri.pdf"
        assert result["solution"]["answer_key"] == "C"

    async def test_hic_cevap_yoksa_puan_gosterilmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]

        body = (
            await client.post(
                f"/courses/{fixture.course_id}/exams/{session_id}/finish",
                headers=fixture.student,
            )
        ).json()

        # 0 değil None: "hiç cevaplamadın" ile "hepsini yanlış yaptın" aynı şey değil.
        assert body["score"] is None
        assert body["answered_count"] == 0
        assert "puan hesaplanmadı" in body["message"]

    async def test_ikinci_kez_bitirilemez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/finish", headers=fixture.student
        )

        response = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/finish", headers=fixture.student
        )

        assert response.status_code == 409

    async def test_bitmis_oturuma_cevap_gonderilemez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/finish", headers=fixture.student
        )

        response = await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={"question_id": str(fixture.question_ids[0]), "given": "C"},
            headers=fixture.student,
        )

        assert response.status_code == 409


# ---------------------------------------------------------------------------
# T037 — mastery entegrasyonu
# ---------------------------------------------------------------------------


async def _mastery_rows(user_id: UUID) -> list[tuple[float, int]]:
    async with rls_session(user_id) as session:
        rows = (await session.execute(text("SELECT score, answer_count FROM mastery"))).all()
    return [(float(row.score), row.answer_count) for row in rows]


class TestMasteryIntegration:
    async def test_sinav_bitisinde_mastery_islenir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={"question_id": str(fixture.question_ids[0]), "given": "C"},
            headers=fixture.student,
        )

        before = await _mastery_rows(fixture.student_id)
        await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/finish", headers=fixture.student
        )
        after = await _mastery_rows(fixture.student_id)

        assert before == []
        assert after == [(1.0, 1)]

    async def test_practice_modunda_mastery_ilk_cevapta_islenir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """FR-017: practice modda mastery bitişi beklemez."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "practice"))["id"]

        await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={"question_id": str(fixture.question_ids[0]), "given": "C"},
            headers=fixture.student,
        )

        assert await _mastery_rows(fixture.student_id) == [(1.0, 1)]

    async def test_ipucu_kademesi_mastery_puanini_kirpar(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """İpucuyla bulunan doğru cevap tam puan getirmez (çarpan 2 → 0.70)."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "practice"))["id"]

        await client.post(
            f"/courses/{fixture.course_id}/exams/{session_id}/answers",
            json={
                "question_id": str(fixture.question_ids[0]),
                "given": "C",
                "hint_level": 2,
            },
            headers=fixture.student,
        )

        assert await _mastery_rows(fixture.student_id) == [(0.70, 1)]
