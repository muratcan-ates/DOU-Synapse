# Service Level Objectives

Bu belge öğrencinin ve eğitmenin kritik yolculukları için SLI, hedef, pencere,
error budget, uyarı ve sahiplik sözleşmesini tanımlar. Buradaki hedefler mevcut
production performansı iddiası değildir.

> **Durum:** Tüm SLO'lar `planned / unmeasured` durumundadır. Repository'de
> `/health/live` ve `/health/ready`, yapısal request/ingestion kayıtları ve yerel
> ölçüm araçları vardır; production monitor, güvenilir event collector,
> dashboard, alert delivery ve on-call route bu turda yapılandırılmamış veya
> gözlenmemiştir. Yerel ya da fake-provider sonucu production SLI verisi olmaz.

`.github/workflows/keepalive.yml` yalnız zamanlanmış readiness smoke'udur.
Gerekli hedef yapılandırılmadıysa yeşil geçmez, açıkça kırmızı olur; buna
rağmen düzenli dış monitor, denominator, data-quality kontrolü, alert delivery
ve on-call bağı olmadığı için uptime ya da SLO kanıtı sayılmaz.

## Yayınlama kuralı

Bir SLO ancak aşağıdakilerin tamamı bağlıysa `measured` durumuna geçebilir:

- exact environment ve service adı;
- SLI sorgusu ya da sentetik probe tanımı;
- denominator, success/failure ve exclusion kuralları;
- ölçüm penceresi, target ve data-quality kontrolü;
- privacy/retention kararı;
- alert route, owner ve çalışan runbook;
- gerçek event üzerinde gözlenmiş dashboard ve alert teslim kanıtı.

Eksik, gecikmiş veya duplicate event'leri başarı kabul etme. Veri kalitesi
ölçümü geçmiyorsa pencere `unavailable` olur; error budget tüketimi `0` olmaz.

## Planlanan SLO kataloğu

Sayılar aday hedeflerdir. Telemetry devreye alındıktan sonra baseline görülmeden
mevcut performans diye sunulamazlar.

### SLO-READY - Servis hazırlığı

| Alan | Tanım |
|---|---|
| Yolculuk | Web/API isteğinin hazır backend'e ulaşabilmesi |
| SLI | Geçerli production `/health/ready` probe'larının başarılı olan yüzdesi |
| Başarı | Beklenen environment/deployment kimliğiyle zamanında HTTP 200 ve bağımlılık readiness sonucu |
| Başarısızlık | Timeout, network hatası, 5xx veya yanlış deployment kimliği |
| Exclusion | Önceden ilan edilmiş bakım yalnız olay akışında işaretliyse; sessiz exclusion yok |
| Aday target/window | Rolling 28 günde en az %99,5 |
| Kaynak | Dış sentetik monitor + deployment digest etiketi |
| Data-quality | Beklenen probe eksikse pencere geçersiz; eksik probe başarı değildir |
| Alert | Hızlı/yavaş error-budget burn veya ardışık readiness kaybı |
| Owner/runbook | Reliability owner / [Incident Response](INCIDENT_RESPONSE.md) |
| Durum | `planned / unmeasured` |

### SLO-CHAT - Kaynak-sınırlı sohbet sonucu

| Alan | Tanım |
|---|---|
| Yolculuk | Yetkili öğrencinin course-scoped sohbet isteğine güvenli ürün sonucu alması |
| SLI | Uygun isteklerin target süre içinde geçerli sonuçla tamamlanan yüzdesi |
| Uygun istek | Auth ve course membership geçen, rate limit/validation dışı istek |
| Başarı | Kaynaklı cevap veya tasarlanmış fail-closed sonuç (`insufficient_context`, `out_of_scope`, blocked) ve target içinde tamamlanma |
| Başarısızlık | Timeout, 5xx, provider zincirinin güvenli sonuç üretememesi, kaynaksız gösterilen cevap veya guardrail ihlali |
| Aday target/window | Rolling 28 günde en az %99 geçerli sonuç; p95 en fazla 10 saniye |
| Kaynak | Privacy-safe request event'i + edge/API latency + AI artifact/change ID |
| Data-quality | Serbest soru/cevap metni tutulmaz; eksik status veya artifact etiketi pencereyi geçersiz yapar |
| Alert | 5xx/provider failure burn, citation/guardrail hard stop veya latency burn |
| Owner/runbook | AI + reliability owner / [AI SDLC](AI_SDLC.md), [Incident Response](INCIDENT_RESPONSE.md) |
| Durum | `planned / unmeasured` |

Fail-closed ve doğru sınıflanmış ret, erişilebilirlik bakımından başarıdır; AI
kalitesi bakımından ayrıca ölçülür. Bu ayrım, sistemin uydurulmuş cevap vererek
availability metriğini yükseltmesini engeller.

### SLO-INGEST - Yüklemeden aranabilirliğe

| Alan | Tanım |
|---|---|
| Yolculuk | Eğitmenin kabul edilen materyali aynı ders içinde aranabilir hale getirmesi |
| SLI | Desteklenen ve kabul edilen upload'ların target içinde `completed` olup sentetik retrieval probe'unda görünme yüzdesi |
| Başarı | Aynı document/source version için ingestion tamamlanır, embedding-space uyumludur ve course-scoped probe ilgili chunk'ı bulur |
| Başarısızlık | Stuck/failed job, timeout, yanlış embedding space, tamamlandı görünüp aranamaz olma |
| Exclusion | Validation'da reddedilen desteklenmeyen/bozuk dosya; kabul edilmiş iş sessizce çıkarılamaz |
| Aday target/window | Rolling 28 günde en az %95'i 5 dakika içinde aranabilir |
| Kaynak | `ingestion_jobs` zamanları + document/chunk provenance + sentetik course-scoped probe |
| Data-quality | Job ve probe aynı course/document/version kimliğine bağlı olmalı |
| Alert | Queue age veya failed/stuck oranı target'ı yakacak biçimde yükselir |
| Owner/runbook | Ingestion + reliability owner / [Incident Response](INCIDENT_RESPONSE.md) |
| Durum | `planned / unmeasured` |

### SLO-EXAM - Sınav gönderimi dayanıklılığı

| Alan | Tanım |
|---|---|
| Yolculuk | Öğrencinin kabul edilen sınav cevabının tekil ve kalıcı kaydedilmesi |
| SLI | Başarılı kabul yanıtı verilen submission'ların target içinde aynı request kimliğiyle tek kayıt olarak okunabilme yüzdesi |
| Başarı | Yetkili attempt'e ait cevap tam bir transaction ile bir kez persist edilir ve doğrulama okumasında görünür |
| Başarısızlık | Kabul yanıtından sonra kayıp, duplicate, yanlış attempt/course bağı veya yetkisiz görünürlük |
| Aday target/window | Rolling 28 günde en az %99,9'u 5 saniye içinde kalıcı ve tekil |
| Kaynak | Privacy-safe request ID + API sonucu + database persistence/audit event'i |
| Data-quality | Request ve attempt kimliği eşleşmeli; cevap içeriği telemetry'ye kopyalanmamalı |
| Alert | Onaylanmış herhangi bir kayıp, duplicate veya isolation ihlali incident açar |
| Owner/runbook | Assessment + reliability owner / [Incident Response](INCIDENT_RESPONSE.md) |
| Durum | `planned / unmeasured` |

## Error budget sözleşmesi

Bir SLO için pencere geçerliyse:

```text
allowed bad events = eligible events * (1 - target)
budget consumed    = observed bad events / allowed bad events
```

Time-based readiness için aynı hesap bad minutes/probes üzerinden yapılır.
Event yokluğu ve ölçüm yokluğu farklıdır: denominator sıfırsa sonuç
`insufficient traffic`, event kaynağı eksikse `unavailable` yaz.

Karar politikası:

- Constitution veya R3 hard-stop ihlali, budget yüzdesinden bağımsız incident
  ve rollout durdurma sebebidir.
- Hızlı burn, ilgili deployment/AI rollout'unu durdurur ve incident triage açar.
- Budget tükenirse yalnız recovery, security, compliance ve açıkça onaylı
  zorunlu değişiklikler ilerler; discretionary R2/R3 rollout bekler.
- Budget sağlıklıysa bile release gate, AI kalite kanıtı veya insan onayı
  atlanamaz.

Bu kararların otomatik enforcement'ı henüz yoktur. Workflow/ruleset veya
deployment controller ile yapılandırılana ve kırmızı yol gözlenene kadar
`documented` kalırlar.

## Telemetry gizliliği

- Student ID yerine gereksinime göre scoped pseudonymous identifier kullan.
- Serbest prompt, cevap, sınav cevabı ve yüklenmiş belge içeriğini SLI event'ine
  koyma.
- Course, role, language, mode, change ID ve artifact version gibi yapısal
  alanları kullan.
- Retention süresini data owner ve privacy owner kararı olmadan uzatma.
- Düşük örnek sayılı dilimleri kişi veya küçük sınıfı açığa çıkaracak şekilde
  yayınlama.

## Aktivasyon ve gözden geçirme

Her SLO aktivasyon PR'ı exact query/probe'u, dashboard görüntüsünü, alert testini
ve runbook owner'ını bağlamalıdır. İlk production penceresi tamamlanmadan hedefi
“karşılandı” diye yazma. Hedef değişikliği ADR veya versioned SLO revision ile
gerekçelendirilir; kötü sonuç görüldükten sonra geçmiş pencerenin target'ı
değiştirilmez.

Release promotion ile error-budget ilişkisi
[Release Process](RELEASE_PROCESS.md), scorecard durumu
[Engineering Excellence](ENGINEERING_EXCELLENCE.md) belgesinde izlenir.
