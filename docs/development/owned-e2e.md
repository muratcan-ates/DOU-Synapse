# Sahipliği doğrulanan tarayıcı testi

Tarayıcı paketi gerçek API ve yeni web derlemesiyle çalışır. Uygulama verisi
ve denetim kayıtları için yalnız bu koşuya ayrılmış sentetik hedef kullanılır.
Mevcut geliştirme veya üretim veritabanında doğrudan temizlik komutu çalıştırmayın.

## Giriş noktası

`scripts/run_owned_e2e.py`, önceden bağımsız olarak oluşturulup kimliği
doğrulanmış hedef için çağrılır. Yerel operatör hedefin tek sahibi olduğunu,
aynı storage alanını veya API sürecini başka koşunun kullanmadığını doğrular.
Araç her fazda kendi API sürecini başlatır; açık web sunucusunu yeniden kullanmaz.

```text
python scripts/run_owned_e2e.py --repo <mutlak-depo-yolu> \
  --pins <özel-hedef-kaydı> --pins-sha256 <önceden-doğrulanan-sha256> \
  --passfile <özel-parola-dosyası> --output <yeni-mutlak-kanıt-dizini> \
  --run-id <benzersiz-koşu-kodu> --web-port <boş-yerel-port>
```

Python ortamında API bağımlılıkları, PATH üzerinde Bun ve PostgreSQL istemcisi,
kurulu Chromium gerekir. `--webpack` yerel derleyici seçeneğidir; varsayılan
CI derleyicisini değiştirmez. Hedef kaydı/üst dizini ve parola dosyası özel
izinli normal dosyalardır. Hedef kaydı cluster kimliği, DB adı/OID, açık sayısal
host/port, DBA rolü, API origin'i ve provisioning makbuzuna bağlanır.
Kendi bağlandığı DB'den hash üretmek, hedefe sahip olunduğunu tek başına kanıtlamaz.

Yerel provisioning ve rol yönetimi operatörün sorumluluğundadır. Bu araç mevcut
rol izinlerini değiştirmez, veritabanı yaratmaz/silmez. `bun run test:e2e`
tek başına üst sürecin sahiplik ve başlangıç kayıtlarını oluşturmaz; doğrudan
çağrı gerekli makbuz yoksa güvenli biçimde reddedilir.

## GitHub işi

E2E işi kendi PostgreSQL servis container kimliğini
`scripts/provision_ci_e2e.py` aracına verir. Araç pinli imajı, container/host
bağlantı eşliğini ve boş servis envanterini doğrular. Yalnız yeni oluşturduğu
hedefte göçleri, mevcut yerel demo rol kurulumunu ve sentetik seed'i uygular;
her SQL dosyasından önce hedef kimliğini tekrar kontrol eder. Mac veya ortak
PostgreSQL için bu CI provisioning yolu kullanılmaz.

## Başarı ölçütü

Her faz için tarayıcı exit0, API'nin gözlenmiş normal kapanışı ve o fazın
başlangıç/son tam audit muhasebesi birlikte gerekir; koşunun tamamı için ayrıca
değişmemiş kaynak hash'leri. Korunmuş satırın kaybolması/değişmesi veya makbuzu
yakalanmayan yeni satır başarısızlık üretir. Araç bunu geniş DELETE ile
gizlemez; hedef ve kanıt inceleme için kalır.

## Fazlar

İki kabul dosyası kendi API sürecini ister ve bayrakları AYNI ANDA açılamaz:
`LLM_SIMULATE_RATE_LIMIT` açıkken sağlayıcı her üretim çağrısında 429 simüle
eder, yani diğer bütün sohbet testleri düşerdi. Araç bu yüzden üç fazı SIRAYLA,
her birini kendi API süreciyle koşar; fazı `E2E_PHASE` ile `playwright.config.ts`
seçer. Değişken kurulmadığında liste ve proje bölünmesi değişmez.

| Faz | API bayrağı | Kapsam |
|---|---|---|
| `main` | yok | İki simülasyon dosyası dışındaki her şey |
| `grounded` | `LLM_SIMULATE_GROUNDED_FEEDBACK=1` | `grounded-wrong-feedback.spec.ts` |
| `ratelimit` | `LLM_SIMULATE_RATE_LIMIT=1` | `provider-fallback.spec.ts` |

Her fazın kendi denetim muhasebesi, kendi API süreci, kendi depo kökü ve kendi
çalışma dizini vardır; `--run-id` üçünde de aynıdır (guard'ın 20 karakter sınırı
ek bir faz sonekine yer bırakmaz). Fazlar ÖRTÜŞMEZ: bir fazın `finish`'i
bitmeden sonraki fazın `begin`'i koşmaz.

Bütçe: `--test-timeout` `main` fazının tarayıcı bütçesidir ve varsayılanı 720
sn'dir (tek koşu üçe bölündüğü için 900'den indirildi). Simülasyon fazlarının
tavanı ayrı sabitlerdir (420 sn ve 300 sn) ve CLI değerinin ORANI DEĞİLDİR, ama
bunlar tavandır: fiilen verilen bütçe, ortak son tarihten sonraki fazların payı
ve fazın kendi ek yükü düşülerek hesaplanır, yani tavanın altında kalabilir.
Ek yük (port sondası, hazır olma, iki guard anlık görüntüsü, kapanış) `budget`'e
girmez; bu yüzden her fazın payı duvar saati olarak ayrılır ve normal ek yük
altında sonraki fazlar payını korur. Patolojik bir faz payı yine de tüketirse
sonraki faz sessizce kısalmaz, açıkça `PHASE_BUDGET_EXHAUSTED` ile FAIL olur.
Bu sayıların hepsi TAHMİNDİR; ilk CI koşusunun `result.json` içindeki
`phases[].seconds` ve `phases[].budgetSeconds` değerleriyle yeniden ölçün.

## Sonucu okuma

`result.json` (`version: 2`) tek dosyadır; `phases[]` her fazın kendi kaydını
taşır. Düz anahtarlar TEK bir fazı yansıtır — ilk düşen faz, hepsi geçtiyse
sonuncusu — ve hangisi olduğu `leadPhase` alanındadır. Toplam `status` yalnız
şu durumda `PASS`: planlanan üç fazın üçü de koştu, üçünün de kendi durumu
`PASS`, hiçbir fazda korunmuş satır hasarı yok ve kaynak hash'leri değişmedi.

Faz başına kanıt, ölçüm dizininin kökünde: `audit/<faz>/final-accounting.json`,
`quiescence-<faz>.json`, `api-<faz>.log`, `playwright-<faz>.log`,
`guard-begin-<faz>.log`, `guard-finish-<faz>.log`. Tarayıcı iz ve ekran
görüntüleri `apps/web/test-results/<faz>/` altındadır; fazlar ayrı dizin
kullanmasaydı Playwright her koşunun başında öncekini silerdi.

`auditReconciled: false` olan faz, satırlarını KİMSENİN raporlamadığı fazdır
(`finish` hiç koşmadı ya da son muhasebe o fazın makbuzuna bağlanamadı). Bu
durumda kalan fazlar koşulmaz: guard'ın `begin`'i sessizlik aramadığı için
sonraki faz o artığı kendi baseline'ına yutar ve temiz görünürdü.

Bunları gerçek test loglarıyla birlikte okuyun. Kapanış hatasında yalnız exit0
yeterli değildir.
Hata sonrası tekrar için yeni koşu/hedef hazırlayın; eski makbuzları başarı
etiketiyle yeniden kullanmayın. Yalnız araç tarafından oluşturulmuş çocuk
süreçlerin kapanışına müdahale edilir.

CI artifact'ı JSON/log ve Playwright rapor/trace'lerini tutar; parola dosyası,
storage içeriği veya `.env` yüklemez. Sentetik fixture ve operasyonel metadata
yine erişim/saklama politikası gerektirir. Yerel başarı gerçek JWT, LLM,
private Storage, Docker hedefi veya hukuki uygunluk kabulü değildir.
