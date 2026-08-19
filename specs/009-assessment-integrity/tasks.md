# Görevler: 009 Assessment Integrity

## P0 — Sözleşme

- [x] T001 Speckit şartname/plan/research/data-model/API/threat/quickstart yaz.
- [x] T002 `009` feature ve `0016` migration çakışma taraması yap.
- [x] T003 R3 dossier root ve boş olmayan, dürüst yerel evidence planı oluştur.

## P1 — Question boundary

- [x] T101 `question_purpose`, backfill/index, ORM/schema contract.
- [x] T102 Purpose-aware RLS + least-privilege grants/helper.
- [x] T103 Instructor-only list, purpose-aware generate/practice/blueprint selection.
- [x] T104 Active exam → new practice lock; own session devamı.
- [x] T105 Published/superseded item question reject/delete/UPDATE guard.
- [x] T106 RLS referans + named mutations.
- [x] T107 Generate classification pair + draft-only classification PATCH.
- [x] T108 `dou_api_runtime` exact-session identity, carrier ACL ve wrong-role readiness.
- [x] T109 Ayrı-commit NOLOGIN + yaşayan eski pool/drain migration preflight kanıtı.
- [x] T110 Karma kullanımdaki resmî soruda yalnız legacy own-session sahibine dar
  devam dalı ver; yeni practice seçimini kapalı tut; sahip/oturumsuz çift kanıtı ekle.
- [x] T111 `dou_app` parent/runtime member grafiği preflight'i ve bütün owner'larda
  tablo default ACL temizliği; ilgili function owner'larda global/schema-local
  PUBLIC EXECUTE kapısı ve etkin probe kanıtı ekle.

## P2 — Feedback ve scoring

- [x] T201 `feedback_available_at` snapshot ve closes_at fail-closed start.
- [x] T202 Ortak release helper; session/list/finish/results aynı kararı kullanır.
- [x] T203 Idempotent `GET results`; pre-release çözüm/source sorgusu yok.
- [x] T204 Question-id → points helper ve weighted score.
- [x] T205 10/90, reorder, ungraded, legacy regressions.

## P3 — Grading hardening

- [x] T301 Untrusted answer/reference/source blocks + fixed-point escaping.
- [x] T302 Exact rubric set ve evidence membership validation.
- [x] T303 Injection/missing/duplicate/unknown/forged evidence tests.
- [x] T304 Deterministik MCQ/short-answer provider-call-zero regressions.

## P4 — Kill switch ve UI

- [x] T401 `ASSESSMENT_BLUEPRINT_ENABLED=false` kod/örnek varsayılanı, açık opt-in,
  503 contract ve existing-session exception.
- [x] T402 Instructor question-purpose control and labels.
- [x] T403 Student pending-feedback/results UX implementation + helper tests;
  gerçek browser/mobile kapısı T502'de kalır.

## P5 — Kanıt

- [ ] T501 Hedefli + tam backend (961/961), Ruff/format/mypy tamam; OpenAPI finali bekliyor.
- [ ] T502 Web library (402/402), typecheck ve production build tamam; gerçek browser
  kapısı disk/bağımlılık uygunluğunda bekliyor.
- [ ] T503 Dossier/evidence hash binding, pending named approvals, rollback rehearsal.
- [ ] T504 Geçici DB/API/browser cleanup; worktree clean handoff.
