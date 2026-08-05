# Takım Koordinasyonu — Dosya Sahipliği ve Çakışma Önleme

> Bu belge takımın **tek koordinasyon kaynağıdır**. Kim hangi dosyaya dokunur, kim
> dokunamaz, ortak dosyalarda ne yapılır — hepsi burada. İş listesi ise
> [`specs/001-course-assistant-mvp/tasks.md`](../../specs/001-course-assistant-mvp/tasks.md).

**Temel kural:** Her dosyanın **tek sahibi** vardır. Sahibi olmadığın bir dosyayı
değiştirmen gerekiyorsa, kendin düzenlemek yerine sahibine söyle. İstisna: aşağıdaki
"sıcak dosyalar" bölümündeki protokol.

---

## 1. Roller ve sahiplik

| # | Rol | Kişi | Ana fazlar |
|---|-----|------|-----------|
| R1 | Backend / RAG | **Eren** | A (retrieval), B-üretim, C-backend |
| R2 | Guardrail & QA | **Eren** | B-guardrail, D-Sokratik, güvenlik koşuları |
| R3 | Assessment & Analytics | **Metehan** | D-sınav/soru, E-mastery |
| R4 | Frontend | **Muratcan** | C/D/E'nin web ayağı + lead + sıcak dosya hakemliği |
| R5 | Data & Eval | **Metehan** | F (ölçüm), H (belgeler), örnek materyal |

**Dağılım gerekçesi:** R1+R2 tek boru hattıdır (retrieval → generation → guardrail);
iki kişiye bölmek arayüz sürtüşmesi yaratır, o yüzden ikisi Eren'de. R3 kendi migration'ı
ve uçları olan ayrılabilir bir dikey, R5 bağımsız ölçüm işi — ikisi Metehan'da; zamanlama
da uyumlu (Eren'in yoğunluğu G5-G8, Metehan'ınki G7-G12). Takım büyürse önce R2 Eren'den
ayrılır, sonra 6. kişi R4'e verilir (PLAN §4 darboğaz uyarısı).

**Okuma listesi:** Eren → `01_BACKEND_RAG_BRIEF.md` + `02_GUARDRAIL_QA_BRIEF.md`;
Metehan → `03_ASSESSMENT_BRIEF.md` + `05_DATA_EVAL_BRIEF.md`; herkes → bu belge +
`AI_ASISTAN_BASLANGIC.md` + `HANDOFF.md`.

---

## 2. Dosya sahipliği matrisi

Bir dosyanın karşısında hangi rol varsa, **o dosyayı yalnız o rol düzenler**.

### Backend — R1 (Backend/RAG)

```
apps/api/app/modules/retrieval/          ← TAMAMI R1
apps/api/app/modules/generation/         ← TAMAMI R1
apps/api/app/api/chat.py                 ← R1 (Sokratik entegrasyonu dahil, T027)
apps/api/app/models/chat.py              ← R1
apps/api/app/schemas/chat.py             ← R1
supabase/migrations/0003_chat.sql        ← R1
apps/api/tests/test_retrieval.py         ← R1
apps/api/tests/test_chat_api.py          ← R1
```

### Backend — R2 (Guardrail & QA)

```
apps/api/app/modules/guardrails/         ← TAMAMI R2
apps/api/app/modules/assessment/socratic.py   ← R2 (state machine)
apps/api/tests/test_guardrails.py        ← R2
apps/api/tests/test_socratic.py          ← R2
supabase/tests/                          ← R2 (RLS canlılık kanıtı, T051 dahil)
evaluation/injection/                    ← R2 (T046a: vaka üretimi + cases.json)
```

> **T046 iki parçadır:** vaka üretimi (T046a) R2'de, koşu + raporlama (T046b,
> sonuçlar `evaluation/results/` altına) R5'tedir. İkisi de "T046 benim" demez.

### Backend — R3 (Assessment & Analytics)

```
apps/api/app/modules/assessment/question_gen.py   ← R3
apps/api/app/modules/assessment/grading.py        ← R3
apps/api/app/modules/mastery/            ← TAMAMI R3
apps/api/app/api/questions.py            ← R3
apps/api/app/api/exams.py                ← R3
apps/api/app/api/analytics.py            ← R3
apps/api/app/models/assessment.py        ← R3
supabase/migrations/0004_assessment.sql  ← R3
apps/api/tests/test_assessment.py        ← R3
apps/api/tests/test_mastery.py           ← R3
```

### Deploy ve altyapı — R1 (R4 ile ortak provalar)

```
apps/api/Dockerfile                      ← R1 (T048)
apps/api/app/api/internal.py             ← R1 (T049 — YENİ)
apps/api/scripts/                        ← R1 (T053)
.github/workflows/                       ← R1 (ci.yml + T052 keepalive)
```

> Faz G dağılımı: T048-T050, T052-T053 → R1 · T051 (prod RLS kanıtı) → R2 ·
> T054-T055 (yedek/restore + cold-start provası) → R1+R4 birlikte.

### Frontend — R4

```
apps/web/                                ← TAMAMI R4
supabase/migrations/0002_supabase_auth_bridge.sql  ← R4 (Supabase Auth geçişiyle birlikte)
```

### Ölçüm ve belgeler — R5

```
evaluation/gold_set/                     ← R5
evaluation/evaluate.py                   ← R5
evaluation/faithfulness/                 ← R5
sample_data/                             ← R5
docs/test-report.md                      ← R5
docs/instructor-guide.md                 ← R5
docs/student-guide.md                    ← R5
docs/runbook.md                          ← R5 (R2 güvenlik bölümünü verir)
```

### Kimse dokunmaz (dondurulmuş)

```
supabase/migrations/0001_core_schema.sql ← DEĞİŞTİRİLMEZ. Şema değişikliği yeni migration'la.
apps/api/app/core/security.py            ← Auth mantığı; değişecekse Murat onaylar
apps/api/app/api/deps.py                 ← Yetkilendirme bağımlılıkları; aynı kural
.specify/memory/constitution.md          ← Anayasa; SemVer + takım onayı gerekir
DESIGN.md                                ← Yalnız R4 + Murat
PLAN.md / ARCHITECTURE.md                ← Yalnız Murat
```

---

## 3. Sıcak dosyalar — çakışma buradan çıkar

Bu dosyalara **birden fazla rol** dokunmak zorunda. Kural: **ekleme yap, düzenleme yapma.**
Kendi bölümüne ekle, başkasının satırına dokunma. Çakışma çıkarsa `git pull --rebase`
yapıp kendi satırını yeniden ekle — asla `--ours`/`--theirs` ile toptan çözme.

| Dosya | Kim ekler | Protokol |
|---|---|---|
| `apps/api/app/core/config.py` | Herkes | Kendi bölüm yorumunun (`# --- Retrieval ---`) altına ekle. Var olan alanı silme. |
| `apps/api/app/main.py` | Router ekleyen herkes | Yalnız `include_router` satırı + import. Tek satırlık değişiklik. |
| `apps/api/pyproject.toml` | Bağımlılık ekleyen | Alfabetik sıraya değil, listenin sonuna ekle; sürümü sabitle. |
| `specs/.../contracts/openapi.json` | Uç ekleyen herkes | **Elle düzenleme.** Yeniden export et (aşağıdaki komut) ve aynı commit'te gönder. |
| `apps/web/lib/types.ts` | R4 | Backend tip değişikliğini R4'e bildir, sen düzenleme. |
| `specs/.../tasks.md` | Herkes | Yalnız kendi görevinin `[ ]` → `[x]` işareti + tarihli DONE notu. |
| `apps/api/tests/conftest.py` | Yeni tablo ekleyen | Yalnız kendi tablo adını TRUNCATE listesine EKLE; başka satır değiştirme. |
| `.env.example` | Yeni ayar ekleyen | Yalnız kendi anahtarını BOŞ değerle ekle; gerçek değer asla. |

**OpenAPI yeniden export:**

```bash
cd apps/api && .venv/bin/python -c "
import json, os
os.environ.setdefault('DEV_AUTH_ENABLED','true')
from app.main import create_app
spec = create_app().openapi()
open('../../specs/001-course-assistant-mvp/contracts/openapi.json','w').write(
    json.dumps(spec, ensure_ascii=False, indent=2))
print('güncellendi:', len(spec['paths']), 'yol')
"
```

---

## 4. Faz sırası ve kim kimi bekler

```
Faz A (R1)  ─────────────┐
                          ├──> Faz C (R1 backend + R4 web) ──> Faz D ──> Faz E
Faz B (R1 üretim,        │                                    (R2+R3+R4)  (R3+R4)
       R2 guardrail) ────┘

Faz F (R5) ── A/B/C bittikçe ölçer, gold set H1'den beri birikir (paralel)
Faz G (R1+R4; T051 R2) ── C'den sonra deploy; T052-T055 dondurma sonrası
Faz H (R5) ── F'nin çıktısıyla rapor; kılavuzlar UI son halini alınca
```

**Kritik bağımlılıklar (bunlar gecikirse takım durur):**

1. **T006 (R1, retrieval servisi)** — B, C, D, F'nin tamamı buna bağlı. İlk bitecek iş.
2. **T010 (R1, cevap şeması)** — R2'nin guardrail'i ve R4'ün tipleri bu şemayı bekliyor.
   R1 bunu yazar yazmaz gruba **"şema hazır"** mesajı atar.
3. **T024 (R3, assessment migration)** — R3'ün kendi işlerinin ve R4'ün sınav ekranının önü.
4. **T041 (R5, gold set)** — hemen başlar, günde 5-8 soru birikir. Beklemez.

---

## 5. Git akışı

```bash
# Her görev kendi branch'inde
git checkout main && git pull
git checkout -b feat/T003-dense-retrieval

# ... çalış ...

git add <yalnız kendi dosyaların>
git commit -m "feat(retrieval): add pgvector dense search with course isolation"
git push -u origin feat/T003-dense-retrieval
# GitHub'da PR aç, en az 1 review iste
```

**Kurallar:**

- **Görev = commit.** Bir görev bitmeden başka göreve geçme; her görev kendi PR'ıyla kapanır.
- **Commit mesajı İngilizce**, conventional commit (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
  Gövdede "ne" değil **"neden"** yaz.
- **`Co-Authored-By` satırı ASLA eklenmez.** AI asistanı kullansan bile commit yalnız senin
  adına gider. (Anayasa IX)
- **`main`'e doğrudan push yok.** Branch + PR + review.
- **`.env` commit edilmez.** Yalnız `.env.example` güncellenir.
- **Repo `~/code/` altında.** Masaüstü/Belgeler iCloud'a senkronlanır, Python projelerini bozar.

**PR açmadan önce (her seferinde):**

```bash
cd apps/api
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

Üçü de yeşil değilse PR açma.

---

## 6. Anayasa — hepimiz için bağlayıcı 10 kural

Tam metin: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md).
En sık ihlal edilen dördü:

1. **Kaynak yoksa cevap yok.** Öğrenciye giden hiçbir akademik cevap, retrieval'dan gelmemiş
   bir kaynağa dayanamaz. Atıf `chunk_id` küme kontrolünden geçer.
2. **course_id istemciden gelen bir yetki değildir.** Her istekte üyelik sunucuda doğrulanır.
   Yeni bir uç yazıyorsan `CourseMemberDep` / `CourseInstructorDep` kullan.
3. **Ölçmeden iddia etme.** "Hızlandı", "iyileşti" demeden önce ölç. Rapora yazılacak her
   sayı gerçekten koşulmuş bir ölçümden gelir.
4. **Doğrulama bitmeden "bitti" yok.** Test yeşil + lint temiz + davranış gerçekten
   gözlenmiş (tarayıcıda veya gerçek API çağrısıyla) olmadan görev kapanmaz.

---

## 7. İletişim

**Kanal:** WhatsApp proje grubu ("DOU-Synapse"). Acil/engelleyici durumda Murat'a DM.
**Toplantı:** Perşembe 20:00 (hoca toplantısı) + gerekirse takım içi kısa çağrı.

| Kişi | Roller | Sorumluluk özeti |
|---|---|---|
| Eren | R1 + R2 | Retrieval, LLM, guardrail zinciri, Sokratik motor |
| Metehan | R3 + R5 | Sınav/soru motoru, mastery, gold set, ölçüm, kılavuzlar |
| Muratcan | R4 + lead | Frontend, PR review, sıcak dosya hakemliği, deploy provaları |

- **Günlük:** kısa durum mesajı — dün ne bitti, bugün ne, engel var mı.
- **Engellendiysen 30 dakika kuralı:** 30 dakikadan fazla takılırsan gruba yaz. Tek başına
  saat harcama.
- **Bir bağımlılığı bitirdiğinde haber ver.** Özellikle T006, T010, T024 — bunları bekleyen
  insanlar var.
- **Kapsam değişikliği tek başına yapılmaz.** "Şunu da ekleyeyim" diye düşündüğünde önce
  gruba sor; PLAN'da kesilmiş bir şeyi geri getiriyor olabilirsin.

---

## 8. Yapay zekâ asistanı kullanımı

Her rol için hazır başlangıç promptu var: [`AI_ASISTAN_BASLANGIC.md`](AI_ASISTAN_BASLANGIC.md).
Yeni bir sohbet açıp o dosyayı yapıştır, rolünü yaz, sonra kendi brief'inle devam et.

**AI'ya bırakılmayacak işler** (insan gözüyle kontrol edilmeli):

- RLS politikaları ve migration'lar
- `course_id` filtreleri ve yetkilendirme kodu
- Gold set cevapları (doğru kaynak eşlemesi)
- API anahtarı / secret kullanımı
- Rapora yazılacak metrikler

**AI'ya asla verilmeyecek:** gerçek `.env` içeriği, LLM API anahtarları, Supabase
service-role anahtarı, gerçek öğrenci verisi.
