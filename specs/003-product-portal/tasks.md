# Tasks: 003 Rol Bazlı Ürün Portalı

**Branch**: `003-product-portal`
**Base**: `3b707ca`
**Migration**: `0014_platform_admin_console.sql`
**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

---

## İşaretleme ve kanıt kuralı

- `[ ]`: Açık. Dosyanın çalışma ağacında bulunması görevi kapatmaz.
- `[x]`: Aynı commit'te uygulama, hedefli test ve ilgili runtime/RLS/tarayıcı kanıtı
  tamamlanmış, görev notuna kanıt eklenmiştir.
- `[P]`: Dosya sahipliği çakışmıyorsa paralel yürütülebilir.
- `[USn]`: Doğrudan kullanıcı hikâyesine bağlıdır.

**2026-08-10 snapshot'ı**: Backend/frontend portal dosyaları ve `0014` migration'ı
feature commit'lerinde bulunmaktadır. Kod, hedefli/tam test, RLS mutasyonu,
generated OpenAPI, build ve tarayıcı nöbetçileri tamamlandı. Yalnız dalın uzak
teslim kaydı T610 ve Faz 7'nin dış ortam işleri açıktır; “yerelde doğrulandı” ile
“production'da kanıtlandı” aynı statü değildir.

---

## Faz 0 — Ön kontrol ve sözleşme dondurma

- [x] T001 Doğru worktree, `003-product-portal` dalı ve `3b707ca` tabanını kayda al;
  başka iş şeritlerinin değişikliklerine dokunma.
- [x] T002 `0013_chat_feedback.sql` rezervasyonunu ve portal migration'ının
  `supabase/migrations/0014_platform_admin_console.sql` olduğunu doğrula.
- [x] T003 [P] Sekiz Speckit belgesini aynı terimlerle tamamla:
  `specs/003-product-portal/{spec,plan,research,data-model,quickstart,tasks,full-product-roadmap}.md`
  ve `specs/003-product-portal/contracts/api.md`.
- [x] T004 Sözleşme taramasında bütün header, endpoint ve migration adlarını
  `003-product-portal`, `/admin/requests`, `/admin/ingestion` ve
  `0014_platform_admin_console.sql` ile birebir eşle; eski taslak ad bırakma.
- [x] T005 Dashboard sözleşmesini dondur: gerçek sayılar
  `documents_processing`, `documents_failed`, `draft_questions`,
  `published_exams`; blueprint yalnız araç linkidir.
- [x] T006 Admin gizlilik sözleşmesini dondur: request/ingestion listesinde serbest
  metin ve ham kimlik yok; ingestion yanıtında `file_name` yok; kullanıcı araması
  yalnız `POST /admin/users` JSON gövdesinde ad veya maskelenmiş e-posta ifadesiyle
  eşleşir, tam e-posta eşleşmez ve URL/query search alanı yoktur.
- [x] T007 `PATCH /me/profile` için yalnız zorunlu `full_name` alanını dondur;
  e-posta, rol ve adminlik değiştirilemez.
- [x] T008 Constitution kapılarını [plan.md](plan.md) ile yeniden kontrol et;
  açık doğrulama kapılarını “GEÇTİ” yapma.

**Faz kapısı**: Sözleşme, Pydantic ve TypeScript alan adları birebir eşleşmeden
migration/API/UI üzerinde yeni davranış eklenmez.

**Kanıt (2026-08-10)**: Dal ve merge-base `003-product-portal` / `3b707ca`
olarak ölçüldü. Sekiz feature belgesi aynı endpoint, migration ve dashboard alan
adlarına getirildi; dış ortam doğrulama kapıları plan ve görev listesinde açık bırakıldı.

---

## Faz 1 — Veri ve platform admin güvenlik çekirdeği

- [x] T101 [US4] `supabase/migrations/0014_platform_admin_console.sql` içinde
  `platform_admins` ve append-only `platform_admin_access_audit` tablolarını,
  FK/kısıtları ve zaman damgalarını oluştur.
- [x] T102 [US4] Aynı migration'da RLS'yi ENABLE et, fakat FORCE etme; PUBLIC,
  `dou_app` ve `dou_worker` tablo grant'lerinin tamamını geri al.
- [x] T103 [US4] DBA dışında admin atama/değiştirme yolu bırakma; uygulamaya
  INSERT/UPDATE/DELETE fonksiyonu veya endpoint'i ekleme.
- [x] T104 [US4] Sabit `search_path` kullanan `app.is_platform_admin()` helper'ını
  yaz; kullanıcı yoksa false dönsün ve EXECUTE yalnız `dou_app`te olsun.
- [x] T105 [US4] `app.audit_platform_admin_access(action, request_id)` helper'ını
  yalnız `GET /admin/overview`, `POST /admin/users` ve kalan üç GET liste action'ı
  ile güvenli request ID biçimine sınırla; allowed ve denied kararını DB'de yeniden
  hesaplayıp append-only tabloya yaz.
- [x] T106 [P] [US4] Her biri admin kontrolünü kendi içinde tekrarlayan dar
  `app.admin_overview`, `app.admin_users`, `app.admin_courses`,
  `app.admin_request_logs`, `app.admin_ingestion_jobs` projeksiyonlarını yaz.
- [x] T107 [US4] `app.admin_users` aramasını `full_name` ve SQL tarafında üretilen
  maskelenmiş e-posta ifadesiyle sınırla; tam e-posta aramasının eşleşmediğini
  kanıtla.
- [x] T108 [US4] Ingestion projeksiyonundan `file_name`, storage path, belge/chunk
  metni ve `last_error` alanlarını şema düzeyinde dışarıda bırak.
- [x] T109 [US4] Request projeksiyonundan kullanıcı UUID'si, e-posta ve bütün
  pseudonym/hash alanlarını çıkar; prompt/cevap/citation metnini de seçme.
- [x] T110 [US4] Limit/offset doğrulamasını SQL katmanında da uygula; limit 1–100,
  offset sıfır veya pozitif olsun.

**Faz kapısı**: Normal uygulama rolü doğrudan tabloya erişemeden admin helper'ı
çalışmalı; admin satırı kaldırıldığında helper reddetmelidir. Mutasyon testi
kırmızıya dönmeden bu faz kapanmaz.

**Kanıt (2026-08-10)**: `fa659d1` migration, dar projeksiyonlar ve negatif
backend testlerini; `9c2fe23` doğrudan grant/admin kontrolü mutasyon nöbetçisini
ekledi. Admin atama endpoint'i yoktur ve akademik içerik projeksiyona alınmaz.

---

## Faz 2 — Backend profil, dashboard ve admin API'leri

- [x] T201 [P] [US3] `apps/api/app/schemas/profile.py` içinde profil/üyelik çıktı
  modellerini ve ekstra alanı reddeden `full_name` update modelini tamamla.
- [x] T202 [US3] `apps/api/app/api/profile.py` içinde `GET /me/profile` ve
  `PATCH /me/profile` uçlarını mevcut Principal/RLS bağlamıyla uygula.
- [x] T203 [P] [US1] [US2] `apps/api/app/schemas/dashboard.py` içinde viewer,
  summary ve course DTO'larını sözleşmeyle eşle.
- [x] T204 [US1] [US2] `apps/api/app/api/dashboard.py` içinde tek aggregation
  isteğini uygula; istemciye ders başına N+1 çağrı yaptırma.
- [x] T205 [US2] Eğitmen `action_items` formülünü yalnız
  processing + failed + draft question toplamı yap; blueprint sayacı üretme.
- [x] T206 [US1] Öğrenci mastery/aktivite alanlarını yalnız giriş yapan kişinin
  verisinden türet; diğer öğrenci satırlarını hiçbir ara sonuçta taşıma.
- [x] T207 [P] [US4] `apps/api/app/schemas/admin.py` içinde overview ve dört
  sayfalı liste zarfını tam allowlist alanlarıyla tanımla.
- [x] T208 [US4] `apps/api/app/api/deps.py` içine fail-closed
  `PlatformAdminDep` ekle; course membership dependency'sinin yerine kullanma.
- [x] T209 [US4] Admin erişim audit çağrısını ana istekten ayrı tamamlanan DB
  işleminde yap; 403 nedeniyle denied audit satırının rollback olmadığını test et.
- [x] T210 [US4] `apps/api/app/api/admin.py` içinde `/admin/overview`, `/users`,
  `/courses`, `/requests`, `/ingestion` uçlarını sözleşmeyle eşle; yalnız kullanıcı
  dizini `POST` JSON body, diğerleri GET/query kullanır.
- [x] T211 `apps/api/app/main.py` içinde üç router'ı kaydet; mevcut request ID,
  hata zarfı ve güvenlik middleware zincirini bozma.
- [x] T212 [US4] Admin overview'a API runtime'ından application/DB/embedding
  durumunu ve `measured_at` ekle; orkestratör probe'larını değiştirme.
- [x] T213 [US3] [US4] `apps/api/tests/test_portal.py` içinde profil, karma rol,
  dashboard sayaç/formül ve admin pozitif/negatif senaryolarını yaz.
- [x] T214 [US4] Aynı testte self-promotion, ham PII/metin sızıntısı, limit 101,
  negatif offset, kullanıcı dizininde query-string search yüzeyinin bulunmaması,
  POST body'sindeki tam e-posta aramasının eşleşmemesi ve ingestion `file_name`
  yokluğu iddialarını ekle.
- [x] T215 [US4] Platform adminin üye olmadığı akademik ders ucunda hâlâ
  reddedildiğini gerçek HTTP testiyle kanıtla.

**Faz kapısı**: Hedefli pytest, ruff ve mypy geçmeli; route path'leri OpenAPI'de
tam olarak sözleşmedeki biçimde görünmelidir.

**Kanıt (2026-08-10)**: `fa659d1` profil/dashboard/admin API ve şemalarını,
router kayıtlarını ve portal testlerini ekledi; `68f8b54` dashboard'u üç server
kaynaklı sınav kilidi alanı ve karma rol/tek-sorgu davranışıyla tamamladı. Testler
self-promotion, bounds/null, tam e-posta, ham içerik ve üyeliksiz akademik erişim
negatiflerini içerir. Generated OpenAPI eşitlemesi T606 kanıtıyla kapatıldı.

---

## Faz 3 — Frontend ortak portal altyapısı

- [x] T301 [P] `apps/web/lib/profile.ts` içinde profil istemci/tiplerini ve güvenli
  hata işleme yolunu yaz.
- [x] T302 [P] `apps/web/lib/dashboard.ts` içinde tek dashboard isteğini ve kesin
  DTO tiplerini yaz.
- [x] T303 [P] `apps/web/lib/admin.ts` içinde overview/list client'larını,
  filtreleri ve sayfalama tiplerini yaz; kullanıcı aramasını POST JSON body ile
  gönder, URL query veya tam e-posta araması sunma.
- [x] T304 `apps/web/components/portal/portal-profile-context.tsx` içinde profil
  sonucunu AppShell, profil ve admin gate arasında paylaş; logout/user değişiminde
  cache'i temizle.
- [x] T305 [P] Portal sayfalarında loading, empty, partial ve error durumlarının
  sahipliğini açık tut: `portal-metrics.tsx` yalnız ölçümü çizer; yükleme/tam hata
  sayfa düzeyindeki ortak durum bileşenlerinde, kısmi hata veri sahibi sayfada
  gösterilir. Aynı durumu iki bileşen birden üretmez.
- [x] T306 [P] `apps/web/components/portal/dashboard-course-card.tsx` içinde rol
  bazlı gerçek araç linklerini oluştur; iş yapmayan düğme bırakma.
- [x] T307 [P] `apps/web/components/portal/admin-data-table.tsx` içinde klavye,
  tablo başlıkları, mobil overflow/kart davranışı ve metinli durumları uygula.
- [x] T308 `apps/web/components/app-shell.tsx` içinde dashboard/profil/admin
  navigasyonunu server-derived profile ile çiz; admin sonucu gelmeden link açma.
- [x] T309 `apps/web/app/page.tsx` giriş sonrası hedefi `/dashboard` yap; mevcut
  ders deep-linklerini bozma.

**Faz kapısı**: Aynı render yolculuğunda `/me/profile` iki kez çağrılmamalı;
localStorage adı veya rolü server gerçeğinin yerine kullanılmamalıdır.

**Kanıt (2026-08-10)**: `77cf35e` istemci sözleşmeleri, tek profil provider'ı,
gerçek araç linkleri, tablo ve navigasyonu ekledi; `68f8b54` provider cache'ini
kullanıcı kimliğine bağladı ve logout/kullanıcı değişiminde eski profilin
taşınmasını kapattı. `9c2fe23` ağ sırası ve tek profil isteğini E2E nöbetçisine aldı.

---

## Faz 4 — Kullanıcı yüzeyleri

### US1 — Öğrenci portalı

- [x] T401 [US1] `apps/web/app/dashboard/layout.tsx` ve `page.tsx` içinde öğrenci
  derslerini, ilerleme/sınav/asistan girişlerini ve dürüst boş durumları göster.
- [x] T402 [US1] Yürüyen sınavda sohbet bağlantısı ve açıklamasını mevcut server
  availability/kilit sözleşmesiyle tutarlı yap.
- [x] T403 [US1] Sahte GPA, dönem, danışman, program, duyuru veya çalışma skoru
  üretmediğini boş/az veri tarayıcı senaryosuyla doğrula.

### US2 — Eğitmen portalı

- [x] T410 [US2] Aynı dashboard'da belge processing/failed, taslak soru,
  yayınlanmış sınav ve aksiyon toplamlarını ayrı etiketlerle göster.
- [x] T411 [US2] Kaynak laboratuvarı, sorular, blueprint, sınavlar, AI politikası
  ve analitik için çalışan doğrudan linkler ekle.
- [x] T412 [US2] Blueprint'i görünür araç yap, fakat sözleşmede olmayan taslak
  blueprint sayacı üretme.
- [x] T413 [US2] Sınıf/operasyon özetini privacy-negative aggregate olarak
  doğrula: yalnız izinli toplu sayaç ve durumları taşı; bireysel sohbet, sınav
  cevabı, prompt veya öğrenciyle eşlenebilir kimlik taşımadığını negatif testle
  kanıtla.

### US3 — Profil ve veri hakları

- [x] T420 [US3] `apps/web/app/profile/layout.tsx` ve `page.tsx` içinde kendi
  kimliğini, değiştirilebilir adı ve ders bazlı üyelik rollerini göster.
- [x] T421 [US3] E-postayı “kimlik sağlayıcısı yönetir” açıklamasıyla salt okunur
  yap; kullanıcıya rol/admin düzenleme kontrolü verme.
- [x] T422 [US3] Mevcut `/account` veri indirme, sohbet silme ve anonimleştirme
  akışlarına belirgin bağlantı ver; fonksiyonları kopyalama.
- [x] T423 [US3] PATCH başarı/hata sonrasında provider verisini doğru yenile;
  eski localStorage adını gerçekmiş gibi bırakma.

### US4 — Platform admin konsolu

- [x] T430 [US4] `apps/web/app/admin/layout.tsx` içinde profil tabanlı fail-closed
  gate kur; admin sonucu gelmeden admin liste isteklerini başlatma.
- [x] T431 [US4] `apps/web/app/admin/page.tsx` içinde uygulama, DB ve embedding
  sağlığını ayrı ve zaman damgalı göster.
- [x] T432 [US4] Kullanıcı dizininde placeholder'ı `Ad veya maskeli e-posta` yap;
  arama değerinin URL'ye girmediğini ve tam e-posta aramasının eşleşmediğini
  UI/API testiyle doğrula.
- [x] T433 [US4] Ders, request ve ingestion tablolarına filtre/sayfalama ile
  loading, empty, error ve partial durumlarını ekle.
- [x] T434 [US4] UI'da `file_name`, last_error, prompt, cevap, stack trace, tam
  e-posta veya ham kullanıcı UUID'si için kolon/ayrıntı görünümü oluşturma.
- [x] T435 [US4] Admin konsolunu salt okunur tut; rol verme, kullanıcı silme,
  kurs kapatma veya job değiştirme aksiyonu ekleme.

**Kanıt (2026-08-10)**: `77cf35e` dört kullanıcı yüzeyini ve gerçek linkleri;
`68f8b54` server-derived sınav kilidi, karma rol ve profil yenilemesini;
`9c2fe23` düşük veri, gizlilik, tam e-posta, gate sırası ve erişim reddi E2E
nöbetçilerini ekledi. Portal admin yerine kullanıcıya görünen ad **Bilgi İşlem**,
yetki modeli ise bağımsız ve salt okunur platform admin ilişkisidir.

---

## Faz 5 — Karma rol ve tasarım regresyonları

- [x] T501 Bütün ders ekranlarında rol çözümlemeyi tara; course içi UI'nın
  `useSession(courseId)` kullanmasını zorunlu kıl.
- [x] T502 `apps/web/app/courses/[courseId]/blueprints/page.tsx` içindeki
  courseId'siz session kullanımını düzelt ve karma rol regresyon testi ekle.
- [x] T503 [P] Dashboard, profil ve admin ekranları için 375 px ve masaüstü
  görünümünü doğrula; yatay sayfa taşmasını gider.
- [x] T504 [P] Koyu tema, visible focus, başlık sırası, klavye kullanımı ve
  durumun yalnız renkle anlatılmaması kontrollerini tamamla.
- [x] T505 OBS referansından yalnız bilgi hiyerarşisinin alındığını doğrula;
  kalıcı 240 px sidebar veya resmi SIS taklidi ekleme.

**Kanıt (2026-08-10)**: `77cf35e` blueprint sayfasını courseId-bağlı role
çevirdi; kaynak taraması course içi çıplak `useSession()` kullanımını sıfırladı.
`9c2fe23` 375 px, koyu tema, klavye ve görünür odak yolculuklarını E2E'ye aldı;
düşük veri vakası OBS'den uydurma SIS/GPA alanı gelmediğini kanıtlar.

---

## Faz 6 — Yerel release kapıları

- [x] T601 Ayrı `TEST_DB_NAME` ile `apps/api/tests/test_portal.py` hedefli
  paketini çalıştır; paralel worktree'nin DB'sini kullanma.
- [x] T602 Tam backend paketini çalıştır; test sayısını belgeye elle değil
  `scripts/docs_check.mjs --metrikler` kaynağıyla aktar.
- [x] T603 RLS/grant doğrudan testini ve admin kontrolü + REVOKE mutasyonlarını
  çalıştır; kırmızıya dönen nöbetçi olmadan geçiş iddiası kurma.
- [x] T604 `uv run ruff check .`, `ruff format --check .` ve `mypy app` kapılarını
  aynı commit'te geçir.
- [x] T605 Frontend doğrulama kapısını aynı commit'te tamamla:
  hedefli test, tam `bun test lib/`, typecheck ve production build.
- [x] T606 OpenAPI'yi çalışan API'den yeniden üret ve
  `specs/003-product-portal/contracts/api.md` ile alan/path farkını sıfırla.
- [x] T607 Playwright'ta öğrenci, eğitmen, karma rol, admin ve admin olmayan
  yolculuklarını ayrı E2E run kimliğiyle çalıştır ve veriyi run-scoped temizle.
- [x] T608 Tarayıcı ağ kaydında tek `/me/profile` isteğini, admin gate öncesi
  hassas istek olmadığını ve konsolun hatasız olduğunu doğrula.
- [x] T609 `node scripts/docs_check.mjs` kapısını çalıştır; status tablosunu
  yalnız ölçülen kanıtla güncelle.
- [x] T610 Değişiklikleri anlamlı commit(ler)e ayır; çalışma ağacı, upstream,
  push ve PR durumunu ayrı ayrı raporla.

**Faz kapısı**: Hedefli + tam test, RLS mutasyon, gerçek HTTP, build ve tarayıcı
kanıtlarından biri eksikse “yerelde doğrulandı” yazılmaz.

**Kanıt (2026-08-10)**: Portal hedefli backend paketi 21/21; tam backend 846/846;
frontend 309/309 ve typecheck/build; çekirdek RLS 109/109, mutasyon 55/55;
Bilgi İşlem RLS mutasyonu 3/3; varsayılan Playwright 33/33 geçti. Başarısız testte
de teardown çalıştı; son ölçümde run-scoped ders ve audit artığı sıfır, korunan
`COME 331` yerindeydi. OpenAPI uygulamadan 50 yol ve 118 şema ile yeniden üretildi.
Tarayıcı konsol nöbetçisi eksik site simgesi 404'ünü kırmızıya çevirdi; simge
eklendikten sonra aynı Bilgi İşlem yolculuğu temiz konsolla geçti. `docs_check`
canlı sayıları kaynaktan yenileyip 77 belgede fark bırakmadı. Dal küçük amaçlı
commit'lerle `origin/003-product-portal` upstream'ine gönderildi; çalışma ağacı
temizdir. 002'ye merge ve PR bu feature tesliminin parçası olarak yapılmadı;
entegrasyon sahibi tarafından ayrıca yürütülecektir.

---

## Faz 7 — Staging ve production hazırlığı

- [ ] T701 Gerçek Supabase Auth ile öğrenci/eğitmen/admin hesaplarını doğrula;
  production'da `dev:` kimliğinin başlamadığını kanıtla.
- [ ] T702 Gerçek Supabase Storage ile upload → worker → source/citation zincirini
  staging'de doğrula; yerel filesystem sonucunu production kanıtı sayma.
- [ ] T703 Gerçek Groq/Gemini ile grounded cevap, Sokratik ipucu, soru üretimi ve
  grading eval setini çalıştır; fake provider sonucunu gerçek kalite sayma.
- [ ] T704 OpenTelemetry trace/metric/log export'unu içerik allowlist'iyle kur;
  prompt, cevap, chunk, token ve tam e-posta sızıntı testi ekle.
- [ ] T705 API 5xx, readiness, latency, ingestion aging, provider failure ve DB
  pool sinyalleri için staging ölçümünden türetilmiş alarm eşikleri yaz.
- [ ] T706 Supabase production checklist'inde RLS, SSL, network restriction,
  MFA, backup/PITR ve yük maddelerini kanıt bağlantılarıyla kapat.
- [ ] T707 Vercel web ve ACA API/worker staging smoke ile rollback prova et;
  deploy commit/SHA'yı kayıt altına al.
- [ ] T708 Backup/restore tatbikatını ayrı staging verisinde yap; production
  verisini silme ve yalnız “backup açık” ekran görüntüsünü restore kanıtı sayma.
- [ ] T709 Öğrenci ve eğitmen insan eval'ini çok turlu senaryolarla tamamla;
  citation support, pedagojik yardım, abstention ve öğretmen kabul oranını raporla.
- [ ] T710 Production URL'de üç rol yolculuğunu, sağlık/telemetry alarmını ve
  destek runbook'unu doğrula; ancak bundan sonra “production'da kanıtlandı” yaz.

---

## Bağımlılık sırası

```text
Faz 0 sözleşme
  └── Faz 1 migration/güvenlik
      ├── Faz 2 backend API
      │   └── Faz 3 ortak frontend
      │       └── Faz 4 kullanıcı yüzeyleri
      │           └── Faz 5 karma rol/erişilebilirlik
      └──────────────────────────┘
                         └── Faz 6 yerel release
                             └── Faz 7 staging/production
```

### Güvenli paralellik

- T201, T203 ve T207 farklı schema dosyalarında paralel yürüyebilir.
- T301–T303 farklı frontend lib dosyalarında paralel yürüyebilir.
- US1/US2 aynı dashboard dosyasını paylaştığı için ayrı sahiplere verilmemelidir.
- `apps/api/app/main.py`, `apps/api/app/api/deps.py`, `apps/web/components/app-shell.tsx`
  ve OpenAPI ortak dosyalardır; tek entegrasyon sahibi olmalıdır.
- RLS testi ve Playwright aynı paylaşılan DB'de başka worktree ile paralel koşmamalıdır.

---

## Feature kesme çizgisi

003'ün merge için asgari kapsamı Faz 0–6'dır. Faz 7 dış servis yetkisi gerektirir ve
merge sonrasında da açık kalabilir; ancak production release bu faz tamamlanmadan
yapılamaz. Khanmigo/NotebookLM/RAGFlow kalite eşlemesinin daha ileri işleri
[full-product-roadmap.md](full-product-roadmap.md) içinde sonraki dalgalara ayrılmıştır.
