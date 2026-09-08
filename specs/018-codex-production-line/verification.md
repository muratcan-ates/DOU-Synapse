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

Yerel varsayılan Turbopack derlemesi Google Fonts TLS bağlantısında durdu ve bu girişim test sonucu sayılmadı. NODE_USE_SYSTEM_CA=1 ile next build --webpack başarıyla tamamlandı; doğrulanmış TLS kapatılmadı. next start --port 3118 üzerinde paket koşuldu. A commit'inin varsayılan Turbopack yolu GitHub CI'da geçti; S adayının hosted sonucu ayrıca izlenir.

## Devam eden doğrulama

A commit'i `2d1b58aeeddaa4b862a760fb46773b2ae73ed253` için kesin SHA yönetişim kontrolü ve [taslak PR26](https://github.com/muratcan-ates/DOU-Synapse/pull/26) kapıları geçti. CI34196848147 içindeki API/Web/Docs/Docker/gerçek E2E; AI quality34196848188, güvenlik34196848181 ve skills34196848361 başarılıdır. [Koşu kaydı](evidence/a-hosted-ci.json). S adayı için bunlar başlangıç kanıtıdır; S hosted sonucu bekler. Gerçek sağlayıcı, insan kalite kabulü, canlı Supabase ve staging/üretim doğrulaması koşulmadı.

## Kanıt saklama

Ham yerel loglar `/private/tmp/dou018-evidence/`; doğrulanan özetler ve ilgili kaynak özetleri `.ai/evidence/025-production-line-gates-r1.json` ve aynı numaralı ayrıntı kayıtlarında saklanır. Geçici klasörün kalıcı olduğu varsayılmaz. Her sonuç için kaynak değiştirilirse etkilenen kontrol yeniden koşulur.

## Yerel S dilimi — son doğrulanan kaynaklar

Tarih: 2026-09-08. Başlangıç A commit'i `2d1b58aeeddaa4b862a760fb46773b2ae73ed253`. Son S kaynakları kendi dossier'indeki SHA256 listesiyle bağlanır.

| Kontrol | Sonuç |
|---|---|
| Tam API | 1332 geçti, 5 mevcut uyarı, 117.21 saniye <!-- docs-check: tarihsel 1332 · 2026-09-08 --> |
| Web birim | 501 geçti, 40 dosya, 1139 assertion <!-- docs-check: tarihsel 501 · 2026-09-08 --> |
| Gerçek HTTP/Chromium | Tek koşuda 50 geçti, 2.5 dakika; 45 sentetik ders ve 8 test audit kaydı temizlendi |
| Derleme ve tipler | Doğrulanmış sistem TLS ile webpack üretim derlemesi; web tsc ve 107 backend dosyasında mypy temiz |
| Ruff/format | Tam API temiz;178 dosya; son iki gövde dosyası ayrıca yeniden kontrol edildi |
| Kontrast/göç/belgeler | Açık/koyu tema eşikleri geçti;19 göç, yalnız0017 boşluğu; canlı sayılar ölçümle eşleşti |

Tam API komutu `.venv/bin/python -m pytest -q`; PG16 localhost55448, TEST_DB_NAME=dou018_security_verified ve admin/app/worker DSN'leri aynı ayrı sentetik DB'ye gider.

Web birim komutu: `bun test lib/`.

Web tip komutu: `tsc --noEmit --incremental false`.

Tarayıcı `bun run test:e2e --workers=1`, E2E_DATABASE_NAME=dou_synapse_e2e_dou018, API8018/web3118, fake LLM/hashing. Derleme `NODE_USE_SYSTEM_CA=1 ... next build --webpack`; TLS doğrulaması kapatılmadı. S için uzak varsayılan Turbopack/CodeQL/CI sonucu henüz bu yerel kayıtla kanıtlanmaz.

Geriye doğru kayıt: ilk S tarayıcı koşusunda47 geçti/3 hata vardı. İki kaynak testi Next route announcer ile gerçek sınav mesajını ayıramıyordu; seçici gerçek mesajla daraltıldı. Üçüncü hata üründeydi: son soru silinince boş havuzda başarı bildirimi kayboluyordu; ürün düzeltildi ve test önce boş havuzu sonra bildirimi doğrulayacak şekilde güçlendirildi. Son50 koşusu tek seferde geçti.

İlk lifecycle tam API koşusunda1324 geçti/1 sağlık gecikmesi hatası vardı (0.467 saniye). Dar tekrar aynı0.1 eşikle geçti. Ayrıca boş isteklerin spool için ortak executor'a girmesi kaldırıldı; gerçek bayt ve Content-Length denetimi korundu. Önceki kodla dört no-thread oracle'ı kırmızı, yenisiyle yeşil. Son tam1332 koşusunda gecikme eşiği değiştirilmeden geçti; ilk gecikmenin tek nedeninin executor olduğu iddia edilmez.

Yeni dosya sahipliği/rollback, belirsiz COMMIT, iptal, kesin COMMIT sonrası mevcut dosya silme, emitted HTTP log ve üst worker istisna zinciri sınandı. Alt ajan iki DB komutunda otomatik izin reddi aldı; o komutlar koşmuş sayılmadı. Ana görev boş test DB adını doğrulayıp yeni gerçek DB vakalarını tam API koşusunda çalıştırdı. İptal ve eski COMMIT-öncesi silme koduyla aynı odak testleri kırmızı oldu. Sonuçlar dağıtık işlem atomikliği veya kalıcı cleanup kuyruğu kanıtı değildir.

B4 ek bulgusu ayrı tutulur: olay bariyerli gerçek testte ders/tümü/profil silme sonrasında önceden başlamış yeni POST bir oturum ve iki mesaj bırakabildi. Üç beklenen kırmızı/tekli mevcut oturum için bir yeşil sonucu [kanıt ve tasarımda](evidence/b4-race-design.md) saklıdır. Test S koleksiyonuna dahil edilmedi; bu kusur S2 arayüz korumasıyla kapanmış sayılmadı. B4 uygulaması için kapsamlı silme nesli ve son yazım kontrolü planlandı.
