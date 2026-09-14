# Kaynaklar

**Kural:** Bu listede yalnız depoda gerçekten atıf yapılan kaynaklar durur. Bir kaynak
buraya "iyi durur" diye eklenmez; önce belgede ya da kodda ona dayanan bir cümle olur,
sonra buraya girer. Danışmanın istediği kitap/kaynak bağlantıları için "Murat ekleyecek"
satırları bilinçli olarak boş bırakılmıştır — uydurma başlık yazılmaz.

Biçim: APA 7'ye yakın; erişim tarihi 14 Eylül 2026. Üniversitenin resmî kaynakça biçimi
netleşince tek geçişte dönüştürülür (bkz. plan maddesi "Kaynak listesi ve teslim evrakı").

## 1. Akademik

| # | Kaynak | Depoda nerede kullanılıyor |
|---|---|---|
| A1 | Liu, R., Zenke, C., Liu, C., Holmes, A., Thornton, P., & Malan, D. J. (2025). *Teaching CS50 with AI: Leveraging generative artificial intelligence in computer science education.* Harvard University. https://cs.harvard.edu/malan/publications/fp0627-liu.pdf | `PLAN.md` §1 ve `docs/requirements-analysis.md` §1.2 — yanıtların %22'sinde doğrudan çalışan kod sızıntısı bulgusu; "kaynak yoksa cevap yok" ve Sokratik fail-closed ilkesinin gerekçesi |

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
