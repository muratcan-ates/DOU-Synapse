# Faz 0 Araştırma: Ürün Portalı ve Production Yolculuğu

**Branch**: `003-product-portal`
**Snapshot**: `b8da84e`, 2026-08-10
**Kural**: Bu belge karar kaydıdır. Ürün veya canlı ortam doğrulaması değildir.

---

## 1. Mevcut teknoloji yeterli mi?

### Repo bulgusu

- `apps/web/package.json`: Next.js 16.3, React 19.2.8, TypeScript 5, Tailwind 4.
- `apps/api/pyproject.toml`: Python 3.12, FastAPI, SQLAlchemy 2 async.
- `supabase/migrations/`: PostgreSQL/pgvector, RLS, blueprint, AI policy,
  ingestion retry, pagination ve privacy migration'ları.
- `apps/web/app/`: App Router sayfaları; ders, chat, sınav, blueprint, kaynak,
  analitik, ayar ve hesap yüzeyleri.
- `apps/api/app/main.py`: tek hata zarfı, request ID, güvenlik başlıkları,
  readiness/liveness ve router katmanı.

### Karar R-001: Yeniden yazma yok

**Karar**: Next.js/React + FastAPI + PostgreSQL/pgvector korunur.

**Neden**:

1. Kullanıcının “HTML/CSS/React” diye tarif ettiği modern web katmanı zaten vardır.
   React bileşenleri HTML üretir; Tailwind CSS katmanıdır; Next.js routing, server
   rendering, bundling ve production build sağlar.
2. Streamlit/Gradio prototip hızını artırabilir, fakat üç rol, erişilebilirlik,
   sınav bütünlüğü, admin konsolu, gerçek kimlik ve uzun ömürlü ürün navigasyonunda
   esnekliği azaltır.
3. Plain SPA'ya dönmek App Router'ın layout/error/loading ve server rendering
   yeteneklerini kaybettirir.
4. Backend'i Node'a taşımak RAG ve Python değerlendirme hattını yeniden yazdırır;
   kullanıcı değeri üretmez.

**Resmi dayanaklar**:

- [Next.js App Router](https://nextjs.org/docs/app)
- [React 19.2](https://react.dev/blog/2025/10/01/react-19-2)
- [Tailwind CSS v4](https://tailwindcss.com/blog/tailwindcss-v4)
- [FastAPI async yaklaşımı](https://fastapi.tiangolo.com/async/)
- [pgvector](https://github.com/pgvector/pgvector)

**Elenenler**: Streamlit/Gradio ana ürün, mikroservis, Kubernetes, LangChain,
LlamaIndex, GraphRAG, ikinci vektör veritabanı. Bunlar teknoloji modernliği değil,
şu an gereksiz mimari hareket üretir.

---

## 2. Ürün boşluğu nerede?

### Repo bulgusu

- Giriş sonrası ana ürün `/courses`; kullanıcıyı rolüne ve bekleyen işine göre
  yönlendiren dashboard yok.
- `AppShell` yalnız DOU Synapse, “Verilerim”, kullanıcı adı ve çıkış taşır.
- `/account` veri indirme, sohbet geçmişi silme ve anonimleştirme açısından güçlü;
  fakat profil kimliği ve ders rolleri görünmez.
- Platform geneli admin kavramı yoktur. `profiles` yorumu “sistem geneli rol yok”
  der; bütün mevcut akademik yetki `course_memberships` üzerindedir.
- Course içi rol çözümleme `useSession(courseId)` ile sunucuya bağlanmıştır; ancak
  `blueprints/page.tsx` hâlâ courseId vermeden `useSession()` çağırır. Karma rollü
  kullanıcıda yanlış UI üretme riski devam eder.

### Karar R-002: Üç ayrı rol bağlamı

1. **Kimlik**: kullanıcı kimdir?
2. **Ders rolü**: bu derste öğrenci mi eğitmen mi?
3. **Platform operasyon rolü**: sistemin güvenli metadata konsolunu görebilir mi?

Bu üçü tek `role` alanına sıkıştırılmaz. Platform admin, eğitmen değildir; eğitmen
de platform admin değildir. Aynı kullanıcı farklı derslerde farklı role sahip olabilir.

### Karar R-003: Tek portal, role göre bileşen

Ayrı öğrenci ve eğitmen uygulaması yapılmaz. `/dashboard` her ders kartını kendi
üyelik rolüyle çizer. Bu, karma rollü kullanıcının iki uygulama arasında yapay bir
switch yapmasını önler.

---

## 3. OBS'den ne alınır, ne alınmaz?

Kullanıcının sağladığı OBS ekranları bir görsel hedef değil, bilgi mimarisi
referansıdır. Mevcut `DESIGN.md` sakin, kurumsal, düşük varyanslı ürün dilini zaten
tanımlar ve 240 px yan menüyü gerekçesiyle reddeder.

### Alınacak ilkeler

| OBS fikri | DOU-Synapse karşılığı | Koşul |
|---|---|---|
| Girişte rol/işlem ayrımı | Öğrenci, eğitmen ve admin yüzeylerinin server-derived görünürlüğü | Ayrı sahte login kartları değil, gerçek yetki |
| Aktif dönem özeti | “Aktif derslerim ve çalışma durumum” | Resmi dönem entegrasyonu yoksa dönem adı uydurulmaz |
| Özet bilgi kartları | Belge, taslak soru, yayınlanmış sınav ve ilerleme metrikleri; blueprint'e araç bağlantısı | Yalnız gerçek API verisi |
| Danışman/duyuru görünürlüğü | İleride kurum entegrasyonlu yardım/duyuru alanı | Veri kaynağı ve sahiplik sözleşmesi olmadan yapılmaz |
| Ders programı | İleride sınav takvimi ve öğretmen ofis saati | Gerçek tarih/schedule modeli geldikten sonra |
| Dönem seçimi | İleride arşivlenmiş ders filtresi | Mevcut şemada dönem yok; bugün filtre yapılmaz |
| Sol menüde iş kümeleri | Dashboard üzerindeki aksiyon grupları | Mevcut üst çubuk + yatay ders navigasyonu korunur |

### Alınmayacaklar

- Sabit, koyu ve çok katmanlı eski tip sidebar.
- Resmi transkript, not listesi, AGNO/GPA, öğrenci numarası, kayıt yenileme,
  staj/başvuru/resmi belge süreçleri.
- Kurumdan gelmeyen sahte danışman, duyuru, ders saati veya akademik dönem.
- Aynı bilgiyi kutu, menü ve ayrı sayfada üç kez tekrarlayan yoğunluk.
- Masaüstüne göre tasarlanıp mobilde yalnız küçültülen tablo/menü yapısı.

### Karar R-004: OBS görünümü değil, OBS'nin “işe dönük başlangıç” ilkesi

DOU-Synapse'in ana sayfası bir kurum ERP'si olmayacaktır. Öğrencinin “hangi derse
çalışmalıyım?”, eğitmenin “hangi iş bekliyor?” ve operatörün “hangi servis sorunlu?”
sorularını hızlı cevaplayan rol bazlı portal olacaktır.

---

## 4. Benzer ürünlerden kalite eşlemesi

### 4.1 Khanmigo

Khan Academy'nin resmi yardım merkezi, öğretmen tarafında ders planı, rubric,
çoktan seçmeli değerlendirme, exit ticket ve Class Snapshot gibi ayrı araçlar
bulunduğunu anlatır: [Khanmigo Teacher Tools](https://support.khanacademy.org/hc/en-us/articles/14799047733645-What-teacher-tools-are-available-on-Khanmigo-).

**Alınacak ders**: öğretmen deneyimi tek chatbot değildir. DOU-Synapse dashboard'u
şu araçları görünür görevler hâline getirmelidir:

- materyal ve ingestion sağlığı,
- soru üretme ve taslak onayı,
- sınav blueprint'i,
- ders AI politikası,
- sınıf ilerleme özeti,
- daha sonra rubric/çıktı kalite incelemesi.

**Alınmayacak**: henüz ders/sınav ürün hedefiyle ilişkisi olmayan genel amaçlı
mektup, newsletter veya IEP üreticileri.

### 4.2 NotebookLM

Google'ın resmi yardım sayfasına göre citation seçildiğinde kullanıcı doğrudan
alıntının özgün konumuna gider ve kaynaklar seçilip dışarıda bırakılabilir:
[NotebookLM citations](https://support.google.com/notebooklm/answer/16179559?hl=en).

**Alınacak ders**:

- citation tıklaması mevcut source context sayfasına deep-link verir,
- kaynak kartı pasajı, dosya ve sayfa/slide konumunu birlikte gösterir,
- öğretmen ders AI politikasından kullanılacak belgeleri seçer,
- kaynak laboratuvarı chunk'ı ve komşu bağlamı gösterir.

**Kalite kapısı**: citation görünmesi yeterli değildir; citation precision,
claim support ve retrieval recall ayrı ölçülür.

### 4.3 Moodle AI Subsystem

Moodle resmi geliştirici dokümanı AI'ı **placement, action, provider** olarak ayırır;
subsystem manager çağrı ve loglama katmanıdır:
[Moodle AI Subsystem](https://moodledev.io/docs/5.1/apis/subsystems/ai).

**Alınacak ders**:

- placement: öğrenci sohbeti, sınav, öğretmen soru üretimi, kaynak laboratuvarı,
- action: grounded answer, Sokratik ipucu, soru üretimi, grading,
- provider: fake, Groq, Gemini,
- policy: hangi action'ın hangi derste/placement'ta açık olduğu.

Yeni plugin framework yazılmayacaktır. Mevcut `LlmTask`, sağlayıcı ve ders AI
politikası bu ayrımın hafif karşılığıdır; belgede ve admin ölçümlerinde görünür kılınır.

### 4.4 RAGFlow

RAGFlow resmi quickstart'ı chunk sonuçlarını görme/düzenleme ve retrieval testing
akışını ürün özelliği olarak sunar:
[RAGFlow quickstart](https://github.com/infiniflow/ragflow/blob/main/docs/quickstart.mdx).

**Alınacak ders**:

- belge → chunk sayısı ve parsing durumu,
- chunk/komşu bağlam önizlemesi,
- öğretmenin soru girip top-k retrieval sonucunu score ile test etmesi,
- kaynak sürümü değişti uyarısı,
- kötü retrieval için insan notu/feedback döngüsü.

**Ertelenecek**: chunk metnini doğrudan düzenleme. Düzenlenen metin kaynağın özgün
kanıtı olmaktan çıkar; provenance ve sürümleme tasarlanmadan açılmaz.

### 4.5 Harvard CS50 AI

Harvard'ın çalışması, course-specific araçları guardrail ve gerçek öğrenci
kullanımıyla değerlendirdiğini anlatır:
[Teaching CS50 with AI](https://cs.harvard.edu/malan/publications/V1fp0567-liu.pdf).

**Alınacak ders**:

- sistem prompt'u tek başına kalite kanıtı değildir,
- çok turlu öğrenci etkileşimi değerlendirilir,
- öğretmen/insan değerlendirmesi düzenli örneklemle yapılır,
- deneysel olduğu ve sınırları öğrenciye dürüstçe söylenir,
- akademik bütünlük guardrail'i ürün akışına gömülür.

**Kalite hedefi**: T047 benzeri insan eval döngüsü release sonrası rapor değil,
release öncesi kapıdır.

---

## 5. Platform admin tasarımı

### Karar R-005: Admin akademik superuser değildir

Adminin ihtiyacı:

- servis ve embedding hazırlığı,
- kaç kullanıcı/ders/aktif üyelik olduğu,
- güvenli kullanıcı dizininde hesap `id`, görünen ad ve maskeli e-posta,
- route/status/latency/token/cache gibi içeriksiz istek ölçümleri,
- ingestion kuyruğu ve başarısızlık durumu,
- support için request ID ve zaman aralığı.

Adminin ihtiyacı olmayan ve görmemesi gereken:

- öğrenci soru metni,
- model cevap metni,
- sohbet geçmişi,
- sınav cevabı,
- kaynak/chunk metni,
- tam e-posta listesi,
- token/access secret.

Kullanıcı dizinindeki arama `full_name` ve SQL tarafında üretilen maskelenmiş
e-posta ifadesi üzerinde çalışır. Tam e-posta araması eşleşmez. Listeleme
`POST /admin/users` ve JSON `{limit, offset, search}` gövdesi kullanır; böylece
arama değeri URL/query access loglarına taşınmaz.

### Karar R-006: Güvenli projeksiyon, sonradan redaction değil

`request_logs` şeması zaten serbest metin taşımaz. Admin fonksiyonları açık alan
listesiyle yalnız güvenli kolonları seçer. Request listesi kullanıcı UUID'sini,
e-postayı, hash/pseudonym'i veya kullanıcı diziniyle eşlenebilecek başka bir kimliği
hiç seçmez. Ayrı kullanıcı dizini destek amacıyla hesap `id` ve `full_name`
taşıyabilir; e-posta yine maskelidir. Bu kimlik alanları request/ingestion
telemetry'sine yayılmaz.

### Karar R-007: `platform_admins` RLS ENABLE, FORCE değil

Tabloda kullanıcı politikası yoktur. PUBLIC, `dou_app` ve `dou_worker` için bütün
tablo grant'leri geri alınır; normal uygulama bağlantısı tabloyu okuyamaz/yazamaz.
Yazma yalnız DBA/operatörde kalır. Aynı tablo sahibine ait dar `SECURITY DEFINER`
yardımcılar her çağrıda platform admin kontrolünü tekrarlar.

`FORCE ROW LEVEL SECURITY` uygulanmaz. Politikasız tabloda FORCE, tablo sahibi
yardımcıyı da kör eder ve güvenli admin kontrolünün çalışmasını engeller. Güvenlik
iddiası FORCE'a değil, kapalı grant'lere ve dar fonksiyon yüzeyine dayanır.

### Karar R-008: İlk dikey dilim salt okunur

Kullanıcı silme, admin verme, ders kapatma, job'ı zorla değiştirme gibi yıkıcı
işlemler admin UI'a eklenmez. İleride eklenecek her işlem ayrı audit tablosu,
reason alanı, idempotency ve çift onay tasarımı ister.

Platform admin **erişim kararı** için ise bu feature'da ayrı append-only
`platform_admin_access_audit` tablosu vardır. API dependency'si beş admin endpoint'i
için allowlist action, actor, `allowed|denied`, request ID ve zamanı ayrı tamamlanan
işlemde yazar. Böylece ana istek 403 ile bittiğinde reddedilen deneme rollback içinde
kaybolmaz. Tablo admin UI'da listelenmez ve uygulama/worker doğrudan okuyamaz.

---

## 6. Profil ve dashboard tasarımı

### Karar R-009: Profilin sahibi server

Header'daki ad ve admin linki `/me/profile` sonucundan gelir. LocalStorage yalnız
yerel oturum bootstrap'ı olabilir; rol veya adminlik kanıtı değildir.

Güncellenebilir tek alan `full_name`'dir. E-posta Supabase Auth kimliğidir; ders
rolleri üyelik tablolarıdır; platform adminliği DBA kontrollüdür.

### Karar R-010: Profil tek provider

AppShell, profil sayfası ve admin gate aynı profil yanıtını paylaşır. Aynı sayfada
iki `/me/profile` çağrısı Anayasa XI'e göre kusurdur. Cache kullanıcı değişiminde
temizlenir; eski kullanıcının admin durumu yeni kullanıcıya taşınmaz.

### Karar R-011: Dashboard tek aggregation endpoint'i

İstemci dersler, belgeler, sorular, blueprint ve sınav uçlarını ders başına çağırmaz.
Backend RLS bağlamında toplar ve role göre dar bir DTO döndürür.

Dashboard bir analitik veri ambarı değildir. İlk dilimde:

- eğitmen: belge durumları, taslak soru, yayınlanmış sınav ve aksiyon toplamı;
  blueprint için sayaç değil görünür araç bağlantısı,
- öğrenci: ders rolü ve gerçek çalışma girişleri; güvenli öz kayıtlar,
- herkes: ders kimliği ve çalışan linkler.

Ölçülmemiş “başarı yüzdesi”, “hazırlık skoru” veya “AI önerisi” üretilmez.

---

## 7. Teknik log ve gözlemlenebilirlik

### Repo bulgusu

`main.py` request ID, method, path, status ve duration loglar. Hata zarfı request ID
taşır. `request_logs` içeriksiz ürün metriği taşır. Bunlar iyi bir başlangıçtır;
ancak production trace/metric backend'i ve alarm kanıtı değildir.

### Karar R-012: Admin paneli log viewer değildir

Admin UI güvenli toplu operasyon görünümüdür. Ham log arama ve trace waterfall,
OpenTelemetry uyumlu ayrı gözlemlenebilirlik backend'inde yaşar.

OpenTelemetry; traces, metrics ve logs sinyallerini ilişkilendiren, vendor-neutral
bir çerçevedir: [OpenTelemetry signals](https://opentelemetry.io/docs/concepts/signals/).

### Telemetry allowlist

**Taşınabilir**:

- `request_id`, `trace_id`, `span_id`,
- service, environment, route template, method, status,
- duration, DB/retrieval/LLM aşama süreleri,
- provider/model alias, token count, cache hit,
- answer status, citation count, retrieval top-k,
- ingestion job status/attempt count,
- deploy version/commit.

**Taşınamaz**:

- prompt ve cevap metni,
- chunk veya belge metni,
- access/refresh token,
- tam e-posta,
- ham kullanıcı UUID'si,
- dosya içeriği.

Admin ingestion görünümü dosya adını da taşımaz. Operasyon için `document_id`,
`course_id`, `course_code`, durum, deneme sayısı ve zaman damgaları yeterlidir;
dosya adı ders materyali hakkında gereksiz akademik metaveri sızdırabilir.

Yüksek kardinaliteyi sınırlamak için kullanıcı kimliği metric label olmaz;
OpenTelemetry'nin cardinality uyarısı dikkate alınır:
[OTel metrics](https://opentelemetry.io/docs/concepts/signals/metrics/).

### Minimum alarm seti

- API 5xx oranı,
- readiness başarısızlığı,
- p95/p99 route latency,
- ingestion failed/pending yaşlanması,
- LLM provider hata/failover oranı,
- abstention ve out-of-scope dağılımındaki ani sapma,
- DB pool saturation,
- rate-limit artışı,
- telemetry export arızası.

Alarm eşikleri staging/load ölçümünden sonra yazılır; bu belgede sayı uydurulmaz.

---

## 8. LLM/RAG güvenliği

OWASP 2025, prompt injection'ın RAG ile tamamen çözülmediğini ve vector/embedding
zayıflıklarını ayrı risk olarak ele alır:

- [OWASP LLM01 Prompt Injection](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [OWASP LLM08 Vector and Embedding Weaknesses](https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/)

NIST AI 600-1, risk yönetimini tasarım, kullanım ve değerlendirme yaşam döngüsüne
yayar: [NIST AI 600-1](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence).

### Karar R-013: Güvenlik release gate'leri

- RLS mutasyon testi ve cross-course sızıntı testi.
- Doğrudan ve belge içine gömülü prompt injection fixture'ları.
- Retrieve edilmemiş citation'ın gösterilmediği test.
- Kaynak erişim izninin embedding/retrieval katmanında da uygulanması.
- LLM çıktısının kod/HTML/URL bağlamında güvenli render edilmesi.
- Soru üretimi ve chat için bounded rate/concurrency.
- Prompt/output telemetry yasağı.
- Bağımlılık, secret ve container taraması.

Admin görünümü bu kontrollerin sonucunu özetleyebilir; kontrolün kendisi değildir.

---

## 9. Production ve deployment kararı

Supabase'in resmi production checklist'i RLS, SSL enforcement, network restriction,
MFA, indeks/load test, backup ve gerektiğinde PITR'ı açıkça ister:
[Supabase Production Checklist](https://supabase.com/docs/guides/deployment/going-into-prod).

### Karar R-014: Üç ortam

- **local**: dev auth, fake LLM, yerel storage; hızlı ve deterministik.
- **staging**: gerçek Auth/Storage/LLM, anonim test verisi; migration/load/eval.
- **production**: yalnız onaylı migration, gerçek kullanıcı, alarm ve backup.

Aynı Supabase projesini test ve production için paylaşmak reddedilir.

### Production kapıları

1. Main CI yeşil ve migration preview geçti.
2. Production'da DEV_AUTH kapalı.
3. Auth e-posta onayı/SMTP ve issuer doğrulaması açık.
4. Storage bucket private ve RLS/policy testli.
5. DB SSL/network restriction/MFA uygulanmış.
6. Backup görünür; restore tatbikatı staging'de geçmiş.
7. Load testi hedef sınıf büyüklüğünde geçmiş.
8. OTel sinyalleri ve alarmlar gerçek hata enjeksiyonunda görülmüş.
9. Rollback adımı prova edilmiş.
10. Smoke test öğrenci/eğitmen/admin yolculuklarını kapsıyor.

Koşulmayan kapı “planlandı”dır, “hazır” değildir.

---

## 10. AI kalite ve insan değerlendirmesi

### Karar R-015: Beş ayrı kalite kümesi

| Küme | Örnek ölçüler | Neden ayrı |
|---|---|---|
| Retrieval | Recall@k, MRR/nDCG, doğru chunk erişimi | Model iyi yazsa da yanlış kanıt getirebilir |
| Grounding | Citation precision, claim support, unsupported claim | Citation sayısı doğruluk değildir |
| Scope/guardrail | in-scope recall, out-of-scope precision/recall, injection başarısı | Fazla ret de eksik ret kadar kötüdür |
| Pedagoji | doğrudan cevap kaçırma, ipucu kalitesi, sonraki adım yararı | Otomatik metrik tek başına öğretmen kalitesini ölçmez |
| Değerlendirme | rubric agreement, puan farkı, açıklama yararı | LLM grading akademik sonuç üretir |

### İnsan eval döngüsü

1. Ders materyalinden stratified örneklem.
2. En az iki bağımsız değerlendirici.
3. Kör rubric etiketleme.
4. Uyuşmazlık çözümü ve inter-rater ölçümü.
5. Prompt/policy değişiminden sonra regresyon karşılaştırması.
6. Çok turlu öğrenci oturumlarının ayrıca değerlendirilmesi.

Fake provider şema ve akışı kanıtlar; pedagojik kaliteyi kanıtlamaz. Gerçek LLM
anahtarı olmadan bu bölümün sonuçları `KOŞULMADI` kalır.

---

## 11. Karar özeti

| ID | Karar | Durum |
|---|---|---|
| R-001 | Modern stack korunur; rewrite yok | Kesin |
| R-002 | Kimlik, ders rolü, platform rolü ayrı | Kesin |
| R-003 | Tek role-aware dashboard | Kesin |
| R-004 | OBS bilgi ilkeleri alınır, ERP işlevleri alınmaz | Kesin |
| R-005 | Admin akademik superuser değildir | Kesin |
| R-006 | Güvenli SQL projeksiyonu, redaction değil | Kesin |
| R-007 | Admin tablosu RLS ENABLE, FORCE değil; grant yok | Kesin |
| R-008 | İlk admin dikey dilimi salt okunur | Kesin |
| R-009 | Profilin sahibi server | Kesin |
| R-010 | Profil tek provider | Kesin |
| R-011 | Dashboard tek aggregation endpoint'i | Kesin |
| R-012 | Admin paneli ham log viewer değil | Kesin |
| R-013 | LLM/RAG güvenlik gate'leri | Kesin |
| R-014 | Local/staging/production ayrımı | Kesin |
| R-015 | Otomatik + insan eval birlikte | Kesin |

---

## 12. Açık kararlar

- Production telemetry backend'i: vendor-neutral OTel korunarak hangi backend?
- Kurumsal SSO: Supabase email/password mı, üniversite OIDC/SAML köprüsü mü?
- Resmi dönem/duyuru/ofis saati verisi için kurum API'si var mı?
- Platform admin bootstrap ve iki kişi kuralı nasıl işletilecek?
- Kullanıcı feedback (`0013_chat_feedback.sql`) hangi kalite kuyruğuna bağlanacak?
- Retention süreleri ve KVKK hukuki onayı kim tarafından verilecek?

Bu kararlar bulunmadan kodun geri kalanı durmaz; yalnız bağımlı production görevleri
`KOŞULMADI` kalır.
