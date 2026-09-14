# CourseGPT tamamlama programı

Kullanıcı 8 Eylül 2026'da Codex ve Claude çalışmalarının birleştirilmesini ve geliştirmeye devam edilmesini istedi. Hocanın e-postası ürün gereksinimi; runbook uygulanmadan önce kodla karşılaştırılan iş önerisidir.

## Güncel çalışma

Aşağıdaki başlangıç ve kanıt kayıtları 8–9 Eylül 2026 tarihli 018 entegrasyon çalışmasına aittir. 13 Eylül L6 devamı `018-l6-frontend-docs` dalında yürür ve taslak PR hedefi `018-codex-production-line` olur; eski taban SHA'sı veya test sonuçları yeni L6 adayının kabulü değildir. Güncel kuyruk için [Codex runbook v2](team/codex/CODEX-RUNBOOK.md) ve [birleşik plan](team/codex/40-BIRLESIK-PLAN.md) okunur; L6'nın özel sahiplik, dossier ve işlem sırası kendi iş talimatından gelir.

### Tarihsel başlangıç — 8 Eylül 2026

O tarihteki dal `018-codex-production-line`; çalışma ağacı `/Users/muratates/code/dou-synapse-018-codex-production-line`. Kesin taban `621815908d5372d8de414aec4ca1dc63da008dca` (`017-completion-integration`), 8 Eylül'de GitHub ile eşleştirildi. 013/014/015 ürün dilimleri, 016 beceriler, Codex017 düzeltmeleri ve Claude'un0020/CI/runbook katkıları tabanda zaten birleşik. Yeni dal bu geçmişi korur. Ana dal veya canlı ortam birleşimi yapılmadı.

Başlangıçta eski defter 016'da kalmıştı. Tarihsel kanıtlar [015](../specs/015-completion-program/verification.md), [016](../specs/016-agent-skills/verification.md) ve [017](../specs/017-completion-integration/verification.md) kayıtlarında korunur; bu adayın sonucu sayılmaz. Geçici017 kanıt klasörü artık yok; eski geçici yollar yeni sonuç olarak kullanılmaz.

018 entegrasyonunun kabul/sahiplik kaydı: [018 spec](../specs/018-codex-production-line/spec.md), [plan](../specs/018-codex-production-line/plan.md), [iş listesi](../specs/018-codex-production-line/tasks.md), [doğrulama](../specs/018-codex-production-line/verification.md).

## Birleştirilmiş iş kuyruğu

| İş | Kodla doğrulanan durum | Sonraki kabul |
|---|---|---|
| A1–A3 CI ve yönetişim | A commit’i 2d1b58a üzerinde yerel ve GitHub CI doğrulandı | Release testleri/uygulama mutasyonları CI adımı; hassas kapılar; hata yutma ve izin genişlemesi negatif testte reddedilir |
| A4/A7 sınav testleri | Yerel birim ve gerçek HTTP akışı geçti | Dört koşullu skip yerine gerçek iddia; monoton ipucu geçmişi; sınavdan önceki gecikmiş200 yeni kilidi açamaz |
| A5 test sağlamlığı | 224 test geçti; 9 mutanttan 8 yakalandı, biri bağımsız RLS ile korundu | Gerçek yardımcı/CLI/export/sonuç kilidi davranışı; aynı test üretim koruması kaldırılınca düşer |
| A6 erişilmeyen kod | Üç kullanılmayan yardımcı kaldırıldı; kullanılan yollar korundu | Retry sınıf-adı yolu, kapsam reddi ve gerçek sources/inspect çağrısı test edilir |
| S1–S7 güvenlik/gizlilik | S71d5ff6 kendi kanıtı; son S/B/C9af4122 üzerinde dört GitHub workflow başarılı | Kurumsal kararlar ve kalıcı cleanup/uzlaştırma açık |
| S8 günlük minimizasyonu | Rota şablonu, Uvicorn erişim kanalı sınırı,21 ASGI ve gerçek Uvicorn v2 kabulü; önceki D/S8 c45 hosted kapıları geçti | V1 başarısız kayıt korunur; dış proxy/hosting günlükleri açık. OPS/D6 kendi f79d8a2 hosted kabulünde; yeni S9 kaynakları ayrı |
| S9/S9B/S9C hata günlükleri | Son errors + güvenli handler entegre; ayrı aşamalarda 18/35/27 PASS, sekiz karşılaştırma kolu ve gerçek dört kolda 16 süreç/20 HTTP kabulü | İlk 1651/38 sonucu ve sonraki maskeleme regresyonu kaydı korunur. Son kaynakta 1655 API/38 alt vaka, dört kırmızı/yeşil kimlik vakası ve 84 yeni kontrol birlikte geçti; yeni kesin commit hosted kapıları bekler. İstemci kimliği/S10, collector ve kurumsal saklama açık |
| S10 destek kimliği ve test sahipliği | Sunucu UUID4, dar iç-tip maskeleme, eksiksiz audit muhasebesi ve owned süreç kapanışı;1688 API/38,573 web,134 izole,56 HTTP ve son71 E2E geçti | Yerel435 kaynak bağlı; gerçek CI Docker/hosted ve dış collector kabulü ayrı; kamuya gönderim onay bekler |
| B1 öğrenme çıktısına konu | Konu seçimi, kaydetme ve yeniden okuma gerçek API/tarayıcıda geçti | İsteğe bağlı konu seçilmezse konusuz dağılım grubu korunur |
| B2 konu/blueprint ile sınav | 014'te zaten vardı; mevcut gerçek öğrenci akışı tekrar geçti | Yeni özellik olarak sayılmaz |
| B3 açık/kod değerlendirme | Geçerli kod rubriği, ölçüt puanlama ve kaynaklı eksik ölçüt API/UI sözleşmesi geçti | Gerçek LLM doğruluğu ve insan pedagojik kabulü E'de açık; tarayıcı geri bildirimi kontrollü DB fixture'ı |
| B4 kişisel sohbet silme | Tekli/ders UI; kalıcı kapsam sürümü; model sonrası son-yazım kilidi; yarış/RLS/sekme testleri geçti | Bütün veri kopyalarının imhası veya auth hesabının kapanması değildir; aktif sınav yardım kilidi korunur |
| B5 politika geçmişi | Önce/sonra, sayfalama, hata ve kimlik/rol geçişinde taslak sınırları gerçek API/tarayıcıda geçti | Actor kimliğinden kişi adı uydurulmaz; aynı kullanıcı RAM taslağı kalıcı kayıt değildir |
| B6 blueprint özellik bayrağı | Kapalı authoring açıklaması ve uygun havuzdan gerçek readiness/publish geçti | False görünümü tarayıcı capability yanıtında simüle edildi; ayrı false-env deployment kanıtı değil |
| B7 soru süzgeçleri | Sunucu durum/konu filtreleri, imleç/boş liste/geç yanıt ve silme bildirimi doğrulandı | Yüklenmiş sayfa adedi bütün sonuç toplamı gibi sunulmaz |
| C1 retrieval adayı | ANN/dense custom plan korunarak FTS hash sıralaması geri çekildi; son hashing ve gerçek E5 karşılaştırmasında non-regression geçti | Hashing 78/105, E5 93/105; iki baseline ile eşit. RLS kapalı deney, CI0.8.6 ölçüm eşdeğerliği ve FTS yeniden yükleme eşitliği açık |
| C2 indeks yapım göçü | Bellek taşması→recall kaybı nedenselliği henüz gösterilmedi | Kontrollü bellek/build deneyi olmadan 0021 veya 2 GB zorunluluğu eklenmez |
| C3 rapor | Başarısız birleşik aday, çapraz tanı ve daraltılmış son kaynak ölçümü ayrı arşivlendi | [Son arama kabulü](../specs/018-codex-production-line/evidence/c1-final-acceptance.md); gerçek E5 retrieval ölçümü LLM cevap/puanlama kabulü değildir |
| D operasyon | D1/D2 ve güncel 22-göçlü D3 önceki kabulleri c45 kontrol noktasında; yeni OPS API 1571/38 alt vaka, tarayıcı 71, gerçek kota dönemi02 ve dört yerel D3 negatif geçti. OPS1/2 kaynakları ve D6 belgeleri/poller entegre | OPS f79d8a2 kesin HEAD: dört workflow/beş CI işi PASS. Docker/scale-to-zero, kurumsal saklama, D3 kalan matris ve dış işletim kabulü açık |
| E gerçek model kabulü | Sahte sağlayıcı sözleşme kanıtları var | Gerçek sağlayıcı bütçesi/erişimi, bağımsız insan etiketleri ve gerçek kalite raporu |
| F auth/private storage | Yerel issuer/JWT/CSP sınırları doğrulandı | Gerçek kullanıcı oturumu, seçilmiş imza yolu ve kullanıcı JWT'siyle Storage RLS ayrı sınanır |
| G dağıtım | Canlı hedef seçilmedi | İncelenebilir migrate/deploy/rollback paketi; gerçek hedef ve yetkiyle canlı tatbikat |
| H erişilebilirlik/E2E | Önceki B68 ve yeni OPS71 tarayıcı kabulü; yönetim375/1440 açık/koyu dört gerçek API görünümü, yatay taşma yokluğu ve ArrowRight/Home klavye dumanı geçti | Yeni 3 E2E vakanın 2’si kontrollü UI yanıtı. Tüm sayfaların axe/manuel/VoiceOver kabulü ayrı açık |
| I belge ve kılavuzlar | Öğrenci/eğitmen/Bilgi İşlem kılavuzları B1–B7 ve S10 ile güncel; kaynak/link denetimi; API/OpenAPI ve gizlilik envanteri hizalı | Tarihsel ekranlar yenilenmedi; gerçek model başarı raporu ve dış kabul açık |

## Ortam ve doğrulama sınırları

Bu göreve özel PostgreSQL16 localhost55448; dou018_* test veritabanları; önceki B/C tarayıcı DB’si dou_synapse_e2e_dou018, son D tarayıcı DB’si dou018_d_e2e_01; API8018/web3118. Fake LLM ve hashing yalnız mekanik doğrulama içindir. Ayrı sentetik korpusta mevcut yerel E5 önbelleğiyle gerçek embedding retrieval karşılaştırması da yapıldı; model indirilmedi ve LLM çağrılmadı. Mevcut sır veya .env kullanılmadı. Yerel pgvector0.8.0 ile CI0.8.6 sürüm farkı retrieval ölçümünde açık tutulur.

## Dış girdiler ve devam

Groq/Gemini erişimi, Supabase proje bilgileri, JWT imza tercihi, bulut/staging hedefi ve branch protection henüz verilmedi. İlgili somut paket hazır olduğunda gereken karar sorulur; diğer hazır işler sürer. İnsan etiketleri boş kalır. Yeni bağımlılık önerileri ve migration-runner tablo kararı kendi diliminde gerekçelendirilir. Bu depo kaydı tek başına zamanlayıcı değildir. Kullanıcının 8 Eylül kesintisiz devam isteği için uygulamada ayrıca 15 dakikalık heartbeat kuruldu; 9 Eylül 2026 03.45 Europe/Istanbul sonuna kadar bu görevin bağlamında sürer. Yerel bilgisayar ve uygulamanın açık kalması gerekir. Bu plan gerçek çalışma süresi veya bitiş garantisi değildir.

## Önceki B/C ve D/S8 kontrol noktaları

Aşağıdaki ara sonuçlar kendi kaynak sürümlerine aittir. Bu bölümlerde o tarihte açık olan işler yeni OPS kabulüne taşınmaz; güncel durum sonraki devam bölümündedir.

B/Cdc7a768 ve aggregate028/9af4122 PR26'ya push edildi; kesin HEAD'in CI, AI quality, agent skills ve security/dependency workflow'ları geçti. [GitHub makbuzu](../specs/018-codex-production-line/evidence/bc-hosted-exact-head-final.json) sonraki yerel D/S8 kaynaklarını kapsamaz.

D1'in iki gerçek HTTP sürecinde 55 isteği, D2 stage02'nin 98 testi ve süreç v2'nin 8 senaryosu geçti. İlk D2 süreç koşusu sekiz davranışı geçmesine rağmen genel parent gizlilik denetiminden kaldı; başarısız sonuç korunur. Worker başlangıçta süresi dolmuş kota satırını temizlerken canlı satırı korudu; gerçek 60 saniyelik dönem veya scale-to-zero saklama garantisi ölçülmedi. D3'ün eski kaynakla 29 ilişki/20000 vektör ve hata deneylerine ek olarak, güncel 22 göçlü kaynakla 30 ilişkinin toplam 14 satırı ve güvenlik kataloğu/rol eşliği doğrulandı. Gerçek eğitmen ve dış kullanıcı RLS ayrımı ile kota tablolarına 42501 reddi geçti; dış Storage kopyalanmadı.

Kaynaklar yerel çalışma ağacına entegredir. İlk birleşik tam API koşusunun 1560 geçti/1 başarısız sonucu korunur. Worker kilit gözlemcisinde her okumadan önce istatistik görüntüsünü yenileyen dar test düzeltmesi geçti; bu yenileme kaldırıldığında aynı kontrol başarısız, geri konduğunda yeniden başarılı oldu. Üretim kodu bu düzeltmede değişmedi. Son tam API koşusunda 1561 test geçti: 102.75 s pytest, 113.344 s kurulumla birlikte; kaynak hashleri koşu boyunca değişmedi. S8'in 21 ASGI kontrolüne ek olarak gerçek Uvicorn v2'de eski/yeni kaynakların her birine üç HTTP isteği geçti; adayda dört ham canary ve erişim kanalı kaydı yoktu, başlangıç/kapanış günlükleri korundu ve DB bağlantısı denenmedi. V1'in baseline sonrası fixture kapanış hatası ayrı korunur. Son 68 gerçek tarayıcı akışı82.187 saniyede geçti; mtsqcmai1b9f koşusunun65 ders/8 audit kaydı temizlendi. İlk adres eşleme hatası ve düzeltmesi ayrı korunur. Yerel kabul tamamlandı; ayrı dossier/commit ve kesin yeni HEAD’in hosted kapıları PR26 üzerinde izlenir. D3'te 07 eşzamanlı yazıcı, cross-cluster/control-loss ve kurumsal saklama/imha; C1 kalan matris hücreleri ve D–I canlı/insan kabulleri açık kalır. Arşiv hedefi `specs/018-codex-production-line/evidence/d-final-local/`; her devirde gerçek HEAD, kirli kaynaklar ve uzak durum yeniden kontrol edilir.

## Güvenlik ve gizlilik dilimi

S1: boyutu sınırlı istek gövdesi, depoya yazmadan değiştirme hedefi doğrulama ve kesin geri alma sonrası yeni nesne temizliği. Belirsiz COMMIT sırasında veri kaybı yaratacak silme yapılmaz; uzlaştırma gereksinimi kaydedilir. S2: sekmeler arası çıkış ve geç yanıt yarışları; sonra sınav geçişi ve kaynak okuyucusu. S3: hesap işleminin gerçek kapsamı ve export sözleşmesi, teknik bulgu/kurumsal karar kaydı. S4: mevcut dou-synapse-role-security becerisine veri yaşam döngüsü referansı eklendi, yapı doğrulaması ve bağımsız kullanım denemesi geçti; bu kurulu beceri depo dışında sürdürülür.


## 8 Eylül 2026 devam kontrol noktası

Önceki uzak kontrol noktası `c45e0e7073c92638ced7a3ff523578dd598c350b`; PR26 açık taslak, hedef017/6218159. Bu HEAD'in CI34238925467 beş işi ve AIquality34238925534, agent-skills34238925527, security34238925449 başarılı. Hosted API1561/38subtests, E2E68. 030 adayındaki Ubuntu geçici-dizin test hazırlığı hatası iki satırlık test düzeltmesi ve031 kaydıyla giderildi; önceki başarısız kanıt korunur. Bu kabul aşağıdaki yeni dirty kaynakları kapsamaz.

Kullanıcı işler bittikçe yeniden planlayarak yaklaşık10 saat devam edilmesini istedi. Hazır yerel geliştirme/test/özellik dalı akışı sürer; gerçek sağlayıcı harcaması, canlı dağıtım, main birleşimi veya insan onayı uydurulmaz. Ağır DB/API/browser/model işleri root tarafından sırayla çalışır. Ortak dosyalar root'a aittir; ajanlar bağımsız geçici adayları devreder. PR açıklamasının yayımlanması önceki otomatik izin incelemesinde reddedildi; ayrı açık onay henüz yok, bu metaveri işlemi bekler.

OPS dilimi OPS1 yönetim/hazırlık tutarlılığı, OPS2 COMMIT sonrası içeriksiz bakım kaydı ve erken yapılandırma doğrulaması, D6 sürekli Compose poller ve operasyon belgeleridir. Tam API 1571/38 alt vaka ile71 tarayıcı vakası yerelde geçti. API makbuzundan sonraki internal.py modül docstring’i, admin test literal düzenlemesi ve kota test ifadesinin satır düzenlemesi davranış AST eşliğiyle ayrıca bağlıdır; byte farkı gizlenmez. OPS kesin `f79d8a208d468be59a0ab4c035af0f6e468826e2` HEAD üzerinde dört GitHub workflow ve beş CI işi geçti; hosted API 1571/38 alt vaka, E2E 71. Bu uzak kabul sonraki S9 çalışma ağacını kapsamaz. [OPS yerel kanıtı](../specs/018-codex-production-line/evidence/ops-local/README.md).

Sıra: entegre S9/S9B/S9C son kimlik maskeleme düzeltmesiyle birleşik ve tam API kabulü/yeni kaynak kapıları → istemci destek kimliği S10 sınırı → C1 eşitlik/yeniden yükleme kontrollü tanısı → C2 nedensellik veya H/I hazır kabulleri. E/F/G dış girdileri beklerken bağımsız hazır işler ilerler; eski test sonucu yeni kaynakta çalışmış gibi sunulmaz.


Yeni dönem 02, başlangıç silmesini 0.544s ve sonraki expired satırın yokluğunu 60.181s'de gözledi; canlı pencerenin byte'ları aynı, SIGTERM çıkış 0/0.086s. İlk eksik yerel auth ayarlı dönem deneyi başarısız olarak korunur. Worker süreci ölçüldü; Docker/Compose ve scale-to-zero saklama SLA'sı ölçülmedi.

OPS1 yönetim görünümü 375/1440 genişlikte açık/koyu dört gerçek API akışında ve ArrowRight/Home klavye dumanında geçti. Yeni71 E2E turundaki3 ek vakanın 1'i gerçek yetkili overview, 2'si kontrollü degraded/eski-alan UI yanıtıdır. R1'de iki gerçek SQL kontrol/SELECT 1/0 kalibrasyonu ile yedi admin testi toplam 9 PASS verdi.22012 sonrası gerçek HTTP 200 degraded, aynı transaction'da 25P02, bağımsız bağlantıda bir allowed audit ve sonraki public readiness'te temiz 200 gözlendi. Bu karakterizasyon yazımlarda transaction garantisi veya bağlantı kaybının güvenle toparlandığı kabulü değildir.

D3'ün yeni dört kontrollü negatif deneyi geçti: kaynak bağlantısı kaybı 0.447s, açık yazıcı 0.310s, kapalı yazıcı 0.322s, bakım bağlantısı kaybı 0.501s.07b son sentinel readback'i yapılmadı; bakım kaybında COMMIT doğrulandı ama hedef yeniden açılmadı. Root makbuzundaki source_unchanged yalnız araç kaynak hash'idir, DB satır eşliği değildir. Cross-cluster, ağ blackhole/reset, ek rol matrisi, dış Storage ve kurumsal saklama/imha açık kalır. Bu OPS ölçümü sırasında S9/S9B ayrı geçici adaydı; o kanıtın kapsamına uygulanmış veya kabul edilmiş özellik olarak dahil değildir.


## S9 hata günlükleri — sonraki yerel dilim

S9 errors + son S9C logging çalışma ağacına entegredir. Aynı çevrimdışı oracle’larda S9 eski 18 FAIL/adayı 18 PASS, errors-only 18 FAIL, formatter-only 14 PASS/4 FAIL; S9B eski 2 PASS/33 FAIL/adayı 35 PASS; S9C eski 8 PASS/19 FAIL/adayı 27 PASS gözlendi. Dört formatter-only hatası destek kimliği sözleşmesidir; bütün FAIL sayıları sızıntı adedi değildir. Bu ayrı aşamalardaki 18+35+27 başarı son birleşik sürümün tek 80-test sonucu olarak sunulmaz. İlk entegre tam API koşusunda 1651 test/38 alt vaka geçti; sonraki P2 destek kimliği maskeleme düzeltmesini kapsamaz. Ek dört sentetik kimlik vakası eski kaynakta FAIL, düzeltmede PASS verdi. Son kaynakla tam 1655 API/38 alt vaka geçti; 84 yeni kontrol bu koşuya dahildir. Kesin yeni commit’in hosted kabulü ayrıca bekler.

Gerçek Uvicorn 0.52.4 karşılaştırmasında current/S9/S9B/S9C dört kolun 16 süreç senaryosu 17.270648 saniyede geçti; 20 yerel HTTP yanıtının gövde hash/zarf eşliği korundu. Eski kolun dört senaryosunda, S9’un yalnız iki lifespan senaryosunda bulunan özel sentetik işaretler S9B/S9C’de yoktu. Bozuk sink farkı süreç deneyinin değil, ayrı 27 S9C testinin kapsamıdır. Yapılandırma öncesindeki 32 standart INFO satırı JSON değildi. Ayrı eski/eksik kol kanıtları [S9 yerel arşivinde](../specs/018-codex-production-line/evidence/s9-local/README.md) korunur.

Log şeması artık string exception yerine nesne özeti taşır; sabit acil fallback’te zaman damgası yoktur. [Operasyon sözleşmesi](operations/logging-privacy.md) collector geçişi ve tanı sınırlarını açıklar. Bağımsız incelemede bulunan destek kimliği regex maskeleme gerilemesi dar `redact(request_id)` ile düzeltilir; bilinen kalıplar logda maskelenir. İstemciden gelen diğer uygun kimlikler yine tekrar kullanılabilir ve ilişkilendirilebilir; S10 henüz çözülmedi. Bu yerel dilim üretim/anonimlik/KVKK veya gerçek sağlayıcı kabulü değildir.


## Çalışma penceresi kapanışı — 9 Eylül 2026

Son uygulama kontrol noktası S10 `d870c261` / own036’dır; kesin commit yönetişim denetimi yeniden geçti. Yukarıdaki S9 döneminin “S10 henüz çözülmedi” ifadesi tarihsel durumdur. S10 test arşivi Git içinde korunur. S10 sonrası C1/C2/S11 geçici paketleri 9 Eylül 16:10 UTC denetiminde bulunamadı; görev kayıtlarından kurtarılan kaynak/özetler özgün ham kanıtın ve son kaynak kabulünün yerine geçmez. S11 henüz ürüne entegre edilmedi. Planlanan 00:45 UTC bitişi geçildiği için otomasyon duraklatıldı. [Tam durum, sınırlar ve devam sırası](team/codex/2026-09-09-window-checkpoint.md).
