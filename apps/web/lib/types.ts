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
