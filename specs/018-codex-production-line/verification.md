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


## B ara doğrulaması — 8 Eylül

S kontrol noktası `71d5ff640f0d48a08f3967b000485a15035f10c7` üzerindeki B4 sunucu adayı:

- Olay bariyerli silme/kayıt yarışları, öğrenci/eğitmen, tekli/ders/tüm/profil kapsamı, ters commit sırası, rollback, üyelik iptali, cache/ret/bütçe/Sokratik yollar ve doğrudan RLS kontrolleri: 34 geçti, 4.84 saniye.
- Tam API: 1366 geçti, 5 mevcut PyMuPDF uyarısı, 89.56 saniye. Bu ara koşu daha sonra eklenen kaynakların yerine geçmez.
- İzole DB adları dou018_b4_verified2 ve dou018_b4_full; ikisi fixture kapanışında kaldırıldı. İlk dar koşunun 3 geçersiz test e-postası ve 1 eksik test bağlantısı düzeltildi; ürün kontrolü gevşetilmedi.
- 0024_chat_privacy_revisions göçü 0021–0023 runbook rezervasyonunu korur. Güncel 20 göç, açık 0017/0021/0022/0023 boşluklarıyla doğrulanır; bildirimsiz sıra kontrolü hâlâ başarısız olur.
- B1/B6/B7 dar birim/negatif kontrolleri geçti. B4/B5 arayüzleri ve tüm birleşik web/tarayıcı koşusu henüz bu ara kayıtta tamamlanmış değildir.

C ön ölçümü 20 bin yapay vektörle tamamlandı. İlk aday kolları yalnız id/similarity taşırken mevcut sorgu tam çıktı taşıdığı için süreler runtime hızlanması olarak kullanılmaz. Eşit projection ile ikinci koşu hazırlanır. Saf CTE'nin geniş kapsamda kaybettiği exact komşular ayrıca kaydedilir; hızlı olması kabul için yeterli değildir.

## B/C yerel aday — 8 Eylül 2026

Başlangıç S71d5ff640f0d48a08f3967b000485a15035f10c7. Bu bölüm B'nin yerel teknik kabulleriyle C'nin araştırma adayını ayırır. Son kaynaklar yeni dossier'de SHA256 ile bağlanır; A hosted sonucu bu adayın sonucu değildir. İlk birleşik retrieval adayı non-regression kapısında reddedildi. FTS geri çekmesinden sonra son dar aday hashing/E5 ve sürücü tekrarını geçti; C1 matrisinin kalan hücreleri ve üretim terfisi açık.

| Kontrol | Sonuç |
|---|---|
| Tam API — son FTS geri çekmesi | 1499 geçti; 5 bilinen PyMuPDF uyarısı; 91.66 saniye |
| Web birim | 555 geçti;44 dosya;1282 assertion |
| Gerçek HTTP/Chromium — son kaynak | Tek koşuda 68 geçti; 1.4 dakika; 65 sentetik ders ve 8 audit temizlendi |
| B4 son tema kanıtı | Yalnız testte tema hazır bekleme ve animations disabled; aynı ürün derlemesinde1 senaryo tekrar geçti;2 test dersi temizlendi |
| B3 son API iddiası | is_correct=true/kısmi puan sınırı ek iddiasıyla10 test geçti;API ürünü değişmedi |
| Tip/biçim | Backend109 kaynak;ruff temiz ve186 dosya biçim uygun;web tsc temiz |
| Derleme | Doğrulanmış sistem TLS ile üretim webpack başarılı;varsayılan Turbopack hosted ayrı |
| Retrieval araçları | Mevcut API CI işine eklendi;104 çevrimdışı test geçti;ayrı koleksiyon |
| Release/workflow/göç/kontrast | 26 release testi;workflow PASS;20 göç ve yalnız0017/0021/0022/0023 boşlukları;tema eşikleri PASS |

API komutu: `.venv/bin/python -m pytest -q`.

Web birim komutu: `bun test lib/`.

Web tip komutu: `tsc --noEmit --incremental false`.

API testleri yalnız localhost55448 ve aynı benzersiz admin/app/worker DB'lerini kullanır. Son tam API DB'si dou018_bc_final3 fixture sonunda kaldırıldı. Önceki tam API koşusundaki ek FTS yeniden-yükleme iddiası, ilgili davranış geri çekildiği için son paketten çıkarıldı; dense yeniden-yükleme ve iki yolun yetki testleri korunur. Tarayıcı E2E_DATABASE_NAME=dou_synapse_e2e_dou018, API8018/web3118 ve fake/hash ile `bun run test:e2e --workers=1`. Önceki 68 turunun kimliği mtshyot850a7, tema odak tekrarı mtsih4xpb742; FTS geri çekmesi sonrası son 68 turu mtskgnz9ac45. Son API yeniden başlatıldı; web ürün kaynakları ve başarılı derleme değişmedi. Manuel LOCAL-B5-018 dersi de tam UUID+kod koşuluyla temizlendi.

B3 tarayıcı geri bildirimi gerçek upload/generation/draft/approval/session/answer sonrası yalnız test kapsamındaki DB satırına kontrollü olarak yazılır; gerçek API'den saved/results/source okunur. Aktif sınav, bozuk kaynak alıntısı ve yeniden doğrulama sınırları gerçektir. Sahte sağlayıcı gerçek cevap puanlaması yapmadığından bu E2E gerçek LLM puanlama doğruluğu kanıtı değildir. Bağımsız inceleme 80 puan/is_correct=true cevabında eksik ölçütün gizlendiğini buldu; önceki yardımcıyla4 negatif test düştü. Görünürlük gerçek eksik ölçüt puanına bağlandı; toplam100'e yuvarlanan düşük ağırlıklı eksik ölçüt de sınandı.

B6 authoring=false arayüzü capability yanıtında simüledir; hazırlık/yayın gerçek API'ye gider. Bu, ayrı false-env backend dağıtımı olarak sayılmaz.

İlk B tarayıcı turunda64 geçti/1 kurulum sırası hatası vardı: ikinci sekmenin auth uzlaştırması testin önceden yazdığı oturum anahtarını temizliyordu. İki sekme kurulduktan sonra gerçek UI seçimi yapıldı; silme/kaçırılmış olay/anahtar oracle'ı korunarak odak tekrar geçti. Son68 turu tek seferde geçti. Sonrasında B4 koyu screenshot'ın tema geçiş karesi olduğu gerçek derlenmiş CSS ile ölçüldü;kararlı renkler ve tek odak tekrar doğrulandı. Tema odak tekrarı 69 farklı vaka olarak sayılmaz. FTS geri çekmesinden sonra ayrıca tam 68 senaryo yeniden çalıştırıldı; bu son turun kanıtı ayrıdır.

İlk C1 plan/runtime/başarısız hashing adayının kapsamı [tarihsel rapordadır](evidence/c1-report.md); son dar kaynak kabulü [ayrı rapora](evidence/c1-final-acceptance.md) bağlanır. İlk eşit olmayan projeksiyon ön bulgudur. Eş projeksiyon V2 gerçek RLS ile yapılır;sonra gerçek sürücüde prepared generic-plan kusuru bulunup yalnız dense custom planıyla düzeltilir. İki runtime adayındaki294 ölçümde anahtar/sıra/sayı aynı;84 negatif gözlem sıfır;1680 kaynak metadata kontrolü geçti. Küçük sorguların ek GUC maliyeti de raporlanır.

Eski üç retrieval kaynağı ile aynı hashing korpusunda127 soru soruldu,105 puanlandı: Recall@5 78/105→77/105;MRR0.618175→0.634444. İlk adayda mechanical_nonregression=false; bu olumsuz kayıt korunur. H-121 kaynak sırası3→6, H-068 sıra6→ilk8 dışı. Eşik/altın set değiştirilmedi. 167parça/22belge, gerçek dou_app/FORCE RLS, before-after içerik/vektör hashleri eşit;LLM çağrısı0. Hashing semantik kalite kanıtı değildir. Daha sonra gerçek önbellekli E5 ile de ilk adayda 93/105→92/105 düşüşü ölçüldü. Çapraz iki dense × iki FTS tanısı gerilemeyi FTS eşit skor sırasına bağladı. FTS değişikliği geri çekildikten sonra aynı son kaynakla iki tam kol tekrarlandı: hashing 78/105 ve MRR0.618175; E5 93/105 ve MRR0.737721, her biri baseline ile aynı. Son E5 retrieval kabulü geçti; insan/LLM cevap ve puanlama kabulü ayrı kalır. RLS kapalı deney ve CIpgvector0.8.6 eşdeğerliği henüz koşulmadı;yerel uzantı0.8.0.

Son log/hash/arşiv yolları yeni değişim kanıt kaydına bağlanır. Eski A/S ve B ara sonuçları bu bölümle değiştirilmez. Yerel belgelerin son sayısal kontrolü ve temiz commit/PR kapıları ayrıca kaydedilecektir.


D3 ayrı adayın ilk gerçek yedeği tamamlandı; geri yükleme iki yeni boş hedefte CURRENT_DATABASE_FENCE_REJECTED ile reddedildi. Hedeflerin bağlantıları açık, tabloları boş kaldı; kurtarma başarısı iddia edilmez. Güvenli bakım bağlantısı protokolü ve gerçek restore/rol/RLS/pgvector tatbikatı ayrı D3 diliminde devam eder. D1/D2/D3 araç kodu bu B/C kontrol noktasına dahil değildir.
