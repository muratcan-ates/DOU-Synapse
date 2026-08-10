-- Keyset sayfalamanın belirlenimci sıralama indeksleri (002 / FR-160...FR-163).
-- Yeni indeksler önce kurulur; kapsadıkları eski indeksler sonra kaldırılır.

CREATE INDEX courses_created_page_idx
    ON courses (created_at DESC, id DESC);

CREATE INDEX documents_course_page_idx
    ON documents (course_id, created_at DESC, id DESC);
DROP INDEX documents_course_idx;

CREATE INDEX questions_course_page_idx
    ON questions (course_id, created_at DESC, id DESC);

CREATE INDEX chat_sessions_user_course_page_idx
    ON chat_sessions (user_id, course_id, updated_at DESC, id DESC);
DROP INDEX chat_sessions_user_idx;

CREATE INDEX chat_messages_session_page_idx
    ON chat_messages (session_id, created_at DESC, seq DESC, id DESC);
DROP INDEX chat_messages_session_idx;
