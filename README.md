# DOU-Synapse

**CourseGPT — Yapay Zekâ Destekli Kişiselleştirilmiş Ders ve Sınav Asistanı**
Doğuş Üniversitesi · COME 491/492 Bitirme Projesi · 2026
Danışman: Yasemin Karagül · Takım: Muratcan Ateş (frontend + lead), Eren (backend/RAG + guardrail), Metehan Alphan (assessment + değerlendirme)

Eğitmenin yüklediği ders materyaliyle **sınırlı** çalışan, her cevabı dosya + sayfa/slayt
kaynağıyla veren, **Sokratik** bir ders asistanı: öğrenciye cevabı söylemek yerine,
kademeli ve kaynaklı ipuçlarıyla **kendi cevabını buldurur**. Öğrenci kendi denemesini
yapmadan bir sonraki ipucu kademesine geçilmez.

**Çekirdek ilke: kaynak yoksa cevap yoktur.** Materyalde karşılığı olmayan soruya sistem
cevap uydurmaz, bulamadığını söyler — bu bir hata değil, tasarlanmış davranıştır.

**Soru hazırlama yükü eğitmende değil, sistemde.** Eğitmen yalnız çerçeveyi kurar —
konuyu ve biçimi seçer (test / klasik / kısa cevap), isterse bir-iki örnek soru verir.
Sistem, ders materyalinden o biçimde ve o üslupta soruları **cevap anahtarı ve kaynak
referansıyla birlikte** kendisi üretir; eğitmene kalan tek iş taslakları onaylamak.
Onaylanmayan hiçbir soru öğrenciye görünmez — denetim her zaman eğitmende.

## Yapay zekânın üç rolü

| Rol | Ne yapar | Sınırı |
|---|---|---|
| **Class Assistant** | Öğrencinin materyal içi sorularını kaynak göstererek yanıtlar | Materyalde karşılığı yoksa cevap vermez |
| **Exam Mentor** | Öğrencinin denemesini bekler; kademeli, kaynaklı Sokratik ipucu verir; yanlış şıkta çelişen kaynak bölümünü gösterir | Cevabı asla doğrudan vermez; sınav modunda ipucu kapalı |
| **CourseGPT** | Eğitmenin kurduğu çerçevede soruları ve cevap anahtarlarını üretir — eğitmen soru yazmakla uğraşmaz | Yayın kararı veremez: eğitmen onaylamadan hiçbir soru öğrenciye açılmaz |

## Ekran görüntüleri

**Giriş** — geliştirme ortamı demo kartları (canlıda üniversite hesabı):

![Giriş ekranı](docs/screenshots/01-giris.png)

**Materyal yönetimi** — yükleme, doğrulama ve canlı işleme durumu:

![Materyaller](docs/screenshots/03-materyaller.png)

**Parça önizleme** — her parçanın yanında geldiği sayfa/satır aralığı. Cevaplardaki
kaynak referansı buradan üretilir, modelin kendi metninden değil:

![Parça önizleme](docs/screenshots/04-parca-onizleme.png)

**Asistan + Sokratik mod** (tasarım önizlemesi — cevap hattı bağlanınca gerçek veriye
geçecek, şeritte açıkça belirtiliyor):

![Asistan](docs/screenshots/05-asistan.png)

**Sınav provası** (tasarım önizlemesi):

![Sınav](docs/screenshots/06-sinav.png)

**İzolasyon kanıtı** — öğrenci, üye olmadığı dersin adresini elle yazarsa "yetkiniz yok"
değil **"Ders bulunamadı"** görür; dersin varlığı bile sızdırılmaz:

![İzolasyon](docs/screenshots/08-izolasyon-404.png)

Diğerleri: [ders listesi](docs/screenshots/02-ders-listesi.png) ·
[katılımcı yönetimi](docs/screenshots/07-katilimcilar.png)

## Yapılanlar ✅

Hepsi bu depoda çalışır ve testlidir — **92 otomatik test** + CI (ruff, mypy, pytest,
RLS izolasyon kanıtı):

- **İki katmanlı ders izolasyonu** — uygulama katmanı (istemciden gelen ders kimliği
  asla yetki sayılmaz) + PostgreSQL Row-Level Security. CI her koşuda politikayı
  **bilerek bozup** testin kırmızı yandığını da doğrular; yanmazsa yapı başarısız sayılır
- **Ders ve üyelik yönetimi** — öğrenci derse yalnız eğitmen davetiyle katılır
- **Materyal işleme hattı** — PDF/PPTX/Markdown/metin/kod; uzantı + boyut + **dosya
  imzası (magic byte)** doğrulaması; asenkron kuyruk + ayrı worker süreci; canlı durum
  rozetleri
- **Sayfa/slayt metadata'sını koruyan parçalama** — parçalama sayfa sınırını asla
  birleştirmez; kaynak referansının hammaddesi budur
- **Embedding + pgvector indeksleme** — multilingual-e5-large, ayrı vektör deposu yok
- **Assessment şeması** — konular, 4 tipli soru havuzu (draft → onay akışıyla), sınav
  oturumları, konu bazlı mastery (EWMA servisi yazıldı ve testli)
- **Örnek materyal paketi** — `sample_data/isletim-sistemleri/` (5 PDF + PPTX + 2 kod
  dosyası, bug_hunt için bilinçli hatalı örnek dahil)
- **6 ekranlı web arayüzü** — Türkçe, koyu tema, mobil uyumlu
- **Gereksinim analizi** — danışman taslağının 12 maddesi → numaralı FR izlenebilirliği

## Yapılacaklar ⏳

Sıradaki iş **cevap üretim hattı** — hedef: 10 Ağustos uçtan uca dikey demo kapısı:

- **Retrieval → LLM → guardrail zinciri** — hibrit arama (dense + full-text, RRF),
  LiteLLM (Groq → Gemini otomatik yedekli), mekanik atıf doğrulaması
- **Sokratik motorun bağlanması** — kademeli durum makinesi backend'de, arayüzdeki
  tasarım önizlemesi gerçek veriye geçer
- **Soru üretimi uçları** — eğitmen çerçevesi (biçim + örnek soru) → taslak üretimi →
  onay/red akışı
- **Sınav prova motoru** — süreli oturum, tek deneme, "neden yanlış" analizi, açık uçlu
  rubrik değerlendirme
- **Mastery entegrasyonu + eğitmen analitiği** — konu bazlı sınıf özeti tek sayfada
- **Supabase Auth** — DEV kimlikleri üretimde yapılandırma düzeyinde zaten reddediliyor
- **Değerlendirme altyapısı** — ≥50 soruluk gold set, Recall@5/@8, atıf hassasiyeti,
  injection ve sızıntı testleri; sayılar kalibrasyon/holdout ayrımıyla raporlanır
- **Bulut dağıtımı** — canlı URL + çevrimdışı demo yedeği

Teslim: **24 Ağustos 2026** · Özellik dondurma: 17 Ağustos · Tam görev listesi:
[`specs/001-course-assistant-mvp/tasks.md`](specs/001-course-assistant-mvp/tasks.md)

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
(öğrenci) demo kartına tıkla.

## Mimari — ne nerede çalışıyor

| Parça | Teknoloji | Nerede |
|---|---|---|
| Veritabanı | PostgreSQL 16 + pgvector (vektörler ayrı depo olmadan aynı DB'de) | :5432 |
| API | FastAPI / Python 3.12 — ders yönetimi, yükleme, yetkilendirme, izolasyon | :8000 |
| Worker | Ayrı süreç — parçalama + embedding (multilingual-e5-large) | — |
| Arayüz | Next.js (masaüstü + mobil tarayıcı, Türkçe birinci dil) | :3000 |

LangChain/LlamaIndex bilinçli olarak kullanılmaz — ince ve şeffaf işlem hattı düz
Python'la kurulur; gerekçeler [ARCHITECTURE.md](ARCHITECTURE.md)'de.

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
