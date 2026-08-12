# Codex Session Recovery — 2026-08-12

> Compact, privacy-safe recovery archive. This is not a byte-for-byte transcript backup.
> User messages, prompts, tool payloads, hidden reasoning, and raw transcripts are excluded.

## Recovery snapshot

- Root task retained locally: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Descendant session records indexed: **128**
- Source footprint represented: **22.45 GiB**
- Closed footprint eligible for removal after remote verification: **22.45 GiB**
- Repository branch at capture: `archive/codex-session-recovery-2026-08-12`
- Repository commit at capture: `50543c4f555a9d21de288040c10b27621e93172a`
- Remote main at capture: `2c178861a3e484af8643f999f210db040eb84e68`

The product source code remains authoritative in Git. This document preserves only the final
technical handoff of each closed child agent so implementation decisions remain searchable.

## Repository checkpoint

```text
50543c4 chore(ai): bind the verified agent candidate evidence
59eb0d8 docs: record the verified DOU-Synapse journey
39ae25e feat(web): refine the role-aware academic studio
e08d6e8 fix(agent): close privacy and RLS evidence gaps
fc5bd59 Record the feature branch delivery
aca3b93 Run the course agent mutation gate in CI
0f47122 Close the local course agent evidence gates
df4776d Record the R3 agent evidence and mutation gates
e6a17cd Specify and document the course agent safeguards
9941979 Add the student coach and instructor assistant UI
7be397d Build the role-aware course agent backend
7c1c219 Record the governance branch delivery evidence
```

## Agent handoffs

<details>
<summary><code>guardian</code> — 1.0 MiB — closed</summary>

- Session: `019fe739-576d-7d60-a5c8-0947585f9a3d`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-09T15:52:02.670Z`
- Source log: `rollout-2026-08-09T18-52-02-019fe739-576d-7d60-a5c8-0947585f9a3d.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>guardian</code> — 13.7 MiB — closed</summary>

- Session: `019fe857-8a45-7882-a5b5-39d9bc59f0da`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-09T21:04:38.981Z`
- Source log: `rollout-2026-08-10T00-04-38-019fe857-8a45-7882-a5b5-39d9bc59f0da.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/verify_branch_deletion (Avicenna)</code> — 96.1 MiB — closed</summary>

- Session: `019feca0-db32-7292-890d-de9ffff65519`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:03:12.690Z`
- Source log: `rollout-2026-08-10T20-03-12-019feca0-db32-7292-890d-de9ffff65519.jsonl`

<pre>
Bağımsız doğrulama sonucu: Claude’un commit kapsamı kararı doğru; önerdiği yerel silme komutunda ise önemli bir hata ve veri kaybı caveat’i var.

### Uzak dallar

GitHub’dan salt-okunur alınan güncel uçlar:

```text
002-production-hardening          89a5d456
feature/exam-blueprint            827b8bb4
hardening/frontend-reliability    d0bb3de1
hardening/runtime-safety          6b93fc42
```

Kullandığım doğrulamalar:

```bash
git ls-remote --heads origin
git rev-list --left-right --count 002-production-hardening...origin/&lt;dal&gt;
git merge-base 002-production-hardening origin/&lt;dal&gt;
git cherry 002-production-hardening origin/&lt;dal&gt;
```

Sonuçlar:

| Dal | `rev-list` | Merge-base | `git cherry` | Hüküm |
|---|---:|---|---|---|
| runtime | `16  0` | dal ucu `6b93fc4` | boş | Tamamen `002` içinde |
| frontend | `17  0` | dal ucu `d0bb3de` | boş | Tamamen `002` içinde |
| blueprint | `1  0` | dal ucu `827b8bb` | boş | Tamamen `002` içinde |

Dolayısıyla bu üç uzak dal, commit kaybı olmadan silinebilir. Commitler `002` üzerinden ulaşılabilir kalır.

### Yerel dallar ve worktree’ler

Üç gerçek worktree temiz:

```text
dou-runtime-safety        clean
dou-frontend-reliability  clean
dou-exam-blueprint        clean
```

Tracked veya untracked değişiklik yok. Boyutları sırasıyla yaklaşık `985M`, `785M`, `1.0G`.

`evaluation/human-study-prep` özel durum:

```bash
git rev-list --left-right --count \
  002-production-hardening...evaluation/human-study-prep
# 22  1

git cherry 002-production-hardening evaluation/human-study-prep
# - 38bf0d8
```

Bu dal literal olarak `002`nin atası değil; fakat tek özgün görünen commit’i `002`deki `2912056` ile aynı yamadır:

```text
38bf0d8 patch-id = 6a611285...
2912056 patch-id = 6a611285...
```

Yani içerik kaybı yok, ancak burada güvence “atalık” değil “patch eşitliği”.

### Kritik düzeltmeler

1. `$HOME/code/dou-human-eval` mevcut değil ve kayıtlı worktree değil. Claude’un `&amp;&amp;` zincirindeki:

```bash
git worktree remove ../dou-human-eval
```

komutu başarısız olur; sonrasındaki `git branch -D ...` hiç çalışmaz. Bu adım çıkarılmalı.

2. Worktree’ler tracked kod bakımından temiz olsa da ignored dosyalar içeriyor. Özellikle runtime worktree’de `apps/api/storage` altında toplam `80K` büyüklüğünde sekiz PDF var. Hash karşılaştırmasında `dou-lead` depolamasında eşleri yok. Zaman/boyutları test çıktısına benziyor ama bunun üretim verisi olmadığını git kanıtlayamaz. Worktree kaldırılmadan önce silinebilir test artığı oldukları doğrulanmalı veya kopyalanmalı.

3. Frontend ve blueprint worktree’lerindeki `.env` dosyaları `dou-lead/apps/api/.env` ile byte-byte aynı; özgün ayar kaybı yok.

4. “Dal silme geri alınamaz” teknik olarak tam doğru değil: bu dal ref’leri, SHA’lar `002`de erişilebilir kaldığı sürece yeniden yaratılabilir. Asıl geri döndürülmesi zor işlem worktree içindeki ignored dosyaların silinmesidir.

Net hüküm: üç uzak dalın ve dört yerel dalın kod içeriği açısından silinmesi güvenli. Fakat `dou-human-eval` kaldırma adımı atlanmalı ve runtime içindeki sekiz ignored PDF önce bilinçli biçimde ele alınmalı. Hiçbir silme, merge, push veya dosya değişikliği yapmadım.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.1 MiB — closed</summary>

- Session: `019feca0-dbeb-7a32-908e-8c422acddaf3`
- Parent: `019feca0-db32-7292-890d-de9ffff65519`
- Started: `2026-08-10T17:03:12.875Z`
- Source log: `rollout-2026-08-10T20-03-12-019feca0-dbeb-7a32-908e-8c422acddaf3.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/verify_source_truth (Curie)</code> — 96.5 MiB — closed</summary>

- Session: `019feca0-f0a5-7f70-9642-416f79c1b9d9`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:03:18.182Z`
- Source log: `rollout-2026-08-10T20-03-18-019feca0-f0a5-7f70-9642-416f79c1b9d9.jsonl`

<pre>
Hüküm: Claude’un düzeltilmiş ana kararı doğru; entegrasyon kaynağı `002-production-hardening` kalmalı.

- Ortak ata `895eedf`. `002`, bunun üstünde tamamlanan üç blueprint commitini (`6453ee7`, `c61ba5d`, `827b8bb`) ve merge’i taşıyor.
- Codex dalı aynı yarım blueprint noktasından ayrılıp kendi `17ede4a` uygulamasını yazmış. Onu ana kaynak yapmak doğrulanmış blueprint soyunu değiştirecekti.
- Fakat veritabanı gerekçesi düzeltilmeli: `0008_exam_blueprint.sql`, `895eedf`, `origin/002` ve Codex dalında aynı Git blob’u: `dfd3249…`. Risk migration uyumsuzluğu değil; migration sonrasındaki API/frontend uygulamasının ve doğrulama geçmişinin ayrışmasıdır.

Docs duplication da doğrulandı:

- Codex’teki `b2caeed`, Claude docs dalındaki `f5ea3f6` ile birebir aynı patch-id’ye sahip: `ff73f336…`.
- `8866052` ile `docs/refresh-after-merge` ucundaki `a7b97d8` aynı konu/tarih ve değişen 23 dosyanın 19’unda aynı son blobu taşıyor. Dört metin dosyası farklı tabana oturduğu için ayrışıyor.
- Bu nedenle Codex docs zinciri topluca alınmamalı.

Beş cherry-pick planındaki önemli düzeltme:

- `fa44b9e`, `35a952d`, `1b56a15`, `973a678` özellik olarak doğru seçilmiş. `973a678` için `course-nav.tsx` ve route testi çatışması gerçek; küçük ama semantik çözüm gerektiriyor.
- `4d82ae3` policy için kod bağımlılığı değil; yalnız event-loop ölçümünü tek koşudan üç turun medyanına geçiriyor. Bilinen CI oynaklığı varsa ayrıca alınması mantıklı.
- `8f13045` normal cherry-pick edilemez. Geçici kopyada önceki dört özellikten sonra uyguladığımde **19 çatışma** verdi: `chat.py`, `api.ts`, ders/giriş sayfaları, RLS testi, docs/spec/OpenAPI dahil.
- Daha önemlisi `8f13045`, doğrudan `973a678` üstünde değil; parent zincirinde `e284b30` var. Parola ekranları `e284b30` tarafından eklenen `apps/web/lib/supabase.ts` ve `@supabase/supabase-js` bağımlılığını import ediyor. `e284b30` alınmadan beşli plan frontend build’ini kırabilir.

`0010/0011` eksikliği kasıtlı erteleme olarak belgelenmemiş; mevcut plana göre entegrasyon açığıdır:

- `002` planı sıralamayı bağlayıcı yazıyor: `0008 → 0009 → 0010 → 0011`.
- Seçilen commitler `0009`, `0012`, `0013` getiriyor.
- `0010` ingestion retry, `0011` pagination, Supabase istemcisi, E2E cleanup ve ilgili runtime/frontend işleri yalnız `e284b30` içinde.
- `origin/002` üzerinde T701–T704, T801–T802 ve T901–T905 açık; `e284b30` bunları DONE’a çeviriyor. Production hedefinde bunları sessizce atlamak doğru değil.

Önerilen sıra:

1. `002` kaynak olarak kalsın.
2. İlk dört özellik semantik çatışmalar çözülerek alınsın.
3. `e284b30`, tek büyük commit olarak değil; auth/Supabase, pagination, ingestion retry ve E2E cleanup parçalarına ayrılarak entegre edilsin.
4. Ardından `8f13045`in feedback/RLS/UI kısmı alınsın.
5. Docs/spec/OpenAPI elle seçilmesin; en sonda güncel ağaçtan yeniden üretilsin.

Canlı not: İnceleme sırasında Claude yerel `002`yi ilerletti. Son gördüğüm temiz uç `d25ce05`; security, source lab, privacy ve policy artık yerel `002` üzerinde, remote hâlâ `89a5d45`. Aktif worktree’ye ben dokunmadım; çatışma ölçümü yalnız `/private/tmp` kopyasında yapıldı.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:795-800|note=[parallel DOU worktree and unique database safeguards]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.2 MiB — closed</summary>

- Session: `019feca0-f11b-79c2-8e52-ff73d6aff411`
- Parent: `019feca0-f0a5-7f70-9642-416f79c1b9d9`
- Started: `2026-08-10T17:03:18.299Z`
- Source log: `rollout-2026-08-10T20-03-18-019feca0-f11b-79c2-8e52-ff73d6aff411.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/verify_ci_and_order (Socrates)</code> — 96.3 MiB — closed</summary>

- Session: `019feca1-0508-7590-bf66-d1079bf5cfe2`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:03:23.400Z`
- Source log: `rollout-2026-08-10T20-03-23-019feca1-0508-7590-bf66-d1079bf5cfe2.jsonl`

<pre>
Salt-okunur doğrulama sonucu:

- `origin/main = ae93417`
- `origin/002-production-hardening = 89a5d45`
- `main`, `002`nin atası; `002` uzakta **31 commit ileride**.
- Açık PR yok.
- `002` ucunda **hiç GitHub check-run yok**.
- CI yalnız `push: main` ve `pull_request` ile çalışıyor.
- Main’in son CI’ında web başarılı; API testleri ve Docker build başarısız; E2E atlanmış. Loglar kimlik doğrulama olmadan 403 verdiği için kök neden doğrulanamadı.

Bu nedenle **002 → main kesinlikle PR üzerinden gitmeli**. Doğrudan push, CI’ı ancak main değiştikten sonra çalıştırır.

Doğru entegrasyon sırası:

1. `002-production-hardening` ana entegrasyon tabanı.
2. Codex parçaları semantik çatışma çözümüyle alınır.
3. Docs/görseller güncel ürün üstünde tamamlanır.
4. `refactor/modularize`, sabit `89a5d45`e değil, bütün bu entegrasyonlardan sonraki **son 002 ucuna** rebase edilir. Şimdiden 002 ile birden fazla merge-tree çatışması var.
5. OpenAPI, docs_check, tam testler.
6. `002 → main` PR ve yeşil CI.

Aktif worktree’ye başka süreç müdahale ediyor. Son gözlemimde yerel 002, origin’den dört commit ilerideydi:

- `8b0c154` güvenlik başlıkları
- `b28e389` kaynak laboratuvarı
- `bfeb8fb` KVKK
- `1f109b9` ders AI politikası

Ayrıca `apps/api/tests/test_error_envelope.py` değiştirilmişti; dolayısıyla şu an aynı worktree’ye ikinci işlem sokulmamalı.

Önemli düzeltme: yalnız beş commit planı **production kapsamını tamamlamıyor**. `e284b30` içinde olup bu seçkide dışarıda kalanlar:

- `0010_ingestion_retry.sql` ve ingestion retry/backoff,
- `0011_pagination_indexes.sql` ve beş liste ucunda pagination,
- E2E `globalTeardown` ve güvenli temizlik komutu,
- production storage düzeltmeleri,
- ilgili pagination/retry frontend ve test altyapısı.

Bunlar `origin/002` görev listesinde hâlâ açık; `e284b30`da tamamlanmış. Dolayısıyla ya `e284b30`daki bu parçalar konu bazlı, izlenebilir commitlerle ayrıca taşınmalı ya da ürün “production tamamlandı” diye işaretlenmemeli. Özellikle ortak veritabanını kirleten E2E cleanup ve sınırsız listeleri düzelten pagination release öncesi alınmalı.

`8f13045` de doğrudan bağımsız bir commit değil; ebeveyni `e284b30` ve dokunduğu 31 dosyanın tabanı 002’den farklı. Kör cherry-pick yerine semantik çözüm ve tam test şart.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:922-944|note=[parallel modularization base and final-tip rebase safeguards]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019feafc-8971-7ca0-a58d-f091f3fde5ea
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.3 MiB — closed</summary>

- Session: `019feca1-0580-7830-9847-3bdf171b7a3f`
- Parent: `019feca1-0508-7590-bf66-d1079bf5cfe2`
- Started: `2026-08-10T17:03:23.520Z`
- Source log: `rollout-2026-08-10T20-03-23-019feca1-0580-7830-9847-3bdf171b7a3f.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>guardian</code> — 0.4 MiB — closed</summary>

- Session: `019feca3-09c5-7122-ba08-54cc95f31352`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:05:35.685Z`
- Source log: `rollout-2026-08-10T20-05-35-019feca3-09c5-7122-ba08-54cc95f31352.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/frontend_audit (Heisenberg)</code> — 105.2 MiB — closed</summary>

- Session: `019fecb3-5055-7b51-8f09-9d0c2a679655`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:23:22.360Z`
- Source log: `rollout-2026-08-10T20-23-22-019fecb3-5055-7b51-8f09-9d0c2a679655.jsonl`

<pre>
## Frontend mimari denetimi

Design read: Öğrenci için mobil öncelikli, eğitmen ve admin için masaüstü yoğunluklu, sakin ve kurumsal bir ürün arayüzü. OBS’nin bilgi mimarisinden yararlanılmalı; eski görsel dili kopyalanmamalı.

### Güncel kaynak ve çakışma durumu

- Doğru kaynak worktree: `$HOME/code/dou-lead`
- Dal: `002-production-hardening`
- HEAD: `d25ce05`
- Çalışma ağacı temiz.
- Dal `origin/002-production-hardening`dan dört commit ileride.
- Hiçbir dosya değiştirmedim.

Yeni arayüz çalışması `d25ce05` tabanından ayrı bir worktree’de başlamalı. `refactor/modularize` şu frontend dosyalarına dokunuyor; yeni panel şeridi bunlardan uzak durmalı:

- `lib/analytics.ts`
- `lib/chat.ts`
- `lib/exam.ts`
- `lib/labels.ts`
- `lib/questions.ts`
- `lib/source.ts`

### Mevcut frontend gerçeği

- Next.js 16.3, React 19.2 ve Tailwind 4 kullanılıyor.
- Hazır component, ikon, grafik veya veri tablosu kütüphanesi yok.
- Güçlü bir yerel tasarım sistemi mevcut: açık ve koyu tema, ölçülmüş kontrast, tek kırmızı vurgu, 44px dokunma hedefi, düşük hareket.
- `DESIGN.md:250` OBS benzeri sabit 240px sol menüyü bilinçli olarak reddediyor. Ders içi yatay sekmeler korunmalı.
- Mevcut tekrar kullanılabilir parçalar:
  - `AppShell`
  - `CourseNav`
  - `PageHeader`
  - `MetricRow`
  - `Loading`
  - `ErrorNote`
  - `Button`
  - `Card`
  - `Badge`
  - `ConfirmAction`
  - `EmptyState`
  - `Field`
  - `Input`
  - `useResource`
  - ortak `api` istemcisi

Mevcut ekranlar dersler, materyaller, sohbet, sınav, soru havuzu, blueprint, analitik, katılımcılar, AI politikası, retrieval laboratuvarı ve KVKK/veri haklarını kapsıyor.

Ancak:

- `/account` bir profil ekranı değil; yalnız veri indirme, sohbet silme ve anonimleştirme içeriyor.
- `/dashboard`, `/profile` ve `/admin` yok.
- Oturum şu anda demo kullanıcısını `localStorage` içinde tutuyor.
- Rol yalnız `instructor | student`.
- Veritabanı şeması açıkça “sistem geneli rol yoktur” diyor.
- Bu nedenle yalnız frontend yazarak güvenli admin paneli üretilemez.

Daha önemlisi, `CourseNav` global demo rolüne bakıyor. Aynı kişi bir derste eğitmen, başka derste öğrenci olursa yanlış sekmeler gösterilebilir. Yeni panel çalışmasında rol, `Course.role` veya sunucudan gelen ders bağlamından okunmalı.

### OBS’den alınabilecek yararlı özellikler

Alınmalı:

- Üst çubukta kimlik ve etkin çalışma alanı
- Kullanıcının öğrenci, eğitmen ve admin alanları arasında geçiş yapabilmesi
- Bildirim ve duyuru merkezi
- Aktif dönem yerine DOU-Synapse’e uygun “aktif ders” bağlamı
- Yaklaşan sınavlar ve kapanış tarihleri
- Eğitmen iletişim bilgisi ve varsa danışmanlık saatleri
- Ana sayfada kısa durum kartları ve hızlı işlemler
- Profil, gizlilik ve hesap işlemlerinin tek kullanıcı menüsünde gruplanması

Şimdilik alınmamalı:

- Transkript
- Resmî not listesi
- Ders kayıt ve ekle-bırak
- Devamsızlık
- Staj ve diploma işlemleri
- OBS öğrenci numarası veya akademik kayıtların kopyalanması

Bunlar ancak resmî OBS entegrasyonu, veri sahibi onayı ve açık API sözleşmesi varsa eklenmeli.

### Önerilen paneller

Öğrenci paneli:

- Derslerim
- Devam et: son sohbet veya sınav oturumu
- Yaklaşan yayınlanmış sınavlar
- Çalışılması gereken konular
- Son ilerleme özeti
- Yeni materyal veya eğitmen duyuruları
- Sınav kilidi gibi aktif durumlar

Eğitmen paneli:

- Ders başına öğrenci ve materyal sayısı
- İşlenmekte veya başarısız materyaller
- Onay bekleyen sorular
- Taslak ve yayınlanmış blueprint’ler
- Yaklaşan sınavlar
- Sınıfın zorlandığı konular
- Günlük token bütçesi ve kullanımı
- Retrieval kalitesi ve kaynak sorunları
- Hızlı işlemler: materyal yükle, soru üret, sınav planla

Profil:

- Ad soyad
- Doğrulanmış üniversite e-postası
- Ders bazlı roller
- Dil, saat dilimi, tema ve bildirim tercihleri
- KVKK/veri haklarına bağlantı
- Son güvenli oturum bilgisi
- E-posta, kimlik sağlayıcının sahibi olduğu için uygulamada doğrudan değiştirilememeli

Admin paneli:

- Sistem hazır mı, embedding hazır mı
- Kullanıcı, ders, belge ve aktif sınav sayıları
- Başarısız ve yeniden denenecek ingestion işleri
- API hata oranı ve gecikme yüzdelikleri
- LLM token kullanımı, sağlayıcı ve maliyet özeti
- Rate-limit olayları
- Depolama durumu
- Son politika ve yönetim değişiklikleri
- Kullanıcı ve ders arama
- Salt okunur denetim izi

### Log ekranı için güvenlik sınırı

`request_logs` şu anda soru ve cevap metni taşımıyor. Bu iyi bir temel. Admin ekranında gösterilebilecek alanlar:

- Zaman
- İstek kimliği
- Rota
- HTTP durumu
- Gecikme
- Mod
- Token sayısı
- Önbellek kullanımı
- Ders
- Takma veya maskeli kullanıcı kimliği

Ham sohbetler, sorular, JWT, API anahtarları ve tam e-posta adresleri gösterilmemeli.

Ayrıca mevcut HTTP middleware logları yalnız stdout’a yazıyor. Bunları doğrudan web panelinde göstermek bugün mümkün değil. “Teknik Loglar” ekranı dürüstçe yapılacaksa ya güvenli bir olay tablosu oluşturulmalı ya da Sentry benzeri gözlemlenebilirlik sistemi bağlanmalı. Sunucu log dosyasını tarayıcıya açmak doğru çözüm değil.

### Düşük çakışmalı dosya sahipliği

Yeni frontend dosyaları:

```text
apps/web/app/dashboard/layout.tsx
apps/web/app/dashboard/page.tsx
apps/web/app/profile/layout.tsx
apps/web/app/profile/page.tsx
apps/web/app/admin/layout.tsx
apps/web/app/admin/page.tsx
apps/web/app/admin/jobs/page.tsx
apps/web/app/admin/logs/page.tsx
apps/web/app/admin/audit/page.tsx

apps/web/components/dashboard/*
apps/web/components/profile/*
apps/web/components/admin/*

apps/web/lib/dashboard.ts
apps/web/lib/dashboard.test.ts
apps/web/lib/profile.ts
apps/web/lib/profile.test.ts
apps/web/lib/admin.ts
apps/web/lib/admin.test.ts
```

Domain tipleri `lib/types.ts` yerine kendi modüllerinde tutulursa modularize dalıyla çakışma azalır.

Zorunlu ortak frontend değişiklikleri yalnız şunlarla sınırlandırılabilir:

- `components/app-shell.tsx`: üst seviye gezinme ve kullanıcı menüsü
- `DESIGN.md`: global gezinme, admin tablo deseni ve ikon seti kararı

Backend için yeni ve büyük ölçüde eklemeli dosyalar:

```text
apps/api/app/api/dashboard.py
apps/api/app/api/profile.py
apps/api/app/api/admin.py
apps/api/app/schemas/dashboard.py
apps/api/app/schemas/profile.py
apps/api/app/schemas/admin.py
apps/api/app/models/admin.py
```

`main.py`ye yalnız router kayıtları eklenir.

Migration numarası şimdiden sabitlenmemeli. `0010`, `0011` ve `0013` entegrasyon kararları tamamlandıktan sonra sıradaki gerçek numara ayrılmalı.

### Güvenli admin yetkilendirmesi

En düşük riskli model:

- Course rolünden ayrı `platform_admins(user_id)` tablosu
- Satırları sıradan kullanıcıya kapalı
- Yalnız boolean döndüren `app.is_platform_admin()` fonksiyonu
- Backend’de `PlatformAdminDep`
- Admin uçlarında hem uygulama kapısı hem RLS
- Her admin değişikliğini yazan değiştirilemez audit kaydı
- `localStorage` içindeki bir alan hiçbir zaman admin yetkisi sayılmamalı

### Önerilen uygulama sırası

1. `GET /me/context` ile gerçek profil, ders rolleri ve platform yetkisini sunucudan döndür.
2. Profil görüntüleme ve tercihleri ekle.
3. Tek toplu `GET /dashboard` sözleşmesini kur. Frontend’in her ders için ayrı ayrı istek atmasına izin verme.
4. Öğrenci ve eğitmen dashboard’larını tamamla.
5. Admin yetkilendirme ve overview endpoint’lerini kur.
6. İş kuyruğu, güvenli log ve audit ekranlarını ekle.
7. AppShell kullanıcı menüsü ve alan geçişini bağla.
8. Mobil, koyu tema, rol izolasyonu ve admin reddi E2E testlerini çalıştır.

En kritik karar: OBS’nin görünümünü kopyalamak yerine kişisel bağlam, bildirim, yaklaşan işler ve rol alanları gibi başarılı bilgi mimarisi fikirlerini DOU-Synapse’in mevcut tasarım sistemine taşımak.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:925-948|note=[parallel worktree and hot file isolation rules]
skills/dou-parallel-worktree-delivery/SKILL.md:10-47|note=[worktree mapping and ownership audit procedure]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019feafc-8971-7ca0-a58d-f091f3fde5ea
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>/root/backend_admin_audit (Euclid)</code> — 105.0 MiB — closed</summary>

- Session: `019fecb3-74b0-7c03-8b61-25d90d3a217c`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:23:31.634Z`
- Source log: `rollout-2026-08-10T20-23-31-019fecb3-74b0-7c03-8b61-25d90d3a217c.jsonl`

<pre>
Salt-okunur denetim tamamlandı. İncelenen anlık durum: `$HOME/code/dou-lead`, `002-production-hardening`, `d25ce054`, origin’den 4 commit ileride ve çalışma ağacı temiz. Hiçbir dosya değiştirmedim.

## Net hüküm

Mevcut backend güçlü bir **ders eğitmeni panelini** besleyebilir; fakat henüz gerçek bir **sistem yöneticisi/admin paneli** desteklemiyor. En kritik sebep: sistem genelinde admin/eğitmen/öğrenci rolü yok. Yalnız ders bağlamında `instructor` ve `student` rolleri var; migration bunu özellikle söylüyor: [0001_core_schema.sql:41]($HOME/code/dou-lead/supabase/migrations/0001_core_schema.sql:41), [0001_core_schema.sql:48]($HOME/code/dou-lead/supabase/migrations/0001_core_schema.sql:48), [core.py:30]($HOME/code/dou-lead/apps/api/app/models/core.py:30).

Dahası, giriş yapmış her kullanıcı `POST /courses` çağırıp kendi kendine eğitmen olabilir; uç yalnız `PrincipalDep` istiyor ve oluşturana instructor üyeliği veriyor: [courses.py:48]($HOME/code/dou-lead/apps/api/app/api/courses.py:48), [courses.py:69]($HOME/code/dou-lead/apps/api/app/api/courses.py:69). OBS benzeri rol ayrımı hedefleniyorsa bu bir release blocker’dır.

## Bugün panele doğrudan bağlanabilecek yetenekler

| Panel alanı | Mevcut API | Yetki |
|---|---|---|
| Derslerim | `GET /courses`, `GET /courses/{id}` | Giriş yapan kullanıcı / ders üyesi |
| Ders oluşturma | `POST /courses` | Şu anda her giriş yapan kullanıcı |
| Üye yönetimi | `GET/POST /courses/{id}/members`, `DELETE .../members/{user_id}` | Ders eğitmeni |
| Öğrenci ilerlemesi | `GET .../analytics/me` | Öğrenci yalnız kendi verisi |
| Sınıf analitiği | `GET .../analytics/class` | Ders eğitmeni |
| AI politikası | `GET/PUT .../ai-policy` | Ders eğitmeni |
| AI politika geçmişi | `GET .../ai-policy/history` | Ders eğitmeni |
| Belge teknik durumu | `GET .../documents` | Ders üyesi |
| Chunk inceleme | `GET .../documents/{id}/chunks` | Ders eğitmeni |
| Retrieval laboratuvarı | `POST .../sources/inspect` | Ders eğitmeni |
| KVKK dışa aktarma | `GET /me/export` | Kullanıcının kendisi |
| Sohbet geçmişi silme | `/me/chat-history` ve ders bazlı silme uçları | Kullanıcının kendisi |
| Hesap anonimleştirme | `DELETE /me` | Kullanıcının kendisi |
| Canlılık/hazırlık | `/health/live`, `/health/ready` | Kimlik gerektirmiyor |

Ders ve üyelik uçlarının kodu [courses.py:30]($HOME/code/dou-lead/apps/api/app/api/courses.py:30)-[courses.py:165]($HOME/code/dou-lead/apps/api/app/api/courses.py:165) arasında. Sınıf analitiği konu ortalamaları, en çok yanlış yapılan sorular ve kapsam dışı ret oranını hazır döndürüyor: [analytics.py:222]($HOME/code/dou-lead/apps/api/app/api/analytics.py:222)-[analytics.py:332]($HOME/code/dou-lead/apps/api/app/api/analytics.py:332). AI değişiklik geçmişi sayfalı: [policy.py:137]($HOME/code/dou-lead/apps/api/app/api/policy.py:137).

## Profil ve kullanıcı yönetimi boşlukları

`profiles` yalnız `id`, `email`, `full_name`, `created_at` tutuyor: [core.py:60]($HOME/code/dou-lead/apps/api/app/models/core.py:60). RLS kullanıcının kendisini güncellemesine izin veriyor, fakat bunu kullanan `GET /me/profile` veya `PATCH /me/profile` API’si yok: [0001_core_schema.sql:336]($HOME/code/dou-lead/supabase/migrations/0001_core_schema.sql:336).

Eksikler:

- Sistem genelinde kullanıcı listeleme/arama yok.
- Admin, hesap durumu veya rol yönetimi yapamıyor.
- Avatar, dil, saat dilimi ve bildirim tercihleri yok.
- Supabase auth hesabının doğrulanmış/engelli/son giriş durumu uygulama şemasında yok.
- `DELETE /me` yalnız uygulama profilini anonimleştiriyor; kimlik sağlayıcısındaki hesap ayrıca kapatılmalı: [privacy.py:223]($HOME/code/dou-lead/apps/api/app/api/privacy.py:223)-[privacy.py:268]($HOME/code/dou-lead/apps/api/app/api/privacy.py:268).

Hızlı ve güvenli profil işi migration gerektirmeden başlayabilir:

- `GET /me/profile`
- `PATCH /me/profile` — yalnız `full_name`
- E-posta salt-okunur olmalı; auth sağlayıcısı dışında değiştirilmemeli.
- Avatar daha sonra ayrı Storage bucket ve bucket RLS ile eklenmeli.

## Log ve denetim durumu

İki farklı kayıt türü var:

1. `request_logs`: yalnız sohbet isteklerinin ölçümü. `route`, `mode`, sonuç durumu, HTTP durumu, gecikme, token ve cache isabeti tutuyor; soru/cevap metni tutmuyor: [chat.py:91]($HOME/code/dou-lead/apps/api/app/models/chat.py:91)-[chat.py:110]($HOME/code/dou-lead/apps/api/app/models/chat.py:110), [api/chat.py:727]($HOME/code/dou-lead/apps/api/app/api/chat.py:727)-[api/chat.py:751]($HOME/code/dou-lead/apps/api/app/api/chat.py:751).

2. Uygulama logları: redaksiyonlu tek satır JSON olarak yalnız stdout’a yazılıyor: [logging.py:69]($HOME/code/dou-lead/apps/api/app/core/logging.py:69)-[logging.py:109]($HOME/code/dou-lead/apps/api/app/core/logging.py:109). Middleware request ID, yol, durum ve süreyi yazıyor: [main.py:100]($HOME/code/dou-lead/apps/api/app/main.py:100)-[main.py:125]($HOME/code/dou-lead/apps/api/app/main.py:125).

Bunlar gerçek admin “Loglar” ekranı için yeterli değil:

- `request_logs` tüm HTTP isteklerini kapsamıyor; sadece sohbet yazıyor.
- Uygulama loglarının kalıcı deposu ve sorgu API’si yok.
- Üye ekleme/çıkarma, belge silme, soru onayı, blueprint yayını, hesap anonimleştirme gibi idari işlemler için birleşik audit izi yok.
- Yalnız AI politika değişikliklerinde append-only audit tablosu ve history endpoint’i var: [0009_course_ai_policy.sql:25]($HOME/code/dou-lead/supabase/migrations/0009_course_ai_policy.sql:25)-[0009_course_ai_policy.sql:79]($HOME/code/dou-lead/supabase/migrations/0009_course_ai_policy.sql:79).

Raw uygulama loglarını veritabanına kopyalayıp tarayıcıya açmak doğru çözüm değil. stdout logları Azure/ACA, Loki, Sentry veya benzeri gözlemleme sistemine gönderilmeli; ürün içi panel yalnız toplulaştırılmış, PII içermeyen operasyon metriklerini göstermeli.

## Health/teknik panel

Mevcut health uçları sağlam bir başlangıç:

- `/health/live`: sürüm ve ortam: [health.py:32]($HOME/code/dou-lead/apps/api/app/api/health.py:32).
- `/health/ready`: DB, pgvector ve embedding warmup durumu; bozuksa 503: [health.py:42]($HOME/code/dou-lead/apps/api/app/api/health.py:42)-[health.py:67]($HOME/code/dou-lead/apps/api/app/api/health.py:67).

Eksik teknik göstergeler:

- Bekleyen/başarısız ingestion işi ve en eski işin yaşı
- Storage erişimi
- LLM sağlayıcı hazır mı bilgisi; anahtarın kendisi asla dönmemeli
- Son 1/24 saatte hata oranı, p50/p95 gecikme
- Token tüketimi ve cache isabet oranı
- DB pool doluluğu
- Son başarılı worker çalışması

## RLS değerlendirmesi

Temel yaklaşım güçlü:

- Her istek PostgreSQL transaction’ında `app.current_user_id` bağlamı alıyor: [db.py:65]($HOME/code/dou-lead/apps/api/app/core/db.py:65)-[db.py:88]($HOME/code/dou-lead/apps/api/app/core/db.py:88).
- API ayrıca aktif üyeliği doğruluyor ve erişilmeyen dersi 404 olarak gizliyor: [deps.py:90]($HOME/code/dou-lead/apps/api/app/api/deps.py:90)-[deps.py:125]($HOME/code/dou-lead/apps/api/app/api/deps.py:125).
- Çekirdek tablolar `ENABLE` ve `FORCE ROW LEVEL SECURITY` taşıyor: [0001_core_schema.sql:322]($HOME/code/dou-lead/supabase/migrations/0001_core_schema.sql:322)-[0001_core_schema.sql:334]($HOME/code/dou-lead/supabase/migrations/0001_core_schema.sql:334).
- Eğitmen kendi dersinin `request_logs` kayıtlarını okuyabilir; öğrenci okuyamaz: [0005_analytics.sql:28]($HOME/code/dou-lead/supabase/migrations/0005_analytics.sql:28)-[0005_analytics.sql:39]($HOME/code/dou-lead/supabase/migrations/0005_analytics.sql:39).
- Chat metinleri eğitmene/admin adayı kullanıcıya açılmıyor; bu gizlilik kararı korunmalı: [0003_chat.sql:165]($HOME/code/dou-lead/supabase/migrations/0003_chat.sql:165)-[0003_chat.sql:208]($HOME/code/dou-lead/supabase/migrations/0003_chat.sql:208).

Açık test borcu: mutasyonlu doğrudan RLS kanıtları 0001+0003, 0004+0005 ve 0008’i kapsıyor; başlıkları bunu açıkça sınırlandırıyor: [rls_isolation.sql:1]($HOME/code/dou-lead/supabase/tests/rls_isolation.sql:1), [rls_assessment.sql:1]($HOME/code/dou-lead/supabase/tests/rls_assessment.sql:1), [rls_blueprint.sql:1]($HOME/code/dou-lead/supabase/tests/rls_blueprint.sql:1). `0009_course_ai_policy` ve `0012_privacy_rights` için ayrı pozitif/negatif ve mutasyonlu RLS paketi yok; API testleri var ama aynı güvence değildir.

## Güvenli minimum admin backend paketi

Sıralama şu olmalı:

1. **Platform admin kimliği**
   - `platform_admins(user_id PK, granted_at, granted_by)` tablosu.
   - İlk admin deployment sırasında dışarıdan seed edilmeli; kullanıcı kendini admin yapamamalı.
   - `app.is_platform_admin()` yalnız boolean döndüren, sabit `search_path` kullanan `SECURITY DEFINER` fonksiyon olmalı.
   - `AdminDep` her `/admin/*` ucunda zorunlu olmalı.
   - Supabase service-role anahtarı frontend’e kesinlikle verilmemeli.

2. **Read-only admin API**
   - `GET /admin/overview`
   - `GET /admin/users?cursor=&amp;limit=&amp;query=`
   - `GET /admin/courses?cursor=&amp;limit=`
   - `GET /admin/operations/ingestion?status=&amp;cursor=`
   - `GET /admin/metrics/requests?from=&amp;to=&amp;course_id=`
   - `GET /admin/audit-events?cursor=&amp;action=`
   - Bütün listeler cursor pagination kullanmalı. Mevcut `/courses` ve `/members` listeleri sayfasız olduğundan admin ölçeğinde yeniden kullanılmamalı.

3. **Append-only audit**
   - `admin_audit_events(id, actor_id, action, target_type, target_id, request_id, safe_metadata, created_at)`.
   - `UPDATE/DELETE` yetkileri `dou_app` ve worker’dan çekilmeli.
   - Request body, token, e-posta, sohbet metni ve sırlar metadata’ya yazılmamalı.
   - İlk etapta üyelik değiştirme, belge silme, soru onay/red, blueprint publish ve hesap yönetimi olayları kapsanmalı.

4. **Profil API**
   - Önce mevcut tabloyla `GET/PATCH /me/profile`.
   - Avatar ve tercihler gerekiyorsa sonraki migration’da dar kolonlar/bucket politikası.
   - OBS öğrenci numarası veya resmî not gibi veriler gerçek entegrasyon olmadan elle tutulmamalı.

5. **RLS ve mutasyon kapısı**
   - Platform admin politikaları için admin/non-admin/başka ders senaryoları.
   - Politika `USING (true)` yapıldığında kırmızı yanan mutasyon testi.
   - Admin olmanın chat mesajı okuma yetkisi vermediğini açıkça kanıtlayan test.
   - Admin API’lerinde service-role yerine normal `dou_app` + RLS yolu kullanılmalı.

OBS’den ürün kapsamına gerçekten uyan backend özellikleri: aktif dönem, ders programı/son teslim takvimi, öğretim elemanı ofis saatleri, duyuru-bildirim merkezi ve öğrenme çıktısı/müfredat ilerlemesi. Not dökümü, GPA, ders kayıt, staj ve form modülleri bu ürünün AI sınav koçu kapsamını büyütür; gerçek OBS entegrasyonu olmadan eklenmemeli.
</pre>

</details>

<details>
<summary><code>/root/obs_feature_map (Mencius)</code> — 104.6 MiB — closed</summary>

- Session: `019fecb3-94cc-7c90-abdc-bdf56ab62eab`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:23:39.853Z`
- Source log: `rollout-2026-08-10T20-23-39-019fecb3-94cc-7c90-abdc-bdf56ab62eab.jsonl`

<pre>
OBS’den alınması gereken şey görsel tarzı değil, bilgi mimarisi. DOU‑Synapse’in mevcut arayüzü temiz ve erişilebilir; fakat işlevler ders sekmelerine dağılmış, gerçek bir öğrenci/eğitmen ana paneli ve platform yöneticisi yüzeyi yok.

## Ekranlardan gözlemlenen yararlı desenler

- Rol bazlı giriş ve başlangıç noktası: öğrenci, akademisyen ve idari kullanıcı ayrımı.
- Sabit uygulama kabuğu: üst çubuk, gruplanmış sol menü, aktif dönem ve bildirim alanı.
- Özet kartları: geçerli dönem, danışman, program ve kayıt durumu gibi en önemli bağlamın ilk ekranda gösterilmesi.
- Dönem seçici: geçmiş ve güncel dönem arasında bağlam değiştirme.
- Program görünümü: haftalık plan ve danışman görüşme saatlerinin aynı ekranda bulunması.
- Gruplanmış işlemler: dersler, kullanıcı işlemleri ve başvuruların açılır menüler altında toplanması.
- Dikkat gerektiren durumlar için sayfa üstü duyuru şeridi.

## DOU‑Synapse’e uyarlanmış öncelik sırası

### P0 — Öğrenci paneli

- “Devam et” kartı: son çalışılan ders ve sohbet/soru oturumu.
- Yaklaşan sınavlar, kalan süre ve sınav sırasında asistanın kapalı olacağı bilgisi.
- Çalışılması gereken ilk üç konu; mevcut analitik verisinden beslenebilir.
- Ders kartlarında materyal, soru ve tamamlanma özeti.
- Son AI geri bildirimi ve kaynak bağlantısına hızlı dönüş.
- Bildirim merkezi: yeni materyal, yayımlanan sınav, değerlendirilen cevap ve eğitmen duyurusu.
- Dönem filtresi ancak ürünün gerçekten dönem verisi oluştuğunda eklenmeli.

### P0 — Eğitmen paneli

- Ders sağlığı özeti: işlenen/başarısız materyal, taslak/onaylı soru, yaklaşan sınav ve öğrenci etkinliği.
- “İşlem bekleyenler” kuyruğu: başarısız ingestion, onay bekleyen AI soruları, yayımlanmamış blueprint ve düşük kanıtlı cevaplar.
- Sınav blueprint’i, soru onayı, AI politikası, kaynak laboratuvarı ve katılımcı yönetimine hızlı işlemler.
- Sınıfın zorlandığı konular ve yüksek yanlış oranlı sorular.
- Duyuru ve danışmanlık/ofis saati kartı; üniversite sistemiyle entegrasyon yoksa eğitmenin elle yönetebileceği sade alan.
- Resmî OBS notu izlenimi vermeden sınav provası sonuçları; mevcut “resmî not değildir” açıklaması korunmalı.

### P0 — Profil ve hesap

Mevcut `/account` yalnızca KVKK/veri işlemlerini içeriyor. Profil iki ayrı bölüm olmalı:

- Profil: ad, rol, tercih edilen dil, saat dilimi, erişilebilirlik ve bildirim tercihleri.
- Gizlilik ve verilerim: dışa aktarma, sohbet silme, anonimleştirme ve KVKK.

Akademik numara, fotoğraf, program, danışman gibi bilgiler yalnız gerçek bir üniversite entegrasyonundan geliyorsa gösterilmeli. Yapay veya manuel doldurulmuş veriler resmî kayıt gibi sunulmamalı.

### P0/P1 — Platform admin paneli

Eğitmen ile platform yöneticisi ayrı roller olmalı. Admin panelinin ilk sürümü:

- Sistem durumu: API, veritabanı, embedding modeli, LLM sağlayıcısı ve depolama.
- Ingestion kuyruğu: bekleyen, çalışan, başarısız işler; güvenli tekrar deneme.
- Kullanım ve maliyet: istek, token, provider/model, ders bazlı kota ve rate-limit ihlalleri.
- Kullanıcı ve rol yönetimi: etkin/pasif hesap, ders üyeliği; her değişiklik audit log’a yazılmalı.
- Global AI varsayılanları ve derslerin bunlardan sapma görünümü.
- Güvenlik olayları: tekrarlanan 401/403, kapsam dışı denemeler, hız sınırı ve şüpheli yönetici işlemleri.
- Depolama/veritabanı kapasitesi, migration sürümü, backup/PITR durumu.
- Feature flag ve bakım modu.

## Log ekranının doğru tasarımı

Ham terminal çıktısını web arayüzüne basmak yerine yapılandırılmış olay tablosu kullanılmalı:

- Zaman, seviye, servis, uç, durum kodu, gecikme ve `request_id`.
- Ders/kullanıcı için doğrudan kişisel bilgi yerine kontrollü kimlik veya takma kimlik.
- Tarih, seviye, servis, istek kimliği ve sonuç durumuna göre filtre.
- Satır ayrıntı çekmecesi ve güvenli JSON görünümü.
- CSV/JSON dışa aktarma yalnız yetkili yöneticiye.
- Prompt, öğrenci cevabı, erişim anahtarı ve authorization header varsayılan olarak asla loglanmamalı.
- Saklama süresi, redaksiyon ve audit kayıtlarının değiştirilemezliği backend’de uygulanmalı.

## Mevcut arayüzle somut fark

- Şu an global kabuk yalnız üst çubuktan oluşuyor; rol bazlı genel navigasyon yok.
- Ders işlevleri yatay sekmelere dağılmış; eğitmene günlük iş kuyruğu sunulmuyor.
- `/account` iyi bir gizlilik merkezi ama profil ekranı değil.
- Öğrenci/eğitmen rolleri var; platform admin rolü ve admin rotaları görünmüyor.
- Analitik, materyal durumu, blueprint ve AI politikası zaten mevcut; yeni paneller bunları yeni veri uydurmadan bir araya getirebilir.

## OBS’den kopyalanmaması gerekenler

- Masaüstüne bağımlı, dar ve sürekli açık sol menü.
- Küçük yazılar, sıkışık gri tablolar ve geniş boş alanlar.
- Aynı kimlik bilgisinin birden fazla yerde tekrarlanması.
- Her özelliğin çok katmanlı açılır menüye gömülmesi.
- AI ilerleme skorunu resmî not/transkript görünümünde sunmak.
- Üniversite logosunu veya OBS tasarımını birebir kopyalamak.
- Profil fotoğrafı, öğrenci numarası ve akademik ayrıntıları gereksiz yere toplamak.
- Backend yetkisi olmadan yalnız arayüzde admin düğmesi gizlemek.

Özetle: OBS’den rol ayrımı, dönem bağlamı, özet kartları, program ve gruplanmış navigasyon alınmalı; eski görsel yoğunluğu ve resmî kayıt hissi alınmamalı. İlk uygulanacak paket öğrenci/eğitmen dashboard’u, ayrılmış profil-gizlilik alanı ve salt okunur sistem sağlığı + yapılandırılmış loglarla başlayan bağımsız admin panelidir.
</pre>

</details>

<details>
<summary><code>/root/speckit_portal_plan (Nietzsche)</code> — 113.5 MiB — closed</summary>

- Session: `019fecbc-7c3b-7111-9763-cf285f86f3c5`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:33:23.388Z`
- Source log: `rollout-2026-08-10T20-33-23-019fecbc-7c3b-7111-9763-cf285f86f3c5.jsonl`

<pre>
Planın omurgası netleşti: mevcut güçlü ders içi modülleri yeniden yazmak yerine, onların önüne rol bazlı ürün portalı ve arkasına güvenli operasyon katmanı ekliyorum. OBS’den yalnız bilgi mimarisi alınacak; not, transkript, ders kayıt gibi resmi öğrenci bilgi sistemi işlevleri ürün iddiasına dönüştürülmeyecek.
</pre>

</details>

<details>
<summary><code>/root/portal_backend (Euler)</code> — 113.5 MiB — closed</summary>

- Session: `019fecbc-c7e2-7642-a682-d9948d8b2fc5`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:33:42.755Z`
- Source log: `rollout-2026-08-10T20-33-42-019fecbc-c7e2-7642-a682-d9948d8b2fc5.jsonl`

<pre>
Yönetim erişimini arayüzde saklanan bir menüye değil, veritabanındaki ayrı bir platform rolüne bağlıyorum. Yöneticiye yalnız sayısal/operasyonel özetler açılıyor; öğrenci sohbet metni ve gizli sağlayıcı verisi bu yüzeye hiç eklenmiyor.
</pre>

</details>

<details>
<summary><code>/root/portal_frontend (Nash)</code> — 113.5 MiB — closed</summary>

- Session: `019fecbc-fe82-7363-97e4-57beb8247e0d`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:33:56.746Z`
- Source log: `rollout-2026-08-10T20-33-56-019fecbc-fe82-7363-97e4-57beb8247e0d.jsonl`

<pre>
İlk dikey dilim tamamlandı. Şimdi sözleşme uyuşmazlıklarını, TypeScript hatalarını ve saf sunum kurallarını testlerle yakalıyorum; ardından derleme hatası kalırsa ekranları backend’in kesin alan adlarına göre düzelteceğim.
</pre>

</details>

<details>
<summary><code>guardian</code> — 5.9 MiB — closed</summary>

- Session: `019feccc-1111-7160-8db4-580e309e931c`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:50:24.530Z`
- Source log: `rollout-2026-08-10T20-50-24-019feccc-1111-7160-8db4-580e309e931c.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/backend_verify (Laplace)</code> — 17.8 MiB — closed</summary>

- Session: `019feccf-fd01-7a11-b846-f34c6bcba1ad`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:54:41.541Z`
- Source log: `rollout-2026-08-10T20-54-41-019feccf-fd01-7a11-b846-f34c6bcba1ad.jsonl`

<pre>
Backend dilimi tamamlandı; commit atılmadı.

Uygulananlar:

- `0014_platform_admin_console.sql`
  - Ayrı `platform_admins` rolü
  - Uygulama/worker için doğrudan tablo erişimi kapalı
  - Yetkiyi SQL içinde tekrar doğrulayan salt-okunur yönetim fonksiyonları
  - Maskeli e-posta ve 12 karakterlik geri döndürülemez `user_ref`
  - Loglarda prompt, cevap, tam e-posta, dosya adı ve hata metni yok
- `GET/PATCH /me/profile`
- Karma ders rollerini koruyan `GET /dashboard`
- `GET /admin/overview|users|courses|requests|ingestion`
- Router, demo admin seed’i ve test temizliği
- Öğrencide başarısız belge/taslak soru sayıları zorunlu `0`
- Platform admin olmak akademik ders/sohbet içeriğine erişim vermiyor

Doğrulama:

- Portal/RLS: **12 passed**
- Ruff: temiz
- Mypy: yeni 7 backend kaynak dosyası temiz
- OpenAPI: 7 yeni yol kayıtlı
- Test DB: yalnız `dou_synapse_test_product_portal_codex`; koşu sonunda silindi
- `git diff --check`: temiz

Tam `main.py` mypy zincirinde bu dilimden önce mevcut olan [questions.py]($HOME/code/dou-product-portal/apps/api/app/api/questions.py:124) kaynaklı 7 hata sürüyor (`source_stale` imzası ve eksik `Chunk`/`Document` adları). Portal dosyalarının hedefli mypy sonucu temizdir.

Eski test asılmasının sebebi de doğrulandı: Documents/iCloud altındaki çalışma ağacında dosyalar `compressed,dataless` idi ve okumalar `Operation timed out (os error 60)` ile bekliyordu; PostgreSQL kilidi değildi. Yeni `$HOME/code/dou-product-portal` çalışma ağacında bu sorun yok.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.6 MiB — closed</summary>

- Session: `019feccf-fde9-7411-99a0-bb3a3f0f4a2c`
- Parent: `019feccf-fd01-7a11-b846-f34c6bcba1ad`
- Started: `2026-08-10T17:54:41.769Z`
- Source log: `rollout-2026-08-10T20-54-41-019feccf-fde9-7411-99a0-bb3a3f0f4a2c.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/frontend_verify (Aquinas)</code> — 26.8 MiB — closed</summary>

- Session: `019fecd0-123f-79b0-9bdc-50fec2a7f0e8`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:54:46.976Z`
- Source log: `rollout-2026-08-10T20-54-46-019fecd0-123f-79b0-9bdc-50fec2a7f0e8.jsonl`

<pre>
Frontend portal tamamlandı.

- Modern rol bazlı dashboard, profil ve salt okunur admin paneli eklendi.
- Admin yetkisi sunucu profilinden doğrulanmadan hiçbir admin isteği başlamıyor.
- Admin görünümünden `user_ref` tamamen kaldırıldı; yalnız anonim teknik ölçümler gösteriliyor.
- Mobil menü, sağlık rozetleri, filtreler, sayfalama, hata/yükleme/boş durumları ve erişilebilir tablolar eklendi.
- Eğitmen ve öğrenci için gerçek hızlı araç bağlantıları eklendi.
- Giriş sonrası yönlendirme `/dashboard` oldu.
- Profil güncellemesi için `api.patch` eklendi.
- Karma ders rolleri için blueprint yetkisi `useSession(courseId)` ile düzeltildi.
- Backend/spec dosyalarına dokunulmadı.

Doğrulama:

- 303 test geçti, 0 hata
- TypeScript kontrolü temiz
- Production build temiz
- `/dashboard`, `/profile`, `/admin` rotaları başarıyla üretildi
- `git diff --check` temiz

Dal: `003-product-portal`
Taban: `b8da84e`
Commit veya push yapılmadı. Canlı API ve tarayıcı doğrulaması, backend entegrasyonu tamamlandıktan sonra son birleşik kapı olarak çalıştırılmalı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 1.2 MiB — closed</summary>

- Session: `019fecd0-12b7-7ce1-969e-d7ebc98e1024`
- Parent: `019fecd0-123f-79b0-9bdc-50fec2a7f0e8`
- Started: `2026-08-10T17:54:47.095Z`
- Source log: `rollout-2026-08-10T20-54-47-019fecd0-12b7-7ce1-969e-d7ebc98e1024.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/spec_review (Franklin)</code> — 27.4 MiB — closed</summary>

- Session: `019fecd0-208a-7000-b8f7-df017ae3cde1`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T17:54:50.634Z`
- Source log: `rollout-2026-08-10T20-54-50-019fecd0-208a-7000-b8f7-df017ae3cde1.jsonl`

<pre>
Tam Speckit setini yalnız `specs/003-product-portal` altında hazırladım:

- [spec.md]($HOME/code/dou-product-portal/specs/003-product-portal/spec.md)
- [plan.md]($HOME/code/dou-product-portal/specs/003-product-portal/plan.md)
- [research.md]($HOME/code/dou-product-portal/specs/003-product-portal/research.md)
- [data-model.md]($HOME/code/dou-product-portal/specs/003-product-portal/data-model.md)
- [API contract]($HOME/code/dou-product-portal/specs/003-product-portal/contracts/api.md)
- [quickstart.md]($HOME/code/dou-product-portal/specs/003-product-portal/quickstart.md)
- [tasks.md]($HOME/code/dou-product-portal/specs/003-product-portal/tasks.md)
- [full-product-roadmap.md]($HOME/code/dou-product-portal/specs/003-product-portal/full-product-roadmap.md)

Belgelerde şu kararlar sabitlendi:

- Dal `003-product-portal`, migration `0014_platform_admin_console.sql`.
- Modern Next.js/React/FastAPI/PostgreSQL yığını korunuyor.
- `platform_admins` RLS ENABLE, FORCE değil; grant’ler kapalı.
- Allowed/denied admin erişimleri kapalı append-only audit tablosuna yazılıyor.
- Kullanıcı dizini `POST /admin/users` JSON gövdesiyle aranıyor; URL’de arama PII’si yok.
- Request listesinde `user_ref` dahil kullanıcı eşleme alanı yok.
- Ingestion listesinde `file_name`, hata veya içerik yok.
- Dashboard blueprint sayacı uydurmuyor; blueprint yalnız görünür araç bağlantısı.
- OBS uyarlaması, öğretmen gereksinim matrisi, benzer ürün eşlemesi, 6–8 haftalık dalgalar ve production release kapıları yer alıyor.

Tutarlılık taramasında eski dal/endpoint/migration ve eski admin alanı kalmadı. `docs_check` içinde 003’e ait yeni hata yok; ancak repo genelinde eski README/ARCHITECTURE/002 sayaçlarından 13 bayat iddia bulunuyor. Backend test ölçümü de sandbox’taki `uv` cache izni nedeniyle alınamadı. Bunlara dokunmadım.

Commit veya push yapmadım; frontend/backend dosyalarını değiştirmedim.
</pre>

</details>

<details>
<summary><code>guardian</code> — 1.4 MiB — closed</summary>

- Session: `019fecd0-20fa-7013-96ab-6789ece0a631`
- Parent: `019fecd0-208a-7000-b8f7-df017ae3cde1`
- Started: `2026-08-10T17:54:50.746Z`
- Source log: `rollout-2026-08-10T20-54-50-019fecd0-20fa-7013-96ab-6789ece0a631.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/portal_security_review (Noether)</code> — 18.1 MiB — closed</summary>

- Session: `019fecdf-97fe-7132-b800-e8ed023b85ed`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T18:11:44.255Z`
- Source log: `rollout-2026-08-10T21-11-44-019fecdf-97fe-7132-b800-e8ed023b85ed.jsonl`

<pre>
Backend, SQL ve ilgili test düzeltmeleri tamamlandı.

- `user_ref` ve `public.digest` tamamen kaldırıldı.
- Overview artık `chat_turns_24h` ve `active_memberships_total` döndürüyor.
- `warming` ve `failed`, admin ile readiness ekranlarında ortak kuralla `degraded`.
- SQL sayfalama yardımcıları `NULL`, sıfır ve 100 üzerini reddediyor.
- İzin verilen/reddedilen admin erişimleri kalıcı, içeriksiz ve uygulamaya kapalı audit tablosuna yazılıyor.
- Audit kaydı 403 işleminden ayrı commit edildiği için reddedilen denemeler kaybolmuyor.
- Güvensiz istek kimlikleri normalize ediliyor.
- OpenAPI yol sayacı yeni yedi portal yoluyla güncellendi.

Doğrulama:

- Hedefli backend paketi: `40 passed in 17.56s`
- Değiştirilen dosyalarda Ruff: temiz
- Değiştirilen uygulama dosyalarında mypy: temiz
- Frontend ve Speckit dosyalarına dokunulmadı.

Frontend sahibinin uyarlaması gereken sözleşme değişikliklerini ana ajana ayrıca ilettim.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.4 MiB — closed</summary>

- Session: `019fecdf-9883-7ea1-8151-bdcaa983ed49`
- Parent: `019fecdf-97fe-7132-b800-e8ed023b85ed`
- Started: `2026-08-10T18:11:44.387Z`
- Source log: `rollout-2026-08-10T21-11-44-019fecdf-9883-7ea1-8151-bdcaa983ed49.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/skill_forward_test (Pasteur)</code> — 0.4 MiB — closed</summary>

- Session: `019fece8-f87b-7c43-92a5-e2ad731c9a11`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T18:21:58.783Z`
- Source log: `rollout-2026-08-10T21-21-58-019fece8-f87b-7c43-92a5-e2ad731c9a11.jsonl`

<pre>
Kontrol listesi henüz karşılanmıyor.

En önemli sorun: `/admin/users` araması kişisel veriyi URL’ye taşıyor. GET endpoint’i serbest `search` parametresi kabul ediyor ([admin.py]($HOME/code/dou-product-portal/apps/api/app/api/admin.py:49)); SQL bunu ad ve maskeli e-posta üzerinde arıyor ([0014_platform_admin_console.sql]($HOME/code/dou-product-portal/supabase/migrations/0014_platform_admin_console.sql:193)). Test ise tam e-postayı gerçekten query string’e gönderip yalnızca “0 sonuç” dönmesini güvenli sayıyor ([test_portal.py]($HOME/code/dou-product-portal/apps/api/tests/test_portal.py:355)). E-posta eşleşmese bile tarayıcı geçmişi, proxy ve erişim günlüklerine ulaşmış olabilir.

Aramayı gövde kullanan, loglanmayan sıkı şemalı bir endpoint’e taşımak ve ham e-postanın yakalanan erişim loglarında bulunmadığını test etmek gerekir.

Yetkilendirmede scoped incelemede bypass görmedim: FastAPI bağımlılığı kontrol ediyor ([deps.py]($HOME/code/dou-product-portal/apps/api/app/api/deps.py:152)), SQL yardımcıları yeniden yetkilendiriyor ve `PUBLIC EXECUTE` kaldırılmış ([0014_platform_admin_console.sql]($HOME/code/dou-product-portal/supabase/migrations/0014_platform_admin_console.sql:451)). Salt-okunur inceleme yaptım; dosya değiştirmedim ve yazma yapan testleri çalıştırmadım.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:804-804|note=[RLS and mutation proof expectation]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019fe6f8-90a1-75f0-b040-c9c44f714fa3
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>/root/portal_e2e (Kepler)</code> — 14.9 MiB — closed</summary>

- Session: `019fecfa-bece-7912-931a-7677a118b578`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T18:41:23.664Z`
- Source log: `rollout-2026-08-10T21-41-23-019fecfa-bece-7912-931a-7677a118b578.jsonl`

<pre>
Yalnız [portal.spec.ts]($HOME/code/dou-product-portal/apps/web/e2e/portal.spec.ts) eklendi.

Kapsanan 6 gerçek E2E senaryosu:

- Eğitmen dashboard’u ve çalışan yönetim bağlantıları
- Öğrenci dashboard’u ve yalnız öğrenci araçları
- Aynı kullanıcının ders bazlı karma rolü
- Profil, salt-okunur e-posta, ders rolleri ve veri hakları
- Platform admin paneli, maskeli e-posta ve teknik sekmeler
- Admin olmayan kullanıcı için UI ve API reddi

Ek güvenlik kanıtları:

- `/me/profile` tek kez çağrılıyor.
- İlk `/admin/*` isteği profil yanıtından sonra başlıyor.
- Admin olmayan kullanıcıda hiçbir tarayıcı `/admin/*` isteği oluşmuyor.
- `/admin/users` yalnız `POST` gövdesi kullanıyor; URL query alanı boş.
- Veriler taklit edilmeden gerçek API üzerinden benzersiz derslerle kuruluyor.

Doğrulama:

- Playwright keşfi: **6 test / 1 dosya**
- TypeScript: **temiz**
- `git diff --check`: **temiz**
- Çalışan API/web sunucusu bulunmadığı için gerçek tarayıcı koşusu yapılmadı.
- Commit veya push yapılmadı; başka dosyaya dokunulmadı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.2 MiB — closed</summary>

- Session: `019fecfa-bfee-7632-9a49-5694143b4233`
- Parent: `019fecfa-bece-7912-931a-7677a118b578`
- Started: `2026-08-10T18:41:23.951Z`
- Source log: `rollout-2026-08-10T21-41-23-019fecfa-bfee-7632-9a49-5694143b4233.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/portal_rls_mutation (Ampere)</code> — 14.7 MiB — closed</summary>

- Session: `019fecfa-dc25-77f3-9171-3a945a59eb2d`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T18:41:31.173Z`
- Source log: `rollout-2026-08-10T21-41-31-019fecfa-dc25-77f3-9171-3a945a59eb2d.jsonl`

<pre>
Tamamlandı: `supabase/tests/rls_portal_admin_mutation_check.sh` eklendi ve çalıştırılabilir yapıldı.

Doğrulama sonucu:

```text
REFERANS   3 güvenlik kapısı doğru nedenle kapalı
YAKALANDI  LEAK__PLATFORM_ADMIN_SELF_PROMOTION
YAKALANDI  LEAK__ADMIN_HELPER_AUTHORIZATION
YAKALANDI  LEAK__PUBLIC_EXECUTE_ADMIN_HELPER

3 mutasyon denendi, 3 kesin sızıntı yakalandı.
```

- Yalnız `rls_portal_admin_*` adlı geçici veritabanları kullanılıyor.
- Tüm migration’lar sıfırdan uygulanıyor.
- Mevcut/verilen ortak DB’ye dokunmayı reddediyor.
- Başarı, hata ve sinyal durumunda geçici DB’ler temizleniyor.
- Koşum sonunda artık DB kalmadığı doğrulandı.
- `bash -n` ve `git diff --check` temiz.
- Başka dosya değiştirilmedi; commit veya push yapılmadı.

Not: self-promotion mutasyonu iki savunma katmanını birlikte zayıflatıyor; yalnız GRANT veya yalnız RLS bozulduğunda diğer katman erişimi engellemeye devam ediyor.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.2 MiB — closed</summary>

- Session: `019fecfa-dcfb-7f12-ad6a-149035c08064`
- Parent: `019fecfa-dc25-77f3-9171-3a945a59eb2d`
- Started: `2026-08-10T18:41:31.388Z`
- Source log: `rollout-2026-08-10T21-41-31-019fecfa-dcfb-7f12-ad6a-149035c08064.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/branch_classify (Mendel)</code> — 1.4 MiB — closed</summary>

- Session: `019fecff-3565-7de0-9866-00919d667047`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T18:46:16.165Z`
- Source log: `rollout-2026-08-10T21-46-16-019fecff-3565-7de0-9866-00919d667047.jsonl`

<pre>
Sonuç: GitHub’daki `56 / 30 / 15 / 14 / 1` sayıları dal sayısı değil, `main`’e göre öndeki commit sayılarıdır. Mevcut fetch edilmiş görünümde `origin/HEAD` hariç 6 uzak ref var: 5 çalışma dalı + `main`.

| Uzak dal | `origin/002` ilişkisi | `origin/main` ilişkisi | Karar |
|---|---:|---:|---|
| `origin/main` | `002` bunun 56 commit önünde | Ana dal | **Tut** |
| `origin/002-production-hardening` | Entegrasyon ucu | 56 önde, 0 geride | **Tut**; PR/CI ve `main` birleşimi tamamlanana kadar silme |
| `origin/feature/exam-blueprint` | Tam commit atası; 0 benzersiz, 26 geride | 30 commit önde | **Uzak dalı silmek güvenli**; tekrar merge etme |
| `origin/hardening/frontend-reliability` | Tam commit atası; 0 benzersiz, 42 geride | 14 commit önde | **Uzak dalı silmek güvenli**; tekrar merge etme |
| `origin/hardening/runtime-safety` | Tam commit atası; 0 benzersiz, 41 geride | 15 commit önde | **Uzak dalı silmek güvenli**; tekrar merge etme |
| `origin/docs/refresh-after-merge` | Atası değil; 1 benzersiz commit | 1 commit önde | **Şimdilik tut ve incele** |

Benzersiz dal:

- `a7b97d8` — `Refresh the docs after the merge made half their warnings wrong`
- `git cherry` bunu `+` olarak gösteriyor; `002` içinde patch-equivalent bir kopyası yok.
- 23 doküman/görsel dosyasını, 15 yenilenmiş ekran görüntüsünü kapsıyor. Önce güncelliği kontrol edilip seçici biçimde entegre edilmeli; sonra silinebilir.

Ek güvenlik notları:

- Bu dört ilgili çalışma ağacı temizdi.
- Uzak dal silme, yerel worktree/dalları otomatik kaldırmaz.
- Yerel `003-product-portal` uzakta görünmüyor; `002`ye göre 3 benzersiz commit ve ayrıca kaydedilmemiş değişiklikler taşıyor. Ona kesinlikle dokunulmamalı.
- Hiçbir fetch, düzenleme, silme, commit veya push yapmadım.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:391-391|note=[Uzak dal silmeden once commit soyunu kanitlama ilkesi]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019fdd94-c341-7f52-b0e0-f64121ff9848
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>/root/e2e_env_audit (Dirac)</code> — 14.8 MiB — closed</summary>

- Session: `019fed08-226a-7bc3-b6c7-84437b98b17a`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T18:56:01.131Z`
- Source log: `rollout-2026-08-10T21-56-01-019fed08-226a-7bc3-b6c7-84437b98b17a.jsonl`

<pre>
İnceleme sonucu: başarısızlıklar tamamen ortam kaynaklı değildi; iki ayrı neden vardı.

1. Belge/sohbet/sınav zaman aşımları ortam kaynaklıydı.

- API, `WORKER_DATABASE_URL` yoksa worker’ı `DATABASE_URL` ile yani `dou_app` olarak çalıştırıyor: [worker.py:34]($HOME/code/dou-product-portal/apps/api/app/worker.py:34).
- `0010` göçü `dou_app` rolünden `ingestion_jobs UPDATE` yetkisini bilinçli çekiyor: [0010_ingestion_retry.sql:52]($HOME/code/dou-product-portal/supabase/migrations/0010_ingestion_retry.sql:52).
- Worker’ın ilk işi `ingestion_jobs` üzerinde `UPDATE ... RETURNING` ile işi sahiplenmek: [pipeline.py:165]($HOME/code/dou-product-portal/apps/api/app/modules/ingestion/pipeline.py:165).
- Dolayısıyla görülen `permission denied for table ingestion_jobs` ve ardından gelen “belge 20 sn içinde işlenmedi” zinciri deterministik bir yanlış başlangıç ortamıydı; ürünün ingestion algoritması bozuk olduğuna kanıt değil.
- Yerelde `WORKER_DRAIN_URL` boş bırakılabilir; bu durumda süreç içi `drain()` çalışır: [internal.py:98]($HOME/code/dou-product-portal/apps/api/app/api/internal.py:98). Ama `WORKER_DATABASE_URL` mutlaka `dou_worker` olmalı.

2. Giriş testi gerçek bir sözleşme eskimesiydi.

`HEAD 8620091` üzerindeki eski test `/courses` bekliyordu, ürün artık `/dashboard` açıyor. Çalışma ağacındaki düzeltme doğru: [flows.spec.ts:340]($HOME/code/dou-product-portal/apps/web/e2e/flows.spec.ts:340).

Ayrıca bu yalnız yerel komut sorunu değildi: `HEAD` üzerindeki CI başlangıcında da `WORKER_DATABASE_URL` eksikti. Çalışma ağacında `.github/workflows/ci.yml` dosyasına eklenmiş mevcut satır doğru düzeltme: [ci.yml:270]($HOME/code/dou-product-portal/.github/workflows/ci.yml:270). Bu iki değişiklik şu an unstaged; ben dosyalara dokunmadım.

Temiz ve çakışmasız tekrar koşum için önerdiğim kesin düzen:

```bash
cd $HOME/code/dou-product-portal
export PATH=&quot;/opt/homebrew/opt/postgresql@16/bin:$PATH&quot;
E2E_DB_NAME=dou_synapse_preview_portal_20260810_2

createdb &quot;$E2E_DB_NAME&quot;
for migration in supabase/migrations/*.sql; do
  psql -v ON_ERROR_STOP=1 -q -d &quot;$E2E_DB_NAME&quot; -f &quot;$migration&quot;
done

psql -v ON_ERROR_STOP=1 -d &quot;$E2E_DB_NAME&quot; \
  -c &quot;ALTER ROLE dou_app LOGIN PASSWORD &#x27;dou_app_local&#x27;&quot; \
  -c &quot;ALTER ROLE dou_worker LOGIN PASSWORD &#x27;dou_worker_local&#x27;&quot; \
  -c &quot;GRANT CONNECT ON DATABASE \&quot;$E2E_DB_NAME\&quot; TO dou_app, dou_worker&quot;

psql -v ON_ERROR_STOP=1 -q -d &quot;$E2E_DB_NAME&quot; -f supabase/seed_demo.sql
```

Özel DB’de `local_dev_setup.sql` dosyasını tek başına kullanmamak daha doğru; bağlantı iznini sabit `dou_synapse` adına veriyor: [local_dev_setup.sql:10]($HOME/code/dou-product-portal/supabase/local_dev_setup.sql:10). Yukarıdaki komut, pytest altyapısının kullandığı doğru modeli izliyor: [conftest.py:45]($HOME/code/dou-product-portal/apps/api/tests/conftest.py:45), [conftest.py:65]($HOME/code/dou-product-portal/apps/api/tests/conftest.py:65).

Yeni API’yi mevcut sunucularla çakışmayan portta başlatma:

```bash
cd $HOME/code/dou-product-portal/apps/api

ENVIRONMENT=local \
DEV_AUTH_ENABLED=true \
DATABASE_URL=postgresql+psycopg://dou_app:dou_app_local@localhost:5432/dou_synapse_preview_portal_20260810_2 \
WORKER_DATABASE_URL=postgresql+psycopg://dou_worker:dou_worker_local@localhost:5432/dou_synapse_preview_portal_20260810_2 \
WORKER_DRAIN_URL= \
CORS_ORIGINS=&#x27;[&quot;http://localhost:3125&quot;]&#x27; \
LLM_FAKE_PROVIDER=true \
EMBEDDING_PROVIDER=hashing \
EMBEDDING_WARMUP_ENABLED=false \
STORAGE_BACKEND=local \
STORAGE_ROOT=/private/tmp/dou-portal-e2e-storage-20260810-2 \
uv run uvicorn app.main:app --port 8025
```

Ardından:

```bash
cd $HOME/code/dou-product-portal/apps/web
E2E_API_URL=http://localhost:8025 \
E2E_PORT=3125 \
node_modules/.bin/playwright test --workers=1
```

Son hüküm:

- Giriş yönlendirme hatası: test sözleşmesi eskimesi, çalışma ağacında düzeltilmiş.
- Belge işlemeyen bütün görülen vakalar: eksik `WORKER_DATABASE_URL` kaynaklı.
- CI da aynı eksikliği taşıyordu; mevcut unstaged CI düzeltmesi gerekli.
- Önceki koşu kesildiği için henüz “başka hata kesinlikle yok” denemez; temiz DB + doğru worker rolüyle 35 testin tamamı yeniden bitmeli.
- E2E otomatik teardown hâlâ yok; test açıkça veri temizlemediğini söylüyor: [flows.spec.ts:15]($HOME/code/dou-product-portal/apps/web/e2e/flows.spec.ts:15). `E2E_DATABASE_NAME` de bugün yalnız CI’da tanımlı, kod tarafından kullanılmıyor. Bu nedenle her doğrulama koşusunda benzersiz DB en güvenli yol.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:793-800|note=[parallel DOU worktrees require isolated test databases]
MEMORY.md:30-32|note=[parallel test failures should be isolated with distinct database names]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019fe6f8-90cc-74d3-a2e2-8ff8e00be499
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>/root/spec_status_audit (Anscombe)</code> — 14.9 MiB — closed</summary>

- Session: `019fed08-3405-73c2-82ad-901936c6c754`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T18:56:05.638Z`
- Source log: `rollout-2026-08-10T21-56-05-019fed08-3405-73c2-82ad-901936c6c754.jsonl`

<pre>
Read-only denetim tamamlandı; hiçbir dosyayı değiştirmedim.

## Şimdi kapatılabilecekler: 53 görev

Ölçülen kanıt notu eklenerek `[x]` yapılabilir:

- Faz 0: `T002`, `T004–T007`
- Faz 1: `T101–T110`
- Faz 2: `T201–T214`
- Faz 3: `T301–T303`, `T306–T308`
- Faz 4: `T401`, `T412`, `T420–T422`, `T430–T432`, `T434–T435`
- Faz 5: `T501`, `T505`
- Faz 6: `T601–T606`

Bunları destekleyen mevcut ölçümler:

- Backend hedefli: 40 geçti
- Backend tam: 841 geçti
- Frontend: 301 geçti
- Ruff, format, mypy, typecheck ve production build: temiz
- OpenAPI: çalışan uygulamayla eşit, 50 yol
- Şema: 25 tablo, `0001–0014`
- Portal RLS nöbetçisi: 3/3 referans kapısı, 3/3 mutasyon sızıntısı yakalandı
- Portal Playwright: hedefli 7 senaryo geçmiş durumda
- Admin gate, tek `/me/profile`, POST gövdesinde kullanıcı araması ve PII allowlist’i testlerde gözleniyor

`T608` koşullu olarak 54. görev olabilir: ağ sırası ve tek profil isteği testli; fakat konsol/page-error kontrolünün açıkça kaydedildiği kanıt yok. Manuel tarayıcı turunda konsol da gerçekten kontrol edildiyse kapatılabilir; aksi halde açık kalmalı.

## Açık kalması gerekenler

### Belge/entegrasyon

- `T001`: Gerçek taban artık `a8a8a36`; görev hâlâ `b8da84e` diyor.
- `T003`: Sekiz belge var, fakat durum ve taban metinleri bayat.
- `T008`: Constitution tablosu hâlâ uygulama öncesi “tasarım koşuluyla” ifadeleri taşıyor.
- `T609`: Docs gate şu anda yeşil değil; `28` E2E iddiasına karşı ölçülen sayı `35`.
- `T610`: Dal hâlâ upstream’siz ve çalışma ağacı kirli.

### Gerçek ürün boşlukları

- `T402`: Dashboard’da yürüyen sınav/availability alanı yok; öğrenciye Asistan ve “Çalışmaya devam et” bağlantısı koşulsuz çiziliyor.
- `T410`: Eğitmen kartında `documents_failed` ayrı metrik değil; uyarı failed veya draft’tan yalnız birini gösteriyor.
- `T411`: Eğitmen kartında yalnız Soru havuzu, Sınav planı ve Ders ayarları doğrudan bağlı. Kaynak laboratuvarı, sınavlar ve analitik doğrudan linkleri eksik; AI politikası da açık isimli bir giriş değil.
- `T413`: Tanımlanan sınıf özeti yüzeyi bulunmuyor; yalnız genel kullanıcı/aksiyon özeti var.
- `T305`: `PortalMetrics` loading/empty/partial/error durumlarını uygulamıyor; bunlar çağıran sayfalara dağılmış.
- `T304`: Profil paylaşımı var, fakat aynı mount içinde kullanıcı değişimi/cache temizliği için açık test veya kullanıcı anahtarlı reset yok.

### Eksik kabul kanıtları

- `T215`: Adminin üye olmadığı akademik uca erişememesi ASGI testinde var; görevde istenen gerçek ağ üzerinden HTTP kanıtı yok.
- `T309`: Kod `/dashboard`a yönlendiriyor; eski tam E2E beklentileri şimdi düzeltiliyor. Tam koşum geçince kapanabilir.
- `T403`: Sahte OBS/GPA verisi kodda yok, fakat görevde istenen boş/az veri tarayıcı senaryosu yok.
- `T423`: PATCH sonrası provider yenilemesi kodda var; tarayıcıda ad değiştirip üst çubuk/profil yenilenmesini kanıtlayan test yok.
- `T433`: Filtre, pagination ve durum kodu var; E2E yalnız sekmelere geçiyor. Filtre/sayfalama/empty/error/partial yolculukları çalıştırılmamış.
- `T502`: `useSession(courseId)` düzeltmesi var, fakat blueprint sayfasına özel karma rol regresyon testi yok.
- `T503–T504`: Yeni test yalnız dashboard’u 375 px, koyu tema ve odak açısından kontrol ediyor. Profil ve admin mobil/masaüstü doğrulaması eksik; test ayrıca henüz commitli değil.
- `T607`: Tam 35 senaryoluk E2E henüz yeşil değil. İzole DB’nin koşum sonunda silinmesi de kanıta eklenmeli.
- `T608`: Konsol hatasızlığı açık kanıtlanmadıysa açık kalmalı.
- `T701–T710`: Tamamı açık kalmalı; gerçek Supabase, Storage, LLM, telemetry, alarm, load, backup/restore, staging ve production URL kanıtı yok.

Bu sınıflamayla `T608` hariç 53 tamam / 31 açık; konsol kanıtı kabul edilirse 54 tamam / 30 açık olur.

## Bayat belge ifadeleri

Şunlar güncellenmeli:

- [spec.md]($HOME/code/dou-product-portal/specs/003-product-portal/spec.md:4): `b8da84e` → `a8a8a36`
- [spec.md]($HOME/code/dou-product-portal/specs/003-product-portal/spec.md:6): “Draft; doğrulama bekliyor” artık doğru değil. “Kodlandı ve kısmen yerelde doğrulandı; tam E2E ve kalan kabul maddeleri açık; production kanıtlanmadı” uygun.
- [spec.md]($HOME/code/dou-product-portal/specs/003-product-portal/spec.md:37): “portal yüzeyleri henüz kodlanmamıştır” doğrudan yanlış.
- [plan.md]($HOME/code/dou-product-portal/specs/003-product-portal/plan.md:4), [tasks.md]($HOME/code/dou-product-portal/specs/003-product-portal/tasks.md:4), [full-product-roadmap.md]($HOME/code/dou-product-portal/specs/003-product-portal/full-product-roadmap.md:4): taban SHA bayat.
- [research.md]($HOME/code/dou-product-portal/specs/003-product-portal/research.md:4): ya `a8a8a36` olmalı ya da “araştırmanın ilk snapshot’ı” diye tarihsel olduğu açıklanmalı.
- [data-model.md]($HOME/code/dou-product-portal/specs/003-product-portal/data-model.md:5): migration/RLS/commit artık beklemiyor; commitli ve mutasyonla yerelde doğrulandı.
- [contracts/api.md]($HOME/code/dou-product-portal/specs/003-product-portal/contracts/api.md:18): OpenAPI doğrulaması bekliyor ifadesi bayat; 50 yolluk export eşit ölçüldü.
- [quickstart.md]($HOME/code/dou-product-portal/specs/003-product-portal/quickstart.md:11) ve teslim tablosu: hedefli API/RLS, frontend build ve portal tarayıcı kanıtlarını artık “bekliyor” göstermemeli; tam E2E ayrıca açık yazılmalı.
- [full-product-roadmap.md]($HOME/code/dou-product-portal/specs/003-product-portal/full-product-roadmap.md:47): portal için “tam kapı sonucu bekliyor” yerine ölçülen ve kalan kapılar ayrı yazılmalı.
- [002 planı]($HOME/code/dou-product-portal/specs/002-production-hardening/plan.md:32): `28` Playwright vakası bayat; statik ölçüm `35`.

Denetim sırasında çalışma ağacı eşzamanlı olarak değişiyordu: `.github/workflows/ci.yml`, `flows.spec.ts` ve `portal.spec.ts` düzenleniyordu. Bu nedenle final checkbox düzenlemesinden hemen önce HEAD/status yeniden ölçülmeli.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:939-944|note=[parallel worktree isolation and unique test database discipline]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019feafc-8971-7ca0-a58d-f091f3fde5ea
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>/root/dashboard_hardening (Bacon)</code> — 0.8 MiB — closed</summary>

- Session: `019fed0e-cf62-7713-99c2-cbbb0ebbe1f8`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T19:03:18.627Z`
- Source log: `rollout-2026-08-10T22-03-18-019fed0e-cf62-7713-99c2-cbbb0ebbe1f8.jsonl`

<pre>
Portal dashboard boşlukları tamamlandı.

- Öğrenci sınav kilitleri tüm dersler için tek batched sorguyla hesaplanıyor; mevcut kesin bitiş/blueprint süresi kuralı kullanılıyor.
- Eğitmenler hiçbir zaman kilitlenmiyor.
- Kilitliyken Asistan bağlantısı kaldırılıyor, sunucu mesajı gösteriliyor ve ana eylem sınava yönleniyor.
- `documents_failed` ayrı gösteriliyor; taslak soru uyarısı artık onu gizlemiyor.
- Eğitmen için kaynaklar, sorular, blueprint, sınav, ayarlar ve analitik bağlantılarının tamamı eklendi.
- Yalnızca ayrılan yedi dosya değiştirildi; E2E/CI dosyalarındaki mevcut başka-şerit değişikliklerine dokunulmadı.

Doğrulama:

- Portal backend: `18 passed`
- Sınav kilidi/blueprint regresyonları: `11 passed`
- Frontend kütüphane testleri: `304 passed`
- Ruff lint + format: geçti
- Mypy: geçti
- TypeScript: geçti
- Next.js production build: geçti
- `git diff --check`: temiz

Dal `003-product-portal`, HEAD hâlâ `8620091`; commit veya push yapılmadı. E2E çalıştırılmadı, kapsam gereği ilgili dosyalara dokunulmadı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.3 MiB — closed</summary>

- Session: `019fed0e-d057-7312-ad0c-e0ea70c7dda5`
- Parent: `019fed0e-cf62-7713-99c2-cbbb0ebbe1f8`
- Started: `2026-08-10T19:03:18.872Z`
- Source log: `rollout-2026-08-10T22-03-18-019fed0e-d057-7312-ad0c-e0ea70c7dda5.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/portal_e2e_gaps (Leibniz)</code> — 0.7 MiB — closed</summary>

- Session: `019fed0e-e7bd-7f50-8fa9-24735d2f4fb2`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T19:03:24.861Z`
- Source log: `rollout-2026-08-10T22-03-24-019fed0e-e7bd-7f50-8fa9-24735d2f4fb2.jsonl`

<pre>
Yalnız [portal.spec.ts]($HOME/code/dou-product-portal/apps/web/e2e/portal.spec.ts:305) genişletildi; başka dosyaya dokunmadım.

Eklenen kapsam:

- Gerçek profil `PATCH`: ad değişikliği, sunucu `GET` doğrulaması, üst çubuk ve profil alanının tam yenileme sonrası güncel kalması; test sonunda eski ad geri yükleniyor.
- Karma rol blueprint regresyonu: global öğrenci Burak’ın eğitmen olduğu derste dashboard aracı, blueprint UI ve API `200`; öğrenci olduğu derste araç gizli, sayfa kapalı ve API `403`.
- Dashboard, profil ve admin için 375 px yatay taşma, gerçek koyu tema tokenı ve klavyeyle görünür odak halkası kontrolleri.
- Admin ölçümü hem sağlık özeti hem kullanıcı listesi yüklendikten sonra yapılıyor.

Doğrulama:

- `bun run typecheck`: geçti.
- Playwright keşfi: geçti, `portal.spec.ts` içinde 10 test bulundu.
- `git diff --check`: geçti.
- Talimat gereği paylaşımlı DB kullanan E2E koşumu çalıştırılmadı.
- Commit veya push yapılmadı.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:22-26|note=[blueprint UI and verification context]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019feafc-8977-7b02-b768-15965bb69c4f
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.3 MiB — closed</summary>

- Session: `019fed0e-e869-7152-80bb-02f9bf5df178`
- Parent: `019fed0e-e7bd-7f50-8fa9-24735d2f4fb2`
- Started: `2026-08-10T19:03:25.033Z`
- Source log: `rollout-2026-08-10T22-03-25-019fed0e-e869-7152-80bb-02f9bf5df178.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/portal_e2e_gaps/portal_test_design (Gauss)</code> — 0.8 MiB — closed</summary>

- Session: `019fed0f-a6a2-7651-943b-f391118bcd90`
- Parent: `019fed0e-e7bd-7f50-8fa9-24735d2f4fb2`
- Started: `2026-08-10T19:04:13.730Z`
- Source log: `rollout-2026-08-10T22-04-13-019fed0f-a6a2-7651-943b-f391118bcd90.jsonl`

<pre>
Düzeltmeleri gördüm. Son bir statik turda özellikle klavye yardımcı döngüsünün gerçek tab sırasını, profil temizliğinin güvenliğini ve blueprint testinin dashboard’daki “Sınav planı” bağlantısını gerçekten kapsayıp kapsamadığını kontrol ediyorum.
</pre>

</details>

<details>
<summary><code>/root/e2e_teardown (Schrodinger)</code> — 16.0 MiB — closed</summary>

- Session: `019fed19-e032-77a1-8e82-d03decdfd370`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T19:15:23.827Z`
- Source log: `rollout-2026-08-10T22-15-23-019fed19-e032-77a1-8e82-d03decdfd370.jsonl`

<pre>
T901/T902 altyapısı tamamlandı; ürün API’sine, migration’a veya ders silme yetkisine dokunulmadı.

Yapılanlar:

- Koşu bazlı `E2E-&lt;run&gt;-&lt;sayı&gt;` ders kodları.
- Playwright `globalSetup` ile tek koşu kimliği.
- `globalTeardown` ile yalnız aynı koşuya ait dersleri DB seviyesinde silme.
- Varsayılan kuru koşu yapan `e2e:clean`; silme yalnız `--evet` ile.
- `COME 331` kodu ve `c3b76077-20de-47e5-9fe1-4e770ffa64d2` UUID’si SQL filtresinde açıkça korunuyor.
- `E2E_DATABASE_NAME` zorunlu. Yerelde `dou_synapse`, sistem DB’leri ve adı `e2e/test/preview` taşımayan DB’ler reddediliyor.
- `dou_synapse` istisnası yalnız `CI=true &amp;&amp; GITHUB_ACTIONS=true` olduğunda geçerli.
- Şemadaki courses bağlantılarının **20/20’sinin `ON DELETE CASCADE`** olduğu doğrulandı.

Kanıt:

- Birim güvenlik testleri: **4/4 geçti, 15 assertion**.
- TypeScript: temiz.
- `git diff --check`: temiz.
- Kuru koşu mutasyonu: 1 kayıt listelendi, silinmedi ve DB’de 1 kaldı; `--evet` sonrası 0.
- Başarısız Playwright vakasında teardown yine çalıştı: önceki ve güncel üç artık dersi sildi, DB’de **0** kaldı.
- Başarılı Playwright vakası: **1/1 geçti**, oluşturduğu dersi teardown sildi, DB’de **0** kaldı.
- İzole DB son ölçümü: `50 toplam | 0 yeni run-scoped artık | 38 eski biçimli E2E artık | 12 diğer ders`. Eski biçimli 38 kayıt güvenlik nedeniyle otomatik silinmedi.
- Geçici API kapatıldı.

Dokunduğum dosyalar:

- `apps/web/e2e/fixtures.ts`
- `apps/web/e2e/global-setup.ts`
- `apps/web/e2e/cleanup.ts`
- `apps/web/e2e/global-teardown.ts`
- `apps/web/lib/e2e-cleanup.test.ts`
- `apps/web/e2e/flows.spec.ts`
- `apps/web/e2e/portal.spec.ts`
- `apps/web/playwright.config.ts`
- `apps/web/package.json`

Notlar:

- Tam E2E paketi bu şeritte **KOŞULMADI**; rebase sonrası parent koşacak.
- Bir portal testi, paralel dashboard değişikliğinde etiketin `Ders ayarları` yerine `AI politikası` olmasından kırmızı kaldı. Cleanup kusuru değil; tam tersine başarısız testte teardown kanıtı olarak kullanıldı.
- Rebase sırasında upstream’deki `grepInvert/EKRAN` ayarı korunmalı ve yanına bu `globalSetup/globalTeardown` satırları alınmalı.
- Commit/push yapmadım.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:49-72|note=[T901 run scoped cleanup design and protected demo constraints]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019feafc-8972-77d1-95c4-89e87361833a
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.5 MiB — closed</summary>

- Session: `019fed19-e0bc-7e11-b6c5-e16a672e7f58`
- Parent: `019fed19-e032-77a1-8e82-d03decdfd370`
- Started: `2026-08-10T19:15:23.964Z`
- Source log: `rollout-2026-08-10T22-15-23-019fed19-e0bc-7e11-b6c5-e16a672e7f58.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/spec_truth_map (Raman)</code> — 16.1 MiB — closed</summary>

- Session: `019fed1e-0c27-7ae2-8a44-5e04ef540a35`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T19:19:57.223Z`
- Source log: `rollout-2026-08-10T22-19-57-019fed1e-0c27-7ae2-8a44-5e04ef540a35.jsonl`

<pre>
Read-only audit complete. Hard verdict: current tree is not eligible for blanket `[x]` marking because [tasks.md]($HOME/code/dou-product-portal/specs/003-product-portal/tasks.md:12) requires implementation and evidence on the same commit, while `003-product-portal` is dirty. Still, most implementation is ready.

### 1. Implementation-ready — final evidence commitinde `[x]` yapılabilir

No missing product work observed in these 53 tasks:

- `T002, T004–T007`
- `T101–T110`
- `T201–T202, T204–T213, T215`
- `T301, T303, T306–T309`
- `T401–T402`
- `T410–T412`
- `T420–T423`
- `T430–T431, T433–T435`
- `T501–T505`

Main evidence:

- Admin security core: [0014 migration]($HOME/code/dou-product-portal/supabase/migrations/0014_platform_admin_console.sql:10), RLS/grants [44–51]($HOME/code/dou-product-portal/supabase/migrations/0014_platform_admin_console.sql:44), authorization/audit [53–111]($HOME/code/dou-product-portal/supabase/migrations/0014_platform_admin_console.sql:53), safe projections [113–439]($HOME/code/dou-product-portal/supabase/migrations/0014_platform_admin_console.sql:113).
- Profile API: [profile.py]($HOME/code/dou-product-portal/apps/api/app/api/profile.py:16), strict update schema [schemas/profile.py]($HOME/code/dou-product-portal/apps/api/app/schemas/profile.py:29).
- Dashboard aggregation and exam lock: [dashboard.py]($HOME/code/dou-product-portal/apps/api/app/api/dashboard.py:64), batch lock logic [exam_state.py]($HOME/code/dou-product-portal/apps/api/app/modules/assessment/exam_state.py:146).
- Fail-closed admin dependency: [deps.py]($HOME/code/dou-product-portal/apps/api/app/api/deps.py:152); endpoints: [admin.py]($HOME/code/dou-product-portal/apps/api/app/api/admin.py:30).
- Backend assertions: [test_portal.py]($HOME/code/dou-product-portal/apps/api/tests/test_portal.py:82).
- Instructor/student actions: [dashboard.ts]($HOME/code/dou-product-portal/apps/web/lib/dashboard.ts:51), [dashboard-course-card.tsx]($HOME/code/dou-product-portal/apps/web/components/portal/dashboard-course-card.tsx:29).
- Profile/data rights: [profile page]($HOME/code/dou-product-portal/apps/web/app/profile/page.tsx:97).
- Read-only Bilgi İşlem tables, filters and states: [admin page]($HOME/code/dou-product-portal/apps/web/app/admin/page.tsx:275), [admin-data-table.tsx]($HOME/code/dou-product-portal/apps/web/components/portal/admin-data-table.tsx:13).
- Role/mobile/admin journeys: [portal.spec.ts]($HOME/code/dou-product-portal/apps/web/e2e/portal.spec.ts:194).

### 2. Gerçek açıklar — henüz `[x]` yapılmamalı

| Tasks | Eksik |
|---|---|
| `T001` | Belgelerde `b8da84e` bayat. Gerçek mevcut merge-base `a8a8a36`; beklenen rebase tabanı şu an `3b707ca`. |
| `T003` | Sekiz belge var fakat base/status metinleri güncel değil. |
| `T008` | Constitution VIII/X ancak final aday kapıları sonrası kapanabilir. |
| `T203, T302` | Backend/TS’ye `assistant_locked`, `assistant_lock_reason`, `assistant_lock_message` eklendi; [API contract]($HOME/code/dou-product-portal/specs/003-product-portal/contracts/api.md:103), data-model ve generated OpenAPI hâlâ bu alanları taşımıyor. |
| `T214` | SQL test matrisi negatif `offset` içermiyor; ayrıca `role`/`is_platform_admin` ile açık self-promotion reddi doğrudan assert edilmiyor. [Mevcut matris]($HOME/code/dou-product-portal/apps/api/tests/test_portal.py:441). |
| `T304` | Profil provider paylaşımı var, fakat kullanıcı kimliğine göre anahtarlama/reset yok. Provider [burada]($HOME/code/dou-product-portal/apps/web/components/portal/portal-profile-context.tsx:14); logout/user-switch cache davranışı test edilmemiş. |
| `T305` | `PortalMetrics` yalnız veri çiziyor; task’ın istediği loading/empty/partial/error durumlarına sahip değil. Ya task “sayfa düzeyinde state” diye düzeltilmeli ya bileşen genişletilmeli. [portal-metrics.tsx]($HOME/code/dou-product-portal/apps/web/components/portal/portal-metrics.tsx:9). |
| `T403` | Backend boş ders testi var; sahte GPA/dönem/danışman üretmediğini gösteren açık boş/az-veri tarayıcı vakası yok. |
| `T413` | Bireysel içerik sızmıyor ama görünür bir “sınıf özeti” de yok. Task ya privacy-negatif assertion olarak yeniden yazılmalı ya ölçülmüş aggregate eklenmeli. |
| `T432` | Placeholder ve API tam-e-posta reddi var; UI’dan tam e-posta yazıp URL/body/boş sonuç kontrolü yapan yolculuk eksik. Mevcut E2E yalnız ilk POST’u ölçüyor: [portal.spec.ts]($HOME/code/dou-product-portal/apps/web/e2e/portal.spec.ts:398). |

### 3. Final aday kapıları

`T601–T610` açık kalmalı.

Özellikle:

- `T602`: 841 sayısı bayat; final tam pytest ölçülmeli.
- `T605`: güncel kaynakta statik ölçüm 308 frontend testi/22 dosya gösteriyor; bu yeni ağacın unit/typecheck/build’i birlikte geçmeli.
- `T606`: OpenAPI dashboard lock alanları nedeniyle artık bayat.
- `T607`: mevcut ağaçtaki 10 portal + 21 normal akış final Playwright koşusunda doğrulanmalı.
- `T609`: rebase öncesi `docs_check` E2E’yi ekran görüntüsü vakalarıyla 38 sayıyor. `3b707ca` üzerindeki `EKRAN` kapısı geldikten sonra varsayılan sayı yeniden ölçülmeli; beklenen 31 olsa da elle yazılmamalı.
- `T610`: ağaç kirli, rebase/commit/push henüz yok.

### 4. T901/T902 durumu

Doğru yaklaşım uygulanmış: ürün API’sine ders silme yetkisi eklenmemiş.

- Run kimliği ve koruma listesi: [fixtures.ts]($HOME/code/dou-product-portal/apps/web/e2e/fixtures.ts:3)
- Kesin kod deseni: [fixtures.ts]($HOME/code/dou-product-portal/apps/web/e2e/fixtures.ts:36)
- Fail-closed DB seçimi: [cleanup.ts]($HOME/code/dou-product-portal/apps/web/e2e/cleanup.ts:29)
- Yalnız kesin run-prefix silme: [cleanup.ts]($HOME/code/dou-product-portal/apps/web/e2e/cleanup.ts:93)
- Varsayılan dry-run ve `--evet`: [cleanup.ts]($HOME/code/dou-product-portal/apps/web/e2e/cleanup.ts:136)
- Global teardown: [global-teardown.ts]($HOME/code/dou-product-portal/apps/web/e2e/global-teardown.ts:4)

Ancak henüz `[x]` değil: bilerek düşürülen bir Playwright koşusunda teardown’ın yine çalıştığı, ardından sıfır artık kaldığı ve COME 331’in korunduğu ölçülmeli.

### 5. Staging/production

`T701–T710` bütünüyle açık kalmalı. Bunlar gerçek Supabase Auth/Storage, Groq/Gemini, telemetry/alarm, load, backup/restore, insan eval, staging ve production URL kanıtlarıdır.

### Bayat belge noktaları

Base şu dosyalarda stale:

- [spec.md]($HOME/code/dou-product-portal/specs/003-product-portal/spec.md:4)
- [plan.md]($HOME/code/dou-product-portal/specs/003-product-portal/plan.md:4)
- [tasks.md]($HOME/code/dou-product-portal/specs/003-product-portal/tasks.md:4)
- [quickstart.md]($HOME/code/dou-product-portal/specs/003-product-portal/quickstart.md:24)
- [full-product-roadmap.md]($HOME/code/dou-product-portal/specs/003-product-portal/full-product-roadmap.md:4)
- [research.md]($HOME/code/dou-product-portal/specs/003-product-portal/research.md:4)

`spec.md:36–44`, `quickstart.md:11–15`, `quickstart.md:344–353`, `data-model.md:5` ve roadmap `37–56` da mevcut ilerlemenin gerisinde.

Önerilen şimdiki ifade:

&gt; **Status**: Portal, profil, Bilgi İşlem konsolu, dashboard sınav kilidi ve koşu-kapsamlı E2E temizliği yerel çalışma ağacında uygulanmıştır. Güncel aday SHA üzerinde tam backend/frontend/RLS/OpenAPI/Playwright/docs_check kapıları henüz tamamlanmadığı için bu sürüm “yerelde doğrulandı” değildir. Staging ve production kanıtları KOŞULMADI.

Final kapılar geçerse:

&gt; **Status**: Yerel release adayı. `&lt;SHA&gt;` üzerinde backend, RLS mutasyonu, frontend test/typecheck/build, OpenAPI, run-scoped Playwright ve rol bazlı tarayıcı yolculukları geçmiştir. Gerçek Supabase Auth/Storage, gerçek LLM, telemetry/alarm, load, backup/restore, staging deployment ve production URL KOŞULMADI; sürüm production’da kanıtlanmış değildir.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:63-72|note=[docs metrics and safe run scoped E2E cleanup rules]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019feafc-8972-77d1-95c4-89e87361833a
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>/root/portal_remaining_gaps (Descartes)</code> — 15.9 MiB — closed</summary>

- Session: `019fed25-7e13-7700-8ad4-2387f904087c`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T19:28:05.140Z`
- Source log: `rollout-2026-08-10T22-28-05-019fed25-7e13-7700-8ad4-2387f904087c.jsonl`

<pre>
Kalan düşük riskli portal açıklarını uyguladım; commit/push yapmadım ve diğer şeritlerin değişikliklerini korudum.

- T214: profil üzerinden `role`/`is_platform_admin` yükseltmesi ve `null full_name` reddi; negatif/null offset kontrolleri eklendi.
- T304: profil kaynağı kullanıcı kimliğiyle anahtarlandı; Ayşe’den çıkıp Burak’a girildiğinde admin profilinin taşınmadığı E2E senaryosu eklendi.
- T403: az verili gerçek derste tüm değerlerin `0`, “Henüz ölçülmedi” ve “Henüz etkinlik yok” kaldığı; sahte GPA/AGNO/dönem/danışman/program/duyuru üretilmediği test edildi.
- T432: mevcut kullanıcının tam e-postasının yalnız POST JSON gövdesine girdiği, URL’ye sızmadığı ve güvenli boş sonuç verdiği E2E iddiası eklendi.
- T413: eğitmen kartında yalnız başarısız belge sayısının taşındığı; dosya adı, depolama yolu ve hata metninin sızmadığı backend iddiası eklendi.

Doğrulama:

- Portal backend: **21 geçti**
- Hedefli frontend: **14 geçti**
- TypeScript: temiz
- Ruff + format: temiz
- Playwright keşfi: **12 portal senaryosu**
- `git diff --check`: temiz

Tam tarayıcı koşusunu paylaşılmış servislerle çalıştırmadım; parent’ın yeniden kuracağı son ortamda çalıştırılmalı.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:939-944|note=[Paralel worktree sahipligi ve ayri test veritabani kurali]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019feafc-8971-7ca0-a58d-f091f3fde5ea
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.3 MiB — closed</summary>

- Session: `019fed25-7e9f-7922-beeb-e410c39ba742`
- Parent: `019fed25-7e13-7700-8ad4-2387f904087c`
- Started: `2026-08-10T19:28:05.279Z`
- Source log: `rollout-2026-08-10T22-28-05-019fed25-7e9f-7922-beeb-e410c39ba742.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/portal_docs_truth (Plato)</code> — 29.9 MiB — closed</summary>

- Session: `019fed35-7aa1-7230-9996-6df231f54386`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T19:45:32.834Z`
- Source log: `rollout-2026-08-10T22-45-32-019fed35-7aa1-7230-9996-6df231f54386.jsonl`

<pre>
Tamamlandı. `git diff --check` temiz.

Güncellenen 11 Markdown dosyasında:

- 003 tabanı her yerde `3b707ca` oldu.
- Dashboard sözleşmesine üç sınav kilidi alanı eklendi.
- T305 sayfa düzeyinde loading/empty/error sahipliği olarak düzeltildi.
- T413 privacy-negative aggregate olarak netleştirildi.
- Kanıtlı Faz 0–5 işleri kapatıldı.
- T601–T610 ve T701–T710 açık bırakıldı.
- T901/T902, izole DB’de koşu bazlı ders + Bilgi İşlem audit temizliği ve `COME 331` korumasıyla kapatıldı.
- Ürün `DELETE course` önerisi kaldırıldı.
- Final metrikler elle yazılmadı; `docs_check` entegratöre bırakıldı.
- Commit/push yapılmadı.

Status’taki E2E ve OpenAPI değişiklikleri başka şeride ait; onlara dokunmadım.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.6 MiB — closed</summary>

- Session: `019fed35-7b32-7d61-83c9-346020e50ab6`
- Parent: `019fed35-7aa1-7230-9996-6df231f54386`
- Started: `2026-08-10T19:45:32.978Z`
- Source log: `rollout-2026-08-10T22-45-32-019fed35-7b32-7d61-83c9-346020e50ab6.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/portal_openapi (Hume)</code> — 29.3 MiB — closed</summary>

- Session: `019fed35-9083-7022-a1ab-59ee840991af`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T19:45:38.435Z`
- Source log: `rollout-2026-08-10T22-45-38-019fed35-9083-7022-a1ab-59ee840991af.jsonl`

<pre>
OpenAPI sözleşmesi resmî `create_app().openapi()` akışıyla güncellendi; elle düzenlenmedi ve veritabanına bağlanılmadı.

- Dal/HEAD: `003-product-portal` · `e7adec7`
- Değişen tek dosya: `specs/001-course-assistant-mvp/contracts/openapi.json`
- Sözleşme: **50 path**, **118 schema**
- Doğrulanan 7 portal yolu:
  - `/me/profile` — GET, PATCH
  - `/dashboard` — GET
  - `/admin/overview` — GET
  - `/admin/users` — POST
  - `/admin/courses` — GET
  - `/admin/requests` — GET
  - `/admin/ingestion` — GET
- `DashboardCourse` içine zorunlu olarak eklendi:
  - `assistant_locked`
  - `assistant_lock_reason`
  - `assistant_lock_message`
- Diff: **30 ekleme, 1 silme**
- `git diff --check`: temiz
- Üretilen dosya `/tmp` doğrulama çıktısıyla byte-byte aynı.
- Commit ve push yapılmadı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.2 MiB — closed</summary>

- Session: `019fed35-9106-7851-96ed-3607cd9270ea`
- Parent: `019fed35-9083-7022-a1ab-59ee840991af`
- Started: `2026-08-10T19:45:38.566Z`
- Source log: `rollout-2026-08-10T22-45-38-019fed35-9106-7851-96ed-3607cd9270ea.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/portal_security_final (Copernicus)</code> — 29.3 MiB — closed</summary>

- Session: `019fed35-a6c3-7db0-a43c-27629a4afe17`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T19:45:44.131Z`
- Source log: `rollout-2026-08-10T22-45-44-019fed35-a6c3-7db0-a43c-27629a4afe17.jsonl`

<pre>
Salt okunur güvenlik doğrulaması tamamlandı; ortak `dou_synapse` veritabanına dokunulmadı.

- Başlangıç: `003-product-portal` · `5a5d388`, taban/merge-base `3b707ca`.
- Bilgi İşlem RLS kapısı:
  - 3 referans yetki reddi doğru nedenle kapalı.
  - 3/3 sızıntı mutasyonu yakalandı: kendini admin yapma, fail-open admin yardımcısı, `PUBLIC EXECUTE`.
- Çekirdek RLS kapısı:
  - 109/109 referans iddiası geçti, `FAIL` yok.
  - 55/55 politika/fonksiyon mutasyonu ilgili testi kırmızıya çevirdi.
- Geçici DB kontrolü: portal şablonu/klonları, isolation şablonu ve tüm mutasyon klonları kaldırıldı; kalan eşleşen DB sayısı `0`.
- Dosya değiştirmedim, commit/push yapmadım.

Koşu sırasında paylaşılan worktree başka görev tarafından ilerledi: HEAD `e7adec7` oldu ve doküman/OpenAPI dosyalarında mevcut değişiklikler var. `5a5d388 → e7adec7` arasında `supabase/tests` ve `supabase/migrations` değişmedi; dolayısıyla güvenlik kanıtı güncel RLS koduyla aynı içeriği sınadı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.2 MiB — closed</summary>

- Session: `019fed35-a740-78a2-941f-3d0ada9b56af`
- Parent: `019fed35-a6c3-7db0-a43c-27629a4afe17`
- Started: `2026-08-10T19:45:44.256Z`
- Source log: `rollout-2026-08-10T22-45-44-019fed35-a740-78a2-941f-3d0ada9b56af.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/release_state_verify (Bohr)</code> — 214.2 MiB — closed</summary>

- Session: `019fed62-8f06-7721-a88e-f1cbc20a761d`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T20:34:47.175Z`
- Source log: `rollout-2026-08-10T23-34-47-019fed62-8f06-7721-a88e-f1cbc20a761d.jsonl`

<pre>
Doğrulama sonucu:

- `003-product-portal`, `002-production-hardening` içine gerçekten birleştirildi.
- Güncel ve uzaktaki `002` SHA’sı: `570ce55`.
- `002`, `main`den 71 commit ileride; `main` hâlâ eski `ae93417` noktasında.
- Çalışma alanları temiz ve yerel dallar GitHub’daki karşılıklarıyla aynı.
- Açık PR yok; bu nedenle `570ce55` GitHub CI’dan henüz geçmedi.
- `570ce55`, portal birleştirmesinden sonra E2E temizliğinin yanlış veritabanına bakmasını ve geç doğrulama yapmasını engelleyen dört dosyalık düzeltmedir.
- Hiçbir dosya, dal, PR veya Git referansı değiştirmedim.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.1 MiB — closed</summary>

- Session: `019fed62-8f67-7772-b653-b748126f0fdf`
- Parent: `019fed62-8f06-7721-a88e-f1cbc20a761d`
- Started: `2026-08-10T20:34:47.271Z`
- Source log: `rollout-2026-08-10T23-34-47-019fed62-8f67-7772-b653-b748126f0fdf.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/docs_refresh_audit (Galileo)</code> — 216.1 MiB — closed</summary>

- Session: `019fed62-d12a-7963-9449-2787653e39a1`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T20:35:04.106Z`
- Source log: `rollout-2026-08-10T23-35-04-019fed62-d12a-7963-9449-2787653e39a1.jsonl`

<pre>
## Hüküm

`a7b97d8` **cherry-pick/merge edilmemeli.** Dal yalnız belge ve PNG içeriyor; kod değeri yok. `ae93417` tabanından yazılmış, güncel `002` ise `570ce55`. Normal merge simülasyonu:

- 4 metin çatışması: `ARCHITECTURE.md`, `PLAN.md`, `docs/runbook.md`, `specs/001-course-assistant-mvp/quickstart.md`
- 6 binary çatışması: `03`, `05`, `06`, `09`, `10-nazik`, `15`
- Otomatik birleşen belgelerde de semantik bayatlık var.

Güncel ağaçta 14 migration/25 tablo, frontend 309 ve E2E 33 iken dal 7 migration/15 tablo/664 backend dönemini anlatıyor. Backend’i bu salt-okunur denetimde sandbox nedeniyle yeniden toplamadım; güncel kaynak işareti ve entegrasyon kanıtı 846.

## Metin dosyaları

### Değerli kaynak; yalnız elle seçilerek taşınmalı

- `docs/demo-script.md`
  - Altıncı sahnenin artık gösterilebilir olması.
  - İki ret türünün ayrı gösterilmesi.
  - “Neden yanlış?” ekran metni.
  - Ancak “soru üretimi gerçek anahtar ister” hâlâ yanlış ve bütün ekran akışı eski üst menüyü kullanıyor.

- `docs/instructor-guide.md`
  - Soru havuzu/analitik için önizleme uyarılarının kaldırılması.
  - `out_of_scope` ile `insufficient_context` ayrımı ve “Ölçüm yok ≠ 0” açıklaması.
  - Ancak blueprint, AI politikası, kaynak laboratuvarı, AI kalite, portal/profil/Bilgi İşlem yok; ayrıca sahte sağlayıcı hakkındaki eski uyarı kalıyor.

- `docs/student-guide.md`
  - İki ret türü açıklaması.
  - Sınav ve ilerleme ekranlarının gerçek ürün olarak anlatılması.
  - Ancak yeni `/dashboard`, profil/hesap, geri bildirim, sınav kilidi ve yeni ana menü yok.

- `docs/runbook.md`
  - Demo öncesi iki ret sorusunu prova etme maddesi.
  - Önizleme şeridi kalmadığını kontrol etme maddesi.
  - Ancak anahtarsız soru üretimi ve Compose RLS hakkındaki eski iddialar nedeniyle dosya bütünü alınmamalı.

### Teknik not olarak faydalı; mevcut dosyaya doğrudan uygulanmamalı

- `ARCHITECTURE.md`
  - `assess_evidence()` ile iki ret ayrımı, `0002`, `0006`, sahte soru üretimi ve KVKK sayfası notları değerlidir.
  - Fakat aynı patch şunları hâlâ yanlış söyler:
    - `/internal/drain` boş — artık dolu.
    - CI Docker build yok — artık var.
    - Compose superuser ile RLS’i atlıyor — artık `dou_app`/`dou_worker`.
    - model imaja gömülü değil — artık Dockerfile’a gömülü.
  - `0008`–`0014`, portal ve platform-admin mimarisi de yok.

- `PLAN.md`
  - Kapsam dışı ayrımı, sahte sağlayıcı soru üretimi ve altıncı demo sahnesi düzeltmeleri değerlidir.
  - 664 test ve portal öncesi kapsam nedeniyle doğrudan alınamaz.

### Alınmamalı

- `specs/001-course-assistant-mvp/quickstart.md`
  - 7 migration, 15 tablo, 664 test, Compose’da RLS yok, model imajda değil iddiaları güncel ağaçla çelişiyor.
  - Yalnız “sahte sağlayıcı soru üretebilir” bilgisi yeni quickstart’a elle yazılabilir.

- `docs/team/parallel/15_R5_BELGELER.md`
  - Tarihsel şerit raporu; “şeritler main’e girdi”, 664 test ve eski açıklar listesi artık yanlış.
  - Ürün belgesine değer katmıyor; commit geçmişi ve `002/003` task kayıtları daha doğru kaynak.

Ek bulgu: `docs/test-report.md` bu committe hiç değişmemiş ve hâlâ `out_of_scope` oranının %0 olduğunu söylüyor. Yeni belge turunda mutlaka kapsam içine alınmalı.

## Alınmaması gereken PNG’ler

Aşağıdaki 15 dosyanın **hiçbiri doğrudan alınmamalı**:

- `docs/images/01-giris.png`
- `docs/images/02-egitmen-ders-listesi.png`
- `docs/images/03-egitmen-materyaller.png`
- `docs/images/04-egitmen-katilimcilar.png`
- `docs/images/05-egitmen-soru-havuzu.png`
- `docs/images/06-egitmen-sinif-analitigi.png`
- `docs/images/07-ogrenci-ders-listesi.png`
- `docs/images/09-sohbet-kaynakli-cevap.png`
- `docs/images/10-sohbet-kapsam-disi-ret.png`
- `docs/images/10-sohbet-nazik-ret.png`
- `docs/images/11-sokratik-kademe-1.png`
- `docs/images/12-sokratik-kademe-2.png`
- `docs/images/13-sokratik-israr-ilerlemiyor.png`
- `docs/images/14-ogrenci-sinav-provasi.png`
- `docs/images/15-ogrenci-ilerleme.png`

Görüntüler gerçek veriden alınmış olsa da portal öncesi kabuğu gösteriyor: `Genel bakış / Dersler / Profil / Bilgi İşlem` ana menüsü yok; derslerde blueprint, AI politikası ve AI kalite sekmeleri yok. `01-giris.png` de güncel Supabase e-posta/parola seçeneğini temsil etmiyor. `10-sohbet-kapsam-disi-ret.png` ve `14-ogrenci-sinav-provasi.png` içerik olarak yararlı referanslar ama güncel kabukta yeniden çekilmeli.

## Güvenli entegrasyon

1. `a7b97d8` cherry-pick edilmez.
2. `570ce55` üstünde yeni bir docs-refresh dalı açılır.
3. Yukarıdaki yararlı metin parçaları güncel kodla tekrar doğrulanarak elle yazılır.
4. `ARCHITECTURE`, `PLAN`, quickstart ve `docs/test-report.md` birlikte güncellenir; sayılar `docs_check` kaynağından üretilir.
5. Portal, profil, Bilgi İşlem, blueprint, AI politikası, kalite ve iki ret akışı güncel tarayıcıdan yeniden görüntülenir.
6. Yeni PNG’ler ayrı committe eklenir; öğrenci/eğitmen/platform-admin görünürlükleri elle doğrulanır.
7. Belge kapısı ve bağlantı taraması geçtikten sonra `docs/refresh-after-merge` dalı “bilinçli olarak superseded” sayılıp kapatılabilir.

Kısacası: dalın **fikirleri kurtarılmalı, commit’i ve binary’leri alınmamalı.**

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:34-72|note=[source derived docs counts and stale screenshot safeguards]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019feafc-8972-77d1-95c4-89e87361833a
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>/root/release_claim_audit (Sagan)</code> — 236.5 MiB — closed</summary>

- Session: `019fed63-4595-7b90-88e3-045af000841f`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T20:35:33.909Z`
- Source log: `rollout-2026-08-10T23-35-33-019fed63-4595-7b90-88e3-045af000841f.jsonl`

<pre>
Tamamlandı. Yalnız izin verilen release dosyalarına dokundum; commit/push yapmadım. HEAD hâlâ `2c178861`.

Uygulanan kapı:

- Exact candidate SHA doğrulaması ve `main` soy kontrolü.
- 10 zorunlu check-run:
  - 5 core CI
  - 2 AI kalite
  - `Workflow dependency policy`
  - 2 CodeQL
- Eksik, skipped, failed, queued/in-progress ve sahte uygulama sonucu fail-closed.
- Dependency Review, PR aşamasına ait olduğu için main aday kapısında değil.
- İmaj yazma yetkileri yalnız doğrulama job’u geçtikten sonra devreye giriyor.
- Kanıt JSON’una 10 başarılı check URL’si ekleniyor.
- Workflow’daki 7 action referansının tamamı immutable SHA.

Değişen dosyalar:

- `.github/workflows/release-candidate.yml`
- `.release/verify_checks.py`
- `.release/test_verify_checks.py`
- `.release/evidence.schema.json`
- `.release/README.md`

Kanıt:

- 12/12 stdlib test geçti.
- Pozitif CLI örneği: `verified 10 required checks`.
- Skipped mutasyonu beklendiği gibi kırmızı.
- Workflow YAML parse edildi.
- Evidence schema JSON parse edildi.
- `git diff --check` temiz.
- Action pin denetimi: 7/7 immutable.

Kalan dürüst risk: canlı GitHub Actions koşusu yapılmadı. AI check’leri exact merged SHA üzerinde üretilmezse release bilinçli olarak bloke olur. Ayrıca check adları workflow job adlarına bağlı; ad değişirse required-check listesi de güncellenmeli. `specs/.../contracts/release-evidence.md` kapsam dışı olduğu için değiştirilmedi; yeni workflow-policy kontrolünü isimle saymıyor.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.6 MiB — closed</summary>

- Session: `019fed63-472e-72e3-80fd-7370ddeaa3f0`
- Parent: `019fed63-4595-7b90-88e3-045af000841f`
- Started: `2026-08-10T20:35:34.318Z`
- Source log: `rollout-2026-08-10T23-35-34-019fed63-472e-72e3-80fd-7370ddeaa3f0.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/ci_cd_audit (Parfit)</code> — 65.9 MiB — closed</summary>

- Session: `019fed86-af2d-7c72-8517-ed3d2f9def96`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T21:14:14.701Z`
- Source log: `rollout-2026-08-11T00-14-14-019fed86-af2d-7c72-8517-ed3d2f9def96.jsonl`

<pre>
Durdum; artık dosya değiştirmiyorum. Commit/push yapılmadı.

Dokunulan dosyalar:

- `.ai/**`
- `scripts/ai_sdlc_check.py`
- `scripts/test_ai_sdlc_check.py`
- `.github/workflows/ai-quality.yml`

Son kanıt: **26/26 test geçti.**

Eklenen sertleştirmeler:

- PR, manual ve `main` push için exact SHA bağı
- Mutable Git ref reddi
- Hassas rename/delete-add kaçışı engeli
- Politika minimumlarının düşürülememesi
- JSON tip çökmesi ve log-forgery koruması
- Git blob tabanlı hash doğrulaması
- Checkout credential kalıcılığının kapatılması
- Immutable action pinleri: [checkout v4.4.0](https://github.com/actions/checkout/releases/tag/v4.4.0) ve [setup-uv v6.8.0](https://github.com/astral-sh/setup-uv/releases/tag/v6.8.0)

Stop talimatı hash güncellemesinden hemen önce geldi. Entegratörün `.ai/changes/example.json` içinde güncellemesi gereken değerler:

- README: `2f1729bfc8477c5b9b53353e5f0fb493d6adb691c0c258a58b444b88de59c7ae`
- Validator: `2bf15107f5f3411d0e0525e1de87f8bb106f9f144e1f346728bc066148f0d430`
- Test: `555d492844dc54bb6b9e135163200aa477a8a0930f6dfaffd38290e2404126e4`
- Workflow: `511c827591407352d76781e724fdc04c31ec58fa7a26c799739838b3fc05c1a8`

Bu hashler güncellenmeden güncel aday için `AI_SDLC_CHECK=PASS` beklenmemeli. Son YAML/JSON ve gerçek geçici aday kontrolü de entegratöre kaldı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.7 MiB — closed</summary>

- Session: `019fed86-af7c-7651-b314-5e8c1a9a5daf`
- Parent: `019fed86-af2d-7c72-8517-ed3d2f9def96`
- Started: `2026-08-10T21:14:14.781Z`
- Source log: `rollout-2026-08-11T00-14-14-019fed86-af7c-7651-b314-5e8c1a9a5daf.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/ai_sdlc_audit (Boyle)</code> — 64.0 MiB — closed</summary>

- Session: `019fed87-16ec-7400-a80e-f5c6ec809a35`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T21:14:41.261Z`
- Source log: `rollout-2026-08-11T00-14-41-019fed87-16ec-7400-a80e-f5c6ec809a35.jsonl`

<pre>
## Net hüküm

`4dbf73d` üzerinde güçlü bir AI kalite altyapısı var; fakat kapalı döngü, release’i gerçekten durdurabilen bir AI SDLC henüz yok.

Mevcut yapı şunları iyi yapıyor: tekrarlanabilir eval harness’i, calibration/holdout ayrımı, retrieval metrikleri, fail-closed guardrail’ler, sağlayıcı fallback’i, embedding provenance, mahremiyet kontrollü kullanıcı geri bildirimi. Eksik kalan kritik halka ise:

&gt; Model/prompt/veri değişikliği → gerçek sağlayıcı ölçümü → insan değerlendirmesi → otomatik release kararı → production izleme → geri bildirimin regression testine dönüşmesi.

Bu nedenle proje “AI SDLC temeli güçlü” denebilir; “AI quality-gated production sistemi” henüz denemez.

Denetim değişmez hedef commit’i `4dbf73d` üzerinden `git show/git grep` ile yapıldı. İnceleme sürerken canlı `002-production-hardening` ucu `beca770d`’ye ilerledi; sonraki commit’ler bu rapora dahil değildir. Hiçbir dosya veya ref değiştirilmedi.

## Güçlü mevcut taraflar

- Eval sistemi bilimsel olarak dikkatli kurulmuş:
  - calibration/holdout, metadata ve “koşulmayanı çalışmış gibi göstermeme” kuralları: `evaluation/README.md:3-22`, `evaluation/README.md:68-88`
  - çalışma kimliği provider, model, embedding runtime, retrieval ayarları ve Git SHA içeriyor: `evaluation/evaluate.py:162-205`
  - bootstrap güven aralığı ve McNemar testi mevcut: `evaluation/metrics.py:271-348`
- Gold set doğrulayıcısı yapı, split çakışması, kaynak dosya/sayfa varlığı ve isteğe bağlı corpus kontrolü yapıyor: `evaluation/verify_gold_set.py:201-235`.
- Faithfulness süreci sahte sağlayıcıyı ve yetersiz/tek etiketleyicili örneklemi fail-closed reddediyor: `evaluation/faithfulness/score_labels.py:75-150`.
- Prompt injection’a karşı materyal talimattan ayrılıyor, XML-benzeri sınırlar kaçırılıyor: `apps/api/app/modules/generation/prompts.py:1-18`, `:27-93`, `:125-148`.
- Sokratik, soru-cevap ve sınav davranışları ayrı kurallara sahip: `apps/api/app/modules/generation/prompts.py:151-185`.
- Atıflar modelin yazdığı sayfa numarasına güvenmiyor; retrieve edilmiş chunk metadata’sından oluşturuluyor ve geçersiz atıf cevabı engelliyor: `apps/api/app/modules/guardrails/citation.py:42-125`.
- LLM katmanı timeout, retry, toplam deadline ve fallback taşıyor; token, model, provider ve süreyi ölçüyor: `apps/api/app/modules/generation/llm.py:192-290`.
- Production ortamı fake provider’ı reddediyor: `apps/api/app/core/config.py:323-329`.
- Embedding alanı provider/model/runtime sürümüyle tanımlanıyor ve ingest/query aynı kimliği kullanıyor: `apps/api/app/core/vector_space.py:16-100`.
- Kullanıcı geri bildiriminde öğrenci yalnız kendi mesajını değerlendirebiliyor; öğretmen yalnız açıkça paylaşılan metni görüyor: `apps/api/app/api/feedback.py:25-130`.
- CI; test, RLS mutasyon kanıtı, ağsız embedding, frontend, erişilebilirlik, build, doküman sayıları ve gerçek API+tarayıcı E2E içeriyor: `.github/workflows/ci.yml:12-303`.

## P0 — Release öncesi kapanmalı

### P0.1 — Release adayı için AI kalite kanıtı yok

Commit edilmiş eval sonuçlarının hiçbiri `4dbf73d` üzerinde üretilmemiş:

- sonuç SHA’ları `6c7419f`, `87a3636`, `ed2a805` veya `ccd8d13`;
- son E2E sonucu da `ccd8d13`: `evaluation/results/2026-08-09T1705-holdout-hybrid-fastembed-e2e.json:2-7`.

CI’daki bütün işler `.github/workflows/ci.yml:12-303` arasında; `evaluate.py`, gold-set doğrulaması veya faithfulness kapısı hiç çağrılmıyor. Dolayısıyla kod, retrieval/scope/citation/Sokratik kalite eşiğini aşmadan yeşil olabilir.

Gerekli çözüm:

- Hedef Git SHA’ya bağlı `ai-quality-gate` işi.
- Gold manifest doğrulaması.
- Retrieval için PR kapısı.
- Gerçek sağlayıcılı tam holdout için staging/release kapısı.
- Threshold ihlalinde merge/release bloklama.
- Sonuç JSON’unu CI artefaktı olarak saklama.

### P0.2 — Gerçek LLM ve insan değerlendirmesi tamamlanmamış

Repo bunu dürüstçe kabul ediyor:

- gerçek LLM anahtarı yok: `docs/test-report.md:620-621`;
- faithfulness etiketi koşulmamış, iki etiket dosyası boş: `docs/test-report.md:519-534`;
- gerçek LLM p95 ölçülmemiş: `docs/test-report.md:538-555`;
- gold set’i takım yazmış ve eğitmen incelemesi yapılmamış: `docs/test-report.md:625-630`;
- gerçek sağlayıcı, iki bağımsız etiketleyici ve eğitmen review hâlâ yapılacaklar arasında: `docs/test-report.md:641-653`.

Son eski E2E artefaktında harness `fake_provider:false` görürken sunucu notu açıkça fake provider diyor: `evaluation/results/2026-08-09T1705-holdout-hybrid-fastembed-e2e.json:26-34`. Bu da mevcut runtime kimliğinin güvenilir biçimde yakalanmadığını gösteriyor.

Repo zaten doğru P0 hedeflerini tanımlamış: `docs/PRODUCT_PARITY_AND_PRODUCTION_ROADMAP.md:107-130`. Bunlar uygulanıp mevcut SHA üzerinde kanıtlanmadan “production AI kalitesi” denmemeli.

### P0.3 — Release hedefleri yazılı fakat yürütülebilir değil

Kaynaksız cevap 0, uydurma atıf 0, kapsam dışı ret ≥%90 ve kritik Sokratik sızıntı 0 hedefleri belgede var: `docs/PRODUCT_PARITY_AND_PRODUCTION_ROADMAP.md:123-130`.

Ancak CI bunları okuyup karar vermiyor. Release kriterleri Markdown’dan makine tarafından okunan sürümlü bir policy dosyasına taşınmalı; gate sonucu hedef, gerçek değer, örneklem ve güven aralığıyla raporlanmalı.

## P1 — Kapalı AI SDLC için gerekli

### P1.1 — Prompt/model/provider/veri lineage eksik

Promptlar doğrudan Python sabitleri olarak tutuluyor: `apps/api/app/modules/generation/prompts.py:125-232`. Git geçmişi değişikliği bulabilir; ancak cevap veya eval kaydında prompt sürümü/hash’i yok.

Eval metadata’sı provider/modeli yazıyor fakat prompt hash’i, temperature, kaynak corpus digest’i ve deployment kimliği yok: `evaluation/evaluate.py:174-227`. Kod ayrıca E2E sunucu ayarını gerçekten gözlemleyemediğini kabul ediyor: `evaluation/evaluate.py:206-225`.

Her AI çalışması için şu kimlikler saklanmalı:

- `prompt_artifact_id`, sürüm ve SHA-256
- provider/model ve model revision
- temperature/parametreler
- embedding-space kimliği
- corpus/source manifest digest’i
- Git SHA ve deployment ID
- fallback/attempt bilgisi
- eval set sürümü

### P1.2 — Token telemetry var, gerçek maliyet yönetimi yok

LLM çağrıları provider/model/token/süre ölçüyor: `apps/api/app/modules/generation/llm.py:268-290`. Request log ise yalnız toplam token, latency ve cache bilgisi tutuyor: `apps/api/app/models/chat.py:108-127`.

Eksikler:

- tahmini/gerçek para maliyeti;
- input/output token ayrımı;
- provider/model bazlı p50/p95;
- fallback ve hata oranı;
- ders, görev ve tenant bazlı bütçe;
- maliyet veya latency SLO alarmı.

Append-only `ai_run_events` tablosu ve provider fiyat kataloğu eklenmeli.

### P1.3 — Kullanıcı feedback’i gerçek review döngüsüne bağlanmamış

Toplama ve mahremiyet tarafı güçlü; fakat feedback modelinde durum, reviewer, karar, düzeltme ve regression bağlantısı yok: `apps/api/app/models/chat.py:130-153`.

`açık → inceleniyor → doğrulandı/reddedildi → düzeltildi` yaşam döngüsü eklenmeli. “Düzeltildi” durumu ancak:

- bir regression/eval vakasına bağlanırsa,
- prompt/model/eşik değişikliği kaydedilirse,
- yeni eval koşusu geçerse

kapanabilmeli. Yol haritası da bunu açıkça istiyor: `docs/PRODUCT_PARITY_AND_PRODUCTION_ROADMAP.md:171-176`.

### P1.4 — Ders AI politikası görev bazlı değil

Mevcut policy mod, kaynak, hint, evidence threshold ve günlük token bütçesini kapsıyor: `apps/api/app/models/policy.py:19-40`.

Fakat sohbet, soru üretimi ve açık uçlu puanlama için ayrı provider/model/prompt/bütçe seçilemiyor. Bu boşluk belgede de kabul edilmiş: `docs/PRODUCT_PARITY_AND_PRODUCTION_ROADMAP.md:63-67`.

`chat`, `question_generation`, `grading` görevleri için ayrı:

- izinli provider/model;
- prompt artefaktı;
- parametreler;
- fallback;
- token ve para bütçesi;
- kalite eşiği

tanımlanmalı.

### P1.5 — Gold corpus tam dondurulmamış

Gold set yalnız `sample_data/isletim-sistemleri v2` gibi insan tarafından yazılmış material sürümü taşıyor: `evaluation/gold_set/holdout.json:1-11`. Dosya içerik hash’leri, parser/chunker sürümü ve corpus build digest’i yok.

Doğrulayıcı sayfanın varlığını kanıtlıyor; içeriğin aynı kaldığını veya gerçekten soruyu desteklediğini kanıtlamıyor: `evaluation/verify_gold_set.py:201-235`, `evaluation/gold_set/SCHEMA.md:100-106`.

Per-file SHA-256, extraction sürümü, parser/chunker sürümü ve tek corpus digest’i eklenmeli. Uyuşmazlıkta eval başlamamalı.

### P1.6 — Legacy embedding provenance fail-open

`0006_embedding_provenance.sql:39-48`, provenance damgası olmayan eski chunk’ları uyumluluk için geçiriyor. Yeni kayıtlar korunuyor; fakat eski corpus aynı index içinde sessizce farklı uzay taşıyabilir.

Release readiness şu koşullarda kırmızı olmalı:

- `embedding_space IS NULL` kayıt varsa;
- aynı aktif corpus içinde birden fazla embedding space varsa;
- corpus yeniden indekslenmeden model/provider değişmişse.

### P1.7 — CI tip kapısı tam kapı değil

Mypy çalışıyor fakat `continue-on-error: true`: `.github/workflows/ci.yml:64-66`. AI sözleşmeleri ve eval metadata’sı açısından type drift release’i durdurmuyor. Önce mevcut borç temizlenip gerçek required check yapılmalı.

## P2 — Olgunluk ve ölçek

- Gold set tek ders ve sınırlı dil/materyal dağılımında: `docs/test-report.md:631-632`. En az birkaç ders; Türkçe/İngilizce, OCR, tablo, kod, multi-turn, grading ve question-generation dilimleri eklenmeli.
- Prompt registry ve onay akışı eklenmeli: owner, amaç, risk sınıfı, eval sonucu, effective/rollback zamanı.
- Model/provider canary veya shadow trafiği, rollout yüzdesi ve otomatik rollback yok.
- Online drift izleme eklenmeli:
  - kapsam dışı ret dağılımı;
  - citation drop;
  - fallback/error artışı;
  - öğretmen şikâyet oranı;
  - token ve maliyet sapması;
  - retrieval score dağılımı.
- Güvenlik geri bildirimleri için ayrı incident/moderation yaşam döngüsü ve saklama politikası kurulmalı.
- Gerçek kullanıcı örnekleri eval’e alınacaksa de-identification, retention ve erişim denetimi zorunlu olmalı.

## Önerilen uygulama sırası

1. `runtime AI fingerprint` üret: Git SHA, deployment, provider/model, prompt hash, embedding space ve corpus digest.
2. Gold corpus manifestini hash’lerle dondur.
3. `ai-quality-gate` CI/release işini ekle.
4. Staging’de gerçek Groq/Gemini holdout’u çalıştır.
5. İki bağımsız insan ve eğitmen değerlendirmesini tamamla.
6. Append-only AI run/cost telemetry ekle.
7. Feedback kayıtlarını regression/eval döngüsüne bağla.
8. Görev bazlı model/provider/prompt/bütçe politikasını çıkar.
9. Canary, drift alarmı ve rollback runbook’u ekle.

Kısa sonuç: mühendislik seviyesi sıradan öğrenci projesinin üzerinde; özellikle guardrail, eval hijyeni ve RLS yaklaşımı güçlü. Fakat en önemli AI SDLC kuralı hâlâ eksik: **ölçülmemiş veya eski/fake-provider sonucu taşıyan bir model değişikliği release’i otomatik olarak durdurmuyor.**

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:798-812|note=[used historical eval caveats only as context and reverified all findings at target SHA]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019fe6f8-90c3-77f2-86f6-8e0aa53314a1
019fe6f8-93d1-71d2-acea-4d6e841e5fba
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>/root/skill_drafts (Peirce)</code> — 1.3 MiB — closed</summary>

- Session: `019fed93-c83b-7641-be31-444bf71574c7`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T21:28:33.084Z`
- Source log: `rollout-2026-08-11T00-28-33-019fed93-c83b-7641-be31-444bf71574c7.jsonl`

<pre>
Güncelleme tamamlandı. Sekiz sahipli dosya incelendi; yalnız şu üçünde metin değişti:

- [RELEASE_PROCESS.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/RELEASE_PROCESS.md)
- [ENGINEERING_EXCELLENCE.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/ENGINEERING_EXCELLENCE.md)
- [ADR-0001]($HOME/code/dou-ai-sdlc-excellence/docs/adr/0001-build-once-promote-by-digest.md)

Güncel gerçeklik:

- Manual release yalnız tam 40 karakterli SHA kabul ediyor.
- `v*` tag, event SHA’sına bağlanıyor.
- Candidate’ın `origin/main` atası olması fail-closed zorunlu.
- GHCR digest, SBOM, provenance ve attestation repo-configured; henüz workflow koşusu yok.
- Required check-run gate mevcut workflow’da henüz yok, bu nedenle `documented/pending`.
- Schema v1 optional `checks`, `migration`, `promotion`, `rollback` alanlarıyla doğru anlatılıyor.
- Staging, production, protected Environments ve deployment OIDC hâlâ dışarıda ve unconfigured.

Kanıt:

- 8 dosya, 33 yerel link, 18 tablo: 0 hata.
- Scoped whitespace/diff: 0 hata.
- Tam `git diff --check`: geçti.
- Eski mutable-ref/reviewed-SHA iddiası taraması: temiz.
- Başka dosyaya dokunulmadı.
- HEAD `2c178861a3e484af8643f999f210db040eb84e68`; upstream yok.
- Commit veya push yapılmadı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.6 MiB — closed</summary>

- Session: `019fed93-c90e-74e3-a710-b521a8d0d7de`
- Parent: `019fed93-c83b-7641-be31-444bf71574c7`
- Started: `2026-08-10T21:28:33.294Z`
- Source log: `rollout-2026-08-11T00-28-33-019fed93-c90e-74e3-a710-b521a8d0d7de.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>guardian</code> — 1.3 MiB — closed</summary>

- Session: `019feda5-65e7-7f13-a4bb-c8e5573643f5`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T21:47:47.560Z`
- Source log: `rollout-2026-08-11T00-47-47-019feda5-65e7-7f13-a4bb-c8e5573643f5.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/final_ai_review (Ramanujan)</code> — 407.0 MiB — closed</summary>

- Session: `019fedd3-363d-77f0-8dc6-ace817800cf9`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T22:37:50.013Z`
- Source log: `rollout-2026-08-11T01-37-50-019fedd3-363d-77f0-8dc6-ace817800cf9.jsonl`

<pre>
Uygulama tamamlandı; yalnız açık kullanıcı onayı gerektiren bootstrap finalizasyonu kaldı.

Tamamlananlar:

- `workflow_dispatch` kaldırıldı; yalnız PR exact head ve `main before → sha` kaldı.
- AI risk kapsamı genişletildi. Migration’lar güvenli tercih olarak genel R3 kaldı; bilinen AI migration yolları ayrıca R3 testli.
- Provider/model/prompt/tool/guardrail/retrieval/embedding/evaluator revision sözleşmesi eklendi.
- Corpus/eval digest, privacy, baseline/candidate metric, threshold, sample size ve exact command zorunlu.
- Deployment/flag/candidate kimliği ve immutable named approval kayıtları eklendi.
- Hash-bound `lineage_id + revision + supersedes` zinciri; fork, history rewrite, risk downgrade ve geçiş atlama reddi eklendi.
- Canary, rollback, closed-success ve closed-rollback semantiği fail-closed uygulandı.
- Dossier governance kaydı daima R3.
- `47/47` adversarial test geçti.
- Ruff, JSON parse ve `git diff --check` temiz.

Exact geçici candidate’ın tek kalan hataları:

- `example.json` içindeki 6 eski artifact hash’i.
- Yeni `004-validator-tests-v2.json` raporunun dossier’a bağlanmaması.

Güvenlik katmanı `example.json` güncellemesini append-only geçmiş rewrite olarak engelledi. Dosya aslında `base` ve remote’ta bulunmayan untracked bootstrap taslağı olsa da araç, bilgilendirilmiş açık kullanıcı onayı olmadan değişikliğe izin vermiyor. Commit/push yapılmadı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.6 MiB — closed</summary>

- Session: `019fedd3-36ab-7d20-b41a-fddd54b4817d`
- Parent: `019fedd3-363d-77f0-8dc6-ace817800cf9`
- Started: `2026-08-10T22:37:50.124Z`
- Source log: `rollout-2026-08-11T01-37-50-019fedd3-36ab-7d20-b41a-fddd54b4817d.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/final_release_review (Locke)</code> — 439.1 MiB — closed</summary>

- Session: `019fedd3-b227-7cf0-82b1-ab36c0bf2326`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T22:38:21.735Z`
- Source log: `rollout-2026-08-11T01-38-21-019fedd3-b227-7cf0-82b1-ab36c0bf2326.jsonl`

<pre>
Final audit düzeltmeleri tamamlandı; commit/push yapılmadı.

- Yapısal workflow policy: 14/14 test
- Release/evidence doğrulaması: 26/26 test
- Gerçek repo policy: PASS
- 5 workflow YAML + shell parse: PASS
- Ruff check/format: PASS
- `git diff --check`: PASS
- CI pgvector resmi digest’e sabitlendi.
- Release yalnız exact `main` HEAD üzerindeki `v*` tag push ve kimliği doğrulanan workflow/job’ları kabul ediyor.
- Quarantine → exact-digest gates → immutable admission evidence akışı kuruldu.
- Candidate/promotion kanıtları ayrıldı.
- Keepalive eksik secret durumunda artık kırmızı.
- External kalanlar: GitHub Environment reviewer/ruleset ayarları ve ilk gerçek tag release koşusu.

Ayrıntılı sözleşme ve dosya durumu `/root` ile docs sahibine iletildi.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:759-762|note=[DOU parallel integration context and requirement to remeasure current evidence]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.8 MiB — closed</summary>

- Session: `019fedd3-b2ad-79c2-99d1-29edea41edc0`
- Parent: `019fedd3-b227-7cf0-82b1-ab36c0bf2326`
- Started: `2026-08-10T22:38:21.869Z`
- Source log: `rollout-2026-08-11T01-38-21-019fedd3-b2ad-79c2-99d1-29edea41edc0.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/final_scope_audit (Poincare)</code> — 0.9 MiB — closed</summary>

- Session: `019fee02-31fa-72a0-9746-f60dce7e9daa`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T23:29:09.114Z`
- Source log: `rollout-2026-08-11T02-29-09-019fee02-31fa-72a0-9746-f60dce7e9daa.jsonl`

<pre>
Salt-okunur audit sonucu: **commit öncesi blocker var**. Dal `004-ai-sdlc-excellence`, `HEAD == origin/main == 2c178861`; tüm paket hâlâ uncommitted. Uygulama runtime’ı veya migration değiştirilmemiş.

## Blocker’lar

1. **Manuel AI workflow, başarısız required check’i yeşille örtebilir.**

   [`ai-quality.yml`]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/ai-quality.yml:8) serbest `base_sha` ile manuel çalıştırılabiliyor; `base_sha == HEAD_SHA` reddedilmiyor. Daha yeni boş-diff manuel başarı, [`verify_checks.py`]($HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:58) tarafından aynı isimli başarısız push check’inin yerine kabul edilir.

   Düzeltme: manuel workflow farklı check adı üretmeli veya kaldırılmalı. Release doğrulaması workflow path/ID, event türü, exact head SHA ve conclusion bağlamalı.

2. **Aynı isimli başka bir GitHub Actions job’u release check’ini taklit edebilir.**

   Kabul ölçütü yalnız ad, `app.slug == github-actions`, en yüksek ID ve success: [`verify_checks.py`]($HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:61). Workflow kimliği doğrulanmıyor.

   Testler: wrong workflow, `workflow_dispatch`, wrong head, duplicate-name ve “newer manual success after failed push” kırmızı olmalı.

3. **Action-pin policy, geçerli YAML flow mapping ile atlanabiliyor.**

   Regex yalnız block-style satırları yakalıyor: [`workflow_policy_check.py`]($HOME/code/dou-ai-sdlc-excellence/scripts/workflow_policy_check.py:10), [`workflow_policy_check.py`]($HOME/code/dou-ai-sdlc-excellence/scripts/workflow_policy_check.py:123). Şu ifade görünmeden geçebilir:

   ```yaml
   - { uses: actions/checkout@v4 }
   ```

   Regex yerine YAML ağacını dolaşan fail-closed parser kullanılmalı. Flow-map, inline-list, quoted key, anchor/alias ve nested local-action testleri eklenmeli.

4. **AI-sensitive path kapsamı bilinen yüksek etkili dosyaları kaçırıyor.**

   [`policy.json`]($HOME/code/dou-ai-sdlc-excellence/.ai/policy.json:107) aşağıdaki yüzeyleri kapsamıyor:

   - R3: `apps/api/app/core/text_tr.py` — grading, Socratic ve retrieval eşdeğerliği.
   - R3: `apps/api/app/modules/assessment/blueprint.py` — sınav yayın/readiness kapısı.
   - R3: `apps/api/app/modules/mastery/service.py` — öğrenci mastery kararı.
   - R2: `apps/api/app/core/rate_limit.py` — chat/question-generation admission.
   - R3: `apps/api/Dockerfile`.
   - R3: `apps/api/scripts/bake_embedding_model.py`.
   - İçerik-duyarlı R2/R3: `apps/api/pyproject.toml`, `apps/api/uv.lock`.
   - En az R2 değerlendirmesi: `docker-compose.yml`, `.env.example`.

   Buna karşılık bütün `supabase/migrations/**` blanket R3 yapılmış: [`policy.json`]($HOME/code/dou-ai-sdlc-excellence/.ai/policy.json:229). AI/index/exam migration’ları ayrıştırılmalı; ilgisiz migration’lar release/security sürecine yönlendirilmeli.

   Bir regression testi, yukarıdaki exact path’lerin beklenen risk sınıfını assert etmeli.

5. **Machine dossier, dokümanın zorunlu tuttuğu lineage’ı temsil edemiyor.**

   Doküman model/provider revision, flag, corpus digest, embedding space, eval-set ve eşik ister: [`AI_SDLC.md`]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/AI_SDLC.md:39). Fakat schema artifact için yalnız `path/state/sha256`, evidence için yalnız label/result/path/hash/SHA kabul ediyor: [`schema.json`]($HOME/code/dou-ai-sdlc-excellence/.ai/schema.json:127).

   Minimum machine alanları:

   - provider/model exact revision;
   - prompt/tool/guardrail/retrieval/embedding/evaluator sürümü;
   - corpus ve eval-set digest/privacy class;
   - baseline/candidate metric, önceden ilan edilmiş threshold, sample size;
   - exact candidate/deployment identity ve flag state;
   - gerçek approval actor, immutable review/environment ref, timestamp ve candidate SHA;
   - promotion target ile claim arasında semantik bağ.

6. **Append-only kuralı ile dossier yaşam döngüsü uyumsuz.**

   Mevcut dossier’i değiştirmek yasak: [`ai_sdlc_check.py`]($HOME/code/dou-ai-sdlc-excellence/scripts/ai_sdlc_check.py:931). Buna rağmen süreç aynı kaydı `draft → canary → rolled-back/closed` ilerletiyor: [`AI_SDLC.md`]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/AI_SDLC.md:114). Schema’da revision/supersedes zinciri yok.

   Ayrıca:

   - Dossier/evidence policy’de R3 olsa da yeni dossier-only kayıt kendi ilan ettiği riskle doğrulanıyor: [`ai_sdlc_check.py`]($HOME/code/dou-ai-sdlc-excellence/scripts/ai_sdlc_check.py:1088).
   - `rolled-back` gerçek rollback kanıtı olmadan geçebilir.
   - Production’a hiç çıkmadan rollback edilen kayıt `closed` olamaz; `closed` her durumda real-provider + production ister: [`ai_sdlc_check.py`]($HOME/code/dou-ai-sdlc-excellence/scripts/ai_sdlc_check.py:721).
   - Canary gerçek approval referansı istemiyor.
   - Örnek dossier gerçek isim yerine rol placeholder’ları taşıyor: [`example.json`]($HOME/code/dou-ai-sdlc-excellence/.ai/changes/example.json:60).

   Güvenli model: `.ai/changes/&lt;change-id&gt;/&lt;revision&gt;.json`; her revision `supersedes` path+hash, değişmez behavior candidate SHA, record SHA ve izinli state transition taşımalı. Fork, history rewrite, risk downgrade ve state-specific evidence fail-closed olmalı.

7. **Release evidence schema, kanıtsız `production: verified` kabul ediyor.**

   Kök required alanlar promotion/migration/rollback istemiyor: [`evidence.schema.json`]($HOME/code/dou-ai-sdlc-excellence/.release/evidence.schema.json:7), fakat `production: verified` geçerli: [`evidence.schema.json`]($HOME/code/dou-ai-sdlc-excellence/.release/evidence.schema.json:53). `promotion.source_digest` ile candidate image digest eşitliği de denetlenmiyor.

   Candidate ve promotion için ayrı state-specific schema/validator kullanılmalı. `verified` ancak same digest, approval, smoke, migration/backup ve rollback kanıtıyla geçmeli. SBOM/provenance için sabit `&quot;embedded&quot;` metni yerine doğrulanabilir digest/reference tutulmalı.

8. **Dokümantasyon tamamlanma durumu erken.**

   [`spec.md`]($HOME/code/dou-ai-sdlc-excellence/specs/004-ai-sdlc-excellence/spec.md:7) “Repository implementation complete” diyor; fakat candidate commit/CI yok ve görevler açık. “Local working-tree implementation candidate; audit/commit/CI pending” doğru ifade olur. [`tasks.md`]($HOME/code/dou-ai-sdlc-excellence/specs/004-ai-sdlc-excellence/tasks.md:51) içindeki `69/69`, `851/851`, `311/311` sonuçlarının bağlı retained kanıtı yok.

   Scorecard ayrıca kendi sözleşmesindeki reviewer, observation time, trigger, bypass/audit, current risk, due date ve expiry alanlarını taşımıyor: [`ENGINEERING_EXCELLENCE.md`]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/ENGINEERING_EXCELLENCE.md:29).

## İkinci kademe riskler

- Release workflow herhangi bir tarihsel `main` atasını privileged tag workflow’uyla çalıştırabiliyor; mevcut control-plane SHA veya protected release environment bağı düşünülmeli.
- İmaj exact-digest ürün kapılarından önce GHCR’a yazılıyor; başarısız digest için quarantine işareti gerekir.
- CI’daki `pgvector/pgvector:pg16` mutable service-image tag’i digest’e pinlenmeli.
- Keepalive secrets yokken hiç probe yapmadan yeşil olabilir; zaten production/SLO kanıtı sayılmamalı.

## Olumlu bulgular

- İncelenen dosyalarda gerçek secret, JWT, e-posta, öğrenci cevabı veya PII bulunmadı.
- Örnek dossier’daki yedi SHA-256 mevcut dosyalarla eşleşiyor.
- Production sınırı genel olarak dürüst: staging/production `not-configured`; yeni kontroller `configured`, `enforced/observed` değil.
- Mevcut 28 remote Action referansı 40 karakterli commit SHA’ya pinli.
- `pull_request_target` yok; PR workflow token’ları read-only.
- `.release/__pycache__` doğru biçimde ignore ediliyor.

## Commit gruplaması

Önerilen üçlü ayrım mantıklı, fakat blocker’lar kapandıktan sonra:

1. **AI SDLC:** `.ai/**`, `ai_sdlc_check.py`, testleri ve `ai-quality.yml` tek atomik commit. Dossier hash’leri bunları birbirine bağlıyor.
2. **CI/release/supply-chain:** CI/keepalive/security/release workflow’ları, `.release/**`, CODEOWNERS/Dependabot/PR template ve workflow-policy script/testleri. Review kolaylığı için bunun içinde action-parser, check-identity ve release-evidence düzeltmeleri ayrı commit olabilir.
3. **Docs/spec:** `.specify/feature.json`, `specs/**`, `docs/**`, ana README en son. Durumlar ve test sayıları exact commit kanıtına göre güncellenmeli.

Hiçbir dosya değiştirilmedi; test, commit veya push yapılmadı.
</pre>

</details>

<details>
<summary><code>/root/final_scope_audit/workflow_audit (Archimedes)</code> — 0.7 MiB — closed</summary>

- Session: `019fee02-b6a5-7c62-b99e-e68c140a663f`
- Parent: `019fee02-31fa-72a0-9746-f60dce7e9daa`
- Started: `2026-08-10T23:29:43.077Z`
- Source log: `rollout-2026-08-11T02-29-43-019fee02-b6a5-7c62-b99e-e68c140a663f.jsonl`

<pre>
Salt-okunur denetim sonucu: çalışma ağacı `HEAD 2c178861a3e484af8643f999f210db040eb84e68` üzerinde kirli; yeni policy/release dosyalarının çoğu henüz untracked.

Blocker bulgular:

- **[P1] Workflow action-pin kapısı YAML flow-mapping ile atlanabiliyor.** Regex yalnız satır başındaki block-style `uses:` anahtarını yakalıyor; `- { uses: actions/checkout@v4 }` eşleşmiyor. Bu nedenle “Workflow dependency policy” yeşil olup mutable action çalıştırabilir ve release’in zorunlu check’ini sahte biçimde karşılar. Kanıt: [$HOME/code/dou-ai-sdlc-excellence/scripts/workflow_policy_check.py:10]($HOME/code/dou-ai-sdlc-excellence/scripts/workflow_policy_check.py:10), [$HOME/code/dou-ai-sdlc-excellence/scripts/workflow_policy_check.py:123]($HOME/code/dou-ai-sdlc-excellence/scripts/workflow_policy_check.py:123), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/security.yml:23]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/security.yml:23), [$HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:25]($HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:25). YAML’ı güvenli/gerçek parser ile ayrıştırıp flow-map, quoted key, anchor/alias ve nested local-action mutasyon testleri eklenmeli.

- **[P1] Manuel AI-quality çalıştırması release check’ini yeniden yazabilir.** `workflow_dispatch` çağırana serbest `base_sha` veriyor; `HEAD_SHA` seçilen ref’ten geliyor. Workflow katmanı `base_sha == HEAD_SHA` veya incelenen lineage şartı koymuyor. Verifier ise aynı isimli `github-actions` check’leri arasından en yüksek ID’yi seçiyor; workflow path/ID/event/base bağlamını doğrulamıyor. Böylece daha yeni bir manuel boş-diff başarı, önceki push başarısızlığını örtebilir. Kanıt: [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/ai-quality.yml:8]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/ai-quality.yml:8), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/ai-quality.yml:28]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/ai-quality.yml:28), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/ai-quality.yml:48]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/ai-quality.yml:48), [$HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:58]($HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:58), [$HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:67]($HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:67). GitHub, write erişimli kullanıcıların workflow’u seçilen branch/tag üzerinde çalıştırabildiğini doğruluyor: [GitHub manual workflow docs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow). Manuel iş farklı check adına ayrılmalı; release yalnız beklenen workflow ID/path + `push` event + exact head SHA kombinasyonunu kabul etmeli.

- **[P1] Aynı isimli başka bir GitHub Actions işi zorunlu check’i taklit edebilir.** Kabul ölçütü yalnız `name`, `app.slug == github-actions`, en büyük ID, success ve boş olmayan URL. Workflow kimliği/event’i doğrulanmıyor. Kanıt: [$HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:61]($HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:61), [$HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:67]($HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:67), [$HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:79]($HOME/code/dou-ai-sdlc-excellence/.release/verify_checks.py:79), [$HOME/code/dou-ai-sdlc-excellence/.release/test_verify_checks.py:76]($HOME/code/dou-ai-sdlc-excellence/.release/test_verify_checks.py:76). Beklenen workflow run’ları ayrıca sorgulanıp path/ID, event, head SHA ve conclusion ile bağlanmalı; beklenmeyen duplicate-name fail-closed olmalı.

- **[P1] Release şeması kanıtsız `production: verified` kabul ediyor.** Kök `required` listesi migration/promotion/rollback istemiyor; buna rağmen staging/production `verified` enum’da geçerli. README ise aynı digest staging kanıtı, approval, migration/backup/smoke/rollback zorunlu diyor. Kanıt: [$HOME/code/dou-ai-sdlc-excellence/.release/evidence.schema.json:7]($HOME/code/dou-ai-sdlc-excellence/.release/evidence.schema.json:7), [$HOME/code/dou-ai-sdlc-excellence/.release/evidence.schema.json:53]($HOME/code/dou-ai-sdlc-excellence/.release/evidence.schema.json:53), [$HOME/code/dou-ai-sdlc-excellence/.release/evidence.schema.json:94]($HOME/code/dou-ai-sdlc-excellence/.release/evidence.schema.json:94), [$HOME/code/dou-ai-sdlc-excellence/.release/README.md:58]($HOME/code/dou-ai-sdlc-excellence/.release/README.md:58). Aşama-bazlı ayrı schema veya semantik validator ile `verified =&gt; promotion + matching digest + approved + smoke passed + migration/backup + rollback evidence` zorunlu olmalı.

- **[P1/external-control blocker] Privileged tag workflow herhangi bir `v*` etiketi ve main’in herhangi bir tarihsel atası için çalışıyor.** `SOURCE_SHA == origin/main HEAD` şartı yok; yalnız ancestor kontrolü var. Candidate job `packages: write`, `id-token: write`, `attestations: write` alıyor ve `environment` approval kullanmıyor. GitHub workflow dosyasını event’in commit/ref’inden bulur; dolayısıyla ileride düzeltilmiş kontrolün eski tarihsel sürümü yeniden tetiklenebilir. Kanıt: [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:3]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:3), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:51]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:51), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:62]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:62), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:97]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:97). GitHub davranışı: [workflow files come from the event SHA/ref](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows). Current protected control-plane SHA/release branch şartı, protected tag ruleset ve approval’lı `release-candidate` environment gerekir.

- **[P1/external-control blocker] Main üyeliği PR review/dependency review kanıtı değildir.** CODEOWNERS kendi başına enforce olmaz; dosya bunu açıkça kabul ediyor. Release yalnız main ancestry + check adlarını inceliyor; `Dependency review` bilinçli olarak listede yok ve “merge öncesi geçmiştir” varsayılıyor. Doğrudan/bypass main push bu varsayımı bozar. Kanıt: [$HOME/code/dou-ai-sdlc-excellence/.github/CODEOWNERS:1]($HOME/code/dou-ai-sdlc-excellence/.github/CODEOWNERS:1), [$HOME/code/dou-ai-sdlc-excellence/.release/README.md:40]($HOME/code/dou-ai-sdlc-excellence/.release/README.md:40), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:62]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:62). Active ruleset; required PR, CODEOWNER review, last-push approval, no bypass ve required checks canlı doğrulanmalı. GitHub da CODEOWNERS zorunluluğunun branch protection/ruleset gerektirdiğini belirtiyor: [GitHub CODEOWNERS docs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners).

Önemli fakat ikinci kademe:

- **[P2] İmaj ürün kapılarından önce GHCR’a yazılıyor.** Offline embedding/RSS başarısız olsa bile `sha-&lt;commit&gt;` etiketi registry’de kalır. Kanıt: [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:134]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:134), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:149]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:149), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:188]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:188). Quarantine namespace/tag veya kapı-sonrası promotion gerekir.

- **[P2] CI servis container’ı mutable tag kullanıyor:** [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/ci.yml:26]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/ci.yml:26), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/ci.yml:253]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/ci.yml:253). Digest pinlenmeli ve kontrollü update mekanizması eklenmeli.

- **[P2] Keepalive yeşil sonucu hiç probe yapılmadığı anlamına gelebilir.** İki secret da eksikse adımlar başarıyla çıkar; bu workflow uptime/production kanıtı olarak kullanılamaz. Kanıt: [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/keepalive.yml:15]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/keepalive.yml:15), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/keepalive.yml:44]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/keepalive.yml:44), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/keepalive.yml:57]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/keepalive.yml:57).

Non-blocker/güçlü taraflar:

- Mevcut 28 external `uses:` referansının tamamı 40 haneli commit SHA’ya pinli.
- PR workflow’larında `pull_request_target` yok; CI/AI/security varsayılan token’ları read-only: [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/ci.yml:12]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/ci.yml:12), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/ai-quality.yml:15]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/ai-quality.yml:15), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/security.yml:13]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/security.yml:13). Keepalive `permissions: {}`: [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/keepalive.yml:29]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/keepalive.yml:29).
- Candidate artifact şu an staging/production’u dürüstçe `not-configured` yazıyor ve özet “deployment iddiası değildir” diyor: [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:226]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:226), [$HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:278]($HOME/code/dou-ai-sdlc-excellence/.github/workflows/release-candidate.yml:278).
- `.release/__pycache__` kaynak sayılmadı ve doğru biçimde git-ignore ediliyor: [$HOME/code/dou-ai-sdlc-excellence/.gitignore:9]($HOME/code/dou-ai-sdlc-excellence/.gitignore:9).

Önerilen commit grupları:

1. `fix(workflow-policy): parse YAML structurally and close flow-map bypass`
2. `fix(release-gates): bind checks to workflow identity/event and isolate manual AI runs`
3. `fix(release-evidence): enforce promotion/migration/rollback semantics`
4. `fix(release-admission): trusted current control plane, protected environment, quarantine publish`
5. `chore(ci-supply-chain): pin service images by digest`

Branch/tag ruleset, independent reviewer/CODEOWNER ekibi, environment reviewer ve secret-scanning ayarları commit dışı ayrı bir GitHub yönetim değişikliği + ekran/API kanıtı olarak izlenmeli. Test çalıştırılmadı; audit salt okunurdu.
</pre>

</details>

<details>
<summary><code>/root/final_scope_audit/docs_contract_audit (Confucius)</code> — 0.8 MiB — closed</summary>

- Session: `019fee02-c28b-7262-8410-e30a5b78f38a`
- Parent: `019fee02-31fa-72a0-9746-f60dce7e9daa`
- Started: `2026-08-10T23:29:46.124Z`
- Source log: `rollout-2026-08-11T02-29-46-019fee02-c28b-7262-8410-e30a5b78f38a.jsonl`

<pre>
Read-only audit result: **5 blockers** before commit.

### Blockers

1. **Machine dossier cannot represent the lineage required by its own docs.**
   [AI_SDLC.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/AI_SDLC.md:39) requires artifact type/version/flag plus corpus digest, embedding space, eval-set version and privacy class; [data-model.md]($HOME/code/dou-ai-sdlc-excellence/specs/004-ai-sdlc-excellence/data-model.md:16) repeats kind/version requirements. But [schema.json]($HOME/code/dou-ai-sdlc-excellence/.ai/schema.json:127) permits only `path/state/sha256`, and top-level extra fields are forbidden at [schema.json]($HOME/code/dou-ai-sdlc-excellence/.ai/schema.json:6). Provider/model revision, prompt kind, corpus digest and embedding identity therefore cannot be explicit schema-valid fields.

2. **The “100% of AI-sensitive paths” claim is false for known shared/high-impact files.**
   [README.md]($HOME/code/dou-ai-sdlc-excellence/.ai/README.md:9) claims prompts, retrieval, grading and exam behaviour are classified, while [spec.md]($HOME/code/dou-ai-sdlc-excellence/specs/004-ai-sdlc-excellence/spec.md:143) claims 100% coverage. Yet the individual path list in [policy.json]($HOME/code/dou-ai-sdlc-excellence/.ai/policy.json:107) omits:

   - `apps/api/app/core/text_tr.py`, which explicitly drives Socratic, question generation, grading and retrieval behavior at [text_tr.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/core/text_tr.py:6) and changes grading equivalence at [text_tr.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/core/text_tr.py:99).
   - `apps/api/app/modules/assessment/blueprint.py`, an exam publication/readiness gate at [blueprint.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/modules/assessment/blueprint.py:155).
   - `apps/api/app/core/rate_limit.py`, which governs shared chat/question-generation admission and concurrency at [rate_limit.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/core/rate_limit.py:1).

   Conversely, all migrations are blanket R3 at [policy.json]($HOME/code/dou-ai-sdlc-excellence/.ai/policy.json:229), pulling unrelated migrations into an AI dossier. The policy needs explicit coverage tests and narrower/rationalized scope.

3. **Lifecycle, approval and promotion contracts contradict one another.**
   [AI_SDLC.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/AI_SDLC.md:117) allows `rolled-back -&gt; closed`, but the checker requires both real-provider and production evidence for every `closed` dossier at [ai_sdlc_check.py]($HOME/code/dou-ai-sdlc-excellence/scripts/ai_sdlc_check.py:721). A change rolled back before production can never close.
   Also, `status`, `promotion.claim`, and `promotion.target` are independent enums at [schema.json]($HOME/code/dou-ai-sdlc-excellence/.ai/schema.json:78) and [schema.json]($HOME/code/dou-ai-sdlc-excellence/.ai/schema.json:358), allowing contradictions such as `development + production` or `production-ready + none`. Canary validation checks evidence but no actual approval reference at [ai_sdlc_check.py]($HOME/code/dou-ai-sdlc-excellence/scripts/ai_sdlc_check.py:713), despite the independent-approval contract at [AI_SDLC.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/AI_SDLC.md:79). The example’s “owners” are generic placeholders, not named accountable people, at [example.json]($HOME/code/dou-ai-sdlc-excellence/.ai/changes/example.json:60).

4. **The engineering scorecard does not meet its own control-record contract.**
   The table at [ENGINEERING_EXCELLENCE.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/ENGINEERING_EXCELLENCE.md:29) omits reviewer, observation timestamp, trigger, failure policy, bypass/audit path, current risk, due date and exception expiry. The same document requires those fields at [ENGINEERING_EXCELLENCE.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/ENGINEERING_EXCELLENCE.md:50) and says unresolved risk cannot be blank at [ENGINEERING_EXCELLENCE.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/ENGINEERING_EXCELLENCE.md:121). There is not even an unresolved-risk column.

5. **Completion wording is ahead of the observable repository state.**
   [spec.md]($HOME/code/dou-ai-sdlc-excellence/specs/004-ai-sdlc-excellence/spec.md:7) says “Repository implementation complete,” while the scorecard admits there is no candidate commit or CI run at [ENGINEERING_EXCELLENCE.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/ENGINEERING_EXCELLENCE.md:22), and [tasks.md]($HOME/code/dou-ai-sdlc-excellence/specs/004-ai-sdlc-excellence/tasks.md:28) plus [tasks.md]($HOME/code/dou-ai-sdlc-excellence/specs/004-ai-sdlc-excellence/tasks.md:49) remain open. Git confirms `HEAD == origin/main == 2c178861`; all package work is uncommitted. “Local working-tree implementation complete” would be accurate. The 69/69, 851/851 and 311/311 claims at [tasks.md]($HOME/code/dou-ai-sdlc-excellence/specs/004-ai-sdlc-excellence/tasks.md:51) also lack linked retained evidence; the sole committed-style evidence file proves only 36 validator tests at [004-validator-tests.json]($HOME/code/dou-ai-sdlc-excellence/.ai/evidence/004-validator-tests.json:3).

### Non-blockers / positive findings

- No actual secret, token, email address, JWT, student response, or identifiable student record was found in the audited files. The current evidence is explicitly synthetic at [004-validator-tests.json]($HOME/code/dou-ai-sdlc-excellence/.ai/evidence/004-validator-tests.json:4).
- All seven SHA-256 values in the example dossier match the current files exactly.
- Production boundaries are generally honest: [AI_SDLC.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/AI_SDLC.md:8), [RELEASE_PROCESS.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/RELEASE_PROCESS.md:7), [SLO.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/SLO.md:3), and [ENGINEERING_EXCELLENCE.md]($HOME/code/dou-ai-sdlc-excellence/docs/engineering/ENGINEERING_EXCELLENCE.md:22) consistently separate configured files from enforced/observed/production state.
- Privacy is currently clean, but enforcement is self-attested: [schema.json]($HOME/code/dou-ai-sdlc-excellence/.ai/schema.json:336) has only a boolean plus prose, while evidence reports are not constrained against arbitrary raw payload fields.
- ADR status vocabulary needs a small fix: [ADR README]($HOME/code/dou-ai-sdlc-excellence/docs/adr/README.md:22) defines no `observed` ADR state, but [ADR-0001]($HOME/code/dou-ai-sdlc-excellence/docs/adr/0001-build-once-promote-by-digest.md:150) says the ADR later becomes `observed`. Treat observation as scorecard state, not ADR status.
- `.specify/feature.json` correctly points to `specs/004-ai-sdlc-excellence`.

### Commit grouping

Do not make one monolithic commit.

1. Spec foundation: `.specify/feature.json` + `specs/004-ai-sdlc-excellence/**`.
2. AI gate atomically: `.ai/**`, `ai_sdlc_check.py`, its tests, and `ai-quality.yml` together—the example dossier hashes bind these files.
3. PR/core-CI/supply-chain controls separately.
4. ADR + release workflow/schema/validators as one reviewable delivery decision slice.
5. Engineering operating docs and README last, after statuses/test evidence are corrected to the actual committed candidate.

No files were edited, committed, or pushed.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.9 MiB — closed</summary>

- Session: `019fee0b-3086-7b03-a704-94bf51a04f06`
- Parent: `019fedd3-363d-77f0-8dc6-ace817800cf9`
- Started: `2026-08-10T23:38:58.566Z`
- Source log: `rollout-2026-08-11T02-38-58-019fee0b-3086-7b03-a704-94bf51a04f06.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>guardian</code> — 0.6 MiB — closed</summary>

- Session: `019fee0b-a3ae-7721-9682-62b38bd534b2`
- Parent: `019fedd3-b227-7cf0-82b1-ab36c0bf2326`
- Started: `2026-08-10T23:39:28.047Z`
- Source log: `rollout-2026-08-11T02-39-28-019fee0b-a3ae-7721-9682-62b38bd534b2.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/docs_evidence_reconcile (Kant)</code> — 438.4 MiB — closed</summary>

- Session: `019fee0c-420e-79d0-ae9c-1bfed2b41876`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-10T23:40:08.590Z`
- Source log: `rollout-2026-08-11T02-40-08-019fee0c-420e-79d0-ae9c-1bfed2b41876.jsonl`

<pre>
Dokümantasyon ve yerel kanıt uzlaştırması tamamlandı.

- AI SDLC yaşam döngüsü, immutable revision zinciri, canary/rollback/kapanış kuralları gerçek validator ile eşlendi.
- Release candidate–promotion ayrımı ve exact-digest sözleşmesi güncellendi.
- Scorecard kayıt sözleşmesi tamamlandı; durumlar dürüstçe yalnız `documented/configured`.
- ADR durum dili düzeltildi.
- Yerel kanıt dosyası eklendi.
- T302, T505 ve T601–T606 açık bırakıldı.
- Bootstrap dossier hash’i immutable candidate oluşana kadar açık blocker.

Doğrulama:

- AI: 47/47
- Workflow policy: 14/14
- Release: 26/26
- Toplam governance: 87/87
- JSON/YAML parse, docs-check, Ruff/format, durum tutarlılığı ve diff-check: geçti
- Commit/push yapılmadı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 1.0 MiB — closed</summary>

- Session: `019fee0c-429f-73e2-b9a1-85b43e45679a`
- Parent: `019fee0c-420e-79d0-ae9c-1bfed2b41876`
- Started: `2026-08-10T23:40:08.735Z`
- Source log: `rollout-2026-08-11T02-40-08-019fee0c-429f-73e2-b9a1-85b43e45679a.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/icloud_inventory (Rawls)</code> — 127.0 MiB — closed</summary>

- Session: `019fee4f-2e2f-7bd3-b80f-1c93d59a2a55`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T00:53:14.416Z`
- Source log: `rollout-2026-08-11T03-53-14-019fee4f-2e2f-7bd3-b80f-1c93d59a2a55.jsonl`

<pre>
Envanter tamamlandı ve `/root` ajanına iletildi.

- `ba` altında 623 dosyanın 622’si iCloud `compressed,dataless` durumda.
- `outputs` klasöründeki 6 dosyanın tamamı çevrimdışı placeholder.
- Yol haritasının iCloud dışı aynı boyutlu kopyası bulundu.
- `dou-role-admin-panels` içindeki commitli ürün kodu güncel `origin/main` geçmişinde korunuyor.
- Tam eski içeriği Git’te bulunmayan 35 çalışma-kopyası varyantı tespit edildi; bunların güncel/final karşılıkları `main` içinde mevcut.
- Hiçbir dosya değiştirilmedi, silinmedi veya kopyalanmadı.
</pre>

</details>

<details>
<summary><code>/root/git_recovery_map (Averroes)</code> — 127.1 MiB — closed</summary>

- Session: `019fee4f-848f-78e0-bab9-61aade3e889d`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T00:53:36.527Z`
- Source log: `rollout-2026-08-11T03-53-36-019fee4f-848f-78e0-bab9-61aade3e889d.jsonl`

<pre>
Salt-okunur Git kurtarma haritası tamamlandı. Hiçbir dosya, ref, branch veya worktree değiştirilmedi.

## Ana kaynak

- Ortak Git deposu: `$HOME/code/DOU-Synapse/.git`
- Güncel remote-tracking ürün ağacı: `origin/main@2c178861a3e484af8643f999f210db040eb84e68`
- Yerel `main@ae93417c5c0f2af57fd57a58b6782f0ffd0609f7`, `origin/main`in 76 commit gerisinde. Kurtarma kaynağı olarak kullanılmamalı.
- `$HOME/code/DOU-Synapse` temiz fakat `feat/chat-socratic@439efee5` üzerinde ve upstream’i silinmiş. Burası ortak Git nesne deposunu taşıdığı için silinmemeli.
- `git fsck --connectivity-only` temiz; gerekli bağlı commit/tree/blob nesneleri mevcut.
- `git stash list` boş.
- Ağ erişimli `fetch` yapmadım; sonuçlar makinedeki mevcut remote-tracking reflerine dayanıyor.

## Eski iCloud worktree

Yol:

`$HOME/Documents/Codex/2026-08-09/ba/dou-role-admin-panels`

Durum:

- Branch: `feature/role-admin-panels`
- HEAD: `d25ce0548e362bd6b12a2fd403f30b85e7686012`
- Branch reflog yalnız branch oluşturma ve `reset: moving to HEAD` içeriyor; bu dalda hiç commit üretilmemiş.
- 455 index kaydı var.
- `diff --cached HEAD` boş.
- `d25ce054` ağacı da tam 455 dosya içeriyor.
- Tüm worktree dosyaları `dataless`; normal status/diff işlemi içerik indirmesine takılıyor.

Epistemik ayrım:

- `d25ce054` commitindeki 455 dosya Git’ten birebir yeniden üretilebilir.
- Bunun mevcut iCloud placeholder içerikleriyle birebir aynı olduğu kanıtlanamadı; dosyalar okunamadığı için hash alınamadı.

## Kanıtlı iCloud taslak farkları

Tracked dosyaların mantıksal boyutu Git blob boyutuyla karşılaştırıldı:

- 449 tracked dosya aynı boyutta; içerik eşitliği yine kanıtlanmış değil.
- Aşağıdaki 6 tracked dosyada kanıtlı unstaged değişiklik vardı:

```text
apps/api/app/api/deps.py
apps/api/app/main.py
apps/api/tests/conftest.py
apps/web/components/app-shell.tsx
apps/web/lib/api.ts
supabase/seed_demo.sql
```

Ayrıca 113 index-dışı dosya bulundu:

- 83 tanesi yeniden üretilebilir cache/pyc dosyası.
- 30 tanesi gerçek portal kaynak/tasarım dosyası:

```text
apps/api/app/api/admin.py
apps/api/app/api/dashboard.py
apps/api/app/api/profile.py
apps/api/app/schemas/admin.py
apps/api/app/schemas/dashboard.py
apps/api/app/schemas/profile.py
apps/api/tests/test_portal.py
apps/web/app/admin/layout.tsx
apps/web/app/admin/page.tsx
apps/web/app/dashboard/layout.tsx
apps/web/app/dashboard/page.tsx
apps/web/app/profile/layout.tsx
apps/web/app/profile/page.tsx
apps/web/components/portal/admin-data-table.tsx
apps/web/components/portal/dashboard-course-card.tsx
apps/web/components/portal/portal-metrics.tsx
apps/web/components/portal/portal-profile-context.tsx
apps/web/lib/admin.test.ts
apps/web/lib/admin.ts
apps/web/lib/dashboard.test.ts
apps/web/lib/dashboard.ts
apps/web/lib/profile.test.ts
apps/web/lib/profile.ts
specs/003-product-portal/contracts/api.md
specs/003-product-portal/data-model.md
specs/003-product-portal/plan.md
specs/003-product-portal/quickstart.md
specs/003-product-portal/research.md
specs/003-product-portal/spec.md
supabase/migrations/0014_platform_admin_console.sql
```

Toplam 36 eski taslak yolun Git nesne taraması:

- Tüm 1.546 Git blobu tarandı.
- 35 dosya için güvenilir eski blob adayı yok.
- Yalnız `apps/api/app/schemas/dashboard.py` placeholder boyutu, aynı yolun `fa659d17...` blob boyutuyla eşleşiyor; dosya okunamadığı için birebir içerik kanıtı değildir.
- Bu nedenle eski ilk taslakların byte-for-byte kurtarılması Git’ten mümkün görünmüyor; iCloud indirmesi veya sohbet/attachment kopyası gerekir.

## İşlevsel hal kaybolmamış

Ancestry zinciri:

```text
d25ce0548e362bd6b12a2fd403f30b85e7686012
  → 2c8ded83791df0dbf4aa0c057078e27f58c36671
  → 3532d49ad939746aad8789d695249f90c1c373c7
  → 2c178861a3e484af8643f999f210db040eb84e68
```

Her ok gerçek ancestor ilişkisiyle doğrulandı.

Portal dosyalarının daha gelişmiş, commitlenmiş sürümleri:

- Backend, şemalar, test ve `0014`: `fa659d17f59cf1e6adc2cb25449027a8d2fd3a44`
- Frontend portal/panel/profil: `77cf35e0723fdd25ffe56d90ce5176056b275e71`
- Speckit portal belgeleri: `81d3c0ab47b246d66bd99fdc27b8df13b4081d62`
- Tarayıcı ve RLS sentinelleri: `9c2fe23130b97570b42d0a56e57b9cfe88b343a9`
- Tam portal dalı: `2c8ded83791df0dbf4aa0c057078e27f58c36671`
- Güncel birleşmiş ürün: `origin/main@2c178861a3e484af8643f999f210db040eb84e68`

Yani eski ilk draftların özgün byte’ları belirsiz olsa da ürün işlevleri kaybolmadı ve `origin/main`den güvenle yeniden kurulabilir.

## Korunması gereken güncel çalışma

`$HOME/code/dou-ai-sdlc-excellence`

- Branch: `004-ai-sdlc-excellence`
- HEAD: `2c178861a3e484af8643f999f210db040eb84e68`
- Dirty ve henüz commitlenmemiş AI SDLC/engineering-excellence çalışması içeriyor.
- Kurtarma sırasında üzerine yazılmamalı; ayrı olarak ham çalışma ağacıyla yedeklenmeli.

Güvenli kurtarma paketinde üç ayrı katman tutulmalı:

1. `d25ce054` — eski worktree’nin kesin Git snapshot’ı.
2. `2c8ded837` — tamamlanmış portal checkpoint’i.
3. `2c178861` — güncel birleşmiş ürün.
4. Ek olarak dirty `004-ai-sdlc-excellence` çalışma ağacı, Git snapshotından ayrı korunmalı.
</pre>

</details>

<details>
<summary><code>/root/artifact_recovery_map (Kuhn)</code> — 127.1 MiB — closed</summary>

- Session: `019fee50-1757-7d10-a6d7-980574dd2679`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T00:54:14.104Z`
- Source log: `rollout-2026-08-11T03-54-14-019fee50-1757-7d10-a6d7-980574dd2679.jsonl`

<pre>
Salt-okunur kurtarma haritası tamamlandı.

- iCloud’daki 6 Markdown dosyasının tamamı `compressed,dataless`; kısa kontrollü okumada 6/6 zaman aşımına uğradı.
- Altı dosyanın özgün içerikleri Codex oturum kaydındaki oluşturma yamalarından eksiksiz çıkarılabiliyor.
- Beş Claude görev dosyasının yeniden oluşturulan boyutları iCloud metadata boyutlarıyla birebir eşleşiyor.
- Yol haritasının 40.084 baytlık tam sürümü `$HOME/code/dou-claude-tasks-v2/DOU-Synapse-End-to-End-Production-Yol-Haritasi.md` ile byte-byte aynı; SHA-256: `62e65025d21bdafa1ed30a7118cdc1084ac53c96cb99acd6c9b08b3beff2cd5b`.
- Sonradan iyileştirilen tüm sohbet görev belgeleri `$HOME/code/dou-claude-tasks-v2/` altında erişilebilir; özgünlerle karıştırılmadan ayrıca korunmalı.
- İki toplantı notu attachment’ı byte-byte aynı; diğer iki DOU attachment’ının da tam yol ve hashleri ana ajana iletildi.
- Hiçbir dosya değiştirilmedi, kopyalanmadı veya silinmedi.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.5 MiB — closed</summary>

- Session: `019fee57-ec87-7d80-b152-f28cf762533f`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T01:02:47.432Z`
- Source log: `rollout-2026-08-11T04-02-47-019fee57-ec87-7d80-b152-f28cf762533f.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/sdlc_status_audit (Volta)</code> — 469.5 MiB — closed</summary>

- Session: `019fee70-a3a4-71d0-a3c6-4b568dfe12c8`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T01:29:47.173Z`
- Source log: `rollout-2026-08-11T04-29-47-019fee70-a3a4-71d0-a3c6-4b568dfe12c8.jsonl`

<pre>
Salt-okunur denetim sonucu:

## Net hüküm

| Alan | Gerçek durum |
|---|---|
| CI | **Var ve gözlenmiş.** PR #4’ün CI run `31434256609` / run #71’i başarıyla tamamlanmış. API, Web, doküman doğruluğu, container/offline embedding ve gerçek API+Playwright E2E olmak üzere 5 iş yeşil. |
| CD | **Yok.** `origin/main` yalnız `ci.yml` ve `keepalive.yml` içeriyor. İmaj kuruluyor ama yayınlanmıyor/dağıtılmıyor; keepalive yalnız uyanıklık kontrolü. Staging/production promotion veya rollback workflow’u yok. |
| AI SDLC | **Üründe kısmi, yönetişim olarak henüz main’de yok.** Main’de gold set, calibration/holdout, injection, faithfulness, provider/model provenance ve sahte/gerçek sağlayıcı ayrımı var. Ancak change dossier, R1/R2/R3 risk, bağımsız onay, canary, kill switch, telemetry ve rollback zinciri main’de bulunmuyor. |
| Engineering excellence | **Kısmen güçlü.** Test, RLS mutasyonları, E2E, docs truth ve imaj kanıtı var. Fakat CODEOWNERS, Dependabot, CodeQL, immutable action pinleri, SBOM/provenance, ADR/SLO/incident/DORA sistemi main’de yok. |
| 004 çalışması | **Yazılmış ama teslim edilmemiş.** `004-ai-sdlc-excellence` HEAD’i tam `origin/main` SHA’sı `2c178861`; üstünde commit yok, upstream yok. 4 değiştirilmiş + 39 untracked dosya var. Dolayısıyla AI SDLC/engineering-excellence paketi GitHub’da ve main’de değil. |

## Dizin ve dal kanıtı

- `$HOME/code/DOU-Synapse`
  - Dal: `feat/chat-socratic`
  - HEAD: `439efee`
  - Temiz fakat `origin/main`in **206 commit gerisinde**; upstream dalı silinmiş.
  - Yetkili güncel checkout olarak kullanılmamalı.

- `$HOME/code/dou-ai-sdlc-excellence`
  - Dal: `004-ai-sdlc-excellence`
  - HEAD: `2c178861`, yani güncel `origin/main` ile aynı taban.
  - 4 tracked değişiklik ve 39 yeni dosya, toplam yaklaşık 367 KB.
  - Hiçbiri commit/push edilmiş değil.

- `$HOME/Documents/ChatGPT/DOU-Synapse`
  - Git deposu değil ve tamamen boş.

## 004 paketinde hazır olanlar

Yerelde hazırlanmış:

- AI change dossier şeması/politikası ve fail-closed validator
- AI quality workflow
- Gold-set bütünlük kapısı
- CODEOWNERS ve PR şablonu
- Dependabot
- Dependency Review ve iki dilli CodeQL
- Immutable action/image pinleme politikası
- Tag tabanlı release-candidate workflow
- GHCR karantina imajı, SBOM, provenance ve attestation tasarımı
- ADR, SLO, incident, release ve engineering excellence belgeleri
- Yerel kanıt: 87 yönetişim testi geçmiş

Ama kanıt belgesi açıkça bunun **commitlenmemiş çalışma ağacı** olduğunu ve GitHub/production kanıtı sayılamayacağını söylüyor.

## Açık sekiz görev

- T302: protected staging/production ve aynı-digest promotion
- T505: commit/push/CI
- T601: `main` ruleset/branch protection
- T602: protected environments ve bağımsız production onayı
- T603: GHCR + OIDC/cloud yetkileri
- T604: gerçek staging, Supabase Auth/Storage, gerçek LLM, smoke ve alarm
- T605: backup-restore/rollback tatbikatı
- T606: staging digest’ini production’a terfi ve SLO telemetry doğrulaması

`gh` oturumu açık olmadığı için canlı ruleset/environment ayarları ayrıca okunamadı; bu nedenle bunlar “yok” değil, güvenli sınıflamayla **doğrulanmamış**. Ancak repository tarafında gerçek CD kesinlikle bulunmuyor.

Önerilen sonraki hareket: `004-ai-sdlc-excellence` çalışma ağacını önce küçük ve izlenebilir commitlere ayırmak, yerel kapıları tekrar çalıştırmak, dalı push edip PR açmak. Sonra GitHub dış ayarları ve gerçek staging/CD ayrı aşamada kurulmalı.
</pre>

</details>

<details>
<summary><code>/root/agent_chat_audit (Hubble)</code> — 565.8 MiB — closed</summary>

- Session: `019fee71-095d-7eb2-bb86-51ecc397e638`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T01:30:13.213Z`
- Source log: `rollout-2026-08-11T04-30-13-019fee71-095d-7eb2-bb86-51ecc397e638.jsonl`

<pre>
Frontend 005 şeridi hazır; commit/push yapılmadı ve yalnız `apps/web/**` değiştirildi.

Ana teslimler:

- Ders sayfaları ve dashboard kartlarından açılan ders-kapsamlı asistan çekmecesi
- Sunucudan doğrulanan “Ders Koçu” / “Eğitmen Asistanı” kimliği
- `allowed_modes`, `hint_limit` ve sınav kilidi desteği
- Eski oturumlarda rol/persona uyuşmazlığında fail-closed davranış
- Politika/persona değişiminde konuşma ve uçuş isteklerinin güvenli sıfırlanması
- Mobil, dark mode, klavye ve native dialog erişilebilirliği
- Rol seçici veya otonom yazma aracı yok
- Eğitmen Sokratik taslak önerisi doğru biçimde QA başlangıcına yönlendirildi

Doğrulama:

- Bun: **322/322 test**
- TypeScript: temiz
- Next.js production build: temiz
- `git diff --check`: temiz
- Canlı tarayıcı/E2E: backend şeridi hâlâ paralel değiştiği için koşulmadı; entegrasyon sonrası seri E2E gerekli

Önemli dosyalar:

- [course-assistant.tsx]($HOME/code/dou-ai-sdlc-excellence/apps/web/components/course-assistant/course-assistant.tsx)
- [chat/page.tsx](&lt;$HOME/code/dou-ai-sdlc-excellence/apps/web/app/courses/[courseId]/chat/page.tsx&gt;)
- [course-assistant.ts]($HOME/code/dou-ai-sdlc-excellence/apps/web/lib/course-assistant.ts)
- [course-assistant.test.ts]($HOME/code/dou-ai-sdlc-excellence/apps/web/lib/course-assistant.test.ts)
- [types.ts]($HOME/code/dou-ai-sdlc-excellence/apps/web/lib/types.ts)
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.8 MiB — closed</summary>

- Session: `019fee71-0a00-7da1-b5e0-60767c3eac7b`
- Parent: `019fee71-095d-7eb2-bb86-51ecc397e638`
- Started: `2026-08-11T01:30:13.376Z`
- Source log: `rollout-2026-08-11T04-30-13-019fee71-0a00-7da1-b5e0-60767c3eac7b.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/agent_feature_spec (Harvey)</code> — 501.4 MiB — closed</summary>

- Session: `019fee71-8b4c-7e03-a9c6-ce5e162abbeb`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T01:30:46.476Z`
- Source log: `rollout-2026-08-11T04-30-46-019fee71-8b4c-7e03-a9c6-ce5e162abbeb.jsonl`

<pre>
Salt-okunur inceleme tamamlandı; repo değişmedi.

Net karar:

- Yeni Speckit özelliği: `005-role-aware-course-agent`
- Migration: `0015_role_aware_course_agent.sql`
- Base: dirty 004 ağacı değil; `004-ai-sdlc-excellence` commitlenip tercihen `main`e girdikten sonraki exact SHA
- Minimum ürün: mevcut ders sohbetini rol-bazlı genişletmek; ayrı/genel bir `/agent` oluşturmamak
- Platform admin akademik superuser olmayacak
- Risk sınıfı: `R3`
- Production kapsamı: immutable session audience, role-bound cache, atomik kota rezervasyonu, concurrency/output cap, exam lock, içeriksiz telemetry, feature flag/kill switch ve gerçek-model insan değerlendirmesi

Mevcut sohbet zaten RAG, kaynak, kapsam reddi, sınav kilidi ve ders politikası içeriyor. En kritik yeni güvenlik noktaları rolün yalnız sunucuda belirlenmesi, cache anahtarına rolün eklenmesi ve process-local limitlerin kalıcı/atomik kotayla desteklenmesi. Ayrıntılı sözleşme ve kabul/mutasyon matrisi ana agente iletildi.
</pre>

</details>

<details>
<summary><code>guardian</code> — 2.5 MiB — closed</summary>

- Session: `019fee7c-5443-7ca0-a8be-a652d23d79a3`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T01:42:33.283Z`
- Source log: `rollout-2026-08-11T04-42-33-019fee7c-5443-7ca0-a8be-a652d23d79a3.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/005_spec (Kierkegaard)</code> — 598.2 MiB — closed</summary>

- Session: `019fee89-d146-7210-bbc8-c0f34216f21e`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T01:57:17.255Z`
- Source log: `rollout-2026-08-11T04-57-17-019fee89-d146-7210-bbc8-c0f34216f21e.jsonl`

<pre>
005 Speckit paketi tamamlandı ve uygulamayla hizalandı:

- [spec.md]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/spec.md)
- [plan.md]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/plan.md)
- [research.md]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/research.md)
- [data-model.md]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/data-model.md)
- [api.md]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/contracts/api.md)
- [quickstart.md]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/quickstart.md)
- [tasks.md]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/tasks.md)
- [threat-model.md]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/threat-model.md)

Belgelenen güncel sözleşme:

- 7 parametreli atomik kota fonksiyonu; ders-kullanıcı, global kullanıcı, ders ve platform limitleri.
- 50k/200k/500k/5m veritabanı tavanları ve dört doğru indeks.
- Sınav başlatma, chat finalizasyonu ve `/me/export` için kullanıcı düzeyinde atomik kilit.
- Aktif öğrenci sınavında export için 423 `exam_export_locked`.
- Varsayılanı açık olan `COURSE_AGENT_ENABLED` acil kill switch semantiği.
- Reservation-ledger tabanlı doğru tüketim göstergesi.
- İçeriksiz abuse kayıtları, R3 AI-SDLC ve açık gelecek güvenlik backlog’u.

Doğrulanmış kanıtlar dokümana işlendi:

- Backend: 878/878
- Mypy: 92 dosya temiz
- Frontend: 322/322
- Typecheck ve production build: temiz
- OpenAPI: 50 path, 119 schema
- Dokümanlarda eski 4/5/6 parametreli imza veya eski persona/flag adı kalmadı
- Sekiz dosyada boşluk ve final-newline kontrolleri geçti

Açık bırakılanlar: gerçek tarayıcı/a11y, Playwright, uygulanmış mutasyon matrisi, format/docs/AI kapıları, gerçek provider testi, retention işi, dağıtık rate-limit/WAF/idempotency, platform-lock yük testi, R3 dossier, iki isimli onay, staging ve canary.

Commit veya push yapılmadı; yalnız `specs/005-role-aware-course-agent/**` yazıldı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 2.3 MiB — closed</summary>

- Session: `019fee89-d1f4-7613-9652-52627046cc23`
- Parent: `019fee89-d146-7210-bbc8-c0f34216f21e`
- Started: `2026-08-11T01:57:17.428Z`
- Source log: `rollout-2026-08-11T04-57-17-019fee89-d1f4-7613-9652-52627046cc23.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/005_backend (Maxwell)</code> — 630.2 MiB — closed</summary>

- Session: `019fee8a-7808-7e91-b2ce-6aa90ca15a24`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T01:57:59.944Z`
- Source log: `rollout-2026-08-11T04-57-59-019fee8a-7808-7e91-b2ce-6aa90ca15a24.jsonl`

<pre>
Dar kapsamlı son düzeltme tamamlandı:

- Günlük token kullanımı artık gerçek atomik rezervasyon defterinden hesaplanıyor.
- Provider hatasında tutulan tam ücret arayüz ve bütçe kontrolüne yansıyor.
- Bayat failover açıklaması düzeltildi.
- Temiz test veritabanında 27/27 hedefli test geçti.
- Ruff ve diff kontrolü temiz.
- Commit/push yapılmadı; dosyalar donduruldu.
</pre>

</details>

<details>
<summary><code>guardian</code> — 2.8 MiB — closed</summary>

- Session: `019fee8a-78a8-77f2-a702-cea01d455cf5`
- Parent: `019fee8a-7808-7e91-b2ce-6aa90ca15a24`
- Started: `2026-08-11T01:58:00.105Z`
- Source log: `rollout-2026-08-11T04-58-00-019fee8a-78a8-77f2-a702-cea01d455cf5.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/005_security_review (Meitner)</code> — 350.7 MiB — closed</summary>

- Session: `019feeb3-ca1a-7f81-8966-2a11d2f1371f`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T02:43:07.930Z`
- Source log: `rollout-2026-08-11T05-43-07-019feeb3-ca1a-7f81-8966-2a11d2f1371f.jsonl`

<pre>
Nihai güvenlik hükmü: **P0 yok, P1 yok. 005 backend güven sınırları merge için onaylı; production onayı değildir.** Dosya değiştirmedim.

Güçlü taraflar:

- Audience istemciden alınmıyor; oturum audience’ı değiştirilemez ve cache RLS’i güncel ders rolüne göre ayrılıyor: [0015_role_aware_course_agent.sql]($HOME/code/dou-ai-sdlc-excellence/supabase/migrations/0015_role_aware_course_agent.sql:23).
- Kota ledger’ı doğrudan erişime kapalı; öğrenci/eğitmen/course/platform toplamları, süresi dolmuş charge ve concurrency tek atomik kararda uygulanıyor: [0015_role_aware_course_agent.sql]($HOME/code/dou-ai-sdlc-excellence/supabase/migrations/0015_role_aware_course_agent.sql:169), [aynı dosya]($HOME/code/dou-ai-sdlc-excellence/supabase/migrations/0015_role_aware_course_agent.sql:262).
- Global-user ve platform sorguları için eksik indeksler tamam: [0015_role_aware_course_agent.sql]($HOME/code/dou-ai-sdlc-excellence/supabase/migrations/0015_role_aware_course_agent.sql:144).
- Exam start, chat finalizasyonu ve `/me/export` aynı kullanıcı transaction lock’unda sıralanıyor. Aktif öğrenci sınavında export 423; eğitmen önizleme istisnası server-derived: [exam_state.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/modules/assessment/exam_state.py:62), [privacy.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/api/privacy.py:106), [chat.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/api/chat.py:1003).
- Provider/usage bilinmezliği tam rezervasyonu koruyor; refund/reconcile arızası başarılı cevabı veya özgün provider hatasını maskelemiyor: [quota.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/modules/agent/quota.py:74).
- Ayar tavanları SQL ile aynı: öğrenci 50k, eğitmen 200k, ders 500k, platform 5m: [config.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/core/config.py:256).

Kalan P2’ler:

1. **Kullanım göstergesi muhasebe defterinden sapabilir.** Panel ve ön kontrol hâlâ `request_logs.token_count` toplamını okuyor; provider hatasında tam charge reservation’da kalırken request log oluşmaz. Güvenlik açığı değil—atomik reserve yine reddeder—ama panel eksik tüketim gösterebilir: [service.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/modules/policy/service.py:95), [0009_course_ai_policy.sql]($HOME/code/dou-ai-sdlc-excellence/supabase/migrations/0009_course_ai_policy.sql:84). `course_tokens_today` 0015’te `ai_token_reservations.charged_tokens` üzerinden yeniden tanımlanmalı.

2. **Provider output sınırı canlı ortamda doğrulanmalı.** `max_tokens` gönderiliyor fakat global `litellm.drop_params=True`, gelecekte desteklenmeyen bir modelde sınırı sessizce atabilir: [llm.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/modules/generation/llm.py:188), [llm.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/modules/generation/llm.py:268). Varsayılan Groq/Gemini modellerinde gerçek-provider testi production kapısı olmalı; desteklenmeyen model fail-closed reddedilmeli.

3. **Yorum gerçek davranışla çelişiyor.** `provider_attempt_limit=1` olduğundan role-aware yolda transport failover yok; satır 233 tersini söylüyor: [service.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/modules/generation/service.py:227). Güvenlik açısından tek deneme doğru ve bütçeli; yorum düzeltilmeli. Failover istenirse iki provider denemesinin üst maliyeti baştan rezerve edilmeli.

Production öncesi açık kabul/operasyon işleri:

- Workerlar arası birleşik request-rate limiti, replay/idempotency ve edge/WAF henüz yok: [threat-model.md]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/threat-model.md:187).
- Guard/reservation retention job’ı ve provider veri bölgesi/saklama sözleşmesi açık: [threat-model.md]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/threat-model.md:202).
- Tek platform lock’u doğruluk sağlıyor fakat staging yük testinde throughput/pool baskısı ölçülmeli.

Kanıt durumu: backend şeridi temiz DB’de **157/157 hedefli**, tam API’de **877/877** bildirdi. Ben final dosyaları yeniden okudum ve `git diff --check` temiz; suite’i ayrıca yeniden koşturmadım.
</pre>

</details>

<details>
<summary><code>/root/005_e2e (Gibbs)</code> — 285.3 MiB — closed</summary>

- Session: `019fef29-31f7-7c63-b713-726d35d87a69`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T04:51:22.232Z`
- Source log: `rollout-2026-08-11T07-51-22-019fef29-31f7-7c63-b713-726d35d87a69.jsonl`

<pre>
E2E kapsamı tamamlandı, commit/push yapılmadı.

- Öğrenci için sunucudan türetilen `Ders Koçu` paneli eklendi.
- Eğitmen için `Eğitmen Asistanı` ve istemcinin rol/persona gönderemediği doğrulandı.
- Aktif sınavda panel açılıyor ancak mesaj gönderme alanı çizilmiyor.
- TypeScript kontrolü ve Playwright test keşfi geçti.
- Gerçek tarayıcı koşusu yerel PostgreSQL/API kapalı olduğu için koşulmadı; CI’da seri çalıştırılmalı.

Değişiklikler yalnızca:

- `apps/web/e2e/role-aware-agent.spec.ts`
- `apps/web/e2e/flows.spec.ts`
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.3 MiB — closed</summary>

- Session: `019fef29-3282-7232-97d1-259583ebf2e7`
- Parent: `019fef29-31f7-7c63-b713-726d35d87a69`
- Started: `2026-08-11T04:51:22.371Z`
- Source log: `rollout-2026-08-11T07-51-22-019fef29-3282-7232-97d1-259583ebf2e7.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/005_final_audit (Aristotle)</code> — 755.9 MiB — closed</summary>

- Session: `019fef2e-47a0-7990-be42-c29c39da5265`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T04:56:55.456Z`
- Source log: `rollout-2026-08-11T07-56-55-019fef2e-47a0-7990-be42-c29c39da5265.jsonl`

<pre>
Son audit sonucu: güncel ağaçta kalan actionable P0/P1/P2 kod kusuru bulamadım.

- Ders-geneli token bütçesi düzeltildi ve çok kullanıcılı testle sabitlendi.
- Eğitmen availability ile doğrudan POST davranışı artık tutarlı.
- `git diff --check` temiz.

Hüküm:

- Checkpoint commit: GO
- Feature merge: Henüz NO-GO
- Production: NO-GO

Merge öncesi zorunlu açık kanıtlar: RLS/mutasyon matrisi, gerçek seri Playwright ve direct-API sınav kilidi, manuel erişilebilirlik/browser turu, tam repo kapıları, R3 dossier ve doküman kapısı. Production için ayrıca gerçek provider/staging, iki bağımsız onay, canary ve rollback provası gerekiyor.

Bu auditte ortak veritabanına dokunmadım; bildirilen fresh-DB 27/27 ve policy 12/12 sonuçlarını liderin kanıtı olarak kabul ettim.
</pre>

</details>

<details>
<summary><code>/root/005_dossier_plan (Singer)</code> — 627.9 MiB — closed</summary>

- Session: `019fef2e-d5a2-7742-a483-3042a35515e0`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T04:57:31.810Z`
- Source log: `rollout-2026-08-11T07-57-31-019fef2e-d5a2-7742-a483-3042a35515e0.jsonl`

<pre>
`005-role-aware-course-agent` için doğru kayıt bir kök R3 dossier olmalı. Mevcut snapshot’ta `HEAD` hâlâ base SHA’da ve tüm 005 değişiklikleri çalışma ağacında; bu nedenle dossier/evidence en son, dosyalar sabitlendikten sonra üretilmeli.

## Dosyalar

- Dossier: `.ai/changes/005-role-aware-course-agent.json`
- Kanıt: `.ai/evidence/005-role-aware-course-agent-local.json`
- `change_id`: `005-role-aware-course-agent`
- `lineage_id`: `role-aware-course-agent`
- `revision`: `1`
- `supersedes`: `null`
- `previous_status`: `null`
- `base_sha`: `7c1c2192ab80cb63f593d433392d9f58a4d2f476`
- `candidate_sha`: `SELF`
- `governance_record_risk`: `R3`
- `risk_tier`: `R3`
- `status`: `evidence-ready`
- `owner`: `Muratcan Ateş`

R3 gerekçesi: ders üyeliğinden rol çıkarımı, öğrenci mahremiyeti, sınav/chat/export yarışları, kalıcı kota ledger’ı, RLS ve yeni migration doğrudan yetkilendirme, sınav bütünlüğü ve maliyet güvenliğini etkiliyor.

## Zorunlu artifact kapsamı

Mevcut HEAD policy’sine göre aşağıdaki 24 yolun tamamı dossier `artifacts` dizisinde `state: &quot;present&quot;` ve son commit içeriğinin SHA-256’sıyla yer almalı:

```text
.ai/policy.json
.env.example
apps/api/app/api/chat.py
apps/api/app/api/exams.py
apps/api/app/api/policy.py
apps/api/app/api/privacy.py
apps/api/app/contracts.py
apps/api/app/core/config.py
apps/api/app/models/chat.py
apps/api/app/models/policy.py
apps/api/app/modules/agent/__init__.py
apps/api/app/modules/agent/quota.py
apps/api/app/modules/assessment/exam_state.py
apps/api/app/modules/generation/llm.py
apps/api/app/modules/generation/prompts.py
apps/api/app/modules/generation/service.py
apps/api/app/modules/policy/service.py
apps/api/app/schemas/chat.py
apps/api/app/schemas/policy.py
apps/web/app/courses/[courseId]/chat/page.tsx
apps/web/components/course-assistant/course-assistant.tsx
apps/web/lib/chat-availability.ts
apps/web/lib/course-assistant.ts
supabase/migrations/0015_role_aware_course_agent.sql
```

İzlenebilirliği tamamlamak için şu policy-dışı fakat davranış/sözleşme üreten dosyaların da artifact listesine alınmasını öneririm:

```text
apps/api/app/core/errors.py
apps/web/components/course-nav.tsx
apps/web/components/portal/dashboard-course-card.tsx
apps/web/components/ui.tsx
apps/web/lib/types.ts
specs/001-course-assistant-mvp/contracts/openapi.json
```

Dossier ve evidence dosyasını artifact listesine koymayın; dossier kendi kendini hash’leyemez, evidence zaten ayrı `evidence` kaydıyla bağlanır.

## Behavior değerleri

Önerilen dürüst revision etiketleri:

```json
{
  &quot;provider_revision&quot;: &quot;litellm-role-aware-single-attempt-v1; real provider not verified&quot;,
  &quot;model_revision&quot;: &quot;not-pinned:not-deployed; exact model required before staging&quot;,
  &quot;prompt_revision&quot;: &quot;005-role-aware-course-agent-v1&quot;,
  &quot;tool_schema_revision&quot;: &quot;none-v1:no-tools-no-writes&quot;,
  &quot;guardrail_revision&quot;: &quot;005-role-quota-exam-privacy-v1&quot;,
  &quot;retrieval_revision&quot;: &quot;base-7c1c219-hybrid-retrieval; source-policy and corpus-revision cache binding&quot;,
  &quot;embedding_revision&quot;: &quot;unchanged-from-base-7c1c219&quot;,
  &quot;evaluator_revision&quot;: &quot;005-fake-provider-contract-suite-v1&quot;
}
```

Model/provider’ın henüz pinlenmemiş olduğunu saklamamak önemli; bu durum `evidence-ready` için kabul edilebilir, staging/production terfisini ise bilinçli olarak engeller.

## Data ve evaluation

- `privacy_classification`: `synthetic-non-personal`
- `corpus_digest`: dış ders corpus’u kullanılmadığı için boş SHA-256 (`e3b0...`) ve evidence raporunda “no external corpus used” açıklaması.
- `eval_set_digest`: seçilen backend/frontend test dosyalarının sıralı `path + sha256` manifestinin SHA-256’sı.
- `calibration_ref`: `specs/005-role-aware-course-agent/spec.md` içindeki önceden tanımlanmış mekanik başarı kapıları.
- `holdout_ref`: `not-run: role-separated real-provider holdout is T502`
- `human_anchor_ref`: `not-run: pedagogy/privacy human anchor and T503 approvals pending`
- `thresholds_declared_before_scoring`: `true`; eşikler “0 failure / tüm vaka pass” olarak Speckit’te önceden tanımlı.
- Gerçek provider, faithfulness veya pedagojik kalite sonucu iddia edilmemeli.

Önerilen sayısal metrikler:

```text
backend_tests_passed:       baseline 851, candidate 878, &gt;= 878, sample 878
frontend_lib_tests_passed:  baseline 311, candidate 322, &gt;= 322, sample 322
forged_persona_fields_rejected: baseline 0, candidate 2, &gt;= 2, sample 2
quota_race_overshoots:      baseline 0, candidate 0, == 0, sample 3
```

Playwright iki rol yolculuğu gerçekten koştuktan sonra ayrıca:

```text
role_browser_journeys_passed: baseline 0, candidate 2, &gt;= 2, sample 2
```

## Evidence raporu

Tek passing label şimdilik `fake-provider` olmalı. Yerel PostgreSQL, fake LLM, unit/integration, build ve yerel browser çalışması `staging` veya `real-provider` değildir.

Raporun zorunlu eşleşen üst alanları:

```json
{
  &quot;candidate_sha&quot;: &quot;SELF&quot;,
  &quot;evidence_label&quot;: &quot;fake-provider&quot;,
  &quot;result&quot;: &quot;pass&quot;
}
```

Ek alanlarda şunlar tutulabilir:

- backend 878/878;
- hedefli backend 305/305;
- Ruff check/format ve mypy 92 dosya;
- frontend 322/322, typecheck, production build;
- OpenAPI 50 path/119 schema ve `ChatRequest` içinde audience/role/max_tokens/user_id bulunmadığı;
- varsa seri Playwright sonucu;
- kullanılan tam komutlar;
- sadece sentetik fixture kimlikleri;
- gerçek provider, staging, load, WAF/idempotency, retention/residency ve canlı rollback’in `not-run` olduğu.

Evidence item:

```json
{
  &quot;label&quot;: &quot;fake-provider&quot;,
  &quot;result&quot;: &quot;pass&quot;,
  &quot;report_path&quot;: &quot;.ai/evidence/005-role-aware-course-agent-local.json&quot;,
  &quot;report_sha256&quot;: &quot;&lt;final evidence file sha256&gt;&quot;,
  &quot;candidate_sha&quot;: &quot;SELF&quot;
}
```

## Approval, deployment ve rollout

R3 için üç rol kaydı zorunlu; `evidence-ready` aşamasında kararları pending kalabilir:

- `engineering`
- `domain`
- `security_or_privacy`

Her kayıtta:

```json
{
  &quot;decision&quot;: &quot;pending&quot;,
  &quot;approval_ref&quot;: null,
  &quot;approved_at&quot;: null,
  &quot;candidate_sha&quot;: &quot;SELF&quot;,
  &quot;independent_of_author&quot;: true
}
```

Actor alanı boş olamaz ve owner ile aynı olmamalı. Domain actor olarak Yasemin Karagül biliniyor; diğerleri gerçekten atanmadıysa “Pending independent engineering reviewer” ve “Pending Bilgi İşlem security/privacy reviewer” denmeli, alınmış onay gibi gösterilmemeli.

Deployment:

```json
{
  &quot;feature_flag&quot;: &quot;COURSE_AGENT_ENABLED&quot;,
  &quot;flag_state&quot;: &quot;disabled&quot;,
  &quot;candidate_sha&quot;: &quot;SELF&quot;,
  &quot;deployment_id&quot;: &quot;not-deployed:005-role-aware-course-agent&quot;,
  &quot;environment&quot;: &quot;not-deployed&quot;
}
```

Buradaki `disabled`, kod varsayılanının `true` olmasını inkâr etmiyor; henüz aktif deployment/canary olmadığını ifade ediyor.

Rollout:

- Kill switch: `COURSE_AGENT_ENABLED=false`, API redeploy/restart; chat provider/session/cache/quota yazmadan fail-closed 503.
- Assignment metninde validator için kelimesi kelimesine `sticky` bulunmalı.
- İlk exposure: none; sonra internal/instructor-only staging, ardından küçük sticky student cohort.
- Aktif sınavlar açık onay tamamlanana kadar dışarıda.
- Stop: herhangi bir cross-role/cross-course veri kaçağı, exam/export bypass, quota overshoot, citation/scope fail-open veya kill-switch başarısızlığı.
- Expand: exact provider/model pin, role-separated real-provider holdout, staging RLS/auth, multi-worker load, retention/residency kararı, rollback provası ve üç bağımsız approval.

## Rollback

```text
previous_compatible_artifact: base:7c1c2192...
max_minutes: 15
state: planned
```

Prosedür:

1. `COURSE_AGENT_ENABLED=false`.
2. Availability disabled ve POST `/chat` 503; provider çağrısı ve yeni session/cache/quota artifact’i sıfır olduğunu doğrula.
3. Gerekirse uygulama kodunu base SHA’ya geri al.
4. `0015` additive şemasını yerinde bırak; canlı veriyi yok eden down migration yapma.
5. Core chat/exam/privacy akışlarını tekrar doğrula.

`state: planned` iken dört rollback evidence alanının tamamı `null` olmalı.

Promotion:

```json
{
  &quot;claim&quot;: &quot;none&quot;,
  &quot;target&quot;: &quot;none&quot;,
  &quot;human_approval_refs&quot;: []
}
```

## Validator tuzakları

- Dossier adı ile `change_id` birebir aynı olmalı.
- Validator yalnız commit blob’larını okur. Şu an `HEAD == base`; uncommitted çalışmaya karşı gerçek doğrulama yapılamaz.
- Final formatter, OpenAPI veya docs işlemlerinden sonra hash üretin. Sonradan artifact değişirse bütün ilgili hash’leri yenileyin.
- Final `head_sha` 40 karakterli commit olmalı ve checkout `HEAD` onunla aynı olmalı.
- `base_sha`, verilen dal adı değil hesaplanan merge-base olmalı; mevcut durumda doğru değer `7c1c2192...`.
- Yeni evidence aynı diff’te yeni dossier tarafından referanslanmalı; orphan evidence fail olur.
- Dossier/evidence append-only. Daha sonra düzeltme gerekirse mevcut kayıt düzenlenmez, yeni revision oluşturulur.
- Dossier ve tüm nested object’lerde `additionalProperties: false`; fazladan açıklama alanı dossier’a eklenemez. Zengin açıklamalar evidence raporuna konabilir.
- Evidence raporundaki `candidate_sha`, `evidence_label`, `result` dossier item ile birebir eşleşmeli.
- `fake-provider` için GitHub run URL gerekmez; passing `real-provider/staging/canary/production` için gerçek GitHub Actions run URL zorunlu.
- `evidence-ready` en az bir passing evidence ister; fake-provider mekanik kanıt bunun için yeterli ama production iddiasına yetmez.
- `canary/expanded` durumları immutable GitHub PR review URL’leri ve onaylı üç R3 actor olmadan reddedilir.
- Planned rollback kanıtlı gösterilemez; evidence alanları null kalmalı.
- `.ai/schema.json` sabit digest ile korunuyor; dokunulmamalı.
- Final policy ile duyarlı yol listesi yeniden çıkarılmalı; yeni bir sensitive path eklenirse 24 yol listesi güncellenir.
- Son doğrulama komutu final commit oluşturulduktan sonra çalışmalı:

```bash
apps/api/.venv/bin/python scripts/ai_sdlc_check.py \
  --repo-root . \
  --policy .ai/policy.json \
  --base-sha 7c1c2192ab80cb63f593d433392d9f58a4d2f476 \
  --head-sha &lt;final-40-char-head&gt;
```

Bu plan `dou-synapse-ai-sdlc` kuralına göre 005’i “mekanik olarak kanıtlanmış yerel R3 aday” seviyesinde tutuyor; gerçek model kalitesi, staging ve production terfisini yanlışlıkla yapılmış gibi göstermiyor.
</pre>

</details>

<details>
<summary><code>/root/005_rls_mutation (Linnaeus)</code> — 348.6 MiB — closed</summary>

- Session: `019fef56-18b6-7da0-be21-5a66ce16b740`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T05:40:24.887Z`
- Source log: `rollout-2026-08-11T08-40-24-019fef56-18b6-7da0-be21-5a66ce16b740.jsonl`

<pre>
Tamamlandı.

- Yeni dosya: `supabase/tests/rls_role_aware_agent_mutation_check.sh`
- 8 güvenlik mutasyonu tanımlandı.
- 7 kapalı erişim sınırı ve 3 kalıcı kota referans iddiası var.
- `bash -n` ve whitespace kontrolü temiz.
- Betik çalıştırılabilir durumda.
- Başka dosyaya dokunulmadı; commit/push yapılmadı.
- Aktif sınavdaki `/me/export` kilidi SQL yüzeyi olmadığı için dürüstçe HTTP testi kapsamına bırakıldı.
- Diskte yalnız 157 MiB kaldığından geçici veritabanlı gerçek mutasyon koşusu yapılmadı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.2 MiB — closed</summary>

- Session: `019fef56-1906-7391-95d9-8726072f0a5a`
- Parent: `019fef56-18b6-7da0-be21-5a66ce16b740`
- Started: `2026-08-11T05:40:24.966Z`
- Source log: `rollout-2026-08-11T08-40-24-019fef56-1906-7391-95d9-8726072f0a5a.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>guardian</code> — 1.4 MiB — closed</summary>

- Session: `019fef77-2576-7d32-93c5-d5104c1f11b3`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T06:16:30.838Z`
- Source log: `rollout-2026-08-11T09-16-30-019fef77-2576-7d32-93c5-d5104c1f11b3.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/market_agent_portfolio (Hegel)</code> — 283.6 MiB — closed</summary>

- Session: `019fef79-942e-7920-af8a-bd23137953e6`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T06:19:10.254Z`
- Source log: `rollout-2026-08-11T09-19-10-019fef79-942e-7920-af8a-bd23137953e6.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/repo_feature_gap (Sartre)</code> — 434.3 MiB — closed</summary>

- Session: `019fef7a-02d9-71f0-9a75-d1ce407a3335`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T06:19:38.585Z`
- Source log: `rollout-2026-08-11T09-19-38-019fef7a-02d9-71f0-9a75-d1ce407a3335.jsonl`

<pre>
## Salt okunur repo hükmü

Yetkili çalışma kopyası şu an `$HOME/code/dou-ai-sdlc-excellence`:

- Worktree temiz.
- `origin/main`: `2c178861a3e484af8643f999f210db040eb84e68` — PR #4 ile `002-production-hardening` ana dala girmiş.
- `origin/005-role-aware-course-agent`: `fc5bd59622c19dfea825f6a751871b7da3dcfc56`.
- `005`, güncel `origin/main`in 9 commit önünde, 0 gerisinde; `004-ai-sdlc-excellence` commit’lerini de içeriyor.
- Dolayısıyla eski `$HOME/code/DOU-Synapse` worktree’sindeki yerel `main` güncel kaynak değil; orada `feat/chat-socratic` ve silinmiş upstream bulunuyor.

En önemli gerçek: rol farkındalıklı ajan **yazıldı ama henüz main’de değil**. Üstelik şartname açıkça gerçek tarayıcı, gerçek sağlayıcı, staging, isimli onay ve canlı rollout kanıtlarının olmadığını söylüyor: [005 spec]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/spec.md:3), [açık release kapıları]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/tasks.md:182).

## Yeniden yapılmaması gerekenler

Şunlar zaten var; yeni isimle ikinci kez yazılmamalı:

- Öğrenci koçu ve eğitmen yardımcısı: rol istemciden değil sunucudan geliyor. [contracts.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/contracts.py:104)
- Ders kapsamlı kaynaklı chatbox, sınav kilidi, kota, ret ve kill switch. [chat.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/api/chat.py:788), [CourseAssistant]($HOME/code/dou-ai-sdlc-excellence/apps/web/components/course-assistant/course-assistant.tsx:3)
- Kaynak/chunk ve retrieval kalite ajanı yerine zaten Retrieval Laboratuvarı var. [sources/page.tsx]($HOME/code/dou-ai-sdlc-excellence/apps/web/app/courses/[courseId]/sources/page.tsx:28)
- AI soru üretimi zaten taslak çıkarıyor; öğretmen onayı olmadan yayınlamıyor. [questions.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/api/questions.py:240)
- Sınav blueprint’i, sürümleme ve açık öğretmen yayını zaten var. [blueprints.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/api/blueprints.py:281)
- Bilgi İşlem paneli zaten salt okunur ve kişisel sohbet taşımıyor. [admin.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/api/admin.py:1)
- Genel web tarayan ajan, otonom multi-agent sürüsü, otomatik soru/not/sınav yayınlayan ajan ve adminin öğrenci konuşmalarını okuduğu bir “analiz ajanı” eklenmemeli.

## Gerçek ürün boşlukları

Hedefli aramada `apps/` ve migration’larda çalışma planı, review queue, spaced repetition, akademik duyuru/takvim ve ders planı üretim modeli bulunmadı.

Mevcut öğrenci kişiselleştirmesi yalnız EWMA mastery göstergesi üretiyor; hangi gün ne çalışacağını planlamıyor. [mastery/service.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/modules/mastery/service.py:1)

Öğretmen analitiği toplu konu ortalamalarını veriyor fakat eyleme dönük haftalık müdahale planı üretmiyor. [analytics.py]($HOME/code/dou-ai-sdlc-excellence/apps/api/app/api/analytics.py:222)

## Öncelikli üç yeni Speckit dikey dilimi

Ön koşul: yeni ajan eklemeden önce 005’in PR/CI, gerçek tarayıcı ve staging/real-provider kapıları kapatılmalı.

### 006 — Student Learning Loop

Tekrarlı kullanım için en değerli dilim.

- “Bugün 20 dakika ne çalışmalıyım?” planı.
- Mastery, yanlış sorular, ipucu kullanımı ve yayınlanmış sınav tarihinden günlük review queue.
- Aralıklı tekrar kartları, tamamlandı/ertele akışı ve haftalık ilerleme.
- AI yalnız açıklama ve plan taslağı üretir; öğrenci verisini başka kullanıcıyla paylaşmaz.
- Önerilen yüzeyler:
  - `GET /courses/{id}/study-plan`
  - `POST /courses/{id}/study-plan/regenerate`
  - `POST /courses/{id}/study-plan/items/{item_id}/complete`
  - `/courses/{id}/study-plan`
- RLS: öğrenci yalnız kendi planını görür; öğretmen yalnız toplu kapsama oranı görür.
- Aktif sınav sırasında AI plan üretimi kapalı kalmalı.

### 007 — Instructor Studio

Yeni sohbet persona’sı değil, görünür öğretmen araçları.

- Kaynaklı ders anlatım taslağı.
- Öğrenme çıktısına bağlı lesson outline.
- Rubrik taslağı ve ölçüt kırılımı.
- Blueprint hücresine bağlı soru seti taslağı.
- “Sınıfın zorlandığı konu için mini tekrar paketi” önerisi.
- Tüm çıktılar `draft`; öğretmen düzenleyip açıkça onaylamadan soru havuzuna veya derse geçmez.
- Mevcut soru üretimi, blueprint, analytics ve kaynak laboratuvarı yeniden kullanılır.
- Önerilen yüzey:
  - `/courses/{id}/studio`
  - draft artifact uçları
  - var olan `/questions/generate` ve blueprint yayın uçlarına açık insan onayıyla geçiş.

### 008 — Course Activity &amp; Notification Center

AI’sız başlaması gereken kritik tam-site özelliği.

- Ders duyuruları.
- Sınav açılış/kapanış tarihleri.
- Kaynak hazır/işleme başarısız bildirimi.
- Öğrencinin günlük review hatırlatıcısı.
- Web içi bildirim merkezi ve kullanıcı tercihleri.
- E-posta/push entegrasyonu ancak sonra; ilk sürümde teslim kaydı ve okunma durumu.
- AI yalnız uzun duyuruyu özetleyebilir; kendi başına duyuru yayınlayamaz.
- Önerilen yüzeyler:
  - `/notifications`
  - `/courses/{id}/activity`
  - `course_events`, `notifications`, `notification_preferences`.

## Daha sonra eklenebilecek ajanlar

- **Sınıf Müdahale Asistanı:** Yalnız toplu analitikten haftalık kavram yanılgısı özeti; ham öğrenci sohbeti yok.
- **Bilgi İşlem Operasyon Copilot’u:** Sağlık, gecikme, ingestion ve runbook önerileri; ilk sürüm salt okunur, restart/silme/deploy yetkisi yok.
- **Kaynak Bakım Asistanı:** Mevcut retrieval laboratuvarından zayıf/parçalanmış/eski kaynak önerisi; chunk’ı otomatik değiştirmez.

Net önerim: ürünün bir sonraki büyük yatırımı yeni bir genel chatbot değil, **005’i doğrulayıp main’e almak, ardından 006 Student Learning Loop** olmalı. Öğrencilerin platformda zaman geçirmesini sağlayacak esas eksik, daha fazla sohbet kişiliği değil; ölçülen zayıflığı günlük çalışmaya dönüştüren devamlı öğrenme döngüsü.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:1002-1046|note=[authoritative DOU worktree and production hardening coordination safeguards]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019fe851-db7d-79a1-b895-f61bbf4ca463
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>/root/product_skill_forward_test (Halley)</code> — 0.5 MiB — closed</summary>

- Session: `019fef86-9785-7982-a738-7db14cc78b1e`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T06:33:23.077Z`
- Source log: `rollout-2026-08-11T09-33-23-019fef86-9785-7982-a738-7db14cc78b1e.jsonl`

<pre>
## Örnek ürün kararı

CourseGPT’ye genel web tarayan otonom multi-agent eklemeyelim. Öğretmen için kaynak kalite işini seçelim; fakat bunu yeni bir ajan/chatbox olarak değil, mevcut Retrieval Laboratuvarı’nı tamamlayan denetlenebilir bir iş akışı olarak tasarlayalım.

Depo gerçeği bu ayrımı zorunlu kılıyor:

- Eğitmene özel `POST /courses/{course_id}/sources/inspect`, chunk skorları, kanıt kararı ve komşu kaynak bağlamı zaten kodda var: [sources.py]($HOME/code/dou-lead/apps/api/app/api/sources.py:22), [sources/page.tsx]($HOME/code/dou-lead/apps/web/app/courses/[courseId]/sources/page.tsx:29).
- Bu yetenek `origin/main` SHA `2c17886147…` içinde bulunuyor. Dolayısıyla “kaynak kalite asistanı” adıyla ikinci bir sohbet yüzeyi yapmak duplikasyon olur.
- Depo teslim kaydı laboratuvarı `Kodlandı`, `Yerelde doğrulandı` ve `main&#x27;e birleşti` olarak gösteriyor; bu turda testler yeniden koşulmadı. `Staging&#x27;de kanıtlandı`: hayır. `Production&#x27;da kanıtlandı`: hayır.
- Sonraki numara `006`; çünkü `004-ai-sdlc-excellence` ve `005-role-aware-course-agent` zaten ayrılmış durumda. `005` dalı `fc5bd59622c19dfea825f6a751871b7da3dcfc56` ile origin’e eşit fakat taze DB, gerçek sağlayıcı, staging ve canary kapıları açık.
- Çalışma diskinde yalnız yaklaşık 394 MiB boş alan var; yeni worktree/test koşusundan önce bu operasyonel engel giderilmeli.

### Karşılaştırmalı puan

| Aday | Pozitif değer | Risk/engel cezası | Sonuç | Karar |
|---|---:|---:|---:|---|
| Genel web tarayan otonom multi-agent | 11 | -41 | **-30** | Do not build |
| Mevcut laboratuvarı tamamlayan kaynak kalite iş akışı | 70 | -7 | **63** | Next |
| Ayrı “kaynak kalite ajanı” chatbox’ı | Yüksek görünür değer | Sert duplikasyon engeli | Puan geçersiz | Do not build |

Puan toplamı güvenlik engelini geçersiz kılamaz. Web ajanı; öğretmen-onaylı corpus, “kaynak yoksa cevap yok”, maliyet, izin ve izlenebilirlik sözleşmelerini aynı anda genişletiyor.

### Güncel ürün desenleri

| Kaynak | Kanıtlanmış desen | Yerel durum | Uyarlama | Risk | Başarı ölçüsü |
|---|---|---|---|---|---|
| [NotebookLM resmî yardım](https://support.google.com/notebooklm/answer/16179559) | Kaynak seçme/dışlama ve citation’dan özgün bağlama gitme | Kaynak bağlamı var | Yalnız onaylı source-set snapshot’ı kullan | Web kaynağını ders gerçeği sanmak | Onaysız kaynaktan cevap: 0 |
| [RAGFlow resmî quickstart](https://github.com/infiniflow/ragflow/blob/main/docs/quickstart.mdx) | Chunk görünürlüğü ve retrieval testing | Büyük kısmı zaten var | Tekrarlanabilir test vakaları, sorun etiketi ve çözüm kuyruğu ekle | Sessiz chunk/eşik değişikliği | Sabit holdout’ta recall@5 değişimi |
| [Khanmigo Teacher Tools](https://support.khanacademy.org/hc/en-us/articles/14799047733645-What-teacher-tools-are-available-on-Khanmigo-) | Genel ajan sürüsü yerine öğretmenin belirli işlerine ayrılmış araçlar | Eğitmen yardımcısı `005` dalında | Laboratuvar içinde görev odaklı kalite akışı | Dekoratif ikinci chatbot | İnceleme süresi ve öğretmen kabul oranı |

## Önerilen Speckit dilimi

**006-instructor-source-quality-workflow**

**Immutable base:** `fc5bd59622c19dfea825f6a751871b7da3dcfc56`
**Başlama kapısı:** `005` taze DB/RLS, gerçek sağlayıcı, staging ve canary kanıtları kapanmadan implementation başlamaz. Main’e farklı bir merge SHA ile girerse base alanı yeniden üretilir.

**Risk:** R3. Yeni öğretmen-yetkili kayıtlar, RLS ve audit sözleşmesi eklediği için; AI’ın otomatik eylem yetkisi olmasa da authorization kapsamına giriyor.

1. **Yolculuklar**
   - Eğitmen: temsilî öğrenci sorusu kaydeder, retrieval sonucunu çalıştırır, zayıf sonucu `kaynak eksik / eski sürüm / OCR-parçalama / yanlış sıralama / kapsam dışı` diye etiketler, deterministik öneriyi kabul eder veya reddeder.
   - Öğrenci: yeni yüzey görmez; yalnız öğretmenin onayladığı kaynak düzeltmesinden sonra mevcut kaynak-sınırlı akışı kullanır.
   - Platform admin: yalnız toplu işlem/başarısızlık sayıları görür; sorgu, chunk metni ve öğretmen notunu göremez.

2. **Non-goals / yasaklar**
   - Genel web tarama, multi-agent delegation, kod çalıştırma.
   - Otomatik kaynak ekleme, chunk düzenleme, threshold/policy değiştirme veya yayınlama.
   - Öğrenci sohbeti, cevabı ya da bireysel davranış verisini kalite ekranına taşıma.
   - Yeni bir “kaynak ajanı” sohbet kimliği.

3. **DB/RLS**
   - `0016_source_quality_reviews.sql` rezervasyonu.
   - `source_quality_cases`, `source_quality_runs`, `source_quality_reviews`.
   - Ders eğitmeni kendi dersinde CRUD; öğrenci erişimi yok; platform admin yalnız privacy-safe aggregate.
   - Run kaydı source-set/version ve retrieval-config revision taşır; ham chunk metnini kopyalamaz.
   - Öneri kabulü yalnız review durumunu değiştirir, kaynak içeriğini değiştirmez.

4. **API ve UI**
   - `POST /courses/{course_id}/source-quality/cases`
   - `POST /courses/{course_id}/source-quality/cases/{id}/run`
   - `GET /courses/{course_id}/source-quality/summary`
   - `PATCH /courses/{course_id}/source-quality/reviews/{id}`
   - Mevcut kaynak sayfasında typed Next.js “Kalite vakaları” bölümü.
   - Empty, error, stale-source, forbidden ve disabled states; klavye erişilebilir tarayıcı yolu.

5. **Kontroller**
   - Server-owned course role, kaynak sürüm snapshot’ı, oran/kota sınırı, audit kaydı.
   - LLM çağrısı yok; öneriler ölçülmüş sinyallerden deterministik şablonlarla üretilir.
   - Ders başına vaka kotası, eşzamanlı run sınırı ve süre bütçesi.
   - Telemetry’de soru/chunk/not metni yok.

6. **Kanıt**
   - Fake-provider testi provider çağrı sayısının sıfır kaldığını göstermeli.
   - Gerçek `fastembed` corpus holdout’u; aynı vakada tekrar üretilebilir sonuç.
   - Eğitmen/öğrenci/admin RLS ve karşı-mutasyon.
   - API, OpenAPI, typed frontend, tarayıcı, 50-vaka load testi.
   - En az iki eğitmenle kör root-cause/öneri yararlılığı değerlendirmesi.

7. **Rollout**
   - `SOURCE_QUALITY_REVIEW_ENABLED` bayrağı ve kill switch.
   - Önce iç ekip, sonra iki ders/beş eğitmen pilotu.
   - Geri alma UI/API’yi kapatır; inceleme kayıtlarını silmez.
   - Ürün, RAG, güvenlik ve release sorumlularının isimleri spec’te doldurulmadan promotion yok.

8. **Çıkış metrikleri**
   - Workflow: başarısız retrieval vakasını sınıflandırma medyanı hedefi ≤3 dakika.
   - Kalite: sabit holdout’ta recall@5 artarken kapsam-dışı false-accept kötüleşmemeli.
   - Güvenilirlik/maliyet: sıcak p95 hedefi ≤2 saniye ve vaka başına LLM çağrısı 0.
   - Bunlar hedeflerdir; ölçülmeden başarı iddiası değildir.

9. **Bağımlılıklar**
   - `005` kapıları ve main entegrasyonu.
   - Migration `0015` sırası.
   - Sürüm sabitli öğretmen test vakaları.
   - Adlandırılmış insan onaylayıcılar.
   - Test çalıştırmaya yetecek disk alanı.

### Yol haritası

- **Now:** `005` R3 kanıtlarını, main entegrasyonunu ve disk engelini kapat.
- **Next:** `006` kalite vaka/inceleme akışı; ardından kaynak-sürümü yeniden işleme görünürlüğü ve privacy-safe eğitmen kalite özeti.
- **Later:** Öğretmenin sonuçları inceleyip tek tek seçtiği, provenance/telif kapılı web kaynağı keşif ve import akışı.
- **Do not build:** cevap anında sınırsız web tarama, otonom swarm, ayrı kaynak-kalite chatbox’ı, sessiz chunk/policy mutasyonu.

## Beceri değerlendirmesi

Beceri genel olarak güçlü ve kullanılabilir:

- **Netlik:** Ajan gerekip gerekmediğini belirleyen kurallar ve dört yol haritası kovası açık.
- **Duplikasyon:** Bu örnekte gerçek bir kopyayı yakaladı; portföy referansı ayrı kaynak ajanı yerine mevcut laboratuvarın genişletilmesini zorladı.
- **Güvenlik:** Genel web ajanını, swarm’ı ve sessiz kaynak mutasyonunu doğrudan reddetti.
- **Speckit uygulanabilirliği:** DB/RLS, API/UI, kanıt, rollout, rollback, metrik ve bağımlılık alanları somut bir dikey dilim üretti.

Bulduğum kusurlar:

1. **Authoritative base seçim algoritması eksik.** Paralel worktree’lerde branch, `.specify/feature.json`, `origin/main` ve daha yeni feature dalları çelişebiliyor. Öncelik sırası ve integrator onayı tanımlanmalı.
2. **Puanlama anchor’ları yok.** `0–5` değerlerinin ne anlama geldiği tanımlanmadığı için iki uygulayıcı farklı toplamlar üretebilir.
3. **Risk-orantılı kanıt matrisi eksik.** Her dilim için fake-provider, real-provider, load ve human-review istemek deterministik özelliklerde gereksiz olabilir; “uygulanamaz + neden” seçeneği yazılmalı.
4. **R3 tanımı fazla geniş.** “Authorization” ifadesi yeni, CourseInstructor ile korunan hemen her endpoint’i R3 yapabiliyor; yeni yetki sınırı ile mevcut bağımlılığın yeniden kullanımı ayrılmalı.
5. **Numara/migration rezervasyon protokolü yok.** Paralel Speckit dallarında `006` veya `0016` çakışmasını önleyecek ortak rezervasyon kaydı tarif edilmeli.
6. **Bloklanmış yüksek değer için kova belirsiz.** “Now fakat blocked” ile “Next” arasında açık bir durum etiketi eklenmeli.
7. **Teslim etiketlerinde hedef ref eksik.** `main&#x27;e birleşti` ifadesi repo/remote/SHA ile birlikte zorunlu olmalı.

Dosyalarda değişiklik yapılmadı; test veya staging çalıştırılmadı.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
MEMORY.md:322-325|note=[source bounded product contract and external web deferral]
MEMORY.md:1004-1005|note=[authoritative DOU worktree guidance]
MEMORY.md:1044-1049|note=[Speckit sequence and parallel worktree safeguards]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019fdd94-c3b1-7343-9d48-05ca4d21afae
019fe851-db7d-79a1-b895-f61bbf4ca463
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>/root/ui_audit (McClintock)</code> — 492.8 MiB — closed</summary>

- Session: `019fef92-8e35-7081-a15b-699804b49e5b`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T06:46:27.125Z`
- Source log: `rollout-2026-08-11T09-46-27-019fef92-8e35-7081-a15b-699804b49e5b.jsonl`

<pre>
Skill forward testi genel olarak geçti. Tetikleme açıklığı, DOU’ya özel anti-slop yönü ve temel rol sınırları güçlü; dosyalarda çelişki veya açıkça tehlikeli talimat yok. Üç senaryoda da dosya değiştirmedim.

| Test istemi | Sonuç | Skill’in doğru kararı | Açık boşluk |
|---|---|---|---|
| Öğrenci dashboard’u | Geçti | Tek baskın çalışma eylemi, kompakt gerçek ilerleme, sunucu kaynaklı sınav kilidi, sahte GPA/streak/başarı verisi yok | “Sıradaki çalışma” API’de tanımlı değilse istemci bunu tahmin edebilir |
| Eğitmen ders ana sayfası | Geçti | Taslak onayı, kaynak sağlığı ve blueprint durumu öne çıkar; yayınlanmamış AI sorusunu yayınlanmış göstermez; üç eşit kartı reddeder | “Sınıf trendleri” mevcut endpoint ile doğrulanmadan üretilmemeli; aggregate ve ders-kapsamlı olmalı |
| Bilgi İşlem admin konsolu | Güçlü geçti | Prompt, yanıt, chunk, tam e-posta, UUID, stack trace ve öğrenci sıralamasını reddeder; admini akademik süper kullanıcıya dönüştürmez; salt okunur konsol önerir | Yetki çözülmeden admin isteği atılmaması ve gizli UI’ın yetkilendirme sayılmaması daha açık yazılmalı |

## Güçlü taraflar

- Açıklama alanı dashboard, profil, admin, course shell, auth, responsive, dark mode ve anti-slop işlerini net biçimde tetikliyor; backend ve yeni agent işlerini doğru şekilde dışlıyor. [SKILL.md]($HOME/.codex/skills/dou-synapse-product-ui/SKILL.md:3)
- Worktree, sahiplik, tasarım belgesi, Speckit ve gerçek tarayıcı kanıtını zorunlu kılması uygulanabilir ve mevcut paralel çalışma modeline uygun. [SKILL.md]($HOME/.codex/skills/dou-synapse-product-ui/SKILL.md:10)
- Kurs rolü, sınav kilidi, admin ayrımı, gizlilik, citation ve duplicate request sınırları iyi korunuyor. [SKILL.md]($HOME/.codex/skills/dou-synapse-product-ui/SKILL.md:29)
- Anti-slop kontrolü genel estetik öğütler yerine kart matrisi, pill navigasyon, dört eşit metrik ve generic AI kopyası gibi gerçek repo sorunlarını hedefliyor. [SKILL.md]($HOME/.codex/skills/dou-synapse-product-ui/SKILL.md:50)
- Admin ekranını “akademik süper kullanıcı” değil Bilgi İşlem konsolu olarak tanımlaması özellikle doğru. [screen-patterns.md]($HOME/.codex/skills/dou-synapse-product-ui/references/screen-patterns.md:20)

## Önerilen üç küçük sertleştirme

1. Öğrenci bölümüne şu kural eklenmeli:

   &gt; Tek bir sonraki çalışma eylemi, açık bir sunucu alanı veya şartnamede tanımlı deterministik seçim kuralı olmadan istemcide tahmin edilmez.

2. Eğitmen bölümüne şu sınır eklenmeli:

   &gt; Sınıf eğilimleri yalnız mevcut endpoint tarafından sağlanan, ders-kapsamlı aggregate veriden gösterilir; öğrenci sıralaması veya bireysel akademik kayıt türetilmez.

3. Admin sözleşmesine şu fail-closed kural eklenmeli:

   &gt; Sunucu platform-admin yetkisini doğrulamadan admin içeriği mount edilmez ve admin veri isteği atılmaz. Navigasyonu gizlemek yetkilendirme değildir; doğrudan rota ve API reddi test edilmelidir.

Ek operasyonel not: güncel çalışma alanında boş disk yaklaşık 100 MiB seviyesinde. Skill’in uygulama öncesi kontrol listesine disk/runtime uygunluğu eklenmesi, build veya yeni worktree’nin yarıda kalmasını önler.
</pre>

</details>

<details>
<summary><code>/root/page_redesign (Cicero)</code> — 844.8 MiB — closed</summary>

- Session: `019fefa2-0e0f-78b1-88cf-948d861423b8`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T07:03:22.895Z`
- Source log: `rollout-2026-08-11T10-03-22-019fefa2-0e0f-78b1-88cf-948d861423b8.jsonl`

<pre>
Metin düzeltildi: “Bu derste sıradaki adım” yerine “Bu derste çalışma yolları” kullanılıyor.

- Rol tabanlı görünüm korundu.
- Sunucuda olmayan öneri/öncelik iddiası kaldırıldı.
- TypeScript ve diff kontrolü temiz.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.4 MiB — closed</summary>

- Session: `019fefa2-0ec6-7a62-8cd8-14b9bf215da3`
- Parent: `019fefa2-0e0f-78b1-88cf-948d861423b8`
- Started: `2026-08-11T07:03:23.078Z`
- Source log: `rollout-2026-08-11T10-03-23-019fefa2-0ec6-7a62-8cd8-14b9bf215da3.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/ui_audit/student_prompt (Hilbert)</code> — 380.6 MiB — closed</summary>

- Session: `019fefa2-364a-7bd3-b379-601c9a1f6166`
- Parent: `019fef92-8e35-7081-a15b-699804b49e5b`
- Started: `2026-08-11T07:03:33.195Z`
- Source log: `rollout-2026-08-11T10-03-33-019fefa2-364a-7bd3-b379-601c9a1f6166.jsonl`

<pre>
Kısa hüküm: Skill bu istemi doğru tetikliyor ve doğru ürün yönünü veriyor. Ancak uygulamaya başlamadan önce iki blocker var: “sıradaki çalışma” kararının veri kaynağı tanımsız ve paralel frontend sahipliği doğrulanamıyor.

## Tetikleme ve süreç

- İstem doğrudan öğrenci dashboard’u, ilerleme, ders kartları ve sınav kilidi içerdiği için `dou-synapse-product-ui` doğru skill.
- Doğru yorum “renkli SaaS dashboard” değil, role uygun hiyerarşi: tek baskın çalışma eylemi, kompakt ilerleme, sonra ders bağlamı.
- Yetkili worktree şu anda temiz: `design/product-ui-refresh`, SHA `fc5bd596…`.
- Aktif Speckit hâlâ `005-role-aware-course-agent`; UI yenilemesi için ayrı acceptance kriteri henüz görünmüyor.
- `feature/role-admin-panels` worktree’si mevcut ancak `.git` okuması zaman aşımına uğradı. Sahiplik doğrulanmadan ortak dashboard dosyalarına dokunulmamalı.
- Diskte yalnız yaklaşık **100 MiB** var; build, bağımlılık kurulumu veya yeni worktree şu anda güvenli değil.

## Rol ve güvenlik değerlendirmesi

Skill kritik sözleşmeleri doğru yakalıyor:

- Rol ders bazında sunucudan geliyor; kullanıcı bir derste öğrenci, başka derste eğitmen olabilir. Global “öğrenci modu” türetilmemeli. [spec.md]($HOME/code/dou-ai-sdlc-excellence/specs/003-product-portal/spec.md:181)
- Dashboard tek `/dashboard` isteği kullanıyor. Görsel değişiklik için ikinci ders/rol isteği eklenmemeli. [dashboard.ts]($HOME/code/dou-ai-sdlc-excellence/apps/web/lib/dashboard.ts:47)
- Sınav kilidinde ana eylem zaten sunucu alanlarından `Sınava dön` oluyor ve Asistan hızlı bağlantısı kaldırılıyor. [dashboard.ts]($HOME/code/dou-ai-sdlc-excellence/apps/web/lib/dashboard.ts:51)
- Bunun kırılabilir testi mevcut. [dashboard.test.ts]($HOME/code/dou-ai-sdlc-excellence/apps/web/lib/dashboard.test.ts:38)
- Chatbox persona bilgisini dashboard rolünden tahmin etmiyor; açıldığında sunucudan availability alıyor. Bu lazy davranış ve duplicate-fetch yasağı korunmalı. [course-assistant.tsx]($HOME/code/dou-ai-sdlc-excellence/apps/web/components/course-assistant/course-assistant.tsx:53)
- Kilitli durumda composer çizilmemesi ve doğrudan API reddi E2E sözleşmesi. [flows.spec.ts]($HOME/code/dou-ai-sdlc-excellence/apps/web/e2e/flows.spec.ts:813)

## Anti-slop yönü

Mevcut iki açık hedef:

- Dashboard dört eşit metrikle başlıyor. [portal-metrics.tsx]($HOME/code/dou-ai-sdlc-excellence/apps/web/components/portal/portal-metrics.tsx:11)
- Ders kartı aynı kutuda metrikler, chatbox, hızlı araçlar, ana eylem, tarih ve uyarıları topluyor. [dashboard-course-card.tsx]($HOME/code/dou-ai-sdlc-excellence/apps/web/components/portal/dashboard-course-card.tsx:21)

Doğru dönüşüm:

1. Üstte tek baskın çalışma eylemi.
2. Altında 2–3 gerçek, kompakt ilerleme göstergesi.
3. Öğrenci ders kartında “Çalışmaya devam et” veya “Sınava dön” görsel olarak birincil.
4. İkincil araçlar düz bağlantı grubu olarak kalmalı.
5. Doğuş kırmızısı tek vurgu; gradient, neon, confetti, streak, XP ve sahte başarı rozeti yok.
6. `mastery_score=null` durumunda gerçek dışı yüzde/progress bar üretilmemeli.

## Skill’in yakalamadığı önemli boşluk

“Sıradaki çalışma aksiyonu” API’de hazır bir karar değil. Mevcut veri yalnız şunları taşıyor:

- ders rolü,
- soru ve sınav sayıları,
- nullable mastery,
- son etkinlik,
- sınav kilidi.

[dashboard.ts]($HOME/code/dou-ai-sdlc-excellence/apps/web/lib/dashboard.ts:18)

Dolayısıyla arayüz:

- ilk dersi keyfî seçmemeli,
- son etkinliği “önerilen ders” diye yorumlamamalı,
- düşük mastery’yi otomatik çalışma önerisine çevirmemeli.

Güvenli seçenekler:

- Yalnız her ders kartındaki mevcut server-derived ana eylemi büyütmek, veya
- Ayrı şartnamede deterministik `next_action` kuralı tanımlayıp bunu backend projeksiyonundan döndürmek.

Aktif sınav varsa onun `Sınava dön` eylemini öne almak makul; birden çok aktif sınav gibi uç durum yine şartnameye yazılmalı.

## Uygulanabilir en küçük dilim

- `DESIGN.md`: yeni dashboard hiyerarşisini önce kaydet.
- `app/dashboard/page.tsx`: dört eşit metriği baskın aksiyon + kompakt bağlama dönüştür.
- `components/portal/dashboard-course-card.tsx`: öğrenci kartı kompozisyonunu sadeleştir.
- `components/portal/portal-metrics.tsx`: kart matrisi yerine veri şeridi.
- `lib/dashboard.ts` ve testi: ancak seçme kuralı açıkça kararlaştırılırsa saf yardımcı ekle.
- `e2e/portal.spec.ts`: öğrenci, karma rol, null mastery, kilitli/kilitsiz, 375 px, koyu tema ve tek dashboard isteği.

Sonuç olarak skill forward testi **geçiyor**, fakat `screen-patterns.md` içine şu ek kural yararlı olur: “Tek bir sonraki çalışma eylemi, açık server alanı veya şartnamede tanımlı deterministik seçim kuralı olmadan istemcide tahmin edilmez.”
</pre>

</details>

<details>
<summary><code>/root/portal_redesign (Boole)</code> — 842.9 MiB — closed</summary>

- Session: `019fefad-4fad-73a1-938f-68baa1e8cd5f`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T07:15:40.589Z`
- Source log: `rollout-2026-08-11T10-15-40-019fefad-4fad-73a1-938f-68baa1e8cd5f.jsonl`

<pre>
Portal anti-slop redesign tamamlandı; commit veya push yapılmadı.

- Dashboard, profil ve Bilgi İşlem ekranları rol odaklı editoryal düzene geçirildi.
- AppShell, PageHeader, Card ve metrik sistemi güncellendi.
- Tek Doğuş kırmızısı, koyu tema, erişilebilirlik ve mevcut güvenlik sözleşmeleri korundu.
- Diğer lane’in `app/page.tsx` ve ders ana sayfasına dokunulmadı.

Doğrulama:

- Frontend testleri: 322 geçti
- TypeScript: temiz
- Açık/koyu tema kontrast kapısı: temiz
- `git diff --check`: temiz
- Build, E2E ve tarayıcı turu: koşulmadı; entegrasyon kapısına bırakıldı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.4 MiB — closed</summary>

- Session: `019fefad-5103-78d0-b1d3-a65d649028b1`
- Parent: `019fefad-4fad-73a1-938f-68baa1e8cd5f`
- Started: `2026-08-11T07:15:40.931Z`
- Source log: `rollout-2026-08-11T10-15-40-019fefad-5103-78d0-b1d3-a65d649028b1.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/redesign_review (Dewey)</code> — 818.9 MiB — closed</summary>

- Session: `019fefbe-489e-7fc3-a759-bda55a6a9e1a`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T07:34:12.895Z`
- Source log: `rollout-2026-08-11T10-34-12-019fefbe-489e-7fc3-a759-bda55a6a9e1a.jsonl`

<pre>
12 dosyalık son tasarım farkını yalnızca okuyarak; rol sınırları, erişilebilirlik, doğru ürün iddiaları ve mobil/karanlık tema açısından denetliyorum.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.2 MiB — closed</summary>

- Session: `019fefbe-4959-7db2-84e0-2ca8f4f24396`
- Parent: `019fefbe-489e-7fc3-a759-bda55a6a9e1a`
- Started: `2026-08-11T07:34:13.082Z`
- Source log: `rollout-2026-08-11T10-34-13-019fefbe-4959-7db2-84e0-2ca8f4f24396.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/readme_feature_audit (Herschel)</code> — 914.7 MiB — closed</summary>

- Session: `019fefdd-99f7-7592-b922-c3b317134a9a`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T08:08:25.337Z`
- Source log: `rollout-2026-08-11T11-08-25-019fefdd-99f7-7592-b922-c3b317134a9a.jsonl`

<pre>
NO-GO: P0/P1 yok, ancak üç P2 var.

1. Gün sınırı testi flake olabilir. [RLS betiği]($HOME/code/dou-ai-sdlc-excellence/supabase/tests/rls_role_aware_agent_mutation_check.sh:231) `created_at` değerini iki dakika geriye alıyor; İstanbul’da 00:00–00:02 arasında kayıt önceki gün kotasına düşer.

2. T112 kapsamı abartılı. [tasks.md]($HOME/code/dou-ai-sdlc-excellence/specs/005-role-aware-course-agent/tasks.md:101) membership, quota ve concurrency mutasyonlarının ayrı ayrı yapıldığını söylüyor; betikte membership ayrı mutasyona uğramıyor, quota ve concurrency tek mutasyonda birleşiyor.

3. Kanıt zinciri çelişkili. Belgeler 882/325 ve Playwright 35/35/T404 DONE derken [evidence JSON]($HOME/code/dou-ai-sdlc-excellence/.ai/evidence/005-role-aware-course-agent-local.json:2) hâlâ `SELF`, 879/322 ve runtime Playwright `not_run` içeriyor.

Privacy API/schema/test değişikliklerinde P0–P2 güvenlik açığı görmedim; aktif sınav kilidi korunuyor, ham operasyon satırları export edilmiyor ve iki cascade yolu gerçek PostgreSQL testiyle kapsanıyor.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.3 MiB — closed</summary>

- Session: `019fefdd-9ae0-7681-a4d3-3b77c132b7c6`
- Parent: `019fefdd-99f7-7592-b922-c3b317134a9a`
- Started: `2026-08-11T08:08:25.568Z`
- Source log: `rollout-2026-08-11T11-08-25-019fefdd-9ae0-7681-a4d3-3b77c132b7c6.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/readme_journey_audit (James)</code> — 914.5 MiB — closed</summary>

- Session: `019fefde-4cf8-7f33-aff1-89cb392db279`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T08:09:11.161Z`
- Source log: `rollout-2026-08-11T11-09-11-019fefde-4cf8-7f33-aff1-89cb392db279.jsonl`

<pre>
README içeriği esasen doğru; ancak depo geneli için henüz **GO değil**.

Tek blocker, AI-SDLC kanıt kaydı:

- `.ai/evidence/005-role-aware-course-agent-local.json:12,16` hâlâ **879/322** yazıyor.
- Aynı dosyanın `:47` satırı Playwright’ı `not_run` gösteriyor.
- `.ai/changes/005-role-aware-course-agent.json:194-219` bu bayat raporu PASS ve 879/322 eşikleriyle bağlıyor.
- Bunlar README’deki **882/325/35** ve T112/T113/T404 kanıtlarıyla çelişiyor.

Branch durumu, CI/production ayrımı ve açık T217/T307/T309/T407/T408/T410 anlatımı doğru. İlgili belgelerde `git diff --check` temiz. Kanıt JSON’u ile dossier hash/metrikleri güncellenip doğrulayıcı tekrar çalıştırıldığında **GO** verilebilir.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.2 MiB — closed</summary>

- Session: `019fefde-4db7-7072-964d-cf2c0594ec3a`
- Parent: `019fefde-4cf8-7f33-aff1-89cb392db279`
- Started: `2026-08-11T08:09:11.351Z`
- Source log: `rollout-2026-08-11T11-09-11-019fefde-4db7-7072-964d-cf2c0594ec3a.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/readme_truth_review (Huygens)</code> — 882.8 MiB — closed</summary>

- Session: `019fefdf-080f-7970-b1e0-dae494e54ef7`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T08:09:59.062Z`
- Source log: `rollout-2026-08-11T11-09-59-019fefdf-080f-7970-b1e0-dae494e54ef7.jsonl`

<pre>
Salt-okunur audit sonucu: yerel çalışma kaybolmamış ve yarım merge yok; fakat henüz teslim edilmiş de değil.

## Mevcut durum

- Dal: `design/product-ui-refresh`
- HEAD: `fc5bd59`
- Dal, `origin/005-role-aware-course-agent` ile birebir aynı.
- `origin/main`den 9 commit ileride.
- Design dalının upstream’i yok.
- Dirty kapsam: README + DESIGN + 11 web dosyası, toplam 13 dosya.
- Untracked dosya, unmerged index, merge markerı, conflict veya `git diff --check` sorunu yok.
- Relative README bağlantıları ve tarihsel ekran dosyaları mevcut.
- Secret veya cihaz yolu sızıntısı görülmedi.
- Disk: yalnız yaklaşık 3.1 GiB boş, filesystem %99 dolu.

## Kritik kapatılacak bulgular

1. Ders ana sayfasındaki `ProductRoles`, 005 sözleşmesiyle çelişiyor.

   [page.tsx]($HOME/code/dou-ai-sdlc-excellence/apps/web/app/courses/[courseId]/page.tsx:137) hâlâ `CourseGPT`, `Exam Mentor`, `Class Assistant` üçlüsünü “AI rolü” gibi kuruyor. 005’in gerçek sunucu profilleri ise yalnız `Ders Koçu` ve `Eğitmen Asistanı`.

   Aynı sayfada `CourseNav` gerçek availability/kilit durumunu biliyor ve aktif sınavda Asistan sekmesini kapatıyor; `ProductRoles` ise chat linkini yine öne çıkarıyor. API güvenliği delinmiyor, ancak kullanıcı arayüzü iki farklı gerçeklik anlatıyor. Commit öncesi aynı server-derived identity ve lock kaynağına bağlanmalı veya tamamen nötr “çalışma yolları” olarak yeniden adlandırılmalı.

2. README mimari oku yanlış.

   [README.md]($HOME/code/dou-ai-sdlc-excellence/README.md:356) `WEB --&gt; ST` diyor. Dosya yükleme web’den API’ye gider; doğru ilişki `API --&gt; ST`.

3. README quickstart çalışma dizini kırılabilir.

   API adımında `cd apps/api` yapıldıktan sonra sonraki blok `cd apps/web` diyor. Aynı terminalde uygulanırsa `apps/api/apps/web` aranır. Her blok repo kökünden bağımsız çalışmalı veya subshell kullanılmalı.

4. Klavye erişilebilirliği iddiası henüz kapanmış değil.

   Admin sekmeleri `role=&quot;tab&quot;` kullanıyor fakat arrow-key/roving-tabindex davranışı yok. Ayrıca profil linkinin erişilebilir adı yalnız kullanıcı adı; `Profil: &lt;ad&gt;` daha açıklayıcı olur. 005 içindeki T307 zaten açık.

5. Gereksiz bileşen yüzeyi var.

   [ui.tsx]($HOME/code/dou-ai-sdlc-excellence/apps/web/components/ui.tsx:77) `Card` için `plain` ve üç padding seçeneği ekliyor; yalnız `soft` gerçekten kullanılıyor. Kullanılmayan API seçenekleri çıkarılabilir.

## Kanıt durumu

- `.next/BUILD_ID`, bütün UI dosyalarından sonra üretilmiş. Dolayısıyla güncel UI ağacı için başarılı yerel build artefaktı güçlü biçimde mevcut.
- Buna karşın design değişikliklerinde test dosyası değişmedi.
- 322 test, ayrı typecheck ve contrast koşusunun kalıcı log/artefaktı yok.
- Playwright raporu veya güncel redesign ekran görüntüsü yok.
- Hiçbir dev server şu an ayakta değil.
- İnteraktif browser doğrulaması bu audit açısından `KOŞULMADI`.
- Mevcut E2E paketi mobil 375px, dark mode, dashboard/profile/admin ve admin ağ sırasını kapsıyor; ancak bu dirty diff üzerinde çalıştırılmamış.
- `docs_check` statik sayıları okudu; audit ortamındaki PATH’te `uv`/`bun` bulunmadığı için backend/frontend ölçüm adımları `KOŞULMADI`. Bu ürün hatası değil ama merge kanıtı da sayılamaz.

## 005’te açık kalan gerçek görevler

T112, T113, T217, T307, T309, T402, T404, T407, T408, T410 ve T501–T507 hâlâ açık. Ayrıca T703–T705 nedeniyle PR, CI gözlemi, merge ve merge-sonrası doğrulama yapılmadı.

## Güvenli kapanış sırası

1. Eski üçlü rol/lock UX çelişkisini düzelt.
2. Bu davranış için odaklı test ekle.
3. Frontend test + typecheck + contrast + build çalıştır.
4. Öğrenci/eğitmen/admin ile 375px ve desktop, light/dark, keyboard, reduced-motion ve network turu yap.
5. Benzersiz test DB ile seri gerçek-API E2E çalıştır.
6. `docs_check` ve `git diff --check` çalıştır.
7. `DESIGN.md + UI` ve `README.md` için iki küçük commit oluştur.
8. `design/product-ui-refresh` dalını upstream ile pushla.
9. En temiz PR: `design/product-ui-refresh → 005-role-aware-course-agent`; ardından tamamlanan 005’i main’e taşı.

Şu anda “kod kaybolmadı”, “build artefaktı var” ve “diff hijyeni temiz” denebilir. “UI işi tamamlandı, testli, tarayıcıda doğrulandı ve pushlandı” henüz denemez.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.3 MiB — closed</summary>

- Session: `019feff1-475d-7890-b963-8588f289c175`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T08:29:54.910Z`
- Source log: `rollout-2026-08-11T11-29-54-019feff1-475d-7890-b963-8588f289c175.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>guardian</code> — 3.2 MiB — closed</summary>

- Session: `019ff026-9f4a-7480-ae85-9a4aa2585d9d`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T09:28:10.828Z`
- Source log: `rollout-2026-08-11T12-28-10-019ff026-9f4a-7480-ae85-9a4aa2585d9d.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/final_e2e_prep (Einstein)</code> — 291.0 MiB — closed</summary>

- Session: `019ff03f-1fb8-7e41-9b92-7a8edd916c11`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T09:54:56.569Z`
- Source log: `rollout-2026-08-11T12-54-56-019ff03f-1fb8-7e41-9b92-7a8edd916c11.jsonl`

<pre>
GO.

- 35/35 seri gerçek-API Playwright, kalıntı 0/0 ve korunan UUID karşı-kontrolü mevcut cleanup sözleşmesiyle uyumlu.
- Quickstart ortam değişkenlerinde veya Playwright komutunda drift yok.
- “Gerçek API” ifadesi gerçek FastAPI/PostgreSQL/tarayıcı akışını anlatıyor; belgeler gerçek provider, staging ve hosting’in doğrulanmadığını açıkça koruyor.
- Yanlış production iddiası yok.
- İlgili diff whitespace açısından temiz.

Tek isteğe bağlı iyileştirme: quickstart’taki “sabit UUID” ifadesinin yanına literal `c3b76077-20de-47e5-9fe1-4e770ffa64d2` yazılabilir; bloklayıcı değil.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.2 MiB — closed</summary>

- Session: `019ff03f-2009-7481-b400-41d8c4f92f09`
- Parent: `019ff03f-1fb8-7e41-9b92-7a8edd916c11`
- Started: `2026-08-11T09:54:56.649Z`
- Source log: `rollout-2026-08-11T12-54-56-019ff03f-2009-7481-b400-41d8c4f92f09.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/fix_ai_lineage (Bernoulli)</code> — 1049.5 MiB — closed</summary>

- Session: `019ff0a3-abd6-7c40-8d25-fc7298fa4032`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T11:44:46.038Z`
- Source log: `rollout-2026-08-11T14-44-46-019ff0a3-abd6-7c40-8d25-fc7298fa4032.jsonl`

<pre>
Blocker A kapandı.

Değiştirilen/yeni kanıt dosyaları:

- `.ai/changes/005-role-aware-course-agent-r3.json`
- `.ai/evidence/005-role-aware-course-agent-main-integration.json`
- `.ai/evidence/main-integration-validator-tests.json`
- `.ai/evidence/main-integration-validator-full-suite.json`
- `.ai/evidence/main-integration-rls-mutations.json`

Kanıt:

- Validator tam paketi: **51/51**
- Yeni lineage testleri: **4/4**
- RLS mutasyonları: **11/11**
- Exact `main` tabanlı geçici aday `5d5e366a...`: `AI_SDLC_CHECK=PASS`
- JSON ve `git diff --check`: temiz
- Eski dossier/evidence dosyaları değiştirilmedi; append-only geçmiş korundu.
- Önceki başarısız entegrasyon sonucu negatif kanıt olarak tutuldu.
- Commit veya push yapılmadı.

Kalan tek zorunlu adım: gerçek commit üretildikten sonra SHA değişeceği için aynı exact validator komutu CI’da yeniden çalışmalı. Disk hâlâ kritik derecede dolu olduğundan geniş yerel paketleri tekrar çalıştırmak riskli.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.5 MiB — closed</summary>

- Session: `019ff0a3-ac49-7f32-a021-0eb625166629`
- Parent: `019ff0a3-abd6-7c40-8d25-fc7298fa4032`
- Started: `2026-08-11T11:44:46.154Z`
- Source log: `rollout-2026-08-11T14-44-46-019ff0a3-ac49-7f32-a021-0eb625166629.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/expand_t112_mutations (Newton)</code> — 1049.2 MiB — closed</summary>

- Session: `019ff0a4-459b-7ae1-bade-9098bb02971e`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T11:45:25.404Z`
- Source log: `rollout-2026-08-11T14-45-25-019ff0a4-459b-7ae1-bade-9098bb02971e.jsonl`

<pre>
Blocker B, yalnızca [RLS mutasyon betiğinde](/private/tmp/dou-evidence-fix.r2CC2o/repo/supabase/tests/rls_role_aware_agent_mutation_check.sh) giderildi.

Yeni ayrı mutasyonlar:

1. Üye olmayan kullanıcının token rezervasyonu
2. Audience immutable trigger
3. Sahte instructor session
4. Cache cross-audience SELECT
5. Cache cross-audience INSERT
6. Doğrudan tablo GRANT
7. PUBLIC helper EXECUTE
8. Advisory-lock kaldırılınca atomik yarış overshoot
9. Yalnız günlük kota kaldırılması
10. Yalnız concurrency sınırı kaldırılması
11. Cross-user privacy okuması

Kanıt:

- Referans: 8 kapalı sınır + 3 kota davranışı geçti.
- Mutasyonlar: **11/11 sızıntı yakalandı**, exit `0`.
- Geçici DB kalıntısı: **0**.
- Son dosyada `bash -n` ve `git diff --check`: temiz.
- Yeni bağımlılık veya çalışma kopyası oluşturulmadı.
- Commit/push yapılmadı.

`/me/export` assessment-user lock SQL migrasyonunda bulunmadığından betikte hâlâ dürüstçe kapsam dışı; sahte SQL kanıtına çevrilmedi. Bu test mevcut uygulama testlerinde kalıyor.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.4 MiB — closed</summary>

- Session: `019ff0a4-4659-74b3-b936-657e220e65da`
- Parent: `019ff0a4-459b-7ae1-bade-9098bb02971e`
- Started: `2026-08-11T11:45:25.594Z`
- Source log: `rollout-2026-08-11T14-45-25-019ff0a4-4659-74b3-b936-657e220e65da.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/fix_docs_truth (Carson)</code> — 1113.2 MiB — closed</summary>

- Session: `019ff0a4-fb2b-7792-86f4-939f49e7ded3`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T11:46:11.883Z`
- Source log: `rollout-2026-08-11T14-46-11-019ff0a4-fb2b-7792-86f4-939f49e7ded3.jsonl`

<pre>
Sorumluluk alanımdaki docs-truth düzeltmeleri tamamlandı; commit/push yapmadım.

Değişen dosyalar:

- `README.md`
- `docs/security.md`
- `specs/005-role-aware-course-agent/spec.md`
- `scripts/docs_check.mjs`

Sonuçlar:

- Güncel 882/325/35 değerleri canlı kaynak tablosunda kaldı.
- 9 ve 11 Ağustos’a ait sabit koşum sonuçları tarihsel işaretlere çevrildi.
- Mypy değeri 59’dan güncel 92 dosyaya ayrıldı.
- Belge kapısı artık tarihli paragrafta canlı sayaç kullanımını ve işaretsiz mypy dosya sayısını reddediyor.
- Backend koleksiyonu: 882 test.
- Mypy: temiz, 92 dosya.
- `node --check` ve `git diff --check`: geçti.

Kalan gerçek sapmalar benim dosya sahipliğimin dışında:

- `PLAN.md:178`
- `docs/deployment.md:101`
- `specs/002-production-hardening/quickstart.md:17,18,128`
- `specs/005-role-aware-course-agent/tasks.md:199`
- `docs/test-report.md:580` — tarihsel `59 dosya` canlıymış gibi yazılmış

Tarihsel Git kanıtı:

- 002 US1 sonrası: backend 677, frontend 211, frontend test dosyası 8
- 9 Ağustos test-report baseline: backend 473, mypy 59

İzole worktree’de `uv`, yerel `node_modules` ve Playwright bulunmadığı için tam `docs_check` ölçümü burada yeşil olamaz; ayrıca yukarıdaki dış-sahiplik sapmalarını bilinçli olarak kırmızı gösteriyor. Frontend’i başka worktree’nin bağımlılıklarıyla çalıştırma denemesi modül çözümlemesinde kaldı; 325 için yeni bir başarı iddiası üretmedim.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.3 MiB — closed</summary>

- Session: `019ff0a4-fbdc-7c53-aaf9-f48ac3266b64`
- Parent: `019ff0a4-fb2b-7792-86f4-939f49e7ded3`
- Started: `2026-08-11T11:46:12.060Z`
- Source log: `rollout-2026-08-11T14-46-12-019ff0a4-fbdc-7c53-aaf9-f48ac3266b64.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/notification_discovery (Beauvoir)</code> — 1138.1 MiB — closed</summary>

- Session: `019ff0ce-d597-7191-b408-971e021ddd89`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T12:31:54.776Z`
- Source log: `rollout-2026-08-11T15-31-54-019ff0ce-d597-7191-b408-971e021ddd89.jsonl`

<pre>
Salt okunur keşif tamamlandı; hiçbir dosyayı değiştirmedim.

## Net hüküm

Projede gerçek bir bildirim/duyuru modeli, API’si veya bildirim kutusu yok. Önceki portal şartnamesi sahte duyuruyu bilinçli olarak yasaklıyor; veri kaynağı ve sahiplik olmadan yapılmaması kararı var ([research.md:98](/private/tmp/dou-evidence-fix.r2CC2o/repo/specs/003-product-portal/research.md:98), [data-model.md:429](/private/tmp/dou-evidence-fix.r2CC2o/repo/specs/003-product-portal/data-model.md:429)).

Kullanıcının yeni talebi bu eksik sahipliği tanımlıyor:

- Bilgi İşlem, platform duyurusunun sahibi.
- Ders eğitmeni, yalnız kendi dersinin duyurusunun sahibi.
- Kullanıcı, yalnız kendisine görünür duyuruları okur ve okundu işaretler.

Bu nedenle doğru yeni özellik: **`specs/006-notification-center`**. Mevcut adayda migration’lar `0001`–`0015`; entegrasyondan hemen önce tekrar kontrol edilmek şartıyla önerilen dosya **`0016_notifications.sql`**.

## En küçük güvenli dikey dilim

### 1. Kullanıcı bildirim kutusu

- Üst çubukta bildirim düğmesi, okunmamış sayı rozeti ve son beş kayıt.
- `/notifications` sayfasında keyset sayfalı tam kutu.
- Tek API yanıtı hem kayıtları hem `unread_count` değerini taşımalı; ayrı sayaç isteği yapılmamalı.
- Masaüstünde sabit, erişilebilir açılır panel; mobilde tam genişlikte panel.
- Kaynak etiketi yalnız `Bilgi İşlem` veya ders kodu.
- “Okunmadı” yalnız renkle değil metin/işaretle belirtilmeli.
- HTML/Markdown/ek/link yok; ilk sürüm yalnız kaçışlanmış düz metin.
- Harici e-posta, mobil push ve WebSocket yok. İlk yükleme, pencere tekrar odaklanınca yenileme ve görünür sekmede seyrek yenileme yeterli.

### 2. Bilgi İşlem gönderim alanı

Ayrı rota: `/admin/announcements`.

Hedef seçenekleri yalnız:

- `Tüm kullanıcılar`
- `Yalnız Bilgi İşlem yöneticileri`

Global “öğrenciler” veya “eğitmenler” hedefi verilmemeli; rol sistem genelinde değil ders bazında olduğundan aynı kullanıcı iki rolü birden taşıyabilir.

Admin arayüzü, mevcut profil cevabı platform yetkisini doğrulamadan mount olmamalı veya veri isteği başlatmamalı. Mevcut admin yüzeyi bunu doğru yapıyor ([admin/page.tsx:42](/private/tmp/dou-evidence-fix.r2CC2o/repo/apps/web/app/admin/page.tsx:42)).

### 3. Eğitmen gönderim alanı

Ayrı rota: `/courses/{course_id}/announcements`.

Hedef seçenekleri yalnız:

- `Dersin tüm aktif katılımcıları`
- `Yalnız bu dersteki öğrenciler`

Form yalnız sunucudan o ders için `instructor` rolü geldikten sonra çizilmeli. Öğrenci aynı sayfada salt okunur ders arşivini görür. CourseNav’a “Duyurular” sekmesi eklenir.

## Yetki matrisi

| İşlem | Öğrenci | Aynı ders eğitmeni | Başka ders eğitmeni | Üyeliksiz platform admin |
|---|---:|---:|---:|---:|
| Platform duyurusu gönder | Hayır | Hayır | Hayır | Evet |
| Ders duyurusu gönder | Hayır | Evet | Hayır | Hayır |
| Platform-genel duyuru oku | Evet | Evet | Evet | Evet |
| Admin-içi duyuru oku | Hayır | Hayır* | Hayır* | Evet |
| Ders duyurusu oku | Aktif üyeyse | Aktif üyeyse | Hayır | Hayır |
| Başkasının okundu kaydını gör | Hayır | Hayır | Hayır | Hayır |

\* Kişi ayrıca platform admin ise görür; eğitmenlik tek başına yetmez.

Temel değişmez:

- Platform admin yetkisi course membership üretmez.
- Eğitmenlik platform yetkisi üretmez.
- Hem admin hem eğitmen olan kişi, her uçta o uç için gereken ayrı yetkiyle değerlendirilir.
- Platform admin bir ders duyurusu gönderecekse ayrıca o dersin aktif eğitmeni olmalıdır.

Mevcut backend ayrımı buna hazır: `CourseInstructorDep` ve `PlatformAdminDep` ayrı eksenlerde ([deps.py:127](/private/tmp/dou-evidence-fix.r2CC2o/repo/apps/api/app/api/deps.py:127), [deps.py:152](/private/tmp/dou-evidence-fix.r2CC2o/repo/apps/api/app/api/deps.py:152)).

## Veri modeli

`announcements`

- `id`
- `scope`: `platform | course`
- `audience`: `all_users | platform_admins | all_members | students`
- `course_id`, platform scope’ta `NULL`
- `title`, en fazla 120 karakter
- `body`, en fazla 2.000–4.000 karakter, düz metin
- `created_by`
- `published_at`
- `expires_at`
- `withdrawn_at`
- `withdrawn_by`
- `created_at`

SQL CHECK:

- `platform` yalnız `course_id IS NULL` ve `all_users/platform_admins`
- `course` yalnız `course_id IS NOT NULL` ve `all_members/students`
- `expires_at &gt; published_at`
- ilk insert sırasında withdraw alanları `NULL`

`announcement_reads`

- `announcement_id`
- `user_id`
- `read_at`
- birleşik PK `(announcement_id, user_id)`
- profil silinince receipt cascade
- announcement silinmez; yalnız geri çekilir

Yayınlandıktan sonra başlık/gövde düzenlenmemeli. Yanlış içerik sessizce değiştirilmek yerine geri çekilip yeni duyuru oluşturulmalı. Böylece kullanıcının gördüğü şeyin geçmişi değişmez.

## API sözleşmesi

Kullanıcı:

- `GET /me/notifications?limit=&amp;cursor=&amp;status=all|unread`
- `PUT /me/notifications/{announcement_id}/read`

Ders:

- `GET /courses/{course_id}/announcements`
- `POST /courses/{course_id}/announcements`
- `POST /courses/{course_id}/announcements/{announcement_id}/withdraw`

Bilgi İşlem:

- `GET /admin/announcements`
- `POST /admin/announcements`
- `POST /admin/announcements/{announcement_id}/withdraw`

Bütün liste uçları ürünün mevcut `{items, next_cursor}` keyset zarfını kullanmalı. Offset/total admin istisnasını bildirim kutusuna taşımamak gerekir.

## RLS ve grant tasarımı

`announcements` ve `announcement_reads` için `ENABLE` + `FORCE RLS`.

- Platform insert: `app.is_platform_admin()`.
- Ders insert: `app.is_instructor(course_id)`.
- Platform görünürlük: tüm kullanıcılar veya yalnız `app.is_platform_admin()`.
- Ders görünürlük: aktif course membership ve audience-role eşleşmesi.
- Receipt: yalnız `user_id = app.current_user_id()`.
- Platform admin, course read policy’sinde hiçbir istisna almaz.
- `dou_worker` ve `PUBLIC` hiçbir bildirim grant’i almaz.
- `DELETE` grant’i yok.
- Başlık/gövde için `UPDATE` grant’i yok; yalnız kontrollü withdraw eylemi.
- Yeni tablolar, `0001`’deki geniş default privileges yüzünden migration sonunda açıkça `REVOKE ALL` ile kapatılmalı ve gerekli dar grant’ler yeniden verilmelidir.

Mevcut platform admin audit allowlist’i sabit beş action kabul ediyor ([0014:23](/private/tmp/dou-evidence-fix.r2CC2o/repo/supabase/migrations/0014_platform_admin_console.sql:23)). `0014` değiştirilmemeli; `0016` içinde constraint ve `app.audit_platform_admin_access` forward-fix edilerek yeni admin action’ları eklenmeli. Dinamik `{announcement_id}` yolları audit’e gerçek UUID ile değil route template’iyle yazılmalı; aksi halde her UUID constraint’i kırar. Mevcut dependency şu an gerçek URL path’ini yazıyor ([deps.py:166](/private/tmp/dou-evidence-fix.r2CC2o/repo/apps/api/app/api/deps.py:166)).

Audit:

- Admin erişimlerinin izin/red kararı mevcut append-only admin audit’e gider.
- Announcement satırı `created_by/created_at` ve `withdrawn_by/withdrawn_at` ile kabul edilen domain eylemini taşır.
- Gönderenlere bireysel okundu listesi veya “kim okumadı?” ekranı verilmez.
- Teknik loglara başlık/gövde yazılmaz.

## Sınav güvenliği kararı

Serbest metinli ders duyurusu, sınav sorusunun cevabını taşıyan yeni bir yan kanal olabilir. En güvenli ilk sürüm:

- Aktif `exam` oturumu olan öğrenciye aynı dersin duyuru gövdesini göstermeme.
- Direct course announcement API ve bildirim kutusu aynı kuralı uygulamalı.
- Platform operasyon duyuruları görünür kalabilir.
- Sınav sırasında resmi gözetmen mesajı gerçekten gerekiyorsa ileride ayrı, dar `exam_notice` türü açılmalı; serbest ders duyurusuna “sınavda göster” bayrağı verilmemeli.

Bu karar spec’te açık yazılmadan uygulama yapılmamalı.

## Öğrenci hedefleme ve gizlilik

İlk dilimde kesinlikle olmamalı:

- Tek öğrenci seçme
- E-posta/ad ile hedefleme
- “Başarısız öğrenciler” veya not/başarı grubuna gönderme
- Okundu/okunmadı öğrenci listesi
- Ek dosya veya tıklanabilir harici link
- Adminin bir dersi seçip o ders adına mesaj atması
- AI tarafından otomatik duyuru yazma/gönderme

Bunlar akademik kayıt, ayrımcılık, taciz, phishing ve KVKK riskini büyütür. İleride bireysel mesajlaşma istenirse ayrı retention, itiraz, moderasyon, export/delete ve danışman onayı spec’i gerekir.

`announcement_reads` kullanıcıya bağlı kişisel veridir:

- kullanıcı silmede cascade;
- export kapsamına ya doğrudan eklenmeli ya da neden içerilmediği açık yazılmalı;
- gönderen/admin bireysel receipt görmemeli;
- saklama süresi ve expired duyuru temizliği belgelenmeli.

## Test ve kanıt planı

Backend/API:

- admin platform duyurusu oluşturur;
- normal kullanıcı ve yalnız eğitmen admin endpoint’inde 403;
- aynı ders eğitmeni course duyurusu oluşturur;
- öğrenci, başka ders eğitmeni ve üyeliksiz admin reddedilir;
- mixed-role kullanıcı iki ayrı eksende sınanır;
- platform-admin-only ve course-students audience görünürlüğü;
- revoked membership ve başka ders izolasyonu;
- mark-read idempotent;
- başkasının/ görünmeyen duyurunun receipt’i yazılamaz;
- expired/withdrawn kayıt unread sayılmaz;
- extra alan, boş/aşırı uzun metin ve bozuk cursor reddedilir;
- `&lt;script&gt;` içeriği metin olarak kalır.

RLS mutasyonları:

1. platform insert admin kontrolü kaldırılınca normal kullanıcı sızıntısı;
2. course insert instructor kontrolü kaldırılınca öğrenci sızıntısı;
3. course select membership kontrolü kaldırılınca cross-course sızıntı;
4. receipt self-check kaldırılınca başka kullanıcı adına okuma sızıntısı;
5. update/delete grant’i açılınca yayınlanmış içeriğin değişmesi;
6. platform admin course bypass eklendiğinde üyeliksiz admin sızıntısı.

Frontend/E2E:

- bildirim kutusu, unread sayı ve read akışı;
- admin olmayan kullanıcıda admin composer hiç mount/request olmaz;
- öğrenci course composer görmez;
- mixed-role iki ayrı kursta doğru araçları görür;
- doğrudan URL/API bypass reddedilir;
- klavye, Escape, odak geri dönüşü, 375 px, koyu tema;
- aktif sınavda course duyurusu yan kanalının kapanması;
- E2E sonunda platform announcement ve admin audit kalıntısı sıfır.

Course duyuruları course cascade ile temizlenir. Platform duyuruları course’a bağlı olmadığı için mevcut E2E cleanup yalnız onları temizleyemez; explicit test ID kaydı ve kimlik doğrulamalı cleanup genişletmesi gerekir. Başlık benzerliğiyle silme yapılmamalı. Mevcut cleanup explicit course/audit kapsamı kullanıyor ([cleanup.ts:275](/private/tmp/dou-evidence-fix.r2CC2o/repo/apps/web/e2e/cleanup.ts:275)).

## Dosya sahipliği ve çakışma haritası

Yeni dosyalar:

- `specs/006-notification-center/*`
- `supabase/migrations/0016_notifications.sql`
- `supabase/tests/rls_notifications_mutation_check.sh`
- `apps/api/app/models/notification.py`
- `apps/api/app/schemas/notification.py`
- `apps/api/app/api/notifications.py`
- `apps/api/tests/test_notifications.py`
- `apps/web/lib/notifications.ts`
- `apps/web/components/notifications/*`
- `apps/web/app/notifications/page.tsx`
- `apps/web/app/admin/announcements/page.tsx`
- `apps/web/app/courses/[courseId]/announcements/page.tsx`
- notification-focused frontend tests/E2E

Çakışacak mevcut dosyalar:

- `apps/api/app/main.py`
- `apps/api/app/api/deps.py`
- `apps/web/components/app-shell.tsx`
- `apps/web/components/course-nav.tsx`
- `apps/web/app/admin/page.tsx`
- `apps/web/e2e/cleanup.ts`
- `.specify/feature.json`
- `DESIGN.md`
- `ARCHITECTURE.md`
- `README.md`
- `docs/kvkk.md`
- `docs/security.md`

Özellikle `README.md` şu an A–D entegrasyon düzeltmelerinde kirli. Bildirim işi mevcut kirli clone’da başlatılmamalı. Önce o düzeltmeler commit/push edilip Claude’un değerlendireceği kesin SHA oluşmalı; sonra `006-notification-center` o SHA’dan veya birleşmiş `main`den açılmalı. Bildirim özelliği AI davranışı değiştirmediği için `.ai/changes` dosyası gerektirmez.

Mevcut candidate SHA: `50543c4f555a9d21de288040c10b27621e93172a`; çalışma ağacındaki A–D düzeltmeleri henüz commit değil. Bu yüzden bugün `0016` yazmaya başlamak entegrasyon izini tekrar karıştırır.
</pre>

</details>

<details>
<summary><code>/root/final_diff_audit (Fermat)</code> — 1149.3 MiB — closed</summary>

- Session: `019ff0e4-be6f-7961-9dfa-710bdd06f1a3`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T12:55:50.640Z`
- Source log: `rollout-2026-08-11T15-55-50-019ff0e4-be6f-7961-9dfa-710bdd06f1a3.jsonl`

<pre>
GO — P0/P1/P2 blocker yok.

- Retroaktif `SELF` fail-open kapalı: her güvenilir dosya yalnız ilk eklendiği commit’e bağlanıyor; sonradan gelen child/branch ucu bağlamı ileri taşıyamıyor ([ai_sdlc_check.py](/private/tmp/dou-evidence-fix.r2CC2o/repo/scripts/ai_sdlc_check.py:1691)).
- Yeniden yazılan r1 ve ona bağlı r2, `untrusted_dossiers` kümesine alınıp lifecycle, evidence ve coverage hesaplarından çıkarılıyor ([ai_sdlc_check.py](/private/tmp/dou-evidence-fix.r2CC2o/repo/scripts/ai_sdlc_check.py:1322), [ai_sdlc_check.py](/private/tmp/dou-evidence-fix.r2CC2o/repo/scripts/ai_sdlc_check.py:1673), [ai_sdlc_check.py](/private/tmp/dou-evidence-fix.r2CC2o/repo/scripts/ai_sdlc_check.py:1775), [ai_sdlc_check.py](/private/tmp/dou-evidence-fix.r2CC2o/repo/scripts/ai_sdlc_check.py:1788), [ai_sdlc_check.py](/private/tmp/dou-evidence-fix.r2CC2o/repo/scripts/ai_sdlc_check.py:1852)).
- Karantina iki tarihsel kaydı doğru introduction SHA ve final blob hashleriyle bağlıyor; ikisini bağımsız yeniden hesapladım ve eşleşti ([legacy.json](/private/tmp/dou-evidence-fix.r2CC2o/repo/.ai/quarantine/005-role-aware-course-agent-legacy.json:10)).
- Yeni r3 gerçek root: `revision=1`, `supersedes=null`, exact main base ve `candidate_sha=SELF` ([r3.json](/private/tmp/dou-evidence-fix.r2CC2o/repo/.ai/changes/005-role-aware-course-agent-r3.json:3)).
- Exact `main → aday` hassas diff: 30 yol. r3 artifact listesi: 30 yol. Eksik: 0, fazla: 0. Tüm 30 artifact ve 7 evidence hash’i eşleşti.
- Karantina replacement’ının exact base/head root ve tam hassas-diff kapsamı validator tarafından ayrıca zorunlu tutuluyor ([ai_sdlc_check.py](/private/tmp/dou-evidence-fix.r2CC2o/repo/scripts/ai_sdlc_check.py:1740)).
- 57/57 tam validator testi ve 7/7 hedefli karantina/SELF regresyon testi geçti ([test_ai_sdlc_check.py](/private/tmp/dou-evidence-fix.r2CC2o/repo/scripts/test_ai_sdlc_check.py:998)).
- Dirty çalışma ağacının birebir geçici commit kopyasında gerçek kapı: `AI_SDLC_CHECK=PASS`.
- Ruff check, Ruff format, JSON doğrulama ve `git diff --check` temiz.

Gerçek commit SHA henüz oluşmadığı için aynı exact-base validator komutu commit sonrasında bir kez daha çalıştırılmalı. Bu normal son kapı; commit öncesi blocker değil. Dosya değiştirmedim.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.2 MiB — closed</summary>

- Session: `019ff0e4-bf1d-7ee1-bce7-ea4bf0823c0b`
- Parent: `019ff0e4-be6f-7961-9dfa-710bdd06f1a3`
- Started: `2026-08-11T12:55:50.813Z`
- Source log: `rollout-2026-08-11T15-55-50-019ff0e4-bf1d-7ee1-bce7-ea4bf0823c0b.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/notification_spec_draft (Erdos)</code> — 267.2 MiB — closed</summary>

- Session: `019ff0f7-cf0d-7de1-87cd-6f24f0cb870f`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T13:16:40.078Z`
- Source log: `rollout-2026-08-11T16-16-40-019ff0f7-cf0d-7de1-87cd-6f24f0cb870f.jsonl`

<pre>
A–D’nin sabit SHA’sını kullanarak taslağı artık gerçek 006 dalına alıyorum. Önce dal/HEAD, migration sırası ve aktif özellik işaretçisini ölçüp yalnız bana ayrılan Speckit alanlarını değiştireceğim.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.8 MiB — closed</summary>

- Session: `019ff0f7-cf90-7921-b851-072d73abcbab`
- Parent: `019ff0f7-cf0d-7de1-87cd-6f24f0cb870f`
- Started: `2026-08-11T13:16:40.208Z`
- Source log: `rollout-2026-08-11T16-16-40-019ff0f7-cf90-7921-b851-072d73abcbab.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/quarantine_validator_fix (Godel)</code> — 130.9 MiB — closed</summary>

- Session: `019ff100-e857-7a73-91b3-3ccd84f3c6f7`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T13:26:36.375Z`
- Source log: `rollout-2026-08-11T16-26-36-019ff100-e857-7a73-91b3-3ccd84f3c6f7.jsonl`

<pre>
Tamamlandı; commit/push yapılmadı.

- Fail-open child-base doğrulaması kaldırıldı.
- Yeniden yazılmış kayıtlar ve onların soyundan gelenler kapsam, kanıt veya yaşam döngüsü yetkisi sağlayamıyor.
- Eski r1/r2 dosyaları silinmeden karantina manifestine bağlandı.
- Yeni exact root r3, karantina dahil 30/30 hassas dosyayı tek başına hash-bind ediyor.
- 6 saldırı testi ve eski açığın regresyon testi eklendi.
- Validator: 57/57 yeşil.
- Ruff, format, JSON ve diff kontrolleri yeşil.
- Son exact base→commit doğrulaması, ana ajan gerçek commit’i oluşturduktan sonra koşulmalı.
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.4 MiB — closed</summary>

- Session: `019ff100-e8d3-7782-88a1-caa6bb0fea5f`
- Parent: `019ff100-e857-7a73-91b3-3ccd84f3c6f7`
- Started: `2026-08-11T13:26:36.499Z`
- Source log: `rollout-2026-08-11T16-26-36-019ff100-e8d3-7782-88a1-caa6bb0fea5f.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/notification_backend (Pauli)</code> — 914.2 MiB — closed</summary>

- Session: `019ff139-e0a7-77c0-8838-c94ae4104200`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T14:28:49.959Z`
- Source log: `rollout-2026-08-11T17-28-49-019ff139-e0a7-77c0-8838-c94ae4104200.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>/root/notification_frontend (Darwin)</code> — 190.7 MiB — closed</summary>

- Session: `019ff13a-9678-7cd0-bba2-9fa4d4c05db9`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T14:29:36.504Z`
- Source log: `rollout-2026-08-11T17-29-36-019ff13a-9678-7cd0-bba2-9fa4d4c05db9.jsonl`

<pre>
Evet — öğretmenden tamamen ayrı Bilgi İşlem panelini yaptım ve GitHub’a gönderdim.

Dal: [`003-product-portal`](https://github.com/muratcan-ates/DOU-Synapse/tree/003-product-portal)
Son commit: `2c8ded8`
Taban: `3b707ca`
Durum: çalışma ağacı temiz, uzak dalla birebir eşit. `main` veya `002` henüz değiştirilmedi.

Yapılanlar:

- Bilgi İşlem’e özel `/admin` paneli
- Uygulama, veritabanı ve embedding sağlık durumu
- Kullanıcı, ders, aktif üyelik ve kaynak sayıları
- AI kullanım ve belge işleme kayıtları
- Maskelenmiş e-posta ve güvenli arama
- İzin verilen/reddedilen yönetim erişimlerinin denetim kaydı
- Öğretmen yetkisinden bağımsız `platform_admins` modeli
- Öğrenci/eğitmen dashboard’ları
- Ders bazlı karma rol desteği
- Profil düzenleme ve veri haklarına erişim
- Aktif sınav sırasında Asistan bağlantısının sunucu kararına göre kilitlenmesi
- OBS’den alınan bilgi hiyerarşisi, kartlar ve mobil navigasyon; sahte AGNO, dönem, danışman veya duyuru eklenmedi
- Eksik site simgesi nedeniyle oluşan tarayıcı 404’ü giderildi

Bilgi İşlem paneli ilk sürümde bilinçli olarak salt okunur. Kullanıcı silme, rol verme, ders kapatma, öğrenci sohbetlerini veya sınav cevaplarını görme yetkisi yok. Adminlik yalnız veritabanı yöneticisi tarafından atanabiliyor; kullanıcı kendini admin yapamıyor.

Doğrulama sonuçları:

- Backend: `846/846`
- Frontend: `309/309`
- Tam tarayıcı paketi: `33/33`
- Çekirdek RLS: `109/109`
- RLS mutasyonları: `55/55`
- Bilgi İşlem güvenlik mutasyonları: `3/3`
- OpenAPI: 50 yol, 118 şema
- Doküman doğruluk kapısı: 77 belge temiz
- Test sonunda kalan ders ve admin audit kaydı: `0`
- Korunan `COME 331`: yerinde kaldı

Oluşturduğum geçici test veritabanlarını kaldırdım, test sunucularını kapattım ve ortak `dou_synapse` veritabanına dokunmadım.

Claude’un yapacağı doğru işlem: `003-product-portal` dalını inceleyip `002-production-hardening` dalına entegre etmek. Production iddiası için gerçek Supabase Auth/Storage, gerçek LLM, telemetry/alarmlar, yük testi, backup-restore tatbikatı ve canlı staging URL hâlâ açık.

&lt;oai-mem-citation&gt;
&lt;citation_entries&gt;
skills/dou-parallel-worktree-delivery/SKILL.md:16-28|note=[parallel worktree isolation validation and delivery procedure]
MEMORY.md:939-948|note=[DOU worktree isolation unique test database and rebase safeguards]
&lt;/citation_entries&gt;
&lt;rollout_ids&gt;
019feafc-8971-7ca0-a58d-f091f3fde5ea
&lt;/rollout_ids&gt;
&lt;/oai-mem-citation&gt;
</pre>

</details>

<details>
<summary><code>guardian</code> — 0.1 MiB — closed</summary>

- Session: `019ff285-bbe3-7bd3-8ca0-4f3ec05522a8`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T20:31:18.499Z`
- Source log: `rollout-2026-08-11T23-31-18-019ff285-bbe3-7bd3-8ca0-4f3ec05522a8.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>

<details>
<summary><code>guardian</code> — 0.2 MiB — closed</summary>

- Session: `019ff2b2-f928-71b3-b069-295429a80666`
- Parent: `019fe732-a346-7ff0-96eb-7a8bd2750f95`
- Started: `2026-08-11T21:20:43.305Z`
- Source log: `rollout-2026-08-12T00-20-43-019ff2b2-f928-71b3-b069-295429a80666.jsonl`

_No final assistant handoff was recoverable from the compact tail window._

</details>
