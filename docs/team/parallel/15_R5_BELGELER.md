# R5 — Belgeler, kılavuzlar ve teslim paketi

> **Önce `10_OKU_ONCE_FAZ2.md`.** Bu belge yalnız senin şeridini anlatır.
> Dal: `feat/docs` · Worktree: `~/code/.dou-docs` · Port: **8025**
> Görevler: **T056 (kısmen), T057, T058, T059, T060**

```bash
cd ~/code/dou-lead && git fetch origin
git worktree add ~/code/.dou-docs -b feat/docs origin/main
cd ~/code/.dou-docs/apps/api && uv venv --python 3.12 && uv pip install -e ".[dev]" && cp ../../.env.example .env
cd ../web && bun install
```

---

## Neden bu şerit

Bu bir bitirme projesi. Jüri kodu satır satır okumayacak; **belgeleri okuyacak ve
demoyu izleyecek.** Bugün elde çok iyi bir sistem var ve onu anlatan hiçbir şey
yok: kurulum README'de eksik, eğitmen ne yapacağını bilmiyor, demo günü planı
kimsenin kafasında.

Ayrıca bir dürüstlük işi: `ARCHITECTURE.md`, `PLAN.md` ve `DESIGN.md` 9
Ağustos'tan önce yazıldı ve sistem o gün epey değişti. **Belgeler ürünü artık
tam tarif etmiyor.** Bunu kapatmak senin işin.

## Sahiplendiğin dosyalar

```
README.md                        senin
docs/runbook.md                  YENİ
docs/instructor-guide.md         YENİ
docs/student-guide.md            YENİ
docs/kvkk.md                     YENİ (metin; SAYFAYI lider yapar)
docs/demo-script.md              YENİ
ARCHITECTURE.md                  senin (gerçekle hizala)
PLAN.md                          senin (gerçekle hizala)
specs/001-course-assistant-mvp/quickstart.md   senin
specs/001-course-assistant-mvp/tasks.md        yalnız T057-T060 satırların
```

**Dokunma:** `apps/**` (kod), `evaluation/**` (R2), `docs/test-report.md` (R2),
`docs/security.md` (R1), `docs/deployment.md` (R3),
`docs/team/parallel/**` (lider), `DESIGN.md` (lider — frontend'in belgesi).

Koda dokunmuyorsun ama **kodu okumak zorundasın.** Yazdığın her cümlenin kodda
karşılığı olmalı.

---

## İş 0 — sistemi kendin çalıştır (yazmadan önce)

Ekran görüntüsü ve doğru anlatım için gerekli. Kendi portlarında:

```bash
# terminal 1
cd ~/code/.dou-docs/apps/api && uv run uvicorn app.main:app --port 8025
# terminal 2
cd ~/code/.dou-docs/apps/api && uv run python -m app.worker
# terminal 3
cd ~/code/.dou-docs/apps/web && NEXT_PUBLIC_API_URL=http://localhost:8025 bun run dev --port 3025
```

**Tuzak:** bu makinede `NEXT_PUBLIC_API_URL` ortamda `:9100`'e kayabiliyor;
yukarıdaki gibi açıkça ver. Playwright koştururken `bunx playwright` KULLANMA
(ayrı kopya indirir, "two different versions" hatası); `node_modules/.bin/playwright`.

Giriş: demo kimlikleri `supabase/seed_demo.sql`'de —
Ayşe Hoca (eğitmen) `11111111-…`, Burak (öğrenci) `22222222-…`.
Materyali olan bir ders: `COME 331`.

**Frontend lider tarafından aktif olarak değiştiriliyor.** Ekran görüntüsü
almadan önce `git pull origin main` yap; ekranlar bugün epey değişti.

## İş 1 — `docs/runbook.md` (T057) — en yüksek değerli belge

Demo günü tek başvuru kaynağı. Üç planlı:

- **Plan A — canlı bulut.** minReplicas=1, sabah warm-up, oturumlar önceden
  açık. Hangi URL, hangi hesap, hangi sırayla.
- **Plan B — telefon hotspot.** Ne zaman geçilir (hangi belirti), nasıl geçilir,
  ne kadar sürer.
- **Plan C — tam çevrimdışı.** `docker compose` fallback profili + dev-auth +
  önceden doldurulmuş `answer_cache`. R3 bunu kuruyor ve **gerçekten ağsız
  koşturuyor**; ölçümlerini ve kısıtlarını ondan al.

Her plan için: **geçiş kararı kimin, hangi belirtiyle, kaç saniyede.**
"İnternet yavaşsa" yetmez; "ilk soruya 15 sn'de cevap gelmezse B'ye geç" yeter.

Ayrıca:
- Sabah kontrol listesi (T-60 dk, T-15 dk, T-0)
- Bilinen kırılgan noktalar ve her birinin kaçış yolu
- Cold start süresi (R3 ölçüyor) — jüri beklerken ne söylenecek
- **Ne gösterilmeyecek:** yarım kalan ekranlar, ölçülmemiş sayılar

## İş 2 — `docs/demo-script.md` — sahne sahne anlatım

Runbook "bozulursa ne yapılır"; bu belge "her şey yolundayken ne anlatılır".

Ürünün tezi şu sırayla gösterilmeli:
1. Eğitmen materyal yükler, işlenme ilerlemesi görünür
2. Öğrenci soru sorar → **kaynaklı cevap, dosya adı + sayfa numarasıyla**
3. Öğrenci ödev sorusu sorar → **cevap yerine Sokratik merdiven**
4. Öğrenci "sadece söyle" der → **merdiven ilerlemez, nazikçe reddedilir**
5. Öğrenci ders dışı soru sorar → **nazik ret; bu bir hata değil, ÖZELLİK**
6. Sınav provası + "neden yanlış" + ilerleme

5. madde bu ürünün en özgün anı: **"bilmiyorum diyebilen asistan".** Bunu bir
kusur gibi değil, tasarım kararı olarak anlat. Her sahne için: ne söylenecek,
ne tıklanacak, ne görünecek, kaç saniye.

Her sahnenin sorusunu **önceden `answer_cache`'e doldurulacak** sorularla
eşleştir (R3'ün `fill_answer_cache.py` betiği) ve listeyi R3'e ver.

## İş 3 — `docs/instructor-guide.md` ve `docs/student-guide.md` (T058, T059)

Ekran görüntülü, adım adım. Eğitmen: ders açma, materyal yükleme + n/m
ilerleme, soru üretimi ve **onay** (onaylanmadan öğrenciye görünmez — bunu
vurgula), sınav yayınlama, analitik. Öğrenci: derse katılım, kaynaklı sohbet,
Sokratik mod, sınav provası, "neden yanlış?", mastery görünümü.

Ekran görüntülerini `docs/images/` altına koy. **Gerçek ekran görüntüsü al**,
çizim yapma. Kişisel veri görünmesin (demo hesapları kullan).

İkisinde de bir **"asistan ne yapmaz"** bölümü olsun: internetten bilgi
getirmez, eğitmenin yüklemediği kaynaktan cevap vermez, ödevi çözmez,
kaynaksız cevap göstermez. Beklentiyi doğru kurmak, sonradan "çalışmıyor"
denmesini engeller.

## İş 4 — `docs/kvkk.md` (T060'ın bir parçası)

Aydınlatma metni. **Hukuki metin uydurma** — yalnız kodda gerçekten olan veri
akışını anlat:
- Hangi kişisel veri işleniyor (e-posta, ad, ders üyeliği, sohbet mesajları,
  sınav cevapları, mastery skorları)
- Nerede saklanıyor, ne kadar süre
- **Soru metinlerinin `request_logs`'a yazılmadığı** (şemada serbest metin
  sütunu yok — yapısal önlem, kod referansıyla)
- Üçüncü taraf: LLM sağlayıcısına ne gidiyor (soru + retrieve edilen parçalar),
  ne gitmiyor (kimlik)
- Kullanıcının hakları ve başvuru yolu

Sayfayı **lider** yapacak (`apps/web` senin değil) — metni markdown olarak ver,
raporunda "sayfa gerekiyor" diye belirt.

## İş 5 — `ARCHITECTURE.md` ve `PLAN.md`'yi gerçekle hizala

Belgeler 9 Ağustos'tan önce yazıldı. Kodu oku, farkları bul, **tek yönde hizala**
ve neyi neden değiştirdiğini yaz. Bilinen ayrışmalar:

- ARCHITECTURE §5 atıf şemasındaki `claim` alanı: `contracts.Citation`'da
  bilinçli olarak YOK, zarf katmanında (`schemas/chat.py`) taşınıyor.
  Bunun gerekçesi `contracts.py`'de yazılı — belgeye taşı.
- `hints[]` dizisi: zarfta VAR ve Sokratik turda doluyor.
- Kanıt eşiği artık **0.81** ve kalibre edildi; holdout doğrulamadı.
- `SessionDep` `scope="function"` — işlem yanıttan önce commit ediliyor.
- Worker tetiği: süreç içi + (R3'ten sonra) HTTP.

**Uygulanmamış bir kararı "yapılacak" diye bırakacaksan belgede AÇIKÇA
"uygulanmadı" yaz.** Sessizce duran bir iddia yalandır.

## İş 6 — `README.md` ve `quickstart.md` (T060)

README: proje ne, canlı URL, `docker compose up` ile kurulum, teslim paketi
haritası (hangi belge nerede), ekip. Jüri buradan başlayacak.

`quickstart.md`: sıfırdan kurulumu **gerçekten baştan koştur** ve her adımın
çalıştığını doğrula. Bugün bilinen bir tuzak var: dev veritabanı `dou_synapse`
`0003`'ü eksik koşuyordu ve sohbet 500 veriyordu. Quickstart bütün
migration'ları sırayla koşturuyor mu, gerçekten kontrol et.

## Lidere iletmen gerekenler

- KVKK sayfası (metin hazır, sayfa lazım)
- Arayüzde yanlış/eksik gördüğün her şey (ekran görüntüsü alırken çok
  göreceksin — bunlar değerli, hepsini yaz)
- DESIGN.md ile kod arasında fark görürsen (DESIGN.md lider'in)

## Bitti sayılma ölçütün

- [ ] Sistemi kendin çalıştırdın, ekran görüntüleri gerçek
- [ ] `runbook.md`: üç plan, geçiş kararı belirtiyle tanımlı
- [ ] `demo-script.md`: altı sahne, her biri süreli ve replikli
- [ ] İki kılavuz ekran görüntülü, "asistan ne yapmaz" bölümlü
- [ ] `kvkk.md` yalnız kodda gerçekten olanı anlatıyor
- [ ] `ARCHITECTURE.md` + `PLAN.md` ürünle uyumlu; uygulanmayanlar "uygulanmadı"
- [ ] `README.md` + `quickstart.md` sıfırdan koşuldu ve çalıştı

---
---

# R5 ŞERİT RAPORU — 9 Ağustos 2026

Dal: `feat/docs` · Worktree: `~/code/.dou-docs` · Port: 8025
Rebase tabanı: `9406e6d` · Commit'ler: 5 · Backend testleri: **478 yeşil** · mypy temiz · ruff temiz

## 1. Teslim edilenler

| Dosya | Durum |
|---|---|
| `docs/runbook.md` | YENİ — A/B/C planı, geçiş ölçütleri, T-60/T-15/T-0, ölçülmüş cold start |
| `docs/demo-script.md` | YENİ — altı sahne, replikli/süreli + `answer_cache` soru listesi |
| `docs/instructor-guide.md` | YENİ — ekran görüntülü, "asistan ne yapmaz" bölümlü |
| `docs/student-guide.md` | YENİ — ekran görüntülü, "asistan ne yapmaz" bölümlü |
| `docs/kvkk.md` | YENİ — yalnız kodda olan veri akışı + 6 maddelik "uygulanmayanlar" |
| `docs/images/` | YENİ — **15 gerçek ekran görüntüsü** (çizim yok) |
| `ARCHITECTURE.md` | Kodla hizalandı + **§10 Uygulanmayanlar** (12 madde, sahipli) |
| `PLAN.md` | §2'ye gerçekleşme, §5'e ölçülen değer sütunu + teslim paketi haritası |
| `README.md` | 92→478 test, tamamlananlar, gerçek ekran görüntüleri, belge haritası |
| `specs/.../quickstart.md` | Sıfırdan koşuldu; iki kusur bulundu ve düzeltildi |
| `specs/.../tasks.md` | Yalnız T057-T060 satırları |

`openapi.json` yeniden export EDİLMEDİ — bu şerit hiçbir uç eklemedi; canlı `/openapi.json`
24 yol döndürüyor ve dosyayla uyumlu.

## 2. LİDERE — arayüzde görülenler

**A. Üç ekran hâlâ tasarım önizlemesi, arka uçları çalışıyor.** En kritik madde.

| Ekran | Arka uç durumu (bugün ölçüldü) |
|---|---|
| `courses/[id]/questions` | `GET/POST .../questions`, `/approve`, `/reject` **çalışıyor** |
| `courses/[id]/exam` | `POST /exams`, `/answers`, `/finish`, `/hint` **çalışıyor** |
| `courses/[id]/analytics` | `/analytics/me` ve `/analytics/class` **çalışıyor** |

Üçü de `PreviewBanner` taşıyor ve örnek veri gösteriyor. **Sonuç: demo senaryosunun 6.
sahnesi (sınav + "neden yanlış") bugün gösterilemiyor.** Ölçülen arka uç davranışı
`docs/demo-script.md` Sahne 6'da tabloyla duruyor; ekranlar bağlanırsa sahne olduğu gibi
geçerli.

**B. KVKK sayfası gerekiyor.** Metin `docs/kvkk.md`'de hazır, markdown. Sayfa
`apps/web/app/privacy/page.tsx`. *Not: `tasks.md` T060 bu ayağı **R4'e** veriyor, benim
brief'im (`15_R5_BELGELER.md`) **lidere** veriyor. İkisi çelişiyor — kimin olduğunu netleştirin.*

**C. Küçük arayüz gözlemleri** (ekran görüntüsü alırken görüldü, hiçbiri engelleyici değil):

1. Sohbette atıf kartları **ilk üç parçayı** gösteriyor; sahte sağlayıcı ayrım yapmadığı
   için üçüncü kart bazen alakasız oluyor (ör. "süreç vs thread" sorusunda
   `02-cpu-scheduling.pdf`). Gerçek anahtarla daralması beklenir; demo öncesi kontrol edilmeli.
2. Sokratik oturumda **soru başlığı her turda tekrar ediyor** (sohbet listesinde aynı
   başlıkla üç kayıt). Ekran doğru çalışıyor, liste gürültülü görünüyor.
3. Ders listesi dev veritabanında onlarca `E2E Test Dersi`/`Curutme Testi` içeriyor.
   Demo öncesi temiz bir liste gerekiyor (runbook §4 madde 8).

## 3. GRUBA — sahipliğim dışında bulunan kusurlar

| # | Nerede | Ne | Kime |
|---|---|---|---|
| 1 | `supabase/tests/rls_isolation.sql` | Quickstart'ın yazdığı sırada (seed'den sonra) **`duplicate key` ile düşüyor**; testin sabit UUID'leri `seed_demo.sql` ile aynı. Temiz DB'de 8/8 PASS. CI temiz DB kurduğu için görmüyor. Kalıcı çözüm: `INSERT ... ON CONFLICT DO NOTHING` | R1 / lider |
| 2 | `app/modules/generation/fake.py` | `FakeLlmClient` **soru üretim şemasını bilmiyor** → anahtarsız ortamda soru üretimi `"yanıtta 'questions' dizisi yok"` diyerek **0 soru** döndürüyor. Çevrimdışı demoda (Plan C) sınav akışı bu yüzden önceden onaylanmış sorulara muhtaç | R4 |
| 3 | `api/chat.py` + `guardrails/chain.py` | **İki orkestratör.** `AnswerPipeline` yalnız testlerde koşuyor; canlı uç kendi kopyasını taşıyor (regen `strict_retry`'sız, farklı şablon, farklı ret metni). Davranış iki yolda da fail-closed, ama Anayasa XI ihlali ve şimdiden ayrışmış | R4 |
| 4 | kanıt kapısı | **`out_of_scope` canlı yolda ulaşılamaz** — kapı LLM'den önce kapanıyor, her kapsam dışı soru `insufficient_context` dönüyor (3/3 ölçüldü). İki sonucu: kullanıcı daha az isabetli ret metnini görüyor; **eğitmen analitiğindeki kapsam dışı ret oranı %0 görünüyor** (`out_of_scope_count: 0`, `insufficient_context_count: 3`) | R2 / R4 |
| 5 | `apps/api/app/api/chat.py` | İki **bayat yorum**: `_has_evidence` "eşik KALİBRE EDİLMEMİŞTİR" diyor (edildi); `_opening_question` "student_attempt imzada yok" diyor (var ve geçiriliyor) | lider |
| 6 | `apps/api/app/modules/retrieval/service.py` | Modül docstring'i hâlâ "eşik kalibre edilmemiştir, `evidence_threshold = 0.35`" diyor; değer artık sağlayıcıya göre 0.81/0.10 | R1 |
| 7 | `docker-compose.yml` | API `postgres` **superuser'ı** ile bağlanıyor → RLS atlanıyor (superuser `FORCE`'u da atlar). Bu yığında izolasyon kanıtı alınamaz; Plan C'de izolasyon sahnesi gösterilemez | R3 |
| 8 | `10_OKU_ONCE_FAZ2.md` §1 ve §4 | **"19 tablo" yanlış.** Migration'lar sıfırdan koşulduğunda **15 tablo** çıkıyor (0001:6, 0003:4, 0004:5, 0005:0 — 0005 yalnız politika ekliyor). Belgedeki "19 tablo görmelisin" her şeridi sağlam bir DB'yi bozuk sanmaya itiyor | lider |
| 9 | dev veritabanı `dou_synapse` | `0005`'in `request_logs_instructor_read` politikası **eksikti** → eğitmen analitiği sessizce boş dönüyordu. **R5 uyguladı** (`psql -d dou_synapse -f supabase/migrations/0005_analytics.sql`). Şemayı değiştiren tek müdahalem budur, bildiriyorum | lider |

## 4. R3'e — bu belgelerin beklediği girdiler

1. `fill_answer_cache.py` — doldurulacak soru listesi `docs/demo-script.md` sonundadır.
2. **Ağsız koşu ölçümü**: Compose yığını gerçekten Wi-Fi kapalıyken kalkıyor mu, cold start
   kaç saniye. Runbook §2'deki sayılar **yerel makinede** ölçüldü, konteynerde değil.
3. **Model imaja gömme.** Bugün fastembed modeli (2,1 GB) macOS'ta `$TMPDIR/fastembed_cache`
   altına iniyor ve işletim sistemi orayı temizliyor. `EMBEDDING_CACHE_DIR` ayarı zaten var
   ama `.env.example`'da yok. Demo sabahı önbellek silinmişse hotspot'ta model inmez.

## 5. Ölçülenler (hepsi bugün, yerel makine)

| Ölçüm | Değer |
|---|---|
| API ayağa kalkma | 0,9 sn |
| İlk soru (2,1 GB model yükleme dahil) | **11,7 sn** |
| İkinci soru (sıcak) | 0,08 sn |
| Sıcak sorgular (önbelleksiz, 5 soru) | 0,086 – 0,409 sn |
| Önbellek isabeti | 0,011 sn |
| İlk materyal yükleme | 19,1 sn · sonrakiler 2,1 – 6,7 sn |
| `sample_data` ingesti | 8/8 `completed`, **33 chunk** |
| Backend testleri | **478 geçti** (103 sn) |
| Migration'lar sıfırdan | 4 dosya, hatasız, **15 tablo** |
| RLS izolasyon kanıtı (temiz DB) | **8/8 PASS** |

**Kanıt eşiği, iki sağlayıcıda ölçüldü:**

| Sağlayıcı | İlgili sorgu | Konu dışı | Eşik | Ayırıyor mu |
|---|---|---|---|---|
| `fastembed` (33 chunk e5 korpusu) | 0,8130 – 0,8699 | 0,7238 – 0,7587 | 0,81 | **Evet** |
| `hashing` (COME 331) | 0,1715 – 0,1951 | **0,1789** | 0,10 | **Hayır** — konu dışı sorgu ilgili birinden yüksek |

**Pooling riski nokta kontrolü:** fastembed 0.8.0 (mean pooling) ile `dou_synapse_eval_e5`
korpusuna sorulan 5 sonda sorgu kalibrasyon bandında kaldı ve eşik doğru ayırdı. Yani
**bu korpus-sürüm çifti bugün tutarlı.** Bu kalibrasyonun yeniden koşulması DEĞİLDİR;
sürüm damgası ihtiyacı (R4, `0006`) aynen duruyor.

## 6. KOŞULMADI — dürüstlük notu

- **Gerçek LLM ile hiçbir şey ölçülmedi.** Anahtar yok; bütün koşular deterministik sahte
  sağlayıcıyla yapıldı. Atıflar, guardrail zinciri, kanıt kapısı ve Sokratik merdiven
  gerçek yolu izliyor — **yalnız cevabın düzyazısı** modelden gelmiyor. Ekran
  görüntülerindeki cevap metinleri bu yüzden şablon gibi okunuyor; gerçek anahtar
  gelince **9 ve 12 numaralı görüntüler yeniden çekilmeli.**
- Uçtan uca p95, Recall@5/@8, citation precision, faithfulness, injection testleri: R2/R4.
- Konteynerde/ağsız cold start: R3.
- Sınav ve analitik ekranları **arayüzde** doğrulanmadı (önizleme oldukları için);
  yalnız arka uçları `curl` ile doğrulandı.

## 7. Yapılan tek şema müdahalesi

Paylaşılan dev veritabanı `dou_synapse`'e `0005_analytics.sql` uygulandı (§3 madde 9).
Yalnız bir SELECT politikası ve bir COMMENT ekler; veri değiştirmez. Bunu yapmasaydım
eğitmen analitiği ekran görüntüsü boş çıkardı ve sebebini yanlış yazardım.

Ayrıca **kendi demo veritabanımı** kurdum (`dou_synapse_docs`, fastembed korpuslu) —
ölçüm anında liderin `dou_synapse`'indeki chunk'lar `hashing` ile gömülüydü ve orada
kaynaklı cevap alınamıyordu. Liderin verisine dokunulmadı; bütün ekran görüntüleri
`dou_synapse_docs` üzerinden alındı (COME 331, 8 materyal, 33 chunk, e5).

> **Sonradan gelen düzeltme (`c4d4c7b`, 17:40):** lider `dou_synapse`'teki 54 chunk'ı
> gerçek E5 modeliyle yerinde yeniden embed etti. Yani yukarıdaki `hashing` ölçümü
> **o andaki paylaşılan korpusa** aittir; bugün `dou_synapse` de fastembed uzayındadır.
> Ölçümün sonucu geçersizleşmedi — `hashing`'in bu materyalde ayırt etme gücü taşımadığı
> bulgusu duruyor ve liderin commit gövdesi de aynı sonuca varıyor. Değişen tek şey,
> paylaşılan veritabanının artık o sağlayıcıda olmaması.
>
> **§3 madde 8 hâlâ açık:** `10_OKU_ONCE_FAZ2.md` satır 20 ve 133'teki "19 tablo"
> ifadesi bu commit'te düzeltilmedi. Doğrusu **15**.
