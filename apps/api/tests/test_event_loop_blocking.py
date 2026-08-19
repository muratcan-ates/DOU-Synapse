"""Event loop'un bloke olmadığının ÖLÇÜMLÜ kanıtı (FR-220, SC-014).

Ölçülen şey toplam süre DEĞİL. `asyncio.to_thread` sarması bir belgenin işlenme
süresini kısaltmaz; değiştirdiği tek şey, o süre boyunca event loop'un başka bir
isteği yürütebilmesidir. Bu yüzden buradaki iddia "hızlı" değil, **"cevap
verebilir"**: yavaş iş sürerken gelen sağlık yoklaması kesintisiz yanıtlanmalı.

Testin kendi körlüğü de aynı dosyada sınanıyor. Yanlış yazılmış bir gecikme
ölçeri her koşuda sıfır döndürür ve sarma kaldırıldığında bile yeşil kalır;
`test_prob_kor_degil_*` aynı prob'u sarma OLMADAN koşturup gecikmeyi gerçekten
gördüğünü kanıtlar. Aynı yöntem depoda kurulu: `flows.spec.ts`'in sayaç
kalibrasyonu ve CI'ın RLS politikasını bilerek bozan adımı.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

import pytest
from httpx import AsyncClient

from app.core.db import rls_session
from app.modules.ingestion.embedding import HashingEmbeddingProvider, set_embedding_provider
from app.modules.retrieval.dense import dense_search
from tests.conftest import UserFactory
from tests.factories import SlowSyncEmbeddingProvider, make_pdf

#: Sarma yerindeyken loop'ta görülmesi gereken üst sınır. Yavaş iş 0,4 sn
#: sürüyor; sarma çalışıyorsa loop bu sürenin neredeyse tamamında serbesttir.
MAX_ACCEPTABLE_LAG_SECONDS = 0.1

#: Kalibrasyonda (sarma yokken) görülmesi gereken ALT sınır. 0,4 sn'lik bir
#: bloke için 0,3 sn eşiği, yavaş bir makinede bile yanlış yeşil vermez.
MIN_BLOCKING_LAG_SECONDS = 0.3


class LoopProbe:
    """Event loop gecikmesini ölçer.

    `asyncio.sleep(interval)` isteyip gerçekte ne kadar beklediğini ölçer;
    aradaki fark, loop'un o sırada başka bir işle meşgul olduğu süredir.
    """

    def __init__(self, interval: float = 0.01) -> None:
        self._interval = interval
        self._running = True
        self.max_lag = 0.0
        self.ticks = 0
        #: İlk tur tamamlandığında kurulur: prob artık ölçüyor.
        self.ready = asyncio.Event()

    async def run(self) -> None:
        while self._running:
            started = time.perf_counter()
            await asyncio.sleep(self._interval)
            self.ticks += 1
            self.max_lag = max(self.max_lag, time.perf_counter() - started - self._interval)
            # `set()` bekleyeni hemen çalıştırmaz, yalnız sıraya alır; bu
            # coroutine bir sonraki `sleep`'e girdikten SONRA bekleyen devam
            # eder. Yani bekleyen koda dönüldüğünde ölçüm penceresi zaten açık.
            self.ready.set()

    def stop(self) -> None:
        self._running = False


async def measure_max_lag(work: Callable[[], Awaitable[object]]) -> float:
    """`work` koşarken görülen en büyük event loop gecikmesi."""
    probe = LoopProbe()
    task = asyncio.create_task(probe.run())
    # Prob'un ilk `sleep`'ine girdiğinden emin ol: bloke eden iş prob henüz
    # başlamadan biterse ölçüm sıfır çıkar ve test hiçbir şey kanıtlamaz.
    await probe.ready.wait()
    try:
        await work()
    finally:
        probe.stop()
        await task
    return probe.max_lag


@pytest.fixture
def slow_provider() -> Iterator[SlowSyncEmbeddingProvider]:
    provider = SlowSyncEmbeddingProvider()
    set_embedding_provider(provider)
    yield provider
    set_embedding_provider(None)


@pytest.fixture
async def ders(
    client: AsyncClient, users: UserFactory
) -> AsyncIterator[tuple[str, dict[str, str]]]:
    ayse_id = await users.create("ayse@dogus.edu.tr")
    headers = users.auth(ayse_id)
    response = await client.post(
        "/courses", json={"code": "COME301", "title": "COME301 Dersi"}, headers=headers
    )
    assert response.status_code == 201, response.text
    yield response.json()["id"], headers


class TestIngestionLoopUnaffected:
    async def test_belge_islenirken_saglik_yoklamasi_kesintisiz_yanit_verir(
        self,
        client: AsyncClient,
        ders: tuple[str, dict[str, str]],
        slow_provider: SlowSyncEmbeddingProvider,
    ) -> None:
        """SC-014'ün birebir iddiası, gerçek HTTP yüzeyinden ölçülür.

        Yükleme ucu yanıtı yazdıktan sonra `_trigger_worker`'ı arka plan görevi
        olarak koşturuyor ve `WORKER_DRAIN_URL` tanımsız olduğu için drain AYNI
        süreçte yapılıyor — yani ayrıştırma ve embedding bu istek sırasında,
        API'nin event loop'unda koşuyor. Ölçüm tam da o pencerede yapılıyor.
        """
        course_id, headers = ders
        pdf = make_pdf(
            [
                "Deadlock icin dort Coffman kosulu birlikte saglanmalidir.",
                "Round Robin algoritmasinda quantum sureyi belirler.",
            ]
        )

        gecikmeler: list[float] = []
        bitti = asyncio.Event()
        yoklama_basladi = asyncio.Event()

        async def saglik_yokla() -> None:
            """Yoklamalar ARALIKSIZ atılır.

            Aralarına `sleep` konsaydı bloke süresi tam o boşluğa düşebilir ve
            ölçülmeden geçerdi — ilk yazımda birebir bu oldu: sarma kaldırıldığı
            hâlde test yeşil kaldı. Ölçüm penceresinin boşluksuz olması, bu
            testin bir şey kanıtlamasının ön koşulu.
            """
            while not bitti.is_set():
                basladi = time.perf_counter()
                saglik = await client.get("/health/live")
                gecikmeler.append(time.perf_counter() - basladi)
                assert saglik.status_code == 200
                yoklama_basladi.set()

        yoklama = asyncio.create_task(saglik_yokla())
        await yoklama_basladi.wait()

        response = await client.post(
            f"/courses/{course_id}/documents",
            files={"file": ("hafta3.pdf", pdf, "application/octet-stream")},
            headers=headers,
        )
        bitti.set()
        await yoklama

        assert response.status_code == 202, response.text

        # Ölçümün boş çıkmadığının kanıtı: yavaş sağlayıcı gerçekten koştu.
        # Bu iddia olmadan, işi hiç yapmayan bir yol da testi yeşil yakardı.
        assert slow_provider.calls >= 1
        assert gecikmeler
        assert max(gecikmeler) < MAX_ACCEPTABLE_LAG_SECONDS, (
            f"sağlık yoklaması {max(gecikmeler):.3f} sn bekledi — "
            f"belge işlenirken event loop bloke oluyor"
        )

    async def test_prob_kor_degil_senkron_cagri_loopu_gercekten_durdurur(
        self, slow_provider: SlowSyncEmbeddingProvider
    ) -> None:
        """Kalibrasyon: aynı prob, sarma OLMADAN gecikmeyi görüyor mu?

        Bu test ürün kodunu değil ÖLÇÜM ARACINI sınar. Geçen bir testin tek
        başına bir şey söylememesinin sebebi budur: yanlış yazılmış bir gecikme
        ölçeri her koşuda sıfır döndürür ve `to_thread` kaldırıldığında bile
        yeşil kalırdı.
        """

        async def dogrudan_loop_uzerinde() -> None:
            slow_provider.embed_documents(["ölçüm"])

        gecikme = await measure_max_lag(dogrudan_loop_uzerinde)

        assert gecikme > MIN_BLOCKING_LAG_SECONDS, (
            f"prob yalnız {gecikme:.3f} sn gecikme gördü — ölçüm körleşmiş, "
            f"diğer testlerin yeşili bir şey kanıtlamıyor"
        )


class TestQueryPathLoopUnaffected:
    async def test_sorgu_embeddingi_loopu_bloke_etmez(
        self,
        client: AsyncClient,
        users: UserFactory,
        slow_provider: SlowSyncEmbeddingProvider,
    ) -> None:
        """Üç sarmanın en kritiği: sorgu yolu her sohbet isteğinde koşuyor.

        Ingestion ayrı bir worker sürecine taşınsa bile `dense.py` API
        sürecinde kalır; bu yüzden ayrı ve doğrudan ölçülüyor.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        response = await client.post(
            "/courses",
            json={"code": "COME302", "title": "COME302 Dersi"},
            headers=users.auth(ayse_id),
        )
        course_id = response.json()["id"]

        async def ara() -> None:
            async with rls_session(ayse_id) as session:
                await dense_search(session, course_id=course_id, query="deadlock nedir", limit=8)

        # Ölçümden ÖNCE hızlı sağlayıcıyla bir ısıtma turu. İlk `dense_search`
        # bağlantı havuzunu kurar ve sorguyu ilk kez hazırlar; bu maliyet
        # sarmayla ilgisizdir ama ölçüme karışıp yüz milisaniyelik bir tepe
        # üretebiliyor (ilk yazımda 0,224 sn ölçüldü). Gürültüyü eşiği
        # gevşeterek değil kaynağında temizlemek gerekiyor: gevşemiş bir eşik
        # gerçek blokeyi de kaçırırdı.
        set_embedding_provider(HashingEmbeddingProvider())
        await ara()
        set_embedding_provider(slow_provider)

        gecikme = await measure_max_lag(ara)

        assert slow_provider.calls == 1
        assert gecikme < MAX_ACCEPTABLE_LAG_SECONDS, (
            f"sorgu embedding'i {gecikme:.3f} sn boyunca loop'u tuttu"
        )
