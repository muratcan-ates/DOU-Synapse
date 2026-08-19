-- DOU-Synapse — assessment integrity forward-fix (009)
--
-- Üç güvenlik sınırını veritabanında da zorlar:
--   1. practice havuzu ile resmî assessment kâğıdı aynı soru kümesi değildir;
--   2. öğrenci assessment sorusunu yalnız kendi dondurulmuş kâğıdında görür;
--   3. yayınlanmış/superseded kâğıdın sorusu ve amacı geriye dönük değişmez.
--
-- Migration forward-only'dir. Rol/ACL contract kesimi için rollout sırası ayrıca
-- zorunludur: runtime credential hazırla, eski pool'u drain et, migrationı uygula,
-- yeni runtime DSN ile readiness duman testini geç. Rollback eski uygulama
-- revizyonunu yine runtime DSN ile çalıştırır; kolon ve tarihsel kanıt sökülmez.

BEGIN;

-- `dou_app` ortak yetki taşıyıcısıdır; gerçek HTTP API bağlantısı ayrı bir LOGIN
-- kimliği kullanır. Böylece öğrenci bağlamını taklit eden ham `dou_app` oturumu,
-- cevap anahtarı / yayınlanmamış puan gibi hassas assessment kolonlarına yalnız
-- RLS ifadesini çağırarak ulaşamaz. Parola ve LOGIN migration dışında, altyapı
-- veya local_dev_setup tarafından verilir.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dou_api_runtime') THEN
        CREATE ROLE dou_api_runtime
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS INHERIT;
    ELSIF EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'dou_api_runtime'
          AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)
    ) THEN
        RAISE EXCEPTION 'dou_api_runtime has unsafe cluster privileges';
    END IF;
END
$$;

-- Contract cut yalnız altyapı `dou_app` LOGIN/parolasını AYRI ve önceden commit
-- edilmiş bir adımda kapattıktan, eski API pool'unu drain ettikten sonra güvenlidir.
-- NOLOGIN'i bu transaction içinde vermek yeterli değildir: preflight ile COMMIT
-- arasındaki dar aralıkta eski parola yeni ve kalıcı bir oturum açabilirdi.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = 'dou_app'
          AND rolcanlogin
    ) THEN
        RAISE EXCEPTION
            'dou_app must already be NOLOGIN before 0016; revoke LOGIN and drain pools first';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_stat_activity
        WHERE usename = 'dou_app'
          AND pid <> pg_backend_pid()
    ) THEN
        RAISE EXCEPTION
            'active dou_app sessions exist; drain old API pools before 0016';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_auth_members membership
        JOIN pg_roles parent ON parent.oid = membership.roleid
        JOIN pg_roles member ON member.oid = membership.member
        WHERE parent.rolname = 'dou_app'
          AND member.rolname <> 'dou_api_runtime'
    ) THEN
        RAISE EXCEPTION
            'dou_app has an unexpected member; remove it before 0016';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_auth_members membership
        JOIN pg_roles member ON member.oid = membership.member
        WHERE member.rolname = 'dou_app'
    ) THEN
        RAISE EXCEPTION
            'dou_app inherits an unexpected parent role';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_auth_members membership
        JOIN pg_roles parent ON parent.oid = membership.roleid
        WHERE parent.rolname = 'dou_api_runtime'
    ) THEN
        RAISE EXCEPTION
            'dou_api_runtime has a member that would inherit sensitive grants';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_auth_members membership
        JOIN pg_roles parent ON parent.oid = membership.roleid
        JOIN pg_roles member ON member.oid = membership.member
        WHERE member.rolname = 'dou_api_runtime'
          AND parent.rolname <> 'dou_app'
    ) THEN
        RAISE EXCEPTION
            'dou_api_runtime inherits an unexpected parent role';
    END IF;
END
$$;

GRANT dou_app TO dou_api_runtime WITH INHERIT TRUE;
GRANT dou_app TO dou_api_runtime WITH SET FALSE;
GRANT dou_app TO dou_api_runtime WITH ADMIN FALSE;

ALTER ROLE dou_app
    NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    PASSWORD NULL;

-- 0001'in gelecek her tabloya blanket CRUD veren owner default'u, yeni runtime
-- üyeliğiyle daha da tehlikeli olurdu. Bundan sonraki migration'lar gereken ACL'i
-- açıkça runtime/worker'a vermek zorundadır.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM dou_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM dou_worker;
-- Fonksiyonların PostgreSQL varsayılan PUBLIC EXECUTE yetkisi GLOBALDIR. `IN
-- SCHEMA app` ile yapılan REVOKE hard-wired varsayılanı kaldıramaz; bu yüzden
-- migration owner için şemasız/global form kullanılır. Aşağıdaki owner döngüsü
-- geçmişte app fonksiyonu yaratmış diğer migration owner'larını da kapsar.
ALTER DEFAULT PRIVILEGES
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- 0001 ve 0016 farklı migration owner'larıyla çalıştırılmış olabilir. ALTER
-- DEFAULT PRIVILEGES aksi halde yalnız current_user kaydını düzeltir ve önceki
-- owner'ın blanket grant'i sessizce yaşamaya devam eder. Migration yöneticisi
-- cluster'daki ilgili bütün owner kayıtlarını normalleştirir, sonra kalıntıyı
-- ayrıca fail-closed doğrular.
DO $$
DECLARE
    v_owner name;
BEGIN
    FOR v_owner IN
        SELECT DISTINCT owner_role.rolname
        FROM pg_default_acl defaults
        JOIN pg_roles owner_role ON owner_role.oid = defaults.defaclrole
        CROSS JOIN LATERAL aclexplode(defaults.defaclacl) privilege
        JOIN pg_roles grantee ON grantee.oid = privilege.grantee
        WHERE defaults.defaclnamespace = 'public'::regnamespace
          AND defaults.defaclobjtype = 'r'
          AND grantee.rolname IN ('dou_app', 'dou_worker')
          AND privilege.privilege_type IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE')
    LOOP
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
            'REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM dou_app, dou_worker',
            v_owner
        );
    END LOOP;

    FOR v_owner IN
        SELECT DISTINCT owner_role.rolname
        FROM pg_roles owner_role
        WHERE owner_role.oid = (SELECT nspowner FROM pg_namespace WHERE nspname = 'app')
           OR owner_role.oid IN (
                SELECT proc.proowner
                FROM pg_proc proc
                WHERE proc.pronamespace = 'app'::regnamespace
           )
           OR owner_role.rolname = current_user
    LOOP
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE %I '
            'REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC',
            v_owner
        );
        -- Önceden açıkça eklenmiş per-schema PUBLIC grant varsa onu da kaldır.
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA app '
            'REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC',
            v_owner
        );
    END LOOP;

    IF EXISTS (
        SELECT 1
        FROM pg_default_acl defaults
        CROSS JOIN LATERAL aclexplode(defaults.defaclacl) privilege
        JOIN pg_roles grantee ON grantee.oid = privilege.grantee
        WHERE defaults.defaclnamespace = 'public'::regnamespace
          AND defaults.defaclobjtype = 'r'
          AND grantee.rolname IN ('dou_app', 'dou_worker')
          AND privilege.privilege_type IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE')
    ) OR EXISTS (
        WITH relevant_owner AS (
            SELECT DISTINCT owner_role.oid
            FROM pg_roles owner_role
            WHERE owner_role.oid = (SELECT nspowner FROM pg_namespace WHERE nspname = 'app')
               OR owner_role.oid IN (
                    SELECT proc.proowner
                    FROM pg_proc proc
                    WHERE proc.pronamespace = 'app'::regnamespace
               )
               OR owner_role.rolname = current_user
        ), effective_global_default AS (
            SELECT
                owner.oid,
                COALESCE(defaults.defaclacl, acldefault('f', owner.oid)) AS acl
            FROM relevant_owner owner
            LEFT JOIN pg_default_acl defaults
              ON defaults.defaclrole = owner.oid
             AND defaults.defaclnamespace = 0
             AND defaults.defaclobjtype = 'f'
        )
        SELECT 1
        FROM effective_global_default defaults
        CROSS JOIN LATERAL aclexplode(defaults.acl) privilege
        WHERE privilege.grantee = 0
          AND privilege.privilege_type = 'EXECUTE'
    ) OR EXISTS (
        SELECT 1
        FROM pg_default_acl defaults
        CROSS JOIN LATERAL aclexplode(defaults.defaclacl) privilege
        WHERE defaults.defaclnamespace = 'app'::regnamespace
          AND defaults.defaclobjtype = 'f'
          AND privilege.grantee = 0
          AND privilege.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'unsafe default privileges remain after normalization';
    END IF;
END
$$;

-- session_user yalnız bağlantıyı gerçekten açan kimliktir; current_user, SET ROLE
-- ve kullanıcı kontrollü GUC değerleri bu güven işaretini taklit edemez.
CREATE OR REPLACE FUNCTION app.is_api_runtime() RETURNS boolean
LANGUAGE sql STABLE
SET search_path = pg_catalog
AS $$
    SELECT session_user = 'dou_api_runtime'
$$;

REVOKE ALL ON FUNCTION app.is_api_runtime() FROM PUBLIC, dou_worker;
GRANT EXECUTE ON FUNCTION app.is_api_runtime() TO dou_app, dou_api_runtime;

CREATE TYPE question_purpose AS ENUM ('practice', 'assessment');

ALTER TABLE questions
    ADD COLUMN purpose question_purpose NOT NULL DEFAULT 'practice';

-- Bilinmeyen diğer eski sorular practice kalır. Ancak herhangi bir blueprint
-- kâğıdına girmiş soru practice havuzunda görünür bırakılamaz; draft kâğıt dahi
-- öğretmenin assessment niyetinin somut kanıtıdır. Aynı soru tarihsel bir legacy
-- question_ids oturumundaysa yalnız o oturumun sahibine aşağıdaki dar helper dalı
-- erişim verir; yeni practice seçimi purpose filtresi nedeniyle onu tekrar seçemez.
UPDATE questions AS q
SET purpose = 'assessment'
WHERE EXISTS (
    SELECT 1
    FROM exam_items AS i
    WHERE i.question_id = q.id
);

-- Tarihsel yayın kanıtı zaten bozuksa migration bunu sessizce "iyileştirmez".
-- Operatör hangi sorunun neden terminal durumdan çıktığını incelemelidir.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM exam_items i
        JOIN exam_versions v ON v.id = i.exam_version_id
        JOIN questions q ON q.id = i.question_id
        WHERE v.status IN ('published', 'superseded')
          AND (
              q.status <> 'approved'
              OR q.purpose <> 'assessment'
              OR q.learning_outcome_id IS NULL
              OR q.difficulty IS NULL
          )
    ) THEN
        RAISE EXCEPTION
            'published/superseded exam contains an unclassified or non-approved assessment question; remediate before migration'
            USING ERRCODE = '23514';
    END IF;
END
$$;

DROP INDEX questions_cell_idx;
CREATE INDEX questions_cell_idx
    ON questions (course_id, learning_outcome_id, difficulty, type)
    WHERE status = 'approved' AND purpose = 'assessment';

CREATE INDEX questions_practice_pool_idx
    ON questions (course_id, topic_id, id)
    WHERE status = 'approved' AND purpose = 'practice';

-- Blueprint sonucunun açılacağı an oturum başlangıcında dondurulur. NULL, legacy
-- veya practice oturumunda "finish ile hemen"; eski bir blueprint satırında ise
-- "güvenli yayın planı bilinmiyor, otomatik açma" anlamına gelir. Yeni blueprint
-- satırları aşağıdaki NOT VALID kısıtla mutlaka bir zaman taşır. NOT VALID yalnız
-- migration öncesi tarihsel satırları grandfather eder; yeni INSERT'leri zorlar.
ALTER TABLE exam_sessions
    ADD COLUMN feedback_available_at timestamptz;

-- Migration öncesi blueprint oturumlarını da güncellenebilir bırak. PostgreSQL'de
-- NOT VALID bir CHECK mevcut bozuk satırı taramaz ama o satırın finished_at gibi
-- ilgisiz bir kolonu UPDATE edildiğinde yeni satır sürümünü yine reddeder. Bu yüzden
-- tarihsel NULL'ı grandfather etmek aktif oturumu bitirilemez yapardı. Kapanışı
-- bilinen kâğıtta aynı güvenli formülü, kapanışı bilinmeyende ise deploy anından bir
-- tam sınav süresi sonrasını kullanıyoruz. Aynı blueprint'teki en geç expires_at da
-- cohort sınırıdır: 0008 döneminde süre kısaltılmış olsa bile erken biten öğrenci,
-- daha geç süresi dolacak akranına cevap/puan sızdıramaz.
UPDATE exam_sessions AS s
SET feedback_available_at = GREATEST(
    b.closes_at + make_interval(mins => b.duration_minutes),
    s.expires_at,
    cohort.max_expires_at,
    -- 0008 döneminde takvim ilk oturumdan sonra değişebiliyordu. Göç anındaki
    -- mutable kapanışa tek başına güvenmek, geçmişe çekilmiş bir değerle sonucu
    -- deploy anında açabilirdi. Bir tam sınav süresi beklemek güvenli sınırdır.
    statement_timestamp() + make_interval(mins => b.duration_minutes)
)
FROM exam_blueprints AS b
LEFT JOIN LATERAL (
    SELECT max(peer.expires_at) AS max_expires_at
    FROM exam_sessions AS peer
    WHERE peer.exam_blueprint_id = b.id
      AND peer.exam_version_id IS NOT NULL
) AS cohort ON true
WHERE s.exam_blueprint_id = b.id
  AND s.exam_version_id IS NOT NULL
  AND s.feedback_available_at IS NULL;

ALTER TABLE exam_sessions
    ADD CONSTRAINT exam_sessions_blueprint_feedback_schedule
        CHECK (exam_version_id IS NULL OR feedback_available_at IS NOT NULL);

CREATE INDEX exam_sessions_feedback_available_idx
    ON exam_sessions (feedback_available_at)
    WHERE exam_version_id IS NOT NULL AND finished_at IS NOT NULL;

-- ---------------------------------------------------------------------------
-- RLS recursion-safe boolean helpers
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION app.has_own_exam_question(
    p_question_id uuid,
    p_course_id uuid
) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
    SELECT app.current_user_id() IS NOT NULL
       AND app.is_member(p_course_id)
       AND (
          EXISTS (
            SELECT 1
            FROM public.exam_items i
            JOIN public.exam_versions v
              ON v.id = i.exam_version_id
             AND v.course_id = i.course_id
            JOIN public.exam_sessions s
              ON s.exam_version_id = v.id
             AND s.course_id = v.course_id
             AND s.exam_blueprint_id = v.blueprint_id
            WHERE i.question_id = p_question_id
              AND i.course_id = p_course_id
              AND s.user_id = app.current_user_id()
              AND v.status IN ('published', 'superseded')
          )
          OR EXISTS (
            -- Mixed-use upgrade istisnası: 0016 öncesinde question_ids içine
            -- dondurulmuş aynı soru sonradan blueprint item'ı olmuş olabilir.
            -- Yalnız mevcut legacy oturum sahibi devam eder; yeni practice havuzu
            -- assessment purpose satırını seçemez.
            SELECT 1
            FROM public.exam_sessions legacy_session
            WHERE legacy_session.exam_version_id IS NULL
              AND legacy_session.course_id = p_course_id
              AND legacy_session.user_id = app.current_user_id()
              AND legacy_session.question_ids IS NOT NULL
              AND p_question_id = ANY(legacy_session.question_ids)
          )
       )
$$;

CREATE OR REPLACE FUNCTION app.has_own_blueprint_session(
    p_blueprint_id uuid,
    p_course_id uuid
) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
    SELECT app.current_user_id() IS NOT NULL
       AND app.is_member(p_course_id)
       AND EXISTS (
            SELECT 1
            FROM public.exam_sessions s
            JOIN public.exam_versions v
              ON v.id = s.exam_version_id
             AND v.course_id = s.course_id
            WHERE v.blueprint_id = p_blueprint_id
              AND s.exam_blueprint_id = p_blueprint_id
              AND v.course_id = p_course_id
              AND s.user_id = app.current_user_id()
              AND v.status IN ('published', 'superseded')
       )
$$;

REVOKE ALL ON FUNCTION app.has_own_exam_question(uuid, uuid)
    FROM PUBLIC, dou_worker;
REVOKE ALL ON FUNCTION app.has_own_blueprint_session(uuid, uuid)
    FROM PUBLIC, dou_worker;
GRANT EXECUTE ON FUNCTION app.has_own_exam_question(uuid, uuid) TO dou_app;
GRANT EXECUTE ON FUNCTION app.has_own_blueprint_session(uuid, uuid) TO dou_app;

DROP POLICY questions_read ON questions;
CREATE POLICY questions_read ON questions
    FOR SELECT USING (
        app.is_instructor(course_id)
        OR (
            app.is_member(course_id)
            AND status = 'approved'
            AND (
                purpose = 'practice'
                OR (
                    purpose = 'assessment'
                    AND app.has_own_exam_question(id, course_id)
                )
            )
        )
    );

CREATE POLICY questions_api_runtime ON questions
    AS RESTRICTIVE FOR SELECT TO dou_app
    USING (app.is_api_runtime());

-- Ham answers satırı resmî sonuç açılmadan score/is_correct/feedback taşır ve
-- INSERT gövdesi puan kolonlarını da içerir. Bu iki yol yalnız gerçek API LOGIN'i
-- üzerinden kullanılabilir; doğrudan dou_app oturumu tablo yetkisinde de kesilir.
DROP POLICY answers_self_read ON answers;
CREATE POLICY answers_self_read ON answers
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM exam_sessions s
            WHERE s.id = answers.session_id
              AND s.user_id = app.current_user_id()
        )
        OR app.is_instructor(course_id)
    );

CREATE POLICY answers_api_runtime_read ON answers
    AS RESTRICTIVE FOR SELECT TO dou_app
    USING (app.is_api_runtime());

DROP POLICY answers_self_insert ON answers;
CREATE POLICY answers_self_insert ON answers
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM exam_sessions s
            WHERE s.id = answers.session_id
              AND s.user_id = app.current_user_id()
              AND s.course_id = answers.course_id
        )
    );

CREATE POLICY answers_api_runtime_insert ON answers
    AS RESTRICTIVE FOR INSERT TO dou_app
    WITH CHECK (app.is_api_runtime());

-- Oturum satırı mode/attempt/takvim ve bitiş durumunu taşır; ham carrier rolünün
-- blueprint'i practice gibi açıp API üzerinden erken feedback almasına veya bitmiş
-- oturumu yeniden açmasına izin verilmez.
CREATE POLICY exam_sessions_api_runtime_read ON exam_sessions
    AS RESTRICTIVE FOR SELECT TO dou_app
    USING (app.is_api_runtime());

CREATE POLICY exam_sessions_api_runtime_insert ON exam_sessions
    AS RESTRICTIVE FOR INSERT TO dou_app
    WITH CHECK (app.is_api_runtime());

CREATE POLICY exam_sessions_api_runtime_update ON exam_sessions
    AS RESTRICTIVE FOR UPDATE TO dou_app
    USING (app.is_api_runtime())
    WITH CHECK (app.is_api_runtime());

CREATE POLICY exam_versions_api_runtime_read ON exam_versions
    AS RESTRICTIVE FOR SELECT TO dou_app
    USING (app.is_api_runtime());

CREATE POLICY exam_items_api_runtime_read ON exam_items
    AS RESTRICTIVE FOR SELECT TO dou_app
    USING (app.is_api_runtime());

-- Pencere kapanınca kendi oturumunun blueprint satırını kaybetmek, süre helper'ını
-- global varsayılana düşürüp exam lock'ını erken açabiliyordu. Own-session dalı
-- yalnız varlığı doğrular; hücre/başka öğrencinin oturumu açılmaz.
DROP POLICY exam_blueprints_read ON exam_blueprints;
CREATE POLICY exam_blueprints_read ON exam_blueprints
    FOR SELECT USING (
        app.is_instructor(course_id)
        OR (
            app.is_member(course_id)
            AND (
                app.blueprint_open_to_students(id)
                OR app.has_own_blueprint_session(id, course_id)
            )
        )
    );

DROP POLICY questions_instructor_update ON questions;
CREATE POLICY questions_instructor_update ON questions
    FOR UPDATE USING (app.is_instructor(course_id) AND status = 'draft')
    WITH CHECK (app.is_instructor(course_id));

DROP POLICY exam_versions_instructor_insert ON exam_versions;
CREATE POLICY exam_versions_instructor_insert ON exam_versions
    FOR INSERT WITH CHECK (app.is_instructor(course_id) AND status = 'draft');

DROP POLICY exam_items_instructor_insert ON exam_items;
CREATE POLICY exam_items_instructor_insert ON exam_items
    FOR INSERT WITH CHECK (
        app.is_instructor(course_id)
        AND EXISTS (
            SELECT 1
            FROM exam_versions v
            WHERE v.id = exam_items.exam_version_id
              AND v.course_id = exam_items.course_id
              AND v.status = 'draft'
        )
        AND EXISTS (
            SELECT 1
            FROM questions q
            WHERE q.id = exam_items.question_id
              AND q.course_id = exam_items.course_id
              AND q.status = 'approved'
              AND q.purpose = 'assessment'
        )
    );

-- ---------------------------------------------------------------------------
-- Terminal immutability and publication guards
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION app.guard_question_assessment_integrity()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
BEGIN
    IF NEW.status = 'approved'
       AND NEW.purpose = 'assessment'
       AND (NEW.learning_outcome_id IS NULL OR NEW.difficulty IS NULL) THEN
        RAISE EXCEPTION 'approved assessment question requires classification'
            USING ERRCODE = '23514', CONSTRAINT = 'questions_assessment_classification';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        IF OLD.status <> 'draft' AND (
            NEW.status IS DISTINCT FROM OLD.status
            OR NEW.purpose IS DISTINCT FROM OLD.purpose
            OR NEW.payload IS DISTINCT FROM OLD.payload
            OR NEW.type IS DISTINCT FROM OLD.type
            OR NEW.source_chunk_id IS DISTINCT FROM OLD.source_chunk_id
            OR NEW.topic_id IS DISTINCT FROM OLD.topic_id
            OR NEW.learning_outcome_id IS DISTINCT FROM OLD.learning_outcome_id
            OR NEW.difficulty IS DISTINCT FROM OLD.difficulty
        ) THEN
            RAISE EXCEPTION 'terminal question is immutable'
                USING ERRCODE = '23514', CONSTRAINT = 'questions_terminal_immutable';
        END IF;

        IF EXISTS (
            SELECT 1
            FROM public.exam_items i
            JOIN public.exam_versions v ON v.id = i.exam_version_id
            WHERE i.question_id = OLD.id
              AND v.status IN ('published', 'superseded')
        ) AND (NEW.status <> 'approved' OR NEW.purpose <> 'assessment') THEN
            RAISE EXCEPTION 'published exam question must remain approved assessment'
                USING ERRCODE = '23514', CONSTRAINT = 'questions_published_exam_integrity';
        END IF;
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER questions_assessment_integrity_guard
BEFORE INSERT OR UPDATE ON questions
FOR EACH ROW EXECUTE FUNCTION app.guard_question_assessment_integrity();

CREATE OR REPLACE FUNCTION app.guard_exam_item_question()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
DECLARE
    v_exam_version_id uuid := CASE WHEN TG_OP = 'DELETE'
        THEN OLD.exam_version_id ELSE NEW.exam_version_id END;
    v_course_id uuid := CASE WHEN TG_OP = 'DELETE'
        THEN OLD.course_id ELSE NEW.course_id END;
    v_version_status text;
BEGIN
    -- Kalem mutasyonu ile publish aynı parent satır kilidinde sıralanır. RLS'in
    -- statement-snapshot status kontrolü tek başına TOCTOU'yu kapatmazdı.
    SELECT v.status::text
    INTO v_version_status
    FROM public.exam_versions v
    WHERE v.id = v_exam_version_id
      AND v.course_id = v_course_id
    FOR UPDATE;

    IF v_version_status IS NULL OR v_version_status <> 'draft' THEN
        RAISE EXCEPTION 'exam items can change only while the version is draft'
            USING ERRCODE = '23514', CONSTRAINT = 'exam_items_version_draft';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM public.questions q
        WHERE q.id = NEW.question_id
          AND q.course_id = NEW.course_id
          AND q.status = 'approved'
          AND q.purpose = 'assessment'
    ) THEN
        RAISE EXCEPTION 'exam item requires an approved assessment question'
            USING ERRCODE = '23514', CONSTRAINT = 'exam_items_assessment_question';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER exam_items_assessment_question_guard
BEFORE INSERT OR UPDATE OR DELETE ON exam_items
FOR EACH ROW EXECUTE FUNCTION app.guard_exam_item_question();

CREATE OR REPLACE FUNCTION app.guard_exam_version_publication()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        IF NOT (
            (OLD.status = 'draft' AND NEW.status = 'published')
            OR (OLD.status = 'published' AND NEW.status = 'superseded')
        ) THEN
            RAISE EXCEPTION 'invalid exam version status transition'
                USING ERRCODE = '23514', CONSTRAINT = 'exam_versions_status_transition';
        END IF;
    END IF;

    IF OLD.status = 'published' AND NEW.status = 'superseded' THEN
        IF NEW.id IS DISTINCT FROM OLD.id
           OR NEW.course_id IS DISTINCT FROM OLD.course_id
           OR NEW.blueprint_id IS DISTINCT FROM OLD.blueprint_id
           OR NEW.version_no IS DISTINCT FROM OLD.version_no
           OR NEW.published_at IS DISTINCT FROM OLD.published_at
           OR NEW.published_by IS DISTINCT FROM OLD.published_by
           OR NEW.blueprint_snapshot IS DISTINCT FROM OLD.blueprint_snapshot
           OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'published exam version evidence is immutable'
                USING ERRCODE = '23514', CONSTRAINT = 'exam_versions_terminal_immutable';
        END IF;
    ELSIF OLD.status <> 'draft' AND NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'terminal exam version is immutable'
            USING ERRCODE = '23514', CONSTRAINT = 'exam_versions_terminal_immutable';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'published' AND EXISTS (
        SELECT 1
        FROM public.exam_items i
        LEFT JOIN public.questions q
          ON q.id = i.question_id
         AND q.course_id = i.course_id
        WHERE i.exam_version_id = NEW.id
          AND (
              q.id IS NULL
              OR q.status <> 'approved'
              OR q.purpose <> 'assessment'
              OR q.learning_outcome_id IS NULL
              OR q.difficulty IS NULL
          )
    ) THEN
        RAISE EXCEPTION 'exam version contains a non-assessment question'
            USING ERRCODE = '23514', CONSTRAINT = 'exam_versions_assessment_questions';
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER exam_versions_assessment_integrity_guard
BEFORE UPDATE ON exam_versions
FOR EACH ROW EXECUTE FUNCTION app.guard_exam_version_publication();

CREATE OR REPLACE FUNCTION app.guard_blueprint_schedule_after_session()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
BEGIN
    IF (
        NEW.duration_minutes IS DISTINCT FROM OLD.duration_minutes
        OR NEW.max_attempts IS DISTINCT FROM OLD.max_attempts
        OR NEW.opens_at IS DISTINCT FROM OLD.opens_at
        OR NEW.closes_at IS DISTINCT FROM OLD.closes_at
    ) AND EXISTS (
        SELECT 1
        FROM public.exam_sessions s
        WHERE s.exam_blueprint_id = OLD.id
    ) THEN
        RAISE EXCEPTION 'blueprint schedule is immutable after the first session'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'exam_blueprints_schedule_after_session';
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER exam_blueprints_schedule_after_session_guard
BEFORE UPDATE OF duration_minutes, max_attempts, opens_at, closes_at
ON exam_blueprints
FOR EACH ROW EXECUTE FUNCTION app.guard_blueprint_schedule_after_session();

CREATE OR REPLACE FUNCTION app.guard_exam_session_feedback_schedule()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
DECLARE
    v_safe_at timestamptz;
    v_duration_minutes integer;
    v_max_attempts integer;
    v_opens_at timestamptz;
    v_closes_at timestamptz;
    v_version_status text;
    v_attempts_used integer;
    v_now timestamptz := statement_timestamp();
    v_is_app boolean := app.is_api_runtime();
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.feedback_available_at IS DISTINCT FROM OLD.feedback_available_at THEN
            RAISE EXCEPTION 'exam feedback schedule is immutable'
                USING ERRCODE = '23514', CONSTRAINT = 'exam_sessions_feedback_immutable';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.exam_version_id IS NULL THEN
        IF NEW.feedback_available_at IS NOT NULL THEN
            RAISE EXCEPTION 'legacy or practice session cannot set delayed feedback'
                USING ERRCODE = '23514', CONSTRAINT = 'exam_sessions_legacy_feedback_null';
        END IF;
        RETURN NEW;
    END IF;

    SELECT
        b.duration_minutes,
        b.max_attempts,
        b.opens_at,
        b.closes_at,
        v.status::text,
        b.closes_at + make_interval(mins => b.duration_minutes)
    INTO
        v_duration_minutes,
        v_max_attempts,
        v_opens_at,
        v_closes_at,
        v_version_status,
        v_safe_at
    FROM public.exam_blueprints b
    JOIN public.exam_versions v
      ON v.id = NEW.exam_version_id
     AND v.blueprint_id = b.id
     AND v.course_id = b.course_id
    WHERE b.id = NEW.exam_blueprint_id
      AND b.course_id = NEW.course_id
    -- Takvim UPDATE'iyle çatışır, başka öğrencilerin aynı anda başlamasıyla
    -- çatışmaz. FOR UPDATE cohort başlangıcını gereksiz yere tamamen seri yapardı.
    FOR SHARE OF b;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'blueprint session pair does not resolve'
            USING ERRCODE = '23514', CONSTRAINT = 'exam_sessions_blueprint_resolution';
    END IF;

    -- Gerçek API runtime rolünün öğrenci bağlamındaki INSERT yolu, normal API
    -- başlangıcının güvenlik kararlarını atlayamaz. BEFORE trigger değerleri
    -- kanonikleştirir; RLS WITH CHECK bundan sonra bu yeni satırı değerlendirir.
    -- Tablo sahibi tarihsel veri taşıyabilir, fakat güvenli feedback sınırı onun
    -- için de aşağıdaki ortak kontrolden geçmeye devam eder.
    IF v_is_app THEN
        IF NEW.mode <> 'exam' OR NEW.question_ids IS NOT NULL
           OR NEW.finished_at IS NOT NULL OR NEW.score IS NOT NULL THEN
            RAISE EXCEPTION 'blueprint session must start as an unfinished exam'
                USING ERRCODE = '23514', CONSTRAINT = 'exam_sessions_blueprint_mode';
        END IF;

        IF v_version_status <> 'published'
           OR v_closes_at IS NULL
           OR (v_opens_at IS NOT NULL AND v_now < v_opens_at)
           OR v_now >= v_closes_at THEN
            RAISE EXCEPTION 'blueprint session is outside its published window'
                USING ERRCODE = '23514', CONSTRAINT = 'exam_sessions_blueprint_window';
        END IF;

        SELECT count(*)::integer
        INTO v_attempts_used
        FROM public.exam_sessions s
        WHERE s.exam_blueprint_id = NEW.exam_blueprint_id
          AND s.user_id = NEW.user_id;

        IF v_attempts_used >= v_max_attempts THEN
            RAISE EXCEPTION 'blueprint attempt limit reached'
                USING ERRCODE = '23514', CONSTRAINT = 'exam_sessions_attempt_limit';
        END IF;

        NEW.started_at := v_now;
        NEW.expires_at := v_now + make_interval(mins => v_duration_minutes);
        NEW.attempt_no := v_attempts_used + 1;
        NEW.feedback_available_at := v_safe_at;
    END IF;

    IF v_safe_at IS NULL OR NEW.feedback_available_at IS NULL
       OR NEW.feedback_available_at < v_safe_at THEN
        RAISE EXCEPTION 'blueprint feedback is earlier than the safe release boundary'
            USING ERRCODE = '23514', CONSTRAINT = 'exam_sessions_feedback_safe_boundary';
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER exam_sessions_feedback_schedule_guard
BEFORE INSERT OR UPDATE ON exam_sessions
FOR EACH ROW EXECUTE FUNCTION app.guard_exam_session_feedback_schedule();

-- API aynı oturum satırını FOR UPDATE kilitler; bu trigger da API dışındaki
-- doğrudan dou_app INSERT yolunu aynı sıraya sokar. Böylece bitmiş/süresi dolmuş
-- oturuma, kâğıtta olmayan soruya veya resmî sınavda ipuçlu cevaba satır
-- enjekte edilemez. Puanlama ayrıntısı uygulamanın işi, kâğıt/lifecycle üyeliği
-- ise veritabanının değişmezidir.
CREATE OR REPLACE FUNCTION app.guard_answer_assessment_integrity()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
DECLARE
    v_exam public.exam_sessions%ROWTYPE;
BEGIN
    SELECT *
    INTO v_exam
    FROM public.exam_sessions
    WHERE id = NEW.session_id
    FOR UPDATE;

    IF NOT FOUND OR v_exam.course_id <> NEW.course_id THEN
        RAISE EXCEPTION 'answer session and course do not match'
            USING ERRCODE = '23514', CONSTRAINT = 'answers_session_course';
    END IF;

    IF v_exam.finished_at IS NOT NULL THEN
        RAISE EXCEPTION 'finished exam session cannot accept answers'
            USING ERRCODE = '23514', CONSTRAINT = 'answers_session_finished';
    END IF;

    IF v_exam.expires_at IS NOT NULL
       AND statement_timestamp() >= v_exam.expires_at THEN
        RAISE EXCEPTION 'expired exam session cannot accept answers'
            USING ERRCODE = '23514', CONSTRAINT = 'answers_session_expired';
    END IF;

    IF v_exam.mode = 'exam' AND NEW.hint_level <> 0 THEN
        RAISE EXCEPTION 'official exam answer cannot claim a hint'
            USING ERRCODE = '23514', CONSTRAINT = 'answers_exam_hint_forbidden';
    END IF;

    IF v_exam.exam_version_id IS NULL THEN
        IF v_exam.question_ids IS NULL
           OR NOT (NEW.question_id = ANY(v_exam.question_ids)) THEN
            RAISE EXCEPTION 'answer question is not in the session paper'
                USING ERRCODE = '23514', CONSTRAINT = 'answers_question_not_in_paper';
        END IF;
    ELSIF NOT EXISTS (
        SELECT 1
        FROM public.exam_items i
        WHERE i.exam_version_id = v_exam.exam_version_id
          AND i.course_id = v_exam.course_id
          AND i.question_id = NEW.question_id
    ) THEN
        RAISE EXCEPTION 'answer question is not in the frozen exam paper'
            USING ERRCODE = '23514', CONSTRAINT = 'answers_question_not_in_paper';
    END IF;

    RETURN NEW;
END
$$;

CREATE TRIGGER answers_assessment_integrity_guard
BEFORE INSERT ON answers
FOR EACH ROW EXECUTE FUNCTION app.guard_answer_assessment_integrity();

REVOKE ALL ON FUNCTION app.guard_question_assessment_integrity()
    FROM PUBLIC, dou_app, dou_worker;
REVOKE ALL ON FUNCTION app.guard_exam_item_question()
    FROM PUBLIC, dou_app, dou_worker;
REVOKE ALL ON FUNCTION app.guard_exam_version_publication()
    FROM PUBLIC, dou_app, dou_worker;
REVOKE ALL ON FUNCTION app.guard_blueprint_schedule_after_session()
    FROM PUBLIC, dou_app, dou_worker;
REVOKE ALL ON FUNCTION app.guard_exam_session_feedback_schedule()
    FROM PUBLIC, dou_app, dou_worker;
REVOKE ALL ON FUNCTION app.guard_answer_assessment_integrity()
    FROM PUBLIC, dou_app, dou_worker;

-- RLS satır sınırıdır; kolon değişmezliği ayrıca grant ile zorlanır. API yalnız
-- draft sınıflandırması ve terminal review alanlarını yazabilir.
REVOKE UPDATE ON questions FROM dou_app;
GRANT UPDATE (
    status,
    reviewed_by,
    reviewed_at,
    purpose,
    learning_outcome_id,
    difficulty
) ON questions TO dou_app;

-- Permission carrier'ın hassas ham yüzeyi yoktur. Runtime, diğer genel yetkileri
-- dou_app üyeliğinden; bu iki tablo için gerekenleri ise doğrudan grant'ten alır.
REVOKE SELECT ON questions FROM dou_app;
REVOKE SELECT, INSERT ON answers FROM dou_app;
REVOKE SELECT, INSERT ON exam_sessions FROM dou_app;
REVOKE UPDATE (finished_at) ON exam_sessions FROM dou_app;
REVOKE SELECT ON exam_versions, exam_items FROM dou_app;
GRANT SELECT ON questions TO dou_api_runtime;
GRANT SELECT, INSERT ON answers TO dou_api_runtime;
GRANT SELECT, INSERT ON exam_sessions TO dou_api_runtime;
GRANT UPDATE (finished_at) ON exam_sessions TO dou_api_runtime;
GRANT SELECT ON exam_versions, exam_items TO dou_api_runtime;

-- Ingestion worker'ın assessment verisine ihtiyacı yoktur. 0001'in gelecekteki
-- bütün tablolara verdiği blanket yetki burada assessment yüzeyi için geri alınır.
REVOKE ALL ON TABLE
    topics,
    questions,
    exam_sessions,
    answers,
    mastery,
    learning_outcomes,
    exam_blueprints,
    blueprint_cells,
    exam_versions,
    exam_items
FROM dou_worker;

COMMIT;
