# D1/D2/D3 ve S8 — son yerel kabul

9af4122 üzerindeki yeni kaynakların yerel kabulüdür; önceki hosted sonucun genişletilmesi değildir. Son kod1561 API testi/38 alt vaka,555 web testi ve68 gerçek HTTP/Chromium akışını geçti. E2E run `mtsqcmai1b9f` kendi65 ders/8 audit kaydını temizledi. API kodu ve22 migration hash'leri tam test ve E2E boyunca değişmedi. Ruff/biçim/mypy, web tip/kontrast,57 yollu OpenAPI sözleşme eşitliği,52 kurtarma aracı testi,104 retrieval aracı testi,26 release testi ve77 yönetişim testi geçti. Sonuç/hash ayrıntıları `archive.json` içindedir.

## Korunan başarısızlıklar ve son kaynak bağı

İlk birleşik API koşusu1560 PASS/1 FAIL üretti: kilit gözlemcisi aynı transaction'da eski `pg_stat_activity` görüntüsünü tutuyordu. Her gözlemde snapshot yenilenmesi ve doğru blocker PID bağı eklendi; gerçek DB'de aday PASS, yalnız yenileme kaldırılınca FAIL, geri yüklenen aday PASS oldu.400ms lease/0.8s gözlem sınırları büyütülmedi. Sonraki tam1561 test geçti. Daha sonra yalnız sekiz dosyanın import grupları proje kuralına getirildi; import bağları ve import dışı AST eşitliği kaydedildi. En son API03 ve E2E bu son baytlara bağlıdır; önceki D2 süreç kanıtları önceki dosya hash'leriyle tarihsel kalır.

İlk tarayıcı koşusu root ayarındaki localhost/127.0.0.1 farkı yüzünden durduruldu. Seçilmiş trace metadata'sı gerçek201 yazımın127.0.0.1 adresinde gerçekleştiğini gösterir; localhost yanıt koşulu ve route interception eşleşmiyordu. Ürün/test kodu değiştirilmedi. Adres eşlenince68 akış geçti; ilk koşunun kalan6 sentetik dersi ayrı run-scope cleanup ile temizlendi. Tam trace yereldir; yalnız içeriksiz seçilmiş ağ metadata'sı arşivlenir.

## Günlük gizliliği

S8 için21 gerçek ASGI/emitted-JSON testi geçti; aynı testler eski kaynakta20, ham adres fallback mutantında9 ve eski Uvicorn kanalı mutantında2 hata yakaladı. Gerçek Uvicorn0.52.4/h11 iki süreç kıyasında401/404/200 yanıtları korunurken dört sentetik canary eski günlükte vardı, yeni günlükte yoktu; `uvicorn.access` kayıtları3'ten0'a indi. `app.request` güvenli şablonları ile `uvicorn.error` başlangıç/kapanış kayıtları korundu, DB bağlantı girişimi0. İlk gerçek probe normal SIGTERM'in Uvicorn tarafından yeniden yükseltilmesi nedeniyle son test makbuzuna ulaşamadı; eski kanıt değiştirilmedi. İkinci probe özel pipe üzerinden normal server.should_exit kapanışıyla tamamlandı. Rota şablonu, serbest istisna metni, istek kimliği, dış proxy logları veya bütün sistem için anonimlik garantisi değildir. Donuk öneri metnindeki0.52.3 sürüm yazımı hatalıydı; ölçülen manifest/süreç sürümü0.52.4'tür.

## Güncel şema kurtarma eşliği

Önceki20k vektörlü D3 deneyi eski şema sürümündedir. Ek küçük deneyde root'un yeni22 migration kaynağı gerçek CLI ile yedeklendi ve ayrı boş hedefe kesin COMMIT ile döndürüldü.30 uygulama ilişkisinde14 sentetik satırın hash/kolon eşliği, owner/ACL/rol bileşeni ve yeni quota/claim şeması doğrulandı. Gerçek dou_app öğretmeni1 ders/3 belge/1 chunk/3 job gördü; üye olmayan0 gördü. İki kota tablosuna doğrudan okuma her iki rolde42501 verdi.1024 boyutlu tek sentetik vektörün okunması ANN veya LLM kalite ölçümü değildir. Yedek dump/özel SQL bu arşive konulmadı.

Root'un ilk after makbuzunda hedefte1 bağlantı görüldü. Daha sonraki ayrı READ ONLY ölçümde her iki sabit OID açık ve0 bağlantılı bulundu; ilk kayıt yeniden yazılmadı. Backup manifestinin tracked-dirty alanı yeni untracked migration dosyalarını kapsamıyordu; gerçek22 dosya hash'i ve ayrı root dirty/provision kaydı birlikte korunur. Bu teknik kaynak eşliği canlı yayın onayı değildir.

07 eşzamanlı writer/fence, cross-cluster/control-loss ve ilave rol grafiği deneyleri; dış storage tutarlılığı, şifreleme/saklama/imha/restore sonrası silme uzlaştırması; gerçek dönem/scale-to-zero işletimi ve kurumsal kararlar açık. Worker threaded parser/embed için mutlak duvar saati kapanış garantisi yoktur. D1 ortak istek kotası, soru üretiminin ayrı süreç içi aktif eşzamanlılık kapısını ortaklaştırmaz.
