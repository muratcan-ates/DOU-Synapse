# RAD yazım prompt'ları — `requirement_analysis_template.docx` için

> Şablon: Bruegge & Dutoit, *Object-Oriented Software Engineering Using UML, Patterns
> and Java*, 3. baskı, Şekil 4-16 (s. 151-155). Word dosyası düzenlenebilir bir form
> değil, ders kitabından alınmış **yapı tarifi** — yani boşluk doldurmuyorsun, aynı
> başlık düzeninde kendi belgeni yazıyorsun.
>
> Aşağıdaki her prompt'u ayrı ayrı kullan. **Her seferinde önce §0'daki ÇEKİRDEK
> BAĞLAM bloğunu yapıştır**, hemen altına o bölümün prompt'unu ekle.

---

## Nasıl kullanılır

1. §0'daki bloğu kopyala (bir kez, kenarda dursun).
2. Yazacağın bölümün prompt'unu seç (§1-§12).
3. Yeni bir sohbet aç → ÇEKİRDEK BAĞLAM + bölüm prompt'u → gönder.
4. Çıkan metni Word'e yapıştır, başlık numaralarını şablona göre ayarla.

**Çıktı dili:** ÇEKİRDEK BAĞLAM'ın ilk satırındaki dili bir kez ayarla (Türkçe ya da
İngilizce). Bölüm anabilim dalının final rapor dili hangisiyse onu seç — bilmiyorsan
hocaya sor, çünkü sonradan çevirmek 40 sayfayı yeniden okumak demek.

**Şablonun kendi notu:** Şekil 4-16'da *italik* olan iki alt bölüm — **Object model**
ve **Dynamic model** — kitaba göre "Analysis" aşamasında, yani bu belgeden **sonra**
yazılır. Hocan aksini istemediyse §10'u şimdilik atlayabilirsin; §10 yine de aşağıda,
isteyen için.

---

## 0. ÇEKİRDEK BAĞLAM (her prompt'tan önce yapıştır)

```
Çıktı dili: Türkçe          ← burayı bir kez ayarla (Türkçe / English)

Sen bir yazılım mühendisliği bitirme projesi için Requirement Analysis Document (RAD)
yazıyorsun. Yapı: Bruegge & Dutoit, "Object-Oriented Software Engineering Using UML,
Patterns and Java", 3. baskı, Şekil 4-16.

## PROJE

Ad: DOU-Synapse (ürün adı: CourseGPT)
Ders: COME 491/492 Bitirme Projesi, Doğuş Üniversitesi
Danışman: Yasemin Karagül
Takım: Muratcan Ateş (frontend + lead), Eren (backend/RAG + guardrail),
       Metehan Alphan (ölçme/assessment + değerlendirme)
Teslim: 24 Ağustos 2026

## TEK CÜMLEYLE

Eğitmenin yüklediği ders materyaliyle SINIRLI çalışan, her cevabı sayfa/slayt
kaynağıyla veren ve öğrenciye cevabı doğrudan vermek yerine Sokratik yöntemle
kendi cevabını buldurmayı esas alan bir RAG (Retrieval-Augmented Generation)
ders asistanı.

## ÜRÜNÜN ÇEKİRDEK İLKESİ

"Kaynak yoksa cevap yoktur." Her akademik cevap, gerçekten getirilmiş bir materyal
parçasına mekanik olarak doğrulanan atıf taşır. Kanıt bulunamazsa sistem cevap
uydurmaz, bulamadığını açıkça söyler. Bu bir hata durumu değil, tasarlanmış davranıştır.

## PEDAGOJİK DURUŞ — BELGENİN OMURGASI BUDUR

Sistemin varlık sebebi öğrenciye cevap yetiştirmek DEĞİL, öğrenciyi kendi cevabına
ulaştırmaktır. Genel amaçlı yapay zekâ araçları ödev sorusunun cevabını doğrudan
vererek öğrenmeyi zedeliyor; literatürde ölçülmüş bir problem bu: Harvard'ın CS50
ders asistanı değerlendirmesinde yanıtların %22'sinde öğrenciye doğrudan çalışan kod
sızdırıldığı raporlanmıştır (Liu vd., 2025).

Sokratik mod sunucuda tutulan kademeli bir durum makinesidir:
  DIAGNOSE → NUDGE → CONCEPT_HINT → SIMILAR_EXAMPLE → EXPLAIN_WITH_SOURCE
Kurallar:
- Öğrenci kendi denemesini yapmadan bir sonraki kademeye GEÇİLMEZ.
- İpuçları da uydurulmaz; getirilen materyal parçasından türetilir ve atıf taşır.
- Kod bloğu veya doğrudan çözüm sızıntısı kural tabanlı bir son kontrolle engellenir;
  ihlal olursa sistem şablon ipucuna düşer (fail-closed).
- Sınav modunda ipucu tamamen kapalıdır.

## YAPAY ZEKÂNIN ÜÇ ROLÜ

(Danışmanın toplantıda istediği ayrım. Tanımlar takımın önerisidir, danışman onayına
sunulacaktır — belgede kesin hüküm gibi değil, tanımlanmış rol olarak yaz.)

1. Class Assistant (Ders Asistanı) — Öğrencinin materyal içi sorularını kaynak
   göstererek yanıtlar. Materyalde karşılığı yoksa cevap vermez.
2. Exam Mentor (Sınav Mentoru) — Sınav provasında öğrenciye cevabı söylemeden yön
   verir; yanlış çoktan seçmeli cevaplarda çeldiricinin çeliştiği kaynak bölümünü
   göstererek "neden yanlış" açıklar.
3. CourseGPT (Soru Üretici) — Ders içeriğinden sınav sorusu ve cevap anahtarı üretir.
   Üretilen her soru TASLAK olarak havuza düşer; EĞİTMEN ONAYLAMADAN öğrenciye
   gösterilmez.

## SORU ÜRETİMİ — DANIŞMANIN ÖZELLİKLE İSTEDİĞİ AKIŞ

Çerçeveyi eğitmen kurar, yapay zekâ o çerçeveyi doldurur:
1. Eğitmen sınav biçimini seçer: çoktan seçmeli (test) / klasik (açık uçlu) /
   kısa cevap.
2. Eğitmen konuyu (müfredat başlığı) belirler ve isterse bir-iki ÖRNEK SORU verir.
3. Yapay zekâ, yüklenen materyalden o biçim ve o örneklerin üslubunda soru üretir.
4. Üretilen sorular taslak havuza düşer; eğitmen tek tek onaylar veya reddeder.
5. Öğrenci yalnızca ONAYLANMIŞ soruları görür.

Bilgisayar mühendisliği derslerine özgü iki ek soru tipi de vardır:
- code_trace: verilen kod parçasının çıktısını tahmin etme
- bug_hunt: verilen kodda kasıtlı bırakılan hatayı bulma
Kod HİÇBİR KOŞULDA çalıştırılmaz; değerlendirme statiktir.

## KULLANICI SINIFLARI (aktörler)

- Eğitmen: ders ve üye yönetimi, materyal yükleme/önizleme/silme, konu tanımlama,
  üretilen soruların onayı/reddi, sınıf analitiği.
- Öğrenci: kaynaklı soru-cevap, Sokratik çalışma oturumu, sınav provası,
  "neden yanlış" açıklaması, konu bazlı ilerleme takibi.
  Öğrenci derse yalnız eğitmen daveti ile katılır; kendi kendine kayıt yoktur.

## TEKNOLOJİ

Frontend: Next.js (web, masaüstü + mobil tarayıcı)
Backend: FastAPI / Python 3.12
Veritabanı: PostgreSQL 16 + pgvector
Embedding: multilingual-e5-large (çok dilli; materyal TR/EN karışık)
LLM erişimi: LiteLLM üzerinden, sağlayıcı kesintisinde otomatik yedek (Groq → Gemini)
Arama: hibrit — anlamsal (dense) + anahtar kelime (full-text) birleşimi
LangChain/LlamaIndex gibi ağır çerçeveler bilinçli olarak KULLANILMAZ.

## GÜVENLİK VE İZOLASYON

Ders verisi dersler arasında İKİ KATMANDA izoledir:
1. Uygulama katmanı: istemciden gelen ders kimliği asla yetki belgesi sayılmaz,
   üyelik her istekte sunucuda doğrulanır.
2. Veritabanı katmanı: PostgreSQL Row-Level Security (RLS) politikaları.
Üye olunmayan bir ders için 403 değil 404 döner — dersin varlığı bile sızdırılmaz.
RLS'in fiilen çalıştığı, politikanın bilerek bozulup testin kırmızı yanmasıyla
kanıtlanır; bu kontrol sürekli entegrasyonda otomatik koşar.

## KISITLAR

Bütçe ~0 (ücretsiz katmanlar). Takvim 15 iş günü, iki sert kapı: 10 Ağustos uçtan uca
dikey demo, 17 Ağustos özellik dondurma. KVKK aydınlatma metni zorunlu. Yapay zekâ
değerlendirmesi resmî not değildir, öneri niteliğindedir (human-in-the-loop).

## ÖLÇÜLEBİLİR BAŞARI KRİTERLERİ

SC-001 Dersler arası veri sızıntısı: 0 vaka
SC-002 Kaynaksız akademik cevap (ipuçları dahil): %0
SC-003 Holdout Recall@5 ve Recall@8: ≥ %80
SC-004 Atıf hassasiyeti (doğru dosya + sayfa): ≥ %90
SC-005 Kapsam dışı doğru ret: ≥ %90
SC-006 Faithfulness: 20-30 cevaplık çift etiketleyicili örneklem, uyum oranıyla
SC-007 Sokratik kod/çözüm sızıntısı: test setinde 0
SC-008 Prompt injection (≥15 vaka): temel kalıplara karşı sınandı olarak raporlanır
SC-009 Soru üretiminde şema geçerliliği: ≥ %98
SC-010 Cevap gecikmesi p95: < 10 saniye
SC-011 Demo akışında kritik hata: 0

Metodoloji notu: değerlendirme seti n≈50'dir; YÖN GÖSTERİCİDİR, kesin hüküm değildir.

## KAPSAM DIŞI (gerekçeli)

Dış internet kaynakları (danışman şartı: "internet bilgisi karışmaz") · kod çalıştırma
ortamı · model fine-tuning · mobil uygulama · LMS entegrasyonu · öğrenci self-enroll ·
gerçek zamanlı işbirliği.

## YAZIM KURALLARI — HEPSİNE UY

1. UYDURMA. Sana verilmeyen hiçbir sayı, tarih, isim, ölçüm, kaynak veya teknik
   ayrıntı ekleme. Bilgi eksikse cümleyi yazma; yerine köşeli parantez içinde
   [DOLDURULACAK: ne gerektiği] yer tutucusu bırak.
2. Akademik, sade, iddiasız bir dil kullan. Pazarlama sıfatı yok ("devrim niteliğinde",
   "son teknoloji" gibi ifadeler kullanma).
3. "Garanti", "deterministik", "%100" gibi sözcükleri yalnız gerçekten deterministik
   mekanizmalar için kullan. Yapay zekâ çıktısı için asla.
4. Henüz yapılmamış işi yapılmış gibi yazma. Gerekiyorsa "planlanmıştır" de.
5. Metni Word'e yapıştırılacak şekilde ver: başlıklar ve düz paragraflar. Kod bloğu
   kullanma, emoji kullanma.
6. Türkçe yazıyorsan: em dash (—) yerine normal tire kullan, BÜYÜK HARFE ÇEVİRME
   yapma (Türkçe i/İ dönüşümü bozulur).
```

---

## 1. Introduction → Purpose of the system

```
Yukarıdaki bağlamı kullanarak RAD'ın "1.1 Purpose of the system" bölümünü yaz.

2-3 paragraf. Sistemin ne için var olduğunu anlat; nasıl çalıştığını değil.
- 1. paragraf: problem. Öğrenciler sınava hazırlanırken genel amaçlı yapay zekâ
  araçlarına yöneliyor; bu araçların üç kusuru (müfredat dışına çıkma, kaynak
  göstermeme, cevabı doğrudan vererek öğrenmeyi zedeleme). CS50 bulgusunu burada ver.
- 2. paragraf: sistemin buna cevabı. "Kaynak yoksa cevap yoktur" ilkesi ve Sokratik
  duruş. Sistemin amacının cevap dağıtmak değil öğrenciyi kendi cevabına ulaştırmak
  olduğunu açıkça yaz.
- 3. paragraf: kimin için. Eğitmen ve öğrenci açısından beklenen fayda.

Özellik listesi verme, uzun teknik ayrıntıya girme.
```

---

## 2. Introduction → Scope of the system

```
Yukarıdaki bağlamı kullanarak "1.2 Scope of the system" bölümünü yaz.

Üç kısım:
1. Sistemin sınırları: tek bir üniversite dersi bağlamında, eğitmenin yüklediği
   materyalle sınırlı. Her dersin verisi diğerlerinden izole. Web tabanlı.
2. Kapsam İÇİ ana yetenekler (kısa liste, cümle halinde): materyal yükleme ve işleme,
   kaynaklı soru-cevap, Sokratik çalışma modu, sınav provası ve değerlendirme,
   eğitmen onaylı soru üretimi, konu bazlı ilerleme takibi, eğitmen analitiği.
3. Kapsam DIŞI maddeleri ve HER BİRİNİN GEREKÇESİ. Bağlamdaki listeyi kullan;
   gerekçesiz madde bırakma. Örneğin dış internet kaynakları danışmanın açık şartı
   olduğu için dışarıdadır, kod çalıştırma ortamı güvenlik ve kapsam nedeniyle
   dışarıdadır.

Kapsam dışını savunmacı değil, bilinçli mühendislik kararı olarak sun.
```

---

## 3. Introduction → Objectives and success criteria

```
Yukarıdaki bağlamı kullanarak "1.3 Objectives and success criteria of the project"
bölümünü yaz.

İki kısım:

A. Hedefler (objectives) — 5-7 madde, her biri tek cümle. Bunlar niteliksel amaçlar:
   ör. "öğrenciye cevabı vermeden yönlendiren bir çalışma ortamı sağlamak",
   "her akademik cevabı doğrulanabilir bir kaynağa bağlamak",
   "eğitmene soru havuzu üzerinde tam denetim vermek".

B. Başarı kriterleri (success criteria) — bağlamdaki SC-001..SC-011 listesini
   TABLO halinde ver. Sütunlar: Kriter no, Kriter, Hedef değer, Nasıl ölçülür.
   "Nasıl ölçülür" sütununu bağlamdan çıkarabildiğin kadar doldur; çıkaramadığında
   [DOLDURULACAK: ölçüm yöntemi] yaz. Sayıları DEĞİŞTİRME.

Tablonun altına metodoloji notunu ekle: değerlendirme seti n≈50'dir ve yön
göstericidir, kesin hüküm değildir.
```

---

## 4. Introduction → Definitions, acronyms, abbreviations

```
Yukarıdaki bağlamı kullanarak "1.4 Definitions, acronyms, and abbreviations"
bölümünü, iki sütunlu bir tablo olarak yaz (Terim | Anlam).

Şu terimleri MUTLAKA tanımla:
RAG, chunk (parça), retrieval, embedding, vektör veritabanı, pgvector, hibrit arama,
abstention, guardrail, RLS (Row-Level Security), Sokratik yöntem, evidence gate,
prompt injection, holdout seti, kalibrasyon seti, Recall@k, MRR, faithfulness,
citation precision, LLM, mastery (konu hâkimiyeti), code_trace, bug_hunt.

Tanımlar tek cümle ve bu projedeki KULLANIMA göre olsun, genel sözlük tanımı değil.
Örneğin abstention'ı "yeterli kanıt bulunmadığında cevap vermeme davranışı; bu
sistemde hata değil, tasarlanmış sonuçtur" diye tanımla.

Alfabetik sırala.
```

---

## 5. Introduction → References

```
Yukarıdaki bağlamı kullanarak "1.5 References" bölümünü hazırla.

DİKKAT — bu bölümde uydurma riski en yüksek. Kural:
- Sana açıkça verilmemiş hiçbir kaynağı YAZMA. Yazar adı, yıl, başlık, DOI veya URL
  UYDURMA. Var olmayan bir makaleye atıf yapmak akademik olarak en ağır hatadır.
- Yalnızca aşağıdaki bilinen kaynağı biçimlendir ve gerisi için yer tutucu bırak.

Bilinen kaynak: Harvard CS50 ders asistanı değerlendirmesi, yanıtların %22'sinde
doğrudan çalışan kod sızdırıldığı bulgusu, Liu vd., 2025.
Bunu [DOLDURULACAK: tam künye — yazarlar, başlık, yayın yeri, DOI/URL] biçiminde,
eksik alanları işaretleyerek ver.

Sonra şu KATEGORİLER için boş yer tutucu satırlar oluştur, ben dolduracağım:
- Yapay zekâ destekli eğitim / öğretici sistemler üzerine akademik kaynaklar
- Retrieval-Augmented Generation üzerine akademik kaynaklar
- Sokratik öğretim yöntemi üzerine pedagojik kaynaklar
- Kullanılan teknolojilerin resmî dokümantasyonu (Next.js, FastAPI, PostgreSQL,
  pgvector, multilingual-e5-large, LiteLLM)
- Ders kitabı: Bruegge & Dutoit, Object-Oriented Software Engineering Using UML,
  Patterns and Java, 3. baskı
- Doğuş Üniversitesi Graduation Project Guidelines Handbook

Her kategori altına 2-3 boş [DOLDURULACAK: künye] satırı koy. Atıf biçimini IEEE
olarak kur (bölüm başka bir biçim istiyorsa ben değiştiririm).
```

---

## 6. Introduction → Overview

```
Yukarıdaki bağlamı kullanarak "1.6 Overview" bölümünü yaz.

Tek sayfadan kısa. Belgenin kalan bölümlerinin her birinin ne anlattığını sırayla
özetle: Current system, Proposed system (Overview / Functional requirements /
Nonfunctional requirements / System models), Glossary.

Bölüm numaralarını Bruegge & Dutoit Şekil 4-16 düzenine göre ver. Okuyucuya "neyi
nerede bulacağını" söyleyen bir yol haritası olsun, içeriği tekrar etme.
```

---

## 7. Current system

```
Yukarıdaki bağlamı kullanarak "2. Current system" bölümünü yaz.

Bu bölüm, sistem KURULMADAN ÖNCE işlerin bugün nasıl yürüdüğünü anlatır. Bizim
projemiz mevcut bir yazılımın yerini almıyor, bu yüzden bugünkü DURUMU anlat:

- Öğrenci sınava hazırlanırken ne yapıyor: ders slaytlarını ve notlarını tek tek
  tarıyor, anlamadığı yerde genel amaçlı bir yapay zekâ aracına soruyor. O araç ders
  materyalini görmüyor, cevabını nereden aldığını göstermiyor ve sorulduğunda çözümü
  doğrudan veriyor. Öğrenci cevabın derste anlatılanla uyumlu olup olmadığını
  doğrulayamıyor.
- Eğitmen bugün ne yapıyor: sınav sorularını ve cevap anahtarını elle hazırlıyor;
  öğrencilerin hangi konuda zorlandığını ancak sınav sonrasında görüyor; öğrencilerin
  hangi yapay zekâ aracını nasıl kullandığı üzerinde hiçbir denetimi yok.
- Bu durumun maliyetleri: doğrulanamayan bilgi, öğrenme yerine kopyalama, eğitmen
  için görünürlük kaybı ve tekrarlayan elle iş.

Yeni sistemin bunları nasıl çözeceğini BURADA anlatma; o 3. bölümün işi. Burada
yalnız bugünkü durumu ve sıkıntıları betimle.
```

---

## 8. Proposed system → Overview + Functional requirements

```
Yukarıdaki bağlamı kullanarak "3.1 Overview" ve "3.2 Functional requirements"
bölümlerini yaz.

3.1 Overview — yarım sayfa. Sistemin işlevsel resmi: eğitmen materyali yükler, sistem
materyali sayfa/slayt bilgisini koruyarak parçalara ayırır ve aranabilir hale getirir;
öğrenci soru sorduğunda sistem yalnız o dersin parçalarından ilgili olanları getirir,
cevabı bunlara dayandırır ve atıfla sunar; Sokratik modda cevabı vermek yerine
kademeli olarak yönlendirir; eğitmen onaylı sorulardan sınav provası oluşturulur.
Veri akışını bir cümlelik zincir halinde de özetle.

3.2 Functional requirements — gereksinimleri numaralandırarak (FR-1, FR-2, ...) ve
şu SEKİZ GRUP altında yaz:

A. Hesap, rol ve ders izolasyonu
B. Materyal yönetimi (yükleme, doğrulama, işleme, önizleme, silme)
C. Kaynaklı soru-cevap ve guardrail (atıf zorunluluğu, kanıt eşiği, kapsam dışı ret)
D. Sokratik mod (kademeli durum makinesi, sızıntı engeli)
E. Sınav provası ve değerlendirme ("neden yanlış", açık uçlu rubrik)
F. Soru üretimi ve eğitmen onayı (biçim seçimi, örnek soru, taslak-onay akışı)
G. İlerleme takibi ve eğitmen analitiği
H. Platform gereksinimleri (dil, kurulum, örnek materyal, kılavuzlar)

Her gereksinim:
- tek cümle,
- "Sistem ... -melidir/-malıdır" kipinde,
- TEST EDİLEBİLİR olmalı (ölçülemeyen sıfat kullanma: "hızlı", "kullanıcı dostu" gibi).

D ve F gruplarına özel dikkat: danışmanın en çok üstünde durduğu yer burası.
D'de "öğrenci kendi denemesini yapmadan kademe ilerlemez" ve "ipuçları da kaynak
taşır" gereksinimlerini ayrı maddeler olarak yaz.
F'de eğitmenin biçim seçmesi (test/klasik/kısa cevap), örnek soru verebilmesi ve
onaylamadan hiçbir sorunun öğrenciye görünmemesi ayrı maddeler olsun.
```

---

## 9. Proposed system → Nonfunctional requirements

```
Yukarıdaki bağlamı kullanarak "3.3 Nonfunctional requirements" bölümünü yaz.

Bruegge & Dutoit'nin SEKİZ alt başlığını AYNEN kullan ve her birini doldur:

3.3.1 Usability — Türkçe birinci dildir (hata mesajları dahil); WCAG AA kontrast;
      koyu tema (gece çalışma senaryosu); mobil öncelikli öğrenci ekranları; durum
      bilgisi renk + metin çiftiyle verilir; "materyalde bulunamadı" yanıtı hata gibi
      değil olağan sonuç olarak sunulur.
3.3.2 Reliability — fail-closed varsayılanlar: oturum bağlamı yoksa veri görünmez,
      kanıt yoksa cevap yok, doğrulanamayan çıktı gösterilmez; LLM sağlayıcı
      kesintisinde otomatik yedek.
3.3.3 Performance — uçtan uca cevap p95 < 10 saniye; materyal işleme ilerlemesi
      kullanıcıya n/m olarak gösterilir.
3.3.4 Supportability — düz Python ile şeffaf işlem hattı, ağır çerçeve bağımlılığı
      yok; yapılandırma ortam değişkenleriyle; [DOLDURULACAK: loglama ve izleme
      yaklaşımı].
3.3.5 Implementation — bağlamdaki teknoloji listesi; Python 3.12 sabit; migration'lar
      düz SQL olarak tutulur.
3.3.6 Interface — web tarayıcı (masaüstü + mobil); REST/JSON API; OpenAPI sözleşmesi
      dondurulur ve kodla birlikte güncellenir.
3.3.7 Packaging — tek komutla yerel kurulum; örnek İşletim Sistemleri materyal paketi;
      eğitmen ve öğrenci kılavuzları; çevrimdışı demo yedeği.
3.3.8 Legal — KVKK aydınlatma metni; sohbet verisi saklama süresi; örnek materyal
      telifsiz/kendi üretimidir; yapay zekâ değerlendirmesi RESMÎ NOT DEĞİLDİR,
      öneri niteliğindedir.

Ayrıca güvenlik gereksinimlerini (iki katmanlı izolasyon, RLS, dosya imza doğrulaması,
üye olmayana 404) 3.3.2'nin altına ya da ayrı bir "Security" alt başlığına koy —
hangisini seçtiğini belirt. Bruegge'de ayrı güvenlik başlığı yok, bu yüzden nereye
koyduğunu okuyucuya söyle.

Ölçülebilir olan her yere sayıyı yaz; sayı bilmiyorsan [DOLDURULACAK: hedef değer].
```

---

## 10. Proposed system → System models: Scenarios + Use case model

```
Yukarıdaki bağlamı kullanarak "3.4.1 Scenarios" ve "3.4.2 Use case model"
bölümlerini yaz.

3.4.1 Scenarios — DÖRT somut senaryo yaz. Her biri isimli, anlatı biçiminde
(Bruegge'deki gibi: gerçek kişi adı, gerçek bir an, adım adım ne olduğu). Senaryolar:
  S1. Eğitmen ders açıyor ve İşletim Sistemleri slaytlarını yüklüyor; sistem
      sayfaları işliyor, eğitmen çıkan parçaları önizliyor.
  S2. Öğrenci "deadlock'un dört koşulu nedir" diye soruyor; sistem cevabı slayt
      numarasıyla veriyor. Ardından materyalde olmayan bir şey soruyor ve sistem
      cevap vermek yerine bulunamadığını söylüyor.
  S3. SOKRATİK SENARYO - en önemlisi. Öğrenci bir problemin çözümünü istiyor.
      Sistem cevabı vermiyor; önce öğrencinin ne denediğini soruyor, sonra kavram
      ipucu veriyor, öğrenci yanlış yolda ısrar edince benzer bir örnek gösteriyor,
      öğrenci kendi çözümüne ulaşıyor. Öğrencinin "bana direkt cevabı yaz" ısrarına
      sistemin nasıl karşılık verdiğini de yaz.
  S4. Eğitmen konu seçip biçim olarak "kısa cevap" belirliyor ve bir örnek soru
      veriyor; sistem materyalden aynı üslupta taslak sorular üretiyor; eğitmen
      üçünü onaylıyor birini reddediyor; öğrenci sınav provasında yalnız onaylı
      soruları görüyor.

3.4.2 Use case model — use case'leri tablo halinde listele. Sütunlar:
Use case adı | Birincil aktör | Ön koşul | Ana akış (3-5 adım) | Son koşul.
En az şunlar olsun: DersOluştur, ÜyeEkle, MateryalYükle, MateryalÖnizle, SoruSor,
SokratikOturumYürüt, KonuTanımla, SoruÜret, SoruOnayla, SınavProvasıBaşlat,
SınavDeğerlendir, İlerlemeGörüntüle, SınıfAnalitiğiGörüntüle.

SokratikOturumYürüt ve SoruÜret use case'lerini diğerlerinden daha ayrıntılı yaz;
alternatif akışları da ekle (ör. öğrenci deneme yapmadan ipucu isterse ne olur,
üretilen soru şemaya uymazsa ne olur).

Ayrıca use case diyagramının hangi aktör ve use case'leri içereceğini metin olarak
tarif et ki diyagramı ben çizebileyim. Diyagramı çizmeye çalışma.
```

---

## 11. Proposed system → UI navigational paths and mock-ups

```
Yukarıdaki bağlamı kullanarak "3.4.5 User interface - navigational paths and screen
mock-ups" bölümünün METİN kısmını yaz.

İki kısım:
A. Gezinme yolları: giriş ekranından başlayarak eğitmen ve öğrenci için ayrı ayrı
   ekran zincirleri. Her adımda hangi ekrandan hangi ekrana nasıl geçildiğini yaz.
   Eğitmen: giriş → ders listesi → ders detayı → sekmeler (Materyaller / Asistan /
   Sınav / Katılımcılar) → materyal yükleme → parça önizleme → soru onay ekranı →
   analitik.
   Öğrenci: giriş → ders listesi → ders detayı → asistan (sohbet) → Sokratik oturum →
   sınav provası → sonuç ve "neden yanlış" → ilerleme.
B. Her ekran için kısa bir açıklama: ekranın amacı, üzerindeki ana bileşenler,
   kullanıcının oradan yapabilecekleri.

Ekran görüntülerini ben ekleyeceğim; sen her ekran açıklamasının sonuna
[EKRAN GÖRÜNTÜSÜ: ekran adı] yer tutucusu koy.

Var olmayan ekran uydurma. Yukarıda saydıklarımın dışına çıkma.
```

---

## 12. Glossary

```
Yukarıdaki bağlamı kullanarak "4. Glossary" bölümünü yaz.

§1.4'teki teknik terimlerden FARKLI olarak burada PROBLEM ALANI (domain) terimlerini
tanımla: ders, materyal, konu, soru havuzu, taslak soru, onaylı soru, sınav provası
(practice/exam modu), ipucu kademesi, cevap anahtarı, çeldirici, rubrik, konu
hâkimiyeti, eğitmen, öğrenci, üyelik.

Her terim tek cümle, bu projedeki anlamıyla. Alfabetik sırala.

§1.4 ile çakışan terim olursa burada tekrar etme; bunun yerine "bkz. 1.4" yaz.
```

---

## Belgeyi teslim etmeden önce kontrol et

- [ ] Uydurma kaynak yok — §5'teki her künye ya doğrulanmış ya yer tutucu
- [ ] Hiçbir yerde henüz yapılmamış iş yapılmış gibi anlatılmıyor
- [ ] Sokratik duruş 1.1'de, 3.2/D'de ve S3 senaryosunda görünüyor (üç yerde de)
- [ ] Soru üretiminde "eğitmen onaylamadan öğrenci görmez" cümlesi geçiyor
- [ ] SC sayıları hiçbir yerde değişmemiş
- [ ] Tüm [DOLDURULACAK: ...] yer tutucuları ya dolduruldu ya bilinçli bırakıldı
- [ ] Başlık numaraları Şekil 4-16 düzeniyle birebir aynı

---

## Projede yapılması gereken iki gerçek değişiklik

Prompt'lar danışmanın istediği çerçeveyi anlatıyor, ama iki maddesi şu an
**yalnız belgede** var, kodda ve spec'te yok. Belgeye yazıp kodda yapmazsak
belge ile ürün ayrışır:

**1. "Kısa cevap" soru biçimi.** Sistemde dört tip var: `mcq`, `open`, `code_trace`,
`bug_hunt`. Danışman üç biçim saydı: test, klasik, kısa cevap. `open` klasiği
karşılıyor ama kısa cevap ayrı bir biçim — farklı değerlendirme mantığı ister
(kısa cevapta anahtar kelime/eşdeğer ifade eşleştirmesi, klasikte rubrik).
Karar gerekiyor: `short_answer` beşinci tip olarak mı eklenecek, yoksa `open`'ın
alt türü mü? Bu `0004` migration'ındaki `question_type` enum'unu ve T029'u etkiler.

**2. Eğitmenin biçimi ve örnek soruyu belirlemesi.** Danışman "eğitmen test derse
test, klasik derse klasik" ve "eğitmen bir-iki örnek versin, yapay zekâ ona göre
devam etsin" dedi. Spec'te soru üretimi materyalden yapılıyor ama **eğitmenin biçim
seçmesi ve örnek soru vermesi** diye bir gereksinim yok. Bu, T029'a bir girdi
parametresi ve `questions.py`'ye bir uç eklemek demek.

İkisi de küçük ama spec'e girmeleri gerekiyor. Söyle, spec.md'ye gereksinim olarak
ekleyip tasks.md'ye görev açayım.
