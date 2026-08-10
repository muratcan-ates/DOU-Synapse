-- Ingestion yeniden deneme zamanlaması (002 / FR-213, FR-214).
--
-- `attempt_count` ilk şemadan beri vardı ama başarısız işler hemen yeniden
-- kuyruğa giriyordu. Yoğun bir dış arıza sırasında bu, aynı bozuk işi sıkı bir
-- döngüde tekrar çalıştırır. `next_attempt_at` worker'ların tamamının gördüğü
-- ortak saattir; süreç içi uyku tek başına çoklu worker'da sınır değildir.

ALTER TABLE ingestion_jobs
    ADD COLUMN next_attempt_at timestamptz NOT NULL DEFAULT now();

DROP INDEX ingestion_jobs_pending_idx;
CREATE INDEX ingestion_jobs_pending_idx
    ON ingestion_jobs (next_attempt_at, created_at, id)
    WHERE status = 'pending';

COMMENT ON COLUMN ingestion_jobs.next_attempt_at IS
    'İşin worker tarafından yeniden alınabileceği en erken veritabanı zamanı.';

-- Genel bir UPDATE politikası, eğitmene `status = completed` veya keyfî bir
-- `attempt_count` yazma yetkisi de verirdi. Yeniden deneme bu yüzden tablo yazma
-- izni değil, yalnızca `failed -> pending` geçişini yapabilen dar bir yetenektir.
-- Fonksiyon çağıranın ders eğitmenliğini kendisi doğrular; eşleşmeyen belge/iş için
-- satır kimliği sızdırmadan NULL döner.
CREATE OR REPLACE FUNCTION app.retry_ingestion_job(p_document_id uuid) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, app AS $$
DECLARE
    v_job_id uuid;
BEGIN
    UPDATE public.ingestion_jobs AS j
    SET status = 'pending',
        attempt_count = 0,
        last_error = NULL,
        started_at = NULL,
        completed_at = NULL,
        next_attempt_at = now()
    FROM public.documents AS d
    WHERE j.document_id = p_document_id
      AND d.id = j.document_id
      AND j.status = 'failed'
      AND app.is_instructor(d.course_id)
    RETURNING j.id INTO v_job_id;

    RETURN v_job_id;
END
$$;

-- PostgreSQL fonksiyonlara varsayılan olarak PUBLIC EXECUTE verir. Bu fonksiyon
-- RLS'i aşan bir yazma yüzeyi olduğundan yalnız API rolü çağırabilir.
REVOKE EXECUTE ON FUNCTION app.retry_ingestion_job(uuid) FROM PUBLIC, dou_worker;
GRANT EXECUTE ON FUNCTION app.retry_ingestion_job(uuid) TO dou_app;

-- 0001'in geniş tablo GRANT'ini daralt: worker kuyruğu ilerletebilir, dou_app ise
-- yalnız yukarıdaki kontrollü fonksiyonu kullanır.
REVOKE UPDATE ON ingestion_jobs FROM dou_app;
