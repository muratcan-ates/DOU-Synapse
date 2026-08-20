# DOU-Synapse — Mimari Kararlar ve Teknik Tasarım

Bu belge 9 araştırma raporunun çeliştiği her noktada verilen **nihai** kararları, gerekçelerini
ve 4 mercekli adversaryal denetimden çıkan düzeltmeleri içerir. Plan/takvim: [PLAN.md](PLAN.md)

> **Kodla hizalama — 9 Ağustos 2026 (R5), beş şerit birleştikten sonra tazelendi.**
> Bu belge 9 Ağustos'tan önce yazıldı ve o gün sistem epey değişti. Kodla satır satır
> karşılaştırılıp hizalandı; şeritler birleşince §5 ve §10 yeniden ölçülüp güncellendi.
> Hizalama kuralı: **belge koda uydurulur, kod belgeye değil.** Tasarlanmış ama
> uygulanmamış her karar, silinmek yerine [§10 Uygulanmayanlar](#10-uygulanmayanlar--tasarlandı-kodda-yok)
> bölümünde açıkça "uygulanmadı" olarak listelenir; sessizce duran bir iddia yalandır
> (Anayasa III).

---

## 1. Nihai Teknoloji Yığını

| Katman | Karar | Elenen alternatifler ve neden |
|---|---|---|
| Frontend | **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui**, Vercel | Streamlit (ürün hissi zayıf; ekipte gerçek Next.js tecrübesi var), Django+HTMX (ekip React biliyor) |
| Backend | **FastAPI (Python)** | Django (ekip uyumu), Node backend (RAG ekosistemi Python'da) |
| Veritabanı + Vektör | **Supabase PostgreSQL + pgvector** (tek veritabanı). Geliştirme de Supabase'in kendisinde (veya `supabase` CLI lokal stack) — Compose'daki düz Postgres yalnızca fallback | Qdrant/FAISS/Chroma (ikinci veri deposu = senkron + yetki sızıntı riski), Azure AI Search ($73+/ay), iki ayrı dev/prod DB (migration/RLS sapması) |
| Auth + Storage | **Supabase Auth + Storage** | Sıfırdan JWT/upload yazmak |
| Doküman işleme | **PyMuPDF + python-pptx + düz parser**; Docling sorunlu dosyalara fallback | Docling ana parser (H1 entegrasyon riski) |
| Embedding | **`intfloat/multilingual-e5-large` (1024 boyut), ONNX/fastembed.** **`EMBEDDING_PROVIDER` ingest-zamanı kararıdır: değiştirmek tam re-index gerektirir, runtime'da çevrilmez.** Modelin imaja gömülmesi **HENÜZ UYGULANMADI** (§10) | bge-m3 (fastembed dense kataloğunda yok — bkz. aşağıdaki not); İngilizce-odaklı embedding (TR materyalde çöker); API-only (per-query maliyet + offline demo imkânsız) |
| Sparse arama | **PostgreSQL FTS, `simple` + `unaccent` konfigürasyonu** (köklendirme yok → `fork()`, `O(n log n)` gibi teknik tokenlar korunur); turkish/english konfigürasyonlarıyla gold set üzerinde karşılaştırılıp raporlanır | turkish snowball (İngilizce terimleri bozar), english (Türkçe ekleri bozar) |
| Füzyon | **Reciprocal Rank Fusion** (k=60) | Öğrenilmiş fusion (veri yok), skor normalizasyonu (kırılgan) |
| Reranker | **P1, bayrak arkasında** (bge-reranker-v2-m3) | Ana hatta zorunlu (latency + deployment riski) |
| LLM | **LiteLLM Router: Groq (Llama) → Gemini Flash OTOMATİK failover + retry/backoff** (kod seviyesinde; manuel anahtar değişimi değil). Failover H2'de bilerek Groq anahtarı bozularak test edilir | Tek sağlayıcı; yerel LLM hosting (GPU/cold-start) |
| Yapılandırılmış çıktı | **Pydantic şema + server-side validasyon + 1 retry** | Sağlayıcıya özel structured-output'a tam güven |
| Orkestrasyon | **Düz Python servis kodu + açık state machine** | LangChain/LlamaIndex/LangGraph (debug şeffaflığı) |
| Arka plan işleri | **Postgres job tablosu (`FOR UPDATE SKIP LOCKED`).** Bugün çalışan tetik **süreç içidir**: upload handler 202 döndükten sonra `BackgroundTasks` ile `worker.drain()` çağrılır (`app/api/documents.py`). HTTP tetiği (`POST /internal/drain`) **UYGULANMADI** — router kayıtlı ama boş (§10) | Sürekli poll eden worker (scale-to-zero ile çelişir: ya hiç sıfıra inmez ve free tier'ı yer, ya iner ve job'lar asılı kalır), Redis+Celery |
| Deploy | **Vercel + Azure Container Apps + Supabase** hedeflenir; bugün depoda yalnız `docker-compose.yml` + `apps/api/Dockerfile` var. Bulut dağıtımı **R3'ün açık işi** (§10) | Son haftada ilk deploy (CORS/JWT/cold-start sürprizleri teslime 2 gün kala), tek VM, K8s |
| CI | **GitHub Actions**: ruff + ruff format + mypy + pytest + RLS izolasyon kanıtı (api) · lint + tsc (web) · Playwright uçtan uca. **Docker build ve "model imaj içinde" assertion'ı henüz YOK** (§10) | — |
| Gözlemleme | **Yapılandırılmış JSON log + request/hata tabloları** (redaction'lı) | Langfuse/Sentry (v2) |

### Embedding modeli: bge-m3'ten multilingual-e5-large'a

İlk tercih bge-m3'tü. Uygulama sırasında fastembed'in **dense model kataloğunda bge-m3
bulunmadığı** görüldü (yalnız seyrek/çok-vektörlü biçimde). İki seçenek vardı: ek bir
çalışma zamanı (sentence-transformers/optimum) getirmek ya da fastembed'de doğrudan
desteklenen çok dilli bir modele geçmek. `intfloat/multilingual-e5-large` seçildi:
aynı **1024 boyut** (şema değişmedi), çok dilli, tek bağımlılık.

**E5 önek kuralı (sessiz kalite kaybı riski):** E5 ailesi, belgelerin `passage: ` ve
sorguların `query: ` önekiyle verilmesini bekler. fastembed'in `query_embed()` metodu
düz `embed()`'e düşer ve bu önekleri eklemez; önek uygulama katmanında açıkça ekleniyor.
Atlanırsa hata alınmaz, yalnızca retrieval kalitesi düşer — bu yüzden davranış
`tests/test_embedding_prefix.py` ile sabitlendi.

bge-m3 kapsam dışı değil, **3. haftadaki embedding A/B karşılaştırmasının adayı**
(PLAN.md G11): multilingual-e5-large ile ≥40 soru üzerinde Recall@5 ve MRR karşılaştırılıp
sonuç test raporunda "embedding seçim gerekçesi" başlığında yayımlanacak.

**Sürüm uyuşmazlığı — AÇIK RİSK (9 Ağustos, ölçüldü).** fastembed 0.8.0 bu modeli artık
**mean pooling** ile çalıştırıyor; eski sürümler **CLS** kullanıyordu ve kütüphane bunu
yalnız bir `UserWarning` ile söylüyor. Pooling değişikliği vektör uzayını değiştirir: bir
sürümle ingest edilmiş korpusa başka bir sürümle sorgu atmak sessizce yanlış komşular
döndürür — hiçbir şey çökmez, retrieval kalitesi düşer ve bunu söyleyen bir mekanizma
yoktur. Kanıt eşiğinin sağlayıcıya göre çözülmesi bu sınıfın yalnız yarısını (sağlayıcı
uyuşmazlığı) kapatır; ikinci yarısı **sürüm**dür ve chunk başına sağlayıcı+sürüm damgası
gerektirir (R4'ün `0006` migration'ı).

Bugünkü durum ölçüldü: `dou_synapse_eval_e5` korpusuna (33 chunk) fastembed 0.8.0 ile beş
sonda sorgu atıldı; ilgili sorular 0.8130–0.8699, konu dışı sorular 0.7238–0.7587 kosinüs
aldı ve 0.81 eşiği ikisini doğru ayırdı. Yani **bu korpus-sürüm çifti bugün tutarlı**.
Bu bir nokta kontrolüdür, kalibrasyonun yeniden koşulması değildir.

### Kanıt eşiği sağlayıcıya bağlıdır

`EVIDENCE_THRESHOLD_BY_PROVIDER` (`app/core/config.py`) iki değer taşır: `fastembed` → **0.81**
(kalibre edildi, T043), `hashing` → **0.10** (kalibre edilemez, yalnız yaklaşık davranış).
Sebep yapısaldır: iki sağlayıcının kosinüs dağılımları farklı bantlarda oturur, birinde
kalibre edilmiş sayı diğerinde anlamsızdır.

Ölçülen (9 Ağustos, `hashing` ile gömülmüş korpus, COME 331): ilgili sorgular
0.1715–0.1951, konu dışı sorgu 0.1789. **Konu dışı sorgu, ilgili sorgulardan birinden
yüksek skor aldı** — yani `hashing` bu materyalde ayırt etme gücü taşımıyor. Bu sağlayıcı
test ve çevrimdışı geliştirme içindir; **demo ve ölçüm bu sağlayıcıyla koşulmaz.**

Testler `hashing`'de kalır ve bu doğrudur: kendi veritabanlarını kurup **sorguladıkları
sağlayıcıyla** ingest ederler, yani kendi içlerinde tutarlıdırlar ve model indirmezler.
Kural şudur: **bir sunucu paylaşılan korpusa bağlanıyorsa o korpusun gömüldüğü sağlayıcıyı
kullanmak zorundadır.** Uyuşmazlık çökmez; sessizce alakasız komşular döndürür.

### Deploy gerçekliği (ölçülecek ve raporlanacak)

- bge-m3 fp32 ONNX ~2.2-2.3 GB, yükleme tepe RAM 3-4 GB → **int8 quantize zorunlu**; replika
  başına ölçülmüş RSS raporlanır (ACA consumption planı ≤ 2 vCPU / 4 GiB).
- Scale-to-zero uyanması = imaj pull + model yükleme (dakikalar sürebilir) → p95 < 10 sn hedefi
  yalnızca **sıcak replika, sorgu yolu** için geçerlidir; cold-start süresi ayrıca ölçülür (G14).
- Sorgu embedding'i yalnızca API konteynerinde; worker aynı imajı paylaşır (çift ayak izi yok).
- Maliyet hedefi ~$0-15/ay; minReplicas=1 yalnızca demo/prova günleri açılır.

---

## 2. Sistem Mimarisi

```
                     ┌────────────────────────────┐
                     │  Next.js (Vercel)          │
                     │  öğrenci UI · eğitmen panel│
                     └─────────────┬──────────────┘
                                   │ HTTPS (Supabase JWT)
                                   ▼
                     ┌────────────────────────────┐
                     │  FastAPI (Azure C. Apps)   │
                     │  authz · chat · exam · api │
                     └───────┬───────────┬────────┘
                    metadata │           │ upload → job + /drain tetiği
                             ▼           ▼
              ┌──────────────────┐  ┌──────────────────┐
              │ Supabase Postgres│  │ Supabase Storage │
              │ + pgvector + RLS │  │ (private bucket) │
              └────────┬─────────┘  └────────┬─────────┘
                       │ job tablosu         │
                       └──────────┬──────────┘
                                  ▼
                     ┌────────────────────────────┐
                     │  Worker (Azure C. Apps)    │
                     │  /drain ile uyanır         │
                     │  parse → chunk → embed     │
                     └─────────────┬──────────────┘
                                   ▼
                     ┌────────────────────────────┐
                     │  LiteLLM Router            │
                     │  Groq ⇄ Gemini (otomatik)  │
                     └────────────────────────────┘
```

---

## 3. Veri Modeli (çekirdek tablolar)

Kodda gerçekten var olan 27 tablo (`supabase/migrations/0001,0002,0003,0004,0005,0006,0007,0008,0009,0010,0011,0012,0013,0014,0015,0016`): <!-- docs-check: tables.count = 27 --><!-- docs-check: migrations.list = 0001,0002,0003,0004,0005,0006,0007,0008,0009,0010,0011,0012,0013,0014,0015,0016 -->

```
profiles            (id, email, full_name, created_at)
courses             (id, code, title, created_by, created_at)
course_memberships  (user_id, course_id, role, status)
documents           (id, course_id, uploaded_by, file_name, file_type,
                     storage_path, file_hash, status: uploaded|processing|completed|failed)
chunks              (id, course_id, document_id, page_number, slide_number,
                     section_title, content_type: text|table|code, chunk_index,
                     text, embedding vector(1024), token_count)
ingestion_jobs      (id, document_id, status, attempt_count, last_error, ...)
topics              (id, course_id, name)                    -- eğitmen tanımlar
questions           (id, course_id, topic_id,
                     type: mcq|open|code_trace|bug_hunt,     -- kod inceleme = ayrı soru tipleri
                     payload jsonb, source_chunk_id, status: draft|approved|rejected,
                     created_by, reviewed_by, reviewed_at)
exam_sessions       (id, user_id, course_id, mode: practice|exam, started_at, ...)
answers             (id, session_id, question_id, given, is_correct,
                     feedback jsonb: {score, eksik_noktalar[], dayanak_chunk_id})
mastery             (user_id, topic_id, course_id, score float, answer_count, updated_at)
answer_cache        (id, course_id, question_hash, answer jsonb, created_at)
chat_sessions       (id, course_id, user_id, mode: qa|socratic|exam, state jsonb, title, ...)
chat_messages       (id, session_id, course_id, role, content, citations jsonb,
                     status, socratic_stage, seq, created_at)
request_logs        (id, course_id, user_id, route, mode, status, http_status,
                     latency_ms, token_count, cache_hit, created_at)
```

Kurallar:
- `chunks.course_id` **denormalize** — filtre JOIN'e bağlı kalmaz.
- Bir chunk **iki sayfayı birleştirmez**; 400–600 token, ~%15 overlap; kod dosyaları
  fonksiyon/sınıf sınırından bölünür.
- `file_hash` ile tekrar embed engellenir.

Belgenin eski hâlinden düzeltilen dört ad/alan (kod kaynak alındı):

| Eski belge | Kodda | Neden önemli |
|---|---|---|
| `profiles.role: instructor\|student` | **yok** | Sistem geneli rol yoktur; yetki daima ders bazlıdır (`course_memberships.role`). Global rol sütunu, iki katmanlı izolasyonu delen bir kestirme olurdu |
| `courses.instructor_id` | `courses.created_by` | Dersin eğitmeni üyelik tablosundan gelir; dersin tek bir "sahibi" alanı yok |
| `answer_cache.response` | `answer_cache.answer` | — |
| `mastery(user_id, topic_id, score)` | `+ course_id, answer_count` | `answer_count` "kaç cevaba dayanıyor" sorusunu cevaplar; tek cevaptan çıkan bir seviye rozetini gösterirken bu bilinmeli |

**Migration numaraları:** `0002` R1'e (Supabase Auth köprüsü), `0006` R4'e, `0007` R3'e
ayrılmıştır ve bugün depoda yoktur. Bu yüzden numaralar `0001, 0003, 0004, 0005` diye
atlamalı gider — eksik dosya değil, ayrılmış numaradır.

---

## 4. Ingestion Pipeline

```
Upload (tür+boyut+magic byte, UUID ad, private bucket)
  → documents (uploaded) + ingestion_jobs (pending) → 202 → worker /drain tetiklenir
Worker: job al (FOR UPDATE SKIP LOCKED) → indir → türe göre parser
  PDF: PyMuPDF (sayfa bazlı) · PPTX: python-pptx (slayt) · MD: başlık hiyerarşili · kod: fonksiyon sınırlı
  → chunk + metadata → bge-m3 batch embed → pgvector → completed
Hata: attempt_count++, last_error; 3 denemede failed → UI'da anlaşılır mesaj
UI: chunk-bazlı ilerleme (n/m) — uzun ingestion "takıldı" gibi görünmez
```

Demo notu: canlı yükleme gösterimi için 5-10 sayfalık küçük PDF kullanılır (süresi provada
ölçülür); büyük materyal önceden işlenmiş seed olarak durur.

---

## 5. Sorgu Pipeline'ı ve Guardrail Zinciri

Sıralama kritiktir; her adım bir güvenlik sınırıdır:

```
0. Sınırlar     soru uzunluğu ≤ 2000 karakter · kullanıcı+ders başına 20 istek / 60 sn
                (süreç içi kayan pencere — çok worker'lı koşuda worker başına uygulanır)
1. AuthZ        Bearer token → user_id → course_memberships kontrolü (CourseMemberDep)
                (course_id İSTEMCİDEN ASLA güvenilmez; backend belirler)
2. Önbellek     birebir eşleşme, YALNIZ qa modunda: sha256(mode + normalize edilmiş soru).
                İsabette LLM'e hiç gidilmez. Benzerlik tabanlı eşleşme YOKTUR.
3. Retrieval    dense top-24 (pgvector) ∥ FTS top-24  →  RRF (k=60)  →  top-8
                her sorguda zorunlu WHERE course_id = :authorized_course_id
4. Evidence     en iyi parçanın DENSE skoru eşik altındaysa → ABSTAIN, LLM HİÇ ÇAĞRILMAZ.
   gate         Eşik sağlayıcıya bağlıdır (fastembed 0.81 · hashing 0.10) ve kalibrasyon
                setiyle ayarlanmıştır; holdout'ta doğrulanmadı (§7, evaluation/calibration.md).
                Eşik füzyon skoruna UYGULANAMAZ: RRF sıralamadan üretilir, üst sınırı ~0.033'tür.
                Kapı reddi TEK ETİKETE düşürmez: `retrieval/scope.assess_evidence` sözlüksel
                örtüşmeye bakıp `out_of_scope` ile `insufficient_context` arasında seçer.
5. Generation   context XML etiketli (<source id file location>); çıktı Pydantic şemasına
                valide (1 retry, sonra abstention)
6. Citation     cevaptaki chunk_id'ler ⊆ retrieve edilen küme mi? (set-membership: deterministik)
   validator    Değilse temizle; geçerli citation kalmadıysa CEVAP GÖSTERİLMEZ (fail-closed).
                Dosya adı + sayfa, model metninden DEĞİL chunk metadata'sından üretilir.
                NOT: Bu kontrol atıf uydurmayı engeller; iddia-kaynak tutarlılığını (faithfulness)
                garanti ETMEZ — o ayrıca örneklem üzerinde ölçülür (§7).
7. Pedagojik    (Sokratik/sınav modunda) kod bloğu + doğrudan-çözüm dedektörü (kural tabanlı:
   filtre       fence, girinti deseni, "cevap: X" kalıpları) → ihlalde 1 regen (stokastik);
                yine ihlalse ŞABLON İPUCUNA DÜŞ (fail-closed, deterministik son durak).
                Kalıp dışı sızıntı (pseudocode, sözel çözüm) MİTİGASYONDUR, garanti değil —
                test seti bu vakaları içerir ve sızıntı oranı raporlanır.
8. Sanitize     Markdown/HTML temizliği (XSS)
9. Kayıt        chat_messages + oturum durumu + request_logs (soru METNİ yazılmaz)
```

Zincirin sırası (`citation → leakage → sanitize`) **tek yerde** sabittir:
`modules/guardrails/chain.py:GUARDRAIL_CHAIN`. Çağıranlar halkaları kendileri dizmez.

### İki orkestratör var ve üretimde biri koşuyor

Bu, belgenin kodla ayrıştığı en önemli nokta ve bilerek kayda geçiriliyor:

| | `api/chat.py::produce_answer` | `modules/guardrails/chain.py::AnswerPipeline` |
|---|---|---|
| Kim çağırıyor | **canlı sohbet ucu** | yalnız testler (`test_guardrails.py`, `test_generation.py`) |
| Sızıntıda yeniden üretim | var, ama **aynı parametrelerle** | var, `strict_retry=True` ile |
| Şablon son durak | `assessment.socratic.template_hint` | `leakage.build_template_hint` |
| Bloklanan cevabın metni | `chat.py:MESSAGE_BLOCKED` | `generation.service.USER_TEXT[...]` |

Yani `AnswerPipeline`'ın `strict_retry` yolu ve `USER_TEXT` sabitleri **üretimde hiç
koşmuyor**. Davranış her iki yolda da fail-closed olduğu için bu bir güvenlik açığı
değildir, ama Anayasa XI ihlalidir: aynı iş iki yerde yazılı ve ikisi şimdiden ayrışmış.
Tekilleştirme R4'e iletildi.

### Cevap şeması (istemciye dönen zarf — `app/schemas/chat.py:ChatResponse`)

```json
{
  "session_id": "…", "message_id": "…",
  "status": "answered | insufficient_context | out_of_scope",
  "mode": "qa | socratic | exam",
  "answer": "...",
  "citations": [{"chunk_id": "…", "claim": "…",
                 "file_name": "…", "location": "Sayfa 7", "snippet": "…"}],
  "hints": [{"text": "…", "chunk_id": "…",
             "file_name": "…", "location": "…", "stage": "nudge"}],
  "socratic_stage": "diagnose | nudge | concept_hint | similar_example | explain_with_source",
  "cached": false
}
```

- Backend `chunk_id` → `{file_name, location, snippet}` eşlemesini kendisi yapar; bu üç alan
  chunk metadata'sından gelir, model metninden değil.
- `session_id`/`message_id` opsiyonel DEĞİLDİR: istemci bir sonraki turu aynı oturuma bağlamak
  zorundadır ve oturum kimliğini uyduramaz.
- `cached` alanı ölçüm içindir: bir cevabın önbellekten mi geldiği raporlanabilmeli.
- **`claim` alanı `contracts.Citation`'da bilinçli olarak YOKTUR.** `contracts.py` guardrail
  zincirinin sözleşmesidir ve **hiçbir guardrail kararı `claim`'e bakmaz**; o bir sunum
  verisidir. Sözleşmeye konsaydı, hiçbir kontrolün okumadığı bir alanı üç modül birden
  doldurmak zorunda kalırdı. Zarf katmanında (`schemas/chat.py`, `to_chat_response(claims=…)`)
  taşınır. Üreteci olan uygulamalar `ClaimingGenerator` protokolünü uygular.
- **`hints[]` dizisi zarfta VARDIR ve Sokratik turda dolar** ama `answer`'ı tekrarlamaz:
  `to_chat_response` ipucunu yalnız `socratic + answered + atıflı` turlarda üretir ve ipucunun
  kaynağı cevabın kaynağıyla **aynı kümedir** — tek atıf kümesi, tek doğrulama. Hocanın "her
  yanıtta kaynak" şartı ipuçlarını da kapsar.
- Sağlayıcı/model adı zarfta **dışarı verilmez** (altyapı ayrıntısı kullanıcıya gitmez);
  ölçüm için `GeneratedAnswer` üzerinde taşınır.

### İki ret, tek kapı — ölçülen davranış

Zarf üç statü tanımlar ve üçü de canlı yolda üretilebilir. Bu **9 Ağustos akşamına kadar
böyle değildi:** kanıt kapısı eşiğin altındaki her sorguyu tek bir etikete
(`insufficient_context`) düşürüyordu, çünkü `out_of_scope`'u yalnız LLM üretebiliyordu ve
kapı LLM'den önce kapanıyordu. Sonuç, eğitmen analitiğindeki kapsam dışı ret oranının
**yapısal olarak %0** ölçülmesiydi (SC-005). Bulgu R5'in koşusundan çıktı ve
`modules/retrieval/scope.py` ile kapatıldı.

Bugün ayrım **kapının kendi içinde**, ölçülmüş ikinci bir sinyalle (sözlüksel örtüşme)
yapılıyor: `assess_evidence()` bir `EvidenceLevel` döndürür, uç de onun `refusal_status`
alanını kullanır. **Cevaplanan küme değişmedi** — "yeterli kanıt" koşulu eskisiyle birebir
aynı; değişen yalnız reddin nasıl etiketlendiği.

Ölçülen (9 Ağustos akşamı, COME 331, fastembed):

| Soru | Statü |
|---|---|
| İtalya'nın başkenti neresidir? | `out_of_scope` |
| Bugün hava nasıl? | `out_of_scope` |
| Fenerbahçe dün kaç attı? | `out_of_scope` |
| Bugünkü dolar kuru ne kadar? | `insufficient_context` |
| En iyi pizza tarifi nedir? | `insufficient_context` |
| Osmanlı Devleti ne zaman kuruldu? | `insufficient_context` |
| Python'da liste nasıl sıralanır? | `answered` (3 atıf — derste `producer_consumer.py` var) |

**Sınır, dürüstçe:** ayrım mükemmel değil. Yukarıdaki üç `insufficient_context` sorusu
insan gözüyle de kapsam dışıdır; sözlüksel örtüşme sinyali onları yakalamıyor. Yani
kapsam dışı ret oranı artık **ölçülebilir**, ama **eksik sayıyor** — gerçek oran
raporlanandan yüksektir. Bu, hiç ölçememekten iyidir ve sayı bu kaydıyla birlikte
kullanılmalıdır.

Kullanıcıya dönen metinler de ayrışır: `out_of_scope` için *"Bu soru dersin kapsamı
dışında görünüyor"*, `insufficient_context` için *"Bu soruya ders materyalinde yeterli
dayanak bulamadım"*. İkisi de nötr bir bildirimle gösterilir, hata rengiyle değil
(Anayasa VII).

### Sokratik state machine (backend'de tutulur)

```
DIAGNOSE → NUDGE → CONCEPT_HINT → SIMILAR_EXAMPLE → EXPLAIN_WITH_SOURCE
```

Öğrenci denemesi olmadan ilerlenmez; her kademe geçişi hem oturum `state` jsonb'sine hem
yapılandırılmış loga yazılır. `ChatRequest`'te `socratic_stage` alanı **bilinçli olarak
yoktur**: kademe kararı sunucudadır, istemci seçebilseydi öğrenci tek istekle
`EXPLAIN_WITH_SOURCE` isteyip merdiveni atlardı.

İki incelik kodda var, belgede yoktu:

- **Arama, turun metniyle değil OTURUMUN AÇILIŞ SORUSUYLA yapılır.** Sokratik turlarda
  öğrencinin yazdığı bir denemedir ("hı", "sanırım dört koşul"), soru değil; onunla arama
  yapılırsa hiçbir parça bulunmaz ve merdiven kanıt eşiğine takılıp çöker. Canlı koşuda
  birebir bu gözlendi.
- **Kademe yalnız gerçekten ipucu servis edildiyse ilerler.** Kanıt eşiği aşılamadıysa
  kullanıcı hiçbir yardım almamıştır; o turu ilerleme saymak öğrenciyi hiç görmediği bir
  kademeye taşırdı.

Israrcı öğrenci yolu (ölçüldü, 9 Ağustos): deneme yapılmadan "sadece söyle" denirse üretim
**hiç çalıştırılmaz**; kullanıcı nazik uyarıyı ve AYNI kademenin deterministik şablon
ipucunu alır. Merdiven ilerlemez, kaynak yine taşınır, LLM bütçesi ısrarla tüketilemez.

Mod politikaları backend'de:

| | ipucu | geri bildirim |
|---|---|---|
| `practice` sınav | **açık** (`POST /exams/{id}/hint`, kademe mastery çarpanına girer) | anında |
| `exam` sınav | **kapalı** — `hint` ucu reddeder, `hint_level > 0` reddedilir | sınav sonunda |
| sohbet `exam` modu | **kapalı** — `POST /chat` `exam` modunu hiç kabul etmez (422) | — |
| **yürüyen `exam` oturumu** | **asistanın tamamı kapalı** — `POST /chat` (her mod), `GET /chat/sessions` ve geçmiş okuma 403 döner (`api/deps.py::require_assistant_unlocked`) | — |

Son satır 002'de eklendi ve yukarıdakilerden farklı bir eksende çalışıyor. İlk üçü
**mod** politikasıdır: istemcinin ne istediğine bakar. Sonuncusu **durum**
politikasıdır: öğrencinin o anda sınav verip vermediğine bakar. Ayrım gerekliydi
çünkü mod ekseni tek başına delinebiliyordu — öğrenci sınavı başlatıp ikinci
sekmede `mode=qa` ile sınav sorusunun tam, atıflı cevabını alabiliyordu.

Kilidin üç sınırı, üçü de bilinçli:

- **Ders bazlıdır.** A dersinde sınav veren öğrenci B dersinin asistanını
  kullanabilir. Kilidin amacı o sınavın bütünlüğü, öğrencinin gününü kapatmak
  değil.
- **Yürüyen oturuma bağlıdır, bitmemiş oturuma değil.** Süresi dolmuş ama
  kapatılmamış oturum kilitlemez; aksi hâlde sınav sekmesini kapatıp giden bir
  öğrenci asistanını kalıcı olarak kaybederdi.
- **Yalnız değerlendirilene uygulanır.** Kendi dersinde oturum açan eğitmen muaf;
  muafiyet sunucuda ve sorgudan önce.

### Açık uçlu cevap değerlendirme (hocanın "eksiği söyle" gereksinimi)

```
Öğrenci cevabı + cevap anahtarı + kaynak chunk'lar → LLM değerlendirici
→ Pydantic şema: {score: 0-100, eksik_noktalar: [...], dayanak_chunk_id}
→ dayanak_chunk_id set-membership kontrolünden geçer (guardrail felsefesiyle tutarlı)
→ "Neden yanlış?": MCQ'da distractor→source_chunk eşlemesi (deterministik, birincil yol);
   açık uçluda eksik_noktalar + dayanak sayfası gösterilir
```
Kod inceleme: `code_trace` (verilen kodun çıktısını tahmin et) ve `bug_hunt` (hatayı bul)
soru tipleri; kod asla çalıştırılmaz, değerlendirme cevap anahtarına karşı yapılır.

### Mastery-Lite ("çalışma performans göstergesi")

```
yeni_puan = (1 - α) × eski_puan + α × son_cevap_skoru        (konu bazında EWMA, α = 0.3)
İpucu kademesi çarpanları: 0→1.00 · 1→0.85 · 2→0.70 · 3→0.50 · 4→0.25
Seviye eşikleri: <0.40 Geliştirilmeli · 0.40-0.74 Orta · ≥0.75 İyi
```

α tek yerde: `Settings.mastery_alpha = 0.3`. Kademe sayısı `Settings.socratic_max_stage = 4`.
**Gerekçe (raporda aynen savunulur):** Bu bilinçli bir sadeleştirmedir. BKT/IRT gibi yerleşik
öğrenci modelleri parametre kestirimi için bizde olmayan öğrenci verisi gerektirir; EWMA,
yakın geçmişe ağırlık veren üstel unutma modellerine kaba bir yaklaşımdır. 0.7/0.3 duyarlılık
notuyla raporlanır. Çıktı **resmî not değil çalışma önerisi göstergesidir** (human-in-the-loop);
arayüzde bu ibare yer alır. Eğitmen ekranı: konu bazlı sınıf ortalaması, en çok yanlış
yapılan sorular, ret istatistiği (tek sayfa).

---

## 6. Güvenlik

- **İzolasyon çift katman — ama dürüst kurulumla:** backend'de zorunlu üyelik doğrulaması
  (`CourseMemberDep`/`CourseInstructorDep`) + Postgres RLS. Bugünkü kurulumda API,
  **tabloların sahibi olmayan ve `BYPASSRLS` taşımayan `dou_app` rolüyle** bağlanır; oturum
  başına `app.user_id` ayarlanır ve politikalar bu değere bakar. Worker ayrı bir rolle
  (`dou_worker`, `BYPASSRLS`) bağlanır çünkü `chunks` tablosuna kullanıcı bağlamı olmadan
  yazar. 27 tablonun tamamı `ENABLE` + **`FORCE ROW LEVEL SECURITY`** ile işaretlidir, yani <!-- docs-check: tables.count = 27 -->
  tablo sahibi bile politikalara tabidir.
  **Testler de `dou_app` ile koşar** — superuser ile koşan bir izolasyon testi her zaman
  yeşil yanar ve hiçbir şey kanıtlamaz. CI her koşuda `supabase/tests/rls_isolation.sql`
  çalıştırır.
  Erişimi olmayan derste **404 döner, 403 değil**: 403, üye olunmayan bir dersin var
  olduğunu sızdırırdı.
- **Compose yığınında RLS DEVREDE DEĞİLDİR.** `docker-compose.yml` API'yi `postgres`
  (superuser) rolüyle bağlar; superuser `FORCE` işaretine rağmen RLS'i atlar. Bu yığın
  yerel/çevrimdışı fallback içindir ve **izolasyon kanıtı bu yığında alınamaz**. Düzeltme
  R3'e iletildi (§10).
- **Upload:** uzantı beyaz listesi + MIME + magic byte; 20 MB; UUID yeniden adlandırma;
  worker'da zaman/bellek sınırı (zip-bomb/dev PDF).
- **Indirect prompt injection:** belge metni `<retrieved_context>` içinde veri olarak
  işaretlenir; talimat kalıpları ingestion'da etiketlenir. Test seti ≥15 vakayla kalıp
  ailelerini kapsar (doküman içi talimat, rol değiştirme, dil değiştirme, encode edilmiş
  talimat); raporda iddia **"bilinen temel kalıplara karşı smoke-test edildi"** düzeyinde
  tutulur — "injection'a dayanıklı" DENMEZ.
- **Secrets:** yalnızca backend env; repo'da `.env.example`; loglarda key/TCKN/e-posta redaction.
- **Rate limiting + token sınırı:** kullanıcı başına istek limiti; girdi karakter sınırı;
  günlük token bütçesi loglanır.
- **Yedekleme/süreklilik:** G14'te pg_dump + storage yedeği ve Compose'a restore provası
  (offline fallback'in veri kaynağı da budur); teslim-jüri arası **günlük keep-alive ping**
  (Supabase free-tier pause önlemi); demo sabahı tüm hesaplarla önceden login.
- **KVKK notu:** sohbet kayıtları saklama süresi + aydınlatma metni sayfası; mastery çıktısı
  "öneri"dir (human-in-the-loop).

### İşlem sınırı: `SessionDep` `scope="function"`

Veritabanı oturumu `Depends(get_session, scope="function")` ile bağlanır. Varsayılan
(`scope="request"`) kapsamda FastAPI, yanıtı istemciye yazdıktan SONRA commit eder;
istemcinin hemen yaptığı ikinci istek işlemi henüz görmez. Ölçülen kusur: `POST /documents`
`202` dönüyor, hemen ardındaki `GET` **0 belge** görüyordu.

Yan etkisi belgeye giriyor çünkü davranışı değiştiriyor: **yükleme ucunun arka plan worker
tetiği artık gerçekten çalışıyor** (önceden boş kuyruk görüp sessizce sıfır dönüyordu).
`BackgroundTasks` hâlâ yanıttan sonra koşar ve bu doğrudur — worker tetiği kullanıcıyı
bekletmemeli; öne alınan yalnız veritabanı işlemidir.

### Demo günü runbook

Üç plan ve geçiş ölçütleri artık ayrı bir belgededir: **[docs/runbook.md](docs/runbook.md)**.
Sahne sahne anlatım: **[docs/demo-script.md](docs/demo-script.md)**.

---

## 7. Değerlendirme Tasarımı

**Gold set (≥50 soru, H1'den itibaren günde 5-8 soru biriktirilir; G11'de temizlik):**
20 doğrudan · 10 çok-chunk · 10 teknik terim/kod · 10 kapsam dışı · ≥15 injection ·
≥5 kod inceleme (code_trace/bug_hunt) · Sokratik sızıntı senaryoları (fence'siz kod,
pseudocode, sözel çözüm, ısrarcı öğrenci, jailbek kalıpları).

**Metodoloji (jüriye karşı savunma hattı):**
- Set **kalibrasyon (~15) / holdout (kalan)** olarak ayrılır; eşikler kalibrasyonla ayarlanır,
  **rapor yalnızca holdout metriklerini** yayınlar.
- Gold set soruları ders materyalinin sahibi eğitmenin gözden geçirmesine sunulur
  ("kendi sınavını kendin yazmışsın" eleştirisine karşı).
- Yargı gerektiren etiketlerde (faithfulness, açık uçlu) 2 kişi bağımsız etiketler,
  uyum oranı raporlanır.
- Baseline (dense-only) vs hybrid+RRF: aynı holdout, eşleştirilmiş anlamlılık testi
  (bootstrap/McNemar) veya en azından güven aralığı; "n=50 — yön göstergesi" kaydı düşülür.
- Embedding seçimi: bge-m3 vs multilingual-e5 (vs API) A/B'si ≥40 soruyla, Recall@5+MRR;
  sonuç "embedding seçim gerekçesi" başlığıyla raporlanır.
- Metrikler: Recall@5 **ve** Recall@8 (üretim k=8; @5 literatür karşılaştırması), MRR,
  citation precision, ret F1, faithfulness (manuel örneklem 20-30 cevap), p95 (sıcak replika).
- Eval harness: rate-limit farkındalıklı kuyruk + sonuç cache'i + ayrı API anahtarı; gece
  koşacak şekilde planlanır (demo arifesinde kota yakmamak için).

---

## 8. Depo Yapısı

```
DOU-Synapse/
├── apps/
│   ├── web/                    # Next.js
│   └── api/                    # FastAPI
│       └── app/
│           ├── api/            # auth, courses, documents, chat, exams, analytics
│           ├── modules/        # ingestion/ retrieval/ generation/ guardrails/
│           │                   # assessment/ mastery/
│           ├── models/ schemas/ core/
│           └── worker.py       # /drain ile tetiklenen job consumer
├── evaluation/                 # gold_set/, calibration.md, evaluate.py, results/
├── sample_data/                # İşletim Sistemleri paketi (sayılar README'de)
├── docs/                       # runbook, demo-script, instructor-guide, student-guide,
│                               # kvkk, test-report, security, deployment, images/
├── supabase/                   # migrations/ (numaraları §3'te), tests/ (RLS kanıtı),
│                               # local_dev_setup.sql, seed_demo.sql
├── .github/workflows/ci.yml    # api: ruff+format+mypy+pytest+RLS · web: lint+tsc · e2e
├── docker-compose.yml          # db (pgvector:pg16) + api — fallback profili, web YOK
└── .env.example
```

`docker-compose.yml` bir **iki servisli** yığındır: frontend Compose'da değildir, `bun` ile
ayrıca çalıştırılır. Worker da ayrı servis değildir; yükleme sonrası tetik API sürecinin
içinde koşar.

---

## 9. v2 Vizyonu (teslim sonrası)

- Eğitmen onaylı dış kaynak katmanı (çift renkli citation) — hocanın kısıtıyla çelişmeyen biçimde
- Parent-child chunking + reranker varsayılan açık; RAGAS sürekli eval
- Sınıf düzeyi kavram yanılgısı kümeleme panosu; Langfuse; LMS entegrasyonu
- Ölçek büyürse (1M+ chunk) Qdrant'a geçiş yolu

---

## 10. Uygulanmayanlar — tasarlandı, kodda yok

Bu bölüm 9 Ağustos 2026'da kod okunarak çıkarıldı. Bir karar burada listeliyse **bugün
çalışmıyor** demektir. Silinmiyorlar çünkü karar hâlâ geçerli; yalnız durumları dürüst
yazılıyor (Anayasa III).

| # | Tasarlanan | Bugünkü durum | Sahibi |
|---|---|---|---|
| 1 | Embedding modeli **Docker imajına gömülü**, runtime'da HuggingFace bağımlılığı yok | **Uygulanmadı.** `apps/api/Dockerfile` yalnız "ileride gömülecek" notu taşıyor. Model çalışma zamanında indiriliyor ve macOS'ta `$TMPDIR/fastembed_cache` altına (2,1 GB) düşüyor — bu dizini işletim sistemi temizler | R3 |
| 2 | CI'da **"model imaj içinde, konteyner ağsız ayağa kalkıyor"** assertion'ı | **Uygulanmadı.** CI'da docker build işi yok | R3 |
| 3 | **HTTP-tetiklemeli worker** (`POST /internal/drain`), ACA scale-to-zero ile uyumlu | **Uygulanmadı.** Router kayıtlı ama boş; `worker_drain_secret` ayarı hazır. Bugün çalışan tetik süreç içi `BackgroundTasks` | R3 |
| 4 | **Vercel + Azure Container Apps + Supabase** canlı dağıtım | **Uygulanmadı.** Depoda yalnız Compose + Dockerfile var; canlı URL yok | R3 |
| 5 | **Supabase Auth** ile gerçek kimlik | **Kısmen.** Köprü migration'ı indi (`0002_supabase_auth_bridge.sql`, `auth` şeması varsa koşullu kurulur) ve JWT doğrulama kodu var; ama yerel/demo kurulum hâlâ `DEV_AUTH_ENABLED=true` ve imzasız `Bearer dev:<uuid>` ile koşuyor | R1 |
| 6 | **Supabase Storage** (private bucket) | **Uygulanmadı.** Yerel dosya sistemi deposu (`STORAGE_ROOT`) kullanılıyor | R3 |
| 7 | Kanıt eşiğinin **holdout'ta hedefi tutturması** (kapsam dışı doğru ret ≥ %90) | **Tutturulmadı.** Ölçülen %80. Eşik holdout'a bakılarak DEĞİŞTİRİLMEDİ; gerekçe `evaluation/calibration.md` §7 | R2 / R4 |
| 8 | Chunk başına **embedding sağlayıcı + sürüm damgası** | ✅ **KAPANDI** — `0006_embedding_provenance.sql`. `chunks.embedding_space` sütunu; ölçülen değer `fastembed/intfloat/multilingual-e5-large@0.8.0` | R4 |
| 9 | `AnswerPipeline`'ın **tekilleştirilmesi** — üretim yolu kendi kopyasını koşuyor (§5) | **Uygulanmadı.** İki orkestratör yan yana duruyor | R4 |
| 10 | Compose yığınında **RLS'in devrede olması** | **Uygulanmadı.** `postgres` superuser'ı ile bağlanılıyor, RLS atlanıyor (§6) | R3 |
| 11 | Sahte LLM sağlayıcısının **soru üretimini** desteklemesi | ✅ **KAPANDI.** Ölçüldü: anahtarsız ortamda 3 soru istendi, **3'ü de üretildi ve şemadan geçti.** Çevrimdışı demoda soru üretimi artık gösterilebilir | R4 |
| 12 | Reranker (`ENABLE_RERANKER`), RAGAS, streaming (SSE) | **Uygulanmadı** — P1, bilinçli olarak dondurma sonrasına bırakıldı | — |

**Şeritler birleştikten sonra kapananlar** (bu belgenin ilk hizalamasında açıktı):

- Soru havuzu, sınav provası ve ilerleme/analitik ekranları **bağlandı**; hiçbirinde
  önizleme şeridi kalmadı. Bu belgenin ilk sürümü üçünü de "arka ucu var, ekranı yok"
  diye kaydediyordu.
- Kanıt kapısının kapsam dışı ile dayanaksızı ayırmaması **düzeldi** (§5).
- KVKK aydınlatma metni **sayfa oldu** (`apps/web/app/kvkk`), `docs/kvkk.md`'yi okuyarak.

Bildirilen **üç bayat yorumdan ikisi düzeltildi**; biri duruyor:

- `app/api/chat.py::_opening_question` — "öğrencinin son denemesi üretime geçirilemiyor
  çünkü `contracts.Generator.generate` imzasında böyle bir alan yok" diyor;
  `student_attempt` alanı imzada var ve uç onu geçiriyor. **Hâlâ yanlış.**

Bu dosya bu şeridin sahipliğinde değil; gruba iletildi.
