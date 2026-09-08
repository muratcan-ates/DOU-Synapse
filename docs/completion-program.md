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
| B1 öğrenme çıktısına konu | Gerçek eksik | UI'dan konu seçilerek kaydedilen çıktı yenilemede korunur |
| B2 konu/blueprint ile sınav | Zaten014'te uygulanmış; runbook iddiası yanlış | Mevcut student-assessment E2E'si bu adayda tekrar çalıştırılır; yeniden yazılmaz |
| B3 açık/kod değerlendirme | Kaynak doğrulama ve kod testleri zaten var; runbook'un yok/sıfır iddiası yanlış | Ayrı neden-yanlış açıklaması ve kod rubrik kırılımı eksik; kaynak varlığı semantik çelişki kanıtı sayılmaz |
| B4 kişisel sohbet silme | API var, web yalnız tüm geçmişi siliyor | Üyeye açık sohbet ekranında kendi oturumu/kendi ders geçmişi; yanlış ID ve hata/iptal/yarış testleri |
| B5 politika geçmişi | API ve0020 cascade testi var, UI yok | Eğitmen salt okunur geçmiş, sayfalama ve hata durumu; kimlikten isim uydurulmaz |
| B6 blueprint özellik bayrağı | Kapalı authoring yalnız düzenleme/üretimi kısıtlar; önceden sınıflandırılmış havuzdan yayın mümkündür | Kullanılamayan sınıflandırma düzeltmesi açık anlatılır; yayın gerçek readiness sonucuna ve sunucu tekrar denetimine bağlıdır |
| B7 soru süzgeçleri | Yalnız yüklenmiş satırlar süzülüyor | status/topic sunucuya gönderilir, imleç sıfırlanır, boş sonuçta filtre kalır |
| C1 retrieval | Dense iç eşitlik sıralaması ANN yolunu bozuyor; belge UUID'si içerikten türemez | İzole gerçekçi korpus/plan/kalite karşılaştırması, içerik hash'iyle son sıralama; yaklaşık aramaya tüm-korpus determinizmi iddia edilmez |
| C2 indeks yapım göçü | Runbook bellek→recall nedenini gösteren tekrar üretilebilir kanıt bulunamadı | Önce bellek/ef_search çapraz ölçümü; mevcut indeks boş tabloda kurulduğu için yeni göç otomatik eklenmez |
| D operasyon | Runbook'taki öneriler henüz tek tek doğrulanmadı | Ortak kota, worker dayanıklılığı, restore ve metrikler; mevcut olanlar tekrar kurulmaz |
| E gerçek model kabulü | Fake/hashing mekanik testleri var; gerçek/human kabul yok | Sınırlı sağlayıcı erişimi, aday bağı, kör insan etiketleri ve gerçek kalite raporu |
| F auth/private storage | Yerel doğrulamalar ile gerçek ortam ayrı | JWT negatifleri, seçilmiş imza yolu; API üyelik reddi ve gerçek kullanıcı Storage RLS ayrı sınanır |
| G dağıtım | Canlı hedef seçilmedi | İncelenebilir migrate/deploy/rollback paketi; dış ortam girdileriyle canlı tatbikat |
| H erişilebilirlik/E2E | Mevcut kütüphane/gerçek ağ kapıları korunur | Dar/koyu/klavye akışları ve canlı HTTP sınav kilidi; görsel test sonucu ayrıca kaydedilir |
| I belge ve kılavuzlar | Sayaç düzeltmeleri her doğrulanmış dilimde, kapsamlı kılavuz en sonda | Güncel öğrenci/eğitmen/admin kılavuzu, gerçek başarı raporu, açık işlerin kanıtla kapanışı |

## Ortam ve doğrulama sınırları

Bu göreve özel PostgreSQL16 localhost55448; dou018_* test veritabanları; tarayıcı için dou_synapse_e2e_dou018, API8018/web3118. Fake LLM ve hashing yalnız mekanik doğrulama içindir. Mevcut sır veya .env kullanılmadı. Yerel pgvector0.8.0 ile CI0.8.6 sürüm farkı retrieval ölçümünde açık tutulur.

## Dış girdiler ve devam

Groq/Gemini erişimi, Supabase proje bilgileri, JWT imza tercihi, bulut/staging hedefi ve branch protection henüz verilmedi. İlgili somut paket hazır olduğunda gereken karar sorulur; diğer hazır işler sürer. İnsan etiketleri boş kalır. Yeni bağımlılık önerileri ve migration-runner tablo kararı kendi diliminde gerekçelendirilir. Bu kayıt gelecekte çalışma planıdır; ayrıca bir zamanlayıcı kurulmuş olduğu anlamına gelmez.

Sonraki yürütülebilir adım: A için taslak PR26 ve GitHub kapıları doğrulandı. S güvenlik/gizlilik diliminin bağımsız son incelemesi ve tarayıcı tekrarını tamamla; ardından B1/B4/B5/B6/B7 uygulamasına geç. Güncel HEAD, temiz ağaç ve uzak dal durumu her devirde yeniden kontrol edilir.

## Güvenlik ve gizlilik dilimi

S1: boyutu sınırlı istek gövdesi, depoya yazmadan değiştirme hedefi doğrulama ve kesin geri alma sonrası yeni nesne temizliği. Belirsiz COMMIT sırasında veri kaybı yaratacak silme yapılmaz; uzlaştırma gereksinimi kaydedilir. S2: sekmeler arası çıkış ve geç yanıt yarışları; sonra sınav geçişi ve kaynak okuyucusu. S3: hesap işleminin gerçek kapsamı ve export sözleşmesi, teknik bulgu/kurumsal karar kaydı. S4: mevcut dou-synapse-role-security becerisine veri yaşam döngüsü referansı eklendi, yapı doğrulaması ve bağımsız kullanım denemesi geçti; bu kurulu beceri depo dışında sürdürülür.
