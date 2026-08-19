# Contract: Staging Preflight Report v1

```json
{
  "schema_version": 1,
  "kind": "staging_preflight",
  "generated_at": "2026-08-19T20:00:00Z",
  "source_sha": "40-hex",
  "image_digest": "sha256:64-hex",
  "overall": "blocked",
  "checks": [
    {
      "name": "candidate",
      "status": "passed",
      "summary": "Candidate sözleşmesi ve kaynak kimliği doğrulandı.",
      "safe_details": {"record_type": "candidate"}
    }
  ],
  "unrun": [],
  "claim_boundary": "Bu kayıt promotion evidence veya staging-verified iddiası değildir."
}
```

## Exit Codes

- `0`: bütün zorunlu kontroller `passed`
- `1`: en az bir gerçek kontrol `failed`
- `2`: eksik config/kanıt nedeniyle `blocked` veya `not_run`

Başarısızlık ve blocked durumunda da yapılandırılmış rapor yazılır. Şema dışı alan, ham response body ve secret yasaktır.

