# Görevler: 010 API Observability

## Speckit ve sınırlar

- [x] T001 Base/candidate, mevcut admin ve eski dal ilişkisini doğrula.
- [x] T002 Privacy veri sözlüğü, non-goals ve SLO dilini dondur.
- [ ] T003 R3 change dossier/evidence root'unu final candidate'a bağla.

## Veritabanı ve runtime

- [ ] T101 `0017_api_observability.sql`: tablo, index, recorder, query, purge.
- [ ] T102 Runtime/admin/worker/PUBLIC ACL ve çift yetki sınırı.
- [ ] T103 Bounded queue, ayrı pool, batch, drop state ve bounded shutdown.
- [ ] T104 Main middleware: request ID, route template, bütün response sınıfları.
- [ ] T105 Kill switch, retention ve release revision ayarları.

## API ve OpenAPI

- [ ] T201 POST admin query schema/router.
- [ ] T202 HTTPBearer/OpenAPI security; health public.
- [ ] T203 Unified 404/405/422/500 ErrorEnvelope.
- [ ] T204 Local docs CSP + production fail-closed docs.
- [ ] T205 Deterministic OpenAPI export ve drift testi.

## Ürün arayüzü

- [ ] T301 DESIGN.md workbench/mobil pattern.
- [ ] T302 Varsayılan/lazy-keepalive API akışı sekmesi.
- [ ] T303 Zaman aralığı, filter, support code, manual/live refresh.
- [ ] T304 Mobil labelled rows; raw belge/event kimliği çizimini kaldır.
- [ ] T305 Unit/type/build/browser accessibility kanıtı.

## Güvenlik ve doğrulama

- [ ] T401 Backend 2xx/4xx/422/404/405/500 ve telemetry failure matrisi.
- [ ] T402 RLS referans + bağımsız mutation kanıtı.
- [ ] T403 DB/API/DOM sensitive-field negatifleri.
- [ ] T404 Full backend/web, OpenAPI, docs ve secret/diff kontrolleri.
- [ ] T405 Süreç, test DB, `.next`, node_modules ve disk temizliği.
- [ ] T406 Engineering, product/operations ve security/privacy onayları pending kaydı.

