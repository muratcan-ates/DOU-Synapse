# Uygulama Planı: 009 Assessment Integrity

**Branch**: `009-assessment-integrity` | **Base**: `2f40ac193114b896d33ef73e72ea51cc51f34d26`

## Teknik yön

- PostgreSQL migration: `0016_assessment_integrity.sql`
- Backend: mevcut FastAPI/SQLAlchemy assessment modülleri
- Frontend: yalnız soru amacı seçimi ve sonuç-yayın durumunu göstermek için mevcut
  Next.js ekranları; yeni framework yok
- AI değişiklik kaydı: `009-assessment-integrity-r1`, R3
- Kill switch: `ASSESSMENT_BLUEPRINT_ENABLED=true`

`0016` numarası bütün yerel worktree ve ref'lerde tarandı; çakışan migration/spec
bulunmadı. 005'in “şema kusuru 0016 forward-fix ile düzeltilir” kararıyla da uyumludur.

## Dilimler

1. **Sözleşme ve kanıt**: Speckit, threat model, dossier root, migration numarası.
2. **Question boundary**: purpose enum/kolon, RLS, app list gate, practice/blueprint
   filtreleri, published-item yaşam-döngüsü koruması.
3. **Feedback boundary**: snapshot release time, results GET, bütün score yüzeylerinde gizleme.
4. **Scoring**: question-id tabanlı `ExamItem.points` haritası ve weighted aggregate.
5. **Grading**: untrusted zarf, exact rubric/evidence validation, adversarial tests.
6. **UI**: instructor purpose seçimi/badge, öğrenci feedback bekleme durumu.
7. **Evidence**: hedefli + tam test, RLS/mutasyon, OpenAPI, docs ve R3 dossier.

## Anayasa kontrolü

- Kaynak ve ölçüm: puan yalnız doğrulanmış cevap/evidence ve frozen points'ten türetilir.
- Yetki: student görünürlüğü hem API hem RLS'te bağımsız kapanır.
- Sınav güvenliği: sonuç yayın zamanı son olası sınav bitişinden önce olamaz.
- Abstention: notlandırılamayan yanıt 0 uydurmaz, paydaya girmez.
- Tek sahiplik: paper id/weights tek assessment helper'ında; feedback policy tek helper'da.
- Kırılabilir kanıt: her kritik koşulun adı konmuş negatif/mutasyon testi vardır.

İstisna yoktur. Bu dal, normal feature skoru yüksek başka işleri security blocker
kapanana kadar geriye iter.

## Dosya sahipliği

```text
supabase/migrations/0016_assessment_integrity.sql
supabase/tests/rls_assessment_integrity.sql
supabase/tests/rls_assessment_integrity_mutation_check.sh

apps/api/app/models/assessment.py
apps/api/app/schemas/assessment.py
apps/api/app/api/questions.py
apps/api/app/api/blueprints.py
apps/api/app/api/exams.py
apps/api/app/modules/assessment/exam_paper.py
apps/api/app/modules/assessment/exam_state.py
apps/api/app/modules/assessment/grading.py
apps/api/app/core/config.py
apps/api/app/core/errors.py
apps/api/tests/test_assessment_integrity.py
apps/api/tests/test_grading_integrity.py

apps/web/app/courses/[courseId]/questions/page.tsx
apps/web/app/courses/[courseId]/exams/**
apps/web/lib/types.ts

.ai/changes/009-assessment-integrity-r1.json
.ai/evidence/009-assessment-integrity-local-r1.json
specs/009-assessment-integrity/**
```

Aktif `feat/rubric-breakdown-ui`, `docs/port-refresh` ve dependency bakım dalları
incoming kabul edilir; lockfile, screenshot ve rubric UI satırları bu dalda yeniden
yazılmaz. Entegrasyonda onların ardından rebase gerekir.

## Rollout ve rollback

Varsayılan flag mevcut davranışı korumak için `true`; korumalı ortamda ilk açılış
engineering/domain/security onayından sonra yapılır. Stop koşulları: herhangi bir
assessment soru sızıntısı, erken feedback, yanlış weighted score, untrusted text'ten
puan değişimi veya sonuç ucunda raw answer/log sızıntısı.

Rollback sırası:

1. `ASSESSMENT_BLUEPRINT_ENABLED=false` ile yeni resmî oturumları durdur.
2. Mevcut oturumların get/answer/finish/results yollarını açık tut.
3. Uygulama commit'ini geri al veya fix-forward et; additive 0016 kolon/enum'u sökme.
4. Aynı candidate/deployment kimliğiyle soru sızıntısı 0 ve mevcut oturum erişimi
   doğrulanmadan flag'i açma.

