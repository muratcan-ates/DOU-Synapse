# DOU-Synapse — Mimari Kararlar ve Teknik Tasarım

Bu belge 9 araştırma raporunun çeliştiği her noktada verilen **nihai** kararları, gerekçelerini
ve 4 mercekli adversaryal denetimden çıkan düzeltmeleri içerir. Plan/takvim: [PLAN.md](PLAN.md)

---

## 1. Nihai Teknoloji Yığını

| Katman | Karar | Elenen alternatifler ve neden |
|---|---|---|
| Frontend | **Next.js (App Router) + TypeScript + Tailwind + shadcn/ui**, Vercel | Streamlit (ürün hissi zayıf; ekipte gerçek Next.js tecrübesi var), Django+HTMX (ekip React biliyor) |
| Backend | **FastAPI (Python)** | Django (ekip uyumu), Node backend (RAG ekosistemi Python'da) |
| Veritabanı + Vektör | **Supabase PostgreSQL + pgvector** (tek veritabanı). Geliştirme de Supabase'in kendisinde (veya `supabase` CLI lokal stack) — Compose'daki düz Postgres yalnızca fallback | Qdrant/FAISS/Chroma (ikinci veri deposu = senkron + yetki sızıntı riski), Azure AI Search ($73+/ay), iki ayrı dev/prod DB (migration/RLS sapması) |
| Auth + Storage | **Supabase Auth + Storage** | Sıfırdan JWT/upload yazmak |
| Doküman işleme | **PyMuPDF + python-pptx + düz parser**; Docling sorunlu dosyalara fallback | Docling ana parser (H1 entegrasyon riski) |
| Embedding | **`intfloat/multilingual-e5-large` (1024 boyut), ONNX/fastembed, model Docker imajına GÖMÜLÜ** — çalışma zamanında HuggingFace'e bağımlılık yok. **`EMBEDDING_PROVIDER` ingest-zamanı kararıdır: değiştirmek tam re-index gerektirir, runtime'da çevrilmez** | bge-m3 (fastembed dense kataloğunda yok — bkz. aşağıdaki not); İngilizce-odaklı embedding (TR materyalde çöker); API-only (per-query maliyet + offline demo imkânsız) |
| Sparse arama | **PostgreSQL FTS, `simple` + `unaccent` konfigürasyonu** (köklendirme yok → `fork()`, `O(n log n)` gibi teknik tokenlar korunur); turkish/english konfigürasyonlarıyla gold set üzerinde karşılaştırılıp raporlanır | turkish snowball (İngilizce terimleri bozar), english (Türkçe ekleri bozar) |
| Füzyon | **Reciprocal Rank Fusion** (k=60) | Öğrenilmiş fusion (veri yok), skor normalizasyonu (kırılgan) |
| Reranker | **P1, bayrak arkasında** (bge-reranker-v2-m3) | Ana hatta zorunlu (latency + deployment riski) |
| LLM | **LiteLLM Router: Groq (Llama) → Gemini Flash OTOMATİK failover + retry/backoff** (kod seviyesinde; manuel anahtar değişimi değil). Failover H2'de bilerek Groq anahtarı bozularak test edilir | Tek sağlayıcı; yerel LLM hosting (GPU/cold-start) |
| Yapılandırılmış çıktı | **Pydantic şema + server-side validasyon + 1 retry** | Sağlayıcıya özel structured-output'a tam güven |
| Orkestrasyon | **Düz Python servis kodu + açık state machine** | LangChain/LlamaIndex/LangGraph (debug şeffaflığı) |
| Arka plan işleri | **Postgres job tablosu (`FOR UPDATE SKIP LOCKED`) + HTTP-tetiklemeli worker**: upload handler 202 döndükten sonra worker'ın `/drain` endpoint'ini çağırır → ACA HTTP scale-to-zero doğal çalışır. (Alternatif: KEDA PostgreSQL scaler) | Sürekli poll eden worker (scale-to-zero ile çelişir: ya hiç sıfıra inmez ve free tier'ı yer, ya iner ve job'lar asılı kalır), Redis+Celery |
| Deploy | **Vercel + Azure Container Apps + Supabase, G1'den itibaren sürekli deploy** — kapılar canlı URL'de geçilir. Demo/prova günleri api+worker **minReplicas=1** (parametrik). Docker Compose lokal/fallback | Son haftada ilk deploy (CORS/JWT/cold-start sürprizleri teslime 2 gün kala), tek VM, K8s |
| CI | **GitHub Actions**: ruff + pytest + tsc + docker build (+ "model imaj içinde, konteyner network'süz ayağa kalkıyor" assertion'ı) | — |
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

```
profiles            (id→auth.users, full_name, role: instructor|student)
courses             (id, code, title, instructor_id)
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
                     payload jsonb, source_chunk_id, status: draft|approved|rejected)
exam_sessions       (id, user_id, course_id, mode: practice|exam, started_at, ...)
answers             (id, session_id, question_id, given, is_correct,
                     feedback jsonb: {score, eksik_noktalar[], dayanak_chunk_id})
mastery             (user_id, topic_id, score float, updated_at)
answer_cache        (course_id, question_hash, response jsonb)   -- exact-match demo cache (P0)
chat_sessions / chat_messages (mode: qa|socratic, state, citations jsonb)
request_logs        (redaction'lı; latency, status, course_id, token_count)
```

Kurallar:
- `chunks.course_id` **denormalize** — filtre JOIN'e bağlı kalmaz.
- Bir chunk **iki sayfayı birleştirmez**; 400–600 token, ~%15 overlap; kod dosyaları
  fonksiyon/sınıf sınırından bölünür.
- `file_hash` ile tekrar embed engellenir. Günlük token tüketimi loglanır (kota bütçesi).

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
1. AuthZ        JWT doğrula → user_id → course_memberships kontrolü
                (course_id İSTEMCİDEN ASLA güvenilmez; backend belirler)
2. Retrieval    dense top-20 (pgvector) ∥ FTS top-20  →  RRF  →  top-8
                her sorguda zorunlu WHERE course_id = :authorized_course_id
3. Evidence     en iyi sonuç eşik altındaysa → ABSTAIN
   gate         Eşik KALİBRASYON setiyle ayarlanır (G6); ret oranı HOLDOUT sette raporlanır
                — kalibrasyon ve test verisi asla karışmaz.
4. Generation   context XML etiketli (<source id page>); çıktı Pydantic şemasına valide (1 retry)
5. Citation     cevaptaki chunk_id'ler ⊆ retrieve edilen küme mi? (set-membership: deterministik)
   validator    Değilse temizle; geçerli citation kalmadıysa CEVAP GÖSTERİLMEZ (fail-closed).
                Dosya adı + sayfa, model metninden DEĞİL chunk metadata'sından üretilir.
                NOT: Bu kontrol atıf uydurmayı engeller; iddia-kaynak tutarlılığını (faithfulness)
                garanti ETMEZ — o ayrıca örneklem üzerinde ölçülür (§7).
6. Pedagojik    (Sokratik/sınav modunda) kod bloğu + doğrudan-çözüm dedektörü (kural tabanlı:
   filtre       fence, girinti deseni, "cevap: X" kalıpları) → ihlalde 1 regen (stokastik);
                yine ihlalse ŞABLON İPUCUNA DÜŞ (fail-closed, deterministik son durak).
                Kalıp dışı sızıntı (pseudocode, sözel çözüm) MİTİGASYONDUR, garanti değil —
                test seti bu vakaları içerir ve sızıntı oranı raporlanır.
7. Sanitize     Markdown/HTML temizliği (XSS) → gönder + event log
```

### Cevap şeması

```json
{
  "status": "answered | insufficient_context | out_of_scope",
  "mode": "qa | socratic | exam",
  "answer": "...",
  "citations": [{"chunk_id": "…", "claim": "…"}],
  "hints": [{"text": "…", "chunk_id": "…"}]
}
```
- Backend `chunk_id` → `{file_name, page_number, snippet}` eşlemesini kendisi yapar.
- **İpuçları da retrieve edilmiş chunk'lardan türetilir, `chunk_id` taşır ve evidence-gate'ten
  geçer** — hocanın "her yanıtta kaynak" şartı hint'leri de kapsar; davranış testlerinde
  "kaynaksız hint" senaryosu vardır.

### Sokratik state machine (backend'de tutulur)

```
DIAGNOSE → NUDGE → CONCEPT_HINT → SIMILAR_EXAMPLE → EXPLAIN_WITH_SOURCE
```
Öğrenci denemesi olmadan ilerlenmez; her kademe event olarak loglanır. Mod politikaları
backend'de: `exam` → hint kapalı, tek deneme, geri bildirim sınav sonunda.

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
yeni_puan = 0.7 × eski_puan + 0.3 × son_cevap_skoru          (konu bazında EWMA)
İpucu kademesi çarpanları: 0→1.00 · 1→0.85 · 2→0.70 · 3→0.50 · 4→0.25
Seviye eşikleri: <0.40 Geliştirilmeli · 0.40-0.74 Orta · ≥0.75 İyi
```
**Gerekçe (raporda aynen savunulur):** Bu bilinçli bir sadeleştirmedir. BKT/IRT gibi yerleşik
öğrenci modelleri parametre kestirimi için bizde olmayan öğrenci verisi gerektirir; EWMA,
yakın geçmişe ağırlık veren üstel unutma modellerine kaba bir yaklaşımdır. 0.7/0.3 duyarlılık
notuyla raporlanır. Çıktı **resmî not değil çalışma önerisi göstergesidir** (human-in-the-loop);
arayüzde bu ibare yer alır. Eğitmen ekranı: konu bazlı sınıf ortalaması, en çok yanlış
yapılan sorular, ret istatistiği (tek sayfa).

---

## 6. Güvenlik

- **İzolasyon çift katman — ama dürüst kurulumla:** backend'de zorunlu `course_id` filtresi +
  Postgres RLS. RLS'in gerçekten tetiklenmesi için backend **anon key + kullanıcı JWT'sini
  geçirir** (service-role ile RLS sessizce bypass olur ve testler sahte yeşil yanar).
  Service-role yalnızca worker'ın iç işlerinde. G13 testi: **policy bilerek bozulur, izolasyon
  testinin KIRMIZI yandığı görülür** — RLS'in canlı olduğunun kanıtı raporda yer alır.
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

### Demo günü runbook (özet)

A planı: canlı bulut (minReplicas=1, sabah warm-up + önceden açık oturumlar).
B planı: telefon hotspot + aynı canlı bulut.
C planı (tam offline): Compose + dev-auth bypass (seed'li oturum) + demo senaryosu cevapları
`answer_cache`'ten (LLM'siz senaryolu akış; sınırları sunumda dürüstçe söylenir).
En az bir prova Wi-Fi kapalı yapılır.

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
├── evaluation/                 # gold_set/ (calibration.json, holdout.json), evaluate.py
├── sample_data/                # İşletim Sistemleri paketi (G3'te v1)
├── docs/                       # test-report, instructor-guide, student-guide, runbook
├── supabase/                   # migrations, RLS policies, seed
├── .github/workflows/ci.yml    # ruff+pytest+tsc+docker build+model-gömülü assertion
├── docker-compose.yml          # web+api+worker+pgvector-postgres+dev-auth (fallback profili)
└── .env.example
```

---

## 9. v2 Vizyonu (teslim sonrası)

- Eğitmen onaylı dış kaynak katmanı (çift renkli citation) — hocanın kısıtıyla çelişmeyen biçimde
- Parent-child chunking + reranker varsayılan açık; RAGAS sürekli eval
- Sınıf düzeyi kavram yanılgısı kümeleme panosu; Langfuse; LMS entegrasyonu
- Ölçek büyürse (1M+ chunk) Qdrant'a geçiş yolu
```
