"use client";

/**
 * Hızlı tekrar kartları.
 *
 * Deste, öğrencinin **kendi tamamladığı** alıştırma oturumundan kurulur; iki
 * mevcut uç yeter ve yeni bir yetki açılmaz:
 *
 *   GET /courses/{id}/exams/history        → hangi oturumlar bitmiş
 *   GET /courses/{id}/exams/{sid}          → kart önü (soru + şıklar, cevapsız)
 *   GET /courses/{id}/exams/{sid}/results  → kart arkası (puan, kaynak, çözüm)
 *
 * Neden soru havuzundan değil: havuz ucu öğrenciye cevap anahtarını vermiyor
 * (`public_payload` beyaz listesi) ve bu bilinçli bir sınav bütünlüğü kararı.
 * Gerekçenin tamamı `lib/cards.ts` başlığında.
 *
 * Sınav kilidi: sunucu `exam_results` içinde `_require_help_unlocked` ile zaten
 * kapatıyor. Ekran kilidi ayrıca okur ki öğrenci hata zarfı yerine sebebini
 * görsün — kapı sunucuda, bu yalnız kullanıcıyı duvara koşturmamak için.
 */

import { useCallback, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { buildDeck } from "@/lib/cards";
import { examDate, formatScore, SCORE_SCALE } from "@/lib/exam";
import type { ExamFinish, ExamSession, Page } from "@/lib/types";
import { useChatAvailability, type ChatLock } from "@/lib/chat-availability";
import { useResource } from "@/lib/use-resource";
import { useSession } from "@/lib/session";
import { AppShell } from "@/components/app-shell";
import { CardDeck } from "@/components/cards/card-deck";
import { CourseNav } from "@/components/course-nav";
import { Field } from "@/components/field";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Card, EmptyState, Select } from "@/components/ui";

export default function CardsPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const identity = useSession();
  const helpLock = useChatAvailability(courseId);
  return (
    <AppShell>
      <CourseNav courseId={courseId} lock={helpLock} />
      {!identity.ready || !identity.user ? (
        <Loading />
      ) : (
        <CardsScreen
          key={`${courseId}:${identity.user.id}`}
          courseId={courseId}
          helpLock={helpLock}
        />
      )}
    </AppShell>
  );
}

function oturumEtiketi(session: ExamSession): string {
  const score = formatScore(session.score);
  const tarih = examDate(session.finished_at ?? session.started_at);
  const soru = `${session.answered_count}/${session.question_count} soru`;
  return score === null ? `${tarih} · ${soru}` : `${tarih} · ${soru} · ${score}/${SCORE_SCALE}`;
}

function CardsScreen({ courseId, helpLock }: { courseId: string; helpLock: ChatLock }) {
  const [selected, setSelected] = useState<string | null>(null);

  const fetchHistory = useCallback(
    () => api.get<Page<ExamSession>>(`/courses/${courseId}/exams/history`),
    [courseId],
  );
  const history = useResource(fetchHistory, [courseId]);

  /*
   * Bitmiş oturumlar. Süresi dolmuş ama bitirilmemiş oturumun sonucu yoktur:
   * `exam_results` onu `ConflictError` ile reddeder, bu yüzden listeye hiç
   * girmez — açılmayacak bir seçeneği menüye koymak kullanıcıyı hataya yollar.
   */
  const finished = useMemo(
    () => (history.data?.items ?? []).filter((session) => session.finished_at !== null),
    [history.data],
  );
  const sessionId = selected ?? finished[0]?.id ?? null;

  const fetchDeck = useCallback(async () => {
    if (sessionId === null) return null;
    // Sıra önemli değil ama iki isteği paralel açmak bir tur RTT kazandırır.
    const [session, results] = await Promise.all([
      api.get<ExamSession>(`/courses/${courseId}/exams/${sessionId}`),
      api.get<ExamFinish>(`/courses/${courseId}/exams/${sessionId}/results`),
    ]);
    return { session, results };
  }, [courseId, sessionId]);
  const deck = useResource(fetchDeck, [courseId, sessionId]);

  /*
   * `cards` referansı sabit olmalı: `CardDeck` deste değişiminde durumu
   * sıfırlıyor ve her render'da yeni dizi gelseydi öğrencinin kararları
   * kaybolurdu.
   */
  const cards = useMemo(
    () => (deck.data ? buildDeck(deck.data.session, deck.data.results.results ?? []) : []),
    [deck.data],
  );

  const header = (
    <PageHeader
      title="Hızlı tekrar"
      description="Tamamladığın alıştırmalardan kart destesi. Kartlar puanlanmaz; yalnız nereye döneceğini gösterir."
    />
  );

  if (helpLock.locked) {
    return (
      <>
        {header}
        <EmptyState title={helpLock.message ?? "Yürüyen bir sınav varken tekrar kartları kapalıdır."} />
      </>
    );
  }

  if (history.loading) return <>{header}<Loading /></>;
  if (history.error) return <>{header}<ErrorNote message={history.error} onRetry={history.reload} /></>;

  if (finished.length === 0) {
    return (
      <>
        {header}
        <EmptyState title="Henüz tamamlanmış bir alıştırma yok. Sınav provası sekmesinden bir alıştırma çöz; kartlar kendi cevaplarından kurulur." />
      </>
    );
  }

  return (
    <>
      {header}

      {/* Tek oturum varsa seçici çizilmez: seçeneksiz bir menü karar varmış gibi görünür. */}
      {finished.length > 1 && (
        <Card className="mb-6">
          <Field label="Hangi alıştırma">
            {(control) => (
              <Select
                {...control}
                value={sessionId ?? ""}
                onChange={(event) => setSelected(event.target.value)}
              >
                {finished.map((session) => (
                  <option key={session.id} value={session.id}>
                    {oturumEtiketi(session)}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        </Card>
      )}

      {deck.loading ? (
        <Loading />
      ) : deck.error ? (
        <ErrorNote message={deck.error} onRetry={deck.reload} />
      ) : sessionId === null ? null : (
        <>
          {deck.refreshError && <ErrorNote message={deck.refreshError} onRetry={deck.reload} />}
          <CardDeck key={sessionId} courseId={courseId} sessionId={sessionId} cards={cards} />
        </>
      )}
    </>
  );
}
