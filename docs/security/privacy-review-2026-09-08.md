# Güvenlik ve kişisel veri incelemesi — 8 Eylül 2026

Kapsam: 017 tabanı `621815908d5372d8de414aec4ca1dc63da008dca`, 018 A kontrol noktası `2d1b58aeeddaa4b862a760fb46773b2ae73ed253` ve bunun üzerindeki S/B/C, yerel D1/D2/D3 ve S8 düzeltmeleri. 9af4122 hosted kontrol noktası sonraki kirli kaynakların uzak kabulü değildir. İnceleme yerel kaynak, sentetik veri ve gerçek yerel API/tarayıcı üzerinden yapılır. Canlı öğrenci verisi veya üretim saldırı testi kullanılmadı. Bu belge hukuki uygunluk sertifikası değildir.

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

S8 yerel ek: app.request ham rota kimliğini yazıyordu; Uvicorn erişim kanalı ham yol/sorgu/istemci bilgisi taşıyabiliyordu. Kaynakta rota şablonu veya sabit `<unmatched>` ve uvicorn.access kanalını kapatma eklendi; 21 ASGI kontrolü geçti. Kurulu Uvicorn sürümü 0.52.4'tür. Gerçek Uvicorn v1 baseline sonrası fixture kapanışında başarısız oldu; bu sonuç korunur. V2'de eski/yeni kaynakların her birine üç gerçek HTTP isteği gönderildi. Eski kaynakta bulunan dört ham canary adayda yoktu, erişim kayıtları üçten sıfıra indi ve başlangıç/kapanış kayıtları korundu. İki süreç de temiz kapandı; DB bağlantısı denenmedi. Bu yerel deneyi yeni hosted, dış proxy günlükleri veya genel anonimlik kabulü olarak kullanmayın.

B4 devam bulgusu: olay bariyerleri kullanan gerçek async API testinde, henüz commit edilmemiş yeni sohbet ders/tüm geçmiş/profil silme sorgusuna görünmüyor. DELETE 200 sonrasında bekletilen model yanıtı serbest bırakıldığında 1 oturum ve 2 mesaj kalıcılaşıyor. Üç negatif vaka mevcut kodda başarısız; mevcut tekli oturum silinmesi yeniden kayıt oluşturmuyor. Bu S2 arayüz iptaliyle kapanmış sayılmadı; kapsam bazlı kalıcı silme nesli ve model sonrası son kontrol B4 sunucu işine eklendi. [Yeniden üretilebilir test ve tasarım](../../specs/018-codex-production-line/evidence/b4-race-design.md), [kaynak hashleri](../../specs/018-codex-production-line/evidence/b4-race-evidence-hashes.json) ile saklanır. S düzeltmeleri bu yarışın düzeltmesi olarak sunulmaz.

B4 sunucu ve arayüz düzeltmesi artık yerel olarak doğrulandı: silme kapsamı için kalıcı sürüm, kısa son-yazım kilidi ve taze üyelik/oturum denetimi eklendi. Yeni oturum model beklerken veritabanına eklenmez. 34 odaklı yarış/RLS kontrolünün ardından B4 ara adayının 1500 API ve 68 gerçek HTTP tarayıcı testi geçti. Son daraltılmış B/C adayında1499 API,555 web ve68 tarayıcı testi ile kesin9af4122 HEAD GitHub kapıları geçti. Tekli/ders silme, hata/iptal, diğer sekme, kaçırılan olay ve geç yanıt senaryoları doğrulandı. Üstteki negatif kayıt tarihsel başlangıçtır; S tek başına bu yarışı kapatmış sayılmaz. Kesin yeni adayın uzak CI kabulü ayrıca kaydedilir.


Öncelikler bu kullanım senaryosuna göre değerlendirmedir; CVSS puanı ölçülmedi. İstemcide gizli kalan görüntü, yeni API isteğinin yetkilendirilmesiyle aynı sınır değildir.

Başlangıç kaynakları kesin A commit'ine bağlıdır: [sınırsız upload okuması](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/api/app/api/documents.py#L76), [doğrulamadan önce dosya yazımı](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/api/app/api/documents.py#L98), [yerel sekme temizliği](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/web/lib/api.ts#L74), [geç geçmiş yanıtı](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/web/lib/use-reverse-history.ts#L160), [profil alanı işlemi](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/api/app/api/privacy.py#L272), [eski export tipi](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/web/lib/privacy.ts#L2), [üretim auth ayarı](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/api/app/core/config.py#L347), [CSP bağlantı listesi](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/web/lib/security-headers.ts#L46), [depo istisna logu](https://github.com/muratcan-ates/DOU-Synapse/blob/2d1b58aeeddaa4b862a760fb46773b2ae73ed253/apps/api/app/modules/ingestion/storage.py#L126).

## Veri kopyaları ve işlemlerin gerçek kapsamı

| Kopya | Mevcut kontrol | Kalan iş |
|---|---|---|
| Profil ve üyelik | Sahip/rol kontrolü; profil alanı kaldırma ve üyelik iptali | Aynı UUID geri bağlanabilir; resmi saklama ve kimlik hesabı kapatma süreci |
| Sohbet ve paylaşılmış inceleme alıntısı | Sahiplik, açık paylaşım tercihi, cascade silme | Sekme olayı ve focus/pageshow yeniden denetimi S/B testleriyle doğrulandı; süre bazlı politika ve dış kopyalar açık |
| Sınav cevabı, değerlendirme, mastery | Sahip filtreleri, RLS ve aktif sınav kilidi | Serbest metin dahil kategori bazlı saklama/erasure kararı ve uygulaması |
| Orijinal dosya, chunk ve vektör | Ders üyeliği, özel depo, dosya boyutu/tür sınırı | Dosya/DB işlemi tek atomik işlem değil; belirsiz sonuç, process crash ve cleanup hatası için uzlaştırma |
| Ders cevap önbelleği | Ders/audience/policy/prompt/corpus kapsamı; guardrail sonrası yazma | Kullanıcı metninden türeyen kişisel içeriğin kalıcılığını ve imha kapsamını ölçme |
| Tarayıcı taslağı ve bellek | Kullanıcı/ders/oturum kapsamı | Çıkış/kullanıcı değişimi/geç yanıt testleri geçti; bütün cihazlar veya önceden indirilmiş dosyalar geri çağrılamaz |
| Sohbet silme kapsam sürümü | Yalnız hesap/ders kimliği ve artan sayaç; soru/cevap veya silme zamanı yok, sahip RLS | Profil satırı veya ders fiziksel silinince cascade; profil alanı kaldırmak bu sayacı silmez. Onaylı saklama/imha politikası ayrıca gerekir |
| Ölçüm, quota, güvenlik ve yönetim kayıtları | Ham prompt yerine kimlik/olay verileri; maskeleme | Kimlikli kayıtlar için amaç/süre; exception/proxy/provider günlükleri ayrıca incelenmeli |
| LLM/kimlik/depo sağlayıcısı | Yapılandırılmış adaptörler, yetki kontrolleri | Sözleşme, bölge, saklama/eğitim ayarı, alt işleyen ve aktarım kanıtı |
| Yedek ve dışa aktarımlar | Yerel restore, güncel 22 göçlü veri/rol/RLS eşliği ve kontrollü hata deneyleri | Dış Storage, bulut erişimi, şifreleme, süre ve restore sonrası imha tatbikatı |

## D operasyon dilimi — devam eden doğrulama

PostgreSQL ortak istek kotası yerel kaynaklara entegre edildi.10 gerçek SQL senaryosuna ek olarak iki gerçek HTTP sürecinde 55 istekle ortak bütçe, rol/kapsam reddi,503/Retry-After ve ayrı kontrol COMMIT'i doğrulandı. D2'nin gerçek worker başlangıcı, aynı sentetik kullanıcı/dersin süresi dolmuş kota satırını silerken canlı satırı korudu. Tekrar planlama birimi kontrollü bekleme sınırını sınar; gerçek 60 saniyelik dönem, scale-to-zero zamanlayıcı veya onaylı fiziksel saklama SLA'sı değildir. Readiness ve worker bakım hata kayıtları sabit içeriksiz tür/aşama kullanır.

Kota kaydı kullanıcı/ders kimliği ve zaman dizisi içerir; anonim ölçüm değildir. `app.rate_limit_windows` için içerik/IP/başlık/token saklanmaz; `app.request_rate_policies` yalnız kanonik politika taşır. Süre sonu yalnız mantıksal uygunluktur; başarıyla çalışan sınırlı bakım veya profil/ders FK silinmesi fiziksel temizler. Üyeliğin kapanması ya da profil alanlarının kaldırılması bütün bu veriyi hemen silmez. Export bu kaydı açıkça kapsam dışında listeler; kapsamlı erişim talebi ve onaylı saklama kararı ayrıca gerekir. Yedekler ayrı kopyadır.

Veritabanındaki request_logs ile uygulama stdout'u farklı akışlardır. D2v2'nin gerçek eski-kaynak ölçümünde yalnız bilinen upload rota UUID'si parent metadata alanında görüldü; içerik/auth/DSN/parola ve diğer alanlarda kimlik eşleşmesi yoktu. Bu anonimlik kanıtı değildir. S8 sonradan raw path yerine rota şablonu yazar; request_id, method, status, duration_ms ve zaman bilgisi kalır. Log toplayıcıya erişen roller, saklama ve silme mekanizması seçilmiş dağıtımda ayrıca doğrulanmalıdır.

İlk belge işleyici deneyinde iptal/SIGTERM sonrası processing durumunda takılma ve409 retry reddi ölçülmüştü. Lease/token ve kaynak revizyonuna bağlı son yazım düzeltmesi artık yerel entegredir; stage02'de 98 test, gerçek süreç v2'de 8 senaryo geçti. V1 süreç koşusunun sekiz davranışı geçip parent gizlilik denetiminden kalan genel failed sonucu korunur. Bu, dış sağlayıcıda exactly-once veya bloke parser thread'i için kesin kapanış süresi taahhüdü değildir. İlk birleşik tam API koşusunun 1560 geçti/1 kilit-gözlem testi başarısız sonucu korunur. İstatistik görüntüsünü yenileyen dar test düzeltmesi geçti; yenileme kaldırılınca başarısız, geri konunca tekrar başarılı oldu. Son birleşik 1561 API testi geçti. Yeni tarayıcı/dossier/commit/hosted kabulü ayrıca gerekir.

D3v4'ün eski kaynakla 29 ilişki ve kontrollü hata kabulüne ek olarak, güncel 22 göçlü sentetik kaynakta yedek/restore yapıldı:30 ilişkinin toplam 14 satırı, güvenlik kataloğu ve rol bileşeni eşleşti. Gerçek dou_app eğitmen/dış kullanıcı ayrımı ve iki kota tablosuna42501 erişim reddi doğrulandı. İlk başarısız adaylar ve kapalı belirsiz hedefler korunur. Kısıtlı role yeni CREATE yetkisi verilmedi.07 eşzamanlı yazıcı, cross-cluster/control-loss ve ek rol grafiği deneyleri açık; dış Storage kopyalanmadı. Canlı yedek hizmeti, bulut yetkileri, şifreleme/saklama/imha ve restore sonrası silme uzlaştırması bu sonuçlarla onaylanmış sayılmaz. Güncel arşiv hedefi `specs/018-codex-production-line/evidence/d-final-local/`; yeni D/S8 kaynaklarının dossier/commit/hosted kabulü ayrıca gerekir.

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

Canlı JWT/Supabase Storage kullanıcı politikası, sağlayıcı gizlilik ayarları, internetten erişilen dağıtım, canlı restore/rollback ve insan kalite kabulü bu aşamada doğrulanmadı. Yerel sentetik restore ve hata kabulü yukarıdaki kapsamla sınırlıdır. İncelenen dosyalarda bir kusurun görülmemesi, bütün olası zafiyetlerin yokluğunu kanıtlamaz.
