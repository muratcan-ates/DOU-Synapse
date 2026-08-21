"""Belge yükleme uçtan uca testleri.

Doğrulanan akış: eğitmen PDF yükler → iş kuyruğa girer → worker belgeyi işler →
chunk'lar sayfa numarasıyla kaydedilir → öğrenci belgeyi görür ama başka dersin
öğrencisi göremez.
"""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import UserFactory
from tests.test_ingestion import make_pdf, make_pptx


async def _course(client: AsyncClient, headers: dict[str, str], code: str) -> str:
    response = await client.post(
        "/courses", json={"code": code, "title": f"{code} Dersi"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _upload(
    client: AsyncClient, headers: dict[str, str], course_id: str, name: str, data: bytes
):
    return await client.post(
        f"/courses/{course_id}/documents",
        files={"file": (name, data, "application/octet-stream")},
        headers=headers,
    )


class TestUpload:
    async def test_pdf_yuklenir_ve_islenir(self, client: AsyncClient, users: UserFactory) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _course(client, ayse, "COME301")

        pdf = make_pdf(
            [
                "Deadlock icin dort Coffman kosulu birlikte saglanmalidir.",
                "Round Robin algoritmasinda quantum sureyi belirler.",
            ]
        )
        response = await _upload(client, ayse, course_id, "hafta3.pdf", pdf)
        assert response.status_code == 202, response.text
        document_id = response.json()["document"]["id"]

        # Worker'ı doğrudan çalıştırırız: arka plan görevinin zamanlamasına bağlı,
        # kırılgan bir test yazmak yerine kuyruğun kendisini sınarız.
        from app import worker

        assert await worker.drain() == 1

        detail = await client.get(f"/courses/{course_id}/documents/{document_id}", headers=ayse)
        body = detail.json()
        assert body["status"] == "completed"
        assert body["page_count"] == 2
        assert body["chunk_count"] >= 2
        assert body["error_message"] is None

    async def test_chunklar_sayfa_numarasi_tasir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _course(client, ayse, "COME301")
        pdf = make_pdf(["Birinci sayfadaki konu.", "Ikinci sayfadaki baska konu."])
        document_id = (await _upload(client, ayse, course_id, "d.pdf", pdf)).json()["document"][
            "id"
        ]

        from app import worker

        await worker.drain()

        chunks = (
            await client.get(f"/courses/{course_id}/documents/{document_id}/chunks", headers=ayse)
        ).json()
        assert chunks
        assert {chunk["page_number"] for chunk in chunks} == {1, 2}
        for chunk in chunks:
            assert chunk["text"].strip()
            assert chunk["token_count"] > 0

    async def test_pptx_slayt_numarasi_tasir(self, client: AsyncClient, users: UserFactory) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _course(client, ayse, "COME301")
        pptx = make_pptx([("Deadlock", "Dort kosul"), ("Semafor", "Karsilikli dislama")])
        document_id = (await _upload(client, ayse, course_id, "slayt.pptx", pptx)).json()[
            "document"
        ]["id"]

        from app import worker

        await worker.drain()

        chunks = (
            await client.get(f"/courses/{course_id}/documents/{document_id}/chunks", headers=ayse)
        ).json()
        assert {chunk["slide_number"] for chunk in chunks} == {1, 2}
        assert all(chunk["page_number"] is None for chunk in chunks)

    async def test_ayni_dosya_ikinci_kez_reddedilir(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _course(client, ayse, "COME301")
        pdf = make_pdf(["Ayni icerik"])

        assert (await _upload(client, ayse, course_id, "a.pdf", pdf)).status_code == 202
        second = await _upload(client, ayse, course_id, "farkli-ad.pdf", pdf)
        assert second.status_code == 409

    async def test_bozuk_dosya_anlasilir_hata(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _course(client, ayse, "COME301")

        response = await _upload(client, ayse, course_id, "sahte.pdf", b"MZ\x90\x00bozuk")

        assert response.status_code == 422
        assert "uyuşmuyor" in response.json()["error"]["message"]

    async def test_silinen_belgenin_chunklari_da_gider(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """Materyal kaldırılınca ondan üretilen içerik aramada kalmamalı."""
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _course(client, ayse, "COME301")
        document_id = (
            await _upload(client, ayse, course_id, "d.pdf", make_pdf(["Silinecek icerik"]))
        ).json()["document"]["id"]

        from app import worker

        await worker.drain()
        assert (
            await client.get(f"/courses/{course_id}/documents/{document_id}/chunks", headers=ayse)
        ).json()

        deleted = await client.delete(f"/courses/{course_id}/documents/{document_id}", headers=ayse)
        assert deleted.status_code == 204
        assert (
            await client.get(f"/courses/{course_id}/documents/{document_id}", headers=ayse)
        ).status_code == 404


class TestDocumentAccess:
    async def test_ogrenci_belge_yukleyemez(self, client: AsyncClient, users: UserFactory) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _course(client, ayse, "COME301")
        await client.post(
            f"/courses/{course_id}/members",
            json={"email": "burak@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )

        response = await _upload(client, users.auth(burak_id), course_id, "x.pdf", make_pdf(["x"]))

        assert response.status_code == 403

    async def test_ogrenci_belgeleri_listeler_ama_chunk_onizlemesi_goremez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        course_id = await _course(client, ayse, "COME301")
        await client.post(
            f"/courses/{course_id}/members",
            json={"email": "burak@dogus.edu.tr", "role": "student"},
            headers=ayse,
        )
        document_id = (
            await _upload(client, ayse, course_id, "d.pdf", make_pdf(["icerik"]))
        ).json()["document"]["id"]

        burak = users.auth(burak_id)
        listed = await client.get(f"/courses/{course_id}/documents", headers=burak)
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        preview = await client.get(
            f"/courses/{course_id}/documents/{document_id}/chunks", headers=burak
        )
        assert preview.status_code == 403

    async def test_baska_dersin_ogrencisi_belgeleri_goremez(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        ceren = users.auth(await users.create("ceren@dogus.edu.tr"))
        course_a = await _course(client, ayse, "COME301")
        await _course(client, ceren, "COME302")
        await _upload(client, ayse, course_a, "d.pdf", make_pdf(["gizli"]))

        response = await client.get(f"/courses/{course_a}/documents", headers=ceren)

        assert response.status_code == 404


class TestWorkerQueue:
    async def test_bos_kuyrukta_sifir_dondurur(self, client: AsyncClient) -> None:
        from app import worker

        assert await worker.drain() == 0

    async def test_isleme_hatasi_belgeyi_failed_yapar(
        self, client: AsyncClient, users: UserFactory, admin_engine
    ) -> None:
        """Depodaki dosya kaybolursa iş sessizce kaybolmaz; belge 'failed' olur."""
        from sqlalchemy import text as sql_text

        from app import worker
        from app.modules.ingestion.storage import get_storage

        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _course(client, ayse, "COME301")
        upload = await _upload(client, ayse, course_id, "d.pdf", make_pdf(["icerik"]))
        document_id = upload.json()["document"]["id"]

        async with admin_engine.begin() as conn:
            storage_path = await conn.scalar(
                sql_text("SELECT storage_path FROM documents WHERE id = :id"),
                {"id": document_id},
            )
        await get_storage().delete(storage_path)

        # Üç deneme hakkı: ilk ikisi kuyruğa geri koyar, üçüncüsü kalıcı hata yazar.
        for _ in range(3):
            await worker.drain()

        detail = (
            await client.get(f"/courses/{course_id}/documents/{document_id}", headers=ayse)
        ).json()
        assert detail["status"] == "failed"
        assert detail["error_message"]
