# Demo Günü Runbook

> **Bu belge demo günü tek başvuru kaynağıdır.** Sunumdan önce okunur, sunum sırasında
> açık durur. Amacı "her şey yolunda gitsin" değil; **bir şey bozulduğunda kimin, hangi
> belirtiye bakarak, kaç saniye içinde ne yapacağını** önceden karara bağlamaktır.
>
> Sahne sahne ne anlatılacağı ayrı belgededir: [demo-script.md](demo-script.md).

**Teslim:** 24 Ağustos 2026 · **Bu belge:** 9 Ağustos 2026 · Sahibi: R5

---

## 0. Roller — kim neye karar verir

Plan değiştirme kararı **tek kişide** olmalı; iki kişi aynı anda karar verirse ikisi de
farklı planı uygular ve demo ortada kalır.

| Rol | Kişi | Yetkisi |
|---|---|---|
| **Sürücü** | Ekrandaki kişi | Tıklar, konuşur. Plan değiştirmez |
| **Operatör** | Yanındaki kişi | **Plan A→B→C geçiş kararını YALNIZ bu kişi verir.** Terminal, hotspot ve yedek makine onda |
| **Anlatıcı** | Üçüncü kişi | Jüriyle konuşur, operatör müdahale ederken boşluğu doldurur |

Operatörün önünde bu belge açık, terminalde üç sekme hazır: API logu, worker logu, `psql`.

---

## 1. Üç plan ve aralarındaki geçiş

| | Plan A | Plan B | Plan C |
|---|---|---|---|
| Ne | Canlı bulut | Telefon hotspot + aynı canlı bulut | Tam çevrimdışı, sunum makinesinde |
| Kimlik | Supabase Auth | Supabase Auth | `DEV_AUTH_ENABLED=true` |
| Veritabanı | Supabase | Supabase | Yerel Postgres / Compose |
| LLM | Groq → Gemini failover | aynı | **YOK** — cevaplar `answer_cache`'ten |
| Ne kaybedilir | — | Birkaç saniye gecikme | Önceden doldurulmamış her soru; soru üretimi |

### Geçiş ölçütleri — belirtiyle, süreyle

Ölçüt "internet yavaş" değildir; **saniyeyle ve gözlenebilir bir belirtiyle** tanımlıdır.

| # | Belirti | Kim görür | Karar | Süre |
|---|---|---|---|---|
| 1 | Giriş ekranı **10 sn** içinde açılmadı | Sürücü sesli söyler | Operatör → **Plan B** | Geçiş ~30 sn |
| 2 | İlk soruya **15 sn** içinde cevap gelmedi | Sürücü sesli söyler | Operatör → **Plan B** | Geçiş ~30 sn |
| 3 | Plan B'de de aynı iki belirtiden biri tekrarladı | Operatör | → **Plan C** | Geçiş ~60 sn |
| 4 | Ekranda ham hata / stack trace / 500 | Herkes | Operatör → **Plan C** | Geçiş ~60 sn |
| 5 | Cevap geldi ama **atıfsız** ya da alakasız | Anlatıcı | Plan değişmez — sahneyi atla, [§6](#6-ne-gösterilmeyecek) | 0 sn |

**Kural:** geçiş kararı verildikten sonra geri dönülmez. Demo ortasında "bir daha
deneyelim" en pahalı hatadır; jüri iki kez bekler ve ikisini de hatırlar.

**Sürücünün tek cümlesi:** geçiş yapılırken jüriye söylenecek söz önceden yazılıdır —
> "Ağ tarafında bir yavaşlama var, yedek planımıza geçiyorum; sistemin kendisi aynı."

### Plan B — hotspot

1. Telefonda kişisel erişim noktası **demodan önce açık** ve dizüstü ona **bağlanmış** olmalı;
   Wi-Fi'yi kapatınca otomatik düşecek şekilde ayarlanır. Demo anında hotspot açmak 30 sn değil
   2 dakika sürer.
2. Telefon şarjda ve **sunum modunda** (bildirim yok, ekran kapanmıyor).
3. Operatör Wi-Fi'yi kapatır → dizüstü hotspot'a düşer → sürücü sayfayı yeniler.

### Plan C — tam çevrimdışı

Bu plan **kurulu ve prova edilmiş** olmadan sunum gününe girilmez.

```bash
# Sunum makinesinde, ağ kapalıyken:
cd ~/code/DOU-Synapse
docker compose up -d          # db (pgvector:pg16) + api
# Frontend Compose'da YOKTUR, ayrıca:
cd apps/web && NEXT_PUBLIC_API_URL=http://localhost:8000 bun run dev
```

Plan C'nin **bugünkü sınırları** (ölçüldü, 9 Ağustos):

- **LLM yoktur.** Anahtar tanımlı değilse sistem deterministik sahte sağlayıcıya düşer ve
  logda `llm anahtarı yok — deterministik sahte sağlayıcıya düşülüyor` satırı görünür.
  Sahte sağlayıcı **gerçek chunk'lara gerçek atıf yapar** ama düzyazıyı model yazmaz.
  Bu yüzden çevrimdışı demoda cevaplar `answer_cache`'ten servis edilmelidir.
- **`answer_cache` yalnız `qa` modunda ve BİREBİR eşleşmeyle çalışır.** Soru bir harf bile
  farklı yazılırsa isabet olmaz. Sürücü soruları **kopyala-yapıştır** ile sorar, elle yazmaz.
  Doldurulacak soruların tam listesi: [demo-script.md §Önbellek listesi](demo-script.md#önbelleğe-doldurulacak-sorular-r3ye).
- **Sokratik mod önbelleğe girmez** (mod anahtarın parçası, cache yalnız `qa`). Sokratik
  sahne çevrimdışıyken sahte sağlayıcıyla koşar; ölçüldü ve **doğru davranıyor** (merdiven
  ilerliyor, ısrar edince ilerlemiyor), yalnız ipucu metni şablon.
- **Soru üretimi çevrimdışı ÇALIŞMAZ.** Sahte sağlayıcının soru şeması yoktur; üretim
  `"yanıtta 'questions' dizisi yok"` diyerek **0 soru** döndürür. Sınav sahnesi için sorular
  **önceden üretilip onaylanmış** olmalıdır (aşağıdaki T-60 listesi).
- **Compose yığınında RLS devrede DEĞİLDİR** (API `postgres` superuser'ı ile bağlanıyor).
  İzolasyon sahnesi bu yığında gösterilirse **yanlış bir şey kanıtlanmış olur**. İzolasyon
  Plan A/B'de gösterilir; Plan C'ye düşülürse bu sahne **atlanır** ve sebebi söylenir.

> **R3'ten alınacak:** `docker compose` fallback profilinin gerçekten ağsız koştuğuna dair
> ölçüm, cold start süresi ve `fill_answer_cache.py` betiği. Bu belge yazılırken R3'ün
> ölçümü henüz yoktu; yukarıdaki sınırlar **R5'in kendi koşusundan** çıkarıldı.

---

## 2. Cold start — jüri beklerken ne söylenecek

Ölçüldü (9 Ağustos, MacBook, yerel, `EMBEDDING_PROVIDER=fastembed`):

| Adım | Süre |
|---|---|
| API süreci ayağa kalkma (`/health/live` cevap veriyor) | **0,9 sn** |
| **İlk soru** — embedding modelinin (2,1 GB ONNX) belleğe yüklenmesi dahil | **11,7 sn** |
| İkinci soru (sıcak) | **0,08 sn** |
| Sonraki sorular (sıcak, önbelleksiz) | **0,09 – 0,41 sn** |
| Önbellek isabeti | **0,011 sn** |
| İlk materyal yükleme (model yükleme dahil) | **19,1 sn** |
| Sonraki yüklemeler | **2,1 – 6,7 sn** |

**Bu sayılar sahte LLM sağlayıcısıyla ölçüldü** — yani gerçek bir dil modeli çağrısı
içermiyorlar. Gerçek anahtarla sağlayıcı gidiş-dönüşü eklenir (zaman aşımı deneme başına
30 sn, iki sağlayıcı → en kötü durum 60 sn). Uçtan uca p95 hedefi (<10 sn) **henüz
ölçülmedi**; R2'nin işi.

**Operasyonel sonuç: ilk soru pahalıdır, ikincisi bedava.** Bu yüzden T-15'te warm-up
zorunludur. Yine de beklenirse anlatıcının cümlesi hazır:

> "İlk soruda çok dilli embedding modeli belleğe yükleniyor; bu tek seferlik. Sonraki
> cevaplar saniyenin altında geliyor — birazdan göreceksiniz."

Bu cümle **doğru** olduğu için söylenebilir; ikinci soruda gerçekten 0,1 saniyeye düşer.

---

## 3. Sabah kontrol listesi

### T-60 dakika — kurulum

- [ ] `git pull origin main` · `git log --oneline -1` ile sürüm not edilir
- [ ] **Model önbelleği kalıcı dizinde mi?** macOS'ta fastembed varsayılan olarak
      `$TMPDIR/fastembed_cache` kullanır ve **işletim sistemi bu dizini temizler.**
      2,1 GB'lık modelin demo sabahı yeniden inmesi hotspot'ta imkânsızdır.
      ```bash
      export EMBEDDING_CACHE_DIR="$HOME/.cache/dou-synapse/fastembed"
      du -sh "$EMBEDDING_CACHE_DIR"      # 2,1G görmelisin
      ```
      Boşsa: modeli **şimdi**, iyi ağdayken indir (§5.1).
- [ ] Şema doğrulaması — **23 tablo** görmelisin: <!-- docs-check: tables.count = 23 -->
      ```bash
      psql -d dou_synapse -tAc "select count(*) from information_schema.tables where table_schema='public' and table_type='BASE TABLE'"
      ```
      15 değilse migration'lar eksik: `for f in supabase/migrations/*.sql; do psql -v ON_ERROR_STOP=1 -d dou_synapse -f "$f"; done`
- [ ] **Analitik politikası var mı?** (`0005` uygulanmamışsa eğitmen analitiği boş görünür)
      ```bash
      psql -d dou_synapse -tAc "select polname from pg_policy p join pg_class c on c.oid=p.polrelid where c.relname='request_logs'"
      # request_logs_self_insert VE request_logs_instructor_read görmelisin
      ```
- [ ] Demo dersinin materyali **hazır** mı: `8 materyal · 8 hazır` (Materyaller ekranı)
- [ ] Sınav sahnesi için **onaylanmış soru var mı** (öğrenci hesabıyla bak, boş olmamalı).
      Yoksa şimdi üret ve onayla — çevrimdışıyken üretilemez.
- [ ] `answer_cache` demo soruları **dolduruldu** mu (Plan C sigortası)
- [ ] **Sahne 5'in iki sorusu denendi mi** — `İtalya'nın başkenti neresidir?` "Dersin
      kapsamı dışında", `Bugünkü dolar kuru ne kadar?` "Materyalde dayanak bulunamadı"
      dönmeli. Ret türü ölçülmüş bir sinyale bağlı; denenmemiş soruyla sahneye çıkılmaz
- [ ] Soru havuzu / sınav / ilerleme ekranlarında **önizleme şeridi kalmadığı** görüldü mü
- [ ] Yedek makine aynı adımlardan geçti mi

### T-15 dakika — ısıtma

- [ ] Plan A/B: bulut `minReplicas=1` **açık**
- [ ] **Warm-up:** her iki hesapla giriş yapılır ve **birer soru sorulur.** Bu, 11,7 saniyelik
      ilk-soru maliyetini demo başlamadan önce ödemek içindir. Sorulan soru demo sorusu
      OLMASIN — sohbet geçmişinde durur ve sahne tekrarı gibi görünür.
- [ ] Oturumlar **açık bırakılır**; demo sırasında giriş yapılmaz
- [ ] Telefon hotspot'u açık, dizüstü ona bağlı, telefon şarjda
- [ ] Tarayıcıda **yalnız demo sekmesi** açık; bildirimler kapalı; ekran uyku kapalı
- [ ] Sürücünün yanında **kopyalanacak sorular** ayrı bir dosyada hazır (elle yazma yok)

### T-0 — son bakış

- [ ] Bu belge operatörün ekranında açık
- [ ] Terminalde üç sekme: API logu, worker logu, `psql`
- [ ] Zoom seviyesi %100'e sabit (yüzde değişimi ekran görüntülerini bozar)
- [ ] Sürücünün ekranında sohbet geçmişi **temiz** (warm-up sohbeti kapatılmış)

---

## 4. Bilinen kırılgan noktalar ve kaçış yolları

| # | Kırılgan nokta | Belirti | Kaçış |
|---|---|---|---|
| 1 | **İlk soru 11,7 sn** (model yükleme) | Uzun bekleme | T-15 warm-up. Olmazsa anlatıcının cümlesi (§2) |
| 2 | **Model önbelleği silinmiş** | İlk soru dakikalarca sürer, log `embedding modeli yükleniyor`da asılı | Kurtarma yok. T-60'ta kontrol et |
| 3 | **`answer_cache` birebir eşleşme** | Plan C'de cevap gelmiyor | Soruları kopyala-yapıştır sor |
| 4 | **Her ders dışı soru "kapsam dışı" demiyor** | Bazıları "Materyalde dayanak bulunamadı" döner | İkisi de doğru davranış, ama sahnede **denenmiş** soruyu kullanın; demo-script sahne 5'te ölçülmüş liste var |
| 5 | **Soru üretimi anahtarsız çalışmıyor** | "0 soru üretildi" | Soruları T-60'ta üret ve onayla |
| 6 | **Hız sınırı**: kullanıcı+ders başına 20 istek / 60 sn | 429 ve "Çok sık soru gönderiyorsun" | Prova ile demoyu aynı hesapta arka arkaya yapma; ya 1 dk bekle ya diğer hesaba geç |
| 7 | **Mod ortada değişmiyor** | "Bu oturum farklı bir modda başlatılmış" | Sokratik'e geçerken **yeni sohbet** aç (arayüz bunu kendi yapıyor) |
| 8 | **Dev veritabanı test dersleriyle dolu** | Ders listesinde onlarca `E2E Test Dersi` | Demo öncesi temiz bir ders listesi hazırla; jüri çöp listeyi görmemeli |
| 9 | **Sunum makinesinde port çakışması** | `address already in use` | Compose ve yerel Postgres ikisi de 5432 ister: birini durdur |
| 10 | **Supabase free-tier duraklaması** | Giriş çalışmıyor | Günlük keep-alive ping; sabah erken giriş |

---

## 5. Kurtarma komutları

### 5.1 Model önbelleğini kalıcı dizine al (T-60'ta bir kez)

```bash
export EMBEDDING_CACHE_DIR="$HOME/.cache/dou-synapse/fastembed"
mkdir -p "$EMBEDDING_CACHE_DIR"
cd apps/api && uv run python -c "
from fastembed import TextEmbedding
import os
TextEmbedding(model_name='intfloat/multilingual-e5-large',
              cache_dir=os.environ['EMBEDDING_CACHE_DIR'])
print('hazır')"
du -sh "$EMBEDDING_CACHE_DIR"     # 2,1G
```

`.env`'e `EMBEDDING_CACHE_DIR` satırını eklemeyi unutma; yoksa süreç yine `$TMPDIR`'a bakar.

### 5.2 Sistem ayakta mı

```bash
curl -s localhost:8000/health/live    # süreç
curl -s localhost:8000/health/ready   # veritabanı + pgvector
```

### 5.3 Bir soru gerçekten cevaplanıyor mu (arayüzsüz)

```bash
curl -s -X POST "http://localhost:8000/courses/<COURSE_ID>/chat" \
  -H "Authorization: Bearer dev:22222222-2222-2222-2222-222222222222" \
  -H "Content-Type: application/json" \
  -d '{"question":"Semafor nedir?","mode":"qa"}'
```

`"status":"answered"` ve dolu bir `citations` dizisi görmelisin.

### 5.4 Sahte sağlayıcıda mıyız (gerçek LLM var mı)

```bash
grep "sahte sağlayıcı" /tmp/api.log
```

Satır varsa gerçek LLM **yok** — bu Plan C'de beklenen, Plan A'da bir arızadır.

---

## 6. Ne gösterilmeyecek

Bu liste bir özdisiplin listesidir. Jüri "neden bunu göstermediniz" diye sormaz; ama
yarım bir ekranı gösterirsek onu sorar.

**Gösterilmez:**

- **Ölçülmemiş hiçbir sayı.** Slaytta bir metrik varsa altında onu üreten koşu vardır.
  Bugün ölçülmemiş olanlar: uçtan uca p95, Recall@5/@8, citation precision, faithfulness,
  injection testleri. Bunlar için tek doğru cümle: *"bu ölçüm henüz koşulmadı."*
- **Kapsam dışı doğru ret oranını %90 diye söylemek.** Ölçülen **%80** ve hedefin
  altında. Doğru anlatım: "hedefimiz %90'dı, retrieval kapısı düzeyinde %80 ölçtük,
  sebebini ve neden eşiği holdout'a bakarak değiştirmediğimizi raporda yazdık." Bu
  cümle projeyi zayıf değil **savunulabilir** gösterir.
- **Eğitmen analitiğindeki "kapsam dışı ret oranı" kartı.** Bugün %0 gösteriyor çünkü
  retler `insufficient_context` olarak kaydediliyor. Sayı yanlış okunmaya açık.
- **Compose yığınında izolasyon kanıtı.** O yığında RLS devrede değil.
- **Soru üretimi ekranı**, gerçek LLM anahtarı yoksa (0 soru döner).
- **Üstünde "Tasarım önizlemesi" şeridi olan hiçbir ekran.** 9 Ağustos akşamı itibarıyla
  böyle bir ekran **kalmadı** (soru havuzu, sınav ve ilerleme o gün bağlandı), ama kural
  duruyor: örnek veri gösteren bir ekranı çalışan ürün diye göstermek, bu listedeki her
  maddeden daha pahalıya patlar. Sunumdan önce üç ekranı bir kez açıp şerit olmadığını
  doğrulayın.
- **Dev veritabanının ham ders listesi** (onlarca test dersi).
- **Ham stack trace / 500 ekranı.** Görülürse Plan C'ye geçilir (§1 ölçüt 4).

**Gösterilir ve övünülür:** kaynaklı cevap, Sokratik merdivenin ilerlememesi, kapsam dışı
soruya verilen nazik ret, "neden yanlış" ekranı. Dördü de 9 Ağustos'ta canlı koşuldu.

---

## 7. Demo sonrası

- [ ] `minReplicas` eski değerine döndürülür (maliyet)
- [ ] Demo sırasında açılan oturumlardan çıkılır
- [ ] Demo sırasında görülen her kusur, unutulmadan yazılır
