"""Kota, eşzamanlılık kapısı ve sayaç tahliyesi (FR-222, FR-223, T206).

Üç iddia var ve üçü de anahtarsız doğrulanabilir — kapılar LLM'e gitmeden önce
kapanıyor, dolayısıyla gerçek sağlayıcıya hiç ihtiyaç yok:

1. Kota dolduğunda uç 429 döner ve **ne zaman tekrar denenebileceğini söyler.**
2. Aynı kullanıcının ikinci eşzamanlı üretimi, LLM ÇAĞRILMADAN reddedilir.
   "Çağrılmadan" kelimesi burada ölçülüyor: sahte sağlayıcının çağrı sayacı
   reddedilen istekte artmamalı. Kapı üretim başladıktan sonra kapansaydı
   maliyet zaten ödenmiş olurdu ve test yine yeşil yanardı.
3. Sayaç kullanılmayan anahtarları tahliye eder; bunun karşı kontrolü de var —
   yaşayan bir anahtar silinmemeli, yoksa "tahliye" fiilen sınırı kaldırırdı.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import get_settings
from app.core.errors import ConcurrencyLimitError
from app.core.rate_limit import ConcurrencyGate, SlidingWindowLimiter, reset_rate_limit
from app.modules.assessment import question_gen
from tests.conftest import UserFactory

# Soru üretimi ortamını kuran yardımcılar `test_assessment.py`'de yaşıyor ve
# oradan ithal ediliyor. İkinci bir kopya yazmak (chunk seed'i, sahte MCQ
# yanıtı) Anayasa XI'in yasakladığı şey olurdu; testler arası ithal bu depoda
# zaten kurulu bir desen (`test_documents_api` → `test_ingestion`).
from tests.test_assessment import (
    DEADLOCK_TEXTS,
    FakeCompletion,
    FakeRetriever,
    _create_course,
    _mcq_response,
    create_topic,
    retrieved,
    seed_chunks,
)


@pytest.fixture(autouse=True)
def temiz_sayaclar() -> AsyncIterator[None]:
    reset_rate_limit()
    yield
    reset_rate_limit()
    question_gen.reset_providers()


# ---------------------------------------------------------------------------
# Sınırlayıcının kendisi
# ---------------------------------------------------------------------------


class TestSlidingWindowLimiter:
    def test_kapsamlar_ayri_sayilir(self) -> None:
        """Aynı anahtar, iki kapsam: biri diğerinin kotasını tüketmemeli.

        Tek örnek iki uç tarafından paylaşılıyor ve ikisinin de doğal anahtarı
        `kullanıcı:ders`. Kapsam olmasaydı sohbet etmek soru üretimini sessizce
        engellerdi ve bunu kimse aramazdı.
        """
        limiter = SlidingWindowLimiter()
        anahtar = "kullanici:ders"

        assert limiter.allow("chat", anahtar, limit=1, window_seconds=60) is True
        assert limiter.allow("chat", anahtar, limit=1, window_seconds=60) is False
        # Sohbet kotası dolu; soru üretimi bundan etkilenmemeli.
        assert limiter.allow("qgen", anahtar, limit=1, window_seconds=60) is True

    def test_retry_after_en_eski_vurustan_hesaplanir(self) -> None:
        """Yer açacak olan şey en eski vuruşun pencereden düşmesi."""
        limiter = SlidingWindowLimiter()
        assert limiter.allow("qgen", "k", limit=1, window_seconds=300) is True
        assert limiter.allow("qgen", "k", limit=1, window_seconds=300) is False

        kalan = limiter.retry_after("qgen", "k", window_seconds=300)

        assert 299 < kalan <= 300

    def test_hic_vurusu_olmayan_anahtar_icin_bekleme_sifir(self) -> None:
        limiter = SlidingWindowLimiter()
        assert limiter.retry_after("qgen", "hic-gorulmemis", window_seconds=300) == 0.0

    def test_kullanilmayan_anahtar_tahliye_edilir(self) -> None:
        """FR-223: sayaç süreç ömrü boyunca sınırsız büyümemeli.

        Düzeltme öncesi her (kullanıcı, ders) çifti için açılan deque boşalsa
        bile anahtarı hiç silinmiyordu; `reset()` yalnız testlerden çağrılıyor,
        üretimde hiç.
        """
        limiter = SlidingWindowLimiter()
        limiter.allow("qgen", "eski-kullanici", limit=5, window_seconds=0.05)
        assert limiter.tracked_keys() == 1

        time.sleep(0.2)
        limiter.allow("qgen", "yeni-kullanici", limit=5, window_seconds=0.05)

        assert limiter.tracked_keys() == 1, "eski anahtar hâlâ bellekte"

    def test_yasayan_anahtar_tahliye_edilmez(self) -> None:
        """Karşı kontrol: her şeyi silen bir 'tahliye' sınırı fiilen kaldırır."""
        limiter = SlidingWindowLimiter()
        limiter.allow("qgen", "aktif", limit=5, window_seconds=0.05)

        time.sleep(0.2)
        # Aynı anahtar yeniden vuruyor: süpürme koşuyor ama bu anahtar taze.
        limiter.allow("qgen", "aktif", limit=5, window_seconds=0.05)
        limiter.allow("qgen", "baska", limit=5, window_seconds=0.05)

        assert limiter.tracked_keys() == 2


class TestConcurrencyGate:
    def test_sinira_ulasinca_ikinci_tutus_reddedilir(self) -> None:
        gate = ConcurrencyGate()
        with gate.hold("qgen", "kullanici", limit=1, message="sürüyor"):
            with pytest.raises(ConcurrencyLimitError):
                with gate.hold("qgen", "kullanici", limit=1, message="sürüyor"):
                    pytest.fail("kapı açılmamalıydı")

    def test_is_bitince_kapi_acilir(self) -> None:
        gate = ConcurrencyGate()
        with gate.hold("qgen", "kullanici", limit=1, message="sürüyor"):
            pass
        with gate.hold("qgen", "kullanici", limit=1, message="sürüyor"):
            pass
        assert gate.active("qgen", "kullanici") == 0

    def test_is_patlasa_da_kapi_acilir(self) -> None:
        """`finally` olmasaydı tek bir hata kullanıcıyı kalıcı olarak kilitlerdi."""
        gate = ConcurrencyGate()
        with pytest.raises(RuntimeError), gate.hold("qgen", "k", limit=1, message="sürüyor"):
            raise RuntimeError("üretim patladı")

        assert gate.active("qgen", "k") == 0

    def test_reddedilen_tutus_anahtar_biriktirmez(self) -> None:
        """Reddedilen tutuş `defaultdict`'te ölü anahtar bırakmamalı."""
        gate = ConcurrencyGate()
        with pytest.raises(ConcurrencyLimitError):
            with gate.hold("qgen", "yok", limit=0, message="sürüyor"):
                pytest.fail("limit 0 iken açılmamalıydı")

        assert gate.active("qgen", "yok") == 0


# ---------------------------------------------------------------------------
# Uç davranışı
# ---------------------------------------------------------------------------


class _BlokeEdenCompletion:
    """İzin verilene kadar bekleyen sahte LLM.

    Eşzamanlılığı ölçmenin tek dürüst yolu: birinci üretim GERÇEKTEN sürerken
    ikincisini göndermek. Sahte sağlayıcı hemen dönseydi iki istek asla
    çakışmaz ve test hiçbir şey kanıtlamazdı.
    """

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls = 0
        self.basladi = asyncio.Event()
        self.ikinci_basladi = asyncio.Event()
        self.devam = asyncio.Event()

    async def complete(self, *, system: str, user: str) -> str:
        del system, user
        self.calls += 1
        self.basladi.set()
        if self.calls >= 2:
            self.ikinci_basladi.set()
        await self.devam.wait()
        return self._response


async def _uretim_ortami(
    client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
) -> tuple[dict[str, str], str, UUID, list[UUID]]:
    """Eğitmen + ders + konu + kaynak chunk'lar."""
    ayse_id = await users.create("ayse@dogus.edu.tr")
    ayse = users.auth(ayse_id)
    course_id = await _create_course(client, ayse, "COME301")
    topic_id = await create_topic(client, ayse, course_id, "Deadlock")
    chunk_ids = await seed_chunks(
        admin_engine, course_id=UUID(course_id), uploaded_by=ayse_id, texts=DEADLOCK_TEXTS
    )
    return ayse, course_id, topic_id, chunk_ids


def _uret(client: AsyncClient, headers: dict[str, str], course_id: str, topic_id: UUID):
    return client.post(
        f"/courses/{course_id}/questions/generate",
        json={"topic_id": str(topic_id), "question_type": "mcq", "count": 1},
        headers=headers,
    )


class TestGenerationQuota:
    async def test_kota_dolunca_429_doner_ve_ne_zaman_denenecegini_soyler(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """FR-222: reddin kendisi yetmez, kullanıcı ne zaman deneyeceğini bilmeli.

        Bu bir nezaket metni değil sözleşme: arayüz backend'in mesajını olduğu
        gibi gösteriyor (`lib/api.ts`), yani süreyi taşıyan tek kanal bu.
        """
        ayse, course_id, topic_id, chunk_ids = await _uretim_ortami(client, users, admin_engine)
        sagliyici = FakeCompletion(_mcq_response(chunk_ids[0]))
        question_gen.set_providers(
            retriever_factory=lambda _s: FakeRetriever(retrieved(chunk_ids, DEADLOCK_TEXTS)),
            completion=sagliyici,
        )
        limit = get_settings().question_gen_rate_limit_requests

        for _ in range(limit):
            assert (await _uret(client, ayse, course_id, topic_id)).status_code == 200

        cagri_sayisi = sagliyici.calls
        response = await _uret(client, ayse, course_id, topic_id)

        assert response.status_code == 429
        hata = response.json()["error"]
        assert hata["code"] == "rate_limited"
        assert "dakika" in hata["message"], hata["message"]
        # Kota reddi LLM'e HİÇ gitmedi.
        assert sagliyici.calls == cagri_sayisi

    async def test_sohbet_kotasi_soru_uretim_kotasini_tuketmez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Kapsam ayrımının uç seviyesindeki karşılığı.

        Sohbetin penceresi 20/dk, üretimin 5/5dk. Tek sayaç paylaşılsaydı 20
        sohbet turu atan bir öğretmen soru üretemez hâle gelirdi.
        """
        from app.api.chat import RATE_LIMIT_SCOPE as CHAT_SCOPE
        from app.api.questions import QUESTION_GEN_SCOPE
        from app.core.rate_limit import get_limiter

        ayse, course_id, topic_id, chunk_ids = await _uretim_ortami(client, users, admin_engine)
        question_gen.set_providers(
            retriever_factory=lambda _s: FakeRetriever(retrieved(chunk_ids, DEADLOCK_TEXTS)),
            completion=FakeCompletion(_mcq_response(chunk_ids[0])),
        )

        # Sohbet kapsamını tıka.
        limiter = get_limiter()
        kullanici = ayse["Authorization"].removeprefix("Bearer dev:")
        anahtar = f"{kullanici}:{course_id}"
        for _ in range(get_settings().chat_rate_limit_requests):
            limiter.allow(CHAT_SCOPE, anahtar, limit=999, window_seconds=60)
        assert limiter.allow(CHAT_SCOPE, anahtar, limit=1, window_seconds=60) is False

        response = await _uret(client, ayse, course_id, topic_id)

        assert response.status_code == 200, response.text
        assert QUESTION_GEN_SCOPE != CHAT_SCOPE


class TestGenerationConcurrency:
    async def test_ikinci_es_zamanli_uretim_llm_e_gitmeden_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """FR-222'nin asıl iddiası. Ölçülen şey "reddedildi" değil, "bedava reddedildi"."""
        ayse, course_id, topic_id, chunk_ids = await _uretim_ortami(client, users, admin_engine)
        sagliyici = _BlokeEdenCompletion(_mcq_response(chunk_ids[0]))
        question_gen.set_providers(
            retriever_factory=lambda _s: FakeRetriever(retrieved(chunk_ids, DEADLOCK_TEXTS)),
            completion=sagliyici,
        )

        birinci = asyncio.create_task(_uret(client, ayse, course_id, topic_id))
        # Birinci üretim GERÇEKTEN LLM'in içinde asılı kalana kadar bekle.
        await asyncio.wait_for(sagliyici.basladi.wait(), timeout=5)
        cagri_sayisi = sagliyici.calls

        # `wait_for` bir süre sınırı değil, KIRILMA BİÇİMİ seçimi. Kapı
        # kaldırıldığında ikinci istek LLM'e girip `devam` olayında sonsuza
        # kadar asılı kalıyor ve test kırmızı yanmak yerine donuyordu; donan
        # bir test CI'da zaman aşımı olarak görünür ve sebebi okunmaz.
        try:
            ikinci = await asyncio.wait_for(_uret(client, ayse, course_id, topic_id), timeout=5)
        except TimeoutError:
            sagliyici.devam.set()
            await birinci
            pytest.fail("ikinci üretim reddedilmedi, LLM'e girip asılı kaldı — kapı çalışmıyor")

        assert ikinci.status_code == 409, ikinci.text
        hata = ikinci.json()["error"]
        assert hata["code"] == "concurrent_request"
        assert "sürüyor" in hata["message"]
        # Kapı LLM'den ÖNCE kapandı: ikinci istek tek bir tur bile ürettirmedi.
        assert sagliyici.calls == cagri_sayisi

        sagliyici.devam.set()
        assert (await birinci).status_code == 200

    async def test_birinci_bitince_ikinci_uretim_kabul_edilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Karşı kontrol: kapı kapalı kalsaydı bu test kırmızı yanardı.

        Sürekli reddeden bir kapı da yukarıdaki testi geçerdi; ayrımı bu yapıyor.
        """
        ayse, course_id, topic_id, chunk_ids = await _uretim_ortami(client, users, admin_engine)
        question_gen.set_providers(
            retriever_factory=lambda _s: FakeRetriever(retrieved(chunk_ids, DEADLOCK_TEXTS)),
            completion=FakeCompletion(_mcq_response(chunk_ids[0])),
        )

        assert (await _uret(client, ayse, course_id, topic_id)).status_code == 200
        assert (await _uret(client, ayse, course_id, topic_id)).status_code == 200

    async def test_baska_kullanici_ayni_anda_uretebilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Kapı KULLANICI başına; bir öğretmenin işi diğerini kilitlemez."""
        ayse, course_id, topic_id, chunk_ids = await _uretim_ortami(client, users, admin_engine)
        mehmet_id = await users.create("mehmet@dogus.edu.tr")
        mehmet = users.auth(mehmet_id)
        # İkinci eğitmen aynı derse eklenir.
        await client.post(
            f"/courses/{course_id}/members",
            json={"email": "mehmet@dogus.edu.tr", "role": "instructor"},
            headers=ayse,
        )

        sagliyici = _BlokeEdenCompletion(_mcq_response(chunk_ids[0]))
        question_gen.set_providers(
            retriever_factory=lambda _s: FakeRetriever(retrieved(chunk_ids, DEADLOCK_TEXTS)),
            completion=sagliyici,
        )

        birinci = asyncio.create_task(_uret(client, ayse, course_id, topic_id))
        await asyncio.wait_for(sagliyici.basladi.wait(), timeout=5)

        ikinci = asyncio.create_task(_uret(client, mehmet, course_id, topic_id))
        # İkinci de LLM'e ULAŞTI: kapı onu reddetmedi.
        await asyncio.wait_for(sagliyici.ikinci_basladi.wait(), timeout=5)

        sagliyici.devam.set()
        assert (await birinci).status_code == 200
        assert (await ikinci).status_code == 200
