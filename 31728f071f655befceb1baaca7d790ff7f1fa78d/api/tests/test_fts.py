"""FTS şeridinin sorgu ayrıştırma kararlarını sabitleyen testler.

`fts.py` iki karar veriyor ve ikisi de sessizce bozulabilecek türden:

1. **`websearch_to_tsquery` seçildi**, çünkü öğrencinin tırnağını ve eksisini yalnız o
   anlıyor. Bu davranış kaybolursa hiçbir hata alınmaz, arama sadece kötüleşir.
2. **Örtük VE, açık işaret yoksa VEYA'ya gevşetilir.** Gerekçe ölçümdü: VE ile doğal
   dilde sorulan soruların 10'da 9'u sıfır sonuç veriyordu. Bu test o ölçümü kalıcı
   hâle getirir — biri gevşetmeyi kaldırırsa FTS şeridi hatta durur ama iş yapmaz
   (Anayasa XI: etkin görünüp iş yapmayan bileşen kusurdur) ve aşağıdaki test kırmızı
   yanar.

Sonda sorgusu (`_KATI_SONDA`) bilinçli olarak `fts.py`'nin SQL'ini tekrar etmez:
karşılaştırılan şey PostgreSQL'in ham `websearch_to_tsquery` davranışıdır.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.db import rls_session
from app.modules.retrieval.fts import _SQL, fts_search, uses_explicit_operators
from tests.conftest import WORKER_DSN, UserFactory
from tests.factories import create_course, seed_document


@pytest.fixture
async def worker_engine(clean_tables: None) -> AsyncIterator[AsyncEngine]:
    """Chunk yazımı üretimdeki gibi RLS'i atlayan `dou_worker` rolüyle yapılır.

    Bu fixture `test_retrieval`'da da aynı gövdeyle duruyor ve eskiden buraya
    oradan bağlanıyordu. Bağ koptu: bir test modülünün başka bir test modülünden
    fixture alması, uzaktaki dosyada yapılan bir düzeltmenin burayı da sessizce
    değiştirmesi demekti. Kopyanın gerçek adresi `conftest.py`; oraya taşımak
    fixture'ları tek dosyada toplayan ayrı bir iştir ve bu turun kapsamı dışında.
    """
    engine = create_async_engine(WORKER_DSN)
    yield engine
    await engine.dispose()


# ---------------------------------------------------------------------------
# Materyal
#
# Korpus `test_retrieval`'dan içe aktarılmıyor, burada duruyor. Metin sabitleri
# yalnız iki dosyada geçtiği için `tests.factories`'e de girmedi (Anayasa XI:
# eşik üç yerdir); bir test modülünü diğerinin materyaline bağlamak ise ödediği
# tekrarsızlıktan fazlasını geri alırdı — orada bir pasaj değiştiğinde burada
# `ts_rank` sıralaması üzerine kurulu iddialar sebepsiz kırılırdı.
#
# Bu şeridin bağımlılıkları da farklı: aşağıdaki testler yalnız `fts` kolonunu
# okur, o yüzden tohumlama gömüsüz yapılır (`embeddings` varsayılan `False`).
# ---------------------------------------------------------------------------

DEADLOCK_TR: list[tuple[int, str]] = [
    (
        1,
        "Deadlock, iki ya da daha fazla sürecin birbirinin tuttuğu kaynağı beklemesi "
        "yüzünden hiçbirinin ilerleyememesi durumudur.",
    ),
    (
        2,
        "Deadlock oluşması için dört koşulun aynı anda sağlanması gerekir: karşılıklı "
        "dışlama, tut ve bekle, kesintiye uğratılamama, döngüsel bekleme. Bu dört koşula "
        "Coffman koşulları denir.",
    ),
    (
        3,
        "Banker's Algorithm, kaynak taleplerini güvenli durum kontrolünden geçirerek "
        "deadlock oluşmasını önler; talebi vermek sistemi güvensiz duruma sokacaksa süreç "
        "bekletilir.",
    ),
]

PROCESSES_EN: list[tuple[int, str]] = [
    (
        1,
        "The fork() system call creates a new process by duplicating the calling process. "
        "It returns 0 in the child and the child PID in the parent.",
    ),
    (
        2,
        "A context switch saves the state of the running process and restores the state of "
        "the next one. Its cost is what makes a very small round robin quantum wasteful.",
    ),
    (
        3,
        "Comparing scheduling algorithms is done in terms of asymptotic cost; a naive "
        "priority scan is O(n log n) once the ready queue is kept sorted.",
    ),
]

# `fts.py`'nin gevşetme öncesi hâli: websearch'ün örtük VE'si, olduğu gibi.
_KATI_SONDA = text(
    "SELECT count(*) FROM chunks c "
    "WHERE c.course_id = :course_id "
    "  AND c.fts @@ websearch_to_tsquery('simple', app.immutable_unaccent(:query))"
)


class TestAcikIsaretTespiti:
    """Gevşetme kararının girdisi — veritabanı gerektirmez."""

    @pytest.mark.parametrize(
        "sorgu",
        [
            '"page fault"',
            'deadlock "dört koşul"',
            "mutex -semaphore",
            "-fork",
            "deadlock or livelock",
            "deadlock OR livelock",
        ],
    )
    def test_acik_isaret_taniniyor(self, sorgu: str) -> None:
        assert uses_explicit_operators(sorgu) is True

    @pytest.mark.parametrize(
        "sorgu",
        [
            "deadlock koşulları nedir",
            "what does fork() return",
            "round robin quantum seçimi",
            # Sözcük içindeki tire işleç değildir: "kilitlenme-önleme" tek terimdir.
            "kilitlenme-önleme yöntemleri",
            # "veya" Türkçedir ve websearch_to_tsquery onu işleç saymaz; biz de saymayız.
            "deadlock veya livelock",
            "O(n log n) karmaşıklığı",
            "",
        ],
    )
    def test_sıradan_sorgu_isaret_sayilmaz(self, sorgu: str) -> None:
        assert uses_explicit_operators(sorgu) is False


class TestVeyaGevsetmesi:
    """Ölçümün kalıcı hâli: gevşetme kaldırılırsa bu sınıf kırmızı yanar."""

    async def test_dogal_dil_sorusu_kati_VE_ile_sifir_gevsetmeyle_sonuc_verir(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="05-deadlock.md",
            passages=DEADLOCK_TR,
        )
        # "nedir" materyalde geçmez; VE bunu da zorunlu kıldığı için hiçbir parça eşleşmez.
        sorgu = "deadlock koşulları nedir"

        async with rls_session(ayse_id) as session:
            kati = (
                await session.execute(_KATI_SONDA, {"course_id": ders, "query": sorgu})
            ).scalar_one()
            gevsek = await fts_search(session, course_id=ders, query=sorgu, limit=8)

        assert kati == 0, "kurgu bozulmuş: katı VE bu sorguda zaten eşleşiyor"
        assert gevsek, "gevşetme kaldırılmış — FTS şeridi doğal dil sorusunda ölü"
        assert "Coffman" in gevsek[0].text

    async def test_ts_rank_daha_cok_terim_eslesen_parcayi_one_alir(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """VEYA'nın geniş aday kümesini sıralama toparlar; yoksa gevşetme gürültü olurdu."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="05-deadlock.md",
            passages=DEADLOCK_TR,
        )

        async with rls_session(ayse_id) as session:
            # "deadlock" her üç parçada da geçer; kalan terimler yalnız Coffman parçasında.
            sonuc = await fts_search(
                session,
                course_id=ders,
                query="deadlock dört döngüsel bekleme nedir",
                limit=8,
            )

        assert len(sonuc) == len(DEADLOCK_TR), "VEYA tüm 'deadlock' geçen parçaları getirmeli"
        assert "Coffman" in sonuc[0].text, "en çok terimi eşleyen parça birinci olmalı"
        assert sonuc[0].fts_score > sonuc[-1].fts_score


class TestAcikIsaretlerKorunur:
    """Öğrenci işaret kullandıysa niyeti bozulmaz — gevşetmenin sınırı budur."""

    async def test_eksi_isareti_parcayi_eler(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="05-deadlock.md",
            passages=DEADLOCK_TR,
        )

        async with rls_session(ayse_id) as session:
            hepsi = await fts_search(session, course_id=ders, query="deadlock", limit=8)
            elenmis = await fts_search(session, course_id=ders, query="deadlock -Coffman", limit=8)

        assert any("Coffman" in parca.text for parca in hepsi)
        assert all("Coffman" not in parca.text for parca in elenmis)
        assert elenmis, "eksi işareti tüm sonuçları silmemeli, yalnız eleneni"

    async def test_tirnakli_ifade_bitisiklik_arar(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """`"tut ve bekle"` bir ifadedir; sözcükleri ayrı ayrı geçen parça eşleşmez."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="05-deadlock.md",
            passages=DEADLOCK_TR,
        )

        async with rls_session(ayse_id) as session:
            ifade = await fts_search(session, course_id=ders, query='"tut ve bekle"', limit=8)
            ters = await fts_search(session, course_id=ders, query='"bekle ve tut"', limit=8)

        assert len(ifade) == 1, "ifade yalnız dört koşulu sayan parçada geçiyor"
        assert "Coffman" in ifade[0].text
        assert ters == [], "ters sırada yazılan ifade eşleşmemeli"


class TestFtsIzolasyon:
    async def test_fts_baska_dersin_parcasini_getirmez(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Zorunlu course_id filtresi dense şeridinde olduğu gibi burada da geçerli."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders_a = await create_course(client, ayse, "COME301")
        ders_b = await create_course(client, ayse, "COME302")
        await seed_document(
            worker_engine,
            course_id=ders_a,
            uploaded_by=ayse_id,
            file_name="a.md",
            passages=DEADLOCK_TR,
        )
        await seed_document(
            worker_engine,
            course_id=ders_b,
            uploaded_by=ayse_id,
            file_name="b.md",
            passages=DEADLOCK_TR,
        )

        async with rls_session(ayse_id) as session:
            sonuc = await fts_search(session, course_id=ders_a, query="Coffman", limit=8)

        assert sonuc
        assert {parca.file_name for parca in sonuc} == {"a.md"}


class TestFtsSiralamaBilgisi:
    async def test_yalnizca_fts_skoru_doldurulur(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Şerit ayrımı korunmalı: birleştirme service.py'nin işi, fts.py'nin değil."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="01-processes.md",
            passages=PROCESSES_EN,
        )

        async with rls_session(ayse_id) as session:
            sonuc = await fts_search(session, course_id=ders, query="context switch", limit=8)

        assert sonuc
        for parca in sonuc:
            assert parca.fts_score > 0.0
            assert parca.dense_score == 0.0
            assert parca.fused_score == 0.0


class TestSiralamaYenidenUretilebilir:
    """Eşit `ts_rank`'li parçaların sırası korpus yeniden kurulunca DEĞİŞMEMELİ.

    R2'nin ölçtüğü kusur: eşitlik bozma `c.id`'ye bağlıydı ve o sütun
    `gen_random_uuid()` ile üretiliyor. Aynı materyal yeniden ingest edildiğinde
    her parça yeni bir kimlik alıyor, eşit rank'li satırların sırası keyfî olarak
    değişiyordu — tek bir korpus içinde kararlı, korpuslar ARASINDA değil.

    Etkisi kozmetik değildi: yeniden kurulan indekste Recall@5 0.981 → 0.971'e
    düştü ve T044'ün MRR güven aralığı sıfırın bir yanından diğerine geçti;
    "hibrit dense'ten iyidir" hükmü bu yüzden geri çekildi. Ölçüm yeniden
    üretilemiyorsa ölçtüğü şeyin de anlamı kalmaz.

    ## Bu test neden SQL metnine bakıyor

    Davranışsal kurmak istedim ve iki kez başarısız oldum. İlk yazım kendi
    SQL'ini yazıyordu, yani `fts.py` bilerek bozulduğunda bile yeşil kaldı —
    kendi kopyasını sınıyordu. İkinci yazım `fts_search`'ü çağırdı ama parça
    kimliklerini yeniden atayarak "korpus yeniden kuruldu"yu taklit etmeye
    çalıştı; o da mutasyonu yakalamadı.

    Kimliğe bağlı sıralamayı davranışla yakalamanın dürüst yolu aynı korpusu iki
    kez ingest edip sıraları karşılaştırmak; ama bozuk kodda bile üç eleman
    tesadüfen aynı sırada gelebilir (1/6), yani test kırılgan olurdu ve kırılgan
    bir nöbetçi, nöbetçi değildir.

    O yüzden iddia yapısal: sıra ifadesi kimliğe DEĞİL içeriğe (`document_id`,
    `chunk_index`) bağlı olmalı. Sınadığı şey davranışın kaynağının ta kendisi ve
    `fts.py` bozulduğunda kesinlikle kırmızı yanıyor — doğrulandı.
    """

    def test_esitlik_bozma_icerige_bagli_kimlige_degil(self) -> None:
        sql = str(_SQL)

        assert "ORDER BY rank DESC, c.document_id, c.chunk_index" in sql, (
            "iç sorgunun eşitlik bozması içerikten türemeli"
        )
        assert "ORDER BY m.rank DESC, m.document_id, m.chunk_index" in sql, (
            "dış sorgunun eşitlik bozması içerikten türemeli"
        )
        assert "ORDER BY rank DESC, c.id" not in sql, (
            "eşitlik bozma chunk kimliğine geri döndü — kimlik her ingest'te "
            "yeniden üretiliyor, ölçüm sonuçları korpus kurulduğunda kayar"
        )
        assert "ORDER BY m.rank DESC, m.id" not in sql

    async def test_esit_rankli_parcalar_belge_ici_sirayla_doner(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Yapısal iddianın davranıştaki karşılığı: eşit rank → chunk_index sırası."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = UserFactory.auth(ayse_id)
        course_id = await create_course(client, ayse, "COME301")

        ayni_metin = "Semafor kritik bolgeyi korur."
        await seed_document(
            worker_engine,
            course_id=course_id,
            uploaded_by=ayse_id,
            file_name="a.md",
            passages=[(1, ayni_metin), (2, ayni_metin), (3, ayni_metin)],
        )

        async with rls_session(ayse_id) as session:
            sonuclar = await fts_search(session, course_id=course_id, query="semafor", limit=10)

        assert len(sonuclar) == 3, "üç parça da eşleşmeli, yoksa vaka geçersiz"
        # Rank'lerin gerçekten eşit olduğunu doğrula: eşit değillerse sıra
        # eşitlik bozmaya hiç düşmez ve bu test sessizce hiçbir şey ölçmez.
        assert len({round(c.fts_score, 9) for c in sonuclar}) == 1

        async with rls_session(ayse_id) as session:
            konum = dict(
                (
                    await session.execute(
                        text("SELECT id, chunk_index FROM chunks WHERE course_id = :c"),
                        {"c": course_id},
                    )
                ).all()
            )
        assert [konum[c.chunk_id] for c in sonuclar] == [0, 1, 2]


class TestBelgePolitikasi:
    """Ders politikası adayları LIMIT uygulanmadan önce SQL'de daraltır."""

    async def test_izinli_belgeler_fts_aday_kumesini_daraltir(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("policy-filter@dogus.edu.tr")
        ayse = UserFactory.auth(ayse_id)
        course_id = await create_course(client, ayse, "POL-FTS")
        allowed_doc = await seed_document(
            worker_engine,
            course_id=course_id,
            uploaded_by=ayse_id,
            file_name="izinli.md",
            passages=[(1, "Deadlock Coffman koşulları kaynak bekleme döngüsüdür.")],
        )
        blocked_doc = await seed_document(
            worker_engine,
            course_id=course_id,
            uploaded_by=ayse_id,
            file_name="kapali.md",
            passages=[(1, "Deadlock Coffman koşulları kaynak bekleme döngüsüdür.")],
        )

        async with rls_session(ayse_id) as session:
            only_allowed = await fts_search(
                session,
                course_id=course_id,
                query="deadlock",
                limit=10,
                document_ids=(allowed_doc.document_id,),
            )
            none_allowed = await fts_search(
                session,
                course_id=course_id,
                query="deadlock",
                limit=10,
                document_ids=(),
            )
            unrestricted = await fts_search(
                session,
                course_id=course_id,
                query="deadlock",
                limit=10,
                document_ids=None,
            )

        assert {chunk.document_id for chunk in only_allowed} == {allowed_doc.document_id}
        assert none_allowed == []
        assert {chunk.document_id for chunk in unrestricted} == {allowed_doc.document_id, blocked_doc.document_id}
