"""Önbellek anahtarı ve mod güvenliği (FR-034, 14_R4 Kusur 6).

`tests/test_chat_api.py` önbelleğin **var olduğunu** sınıyor: ikinci aynı soru
LLM'e gitmiyor, ders bazlı izolasyon tutuyor, reddedilen cevap saklanmıyor. Bu
dosya anahtarın **doğru olduğunu** sınıyor — ikisi ayrı iddia.

Neden ayrı bir dosya: buradaki testlerin tamamı tek bir mekanizmanın (`question_hash`
ve onu okuyan iki fonksiyonun) regresyon koruması ve o mekanizma bugün en zayıf
korunan yer. Sohbet ucu testlerinin arasına dağıtılsalardı "önbellek anahtarında
mod var mı" sorusu bir daha tek bakışta cevaplanamazdı.

Sahte hat sınıfları `test_chat_api`'den içe aktarılıyor; üçüncü bir kopya yazmak
Anayasa XI'e aykırı olurdu (aynı gerekçeyle o dosya da `test_socratic`'ten alıyor).
"""

from __future__ import annotations

import json
import unicodedata
from collections.abc import AsyncIterator, Iterator
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.api.chat import question_hash, reset_rate_limit, set_pipeline
from app.contracts import ChatMode
from tests.conftest import WORKER_DSN, UserFactory
from tests.test_chat_api import Pipeline, _create_course, _install, sourced_answer
from tests.test_socratic import make_chunk


@pytest.fixture
def pipeline() -> Iterator[Pipeline]:
    fake = Pipeline()
    _install(fake)
    reset_rate_limit()
    yield fake
    set_pipeline()
    reset_rate_limit()


@pytest.fixture
async def worker_engine() -> AsyncIterator[AsyncEngine]:
    """Bozuk satır yazmak için RLS'i atlayan rol.

    `answer_cache` üzerinde `dou_app` için UPDATE politikası bilerek YOKTUR
    (0003_chat.sql): uygulama önbelleği yazar ve okur, düzenlemez. Bozuk satır
    senaryosunu kurmak bu yüzden ayrı bir rol istiyor — ve bu, testin kurduğu
    senaryonun uygulamanın kendi eliyle üretemeyeceği bir bozulma olduğunu da
    gösteriyor (dış müdahale, elle veri düzeltme, şema göçü).
    """
    engine = create_async_engine(WORKER_DSN)
    yield engine
    await engine.dispose()


# ---------------------------------------------------------------------------
# Anahtarın kendisi — saf fonksiyon, veritabanı gerekmez
# ---------------------------------------------------------------------------


class TestOnbellekAnahtari:
    def test_mod_anahtarin_parcasidir(self) -> None:
        """Bir QA cevabı Sokratik moda servis edilirse merdiven baypas edilir.

        Bugün `_lookup_cache` yalnız QA modunda çağrılıyor, yani bu özellik ikinci
        katman. Tam da bu yüzden test ediliyor: çağrı yerindeki `if` bir gün
        gevşerse anahtarın kendisi hâlâ ayırıyor olmalı (Anayasa II deseni).
        """
        soru = "Deadlock koşulları nedir?"
        assert question_hash(ChatMode.QA, soru) != question_hash(ChatMode.SOCRATIC, soru)
        assert question_hash(ChatMode.QA, soru) != question_hash(ChatMode.EXAM, soru)

    def test_harf_buyuklugu_korunur(self) -> None:
        """Türkçede i/İ ve ı/I dönüşümü kayıplıdır; küçültme "aynı soru"yu bozar.

        "İş" ve "iş" farklı sözcüklerdir. Anahtar küçültseydi bu iki soru aynı
        önbellek satırını paylaşırdı ve biri diğerinin cevabını alırdı.
        """
        assert question_hash(ChatMode.QA, "Deadlock") != question_hash(ChatMode.QA, "deadlock")
        assert question_hash(ChatMode.QA, "İşlem") != question_hash(ChatMode.QA, "işlem")
        assert question_hash(ChatMode.QA, "IŞIK") != question_hash(ChatMode.QA, "ışık")

    def test_bosluk_farklari_ayni_anahtari_verir(self) -> None:
        """Kullanıcının fazladan boşluğu ayrı bir soru değildir."""
        temel = question_hash(ChatMode.QA, "Deadlock nedir?")
        assert question_hash(ChatMode.QA, "  Deadlock   nedir?  ") == temel
        assert question_hash(ChatMode.QA, "Deadlock\n\tnedir?") == temel

    def test_unicode_bicimi_normalize_edilir(self) -> None:
        """Aynı harf iki kod noktası dizisiyle yazılabilir; ikisi aynı sorudur.

        "ş" tek kod noktası (U+015F) ya da "s" + birleşik çengel (U+0327) olarak
        gelebilir — kopyala/yapıştır kaynağına göre değişir. NFC ikisini birleştirir.

        Ayrışık biçim kaynak dosyaya GÖMÜLMÜYOR, `NFD` ile üretiliyor: gömülü
        olsaydı dosyayı normalize eden herhangi bir araç iki dizeyi eşitler ve
        test hiçbir şey sınamadan yeşil yanardı.
        """
        tek_kod_noktasi = "İşletim sistemi nedir?"
        ayrisik = unicodedata.normalize("NFD", tek_kod_noktasi)
        assert tek_kod_noktasi != ayrisik, "NFD ayrışık bir biçim üretmedi"
        assert question_hash(ChatMode.QA, ayrisik) == question_hash(ChatMode.QA, tek_kod_noktasi)

    def test_aksan_farki_ayri_sorudur(self) -> None:
        """Normalize etmek başka, harfi değiştirmek başka.

        "çözüm" ile "cozum" aynı soru DEĞİLDİR: anahtar aksanı katlasaydı önbellek
        kullanıcının yazdığından farklı bir sorunun cevabını dönebilirdi. (Kapsam
        sinyali aksanı katlar — orada amaç eşleştirme, burada kimlik.)
        """
        assert question_hash(ChatMode.QA, "çözüm") != question_hash(ChatMode.QA, "cozum")

    def test_anahtar_deterministik(self) -> None:
        soru = "Deadlock koşulları nedir?"
        assert question_hash(ChatMode.QA, soru) == question_hash(ChatMode.QA, soru)


# ---------------------------------------------------------------------------
# Uç davranışı
# ---------------------------------------------------------------------------


async def _ask(
    client: AsyncClient, course_id: str, headers: dict[str, str], question: str, **extra: object
) -> dict[str, object]:
    response = await client.post(
        f"/courses/{course_id}/chat", json={"question": question, **extra}, headers=headers
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


class TestModGuvenligi:
    async def test_qa_cevabi_sokratik_turda_servis_edilmez(
        self, client: AsyncClient, users: UserFactory, pipeline: Pipeline
    ) -> None:
        """Merdivenin baypas edilebileceği en kısa yol buydu.

        Öğrenci soruyu önce QA modunda sorup cevabı önbelleğe düşürür, sonra aynı
        soruyla Sokratik oturum açar. Anahtar modu taşımasaydı ikinci turda kaynaklı
        tam cevap dönerdi ve merdiven hiç çalışmazdı.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")
        parca = pipeline.serve(course_id, make_chunk())
        pipeline.answers(
            sourced_answer(parca, "QA cevabı: dört koşul aynı anda sağlanır."),
            sourced_answer(parca, "Sokratik ipucu: hangi koşulun sağlanmadığını düşün."),
        )
        soru = "Deadlock koşulları nedir?"

        qa = await _ask(client, course_id, ayse, soru)
        sokratik = await _ask(client, course_id, ayse, soru, mode="socratic")

        assert qa["cached"] is False
        assert sokratik["cached"] is False, "QA cevabı Sokratik turda önbellekten döndü"
        assert sokratik["answer"] != qa["answer"]

    async def test_sokratik_tur_onbellege_yazmaz(
        self, client: AsyncClient, users: UserFactory, pipeline: Pipeline
    ) -> None:
        """Ters yön: Sokratik ipucu QA'ya sızarsa öğrenci cevabı alamamış olur.

        Sokratik tur önbelleğe hiç yazmaz — ipucu oturumun kademesine bağlıdır ve
        soruya bağlı bir anahtarla saklanamaz.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")
        parca = pipeline.serve(course_id, make_chunk())
        pipeline.answers(
            sourced_answer(parca, "Sokratik ipucu"),
            sourced_answer(parca, "QA cevabı"),
        )
        soru = "Deadlock koşulları nedir?"

        await _ask(client, course_id, ayse, soru, mode="socratic")
        qa = await _ask(client, course_id, ayse, soru)

        assert qa["cached"] is False
        assert qa["answer"] == "QA cevabı"

    async def test_harf_buyuklugu_farkli_soru_sayilir(
        self, client: AsyncClient, users: UserFactory, pipeline: Pipeline
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")
        parca = pipeline.serve(course_id, make_chunk())
        pipeline.answers(
            sourced_answer(parca, "birinci"),
            sourced_answer(parca, "ikinci"),
        )

        await _ask(client, course_id, ayse, "Deadlock nedir?")
        ikinci = await _ask(client, course_id, ayse, "deadlock nedir?")

        assert ikinci["cached"] is False

    async def test_fazladan_bosluk_ayni_soru_sayilir(
        self, client: AsyncClient, users: UserFactory, pipeline: Pipeline
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")
        parca = pipeline.serve(course_id, make_chunk())
        pipeline.answers(sourced_answer(parca, "tek cevap"))

        await _ask(client, course_id, ayse, "Deadlock nedir?")
        ikinci = await _ask(client, course_id, ayse, "Deadlock    nedir?")

        assert ikinci["cached"] is True


class TestBozukOnbellekSatiri:
    @pytest.mark.parametrize(
        ("ad", "bozuk"),
        [
            ("bos_nesne", {}),
            ("statu_yok", {"text": "bir cevap", "citations": []}),
            ("tanimsiz_statu", {"status": "kesinlikle_dogru", "text": "x", "citations": []}),
            ("metin_yok", {"status": "answered", "citations": []}),
            ("atif_listesi_degil", {"status": "answered", "text": "x", "citations": "bozuk"}),
            (
                "atif_alani_eksik",
                {"status": "answered", "text": "x", "citations": [{"file_name": "a.pdf"}]},
            ),
            (
                "chunk_id_uuid_degil",
                {
                    "status": "answered",
                    "text": "x",
                    "citations": [{"chunk_id": "uuid-degil", "file_name": "a", "location": "b"}],
                },
            ),
        ],
    )
    async def test_bozuk_satir_yok_sayilir_ve_cevap_yeniden_uretilir(
        self,
        client: AsyncClient,
        users: UserFactory,
        pipeline: Pipeline,
        worker_engine: AsyncEngine,
        ad: str,
        bozuk: dict[str, object],
    ) -> None:
        """Önbellek bir hızlandırmadır, doğruluk kaynağı değildir.

        Bozuk bir satır yüzünden 500 dönmek, ürünü tek bir kötü JSON'la
        durdurulabilir kılardı; sessizce boş cevap dönmek ise daha kötü olurdu.
        Doğru davranış satırı yok saymak ve cevabı yeniden üretmektir.
        """
        del ad  # parametre kimliği yalnız hata mesajında okunur
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_id = await _create_course(client, ayse, "COME301")
        parca = pipeline.serve(course_id, make_chunk())
        pipeline.answers(sourced_answer(parca, "yeniden üretilmiş cevap"))
        soru = "Deadlock nedir?"

        async with worker_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO answer_cache (course_id, question_hash, answer) "
                    "VALUES (:cid, :hash, CAST(:answer AS jsonb))"
                ),
                {
                    "cid": UUID(course_id),
                    "hash": question_hash(ChatMode.QA, soru),
                    "answer": json.dumps(bozuk),
                },
            )

        body = await _ask(client, course_id, ayse, soru)

        assert body["cached"] is False
        assert body["answer"] == "yeniden üretilmiş cevap"

    async def test_saglam_satir_gercekten_okunur(
        self,
        client: AsyncClient,
        users: UserFactory,
        pipeline: Pipeline,
        worker_engine: AsyncEngine,
    ) -> None:
        """Pozitif kontrol: yukarıdaki testler ancak okuma yolu çalışıyorsa anlamlı.

        Bu olmadan "bozuk satır yok sayıldı" iddiası, önbelleğin hiç okunmadığı
        bir dünyada da yeşil yanardı.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_id = await _create_course(client, ayse, "COME301")
        parca = pipeline.serve(course_id, make_chunk())
        pipeline.answers(sourced_answer(parca, "üretimden gelen"))
        soru = "Deadlock nedir?"

        async with worker_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO answer_cache (course_id, question_hash, answer) "
                    "VALUES (:cid, :hash, CAST(:answer AS jsonb))"
                ),
                {
                    "cid": UUID(course_id),
                    "hash": question_hash(ChatMode.QA, soru),
                    "answer": json.dumps(
                        {
                            "status": "answered",
                            "text": "önbellekten gelen",
                            "citations": [
                                {
                                    "chunk_id": str(parca.chunk_id),
                                    "file_name": parca.file_name,
                                    "location": parca.location,
                                    "quote": "alıntı",
                                }
                            ],
                        }
                    ),
                },
            )

        body = await _ask(client, course_id, ayse, soru)

        assert body["cached"] is True
        assert body["answer"] == "önbellekten gelen"
        assert pipeline.generator.calls == 0, "önbellek isabetinde LLM çağrılmamalı"


class TestDersIzolasyonuVeritabaninda:
    async def test_ayni_anahtar_iki_derste_ayri_satirdir(
        self,
        client: AsyncClient,
        users: UserFactory,
        pipeline: Pipeline,
        worker_engine: AsyncEngine,
    ) -> None:
        """`test_chat_api` bunu uç davranışıyla sınıyor; burada satır düzeyinde.

        İki katman da bağımsız olarak doğru olmalı (Anayasa II): uçtaki
        `course_id` filtresi kaldırılsa bile benzersizlik kısıtı ve okuma
        koşulu dersi ayırıyor olmalı.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders_a = await _create_course(client, ayse, "COME301")
        ders_b = await _create_course(client, ayse, "COME302")
        parca_a = pipeline.serve(ders_a, make_chunk(file_name="a.pdf"))
        parca_b = pipeline.serve(ders_b, make_chunk(file_name="b.pdf"))
        pipeline.answers(
            sourced_answer(parca_a, "A cevabı"),
            sourced_answer(parca_b, "B cevabı"),
        )
        soru = "Deadlock nedir?"

        await _ask(client, ders_a, ayse, soru)
        b_yaniti = await _ask(client, ders_b, ayse, soru)

        assert b_yaniti["answer"] == "B cevabı"
        assert b_yaniti["cached"] is False

        async with worker_engine.connect() as conn:
            satirlar = (
                await conn.execute(
                    text(
                        "SELECT course_id, answer->>'text' AS metin FROM answer_cache "
                        "WHERE question_hash = :hash ORDER BY answer->>'text'"
                    ),
                    {"hash": question_hash(ChatMode.QA, soru)},
                )
            ).all()

        assert [(str(r.course_id), r.metin) for r in satirlar] == [
            (ders_a, "A cevabı"),
            (ders_b, "B cevabı"),
        ]


class TestNeyinSaklandigi:
    async def test_atifsiz_cevap_saklanmaz(
        self,
        client: AsyncClient,
        users: UserFactory,
        pipeline: Pipeline,
        worker_engine: AsyncEngine,
    ) -> None:
        """`answered` olması yetmez; kaynaksız bir cevap kalıcılaştırılmaz.

        Kaynaksız cevap zaten kullanıcıya gitmiyor (FR-013), ama önbellek onu
        saklarsa kural bir kez daha kırılmaya açık hâle gelir.
        """
        from app.contracts import AnswerStatus, GeneratedAnswer

        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_id = await _create_course(client, ayse, "COME301")
        pipeline.serve(course_id, make_chunk())
        pipeline.answers(
            GeneratedAnswer(
                status=AnswerStatus.ANSWERED,
                mode=ChatMode.QA,
                text="Kaynaksız ama iddialı bir cevap.",
                citations=[],
            )
        )

        await _ask(client, course_id, ayse, "Deadlock nedir?")

        async with worker_engine.connect() as conn:
            sayi = (await conn.execute(text("SELECT count(*) FROM answer_cache"))).scalar_one()

        assert sayi == 0
