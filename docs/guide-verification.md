# Kılavuz ekran doğrulaması

13 Eylül 2026. `i2-browser-02`, yeni üretim derlemesi ve sahipli yerel API ile tamamlandı. Playwright, API kapanışı ve audit sonucu başarılı; ürün ve ayrı runtime girdilerinin koşu öncesi/sonrası özetleri aynı kaldı.

> **15 Eylül notu:** Bu belgedeki bütün tarih, sayı ve görsel bulguları 13 Eylül
> `i2-browser-02` koşusunundur ve değiştirilmedi. `docs/images` 15 Eylül'de yeniden
> çekildi; belgenin sonundaki **"15 Eylül 2026 eki"** paragrafını önce okuyun.

Gerçek kayıtlarda 44 ekran gözlemi, aşağıdaki 31 denetim maddesine bağlandı. <!-- docs-check: tarihsel 44 · 2026-09-13 --> Beş tarayıcı vakası iki worker ile geçti. Bu sayılar kaynak koleksiyonu veya bütün iş akışlarının kabulü değildir. Ekran görüntülerinin ayrı görsel incelemesi aşağıda kaydedilir.

## Ekran matrisi

| Madde | Ekran / konu | Gözlenen yerel kontrol kayıtları |
|---|---|---|
| 1 | Ortak giriş | `public-login` |
| 2 | Parola bağlantısı | `public-forgot-password` |
| 3 | Yeni parola | `public-reset-password` |
| 4 | Gezinme | `teacher-dashboard`, `student-dashboard` |
| 5 | Genel bakış | `teacher-dashboard`, `student-dashboard` |
| 6 | Derslerim | `teacher-new-course`, `student-courses` |
| 7 | Ders rolü | `teacher-new-course`, `student-courses` |
| 8 | Materyaller | `teacher-course`, `student-course` |
| 9 | Katılımcılar | `teacher-members`, `student-denied-members` |
| 10 | Tam asistan | `teacher-chat`, `student-chat` |
| 11 | Kısa asistan | `student-assistant` |
| 12 | Asistan kimliği | `teacher-course`, `teacher-chat`, `student-course`, `student-assistant`, `student-chat` |
| 13 | Kaynak bağlamı | `teacher-context`, `student-context` |
| 14 | Retrieval laboratuvarı | `teacher-sources`, `student-denied-sources` |
| 15 | Soru havuzu | `teacher-questions`, `student-denied-questions` |
| 16 | Soru taslağı | `teacher-draft` |
| 17 | Blueprint | `teacher-blueprint`, `student-denied-blueprints` |
| 18 | Sınav başlangıcı | `student-exam-start` |
| 19 | Etkin sınav | `student-exam-running` |
| 20 | Sonuç ve geçmiş | `student-exam-result` |
| 21 | AI politikası | `teacher-policy`, `student-denied-settings` |
| 22 | AI kalite | `teacher-quality`, `student-denied-quality` |
| 23 | İlerleme ve analitik | `teacher-analytics`, `student-analytics` |
| 24 | Profil | `teacher-profile`, `student-profile` |
| 25 | Tema | `student-profile-dark-mobile` |
| 26 | Verilerim | `student-account` |
| 27 | Bilgi İşlem genel görünüm | `admin-overview` |
| 28 | Bilgi İşlem listeleri | `admin-users`, `admin-courses`, `admin-ai-records`, `admin-ingestion` |
| 29 | Bilgi İşlem klavye sözleşmesi | `admin-keyboard` |
| 30 | Platform rolü | `admin-overview`, `nonadmin-denied` |
| 31 | Kişisel veri kapsamı | `public-kvkk` |

Matristeki sonuç yalnız [ölçüm kaydında](evidence/l6-i2-guides.json) her ekran için yazılı iddiaları kapsar. Öğrenciye kapalı eğitmen sayfalarının ret görünümü ayrıca gözlendi. İşlevin görünmesi, kaydetme veya dış sağlayıcı işleminin tamamlandığı anlamına gelmez.

## Görsel inceleme

Kırk dört kaydın asıl PNG dosyaları tek tek açıldı; dosya özetleri ve somut gözlemler
[ölçüm kaydına](evidence/l6-i2-guides.json) bağlandı. Bunlar 43 benzersiz görüntü
özeti içerir: `admin-overview` ve `admin-users`, farklı kontrollerin aynı ekran
durumunu yakalamasıdır. İnceleme, insan kabulü veya WCAG sertifikası değildir.

| Kayıt | Açık görsel bulgu |
|---|---|
| `student-profile-dark-mobile` | 375px koyu profilin tam sayfa görüntüsünde sabit menü profil özetiyle örtüşüyor; sağ kenarda rol etiketi ve bazı metinler kesiliyor. Yatay taşma kontrolünün geçmesi bu bulguyu ortadan kaldırmaz. |
| `teacher-course` | 1440×1000 görünümde sabit Eğitmen Asistanı, İçerik önizle/Sil düğmelerinin alt kenarını kısmen örtüyor. Bu özel I2 görüntüsü, ayrı yenilenen H7 materyal görselinin yerine geçmez. 15 Eylül'de o materyal görseli `df60275` ile yeniden çekildi ("sabit kabuk çakışması olmadan"); çakışmanın giderilip giderilmediği bu belgede ölçülmedi — **not-run**, bkz. [screenshots.md](screenshots.md) 15 Eylül eki. |

Uzun tam sayfa görüntülerinde sabit menü ve asistan, çekim anındaki kaydırma
konumuna göre sayfanın ortasında kalabilir. Bulgular belirtilen çekim durumuna
aittir; her sayfanın veya bütün kaydırma konumlarının genel kabulü değildir.
Ürün yerleşimi bu belge işi kapsamında değiştirilmedi.

## Sınırlar ve önceki deneme

Gerçek Supabase girişi, parola e-postası ve kurtarma işlemi koşulmadı; ortak girişte yerel yapılandırmanın kapalı açıklamaları görüldü. Politika kaydı, katılımcı çıkarma, sohbet/hesap silme, veri indirme ve anonimleştirme yapılmadı. Taslak düzenleme ve blueprint formları açıldı; taslağı kaydetme, onaylama ve sınav yayımlama kabulü üretilmedi. Mobil koyu görünüm yalnız öğrenci profilinde incelendi; bütün ekranlar için erişilebilirlik veya responsive kabulü değildir.

İlk `i2-browser-01` denemesi, aynı hedefe giden iki bağlantı ve açıklamalı alan adları ile form dışında `form` niteliğiyle bağlanan kaydet düğmesinin seçicileri nedeniyle başarısızdı. Gerçek ekran ve kaynak yapısına göre runtime seçicileri düzeltildi; ürün kodu ve test kapıları değişmedi. İlk sonuç arşivde korunur.

[H7 görüntü üretim kaydı](screenshots.md), bu kılavuzlarda yenilenen seçili belge görsellerini listeler. I2 özel kanıt PNG’leri kılavuz görseli olarak yayımlanmadı; H7 dışındaki önceki görseller yenilenmiş sayılmaz.

**15 Eylül 2026 eki:** Yukarıdaki cümle 13 Eylül'ün durumudur ve olduğu gibi bırakıldı;
o tarihte doğruydu. 15 Eylül'de `docs/images` yeniden çekildi ve ayrım iki yönden de
geçerliliğini yitirdi: H7'nin sekiz sahnesi **dışındaki** kılavuz görselleri de
yenilendi, buna karşılık H7 kapsamı **içindeki** `images/10-sohbet-kapsam-disi-ret.png`
yenilenmedi. Yani "H7 dışındakiler yenilenmiş sayılmaz" cümlesi artık hangi görselin
güncel olduğunu belirlemek için kullanılamaz; dosya dosya git ölçümü
[screenshots.md](screenshots.md) "15 Eylül eki" bölümündedir.

Bu belgedeki ekran matrisi, sayılar ve görsel inceleme bulguları 13 Eylül I2 kanıt
PNG'lerine aittir ve 15 Eylül çekimi üzerinde **tekrarlanmadı**. Yenileme; insan kabulü,
WCAG AA uygunluğu veya erişilebilirlik kabulü değildir — yukarıdaki "Sınırlar ve önceki
deneme" bölümü aynen geçerlidir.
