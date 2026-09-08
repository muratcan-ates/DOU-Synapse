# Uygulama günlükleri ve hata tanısı

Bu sözleşme S9 hata/günlük korumalarını ve S10 sunucu destek kimliğini birlikte
anlatır. S9'un tarihsel ölçümleri [kendi kabul kaydında](../../specs/018-codex-production-line/evidence/s9-local/README.md),
S10'un yerel ölçümleri [S10 kaydında](../../specs/018-codex-production-line/evidence/s10-local/README.md)
tutulur. Son uzak kabul f79d8a2'ye aittir; yeni S9/S10 kodunun GitHub'a gönderimi
kullanıcının paylaşım onayını bekler. Bu yerel kanıt üretim log toplayıcısı, alarm
teslimi, kurumsal saklama/imha veya hukuki uygunluk kabulü değildir.

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

Sunucu her HTTP isteğinde bir UUID4 destek kodu üretir; istemcinin `X-Request-ID`
başlığı kimlik kaynağı olarak kullanılmaz. Tek istek içinde request state,
normal yanıt başlığı, hata zarfı ve ilgili denetim kaydı aynı kodu kullanır.
Yeni bir HTTP denemesinin kodu değişebilir. Bu kod kullanıcı kimliği,
yetkilendirme veya işlemi yalnız bir kez uygulama garantisi değildir.

Beklenmeyen hata mevcut 500 durumuyla genel Türkçe
`{error: {code, message, request_id}}` zarfını korur. Bu middleware dışı genel
500 yolunda `X-Request-ID` yanıt başlığı bulunmayabilir; destek kodu gövdede ve
`app.error` kaydındadır. 200/401 yollarının başlıkları ayrıca doğrulanmıştır.

İç `ServerRequestId` tipi yalnız sunucunun UUID4 üretimiyle oluşur. Genel
maskeleme yalnız `app.request`/`app.error` kayıtlarının doğrudan
`context.request_id` alanında ve tam bu iç tipte atlanır. Düz UUID biçimli
metin, alt sınıf, başka logger/alan ve iç içe dict/list/tuple değerleri bu
muafiyeti almaz. Böylece UUID içindeki tesadüfi 11 rakam dizisi destek
korelasyonunu bozmaz; rastgele sayı üretimi tekrar tekrar denenmez.
Bu tip ayrımı keyfi Python çalıştırmaya karşı bir güvenlik sınırı değildir.

İstemci artık bu alana serbest kişisel metin yerleştiremez; fakat destek kodu
aktör, zaman ve yönetim işlemiyle ilişkilendirilebilir. Anonim veri sayılmaz.
Geçmiş platform denetim kayıtları değiştirilmez; `request_logs` tablosuna yeni
bir kimlik sütunu eklenmez. Log tüketicileri yeni kodun istekler arasında tekrar
kullanılmadığını ve geçmiş kodların eski biçimde kalabileceğini hesaba katmalıdır.

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

## Test kayıtlarının sahipliği

Tarayıcı testleri yalnız izinli API origin'i, sentetik aktör ve sabit yönetim
işlemleri için sunucudan dönen kodları özel koşu makbuzlarına kaydeder.
Yönlendirme, yanlış aktör/işlem veya eksik yanıt tamamlanmış sayılmaz. Temizlik
her makbuzun request ID, aktör, işlem, sonuç ve önceden listelenmiş satır
kimliğini birlikte doğrular; boş küme bütün kayıtlara genişlemez.

`run_owned_e2e.py` önceden provision edilmiş özel test hedefini doğrular,
bütün audit satırlarının başlangıç özetini alır ve kendi API/tarayıcı sürecini
başlatır. Web sunucusu yeniden kullanılmaz; yeni derleme açık API adresiyle
çalışır. API gerçek normal kapanışını tamamlamadan son muhasebe yapılmaz.
Eksilen, değişen veya beklenmeyen yeni satır başarısız sonuç üretir ve geniş
silme denenmez. API başlangıç/kapanış hatası test başarısına dönüşmez.

Yerel PostgreSQL ve özel GitHub servisinin provisioning yolları ayrıdır.
GitHub yolu job'un container kimliğini, pinli imajı ve container/host DB
kimliğini karşılaştırır; yalnız kendi yeni sentetik hedefinde mevcut yerel
rol kurulumunu uygular. Yerel sözleşme testleri gerçek Docker/hosted kabulü
sayılmaz. Parola dosyaları arşiv yükleme kapsamının dışındadır.

S10'da 1688 API testi/38 alt vaka, 573 web testi ve ayrı 134 DB/ağsız günlük
kontrolü geçti. Dört gerçek Uvicorn sürecindeki 56 HTTP karşılaştırması ve
iki koşulu gerçek PostgreSQL deneyi ayrı kanıtlardır. İlk tam tarayıcı
koşusunda 71 test geçti; 65 ders/14 audit satırı temizlendi ve korunmuş bir
başlangıç satırı tam özetiyle aynı kaldı. Son controller ve güncel KVKK metniyle
ayrı fresh hedefte 71 test yeniden geçti (92.288 s); korunmuş satırın tam
özeti aynı kaldı ve API normal kapanışı doğrulandı. Sürekli testlerde 14 CI
provisioning ve 11 süreç sözleşmesi de geçti. Son kaynaklar S10 kaydında bağlıdır.
