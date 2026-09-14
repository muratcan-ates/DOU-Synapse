# Gece raporu — 14 Eylül 2026

Yazılış 23:45. Kural: ölçülmeyen "çalışıyor" diye yazılmaz; koşulmayan iş KOŞULMADI der.
Saatli plan `YOL-HARITASI-16-EYLUL.md`'de; bu belge yalnız gecenin sonucudur.

## 1. main'e giren 12 commit

`main` = `017-completion-integration` = `018-codex-production-line` = **42566f3**

| Commit | Ne | Kanıt |
|---|---|---|
| `292bf8e` | CI Storage RLS kök nedeni: test koruması Docker servis konteynerinin `172.x` adresini reddediyordu | Bu düzeltmeden sonra CI'da **API işi yeşil** (run 34892983070) |
| `16efd97` | `/docs` belge sayfası 14 Eylül açık kabuğuna geçti | Açık/koyu ekran görüntüsü |
| `c6e289d` | Plan C docker'sız yol, `DOU_DEMO_OFFLINE=1`, yedek betiği, önbellek betiği düzeltmesi | `backup_demo.sh` provası: backup-complete |
| `a5424a5` | Gereksinim analizi v2 + yol haritası + 12 yeni ekran görüntüsü | docs_check yeşil |
| `ae2d374` | docs_check işaret hizası | rc=0 |
| `7ab347c` | **Telefonda sohbet taşması + ulaşılmaz mobil menü** | 375×812 koyu tema: scrollWidth 567→375; menüye 30+ sekme→4, halka 2px |
| `b06736a` | Sınav sayacı etiketi `2 / 3` → `2/3` | Kabuk turu etiketi bozmuştu; flows.spec:704 bu yüzden kırılmıştı |
| `d652809` | G1 koşucusu + CI e2e kök neden tablosu | — |
| `6ac2a03` | **P2 birleşti** (öğrenci sınav akışı e2e paketi) | 11 arayüz etiketi statik doğrulandı |
| `1b96a0d` | **P1 birleşti**, üç çakışma main lehine çözüldü | pytest 2139 · tsc 0 · bun 632 · contrast · docs_check |
| `493337b` | G1 koşu kimliği UUID | provenance.py:69 UUID istiyor |
| `42566f3` | P2'nin `test.skip`'i `@ekran` etiketine çevrildi | CI kapısının kendi komutu yerelde koşuldu |

## 2. CI durumu

Son tam koşu (`1b96a0d`): **API — lint, tip, test ✅ · API imajı ✅ · Belgeler ✅ · Web ❌**
Web'in tek düşen adımı "E2E süitinde devre dışı bırakılmış test yok" kapısıydı; `42566f3`
onu kapattı. Uçtan uca işi web kırmızı olduğu için atlandı — bir sonraki koşuda çalışacak.

**Uçtan uca süitin ilk gerçek koşusu (run 34884025385): 72 geçti, 9 düştü, 1 kararsız.**
Üçü gerçek regresyondu, düzeltildi. Kalan altısı düzenek boşluğu: `run_owned_e2e.py:72`
tek API süreci açıyor ve testlerin istediği iki simülasyon bayrağını kurmuyor. İki bayrak
birlikte açılamaz (`provider_fallback.py:196` bayrak açıkken her çağrıda 429 simüle eder),
yani fazlı koşu gerekiyor. Gerekçesi ve çözüm planı yol haritasında; sunum sonrasına alındı.

## 3. Gece boyunca kendiliğinden koşan iş

`scratchpad/kota-gozcusu.sh` 15 dakikada bir Groq kotasını yokluyor. 23:32'de kota açıldı
ve sırayla şunları başlattı:

1. **`answer_cache` doldurma** — çevrimdışı demo sigortası. Sabah kontrol:
   `psql -d dou_demo -Atc "select count(*) from answer_cache"` · günlük `scratchpad/fill_final.log`
2. **G1 gerçek model holdout değerlendirmesi** — günlük `scratchpad/g1_final.log`,
   sonuçlar `~/.cache/dou-synapse/g1/results`

G1 hattının tamamı kuruldu ve tek tek doğrulandı: `dou_eval` veritabanı (22 belge,
167 parça), korpus özeti, ön kontrol (tüm denetimler geçti), API açılışı, ders uçları 200.
**Gece 23:28'de tek engel Groq kotasıydı** (`/chat` → 429); eval anahtarı ayrı olsa da
aynı hesabın kotasını paylaşıyor.

## 3.1 Gecenin en kritik bulgusu: jeton kotası demoyu durdurabilir

Akşam boyunca gördüğüm `429`'ları Groq'a yazmıştım; **yanlıştı.** Hata gövdesi şunu
diyor: `agent_quota_exhausted — "Günlük kişisel AI kullanım kotan doldu."` Yani sınır
bizim kendi ürün kotamız.

Ölçülenler:

| Ölçüm | Değer | Kaynak |
|---|---|---|
| Öğrenci günlük tavanı | **50.000 jeton** | `0015_role_aware_course_agent.sql` — veritabanı sabiti; politikayla aşılamaz (aşılırsa exception) |
| Eğitmen günlük tavanı | 200.000 jeton | aynı göç |
| İstek başına gerçek tüketim | **~4.500 jeton** | 14 Eyl İstanbul günü: 10 istek / 44.862 jeton |
| Öğrenci başına günlük soru | **~11** | yukarıdaki ikisinden |
| Gün sınırı | `Europe/Istanbul` gece yarısı | `date_trunc('day', now() AT TIME ZONE 'Europe/Istanbul')` |

**Demo riski:** jüri senaryosunda ~10 soru var. Tek öğrenci hesabıyla demo tam sınırda
koşar; provada birkaç soru harcanmışsa sunum ortasında ekranda *"Günlük kişisel AI
kullanım kotan doldu"* yazar. Politika ekranından yükseltmek İŞE YARAMAZ — tavan
veritabanında.

**Gerçek koruma `answer_cache`.** Önbellekten dönen cevap LLM'e gitmez, dolayısıyla jeton
harcamaz. Yani önbellek yalnız "internet giderse" sigortası değil, **kota sigortası**.

Bu yüzden doldurma dört sentetik öğrenciye bölündü (`burak2..4`, demo veritabanına
eklendi): her biri kendi 50.000'ini kullanır, önbellek ise kullanıcıdan bağımsız
anahtarlandığı için sonuç tek kullanıcıyla aynıdır. Depodaki `demo_questions.json`
senaryonun kanonik hâli olarak DEĞİŞMEDİ; bölünmüş liste yalnız doldurma aracıdır.

## 3.2 GPT'nin kampüs tasarımı main'e alındı

Murat'ın kararı: GPT'nin tasarımı esas. `025-campus-ui` dalının **tasarım** commit'i
(`ffd9bf7`, 61 dosya) main'e merge edildi; **GPT'nin dalına dokunulmadı** (`origin/025-campus-ui`
hâlâ `3e7aa8b`) ve GPT çalışmaya devam ediyor — yeni hâli yarın aynı şekilde çekilecek,
git artımlı birleştirdiği için tekrar iş çıkmaz.

Dalın ikinci commit'i **bilerek alınmadı**, ayrı kararlar:
- `next` 16.3.1 → 16.3.3 güvenlik yaması (+ `bun.lock`) — bağımlılık kararı Murat'ın.
- GPT'nin kendi CI kablolaması + dossier 101. Not: GPT'nin CI çözümü bazı yerlerde
  benimkinden **iyi** — `fetch-depth: 0` ekleyip diff-coverage raporunu gerçekten
  koşturuyor ve Storage RLS testini korumayı gevşetmek yerine Postgres konteynerinin
  İÇİNDE çalıştırıyor. Benim çözümüm (292bf8e + dossier 151) zaten main'de ve CI'da
  yeşil; 36 saat kala değiştirmedim. Sunum sonrası GPT'ninkine geçilebilir.

İki çakışma çıktı, ikisi de bu gecenin telefon düzeltmeleriyle aynı dosyalarda:
`app-shell.tsx`'te GPT'nin sürümünde mobil çubuk yine DOM'un sonundaydı — öne alındı.
`chat/page.tsx`'te GPT zaten `minmax(0,1fr)` + `min-w-0` kullanmış, düzeltme korunuyor.

Doğrulandı (gerçek tarayıcı, 375×812, koyu tema): taşma yok (375/375), mobil menüye
**4 sekme**, odak halkası 2px. Kapılar: tsc 0 · bun 632 · contrast AA.

**Sonuç:** `docs/images` altındaki 12 görüntü yine eskidi (eski kabuğu gösteriyor).
Önbellek doldurma bitince yeni tasarımla yeniden çekilecek.

## 4. Sabah ilk 30 dakika

- [ ] `scratchpad/gozcu.log` son satırı: doldurma ve G1 koştu mu?
- [ ] Koştuysa `g1_final.log` içindeki sayılar `docs/test-report.md`'ye **gerçek model** etiketiyle işlenir
- [ ] Koşmadıysa sebebi yazılır (kota/başka) ve `sh scripts/demo/run_g1_eval.sh --set holdout --max-requests 40` elle koşulur
- [ ] CI son koşusu: web ve uçtan uca yeşil mi
- [ ] Önbellekte olmayan sorular demo senaryosundan çıkarılır — `inode ne saklar?` zaten
      `insufficient_context` alıyor (demo materyalinde inode yok), listeden çıkmalı
- [ ] Gereksinim v2 son okuma → hocaya gönderim

## 5. Murat'a kalan işler (ben yapamam)

| # | İş | Neden bende değil |
|---|---|---|
| 1 | Video (10–15 dk) ve OneDrive bağlantısı | Fiziksel |
| 2 | `docs/references.md` kitap satırları | Gerçek kaynak bilgisi sende |
| 3 | Yönetişim karantinası onayı | Denetim kaydı silme; onayın şart |
| 4 | Yedek klasörünü USB/iCloud'a kopyalama | Fiziksel |
| 5 | 025-campus-ui merge kararı | Tasarım GPT'de, karar senin |
| 6 | Gemini anahtarı (isteğe bağlı) | `scratchpad/gemini-kur.sh` — Groq kotası dolarsa demoyu ayakta tutar |

## 6. Ölçülmemiş / bilinmeyen

- Uçtan uca süitin **bayrağa bağlı 6 testi** hiç koşmadı (düzenek boşluğu, §2).
- Gerçek modelle holdout metrikleri bu satır yazılırken **koşuluyordu**; sonuç
  `g1_final.log`'da. Bu belgede sayı YOK, çünkü ölçüm bitmeden yazılmaz.
- Groq kotasının günlük mü dakikalık mı olduğu ölçülmedi; 23:32'de açıldığı gözlendi.
