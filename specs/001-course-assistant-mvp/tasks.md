---

description: "DOU-Synapse CourseGPT MVP — kalan işlerin görev listesi (G5-G15)"
---

# Görevler: CourseGPT — Ders ve Sınav Asistanı MVP

**Girdi**: `/specs/001-course-assistant-mvp/` tasarım belgeleri + kök `PLAN.md`, `ARCHITECTURE.md`, `DESIGN.md`

**Ön koşullar**: PLAN.md (takvim + kapsam), ARCHITECTURE.md (nihai kararlar), `.specify/memory/constitution.md` v1.0.0, `specs/001-course-assistant-mvp/contracts/openapi.json` (dondurulmuş sözleşme — yeni uçlar eklenirken güncellenir)

**Testler**: pytest (apps/api/tests/) mevcut düzeni sürdürür; her faz kendi davranış testlerini içerir. Anayasa VIII gereği "bitti" = testler yeşil + lint temiz + davranış gerçek ortamda (tarayıcı veya gerçek API çağrısı) gözlenmiş.

**Organizasyon**: Görevler PLAN.md §3 takvimindeki fazlara (A-H) göre gruplanır. G1-G4 işleri tamamlandı ve aşağıda tek satırlık özetle geçilir.

## Format: `[ID] [P?] [Faz] Açıklama`

- **[P]**: Paralel koşulabilir (farklı dosyalar, tamamlanmamış göreve bağımlılık yok)
- **[Faz]**: A Retrieval · B Generation+Guardrails · C Chat · D Sokratik+Sınav · E Mastery+Analitik · F Eval · G Deploy · H Belgeler
- Her görev TAM dosya yolu içerir; henüz var olmayan dosyalar **YENİ:** önekiyle işaretlidir
- **Done = committed**: Anayasa IX gereği her görev kendi conventional commit'iyle biter ve tamamlanınca tarihli **DONE** notu düşülür (innova/specs/001 üslubu)

## Yol Kuralları (repodan doğrulanmış)

- Backend: `apps/api/app/` — `api/` (router'lar), `modules/` (ingestion/retrieval/generation/guardrails/assessment/mastery), `models/`, `schemas/`, `core/`, `worker.py`
- Frontend: `apps/web/app/` (App Router), `apps/web/components/`, `apps/web/lib/{api.ts,types.ts}` — Bun + Next.js 16 (bkz. `apps/web/AGENTS.md`: sürüm eğitim verisinden farklı olabilir, `node_modules/next/dist/docs/` okunur)
- SQL: `supabase/migrations/` (düz SQL, ORM'den üretilmez — `app/models/core.py` şemayı yansıtır), RLS testi `supabase/tests/rls_isolation.sql`
- Backend yetki deseni: `apps/api/app/api/deps.py` içindeki `CourseMemberDep` (course_id istemciden asla yetki değildir)
- Testler: `apps/api/tests/` — mevcut `conftest.py` düzeni

---

## Faz 0: Tamamlanan işler (G1-G4) — özet

- [x] **G1** Monorepo iskeleti + CI (`.github/workflows/ci.yml`: ruff, mypy, pytest, RLS izolasyon kanıtı) + çekirdek şema (`supabase/migrations/0001_core_schema.sql` — unaccent + `chunks.fts` generated column + GIN indeksi DAHİL; FTS için ek migration gerekmez) + Compose fallback (`docker-compose.yml`)
- [x] **G2** Auth (JWT doğrulama `app/core/security.py`, DEV_AUTH lokal) + ders/üyelik API'si (`app/api/courses.py`) + RLS politikaları + izolasyon smoke testi (`apps/api/tests/test_courses.py`, `supabase/tests/rls_isolation.sql`) + OpenAPI sözleşmesi donduruldu (`specs/001-course-assistant-mvp/contracts/openapi.json` — 9 uç)
- [x] **G3** Upload + validasyon + job tablosu + parser'lar (`app/api/documents.py`, `app/modules/ingestion/{validation,parsers,storage,pipeline}.py`, `app/worker.py`)
- [x] **G4** Chunking + embedding + pgvector (`app/modules/ingestion/{chunking,embedding}.py` — multilingual-e5-large, `query:`/`passage:` önek davranışı `tests/test_embedding_prefix.py` ile sabit)
- [x] Frontend iskeleti: demo yolu ekranları (`apps/web/app/courses/**`), tasarım token'ları (`DESIGN.md` → `apps/web/app/globals.css`), API istemcisi (`apps/web/lib/api.ts` — şimdilik dev-token)

> Not: PLAN G3 çıktısı olan `sample_data/` paketi repoda YOK — T002 olarak görevleştirildi.

---

## Faz A: Retrieval hattı (PLAN G5-G7)

**Amaç**: Dense (pgvector) + FTS (simple+unaccent) + RRF füzyonu + evidence gate. Her sorguda zorunlu `course_id` filtresi.

- [ ] T001 [A] Doğrulama (migration YOK): FTS altyapısının tamamı `supabase/migrations/0001_core_schema.sql`'de zaten uygulanmış durumda — `unaccent` extension, `app.immutable_unaccent` IMMUTABLE sarmalayıcı, `chunks.fts` generated column (`to_tsvector('simple', ...)`) ve `chunks_fts_idx` GIN indeksi. Görev: lokal DB'de `SELECT fts FROM chunks LIMIT 1` ve örnek `websearch_to_tsquery` sorgusuyla kolonun dolu ve sorgulanabilir olduğu doğrulanır; sonuç tasks notuna işlenir.
- [x] T002 [P] [A] YENİ: `sample_data/isletim-sistemleri/` v1 paketi — ≥3 PDF + 1 PPTX + 2 kod dosyası (PLAN G3 tanımı). Telifsiz/kendi üretimi materyal; canlı demo yüklemesi için 5-10 sayfalık küçük bir PDF ayrıca işaretlenir. `sample_data/README.md` ile içerik listesi. **DONE (2026-08-06):** 5 PDF + 1 PPTX + 2 kod dosyası (biri bilinçli hatalı) yazıldı, README dolduruldu. Derse gerçek yükleme + `completed` doğrulaması Metehan'ın yerel ortamında yapılacak (Anayasa VIII, sandbox'ta canlı Postgres yok).
- [x] T003 [A] YENİ: `apps/api/app/modules/retrieval/dense.py` — pgvector cosine top-20; sorgu embedding'i mevcut `apps/api/app/modules/ingestion/embedding.py` üzerinden `query: ` önekiyle üretilir; zorunlu `WHERE course_id = :authorized_course_id`. **DONE (2026-08-09):** kosinüs (`<=>`) seçildi ve gerekçesi ÖLÇÜLDÜ — e5 çıktısı birim değil (norm 27.4-30.3), bu yüzden L2/iç çarpım kosinüsten farklı sıralama üretiyor (12 sorguda 10 ve 12 kez).
- [x] T004 [P] [A] YENİ: `apps/api/app/modules/retrieval/fts.py` — MEVCUT `chunks.fts` kolonuna karşı `websearch_to_tsquery('simple', unaccent(:q))` ile top-20; aynı zorunlu course_id filtresi. **DONE (2026-08-09):** `websearch_to_tsquery` (tırnak/eksi korunuyor), ama örtük VE gerçek materyalde 10 sorgunun 9'unda sıfır sonuç verdiği ölçüldüğü için açık işaret yoksa VEYA'ya gevşetiliyor; sıralama `ts_rank`.
- [x] T005 [A] YENİ: `apps/api/app/modules/retrieval/fusion.py` — Reciprocal Rank Fusion (k=60), T003+T004 sonuç listelerini birleştirir → top-8. **DONE (2026-08-09):** saf RRF (k=`retrieval_rrf_k`), belirlenimci beraberlik bozma; `max_possible_score()` fused skorun neden eşik taşıyamayacağını kanıtlıyor.
- [x] T006 [A] YENİ: `apps/api/app/modules/retrieval/service.py` + `apps/api/app/core/config.py`'ye ayarlar (`retrieval_dense_k=20`, `retrieval_fts_k=20`, `rrf_k=60`, `retrieval_final_k=8`, `evidence_threshold`) — tek giriş noktası `retrieve(session, course_id, query)`; en iyi sonuç eşik altındaysa boş/abstain sonucu döner (fail-closed). Eşik başlangıç değeri geçicidir; kalibrasyon T043'te. **DONE (2026-08-09):** `HybridRetriever.search()` HAM sonuç (kalibrasyon eşiği süpürebilsin), `retrieve()` kanıt kapısını uygular ve eşik altında chunks'ı BOŞ döner. Kapı `dense_score`'a bakıyor; `config.py`'ye DOKUNULMADI. **T043 için bulgu:** gerçek materyalde varsayılan 0.35 ile konu dışı 10 sorgunun 10'u da kapıdan geçiyor — en iyi kesim 0.7963'te doğruluk 0.96 (n=24, yön göstergesi).
- [x] T007 [A] YENİ: `apps/api/tests/test_retrieval.py` — (1) başka dersin chunk'ı hiçbir koşulda dönmez (izolasyon), (2) RRF birleşimi sentetik sıralamalarla doğrulanır, (3) eşik altı sorgu abstain döner, (4) FTS teknik token'ı (`fork()`) yakalar. `EMBEDDING_PROVIDER=hashing` ile deterministik koşar. **DONE (2026-08-09):** 54 test. İzolasyon üç katmanlı kanıtla: RLS tek başına, uygulama filtresi tek başına, ve politika `USING(true)` yapılıp sızıntının GERÇEKLEŞTİĞİ doğrulanıyor (Anayasa II, her koşuda). Gerçek materyalde TR/EN doğrulaması ayrıca yapıldı: top-1 doğru dosya 8/10, top-3 içinde 10/10.

**Kapanış kabul kriteri**: Seed'li derste TR ve EN sorguyla dense-only ve hybrid sonuçlar elde ediliyor; izolasyon + abstain testleri ve ruff/mypy yeşil; gerçek materyal (`sample_data/`) ingest edilip canlı URL'de sorgulanabiliyor (G5 kapısı).

---

## Faz B: Generation + guardrail zinciri (PLAN G5-G8)

**Amaç**: LiteLLM failover'lı üretim + Pydantic cevap şeması + deterministik citation validator + kod/çözüm sızıntı filtresi. ARCHITECTURE §5 sıralaması aynen uygulanır.

- [x] T008 [B] `apps/api/pyproject.toml`'a `litellm` bağımlılığı; `apps/api/app/core/config.py`'ye LLM ayarları (Groq/Gemini model adları, API anahtarları, timeout, retry sayısı, günlük token bütçesi); `.env.example` güncellenir (anahtarlar boş şablon). **DONE (2026-08-09):** config.py ve pyproject zaten hazırdı; .env.example'a LLM bloğu eklendi. Anahtarlar boş şablon: ikisi de tanımsızsa sistem sahte sağlayıcıya düşer, kurulum ağsız tamamlanır.
- [x] T009 [B] YENİ: `apps/api/app/modules/generation/llm.py` — LiteLLM Router: Groq (Llama) → Gemini Flash OTOMATİK failover + exponential backoff (kod seviyesinde, manuel anahtar değişimi değil); token kullanımı redaction'lı logger'a yazılır. **DONE (2026-08-09):** LiteLLM üzerinden Groq→Gemini otomatik failover; üstel geri çekilme llm_max_retries ile sınırlı. Süre çift katmanlı (deneme başına + toplam bütçe): tek katman olsaydı failover toplam gecikmeyi sessizce katlardı. 429→failover ve 401→retry'sız failover mock ile testli. litellm tembel import ediliyor. GERÇEK ÇAĞRI YAPILAMADI: ortamda API anahtarı yok, gecikme yalnız sahte sağlayıcıda ölçüldü (uçtan uca p50 0.08 ms). Anahtar geldiğinde tek gerçek çağrı + gecikme ölçümü yapılmalı.
- [x] T010 [P] [B] YENİ: `apps/api/app/schemas/chat.py` — ARCHITECTURE §5 cevap şeması: `status: answered|insufficient_context|out_of_scope`, `mode: qa|socratic|exam`, `answer`, `citations[{chunk_id, claim}]`, `hints[{text, chunk_id}]` + istek şemaları. **DONE (2026-08-09):** schemas/chat.py — model çıktısı (LlmAnswerPayload) ile istemci zarfı (ChatResponse) ayrı. Dosya adı/konum/alıntı yalnız zarfta ve chunk metadata'sından. ChatRequest'te socratic_stage yok (kademe state machine'in işi, FR-014). NOT: ARCHITECTURE §5'teki citations[].claim alanının contracts.Citation'da karşılığı yok; sunum verisi olarak zarf katmanında taşınıyor, guardrail kararlarına girmiyor.
- [x] T011 [B] YENİ: `apps/api/app/modules/generation/prompts.py` — bağlam `<retrieved_context><source id="..." page="...">` XML etiketleriyle veri olarak işaretlenir (indirect injection önlemi); qa/socratic/exam mod prompt'ları; müfredat dışına nazik Türkçe ret talimatı. **DONE (2026-08-09):** Bağlam <source> etiketleriyle veri olarak işaretleniyor; materyal ve öğrenci sorusu kaçıştan geçip etiket sınırı sabit noktaya kadar denetleniyor (tek geçiş `</sou</source>rce>` yazımında etiketi geri üretiyordu). İstenen JSON biçimi şema alanlarından türetiliyor ki prompt ile şema ayrışmasın.
- [x] T012 [B] YENİ: `apps/api/app/modules/generation/service.py` — `generate(chunks, question, mode)`: prompt → LLM → Pydantic validasyon; bozuk çıktıda 1 retry; yine bozuksa `insufficient_context` (fail-closed). **DONE (2026-08-09):** Chunk yoksa LLM hiç çağrılmıyor; bozuk çıktı llm_max_retries kadar yeniden deneniyor, ısrarda insufficient_context. Sağlayıcı arızası bilerek abstention'a çevrilmiyor (503 yükseliyor) — SC-005 ret oranını şişirmemek için. Dosya adı/sayfa modelden değil metadata'dan.
- [x] T013 [B] YENİ: `apps/api/app/modules/guardrails/citation.py` — set-membership: cevap ve hint'lerdeki `chunk_id` ⊆ retrieve edilen küme (deterministik); ihlal eden atıf temizlenir, geçerli atıf kalmazsa CEVAP GÖSTERİLMEZ; `chunk_id → {file_name, page_number/slide_number, snippet}` eşlemesi model metninden değil chunk metadata'sından üretilir. **DONE (2026-08-09):** Set-membership deterministik; uydurma atıf düşüyor, geçerli atıf kalmazsa cevap bloklanıyor. dropped_citations tek yerde sayılıyor (Anayasa III). Abstention muaf: kaynak bulamadığını söylemek için kaynak gerekmiyor. İpucu kaynakları da aynı kümeye katılıyor — tek kapı.
- [x] T014 [P] [B] YENİ: `apps/api/app/modules/guardrails/leakage.py` — kural tabanlı kod bloğu + doğrudan-çözüm dedektörü (fence, girinti deseni, "cevap: X" kalıpları); ihlalde 1 regen; yine ihlalse şablon ipucuna düşer (deterministik son durak). Şablon ipuçları da kaynak chunk_id taşır. **DONE (2026-08-09):** Altı dedektör (kod çiti, çitsiz girintili kod, cevap/sonuç kalıbı, sözde-kod, kod imzası, adım adım çözüm). Türkçe eşleştirme re.IGNORECASE ile değil açık varyantlarla: 'İ'.lower() 'i' ile eşleşmiyor ve büyük harfli 'ÇÖZÜM:' kaçıyordu. Sokratik+sınav modunda etkin; ihlalde 1 regen, ısrarda kaynak taşıyan şablon ipucu. Sınavda şablon yolu kapalı, ihlal doğrudan bloklanıyor. Kalıpsız (düzyazı) sızıntı MİTİGASYON, garanti değil — oran T041 gold set üzerinde ölçülecek.
- [x] T015 [P] [B] YENİ: `apps/api/app/modules/guardrails/sanitize.py` — Markdown/HTML temizliği (XSS); ham stack trace asla kullanıcıya gitmez (Anayasa X). **DONE (2026-08-09):** Varlıklar önce çözülüyor (&#106;avascript: kaçışı için), etiket sökümü sabit noktada. Etiket deseni dar: 'x < y > z' yenmiyor. Hassas kalıplar core.logging.redact'ten geliyor, yeniden tanımlanmadı. Metin temizlikte tamamen giderse cevap bloklanıyor.
- [x] T016 [B] YENİ: `apps/api/tests/test_guardrails.py` — (1) uydurma chunk_id'li atıf düşer, atıf kalmazsa cevap bloklanır, (2) kaynaksız hint bloklanır, (3) fence'li/fence'siz kod ve "cevap: X" kalıbı yakalanır, regen sonrası ısrarda şablona düşer, (4) sanitize XSS payload'ı temizler, (5) LLM mock'uyla Groq 429 → Gemini failover birim testi. **DONE (2026-08-09):** 68 test, hepsi ağsız (160/160 yeşil, ruff temiz). Enjeksiyon iki seviyede: yapısal (etiket sınırı kırılamıyor) ve davranışsal (model enjeksiyona UYSA bile zincir durduruyor). Ağsızlık, sağlayıcı adına bakarak değil TCP bağlantısı yasaklanarak sınandı. Yanlış pozitif testleri de var: filtre meşru ipucunu bloklarsa Sokratik mod ölür. Guardrail zinciri gecikmesi p50 0.040 ms (n=200).

**Kapanış kabul kriteri**: Mock retrieval üzerinde üretim zinciri (generation → citation → leakage → sanitize) uçtan uca çalışır; "model atıf uyduramaz" davranışı testle kanıtlı (G6 çıktısı); tüm testler + lint yeşil.

---

## Faz C: Chat API + frontend bağlama (PLAN G5-G8)

**Amaç**: Sorgu pipeline'ını tek chat ucunda birleştirmek ve `apps/web` chat sayfasını mock'tan gerçek veriye geçirmek.

- [x] T017 [C] YENİ: `supabase/migrations/0003_chat.sql` — `chat_sessions` (mode qa|socratic, state), `chat_messages` (citations jsonb), `answer_cache` (course_id, question_hash, response jsonb — exact-match demo cache), `request_logs` (redaction'lı; latency, status, course_id, token_count) + RLS politikaları (üye kendi oturumunu okur/yazar; `request_logs`'a istemci erişimi yok). **DONE (2026-08-09):** dört tablo + `chat_mode`/`chat_role`/`answer_status`/`socratic_stage` enum'ları (değerler `contracts.py` ile birebir). Önbellek sütunu `response` değil **`answer`** adlandırıldı (03 handoff'u esas alındı; T053 bu adı kullanmalı). Her INSERT politikası ya `app.is_member(course_id)` çağırıyor ya da satırın course_id'sini oturumunkiyle eşliyor — 0004'te yakalanan "yalnız user_id" açığı tekrarlanmadı. `chat_messages`'ta UPDATE/DELETE politikası yok (geçmiş denetlenebilir kalmalı). `request_logs` yazma-yalnız: SELECT politikası yok, dolayısıyla `INSERT ... RETURNING` kullanılamaz (psql'de doğrulandı). Sıfırdan bir veritabanına hatasız uygulandı; RLS iddiaları psql ile fiilen denendi (üye olmayan oturum açamıyor, oturum başka derse taşınamıyor, sahte course_id ile mesaj enjekte edilemiyor, geçmiş değiştirilemiyor).
- [x] T018 [C] YENİ: `apps/api/app/models/chat.py` — 0003 migration'daki tablolarla birebir SQLAlchemy modelleri (`app/models/core.py` deseni). **DONE (2026-08-09):** `ChatSession`/`ChatMessage`/`AnswerCache`/`RequestLog`. Enum sütunları `contracts.py`'deki tiplere doğrudan bağlandı, ikinci bir tanım açılmadı. `_pg_enum` yardımcısı `models/core.py`'den içe aktarıldı — üçüncü kopya yazılmadı (Anayasa XI); helper'ın `models/base.py`'ye taşınması lider için not edildi.
- [x] T019 [C] YENİ: `apps/api/app/api/chat.py` — `POST /courses/{course_id}/chat`: `CourseMemberDep` authz → `answer_cache` exact-match kontrolü → retrieval (T006) → evidence gate → generation (T012) → citation validator (T013) → (moda göre) leakage (T014) → sanitize (T015) → mesaj + `request_logs` kaydı; oturum/geçmiş uçları (`GET .../chat/sessions`, mesaj listesi); kullanıcı başına istek sınırı (rate limit) ve soru uzunluğu sınırı bu uçta uygulanır (FR-035). Router `apps/api/app/main.py`'ye eklenir ve `specs/001-course-assistant-mvp/contracts/openapi.json` sözleşmesi güncellenir. **DONE (2026-08-09):** `POST /courses/{course_id}/chat` + `GET .../chat/sessions` + `GET .../chat/sessions/{session_id}`; router zaten kayıtlıydı, `main.py`'ye dokunulmadı; openapi.json yeniden export edildi (13 yol). Retrieval/generation/guardrail `contracts.py` imzalarına karşı yazıldı ve `set_pipeline()` ile takılıyor; takılı değilse uç 503 döner (fail-closed, sessiz boş cevap yok). **Kanıt eşiği füzyon skoruna değil dense skoruna bakar** — RRF skoru 1/(k+sıra) toplamıdır ve k=60'ta ~0.016 çıkar, 0.35'lik eşikle karşılaştırılsaydı her soru reddedilirdi. Ret metinleri sabittir ve modelden gelmez (injection savunması + Anayasa V). FR-035 sınırları uçta: 2000 karakter → 422, kullanıcı+ders başına dakikada 20 istek → 429; sayaç süreç içidir (tek worker varsayımı, raporda böyle anlatılacak). `mode=exam` bu uçtan reddedilir (422): sınavda ipucu kapalı ve bu uç bir ipucu yüzeyi. **DONE (2026-08-09):** uç Şerit 3'te yazıldı; lider şeridinde zarf `app/schemas/chat.py`'ye taşındı — uçtaki geçici `ChatRequest`/`ChatResponse` kopyası silindi. Canlı doğrulandı (COME 331, gerçek materyal): kaynaklı cevap `Sayfa 3` atfıyla, kapsam dışı soru `insufficient_context` + Türkçe ret.
- [x] T020 [C] YENİ: `apps/api/tests/test_chat_api.py` — (1) kaynaksız akademik cevap asla dönmez, (2) kapsam dışı soru `out_of_scope` + nazik Türkçe metinle döner, (3) üye olmayan kullanıcı erişemez, (4) cache isabeti LLM çağrısı yapmaz (mock ile kanıt), (5) abstention cevabı hata zarfı DEĞİL normal 200 + `insufficient_context`, (6) istek sınırı aşımında 429 ve aşırı uzun soru 422 döner (FR-035). **DONE (2026-08-09):** 25 test; altı vakanın tamamı + izolasyon (başka dersin materyali karışmıyor, A dersinin önbelleği B'ye servis edilmiyor), üye olmayan **404** alıyor (403 değil), RLS'in ikinci katmanı `rls_session` üzerinden ayrıca sınanıyor. Sahte retriever kendisine gelen `course_id`'ye bakıyor: uç yetkilendirilmiş dersi geçirmezse test kırmızıya döner.
- [x] T021 [P] [C] `apps/web/lib/types.ts` + `apps/web/lib/api.ts` — chat sözleşme tipleri (AnswerResponse, ChatMessage, Citation) ve istemci fonksiyonları; backend hata zarfı `{error:{code,message}}` düzeni korunur (Anayasa V). **DONE (2026-08-09):** tipler openapi.json ile birebir hizalandı (`hints` artık `Hint[]`, `claim`/`snippet`/`cached` eklendi, `ChatMessage`+`ChatSessionSummary` tamamlandı). `lib/api.ts` ayrıştırılamayan 200 yanıtını artık sessizce null'a düşürmüyor; FastAPI'nin ham 422 biçimi SUNUCUDA tek zarfa alındığı için istemcide savunma kodu gerekmedi.
- [x] T022 [C] `apps/web/app/courses/[courseId]/chat/page.tsx` — gerçek veriye geçiş: mesaj geçmişi, `apps/web/components/source-card.tsx` ile dosya adı + sayfa/slayt kaynak kartları, abstention hata gibi DEĞİL bilgi durumu olarak gösterilir (Anayasa VII); token'lar `DESIGN.md`'den. **DONE (2026-08-09):** ekran gerçek akışa geçti — oturum listesi, geçmiş, üç `status` ayrı ele alınıyor, abstention nötr yüzeyde (kırmızı/ünlem/`role="alert"` yok), Sokratik turda `question`=açılış sorusu + `student_attempt`=deneme, `PreviewBanner` ve uydurma kaynak listesi kaldırıldı. Tarayıcıda doğrulandı (:3010 → :8010).
- [ ] T023 [C] `apps/web` girişini gerçek Supabase Auth'a bağla — YENİ: `supabase/migrations/0002_supabase_auth_bridge.sql` (auth.users→profiles senkron trigger'ı; 0001'in şema yorumunda ve data-model.md §2.1'de ayrılmış numara) + YENİ: `apps/web/lib/supabase.ts` (`@supabase/supabase-js` bağımlılığı `apps/web/package.json`'a), `apps/web/app/page.tsx` giriş akışı Supabase oturum token'ını `lib/api.ts`'e taşır; dev-token (`dev:<uuid>`) yalnız lokal/Compose fallback olarak kalır (`DEV_AUTH_ENABLED` ile). **BACKEND AYAĞI DONE (2026-08-09) — kutu AÇIK, frontend ayağı liderde:** `0002_supabase_auth_bridge.sql` yazıldı ve sıfır veritabanında 0001→0005 sırasıyla hatasız koşuyor; ikinci kez koşturulduğunda da hata vermiyor (idempotent). Trigger koşullu kuruluyor (`auth` şeması varsa), fonksiyonlar koşulsuz — testler migration'ın kendi `app.install_auth_user_bridge()` fonksiyonunu çağırıyor, kendi trigger'ını yazmıyor. `apps/api/tests/test_auth_bridge.py`: 15 test (profil oluşma, e-posta normalizasyonu, e-posta/ad senkronu, girişte gereksiz UPDATE yazılmaması, silmede profilin KALMASI, e-posta çakışmasının ve e-postasız kaydın reddi, backfill 1 eklendi/1 atlandı). `app/core/security.py` sertleştirildi: exp/sub/aud/iss zorunlu claim, `none` algoritması elenir, tek ret mesajı; `tests/test_security.py` 25 test. GERÇEK SUPABASE'DE KOŞULMADI (anahtar yok) — sahte `auth.users` ve yetkisiz taklit rolle sınandı. Frontend ayağı liderde (docs/team/parallel/11_R1_KIMLIK.md raporu).

**Kapanış kabul kriteri**: Tarayıcıda login → ders → gerçek materyale kaynaklı cevap (dosya adı + sayfa görünür) → kapsam dışı soruda nazik ret; canlı URL'de uçtan uca gözlemlenmiş (G5 kapısı + G8 sertleştirme); testler yeşil.

---

## Faz D: Sokratik motor + sınav modu (PLAN G7-G9)

**Amaç**: Backend state machine'li Sokratik mod, 4 tipli soru üretici + eğitmen onayı, süreli sınav provası, "neden yanlış?" ve açık uçlu rubrik değerlendirme.

- [x] T024 [D] YENİ: `supabase/migrations/0004_assessment.sql` — `topics`, `questions` (type: mcq|open|code_trace|bug_hunt, payload jsonb, source_chunk_id, status: draft|approved|rejected), `exam_sessions` (mode: practice|exam), `answers` (feedback jsonb: {score, eksik_noktalar[], dayanak_chunk_id}), `mastery` + RLS (öğrenci yalnız `approved` soruları görür; draft/rejected yalnız eğitmen).
- [x] T025 [D] YENİ: `apps/api/app/models/assessment.py` — 0004 tablolarının modelleri. **DONE (2026-08-06):** migration + model + topics ucu (T030'un ilk parçası) yazıldı; yerel Postgres olmadığı için canlı doğrulama Metehan tarafından yapılacak.
- [x] T026 [D] YENİ: `apps/api/app/modules/assessment/socratic.py` — state machine `DIAGNOSE → NUDGE → CONCEPT_HINT → SIMILAR_EXAMPLE → EXPLAIN_WITH_SOURCE`; öğrenci denemesi olmadan kademe ilerlemez; ipuçları retrieve edilmiş chunk'lardan türetilir ve `chunk_id` taşır (evidence gate'ten geçer); her kademe geçişi event olarak loglanır. **DONE (2026-08-09):** saf state machine — veritabanı ve LLM bilmiyor, testleri DB'siz koşuyor. **"Deneme" tanımı karar olarak verildi ve gerekçesi modül docstring'ine yazıldı:** "bilmiyorum" yalnız DIAGNOSE'da ilerletir (orada "hiçbir şey" sorunun geçerli cevabıdır), sonrasında ilerletmez — aksi hâlde merdiven beş mesajlık geri sayıma döner. Yanlış cevap ilerletir: ilerleme çabaya bağlı, isabete değil. Kademe **sunucu otoritesindedir**, model kendini terfi ettiremez. Geçişler hem `chat_sessions.state`'te hem yapılandırılmış logda kayıtlı. Şablon ipuçları chunk metnini alıntılamaz (kaynak parça çözümü içerebilir) ama `chunk_id` taşır.
- [x] T027 [D] `apps/api/app/api/chat.py`'ye `mode=socratic` entegrasyonu — state `chat_sessions.state`'te tutulur; Sokratik cevap yolu leakage filtresinden (T014) zorunlu geçer; exam modunda hint tamamen kapalı (mod politikaları backend'de). **DONE (2026-08-09):** durum her turda jsonb'a yazılıyor, bozuk/eksik veri merdivenin başına düşüyor (fail-closed). Deneme yapılmadıysa üretim **hiç çağrılmıyor**: kullanıcı nazik uyarıyı ve aynı kademenin şablon ipucunu alıyor — merdiven ilerlemiyor, LLM bütçesi ısrarla tüketilemiyor. Filtre ihlalinde tam olarak bir kez yeniden üretiliyor, sürerse şablona düşülüyor (FR-015). Oturumun modu ortada değiştirilemiyor (422), `mode=exam` uçtan reddediliyor. Canlı koşuda (gerçek Postgres + gerçek materyal + uvicorn) iki kusur yakalanıp düzeltildi: (a) ipucu verilemeyen turlar merdiveni ilerletiyordu, (b) arama sorgusu öğrencinin denemesiydi ("hı", "sadece söyle") — artık oturumun açılış sorusu. İkisinin de regresyon testi var.
- [x] T028 [D] YENİ: `apps/api/tests/test_socratic.py` — (1) ilk turda cevap verilmez, (2) deneme olmadan kademe atlanmaz, (3) kaynaksız hint bloklanır, (4) ısrarcı öğrenci senaryosunda şablon ipucuna düşülür, (5) state kalıcıdır (oturum yeniden yüklense de kademe korunur). **DONE (2026-08-09):** 42 test, DB'siz, ~2,6 sn. Beş vakanın tamamı + Türkçe i/İ tuzağı ("SADECE SÖYLE" ile "sadece soyle" aynı sınıfa düşüyor), bozuk durumun onarımı, geçiş geçmişinin sınırsız büyümemesi. Israrcı öğrenci iki okumasıyla da test edildi: cevap dayatması (üretim hiç çağrılmıyor) ve filtrenin ısrarla ihlali (bir regen sonrası şablon).
- [x] T029 [D] YENİ: `apps/api/app/modules/assessment/question_gen.py` — içerikten 4 tip soru üretimi (mcq/open/code_trace/bug_hunt), Pydantic JSON şemalı çıktı + 1 retry, `source_chunk_id` zorunlu, üretilen her soru `status=draft` (eğitmen onayı olmadan yayınlanmaz). MCQ'da distractor'lar için kaynak eşlemesi payload'a yazılır ("neden yanlış" T031'in girdisi). **DONE (2026-08-09):** üretim `StructuredCompletion` + `Retriever` protokollerine karşı yazıldı; `source_chunk_id` set-membership'ten geçmeyen soru havuza yazılmaz, `distractor_sources` modelden istenmeyip retrieve edilmiş kümeden örtüşmeyle eşlenir. Şerit 1/2 inene kadar uç 503 döner (sahte soru üretilmez).
- [x] T030 [D] YENİ: `apps/api/app/api/questions.py` — eğitmen uçları: konu yönetimi `POST/GET /courses/{course_id}/topics` (FR-027; soru üretimi ve mastery bu uca bağımlı), `POST /courses/{course_id}/questions/generate` (topic + tip + adet), `GET` listeleme (statü filtreli), `PATCH .../approve|reject`; öğrenci yalnız approved görür. `main.py` + `openapi.json` güncellenir. **DONE (2026-08-09):** generate/list/approve/reject eklendi (`PATCH` yerine `POST` — 04_SORU_SINAV.md ile hizalı). Öğrenciye `status` sunucuda `approved`'a sabit; payload beyaz listeden geçer, cevap anahtarı sızmaz.
- [x] T031 [D] YENİ: `apps/api/app/modules/assessment/grading.py` — MCQ: deterministik puanlama + distractor→source_chunk eşlemesiyle "neden yanlış?" (çelişen sayfa gösterilir); open/code_trace/bug_hunt: cevap anahtarı + kaynak chunk'larla şemalı LLM değerlendirme `{score: 0-100, eksik_noktalar[], dayanak_chunk_id}`; `dayanak_chunk_id` set-membership kontrolünden geçer (T013 ile tutarlı). Kod ASLA çalıştırılmaz. **DONE (2026-08-09):** MCQ ve kısa cevap deterministik (LLM'siz de çalışır); açık uçlu/kod yolu şemalı + 1 retry + set-membership'li dayanak, iki denemede de bozuksa uydurma puan yerine 'tamamlanamadı'. Kod hiçbir aşamada çalıştırılmaz.
- [x] T032 [D] YENİ: `apps/api/app/api/exams.py` — `POST /courses/{course_id}/exams` oturum başlat (mode practice|exam; exam: süreli, tek deneme, hint kapalı, geri bildirim sınav sonunda; süre ve soru sayısı MVP'de config sabitlerinden gelir — eğitmen ayarı P1; bağlantı kopmasında oturuma kalan süreyle devam edilir; onaylı soru havuzu boşsa oturum başlatılamaz), `POST .../answers` cevap gönder, `POST .../finish` bitir → puan + soru bazlı geri bildirim. `main.py` + `openapi.json` güncellenir. **DONE (2026-08-09):** süre veritabanı saatinden ve `min(expires_at, started_at + süre)` ile kırpılarak; soru başına tek deneme; exam'de ipucu 403; boş havuzda 409; puan `answers`'tan türetilir. Cevap satırı write-once (KARARLAR_SERIT4.md Karar 1).
- [x] T033 [D] YENİ: `apps/api/tests/test_assessment.py` — (1) soru üretimi şema geçerliliği (bozuk LLM çıktısı retry sonrası reddedilir), (2) draft soru öğrenci uçlarından görünmez, (3) exam modunda hint isteği reddedilir, (4) süre dolunca cevap kabul edilmez ve cevaplanmamış sorular boş sayılır (puana katılmaz), (5) MCQ "neden yanlış" doğru distractor kaynağını döndürür, (6) boş onaylı havuzda sınav başlatma reddedilir, (7) oturuma dönüşte kalan süre korunur, (8) practice modda ipucu açık + anında geri bildirim. **DONE (2026-08-09):** sekiz vakanın tamamı + fazlası; `test_exams.py` eklendi. Vaka 2 için `questions_read` bilerek bozulup testin kırmızı yandığı ve uygulama katmanının tek başına tuttuğu ayrı ayrı gösterildi (KARARLAR_SERIT4.md §RLS kanıtı).
- [ ] T034 [D] `apps/web/app/courses/[courseId]/exam/page.tsx` — gerçek veriye geçiş: sınav başlatma, süre sayacı, MCQ + açık uçlu cevap formu, sonuç ekranında puan + "neden yanlış?" dayanak sayfasıyla; `apps/web/lib/types.ts`/`api.ts`'e sınav tipleri eklenir.
- [ ] T035 [D] `apps/web/components/socratic-ladder.tsx` chat sayfasında gerçek state'e bağlanır (kademe göstergesi backend state'inden) VE YENİ: `apps/web/app/courses/[courseId]/questions/page.tsx` — eğitmen soru onay paneli (düz tablo; PLAN §4 "basitleştirilebilir" listesine uygun minimal biçim) + panel içinde minimal konu ekleme formu (T030 topics ucuna bağlanır).

**Kapanış kabul kriteri**: Tarayıcıda tam döngü: eğitmen soru üretir → onaylar → öğrenci sınava girer → puan + "neden yanlış" + eksik_noktalar görür; Sokratik modda cevap sızmadığı davranış testleriyle yeşil (G9 çıktısı).

---

## Faz E: Mastery-Lite + eğitmen analitiği (PLAN G9-G10)

- [x] T036 [E] YENİ: `apps/api/app/modules/mastery/service.py` — konu bazlı EWMA: `yeni = 0.7×eski + 0.3×son_skor`; ipucu kademesi çarpanları (0→1.00, 1→0.85, 2→0.70, 3→0.50, 4→0.25); seviye eşikleri (<0.40 Geliştirilmeli, 0.40-0.74 Orta, ≥0.75 İyi). Sadeleştirme gerekçesi (BKT/IRT verisi yok) modül docstring'ine yazılır.
- [x] T037 [E] Sınav bitişi ve Sokratik oturum kapanışına mastery güncelleme entegrasyonu — `apps/api/app/api/exams.py` (grading sonrası) ve `apps/api/app/api/chat.py` (ipucu kademesi çarpanıyla) `mastery` tablosunu günceller. **SAHİPLİK NOTU: exams.py entegrasyonu R3'ün; chat.py'deki Sokratik-kapanış çağrısı R1'e devredilir (R3, arayüz imzasını R1'e yazılı verir) — çapraz düzenleme yok.** **DONE (2026-08-09, exams.py ayağı):** practice modda ilk cevapta, exam modunda bitişte `mastery.record_answer` çağrılır (ipucu çarpanıyla). chat.py ayağı R1'de: imza `record_answer(session, *, user_id, topic_id, course_id, raw_score, hint_level, alpha)`.
- [x] T038 [E] YENİ: `apps/api/app/api/analytics.py` — öğrenci: konu bazlı mastery listesi; eğitmen: konu bazlı sınıf ortalaması, en çok yanlış yapılan sorular, kapsam dışı ret istatistiği (`request_logs`/`chat_messages`'tan). `main.py` + `openapi.json` güncellenir. **DONE (2026-08-09):** iki uç — `/analytics/me` (öğrenci) ve `/analytics/class` (eğitmen); yetki yol düzeyinde CourseMemberDep/CourseInstructorDep ile. Çalışılmamış konu listeye girmez (0.0 skor uydurulmaz), en çok yanlış yapılan sorularda payda da döner, kapsam dışı ret oranı `chat_messages` yokken `source: unavailable` + `rate: null` döner. 11 test; openapi.json güncellendi.
- [x] T039 [P] [E] YENİ: `apps/api/tests/test_mastery.py` — EWMA hesabı, ipucu çarpanları, seviye sınır değerleri (0.40 ve 0.75 tam sınırda), ilk cevapta başlangıç davranışı. **DONE (2026-08-06):** `record_answer()` imzası hazır, R1'e chat.py entegrasyonu için verilecek.
- [ ] T040 [E] YENİ: `apps/web/app/courses/[courseId]/analytics/page.tsx` — eğitmen özet ekranı (tek kart sayfası) + öğrenci mastery liste görünümü; arayüzde "resmî not değil, çalışma önerisi göstergesidir" ibaresi (ARCHITECTURE §5, KVKK notu); nav bağlantısı `apps/web/components/course-nav.tsx`'e eklenir.

**Kapanış kabul kriteri**: Sınav çözümünden sonra mastery değişimi UI'da gözlenir; eğitmen özeti tek sayfada; testler yeşil (G10 özellik dondurma öncesi son özellik).

---

## Faz F: Eval altyapısı ve ölçüm (PLAN G11-G12)

**Amaç**: Gold set (kalibrasyon/holdout AYRIK), otomatik eval harness, kalibrasyon, baseline-vs-hybrid ve A/B koşuları. Anayasa III: çalıştırılmayan deney için sonuç yazılmaz.

- [x] T041 [F] YENİ: `evaluation/gold_set/calibration.json` (~15 soru) + `evaluation/gold_set/holdout.json` — toplam ≥50: 20 doğrudan, 10 çok-chunk, 10 teknik terim/kod, 10 kapsam dışı, ≥15 injection (doküman içi talimat, rol değiştirme, dil değiştirme, encode edilmiş talimat aileleri), ≥5 kod inceleme, Sokratik sızıntı senaryoları (fence'siz kod, pseudocode, sözel çözüm, ısrarcı öğrenci). Format: `{id, question, category, expected_chunk_ids|expected_behavior}`. Sorular ders materyali sahibi eğitmenin gözden geçirmesine sunulur. **DONE (2026-08-09):** kalibrasyon 15, holdout 76 soru (20 direct, 10 multi_chunk, 10 technical_term, 10 out_of_scope, 15 injection, 5 code_review, 6 socratic_leak). `verify_gold_set.py` üç şeyi makineyle denetliyor: yapısal bütünlük, kalibrasyon-holdout ayrıklığı, her expected_sources girdisinin materyalde ve gerçek korpusta karşılığı. Doğrulayıcının kırmızı yanabildiği bozuk kopyayla sınandı. İçerik ve eğitmen doğrulaması BEKLİYOR (dosyaların `verification` bloğunda işaretli).
- [x] T042 [F] YENİ: `evaluation/evaluate.py` — metrikler: Recall@5 VE Recall@8, MRR, citation precision, ret F1; rate-limit farkındalıklı kuyruk + sonuç cache'i + ayrı eval API anahtarı (config: `EVAL_LLM_API_KEY`); gece koşacak CLI (`--set holdout --mode hybrid|dense`); sonuçlar YENİ: `evaluation/results/` altına tarihli JSON. **DONE (2026-08-09):** `--set/--layer/--mode/--dry-run` çalışıyor; meta veri bloğu (git SHA, embedding sağlayıcısı, retrieval parametreleri, eşiğin kalibre olup olmadığı) zorunlu. Devam dosyası + sonuç cache'i aynı jsonl; ayar değişince parmak izi değişir. 429'da üstel geri çekilme testli. Metrik tanımları `evaluation/metrics.py`'de saf fonksiyon, `apps/api/tests/test_eval_metrics.py`'de sabit (37 test). Arka uçlar (Şerit 1/3) inmeyince sessizce boş sonuç değil, nereye bakıldığını yazan hata veriyor. EVAL_LLM_API_KEY şimdilik ortamdan okunuyor — Settings'e alınması config.py'ye dokunmak demek, gruba istek olarak `evaluation/README.md`'de.
- [x] T043 [F] Evidence eşiği kalibrasyonu — `evaluation/evaluate.py --set calibration` ile `evidence_threshold` ayarlanır; seçilen değer + gerekçe YENİ: `evaluation/calibration_notes.md`'ye; holdout'a BAKILMAZ (Anayasa III). Kapsam dışı ret oranı sonra holdout'ta raporlanır. **DONE (2026-08-09):** seçilen değer **0.81** (kalibrasyon setinde iki sınıfın ayrıştığı 0.0054 genişliğindeki aralığın orta noktası); gerekçe, tarama tablosu ve "holdout'a bakılmadı" beyanı `evaluation/calibration.md`'de. İki bulgu: (1) `config.py`'deki 0.35 ATIL — ölçülen hiçbir skor 0.76 altına inmiyor, eşik hiç tetiklenmiyor; (2) kalibrasyondaki ayrışma holdout'ta TUTMADI, 0.81'de doğru ret %80 (hedef %90). Eşik holdout'a bakılarak değiştirilmedi. Değeri Şerit 1 güncelleyecek.
- [x] T044 [F] Baseline (dense-only) vs hybrid (dense+FTS+RRF) koşusu — aynı holdout, eşleştirilmiş anlamlılık (bootstrap veya McNemar, en azından güven aralığı); "n=50 — yön göstergesi" kaydıyla sonuç `evaluation/results/`'a. **DONE (2026-08-09):** aynı holdout, aynı config, fastembed korpusu. Recall@5/@8 iki kolda da 1.000 — ama korpus 33 chunk ve top_k=8, yani bu ölçüt doygun; rapora bu uyarıyla girdi. Ayırt eden MRR: dense 0.774 → hibrit 0.893, fark +0.119, %95 GA [+0.054, +0.191], sıfırı dışlıyor. Tam kapsama@8'de fark yok (GA sıfırı içeriyor, McNemar p=1.00). "n=45 — yön göstergesi" kaydı düşüldü.
- [ ] T045 [P] [F] Embedding A/B — multilingual-e5-large vs bge-m3, ≥40 soru, Recall@5 + MRR; bge-m3 için geçici indeks (karar ingest-zamanıdır, üretim indeksi değişmez); sonuç "embedding seçim gerekçesi" başlığının verisi olur. **DURUM (2026-08-09):** KOŞULMADI. `build_corpus.py --database` ile ayrı veritabanında A/B kurulabiliyor; üretim indeksi değişmiyor.
- [ ] T046 [F] Injection + Sokratik sızıntı koşusu — ≥15 injection vakası ve sızıntı senaryoları guardrail zincirinden geçirilir; sızıntı/ihlal oranı kaydedilir; rapor dili "bilinen temel kalıplara karşı smoke-test edildi" düzeyinde tutulur ("dayanıklı" DENMEZ). **DURUM (2026-08-09):** KOŞULMADI. Vakalar hazır: holdout'ta 15 injection (kalıp aileleri etiketli) + 6 Sokratik sızıntı senaryosu. R2'nin `evaluation/injection/cases.json` dosyası inince `r2_case_ref` alanları doldurulup listeler birleştirilecek. Harness açık ihlalleri işaretliyor ve kalanları `<run_id>.review.md`'ye döküyor; işaretlenmemek ihlal olmadığını kanıtlamaz.
- [ ] T047 [F] Faithfulness örneklemi — 20-30 gerçek cevap çekilir, YENİ: `evaluation/faithfulness/sample_template.md` etiketleme şablonu; 2 kişi bağımsız etiketler, uyum oranı kaydedilir. **DURUM (2026-08-09):** şablon hazır (`evaluation/faithfulness/sample_template.md`): 2 bağımsız etiketleyici, ham uyum çözüm öncesi hâliyle, örneklem sabit tohumlu. Uyum hesabı `metrics.label_agreement` ile testli. Örneklem KOŞULMADI — gerçek cevap üretilmedi.

**Kapanış kabul kriteri**: Tüm holdout metrikleri üretilmiş ve `evaluation/results/` altında; kalibrasyon-holdout ayrımı dosya düzeyinde kanıtlanabilir; PLAN §5 tablosundaki her satır için ya ölçüm var ya "koşulmadı" notu.

---

## Faz G: Deploy + demo sertleştirme (PLAN G13-G14)

- [ ] T048 [G] `apps/api/Dockerfile` — multilingual-e5-large ONNX (int8 quantize) modeli build aşamasında indirilip imaja GÖMÜLÜR (`EMBEDDING_CACHE_DIR` imaj içi; çalışma zamanında HuggingFace'e bağımlılık yok); `.github/workflows/ci.yml`'e "network'süz konteyner ayağa kalkıyor ve embed üretebiliyor" assertion adımı; replika başına RSS ölçülüp not edilir (ACA ≤ 2 vCPU / 4 GiB).
- [ ] T049 [G] Worker'ın HTTP tetiği — YENİ: `apps/api/app/api/internal.py` korumalı `POST /internal/drain` ucu (paylaşılan secret ile); `apps/api/app/api/documents.py::_trigger_worker` ortama göre in-process `worker.drain()` (lokal) veya worker servisine HTTP çağrısı (bulut) seçer. KARAR: tek Docker imajı, iki ayrı Container App (api: uvicorn komutu, worker: `python -m app.worker` komutu) — ARCHITECTURE §2 ile uyumlu; IaC/deploy betiği bu görevde yazılır.
- [ ] T050 [G] Prod ortam doğrulaması — migration'lar (0002-0004) prod Supabase'de koşulur; Vercel'de `NEXT_PUBLIC_API_URL` + Supabase anahtarları; ACA'da CORS ve `DEV_AUTH_ENABLED=false` (config'in production'da dev-auth'u reddettiği gerçek ortamda test edilir); LLM failover canlı testi: Groq anahtarı bilerek bozulur → Gemini'ye otomatik geçiş gözlemlenir ve geri alınır. NOT: PLAN G1'deki "hello world üçlü deploy" fiilen YAPILMADI (yalnız yerel geliştirme kuruldu); ilk gerçek bulut deploy'u T049-T050'dir ve Faz G beklenmeden öne alınabilir.
- [ ] T051 [G] RLS canlılık kanıtı prod'da — `supabase/tests/rls_isolation.sql` prod kopya/branch üzerinde koşulur; bir policy bilerek bozulur → izolasyon testinin KIRMIZI yandığı görülür → geri alınır; çıktı ekran kaydı/log olarak saklanır (T056 test raporunun girdisi). **YERELDE DONE (2026-08-09) — kutu AÇIK, görev metni prod koşusu istiyor:** `supabase/tests/rls_isolation.sql` 8 iddiadan **98 iddiaya** çıkarıldı — 0001'in 15, 0003'ün 9 politikası + politikası bilinçli olmayan 13 işlem, her politikaya en az bir olumlu ve bir olumsuz iddia. YENİ: `supabase/tests/rls_isolation_mutation_check.sh` — her politikayı teker teker bozup HANGİ iddianın kırmızıya döndüğünü doğruluyor: **52/52 yakalandı** (4'ü yardımcı fonksiyon mutasyonu). Komut: `psql -d dou_synapse -f supabase/tests/rls_isolation.sql` + `supabase/tests/rls_isolation_mutation_check.sh`. İkinci katman ayrıca sınandı: YENİ `apps/api/tests/test_isolation_layers.py` (8 test) API'yi BYPASSRLS rolüne çevirip uygulama katmanının tek başına tuttuğunu, aynı konfigürasyonda veritabanının gerçekten sızdırdığını ölçüyor. PROD KOPYA ÜZERİNDE KOŞULMADI — gerçek Supabase projesi yok.
- [ ] T052 [P] [G] YENİ: `.github/workflows/keepalive.yml` — günlük cron: Supabase'e hafif sorgu + API `/health/ready` ping'i (free-tier pause önlemi; teslim-jüri arası çalışır).
- [ ] T053 [G] YENİ: `apps/api/scripts/fill_answer_cache.py` — demo senaryosu soruları `answer_cache` tablosuna önceden doldurulur (exact-match; offline sigortası). Cache girdileri elle yazılmaz: script gerçek chat pipeline'ını (T019) çağırır, guardrail zincirinden geçmiş yanıtı saklar. Derse belge eklendiğinde/silindiğinde o dersin cache satırları temizlenir (ingestion pipeline'ına hook). Demo soru listesi YENİ: `apps/api/scripts/demo_questions.json`.
- [ ] T054 [G] Yedek + restore provası — `pg_dump` + Storage yedeği alınır; `docker-compose.yml` fallback profiline restore edilip dev-auth + `answer_cache` ile TAM OFFLINE akış (Wi-Fi kapalı) en az 1 kez prova edilir; adımlar T057 runbook'una yazılır.
- [ ] T055 [G] Cold-start ölçümü + demo günü ayarı — scale-to-zero'dan uyanma süresi ölçülür; sıcak replikada sorgu yolu p95 ölçülür (<10 sn hedefi yalnız sıcak replika için); demo/prova günleri `minReplicas=1` prosedürü nota bağlanır.

**Kapanış kabul kriteri**: Canlı URL'de tam demo yolu çalışır; DEV_AUTH prod'da kapalı olduğu kanıtlı; RLS kanıtı ve failover kaydı alınmış; en az 1 tam offline prova yapılmış; p95 + cold-start sayıları ölçülmüş.

---

## Faz H: Belgeler ve teslim (PLAN G12-G15)

- [ ] T056 [H] YENİ: `docs/test-report.md` — başarı testi raporu: holdout metrikleri (PLAN §5 tablosu birebir), baseline vs hybrid + anlamlılık kaydı, guardrail/sızıntı sonuçları, injection smoke-test sonucu, faithfulness örneklemi + etiketleyici uyumu, embedding seçim gerekçesi (T045), RLS canlılık kanıtı (T051), p95 + cold-start (T055); her sonuçta "n=50 — yön göstergesi, kesin hüküm değil" kaydı. **DURUM (2026-08-09):** taslak yazıldı (`docs/test-report.md`). PLAN §5 tablosunun her satırında ya ölçülmüş sayı ya KOŞULMADI var. Bugün ölçülü olanlar: RLS kanıtı (8+53 iddia, 21/21 mutasyon), sample_data ingesti (8/8 completed, 33 chunk), 140 test yeşil.
- [ ] T057 [P] [H] YENİ: `docs/runbook.md` — demo günü A/B/C planı (A: canlı bulut minReplicas=1 + sabah warm-up + önceden açık oturumlar; B: telefon hotspot; C: Compose + dev-auth + answer_cache), hesap listesi, prova kontrol listesi, restore adımları (T054).
- [ ] T058 [P] [H] YENİ: `docs/instructor-guide.md` — ders açma, materyal yükleme + n/m ilerleme, soru üretimi ve onayı, sınav yayınlama, analitik ekranı; ekran görüntülü, rol bazlı.
- [ ] T059 [P] [H] YENİ: `docs/student-guide.md` — derse katılım, kaynaklı sohbet, Sokratik mod, sınav provası, "neden yanlış?", mastery görünümü; ekran görüntülü.
- [ ] T060 [H] Teslim kapanışı — kök `README.md` güncellenir (canlı URL, `docker compose up` kurulumu, teslim paketi haritası); KVKK aydınlatma metni sayfası YENİ: `apps/web/app/privacy/page.tsx` (sohbet kayıtları saklama notu); sürüm etiketi `v1.0.0` + son demo provası (G15). **(KVKK/privacy sayfası ayağı R4'ündür.)**

**Kapanış kabul kriteri**: Hocanın 3 teslim kalemi eksiksiz karşılanır: (1) canlı URL + Compose kurulum, (2) `sample_data/` + `docs/test-report.md`, (3) iki kılavuz; repo `v1.0.0` etiketli.

---

## Bağımlılıklar ve Yürütme Sırası

### Faz bağımlılıkları

- **Faz A**: hemen başlayabilir (G1-G4 çıktıları üzerine kurulur). T002 (materyal) yalnız kapanış kriterini bloklar; T001 salt doğrulamadır, kimseyi bloklamaz.
- **Faz B**: T003-T006'dan bağımsız başlayabilir (mock retrieval ile — PLAN G4 notu "LLM+citation işi mock retrieval üzerinde paralel başlar"). T008 → T009 → T012 sıralı; T010, T014, T015 paralel.
- **Faz C**: A + B'nin tamamına bağımlı (pipeline'ı birleştirir). T017 → T018 → T019 sıralı.
- **Faz D**: C'ye bağımlı (chat altyapısı + LLM servisi). T024 → T025 → sonrası; T029-T033 backend, T034-T035 frontend.
- **Faz E**: D'ye bağımlı (sınav sonuçları mastery'nin girdisi).
- **Faz F**: T041 (gold set) H1'den beri birikmeli — hemen başlayabilir ve A-E ile paralel yürür; T042-T047 ise C'nin (gerçek pipeline) tamamlanmasını bekler. T043 (kalibrasyon) T044'ten önce.
- **Faz G**: T048-T049 C'den sonra başlayabilir; T050-T055 özellik dondurma (G10) sonrası. T053 chat API'ye (T019), T054 T053'e bağlı.
- **Faz H**: T056 Faz F+G çıktılarına bağlı; T057-T059 G12'den itibaren paralel yazılabilir; T060 en son.

### Paralel fırsatlar

- Faz A içinde: T002 (materyal) ve T004 (FTS) diğerleriyle paralel.
- Faz B, Faz A'nın T003-T006'sı ile ekip düzeyinde paralel (Backend/RAG lead ↔ Guardrail&QA rolleri, PLAN §4).
- T041 (gold set, Data&Eval rolü) tüm fazlarla paralel — günde 5-8 soru birikimi sürer.
- Faz H'nin kılavuzları (T057-T059) Faz G ile paralel yazılır.

### Takvim eşlemesi (PLAN §3)

| Faz | Günler | Sert kapı |
|---|---|---|
| A + B (dense yol) + C (v0) | G5-G6 | **G5: uçtan uca kaynaklı cevap kapısı** |
| A (hybrid) + D (Sokratik) | G7 | — |
| B (leakage) + D (soru üretici) | G8 | — |
| D (sınav) + E (mastery backend) | G9 | — |
| E (ekranlar) + frontend kapama | G10 | **G10: özellik dondurma** |
| F | G11-G12 | — |
| G | G13-G14 | — |
| H | G12-G15 | G15: teslim |

---

## Görev Sayısı Özeti

| Faz | Görev | Aralık |
|---|---|---|
| A. Retrieval hattı | 7 | T001-T007 |
| B. Generation + guardrails | 9 | T008-T016 |
| C. Chat API + frontend | 7 | T017-T023 |
| D. Sokratik + sınav | 12 | T024-T035 |
| E. Mastery + analitik | 5 | T036-T040 |
| F. Eval altyapısı | 7 | T041-T047 |
| G. Deploy + sertleştirme | 8 | T048-T055 |
| H. Belgeler + teslim | 5 | T056-T060 |
| **Toplam** | **60** | |

## Notlar

- Bu dosya tek iş listesi kaynağıdır (Anayasa, Geliştirme İş Akışı). Her görev kendi conventional commit'iyle kapanır ve tamamlanınca tarihli **DONE** notu düşülür; Co-Authored-By izleri asla eklenmez (Anayasa IX).
- [P] işaretleri dosya düzeyi bağımsızlığı gösterir; rol dağılımı PLAN §4'tedir.
- Anayasa VIII: UI görevi tarayıcıda görülmeden, API görevi gerçek istekle sınanmadan "bitti" sayılmaz.
- Yeni uç ekleyen her görev (T019, T030, T032, T038) `specs/001-course-assistant-mvp/contracts/openapi.json` sözleşmesini aynı commit'te günceller — sözleşme ile kod ayrışmaz.
- G10 (17 Ağu) özellik dondurmasından sonra yalnız düzeltme + bayrak arkasında P1 (reranker `ENABLE_RERANKER`, RAGAS, SSE) — bu listede P1 görevi YOKTUR, bilinçli.
- Deploy fazındaki iki belirsizlik karara bağlandı (T049: tek imaj + iki Container App; T050: ilk gerçek deploy Faz G'dedir, G1'de bulut deploy yapılmamıştı).
