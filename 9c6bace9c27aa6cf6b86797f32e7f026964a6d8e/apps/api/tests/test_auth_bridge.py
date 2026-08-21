"""`0002_supabase_auth_bridge.sql` davranış testleri (T023 backend ayağı).

Yerel PostgreSQL'de `auth` şeması YOKTUR — o Supabase'e aittir. Migration bu yüzden
trigger'ı koşullu kurar. Buradaki testler o koşulu sahte bir `auth.users` tablosu
yaratarak sağlar ve **migration'ın kendi kurulum fonksiyonunu** (`app.install_auth_user_bridge`)
çağırır; trigger'ı testin içinde yeniden yazmaz. Böylece sınanan şey üretimde koşacak
kodun aynısıdır.

Sahte tablo Supabase'in `auth.users` tablosundan yalnız köprünün okuduğu sütunları
taşır: `id`, `email`, `raw_user_meta_data` ve trigger'ın WHEN koşulunu sınamak için
`last_sign_in_at`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# Supabase'de `auth.users`'a yazan rol `supabase_auth_admin`'dir ve `app` şemasına da
# `public.profiles` tablosuna da yetkisi YOKTUR. Onu taklit eden yetkisiz rolün adı test
# veritabanından türetilir: rol adları küme genelindedir ve iki worktree aynı anda pytest
# koşarken sabit bir ad birbirini düşürürdü (conftest'in veritabanı adında çözdüğü sorunun
# aynısı).
_AUTH_ADMIN_ROLE_SQL = "SELECT 'ta_' || substr(md5(current_database()), 1, 12)"

# Supabase'in `auth.users` tablosunun köprüyü ilgilendiren kısmı.
_FAKE_AUTH_USERS = """
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (
    id                 uuid PRIMARY KEY,
    email              text,
    raw_user_meta_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_sign_in_at    timestamptz
);
GRANT USAGE ON SCHEMA auth TO dou_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON auth.users TO dou_app;
DO $$
DECLARE v_role text := 'ta_' || substr(md5(current_database()), 1, 12);
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_role) THEN
        EXECUTE format('CREATE ROLE %I NOLOGIN', v_role);
    END IF;
    EXECUTE format('GRANT USAGE ON SCHEMA auth TO %I', v_role);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON auth.users TO %I', v_role);
END $$;
"""

_DROP_FAKE_AUTH = """
DROP SCHEMA IF EXISTS auth CASCADE;
DO $$
DECLARE v_role text := 'ta_' || substr(md5(current_database()), 1, 12);
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = v_role) THEN
        EXECUTE format('DROP OWNED BY %I', v_role);
        EXECUTE format('DROP ROLE %I', v_role);
    END IF;
END $$;
"""


def _statements(script: str) -> list[str]:
    """Betiği `;` ile bölmeden çalıştırılabilir parçalara ayırır.

    `DO $$ ... $$` blokları noktalı virgül içerdiği için düz bölme onları parçalar;
    bloklar bütün hâlde tutulur.
    """
    parts: list[str] = []
    buffer = ""
    in_block = False
    for line in script.splitlines():
        buffer += line + "\n"
        if line.strip().startswith("DO $$"):
            in_block = True
        if in_block:
            if line.strip().startswith("END $$;"):
                in_block = False
                parts.append(buffer)
                buffer = ""
            continue
        if line.rstrip().endswith(";"):
            parts.append(buffer)
            buffer = ""
    return [p.strip() for p in parts if p.strip()]


@pytest.fixture
async def auth_schema(admin_engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    """Sahte `auth.users` tablosunu kurar; trigger'ı KURMAZ."""
    async with admin_engine.begin() as conn:
        for statement in _statements(_FAKE_AUTH_USERS):
            await conn.execute(text(statement))
        await conn.execute(text("TRUNCATE auth.users"))
    yield admin_engine
    async with admin_engine.begin() as conn:
        for statement in _statements(_DROP_FAKE_AUTH):
            await conn.execute(text(statement))


async def _install_bridge(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("SELECT app.install_auth_user_bridge()"))


async def _profile(engine: AsyncEngine, user_id: UUID) -> tuple[str, str | None] | None:
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT email, full_name FROM profiles WHERE id = :id"),
                {"id": user_id},
            )
        ).first()
    return None if row is None else (row.email, row.full_name)


async def _signup(
    engine: AsyncEngine,
    user_id: UUID,
    email: str | None,
    meta: str = "{}",
    *,
    as_role: str | None = None,
) -> None:
    """`auth.users`'a kayıt düşer — Supabase'de bir kullanıcının doğduğu an."""
    async with engine.begin() as conn:
        if as_role is not None:
            await conn.execute(text(f"SET LOCAL ROLE {as_role}"))
        await conn.execute(
            text(
                "INSERT INTO auth.users (id, email, raw_user_meta_data) "
                "VALUES (:id, :email, CAST(:meta AS jsonb))"
            ),
            {"id": user_id, "email": email, "meta": meta},
        )


class TestProfilOlusturma:
    async def test_auth_kullanicisi_profil_yaratir(self, auth_schema: AsyncEngine) -> None:
        await _install_bridge(auth_schema)
        user_id = uuid4()

        await _signup(auth_schema, user_id, "Elif@Dogus.Edu.Tr", '{"full_name": "Elif Yılmaz"}')

        assert await _profile(auth_schema, user_id) == ("elif@dogus.edu.tr", "Elif Yılmaz")

    async def test_eposta_kucuk_harfe_normalize_edilir(self, auth_schema: AsyncEngine) -> None:
        """`app.add_course_member` e-postayı `lower()` ile arıyor (0001).

        Köprü büyük harfli bir e-postayı olduğu gibi yazsaydı, eğitmen üye eklerken
        kullanıcıyı bulur ama `profiles.email` üzerindeki UNIQUE indeks büyük/küçük
        harf duyarlı olduğu için aynı kişi iki farklı satır olarak var olabilirdi.
        """
        await _install_bridge(auth_schema)
        user_id = uuid4()

        await _signup(auth_schema, user_id, "  BURAK@DOGUS.EDU.TR  ")

        profile = await _profile(auth_schema, user_id)
        assert profile is not None
        assert profile[0] == "burak@dogus.edu.tr"

    async def test_ad_meta_veriden_name_alanindan_da_okunur(self, auth_schema: AsyncEngine) -> None:
        """Supabase'in kendi konvansiyonu `full_name`; OAuth sağlayıcıları `name` yazar."""
        await _install_bridge(auth_schema)
        user_id = uuid4()

        await _signup(auth_schema, user_id, "ceren@dogus.edu.tr", '{"name": "Ceren Demir"}')

        assert await _profile(auth_schema, user_id) == ("ceren@dogus.edu.tr", "Ceren Demir")

    async def test_ayricaliksiz_rol_yazarken_de_profil_olusur(
        self, auth_schema: AsyncEngine
    ) -> None:
        """Köprünün RLS'i gerçekten atladığının kanıtı.

        `profiles` FORCE ROW LEVEL SECURITY taşır ve INSERT politikası yoktur. Trigger
        fonksiyonu `dou_auth_bridge` (BYPASSRLS) rolüne devredilmemiş olsaydı bu test
        "new row violates row-level security policy" ile düşerdi. Superuser bağlantısıyla
        yazılan bir test bunu ASLA yakalayamazdı: superuser RLS'i zaten atlar ve testin
        yeşil yanması köprü hakkında hiçbir şey söylemezdi.
        """
        await _install_bridge(auth_schema)
        user_id = uuid4()

        await _signup(
            auth_schema,
            user_id,
            "deniz@dogus.edu.tr",
            '{"full_name": "Deniz Ak"}',
            as_role="dou_app",
        )

        assert await _profile(auth_schema, user_id) == ("deniz@dogus.edu.tr", "Deniz Ak")

    async def test_app_semasina_yetkisiz_rol_de_tetikleyebilir(
        self, auth_schema: AsyncEngine
    ) -> None:
        """Üretimdeki gerçek çağıran: `supabase_auth_admin`.

        O rolün `app` şemasına USAGE'ı ve `profiles`'a INSERT'ü YOKTUR. Trigger yine de
        çalışmalıdır — fonksiyon SECURITY DEFINER olduğu ve trigger fonksiyonu adla değil
        OID ile bağladığı için. Bu testi yazmasaydık, köprünün Supabase'de çalışıp
        çalışmayacağı ancak gerçek bir proje üstünde denenerek görülebilirdi (İş 5).

        `dou_app` ile yazılan üstteki test bunu KANITLAMAZ: 0001 `dou_app`'e
        `GRANT USAGE ON SCHEMA app` veriyor.
        """
        await _install_bridge(auth_schema)
        user_id = uuid4()
        async with auth_schema.connect() as conn:
            role = await conn.scalar(text(_AUTH_ADMIN_ROLE_SQL))
            assert role is not None
            yetkili = await conn.scalar(
                text("SELECT has_schema_privilege(:r, 'app', 'USAGE')"), {"r": role}
            )
        assert yetkili is False, "taklit rol yanlışlıkla yetkilendirilmiş, test bir şey ölçmez"

        await _signup(
            auth_schema, user_id, "yetkisiz@dogus.edu.tr", '{"name": "Yetkisiz"}', as_role=role
        )

        assert await _profile(auth_schema, user_id) == ("yetkisiz@dogus.edu.tr", "Yetkisiz")

    async def test_mevcut_profil_varsa_hata_vermez(self, auth_schema: AsyncEngine) -> None:
        """Idempotency: profil zaten varsa (yerelde elle yaratılmış olabilir) güncellenir."""
        await _install_bridge(auth_schema)
        user_id = uuid4()
        async with auth_schema.begin() as conn:
            await conn.execute(
                text("INSERT INTO profiles (id, email, full_name) VALUES (:id, :email, :name)"),
                {"id": user_id, "email": "eski@dogus.edu.tr", "name": "Eski Ad"},
            )

        await _signup(auth_schema, user_id, "yeni@dogus.edu.tr", '{"full_name": "Yeni Ad"}')

        assert await _profile(auth_schema, user_id) == ("yeni@dogus.edu.tr", "Yeni Ad")


class TestSenkron:
    async def test_eposta_degisikligi_profile_yansir(self, auth_schema: AsyncEngine) -> None:
        await _install_bridge(auth_schema)
        user_id = uuid4()
        await _signup(auth_schema, user_id, "eski@dogus.edu.tr", '{"full_name": "Ali Vural"}')

        async with auth_schema.begin() as conn:
            await conn.execute(
                text("UPDATE auth.users SET email = :email WHERE id = :id"),
                {"email": "yeni@dogus.edu.tr", "id": user_id},
            )

        assert await _profile(auth_schema, user_id) == ("yeni@dogus.edu.tr", "Ali Vural")

    async def test_ad_bosalirsa_mevcut_ad_korunur(self, auth_schema: AsyncEngine) -> None:
        """Meta veri sadeleşirse ad SİLİNMEZ — `coalesce(excluded.full_name, ...)`."""
        await _install_bridge(auth_schema)
        user_id = uuid4()
        await _signup(auth_schema, user_id, "ali@dogus.edu.tr", '{"full_name": "Ali Vural"}')

        async with auth_schema.begin() as conn:
            await conn.execute(
                text("UPDATE auth.users SET raw_user_meta_data = '{}'::jsonb WHERE id = :id"),
                {"id": user_id},
            )

        assert await _profile(auth_schema, user_id) == ("ali@dogus.edu.tr", "Ali Vural")

    async def test_giris_zamani_guncellemesi_profili_degistirmez(
        self, auth_schema: AsyncEngine
    ) -> None:
        """Trigger'ın WHEN koşulunun kanıtı.

        `auth.users` her girişte güncellenir. Koşulsuz bir AFTER UPDATE trigger'ı, her
        girişte `profiles` satırına gereksiz bir UPDATE yazar ve kullanıcının elle
        düzelttiği adı meta veriden gelen eski değere geri döndürürdü. Aşağıdaki
        senaryo tam olarak bunu ölçer: profil adı elle değiştirilir, sonra yalnız
        `last_sign_in_at` güncellenir.
        """
        await _install_bridge(auth_schema)
        user_id = uuid4()
        await _signup(auth_schema, user_id, "elif@dogus.edu.tr", '{"full_name": "Meta Ad"}')
        async with auth_schema.begin() as conn:
            await conn.execute(
                text("UPDATE profiles SET full_name = 'Elle Düzeltilmiş' WHERE id = :id"),
                {"id": user_id},
            )

        async with auth_schema.begin() as conn:
            await conn.execute(
                text("UPDATE auth.users SET last_sign_in_at = now() WHERE id = :id"),
                {"id": user_id},
            )

        assert await _profile(auth_schema, user_id) == ("elif@dogus.edu.tr", "Elle Düzeltilmiş")


class TestSilme:
    async def test_auth_kullanicisi_silinince_profil_kalir(self, auth_schema: AsyncEngine) -> None:
        """KARAR 2 (migration yorumu): akademik kayıt kullanıcı silinince yok olmaz.

        Cascade kurulsaydı Supabase panelinden bir kullanıcı silmek, o kullanıcının
        yüklediği belgeleri, sohbet geçmişini ve ölçüm kayıtlarını da götürürdü.
        """
        await _install_bridge(auth_schema)
        user_id = uuid4()
        await _signup(auth_schema, user_id, "silinen@dogus.edu.tr", '{"full_name": "Silinen"}')

        async with auth_schema.begin() as conn:
            await conn.execute(text("DELETE FROM auth.users WHERE id = :id"), {"id": user_id})

        assert await _profile(auth_schema, user_id) == ("silinen@dogus.edu.tr", "Silinen")


class TestFailClosed:
    async def test_ayni_eposta_ikinci_kimlige_baglanmaz(self, auth_schema: AsyncEngine) -> None:
        """Silinen kullanıcı aynı e-postayla yeniden kaydolursa kayıt DÜŞER.

        Bu, KARAR 2'nin kabul edilen bedelidir ve sessizce çözülmez: yeni kimliği eski
        akademik kayda bağlamak da eski kaydı ezmek de veri bütünlüğünü bozardı
        (Anayasa IV). Operatör kararı gerekir; docs/security.md'de yazılı.
        """
        await _install_bridge(auth_schema)
        await _signup(auth_schema, uuid4(), "ortak@dogus.edu.tr")

        with pytest.raises(Exception, match="başka bir profile bağlı"):
            await _signup(auth_schema, uuid4(), "ortak@dogus.edu.tr")

    async def test_epostasiz_kayit_reddedilir(self, auth_schema: AsyncEngine) -> None:
        """Telefonla kayıt: e-postasız kullanıcı hiçbir derse eklenemez, en baştan durur."""
        await _install_bridge(auth_schema)

        with pytest.raises(Exception, match="e-posta yok"):
            await _signup(auth_schema, uuid4(), None)

    async def test_kopru_kurulmadan_trigger_yoktur(self, auth_schema: AsyncEngine) -> None:
        """Fonksiyonlar her ortamda var, trigger yalnız kurulduğunda.

        Yerel kurulumun gerçek hâli budur: migration koşmuştur, `auth` şeması yoktur,
        dolayısıyla trigger da yoktur ve profil satırları uygulama tarafından yazılır.
        """
        async with auth_schema.connect() as conn:
            count = await conn.scalar(
                text("SELECT count(*) FROM pg_trigger WHERE tgname = 'on_auth_user_created'")
            )
        assert count == 0


class TestBackfill:
    async def test_kopru_oncesi_kullanicilar_doldurulur(self, auth_schema: AsyncEngine) -> None:
        """Migration gerçek bir Supabase projesine ilk kez uygulandığında `auth.users`
        genellikle DOLUDUR. Trigger yalnız yeni kayıtlar için çalışır; mevcut kullanıcılar
        backfill olmadan profilsiz kalır ve sisteme giremezdi.
        """
        eski = uuid4()
        async with auth_schema.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO auth.users (id, email, raw_user_meta_data) "
                    'VALUES (:id, :email, \'{"full_name": "Eski Kullanıcı"}\'::jsonb)'
                ),
                {"id": eski, "email": "eski.kullanici@dogus.edu.tr"},
            )
        assert await _profile(auth_schema, eski) is None

        await _install_bridge(auth_schema)
        async with auth_schema.begin() as conn:
            row = (
                await conn.execute(text("SELECT * FROM app.backfill_profiles_from_auth()"))
            ).one()

        assert (row.inserted, row.skipped) == (1, 0)
        assert await _profile(auth_schema, eski) == (
            "eski.kullanici@dogus.edu.tr",
            "Eski Kullanıcı",
        )

    async def test_cakisan_eposta_atlanir_migration_dusmez(self, auth_schema: AsyncEngine) -> None:
        """Tek bir çakışma migration'ın tamamını düşürmemeli: kalan kullanıcılar girer,
        atlanan sayısı operatöre bildirilir.
        """
        cakisan, temiz = uuid4(), uuid4()
        async with auth_schema.begin() as conn:
            await conn.execute(
                text("INSERT INTO profiles (id, email) VALUES (:id, :email)"),
                {"id": uuid4(), "email": "cakisan@dogus.edu.tr"},
            )
            await conn.execute(
                text("INSERT INTO auth.users (id, email) VALUES (:a, :ae), (:b, :be)"),
                {
                    "a": cakisan,
                    "ae": "cakisan@dogus.edu.tr",
                    "b": temiz,
                    "be": "temiz@dogus.edu.tr",
                },
            )

        async with auth_schema.begin() as conn:
            row = (
                await conn.execute(text("SELECT * FROM app.backfill_profiles_from_auth()"))
            ).one()

        assert (row.inserted, row.skipped) == (1, 1)
        assert await _profile(auth_schema, cakisan) is None
        assert await _profile(auth_schema, temiz) is not None
