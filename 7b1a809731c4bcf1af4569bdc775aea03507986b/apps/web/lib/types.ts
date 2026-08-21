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

export type AnswerStatus = "answered" | "insufficient_context" | "out_of_scope";
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
  claim: string | null;
  file_name: string;
  /** "Sayfa 7" · "Slayt 3" — chunk metadata'sından üretilir, model metninden değil. */
  location: string;
  snippet: string;
}

export interface ChatAnswer {
  session_id: string;
  message_id: string;
  status: AnswerStatus;
  mode: ChatMode;
  answer: string;
  citations: Citation[];
  hints: string[];
  socratic_stage: SocraticStage | null;
}

export interface ChatRequest {
  question: string;
  mode: ChatMode;
  session_id?: string;
  /** Sokratik modda öğrencinin bu turdaki denemesi; ipucu buna göre şekillenir. */
  student_attempt?: string;
}

export interface ChatSessionSummary {
  id: string;
  mode: ChatMode;
  title: string | null;
  created_at: string;
}
