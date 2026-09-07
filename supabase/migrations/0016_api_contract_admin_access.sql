-- 0016 — API sözleşmesi (`GET /openapi.json`) yönetici erişim kaydına eklenir.
--
-- `/openapi.json` artık platform yöneticisi kapısının arkasında: şema ürünün
-- tüm yüzeyini (uçlar, alanlar, hata kodları) tek dosyada anlatır ve dışarıya
-- açık bırakmak saldırı yüzeyini haritalamayı kolaylaştırır.
--
-- Kapı `app.audit_platform_admin_access` ile denetlenir; o fonksiyon eylem
-- adını BEYAZ LİSTEYLE doğrular (rastgele dize audit tablosuna yazılamasın
-- diye). Yeni yüzey listeye eklenmezse kapı, yetkili yöneticide bile hata
-- verir. Aşağıdaki gövde 0014'teki fonksiyonun BİREBİR kopyasıdır; tek fark
-- listeye eklenen satırdır — istek kimliği doğrulaması, audit yazımı ve
-- yetki kontrolü aynen korunur.

CREATE OR REPLACE FUNCTION app.audit_platform_admin_access(
    p_action text,
    p_request_id text
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog, public, app AS $$
DECLARE
    v_actor uuid := app.current_user_id();
    v_allowed boolean;
BEGIN
    IF v_actor IS NULL THEN
        RAISE EXCEPTION 'kimlik bağlamı yok'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF p_action IS NULL OR p_action NOT IN (
        'GET /admin/overview',
        'POST /admin/users',
        'GET /admin/courses',
        'GET /admin/requests',
        'GET /admin/ingestion',
        -- 20 Ağustos 2026: API sözleşmesi yüzeyi (`/openapi.json`).
        'GET /openapi.json'
    ) THEN
        RAISE EXCEPTION 'geçersiz admin eylemi'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    IF p_request_id IS NULL OR p_request_id !~ '^[A-Za-z0-9_-]{1,128}$' THEN
        RAISE EXCEPTION 'geçersiz istek kimliği'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    v_allowed := app.is_platform_admin();
    INSERT INTO public.platform_admin_access_audit (
        actor_user_id,
        action,
        result,
        request_id
    ) VALUES (
        v_actor,
        p_action,
        CASE WHEN v_allowed THEN 'allowed' ELSE 'denied' END,
        p_request_id
    );
    RETURN v_allowed;
END
$$;

-- Aynı kural tabloda da yazılı (iki katman: fonksiyon reddeder, tablo da kabul
-- etmez). Fonksiyonu genişletip kısıtı unutmak, yetkili yöneticide bile
-- CheckViolation üretirdi — testte tam bu yaşandı.
ALTER TABLE public.platform_admin_access_audit
    DROP CONSTRAINT platform_admin_access_audit_action;

ALTER TABLE public.platform_admin_access_audit
    ADD CONSTRAINT platform_admin_access_audit_action CHECK (
        action IN (
            'GET /admin/overview',
            'POST /admin/users',
            'GET /admin/courses',
            'GET /admin/requests',
            'GET /admin/ingestion',
            'GET /openapi.json'
        )
    );
