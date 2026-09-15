# Modülerizasyon — kalan işler ve doğrulanmış bölme planları (15 Eylül 2026)

`docs/team/modularization-v2-audit.md` (16 Ağustos) planının durumu ve 15 Eylül'de yapılan
paralel analizin (5 plan + 5 düşmanca denetim) sonucu. Uygulayan oturum bu belgeyi
`OZELLIK-PLANI-V2.md` §0 kurallarıyla birlikte okur. Satır numaraları **15 Eylül `d574d50`**
başına göredir; uygulamadan önce yeniden ölçülür.

## 1. Ağustos planının durumu

| PR | İş | Durum (ölçüldü) |
|---|---|---|
| 1 | Test fixture konsolidasyonu → `factories.py` | ✅ var |
| 4 | `SourceInfo` → `lib/types.ts`, `InstructorGate` | ✅ var |
| 5 | `useSubmit` | ✅ var |
| 6 | `paginate`/`paginate_keyset`/`load_owned` | ✅ `core/pagination.py`, `api/deps.py` |
| 7 | `USER_TEXT`, `EvidenceLevel` → `contracts.py` | ✅ var |
| 9 | core→modules tersinmesi | ✅ fonksiyon-yerel import (`core/vector_space.py:85,102`, `core/warmup.py:92`) |
| 11 | `chat.py` bölünmesi | ✅ 1622 → 804; `chat_cache.py`, `chat_history.py`, `modules/agent/*` |
| 12 | `ChatScreen` bölünmesi | kısmen: `ChatScreen` 578 → 161 satır; dosya 682, beş bileşen içeride |
| 2, 3, 8, 10 | CI mutasyon kanıtları, sözleşme hijyeni, sayfalama→hassas router'lar, hata zarfı openapi | açık |

**15 Eylül'de yapılan:** `blueprints/page.tsx` 1165 → 620 (`e39ea62`), `admin/page.tsx` 829 → 173
(`e8af822`); on yeni bileşen dosyası `components/blueprint/`, `components/admin/`. Bit bazında
özdeş taşıma; sensitive değil.

## 2. Kalan büyük dosyalar ve karar

| Dosya | Satır | Karar | Neden |
|---|---|---|---|
| `apps/api/app/api/exams.py` | 1346 | **Böl** (§3.1) — en riskli, dossier | 8 fonksiyonluk saf projeksiyon kümesi; R3 |
| `apps/api/app/modules/assessment/grading.py` | 771 | **Böl** (§3.2) — dossier | kaynak malzeme bloğu puanlama modülünden `questions.py:60`'a sızıyor |
| `apps/api/app/modules/assessment/quality.py` | 854 | **Bölme** | 854'ün 418'i kod, kalanı docstring/yorum; tek tüketici kendi testi; bant yorumlarıyla zaten ayrık |
| `apps/api/app/api/chat.py` | 804 | Dokunma | zaten bölünmüş; `post_chat` R3 kalbi |
| `apps/web/app/courses/[courseId]/chat/page.tsx` | 682 | Dokunma (sunum sonrası bileşen çıkarma) | R3 web; beş bileşen 130 satır civarı |

## 3. Doğrulanmış planlar (denetim düzeltmeleri işlenmiş)

### 3.1 `exams.py` → yeni dosya: `apps/api/app/api/exam_feedback.py`

**Taşınan küme (kapalı — exams.py'de kalan hiçbir ada referans yok, döngü riski sıfır):**
`_feedback_payload` (191), `_chunk_id` (219), `_grounded_feedback_evidence` (227),
`_answer_is_displayable` (247), `_answer_feedback` (290), `_grounded_missing_criterion` (379),
`_rubric_breakdown` (413), `_feedback_score` (451). Satır aralığı 186–422 + 451–452.
`_saved_feedback`, `_session_out`, `_results_locked`, `_require_help_unlocked`,
`_completed_results_out`, `_finish_message` **kalır** (DB'ye dokunur ya da rota katmanı; testler
`exam_api._results_locked`, `_completed_results_out`, `acquire_user_assessment_lock`,
`load_source_material` adlarını `exams` ad alanında monkeypatch'liyor — bunlar kümenin dışında).

**Yeni dosyanın import'ları — plan 17 saydı, gerçek 23.** Şu altısı exams.py'de de kalır,
**kopyalanır**: `from collections.abc import Sequence`, `from uuid import UUID`,
`from app.models.assessment import Answer, Question`, `app.schemas.assessment` bloğuna
`AnswerFeedbackOut`, `SourceRefOut`. (Ölçüldü: eksik hâlde ruff 24 × F821.)

**Re-export — tek blok yazılamaz.** ruff isort ayarı `X as X` biçimini ayrı ifadeye zorluyor;
emsal `chat.py:56-67` üç ayrı ifade. Doğru biçim **beş** ifade:
```python
from app.api.exam_feedback import (
    _answer_feedback,
    _chunk_id,
    _feedback_payload,
    _feedback_score,
)
from app.api.exam_feedback import (
    _answer_is_displayable as _answer_is_displayable,
)
# … _grounded_feedback_evidence, _grounded_missing_criterion, _rubric_breakdown için birer ifade
```
Zorunlu re-export gerekçesi: `apps/api/tests/test_code_grading_criteria.py:14`
`from app.api.exams import _answer_feedback, _feedback_payload`.

**Diğer düzeltmeler:**
- `_feedback_score` kesimi 4 ardışık boş satır bırakıyor → `ruff format` koş.
- `.ai/policy.json`'a `{"pattern": "apps/api/app/api/exam_feedback.py", "minimum_risk": "R3"}`
  ekle: taşınan `_answer_is_displayable` öğrenciye puan/çözüm gösterilip gösterilmeyeceğine karar
  veren kaynak doğrulama kapısıdır. `policy.json` kendisi R3 → dossier `artifacts`'ına
  `exams.py` + `exam_feedback.py` + `policy.json` üçü girer. (`chat_cache.py`/`chat_history.py`
  aynı boşlukta — ayrı iş.)
- Bayat atıflar `exams.py:160` → yeni değer **161** (17 import satırı çıkıyor, 18 giriyor):
  `apps/api/app/api/chat.py:691, :721`, `apps/api/tests/test_chat_isolation_layers.py:7, :10`.
  Kendi diff'inde yeniden ölç. `specs/002-*` altındaki ~15 atıfa dokunma (kapanmış şerit, kapı ölçmüyor).
- openapi: `ENVIRONMENT=local DEV_AUTH_ENABLED=true DATABASE_URL=… python -c "from app.main import create_app; …"`
  → **61 yol / 135 şema**, sıra dâhil özdeş kalmalı (plandaki 57 yanlıştı).
- `docs_check` `backend.mypyFiles = 124` → 125: `--duzelt` `docs/security.md:366`'yı yazar;
  `specs/005/spec.md`'ye de dokunuyorsa (başka şerit) PR'da belirt ya da `ENGEL`.
- Dossier: R3, `require_feature_flag` vb. için `flag_state="not-applicable"` + kill switch =
  geri alma yordamı (bkz. §3.2 aynı kural). Numara şerit aralığından; bilinmiyorsa `ENGEL`.

**Kapılar:** tam pytest (özellikle `test_exams.py`, `test_exam_workspace.py`, `test_code_grading_criteria.py`,
`test_explanation_feedback_api.py`, `test_study_continuity.py`) + ruff/format/mypy + openapi özdeşlik + docs_check.

### 3.2 `grading.py` → iki yeni dosya

| Yeni dosya | Aralık | Semboller | Neden |
|---|---|---|---|
| `apps/api/app/modules/assessment/source_material.py` | 74–172 | `SNIPPET_CHARS`, `chunk_location`, `_best_snippet`, `SourceMaterial`, `load_source_material`, `load_source_refs` | puanlama yapmaz; chunk okur, `SourceRefOut` üretir; `api/questions.py:60` yalnız bunun için R3 puanlama modülünü import ediyor |
| `apps/api/app/modules/assessment/rubric_verdict.py` | 342–514 | `_RubrikSatiri`, `_LlmVerdict`, `_SYSTEM_PROMPT`, `_reference_block`, `_sources_block`, `_parse_verdict`, `payload_rubric`, `_rubric_breakdown`, `grounded_criterion_is_valid` | LLM karar şeması ve ayrıştırma |

**Denetim düzeltmeleri:**
- Modül 2 çıkınca `grading.py`'de `Field` (42), `RubricItem` (66), `normalized_rubric` (68) artık
  kullanılmıyor → F401. `from pydantic import BaseModel, ValidationError` yap; ikisini şema
  bloğundan sil; üçü `rubric_verdict.py`'ye gider.
- `__all__` yazılırsa **RUF022** açık: isort düzeninde sırala, `ruff check` ile doğrula. `__all__`
  yalnız re-export'ları değil grading.py'de **kalan** public adları da içersin (`GradingOutcome`,
  `grade_answer`, `grade_mcq`, `grade_short_answer`, `grade_with_llm`, `score_of`,
  `grounded_feedback_is_valid`, `literal_feedback_quote`) — yüzey daralmasın.
- `SNIPPET_CHARS = 320` üç dosyada kullanılıyor → tek kaynak `source_material.py`; diğerleri oradan okur.
- `app/core/logging.py:54` `_EXCEPTION_EVENTS` sözlüğü `app.assessment.grading` logger adını
  çiviliyor — logger adı **değişmez** (taşınan kod aynı logger'ı `getLogger` ile alır ya da grading'de kalır).
- Dossier R3: `rollout.feature_flag` = `deployment.feature_flag` (ör. `assessment_grading_module_split`),
  `flag_state="not-applicable"`, kill switch = commit geri alma, assignment metninde "sticky";
  `artifacts` üç dosya (grading + iki yeni) gerçek sha256 ile.
- Tüketici güncellemesi: `api/questions.py:60`, `api/exams.py` import'ları yeni yollara; eski yol
  re-export ile çalışmaya devam eder.

**Kapılar:** `pytest tests/test_assessment.py tests/test_code_grading_criteria.py tests/test_logging_redaction.py tests/test_exception_log_privacy.py` + tam süit; ruff/format/mypy; docs_check `--duzelt` (mypyFiles +2).

### 3.3 Bit-özdeşlik kanıtı (her bölmede)

Taşınan bloklar `git show <taban>:<dosya>` aralığıyla karşılaştırılır; yalnız `export`/re-export
farkı kabul edilir. 15 Eylül web bölmelerinde kullanılan betik mantığı: aralıkları kes, yeni
dosyanın import'larını taşınan koddan **türet** (plan bir `Badge`'i kaçırmıştı; türetme kaçırmaz),
yorumları taramadan önce sil (yalnız docblock'ta anılan ad ölü import olmasın).

## 4. İnsan kararı bekleyenler (`ENGEL`)

1. Dossier numara aralığı (bu iş için).
2. `.ai/policy.json`'a `exam_feedback.py` (ve `chat_cache.py`, `chat_history.py`) R3 eklenmesi.
3. `docs_check --duzelt`'in `specs/005/spec.md`'ye (başka şerit) yazması kabul mü.
4. `LINEAGE_DUPLICATE_REVISION`: `.ai/changes/101-ci-evidence-wiring-r1.json` ve
   `151-ci-evidence-wiring-r1.json` aynı soy, aynı revizyon — hangisi r2 olacak.
