# Ortak istek kotasının işletimi

8 Eylül 2026: 0025 ortak kota kodunun iki gerçek API süreci kabulü
[kendi arşivindedir](../../specs/018-codex-production-line/evidence/d1-http-local/README.md).
`c45e0e7` için dört hosted iş akışı geçti; daha sonraki worker bakım/Compose
değişikliği yeni yerel dilimdir. Aşağıdaki gerçek dönem ölçümü bu dilime bağlıdır.
Bu belge canlıya alım onayı veya saklama süresi taahhüdü vermez.

## Davranış ve sınırlar

Sohbet için varsayılan20 istek/60 saniye, soru üretimi için5 istek/300 saniye;
anahtar kapsam+kullanıcı+derstir. PostgreSQL bütün API süreçlerinin aynı pencereyi
kullanmasını sağlar. İstek kabulü ayrı kontrol işleminde kesinleşir; sonraki model
hatası veya ana işlemin geri alınması kabul edilmiş hakkı geri vermez. Önbellekten
yanıtlanan veya kapsam nedeniyle reddedilen sohbet de önceki sözleşme gibi sayılır.
Reddedilen kota isteği yeni zaman damgası yazmaz ve saklama süresini uzatmaz.

429 yanıtındaki Retry-After veritabanı kararından gelir; soru üretiminde eski
sabit60 saniye yerine gerçek300 saniyelik pencere dikkate alınır. Veritabanı,
kontrol havuzu veya politika doğrulaması başarısızsa sabit503/rate_limit_unavailable
ve Retry-After1 döner; bu istek sağlayıcıya gönderilmez. Belirsiz COMMIT halinde
tekrar kabul veya yerel bellek sayacına dönüş yapılmaz. Muhafazakâr biçimde
sayılmış olabilecek hak normal pencere sonunda düşer.

Kontrol işleminin dış zaman sınırı1 saniye; SQL kilit sınırı250ms, sorgu sınırı500ms.
Sürücü iptal/bağlantı temizliği ek süre alabilir: bunlar yapılandırma sınırlarıdır,
ölçülmüş duvar saati hizmet garantisi değildir. Mevcut kontrol havuzu diğer token
ve koruma işlemleriyle paylaşılır; çok makine yük/kapasite kabulü ayrıca gereklidir.

Bu değişiklik istek sayısını paylaşır. Sohbetin mevcut kalıcı sağlayıcı eşzamanlılık
kontrolü ve token rezervasyonları ayrıca çalışır. Soru üretiminin aktif iş sayısı
kontrolü süreç içindedir; ortak istek sayacı bunu dağıtık bir iş kilidine dönüştürmez.

## İlk geçiş ve geri dönüş

Eski bellek sayacını kullanan bütün API işçileri ve bu uçlara ulaşabilecek arka plan
işleri durdurulmadan ortak kota etkin sayılmaz. Yeni kodun politika parmak izi eski
kodu yeni işlevi çağırmaya zorlayamaz. Eski ve yeni sürümler karışık çalışırsa toplam
L sınırı garantisi yoktur. İlk geçişte kabul trafiği durdurulur, eski işler boşaltılır,
göç uygulanır, bütün yeni işçiler aynı politika ile başlatılır ve readiness doğrulanır.

Geri dönüş ortak kabulü kaldırıyorsa AI girişini durdurmak gerekir. Ortak kabulü
koruyan ileri düzeltme tercih edilir. Hata sırasında sessiz bellek sayacına geçiş
veya canlı pencere silerek trafiği açma bu tasarımın parçası değildir.

## Politika değişikliği

`app.request_rate_policies` yetkili politika kaynağıdır; uygulamanın kapsam, limit
ve milisaniye pencere ayarı bununla eşleşmelidir. Parmak izi bütçenin anahtarına
katılmaz. Farklı ayarlı işçi yeni kullanıcıda bile503 alır; farklı parmak izli eski
pencere de temizlenene kadar kapalı kalır. Uygulamada politika değiştirme veya
kota sıfırlama ucu yoktur. Readiness yalnız okur, sahte kullanıcı penceresi açmaz.

1. Etkilenen sohbet/soru üretim girişlerini durdurun ve bütün eski işleri boşaltın.
2. Son olası kabulden sonra eski ve yeni pencereden büyük olan süreyi bekleyin.
   Son kabul zamanı bilinmiyorsa süreyi kesin duruş anından başlatın.
3. Süresi dolmuş satırları sınırlı bakım çağrılarıyla temizleyin; ilgili kapsamda
   pencere kalmadığını doğrulayın. Hâlâ canlı pencereyi silmeyin.
4. İncelenmiş yönetici işlemiyle kanonik politikayı ve bütün işçi ayarlarını birlikte
   güncelleyin. Readiness başarılı olduktan sonra trafiği açın.

Kesintisiz çevrimiçi politika göçü doğrulanmış değildir. Yapılandırma1ms hassasiyet,
1–100 istek ve1ms–3600s pencere sınırlarını uygular; sıfır/sonlu olmayan değerler reddedilir.

## Yetki ve kişisel veri

SQL aktörü `app.current_user_id()` üzerinden alır; istemcinin kullanıcı kimliği
parametresi yoktur. Aktif ders üyeliği ve soru üretiminde eğitmen rolü tekrar
denetlenir. Kısa FOR SHARE kilidi bu kararı kabul işlemi sonuna kadar tutarlı kılar.
Bu, daha önce kabul edilmiş bütün sağlayıcı işlerinin rol iptalinde duracağı iddiası
değildir; mevcut sınav ve veri yaşam döngüsü kontrolleri ayrıca gereklidir.

RLS etkin tablolara uygulama ve işleyici doğrudan erişemez. Sabit search_path ve
tam nitelikli nesne adları kullanan işlevlerin PUBLIC yetkileri kaldırılmıştır.
dou_app kabul ve kişisel olmayan politika görünümünü kullanır; dou_worker yalnız
sınırlı süre sonu temizliği çağırır. Mevcut güvenilir DB kimlik bilgisi/GUC modeli
geçerlidir; keyfî uygulama DB kimlik bilgilerine sahip saldırgan için ek kimlik
doğrulaması sağlandığı iddia edilmez. SQL işlevi kendi başına otonom COMMIT yapmaz;
dayanıklılığı API'nin ayrı kontrol işlemi sağlar.

Kullanıcı/ders kimlikleri, kabul zamanları ve sona erme zamanı takma kimlikli kişisel
kullanım verisidir. Soru, yanıt, belge adı, IP, JWT veya HTTP başlığı tutulmaz.
Profil/derste gerçek silme FK ile yayılır. Profil anonimleştirme işlemi profili
tutabiliyorsa bu satırları hemen fiziksel olarak silmez; üyelik iptali yeni kullanımı
engeller, süre sonu bakımı siler. Sınırlı kullanıcı JSON dışa aktarımı bu operasyonel
kayıtları içermediğini açıkça bildirir. Yedekler ayrı saklama politikasına tabidir.

## Süre sonu bakımı ve açık işletim kabulü

`purge_expired_request_windows` yalnız DB saatine göre sona ermiş satırları siler;
batch1–1000, SKIP LOCKED ve tek lider için advisory try-lock kullanır. Yardımcı
işlev sayıyı COMMIT sonrası döndürür; ham DB hataları loglanmaz. Silme fiziksel olarak
ancak başarılı bakım gerçekleştiğinde olur. Mantıksal sona erme anı silme taahhüdü değildir.

Bağımsız worker başlangıçta ve çalıştığı sürece60 saniyelik beklemeler arasında
en çok500 satır için bakım çağırır. Bu görev ingestion işleminden ayrıdır; bakım
hatası mevcut belge işini iptal etmez. Başarı kaydı yalnız COMMIT sonrasında
`stage`, `deleted_windows`, `duration_ms` alanlarını içerir; sıfır sonuç bütün
expired satırların bittiğini kanıtlamaz. `/internal/drain` çağrısı tek başına
sürekli bakım zamanlayıcısı değildir.

8 Eylül `quota-period-02` gerçek bağımsız süreç deneyinde başlangıç silmesi
0.544 saniyede gözlendi. Bu COMMIT'ten sonra eklenen yeni expired satır 59.973
saniyede hâlâ vardı; 60.181 saniyede silinmişti. Canlı pencerenin byte'ları aynı
kaldı; kendi SIGTERM kapanışı kod 0 ve 0.086 saniyeydi. Saat/60 saniye sabiti
değiştirilmedi. Ölçülen worker SHA'sı `2cdbea27191cadd0bd2d73f88857b3e461122bdde0f4bdebc98f606771b7a634`;
bu `c45e0e7` sonrası yerel kaynak deneyidir, o commit'in hosted sonucu değildir.
İlk koşudaki eksik yerel auth yapılandırması başarısız kayıt olarak korunur.
Docker, dış zamanlayıcı veya fiziksel retention SLA'sı bu deneyde ölçülmedi.

Yerel Compose HTTP worker'ı korur ve ayrıca HTTP portu olmayan `worker-poller`
başlatır; yerel auth ayarı açıkça tanımlıdır. Worker Settings doğrulamasını görev
yaratmadan yapar, bozuk yapılandırmada sabit hata ve çıkış 1 üretir. Bu süreç
başlangıcının fail-closed kontrolüdür; üretimde dev-auth yine yasaktır.

İşçi uyutulan barındırmada dış zamanlayıcı gereklidir. Barındırma hedefi, zamanlayıcı,
başarısız bakım uyarısı ve kurumun saklama süresi belirlenmeden fiziksel TTL hizmet
garantisi verilemez. İzleme yalnız kapsam/karar/süre gibi düşük çeşitlilikli toplamlar
tutmalı; kullanıcı/ders kimliği veya içerik telemetri etiketi olmamalıdır.
