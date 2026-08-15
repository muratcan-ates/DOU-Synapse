<div align="center">

# DOU-Synapse

### CourseGPT — Yapay Zekâ Destekli Kişiselleştirilmiş Ders ve Sınav Platformu

**Doğuş Üniversitesi · COME 492 Bitirme Projesi · 2026**

Danışman: Yasemin Karagül<br>
Takım: Muratcan Ateş · Eren Onur · Metehan Alphan

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16_+_pgvector-4169E1?logo=postgresql&logoColor=white)
![Backend tests](https://img.shields.io/badge/backend_tests-894_ge%C3%A7ti-brightgreen) <!-- docs-check: backend.tests = 894 -->
![Frontend tests](https://img.shields.io/badge/frontend_tests-349_ge%C3%A7ti-brightgreen) <!-- docs-check: frontend.tests = 349 -->
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

**Ders materyalini güvenilir öğrenme döngüsüne dönüştüren; öğrenci, eğitmen ve Bilgi İşlem
rollerini aynı güvenli platformda buluşturan LLM + RAG ürünü.**

</div>

---

## Güncel durum — hangi parça nerede?

Bu README yalnız özellikleri değil, **kanıt seviyesini** de gösterir. “Kodlandı”,
“yerelde doğrulandı”, “main’e birleşti” ve “production’da çalışıyor” aynı şey değildir.

| Katman | Durum | Açıklama |
|---|---|---|
| **Birleşmiş temel ürün** | <code>origin/main · 2c17886</code> | Production-hardening ve ürün portalı PR #4 ile main’e birleşti |
| **AI-SDLC ve engineering excellence** | <code>004-ai-sdlc-excellence · 7c1c219</code> | Uzak feature dalında; main’e henüz birleşmedi |
| **Rol farkındalıklı ders ajanı** | <code>005-role-aware-course-agent · fc5bd59</code> | Uzak feature dalında; main’e henüz birleşmedi |
| **Güncel ürün adayı** | <code>design/product-ui-refresh</code> | 005 üzerinde UI, KVKK ve append-only R3 kanıt revizyonu; doğrulandı ve feature dalında, main’e henüz birleşmedi |
| **Canlı production** | **Kanıtlanmadı** | Staging URL, canlı Supabase, gerçek LLM değerlendirmesi, canary ve rollback kanıtı açık |

### Kanıt etiketleri

- **Kodlandı:** Gerçek API, UI, migration veya otomatik kontrol mevcut.
- **Yerelde doğrulandı:** İzole test veritabanı, fake provider ve/veya yerel build ile kanıtlandı.
- **CI’da gözlendi:** İlgili commit için GitHub Actions sonucu görüldü.
- **Dış doğrulama bekliyor:** Gerçek Supabase, gerçek Groq/Gemini, staging, telemetry,
  yük, backup/restore veya production ortamı gerekiyor.

> Bugünkü ürün güçlü bir **repository candidate**’dır; “production’a deploy edildi”
> veya “gerçek model kalitesi kanıtlandı” iddiasında bulunmaz.

## İçindekiler

- [Ürün fikri](#ürün-fikri)
- [Hocanın gereksinimleri nasıl karşılandı?](#hocanın-gereksinimleri-nasıl-karşılandı)
- [Kullanıcı yolculukları](#kullanıcı-yolculukları)
- [Tüm ürün özellikleri](#tüm-ürün-özellikleri)
- [Rol farkındalıklı ders ajanı](#rol-farkındalıklı-ders-ajanı)
- [Güvenlik, sınav bütünlüğü ve KVKK](#güvenlik-sınav-bütünlüğü-ve-kvkk)
- [Mimari ve teknoloji yığını](#mimari-ve-teknoloji-yığını)
- [CI/CD, AI-SDLC ve engineering excellence](#cicd-ai-sdlc-ve-engineering-excellence)
- [Ölçülmüş kanıt](#ölçülmüş-kanıt)
- [Gelişim yolculuğu](#gelişim-yolculuğu)
- [Ekran görüntüleri](#ekran-görüntüleri)
- [Production’a giden açık yol](#productiona-giden-açık-yol)
- [Yerel kurulum](#yerel-kurulum)
- [Depo haritası ve belgeler](#depo-haritası-ve-belgeler)

## Ürün fikri

Öğrencilerin genel amaçlı bir sohbet botuna değil, **dersin öğretim elemanı tarafından
sınırlandırılmış bir çalışma ortamına** ihtiyacı var. CourseGPT bu nedenle yalnız
eğitmenin yüklediği PDF, PPTX, Markdown, metin ve kod dosyalarını bilgi kaynağı kabul eder.

Çekirdek ilke basittir:

> **Kaynak yoksa cevap yoktur.**

Sistem bir yanıtı yalnız üretmez; cevabın hangi dosya, sayfa, slayt, başlık veya kod
satırına dayandığını gösterir. Kanıt yetersizse bunu dürüstçe söyler. Sokratik modda
doğru cevabı doğrudan vermek yerine öğrencinin denemesini bekler ve kademeli ipucu verir.

CourseGPT zaman içinde basit bir RAG sohbet ekranından şunları içeren tam bir web ürününe
dönüştü:

- rol bazlı öğrenci, eğitmen ve Bilgi İşlem portalları;
- kaynak yönetimi ve retrieval laboratuvarı;
- soru üretimi, öğretmen onayı ve sürümlü sınav blueprint’i;
- süreli practice/exam akışı, değerlendirme ve “Neden yanlış?”;
- öğrenci ilerlemesi, sınıf analitiği ve AI kalite geri bildirimi;
- platform yönetimi, içeriksiz teknik loglar ve audit;
- sınav kilidi, RLS, KVKK hakları, atomik AI kotaları ve acil kapatma anahtarı;
- CI, güvenlik kontrolleri, AI değişiklik dosyaları ve kanıt temelli release tasarımı.

## Hocanın gereksinimleri nasıl karşılandı?

| Danışman gereksinimi | Uygulamadaki karşılığı | Kanıt sınırı |
|---|---|---|
| PDF, Markdown ve kod yükleme | PDF, PPTX, MD, TXT ve yaygın kod türleri; doğrulama, parçalama, provenance, worker | Kodlandı ve testli |
| Yalnız öğretmenin kaynakları | Ders üyeliği + PostgreSQL RLS + seçili kaynak politikası | Yerel RLS ve mutasyon kanıtı |
| Sokratik mod | Deneme bekleyen, kademeli ve kaynaklı ipucu merdiveni | Deterministik mekanik kanıt; gerçek pedagojik ölçüm açık |
| Sınav prova modu | Sunucu süreli practice/exam oturumları, puanlama ve geri bildirim | Kodlandı; önceki E2E kanıtı var |
| AI soru üretimi | Dört soru ailesi, öğrenme çıktısı, zorluk, cevap anahtarı ve kaynak | Fake provider mekanik akışı kanıtlıyor; gerçek model kabul oranı açık |
| Öğretmen onayı | Taslak → onay/red → öğrenciye yayın akışı; RLS yalnız onaylı soruları açar | API, DB ve testlerle zorunlu |
| “Neden yanlış?” | Yanlış şık/cevap ile çelişen kaynak ve rubric kırılımı | Kodlandı |
| Kod/senaryo inceleme | <code>code_trace</code> ve <code>bug_hunt</code>; statik değerlendirme | Kod hiçbir zaman çalıştırılmaz |
| Kapsam dışı ret | <code>out_of_scope</code> ve <code>insufficient_context</code> ayrı sinyaller | LLM öncesi ret yolu mevcut |
| Kaynak gösterme | Retrieved metadata’dan mekanik citation doğrulaması | Kodlandı; gerçek-model faithfulness örneklemi açık |
| Web platformu | Next.js öğrenci/eğitmen/admin portalı + FastAPI + PostgreSQL | Yerelde build/test kanıtı |
| Test raporu ve kılavuz | Speckit, docs-check, öğrenci/eğitmen kılavuzları, test/eval belgeleri | Depoda mevcut |

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

- Uygulama, veritabanı ve embedding readiness özeti.
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
- Fake provider sonucu gerçek pedagojik kalite kanıtı sayılmaz.

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
- AI kalite incelemesinde metin paylaşımı öğrenci onayına bağlıdır.
- Platform admin akademik içeriğe admin sıfatıyla erişemez.
- Teknik loglar içeriksizdir; request ID, durum, latency ve aggregate token gibi alanları
  taşır.
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

## Mimari ve teknoloji yığını

~~~mermaid
flowchart LR
    U["Öğrenci / Eğitmen / Bilgi İşlem"] --> WEB["Next.js 16 + React 19"]
    WEB --> API["FastAPI · Python 3.12"]
    API --> AUTH["Supabase Auth / JWT"]
    API --> DB[("PostgreSQL 16 + pgvector<br/>RLS + FTS + audit")]
    API --> ST["Supabase Storage veya yerel storage"]
    API --> Q["Ingestion job"]
    Q --> W["Ayrı worker<br/>parse + chunk + embed"]
    W --> ST
    W --> DB
    API --> R["Hybrid retrieval<br/>dense + FTS + RRF"]
    DB --> R
    R --> S{"Kanıt / kapsam / bütçe"}
    S -->|"uygun"| L["LiteLLM<br/>Groq → Gemini"]
    S -->|"yetersiz"| X["Dürüst ret<br/>LLM çağrısı yok"]
    L --> G["Citation + leakage + sanitize guardrails"]
    G --> C["Kaynaklı cevap / Sokratik ipucu"]
    C --> T["İçeriksiz kullanım ve kalite sinyali"]
    T --> DB
~~~

| Katman | Teknoloji | Neden |
|---|---|---|
| Web | Next.js 16, React 19, TypeScript 5, Tailwind 4, Bun | Tam web ürünü, rol bazlı routing, responsive UI |
| API | FastAPI, Pydantic, SQLAlchemy 2, Python 3.12 | Açık sözleşme, async API, güçlü tip/doğrulama |
| Veritabanı | PostgreSQL 16 + pgvector | İlişkisel veri, FTS, vektör, RLS ve audit tek yerde |
| AI | LiteLLM, Groq, Gemini | Sağlayıcı adaptörü, timeout ve sınırlı fallback |
| Embedding | FastEmbed multilingual-e5-large veya deterministik hashing | Anlamsal production yolu ve hızlı test yolu |
| Storage | Supabase Storage veya yerel adaptör | Yerel geliştirme ile cloud depolamayı ayırma |
| Test | Pytest, Bun test, Playwright, SQL/RLS mutasyon betikleri | Birim, sözleşme, tarayıcı ve yetki kanıtı |
| Delivery | GitHub Actions, Docker, Speckit, AI dossier | Ölçülebilir ve izlenebilir değişiklik akışı |

### Neden LangChain/LlamaIndex/LangGraph yok?

Retrieval → LLM → guardrail hattı, Sokratik durum makinesi, citation kontrolü ve sınav
kuralları bu ürün için düz Python’la yazıldı. Amaç çerçeve sayısını artırmak değil;
yetki, citation ve maliyet kararlarını kodda görünür ve test edilebilir tutmak.
Rol farkındalıklı ajan da otonom bir graph değil, araç-yetkisiz course-scoped bir
yardımcıdır.

## CI/CD, AI-SDLC ve engineering excellence

### Çekirdek CI

Depoda tanımlı CI işleri:

- **API:** Ruff, format, mypy, Pytest, migration ve RLS/mutasyon kontrolleri.
- **API imajı:** Docker build, gömülü embedding, ağsız çalışma ve RSS sınırı.
- **Web:** tip kontrolü, birim testleri, kontrast kapısı ve production build.
- **Belgeler:** canlı test/migration/tablo/ekran sayılarının kaynak koddan doğrulanması.
- **Uçtan uca:** gerçek API + worker + tarayıcı akışı ve run-scoped cleanup.
- **Security:** dependency review, CodeQL ve workflow dependency politikası.
- **AI quality:** AI-sensitive diff ve değişiklik dossier doğrulaması.

PR #4’ün birleşmiş baseline’ında çekirdek beş işin yeşil sonucu gözlendi. 004/005
özelliklerinin kendi PR/required-check gözlemi ise açık olduğundan README bunları main’de
veya enforced olarak sunmaz.

### CD ve release candidate

Depoda bir **release-candidate admission tasarımı** vardır:

- tag event’i current main’in exact SHA’sına bağlanır;
- imaj önce quarantine kimliğiyle üretilir;
- exact digest ağsız embedding, bake ve RSS kontrollerinden geçer;
- SBOM, provenance/attestation ve kanıt zarfı hazırlanır;
- candidate ile promotion kanıtı birbirinden ayrılır.

Ancak staging/production deploy workflow’u, canlı cloud credential’ları, protected
environment onayı ve gerçek promotion gözlemi yoktur. Dolayısıyla:

> **CI var ve güçlüdür; production CD henüz kanıtlanmış değildir.**

### AI-SDLC

Prompt, provider/model, embedding, retrieval, guardrail, evaluator veya AI özelliği
değiştiğinde:

1. değişen AI-sensitive dosyalar belirlenir;
2. artifact hash ve lineage kaydı tutulur;
3. risk R1–R3 olarak sınıflanır;
4. kanıt türü fake-provider / real-provider / staging / production olarak etiketlenir;
5. gerekli engineering, domain ve security/privacy onayları ayrılır;
6. feature flag, kill switch, canary ve rollback planı yazılır;
7. önceki immutable kayıt değiştirilmez; yeni revision eklenir.

Offline validator mekanik sözleşmeyi kanıtlar; gerçek model çağrısını, insan pedagojik
değerlendirmesini veya production telemetry’sini taklit etmez.

### Engineering excellence

- CODEOWNERS ve PR kanıt şablonu.
- Dependabot ve kilit dosyası disiplini.
- Immutable action SHA politikası.
- ADR kayıtları ve build-once/promote-by-digest kararı.
- SLO/error-budget sözleşmesi.
- Incident response ve rollback runbook’u.
- Kaynak koddan ölçülen <code>docs_check</code>.
- Generated OpenAPI sözleşmesi.
- İçeriksiz teknik telemetry ve request ID.
- Background embedding warmup ve live/ready health ayrımı.
- Güvenli pagination, ingestion retry ve event-loop koruması.

Bu yönetim katmanı 004 feature dalında yapılandırılmıştır; GitHub ruleset, protected
environment, gerçek release ve production gözlemi olmadan “enforced” denmez.

## Ölçülmüş kanıt

| Ölçüm | Güncel kaynak değeri | Ne kanıtlar / neyi kanıtlamaz |
|---|---:|---|
| Backend testleri | **894** <!-- docs-check: backend.tests = 894 --> | Repo sözleşmeleri ve deterministik mekanik davranış; gerçek LLM kalitesi değil |
| Frontend birim testleri | **349** <!-- docs-check: frontend.tests = 349 --> | 30 test dosyasındaki UI yardımcıları/sözleşmeleri; tek başına pedagojik kalite kanıtı değil <!-- docs-check: frontend.testFiles = 30 --> |
| Playwright gerçek-API vakaları | **36** <!-- docs-check: e2e.tests = 36 --> | Benzersiz PostgreSQL, fake LLM ve tek worker ile 36/36; gerçek provider/staging kanıtı değil |
| Migration | **15** <!-- docs-check: migrations.count = 15 --> | Şema evriminin kaynak dosyası sayısı |
| CREATE TABLE | **27** <!-- docs-check: tables.count = 27 --> | Migration’larda kurulan benzersiz tablo sayısı |
| Web ekranı | **20** <!-- docs-check: screens.count = 20 --> | Next.js <code>page.tsx</code> sayısı |
| Örnek teslim dosyası | **22** <!-- docs-check: sampleData.files = 22 --> | İşletim Sistemleri örnek materyal paketi |

005'in 11 Ağustos 2026 tarihli yerel kanıt koşusu ayrıca şunları kaydeder:

- 92 backend dosyasında mypy sonucu; <!-- docs-check: tarihsel 92 · 2026-08-11 -->
- frontend typecheck, açık/koyu tema kontrast kapısı ve production build;
- Ruff;
- 50 OpenAPI yolu ve 119 şema; <!-- docs-check: tarihsel 50 · 2026-08-11 --><!-- docs-check: tarihsel 119 · 2026-08-11 -->
- persona alanlarının istemciden gönderilmesinin reddi;
- cross-course quota yarışları, cache izolasyonu ve exam/export yarış korumaları;
- gerçek API’ye karşı 35/35 seri tarayıcı akışı, teardown sonrası ders/audit kalıntısı <!-- docs-check: tarihsel 35 · 2026-08-11 -->
  <code>0/0</code> ve sabit UUID’li <code>COME 331</code> koruma kanıtı; <!-- docs-check: tarihsel 0 · 2026-08-11 -->
- 8 kapalı sınır, 3 kalıcı kota iddiası ve 11/11 kasıtlı DB/RLS mutasyonunun <!-- docs-check: tarihsel 8 · 2026-08-11 --><!-- docs-check: tarihsel 3 · 2026-08-11 --><!-- docs-check: tarihsel 11 · 2026-08-11 -->
  beklenen sızıntıyı görünür kılması.

Bu kanıt **yerel PostgreSQL + deterministik fake provider** ortamındadır. Gerçek provider,
staging, canary veya production kanıtı değildir.

15 Ağustos entegrasyon adayı ayrıca 894/894 backend, 349/349 frontend (30 test
dosyası), 36/36 seri gerçek-API Playwright, 12/12 uygulama mutasyonu ve 7/7
offline/fake RAG mekanik vakasını geçti. İki-worker yerel yükte kota overshoot 0,
aktif reservation tepesi 1, cache-miss p95 1659.16 ms ve cache-hit p95 493.73 ms
ölçüldü. Bunlar final R4 evidence kaydına bağlanmadan ve gerçek provider/staging
kapıları koşulmadan production kanıtı değildir.

### Migration yolculuğu

<code>0001,0002,0003,0004,0005,0006,0007,0008,0009,0010,0011,0012,0013,0014,0015</code> <!-- docs-check: migrations.list = 0001,0002,0003,0004,0005,0006,0007,0008,0009,0010,0011,0012,0013,0014,0015 -->

| Migration | Ürüne eklediği katman |
|---|---|
| 0001 | Çekirdek ders, üyelik, belge/chunk, RLS ve request-scoped kullanıcı |
| 0002 | Supabase Auth köprüsü |
| 0003 | Sohbet oturumları, mesajlar, cache ve request log |
| 0004 | Konu, soru, sınav, cevap ve mastery |
| 0005 | Mahremiyetli analitik |
| 0006 | Embedding provenance |
| 0007 | Dar soru silme ve sınav grant’leri |
| 0008 | Sürümlü sınav blueprint’i |
| 0009 | Ders bazlı AI politikası |
| 0010 | Ingestion retry zamanlaması |
| 0011 | Pagination indeksleri |
| 0012 | KVKK/veri hakları |
| 0013 | AI sohbet geri bildirimi ve paylaşım onayı |
| 0014 | Platform-admin konsolu ve audit |
| 0015 | Rol farkındalıklı ajan, audience izolasyonu ve atomik AI kotaları |

## Gelişim yolculuğu

### 1. 2 Ağustos — fikir depoya dönüştü

İlk commit proje iskeletini ve MIT lisansını kurdu. Henüz “ürün” iddiası yoktu; amaç
hocanın CourseGPT taslağını izlenebilir bir mühendislik çalışmasına çevirmekti.

### 2. 4 Ağustos — mimari ve güvenli çekirdek

Üç haftalık plan, mimari kararlar, FastAPI, PostgreSQL/pgvector, ilk CI ve ders bazlı
iki katmanlı izolasyon geldi. <code>0001</code>, request-scoped kullanıcı bağlamı,
uygulama rolleri ve fail-closed RLS’in temelini attı.

**Öğrenilen:** Yetki yalnız frontend sekmesi veya API if’i olamaz; veritabanı ikinci
savunma katmanı olmalıdır.

### 3. 4–5 Ağustos — materyal aranabilir öğrenme tabanına dönüştü

Dosya doğrulama, parser, sayfa/slayt koruyan chunking, worker, embedding ve ilk
Next.js ders ekranları eklendi. Ardından Speckit, proje anayasası ve
<code>001-course-assistant-mvp</code> ile geliştirme “önce kod”dan “önce sözleşme ve
kabul kriteri” modeline geçti.

**Öğrenilen:** Atıf kalitesi üretim sonunda eklenen bir metin değil, ingestion sırasında
korunan provenance’ın sonucudur.

### 4. 6–9 Ağustos — chatbot’tan tam öğrenme döngüsüne

Auth köprüsü, sohbet/cache/log, soru/sınav/mastery, analitik, embedding provenance ve dar
grant’ler geldi. Retrieval, generation ve Sokratik akış birleştirildi. Soru üretimi,
öğretmen onayı, server-timed sınav, grading ve “Neden yanlış?” aynı ürün döngüsüne
bağlandı. Gold set, holdout ve RLS mutasyon kanıtları eklendi.

**Dönüm noktası:** Ürün artık yalnız soru cevaplayan bir bot değildi; eğitmenin
materyali yüklediği, soruyu onayladığı, öğrencinin çalıştığı ve sonucun ölçüldüğü
kapalı bir öğrenme çevrimiydi.

### 5. 9–10 Ağustos — demo varsayımları production-hardening’e dönüştü

<code>002-production-hardening</code> şu gerçek kusurları görünür kıldı:

- sınav yardımı yalnız UI/mod ile değil, aktif oturum durumuyla kilitlenmeli;
- ikinci sekme ve doğrudan API yolu aynı sınırdan geçmeli;
- senkron parsing/embedding event loop’u kilitlememeli;
- embedding hazırlığı readiness’ten ayrılmalı;
- pahalı üretim uçlarında hız ve eşzamanlılık sınırı olmalı;
- belgelerdeki sayılar elle değil kaynak koddan ölçülmeli.

Bu dalda <code>0008–0013</code> ile blueprint, ders AI politikası, retry, pagination,
KVKK hakları ve consent-based feedback eklendi.

### 6. 10 Ağustos — uygulama gerçek bir portala dönüştü

<code>003-product-portal</code>, ürüne dashboard, profil, hesap/veri hakları ve ayrı
Bilgi İşlem paneli getirdi. <code>0014</code>, platform admini ders eğitmenliğinden
ayırdı; salt okunur, içeriksiz ve audit edilebilir operasyon yüzeyi kurdu.

**Öğrenilen:** Admin observability, öğrenci sohbetini veya akademik cevabı görme yetkisi
anlamına gelmez.

### 7. 11 Ağustos — doğrulanmış baseline main’e ulaştı

PR #4, production-hardening ve portalı <code>origin/main</code> dalına
<code>2c17886</code> ucu olarak taşıdı. Bu; runtime, security, reliability,
modularizasyon, docs gate, E2E ve RLS çalışmalarının birleşmiş repository baseline’ıdır.

Bu adım **canlı production deploy** değildir.

### 8. 11 Ağustos — AI-SDLC ve engineering governance

<code>004-ai-sdlc-excellence</code> dalında:

- AI artifact policy/schema/dossier;
- AI-sensitive diff gate;
- CODEOWNERS, PR şablonu ve dependency/security workflow’ları;
- release evidence doğrulaması;
- build-once/promote-by-digest ADR;
- SLO, incident response ve release/rollback belgeleri

hazırlandı. Dal uzak repoya gönderildi ancak main’e birleşmedi. Canlı ruleset,
protected environment ve release gözlemi hâlâ dış doğrulama gerektirir.

### 9. 11 Ağustos — rol farkındalıklı ders ajanı

<code>005-role-aware-course-agent</code>:

- öğrenci için Ders Koçu;
- eğitmen için Eğitmen Asistanı;
- immutable audience ve persona spoof reddi;
- öğrenci/eğitmen cache izolasyonu;
- atomik kullanıcı/ders/platform token rezervasyonu;
- hard cap, concurrency, output limit ve kill switch;
- exam/chat/export yarış kilitleri;
- içeriksiz guard ledger;
- native course-assistant UI

ekledi. Dal uzak repoya gönderildi fakat PR/CI/main birleşmesi açık.

**Öğrenilen:** Bir eğitim ajanının değeri “daha otonom” olmasından değil, yetkisi,
kaynağı, maliyeti ve pedagojik davranışının sınırlarının görünür olmasından gelir.

### 10. Bugün — AI slop’tan uzak ürün tasarımı

<code>design/product-ui-refresh</code> adayı giriş, AppShell, dashboard,
ders ana sayfası, profil ve admin yüzeylerini daha editoryal bir akademik stüdyoya
dönüştürüyor. Tek kırmızı aksan, daha net tipografik hiyerarşi, düz veri rayları,
responsive/dark-mode davranışı ve dürüst durum dili kullanılıyor.

11 Ağustos adayında 325 frontend testi, typecheck, açık/koyu tema kontrast kontrolü ve <!-- docs-check: tarihsel 325 · 2026-08-11 -->
production build geçti. Benzersiz PostgreSQL ile gerçek API’ye karşı seri Playwright
paketi 35/35 geçti; ders/audit kalıntısı 0/0 ölçüldü. <!-- docs-check: tarihsel 35 · 2026-08-11 --><!-- docs-check: tarihsel 0 · 2026-08-11 --> Manuel ekran okuyucu ve
<code>prefers-reduced-motion</code> gözlemi ile bütün uygulama-katmanı mutasyon matrisi
ayrı kapılar olarak açık tutulur. Dal main’e henüz birleşmedi.

## Yol boyunca bulunan ve kapatılan gerçek kusurlar

| Kusur | Nasıl bulundu? | Kalıcı ders |
|---|---|---|
| RLS mastery/answer izolasyon açığı | Temiz DB’de saldırı + mutasyon | “Policy var” değil, policy kaldırılınca test kırmızı mı? |
| GitHub Actions hiç job başlatmıyordu | İlk gerçek CI incelemesi | Yerel yeşil, CI’ın çalıştığını kanıtlamaz |
| Kurulum yeni migration’ları atlıyordu | Sıfırdan kurulum | Migration’ları tek tek belgelemek yerine sıralı glob uygula |
| Aktif sınavda ikinci sekmeden sohbet | Gerçek kullanıcı akışı | Exam integrity bir UI değil, state/race problemidir |
| Sync ONNX embedding event loop’u donduruyordu | Runtime ölçümü | CPU işini async fonksiyon içinde çağırmak onu async yapmaz |
| JWT issuer env adı sessizce yutuluyordu | Config-kod karşılaştırması | Örnek env ile Settings sözleşmesi test edilmelidir |
| GET retry ve timeout eksikti | Frontend reliability turu | POST otomatik retry edilmez; request ID görünür olmalıdır |
| E2E verisi birikiyor ve paylaşılan DB’yi bozuyordu | Seri/paralel test farkı | Run-scoped veri + fail-closed cleanup gerekir |
| Test DB kimliği CI ile fixture’da ayrışıyordu | Draft PR CI | DB’yi kuran ve kullanan süreç aynı identity’yi paylaşmalı |
| ONNX symlink/hardlink imajda reddediliyordu | Docker/CI kapısı | “Gerçek dosya” tek bağlantılı inode sözleşmesidir |
| Belgelerde farklı test sayıları vardı | Kod-belge karşılaştırması | <code>docs_check</code> sayıların kaynağını komut yapar |
| Admin metriği özel veriyi eşleyebilirdi | Adversarial security review | Operasyon paneli aggregate ve içeriksiz olmalıdır |
| Chat finalizasyonu sınav başlangıcıyla yarışabiliyordu | Forced interleaving review | Entry check yetmez; paylaşılan DB kilidi gerekir |
| KVKK export eski cevapları sınavda sızdırabiliyordu | Yan yol tehdit analizi | Güvenlik sınırı bütün veri çıkışlarını kapsamalıdır |

## Ekran görüntüleri

Aşağıdaki görseller **9 Ağustos 2026 işlevsel baseline’ına** aittir. Kaynak yükleme,
atıf, Sokratik davranış, sınav, analitik ve izolasyonun çalıştığını gösterir; bugünkü
yerel UI refresh’inin güncel görünümü olarak sunulmaz.

<details>
<summary><b>Tarihsel ürün galerisi</b></summary>

<br/>

**Materyal yönetimi**

![Materyaller](docs/images/03-egitmen-materyaller.png)

**Kaynaklı cevap**

![Kaynaklı cevap](docs/images/09-sohbet-kaynakli-cevap.png)

**Sokratik ısrar reddi**

![Sokratik mod](docs/images/13-sokratik-israr-ilerlemiyor.png)

**Kapsam dışı nazik ret**

![Nazik ret](docs/images/10-sohbet-nazik-ret.png)

**Soru havuzu ve onay**

![Soru havuzu](docs/images/05-egitmen-soru-havuzu.png)

**Sınav provası**

![Sınav provası](docs/images/14-ogrenci-sinav-provasi.png)

**Sınıf analitiği**

![Sınıf analitiği](docs/images/06-egitmen-sinif-analitigi.png)

**KVKK**

![KVKK](docs/images/16-kvkk.png)

**Üye olunmayan ders için 404**

![İzolasyon](docs/screenshots/08-izolasyon-404.png)

</details>

Güncel tasarımın ekran görüntüleri, feature dalı review edildikten ve aday kimliği
sabitlendikten sonra yeniden üretilmelidir. Tarihsel PNG’ler sessizce “güncel”
etiketine taşınmaz.

## Production’a giden açık yol

### Kod/repo seviyesinde açık kapılar

- 004 ve 005 dalları için PR, temiz CI ve main birleşmesi.
- Güncel ürün adayının review edilmesi, CI’da gözlenmesi ve onaydan sonra main’e birleşmesi.
- Manuel VoiceOver+Safari turu; doğrudan exam POST ve kill-switch tarayıcı yolları.
- Yerel fake/mutasyon/yük sonuçlarının exact candidate hash'leriyle final R4
  evidence kaydına bağlanması.
- OpenAPI ve docs-check’in final aday commit’i üzerinde yeniden üretilmesi.

### Gerçek model ve ürün kalitesi

- Groq/Gemini ile dondurulmuş holdout.
- Kaynak faithfulness ve citation precision örneklemi.
- Öğrenci için cevap sızıntısı / ipucu yararlılığı insan değerlendirmesi.
- Eğitmen için doğruluk, kaynak bağlılığı ve taslak yararlılığı.
- Soru üretiminde öğretmen kabul/red oranı.
- Kapsam dışı ret ve prompt injection dayanımı.
- Token, maliyet ve p95 latency ölçümü.

### Staging ve production

- Gerçek Supabase Auth ve Storage.
- Staging URL ve environment secret’ları.
- Multi-worker yük ve atomik kota doğrulaması.
- OTel/telemetry export ve gerçek alarm teslimi.
- Backup/restore tatbikatı.
- Veri saklama ve residency kararı.
- Protected environment ve bağımsız approver.
- Canary, kill-switch gözlemi ve canlı rollback provası.
- Production promotion ve operasyon devir teslimi.

Bu kapılar tamamlanmadan “production-ready”, “canlıda” veya “gerçek LLM kalitesi
kanıtlandı” ifadeleri kullanılmaz.

## Yerel kurulum

Tam kurulum ve doğrulama için:
[Speckit quickstart](specs/005-role-aware-course-agent/quickstart.md).

### Önkoşullar

- PostgreSQL 16 + pgvector
- Python 3.12
- uv
- Bun 1.3+
- Node uyumlu shell ortamı

### 1. Depoyu klonla

~~~bash
git clone https://github.com/muratcan-ates/DOU-Synapse.git
cd DOU-Synapse
~~~

### 2. Veritabanını kur

~~~bash
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
createdb dou_synapse
for f in supabase/migrations/*.sql; do
  psql -v ON_ERROR_STOP=1 -d dou_synapse -f "$f"
done
psql -d dou_synapse -f supabase/local_dev_setup.sql
psql -d dou_synapse -f supabase/seed_demo.sql
~~~

### 3. API bağımlılıklarını kur ve test et

~~~bash
(
  cd apps/api
  uv sync --extra dev --frozen
  cp ../../.env.example .env
  uv run pytest -q
)
~~~

Güncel feature kanıtında backend koleksiyonu 894 testtir. <!-- docs-check: backend.tests = 894 -->

### 4. Web bağımlılıklarını kur ve test et

~~~bash
(
  cd apps/web
  bun install --frozen-lockfile
  bun test lib/
  bun run typecheck
  bun run build
)
~~~

Güncel feature kanıtında frontend kütüphane paketi 349 testtir. <!-- docs-check: frontend.tests = 349 -->

### 5. Üç servisi ayrı terminallerde başlat

Terminal 1 — API:

~~~bash
cd apps/api
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
~~~

Terminal 2 — worker:

~~~bash
cd apps/api
uv run python -m app.worker
~~~

Terminal 3 — web:

~~~bash
cd apps/web
bun run dev
~~~

Ardından [http://localhost:3000](http://localhost:3000) adresini açın.

### Embedding modu

Hashing modu deterministik ve hızlıdır; test/CI için kullanılır, anlamsal kalite kanıtı
değildir. Gerçek semantic retrieval için FastEmbed modeli kullanılır. Korpus hangi
embedding provider ve sürümüyle üretildiyse sorgu aynı uzayda çalışmalıdır; migration
provenance kaydı uyuşmazlıkta fail-closed davranışı sağlar.

## Depo haritası ve belgeler

~~~text
apps/
  api/                     FastAPI, worker, AI/RAG, assessment, admin
  web/                     Next.js ürün arayüzü ve Playwright
supabase/
  migrations/              0001–0015 şema, RLS ve SECURITY DEFINER sözleşmeleri
  tests/                   RLS ve mutasyon betikleri
specs/
  001-course-assistant-mvp
  002-production-hardening
  003-product-portal
  004-ai-sdlc-excellence
  005-role-aware-course-agent
.ai/                       AI change policy, schema, dossier ve kanıt
.release/                  Release evidence sözleşmesi ve validator
docs/
  engineering/             AI-SDLC, release, SLO, incident response
  adr/                     Mimari karar kayıtları
  images/                  Tarihsel ürün ekranları
evaluation/                Gold set, kalibrasyon, holdout ve kalite araçları
sample_data/               İşletim Sistemleri örnek ders paketi
scripts/                   Docs, workflow, eval ve güvenlik kontrolleri
~~~

### Başlangıç belgeleri

| Belge | Amaç |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Sistem bileşenleri, güven sınırları ve kararlar |
| [DESIGN.md](DESIGN.md) | UI tasarım sistemi ve ürün dili |
| [Proje anayasası](.specify/memory/constitution.md) | Pazarlık yapılmayan geliştirme ilkeleri |
| [Gereksinim analizi](docs/requirements-analysis.md) | Danışman taslağı → izlenebilir gereksinimler |
| [Öğrenci kılavuzu](docs/student-guide.md) | Öğrenci akışları |
| [Eğitmen kılavuzu](docs/instructor-guide.md) | Eğitmen akışları |
| [KVKK](docs/kvkk.md) | Veri işleme ve kullanıcı hakları |
| [AI-SDLC](docs/engineering/AI_SDLC.md) | AI değişiklik yönetimi |
| [Engineering Excellence](docs/engineering/ENGINEERING_EXCELLENCE.md) | CI, supply chain ve kalite sistemi |
| [Release süreci](docs/engineering/RELEASE_PROCESS.md) | Candidate, promotion ve rollback |
| [SLO](docs/engineering/SLO.md) | Hedef hizmet seviyeleri ve kanıt durumu |
| [Incident response](docs/engineering/INCIDENT_RESPONSE.md) | Olay yönetimi |
| [ADR kayıtları](docs/adr/README.md) | Mimari karar geçmişi |
| [Demo runbook](docs/runbook.md) | Demo günü kontrol ve fallback planı |
| [Test raporu](docs/test-report.md) | Ölçüm ve sınırlar |

## Ürün ilkelerimiz

1. **Kaynak yoksa cevap yok.**
2. **Öğretmen onayı olmadan soru yayınlanmaz.**
3. **Sınav bütünlüğü UI’da değil, API ve veritabanında korunur.**
4. **Rol global değil, ders üyeliğinden türetilir.**
5. **Admin observability, akademik içerik yetkisi değildir.**
6. **Fake provider, gerçek model kalitesi değildir.**
7. **Belge sayısı elle yazılmaz; kaynağından ölçülür.**
8. **Yeşil test ancak guard kaldırıldığında kırmızıya dönebiliyorsa anlamlıdır.**
9. **Production iddiası canlı ortam kanıtı olmadan yapılmaz.**
10. **AI daha otonom olduğu için değil, daha güvenilir öğrettiği için değerlidir.**

## Takım

- **Muratcan Ateş** — frontend, ürün, entegrasyon ve proje liderliği
- **Eren Onur** — backend, RAG ve guardrail
- **Metehan Alphan** — assessment ve değerlendirme
- **Yasemin Karagül** — proje danışmanı

## Lisans

Bu proje [MIT Lisansı](LICENSE) ile yayımlanır.
