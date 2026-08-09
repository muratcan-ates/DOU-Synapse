import type { LabelSpec } from "@/lib/labels";

export type EvidenceLevel = "sufficient" | "weak" | "out_of_scope";

export interface RetrievalCandidate {
  rank: number;
  chunk_id: string;
  document_id: string;
  file_name: string;
  location: string;
  text: string;
  dense_score: number;
  fts_score: number;
  fused_score: number;
}

export interface RetrievalInspection {
  query: string;
  level: EvidenceLevel;
  answer_allowed: boolean;
  threshold: number;
  best_dense_score: number;
  best_fts_score: number;
  lexical_coverage: number;
  candidate_count: number;
  candidates: RetrievalCandidate[];
}

export interface SourceContextChunk {
  id: string;
  chunk_index: number;
  page_number: number | null;
  slide_number: number | null;
  section_title: string | null;
  content_type: "text" | "table" | "code";
  token_count: number;
  text: string;
  selected: boolean;
}

export interface SourceContext {
  document_id: string;
  file_name: string;
  selected_chunk_id: string;
  chunks: SourceContextChunk[];
}

export const EVIDENCE_LEVEL: Record<EvidenceLevel, LabelSpec & { explanation: string }> = {
  sufficient: {
    label: "Yanıt üretilebilir",
    tone: "success",
    explanation: "En iyi anlamsal eşleşme dersin kanıt eşiğini geçti.",
  },
  weak: {
    label: "Kanıt zayıf",
    tone: "warning",
    explanation: "Soru dersle ilişkili görünüyor ancak getirilen parçalar yeterince güçlü değil.",
  },
  out_of_scope: {
    label: "Kapsam dışında",
    tone: "neutral",
    explanation: "Getirilen parçalarda sorguyu ders kapsamına bağlayan yeterli sinyal yok.",
  },
};

export function sourceContextHref(courseId: string, chunkId: string): string {
  return `/courses/${encodeURIComponent(courseId)}/sources/${encodeURIComponent(chunkId)}`;
}

export function formatRetrievalScore(value: number): string {
  return Number.isFinite(value) ? value.toFixed(4) : "—";
}
