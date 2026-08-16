# ADR-NNNN: Karar başlığı

- **Status:** Proposed
- **Date:** YYYY-MM-DD
- **Owners:** Sorumlu rol/kişiler
- **Deciders:** Onay verecek bağımsız rol/kişiler
- **Review by:** YYYY-MM-DD veya olay koşulu
- **Supersedes:** Yok veya ADR-NNNN
- **Superseded by:** Yok veya ADR-NNNN
- **Related:** Spec, PR, incident, SLO ve release linkleri

## Context

Kararı zorunlu kılan mevcut durumu ve kanıtı yaz. Planned, configured, enforced
ve observed uygulama durumlarını ayır; bunları ADR'nin `Status` alanına
yazma. Ölçülmemiş sayı veya production iddiası ekleme.

## Decision drivers

- Güvenlik, gizlilik ve course isolation gereksinimleri
- Operasyonel/reliability gereksinimleri
- Maliyet ve ekip kapasitesi
- Migration, compatibility ve reversal maliyeti
- Doğrulama ve gözlemlenebilirlik gereksinimleri

## Considered options

### Option A

Yaklaşım, fayda, risk ve reversal.

### Option B

Yaklaşım, fayda, risk ve reversal.

## Decision

Seçilen yaklaşımı ve özellikle seçilmeyen davranışı açıkla.

## Consequences

### Positive

- Beklenen fayda ve bunu doğrulayacak evidence.

### Negative and trade-offs

- Kabul edilen bedel, owner ve azaltıcı kontrol.

## Security and privacy

Trust boundary, identity/secret, student data ve retention etkisini yaz.

## Cost and operability

Build/deploy süresi, storage/compute, owner ve runbook etkisini yaz.

## Migration and compatibility

Eski/yeni application-data-artifact uyumluluğunu ve irreversibility'yi yaz.

## Observability and evidence

Kararın çalıştığını hangi event, gate, dashboard, test veya exercise'ın
kanıtlayacağını yaz. Eksik veri için `unavailable` kullan.

## Rollout and reversal

Kademeli uygulama, stop koşulları, geri alma/fix-forward ve doğrulama adımları.

## Validation before acceptance

- [ ] Karar owner ve bağımsız decider tarafından review edildi.
- [ ] Negatif yol kırmızı yanabildi.
- [ ] Migration/reversal güvenli ortamda prova edildi veya açıkça blocked.
- [ ] External configuration repo kanıtından ayrı doğrulandı.
- [ ] Kalan risk ve review tarihi kaydedildi.

## Open questions

- Karar öncesi yanıtlanması gereken soru ve owner.
