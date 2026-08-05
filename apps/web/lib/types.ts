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
