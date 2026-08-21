# Uygulama Planı: 010 API Observability

**Branch**: `010-api-observability` | **Base**: `db2f42a9ef7e75423c54db45fecedd1436ffa91b`

## Teknik yön

- Migration: `0017_api_observability.sql`
- Runtime: bounded process queue + ayrı tek bağlantılı SQLAlchemy pool
- API: mevcut FastAPI middleware/admin sınırı; yeni framework yok
- UI: mevcut `/admin`, `AdminGate`, `useResource`, token ve tablo desenleri
- Contract: generated OpenAPI 3.1 + HTTP Bearer + tek `ErrorEnvelope`
- Governance: `010-api-observability-r1`, R3; flag/kill switch varsayılan kapalı

`0017` ve `specs/010-*` numaraları bütün yerel worktree/ref'lerde taranmış ve boş
bulunmuştur. `feature/role-admin-panels` bu base'in atasıdır; incoming değişiklik
değildir ve cherry-pick edilmeyecektir.

## Dikey dilimler

1. **Sözleşme**: Speckit, privacy/threat boundary, R3 dossier root.
2. **Depolama**: içeriksiz event tablosu, exact-runtime recorder, admin projection,
   retention ve bağımsız RLS/mutasyon kanıtı.
3. **Runtime**: request ID, route-template, bounded queue, ayrı pool, bounded shutdown,
   fail-open telemetry / fail-closed privacy.
4. **Hata + OpenAPI**: 404/405/422/500 zarfı, Bearer scheme, local docs CSP,
   production docs kapısı ve generated contract.
5. **UI**: mevcut admin shell içinde API akışı workbench'i, filtreler, manual/live
   refresh, mobil labelled rows ve ham kimlik temizliği.
6. **Kanıt**: targeted/full backend, RLS/mutations, web unit/type/build, real API
   browser, OpenAPI drift, docs/dossier ve kalıntı temizliği.

## Anayasa kontrolü

- Telemetri gözlemdir; kullanıcı yanıtını veya kararını değiştiremez.
- Privacy veri modelinde yapısaldır: hassas alanlar yalnız redakte edilmez, tabloda yoktur.
- Yetki API bağımlılığı + SECURITY DEFINER iç kontrol + tablo ACL/RLS olarak üç katlıdır.
- Sağlık ve admin çağrılarının dışlanması ölçümü kendi kendine referanslı yapmaz.
- “İstek yok” ölçümü “sağlıklı” veya “SLO başarılı” diye yeniden adlandırılmaz.
- Bearer ve ErrorEnvelope tek üretim kaynağından OpenAPI'ye geçer; JSON elle yamalanmaz.
- Kill switch yeni kayıt üretimini durdurur; ana API ve tarihsel sorgu kullanılabilir kalır.

İstisna yoktur.

## Sahiplik ve entegrasyon sırası

```text
specs/010-api-observability/**                       root
supabase/migrations/0017_api_observability.sql      backend/RLS lane
supabase/tests/rls_api_observability*               backend/RLS lane
apps/api/app/core/request_observability.py          backend/RLS lane
apps/api/app/core/db.py, core/config.py              backend/RLS lane
apps/api/app/api/admin.py, schemas/admin.py          backend/RLS lane
apps/api/app/api/deps.py, core/errors.py             OpenAPI lane
apps/api/app/core/openapi.py                         OpenAPI lane
apps/api/app/main.py                                 root integration
apps/web/app/admin/page.tsx                          frontend lane
apps/web/components/portal/admin-*                  frontend lane
apps/web/lib/admin.ts, lib/admin.test.ts             frontend lane
apps/web/e2e/portal.spec.ts, DESIGN.md               frontend lane
```

Entegrasyon sırası: migration/API → runtime main bağlantısı → OpenAPI → UI →
generated contract → kanıt/dossier. Şeritler birbirinin dosyasını değiştirmez.

## Rollout ve rollback

1. Migration ve uygulama aynı adayda, `API_OBSERVABILITY_ENABLED=false` ile dağıtılır.
   Migration-first mixed-version penceresinde eski API'nin legacy request ID'si ham
   saklanmaz; audit fonksiyonu yeni server 32-hex kodu üretip 500 regresyonunu önler.
2. Runtime role/retention/config readiness doğrulanır; eski API davranışı smoke edilir.
3. Flag yalnız küçük staging/canary diliminde açılır; queue drop, DB write failure,
   API p95 ve tablo büyümesi gözlenir.
4. Stop koşulunda flag kapatılır; tablo/history korunur, ana API çalışmaya devam eder.
5. Gerekirse yalnız `010` retention bakımını taşıyan önceki revizyona dönülür;
   additive 0017 sökülmez ve bounded purge sürer. `0017` öncesine dönüş gerekiyorsa
   runtime rolüyle eşdeğer periyodik purge önceden kurulup prova edilmeden rollback yapılmaz.

Bu çalışma ağacında rollout yapılmaz. Production URL, collector, alert, canary,
rollback rehearsal ve insan onayı ayrıca kanıtlanmadan promotion yoktur.
