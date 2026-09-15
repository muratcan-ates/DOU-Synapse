# Sunum akışı — 16 Eylül 2026

Yeni dosya: `docs/team/SUNUM-AKISI-16-EYLUL.md`. Yazılış: 15 Eylül 2026.
Yol haritası madde **19 · 20**'nin çıktısı.

**Masaya basılacak tek sayfa §0 + §1'dir** (roller + dakika dakika akış). §2–§5 operatörün
yanında duran ek: sorulacak sorular, çökme senaryosu ve sahnede iddia edilmeyecekler.
Baştaki **ENGEL** bölümü sunumdan önce kapatılacak tek maddedir; kapandıktan sonra silinmez,
"kapatıldı" diye tarih ve ölçümle işaretlenir.

Kaynaklar: [demo-script.md](../demo-script.md) (sahne metinleri, ölçülmüş soru listesi),
[jury-demo.md](../jury-demo.md) (jüri provası, 15 Eylül eki), [runbook.md](../runbook.md)
(Plan A/B/C, geçiş ölçütleri, roller), [requirements-analysis.md §3.1](../requirements-analysis.md)
(üç rolün otoriter tanımı).

> **Süreler hedeftir, ölçülmüş çalışma süresi değildir.** Toplam 9:30, demo-script'teki altı
> sahnenin kendi sürelerinin toplamıdır (60+90+90+60+60+120 sn = 8:00) artı açılış ve kapanış
> (2×45 sn). jury-demo.md "10 dakikalık senaryo" der; aradaki 30 saniye o belgenin ölçüm
> kartı adımını da içermesinden gelir, bu akış onu kapanışa katar.

## ENGEL — sunumdan önce kapatılmalı: `answer_cache` şu anda ÖLÜ

15 Eylül 08:20'de ölçüldü. Önbellek araması `course_id + audience + policy_revision +
prompt_revision + **corpus_revision** + question_hash` altısını birden eşler
(`apps/api/app/api/chat_cache.py`). `corpus_revision`, dersin `completed` belgelerinin
(id, file_hash, updated_at, superseded_at) listesinden her istekte yeniden hesaplanır.

- 07:34:37 — sahne provası koştu: 16/16 geçti, jeton farkı 0. **O an doğruydu.**
- 07:39:53 — COME302'ye altıncı belge (`03-memory-management.md`) `completed` oldu.
- Sonuç: `corpus_revision` `3f98c0d7…a87a` → `3b5d0a8f…17a5`. Önbellekteki **13 satırın
  tamamı** eski anahtarda kaldı. Bugün hiçbir sahne sorusu önbellekten dönmez.

**Bu, Plan C'yi ve jeton sigortasını aynı anda düşürür.** Aşağıdaki §4.3'ün "kaybedilmez"
satırı ancak bu engel kapatıldıktan sonra geçerlidir.

İki çıkış yolu var; ikisi de ölçüldü:

| Seçenek | Ne yapar | Maliyet |
|---|---|---|
| **(a) Tercih edilen** — `03-memory-management.md`'yi COME302'den çıkar/`superseded` yap | `corpus_revision` **birebir** `3f98c0d7…a87a`'ya döner (hesaplandı, doğrulandı); 13 satır aynen isabet etmeye başlar | **0 jeton**, saniyeler |
| (b) `fill_answer_cache.py`'yi güncel korpusla yeniden koş | Yeni anahtarda taze önbellek | ~13 soru × ~4.500 ≈ 58.500 jeton > öğrencinin 50.000 günlük tavanı → ya ikinci sentetik öğrenci ya gece yarısı sonrası |

Hangisi seçilirse seçilsin **kanıt tek:** `python3 scripts/demo/sahne_provasi.py` çıktısında
16 satır ✓ **ve jeton farkı 0** olmalı. Jeton farkı 0'dan büyükse önbellek ıskalıyor demektir.

**Bunun doğrudan sahne sonucu: Sahne 1'de CANLI DOSYA YÜKLENMEZ.** Yüklenen belge "Hazır"
olduğu an `corpus_revision` değişir ve o andan sonraki bütün `qa` aramaları ıskalar — yani
demo ortasında Plan C sigortası düşer. Bugün tam olarak bu oldu.

---

## 0. Masadaki üç kişi — kim neye karar verir

Plan değiştirme kararı **tek kişidedir** (runbook §0).

| Rol | Kim | Yetkisi |
|---|---|---|
| **Sürücü** | Ekrandaki kişi | Tıklar, konuşur. **Plan değiştirmez.** |
| **Operatör** | Yanındaki kişi | **Plan A→B→C geçişine YALNIZ bu kişi karar verir.** Terminal, hotspot, yedek makine onda |
| **Anlatıcı** | Üçüncü kişi | Jüriyle konuşur, operatör müdahale ederken boşluğu doldurur |

Operatörün önünde bu sayfa ve runbook açık; terminalde üç sekme: API logu, worker logu, `psql`.

---

## 1. Dakika dakika — üç rol sırayla

Anlatının omurgası tek cümle: **"Kaynak yoksa cevap da yok."**
Danışmanın M4 eleştirisine ("çok geniş düşünüyorsunuz; yapay zekâ nerede değer katıyor?")
cevap, özellik listesi değil **üç rolün sırayla kanıtlanmasıdır**.

| Zaman | Rol | Ne yapılır | Ekranda kanıt |
|---|---|---|---|
| 00:00–00:45 | — | Açılış: tek cümlelik tez | Sadece tez. Ürün adı saymaca yok |
| 00:45–01:45 | — | **Sahne 1:** Ayşe Hoca materyal listesini gösterir (COME302 → Materyaller). **Canlı yükleme YOK** — sebebi yukarıdaki ENGEL | Hazır rozetleri ve parça sayıları. "Bilgi tabanını hoca kuruyor" |
| 01:45–03:15 | **1 · Ders Asistanı** | **Sahne 2:** öğrenci kaynaklı soru sorar | Cevabın altında **kaynak kartları**: dosya adı + sayfa + birebir alıntı |
| 03:15–04:45 | **1 · Ders Asistanı** | **Sahne 3:** ödev sorusu → Sokratik mod | Beş noktalı **merdiven**, kademe **Tanı**; öğrenci deneyince **Yönlendirme**'ye ilerler |
| 04:45–05:45 | **1 · Ders Asistanı** | **Sahne 4:** "sadece söyle" | Merdiven **ilerlemez**. Karar sunucudaki durum makinesinde; modele hiç gidilmez |
| 05:45–06:45 | **1 · Ders Asistanı** ★ | **Sahne 5:** ders dışı soru → nazik ret, sonra ikinci ret türü | **İki ayrı ret**: "kapsam dışı" ve "materyalde dayanak yok". Hata rengi/ikonu yok |
| 06:45–08:00 | **2 · Sınav Mentoru** | **Sahne 6b:** sınav provası, bilerek yanlış şık, "Neden yanlış?", İlerleme sekmesi | `Yanlış · 0 / 100` + çeldiricinin **çeliştiği kaynak bölümü** (dosya + sayfa + alıntı) |
| 08:00–08:45 | **3 · Soru Üretici** | **Sahne 6a:** soru havuzu; **taslak varsa** bir soru **Onayla**, bir soru **Reddet**; yoksa havuzun mevcut hâli anlatılır | "Bu sorular otomatik üretildi ama **otomatik yayınlanmadı**." Onaysız soru öğrencide listede bile yok |
| 08:45–09:30 | — | Kapanış: döngü + açık işler | "Hocanın materyali → kaynaklı cevap → yönlendirme → sınav → konu bazlı zayıflık" |
| 09:30 → | — | Soru-cevap (3–5 dk) | Hazır cevaplar: [jury-demo.md §Jüri sorularına cevap taslakları](../jury-demo.md) |

### Rol sırası neden böyle — ve demo-script'ten farkı

demo-script sahne sırasında **6a (eğitmen onayı) 6b'den (öğrenci sınavı) önce** gelir.
Bu akış ikisini yer değiştirir, çünkü istenen anlatı rol sırasıdır: *Ders Asistanı →
Sınav Mentoru → Soru Üretici*. Bu bir kısaltma değil:

- Onaylanmış soru havuzu **zaten T-60'ta hazır olmak zorunda** (runbook §3: "Sınav sahnesi
  için onaylanmış soru var mı"). Yani 6a sahnede kurulum değil, **açıklama**dır.
- Böylece Soru Üretici, jürinin Sınav Mentoru'nu gördükten sonra soracağı soruyu
  ("bu sorular nereden geldi, kim onayladı?") kapatan **kapanış vuruşu** olur.
- Anlatım kaybı yok: 6a'nın "onaysız soru öğrenciye görünmez" cümlesi aynen söylenir.

| Rol | Danışmanın adı | Yüzey | Tek cümlede | Sahnede kanıt |
|---|---|---|---|---|
| **Ders Asistanı** | Class Assistant | `/courses/[id]/chat` — "Ders Koçu" | Materyal içi soruyu **kaynak göstererek** yanıtlar; Sokratik modda ipucu merdiveni | Sahne 2–5 |
| **Sınav Mentoru** | Exam Mentor | `/courses/[id]/exam` | Cevabı değerlendirir, yanlış çeldiricinin **çeliştiği kaynak bölümünü** gösterir | Sahne 6b |
| **Soru Üretici** | CourseGPT | `/courses/[id]/questions` — "Eğitmen Asistanı" | Eğitmenin kurduğu çerçevede soru + cevap anahtarı üretir | Sahne 6a |

---

## 2. Sahnede sorulacak sorular — kopyala-yapıştır, elle yazma

`answer_cache` **birebir eşleşir**; bir harf farkı isabeti kaçırır ve soru modele gider.
Aşağıdaki metinler doğru metinlerdir; ama baştaki ENGEL kapatılmadıkça hiçbiri isabet etmez.

| Sahne | Soru (aynen) | Ölçülen |
|---|---|---|
| 2 | `Süreç ile thread arasındaki temel fark nedir?` | `answered`, 3 atıf — önbellekte |
| 3 | `Deadlock oluşması için gereken dört koşul nedir?` | Sokratik mod; önbelleğe **girmez** |
| 3 (devam) | `Sanırım karşılıklı dışlama ve döngüsel bekleme var, diğerlerini bilmiyorum` | Merdiveni bir kademe ilerletir |
| 4 | `sadece söyle` | Merdiven ilerlemez; modele gidilmez |
| 5 | `İtalya'nın başkenti neresidir?` | `out_of_scope` — önbelleğe girmez, gerek de yok |
| 5 (ikinci ret) | `Bugünkü dolar kuru ne kadar?` | `insufficient_context` |

**Jüri "başka bir şey sorun" derse** — yalnız bu listeden (hepsi önbellekte, jeton harcamaz):
`Dairesel bekleme koşulu nedir?` · `Banker's Algorithm hangi deadlock stratejisine girer?` ·
`Mutex ile semafor arasındaki fark nedir?` · `Semafor nedir ve ne işe yarar?` ·
`Context switch ne zaman gerçekleşir?` · `fork() çağrısı ne döndürür?` ·
`Round-robin zamanlamada quantum süresinin seçimi neyi etkiler?` ·
`Turnaround time ile waiting time arasındaki fark nedir?` ·
`Context switch maliyeti neden yüksek?` ·
`Deadlock oluşabilmesi için hangi dört koşulun sağlanması gerekir?`

### DİKKAT — Sahne 2 sorusu demo-script'tekinden farklı, sebebi ölçüldü

demo-script Sahne 2'de yazılı soru `Süreç ile iş parçacığı arasındaki fark nedir?`
**önbellekte değil.** 15 Eylül'de ölçüldü: `apps/api/scripts/demo_questions.json`
listesindeki bu soru `fill_answer_cache.py` koşusunda önbelleğe **girmedi** ve
demo-script'in "kaynaklı cevap veren 12 soru" listesinde de yok; sahne provası
(`scripts/demo/sahne_provasi.py`) da onu denemiyor. Sonucu:

- **Plan C'de (çevrimdışı) bu soru cevapsız kalır.**
- Plan A'da bile modele gider: jeton harcar ve sonucu bu adayda ölçülmemiştir.

Bu yüzden sahnede **önbellekteki eşdeğeri** sorulur: `Süreç ile thread arasındaki temel
fark nedir?` — aynı kavram, ölçülmüş, 3 atıflı. Sahne 2'nin anlatısı değişmez.
(demo-script bu sayfanın yüzeyi değil; düzeltme ayrı iş olarak açılmalı.)

### Kaynak belgelerde ölçümle çelişen üç nokta — sahnede bunlara uyma

demo-script bu üç noktada güncel demo veritabanıyla uyuşmuyor; hepsi `dou_demo` üzerinde
15 Eylül'de ölçüldü:

| demo-script diyor | Ölçülen |
|---|---|
| Ders `COME 331 · İşletim Sistemleri`, üç materyal (`producer_consumer.py`, `04-synchronization.pdf`, `01-processes.pdf`) | Ders **`COME302 · İşletim Sistemleri`**; altı belge: `01-processes.pdf`, `02-cpu-scheduling.pdf`, `03-memory-management.md`, `04-synchronization.**md**`, `06-file-systems.pptx`, `deadlock-notlari.md` |
| Sahne 3 ipucu kartı `05-deadlock-demo.pdf · Sayfa 1` gösterir | Bu dosya korpusta **yok**. Sokratik cevaplar önbelleğe girmediği için hangi kaynağın çıkacağı ölçülemez — **ekranda yazanı okuyun**, dosya adı ezberden söylenmesin |
| Hazırlık adımları `dou_synapse` veritabanı ve `:8030`/`:3030` portlarını kullanır | Demo yığını `dou_demo` + `:8020`/`:3020` (`scripts/demo/run_api.sh`, `run_web.sh`) |

---

## 3. Sahnede SORULMAYACAKLAR

demo-script §Önbellek listesi'nde ölçülmüş: materyalde karşılığı yok, `insufficient_context`
ya da `out_of_scope` döner. Doğru davranış ama demo akışında **arıza gibi görünür**:

`Sayfalama nedir?` · `Sayfalama (paging) dış parçalanmayı nasıl ortadan kaldırır?` ·
`TLB ne işe yarar?` · `inode ne saklar?` ·
`Deadlock'u önlemek için tut ve bekle koşulu nasıl kırılır?`

> **Son madde için ölçülen çelişki:** bu soru `dou_demo.answer_cache`'te **`answered` ve
> 5 atıflı** duruyor (15 Eylül ölçümü) — yani doldurma koşusunda cevap almış. demo-script
> ise onu "materyalde karşılığı yok" diye listeliyor. İki kayıt çelişiyor; çelişki
> çözülene kadar **muhafazakâr taraf geçerli: sorulmaz.** Aynı sınıfta ikinci bir boşluk
> var: `Üretici-tüketici probleminde sınırlı tampon neden gerekir?` `demo_questions.json`
> listesinde olmasına rağmen ne önbellekte ne de demo-script'in iki listesinde geçiyor —
> sınıflandırılmamış, dolayısıyla sahne dışı.

Kural daha basit hâliyle: **§2'deki listede olmayan hiçbir soru sahnede sorulmaz.**
Jüri kendi sorusunu söylerse cevap: "Bu soruyu bu materyalle denemedik; denenmemiş
soruyla sahnede oynamıyoruz — isterseniz kaydedip size ölçümle dönelim."

---

## 4. Çökme senaryosu — internet giderse Plan C

### 4.1 Geçiş ölçütleri (runbook §1) — belirtiyle ve saniyeyle

| # | Belirti | Kim görür | Karar | Süre |
|---|---|---|---|---|
| 1 | Giriş ekranı **10 sn** içinde açılmadı | Sürücü sesli söyler | Operatör → **Plan B** | ~30 sn |
| 2 | İlk soruya **15 sn** içinde cevap gelmedi | Sürücü sesli söyler | Operatör → **Plan B** | ~30 sn |
| 3 | Plan B'de aynı belirti tekrarladı | Operatör | → **Plan C** | ~60 sn |
| 4 | Ekranda ham hata / stack trace / 500 | Herkes | Operatör → **Plan C** | ~60 sn |
| 5 | Cevap geldi ama **atıfsız** ya da alakasız | Anlatıcı | Plan değişmez — **sahneyi atla** | 0 sn |

**Geçiş kararı verildikten sonra geri dönülmez.** "Bir daha deneyelim" en pahalı hatadır.

Sürücünün geçiş cümlesi önceden yazılıdır:
> "Ağ tarafında bir yavaşlama var, yedek planımıza geçiyorum; sistemin kendisi aynı."

### 4.2 Plan B — hotspot (30 sn)

Hotspot **demodan önce açık** ve dizüstü ona **bağlanmış** olmalı. Operatör Wi-Fi'yi kapatır →
dizüstü hotspot'a düşer → sürücü sayfayı yeniler. Demo anında hotspot açmak 30 sn değil
2 dakika sürer.

### 4.3 Plan C — tam çevrimdışı (60 sn)

**`qa` sahneleri için hiçbir şey yapılmaz.** Sohbet ucu `answer_cache`'i LLM'den **önce**
arar (`apps/api/app/api/chat.py`); isabet varsa ağa hiç çıkmaz. Yalnız **Sokratik sahne ve
soru üretimi** için API sahte sağlayıcıyla yeniden başlatılır:

```bash
cd ~/code/dou-synapse-018-codex-production-line
DOU_DEMO_OFFLINE=1 sh scripts/demo/run_api.sh   # 127.0.0.1:8020, LLM_FAKE_PROVIDER=true
sh scripts/demo/run_web.sh                       # 127.0.0.1:3020 — ayaktaysa DOKUNMA
```

**`scripts/demo/setup_db.sh` demo ortasında ASLA koşturulmaz** — `dou_demo`'yu silip yeniden
kurar, dolu `answer_cache` de gider.

**Plan C'de ne kaybedilir, ne kaybedilmez:**

| | Durum (**ENGEL kapatıldıktan sonra**) |
|---|---|
| Sahne 2 (`qa`, kaynaklı cevap) | **Kaybedilmez** — önbellekten gelir, jeton harcamaz |
| Sahne 5 (iki ret) | **Kaybedilmez, ama sebebi önbellek değil.** Önbellek yalnız `answered` + atıflı cevapları saklar; ret sorularının hiçbiri önbelleğe girmez. Çevrimdışında doğru davranmalarının sebebi kanıt kapısının modele gitmeden kapanmasıdır. Operatör "ret gelmiyor" diye önbelleği suçlamasın |
| Sahne 3–4 (Sokratik) | Çalışır ama **ipucu metni şablon**: önbellek yalnız `qa` modunu saklar, sahte sağlayıcı devreye girer. Ölçüldü: merdiven ilerliyor, ısrarda ilerlemiyor — davranış doğru |
| Sahne 6a (soru üretimi) | Sentetik üretim. **Gerçek üretim gibi sunulmaz** |
| Liste dışı her soru | **Kaybedilir** |

**15 Eylül 07:34 sahne provası** (`scripts/demo/sahne_provasi.py`): 16 sorunun 16'sı geçti —
12 kaynaklı cevap (atıf sayıları belgelenen listeyle birebir), 4 doğru ret (2 `out_of_scope`,
2 `insufficient_context`). Yanıt süreleri 0,02–0,61 sn. **Harcanan jeton: 0** (26.868 → 26.868).

> **Bu ölçüm 07:34'ün ölçümüdür ve 07:39:53'te geçersizleşti** (bkz. baştaki ENGEL): altıncı
> belge tamamlanınca `corpus_revision` değişti. demo-script'teki "07:40" başlığı provanın
> yazıldığı saattir, koşulduğu saat değil. Prova yeniden koşulup **jeton farkı 0** görülmeden
> Plan C'nin çalıştığı söylenemez.

### 4.4 Sunum sabahı — bu üçünü koşmadan sahneye çıkma

```bash
python3 scripts/demo/sahne_provasi.py            # 16/16 ✓ VE jeton farkı 0 — ikisi birden
curl -s http://127.0.0.1:8020/health/ready       # database/pgvector/embedding üçü de "ok"
for r in /study /settings /dashboard /profile; do \
  printf "%s %s\n" "$r" "$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3020$r)"; done
```

**Provanın jeton farkı bu belgedeki tek gerçek Plan C kanıtıdır.** 16 satır ✓ görünüp jeton
farkı 0'dan büyükse cevaplar modelden geliyor demektir: sahne çalışır ama çevrimdışında
çökerdi ve kota tükenir. Bu durumda baştaki ENGEL bölümüne dönün.

Sahne 6a'nın hangi biçimde oynanacağını da ölçerek belirleyin — havuz durumu değişkendir
(15 Eylül 08:20 ölçümü: `draft` 2, `approved` 7, `rejected` 3):

```bash
psql -d dou_demo -Atc "select status, count(*) from questions group by 1 order by 1"
```

`draft` satırı varsa sahnede canlı **Onayla/Reddet** yapılabilir. Yoksa onay kapısı
anlatılır ve havuzun mevcut hâli gösterilir; olmayan bir taslağı onaylıyormuş gibi
yapılmaz.

Dördü de **200** değilse web'i durdurup `sh scripts/demo/run_web.sh` ile yeniden başlat:
`run_web.sh` üretim derlemesi yapar ve **bayat derleme yeni rotalarda 404 verir** —
15 Eylül'de tam bu yaşandı.

**Jeton kotası** demoyu durdurabilecek tek sessiz risk: öğrenci günlük tavanı 50.000,
istek başına ~4.500 gider, dolarsa ekranda "Günlük kişisel AI kullanım kotan doldu" çıkar.
Önbellekten dönen cevaplar jeton harcamaz — bu yüzden **liste dışına çıkılmaz**.
Kontrol komutu ve 35.000 eşiği: [runbook §3](../runbook.md) ve yol haritası §3 kontrol listesi.

**Salon / donanım:** laptop adaptörde · telefon hotspot bağlı ve şarjda · bildirimler
susturuldu (Rahatsız Etme) · tarayıcıda yalnız demo sekmesi · ekran uykusu kapalı ·
çözünürlük ayarlı · yedek klasörü (`dou_demo.bundle` + `api.env` + OKU.md) USB'de.

**T-15 ısıtma:** her iki hesapla giriş yapılır ve **birer soru sorulur** (11,7 sn'lik
ilk-soru maliyeti demo başlamadan ödensin diye). Isıtma sorusu **demo sorusu olmasın** —
sohbet geçmişinde durur ve sahne tekrarı gibi görünür. Oturumlar açık bırakılır.

---

## 5. Sahnede iddia EDİLMEYECEKLER

Bunların hepsi ölçülmüş sınırlardır; jüri sormadan önce kendimiz söylemek daha iyidir.

- **Sağlayıcı failover gösterilmez ve "var" denmez.** Rol farkındalıklı sohbet yolu
  `provider_attempt_limit=1` kuruyor: ikinci sağlayıcı **tasarım gereği** denenmiyor
  (jeton rezervasyonu atomik kalsın diye). `LLM_FALLBACK_MODEL` ayarlı olsa bile sohbet
  isteğinde devreye girmez. Groq'ta anlık hata olursa **tek gerçek koruma `answer_cache`'tir.**
- **429 simülasyonu → "Önceden kaydedilmiş demo yanıtı" akışı** bu tabanda doğrulanmadı.
  Beklenen davranış **plan olarak** anlatılır, gerçekleşmiş gibi oynatılmaz.
- **`learning_events` eğitmen özeti** bu tabanda doğrulanmadı. Mevcut analitik görünümü ile
  planlanan olay özeti **ayrı** anlatılır.
- **Gerçek modelle holdout başarı raporu (G1) koşulmadı.** Sayı sorulursa: "o ölçümü
  yapmadık, uydurmuyoruz." Retrieval tarafında ölçülen var, LLM kalitesi tarafında yok.
  Kapsam dışı ret oranı için sahnede **yüzde telaffuz edilmez**: `docs/test-report.md`
  kanıt kapısı düzeyinde %50 (11/22) ve uçtan uca SC-005 için %0 (0/22) veriyor ve bunu
  "n=4 bir SC-005 ölçümü değildir" diye sınırlıyor. Doğru cümle: "gerçek modelle holdout
  üstünde henüz ölçmedik; ölçtüğümüz düzeyde hedefin altındayız ve sayıyı olduğu gibi
  raporladık."
- **Injection'ın yalnız deterministik yarısı koşuldu:** 35 vakanın 3'ü ihlal etti
  (`docs/test-report.md`). Gerçek modelle koşulmadı. "Injection testleri koşulmadı" demek
  de yanlış olur — olumsuz bulguyu örter.
- **"Yayımlanmış sınav" ya da "blueprint kataloğu" iddia edilmez.** Ekranın adı gerçekten
  *Sınav provası*, mod etiketi *Alıştırma*; ikisi de ürünün kendi metni ve söylenebilir.
  Söylenmeyecek olan, arkasında yayımlanmış bir sınav sürümü olduğudur.
- **`provider-fallback` uçtan uca testleri CI'da koşmuyor** (simülasyon bayrağı koşucuya
  bağlanmadı; fazlı koşucu birleşmedi). Sunum sonrasına alındı.
- **Kullanılmayacak ifadeler:** "KVKK uyumlu", "production-ready", "LTI hazır".
  Bunların yerine ne söyleneceği [jury-demo.md](../jury-demo.md) cevap taslaklarındadır.
- **Sahte sağlayıcıyla gösterilen hiçbir şey gerçek model kalitesi diye sunulmaz.**
  Hangi sağlayıcıyla koşulduğu logdan doğrulanır ve jüriye söylenir.
- Ekranda **atıfsız ya da alakasız** bir cevap gelirse plan değişmez: **sahne atlanır**
  (geçiş ölçütü 5). Israrla tekrarlanmaz.
