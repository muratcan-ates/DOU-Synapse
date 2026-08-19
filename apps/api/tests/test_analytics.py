"""Analitik uçları testleri (T038).

İki uç, iki ayrı soru: `analytics/me` "hangi konuya çalışmalıyım?", `analytics/class`
"sınıf nerede zorlanıyor?". Testler ikisinin yetki sınırını, sıralamasını ve
ölçemediği şeyi nasıl bildirdiğini kapsar.

Veri, üretim yolunu kullanarak yazılır: mastery satırları `record_answer` ile RLS
oturumunda oluşturulur. Doğrudan INSERT ile yazılsaydı test, uçların okuduğu şeklin
gerçekten üretilen şekil olduğunu kanıtlamazdı. Soru/sınav uçları henüz yazılmadığı
için (Şerit 4) `questions`/`exam_sessions`/`answers` satırları sahip bağlantısıyla
seed edilir.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import rls_session
from app.models.assessment import QuestionType
from app.modules.mastery.service import record_answer
from tests.conftest import UserFactory
from tests.factories import (
    create_course,
    create_topic,
    enroll_student,
    seed_document,
    seed_question,
)

# Ders/üyelik/konu/soru kurulumu `tests.factories`'ten gelir. Aşağıda kalan
# yardımcılar bu dosyaya ÖZGÜ: `exam_sessions`/`answers`/`request_logs` satırlarını
# yalnız analitik uçları okuyor, dolayısıyla ortak fabrikaya taşımak kimseye
# hizmet etmezdi.


async def _record(user_id: UUID, topic_id: UUID, course_id: UUID, raw_score: int) -> float:
    async with rls_session(user_id) as session:
        return await record_answer(
            session,
            user_id=user_id,
            topic_id=topic_id,
            course_id=course_id,
            raw_score=raw_score,
        )


async def _seed_session(
    engine: AsyncEngine, *, course_id: UUID, user_id: UUID, question_id: UUID
) -> UUID:
    session_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO exam_sessions (id, course_id, user_id, mode, question_ids) "
                "VALUES (:id, :course_id, :user_id, 'practice', ARRAY[:question_id]::uuid[])"
            ),
            {
                "id": session_id,
                "course_id": course_id,
                "user_id": user_id,
                "question_id": question_id,
            },
        )
    return session_id


async def _seed_answer(
    engine: AsyncEngine,
    *,
    session_id: UUID,
    question_id: UUID,
    course_id: UUID,
    is_correct: bool | None,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO answers (session_id, question_id, course_id, given, is_correct) "
                "VALUES (:session_id, :question_id, :course_id, 'cevap', :is_correct)"
            ),
            {
                "session_id": session_id,
                "question_id": question_id,
                "course_id": course_id,
                "is_correct": is_correct,
            },
        )


async def _seed_requests(
    engine: AsyncEngine, *, course_id: UUID, user_id: UUID, statuses: list[str | None]
) -> None:
    """`request_logs` satırları yazar; None = cevap durumu üretmeyen istek.

    Durumu NULL olan satır paydaya girmemeli: oturum listeleme gibi istekler
    reddedilebilecek bir soru taşımıyor ve oranı sulandırırlardı.
    """
    async with engine.begin() as conn:
        for status in statuses:
            await conn.execute(
                text(
                    "INSERT INTO request_logs (course_id, user_id, route, mode, status, "
                    "http_status, latency_ms) VALUES (:cid, :uid, '/chat', 'qa', "
                    "CAST(:status AS answer_status), 200, 120)"
                ),
                {"cid": course_id, "uid": user_id, "status": status},
            )


class TestStudentProgress:
    async def test_konular_en_dusuk_skordan_siralanir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """Listenin tepesi 'önce şuna bak' demektir; alfabetik sıra bu işi yapmaz."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")

        deadlock = await create_topic(client, ayse, course_id, "Deadlock")
        scheduling = await create_topic(client, ayse, course_id, "CPU zamanlama")
        await _record(burak_id, deadlock, course_id, 30)
        await _record(burak_id, scheduling, course_id, 90)

        response = await client.get(
            f"/courses/{course_id}/analytics/me", headers=users.auth(burak_id)
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert [t["name"] for t in body["topics"]] == ["Deadlock", "CPU zamanlama"]
        assert body["topics"][0]["level"] == "needs_work"
        assert body["topics"][1]["level"] == "good"
        assert body["needs_work_topics"] == 1
        assert body["answered_questions"] == 2
        assert body["average_score"] == pytest.approx(0.60)

    async def test_seviye_esikleri_sinirda_dahildir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """FR-027: tam 0.40 Orta'ya, tam 0.75 İyi'ye girer.

        Aynı eşikler arayüzde `lib/labels.ts`'te de var. İki taraf ayrışırsa aynı
        öğrenci aynı anda iki farklı etiketle görünür; sınır değerleri bu yüzden
        burada sabitlenir.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")

        orta = await create_topic(client, ayse, course_id, "Tam sınırda orta")
        iyi = await create_topic(client, ayse, course_id, "Tam sınırda iyi")
        # İlk cevapta EWMA yok: yeni = son, yani skor birebir raw/100 olur.
        assert await _record(burak_id, orta, course_id, 40) == pytest.approx(0.40)
        assert await _record(burak_id, iyi, course_id, 75) == pytest.approx(0.75)

        body = (
            await client.get(f"/courses/{course_id}/analytics/me", headers=users.auth(burak_id))
        ).json()

        levels = {t["name"]: t["level"] for t in body["topics"]}
        assert levels["Tam sınırda orta"] == "medium"
        assert levels["Tam sınırda iyi"] == "good"

    async def test_calisilmamis_konu_listeye_girmez_ama_sayilir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """Skoru olmayan konuya 0.0 vermek 'Geliştirilmeli' etiketi üretirdi.

        Bu, öğrenciye hiç çalışmadığı bir konuda başarısız olduğunu söylemek olurdu.
        Konu listeye girmez, sayı olarak bildirilir.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")

        deadlock = await create_topic(client, ayse, course_id, "Deadlock")
        await create_topic(client, ayse, course_id, "Dosya sistemleri")
        await _record(burak_id, deadlock, course_id, 60)

        body = (
            await client.get(f"/courses/{course_id}/analytics/me", headers=users.auth(burak_id))
        ).json()

        assert body["tracked_topics"] == 1
        assert body["untracked_topics"] == 1
        assert [t["name"] for t in body["topics"]] == ["Deadlock"]

    async def test_hic_veri_yokken_ortalama_sifir_degil_none(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """Ortalama 0.0 dönseydi 'her konuda sıfırsın' demek olurdu."""
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")

        body = (
            await client.get(f"/courses/{course_id}/analytics/me", headers=users.auth(burak_id))
        ).json()

        assert body["average_score"] is None
        assert body["topics"] == []

    async def test_baska_ogrencinin_skoru_gorunmez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        ceren_id = await users.create("ceren@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")
        await enroll_student(client, ayse, course_id, "ceren@dogus.edu.tr")

        deadlock = await create_topic(client, ayse, course_id, "Deadlock")
        await _record(burak_id, deadlock, course_id, 20)
        await _record(ceren_id, deadlock, course_id, 100)

        burak_body = (
            await client.get(f"/courses/{course_id}/analytics/me", headers=users.auth(burak_id))
        ).json()
        ceren_body = (
            await client.get(f"/courses/{course_id}/analytics/me", headers=users.auth(ceren_id))
        ).json()

        assert burak_body["topics"][0]["score"] == pytest.approx(0.20)
        assert ceren_body["topics"][0]["score"] == pytest.approx(1.00)
        assert burak_body["tracked_topics"] == ceren_body["tracked_topics"] == 1

    async def test_uye_olmayan_kullanici_404_alir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        disari = users.auth(await users.create("disari@dogus.edu.tr"))
        course_id = await create_course(client, ayse, "COME301")

        response = await client.get(f"/courses/{course_id}/analytics/me", headers=disari)

        # Dersin varlığı sızdırılmaz: 403 değil 404.
        assert response.status_code == 404


class TestClassAnalytics:
    async def test_ogrenci_sinif_analitigini_goremez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")

        response = await client.get(
            f"/courses/{course_id}/analytics/class", headers=users.auth(burak_id)
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    async def test_egitmen_konu_bazli_sinif_ortalamasini_gorur(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        ceren_id = await users.create("ceren@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")
        await enroll_student(client, ayse, course_id, "ceren@dogus.edu.tr")

        deadlock = await create_topic(client, ayse, course_id, "Deadlock")
        scheduling = await create_topic(client, ayse, course_id, "CPU zamanlama")
        await _record(burak_id, deadlock, course_id, 20)
        await _record(ceren_id, deadlock, course_id, 40)
        await _record(burak_id, scheduling, course_id, 80)
        await _record(ceren_id, scheduling, course_id, 100)

        response = await client.get(f"/courses/{course_id}/analytics/class", headers=ayse)

        assert response.status_code == 200, response.text
        body = response.json()
        assert [t["name"] for t in body["topics"]] == ["Deadlock", "CPU zamanlama"]
        assert body["topics"][0]["average_score"] == pytest.approx(0.30)
        assert body["topics"][0]["student_count"] == 2
        assert body["topics"][1]["average_score"] == pytest.approx(0.90)
        assert body["student_count"] == 2
        assert body["answered_questions"] == 4

    async def test_en_cok_yanlis_yapilan_sorular_siralanir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Sıralama yanlış oranına göre; payda yalnız DEĞERLENDİRİLMİŞ cevaplardır.

        Değerlendirilmemiş (is_correct NULL) bir cevabı doğru saymak oranı düşürür,
        yanlış saymak yükseltir — ikisi de ölçülmemiş bir şeyi raporlamak olur.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")

        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        # Soruların kaynağı: `questions.source_chunk_id` NOT NULL'dur.
        chunk_id = (
            await seed_document(
                admin_engine,
                course_id=course_id,
                uploaded_by=ayse_id,
                passages=["Deadlock için dört Coffman koşulu birlikte sağlanmalıdır."],
            )
        ).chunk_ids[0]
        zor = await seed_question(
            admin_engine,
            course_id=course_id,
            topic_id=topic_id,
            source_chunk_id=chunk_id,
            payload={
                "stem": "Banker's algoritmasında güvenli durum ne demektir?",
                "answer_key": "dört koşul",
            },
            question_type=QuestionType.OPEN,
            status="approved",
            created_by=ayse_id,
            reviewed_by=ayse_id,
        )
        kolay = await seed_question(
            admin_engine,
            course_id=course_id,
            topic_id=topic_id,
            source_chunk_id=chunk_id,
            payload={
                "stem": "Deadlock kaç koşulun birlikte sağlanmasıyla oluşur?",
                "answer_key": "dört koşul",
            },
            question_type=QuestionType.OPEN,
            status="approved",
            created_by=ayse_id,
            reviewed_by=ayse_id,
        )

        # Zor soru: 2 cevap, 2 yanlış -> 1.00. Kolay soru: 2 cevap, 1 yanlış -> 0.50.
        # Kolay soruya ayrıca değerlendirilmemiş bir cevap: paydaya girmemeli.
        for is_correct, question_id in (
            (False, zor),
            (False, kolay),
            (True, kolay),
            (None, kolay),
        ):
            session_id = await _seed_session(
                admin_engine,
                course_id=course_id,
                user_id=burak_id,
                question_id=question_id,
            )
            await _seed_answer(
                admin_engine,
                session_id=session_id,
                question_id=question_id,
                course_id=course_id,
                is_correct=is_correct,
            )
        session_id = await _seed_session(
            admin_engine, course_id=course_id, user_id=burak_id, question_id=zor
        )
        await _seed_answer(
            admin_engine,
            session_id=session_id,
            question_id=zor,
            course_id=course_id,
            is_correct=False,
        )

        body = (await client.get(f"/courses/{course_id}/analytics/class", headers=ayse)).json()

        missed = body["missed_questions"]
        assert [q["wrong_rate"] for q in missed] == [pytest.approx(1.0), pytest.approx(0.5)]
        assert missed[0]["stem"].startswith("Banker's")
        assert missed[0]["graded_answer_count"] == 2
        assert missed[1]["graded_answer_count"] == 2  # NULL cevap paydaya girmedi
        assert missed[0]["topic_name"] == "Deadlock"

    async def test_hic_yanlis_yapilmamis_soru_listeye_girmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """`missed_questions` adı ne diyorsa onu içerir.

        Süzgeç yalnız `graded > 0` iken, hiç yanlış yapılmamış sorular da listeye
        giriyordu — canlı veride gözlendi (COME 331'de dört satırdan birinin
        `wrong_rate` değeri 0). Eğitmen bu panele "sınıf nerede zorlanıyor" diye
        bakıyor; oraya sorunu olmayan bir soruyu koymak, olmayan bir sorunu
        varmış gibi raporlamaktır.

        Liste boş dönerse bu anlamlı bir cevaptır: henüz kimse yanlış yapmadı.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")

        topic_id = await create_topic(client, ayse, course_id, "Deadlock")
        chunk_id = (
            await seed_document(
                admin_engine,
                course_id=course_id,
                uploaded_by=ayse_id,
                passages=["Deadlock için dört Coffman koşulu birlikte sağlanmalıdır."],
            )
        ).chunk_ids[0]
        herkes_dogru = await seed_question(
            admin_engine,
            course_id=course_id,
            topic_id=topic_id,
            source_chunk_id=chunk_id,
            payload={
                "stem": "Deadlock kaç koşulun birlikte sağlanmasıyla oluşur?",
                "answer_key": "dört koşul",
            },
            question_type=QuestionType.OPEN,
            status="approved",
            created_by=ayse_id,
            reviewed_by=ayse_id,
        )

        for _ in range(2):
            session_id = await _seed_session(
                admin_engine,
                course_id=course_id,
                user_id=burak_id,
                question_id=herkes_dogru,
            )
            await _seed_answer(
                admin_engine,
                session_id=session_id,
                question_id=herkes_dogru,
                course_id=course_id,
                is_correct=True,
            )

        body = (await client.get(f"/courses/{course_id}/analytics/class", headers=ayse)).json()

        assert body["missed_questions"] == []

    async def test_hic_asistan_cevabi_yokken_oran_sifir_degil_none(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """0.0 döndürmek 'bu derste hiçbir soru reddedilmedi' demek olurdu.

        Anayasa III: ölçülmemiş bir şey sayı olarak raporlanamaz. Kaynak her zaman
        bildirilir, oran ancak ölçülecek veri varsa doldurulur.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await create_course(client, ayse, "COME301")

        body = (await client.get(f"/courses/{course_id}/analytics/class", headers=ayse)).json()

        out_of_scope = body["out_of_scope"]
        assert out_of_scope["source"] == "request_logs"
        assert out_of_scope["rate"] is None
        assert out_of_scope["answered_request_count"] == 0

    async def test_kapsam_disi_ret_orani_olcum_kaydindan_hesaplanir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """SC-005 yalnız `out_of_scope` sayar; `insufficient_context` orana girmez.

        İkisi farklı şeydir: biri "bu ders bu konuyu hiç kapsamıyor", diğeri
        "materyalde olabilir ama kanıt zayıf" (contracts.AnswerStatus). Aynı orana
        katılsalardı SC-005 ölçtüğünü iddia ettiği şeyi ölçmezdi.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")

        # 4 cevap üretilmiş istek: 1 kapsam dışı, 1 kanıt yetersiz, 2 cevaplanmış.
        # Beşinci satır durumu olmayan bir istek: paydaya GİRMEMELİ.
        await _seed_requests(
            admin_engine,
            course_id=course_id,
            user_id=burak_id,
            statuses=["out_of_scope", "insufficient_context", "answered", "answered", None],
        )

        body = (await client.get(f"/courses/{course_id}/analytics/class", headers=ayse)).json()

        out_of_scope = body["out_of_scope"]
        assert out_of_scope["source"] == "request_logs"
        assert out_of_scope["answered_request_count"] == 4
        assert out_of_scope["out_of_scope_count"] == 1
        assert out_of_scope["insufficient_context_count"] == 1
        assert out_of_scope["rate"] == pytest.approx(0.25)

    async def test_kapsam_disi_orani_baska_dersin_kaydini_saymaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        os_course = await create_course(client, ayse, "COME301")
        ds_course = await create_course(client, ayse, "COME302")
        await enroll_student(client, ayse, os_course, "burak@dogus.edu.tr")
        await enroll_student(client, ayse, ds_course, "burak@dogus.edu.tr")

        await _seed_requests(
            admin_engine, course_id=os_course, user_id=burak_id, statuses=["answered"]
        )
        await _seed_requests(
            admin_engine,
            course_id=ds_course,
            user_id=burak_id,
            statuses=["out_of_scope", "out_of_scope"],
        )

        body = (await client.get(f"/courses/{os_course}/analytics/class", headers=ayse)).json()

        assert body["out_of_scope"]["answered_request_count"] == 1
        assert body["out_of_scope"]["out_of_scope_count"] == 0

    async def test_baska_dersin_verisi_sizmaz(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """İstemciden gelen course_id yetki değildir; her ders kendi sayısını görür."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        os_course = await create_course(client, ayse, "COME301")
        ds_course = await create_course(client, ayse, "COME302")
        await enroll_student(client, ayse, os_course, "burak@dogus.edu.tr")
        await enroll_student(client, ayse, ds_course, "burak@dogus.edu.tr")

        os_topic = await create_topic(client, ayse, os_course, "Deadlock")
        ds_topic = await create_topic(client, ayse, ds_course, "Yığın ve kuyruk")
        await _record(burak_id, os_topic, os_course, 20)
        await _record(burak_id, ds_topic, ds_course, 100)

        os_body = (await client.get(f"/courses/{os_course}/analytics/class", headers=ayse)).json()

        assert [t["name"] for t in os_body["topics"]] == ["Deadlock"]
        assert os_body["answered_questions"] == 1
