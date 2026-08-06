-- DOU-Synapse — ölçme (assessment) şeması
--
-- Tasarım notu (R3 brief §2 Teslimat 1):
-- Konu, soru, sınav oturumu, cevap ve mastery tabloları. 0001_core_schema.sql'in izolasyon
-- desenini birebir izler: course_id her tabloda denormalize edilir (retrieval/izolasyon
-- filtresi JOIN'e bağlı kalmaz), her tablo ENABLE + FORCE ROW LEVEL SECURITY ile işaretlenir,
-- politikalar app.is_member() / app.is_instructor() yardımcılarını kullanır.
--
-- En kritik politika: öğrenci yalnız status='approved' sorularını görebilir; draft/rejected
-- yalnız dersin eğitmenine açıktır. Bu, uygulama katmanındaki aynı filtreyle birlikte
-- "iki katmanlı izolasyon"un ölçme ayağıdır (Anayasa II).

BEGIN;

-- ---------------------------------------------------------------------------
-- Enum'lar
-- ---------------------------------------------------------------------------

CREATE TYPE question_type   AS ENUM ('mcq', 'open', 'code_trace', 'bug_hunt');
CREATE TYPE question_status AS ENUM ('draft', 'approved', 'rejected');
CREATE TYPE exam_mode       AS ENUM ('practice', 'exam');

-- ---------------------------------------------------------------------------
-- Konular
-- ---------------------------------------------------------------------------

CREATE TABLE topics (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id   uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    name        text NOT NULL,
    created_by  uuid NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT topics_name_not_blank CHECK (length(btrim(name)) > 0)
);

-- Aynı derste aynı isimde iki konu olmasın (soru üretimi ve mastery konu adına bağlı).
CREATE UNIQUE INDEX topics_course_name_key ON topics (course_id, lower(name));
CREATE INDEX topics_course_idx ON topics (course_id);

-- ---------------------------------------------------------------------------
-- Sorular
-- ---------------------------------------------------------------------------

CREATE TABLE questions (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Denormalize: draft/approved filtresi JOIN'e bağlı kalmasın (chunks ile aynı desen).
    course_id        uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    topic_id         uuid NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    type             question_type NOT NULL,
    -- Dört tipin ortak zarfı: {stem/prompt, ..., answer_key, ...}. Biçim R3 brief §2'de
    -- sabitlenmiştir; MCQ'da distractor_sources zorunludur ("neden yanlış?"nin girdisi).
    payload          jsonb NOT NULL,
    -- Üretimde kullanılan kaynak chunk. Model uydurursa (retrieve edilmiş kümede yoksa)
    -- soru havuza hiç yazılmaz (question_gen.py, fail-closed).
    source_chunk_id  uuid NOT NULL REFERENCES chunks(id) ON DELETE RESTRICT,
    status           question_status NOT NULL DEFAULT 'draft',
    created_by       uuid REFERENCES profiles(id) ON DELETE SET NULL,
    reviewed_by      uuid REFERENCES profiles(id) ON DELETE SET NULL,
    reviewed_at      timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT questions_reviewed_consistency CHECK (
        (status = 'draft' AND reviewed_by IS NULL AND reviewed_at IS NULL)
        OR (status IN ('approved', 'rejected') AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
    )
);

CREATE INDEX questions_course_idx ON questions (course_id, status);
CREATE INDEX questions_topic_idx ON questions (topic_id);

-- ---------------------------------------------------------------------------
-- Sınav oturumları
-- ---------------------------------------------------------------------------

CREATE TABLE exam_sessions (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id     uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id       uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    mode          exam_mode NOT NULL,
    started_at    timestamptz NOT NULL DEFAULT now(),
    -- practice modda NULL: süresiz. exam modda started_at + EXAM_DURATION_MINUTES.
    -- İstemci saatine güvenilmez; kalan süre her istekte buradan hesaplanır.
    expires_at    timestamptz,
    finished_at   timestamptz,
    score         numeric,
    -- Oturum açılırken seçilen sorular burada sabitlenir. Sonradan onaylanan/reddedilen
    -- sorular başlamış bir sınavı değiştirmez.
    question_ids  uuid[] NOT NULL,
    CONSTRAINT exam_sessions_exam_has_expiry CHECK (
        mode = 'practice' OR expires_at IS NOT NULL
    )
);

CREATE INDEX exam_sessions_course_idx ON exam_sessions (course_id);
CREATE INDEX exam_sessions_user_idx ON exam_sessions (user_id, started_at DESC);

-- ---------------------------------------------------------------------------
-- Cevaplar
-- ---------------------------------------------------------------------------

CREATE TABLE answers (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   uuid NOT NULL REFERENCES exam_sessions(id) ON DELETE CASCADE,
    question_id  uuid NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    -- Denormalize: RLS filtresi exam_sessions'a JOIN etmeden tek satırda ifade edilir.
    course_id    uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    given        text,
    is_correct   boolean,
    score        integer,
    hint_level   integer NOT NULL DEFAULT 0,
    -- Açık uçlu/kod sorularında şemalı LLM değerlendirmesi:
    -- {"score": 0-100, "eksik_noktalar": [...], "dayanak_chunk_id": "..."}
    feedback     jsonb,
    answered_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT answers_score_range CHECK (score IS NULL OR (score >= 0 AND score <= 100)),
    -- Bir oturumda aynı soru yalnız bir kez cevaplanır (exam modda "tek deneme" burada da
    -- veritabanı seviyesinde zorlanır; uygulama katmanı ayrıca 409 döner).
    UNIQUE (session_id, question_id)
);

CREATE INDEX answers_session_idx ON answers (session_id);
CREATE INDEX answers_course_idx ON answers (course_id);

-- ---------------------------------------------------------------------------
-- Mastery (konu bazlı EWMA göstergesi)
-- ---------------------------------------------------------------------------

CREATE TABLE mastery (
    user_id       uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    topic_id      uuid NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    course_id     uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    score         double precision NOT NULL,
    -- "İlk cevap mı" sorusunu cevaplar: 0 ise EWMA'yı 0'dan başlatmak yerine ilk skoru
    -- doğrudan yazarız (mastery/service.py, T036).
    answer_count  integer NOT NULL DEFAULT 0,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, topic_id),
    CONSTRAINT mastery_score_range CHECK (score >= 0 AND score <= 1)
);

CREATE INDEX mastery_course_idx ON mastery (course_id);

-- ---------------------------------------------------------------------------
-- RLS politikaları
-- ---------------------------------------------------------------------------

ALTER TABLE topics         ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_sessions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE answers        ENABLE ROW LEVEL SECURITY;
ALTER TABLE mastery        ENABLE ROW LEVEL SECURITY;

ALTER TABLE topics         FORCE ROW LEVEL SECURITY;
ALTER TABLE questions      FORCE ROW LEVEL SECURITY;
ALTER TABLE exam_sessions  FORCE ROW LEVEL SECURITY;
ALTER TABLE answers        FORCE ROW LEVEL SECURITY;
ALTER TABLE mastery        FORCE ROW LEVEL SECURITY;

-- topics: dersin üyeleri okur, yalnız eğitmen yazar.
CREATE POLICY topics_member_read ON topics
    FOR SELECT USING (app.is_member(course_id));
CREATE POLICY topics_instructor_write ON topics
    FOR INSERT WITH CHECK (app.is_instructor(course_id));
CREATE POLICY topics_instructor_update ON topics
    FOR UPDATE USING (app.is_instructor(course_id));
CREATE POLICY topics_instructor_delete ON topics
    FOR DELETE USING (app.is_instructor(course_id));

-- questions: EN KRİTİK politika. Öğrenci yalnız approved görür; draft/rejected yalnız
-- eğitmene açıktır. Uygulama katmanı da aynı filtreyi zorunlu tutar (iki katman).
CREATE POLICY questions_read ON questions
    FOR SELECT USING (
        app.is_instructor(course_id)
        OR (app.is_member(course_id) AND status = 'approved')
    );
CREATE POLICY questions_instructor_write ON questions
    FOR INSERT WITH CHECK (app.is_instructor(course_id));
CREATE POLICY questions_instructor_update ON questions
    FOR UPDATE USING (app.is_instructor(course_id));

-- exam_sessions: kullanıcı yalnız kendi oturumlarını görür/açar; eğitmen kendi dersinin
-- oturumlarını yalnız OKUR (analitik için), yazamaz.
CREATE POLICY exam_sessions_self_read ON exam_sessions
    FOR SELECT USING (
        user_id = app.current_user_id() OR app.is_instructor(course_id)
    );
CREATE POLICY exam_sessions_self_insert ON exam_sessions
    FOR INSERT WITH CHECK (user_id = app.current_user_id() AND app.is_member(course_id));
-- WITH CHECK eklendi: eklenmezse Postgres güncellenen satır için de USING'i kullanır,
-- ki bu yalnızca user_id kontrol eder — oturum course_id'si üyesi olunmayan bir derse
-- kaydırılabilirdi (PR incelemesi, kalem 2'yle aynı sınıf açık; koştu, kapandı).
CREATE POLICY exam_sessions_self_update ON exam_sessions
    FOR UPDATE USING (user_id = app.current_user_id())
    WITH CHECK (user_id = app.current_user_id() AND app.is_member(course_id));

-- answers: kullanıcı yalnız kendi cevaplarını görür/yazar; eğitmen kendi dersininkileri
-- yalnız OKUR.
CREATE POLICY answers_self_read ON answers
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM exam_sessions s
            WHERE s.id = answers.session_id AND s.user_id = app.current_user_id()
        )
        OR app.is_instructor(course_id)
    );
CREATE POLICY answers_self_insert ON answers
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM exam_sessions s
            WHERE s.id = answers.session_id
              AND s.user_id = app.current_user_id()
              -- Satırın taşıdığı course_id, oturumun gerçek course_id'siyle eşleşmeli;
              -- aksi halde kendi oturumuna sahte bir course_id iliştirilip başka
              -- dersin eğitmen analitiğine satır enjekte edilebilir (PR incelemesi,
              -- kalem 2).
              AND s.course_id = answers.course_id
        )
    );

-- mastery: öğrenci kendi satırını, eğitmen kendi dersinin satırlarını okur. Yazma yalnız
-- mastery/service.py üzerinden (uygulama rolü UPDATE/INSERT yapar, RLS ile tutarlı).
CREATE POLICY mastery_self_read ON mastery
    FOR SELECT USING (
        user_id = app.current_user_id() OR app.is_instructor(course_id)
    );
-- app.is_member(course_id) eksikti: yalnızca user_id kontrolü, kullanıcının o dersin
-- üyesi olup olmadığına bakmıyordu. Üye olunmayan bir derse mastery satırı yazılıp o
-- dersin eğitmeninin analitiğine sahte veri enjekte edilebiliyordu (PR incelemesi,
-- kalem 2 — üye olmayan öğrenciyle canlı doğrulandı).
CREATE POLICY mastery_self_insert ON mastery
    FOR INSERT WITH CHECK (user_id = app.current_user_id() AND app.is_member(course_id));
CREATE POLICY mastery_self_update ON mastery
    FOR UPDATE USING (user_id = app.current_user_id() AND app.is_member(course_id));

COMMIT;
