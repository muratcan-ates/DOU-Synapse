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
from app.modules.mastery.service import record_answer
from tests.conftest import UserFactory


async def _create_course(client: AsyncClient, headers: dict[str, str], code: str) -> UUID:
    response = await client.post(
        "/courses", json={"code": code, "title": f"{code} Dersi"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def _add_student(
    client: AsyncClient, headers: dict[str, str], course_id: UUID, email: str
) -> None:
    response = await client.post(
        f"/courses/{course_id}/members",
        json={"email": email, "role": "student"},
        headers=headers,
    )
    assert response.status_code in (200, 201), response.text


async def _create_topic(
    client: AsyncClient, headers: dict[str, str], course_id: UUID, name: str
) -> UUID:
    response = await client.post(
        f"/courses/{course_id}/topics", json={"name": name}, headers=headers
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


async def _record(user_id: UUID, topic_id: UUID, course_id: UUID, raw_score: int) -> float:
    async with rls_session(user_id) as session:
        return await record_answer(
            session,
            user_id=user_id,
            topic_id=topic_id,
            course_id=course_id,
            raw_score=raw_score,
        )


async def _seed_chunk(engine: AsyncEngine, course_id: UUID, uploader_id: UUID) -> UUID:
    """Soru üretiminin kaynağı: questions.source_chunk_id NOT NULL'dur."""
    document_id, chunk_id = uuid4(), uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO documents (id, course_id, uploaded_by, file_name, file_type, "
                "storage_path, file_hash, byte_size, status) VALUES "
                "(:id, :course_id, :uploader, '05-deadlock-demo.pdf', 'pdf', "
                "'courses/x/d.pdf', :hash, 1024, 'completed')"
            ),
            {
                "id": document_id,
                "course_id": course_id,
                "uploader": uploader_id,
                "hash": str(document_id),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO chunks (id, course_id, document_id, chunk_index, page_number, "
                "text, token_count) VALUES (:id, :course_id, :document_id, 0, 1, "
                "'Deadlock için dört Coffman koşulu birlikte sağlanmalıdır.', 42)"
            ),
            {"id": chunk_id, "course_id": course_id, "document_id": document_id},
        )
    return chunk_id


async def _seed_question(
    engine: AsyncEngine,
    *,
    course_id: UUID,
    topic_id: UUID,
    chunk_id: UUID,
    instructor_id: UUID,
    stem: str,
) -> UUID:
    question_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO questions (id, course_id, topic_id, type, payload, "
                "source_chunk_id, status, created_by, reviewed_by, reviewed_at) VALUES "
                "(:id, :course_id, :topic_id, 'open', "
                # CAST şart: jsonb_build_object'in argüman tipi "any" olduğu için
                # sunucu bind parametresinin tipini kendi başına çıkaramaz. `::text`
                # biçimi kullanılamaz — SQLAlchemy'nin text() ayrıştırıcısı iki üst
                # üste noktayı parametre sınırı sanıp bağlamayı bozar.
                "jsonb_build_object('stem', CAST(:stem AS text), 'answer_key', 'dört koşul'), "
                ":chunk_id, 'approved', :instructor, :instructor, now())"
            ),
            {
                "id": question_id,
                "course_id": course_id,
                "topic_id": topic_id,
                "stem": stem,
                "chunk_id": chunk_id,
                "instructor": instructor_id,
            },
        )
    return question_id


async def _seed_session(engine: AsyncEngine, *, course_id: UUID, user_id: UUID) -> UUID:
    session_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO exam_sessions (id, course_id, user_id, mode, question_ids) "
                "VALUES (:id, :course_id, :user_id, 'practice', '{}'::uuid[])"
            ),
            {"id": session_id, "course_id": course_id, "user_id": user_id},
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


class TestStudentProgress:
    async def test_konular_en_dusuk_skordan_siralanir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """Listenin tepesi 'önce şuna bak' demektir; alfabetik sıra bu işi yapmaz."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await _add_student(client, ayse, course_id, "burak@dogus.edu.tr")

        deadlock = await _create_topic(client, ayse, course_id, "Deadlock")
        scheduling = await _create_topic(client, ayse, course_id, "CPU zamanlama")
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
        course_id = await _create_course(client, ayse, "COME301")
        await _add_student(client, ayse, course_id, "burak@dogus.edu.tr")

        orta = await _create_topic(client, ayse, course_id, "Tam sınırda orta")
        iyi = await _create_topic(client, ayse, course_id, "Tam sınırda iyi")
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
        course_id = await _create_course(client, ayse, "COME301")
        await _add_student(client, ayse, course_id, "burak@dogus.edu.tr")

        deadlock = await _create_topic(client, ayse, course_id, "Deadlock")
        await _create_topic(client, ayse, course_id, "Dosya sistemleri")
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
        course_id = await _create_course(client, ayse, "COME301")
        await _add_student(client, ayse, course_id, "burak@dogus.edu.tr")

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
        course_id = await _create_course(client, ayse, "COME301")
        await _add_student(client, ayse, course_id, "burak@dogus.edu.tr")
        await _add_student(client, ayse, course_id, "ceren@dogus.edu.tr")

        deadlock = await _create_topic(client, ayse, course_id, "Deadlock")
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
        course_id = await _create_course(client, ayse, "COME301")

        response = await client.get(f"/courses/{course_id}/analytics/me", headers=disari)

        # Dersin varlığı sızdırılmaz: 403 değil 404.
        assert response.status_code == 404


class TestClassAnalytics:
    async def test_ogrenci_sinif_analitigini_goremez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await _add_student(client, ayse, course_id, "burak@dogus.edu.tr")

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
        course_id = await _create_course(client, ayse, "COME301")
        await _add_student(client, ayse, course_id, "burak@dogus.edu.tr")
        await _add_student(client, ayse, course_id, "ceren@dogus.edu.tr")

        deadlock = await _create_topic(client, ayse, course_id, "Deadlock")
        scheduling = await _create_topic(client, ayse, course_id, "CPU zamanlama")
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
        course_id = await _create_course(client, ayse, "COME301")
        await _add_student(client, ayse, course_id, "burak@dogus.edu.tr")

        topic_id = await _create_topic(client, ayse, course_id, "Deadlock")
        chunk_id = await _seed_chunk(admin_engine, course_id, ayse_id)
        zor = await _seed_question(
            admin_engine,
            course_id=course_id,
            topic_id=topic_id,
            chunk_id=chunk_id,
            instructor_id=ayse_id,
            stem="Banker's algoritmasında güvenli durum ne demektir?",
        )
        kolay = await _seed_question(
            admin_engine,
            course_id=course_id,
            topic_id=topic_id,
            chunk_id=chunk_id,
            instructor_id=ayse_id,
            stem="Deadlock kaç koşulun birlikte sağlanmasıyla oluşur?",
        )

        # Zor soru: 2 cevap, 2 yanlış -> 1.00. Kolay soru: 2 cevap, 1 yanlış -> 0.50.
        # Kolay soruya ayrıca değerlendirilmemiş bir cevap: paydaya girmemeli.
        for is_correct, question_id in (
            (False, zor),
            (False, kolay),
            (True, kolay),
            (None, kolay),
        ):
            session_id = await _seed_session(admin_engine, course_id=course_id, user_id=burak_id)
            await _seed_answer(
                admin_engine,
                session_id=session_id,
                question_id=question_id,
                course_id=course_id,
                is_correct=is_correct,
            )
        session_id = await _seed_session(admin_engine, course_id=course_id, user_id=burak_id)
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

    async def test_kapsam_disi_orani_kaynak_yokken_olculmedi_der(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """Sohbet kayıtları (migration 0003) yoksa oran uydurulmaz.

        Anayasa III: çalıştırılmayan ölçüm için sayı yazılmaz. Uç, sayının nereden
        geldiğini her zaman söyler; kaynak yoksa `unavailable` döner.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")

        body = (await client.get(f"/courses/{course_id}/analytics/class", headers=ayse)).json()

        out_of_scope = body["out_of_scope"]
        assert out_of_scope["source"] == "unavailable"
        assert out_of_scope["rate"] is None
        assert out_of_scope["out_of_scope_count"] is None
        assert "ölçülmedi" in out_of_scope["note"]

    async def test_baska_dersin_verisi_sizmaz(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """İstemciden gelen course_id yetki değildir; her ders kendi sayısını görür."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")
        os_course = await _create_course(client, ayse, "COME301")
        ds_course = await _create_course(client, ayse, "COME302")
        await _add_student(client, ayse, os_course, "burak@dogus.edu.tr")
        await _add_student(client, ayse, ds_course, "burak@dogus.edu.tr")

        os_topic = await _create_topic(client, ayse, os_course, "Deadlock")
        ds_topic = await _create_topic(client, ayse, ds_course, "Yığın ve kuyruk")
        await _record(burak_id, os_topic, os_course, 20)
        await _record(burak_id, ds_topic, ds_course, 100)

        os_body = (await client.get(f"/courses/{os_course}/analytics/class", headers=ayse)).json()

        assert [t["name"] for t in os_body["topics"]] == ["Deadlock"]
        assert os_body["answered_questions"] == 1
