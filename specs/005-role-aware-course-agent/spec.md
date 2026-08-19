# Özellik Şartnamesi: Rol Farkındalıklı Ders Ajanı

**Feature Branch**: `005-role-aware-course-agent`
**Base**: `7c1c219` (`004-ai-sdlc-excellence`; yerel governance teslim commit'i)
**Created**: 2026-08-11

**Status**: Backend, `0015` ve frontend kodlandı; tam API 961/961, mypy 99 dosya, <!-- docs-check: backend.tests = 961 --><!-- docs-check: backend.mypyFiles = 99 -->
frontend 402/402, typecheck ve production build geçti. <!-- docs-check: frontend.tests = 402 --> Seri gerçek-API tarayıcı
36/36; manuel VoiceOver+Safari, doğrudan exam/kill-switch browser yolları, <!-- docs-check: e2e.tests = 36 -->
real-provider, staging, isimli onay ve canlı rollout kanıtı henüz yok.
**Risk**: R3 — öğrenci/eğitmen davranışı, kota, kötüye kullanım ve sınav kilidi değişiyor

**Input**: Kullanıcının öğrenci ve eğitmen için uygun cevap veren bir AI chatbox,
gereksiz sorulara yanıt vermeme, token/maliyet kontrolü ve kasıtlı kötüye kullanım
direnci talebi; mevcut CourseGPT chat/RAG/policy/exam-lock altyapısı.

---

## 1. Amaç ve sınır

005, mevcut `/courses/{course_id}/chat` RAG hattını ikinci kez yazmaz. Aynı
kaynak-bounded zinciri iki görünür kullanım biçiminde sunar:

- **Öğrenci çalışma koçu** (`audience=student`, `agent_profile=student_coach`):
  Sokratik mod seçildiğinde öğrencinin denemesini ister ve doğrudan cevabı ders
  politikasına göre sınırlar.
- **Eğitmen yardımcısı** (`audience=instructor`, `agent_profile=instructor_assistant`): yalnız seçili dersin
  onaylı kaynakları üzerinden açıklama, ders anlatımı yaklaşımı, kavram yanılgısı
  ve taslak soru fikri önerebilir.

“Ajan” sözcüğü burada **otonom olmayan, araç çağırmayan, akademik içeriği
değiştirmeyen rol farkındalıklı sohbet yüzeyi** anlamındadır. Bu dilimde ajan:

- belge, soru, sınav, not, üyelik veya politika oluşturamaz/değiştiremez;
- başka derse, platform admin verisine veya öğrenci sohbetlerine erişemez;
- web araması, kod çalıştırma, e-posta veya başka dış araç kullanamaz;
- sistem promptunu, gizli anahtarı veya başka kullanıcının verisini açıklayamaz;
- kaynak yetersizse cevap uydurmaz.

Bu sınırlar ileride araçlı bir ajana geçişi engellemez; araç yetkisi ayrı R3
şartname, tehdit modeli ve insan onayı olmadan bu özelliğe eklenemez.

### Durum sözlüğü

| Durum | Anlamı |
|---|---|
| Tasarlandı | Bu şartname ve sözleşmeler yazıldı. |
| Kodlandı | Migration, API, UI ve testler feature dalında mevcut. |
| Yerelde doğrulandı | Hedefli/tam test, mutasyon ve gerçek tarayıcı aynı commit'te geçti. |
| Staging'de doğrulandı | Gerçek kimlik/depolama/LLM ile sınırlı ortam kanıtı var. |
| Production'da gözlendi | Canary, telemetry, stop koşulu ve rollback kanıtı var. |

Alt durum üst durumu ima etmez.

---

## 2. Kullanıcı hikâyeleri

### US1 — Öğrenci ders içinde güvenli çalışma koçuna ulaşır (P1)

Öğrenci dashboard veya ders sayfasından küçük chatbox'ı açar, bir ders seçer ve
o dersin materyali üzerinde çalışır. Ajan, öğrencinin seviyesine uygun ipucu
verir; öğrenci denemeden Sokratik merdiveni ilerlemez.

**Independent Test**: Öğrenci iki derse üyedir. A dersinde chatbox açıp soru
sorar; yanıt `audience=student`, `agent_profile=student_coach`, A dersi kaynakları
ve öğrenci oturumuyla gelir.
B dersinin cache'i, oturumu veya kaynağı görünmez.

**Acceptance Scenarios**:

1. İstemci `audience=instructor` göndermeye çalışsa bile alan 422 ile
   reddedilir veya hiç sözleşmede bulunmaz; sunucu aktif üyelikten öğrenciyi çözer.
2. UI yalnız sunucunun `allowed_modes` sırasındaki ilk modu seçer; role bakarak
   gizli bir `default_mode` türetmez. Öğrenci Sokratik modu veya Sokratik öneriyi
   seçtiğinde mevcut merdiven kuralları çalışır.
3. Kaynak yoksa `insufficient_context`, ders dışı soruysa `out_of_scope` döner;
   sağlayıcıya serbest cevap ürettirilmez.
4. Öğrenci devam eden sınavdayken chatbox, tam sayfa chat, oturum listesi ve
   doğrudan API reddedilir. Sınav başlatma ile chat finalizasyonu aynı kullanıcı
   düzeyindeki transaction kilidinde sıralanır; provider çağrısı sürerken başlayan
   sınav cevabın/session/cache'in commit edilmesini engeller.
5. Practice ve süresi dolmuş sınav kilitlemez.
6. Mobil ekranda chatbox klavyeyle açılır/kapanır, odak kapanınca çağıran
   düğmeye döner ve sayfa yatay taşmaz.
7. `GET /me/export`, herhangi bir derste aktif öğrenci EXAM oturumu varken 423
   `exam_export_locked` döner; practice, süresi dolmuş sınav ve eğitmen önizlemesi
   KVKK dışa aktarma hakkını geciktirmez.

### US2 — Eğitmen kaynak-bounded yardımcı pilota danışır (P1)

Eğitmen, ders materyalini nasıl açıklayacağını, hangi kavram yanılgılarının
vurgulanabileceğini veya bir konu için taslak soru fikrini sorabilir. Yanıt
öğretmen bağlamında yazılır fakat hiçbir akademik kaydı değiştirmez.

**Independent Test**: Aynı kullanıcı A dersinde eğitmen, B dersinde öğrencidir.
A'daki yeni oturum `audience=instructor`, B'deki yeni oturum `audience=student`
olarak sunucu tarafından bağlanır; görünür profilleri sırasıyla
`instructor_assistant` ve `student_coach` olur.

**Acceptance Scenarios**:

1. Eğitmen ajanı, öğrenci sohbeti/cevabı/notu veya bireysel ilerleme istemini
   reddeder; toplu analitik için mevcut ayrı öğretmen ekranına yönlendirir.
2. “Bu belgeye göre örnek soru fikri ver” kaynaklı bir **taslak öneri** üretir;
   soru havuzuna yazmaz, yayınlamaz ve onay durumunu değiştirmez.
3. “Öğrencinin sınav cevabını değiştir” gibi eylem istemleri reddedilir.
4. Eğitmen başka dersin kimliğini veya öğrenci oturum kimliğini kullanamaz.
5. Eğitmen mod politikalarını test edebilse bile course/source/evidence, quota,
   output ve kötüye kullanım sınırlarını aşamaz.

### US3 — Her yüzey aynı rol ve API sözleşmesini kullanır (P1)

Chatbox ve mevcut tam sayfa asistan aynı API, RAG, guardrail, sınav kilidi,
kota ve session modelini kullanır. İlk 005 dilimi drawer'dan tam sayfaya
deep-link/continuation teslimi iddia etmez; drawer kendi açık konuşmasını aynı
`session_id` ile çok turlu sürdürebilir.

**Independent Test**: Chatbox bir oturum açar ve ikinci turda aynı `session_id`
ile devam eder. Üyelik rolü değişince eski oturum yeni role taşınmaz.

**Acceptance Scenarios**:

1. Oturum `audience` alanı sunucuda oluşturulurken sabitlenir.
2. Oturumun audience'ı aktif üyelikten çözülen audience ile uyuşmazsa 409
   `session_audience_changed` döner ve yeni oturum önerilir.
3. Cache anahtarı en az ders, mod, audience, normalize soru, kaynak/politika
   revizyonu ve prompt contract revizyonunu içerir.
4. `audience=student` cache'i `audience=instructor` isteğinde kullanılmaz; bunu
   kaldıran mutasyon testi kırmızı olur.
5. Chatbox dashboard verisini ikinci kez çekmez; ortak provider/query cache'i
   ders ve rol listesini paylaşır.

### US4 — Token ve istek tüketimi atomik, kalıcı ve adildir (P1)

Her istek, LLM çağrısından **önce** veritabanında en kötü durum token maliyetini
rezerve eder. Ölçülmüş başarılı kullanım gerçek tüketimle finalize edilir; provider
hatası, iptal veya bilinmeyen usage rezervasyonu sıfırlamaz, muhafazakâr biçimde
rezerve edilen tutarı korur. Birden fazla API worker'ı aynı anda çalışsa bile limit
aşılamaz.

**Independent Test**: Aynı kullanıcı için iki ayrı süreç eşzamanlı son kota
dilimini rezerve etmeye çalışır; yalnız biri kabul edilir ve toplam hiçbir anda
tanımlı sınırı aşmaz.

**Acceptance Scenarios**:

1. Ders içi audience bazlı kullanıcı bütçesi; kullanıcının bütün derslerdeki
   global hard cap'i; ders toplam hard cap'i; platform toplam hard cap'i ve kalıcı
   aktif reservation eşzamanlılığı atomik tek kararda uygulanır.
2. Provider'a gönderilen `max_tokens`/eşdeğeri sunucunun rol bazlı output cap'ini
   aşamaz; yalnız sonradan metin kesmeye güvenilmez.
3. Reservation ayrı kısa işlemde commit edilir; sağlayıcı çağrısı boyunca DB
   işlemi açık tutulmaz.
4. Provider hatası, istemci iptali veya usage'ın ölçülemediği yol `finally` içinde
   rezerve edilen tutarla uzlaştırılır; yalnız provider sınırını hiç geçmeyen yol 0
   olabilir. Süreç tamamen çökerse lease, rol-farkındalıklı tek provider denemesinin
   kesin zaman aşımı ve reconciliation marjından sonra yalnız aktif concurrency
   kilidini bırakır; muhafazakâr günlük charge kaybolmaz.
5. Bu dilim request-level idempotency vaat etmez; her HTTP çağrısı yeni
   reservation UUID'si alır. Replay anahtarı gelecek backlog'udur.
6. Cache isabeti LLM tokenı rezerve etmez fakat mevcut process-local burst
   kontrolünden geçer; request log `cached=true` olarak ölçülür.
7. Kullanıcı bütçe bittiğinde teknik ayrıntı veya diğer kullanıcıların tüketimi
   yerine kendi tekrar deneme zamanını ve anlaşılır Türkçe mesajı görür.

### US5 — Gereksiz ve kötü niyetli kullanım fail-closed durur (P1)

Sistem; ders dışı istek, kapsam reddi, hız/kota ve eşzamanlılık sınırı gibi
durumları içeriksiz kategorilerle kaydeder. Normal ders dışı merak nazikçe
reddedilir; mevcut süreç içi burst limiter ve kalıcı token/concurrency
rezervasyonu gereksiz tüketimi sınırlar.

**Independent Test**: Kapsam dışı istem yanıt üretmeden reddedilir ve yalnız
`scope_refused` kategorisi yazılır; rate/quota/concurrency reddi de içerik
taşımadan kendi kategorisinde kalır. Başka ders/kullanıcı etkilenmez.

**Acceptance Scenarios**:

1. Mevcut system-owned prompt, source/evidence/citation ve leakage/content
   guardrail zinciri prompt injection veya secret çıkarma taleplerine karşı korunur;
   005 bunu tool/write yetkisi ekleyerek zayıflatmaz.
2. Sıradan kapsam dışı soru tek başına “saldırgan” sayılmaz ve kalıcı ceza üretmez.
3. Bu dilimde guard event'ler adaptif ceza skoru üretmez; event yazmak tek başına
   kullanıcıyı engellemez.
4. Guard ledger soru/cevap, kaynak metni, IP, e-posta, JWT veya prompt hash'i taşımaz.
5. Öğretmen ve platform admin ham kullanıcı abuse satırlarını göremez; yalnız
   içeriksiz toplu operasyon metriği ileride ayrı sözleşmeyle açılabilir.
6. Ajan, HTML/script/prompt talimatı kaynak içinde bulsa bile bunu sistem talimatı
   saymaz; mevcut guardrail ve provenance zinciri korunur.

### US6 — AI değişikliği kontrollü yayınlanır ve geri alınır (P1)

Rol promptu, audience çözümü, quota/guardrail veya cache davranışı R3 AI-SDLC
dossier'ına bağlıdır. Deterministik/fake-provider kanıtı merge mekaniğini ölçer;
staging/production kalite iddiası için gerçek sağlayıcı ve insan değerlendirmesi gerekir.

**Independent Test**: AI-sensitive bir dosya değiştirilip dossier/hash/rollback
kanıtı güncellenmez; AI quality gate kırmızı olur.

**Acceptance Scenarios**:

1. `COURSE_AGENT_ENABLED` mevcut `/chat` yolunun varsayılanı `true` olan acil
   kill switch'idir; cohort/canary seçici değildir. `false` iken chatbox composer
   çizmez, direct backend POST 503 `course_agent_disabled` döner ve provider çağrılmaz.
2. Canary önce iç ekip/eğitmen, sonra küçük öğrenci kohortunda ilerler.
3. Stop koşulları en az citation faithfulness, scope precision, leakage,
   latency, 429/refusal oranı, token/tur ve kullanıcı geri bildirimini kapsar.
4. Rollback yeni agent isteklerini kill switch ile durdurur; 0015 verisi silinmez
   ve audience'lı mevcut veriler forward-compatible kalır.

---

## 3. Fonksiyonel gereksinimler

### Rol, kapsam ve yetki

- **FR-501**: Audience yalnız aktif `course_memberships.role` üzerinden sunucuda
  `student|instructor` olarak çözülmeli; görünür davranış profili yalnız sunucuda
  `student_coach|instructor_assistant` olarak türetilmelidir.
- **FR-502**: İstek gövdesi audience, sistem promptu, output limiti, quota veya
  tool yetkisi seçememelidir; ekstra alanlar 422 olmalıdır.
- **FR-503**: Her chat, availability, session ve message ucu course membership +
  RLS ile ders kapsamında kalmalıdır.
- **FR-504**: Platform adminlik audience üretmemeli ve akademik course membership
  sağlamamalıdır.
- **FR-505**: Ajan otonom eylem veya tool call üretmemeli; write action talebi
  reddedilmelidir.
- **FR-506**: Eğitmen audience'ı öğrenci özel içeriğini, notunu veya sohbetini
  açmamalıdır.

### Kaynak-bounded üretim

- **FR-510**: Mevcut retrieval, evidence threshold, citation validation,
  leakage/content guardrail ve “kaynak yoksa cevap yok” zinciri tek üretim yolu olmalıdır.
- **FR-511**: Rol promptu sistem-owned, sürümlü ve dossier/hash ile izlenebilir olmalıdır.
- **FR-512**: Student persona Sokratik öğretim sınırlarını; instructor persona
  önerinin taslak ve eylemsiz olduğunu açıkça zorlamalıdır.
- **FR-513**: Mevcut system-owned prompt, source/evidence/citation ve
  leakage/content guardrail zinciri her iki audience için korunmalı; 005 tool,
  write action veya secret yüzeyi eklememelidir.
- **FR-514**: Kapsam dışı ve yetersiz kanıt normal 200 abstention olmalı;
  exam/rate/quota/concurrency/kill-switch ihlali tek hata zarfıyla
  403/409/429/503 olmalıdır. Süreç-içi aynı kullanıcı/ders çakışması 409
  `concurrent_request`; kalıcı reservation sınırı 429
  `agent_concurrency_limited` olmalıdır.
- **FR-515**: Model/provider adı, system prompt, secret veya iç guardrail metni
  istemciye dönmemelidir.
- **FR-516**: Sınav başlatma, öğrenci chat finalizasyonu ve `GET /me/export`, aynı
  deterministik kullanıcı düzeyi PostgreSQL transaction advisory lock'unu
  kullanmalıdır. Chat, provider dönüşünden sonra fakat cevap/session/message/cache
  commitinden önce kendi dersi için aktif EXAM durumunu yeniden kontrol etmelidir.
- **FR-517**: Öğrencinin herhangi bir dersinde aktif EXAM varken `/me/export`
  423 `exam_export_locked` dönmeli; practice/süresi dolmuş sınav ve eğitmen
  önizlemesi engellenmemelidir. Bu geçici gecikme dışa aktarma hakkını silmez.

### Oturum ve cache

- **FR-520**: `chat_sessions` her yeni oturumda immutable `audience` taşımalıdır.
- **FR-521**: Aktif rol ile session audience uyuşmazlığı fail-closed 409
  `session_audience_changed` olmalıdır.
- **FR-522**: Legacy oturumlar migration anındaki aynı course/user aktif üyeliğine
  göre `student|instructor` audience'ına; eşleşmeyenler fail-closed `student` değerine bağlanmalıdır.
- **FR-523**: `answer_cache` audience ve prompt/policy/source contract revizyonuna
  bağlanmalıdır.
- **FR-524**: Audience/policy/source revizyonu değişince eski cache kullanılmamalıdır.
- **FR-525**: Chatbox ve tam sayfa aynı session/message endpoint ve şemalarını
  kullanmalıdır; drawer-to-full-page deep-link ayrı UI backlog'udur.

### Kota, maliyet ve kötüye kullanım

- **FR-530**: `0015_role_aware_course_agent.sql`, sabit platform-gün kilidini ve
  ardından ders kilidini alarak çok worker altında ders-kullanıcı, global-kullanıcı,
  ders-toplam ve platform-toplam günlük token rezervasyonunu atomik sağlamalıdır.
- **FR-531**: Rezervasyon provider çağrısından önce ayrı commit edilmeli; provider
  sonucu ölçüldüyse gerçek tokenla; provider hatası/iptal/bilinmeyen usage yoluysa
  rezerve edilen tutarla aynı reservation'ı uzlaştırmalıdır.
- **FR-531a**: Kullanıcıya gösterilen ve precheck'te kullanılan ders içi günlük
  tüketim `request_logs` yerine atomik `ai_token_reservations.charged_tokens`
  defterinden hesaplanmalıdır; provider hatasında kalan tam ön charge görünmelidir.
- **FR-532**: Kota kararı ders içi audience bazlı kullanıcı günlük bütçesini,
  cross-course global kullanıcı hard cap'ini, ders toplam hard cap'ini, platform
  aggregate hard cap'ini ve kalıcı aktif reservation eşzamanlılığını kapsamalıdır.
  Eğitmen course policy ile deployment cap'lerini yükseltememelidir; DB student,
  instructor, course ve platform için sırasıyla 50000/200000/500000/5000000
  mutlak tavanlarını ayrıca zorlamalıdır.
- **FR-533**: Output token cap provider çağrısında zorlanmalı; sunucu hard ceiling'i
  hiçbir course policy ile yükseltilememelidir.
- **FR-534**: Süresi dolmuş uzlaştırılmamış reservation aktif concurrency hesabına
  girmemeli fakat o günün ders-kullanıcı/global-kullanıcı/ders/platform quota
  toplamlarında muhafazakâr reserved charge olarak kalmalıdır; geç ve geçerli
  reconcile varsa gerçek kullanıma yalnız ilk kez iner. `actual > reserved`
  reddedilmeli ve muhafazakâr reserved charge korunmalıdır.
- **FR-534a**: Lease, rol-farkındalıklı HTTP yolunun zorlanan tek provider denemesi
  için toplam transport deadline'ından uzun olmalı; API'nin gönderdiği saniye SQL'de
  `30..600` aralığında doğrulanmalıdır.
- **FR-535**: Mevcut process-local sliding limiter hızlı ilk katman olarak kalabilir
  fakat dayanıklı quota'nın yerine geçemez.
- **FR-536**: Guard event içeriksiz, append-only ve yalnız
  `rate_limited|quota_exhausted|concurrency_limited|scope_refused` kategorilerinden biri olmalıdır.
- **FR-537**: `scope_refused` event'i bu dilimde adaptif backoff veya kalıcı ceza üretmemelidir.
- **FR-538**: Prompt fingerprint/hash bu dilimde saklanmamalıdır. Adaptif tekrar
  tespiti gerekirse ayrı tehdit modeli ve privacy kararıyla sonraki feature'a alınmalıdır.
- **FR-539**: Quota/abuse tablolarına normal kullanıcı, eğitmen, worker veya
  platform admin için doğrudan SELECT/UPDATE/DELETE grant'i verilmemelidir.

### Arayüz ve erişilebilirlik

- **FR-540**: Kimliği doğrulanmış course nav ve dashboard course card içinde
  erişilebilir `CourseAssistant` tetikleyicisi bulunmalıdır; login ve akademik
  bağlamı olmayan admin sayfasında genel amaçlı chat açılmamalıdır.
- **FR-541**: Her drawer yalnız onu açan course nav/card'ın `course_id` değerini
  kullanmalı; drawer içinde başka ders kimliği/persona seçimi olmamalıdır.
- **FR-542**: Audience/agent profile etiketi, kaynak sınırı ve sunucunun hata veya
  abstention mesajı teknik olmayan Türkçe ile görünmelidir. API sunmuyorsa UI
  kalan token/request sayısı uydurmamalıdır.
- **FR-543**: Chatbox availability sonucu gelmeden composer çizmemeli ve paralel
  hassas istek atmamalıdır.
- **FR-544**: 375 px, koyu tema, klavye, screen reader label, focus trap/return ve
  reduced-motion release kapısıdır.
- **FR-545**: Aynı dashboard/course/availability verisi aynı görünümde ikinci kez
  çekilmemelidir.

### Gizlilik, ölçüm ve işletim

- **FR-550**: Reservation, guard event ve request log prompt/answer/source text,
  e-posta, JWT veya secret taşımamalıdır.
- **FR-551**: Öğrenci sohbet metni yalnız mevcut self-only RLS sözleşmesiyle
  saklanmalı; eğitmen audience'ı bunu değiştirmemelidir.
- **FR-552**: İçeriksiz ölçüm üç kaynağa ayrılmalıdır: request log yalnız mevcut
  status/latency/token/cache alanlarını; guard event audience+allowlist event'i;
  reservation audience+token+zaman alanlarını taşır. Yeni serbest metin yoktur.
- **FR-553**: UI/API hata ve reddetmelerinde `request_id` korunmalıdır.
- **FR-554**: Canlı provider, canary, load ve saldırı kanıtı yoksa rapor bunları
  `KOŞULMADI` olarak yazmalıdır.
- **FR-555**: 005 değişiklikleri R3 dossier, iki bağımsız insan onayı, feature
  flag, canary stop koşulu ve rollback kaydı olmadan production'a yükselmemelidir.

---

## 4. Başarı kriterleri

- **SC-501**: Rol değiştirme/istemci audience enjeksiyonu testlerinin %100'ü
  fail-closed sonuç verir.
- **SC-502**: Öğrenci ve eğitmen cevaplarının %100'ü gösterilen ders kaynaklarına
  bağlıdır veya sistem açıkça abstain eder.
- **SC-503**: Eşzamanlı son-quota yarışında kabul edilen rezervasyonların toplamı
  tanımlı limiti hiçbir denemede aşmaz.
- **SC-504**: Provider exception, client cancellation ve process-crash senaryosunda
  TTL sonrası aktif reservation kalmaz.
- **SC-505**: Audience/cache/session güvenlik kontrollerinden biri kaldırıldığında
  adlandırılmış mutasyon testi kırmızı olur.
- **SC-506**: Guard/reservation tablolarının şema ve örnek satırlarında serbest metin,
  prompt, cevap, tam e-posta, IP, JWT veya ham prompt hash'i bulunmaz.
- **SC-507**: 375 px ve masaüstünde öğrenci/eğitmen chatbox yolculukları klavye ve
  gerçek API ile geçer; devam eden sınav ikinci sekme/API yolunda yardım vermez.
- **SC-508**: Deterministik PR paketi backend/frontend/RLS/OpenAPI/docs/AI gate'i
  yeşil yapar; bu sonuç gerçek LLM pedagojik kalitesi diye sunulmaz.
- **SC-509**: Staging canary'de önceden yazılmış eşikleri aşan leakage, faithfulness,
  scope precision, p95 latency, token/tur veya 429 oranı rollout stop kararı üretir.
- **SC-510**: Zorlanmış interleaving testlerinde sınav önce commit ederse chat 403
  ve export 423 döner; chat/export önce commit ederse sınav yalnız onların
  transaction'ı bittikten sonra başlar. Hiçbir sıralamada aktif sınav penceresinden
  kaynaklı cevap veya export geçmez.

---

## 5. Kapsam dışı

- Çok ajanlı orkestrasyon, LangGraph/LangChain, tool calling veya otonom iş akışı.
- Web araması ve ders dışı genel bilgi asistanı.
- Öğrenci notu/cevabı/sohbeti üzerinde eğitmen veya admin agent erişimi.
- Otomatik soru yayınlama, sınav/not/politika değiştirme.
- Faturalama, ödeme, resmi OBS entegrasyonu veya akademik kayıt sistemi.
- İlk dilimde IP tabanlı WAF/gateway kontrolü; bunun yerine account/course quota
  uygulanır, edge kontrolü ayrı deployment görevidir.

---

## 6. Varsayımlar ve açık kararlar

- `Europe/Istanbul` günlük quota sınırıdır; yaz/kış saati PostgreSQL timezone
  işlemleriyle çözülür.
- İlk repo varsayılanları öğrenci için 12.000, eğitmen için 40.000 token/gün;
  output 700 token ve concurrency 1'dir. Bunlar production kalibrasyonu değil,
  staging'de ölçülecek başlangıç değerleridir; output schema hard ceiling 4096'dır.
- Exact sayılar ürün sahibi + güvenlik + maliyet sahibi tarafından dossier'da
  onaylanmadan production eşiği değildir.
- Gerçek provider ve staging bilgileri mevcut değilse deterministic fake-provider
  kanıtıyla yalnız repo entegrasyonu yapılır.
- IP/device temelli edge sınırlama, adaptif strike/backoff ve prompt tekrar
  fingerprint'i 005 ilk diliminin açık gelecek backlog'udur.
- Request-level idempotency/replay anahtarı ve DB-backed minute/request bucket
  da ilk 005 diliminin açık gelecek backlog'udur.
