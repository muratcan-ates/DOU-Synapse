# Incident response ve öğrenme

Bu belge production, staging ve ciddi AI kalite olaylarında ortak müdahale ve
öğrenme sözleşmesidir. Öncelik kullanıcıyı ve veriyi korumak, sonra hizmeti
güvenli biçimde geri getirmek, en son nedeni ve kalıcı kontrolü kanıtlamaktır.

> **Durum:** Süreç `documented` durumundadır. Production on-call rotası, paging,
> alert delivery, status page ve incident tatbikatı bu dokümantasyon turunda
> yapılandırılmamış veya gözlenmemiştir. Bir template'in varlığı hazır müdahale
> ekibi kanıtı değildir.

## Olay açma ölçütü

Aşağıdakilerden biri varsa incident kaydı aç:

- course isolation, auth, privacy, secret veya kişisel veri ihlali;
- kaynaksız akademik cevap, yanlış citation gösterimi veya exam guardrail bypass;
- kabul edilmiş sınav cevabının kaybı, duplicate yazımı veya yanlış attempt'e
  bağlanması;
- service outage, sürekli 5xx, stuck ingestion veya güvenli fallback'in tükenmesi;
- production deployment'ın rollback/hotfix gibi acil müdahale istemesi;
- SLO hızlı burn ya da gözlem kaybı nedeniyle güvenilir durum kararı verilememesi;
- etkisiz kalmış bir security, release veya AI gate'inin sonradan fark edilmesi.

Near miss kullanıcı etkisi üretmese de aynı kayıt biçimiyle öğrenme adayıdır.

## Severity

| Seviye | Ölçüt | İlk odak |
|---|---|---|
| `SEV-1` | Dersler arası veri açığı, aktif sınav bütünlüğü kaybı, onaylanmış veri kaybı, sızmış production secret veya geniş kritik kesinti | Etkiyi kes, erişimi daralt, güvenli modu/rollback'i değerlendir, security/privacy owner'ı çağır |
| `SEV-2` | Kritik yolculuğun büyük bölümünde kesinti, gerçek-provider/fallback zincirinin güvenli sonuç verememesi, hızla tükenen error budget | Rollout'u durdur, bilinen iyi digest/flag durumuna dön, kapsamı ölç |
| `SEV-3` | Sınırlı kullanıcı/kurs etkisi, workaround bulunan degradation, gecikmiş ingestion veya tek provider sorunu | Etkiyi sınırla, owner ata, planlı düzeltme ve gözlem yap |
| `SEV-4` | Kullanıcı etkisiz near miss, noisy alert, prosedür/kanıt boşluğu | Öğrenme kaydı ve kontrollü backlog |

Belirsizse daha yüksek severity ile başla; kanıt geldikçe incident commander
değişikliği zaman damgasıyla kaydeder.

## Roller

| Rol | Sorumluluk |
|---|---|
| Incident Commander | Severity, öncelik, rol ataması ve karar kaydı; aynı anda teknik ayrıntıyı çözmeye çalışmaz |
| Operations Lead | Containment, rollback/fix-forward, smoke ve telemetry doğrulaması |
| Scribe | Zaman çizelgesi, kanıt linkleri, hipotez ve kararları gerçek zamanlı kaydeder |
| Communications Owner | Etkilenen paydaşlara doğrulanmış kapsam ve sonraki güncelleme zamanını iletir |
| Domain Owner | Course/exam/pedagoji etkisini ve güvenli fallback'i değerlendirir |
| Security/Privacy Owner | Yetki, veri, secret, bildirim ve evidence-retention kararlarını verir |

Bir kişi birden fazla rol alabilir; Incident Commander ve Communications Owner
yine de açıkça adlandırılır. Kişi adı repo template'inde zorunlu değildir, gerçek
incident kaydında zorunludur.

## Müdahale akışı

### 1. Declare ve kapsamı dondur

- Incident ID, başlangıç zamanı, ilk belirti, environment ve reporter kaydet.
- Etkilenen service, course/role/mode, candidate SHA, artifact digest, AI change
  ID ve son başarılı deployment'ı bağla.
- Varsayımı gerçek gibi yazma; `confirmed`, `suspected`, `unknown` etiketlerini
  kullan.

### 2. Contain

- Yeni rollout ve promotion'ı durdur.
- Uygunsa AI feature flag/kill switch'i kapat veya bilinen iyi digest'e dön.
- Citation, RLS, auth, scope ya da exam korumasını gevşeterek hizmeti geri
  getirme. Güvenli cevap üretilemiyorsa fail closed kal.
- Secret şüphesinde erişimi sınırla ve rotasyon kararını security owner'a ver.
- Delili koru fakat student content, JWT veya secret'ı incident belgesine kopyalama.

### 3. Diagnose

- Zaman korelasyonunu deployment, config, provider, migration, traffic ve alert
  event'leriyle kur.
- Tetikleyici olayı, katkıda bulunan koşulları ve kontrol boşluğunu ayır.
- Aynı davranışı staging veya güvenli fixture'da yeniden üret; production'da
  yıkıcı deney yapma.
- Missing telemetry'yi “olay yok” diye yorumlama.

### 4. Recover

- [Release Process](RELEASE_PROCESS.md) içindeki aynı-digest rollback veya
  fix-forward kararını uygula.
- Migration uyumluluğu bilinmiyorsa eski uygulama digest'ine dönme; önce
  preflight yap.
- AI rollback'te prompt/model/index/tool ve evaluator uyumluluğunu birlikte
  kontrol et.
- Readiness tek başına yeterli değildir; etkilenen kullanıcı yolculuğu için
  non-destructive smoke ve privacy-safe telemetry doğrula.

### 5. Communicate

- Yalnız doğrulanmış impact, alınan önlem ve bir sonraki update zamanını paylaş.
- Kök neden kesin değilse açıkça söyle.
- Production, kullanıcı sayısı, veri kaybı veya recovery süresi hakkında
  ölçülmemiş sayı üretme.
- External bildirim gereksinimini security/privacy owner kararı olmadan kapatma.

### 6. Learn ve verify

- Blameless timeline ve contributing conditions yaz.
- “Daha dikkatli ol” yerine kırmızı yanabilen veya gözlenebilir corrective action
  üret.
- Owner, due date, doğrulama komutu/koşusu ve beklenen kırmızı/yeşil davranışı
  ekle.
- Action'ı yalnız kod merge olduğu için kapatma; preventive/detection davranışı
  gösteren evidence bağla.

## Incident kayıt şablonu

```markdown
# INC-<YYYYMMDD>-<slug>

- Status: declared | contained | monitoring | resolved | learning-open | closed
- Severity:
- Environment:
- Incident Commander:
- Operations Lead:
- Communications Owner:
- Domain/Security/Privacy owners:
- Started at:
- Detected at:
- Contained at:
- Service restored at:
- Closed at:
- Related candidate SHA/digest:
- Related AI change ID / ADR / SLO:

## Impact

- Confirmed:
- Suspected:
- Unknown:
- Privacy/data classification:

## Timeline

| Time (UTC) | Observation or decision | Evidence | Owner |
|---|---|---|---|

## Containment and recovery

- Action:
- Why:
- Result:
- Post-action smoke/telemetry:

## Contributing conditions

- Trigger:
- Conditions:
- Control that should have prevented/detected it:
- Why that control did not:

## Corrective actions

| Action | Type | Owner | Due | Verification evidence | Status |
|---|---|---|---|---|---|

## Communication record

| Time (UTC) | Audience | Confirmed message | Owner |
|---|---|---|---|
```

Action durumu `open -> implemented -> verified -> closed` sırasını izler.
Incident hizmet geri geldiğinde `resolved` olabilir; corrective action'lar
kanıtlanmadan `closed` olamaz.

## Kapanış kapısı

Şunların tümü olmadan incident'i kapatma:

- etki ve zaman çizelgesi ölçülmüş/etiketlenmiş;
- recovery exact digest/config/flag ile doğrulanmış;
- kullanıcı yolculuğu smoke'u ve ilgili SLO/AI sinyali görülmüş;
- veri veya privacy kararının owner'ı belli;
- corrective action'ların her biri owner, due date ve verification taşıyor;
- runbook, gate, SLO veya ADR değişikliği gereken yerde bağlanmış;
- unresolved risk ve tekrar gözden geçirme tarihi yazılmış.

[SLO](SLO.md) budget etkisini, [AI SDLC](AI_SDLC.md) AI artefaktı ve canary
kararını, [Engineering Excellence](ENGINEERING_EXCELLENCE.md) kalıcı control
state değişikliğini tutar.
