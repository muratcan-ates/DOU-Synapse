# Tehdit Modeli: API Observability

## Varlıklar ve güven sınırları

- Öğrenci/eğitmen içeriği ve kimliği: telemetri sınırının dışında kalmalıdır.
- Destek kodu: kişisel değildir ama erişim korelasyonu sağlayan bounded operatör verisidir.
- Platform admin yetkisi: ders eğitmenliğinden ayrı ve DB'de yeniden doğrulanır.
- Runtime DB credential: trusted backend kimliğidir; kullanıcı GUC'si bunun yerine geçmez.
- Telemetri kuyruğu: best-effort gözlem katmanıdır, ürün doğruluk kaynağı değildir.

## Abuse yolları ve kontroller

| Tehdit | Kontrol | Kanıt |
|---|---|---|
| Path UUID/query/body telemetriye sızar | Yalnız router template; şemada hassas kolon yok | Unit + DB field-set negatif |
| Kullanıcı admin endpoint'ini çağırır | PlatformAdminDep + audit + SQL iç re-check | API + RLS/mutasyon |
| Carrier/worker event yazar/okur | Exact runtime recorder; tablo ACL yok | Direct SQL negatif |
| Sahte event geniş/metin payload taşır | Batch/enum/regex/length/status/duration SQL doğrulaması | Mutation/invalid batch |
| Telemetri hatası API'yi düşürür | `put_nowait`, bounded queue, exception containment | Persist/down/full queue test |
| Canlı panel kendi metriğini şişirir | `/admin`, `/health`, `OPTIONS` exclusion | Route helper + browser count |
| Ham exception/stack admin'e çıkar | Yalnız bounded outcome code; ErrorEnvelope | 500/API response set testi |
| Migration-first pencerede eski API legacy request ID yollar | Fonksiyon raw değeri saklamadan server 32-hex koda çevirir | Mixed-version SQL testi |
| Swagger production'da saldırı yüzeyi olur | Production docs/openapi fail-closed | Config + route smoke |
| Retention büyümesi disk/DB'yi tüketir | 1–30 gün, expires index, bounded purge | SQL purge testi + runbook |
| Yerel snapshot SLO diye sunulur | UI/docs explicit “snapshot, SLO değil” | Copy/browser review |

## Kabul edilen sınır

Gerçek `dou_api_runtime` credential'ı trusted backend sırrıdır. Bu özellik, ele
geçirilmiş runtime credential'ını sandbox'layan yeni bir proxy kurmaz. Buna karşılık
öğrenci/eğitmen token'ı, `dou_app` carrier veya `dou_worker` rolü event tablosuna ve
admin projection'a erişemez.
