# R1 — Kimlik ve üretim güvenliği

> **Önce `10_OKU_ONCE_FAZ2.md`.** Bu belge yalnız senin şeridini anlatır.
> Dal: `feat/auth` · Worktree: `~/code/.dou-auth` · Port: **8021**
> Görevler: **T023 (backend ayağı)**, **T051**, `0002` migration + güvenlik sertleştirme

```bash
cd ~/code/dou-lead && git fetch origin
git worktree add ~/code/.dou-auth -b feat/auth origin/main
cd ~/code/.dou-auth/apps/api && uv venv --python 3.12 && uv pip install -e ".[dev]" && cp ../../.env.example .env
uv run pytest -q      # 473 yeşil görmeden başlama
```

---

## Neden bu şerit

Bugün sistem `DEV_AUTH_ENABLED=true` ile koşuyor: `Authorization: Bearer dev:<uuid>`
yazan herkes o kullanıcı oluyor. Yerel geliştirme ve çevrimdışı demo için doğru
karar, ama **teslim edilecek sistemin kimlik katmanı bu değil.** Jüri "kimlik
doğrulaması nasıl çalışıyor" diye sorduğunda gösterilecek şey `dev:` öneki
olamaz.

Ayrıca projenin en güçlü iddiası izolasyon (Anayasa II) ve bu iddianın kanıtı
şu an yalnız yerel veritabanında koşuyor. Üretimde de koştuğunu göstermek T051.

## Sahiplendiğin dosyalar

```
supabase/migrations/0002_supabase_auth_bridge.sql   YENİ (numara sana ayrıldı)
apps/api/app/core/security.py                       MEVCUT — genişlet
apps/api/tests/test_security.py                     YENİ
apps/api/tests/test_auth_bridge.py                  YENİ
supabase/tests/rls_isolation.sql                    MEVCUT — genişlet
supabase/tests/rls_isolation_mutation_check.sh      YENİ (desen: rls_assessment_mutation_check.sh)
docs/security.md                                    YENİ
specs/001-course-assistant-mvp/tasks.md             yalnız T023 ve T051 satırların
```

**Dokunma:** `apps/api/app/api/deps.py` (lider), `config.py` (lider),
`apps/web/**` (lider). `deps.py`'de değişiklik gerekiyorsa raporuna yaz.

---

## İş 1 — `0002_supabase_auth_bridge.sql` (en önce bu)

`0001` şemayı kurdu ve `profiles` tablosunu `auth.users`'a bağlamadı; çünkü o gün
Supabase Auth henüz devrede değildi. Köprü şu:

- `auth.users` içine bir kullanıcı düştüğünde `public.profiles` satırı
  **otomatik oluşsun** (trigger + `security definer` fonksiyon).
- `profiles.id` = `auth.users.id`. E-posta ve ad, `raw_user_meta_data`'dan.
- Aynı kullanıcı için ikinci kez çalışırsa **hata vermesin** (idempotent):
  `on conflict (id) do nothing` ya da `do update`.
- Silme davranışını **açıkça yaz**: `auth.users` silinince profil ne olacak?
  (Öneri: `on delete cascade` DEĞİL — ders geçmişi ve mesajlar profile bağlı;
  kullanıcı silinince akademik kayıt sessizce yok olmamalı. Kararını migration
  yorumunda gerekçelendir.)

**Dikkat:** yerel Postgres'te `auth` şeması ve `auth.users` tablosu YOKTUR — o
Supabase'in şeması. Migration'ın yerel kurulumda da hatasız koşması gerekiyor
(`quickstart.md` bütün migration'ları sırayla koşuyor ve CI de öyle). İki seçenek
var, birini seç ve gerekçesini yaz:

1. `do $$ begin if exists (select 1 from pg_namespace where nspname='auth') then
   ... end if; end $$;` ile koşullu kur.
2. Yerel için `supabase/local_dev_setup.sql`'e sahte bir `auth.users` kur ve
   migration'ı koşulsuz yaz.

Hangisini seçersen seç: **`for f in supabase/migrations/*.sql; do psql ...; done`
sıfırdan hatasız koşmalı.** Bunu gerçekten dene, varsayma.

## İş 2 — `security.py`: gerçek JWT doğrulaması

Şu an `authenticate()` iki yolu destekliyor. Gerçek yolu sağlamlaştır:

- **İmza doğrulaması** `SUPABASE_JWT_SECRET` ile (HS256). Anahtar yoksa ve
  `DEV_AUTH_ENABLED` kapalıysa uygulama **açılmamalı** — bu kural `config.py`'de
  zaten var, bozma.
- **`exp` kontrolü zorunlu.** Süresi geçmiş token 401.
- **`aud` ve `iss` kontrolü.** Supabase `aud: "authenticated"` gönderir.
  Kontrol etmemek, başka bir Supabase projesinin token'ını kabul etmek demektir.
- **`sub`** claim'i UUID olmalı; olmayan token 401.
- Hata mesajları **Türkçe** ve **ayrıntısız**: "token süresi doldu" ile
  "imza geçersiz" arasındaki farkı kullanıcıya söyleme (bilgi sızıntısı),
  loga yaz.

Testler (`test_security.py`) — hepsi DB'siz, saf:
- geçerli token → `Principal`
- süresi geçmiş → 401
- yanlış anahtarla imzalanmış → 401
- `aud` yanlış → 401
- `sub` UUID değil → 401
- algoritma `none` → 401 **(bu testi mutlaka yaz — klasik JWT açığı)**
- `DEV_AUTH_ENABLED=false` iken `dev:` öneki → 401 **(kritik)**

Son madde en önemlisi: dev kimlikleri üretimde kabul edilirse, herkes herkes
olabilir. Bunun testi olmadan bu şerit bitmiş sayılmaz.

## İş 3 — T051: RLS canlılık kanıtı ve mutasyon kontrolü

Şerit 5 `0004`+`0005` için mükemmel bir desen bıraktı:
`supabase/tests/rls_assessment.sql` (58 iddia) +
`rls_assessment_mutation_check.sh` (24 mutasyon). Aynısını **çekirdek şema**
(`0001` + `0003`) için kur.

`supabase/tests/rls_isolation.sql` zaten var ama mutasyon kontrolü yok. Ekle:

- Her politikayı **teker teker boz**, testin KIRMIZI yandığını göster, geri al.
- Bozukken de uygulama katmanının (üyelik kontrolü) tek başına tuttuğunu göster
  — iki katman ayrı ayrı sınanmalı (Anayasa II).
- Kapsam: `courses`, `course_memberships`, `documents`, `chunks`,
  `chat_sessions`, `chat_messages`, `answer_cache`, `request_logs`.

`request_logs`'a özellikle bak: SELECT politikası **bilinçli olarak yok** ve
`chat.py` bu yüzden RETURNING'siz INSERT kullanıyor. Bu davranışın testi olsun —
biri "eksik" sanıp politika eklerse ne bozulacağını test söylesin.

Çıktı: "N/N iddia PASS, M/M mutasyon yakalandı" biçiminde, komutuyla birlikte.

## İş 4 — `docs/security.md`

Jürinin soracağı güvenlik sorularının tek cevap yeri. Yaz:

- Kimlik: Supabase Auth → JWT → `Principal`; dev yolunun ne olduğu ve
  **üretimde neden açılamadığı** (kod referansıyla).
- Yetkilendirme iki katman: uygulama (`CourseMemberDep`) + RLS. Neden ikisi de.
- İzolasyon kanıtı: kaç iddia, kaç mutasyon, hangi komut.
- Prompt injection savunması: ret metinleri **bizim sabitlerimiz**, modelin
  ürettiği metin değil (`api/chat.py`'deki `MESSAGE_*`). Materyalin içine gömülü
  bir talimat ret metnini ele geçiremez.
- Atıf uydurma savunması: `chunk_id` set-membership, deterministik.
- Sızdırılmayan şeyler: sağlayıcı/model adı kullanıcıya gitmez; soru metni
  `request_logs`'a yazılmaz (şemada serbest metin sütunu yok — yapısal önlem).
- Sınırlar (dürüstlük bölümü): istek sınırı **süreç içidir**, çok worker'lı
  kurulumda worker başına uygulanır. Dağıtık sınır Redis ister, kapsam dışı.
- KVKK: hangi kişisel veri tutuluyor, nerede, ne kadar süre.

**Bu belgede iddia ettiğin her şeyin kodda karşılığı olmalı.** Olmayanı
"uygulanmadı" diye yaz.

## İş 5 — anahtar geldiğinde (en sona bırak)

Gerçek Supabase projesi ve anahtarları olmadan yapamayacağın tek iş budur:
`0002`'nin gerçek `auth.users` üstünde koşması ve uçtan uca bir giriş.
Anahtar yoksa: migration'ı yerelde sahte `auth` şemasıyla koştur, testleri yaz,
**"gerçek Supabase'de KOŞULMADI" diye kayda geç** ve devam et.

## Lidere iletmen gerekenler

Rapor sonunda ayrı başlık altında:
- Frontend giriş ekranının hangi çağrıyı yapması gerektiği (tam imza + örnek
  gövde + dönen alanlar). Lider `apps/web/app/page.tsx`'i buna göre yazacak.
- `deps.py`'de değişiklik gerekiyorsa tam yaması.
- `.env.example`'a eklenmesi gereken değişkenler (dosya lider'in değil, senin
  ekleyebileceğin bir dosya DEĞİL — listesini ver).

## Bitti sayılma ölçütün

- [ ] `0002` sıfırdan kurulumda hatasız koşuyor (gerçekten denendi)
- [ ] `test_security.py` yedi vakayı da kapsıyor, `dev:` öneki üretimde reddediliyor
- [ ] `rls_isolation.sql` + mutasyon betiği, sayılarıyla raporlanmış
- [ ] `docs/security.md` yazıldı ve her iddiasının kod karşılığı var
- [ ] 473+ test yeşil, mypy temiz, ruff temiz
- [ ] `tasks.md`'de T023/T051 satırların DONE notuyla güncel

---

# R1 raporu — 9 Ağustos 2026

Dal: `feat/auth` · Worktree: `~/code/.dou-auth` · Taban: `c4d4c7b` (rebase'li)
Doğrulama: **527 test yeşil**, mypy temiz (59 dosya), ruff temiz.

## Bitti sayılma ölçütü

- [x] `0002` sıfırdan kurulumda hatasız koşuyor — gerçekten denendi (boş veritabanı,
      `0001`→`0005` sırayla; ayrıca ikinci kez koşturuldu, idempotent)
- [x] `test_security.py` yedi vakayı da kapsıyor (25 test); `dev:` öneki
      `DEV_AUTH_ENABLED=false` iken reddediliyor
- [x] `rls_isolation.sql` + mutasyon betiği: **98 iddia, 52/52 mutasyon**
- [x] `docs/security.md` yazıldı; iddiaların kod karşılığı satır numaralı,
      karşılığı olmayanlar §8'de "uygulanmadı" olarak yazılı
- [x] `tasks.md` T023/T051 satırları ölçülmüş notla güncel — **kutular AÇIK**
      (T023'ün frontend ayağı sizde, T051'in görev metni prod koşusu istiyor)

## Yapılanlar

**`supabase/migrations/0002_supabase_auth_bridge.sql`** — koşullu kurulum (belgedeki
1. seçenek). Gerekçe: migration klasörü üç yerde tek başına uygulanıyor (conftest'in
`database` fixture'ı, CI'nin `rls_check` adımı, quickstart) ve hiçbirinde
`local_dev_setup.sql` koşmuyor; sahte `auth.users`'ı oraya koymak üçünü de düşürürdü.
Bedeli — köprünün yerelde kendini sınamaması — fonksiyonları trigger'dan ayırarak
ödendi: testler `app.install_auth_user_bridge()`'i çağırıyor, kendi trigger'ını
yazmıyor.

**Silmede cascade YOK.** `courses.created_by` ve `documents.uploaded_by` zaten
`ON DELETE RESTRICT`; proje bu tarafı 0001'de seçmişti. Kabul edilen bedel: aynı
e-postayla yeniden kayıt düşer, çözüm operatör kararıdır. Testi var.

**`app/core/security.py`** — `exp`/`sub`/`aud`/`iss` zorunlu claim listesine alındı
(PyJWT eksik claim'i sessizce geçiyordu), `none` algoritması izin listesinden
eleniyor, bütün ret sebepleri tek kullanıcı mesajına indirildi ve ayrım `app.auth`
loguna taşındı.

**`supabase/tests/rls_isolation.sql`** 8 → 98 iddia; **`rls_isolation_mutation_check.sh`**
yeni (52 mutasyon, 4'ü yardımcı fonksiyon). **`apps/api/tests/test_isolation_layers.py`**
yeni: API'yi BYPASSRLS rolüne çevirip uygulama katmanının tek başına tuttuğunu ölçüyor.

**`docs/security.md`** yeni.

## Canlı koşu (Anayasa VIII)

Sunucu `ENVIRONMENT=local`, `DEV_AUTH_ENABLED=false`, gerçek `SUPABASE_JWT_SECRET`
ile ayağa kaldırıldı ve `GET /courses` gerçek token'larla çağrıldı:

| İstek | Sonuç |
|---|---|
| Geçerli Supabase biçimli JWT | **200**, ders döndü |
| Süresi geçmiş | 401, tek mesaj |
| Yanlış anahtarla imzalı | 401, tek mesaj |
| `aud=anon` | 401, tek mesaj |
| `iss` claim'i yok | 401, tek mesaj |
| `alg=none` (imzasız) | 401, tek mesaj |
| `dev:<uuid>` | 401, tek mesaj |

Logda altı ayrı ret sebebi görünüyor, **token görünmüyor** (arandı, yok). Ayrıca
`ENVIRONMENT=production` + `DEV_AUTH_ENABLED=true` ve "secret yok + dev kapalı"
konfigürasyonlarının ikisi de ayarlar yüklenirken reddedildi.

**Port notu:** belgede R1'e 8021 verilmiş ama o port bu makinede başka bir süreç
tarafından tutuluyordu (`lsof` sandbox'ta sahibini göstermiyor). Koşu **8121**'de
yapıldı; başka şeridin portuna girilmedi.

## Ölçerken bulunan üç şey

**1. `0003`'ün "`INSERT ... RETURNING` yapılamaz" cümlesi artık dar.** `0005`
eğitmene kendi dersi için SELECT açtığından eğitmen bağlamında RETURNING geçiyor
(psql'de doğrulandı). Kod etkilenmiyor — `chat.py` `.inline()` ile RETURNING
üretmiyor, rolden bağımsız. `0003` main'de olduğu için dokunulmadı; iddia testte
öğrenci bağlamıyla sınırlandı. **Karar sizin:** `0003`'ün yorumuna bir düzeltme
notu düşmek isteyebilirsiniz.

**2. SELECT politikası, UPDATE/DELETE politikasını maskeliyor.** PostgreSQL satırı
bulmak için SELECT politikalarını da uyguluyor ve UPDATE'te güncellenmiş satırın da
onlardan geçmesini istiyor. Sonucu: "başkasının satırını değiştiremez" biçimindeki
iddialar UPDATE politikasını hiç ölçmüyor. Bu, `rls_assessment.sql`'i de ilgilendirir
ama oradaki iddialar zaten mutasyonla doğrulanmış olduğu için bir işlem gerekmiyor;
yeni iddia yazan herkesin bilmesi gereken bir tuzak (rls_isolation.sql, OKUMA NOTU 2).

**3. Köprünün iki tasarım hatası testle yakalandı**, ikisi de üretimde ancak gerçek
bir kayıt denemesiyle görülürdü: backfill `SECURITY DEFINER` iken köprü rolünün
`auth` şemasına yetkisi olmadığı için düşüyordu; ve üretimde tetikleyen rol
(`supabase_auth_admin`) `app` şemasına yetkisiz olduğu hâlde trigger'ın çalışması
gerekiyordu — `dou_app` ile yazılan test bunu kanıtlamıyordu (0001 ona USAGE veriyor).

## Size iletmem gerekenler

### 1. Frontend giriş ekranının yapması gereken çağrı

Backend'in **giriş ucu yoktur ve olmayacaktır**: token'ı Supabase üretir, backend
yalnız doğrular. Akış:

```ts
// apps/web/lib/supabase.ts (sizde)
const { data, error } = await supabase.auth.signInWithPassword({ email, password })
// data.session.access_token  → her API isteğinde:
//   Authorization: Bearer <access_token>
```

Backend'e giden istek ve dönen alanlar (bugün çalışan uç):

```
GET /courses
Authorization: Bearer <supabase access_token>

200 → [{ "id": uuid, "code": string, "title": string,
          "created_at": iso8601, "role": "instructor" | "student" }]
401 → { "error": { "code": "unauthenticated",
                   "message": "Oturumunuz geçerli değil. Lütfen tekrar giriş yapın." } }
```

**Arayüz için üç kural:**

1. **401 geldiğinde tek davranış: oturumu temizle ve giriş ekranına dön.** Backend
   artık "süresi doldu" ile "geçersiz" arasında ayrım YAPMIYOR (bilgi sızıntısı) —
   arayüz bu ayrımı beklemesin. Yenileme kararını `supabase-js` kendi verir.
2. **Backend'in mesajını göster, kendi metnini uydurma** (Anayasa V).
3. **Profil satırı otomatik oluşur** (0002 trigger'ı). Giriş sonrası ayrı bir
   "profil oluştur" çağrısı YOK. Yalnız gerçek Supabase'de; yerelde `dev:<uuid>`
   yolunda profil hâlâ elle/seed ile yazılıyor.

Token'ı `localStorage`'a siz koymayın; `supabase-js` kendi saklamasını kullanır.

### 2. `deps.py` yaması — GEREKMİYOR

`deps.py`'de değişiklik gerekmedi; `get_principal` `authenticate()`'i çağırıyor ve
sertleştirme tamamen `security.py`'nin içinde kaldı. Dokunulmadı.

### 3. `config.py`'ye eklenmesi gereken alan (bir tane)

```python
    #: Beklenen `iss` claim'i: `https://<proje-ref>.supabase.co/auth/v1`.
    #: Tanımsızsa `iss`in yalnız varlığı sınanır, değeri sabitlenmez.
    jwt_issuer: str | None = None
```

`security.py` bu alanı `getattr` ile okuyor, yani alan eklendiği an ek bir
değişiklik olmadan devreye girer. Testi bugünden yazılı
(`test_security.py::TestIssuerSabitleme`, `Settings` alt sınıfıyla ölçüldü).
Alan eklenince `test_issuer_ayarli_degilken_iss_degeri_sabitlenmez` testinin
gerekçesi kalkar — o testi silmek ve `docs/security.md` §8.1'i kaldırmak gerekir.

### 4. `.env.example`'a eklenmesi gerekenler

```bash
# Supabase → Project Settings → API → Project URL'den türetilir:
# https://<proje-ref>.supabase.co/auth/v1
# Boş bırakılırsa `iss` claim'inin yalnız varlığı sınanır, değeri sabitlenmez.
SUPABASE_JWT_ISSUER=
```

Frontend tarafı için (sizin dosyanız, sizin kararınız): `NEXT_PUBLIC_SUPABASE_URL`,
`NEXT_PUBLIC_SUPABASE_ANON_KEY`.

### 5. CI'ye eklenmesi gereken adım

`.github/workflows/ci.yml`'deki "RLS izolasyon kanıtı" adımı bugün tek bir
politikayı elle bozup FAIL arıyor. Artık betik var; o elle bozma bloğu şununla
değiştirilebilir:

```yaml
          psql -d rls_check -f supabase/tests/rls_isolation.sql 2>&1 | tee /tmp/rls.out
          if grep -q FAIL /tmp/rls.out; then echo "RLS izolasyonu bozuk"; exit 1; fi
          supabase/tests/rls_isolation_mutation_check.sh rls_check
```

**Dikkat:** mutasyon betiği, şablon veritabanı YOKSA kurar, VARSA olduğu gibi
kullanır. CI'da `rls_check` her koşuda yeniden kuruluyor, sorun yok; ama yerelde
migration değiştikten sonra `dropdb rls_isolation_template` demeyi unutmayın —
yoksa eski şemayla koşar. Aynı tuzak `rls_assessment_template` için de var.

### 6. Bir de küçük bir gözlem (`main.py`, sizin dosyanız)

CORS'ta `allow_credentials=True` var ama sistem kimliği `Authorization` başlığıyla
taşıyor, çerezle değil. Kaynak listesi sabitlendiği için bu bir açık değil, gereksiz
bir genişlik. `docs/security.md` §8.5'te yazılı; kararı size bırakıyorum.

## Yapılmayanlar (İş 5 ve diğerleri)

- **Gerçek Supabase üstünde koşulmadı** — proje ve anahtar yok. `0002` sahte bir
  `auth.users` ve yetkisiz taklit rolle sınandı; sınanan kod üretimde koşacak kodun
  aynısı ama Supabase'in şeması/izinleri gerçek değil. Anahtar geldiğinde yapılacak
  tek iş: migration'ı gerçek projeye uygulamak, bir kullanıcı kaydı açmak ve
  `profiles` satırının oluştuğunu görmek.
- **T051'in prod koşusu yapılmadı** — aynı sebep. Yerel kanıt tam.
- **Güvenlik başlıkları (HSTS/CSP) yok** — dağıtım katmanı, R3'ün alanı.
- **İstek sınırı süreç içi** — dağıtık sınır Redis ister, kapsam dışı.
- **KVKK**: tanımlı saklama/imha süresi yok ve LLM sağlayıcılarına yurt dışı
  aktarımı için aydınlatma metni repoda yok. İkisi de ürün kararı; `docs/security.md`
  §9'da açıkça yazılı.
