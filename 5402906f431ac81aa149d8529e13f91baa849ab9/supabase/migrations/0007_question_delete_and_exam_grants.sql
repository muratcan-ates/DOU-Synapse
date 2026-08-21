-- DOU-Synapse — eğitmen soru silme + sınav oturumu kolon yetkisi (lider, 0007)
--
-- İki madde. Üçüncüsü (yeniden puanlama fonksiyonu) BİLEREK YAPILMADI, gerekçesi
-- aşağıda.
--
-- Kaynak: `docs/team/parallel/KARARLAR_SERIT4.md` Karar 2 ve Karar 3. Şerit 4
-- ikisini de teşhis etti, yamalarını yazdı ve uygulamadı — migration numarası ve
-- politika değişikliği o şeridin sınırı dışındaydı.


-- ---------------------------------------------------------------------------
-- (a) Eğitmen havuzdan soru silebilsin
-- ---------------------------------------------------------------------------
--
-- Bu politika olmadan bir ÇIKMAZ vardı ve 9 Ağustos akşamı kendi elimle
-- kurdum: `documents.py` artık, o belgeden üretilmiş soru varsa silmeyi 409 ile
-- reddediyor ve kullanıcıya şunu söylüyor —
--
--     "Bu belgeden üretilmiş sorular havuzda olduğu için belge silinemiyor.
--      Önce ilgili soruları kaldırın."
--
-- Ama soruyu kaldırmanın hiçbir yolu yoktu. Ne politika vardı ne uç. Yani hata
-- mesajı, var olmayan bir çıkış yolunu tarif ediyordu; bu, hiç mesaj vermemekten
-- kötüdür — kullanıcı yapamayacağı bir şeyi denemekle vakit kaybeder.
--
-- Reddetmek (`status = 'rejected'`) silmenin yerine geçmez: reddedilen soru
-- öğrenciye görünmez ama satır durur, `source_chunk_id` hâlâ chunk'a bağlıdır ve
-- `ON DELETE RESTRICT` belgeyi kilitlemeye devam eder. Red pedagojik bir karar,
-- silme ise yapısal bir işlem.
--
-- Yalnız DELETE veriliyor: eğitmen kendi dersinin sorusunu silebilir, başka
-- dersinkini göremez bile (`questions_read` zaten ders kapsamlı).
CREATE POLICY questions_instructor_delete ON questions
    FOR DELETE USING (app.is_instructor(course_id));


-- ---------------------------------------------------------------------------
-- (b) Öğrenci kendi sınav oturumunun süresini ve puanını yazamasın
-- ---------------------------------------------------------------------------
--
-- Şerit 4'ün Karar 2'si: kalan süre `min(expires_at, started_at + süre)` ile
-- kırpılıyor, yani `expires_at` yazılabilir kaldığı sürece kırpma tam kapanmıyor.
-- RLS satır düzeyinde çalışır, SÜTUN kısıtı veremez — bu yüzden kolon bazlı GRANT.
--
-- `finished_at` API'nin gerçekten yazdığı tek sütun: bitiş akışı onu damgalıyor.
-- Puan `answers`'tan türetiliyor (`score_of(outcomes)`), `exam_sessions.score`
-- sütununa API tarafından YAZILMIYOR — dolayısıyla bu kısıt bugünkü hiçbir kod
-- yolunu kırmıyor. Doğrulandı: 35 sınav testi ve tam süit bu göçle yeşil.
REVOKE UPDATE ON exam_sessions FROM dou_app;
GRANT UPDATE (finished_at) ON exam_sessions TO dou_app;


-- ---------------------------------------------------------------------------
-- (c) Yeniden puanlama fonksiyonu — YAPILMADI
-- ---------------------------------------------------------------------------
--
-- Şerit 4 bunu "istenirse; istenmezse hiç yapılmasın, bugünkü davranış FR-020
-- uyumlu" diye bıraktı. Yapılmadı ve sebebi burada yazılı olsun:
--
-- Değerlendirilemeyen bir cevap bugün dürüst davranıyor — `graded: false`,
-- `score: null`, ve arayüz puan uydurmak yerine "değerlendirilemedi" diyor,
-- bitişte de kaç cevabın puana katılmadığını söylüyor. Yani eksiklik görünür ve
-- yanlış bir sayı üretilmiyor.
--
-- `SECURITY DEFINER` bir yeniden puanlama fonksiyonu, RLS'i atlayan yeni bir
-- yazma yüzeyi açar. Bugün ölçülmüş bir ihtiyaç yokken böyle bir yüzey açmak,
-- kazandırdığından fazlasını riske eder. Gerçek bir LLM anahtarıyla koşulduktan
-- sonra "kaç cevap değerlendirilemedi" ölçülür; sayı anlamlıysa o zaman açılır.
