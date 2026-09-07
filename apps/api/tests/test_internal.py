"""`POST /internal/drain` ve worker tetiği testleri (T049).

Bu uç kullanıcı arayüzünün değil altyapının ucudur: kimlik doğrulaması yoktur,
paylaşılan sır vardır. Sınanan dört davranış:

1. Sır yapılandırılmamışken uç **yok gibi** davranır (404, 403 değil).
2. Yanlış/eksik sır 403 alır.
3. Doğru sır işi gerçekten işler ve işlenen sayıyı döndürür.
4. Karşılaştırma sabit zamanlıdır — düz `==` sırrı bayt bayt tahmin ettirir.

Ayrıca `trigger_drain`'in iki dağıtım biçimi de sınanır: ortamda worker URL'i
varsa gerçek bir HTTP isteği yapılır (ASGI taşıması üzerinden, ağsız), yoksa
süreç içi `drain()` koşar.
"""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from uuid import UUID

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api import internal
from tests.conftest import UserFactory
from tests.factories import create_course, make_pdf

SECRET = "cok-uzun-ve-rastgele-bir-sir-0123456789"


@pytest.fixture
def drain_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Sırrı tanımlar ve ayar önbelleğini temizler.

    `get_settings` lru_cache'lidir; ortam değişkenini yazmak tek başına yetmez.
    """
    from app.core.config import get_settings

    monkeypatch.setenv("WORKER_DRAIN_SECRET", SECRET)
    get_settings.cache_clear()
    yield SECRET
    get_settings.cache_clear()


async def _course_with_pending_job(
    client: AsyncClient, users: UserFactory, monkeypatch: pytest.MonkeyPatch
) -> UUID:
    """Kuyrukta GERÇEKTEN bekleyen bir iş bırakır ve ders kimliğini döndürür.

    Yüklemenin arka plan tetiği bilerek devre dışı bırakılır: aksi hâlde iş,
    biz drain ucunu çağırmadan önce işlenmiş olur ve test "işlenen sayı"yı
    yarışa bağlı biçimde ölçerdi.
    """
    monkeypatch.setattr("app.api.documents._trigger_worker", _noop)

    headers = users.auth(await users.create("ayse@dogus.edu.tr"))
    course_id = await create_course(client, headers, "COME360", title="Dagitim")

    pdf = make_pdf(["Kuyruga giren tek belgenin tek sayfasi."])
    upload = await client.post(
        f"/courses/{course_id}/documents",
        files={"file": ("hafta1.pdf", pdf, "application/pdf")},
        headers=headers,
    )
    assert upload.status_code == 202, upload.text
    return course_id


async def _noop() -> None:
    return None


class TestDrainYetkilendirme:
    async def test_sir_tanimsizsa_uc_yok_gibi_davranir(self, client: AsyncClient) -> None:
        """Fail-closed: yapılandırılmamış koruma açık uç bırakmaz.

        403 değil 404 beklenir — 403 "burada korunan bir şey var" bilgisini
        sızdırır ve sırrı aramaya davet ederdi.
        """
        response = await client.post("/internal/drain")
        assert response.status_code == 404, response.text
        assert response.json()["error"]["code"] == "not_found"

    async def test_sir_tanimsizsa_dogru_sirla_bile_404(self, client: AsyncClient) -> None:
        response = await client.post("/internal/drain", headers={"X-Worker-Secret": SECRET})
        assert response.status_code == 404, response.text

    async def test_sirsiz_istek_403(self, client: AsyncClient, drain_secret: str) -> None:
        response = await client.post("/internal/drain")
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "permission_denied"

    async def test_yanlis_sir_403(self, client: AsyncClient, drain_secret: str) -> None:
        response = await client.post("/internal/drain", headers={"X-Worker-Secret": "yanlis"})
        assert response.status_code == 403, response.text

    async def test_dogru_onekli_ama_eksik_sir_403(
        self, client: AsyncClient, drain_secret: str
    ) -> None:
        """Farklı uzunluk `compare_digest`'i patlatmaz, 403 verir."""
        response = await client.post(
            "/internal/drain", headers={"X-Worker-Secret": drain_secret[:-1]}
        )
        assert response.status_code == 403, response.text

    async def test_uc_openapi_semasina_girmez(self) -> None:
        """Dahili uç istemci sözleşmesinin parçası değildir.

        Şema HTTP'den değil uygulamadan okunuyor: `/openapi.json` artık platform
        yöneticisi ister ve bu test yetkiyi değil ŞEMA İÇERİĞİNİ çiviliyor.
        Kapıyı ayrıca `test_security_headers` sınar.
        """
        from app.main import create_app

        spec = create_app().openapi()
        assert not [path for path in spec["paths"] if path.startswith("/internal")]


class TestSabitZamanliKarsilastirma:
    def test_stdlib_compare_digest_kullaniliyor(self) -> None:
        """Modül düzeyindeki adın gerçekten stdlib'in sabit zamanlı işlevi olduğu.

        Aynı adı taşıyan yerel bir sarmalayıcı bu iddiayı düşürür.
        """
        assert internal.compare_digest is secrets.compare_digest

    async def test_karar_compare_digest_uzerinden_veriliyor(
        self, client: AsyncClient, drain_secret: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Uç, kararı gerçekten o işlevden geçirerek veriyor mu.

        Yalnız `is` kontrolü yetmez: içe aktarılmış ama kullanılmıyor olabilirdi.
        """
        calls: list[tuple[bytes, bytes]] = []

        def spy(a: bytes, b: bytes) -> bool:
            calls.append((a, b))
            return secrets.compare_digest(a, b)

        monkeypatch.setattr(internal, "compare_digest", spy)

        response = await client.post("/internal/drain", headers={"X-Worker-Secret": "yanlis"})
        assert response.status_code == 403
        assert calls, "sır karşılaştırması compare_digest'e uğramadı"
        # Sır düz metin olarak değil, karşılaştırmaya giren baytlar olarak görülür.
        assert calls[0][1] == SECRET.encode("utf-8")


class TestDrainIsGorur:
    async def test_dogru_sir_bekleyen_isi_isler(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        drain_secret: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        course_id = await _course_with_pending_job(client, users, monkeypatch)

        async with admin_engine.begin() as conn:
            pending = await conn.scalar(
                text("SELECT count(*) FROM ingestion_jobs WHERE status = 'pending'")
            )
        assert pending == 1, "test kurulumu bozuk: kuyrukta bekleyen iş yok"

        response = await client.post("/internal/drain", headers={"X-Worker-Secret": drain_secret})
        assert response.status_code == 200, response.text
        assert response.json() == {"processed": 1}

        async with admin_engine.begin() as conn:
            status_value = await conn.scalar(
                text("SELECT status FROM documents WHERE course_id = :cid"),
                {"cid": course_id},
            )
        assert status_value == "completed"

    async def test_bos_kuyrukta_sifir_doner(self, client: AsyncClient, drain_secret: str) -> None:
        """Uç idempotenttir: işlenecek iş yoksa hata değil sıfır döner."""
        response = await client.post("/internal/drain", headers={"X-Worker-Secret": drain_secret})
        assert response.status_code == 200, response.text
        assert response.json() == {"processed": 0}


class TestTetikSecimi:
    async def test_url_yoksa_surec_ici_drain_kosar(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv(internal.WORKER_DRAIN_URL_ENV, raising=False)
        await _course_with_pending_job(client, users, monkeypatch)

        # HTTP yolunun SEÇİLMEDİĞİ de kanıtlanmalı: iş her iki yolda da işlenirdi,
        # dolayısıyla yalnız sonucu ölçen bir test iki dalı ayırt edemez.
        def forbidden(**kwargs: object) -> httpx.AsyncClient:
            raise AssertionError("URL yokken HTTP istemcisi kurulmamalı")

        monkeypatch.setattr(internal.httpx, "AsyncClient", forbidden)

        await internal.trigger_drain()

        async with admin_engine.begin() as conn:
            status_value = await conn.scalar(text("SELECT status FROM documents LIMIT 1"))
        assert status_value == "completed", "süreç içi tetik işi işletmedi"

    async def test_url_varsa_gercek_http_istegi_yapilir(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        drain_secret: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Uzak dağıtım biçimi: tetik → HTTP → /internal/drain → drain().

        İstek gerçek `httpx` istemcisiyle yapılır; yalnız taşıma katmanı ASGI'ye
        yönlendirilir, böylece test ağsız koşar ama HTTP yolu (başlık dâhil)
        gerçekten çalışır.
        """
        await _course_with_pending_job(client, users, monkeypatch)

        from app.main import create_app

        app = create_app()
        real_client = httpx.AsyncClient
        requests: list[int] = []

        def factory(**kwargs: object) -> httpx.AsyncClient:
            requests.append(1)
            kwargs["transport"] = httpx.ASGITransport(app=app)
            return real_client(**kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(internal.httpx, "AsyncClient", factory)
        monkeypatch.setenv(internal.WORKER_DRAIN_URL_ENV, "http://worker.internal/internal/drain")

        await internal.trigger_drain()

        # İş her iki dalda da işlenirdi; HTTP dalının seçildiği ayrıca kanıtlanır.
        assert requests == [1], "uzak dal seçilmedi, süreç içi drain'e düşülmüş"

        async with admin_engine.begin() as conn:
            status_value = await conn.scalar(text("SELECT status FROM documents LIMIT 1"))
            pending = await conn.scalar(
                text("SELECT count(*) FROM ingestion_jobs WHERE status = 'pending'")
            )
        assert status_value == "completed", "HTTP tetiği işi işletmedi"
        assert pending == 0

    async def test_url_var_sir_yoksa_istek_yapilmaz(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sırsız uzak çağrı zaten 404 alır; boşuna istek atılmaz."""
        called = False

        def factory(**kwargs: object) -> httpx.AsyncClient:
            nonlocal called
            called = True
            raise AssertionError("sırsızken HTTP istemcisi kurulmamalı")

        monkeypatch.setattr(internal.httpx, "AsyncClient", factory)
        monkeypatch.setenv(internal.WORKER_DRAIN_URL_ENV, "http://worker.internal/internal/drain")
        monkeypatch.delenv("WORKER_DRAIN_SECRET", raising=False)

        from app.core.config import get_settings

        get_settings.cache_clear()
        try:
            await internal.trigger_drain()
        finally:
            get_settings.cache_clear()
        assert called is False

    async def test_uzak_tetik_hatasi_yukleme_istegini_dusurmez(
        self, monkeypatch: pytest.MonkeyPatch, drain_secret: str
    ) -> None:
        """Tetik başarısızlığı yutulur: dosya kaydedilmiştir, iş kuyrukta bekler."""

        def factory(**kwargs: object) -> httpx.AsyncClient:
            raise httpx.ConnectError("worker ayakta değil")

        monkeypatch.setattr(internal.httpx, "AsyncClient", factory)
        monkeypatch.setenv(internal.WORKER_DRAIN_URL_ENV, "http://worker.internal/internal/drain")

        await internal.trigger_drain()  # istisna dışarı sızmamalı
