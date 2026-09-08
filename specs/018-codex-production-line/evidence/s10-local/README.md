# S10 — sunucu destek kimliği ve test kayıtlarının sahipliği

8 Eylül 2026 yerel kabulü. Taban `deb83e1`; adayın kaynakları
[son kaynak bağında](final-source-binding.json) bağlıdır. Arşiv hazırlığında
435 dosya byte-exact aynıydı; son kapıdaki tek gereksiz EOF satırı düzeltmesinden
sonra 434 dosya byte-exact, bir fixture ise aynı Bun JavaScript çıktısıyla bağlıdır.
[Özgün ölçüm eşliği](source-equivalence.json) değişmeden korunur.
Bu kayıt yeni GitHub/üretim kabulü değildir. Son uzak kabul `f79d8a2` üzerindedir;
S9 ve onu taşıyan sonraki commit'lerin herkese açık gönderimi kullanıcı onayı bekler.

## Değişen davranış

- Destek kodunu sunucu her HTTP denemesinde bir kez üretir. İstemcinin
  `X-Request-ID` değeri kimlik kaynağı olmaz. Yanıt, hata gövdesi, izinli günlük
  ve ilgili yönetim denetimi tek istek içinde aynı kodu kullanır.
- Yalnız doğrudan izinli alandaki tam iç kimlik tipi maskelemeden muaf olur.
  UUID içindeki tesadüfi rakam dizisi korelasyonu bozmaz; düz metin, alt sınıf,
  başka alan ve iç içe dict/list/tuple bu muafiyeti almaz.
- Tarayıcı temizlik makbuzları gerçek sunucu yanıtına, izinli hedef/aktör/işleme
  bağlanır. Eksik, yanlış veya yönlenen yanıt başarı sayılmaz. Boş makbuz
  bütün kayıtları seçmez. İki koşunun kayıtları birbirinden ayrılır.
- Denetleyici kendi API sürecini ve yeni web derlemesini başlatır; gerçek normal
  kapanışı bekler. Son audit muhasebesi bütün başlangıç satırlarının içeriğini
  karşılaştırır. Beklenmeyen kayıt varsa başarısız çıkar ve geniş silme yapmaz.
- GitHub E2E hazırlığı yalnız işe ait pinli servis/hedefi doğrular. İmaj, DB ve
  rol kimliği kontrolünden önce eski bir hedefte göç/rol kurulumuna geçmez.
  Parola dosyaları ve storage içeriği artifact yükleme kapsamının dışındadır.
- Öğrenci, eğitmen ve Bilgi İşlem kılavuzları mevcut B1–B7 akışlarıyla güncellendi.
  Tarihsel ekran görüntüleri yenilenmiş kanıt olarak sunulmaz.

## Gerçek ölçümler

| Kanıt | Sonuç | Kapsam |
|---|---|---|
| Tam API | 1688 PASS + 38 alt vaka | Ayrı fresh DB; koşu sonunda DB kaldırıldı, kaynak aynı. Beş mevcut uyarı korunur |
| Birleşik günlük/kimlik testleri | 134 PASS | DB ve ağ deneme sayaçları 0; tam API koşusuna dahil testlerin ayrı izolasyon ölçümü |
| Web ve TypeScript | 573 PASS, tip denetimi PASS | 45 dosya, 1362 assertion; doğru paket test komutu |
| Gerçek HTTP | 4 Uvicorn süreci, 56 yanıt | h11/httptools, eski/aday, paralel istekler, 401/500; 5.760984 s; DB/model/outbound denemesi 0 |
| Audit ayrımı | A/B tam satırları ve korunmuş P | A1→B1→A2→B2, yanlış/eksik makbuz reddi; A temizliği B'ye, B temizliği P'ye dokunmadı |
| Kaybolan makbuz | Beklenen FAIL, 1 ek O korunur | Gerçek isteğin makbuzu kasıtlı alınmadı; guard exit 1, broad delete 0; deneyin kabul koşulu bu başarısızlıktır |
| Son tam tarayıcı | 71 PASS, 92.288 s | Fresh DB02; 65 ders/14 audit temizliği; P02 tam satır özeti aynı; API exit 0 ve graceful pipe/wait |
| Gerçek süreç kapanışı | 6 çocuk, karşılaştırma PASS | Eski/final controller × normal/startup/shutdown. Final 0/3/1; Python fatal tanısı yok; bütün çocuklar toplandı |
| Sürekli süreç testleri | 11 PASS | 8 çevrimdışı stop sözleşmesi + 3 gerçek minimal ASGI çocuk; ürün/DB testi değildir |
| CI provisioning sözleşmesi | 14 PASS | Mock transport; geç kimlik sapması SQL'den önce reddedilir. İki sıra mutantı gerçek assertion FAIL |
| Statik kapılar | Ruff/format, mypy 114 PASS | Script denetimi açık proje ayarına bağlı; docs/migration/yönetişim kapıları ayrı kaydedilir |

Son E2E controller `56fc42a6`, guard `b36bfd7f` kaynaklarıyla çalıştı.
Önceki `ba51199d`/`eae66276` karşılaştırmalarından bu sürüme geçiş yalnız
biçim/açıklamadır; exact AST eşliği ayrıca arşivlidir. İlk 71-test E2E01
`d0db75dc` ile 99.477 s sürmüştü; sonucun üstüne yazılmadı.

## Korunan başarısızlıklar ve kanıt sınırı

- İlk S10 incelemesi tuple redaction ve yanlış/eksik tracked yanıt makbuzunu
  buldu. Aynı altı Python vakası eski kaynakta 6 assertion FAIL, düzeltmede
  6 PASS; aynı 17 web vakası 11 PASS/6 assertion FAIL → 17 PASS verdi.
  Bu sayılar altı ayrı sızıntı olayı anlamına gelmez.
- İlk negatif koşuda Bun exit hook'u sonuç makbuzunu yazmadı. `not complete`
  sonucu korunur; v2 aynı oracle'ları `afterAll` makbuzuyla çalıştırdı.
- İlk web komutu paket kapsamı yerine bütün test dosyalarını topladı:
  573 PASS yanında 16 Playwright toplama hatası vardı. İlk tip denetimindeki
  beş hata düzeltildi; iki değişikliğin Bun çıktısı byte-exact aynı kaldı.
- İlk lifecycle oracle'ı başlangıçtaki Python abort `-6` sonucunu yeterince
  ayırmadı. Özgün PASS kaydı ve düzeltici inceleme birlikte korunur. Ham stdin
  okuma/thread kapanışı düzeltildi. İkinci oracle yanlışlıkla startup exit 1
  bekledi; kurulu Uvicorn'un gerçek sözleşmesi exit 3'tür. v3 bunu açıkça
  sınar. Shutdown exit 0 artık tek başına başarılı kapanış sayılmaz.
- İlk CI YAML taslağı yanlış env sınırı nedeniyle servis bloğunu kaybetti;
  çalıştırılmadan reddedildi. Son taslak özgün pinli servis bloğunu korur.
- İlk script lint kontrolü kişisel global ayarı kullandı. Son kontrol açıkça
  projenin `apps/api/pyproject.toml` kurallarını kullanır; çalıştırılabilir
  AST'nin aynı kaldığı bağımsız ölçülmüştür.

Yerel PostgreSQL 16.14/pgvector 0.8.0 kullanıldı. Pinli CI pgvector 0.8.6
container'ı burada çalıştırılmadı; Docker/hosted sonucu türetilmez. Hata gövdesi
ve `app.error` aynı kodu taşırken genel 500 yolunda yanıt başlığı bulunmayabilir.
Destek kodu anonimlik, yetkilendirme veya idempotency anahtarı değildir.
Gerçek LLM/JWT/Storage, bütün log toplayıcıları, kurumun saklama ve imha kararı,
insan pedagojik kabulü ve hukuki uygunluk bu ölçümün dışında kalır.

## Arşivi okuma

[Özgün dosya eşliği](archive-origins.json) her tar üyesinin başlangıç yolunu,
boyutunu ve SHA256'sını verir. Altı gzip/tar paketi bağımsız kanıt gruplarıdır;
`measurements/` sonuçların byte-exact kopyalarını, `harness/` kök araçlarını
çalıştırılmayan metin olarak, `reviews/` ayrı incelemeleri tutar. Arşiv yolları
özgün `/private/tmp` çalıştırma yollarının otomatik yerine geçmez; yeniden
ölçüm için yeni hedef ve yeni kayıt gerekir. Özgün sonuçlar yeniden etiketlenmez.
Storage dosyaları, parola dosyaları, symlink'ler ve araç cache'leri dışarıdadır.
Sentetik fixture'ların kamuya gönderimi ayrıca açık paylaşım onayına tabidir.

Belge/göç/workflow kapıları son ölçümde geçti; workflow negatif paketi27 PASS.
İlk belge ölçümü PATH içinde uv bulamadı; ilk whitespace kapısı tek EOF boşluğunu
buldu. Bu kayıtlar korunur; düzeltmeler ve son bağımsız kontrol aynı arşivdedir.
