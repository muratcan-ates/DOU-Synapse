/** Backend şemalarıyla birebir sözleşmeler (apps/api/app/schemas). */

export interface Course {
  id: string;
  code: string;
  title: string;
  created_at: string;
  role: "instructor" | "student";
}

export type DocumentStatus = "uploaded" | "processing" | "completed" | "failed";

export interface CourseDocument {
  id: string;
  file_name: string;
  file_type: string;
  byte_size: number;
  status: DocumentStatus;
  page_count: number | null;
  chunk_count: number;
  error_message: string | null;
  supersedes_document_id?: string | null;
  superseded_at?: string | null;
  created_at: string;
}

export interface ChunkPreview {
  id: string;
  chunk_index: number;
  page_number: number | null;
  slide_number: number | null;
  section_title: string | null;
  content_type: "text" | "table" | "code";
  token_count: number;
  text: string;
}

export interface Member {
  user_id: string;
  email: string;
  full_name: string | null;
  role: "instructor" | "student";
  status: "active" | "revoked";
}

// --- Sohbet (T021) — backend `app/schemas/chat.py` ile birebir ---------------

export type AnswerStatus =
  | "answered"
  | "insufficient_context"
  | "out_of_scope"
  | "budget_exhausted";
export type ChatMode = "qa" | "socratic" | "exam";
export type SocraticStage =
  | "diagnose"
  | "nudge"
  | "concept_hint"
  | "similar_example"
  | "explain_with_source";

export interface Citation {
  chunk_id: string;
  /** Atıfın hangi iddiayı desteklediği — sunum verisi, guardrail buna bakmaz. */
  claim: string;
  file_name: string;
  /** "Sayfa 7" · "Slayt 3" — chunk metadata'sından üretilir, model metninden değil. */
  location: string;
  snippet: string;
}

/**
 * Sokratik ipucu. Kaynaksız ipucu istemciye HİÇ ulaşmaz (FR-013/FR-016), bu yüzden
 * `chunk_id`/`file_name`/`location` opsiyonel değildir — arayüz kaynağı her zaman
 * gösterebilir.
 */
export interface Hint {
  text: string;
  chunk_id: string;
  file_name: string;
  location: string;
  stage: SocraticStage | null;
}

export interface ChatAnswer {
  session_id: string;
  message_id: string;
  status: AnswerStatus;
  mode: ChatMode;
  answer: string;
  citations: Citation[];
  hints: Hint[];
  socratic_stage: SocraticStage | null;
  /** Cevap birebir eşleşmeli önbellekten geldi mi (FR-034). */
  cached: boolean;
}

export interface ChatRequest {
  question: string;
  mode: ChatMode;
  session_id?: string;
  /**
   * Sokratik modda öğrencinin bu turdaki denemesi; ipucu buna göre şekillenir.
   *
   * Sokratik turlarda `question` OTURUMU AÇAN soru olarak tekrar gönderilir ve
   * yeni yazılan metin buraya konur. Sebep sunucuda: arama açılış sorusuna bağlı
   * kalmalı, yoksa "hı" gibi bir denemeyle yapılan arama hiçbir parça bulmaz ve
   * merdiven kanıt eşiğine takılıp çöker.
   */
  student_attempt?: string;
}

export type ChatRole = "user" | "assistant";

/** Oturum geçmişindeki tek mesaj (`GET /chat/sessions/{id}`). */
export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  citations: Citation[];
  status: AnswerStatus | null;
  socratic_stage: SocraticStage | null;
  created_at: string;
}

export interface ChatSessionSummary {
  id: string;
  course_id: string;
  mode: ChatMode;
  title: string | null;
  socratic_stage: SocraticStage | null;
  created_at: string;
  updated_at: string;
}

// --- Değerlendirme: soru havuzu + sınav (Şerit 4) ---------------------------
//
// Backend `app/schemas/assessment.py` ile birebir; kaynak openapi.json.
// `payload` bilinçli olarak `unknown` değil dar tiplerle modellenmiyor: soru
// tipine göre şekli değişiyor ve backend onu jsonb olarak taşıyor. Arayüz
// `question_type`'a bakıp daraltır (bkz. `isMcqPayload` vb. yardımcılar).

export type ExamMode = "practice" | "exam";
export type QuestionType = "mcq" | "open" | "code_trace" | "bug_hunt";
export type QuestionStatus = "draft" | "approved" | "rejected";
export type AnswerFormat = "essay" | "short_answer";
export type QuestionDifficulty = "easy" | "medium" | "hard";

/**
 * Kaynak referansı. `file_name`/`location`/`snippet` chunk metadata'sından gelir,
 * model metninden ÜRETİLMEZ (Anayasa I) — arayüz bunları olduğu gibi gösterir.
 */
export interface SourceRef {
  chunk_id: string;
  file_name: string;
  location: string;
  snippet: string;
}

export interface Topic {
  id: string;
  course_id: string;
  name: string;
  created_by: string;
  created_at: string;
}

export interface Question {
  id: string;
  course_id: string;
  topic_id: string;
  learning_outcome_id?: string | null;
  difficulty?: QuestionDifficulty | null;
  type: QuestionType;
  /** Soru tipine göre şekil değişir; daraltma arayüzün işi. */
  payload: Record<string, unknown>;
  status: QuestionStatus;
  created_by: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  created_at: string;
  source?: SourceRef | null;
  source_stale?: boolean;
}

export interface QuestionGenerateRequest {
  topic_id: string;
  learning_outcome_id?: string | null;
  difficulty?: QuestionDifficulty | null;
  question_type?: QuestionType;
  answer_format?: AnswerFormat | null;
  count?: number | null;
  example_questions?: string[];
}

/**
 * Üretim turunun dürüst muhasebesi: istenen, dönen, kabul edilen, reddedilen.
 * `rejected` sıfırdan büyükse sebepleri `rejection_reasons`'ta — bunlar
 * gizlenmez, eğitmen neyin neden elendiğini görür (Anayasa III).
 */
export interface QuestionGeneration {
  requested: number;
  returned: number;
  accepted: number;
  rejected: number;
  rejection_reasons?: string[];
  questions?: Question[];
}

export interface ExamQuestion {
  id: string;
  type: QuestionType;
  payload: Record<string, unknown>;
  answered: boolean;
}

export interface ExamSession {
  id: string;
  course_id: string;
  mode: ExamMode;
  started_at: string;
  expires_at: string | null;
  /** Kalan süre SUNUCUDAN gelir; istemci saatine güvenilmez. */
  remaining_seconds: number | null;
  expired: boolean;
  finished_at: string | null;
  score: number | null;
  question_count: number;
  answered_count: number;
  questions?: ExamQuestion[];
  exam_version_id?: string | null;
  exam_blueprint_id?: string | null;
  attempt_no?: number | null;
}

export interface ExamStartRequest {
  mode?: ExamMode;
  topic_id?: string | null;
  blueprint_id?: string | null;
}

export interface AnswerSubmitRequest {
  question_id: string;
  given: string;
  hint_level?: number;
}

/**
 * Tek cevabın geri bildirimi.
 *
 * `graded` false olabilir (açık uçlu cevap LLM'e gidemediyse): o durumda
 * `is_correct` ve `score` null'dır ve arayüz **puan uydurmaz** — "değerlendirilemedi"
 * der. `why_wrong` ve `evidence` kaynaklıdır; kaynaksız açıklama gösterilmez.
 */
export interface AnswerFeedback {
  question_id: string;
  recorded?: boolean;
  graded: boolean;
  is_correct?: boolean | null;
  score?: number | null;
  missing_points?: string[];
  rubric_breakdown?: RubricScore[] | null;
  why_wrong?: SourceRef | null;
  evidence?: SourceRef | null;
  solution?: Record<string, unknown> | null;
  message?: string | null;
}

export interface RubricScore {
  criterion: string;
  weight: number;
  score: number;
  awarded_points: number;
}

// --- Sınav blueprint'i (002 US3) -----------------------------------------

export interface LearningOutcome {
  id: string;
  code: string;
  description: string;
  topic_id: string | null;
  created_at: string;
}

export interface BlueprintCell {
  id: string;
  learning_outcome_id: string;
  difficulty: QuestionDifficulty;
  question_type: QuestionType;
  question_count: number;
  points_per_question: number;
  label: string;
}

export interface BlueprintTopicShare {
  topic_id: string | null;
  topic_name: string | null;
  question_count: number;
}

export interface ExamBlueprint {
  id: string;
  course_id: string;
  title: string;
  description: string | null;
  duration_minutes: number;
  max_attempts: number;
  opens_at: string | null;
  closes_at: string | null;
  created_at: string;
  updated_at: string;
  cells: BlueprintCell[];
  total_questions: number;
  total_points: number;
  topic_distribution: BlueprintTopicShare[];
  published_version_no: number | null;
}

export interface ExamVersion {
  id: string;
  blueprint_id: string;
  version_no: number;
  status: "draft" | "published" | "superseded";
  published_at: string | null;
  superseded_at: string | null;
  created_at: string;
  item_count: number;
  total_points: number;
}

export interface ExamItem {
  id: string;
  position: number;
  question_id: string;
  points: number;
  question_type: QuestionType;
  difficulty: QuestionDifficulty | null;
  learning_outcome_id: string | null;
  stem: string;
}

export interface BlueprintReadiness {
  ready: boolean;
  missing_cells: Array<{
    learning_outcome_id: string;
    difficulty: QuestionDifficulty;
    question_type: QuestionType;
    required: number;
    filled: number;
    label: string;
  }>;
  unclassified_items: Array<{
    question_id: string;
    position: number;
    missing_fields: string[];
    label: string;
  }>;
  message: string;
}

export interface ExamFinish {
  session_id: string;
  score: number | null;
  answered_count: number;
  unanswered_count: number;
  /** Değerlendirilemeyen cevap sayısı — puanın paydası bu kadar eksik. */
  ungraded_count: number;
  message: string;
  results?: AnswerFeedback[];
}

export interface ExamHintRequest {
  question_id: string;
  hint_level?: number;
}

export interface ExamHint {
  question_id: string;
  hint_level: number;
  text: string;
  source: SourceRef;
}

// --- Analitik (Şerit 5) -----------------------------------------------------

export type MasteryLevel = "needs_work" | "medium" | "good";

export interface TopicProgress {
  topic_id: string;
  name: string;
  score: number;
  level: MasteryLevel;
  answer_count: number;
}

export interface ClassTopicProgress {
  topic_id: string;
  name: string;
  average_score: number;
  level: MasteryLevel;
  student_count: number;
  answer_count: number;
}

export interface MissedQuestion {
  question_id: string;
  topic_name: string;
  stem: string;
  wrong_rate: number;
  graded_answer_count: number;
}

/**
 * Kapsam dışı ret istatistiği.
 *
 * `rate` null olabilir — kaynak veri yoksa oran UYDURULMAZ. `note` neden
 * ölçülemediğini Türkçe anlatır ve arayüz o cümleyi gösterir.
 */
export interface OutOfScopeStat {
  source: "request_logs";
  rate: number | null;
  out_of_scope_count: number;
  insufficient_context_count: number;
  answered_request_count: number;
  note: string;
}

/**
 * Öğrencinin kendi ilerlemesi.
 *
 * `untracked_topics`: hiç cevaplanmamış konular. Bunlar listede 0.0 skorla
 * GÖSTERİLMEZ — çalışılmamış bir konu "sıfır aldın" demek değildir.
 */
export interface StudentAnalytics {
  course_id: string;
  topics: TopicProgress[];
  average_score: number | null;
  tracked_topics: number;
  untracked_topics: number;
  needs_work_topics: number;
  answered_questions: number;
}

export interface ClassAnalytics {
  course_id: string;
  topics: ClassTopicProgress[];
  missed_questions: MissedQuestion[];
  average_score: number | null;
  tracked_topics: number;
  untracked_topics: number;
  student_count: number;
  answered_questions: number;
  out_of_scope: OutOfScopeStat;
}

/**
 * Asistanın bu kullanıcı için açık olup olmadığı.
 *
 * `reason` ve `message` sunucudan gelir; arayüz kilit metnini uydurmaz.
 * Kararın sahibi `GET /courses/{id}/chat/availability` ve aynı kararı
 * `POST /chat` de 403 ile uygular — iki yüzey tek fonksiyonu okur.
 */
export interface ChatAvailability {
  available: boolean;
  reason: string | null;
  message: string | null;
  allowed_modes: ChatMode[];
  hint_limit: number;
}
