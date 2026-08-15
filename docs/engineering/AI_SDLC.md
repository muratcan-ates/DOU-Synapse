# AI değişiklik yaşam döngüsü

Bu belge, DOU-Synapse'te kullanıcıya yansıyan bir AI davranış değişikliğinin
öneriden geri alma penceresinin kapanmasına kadar nasıl yönetileceğini tanımlar.
Amaç bir model cevabını tek başına değerlendirmek değil; değişen artefaktı,
kanıtı, insan kararını ve çalışan sürümü aynı iz üzerinde tutmaktır.

> **Kanıt sınırı (2026-08-11):** Başlangıç SHA'sı `2c178861` sürümlü
> değerlendirme kümeleri, retrieval sonuçları, guardrail'ler ve core CI
> kontrolleri içeriyor; `.ai/` manifest kapısı içermiyordu. Bu feature branch
> working tree'sinde `.ai/policy.json`, `.ai/schema.json`, validator/testleri ve
> `.github/workflows/ai-quality.yml` artık repo-configured durumdadır. Bu turda
> workflow run'ı, required-check enforcement'ı, gerçek sağlayıcı, canary veya
> production gözlemi yapılmadığı için kontrol `enforced` ya da `observed`
> değildir.

## Kapsam ve yönlendirme

Bu süreç aşağıdaki artefaktlardan biri değiştiğinde uygulanır:

- sağlayıcı, model veya sabit model revizyonu;
- sistem/ürün prompt'u, araç şeması ya da araç yetkisi;
- chunking, embedding uzayı, retrieval, sıralama veya kanıt eşiği;
- citation, kapsam, leakage, sanitization veya sınav guardrail'i;
- evaluator, rubric, kalibrasyon/holdout kümesi veya karar eşiği;
- davranışı açan feature flag, fallback ya da provider routing kuralı.

Retrieval, grounding, citation, abstention, Sokratik davranış ve sınav geri
bildirimi metriklerinin ayrıntılı ölçümü RAG değerlendirme sürecine aittir. Tek
bir release adayının tüm repo ve production kapıları ise release doğrulama
sürecine aittir. Bu belge, o kanıtların hangi AI değişikliğine bağlandığını ve
hangi koşulda terfi kararı üretebildiğini yönetir.

## Değişiklik kaydı ve lineage

Her AI davranış değişikliği için tek bir dossier aç. Dossier en az şunları
içermelidir:

| Alan | Zorunlu içerik |
|---|---|
| Kimlik | Benzersiz change ID, sorumlu, oluşturma ve gözden geçirme tarihi |
| Revision zinciri | Sabit `lineage_id`, artan `revision`, önceki base kaydının yolu ve SHA-256'sı ile `supersedes`, önceki durum |
| Kaynak | Base SHA, candidate SHA, PR ve hedef ortam |
| Amaç | Etkilenen kullanıcı yolculuğu, hipotez ve korunacak davranışlar |
| Davranış kimlikleri | Provider, model, prompt, tool schema, guardrail, retrieval, embedding ve evaluator revizyonları |
| Veri artefaktları | Corpus ve eval-set digest'leri ile gizlilik sınıfı |
| Değerlendirme | Baseline/candidate metrikleri, operatör, önceden ilan edilmiş eşik, örnek sayısı ve exact komut |
| Kanıt | Ortam etiketi, hash-bound rapor yolu/digest'i, candidate kimliği ve sonuç |
| İnsan kararı | Rol, adlandırılmış actor, immutable review ref, karar zamanı, candidate SHA ve yazar bağımsızlığı |
| Deployment | Feature flag durumu, candidate SHA, deployment kimliği ve ortam |
| Rollout | Başlangıç kohortu, sticky atama, kill switch, genişletme/durdurma koşulları ve aktif sınav politikası |
| Rollback | Önceki uyumlu artefakt, bounded prosedür ve candidate/deployment/report hash'ine bağlı doğrulama |

İz zincirini şu sırayla koru:

```text
source/corpus -> embedding/index -> retrieval policy -> prompt/tool contract
-> provider/model -> evaluation run -> human approval -> artifact digest
-> environment -> privacy-safe telemetry -> keep/expand/rollback decision
```

Mutable model alias'ı, yalnız sağlayıcı panelinde yapılan değişiklik, hash'siz
corpus, kaydedilmemiş eşik veya başka candidate SHA'ya ait rapor
tekrarlanabilir kanıt değildir. Bunlardan biri varsa promotion'ı durdur.

Dossier ve kanıt raporları append-only'dir. Yeni revision, değiştirdiği kaydı
reviewed base içinde bulmalı; aynı `lineage_id`'yi korumalı; revision'ı tam bir
artırmalı ve `supersedes.path` ile o base dosyasının gerçek SHA-256'sını
eşlemelidir. Bir parent'ın birden fazla child'ı, aynı revision'ın iki kaydı,
lineage değişimi, sıra atlama, durum atlama, risk düşürme veya geçmiş dosyayı
yeniden yazma fail closed olur. Düzeltme eski dosyayı değiştirmek değil, yeni
immutable revision eklemektir.

Öğrenci prompt'u, cevap metni, JWT, e-posta veya yüklenmiş belge içeriğini
dossier'e varsayılan olarak koyma. Gereken incelemeyi kimliksiz örnek kimliği ve
ayrı, süreli erişimle bağla.

Makine sözleşmesinin ürün gereksinimi için
[AI change dossier contract](../../specs/004-ai-sdlc-excellence/contracts/ai-change-dossier.md)
belgesini, repo-configured kullanım için
[AI governance README](../../.ai/README.md) belgesini kullan. Dosyaların varlığı
promotion kararı değildir; validator'ın exact reviewed diff üzerinde koşması ve
GitHub ruleset'in bu sonucu gerçekten zorunlu tutması ayrıca kanıtlanır.

## Risk sınıflandırması

En yüksek eşleşen sınıfı uygula. Etki veya geri alma belirsizse bir üst sınıfa
çık.

| Risk | Kapsam | Asgari bağımsız karar | İlk exposure sınırı |
|---|---|---|---|
| `R1` | Metadata, gözlemlenebilirlik veya davranış/karar/veri sınırını değiştirmeyen sunum | Yazar dışı peer | Geri alma anlıksa normal kontrollü rollout |
| `R2` | Model, prompt, provider, retrieval, embedding, guardrail, evaluator, maliyet veya gecikme davranışını değiştirir | Engineering owner + course/product owner | İç ekip/eğitmen pilotu, sonra küçük sticky kohort |
| `R3` | Notlandırma, sınav bütünlüğü, öğrenci gizliliği, ders izolasyonu, autonomous write/tool, provider residency veya zor geri alınan veri/index etkisi | Engineering + domain owner + ilgili security/privacy owner | Açıkça adlandırılmış kohort; aktif sınav dışarıda |

Yazar, `R2` veya `R3` için tek onaylayıcı olamaz. Risk düşürmek için aynı kaydı
sessizce değiştirme; yeni candidate ve gözden geçirilmiş dossier üret.

## Kanıt seviyeleri

| Etiket | Kanıtladığı şey | Kanıtlamadığı şey |
|---|---|---|
| `fake-provider` | Şema, deterministik control flow ve hata yolları | Gerçek model kalitesi, maliyet veya latency |
| `offline-replay` | Kayıtlı girdilerde yeniden üretilebilir karşılaştırma | Güncel provider ve canlı entegrasyon |
| `real-provider` | Kaydedilmiş model/revizyon/ayarlarla gerçek model davranışı | Auth, storage, network ve deployment bütünlüğü |
| `staging` | Entegre staging davranışı | Production kullanıcı veya yük davranışı |
| `canary` | Sınırlı gerçek exposure altında operasyon sinyali | Tam rollout güvenliği |
| `production` | Belirtilen digest ve zaman aralığında gözlenmiş canlı davranış | Başka SHA, provider revizyonu veya dönem |

Karşılaştırmadan önce beklenen kazanımı, korunacak boyutları, kalibrasyon
kuralını ve hard-stop eşiklerini yaz. Baseline ile candidate'ı aynı sürümlü
girdilerde çalıştır ve kasıtlı farkların tamamını kaydet. Kalibrasyon ile
holdout'u karıştırma.

Evaluator değişiyorsa yeni evaluator kendi değişikliğinin tek hakemi olamaz.
Eski değerlendirme ile yan yana ölçüm ve sabit, insan tarafından gözden
geçirilmiş anchor örnek gerekir. Negatif sonuçları ve reddedilen varyantları
silme; sonuç görüldükten sonra eşik değişirse bunu yeni karar revizyonu olarak
kaydet.

Deterministik CI kanıtı normal PR'larda yararlıdır fakat production AI iddiası
için yeterli değildir. Production terfisi, aynı candidate'a bağlı güncel gerçek
sağlayıcı kanıtı ve gerekli bağımsız insan kararları olmadan kapalı kalır.

## Yaşam döngüsü

```text
draft -> evidence-ready -> awaiting-approval -> canary -> expanded -> closed
   \----------\---------------\------------\---------> rolled-back -> closed
```

- `draft`: lineage veya risk alanlarından en az biri eksik.
- `evidence-ready`: Önceden ilan edilen deterministik ve kalite kanıtı bağlı.
- `awaiting-approval`: Risk sınıfının istediği bağımsız karar bekleniyor.
- `canary`: Sınırlı exposure başladı; genişletme ve stop koşulları değiştirilemez.
- `expanded`: Kararlaştırılan exposure tamamlandı; gözlem penceresi açık.
- `rolled-back`: Candidate devre dışı; hash-bound rollback raporu candidate ve
  deployment kimliğine bağlı; önceki davranış doğrulandı.
- `closed`: Yalnız aşağıdaki production-success veya rollback-before-production
  dallarından biri makine sözleşmesini sağladığında kapanır.

İzin verilen exact geçişler şunlardır; aynı durumda yeni immutable revision
kalabilir, fakat durum geriye alınamaz:

| Önceki durum | İzinli yeni durumlar |
|---|---|
| `draft` | `draft`, `evidence-ready`, `rolled-back` |
| `evidence-ready` | `evidence-ready`, `awaiting-approval`, `rolled-back` |
| `awaiting-approval` | `awaiting-approval`, `canary`, `rolled-back` |
| `canary` | `canary`, `expanded`, `rolled-back` |
| `expanded` | `expanded`, `closed`, `rolled-back` |
| `rolled-back` | `rolled-back`, `closed` |
| `closed` | `closed` |

`canary` durumu en az passing `real-provider` ve `canary` kanıtını, candidate'a
bağlı gerekli tüm bağımsız onayları, canary ortam/flag kimliğini gerektirir.
`expanded` en az passing `real-provider` ve `production` kanıtını, production
deployment kimliği ile enabled flag'i ve `production-ready` kararını gerektirir.
Bir alanı yalnız metinle doldurmak bu durumlardan hiçbirini üretmez.

`closed` iki ayrı ve birbirine karıştırılmayan son dal kabul eder:

1. **Production success:** aynı candidate için passing `real-provider` ve
   `production` kanıtı, risk rollerinin immutable ve adlandırılmış onayları,
   `production-ready/production` kararı, production deployment kimliği ve
   enabled flag birlikte vardır.
2. **Rollback before production:** promotion `none/none`, flag disabled,
   rollback durumu `verified-before-production` ve passing rollback raporu
   exact candidate, deployment kimliği, rapor yolu ve SHA-256 ile bağlıdır.

Production'a çıktıktan sonraki doğrulanmış rollback, `rolled-back` durumunu
kanıtlayabilir; ancak validator'ın `closed` rollback dalı özellikle
rollback-before-production içindir. Production sonrası kapanış için yeni,
uyumlu bir revision ve production-success şartları gerekir.

Eksik, skipped veya stale kanıtı başarı sayma. Dossier durumu, bir GitHub review
veya protected-environment approval yerine geçmez.

## Canary ve promotion

1. Versioned feature flag, kill switch ve güvenli fallback tanımla.
2. Offline/shadow kanıtından iç ekip veya eğitmen pilotuna geç.
3. Atamayı deterministik ve sticky tut; aynı oturumda model/prompt/rubric
   değiştirme.
4. Aktif sınav girişimini hiçbir canary varyantı arasında bölme. Yüksek riskli
   değerlendirme yüzeyini ayrıca onaylanana kadar hariç tut.
5. Önceki embedding index'ini veya diğer uyumluluk-kritik artefaktı rollback
   penceresi kapanana kadar koru.
6. Önceki aşamanın eşikleri karşılanmadan exposure artırma.

Canary için gerekli rollerin adlandırılmış, immutable review referanslı ve exact
candidate'a bağlı onayları zorunludur. Dossier içindeki `pending` alan ya da
yazarın kendi beyanı protected review/Environment kararının yerine geçmez.

Stop, rollback ve expand koşullarını canary başlamadan yaz. Canary gözlemi,
pre-deployment değerlendirmesinin yerine geçmez.

## Monitoring ve rollback

Her AI isteğinin privacy-safe trace'ine change ID, artefakt sürümü, provider/model
revizyonu, course/language/role/mode dilimi ve sonuç sınıfını bağla. Serbest
öğrenci metnini varsayılan telemetry alanı yapma.

En az şu sinyaller için karar kuralı tanımla:

- kaynaksız cevap, yanlış citation, scope/refusal ve sınav guardrail ihlali;
- provider hata/fallback, latency, token ve maliyet sapması;
- retrieval veya embedding-space uyumsuzluğu;
- evaluator ile insan anchor arasındaki sapma;
- ders, dil, rol veya mod diliminde örnek sayısıyla birlikte kalite düşüşü.

Her eşik için eylemi önceden seç: rollout'u durdur, flag'i kapat, otomatik geri
al veya insan kararı iste. Citation, scope, authorization ya da exam korumasını
atlayan fallback kullanma; güvenli yol yoksa fail closed davran.

Rollback sonrasında yalnız flag durumuna bakma. Önceki model/prompt/index
uyumluluğunu, temel kullanıcı akışını ve telemetry etiketini yeniden doğrula.
Olay veya hata bütçesi etkisi varsa
[Incident Response](INCIDENT_RESPONSE.md) ve [SLO](SLO.md) kayıtlarına bağla.
Artifact promotion ve uygulama geri alma ayrıntıları
[Release Process](RELEASE_PROCESS.md) belgesindedir.

## Bu slice sonunda açık kalanlar

- Machine-readable policy/schema, changed-path validator ve AI workflow repo
  dosyası olarak `configured`; validator yerelde deterministik olarak
  çalıştırılabilir. Bu çalışma ağacı henüz immutable commit/candidate kimliğine
  bağlanmadığı için sonuçlar exact GitHub candidate kanıtı değildir.
- AI workflow'unun required check olması dış branch/ruleset doğrulaması ister;
  repository YAML'si enforcement kanıtı değildir.
- Offline validator repo diff'ini, şema/lineage/hash bağlarını ve kanıt
  dosyalarının biçimini doğrular; provider'ı gerçekten çağırdığını, deploy'un
  gerçekleştiğini, GitHub reviewer/Environment kimliğini, ruleset enforcement'ı,
  canary routing'i veya production telemetry'sini kendi başına gözleyemez.
- Gerçek-provider holdout ortamı, anahtarları ve insan onay kaydı yapılandırılmamıştır.
- Canary routing, production telemetry ve kill-switch tatbikatı gözlenmemiştir.
- Bu açıklar kapanmadan bu belge production AI readiness kanıtı olarak kullanılamaz.
