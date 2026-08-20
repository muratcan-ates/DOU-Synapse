"""T906 — API JSON yanıtlarının temel tarayıcı güvenlik başlıkları."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import UserFactory

EXPECTED_HEADERS = {
    "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}


async def test_api_basari_yaniti_guvenlik_basliklarini_tasir(client: AsyncClient) -> None:
    response = await client.get("/health/live")

    assert response.status_code == 200
    for key, value in EXPECTED_HEADERS.items():
        assert response.headers[key] == value


async def test_api_hata_yaniti_da_guvenlik_basliklarini_tasir(client: AsyncClient) -> None:
    response = await client.get("/olmayan-yol")

    assert response.status_code == 404
    for key, value in EXPECTED_HEADERS.items():
        assert response.headers[key] == value


DOCS_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
    "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


async def test_belge_yuzeyi_kendi_politikasiyla_servis_edilir(client: AsyncClient) -> None:
    """`/docs` bir SAYFADIR: kendi CSS'ini ve Swagger paketini yükleyebilmeli.

    JSON uçlarının `default-src 'none'` kuralı burada uygulanırsa kullanıcı boş
    ekran görür. Gevşetme yalnız bu yüzeye ve yalnız `'self'` kadardır.
    """
    response = await client.get("/docs")

    assert response.status_code == 200
    assert response.headers["content-security-policy"] == DOCS_CSP
    assert response.headers["x-content-type-options"] == "nosniff"


async def test_belge_yuzeyi_gevsemesi_json_uclarina_sizmaz(client: AsyncClient) -> None:
    """Yüzey ayrımı tek yönlüdür; veri uçları katı politikada kalır."""
    response = await client.get("/health/live")

    assert (
        response.headers["content-security-policy"] == EXPECTED_HEADERS["content-security-policy"]
    )


async def test_belge_sayfasi_cdn_ve_inline_script_kullanmaz(client: AsyncClient) -> None:
    """Sayfa kendi varlıklarını barındırır; yoksa politika onu zaten çalıştırmaz.

    Kaynak taraması bilinçli: politikayı gevşetmeden 'çalışıyor' demenin tek
    yolu, sayfanın dışarıdan script çekmediğini ve inline script taşımadığını
    kanıtlamaktır.
    """
    body = (await client.get("/docs")).text

    assert "https://cdn." not in body and "unpkg.com" not in body
    assert "<script>" not in body  # yalnız `src` ile yüklenen betikler
    assert "/static/vendor/swagger-ui-bundle.js" in body


async def test_sozlesme_yonetici_olmadan_alinamaz(client: AsyncClient) -> None:
    """`/openapi.json` ürünün tüm yüzeyini anlatır; herkese açık değildir."""
    response = await client.get("/openapi.json")

    assert response.status_code in (401, 403), response.text
    assert "paths" not in response.text


async def test_sozlesme_ders_uyesine_de_kapali(client: AsyncClient, users: UserFactory) -> None:
    """Ders üyeliği yeterli DEĞİL: kapı platform yöneticiliğine bakar."""
    user_id = await users.create("sozlesme-uye@dogus.edu.tr")

    response = await client.get("/openapi.json", headers=users.auth(user_id))

    assert response.status_code == 403, response.text


async def test_belge_kabugu_sozlesme_icermez(client: AsyncClient) -> None:
    """Kabuk herkese açıktır ama içinde uç listesi YOKTUR.

    Sayfayı gizlemek koruma değildir; korunması gereken şey sözleşmedir. Bu
    test, kabuğa bir gün şema gömülürse kırmızı yanar.
    """
    body = (await client.get("/docs")).text

    assert "/courses/{course_id}/chat" not in body
    assert '"paths"' not in body
    assert "Yönetici erişimi gerekiyor" in body
