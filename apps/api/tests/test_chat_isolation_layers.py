"""Sohbet OKUMA yolunda iki katmanlı izolasyonun ayrı ayrı sınanması.

`test_isolation_layers.py` aynı soruyu ders üyeliği için soruyor: RLS kapalıyken
uygulama katmanı tek başına tutuyor mu? Bu dosya soruyu sohbet oturumunun
SAHİPLİĞİ için sorar, çünkü orada cevap uzun süre "hayır"dı.

`deps.py` ve `exams.py:160` doktrini yazılı ilan ediyor: *"RLS başka dersin kaydını
zaten gizler; yine de ders eşleşmesi açıkça kontrol edilir — iki katman da bağımsız
olarak doğru davranmalı."* Sınav, gizlilik ve geri bildirim yolları bunu gerçekten
yapıyor; `exams.py` oturumu yüklerken `course_id` YANINDA `user_id` de karşılaştırıyor.

Sohbet okuma yolu ise yalnız `course_id` bakıyordu. Yani aynı dersteki ikinci bir
öğrenci için tek savunma RLS'ti (`chat_sessions_self_read`, 0003_chat.sql:171).
O politika bilinçli ve sıkı — eğitmen istisnası bile yok, çünkü öğrencinin çekindiği
soruyu sorabilmesi ürünün gerekçelerinden biri. Ama tek katman, doktrinin reddettiği
şeydir: politika bir gün gevşerse ya da bir uç `dou_worker` bağlantısı kullanırsa
uygulama katmanında onu tutacak hiçbir şey yoktu.

Yöntem `test_isolation_layers.py` ile aynı: API bağlantısı BYPASSRLS taşıyan
`dou_worker` rolüne çevrilir, veritabanı hiçbir satırı gizlemez, kalan tek savunma
uygulama kodudur.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.conftest import ADMIN_DSN, UserFactory
from tests.factories import create_course, enroll_student


@pytest.fixture
async def rls_kapali() -> AsyncIterator[None]:
    """API bağlantısını RLS'i atlayan role çevirir — ikinci katman tamamen kapalı.

    `test_isolation_layers.py` bunu `dou_worker` (BYPASSRLS) ile yapıyor; sohbet
    uçları için O ROL YETMİYOR ve sebebi ölçüldü: sohbet okuma yolu
    `UnlockedCourseMemberDep`'ten geçiyor, o da `app.own_exam_duration()` çağırıyor
    ve `dou_worker`'ın bu fonksiyonda EXECUTE yetkisi yok — istek iddiaya varmadan
    `InsufficientPrivilege` ile düşüyor. Yetkiyi göçe eklemek testi kolaylaştırmak
    için üretim rolünü genişletmek olurdu; yapılmadı.

    Onun yerine yerel süper kullanıcı (`ADMIN_DSN`) kullanılıyor: süper kullanıcı
    RLS'i tamamen atlar ve her fonksiyonu çalıştırabilir, yani deneyin istediği
    "veritabanı hiçbir şey gizlemiyor" koşulunu tam olarak kurar.
    """
    from app.core.config import get_settings
    from app.core.db import dispose_engine

    onceki = os.environ["DATABASE_URL"]
    os.environ["DATABASE_URL"] = ADMIN_DSN
    get_settings.cache_clear()
    await dispose_engine()
    try:
        yield
    finally:
        os.environ["DATABASE_URL"] = onceki
        get_settings.cache_clear()
        await dispose_engine()


async def _yabanci_oturum_ek(admin_engine: AsyncEngine, *, course_id: UUID, user_id: UUID) -> UUID:
    """Başka öğrenciye ait, mesajı olan bir sohbet oturumunu doğrudan yazar.

    Uçtan değil admin bağlantısından yazılıyor: `POST /chat` üretim hattını
    çalıştırır ve bu testin sorusu üretimle ilgili değil, okuma yetkisiyle.
    """
    session_id = uuid4()
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO chat_sessions (id, course_id, user_id, mode, title) "
                "VALUES (:id, :course_id, :user_id, 'qa', :title)"
            ),
            {
                "id": session_id,
                "course_id": course_id,
                "user_id": user_id,
                "title": "Çekindiğim soru",
            },
        )
        await conn.execute(
            text(
                "INSERT INTO chat_messages "
                "(id, session_id, course_id, role, content, citations, status, seq) "
                # `chat_messages_status_by_role` (0003_chat.sql:92): kullanıcı
                # mesajının `status`'u NULL olmak ZORUNDA; durum yalnız asistan
                # mesajına aittir.
                "VALUES (:id, :session_id, :course_id, 'user', :content, "
                "CAST('[]' AS jsonb), NULL, 1)"
            ),
            {
                "id": uuid4(),
                "session_id": session_id,
                "course_id": course_id,
                "content": "Bunu sormaya utanıyorum ama semafor tam olarak ne?",
            },
        )
    return session_id


class TestSohbetSahipligiKatmanlari:
    async def test_rls_acikken_ikinci_ogrenci_yabanci_oturumu_goremez(
        self, client: AsyncClient, users: UserFactory, admin_engine: AsyncEngine
    ) -> None:
        """Karşı kontrol: normal konfigürasyonda RLS zaten gizliyor.

        Bu iddia olmadan aşağıdaki testlerin "RLS gerçekten kapalıydı" varsayımı
        doğrulanmamış kalır.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        ceren_id = await users.create("ceren@dogus.edu.tr")
        ceren = users.auth(ceren_id)
        course_id = await create_course(client, ayse, "COME302")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")
        await enroll_student(client, ayse, course_id, "ceren@dogus.edu.tr")
        yabanci = await _yabanci_oturum_ek(admin_engine, course_id=course_id, user_id=burak_id)

        liste = await client.get(f"/courses/{course_id}/chat/sessions", headers=ceren)
        assert liste.status_code == 200, liste.text
        assert liste.json()["items"] == []

        tek = await client.get(f"/courses/{course_id}/chat/sessions/{yabanci}", headers=ceren)
        assert tek.status_code == 404, tek.text

    async def test_rls_kapaliyken_veritabani_gercekten_sizdiriyor(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        rls_kapali: None,
    ) -> None:
        """Deneyin kurulum kontrolü: bu konfigürasyonda politikalar gerçekten inert.

        Bu test KIRMIZI olursa aşağıdaki iddialar yanlış sebeple yeşil yanıyor
        demektir — RLS hâlâ açıksa "uygulama katmanı tuttu" sonucu çıkarılamaz.
        """
        from app.core.db import rls_session

        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        ceren_id = await users.create("ceren@dogus.edu.tr")
        course_id = await create_course(client, ayse, "COME302")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")
        await enroll_student(client, ayse, course_id, "ceren@dogus.edu.tr")
        await _yabanci_oturum_ek(admin_engine, course_id=course_id, user_id=burak_id)

        async with rls_session(ceren_id) as session:
            gorunen = int((await session.scalar(text("SELECT count(*) FROM chat_sessions"))) or 0)

        assert gorunen == 1, "RLS hâlâ gizliyor; bu konfigürasyonda deney kurulmamış"

    async def test_rls_kapaliyken_liste_yabanci_oturumu_sizdirmaz(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        rls_kapali: None,
    ) -> None:
        """Asıl iddia: veritabanı hiçbir şey gizlemezken liste yine boş dönmeli.

        Ceren derse GERÇEKTEN üye, yani `require_course_member` onu durdurmaz.
        Durduracak tek şey sorgunun kendi sahiplik süzgecidir.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        ceren = users.auth(await users.create("ceren@dogus.edu.tr"))
        course_id = await create_course(client, ayse, "COME302")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")
        await enroll_student(client, ayse, course_id, "ceren@dogus.edu.tr")
        await _yabanci_oturum_ek(admin_engine, course_id=course_id, user_id=burak_id)

        liste = await client.get(f"/courses/{course_id}/chat/sessions", headers=ceren)

        assert liste.status_code == 200, liste.text
        assert liste.json()["items"] == [], "Başka öğrencinin sohbet oturumu listelendi"

    async def test_rls_kapaliyken_yabanci_oturumun_mesajlari_okunamaz(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        rls_kapali: None,
    ) -> None:
        """Kimliği bilinen yabancı oturum doğrudan istendiğinde de 404.

        Kayıt hiç yokken de başkasınınken de AYNI 404 döner: yabancı oturumun
        varlığı sızdırılmaz (`deps.py` aynı kuralı ders kayıtları için koyuyor).
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        ceren = users.auth(await users.create("ceren@dogus.edu.tr"))
        course_id = await create_course(client, ayse, "COME302")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")
        await enroll_student(client, ayse, course_id, "ceren@dogus.edu.tr")
        yabanci = await _yabanci_oturum_ek(admin_engine, course_id=course_id, user_id=burak_id)

        mevcut = await client.get(f"/courses/{course_id}/chat/sessions/{yabanci}", headers=ceren)
        olmayan = await client.get(f"/courses/{course_id}/chat/sessions/{uuid4()}", headers=ceren)

        assert mevcut.status_code == 404, mevcut.text
        assert olmayan.status_code == 404, olmayan.text

        # `request_id` istek başına benzersiz ve öyle olmalı; sızıntı garantisi
        # hata kodunun ve metninin ayırt edilemez olmasıdır.
        def govde(response: object) -> tuple[str, str]:
            hata = response.json()["error"]  # type: ignore[attr-defined]
            return hata["code"], hata["message"]

        assert govde(mevcut) == govde(olmayan), "Yabancı oturumun varlığı sızdırıldı"

    async def test_rls_kapaliyken_yabanci_oturuma_mesaj_yazilamaz(
        self,
        client: AsyncClient,
        users: UserFactory,
        admin_engine: AsyncEngine,
        rls_kapali: None,
    ) -> None:
        """Yazma yolu: başkasının oturumuna `session_id` vererek mesaj eklenemez.

        `_load_or_create_session` yeni oturumu `user_id=context.user_id` ile açıyor
        ama var olana bağlanırken sahipliği kontrol etmiyordu. 404 üretim hattından
        ÖNCE döndüğü için bu test model çağırmıyor.
        """
        ayse = users.auth(await users.create("ayse@dogus.edu.tr"))
        burak_id = await users.create("burak@dogus.edu.tr")
        ceren = users.auth(await users.create("ceren@dogus.edu.tr"))
        course_id = await create_course(client, ayse, "COME302")
        await enroll_student(client, ayse, course_id, "burak@dogus.edu.tr")
        await enroll_student(client, ayse, course_id, "ceren@dogus.edu.tr")
        yabanci = await _yabanci_oturum_ek(admin_engine, course_id=course_id, user_id=burak_id)

        response = await client.post(
            f"/courses/{course_id}/chat",
            json={"question": "Semafor nedir?", "mode": "qa", "session_id": str(yabanci)},
            headers=ceren,
        )

        assert response.status_code == 404, response.text
