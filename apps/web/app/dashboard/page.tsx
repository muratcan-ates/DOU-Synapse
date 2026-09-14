"use client";

import Link from "next/link";
import { useCallback } from "react";
import { AppShell } from "@/components/app-shell";
import { CourseAssistant } from "@/components/course-assistant/course-assistant";
import { BookIcon, ChevronRightIcon } from "@/components/icons";
import { PortalMetrics } from "@/components/portal/portal-metrics";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Badge, EmptyState } from "@/components/ui";
import {
  coursePrimaryHref,
  coursePrimaryLabel,
  courseQuickTools,
  getDashboard,
  instructorAttentionMessages,
  lastActivityLabel,
  masteryLabel,
  type DashboardCourse,
} from "@/lib/dashboard";
import { roleLabel } from "@/lib/profile";
import { useResource } from "@/lib/use-resource";

const SECONDARY_ACTION =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-border-strong bg-surface px-4 text-sm font-medium text-fg transition-colors hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
const PRIMARY_ACTION =
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-brand px-5 text-sm font-medium text-white shadow-e1 transition-colors hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand dark:text-bg";
const QUICK_LINK =
  "inline-flex min-h-11 items-center rounded-lg px-3 text-sm text-fg-muted transition-colors hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

export default function DashboardPage() {
  return <AppShell><DashboardContent /></AppShell>;
}

function DashboardContent() {
  const fetchDashboard = useCallback(() => getDashboard(), []);
  const { data, error, refreshError, errorKind, errorRequestId, loading, reload } =
    useResource(fetchDashboard, []);

  if (error) {
    return <ErrorNote message={error} kind={errorKind} requestId={errorRequestId} onRetry={reload} />;
  }
  if (loading || !data) return <Loading label="Çalışma alanınız hazırlanıyor…" />;

  const firstName = data.viewer.full_name?.trim().split(/\s+/)[0] ?? "";
  const focusCourse = data.courses[0] ?? null;

  return (
    <div className="space-y-7">
      <PageHeader
        title={firstName ? `Merhaba, ${firstName}` : "Genel bakış"}
        description="Bugün hangi dersten devam etmek istersiniz?"
        action={<Link href="/courses" className={SECONDARY_ACTION}>Tüm dersler <ChevronRightIcon size={17} /></Link>}
      />

      {refreshError && <ErrorNote message={refreshError} kind={errorKind} requestId={errorRequestId} onRetry={reload} />}

      {focusCourse && (
        <section aria-labelledby="dashboard-focus-title" className="rise flex flex-col gap-4 rounded-[20px] bg-brand-subtle p-5 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:px-6">
          <div className="min-w-0">
            <p className="text-sm font-medium text-brand">Kaldığınız yerden</p>
            <h2 id="dashboard-focus-title" className="mt-1 text-lg font-semibold tracking-tight text-fg">
              {focusCourse.title} <span className="ml-1 text-sm font-normal text-fg-muted">{focusCourse.code}</span>
            </h2>
            <p className="mt-1 text-sm text-fg-muted">
              {focusCourse.assistant_locked && focusCourse.role !== "instructor"
                ? focusCourse.assistant_lock_message || "Aktif sınav sürerken asistan kullanılamaz."
                : `Son etkinlik: ${lastActivityLabel(focusCourse.last_activity_at)}`}
            </p>
          </div>
          <Link href={coursePrimaryHref(focusCourse)} className={`${PRIMARY_ACTION} shrink-0 self-start sm:self-auto`}>
            {coursePrimaryLabel(focusCourse)} <ChevronRightIcon size={17} />
          </Link>
        </section>
      )}

      <section aria-labelledby="course-workspaces-title">
        <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="course-workspaces-title" className="text-xl font-semibold tracking-tight text-fg">Tüm çalışma alanları</h2>
          <span className="text-sm text-fg-muted">{data.summary.total_courses} ders</span>
        </div>
        {data.courses.length === 0 ? (
          <EmptyState title="Henüz bağlı olduğunuz bir ders bulunmuyor." />
        ) : (
          <ul className="grid items-start gap-5 xl:grid-cols-2">
            {data.courses.map((course) => <li key={course.id} className="min-w-0"><WorkspaceRow course={course} /></li>)}
          </ul>
        )}
      </section>

      <details className="rounded-[20px] bg-surface shadow-e1">
        <summary className="cursor-pointer rounded-[20px] px-5 py-4 text-sm font-medium text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand sm:px-6">Çalışma özeti</summary>
        <PortalMetrics items={[
          { label: "Toplam ders", value: data.summary.total_courses },
          { label: "Eğitmen olduğunuz", value: data.summary.instructor_courses },
          { label: "Öğrenci olduğunuz", value: data.summary.student_courses },
          { label: "İlgilenilecek iş", value: data.summary.action_items, detail: "İşlenen kaynak, hata ve onay bekleyen soru" },
        ]} />
      </details>
    </div>
  );
}

/** Aynı dersin araçları ve ayrıntıları tek yüzeyde, ikincil bilgiler açılır bölümde. */
function WorkspaceRow({ course }: { course: DashboardCourse }) {
  const instructor = course.role === "instructor";
  const quickTools = courseQuickTools(course);
  const attentionMessages = instructorAttentionMessages(course);

  return (
    <article className="overflow-hidden rounded-[20px] bg-surface shadow-e1 transition-shadow hover:shadow-e2">
      <div className="p-5 sm:p-6">
        <div className="flex items-start gap-3.5">
          <span aria-hidden="true" className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-surface-sunken text-brand"><BookIcon size={24} /></span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium text-fg-muted">{course.code}</span>
              <Badge tone={instructor ? "info" : "neutral"}>{roleLabel(course.role)}</Badge>
            </div>
            <h3 className="mt-2 text-xl font-semibold leading-snug tracking-tight text-fg">{course.title}</h3>
          </div>
        </div>

        {attentionMessages.length > 0 && (
          <div role="status" className="mt-4 rounded-xl bg-warning-bg px-4 py-3 text-sm text-warning">
            {attentionMessages.map((message) => <p key={message}>{message}</p>)}
          </div>
        )}
        {!instructor && course.assistant_locked && course.assistant_lock_message && (
          <p role="status" className="mt-4 rounded-xl bg-warning-bg px-4 py-3 text-sm text-warning">{course.assistant_lock_message}</p>
        )}

        <dl className="mt-5 grid grid-cols-2 gap-4 border-t border-border pt-4">
          <CourseDatum label={instructor ? "Kaynak" : "Çalışma sorusu"} value={instructor ? course.documents_total : course.questions_total} />
          <CourseDatum label="Yayındaki sınav" value={course.published_exams} />
        </dl>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <Link href={coursePrimaryHref(course)} className={SECONDARY_ACTION}>{coursePrimaryLabel(course)} <ChevronRightIcon size={17} /></Link>
          <CourseAssistant courseId={course.id} courseLabel={course.code} placement="inline" />
        </div>
      </div>

      <details className="border-t border-border">
        <summary className="cursor-pointer px-5 py-3.5 text-sm font-medium text-fg-muted transition-colors hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand sm:px-6">Araçlar ve ders ayrıntıları</summary>
        <div className="px-5 pb-5 sm:px-6">
          <nav aria-label={course.code + " hızlı araçları"} className="-mx-3 flex flex-wrap gap-x-1 gap-y-0.5">
            {quickTools.map((tool) => <Link key={tool.href} href={tool.href} className={QUICK_LINK}>{tool.label}</Link>)}
          </nav>
          <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-border pt-4 sm:grid-cols-3">
            {instructor ? <>
              <CourseDatum label="İşleniyor" value={course.documents_processing} />
              <CourseDatum label="İşlenemedi" value={course.documents_failed} />
              <CourseDatum label="Taslak soru" value={course.draft_questions} />
            </> : <>
              <CourseDatum label="Konu hâkimiyeti" value={masteryLabel(course.mastery_score)} />
              <CourseDatum label="Kaynak" value={course.documents_total} />
            </>}
          </dl>
          <p className="mt-4 text-xs text-fg-subtle">Son etkinlik: {lastActivityLabel(course.last_activity_at)}</p>
        </div>
      </details>
    </article>
  );
}

function CourseDatum({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <dt className="text-sm text-fg-muted">{label}</dt>
      <dd className="text-base font-semibold tabular-nums text-fg">{value}</dd>
    </div>
  );
}
