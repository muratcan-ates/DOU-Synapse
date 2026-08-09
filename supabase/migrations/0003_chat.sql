-- DOU-Synapse — sohbet (chat) şeması
--
-- Tasarım notu (tasks.md T017, ARCHITECTURE.md §5):
-- Sohbet oturumu, mesaj geçmişi, birebir eşleşmeli cevap önbelleği ve istek ölçüm kaydı.
-- 0001_core_schema.sql ile 0004_assessment.sql desenini birebir izler: course_id her
-- tabloda denormalize edilir (izolasyon filtresi JOIN'e bağlı kalmaz), her tablo
-- ENABLE + FORCE ROW LEVEL SECURITY ile işaretlenir, politikalar app.is_member() /
-- app.is_instructor() yardımcılarını kullanır.
--
-- 0004 incelemesinde yakalanan hata burada tekrarlanmıyor: denormalize course_id taşıyan
-- bir tabloya INSERT politikası yazarken YALNIZ user_id kontrolü yetmez. Üye olmayan bir
-- kullanıcı, üyesi olmadığı dersin verisine satır enjekte edebilir. Bu dosyadaki her
-- INSERT politikası ya app.is_member(course_id) çağırır ya da satırın course_id'sini
-- sahibi olduğu oturumun course_id'siyle eşler (üçlü kontrol).
--
-- UPDATE politikalarında WITH CHECK bilinçli olarak yazılmıştır: yazılmazsa PostgreSQL
-- güncellenen satır için USING ifadesini kullanır ve satırın başka bir derse TAŞINMASINI
-- engellemez.

BEGIN;

-- ---------------------------------------------------------------------------
-- Enum'lar
-- ---------------------------------------------------------------------------

-- Değerler `apps/api/app/contracts.py` içindeki ChatMode / AnswerStatus / SocraticStage
-- ile BİREBİR aynıdır; modeller (app/models/chat.py) sözleşme enum'larına doğrudan
-- bağlanabilsin diye. `exam` MVP'de chat_sessions'a yazılmaz (sınav akışı exam_sessions
-- tablosundadır) ama enum eksik bırakılırsa sözleşmeden şemaya eşleme kısmi kalırdı.
CREATE TYPE chat_mode     AS ENUM ('qa', 'socratic', 'exam');
CREATE TYPE chat_role     AS ENUM ('user', 'assistant');
CREATE TYPE answer_status AS ENUM ('answered', 'insufficient_context', 'out_of_scope');
CREATE TYPE socratic_stage AS ENUM (
    'diagnose', 'nudge', 'concept_hint', 'similar_example', 'explain_with_source'
);

-- ---------------------------------------------------------------------------
-- Sohbet oturumları
-- ---------------------------------------------------------------------------

CREATE TABLE chat_sessions (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id   uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id     uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    mode        chat_mode NOT NULL DEFAULT 'qa',
    -- Sokratik kademe ve öğrencinin deneme sayacı burada yaşar. jsonb seçilmesinin
    -- sebebi: state machine saf Python'da (modules/assessment/socratic.py) tanımlıdır ve
    -- kademe kümesi büyüdüğünde şema değişmeden serileşebilmelidir. Biçim:
    --   {"socratic": {"stage": "...", "attempts": n, "refusals": n, "transitions": [...]}}
    state       jsonb NOT NULL DEFAULT '{}'::jsonb,
    title       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX chat_sessions_user_idx ON chat_sessions (user_id, updated_at DESC);
CREATE INDEX chat_sessions_course_idx ON chat_sessions (course_id);

COMMENT ON COLUMN chat_sessions.state IS
    'Sokratik merdivenin kalıcı hâli. Oturum yeniden yüklense de kademe korunur (FR-014).';

-- ---------------------------------------------------------------------------
-- Mesajlar
-- ---------------------------------------------------------------------------

CREATE TABLE chat_messages (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     uuid NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    -- Denormalize: izolasyon filtresi chat_sessions'a JOIN etmeden tek satırda ifade
    -- edilir (answers tablosuyla aynı desen).
    course_id      uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    role           chat_role NOT NULL,
    content        text NOT NULL,
    -- [{"chunk_id": "...", "file_name": "...", "location": "Sayfa 7", "quote": "..."}]
    -- Dosya adı ve konum MODEL METNİNDEN DEĞİL chunk metadata'sından üretilir (Anayasa I);
    -- burada yalnız üretilmiş hâli saklanır.
    citations      jsonb NOT NULL DEFAULT '[]'::jsonb,
    -- Kullanıcı mesajlarında NULL; asistan mesajlarında üç meşru sonuçtan biri.
    -- SC-005 yalnız out_of_scope'u ölçer, insufficient_context'i değil — bu yüzden iki
    -- durum aynı sütunda ama ayrı değerlerle tutulur, birleştirilmez.
    status         answer_status,
    socratic_stage socratic_stage,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chat_messages_status_by_role CHECK (
        (role = 'user' AND status IS NULL) OR (role = 'assistant' AND status IS NOT NULL)
    )
);

CREATE INDEX chat_messages_session_idx ON chat_messages (session_id, created_at);
CREATE INDEX chat_messages_course_idx ON chat_messages (course_id);

-- ---------------------------------------------------------------------------
-- Cevap önbelleği (FR-034)
-- ---------------------------------------------------------------------------

-- Birebir eşleşmeli önbellek; benzerlik tabanlı eşleşme YOKTUR. Demo günü aynı soruyu
-- ikinci kez sormak ücretsiz ve anlık olmalıdır.
--
-- Önbellek DERS BAZLIDIR: bir dersin önbelleği başka derse asla servis edilmez. Aksi
-- hâlde izolasyon tezinin tamamı çöker — bu yüzden benzersizlik anahtarı
-- (course_id, question_hash) çiftidir, tek başına question_hash değil.
CREATE TABLE answer_cache (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id      uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    -- sha256(mode + '\n' + normalize edilmiş soru). Mod anahtarın parçasıdır: bir QA
    -- cevabı Sokratik moda servis edilirse merdiven baypas edilmiş olur.
    question_hash  text NOT NULL,
    -- Guardrail zincirinden GEÇMİŞ cevap zarfı (status, text, citations, ...).
    -- Elle yazılmaz; yalnız tam hattan çıkmış bir cevap buraya girer.
    answer         jsonb NOT NULL,
    created_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT answer_cache_hash_not_blank CHECK (length(btrim(question_hash)) > 0)
);

CREATE UNIQUE INDEX answer_cache_course_question_key ON answer_cache (course_id, question_hash);

-- ---------------------------------------------------------------------------
-- İstek ölçüm kaydı (FR-035, Anayasa III)
-- ---------------------------------------------------------------------------

-- Ölçülemeyen iddia savunulamaz: gecikme, sonuç dağılımı, önbellek isabet oranı ve token
-- tüketimi buradan raporlanır.
--
-- SORU METNİ VE HİÇBİR SERBEST METİN BURAYA YAZILMAZ. Tablo yalnız sayısal/kategorik
-- alan taşır; kişisel veri redaksiyonu (FR-035) böylece bir filtreye değil şemaya
-- dayanır — yanlışlıkla PII yazmak mümkün değildir.
CREATE TABLE request_logs (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id    uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    user_id      uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    route        text NOT NULL,
    mode         chat_mode NOT NULL,
    status       answer_status,
    http_status  integer NOT NULL,
    latency_ms   integer NOT NULL CHECK (latency_ms >= 0),
    token_count  integer,
    cache_hit    boolean NOT NULL DEFAULT false,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX request_logs_course_idx ON request_logs (course_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- RLS politikaları
-- ---------------------------------------------------------------------------

ALTER TABLE chat_sessions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages  ENABLE ROW LEVEL SECURITY;
ALTER TABLE answer_cache   ENABLE ROW LEVEL SECURITY;
ALTER TABLE request_logs   ENABLE ROW LEVEL SECURITY;

ALTER TABLE chat_sessions  FORCE ROW LEVEL SECURITY;
ALTER TABLE chat_messages  FORCE ROW LEVEL SECURITY;
ALTER TABLE answer_cache   FORCE ROW LEVEL SECURITY;
ALTER TABLE request_logs   FORCE ROW LEVEL SECURITY;

-- chat_sessions: kullanıcı YALNIZ kendi oturumlarını görür ve açar.
--
-- Eğitmene okuma yetkisi bilinçli olarak VERİLMEDİ: öğrencinin hocasına sorma
-- çekindiği soruyu sisteme sorabilmesi ürünün gerekçelerinden biri, eğitmenin bunu
-- satır satır okuyabilmesi bunu bozar. Eğitmen ekranı toplulaştırılmış analitiği
-- (Faz E) kullanır. Bu bir gizlilik kararıdır; değişecekse gruba yazılır.
CREATE POLICY chat_sessions_self_read ON chat_sessions
    FOR SELECT USING (
        user_id = app.current_user_id() AND app.is_member(course_id)
    );
-- user_id kontrolü TEK BAŞINA yetmez: üye olmayan bir kullanıcı kendi adına, üyesi
-- olmadığı bir dersin kimliğiyle oturum açabilirdi (0004 incelemesi, kalem 2).
CREATE POLICY chat_sessions_self_insert ON chat_sessions
    FOR INSERT WITH CHECK (
        user_id = app.current_user_id() AND app.is_member(course_id)
    );
CREATE POLICY chat_sessions_self_update ON chat_sessions
    FOR UPDATE USING (user_id = app.current_user_id() AND app.is_member(course_id))
    WITH CHECK (user_id = app.current_user_id() AND app.is_member(course_id));

-- chat_messages: oturum sahibine bağlıdır. UPDATE/DELETE politikası YOKTUR — mesaj
-- geçmişi denetlenebilir olmak zorundadır; sonradan düzeltilebilen bir geçmiş,
-- "sistem gerçekten yönlendirdi mi" sorusuna kanıt olamaz (Anayasa III).
CREATE POLICY chat_messages_self_read ON chat_messages
    FOR SELECT USING (
        app.is_member(course_id)
        AND EXISTS (
            SELECT 1 FROM chat_sessions s
            WHERE s.id = chat_messages.session_id
              AND s.user_id = app.current_user_id()
        )
    );
-- Üçlü kontrol: oturum bana ait olmalı VE satırın taşıdığı course_id oturumun gerçek
-- course_id'siyle eşleşmeli. Eşleşme aranmazsa kendi oturumuna sahte bir course_id
-- iliştirip başka dersin kayıtlarına satır enjekte etmek mümkün olurdu.
CREATE POLICY chat_messages_self_insert ON chat_messages
    FOR INSERT WITH CHECK (
        EXISTS (
            SELECT 1 FROM chat_sessions s
            WHERE s.id = chat_messages.session_id
              AND s.user_id = app.current_user_id()
              AND s.course_id = chat_messages.course_id
        )
    );

-- answer_cache: ders bazlı paylaşımlı önbellek. Üyeler okur ve yazar; temizlik yalnız
-- eğitmende.
--
-- Kabul edilen artık risk (Anayasa III — abartmadan yazılıyor): RLS düzeyinde dersin bir
-- üyesi kendi dersinin önbelleğine satır yazabilir. Önbelleğe yalnız guardrail
-- zincirinden geçmiş cevabın girmesi UYGULAMA katmanının garantisidir, veritabanının
-- değil. Bu kabul edilebilir çünkü kullanıcıların doğrudan veritabanı kimliği yoktur;
-- tek yol API'dir. Başka derse sızma ise iki katmanda da kapalıdır.
CREATE POLICY answer_cache_member_read ON answer_cache
    FOR SELECT USING (app.is_member(course_id));
CREATE POLICY answer_cache_member_insert ON answer_cache
    FOR INSERT WITH CHECK (app.is_member(course_id));
CREATE POLICY answer_cache_instructor_delete ON answer_cache
    FOR DELETE USING (app.is_instructor(course_id));

-- request_logs: istemciye KAPALI. SELECT politikası bilinçli olarak yoktur; tablo
-- uygulama rolü için yazma-yalnız davranır. Ölçüm raporları sahip rolle (psql,
-- evaluation/) okunur. Analitik ekranı satır bazlı erişime ihtiyaç duyarsa eğitmen
-- kapsamlı bir SELECT politikası 0005'te açılır (Şerit 5) — burada değil.
CREATE POLICY request_logs_self_insert ON request_logs
    FOR INSERT WITH CHECK (
        user_id = app.current_user_id() AND app.is_member(course_id)
    );

COMMIT;
