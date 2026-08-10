# DOU-Synapse: Uçtan Uca Ürün ve Production Yol Haritası

**Plan dalı**: `003-product-portal`
**Taban**: `b8da84e` (`002-production-hardening`)
**Tarih**: 2026-08-10
**Ufuk**: 6–8 haftalık ürünleştirme dalgaları
**Durum kuralı**: Kodlandı ≠ yerelde doğrulandı ≠ staging'de doğrulandı ≠ production'da kanıtlandı

---

## 1. Net karar

DOU-Synapse'i başka bir dile veya “HTML/CSS/React” adıyla yeni bir uygulamaya
yeniden yazmayacağız. Proje zaten modern ve birbirine uyumlu bir full-stack yığında:

- Next.js 16.3 + React 19.2 + TypeScript 5 + Tailwind CSS 4,
- FastAPI + Python 3.12 + SQLAlchemy async,
- PostgreSQL 16 + pgvector + RLS,
- Supabase Auth/Storage hedefi,
- LiteLLM sağlayıcı katmanı ve hibrit RAG.

React zaten HTML üretir, Tailwind CSS katmanıdır; Next.js routing, layout, server
rendering ve production build sağlar. Ürün kalitesini artıracak yatırım yeniden
yazım değil, mevcut yetenekleri kullanıcı yolculuğuna bağlamak, gerçek servislerle
kanıtlamak ve operasyon/eval kapılarını tamamlamaktır.

Hedef “çalışan chatbot” değil; öğrencinin tekrar tekrar kullanacağı, eğitmenin
kapsam ve sınavı yönettiği, operatörün akademik mahremiyeti bozmadan işlettiği
**ders odaklı öğrenme ürünü**dür.

---

## 2. Bugünkü doğruluk tablosu

Bu tablo feature dalındaki gözlemi anlatır; canlı ortam iddiası değildir.

| Alan | Kodlandı | Yerelde doğrulandı | Production'da kanıtlandı | Açık kanıt |
|---|---:|---:|---:|---|
| PDF/Markdown/kod ingestion | 002 tabanında var | Bu feature'da yeniden ölçülmedi | Hayır | Gerçek Storage + worker smoke |
| Kaynak sınırlı hibrit RAG | 002 tabanında var | Bu feature'da yeniden ölçülmedi | Hayır | Gerçek sağlayıcı faithfulness |
| Citation ve kaynak bağlamı | 002 tabanında var | Bu feature'da yeniden ölçülmedi | Hayır | Citation precision + deep-link E2E |
| Sokratik/sınav modları | 002 tabanında var | Bu feature'da yeniden ölçülmedi | Hayır | İnsan pedagojik eval |
| Sınav kilidi | 002 tabanında var | Önceki dal kanıtı var; entegrasyon commit'i yeniden koşulmalı | Hayır | Production iki sekme E2E |
| Sınav blueprint'i | 002 tabanında var | Entegrasyon sonrası yeniden koşulmalı | Hayır | Gerçek öğretmen yayın akışı |
| Ders AI politikası | 002 tabanında var | Entegrasyon sonrası yeniden koşulmalı | Hayır | Gerçek bütçe/provider davranışı |
| Kaynak kalite laboratuvarı | Entegrasyona gelecek kod var | Bu dalda kanıt yok | Hayır | Retrieval test + öğretmen gözlemi |
| Profil/dashboard/admin portalı | Bu çalışma ağacında var | Tam kapı sonucu bekliyor | Hayır | API/RLS/build/tarayıcı |
| Gerçek Supabase Auth/Storage | Hedef mimaride var | KOŞULMADI | Hayır | Staging smoke |
| OpenTelemetry + alarm | Tasarım var | KOŞULMADI | Hayır | Export, dashboard, tetiklenen alarm |
| Load ve backup/restore | Plan var | KOŞULMADI | Hayır | Ölçüm ve restore tatbikatı |
| Gerçek LLM + insan eval | Eval altyapısı kısmi | KOŞULMADI | Hayır | Holdout + öğretmen/öğrenci çalışma |
| Doğrulanmış canlı URL | Yok | Uygulanamaz | Hayır | Deploy SHA + smoke kaydı |

Portal dosyalarının varlığı yalnız **kodlandı** statüsüdür. 003'ün hedefli test,
RLS mutasyonu, gerçek HTTP, production build ve tarayıcı kapıları tamamlanmadan
“yerelde doğrulandı” sütunu değiştirilmez.

---

## 3. Hoca gereksinim matrisi

| Hoca gereksinimi | Ürün karşılığı | Mevcut durum | Bu yol haritasındaki kapanış kanıtı |
|---|---|---|---|
| Eğitmen PDF, Markdown ve kod yükler | Kaynaklar + ingestion worker + kaynak sağlığı | Kod var | Gerçek Storage upload → parsed chunks → ready |
| Sistem yalnız yüklenen kaynaklardan cevap verir | Hibrit retrieval, evidence eşiği, abstention | Kod var | Kaynak dışı/eksik bağlam holdout'u |
| Eğitmen pedagojik modu belirler | Ders AI politikası: normal/Sokratik/sınav | Kod var | Policy değişimi API + UI + gerçek LLM davranışı |
| AI soru havuzu üretir | Taslak üretim, öğretmen düzenleme/onay | Kod var | Gerçek sağlayıcı kabul oranı ve DRAFT zorlaması |
| Öğrenci interaktif soru çözer | Çalışma/sınav akışları | Kod var | Çok turlu öğrenci E2E ve insan değerlendirmesi |
| “Neden yanlış?” analizi | Citation + rubric kriteri + çelişen kaynak | Kısmi | Açık uçlu/kod/rubric kalite seti |
| Kod/senaryo inceleme | Kod sorusu ve değerlendirme tipi | Kod var | Güvenli örnek set ve deterministic rubric |
| Müfredat dışı istek reddi | Scope gate + abstention | Kod var | Türkçe paraphrase/adversarial holdout ≥ kabul eşiği |
| Her yanıtta kaynak | Citation nesneleri + source context | Kod var | Claim support ve yanlış citation testi |
| Süreli sınav, yardım yok | Exam session + server-side chat lock | Kod var | API, iki sekme ve mutasyon testi |
| Çalışan web platformu | Rol bazlı portal + ders içi araçlar | Portal kodu çalışma ağacında | Staging ve production üç rol smoke |
| Örnek materyal ve başarı raporu | Demo course + eval raporu | Kısmi | Sürüm sabitli paket ve tekrarlanabilir rapor |
| Öğrenci/eğitmen kılavuzu | Rol bazlı dokümanlar ve demo | Kısmi | Güncel ekranlar, runbook ve prova videosu |

### Sınav çatısı değişmez öncelik

AI doğrudan “10 soru üret” komutuyla yayın yapmamalıdır. Akış:

```text
Öğrenme çıktıları + kaynak sürümleri + konu/zorluk/tür dağılımı
  → versioned blueprint
  → AI yalnız DRAFT soru önerir
  → öğretmen düzenler ve onaylar
  → immutable published exam version
  → süreli öğrenci session'ı
  → rubric bazlı değerlendirme ve kaynaklı geri bildirim
```

Blueprint aracı portalda görünür bir eğitmen girişidir. Dashboard sözleşmesi taslak
blueprint sayısı taşımadığı için arayüz böyle bir sayaç uydurmaz. Gerçek sayaçlar
yalnız `documents_processing`, `documents_failed`, `draft_questions` ve
`published_exams` alanlarıdır.

---

## 4. Ürün bilgi mimarisi

### 4.1 Ortak çatı

- Giriş sonrası `/dashboard`.
- Global üst çubuk: Dashboard, Profil, dersler, gerekiyorsa Admin, çıkış.
- Ders içinde mevcut yatay navigasyon: Genel Bakış, Kaynaklar, Asistan, Sorular,
  Sınavlar, Blueprint, AI Politikası, Analitik.
- Rol ve yetki her zaman sunucudan; localStorage yalnız bootstrap kolaylığı olabilir.
- Aynı kişi farklı derslerde farklı rol taşıyabilir; global “öğrenci/eğitmen” seçici yoktur.

### 4.2 Öğrenci paneli

Öğrencinin ilk ekranda cevap bulması gereken sorular:

1. Hangi derslerim var?
2. Kaldığım yer neresi?
3. Şimdi çalışabilir miyim, yoksa materyal/sınav durumu engel mi?
4. Yaklaşan veya devam eden sınavım var mı?
5. Hangi konuda tekrar yapmalıyım?

Panel öğeleri:

- aktif ders kartları ve ders bazlı rol,
- Asistan / Sınav / İlerleme hızlı girişleri,
- yalnız kendi mastery/aktivite özeti,
- devam eden sınavda server-derived kilit açıklaması,
- gerçek veriye dayalı boş/loading/error/partial durumları.

Sahte “hazırlık skoru”, resmi GPA, danışman, program veya dönem bilgisi yoktur.

### 4.3 Eğitmen paneli

Tek chatbot yerine görünür araçlar:

- ingestion sağlığı ve başarısız/işlenen belge kuyruğu,
- kaynaklar ve retrieval laboratuvarı,
- AI soru üretme ve taslak soru onayı,
- sınav blueprint'i ve yayınlanmış sürümler,
- ders bazlı AI pedagojisi/provider/bütçe politikası,
- sınıf ilerleme ve kalite özeti,
- eval/feedback inceleme girişi.

Öğretmen dashboard'unda aksiyon toplamı açıklanabilir olmalıdır:

```text
action_items = documents_processing + documents_failed + draft_questions
```

### 4.4 Profil ve veri hakları

- Kendi adı, tam e-postası ve hesap oluşturma zamanı.
- Her dersin kodu, adı ve o dersteki rol.
- Değiştirilebilir tek profil alanı `full_name`.
- E-posta kimlik sağlayıcısına, ders rolü üyeliğe, adminlik DBA'ya aittir.
- Mevcut `/account` indirme, sohbet silme ve anonimleştirme akışlarına giriş.
- Profil verisi AppShell ve gate'lerle tek context üzerinden paylaşılır.

### 4.5 Bilgi İşlem / platform yönetimi paneli

Bilgi İşlem paneli öğretmen paneli, akademik superuser veya ham log ekranı değildir.
DBA tarafından atanan platform yöneticilerine açık, salt okunur operasyon konsoludur:

- uygulama, DB ve embedding hazırlığı,
- kullanıcı/ders/belge ve son 24 saat başarılı sohbet turu özeti,
- maskeli e-postalı güvenli kullanıcı dizini,
- ders operasyon dizini,
- route/status/latency/token/cache request ölçümleri,
- document/course kimlikli ingestion durumu ve deneme zamanları.

Gizlilik sınırı:

- Kullanıcı araması `full_name` veya SQL tarafında üretilen maskelenmiş e-posta
  ifadesiyle eşleşir. Tam e-posta araması eşleşmez; `POST /admin/users` JSON
  gövdesi kullanıldığı için arama değeri URL/access log query'sine girmez.
  Placeholder **“Ad veya maskeli e-posta”**dır.
- Request listesinde prompt, cevap, citation metni, kullanıcı UUID/e-posta/hash/
  pseudonym'i veya kullanıcı diziniyle eşlenebilecek başka bir alan yoktur.
- Ingestion listesinde `file_name`, path, `last_error`, belge/chunk metni yoktur.
- Admin üyelik olmadan ders içeriğini, öğrenci sohbetini veya sınav cevabını göremez.
- İlk dikey dilimde kullanıcı silme, rol verme, ders kapatma veya job değiştirme yoktur.

---

## 5. OBS'den alınacak ve alınmayacaklar

OBS bir stil şablonu değil, işe dönük bilgi mimarisi referansıdır.

### Alınacak

- girişte role göre doğru iş alanına yönlenme,
- güncel ders/çalışma bağlamının özetlenmesi,
- önemli durumların kartlarla öne çıkması,
- görevlerin kategori halinde düzenlenmesi,
- profil ve bildirimlerin görünür ama ikincil olması,
- yazdırma yerine DOU için paylaşılabilir sonuç/eval raporu.

### Alınmayacak

- sabit ve yoğun koyu sidebar,
- resmi transkript, not, AGNO/GPA, öğrenci numarası, kayıt, staj veya başvuru işlemleri,
- kaynağı olmayan dönem, danışman, duyuru ve ders programı,
- masaüstü tablosunu mobilde yalnız küçülten eski düzen,
- aynı verinin menü, kart ve sayfada gereksiz tekrarı.

Gelecekte OBS/SIS entegrasyonu istenirse ayrı veri sahipliği, izin, senkronizasyon,
KVKK ve hata sözleşmesi gerekir; UI'ya sahte alan koyarak başlanmaz.

---

## 6. Benzer ürün kalitesine ulaşma eşlemesi

### Khanmigo — öğretmen araçları

Khanmigo, öğretmeni tek sohbet kutusuna sıkıştırmaz; ders planı, rubric,
değerlendirme ve sınıf özeti gibi ayrı araçlar sunar.
[Resmi Khanmigo teacher tools](https://support.khanacademy.org/hc/en-us/articles/14799047733645-What-teacher-tools-are-available-on-Khanmigo-)

DOU-Synapse karşılığı:

- portalda ayrı Kaynaklar, Sorular, Blueprint, AI Politikası, Analitik araçları,
- öğretmen aksiyon kuyruğu,
- rubric kriter kırılımı ve soru kabul/red nedeni,
- sınıf özeti ile bireysel öğrenci mahremiyeti arasında net sınır.

Kalite kanıtı: öğretmen bir sınavı kaynaktan blueprint'e, taslaktan onaya ve
yayına kadar dış yardım olmadan tamamlayabilmelidir.

### NotebookLM — citation ve kaynak kontrolü

NotebookLM citation seçildiğinde özgün kaynak bağlamına götürür ve kullanılacak
kaynakların seçilmesine izin verir.
[Resmi NotebookLM citation açıklaması](https://support.google.com/notebooklm/answer/16179559?hl=en)

DOU-Synapse karşılığı:

- citation → sayfa/slide/line ve komşu chunk deep-link,
- kaynak passage + özgün konum + sürüm birlikte,
- eğitmen AI politikasında kaynak allowlist'i,
- yanlış/eski kaynak sürümü uyarısı,
- citation precision ve claim support eval'i.

### Moodle AI — placement/action/provider ayrımı

Moodle AI subsystem; AI'ın nerede göründüğünü, hangi eylemi yaptığını ve hangi
sağlayıcının kullandığını ayırır.
[Resmi Moodle AI subsystem](https://moodledev.io/docs/5.1/apis/subsystems/ai)

DOU-Synapse karşılığı:

- placement: öğrenci chat, sınav, soru üretici, grading, kaynak laboratuvarı,
- action: grounded answer, Sokratik ipucu, soru üretme, puanlama,
- provider: fake yalnız test için; Groq/Gemini production için,
- policy: ders bazında açık/kapalı, model, bütçe, kanıt ve ret eşiği.

Yeni bir plugin sistemi yazmak yerine mevcut `LlmTask` ve ders AI politikasını
bu kavramlarla görünür ve ölçülebilir kılarız.

### RAGFlow — chunk ve retrieval laboratuvarı

RAGFlow chunk görünürlüğünü ve retrieval testing akışını ürün özelliği yapar.
[Resmi RAGFlow quickstart](https://github.com/infiniflow/ragflow/blob/main/docs/quickstart.mdx)

DOU-Synapse karşılığı:

- parsing/embedding durumu ve chunk sayısı,
- chunk + komşu bağlam + provenance önizleme,
- öğretmenin örnek sorguyla top-k sonuç/score testi,
- düşük kaliteli retrieval'a feedback,
- kaynak sürümü değiştiğinde yeniden embedding görünürlüğü.

Chunk metni doğrudan düzenleme provenance/sürümleme tasarlanmadan açılmaz.

### Harvard CS50 — insan değerlendirmesi

CS50 çalışması course-specific AI'ı gerçek öğrenci kullanımı ve guardrail'lerle
değerlendirir.
[Teaching CS50 with AI](https://cs.harvard.edu/malan/publications/V1fp0567-liu.pdf)

DOU-Synapse karşılığı:

- tek turlu prompt testi yerine çok turlu öğrenme senaryosu,
- eğitmen rubric'iyle örneklem değerlendirmesi,
- yanlış yönlendirme, fazla doğrudan cevap ve akademik bütünlük ölçümü,
- model/provider değişiminde regresyon eval'i,
- öğrenciye sistemin deneysel sınırlarını açık söyleme.

---

## 7. Uyumlu hedef mimari

```text
Vercel / Next.js Web
  ├── rol bazlı portal, profil, admin
  ├── ders içi öğrenme/sınav araçları
  └── Supabase Auth oturumu
                 │ HTTPS + JWT
                 ▼
Azure Container Apps / FastAPI API
  ├── profile + dashboard + admin projection
  ├── course/chat/questions/exams/blueprints/policies
  ├── RAG orchestration + guardrails
  ├── rate limit / timeout / request ID
  └── OpenTelemetry instrumentation
                 │
       ┌─────────┴─────────┐
       ▼                   ▼
Supabase PostgreSQL     ACA ingestion worker
  ├── RLS + pgvector       ├── Storage fetch
  ├── versioned sources    ├── parse/chunk/embed
  ├── exam snapshots       └── retry/DLQ state
  └── admin projections
       │                   │
       └──── Supabase Storage

External model providers
  └── LiteLLM policy → Groq/Gemini failover

Observability backend
  └── content-free traces + metrics + logs + alerts
```

### Neden bu parçalar uyumlu?

- TypeScript istemci, OpenAPI/Pydantic sözleşmesine bağlanır.
- FastAPI, Python RAG/parsing/eval ekosistemini korur.
- PostgreSQL hem ilişkisel sınav verisini hem pgvector retrieval'ı tek RLS sınırında tutar.
- Supabase Auth kimlik, Storage dosya; uygulama katmanı ders kurallarını yönetir.
- LiteLLM sağlayıcı değişimini ders politikasından ayırır.
- Vercel/ACA ayrımı web ile uzun süren ingestion/API süreçlerinin ölçeklenmesini ayırır.
- OpenTelemetry vendor bağımlılığı olmadan sinyalleri ilişkilendirir.

Mikroservis, Kubernetes, ikinci vektör DB, LangChain/LlamaIndex veya GraphRAG ancak
ölçülmüş bir sınır ortaya çıktığında gündeme gelir.

---

## 8. Güvenlik ve gözlemlenebilirlik omurgası

### Platform admin güvenliği

`platform_admins`:

- `0014_platform_admin_console.sql` ile gelir,
- RLS ENABLE, bilinçli olarak FORCE değildir,
- kullanıcı politikası yoktur,
- PUBLIC/`dou_app`/`dou_worker` bütün tablo grant'leri geri alınır,
- yazma yalnız DBA/operatördedir,
- dar `SECURITY DEFINER` fonksiyonları her çağrıda adminliği tekrar doğrular.

`platform_admin_access_audit` da RLS ENABLE/kapalı grant tasarımını kullanır. API
dependency'si beş admin endpoint'ine allowed ve denied erişim kararlarını allowlist
action, actor, request ID ve zamanla ayrı tamamlanan işlemde yazar; 403 ana isteği
denied satırını rollback etmez. Audit tablosu admin UI'da listelenmez.

FORCE kullanılmamasının nedeni güvenlikten vazgeçmek değil, politikasız tabloda
owner helper'ının kör edilmesini önlemektir. Güvenlik doğrudan grant/mutasyon testiyle kanıtlanır.

### LLM/RAG güvenliği

OWASP prompt injection'ın RAG ile ortadan kalkmadığını; vector/embedding zayıflıklarının
ayrı risk olduğunu vurgular.
[OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
[OWASP LLM08:2025 Vector and Embedding Weaknesses](https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/)

NIST AI 600-1 riskleri tasarım, kullanım, ölçüm ve yönetişim boyunca ele alır.
[NIST AI RMF Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)

Ürün kapıları:

- kaynak ve chunk'lar güvenilmeyen veri kabul edilir,
- retrieval metni system instruction değildir,
- dosya türü/boyutu/MIME doğrulaması,
- source/course sınırı hem uygulama hem RLS,
- dış kapsam, prompt injection ve veri sızdırma eval seti,
- sınav sırasında bütün yardım yan yolları server-side kapalı,
- provider timeout/retry/failover bütçesi,
- üretim secret'ları UI/log/trace'e girmez.

### Gözlemlenebilirlik

Admin paneli ham log viewer değildir. Telemetry allowlist'i:

- request/trace/span ID,
- servis, ortam, deploy commit, route template, method/status,
- API/DB/retrieval/LLM aşama süreleri,
- model alias, token count, cache hit, answer status, citation count,
- ingestion durum/attempt ve queue age.

Prompt, cevap, chunk, belge içeriği, access/refresh token, tam e-posta, ham kullanıcı UUID'si ve
dosya adı telemetry'ye yazılmaz. Alarm eşikleri staging/load ölçümünden sonra konur;
bu plan sayı uydurmaz.

---

## 9. 6–8 haftalık uygulama dalgaları

Hafta numaraları sabit takvim değil, sıraya bağlı kapılardır. Bir haftanın çıkış
kanıtı eksikse sonraki dalgaya “bitti” etiketiyle taşınmaz.

### Hafta 1 — Portal entegrasyonu ve sözleşme doğruluğu

**Amaç**: 003'ün profil, dashboard ve salt okunur admin dikey dilimini güvenle birleştirmek.

- `0014` migration, çift admin kontrolü ve allowed/denied erişim audit'i,
- profil/dashboard/admin API'leri,
- öğrenci/eğitmen/admin UI,
- karma rol ve blueprint session düzeltmesi,
- OpenAPI/Pydantic/TypeScript eşleme,
- hedefli test, RLS mutasyon, build, 375 px ve tarayıcı ağ kontrolü.

**Çıkış**: Faz 0–6 [tasks.md](tasks.md) kapalı; gerçek HTTP ile üç rol yolculuğu.

### Hafta 2 — Gerçek kimlik, depolama ve demo bütünlüğü

**Amaç**: Yerel dev kartlarından staging kimliğine geçmek.

- gerçek Supabase Auth giriş/çıkış/token yenileme,
- production'da `dev:` yasağı,
- gerçek Storage upload/download/signed URL,
- worker job ve retry görünürlüğü,
- demo seed'inin idempotent/run-scoped temizliği,
- öğrenci/eğitmen/platform admin hesap matrisi.

**Çıkış**: Staging'de login → upload → processed source → grounded query smoke.

### Hafta 3 — Eğitmen ürün derinliği

**Amaç**: Khanmigo/RAGFlow seviyesinde öğretmen işi görünür kılmak.

- kaynak laboratuvarı ve retrieval test UX,
- chunk + komşu bağlam + sürüm görünürlüğü,
- soru taslağı kabul/red/düzenleme ergonomisi,
- blueprint kapsam/çıktı/zorluk/tür dağılımı özeti,
- ders AI politika ekranının placement/action/provider diline bağlanması,
- rubric kriter kırılımı ve öğretmen notu.

**Çıkış**: Eğitmen tek oturumda kaynak yükler, retrieval'ı test eder, blueprint
kurar, taslak üretir, düzenler, onaylar ve sınav yayınlar.

### Hafta 4 — Öğrenci öğrenme döngüsü

**Amaç**: Öğrencinin platformda zaman harcamasını değerli ve ölçülebilir yapmak.

- “çalışmaya devam et” ve konu tekrar girişleri,
- Sokratik aşama görünürlüğü,
- “Neden yanlış?” için kaynak pasajı + rubric kriteri,
- açık uçlu/kod sorularında yapılandırılmış geri bildirim,
- sınav sonrası güçlü/zayıf konu özeti,
- erişilebilir mobil çalışma/sınav UX,
- streak/rozet yerine gerçek mastery ve tekrar önerisi.

**Çıkış**: Çok turlu öğrenci senaryosunda sistem cevabı ele vermeden yönlendirir,
yanlışın kaynağını gösterir ve bir sonraki anlamlı adıma götürür.

### Hafta 5 — Operasyon, güvenlik ve gözlemlenebilirlik

**Amaç**: Sistemin sorununu kullanıcıdan önce görebilmek.

- OpenTelemetry API/worker instrumentation,
- güvenli log/metric/trace allowlist testleri,
- ingestion aging, provider failover, 5xx, latency ve DB pool dashboard'ları,
- alarm teslimat deneyi ve runbook,
- admin erişim audit tasarımı,
- OWASP prompt injection/vector test paketi,
- dependency/secret/container taraması.

**Çıkış**: Kontrollü bir arıza trace/request ID ile bulunur; alarm tetiklenir;
telemetry örneğinde kullanıcı içeriği bulunmaz.

### Hafta 6 — Gerçek LLM ve insan kalite kapısı

**Amaç**: Fake provider ile değil, gerçek pedagojik sonuçla karar vermek.

- gerçek Groq/Gemini holdout koşuları,
- citation precision, claim support, retrieval recall,
- kapsam dışı ret ve prompt injection dayanımı,
- soru kalite/öğretmen kabul oranı,
- grading-rubric uyumu,
- çok turlu öğrenci/öğretmen insan eval'i,
- hata kümelemesi ve düzeltme → yeniden ölçüm döngüsü.

**Çıkış**: Sürüm, dataset ve model damgalı tekrar üretilebilir eval raporu; kritik
senaryolarda kabul eşiği geçilmezse release durur.

### Hafta 7 — Staging, yük ve kurtarma

**Amaç**: Tek kullanıcılı demodan güvenilir servise geçmek.

- Vercel + ACA + Supabase staging,
- concurrency/load/soak testi,
- API, retrieval ve LLM p95/p99 ölçümü,
- rate limit/concurrency/budget davranışı,
- backup/PITR ve gerçek restore tatbikatı,
- migration ve rollback provası,
- ağ kısıtı, SSL, MFA, secret rotation kontrolü.

**Çıkış**: Yük raporu, restore kaydı, rollback süresi, alarm kanıtı ve kalan kapasite riski.

### Hafta 8 — Production pilot ve jüri paketi

**Amaç**: Kontrollü gerçek kullanıcı pilotu ve dürüst teslim.

- küçük ders/kullanıcı cohort'u,
- production smoke: öğrenci, eğitmen, admin,
- support/runbook ve sorumluluk matrisi,
- kullanıcı/eğitmen kılavuzları,
- güncel mimari, threat model, veri akışı,
- örnek ders materyali + sürümlü başarı raporu,
- ekran görüntüsü ve demo videosunun gerçek release commit'ine bağlanması,
- incident/rollback ve pilot geri bildirim planı.

**Çıkış**: Canlı URL, deploy SHA, production smoke, backup/restore, alarm ve eval
kanıtları tek release sayfasında.

### Altı haftaya sıkışırsa

- Hafta 1 ve 2 birleşir.
- Hafta 3 ve 4 ayrı kalır; bunlar ürün değeridir.
- Hafta 5 ve 7 güvenlik/operasyon olarak birleşir.
- Hafta 6 kalite kapısı kalır.
- Hafta 8'in yalnız pilot, kılavuz ve demo kısmı son haftaya alınır.

Kesilmeyecekler: sınav kilidi, RLS, gerçek Auth/Storage, citation/eval, backup/restore,
admin gizlilik sınırı ve production smoke. Kesilebilecekler: gelişmiş rozetler,
özelleştirilebilir dashboard, resmi OBS/SIS entegrasyonu ve yıkıcı admin aksiyonları.

---

## 10. Release kapıları

### Gate A — Fonksiyonellik

- Öğrenci/eğitmen/karma rol/admin/admin olmayan yolculukları.
- Upload → parse → chunk → retrieve → answer → citation zinciri.
- Blueprint → draft → approval → published exam → timed session → result.
- Sınavda sohbetin bütün mod ve yan yollardan server-side kapanması.
- Profil ve KVKK akışları.

### Gate B — Güvenlik ve gizlilik

- Uygulama ve RLS izolasyonu ayrı ayrı testli ve mutasyonla kırılabilir.
- `platform_admins`: RLS ENABLE, FORCE değil; grant yok; DBA-only write.
- Admin endpoint allowed/denied kararları ayrı işlemde audit edilir; uygulamanın
  audit tablosuna doğrudan grant'i veya okuma endpoint'i yoktur.
- Platform admin akademik superuser değildir.
- Request/ingestion projeksiyonlarında serbest metin/PII yok.
- Tam e-posta araması eşleşmez; maskeli e-posta araması çalışır.
- Kullanıcı araması yalnız `POST /admin/users` gövdesindedir; URL/query'de PII
  veya başka arama metni taşınmaz.
- Dev auth production'da kapalı; secret ve güvenlik header testleri yeşil.
- OWASP prompt injection/vector test seti geçer.

### Gate C — AI/RAG kalitesi

- Kaynak dışı cevapta abstention.
- Citation claim'i gerçekten destekler.
- Retrieval doğru kaynak sürümünden doğru chunk'ı bulur.
- Sokratik mod cevabı erken ele vermez.
- Soru ve grading öğretmen rubric'ine yeterli uyum gösterir.
- Fake provider ölçümü gerçek sağlayıcı sonucu olarak raporlanmaz.

Eşikler eval protokolünde örneklem ve hata maliyetiyle sabitlenir; bu roadmap
ölçülmeden yüzde uydurmaz.

### Gate D — Performans ve güvenilirlik

- API/event loop ingestion ve embedding sırasında yanıt verebilir.
- p95/p99, hata oranı ve throughput staging yükünde ölçülür.
- Timeout/retry/failover bütçesi bounded'dır.
- Rate limit ve token/course bütçesi fail-closed çalışır.
- Readiness, liveness ve worker health ayrıdır.

### Gate E — Operasyon ve kurtarma

- Log/metric/trace export'u ve alarm teslimatı kanıtlı.
- Dashboard deploy commit/environment taşır.
- Backup açık olmakla kalmaz, restore edilmiş veriyle tatbikat yapılır.
- Migration/rollback provası ve runbook vardır.
- Incident owner ve destek yolu bellidir.

### Gate F — UX, erişilebilirlik ve belge

- 375 px, masaüstü, koyu tema, klavye, görünür odak.
- Loading/empty/partial/error ayrı.
- Çalışmayan kontrol ve sahte veri yok.
- Aynı veri iki kez çekilmiyor; ağ kaydı incelenmiş.
- README, mimari, OpenAPI, kılavuz, ekran görüntüsü ve test metrikleri aynı release'i anlatır.
- `docs_check` ve production build yeşil.

---

## 11. Production altyapı kontrol listesi

Supabase resmi checklist'i RLS, SSL, network restriction, load ve backup/PITR gibi
kontrolleri ister:
[Supabase production checklist](https://supabase.com/docs/guides/deployment/going-into-prod).

Next.js resmi checklist'i production build, environment, güvenlik, caching ve
performans kontrollerini toplar:
[Next.js production checklist](https://nextjs.org/docs/app/guides/production-checklist).

Production öncesi kayıt:

- [ ] Web deploy URL + commit SHA
- [ ] API/worker image digest + commit SHA
- [ ] Migration manifest (`0013` sonra `0014`)
- [ ] Auth redirect/cookie/CORS allowlist
- [ ] Storage bucket policy ve signed URL süresi
- [ ] RLS/grant/mutasyon raporu
- [ ] Secret store ve rotation tarihi
- [ ] TLS/SSL ve network restriction
- [ ] Load/soak sonucu
- [ ] Backup/PITR + restore tatbikatı
- [ ] OTel dashboard + gerçek alarm teslimatı
- [ ] Gerçek LLM eval raporu
- [ ] İnsan eval raporu
- [ ] Üç rol production smoke
- [ ] Rollback komutu/runbook ve sorumlu kişi

Her kutu ekran görüntüsüne değil, tekrarlanabilir komut/rapor/trace veya gerçek
URL kanıtına bağlanmalıdır.

---

## 12. Başarı ölçümü

### Öğrenme kalitesi

- citation precision ve claim support,
- retrieval recall@k,
- doğru abstention ve kapsam dışı ret,
- Sokratik “cevabı erken verme” ihlal oranı,
- grading/rubric uyumu,
- öğretmen soru kabul/düzenleme/red dağılımı,
- öğrenci çok turlu görevi tamamlayabilme.

### Ürün kullanımı

- dashboard → anlamlı ders aksiyonu dönüşümü,
- ilk kaynak yüklemeden ilk grounded cevaba süre,
- blueprint'ten yayınlanmış sınava tamamlama,
- hata/boş durumdan kurtulma,
- tekrar gelen öğrenci ve tamamlanan çalışma oturumu,
- terk edilen veya süresi dolmuş sınav oturumu.

### Operasyon

- API/DB/retrieval/LLM p50/p95/p99,
- 4xx/5xx ve provider failover,
- ingestion queue age/failure/retry,
- DB pool ve worker saturation,
- cost/token per course/action,
- alarm detection/acknowledgement/restore süresi.

Metrikler user ID veya akademik içerik label'ı taşımaz. Eşikler baseline/load/human
eval sonrasında karar kaydına yazılır.

---

## 13. Öncelik ve ürün kesme çizgisi

### P0 — Production release öncesi zorunlu

1. 003 portal entegrasyonu ve karma rol doğruluğu.
2. Gerçek Auth/Storage.
3. Sınav blueprint/onay/immutable yayın ve yardım kilidi.
4. Kaynak/citation doğruluğu ve kapsam dışı guardrail.
5. Admin gizlilik/RLS/grant sınırı.
6. OTel alarm, load, backup/restore.
7. Gerçek sağlayıcı ve insan eval.
8. Güncel kılavuz, demo ve production smoke.

### P1 — Pilot kalitesini yükseltir

- retrieval laboratuvarı UX ve feedback,
- rubric kriter kırılımı,
- öğrenci tekrar/yanlış analizi,
- öğretmen sınıf kalite özeti,
- model/provider maliyet ve bütçe görünürlüğü.

### P2 — Ölçümden sonra

- resmi OBS/SIS/LMS entegrasyonu,
- dönem/danışman/ofis saati/duyuru,
- yıkıcı admin işlemleri ve çift onay,
- keyset admin pagination,
- ayrı analytics warehouse,
- gelişmiş gamification veya kişiselleştirilmiş bildirim.

P2 işleri P0'ı geciktirmemeli; veri kaynağı ve sahipliği olmadan UI kabuğu olarak
eklenmemelidir.

---

## 14. Resmi kaynaklar

- [Khanmigo öğretmen araçları](https://support.khanacademy.org/hc/en-us/articles/14799047733645-What-teacher-tools-are-available-on-Khanmigo-)
- [NotebookLM citations](https://support.google.com/notebooklm/answer/16179559?hl=en)
- [Moodle AI subsystem](https://moodledev.io/docs/5.1/apis/subsystems/ai)
- [RAGFlow quickstart ve retrieval test](https://github.com/infiniflow/ragflow/blob/main/docs/quickstart.mdx)
- [Harvard CS50 AI çalışması](https://cs.harvard.edu/malan/publications/V1fp0567-liu.pdf)
- [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [OWASP LLM08:2025 Vector and Embedding Weaknesses](https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/)
- [NIST AI 600-1](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence)
- [Supabase production checklist](https://supabase.com/docs/guides/deployment/going-into-prod)
- [Next.js production checklist](https://nextjs.org/docs/app/guides/production-checklist)
- [OpenTelemetry signals](https://opentelemetry.io/docs/concepts/signals/)

Bu kaynaklar tasarım yönü verir; DOU-Synapse'in kalite iddiası yalnız kendi
release commit'i, test/eval seti, gerçek servis ölçümü ve kullanıcı kanıtıyla kurulur.
