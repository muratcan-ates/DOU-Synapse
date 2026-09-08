-- Allocated by parent after0025/D1; review candidate, not applied here.
-- Stop all old workers AND API-local drains before migration. Never mix old
-- un-fenced write code with live lease claims. Existing stuck processing rows
-- need individual operator reconciliation after all old workers are stopped.
BEGIN;
LOCK TABLE public.documents IN SHARE ROW EXCLUSIVE MODE;
LOCK TABLE public.ingestion_jobs IN SHARE ROW EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.ingestion_jobs WHERE status = 'processing') THEN
        RAISE EXCEPTION 'ingestion migration requires no processing jobs';
    END IF;
    IF EXISTS (
        SELECT document_id FROM public.ingestion_jobs
        WHERE status IN ('pending', 'processing')
        GROUP BY document_id HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'ingestion migration requires unique active jobs';
    END IF;
END
$$;

ALTER TABLE public.documents
    ADD COLUMN ingestion_revision bigint NOT NULL DEFAULT 1
    CHECK (ingestion_revision > 0);

-- supersedes_document_id is lineage only: predecessor ON DELETE SET NULL
-- does not change this document source. superseded_at still fences old sources.
CREATE FUNCTION app.track_ingestion_revision() RETURNS trigger
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.ingestion_revision := 1;
    ELSIF ROW(NEW.course_id, NEW.uploaded_by, NEW.file_name, NEW.file_type,
              NEW.storage_path, NEW.file_hash, NEW.byte_size,
              NEW.superseded_at)
          IS DISTINCT FROM
          ROW(OLD.course_id, OLD.uploaded_by, OLD.file_name, OLD.file_type,
              OLD.storage_path, OLD.file_hash, OLD.byte_size,
              OLD.superseded_at) THEN
        NEW.ingestion_revision := OLD.ingestion_revision + 1;
    ELSE
        NEW.ingestion_revision := OLD.ingestion_revision;
    END IF;
    RETURN NEW;
END
$$;
REVOKE ALL ON FUNCTION app.track_ingestion_revision() FROM PUBLIC, dou_app, dou_worker;
CREATE TRIGGER track_ingestion_revision
    BEFORE INSERT OR UPDATE ON public.documents
    FOR EACH ROW EXECUTE FUNCTION app.track_ingestion_revision();

ALTER TABLE public.ingestion_jobs
    ADD COLUMN claim_token uuid,
    ADD COLUMN claim_document_revision bigint,
    ADD COLUMN lease_expires_at timestamptz,
    ADD CONSTRAINT ingestion_claim_shape CHECK (
        (status = 'processing' AND claim_token IS NOT NULL
         AND claim_document_revision > 0 AND claim_document_revision IS NOT NULL
         AND lease_expires_at IS NOT NULL AND attempt_count BETWEEN 1 AND 3)
        OR
        (status <> 'processing' AND claim_token IS NULL
         AND claim_document_revision IS NULL AND lease_expires_at IS NULL)
    );
CREATE UNIQUE INDEX ingestion_jobs_one_active_document
    ON public.ingestion_jobs (document_id)
    WHERE status IN ('pending', 'processing');
CREATE INDEX ingestion_jobs_expired_lease
    ON public.ingestion_jobs (lease_expires_at, created_at, id)
    WHERE status = 'processing';

-- API can enqueue an instructor's fresh job; it cannot forge a processing claim.
-- dou_worker retains existing bypass/table writes. No new public read surface.
DROP POLICY jobs_instructor_insert ON public.ingestion_jobs;
CREATE POLICY jobs_instructor_insert ON public.ingestion_jobs
    FOR INSERT WITH CHECK (
        status = 'pending' AND attempt_count = 0 AND claim_token IS NULL
        AND claim_document_revision IS NULL AND lease_expires_at IS NULL
        AND EXISTS (
            SELECT 1 FROM public.documents d
            WHERE d.id = ingestion_jobs.document_id
              AND d.superseded_at IS NULL AND app.is_instructor(d.course_id)
        )
    );

-- Preserve instructor-only failed→pending reset, with document→job lock order.
-- No automatic fourth attempt. Superseded sources must not be manually revived.
CREATE OR REPLACE FUNCTION app.retry_ingestion_job(p_document_id uuid) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    v_job_id uuid;
    v_course_id uuid;
BEGIN
    SELECT d.course_id INTO v_course_id FROM public.documents d
    WHERE d.id = p_document_id AND d.status = 'failed' AND d.superseded_at IS NULL
      AND app.is_instructor(d.course_id)
    FOR UPDATE;
    IF v_course_id IS NULL OR NOT app.is_instructor(v_course_id) THEN
        RETURN NULL;
    END IF;
    -- Existing historical failed rows are not deleted. Only one job is reset.
    SELECT j.id INTO v_job_id FROM public.ingestion_jobs j
    WHERE j.document_id = p_document_id AND j.status = 'failed'
      AND NOT EXISTS (
          SELECT 1 FROM public.ingestion_jobs a
          WHERE a.document_id = p_document_id AND a.status IN ('pending', 'processing')
      )
    ORDER BY j.created_at DESC, j.id DESC LIMIT 1 FOR UPDATE;
    IF v_job_id IS NULL THEN
        RETURN NULL;
    END IF;
    UPDATE public.ingestion_jobs SET status = 'pending', attempt_count = 0,
        last_error = NULL, started_at = NULL, completed_at = NULL,
        next_attempt_at = pg_catalog.clock_timestamp(),
        claim_token = NULL, claim_document_revision = NULL, lease_expires_at = NULL
    WHERE id = v_job_id;
    RETURN v_job_id;
END
$$;
REVOKE EXECUTE ON FUNCTION app.retry_ingestion_job(uuid) FROM PUBLIC, dou_worker;
GRANT EXECUTE ON FUNCTION app.retry_ingestion_job(uuid) TO dou_app;
REVOKE UPDATE ON public.ingestion_jobs FROM dou_app;

COMMENT ON COLUMN public.documents.ingestion_revision IS
    'Server-controlled source revision; source changes fence stale ingestion writes.';
COMMENT ON COLUMN public.ingestion_jobs.claim_token IS
    'Current worker claim fence; clear on release/completion. Never log or expose through APIs.';
COMMENT ON COLUMN public.ingestion_jobs.lease_expires_at IS
    'DB-clock renewal deadline; expiry permits reclaim on the next worker wake-up.';
COMMIT;
