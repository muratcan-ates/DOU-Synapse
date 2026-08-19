-- YALNIZCA YEREL GELİŞTİRME İÇİNDİR. Üretimde veya demo ortamında çalıştırmayın.
--
-- Migration, `dou_api_runtime`, `dou_app` ve `dou_worker` rollerini NOLOGIN olarak
-- oluşturur; bulutta runtime/worker giriş yetkisi ve parolası altyapı tarafında verilir.
-- `dou_app` yalnız ortak yetki taşıyıcısıdır ve LOGIN olarak açılmaz.
--
-- Amaç: testler superuser ile bağlanıp RLS'i sessizce atlamasın. Superuser bağlantısıyla
-- yazılan bir izolasyon testi her zaman yeşil yanar ve hiçbir şey kanıtlamaz.

ALTER ROLE dou_api_runtime LOGIN PASSWORD 'dou_api_runtime_local';
ALTER ROLE dou_worker      LOGIN PASSWORD 'dou_worker_local';

GRANT CONNECT ON DATABASE dou_synapse TO dou_api_runtime, dou_worker;
