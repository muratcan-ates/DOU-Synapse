# D1 iki HTTP süreci — bağımsız yerel kanıt incelemesi

2026-09-08. **İncelenen kaynaklarda ve bu yerel deneyde kota veya yetki kabulünü engelleyen kalan bir bulgu saptanmadı.** Bu inceleme yeni veritabanı bağlantısı, sunucu, HTTP isteği veya ürün testi çalıştırmadı; mevcut ham kayıtları, çalıştırıcı kaynaklarını ve kök görev makbuzlarını karşılaştırdı.

[Ölçüm sonucu](/private/tmp/dou018-evidence/d1-http-measured-02/result.json), [ham HTTP kayıtları](/private/tmp/dou018-evidence/d1-http-measured-02/http-results.json) ve [kök çalıştırma makbuzu](/private/tmp/dou018-evidence/d1-http-provision-02/result.json) aynı deneyi destekliyor. DB `dou_synapse_d1_http02`, OID `1048788`, PostgreSQL `160014`, küme `7683042491268153327`, uç `127.0.0.1:55448`; süreçler `27764/27765`. Önceden kök tarafından sağlanan hedef parmak izi ile dört gerçek main/control havuzunun uç/OID/sürüm kimlikleri uyumlu. Dördünde de `dou_app`, superuser=false, bypassrls=false ve row_security=on. Küme kimliği kontrolü uygulama rolüne yetki eklenmeden yönetici korumasında yapılıyor; ham uygulama havuzu satırları küme kimliğini tekrar okumuyor.

| Ölçülen durum | Ham kaydın desteklediği sonuç |
|---|---|
| Ürün HTTP istekleri | 55 tekil istek; iki hazırlık isteği dahil 57 süreç yanıt olayı |
| Paylaşılan sohbet kotası | 40 istek: 20 kabul, 20 HTTP 429; her süreçte 10+10; reddetmede Retry-After=60 |
| Sağlayıcı hatası | Tek kontrollü sağlayıcı çağrısı, HTTP 503 / llm_unavailable |
| İki süreçte aynı önbellek sorusu | İlk yanıt cached=false, ikinci cached=true; toplam tek sağlayıcı çağrısı |
| Eğitmen soru üretimi | 5 kabul ve her kabulde 1 soru; ardından iki süreçten toplam 2 adet 429 / Retry-After=300 |
| Öğrenci soru üretimi | HTTP 403 / permission_denied; sağlayıcı çağrısı yok |
| Politika uyuşmazlığı / kontrol kilidi zaman aşımı | HTTP 503 / rate_limit_unavailable / Retry-After=1; sağlayıcı çağrısı yok; kilit sonrası istek kabul ediliyor |

Yedi sağlayıcı olayı, ham istek kimlikleriyle eşleşiyor: 1 kontrollü sohbet hatası, 1 ilk önbellek yanıtı, 5 soru üretimi. Reddedilen, politika/kilit nedeniyle başarısız, öğrenci ve önbellek isabeti isteklerinde sağlayıcı olayı yok. 28 sentetik retrieval olayı var. Gerçek FastAPI yönlendirme, rol/RLS oturumu, kota ve üretim iş akışı çalışıyor; retrieval ve LLM sağlayıcıları denetimli sentetik adaptörlerdir. Harici LLM çağrısının olmaması kaynak ve çocuk ortamı seçimiyle desteklenir; paket yakalama kanıtı değildir.

Kota sayaçları (20/1/0/0/1/2/0/5) ile sağlayıcı hatasında ana chat_sessions işlemindeki geri alma, değişmemiş çalıştırıcıdaki gerçek SQL assertion'larının başarıyla tamamlanmasıyla destekleniyor. **Bu ara skaler sonuçlar ayrı ham dosyalar halinde saklanmamış.** Son rapor courses/profiles/quota_windows/chat_sessions temizliğini dört sıfır sayıyla kaydediyor; kök işlem exit=0. Bu inceleme temizlikten sonra DB'yi yeniden okumadı. Üç DB işlevinin SECURITY DEFINER, volatility ve sabit search_path gözlemleri mevcut; tanım hash'leri kaydedilmiş ancak ham pg_get_functiondef metni bulunmadığı için burada yeniden hesaplanamıyor.

15 adlandırılmış çalışma zamanı kaynağı, tüm 111 Python kaynak dosyası ve kökün 21 göç dosyası hash'i eşleşti. Başlangıç/son ve inceleme anındaki kaynaklar aynı. Aday `0023` → entegre `0025` göç adı eşlemesi açık; advisory namespace `15023` korunmuş. Dört çalıştırıcı dosyası kökün önceden incelediği hash'lerle aynı. [Makine okunur denetim](/private/tmp/dou018-evidence/d1-http-independent-audit.json) giriş hash'lerini ve ayrıntıları içerir.

66 JSON uygulama satırı ve 155 süreç olayı incelendi. Gönderilen sentetik prompt işaretleri, Authorization/dev-token/DSN dizileri, JWT kalıbı ve özel içerik alanları dört log dosyasında yok. UUID/path/zaman/sayaç gibi sentetik metadata mevcut. Bir istek kimliğinin 11 basamaklı alt dizisi mevcut TCKN filtresinde maskelenmiş: 54 kimlik düz, biri aynı kaynak redaction dönüşümünden sonra eşleşiyor. Bu bir kota farkı değildir; düz kimlik üzerinden log birleştirmede mevcut bir yanlış pozitif sınırlamasıdır. Çevrimdışı sır canary'si bu HTTP koşusuna enjekte edilmedi; yokluğu gerçek sır maskeleme sınaması sayılamaz.

Ortak kota bölümü 0.327876 saniye, çalıştırıcı 1.952925 saniye, kök sarmalayıcı 2.13 saniye ölçmüş. Bunlar farklı kapsamların süreleridir; yük/performans garantisi değildir. Deney tek yerel PostgreSQL, geliştirme kimlik doğrulaması, denetimli sağlayıcı ve sabit döngü adresi kapsamındadır. Gerçek JWT/LLM, ağ kesintisi, çok makine dağıtımı, eşzamanlı soru üretimi, tam pencere sınırı, TTL takvimi ve hukuki uyumluluk bu kabulün dışındadır.

İlk başarısız v1 fixture deneyi korunmuştur: [ilk sonuç](/private/tmp/dou018-evidence/d1-http-measured-01/result.json) sunucu başlamadan `topics.created_by` eksikliğinden NotNullViolation kaydeder. V1 kaynakları ile ilk hata makbuzları koruma manifestine göre byte düzeyinde değişmemiştir. V2 bu fixture sütununu tamamlar; ilk olumsuz sonuç başarılıymış gibi yeniden yazılmamıştır.
