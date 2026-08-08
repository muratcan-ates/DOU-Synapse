# DOU-Synapse

**CourseGPT — Yapay Zekâ Destekli Kişiselleştirilmiş Ders ve Sınav Asistanı**
Doğuş Üniversitesi · COME 491/492 Bitirme Projesi · 2026
Danışman: Yasemin Karagül · Takım: Muratcan Ateş (frontend + lead), Eren (backend/RAG + guardrail), Metehan Alphan (assessment + değerlendirme)

Eğitmenin yüklediği ders materyaliyle **sınırlı** çalışan, her cevabı dosya + sayfa/slayt
kaynağıyla veren, öğrenciye cevabı doğrudan vermek yerine **Sokratik yöntemle kendi
cevabını buldurmayı** esas alan RAG tabanlı ders asistanı.

**Çekirdek ilke: kaynak yoksa cevap yoktur.** Materyalde karşılığı olmayan soruya sistem
cevap uydurmaz, bulamadığını söyler — bu bir hata değil, tasarlanmış davranıştır.

## Yapay zekânın üç rolü

| Rol | Ne yapar | Sınırı |
|---|---|---|
| **Class Assistant** | Öğrencinin materyal içi sorularını kaynak göstererek yanıtlar | Materyalde karşılığı yoksa cevap vermez |
| **Exam Mentor** | Öğrencinin denemesini bekler; kademeli, kaynaklı Sokratik ipucu verir; yanlış şıkta çelişen kaynak bölümünü gösterir | Cevabı asla doğrudan vermez; sınav modunda ipucu kapalı |
| **CourseGPT** | Eğitmenin kurduğu çerçevede (konu + biçim + örnek soru) taslak soru ve cevap anahtarı üretir | Yayın kararı veremez — **eğitmen onaylamadan hiçbir soru öğrenciye görünmez** |

## Durum (8 Ağustos 2026)

**Çalışıyor ve testli:** iki katmanlı ders izolasyonu (uygulama katmanı + PostgreSQL RLS,
kanıtı CI'da), ders/üyelik yönetimi, materyal yükleme (magic-byte doğrulamalı) ve işleme
hattı, sayfa/slayt metadata'sını koruyan parçalama, embedding + pgvector indeksleme,
assessment şeması (konular, soru havuzu, sınav oturumları, mastery), 6 ekranlı web
arayüzü. **92 otomatik test** + CI (lint, tip, test, RLS izolasyon kanıtı).

**Henüz tasarım önizlemesi:** sohbet ve sınav ekranları — cevap üretim hattı
(retrieval → LLM → guardrail) sıradaki iş, hedef 10 Ağustos dikey demo kapısı.

## Kurulum — GitHub'dan sıfıra

> Tam anlatım (PostgreSQL/pgvector kurulumu dahil):
> [`specs/001-course-assistant-mvp/quickstart.md`](specs/001-course-assistant-mvp/quickstart.md)
> Alternatif: `docker compose up` (bkz. quickstart §8).

**Önkoşullar** (macOS + Homebrew): `postgresql@16` + pgvector (16'ya karşı kaynaktan
derlenir — quickstart §1), [`uv`](https://docs.astral.sh/uv/) (Python 3.12'yi kendisi
indirir), [Bun](https://bun.sh) 1.x.

**1. Depoyu klonla**

```bash
git clone https://github.com/muratcan-ates/DOU-Synapse.git
cd DOU-Synapse
```

**2. Veritabanını kur** — şema + RLS politikaları + demo kullanıcıları:

```bash
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
createdb dou_synapse
for f in supabase/migrations/*.sql; do psql -v ON_ERROR_STOP=1 -d dou_synapse -f "$f"; done
psql -d dou_synapse -f supabase/local_dev_setup.sql
psql -d dou_synapse -f supabase/seed_demo.sql
```

**3. Backend'i kur, testleri koştur**

```bash
cd apps/api
uv venv --python 3.12
uv pip install -e ".[dev]"
cp ../../.env.example .env        # varsayılanlar yerel için yeterli
uv run pytest -q                  # 92 test yeşil olmalı
```

**4. Servisleri başlat** (üç ayrı terminal)

```bash
uv run uvicorn app.main:app --port 8000
```

```bash
uv run python -m app.worker
```

```bash
cd apps/web && bun install && bun run dev
```

**5. Aç:** http://localhost:3000 — girişte **Ayşe Hoca** (eğitmen) veya **Burak Yılmaz**
(öğrenci) demo kartına tıkla. (Yerel geliştirmede DEV kimlikleri kullanılır; Supabase
Auth entegrasyonu planlıdır ve DEV kimliği üretim ortamında yapılandırma düzeyinde
reddedilir.)

## Mimari — ne nerede çalışıyor

| Parça | Teknoloji | Nerede |
|---|---|---|
| Veritabanı | PostgreSQL 16 + pgvector (vektörler ayrı depo olmadan aynı DB'de) | :5432 |
| API | FastAPI / Python 3.12 — ders yönetimi, yükleme, yetkilendirme, izolasyon | :8000 |
| Worker | Ayrı süreç — parçalama + embedding (multilingual-e5-large) | — |
| Arayüz | Next.js (masaüstü + mobil tarayıcı, Türkçe birinci dil) | :3000 |

Hedef cevap hattı: hibrit arama (dense + full-text, RRF) → LiteLLM (Groq → Gemini
otomatik yedekli) → guardrail zinciri → mekanik atıf doğrulaması.
LangChain/LlamaIndex bilinçli olarak kullanılmaz — gerekçeler
[ARCHITECTURE.md](ARCHITECTURE.md)'de.

## Belgeler

| Belge | İçerik |
|---|---|
| [docs/requirements-analysis.md](docs/requirements-analysis.md) | Gereksinim analizi — danışman taslağı → FR izlenebilirliği, kabul kriterleri |
| [specs/001-course-assistant-mvp/](specs/001-course-assistant-mvp/) | Spec (35 FR), plan, görev listesi, quickstart, OpenAPI sözleşmesi |
| [PLAN.md](PLAN.md) | 15 iş günlük takvim, kapılar (10 Ağu demo, 17 Ağu dondurma), riskler |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Teknoloji kararları + gerekçeleri, guardrail zinciri, değerlendirme tasarımı |
| [DESIGN.md](DESIGN.md) | Tasarım token'ları — arayüzün tek otoritesi |
| [docs/team/](docs/team/) | Takım koordinasyonu, rol brief'leri, devir teslim |

## Lisans

[MIT](LICENSE)
