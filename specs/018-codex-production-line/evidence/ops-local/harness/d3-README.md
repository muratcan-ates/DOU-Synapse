# D3 sonraki yerel olumsuz deney adayı

Bu dizin yalnız hazırlıktır. DB bağlantısı, gerçek araç/uygulama süreci veya deney çalıştırılmadı. Root inceleyip yeni hedefleri sağladıktan sonra çalıştırır. Repo kaynağı değiştirilmez. Hazırlık tabanı `c45e0e7073c92638ced7a3ff523578dd598c350b`; üretim `scripts/recovery.py` özeti değişmeyen `a0bc48077e2fbdcfc904e31d08750b5c0b858cf737f83f35389cde5661f1777b`.

## Sınır ve girdiler

- Gerçek mevcut v4 `backup`/`restore` fonksiyonları, gerçek psql/pg_dump/pg_restore ve gerçek psycopg bağlantıları kullanılır. CLI'nin argüman ayrıştırıcısı yeniden sınanmaz. Yalnız aşağıda belirtilen faz dönüşleri çevresine bariyer/bağlantı kapatma kancaları eklenir; SQL guard'ları, sonuçları, dump, COMMIT zarfı ve izinler değiştirilmez.
- Kaynak önceki güncel 22 göçlü küçük sentetik `dou018_recovery_current_source01`, OID `1161812`, fingerprint `a122f54de62714a8c18edfc5a5073a82a6cbefefed465fa52ecc6adf4b714da4`. Kaynakta yazım yapılmaz.
- Restore girdisi `/private/tmp/dou018-d3-current-parity-result-01/own-backup`. Manifest ve 248395 byte dump'ın SHA değerleri runner içinde sabittir. Bu, önceki root başarılı backup makbuzuna bağlı kendi sentetik yedeğidir; özel dump repo kanıtına kopyalanmaz.
- Root her restore vakası için yeni template0 hedefini oluşturur: `dou018_recovery_next_07a01`, `dou018_recovery_next_07b01`, `dou018_recovery_next_ctrl01`. Araç DB/rol oluşturmaz, mevcut hedefi silmez ve yetki genişletmez. Önceki03/04/09/10 veya başka hedef adları kabul edilmez.
- Ayrı `postgres` bakım veritabanı, sayısal loopback, açık port, aynı cluster, root sağladığı OID/fingerprint ve mevcut DBA rolü gereklidir. Fixture writer aynı mevcut DBA yetkisiyle yalnız yeni hedefte tek sentetik tablo oluşturur. Bu bir öğrenci yetki saldırısı veya kötü niyetli DBA'ya direnç iddiası değildir.
- Root pin JSON'u komutta ayrı SHA ile bağlanır. Yeni bakım gözlemleri READ ONLY'dir; ürün bakım bağlantıları gerçek fence için mevcut yazma yetkisini kullanır. Ad/OID/cluster/postmaster kontrolleri gerçek bağlantılardan tekrar yapılır.
- Private FD yakalayıcısı daha önce dondurulmuş `/private/tmp/dou018-d3-negative-runner/runner.py` içinden yalnız `Observer` sınıfını kullanır; dosyanın `356a896a…` SHA'sı zorunludur. Eski runner çalıştırılmaz, global hedef haritası veya runtime kodu değiştirilmez.

## Önceden tanımlanan dört kabul senaryosu

| Vaka | Kesin kontrol olayı | Beklenen olumsuz sonuç | Hedef / kaynak son durumu |
|---|---|---|---|
| `writer_open` (07a) | Gerçek `TargetSession.guard` başarıyla döndükten sonra ikinci gerçek bağlantı CREATE+INSERT COMMIT yapar; bağlantı açık kalır. | Bakımın ilk gerçek session-count doğrulaması `TARGET_SESSION_BINDING_OR_COUNT_CHANGED`; fence ve apply hiç çağrılmaz. | Hedef açık kalır. Writer'ın kendi bağlantısından aynı tek satır hash'i doğrulanır, ardından yalnız kendi bağlantısı kapanır; son bağlantı sayısı0. |
| `writer_closed` (07b) | Aynı guard sonrası ikinci bağlantı yazıp COMMIT eder ve kapanır. Bakım gözlemcisi writer backend'inin bittiğini, hedefte yalnız kalıcı psql kaldığını gerçek katalogdan görmeden akış ilerlemez. | Gerçek maintenance fence COMMIT başarılı. Scriptin ilk işlem içi boşluk guard'ı `TARGET_NOT_EMPTY_OR_UNAUTHORIZED`; psql exit3, COMMIT makbuzu yok, reopen çağrısı yok. | Hedef kapalı ve bağlantı sayısı0 kalır. Son sentinel okuması bu runner tarafından yapılmaz. |
| `source_loss` | Gerçek exported-snapshot pg_dump başarıyla döner dönmez yalnız bu backup'ın kendi psycopg kaynak bağlantısı `.close()` ile kapatılır. Gerçek archive `--list` sonraki aşamada tamamlanır. | Context'in gerçek son kontrolü `SOURCE_SNAPSHOT_CONTROL_FAILED`; başarılı backup makbuzu ve completion manifesti yok. | Özel kısmi dump korunur; source metadata/cluster önce-sonra eşittir. Hiçbir hedef bağlantısı yok. |
| `maintenance_loss` | Gerçek fence COMMIT ve son doğrulaması döndükten sonra yalnız o restore'un kendi bakım bağlantısı `.close()` ile kapatılır. | Gerçek target restore ve nonce/xid8 COMMIT doğrulaması tamamlanır; kapalı bakım bağlantısında reopen çalışamaz. Sonuç `RESTORE_COMMITTED_FENCE_REOPEN_UNCONFIRMED`. | Hedef kesin committed fakat kapalı, bağlantı sayısı0. Otomatik reopen yok. |

07a/07b zamanlama için rastgele sleep kullanmaz: kanca orijinal guard'ın gerçek yanıtından sonra ilerler. 07b'deki en çok3 saniye/100ms aralıklı katalog gözlemi yalnız kapanan writer backend'inin çıkış bariyeridir; yarış oluşturma aracı değildir. Root sunucu slotunu bu sırada başka DB testiyle paylaşmamalı. Her vaka tek koşudur; önceki hedef tekrar kullanılmaz.

Kontrol kaybı gerçek istemci tarafı bağlantı kapanmasıdır. İstisna sahte olarak fırlatılmaz ve sonuç makbuzu gizlenmez. Bu, kernel/network reset, paket kara deliği, cluster değişimi veya COMMIT ile bağlantı kaybının aynı ana gelmesi deneylerinin yerine geçmez. Kaynak kontrol kaybı özellikle **dump tamamlandıktan sonra completion** sınırını ölçer; pg_dump ortasında exported snapshot kaybı iddiası yapılmaz.

## 07b için ayrı inceleme; runner otomatik açmaz

İlk SQL hata kodu/satırı, private script SHA'sı, psql exit3, ilk işlem içi guard'ın üretilen source DDL/COPY/ACL ve son COMMIT'ten önce olduğu bağımsız incelenmeli. Bunlar kesin erken başarısızlığı desteklerse root **yalnız yeni07b OID** için ayrı guarded maintenance açılışına karar verebilir. Ondan sonra READ ONLY sentinel hash'i ve initial target owner/ACL/format/role + tek sentinel DDL eşliği ölçülebilir. Bu ikinci aşama henüz runner'a eklenmemiştir; current negative PASS sentinel'in son satır eşliğini tek başına iddia etmez. 03/04/09/10 veya unknown durumda başka hedef açılmaz.

## Negatif orakıl ve kanıt

`negative-acceptance-pass` gerçek ürün işleminin beklenen noktada reddedildiği anlamına gelir. Bir hata kodunun gelmesi tek başına yeterli değildir: faz bayrakları, gerçek fence dönüşü, gerçek COMMIT doğrulaması, child exit, final allow_connections ve bağlantı sayısı birlikte doğrulanır. Beklenmeyen başarılı restore makbuzu her vakayı başarısız yapar.

07a ilk session kapısını, 07b son empty kapısını ayırır. Bir kapı kaldırıldığında sonraki güvenlik katmanı işlemi hâlâ durdurabilir; bu savunma derinliğini ürün açığı gibi yorumlamayacağız. Test beklenen kapının çalıştığını da ölçer. Ek mutation koşuları henüz uygulanmış/çalıştırılmış değildir.

Her koşu yeni0700 çıktı dizini ve0600 JSON/private FD dosyaları oluşturur; eski kayıtların üstüne yazılmaz. Private stdout/stderr/SQL sadece yerelde kalır. Kullanıcı çıktısında sabit sonuç kodu; raporda yalnız metadata/hash/phase ve sentetik bağlantı bağları bulunur. Runtime SHA her koşu sonunda yeniden kaydedilir. Kaynak `.close()` veya ürün çocuğunun kendi cleanup'ı dışında `pg_terminate_backend`, başka süreç sinyali, ALTER/reopen veya veri silme kancası yoktur. Fence/reopen SQL'ini yalnız gerçek üretim restore'u yürütür.

## Root çalıştırma sırası

1. `pins.example.json` kopyasını her vaka için gerçek root OID/cluster/rol/port değerleriyle doldur ve SHA'sını al. `source_loss` için `target:null`; diğerlerinde doğru sabit yeni hedef adı/OID/fingerprint. Yeni hedeflerin template0, açık ve boş olduğunu root provisioning makbuzunda kaydet.
2. Önce statik/bağımsız kod incelemesi, istenirse yeni hafif offline kontrat kontrolleri. Bu aday hazırlanırken yalnız sözdizimi/AST okunmuştur; pytest/unittest veya CLI çalıştırılmamıştır.
3. `DOU_BACKUP_*` kaynak, `DOU_RESTORE_*` seçilen hedef, `DOU_MAINTENANCE_*` postgres için mevcut özel ortamda açık numeric endpoint/port/DBA rolünü ayarla. `DOU_RECOVERY_PG_BIN=/opt/homebrew/opt/postgresql@16/bin`. Sırlar komuta veya rapora yazılmamalı.
4. Sıra önerisi `source_loss` → `writer_open` → `writer_closed` → `maintenance_loss`. Her biri ayrı yeni output. İlk başarısız oracle'da sonraki hedefe ilerlemeden incele.

```text
apps/api/.venv/bin/python /private/tmp/dou018-d3-next-candidate/run.py --case writer_closed
apps/api/.venv/bin/python /private/tmp/dou018-d3-next-candidate/run.py --case writer_closed --execute --pins /private/tmp/ROOT-PIN-FILE.json --pins-sha256 ROOT_CALCULATED_SHA --output /private/tmp/dou018-d3-next-writer-closed-01
```

İlk komut bağlantısız plan; execute olmadan pin/backup dosyası bile okunmaz. Root gerçek deneyi kendi bounded üst runner'ında çalıştırır ve dış süre sınırına ulaşırsa yalnız o kendi sürecinin normal cleanup'ını kullanır; belirsiz hedef üzerinde düzeltici otomasyon yoktur. Sonuç gelmeden dokümantasyondaki açık07/control-loss kapıları kapatılmaz.
