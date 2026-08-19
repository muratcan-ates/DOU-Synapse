# Quickstart: Release Readiness

## Ağsız birim kanıtı

```bash
python3 -m unittest discover -s .release -p 'test_staging_preflight.py'
```

## Gerçek staging preflight

Secret'ları shell history'ye argüman olarak yazmayın; yalnız environment'tan verin.

```bash
python3 .release/staging_preflight.py \
  --candidate release-evidence/candidate.json \
  --api-url "$STAGING_API_URL" \
  --web-url "$STAGING_WEB_URL" \
  --course-id "$STAGING_SMOKE_COURSE_ID" \
  --migration-decision none \
  --backup-evidence-ref "$STAGING_BACKUP_EVIDENCE_REF" \
  --rollback-evidence-ref "$STAGING_ROLLBACK_EVIDENCE_REF" \
  --previous-digest "$PREVIOUS_DIGEST" \
  --json-out release-evidence/staging-preflight.json \
  --markdown-out release-evidence/staging-preflight.md
```

İlk koşu candidate artifact, migration ledger veya dış kanıt yoksa `blocked` dönebilir. Bu beklenen fail-closed davranıştır; deploy başarısı değildir.
