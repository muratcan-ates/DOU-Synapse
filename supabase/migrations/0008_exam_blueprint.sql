-- DOU-Synapse — sınav blueprint ailesi (002 US3, FR-110…FR-119)
--
-- Beş yeni tablo, üç mevcut tabloya kolon, iki `app` yardımcısı.
-- `0004_assessment.sql`'in izolasyon desenini birebir izler: course_id her tabloda
-- denormalize, her tablo ENABLE + FORCE ROW LEVEL SECURITY, politikalar
-- app.is_member() / app.is_instructor() üzerinden.
--
-- ---------------------------------------------------------------------------
-- Neden bu biçim
-- ---------------------------------------------------------------------------
--
-- (1) `exams` diye bir tablo AÇILMIYOR. Var olan `exam_sessions` bir öğrencinin tek
--     denemesidir, öğretmenin sınavı değil. Blueprint onun yerini almaz, üstüne gelir:
--     bir oturum ya bugünkü self-servis provadır (`question_ids` dolu) ya da bir
--     blueprint sürümüne bağlıdır (`exam_version_id` dolu). İkisi bir arada olamaz ve
--     bu, `exam_sessions_paper_source` kısıtıyla ifade edilemez kılınmıştır.
--
-- (2) Yayınlanmış kâğıt SNAPSHOT'lanmıyor, KİMLİKLE referans veriliyor. Bu depoda
--     soru içeriği zaten değişmez — `api/questions.py`'de soruyu düzenleyen hiçbir uç
--     yok (yalnız generate/approve/reject/delete). İçerik değişmezse kimlikle referans
--     kopyayla saklama kadar sağlamdır. Dahası kopya zararlı olurdu: payload şeması
--     değişince eski snapshot'lar `parse_payload`'dan düşer ve değerlendirme
--     "değerlendirilemedi"ye çevrilir — geçmişi korumak yerine bozardı.
--
-- (3) Ama DAĞILIM donuyor (`exam_versions.blueprint_snapshot`). Sebep asimetrik:
--     soru içeriği değişmez, `blueprint_cells` ise düzenlenebilir. Sürüm
--     yayınlandıktan sonra hücreler değişirse "bu sınav blueprint'ine birebir uydu"
--     iddiası (SC-003) geriye dönük olarak yeniden üretilemez hâle gelirdi.
--     `exam_items.points`'in `points_per_question`'dan yayın anında kopyalanması ile
--     aynı karar; gerekçesi ve reddedilen iki alternatifi data-model.md §8 madde 1'de.
--
-- (4) FR-112'nin iç tutarlılık doğrulaması BURADA DEĞİL, uygulama katmanında.
--     Satır içi olgular CHECK'te (adet aralığı, puan aralığı, UNIQUE); satırlar arası
--     aritmetik uygulamada. İki sebep: CHECK diğer satırlara bakamaz (tek alternatif
--     trigger'dır ve bu depoda `public` şemasındaki hiçbir iş kuralı trigger'a
--     yazılmamıştır), ve kısıt ihlali PostgreSQL'den kısıt adıyla döner — "Zor MCQ
--     hücresi 2 soru istiyor ama 1 tane var" cümlesini kuramaz (Anayasa V).
--
-- ---------------------------------------------------------------------------
-- BİLEREK YAPILMAYANLAR (0007'nin (c) maddesinin âdeti)
-- ---------------------------------------------------------------------------
--
-- (a) `rubrics` tablosu — rubrik `questions.payload.rubric`'te yaşıyor ve
--     `modules/assessment/grading.py` onu zaten okuyor. Paylaşılan bir rubrik,
--     sürümleme sorununu ikinci bir varlığa taşırdı: soru dondurulmuşken rubrik
--     değişirse yürüyen sınavın puanlaması değişirdi.
-- (b) `question_learning_outcomes` ara tablosu — FR-113 tekil kardinalite istiyor.
--     Çoğa-çok, FR-112/FR-114 aritmetiğini imkânsız kılardı: bir soru iki hücreye
--     sayılırsa hücre toplamları soru sayısına eşitlenemez.
-- (c) `exam_publications` tablosu — yayın, sürümün durumudur. Ayrı tabloda "bir
--     blueprint'in aynı anda tek yayınlanmış sürümü olur" kuralı uygulama koduyla
--     korunurdu; kolon olunca kısmi tekil indeksle yapısal olur.
-- (d) `questions.source_stale` bayrağı — türetilebilir. Saklanan bir bayrağın bir
--     yazıcısı olur ve o yazıcı yükleme anında o belgenin tüm chunk'larının tüm
--     sorularını gezmek zorundadır; bu fan-out arka planda sessizce düşebilir.
-- (e) `exam_items.blueprint_cell_id` — türetilebilir. Pointer tutmak, hücre
--     silindiğinde ya kanıtı kaybettiren (SET NULL) ya da blueprint'i kilitleyen
--     (RESTRICT) bir ikilem üretirdi.
-- (f) `exam_version_cells` tablosu — (3)'ün normalize edilmiş biçimi. Yalnız okunup
--     hiç toplulaştırılmayan bir kanıt için altıncı tablo açmaya değmedi.
-- (g) `GRANT UPDATE ON exam_sessions TO dou_app` — 0007 bu yetkiyi bilerek çekti ve
--     yalnız `finished_at`'i geri verdi. Geniş bir UPDATE geri verilirse öğrenci kendi
--     `expires_at`'ini yazabilir hâle gelir ve süre koruması sessizce kalkar. Yeni
--     kolonlar INSERT anında yazılır; UPDATE gerekmez.

BEGIN;

-- ---------------------------------------------------------------------------
-- Enum'lar
-- ---------------------------------------------------------------------------

CREATE TYPE question_difficulty AS ENUM ('easy', 'medium', 'hard');
CREATE TYPE exam_version_status AS ENUM ('draft', 'published', 'superseded');

-- ---------------------------------------------------------------------------
-- Öğrenme çıktıları
-- ---------------------------------------------------------------------------
--
-- Neden `topics`'e katılmadı: `topics` mastery'nin birincil anahtarının parçasıdır
-- (0004:136) ve soru üretiminin retrieval sorgusu `topic.name`'dir. Konu bir ARAMA
-- KOLU, çıktı bir ÖLÇÜLEBİLİR İDDİA'dır. Birleştirmek mastery semantiğini ve
-- ölçülmüş retrieval davranışını aynı anda değiştirirdi (Anayasa III).
--
-- `topic_id` köprüsü üretimin bugünkü davranışını korumak için var: çıktı bir konuya
-- bağlıysa soru üretimi bugünkü sorgusunu aynen kullanır. Konu dağılımı da bu köprü
-- üzerinden TÜRETİLİR; ayrı bir hücre ekseni değildir (data-model.md §8 madde 2).

CREATE TABLE learning_outcomes (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id    uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    code         text NOT NULL,
    description  text NOT NULL,
    topic_id     uuid REFERENCES topics(id) ON DELETE SET NULL,
    created_by   uuid NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT learning_outcomes_code_not_blank CHECK (length(btrim(code)) > 0)
);

-- `topics_course_name_key` (0004:37) ve `courses_code_key` (0001:64) ile aynı desen:
-- derste kod büyük/küçük harf duyarsız tekildir.
CREATE UNIQUE INDEX learning_outcomes_course_code_key
    ON learning_outcomes (course_id, lower(code));
CREATE INDEX learning_outcomes_course_idx ON learning_outcomes (course_id);

-- ---------------------------------------------------------------------------
-- `questions` — hücre ekseni kolonları
-- ---------------------------------------------------------------------------
--
-- İkisi de NULL kabul eder ve VARSAYILANI YOKTUR. `0006:33-37`'nin gerekçesi birebir
-- geçerli: "NOT NULL + varsayılan değer koymak, bilmediğimiz bir şeyi biliyormuş gibi
-- yazmak olurdu". Havuzdaki bir sorunun hangi kazanımı ölçtüğünü göç bilemez;
-- 'medium' gibi bir varsayılan, ölçülmemiş bir iddiayı veriye yazmak olurdu.
--
-- BEDELİ AÇIKÇA YAZILIYOR: "her soru bir çıktıya bağlıdır" kuralı veri düzeyinde
-- garanti DEĞİLDİR. Kuralı zorlayan tek yer yayın kapısıdır ve kapı bunu ayrı bir
-- madde olarak raporlar ("sınıflandırılmamış kalemler"), eksik hücre olarak değil —
-- aksi hâlde öğretmen yanlış hücreye soru eklemeye çalışırdı (data-model.md §8 md 7).

ALTER TABLE questions
    ADD COLUMN learning_outcome_id uuid REFERENCES learning_outcomes(id) ON DELETE SET NULL,
    ADD COLUMN difficulty question_difficulty;

-- Hücre doldurma ve yayın kapısı bu indeksten okunur. Kısmi indeks deseni
-- `ingestion_jobs_pending_idx` (0001:284-285) ile aynı: sorgu zaten yalnız approved
-- satırlarla ilgilenir.
CREATE INDEX questions_cell_idx
    ON questions (course_id, learning_outcome_id, difficulty, type)
    WHERE status = 'approved';

-- ---------------------------------------------------------------------------
-- Blueprint (sınavın çatısı — sorulardan ÖNCE var)
-- ---------------------------------------------------------------------------

CREATE TABLE exam_blueprints (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id         uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title             text NOT NULL,
    description       text,
    duration_minutes  integer NOT NULL,
    max_attempts      smallint NOT NULL DEFAULT 1,
    opens_at          timestamptz,
    closes_at         timestamptz,
    created_by        uuid NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT exam_blueprints_title_not_blank CHECK (length(btrim(title)) > 0),
    CONSTRAINT exam_blueprints_duration_range CHECK (duration_minutes BETWEEN 1 AND 600),
    CONSTRAINT exam_blueprints_attempts_range CHECK (max_attempts >= 1),
    -- Ters pencere İFADE EDİLEMEZ olmalı; `exam_sessions_exam_has_expiry` (0004:88-90)
    -- ile aynı "geçersiz durumu ifade edilemez kıl" deseni. NULL = o yönde sınır yok.
    CONSTRAINT exam_blueprints_window_order CHECK (
        opens_at IS NULL OR closes_at IS NULL OR opens_at < closes_at
    )
);

-- Sayfalama için baştan doğru sıralama (0011 bu desen üzerine gelecek).
CREATE INDEX exam_blueprints_course_idx
    ON exam_blueprints (course_id, created_at DESC, id DESC);

-- Toplam soru sayısı KOLON DEĞİLDİR: SUM(blueprint_cells.question_count)'tur.
-- Türetilmiş olduğu için tutarsız olamaz ve spec.md:235'in saydığı hata sınıflarından
-- biri (tip toplamları adetle eşleşmiyor) tanımdan silinir.

-- ---------------------------------------------------------------------------
-- Dağılım hücreleri: (çıktı × zorluk × tip) → kaç soru, kaçar puan
-- ---------------------------------------------------------------------------
--
-- Neden JSONB değil: bu depo JSONB'yi iki gerekçeyle seçmiş — varyant şekil
-- (`questions.payload`) ve şemasız büyüyecek durum (`chat_sessions.state`). Hücre
-- ikisi de değil: sabit dört alanlı bir demet ve üzerinde TOPLAMA yapılıyor.
-- FR-114'ün "eksik hücreler" raporu tek SQL diff'ine iniyor; JSONB'de bu diff
-- Python'da elle üretilirdi ve UNIQUE ile çift hücre engellenemezdi.
--
-- Yüzdeler SAKLANMAZ: arayüz marjinal dağılım alır, API tam sayı hücrelere açar.
-- %40 × 7 = 2,8 ve yuvarlama kuralı saklanan veride görünmezse SC-003'ün "birebir
-- uyar" iddiası karar verilemez hâle gelir.

CREATE TABLE blueprint_cells (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Denormalize: izolasyon filtresi JOIN'e bağlı kalmaz (0004:3-11).
    course_id            uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    blueprint_id         uuid NOT NULL REFERENCES exam_blueprints(id) ON DELETE CASCADE,
    -- RESTRICT bilinçli: bir blueprint'te kullanılan öğrenme çıktısı silinemez.
    -- `questions.source_chunk_id` (0004:55) ile aynı gerekçe — dayanağı silinmiş bir
    -- kural, doğrulanamayan bir kuraldır.
    learning_outcome_id  uuid NOT NULL REFERENCES learning_outcomes(id) ON DELETE RESTRICT,
    difficulty           question_difficulty NOT NULL,
    question_type        question_type NOT NULL,
    question_count       smallint NOT NULL,
    points_per_question  smallint NOT NULL DEFAULT 1,
    CONSTRAINT blueprint_cells_count_range CHECK (question_count BETWEEN 1 AND 100),
    CONSTRAINT blueprint_cells_points_range CHECK (points_per_question BETWEEN 1 AND 100),
    -- Aynı hücre iki kez tanımlanamaz. FR-112'nin bir bölümünü uygulama koduna hiç
    -- sormadan kapatır.
    UNIQUE (blueprint_id, learning_outcome_id, difficulty, question_type)
);

CREATE INDEX blueprint_cells_blueprint_idx ON blueprint_cells (blueprint_id);

-- ---------------------------------------------------------------------------
-- Sınav sürümleri (yayınlanmış sınavın dondurulmuş hâli)
-- ---------------------------------------------------------------------------

CREATE TABLE exam_versions (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id           uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    blueprint_id        uuid NOT NULL REFERENCES exam_blueprints(id) ON DELETE CASCADE,
    version_no          smallint NOT NULL,
    status              exam_version_status NOT NULL DEFAULT 'draft',
    published_at        timestamptz,
    published_by        uuid REFERENCES profiles(id) ON DELETE SET NULL,
    superseded_at       timestamptz,
    -- Yayın anında kapının doğruladığı hücre kümesi (çıktı, zorluk, tip, adet, puan).
    -- Toplulaştırılmaz, bütün olarak okunur ve bir daha yazılmaz — `answers.feedback`
    -- sınıfından bir kanıt kaydı.
    blueprint_snapshot  jsonb,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT exam_versions_version_no_positive CHECK (version_no >= 1),
    UNIQUE (blueprint_id, version_no),
    -- `questions_reviewed_consistency` (0004:61-64) ile birebir aynı kalıp: durum ile
    -- damgalar birlikte tutarlı olmak zorundadır.
    CONSTRAINT exam_versions_publish_consistency CHECK (
           (status = 'draft'
                AND published_at IS NULL     AND published_by IS NULL
                AND superseded_at IS NULL    AND blueprint_snapshot IS NULL)
        OR (status = 'published'
                AND published_at IS NOT NULL AND published_by IS NOT NULL
                AND superseded_at IS NULL    AND blueprint_snapshot IS NOT NULL)
        OR (status = 'superseded'
                AND published_at IS NOT NULL
                AND superseded_at IS NOT NULL AND blueprint_snapshot IS NOT NULL)
    )
);

-- "Bir blueprint'in aynı anda tek yayınlanmış sürümü olur" kuralı YAPISALDIR;
-- uygulama koduna sorulmaz.
CREATE UNIQUE INDEX exam_versions_one_published
    ON exam_versions (blueprint_id) WHERE status = 'published';

CREATE INDEX exam_versions_blueprint_idx ON exam_versions (blueprint_id, version_no DESC);

-- ---------------------------------------------------------------------------
-- Sürüm kalemleri (kâğıdın sırası ve puanı)
-- ---------------------------------------------------------------------------

CREATE TABLE exam_items (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id        uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    exam_version_id  uuid NOT NULL REFERENCES exam_versions(id) ON DELETE CASCADE,
    position         smallint NOT NULL,
    -- RESTRICT: bir kalemde kullanılan soru silinemez.
    question_id      uuid NOT NULL REFERENCES questions(id) ON DELETE RESTRICT,
    -- `blueprint_cells.points_per_question`'dan YAYIN ANINDA kopyalanır. Gerekçe
    -- 0004:85-86 ile aynı ("oturum açılırken sorular burada sabitlenir"): blueprint
    -- sonradan düzenlense de yayınlanmış kâğıdın puanlaması değişmez.
    points           smallint NOT NULL,
    CONSTRAINT exam_items_position_positive CHECK (position >= 1),
    CONSTRAINT exam_items_points_range CHECK (points BETWEEN 1 AND 100),
    UNIQUE (exam_version_id, position),
    UNIQUE (exam_version_id, question_id)
);

CREATE INDEX exam_items_version_idx ON exam_items (exam_version_id, position);
CREATE INDEX exam_items_question_idx ON exam_items (question_id);

-- ---------------------------------------------------------------------------
-- `exam_sessions` — blueprint bağı
-- ---------------------------------------------------------------------------
--
-- İki akış yan yana yaşar:
--   exam_version_id IS NULL     → bugünkü self-servis prova; `question_ids` yetkili kaynak
--   exam_version_id IS NOT NULL → blueprint sınavı; kâğıt exam_items'tan ORDER BY position
--
-- `num_nonnulls(...) = 1` kısıtı "kâğıdın iki kaynağı olamaz"ı ifade edilemez kılar.
-- İkisini birden yazmak aynı gerçeği iki yere koymak olurdu ve bir sürüm geçişinde
-- ikisinin ayrışması SESSİZ olurdu (Anayasa XI).

ALTER TABLE exam_sessions
    ADD COLUMN exam_version_id   uuid REFERENCES exam_versions(id)   ON DELETE RESTRICT,
    ADD COLUMN exam_blueprint_id uuid REFERENCES exam_blueprints(id) ON DELETE RESTRICT,
    ADD COLUMN attempt_no smallint,
    ALTER COLUMN question_ids DROP NOT NULL,
    ADD CONSTRAINT exam_sessions_attempt_no_positive
        CHECK (attempt_no IS NULL OR attempt_no >= 1),
    ADD CONSTRAINT exam_sessions_paper_source
        CHECK (num_nonnulls(exam_version_id, question_ids) = 1),
    ADD CONSTRAINT exam_sessions_blueprint_pair CHECK (
        (exam_version_id IS NULL) = (exam_blueprint_id IS NULL)
        AND (exam_version_id IS NULL) = (attempt_no IS NULL)
    );

-- FR-111'in yeniden deneme politikasını YARIŞA DAYANIKLI kılar: uygulama
-- `max_attempts`'i kontrol eder, eşzamanlı ikinci istek unique ihlaline düşer ve
-- mevcut IntegrityError → ConflictError deseniyle 409'a çevrilir. NULL'lar tekil
-- indekste çakışmaz (PostgreSQL varsayılanı), bu yüzden mevcut satırlar birbirini
-- engellemez. 0004:115-117'nin bir üst granülaritede tekrarı.
CREATE UNIQUE INDEX exam_sessions_attempt_key
    ON exam_sessions (exam_blueprint_id, user_id, attempt_no);

CREATE INDEX exam_sessions_version_idx ON exam_sessions (exam_version_id);

-- ---------------------------------------------------------------------------
-- `documents` — kaynak sürümü (FR-118)
-- ---------------------------------------------------------------------------
--
-- TESPİT ÖNCE: bugün sürüm izi YOKTUR ve otomatik anlaşılamaz. `chunks`'ta sürüm
-- alanı yok; 0006'nın eklediği `embedding_space` sürüm izi değildir, vektör uzayı
-- kimliğidir. Değiştirilmiş bir dosya farklı hash taşır, yeni satır olarak girer ve
-- ikisi arasında hiçbir bağ kurulmaz. FR-118 veri eksikliğinden değil İLİŞKİ
-- eksikliğinden çalışmıyor.
--
-- Bağ AÇIK EYLEMLE kurulur, tahminle değil. Dosya adına bakarak otomatik eşleme
-- reddedildi: `file_name` üzerinde hiçbir tekillik yok, "hafta3.pdf" her dönem
-- yeniden yüklenir (yanlış pozitif) ve yeniden adlandırılmış bir güncelleme
-- yakalanmaz (yanlış negatif). Yanlış işaretlenen bir soru, öğretmenin işarete olan
-- güvenini bitirir; güvenilmez işaret, hiç işaret olmamasından kötüdür.
--
-- Bayatlık SAKLANMAZ, TÜRETİLİR (`questions.source_stale` gibi bir bayrak yok):
--   SELECT q.id FROM questions q
--     JOIN chunks c    ON c.id = q.source_chunk_id
--     JOIN documents d ON d.id = c.document_id
--    WHERE q.course_id = :course AND d.superseded_at IS NOT NULL;

ALTER TABLE documents
    ADD COLUMN supersedes_document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
    ADD COLUMN superseded_at timestamptz;

CREATE INDEX documents_superseded_idx ON documents (course_id) WHERE superseded_at IS NOT NULL;

-- ---------------------------------------------------------------------------
-- `app` yardımcıları
-- ---------------------------------------------------------------------------
--
-- İkisi de yalnız BOOLEAN döndürür, satır sızdırmaz — `app.is_member` ile birebir
-- aynı gerekçe (0001:83-85): politika içinden başka bir RLS'li tabloya SELECT atmak
-- iki tablonun politikalarını birbirine bağlar ve ilerideki bir politika değişikliği
-- bu bağı sessizce bozar.
--
-- Zaman kaynağı `now()`, yani İŞLEMİN VERİTABANI SAATİ; istemci saatine güvenilmez
-- (0004:80-82'nin kuralı).

-- İki argümanlıdır çünkü iki çağrı yeri de ders eşleşmesini ister: `exam_versions_read`
-- ve `exam_sessions_self_insert`. Tek imza, kuralın tek yerde yaşamasını sağlar.
CREATE OR REPLACE FUNCTION app.is_exam_open(p_version_id uuid, p_course_id uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, app AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.exam_versions v
        JOIN public.exam_blueprints b ON b.id = v.blueprint_id
        WHERE v.id = p_version_id
          AND v.course_id = p_course_id
          AND v.status = 'published'
          AND (b.opens_at  IS NULL OR b.opens_at <= now())
          AND (b.closes_at IS NULL OR now() < b.closes_at)
    )
$$;

-- `exam_blueprints_read` için gerekir. İkinci bir fonksiyon açmanın sebebi, blueprint
-- politikasının `exam_versions`'a doğrudan EXISTS atmasını önlemektir.
CREATE OR REPLACE FUNCTION app.blueprint_open_to_students(p_blueprint_id uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, app AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.exam_versions v
        JOIN public.exam_blueprints b ON b.id = v.blueprint_id
        WHERE v.blueprint_id = p_blueprint_id
          AND v.status = 'published'
          AND (b.opens_at  IS NULL OR b.opens_at <= now())
          AND (b.closes_at IS NULL OR now() < b.closes_at)
    )
$$;

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------

ALTER TABLE learning_outcomes  ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_blueprints    ENABLE ROW LEVEL SECURITY;
ALTER TABLE blueprint_cells    ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_versions      ENABLE ROW LEVEL SECURITY;
ALTER TABLE exam_items         ENABLE ROW LEVEL SECURITY;

ALTER TABLE learning_outcomes  FORCE ROW LEVEL SECURITY;
ALTER TABLE exam_blueprints    FORCE ROW LEVEL SECURITY;
ALTER TABLE blueprint_cells    FORCE ROW LEVEL SECURITY;
ALTER TABLE exam_versions      FORCE ROW LEVEL SECURITY;
ALTER TABLE exam_items         FORCE ROW LEVEL SECURITY;

-- learning_outcomes: `topics`'in birebir kopyası (0004:158-166), tek farkla —
-- UPDATE'e WITH CHECK de yazılıyor. Yazılmazsa PostgreSQL güncellenen satır için
-- USING'i kullanır ve satırın BAŞKA BİR DERSE TAŞINMASINI engellemez (0003:16-18).
CREATE POLICY learning_outcomes_member_read ON learning_outcomes
    FOR SELECT USING (app.is_member(course_id));
CREATE POLICY learning_outcomes_instructor_write ON learning_outcomes
    FOR INSERT WITH CHECK (app.is_instructor(course_id));
CREATE POLICY learning_outcomes_instructor_update ON learning_outcomes
    FOR UPDATE USING (app.is_instructor(course_id))
    WITH CHECK (app.is_instructor(course_id));
CREATE POLICY learning_outcomes_instructor_delete ON learning_outcomes
    FOR DELETE USING (app.is_instructor(course_id));

-- exam_blueprints: okuma politikası `questions_read`'in (0004:168-174, dosyanın "EN
-- KRİTİK politika" dediği satırlar) YAPISAL İKİZİDİR — eğitmen hepsini görür, üye
-- yalnız serbest bırakılmış alt kümeyi görür. Orada serbest bırakan şey
-- status='approved', burada "yayınlanmış sürüm + açık pencere". Böylece spec
-- senaryo 1 (taslak blueprint öğrenciye görünmez) ve FR-116 aynı politikayla karşılanır.
CREATE POLICY exam_blueprints_read ON exam_blueprints
    FOR SELECT USING (
        app.is_instructor(course_id)
        OR (app.is_member(course_id) AND app.blueprint_open_to_students(id))
    );
CREATE POLICY exam_blueprints_instructor_insert ON exam_blueprints
    FOR INSERT WITH CHECK (app.is_instructor(course_id));
CREATE POLICY exam_blueprints_instructor_update ON exam_blueprints
    FOR UPDATE USING (app.is_instructor(course_id))
    WITH CHECK (app.is_instructor(course_id));
CREATE POLICY exam_blueprints_instructor_delete ON exam_blueprints
    FOR DELETE USING (app.is_instructor(course_id));

-- blueprint_cells: ÖĞRENCİYE SELECT POLİTİKASI BİLEREK YOKTUR. "Bu sınavda 2 zor
-- açık uçlu var" bilgisi sınav öncesi istihbarattır. Kapalı doğup gerekirse
-- gerekçesiyle açmak deponun yazılı alışkanlığıdır: `request_logs` 0003'te tamamen
-- kapatıldı, 0005'te dar bir kapsamla açıldı (0005:3-13).
--
-- UPDATE politikası da yoktur ve yetki de çekilir (aşağıda). Hücre kümesi bütün
-- olarak DELETE+INSERT ile değişir; gerekçe: FR-112 doğrulaması KÜME üzerinde yapılır
-- ve tek hücrelik bir UPDATE doğrulamayı atlayıp tutarsız bir dağılım bırakabilirdi.
CREATE POLICY blueprint_cells_instructor_read ON blueprint_cells
    FOR SELECT USING (app.is_instructor(course_id));
CREATE POLICY blueprint_cells_instructor_insert ON blueprint_cells
    FOR INSERT WITH CHECK (app.is_instructor(course_id));
CREATE POLICY blueprint_cells_instructor_delete ON blueprint_cells
    FOR DELETE USING (app.is_instructor(course_id));

-- exam_versions: üçüncü OR dalı FR-115'in OKUMA AYAĞIDIR — pencere kapansa da yürüyen
-- oturumun sahibi kendi sürümünü görmeye devam eder. FR-116 "kapandığında YENİ oturum
-- başlatamaz" der, başlamışı düşürmez. Dal, `answers_self_read`'in (0004:197-204)
-- EXISTS kalıbının aynısıdır ve `exam_sessions_self_read` sayesinde kullanıcı kendi
-- oturumunu zaten görebildiği için ek bir SECURITY DEFINER yardımcısı gerektirmez.
CREATE POLICY exam_versions_read ON exam_versions
    FOR SELECT USING (
        app.is_instructor(course_id)
        OR (app.is_member(course_id) AND app.is_exam_open(id, course_id))
        OR EXISTS (
            SELECT 1 FROM exam_sessions s
            WHERE s.exam_version_id = exam_versions.id
              AND s.user_id = app.current_user_id()
        )
    );
CREATE POLICY exam_versions_instructor_insert ON exam_versions
    FOR INSERT WITH CHECK (app.is_instructor(course_id));
CREATE POLICY exam_versions_instructor_update ON exam_versions
    FOR UPDATE USING (app.is_instructor(course_id))
    WITH CHECK (app.is_instructor(course_id));
-- Yayınlanmış bir sürüm SİLİNEMEZ: silinseydi ona bağlı oturumların kanıtı yok
-- olurdu. `exam_sessions.exam_version_id` RESTRICT ile de kapalı; iki katman.
CREATE POLICY exam_versions_instructor_delete ON exam_versions
    FOR DELETE USING (app.is_instructor(course_id) AND status = 'draft');

-- exam_items: öğrenci kâğıdı ancak O SÜRÜMDE OTURUMU VARSA görür. Pencereye
-- bağlanmadı — zil çaldığında yürüyen öğrencinin kâğıdı ekrandan silinmemelidir.
--
-- INSERT/DELETE'teki status='draft' koşulu FR-115'in YAPISAL ayağıdır: UPDATE yetkisi
-- hiç verilmediği ve yayınlanmış sürüme kalem eklenip çıkarılamadığı için,
-- yayınlanmış bir kâğıdın soru listesi hiçbir kod yolundan değiştirilemez.
--
-- INSERT'teki `v.course_id = exam_items.course_id` koşulu `answers_self_insert`'in
-- (0004:205-217) üçlü kontrolüdür: denormalize course_id taşıyan satıra sahte bir
-- ders kimliği iliştirilmesini engeller.
CREATE POLICY exam_items_read ON exam_items
    FOR SELECT USING (
        app.is_instructor(course_id)
        OR EXISTS (
            SELECT 1 FROM exam_sessions s
            WHERE s.exam_version_id = exam_items.exam_version_id
              AND s.user_id = app.current_user_id()
        )
    );
CREATE POLICY exam_items_instructor_insert ON exam_items
    FOR INSERT WITH CHECK (
        app.is_instructor(course_id)
        AND EXISTS (
            SELECT 1 FROM exam_versions v
            WHERE v.id = exam_items.exam_version_id
              AND v.course_id = exam_items.course_id
              AND v.status = 'draft'
        )
    );
CREATE POLICY exam_items_instructor_delete ON exam_items
    FOR DELETE USING (
        app.is_instructor(course_id)
        AND EXISTS (
            SELECT 1 FROM exam_versions v
            WHERE v.id = exam_items.exam_version_id AND v.status = 'draft'
        )
    );

-- FR-116'nın İKİNCİ KATMANI. 0004'ün iki koşulu (user_id + is_member) AYNEN korunur;
-- yalnız üçüncü koşul eklenir. `exam_sessions_self_update` politikasına (0004:191-193)
-- DOKUNULMAZ — o politika bir PR incelemesinde kapatılmış gerçek bir açığın yamasıdır
-- ve yeniden yazılırsa koşullarından biri düşebilir.
DROP POLICY exam_sessions_self_insert ON exam_sessions;
CREATE POLICY exam_sessions_self_insert ON exam_sessions
    FOR INSERT WITH CHECK (
        user_id = app.current_user_id()
        AND app.is_member(course_id)
        AND (exam_version_id IS NULL OR app.is_exam_open(exam_version_id, course_id))
    );

-- ---------------------------------------------------------------------------
-- GRANT / REVOKE — bu göçün en kolay unutulan bölümü
-- ---------------------------------------------------------------------------
--
-- 0001:313 ve :315-316 tüm mevcut VE GELECEK tablolara `dou_app` / `dou_worker` için
-- SELECT, INSERT, UPDATE, DELETE verir. Yani aşağıdakiler açıkça yazılmazsa yeni
-- tablolar TAM YAZILABİLİR DOĞAR ve FR-115'in yapısal ayağı hiç kurulmamış olur.
--
-- Bu, 0007:43'ün cümlesinin uygulanmasıdır: "RLS satır düzeyinde çalışır, SÜTUN
-- kısıtı veremez — bu yüzden kolon bazlı GRANT."
--
-- SESSİZ KALABİLECEK HATA: bu satırlar unutulursa hiçbir test kırmızı yanmaz, çünkü
-- uygulama kodu zaten doğru davranıyordur. Bu yüzden "kalem listesi güncellenemez" ve
-- "hücre güncellenemez" için YETKİYİ DOĞRUDAN sınayan ayrı testler yazıldı
-- (`tests/test_blueprint_grants.py`).

REVOKE UPDATE ON exam_items, blueprint_cells FROM dou_app;

-- Dört kolon yayın akışının yazdığı alanlar, beşincisi (`blueprint_snapshot`) yayın
-- anındaki dağılım kanıtı. Kısıt bunların hepsini `published` için NOT NULL istiyor ve
-- satır `draft` doğuyor, yani UPDATE ile yazılmak zorundalar.
-- `blueprint_id`, `version_no`, `course_id` yazılamaz kalır — kâğıdın kimliği değişmez.
REVOKE UPDATE ON exam_versions FROM dou_app;
GRANT  UPDATE (status, published_at, published_by, superseded_at, blueprint_snapshot)
    ON exam_versions TO dou_app;

-- `dou_worker` yetkileri ÇEKİLMİYOR: worker bu tabloların hiçbirine dokunmaz, ama
-- 0001'in verdiği varsayılanı burada daraltmak, ilgisiz bir rolü ilgisiz bir
-- gerekçeyle değiştirmek olurdu.
--
-- KABUL EDİLEN ARTIK RİSK (0003:213-217'nin üslubuyla): `blueprint_cells`'e UPDATE
-- yetkisi yoktur ama INSERT/DELETE vardır; dolayısıyla dağılımın "küme olarak
-- doğrulanmış" olması UYGULAMA KATMANININ garantisidir, veritabanınınki değil.
-- Veritabanı yalnız "aynı hücre iki kez tanımlanamaz" ve "sayılar aralıkta" der. Bu
-- kabul edilebilir çünkü kullanıcıların doğrudan veritabanı kimliği yoktur; tek yol API'dir.

COMMIT;
