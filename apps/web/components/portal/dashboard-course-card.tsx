import Link from "next/link";
import { CourseAssistant } from "@/components/course-assistant/course-assistant";
import { Badge } from "@/components/ui";
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
    <article className="grid gap-5 border-t border-border py-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(300px,0.75fr)] lg:gap-8">
      <div className="min-w-0">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-mono text-xs text-fg-subtle">{course.code}</p>
            <h3 className="mt-1 text-lg font-medium text-fg">{course.title}</h3>
          </div>
          <Badge tone={instructor ? "info" : "neutral"}>{roleLabel(course.role)}</Badge>
        </div>

        {attentionMessages.length > 0 && (
          <div role="status" className="mt-4 border-l-2 border-warning pl-3 text-xs text-warning">
            {attentionMessages.map((message) => (
              <p key={message}>{message}</p>
            ))}
          </div>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-x-5 gap-y-1">
          <CourseAssistant
            courseId={course.id}
            courseLabel={course.code}
            placement="inline"
          />
          <nav
            aria-label={course.code + " hızlı araçları"}
            className="flex flex-wrap gap-x-5 gap-y-1"
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
        </div>

        <p className="mt-4 text-xs text-fg-subtle">
          Son etkinlik: {lastActivityLabel(course.last_activity_at)}
        </p>
      </div>

      <div className="flex flex-col justify-between border-t border-border pt-5 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
        {instructor ? (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-3 lg:grid-cols-2">
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

        {!instructor && course.assistant_locked && course.assistant_lock_message && (
          <p role="status" className="mt-4 text-xs text-warning">
            {course.assistant_lock_message}
          </p>
        )}

        <Link
          href={coursePrimaryHref(course)}
          className="mt-5 inline-flex min-h-11 w-fit items-center rounded-lg border border-border-strong px-4 text-sm font-medium text-fg hover:border-fg-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          {coursePrimaryLabel(course)}
        </Link>
      </div>
    </article>
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
