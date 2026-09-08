# Plan — 018

Dal: 018-codex-production-line. Çalışma ağacı: /Users/muratates/code/dou-synapse-018-codex-production-line. Kesin taban: 621815908d5372d8de414aec4ca1dc63da008dca; GitHub ve origin aynı. 018-retrieval-performance farklı, eski 88a8097 tabanındaki çalışma ağacıdır; ona dokunulmaz. Runbook'taki dal adı kullanılır; specs/018-codex-production-line yeni ve ayrıdır. Göç 0021/0022/0023 önceki kuyruk rezervleri korunur; bu başlangıç dilimi göç eklemez.

## Sahiplik
Root: ortam, ortak ayarlar, .ai kayıtları, spec/defter, git ve PR. gate_audit: yalnız atanmış CI/politika dosyaları. product_reconcile: başlangıçta salt okunur A7/B uzlaştırması. retrieval_review: salt okunur C tasarım/kanıt incelemesi. Hiçbir alt ajan commit/push yapmaz. Yeni yazma görevleri açık dosya sınırıyla atanır.

## Doğrulama
Önce değişen davranışın hedefli ve negatif testleri; sonra API tam test, web birim/tsc/kontrast, docs/göç ve temiz commit üzerinde yönetişim. Ağır testler sırayla. Yeni yerel PostgreSQL 16 kümesi, port 55448; veritabanları dou018_*; ayrı E2E veritabanı. Gerçek anahtar veya başka şeridin .env dosyası kullanılmaz. Kanıtlar yalnız geçici klasörde bırakılmaz; sürümlü doğrulama kaydı sonuç ve komutları taşır.

## Devam
A1 → A2 → A3, ardından doğrulanmış A/B işleri. Sır veya canlı hedef gerektiren alt adım ayrı beklerken hazır işler devam eder. Her hassas commit yeni dossier alır; eski .ai kayıtları değişmez. 017 hedefli taslak PR, yerel kapılar sonrasında hazırlanır.

## S sahiplik ve inceleme

S1/S7 ilk uygulama gate_audit; iptal ve COMMIT sonrası silme için bağımsız inceleme/düzeltme retrieval_review. S2 tarayıcı kimlik/sınav nesilleri ve E2E product_reconcile. S3 ve S5/S6 sözleşme/ayar uygulaması retrieval_review; ortak rapor, son web/API koşuları, hukuk kaynakları, skill-creator güncellemesi ve yayımlanmamış yönetişim kaydı root. B4 yarış araştırması ayrı izole dou018_delete_race veritabanında; S kabulüne bitmemiş test karıştırılmaz.


B/C sahipliği: B4 sunucu ve 0024 göçü gate_audit; B1/B6/B7 ve B4 sohbet UI product_reconcile; B5 ilk uygulama root, bağımsız inceleme ve scoped RAM taslak düzeltmesi gate_audit; C ölçüm harness'i retrieval_review. Root benzersiz DB kurulumu, tüm gerçek API/tarayıcı/benchmark koşuları, belge/mahremiyet envanteri ve yönetişim entegrasyonunu yürütür. Ağır koşular sıralıdır. 0021/0022/0023 rezervasyonu korunur; CI boşlukları tek tek açıktır.

## B/C son sahiplik ve devam sınırı

B3 backend gate_audit; kod rubriği ve geri bildirim web product_reconcile; kısmi puan görünürlüğünün bağımsız incelemesi/düzeltmesi gate_audit. C sorgu/runtime/harness retrieval_review; root ayrı DB'lerde gerçek deneyleri çalıştırır ve kaynak/kanıt bağını yönetir. B4 son koyu ekran düzeltmesi yalnız testte tema geçişinin bitmesini bekler; ürün kaynakları değişmez. Ağır işler aynı anda çalıştırılmaz.

B4 için 0024_chat_privacy_revisions eklendi: 20 göç ve bildirilen 0017/0021/0022/0023 boşlukları. B/C kontrol noktasına D3 araç kodu dahil edilmez. D3 yalnız tasarım ve depo dışı adaydır; gerçek geri yükleme/rol/RLS/pgvector deneyi geçmeden benimsenmez. C1 ilk hashing/E5 adayındaki FTS gerilemesi çapraz tanıyla ayrıldı. Yalnız FTS hash sıralaması geri çekildi; son kaynak iki holdout ve prepared runtime tekrarını geçti. Önceki olumsuz kayıtlar korunur; geliştirme dalı kaydı üretim veya LLM kalite terfisi değildir.
