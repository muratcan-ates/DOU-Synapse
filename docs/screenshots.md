# Belge ekran görüntülerini üretme

Yeni dosya: `docs/screenshots.md`. Hazırlık kaydı: 13 Eylül 2026.

[`screenshots.spec.ts`](../apps/web/e2e/screenshots.spec.ts), belge PNG'lerini
gerçek arayüzden alır. Ders, üyelik, materyal ve soru verisi yerel API'de yeni
kurulur; eski COME 331 dersinin veya sabit Ayşe/Burak profillerinin verisi
kullanılmaz. Her çalışan [`worker-fixture.ts`](../apps/web/e2e/worker-fixture.ts)
ile kendi sentetik kimliklerini alır. Materyalli sahneler
[`seed-assessment-course.ts`](../apps/web/e2e/seed-assessment-course.ts) üzerinden
kurulur; materyalsiz ret için ayrıca bu koşuya ait boş ders açılır.

## Çalıştırma koşulları

Önce koşunun sahibi yeni, izole E2E veritabanını ve ona bağlı API'yi kurar.
Global setup API ile veritabanının aynı hedefe bağlı olduğunu doğrular;
çalışan profilleri özel başarı makbuzu olmadan kurulmaz. `E2E_RUN_ID`,
`E2E_DATABASE_NAME`, `E2E_API_URL`, `E2E_AUDIT_TARGET_ID` ve `E2E_AUDIT_DIR`
doğrulanmış çalıştırma ortamından gelmelidir. Mevcut kişisel/ders veritabanının
adını değiştirerek E2E hedefi gibi göstermek bu kurulumun yerine geçmez.

API başlatma kaydında sahte sağlayıcı ve hashing seçimi açıkça korunur.
Bu seçim gerçek LLM kalitesini ölçmez; üretilen dosyalar sentetik arayüz
örnekleridir. Belge görüntüsü için eşik, yetki, kaynak veya sınav kilidi
gevşetilmez. Beklenen durum dönmezse ilgili görüntü üretilmez ve hata saklanır.

Doğrulanmış ortamda, `apps/web` dizininden:

```sh
EKRAN=1 ./node_modules/.bin/playwright test screenshots.spec.ts --project=llm --workers=2 --grep @ekran
```

`screenshots.spec.ts`, [`playwright.config.ts`](../apps/web/playwright.config.ts)
içindeki LLM dosya listesinde olmalıdır. `@llm` etiketi tek başına dosyayı bu
projeye taşımaz. Normal koşunun `@ekran` dışlaması korunur; yeni bağımlılık
kurulmaz. Mevcut genel çalıştırıcının `--workers=1` zorlaması ve ayrı argüman
aktarımı sınırı [test belgesinde](testing.md) izlenir; yukarıdaki seçili komut
genel çalıştırıcının paralel çalıştığına kanıt değildir.

Üretici kaynağın konumundan `docs/images` dizinini bulur. Arayüzün ilgili
başlığı/verisi görünmeden, yükleme durumu bitmeden ve yazı tipleri hazır olmadan
çekim yapmaz. Materyal ve soru havuzu sahneleri, gerçek ders rolü ve asistan
availability GET yanıtlarının başarısını ve tamamlanmış eğitmen kontrollerini
ayrıca bekler. Soru havuzu gerçek authoring kararını; etkinse öğrenme çıktısı
yanıtını ve ona karşılık gelen sınıflandırma alanlarını bekler. Bu yanıtlar
navigasyondan önce izlenir; erken gelen yanıt kaybolmaz. Üç sohbet sahnesi ayrıca
ilk materyal ve geçmiş yanıtını, dolu/boş kaynak sütununun gerçek hâlini ve
öğrenci navigasyonunu bekler. Gönderimden sonraki yeni geçmiş yanıtı eski ilk
yüklemeyle karıştırılmaz; cevabın oturum kimliğine ait etkin geçmiş satırı
ve cevap metni görünmeden PNG alınmaz. İki analitik sahnesinde gerçek rol ve
availability yanıtları ile role uygun Eğitmen Asistanı/Ders Koçu düğmesi de
beklenir; analitik verinin gelmesi bağımsız kabuk isteğinin bitmesi sayılmaz.
Açık tema ve genişlik sabittir. Başlangıç viewport'u 1280×900; materyal ve
soru havuzu gibi uzun form çekimlerinde yüklenen sayfa yüksekliği ölçülüp
sabit asistan düğmesi için 80 piksel boşluk eklenerek gerçek tarayıcı
yüksekliği artırılır. DOM gizlenmez; ürün arayüzü değişmez. PNG boyutları
ölçüm kaydında ayrı yer alır. Animasyonlar screenshot API'sinde kapatılır,
sabit süre uyutma kullanılmaz. Bu PNG'ler H2'nin Linux CI
referans görüntüleri değildir.

## Çıktılar ve veri anlamı

| Dosya | Görünen sahne | Verinin kaynağı | 13 Eylül 2026 son koşu |
|---|---|---|---|
| `images/09-sohbet-kaynakli-cevap.png` | Kaynak kartlı yanıt | Sentetik Markdown materyali, gerçek sohbet yanıtı; konum bölüm adı olabilir | Üretildi; gözle incelendi |
| `images/10-sohbet-nazik-ret.png` | Materyalde dayanak bulunamadı | Bu koşunun materyalsiz dersi, gerçek `insufficient_context` yanıtı | Üretildi; gözle incelendi |
| `images/10-sohbet-kapsam-disi-ret.png` | Dersin kapsamı dışında | Materyalli sentetik derste gerçek `out_of_scope` yanıtı | Üretildi; gözle incelendi |
| `images/05-egitmen-soru-havuzu.png` | Onaylı soru ve kaynak incelemesi | API'de üretilip onaylanan sentetik soru; ekranda üretim raporu olduğu iddia edilmez | Üretildi; gözle incelendi |
| `images/06-egitmen-sinif-analitigi.png` | Konu bazlı sınıf durumu | Gerçek API'ye gönderilen sentetik yanlış MCQ cevabı ve kapanmış alıştırma | Üretildi; gözle incelendi |
| `images/15-ogrenci-ilerleme.png` | Öğrencinin konu göstergesi | Aynı tür sentetik alıştırmanın gerçek kaydı; öğrenme başarısı ölçümü değildir | Üretildi; gözle incelendi |
| `images/03-egitmen-materyaller.png` | Hazır materyal | Bu koşuda gerçekten yüklenip işlenen `network-guards.md` | Üretildi; gözle incelendi |
| `images/16-kvkk.png` | Kişisel veri açıklaması | Güncel `/kvkk` sayfası; hukuki uygunluk sertifikası değildir | Üretildi; gözle incelendi |

Analitik sayıları arayüze yazılarak taklit edilmez; API'nin kaydettiği sentetik
cevaptan okunur. Kaynaklı yanıt sahnesi önbellek isabeti ölçümü değildir.
Materyalsiz ret görüntüsü dolu bir korpusta kapsam ayrımının kalite ölçümü
olarak sunulmaz. Sentetik profillerin adı/e-postası gerçek kişi bilgisi değildir.

Bu üreticinin kapsamadığı mevcut giriş, ders listesi, katılımcı, boş sohbet,
Sokratik kademe/ısrar ve sınav provası görselleri yenilenmiş sayılmaz. Kılavuz
denetimi bunları ayrıca ele alır. Başarısız bir sahnenin eski PNG'si dizinde
kalabilir; dosyanın varlığı son koşuda üretildiğine kanıt değildir.

## Üretim sonrası kayıt

Koşunun sahibi komutu, aday commit'ini, sağlayıcı seçimini, Playwright çıkışını,
API kapanışı ve audit/temizlik sonucunu saklar. Gerçekten oluşan dosyaların
hashleri alınır ve her PNG gözle incelenir: doğru ekran, okunur yazı, yükleme
ve hata yüzeyi bulunmaması, kesilme olmaması ve sentetik kapsamın anlaşılması.
Bu kontroller yapılmadan tabloya "üretildi/doğrulandı" yazılmaz. Kaynak hazırlığı,
tek başına görüntü üretimi veya tarayıcı kabulü değildir.

## Gerçek üretim ve inceleme — 13 Eylül 2026

`h7-screenshots-03` seçili sekiz sahneyi iki worker ile tamamladı;
Playwright, sahipli API kapanışı ve audit sonucu başarılıydı. Ürün kaynağı
ve yeniden kullanılan H6 üretim derlemesinin özetleri koşu boyunca aynı kaldı.
Bütün PNG'ler yeniden yazıldı ve tek tek açılıp incelendi. İlk denemedeki
gizli option seçici hatası ile sonraki uzun form örtüşmesi kayıtları korunur;
son görüntülerde form kontrolleri okunur durumdadır.

[Gerçek dosya özetleri ve görsel gözlemler](evidence/l6-h7-images.json),
her PNG'nin boyutunu, sentetik kapsamını ve koşu kaydını içerir. Gerçek
sağlayıcı kabulü, hukuki uygunluk veya H2 Linux referans üretimi yapılmış sayılmaz.
