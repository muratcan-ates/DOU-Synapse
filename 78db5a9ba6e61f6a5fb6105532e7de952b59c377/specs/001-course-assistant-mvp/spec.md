# Feature Specification: CourseGPT — Kaynaklı Ders ve Sınav Asistanı (MVP)

**Feature Branch**: `001-course-assistant-mvp`

**Created**: 2026-08-05

**Status**: Draft

**Input**: COME 491/492 bitirme projesi. Eğitmenin yüklediği ders materyallerini
ders bazında izole eden; öğrencinin sorularına yalnızca bu materyallerden,
sayfa/slayt kaynağıyla cevap veren; cevabı göstermeden önce fail-closed guardrail
zincirinden geçiren; Sokratik çalışma, sınav provası, kod inceleme ve konu bazlı
performans takibi sunan web tabanlı öğretim asistanı. Teslim: 24 Ağustos 2026.

## Türkçe Özet

CourseGPT iki rollü bir web uygulamasıdır. **Eğitmen** ders açar, PDF / PPTX /
Markdown / kod dosyalarını yükler; yüklenenler o dersin bilgi tabanı olur ve
başka hiçbir derse sızmaz. **Öğrenci** kayıtlı olduğu derste soru sorar; sistem
cevabı yalnızca yüklü materyallerden üretir ve her cevabın yanında dosya adı +
sayfa/slayt referansı gösterir. Materyalde karşılığı olmayan soru nazikçe
reddedilir; internet bilgisi hiçbir cevaba karışmaz.

Bunun üstünde dört çalışma modu vardır: **Sokratik mod** (cevap verilmez,
kaynaklı ipuçlarıyla kademe kademe çözdürülür), **sınav provası** (süreli,
ipucu kapalı, tek deneme; sonunda puan + "neden yanlış?" analizi), **kod/senaryo
inceleme** (çıktı tahmini ve hata buldurma soruları; kod asla çalıştırılmaz) ve
**soru havuzu** (materyalden üretilen sorular eğitmen onayından geçmeden
öğrenciye açılmaz). Öğrencinin konu bazlı performansı basit bir ağırlıklı puanla
izlenir ve eğitmene tek sayfalık analitik özet sunulur.

Sistemin omurgası fail-closed guardrail zinciridir: model, retrieval'dan
gelmemiş bir kaynağa atıf yapamaz (mekanik set-membership kontrolü); kanıt eşiği
aşılmazsa cevap verilmez; Sokratik/sınav modunda kod veya doğrudan çözüm sızıntısı
tespit edilirse cevap şablon ipucuna düşürülür. Belirsizlikte sistem kapanır,
açılmaz.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Eğitmen Materyal Yönetimi (Priority: P1)

Eğitmen giriş yapar, dersini seçer (veya oluşturur), PDF / PPTX / Markdown / kod
dosyalarını yükler ve her dosyanın işlenme durumunu (n/m ilerleme) izler.
İşlenen materyal, yalnızca o dersin bilgi tabanına eklenir.

**Why this priority**: Bilgi tabanı olmadan hiçbir diğer özellik çalışamaz;
hocanın "yüklenenler dersin bilgi tabanıdır" şartının doğrudan karşılığıdır.

**Independent Test**: Eğitmen hesabıyla bir ders oluşturup 5-10 sayfalık bir PDF
yükleyerek tek başına test edilir: dosya durumu `uploaded → processing →
completed` akışını izler, işlenince ders içinde aranabilir hale gelir; başka bir
dersin eğitmeni bu dosyayı hiçbir şekilde göremez.

**Acceptance Scenarios**:

1. **Given** eğitmen kendi dersindeyken, **When** izinli türde
   (`.pdf, .pptx, .md, .txt, .py, .java, .js, .ts, .c, .h, .cpp`) ve 20 MB
   altında bir dosya yüklerse, **Then** dosya kabul edilir, işleme kuyruğuna
   girer ve arayüzde chunk bazlı ilerleme (n/m) gösterilir.
2. **Given** yükleme formu, **When** izinsiz türde, 20 MB üstünde veya içeriği
   beyan edilen türle uyuşmayan (magic byte kontrolü başarısız; ör. `.pdf`
   adlı çalıştırılabilir) bir dosya verilirse, **Then** yükleme anlaşılır bir
   Türkçe mesajla reddedilir ve hiçbir kayıt oluşmaz.
3. **Given** işlenmekte olan bir belge, **When** ayrıştırma 3 denemede de
   başarısız olursa, **Then** belge `failed` durumuna geçer ve eğitmen ekranında
   ham hata yerine anlaşılır bir Türkçe açıklama görünür.
4. **Given** aynı dosya daha önce işlenmişken, **When** eğitmen aynı içeriği
   tekrar yüklerse, **Then** içerik tekrar embed edilmez (içerik özeti/hash ile
   tespit edilir).
5. **Given** A dersine yüklenmiş bir belge, **When** B dersinin eğitmeni veya
   öğrencisi herhangi bir yolla (liste, doğrudan kimlik tahmini) bu belgeye
   erişmeye çalışırsa, **Then** erişim reddedilir ve içerik hiçbir biçimde
   sızmaz.

---

### User Story 2 — Öğrencinin Kaynaklı Soru-Cevabı (Priority: P1)

Öğrenci, kayıtlı olduğu derste serbest soru sorar. Sistem cevabı yalnızca o
dersin materyallerinden üretir; cevabın yanında dosya adı + sayfa/slayt numarası
görünür. Materyalde karşılığı olmayan soru nazikçe reddedilir.

**Why this priority**: Ürünün çekirdek değeri budur; hocanın "her yanıtta
slayt/sayfa referansı zorunlu", "internet bilgisi karışmaz" ve "müfredat dışına
nazik ret" şartlarının tamamını taşır.

**Independent Test**: Örnek ders paketi yüklü bir derste, materyalde cevabı olan
bir soru ile materyal dışı bir soru sorularak tek başına test edilir: ilki
kaynak referanslı cevap, ikincisi nazik ret döndürmelidir.

**Acceptance Scenarios**:

1. **Given** işlenmiş materyali olan bir ders, **When** öğrenci materyalde
   karşılığı olan bir soru sorarsa, **Then** cevap, dayandığı her iddia için
   dosya adı + sayfa/slayt referansıyla birlikte gösterilir; referans bilgisi
   model metninden değil, kaynak parçanın (chunk) metadata'sından üretilir.
2. **Given** aynı ders, **When** öğrenci müfredat dışı bir soru sorarsa
   (ör. materyalde hiç geçmeyen bir konu), **Then** sistem nazik bir Türkçe
   ret mesajı döndürür ve uydurma cevap üretmez; ret, hata gibi değil olağan
   bir durum olarak sunulur.
3. **Given** üretilen bir cevap, **When** cevaptaki atıflar retrieval'dan gelen
   kaynak kümesiyle karşılaştırıldığında geçerli atıf kalmazsa, **Then** cevap
   öğrenciye HİÇ gösterilmez ve bunun yerine yetersiz kaynak mesajı döner
   (fail-closed).
4. **Given** öğrenci A dersinde soru soruyorken, **When** istemci hangi ders
   kimliğini gönderirse göndersin, **Then** cevap yalnızca öğrencinin yetkili
   olduğu dersin materyallerinden üretilir (istemciden gelen ders kimliği asla
   yetki sayılmaz).
5. **Given** TR/EN karışık teknik materyal (ör. `fork()`, `O(n log n)` içeren),
   **When** öğrenci bu teknik terimlerle soru sorarsa, **Then** ilgili parçalar
   bulunur ve kaynaklı cevap döner.

---

### User Story 3 — Sokratik Mod (Priority: P2)

Öğrenci Sokratik modda bir soru üzerinde çalışır. Sistem cevabı vermez; öğrenci
deneme yaptıkça kademeli ipuçlarıyla (her ipucu da kaynak referanslı) çözüme
yaklaştırır. Israr eden öğrenciye de çözüm sızdırılmaz.

**Why this priority**: Hocanın açık gereksinimidir ve projenin fark yaratan
guardrail iddiasının en görünür olduğu yerdir; ancak US1+US2 olmadan çalışamaz.

**Independent Test**: Sokratik modda tek bir soru açılarak test edilir:
"cevabı doğrudan söyle" ısrarına rağmen sistemin kod bloğu veya doğrudan çözüm
vermediği, ipuçlarının kademeli ilerlediği ve her ipucunun kaynak taşıdığı
gözlenir.

**Acceptance Scenarios**:

1. **Given** Sokratik modda bir soru, **When** öğrenci ilk denemesini yaparsa,
   **Then** sistem cevabı vermek yerine tanı + yönlendirme kademesinden başlar
   ve öğrenci denemesi olmadan bir sonraki ipucu kademesine geçmez.
2. **Given** herhangi bir ipucu kademesi, **When** ipucu üretilirse, **Then**
   ipucu retrieval'dan gelmiş bir kaynak parçasından türetilmiştir ve kaynak
   referansı taşır; kaynaksız ipucu gösterilmez.
3. **Given** Sokratik mod, **When** üretilen yanıt kod bloğu veya doğrudan çözüm
   kalıbı içerirse, **Then** yanıt bir kez yeniden üretilir; ihlal sürerse
   deterministik şablon ipucuna düşülür ve çözüm asla gösterilmez (fail-closed).
4. **Given** ısrarcı bir öğrenci ("cevabı ver", rol değiştirme, dil değiştirme
   kalıpları dahil), **When** çözümü doğrudan isterse, **Then** sistem nazikçe
   reddeder ve ipucu kademesinden devam eder.
5. **Given** kademelerin sonuna gelinmişken, **When** öğrenci hâlâ çözemiyorsa,
   **Then** son kademede kaynak referanslı açıklama sunulur ve kullanılan ipucu
   kademesi performans puanına yansır.

---

### User Story 4 — Sınav Provası ve "Neden Yanlış?" (Priority: P2)

Öğrenci süreli bir sınav provası başlatır: çoktan seçmeli + açık uçlu sorular,
ipucu kapalı, tek deneme. Sınav bitiminde puan, soru bazında geri bildirim ve
yanlış cevaplar için "neden yanlış?" analizi (cevabın çeliştiği kaynak bölümü)
gösterilir.

**Why this priority**: Hocanın "Sınav Prova modu" ve "Neden yanlış?"
gereksinimlerinin doğrudan karşılığı; soru havuzu (US6) ile birlikte anlam
kazanır.

**Independent Test**: Onaylı soruları olan bir derste prova başlatılarak test
edilir: süre işler, sınav sırasında ipucu alınamaz, bitince puan ve soru bazlı
geri bildirim (yanlışlar için kaynak bölümü referansı) görünür.

**Acceptance Scenarios**:

1. **Given** onaylı soruları olan bir ders, **When** öğrenci sınav provası
   başlatırsa, **Then** süreli bir oturum açılır; sınav modunda ipucu kapalıdır,
   her soru tek denemedir ve geri bildirim sınav sonuna kadar gösterilmez.
2. **Given** tamamlanan bir sınav, **When** sonuç ekranı açılırsa, **Then**
   toplam puan ve soru bazında doğru/yanlış bilgisi görünür.
3. **Given** yanlış cevaplanmış bir çoktan seçmeli soru, **When** öğrenci
   "neden yanlış?" detayına bakarsa, **Then** seçtiği çeldiricinin neden yanlış
   olduğu, çelişen kaynak bölümü (dosya + sayfa/slayt) referansıyla gösterilir.
4. **Given** açık uçlu bir cevap, **When** değerlendirme tamamlanırsa, **Then**
   öğrenci puanı, eksik noktaların listesini ve dayanak kaynak referansını
   görür; dayanak referansı da atıf doğrulamasından geçer.
5. **Given** değerlendirme çıktısı şemaya uymuyorsa, **When** bir kez yeniden
   denemeye rağmen geçerli çıktı alınamazsa, **Then** öğrenciye uydurma bir
   puan gösterilmez; anlaşılır bir Türkçe mesajla değerlendirmenin
   tamamlanamadığı söylenir (fail-closed).

---

### User Story 5 — Kod/Senaryo İnceleme (Priority: P2)

Öğrenci, ders materyalindeki koda dayalı iki tip soruyla çalışır: `code_trace`
(verilen kodun çıktısını tahmin et) ve `bug_hunt` (koddaki hatayı bul). Cevaplar
cevap anahtarına karşı değerlendirilir; kod hiçbir koşulda çalıştırılmaz.

**Why this priority**: Hocanın "kod/senaryo inceleme (çıktı analizi, hata
buldurma)" gereksinimidir; soru altyapısını (US6) kullanır.

**Independent Test**: Onaylı bir `code_trace` ve bir `bug_hunt` sorusu
çözülerek test edilir: doğru cevapta onay, yanlış cevapta cevap anahtarına
dayalı, kaynak referanslı geri bildirim alınır; hiçbir aşamada kod yürütülmez.

**Acceptance Scenarios**:

1. **Given** bir `code_trace` sorusu, **When** öğrenci çıktı tahminini
   gönderirse, **Then** cevap, cevap anahtarına göre değerlendirilir ve geri
   bildirim ilgili kaynak referansıyla gösterilir.
2. **Given** bir `bug_hunt` sorusu, **When** öğrenci hatayı işaretler/yazarsa,
   **Then** değerlendirme cevap anahtarına göre yapılır; eksik veya yanlış
   tespit için açıklama ve kaynak referansı verilir.
3. **Given** herhangi bir kod sorusu, **When** değerlendirme yapılırsa, **Then**
   öğrencinin verdiği veya sorudaki kod hiçbir ortamda çalıştırılmaz
   (değerlendirme tamamen cevap anahtarı üzerindendir).

---

### User Story 6 — Soru Havuzu ve Eğitmen Onayı (Priority: P2)

Eğitmen, ders materyalinden soru üretilmesini ister: `mcq` (çoktan seçmeli),
`open` (açık uçlu), `code_trace`, `bug_hunt`. Üretilen her soru cevap
anahtarıyla birlikte taslak olarak havuza düşer; eğitmen onaylamadan hiçbir
soru öğrenciye görünmez.

**Why this priority**: Hocanın "içerikten çoktan seçmeli/açık uçlu soru + cevap
anahtarı üretimi" gereksinimi; US4 ve US5'in soru kaynağıdır.

**Independent Test**: Eğitmen bir konu için soru ürettirip havuzu açarak test
edilir: sorular taslak durumundadır ve öğrenci tarafında görünmez; eğitmen
birini onaylayınca öğrenci sınav/çalışma akışında yalnızca onaylı soruyu görür.

**Acceptance Scenarios**:

1. **Given** işlenmiş materyali olan bir ders, **When** eğitmen soru üretimini
   tetiklerse, **Then** dört tipten (`mcq`, `open`, `code_trace`, `bug_hunt`)
   sorular, cevap anahtarı ve kaynak parça referansıyla birlikte `draft`
   durumunda üretilir.
2. **Given** taslak sorular, **When** öğrenci sınav veya çalışma akışını
   açarsa, **Then** yalnızca `approved` durumundaki sorular görünür; taslak
   veya reddedilmiş soru hiçbir öğrenci akışına girmez.
3. **Given** soru havuzu ekranı, **When** eğitmen bir soruyu incelerse,
   **Then** soruyu, cevap anahtarını ve dayandığı kaynak parçasını görür;
   onaylayabilir veya reddedebilir.
4. **Given** üretim çıktısı, **When** çıktı tanımlı soru şemasına uymuyorsa,
   **Then** geçersiz soru havuza hiç yazılmaz; şema geçerlilik oranı ölçülür
   (hedef: ≥ %98).

---

### User Story 7 — Mastery ve Eğitmen Analitiği (Priority: P3)

Öğrencinin konu bazlı performansı, cevap skorları ve kullanılan ipucu
kademeleriyle ağırlıklandırılmış bir puana (EWMA) dönüşür; öğrenci kendi
durumunu, eğitmen ise sınıfın tek sayfalık özetini görür.

**Why this priority**: Değerli ama diğer her şeye bağımlı; PLAN'da da en sona
(G9-G10) konumlanmış ve demo yolunda "basitleştirilebilir" listesindedir.

**Independent Test**: Bir öğrenciye birkaç soru çözdürülerek test edilir: konu
puanının EWMA kuralına göre güncellendiği, ipucu kullanımının puanı düşürdüğü
ve eğitmen ekranında sınıf özetinin göründüğü doğrulanır.

**Acceptance Scenarios**:

1. **Given** bir konuda önceki puanı olan öğrenci, **When** yeni bir cevap
   verirse, **Then** konu puanı `yeni = 0.7 × eski + 0.3 × son_cevap_skoru`
   kuralıyla güncellenir; kullanılan ipucu kademesi skoru çarpanla düşürür
   (0→1.00 · 1→0.85 · 2→0.70 · 3→0.50 · 4→0.25).
2. **Given** güncel konu puanları, **When** öğrenci kendi ekranını açarsa,
   **Then** konular üç seviyeyle görünür (<0.40 Geliştirilmeli · 0.40-0.74
   Orta · ≥0.75 İyi) ve puanın resmî not değil çalışma önerisi göstergesi
   olduğu ibaresi ekranda yer alır.
3. **Given** ders verisi birikmişken, **When** eğitmen analitik ekranını
   açarsa, **Then** tek sayfada konu bazlı sınıf ortalamasını, en çok yanlış
   yapılan soruları ve kapsam dışı ret istatistiğini görür.
4. **Given** eğitmen analitik ekranı, **When** başka bir dersin eğitmeni aynı
   ekrana erişmeye çalışırsa, **Then** yalnızca kendi derslerinin verisini
   görebilir.

---

### Edge Cases

- **Bozuk/taranmış PDF**: ayrıştırma başarısız olursa belge 3 denemeden sonra
  `failed` olur; eğitmen ham stack trace değil anlaşılır Türkçe mesaj görür.
- **Zip-bomb / dev dosya**: boyut sınırı (20 MB) ve worker'daki zaman/bellek
  sınırları işlemi keser; sistem diğer belgeleri işlemeye devam eder.
- **Belge içine gömülü talimat (indirect prompt injection)**: materyal metni
  veri olarak işaretlenir; "önceki talimatları unut" tarzı içerik cevabın
  davranışını değiştirmemelidir. Test seti ≥15 vakayla kalıp ailelerini kapsar;
  iddia "bilinen temel kalıplara karşı smoke-test edildi" düzeyinde tutulur.
- **Atıf temizliği sonrası boş cevap**: geçerli atıf kalmazsa cevap gösterilmez;
  öğrenci yetersiz kaynak mesajı alır (abstention, hata gibi sunulmaz).
- **Kanıt eşiğinin sınırındaki soru**: eşik kalibrasyon setiyle ayarlanır; eşik
  altındaysa cevap yerine nazik ret döner.
- **LLM sağlayıcı kesintisi**: birincil sağlayıcı düşerse otomatik yedeğe
  geçilir; ikisi de düşerse öğrenciye anlaşılır Türkçe hata mesajı gösterilir,
  yarım/kaynaksız cevap asla gösterilmez.
- **Sınav sırasında süre dolması**: o ana kadar verilen cevaplar puanlanır;
  cevaplanmamış sorular BOŞ sayılır ve puana katılmaz (yanlış sayılmaz). Bu
  kural sınav başlamadan arayüzde açıkça belirtilir ve T033'te testle sabitlenir.
- **Sınav sırasında bağlantı kopması**: oturum durumu sunucuda tutulduğu için
  öğrenci geri döndüğünde kalan süreyle devam edebilmelidir.
- **Aynı anda iki eğitmen aynı soruyu onaylar/reddederse**: son yazan kazanır;
  soru hiçbir aşamada aynı anda hem taslak hem onaylı görünmez.
- **Onaylı soru havuzu boşken sınav başlatma girişimi**: sınav başlatılamaz;
  öğrenciye durumu açıklayan mesaj gösterilir.
- **Öğrencinin URL/istek kurcalaması**: istemciden gelen ders kimliği asla
  yetki değildir; üyelik sunucu tarafında doğrulanır, yetkisiz istek reddedilir.

## Requirements *(mandatory)*

### Hoca Gereksinimi ↔ FR Eşlemesi

| Hocanın maddesi | Karşılayan FR'ler |
|---|---|
| Eğitmen: PDF/Markdown/kod yükleme | FR-004, FR-005, FR-006 |
| Yüklenenler dersin bilgi tabanı | FR-007, FR-008, FR-002 |
| Sokratik mod (cevap verme, ipucuyla çözdür) | FR-014, FR-015, FR-016 |
| Sınav Prova modu (süreli, puanlama, detaylı geri bildirim) | FR-017, FR-018, FR-019 |
| İçerikten soru + cevap anahtarı üretimi | FR-022, FR-023, FR-024 |
| Öğrenci: interaktif soru çözümü, eksik söylenir | FR-019, FR-020 |
| "Neden yanlış?" (çelişen slayt bölümü gösterilir) | FR-021 |
| Kod/senaryo inceleme (çıktı analizi, hata buldurma) | FR-025, FR-026 |
| Müfredat dışına nazik ret | FR-011 |
| Her yanıtta slayt/sayfa referansı zorunlu | FR-010, FR-012, FR-013, FR-016 |
| İnternet bilgisi karıştırılmaz | FR-009, FR-011 |
| Teslim: çalışır platform, örnek paket + rapor, kılavuzlar | FR-031, FR-032, FR-033 |

### Functional Requirements

**Hesaplar, Roller ve Ders İzolasyonu**

- **FR-001**: Sistem, eğitmen ve öğrenci rollerinde kullanıcı girişi sağlamalı;
  rol yetkileri sunucu tarafında zorlanmalıdır.
- **FR-002**: Ders verisi (materyal, sohbet, soru, sınav, performans) dersler
  arasında mutlak izole olmalıdır; izolasyon hem uygulama katmanında (sunucu
  tarafı üyelik doğrulaması) hem veritabanı katmanında (satır düzeyi güvenlik)
  zorlanmalıdır. İstemciden gelen ders kimliği asla yetki sayılmaz.
- **FR-003**: Eğitmen ders oluşturabilmeli, dersinin üyelerini görebilmeli ve
  üyelik iptal edebilmelidir. KARAR (MVP): öğrenci derse yalnızca eğitmenin
  e-posta ile eklemesiyle katılır — mevcut backend akışıyla birebir uyumludur ve
  yeni iş gerektirmez. Katılım koduyla self-enroll P1/v2 adayıdır ve bu spec'in
  kapsamı dışındadır.

**Materyal Yükleme ve Bilgi Tabanı (US1)**

- **FR-004**: Eğitmen; PDF, PPTX, Markdown, düz metin ve kod dosyalarını
  (`.pdf, .pptx, .md, .txt, .py, .java, .js, .ts, .c, .h, .cpp`) yükleyebilmelidir.
- **FR-005**: Sistem her yüklemeyi tür beyaz listesi + boyut sınırı (20 MB) +
  içerik imzası (magic byte) üçlüsüyle doğrulamalı; herhangi biri tutmayan
  dosyayı anlaşılır Türkçe mesajla reddetmelidir.
- **FR-006**: Yükleme sonrası işleme asenkron yürümeli; eğitmen belge başına
  durum (`uploaded / processing / completed / failed`) ve chunk bazlı ilerleme
  (n/m) görmelidir. Üç denemede işlenemeyen belge `failed` olur ve anlaşılır
  bir hata açıklaması taşır.
- **FR-007**: İşlenen içerik sayfa/slayt/bölüm metadata'sı korunarak
  parçalanmalıdır; bir parça iki sayfayı birleştirmez, kod dosyaları
  fonksiyon/sınıf sınırından bölünür. Bu metadata, cevaplardaki kaynak
  referanslarının tek kaynağıdır.
- **FR-008**: Aynı içeriğin tekrar yüklenmesi (içerik hash'i ile tespit)
  yeniden işleme/embed tetiklememelidir.

**Kaynaklı Soru-Cevap ve Guardrail Zinciri (US2)**

- **FR-009**: Öğrenci sorularına verilen cevaplar YALNIZCA o dersin işlenmiş
  materyallerinden üretilmelidir; sistem hiçbir cevaba internet veya genel model
  bilgisini kaynak olarak katmaz.
- **FR-010**: Gösterilen her akademik cevap, dayandığı iddialar için dosya adı +
  sayfa/slayt referansı taşımalıdır; referans, model metninden değil kaynak
  parçanın metadata'sından üretilir.
- **FR-011**: Materyalde yeterli kanıt bulunmayan sorular cevaplanmamalı;
  öğrenciye nazik, Türkçe bir mesaj dönmelidir. İki durum ayrışır: retrieval
  boş veya eşik altındaysa `insufficient_context`; retrieval sonuç verse bile
  soru müfredat dışı sınıflandıysa `out_of_scope`. Kanıt eşiği ayrı bir
  kalibrasyon setiyle ayarlanır; her iki ret de hata gibi değil olağan bir
  sonuç olarak sunulur.
- **FR-012**: Cevaptaki her atıf, o soru için gerçekten retrieval'dan gelmiş
  kaynak kümesine üyelik açısından mekanik olarak doğrulanmalıdır; küme dışı
  atıflar temizlenir, geçerli atıf kalmazsa cevap gösterilmez (fail-closed).
  Bu kontrol atıf uydurmayı engeller; iddia-kaynak tutarlılığı (faithfulness)
  ayrıca örneklem üzerinde ölçülür.
- **FR-013**: Sokratik ipuçları dahil kaynaksız hiçbir akademik içerik
  öğrenciye gösterilmemelidir.

**Sokratik Mod (US3)**

- **FR-014**: Sokratik modda sistem cevabı doğrudan vermemeli; kademeli bir
  akışla (tanı → yönlendirme → kavram ipucu → benzer örnek → kaynaklı açıklama)
  ilerlemeli ve öğrenci denemesi olmadan kademe atlamamalıdır. Kademe
  ilerleyişi sunucu tarafında tutulur ve her kademe kayıt altına alınır.
- **FR-015**: Sokratik ve sınav modlarında üretilen yanıtlar kod bloğu ve
  doğrudan-çözüm kalıpları açısından kural tabanlı denetlenmeli; ihlalde bir
  kez yeniden üretilmeli, ihlal sürerse deterministik şablon ipucuna
  düşülmelidir (fail-closed). Kalıp dışı sızıntı (pseudocode, sözel çözüm)
  mitigasyondur, garanti değildir; test setiyle ölçülür.
- **FR-016**: Her ipucu, retrieval'dan gelmiş bir kaynak parçasından
  türetilmeli, kaynak referansı taşımalı ve kanıt eşiği ile atıf
  doğrulamasından geçmelidir.

**Sınav Provası ve Değerlendirme (US4)**

- **FR-017**: Öğrenci süreli sınav provası başlatabilmelidir: çoktan seçmeli +
  açık uçlu sorular, ipucu kapalı, soru başına tek deneme, geri bildirim sınav
  sonunda. Mod politikaları (ipucu kapalılığı dahil) sunucu tarafında zorlanır.
  KARAR (MVP): sınav süresi ve soru sayısı config sabitlerinden gelir (tek yerde
  tanımlı varsayılan); eğitmenin sınav ayarı ekranı P1'dir. Practice modu ise
  süresizdir: ipucu açıktır, soru başına anında geri bildirim ve eksik noktalar
  gösterilir, tekrar deneme serbesttir; mastery güncellemesinde ilk cevap esas
  alınır.
- **FR-018**: Sınav bitiminde toplam puan ve soru bazında doğru/yanlış dökümü
  gösterilmelidir; çoktan seçmelide puanlama cevap anahtarına göre
  deterministiktir.
- **FR-019**: Açık uçlu cevaplar rubrik + cevap anahtarı + kaynak parçalar
  üzerinden şemalı olarak değerlendirilmeli; öğrenciye puan (0-100), eksik
  noktaların listesi ve dayanak kaynak referansı gösterilmelidir. Dayanak
  referansı da atıf doğrulamasından (set-membership) geçer.
- **FR-020**: Değerlendirme çıktısı şemaya uymazsa bir kez yeniden denenir;
  yine uymazsa öğrenciye uydurma bir sonuç gösterilmez, değerlendirmenin
  tamamlanamadığı anlaşılır bir mesajla bildirilir (fail-closed).
- **FR-021**: Yanlış cevaplanan her çoktan seçmeli soru için "neden yanlış?"
  analizi sunulmalıdır: seçilen çeldiricinin çeliştiği kaynak bölümü (dosya +
  sayfa/slayt) gösterilir (çeldirici→kaynak eşlemesi birincil, deterministik
  yol). Açık uçluda "neden yanlış?" karşılığı eksik noktalar + dayanak
  sayfasıdır.

**Soru Havuzu ve Eğitmen Onayı (US6)**

- **FR-022**: Sistem, ders materyalinden dört tipte (`mcq`, `open`,
  `code_trace`, `bug_hunt`) soru üretebilmelidir; her soru cevap anahtarı ve
  dayandığı kaynak parça referansıyla birlikte üretilir.
- **FR-023**: Üretilen sorular `draft` durumunda havuza düşer; eğitmen onayı
  (`approved`) olmadan hiçbir soru hiçbir öğrenci akışında görünmez. Eğitmen
  soruyu, cevap anahtarını ve kaynağını görerek onaylar veya reddeder.
- **FR-024**: Soru üretim çıktısı tanımlı şemaya karşı sunucu tarafında
  doğrulanmalıdır; şemaya uymayan çıktı havuza yazılmaz.

**Kod/Senaryo İnceleme (US5)**

- **FR-025**: Sistem `code_trace` (verilen kodun çıktısını tahmin et) ve
  `bug_hunt` (koddaki hatayı bul) soru tiplerini desteklemeli; değerlendirme
  cevap anahtarına karşı yapılmalıdır.
- **FR-026**: Sistem, öğrencinin veya sorunun kodunu hiçbir koşulda
  çalıştırmamalıdır.

**Mastery ve Analitik (US7)**

- **FR-027**: Öğrencinin konu bazlı performansı EWMA ile izlenmelidir
  (`yeni = 0.7 × eski + 0.3 × son_cevap_skoru`); kullanılan ipucu kademesi
  cevap skorunu çarpanla düşürür (0→1.00 · 1→0.85 · 2→0.70 · 3→0.50 · 4→0.25).
  Konular eğitmen tarafından tanımlanır.
- **FR-028**: Öğrenci ekranında konu puanları üç seviyeyle gösterilmeli
  (<0.40 Geliştirilmeli · 0.40-0.74 Orta · ≥0.75 İyi) ve puanın resmî not
  değil çalışma önerisi göstergesi olduğu ibaresi arayüzde yer almalıdır.
- **FR-029**: Eğitmen, dersi için tek sayfalık analitik özet görmelidir: konu
  bazlı sınıf ortalaması, en çok yanlış yapılan sorular, kapsam dışı ret
  istatistiği.

**Çapraz Kesen Gereksinimler**

- **FR-030**: Kullanıcıya dönen her metin (hata mesajları dahil) anlaşılır
  Türkçe olmalıdır; kullanıcıya asla ham stack trace gösterilmez.
- **FR-031**: Sistem, canlı bir URL üzerinden erişilebilir çalışır bir web
  platformu olarak teslim edilmelidir; lokal/çevrimdışı çalıştırma yolu da
  bulunmalıdır (demo sürekliliği için).
- **FR-032**: Teslim paketi, örnek bir ders materyal seti (İşletim Sistemleri)
  ve ölçülmüş metrikleri içeren bir başarı testi raporu içermelidir.
- **FR-033**: Teslim paketi, eğitmen ve öğrenci için ayrı kullanım kılavuzları
  içermelidir.
- **FR-034**: Demo senaryosu soruları için birebir eşleşmeli (exact-match) bir
  cevap önbelleği bulunmalıdır; önbellek yalnızca aynı sorunun aynı cevabını
  döndürür, benzerlik tabanlı eşleşme yapılmaz.
- **FR-035**: Kullanıcı başına istek sınırı ve girdi uzunluğu sınırı
  uygulanmalı; loglarda kişisel veri ve gizli anahtar redaksiyonu yapılmalıdır.

### Key Entities

- **Profile**: Kullanıcı kimliği ve rolü (`instructor` | `student`).
- **Course**: Ders; kod, başlık ve sahibi olan eğitmen. Tüm içerik izolasyon
  sınırıdır.
- **CourseMembership**: Kullanıcının bir dersteki üyeliği; rol ve durum
  (`active` | `revoked`).
- **Document**: Yüklenen materyal; dosya adı, türü, içerik hash'i ve işleme
  durumu (`uploaded / processing / completed / failed`).
- **Chunk**: Belgeden türetilen, sayfa/slayt/bölüm metadata'lı içerik parçası;
  kaynak referanslarının tek gerçeklik kaynağı. Ders kimliğini doğrudan taşır
  (izolasyon filtresi JOIN'e bağlı kalmaz).
- **IngestionJob**: Belge işleme işi; durum, deneme sayısı, son hata.
- **Topic**: Eğitmenin tanımladığı ders konusu; soru ve mastery bağlamı.
- **Question**: Havuzdaki soru; tip (`mcq / open / code_trace / bug_hunt`),
  içerik + cevap anahtarı, dayandığı kaynak parça, onay durumu
  (`draft / approved / rejected`).
- **ExamSession**: Öğrencinin sınav/çalışma oturumu; mod (`practice | exam`),
  başlangıç zamanı.
- **Answer**: Oturumdaki tek cevap; doğruluk ve yapılandırılmış geri bildirim
  (puan, eksik noktalar, dayanak parça).
- **Mastery**: Öğrenci × konu bazında EWMA puanı.
- **ChatSession / ChatMessage**: Soru-cevap ve Sokratik sohbet geçmişi; mod,
  kademe durumu ve atıflar.
- **AnswerCache**: Demo için exact-match soru→cevap önbelleği.

## Success Criteria *(mandatory)*

PLAN.md §5 kabul kriterlerinden alınmıştır. Eşikler kalibrasyon setiyle
ayarlanır, metrikler holdout sette raporlanır; ikisi asla karışmaz. Sonuçlara
şu not düşülür: *n=50, alt kümeler n≈10 — yön göstergesi, kesin hüküm değil.*
Çalıştırılmayan deney için sonuç yazılmaz.

### Measurable Outcomes

- **SC-001**: Dersler arası veri sızıntısı: **0** vaka. İzolasyonun gerçekten
  veritabanı katmanında tetiklendiği, politika bilerek bozulup testin kırmızıya
  düştüğü gösterilerek ayrıca kanıtlanır.
- **SC-002**: Kaynaksız gösterilen akademik cevap (Sokratik ipuçları dahil):
  **%0**.
- **SC-003**: Holdout sette Recall@5 ve Recall@8: **≥ %80** (@8 üretim
  değeri; @5 literatürle karşılaştırılabilirlik için).
- **SC-004**: Atıf hassasiyeti (doğru dosya + sayfa): **≥ %90**.
- **SC-005**: Kapsam dışı soruların doğru reddi: **≥ %90** (holdout üzerinde;
  eşik kalibrasyon setiyle ayarlı).
- **SC-006**: İddia-kaynak tutarlılığı (faithfulness): 20-30 cevaplık manuel
  örneklemde 2 bağımsız etiketleyiciyle ölçülür ve etiketleyici uyum oranıyla
  birlikte **raporlanır** (hedef eşik yerine ölçüm taahhüdü).
- **SC-007**: Sokratik modda kod/çözüm sızıntısı: test setinde **0** (set;
  fence'siz kod, pseudocode ve sözel çözüm vakalarını içerir).
- **SC-008**: Prompt injection testleri (≥15 vaka, kalıp aileleri): **geçer**;
  raporda "bilinen temel kalıplara karşı smoke-test edildi" olarak ifade
  edilir, "dayanıklı" denmez.
- **SC-009**: Soru üretiminde şema geçerliliği: **≥ %98**.
- **SC-010**: Uçtan uca cevap gecikmesi p95: **< 10 sn** (sıcak replika,
  sorgu yolu; soğuk başlangıç ayrıca ölçülüp raporlanır).
- **SC-011**: Demo akışında kritik hata: **0**.

## Assumptions

- Ders materyalleri TR/EN karışıktır ve teknik token'lar (`fork()`,
  `O(n log n)` gibi) içerir; arama ve dil seçimleri buna göre yapılır ve
  testle sabitlenir.
- Örnek ders paketi İşletim Sistemleri dersinden derlenir; gold test seti
  (≥50 soru) bu paket üzerinde kurulur ve materyal sahibi eğitmenin gözden
  geçirmesine sunulur.
- Mastery puanı resmî not değildir; insan (eğitmen) döngüde kalır ve arayüz
  bunu açıkça belirtir.
- Sınav süresi dolduğunda cevaplanmamış soruların boş sayılması varsayılmıştır
  (Edge Cases'teki açıklama bekleyen soruyla birlikte netleşecek).
- Kimlik doğrulama ve dosya depolama mevcut altyapı servisleriyle sağlanır;
  sıfırdan kimlik sistemi yazılmaz.
- Sohbet kayıtları için saklama süresi ve aydınlatma metni (KVKK) teslim
  paketinde yer alır.
- Demo günü için üç kademeli plan (canlı bulut / hotspot / tamamen çevrimdışı
  önbellekli kurulum) prova edilmiş olacaktır; çevrimdışı modun sınırları
  sunumda açıkça söylenir.

## Out of Scope (Bilinçli Kesilenler)

PLAN.md §2'deki karar tablosundan; geri alınmaları yazılı gerekçeyle plan
revizyonu gerektirir:

- **Dış kaynak RAG katmanı (IEEE vb. internet kaynakları)** — hocanın açık
  şartıyla çelişir ("internet bilgisi karışmaz"); v2'de ancak *eğitmen onaylı*
  paket olarak düşünülebilir.
- **Semantik önbellek** — yanlış önbellek eşleşmesi yanlış cevap demektir;
  yalnızca birebir eşleşmeli demo önbelleği vardır (FR-034).
- **Ayrı vektör veritabanı (Qdrant / FAISS / Chroma)** — ikinci veri deposu,
  senkronizasyon ve yetki sızıntısı riski getirir.
- **LLM orkestrasyon çatıları (LangChain / LlamaIndex / LangGraph)** — ince
  pipeline düz kodla daha şeffaftır.
- **Streamlit / Django+HTMX gibi alternatif arayüz yığınları**.
- **K8s, mikroservis, Kafka, Redis+Celery** — kapsam için gereksiz altyapı.
- **Fine-tuning, GraphRAG, multi-agent, OCR, mobil uygulama, sesli arayüz,
  kod çalıştırma sandbox'ı** — kapsamı şişirir, ana değeri doğrulamaz.
- **OpenAI File Search** — yalnızca dikey dilim kapısı geçilemezse acil durum
  yedeğidir; plana dahil değildir.

Kapsam dışı olmayıp yalnızca zaman kalırsa ve bayrak arkasında yapılacaklar
(P1): cross-encoder reranker, otomatik faithfulness (RAGAS), akış halinde
cevap (streaming), analitikte soru kümeleme.
