"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { browserDraftStorage, removeExamDrafts } from "@/lib/exam-drafts";
import { examSessionKey, shouldPoll } from "@/lib/exam";
import type { ExamCatalog, ExamSession } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { useChatAvailability, type ChatLock } from "@/lib/chat-availability";
import { useSession } from "@/lib/session";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { ErrorNote, Loading } from "@/components/page-state";
import { StartPanel } from "@/components/exam/start-panel";
import { RunningExam } from "@/components/exam/running-exam";

export default function ExamPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const identity = useSession();
  const helpLock = useChatAvailability(courseId);
  return (
    <AppShell>
      <CourseNav courseId={courseId} lock={helpLock} />
      {!identity.ready || !identity.user ? <Loading /> : (
        <ExamScreen key={`${courseId}:${identity.user.id}`} courseId={courseId} userId={identity.user.id} helpLock={helpLock} />
      )}
    </AppShell>
  );
}

/** Yerel kayıt yalnız son seçimi hatırlar; geçmişin sahibi sunucudur. */
function ExamScreen({ courseId, userId, helpLock }: { courseId: string; userId: string; helpLock: ChatLock }) {
  const storageKey = examSessionKey(courseId, userId);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [restored, setRestored] = useState(false);
  useEffect(() => {
    setSessionId(localStorage.getItem(storageKey));
    setRestored(true);
  }, [storageKey]);

  const rememberSession = useCallback((id: string | null) => {
    if (id === null) localStorage.removeItem(storageKey);
    else localStorage.setItem(storageKey, id);
    setSessionId(id);
  }, [storageKey]);

  const fetchCatalog = useCallback(() => api.get<ExamCatalog>(`/courses/${courseId}/exams/catalog`), [courseId]);
  const catalog = useResource(fetchCatalog, [courseId, userId]);
  const fetchSession = useCallback(async (): Promise<{ session: ExamSession | null }> => {
    if (!restored || sessionId === null) return { session: null };
    try {
      return { session: await api.get<ExamSession>(`/courses/${courseId}/exams/${sessionId}`) };
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        localStorage.removeItem(storageKey);
        removeExamDrafts(browserDraftStorage(), { userId, courseId, sessionId });
        return { session: null };
      }
      throw error;
    }
  }, [courseId, userId, sessionId, restored, storageKey]);
  const exam = useResource(fetchSession, [courseId, userId, sessionId, restored], {
    pollWhile: (view) => view.session !== null && shouldPoll(view.session),
    intervalMs: 15000,
  });

  if (!restored || exam.loading || catalog.loading) return <Loading />;
  if (catalog.error) return <ErrorNote message={catalog.error} onRetry={catalog.reload} />;
  if (exam.error) return <ErrorNote message={exam.error} onRetry={exam.reload} />;
  if (exam.data === null || catalog.data === null) return <Loading />;
  const session = exam.data.session;

  if (session === null) return (
    <StartPanel courseId={courseId} catalog={catalog.data} onRefreshCatalog={catalog.reload} onStarted={rememberSession} />
  );
  return (
    <RunningExam key={session.id} courseId={courseId} userId={userId} session={session} helpLock={helpLock}
      refreshError={exam.refreshError} onReload={exam.reload}
      historyEnabled={catalog.data.enabled} onLeave={() => { rememberSession(null); void catalog.reload(); }} />
  );
}
