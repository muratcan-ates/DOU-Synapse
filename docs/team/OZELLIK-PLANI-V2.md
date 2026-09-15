# Özellik Planı v2 — beş öğrenci özelliği

**Yazım:** 15 Eylül 2026, sunum arifesi · **Uygulayan:** Opus geliştirme oturumu ·
**Denetleyen:** bu planı yazan oturum (Fable) · **Karar sahibi:** Muratcan Ateş

Bu belge bir **devir belgesidir**: uygulayan oturum bu sohbeti görmez. Her özellik için
dosya yolları, uçlar, şemalar, dokunulmayacak yerler, kapılar ve denetimde aranacak kabul
kriterleri buradadır. "Yeni dosya:" ile işaretlenen yollar henüz yoktur.

---

## 0. Uygulayan oturum için kullanım

### 0.1 Önce oku, bu sırayla

1. `AGENTS.md` — pazarlık edilmeyen 16 kural, kapı komutları, dossier biçimi.
2. `docs/team/codex/CODEX-RUNBOOK.md` §0–§4.
3. `DESIGN.md` — tek tasarım otoritesi; ikon kütüphanesi yok; açık/koyu temada AA.
4. `ARCHITECTURE.md` §5 (sorgu hattı ve guardrail zinciri) ve §6 (güvenlik).
5. Bu belge.

### 0.2 Bu plana özgü ek kurallar (AGENTS.md'nin üstüne)

| # | Kural | Neden |
|---|---|---|
| P1 | **`PROMPT_REVISION` sabitine dokunulmaz** (`apps/api/app/api/chat_cache.py:32`). Yeni istem = `apps/api/app/modules/generation/prompts.py`'ye **ayrı** sabit | Demo, `answer_cache`'teki 16 sahne sorusuna dayanıyor (Plan C). Revizyon değişirse önbellek boşalır, sahnede canlı çağrı olur |
| P2 | Yeni sistem istemi eklenirse SHA-256'sı `apps/api/app/modules/agent/token_precharge.py:40` `_KNOWN_SYSTEM_PROMPT_SHA256S` kümesine girer | Bilinmeyen istem kırmaz ama tavana (`:39`, 1024 jeton) çekilir; ön-şarj yanlış hesaplanır |
| P3 | Öğrenciye açılan **her** yeni çalışma yüzeyi `UnlockedCourseMemberDep` kullanır (`apps/api/app/api/deps.py:281`) | Aktif sınavda kartlar, kavram haritası ve özet notu da kilitlenir; yoksa sınav bütünlüğü delinir (ARCHITECTURE §6) |
| P4 | Yeni LLM üretimi guardrail zincirinden geçer; sıra sabit: `generation → citation → leakage → sanitize` | Zincir dışı üretim yolu açılmaz |
| P5 | Öğrenciye giden soru içeriği **yalnız `approved`** durumundan gelir | Ürün ilkesi 2: öğretmen onayı olmadan soru yayınlanmaz |
| P6 | **Sunumdan (16 Eylül) önce main'e birleşme yok.** Her özellik kendi dalında, taslak PR'da | Demo yığını dondurulmuş sayılır |
| P7 | Göç ve dossier numarası şerit aralığından; aralık bilinmiyorsa `ENGEL:` yaz, varsayma | AGENTS.md 6 ve 14; 101/151 soy çakışması bu yüzden oldu |
| P8 | Kaynak metnini çivileyen testler var (`readFileSync` ile sayfa kaynağını okuyanlar: `apps/web/lib/question-page-contracts.test.ts`, `members.test.ts`, `course-assistant*.test.ts`). Dokunduğun sayfayı çivileyen test varsa **önce onu oku** | Sessizce kırmızı yanar, sebebini bulmak zaman alır |

### 0.3 Dal, commit, PR

- Dal adı: `feat/f<N>-<kısa-ad>` (ör. `feat/f4-review-cards`). Taban: `origin/main` güncel başı.
- Commit: conventional başlık İngilizce türde (`feat(api): …`), gövde Türkçe, **neden** yazılır. `Co-Authored-By` yok.
- PR: hedef `main`, taslak, başlık `[F<N>] <özellik>`; açıklamaya AGENTS.md'deki rapor şablonu.
- Her PR tek özellik. F1/F4/F5 birbirinden bağımsız; paralel dallarda çalışılabilir.

### 0.4 Kapılar — her commit öncesi

```bash
KOK="$(git rev-parse --show-toplevel)"
cd "$KOK/apps/api" && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app
TEST_DB_NAME="dou_feat" .venv/bin/python -m pytest -q
cd "$KOK/apps/web" && bun test lib/ && bunx tsc --noEmit && node scripts/contrast.mjs && bun run build
cd "$KOK" && node scripts/docs_check.mjs
python3 scripts/migration_check.py --allow-gap 0017 --allow-gap 0021 --allow-gap 0022 --allow-gap 0023 --allow-gap 0028
apps/api/.venv/bin/python scripts/workflow_policy_check.py
```

Taban (15 Eylül, `d574d50`): pytest **2159 geçti**, `bun test lib/` **648 geçti**, tsc rc=0,
build rc=0, docs_check ✓. Yeni test eklendiğinde `node scripts/docs_check.mjs --duzelt`
sayaçları ölçümden yazar; **elle sayı yazılmaz**.

### 0.5 Denetimde bakılacaklar (Fable'ın listesi — PR açıklamasında karşılığı olsun)

1. Her uç için: hangi `Dep` kullanıldı, `course_id` istemciden mi geliyor (gelmemeli), RLS testi var mı.
2. Aktif sınav kilidi: yeni yüzey `UnlockedCourseMemberDep` ile mi; `apps/api/tests/test_exam_lock.py`'ye vaka eklendi mi.
3. Öğrenci verisi başka öğrenciye sızıyor mu: iki öğrencili negatif test.
4. Yeni LLM istemi varsa: P1/P2 uygulandı mı, `guardrails/chain.py` sırası aynı mı, `PROMPT_REVISION` diff'te yok mu.
5. Dossier: sensitive yola dokunan commit aynı commit'te dossier + kanıt taşıyor mu; `artifacts[].sha256` gerçek mi.
6. Frontend: DESIGN.md dışı renk/ikon var mı, `useSubmit` kullanıldı mı, klavye ve `prefers-reduced-motion` gözetildi mi, 375px'te yatay taşma yok mu.
7. Kaynak metnini çivileyen testler güncellendi mi, gevşetildi mi (gevşetme kabul edilmez).
8. PR raporundaki her "geçti" bir komut çıktısına dayanıyor mu; koşulamayan `not-run` + neden yazılmış mı.

---

## 1. Fazlar, sıra, bağımlılıklar

| Faz | Zaman | Kapsam | Gerekçe |
|---|---|---|---|
| **0** | 15–16 Eylül, sunum ÖNCESİ | Hiçbir şey main'e girmez. En fazla F4-lite ve F5-lite bir dalda hazırlanır, **sunumda gösterilmez** | Demo yığını dondu; hoca çalışan sistemi görecek, yarım özelliği değil |
| **1** | 17–23 Eylül | F4-lite, F5-lite, F1-lite, F2 | LLM'siz, istemsiz, önbelleği etkilemeyen; var olan verinin yeni yüzü |
| **2** | 24 Eylül – 7 Ekim | F3 (analoji modu), F1-full, F5-full | Yeni istem + guardrail çalışması; dossier'li |
| **3** | Ekim | F4-full (`true_false` soru tipi) | Enum göçü + üretim + puanlama; insan kararı bekliyor (§5) |

Bağımlılık: F4-lite ve F5-lite → **öğrenme olayı** altyapısını paylaşır (§2.3), önce hangisi
yazılırsa olayı o ekler. F1-lite, F4/F5 olaylarını da özete katmak için onlardan **sonra**
bitirilmeli (başlayabilir, son bölümü bekler). F2 bağımsız. F3 bağımsız ama §2.1 protokolünü
ilk kullanan olur; protokolü o yazar.

---

## 2. Ortak altyapı kararları

### 2.1 Yeni istem ekleme protokolü (F3, F1-full, F5-full)

1. `apps/api/app/modules/generation/prompts.py`'ye yeni bir sabit (ör. `SIMPLIFY_SYSTEM_PROMPT`). Var olan sabitler değişmez.
2. Sabitin SHA-256'sı `token_precharge._KNOWN_SYSTEM_PROMPT_SHA256S`'e eklenir; jeton tavanı ölçülüp yazılır (fake sağlayıcı ile ölçülemez; gerçek sağlayıcı koşusu **not-run** ise tavan varsayılan kalır ve dossier'de öyle yazılır).
3. Üretim `Generator.generate` üzerinden; çıktı zincire girer (P4).
4. `PROMPT_REVISION` sabiti **değişmez** (P1). Yeni özelliğin kendi önbellek anahtarı varsa `CacheRevision`'a yeni bir alan olarak eklenir; var olan anahtarların hash'i değişmemeli — `apps/api/tests/test_answer_cache.py`'de "eski anahtar aynı kalır" testi yazılır.
5. Sensitive: `modules/generation/**` R2, `modules/guardrails/**` R3, `schemas/chat.py` R3 → dossier.

### 2.2 Kota

Öğrenci günlük jeton tavanı `apps/api/app/core/config.py` `course_agent_student_daily_hard_limit` (varsayılan 50 000; ürünün kendi tavanı, sağlayıcının değil). Yeni LLM özellikleri **aynı** tavandan düşer; ayrı kova açılmaz. Kota bittiğinde `agent_quota_exhausted` kodu döner; frontend bunu kalıcı hata olarak gösterir (`apps/web/lib/api.ts`, 429 kuralından önce).

### 2.3 Öğrenme olayı ekleme protokolü (F4, F5, F1)

~~`event_type` serbest metin, göç gerekmez~~ — **YANLIŞTI, 15 Eyl'de ölçüldü.** Serbest metin olan
yalnız SQLAlchemy modeli. Veritabanı üç yerde kısıtlıyor: `0027_learning_events.sql:58` tablo
`CHECK (event_type IN (...))` (6 değer), `:131` `app.record_learning_event` içindeki tür listesi ve
`:180-191` tür başına yapısal kurallar. **Yeni tür yeni göç ister** → numara K1 (160–169 bloğu
ayrıldı; göç numarası hâlâ açık). F4 bu yüzden olay yazmadan teslim edildi. Yeni tür eklemek için:

1. `apps/api/app/schemas/learning_events.py`'ye istek şeması (`CitationOpenedRequest` emsali: `extra="forbid"`).
2. `apps/api/app/modules/assessment/learning_events.py` `record_learning_event` ile kayıt; `get_learning_summary` yeni türü konu özetine katar.
3. Uç `apps/api/app/api/exams.py` `citation_opened` emsalinde (`@router.post` … `LearningEventReceipt`).
4. Test: `apps/api/tests/test_study_continuity.py` ve `test_learning_events*.py` emsalleri.

Yeni türler: `card_reviewed` (F4, gövde: `question_id`, `verdict: "knew" | "review"`), `concept_opened` (F5, gövde: `chunk_id`, `term`).

### 2.4 İndirme protokolü (F1, F5)

- Uç `GET /courses/{course_id}/…/export` `text/markdown; charset=utf-8` döner, `Content-Disposition: attachment; filename="…"`. PDF üretilmez (bağımlılık ister → `ENGEL: bağımlılık`); Markdown tarayıcıda da okunur.
- Yalnız isteyen kullanıcının kendi verisi. `UnlockedCourseMemberDep` (P3).
- Dosya adı ASCII (`calisma-ozeti-<kurs-kodu>-<YYYYAAGG>.md`); Türkçe karakter `Content-Disposition`'da sorun çıkarır.
- Günlüğe içerik yazılmaz; yalnız `request_id`, kurs, bayt sayısı (`docs/operations/logging-privacy.md`).
- Frontend: `<a href download>` değil, `api` üzerinden fetch + `Blob` — Bearer başlığı gerekiyor.

### 2.5 Frontend ortak kuralları

- Sayfa: `apps/web/app/courses/[courseId]/<segment>/page.tsx` + `layout.tsx` (yalnız metadata, `apps/web/lib/metadata.ts` şablonu). Next 16: rota/layout'a dokunmadan önce `node_modules/next/dist/docs` okunur.
- Yardımcı bileşenler `apps/web/components/<alan>/` altında (`components/exam/`, `components/blueprint/` emsali). `"use client"` başa yazılır.
- Gönderim: `apps/web/lib/use-submit.ts`. Eğitmen kapısı gerekiyorsa `apps/web/components/instructor-gate.tsx`.
- Öğrenci gezinmesine giriş: `apps/web/components/course-nav.tsx` sekmesi; mobilde 4 sekmede ulaşılabilirlik korunur (15 Eylül düzeltmesi).
- Kontrast `node scripts/contrast.mjs`; jeton renkleri DESIGN.md tablosundan.

---

## 3. Özellikler

### F1 — Çalışma özeti (indirilebilir ders notu)

**Hoca gereksinimi:** öğrencinin "neyi bilmiyorum" sorusuna materyale bağlı cevap; kişiselleştirme.

**Kullanıcı akışı (lite):** Öğrenci `/courses/{id}/study` → "Çalışma özetimi indir" → Markdown iner. İçerik sırasıyla: (1) son 30 günde çalışılan konular ve mastery düzeyi, (2) yanlış/kısmi cevaplanan sorular — her biri için soru kökü, öğrencinin cevabı, doğru cevap, **"neden yanlış" kaynak pasajı ve konumu**, (3) en çok açılan kaynaklar, (4) F4/F5 olaylarından "tekrar" işaretlenen kartlar ve açılan kavramlar, (5) öneri: en zayıf üç konu için ilgili kaynak pasajları. Hepsi var olan kayıttan; **model çağrısı yok**.

**Backend (lite):**
- Yeni dosya: `apps/api/app/modules/assessment/study_summary.py` — `build_study_summary(session, context, *, days=30) -> StudySummary` (saf veri) ve `render_markdown(summary) -> str`. Kaynaklar: `get_learning_summary` (mastery/konular), `Answer` + `Question` + `exam_feedback` projeksiyonu (`apps/api/app/api/exams.py` `_saved_feedback` — R3 dosya; **import edilir, kopyalanmaz**), `LearningEvent`.
- Uç: `apps/api/app/api/exams.py`'ye değil, yeni dosya `apps/api/app/api/study.py` (router `/courses/{course_id}/study`), `main.py`'ye kayıt (main.py R3 → dossier). `GET /study/summary` (JSON, ekranda önizleme) ve `GET /study/summary/export` (Markdown).
- Şema: yeni dosya `apps/api/app/schemas/study.py`.
- Dep: `UnlockedCourseMemberDep`. Eğitmen kendi verisini görebilir; başkasının verisi yok.

**Frontend (lite):** `/study` sayfası zaten var ama **ders üstü**: `apps/web/app/study/page.tsx` (kampüs birleşmesi; `courses/[courseId]/study` yok). Özet ders bazlı olduğundan sayfa ders seçtirir (öğrencinin üye olduğu dersler `useSession`'dan) ve seçili ders için "Çalışma özeti" kartı + indirme düğmesi gösterir; önizleme JSON'dan render (`components/study/summary-card.tsx` yeni dosya). Ders sayfasına (`courses/[courseId]/page.tsx`) da "Çalışma özetim" bağlantısı eklenir.

**Full (Faz 2):** Özetin başına LLM'in yazdığı 150–250 kelimelik "bu hafta nerede zorlandın" anlatısı. §2.1 protokolü; anlatı yalnız özetteki pasajlara atıf yapar, citation guardrail'den geçer; atıfsız cümle üretilirse anlatı bölümü düşer, özetin kalanı yine iner.

**Testler:** `apps/api/tests/test_study_summary.py` yeni dosya — boş geçmiş (yalnız başlık döner), yanlış cevaplı öğrenci (pasaj ve konum var), iki öğrenci (çapraz sızıntı yok), aktif sınav (kilit → `ExamLockedError`), Markdown çıktısında ham `chunk_id` yok. Web: `apps/web/lib/study-summary.test.ts` render yardımcıları.

**Sensitive/dossier:** `main.py` R3, `modules/assessment/**` R3 → dossier. `api/study.py` yeni; `.ai/policy.json`'a eklenmesi **önerilir** (öğrenci cevaplarını dışa yazıyor).

**Süre (tahmin):** lite 5–7 saat; full +4 saat.
**Riskler:** Markdown'a `answers.feedback` ham JSON sızması (test var); Türkçe dosya adı; büyük derste yavaş sorgu (30 gün sınırı ve `LIMIT`).
**Kabul:** iki öğrenci, biri yanlış cevaplı → indirilen dosyada yalnız kendi cevabı ve o cevabın pasajı; aktif sınavda 423/409 (mevcut `ExamLockedError` kodu neyse o).

---

### F2 — Marka ve logo tutarlılığı

**Mevcut durum (ölçüldü):** `apps/web/components/brand-mark.tsx` üniversite arması (`/brand/dogus-universitesi.svg`) + "DOU Synapse" yazısı (`BrandLockup`), `UniversitySignature`. `apps/web/app/icon.svg` var. **Ürünün kendi işareti yok**; Open Graph görseli yok; dışa aktarılan dosyalarda başlık yok.

**Kapsam:**
1. Ürün işareti: DESIGN.md'deki "altın sinaps ışıması" (satır 133) dilinde tek renkli SVG işaret; inline bileşen `components/brand-mark.tsx` içinde `ProductMark` — dış SVG dosyası değil (CSP ve tema uyumu için `currentColor`).
2. `BrandLockup`'ta arma + ürün işareti + metin düzeni; açık/koyu temada kontrast tablosundaki `--brand-on-ink` çiftleri.
3. `app/icon.svg` ve `app/apple-icon.png` uyumu; `app/opengraph-image` (Next 16 dosya konvansiyonu — önce `node_modules/next/dist/docs` oku).
4. Giriş, şifre sıfırlama ve KVKK sayfalarında imza; F1/F5 Markdown çıktılarının başına metin imzası ("DOU-Synapse · CourseGPT · <tarih>").

**Karar Murat'ta:** işaretin biçimi (sinaps düğüm-bağ mı, "S" harfi mi). Karar gelmeden 1. madde `ENGEL: ürün kararı`; 3–4. maddeler yapılabilir.

**Testler:** `node scripts/contrast.mjs` yeşil; `apps/web/lib/accessibility.test.ts` emsali gibi işaretin `aria-hidden` olduğu ve metin eşdeğerinin bulunduğu testi.
**Sensitive:** yok. **Süre:** 2–3 saat. **Kabul:** her rota tek marka düzeni; 375px'te taşma yok; koyu temada AA.

---

### F3 — "Anlamadım" → basitleştir, günlük hayattan örnekle

**Hoca gereksinimi:** öğrenci anlamadığında öğretmen gibi başka yoldan anlatma.

**Tasarım kararı:** Yeni **mod** değil, QA moduna bağlı bir **niyet**. `ChatMode` (`apps/api/app/contracts.py:140`: `qa/socratic/exam`) değişmez. `ChatRequest`'e `intent: Literal["default", "simplify"] = "default"` (`apps/api/app/schemas/chat.py`, R3). Sokratik modda `simplify` **reddedilir** (422): analoji anlatım demektir, `DIAGNOSE/NUDGE` kademesinde anlatım `leakage.exposition` dedektörünün tam da bloklamak için yazıldığı şeydir.

**Akış:** Öğrenci QA cevabının altında "Anlamadım — günlük hayattan örnekle" düğmesine basar → aynı `session_id`, aynı soru, `intent=simplify` → sunucu **aynı retrieval kümesini** kullanır (yeniden arama yok; önceki turun `citations` listesi `chunk_id` olarak istekle gelir, sunucu bunları **yeniden yükleyip doğrular** — istemciden metin alınmaz) → yeni istem: "yalnız bu pasajları, sade Türkçeyle, bir günlük hayat benzetmesiyle anlat; benzetmeyi `> Benzetme:` bloğuna ayır; pasajda olmayan hiçbir teknik iddia ekleme" → zincir: citation (atıf yine pasajlara), leakage (kod/adım sızıntısı kontrolü aynı), sanitize.

**Guardrail ile uzlaşma (kritik):** Benzetme tanımı gereği materyalde yoktur. Kural: benzetme **yalnız `> Benzetme:` bloğunda** yaşar; blok dışındaki her cümle atıf taşır. Zincire yeni halka **eklenmez**; `citation` guardrail'ine "alıntı bloğu içindeki cümleler atıf zorunluluğundan muaf, ancak blok en fazla 3 cümle" kuralı eklenir (`apps/api/app/modules/guardrails/citation.py`, R3). Blok sınırı aşılırsa cevap düşer, deterministik "bu kısmı sadeleştiremedim, pasaj şu" yedeğine iner. Frontend blok için görsel ayrım: "Benzetme — materyalde yok, anlamana yardım için" etiketi (`components/chat/analogy-note.tsx` yeni dosya).

**Kota/önbellek:** her `simplify` gerçek çağrıdır; `answer_cache`'e `intent` anahtar parçası olarak girer (§2.1 madde 4 — eski anahtar değişmez). Sahne sorularının `simplify` sürümü **demodan önce önbelleğe yazılmaz**; özellik Faz 2.

**Dosyalar:** `schemas/chat.py` (R3), `api/chat.py` (R3; yalnız niyet dallanması, `post_chat` gövdesine minimum dokunuş — `modules/agent/answers.py` `produce_answer` içinde yeni yol), `modules/generation/prompts.py` (R2), `modules/guardrails/citation.py` (R3), `modules/agent/token_precharge.py` (R3), `apps/web/lib/chat.ts` + `app/courses/[courseId]/chat/page.tsx` (R3 web).

**Testler:** `test_chat_api.py` — Sokratik + simplify → 422; QA + simplify → cevapta `> Benzetme:` bloğu var ve blok dışı cümleler atıflı (fake sağlayıcı senaryosu `modules/generation/fake.py`'ye eklenir); benzetme bloğu 4 cümle → düşer ve yedek gelir; `test_answer_cache.py` — eski anahtar hash'i aynı, `intent` farklı anahtar; `test_guardrails.py` — `TestAnlatimSizintisi` emsalinde blok muafiyeti testi; mutasyon: blok sınırı kaldırılınca test kırmızıya dönmeli. e2e: `apps/web/e2e/flows.spec.ts` sohbet bölümüne bir vaka (fake sağlayıcı).

**Dossier:** R3, `require_feature_flag`: `CHAT_SIMPLIFY_INTENT_ENABLED` (varsayılan kapalı), kill switch = bayrağı kapatmak, sticky assignment = ders bazlı.
**Süre:** 8–12 saat. **Riskler:** en yüksek — ürünün kalbi; benzetme bloğunun sızıntıya kapı olması (kod parçası benzetme kılığında → `leakage` yine çalışır, test var); jeton maliyeti.
**Kabul:** gerçek modelle 10 soruda benzetme bloğu dışında atıfsız cümle 0; Sokratik'te 422; bayrak kapalıyken düğme görünmez ve uç 404/403.

---

### F4 — Hızlı tekrar kartları (kaydırmalı)

**Hoca gereksinimi:** hızlı tekrar ve pekiştirme.

**Uygulandığı hâl (15 Eyl, `20d1700`) — plandan iki sapma, ikisi de ölçümle:** (1) Deste onaylı
havuzdan DEĞİL öğrencinin bitirdiği alıştırmadan kuruldu: `GET .../questions?status=approved`
öğrenciye cevap anahtarı vermiyor (`schemas/assessment.py:233` `_PUBLIC_PAYLOAD_KEYS`, yalnız
`stem`+`options`) ve bu sınav bütünlüğü kararı delinmedi; ön yüz `GET /exams/{sid}`, arka yüz
`GET /exams/{sid}/results`, ikisi de mevcut ve kilitli — **backend değişmedi**. (2) `card_reviewed`
olayı yazılmadı (§2.3 düzeltmesi). Aşağıdaki metin özgün plandır; tarihçe için duruyor.

**Lite (Faz 1) — onaylı havuzdan kart:** Yeni soru tipi **yok**. Kaynak: dersin `status=approved` soruları (`GET /courses/{id}/questions?status=approved`, mevcut). Kart önü: soru kökü (+ şıklar MCQ ise); dokunma/Enter → arka yüz: doğru cevap + **kaynak kartı** (`SourceInfo`, mevcut bileşen) + "neden" açıklaması varsa. Sağa kaydır / `→` = "Biliyordum", sola / `←` = "Tekrar". Her karar `card_reviewed` olayı (§2.3). Oturum sonu: X/Y biliyordun, "tekrar"ların konu dağılımı, `/study`'e bağlantı.

**Kapsam dışı (bilinçli):** puanlama yok, mastery'ye yazmaz (mastery yalnız gerçek cevaptan güncellenir — `modules/mastery/service.py` `record_answer`); kartlar sınav değildir. Chat'ten D/Y üretimi **yapılmaz**: model anında soru uydurur, onaysızdır (P5).

**Backend:** yalnız olay ucu `POST /courses/{id}/learning-events/card-reviewed` (`exams.py` `citation_opened` emsali; `exams.py` R3 → dossier) ve `get_learning_summary`'ye tür eklenmesi. `GET .../questions?status=approved` sayfalıdır; frontend `usePagedResource` ile çeker.

**Frontend:** `apps/web/app/courses/[courseId]/cards/page.tsx` yeni dosya + `layout.tsx`; `components/cards/card-deck.tsx`, `card-face.tsx`, `deck-summary.tsx` yeni dosyalar. Kaydırma: pointer events + `translateX`; `prefers-reduced-motion`'da animasyon yok, düğmeler her zaman var (kaydırma tek yol olamaz — erişilebilirlik). Klavye: `←/→/Enter/Space`; `aria-live` ile "Biliyordun / Tekrar" duyurusu. `course-nav.tsx`'e "Kartlar" sekmesi (mobil 4 sekme kuralı: gerekirse "Çalış" altına). Aktif sınavda sayfa kilit mesajı gösterir (uç zaten P3 ile 4xx döner; `chat-availability` emsali).

**Testler:** web `apps/web/lib/cards.test.ts` yeni dosya — deste sırası, karar sayacı, boş havuz durumu, klavye eşlemesi (saf mantık `lib/cards.ts`'te). API: olay kaydı, başka dersin `question_id`'si → 404, aktif sınav → kilit. e2e: `apps/web/e2e/student-cards.spec.ts` yeni dosya — onaylı 3 soru, 2 sağ 1 sol, özet metni; `screenshots.spec` çekimine bir kare (sunum sonrası galeri için).

**Full (Faz 3) — gerçek doğru/yanlış tipi:** `questions.type` **PostgreSQL enum** (`supabase/migrations/0004_assessment.sql:19`); `ALTER TYPE question_type ADD VALUE 'true_false'` göçü gerekir → numara şerit aralığından (`ENGEL`). Ardından `models/assessment.py` `QuestionType`, `schemas/assessment.py` (`TrueFalsePayload`, `parse_payload/public_payload/solution_payload` dalları), `modules/assessment/question_gen.py` üretim istemi (§2.1), `grading.py` puanlama (deterministik), RLS testleri (`supabase/tests/`), frontend `QuestionBody` dalı. Eğitmen onay akışı değişmez.

**Dossier:** lite için `exams.py` R3 (tek uç) — küçük dossier. Full için R3 + göç.
**Süre:** lite 6–8 saat; full 12+ saat.
**Kabul (lite):** onaysız (`draft`) soru kartlarda **hiç** görünmez (negatif test); aktif sınavda sayfa kilitli; klavyeyle baştan sona geçilebilir; kaydırma kapalıyken (reduced motion) düğmelerle aynı sonuç.

---

### F5 — Anahtar kavram haritası (cheat sheet)

**Hoca gereksinimi:** konunun özü; parçalar ve bağlantılar (reductionism → systems thinking).

**Lite (Faz 1) — materyalden çıkarım, model yok:**
- **Parçalar:** dersin READY belgelerinin chunk'larından anahtar terimler. Yöntem: `app/core/text_tr.tokens(min_length=4)` + `fold` ile normalize; belge-frekansına göre TF-IDF benzeri ağırlık (chunk = belge); kısa durak listesi `text_tr` içinde varsa o, yoksa yeni dosya `core/stopwords_tr.py` (~150 kelime, elle). Üst 40 terim.
- **Her terim için** en yüksek ağırlıklı **tek pasaj** (chunk) → kaynak kartı: dosya, sayfa/slayt, 1–2 cümle (mevcut `_best_snippet`/`SNIPPET_CHARS` mantığı `modules/assessment/grading.py:74-172`'de; **oradan import edilir** — o blok ayrı modüle taşınmayı bekliyor, taşınırsa import yolu güncellenir).
- **Bağlantılar:** iki terim aynı chunk'ta geçiyorsa kenar; ağırlık = birlikte geçtiği chunk sayısı. Üst 60 kenar. Bu, "sistem" katmanıdır: hangi parçalar birlikte anlatılıyor.
- **Konu bağı:** `Topic` (`models/assessment.py:52`) ve `LearningOutcome` varsa terimler konuya eşlenir (onaylı soruların `source_chunk_id` → konu).
- Çıktı: JSON (`GET /courses/{id}/concepts`) + Markdown dışa aktarım (`/concepts/export`, §2.4). Hesap **ders + korpus revizyonu** anahtarıyla önbelleklenir (yeni tablo **yok**; süreç içi `functools.lru_cache` yeterli değil — worker'da ayrı süreç; ilk sürümde her istekte hesapla, 200 chunk'lık derste ölç; yavaşsa `answer_cache` benzeri tablo Faz 2).

**Frontend:** `apps/web/app/courses/[courseId]/concepts/page.tsx` yeni dosya. Üst: "Parçalar" — terim rozetleri (ağırlığa göre boyut **değil**, sıra; boyutla anlam taşımak DESIGN.md'nin "durumlar metinle de açıklanır" kuralına aykırı). Terime tıkla → pasaj kaynak kartı + `concept_opened` olayı. Alt: "Bağlantılar" — kenar listesi tablo (terim A — terim B — kaç pasajda birlikte — o pasajlardan biri). Grafik çizimi **yok** (Faz 2; SVG elle, kütüphane yok). İndir düğmesi.

**Full (Faz 2):** Her terim için LLM'in **yalnız o pasajdan** yazdığı tek cümlelik tanım (§2.1; atıfsız tanım düşer, terim pasajla kalır); konu başına "bu parçalar şu bütünü kurar" bir paragraf. Her cümle atıflı.

**Testler:** `apps/api/tests/test_concepts.py` yeni dosya — deterministik korpusla üst terimler ve kenarlar sabit; durak kelimeler çıkmıyor; başka dersin chunk'ı görünmüyor (iki ders); READY olmayan belge dâhil değil; Markdown'da ham kimlik yok; aktif sınav kilidi. Web: `lib/concepts.test.ts` sıralama/gruplama.
**Sensitive:** `modules/**` R3 (yeni dosya `modules/retrieval/concepts.py` ya da `modules/assessment/concepts.py` — retrieval R2 daha uygun; `.ai/policy.json`'a yeni dosya eklenmesi önerilir), `main.py` R3 → dossier.
**Süre:** lite 6–8 saat; full +5 saat.
**Riskler:** Türkçe ekler yüzünden aynı kavramın iki terim sayılması (`fold` yardımcı olur, gövdeleme yok — kabul edilen sınır, ekranda "aynı kavramın çekimleri ayrı görünebilir" notu); büyük korpusta hesap süresi.
**Kabul:** iki dersli testte sızıntı 0; üst 40 terimin ≥ 35'i durak/sayı değil (elle bakılır, dossier'e yazılır); her terimin pasajı gerçekten o terimi içeriyor (test).

---

## 4. Özet tablo

| # | Özellik | Faz | LLM | Yeni göç | Sensitive | Dossier | Süre (tahmin) |
|---|---|---|---|---|---|---|---|
| F1 | Çalışma özeti | 1 (lite) / 2 (full) | lite hayır / full evet | hayır | `main.py`, `modules/assessment` | evet | 5–7 s / +4 s |
| F2 | Marka/logo | 1 | hayır | hayır | yok | hayır | 2–3 s |
| F3 | Analoji niyeti | 2 | **evet** | hayır | `chat.py`, `schemas/chat`, `guardrails`, `generation` | evet, bayraklı | 8–12 s |
| F4 | Tekrar kartları | 1 (lite) / 3 (full) | lite hayır / full evet | lite hayır / **full evet** | `exams.py` | evet (küçük) | 6–8 s / 12+ s |
| F5 | Kavram haritası | 1 (lite) / 2 (full) | lite hayır / full evet | hayır | `modules/retrieval` veya `assessment`, `main.py` | evet | 6–8 s / +5 s |

---

## 5. Açık kararlar (Murat) — `ENGEL` listesi

| # | Karar | Kimi bloke ediyor |
|---|---|---|
| K1 | Göç ve dossier numara aralığı (bu özellik şeridi için) | F1, F3, F4, F5 dossier'leri; F4-full göçü |
| K2 | Ürün işaretinin biçimi (sinaps mı, harf mi) | F2 madde 1 |
| K3 | `.ai/policy.json`'a yeni dosyaların R2/R3 olarak eklenmesi (policy.json kendisi R3 → ayrı onay) | F1, F5 |
| K4 | F3'ün bayrak adı ve varsayılan durumu (öneri: `CHAT_SIMPLIFY_INTENT_ENABLED=false`) | F3 |
| K5 | Kartlar sekmesinin mobil gezinmede yeri (4 sekme kuralı) | F4 frontend |
| K6 | F5'te gövdeleme (stemming) istenir mi — bağımlılık gerekir (`ENGEL: bağımlılık`) | F5 kalite |

---

## 6. Sunumda nasıl anlatılır (16 Eylül)

Bu beş özellik **v2 yol haritası** slaytında durur, demo yapılmaz. Tek cümlelik anlatım:
"Hepsi aynı ilkeyle: model ancak öğretmenin materyaline dayanarak konuşur; kartlar yalnız
öğretmenin onayladığı sorulardan gelir; kavram haritası ve çalışma özeti materyalden ve
öğrencinin kendi geçmişinden çıkarılır; 'anlamadım' modunda benzetme ayrı bir kutuda
'materyalde yok' etiketiyle durur." Hoca "neden şimdi yok" derse: demo yığını 14 Eylül'de
donduruldu; bunlar ölçülmüş bir taban üstüne, dossier'li ve bayraklı gelecek.
