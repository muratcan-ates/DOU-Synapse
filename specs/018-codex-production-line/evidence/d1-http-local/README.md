# D1 gerçek iki HTTP süreci kabulü

Bu arşiv 8 Eylül 2026 yerel D1 kaynaklarını ölçer; uzak 9af4122 CI sonucuna dahil değildir.
`run-02/result.json` ile `http-results.json`: 55 ürün isteği, iki ayrı PID,
40 ortak sohbet isteğinde 20 kabul/20 ret, 7 kontrollü sağlayıcı olayı.
Soru üretiminde 5 kabul ve 2 ret; gerçek Retry-After 300 saniye.
Politika uyuşmazlığı/kilit zaman aşımı 503, öğrenci üretimi 403;
bu retlerde sağlayıcı çağrısı sıfır. Sağlayıcı hatası kotayı geri almaz;
iki süreçte önbellek isabeti tek sağlayıcı çağrısıyla iki istek sayar.

`run-01` sunucu başlamadan eksik topics.created_by fixture sütunu nedeniyle
başarısızdır. Başarılı sonuçla değiştirilmedi. `harness-v2` bu fixture düzeltmesini
içerir; ürün kaynakları değiştirilmedi. Bağımsız incelemenin asıl byte'ları ve
mutlak yerel bağlantıları korunur; aynı girdilerin taşınabilir kopyaları burada.
Hash eşlemesi `archive.json` içindedir; gzip dosyalarında mtime=0 kullanılır.

Gerçek FastAPI, PostgreSQL/RLS ve uygulama üretim akışı kullanılmıştır;
kimlik doğrulaması geliştirme kipinde, retrieval/LLM kontrollü sentetiktir.
Harici model/JWT, çok makine, ağ kaybı, belirsiz kontrol COMMIT'i ve fiziksel TTL
takvimi bu deneyin kapsamına girmez. Ara SQL skalerleri ayrı ham dosyalara
yazılmamıştır; değişmemiş harness assertion'ları ve başarılı süreç çıkışıyla
desteklenir. pg_get_functiondef yalnız hash/öznitelik olarak kaydedilmiştir.
Bir UUID alt dizisinin mevcut TCKN filtresince maskelenmesi log birleştirmesinde
yanlış pozitif sınırıdır; tüm 55 istek dönüşüm hesaba katıldığında eşleşir.
