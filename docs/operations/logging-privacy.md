# Uygulama günlükleri ve hata tanısı

Bu sözleşme S9 hata işleyicisi ile S9C günlük handler'ının birleşik kaynak
davranışını anlatır. Kod yerel çalışma ağacına entegredir; aşamalı çevrimdışı
ve gerçek süreç kanıtları vardır. Son birleşik test ve kesin commit'in uzak
kapıları [S9 kabul kaydından](../../specs/018-codex-production-line/evidence/s9-local/README.md)
izlenir. Üretim log toplayıcısı, alarm teslimi ve saklama/imha kabulü değildir.

## Akışlar ve alanlar

Veritabanındaki `request_logs` ile stdout/stderr farklı kopyalardır. SQL RLS,
toplayıcıdaki bir kayda erişimi veya silinmesini yönetmez. Uygulama kurulumu
`uvicorn.access` kanalını kapatır; `app.request` ve `uvicorn.error` açık kalır.
Uygulama kurulmadan önce Uvicorn kendi başlangıç mesajlarını yazabilir;
sürecin bütün çıktısının JSON olduğu varsayılmaz.

| Akış | Mevcut biçim ve korunan alanlar | Sınır |
| --- | --- | --- |
| Tamamlanan HTTP isteği | JSON `ts`, `level`, `logger`, `message`; context'te `request_id`, `method`, rota şablonu veya `<unmatched>`, `status`, `duration_ms` | Ham yol/sorgu yerine şablon kullanılır. Middleware'den hata fırlayan yol ayrı hata kayıtlarına gider; bu akış bütün isteklerin güvenilir toplamı değildir. |
| `exc_info` taşıyan kayıt | JSON `ts`, `level`, izinli logger/olay, `context.error_code`; `exception` artık metin yerine nesne | Mesaj, args, locals, cause/context zinciri, notes, exception-group üyeleri, kaynak satırı ve keyfi extra alanları biçimlendirilmez. |
| Düz `uvicorn.error` ERROR/CRITICAL | JSON zaman/seviye, sabit olay metni ve `context.error_code` | Bilinmeyen metin `uvicorn_error` olur; serbest args/extra kaybolur. İzinli timeout sayısı veya bilinen errno/errno_name korunabilir. |
| Diğer uygulama kayıtları | Genel JSON mesaj/context/extra yolu, bilinen kalıplarda `RedactionFilter` | Regex serbest kişisel metni bütünüyle tanımaz; bu dal ve dış proxy/sağlayıcı günlükleri için anonimlik garantisi yoktur. |
| Günlük çıktısı arızası | Aşağıdaki sabit ASCII JSON, doğrudan stderr | Zaman damgası, destek kimliği ve exception ayrıntısı yoktur. Fallback da başarısız olursa ek çıktı garantisi yoktur. |

`exception` alanının eski string biçiminden yeni nesneye dönüşmesi **log şeması
değişikliğidir**. Nesne yalnız `error_type`, `frames`, `frames_truncated`
alanlarını taşır. Bilinmeyen exception sınıfı `Exception` olarak adlandırılır.
En fazla 64 traceback düğümü incelenir ve son sekiz izinli uygulama frame'i
tutulur; her frame mevcut kaynakta doğrulanmış göreli `path`, `function` ve
`line` taşır. Kaynak satırı, yerel değişken veya mutlak dosya yolu döndürülmez.
Bu metadata yine işletim verisidir; kaynak dosyası okuma/AST işinin bütün
koşullarda sabit süreli olduğu iddia edilmez.

## Destek kimliği ve istemci yanıtı

Beklenmeyen hata istemciye 500 ve genel Türkçe
`{error: {code, message, request_id}}` zarfıyla döner. Destek kimliği bilinen
hassas kalıplar maskelenerek `app.error` context'ine konur; maskelenen bir
istemci değeri logda yanıt gövdesiyle birebir aynı olmayabilir. Şu an middleware, istemcinin
`X-Request-ID` başlığındaki 1–128 ASCII harf/rakam/alt çizgi/tire değerini
kabul eder; uygun değilse yeni kimlik üretir. Kabul edilen değer tekrar
kullanılabilir ve bir kişiyi/istek grubunu ilişkilendirebilir. Sözdizimi
sınırı, değerin kişisel bilgi veya sır taşımadığını garanti etmez. Exception
context'indeki destek kimliğine de bilinen hassas kalıplar için maskeleme
uygulanır; kalıplara uymayan istemci değerleri yine ilişkilendirilebilir. Kimlik,
yetkilendirme ya da işlemin tekilliği için kanıt değildir.

İstemci kaynaklı kimliğin değiştirilmesi **S10'da açıktır**; S9/S9C bunu
çözmüş sayılmaz. Genel 500 yolunda `X-Request-ID` yanıt başlığı mevcut
middleware akışında bulunmayabilir; destek için zarfın alanı kullanılır.
Gerçek karşılaştırmada bu başlık bütün kollarda yoktu, gövdedeki kimlik aynı
kaldı. Yeni bir başlık sözleşmesi veya benzersizlik garantisi çıkarılmamalı.

## Günlük çıktısı çalışmıyorsa

`PrivacySafeStreamHandler`, formatter/write/flush sırasında ordinary
`Exception` oluşursa ham LogRecord veya traceback'i yeniden yazmak yerine
tek doğrudan stderr yazımı dener:

```json
{"level":"ERROR","logger":"app.logging","message":"log emission failed","context":{"error_code":"logging_output_failed"}}
```

Bu acil kayıtta kasıtlı olarak **`ts` yoktur**; toplayıcı onu uygulama olay
zamanı varmış gibi yorumlamamalı. Gerekirse kendi alma zamanını ayrı alan
olarak tutar. Handler aynı handler'a yeniden girişi düşürür; fallback için
yeni logging çağrısı yapmaz ve `logging.raiseExceptions` genel ayarını
değiştirmez. Fallback'in kendi ordinary hatası da yutulur. `KeyboardInterrupt`
ve `SystemExit` kontrol sinyalleri korunur. Bu mekanizma bloke bir stream için
hard-wall timeout veya her third-party handler için koruma değildir.

Operatör bu olayı gördüğünde günlük çıktısının eksik olabileceğini kabul
etmeli; olay yokluğunu başarılı istek saymamalıdır. Collector/disk/pipe
sağlığını, hata kodunu ve ilgili deployment kaynak sürümünü kontrol eder.
Tanı için ham exception/prompt/token çıktısını yeniden açmak yerine izinli
özet ile bağımsız readiness ve iş durumu görünümünü kullanır. Collector'ın
`exception` nesnesini ve zaman damgasız acil kaydı kabul etmesi dağıtımda
ayrıca doğrulanır. Alarm, erişim, saklama ve silme sahipliği
[olay müdahalesi](../engineering/INCIDENT_RESPONSE.md) ve
[SLO sınırları](../engineering/SLO.md) ile birlikte karara bağlanır.

## Ölçülmüş kabulün kapsamı

[S9 yerel arşivi](../../specs/018-codex-production-line/evidence/s9-local/README.md)
eski/eksik kolların kırmızı sonuçlarını da korur. S9 testleri eski 18 FAIL,
aday 18 PASS, errors-only 18 FAIL, formatter-only 14 PASS/4 FAIL; S9B
eski 2 PASS/33 FAIL, aday 35 PASS; S9C eski 8 PASS/19 FAIL, aday 27 PASS
verdi. Başarısız testlerin bir kısmı olay/context şeması, destek kimliği,
yeniden giriş veya hata yanıtı dayanıklılığıdır; test adedi sızıntı adedi
değildir. Üç ayrı aşamanın 18+35+27 sonucu, son birleşik sürümde tek 80-test
koşusu olarak sunulmaz.

İlk birleşik sürümde 1651 API testi ve 38 alt vaka geçti. Sonraki bağımsız
inceleme, exception context'indeki destek kimliğinde bilinen regex maskesinin
atlandığını buldu; `redact(request_id)` geri getirildi. Bu ilk tam sonuç
düzeltme öncesine aittir. Ek kimlik canary'leriyle son birleşik/tam API
sonucu ve yeni commit'in uzak kabulü ayrıca kaydedilir.

Uvicorn 0.52.4 ile current/S9/S9B/S9C dört kolda 16 gerçek süreç senaryosu
17.270648 saniyede geçti. h11 ve httptools hata istekleri ile startup/shutdown
hataları karşılaştırıldı; 20 gerçek yerel HTTP yanıtının gövde hashleri ve
zarf sözleşmesi eşleşti. Eski kolun dört senaryosunda, S9'un yalnız iki
lifespan senaryosunda bulunan dört özel sentetik işaret S9B/S9C'de yoktu.
DB, outbound socket, embedding ve LLM deneme sayaçları sıfırdı. Bu süreç
deneyi sağlıklı sink kullanır; bozuk sink farkı ayrı 27 S9C testiyle ölçüldü.

On altı süreçte yapılandırma öncesi toplam 32 standart INFO başlangıç satırı
vardı; bunlar JSON değildi ve fixture işareti içermiyordu. Startup failure
exit 3, shutdown failure exit 0 ile sonuçlandı; ikinci durumda failed olayı
korundu, shutdown-complete olayı oluşmadı. Çıkış 0 tek başına başarılı
uygulama kapanışı değildir. Gerçek deployment, bütün startup hataları,
collector/sink arızası, gerçek sağlayıcı veya hukukî uygunluk bu dar yerel
kanıtın dışındadır.

Son S9 yerel birleşik doğrulama: takip kimliği maskeleme düzeltmesi dahil 1655 API testi ve 38 alt vaka geçti; yeni 84 kontrol bu tam koşuya dahildir. Ayrı dört kimlik regresyon vakası eski kaynakta başarısız, düzeltmede başarılı oldu. Önceki 1651 sonucu ve aşamalı karşılaştırmalar tarihsel olarak korunur. Kesin yeni commit’in GitHub kabulü ayrıca kaydedilecektir.
