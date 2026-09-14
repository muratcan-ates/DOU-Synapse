# Erişilebilirlik ve klavye turu

Yeni dosya: `docs/accessibility.md`. Protokol hazırlık tarihi: 13 Eylül 2026. Manuel tarayıcı turu ve ekran okuyucu turu çalıştırılmadı. Dar otomatik klavye koşusunun gerçek sonucu aşağıda ayrı kayıtlıdır; manuel bulgu alanları **yapılmadı** durumundadır. Kaynak kodda bir özelliğin bulunması, tarayıcıda doğru çalıştığının kanıtı değildir.

[DESIGN.md](../DESIGN.md) tek tasarım otoritesidir. Görünür odak, etiketli alanlar, renk dışında durum bilgisi, açık/koyu tema ve mobil kullanım bu protokolün kontrol koşullarıdır. Belgede geçmişte kayıtlı kontrast oranları burada yeniden ölçülmüş sayılmaz. Yeni oran veya AA uygunluğu iddiası eklenmedi.

**ENGEL: bağımlılık @axe-core/playwright.** Bağımlılık onayı bulunmadığı için axe taraması eklenmedi veya çalıştırılmadı. Paket ve kilit dosyaları değiştirilmedi. `getByRole`, odak ve `aria-*` iddiaları otomatik axe taramasının, ekran okuyucuyla kullanımın veya bütün ürün için uygunluk incelemesinin yerini tutmaz.

## Turun kurulumu

- Ayrı test veritabanı ve sentetik öğrenci/eğitmen hesapları [test protokolüne](testing.md) göre hazırlanır. Platform yöneticisi kontrolü yalnız hazırlanmış yerel demo yöneticisiyle yapılır. Gerçek öğrenci verisi gözlem kaydına girmez.
- Görüntü alanı **375 × 812 CSS piksel**, başlangıç teması **koyu** olur. Görünür ürün tema seçimi de kaydedilir; yalnız işletim sistemi ayarının koyu olması yeterli kabul edilmez. Temaya özgü kontroller ayrıca açık tema ile tekrar edilir.
- Oturum/veri kurulumu bittikten sonra sayfanın ilk odağından başlanır. Gözlenen akışta fare, dokunma, `focus()` veya odak veren geliştirici aracı kullanılmaz. `Tab`, `Shift+Tab`, `Enter`, `Space`, yön tuşları ve gerektiğinde `Escape` kullanılır.
- Her hedefin erişilebilir adı, etkin/devre dışı durumu, odak görünürlüğü, görsel sıra ile klavye sırası ve odak dönüşü kaydedilir. Sabit başlık, yatay ders şeridi veya asistan düğmesi odaklanan hedefi örtmemeli; sayfa genelinde yatay taşma olmamalıdır. Kaydırılabilir bir veri alanının kendi davranışı ayrıca yazılır.
- İçeriğe atlama bağlantısı etkinleştirilir; odağın gerçek ana içeriğe geçmesi sınanır. Aktif gezinme `aria-current`, açılan bölüm `aria-expanded`/`aria-controls`, salt okunur alan `aria-readonly`, tema seçimi `aria-pressed` ile karşılaştırılır. Metin etiketi placeholder'a bırakılmamalıdır.
- Kaydetme, hata, boş durum, yükleme ve iptal sonrası odak ayrıca gözlenir. Durum mesajının DOM'daki canlı bölgesi kontrol edilir; ekran okuyucu tarafından duyulduğu ancak gerçekten dinlenmişse yazılır.
- Silme ve profil kaldırma ekranlarında bu ilk tur onayı açıp **Vazgeç** ile döner. Gerçek silme davranışı yalnız kendine ait sentetik veriyle ayrı kayıt altında sınanır. Parola sıfırlama e-postası gönderilmez; sağlayıcı akışı kurulu değilse o bölüm **yapılmadı: sağlayıcı kurulumu yok** olarak kalır.

Her bulgu kaydı şu bilgileri taşır: gözlem tarihi, aday SHA, tarayıcı/sürüm ve işletim sistemi, route/rol, tema/viewport, tam tuş sırası, beklenen ve görülen davranış, sentetik kanıt yolu, issue/sorumlu ve yeniden kontrol sonucu. Olmayan issue veya kişi adı doldurulmaz.

## Gerçek sayfa envanteri ve bulgular

Tablo `apps/web/app/**/page.tsx` sayfalarını kapsar; `[courseId]` ve `[chunkId]` koşunun kendi kaynaklarından alınır. Her satırda yukarıdaki **375px + koyu + yalnız klavye** ortak turu ve satıra özgü akış birlikte uygulanır. Route'un birden çok rol/durum taşıması tek başarılı ekranla kapatılamaz.

| Route ve kaynak | Rol / gerekli durum | Sayfaya özgü klavye turu ve kontrol koşulu | Bulgu / kanıt / tarih |
|---|---|---|---|
| `/` · [giriş](../apps/web/app/page.tsx) | Oturumsuz; yerel demo, varsa ayrı gerçek giriş kurulumu | Tema düğmeleri, demo kartları, gizlilik bağlantısı ve kuruluysa etiketli giriş alanları sırayla ulaşılabilir. Enter ile girişin sonucu ve hata mesajına erişim kaydedilir. | yapılmadı |
| `/forgot-password` · [parola isteği](../apps/web/app/forgot-password/page.tsx) | Oturumsuz; sağlayıcı kapalı/açık ayrı | Kurulum yoksa açıklama ve “Oturum açmaya dön” bağlantısı; varsa e-posta alanı ve gönderim durumları incelenir. Bu tur e-posta göndermez. | yapılmadı |
| `/reset-password` · [yeni parola](../apps/web/app/reset-password/page.tsx) | Kurtarma oturumu; sağlayıcı kapalı/açık ayrı | Kurulum açıklaması veya iki parola etiketinin bağı, eşleşmeme hatası ve yeni bağlantı isteme yolu incelenir. Gerçek hesap parolası değiştirilmez. | yapılmadı |
| `/dashboard` · [genel bakış](../apps/web/app/dashboard/page.tsx) | Öğrenci, eğitmen, karma üyelik; boş/dolu | “Ana içeriğe geç” gerçekten ana içeriğe odak taşır. “Tüm dersler”, rol araçları ve asistan tetikleyicisi sırada erişilebilir; olmayan eğitmen aracı öğrencinin odak sırasına girmez. | yapılmadı |
| `/courses` · [ders listesi](../apps/web/app/courses/page.tsx) | Sentetik kullanıcı; boş/dolu liste | “Yeni ders” açıldığında `aria-expanded` ve `aria-controls` gerçek formu gösterir, “Ders kodu” odaklanır. `Shift+Tab` ile “Vazgeç”e dönüp kapatınca odak tetikleyicide kalır. | yapılmadı |
| `/profile` · [profil](../apps/web/app/profile/page.tsx) | Öğrenci/eğitmen; yalnız kendi sentetik profil | Ad soyad klavyeyle düzenlenir, e-posta hem salt okunur hem anlaşılır kalır. Kaydetme durumu ve tema düğmelerinin `aria-pressed` değerleri kontrol edilir; ad gerçek API'de özgün değerine geri konur. | yapılmadı |
| `/account` · [verilerim](../apps/web/app/account/page.tsx) | Sentetik kullanıcı | Dışa aktarma, sohbet silme ve profil kaldırma tetikleyicilerinin adları ayrılır. Onay sorusu okunabilir, Vazgeç erişilebilir ve iptal odağı korunur; bu tur yıkıcı onayı tamamlamaz. | yapılmadı |
| `/kvkk` · [gizlilik metni](../apps/web/app/kvkk/page.tsx) | Oturumsuz/oturumlu | Başlık yapısı ve metin bağlantıları, dönüş bağlantısı ve dar ekrandaki tablolar incelenir. Yatay veri alanı ile sayfanın tamamının taşması ayrı kaydedilir. | yapılmadı |
| `/admin` · [Bilgi İşlem](../apps/web/app/admin/page.tsx) | Yerel demo yöneticisi; yetkisiz kullanıcı ayrı | Sekme adı/seçimi, kullanıcı arama, Uygula ve devam kontrolleri klavyeyle kullanılır. Yetkisiz kapakta gizli yönetim denetimleri odak sırasına girmemeli; gerçek audit temizliği ayrı koşu muhasebesine bağlıdır. | yapılmadı |
| `/courses/[courseId]` · [materyaller](../apps/web/app/courses/[courseId]/page.tsx) | Eğitmen/öğrenci; hazır/işlenen/hatalı kaynak | Ders şeridi ve yükleme girdisinin adı kontrol edilir. Önizleme aç/kapa durumları ve tetikleyici odağı izlenir; öğrenciye sunulmayan yazma denetimleri odak sırasına girmez. | yapılmadı |
| `/courses/[courseId]/chat` · [asistan](../apps/web/app/courses/[courseId]/chat/page.tsx) | Öğrenci/eğitmen; boş, yanıt, ret, hata, sınav kilidi | Mod seçimi, etiketli besteci, gönderim, kaynak bağlamı bağlantıları ve sohbet geçmişi klavyeyle izlenir. Kapsam dışı ret hata gibi duyurulmamalı; kilitli besteci odak sırasına girmemeli. | yapılmadı |
| `/courses/[courseId]/questions` · [soru havuzu](../apps/web/app/courses/[courseId]/questions/page.tsx) | Eğitmen; taslak/onaylı/boş; öğrenci kapağı ayrı | Süzgeçlerin seçimi, soru listesi, taslak editörü ve “sonraki taslak” odağı kontrol edilir. Onay/iptal mesajlarına erişim ve öğrenciye kapalı durum kaydedilir. | yapılmadı |
| `/courses/[courseId]/blueprints` · [sınav planı](../apps/web/app/courses/[courseId]/blueprints/page.tsx) | Eğitmen; boş, taslak, hazır/eksik sürüm | Öğrenme çıktısı alanları, konu seçimi, yeni sınav, hücreler ve hazır olma raporu sırayla incelenir. Hata hangi alan/eksikle ilgiliyse erişilebilir ilişkisi yazılır. | yapılmadı |
| `/courses/[courseId]/settings` · [AI politikası](../apps/web/app/courses/[courseId]/settings/page.tsx) | Eğitmen; devralınmış/özelleştirilmiş ayarlar | Varsayılanı kullan, mod checkbox'ları, etiketli sayısal alanlar ve kaynak seçimi gezinilir. Devralınan alanların durumları ve kaydetme geri bildirimi kontrol edilir; değişiklik yalnız kendi test dersinde geri alınır. | yapılmadı |
| `/courses/[courseId]/exam` · [sınav provası](../apps/web/app/courses/[courseId]/exam/page.tsx) | Öğrenci; katalog, alıştırma, aktif sınav, sonuç | Konu seçimi, radio grubu/yön tuşları, cevap ve `aria-disabled` gezinme davranışı incelenir. Sayaç her saniye canlı duyuru üretmemeli; bitirme/iptal odağı, kilit ve yeniden açılan sonuç ayrıca gözlenir. | yapılmadı |
| `/courses/[courseId]/analytics` · [ilerleme](../apps/web/app/courses/[courseId]/analytics/page.tsx) | Öğrenci/eğitmen; veri var/yok | Yenileme, ilgili çalışma bağlantıları ve görsel özetlerin metinsel karşılığı incelenir. Ölçülmeyen veya bulunmayan değer için uydurma sayı aranmaz; mevcut boş durum kaydedilir. | yapılmadı |
| `/courses/[courseId]/quality` · [AI kalite](../apps/web/app/courses/[courseId]/quality/page.tsx) | Eğitmen; boş/dolu izinli inceleme kuyruğu | Yenileme, gerekçe özeti ve izinle paylaşılmış inceleme kayıtları klavyeyle okunur. Öğrenci kapağı ve yenileme hatasından dönüş yolu ayrı gözlenir. | yapılmadı |
| `/courses/[courseId]/members` · [katılımcılar](../apps/web/app/courses/[courseId]/members/page.tsx) | Eğitmen; dolu/boş liste; öğrenci kapağı | E-posta/rol alanları, ekleme, devam ve çıkarma onayının adları ayrılır. Çıkarma iptalinde odak kaybolmamalı; gerçek üyelik değişikliği yalnız sentetik kullanıcıyla yapılır. | yapılmadı |
| `/courses/[courseId]/sources` · [retrieval laboratuvarı](../apps/web/app/courses/[courseId]/sources/page.tsx) | Eğitmen; sonuçlu/sonuçsuz sorgu | Sorgu alanı, Ara düğmesi, boş sonuç ve kaynak bağlantıları sırayla incelenir. Öğrenci kapağındaki dönüş bağlantısı erişilebilir kalır. | yapılmadı |
| `/courses/[courseId]/sources/[chunkId]` · [kaynak bağlamı](../apps/web/app/courses/[courseId]/sources/[chunkId]/page.tsx) | Yetkili üye; normal, sınav kilidi, bulunamayan kaynak | Kırıntı bağlantıları, seçili pasaj etiketi ve uzun/kod içerikleri dar ekranda incelenir. Kilitte veya hata/yenilemede eski özel pasaj görünür kalmamalı; dönüş yolu klavyeyle erişilebilir olmalı. | yapılmadı |

## Bekleyen otomatik aday ve mevcut testler

Ayrı hazırlanan `apps/web/e2e/accessibility-keyboard.spec.ts` adayı henüz yayımlanmadı. Bu protokol değişikliği E2E kaynak dosyasını içermez. E2E adayının yayımlanması, L6 düzenleme kapsamı dışındaki iki canlı sayacın güncellenmesi için beklenen izne ve ortak doğrulama kapılarının geçmesine bağlıdır. Aday ayrı çalışma alanında korunur; bu bekleme test kapsamını veya sayaçları devre dışı bırakarak aşılmaz. Bu durum H3 çalışmasının tamamlandığı anlamına gelmez.

Adaydaki `@keyboard` vakaları; ana içeriğe atlama bağlantısının **etkinleştirilmesini**, gerçek klavye gezinmesinde `aria-current` değişimini, ders formunun `aria-expanded`/`aria-controls` ilişkisini ve iptal odağını, profil kaydetme durumunu, salt okunur e-postayı ve tema seçiminin durumunu sınamak üzere hazırlanmıştır. Kimlik kurulduktan sonraki gözlenen etkileşimlerde gerçek klavye komutları kullanılır; odağı doğrudan yerleştiren helper yoktur. Profil adı `finally` içinde aynı worker'ın `studentHeaders` bilgileriyle gerçek API üzerinden geri yüklenir.

Mevcut [portal testleri](../apps/web/e2e/portal.spec.ts) mobil/koyu odak ve taşmayı, [rol bazlı asistan testleri](../apps/web/e2e/role-aware-agent.spec.ts) dialog odak sınırını, Escape ve tetikleyiciye dönüşü, [sohbet silme testleri](../apps/web/e2e/chat-history-deletion.spec.ts) iptal odağını, [blueprint konu testleri](../apps/web/e2e/blueprint-topic-readiness.spec.ts) düzenleme odağını, [politika geçmişi testleri](../apps/web/e2e/policy-history.spec.ts) özet odağını içerir. Kaynakta bulunmaları bu hazırlıkta çalıştırıldıkları anlamına gelmez. Bu dialog senaryoları yeni dosyada tekrarlanmadı.

Aday gerçekten çalıştırıldığında komut, kaynak SHA, tarih, ortam ve çıkış sonucu ayrı bir kanıt kaydıyla eklenir. Başarılı bir aday koşusu bile aşağıdaki manuel rota ve ekran okuyucu turlarını yapılmış saymaz. 13 Eylül 2026 yerel aday koşusu aşağıda kayıtlıdır; yayımlanmamış test kaynağının kabulü bütün H3 işinin tamamlanması değildir.

| Kontrol | Bu hazırlıktaki durum | Kanıt |
|---|---|---|
| Yeni klavye E2E aday vakaları | yerelde geçti; kaynak yayımlanmadı | [Gerçek koşu kaydı](evidence/l6-h3-verification.json) |
| Route tablosundaki manuel turlar | yapılmadı | yok |
| Ekran okuyucuyla duyuru/okuma sırası | yapılmadı | yok |
| Yeni kontrast/AA ölçümü | yapılmadı | yok |
| axe otomatik taraması | koşulmadı | ENGEL: bağımlılık @axe-core/playwright |

Bir bulgu giderildiğinde ürün değişikliği ayrıca incelenir ve aynı route/rol/tuş sırası yeniden uygulanır. Alanın yalnız “kontrol edildi” diye işaretlenmesi yetmez; görülen davranış ve kanıt yolu eklenir. Kullanılmayan sonuç hücreleri **yapılmadı** olarak kalır.

## Yerel aday koşusu — 13 Eylül 2026

Üç klavye vakası iki worker ile yerel Chrome tarayıcısında geçti. Komut `playwright test --workers=2 --config runtime/repeat.config.ts accessibility-keyboard --grep @keyboard`; tam yollar, gerçek sonuç ve kaynak özetleri [koşu kaydındadır](evidence/l6-h3-verification.json). Ayrı sentetik veritabanı, sahte sağlayıcı ve hashing embedding kullanıldı. Playwright, sahipli API kapanışı ve audit son denetimi başarılı; kaynaklar ve kullanılan üretim derlemesi koşu boyunca değişmedi.

Bu adayın eklenmesiyle ölçülen E2E koleksiyonu 74 oldu; belge kapısı eski 71 iddiaları için başarısız döndü. README için ölçümden üretilen düzeltme hazırdır; `specs/002-production-hardening/plan.md` ile `specs/005-role-aware-course-agent/spec.md` L6 kapsamı dışında olduğundan izin bekleniyor. Test dosyası ve tam aday kanıtları korunarak bu belge tesliminden ayrıldı. Sayaç veya test kapısı devre dışı bırakılmadı; manuel rota tablosu, ekran okuyucu ve axe kabulü açık kalır.
