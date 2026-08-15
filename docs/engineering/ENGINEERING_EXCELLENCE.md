# Mühendislik mükemmelliği scorecard'ı

Bu belge DOU-Synapse'in kalıcı mühendislik işletim sistemini izler. Bir feature'ın
uygulanma kontrol listesi veya tek bir release adayının go/no-go raporu değildir.
Her kontrol için niyet ile gerçek enforcement'ı ayrı gösterir.

## Kanıt durumları

| Durum | Anlamı |
|---|---|
| `documented` | Beklenen davranış ve sahiplik yazılıdır; çalışan kontrol kanıtı yoktur |
| `configured` | Repo veya dış sistemde kontrol tanımlıdır; zorunlu olduğu henüz kanıtlanmamıştır |
| `enforced` | Kontrol ihlali promotion'ı gerçekten bloklar veya test edilmiş policy ile kapanır |
| `observed` | Gerçek bir koşu kontrolün beklenen davranışı ürettiğini göstermiştir |

Bir kontrol prose, checkbox veya plan sayesinde üst duruma çıkmaz. `configured`
durumu `enforced`, geçmiş başka SHA'daki başarılı koşu da mevcut candidate için
`observed` sayılmaz. Eksik telemetry sıfır değildir.

## Feature-branch scorecard'ı

Başlangıç SHA'sı
`2c178861a3e484af8643f999f210db040eb84e68`'dir. Bu kayıt
`2026-08-11T03:43:58+03:00` anında gözlenen, commit'e bağlanmamış feature
working tree'sini anlatır; exact local komut ve sonuçlar
[retained evidence](../../specs/004-ai-sdlc-excellence/evidence/2026-08-11-local-verification.md)
dosyasındadır. Branch push,
PR, GitHub Actions run'ı, ruleset, protected Environment, registry publish ve
cloud deployment henüz kanıt değildir. Repo dosyası eklenen kontroller bu
yüzden en fazla `configured`; yalnız yazılan işletim süreçleri ise
`documented` durumundadır.

### Kontrol kaydı sözleşmesi

Her satır owner ve yazar dışı reviewer, trigger, exact evidence ve gözlem
zamanı, failure policy, bypass/audit yolu, güncel risk, hedef ve next action,
due date ile exception expiry taşır. `Yok` değeri, alanın unutulduğu değil
istisna tanımlanmadığı anlamına gelir. Aşağıdaki tarihler ilk PR review'unda
owner tarafından onaylanacak geçici hedeflerdir; kendiliğinden yetki veya risk
kabulü yaratmaz. `unavailable` dış kanıtı da aynı timestamp'te aranmış fakat bu
repository-only audit'te gözlenmemiş olarak okunur.

| ID / kontrol | Durum | Owner / reviewer | Trigger | Kanıt ve son gözlem | Failure policy | Bypass ve audit | Güncel risk / hedef ve next action | Due / exception expiry |
|---|---|---|---|---|---|---|---|---|
| C01 Core CI | `configured` | Repo owner / CODEOWNER | PR ve `main` push | `.github/workflows/ci.yml`; local ürün kapıları için [retained evidence](../../specs/004-ai-sdlc-excellence/evidence/2026-08-11-local-verification.md); GitHub run: `unavailable` | Bir job hatası workflow'u kırmızı yapar; merge bloklama ruleset'e bağlıdır | Repo içi bypass yok; ruleset bypass/audit `unverified` | Required-check enforcement bilinmiyor / PR açıp run URL'si ve ruleset'i bağla | 2026-08-12 / Yok |
| C02 Type gate | `configured` | API owner / CODEOWNER | API lint/type job | `continue-on-error` kaldırıldı; local mypy sonucu retained evidence'da; CI gözlemi `unavailable` | Mypy non-zero job'u kırmızı yapar | Yalnız auditli ruleset istisnası; canlı ayar `unverified` | Negatif CI kanıtı yok / candidate run'da job sonucunu bağla | 2026-08-12 / Yok |
| C03 Container product gates | `configured` | Release owner / Security reviewer | Core image job ve `v*` candidate | Core CI build; release workflow quarantine -> exact digest -> offline embedding/bake/RSS sözleşmesi; canlı image run `unavailable` | Her product-gate hatası admission'ı durdurur | Manual release yolu yok; registry audit/retention `unverified` | GHCR'de admitted digest yok / canlı candidate'ı güvenli tag ile gözle | 2026-08-17 / Yok |
| C04 Documentation truth | `configured` | Docs owner / CODEOWNER | PR ve `main` push | `scripts/docs_check.mjs`; 15 Ağustos working-tree ölçümünde 27 canlı iddia kaynakla eşleşti; GitHub run `unavailable` | Sayaç drift'i non-zero | Ruleset dışı bypass yok; bypass audit `unverified` | Required enforcement bilinmiyor / exact candidate ve PR run URL'sini bağla | 2026-08-15 / Yok |
| C05 Real API/browser E2E | `configured` | QA owner / API+Web reviewer | Core E2E job | 15 Ağustos'ta benzersiz PostgreSQL + gerçek API + Playwright ile 36/36 seri vaka; teardown kalıntısı 0/0 ve korunan `COME 331` yerinde | Setup, test veya teardown hatası job'u kırmızı yapar | Quarantine ancak issue, owner, coverage etkisi ve expiry ile | Çalışma ağacı kanıtı exact candidate/CI taşınabilirliği değildir / PR run, süre ve flake kaydını bağla | 2026-08-15 / Yok |
| C06 PR ownership/evidence | `configured` | Repo owner / CODEOWNER | PR açılması ve sensitive-path diff'i | `.github/CODEOWNERS`, PR template; canlı review/ruleset `unavailable` | Template prose tek başına bloklamaz; ruleset yoksa fail-open riski vardır | Bypass yalnız adlandırılmış aktör, gerekçe ve audit kaydıyla | Code Owner approval/stale dismissal bilinmiyor / live ruleset'i doğrula | 2026-08-12 / Yok |
| C07 AI change governance | `configured` | AI owner / Course+Security reviewer | AI-sensitive reviewed diff | `.ai/` policy/schema; 12/12 uygulama mutasyonu ve 7/7 offline/fake rol-RAG mekaniği yerelde geçti; final R4 exact-candidate bağı ile PR enforcement `unavailable` | Eksik/hash uyuşmaz dossier ve geçersiz state fail closed | R2/R3 yazar bypass'ı yok; gerçek review/audit GitHub kaydı ister | Offline kapı production kalitesini kanıtlamaz / final R4, PR negative run ve ruleset bağla | 2026-08-15 / Yok |
| C08 Supply chain | `configured` | Security owner / Repo owner | PR, schedule ve candidate | Dependabot, Dependency Review, CodeQL, immutable Action policy ve CI'daki pgvector image digest pin'i; local policy sonucu retained evidence'da; GitHub tarama run'ı `unavailable` | Mutable/unresolved Action ve analysis hatası kırmızı; missing run başarı değildir | Geçici istisna owner+gerekçe+expiry ile; aktif istisna yok | Secret/container/license scan eksik / canlı security run'ları ve tarama backlog'unu kapat | 2026-08-17 / Yok |
| C09 Candidate admission/evidence | `configured` | Release owner / Security+Operations reviewer | Event-bound `v*` push | Trusted workflow identity, exact current `origin/main` HEAD, paginated workflow/job kontrolleri ve schema validator repo sözleşmesidir; canlı run `unavailable` | Foreign/manual/duplicate/stale/missing/failed kimlik ve kanıt fail closed | Manual dispatch ve mutable admitted tag yok; tag/registry yetkisi ve audit `unverified` | Canlı admitted evidence artifact'ı yok / negatif ve pozitif tag run'ı gözle | 2026-08-17 / Yok |
| C10 Branch protection | `documented` | Repo administrator / Engineering lead | `main` değişikliği | Repo içinden canlı ruleset okunmadı; gözlem `unavailable` | Required PR/check/review yoksa fail-open | Emergency bypass adlandırılmış aktör+süre+gerekçe+audit ister | Merge enforcement bilinmiyor / live ruleset export'unu kaydet | 2026-08-12 / Yok |
| C11 Protected environments | `documented` | Platform owner / Operations reviewer | Candidate admission ve staging/production promotion | Workflow `release-candidate` environment adını taşır; canlı protection/reviewer ile staging/production Environment, OIDC, secret ve target gözlemi `unavailable` | Eksik ortam/protection başarı sayılmaz; deployment `not-configured` kalır | Production bypass yalnız expiring, auditli acil durum kaydıyla | Environment adı koruma kanıtı değil / release-candidate, staging ve production protection'ını kur | 2026-08-17 / Yok |
| C12 SLO/alerting | `documented` | Reliability owner / Product owner | Aylık review ve burn alert | [SLO](SLO.md) `planned/unmeasured`; telemetry ve alert route `unavailable` | Missing telemetry `0` değildir; promotion kararında risk olarak kalır | Budget override owner, gerekçe, süre ve incident/decision kaydı ister | Canlı SLI yok / collector, dashboard, alert ve runbook'u prova et | 2026-08-24 / Yok |
| C13 Incident learning | `documented` | Incident commander / Reliability reviewer | SEV ilanı veya tatbikat | [Incident Response](INCIDENT_RESPONSE.md); on-call/paging/tatbikat `unavailable` | Doğrulanmamış action varken learning kaydı kapanmaz | Severity düşürme ve kapatma auditli timeline'a yazılır | Operasyon pratiği yok / non-production tatbikatı yap | 2026-08-24 / Yok |
| C14 ADR governance | `documented` | Architecture owner / Adlandırılmış decider | Kalıcı mimari karar | ADR index/template ve ADR-0001 `Proposed`; insan review `unavailable` | Decider kanıtı olmadan `Accepted` olmaz | Karar değişikliği yeni ADR/supersedes zinciri ister | ADR henüz kabul edilmedi / review'a götür | 2026-08-17 / Yok |
| C15 DORA/flow | `documented` | Engineering owner / Reliability reviewer | Aylık service review | Tanımlar var; deployment/incident event kaynağı `unavailable` | Missing event `0` yazılmaz; kişi sıralaması yasak | Metrik tanımı değişikliği versionlu ve auditli olur | Trend üretilemez / event modeli ve veri kalite kontrolü kur | 2026-08-24 / Yok |

## CI/CD ve PR kalite ilkeleri

- Her gate için owner, trigger, evidence, süre bütçesi, failure policy ve bypass
  yolunu kaydet.
- Gate'i reviewed commit üzerinde çalıştır; stale, malformed, missing veya
  skipped sonucu başarı sayma.
- Hız için güvenli cache ve paralellik kullan; test izolasyonunu veya
  deterministikliği bozma.
- Flaky check'i kusur olarak kaydet. Quarantine, owner ve expiry olmadan
  yapılamaz ve eksilen coverage “passed” diye raporlanamaz.
- Shared branch için bağımsız review, sensitive-path owner, resolved
  conversation ve auditli istisna iste.
- Build'i environment başına tekrarlama; tek immutable digest'i terfi ettir.
- Migration ile application rollout'unu ayrı kararlar olarak izle ve uyumsuz
  adımları serialize et.

Tek feature'ın repo/test teslimi feature-delivery sürecine, belirli release
candidate'ının bütün gate denetimi release-verification sürecine aittir.
[Release Process](RELEASE_PROCESS.md), kalıcı pipeline sözleşmesini açıklar.

## Supply-chain hedef kontrolü

1. Direct/transitive dependency lock'larını ve third-party Actions kimliklerini
   immutable revizyonlara bağla.
2. Source, dependency, container, license ve secret taramalarını en erken anlamlı
   aşamada çalıştır.
3. Candidate için source SHA, image digest, SBOM digest ve provenance/attestation
   bağını koru.
4. Artifact'ı deployment'tan önce verify et; yalnız tag adına güvenme.
5. Kısa ömürlü ve least-privilege deployment identity kullan; ortamları ayır.
6. Kabul edilen risk için severity, compensating control, owner ve expiry yaz.

Remote üçüncü taraf Actions tam commit SHA'sına pinlidir ve
`scripts/workflow_policy_check.py` mutable ref'i; block, quoted veya inline
`pull_request_target` tetikleyicisini; çözülemeyen local action'ı ve recursive
local composite bağımlılığını reddeder. Dependabot config'i repository'nin gerçek lock
yöneticileri olan `uv` ve `bun` ecosystem'lerini kullanır. Buna rağmen ilk
gerçek update PR'ı `uv.lock` ve `bun.lock` değişimini göstermeden otomasyon
`observed` değildir. Dependency Review ve CodeQL dosyaları da ilgili GitHub
özelliklerinin repo için etkin olduğunu veya workflow'un başarıyla koştuğunu tek
başına kanıtlamaz.

## DORA ve flow tanımları

Güncel DORA delivery set'ini service düzeyinde izle. Kaynak:
[DORA software delivery performance metrics](https://dora.dev/guides/dora-metrics/).

| Metrik | DOU-Synapse tanımı | Gerekli event | Başlangıç durumu |
|---|---|---|---|
| Change lead time | Commit'in version control'a girmesinden o değişikliği içeren digest'in production'da başarılı terfisine kadar süre | Commit SHA + başarılı production deployment zamanı | `unavailable`; deployment event'i yok |
| Deployment frequency | Seçilen dönemdeki başarılı production deployment sayısı veya aralığı | Environment + digest + success zamanı | `unavailable`; sıfır olarak yazılmaz |
| Failed deployment recovery time | Müdahale gerektiren başarısız deployment başlangıcından hizmetin doğrulanmış geri dönüşüne kadar süre | Failure, incident/rollback ve recovery zamanları | `unavailable` |
| Change fail rate | Acil rollback, hotfix veya başka doğrudan müdahale isteyen production deployment'ların tüm production deployment'lara oranı | Deployment sonucu + intervention sınıfı | `unavailable` |
| Deployment rework rate | Production incident'i nedeniyle yapılan plansız deployment'ların tüm production deployment'lara oranı | Deployment reason + incident ID | `unavailable` |

Clock ve denominator tanımını ölçümden önce versionla. Başarısız release
candidate build'ini production change failure ile karıştırma. Planned deploy'u
production deployment sayma. Missing event'i `0` olarak doldurma.

Metrikleri kişi sıralaması, performans puanı veya PR sayısı yarışması için
kullanma. Service ve zaman aralığı düzeyindeki trendi SLO bütçesi, CI süresi,
review gecikmesi, flaky-check yükü ve developer experience sinyaliyle birlikte
yorumla.

## İyileştirme döngüsü

1. Scorecard'ı exact SHA ve observation zamanı ile yeniden baseline et.
2. En büyük flow veya reliability darboğazını kanıtla.
3. Tek küçük süreç/kontrol değişikliği ve karşı metriğini seç.
4. Değişikliği versionla; bypass ve expiry'yi görünür tut.
5. Yeterli event biriktikten sonra trendi ve yan etkileri karşılaştır.
6. Kanıt iyileşmiyorsa değişikliği geri al veya yeni hipotez aç.

Kontrol tablosunda owner, evidence, target, next experiment ve unresolved risk
boş bırakılamaz. Dış ayar gerektiren satırlar repository commit'iyle
`configured`, `enforced` veya `observed` yapılamaz.
