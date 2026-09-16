# Ürün ayrıntıları

DOU-Synapse'in tüm kullanıcı akışları, özellik envanteri, rol farkındalıklı ders ajanı
ve güvenlik/sınav bütünlüğü/KVKK ayrıntıları. Özet ve kanıt tablosu
[README](../README.md) içindedir; burası ayrıntının yeridir.

---

## Kullanıcı yolculukları

### Öğrenci yolculuğu

1. Öğrenci giriş yapar ve yalnız üyesi olduğu dersleri görür.
2. Dashboard’da ders rolü, materyal/soru durumu ve ölçülebilen ilerleme gösterilir.
3. **Ders Koçu** ile yalnız o dersin kaynaklarından soru sorar.
4. QA modunda kaynaklı açıklama; Sokratik modda kademeli ipucu alır.
5. Practice sınavında onaylanmış soruları çözer, “Neden yanlış?” ve rubric geri
   bildirimi görür.
6. Konu bazlı mastery ve çalışma önceliklerini izler.
7. Yararlı/sorunlu geri bildirimi bırakabilir; sohbet metnini öğretmenle paylaşmak
   ayrıca ve açıkça öğrencinin tercihidir.
8. Profil, sohbet silme, veri dışa aktarma ve anonimleştirme haklarını kullanabilir.

### Eğitmen yolculuğu

1. Eğitmen ders açar, katılımcıları öğrenci/eğitmen rolüyle yönetir.
2. Ders materyallerini yükler; parsing, embedding ve ingestion durumunu izler.
3. Chunk önizleme, kaynak bağlamı ve retrieval laboratuvarıyla RAG kalitesini inceler.
4. Dersin AI politikasını ayarlar: modlar, ipucu tavanı, kanıt eşiği, kaynak kapsamı
   ve bütçe.
5. Öğrenme çıktıları ve soru dağılımıyla tam bir sınav blueprint’i oluşturur.
6. AI’ın ürettiği taslak soruları düzenler, onaylar veya reddeder.
7. Sınıf analitiğini ve mahremiyetli AI kalite özetini görür.
8. **Eğitmen Asistanı** ile kaynaklı anlatım yaklaşımı, kavram yanılgısı ve soru taslağı
   fikri üretir; ajan hiçbir akademik kaydı otomatik değiştirmez.

### Bilgi İşlem / platform admin yolculuğu

1. Platform admin yetkisi ders eğitmenliğinden ayrı tutulur.
2. Salt okunur panelden servis, veritabanı, embedding ve ingestion sağlığını izler.
3. Maskeli kullanıcı dizini, ders metaverisi ve içeriksiz AI kullanım ölçümlerini görür.
4. İzin verilen ve reddedilen admin erişimleri request ID ile audit edilir.
5. Admin sıfatı öğrenci sohbetlerine, cevaplarına veya ders içeriğine erişim sağlamaz.
6. Kullanıcı/ders/not silme gibi geri alınamaz akademik işlemler bilinçli olarak panelde yoktur.

## Tüm ürün özellikleri

### 1. Ders, üyelik ve kimlik

- Ders oluşturma ve ders bazlı öğrenci/eğitmen üyeliği.
- Aynı kişinin farklı derslerde farklı role sahip olabilmesi.
- Supabase Auth köprüsü; JWT imza, audience, issuer, expiry ve subject doğrulaması.
- Production modunda demo kimliklerinin fail-closed reddi.
- Üye olunmayan ders için varlık bilgisi sızdırmayan 404 davranışı.
- Profil adı, üyelik özeti, parola sıfırlama ve hesap ekranları.

### 2. Materyal ve ingestion hattı

- PDF, PPTX, Markdown, düz metin ve yaygın kaynak kodu dosyaları.
- Uzantı, boyut, UTF-8, magic-byte ve path-traversal doğrulaması.
- Yerel disk veya Supabase Storage adaptörü.
- Ayrı worker sürecinde parsing, sayfa/slayt sınırını koruyan chunking ve embedding.
- CPU ağırlıklı parsing/embedding işlerinin event loop dışına alınması.
- İş durumu, retry zamanı, hata özeti ve güvenli silme.
- Her chunk için dosya, sayfa, slayt, bölüm ve kod satırı provenance bilgisi.
- Embedding sağlayıcı/sürüm damgası; korpus-sorgu uzayı uyuşmazlığında fail-closed.
- Metin katmanı olmayan PDF (tarama, el yazısı) görsel modelle transkribe edilir; eğitmenin
  "bu tarama, önce OCR'dan geçireyim" demesi beklenmez. Görsel okuma kapalıysa belge net bir
  mesajla ve **yeniden denenmeden** reddedilir — içerik hatası kalıcıdır.
- Görsel okumada üç koruma: transkripsiyon istemi harfi harfine aktarım ister ve tahmini
  yasaklar (`[okunamadı]`, çizimler transkribe edilmez); güven eşiğini geçemeyen sayfa
  atılır ve hiçbiri geçemezse belge reddedilir; her parça "AI okuması" köken etiketi taşır.

### 3. Hibrit RAG ve kaynak laboratuvarı

- PostgreSQL full-text search + pgvector dense retrieval.
- Reciprocal Rank Fusion ile hibrit aday birleştirme.
- Ders, kaynak seçimi ve RLS ile retrieval izolasyonu.
- Kanıt eşiği ve ayrı sonuç durumları:
  <code>answered</code>, <code>insufficient_context</code>,
  <code>out_of_scope</code>, <code>budget_exhausted</code>.
- Citation → leakage → sanitize guardrail zinciri.
- Modelin uydurduğu chunk kimliğini reddeden mekanik citation set kontrolü.
- Kaynak kartından pasajın önceki/sonraki chunk’larla özgün bağlamını açma.
- Eğitmen için dense/FTS/RRF adaylarını ve ret gerekçesini LLM çağırmadan gösteren
  retrieval laboratuvarı.

- Kavram haritası: dersin işlenmiş pasajlarından anahtar terimler, her terim için materyaldeki
  pasaj (birebir alıntı, dosya ve konum) ve terimlerin aynı pasajda birlikte geçme bağları.
  Model çağrılmaz; sıralama TF-IDF değil pasaj sayısıdır (merkezî kavram çoğu pasajda geçer);
  Türkçe ekler gövdeleyici olmadan önek kuralıyla birleştirilir ve sınır ekranda yazılıdır.
  Aktif sınavda kilitli; Markdown olarak indirilebilir.

### 4. Kaynaklı sohbet ve Sokratik çalışma

- Çok turlu oturumlar ve mesaj geçmişi.
- QA ve Sokratik modlar.
- Deneme olmadan ilerlemeyen ipucu merdiveni.
- “Sadece cevabı söyle” ısrarında fail-closed davranış.
- Kod sızıntısı, geçersiz citation ve kapsam dışı içerik kontrolleri.
- Frontend request timeout’u, GET/HEAD-only retry, jitter/backoff ve görünür request ID.
- Eski oturumlarda rol/persona uyuşmazlığını sessizce taşımayan oturum kontrolü.

### 5. Soru laboratuvarı

- Çoktan seçmeli, klasik/açık uçlu, kısa cevap, kod izleme ve hata bulma aileleri.
- Konu, öğrenme çıktısı, zorluk, örnek soru ve adet ile üretim.
- Cevap anahtarı, rubric ve kaynak referansı.
- Her üretimin önce taslak havuzuna düşmesi.
- Eğitmen onayı olmadan öğrenciye görünmeme.
- Onay, red, düzenleme ve güvenli silme uçları.
- İstenen/dönen/kabul edilen sayı ile elenme gerekçelerinin görünür tutulması.

### 6. Sınav blueprint’i ve değerlendirme

- Öğrenme çıktıları ve konu dağılımı.
- Kolay/orta/zor oranları ve soru türü dağılımı.
- Puan, süre, yayın/kapanış penceresi ve yeniden deneme politikası.
- Readiness doğrulaması ve publish kapısı.
- Yayınlanmış blueprint’in sürümlenmesi ve sınav oturumuna immutable snapshot alınması.
- Sunucu zamanına bağlı practice/exam oturumları.
- Çoktan seçmeli, açık uçlu ve kod sorularına uygun değerlendirme.
- Rubric kırılımı ve “Neden yanlış?” kaynak açıklaması.
- Değerlendirilemeyen cevapta puan uydurmayan fail-closed davranış.

- Hızlı tekrar: bitmiş alıştırmanın soruları kart destesi olur — ön yüz soru ve şıklar, arka yüz
  sunucunun sonucu, "neden yanlış" kaynak kartı ve çözüm. Yanlışlar başa sıralanır; kaydırma,
  klavye (←/→/Enter/Boşluk) ve düğmeler aynı kararı verir. Kararlar oturumda kalır, puana ve
  mastery'ye girmez; deste sonunda "biliyordum dediğin ama yanlış yaptığın" kartlar ayrı listelenir.
  Cevap anahtarı yalnız bitmiş oturumdan gelir — onaylı havuz öğrenciye anahtar vermez.

### 7. İlerleme, analitik ve AI kalite döngüsü

- Öğrenci için konu bazlı mastery, çalışma önceliği ve yanıt sayısı.
- Çalışılmamış konuyu “0 başarı” gibi göstermeyen ölçüm dili.
- Eğitmen için sınıf konu performansı, yanlış oranı ve zorlanılan sorular.
- Kapsam dışı/yetersiz bağlam sinyallerinin ayrı raporlanması.
- “Resmî not değildir” sınırının UI’da korunması.
- AI yanıtına yararlı/sorunlu geri bildirimi ve kategori seçimi.
- Yalnız öğrencinin açıkça paylaştığı metinlerin eğitmen inceleme kuyruğuna girmesi.
- Kullanıcılar/dersler arasında RLS ile geri bildirim izolasyonu.

### 8. Profil, hesap ve KVKK

- Profil adını güncelleme ve ders üyeliklerini görüntüleme.
- Sohbet geçmişini silme.
- Kişisel veriyi JSON olarak dışa aktarma.
- Dışa aktarmada ham kota/guard satırları veya iç kimlikler yerine, içeriksiz operasyon
  kayıtlarının neden pakete alınmadığını açıklayan geriye uyumlu <code>not_included</code> alanı.
- Hesabı anonimleştirme.
- Ders ve profil silme yollarında reservation/guard kayıtlarının PostgreSQL cascade ile
  kalıntı bırakmadığını doğrulayan gerçek veritabanı testi.
- Aktif sınav sırasında eski kaynaklı cevapların KVKK dışa aktarımı üzerinden
  alınmasını da engelleyen sınav kilidi.
- Giriş öncesi erişilebilen KVKK aydınlatma sayfası.

Otomatik saklama/retention işi henüz canlı bir operatör politikasıyla kanıtlanmadı;
bu, production öncesi açık işletim sorumluluğudur.

### 9. Bilgi İşlem admin paneli

- Uygulama, veritabanı, pgvector, ortak istek kotası ve embedding hazırlık özeti; eksik alan “Ölçülemedi” gösterilir.
- Toplam kullanıcı, aktif üyelik, ders ve belge metrikleri.
- Kullanıcı arama ve maskeli e-posta.
- Ders metaverisi ve rol dağılımı.
- İçeriksiz AI kullanım/latency/token özetleri.
- Ingestion işlerinin durum ve retry görünümü.
- Admin erişim audit’i.
- Self-promotion, doğrudan tablo erişimi ve yetkisiz SECURITY DEFINER çağrılarına
  karşı kapalı yetki modeli.
- Akademik içerik, ham prompt/cevap, dosya adı, stack trace ve özel sohbet göstermeyen
  privacy-first operasyon yüzeyi.

### 10. Ürün arayüzü

Mevcut feature dalındaki ürün arayüzü:

- Next.js 16 + React 19 + TypeScript ile gerçek çok sayfalı web uygulaması.
- Rol farkındalıklı dashboard, ders alanı, profil ve admin portalı.
- Mobil 375px, masaüstü, açık/koyu tema ve klavye erişimi.
- Tema **uygulama içinden** seçilir (Sistem / Açık / Koyu): rayda, profilde ve
  giriş ekranında; API belge sayfasının kendi seçicisi var. Seçim ilk boyamadan
  önce uygulanır, açılışta beyaz çakma olmaz.
- Yükleniyor, boş, hata ve kilit durumları için ortak bileşenler.
- Tasarım token’larıyla yönetilen tutarlı arayüz.
- Son yerel tasarım çalışmasında tek kırmızı aksanlı, daha editoryal ve insan eliyle
  hazırlanmış “akademik stüdyo” dili.
- Dashboard’da “öneri” uydurmak yerine dürüstçe **En yeni ders alanı**.
- Ders sayfasında sunucuda olmayan öncelik iddiası yerine **Bu derste çalışma yolları**.
- AI üretimi hissi veren rastgele gradient, dekoratif metrik kartı ve sahte durum verisi yok.

> Aşağıdaki tarihsel ekranlar güncel ürün adayının görünümünü temsil etmez; yeni ekran
> görüntüleri ancak bu dal review edilip main’e alındıktan sonra üretilecektir.

## Rol farkındalıklı ders ajanı

CourseGPT’deki yeni ajan, genel amaçlı veya otonom bir ajan değildir. Mevcut kaynaklı
ders sohbetinin, seçili dersteki üyelik rolüne göre güvenli şekilde özelleşen halidir.

| Sunucunun türettiği profil | Kullanıcı | Yapabildikleri | Yapamadıkları |
|---|---|---|---|
| **Ders Koçu** | Öğrenci | Kaynaklı QA, Sokratik çalışma, citation ve çalışma önerisi | Aktif sınavda yardım, doğrudan cevap sızdırma, ders dışı işlem |
| **Eğitmen Asistanı** | Eğitmen | Kaynaklı anlatım yaklaşımı, kavram yanılgısı, soru/yönlendirme taslağı | Soru yayınlama, not/üyelik/politika değiştirme, öğrenci sohbeti okuma |

### Ajanın güvenlik ve maliyet sınırları

- Persona istemciden kabul edilmez; üyelik rolünden sunucuda türetilir.
- Oturum audience değeri immutable’dır; rol değişirse eski persona ile devam edilemez.
- Öğrenci ve eğitmen cache kayıtları birbirine geçmez.
- Kaynak/politika revizyonu cache anahtarına dahildir.
- Global kill switch doğrudan API’yi kapatır.
- Girdi ve çıktı uzunluğu sunucuda sınırlandırılır.
- Sağlayıcı deneme sayısı ve toplam zaman bütçesi kontrollüdür.
- Kullanıcı, ders ve platform için kalıcı/atomik günlük token tavanları vardır.
- Eşzamanlı istek rezervasyonu ve lease mekanizması bulunur.
- <code>429</code> yanıtı <code>Retry-After</code> taşır.
- Kapsam dışı, yetersiz kaynaklı veya bütçesi bitmiş istek LLM’e gitmeden reddedilebilir.
- İçeriksiz guard ledger; prompt, cevap, e-posta, IP, JWT veya belge metni saklamaz.
- Aktif sınav başlaması, chat finalizasyonu ve veri dışa aktarımı ortak kullanıcı kilidiyle
  yarış koşullarına karşı sıralanır.

### Ajanın bilinçli sınırları

- Web araması yapmaz.
- Kod çalıştırmaz.
- E-posta veya bildirim göndermez.
- Belge, soru, sınav, not, üyelik veya politika değiştirmez.
- Başka derse veya başka kullanıcının özel verisine erişmez.
- Platform admin yetkisi kazanmaz.
- Tekil demo koşuları pedagojik kalite kanıtı sayılmaz; geniş örneklemli insan
  değerlendirmesinin yerini tutmaz.

## Güvenlik, sınav bütünlüğü ve KVKK

### İki katmanlı yetkilendirme

1. **API katmanı:** Her istek course membership ve rol bağımlılıklarından geçer.
2. **Veritabanı katmanı:** PostgreSQL Row-Level Security, uygulama hatası olsa bile
   satırları ders/kullanıcı sınırında tutar.

RLS politikaları yalnız “yeşil test” ile bırakılmaz. Mutasyon betikleri politikayı veya
grant’i bilinçli zayıflatır; izolasyon testi kırmızıya dönmezse kanıt başarısız sayılır.

### Sınav bütünlüğü

- Aktif exam oturumunda sohbet, oturum listesi, mesajlar ve kaynak bağlamı API’de kapanır.
- UI gizlemek yeterli kabul edilmez; doğrudan API ve ikinci sekme yolları test kapsamındadır.
- Süresi dolmuş veya practice oturumu öğrenciyi kalıcı kilitlemez.
- Eğitmen kendi yapılandırmasını test edebilir.
- Chat sınavdan önce başlayıp sağlayıcıdan sonra dönerse final persist öncesi durum yeniden
  ve atomik kilitle kontrol edilir.
- Aktif sınavda eski cevapları hesap dışa aktarımından alma yolu da kapanır.

### Mahremiyet

- Eğitmen yalnız kendi dersinin agregalarını görür.
- Öğretmen öğrencinin özel sohbet metnini varsayılan olarak okuyamaz.
- Sohbet oturumu yalnız sahibine açılır: liste sorgusu ve iki yükleme yolu da
  <code>user_id</code> eşleşmesi arar, aynı derste kayıtlı başka bir öğrenci oturum
  kimliğini bilse bile geçmişi okuyamaz.
- Öğrenciye dönen soru kaynakları yalnız dosya adı, konum ve chunk kimliğidir; ham pasaj
  metni eğitmen yüzeyinde kalır, böylece soru kartı cevabı ele vermez.
- AI kalite incelemesinde metin paylaşımı öğrenci onayına bağlıdır.
- Platform admin akademik içeriğe admin sıfatıyla erişemez.
- Teknik kayıtlar request ID, durum ve süre gibi metadata taşır; genel anonimlik
  garantisi yoktur. Hata kayıtları sınırlı nesne/sabit olay özetleri kullanır.
  Destek kodunu sunucu üretir; istemci değeri kullanılmaz. Dış günlük ve saklama
  sınırları [günlük sözleşmesinde](operations/logging-privacy.md) açıklanır.
- KVKK dışa aktarma, sohbet silme ve anonimleştirme akışları vardır.

### Web ve dosya güvenliği

- CSP ve güvenlik başlıkları.
- Tek ve içerik sızdırmayan hata zarfı: <code>code</code>, <code>message</code>,
  <code>request_id</code>.
- Dosya türü/imza/boyut/UTF-8 kontrolleri.
- Path traversal ve uygunsuz dosya adı savunması.
- Production’da demo auth reddi.
- JWT için audience ve issuer doğrulaması.
- E2E koşu kimliği, dar kapsamlı teardown ve korunan demo dersi.
