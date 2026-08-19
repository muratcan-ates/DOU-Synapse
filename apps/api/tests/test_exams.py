"""Sınav provası testleri — T032/T033.

Kapsanan vakalar (tasks.md T033): (3) exam modunda ipucu reddi, (4) süre dolunca
cevap kabul edilmez ve boş sorular puana katılmaz, (6) boş onaylı havuzda sınav
reddi, (7) oturuma dönüşte kalan süre korunur, (8) practice modda ipucu açık +
anında geri bildirim. Vaka (1), (2) ve (5) havuz tarafındadır: `test_assessment.py`.

Zamanı hızlandırmak için `sleep` yok: oturumun `started_at`/`expires_at` sütunları
sahip bağlantısıyla geriye alınır. Süre karşılaştırması zaten veritabanı saatine
göre yapıldığı için bu, gerçekten süre geçmiş bir oturumla aynı durumdur.

Ders/üyelik/konu/belge/soru satırlarını `tests/factories.py` yazar. Soru havuzunun
KORPUSU (`DEADLOCK_TEXTS`, payload üreteçleri, `ESSAY_PAYLOAD`), sahte LLM ve
sınav kurulumu (`ExamFixture`, `build_course`, `start`, `rewind`) de oradadır:
sınav testleri havuzun ürettiği soruların aynısını görmek zorunda ve aynı kurulumu
`test_exam_lock`, `test_user_rights`, `test_sources_api` ile
`test_role_aware_agent_application_guards` da kullanıyor (Anayasa XI, eşik üç).
Bu dosyada yalnız buraya özgü uç sarmalayıcıları (`answer`/`finish`/`hint`) kaldı.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import rls_session
from app.models.assessment import QuestionType
from app.modules.assessment import question_gen
from tests.conftest import UserFactory
from tests.factories import (
    ESSAY_PAYLOAD,
    EXAM_DURATION_SECONDS,
    ExamFixture,
    FakeCompletion,
    build_course,
    enroll_student,
    mcq_payload,
    rewind,
    seed_document,
    seed_question,
    start,
)


@pytest.fixture
def bind_completion() -> Iterator[Callable[[FakeCompletion], None]]:
    """Sahte LLM sağlayıcısını süreç geneline bağlar ve test bitince söker.

    Sağlayıcı kaydı modül düzeyinde tutulduğu için sızıntı riski var; fixture
    `reset_providers()` ile kapatır, böylece bir sonraki test yine "bağlı değil"
    hâlinde başlar.
    """
    yield lambda completion: question_gen.set_providers(completion=completion)
    question_gen.reset_providers()


# ---------------------------------------------------------------------------
# Uç sarmalayıcıları — YALNIZ bu dosyaya ait
#
# Üçü de ham `Response` döndürür ve HİÇBİR durum kodu iddia etmez. Sebebi
# testlerin kendisi: aynı üç uca 201 de bekleniyor, 403/404/409 da. İddiayı
# yardımcıya taşımak reddedilme senaryolarını — sınav bitince cevap kabul
# edilmemesi, sınav modunda ipucunun kapalı olması — kurulamaz hâle getirirdi.
#
# `tests/factories.py`'ye TAŞINMADILAR: bu üç ucu bugün yalnız bu dosya çağırıyor.
# ---------------------------------------------------------------------------


async def answer(
    client: AsyncClient,
    fixture: ExamFixture,
    session_id: str,
    question_id: UUID | str,
    given: str,
    **extra: object,
) -> Response:
    """Öğrencinin bir soruya cevabını gönderir.

    `**extra` bugün yalnız `hint_level` taşıyor ve varsayılan olarak GÖNDERİLMEZ:
    ipucu beyanının yokluğu birçok testte iddianın parçası (sınavda ipucu beyan
    eden cevap 403 alır, prova modunda puanı kırpılır).
    """
    return await client.post(
        f"/courses/{fixture.course_id}/exams/{session_id}/answers",
        json={"question_id": str(question_id), "given": given, **extra},
        headers=fixture.student,
    )


async def finish(client: AsyncClient, fixture: ExamFixture, session_id: str) -> Response:
    """Oturumu bitirir."""
    return await client.post(
        f"/courses/{fixture.course_id}/exams/{session_id}/finish", headers=fixture.student
    )


async def hint(
    client: AsyncClient,
    fixture: ExamFixture,
    session_id: str,
    question_id: UUID | str,
    *,
    level: int,
) -> Response:
    """Bir soru için ipucu ister."""
    return await client.post(
        f"/courses/{fixture.course_id}/exams/{session_id}/hint",
        json={"question_id": str(question_id), "hint_level": level},
        headers=fixture.student,
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
        await enroll_student(client, fixture.instructor, fixture.course_id, "ceren@dogus.edu.tr")

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

        # `0007` öncesi öğrenci bu sütunu YAZABİLİYORDU ve tek koruma sunucu
        # tarafındaki kırpmaydı. Artık kolon GRANT'i yazmayı veritabanı düzeyinde
        # reddediyor — kırpma ikinci katman olarak duruyor (Anayasa II: iki katman
        # da bağımsız olarak doğru davranmalı).
        with pytest.raises(ProgrammingError) as reddedildi:
            async with rls_session(fixture.student_id) as session:
                await session.execute(
                    text(
                        "UPDATE exam_sessions SET expires_at = now() + interval '1 day' "
                        "WHERE id = :id"
                    ),
                    {"id": UUID(session_id)},
                )
        assert "permission denied" in str(reddedildi.value)

        response = await client.get(
            f"/courses/{fixture.course_id}/exams/{session_id}", headers=fixture.student
        )

        assert response.json()["remaining_seconds"] <= EXAM_DURATION_SECONDS


# ---------------------------------------------------------------------------
# Cevap gönderme — vaka 3, 4
# ---------------------------------------------------------------------------


class TestOturumListesi:
    """`GET /exams` — öğrenci devam eden sınavına oturum kimliği olmadan dönebilmeli.

    Bu uç, kimliğin yalnız istemcide tutulmasının açtığı iki boşluğu birden
    kapatıyor: tarayıcı verisi silinince oturumun kaybolması, ve kaybolan
    oturumun yerine yenisini açıp süreyi baştan alabilmek. Süre sunucunun
    kararıysa, oturumu bulmak da sunucunun işi.
    """

    async def test_kendi_oturumlarini_yeniden_eskiye_listeler(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        birinci = (await start(client, fixture, "practice"))["id"]
        ikinci = (await start(client, fixture, "practice"))["id"]

        response = await client.get(f"/courses/{fixture.course_id}/exams", headers=fixture.student)

        assert response.status_code == 200, response.text
        kimlikler = [row["id"] for row in response.json()]
        assert kimlikler == [ikinci, birinci], "en yeni oturum başta olmalı"

    async def test_devam_eden_oturum_kalan_suresiyle_bulunur(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Ucun var olma sebebi: kimlik kaybolsa bile süre kaybolmuyor."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        await rewind(admin_engine, session_id, minutes=5)

        satir = (
            await client.get(f"/courses/{fixture.course_id}/exams", headers=fixture.student)
        ).json()[0]

        assert satir["id"] == session_id
        assert satir["finished_at"] is None
        assert 15 * 60 - 10 <= satir["remaining_seconds"] <= 15 * 60

    async def test_baska_ogrencinin_oturumu_listeye_girmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """RLS + ders kontrolü: iki katman da bağımsız olarak doğru davranmalı."""
        fixture = await build_course(client, users, admin_engine)
        await start(client, fixture, "exam")
        ceren_id = await users.create("ceren@dogus.edu.tr")
        await enroll_student(client, fixture.instructor, fixture.course_id, "ceren@dogus.edu.tr")

        response = await client.get(
            f"/courses/{fixture.course_id}/exams", headers=users.auth(ceren_id)
        )

        assert response.status_code == 200
        assert response.json() == [], "başka öğrencinin oturumu görünmemeli"

    async def test_liste_soru_metinlerini_tasimaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Liste "hangi oturumlarım var" sorusunu cevaplar, sınavın içeriğini değil."""
        fixture = await build_course(client, users, admin_engine)
        await start(client, fixture, "exam")

        satir = (
            await client.get(f"/courses/{fixture.course_id}/exams", headers=fixture.student)
        ).json()[0]

        assert satir["questions"] == []
        # Sayaçlar yine de dolu: ekran ilerlemeyi soru metni olmadan gösterebilmeli.
        assert satir["question_count"] > 0


class TestAnswerSubmission:
    async def test_exam_modunda_puan_cevapla_birlikte_donmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Geri bildirim sınav sonunda: puan yazılır ama gösterilmez."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]

        response = await answer(client, fixture, session_id, fixture.question_ids[0], "C")

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
        question_id = fixture.question_ids[0]

        first = await answer(client, fixture, session_id, question_id, "C")
        # Şık değişiyor: reddin sebebi "aynı cevap" değil "aynı soru" olmalı.
        second = await answer(client, fixture, session_id, question_id, "A")

        assert first.status_code == 201
        assert second.status_code == 409
        assert "tek deneme" in second.json()["error"]["message"]

    async def test_exam_modunda_ipucu_kademesi_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Vaka 3 (ilk kapı): ipucu kullanıldığını beyan eden cevap sınavda geçmez."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]

        response = await answer(
            client, fixture, session_id, fixture.question_ids[0], "C", hint_level=2
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    async def test_oturumda_olmayan_soru_cevaplanamaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]

        response = await answer(client, fixture, session_id, uuid4(), "C")

        assert response.status_code == 404

    async def test_sure_dolunca_cevap_kabul_edilmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Vaka 4 (ilk yarısı)."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        await rewind(admin_engine, session_id, minutes=25)

        response = await answer(client, fixture, session_id, fixture.question_ids[0], "C")

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

        response = await answer(client, fixture, session_id, fixture.question_ids[0], "D")

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

        body = (await answer(client, fixture, session_id, fixture.question_ids[0], "C")).json()

        assert body["is_correct"] is True
        assert body["score"] == 100
        assert body["why_wrong"] is None

    async def test_practice_modunda_ipucu_kaynaktan_gelir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "practice"))["id"]

        first = await hint(client, fixture, session_id, fixture.question_ids[0], level=1)
        deeper = await hint(client, fixture, session_id, fixture.question_ids[0], level=4)

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

        response = await hint(client, fixture, session_id, fixture.question_ids[0], level=1)

        assert response.status_code == 403
        assert "ipucu kapalıdır" in response.json()["error"]["message"]

    async def test_kisa_cevap_llm_olmadan_degerlendirilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Karar 4: kısa cevap deterministiktir, sağlayıcı bağlı olmasa da çalışır."""
        fixture = await build_course(client, users, admin_engine, short_answer=True)
        session_id = (await start(client, fixture, "practice"))["id"]

        body = (
            await answer(client, fixture, session_id, fixture.question_ids[0], "Döngüsel Bekleme")
        ).json()

        assert body["graded"] is True
        assert body["score"] == 100

    async def test_semaya_uymayan_degerlendirme_uydurma_puan_almaz(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """FR-020: değerlendirilemeyen cevaba uydurma puan verilmez.

        Anahtar yokken üretim istemcisi deterministik sahteye düşer ve o sahte
        sohbet cevabı üretmek için yazılmıştır — değerlendirme şemasını
        karşılamaz. Cevap kaydedilir, puan verilmez.
        """
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

        body = (await answer(client, fixture, session_id, essay_id, "Dört koşul vardır.")).json()

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
        await answer(client, fixture, session_id, fixture.question_ids[0], "C")
        await rewind(admin_engine, session_id, minutes=25)

        response = await finish(client, fixture, session_id)

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
        await answer(client, fixture, session_id, fixture.question_ids[0], "A")

        body = (await finish(client, fixture, session_id)).json()

        result = body["results"][0]
        assert result["is_correct"] is False
        assert result["why_wrong"]["file_name"] == "isletim-sistemleri.pdf"
        assert result["solution"]["answer_key"] == "C"

    async def test_neden_yanlis_alintisi_secilen_celdiriciye_odaklanir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Aynı kaynak, farklı çeldirici → farklı cümle.

        Alıntı chunk'ın başından kesilseydi iki öğrenci de aynı metni görürdü ve
        "neden yanlış" hiçbir şey açıklamazdı.
        """
        # `approved=0`: havuz boş kuruluyor, tek onaylı soru aşağıda elle yazılıyor.
        # Kaynak metin standart korpustan farklı olmak ZORUNDA — üç çeldiricinin
        # üçü de aynı chunk'ı gösteriyor ve iddia, alıntının hangi cümleye
        # düştüğü. Tek cümlelik bir kaynakta iki çeldirici aynı metni verirdi.
        fixture = await build_course(client, users, admin_engine, approved=0)
        seeded = await seed_document(
            admin_engine,
            course_id=UUID(fixture.course_id),
            uploaded_by=fixture.instructor_id,
            passages=[
                "Karşılıklı dışlama, kaynağın aynı anda tek süreç tarafından "
                "kullanılabilmesidir. Tut ve bekle, elindeki kaynağı bırakmadan "
                "yenisini istemektir. Döngüsel bekleme ise süreçlerin halka "
                "oluşturmasıdır."
            ],
        )
        chunk_ids = seeded.chunk_ids
        payload = mcq_payload(chunk_ids)
        payload["distractor_sources"] = {key: str(chunk_ids[0]) for key in ("A", "B", "D")}
        question_id = await seed_question(
            admin_engine,
            course_id=UUID(fixture.course_id),
            topic_id=fixture.topic_id,
            source_chunk_id=chunk_ids[0],
            payload=payload,
            status="approved",
            reviewed_by=fixture.instructor_id,
        )

        snippets = {}
        for chosen in ("A", "D"):
            session_id = (await start(client, fixture, "exam"))["id"]
            await answer(client, fixture, session_id, question_id, chosen)
            finished = await finish(client, fixture, session_id)
            snippets[chosen] = finished.json()["results"][0]["why_wrong"]["snippet"]

        assert "Karşılıklı dışlama" in snippets["A"]
        assert "Tut ve bekle" in snippets["D"]
        assert snippets["A"] != snippets["D"]

    async def test_hic_cevap_yoksa_puan_gosterilmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]

        body = (await finish(client, fixture, session_id)).json()

        # 0 değil None: "hiç cevaplamadın" ile "hepsini yanlış yaptın" aynı şey değil.
        assert body["score"] is None
        assert body["answered_count"] == 0
        assert "puan hesaplanmadı" in body["message"]

    async def test_ikinci_kez_bitirilemez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        await finish(client, fixture, session_id)

        response = await finish(client, fixture, session_id)

        assert response.status_code == 409

    async def test_bitmis_oturuma_cevap_gonderilemez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "exam"))["id"]
        await finish(client, fixture, session_id)

        response = await answer(client, fixture, session_id, fixture.question_ids[0], "C")

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
        await answer(client, fixture, session_id, fixture.question_ids[0], "C")

        before = await _mastery_rows(fixture.student_id)
        await finish(client, fixture, session_id)
        after = await _mastery_rows(fixture.student_id)

        assert before == []
        assert after == [(1.0, 1)]

    async def test_practice_modunda_mastery_ilk_cevapta_islenir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """FR-017: practice modda mastery bitişi beklemez."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "practice"))["id"]

        await answer(client, fixture, session_id, fixture.question_ids[0], "C")

        assert await _mastery_rows(fixture.student_id) == [(1.0, 1)]

    async def test_llm_bagliyken_acik_uclu_soru_uctan_puanlanir(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        bind_completion: Callable[[FakeCompletion], None],
    ) -> None:
        """Şerit 2 indiğinde açık uçlu yolun uçtan uca çalıştığının kanıtı.

        Sağlayıcı bağlandığında hiçbir uç değişmez: aynı cevap ucu, aynı akış,
        yalnız `grade_answer` artık LLM yolunu bulur.
        """
        fixture = await build_course(client, users, admin_engine, approved=0)
        essay_id = await seed_question(
            admin_engine,
            course_id=UUID(fixture.course_id),
            topic_id=fixture.topic_id,
            source_chunk_id=fixture.chunk_ids[0],
            payload=ESSAY_PAYLOAD,
            question_type=QuestionType.OPEN,
            status="approved",
            reviewed_by=fixture.instructor_id,
        )
        bind_completion(
            FakeCompletion(
                json.dumps(
                    {
                        "score": 75,
                        "eksik_noktalar": ["kesilemezlik"],
                        "dayanak_chunk_id": str(fixture.chunk_ids[0]),
                    }
                )
            )
        )
        session_id = (await start(client, fixture, "practice"))["id"]

        body = (await answer(client, fixture, session_id, essay_id, "Üç koşulu sayıyorum.")).json()

        assert body["graded"] is True
        assert body["score"] == 75
        assert body["missing_points"] == ["kesilemezlik"]
        assert body["evidence"]["file_name"] == "isletim-sistemleri.pdf"
        assert await _mastery_rows(fixture.student_id) == [(0.75, 1)]

    async def test_ipucu_kademesi_mastery_puanini_kirpar(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """İpucuyla bulunan doğru cevap tam puan getirmez (çarpan 2 → 0.70)."""
        fixture = await build_course(client, users, admin_engine)
        session_id = (await start(client, fixture, "practice"))["id"]

        await answer(client, fixture, session_id, fixture.question_ids[0], "C", hint_level=2)

        assert await _mastery_rows(fixture.student_id) == [(0.70, 1)]
