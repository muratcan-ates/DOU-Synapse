-- DOU-Synapse — çekirdek şema
--
-- Tasarım notu (ARCHITECTURE.md §6):
-- Ders izolasyonu iki katmanlıdır. Birinci katman uygulama kodundaki zorunlu course_id
-- filtresi, ikinci katman buradaki RLS politikalarıdır. RLS'in gerçekten tetiklenmesi için
-- API, tablo sahibi olmayan `dou_app` rolüyle bağlanır ve her istek için işlem içinde
--     SET LOCAL app.current_user_id = '<uuid>'
-- yapar. Politikalar bu GUC'yi okur; ayarlanmamışsa hiçbir satır görünmez (fail-closed).
-- Tablolar FORCE ROW LEVEL SECURITY ile işaretlidir, böylece sahip rol bile politikalara tabidir.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Oturum bağlamı yardımcıları
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS app;

-- Geçerli isteğin kullanıcı kimliği. Ayarlanmamışsa NULL döner ve tüm politikalar kapanır.
CREATE OR REPLACE FUNCTION app.current_user_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.current_user_id', true), '')::uuid
$$;

-- unaccent() STABLE'dır; generated column IMMUTABLE ister. İki argümanlı biçim IMMUTABLE.
CREATE OR REPLACE FUNCTION app.immutable_unaccent(text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT public.unaccent('public.unaccent', $1)
$$;

-- ---------------------------------------------------------------------------
-- Kullanıcılar
-- ---------------------------------------------------------------------------

-- Supabase'de auth.users kimliğiyle birebir eşleşir (bkz. 0002_supabase_auth_bridge.sql).
-- Lokal geliştirmede doğrudan yazılır; bu yüzden auth şemasına FK verilmez.
CREATE TABLE profiles (
    id          uuid PRIMARY KEY,
    email       text NOT NULL UNIQUE,
    full_name   text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE profiles IS
    'Kullanıcı profili. Sistem geneli rol yoktur; yetki daima ders bazlıdır (course_memberships).';

-- ---------------------------------------------------------------------------
-- Dersler ve üyelik
-- ---------------------------------------------------------------------------

CREATE TABLE courses (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code        text NOT NULL,
    title       text NOT NULL,
    created_by  uuid NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT courses_code_not_blank CHECK (length(btrim(code)) > 0)
);

CREATE UNIQUE INDEX courses_code_key ON courses (lower(code));

CREATE TYPE membership_role AS ENUM ('instructor', 'student');
CREATE TYPE membership_status AS ENUM ('active', 'revoked');

CREATE TABLE course_memberships (
    course_id   uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id     uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    role        membership_role NOT NULL,
    status      membership_status NOT NULL DEFAULT 'active',
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (course_id, user_id)
);

CREATE INDEX course_memberships_user_idx ON course_memberships (user_id, status);

-- Üyelik yardımcıları. course_memberships'e baktıkları için tablodan sonra tanımlanır
-- (SQL fonksiyon gövdeleri CREATE anında doğrulanır).
--
-- SECURITY DEFINER kasıtlıdır: politikalar bu fonksiyonları çağırırken üyelik tablosunu
-- okumak zorundadır; aksi halde course_memberships üzerindeki RLS ile sonsuz özyineleme
-- oluşur. Fonksiyonlar yalnızca boolean döndürür, satır sızdırmaz.
CREATE OR REPLACE FUNCTION app.is_member(p_course_id uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, app AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.course_memberships m
        WHERE m.course_id = p_course_id
          AND m.user_id = app.current_user_id()
          AND m.status = 'active'
    )
$$;

CREATE OR REPLACE FUNCTION app.is_instructor(p_course_id uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, app AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.course_memberships m
        WHERE m.course_id = p_course_id
          AND m.user_id = app.current_user_id()
          AND m.status = 'active'
          AND m.role = 'instructor'
    )
$$;

-- Ders oluşturma: dersi ve oluşturanın eğitmen üyeliğini tek işlemde yazar.
--
-- SECURITY DEFINER'dır çünkü bu bootstrap adımında kullanıcının henüz üyeliği yoktur ve
-- hiçbir RLS politikası "üyeliği olmayan ama bu dersi yaratan kişi" durumunu okuma
-- yüzeyini genişletmeden ifade edemez. Fonksiyon yalnızca çağıranın kendi adına ders
-- açmasına izin verir; oturum bağlamı yoksa hata verir.
CREATE OR REPLACE FUNCTION app.create_course(p_code text, p_title text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, app AS $$
DECLARE
    v_user_id uuid := app.current_user_id();
    v_course_id uuid;
BEGIN
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'oturum bağlamı ayarlanmamış'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    INSERT INTO public.courses (code, title, created_by)
    VALUES (btrim(p_code), btrim(p_title), v_user_id)
    RETURNING id INTO v_course_id;

    INSERT INTO public.course_memberships (course_id, user_id, role, status)
    VALUES (v_course_id, v_user_id, 'instructor', 'active');

    RETURN v_course_id;
END
$$;

-- Derse üye ekleme.
--
-- SECURITY DEFINER'dır çünkü e-postadan kullanıcı bulmak, profiles üzerindeki RLS'i
-- aşmayı gerektirir. Yetki kontrolü fonksiyonun İLK adımıdır: çağıran dersin eğitmeni
-- değilse hiçbir arama yapılmaz. Böylece e-posta numaralandırma (enumeration) yalnızca
-- ilgili dersin eğitmenine açık olur ve dışarıya profil satırı sızmaz.
CREATE OR REPLACE FUNCTION app.add_course_member(
    p_course_id uuid,
    p_email     text,
    p_role      membership_role,
    OUT result  text,
    OUT user_id uuid
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, app AS $$
DECLARE
    v_status membership_status;
BEGIN
    IF NOT app.is_instructor(p_course_id) THEN
        RAISE EXCEPTION 'ders eğitmeni değil' USING ERRCODE = 'insufficient_privilege';
    END IF;

    SELECT p.id INTO user_id
    FROM public.profiles p
    WHERE lower(p.email) = lower(btrim(p_email));

    IF user_id IS NULL THEN
        result := 'no_user';
        RETURN;
    END IF;

    SELECT m.status INTO v_status
    FROM public.course_memberships m
    WHERE m.course_id = p_course_id AND m.user_id = add_course_member.user_id;

    IF v_status = 'active' THEN
        result := 'already_member';
        RETURN;
    ELSIF v_status IS NULL THEN
        INSERT INTO public.course_memberships (course_id, user_id, role, status)
        VALUES (p_course_id, add_course_member.user_id, p_role, 'active');
        result := 'added';
    ELSE
        UPDATE public.course_memberships
        SET status = 'active', role = p_role
        WHERE course_id = p_course_id AND user_id = add_course_member.user_id;
        result := 'reactivated';
    END IF;
END
$$;

-- Bir profilin, o kişinin öğrencisi olduğu dersin eğitmenine görünmesini sağlar.
-- Öğrenciler birbirlerinin profillerini göremez.
CREATE OR REPLACE FUNCTION app.is_instructor_of(p_user_id uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, app AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.course_memberships target
        JOIN public.course_memberships mine ON mine.course_id = target.course_id
        WHERE target.user_id = p_user_id
          AND target.status = 'active'
          AND mine.user_id = app.current_user_id()
          AND mine.status = 'active'
          AND mine.role = 'instructor'
    )
$$;

-- ---------------------------------------------------------------------------
-- Belgeler
-- ---------------------------------------------------------------------------

CREATE TYPE document_status AS ENUM (
    'uploaded', 'processing', 'completed', 'failed'
);

CREATE TABLE documents (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id     uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    uploaded_by   uuid NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    file_name     text NOT NULL,
    file_type     text NOT NULL,
    storage_path  text NOT NULL,
    file_hash     text NOT NULL,
    byte_size     bigint NOT NULL CHECK (byte_size > 0),
    status        document_status NOT NULL DEFAULT 'uploaded',
    page_count    integer,
    chunk_count   integer NOT NULL DEFAULT 0,
    error_message text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now()
);

-- Aynı dosyanın aynı derse ikinci kez yüklenip yeniden embed edilmesini engeller.
CREATE UNIQUE INDEX documents_course_hash_key ON documents (course_id, file_hash);
CREATE INDEX documents_course_idx ON documents (course_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- Chunk'lar
-- ---------------------------------------------------------------------------

CREATE TYPE chunk_content_type AS ENUM ('text', 'table', 'code');

CREATE TABLE chunks (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- course_id denormalize: retrieval filtresi JOIN'e bağlı kalmasın (ARCHITECTURE.md §3).
    course_id      uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    document_id    uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index    integer NOT NULL,
    page_number    integer,
    slide_number   integer,
    section_title  text,
    content_type   chunk_content_type NOT NULL DEFAULT 'text',
    language       text,
    text           text NOT NULL,
    token_count    integer NOT NULL,
    embedding      vector(1024),
    -- Sparse arama: 'simple' + unaccent. Köklendirme yok; fork(), TLB gibi teknik
    -- tokenlar bozulmadan kalır (ARCHITECTURE.md §1, Sparse arama satırı).
    fts            tsvector GENERATED ALWAYS AS (
                       to_tsvector('simple', app.immutable_unaccent(text))
                   ) STORED,
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX chunks_course_idx ON chunks (course_id);
CREATE INDEX chunks_fts_idx ON chunks USING gin (fts);

-- HNSW: pgvector'ün önerdiği varsayılanlar. Kosinüs mesafesi retrieval katmanıyla eşleşir.
CREATE INDEX chunks_embedding_idx ON chunks
    USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- ---------------------------------------------------------------------------
-- Ingestion kuyruğu
-- ---------------------------------------------------------------------------

CREATE TYPE job_status AS ENUM ('pending', 'processing', 'completed', 'failed');

CREATE TABLE ingestion_jobs (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    status        job_status NOT NULL DEFAULT 'pending',
    attempt_count integer NOT NULL DEFAULT 0,
    last_error    text,
    started_at    timestamptz,
    completed_at  timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- Worker `FOR UPDATE SKIP LOCKED` ile bu indeks üzerinden sıradaki işi çeker.
CREATE INDEX ingestion_jobs_pending_idx ON ingestion_jobs (created_at)
    WHERE status = 'pending';

-- ---------------------------------------------------------------------------
-- Uygulama rolü ve yetkiler
-- ---------------------------------------------------------------------------

-- dou_app: API'nin bağlandığı rol. Tabloların sahibi DEĞİLDİR ve BYPASSRLS yoktur,
-- dolayısıyla aşağıdaki politikalara tabidir.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dou_app') THEN
        CREATE ROLE dou_app NOLOGIN;
    END IF;
END
$$;

-- dou_worker: ingestion worker'ı. chunks tablosuna yazabilmesi gerekir ve chunks'ta
-- bilinçli olarak hiçbir INSERT politikası yoktur; bu yüzden RLS'i atlar. Worker asla
-- kullanıcı isteği bağlamında çalışmaz — yalnızca kuyruktaki işleri işler.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dou_worker') THEN
        CREATE ROLE dou_worker NOLOGIN BYPASSRLS;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA public, app TO dou_app, dou_worker;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO dou_app, dou_worker;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO dou_app, dou_worker;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO dou_app, dou_worker;

-- ---------------------------------------------------------------------------
-- RLS politikaları
-- ---------------------------------------------------------------------------

ALTER TABLE profiles            ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses             ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_memberships  ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents           ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks              ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_jobs      ENABLE ROW LEVEL SECURITY;

ALTER TABLE profiles            FORCE ROW LEVEL SECURITY;
ALTER TABLE courses             FORCE ROW LEVEL SECURITY;
ALTER TABLE course_memberships  FORCE ROW LEVEL SECURITY;
ALTER TABLE documents           FORCE ROW LEVEL SECURITY;
ALTER TABLE chunks              FORCE ROW LEVEL SECURITY;
ALTER TABLE ingestion_jobs      FORCE ROW LEVEL SECURITY;

-- profiles: kullanıcı kendini görür; eğitmen kendi dersindeki öğrencilerin profilini görür.
CREATE POLICY profiles_self_read ON profiles
    FOR SELECT USING (
        id = app.current_user_id() OR app.is_instructor_of(id)
    );
CREATE POLICY profiles_self_update ON profiles
    FOR UPDATE USING (id = app.current_user_id());

-- courses: yalnızca üye olunan dersler görülür.
--
-- INSERT politikası bilinçli olarak YOKTUR: ders oluşturma bir "bootstrap" işlemidir
-- (nesneyi yaratıp aynı anda sahibi olursunuz) ve politikalarla ifade edilmeye
-- çalışıldığında ya RETURNING'i kıran ya da okuma yüzeyini genişleten bir tasarım çıkar.
-- Bunun yerine işlem, aşağıdaki app.create_course() fonksiyonunda atomik olarak yapılır;
-- uygulama rolünün courses tablosuna doğrudan yazma yetkisi hiç olmaz.
CREATE POLICY courses_member_read ON courses
    FOR SELECT USING (app.is_member(id));
CREATE POLICY courses_instructor_update ON courses
    FOR UPDATE USING (app.is_instructor(id));

-- course_memberships: kullanıcı kendi üyeliklerini, eğitmen dersin tüm üyeliklerini görür.
CREATE POLICY memberships_read ON course_memberships
    FOR SELECT USING (
        user_id = app.current_user_id() OR app.is_instructor(course_id)
    );
-- Üyelik ekleme yalnızca dersin eğitmenine açıktır. İlk eğitmen üyeliği create_course()
-- içinde oluşturulduğu için burada bootstrap istisnasına gerek yoktur.
CREATE POLICY memberships_insert ON course_memberships
    FOR INSERT WITH CHECK (app.is_instructor(course_id));
CREATE POLICY memberships_instructor_update ON course_memberships
    FOR UPDATE USING (app.is_instructor(course_id));
CREATE POLICY memberships_instructor_delete ON course_memberships
    FOR DELETE USING (app.is_instructor(course_id));

-- documents: dersin üyeleri okur, yalnızca eğitmen yazar.
CREATE POLICY documents_member_read ON documents
    FOR SELECT USING (app.is_member(course_id));
CREATE POLICY documents_instructor_insert ON documents
    FOR INSERT WITH CHECK (app.is_instructor(course_id));
CREATE POLICY documents_instructor_update ON documents
    FOR UPDATE USING (app.is_instructor(course_id));
CREATE POLICY documents_instructor_delete ON documents
    FOR DELETE USING (app.is_instructor(course_id));

-- chunks: dersin üyeleri okur. Yazma yalnızca worker'ındır (sahip rol, RLS dışı bağlantı).
CREATE POLICY chunks_member_read ON chunks
    FOR SELECT USING (app.is_member(course_id));

-- ingestion_jobs: yalnızca dersin eğitmeni durumu görebilir.
CREATE POLICY jobs_instructor_read ON ingestion_jobs
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM documents d
            WHERE d.id = ingestion_jobs.document_id
              AND app.is_instructor(d.course_id)
        )
    );
CREATE POLICY jobs_instructor_insert ON ingestion_jobs
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM documents d
            WHERE d.id = ingestion_jobs.document_id
              AND app.is_instructor(d.course_id)
        )
    );

COMMIT;
