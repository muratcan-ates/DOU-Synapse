"""Hibrit retrieval testleri (T007).

Testler `hashing` embedding sağlayıcısıyla koşar: deterministik, ağsız, model
indirmez. Sağlayıcı anlamsal değildir — sözcük örtüşmesine göre gerçek bir benzerlik
üretir. Bu yüzden burada **anlamsal kalite iddiası yoktur**; sınanan şey hattın
mekaniğidir: izolasyon, birleştirme, kapı ve dil/token davranışı. Anlamsal kalite
gerçek modelle ölçülür ve T043'te raporlanır (Anayasa III).

Chunk'lar üretimdeki gibi `dou_worker` rolüyle yazılır (chunks tablosunda bilinçli
olarak INSERT politikası yoktur), okuma ise `dou_app` rolüyle ve RLS altında yapılır.
Superuser ile okunsaydı izolasyon testleri hiçbir şey kanıtlamadan yeşil yanardı.
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Sequence
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.contracts import RetrievedChunk, Retriever
from app.core.config import get_settings
from app.core.db import rls_session
from app.modules.ingestion.embedding import get_embedding_provider
from app.modules.retrieval import (
    EvidenceLevel,
    HybridRetriever,
    assess_evidence,
    lexical_coverage,
    retrieve,
)
from app.modules.retrieval.dense import dense_search
from app.modules.retrieval.fts import fts_search
from app.modules.retrieval.fusion import max_possible_score, reciprocal_rank_fusion
from app.modules.retrieval.scope import COVERAGE_CEILING, FTS_CEILING
from app.modules.retrieval.service import fuse
from tests.conftest import WORKER_DSN, UserFactory

# ---------------------------------------------------------------------------
# Materyal — TR/EN karışık, teknik tokenlar birebir korunmuş hâlde
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

# Aynı konu, BAŞKA ders. İzolasyon testinin anlamlı olması için metin kasten benzer:
# farklı konulu materyalle "gelmedi" demek izolasyonu değil, alakasızlığı kanıtlardı.
DEADLOCK_BASKA_DERS: list[tuple[int, str]] = [
    (
        1,
        "Deadlock oluşması için dört koşulun aynı anda sağlanması gerekir: karşılıklı "
        "dışlama, tut ve bekle, kesintiye uğratılamama, döngüsel bekleme. Bu dört koşula "
        "Coffman koşulları denir.",
    ),
    (
        2,
        "Banker's Algorithm kaynak taleplerini güvenli durum kontrolünden geçirir ve "
        "deadlock oluşmasını önler.",
    ),
]


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------


@pytest.fixture
async def worker_engine(clean_tables: None) -> AsyncIterator[AsyncEngine]:
    """Chunk yazımı üretimdeki gibi RLS'i atlayan `dou_worker` rolüyle yapılır."""
    engine = create_async_engine(WORKER_DSN)
    yield engine
    await engine.dispose()


async def seed_document(
    engine: AsyncEngine,
    *,
    course_id: UUID,
    uploaded_by: UUID,
    file_name: str,
    passages: Sequence[tuple[int, str]],
    embedding_space: str | None = None,
) -> UUID:
    """Bir belge ve chunk'larını yazar; embedding'ler yapılandırılmış sağlayıcıdan gelir.

    Ingestion hattını çağırmak yerine doğrudan yazılır: burada sınanan retrieval,
    ayrıştırma değil. Metin üzerinde tam kontrol, testlerin ne kanıtladığını okunur kılar.
    """
    vectors = get_embedding_provider().embed_documents([body for _, body in passages])
    async with engine.begin() as conn:
        document_id = (
            await conn.execute(
                text(
                    "INSERT INTO documents (course_id, uploaded_by, file_name, file_type, "
                    "storage_path, file_hash, byte_size, status, page_count, chunk_count) "
                    "VALUES (:course_id, :uploaded_by, :file_name, 'md', :path, :hash, "
                    "4096, 'completed', :pages, :chunks) RETURNING id"
                ),
                {
                    "course_id": course_id,
                    "uploaded_by": uploaded_by,
                    "file_name": file_name,
                    "path": f"courses/{course_id}/{uuid4().hex}.md",
                    "hash": uuid4().hex,
                    "pages": len(passages),
                    "chunks": len(passages),
                },
            )
        ).scalar_one()

        await conn.execute(
            text(
                "INSERT INTO chunks (course_id, document_id, chunk_index, page_number, "
                "section_title, content_type, text, token_count, embedding, embedding_space) "
                "VALUES (:course_id, :document_id, :chunk_index, :page_number, "
                ":section_title, 'text', :text, :token_count, CAST(:embedding AS vector), "
                ":embedding_space)"
            ),
            [
                {
                    "course_id": course_id,
                    "document_id": document_id,
                    "chunk_index": index,
                    "page_number": page,
                    "section_title": None,
                    "text": body,
                    "token_count": max(1, len(body) // 4),
                    "embedding": str(vector),
                    # Varsayılan `None`: 0006 öncesi yazılmış satırların hâli. Testlerin
                    # çoğu damgayı umursamaz ve damgasız korpus üzerinde koşarak
                    # "damgasız satır aramayı durdurmaz" iddiasını da sürekli sınar.
                    "embedding_space": embedding_space,
                }
                for index, ((page, body), vector) in enumerate(zip(passages, vectors, strict=True))
            ],
        )
    return document_id


async def create_course(client: AsyncClient, headers: dict[str, str], code: str) -> UUID:
    response = await client.post(
        "/courses", json={"code": code, "title": f"{code} Dersi"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["id"])


#: Uygulama katmanındaki zorunlu `course_id` filtresi OLMADAN aynı aramayı yapan sonda.
#: İzolasyonun iki katmanını birbirinden ayırmanın tek yolu bu: birinci katmanı
#: kaldırıp ikincisinin tek başına ne yaptığını görmek (Anayasa II).
_FILTRESIZ_SONDA = text(
    "SELECT c.id, c.course_id FROM chunks c "
    "ORDER BY c.embedding <=> CAST(:query_vector AS vector) LIMIT 50"
)


async def filtresiz_gorunen_dersler(user_id: UUID, query: str) -> set[UUID]:
    """Uygulama filtresi olmadan, verilen kullanıcının oturumunda görünen ders kimlikleri."""
    vector = get_embedding_provider().embed_query(query)
    async with rls_session(user_id) as session:
        rows = (await session.execute(_FILTRESIZ_SONDA, {"query_vector": str(vector)})).all()
    return {row.course_id for row in rows}


# ---------------------------------------------------------------------------
# 1. İzolasyon — pazarlıksız
# ---------------------------------------------------------------------------


class TestIzolasyon:
    """Ders izolasyonu iki katmanlıdır; her katmanın tek tek iş yaptığı kanıtlanır."""

    async def test_baska_dersin_parcasi_hicbir_kosulda_donmez(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """İki ders, neredeyse aynı metin. A'da arama B'nin parçasını getirmez."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders_a = await create_course(client, ayse, "COME301")
        ders_b = await create_course(client, ayse, "COME302")

        await seed_document(
            worker_engine,
            course_id=ders_a,
            uploaded_by=ayse_id,
            file_name="05-deadlock.md",
            passages=DEADLOCK_TR,
        )
        await seed_document(
            worker_engine,
            course_id=ders_b,
            uploaded_by=ayse_id,
            file_name="baska-ders-deadlock.md",
            passages=DEADLOCK_BASKA_DERS,
        )

        async with rls_session(ayse_id) as session:
            sonuc = await HybridRetriever(session).search(
                course_id=ders_a, query="deadlock dört koşul Coffman", limit=8
            )
            b_chunk_sayisi = (
                await session.execute(
                    text("SELECT count(*) FROM chunks WHERE course_id = :cid"),
                    {"cid": ders_b},
                )
            ).scalar_one()

        assert sonuc, "A dersinde sonuç bekleniyordu"
        assert b_chunk_sayisi == len(DEADLOCK_BASKA_DERS), "B dersinin materyali yazılmamış"
        dosyalar = {chunk.file_name for chunk in sonuc}
        assert dosyalar == {"05-deadlock.md"}, f"başka dersin dosyası sızdı: {dosyalar}"

    async def test_rls_uye_olunmayan_dersi_uygulama_filtresi_olmadan_da_kapatir(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """İKİNCİ KATMAN: uygulama filtresi kaldırılsa bile RLS yabancı dersi kapatır."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")

        ders_a = await create_course(client, ayse, "COME301")
        ders_b = await create_course(client, ayse, "COME302")
        eklendi = await client.post(
            f"/courses/{ders_a}/members",
            json={"email": "burak@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )
        assert eklendi.status_code == 201, eklendi.text

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
            passages=DEADLOCK_BASKA_DERS,
        )

        gorunen = await filtresiz_gorunen_dersler(burak_id, "deadlock dört koşul")

        assert gorunen == {ders_a}, (
            "Burak yalnız A dersinin üyesi; uygulama filtresi olmadan bile B görünmemeli. "
            f"görünen: {gorunen}"
        )

    async def test_politika_bozulunca_yabanci_parca_gercekten_sizar(
        self,
        client: AsyncClient,
        users: UserFactory,
        worker_engine: AsyncEngine,
        admin_engine: AsyncEngine,
    ) -> None:
        """RLS'in taşıyıcı olduğunun kanıtı — politika bilerek bozulur (Anayasa II).

        Bir üstteki test "yabancı parça gelmiyor" diyor. Tek başına bu, izolasyonun
        RLS'ten geldiğini KANITLAMAZ: veri hiç yazılmamış olsaydı ya da sorgu yanlış
        kurulmuş olsaydı da aynı yeşil yanardı. Kanıt, politikayı gevşetince sonucun
        DEĞİŞMESİDİR. Değişmiyorsa yeşil renk tesadüftür ve izolasyon testi hiçbir şey
        ölçmüyordur.

        Politika `finally` ile geri alınır; bozuk bırakılırsa aynı oturumdaki diğer
        izolasyon testleri sessizce anlamsızlaşır.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        burak_id = await users.create("burak@dogus.edu.tr")

        ders_a = await create_course(client, ayse, "COME301")
        ders_b = await create_course(client, ayse, "COME302")
        await client.post(
            f"/courses/{ders_a}/members",
            json={"email": "burak@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )
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
            passages=DEADLOCK_BASKA_DERS,
        )
        sorgu = "deadlock dört koşul"

        assert await filtresiz_gorunen_dersler(burak_id, sorgu) == {ders_a}

        async with admin_engine.begin() as conn:
            await conn.execute(text("ALTER POLICY chunks_member_read ON chunks USING (true)"))
        try:
            sizinti = await filtresiz_gorunen_dersler(burak_id, sorgu)
        finally:
            async with admin_engine.begin() as conn:
                await conn.execute(
                    text(
                        "ALTER POLICY chunks_member_read ON chunks USING (app.is_member(course_id))"
                    )
                )

        assert sizinti == {ders_a, ders_b}, (
            "Politika gevşetildiği hâlde yabancı ders hâlâ görünmüyor: demek ki "
            "izolasyon testi RLS'i değil başka bir tesadüfü ölçüyor."
        )

        # Politikanın geri alındığı da kanıtlanmalı; aksi hâlde bu test kendinden
        # sonraki izolasyon testlerini sessizce çürütürdü.
        assert await filtresiz_gorunen_dersler(burak_id, sorgu) == {ders_a}

    async def test_uygulama_filtresi_iki_derse_de_uye_kullanicida_ayrimi_yapar(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """BİRİNCİ KATMAN: RLS'in yetmediği durumu gösterir — ve filtrenin kapattığını.

        Ayşe iki dersin de eğitmeni olduğu için RLS ikisini de açar. Uygulama
        filtresi kaldırılırsa yabancı parça GERÇEKTEN gelir; bu test o filtrenin
        dekoratif değil taşıyıcı olduğunun kanıtıdır. Filtre silinirse aşağıdaki
        son iddia kırmızı yanar.
        """
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
            passages=DEADLOCK_BASKA_DERS,
        )

        # RLS tek başına: Ayşe ikisinin de üyesi, dolayısıyla ikisi de görünür.
        gorunen = await filtresiz_gorunen_dersler(ayse_id, "deadlock dört koşul")
        assert gorunen == {ders_a, ders_b}, (
            "Bu senaryoda RLS tek başına ayrım yapmaz; testin kurgusu bozulmuş."
        )

        # Uygulama filtresi devrede: yalnız istenen ders.
        async with rls_session(ayse_id) as session:
            sonuc = await HybridRetriever(session).search(
                course_id=ders_a, query="deadlock dört koşul", limit=8
            )
        assert {chunk.file_name for chunk in sonuc} == {"a.md"}

    async def test_uye_olmayan_kullanici_hicbir_parca_goremez(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Fail-closed: üyeliği olmayan kullanıcı için arama boş döner, hata vermez."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        yabanci_id = await users.create("yabanci@dogus.edu.tr")
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="a.md",
            passages=DEADLOCK_TR,
        )

        async with rls_session(yabanci_id) as session:
            sonuc = await HybridRetriever(session).search(
                course_id=ders, query="deadlock dört koşul", limit=8
            )

        assert sonuc == []


# ---------------------------------------------------------------------------
# 2. RRF — saf fonksiyon, elle hesaplanmış beklentiye karşı
# ---------------------------------------------------------------------------


class TestReciprocalRankFusion:
    """Formül sınanıyor, model değil: gerçek embedding kullanılmaz."""

    def test_elle_hesaplanmis_sonuc(self) -> None:
        dense = ["a", "b", "c"]
        fts = ["c", "a", "d"]
        # k=60 ile beklenen:
        #   a: 1/61 + 1/62 = 0.0163934 + 0.0161290 = 0.0325224
        #   c: 1/63 + 1/61 = 0.0158730 + 0.0163934 = 0.0322664
        #   b: 1/62                                 = 0.0161290
        #   d: 1/63                                 = 0.0158730
        sonuc = reciprocal_rank_fusion([dense, fts], k=60)

        assert [anahtar for anahtar, _ in sonuc] == ["a", "c", "b", "d"]
        beklenen = {
            "a": 1 / 61 + 1 / 62,
            "c": 1 / 63 + 1 / 61,
            "b": 1 / 62,
            "d": 1 / 63,
        }
        for anahtar, skor in sonuc:
            assert skor == pytest.approx(beklenen[anahtar])

    def test_iki_listede_de_gecen_parca_tek_listedekini_geride_birakir(self) -> None:
        """RRF'in asıl işi: iki şeridin birden onayladığı parçayı yukarı çekmek."""
        sonuc = dict(reciprocal_rank_fusion([["ortak", "yalnız_dense"], ["ortak"]], k=60))
        assert sonuc["ortak"] > sonuc["yalnız_dense"]

    def test_k_buyudukce_ust_siralar_arasindaki_fark_yumusar(self) -> None:
        kucuk_k = dict(reciprocal_rank_fusion([["birinci", "ikinci"]], k=1))
        buyuk_k = dict(reciprocal_rank_fusion([["birinci", "ikinci"]], k=1000))
        assert kucuk_k["birinci"] / kucuk_k["ikinci"] > buyuk_k["birinci"] / buyuk_k["ikinci"]

    def test_ayni_siralamada_tekrarlanan_anahtar_cift_sayilmaz(self) -> None:
        tekrarli = dict(reciprocal_rank_fusion([["a", "a", "b"]], k=60))
        assert tekrarli["a"] == pytest.approx(1 / 61)

    def test_beraberlik_belirlenimci_bozulur(self) -> None:
        """Aynı girdi her koşumda aynı sırayı vermeli; yoksa regresyon testi kurulamaz."""
        siralamalar = [["x", "y"], ["y", "x"]]
        ilk = reciprocal_rank_fusion(siralamalar, k=60)
        for _ in range(5):
            assert reciprocal_rank_fusion(siralamalar, k=60) == ilk
        # x ve y skorca eşit; en iyi sıra da eşit; ilk görülme sırası x'i öne alır.
        assert [anahtar for anahtar, _ in ilk] == ["x", "y"]

    def test_bos_girdi_bos_doner(self) -> None:
        assert reciprocal_rank_fusion([], k=60) == []
        assert reciprocal_rank_fusion([[], []], k=60) == []

    def test_negatif_k_reddedilir(self) -> None:
        with pytest.raises(ValueError, match="negatif"):
            reciprocal_rank_fusion([["a"]], k=-1)

    def test_fused_skorun_ust_siniri_alakadan_bagimsizdir(self) -> None:
        """Kanıt eşiğinin neden fused skora uygulanamayacağının kanıtı.

        Alakasız bir korpus da, mükemmel bir korpus da aynı üst sınırı üretir: her
        sıralamanın bir birincisi vardır. Eşik olarak kullanılsaydı hiçbir şey ayırt
        etmezdi.
        """
        mukemmel = reciprocal_rank_fusion([["doğru"], ["doğru"]], k=60)
        alakasiz = reciprocal_rank_fusion([["saçma"], ["saçma"]], k=60)
        assert mukemmel[0][1] == alakasiz[0][1] == pytest.approx(max_possible_score(2, k=60))


# ---------------------------------------------------------------------------
# 3. Birleştirme — üç skor da doğru taşınıyor mu
# ---------------------------------------------------------------------------


def chunk(chunk_id: UUID, *, dense: float = 0.0, fts: float = 0.0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=uuid4(),
        file_name="a.md",
        page_number=1,
        slide_number=None,
        section_title=None,
        text="metin",
        dense_score=dense,
        fts_score=fts,
    )


class TestFuse:
    def test_uc_skor_da_dolar(self) -> None:
        ortak = uuid4()
        birlesik = fuse([chunk(ortak, dense=0.81)], [chunk(ortak, fts=0.42)], limit=8, rrf_k=60)
        assert len(birlesik) == 1
        assert birlesik[0].dense_score == pytest.approx(0.81)
        assert birlesik[0].fts_score == pytest.approx(0.42)
        assert birlesik[0].fused_score == pytest.approx(2 / 61)

    def test_tek_seritten_gelen_parcanin_diger_skoru_sifir_kalir(self) -> None:
        yalnız_dense = uuid4()
        birlesik = fuse([chunk(yalnız_dense, dense=0.7)], [], limit=8, rrf_k=60)
        assert birlesik[0].dense_score == pytest.approx(0.7)
        assert birlesik[0].fts_score == 0.0
        assert birlesik[0].fused_score == pytest.approx(1 / 61)

    def test_limit_uygulanir(self) -> None:
        parcalar = [chunk(uuid4(), dense=1.0 - index / 100) for index in range(10)]
        assert len(fuse(parcalar, [], limit=3, rrf_k=60)) == 3

    def test_bos_girdide_patlamaz(self) -> None:
        assert fuse([], [], limit=8, rrf_k=60) == []


# ---------------------------------------------------------------------------
# 4. Dil ve teknik token davranışı
# ---------------------------------------------------------------------------


class TestDilVeToken:
    async def test_turkce_ve_ingilizce_sorgu_dogru_belgeyi_getirir(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Materyal TR/EN karışık; her iki dilde de arama çalışmalı."""
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
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="01-processes.md",
            passages=PROCESSES_EN,
        )

        async with rls_session(ayse_id) as session:
            turkce = await HybridRetriever(session).search(
                course_id=ders, query="deadlock için gereken dört koşul nedir", limit=3
            )
            ingilizce = await HybridRetriever(session).search(
                course_id=ders, query="what does the fork() system call return", limit=3
            )

        assert turkce[0].file_name == "05-deadlock.md"
        assert "Coffman" in turkce[0].text
        assert ingilizce[0].file_name == "01-processes.md"
        assert "fork()" in ingilizce[0].text

    async def test_teknik_token_fts_ile_bulunur(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """`simple` konfigürasyonunun varlık sebebi: `fork()` köklendirilip bozulmaz."""
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
            sonuc = await fts_search(session, course_id=ders, query="fork()", limit=8)

        assert sonuc, "fork() aranabilir olmalı"
        assert "fork()" in sonuc[0].text

    async def test_o_notasyonu_aranabilir(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
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
            sonuc = await fts_search(session, course_id=ders, query='"O(n log n)"', limit=8)

        assert sonuc, "O(n log n) aranabilir olmalı"
        assert "O(n log n)" in sonuc[0].text

    async def test_turkce_aksan_farki_eslesmeyi_bozmaz(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """İndeks ve sorgu AYNI unaccent'ten geçer; 'kosul' yazan öğrenci 'koşul' bulur."""
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
            aksanli = await fts_search(session, course_id=ders, query='"döngüsel bekleme"', limit=8)
            aksansiz = await fts_search(
                session, course_id=ders, query='"dongusel bekleme"', limit=8
            )

        assert aksanli, "aksanlı sorgu eşleşmeli"
        assert [c.chunk_id for c in aksanli] == [c.chunk_id for c in aksansiz]


# ---------------------------------------------------------------------------
# 5. Boş ve bozuk girdi — patlamamak da bir davranıştır
# ---------------------------------------------------------------------------


class TestBosVeBozukGirdi:
    async def test_materyalsiz_derste_arama_bos_doner(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ders = await create_course(client, users.auth(ayse_id), "COME301")

        async with rls_session(ayse_id) as session:
            sonuc = await HybridRetriever(session).search(
                course_id=ders, query="deadlock nedir", limit=8
            )
            kapili = await retrieve(session, course_id=ders, query="deadlock nedir")

        assert sonuc == []
        assert kapili.chunks == []
        assert kapili.abstained is True
        assert kapili.candidate_count == 0

    @pytest.mark.parametrize("sorgu", ["", "   ", "\n\t "])
    async def test_bos_sorgu_patlamaz(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine, sorgu: str
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="a.md",
            passages=DEADLOCK_TR,
        )

        async with rls_session(ayse_id) as session:
            assert await HybridRetriever(session).search(course_id=ders, query=sorgu) == []

    @pytest.mark.parametrize("sorgu", ["!!! ???", "& | !", "<>", "'''", '"""'])
    async def test_noktalama_yigini_sorgu_patlamaz(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine, sorgu: str
    ) -> None:
        """Kullanıcı girdisi tsquery'ye ham girmez; bozuk girdi hata değil boş sonuç verir."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="a.md",
            passages=DEADLOCK_TR,
        )

        async with rls_session(ayse_id) as session:
            assert await fts_search(session, course_id=ders, query=sorgu, limit=8) == []
            # Dense şerit metinden bağımsız çalışır; sorgu anlamsız olsa da patlamamalı.
            assert await dense_search(session, course_id=ders, query=sorgu, limit=8) != []


# ---------------------------------------------------------------------------
# 6. Kanıt kapısı
# ---------------------------------------------------------------------------


class TestKanitKapisi:
    async def test_esik_asilinca_parcalar_doner(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="a.md",
            passages=DEADLOCK_TR,
        )
        ayarlar = get_settings().model_copy(update={"evidence_threshold": 0.01})

        async with rls_session(ayse_id) as session:
            sonuc = await retrieve(
                session, course_id=ders, query="deadlock dört koşul", settings=ayarlar
            )

        assert sonuc.abstained is False
        assert sonuc.chunks
        assert sonuc.best_dense_score >= 0.01

    async def test_esik_asilamayinca_parcalar_bilerek_geri_verilmez(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Fail-closed: çağıran bayrağı gözden kaçırsa bile elinde zayıf parça olmaz."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="a.md",
            passages=DEADLOCK_TR,
        )
        ayarlar = get_settings().model_copy(update={"evidence_threshold": 0.99})

        async with rls_session(ayse_id) as session:
            sonuc = await retrieve(
                session, course_id=ders, query="deadlock dört koşul", settings=ayarlar
            )

        assert sonuc.abstained is True
        assert sonuc.chunks == []
        # Aday vardı ama kanıt zayıftı: bu ayrım cevap katmanının
        # insufficient_context / out_of_scope kararını besler.
        assert sonuc.candidate_count > 0
        assert sonuc.best_dense_score < sonuc.threshold

    async def test_konu_disi_sorgu_ilgili_sorgudan_dusuk_skor_alir(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Kapının dayandığı sinyal gerçekten ayırt ediyor mu — eşikten bağımsız kontrol.

        Mutlak eşik kalibre edilmemiştir (T043); ölçülebilir olan SIRALAMA ilişkisidir:
        konu dışı bir sorgunun en iyi kanıtı, konuyla ilgili sorgununkinden düşük olmalı.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="a.md",
            passages=DEADLOCK_TR,
        )
        ayarlar = get_settings().model_copy(update={"evidence_threshold": 0.0})

        async with rls_session(ayse_id) as session:
            ilgili = await retrieve(
                session,
                course_id=ders,
                query="deadlock dört koşul karşılıklı dışlama döngüsel bekleme",
                settings=ayarlar,
            )
            konu_disi = await retrieve(
                session, course_id=ders, query="makarna nasıl pişirilir", settings=ayarlar
            )

        assert ilgili.best_dense_score > konu_disi.best_dense_score


# ---------------------------------------------------------------------------
# 6b. Kapsam sinyali — reddin SEBEBİ (R4 / Kusur 1-2)
#
# Kapının kararı değişmiyor; değişen, kapı kapandığında ne denildiği. Bu yüzden
# testlerin çoğu `assess_evidence`'a doğrudan bakar: sınanan şey sınıflandırma,
# retrieval kalitesi değil.
# ---------------------------------------------------------------------------


def metinli_chunk(text: str, *, dense: float = 0.0, fts: float = 0.0) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        document_id=uuid4(),
        file_name="ders.pdf",
        page_number=1,
        slide_number=None,
        section_title=None,
        text=text,
        dense_score=dense,
        fts_score=fts,
    )


DEADLOCK_PASAJI = (
    "Deadlock oluşması için dört koşulun aynı anda sağlanması gerekir: karşılıklı "
    "dışlama, tut ve bekle, kesintiye uğratılamama, döngüsel bekleme."
)


class TestSozlukselKapsama:
    """`lexical_coverage` — ölçekten bağımsız, Türkçe güvenli örtüşme."""

    def test_sorgu_sozcukleri_parcada_geciyorsa_kapsama_yuksek(self) -> None:
        kapsama = lexical_coverage(
            "deadlock için dört koşul nedir", [metinli_chunk(DEADLOCK_PASAJI)]
        )
        # "deadlock", "dort", "kosul" geçiyor; "icin"/"nedir" geçmiyor.
        assert kapsama == pytest.approx(3 / 5)

    def test_alakasiz_sorguda_kapsama_dusuk(self) -> None:
        kapsama = lexical_coverage(
            "Kubernetes yatay pod ölçekleme", [metinli_chunk(DEADLOCK_PASAJI)]
        )
        assert kapsama == 0.0

    def test_turkce_buyuk_harf_ve_aksan_eslesmeyi_bozmaz(self) -> None:
        """i/İ ve ı/I tuzağı: `lower()` tek başına bu testi geçemez."""
        assert lexical_coverage(
            "İŞLETİM SİSTEMİ", [metinli_chunk("işletim sistemi çekirdeği")]
        ) == pytest.approx(1.0)
        assert lexical_coverage(
            "cozum kosulu", [metinli_chunk("çözüm koşulu aranır")]
        ) == pytest.approx(1.0)

    def test_kapsama_en_iyi_TEK_parcadan_okunur(self) -> None:
        """Parçaların BİRLEŞİMİ ölçüldü ve ayırmıyor — gerekçe scope.py'de.

        Sorgunun sözcükleri sekiz ayrı parçaya dağılmışsa bu bir kanıt değildir;
        ayırt edici olan, birlikte TEK bir pasajda bulunmalarıdır.
        """
        dagilmis = [metinli_chunk("deadlock tanımı"), metinli_chunk("dört koşul listesi")]
        birarada = [metinli_chunk("deadlock dört koşul birlikte anlatılır")]
        assert lexical_coverage("deadlock dört koşul", dagilmis) == pytest.approx(2 / 3)
        assert lexical_coverage("deadlock dört koşul", birarada) == pytest.approx(1.0)

    def test_iki_harfli_sozcukler_sayilmaz(self) -> None:
        """Her metinde bulunan parçacıklar kapsamayı sabit bir tabana oturtur."""
        assert lexical_coverage("bu ve şu", [metinli_chunk("bu ve şu her yerde")]) == 0.0

    def test_bos_sorgu_sifir_kapsama(self) -> None:
        assert lexical_coverage("", [metinli_chunk(DEADLOCK_PASAJI)]) == 0.0
        assert lexical_coverage("deadlock", []) == 0.0


class TestKanitSeviyesi:
    """`assess_evidence` — üç seviyenin sınırları."""

    def test_esik_asilinca_seviye_yeterli(self) -> None:
        karar = assess_evidence(
            [metinli_chunk(DEADLOCK_PASAJI, dense=0.85, fts=0.05)],
            query="deadlock dört koşul",
            threshold=0.81,
        )
        assert karar.level is EvidenceLevel.SUFFICIENT
        assert karar.abstained is False

    def test_esik_altinda_ama_konu_derste_ise_zayif(self) -> None:
        """Kapsam içi soru, dayanağı zayıf olduğunda 'kapsam dışı' DENMEZ."""
        karar = assess_evidence(
            [metinli_chunk(DEADLOCK_PASAJI, dense=0.70, fts=0.05)],
            query="deadlock dört koşul",
            threshold=0.81,
        )
        assert karar.level is EvidenceLevel.WEAK
        assert karar.abstained is True

    def test_esik_altinda_ve_sozcuksel_iz_yoksa_kapsam_disi(self) -> None:
        karar = assess_evidence(
            [metinli_chunk(DEADLOCK_PASAJI, dense=0.79, fts=0.004)],
            query="Kubernetes yatay pod ölçekleme",
            threshold=0.81,
        )
        assert karar.level is EvidenceLevel.OUT_OF_SCOPE

    def test_iki_sinyal_ayrisirsa_zayifa_dusulur(self) -> None:
        """Fail-closed yönü: 'kapsam dışı' demek 'kaynak bulamadım'dan daha iddialı.

        Sözlüksel kapsama sıfır ama FTS tavanı aşılmış — bir sinyal 'kapsam dışı'
        diyor, diğeri demiyor. Bu durumda öğrenciye dersi hakkında yanlış bir şey
        söylemek yerine soruyu yeniden sorması istenir.
        """
        karar = assess_evidence(
            [metinli_chunk(DEADLOCK_PASAJI, dense=0.60, fts=0.9)],
            query="Kubernetes yatay pod ölçekleme",
            threshold=0.81,
        )
        assert karar.level is EvidenceLevel.WEAK

    def test_hic_parca_yoksa_kapsam_disi_denmez(self) -> None:
        """Materyalsiz ders sistemin eksiğidir, öğrencinin sorusunun değil."""
        karar = assess_evidence([], query="deadlock nedir", threshold=0.81)
        assert karar.level is EvidenceLevel.WEAK
        assert karar.best_dense_score == 0.0

    def test_karar_gerekcesini_tasir(self) -> None:
        karar = assess_evidence(
            [metinli_chunk(DEADLOCK_PASAJI, dense=0.79, fts=0.004)],
            query="Kubernetes ölçekleme",
            threshold=0.81,
        )
        assert karar.best_dense_score == pytest.approx(0.79)
        assert karar.best_fts_score == pytest.approx(0.004)
        assert karar.lexical_coverage == 0.0
        assert karar.threshold == pytest.approx(0.81)

    def test_esikler_kalibrasyonda_olculen_ayrisma_araliginda(self) -> None:
        """Dondurulmuş sayıların regresyon koruması.

        Kalibrasyon setinde (n=15, `scope.py` docstring'i) ölçülen ayrışma:
        FTS  → kapsam dışı max 0.0171, cevaplanabilir min 0.0289
        kaps → kapsam dışı max 0.2000, cevaplanabilir min 0.3333

        Bir eşik bu aralığın DIŞINA çıkarsa kalibrasyon geçersizdir; bu test o
        değişikliği sessiz bırakmaz.
        """
        assert 0.0171 < FTS_CEILING < 0.0289
        assert 0.2000 < COVERAGE_CEILING < 0.3333

    def test_kapsam_esikleri_disaridan_verilebilir(self) -> None:
        """R2'nin daha büyük bir kalibrasyon setinde tarama yapabilmesi için."""
        parcalar = [metinli_chunk(DEADLOCK_PASAJI, dense=0.70, fts=0.05)]
        gevsek = assess_evidence(
            parcalar,
            query="Kubernetes ölçekleme",
            threshold=0.81,
            fts_ceiling=0.10,
            coverage_ceiling=0.50,
        )
        assert gevsek.level is EvidenceLevel.OUT_OF_SCOPE


class TestKapsamSeviyesiGercekHatta:
    async def test_konu_disi_sorgu_kapsam_disi_isaretlenir(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Uçtan uca değil ama gerçek indeks üzerinde: kapı + sınıflandırma birlikte."""
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="a.md",
            passages=DEADLOCK_TR,
        )
        # Eşik 1.0: hiçbir sorgu kapıyı geçemez, yani her ikisi de abstain eder ve
        # ayrımı yapan tek şey kapsam sinyali olur.
        ayarlar = get_settings().model_copy(update={"evidence_threshold": 1.0})

        async with rls_session(ayse_id) as session:
            konu_disi = await retrieve(
                session,
                course_id=ders,
                query="Kubernetes yatay pod ölçekleme yapılandırması",
                settings=ayarlar,
            )
            ilgili = await retrieve(
                session, course_id=ders, query="deadlock dört koşul", settings=ayarlar
            )

        assert konu_disi.abstained and ilgili.abstained
        assert konu_disi.level is EvidenceLevel.OUT_OF_SCOPE
        assert ilgili.level is EvidenceLevel.WEAK
        assert ilgili.lexical_coverage > konu_disi.lexical_coverage


# ---------------------------------------------------------------------------
# 7. Sözleşme uyumu — diğer şeritler bu imzaya karşı yazıyor
# ---------------------------------------------------------------------------


class TestProtokolUyumu:
    def test_hybrid_retriever_retriever_protokolunu_karsilar(self) -> None:
        """Şerit 3 ve 4 sahte uygulamalarını bırakıp buna geçecek; imza sapamaz."""
        imza = inspect.signature(HybridRetriever.search)
        parametreler = imza.parameters

        assert list(parametreler) == ["self", "course_id", "query", "limit"]
        for ad in ("course_id", "query", "limit"):
            assert parametreler[ad].kind is inspect.Parameter.KEYWORD_ONLY
        assert parametreler["limit"].default == 8

        protokol = inspect.signature(Retriever.search)
        assert list(protokol.parameters) == list(parametreler)

    async def test_donen_parcalar_atif_icin_gereken_metadatayi_tasir(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Anayasa I: dosya adı ve konum model metninden değil buradan üretilir."""
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
            sonuc = await HybridRetriever(session).search(
                course_id=ders, query="Coffman koşulları", limit=8
            )

        assert sonuc
        for parca in sonuc:
            assert parca.file_name == "05-deadlock.md"
            assert parca.page_number is not None
            assert parca.location.startswith("Sayfa ")
            assert parca.text


# ---------------------------------------------------------------------------
# 8. Embedding uzayı kökeni — 0006, fail-closed uyuşmazlık
#
# Korunan hata sınıfı SESSİZDİR: iki farklı uzaydan gelen vektörlerin kosinüsü
# de bir sayı üretir, sıralama da üretilir; yalnızca anlamsızdır. Bu yüzden
# testler "hata veriyor mu"ya değil, "durduruyor mu"ya bakar.
# ---------------------------------------------------------------------------


class TestVektorUzayiKimligi:
    def test_kanonik_bicim_uc_bileseni_de_tasir(self) -> None:
        from app.core.vector_space import current_space

        kimlik = current_space()
        saglayici, _, kalan = kimlik.partition("/")
        model, _, surum = kalan.rpartition("@")

        assert saglayici, "sağlayıcı türü yok"
        assert model, "model adı yok"
        assert surum, "sürüm yok"

    def test_farkli_saglayicilar_farkli_uzaylardir(self) -> None:
        from app.core.vector_space import space_of
        from app.modules.ingestion.embedding import FastEmbedProvider, HashingEmbeddingProvider

        assert space_of(HashingEmbeddingProvider()) != space_of(FastEmbedProvider())

    def test_ayni_saglayici_farkli_model_farkli_uzaydir(self) -> None:
        """Boyut eşitliği yeterli bir kontrol DEĞİL: iki model de vector(1024)'e sığar."""
        from app.core.vector_space import space_of
        from app.modules.ingestion.embedding import FastEmbedProvider

        assert space_of(FastEmbedProvider("intfloat/multilingual-e5-large")) != space_of(
            FastEmbedProvider("BAAI/bge-m3")
        )

    def test_taninmayan_saglayici_kendi_uzayini_alir(self) -> None:
        """Uydurma bir kimlik değil, eşleşmeyen bir kimlik: fail-closed."""
        from app.core.vector_space import space_of

        class Yabanci:
            name = "kimse"

        kimlik = space_of(Yabanci())
        assert "Yabanci" in kimlik
        assert kimlik != space_of(get_embedding_provider())


class TestUzayUyusmazligi:
    async def _ders_kur(
        self,
        client: AsyncClient,
        users: UserFactory,
        worker_engine: AsyncEngine,
        *,
        embedding_space: str | None,
    ) -> tuple[UUID, UUID]:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        ders = await create_course(client, ayse, "COME301")
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="a.md",
            passages=DEADLOCK_TR,
            embedding_space=embedding_space,
        )
        return ders, ayse_id

    async def test_ayni_uzaydaki_korpus_normal_aranir(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Pozitif kontrol: kapı meşru aramayı kapatmıyor."""
        from app.core.vector_space import current_space

        ders, ayse_id = await self._ders_kur(
            client, users, worker_engine, embedding_space=current_space()
        )

        async with rls_session(ayse_id) as session:
            sonuc = await HybridRetriever(session).search(course_id=ders, query="deadlock nedir")

        assert sonuc

    async def test_baska_uzaydaki_korpus_aramayi_durdurur(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Asıl iddia: uyuşmazlıkta sonuç DÖNMEZ, hata döner.

        Sessizce devam etmek, alakasız parçalara dayanan "kaynaklı" bir cevap
        üretmek demektir — kullanıcının yanlışlığını anlayamayacağı tek hata türü.
        """
        from app.modules.retrieval.dense import EmbeddingSpaceMismatchError

        ders, ayse_id = await self._ders_kur(
            client,
            users,
            worker_engine,
            embedding_space="fastembed/baska/model@0.0.1",
        )

        async with rls_session(ayse_id) as session:
            with pytest.raises(EmbeddingSpaceMismatchError) as hata:
                await HybridRetriever(session).search(course_id=ders, query="deadlock nedir")

        assert hata.value.status_code == 503
        assert hata.value.found == ["fastembed/baska/model@0.0.1"]

    async def test_damgasiz_korpus_aramayi_durdurmaz(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """0006 öncesi satırların hâli. Bilinçli sınır — göç kimseyi durdurmaz.

        Bu testin yeşil olması korumanın çalıştığını DEĞİL, kapsamının bilindiğini
        gösterir: damga yazılmaya başlanana kadar korunan satır yoktur.
        """
        ders, ayse_id = await self._ders_kur(client, users, worker_engine, embedding_space=None)

        async with rls_session(ayse_id) as session:
            sonuc = await HybridRetriever(session).search(course_id=ders, query="deadlock nedir")

        assert sonuc

    async def test_karisik_uzay_da_durdurur(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Kısmi yeniden embed etme: bir belge yenilenmiş, diğeri eski uzayda kalmış.

        Bu, tek bir sağlayıcı değişikliğinden daha sinsi: ders çalışıyor görünür,
        yalnız bazı belgeler hiç bulunmaz.
        """
        from app.core.vector_space import current_space
        from app.modules.retrieval.dense import EmbeddingSpaceMismatchError

        ders, ayse_id = await self._ders_kur(
            client, users, worker_engine, embedding_space=current_space()
        )
        await seed_document(
            worker_engine,
            course_id=ders,
            uploaded_by=ayse_id,
            file_name="eski.md",
            passages=PROCESSES_EN,
            embedding_space="hashing/hashing-v1@builtin-0",
        )

        async with rls_session(ayse_id) as session:
            with pytest.raises(EmbeddingSpaceMismatchError):
                await HybridRetriever(session).search(
                    course_id=ders, query="fork context switch", limit=24
                )

    async def test_uyusmazlik_fts_seridini_etkilemez(
        self, client: AsyncClient, users: UserFactory, worker_engine: AsyncEngine
    ) -> None:
        """Denetim yalnız dense şeridinde: `ts_rank` embedding sağlayıcısını bilmez.

        FTS'i de durdurmak, uyuşmazlığın etkilemediği bir yeteneği kapatmak olurdu.
        """
        ders, ayse_id = await self._ders_kur(
            client, users, worker_engine, embedding_space="fastembed/baska/model@0.0.1"
        )

        async with rls_session(ayse_id) as session:
            sonuc = await fts_search(session, course_id=ders, query="deadlock", limit=8)

        assert sonuc
