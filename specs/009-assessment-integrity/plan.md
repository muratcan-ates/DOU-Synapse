# Uygulama Planı: 009 Assessment Integrity

**Branch**: `009-assessment-integrity` | **Base**: `2f40ac193114b896d33ef73e72ea51cc51f34d26`

## Teknik yön

- PostgreSQL migration: `0016_assessment_integrity.sql`
- Runtime DB identity: gerçek LOGIN `dou_api_runtime`; NOLOGIN yetki taşıyıcısı
  `dou_app`; dar ve doğrulanan rol grafiği; bütün owner'larda güvenli default ACL;
  hassas assessment yüzeyinde exact `session_user` kapısı
- Backend: mevcut FastAPI/SQLAlchemy assessment modülleri
- Frontend: yalnız soru amacı seçimi ve sonuç-yayın durumunu göstermek için mevcut
  Next.js ekranları; yeni framework yok
- AI değişiklik kaydı: `009-assessment-integrity-r1`, R3
- Kill switch: üretim ve örnek ayarda fail-closed
  `ASSESSMENT_BLUEPRINT_ENABLED=false`; yalnız doğrulanmış yerel/CI ortamları açıkça
  `true` verir.

`0016` numarası bütün yerel worktree ve ref'lerde tarandı; çakışan migration/spec
bulunmadı. 005'in “şema kusuru 0016 forward-fix ile düzeltilir” kararıyla da uyumludur.

## Dilimler

1. **Sözleşme ve kanıt**: Speckit, threat model, dossier root, migration numarası.
2. **Runtime identity boundary**: carrier ACL kesimi, exact LOGIN readiness,
   rol-grafiği/default-ACL preflight'leri, eski pool drain kanıtı ve doğrudan SQL
   negatifleri.
3. **Question boundary**: purpose enum/kolon, RLS, app list gate, practice/blueprint
   filtreleri, published-item yaşam-döngüsü koruması ve karma kullanımdaki eski
   oturum sahibine dar, referansları değiştirmeyen devam istisnası.
4. **Feedback boundary**: snapshot release time, results GET, bütün score yüzeylerinde gizleme.
5. **Scoring**: question-id tabanlı `ExamItem.points` haritası ve weighted aggregate.
6. **Grading**: untrusted zarf, exact rubric/evidence validation, adversarial tests.
7. **UI**: instructor purpose seçimi/badge, öğrenci feedback bekleme durumu.
8. **Evidence**: hedefli + tam test, RLS/mutasyon, OpenAPI, docs ve R3 dossier.

## Anayasa kontrolü

- Kaynak ve ölçüm: puan yalnız doğrulanmış cevap/evidence ve frozen points'ten türetilir.
- Yetki: student görünürlüğü hem API hem RLS'te bağımsız kapanır.
- Runtime kimliği: kullanıcı GUC'si tek başına backend güveni değildir; hassas ham
  yüzey gerçek `dou_api_runtime` bağlantısı olmadan açılmaz.
- Geriye uyumluluk: resmî kâğıtla ortak eski soruyu kullanan kâğıtsız oturumun soru
  sırası/cevap kimliği değişmez; yalnız sahibi dar RLS dalıyla devam eder, resmî satır
  assessment-only kalır ve yeni practice seçimine girmez.
- Yetki kalıcılığı: başka owner'ların tablo default ACL kayıtları gelecekte
  carrier/worker ayrıcalığını; ilgili function owner'ların global/schema-local
  varsayılanları da yeni `app` fonksiyonunda PUBLIC EXECUTE'ı yeniden açamaz.
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

docs/deployment.md
docs/security.md
specs/001-course-assistant-mvp/quickstart.md
evaluation/README.md
```

Aktif `feat/rubric-breakdown-ui`, `docs/port-refresh` ve dependency bakım dalları
incoming kabul edilir; lockfile, screenshot ve rubric UI satırları bu dalda yeniden
yazılmaz. Entegrasyonda onların ardından rebase gerekir.

## Rollout ve rollback

Kod ve örnek ortam varsayılanı `false`tır; doğrulanmış yerel Compose ve CI akışları
özelliği açıkça `true` yapar. Bu aday henüz hiçbir ortama dağıtılmadı; korumalı ortam
secret'ında ilk açılış `false` kalır. Engineering, domain ve security/privacy onayları
ile gerçek-provider + staging kanıtı olmadan öğrenci kohortuna promotion yapılmaz.
Stop koşulları: herhangi bir assessment soru sızıntısı, erken feedback, yanlış
weighted score, untrusted text'ten puan değişimi, sonuç ucunda raw answer/log sızıntısı
veya runtime identity readiness hatası.

Migration kesimi: `0016`dan önce `dou_api_runtime` LOGIN/secret/üyeliği önceden
hazırlanır ve aynı production DSN/pooler yolunda `session_user` doğrulanır. Trafik
kesildikten sonra owner/admin ayrı bir commit'te `ALTER ROLE dou_app NOLOGIN
PASSWORD NULL` uygular; eski login'in başarısızlığı ve `pg_stat_activity=0`
ölçülür. Ancak bundan sonra `0016` koşar. Migration ilk kesimi yapmak yerine bu
durumu assert eder/normalize eder; aktif carrier oturumu veya beklenmeyen üyede
fail-closed durur. `dou_app`ın parent rolü, runtime'ın üyesi veya beklenmeyen parent'ı
varsa da durur. Bütün ilgili owner'ların default ACL kayıtlarını temizleyebilmek için
migration yeterli admin yetkisiyle çalışmalıdır; kalıntı grant commit'i engeller.
`SET ROLE` ile runtime adı taklit etmek yeterli değildir.

Rollback sırası:

1. `ASSESSMENT_BLUEPRINT_ENABLED=false` ile yeni resmî oturumları durdur.
2. Mevcut oturumların get/answer/finish/results yollarını açık tut.
3. Yalnız post-`0016` sözleşmesiyle doğrulanmış revizyona dön veya fix-forward et;
   eski revizyon da `dou_api_runtime` DSN kullanır. `dou_app` LOGIN/parolasını açma.
   Additive 0016 kolon/enum/kanıtını sökme.
4. Aynı candidate/deployment kimliğiyle soru sızıntısı 0 ve mevcut oturum erişimi
   doğrulanmadan flag'i açma.
