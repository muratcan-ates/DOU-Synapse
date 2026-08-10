"""Ders erişimi ve izolasyon testleri (PLAN.md G2 kapısı).

Bu dosyanın asıl işi mutlu yolu doğrulamak değil; **başka bir dersin verisine erişimin
mümkün olmadığını** göstermektir. Testler API'nin üretimdeki bağlantı yolunu kullanır
(dou_app rolü), dolayısıyla hem uygulama katmanı hem RLS gerçekten devrededir.
"""

from __future__ import annotations

from uuid import uuid4

from httpx import AsyncClient

from tests.conftest import UserFactory
from tests.factories import create_course, enroll_student

# Üyelik ekleme yalnız KURULUM olduğu yerlerde `enroll_student` ile yapılır. Üyelik
# ucunun kendisini sınayan testler (401/403/404 ya da yanıt gövdesi) isteği elle
# kurar: iddiayı fabrikaya taşımak, testin ne kanıtladığını çağrı yerinden okunmaz
# hale getirirdi.


class TestAuthentication:
    async def test_auth_header_olmadan_401(self, client: AsyncClient) -> None:
        response = await client.get("/courses")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"

    async def test_bozuk_token_401(self, client: AsyncClient) -> None:
        response = await client.get("/courses", headers={"Authorization": "Bearer dev:xyz"})
        assert response.status_code == 401

    async def test_bearer_olmayan_sema_401(self, client: AsyncClient) -> None:
        response = await client.get("/courses", headers={"Authorization": "Basic abc"})
        assert response.status_code == 401


class TestCourseCreation:
    async def test_ders_olusturan_egitmen_olur(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        user_id = await users.create("ayse@dogus.edu.tr", "Ayşe Hoca")
        headers = users.auth(user_id)

        response = await client.post(
            "/courses", json={"code": "COME301", "title": "İşletim Sistemleri"}, headers=headers
        )

        assert response.status_code == 201
        body = response.json()
        assert body["code"] == "COME301"
        assert body["role"] == "instructor"

    async def test_ayni_kod_ikinci_kez_reddedilir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        headers = users.auth(await users.create("ayse@dogus.edu.tr"))
        await create_course(client, headers, "COME301")

        response = await client.post(
            "/courses", json={"code": "come301", "title": "Kopya"}, headers=headers
        )

        assert response.status_code == 409

    async def test_liste_yalnizca_uye_olunan_dersleri_dondurur(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak = users.auth(await users.create("burak@dogus.edu.tr"))
        await create_course(client, ayse, "COME301")

        assert len((await client.get("/courses", headers=ayse)).json()["items"]) == 1
        assert (await client.get("/courses", headers=burak)).json()["items"] == []

    async def test_liste_keyset_ile_sayfalanir_es_zamanli_ekleme_kaydirmaz(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_ids = {
            str(await create_course(client, ayse, "PAGE1")),
            str(await create_course(client, ayse, "PAGE2")),
            str(await create_course(client, ayse, "PAGE3")),
        }

        first = (await client.get("/courses", params={"limit": 2}, headers=ayse)).json()
        assert first["next_cursor"] is not None

        # İlk sayfadan sonra başa yeni kayıt girse bile ikinci sayfa tekrar/atlama yapmaz.
        inserted_after_cursor = await create_course(client, ayse, "PAGE4")
        second = (
            await client.get(
                "/courses",
                params={"limit": 2, "cursor": first["next_cursor"]},
                headers=ayse,
            )
        ).json()

        assert len(first["items"]) == 2
        assert len(second["items"]) == 1
        assert {row["id"] for row in first["items"] + second["items"]} == course_ids
        assert inserted_after_cursor not in {row["id"] for row in second["items"]}
        assert (await client.get("/courses?limit=101", headers=ayse)).status_code == 200
        invalid = await client.get("/courses?cursor=bozuk", headers=ayse)
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "invalid_cursor"


class TestCourseIsolation:
    """course_id istemciden gelse bile yetkisiz erişim mümkün olmamalı."""

    async def test_uye_olmayan_kullanici_dersi_goremez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak = users.auth(await users.create("burak@dogus.edu.tr"))
        course_id = await create_course(client, ayse, "COME301")

        response = await client.get(f"/courses/{course_id}", headers=burak)

        # Dersin varlığı sızdırılmaz: 403 değil 404 döner.
        assert response.status_code == 404

    async def test_var_olmayan_ders_de_404(self, client: AsyncClient, users: UserFactory) -> None:
        burak = users.auth(await users.create("burak@dogus.edu.tr"))
        response = await client.get(f"/courses/{uuid4()}", headers=burak)
        assert response.status_code == 404

    async def test_ogrenci_uye_listesini_goremez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")

        response = await client.get(f"/courses/{course_id}/members", headers=users.auth(burak_id))

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    async def test_ogrenci_derse_uye_ekleyemez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        await users.create("ceren@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")

        response = await client.post(
            f"/courses/{course_id}/members",
            json={"email": "ceren@dogus.edu.tr", "role": "student"},
            headers=users.auth(burak_id),
        )

        assert response.status_code == 403


class TestMembership:
    async def test_egitmen_ogrenci_ekler_ve_ogrenci_dersi_gorur(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr", "Burak Öğrenci")
        course_id = await create_course(client, ayse, "COME301")

        added = await client.post(
            f"/courses/{course_id}/members",
            json={"email": "burak@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )
        assert added.status_code == 201
        assert added.json()["role"] == "student"

        listed = await client.get("/courses", headers=users.auth(burak_id))
        assert [c["id"] for c in listed.json()["items"]] == [str(course_id)]

    async def test_kayitli_olmayan_eposta_404(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await create_course(client, ayse, "COME301")

        response = await client.post(
            f"/courses/{course_id}/members",
            json={"email": "yok@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )

        assert response.status_code == 404

    async def test_uyelik_iptali_erisimi_kapatir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME301")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")

        revoked = await client.delete(f"/courses/{course_id}/members/{burak_id}", headers=ayse)
        assert revoked.status_code == 204

        assert (await client.get("/courses", headers=users.auth(burak_id))).json()["items"] == []
        assert (
            await client.get(f"/courses/{course_id}", headers=users.auth(burak_id))
        ).status_code == 404

    async def test_egitmen_kendi_uyeligini_kaldiramaz(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_id = await create_course(client, ayse, "COME301")

        response = await client.delete(f"/courses/{course_id}/members/{ayse_id}", headers=ayse)

        assert response.status_code == 422
