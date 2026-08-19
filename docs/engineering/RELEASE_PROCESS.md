# Release süreci: build once, digest ile terfi

Bu runbook, exact source SHA'dan tek immutable candidate üretmeyi,
kanıt paketini saklamayı ve aynı digest'i ortamlar arasında terfi ettirmeyi
tanımlar. Environment başına yeniden build etmek yasaktır.

> **Mevcut sınır (2026-08-20):** `origin/main` SHA'sı `2f40ac19` üzerindeki core CI
> API image'ını build/test eder fakat push/deploy etmez. Bu feature branch
> working tree'sindeki release-candidate workflow'u yalnız current
> `origin/main` HEAD'e eşit `v*` push event SHA'sını kabul eder; exact checkout,
> trusted workflow/job kimliği, quarantine publication, yayımlanan exact digest
> üzerinde ağsız embedding/bake-report/RSS kapıları, admitted artifact,
> verifiable SBOM/provenance/attestation referansları ve candidate-evidence schema
> doğrulamasını repo-configured hale getirir. Workflow
> henüz koşmadı;
> staging/production promotion job'ları, protected GitHub
> Environments ve deployment OIDC/credentials ise dışarıda ve unconfigured'dır.
> Aşağıdaki süreç “deployed” ya da “production verified” iddiası değildir.

Source admission mutable veya operatörce seçilen ref'e açık değildir. Tek yol,
`v*` push event'inin 40 karakterli SHA'sını checkout etmek ve bunun candidate
başlarken current `origin/main` HEAD'e eşit olduğunu doğrulamaktır. Required
gate'ler display name ile değil exact trusted workflow path/identity, `push`
event'i, exact head SHA, immutable run/job kimliği ve `completed/success`
birlikteliğiyle doğrulanır. Workflow-run ve job API'larının bütün sayfaları
toplanır; eksik sayfa, foreign/manual run, duplicate/newer spoof, missing,
skipped, stale veya başarısız sonuç fail closed olur.

Kararın gerekçesi [ADR-0001](../adr/0001-build-once-promote-by-digest.md)
belgesindedir. ADR `Accepted` olmadan ve workflow kırmızı/yeşil yollarıyla
gözlenmeden release süreci `enforced` veya `observed` sayılamaz.

## Durum dili

| Durum | Söylenebilmesi için gereken kanıt |
|---|---|
| `source-frozen` | Exact SHA, branch/upstream, clean/dirty state ve reviewed diff |
| `quarantined` | Current-main source SHA'dan tek registry digest'i üretildi; henüz candidate olarak kabul edilmedi |
| `candidate-evidenced` | Quarantine'dan çekilen exact digest ağsız embedding, bake report ve `<4 GiB` RSS kapılarını geçti; admitted digest, trusted workflow/job kimlikleri, verifiable SBOM/provenance/attestation ve schema-valid kayıt bağlı |
| `staging-deployed` | Aynı digest'in staging target'a uygulanma kaydı; skipped job yeterli değil |
| `staging-verified` | Auth/storage/database/real-provider ve kritik journey smoke kanıtı |
| `production-deployed` | Staging'de doğrulanan aynı digest, bağımsız environment approval ve deployment kaydı |
| `production-verified` | Post-deploy smoke, SLO telemetry, alert ve rollback readiness aynı digest'i gösteriyor |
| `rolled-back` | Önceki digest/config geri geldi ve etkilenen journey yeniden doğrulandı |

Bir durum sonraki durumu ima etmez. `quarantined`, registry'ye push edilmiş
olabilir fakat admitted candidate, staging veya production deployment değildir.
Repository-green, production-green değildir.

## 1. Candidate'ı dondur

Release owner şu bilgileri tek kayda yazar:

- repository, branch, exact candidate SHA ve upstream SHA;
- working-tree durumu ve candidate'a girmeyen worktree/commit'ler;
- PR ve bağımsız review;
- candidate SHA üzerinde koşmuş required checks;
- migration listesi ve application/schema compatibility kararı;
- AI-sensitive değişiklik varsa dossier ID ve promotion durumu.

Stale branch, başka SHA'daki CI, skipped gate veya yalnız commit mesajındaki test
iddiası candidate kanıtı değildir. Release doğrulamasını exact candidate üzerinde
ayrıca yürüt.

## 2. Tek candidate üret

Candidate workflow'u aşağıdaki sözleşmeyi uygulamalıdır:

1. Yalnız `v*` tag `push` event'inde çalış; checkout sonucunu event'in tam 40
   karakterli SHA'sına bağla. Manual/ref-selected release yolu sağlama.
2. Event SHA'nın candidate başlarken current `origin/main` HEAD'e tam eşit
   olduğunu doğrula; tarihsel main atasını, dal ucunu veya mutable adı release
   kimliği olarak kabul etme.
3. Required gate'leri exact trusted workflow path/identity, beklenen job adı,
   `push` event'i ve aynı head SHA ile eşle. Workflow-run ve job sayfalarını
   eksiksiz topla. Foreign/manual/duplicate/newer spoof, kesik pagination,
   missing/skipped/stale/failed sonuçta fail closed yap; immutable run/job
   URL ve kimliklerini evidence'a bağla.
4. API/worker'ın kullandığı tek container image'ı bir kez build edip quarantine
   namespace/tag ile registry'ye publish et; build adımını tekrarlama.
5. Quarantine `image.name@image.digest` referansını registry'den hemen pull et.
   Ağsız embedding, bake report ve `< 4 GiB` RSS assert'ini bu exact digest
   üzerinde çalıştır. Herhangi biri başarısızsa digest quarantined kalır;
   admitted candidate/evidence üretme.
6. Kapıları geçen exact digest'i yalnız immutable evidence artifact'ıyla
   admitted olarak kaydet; mutable admitted tag yaratma. Source SHA, builder ve
   inputs bağını verifiable provenance/attestation reference ve
   digest'iyle kur; aynı digest için verifiable SBOM reference/digest'i üret.
7. Admission ve supply-chain kimlikleri bittikten sonra candidate JSON'unu üret.
8. JSON'u dependency-free `.release/validate_evidence.py` ile
   `.release/evidence.schema.json` sözleşmesine göre fail closed doğrula.
9. Schema-valid evidence artifact'ını sakla; build, pull, test, attestation,
   schema validation veya artifact upload başarısızsa candidate kabul etme.
10. Candidate kaydında staging ve production değerlerini yalnız
    `not-configured` tut; promotion nesnesi veya deployment başarısı yazma.

Build adımı production secret'ı almamalıdır. Workflow permissions least
privilege olmalı; package ve identity yetkileri yalnız ihtiyacı olan job'a
verilmelidir. Remote third-party Action kimlikleri tam commit SHA'sına pinlidir;
repository policy mutable ref'i geri getiren değişikliği kırmızıya çevirir.

## 3. Candidate ve promotion evidence

[Release-candidate workflow](../../.github/workflows/release-candidate.yml) ve
[release evidence schema](../../.release/evidence.schema.json) v2,
`record_type: candidate` ile `record_type: promotion` kayıtlarını ayırır.
Candidate kaydı current-main source SHA'yı, exact trusted
workflow/run/job kimliklerini, quarantine ve admitted immutable referansları,
exact-digest product gate'lerini ve verifiable SBOM/provenance/attestation
reference+digest'lerini aynı candidate'a bağlar.

Candidate evidence staging ve production için yalnız `not-configured` taşır ve
promotion nesnesini yasaklar. Environment approval, migration, backup, smoke,
rollback, SLO veya real-provider başarısı içermez. Candidate schema'nın geçmesi
bunlardan hiçbirini ima etmez.

Staging veya production ilerlediğinde candidate kaydını değiştirme. Aynı admitted
digest'e bağlı ayrı, append-only immutable promotion kaydı üret. Her kayıt en az
şunları taşır:

- hedef ortam, candidate SHA ve admitted digest;
- adlandırılmış approver, immutable actor identity/reference, approval zamanı
  ve onaylanan SHA;
- migration kararı, compatibility ve preflight evidence'ı;
- backup/restore sonucu ve immutable kanıt referansı;
- hedefe özgü smoke sonucu ve run kimliği;
- previous digest, rollback readiness/exercise ve doğrulama kanıtı;
- production için aynı digest'e ait başarılı staging promotion kaydı.

`skipped`, `missing`, `not-run`, `not-configured`, rejected, failed veya stale
değerleri yeşil sonuca dönüşmez. Secret, JWT, student content, prompt/answer
body veya raw database dump'ı hiçbir evidence paketine koyma. Ayrıntılı
makine sözleşmesi [release evidence contract](../../specs/004-ai-sdlc-excellence/contracts/release-evidence.md)
belgesindedir.

## 4. Migration preflight

Staging veya production promotion öncesinde:

1. Migration'ları source-controlled alfabetik sırada listele; dashboard'da elle
   schema değiştirme.
2. Kararı `none`, `expand`, `contract` veya `blocked` olarak kaydet.
3. Önceki ve yeni application digest'lerinin mevcut/sonraki schema ile
   uyumluluğunu matriste göster.
4. Destructive veya geri çevrilemez adımı production'dan ayır; backup ve
   doğrulanmış restore ya da açık fix-forward kararı olmadan ilerletme.
5. Aynı environment'ta migration koşularını serialize et.
6. Staging kopyasında migration, application smoke ve rollback/fix-forward
   provası yap.

Mevcut [deployment belgesindeki](../deployment.md) backup/restore komutları bir
başlangıçtır; gerçek target, policy ve storage geri yüklemesiyle yapılan prova
olmadan production recovery kanıtı değildir.

Application rollback bir migration'ı geri almaz. Önceki digest yeni schema ile
uyumsuzsa eski digest'e dönme; güvenli fix-forward uygula.

### 4.1. Fail-closed staging preflight

Deploy kaydı üretildikten sonra, ancak `staging-verified` kararı verilmeden önce
`.release/staging_preflight.py` çalıştırılır. Gerekli secret'lar komut satırı
argümanı değil environment değişkenidir; tam örnek
[`specs/006-release-readiness/quickstart.md`](../../specs/006-release-readiness/quickstart.md)
belgesindedir.

Araç candidate SHA/digest'ini checkout ve current `origin/main` ile; web,
live/readiness, gerçek auth, private storage, remote migration ledger,
availability ve cache-free cited real-provider smoke'unu canlı hedefle; backup,
previous digest ve rollback referanslarını dış kanıtlarla karşılaştırır. JSON ve
Markdown çıktıları secret redaction uygular.

Çıkış `0` bütün preflight kontrollerinin geçtiğini, `1` canlı bir kontrolün
başarısız olduğunu, `2` ise prerequisites/evidence eksikliği nedeniyle kararın
blocked kaldığını belirtir. Başarılı sonuç bile protected environment approval,
deployment record ve gözlem kanıtı olmadan promotion veya `staging-verified`
değildir.

## 5. Staging promotion

Staging ancak aşağıdakiler varsa açılır:

- protected staging Environment gerçekten yapılandırılmış;
- registry artifact digest ile çekilebiliyor ve kimliği verify edilmiş;
- gerekli OIDC/least-privilege credentials mevcut;
- migration preflight ve backup/restore kararı bağlı;
- candidate checks aynı digest ve source SHA'yı gösteriyor.

Staging job image'ı yeniden build edemez. Candidate digest'i input alır ve
deployment record'a yazar.

Staging smoke en az şunları kapsar:

- `/health/live` ve `/health/ready`;
- gerçek auth, course-scoped erişim ve negatif izolasyon;
- upload -> ingestion -> searchable source yolculuğu;
- gerçek-provider gerektiren değişiklikte sabit acceptance örneği;
- chat citation/scope ve sınav lock/submit akışı;
- structured telemetry'de source SHA, digest ve AI change ID;
- alert route'un test sinyali.

Fake-provider smoke mekanik yolu doğrular; production-grade AI kanıtı değildir.
Skipped veya credentials eksik job staging başarısı değildir.

## 6. Production promotion

Production promotion için:

1. Staging'de doğrulanmış exact digest'i seç.
2. Staging evidence, migration kararı, açık incident/SLO riski ve rollback
   compatibility'sini review et.
3. Protected production Environment'ta bağımsız insan approval iste; named
   actor identity, immutable approval reference, zaman damgası ve onaylanan
   candidate SHA'yı promotion kaydına bağla.
4. Aynı digest'i deploy et; tag'i yeniden build veya resolve etme.
5. Deployment record'a source SHA, digest, approval ve zaman damgası yaz.
6. Non-destructive post-deploy smoke ve SLO telemetry'yi gözle.
7. Observation tamamlanana kadar `production-verified` kullanma.

Bu repository-configured slice hiçbir production adımı çalıştırmaz ve dış
approval'ın varlığını doğrulamaz.

## 7. Rollback ve fix-forward

Rollback tetiklerini release'ten önce tanımla:

- readiness veya kritik journey smoke başarısız;
- SLO hızlı burn;
- course isolation/privacy/security hard stop;
- kaynaksız AI cevabı, exam integrity veya R3 canary stop;
- migration/application incompatibility;
- yanlış digest veya doğrulanamayan provenance.

Karar sırası:

1. Promotion ve yeni traffic genişlemesini durdur.
2. Incident ID aç ve candidate/digest/AI change ID'yi bağla.
3. Önceki digest'in mevcut schema/config/index ile uyumluluğunu kontrol et.
4. Uyumluysa aynı deployment mekanizmasıyla önceki immutable digest'i terfi et.
5. Uyumlu değilse güvenli fix-forward uygula; schema'yı doğaçlama geri sarma.
6. Readiness, etkilenen journey, isolation ve telemetry'yi tekrar doğrula.
7. `rolled-back` durumunu yalnız bu kanıtlar bağlandıktan sonra yaz.

AI değişikliğinde application digest dışında prompt, provider routing, feature
flag ve embedding index'i de geri alınmalıdır. Güvenli eski index korunmamışsa
code rollback tek başına yeterli değildir.

Incident akışı [Incident Response](INCIDENT_RESPONSE.md), budget kararı
[SLO](SLO.md), AI artefaktı [AI SDLC](AI_SDLC.md) belgesinde tutulur.

## 8. Dış enablement kontrolü

Aşağıdakiler repo dosyasıyla tamamlanmış sayılamaz:

- `main`/release-tag ruleset'i ve gerçekten required check listesi;
- protected release-candidate, staging ve production GitHub Environments;
- bağımsız production approval ve auditli bypass;
- GHCR/package permissions, quarantine/artifact retention ve cleanup;
- cloud target, OIDC federation, secrets, domain ve network policy;
- production monitor, alert delivery, backup/restore ve rollback tatbikatı;
- canlı negative/positive candidate run'ı ve immutable approval kaydı.

Her satır live sistemde okunmalı veya güvenli non-production deneyiyle
gözlenmelidir. “Planlandı”, “workflow yazıldı” ve “deployed” farklı durumlardır.
