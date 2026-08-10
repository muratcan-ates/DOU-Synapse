"""İki katmanlı izolasyonun AYRI AYRI sınanması (Anayasa II, T051).

`supabase/tests/rls_isolation.sql` ikinci katmanı (RLS) tek başına kanıtlar: politikalar
teker teker bozulur ve iddiaların kırmızı yandığı gösterilir. Bu dosya simetrik soruyu
sorar: **RLS tamamen devre dışıyken uygulama katmanı tek başına tutuyor mu?**

Soru teorik değil. `require_course_member` her istekte üyelik tablosuna bakıyor, ama bu
kontrolün gerçekten karar verdiğini gösteren bir test yoktu: RLS de aynı anda devrede
olduğu için her yetkisiz istek zaten boş sonuç dönüyordu ve iki katmandan hangisinin
tuttuğu ölçülmemişti. Uygulama katmanı sessizce delinseydi (ör. bir uçta `course_id`
doğrudan sorguya geçseydi) testlerin hiçbiri kırmızı yanmazdı.

Yöntem: API bağlantısı, RLS'i atlayan `dou_worker` rolüne çevrilir (BYPASSRLS). O
konfigürasyonda veritabanı hiçbir satırı gizlemez; kalan tek savunma uygulama kodudur.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.conftest import WORKER_DSN, UserFactory


@pytest.fixture
async def rls_kapali() -> AsyncIterator[None]:
    """API bağlantısını BYPASSRLS taşıyan role çevirir — ikinci katman tamamen kapalı."""
    from app.core.config import get_settings
    from app.core.db import dispose_engine

    onceki = os.environ["DATABASE_URL"]
    os.environ["DATABASE_URL"] = WORKER_DSN
    get_settings.cache_clear()
    await dispose_engine()
    try:
        yield
    finally:
        os.environ["DATABASE_URL"] = onceki
        get_settings.cache_clear()
        await dispose_engine()


async def _create_course(client: AsyncClient, headers: dict[str, str], code: str) -> str:
    response = await client.post(
        "/courses", json={"code": code, "title": f"{code} Dersi"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _gorunen_ders_sayisi(user_id: UUID) -> int:
    """Uygulamanın kullandığı oturumla, HAM SQL ile kaç ders görünüyor."""
    from app.core.db import rls_session

    async with rls_session(user_id) as session:
        return int((await session.scalar(text("SELECT count(*) FROM courses"))) or 0)


class TestKatmanAyrimi:
    async def test_rls_acikken_yabanci_hicbir_dersi_goremez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """Karşı kontrol: normal konfigürasyonda veritabanı satırı zaten gizliyor.

        Bu iddia olmadan aşağıdaki testin "RLS gerçekten kapalıydı" varsayımı
        doğrulanmamış kalırdı.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        await _create_course(client, ayse, "COME301")
        yabanci = await users.create("emre@dogus.edu.tr")

        assert await _gorunen_ders_sayisi(yabanci) == 0

    async def test_rls_kapaliyken_veritabani_gercekten_sizdiriyor(
        self, client: AsyncClient, users: UserFactory, rls_kapali: None
    ) -> None:
        """Deneyin kurulum kontrolü: BYPASSRLS rolüyle politikalar gerçekten inert.

        Bu test KIRMIZI olursa aşağıdaki iddialar yanlış sebeple yeşil yanıyor demektir
        — RLS hâlâ açıksa "uygulama katmanı tuttu" sonucu çıkarılamaz.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        await _create_course(client, ayse, "COME301")
        yabanci = await users.create("emre@dogus.edu.tr")

        assert await _gorunen_ders_sayisi(yabanci) == 1

    async def test_rls_kapaliyken_uye_olmayan_dersi_goremez(
        self, client: AsyncClient, users: UserFactory, rls_kapali: None
    ) -> None:
        """Asıl iddia: `require_course_member` tek başına yeterli.

        İstemciden gelen `course_id` gerçek ve mevcut; veritabanı hiçbir şey gizlemiyor.
        404 dönüyorsa kararı veren uygulama katmanıdır.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak = users.auth(await users.create("burak@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")

        response = await client.get(f"/courses/{course_id}", headers=burak)

        assert response.status_code == 404, response.text

    async def test_rls_kapaliyken_uye_belgeleri_goremez(
        self, client: AsyncClient, users: UserFactory, rls_kapali: None
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak = users.auth(await users.create("burak@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")

        response = await client.get(f"/courses/{course_id}/documents", headers=burak)

        assert response.status_code == 404, response.text

    async def test_rls_kapaliyken_ogrenci_uye_listesini_goremez(
        self, client: AsyncClient, users: UserFactory, rls_kapali: None
    ) -> None:
        """Rol kontrolü de uygulama katmanında: `CourseInstructorDep` 403 döndürür.

        Ders bulunamadı (404) değil yetki yok (403) beklenir: kullanıcı dersin üyesi,
        yalnız eğitmeni değil — dersin varlığını zaten biliyor.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await client.post(
            f"/courses/{course_id}/members",
            json={"email": "burak@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )

        response = await client.get(f"/courses/{course_id}/members", headers=users.auth(burak_id))

        assert response.status_code == 403, response.text

    async def test_rls_kapaliyken_ders_listesi_de_uygulamada_filtreleniyor(
        self, client: AsyncClient, users: UserFactory, rls_kapali: None
    ) -> None:
        """`GET /courses` üyelik JOIN'ini SQL'de kendisi yazıyor, RLS'e güvenmiyor.

        Bu ayrım önemli: filtreyi yalnız RLS'e bırakan bir uç, RLS'in bir gün
        gevşetilmesi hâlinde sessizce tüm dersleri listelerdi.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        yabanci = users.auth(await users.create("emre@dogus.edu.tr"))
        await _create_course(client, ayse, "COME301")

        response = await client.get("/courses", headers=yabanci)

        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_rls_kapaliyken_uye_dersini_gorebiliyor(
        self, client: AsyncClient, users: UserFactory, rls_kapali: None
    ) -> None:
        """Olumlu kontrol: yukarıdaki retler "her şey kapalı"dan gelmiyor."""
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")

        response = await client.get(f"/courses/{course_id}", headers=ayse)

        assert response.status_code == 200
        assert response.json()["id"] == course_id

    async def test_rls_kapaliyken_var_olmayan_ders_de_404(
        self, client: AsyncClient, users: UserFactory, rls_kapali: None
    ) -> None:
        """Var olmayan ders ile erişilemeyen ders aynı yanıtı verir: varlık sızmaz."""
        burak = users.auth(await users.create("burak@dogus.edu.tr"))

        response = await client.get(f"/courses/{uuid4()}", headers=burak)

        assert response.status_code == 404
