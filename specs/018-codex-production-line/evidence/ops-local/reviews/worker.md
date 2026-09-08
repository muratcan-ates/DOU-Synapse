# Dönemsel worker bakımı — bağımsız statik inceleme

Kapsam: root'un ilk dirty worker başarı logu, yeni Compose poller, ek unit test ve v1 gerçek dönem runner'ı. Bu inceleme DB/test/uygulama süreci çalıştırmadı, repo dosyası değiştirmedi. Root v1 başarısız sonucunu koruyor. İnceleme sonunda eklenen erken get_settings doğrulaması ve local poller DEV_AUTH ayarı da salt okuyarak tekrar değerlendirildi; doğru yerde ve kapsamda. Gerçek v2 süreç sonucu bu incelemede ölçülmedi.

## Geçerli bulgu ve gerekli düzeltme

Yeni docker-compose.yml worker-poller environment bölümünde DEV_AUTH_ENABLED ve SUPABASE_JWT_SECRET yok. Settings'in config.py:378–379 denetimi bu local yapılandırmayı reddeder. Mevcut run_forever hata alan drain/bakım task'larını warning ile devam ettirdiğinden süreç canlı görünüp iş/bakım yapamayabilir. Root'un bildirdiği gerçek v1 yalnız başlangıç ve sabit warning üretmesi bu statik yolu doğruluyor; 60 saniye dönem başarısı değildir.

Dar çözüm: HTTP listener açmayan **local** poller'a mevcut Compose API/HTTP worker ile aynı DEV_AUTH_ENABLED=true koymak ve run_forever başlangıcında Settings'i doğrulamak. Üretim auth validator'ı veya rol izinleri gevşetilmemeli. Başlangıç doğrulaması bakım/drain task yaratımından ve worker başlatıldı mesajından önce gelmeli. Geçersiz ayarda sabit içeriksiz error + SystemExit1; raw ValidationError veya chained canary loglanmamalı. Testler bu başarısızlıkta task/drain/engine başlamamasını ve canary'nin emitted çıktıda olmamasını doğrulamalı.

## Korunan sınırlar

- apps/api/app/core/request_quota_maintenance.py:28–37, count'u session.begin bağlamı kapandıktan sonra döndürür. Yeni worker başarı kaydı gerçekten helper dönüşünden sonra; COMMIT beklerken başarı yok. Sonuç0 yalnız bu batch'in sonucu, toplam backlogun bittiği iddiası değil.
- Log context yalnız stage/deleted_windows/duration_ms; kullanıcı/course/DB kimliği veya satır gövdesi yok. Mevcut hata warning'inde exc_info/cause yok. Unit barrier helper dönüş sırasını sınar; tek başına gerçek SQL COMMIT kanıtı değildir.
- Mevcut HTTP worker servisi, /internal/drain adresi, ortak sır ve ortak storage volume korunur. Poller aynı dar dou_worker veri yolu ve mevcut0026 claim/lease korumasını kullanır; yeni HTTP/socket listener ya da host portu eklenmez. Dockerfile EXPOSE metadata'sı kendi başına listener açmaz; HTTP HEALTHCHECK mirası yok.
- stop_grace_period15s, uygulamanın varsayılan5s süresinden uzun. Threaded parser/model için mutlak kapanış garantisi getirmez. restart policy bakım/retention SLA'sı değildir; yorum da bunu açık tutar.

## V1 runner'ın kabul sınırı

İzole yeni DB,22 migration, özel env, gerçek python -m app.worker ve gerçek PostgreSQL expiry kullanılıyor. Önce başlangıç COMMIT'i satırın kaybolmasıyla gözlenip **sonra** yeni expired satır ekleniyor. 58 saniye alt sınırı/75 saniye gözlem bütçesi, canlı qgen satırının byte eşliği, iki gerçek başarı logu ve kendi SIGTERM çıkışı açık orakıllar. Runtime hash'leri başlangıç/son karşılaştırılıyor. Saat/period patch'i yok.

Bunlar başarılı v2 koşusunda dar gerçek dönem kabulünü destekleyebilir; v1 fail korunmalı. Compose container'ın çalıştığı, hosting/scale-to-zero bakım takvimi veya maksimum fiziksel retention süresi bu bağımsız Python deneyiyle kanıtlanmaz. Canlı qgen/expired chat satırları doğrudan sentetik admin seed'i olduğu için gerçek kota admission davranışını yeniden doğrulamaz; konu yalnız worker purge yetkisi ve dönemidir.

Yeni İngilizce yorum/docstring'ler runbook'un Türkçe yorum kuralıyla uyumsuz küçük bir dil düzeltmesi gerektiriyor. Kaynaklara aktif gerçek koşu boyunca dokunulmamalı; sonraki source binding bu byte değişikliklerini de doğru sürüme bağlamalı.

## Son eklenen startup kontrolü

worker.py:106–118 Settings doğrulamasını worker başlatıldı logundan ve create_task çağrılarından önce yapıyor; hata fixed context ile yazılıp SystemExit(1) from None veriliyor. docker-compose local poller DEV_AUTH_ENABLED=true eklendi. Yeni negatif unit test, DB factory/drain/bakım await edilmemesini ve canary taşınmamasını denetliyor. Küçük test dayanıklılığı önerisi: doğrudan run_forever await'ini aynı-task asyncio.timeout(1) ile sınırlamak; startup guard kaldırılırsa test sonsuza kadar beklememeli. Bu not ürün korumasının çalışmadığı iddiası değildir.

## Okunan byte özetleri

{
  "/Users/muratates/code/dou-synapse-018-codex-production-line/apps/api/app/worker.py": "2cdbea27191cadd0bd2d73f88857b3e461122bdde0f4bdebc98f606771b7a634",
  "/Users/muratates/code/dou-synapse-018-codex-production-line/apps/api/tests/test_worker_lifecycle.py": "74e20080189f23b0e471f22364de181e403c1cf0f244ba5c24dbdfecbd72cb76",
  "/Users/muratates/code/dou-synapse-018-codex-production-line/docker-compose.yml": "0d9b5a0975b4b15ccba0207875b010caf2bc4577df0846f3013ae5571e7cf705",
  "/private/tmp/dou018_quota_period_run.py": "b3da297e66920c78cf7208a3b852a0f805aed2e31b5452b2590717672687b6d2",
  "/Users/muratates/code/dou-synapse-018-codex-production-line/apps/api/app/core/request_quota_maintenance.py": "6e3d66a4bcb5605ec36ed9ed28e78afc2c35f40ad96f94fd0558918cc6436479"
}
