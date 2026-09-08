# Doğrulama — 018

Tarih: 2026-09-08. Taban: `621815908d5372d8de414aec4ca1dc63da008dca`. Kaynak HEAD bu kaydı içeren commit'te SELF olarak bağlanır. Aşağıdaki sonuçlar bu tur gerçekten koşuldu; eski aday sayıları tekrar kullanılmadı.

## Yerel A dilimi

| Kontrol | Gerçek sonuç |
|---|---|
| Tam API, `apps/api/.venv/bin/python -m pytest -q` | 1212 geçti, 5 mevcut PyMuPDF kullanım dışı kalma uyarısı, 273.01 sn |
| Web, `bun test lib/` | 432 geçti, 39 dosya <!-- docs-check: tarihsel 432 · 2026-09-08 --> |
| Exam hedefli birim testleri | 61 geçti |
| A5 dört API test dosyası | 224 geçti; mutant sonrası tekrar224 geçti |
| A6 retry/kapsam/kaynak laboratuvarı | 14 geçti; gerçek API→inspection→dense/FTS, yalnız hashing embedding |
| Release doğrulayıcıları | unittest discovery ile26 geçti |
| Workflow politika testleri | 27 geçti; gerçek iş akışları PASS |
| AI yönetişim testleri | 77 geçti; gerçek geçici Git commit'leri yeni7 kapıyı dosyasız değiştirince UNCOVERED |
| Ruff kontrol/biçim | Temiz;173 API dosyası |
| Backend tip |105 kaynak dosyasında sorun yok |
| Web tip | `tsc --noEmit --incremental false` geçti |
| Kontrast | Açık/koyu tema metin ve metin dışı eşikler geçti |
| Göç |19 göç, yalnız bildirilen0017 boşluğu; yeni göç yok |
| Belge kontrolü | Canlı sayılar ölçümden yenilendi;017'nin tarihli sonuçları tarihsel olarak sabitlendi |

Tam API ortamı: PostgreSQL16 localhost55448, TEST_DB_NAME=dou018_full; admin/app/worker DSN'leri aynı ayrı veritabanına gider. Ortam sağlayıcı anahtarları test fixture'ında boşlanır; uygulama RLS rolü dou_app. Tarayıcı ortamı ayrıca dou_synapse_e2e_dou018 üzerinde fake/hash, API8018/web3118;19 göç ve sentetik örnek kullanıcılar. local_dev_setup.sql sabit dou_synapse adına izin verdiği için bu test DB'sine aynı dar CONNECT izni açıkça verildi; gerçek ders verisi kullanılmadı.

## Olumsuz kontroller

- Önceki workflow kontrolüyle17 yeni alt vaka başarısız; aday sürümle yeşil. Önceki .ai politikasıyla7 gerçek dosyasız commit kontrolü başarısız; adayla yeşil.
- İpucu monotonluk koruması kopya kaynakta kaldırıldığında3 yeni test başarısız (58 geçti); asıl kaynak değişmedi.
- A5:9 mutanttan8'i aynı gerçek regresyon testinde yakalandı. Sohbet sahip filtresi çıkarma mutantı bağımsız RLS nedeniyle veri sızdıramadı ve yakalanmış sayılmadı. Exam sahip filtresi, boş200 export, sonuç kilidi, ScriptedLlm sırası, int8/fp32 materyal dosyaları sınandı. Mutasyon sonrası4dosya/224test tekrar geçti.
- Yeni A6 testinin ilk kurulumunda keyword-only fabrika çağrısı ve örtük eşik varsayımı hatalıydı; test verisi düzeltildi, açık0.81 eşik verildi. Ürün eşiği değiştirilmedi.

## Tarayıcı ve uygulama mutasyonu

Uygulama mutasyon koşucusu: 12/12 koruma kaldırılınca ilgili test kırmızı, 12/12 geri yüklemede yeşil; başlangıç 19 test yeşil, geçici veritabanı artığı sıfır. Sonuç 06:24:49 UTC'de yakalandı.

Gerçek HTTP/Chromium paketi: ilk tamamlanan koşuda 41 geçti, 1 başarısız (2.1 dakika). Başarısız soru-belge silme testi üç Reddedildi düğmesini ayıramıyordu. Tam eşleşmeli erişilebilir ad seçicisiyle aynı senaryo tekrar geçti (5.1 saniye); ürün kodu değişmedi. Böylece 42 farklı akışın tamamı başarılı çalıştırıldı; tek koşuda 42 geçti iddiası yok. 41 testlik koşuda geç gelen eski 200 yanıtının yeni sınav kilidini açamadığı, konu/blueprint ile öğrenci sınavı ve tüm zorunlu iki-soru koşulları da geçti. Her koşunun sentetik dersleri temizlendi.

Yerel varsayılan Turbopack derlemesi Google Fonts TLS bağlantısında durdu ve bu girişim test sonucu sayılmadı. NODE_USE_SYSTEM_CA=1 ile next build --webpack başarıyla tamamlandı; doğrulanmış TLS kapatılmadı. next start --port 3118 üzerinde paket koşuldu. CI'ın varsayılan Turbopack yolu ayrıca GitHub'da doğrulanmalıdır.

## Devam eden doğrulama

 Temiz commit için kesin SHA yönetişim kontrolü ve taslak PR CI sonucu henüz yok. Docker imajı yerelde çalıştırılmadı. Gerçek sağlayıcı, insan kalite kabulü, canlı Supabase ve staging/üretim doğrulaması koşulmadı.

## Kanıt saklama

Ham yerel loglar `/private/tmp/dou018-evidence/`; doğrulanan özetler ve ilgili kaynak özetleri `.ai/evidence/025-production-line-gates-r1.json` ve aynı numaralı ayrıntı kayıtlarında saklanır. Geçici klasörün kalıcı olduğu varsayılmaz. Her sonuç için kaynak değiştirilirse etkilenen kontrol yeniden koşulur.
