# DOU-Synapse — 3 Haftalık Geliştirme Planı (Nihai)

**Proje:** COME 491/492 Bitirme Projesi — CourseGPT: Yapay Zeka Destekli Kişiselleştirilmiş Ders ve Sınav Asistanı
**Süre:** 15 iş günü — **Salı 4 Ağustos – Pazartesi 24 Ağustos 2026** (4 Ağu 2026 Salı'dır; hafta 1'de 4 iş günü var)
**Repo:** https://github.com/muratcan-ates/DOU-Synapse
**Mimari detayları:** [ARCHITECTURE.md](ARCHITECTURE.md)

> Bu plan; 9 derin araştırma raporunun sentezidir ve 4 bağımsız denetim merceğinden
> (fizibilite, gereksinim kapsaması, demo/operasyon riski, akademik savunulabilirlik)
> geçirilerek revize edilmiştir. Raporların çeliştiği her noktada tek karar verildi;
> gerekçeler ARCHITECTURE.md'dedir.

> **Gerçekle hizalama — 9 Ağustos 2026 (R5).** Takvim tablosu planlandığı gibi bırakıldı
> (plan bir tarih kaydıdır, sonradan yazılmaz), ama **§2 kapsam tablosuna gerçekleşme
> sütunu** ve **§5 kabul kriterlerine ölçülen değer sütunu** eklendi. Ölçülmemiş bir satıra
> sonuç yazılmadı; "KOŞULMADI" yazmak tahmin yazmaktan iyidir (Anayasa III).
> Uygulanmayan mimari kararların tam listesi: [ARCHITECTURE.md §10](ARCHITECTURE.md#10-uygulanmayanlar--tasarlandı-kodda-yok).

---

## 1. Karar Özeti

**3 haftada ne yapıyoruz:**

> Öğretmenin yüklediği ders materyallerini ders bazında izole eden; öğrencinin sorularına
> **yalnızca bu materyallerden, sayfa/slayt kaynağıyla** cevap veren; cevabı göstermeden
> önce **fail-closed guardrail zincirinden** geçiren (atıf doğrulama + kanıt eşiği + kod/çözüm
> sızıntı filtresi); Sokratik çalışma, sınav provası, kod inceleme ve konu bazlı performans
> takibi sunan web tabanlı öğretim asistanı.

**Jüri için konumlandırma** (ölçüme bağlı, abartısız):

> "Harvard'ın CS50 Duck değerlendirmesinde yanıtların %22'sinde doğrudan kod sızdırıldığı
> raporlandı.¹ DOU-Synapse bu problemi hedef alır: atıflar mekanik olarak doğrulanır
> (model retrieve edilmemiş kaynağa atıf yapamaz), kanıt yoksa cevap verilmez ve Sokratik
> modda kural tabanlı, fail-closed bir son kontrol katmanı çalışır. Sızıntı oranımızı
> kendi test setimizde ölçüp raporluyoruz — garanti iddia etmiyoruz, ölçüm sunuyoruz."
>
> ¹ Liu ve ark., "Improving AI in CS50: Leveraging Human Feedback for Better Learning",
> Harvard, 2025 — https://cs.harvard.edu/malan/publications/fp0627-liu.pdf

**Fark yaratan üç şey** (hocanın taslağında olmayan, 15 iş gününe sığan, demo'da görünür):

1. **Fail-closed pedagojik guardrail zinciri** — atıf set-membership kontrolü
   (deterministik), kanıt eşiği altında cevap yok, kod/çözüm dedektörü ihlalde şablon
   ipucuna düşer. İddia-kaynak tutarlılığı (faithfulness) ayrıca örneklem üzerinde ölçülür.
2. **Hybrid retrieval (dense + BM25 + RRF)** — TR/EN karışık teknik materyalde (`fork()`,
   `TLB`, `O(n log n)`) düz vektör aramanın kaçırdığını yakalar; dense-only baseline'a
   karşı **holdout set üzerinde, anlamlılık kaydıyla** raporlanır.
3. **Mastery-Lite (çalışma performans göstergesi) + eğitmen analitik ekranı** — konu bazlı
   ağırlıklı puan; bilinçli bir EWMA sadeleştirmesi olduğu gerekçesiyle birlikte belgelenir.

---

## 2. Kapsam

### P0 — Teslim için zorunlu

Son sütun **9 Ağustos 2026'da kod okunarak ve sistem çalıştırılarak** dolduruldu.
✅ çalışıyor · ⚠️ çalışıyor ama sınırı var · ❌ henüz yok.

| # | Özellik | 3 haftalık biçimi | Durum (9 Ağu) |
|---|---|---|---|
| 1 | Eğitmen/öğrenci girişi ve rolleri | Supabase Auth; RBAC backend'de | ⚠️ RBAC ders bazlı ve çalışıyor; kimlik hâlâ `DEV_AUTH` (`Bearer dev:<uuid>`). Supabase Auth köprüsü R1'de |
| 2 | Ders oluşturma + öğrenci kaydı | `courses`, `course_memberships` | ✅ |
| 3 | PDF / PPTX / Markdown / kod yükleme | Tür+boyut+magic byte kontrolü; asenkron ingestion + n/m ilerleme göstergesi | ✅ 8 dosya → 33 chunk, hepsi `completed` |
| 4 | Ders bazlı mutlak izolasyon | Server-side `course_id` + RLS (gerçekten tetiklendiği kanıtlanarak) | ⚠️ Yerel/CI'da ✅ (`dou_app` rolü + FORCE RLS + CI'da izolasyon kanıtı); **Compose yığınında RLS devre dışı** (superuser) |
| 5 | Kaynaklı sohbet | Cevap + dosya adı + sayfa/slayt; kaynak chunk metadata'sından üretilir | ✅ |
| 6 | Kapsam dışı ret (abstention) | Kanıt eşiği (kalibrasyon setiyle ayarlanır) + kaynaksız cevabı bloklama | ⚠️ Çalışıyor ama statü `insufficient_context` dönüyor, `out_of_scope` değil (ARCHITECTURE §5); holdout'ta %80 |
| 7 | Sokratik mod | Backend state machine; **ipuçları da retrieve edilmiş kaynaklardan türetilir ve kaynak taşır** | ✅ Israrcı öğrenci yolu dahil canlıda doğrulandı |
| 8 | Sınav prova modu | Süreli MCQ + açık uçlu; ipucu kapalı, tek deneme | ✅ `exam` modunda ipucu kapalı; `practice` modunda açık ve mastery çarpanına giriyor |
| 9 | "Neden yanlış?" analizi | MCQ'da distractor→kaynak eşlemesi (birincil); açık uçlu için rubrik geri bildirimi | ✅ MCQ yolu deterministik, dosya+sayfa ile doğrulandı |
| 10 | Soru havuzu üretici | JSON şemalı; `mcq / open / code_trace / bug_hunt` tipleri; **eğitmen onayı olmadan yayınlanmaz** | ⚠️ Onay kapısı ✅ (öğrenci taslak göremiyor, `answer_key` beyaz listeyle eleniyor); **üretim gerçek LLM anahtarı ister** — sahte sağlayıcı 0 soru döndürüyor |
| 11 | Kod/senaryo inceleme | `code_trace` (çıktı tahmini) + `bug_hunt` (hata buldurma) soru tipleri; kod ÇALIŞTIRMADAN | ⚠️ Şema ve puanlama var; üretim #10'un kısıtına tabi |
| 12 | Açık uçlu değerlendirme | Rubrik + şemalı LLM değerlendirmesi (skor, eksik_noktalar[], dayanak_chunk_id) | ⚠️ Kod yolu var; anahtarsız ortamda ölçülemedi |
| 13 | Guardrail zinciri | Citation validator + kod sızıntı filtresi + evidence gate (fail-closed) | ✅ Sıra tek yerde sabit; **iki orkestratör var, üretimde biri koşuyor** (ARCHITECTURE §5) |
| 14 | Mastery-Lite | Konu bazlı EWMA puanı + eğitmen özet ekranı (tek sayfa) | ✅ Öğrenci ve sınıf görünümü canlıda doğrulandı |
| 15 | Demo cevap cache'i | Exact-match cache; demo senaryosu soruları önceden doldurulur (offline sigortası) | ⚠️ Cache mekanizması ✅ (yalnız `qa` modu, birebir eşleşme); **doldurma betiği R3'te, soru listesi `docs/demo-script.md`'de** |
| 16 | Gold test seti + başarı raporu | ≥50 soru (kalibrasyon/holdout ayrık); metrikler + faithfulness örneklemi (20-30 cevap, elle) | ⚠️ Set ve harness var; uçtan uca metrikler R2'de, anahtar bekliyor |
| 17 | Canlı URL (1. günden) + Docker Compose | Sürekli deploy; Compose lokal/fallback | ❌ Canlı URL yok; Compose var ama RLS'siz. R3'ün işi |
| 18 | Kullanım kılavuzları + örnek ders paketi | Eğitmen + öğrenci kılavuzu; İşletim Sistemleri materyal seti | ✅ Bu şerit (R5): iki kılavuz + runbook + demo script + KVKK metni |

### P1 — Zaman kalırsa (dondurmadan sonra yalnızca bayrak arkasında)

- Cross-encoder reranker (`ENABLE_RERANKER`)
- RAGAS ile otomatik faithfulness (manuel örneklemin üstüne)
- Streaming cevap (SSE)
- Analitikte soru kümeleme

### Bilinçli kesilenler

| Öneri | Kaynak | Neden reddedildi |
|---|---|---|
| Dış kaynak RAG katmanı (IEEE vb.) | Konumlandırma raporu | **Hocanın açık şartıyla çelişir** ("internet bilgisi karışmaz"). v2'de *eğitmen onaylı* paket olarak |
| Semantik önbellek (Redis/GPTCache) | Konumlandırma raporu | Yanlış cache eşleşmesi = yanlış cevap; exact-match cache yeter |
| Qdrant / FAISS / Chroma | ChatGPT planı | İkinci veri deposu = senkron + yetki sızıntısı riski; pgvector yeter |
| LangChain/LlamaIndex/LangGraph | ChatGPT planı, ilk planımız | İnce pipeline düz Python'la daha şeffaf; state machine framework istemez |
| Streamlit / Django+HTMX | Rapor-11, Rapor-12 | Ekipte gerçek Next.js tecrübesi var; ekip React biliyor |
| K8s, mikroservis, Kafka, Redis+Celery | Tüm raporlar hemfikir | Postgres job tablosu + HTTP-tetiklemeli worker yeter |
| Fine-tuning, GraphRAG, multi-agent, OCR, mobil, sesli, kod sandbox | Tüm raporlar hemfikir | Kapsam şişirir, ana değeri doğrulamaz |
| OpenAI File Search | Rapor-15 | Yalnızca 5. gün kapısı geçilemezse acil durum yedeği |

---

## 3. Takvim (gerçek 2026 günleriyle)

Sert kapılar: **G5 (Pzt 10 Ağu) dikey demo kapısı** ve **G10 (Pzt 17 Ağu) özellik dondurma**.
**Hafta sonları plansız buffer'dır** — kayan iş emici; P0 işi hafta sonuna yazılmaz.

### Hafta 1: Sal 4 – Cum 7 (4 iş günü) — İskelet + ingestion

| Gün | İş | Gün sonu çıktısı |
|---|---|---|
| Sal 4 (G1) | Repo/monorepo iskeleti, CI, **"hello world" üçlü deploy (Vercel + ACA + Supabase)**, çekirdek 3-4 tablo. Hocaya 1 sayfalık kapsam özeti e-postası (asenkron ön-onay) | **Canlı URL 1. günden yaşıyor** |
| Çar 5 (G2) | Auth + roller + ders/üyelik + **RLS (auth'la birlikte) + izolasyon smoke testi**; **OpenAPI sözleşmesi dondurulur** → frontend mock'larla başlar | Giriş + izolasyon çalışır |
| Per 6 (G3) | Upload (validasyon) + job tablosu + PyMuPDF/pptx/kod parser'ları; `sample_data/` v1 (≥3 PDF + 1 PPTX + 2 kod dosyası). **20:00 hoca toplantısı: ilerleme demosu + plan sunumu** | Sayfa metadata'lı chunk'lar |
| Cum 7 (G4) | Chunking + embedding (multilingual-e5-large, fastembed/ONNX, imaja gömülü — gerekçe: specs/001 research.md §4) + pgvector; LLM+citation işi **mock retrieval üzerinde paralel** başlar; kalibrasyon seti (~15-20 soru; tasks T041/T043 ile aynı sayı) | Aranabilir ders indeksi |
| Cmt-Paz | **Buffer** (planlı iş yok) | — |

### Hafta 2: Pzt 10 – Cum 14 — Çekirdek RAG + eğitim modları

| Gün | İş | Gün sonu çıktısı |
|---|---|---|
| Pzt 10 (G5) | Dense-only retrieval + LLM + citation + abstention v0, **gerçek materyalle, canlı URL'de** | **KAPI: uçtan uca kaynaklı cevap.** Geçilemezse File Search kararı |
| Sal 11 (G6) | Pydantic şemalar + citation validator + **eşik kalibrasyonu (kalibrasyon setiyle)**; FTS (simple+unaccent) başlar | Model atıf uyduramaz |
| Çar 12 (G7) | Hybrid (dense+FTS+RRF) tamam; Sokratik state machine (kaynaklı ipuçları) | Baseline vs hybrid ölçülebilir durumda |
| Per 13 (G8) | Kod sızıntı filtresi + kapsam dışı ret sertleştirme; soru üretici (4 tip) + eğitmen onay akışı | Guardrail zinciri + soru bankası |
| Cum 14 (G9) | Sınav prova modu + MCQ puanlama + "neden yanlış"; açık uçlu rubrik değerlendirme v1; Mastery-Lite backend | Sınav döngüsü çalışır |
| Cmt-Paz | **Buffer** | — |

### Hafta 3: Pzt 17 – Pzt 24 — Analitik, ölçüm, teslim

| Gün | İş | Gün sonu çıktısı |
|---|---|---|
| Pzt 17 (G10) | Mastery ekranı + eğitmen analitik kartı + frontend eksik ekran kapama | **Gün sonu: ÖZELLİK DONDURMA** |
| Sal 18 (G11) | Gold set çapraz kontrol + eksik kategorilerin tamamlanması (H1'den beri günde 5-8 soru birikti) + **kalibrasyon/holdout ayrımı**; embedding A/B (≥40 soru, Recall@5+MRR) | Etiketli, ayrık değerlendirme seti |
| Çar 19 (G12) | Otomatik eval (rate-limit kuyruklu, ayrı API anahtarı, gece koşar): baseline vs hybrid, anlamlılık kaydı; faithfulness örneklemi (20-30 cevap, 2 etiketleyici); **kılavuz taslakları başlar** (rol bazlı) | Ölçülmüş kalite verisi |
| Per 20 (G13) | Güvenlik testleri **prod URL'de** (RLS'in gerçekten tetiklendiği kanıtı: policy bilerek bozulur, test kırmızı yanmalı); LLM failover testi (Groq anahtarı bilerek bozulur) | Negatif testleri geçen sürüm |
| Cum 21 (G14) | Son sürüm deploy + cold-start ölçümü + demo günü minReplicas kararı + **demo cache doldurma** + pg_dump yedek + Compose'a restore provası; başarı raporu yazımı | Teslim paketi hazır |
| Cmt-Paz | Buffer + isteğe bağlı demo provası (en az 1 tam **offline** prova: Wi-Fi kapalı) | — |
| Pzt 24 (G15) | Yalnızca kritik düzeltme, demo provası, sürüm etiketi, teslim | Release |

---

## 4. Rol Dağılımı (4 kişi; 5. üye çıkarsa doğrudan frontend'e)

| Rol | Sorumluluk | Not |
|---|---|---|
| **Backend/RAG lead** | FastAPI, ingestion, retrieval, LLM | H1-2 yoğun |
| **Frontend lead (Muratcan)** | Next.js; **G2'den itibaren mock'larla** | Ekran önceliği aşağıda |
| **Guardrail & QA** | Validator'lar, state machine, güvenlik testleri | H2'de form-düzeyi React öğrenir (yedeklilik) |
| **Data & Eval** | Materyal paketi (H1), **her gün 5-8 gold soru**, eval harness, rapor | H3 çok yoğun |

**Frontend ekran önceliği** (feda kararı panik anında verilmesin diye şimdiden):
- *Demo yolu (feda edilemez):* login → ders → upload+durum → citation'lı chat → Sokratik → sınav
- *Basitleştirilebilir:* soru onay paneli (düz tablo), analitik (tek kart sayfası), mastery görünümü (liste)

Kurallar: Issue → branch → PR → 1 review → merge; `main` korumalı. AI araçları küçük, kabul
kriterli görevlerle; auth, RLS, `course_id` filtreleri, migration'lar insan incelemesinden geçer.

---

## 5. Kabul Kriterleri (başarı raporunun iskeleti)

| Metrik | Hedef | Ölçülen (9 Ağu 2026) | Kayıt |
|---|---:|---|---|
| Dersler arası veri sızıntısı | 0 | **0** — CI her koşuda `supabase/tests/rls_isolation.sql` çalıştırıyor | RLS'in tetiklendiği ayrıca kanıtlanır |
| Kaynaksız gösterilen akademik cevap (ipuçları dahil) | %0 | **%0** — kod yolu fail-closed; uçtan uca örneklem KOŞULMADI | — |
| Holdout sette Recall@5 ve Recall@8 | ≥ %80 | **KOŞULMADI** (R2) | @8 = üretim k'sı; @5 = karşılaştırılabilirlik |
| Citation precision (doğru dosya+sayfa) | ≥ %90 | **KOŞULMADI** (R2) | — |
| Kapsam dışı doğru ret | ≥ %90 | **%80 — HEDEFİN ALTINDA.** Retrieval kapısı düzeyinde, 55 soruluk holdout, eşik 0.81 | `evaluation/calibration.md` §7. Uçtan uca değer R2'de |
| Faithfulness (manuel örneklem, 20-30 cevap, 2 etiketleyici) | raporlanır | **KOŞULMADI** (R2, LLM anahtarı bekliyor) | Uyum oranıyla birlikte |
| Sokratik modda kod/çözüm sızıntısı | Test setinde 0 | **Birim testlerinde 0**; gerçek LLM ile KOŞULMADI | Set fence'siz kod, pseudocode, sözel çözüm vakaları içerir |
| Injection testleri (≥15 vaka, kalıp aileleri) | Geçer | **KOŞULMADI** (R4) | "Smoke-test edildi" olarak raporlanır, "dayanıklı" denmez |
| Soru üretiminde şema geçerliliği | ≥ %98 | **ÖLÇÜLEMEDİ** — sahte sağlayıcı soru üretmiyor; gerçek anahtar gerekiyor | — |
| Uçtan uca cevap p95 | < 10 sn | **KOŞULMADI.** Yerel ölçüm: ilk yükleme 19,1 sn (model yükleme dahil), sonraki yüklemeler 2–7 sn | **Sıcak replika, sorgu yolu** |
| Demo akışında kritik hata | 0 | Altı sahnenin **beşi** canlıda koşuldu ve geçti; 6. sahne (sınav) önceden onaylanmış soru gerektirdi | `docs/demo-script.md` |
| Backend testleri | yeşil | **851 geçiyor** (`uv run pytest -q`) | — | <!-- docs-check: backend.tests = 851 -->

Sonuçlar sunulurken not düşülür: *n=50, alt kümeler n≈10 — yön göstergesi, kesin hüküm değil.*
Çalıştırılmayan deney için sonuç yazılmaz — yukarıdaki **KOŞULMADI** satırları bunun içindir.

---

## 6. Riskler ve Geri Dönüş Planları

| Risk | Erken işaret | Geri dönüş |
|---|---|---|
| Retrieval hattı G5'te çalışmıyor | Kapı demosu başarısız | OpenAI File Search yedeği; mimari büyütülmez |
| PDF ayrıştırma bozuk | Sayfa sırası/tablolar anlamsız | Docling'i sorunlu dosyalara fallback yap |
| TR retrieval kalitesi düşük | Embedding A/B'de Recall düşük | multilingual-e5 ↔ bge-m3 ↔ API; **karar ingest-zamanıdır, geçiş tam re-index demektir** |
| LLM kota/kesinti | 429/timeout | **LiteLLM Router otomatik failover (Groq→Gemini) + backoff — manuel geçiş değil**; kota bütçesi; demo soruları cache'ten |
| Supabase kesintisi / free-tier pause | Login çalışmıyor; proje uykuda | Demo sabahı oturumlar önceden açılır; günlük keep-alive ping; pg_dump + Compose restore provası (G14) |
| Sokratik mod cevabı hemen veriyor | Davranış testi kırmızı | State machine + fail-closed filtre; prompt'a tek başına güvenilmez |
| Frontend darboğazı | H2 ortasında ekranlar gecikmiş | Ekran öncelik listesi uygulanır; Guardrail&QA üyesi form işleri alır |
| Demo günü internet sorunu | — | **Birincil B planı: telefon hotspot + canlı bulut.** C planı: Compose + dev-auth bypass + demo cache'ten cevaplar (LLM'siz senaryolu akış). En az 1 tam offline prova |
| ACA cold start demo'da | İlk istek dakikalar | Demo/prova günleri **minReplicas=1**; model imaja gömülü (HF'e runtime bağımlılık yok) |
| Kapsam sürünmesi | P0 dışı issue açılıyor | G10 dondurma; P1 yalnızca bayrak arkasında |

---

## 7. Teslim Paketi (hocanın 3 çıktısına karşılık)

1. **Çalışır web platformu** → canlı URL (1. günden yaşayan) + `docker compose up` lokal kurulum
2. **Örnek ders paketi + başarı testi raporu** → `sample_data/` İşletim Sistemleri seti +
   `docs/test-report.md` (holdout metrikleri, baseline vs hybrid + anlamlılık, guardrail/sızıntı
   testleri, faithfulness örneklemi, embedding seçim gerekçesi)
3. **Kılavuzlar** → `docs/instructor-guide.md`, `docs/student-guide.md` (G12'den itibaren rol
   bazlı yazılır; G14-15 yalnızca ekran görüntüsü + son okuma)

### Jürinin eline geçen belgeler (harita)

| Belge | Ne cevaplar | Durum |
|---|---|---|
| [`README.md`](README.md) | Proje ne, nasıl kurulur, hangi belge nerede | ✅ |
| [`specs/001-course-assistant-mvp/quickstart.md`](specs/001-course-assistant-mvp/quickstart.md) | Sıfırdan kurulum, adım adım | ✅ sıfırdan koşuldu |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Hangi karar neden verildi; **ne uygulanmadı** | ✅ kodla hizalı |
| [`PLAN.md`](PLAN.md) | Takvim, kapsam, kabul kriterleri ve **ölçülen değerler** | ✅ |
| [`docs/runbook.md`](docs/runbook.md) | Demo günü ne yapılır, bozulursa ne yapılır | ✅ |
| [`docs/demo-script.md`](docs/demo-script.md) | Sahne sahne ne anlatılır | ✅ |
| [`docs/instructor-guide.md`](docs/instructor-guide.md) | Eğitmen ne yapar | ✅ |
| [`docs/student-guide.md`](docs/student-guide.md) | Öğrenci ne yapar | ✅ |
| [`docs/kvkk.md`](docs/kvkk.md) | Hangi kişisel veri nasıl işleniyor | ✅ metin hazır, **sayfa lider'de** |
| [`docs/test-report.md`](docs/test-report.md) | Ölçülen kalite | R2 |
| `docs/security.md` | Güvenlik testleri | R1 — **dosya henüz yok** |
| `docs/deployment.md` | Dağıtım | R3 — **dosya henüz yok** |
| [`evaluation/calibration.md`](evaluation/calibration.md) | Eşik neden 0.81, neden hedefi tutmadı | ✅ |
