# Özellik Şartnamesi: Rol Bazlı Ürün Portalı

**Feature Branch**: `003-product-portal`
**Base**: `3b707ca` (`002-production-hardening`)
**Created**: 2026-08-10
**Status**: Yerelde doğrulanmış release adayı; 002 entegrasyonu ve staging/production kanıtı bekliyor

**Input**: Yasemin Karagül'ün CourseGPT proje taslağı, önceki toplantı kararları,
002 production-hardening çıktıları, OBS ekranlarından çıkarılan bilgi mimarisi
dersleri ve resmi benzer ürün incelemeleri.

---

## 1. Amaç

DOU-Synapse bugün güçlü ders, RAG, sohbet, sınav, blueprint, AI politikası,
analitik ve veri hakkı yüzeylerine sahiptir. Ancak ürün, kullanıcı girişinden sonra
onu yönlendiren tek bir ana sayfa; kimliği ve ders bazlı rollerini açıklayan bir
profil; ve akademik içeriği açmadan sistemi işletmeye yarayan bir platform yönetim
paneli taşımamaktadır.

003'ün amacı, mevcut yetenekleri yeni bir çatıya taşımak veya yeniden yazmak değil,
onları **öğrenci, eğitmen ve platform yöneticisi için tek, anlaşılır ürün
yolculuğunda birleştirmektir**.

### Durum sözlüğü

Bu şartname boyunca üç ifade bilinçli olarak ayrılır:

| İfade | Anlamı |
|---|---|
| **Kodlandı** | İlgili dosya ve davranış repo ağacında bulunuyor. |
| **Yerelde doğrulandı** | Hedefli test, gerçek API isteği ve gerekiyorsa tarayıcı gözlemi aynı commit'te geçti. |
| **Production'da kanıtlandı** | Gerçek kimlik, gerçek depolama, gerçek sağlayıcı ve canlı URL üzerinde ölçülmüş kanıt var. |

Bir alt seviyenin varlığı üst seviyeyi ima etmez. Bu feature'ın ilk şartname
snapshot'ında portal, profil ve platform admin yüzeyleri henüz kodlanmamıştı; bu
tarihsel başlangıç durumu aşağıdaki güncel dal notunun yerine geçmez. 002'de bulunan
yetenekler repo gerçeğidir; bu şartname onları yeniden doğruladığını iddia etmez.

**Güncel dal notu**: Portal backend/frontend dosyaları ve `0014` migration'ı
feature commit'lerinde bulunmaktadır. Hedefli ve tam backend/frontend paketleri,
RLS referans ve mutasyon kapıları, generated OpenAPI, production build ve koşu
kimlikli tarayıcı yolculukları geçtiği için feature **yerelde doğrulandı**
durumundadır. Gerçek Auth/Storage/LLM, telemetry, yük, restore ve canlı URL
kanıtları olmadığı için **production'da kanıtlandı** durumu açıkça yoktur.

---

## 2. Teknoloji kararı

Mevcut yığın korunur:

- **Frontend**: Next.js 16.3 App Router, React 19.2, TypeScript 5, Tailwind CSS 4
- **Backend**: FastAPI, Python 3.12, SQLAlchemy 2 async
- **Veri**: PostgreSQL 16, pgvector, düz SQL migration ve RLS
- **AI**: LiteLLM sağlayıcı katmanı, fastembed `multilingual-e5-large`, hibrit retrieval
- **Kimlik ve dosya**: Supabase Auth ve üretimde Supabase Storage

Plain HTML/CSS'e, Streamlit/Gradio'ya veya yalnız React SPA'ya yeniden yazım
yapılmayacaktır. Mevcut yığın zaten hocanın önerdiği Next.js/React seçeneğinin
production sınıfı sürümüdür. Yeniden yazım, çalışan RAG/sınav güvenliğini taşırken
regresyon üretir ve kullanıcı değerini artırmaz.

---

## 3. Hoca gereksinimleriyle mevcut durum

| Gereksinim | 003 başlangıcındaki repo gerçeği | 003'ün katkısı | Production kanıtı |
|---|---|---|---|
| PDF, Markdown ve kod yükleme | Kodlandı | Dashboard'dan durum ve aksiyon görünürlüğü | Yok |
| Yalnız öğretmen kaynağından RAG | Kodlandı | Kaynak sağlığı ve eksik aksiyon özeti | Gerçek LLM ölçümü bekliyor |
| Kaynak gösterimi | Kodlandı; chunk bağlamı ve kaynak ekranı var | Dashboard'dan kaynak laboratuvarına giriş | Faithfulness holdout bekliyor |
| Sokratik çalışma | Kodlandı | Öğrenci ana sayfasında doğru giriş noktası | Pedagojik insan değerlendirmesi bekliyor |
| Sınav provası ve süre | Kodlandı | Yaklaşan/yürüyen sınav aksiyonu | Canlı yük altında kanıt yok |
| Sınav sırasında yardım yasağı | Kodlandı | Kilit durumu portalda da tutarlı görünür | Production E2E yok |
| Sınav blueprint'i | Kodlandı | Eğitmen kartından araca hızlı giriş; yeni sayaç uydurulmaz | Production veriyle kanıt yok |
| Ders bazlı AI politikası | Kodlandı | Eğitmen dashboard'undan doğrudan giriş | Gerçek maliyet/bütçe kanıtı yok |
| AI soru üretimi ve onay | Kodlandı | Taslak soru sayısı ve inceleme aksiyonu | Gerçek LLM kabul oranı ölçülmedi |
| “Neden yanlış?” | Soru tipi ve LLM kalitesine bağlı, kısmi | Öğrenci ilerleme ve tekrar çalışma girişi | Rubrik kalite çalışması bekliyor |
| Öğrenci/eğitmen ayrımı | Ders bazında kodlandı | Karma rolleri tek profilde açık gösterme | Canlı kimlik kanıtı yok |
| Çalışan web platformu | Yerel repo yüzeyleri var | Rol bazlı ürün ana sayfası, profil, admin | Doğrulanmış canlı URL yok |
| Başarı testi ve kılavuz | Repo içinde test/eval belgeleri var | Tek release matrisi ve kanıt statüsü | Gerçek sağlayıcı + insan eval bekliyor |

---

## 4. Kullanıcı hikâyeleri

### US1 - Öğrenci kaldığı yere tek ekrandan döner (P1)

Öğrenci giriş yaptığında derslerini, her dersteki rolünü, çalışmaya devam edeceği
asistan/sınav/ilerleme girişlerini ve bekleyen önemli aksiyonları tek bir ana
sayfada görür. OBS'deki “aktif dönem bilgisi” fikri, resmi akademik kayıt taklidi
olmadan “bu dönemki derslerim ve çalışma durumum” biçiminde uyarlanır.

**Independent Test**: İki derste öğrenci olan kullanıcı `/dashboard` açar; yalnız
aktif üyelikleri ve kendi çalışma özetleri görünür, başka kullanıcının satırı yoktur.

**Acceptance Scenarios**:

1. Ders yoksa boş durum ne yapılacağını söyler; uydurma örnek ders göstermez.
2. Belgeleri henüz işlenmemiş bir derste “çalışmaya hazır” denmez; gerçek durum görünür.
3. Yürüyen sınav varsa asistan bağlantısı açık görünmez ve kilit nedeni sunucudan gelir.
4. Aynı kullanıcı bir derste öğrenci, başka derste eğitmense her kart kendi gerçek rolünü gösterir.
5. Dar ekranda ana görevler yatay kaydırma gerektirmeden kullanılabilir.

### US2 - Eğitmen operasyon kuyruğunu görür (P1)

Eğitmen giriş yaptığında yönettiği dersleri ve her ders için materyal işleme,
taslak soru onayı, blueprint hazırlığı, AI politikası ve sınıf ilerlemesi gibi
işleri bir aksiyon kuyruğunda görür. Bu, Khanmigo'daki ayrı öğretmen araçları
yaklaşımının DOU-Synapse'e uygun karşılığıdır; tek sohbet kutusu değildir.

**Independent Test**: Eğitmenin bir derste başarısız/işlenen belge ve taslak
soruları vardır. Dashboard doğru sayaçları ve blueprint dahil gerçek öğretmen
araçlarına giden çalışan bağlantıları gösterir.

**Acceptance Scenarios**:

1. Yalnız eğitmen olduğu derslerde yönetim aksiyonları görünür.
2. Her aksiyon gerçek bir hedefe gider; etkin görünüp iş yapmayan kontrol yoktur.
3. Dersin öğrenci sohbet metinleri dashboard veya admin görünümüne sızmaz.
4. İşleme başarısızlığı, işlenmekte olan belge ve bekleyen soru ayrı etiketlenir;
   blueprint aracı sayaç uydurmadan görünür bir giriş olarak sunulur.
5. “Sınıf özeti” yalnız ölçülmüş toplu veriyi taşır; bireysel gizli sohbet taşımaz.

### US3 - Kullanıcı profilini ve veri haklarını yönetir (P1)

Kullanıcı adını, e-posta kimliğini, aktif ders üyeliklerini ve her dersteki rolünü
tek profilde görür. Değiştirilebilir alan ile kimlik sağlayıcısının yönettiği alan
ayrıdır. Var olan KVKK indirme, sohbet silme ve anonimleştirme akışları bu profil
alanından erişilebilir olur; yeniden yazılmaz.

**Independent Test**: Kullanıcı yalnız `full_name` alanını günceller; e-posta,
rol, platform adminliği veya başka profil alanı değiştirilemez.

**Acceptance Scenarios**:

1. `GET /me/profile` kimliği, maskelenmemiş kendi e-postasını, üyelikleri ve platform admin durumunu döndürür.
2. `PATCH /me/profile` yalnız 2–120 karakterlik `full_name` kabul eder; bilinmeyen alanı reddeder.
3. Kullanıcı kendisini eğitmen veya platform admin yapamaz.
4. Profil, KVKK/veri hakkı ekranına açık bağlantı taşır.
5. Profil yüklenemezse eski localStorage adı “gerçek profil” gibi gösterilmez.

### US4 - Bilgi İşlem platformu akademik mahremiyeti bozmadan işletir (P1)

Platform yöneticisi kullanıcı, ders, istek ve belge işleme sağlığını görür; ancak
bu rol öğretmen rolü değildir. Platform adminliği bir derse üyelik sağlamaz,
öğrenci sohbetini, cevap metnini, soru içeriğini veya kaynak metnini açmaz.

**Independent Test**: Platform admin hiçbir derse üye değildir. `/admin` operasyon
özetini görür; ders detayına veya sohbet geçmişine doğrudan gittiğinde mevcut ders
üyeliği kapısı onu reddeder.

**Acceptance Scenarios**:

1. Admin olmayan kullanıcı bütün `/admin/*` uçlarında 403 alır.
2. Admin kullanıcı listesinde yalnız maskeli e-posta görür.
3. İstek listesinde prompt/cevap ve kullanıcıyı eşleştiren hiçbir kimlik alanı yoktur.
4. Admin, platform admin tablosuna uygulama rolüyle INSERT/UPDATE/DELETE yapamaz.
5. Sistem sağlığı uygulama, veritabanı ve embedding hazırlığını ayrı gösterir.
6. Liste uçları sayfalanır ve limit sunucuda en fazla 100'e kırpılır.
7. Admin konsolu ilk yetki sonucu gelmeden hassas uçlara paralel istek atmaz.

### US5 - Operasyon ve release gerçeği tek yerde görünür (P2)

Takım, “kod var” ile “canlıda kanıtlandı” arasındaki farkı kaybetmeden sistemi
yayına hazırlar. Admin ekranı debug konsolu değildir; teknik ayrıntıların güvenli
özeti ve destek kodları vardır. Ham stack trace veya kullanıcı içeriği yoktur.

**Independent Test**: Hazırlık probe'u embedding henüz hazır değilken bunu ayrı
durumla bildirir; admin overview aynı gerçeği tarih damgasıyla gösterir. API
canlı ama model hazırlığı bitmemişse tek bir yanıltıcı “Her şey sağlıklı” rozeti yoktur.

---

## 5. Fonksiyonel gereksinimler

### Kimlik ve yetki

- **FR-301**: Profil ve dashboard kimliği sunucudan okunmalı; localStorage rolü yetki veya platform admin kanıtı olmamalıdır.
- **FR-302**: Ders rolü her ders üyeliğinden çözülmeli; sistem geneli “öğrenci/eğitmen” rolü türetilmemelidir.
- **FR-303**: Platform adminliği `platform_admins` ilişkisinde tutulmalı ve ders üyeliğinden bağımsız olmalıdır.
- **FR-304**: Platform adminliği uygulamanın normal kullanıcı rolüyle değiştirilememelidir.
- **FR-305**: Platform admin, yalnız admin olduğu için akademik ders içeriğine erişmemelidir.

### Profil

- **FR-310**: `GET /me/profile`, `id`, kendi `email`, `full_name`, üyelikler ve `is_platform_admin` döndürmelidir.
- **FR-311**: `PATCH /me/profile` yalnız zorunlu `full_name` alanını kabul etmelidir.
- **FR-312**: `full_name` trim edildikten sonra 2–120 karakter olmalıdır.
- **FR-313**: Profil e-postasının kimlik sağlayıcısı tarafından yönetildiği arayüzde açık yazılmalıdır.
- **FR-314**: Profil, mevcut `/account` veri hakkı akışına bağlanmalıdır.

### Dashboard

- **FR-320**: `GET /dashboard`, tek istekte rol bazlı ders özetlerini döndürmelidir.
- **FR-321**: Her ders özeti kendi rolünü taşımalıdır.
- **FR-322**: Eğitmen özeti `documents_processing`, `documents_failed`,
  `draft_questions` ve `published_exams` için gerçek sayılar taşımalıdır; dashboard
  sözleşmesinde bulunmayan taslak blueprint sayısı üretilmemelidir.
- **FR-323**: Öğrenci özeti yalnız kendi çalışma/sınav verisinden türemelidir.
- **FR-324**: `action_items`, işlenen ve başarısız belgeler ile bekleyen taslak soruların toplamından türetilmelidir; ekranda formülü gizleyen sihirli sayı olmamalıdır.
- **FR-325**: Dashboard sahte dönem, GPA, danışman veya duyuru verisi üretmemelidir.
- **FR-326**: Öğrenci ders kartı etkin ve süresi dolmamış sınav oturumunda
  `assistant_locked`, `assistant_lock_reason` ve `assistant_lock_message`
  alanlarını sunucudan almalı; asistan deep-link'i yerine sınava dönüş eylemi
  göstermelidir. Practice/süresi dolmuş oturum ve eğitmen kartı kilitlenmemelidir.

### Platform admin

- **FR-330**: `0014_platform_admin_console.sql`, `platform_admins` tablosunu RLS ve açık GRANT/REVOKE ile oluşturmalıdır. RLS etkin, FORCE değildir; tablo sahibi dar `SECURITY DEFINER` yardımcılarının kontrollü okuyabilmesi gerekir.
- **FR-331**: Admin sorguları doğrudan tablo SELECT yetkisine değil, dar `SECURITY DEFINER` fonksiyonlarına dayanmalıdır.
- **FR-332**: Her admin fonksiyonu çağıranı kendi içinde yeniden platform admin olarak doğrulamalıdır.
- **FR-333**: Admin overview kullanıcı, aktif üyelik, ders, belge, başarılı sohbet
  turu, token ve işleme durumlarının toplu sayılarını; başarılı sohbetlerin p95
  gecikmesini, uygulama/DB/embedding sağlık özetini ve ölçüm zamanını taşımalıdır.
- **FR-334**: Kullanıcı listesi tam e-posta yerine maskeli e-posta döndürmelidir.
- **FR-334A**: Admin kullanıcı araması `full_name` ve SQL tarafında üretilen
  maskelenmiş e-posta ifadesi üzerinde çalışmalıdır. Tam e-posta araması eşleşmemeli;
  arama değeri `POST /admin/users` JSON gövdesinde taşınmalı ve URL/access log
  query alanına bırakılmamalıdır.
- **FR-335**: İstek listesi `log_id`, yol, mod, kategorik cevap durumu, HTTP durumu, gecikme, token ve cache bilgisi taşıyabilir; serbest metin taşıyamaz.
- **FR-336**: Request listesi kullanıcı UUID'si, e-posta, hash/pseudonym veya
  kullanıcı diziniyle eşlenebilecek başka bir kimlik alanı taşımamalıdır.
- **FR-337**: Admin liste uçları cursor veya page/limit ile sayfalanmalı, limit 100'ü geçmemelidir.
- **FR-338**: Admin ekranı salt okunur başlamalıdır; kullanıcı silme, rol verme veya ders müdahalesi bu dikey dilimde yoktur.
- **FR-339**: Admin ingestion listesi dosya adını veya belge içeriğini döndürmemeli; yalnız `document_id`, `course_id`, `course_code`, durum, deneme sayısı ve zaman damgalarını taşımalıdır.

### Arayüz ve erişilebilirlik

- **FR-340**: Yeni ekranlar `DESIGN.md` token'larını ve mevcut `AppShell`, `PageHeader`, `Card`, `ErrorNote`, `Loading` bileşenlerini kullanmalıdır.
- **FR-341**: OBS'nin kalıcı koyu yan menüsü kopyalanmamalı; mevcut üst çubuk ve ders içi yatay gezinme korunmalıdır.
- **FR-342**: Durum yalnız renkle anlatılmamalı; metin ve gerektiğinde ikon taşımalıdır.
- **FR-343**: Koyu tema ve 375 px mobil görünüm release kapısıdır.
- **FR-344**: Aynı profil verisi aynı ekranda iki kez çekilmemeli; ortak bağlam tek istek paylaşmalıdır.
- **FR-345**: Loading, empty, partial ve error durumlarının her biri ayrı tasarlanmalıdır.

### Gözlemlenebilirlik ve güvenlik

- **FR-350**: Kullanıcıya gösterilen her sunucu hatası mevcut `request_id` sözleşmesini korumalıdır.
- **FR-351**: Admin görünümü ham uygulama logu veya stack trace göstermemelidir.
- **FR-352**: Production gözlemlenebilirliği log, metrik ve trace sinyallerini içerik toplamadan ilişkilendirecek şekilde tasarlanmalıdır.
- **FR-353**: Prompt, cevap, kaynak metni, tam e-posta ve access token telemetry'ye yazılmamalıdır.
- **FR-354**: Beş admin endpoint'ine izin verilen ve reddedilen erişim denemeleri,
  ayrı tamamlanan işlemde `actor_user_id`, allowlist action, `allowed|denied`,
  `request_id` ve zamanla append-only audit tablosuna yazılmalıdır. Bu tablo için
  uygulama/worker grant'i veya listeleme endpoint'i bulunmamalıdır; admin tablo
  değişikliği yalnız kontrollü operatör işlemiyle yapılmalıdır.

### Doğruluk statüsü

- **FR-360**: Her roadmap teslimi `kodlandı`, `yerelde doğrulandı`, `staging doğrulandı`, `production'da kanıtlandı` alanlarıyla raporlanmalıdır.
- **FR-361**: Koşulmayan gerçek sağlayıcı, load, backup/restore veya insan eval sonucu `KOŞULMADI` olarak kalmalıdır.
- **FR-362**: Test sayıları elle çoğaltılmamalı; mevcut `docs_check` kaynağından türetilmelidir.

---

## 6. Başarı kriterleri

- **SC-301**: Öğrenci, eğitmen ve karma rollü kullanıcı doğru dashboard'a tek girişte ulaşır.
- **SC-302**: Admin olmayan kullanıcının denenen bütün admin uçları reddedilir.
- **SC-303**: Platform adminliği kaldırıldığında admin testleri kırmızı yanar; akademik üyelik testleri değişmeden kalır.
- **SC-304**: Admin request ve ingestion örneklerinde prompt, cevap, kaynak/dosya metni, dosya adı, tam e-posta veya ham kullanıcı UUID'si bulunmaz. Ayrı kullanıcı dizini, destek için kullanıcı `id`, `full_name` ve maskeli e-posta taşıyabilir.
- **SC-305**: Profil güncellemesi yalnız adı değiştirir; e-posta, rol ve adminlik aynı kalır.
- **SC-306**: Dashboard, profil ve admin ekranları 375 px ve masaüstünde yatay taşma olmadan çalışır.
- **SC-307**: Yeni ekranlar klavyeyle kullanılabilir ve görünür odak taşır.
- **SC-308**: Backend hedefli test, RLS/mutasyon, frontend birim testi, typecheck, production build ve Playwright kapıları geçmeden görev “bitti” sayılmaz.
- **SC-309**: Canlı URL, gerçek Supabase, gerçek Storage, gerçek LLM, load ve backup/restore kanıtı yoksa release raporu bunların hiçbirine “hazır” demez.

---

## 7. Edge cases

- Kullanıcının hiç aktif üyeliği yoktur ama platform admindir: boş dashboard görür, admin konsoluna erişebilir.
- Kullanıcı aynı anda farklı derslerde öğrenci ve eğitmendir: profil ve dashboard rolleri ders bazında korur.
- Admin tablosunda kullanıcı vardır fakat profili anonimleştirilmiştir: konsol tam kimlik sızdırmadan çalışır.
- Embedding modeli hazırlanırken API ve DB canlıdır: sağlık tek yeşil durumla özetlenmez.
- Profil isteği düşer: header localStorage adını sunucu profiliymiş gibi kesin göstermez.
- Request log status değeri `NULL` olabilir: filtre ve tablo bunu “sonuç yok” olarak açık gösterir.
- Çok uzun ders/kullanıcı listesi: ilk sayfa bounded gelir, devam kontrollü yüklenir.
- Admin kullanıcı tam e-posta ile arama ister: bu dikey dilimde desteklenmez; maskeli veri sınırı korunur.

---

## 8. Bilinçli kapsam dışı

- OBS'den transkript, resmi not listesi, GPA/AGNO, öğrenci numarası, kayıt yenileme veya resmi belge akışı kopyalamak
- Platform adminine öğrenci sohbeti ya da akademik cevap metni açmak
- Yeni mikroservis, Kubernetes, GraphRAG, LangChain/LlamaIndex veya ikinci vektör veritabanı
- Mobil native uygulama
- Kod çalıştırma sandbox'ı
- Admin panelinden yıkıcı kullanıcı/ders işlemleri
- Gerçek üniversite SIS entegrasyonu; ayrı veri sözleşmesi ve kurum izni olmadan yapılmaz

---

## 9. Varsayımlar ve dış bağımlılıklar

- Gerçek Supabase projesi, Auth ayarları, Storage bucket/politikaları ve LLM anahtarları kullanıcı/operatör tarafından sağlanacaktır.
- Production deploy, DNS, network restriction, backup/PITR ve üçüncü taraf gözlemlenebilirlik hesabı repo koduyla tek başına kanıtlanamaz.
- Bu feature, 002'nin göçlerini yeniden numaralamaz. Entegrasyon sırasında seçilerek alınacak `0013_chat_feedback.sql` için numara ayrılmıştır; portal göçü `0014_platform_admin_console.sql` olmalıdır.
- Platform admin ilk kaydı seed'e yalnız yerel demo için eklenebilir; production bootstrap ayrı operatör runbook'u ister.
