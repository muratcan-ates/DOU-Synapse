-- DOU-Synapse — öğrenci geri bildirimi ve gizlilik korumalı insan incelemesi
--
-- Ürün kararı: eğitmen öğrencilerin bütün sohbetlerini okuyamaz. Öğrenci yalnızca
-- açıkça "öğretmenimle paylaş" dediğinde ilgili soru-cevap çifti geri bildirim
-- kaydına sunucu tarafından kopyalanır. Paylaşılmayan puanlar yalnız toplulaştırılmış
-- kalite sayımlarına girer; serbest metin ve sohbet içeriği görünmez.

CREATE TYPE chat_feedback_rating AS ENUM ('helpful', 'unhelpful');
CREATE TYPE chat_feedback_reason AS ENUM (
    'helpful',
    'inaccurate',
    'irrelevant',
    'citation_problem',
    'too_direct',
    'unsafe',
    'other'
);

CREATE TABLE chat_message_feedback (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id             uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    message_id            uuid NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    user_id               uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    rating                chat_feedback_rating NOT NULL,
    reason                chat_feedback_reason NOT NULL,
    comment               text,
    share_with_instructor boolean NOT NULL DEFAULT false,
    -- Bu iki alan istemciden kabul edilmez; aşağıdaki tetikleyici gerçek konuşmadan
    -- ve yalnız açık paylaşım izni varken doldurur.
    question_excerpt      text,
    answer_excerpt        text,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chat_feedback_one_per_message UNIQUE (message_id),
    CONSTRAINT chat_feedback_comment_length CHECK (
        comment IS NULL OR length(comment) <= 1000
    ),
    CONSTRAINT chat_feedback_reason_matches_rating CHECK (
        (rating = 'helpful' AND reason IN ('helpful', 'other'))
        OR (rating = 'unhelpful' AND reason <> 'helpful')
    ),
    CONSTRAINT chat_feedback_excerpt_consent CHECK (
        (share_with_instructor AND answer_excerpt IS NOT NULL)
        OR (
            NOT share_with_instructor
            AND question_excerpt IS NULL
            AND answer_excerpt IS NULL
        )
    )
);

CREATE INDEX chat_feedback_course_updated_idx
    ON chat_message_feedback (course_id, updated_at DESC, id DESC);

ALTER TABLE chat_message_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_message_feedback FORCE ROW LEVEL SECURITY;

-- Öğrenci kendi puanını görür. Eğitmen yalnız açıkça paylaşılan kayıtları satır
-- olarak görür; paylaşılmayan puanlar aşağıdaki toplu fonksiyondan sayılır.
CREATE POLICY chat_feedback_self_read ON chat_message_feedback
    FOR SELECT USING (
        user_id = app.current_user_id() AND app.is_member(course_id)
    );
CREATE POLICY chat_feedback_instructor_shared_read ON chat_message_feedback
    FOR SELECT USING (
        share_with_instructor AND app.is_instructor(course_id)
    );

-- Yalnız kendi oturumundaki bir ASİSTAN mesajı puanlanabilir. Yol parametresi ve
-- istemcinin gönderdiği kimlikler tek başına yetki değildir.
CREATE POLICY chat_feedback_self_insert ON chat_message_feedback
    FOR INSERT WITH CHECK (
        user_id = app.current_user_id()
        AND app.is_member(course_id)
        AND NOT app.is_instructor(course_id)
        AND EXISTS (
            SELECT 1
            FROM chat_messages m
            JOIN chat_sessions s ON s.id = m.session_id
            WHERE m.id = chat_message_feedback.message_id
              AND m.course_id = chat_message_feedback.course_id
              AND m.role = 'assistant'
              AND s.user_id = app.current_user_id()
              AND s.course_id = chat_message_feedback.course_id
        )
    );
CREATE POLICY chat_feedback_self_update ON chat_message_feedback
    FOR UPDATE USING (
        user_id = app.current_user_id() AND app.is_member(course_id)
    )
    WITH CHECK (
        user_id = app.current_user_id()
        AND app.is_member(course_id)
        AND NOT app.is_instructor(course_id)
        AND EXISTS (
            SELECT 1
            FROM chat_messages m
            JOIN chat_sessions s ON s.id = m.session_id
            WHERE m.id = chat_message_feedback.message_id
              AND m.course_id = chat_message_feedback.course_id
              AND m.role = 'assistant'
              AND s.user_id = app.current_user_id()
              AND s.course_id = chat_message_feedback.course_id
        )
    );

-- Kimlik/kapsam alanları değiştirilemez. Paylaşım özeti tetikleyici tarafından
-- gerçek mesajlardan üretilir; API veya doğrudan rol sahte alıntı yazamaz.
CREATE OR REPLACE FUNCTION app.prepare_chat_message_feedback()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = public, app
AS $$
DECLARE
    v_session_id uuid;
    v_answer text;
    v_question text;
    v_created_at timestamptz;
    v_seq smallint;
BEGIN
    IF TG_OP = 'UPDATE' AND (
        NEW.course_id IS DISTINCT FROM OLD.course_id
        OR NEW.message_id IS DISTINCT FROM OLD.message_id
        OR NEW.user_id IS DISTINCT FROM OLD.user_id
    ) THEN
        RAISE EXCEPTION 'feedback identity is immutable' USING ERRCODE = '42501';
    END IF;

    IF NEW.user_id IS DISTINCT FROM app.current_user_id() THEN
        RAISE EXCEPTION 'feedback owner mismatch' USING ERRCODE = '42501';
    END IF;

    IF app.is_instructor(NEW.course_id) THEN
        RAISE EXCEPTION 'student feedback required' USING ERRCODE = '42501';
    END IF;

    SELECT m.session_id, m.content, m.created_at, m.seq
      INTO v_session_id, v_answer, v_created_at, v_seq
      FROM chat_messages m
      JOIN chat_sessions s ON s.id = m.session_id
     WHERE m.id = NEW.message_id
       AND m.course_id = NEW.course_id
       AND m.role = 'assistant'
       AND s.user_id = app.current_user_id()
       AND s.course_id = NEW.course_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'assistant message not found' USING ERRCODE = '42501';
    END IF;

    IF NEW.share_with_instructor THEN
        SELECT m.content
          INTO v_question
          FROM chat_messages m
         WHERE m.session_id = v_session_id
           AND m.role = 'user'
           AND (m.created_at, m.seq, m.id)
               < (v_created_at, v_seq, NEW.message_id)
         ORDER BY m.created_at DESC, m.seq DESC, m.id DESC
         LIMIT 1;

        NEW.question_excerpt := left(v_question, 2000);
        NEW.answer_excerpt := left(v_answer, 4000);
    ELSE
        NEW.question_excerpt := NULL;
        NEW.answer_excerpt := NULL;
    END IF;

    NEW.comment := NULLIF(btrim(NEW.comment), '');
    NEW.updated_at := now();
    RETURN NEW;
END
$$;

CREATE TRIGGER chat_message_feedback_prepare
BEFORE INSERT OR UPDATE ON chat_message_feedback
FOR EACH ROW EXECUTE FUNCTION app.prepare_chat_message_feedback();

-- Eğitmenin paylaşılmayan satırlara erişmeden kalite dağılımını görmesi için
-- yalnız sayıları döndüren güvenli fonksiyon. Serbest metin veya kullanıcı kimliği
-- bu sözleşmeye giremez.
CREATE OR REPLACE FUNCTION app.chat_feedback_summary(p_course_id uuid)
RETURNS TABLE (
    rated_count bigint,
    helpful_count bigint,
    unhelpful_count bigint,
    shared_review_count bigint,
    reason_counts jsonb
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, app
AS $$
BEGIN
    IF NOT app.is_instructor(p_course_id) THEN
        RAISE EXCEPTION 'course instructor required' USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT
        count(*)::bigint,
        count(*) FILTER (WHERE f.rating = 'helpful')::bigint,
        count(*) FILTER (WHERE f.rating = 'unhelpful')::bigint,
        count(*) FILTER (WHERE f.share_with_instructor)::bigint,
        COALESCE(
            (
                SELECT jsonb_object_agg(reason::text, reason_count)
                FROM (
                    SELECT reason, count(*)::bigint AS reason_count
                    FROM chat_message_feedback
                    WHERE course_id = p_course_id
                    GROUP BY reason
                ) counts
            ),
            '{}'::jsonb
        )
    FROM chat_message_feedback f
    WHERE f.course_id = p_course_id;
END
$$;

-- 0001'deki varsayılan tam UPDATE yetkisini daralt: kapsam ve paylaşılan alıntı
-- sütunları yalnız tetikleyicinin kontrolündedir.
REVOKE UPDATE, DELETE ON chat_message_feedback FROM dou_app;
GRANT SELECT, INSERT ON chat_message_feedback TO dou_app;
GRANT UPDATE (rating, reason, comment, share_with_instructor, updated_at)
    ON chat_message_feedback TO dou_app;
REVOKE ALL ON chat_message_feedback FROM dou_worker;

REVOKE ALL ON FUNCTION app.chat_feedback_summary(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.chat_feedback_summary(uuid) TO dou_app;
REVOKE ALL ON FUNCTION app.prepare_chat_message_feedback() FROM PUBLIC;

COMMENT ON TABLE chat_message_feedback IS
    'Öğrenci yanıt puanları; eğitmen yalnız açıkça paylaşılan metinleri görür.';
