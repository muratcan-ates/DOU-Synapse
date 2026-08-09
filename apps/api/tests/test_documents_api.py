"""Belge yükleme uçtan uca testleri.

Doğrulanan akış: eğitmen PDF yükler → iş kuyruğa girer → worker belgeyi işler →
chunk'lar sayfa numarasıyla kaydedilir → öğrenci belgeyi görür ama başka dersin
öğrencisi göremez.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import UserFactory
from tests.test_ingestion import make_pdf, make_pptx


async def _course(client: AsyncClient, headers: dict[str, str], code: str) -> str:
    response = await client.post(
        "/courses", json={"code": code, "title": f"{code} Dersi"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _upload(
    client: AsyncClient,
    headers: dict[str, str],
    course_id: str,
    name: str,
    data: bytes,
    *,
    replaces_document_id: str | None = None,
):
    return await client.post(
        f"/courses/{course_id}/documents",
        files={"file": (name, data, "application/octet-stream")},
        data=(
            {"replaces_document_id": replaces_document_id}
            if replaces_document_id is not None
            else None
        ),
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

        # Kuyruk, yanıttan sonra çalışan arka plan tetiği tarafından ZATEN
        # boşaltılmış olabilir. 9 Ağustos'a kadar olamazdı: belge satırı yanıttan
        # sonra commit edildiği için tetik hiçbir iş bulamıyor ve sessizce sıfır
        # dönüyordu — kuyruğu gerçekte bu satır boşaltıyordu. `SessionDep` artık
        # yanıt yazılmadan önce commit ettiği için tetik iş görüyor.
        #
        # Bu yüzden burada kuyruk SAYISI değil SONUÇ sınanır: iş ister tetikle
        # ister burada işlensin, belge işlenmiş olmalı. `drain()` idempotenttir.
        from app import worker

        await worker.drain()

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

    async def test_yeni_surum_eski_belgeyi_acikca_isaretler(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _course(client, ayse, "COME301")
        old_id = (
            await _upload(client, ayse, course_id, "hafta3-v1.pdf", make_pdf(["Eski içerik"]))
        ).json()["document"]["id"]

        replacement = await _upload(
            client,
            ayse,
            course_id,
            "hafta3-v2.pdf",
            make_pdf(["Yeni ve düzeltilmiş içerik"]),
            replaces_document_id=old_id,
        )

        assert replacement.status_code == 202, replacement.text
        assert replacement.json()["document"]["supersedes_document_id"] == old_id
        old = await client.get(f"/courses/{course_id}/documents/{old_id}", headers=ayse)
        assert old.json()["superseded_at"] is not None

        repeated = await _upload(
            client,
            ayse,
            course_id,
            "hafta3-v3.pdf",
            make_pdf(["Üçüncü içerik"]),
            replaces_document_id=old_id,
        )
        assert repeated.status_code == 409
        assert "en güncel" in repeated.json()["error"]["message"]

    async def test_yenilenen_kaynaga_bagli_soru_bayat_isaretlenir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = users.auth(ayse_id)
        course_id = await _course(client, ayse, "COME301")
        old_id = (
            await _upload(client, ayse, course_id, "v1.pdf", make_pdf(["Kaynak sürüm bir"]))
        ).json()["document"]["id"]
        from app import worker

        await worker.drain()
        old_chunks = (
            await client.get(f"/courses/{course_id}/documents/{old_id}/chunks", headers=ayse)
        ).json()
        async with admin_engine.begin() as conn:
            topic_id = await conn.scalar(
                text(
                    "INSERT INTO topics (course_id, name, created_by) "
                    "VALUES (:course, 'Sürüm', :user) RETURNING id"
                ),
                {"course": course_id, "user": ayse_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO questions "
                    "(course_id, topic_id, source_chunk_id, type, payload, status, created_by) "
                    "VALUES (:course, :topic, :chunk, 'mcq', '{}'::jsonb, 'draft', :user)"
                ),
                {
                    "course": course_id,
                    "topic": topic_id,
                    "chunk": old_chunks[0]["id"],
                    "user": ayse_id,
                },
            )

        before = await client.get(f"/courses/{course_id}/questions", headers=ayse)
        assert before.json()[0]["source_stale"] is False

        replaced = await _upload(
            client,
            ayse,
            course_id,
            "v2.pdf",
            make_pdf(["Kaynak sürüm iki"]),
            replaces_document_id=old_id,
        )
        assert replaced.status_code == 202, replaced.text

        after = await client.get(f"/courses/{course_id}/questions", headers=ayse)
        assert after.json()[0]["source_stale"] is True

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

    async def test_havuzda_sorusu_olan_belge_409_ile_reddedilir(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Kaynağı silinecek soru varsa silme reddedilir — 500 ile değil, 409 ile.

        `questions.source_chunk_id` `ON DELETE RESTRICT` taşır ve bu kısıt bilinçli:
        kaynağı silinmiş bir soru, kaynağına karşı doğrulanamayan bir sorudur
        (Anayasa I). Kısıt doğruydu ama uç `IntegrityError`'ı yakalamadığı için
        kullanıcı "bir şeyler ters gitti" görüyordu. Şerit 4 soru üretimini indirince
        bu yol ulaşılabilir hâle geldi.
        """
        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = UserFactory.auth(ayse_id)
        course_id = await _course(client, ayse, "COME301")
        document_id = (
            await _upload(client, ayse, course_id, "d.pdf", make_pdf(["Kaynak icerik"]))
        ).json()["document"]["id"]

        from app import worker

        await worker.drain()
        chunks = (
            await client.get(f"/courses/{course_id}/documents/{document_id}/chunks", headers=ayse)
        ).json()
        assert chunks, "chunk üretilmeden bu testin kuracağı durum oluşmaz"

        # Soruyu doğrudan yazıyoruz: üretim ucu gerçek LLM ister ve bu test onun
        # değil, silme davranışının testi.
        async with admin_engine.begin() as conn:
            topic_id = await conn.scalar(
                text(
                    "INSERT INTO topics (course_id, name, created_by) "
                    "VALUES (:c, 'Konu', :u) RETURNING id"
                ),
                {"c": course_id, "u": ayse_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO questions "
                    "(course_id, topic_id, source_chunk_id, type, payload, status, created_by) "
                    "VALUES (:c, :t, :ch, 'mcq', '{}'::jsonb, 'draft', :u)"
                ),
                {"c": course_id, "t": topic_id, "ch": chunks[0]["id"], "u": ayse_id},
            )

        response = await client.delete(
            f"/courses/{course_id}/documents/{document_id}", headers=ayse
        )

        assert response.status_code == 409, response.text
        assert response.json()["error"]["code"] == "conflict"
        assert "soru" in response.json()["error"]["message"].lower()

        # Reddedilen silme HİÇBİR ŞEYİ silmemiş olmalı: belge de dosyası da yerinde.
        # Depodaki dosya `flush()` başarılı olduktan SONRA siliniyor; sıra ters
        # olsaydı kayıt duran ama dosyası olmayan bir belge kalırdı.
        assert (
            await client.get(f"/courses/{course_id}/documents/{document_id}", headers=ayse)
        ).status_code == 200


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
        self, client: AsyncClient, users: UserFactory, admin_engine, monkeypatch
    ) -> None:
        """Depodaki dosya kaybolursa iş sessizce kaybolmaz; belge 'failed' olur.

        Arka plan tetiği burada BİLİNÇLİ olarak kapatılıyor: testin kurgusu
        "dosyayı sil, sonra işlet" sırasına dayanıyor ve tetik açıkken belge daha
        dosya silinmeden işlenip `completed` oluyor. Tetiğin kendisi başka bir
        testin konusu; burada sınanan, işlemenin başarısız olduğunda ne yazdığı.
        """
        from sqlalchemy import text as sql_text

        from app import worker
        from app.api import documents as documents_api
        from app.modules.ingestion.storage import get_storage

        async def tetikleme_yok() -> None:
            return None

        monkeypatch.setattr(documents_api, "_trigger_worker", tetikleme_yok)

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


class TestYazmaGorunurlugu:
    """Yanıt gönderildiği ANDA yazma kalıcı mı?

    Ölçülen kusur (lider şeridi, 9 Ağustos): `POST /documents` `202` dönüyor, hemen
    ardından yapılan `GET` sıfır belge görüyor, bir saniye sonraki `GET` bir belge
    görüyor. Arayüz bunu geçici bir tazeleme penceresiyle maskeliyordu.

    Sebep FastAPI'nin `yield` bağımlılıklarını varsayılan olarak yanıt gönderildikten
    SONRA kapatması; oturumun commit'i o kapanışta gerçekleşiyor. Düzeltme
    `deps.SessionDep`'in `scope="function"` ile tanımlanması.

    Bu testin ölçme biçimi önemlidir: normal bir test istemcisi ASGI çağrısının
    TAMAMI bittikten sonra döner, yani yarışı hiç göremez. Burada gövde mesajının
    gönderildiği anı yakalayıp, o anda AYRI BİR BAĞLANTIDAN satırın görünüp
    görünmediğine bakıyoruz — yalnız commit edilmiş veri başka bir bağlantıdan
    görülebildiği için bu, "istemcinin gördüğü yanıt kalıcı bir işlemi temsil
    ediyor mu" sorusunun doğrudan ölçümü.
    """

    async def test_yanit_gonderilirken_satir_baska_baglantidan_gorunur(
        self, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        from httpx import ASGITransport, AsyncClient

        from app.core.db import dispose_engine
        from app.main import create_app

        ayse_id = await users.create("ayse@dogus.edu.tr")
        ayse = UserFactory.auth(ayse_id)

        #: Gövde yazılırken dışarıdan sayılan belge adedi.
        gorulen: list[int] = []

        async def say() -> int:
            async with admin_engine.begin() as conn:
                result = await conn.execute(text("SELECT count(*) FROM documents"))
                return int(result.scalar_one())

        app = create_app()

        async def probe(scope: dict, receive: object, send: object) -> None:
            async def probing_send(message: dict) -> None:
                if message["type"] == "http.response.body" and not message.get("more_body"):
                    gorulen.append(await say())
                await send(message)  # type: ignore[operator]

            await app(scope, receive, probing_send)  # type: ignore[arg-type]

        transport = ASGITransport(app=probe)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            course_id = await _course(client, ayse, "COME301")
            gorulen.clear()
            response = await _upload(
                client, ayse, course_id, "hafta3.pdf", make_pdf(["Deadlock kosullari."])
            )
        await dispose_engine()

        assert response.status_code == 202, response.text
        assert gorulen == [1], (
            "202 istemciye yazılırken belge satırı henüz commit edilmemiş: "
            "istemcinin hemen yapacağı GET boş dönecek"
        )

    async def test_arka_plan_tetigi_belgeyi_gercekten_isler(
        self, client: AsyncClient, users: UserFactory
    ) -> None:
        """Yükleme yanıtından sonraki tetik işi BULUR ve işler.

        9 Ağustos'a kadar bulamıyordu: belge satırı yanıt gönderildikten sonra
        commit edildiği için tetik boş kuyruk görüp sessizce sıfır dönüyordu.
        Kusur görünmüyordu çünkü demo sırasında ayrı bir worker döngüsü
        (`python -m app.worker`) zaten koşuyor ve işi o alıyordu — yalnız API
        çalıştırıldığında hiçbir belge işlenmezdi.

        Bu test elle `drain()` ÇAĞIRMAZ; çağırsaydı tetiğin çalışıp çalışmadığını
        gizlerdi.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        course_id = await _course(client, ayse, "COME301")

        upload = await _upload(
            client, ayse, course_id, "tetik.pdf", make_pdf(["Deadlock kosullari."])
        )
        assert upload.status_code == 202, upload.text
        document_id = upload.json()["document"]["id"]

        detail = (
            await client.get(f"/courses/{course_id}/documents/{document_id}", headers=ayse)
        ).json()
        assert detail["status"] == "completed"
        assert detail["chunk_count"] >= 1
