# ADR-0001: Build once, promote by digest

- **Status:** Proposed
- **Date:** 2026-08-11
- **Owners:** Release engineering owner
- **Deciders:** Engineering lead ve operasyon/deployment owner
- **Review by:** Candidate workflow ve protected staging ortamı doğrulandığında
- **Supersedes:** Yok
- **Superseded by:** Yok
- **Related:** [Feature spec](../../specs/004-ai-sdlc-excellence/spec.md), [Release Process](../engineering/RELEASE_PROCESS.md), [Engineering Excellence](../engineering/ENGINEERING_EXCELLENCE.md)

## Context

Başlangıç SHA'sı `2c178861` üzerindeki `.github/workflows/ci.yml`, API container
image'ını build eder ve ağsız embedding davranışını sınar; image'ı push etmez.
Bu feature branch working tree'si release-candidate workflow'u ile yalnız
current `origin/main` HEAD'e eşit event-bound `v*` push SHA kabulü, exact
checkout, trusted workflow/job kimliği, fail-closed pagination/duplicate kapısı,
tek quarantine GHCR publish, yayımlanan exact digest üzerinde ağsız
embedding/bake-report/RSS doğrulaması, admitted artifact ve verifiable
SBOM/provenance/attestation referanslarıyla candidate-evidence schema validation
tanımlar. Manual, ref-selected veya historical-main release yolu yoktur.
Workflow run'ı, staging/production promotion, protected Environment veya çalışan
CD yolu henüz gözlenmemiştir.

Environment başına yeniden build edilen image'lar aynı source SHA'dan gelse bile
dependency çözümü, base image veya builder farkı yüzünden byte/digest düzeyinde
aynı olmayabilir. Staging'de sınanan şey ile production'da çalışan şeyin aynı
olduğunu source SHA tek başına kanıtlamaz.

Bu ADR mevcut deployment veya registry varlığını iddia etmez. Kararın durumu,
repo workflow'u ve dış protected environment gözlenene kadar `Proposed` kalır.

## Decision drivers

- Staging kanıtını production artifact'ına doğrudan bağlamak
- Source SHA, image digest, SBOM ve build provenance lineage'ını korumak
- Environment secret'larını build aşamasından ayırmak
- Hızlı ve tanımlı application rollback sağlamak
- Rebuild ve mutable-tag drift'ini önlemek
- Eksik credentials/environment durumunu başarısız veya `not configured` olarak
  görünür tutmak

## Considered options

### Option A - Her environment için yeniden build

Basittir ve environment-specific değerleri image'a gömmeyi kolaylaştırır. Buna
karşılık staging'de doğrulanan digest production'da çalışmaz; supply-chain ve
rollback lineage'ı zayıflar. Reddedildi.

### Option B - Tek build, mutable tag ile promotion

Build tekrarını kaldırır fakat `latest` veya version tag'i başka digest'e
taşınabilir. Deployment kaydında gerçekten hangi bytes'ın çalıştığı belirsiz
kalır. Tek başına yeterli olmadığı için reddedildi.

### Option C - Tek build, immutable digest ile promotion

Reviewed SHA'dan bir candidate üret, registry digest'ini evidence bundle'a yaz,
staging ve production job'larına yalnız bu digest'i input ver. Seçilen yaklaşım
budur.

## Decision

DOU-Synapse release pipeline'ı bir source SHA için container candidate'ı bir kez
build edecektir. Candidate registry'ye immutable digest ile publish edilecek;
staging ve production aynı digest'i yeniden build etmeden terfi ettirecektir.

Source admission yalnız `v*` tag `push` event'inin tam 40 karakterli SHA'sıyla
yapılacaktır. Manual/ref-selected/historical-main yol bulunmayacak; candidate'ın
başlarken current `origin/main` HEAD'e eşit olması zorunlu olacaktır.
Required gate, beklenen core/AI/security sonuçlarını display name ile değil exact
trusted workflow path/identity, push event, head SHA, run/job kimliği ve
completed/success sonucuyla bağlayacaktır. Pagination, foreign/manual run,
duplicate/newer spoof veya missing/skipped/stale/failure fail closed olur.

Image bir kez build edilip quarantine kimliğiyle publish edilecek; registry'nin
döndürdüğü exact `name@sha256:digest` hemen pull edilip ağsız embedding, bake
report ve `<4 GiB` RSS assert'inden geçirilecektir. Digest ancak bundan sonra
yalnız immutable evidence artifact'ıyla admitted olarak kaydedilebilir; mutable
admitted tag üretilmez. Candidate evidence verifiable
SBOM, provenance ve attestation reference+digest'lerini taşır.

Candidate evidence bundle en az şunları bağlayacaktır:

- repository ve exact source SHA;
- quarantine reference ve admitted immutable `sha256` digest;
- image digest'ine bağlı verifiable SBOM identity/reference+digest;
- verifiable provenance/attestation reference+digest;
- exact candidate üzerinde trusted workflow/run/job core, AI ve security gate sonuçları;
- exact published digest'i sınayan workflow run'ı;
- candidate admission state'i; staging/production yalnız `not-configured`
  olabilir ve candidate kaydı promotion nesnesi taşıyamaz.

Migration compatibility/backup, environment approval/deployment/smoke ve
previous-digest rollback kanıtları candidate bundle'a uydurulmayacaktır. Bu
kayıtlar ilgili aşama gerçekten çalıştığında aynı admitted digest'e bağlı yeni,
append-only promotion kayıtlarıdır. Named approver, immutable actor/ref/time ve
approved SHA olmadan approval geçerli değildir.

Runtime configuration image'a gömülmeyecektir. Environment-specific secret ve
target ayarları protected environment tarafından deployment anında sağlanacaktır.
Bir ortamın eksik olması diğerini “deployed” göstermez.

## Consequences

### Positive

- Staging ve production aynı çalıştırılabilir bytes'a bağlanır.
- Rollback hedefi tag yerine bilinen immutable digest olur.
- SBOM, provenance ve test evidence tek candidate etrafında birleşir.
- Environment'ta rebuild kaynaklı drift ortadan kalkar.

### Negative and trade-offs

- Registry, artifact retention ve least-privilege publish yetkisi gerekir.
- Büyük embedding-model image'ları storage ve transfer maliyeti üretir.
- Runtime config ile build-time config'in ayrımı disiplin ister.
- Schema backward-compatible değilse application digest rollback'i mümkün
  olmayabilir; fix-forward gerekir.
- Digest'in kendisi güven oluşturmaz; builder/provenance ve deployment verify
  kontrolleri de gerekir.

## Security and privacy

- Build job production secret'ı almaz.
- Publish ve attestation job'ları yalnız gereken `packages`/identity yetkisini
  alır; repository-wide write yetkisi verilmez.
- Third-party Actions immutable revision'a taşınır veya expiring exception ile
  görünür tutulur.
- SBOM/evidence bundle secret, JWT, student content veya raw prompt/answer içermez.
- Deployment digest'i target'ta verify edilmeden traffic açılmaz.

## Cost and operability

Tek build CI süresini ve farklı ortam rebuild maliyetini azaltır; registry
storage ve retention gerektirir. Release owner candidate retention süresini,
son bilinen iyi digest sayısını ve silme politikasını dış registry
yapılandırmasıyla birlikte belirlemelidir. Bu değerler henüz yapılandırılmış
değildir.

## Migration and compatibility

Migration'lar image'dan ayrı, serialize edilmiş bir adım olarak yürütülür.
Evidence bundle `none`, `expand`, `contract` veya `blocked` kararı taşır. Önceki
application digest'in yeni schema ile uyumluluğu staging'de kanıtlanmadan
rollback-ready denmez.

Destructive migration için restore ya da güvenli fix-forward kanıtı yoksa
production promotion bloklanır. Application rollback uygulanmış migration'ı
geri sarmaz.

## Observability and evidence

ADR yalnız adlandırılmış decider review'u ile `Accepted` olabilir. Aşağıdaki
gözlemler ise ADR durumunu değil, scorecard'daki uygulama kaydını `observed`
yapabilir:

- invalid/mismatched SHA, moved `origin/main` HEAD ve historical-main commit
  source gate'inde kırmızı yanar;
- foreign/manual workflow, wrong event/head SHA, duplicate/newer spoof ve
  missing/skipped/stale/failure candidate'ı bloklar;
- kesik workflow/job pagination ve schema-invalid evidence candidate'ı bloklar;
- workflow tek quarantine digest üretir; yayımlanan exact digest registry'den
  pull/test edilmeden admitted olmaz;
- aynı digest staging deployment record'unda görünür;
- production job yeniden build girişimine izin vermez;
- SBOM, provenance ve attestation verifiable ref/digest ile exact admitted
  digest'e bağlanır;
- yanlış/stale digest ve eksik environment negatif testleri kırmızı yanar;
- rollback tatbikatı önceki digest'i deploy eder ve journey smoke'u geçer.

Bu repository-configured slice'ın local policy/validator testleri yeşildir;
workflow, registry publish ve dış environment gözlemleri henüz yapılmamıştır.

## Rollout and reversal

1. Tag push event SHA equality ve current `origin/main` HEAD gate'lerini negatif
   yollarla doğrula; manual/ref-selected/historical-main release yolu açma.
2. Trusted workflow/job identity gate'ini ekle; foreign/manual/duplicate,
   pagination ve missing/skipped/stale/failure durumlarını kırmızı çalıştır.
3. Quarantine GHCR publish sonrası exact digest pull/embedding/bake/RSS,
   admission, verifiable SBOM/provenance/attestation ve schema-valid candidate
   evidence'ı test et; deployment job'u açma.
4. Protected staging Environment kur ve aynı digest promotion'ı gözle.
5. Migration ve previous-digest rollback'i non-production target'ta prova et.
6. Bağımsız review sonrası ADR'yi `Accepted` yap.
7. Production Environment'ı ancak staging/SLO/incident kontrolleri hazırsa aç.

Karar geri alınırsa candidate workflow publication'ı durdurulur; mevcut digest
ve evidence kayıtları audit için korunur. Rebuild-per-environment yaklaşımına
dönüş yeni ADR gerektirir.

## Validation before acceptance

- [ ] Tag push SHA ve current `origin/main` HEAD negatif/pozitif yolları
      gözlendi; manual/ref-selected/historical-main admission bulunmadı.
- [ ] Trusted workflow/job gate foreign/manual/duplicate, wrong event/head SHA,
      missing/skipped/stale/failure ve kesik pagination durumlarını blokladı.
- [ ] Registry'den pull edilen exact digest ağsız embedding/bake/RSS kapılarını
      geçti; quarantine digest yalnız bundan sonra admitted oldu ve verifiable
      SBOM/provenance/attestation schema-valid evidence'a bağlandı.
- [ ] Staging exact digest'i rebuild etmeden kullandı.
- [ ] Missing credential/environment `not configured` veya fail olarak göründü.
- [ ] Wrong/stale digest promotion'ı kırmızı yandı.
- [ ] Migration compatibility ve previous-digest rollback prova edildi.
- [ ] Branch ruleset ve protected Environment canlı olarak doğrulandı.
- [ ] Engineering lead ve deployment owner bağımsız review verdi.

## Open questions

- GHCR retention ve son bilinen iyi digest saklama süresi nedir?
- Container signing/verification için hangi GitHub-native veya harici mekanizma
  seçilecektir?
- API ve worker aynı image digest'ini farklı command ile çalıştırırken deployment
  order ve rollback atomikliği nasıl sağlanacaktır?
- Web artifact'ı aynı build-once sözleşmesine hangi packaging modeliyle dahil
  edilecektir?
