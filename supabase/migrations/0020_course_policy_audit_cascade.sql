-- Ders silinirken politika denetim kaydı yetim satır üretmeye çalışmasın.
--
-- Kusur: `courses` satırı silinince `course_ai_policies` ON DELETE CASCADE ile
-- düşer; DELETE tetikleyicisi bu sırada `course_ai_policy_audit`'e silinen dersi
-- işaret eden bir satır eklemeye kalkar. Ders çoktan silinmiş olduğu için
-- yabancı anahtar ihlali doğar ve ders silme işlemi 0009'dan beri hata verir
-- (tests/test_course_policy_cascade.py bunu kırmızı olarak sabitledi).
--
-- Çözüm: denetim satırı yalnız ders hâlâ varken yazılır. Eğitmenin politikayı
-- kendi eliyle silmesi eskisi gibi denetlenir (ders duruyor); dersin kendisi
-- silinirken ise denetim geçmişi zaten CASCADE ile birlikte gider, korunacak
-- bir şey kalmaz. Fonksiyon SECURITY INVOKER ve aynı search_path ile kalır;
-- dou_app'in denetim tablosunda UPDATE/DELETE yetkisi yoktur, değişmez.
BEGIN;

CREATE OR REPLACE FUNCTION app.audit_course_ai_policy()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, app
AS $$
BEGIN
    -- Üst kayıt silinirken tetiklenen CASCADE: ders satırı bu işlemde artık
    -- görünmez. Denetim eklemek yabancı anahtarı kırar; yazmadan geç.
    IF NOT EXISTS (SELECT 1 FROM courses WHERE id = COALESCE(NEW.course_id, OLD.course_id)) THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    INSERT INTO course_ai_policy_audit (course_id, changed_by, before, after)
    VALUES (
        COALESCE(NEW.course_id, OLD.course_id),
        app.current_user_id(),
        CASE WHEN TG_OP = 'INSERT' THEN NULL ELSE to_jsonb(OLD) END,
        CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE to_jsonb(NEW) END
    );
    RETURN COALESCE(NEW, OLD);
END
$$;

COMMIT;
