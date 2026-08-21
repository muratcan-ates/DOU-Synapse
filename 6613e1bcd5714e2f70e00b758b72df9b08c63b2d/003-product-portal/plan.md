# Implementation Plan: Rol Bazlı Ürün Portalı

**Branch**: `003-product-portal`
**Base**: `b8da84e`
**Date**: 2026-08-10
**Spec**: [spec.md](spec.md)

**Input**: [spec.md](spec.md) · [constitution.md](../../.specify/memory/constitution.md)
v1.1.0 · 002 production-hardening belgeleri

---

## 1. Özet

003, çalışan ders içi araçların önüne üç ürün yüzeyi koyar:

1. rol bazlı öğrenci/eğitmen dashboard'u,
2. sunucudan doğrulanan profil ve mevcut veri hakkı akışına giriş,
3. akademik içeriğe erişim vermeyen salt-okunur platform admin konsolu.

Teknik yaklaşım: **mevcut Next.js/FastAPI/PostgreSQL yapısını uzat, ikinci bir
uygulama çatısı kurma**. Dashboard toplaması API'de yapılır; istemci beş ayrı listeyi
çekip birleştirmez. Profil tek context üzerinden AppShell ve sayfalar arasında
paylaşılır. Platform adminliği course membership'e eklenmez; ayrı, uygulama yazmasına
kapalı bir operatör ilişkisidir.

---

## 2. Teknik bağlam

| Alan | Karar |
|---|---|
| Dil/sürüm | Python 3.12 · TypeScript 5 |
| Frontend | Next.js 16.3 App Router · React 19.2 · Tailwind 4 · Bun |
| Backend | FastAPI · SQLAlchemy 2 async · Pydantic |
| Veri | PostgreSQL 16 · pgvector · düz SQL migration · RLS |
| Kimlik | Supabase Auth; yerel geliştirmede `dev:` yolu production'da kapalı |
| Depolama | Yerelde filesystem adapter; production hedefi Supabase Storage |
| AI | LiteLLM · Groq/Gemini · fastembed `multilingual-e5-large` |
| Test | pytest · ruff · mypy · Bun test · Next build · Playwright · psql RLS/mutasyon |
| Hedef hosting | Vercel web · Azure Container Apps API/worker · Supabase DB/Auth/Storage |

**Yeniden yazım kararı**: HTML/CSS zaten React bileşenlerinin çıktısıdır. “HTML/CSS/
React'e geçmek” diye ayrı bir migration yoktur; ürün hâlihazırda React/Next.js'tir.
Streamlit veya Gradio'ya dönmek rol bazlı portalı, erişilebilirliği ve production
operasyonlarını geriye götürür.

---

## 3. Mimari

```text
Tarayıcı
  └── Next.js App Router
      ├── /dashboard        öğrenci + eğitmen özetleri
      ├── /profile          kimlik + ders rolleri + veri hakları
      ├── /admin            salt-okunur operasyon konsolu
      └── /courses/{id}/*   mevcut ders içi ürün
             │
             ▼ Bearer token
FastAPI
  ├── /me/profile
  ├── /dashboard
  ├── /admin/overview
  ├── /admin/users
  ├── /admin/courses
  ├── /admin/requests
  └── /admin/ingestion
             │
             ▼ dou_app + app.current_user_id
PostgreSQL 16
  ├── mevcut RLS'li akademik tablolar
  ├── platform_admins (RLS ENABLE, FORCE değil; uygulama grant'i yok)
  ├── platform_admin_access_audit (kapalı, append-only erişim kararı izi)
  └── dar SECURITY DEFINER admin projeksiyonları
```

### 3.1 Yetki sınırı

- `PrincipalDep`: kimlik.
- `CourseMemberDep` / `CourseInstructorDep`: akademik ders yetkisi.
- `PlatformAdminDep`: yalnız platform operasyonu.
- `PlatformAdminDep`, course dependency'nin yerine geçmez.
- Admin fonksiyonları `SECURITY DEFINER` olsa da her çağrıda
  `app.is_platform_admin()` kontrolünü kendi içinde tekrarlar.
- API dependency'si izin verilen ve reddedilen her admin endpoint denemesini
  `app.audit_platform_admin_access()` ile ayrı tamamlanan işlemde kaydeder; ana
  isteğin 403/rollback olması reddedilen izi silmez.
- `platform_admins` tablosunda RLS **ENABLE** edilir fakat **FORCE edilmez**.
  Politika yokken FORCE, tablo sahibi olan güvenli yardımcıyı da kör ederdi.
- Güvenlik FORCE'tan değil; PUBLIC, `dou_app` ve `dou_worker` için bütün tablo
  grant'lerinin geri alınması, yazmanın yalnız DBA/operatörde kalması ve dar
  yardımcıların kontrolü tekrar etmesinden gelir.

### 3.2 Veri toplama sınırı

- Dashboard tek endpoint'tir; N+1 istemci çağrısı yoktur.
- Profil yanıtı AppShell, profil ve admin gate tarafından tek provider üzerinden paylaşılır.
- Admin konsolu yetki bilgisi gelmeden admin liste uçlarını çağırmaz.
- Admin sorguları akademik serbest metni seçmez. Şema düzeyinde taşınmayan alan
  sonradan “redact” edilmek zorunda kalmaz.

### 3.3 Arayüz sınırı

- `DESIGN.md` tek tasarım kaynağıdır.
- OBS'nin bilgi hiyerarşisi alınır; görsel dili, eski sidebar'ı ve resmi kayıt
  işlevleri alınmaz.
- Ürün dışı global alanlar üst çubukta; ders içi araçlar mevcut yatay şeritte kalır.
- Admin tablosu yoğun masaüstü kullanıma uygun, mobilde anlamlı kart/overflow
  davranışıyla çalışır.

---

## 4. Constitution check

| İlke | Kapı | Durum |
|---|---|---|
| I. Kaynak Yoksa Cevap Yok | Portal cevap/citation zincirini gevşetiyor mu? | **GEÇTİ.** Portal yalnız mevcut yüzeylere yönlendirir; cevap üretmez. |
| II. İki Katmanlı İzolasyon | Admin akademik RLS'i atlıyor mu? | **GEÇTİ, tasarım koşuluyla.** Admin projeksiyonu yalnız metadata; course içeriği mevcut üyelik kapılarında kalır. |
| III. Ölçmeden İddia Etme | Canlı ortam sonucu varmış gibi yazılıyor mu? | **GEÇTİ.** Status matrisi production kanıtını ayrı tutar. |
| IV. Fail-Closed | Profil/admin durumu belirsizken açılıyor mu? | **GEÇTİ.** Admin gate sonuç gelene kadar liste isteği atmaz. |
| V. Türkçe Birinci Sınıf | Yeni metinler/hatalar? | **GEÇTİ.** Backend zarfı korunur; UI kendi sunucu hatasını uydurmaz. |
| VI. Kapsam Kapıları | Portal, LMS/SIS'e dönüşüyor mu? | **GEÇTİ.** Resmi OBS verileri ve SIS entegrasyonu kapsam dışı. |
| VII. Tasarım Sistemi | Yeni renk/spacing icat ediliyor mu? | **GEÇTİ.** Mevcut token/bileşenler zorunlu. |
| VIII. Doğrulama | Kod varlığı “bitti” sayılıyor mu? | **AÇIK KAPI.** API, RLS, build ve tarayıcı doğrulaması tamamlanmadan hiçbir görev kapanmaz. |
| IX. Git | İzole worktree ve migration sırası? | **GEÇTİ.** `~/code`, feature branch; `0013` rezerve, portal `0014`. |
| X. Demo | Seed ve rol yolculukları var mı? | **AÇIK KAPI.** Öğrenci/eğitmen/admin üçlü demo tarayıcıda prova edilmelidir. |
| XI. Modülerlik | Profil/rol birden çok kez çekiliyor mu? | **GEÇTİ, tasarım koşuluyla.** Ortak provider ve tek dashboard endpoint'i. |

---

## 5. Dosya planı

```text
specs/003-product-portal/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── contracts/api.md
├── quickstart.md
├── tasks.md
└── full-product-roadmap.md

supabase/migrations/
└── 0014_platform_admin_console.sql

apps/api/app/
├── api/
│   ├── profile.py
│   ├── dashboard.py
│   ├── admin.py
│   └── deps.py                 # PlatformAdminDep
├── schemas/
│   ├── profile.py
│   ├── dashboard.py
│   └── admin.py
└── main.py                     # üç router kaydı

apps/api/tests/
└── test_portal.py

apps/web/
├── app/
│   ├── dashboard/{layout.tsx,page.tsx}
│   ├── profile/{layout.tsx,page.tsx}
│   └── admin/{layout.tsx,page.tsx}
├── components/portal/
│   ├── portal-profile-context.tsx
│   ├── portal-metrics.tsx
│   ├── dashboard-course-card.tsx
│   └── admin-data-table.tsx
├── lib/
│   ├── profile.ts
│   ├── dashboard.ts
│   ├── admin.ts
│   └── {profile,dashboard,admin}.test.ts
├── components/app-shell.tsx
└── app/page.tsx                # giriş sonrası /dashboard
```

Bu yapı planlanan hedeftir; dosya listesinde görünmesi tek başına doğrulama değildir.

---

## 6. Uygulama fazları

### Faz 0 - Şartname ve sözleşme

- Sekiz Speckit belgesini aynı terminolojiyle tamamla.
- `0013_chat_feedback.sql` rezervasyonunu açık yaz; portal migration `0014`.
- API örnekleri ile Pydantic/TypeScript alanlarını birebir eşle.

### Faz 1 - Veri ve backend güvenlik çekirdeği

- `platform_admins`, `app.is_platform_admin()` ve dar admin fonksiyonları.
- PUBLIC/`dou_app`/`dou_worker` grant'lerini geri al.
- Profil, dashboard ve admin şemaları/router'ları.
- Admin olmayan, self-promotion ve academic-access negatif testleri.

### Faz 2 - Öğrenci/eğitmen portalı

- Dashboard ve profil istemci sözleşmeleri.
- Ortak profil provider.
- Rol bazlı kurs kartları ve gerçek aksiyonlar.
- Login sonrası `/dashboard` yönlendirmesi.

### Faz 3 - Platform admin konsolu

- Server-derived admin gate.
- Overview + dört güvenli liste.
- Filtre, sayfalama, loading/empty/error/partial durumları.
- Sağlık sinyallerinin uygulama/DB/embedding ayrımı.

### Faz 4 - Ders rolü regresyon kapısı

- Bütün ders ekranlarında `useSession(courseId)` kullanıldığını doğrula.
- Özellikle blueprint ekranındaki courseId'siz kullanım giderilmelidir.
- Aynı kişinin iki derste farklı rolü tarayıcıda kanıtlanmalıdır.

### Faz 5 - Doğrulama ve sözleşme dondurma

- Hedefli backend/frontend testleri.
- RLS doğrudan test ve mutasyon.
- Ruff, mypy, typecheck, production build.
- OpenAPI export ve frontend tip karşılaştırması.
- Playwright: öğrenci, eğitmen, admin, admin olmayan, karma rol.
- 375 px, koyu tema, klavye ve ağ isteği denetimi.

### Faz 6 - Production hazırlığı

- Gerçek Auth/Storage/LLM staging doğrulaması.
- OpenTelemetry instrumentation ve seçilen backend.
- Alarm, SLO, load testi, backup/restore tatbikatı.
- Supabase RLS/SSL/network restriction/MFA/PITR checklist'i.
- Vercel/ACA staging, smoke ve rollback.

Faz 6 dış sistem yetkileri olmadan tamamlanmış sayılmaz.

---

## 7. Sözleşme kararları

1. `PATCH /me/profile` kısmi görünse de bu dikey dilimde tek değiştirilebilir alan
   vardır; gövde `full_name` alanını zorunlu taşır, `null` kabul etmez ve ekstra alanı reddeder.
2. Admin kullanıcı listesi `masked_email`; tam e-posta yalnız kişinin kendi profilinde.
3. Kullanıcı listesi araması query string kullanmaz: `POST /admin/users` JSON
   `{limit, offset, search}` gövdesiyle çalışır. Tam e-posta eşleşmez; böylece
   URL/access loglarında arama PII'si bırakılmaz.
4. Request log anahtarı yalnız `log_id`dir; kullanıcı kimliği/pseudonym,
   prompt veya cevap alanı yoktur.
5. Cevap durumu filtresi mevcut enum'la aynıdır:
   `answered`, `insufficient_context`, `out_of_scope`, `budget_exhausted`.
6. Ingestion filtresi mevcut enum'la aynıdır:
   `pending`, `processing`, `completed`, `failed`.
7. Dashboard `documents_processing`, hem `uploaded` hem `processing` durumunu kapsar.
8. `action_items = documents_processing + documents_failed + draft_questions`.
9. Admin overview sağlık özeti ayrı frontend çağrılarından uydurulmaz; backend
   ölçüm zamanıyla döndürür. Orkestratör için `/health/live` ve `/health/ready` kalır.

---

## 8. Riskler ve geri dönüş

| Risk | Erken işaret | Karşı önlem / geri dönüş |
|---|---|---|
| Admin rolü akademik superuser'a dönüşür | Course endpoint'i üyelik olmadan 200 | Ayrı dependency; negatif test; admin fonksiyonlarının metadata allowlist'i |
| Admin logunda PII sızar | Tam e-posta/UUID/prompt alanı görülür | SQL projeksiyonu düzeyinde seçme; redaction'a güvenme |
| Kullanıcı araması proxy access loguna düşer | URL'de `search=` ve isim/e-posta görülür | `POST /admin/users` JSON gövdesi; query parametresi yok |
| Profil iki kez çekilir | Aynı sayfada iki `/me/profile` isteği | Ortak provider; ağ gözlemi release kapısı |
| Dashboard N+1 olur | Ders sayısı kadar istek | Tek `/dashboard` endpoint'i |
| LocalStorage rolü karma kullanıcıyı yanlış çizer | Blueprint veya admin sekmesi yanlış görünür | Her ders için server role; `useSession(courseId)` taraması |
| Migration sırası çakışır | İki farklı `0013` | Chat feedback `0013`, portal `0014` |
| RLS FORCE güvenli helper'ı kör eder | Admin helper her zaman false/boş | `platform_admins`: ENABLE, FORCE değil; grant'ler kapalı, helper dar |
| Admin konsolu debug paneline dönüşür | Stack trace/raw log görünür | Yalnız güvenli operasyon şemaları; ayrıntı OTel backend'inde |
| Reddedilen admin denemesi rollback ile kaybolur | Audit tablosunda yalnız allowed satır | Audit helper'ını ana istekten ayrı tamamlanan işlemde çağır; allowed/denied testi |
| Portal “production hazır” algısı yaratır | Canlı kanıt olmadan yeşil rapor | Dört seviyeli status matrisi ve KOŞULMADI etiketi |

---

## 9. Uygulama sonrası anayasa yeniden değerlendirmesi

Faz 5 sonunda şu sorular yeniden cevaplanır:

- Admin tablosu FORCE olmadan ama grant'leri kapalı biçimde doğrudan saldırı testini geçiyor mu?
- Platform admin ders üyesi olmadan akademik içeriğe erişemiyor mu?
- Profil ve dashboard başka kullanıcı verisi sızdırmıyor mu?
- Aynı kişi iki derste farklı rolü doğru görüyor mu?
- UI aynı profile iki istek atmıyor mu?
- Hata, loading ve health ekranları ölçülmemiş bir güven iddiası kuruyor mu?

Bu cevapların biri gözlenmediyse ilgili görev açık kalır.
