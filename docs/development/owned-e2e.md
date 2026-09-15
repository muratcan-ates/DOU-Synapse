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
İlk fazlı CI koşusundan (34926253846) yeniden ölçüldü:

- `--test-timeout` 720 **korundu**. O koşu `PLAYWRIGHT_BUDGET_EXCEEDED` verdi
  ama sebebi bütçe değil: `api-main.log` zaman damgalarına göre 720,3 sn'lik
  açıklığın 544,4 sn'si ≥10 sn'lik BOŞLUK (2 × 90 sn test zaman aşımı,
  18 × ~11 sn expect zaman aşımı, kesilen kuyruk). Gerçek iş 175,7 sn; fazlama
  öncesi koşuda (34900228666, 87 vaka) aynı hesap 182,8 sn. Vaka başına iş
  2,10 → 2,25 sn, yani uygulama yavaşlamadı. Yeşil bir ana faz ~250 sn.
  Üst sınırda vaka tavanı 90 sn DEĞİL: süitte `test.setTimeout` 120_000 (14
  vaka), 150_000 (5) ve 180_000 (2) ile yükseltiliyor ve ana fazda `retries: 1`
  var, yani tek bir asılı ağır vaka 2 × 180 = 360 sn yiyebilir. Yeşil ~250 +
  bir asılı ağır vaka ~360 = ~610 sn, hâlâ 720'nin altında; iki tanesi sığmaz
  ve bütçe aşılır — istenen işaret de budur.
- `OVERALL_BUDGET` 1250 → **1440**. E2E işini gerçekten koşan 29 CI koşusunda
  iş kurulumu maks 80 sn, adım sonrası kuyruk maks 7 sn, provision maks 2,3 sn;
  30 dk sınırından ham boşluk 1710 sn, soğuk bağımlılık önbelleği için 270 sn
  pay. 1250 bu boşluğun 460 sn'sini kullanmıyordu ve ana faz tavanını yakınca
  `grounded`'ı 420 yerine 256,9'a sıkıştırıyordu; 1440 ile tam tavanını alır.
- `PHASE_OVERHEAD` 60 korundu. Ölçülen ek yük 3,1 sn'dir ama o fazın guard
  baseline'ı boştu (`baselineCount: 0`) ve pay artık SIGINT iptal zincirini
  (25 sn) de kapatmak zorunda.

**Hâlâ ölçülmedi:** simülasyon fazlarının dört sabiti (420/260 ve 300/210).
O fazlar bu koşuda hiç başlamadı — `grounded` kendi API sürecine ulaşamadan
`WEB_PORT_BUSY` aldı (15,052 sn = port sondasının tam zaman aşımı), `ratelimit`
hiç sıraya gelmedi. Port düzeltmesi yeşil `phases[].seconds` üretince bu dört
sayıyı o koşudan yeniden ayarlayın.

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

`browserStopObservation` fazın tarayıcısının NASIL durduğunu söyler. Playwright
web sunucusunu `detached: true` ile ayrı süreç grubu ve oturumunda başlatır, bu
yüzden koşucunun `killpg`i oraya ulaşmaz; onu kapatan tek yol Playwright'ın
SIGINT iptal zinciridir (SIGTERM'in Node'da işleyicisi yoktur, süreç anında
ölür ve `next start` portta kalır). Basamak SIGINT → SIGTERM → SIGKILL'dir ve
ikinci bir SIGINT bilerek gönderilmez: teardown'un kendi gözcüsü vardır, ikinci
sinyal tam da web sunucusunu öldüren adımı iptal ederdi.

| Değer | Anlamı |
|---|---|
| `exited-before-stop` | Tarayıcı kendi bitti; sinyal gönderilmedi (normal yol) |
| `interrupted` | SIGINT yetti; Playwright kendi web sunucusunu kapattı |
| `forced-terminate` / `forced-kill` | İptal zinciri bitmedi; port sonraki faza öksüz devredilebilir |

Bütçe aşan bir fazda `interrupted` BEKLENİR. `forced-*` görülüyorsa sonraki
fazın `WEB_PORT_BUSY`'si tesadüf değildir, bu satırla eşleştirilir.

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
