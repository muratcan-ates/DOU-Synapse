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

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.db import rls_session
from app.modules.retrieval.fts import fts_search, uses_explicit_operators
from tests import test_retrieval
from tests.conftest import UserFactory
from tests.test_retrieval import DEADLOCK_TR, PROCESSES_EN, create_course, seed_document

#: Fixture'lar modüle özeldir; `conftest.py` bu şeridin dosyası olmadığı için
#: `worker_engine` kopyalanmak yerine bağlanır.
worker_engine = test_retrieval.worker_engine

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
