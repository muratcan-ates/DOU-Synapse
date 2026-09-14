import { api } from "@/lib/api";

export type LearningSummaryDays = 7 | 30;

export interface TopicLearningSummary {
  topic_id: string | null;
  topic_name: string;
  wrong_answers: number;
  hints_requested: number;
  unsupported_refusals: number;
}

export interface LearningSummary {
  course_id: string;
  days: LearningSummaryDays;
  topics: TopicLearningSummary[];
  total_events: number;
}

export interface CitationLearningContext {
  courseId: string;
  chunkId: string;
  sessionId?: string | null;
}

export function getLearningSummary(courseId: string, days: LearningSummaryDays) {
  return api.get<LearningSummary>(`/courses/${courseId}/learning-summary?days=${days}`);
}

/** Kimlik, alıntı ve sohbet metni gönderilmez; ders ve oturum yetkisini sunucu doğrular. */
export function recordCitationOpened({ courseId, chunkId, sessionId }: CitationLearningContext) {
  return api.post<{ id: string }>(`/courses/${courseId}/learning-events/citation-opened`, {
    chunk_id: chunkId,
    session_id: sessionId ?? null,
  });
}
