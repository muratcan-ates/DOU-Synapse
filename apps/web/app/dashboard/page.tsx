"use client";

import Link from "next/link";
import { useCallback } from "react";
import { AppShell } from "@/components/app-shell";
import { CourseAssistant } from "@/components/course-assistant/course-assistant";
import { ChevronRightIcon, ShieldIcon } from "@/components/icons";
import { usePortalProfile } from "@/components/portal/portal-profile-context";
import { CourseCover } from "@/components/course-cover";
import { ErrorNote, Loading } from "@/components/page-state";
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
  "inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-3 text-sm font-semibold text-fg transition-colors duration-250 hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";
const QUICK_LINK =
  "inline-flex min-h-11 items-center rounded-lg px-3 text-sm text-fg-muted transition-colors duration-250 hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

export default function DashboardPage() {
  return <AppShell><DashboardContent /></AppShell>;
}

function DashboardContent() {
  const { data: profile } = usePortalProfile();
  const fetchDashboard = useCallback(() => getDashboard(), []);
  const { data, error, refreshError, errorKind, errorRequestId, loading, reload } =
    useResource(fetchDashboard, []);

  if (error) {
    return <ErrorNote message={error} kind={errorKind} requestId={errorRequestId} onRetry={reload} />;
  }
  if (loading || !data) return <Loading label="Çalışma alanınız hazırlanıyor…" />;

  const firstName = data.viewer.full_name?.trim().split(/\s+/)[0] ?? "";
  const isOperationsOnly = profile?.is_platform_admin === true && profile.memberships.length === 0;
  const instructorCourses = data.courses.filter((course) => course.role === "instructor");
  const studentCourses = data.courses.filter((course) => course.role === "student");
  const description = instructorCourses.length > 0 && studentCourses.length > 0
    ? "Derslerinize göre eğitmen ve öğrenci alanlarınız."
    : instructorCourses.length > 0
      ? "Dersleriniz, içerikleriniz ve sınıf çalışmaları."
      : studentCourses.length > 0
        ? "Ders tekrarı, ilerlemeniz ve sınavlarınız."
        : profile?.is_platform_admin
          ? "Sistem durumu ve teknik yönetim."
          : "Ders üyelikleriniz burada görünecek.";

  return (
    <div className="space-y-7 sm:space-y-8">
      <header>
        <h1 className="min-w-0 text-[2rem] font-semibold leading-tight tracking-[-0.035em] text-fg [overflow-wrap:anywhere] sm:text-[2.25rem]">
          {isOperationsOnly ? "Bilgi İşlem çalışma alanı" : firstName ? `Merhaba, ${firstName}` : "Genel bakış"}
        </h1>
        <p className="mt-1.5 text-base text-fg-muted">{description}</p>
      </header>

      {refreshError && <ErrorNote message={refreshError} kind={errorKind} requestId={errorRequestId} onRetry={reload} />}

      {profile?.is_platform_admin && (
        <section aria-labelledby="dashboard-operations-title" className="flex flex-wrap items-center gap-4 rounded-[20px] border border-border bg-surface p-5 shadow-e1 sm:p-6">
          <span aria-hidden="true" className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-brand-subtle text-brand"><ShieldIcon size={24} /></span>
          <div className="min-w-0 flex-1 basis-56">
            <h2 id="dashboard-operations-title" className="text-xl font-semibold tracking-tight text-fg">Bilgi İşlem paneli</h2>
            <p className="mt-1 text-sm leading-relaxed text-fg-muted">Servis sağlığı, kullanım kayıtları ve kaynak işleme süreçleri.</p>
          </div>
          <Link href="/admin" className={SECONDARY_ACTION}>Teknik paneli aç <ChevronRightIcon size={17} /></Link>
        </section>
      )}

      {instructorCourses.length > 0 && <InstructorPanel courses={instructorCourses} />}
      {studentCourses.length > 0 && <StudentPanel courses={studentCourses} />}

      {(data.courses.length > 0 || !profile?.is_platform_admin) && <section aria-labelledby="course-workspaces-title">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 id="course-workspaces-title" className="text-xl font-semibold tracking-tight text-fg">Tüm çalışma alanları <span className="ml-1 text-base font-normal text-fg-muted">({data.summary.total_courses})</span></h2>
          <Link href="/courses" className={`${SECONDARY_ACTION} -mr-3`}>Tüm dersler <ChevronRightIcon size={17} /></Link>
        </div>
        {data.courses.length === 0 ? (
          <EmptyState title="Henüz bağlı olduğunuz bir ders bulunmuyor." />
        ) : (
          <ul className="space-y-3">
            {data.courses.map((course) => <li key={course.id} className="min-w-0"><WorkspaceRow course={course} /></li>)}
          </ul>
        )}
      </section>}
    </div>
  );
}

function StudentPanel({ courses }: { courses: DashboardCourse[] }) {
  const focusCourse = courses[0]!;
  const examCourses = courses.filter((course) => course.assistant_locked || course.published_exams > 0);

  return (
    <section aria-labelledby="student-panel-title" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 id="student-panel-title" className="text-xl font-semibold tracking-tight text-fg">Öğrenci paneli</h2>
          <p className="mt-1 text-sm text-fg-muted">Kaldığınız yerden çalışmaya devam edin.</p>
        </div>
        <Link href="/study" className={`${SECONDARY_ACTION} -mr-3`}>Ders tekrarı <ChevronRightIcon size={17} /></Link>
      </div>
      <div className="grid min-w-0 items-start gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <FocusCourse course={focusCourse} />
        <div className="overflow-hidden rounded-[20px] bg-surface px-5 shadow-e1 sm:px-6">
          <h3 className="pt-5 text-base font-semibold text-fg">İlerlemem ve sınavlarım</h3>
          <ul className="divide-y divide-border">
            {courses.slice(0, 3).map((course) => (
              <li key={course.id} className="flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3">
                <div className="min-w-0 flex-1 basis-36">
                  <p className="text-sm font-semibold text-fg [overflow-wrap:anywhere]">{course.code}</p>
                  <p className="mt-0.5 text-sm text-fg-muted">Konu hâkimiyeti: {masteryLabel(course.mastery_score)}</p>
                </div>
                <Link href={`/courses/${course.id}/analytics`} className={`${QUICK_LINK} -mr-3`}>İlerleme <ChevronRightIcon size={15} className="ml-1" /></Link>
              </li>
            ))}
          </ul>
          <div className="border-t border-border py-4">
            {examCourses.length > 0 ? (
              <ul className="space-y-1">
                {examCourses.slice(0, 3).map((course) => (
                  <li key={course.id}>
                    <Link href={`/courses/${course.id}/exam`} className="flex min-h-11 min-w-0 items-center justify-between gap-3 rounded-lg py-2 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
                      <span className="min-w-0 text-fg [overflow-wrap:anywhere]">{course.code} <span className="text-fg-muted">· {course.assistant_locked ? "Aktif sınav" : `${course.published_exams} yayındaki sınav`}</span></span>
                      <ChevronRightIcon size={17} className="shrink-0 text-brand" />
                    </Link>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-fg-muted">Derslerinizde yayında bir sınav yok.</p>}
          </div>
        </div>
      </div>
    </section>
  );
}

function InstructorPanel({ courses }: { courses: DashboardCourse[] }) {
  const pending = courses.flatMap((course) => {
    const messages = instructorAttentionMessages(course);
    if (course.documents_processing > 0) messages.push(`${course.documents_processing} kaynak işleniyor.`);
    return messages.length > 0 ? [{ course, messages }] : [];
  });
  const recentCourses = courses
    .filter((course) => course.last_activity_at !== null && Number.isFinite(Date.parse(course.last_activity_at)))
    .toSorted((first, second) => Date.parse(second.last_activity_at!) - Date.parse(first.last_activity_at!))
    .slice(0, 3);

  return (
    <section aria-labelledby="instructor-panel-title" className="space-y-3">
      <div>
        <h2 id="instructor-panel-title" className="text-xl font-semibold tracking-tight text-fg">Eğitmen paneli</h2>
        <p className="mt-1 text-sm text-fg-muted">Ders içerikleri, soru onayları ve sınıf etkinliği.</p>
      </div>
      <div className="grid min-w-0 items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div className="overflow-hidden rounded-[20px] bg-surface px-5 shadow-e1 sm:px-6">
          <h3 className="pt-5 text-base font-semibold text-fg">{pending.length > 0 ? "İlgilenilecek işler" : "Son ders etkinliği"}</h3>
          {pending.length > 0 ? (
            <>
              <ul className="divide-y divide-border">
                {pending.slice(0, 3).map(({ course, messages }) => (
                  <li key={course.id}>
                    <Link href={coursePrimaryHref(course)} className="group flex min-h-16 items-center gap-3 rounded-lg py-3.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-fg [overflow-wrap:anywhere]">{course.code}</p>
                        <p className="mt-0.5 text-sm leading-relaxed text-fg-muted">{messages.join(" ")}</p>
                      </div>
                      <ChevronRightIcon size={18} className="shrink-0 text-brand" />
                    </Link>
                  </li>
                ))}
              </ul>
              {pending.length > 3 && <p className="border-t border-border py-3 text-sm text-fg-muted">Diğer {pending.length - 3} dersin işleri aşağıdaki listede.</p>}
            </>
          ) : recentCourses.length > 0 ? (
            <ul className="divide-y divide-border">
              {recentCourses.map((course) => (
                <li key={course.id}>
                  <Link href={`/courses/${course.id}/analytics`} className="flex min-h-16 items-center justify-between gap-4 rounded-lg py-3.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-fg [overflow-wrap:anywhere]">{course.code}</p>
                      <p className="mt-0.5 text-sm text-fg-muted">{lastActivityLabel(course.last_activity_at)}</p>
                    </div>
                    <ChevronRightIcon size={18} className="shrink-0 text-fg-muted" />
                  </Link>
                </li>
              ))}
            </ul>
          ) : <p className="py-5 text-sm text-fg-muted">Onay bekleyen soru veya işleme sorunu yok. Henüz kayıtlı ders etkinliği bulunmuyor.</p>}
        </div>
        <FocusCourse course={courses[0]!} />
      </div>
    </section>
  );
}

function FocusCourse({ course }: { course: DashboardCourse }) {
  const instructor = course.role === "instructor";
  return (
    <div className="rounded-[20px] bg-surface p-5 shadow-e1 sm:p-6">
      <div className="flex min-w-0 items-start gap-4">
        <CourseCover title={course.title} code={course.code} size="compact" />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm text-fg-muted">
            <span className="font-medium text-brand [overflow-wrap:anywhere]">{course.code}</span>
            <span>{roleLabel(course.role)}</span>
          </p>
          <h3 className="mt-1 text-[1.375rem] font-semibold leading-snug tracking-tight text-fg [overflow-wrap:anywhere]">{course.title}</h3>
        </div>
      </div>
      {!instructor && course.assistant_locked && (
        <p role="status" className="mt-4 text-sm leading-relaxed text-warning">{course.assistant_lock_message || "Aktif sınav sürerken asistan kullanılamaz."}</p>
      )}
      {instructor && <nav aria-label={`${course.code} eğitmen kısayolları`} className="-mx-3 mt-3 flex flex-wrap gap-1">
        <Link href={`/courses/${course.id}/sources`} className={QUICK_LINK}>Kaynaklar</Link>
        <Link href={`/courses/${course.id}/questions`} className={QUICK_LINK}>Soru havuzu</Link>
        <Link href={`/courses/${course.id}/analytics`} className={QUICK_LINK}>Sınıf analitiği</Link>
      </nav>}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
        <p className="text-sm text-fg-muted">Son etkinlik: {lastActivityLabel(course.last_activity_at)}</p>
        <Link href={coursePrimaryHref(course)} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-brand px-4 text-sm font-semibold text-brand-fg transition-colors duration-250 hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
          {coursePrimaryLabel(course)} <ChevronRightIcon size={17} />
        </Link>
      </div>
    </div>
  );
}

function WorkspaceRow({ course }: { course: DashboardCourse }) {
  const instructor = course.role === "instructor";
  const quickTools = courseQuickTools(course);
  const attentionMessages = instructorAttentionMessages(course);

  return (
    <article className="min-w-0 overflow-hidden rounded-[20px] bg-surface shadow-e1">
      <div className="px-5 py-4 sm:px-6">
        <div className="grid min-w-0 items-center gap-3 xl:grid-cols-[minmax(0,1fr)_auto]">
          <div className="flex min-w-0 items-start gap-3.5">
            <CourseCover title={course.title} code={course.code} size="compact" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="min-w-0 max-w-full text-sm font-medium text-brand [overflow-wrap:anywhere]">{course.code}</span>
                <Badge tone={instructor ? "info" : "neutral"}>{roleLabel(course.role)}</Badge>
              </div>
              <h3 className="mt-1 text-xl font-semibold leading-snug tracking-tight text-fg [overflow-wrap:anywhere]">{course.title}</h3>
              <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
                <CourseDatum inline label={instructor ? "Kaynak" : "Çalışma sorusu"} value={instructor ? course.documents_total : course.questions_total} />
                <CourseDatum inline label="Yayındaki sınav" value={course.published_exams} />
              </dl>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 xl:justify-end">
            <Link href={coursePrimaryHref(course)} className={SECONDARY_ACTION}>{coursePrimaryLabel(course)} <ChevronRightIcon size={17} /></Link>
            <CourseAssistant courseId={course.id} courseLabel={course.code} placement="inline" />
          </div>
        </div>

        {attentionMessages.length > 0 && (
          <div role="status" className="mt-3 border-l-2 border-warning pl-3 text-sm leading-relaxed text-warning">
            {attentionMessages.map((message) => <p key={message}>{message}</p>)}
          </div>
        )}
        {!instructor && course.assistant_locked && course.assistant_lock_message && (
          <p role="status" className="mt-3 border-l-2 border-warning pl-3 text-sm leading-relaxed text-warning">{course.assistant_lock_message}</p>
        )}
      </div>

      <details className="border-t border-border">
        <summary className="cursor-pointer px-5 py-3 text-sm font-medium text-fg-muted transition-colors duration-250 hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand sm:px-6">Araçlar ve ders ayrıntıları</summary>
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

function CourseDatum({ label, value, inline = false }: { label: string; value: string | number; inline?: boolean }) {
  return (
    <div className={inline ? "flex min-w-0 items-baseline gap-2" : "min-w-0"}>
      <dt className="text-sm text-fg-muted">{label}</dt>
      <dd className={`${inline ? "text-sm" : "mt-1 text-lg"} font-semibold tabular-nums text-fg [overflow-wrap:anywhere]`}>{value}</dd>
    </div>
  );
}
