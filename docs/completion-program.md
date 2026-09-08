# CourseGPT tamamlama programı

Kullanıcı 8 Eylül 2026'da Codex ve Claude çalışmalarının birleştirilmesini ve geliştirmeye devam edilmesini istedi. Hocanın e-postası ürün gereksinimi; runbook uygulanmadan önce kodla karşılaştırılan iş önerisidir.

## Güncel çalışma

Aktif dal `018-codex-production-line`; çalışma ağacı `/Users/muratates/code/dou-synapse-018-codex-production-line`. Kesin taban `621815908d5372d8de414aec4ca1dc63da008dca` (`017-completion-integration`), 8 Eylül'de GitHub ile eşleştirildi. 013/014/015 ürün dilimleri, 016 beceriler, Codex017 düzeltmeleri ve Claude'un0020/CI/runbook katkıları tabanda zaten birleşik. Yeni dal bu geçmişi korur. Ana dal veya canlı ortam birleşimi yapılmadı.

Eski defter016'da kalmıştı. Tarihsel kanıtlar [015](../specs/015-completion-program/verification.md), [016](../specs/016-agent-skills/verification.md) ve [017](../specs/017-completion-integration/verification.md) kayıtlarında korunur; bu adayın sonucu sayılmaz. Geçici017 kanıt klasörü artık yok; eski geçici yollar yeni sonuç olarak kullanılmaz.

Güncel kabul/sahiplik: [018 spec](../specs/018-codex-production-line/spec.md), [plan](../specs/018-codex-production-line/plan.md), [iş listesi](../specs/018-codex-production-line/tasks.md), [doğrulama](../specs/018-codex-production-line/verification.md).

## Birleştirilmiş iş kuyruğu

| İş | Kodla doğrulanan durum | Sonraki kabul |
|---|---|---|
| A1–A3 CI ve yönetişim | A commit’i 2d1b58a üzerinde yerel ve GitHub CI doğrulandı | Release testleri/uygulama mutasyonları CI adımı; hassas kapılar; hata yutma ve izin genişlemesi negatif testte reddedilir |
| A4/A7 sınav testleri | Yerel birim ve gerçek HTTP akışı geçti | Dört koşullu skip yerine gerçek iddia; monoton ipucu geçmişi; sınavdan önceki gecikmiş200 yeni kilidi açamaz |
| A5 test sağlamlığı | 224 test geçti; 9 mutanttan 8 yakalandı, biri bağımsız RLS ile korundu | Gerçek yardımcı/CLI/export/sonuç kilidi davranışı; aynı test üretim koruması kaldırılınca düşer |
| A6 erişilmeyen kod | Üç kullanılmayan yardımcı kaldırıldı; kullanılan yollar korundu | Retry sınıf-adı yolu, kapsam reddi ve gerçek sources/inspect çağrısı test edilir |
| S1–S7 güvenlik/gizlilik | S71d5ff6 kendi kanıtı; son S/B/C9af4122 üzerinde dört GitHub workflow başarılı | Kurumsal kararlar ve kalıcı cleanup/uzlaştırma açık |
| S8 günlük minimizasyonu | Rota şablonu ve Uvicorn erişim kanalı sınırı entegre; 21 ASGI ve gerçek Uvicorn v2 deneyi geçti | V1 fixture kapanış hatası korunur; yeni tarayıcı/hosted ve dış proxy günlüklerinin kabulü açık |
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
| D operasyon | D1 iki HTTP sürecinde 55 istek; D2 stage02'de 98 test ve süreç v2'de 8 senaryo geçti. Başlangıç kota temizliği doğrulandı. D3 güncel 22 göçle 30 ilişki/14 satır ve rol/RLS eşliği geçti; kaynaklar yerel checkout'a entegre | Son 1561 API ve 68 gerçek tarayıcı testi geçti; kesin commit/dossier/hosted kabulü, gerçek periyodik ve scale-to-zero işletim; D3 kalan hata matrisi ve kurumsal/canlı kabul açık |
| E gerçek model kabulü | Sahte sağlayıcı sözleşme kanıtları var | Gerçek sağlayıcı bütçesi/erişimi, bağımsız insan etiketleri ve gerçek kalite raporu |
| F auth/private storage | Yerel issuer/JWT/CSP sınırları doğrulandı | Gerçek kullanıcı oturumu, seçilmiş imza yolu ve kullanıcı JWT'siyle Storage RLS ayrı sınanır |
| G dağıtım | Canlı hedef seçilmedi | İncelenebilir migrate/deploy/rollback paketi; gerçek hedef ve yetkiyle canlı tatbikat |
| H erişilebilirlik/E2E | B'nin 68 gerçek HTTP akışı ve dar/koyu görselleri doğrulandı | Tüm sayfaların klavye/axe/manuel kabulü ayrı açık |
| I belge ve kılavuzlar | Değişen API/OpenAPI ve gizlilik envanteri güncellendi | Güncel öğrenci/eğitmen/admin kılavuzu ve gerçek başarı raporu; bitmemiş işler bitmiş gösterilmez |

## Ortam ve doğrulama sınırları

Bu göreve özel PostgreSQL16 localhost55448; dou018_* test veritabanları; önceki B/C tarayıcı DB’si dou_synapse_e2e_dou018, son D tarayıcı DB’si dou018_d_e2e_01; API8018/web3118. Fake LLM ve hashing yalnız mekanik doğrulama içindir. Ayrı sentetik korpusta mevcut yerel E5 önbelleğiyle gerçek embedding retrieval karşılaştırması da yapıldı; model indirilmedi ve LLM çağrılmadı. Mevcut sır veya .env kullanılmadı. Yerel pgvector0.8.0 ile CI0.8.6 sürüm farkı retrieval ölçümünde açık tutulur.

## Dış girdiler ve devam

Groq/Gemini erişimi, Supabase proje bilgileri, JWT imza tercihi, bulut/staging hedefi ve branch protection henüz verilmedi. İlgili somut paket hazır olduğunda gereken karar sorulur; diğer hazır işler sürer. İnsan etiketleri boş kalır. Yeni bağımlılık önerileri ve migration-runner tablo kararı kendi diliminde gerekçelendirilir. Bu kayıt gelecekte çalışma planıdır; ayrıca bir zamanlayıcı kurulmuş olduğu anlamına gelmez.

B/Cdc7a768 ve aggregate028/9af4122 PR26'ya push edildi; kesin HEAD'in CI, AI quality, agent skills ve security/dependency workflow'ları geçti. [GitHub makbuzu](../specs/018-codex-production-line/evidence/bc-hosted-exact-head-final.json) sonraki yerel D/S8 kaynaklarını kapsamaz.

D1'in iki gerçek HTTP sürecinde 55 isteği, D2 stage02'nin 98 testi ve süreç v2'nin 8 senaryosu geçti. İlk D2 süreç koşusu sekiz davranışı geçmesine rağmen genel parent gizlilik denetiminden kaldı; başarısız sonuç korunur. Worker başlangıçta süresi dolmuş kota satırını temizlerken canlı satırı korudu; gerçek 60 saniyelik dönem veya scale-to-zero saklama garantisi ölçülmedi. D3'ün eski kaynakla 29 ilişki/20000 vektör ve hata deneylerine ek olarak, güncel 22 göçlü kaynakla 30 ilişkinin toplam 14 satırı ve güvenlik kataloğu/rol eşliği doğrulandı. Gerçek eğitmen ve dış kullanıcı RLS ayrımı ile kota tablolarına 42501 reddi geçti; dış Storage kopyalanmadı.

Kaynaklar yerel çalışma ağacına entegredir. İlk birleşik tam API koşusunun 1560 geçti/1 başarısız sonucu korunur. Worker kilit gözlemcisinde her okumadan önce istatistik görüntüsünü yenileyen dar test düzeltmesi geçti; bu yenileme kaldırıldığında aynı kontrol başarısız, geri konduğunda yeniden başarılı oldu. Üretim kodu bu düzeltmede değişmedi. Son tam API koşusunda 1561 test geçti: 102.75 s pytest, 113.344 s kurulumla birlikte; kaynak hashleri koşu boyunca değişmedi. S8'in 21 ASGI kontrolüne ek olarak gerçek Uvicorn v2'de eski/yeni kaynakların her birine üç HTTP isteği geçti; adayda dört ham canary ve erişim kanalı kaydı yoktu, başlangıç/kapanış günlükleri korundu ve DB bağlantısı denenmedi. V1'in baseline sonrası fixture kapanış hatası ayrı korunur. Son 68 gerçek tarayıcı akışı82.187 saniyede geçti; mtsqcmai1b9f koşusunun65 ders/8 audit kaydı temizlendi. İlk adres eşleme hatası ve düzeltmesi ayrı korunur. Yerel kabul tamamlandı; ayrı dossier/commit ve kesin yeni HEAD’in hosted kapıları PR26 üzerinde izlenir. D3'te 07 eşzamanlı yazıcı, cross-cluster/control-loss ve kurumsal saklama/imha; C1 kalan matris hücreleri ve D–I canlı/insan kabulleri açık kalır. Arşiv hedefi `specs/018-codex-production-line/evidence/d-final-local/`; her devirde gerçek HEAD, kirli kaynaklar ve uzak durum yeniden kontrol edilir.

## Güvenlik ve gizlilik dilimi

S1: boyutu sınırlı istek gövdesi, depoya yazmadan değiştirme hedefi doğrulama ve kesin geri alma sonrası yeni nesne temizliği. Belirsiz COMMIT sırasında veri kaybı yaratacak silme yapılmaz; uzlaştırma gereksinimi kaydedilir. S2: sekmeler arası çıkış ve geç yanıt yarışları; sonra sınav geçişi ve kaynak okuyucusu. S3: hesap işleminin gerçek kapsamı ve export sözleşmesi, teknik bulgu/kurumsal karar kaydı. S4: mevcut dou-synapse-role-security becerisine veri yaşam döngüsü referansı eklendi, yapı doğrulaması ve bağımsız kullanım denemesi geçti; bu kurulu beceri depo dışında sürdürülür.
