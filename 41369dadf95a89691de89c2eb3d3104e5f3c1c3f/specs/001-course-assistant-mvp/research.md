# Research — Course Assistant MVP (001)

**Kaynak:** 9 derin araştırma raporu + 4 mercekli adversaryal denetim (4-5 Ağustos 2026).
Bu belge, [ARCHITECTURE.md](../../ARCHITECTURE.md) §1 karar tablosunun ve "Embedding modeli" /
"Deploy gerçekliği" bölümlerinin spec-kit formatına dökülmüş halidir. Raporların çeliştiği her
noktada tek karar verildi; aşağıda her karar Decision / Rationale / Alternatives considered
yapısıyla kayıtlıdır. Plan ve takvim: [PLAN.md](../../PLAN.md).

---

## 1. Frontend çatısı

**Decision:** Next.js (App Router) + TypeScript + Tailwind + shadcn/ui, Vercel'de.

**Rationale:** Ekipte gerçek Next.js/React tecrübesi var; "çalışır web platformu" tesliminde
ürün hissi (eğitmen paneli + öğrenci UI, rol bazlı ekranlar) önemli. Vercel ile G1'den itibaren
sürekli deploy mümkün.

**Alternatives considered:**
- *Streamlit* — prototip hızlı ama ürün hissi zayıf; çok ekranlı rol bazlı UI'da (eğitmen
  onay paneli, sınav modu, analitik) sınırlayıcı. Ekip zaten React biliyorken kazancı yok.
- *Django + HTMX* — ekip React biliyor; ayrı bir şablon ekosistemi öğrenmek 15 iş günlük
  takvimde gereksiz risk.

---

## 2. Vektör deposu

**Decision:** Supabase PostgreSQL + pgvector — tek veritabanı; `chunks.embedding vector(1024)`.

**Rationale:** İkinci bir veri deposu, iki sistem arasında senkron ve **yetki sızıntısı**
riski demek: ders bazlı mutlak izolasyon (P0 #4) Postgres RLS + `course_id` filtresiyle tek
yerde uygulanır. MVP ölçeğinde (tek üniversite dersi, on binlerce chunk) pgvector yeterli;
metadata + vektör aynı transactionda yaşar.

**Alternatives considered:**
- *Qdrant / FAISS / Chroma* — ayrı depo = RLS dışında kalan bir yüzey + senkron kodu +
  ek operasyon. Ölçek büyürse (1M+ chunk) Qdrant'a geçiş yolu v2 vizyonunda saklı.
- *Azure AI Search* — $73+/ay; maliyet hedefi ~$0-15/ay ile uyumsuz.
- *İki ayrı dev/prod DB* — migration/RLS sapması riski; geliştirme de Supabase'te
  (veya `supabase` CLI lokal stack), Compose'daki düz Postgres yalnızca fallback.

---

## 3. Doküman ayrıştırma

**Decision:** PyMuPDF (PDF, sayfa bazlı) + python-pptx (slayt) + düz parser'lar (Markdown
başlık hiyerarşili, kod fonksiyon sınırlı); Docling yalnızca sorunlu dosyalara fallback.

**Rationale:** Hocanın "her yanıtta slayt/sayfa referansı" şartı, sayfa/slayt metadata'sını
kayıpsız taşıyan hafif parser'larla karşılanır. PyMuPDF hızlı ve H1'e sığar; Docling'i ana
parser yapmak H1'de entegrasyon riski taşır.

**Alternatives considered:**
- *Docling ana parser* — daha güçlü layout analizi ama ağır bağımlılık ve H1 entegrasyon
  riski; "PDF ayrıştırma bozuk" riskinin geri dönüşü olarak fallback konumunda tutuldu
  (PLAN.md §6).

---

## 4. Embedding modeli

**Decision:** `intfloat/multilingual-e5-large` (1024 boyut), ONNX/fastembed, model Docker
imajına gömülü. `EMBEDDING_PROVIDER` ingest-zamanı kararıdır: değiştirmek tam re-index
gerektirir, runtime'da çevrilmez.

**Rationale:** İlk tercih bge-m3'tü; uygulama sırasında fastembed'in **dense model
kataloğunda bge-m3'ün bulunmadığı** görüldü (yalnız seyrek/çok-vektörlü biçimde). Ek bir
çalışma zamanı (sentence-transformers/optimum) getirmek yerine fastembed'de doğrudan
desteklenen çok dilli modele geçildi: aynı 1024 boyut (şema değişmedi), çok dilli, tek
bağımlılık. Model imaja gömülü olduğundan çalışma zamanında HuggingFace'e bağımlılık yok
(offline demo + ACA cold-start açısından kritik); "model imaj içinde, konteyner
network'süz ayağa kalkıyor" CI assertion'ı henüz yok — T048 ile eklenecek.

**E5 önek kuralı (sessiz kalite kaybı riski):** E5 ailesi belgelerin `passage: `, sorguların
`query: ` önekiyle verilmesini bekler. fastembed'in `query_embed()` metodu düz `embed()`'e
düşer ve önek eklemez; önek uygulama katmanında açıkça ekleniyor. Atlanırsa hata alınmaz,
yalnızca retrieval kalitesi düşer — davranış `apps/api/tests/test_embedding_prefix.py` ile
sabitlendi.

**Alternatives considered:**
- *bge-m3* — fastembed dense kataloğunda yok; kapsam dışı değil, G11'deki embedding A/B
  karşılaştırmasının adayı (≥40 soru, Recall@5 + MRR; sonuç test raporunda "embedding seçim
  gerekçesi" başlığında yayımlanacak).
- *İngilizce-odaklı embedding* — TR/EN karışık materyalde (Türkçe anlatım + `fork()`, `TLB`
  gibi terimler) Türkçe tarafında çöker.
- *API-only embedding* — per-query maliyet + offline demo (C planı) imkânsız hale gelir.

---

## 5. Sparse arama (FTS konfigürasyonu)

**Decision:** PostgreSQL FTS, `simple` + `unaccent` konfigürasyonu (köklendirme yok).

**Rationale:** Köklendirme kapalı olduğu için `fork()`, `O(n log n)`, `TLB` gibi teknik
tokenlar bozulmadan korunur — hybrid retrieval'ın TR/EN karışık teknik materyaldeki ana
kazanım noktası tam da bu. `unaccent` Türkçe aksan varyasyonlarını normalize eder.
turkish/english konfigürasyonlarıyla gold set üzerinde karşılaştırılıp raporlanacak.

**Alternatives considered:**
- *turkish (snowball)* — İngilizce teknik terimleri yanlış köklendirip bozar.
- *english* — Türkçe ekleri bozar; TR sorgu-belge eşleşmesini düşürür.

---

## 6. Retrieval füzyonu

**Decision:** Reciprocal Rank Fusion (k=60): dense top-20 (pgvector) ∥ FTS top-20 → RRF →
top-8; her sorguda zorunlu `WHERE course_id = :authorized_course_id`.

**Rationale:** RRF sıra tabanlıdır — iki farklı skor uzayını (kosinüs benzerliği vs
ts_rank) normalize etme derdi olmadan birleştirir; parametresizdir, veri gerektirmez,
deterministiktir. Baseline (dense-only) vs hybrid+RRF holdout sette anlamlılık kaydıyla
raporlanacak (PLAN.md G12).

**Alternatives considered:**
- *Öğrenilmiş fusion* — eğitecek veri yok.
- *Skor normalizasyonu* — farklı skor dağılımları arasında kırılgan; RRF'nin sıra tabanlı
  yaklaşımı bu sorunu tanım gereği taşımıyor.

---

## 7. LLM sağlayıcı stratejisi

**Decision:** LiteLLM Router: Groq (Llama) → Gemini Flash **otomatik** failover + retry/backoff,
kod seviyesinde — manuel anahtar değişimi değil.

**Rationale:** Free-tier kotalar ve 429/timeout, demo günü için en gerçek risklerden;
failover'ın insan müdahalesi gerektirmemesi gerekir. LiteLLM tek arayüzden çoklu sağlayıcı
yönetir; failover G13'te Groq anahtarı bilerek bozularak test edilir (Anayasa III: ölçmeden
iddia etme). Yapılandırılmış çıktı sağlayıcıya bırakılmaz: Pydantic şema + server-side
validasyon + 1 retry.

**Alternatives considered:**
- *Tek sağlayıcı* — kota/kesintide demo çöker; tek nokta hatası.
- *Yerel LLM hosting* — GPU maliyeti + cold-start; ACA consumption planına sığmaz.

---

## 8. Arka plan işleri (job kuyruğu)

**Decision:** Postgres job tablosu (`ingestion_jobs`, `FOR UPDATE SKIP LOCKED`) +
HTTP-tetiklemeli worker: upload handler 202 döner, sonra worker'ın `/drain` endpoint'ini
çağırır.

**Rationale:** ACA'nın HTTP scale-to-zero'suyla doğal uyum: worker yalnızca iş geldiğinde
uyanır. Kuyruk veriyle aynı Postgres'te yaşadığından ek altyapı, ek senkron, ek maliyet yok.
Alternatif tetikleme olarak KEDA PostgreSQL scaler notu düşüldü.

**Alternatives considered:**
- *Sürekli poll eden worker* — scale-to-zero ile çelişir: ya hiç sıfıra inmez ve free tier'ı
  yer, ya iner ve job'lar asılı kalır.
- *Redis + Celery* — MVP hacminde (ders başına onlarca doküman) gereksiz altyapı; tüm
  raporlar bu sadeleştirmede hemfikir (PLAN.md "Bilinçli kesilenler").

---

## 9. İzolasyon: iki katmanlı RLS

**Decision:** Ders izolasyonu çift katman: (1) backend'de zorunlu server-side `course_id`
filtresi — istemciden gelen `course_id` asla yetki değildir; (2) PostgreSQL RLS. RLS'in
gerçekten tetiklenmesi için backend anon key + kullanıcı JWT'sini geçirir; service-role
yalnızca worker'ın iç işlerinde. API tablo sahibi olmayan, BYPASSRLS taşımayan `dou_app`
rolüyle bağlanır (Anayasa II).

**Rationale:** "Dersler arası veri sızıntısı = 0" kabul kriterinin tek savunma hattıyla
karşılanması kabul edilemez; uygulama hatası RLS'e, RLS yanlış yapılandırması uygulama
filtresine takılır. Kritik incelik: service-role key ile RLS **sessizce bypass olur ve
izolasyon testleri sahte yeşil yanar** — bu yüzden G13'te policy bilerek bozulur ve
izolasyon testinin kırmızı yandığı görülür; RLS'in canlı olduğunun kanıtı raporda yer alır.

**Alternatives considered:**
- *Yalnızca uygulama katmanı filtresi* — tek unutulmuş WHERE = sızıntı; savunulamaz.
- *Yalnızca RLS (service-role ile bypass edilen kurulum)* — testler sahte güven verir;
  "dürüst kurulum" ancak anon key + JWT geçirilerek sağlanır.

---

## 10. Orkestrasyon

**Decision:** Düz Python servis kodu + açık state machine (Sokratik mod:
`DIAGNOSE → NUDGE → CONCEPT_HINT → SIMILAR_EXAMPLE → EXPLAIN_WITH_SOURCE`, backend'de).

**Rationale:** Pipeline incedir ve her adımı bir güvenlik sınırıdır (authz → retrieval →
evidence gate → generation → citation validator → pedagojik filtre → sanitize); bu zincirin
debug şeffaflığı framework soyutlamasından değerlidir. Sokratik akış bir framework'ün graf
soyutlamasını değil, açıkça yazılmış ve loglanan bir state machine'i gerektirir. Jüri
savunmasında "her adım bizim kodumuz" diyebilmek akademik savunulabilirlik merceğinin de
tercihiydi.

**Alternatives considered:**
- *LangChain / LlamaIndex / LangGraph* — soyutlama katmanları fail-closed guardrail
  zincirinin denetimini zorlaştırır; sürüm churn'ü 3 haftalık takvimde risk. Anayasa
  "Teknoloji Kilidi" bölümünde bilinçli olarak dışarıda tutulduğu kayıtlıdır; geri alınması
  plan revizyonu + yazılı gerekçe ister.

---

## Deploy gerçekliği (ölçülecek ve raporlanacak)

Karar tablosunun eki niteliğinde, ARCHITECTURE.md'den aynen taşınan kısıtlar:

- Embedding modeli fp32 ONNX ~2.2-2.3 GB, yükleme tepe RAM 3-4 GB → **int8 quantize
  zorunlu**; replika başına ölçülmüş RSS raporlanır (ACA consumption planı ≤ 2 vCPU / 4 GiB).
- Scale-to-zero uyanması = imaj pull + model yükleme (dakikalar sürebilir) → p95 < 10 sn
  hedefi yalnızca **sıcak replika, sorgu yolu** için geçerlidir; cold-start ayrıca ölçülür
  (G14). Demo/prova günleri api+worker minReplicas=1 (parametrik).
- Sorgu embedding'i yalnızca API konteynerinde; worker aynı imajı paylaşır (çift ayak izi yok).
- Maliyet hedefi ~$0-15/ay.

---

## Açık noktalar

- [NEEDS CLARIFICATION: ARCHITECTURE.md §1 quantize/RAM notu "bge-m3 fp32 ONNX ~2.2-2.3 GB"
  diyor; model multilingual-e5-large'a geçtiğine göre bu ölçüm E5 için tekrarlanıp not
  güncellenecek mi?]
