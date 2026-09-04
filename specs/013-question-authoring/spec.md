# 013 — Eğitmen soru yazımı ve sınav planına geçiş

Base: ba69ff9eec0a2867614dd145eb6e995f6c0af5ac (origin/main, 4 Eylül 2026'da doğrulandı).
Owner: Muratcan Ateş. Branch: 013-question-authoring. Risk: R3 (assessment, draft editing and exam integrity).

## Problem ve kullanıcı yolculuğu

Öğretmen soru üretiminde öğrenme çıktısı ve zorluk seçemiyor; mevcut servis bunları kabul etse de API taşımıyor. Üretilen soru düzenlenemiyor. Sınıflandırılmamış sorular blueprint yayın kapısından geçemiyor. Öğretmen aynı ders içinde konu/çıktı/zorluk seçer, kaynaklı taslak üretir, metin/anahtar/rubriği inceler ve düzeltir, onaylar ve mevcut blueprint sürümüne ekleyip yayımlar.

## Gereksinimler

- Generation request optional learning_outcome_id/difficulty pair: both populated or both null. Legacy unclassified practice generation remains available.
- Outcome belongs to selected course and its topic is null or matches the question topic. API and database independently protect the relation.
- Question response carries learning_outcome_id, difficulty and existing source_stale truthfully.
- Instructor-only authoring capability read and draft update endpoints. Deployment flag is disabled by default, local example opts in explicitly. Off switch prevents classified generation and edits, legacy generation remains unchanged.
- Full replacement of type-specific payload and explicit nullable classification; unknown envelope fields rejected. Course, topic, type, source, creator/status/review metadata are never client-editable.
- Only never-used draft questions may change. Approved/rejected records and any question attached to a paper, session or answer remain immutable in content/classification. No return to draft after review.
- Edit and approve serialize on the same question row. SQL enforces the same content boundary for direct application-role access.
- Existing payload parsers validate all four types. MCQ distractor references remain in course; new edited essays require a nonempty rubric totaling 100. Legacy read normalization is preserved.
- UI provides normal Turkish fields for MCQ, essay/short answer, code trace and bug hunt. No raw JSON editor. Loading/error/disabled/saving/cancel states and keyboard access use existing components/tokens.
- Existing source-stale signal is visible during review. Classification is shown in pool and flows into existing blueprint readiness.

## Kabul senaryoları

1. Through real API/browser, create course/topic/outcome, upload a source, generate a classified draft, edit it, approve, build and publish one valid blueprint without SQL question insertion.
2. Student/nonmember/admin without instructor membership cannot edit; mixed role is course-scoped.
3. Another course's outcome or distractor source is denied; invalid payload/classification produces no partial write.
4. Approved/rejected/attached draft edit and reviewed-to-draft are denied, including direct SQL. Removing the DB guard makes its targeted check fail.
5. Approval racing with edit cannot mutate content after review. Off switch blocks authoring writes; old generation works.
6. All relevant backend/web suites, types/build, OpenAPI, docs and focused browser checks run against the candidate; results are recorded, no fake-provider result is called real model quality.

## Kapsam dışı

Student exam discovery/resume/history; delayed feedback; grading redesign; official/practice purpose split; new model/provider, source replacement workflow, OCR, deployment and production promotion. Existing unmerged 009 is reference only, not wholesale integration.
