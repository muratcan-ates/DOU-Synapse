# S9 hata günlükleri — yerel kabul

8 Eylül 2026; f79d8a2 üzerine iki üretim modülü, dört yeni test dosyası ve mevcut altı Storage testinin yeni nesne şemasıyla uyumu. İstemci yanıtı sabit kalır. İstisna ve düz sunucu hata metni yerine sınırlı tanı, günlük çıktısı arızasında sabit stderr olayı kullanılır. Takip kimliğinin bilinen hassas kalıp maskesi korunur.

| Ölçüm | Sonuç |
|---|---|
| Son tam API | 1655 geçti,38 alt vaka,103.43s;219 kaynak koşu boyunca aynı, yeni test DB'si kaldırıldı |
| Son bağımsız günlük grubu | 84 geçti; DB/ağ bağlantı denemesi0; kaynaklar aynı |
| Gerçek tarayıcı | 71 geçti,91.979s; mtsxg2b23192 koşusunun65 dersi/14 audit kaydı temizlendi |
| Son gerçek sunucu karşılaştırması | Dört kol,16 süreç,20 yerel HTTP yanıtı;16.997839s PASS |
| Kod kapıları | Ruff/biçim ve113 kaynak için mypy geçti |

Sekiz özgün çevrimdışı kol değişmeden korunur: S9 eski18 FAIL/adayı18 PASS; errors-only18 FAIL; formatter-only14 PASS/4 destek kimliği FAIL. S9B eski2 PASS/33 FAIL, adayı35 PASS. S9C eski8 PASS/19 FAIL, adayı27 PASS. Bütün başarısızlık sayıları sızıntı sayısı değildir; şema, yeniden giriş ve yanıt dayanıklılığı da sınanır.

İlk entegre tam1651/38 koşusu geçti; bağımsız inceleme sonrasında bilinen request-ID maskesinin atlandığı P2 regresyonu bulundu. İki sentetik kalıp × filtresiz gerçek formatter/gerçek hata handler'ı dört vakada eskiyi başarısız, düzeltmeyi başarılı yaptı. Son1655/38 koşusu bu dört yeni kontrolü içerir. Eski yeşil sonuç yeni düzeltmeye taşınmadı. İlk birleşik çevrimdışı koşu eksik yerel auth ayarı nedeniyle83 PASS/1 Settings hatası verdi; ayrı temiz ortamlı ikinci koşu84 PASS verdi. Her ikisinde DB/ağ denemesi0; üretim kaynakları değiştirilmedi.

İlk gerçek dört kollu deney16 süreçte17.270648s geçti. Son pakette üç eski kol ve yardımcılar aynı; yalnız S9C logging son düzeltmeye bağlandı, deney yeniden çalıştı. h11/httptools HTTP500 ve sağlık200 zarf/gövde eşliği korunur. Eski kolun dört senaryosunda, S9'un yalnız lifespan yollarında görülen dört sentetik özel işaret S9B/son S9C'de yoktur. DB/outbound-socket/embedding/LLM denemesi0. İki olağan yapılandırma öncesi INFO satırı her süreçte JSON dışındadır. Startup failure exit3, shutdown failure exit0 olsa da failed olayı korunur. Normal sink deneyi, bozuk sink veya hassas destek kimliği deneyinin yerine geçmez.

`packages/` gzip tar dosyaları donmuş aday kaynaklarıdır; yürütülmemiş üç kollu ön hazırlık da ayrı korunur. `archive-origins-01.json` özgün dosya/üye hashlerini tutar. `source-equivalence.json` son API ve tarayıcı kaynak eşliğini bağlar. `reviews/` bağımsız raporları, `harness/` yerel korumalı çalıştırıcıları içerir. Önceki OPS hosted f79 sonucu yalnız o commit'e aittir. Yeni S9 kesin commit/PR kapıları ayrıca izlenir.

Sınırlar: istemci kontrollü destek kimliği hâlâ tekrar kullanılabilir ve kimlikle ilişkilendirilebilir; S10 ayrı iş. Genel INFO/WARNING, yapılandırma öncesi veya başka handler/proxy/hosting çıktıları için anonimlik garantisi yoktur. Exception nesnesi ve zaman damgasız acil fallback, collector geçişi gerektirir. Bloke stream için kesin süre, canlı hizmet/öğrenci, gerçek sağlayıcı kalite kabulü, hukuki sertifika veya üretim terfisi iddiası yoktur.
