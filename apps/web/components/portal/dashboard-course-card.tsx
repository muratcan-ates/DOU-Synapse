import Link from "next/link";
import { Badge, Card } from "@/components/ui";
import {
  coursePrimaryHref,
  coursePrimaryLabel,
  courseQuickTools,
  instructorAttentionMessages,
  lastActivityLabel,
  masteryLabel,
  type DashboardCourse,
} from "@/lib/dashboard";
import { roleLabel } from "@/lib/profile";

export function DashboardCourseCard({ course }: { course: DashboardCourse }) {
  const instructor = course.role === "instructor";
  const quickTools = courseQuickTools(course);
  const attentionMessages = instructorAttentionMessages(course);

  return (
    <Card className="flex h-full flex-col gap-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-xs text-fg-subtle">{course.code}</p>
          <h3 className="mt-1 text-lg font-medium text-fg">{course.title}</h3>
        </div>
        <Badge tone={instructor ? "info" : "neutral"}>{roleLabel(course.role)}</Badge>
      </div>

      {instructor ? (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <CourseDatum label="Kaynak" value={course.documents_total} />
          <CourseDatum label="İşleniyor" value={course.documents_processing} />
          <CourseDatum label="İşlenemedi" value={course.documents_failed} />
          <CourseDatum label="Taslak soru" value={course.draft_questions} />
          <CourseDatum label="Yayındaki sınav" value={course.published_exams} />
        </dl>
      ) : (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <CourseDatum label="Çalışma sorusu" value={course.questions_total} />
          <CourseDatum label="Yayındaki sınav" value={course.published_exams} />
          <CourseDatum label="Konu hâkimiyeti" value={masteryLabel(course.mastery_score)} />
          <CourseDatum label="Kaynak" value={course.documents_total} />
        </dl>
      )}

      <nav
        aria-label={course.code + " hızlı araçları"}
        className="flex flex-wrap gap-x-4 gap-y-2"
      >
        {quickTools.map((tool) => (
          <Link
            key={tool.href}
            href={tool.href}
            className="inline-flex min-h-11 items-center text-xs font-medium text-brand underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            {tool.label}
          </Link>
        ))}
      </nav>

      {!instructor && course.assistant_locked && course.assistant_lock_message && (
        <p role="status" className="text-xs text-warning">
          {course.assistant_lock_message}
        </p>
      )}

      <div className="mt-auto flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <p className="text-xs text-fg-subtle">
          Son etkinlik: {lastActivityLabel(course.last_activity_at)}
        </p>
        <Link
          href={coursePrimaryHref(course)}
          className="inline-flex min-h-11 items-center rounded-lg border border-border-strong px-4 text-sm font-medium text-fg hover:border-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          {coursePrimaryLabel(course)}
        </Link>
      </div>

      {attentionMessages.length > 0 && (
        <div role="status" className="space-y-1 text-xs text-warning">
          {attentionMessages.map((message) => (
            <p key={message}>{message}</p>
          ))}
        </div>
      )}
    </Card>
  );
}

function CourseDatum({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col-reverse gap-0.5">
      <dt className="text-xs text-fg-muted">{label}</dt>
      <dd className="font-mono text-base text-fg">{value}</dd>
    </div>
  );
}
