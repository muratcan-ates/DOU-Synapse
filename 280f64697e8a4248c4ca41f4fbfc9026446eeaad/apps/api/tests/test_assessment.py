"""Ölçme (assessment) testleri.

Bu dosya şu an yalnız `topics` ucunu kapsar (T030'un T024/T025'i açan ilk parçası).
question_gen/grading/exams uçları eklendikçe tasks.md T033'teki sekiz vaka buraya
eklenecek: şema geçerliliği, draft görünmezliği, exam modu ipucu reddi, süre/boş cevap
davranışı, MCQ "neden yanlış", boş havuzda sınav reddi, oturuma dönüş, practice modu.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.db import rls_session
from tests.conftest import UserFactory


async def _create_course(client: AsyncClient, headers: dict[str, str], code: str) -> str:
    response = await client.post(
        "/courses", json={"code": code, "title": f"{code} Dersi"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


class TestTopicCreation:
    async def test_egitmen_konu_olusturur(self, client: AsyncClient, users: UserFactory) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")

        response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["name"] == "Deadlock"
        assert body["course_id"] == course_id

    async def test_ogrenci_konu_olusturamaz(self, client: AsyncClient, users: UserFactory) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await client.post(
            f"/courses/{course_id}/members",
            json={"email": "burak@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )

        response = await client.post(
            f"/courses/{course_id}/topics",
            json={"name": "Deadlock"},
            headers=users.auth(burak_id),
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "permission_denied"

    async def test_uye_olmayan_kullanici_konu_olusturamaz(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        disari = users.auth(await users.create("disari@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")

        response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=disari
        )

        # Dersin varlığı sızdırılmaz: 403 değil 404.
        assert response.status_code == 404

    async def test_ayni_isimde_ikinci_konu_reddedilir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")
        await client.post(f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse)

        response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "deadlock"}, headers=ayse
        )

        assert response.status_code == 409


class TestTopicListing:
    async def test_ogrenci_konu_listesini_gorur(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await client.post(
            f"/courses/{course_id}/members",
            json={"email": "burak@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )
        await client.post(f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse)
        await client.post(
            f"/courses/{course_id}/topics", json={"name": "CPU Zamanlama"}, headers=ayse
        )

        response = await client.get(f"/courses/{course_id}/topics", headers=users.auth(burak_id))

        assert response.status_code == 200
        names = {topic["name"] for topic in response.json()}
        assert names == {"Deadlock", "CPU Zamanlama"}

    async def test_baska_dersin_konusu_donmez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """İzolasyon: course_id istemciden gelse bile başka dersin verisi sızmaz (Anayasa II)."""
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_a = await _create_course(client, ayse, "COME301")
        course_b = await _create_course(client, ayse, "COME302")
        await client.post(f"/courses/{course_a}/topics", json={"name": "Deadlock"}, headers=ayse)
        await client.post(
            f"/courses/{course_b}/topics", json={"name": "Bellek Yönetimi"}, headers=ayse
        )

        response_a = await client.get(f"/courses/{course_a}/topics", headers=ayse)
        response_b = await client.get(f"/courses/{course_b}/topics", headers=ayse)

        assert [t["name"] for t in response_a.json()] == ["Deadlock"]
        assert [t["name"] for t in response_b.json()] == ["Bellek Yönetimi"]

    async def test_uye_olmayan_kullanici_listeyi_goremez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        disari = users.auth(await users.create("disari@dogus.edu.tr"))
        course_id = await _create_course(client, ayse, "COME301")
        await client.post(f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse)

        response = await client.get(f"/courses/{course_id}/topics", headers=disari)

        assert response.status_code == 404


class TestMasteryAndAnswersCourseIsolation:
    """PR incelemesi kalem 2 regresyon testi.

    mastery_self_insert / mastery_self_update ve answers_self_insert politikaları
    yalnızca user_id kontrol ediyordu; kullanıcının o dersin üyesi olup olmadığına
    bakmıyordu. Üye olunmayan bir derse mastery satırı yazılabiliyordu (elle psql ile
    kanıtlandı: bkz. PR_INCELEME_2026-08-06.md kalem 2). Bu test, düzeltmenin gerçekten
    kapattığını otomatik olarak doğrular.
    """

    async def test_uye_olmayan_ders_icin_mastery_satiri_yazilamaz(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        # Burak hiçbir derse üye değil.
        course_id = await _create_course(client, ayse, "COME301")
        topic_response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse
        )
        topic_id = UUID(topic_response.json()["id"])

        with pytest.raises(DBAPIError):
            async with rls_session(burak_id) as session:
                await session.execute(
                    text(
                        "INSERT INTO mastery (user_id, topic_id, course_id, score, "
                        "answer_count) VALUES (:uid, :tid, :cid, 0.8, 1)"
                    ),
                    {"uid": burak_id, "tid": topic_id, "cid": UUID(course_id)},
                )

    async def test_uye_olan_kullanici_kendi_mastery_satirini_yazabilir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """Düzeltmenin aşırıya kaçıp meşru yazımı da engellemediğinin kontrolü."""
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _create_course(client, ayse, "COME301")
        await client.post(
            f"/courses/{course_id}/members",
            json={"email": "burak@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )
        topic_response = await client.post(
            f"/courses/{course_id}/topics", json={"name": "Deadlock"}, headers=ayse
        )
        topic_id = UUID(topic_response.json()["id"])

        async with rls_session(burak_id) as session:
            await session.execute(
                text(
                    "INSERT INTO mastery (user_id, topic_id, course_id, score, "
                    "answer_count) VALUES (:uid, :tid, :cid, 0.8, 1)"
                ),
                {"uid": burak_id, "tid": topic_id, "cid": UUID(course_id)},
            )
