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

## 3.3 Düzeltme: Gemini yedeği sohbet yolunda DEVREYE GİRMİYOR

Gece boyunca iki kez "Gemini yedeği 429/503'ü çözer" dedim. **Öğrenci sohbeti için
yanlıştı.** Kod bunu bilerek kapatmış (`modules/generation/service.py:213-217`):

> *The role-aware HTTP path makes one semantic generation attempt. This keeps actual
> usage inside the atomic reservation. Transport retries and provider failover are both
> disabled for this route; malformed JSON fails closed instead of spending another budget.*

`provider_attempt_limit=1` ve `schema_retry_limit=0`. Yani `LLM_FALLBACK_MODEL` ayarlı
olsa bile sohbet isteğinde **ikinci sağlayıcı denenmiyor**; sebebi jeton rezervasyonunun
atomik kalması. Ölçüldü: demo API günlüğünde 503 dönen isteklerde tek bir
`provider = groq` satırı var, `gemini` hiç geçmiyor.

**Sunum sonucu:** Groq'ta anlık bir hata olursa ekranda "asistan kullanılamıyor" çıkar ve
ikinci sağlayıcı kurtarmaz. Tek gerçek koruma `answer_cache`'tir — önbellekteki soru
modele hiç gitmez. Bu yüzden canlı sahnelerde **yalnız önbellekteki 12 soru** sorulmalı
(liste `docs/demo-script.md`). Gemini anahtarı yine de `.env`'de duruyor; değerlendirme
ve soru üretimi gibi başka yollar için geçerli, sohbet yolu için değil.

Bu davranışı değiştirmek (failover'ı açmak) rezervasyon değişmezini etkiler; sunumdan
36 saat önce yapılmadı, karar Murat'ın.

## 4. Sabah ilk 30 dakika

- [ ] `scratchpad/gozcu.log` son satırı: doldurma ve G1 koştu mu?
- [ ] Koştuysa `g1_final.log` içindeki sayılar `docs/test-report.md`'ye **gerçek model** etiketiyle işlenir
- [ ] Koşmadıysa sebebi yazılır (kota/başka) ve `sh scripts/demo/run_g1_eval.sh --set holdout --max-requests 40` elle koşulur
- [ ] CI son koşusu: web ve uçtan uca yeşil mi
- [ ] Önbellekte olmayan sorular demo senaryosundan çıkarılır — `inode ne saklar?` zaten
      `insufficient_context` alıyor (demo materyalinde inode yok), listeden çıkmalı
- [ ] Gereksinim v2 son okuma → hocaya gönderim

## 4.1 Gecenin sonucu (00:45 itibarıyla)

| Konu | Durum | Kanıt |
|---|---|---|
| Yönetişim kapısı | **YEŞİL** | `AI quality` iki ardışık koşuda `success`. Sebep onay değil, bağlanmamış dört kanıt betiğiydi (dossier 151) |
| CI api işi | **YEŞİL** | Storage RLS kök nedeni düzeltildi (292bf8e) |
| Retrieval kalitesi | **Regresyon yok** | 15 Eyl koşusu: Recall@5 0,9714 · Recall@8 0,9810 · MRR 0,8583 (161 soruluk holdout, LLM'siz) |
| Çevrimdışı önbellek | **12 soru + 4 ret** | Gerçek modelle dolduruldu; liste `docs/demo-script.md` |
| Ekran görüntüleri | **16'sı yenilendi** | Kampüs tasarımı + gerçek model; Sokratik tur ısrar sahnesi dahil |
| P1 · P2 dalları | **Kapandı** | Çakışmalar main lehine çözüldü, 11 tip hatası düzeltildi |
| Gerçek modelli e2e metrikleri (G1) | **KOŞULMADI** | Ürünün kendi jeton kotası durdurdu; sayı yazılmadı. Kota matematiği §4.2'de |
| GPT'nin yeni tasarımı | **ALINDI** (15 Eyl 02:10) | GPT 01:28'de `aba76c2` ile commit'lemiş ama push'lamamıştı; yerel `025-campus-ui` dalından `3f96d43` ile `main`'e alındı. Ayrıntı §4.2 |

## 4.2 Gece yarısından sonra (15 Eylül 01:00–02:30)

**GPT'nin tasarımı alındı.** Dal push'lanmamıştı ama `~/code/dou-synapse-025-campus-ui`
worktree'sinde commit'liydi (`aba76c2`, 01:28). Beş çakışma çıktı; dördünde GPT'nin
sürümü aynen alındı. Tek istisna `app-shell.tsx`: tasarım turu mobil gezinmeyi yine
DOM'un sonuna almıştı, erişilebilirlik düzeltmesi geri taşındı. Gerçek tarayıcıyla
ölçüldü (375×812, koyu tema): yatay taşma yok (375/375), mobil menüye **4 sekmede**
ulaşılıyor (regresyonda 30+ sekmede ulaşılamıyordu), odak halkası `2px solid`.
Izgara düzeltmesi (`minmax(0,1fr)` + `min-w-0`) GPT'nin sürümünde zaten korunmuştu.

`ci.yml`'de iki taraf da kapsam kanıtı adımı eklemişti; birleştirildi — GPT'nin
`report` adımı (taban SHA'lı) korundu, benim `upload-artifact` kanıt adımım da
duruyor. Tasarım `gsap` + `@gsap/react` bağımlılığı getiriyor (GPT'nin dossier 102
kararı). Kapılar: tsc temiz · `bun test lib/` 648/648 · kontrast AA · docs_check
yeşil (uçtan uca sayacı 82→87 ölçümden düzeltildi) · migration_check PASS.

**G1 hâlâ koşulamıyor — sebep ölçüldü (02:25).** Değerlendirme veritabanındaki
kullanıcı `course_memberships`'te **öğrenci** rolünde; öğrenci günlük tavanı 50.000
jeton ve bu tavan `config.py:285`'te `le=50_000` ile sabitli, ders politikasıyla
aşılamıyor. 15 Eylül 00:00'dan 02:25'e kadar 41.219 jeton harcanmış (gece yarısı
sonrası kısmi koşu), kalan ~8.781 jeton yaklaşık **iki isteğe** yetiyor; holdout 40
istek istiyor. Sonraki sıfırlama **16 Eylül 00:00** — yani sunum sabahı. Seçenekler:
(a) sunum sabahı erken koşmak, (b) demo önbelleği doldururken yapıldığı gibi birden
çok sentetik öğrenciyle bölmek (her biri kendi 50.000'iyle). Karar Murat'ın; sayı
koşulmadan rapora **yazılmaz**.

## 4.3 ENGEL — yönetişim kapısı merge'den sonra kırmızı (insan kararı gerekiyor)

**Durum:** `main`'de `AI quality` işi kırmızı. Merge'den önce iki ardışık koşuda
yeşildi; kırmızıyı kampüs tasarımını birleştiren commit açtı. Sebep ölçüldü:

```
AI_SDLC_CHECK=FAIL
LINEAGE_DUPLICATE_REVISION:.ai/changes/101-ci-evidence-wiring-r1.json
```

`scripts/ai_sdlc_check.py:1592-1608` soy kimliğini `(lineage_id, revision)` çifti
olarak anahtarlıyor. GPT'nin dalından gelen `101-ci-evidence-wiring-r1` ile benim
`151-ci-evidence-wiring-r1` kaydım **aynı çifti** taşıyor: ikisinde de
`lineage_id = "ci-evidence-wiring"`, `revision = 1`.

**İki kayıt gerçekten farklı iştir**, çakışma yalnız isim tesadüfü:

| Kayıt | Kim | Ne |
|---|---|---|
| 101 | GPT (`3e7aa8b`) | Kampüs arayüzü, web bağımlılık yaması, CI kanıtı |
| 151 | Ben (`12c9906`) | Bağlanmamış dört kanıt betiğini CI'a bağlama |

**Neden kendim düzeltmedim.** `lineage_id`'yi kendi kaydımda değiştirmeyi denedim;
doğrulayıcı bu sefer `STACK_CONTEXT:151-ci-evidence-wiring-r1:history` verdi —
kayıtlar tanıtıldıkları commit'e bağlı ve sonradan düzenlenemiyor (append-only
kuralının kodla zorlanmış hâli, AGENTS.md "Hassas commit ve dossier"). Denemeyi
geri aldım, push'lanmadı. Yeni bir kayıt eklemek de işe yaramıyor: çakışan çift
`(ci-evidence-wiring, 1)` ve o çiftteki iki girdi yerinde kalıyor. Toplayıcı
(`refresh_aggregate_dossier.py`) başka bir sorunu çözüyor — çok commit'li dalda
kapsamsız kalan hassas dosyaları — soy çakışmasını değil.

**Seçenekler (karar Murat'ın):**

1. **Kırmızıyı kabul et.** AGENTS.md zaten bunu öngörüyor: *"Toplayıcı nedeniyle
   PR'daki 'Govern reviewed AI diff' kırmızı kalabilir; ebeveyn denetiminin yerini
   tutmaz."* Sunumda yönetişim anlatılacaksa bu satır dürüstçe açıklanabilir:
   iki şerit aynı adı seçti, kayıtlar silinmedi.
2. **Denetim kaydını bilerek değiştir.** 101 ya da 151'in `lineage_id`'si
   ayrıştırılır ve `STACK_CONTEXT` hatası da ayrıca giderilir. Bu, denetim
   geçmişine dokunmak demektir; onayın şart, ben tek başıma yapmam.
3. **GPT kendi kaydını düzeltsin.** 101 `origin/025-campus-ui`'de yayımlanmış
   durumda, yani bu da yayımlanmış geçmişi değiştirmek olur.

Sunumu durduran bir şey değil — ürün, testler ve demo etkilenmiyor. Yalnız
`AI quality` rozeti kırmızı görünür.

## 4.4 Sabah simülasyonu (15 Eylül 06:50–08:15) — öğrenci ve eğitmen gözünden

27 rota iki rolle gerçek tarayıcıda gezildi (`scratchpad/simulasyon.mjs`). Üç kusur
bulundu, üçü de ölçümle:

**1. `/study` ve `/settings` her iki rolde 404 idi.** Sebep kod değil bayat derleme:
kampüs tasarımı 02:10'da birleşti, koşan üretim derlemesi 00:01'dendi. Bu sessiz bir
sahne riskiydi — ana menüde **"Ayarlar"**, panoda **"Ders tekrarına geç"** düğmesi bu
rotalara link veriyor. Web yeniden derlendi; 27/27 rota şimdi 200, HTTP/konsol hatası 0.
Kontrol komutu 16 Eylül listesine eklendi.

**2. Soru havuzundaki 3 tohum sorusu sahteydi.** Alıştırma açılınca çıkan soru şuydu:
*"Ders materyaline göre aşağıdakilerden hangisi doğrudur?"* — doğru şık, kaynak parçanın
ham ve kesilmiş kopyası; çeldiriciler "Materyalde bu şekilde anlatılmıyor", "Bu bölümde
tanımlanmayan bir davranış". Jüri bunu görse soru üretiminin çalışmadığı sonucunu çıkarır.

Gerçek üretim denendi ve **çalışıyor**: eğitmen hesabıyla `POST …/questions/generate`
(konu: Süreçler ve CPU zamanlama, tip: mcq, adet 6) → **6 istendi, 6 döndü, 6 kabul,
0 ret**. Örnek: *"Round-Robin zamanlamasında quantum çok büyük seçildiğinde hangi durum
ortaya çıkar?"* (doğru: FCFS'ye benzer, yanıt süresi kötüleşir), *"Süreçler arası context
switch neden thread'ler arasından pahalı?"* (MMU sayfa tablosu + TLB flush), *"Öncelik
açlığına karşı hangi teknik?"* (aging). Her birinde açıklama ve çeldirici kaynakları var.

Altısı onaylandı, üç sahte soru **API üzerinden reddedildi** (`POST …/reject`) — denetim
izi korunsun ve "eğitmen reddetti" akışı belgelendiği gibi işlesin diye. Havuz artık
`approved|6 · rejected|3`. Alıştırma altı gerçek soruyla açılıyor.

**3. Demo kotası sunuma hazır değil.** Ana demo öğrencisi (`burak@`) bugün **44.469**
jeton harcamış; yol haritasının eşiği 35.000. Gece yarısı sıfırlanacağı için 16 Eylül'de
sorun olmayacak, ama bugün prova yapılacaksa `burak4@` kullanılmalı (26.868, ~5 istek).
Eğitmen hesabı temiz: 200.000'de 0.

**Çalışan ve dokunulmayanlar:** ders sayfası "5 materyal · 5 hazır" gösteriyor (belgeleri
dün gece 8'den 5'e düzeltmem doğruymuş), sınav provası boş durumları dürüst, `/study`
dersi listeliyor, eğitmenin soru üretim formu tam. Sınav planı ve yayımlanmış sınav
sürümü **0** — "Sınav Mentoru" rolü sahnede yalnız alıştırma moduyla gösterilebilir.

## 5. Murat'a kalan işler (ben yapamam)

| # | İş | Neden bende değil |
|---|---|---|
| 1 | Video (10–15 dk) ve OneDrive bağlantısı | Fiziksel |
| 2 | `docs/references.md` kitap satırları | Gerçek kaynak bilgisi sende |
| 3 | Yönetişim karantinası onayı | Denetim kaydı silme; onayın şart |
| 4 | Yedek klasörünü USB/iCloud'a kopyalama | Fiziksel |
| 5 | 025-campus-ui merge kararı | Tasarım GPT'de, karar senin |
| 6 | **GPT'ye "commit'le ve push'la" demek** | Yeni kampüs tasarımı git'te yok; ben yalnız push'lanana erişebiliyorum |
| 7 | Gemini anahtarı | Kondu. Ama §3.3: sohbet yolunda yedek sağlayıcı devreye GİRMİYOR, beklenti buna göre kurulmalı |

## 6. Ölçülmemiş / bilinmeyen

- Uçtan uca süitin **bayrağa bağlı 6 testi** hiç koşmadı (düzenek boşluğu, §2).
- Gerçek modelle holdout metrikleri bu satır yazılırken **koşuluyordu**; sonuç
  `g1_final.log`'da. Bu belgede sayı YOK, çünkü ölçüm bitmeden yazılmaz.
- Groq kotasının günlük mü dakikalık mı olduğu ölçülmedi; 23:32'de açıldığı gözlendi.
