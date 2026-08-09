-- DOU-Synapse — analitik okuma yetkisi
--
-- TEK İŞ: eğitmenin, kendi dersinin `request_logs` satırlarını OKUYABİLMESİ.
--
-- Neden gerekli: T038'in eğitmen görünümü kapsam dışı ret oranını (SC-005) raporlar.
-- 0003 bu tabloyu istemciye tamamen kapalı bıraktı ve gerekçesiyle birlikte kararı
-- buraya devretti:
--
--     "request_logs: istemciye KAPALI. SELECT politikası bilinçli olarak yoktur (...)
--      Analitik ekranı satır bazlı erişime ihtiyaç duyarsa eğitmen kapsamlı bir SELECT
--      politikası 0005'te açılır (Şerit 5) — burada değil."   (0003_chat.sql)
--
-- NEDEN `chat_messages` DEĞİL: analitik önce oradan okuyordu ve eğitmen bağlamında
-- her zaman sıfır satır görüyordu — çünkü `chat_messages_self_read` yalnız oturum
-- sahibine açık. Bu bir kusur değil, 0003'ün bilinçli gizlilik kararı:
--
--     "Eğitmene okuma yetkisi bilinçli olarak VERİLMEDİ: öğrencinin hocasına sorma
--      çekindiği soruyu sisteme sorabilmesi ürünün gerekçelerinden biri, eğitmenin
--      bunu satır satır okuyabilmesi bunu bozar."
--
-- O karar bu migration'da KORUNUYOR. `chat_messages` eğitmene kapalı kalır; analitik
-- artık `request_logs`'tan okur. Fark önemli: `request_logs` şema gereği serbest metin
-- TAŞIMAZ (soru metni, cevap metni yok; yalnız sayısal/kategorik alanlar). Yani
-- eğitmen "kaç soru kapsam dışı diye reddedildi" sorusunun cevabını alır ama hiçbir
-- öğrencinin ne sorduğunu göremez. Gizlilik kararı ile ölçülebilirlik ihtiyacı
-- böylece aynı anda karşılanıyor.
--
-- Kapsam bilinçli olarak DAR: yalnız SELECT, yalnız eğitmen, yalnız kendi dersi.
-- INSERT politikası 0003'teki hâliyle kalır; UPDATE/DELETE politikası hâlâ YOKTUR —
-- ölçüm kaydı sonradan düzeltilebilirse hiçbir şeyin kanıtı olamaz (Anayasa III).

BEGIN;

CREATE POLICY request_logs_instructor_read ON request_logs
    FOR SELECT USING (app.is_instructor(course_id));

COMMENT ON TABLE request_logs IS
    'Ölçüm kaydı. Serbest metin taşımaz. Eğitmen kendi dersinin satırlarını okur '
    '(0005); öğrenci hiçbir satırı okuyamaz, yalnız kendi adına satır yazabilir.';

COMMIT;
