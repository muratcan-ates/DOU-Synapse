---
name: dou-kurulum
description: "DOU-Synapse çalışma ağacı, bağımlılıklar, yerel sunucu ve izole test ortamını kur veya kurulum arızasını teşhis et. Mevcut paylaşılan veri ve diğer çalışan şeritleri koru."
---

# DOU-Synapse ortam kurulumu

İstenen işin kurulum mu yoksa yalnız teşhis mi olduğunu ayır. Aktif depoyu `git rev-parse --show-toplevel`, dal/HEAD, `git status --short` ve `git worktree list --porcelain` ile doğrula. Senkron `sources/` dosyaları referanstır. Başka görevlerin değişiklikleri, çalışma ağaçları ve çalışan süreçleri korunur.

## Bağımsız çalışma ağacı

Yeni şerit gerekiyorsa mevcut depodan tam base SHA ile ayrı bir çalışma ağacı aç; iCloud dışındaki kullanıcı çalışma alanını kullan. Mevcut işi sürdürüyorsan sırf skill çağrıldı diye yeni dal açma. Base, dizin, görev sahipliği, test veritabanı adı ve portları feature planında kaydet. Başka şeritte kullanımdaki bir numarayı veya portu alma. Kirli dosyaları sıfırlamak yerine işin sahibiyle kapsamı ayır.

## Bağımlılıklar ve yapılandırma

Depo köküne göre şu kurulumlar kilit dosyalarını değiştirmez:

```bash
uv sync --project apps/api --frozen --extra dev
bun install --cwd apps/web --frozen-lockfile
```

Her çalışma ağacının kendi `.venv` ve `node_modules` dizini olsun. Editable Python kurulumu başka ağaca bağlanabilir; `app.__file__` ve çalışma diziniyle gerçekten bu ağacın kodunun yüklendiğini kontrol et. Ortam değişkenlerinin anlamı için [.env.example](../../../.env.example) ve [yapılandırmayı](../../../apps/api/app/core/config.py) oku. Başka şeridin `.env` dosyasını kopyalama ve sırları rapora yazma.

Sentetik çevrimdışı çalışma için yalnız başlatılan süreçte yerel ortamı, geliştirme kimliğini, sahte sağlayıcıyı ve hashing embedding'i açık seç. Gerçek materyal/sağlayıcı çalışması ayrı yapılandırılır; eksik anahtar veya sahte cevap gerçek kalite kanıtı değildir. Gerçek kimlik ayarlarını yerel test uğruna değiştirme.

## Veritabanı ve sunucu kimliği

Test çalıştırmadan [pytest fixture'ını](../../../apps/api/tests/conftest.py) ve yapılacak komutun yan etkilerini oku: test veritabanı silinip yeniden kurulabilir. Her eşzamanlı koşuya ayrı, açık `TEST_DB_NAME` ver. `TEST_ADMIN_DSN`, `TEST_APP_DSN` ve gerekirse `TEST_WORKER_DSN` aynı test sunucusu/port/veritabanına, ayrı doğru rollere gitmeli. Kalıtılmış PostgreSQL yönlendirme değişkenlerini ve istemci ayarlarını kontrol et; isim kontrolünü hedef bağlantı kontrolünün yerine koyma. Uygulama rolü tablo sahibi veya RLS atlayan rol olmamalı.

Yeni rollerin kurulması cluster kapsamındadır; başka şeridin rol parolasını değiştiren ortak kurulum betiklerini çalıştırma. Varsa doğru rolleri kullan; yeni küme gerekiyorsa yalnız bu iş için yerel, izole küme hazırla. Göç ve sentetik seed yalnız doğrulanmış, bu işe ait hedefe uygulanır. Ortak demo dersini veya mevcut değerlendirme verisini temizleme.

API ve web için boş portları belirle. API CORS, web API adresi ve tarayıcı test adresleri birbiriyle eşleşsin. Kullanılabilir süreç/terminal aracıyla başlat; belirli bir aracın veya global launch kaydının varlığını varsayma. Başlattığın süreç kimliklerini kaydet. Hazır olma yanıtı, gerçek OpenAPI sözleşmesi ve doğru çalışma ağacından yüklenen kodla sunucuyu doğrula. Mevcut bir porttaki herhangi bir sunucuyu doğru aday sayma.

Embedding modeli ile mevcut korpusun uzayı eşleşmeli. Gerçek E5 korpusuna hashing sorgusu yapma. Isınma sırasında hazır olma uç noktasının geçici 503 yanıtı hata olmayabilir; sınırlı bekleme sonunda hâlâ hazır değilse belirt ve teşhis et.

İş sonunda yalnız bu işin başlattığı süreçleri kapat. Test kayıtlarını koru; genel temizlik veya `git checkout` ile başka değişiklikleri silme. Ortam hazır, test geçti ve gerçek sağlayıcı doğrulandı durumlarını ayrı raporla.
