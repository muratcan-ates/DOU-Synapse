# Araştırma ve Tasarım Kararları: 005 Rol Farkındalıklı Ders Ajanı

**Tarih**: 2026-08-11
**Base**: `7c1c219`
**Kanıt türü**: Repo/kod incelemesi ve tasarım; canlı provider/production kanıtı değildir

## 1. Mevcut sistemde gerçekten ne var?

Repo incelemesi, yeni bir genel chatbot backend'i yazmanın gereksiz olduğunu
gösterdi. Mevcut sistem zaten:

- `POST /courses/{course_id}/chat` ve session/message geçmişi;
- `CourseMemberDep` / `UnlockedCourseMemberDep` ile course scope ve exam lock;
- QA/Sokratik mod, source filter, evidence threshold ve daily course budget;
- hybrid retrieval, citation doğrulama, leakage/content guardrail;
- birebir cevap cache'i, request log, feedback ve role-aware dashboard;
- süreç içi 20 istek/60 sn sınırlayıcı ve ortak concurrency mekanizması

taşıyor. Bu nedenle 005'in değeri yeni bir üretim hattı değil; audience,
kalıcı quota, abuse kontrolü ve her sayfadan erişilen tutarlı chatbox katmanıdır.

## 2. Karar: Multi-agent değil, tek eylemsiz ders ajanı

### Seçilen

`audience=student|instructor` yetki bağlamıdır; `student_coach` ve
`instructor_assistant` aynı üretim hattına verilen iki server-owned davranış
profilidir. Ajan tool çağırmaz ve write action yapmaz.

### Neden

- Projenin anayasal sınırı kaynak-bounded RAG'dir.
- Hoca gereksinimi öğrenciye rehberlik ve eğitmene içerik yönetim desteğidir;
  otonom ajan ağı değildir.
- Tool yetkisi; prompt injection'ı veri sızıntısından gerçek eyleme yükseltir.
- LangGraph/LangChain eklemek mevcut LiteLLM/FastAPI zincirini çoğaltır ve
  ölçülmemiş operasyon maliyeti yaratır.

### Reddedilen

- Ayrı öğrenci/eğitmen endpoint'leri: davranış, sınav kilidi ve quota iki yerde ayrışır.
- İstemcinin persona seçmesi: öğrenci instructor promptuna geçebilir.
- “Genel kampüs asistanı”: ders kapsamı ve source-only sözleşmesini bozar.

## 3. Karar: Audience her istekte üyelikten çözülür

### Seçilen

`CourseContext.role` tek kaynak; `student -> audience student -> student_coach`,
`instructor -> audience instructor -> instructor_assistant`. Platform admin bu haritada yoktur.

Session audience oluşturulurken saklanır. Devam isteğinde güncel active membership
tekrar çözülür ve session audience ile karşılaştırılır.

### Neden

Kullanıcı farklı derslerde farklı rollerde olabilir. Global profil rolü veya
localStorage bu gerçeği temsil etmez. Üyelik sonradan değiştiğinde eski instructor
oturumunu student olarak sürdürmek yetki yükseltmesi olur.

### Legacy kararı

0015 öncesi session satırları migration anındaki aynı course/user aktif üyeliğine
göre `student|instructor`, eşleşmeyenler `student` ile backfill edilir. Legacy cache
satırları `audience=student` ve `legacy` policy/prompt/corpus revizyonuna bağlanır.

## 4. Karar: Cache açıkça audience + contract'a bağlanır

### Seçilen

Cache kimliği şu girdilerin canonical hash'idir:

```text
course_id
audience
mode
normalized_question
source_document_set_revision
course_policy_revision
prompt_contract_revision
retrieval_contract_revision
```

DB satırı audience ve contract hash'i ayrıca taşır; unique key bu alanları içerir.

### Neden

Yalnız normalize soruyu hash'lemek, instructor açıklamasını öğrenciye veya eski
policy cevabını yeni policy altında gösterebilir. Alanları yalnız hash içinde
gizlemek incelemeyi zorlaştırır; explicit audience şema çivisidir.

### Reddedilen

- Tüm cache'i kapatmak: maliyet ve gecikme avantajını gereksiz kaybettirir.
- Yalnız role göre iki tablo: kaynak/prompt revizyonu yine ayrışabilir.
- Semantik cache: benzer fakat farklı soruya yanlış cevap riski mevcut exact-match
  ürün kararını aşar.

## 5. Karar: Token quota reservation ile harcamadan önce alınır

### 004 baseline kusuru ve 0015 düzeltmesi

`course_tokens_today()` legacy `request_logs` içinde ders toplamını okur. İki worker aynı
son bütçe dilimini aynı anda görüp ikisi de sağlayıcıya gidebilir. Süreç içi limiter
çok worker/restart altında otorite değildir. 0015 bu fonksiyonu
dersin bütün kullanıcılarını kapsayan `ai_token_reservations.charged_tokens`
defterinden okuyacak biçimde yeniden
tanımlar; aşağıdaki reserve protokolü de harcama öncesi otorite olur.

### Seçilen

PostgreSQL içinde atomik `reserve -> reconcile` protokolü:

1. Sabit platform-gün transaction advisory lock'u, ardından course lock alınır.
   Sıra reserve ve reconcile için aynıdır; provider I/O başlamadan commit edilir.
2. Gün içindeki bütün reservation `charged_tokens` değerleri ders-kullanıcı,
   global-kullanıcı, ders ve platform toplamlarına girer; yalnız concurrency için
   süresi dolmamış unreconciled satırlar aktif sayılır.
3. Üyelik/audience, dört quota toplamı ve aktif reservation concurrency tek
   atomik kararda kontrol edilir.
4. Ders içi kullanıcı policy'si (student 12k/instructor 40k), cross-course global
   kullanıcı hard cap'i, ders hard cap'i ve platform aggregate hard cap'i birlikte
   uygulanır. DB yanlış operator ayarını da 50k/200k/500k/5m tavanlarıyla reddeder.
5. Tahmini prompt + server output cap `charged_tokens` olarak rezerve edilir ve kısa işlem commit edilir.
6. Ölçülmüş provider başarısı gerçek tokenla reconcile edilir. Provider hatası,
   iptal veya eksik usage muhafazakâr biçimde rezerve edilen tutarı korur. Reconcile
   best-effort'tur: başarısızlık kullanıcıya üretilmiş cevabı maskelemez ve ön charge
   yerinde kalır. `actual > reserved` reddedilir.
7. Lease, rol-farkındalıklı yolun zorlanan tek provider denemesinin deadline'ını
   ve reconciliation marjını aşar; SQL yalnız `30..600` saniyeyi kabul eder.
8. Mevcut user/course tüketim göstergesi de `request_logs` yerine aynı
   `charged_tokens` defterinden okunur; hata yolundaki muhafazakâr charge gizlenmez.

### Neden PostgreSQL?

- Zaten zorunlu ve transaction/locking yeteneği var.
- Yeni Redis/queue/deploy bağımlılığı açmaz.
- İlk ölçek için doğruluk, mikro-saniye optimizasyonundan değerlidir.

### Reddedilen

- Yalnız in-memory limiter: çok worker'da fail-open.
- Provider sonrası sayaç: aşımı engellemez, yalnız raporlar.
- Uzun DB transaction içinde LLM çağrısı: connection/lock tüketir.
- Redis'i hemen eklemek: ölçülmemiş ihtiyaç ve yeni operasyon yüzeyi.

## 6. Karar: Quota katmanları ve output cap

### Katmanlar

1. Mevcut process-local sliding window: ucuz burst filtresi.
2. DB course-user-day policy limiti: seçili derste hesap maliyet kontrolü.
3. DB global-user-day hard cap: aynı hesabın bütün derslerdeki toplamı.
4. DB course-day hard cap: tek dersin toplamı; policy satırı olmasa da uygulanır.
5. DB platform-day aggregate hard cap: tüm ders/kullanıcı toplamı.
6. DB içi 50k/200k/500k/5m ceiling: yanlış deployment config'ine son savunma.
7. DB active reservation sayısı: worker bağımsız concurrency.
8. Provider `max_tokens`: output maliyetini oluşmadan sınırlar.
9. Response/structured schema: provider sözleşme ihlaline son savunma.

### Cache hit kararı

Cache hit provider tokenı tüketmez; bu yüzden token reservation açmaz. Fakat
process-local burst limiter ve içeriksiz ölçüm kapısını geçer. Dağıtık edge/IP
limiti ayrıca canlı deployment backlog'udur.

### Varsayılan sayılar

İlk sayılar production gerçeği değil başlangıç önerisidir; staging ölçümü ve maliyet
sahibi onayı gerekir. DB hard ceiling course policy'nin aşamayacağı üst sınırdır.

## 7. Karar: Kapsam dışı ile saldırı ayrılır

### İlk dilimde seçilen sınıflar

- `ordinary_out_of_scope`: nazik 200 refusal, abuse skoruna girmez.
- `scope_refused`: normal kaynak/kapsam reddi için içeriksiz event.
- `rate_limited`: mevcut process-local burst reddi.
- `quota_exhausted`: course/user günlük token reddi.
- `concurrency_limited`: süreç-içi `concurrent_request` veya aktif kalıcı
  reservation reddinde kullanılan içeriksiz ledger kategorisi. HTTP sözleşmesi
  bunları sırasıyla 409 ve 429 olarak ayırır.

### Neden

Bir öğrencinin yanlışlıkla tarih sorusu sorması saldırı değildir. Bu nedenle
`scope_refused` kaydı ölçümdür, ceza değildir.

### Gelecek backlog

Adaptif strike/backoff, prompt fingerprint, IP/device ve worker'lar arası request
burst limiti ilk 005 diliminde yoktur. Gerekirse ayrı privacy/threat kararıyla
tasarlanır; bu dilimde ham prompt veya hash saklanmaz.

## 8. Karar: Abuse log ana işleme bağlı rollback olmamalı

Reserve/reject ve abuse yazımı ana chat transaction'ından ayrı kısa RLS bağlamlı
işlemde commit edilir. HTTP hata istisnası ana transaction'ı rollback etse bile
reddetme kaydı ve kota kararı kaybolmaz. SECURITY DEFINER fonksiyon:

- `app.current_user_id()` değerini kullanır;
- membership ve audience'ı kendisi yeniden çözer;
- serbest metin kabul etmez;
- allowlist kategori dışında değer reddeder;
- normal tablolara direct grant açmaz.

## 9. Karar: Instructor yardımcı pilotunun bilgi sınırı

Instructor persona şunları yapabilir:

- ders kaynağını açıklamak/özetlemek;
- öğretim yaklaşımı ve kavram yanılgısı önermek;
- kaynaklı taslak soru/rubric fikri vermek;
- kaynakta hangi bölümün ilgili olduğunu göstermek.

Şunları yapamaz:

- öğrenci sohbeti, cevabı, notu veya bireysel profilini okumak;
- soru/sınav/not/policy/belge üzerinde write action yapmak;
- “sistem ne biliyor?” diye platform logu veya secret açmak;
- kaynak dışı kesin akademik iddia üretmek.

## 10. Karar: Chatbox yeni backend değildir

`CourseAssistant`, mevcut API/session'ı kullanır. Course route'ta `CourseNav`
course id'yi verir; dashboard'da her `DashboardCourseCard` kendi active course
kimliğiyle inline tetikleyici sunar. Drawer içinde serbest course/persona seçimi
yoktur. Chatbox:

- availability gelmeden composer çizmez;
- aynı veriyi ikinci kez fetch etmez;
- drawer içinde aynı `session_id` ile çok turlu devam eder; tam sayfa deep-link
  ilk 005 acceptance kapsamı değildir;
- mobilde modal/drawer erişilebilirlik sözleşmesini uygular;
- login ve course context'i olmayan admin yüzeyinde genel chat olmaz.

## 11. Karar: Sınav bütünlüğü kullanıcı düzeyinde atomik sıralanır

Girişteki `UnlockedCourseMemberDep` tek başına yeterli değildir: provider çağrısı
sürerken ikinci sekmede sınav başlayabilir. Ayrıca `/me/export` önceki kaynaklı
sohbet yanıtlarını taşır. Bu nedenle sınav başlatma, öğrenci chat finalizasyonu ve
privacy export aynı user-wide advisory transaction lock'u kullanır.

- Exam önce commit ederse chat son kontrolü 403 `exam_in_progress`, export 423
  `exam_export_locked` döner.
- Chat/export önce kilidi alırsa kendi transaction'ını tamamlar; exam start sonra
  ilerler. Böylece aktif sınavla cevap/export arasında kesişen pencere kalmaz.
- Chat kontrolü provider dönüşünden sonra, session/message/cache/response
  commitinden önce yapılır; reddedilen yarışta answer artifact'i kalmaz.
- Export herhangi bir dersteki aktif student EXAM için geçici gecikir; practice,
  expired sınav ve instructor preview engellenmez.

## 12. Karar: Feature flag acil kill switch'tir

`COURSE_AGENT_ENABLED` varsayılanı `true` olan ve yeniden kullanılan `/chat`
yolunu bütünüyle kapatan bir acil anahtardır. `false`, availability'de
`globally_disabled`, POST'ta 503 `course_agent_disabled` üretir ve provider'a
gitmez. Bu anahtar cohort seçici değildir; kademeli canary hedeflemesi dış
deployment/feature-management kararı olarak açık kalır.

## 13. Karar: R3 AI-SDLC ve insan değerlendirmesi

Rol promptu, scope/abuse guard, cache identity, output cap ve quota davranışı R3'tür.
Merge öncesi deterministic/fake-provider kanıt:

- sözleşme ve güvenlik mekaniği;
- source/citation/exam/audience izolasyonu;
- kota yarışı ve reservation recovery;
- UI/API/RLS entegrasyonu.

Production kalite iddiası için ayrıca:

- aynı candidate üzerinde real-provider holdout;
- öğrenci Sokratik ve eğitmen faydası için ayrı rubric;
- iki bağımsız isimli onay (pedagoji/ürün ve güvenlik/operasyon);
- canary telemetry, stop koşulu, flag ve rollback kanıtı gerekir.

## 14. Yerel backend kanıtı ve açık doğrulamalar

Backend handoff'unda taze hedefli paket 157/157; son adayda
`pytest -q apps/api/tests` 894/894 ve mypy 92 dosya geçti. Ledger-counter
düzeltmesi ayrıca temiz DB'de 27/27 hedefli, ruff ve diff kontrolünden geçti.
Frontend `bun test lib/` 395/395, typecheck ve production build yeşildir. <!-- docs-check: frontend.tests = 395 --> Repo
kökünden çıplak pytest ise 005 dışı kardeş `scripts.*` import
collection sorunu buldu; bu yüzden “repo-root full suite yeşil” iddiası yoktur.
Fake/deterministik kanıt gerçek model pedagojisini veya production davranışını
kanıtlamaz.

- Gerçek provider başına `max_tokens` parametresinin LiteLLM adapter'ında nasıl
  eşlendiği entegrasyon testinde ölçülmelidir.
- Quota başlangıç sayıları staging token/tur ve kullanıcı davranışıyla kalibre edilmelidir.
- PostgreSQL bucket/reclaim davranışı yerel iki-worker fake-provider yükünde
  overshoot 0 ve reservation tepesi 1 olarak ölçüldü; gerçek provider/staging
  kapasitesi ayrıca ölçülmelidir.
- Edge/IP rate limit, WAF ve bot koruması canlı hosting sağlayıcısında ayrıca yapılandırılmalıdır.
- Guard/reservation retention süresi ve cleanup job'ı dış privacy/operations
  kararı olarak açıktır.
- Cohort canary kontrolü ve iki isimli approval henüz uygulanmamıştır.
