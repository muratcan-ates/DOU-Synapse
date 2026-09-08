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
| S1–S7 güvenlik/gizlilik | S71d5ff6 yerel kontrol noktası; kendi kanıtı var | S/B/C uzak kapıları ayrıca doğrulanır; kurumsal kararlar ve kalıcı cleanup/uzlaştırma açık |
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
| D operasyon | Ortak kota ve worker probe adayları hazır; D3 gerçek yedek başarılı, ilk restore hedef bağlantı kapatma hatasıyla reddedildi | Boş hedefler değişmedi. Ayrı bakım bağlantısıyla güvenli restore, çok süreçli kota, worker iptal/lease ve metrikler ayrı kabul bekler |
| E gerçek model kabulü | Sahte sağlayıcı sözleşme kanıtları var | Gerçek sağlayıcı bütçesi/erişimi, bağımsız insan etiketleri ve gerçek kalite raporu |
| F auth/private storage | Yerel issuer/JWT/CSP sınırları doğrulandı | Gerçek kullanıcı oturumu, seçilmiş imza yolu ve kullanıcı JWT'siyle Storage RLS ayrı sınanır |
| G dağıtım | Canlı hedef seçilmedi | İncelenebilir migrate/deploy/rollback paketi; gerçek hedef ve yetkiyle canlı tatbikat |
| H erişilebilirlik/E2E | B'nin 68 gerçek HTTP akışı ve dar/koyu görselleri doğrulandı | Tüm sayfaların klavye/axe/manuel kabulü ayrı açık |
| I belge ve kılavuzlar | Değişen API/OpenAPI ve gizlilik envanteri güncellendi | Güncel öğrenci/eğitmen/admin kılavuzu ve gerçek başarı raporu; bitmemiş işler bitmiş gösterilmez |

## Ortam ve doğrulama sınırları

Bu göreve özel PostgreSQL16 localhost55448; dou018_* test veritabanları; tarayıcı için dou_synapse_e2e_dou018, API8018/web3118. Fake LLM ve hashing yalnız mekanik doğrulama içindir. Ayrı sentetik korpusta mevcut yerel E5 önbelleğiyle gerçek embedding retrieval karşılaştırması da yapıldı; model indirilmedi ve LLM çağrılmadı. Mevcut sır veya .env kullanılmadı. Yerel pgvector0.8.0 ile CI0.8.6 sürüm farkı retrieval ölçümünde açık tutulur.

## Dış girdiler ve devam

Groq/Gemini erişimi, Supabase proje bilgileri, JWT imza tercihi, bulut/staging hedefi ve branch protection henüz verilmedi. İlgili somut paket hazır olduğunda gereken karar sorulur; diğer hazır işler sürer. İnsan etiketleri boş kalır. Yeni bağımlılık önerileri ve migration-runner tablo kararı kendi diliminde gerekçelendirilir. Bu kayıt gelecekte çalışma planıdır; ayrıca bir zamanlayıcı kurulmuş olduğu anlamına gelmez.

Sonraki yürütülebilir adım: B'nin yerel kabulleri geçti. S sonrası B/C kontrol noktası dc7a768 ve kendi027 kanıtıyla kaydedildi; kesin commit yönetişim denetimi geçti. PR26 için yeni uzak kapılar hazırlanır. FTS bileşeni geri çekildikten sonra son hashing/E5 non-regression ve gerçek sürücü kontrolleri geçti; önceki olumsuz kanıtlar değişmedi. C1 matrisinin kalan hücreleri ve üretim terfisi açık. D3 ilk gerçek restore hatasını gideren ayrı bakım bağlantısı tasarımı incelemede; D–I hazır işleri sürer. Her devirde gerçek HEAD ve uzak dal durumu yeniden kontrol edilir.

## Güvenlik ve gizlilik dilimi

S1: boyutu sınırlı istek gövdesi, depoya yazmadan değiştirme hedefi doğrulama ve kesin geri alma sonrası yeni nesne temizliği. Belirsiz COMMIT sırasında veri kaybı yaratacak silme yapılmaz; uzlaştırma gereksinimi kaydedilir. S2: sekmeler arası çıkış ve geç yanıt yarışları; sonra sınav geçişi ve kaynak okuyucusu. S3: hesap işleminin gerçek kapsamı ve export sözleşmesi, teknik bulgu/kurumsal karar kaydı. S4: mevcut dou-synapse-role-security becerisine veri yaşam döngüsü referansı eklendi, yapı doğrulaması ve bağımsız kullanım denemesi geçti; bu kurulu beceri depo dışında sürdürülür.
