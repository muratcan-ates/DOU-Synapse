# Plan — 018

Dal: 018-codex-production-line. Çalışma ağacı: /Users/muratates/code/dou-synapse-018-codex-production-line. Kesin taban: 621815908d5372d8de414aec4ca1dc63da008dca; GitHub ve origin aynı. 018-retrieval-performance farklı, eski 88a8097 tabanındaki çalışma ağacıdır; ona dokunulmaz. Runbook'taki dal adı kullanılır; specs/018-codex-production-line yeni ve ayrıdır. Göç 0021/0022/0023 önceki kuyruk rezervleri korunur; bu başlangıç dilimi göç eklemez.

## Sahiplik
Root: ortam, ortak ayarlar, .ai kayıtları, spec/defter, git ve PR. gate_audit: yalnız atanmış CI/politika dosyaları. product_reconcile: başlangıçta salt okunur A7/B uzlaştırması. retrieval_review: salt okunur C tasarım/kanıt incelemesi. Hiçbir alt ajan commit/push yapmaz. Yeni yazma görevleri açık dosya sınırıyla atanır.

## Doğrulama
Önce değişen davranışın hedefli ve negatif testleri; sonra API tam test, web birim/tsc/kontrast, docs/göç ve temiz commit üzerinde yönetişim. Ağır testler sırayla. Yeni yerel PostgreSQL 16 kümesi, port 55448; veritabanları dou018_*; ayrı E2E veritabanı. Gerçek anahtar veya başka şeridin .env dosyası kullanılmaz. Kanıtlar yalnız geçici klasörde bırakılmaz; sürümlü doğrulama kaydı sonuç ve komutları taşır.

## Devam
A1 → A2 → A3, ardından doğrulanmış A/B işleri. Sır veya canlı hedef gerektiren alt adım ayrı beklerken hazır işler devam eder. Her hassas commit yeni dossier alır; eski .ai kayıtları değişmez. 017 hedefli taslak PR, yerel kapılar sonrasında hazırlanır.
