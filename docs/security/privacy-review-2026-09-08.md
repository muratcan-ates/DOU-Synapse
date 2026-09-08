# Güvenlik ve kişisel veri incelemesi — 8 Eylül 2026

Kapsam: 017 tabanı `621815908d5372d8de414aec4ca1dc63da008dca`, 018 A kontrol noktası `2d1b58aeeddaa4b862a760fb46773b2ae73ed253` ve bunun üzerindeki S düzeltmeleri. İnceleme yerel kaynak, sentetik veri ve gerçek yerel API/tarayıcı üzerinden yapılır. Canlı öğrenci verisi veya üretim saldırı testi kullanılmadı. Bu belge hukuki uygunluk sertifikası değildir.

## Doğrulanmış bulgular

| Kimlik | Öncelik ve etki | Kanıt | Durum |
|---|---|---|---|
| S1.1 | Yüksek: büyük istekle bellek/geçici disk tüketimi | Upload önce sınırsız `file.read()` yapıyordu; dosya sınırı bundan sonra uygulanıyordu. FastAPI multipart ayrıştırması endpoint kimlik bağımlılığından önce gerçekleşir | Gövde ayrıştırma öncesi sınırlı; endpoint max+1 okur. Gerçek boş gövde executor istemez; negatif ve tam testler geçti |
| S1.2 | Orta: başarısız yüklemeden özel dosya kalması | Hatalı değiştirme hedefiyle 404 dönen sentetik istekte dosya depoya yazılmış, belge satırı oluşmamıştı | Hedef önce doğrulanır; kesin rollback sonrasında yalnız başarıyla yazılmış yeni nesne temizlenir; belirsiz sonuçta korunur |
| S1.3 | Yüksek: COMMIT reddinde mevcut belge dosyasının kaybı | Fiziksel DELETE flush sonrasındaydı; flush kalıcı COMMIT değildir | Silme kesin COMMIT sonrasına taşındı; gerçek API/DB success, deferred rejection ve cleanup failure testleri geçti |
| S1.4 | Orta: cleanup iptalinde tamamlanmamış nesnelerin kaydının kaybı | CancelledError önceki Exception dalına girmiyordu | İptal korunur; başarısız/iptal/başlanmamış nesnelerin sayısı içeriksiz sinyalle kaydedilir; negatif testle doğrulandı |
| S2.1 | Yüksek: paylaşılan cihazın başka sekmesinde eski özel görünüm | Çıkış yalnız çağıran sekmenin sessionStorage alanını temizliyordu; diğer sekmede kimlik/geçmiş/draft invalidation yoktu | İçeriksiz kimlik olayı, özel görünümün kaldırılması ve geç yanıt koruması; beş gerçek tarayıcı senaryosu geçti |
| S2.2 | Orta: eski sohbet mesajlarının yeni konuşmaya karışması | `use-reverse-history` eski loadOlder yanıtında oturum/nesil kontrolü yapmıyordu; mevcut test bu davranışı bekliyordu | Başarı/hata yanıtları oturum nesline bağlandı; reset/unmount/kimlik değişiminde eski yanıtlar yok sayılıyor |
| S2.3 | Orta: başka sekmede başlayan sınav sonrası eski yardımın görünmesi | Sunucu yeni istekleri reddediyor; kaynak okuyucusu ve sohbet yüzeyinin istemci yenilemesi aynı kapsamda değil | İçeriksiz sınav olayı ve yeniden doğrulama eklendi; üç gerçek tarayıcı senaryosu geçti |
| S3.1 | Orta: silme/anonimlik konusunda yanıltıcı kullanıcı açıklaması | `/me` aynı UUID, cevaplar ve mastery bağlantısını koruyor; UI “anonim profil” ve doğrulanmamış mevzuat gerekçesi söylüyordu | Profil alanı kaldırma kapsamı ve korunan kayıtlar açıkça anlatılıyor |
| S3.2 | Düşük: export tip sözleşmesi eski | API sürüm2 ve not_included, web tipi sürüm1 | Tip ve gerçek JSON indirme testi güncellendi; indirme gövdesinin daha önce eksiltildiği iddia edilmiyor |
| S3.3 | Orta: kamuya açık gizlilik açıklaması güncel değil | Gerçek auth ve veri hakkı ekranı yok deniyordu; paylaşım tercihi, değerlendirme çağrıları ve saklanan kopyalar eksikti | `docs/kvkk.md` gerçek davranışla yenilendi; eksik kurumsal kararlar açık bırakıldı |
| S5 | Orta: eksik issuer yapılandırması sessizce kabul edilebilir | `jwt_issuer` yapılandırılabilir; üretim Settings doğrulayıcısı varlığını zorlamıyor | Üretim başlangıcı ve JWT tüketicisi sertleştirildi; negatif ayar/token testleri geçti |
| S6 | Kullanılabilirlik: gerçek auth bağlantısı CSP tarafından kesilebilir | Web connect-src yalnız self ve API; farklı Supabase origin'i eklenmiyor | Yapılandırılmış API/Supabase origin doğrulaması eklendi; CSP testleri geçti |
| S7 | Orta: özel depo konumlarının günlüklerde görünmesi | Sentetik MockTransport ile altı save/load/delete başarı/hata durumunda proje/bucket URL'si; save/load'da nesne anahtarı emitted JSON loguna girdi | HTTP tanı logları ve istisna zinciri daraltıldı; emitted log ve üst worker zinciri testleri geçti; fixture'da dosya gövdesi veya servis anahtarı sızıntısı bulunmadı |

B4 devam bulgusu: olay bariyerleri kullanan gerçek async API testinde, henüz commit edilmemiş yeni sohbet ders/tüm geçmiş/profil silme sorgusuna görünmüyor. DELETE 200 sonrasında bekletilen model yanıtı serbest bırakıldığında 1 oturum ve 2 mesaj kalıcılaşıyor. Üç negatif vaka mevcut kodda başarısız; mevcut tekli oturum silinmesi yeniden kayıt oluşturmuyor. Bu S2 arayüz iptaliyle kapanmış sayılmadı; kapsam bazlı kalıcı silme nesli ve model sonrası son kontrol B4 sunucu işine eklendi. [Yeniden üretilebilir test ve tasarım](../../specs/018-codex-production-line/evidence/b4-race-design.md), [kaynak hashleri](../../specs/018-codex-production-line/evidence/b4-race-evidence-hashes.json) ile saklanır. S düzeltmeleri bu yarışın düzeltmesi olarak sunulmaz.

Öncelikler bu kullanım senaryosuna göre değerlendirmedir; CVSS puanı ölçülmedi. İstemcide gizli kalan görüntü, yeni API isteğinin yetkilendirilmesiyle aynı sınır değildir.

Başlangıç kaynakları kesin A commit'ine bağlıdır: [sınırsız upload okuması](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/api/app/api/documents.py#L76), [doğrulamadan önce dosya yazımı](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/api/app/api/documents.py#L98), [yerel sekme temizliği](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/web/lib/api.ts#L74), [geç geçmiş yanıtı](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/web/lib/use-reverse-history.ts#L160), [profil alanı işlemi](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/api/app/api/privacy.py#L272), [eski export tipi](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/web/lib/privacy.ts#L2), [üretim auth ayarı](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/api/app/core/config.py#L347), [CSP bağlantı listesi](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/web/lib/security-headers.ts#L46), [depo istisna logu](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/api/app/modules/ingestion/storage.py#L126).

## Veri kopyaları ve işlemlerin gerçek kapsamı

| Kopya | Mevcut kontrol | Kalan iş |
|---|---|---|
| Profil ve üyelik | Sahip/rol kontrolü; profil alanı kaldırma ve üyelik iptali | Aynı UUID geri bağlanabilir; resmi saklama ve kimlik hesabı kapatma süreci |
| Sohbet ve paylaşılmış inceleme alıntısı | Sahiplik, açık paylaşım tercihi, cascade silme | Silme eyleminin bütün açık sekmelere yansıması; süre bazlı politika |
| Sınav cevabı, değerlendirme, mastery | Sahip filtreleri, RLS ve aktif sınav kilidi | Serbest metin dahil kategori bazlı saklama/erasure kararı ve uygulaması |
| Orijinal dosya, chunk ve vektör | Ders üyeliği, özel depo, dosya boyutu/tür sınırı | Dosya/DB işlemi tek atomik işlem değil; belirsiz sonuç, process crash ve cleanup hatası için uzlaştırma |
| Ders cevap önbelleği | Ders/audience/policy/prompt/corpus kapsamı; guardrail sonrası yazma | Kullanıcı metninden türeyen kişisel içeriğin kalıcılığını ve imha kapsamını ölçme |
| Tarayıcı taslağı ve bellek | Kullanıcı/ders/oturum kapsamı | Çıkış, kullanıcı değişimi ve geç yanıt testleri; önceden indirilmiş dosyalar geri çağrılamaz |
| Ölçüm, quota, güvenlik ve yönetim kayıtları | Ham prompt yerine kimlik/olay verileri; maskeleme | Kimlikli kayıtlar için amaç/süre; exception/proxy/provider günlükleri ayrıca incelenmeli |
| LLM/kimlik/depo sağlayıcısı | Yapılandırılmış adaptörler, yetki kontrolleri | Sözleşme, bölge, saklama/eğitim ayarı, alt işleyen ve aktarım kanıtı |
| Yedek ve dışa aktarımlar | Depoda runbook ve yerel mekanik kontroller | Gerçek şifreleme, erişim, restore, süre ve restore sonrası imha tatbikatı |

## Kurum tarafından tamamlanacak kararlar

KVKK teknik/idari güvenlik tedbirleri yalnız koddaki test sayılarıyla karşılanmış sayılmaz. Sorumlu birim, erişim yönetimi ve işletme süreçleri de gerekir. [KVKK veri güvenliği yükümlülükleri](https://www.kvkk.gov.tr/Icerik/2040/Veri-Guvenligine-Iliskin-Yukumlulukler).

İşleme sebepleri ortadan kalkan verilerin silinmesi, yok edilmesi veya anonimleştirilmesi; tutulan akademik kayıtların dayanağı ve imha politikasıyla birlikte ele alınmalıdır. Teknik pseudonymization tam anonimlik değildir. [KVKK silme/yok etme/anonimleştirme açıklaması](https://www.kvkk.gov.tr/Icerik/2038/kisisel-verilerin-silinmesi-yok-edilmesi-veya-anonim-hale-getirilmesi).

Yurt dışı aktarım için yalnız “hizmet gereği” açıklaması yeterlilik kanıtı değildir; gerçek veri akışı ve uygulanabilir mekanizma kurumsal incelemeye sunulmalıdır. Güncel KVKK çerçevesi standart sözleşme ve diğer güvenceleri içerir. [KVKK yurt dışı aktarım](https://www.kvkk.gov.tr/Icerik/2053/Yurtdisina-Aktarim), [resmî aktarım rehberi](https://www.kvkk.gov.tr/Icerik/8143/Kisisel-Verilerin-Yurt-Disina-Aktarilmasi-Rehberi).

| Karar | Hazırlanacak somut kayıt | Sahip/durum |
|---|---|---|
| Veri sorumlusu/işleyen ve başvuru kanalı | Resmî unvan, iletişim, görev dağılımı | Kurum tarafından atanmalı |
| Kategori bazında amaç ve hukuki sebep | Profil, sohbet, sınav, telemetry ve materyal envanteri | Kurum/hukuk incelemesi bekler |
| Saklama ve imha | Kategori, süre, dayanak, istisna, silme yöntemi ve denetim kanıtı | Süre uydurulmadı |
| Sağlayıcı ve yurt dışı aktarım | Bölge, DPA/ilgili sözleşme, alt işleyen, eğitim/saklama ayarları | Gerçek hesap kanıtı bekler |
| Hak talepleri | Kimlik doğrulama, kapsamlı erişim/erasure iş akışı, yanıt ve takip | Mevcut hesap işlemleri kısmi |
| İhlal müdahalesi | İç sorumlu, değerlendirme, bildirim kararı, delil koruma | Kuruma ve uygulanabilir mevzuata göre tamamlanmalı |
| GDPR kapsamı | Kullanım/coğrafya/veri sorumlusu temelinde kapsam analizi | Teknik rapor otomatik uygulanabilirlik veya uygunluk kararı vermez |

GDPR için resmî mevzuat kaynağı: [Regulation (EU) 2016/679](https://eur-lex.europa.eu/legal-content/EN/TXT/?qid=1673360464141&uri=CELEX%3A32016R0679). Bu incelemede KVKK ve GDPR için tek bir evrensel saklama ya da ihlal bildirim süresi varsayılmadı.

## Kanıt ve sınırlamalar

A kontrol noktası: 1212 API testi, 432 web birim testi, 42 farklı gerçek HTTP tarayıcı akışı; ayrı koşuda düzeltilen bir seçici. Uygulama mutasyonları 12/12 yakalanıp geri yüklenmiştir. Kesin komutlar ve ortam [018 doğrulamasında](../../specs/018-codex-production-line/verification.md), içeriksiz sürümlü sonuçlar `.ai/evidence/025-*` altındadır. Bu kanıt S uygulaması öncesine aittir. Son S kaynaklarında1332 API,501 web ve tek koşuda50 gerçek HTTP tarayıcı testi geçti; yeni sonuç ve sınırlamalar [018 S doğrulamasında](../../specs/018-codex-production-line/verification.md) saklanır. A commit'inin GitHub API, web, belge, Docker/embedding, gerçek tarayıcı, AI yönetişim, güvenlik ve beceri kontrolleri geçti; [koşu kimlikleri](../../specs/018-codex-production-line/evidence/a-hosted-ci.json) saklanır.

Canlı JWT/Supabase Storage kullanıcı politikası, sağlayıcı gizlilik ayarları, internetten erişilen dağıtım, restore/rollback ve insan kalite kabulü bu aşamada doğrulanmadı. İncelenen dosyalarda bir kusurun görülmemesi, bütün olası zafiyetlerin yokluğunu kanıtlamaz.
