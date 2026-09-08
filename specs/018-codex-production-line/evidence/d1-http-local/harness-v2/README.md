# D1 iki gerçek HTTP süreci kabul adayı v2

Durum: ayrı `/private/tmp` v2 adayı, **yalnız çevrimdışı doğrulandı**.
V1 `/private/tmp/dou018-d1-http-candidate` ve ilk başarısız koşu korunur.
V1 fixture topics.created_by alanını atladığı için gerçek DB NOT NULL reddi verdi;
sunucu başlamadı ve HTTP kabul ölçümü yapılmadı. V2 yalnız bu INSERT
sütunu/değerini eğitmen kimliğine bağlar; yeni schema-contract testi aynı
fixturenin altı tablodaki zorunlu girdilerini ve bind sayısını çevrimdışı kontrol eder. Gerçek DB veya
sunucu çalıştırılmadı. D1 v2 dosyaları ve depo bu hazırlık sırasında değiştirilmedi.
D1 v2'nin kök tarafından ölçülmüş 10 PostgreSQL testi ayrı kanıttır; buradaki 55
HTTP çağrısının sonucu değildir.

## Nelerin gerçek olduğu

İki ayrı Python/Uvicorn süreci, gerçek FastAPI uygulamasını ve mevcut chat/qgen
uçlarını çalıştırır. Quota helper, bağımsız control COMMIT, ana transaction,
API dependencies, ders yetkisi, app RLS, hata handler ve cache kodu değiştirilmez.
Her süreç gerçek `dou_app` kullanıcı adı ile bağlanır; gerçek ana/control havuzları
salt okunur sorguyla OID/endpoint/version, role/session-role, non-superuser,
non-BYPASSRLS ve row_security=on bakımından doğrulanır. DBA cluster system identifier
kontrolü ilk fixture yazımından önce yapılır; `pg_control_system` uygulama rolüne
verilmez.

Yalnız mevcut `set_pipeline` ve `question_gen.set_providers` DI girişleri kullanılır.
Retrieval fixture'ı gerçek istek SQLAlchemy/RLS oturumundan dersin üç sentetik
chunk'ını okur; skorları sabit1'dir. `D1_NO_SOURCE` test girdisi boş sonuç üretir.
Bunlar ANN veya semantik retrieval kalite testleri değildir. Asıl GenerationService,
guardrail ve qgen parser çalışır; deterministik FakeLlmClient alt sınıfı çağrıyı
sayar ve yalnız `D1_PROVIDER_FAILURE` sentetik girdisinde LlmUnavailableError atar.
Sağlayıcı anahtarı yoktur; dış modele gidilmez. JWT sağlayıcı doğrulaması yerine
uygulamanın yetkili yerel `dev:<uuid>` auth yolu kullanılır.

## Sınırlı senaryolar

1. Her süreçten önce bir kabul; ardından iki eşzamanlı HTTP döngüsünde19'ar çağrı:
   aynı öğrenci/ders için toplam40 istekten tam20 HTTP200 kaynak reddi ve20 HTTP429.
   Aynı pencerede DB'de20 kabul, iki gerçek child PID ve hiçbir sağlayıcı çağrısı.
   Senaryo60 saniyeyi aşarsa sonuç kabul edilmez; eşik gevşetilmez.
2. Yeni öğrenciyle kontrollü provider503: gerçekten bir çağrı yapılır, slot1 kalır,
   ana chat_sessions işlemi rollback olur.
3. Yalnız izole DB'de canonical chat policy20→19: her iki API503/Retry-After1,
   slot0, provider0. `finally` policy20'yi geri yükler. Ardından ayrı kullanıcıda
   gerçek advisory lock timeout:503/Retry-After1, slot0/provider0; kilit kalkınca
   kabul ve slot1. Bu test DB ağ kesintisi değildir.
4. Aynı QA sorusu iki süreçte: iki slot, ilk yanıtta provider çağrısı, ikinci
   yanıtta DB cache isabeti; sağlayıcı toplam1.
5. Öğrenci qgen403/slot0/provider0; eğitmen iki API'ye dönüşümlü5 çağrıyla5 taslak,
   ardından her iki API429/Retry-After1..300; provider toplam5, committed slot5.
   Bu senaryo dağıtık qgen eşzamanlılık kilidini kanıtlamaz.

Toplam55 ölçülen ürün isteği; ayrıca startup readiness sorguları vardır. Sınama
metinleri/Authorization başlıkları ham rapora yazılmaz. İstekler yalnız rastgele
sentetik request ID, endpoint süreci/PID, status/error code, Retry-After, cache ve
kabul sayısıyla kaydedilir. Sağlayıcı olayları request ID+PID ile eşlenir. Raw
uygulama logu yalnız sentetik bu koşuya aittir; hata gövdeleri rapora kopyalanmaz.

## Kökün sağlayacağı güvenilir girdiler

- Yeni, boş `dou_synapse_d1_*` DB; güncel depo migration'ları uygulanmış olmalı.
  Harness DB yaratmaz veya migration/DDL yürütmez. Mevcut course/profile varsa durur.
- `D1_TEST_DB_NAME`, `D1_ADMIN_DSN`, `D1_EXPECTED_TARGET_JSON`: D1 v2 ile aynı
  altı alanlı fingerprint sözleşmesi. Güvenilir provisioning bağlantısında
  `host(inet_server_addr())` kullanın; CIDR parser tarafından kabul edilmez.
- `D1_HTTP_APP_DSN`: aynı açık numeric loopback/port/DB, tam `dou_app` rolü,
  `postgresql+psycopg` şeması; query/fragment yok. Gerekli parolalar yalnız mevcut
  gizli ortam kanalından gelir. URI'ler argüman/loga verilmez.
- `D1_HTTP_PORTS_JSON`: iki farklı açık1024..65535 port, örneğin `[18331,18332]`.
  DB portu olamaz. Parent127.0.0.1'e bind eder, açık listener FD'lerini iki çocuğa
  geçirir. Mevcut dinleyiciyi öldürmez veya porta otomatik alternatif seçmez.
- `D1_HTTP_SOURCE_MANIFEST_JSON`: `common.SOURCE_PATHS` içindeki15 gerçek dosyanın
  kök tarafından onaylanan path→SHA256 haritası. `probe.py` varsayılan planı gerekli
  yolları gösterir. Kök `common.source_hashes()` sonucunu inceleyip bu açık ortam
  girdisine bağlayabilir; çalıştırıcı beklenen kaynağı kendisi öğrenip onaylamaz.

D1 candidate0023 → gerçek `supabase/migrations/0025_shared_request_quota.sql`
mapping'i sonuçta açık kaydedilir; basename'in aynı olması beklenmez. Advisory
namespace15023 değişmemiştir. SQL function definition hash/SECURITY DEFINER/
volatility/search_path bilgisi DB'den ayrıca alınır. Ölçüm öncesi/sonrası15 dosya
ve tüm `apps/api/app/**/*.py` hash'leri eşit olmalıdır; Git HEAD kirli kaynağın
tek kimliği sayılmaz. Worker veya başka API kaynakları değişirken çalıştırmayın.

Parent tüm inherited PG* girdilerini kaldırır. Çocuk ortamı allowlist'tir;
provider/admin/worker credential, PG service/hostaddr/options mirası yoktur.
Yalnız bu fresh0700 çıktı dizininde yaratılan0600 özel boş regular passfile
`PGPASSFILE` olarak verilir. Sürücü DSN'sinin tek query girdisi, doğrulanmış IP'den
oluşturulan `hostaddr`'dır. API'nin WORKER_DATABASE_URL girdisi aynı dou_app DSN'sidir;
worker bu senaryoda başlamaz. Sabit yerel listener ve DBA sakinliği varsayılır;
kriptografik sunucu kimliği veya kötü niyetli yerel proxy savunması iddiası yoktur.

## Çalıştırma ve sonuç

Girdiler kökün gizli ortamında sağlanınca:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/muratates/code/dou-synapse-018-codex-production-line/apps/api/.venv/bin/python /private/tmp/dou018-d1-http-candidate-v2/probe.py --execute --output /private/tmp/dou018-evidence/d1-http-measured-02
```

Çıktı dizini yeni olmalı; önceki sonucu ezmez. Varsayılan giriş `--execute` yokken
stdlib ile yalnız JSON plan basar, credential okumaz ve bağlantı/sunucu açmaz.
Başarı ancak tüm55 sonuç, DB state ve provider sayaçları eşleşirse `measured`
olur. Çocuklar `finally` içinde sonlandırılır; varsayılan olarak yalnız oluşturulan
course/profile fixture'ları silinir, kalan course/profile/quota/chat sayılarına
bakılır. `--keep-fixtures` kökün bilinçli tanısı için bu son temizliği atlar.
Hata ve önceki kanıtlar korunur; yeni kaynak/koşu yeni çıktı dizini almalıdır.

Çevrimdışı tekrar:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/muratates/code/dou-synapse-018-codex-production-line/apps/api/.venv/bin/python /private/tmp/dou018-d1-http-candidate-v2/test_offline.py
PYTHONDONTWRITEBYTECODE=1 /Users/muratates/code/dou-synapse-018-codex-production-line/apps/api/.venv/bin/python /private/tmp/dou018-d1-http-candidate-v2/negative_controls.py
```

V2 hazırlıkta15 offline test ve5 guard/provider mutant RED; ayrıca değişmemiş
v1 fixture aynı yeni testte missing topics.created_by nedeniyle RED; gerçek HTTP sonucu henüz yoktur.
Normal repo testlerinde deque'yi dolduran fixture'lar yeni DB canonical policy ve
quota state hazırlığına dönmelidir; bu araç eski testleri otomatik değiştirmez.
Farklı limit ayarlayan test, izole DB policy'sini aynı değere bağlamalıdır.
Worker TTL hook/scheduled wakeup, retention/export envanteri, hosted rollout ve
D2 dağıtık iş/lease toparlanma kanıtları ayrı açık işlerdir.
