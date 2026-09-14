"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { CourseCover } from "@/components/course-cover";
import { ChevronRightIcon } from "@/components/icons";
import { ErrorNote, Loading } from "@/components/page-state";
import { usePortalProfile } from "@/components/portal/portal-profile-context";
import { roleLabel } from "@/lib/profile";

function searchable(value: string) {
  return value.toLocaleLowerCase("tr-TR").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/ı/g, "i");
}

export default function StudyPage() {
  return <AppShell><StudyCourses /></AppShell>;
}

function StudyCourses() {
  const { data: profile, loading, error, refreshError, errorKind, errorRequestId, reload } = usePortalProfile();
  const [query, setQuery] = useState("");
  const searchId = useId();
  const terms = searchable(query).trim().split(/\s+/).filter(Boolean);
  const courses = (profile?.memberships ?? []).filter((course) => terms.every((term) => searchable(`${course.course_code} ${course.course_title}`).includes(term)));

  return <div className="mx-auto max-w-4xl">
    <header className="mb-7">
      <Link href="/dashboard" className="mb-4 inline-flex min-h-11 items-center gap-2 text-sm text-fg-muted hover:text-brand focus-visible:outline-2 focus-visible:outline-brand"><span aria-hidden="true">←</span> Genel bakış</Link>
      <h1 className="text-[1.875rem] font-semibold leading-tight tracking-[-.035em] text-fg sm:text-[2.25rem]">Ders tekrarı</h1>
      <p className="mt-3 max-w-xl text-base leading-7 text-fg-muted">Dersini seç. Kaynaklarına dön, alıştırmalarla konuyu pekiştir.</p>
    </header>
    {loading ? <Loading label="Dersleriniz yükleniyor…" /> : error ? <ErrorNote message={error} kind={errorKind} requestId={errorRequestId} onRetry={reload} /> : <>
      {refreshError && <div className="mb-5"><ErrorNote message={refreshError} kind={errorKind} requestId={errorRequestId} onRetry={reload} /></div>}
      {profile && profile.memberships.length > 0 ? <>
        <div className="mb-6">
          <label htmlFor={searchId} className="mb-2 block text-sm font-medium text-fg">Tekrar etmek istediğin dersi bul</label>
          <input id={searchId} type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Ders adı veya kodu…" className="min-h-12 w-full rounded-2xl border border-border-strong bg-surface px-4 text-base text-fg placeholder:text-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand" />
          <p role="status" className="mt-2 text-xs text-fg-muted">{courses.length} ders</p>
        </div>
        {courses.length > 0 ? <ul className="space-y-3" aria-label="Tekrar edilecek dersler">
          {courses.map((course) => <li key={course.course_id} className="rounded-[20px] border border-border bg-surface p-5 sm:p-6">
            <div className="flex items-center gap-4">
              <CourseCover title={course.course_title} code={course.course_code} size="compact" />
              <div className="min-w-0">
                <p className="text-xs font-medium text-fg-muted">{course.course_code} · {roleLabel(course.role)}</p>
                <h2 className="mt-1 break-words text-lg font-semibold leading-6 tracking-tight text-fg">{course.course_title}</h2>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-2">
              <Link href={`/courses/${encodeURIComponent(course.course_id)}/exam`} aria-label={`${course.course_title}: alıştırmalara geç`} className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-brand px-4 py-2 text-sm font-semibold text-brand-fg hover:bg-brand-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">Alıştırmalara geç <ChevronRightIcon size={16} /></Link>
              <Link href={`/courses/${encodeURIComponent(course.course_id)}`} aria-label={`${course.course_title}: kaynakları aç`} className="inline-flex min-h-11 items-center text-sm font-medium text-fg-muted underline-offset-4 hover:text-brand hover:underline focus-visible:outline-2 focus-visible:outline-brand">Kaynakları aç</Link>
            </div>
          </li>)}
        </ul> : <div className="rounded-[20px] bg-surface p-7 text-center"><p className="font-semibold text-fg">Bu aramayla eşleşen ders yok.</p><button type="button" onClick={() => setQuery("")} className="mt-3 min-h-11 rounded-xl px-4 text-sm font-medium text-brand hover:bg-brand-subtle focus-visible:outline-2 focus-visible:outline-brand">Aramayı temizle</button></div>}
        <p className="mt-5 text-sm leading-6 text-fg-muted">Alıştırmalar, dersin sınav provası sayfasında açılır. Oradan çalışmaya başlayabilir veya devam eden oturumuna dönebilirsin.</p>
      </> : <div className="rounded-[20px] bg-surface p-7"><h2 className="text-xl font-semibold text-fg">Henüz bir dersin yok.</h2><p className="mt-2 text-sm text-fg-muted">Bir derse katıldığında tekrar seçenekleri burada görünecek.</p><Link href="/courses" className="mt-4 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-brand hover:underline focus-visible:outline-2 focus-visible:outline-brand">Derslere git <ChevronRightIcon size={16} /></Link></div>}
    </>}
  </div>;
}
