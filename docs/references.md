# Kaynaklar

**Kural:** Bu listede yalnız depoda gerçekten atıf yapılan kaynaklar durur. Bir kaynak
buraya "iyi durur" diye eklenmez; önce belgede ya da kodda ona dayanan bir cümle olur,
sonra buraya girer. Danışmanın istediği kitap/kaynak bağlantıları için "Murat ekleyecek"
satırları bilinçli olarak boş bırakılmıştır — uydurma başlık yazılmaz.

Biçim: APA 7'ye yakın; erişim tarihi 15 Eylül 2026. A2–A5'in künyeleri Crossref ve
arXiv kayıtlarından tek tek doğrulanmıştır (başlık, yazar sırası, cilt/sayı/madde, DOI);
ikincil kaynaklardan kopyalanmamıştır. Üniversitenin resmî kaynakça biçimi
netleşince tek geçişte dönüştürülür (bu listenin kaydı: `docs/team/YOL-HARITASI-16-EYLUL.md`
satır B3, "Kaynak listesi iskeleti"). `PLAN.md`'de böyle bir madde yok; önceki sürümde
olmayan bir plan maddesine atıf yapılıyordu.

## 1. Akademik

| # | Kaynak | Depoda nerede kullanılıyor |
|---|---|---|
| A1 | Liu, R., Zenke, C., Liu, C., Holmes, A., Thornton, P., & Malan, D. J. (2025). *Teaching CS50 with AI: Leveraging generative artificial intelligence in computer science education.* Harvard University. https://cs.harvard.edu/malan/publications/fp0627-liu.pdf | `PLAN.md` §1 ve `docs/requirements-analysis.md` §1.2 — yanıtların %22'sinde doğrudan çalışan kod sızıntısı bulgusu; "kaynak yoksa cevap yok" ve Sokratik fail-closed ilkesinin gerekçesi |
| A2 | Wallat, J., Heuss, M., de Rijke, M., & Anand, A. (2025). *Correctness is not faithfulness in retrieval augmented generation attributions.* ICTIR '25 — Proceedings of the 2025 ACM SIGIR International Conference on the Theory of Information Retrieval (s. 22–32). ACM. https://doi.org/10.1145/3731120.3744592 | `docs/requirements-analysis.md` §1.2 ve §1.3 — atıfların %57'ye kadarının post-rationalization olabildiği bulgusu; atfı modelin beyanına değil mekanik doğrulamaya bağlama kararının gerekçesi (`apps/api/app/modules/guardrails/citation.py`) |
| A3 | Tufino, E. (2025). *NotebookLM as a Socratic physics tutor: Design and preliminary observations of a RAG-based tool.* arXiv:2504.09720 [physics.ed-ph]. https://arxiv.org/abs/2504.09720 (The Physics Educator'da yayımlanmak üzere kabul edildi) | `docs/requirements-analysis.md` §1.3 — genel amaçlı RAG aracında Sokratik davranışın kullanıcı istemine bırakılması; bizim kademe otoritesini sunucu tarafı durum makinesine taşıma kararımızın karşıt örneği |
| A4 | Toskova, A., Georgiev, K., & Glushkova, T. (2026). Dialogical learning support in RAG-based e-learning. *Information, 17*(5), 418. https://doi.org/10.3390/info17050418 | `docs/requirements-analysis.md` §1.3 — eğitmen tarafından doğrulanmış materyale bağlı diyalojik öğrenme desteği; "yalnız öğretmenin kaynakları" ve onay akışının literatür dayanağı |
| A5 | Vadlapati, P. (2026). *Index-RAG: Storing text locations in vector databases for question-answering tasks* [ön baskı, **hakem değerlendirmesinden geçmemiştir**]. Preprints.org. https://doi.org/10.20944/preprints202603.2025.v1 | `docs/requirements-analysis.md` §1.3 — konum meta verisini (dosya, sayfa, satır) vektör deposunda tutmanın atıf doğruluğuna katkısı; chunk provenance tasarımımızın dayanağı. **Hakemli değildir**, destekleyici kaynak olarak kullanılır |

## 2. Ders kitapları (danışmanın istediği liste)

| # | Kaynak | Durum |
|---|---|---|
| K1 | İşletim Sistemleri ana ders kitabı (örnek materyal paketinin dayandığı kaynak) | **Murat ekleyecek** — başlık, yazar, baskı, ISBN |
| K2 | Danışmanın önerdiği ek okuma(lar) | **Murat ekleyecek** — danışmanla teyit edilecek |

## 3. Kullanılan araç ve modeller (teknik belgeler)

Bu satırlar `ARCHITECTURE.md` ve `docs/security.md` içinde adıyla anılan bileşenlerdir;
sürüm numaraları `apps/api/uv.lock` ve `apps/web/bun.lock` kilit dosyalarından okunur.

| # | Bileşen | Rolü | Belge |
|---|---|---|---|
| T1 | `intfloat/multilingual-e5-large` | Çok dilli embedding (1024 boyut); `query:`/`passage:` önek kuralı | https://huggingface.co/intfloat/multilingual-e5-large |
| T2 | fastembed (ONNX çalışma zamanı) | Embedding'in yerel, ağsız üretimi | https://github.com/qdrant/fastembed |
| T3 | PostgreSQL 16 + pgvector | Tek veritabanı: ilişkisel veri, vektör arama, RLS ile ders izolasyonu | https://www.postgresql.org/docs/16/ · https://github.com/pgvector/pgvector |
| T4 | LiteLLM | Sağlayıcı yönlendirme, yedek model, retry | https://docs.litellm.ai/ |
| T5 | Groq API — `openai/gpt-oss-120b` (birincil), `qwen/qwen3.6-27b` (yedek) | Cevap üretimi; OpenAI'ın açık ağırlıklı modeli Groq üzerinden | https://console.groq.com/docs |
| T6 | Google Gemini API | İkinci sağlayıcı (yedek) ve değerlendirme yargıcı seçeneği | https://ai.google.dev/gemini-api/docs |
| T7 | FastAPI · Next.js 16 · Playwright | API çerçevesi · web arayüzü · gerçek tarayıcı kabul testleri | https://fastapi.tiangolo.com/ · https://nextjs.org/docs · https://playwright.dev/ |

## 4. Güvenlik bildirimleri

`docs/test-report.md` içinde bağımlılık denetimi sırasında atıf yapılan GitHub
güvenlik bildirimleri: GHSA-2xp9-vwfh-vxw4, GHSA-p293-qw3h-jr36, GHSA-2v37-7h3g-55p8,
GHSA-rgj7-g3m4-5g8c (https://github.com/advisories/<kimlik>).

## 5. Standartlar

| # | Kaynak | Depoda nerede |
|---|---|---|
| S1 | WCAG 2.1 AA — https://www.w3.org/TR/WCAG21/ | `DESIGN.md`, `docs/accessibility.md`; kontrast ölçümü `apps/web/scripts/contrast.mjs` |
| S2 | 6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK) — https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=6698&MevzuatTur=1&MevzuatTertip=5 | `docs/kvkk.md`, `/kvkk` aydınlatma sayfası |
