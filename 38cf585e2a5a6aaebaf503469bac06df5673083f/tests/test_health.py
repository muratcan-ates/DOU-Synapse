"""Sağlık uçları ve embedding ısıtması (FR-221, T203).

Asıl iddia tek cümle: **ısıtma başlangıcı bloklamaz.** Bunun ölçülmesi gerekiyor
çünkü "arka planda başlattım" demek yetmez — `create_task` yerine `await`
yazılsaydı kod yine derlenir, testler yine geçer ve arıza yalnız üretimde,
konteyner yeniden başlatma döngüsüne girdiğinde görünürdü.

Ölçüm sahte bir YAVAŞ sağlayıcıyla yapılıyor: gerçek model bu pakette hiçbir
koşulda yüklenmez ve bu da ayrıca sınanıyor.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterator, Sequence

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.warmup import (
    reset_warmup_state,
    start_warmup,
    warm_embedding,
    warmup_state,
)
from app.modules.ingestion.embedding import HashingEmbeddingProvider, set_embedding_provider
from tests.test_event_loop_blocking import SLOW_CALL_SECONDS, SlowSyncEmbeddingProvider

#: Isıtma bloklamıyorsa `lifespan`'e girmenin alması gereken süre. Sahte
#: sağlayıcı 0,4 sn harcıyor; `await` edilseydi startup en az o kadar sürerdi.
MAX_STARTUP_SECONDS = 0.1


class BozukEmbeddingProvider(HashingEmbeddingProvider):
    """Isıtma sırasında patlayan sağlayıcı (eksik model dizini vekili)."""

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("model dizini bulunamadı")

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        raise RuntimeError("model dizini bulunamadı")


@pytest.fixture(autouse=True)
def temiz_isitma_durumu() -> Iterator[None]:
    reset_warmup_state()
    yield
    reset_warmup_state()
    set_embedding_provider(None)


def _bayrak(monkeypatch: pytest.MonkeyPatch, deger: str) -> Iterator[None]:
    """Isıtma bayrağını yalnız bir test boyunca değiştirir.

    Bayrak `conftest.py`'de paket genelinde AYARLANMIYOR ve ayarlanmamalı:
    `tests/test_error_envelope.py::TestAyarAdlari` liderin sabitlediği
    varsayılanı `Settings(_env_file=None)` ile denetliyor ve pydantic-settings
    `_env_file=None` verilse de `os.environ`'u okumaya devam ediyor — paket
    genelinde bir ortam değişkeni koymak o sözleşme testini kırardı.

    Gerçek modelin yüklenmemesini sağlayan şey zaten bayrak değil
    `EMBEDDING_PROVIDER=hashing`; bkz. `test_pakette_gercek_model_*`.
    """
    monkeypatch.setenv("EMBEDDING_WARMUP_ENABLED", deger)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def isitma_acik(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    yield from _bayrak(monkeypatch, "true")


@pytest.fixture
def isitma_kapali(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    yield from _bayrak(monkeypatch, "false")


class TestWarmup:
    async def test_isitma_baslangici_bloklamaz(self, isitma_acik: None) -> None:
        """T203'ün tek cümlelik iddiası, ölçülerek.

        `lifespan`'e girmek 0,4 sn'lik ısıtmayı BEKLEMEMELİ. Ölçüm sahte
        sağlayıcıyla yapılıyor; gerçek modelde bu süre saniyeler mertebesinde.
        """
        # İçeride ithal ediliyor: `app.main` modül düzeyinde `create_app()`
        # çağırıyor, yani ithal anında `Settings` kuruluyor. Dosyanın başında
        # ithal edilseydi ortam fixture'ı henüz koşmadan doğrulama patlardı
        # (conftest'in `client` fixture'ı da aynı sebeple içeride ithal ediyor).
        from app.main import create_app, lifespan

        set_embedding_provider(SlowSyncEmbeddingProvider())

        basladi = time.perf_counter()
        async with lifespan(create_app()):
            startup = time.perf_counter() - basladi
            # Görev başlamış ama bitmemiş olmalı.
            assert warmup_state() == "warming"
            assert startup < MAX_STARTUP_SECONDS, (
                f"başlangıç {startup:.3f} sn sürdü — ısıtma `await` ediliyor"
            )
            assert startup < SLOW_CALL_SECONDS

    async def test_isitma_bitince_durum_ok_olur(self) -> None:
        set_embedding_provider(HashingEmbeddingProvider())
        await warm_embedding()
        assert warmup_state() == "ok"

    async def test_isitma_patlarsa_surec_olmez_durum_failed_olur(self) -> None:
        """Isıtma bir kolaylık katmanı; patlaması sürecin ölmesi için sebep değil."""
        set_embedding_provider(BozukEmbeddingProvider())
        await warm_embedding()
        assert warmup_state() == "failed"

    async def test_kapaliyken_gorev_hic_baslamaz(self, isitma_kapali: None) -> None:
        """Operatör kapattığında sağlayıcıya hiç dokunulmaz."""
        provider = SlowSyncEmbeddingProvider()
        set_embedding_provider(provider)

        assert start_warmup() is None
        assert warmup_state() == "disabled"
        assert provider.calls == 0

    async def test_pakette_gercek_model_hicbir_kosulda_yuklenmez(self, client: AsyncClient) -> None:
        """Regresyon kapısı, temenni değil. İki ayrı güvence sınanıyor.

        (1) Sağlayıcı `hashing`: bayrak açık kalsa bile 2,1 GB'lık ONNX modeli
        yüklenmez. Isıtmanın gerçek maliyeti sağlayıcıya bağlı, bayrağa değil.

        (2) Test taşıyıcısı `lifespan` koşturmuyor: bir istek atıldıktan sonra
        bile ısıtma durumu `disabled` kalıyor. Bu bir tesadüf değil, httpx'in
        `ASGITransport`'unun sözleşmesi — ama gün gelip taşıyıcı değişirse
        (ör. `LifespanManager`) paket sessizce her koşuda model yüklemeye
        başlardı; bu iddia o günü kırmızıya çevirir.
        """
        assert get_settings().embedding_provider == "hashing"

        assert (await client.get("/health/live")).status_code == 200
        assert warmup_state() == "disabled"


class TestReadiness:
    async def test_isitma_kapaliyken_hazirlik_dusmez(self, client: AsyncClient) -> None:
        """`disabled` bir arıza değil: model ilk istekte tembel yüklenir."""
        response = await client.get("/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["checks"]["embedding"] == "disabled"

    async def test_isinirken_hazirlik_dusuk_kalir(
        self, client: AsyncClient, isitma_acik: None
    ) -> None:
        """Orkestratör ısınma bitmeden trafiği buraya yöneltmemeli."""
        set_embedding_provider(SlowSyncEmbeddingProvider())
        task = start_warmup()
        assert task is not None
        try:
            response = await client.get("/health/ready")

            assert response.status_code == 503
            body = response.json()
            assert body["status"] == "degraded"
            assert body["checks"]["embedding"] == "warming"
            # Veritabanı sağlamken bile düşüyor: düşüren şey ısınma.
            assert body["checks"]["database"] == "ok"
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_isitma_bittiginde_hazirlik_yukselir(self, client: AsyncClient) -> None:
        set_embedding_provider(HashingEmbeddingProvider())
        await warm_embedding()

        response = await client.get("/health/ready")

        assert response.status_code == 200
        assert response.json()["checks"]["embedding"] == "ok"

    async def test_isitma_basarisizsa_hazirlik_dusuk_kalir(self, client: AsyncClient) -> None:
        """Fail-closed (Anayasa IV): bozuk retrieval'ı sessizce servis etmektense çekil."""
        set_embedding_provider(BozukEmbeddingProvider())
        await warm_embedding()

        response = await client.get("/health/ready")

        assert response.status_code == 503
        assert response.json()["checks"]["embedding"] == "failed"

    async def test_live_isinirken_de_200_doner(
        self, client: AsyncClient, isitma_acik: None
    ) -> None:
        """`/live` bağımlılıksızdır; ısınan bir süreç ölü sayılmamalı."""
        set_embedding_provider(SlowSyncEmbeddingProvider())
        task = start_warmup()
        assert task is not None
        try:
            response = await client.get("/health/live")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
