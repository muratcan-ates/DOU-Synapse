-- DOU-Synapse — embedding kökeni (R4, 0006)
--
-- TEK İŞ: her chunk'ın HANGİ VEKTÖR UZAYINDA embed edildiğini kayda geçirmek.
--
-- Neden gerekli. 9 Ağustos akşamı `fastembed` şu uyarıyı verdi:
--
--     The model intfloat/multilingual-e5-large now uses mean pooling instead of
--     CLS embedding. In order to preserve the previous behaviour, consider either
--     pinning fastembed version to 0.5.1 ...
--
-- Bu bir kullanımdan kaldırma notu değil, vektör uzayı değişikliğidir. Bir korpus
-- bir havuzlama stratejisiyle embed edilip başka biriyle sorgulanırsa hiçbir şey
-- çökmez; yalnızca sessizce yanlış komşular döner. Aynı gün bunun kardeşi bir kusur
-- canlıda gözlendi: dev korpusu `hashing` ile ingest edilmişti, sorgular `fastembed`
-- uzayındaydı ve sonuç saatlerce "retrieval kötü" diye okundu.
--
-- Bugün bu bilgi sistemde HİÇBİR YERDE tutulmuyor. Tutulmadığı için de uyuşmazlık
-- ancak sonuçların kalitesine bakılarak, yani insan sezgisiyle fark edilebiliyor.
--
-- NEDEN TEK SÜTUN, ÜÇ DEĞİL. Uzayı üç bileşen tanımlıyor (sağlayıcı türü, model adı,
-- kütüphane sürümü) ve üçü de gerekli — özellikle sürüm, çünkü yukarıdaki uyarının
-- konusu tam olarak o. Üç ayrı sütun raporlamada rahat olurdu ama karşılaştırmayı üç
-- kez yaptırırdı; üçüncüsü bir gün unutulur ve kontrol sessizce yalan söylemeye
-- başlardı. Kanonik tek dize, uyuşmazlık denetimini tek bir eşitliğe indiriyor.
--
--     biçim:  <sağlayıcı>/<model>@<sürüm>
--     örnek:  fastembed/intfloat/multilingual-e5-large@0.8.0
--     örnek:  hashing/hashing-v1@builtin-1
--
-- Model adı eğik çizgi içerdiği için ayrıştırma İLK eğik çizgiden ve SON `@`'ten
-- yapılır. Üreten fonksiyon: `app/core/vector_space.py:current_space`.
--
-- NEDEN NOT NULL DEĞİL. Bu göç var olan satırlar hakkında bir şey BİLEMEZ: hangi
-- sağlayıcıyla yazıldıklarını kayıt altına alan bir yer yok, zaten sorun bu. NOT NULL
-- + varsayılan değer koymak, bilmediğimiz bir şeyi biliyormuş gibi yazmak olurdu ve
-- ürettiği yanlış güven, bilgisizlikten kötüdür (Anayasa III). NULL burada dürüst bir
-- değer: "kökeni kaydedilmemiş".
--
-- Sorgu tarafındaki kontrol bu ayrımı korur (`app/modules/retrieval/dense.py`):
--
--     damga var  ve  farklı  → FAIL-CLOSED, istek reddedilir
--     damga var  ve  aynı    → geçer
--     damga YOK              → geçer, ama korunmuyor demektir
--
-- Son satır bilinçli. "Damgasız satırı da reddet" demek, bu göçün uygulandığı anda
-- var olan her kurulumu tuğlaya çevirirdi — kayıtlı korpusun tamamı damgasız. Kontrol
-- ancak damgalar yazılmaya başlandıktan sonra gerçekten koruma sağlar; o güne kadar
-- yeni yazılan chunk'ları korur.
--
-- MEVCUT KORPUSU DAMGALAMAK. Sağlayıcısı BİLİNEN bir veritabanında satırlar elle
-- damgalanabilir. Bunu göç yapmaz, çünkü göç hangi sağlayıcının kullanıldığını bilemez;
-- operatör bilir. Örnek (dev korpusu 9 Ağustos'ta E5 ile yeniden embed edildi):
--
--     UPDATE chunks SET embedding_space = 'fastembed/intfloat/multilingual-e5-large@0.8.0'
--     WHERE embedding_space IS NULL;
--
-- Bu komut GÖÇE KONMADI ve konmamalı: yanlış bir veritabanında koşturulduğunda
-- uyuşmazlığı gizler — tam olarak yakalamak için var olduğu şeyi.

ALTER TABLE chunks
    ADD COLUMN IF NOT EXISTS embedding_space text;

COMMENT ON COLUMN chunks.embedding_space IS
    'Vektörün üretildiği uzayın kanonik kimliği: <sağlayıcı>/<model>@<sürüm>. '
    'NULL = kökeni kaydedilmemiş (0006 öncesi satırlar). '
    'Üreten: app/core/vector_space.py:current_space';

-- "Bu derste kaç farklı uzay var" sorusunu indeksten cevaplar. Kısmi yeniden
-- embed etme (bir belge yenilenmiş, diğerleri eski uzayda kalmış) bu sorgunun
-- yakaladığı durumdur ve elle bakmak zorunda kalınmayacak kadar sık olur:
--
--     SELECT course_id, embedding_space, count(*)
--     FROM chunks GROUP BY 1, 2 HAVING count(DISTINCT embedding_space) > 1;
CREATE INDEX IF NOT EXISTS chunks_course_space_idx
    ON chunks (course_id, embedding_space);
