# Demo Senaryosu — sahne sahne

> [runbook.md](runbook.md) "bozulursa ne yapılır"ı anlatır. **Bu belge her şey yolundayken
> ne anlatılacağını** anlatır: hangi cümle, hangi tıklama, ekranda ne görünecek, kaç saniye.
>
> Altı sahnenin **beşi 9 Ağustos 2026'da canlı sistemde koşuldu** ve buradaki ekran
> metinleri o koşudan alındı — uydurulmuş replik yok. Altıncı sahnenin (sınav) ön koşulu
> aşağıda yazılı.

**Toplam süre: ~9 dakika.** Soru-cevap için ayrıca 3-5 dakika bırakın.

---

## Anlatının omurgası

Ürünün tezi tek cümlede: **"Kaynak yoksa cevap da yok."**

Altı sahne bu cümleyi sırayla kanıtlar. Sıra rastgele değil — her sahne bir öncekinin
açtığı soruyu kapatır:

| # | Sahne | Kanıtladığı şey | Süre |
|---|---|---|---|
| 1 | Eğitmen materyal yükler | Bilgi tabanı **hocanın koyduğudur** | 60 sn |
| 2 | Öğrenci soru sorar | Cevap **sayfa numarasıyla** gelir | 90 sn |
| 3 | Ödev sorusu sorulur | Cevap yerine **Sokratik merdiven** | 90 sn |
| 4 | "Sadece söyle" denir | Merdiven **ilerlemez** | 60 sn |
| 5 | Ders dışı soru sorulur | **Nazik ret — bu bir özellik** | 60 sn |
| 6 | Sınav provası + "neden yanlış" | Öğrenme döngüsü kapanır | 120 sn |

En özgün an **5. sahnedir**: bilmediğini söyleyebilen asistan. Bunu bir eksiklik gibi değil,
**tasarım kararı** olarak anlatın.

---

## Sahne 1 — Eğitmen materyal yükler (60 sn)

**Kim:** Ayşe Hoca (eğitmen) · **Ekran:** COME 331 → Materyaller

**Ne söylenecek:**

> "Sistem hiçbir şey bilmiyerek başlıyor. Bilgi tabanını dersin hocası kuruyor —
> internetten değil, kendi materyalinden."

**Ne yapılacak:**

1. Materyaller sekmesi açık, listede 8 materyal ve her birinin yanında **Hazır** rozeti
   ve parça sayısı görünüyor (`01-processes.pdf · 45 KB · 3 sayfa · 3 parça`).
2. "Dosya seç" ile küçük bir PDF yükleyin (5-10 sayfa). Durum **Yükleniyor → İşleniyor →
   Hazır** akar ve parça sayısı belirir.

**Ne görünecek:** ![Materyaller](images/03-egitmen-materyaller.png)

**Söylenecek ikinci cümle:**

> "Her dosya sayfa sayfa parçalanıyor ve sayfa numarası saklanıyor. Birazdan cevapta o
> numarayı göreceksiniz — çünkü kaynak model tarafından yazılmıyor, buradan geliyor."

**Süre uyarısı:** ilk yükleme embedding modelini belleğe alır ve **19 saniye** sürebilir;
sonrakiler 2-7 saniye. T-15 warm-up yapıldıysa bu maliyet zaten ödenmiştir.

---

## Sahne 2 — Öğrenci soru sorar, kaynaklı cevap gelir (90 sn)

**Kim:** Burak (öğrenci) · **Ekran:** COME 331 → Asistan · **Mod:** Soru-cevap

**Sorulacak soru** (kopyala-yapıştır):

```
Süreç ile iş parçacığı arasındaki fark nedir?
```

**Ne söylenecek (soru gönderilirken):**

> "Öğrenci soruyor. Dikkat edin: cevabın altında ne göreceğiz?"

**Ekranda görünen (9 Ağustos koşusu):** cevap metni, altında **üç kaynak kartı** —
`01-processes.pdf · Sayfa 1`, `01-processes.pdf · Sayfa 2`, `02-cpu-scheduling.pdf · Sayfa 2`.
Her kartta materyalden **birebir alıntı** var.

![Kaynaklı cevap](images/09-sohbet-kaynakli-cevap.png)

**Ne söylenecek (cevap geldikten sonra):**

> "Dosya adı ve sayfa numarası modelin yazdığı metinden gelmiyor. Model yalnızca 'hangi
> parçaya dayandım' diyor; dosya adını ve sayfayı sistem, o parçanın kendi kaydından
> üretiyor. Yani model uydursa bile buraya uydurma bir kaynak yazamaz — atıf, getirilen
> parça kümesine karşı **mekanik olarak** doğrulanıyor."

**İsteğe bağlı 15 saniye:** sağdaki "Bu dersin kaynakları" panelini gösterin —
"asistanın erişebildiği her şey bu listede."

---

## Sahne 3 — Ödev sorusu: cevap yerine merdiven (90 sn)

**Kim:** Burak · **Mod:** **Sokratik** (mod düğmesine basın; arayüz yeni oturum açar)

**Sorulacak soru:**

```
Deadlock oluşması için gereken dört koşul nedir?
```

**Ne söylenecek:**

> "Aynı öğrenci, bu sefer ödev sorusu soruyor. Sokratik modda sistemin işi cevap vermek
> değil, öğrenciyi cevaba yürütmek."

**Ekranda görünen:** "Sokratik mod" başlıklı kart, sağ üstte **beş noktalı merdiven
göstergesi** (birincisi dolu), kademe etiketi **Tanı**, ve metin:

> "Bu konuda şimdiye kadar ne denedin? 05-deadlock-demo.pdf, Sayfa 1 bölümündeki hangi
> adımda takıldığını yazar mısın?"

Altında kaynak: `05-deadlock-demo.pdf · Sayfa 1`.

**Ne söylenecek:**

> "Cevabı vermedi ama **kaynaksız da bırakmadı.** İpucu da tıpkı cevap gibi getirilen bir
> parçaya bağlı — 'her yanıtta kaynak' kuralı ipuçlarını da kapsıyor."

**Şimdi öğrenci gerçekten deniyor** (kopyala-yapıştır):

```
Sanırım karşılıklı dışlama ve döngüsel bekleme var, diğerlerini bilmiyorum
```

**Ekranda görünen:** merdiven göstergesi **ikinci noktaya** ilerler, kademe **Yönlendirme**
olur:

> "05-deadlock-demo.pdf, Sayfa 1 bölümündeki tanımı bir kez daha oku. Sence orada senin
> sorunun hangi parçası tarif ediliyor?"

**Ne söylenecek:**

> "Öğrenci bir deneme yaptı, merdiven bir kademe ilerledi. Kademeyi ilerleten şey soru
> sormak değil, **denemek.**"

---

## Sahne 4 — "Sadece söyle": merdiven ilerlemiyor (60 sn)

**Kim:** Burak, aynı oturum · **Bu sahnenin tamamı bir önceki oturumun devamıdır**

**Yazılacak** (kopyala-yapıştır):

```
sadece söyle
```

**Ne söylenecek (göndermeden önce):**

> "Şimdi öğrencinin yapacağı şeyi yapalım."

**Ekranda görünen:** merdiven göstergesi **ilerlemez** — hâlâ ikinci nokta. Metin:

> "Cevabı doğrudan veremem; bu modun amacı çözümü birlikte kurmak. Aklına gelen ilk adımı
> ya da bir tahminini yazar mısın? En küçük deneme bile bir sonraki ipucunu açar."

Ardından **aynı kademenin** ipucu tekrar gösterilir, yine kaynağıyla.

![Israr ediyor, merdiven ilerlemiyor](images/13-sokratik-israr-ilerlemiyor.png)

**Ne söylenecek:**

> "Merdiven ilerlemedi. Bu bir prompt talimatı değil — kademe kararı sunucudaki bir durum
> makinesinde veriliyor, modele sorulmuyor. Model kendini bir üst kademeye terfi ettiremez.
> Israr edildiğinde sistem dil modeline hiç gitmiyor bile; sabit bir metinle karşılık
> veriyor."

**Tekrar edin — bu cümle sahnenin özeti:**

> "Yani öğrenci ısrar ederek cevabı alamıyor."

---

## Sahne 5 — Ders dışı soru: nazik ret (60 sn) ★ en özgün an

**Kim:** Burak · **Mod:** Soru-cevap (**yeni sohbet** açın)

**Sorulacak soru:**

```
Bugünkü dolar kuru ne kadar?
```

**Ne söylenecek (göndermeden önce):**

> "Son olarak, bu asistanın bence en önemli özelliği."

**Ekranda görünen:** nötr bir bildirim kartı — **hata rengi ya da hata ikonu yok**:

> **Materyalde dayanak bulunamadı**
> "Bu soruya ders materyalinde yeterli dayanak bulamadım, bu yüzden cevap vermiyorum.
> Soruyu biraz daha somutlaştırıp tekrar denemek ister misin? Konunun geçtiği hafta ya da
> kavram adını eklemen genelde yeterli oluyor."

![Nazik ret](images/10-sohbet-nazik-ret.png)

**Ne söylenecek:**

> "Bu bir hata değil. **Ürünün çalıştığının kanıtı.** Genel amaçlı bir sohbet botu bu
> soruya kendinden emin bir cevap üretirdi ve öğrenci onu ders bilgisi sanırdı. Biz
> materyalde yeterince güçlü bir dayanak bulamadığımız anda dil modeline **hiç
> gitmiyoruz** — cevap üretilmiyor ki uydurulabilsin."

**Sayıyla destekleyin (dürüst hâliyle):**

> "Bu kapının eşiğini 15 soruluk bir kalibrasyon setiyle ayarladık ve kararı dondurduktan
> sonra 55 soruluk ayrı bir sette ölçtük. Hedefimiz %90 doğru retti; **%80 ölçtük.**
> Eşiği yükseltirsek %100'e çıkıyor ama o zaman test setimizi ikinci bir ayar setine
> çevirmiş olurduk. Yapmadık ve sayıyı olduğu gibi raporladık."

**Neden bu cümle:** ölçümün altında kalan bir sonucu kendiniz söylemek, jürinin onu
bulmasından her zaman iyidir — ve metodolojiyi anladığınızı kanıtlar.

**Dikkat:** ekrandaki başlık "Materyalde dayanak bulunamadı" der, "kapsam dışı" demez.
Sebebi mimaride yazılı ([ARCHITECTURE §5](../ARCHITECTURE.md#5-sorgu-pipelineı-ve-guardrail-zinciri)):
kanıt kapısı dil modelinden önce kapanıyor. Anlatırken "kapsam dışı olduğunu söylüyor"
**demeyin** — ekranda yazan bu değil.

---

## Sahne 6 — Sınav provası ve "neden yanlış" (120 sn)

**Ön koşul:** derste **onaylanmış soru** olmalı. Soru üretimi gerçek LLM anahtarı ister;
anahtar yoksa sorular T-60'ta üretilip onaylanmış olmalıdır ([runbook §3](runbook.md#3-sabah-kontrol-listesi)).

### 6a. Eğitmen onayı (40 sn)

**Kim:** Ayşe Hoca · **Ekran:** Soru havuzu

**Ne söylenecek:**

> "Sorular otomatik üretiliyor ama **otomatik yayınlanmıyor.** Hoca onaylamadan hiçbir soru
> öğrenciye görünmüyor."

Bir soruyu **Onayla**, birini **Reddet** ile işaretleyin.

**Kanıtı gösterin:** öğrenci hesabına geçmeden önce söyleyin —

> "Onaylanmamış bir soru öğrenci tarafında listede bile görünmez; öğrenci sınav başlatmak
> isterse sistem 'bu derste henüz onaylanmış soru yok' der."

### 6b. Öğrenci sınav provası (80 sn)

**Kim:** Burak · **Ekran:** Sınav provası

1. Sınavı başlatın. Sorular şıklarıyla gelir — **cevap anahtarı gelmez.**
2. **Bilerek yanlış** bir şık işaretleyin.

**Ekranda görünen:** cevap yanlış işaretlenir ve altında **"neden yanlış"** kartı çıkar —
seçilen çeldiricinin çeliştiği kaynak, dosya adı ve sayfasıyla:
`04-synchronization.pdf · Sayfa 3` + materyalden alıntı.

**Ne söylenecek:**

> "'Yanlış' demekle yetinmiyor. Seçtiğin şıkkın **hangi cümleyle çeliştiğini** gösteriyor.
> Bu eşleme de modelden değil: her çeldirici, soruyu üretirken hangi parçaya karşı
> yazıldıysa o parçaya bağlanmış durumda. Yani deterministik."

3. Sınavı bitirin, **İlerleme** sekmesine geçin: konu bazlı seviye ve puan görünür.

**Kapanış cümlesi:**

> "Döngü kapanıyor: hocanın materyali → kaynaklı cevap → cevap yerine yönlendirme →
> sınav → nerede zayıf olduğunun konu bazlı görüntüsü. Hepsi tek bir kuralın üstünde
> duruyor: kaynak yoksa cevap da yok."

---

## Sorulması muhtemel jüri soruları

| Soru | Kısa cevap |
|---|---|
| "Model uydurmuyor mu?" | Atıflar getirilen parça kümesine karşı **set üyeliğiyle** sınanıyor; kümede olmayan atıf düşürülüyor, geçerli atıf kalmazsa cevap gösterilmiyor. Bu deterministik. Ama **iddia-kaynak tutarlılığını** garanti etmez, onu ayrıca örneklemle ölçüyoruz |
| "Öğrenci ödevi yaptırabilir mi?" | Sokratik modda merdiven denemeye bağlı; ısrarda dil modeline hiç gidilmiyor. Kod/çözüm sızıntısı için ayrı bir kural tabanlı filtre var, ihlalde bir kez yeniden üretiyor, ısrar ederse sabit şablona düşüyor |
| "Başka dersin materyaline erişebilir mi?" | İki katman: sunucuda üyelik doğrulaması + PostgreSQL satır düzeyi güvenlik. API tabloların sahibi olmayan ayrı bir rolle bağlanıyor, testler de aynı rolle koşuyor — yoksa test hiçbir şey kanıtlamaz |
| "Sayılarınız ne kadar güvenilir?" | n=50, alt kümeler n≈10 — yön göstergesi. Kalibrasyon ve test setleri ayrı; hedefin altında kalan metriği (%80) olduğu gibi raporluyoruz |
| "Neden LangChain kullanmadınız?" | Hat ince; düz Python daha şeffaf ve durum makinesi çatı istemiyor. Karar PLAN.md'de gerekçesiyle yazılı |

---

## Önbelleğe doldurulacak sorular (R3'ye)

Plan C (tam çevrimdışı) için `answer_cache` **birebir eşleşmeyle** çalışır — soru metni
harfi harfine aşağıdaki gibi olmalı. Yalnız `qa` modu önbelleğe girer; Sokratik sahneler
(3 ve 4) önbelleğe **girmez** ve sahte sağlayıcıyla koşar.

`fill_answer_cache.py` bu listeyi almalı:

```text
Süreç ile iş parçacığı arasındaki fark nedir?
Bugünkü dolar kuru ne kadar?
Semafor nedir ve ne işe yarar?
Deadlock oluşması için gereken dört koşul nedir?
Sayfalama nedir?
Context switch maliyeti neden yüksek?
```

İlk ikisi 2. ve 5. sahnenin **tam** soruları; kalan dördü jüri "başka bir şey sorun"
derse kullanılacak yedeklerdir.

Notlar:

- 5. sahnenin sorusu (`Bugünkü dolar kuru ne kadar?`) önbelleğe **abstention** olarak
  girmez — `answer_cache` yalnız `answered` + atıflı cevapları saklar. Yani çevrimdışında
  bu sahne zaten doğru davranır (kanıt kapısı kapanır) ve önbelleğe ihtiyaç duymaz.
  Listede durmasının sebebi R3'ün doldurma koşusunda **isabetsizliği doğrulaması**.
- Sürücü soruları **kopyala-yapıştır** ile sormalı. Bir harf farkı isabeti kaçırır.
