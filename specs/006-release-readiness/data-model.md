# Data Model: Staging Preflight Report

Yeni veritabanı entity'si veya migration yoktur.

## Report

- `schema_version`: sözleşme sürümü (`1`)
- `kind`: sabit `staging_preflight`
- `generated_at`: UTC RFC 3339 zaman damgası
- `source_sha`: doğrulanan checkout SHA
- `image_digest`: candidate immutable digest'i
- `overall`: `passed | failed | blocked`
- `checks`: sıralı `CheckResult` listesi
- `unrun`: `not_run` durumundaki kontrol adları
- `claim_boundary`: bunun promotion evidence olmadığını belirten sabit metin

## CheckResult

- `name`: sabit kontrol kimliği
- `status`: `passed | failed | blocked | not_run`
- `summary`: secret içermeyen kısa açıklama
- `safe_details`: yalnız boolean, sayı, checksum, genel URL veya immutable referans

## Invariants

1. Zorunlu bir kontrol `passed` değilse `overall: passed` olamaz.
2. En az bir `failed` varsa overall `failed`; aksi halde geçmeyen zorunlu kontrol overall `blocked` üretir.
3. Secret değerleri model alanı değildir.
4. `not_run` kontroller aynı zamanda `unrun` listesinde yer alır.

