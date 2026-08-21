"""T906 — API JSON yanıtlarının temel tarayıcı güvenlik başlıkları."""

from __future__ import annotations

from httpx import AsyncClient

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
