# Doğrulama — 018

Tarih: 2026-09-08. Taban: `621815908d5372d8de414aec4ca1dc63da008dca`. Her kontrol noktası kendi dossier/commit ve kaynak hashlerine bağlanır. Aşağıdaki A/S/B/C/D bölümleri tarihsel ölçümlerdir; bir bölümün sonucu yeni kaynakta yeniden koşulmuş sayılmaz. Son güncel kabul en sondaki OPS/D6 bölümündedir.

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


## Kesin S/B/C hosted kabulü ve D1 yerel devam — 8 Eylül

PR26 target017;9af41226d456efb7e20d22cec490566fb8c1a01c üzerinde GitHub CI34220885206 (API,web,belgeler,imaj/ağsız embedding ve gerçek tarayıcı), AI quality34220885195, Agent skills34220885222 ve Security34220885177 başarılı. [Tam durum/zaman makbuzu](evidence/bc-hosted-exact-head-final.json). PR açıklaması sonuçla güncellendi; draft ve maintainer_can_modify=false korunur. Bu kanıt sonraki yerel D kaynaklarını kapsamaz.

D1 ilk yerel aday:0025 ortak kota, ayrı kontrol COMMIT'i, fail-closed503/Retry-After, okuma amaçlı readiness, içeriksiz sağlık hata kaydı ve dürüst export/gizlilik kapsamı. Eski kullanılmayan bellek sayacı kaldırıldı; eski beş sayaç testi yerini yeni kalıcı kota/işlem testlerine bıraktı. Gerçek sohbet kapsamı dolsa da soru üretimi kabul edilir; qgen300sn başlığı gerçek uçta doğrulanır.

Tam API1519 geçti,5 mevcut PyMuPDF uyarısı ve38 alt vaka;92.20s pytest/102.276s kurulumla birlikte. Test veritabanı dou018_d1_api_full01 fixture sonunda kaldırıldı; kaynak hashleri koşu boyunca aynı. [Makbuz](evidence/d1-first-local/full-api.json), [log](evidence/d1-first-local/full-api.log.gz). İlk iki odak turunda yalnız yeni test fixture kullanım hataları vardı (yanlış enroll_student argümanı, yerel worker fixture varsayımı ve geçersiz example.invalid üyelik e-postası); bu kayıtlar arşivde korunur, ürün güvenlik kontrolü gevşetilmedi.

Bağımsız iki süreçli SQL adayı10/10 geçti: dou_synapse_d1_sql01/OID908186,yerel PG160014. Çalışma sonunda profiles/courses/memberships/windows fixture sayıları0. Bu doğrudan SQL deneyi iki HTTP sunucusu kanıtı değildir. [Makbuz](evidence/d1-first-local/pg10.json). SQL aday adı0023'tü; son0025 dosyasında yalnız yorum/numara açıklaması değişti, advisory namespace15023 korunur. Son yerel API gerçek0025 ile kuruldu.

API Ruff temiz;185 kaynak/test dosyası biçim uygun;111 uygulama kaynağında mypy temiz. Bu üç çıktı araç yanıtında gözlendi, yeniden çalışmış log uydurulmadı. OpenAPI57 yoluyla kayıtlı sözleşmeyle nesne olarak eşit. Bu ilk kontrol noktasında iki-HTTP,worker periyodik TTL ve D1'in hosted kabulü henüz yoktu; sonraki HTTP sonucu aşağıda ayrı kaydedilir. D2/D3 kaynakları bu ilk D1 koduna dahil değildir. Arşiv byte/hash listesi [archive.json](evidence/d1-first-local/archive.json).


## D1 gerçek iki HTTP süreci ve D2/D3 ara kanıtı — 8 Eylül

Bu bölüm o ara kontrol noktasını korur; sonraki yerel entegrasyon aşağıdaki güncel ekte kayıtlıdır.

[Taşınabilir HTTP arşivi](evidence/d1-http-local/README.md): iki gerçek API sürecinde 55 ürün isteği,40 ortak kota isteğinde20 kabul/20 ret;7 kontrollü sağlayıcı olayı. Politikası uyuşmayan veya kontrol kilidi zaman aşımına uğrayan istek sağlayıcıya ulaşmadan503 alır. Soru üretiminde5 kabul/2 ret ve Retry-After300 doğrulandı; öğrenci403 alır. Dört gerçek dou_app havuzu aynı beklenen DB kimliğini ve RLS etkinliğini gösterir. Sağlayıcı hatası ana sohbet işlemini geri alırken kabul edilmiş kota korunur. Bağımsız salt okunur denetim ham kayıtlar/kaynak hashleriyle uyumlu. Ara SQL skalerleri ayrı ham dosya olarak saklanmamıştır; kaynak bağlı assertion ve exit0 kanıtıdır. Gerçek JWT/LLM veya çok makine kabulü değildir.

İlk HTTPv1 fixture eksikliği sunucu başlamadan hata verdi; arşivde korunur. V2 sadece topics.created_by test verisini tamamladı. D1 worker TTL ve yeni hosted kabulü halen açık.

D2 kaynakları henüz kök depoya uygulanmadı. Donuk adayın ayrı staging kopyasında91 test (10 yeni gerçek PostgreSQL yarışı dahil) geçti; gerçek süreç kesintisi/devralma ayrıca yürütülür. D3v4 ayrı hedefte24.39s'de kesin COMMIT ile restore oldu; sonraki salt okunur incelemede29 ilişkinin şema/satır hashleri, rol/ACL ve dört gerçek uygulama RLS kimliği eşleşti. Tek restore sorgusundaki ANN recall@8=.875 kaydedildi; bu C1 tam retrieval kabulü değildir. Başarısız03/04 hedefleri kapalı tutulur; D3 gerçek hata tatbikatı ve kaynak entegrasyonu tamamlanmış sayılmaz.


## D1/D2/D3 ve S8 yerel entegrasyon — önceki 9af üstü kontrol noktası, 8 Eylül

Bu ek,9af4122 üzerindeki kirli çalışma ağacını ve ayrı kaynak hashlerine bağlı yerel deneyleri anlatır. Önceki hosted kabulü bu kaynaklara genişletilmez. Arşiv hedefi `evidence/d-final-local/`; önceki [D1 HTTP](evidence/d1-http-local/README.md), [D2](evidence/d2-local/README.md) ve [D3](evidence/d3-local/README.md) makbuzları değiştirilmez.

| Kontrol | Sonuç ve kapsam |
|---|---|
| D1 gerçek HTTP | İki API sürecinde 55 istek; ortak20 kabul/20 ret, rol/kapsam ve503/Retry-After kapıları geçti |
| D2 stage02 | 98 test geçti: önceki91, gerçek lineage regresyonu ve6 app/worker yetki testi; kaynaklar değişmedi |
| D2 gerçek süreç v2 | 8 senaryo,19.919 s, exit0; gerçek iptal/SIGTERM/SIGKILL/devralma, eski token reddi, canary ve başlangıç kota temizliği |
| D3 güncel şema | 22 göçle 30 ilişki, toplam 14 sentetik satır, güvenlik kataloğu/rol bileşeni eşliği; gerçek eğitmen/dış kullanıcı ve doğrudan kota 42501 kontrolleri geçti |
| S8 ASGI | 21 kontrol geçti; rota şablonu ve Uvicorn erişim kanalı sınırı entegre |
| S8 gerçek Uvicorn v2 | Eski/yeni kaynakların her birine üç gerçek HTTP isteği; adayda dört ham canary ve uvicorn.access kaydı yok, başlangıç/kapanış korunuyor; DB bağlantısı denemesi 0 |
| İlk birleşik tam API | 1560 geçti, 1 başarısız, 5 mevcut PyMuPDF uyarısı, 38 alt vaka; 106.31 s pytest/117.09 s kurulumla birlikte. Genel sonuç failed; tarihsel kayıt korunur |
| Son birleşik tam API03 | 1561 geçti, 5 mevcut PyMuPDF/Swig uyarısı, 38 alt vaka; 102.75 s pytest/113.344 s kurulumla birlikte. Exit0, kaynak hashleri değişmedi; geçici DB kaldırıldı |

D2'nin ilk süreç koşusu sekiz davranışı geçse de son parent gizlilik denetiminden kaldı. Ham parent log atıldığından tam eşleşme sonradan belirlenemez; v1 genel failed korunur. V2 yalnız bilinen fixture uploadunun app.request rota UUID'sini ayrı metadata olarak gözledi; içerik/auth/DSN/parola yok ve diğer alanlarda kimlik eşleşmesi yoktu. Eski süreçteki üç stale-token yardımcısı aynı eski PID'de ayrıca çağrıldı; hepsinin otomatik pipeline hata dalından geçtiği iddia edilmez. Bu ölçüm S8 rota minimizasyonundan öncedir.

Worker başlangıç bakımı expired quota satırını sildi ve canlı satırı aynen korudu. Dört yaşam döngüsü birimi grace içinde bitiş, grace aşımı, bakım hatasının ingestion'dan ayrılması ve kontrollü bekleme sonrası tekrar planlamayı sınar. Gerçek 60 saniyelik dönem veya scale-to-zero saklama SLA'sı değildir. asyncio.to_thread iptali çalışan parser/model thread'ini öldürmez; süreç kapanışı executor'u bekleyebilir. Kontrollü async depolama bariyeri kesin duvar saati kapanış garantisi vermez.

D3 güncel kaynak deneyinin root makbuzu 1.252 s/exit0; yedek 0.397 s ve restore 0.422 s olarak ölçüldü. 30 ilişkinin 28'i public, 2'si app şemasındadır; toplam 14 satır ve bütün karşılaştırma eşlikleri doğrudur. Kaynakta pending/failed/completed işler ile 0025 kota verisi vardı. Gerçek dou_app eğitmeni 1 ders/3 belge/1 chunk/3 iş gördü, dış kullanıcı bunların hiçbirini görmedi; ikisi de iki quota tablosuna doğrudan erişimde 42501 aldı. Güvenlik kataloğu ve rol bileşeni eşleşti. Tek vektörün görünürlüğü ANN veya semantik kalite kabulü değildir; dış Storage kopyalanmadı. Yedek makbuzundaki tracked_schema_dirty=false alanı untracked 0025/0026 göçlerini dışlar; kesin 22 hash manifesti ve root working_tree_dirty=true makbuzu birlikte değerlendirilir, committed release iddiası yoktur. Eski 20000 vektör/29 ilişki ve hata deneyleri ayrı kalır; 07 yazıcı yarışı, cross-cluster/control-loss ve canlı bulut/saklama/imha kabulü açık.

İlk birleşik tam API koşusu son worker testinin pg_stat_activity kilit gözleminde0.8s zaman aşımına uğradı; LostClaim ve son durum eşliği iddialarına ulaşmadı. Her okumadan önce pg_stat_clear_snapshot çağıran dar gözlemci düzeltmesi gerçek ayrı veritabanlarında geçti; bu çağrı kaldırıldığında test başarısız oldu, geri konduğunda yeniden geçti. Önceden doldurulmuş istatistik görüntüsü bu negatif kontrolü belirginleştirir. 0.8s gözlem sınırı, gerçek satır kilidi, veritabanı saatiyle lease sonunu geçme, LostClaim ve son durum eşliği iddiaları korunur; üretim kodu değişmedi. Ardından sekiz dosyada yalnız import sırası/grup boşluğu düzenlendi; import bağları ve import dışı AST eşliği ayrıca doğrulandı. Son API03 koşusu bu yeni bayt hashlerine bağlıdır; önceki süreç kanıtları kendi kaynak hashlerini korur.

S8 artık kaynakta APIRoute.path_format veya sabit `<unmatched>` yazar ve uygulama log kurulumunda uvicorn.access kanalını kapatır. Kurulu sürüm Uvicorn 0.52.4'tür; ilk donuk nottaki 0.52.3 değeri kurulu manifesti temsil etmez. Gerçek süreç v1 baseline sonrasında fixture kapanışında başarısız oldu; bu kayıt değiştirilmez. V2, aynı bağımlılıklarda iki hash bağlı eski/yeni modül ile gerçek Uvicorn h11 ve app.main yaşam döngüsünü ölçtü: her birinde bilinen rotada401, eşleşmeyen yolda404 ve health/live için200 alındı. Eski kaynakta dört ham canary ve üç uvicorn.access kaydı görülürken adayda bunlar yoktu; uvicorn.error başlangıç/kapanış kayıtları ve kontrollü temiz kapanış korundu. Isınma kapalıydı, psycopg koruyucusu iki süreçte de sıfır bağlantı denemesi kaydetti. Deney genel anonimlik veya hosting/proxy günlüklerinin kabulü değildir. Son birleşik API ve aşağıdaki tarayıcı kabulü geçti; ayrı dossier/commit ve kesin yeni HEAD hosted kapıları ayrıca izlenir. Gerçek LLM/JWT/Storage, üretim ve hukuki uygunluk kabulü bu sonuçlardan türetilmez.


## D/S8 önceki son yerel kabul — 8 Eylül

[Son kanıt arşivi](evidence/d-final-local/README.md)111 girdiyi ve son API/E2E kaynak hashlerini bağlar.68 gerçek Chromium akışı82.187s'de geçti; run mtsqcmai1b9f kendi65 ders ve8 audit kaydını temizledi. İlk koşuda root ayarı localhost:8018, önceden kurulmuş değişmemiş web ise127.0.0.1:8018 kullanıyordu: trace gerçek201 öğrenme çıktısı yazımını gösterse de tam URL koşulu ve route interception eşleşmedi. İlk koşu durduruldu, ürün/test kodu değiştirilmeden doğru adresle tekrarlandı; ilk koşunun kalan6 sentetik dersi ayrı temizlendi. Bu hata yeni worker'ın işlem başarısızlığı diye sınıflandırılmadı.

Son1561 API testinin yanında555 web testi,52 kurtarma aracı testi,104 retrieval aracı testi,26 release testi ve77 yönetişim testi geçti. Ruff/biçim/mypy, web tip/kontrast,22 migration ve belge sayısı kapıları geçti; dinamik OpenAPI57 yolda sürümlenmiş sözleşmeyle yapısal olarak aynı. Son sekiz import düzenlemesi dışında davranış kodu değişmedi; bu düzenleme sonrası tam API03 ve E2E son hashleri doğruladı. Sonradan yapılan READ ONLY gözlemde güncel D3 source/target sabit OID'leri açık ve0 bağlantılı bulundu; ilk active1 makbuzu korunur. Yeni başın GitHub kabulü bu yerel arşivden türetilmez.


## OPS/D6 yerel kabul — c45 üstü yeni kaynaklar, 8 Eylül

Önceki kesin uzak baş `c45e0e7073c92638ced7a3ff523578dd598c350b` üzerinde dört hosted workflow geçti: CI34238925467 (beş iş), AI quality34238925534, agent skills34238925527 ve security34238925449. O kaynaktaki API 1561/38 alt vaka ve E2E 68 sonucu yeni kirli OPS/D6 ağacının hosted kabulü değildir. 030'un Ubuntu geçici-dizin test hazırlığı hatası 031 düzeltmesiyle giderildi; önceki başarısız makbuz korunur.

Yeni dilimin [yerel kanıt arşivi](evidence/ops-local/README.md) kaynak/log/result hashlerini ayrı bağlar. Eski d-final-local arşivi değişmez. Aşağıdaki kabul yerel ve sentetiktir; yeni dossier/commit/PR kapıları ayrıca tamamlanmalıdır.

| Kontrol | Gerçek yeni sonuç ve sınır |
|---|---|
| Tam API | 1571 geçti; 38 alt vaka ayrıca; 5 mevcut uyarı; 104.37s pytest/114.755s kurulumla. 215 kaynak hash'i koşu içinde sabitti, geçici DB kaldırıldı. Sonraki internal.py modül docstring’i, admin test literal düzenlemesi ve kota test ifadesinin satır düzenlemesi ayrı AST eşliğiyle bağlı; byte eşliği iddia edilmez.|
| HTTP/Chromium | 71 geçti; 82.581s. 281 kaynak hash'i aynı; koşu mtstzx3p73fa kendi 65 ders/14 audit kaydını temizledi. Yeni 3 vakanın 1'i gerçek yetkili overview, 2'si gerçek cevaptan türetilmiş kontrollü dependency/eski-alan UI sözleşmesidir. Gerçek kota politika uyuşmazlığı/recovery API/DB testindedir.|
| Yönetim görünümü/klavye | 375 ve 1440 genişlikte açık/koyu dört gerçek API 200 görünümü; yatay taşma yok, ArrowRight/Home odağı geçti. Reduced-motion açıktı. Dört görsel ayrı smoke gözlemidir; 71 paketine eklenip 75 farklı test sayılmaz. Tüm site axe/VoiceOver/manuel kabulü değildir.|
| R1 SQL karakterizasyonu |Kontrol ve gerçek SELECT 1/0 olmak üzere iki kalibrasyon; mevcut yedi admin testiyle 9 PASS, 2.18s test/2.845s toplam. 22012 sonrası gerçek HTTP 200 degraded; aynı transaction'da 25P02; bağımsız bağlantıda 1 allowed audit; sonraki public readiness temiz 200 gözlendi. Kalibrasyon testlerinin geçmesi bu HTTP 200 davranışını otomatik ürün onayı yapmaz; gözlem ayrıca değerlendirildi.|
| D1 gerçek dönem 02 |Başlangıç silmesi 0.544s; sonradan eklenen expired satır 59.973s'de var,60.181s'de yok; canlı satır byte eşit. Saat/60s sabiti değiştirilmedi; SIGTERM 0/0.086s. İlk eksik yerel auth ayarlı koşu başarısız kanıt olarak tutulur.|
| D3 dört negatif |Source-loss 0.447s; açık yazıcı 0.310s; kapalı yazıcı 0.322s; bakım bağlantısı kaybı 0.501s. Gerçek donuk v4 koruma/fence/COMMIT yolları çalıştı; herhangi bir restore-complete sonucu üretilmedi.|

OPS1 read-only helper veritabanı/pgvector, ortak kota ve embedding durumunu public readiness ile yetkili admin özetinde tutarlı gösterir. Admin kendi mevcut oturumunu kullanır; auth/overview öncesi hatayı boş toplamlarla değiştirmez. R1 karakterizasyonunda uygulama transaction/exception/audit kodu değiştirilmedi. Gerçek SQL hata sonrası aynı transaction'ın 25P02 durumu gözlendi; bağımsız audit ve sonraki ayrı public oturum sağlığı ayrıca ölçüldü. Bu sonuç yazım atomikliği, her DB hatasının başarıya çevrilmesi veya bağlantı kaybının güvenli toparlanması garantisi değildir.

OPS2 başarı olayı helper COMMIT döndükten sonra yalnız stage/deleted_windows/duration_ms taşır; sıfır silme bütün expired satırların bittiği anlamına gelmez. Worker geçersiz Settings'i görev/bağlantı başlamadan sabit hata ve çıkış 1 ile reddeder. Yerel Compose HTTP worker/drain'i korur, ayrı `python -m app.worker` poller HTTP portu açmaz; yerel dev-auth üretim auth kabulü değildir. Docker/Compose çalıştırılmadı; gerçek dönem deneyinden scale-to-zero veya fiziksel saklama SLA'sı çıkarılmaz.

D3 açık yazıcı ilk guard'dan sonra COMMIT edip bağlı kalınca maintenance preflight fence/apply öncesinde reddetti; sentinel aynı bağlantıdan tekrar hashlenip eşleşti. Kapalı yazıcı vakasında fence gerçekten COMMIT oldu; final empty guard SQL 101'de reddetti, dump gövdesi 114 ve final COMMIT 5764'e ulaşılmadı, child 3. Hedef kapalı/oturumsuz kaldı; 07b son sentinel bağımsız readback yapılmadı. Source-loss tamamlanma manifesti üretmedi. Maintenance-loss'ta nonce/xid/binding bağlı COMMIT doğrulandı ama reopen tamamlanmadı; kapalı/oturumsuz hedef korundu. Bu kontrollü istemci kapanışları ağ blackhole/reset veya cross-cluster kabulü değildir. Root makbuzundaki source_unchanged alanı runtime dosya hash'idir, DB satır eşliği değildir; eski 20k ve güncel-mini content/RLS tatbikatı bu turda tekrarlanmadı.

Yeni gerçek LLM/hoca, Supabase JWT/Storage, hosting/proxy günlükleri, dış telemetry/alarmlar, kurumsal saklama ve production promotion kabulleri açık kalır. S9/S9B ayrı geçici aday olarak hazırlandı; bu dilimde uygulanmadı veya kabul edilmedi. Yeni hosted başarı, yalnız yeni kesin commit'in kendi makbuzuyla eklenir.
