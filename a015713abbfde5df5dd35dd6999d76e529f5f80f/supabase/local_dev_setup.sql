-- YALNIZCA YEREL GELİŞTİRME İÇİNDİR. Üretimde veya demo ortamında çalıştırmayın.
--
-- Migration, `dou_app` ve `dou_worker` rollerini NOLOGIN olarak oluşturur; bulutta bu
-- rollere giriş yetkisi ve parolası altyapı tarafında verilir. Yerelde geliştirme ve
-- testlerin üretimdeki bağlantı yolunu birebir kullanabilmesi için burada giriş açılır.
--
-- Amaç: testler superuser ile bağlanıp RLS'i sessizce atlamasın. Superuser bağlantısıyla
-- yazılan bir izolasyon testi her zaman yeşil yanar ve hiçbir şey kanıtlamaz.

ALTER ROLE dou_app    LOGIN PASSWORD 'dou_app_local';
ALTER ROLE dou_worker LOGIN PASSWORD 'dou_worker_local';

GRANT CONNECT ON DATABASE dou_synapse TO dou_app, dou_worker;
