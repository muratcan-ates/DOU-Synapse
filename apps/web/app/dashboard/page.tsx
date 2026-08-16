"use client";

import Link from "next/link";
import { useCallback } from "react";
import { AppShell } from "@/components/app-shell";
import { DashboardCourseCard } from "@/components/portal/dashboard-course-card";
import { PortalMetrics } from "@/components/portal/portal-metrics";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { EmptyState } from "@/components/ui";
import {
  coursePrimaryHref,
  coursePrimaryLabel,
  getDashboard,
  lastActivityLabel,
} from "@/lib/dashboard";
import { roleLabel } from "@/lib/profile";
import { useResource } from "@/lib/use-resource";

export default function DashboardPage() {
  return (
    <AppShell>
      <DashboardContent />
    </AppShell>
  );
}

function DashboardContent() {
  const fetchDashboard = useCallback(() => getDashboard(), []);
  const {
    data,
    error,
    refreshError,
    errorKind,
    errorRequestId,
    loading,
    reload,
  } = useResource(fetchDashboard, []);

  if (error) {
    return (
      <ErrorNote
        message={error}
        kind={errorKind}
        requestId={errorRequestId}
        onRetry={reload}
      />
    );
  }
  if (loading || !data) return <Loading label="Çalışma alanınız hazırlanıyor…" />;

  const firstName = data.viewer.full_name?.trim().split(/\s+/)[0] ?? "";
  const focusCourse = data.courses[0] ?? null;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Kişisel çalışma alanı"
        title={firstName ? `Merhaba, ${firstName}` : "Genel bakış"}
        description="Rolünüze göre güncel işi görün, kaynaklara dönün ve kaldığınız yerden devam edin."
        action={
          <Link
            href="/courses"
            className="inline-flex min-h-11 items-center rounded-lg border border-border-strong bg-surface px-4 text-sm font-medium text-fg hover:border-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            Tüm dersler
          </Link>
        }
      />

      {refreshError && (
        <ErrorNote
          message={refreshError}
          kind={errorKind}
          requestId={errorRequestId}
          onRetry={reload}
        />
      )}

      {focusCourse && (
        <section
          aria-labelledby="dashboard-focus-title"
          className="overflow-hidden rounded-xl border border-border bg-surface"
        >
          <div className="grid lg:grid-cols-[minmax(0,1.45fr)_minmax(260px,0.55fr)]">
            <div className="border-l-4 border-brand px-5 py-6 sm:px-8 sm:py-8">
              <p className="mb-3 text-xs font-medium text-fg-muted">En yeni ders alanı</p>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <p className="font-mono text-xs font-medium text-brand">
                  {focusCourse.code}
                </p>
                <p className="text-xs text-fg-muted">{roleLabel(focusCourse.role)}</p>
              </div>
              <h2
                id="dashboard-focus-title"
                className="mt-3 max-w-2xl text-balance text-xl font-semibold tracking-tight text-fg sm:text-2xl"
              >
                {focusCourse.title}
              </h2>
              <p className="prose-tr mt-3 text-sm text-fg-muted">
                {focusCourse.role === "instructor"
                  ? "Kaynak, soru ve sınav akışını bu çalışma alanından yönetin."
                  : focusCourse.assistant_locked
                    ? focusCourse.assistant_lock_message ||
                      "Aktif sınav sürerken asistan kullanılamaz."
                    : "Bu dersin kaynaklara dayalı asistanını açın ve çalışma araçlarına ulaşın."}
              </p>
              <Link
                href={coursePrimaryHref(focusCourse)}
                className="mt-6 inline-flex min-h-11 items-center rounded-lg bg-brand px-5 text-sm font-medium text-bg hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              >
                {coursePrimaryLabel(focusCourse)}
              </Link>
            </div>

            <div className="border-t border-border bg-bg px-5 py-6 lg:border-l lg:border-t-0 lg:px-6">
              <p className="text-xs font-medium text-fg-muted">Çalışma bağlamı</p>
              <dl className="mt-5 space-y-4">
                <div className="border-b border-border pb-4">
                  <dt className="text-xs text-fg-muted">Son etkinlik</dt>
                  <dd className="mt-1 text-sm font-medium text-fg">
                    {lastActivityLabel(focusCourse.last_activity_at)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-fg-muted">Tüm derslerdeki iş</dt>
                  <dd className="mt-1 font-mono text-xl text-fg">
                    {data.summary.action_items}
                  </dd>
                </div>
              </dl>
            </div>
          </div>
        </section>
      )}

      <PortalMetrics
        items={[
          { label: "Toplam ders", value: data.summary.total_courses },
          { label: "Eğitmen olduğunuz", value: data.summary.instructor_courses },
          { label: "Öğrenci olduğunuz", value: data.summary.student_courses },
          {
            label: "İlgilenilecek iş",
            value: data.summary.action_items,
            detail: "İşlenen kaynak, hata ve onay bekleyen soru",
          },
        ]}
      />

      <section aria-labelledby="course-workspaces-title">
        <div className="mb-4">
          <h2 id="course-workspaces-title" className="text-xl font-medium tracking-tight text-fg">
            Tüm çalışma alanları
          </h2>
          <p className="mt-1 text-sm text-fg-muted">
            Her satır yalnız o dersteki rolünüze uygun araçları ve gerçek durumu gösterir.
          </p>
        </div>

        {data.courses.length === 0 ? (
          <EmptyState title="Henüz bağlı olduğunuz bir ders bulunmuyor." />
        ) : (
          <ul className="border-b border-border">
            {data.courses.map((course) => (
              <li key={course.id}>
                <DashboardCourseCard course={course} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
