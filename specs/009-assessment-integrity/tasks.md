# Görevler: 009 Assessment Integrity

## P0 — Sözleşme

- [x] T001 Speckit şartname/plan/research/data-model/API/threat/quickstart yaz.
- [x] T002 `009` feature ve `0016` migration çakışma taraması yap.
- [ ] T003 R3 dossier root ve boş olmayan, dürüst yerel evidence planı oluştur.

## P1 — Question boundary

- [ ] T101 `question_purpose`, backfill/index, ORM/schema contract.
- [ ] T102 Purpose-aware RLS + least-privilege grants/helper.
- [ ] T103 Instructor-only list, purpose-aware generate/practice/blueprint selection.
- [ ] T104 Active exam → new practice lock; own session devamı.
- [ ] T105 Published/superseded item question reject/delete/UPDATE guard.
- [ ] T106 RLS referans + named mutations.

## P2 — Feedback ve scoring

- [ ] T201 `feedback_available_at` snapshot ve closes_at fail-closed start.
- [ ] T202 Ortak release helper; session/list/finish/results aynı kararı kullanır.
- [ ] T203 Idempotent `GET results`; pre-release çözüm/source sorgusu yok.
- [ ] T204 Question-id → points helper ve weighted score.
- [ ] T205 10/90, reorder, ungraded, legacy regressions.

## P3 — Grading hardening

- [ ] T301 Untrusted answer/reference/source blocks + fixed-point escaping.
- [ ] T302 Exact rubric set ve evidence membership validation.
- [ ] T303 Injection/missing/duplicate/unknown/forged evidence tests.
- [ ] T304 Deterministik MCQ/short-answer provider-call-zero regressions.

## P4 — Kill switch ve UI

- [ ] T401 `ASSESSMENT_BLUEPRINT_ENABLED`, 503 contract, existing-session exception.
- [ ] T402 Instructor question-purpose control and labels.
- [ ] T403 Student pending-feedback/results UX; keyboard/mobile/error states.

## P5 — Kanıt

- [ ] T501 Hedefli + tam backend, static checks ve OpenAPI.
- [ ] T502 Frontend/typecheck/browser (disk kapısı uygunsa).
- [ ] T503 Dossier/evidence hash binding, pending named approvals, rollback rehearsal.
- [ ] T504 Geçici DB/API/browser cleanup; worktree clean handoff.

