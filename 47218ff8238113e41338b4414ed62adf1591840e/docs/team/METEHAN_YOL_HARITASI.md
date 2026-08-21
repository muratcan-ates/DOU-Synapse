# Metehan — yol haritası ve kalan işler

> Rol: **R3 (Assessment)** + **R5 (Data & Eval)** · Hazırlayan: Muratcan (lead)
> Durum tarihi: **7 Ağustos 2026, Cuma = G4** · Teslim: **24 Ağustos, G15**
> Kaynaklar: `specs/001-course-assistant-mvp/tasks.md`, `docs/team/03_ASSESSMENT_BRIEF.md`,
> `docs/team/05_DATA_EVAL_BRIEF.md`, `PLAN.md`, `docs/team/PR_INCELEME_2026-08-06.md`

---

## 1. Nerede duruyoruz

Üç PR'ın da incelemesi bitti ve **hepsi `main`'de**. Uzakta artık yalnız `main` var,
dallar silindi.

| PR | Görev | Durum |
|---|---|---|
| `feat/T024-assessment-migration` | T024 + T025 + T030'un topics parçası | ✅ merge, düzeltmeler dahil |
| `feat/T036-mastery-service` | T036 + T039 | ✅ merge |
| `feat/T002-sample-data` | T002 | ✅ merge, cevap anahtarı düzeltilmiş |

`main` sağlık durumu: **92 test yeşil**, ruff temiz, `rls_isolation.sql` 8 PASS / 0 FAIL,
mypy yalnız önceden var olan 2 hata (`parsers.py:63`, senin dosyan değil).

**İnceleme sonucu kısa:** üç kalem çıktı, üçünü de aynı gün düzelttin, üçü de
doğrulandı. Önerdiğim ama zorunlu tutmadığım `exam_sessions_self_update` kalemini de
yapmışsın. Detay: [`PR_INCELEME_2026-08-06.md`](PR_INCELEME_2026-08-06.md).

### Takvime göre nerede?

R3 brief'i (`03_ASSESSMENT_BRIEF.md` §6) T024+T025+topics ucunu **G7'ye** koymuştu;
sen G3'te bitirdin — kendi hattında **4 gün öndesin**. R5 hattında da G3 çıktısı
(T002) zamanında teslim edildi.

**Ama:** kalan işlerinin çoğu Faz C'ye (gerçek retrieval + LLM) bağımlı ve Faz C
henüz başlamadı. Öndeliğin, ancak §3'teki "bloksuz iş" listesini çalıştırırsan
işe yarar.

---

## 2. Neyin bitti, neyin açık

### Bitti ✅

| Görev | Ne |
|---|---|
| T002 | `sample_data/isletim-sistemleri/` — 5 md + 5 pdf + 1 pptx + 2 kod dosyası |
| T024 | `supabase/migrations/0004_assessment.sql` — 5 tablo + 15 RLS politikası |
| T025 | `apps/api/app/models/assessment.py` |
| T030 (kısmi) | `POST/GET /courses/{id}/topics` + şemalar + testler |
| T036 | `apps/api/app/modules/mastery/service.py` — EWMA |
| T039 | `apps/api/tests/test_mastery.py` |

### Açık — R3 (Assessment)

| Görev | Dosya | Bağımlılık |
|---|---|---|
| T026 | `modules/assessment/socratic.py` | 🔴 Faz C (chat + LLM) |
| T027 | `api/chat.py` entegrasyonu | 🔴 Faz C · **dosya R1'in** |
| T028 | `tests/test_socratic.py` | 🔴 T026 |
| T029 | `modules/assessment/question_gen.py` | 🔴 T008 (LiteLLM) + retrieval |
| T030 (kalan) | `api/questions.py` — soru listeleme/onay/red | 🟡 **kısmen bloksuz**, §3'e bak |
| T031 | `modules/assessment/grading.py` | 🟡 **MCQ kısmı bloksuz**, §3'e bak |
| T032 | `api/exams.py` | 🟡 **iskelet bloksuz**, §3'e bak |
| T033 | `tests/test_assessment.py` — 8 vaka | 🟡 T030-T032 ile birlikte |
| T034 | `apps/web/.../exam/page.tsx` | 🔴 T032 · **dosya R4'ün (bende)** |
| T035 | `apps/web/components/socratic-ladder.tsx` | 🔴 T027 · **dosya R4'ün (bende)** |

### Açık — R5 (Data & Eval)

| Görev | Dosya | Bağımlılık |
|---|---|---|
| **T041** | `evaluation/gold_set/{calibration,holdout}.json` | 🟢 **BLOKSUZ — bugün başlıyor** |
| T042 | `evaluation/evaluate.py` | 🔴 T019 (chat API) · iskeleti G9'da |
| T043 | Evidence eşiği kalibrasyonu | 🔴 T042 |
| T044 | Baseline vs hybrid koşusu | 🔴 T042 + T043 |
| T045 | Embedding A/B (e5 vs bge-m3) | 🔴 T042 |
| T046 | Injection + sızıntı koşusu | 🔴 T042 · R2 ile ortak |
| T047 | Faithfulness örneklemi | 🔴 T042 |

### Açık — E fazı (Mastery + analitik)

| Görev | Dosya | Bağımlılık |
|---|---|---|
| T037 | mastery entegrasyonu (`exams.py` + `chat.py`) | 🔴 T032 · **`chat.py` kısmı R1'e devredilecek** |
| T038 | `api/analytics.py` | 🟡 **iskelet bloksuz** |
| T040 | `apps/web/.../analytics/page.tsx` | 🔴 T038 · **dosya R4'ün (bende)** |

---

## 3. BUGÜN (G4, Cum 7 Ağu) — tek öncelik: T041-a

`05_DATA_EVAL_BRIEF.md:724` → **"G4 | Cum 7 Ağu | T041-a kalibrasyon seti (~15) |
`calibration.json`"**. Repoda `evaluation/` dizini henüz yok.

**Branch:** `feat/T041-calibration-set`

**Kapsam — 15 soru:**

| Kategori | Adet |
|---|---|
| `direct` | 6 |
| `multi_chunk` | 3 |
| `out_of_scope` | 3 |
| `technical_term` | 3 |

**Dosya:** `evaluation/gold_set/calibration.json` · format `05_DATA_EVAL_BRIEF.md:217`

```json
{
  "set": "calibration",
  "version": "1.0",
  "material": "sample_data/isletim-sistemleri v1",
  "items": [
    {
      "id": "C-001",
      "question": "Round-robin zamanlamada quantum süresi çok küçük seçilirse ne olur?",
      "category": "direct",
      "expected_sources": [
        { "file_name": "02-cpu-scheduling.pdf", "page_number": 7 }
      ],
      "expected_chunk_ids": [],
      "expected_behavior": "answered",
      "notes": "quantum küçüklüğü ↔ context switch maliyeti"
    }
  ]
}
```

**Kritik kural (koordinasyon §8):** soruları asistan taslak üretebilir, ama
`expected_sources` eşlemesini **materyali açıp sen doğrulayacaksın**. Gold set kaynak
eşlemesi AI'ya bırakılmaz — çünkü bu set, sistemin doğruluğunu ölçen cetvel; cetvel
yanlışsa ölçüm de yanlış.

**Materyal artık `main`'de**, önün açık. Sayfa numaralarını gerçek PDF'lerden al —
`.md` kaynaklarından değil, çünkü ingest edilen PDF.

**Dikkat:** `04-synchronization` dosyasındaki `bug_hunt` cevap anahtarı dün düzeltildi.
`code_review` kategorisinde soru yazarken **güncel metni** kullan: bu koddaki hatanın
tek sonucu **deadlock**'tur; taşma/taşınma değil.

---

## 4. Faz C beklerken yapılabilecek işler

Kalan R3 işlerinin çoğu "LLM lazım" diye etiketli ama **hepsi değil**. Aşağıdakiler
bugün/hafta sonu yazılabilir ve Faz C indiğinde tak-çalıştır olur:

### 4.1 T030'un LLM gerektirmeyen yarısı 🟢

`api/questions.py`'ye soru **listeleme / onaylama / reddetme** uçları. Bunlar
`questions` tablosu üzerinde çalışır, üretimle (T029) ilgisi yok:

- `GET /courses/{id}/questions` — eğitmen hepsini, öğrenci yalnız `approved` görür
- `POST /courses/{id}/questions/{qid}/approve` → `status='approved'`, `reviewed_by`,
  `reviewed_at`
- `POST /courses/{id}/questions/{qid}/reject` → `status='rejected'`

`questions_reviewed_consistency` CHECK'i `reviewed_by`/`reviewed_at` alanlarını
zorunlu tutuyor, onu ihmal etme. Testleri şimdi yazılabilir (soruları fixture'da
elle INSERT ederek).

### 4.2 T031'in MCQ yarısı 🟢

MCQ puanlama **deterministik** — LLM gerekmiyor. `payload.answer_key` ile karşılaştır,
`distractor_sources` üzerinden "neden yanlış?" eşlemesini kur. Açık uçlu rubrik
değerlendirmesi (LLM'li kısım) T008 gelince eklenir.

### 4.3 T032'nin iskeleti 🟡

Oturum açma/kapama, süre hesabı (`expires_at`, istemci saatine güvenilmez), tek
deneme kuralı, boş havuzda 409 — hepsi şema üzerinde çalışır. Soru seçimi için
havuzda `approved` soru gerekiyor; testte fixture ile üretilebilir.

### 4.4 T038'in iskeleti 🟡

`api/analytics.py` — öğrenci mastery listesi ve eğitmen özeti `mastery` tablosundan
okunur. Tablo dolu değil ama uç ve testleri yazılabilir.

### 4.5 İnceleme takip görevleri — §5

---

## 5. İncelemeden gelen takip görevleri

Bunlar merge'i bloklamadı ama kapatılmaları gereken kalemler. **Şiddet sırasına göre:**

### 5.1 `0004`'ün 15 RLS politikasının otomatik kanıtı yok `[major]`

Ölçüm: `questions_read`'den `AND status = 'approved'` düşürüldüğünde **92 test yeşil**,
`rls_isolation.sql` 8/8 PASS, CI'daki `grep -q FAIL` kapısı geçiyor — aynı anda psql'de
öğrenci taslak soruyu görüyor. Ölçme katmanının **tüm** politikaları `USING(true)`
yapılsa bile CI tamamen yeşil.

Politikalar doğru çalışıyor; eksik olan **kanıt**. Projenin tezi tam olarak buydu:
"iki katmanlı izolasyon, **kanıtlı**".

Ayrıca dünkü üç RLS düzeltmesinden **yalnız biri** testle korunuyor:

| Düzeltme | Mutasyon sonucu |
|---|---|
| `mastery_self_insert` | 1 failed ✅ korunuyor |
| `answers_self_insert` | 92 passed ❌ testsiz |
| `exam_sessions_self_update` | 92 passed ❌ testsiz |

**İş:** `rls_isolation.sql` desenine uygun, ölçme tablolarını sınayan bir blok.
En az şunlar: öğrenci `draft` soruyu görmez / eğitmen görür; öğrenci başkasının
`exam_sessions` satırını görmez; `answers`'a sahte `course_id` yazılamaz; oturum
yabancı derse taşınamaz; mastery üye olunmayan derse yazılamaz.

**⚠️ Sahiplik:** `supabase/tests/` **R2'nin (Eren) dosyası** — çapraz düzenleme yok.
İki seçenek: (a) bloğu yazıp Eren'e ver, (b) ayrı `supabase/tests/rls_assessment.sql`
aç ve `ci.yml`'ye ekle. **(b)'yi tercih et**, Eren'i beklemez.

**Ucuz ek:** `test_mastery.py`'deki entegrasyon testi eğitmen personasıyla koşuyor
(Ayşe hem eğitmen hem satır sahibi), mastery politikalarının **öğrenci kolunu hiç
sınamıyor**. Personayı öğrenciye çevir.

### 5.2 `source_chunk_id ON DELETE RESTRICT` belge silmeyi kilitliyor `[major]` — **T029'dan ÖNCE karar**

`DELETE /courses/{id}/documents/{doc_id}` `main`'de **zaten canlı**. Belge silme
chunk'ları CASCADE ile düşürüyor; o chunk'tan üretilmiş soru varsa RESTRICT patlıyor
ve uç IntegrityError yakalamadığı için kullanıcı **409 yerine 500** görüyor.

Bugün ulaşılamaz (soru yazan yol yok) ama T029 iner inmez patlar. Kötüsü:
`test_silinen_belgenin_chunklari_da_gider` 204 bekleyerek yeşil geçiyor, yani T029'u
yazarken `documents.py`'ye bakmak için sebebin olmayacak.

İki yol: (a) `SET NULL` + nullable yap, kaynak bilgisini `payload`'a kopyalanan
alıntıyla telafi et; (b) `delete_document`'te açık 409 `ConflictError` + `questions`'a
eğitmen DELETE politikası.

### 5.3 Öğrenci kendi puanını yazabiliyor `[major]` — **T032/T037'den ÖNCE karar**

`exam_sessions_self_update` ve `mastery_self_update` **sütun kısıtsız**: öğrenci kendi
`score`'unu, `expires_at`'ini (sınav süresi uzatma) ve `mastery.score`'unu doğrudan
yazabiliyor. Dünkü düzeltme `course_id` taşımayı kapattı ama **sütun bazlı yazma
serbest**.

RLS yapısal olarak sütun kısıtı veremez. Çözüm: kolon bazlı GRANT, BEFORE UPDATE
trigger, ya da puanlama yazımını `SECURITY DEFINER` fonksiyona (`app.finish_exam()`)
veya `dou_worker` rolüne taşımak.

### 5.4 `answers`'ta UPDATE politikası yok `[major]` — **T031'den ÖNCE karar**

Puanlama ve ipucu sayacı cevap satırına yazmak zorunda; şu an bu yol tanımsız.

### 5.5 Küçük kalemler `[minor/nit]`

- **`Settings.mastery_alpha` ölü ayar** — `config.py`'ye eklendi ama
  `mastery/service.py` onu hiç okumuyor; kendi `DEFAULT_ALPHA` sabitini kullanıyor.
  Docstring ise okuduğunu söylüyor. İkisinden biri düzeltilsin.
- **`mastery.updated_at` hiç güncellenmiyor** — kalıcı olarak ilk cevabın zamanını
  gösteriyor. `record_answer` içinde `func.now()` ata.
- **`questions.reviewed_by ON DELETE SET NULL` ile `questions_reviewed_consistency`
  çelişiyor** — inceleyen eğitmenin profili silinirse CHECK ihlali doğar.
- **`questions`/`exam_sessions` için DELETE politikası yok** — eğitmen hatalı üretilmiş
  soruyu silemez.
- **`_hint_multiplier` fail-closed dalı, `raw_score` clamp'i, `previous_answer_count == 0`
  kolu testsiz** — üçü de kaldırılsa testler yeşil kalıyor.
- **`README.md` içerik tablosu 13 dosyanın 8'ini listeliyor** — 5 `.md` kaynağı geçmiyor.
  Ayrıca beş belge korpusta iki kez var (`.md` + `.pdf` ikizleri, ~%98,5 aynı) —
  retrieval'da yinelenen sonuç riski. Bilinçli karar mı, README'de belirt.
- **Demo PDF'i 2 sayfa** — T002 kriteri 5-10 sayfa diyor (`05-deadlock-demo.pdf`).
- **PPTX metadata'sı üçüncü şahsa ait** — `last_modified_by = 'Steve Canny'`,
  `created = 2013-01-27` (python-pptx varsayılan şablonu). İçerik kendi üretimin ama
  metadata telif beyanıyla çelişkili görünüyor, temizle.
- **`tasks.md` işaretleme protokolü** — T024 ve T036 `[x]` ama tarihli DONE notu yok
  (koordinasyon §139 istiyor). T030 fiilen kısmen yapıldı ama `[ ]` kaldı.

---

## 6. Gün gün yol haritası

`05_DATA_EVAL_BRIEF.md` takvimi + R3 brief'i + inceleme takipleri birleştirilmiş hâli.
🟢 bloksuz · 🟡 kısmen bloklu · 🔴 Faz C'ye bağımlı

| Gün | Tarih | İş | Gün sonu çıktısı |
|---|---|---|---|
| **G4** | **Cum 7 Ağu** | 🟢 **T041-a kalibrasyon seti (15 soru)** | `calibration.json` |
| — | Cmt-Paz | Buffer · isteğe bağlı: §5.1 RLS test bloğu | `rls_assessment.sql` |
| G5 | Pzt 10 Ağu | 🟢 Gold set 5-8 (`direct`) · 🟡 §4.1 T030 onay/red uçları | holdout ~8 |
| G6 | Sal 11 Ağu | 🟢 Gold set 5-8 · 🟡 §4.2 MCQ puanlama | holdout ~15 |
| G7 | Çar 12 Ağu | 🟢 Gold set 5-8 (`multi_chunk`) · 🔴 T029 (LLM inerse) | holdout ~23 |
| G8 | Per 13 Ağu | 🟢 Gold set 5-8 (`technical_term`) · 🔴 T029 + T030 kalanı | holdout ~30 · soru bankası |
| G9 | Cum 14 Ağu | 🟢 Gold set 5-8 · 🔴 T031 + T032 + T033 · **`evaluate.py` iskeleti** | holdout ~38 · sınav döngüsü |
| — | Cmt-Paz | Buffer | — |
| **G10** | **Pzt 17 Ağu** | 🔴 T037 + T038 · gold set kapanış · harness `--layer retrieval` | holdout ≥50 · **ÖZELLİK DONDURMA** |
| G11 | Sal 18 Ağu | T041 kapanışı (kategori denetimi, eğitmene sunum) + **T045 embedding A/B** | Ayrık, etiketli set |
| G12 | Çar 19 Ağu | **T043** kalibrasyon → **T044** baseline vs hybrid (gece koşusu) → **T047** faithfulness | Ölçülmüş kalite verisi |
| G13 | Per 20 Ağu | **T046** injection + sızıntı koşusu (R2 ile ortak) | Negatif test sonuçları |
| G14 | Cum 21 Ağu | **T056** `docs/test-report.md` | Teslim paketi |
| — | Cmt-Paz | Buffer + offline demo provası | — |
| G15 | Pzt 24 Ağu | T060 teslim kapanışı | Release |

**Yük uyarısı** (`PLAN.md` §4): **G11-G14 senin en yoğun dönemin.** T042'nin
(`evaluate.py`) iskeletini G9'a kadar yazmazsan G12'deki gece koşusu yetişmez —
brief bunu açıkça uyarıyor: *"G12'ye bırakma."*

---

## 7. Takvimin en büyük riski — sende değil

Kalan R3/R5 işlerinin çoğu **Faz C'ye** (gerçek retrieval + LLM) bağımlı. Faz C ise
**Faz B'ye** ve **T006'ya** (hybrid retrieval, R1/R2 = Eren) bağımlı.

Bugün itibarıyla: repoda Eren'den **tek commit veya dal yok**,
`apps/api/app/modules/retrieval/` hâlâ boş, ve Eren'in repo erişimi henüz açılmadı.
`HANDOFF.md` §9'un kendi ifadesiyle: **"T006 herkesi bloklar — takımın önceliği."**

Bu senin kontrolünde değil ama planını etkiliyor. Bu yüzden §4'teki bloksuz işleri
öne çek: Faz C indiğinde tak-çalıştır olacak parçaları önceden yaz.

Erişim meselesi bende, takip ediyorum.

---

## 8. Protokol hatırlatmaları

**Lokal veritabanını yeniden kur.** `0004_assessment.sql` dün `main`'e girdikten
sonra **yerinde** düzeltildi. Eski sürümü lokaline uyguladıysan düzeltmeyi almazsın —
`psql -f` bir kez çalışır:

```bash
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
dropdb dou_synapse && createdb dou_synapse
psql -d dou_synapse -f supabase/migrations/0001_core_schema.sql
psql -d dou_synapse -f supabase/migrations/0004_assessment.sql
psql -d dou_synapse -f supabase/local_dev_setup.sql
psql -d dou_synapse -f supabase/seed_demo.sql
```

**Bundan sonra:** `main`'e girmiş bir migration bir daha yerinde değiştirilmez,
`0005_*.sql` açılır. Dünkü istisna, `0004` henüz hiçbir kalıcı veritabanına
uygulanmadığı için verildi.

**Yeni uç eklediğin her commit'te OpenAPI'yi yeniden export et** — elle düzenleme yok
(`tasks.md:225`, koordinasyon §137):

```bash
cd apps/api && uv run python -c "
import json, os
os.environ.setdefault('DEV_AUTH_ENABLED','true')
from app.main import create_app
spec = create_app().openapi()
open('../../specs/001-course-assistant-mvp/contracts/openapi.json','w').write(
    json.dumps(spec, ensure_ascii=False, indent=2))
print('güncellendi:', len(spec['paths']), 'yol')
"
```

**Sıcak dosyalar** — koordinasyon §135-139:

| Dosya | Kural |
|---|---|
| `app/main.py` | yalnız import + tek `include_router` satırı |
| `app/core/config.py` | kendi `# --- Assessment ---` başlığın altına; var olanı silme/sıralama değiştirme |
| `contracts/openapi.json` | elle düzenleme yok, export et, aynı commit'te gönder |
| `specs/.../tasks.md` | yalnız kendi görevinin `[ ]` → `[x]` + **tarihli DONE notu** |
| `apps/web/lib/types.ts` | R4'ün (bende) — sen düzenleme, bana bildir |
| `supabase/tests/` | R2'nin (Eren) — çapraz düzenleme yok, ayrı dosya aç |

**Görev = commit = PR.** PR #1 tek commit'te T024 + T025 + T030'un parçasını taşıyordu;
bir dahakine ayır — inceleme ve geri alma kolaylaşır.

**30 dakika kuralı:** bir hatada 30 dakikadan fazla takılırsan gruba yaz.

---

## 9. Bir işi "bitti" saymadan önce

- [ ] `uv run pytest -q` yeşil
- [ ] `uv run ruff check .` ve `ruff format --check .` temiz
- [ ] Yeni uç varsa `openapi.json` yeniden export edildi
- [ ] Yeni RLS politikası varsa **kanıtı da** var: politikayı bilerek boz, testin
      kırmızı yandığını gör, geri al (Anayasa VIII — gözlenmeden bitmedi)
- [ ] `tasks.md`'de kendi satırın `[x]` + tarihli DONE notu
- [ ] Dosya sahipliği matrisine uyuldu, çapraz düzenleme yok
- [ ] Commit gövdesi neyi **neden** yaptığını anlatıyor
