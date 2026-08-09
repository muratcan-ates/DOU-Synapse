-- DOU-Synapse — Supabase Auth köprüsü (T023 backend ayağı)
--
-- 0001 şemayı kurarken `profiles` tablosunu bilinçli olarak `auth.users`'a BAĞLAMADI
-- (bkz. 0001_core_schema.sql, "Kullanıcılar" bölümünün yorumu): o gün Supabase Auth
-- devrede değildi ve `auth` şemasına verilen bir foreign key, şemayı yerelde
-- kurulamaz hâle getirirdi. Bu migration o köprüyü kurar: Supabase Auth bir kullanıcı
-- yarattığında `public.profiles` satırı otomatik oluşur.
--
-- ---------------------------------------------------------------------------
-- KARAR 1 — Neden koşullu kurulum (`auth` şeması varsa)
-- ---------------------------------------------------------------------------
-- `auth.users` Supabase'in şemasıdır; yerel PostgreSQL'de YOKTUR. Bu dosyanın yerelde
-- de hatasız koşması pazarlık dışı, çünkü migration klasörü ÜÇ ayrı yerde tek başına,
-- sırayla uygulanıyor ve hiçbirinde `local_dev_setup.sql` çalışmıyor:
--
--   1. apps/api/tests/conftest.py :: database fixture  (her pytest oturumu)
--   2. .github/workflows/ci.yml   :: "RLS izolasyon kanıtı" adımı (rls_check veritabanı)
--   3. specs/.../quickstart.md    :: kurulum adımları
--
-- Bu yüzden 11_R1_KIMLIK.md'deki iki seçenekten BİRİNCİSİ seçildi. İkinci seçenek
-- (yerel için `local_dev_setup.sql`'e sahte bir `auth.users` kurup migration'ı koşulsuz
-- yazmak) yukarıdaki üç yolun üçünü de kırardı: o dosya migration'lardan sonra ve
-- yalnızca elle çalıştırılıyor, dolayısıyla `for f in supabase/migrations/*.sql`
-- döngüsü "auth.users yok" hatasıyla düşerdi.
--
-- Koşullu kurulumun bedeli: yerelde köprü kurulmaz, yani kendini test etmez. Bu bedel
-- fonksiyonları trigger'dan AYIRARAK ödeniyor — `app.sync_profile_from_auth_user()` ve
-- `app.install_auth_user_bridge()` her ortamda koşulsuz oluşur, aşağıdaki DO bloğu
-- yalnız trigger kurulumunu koşula bağlar. Testler (apps/api/tests/test_auth_bridge.py)
-- sahte bir `auth.users` yaratıp `app.install_auth_user_bridge()` çağırır; yani ÜRETİMDE
-- KOŞACAK KODUN AYNISI sınanır, testin kendi kopyası değil.
--
-- ---------------------------------------------------------------------------
-- KARAR 2 — Silme davranışı: auth.users silinince profil KALIR
-- ---------------------------------------------------------------------------
-- `ON DELETE CASCADE` bilinçli olarak KURULMADI ve DELETE trigger'ı da yazılmadı.
-- Gerekçe: `documents.uploaded_by`, `chat_messages` (oturum üzerinden), `answers`,
-- `mastery` ve `request_logs` profile bağlıdır. Cascade kurulsaydı Supabase panelinden
-- bir kullanıcıyı silmek, o kullanıcının akademik kaydını ve dersin ölçüm geçmişini de
-- sessizce silerdi — geri alınamaz ve fark edilmesi zor bir veri kaybı. `courses.created_by`
-- ve `documents.uploaded_by` zaten `ON DELETE RESTRICT` taşıyor: proje "akademik kayıt
-- korunur" tarafını daha 0001'de seçmişti, bu migration o kararla tutarlı kalıyor.
--
-- KABUL EDİLEN SONUÇ (dürüstlük notu, Anayasa III): `auth.users`'tan silinen bir kullanıcı
-- aynı e-postayla yeniden kaydolursa yeni bir `auth.users.id` alır, eski profil satırı ise
-- o e-postayı hâlâ tutuyordur. `profiles.email` UNIQUE olduğu için köprü bu kaydı
-- REDDEDER (aşağıdaki e-posta çakışması kontrolü) ve kayıt işlemi hata verir. Bu, sessizce
-- yanlış şeyi yapmaya (yeni kimliği eski akademik kayda bağlamak ya da eski kaydı ezmek)
-- tercih edilmiştir (Anayasa IV). Çözüm operatörün bilinçli kararıdır: ya eski profil
-- silinir ya da e-postası arşiv değerine çevrilir. docs/security.md'de yazılıdır.
--
-- ---------------------------------------------------------------------------
-- KARAR 3 — Neden ayrı bir `dou_auth_bridge` rolü
-- ---------------------------------------------------------------------------
-- `profiles` tablosu 0001'de `FORCE ROW LEVEL SECURITY` ile işaretli ve tabloda INSERT
-- politikası YOK (kullanıcı kendi profilini yaratamaz — profil yalnız kimlik
-- sağlayıcısından doğar). FORCE, tablo sahibini de politikalara tabi kılar; dolayısıyla
-- `SECURITY DEFINER` olmak tek başına yetmez, definer rolünün RLS'i atlaması gerekir.
--
-- Bunu "migration'ı koşturan rol nasılsa ayrıcalıklıdır" varsayımına bırakmak, üretimde
-- ancak gerçek bir kayıt denemesiyle görülebilecek bir kusur üretirdi. Bu yüzden köprü
-- fonksiyonu, 0001'deki `dou_worker` desenini izleyen NOLOGIN + BYPASSRLS bir role
-- devredilir. Rol asla giriş yapmaz; tek işlevi bu fonksiyonun sahibi olmaktır ve
-- yalnız `profiles` üzerinde yetkilidir.

BEGIN;

-- ---------------------------------------------------------------------------
-- Köprü rolü
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dou_auth_bridge') THEN
        CREATE ROLE dou_auth_bridge NOLOGIN BYPASSRLS;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public, app TO dou_auth_bridge;
GRANT SELECT, INSERT, UPDATE ON public.profiles TO dou_auth_bridge;

-- ---------------------------------------------------------------------------
-- Profil yazımı — köprünün TEK yazma noktası
-- ---------------------------------------------------------------------------

-- Trigger da backfill de buradan geçer. Ayrı ayrı yazılsalardı normalizasyon kuralı
-- (küçük harf, ad alanının iki olası adı, boş e-posta reddi) iki yerde yaşar ve zamanla
-- ayrışırdı (Anayasa XI). Ayrıca ayrıcalık yalnızca burada toplanır: `auth.users`'ı
-- OKUMAK çağıranın işidir, `profiles`'a YAZMAK bu fonksiyonun.
CREATE OR REPLACE FUNCTION app.upsert_profile_from_auth(
    p_id    uuid,
    p_email text,
    p_meta  jsonb
) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, app AS $fn$
DECLARE
    v_email     text;
    v_full_name text;
    v_owner     uuid;
BEGIN
    -- Supabase telefonla kayıtta `email`'i NULL bırakabilir; meta veride bulunursa oradan
    -- alınır. Hiç yoksa profil YARATILMAZ ve kayıt işlemi düşer: e-postasız bir profil
    -- `profiles.email NOT NULL` yüzünden zaten yazılamaz, ayrıca derse üye ekleme
    -- (app.add_course_member) e-postayla çalışır — e-postasız kullanıcı sisteme
    -- alınabilseydi hiçbir derse eklenemeyen, sebebi görünmeyen bir hesap olurdu.
    v_email := lower(btrim(coalesce(p_email, p_meta ->> 'email', '')));
    IF v_email = '' THEN
        RAISE EXCEPTION 'auth.users kaydında e-posta yok, profil oluşturulamaz (id=%)', p_id
            USING ERRCODE = 'not_null_violation';
    END IF;

    -- Supabase'in kendi konvansiyonu `full_name`; bazı OAuth sağlayıcıları `name` yazar.
    v_full_name := nullif(btrim(coalesce(
        p_meta ->> 'full_name',
        p_meta ->> 'name',
        ''
    )), '');

    -- E-posta başka bir kimliğe bağlıysa DUR (KARAR 2). `ON CONFLICT (id)` bu durumu
    -- yakalamaz: çakışma birincil anahtarda değil, e-posta üzerindeki UNIQUE indekstedir.
    -- Kontrol açıkça yazılıyor ki hata mesajı "duplicate key value violates unique
    -- constraint" değil, ne olduğunu anlatan bir cümle olsun.
    SELECT p.id INTO v_owner FROM public.profiles p WHERE lower(p.email) = v_email;
    IF v_owner IS NOT NULL AND v_owner <> p_id THEN
        RAISE EXCEPTION
            'bu e-posta zaten başka bir profile bağlı (e-posta=%, mevcut profil=%)',
            v_email, v_owner
            USING ERRCODE = 'unique_violation';
    END IF;

    -- Idempotent: aynı kullanıcı için ikinci kez koşarsa hata vermez, günceller.
    -- `full_name`'de coalesce kullanılır çünkü sağlayıcı adı sonradan boş gönderirse
    -- (ör. e-posta doğrulama sonrası meta verinin sadeleşmesi) mevcut adı silmemelidir.
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (p_id, v_email, v_full_name)
    ON CONFLICT (id) DO UPDATE
        SET email     = excluded.email,
            full_name = coalesce(excluded.full_name, profiles.full_name);
END
$fn$;

ALTER FUNCTION app.upsert_profile_from_auth(uuid, text, jsonb) OWNER TO dou_auth_bridge;

COMMENT ON FUNCTION app.upsert_profile_from_auth(uuid, text, jsonb) IS
    'Kimlik sağlayıcısından gelen kullanıcıyı public.profiles ile eşitler. '
    'SECURITY DEFINER + BYPASSRLS sahibi: profiles FORCE RLS taşır ve INSERT politikası yoktur.';

-- ---------------------------------------------------------------------------
-- Trigger gövdesi
-- ---------------------------------------------------------------------------

-- plpgsql gövdesi CREATE anında yalnız sözdizimi açısından denetlenir ve burada
-- `auth.users`'a hiç dokunulmaz (yalnız NEW kaydı okunur); fonksiyon bu yüzden `auth`
-- şeması olmayan yerel kurulumda da sorunsuz oluşur.
--
-- SECURITY DEFINER: `auth.users`'a yazan rol (Supabase'de `supabase_auth_admin`) `app`
-- şemasına ve `profiles` tablosuna yetkili değildir. Ayrıcalık yine tek noktada —
-- bu fonksiyon yalnız NEW'i ayrıştırıp yazma fonksiyonunu çağırır.
CREATE OR REPLACE FUNCTION app.sync_profile_from_auth_user() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, app AS $fn$
BEGIN
    PERFORM app.upsert_profile_from_auth(NEW.id, NEW.email, NEW.raw_user_meta_data);
    RETURN NEW;
END
$fn$;

ALTER FUNCTION app.sync_profile_from_auth_user() OWNER TO dou_auth_bridge;

COMMENT ON FUNCTION app.sync_profile_from_auth_user() IS
    'auth.users üzerindeki INSERT/UPDATE trigger gövdesi.';

-- ---------------------------------------------------------------------------
-- Trigger kurulumu (yalnız auth.users varken)
-- ---------------------------------------------------------------------------

-- Trigger'lar `EXECUTE` ile kuruluyor: plpgsql, gövdesindeki DDL'i doğrudan yazdığımızda
-- utility deyimi olarak geçirir ve `WHEN (OLD... NEW...)` ifadesinin plpgsql değişkeni mi
-- SQL tanımlayıcısı mı olduğu okuyucu için belirsizleşir. Metin olarak koşturmak bu
-- belirsizliği tamamen kaldırır.
CREATE OR REPLACE FUNCTION app.install_auth_user_bridge() RETURNS void
LANGUAGE plpgsql AS $fn$
BEGIN
    IF to_regclass('auth.users') IS NULL THEN
        RAISE EXCEPTION 'auth.users bulunamadı; köprü kurulamaz'
            USING ERRCODE = 'undefined_table';
    END IF;

    EXECUTE 'DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users';
    EXECUTE $trg$
        CREATE TRIGGER on_auth_user_created
            AFTER INSERT ON auth.users
            FOR EACH ROW EXECUTE FUNCTION app.sync_profile_from_auth_user()
    $trg$;

    -- E-posta ya da ad değişikliği profile yansımalıdır; aksi hâlde eğitmenin üye
    -- listesinde gördüğü e-posta ile kullanıcının giriş yaptığı e-posta zamanla ayrışır.
    -- WHEN koşulu şart: `auth.users` her girişte (last_sign_in_at) güncelleniyor ve
    -- koşulsuz bir trigger her girişte profiles'a gereksiz bir UPDATE yazardı.
    EXECUTE 'DROP TRIGGER IF EXISTS on_auth_user_updated ON auth.users';
    EXECUTE $trg$
        CREATE TRIGGER on_auth_user_updated
            AFTER UPDATE ON auth.users
            FOR EACH ROW
            WHEN (OLD.email IS DISTINCT FROM NEW.email
                  OR OLD.raw_user_meta_data IS DISTINCT FROM NEW.raw_user_meta_data)
            EXECUTE FUNCTION app.sync_profile_from_auth_user()
    $trg$;
END
$fn$;

-- Köprü kurulmadan ÖNCE var olan kullanıcıların profili yoktur; trigger yalnız yeni
-- kayıtlar için çalışır. Bu fonksiyon onları doldurur.
--
-- SECURITY INVOKER'dır ve bu bilinçlidir: `auth.users`'ı okumak çağıranın yetkisiyle
-- olur. Fonksiyon DEFINER yapılıp `dou_auth_bridge`'e devredilseydi o rolün `auth`
-- şemasına da yetkilendirilmesi gerekirdi — köprü rolünün yetkisi `profiles` ile sınırlı
-- kalsın diye tercih edilmedi. (Bu tasarım testte ölçüldü: DEFINER hâli
-- "permission denied for schema auth" veriyordu.) Yazma kısmı yine ayrıcalıklı
-- `app.upsert_profile_from_auth` üzerinden geçer.
--
-- Çakışan kayıtlar ATLANIR ve sayısı bildirilir: tek bir çakışma yüzünden migration'ın
-- tamamını düşürmek, kurulumu onarılamaz hâle getirirdi. Atlanan kullanıcı sisteme
-- giremez ve bunu operatör NOTICE'ten görür.
CREATE OR REPLACE FUNCTION app.backfill_profiles_from_auth(OUT inserted integer,
                                                           OUT skipped integer)
LANGUAGE plpgsql SECURITY INVOKER SET search_path = public, app AS $fn$
DECLARE
    r record;
BEGIN
    inserted := 0;
    skipped  := 0;

    IF to_regclass('auth.users') IS NULL THEN
        RETURN;
    END IF;

    FOR r IN EXECUTE $q$
        SELECT u.id, u.email, u.raw_user_meta_data AS meta
        FROM auth.users u
        WHERE NOT EXISTS (SELECT 1 FROM public.profiles p WHERE p.id = u.id)
    $q$
    LOOP
        BEGIN
            PERFORM app.upsert_profile_from_auth(r.id, r.email, r.meta);
            inserted := inserted + 1;
        EXCEPTION
            -- Yazma fonksiyonunun reddettiği iki durum: e-postasız kayıt ve başka bir
            -- profile bağlı e-posta. İkisi de operatör kararı ister, migration'ı düşürmez.
            WHEN unique_violation OR not_null_violation THEN
                skipped := skipped + 1;
                RAISE NOTICE '0002 backfill: atlandı (auth.users.id=%): %', r.id, SQLERRM;
        END;
    END LOOP;
END
$fn$;

DO $$
DECLARE
    v_inserted integer;
    v_skipped  integer;
BEGIN
    IF to_regclass('auth.users') IS NULL THEN
        RAISE NOTICE
            '0002: auth şeması yok (yerel kurulum). Köprü fonksiyonları hazır, '
            'trigger kurulmadı. Supabase üstünde bu migration trigger''ları kurar.';
        RETURN;
    END IF;

    PERFORM app.install_auth_user_bridge();
    SELECT * INTO v_inserted, v_skipped FROM app.backfill_profiles_from_auth();
    RAISE NOTICE '0002: auth.users köprüsü kuruldu (backfill: % eklendi, % atlandı)',
        v_inserted, v_skipped;
END
$$;

COMMIT;
