# 025 · Rol, erişilebilirlik ve kurtarma önizleme kontrolü

Tarihli aday anlık görüntüsü: **2026-09-14T23:28:26+03:00**. Dal: `025-campus-ui`.
HEAD: `3e7aa8be6fd69ffcf8a447b8fa6853143d414e20`. Aşağıdaki kaynak özetleri, bu HEAD üzerindeki
**commit edilmemiş çalışma ağacını** tanımlar; HEAD tek başına bu değişiklikleri içermez.
Bu not yerel önizleme adayını kaydeder; yayın onayı, release sertifikası veya WCAG
uygunluk sertifikası değildir. Yeni commit/push, servis başlatma veya derleme bu not
hazırlanırken yapılmadı. Önceki CI/harness değişiklikleri korunmuştur.

## Sonucun kapsamı

Öğrenci ve eğitmen alanları ders üyeliğinden, teknik yönetim platform yetkisinden
ayrılır. Ayarlar tarayıcıya özgü yazı boyutu, hareket, kontrast ve bağlantı tercihleri
sunar. Asistan kitap imzası mevcut rol/sınav sınırlarını korur. Anonim 404 ile gerçek
çalışma zamanı hatasının kurtarma ekranları ayrıdır.

## Entegratörün canlı kontrol kaydı

Aşağıdaki gözlemler `/root` entegratörünün bu görevde ilettiği gerçek tarayıcı/API/SQL
kontrolleridir; notu yazan ajan bunları yeniden çalıştırmadı. Önizleme web portu 3125,
API portu 8025; sahipli sentetik veritabanı `dou_campus025_20260914` kullanıldı.
Gerçek öğrenci içeriği veya kimlik bilgisi bu nota alınmadı.

| Rol | Tarayıcı gözlemi | API ve bağımsız SQL kontrolü |
|---|---|---|
| Öğrenci | Bilgi İşlem gezinmesi yok; doğrudan `/admin` erişimi reddedildi. | Beş admin ucu 403; üyelik gerektiren ders erişimi 200; `dou_app` ile `app.admin_overview()` reddedildi. |
| Eğitmen | Bilgi İşlem gezinmesi yok. | Beş admin ucu 403; üyelik gerektiren ders erişimi 200; aynı SQL çağrısı reddedildi. |
| Yalnız Bilgi İşlem | Teknik ölçümler ve bağlı olmayan güvenlik akışı açıklaması var. Genel bakış/Profil/Ayarlar ve ayrı teknik giriş; ders gezinmesi ve öğrenme kapanışı yok. Kullanıcı dizini “Tekrar dene” ile düzeldi. | Beş admin ucu 200; üye olmadığı ders erişimi 404; aynı SQL çağrısına izin verildi. |

Tablodaki ders erişimi ölçümü GET
`/courses/d879bf7c-7b65-40ae-9fe7-235a0246431a` isteğidir.

Beş admin ucu: GET `/admin/overview`, POST `/admin/users`, GET `/admin/courses`,
GET `/admin/requests`, GET `/admin/ingestion`. Bu gözlem tüm yetki/RLS testlerinin
yerini tutmaz. Demo hesap kurulumuna ait **14 testin geçtiği** entegratörün tool
sonucuyla bildirildi; ayrı günlük dosyası sağlanmadığı için buna günlük özeti atanmadı.

- Tercihler yeniden yüklemede korundu; sıfırlama çalıştı. Açık/koyu yüksek kontrast
  gözlendi. Büyük yazı kök boyutu 20px: 320px ekranda scrollWidth 320, 375px ekranda
  375, 1280px ekranda 1280; büyük yazı masaüstü gezinme rezervi 304px ölçüldü.
- Kitap asistanı 375px ekranda açılıp kapandı; “Rol ve kapsam” ayrıntısı açıldı.
  Escape kapattı ve odak tetikleyiciye döndü.
- `/sayfa-bulunamadi-onizleme` anonim tarayıcıda özel 404 gösterdi; HTTP kontrolü
  **404** döndü. `/dashboard` dönüşü anonim kullanıcıyı girişe götürdü.
- Gerçek çalışma zamanı istisnası tarayıcıda zorlanmadı. Geçici React testinde gerçek
  ekran ve Button render edildi; üretilen düğmenin onClick işleyicisi çağrılarak
  retry sayacı doğrulandı. Bu, tarayıcı tıklaması veya HTTP hata testi olarak sayılmaz.

## Okunan test ve derleme günlükleri

Bu bölüm tarihlidir; test sayıları canlı depo sayacı değildir. Birbirini kapsayabilen
odaklı gruplar toplanarak toplam test sayısı üretilmedi. Günlükler yerel `/tmp`
dosyalarıdır; SHA256 kaydı kalıcı CI arşivinin yerini tutmaz.

| Kontrol | Ölçülen sonuç | Yerel günlük SHA256 |
|---|---|---|
| Son üretim derlemesi | PASS; Next 16.3.3 derleme, TypeScript ve sayfa üretimi tamamlandı. Günlük: `/tmp/campus025-complete-ui-build.log` | `2818ec728c7f2f51a00438457dffef07b8cc31877723a8537f8f789278276003` |
| Rol/oturum/tema odaklı testler | 51 geçti, 0 başarısız; 165 assertion, 9 dosya. Günlük: `/tmp/campus025-role-accessibility-tests.log` | `488f92dba91e2ff64fd048a5d4727d7fdfb602f786a930d0c81057680df3b027` |
| Asistan/kitap/klavye sözleşmeleri | 33 geçti, 0 başarısız; 105 assertion, 4 dosya. Günlük: `/tmp/campus025-assistant-book-tests.log` | `e9a7749813fd5dfc9a2f5cd6ebd0d48bf8872507912e131f39fe7704117c1c29` |
| Erişilebilirlik ayrıştırıcı/açılış ve tema | 13 geçti, 0 başarısız; 63 assertion, 2 dosya. Günlük: `/tmp/campus025-accessibility-tests.log` | `589e3163c72108c3c29a04ee05616a44402633454b8b88756d93147135995ecb` |
| Gerçek React kurtarma render kontrolü | 3 geçti, 0 başarısız; 9 assertion. Gerçek Button işleyicisi retry çağırdı; ham hata/stack HTML’de yok. Günlük: `/tmp/campus025-recovery-render.log` | `7d8606ff05fbbcd0003eddcdcb3094185391eeaf76e66f548a5487c2ad57fbcc` |
| Açık/koyu ve iki yüksek kontrast teması | Dört temada ölçülen metin çiftleri 4.5:1, kontrol çiftleri 3:1 kapısını geçti. Günlük: `/tmp/campus025-accessibility-contrast.log` | `bedc881fbdf59743e5dcaa9279e2840344e96705bc23bfa0bb4e1c833d8eb597` |

## Açık kalan doğrulamalar

Tam E2E paketi bu son adayda yeniden koşulmadı. Önceki hosted koşunun **71 başarılı /
11 başarısız** sonucu tarihsel kayıt olarak duruyor; bu not onu başarılıya çevirmiyor.
Yerelde tam API veritabanı paketi, gerçek kurumsal oturum, gerçek model kalitesi,
zorlanmış çalışma zamanı hata ekranı ve üretim altyapısı bu kapsamda doğrulanmadı.
Tarayıcı örnekleri bütün sayfalar/yardımcı teknolojiler için evrensel erişilebilirlik
iddiası oluşturmaz. Değişen kaynaklarda veya yeni adayda uygun kapılar tekrar gerekir.

## Kaynak ve kontrol referanslarının SHA256 anlık izi

Aşağıdaki liste bu kontrolle ilgili dosyaları bağlar; dosyanın listede olması bu turda
hepsinin değiştirildiği anlamına gelmez. Eski migration dosyaları yalnız referanstır.

| Dosya | SHA256 |
|---|---|
| `DESIGN.md` | `07daf404e2626364353dde393015928689c311bb3776e1553c47bb94a28bd6b2` |
| `apps/web/app/page.tsx` | `21a5ac5e2d185d295609ef7e42c53d2210fd57767091402f9c5dbd46abcaaccf` |
| `apps/web/app/dashboard/page.tsx` | `c5cd52f66a7c83811eb989264dc2d7b414399225e944683f1db251b3cf9b26f4` |
| `apps/web/app/admin/page.tsx` | `cd3bce8a10753359ef732f128e69a6eb3d865703feca48916ff547f2bbf303ce` |
| `apps/web/app/profile/page.tsx` | `2f19145243cb97bb035f5ad8650aedb2f4e35f9a696ce218a46d8bd1c0701be4` |
| `apps/web/app/courses/page.tsx` | `3db3314a9aa0a2cf4328544f84ef7a17263d966255fb2ffa1399520af627ab08` |
| `apps/web/components/app-shell.tsx` | `fe4448e992837cfae20eb338bd7e751f1d5f8761a7eccc10e168a8ee48c9daf7` |
| `apps/web/components/quick-switch.tsx` | `3c3bac58ca384d1ebd4004f02435b49e24457fba18aefeb613f53fc9a9b103f2` |
| `apps/web/components/synapse-footer.tsx` | `cf6ee0c94117a6c629968751b81987b9c584bd37703f12cc3647036b5a426412` |
| `apps/web/components/portal/portal-profile-context.tsx` | `a2bc8789399a8cbedf585222c9fc04e4c4b8fa22a137afd15049b1361857c690` |
| `apps/web/lib/auth-session.ts` | `20e91518273c76152235ceb2458f4444de0c18e46b0c7fc917afcd0501f29099` |
| `apps/web/lib/profile.ts` | `b228c10b7fea9d5b9e396661b9f123e4a974e63c17f079ca9a55f17d366be80c` |
| `apps/web/lib/session.ts` | `9d09b20db610246b534d5232d838d17f5610ccf1a71ce37f74e838381a33fe0d` |
| `apps/web/lib/admin.ts` | `513bc40af301cc4e7ebc69215b164302a14c57df6607e200372dc7102a4476ec` |
| `apps/web/app/layout.tsx` | `8541e678399a3d104e602398cd6d550786d8c18ba3a604df9c0573395db6c5fd` |
| `apps/web/app/globals.css` | `cd12bc59123eb036331ea792b2431517a07d50f8e884bff51c82512e878f470b` |
| `apps/web/app/settings/page.tsx` | `2a77b5aef14a067d6a8e7b3a0fdf46d3c841f4df701d9d7c07377fefb2108ef7` |
| `apps/web/app/settings/layout.tsx` | `0974d79f9fe1cdeb979ebf4410910d87654f9593edab8f6eda4ec77904eb0b72` |
| `apps/web/components/accessibility-provider.tsx` | `84150f75181f77fea39d994d8150dc8e62100a5a947860d13656ffbe1c266203` |
| `apps/web/lib/accessibility.ts` | `8cd01b85131b861d7407ffa2787ac591987729030dff77ce2a14b4e986699a08` |
| `apps/web/lib/accessibility.test.ts` | `3319cb0d4c6911b06fa93debebbbd8047d4289d36fc31d62311fe6fae055cbe1` |
| `apps/web/public/accessibility-boot.js` | `d6deab96baa3b143b04976fad71613a91a9a806a3271bc36c9b6925575537bfc` |
| `apps/web/components/campus-motion.tsx` | `a78685a494fa35ad6d0584da1a9a21493b1be47b1547376aac356ec57b953ece` |
| `apps/web/components/theme-control.tsx` | `4db77aa6a2a9f3e56cfe721d2c3fe68201b7f9952fd5216b8fdb5c9fa4ff7300` |
| `apps/web/lib/theme.ts` | `9310417beb5b4c6d72c2a516a66f7bc9f957f1efb629378e91812096e673abdc` |
| `apps/web/scripts/contrast.mjs` | `fee112592aa8077da44b1de464538a3683d541cd6149589dc2164fd05e94d281` |
| `apps/web/components/course-assistant/course-assistant.tsx` | `9001b352d62969f65b849b16a2efc413dffcb9a9a80ec60bfa00423cb2f69751` |
| `apps/web/lib/course-assistant.ts` | `1bfbe2986517db2ab6c2e7141a3ec0ac5651fb2b398f3aba7008c42edebadc95` |
| `apps/web/lib/course-assistant-dialog.test.ts` | `a6274914807ce91574b20e421231799c271f7fd2958be241670d52b0ff4bd4e5` |
| `apps/web/lib/chat-availability.ts` | `9c43a460ddf5f945e6281394b952b7f9f9acdb36afa0b7ca07e11c896aa695a6` |
| `apps/web/app/not-found.tsx` | `2582218a9190867e837be62ae64f60ea453b7131b8566201286510204c1e5f7e` |
| `apps/web/app/error.tsx` | `a0db6dc4b5c581127715e8d8f30a7c8297774ba523da13f48ed7b6c33b62f3f2` |
| `apps/web/components/brand-mark.tsx` | `c772acd4674da103aa4e6a7cd890ebc40d2a8ffa5376a971d324432e0a6ba208` |
| `scripts/provision_ci_e2e.py` | `2ef26212e3803a9dabd1600efbd557e3e52d5e7862d920930ea7aecd99fb5dc7` |
| `scripts/test_provision_ci_e2e.py` | `41ad13525f1b5f8417c2a16bfd98464effeb36028111fba8a9b4e5edc9d79ff7` |
| `supabase/seed_demo.sql` | `46505b4db3832a00c8bbccef388e7f9dc3b63f5c8b8c1952c6fad50ce1e86551` |
| `apps/api/app/api/admin.py` | `fdf679b526046e41cfc78d266a91bbef5bebc4f8a0a27338a192e8b702a53a46` |
| `apps/api/app/api/deps.py` | `77edb1855d0c5d16b1c17d5a383d3ebadb5ffa0b087692c32ba14d8ab1cbb360` |
| `supabase/migrations/0014_platform_admin_console.sql` | `8b234683593a2f2c2c0c4fc48d47d5b1f4ded9fa4e3d62bf6c152117802479c5` |
| `/tmp/campus025-recovery-render/recovery.test.ts` (geçici test) | `11d28ec344f8037ba580eb5988d8c9581d13ca3b47c31bbea2c722858519a975` |
