"use client";

import Link from "next/link";
import { useCallback } from "react";
import { AppShell } from "@/components/app-shell";
import { CourseAssistant } from "@/components/course-assistant/course-assistant";
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

/*
 * Pano, 14 Eylül tasarım turu: "üniversite portalı" hissinin üç ölçülmüş kaynağı
 * kaldırıldı — kutu-içinde-kutu (kenarlık + iç kenarlık + saç çizgili sütun),
 * kırmızı enflasyonu (ray + mono kod + buton + yedi kırmızı bağlantı aynı blokta)
 * ve etiket enflasyonu (eyebrow, "En yeni ders alanı", "Çalışma bağlamı").
 *
 * Kırmızı bu sayfada yalnız odak kartındaki birincil eylemde kalır (DESIGN.md
 * renk kilidi). Katman sinyali kenarlıktan değil `shadow-e1`'den gelir; rakamlar
 * `font-mono` yerine `tabular-nums` ile hizalanır (Türkçe ondalık ayracı kopmaz).
 *
 * Erişilebilirlik sözleşmesi DEĞİŞMEDİ: `aria-labelledby`/`id` çiftleri, `nav`
 * etiketi, bağlantı metinleri ve href'ler e2e testlerinin bulduğu hâliyle durur;
 * yalnız sunum değişti.
 */

/** İkincil eylem: `Button variant="secondary"` ile aynı gramer, `<a>` gövdesinde. */
const SECONDARY_ACTION =
  "inline-flex min-h-11 items-center justify-center rounded-lg border border-border-strong bg-surface px-4 text-sm font-medium text-fg transition-[color,background,border,transform] duration-200 hover:border-fg-subtle hover:bg-surface-sunken active:translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

/** Birincil eylem: sayfadaki TEK kırmızı yüzey. `Button variant="primary"` grameri. */
const PRIMARY_ACTION =
  "inline-flex min-h-11 items-center justify-center rounded-lg bg-brand px-5 text-sm font-medium text-bg shadow-e1 transition-[color,background,transform,box-shadow] duration-200 hover:bg-brand-strong active:translate-y-px active:shadow-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

/**
 * Hızlı araç bağlantısı: ikincil metin bağlantısı, aksan rengi taşımaz.
 * Önceki hâlde satır başına yedi `text-brand` bağlantı vardı ve kırmızı
 * "buraya bas" demeyi bırakmıştı. 44px dokunma hedefi `min-h-11` ile korunur.
 */
const QUICK_LINK =
  "inline-flex min-h-11 items-center text-sm text-fg-muted underline-offset-4 transition-colors duration-200 hover:text-fg hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

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
        title={firstName ? `Merhaba, ${firstName}` : "Genel bakış"}
        description="Rolünüze göre güncel işi görün, kaynaklara dönün ve kaldığınız yerden devam edin."
        action={
          <Link href="/courses" className={SECONDARY_ACTION}>
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
        /*
         * Odak kartı: tek yükselmiş yüzey (DESIGN.md §Elevation seviye 1),
         * kenarlık yok, iç ray yok. Sağdaki bağlam paneli kanvasın altında
         * duran çukur yüzeydir; sütunlar saç çizgisiyle değil boşlukla ayrılır.
         */
        <section
          aria-labelledby="dashboard-focus-title"
          className="rounded-xl bg-surface p-5 shadow-e1 sm:p-8"
        >
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(240px,18rem)] lg:gap-8">
            <div className="min-w-0">
              <p className="flex flex-wrap items-center gap-x-3 text-sm text-fg-muted">
                <span>{focusCourse.code}</span>
                <span>{roleLabel(focusCourse.role)}</span>
              </p>
              <h2
                id="dashboard-focus-title"
                className="mt-2 max-w-2xl text-balance text-2xl font-semibold tracking-tight text-fg sm:text-3xl"
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
                className={`mt-6 ${PRIMARY_ACTION}`}
              >
                {coursePrimaryLabel(focusCourse)}
              </Link>
            </div>

            {/*
             * DOM sırası etiket → değer (ekran okuyucu "Son etkinlik: …" okur);
             * `flex-col-reverse` görselde sayıyı üste, etiketi alta koyar — metrik
             * şeridiyle aynı okuma düzeni.
             */}
            <dl className="grid grid-cols-2 gap-4 rounded-lg bg-surface-sunken p-5 lg:grid-cols-1 lg:content-start lg:gap-6">
              <div className="flex flex-col-reverse gap-1">
                <dt className="text-xs text-fg-muted">Son etkinlik</dt>
                <dd className="text-sm font-medium tabular-nums text-fg">
                  {lastActivityLabel(focusCourse.last_activity_at)}
                </dd>
              </div>
              <div className="flex flex-col-reverse gap-1">
                <dt className="text-xs text-fg-muted">Tüm derslerdeki iş</dt>
                <dd className="text-2xl leading-none font-semibold tracking-tight tabular-nums text-fg">
                  {data.summary.action_items}
                </dd>
              </div>
            </dl>
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
          <h2 id="course-workspaces-title" className="text-lg font-semibold tracking-tight text-fg">
            Tüm çalışma alanları
          </h2>
          <p className="mt-1 text-sm text-fg-muted">
            Her satır yalnız o dersteki rolünüze uygun araçları ve gerçek durumu gösterir.
          </p>
        </div>

        {data.courses.length === 0 ? (
          <EmptyState title="Henüz bağlı olduğunuz bir ders bulunmuyor." />
        ) : (
          <ul className="space-y-4">
            {data.courses.map((course) => (
              <li key={course.id}>
                <WorkspaceRow course={course} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/**
 * Çalışma alanı satırı: kendi başına yükselen kart, içinde kutu yok.
 *
 * Üç bölge yan yana: kimlik + araçlar (esner) · kompakt sayı ızgarası · tek
 * ikincil eylem. Önceki satır ortası boştu, sağda saç çizgili bir sayı bloğu
 * vardı ve araç bağlantıları kırmızıydı. Sayılar artık sol bloğun hemen yanında
 * durur, eylem en sağda; kırmızı hiçbir yerde yok.
 */
function WorkspaceRow({ course }: { course: DashboardCourse }) {
  const instructor = course.role === "instructor";
  const quickTools = courseQuickTools(course);
  const attentionMessages = instructorAttentionMessages(course);

  return (
    <article className="flex flex-col gap-5 rounded-xl bg-surface p-5 shadow-e1 lg:flex-row lg:items-start lg:gap-8">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="text-sm text-fg-muted">{course.code}</p>
          <Badge tone={instructor ? "info" : "neutral"}>{roleLabel(course.role)}</Badge>
        </div>
        <h3 className="mt-1 text-lg font-semibold tracking-tight text-fg">{course.title}</h3>

        {attentionMessages.length > 0 && (
          <div role="status" className="mt-3 text-sm text-warning">
            {attentionMessages.map((message) => (
              <p key={message}>{message}</p>
            ))}
          </div>
        )}

        {/*
         * `[&>button]` seçicileri satır içi asistan tetikleyicisi içindir:
         * bileşen (`course-assistant.tsx`) inline yerleşimde `text-xs text-brand`
         * yazar ve bu sayfanın yüzeyi değildir. Aksan kilidi (yalnız odak kartı
         * kırmızı) ebeveynden kurulur; tetikleyicinin davranışı, adı ve dialog'u
         * olduğu gibi kalır. Yalnız doğrudan çocuk buton hedeflenir, dialog
         * içindeki butonlar etkilenmez.
         */}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 [&>button]:text-sm [&>button]:text-fg-muted [&>button:hover]:text-fg">
          <CourseAssistant
            courseId={course.id}
            courseLabel={course.code}
            placement="inline"
          />
          <nav
            aria-label={course.code + " hızlı araçları"}
            className="flex flex-wrap gap-x-4 gap-y-1"
          >
            {quickTools.map((tool) => (
              <Link key={tool.href} href={tool.href} className={QUICK_LINK}>
                {tool.label}
              </Link>
            ))}
          </nav>
        </div>

        {!instructor && course.assistant_locked && course.assistant_lock_message && (
          <p role="status" className="mt-2 text-sm text-warning">
            {course.assistant_lock_message}
          </p>
        )}

        <p className="mt-3 text-xs text-fg-subtle">
          Son etkinlik: {lastActivityLabel(course.last_activity_at)}
        </p>
      </div>

      {/*
       * Sayı ızgarası: kenarlıksız, saç çizgisiz; eğitmende beş, öğrencide dört
       * ölçüm. Eğitmen ızgarası geniş ekranda üç sütun (5 → 3+2), öğrenci 2×2.
       */}
      {instructor ? (
        <dl className="grid shrink-0 grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:w-72">
          <CourseDatum label="Kaynak" value={course.documents_total} />
          <CourseDatum label="İşleniyor" value={course.documents_processing} />
          <CourseDatum label="İşlenemedi" value={course.documents_failed} />
          <CourseDatum label="Taslak soru" value={course.draft_questions} />
          <CourseDatum label="Yayındaki sınav" value={course.published_exams} />
        </dl>
      ) : (
        <dl className="grid shrink-0 grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4 lg:w-56 lg:grid-cols-2">
          <CourseDatum label="Çalışma sorusu" value={course.questions_total} />
          <CourseDatum label="Yayındaki sınav" value={course.published_exams} />
          <CourseDatum
            label="Konu hâkimiyeti"
            value={masteryLabel(course.mastery_score)}
            emphasis={course.mastery_score !== null}
          />
          <CourseDatum label="Kaynak" value={course.documents_total} />
        </dl>
      )}

      <div className="shrink-0">
        <Link href={coursePrimaryHref(course)} className={SECONDARY_ACTION}>
          {coursePrimaryLabel(course)}
        </Link>
      </div>
    </article>
  );
}

/**
 * Tek ölçüm: değer üstte, etiket altında (görsel); DOM'da `dt` önce gelir ki
 * ekran okuyucu "Kaynak: 0" okusun ve `dt`'nin kardeşi `dd` olsun (e2e bu
 * kardeşliği XPath ile bulur).
 *
 * `emphasis=false` sayı olmayan değer içindir ("Henüz ölçülmedi"): metin bir
 * ölçüm değil, ölçümün yokluğudur; display boyunda basılırsa uydurma bir skor
 * gibi ağırlık kazanır.
 */
function CourseDatum({
  label,
  value,
  emphasis = true,
}: {
  label: string;
  value: string | number;
  emphasis?: boolean;
}) {
  return (
    <div className="flex flex-col-reverse gap-0.5">
      <dt className="text-xs text-fg-muted">{label}</dt>
      <dd
        className={
          emphasis
            ? "text-lg leading-tight font-semibold tracking-tight tabular-nums text-fg"
            : "text-sm leading-tight font-medium text-fg"
        }
      >
        {value}
      </dd>
    </div>
  );
}
