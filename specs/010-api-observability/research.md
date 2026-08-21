# Araştırma ve Kararlar

## 1. Mevcut panel mi, yeni panel mi?

Mevcut `/admin` gerçek verili, server-verified `AdminGate`, çift SQL yetki kontrolü,
audit ve E2E kanıtına sahiptir. Yeni dashboard kurmak hem yetki yüzeyini çoğaltır hem
de `feature/role-admin-panels` atasını yanlışlıkla yeniden taşır. Karar: mevcut paneli
genişlet.

## 2. `request_logs` neden kullanılmıyor?

Bu tablo chat outcome/token/cache ölçümüdür ve yalnız tamamlanan sohbet turlarında
yazılır. Genel API 4xx/5xx veya route latency kaynağı değildir. Karar: ayrı,
content-free `api_request_events`.

## 3. Neden ayrı endpoint ve POST?

`/admin/overview` ucuz, sabit platform özeti olarak kalır. Olay sorgusu filtreli,
sayfalı ve destek kodu taşır. POST destek kodunu query/access logundan uzak tutar;
ayrı uç sorgu maliyetini ve anlamını ayırır.

## 4. Neden background task değil bounded worker?

Her cevap için sınırsız task/ayrı transaction yük altında bağlantı ve task fırtınası
üretebilir. Tek bounded queue, tek writer ve küçük batch backpressure'ı gözlem
katmanında tutar. Dolu queue olay düşürür; kullanıcı yanıtını asla bekletmez.

## 5. Neden ham Swagger panelde yok?

Bilgi İşlem paneli insan operasyon yüzeyidir; keyfî write çağrısı rol/CSRF/hata riskini
artırır. Developer etkileşimi doğru Bearer security ve doğru ErrorEnvelope ile yerel
Swagger'da kalır. Production docs default kapalıdır.

## 6. SLO dili

Repository SLO dokümanında ölçümler halen `planned/unmeasured`; external collector,
alert ve staging/prod kanıtı yoktur. Yeni panel “yerel/ortam snapshot'ı” der; error
budget veya production SLO iddiası üretmez.

