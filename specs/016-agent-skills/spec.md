# 016 — Taşınabilir ajan becerileri

Kullanıcı mevcut beceriler incelendikten sonra geliştirmeye devam edilmesini istedi. Bu dilim,17 mevcut repo becerisinin Codex karşılığını ve eski DOU yönergelerinin güncellenmesini kapsar. 90+ ajan kaynağı bulunmuş sayılmaz; yeni bir üçüncü taraf katalog kurulmaz.

## Kabul ölçütleri

- Mevcut 17 becerinin her biri `.agents/skills` altında aynı adla desteklenen metadata ve işleyen repo akışıyla bulunur.
- 14 Speckit Claude kaynağı korunur; 3 DOU kaynağının hem Claude hem Codex sürümü aynı taşınabilir içeriği taşır.
- Mevcut feature/plan veya kullanıcının çalışması ezilmez; dış issue/push/merge ve global yapılandırma beceri çağrısıyla kendiliğinden yapılmaz.
- Sabit kullanıcı dizini, zorunlu ortam dosyası kopyası, ortak veritabanı göçü ve kör temizlik talimatı kalmaz.
- Yapısal doğrulama bozuk/yinelenen metadata, eksik eşleme ve bozuk yerel bağlantıları yakalar; gerçekçi bağımsız deneme becerilerin kararlarını sınar.
- Yerel/küresel keşif ve beceri/ajan/çalışan süreç farkı belgelenir. Ürün testleri ve gerçek model sonucu bu belge değişikliğinde yeniden koşulmuş sayılmaz.

Ürün API'si, veritabanı şeması, model davranışı ve ön yüz değişmez. Bu, geliştirme araçları dilimidir.
