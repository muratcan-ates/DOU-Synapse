"use client";

/**
 * AI kalite — eğitmen görünümü.
 *
 * Kompozisyon analitik sayfasıyla aynı desendir (DESIGN.md "Modern akademik
 * stüdyo grameri"): tek odak kartı (gizlilik cümlesi + üç büyük sayı), altında
 * kompakt metrik şeridi (incelemeye açılan + gerekçe dağılımı), sonra paylaşılan
 * inceleme kuyruğu tek çerçeveli liste olarak. Dört eşit metrik sayfayı açmaz.
 *
 * "Henüz ölçülmedi" bir hata değildir: nötr rozetle söylenir, kırmızı/uyarı
 * tonuyla değil (DESIGN.md: abstention ve boşluk hata gibi görünmemeli).
 */

import { useCallback } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { FEEDBACK_REASON_LABEL } from "@/components/chat-feedback";
import { CourseNav } from "@/components/course-nav";
import { InstructorGate } from "@/components/instructor-gate";
import { ErrorNote, Loading, MetricRow, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, EmptyState } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { ChatFeedbackReason, ChatQuality } from "@/lib/types";
import { useResource } from "@/lib/use-resource";

export default function QualityPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isInstructor, ready } = useSession(courseId);

  return (
    <AppShell>
      <CourseNav courseId={courseId} />
      <InstructorGate
        ready={ready}
        isInstructor={isInstructor}
        fallback={<EmptyState title="Bu kalite görünümü yalnız dersin eğitmenine açıktır." />}
      >
        <QualityView courseId={courseId} />
      </InstructorGate>
    </AppShell>
  );
}

function QualityView({ courseId }: { courseId: string }) {
  const fetchQuality = useCallback(
    () => api.get<ChatQuality>(`/courses/${courseId}/chat/quality`),
    [courseId],
  );
  const { data, error, loading, reload } = useResource<ChatQuality>(fetchQuality, [courseId]);

  return (
    <>
      <PageHeader
        title="AI kalite"
        description="Öğrenci puanları ve yalnız açık izinle paylaşılan yanıt incelemeleri."
        action={
          <Button variant="secondary" onClick={() => void reload()}>
            Yenile
          </Button>
        }
      />

      {error && <ErrorNote message={error} onRetry={() => void reload()} />}
      {loading && <Loading label="Kalite ölçümleri yükleniyor…" />}

      {/* Gizlilik cümlesi veri gelmese de yerinde kalır; sayılar ona eklenir. */}
      <FocusCard data={data} />

      {data && (
        <>
          <ReasonBreakdown
            sharedCount={data.shared_review_count}
            counts={data.reason_counts}
          />
          <SharedReviews reports={data.recent_shared} />
        </>
      )}
    </>
  );
}

/**
 * Odak kartı: gizlilik ilkesi + üç büyük sayı.
 *
 * Sayılar sunucudan gelir; hiçbiri istemcide türetilmez. Puanlanan yanıt yoksa
 * "Henüz ölçülmedi" nötr rozettir — sıfır bir sorun değil, ölçümün henüz
 * başlamamış olmasıdır.
 */
function FocusCard({ data }: { data: ChatQuality | null }) {
  return (
    <Card className="mb-6">
      <p className="prose-tr max-w-[70ch] text-sm text-fg-muted">
        <span className="font-medium text-fg">Sohbetler varsayılan olarak özeldir.</span>{" "}
        Paylaşılmayan puanlar yalnız toplu sayılara girer. Aşağıdaki soru ve cevaplar,
        öğrenci tarafından özellikle öğretmen incelemesine açılmıştır.
      </p>
      {data && (
        <div className="mt-6 flex flex-wrap items-end gap-x-12 gap-y-6">
          <dl className="flex flex-wrap gap-x-12 gap-y-6">
            {[
              { value: data.rated_count, label: "Puanlanan yanıt" },
              { value: data.helpful_count, label: "Yararlı" },
              { value: data.unhelpful_count, label: "Sorun bildirilen" },
            ].map((figure) => (
              <div key={figure.label} className="flex flex-col-reverse gap-2">
                <dt className="text-xs font-medium text-fg-muted">{figure.label}</dt>
                <dd className="text-4xl leading-none font-semibold tracking-tight tabular-nums text-fg sm:text-5xl">
                  {figure.value}
                </dd>
              </div>
            ))}
          </dl>
          {data.rated_count === 0 && <Badge tone="neutral">Henüz ölçülmedi</Badge>}
        </div>
      )}
    </Card>
  );
}

/**
 * Kompakt metrik şeridi: incelemeye açılan yanıt sayısı + gerekçe dağılımı.
 *
 * Gerekçe sayıları da birer metriktir; ayrı bir kart açmak yerine şeride
 * eklenir (üç+ ilgisiz bölüm aynı kart kalıbında olmasın). Hiç gerekçe
 * bildirilmemişse bu ölçülmemiş bir şeydir, eksik bir şey değil: nötr rozet.
 */
function ReasonBreakdown({
  sharedCount,
  counts,
}: {
  sharedCount: number;
  counts: Partial<Record<ChatFeedbackReason, number>>;
}) {
  const rows = Object.entries(counts) as Array<[ChatFeedbackReason, number]>;
  return (
    <>
      <MetricRow
        items={[
          { value: sharedCount, label: "İncelemeye açılan" },
          ...rows.map(([reason, count]) => ({
            value: count,
            label: `Gerekçe: ${FEEDBACK_REASON_LABEL[reason]}`,
          })),
        ]}
      />
      {rows.length === 0 && (
        <div className="mb-6 flex flex-wrap items-center gap-3">
          <Badge tone="neutral">Gerekçe dağılımı ölçülmedi</Badge>
          <p className="text-xs text-fg-muted">
            Sorun bildiren öğrenci henüz gerekçe seçmedi.
          </p>
        </div>
      )}
    </>
  );
}

/**
 * Paylaşılan inceleme kuyruğu: tek çerçeveli liste (`Card flat` + satır
 * ayraçları). Her satır: öğrenci · zaman · gerekçe, altında soru ve yanıt
 * alıntıları, varsa öğrenci notu çukur yüzeyde.
 */
function SharedReviews({ reports }: { reports: ChatQuality["recent_shared"] }) {
  if (reports.length === 0) {
    return (
      <section>
        <h2 className="mb-3 text-sm font-medium text-fg">
          Paylaşılan inceleme kuyruğu
        </h2>
        <EmptyState title="Öğretmen incelemesine açılmış bir yanıt yok." />
      </section>
    );
  }
  return (
    <Card variant="flat" className="px-0 py-0">
      <div className="flex items-center justify-between gap-3 px-5 py-3">
        <h2 className="text-sm font-medium text-fg">Paylaşılan inceleme kuyruğu</h2>
        <span className="text-xs tabular-nums text-fg-muted">{reports.length} yanıt</span>
      </div>
      <ul className="divide-y divide-border border-t border-border">
        {reports.map((report) => (
          <li key={report.id} className="px-5 py-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-3">
                <p className="text-sm font-medium text-fg">{report.student_name}</p>
                <Badge tone="neutral">{FEEDBACK_REASON_LABEL[report.reason]}</Badge>
              </div>
              <p className="text-xs tabular-nums text-fg-subtle">
                {new Date(report.updated_at).toLocaleString("tr-TR")}
              </p>
            </div>
            {report.question_excerpt && (
              <div className="mt-4 border-l-2 border-border-strong pl-3">
                <p className="text-xs font-medium text-fg-subtle">Öğrencinin sorusu</p>
                <p className="prose-tr mt-1 text-sm text-fg">{report.question_excerpt}</p>
              </div>
            )}
            <div className="mt-4 border-l-2 border-border-strong pl-3">
              <p className="text-xs font-medium text-fg-subtle">Asistanın yanıtı</p>
              <p className="prose-tr mt-1 text-sm whitespace-pre-line text-fg">
                {report.answer_excerpt}
              </p>
            </div>
            {report.comment && (
              <p className="prose-tr mt-4 rounded-xl bg-surface-sunken px-4 py-3 text-sm text-fg-muted">
                Öğrenci notu: {report.comment}
              </p>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}
