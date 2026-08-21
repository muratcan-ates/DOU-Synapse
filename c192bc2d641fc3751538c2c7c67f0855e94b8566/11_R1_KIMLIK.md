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
