# Güncel22göç için küçük D3 parite deneyi

Bu yardımcı hazırlanırken DB/ağ işlemi yapılmadı. Root iki yeni yerel veritabanını zaten oluşturdu; `/private/tmp/dou018-evidence/d3-current-provision-01/result.json` gerçek22göç dosya/hash'ini ve uygulama log hash'ini içeriyor. Araç bu makbuzun sabit SHA'sını, altı kimlik pinini ve `input-manifest.json` içindeki22 migration + exact v4 recovery/wrapper dosyasını doğrular. Kaynaklar kirli çalışma ağacına aittir; hazırlık HEAD'i `9af41226d456efb7e20d22cec490566fb8c1a01c` olup commit edilmiş yayın iddiası yoktur.

Sabit kapsam:

- Kaynak `dou018_recovery_current_source01`, OID1161812, SHA `a122f54de62714a8c18edfc5a5073a82a6cbefefed465fa52ecc6adf4b714da4`.
- Hedef `dou018_recovery_current_target01`, OID1161813, SHA `b37b7085aa080a91be6c52d4bb4bbfa33b87d8fe2790923495454d1be88daa55`.
- Cluster7683042491268153327, bakım `postgres` OID5, numeric endpoint127.0.0.1:55448, DBA `muratates`, gerçek uygulama login'i `dou_app`.
- Önceki03/04/09/10 veya başka source/target rotası kullanılmaz. DB/rol oluşturma, silme, migration uygulama veya telafi amaçlı reopen kodu yoktur. Yalnız özgün recovery CLI normal protokolünde hedefin connection fence'ini değiştirir.

## Akış

1. Varsayılan plan sıfır-etkilidir: kaynak/ortam okuma, dosya yaratma veya DB erişimi yapmaz.
2. `--execute` yalnız root tarafından sağlanan bütün pinler ve özel env rotaları eşleşince çalışır. Yeni0700 çıktı dizini açılır. Source/target/maintenance canlı metadata kimlikleri ve aynı postmaster bağlanır; hedefin template0 boşluğu görülür.
3. Source üzerindeki tek kısa transaction, bütün uygulama tablolarını kilitler ve hepsinin boş olduğunu doğrular. Yalnız kanonik `app.request_rate_policies` iki satırı istisnadır. 0025/26 alanları, claim constraint, aktif-job unique index, SECURITY DEFINER/search_path ve app/worker grants kontrol edilir. Root'un gerçek22göç uygulama makbuzu ayrı kanıttır; bu kontroller onun yerine tarih uydurmaz.
4. Yalnız sentetik iki profil (öğretmen ve üye olmayan), tek ders ve öğretmen üyeliği, completed/uploaded/failed üç belge, completed/pending/failed üç job, bir adet1024boyutlu basit vektör ve tek kota penceresi yazılır. Yeni revision1 ve non-processing claim alanlarının NULL olduğu doğrulanır. Pending job2100'e ertelenmiştir; hiçbir worker/API bu yeni DB'ye yöneltilmemelidir. Kaynak dosya/storage nesnesi oluşturulmaz; `storage_path` yalnız açıkça sentetik placeholder'dır.
5. Bütün seed/gözlem bağlantıları kapandıktan sonra **repodaki exact v4 `scripts/recovery.py` CLI** gerçek backup ve restore yapar; seed dışında helper restore davranışını monkeypatch etmez. Source/target SHA ve gerçek committed makbuzu kontrol edilir. Yedeğin manifestinde22migrationhash'i eşleşir. V4 `tracked_schema_dirty` yalnız tracked değişiklikleri kapsar; yeni untracked göçleri kapsamadığı, root'un ayrı `working_tree_dirty:true` makbuzu ile birlikte raporda açıkça belirtilir.
6. Source/target üzerinde READ ONLY REPEATABLE READ işlemleriyle bütün nonextension yerel uygulama tabloları ve kolonları karşılaştırılır. Her tablo en çok100 satır; her satırın DB'de kanonik JSON SHA'sı sıralanıp çoklu-küme özeti çıkarılır. Satır/metin veya tekil hash rapora çıkmaz. Katalog, owner/ACL, metadata ve ilgili çift yönlü rol bileşeni eşittir.
7. Gerçek `dou_app` bağlantısı target admin'in gördüğü backendPID/start/user/endpoint ile bağlanır. Öğretmen üç belge/job ve bir vektörü görür; üye olmayan hepsinde0 görür. Her iki kimlik için quota tablolarına doğrudan okuma gerçek42501 üretmeli, yalnız izinli policy helper'ı2satır döndürmelidir. Tek sentetik vektörün mesafesi ve RLS kapsamı kontrol edilir. Bu **ANN/semantik kalite eşiği değildir**; önceki20k deneyi bağımsızdır.

## Root komutu ve ortamı

Özel wrapper içinde:

- `DOU_BACKUP_PGHOST/PGPORT/PGDATABASE/PGUSER`:127.0.0.1/55448/current_source01 tam adı/muratates.
- `DOU_RESTORE_` aynı alanlar:127.0.0.1/55448/current_target01 tam adı/muratates.
- `DOU_MAINTENANCE_` aynı alanlar:127.0.0.1/55448/postgres/muratates.
- `D3_CURRENT_APP_` aynı alanlar:127.0.0.1/55448/current_target01 tam adı/dou_app.
- Gerekli mevcut credential/passfile değerlerini ilgili özel önekte tut; CLI argümanına veya stdout'a koyma.
- `DOU_RECOVERY_PG_BIN=/opt/homebrew/opt/postgresql@16/bin`.

```sh
/Users/muratates/code/dou-synapse-018-codex-production-line/apps/api/.venv/bin/python /private/tmp/dou018-d3-current-parity/run.py \
  --execute --output /private/tmp/dou018-d3-current-parity-result-01 \
  --cluster 7683042491268153327 \
  --source-oid 1161812 --source-sha a122f54de62714a8c18edfc5a5073a82a6cbefefed465fa52ecc6adf4b714da4 \
  --target-oid 1161813 --target-sha b37b7085aa080a91be6c52d4bb4bbfa33b87d8fe2790923495454d1be88daa55 \
  --maintenance-oid 5 --maintenance-database postgres --maintenance-role muratates \
  --dba-role muratates --host 127.0.0.1 --port 55448
```

CLI stdout yalnız durum/sabit kod ve göç sayısıdır. `result.json`, özel CLI stdout/stderr ve kendi yedeği0700/0600 çıktı altında kalır; yedek kişisel/idarî veri içerebilen executable SQL olarak korunmalıdır. Root kaynak ve hedefte başka istemci/DBA değişikliği olmadığını sağlar; açık numeric endpoint kontrolü ayrı kötü niyetli local proxy/DBA yönetimini engellediğini iddia etmez.

Hata olursa tekrar seed veya restore otomatik yapılmaz. Seed COMMIT veya restore COMMIT yakınındaki bağlantı kaybı ayrı manuel durum incelemesi gerektirir. CLI180s sınırına ulaşırsa önce kendi CLI'sına SIGTERM verilerek özgün cleanup'a8s tanınır, sonra yalnız kendi süreç sonlandırılır; yine hiçbir başarısız hedef yeniden açılmaz. Kaynak ve hedef DB'ler deney sonunda silinmez.

Çevrimdışı9test ve izole Ruff kontrolü geçti; bunlar gerçek mini DB deneyi yerine geçmez.
