# Özellik Şartnamesi: API Gözlenebilirliği ve Etkileşimli Sözleşme

**Feature Branch**: `010-api-observability`  
**Base**: `db2f42a9ef7e75423c54db45fecedd1436ffa91b` (`009-assessment-integrity`)  
**Created**: 2026-08-20  
**Status**: Yerel uygulama ve kanıt turu; dağıtım/promotion yok  
**Risk**: R3 — merkezi istek middleware'i, operasyon telemetrisi ve platform-admin sınırı değişiyor

## Amaç

Mevcut Bilgi İşlem panelini yeniden yazmadan, API'nin bütün HTTP akışını içerik
toplamadan gözlenebilir yapmak ve export edilen OpenAPI sözleşmesini gerçekten
etkileşimli hâle getirmek.

Bu dilim üç kopukluğu kapatır:

1. Genel API 4xx/5xx/gecikme bilgisi bugün yalnız süreç logundadır; güvenli yönetim
   ekranından görülemez.
2. OpenAPI korumalı uçların Bearer kimliğini tanımlamadığı için Swagger'da
   `Authorize` yoktur.
3. Runtime tek Türkçe `ErrorEnvelope` döndürürken OpenAPI ve framework 404/405
   yolları farklı hata biçimleri göstermektedir.

## Kullanıcı hikâyeleri

### US1 — Bilgi İşlem API akışını içerik görmeden izler (P0)

Platform yöneticisi 15 dakika, 1 saat veya 24 saatlik bir aralık seçer; toplam
istekleri, durum sınıflarını, P50/P95 gecikmeyi, uç bazlı yoğunluğu ve son güvenli
olayları tek snapshot'ta görür. Destek kodunu POST gövdesinde arayabilir.

**Kabul senaryoları**:

1. Öğrenci, eğitmen ve normal kullanıcı yeni uca 403 alır; karar audit'e yazılır.
2. Yanıt kullanıcı/ders/belge kimliği, ham URL, query, body, IP, user-agent,
   prompt, cevap, stack trace veya ham hata metni taşımaz.
3. Uçlar `/courses/{course_id}/chat` gibi route template olarak görünür; gerçek UUID
   veya bilinmeyen yol asla fallback olarak kaydedilmez.
4. `/admin/*`, `/health/*`, docs/OpenAPI kabuğu ve `OPTIONS` olay üretmez; panel,
   hazır olma sondası ve sözleşme görüntüleme trafiği ürün metriğini şişirmez.
5. Filtre değişimi eski cevabın yenisini ezmesine izin vermez; manuel yenileme ve
   varsayılan-kapalı canlı izleme üst üste istek üretmez.
6. Boş aralık açıkça “istek yok” der; bunu servis sağlığı veya SLO başarısı diye
   yorumlamaz.

### US2 — Telemetri kullanıcı yanıtından bağımsızdır (P0)

İstek middleware'i yanıtı tamamladıktan sonra içeriksiz olayı sınırlı kuyruğa
bırakır. Tek bağlantılı ayrı yazıcı küçük partilerle saklar. Kuyruk doluysa veya
veritabanı yazımı başarısızsa asıl HTTP yanıtı değişmez.

**Kabul senaryoları**:

1. 2xx, uygulama 4xx, doğrulama 422, framework 404/405 ve beklenmeyen 500 aynı
   event sözleşmesini kullanır.
2. 500 gövdesi, `X-Request-ID`, güvenlik başlıkları, tamamlanma logu ve olay kaydı
   aynı güvenli destek kodunu taşır.
3. Kuyruk bounded'dır; başarısız batch sonsuz retry veya yeni görev fırtınası üretmez.
4. Kapanış en fazla iki saniye flush bekler; süreç süresiz açık kalmaz.
5. `API_OBSERVABILITY_ENABLED=false` yeni olay üretimini durdurur, uygulama ve
   geçmiş admin sorgusu çalışmaya devam eder.
6. Süre dolan satırlar yalnız bounded purge ile silinir; serbest tarih veya tablo
   silme yetkisi yoktur.

### US3 — API sözleşmesi tarayıcıda doğru ve kullanılabilirdir (P0)

Yerel/demo geliştirici Swagger'da `Authorize` ile Bearer token tanımlar ve korumalı
bir GET çağrısını çalıştırır. Sağlık uçları public kalır. 422, 404, 405 ve 500
gerçek runtime zarfıyla belgelenir/döner.

**Kabul senaryoları**:

1. `components.securitySchemes.BearerAuth` vardır; korumalı işlemlerde security,
   `/health/live` ve `/health/ready` işlemlerinde yoktur.
2. Hiçbir işlem `HTTPValidationError` şemasına referans vermez; 422
   `ErrorEnvelope` kullanır.
3. Bilinmeyen yol ve yanlış metot Türkçe `ErrorEnvelope` ve destek kodu döndürür.
4. Yerel/demo yalnız Swagger `/docs` yüzeyini dar CSP ile açar; ReDoc kapalıdır.
   Üretimde docs/OpenAPI varsayılan kapalıdır ve açıkça etkinleştirilemez.
5. Generated OpenAPI elle düzenlenmez; uygulama şemasından deterministik üretilir.

### US4 — Yönetim arayüzü erişilebilir ve küçük ekranda kullanılabilir (P1)

API akışı mevcut Bilgi İşlem sayfasının yeni, varsayılan sekmesidir. Sağlam admin
kapısı korunur; profil doğrulanmadan hiçbir `/admin/*` isteği başlamaz.

**Kabul senaryoları**:

1. 375 px görünümde sayfa yatay taşmaz; olaylar etiketli satır gruplarıdır.
2. Sekmeler, filtreler, yenileme ve detay açma klavyeyle çalışır ve görünür odağa sahiptir.
3. Tazeleme hatası eski snapshot'ı silmez; destek kodu ve tekrar deneme gösterir.
4. Sekmeye geri dönmek filtreyi/veriyi korur ve gereksiz tekrar isteği başlatmaz.
5. Ham veritabanı UUID'si veya öğrenci içeriği görsel kısaltma olarak dahi çizilmez.

## Fonksiyonel gereksinimler

- **FR-1001**: Genel HTTP ölçümü, chat'e özgü `request_logs` tablosundan ayrı olmalıdır.
- **FR-1002**: `api_request_events` yalnız sabit teknik alanları taşımalı; içerik ve
  kişi/ders bağlantısı için kolon bulunmamalıdır.
- **FR-1003**: Kayıt fonksiyonu yalnız exact `session_user=dou_api_runtime` için ve
  en fazla 100 olaylık batch ile çalışmalıdır.
- **FR-1004**: Runtime tabloyu doğrudan okuyamamalı/yazamamalı; admin projection da
  kendi içinde `app.is_platform_admin()` kontrolünü tekrarlamalıdır.
- **FR-1005**: Retention 1–30 gün olmalı; production değeri açıkça tanımlanmalıdır.
- **FR-1006**: Admin sorgusu yalnız `15|60|1440` dakika ve limit 1–100 kabul etmelidir.
- **FR-1007**: Destek kodu filtresi URL/query yerine POST gövdesinde taşınmalıdır.
- **FR-1008**: Observer başarısızlığı kullanıcı yanıtının durumunu, gövdesini veya
  gecikme kritik yolunu değiştirmemelidir.
- **FR-1009**: Request tamamlanma logu yalnız normalize route template yazmalıdır.
- **FR-1010**: Bütün runtime hata yolları `ErrorEnvelope` kullanmalı ve request ID
  header/gövde/log/event arasında aynı kalmalıdır.
- **FR-1011**: OpenAPI Bearer güvenliğini ve gerçek hata zarfını otomatik üretmelidir.
- **FR-1012**: Production docs yüzeyi fail-closed kapalı; local/demo CSP dar izinli olmalıdır.
- **FR-1013**: Admin UI tek resource snapshot'ı paylaşmalı ve kendi/admin/health
  çağrılarını ölçüme sokmamalıdır.
- **FR-1014**: Kill switch varsayılan `false` olmalı; yalnız doğrulanan yerel/CI
  yolları explicit opt-in yapmalıdır.

## Kapsam dışı

- Ham log, prompt, response body, stack trace, SQL veya kullanıcı içeriği görüntüleyicisi.
- Yönetim panelinden keyfî HTTP yazma/çalıştırma konsolu; etkileşimli geliştirici
  yüzeyi Swagger'dır.
- OpenTelemetry collector, distributed trace waterfall, Prometheus, paging veya
  production alert entegrasyonu.
- Bugünkü yerel veriden production SLO/error-budget başarısı iddiası.
- Platform admin atama/değiştirme arayüzü.
- Eski `feature/role-admin-panels` dalının yeniden birleştirilmesi.

## Başarı ölçütleri

- **SC-1001**: Hedefli backend, RLS ve her kritik yetki/validasyon mutasyonu geçer.
- **SC-1002**: 2xx/4xx/422/404/405/500 matrisinde güvenli olay ve aynı request ID kanıtlanır.
- **SC-1003**: OpenAPI'de korumalı/public işlem ayrımı ve ErrorEnvelope drift testi geçer.
- **SC-1004**: Web unit/type/build ile gerçek API Playwright masaüstü, 375 px,
  klavye ve reduced-motion yolları geçer.
- **SC-1005**: İçerik/kimlik/raw-path negatif taraması DB, API ve DOM katmanında sıfır sızıntı verir.
- **SC-1006**: Disk 10 GiB altındaysa ağır paket başlatılmaz; test DB, sunucu,
  Playwright ve build cache kalıntısı sıfır olur.
- **SC-1007**: Yerel kanıt local-only/not-deployed diye etiketlenir; gerçek staging,
  collector, alert ve insan onayı yoksa promotion `none` kalır.
