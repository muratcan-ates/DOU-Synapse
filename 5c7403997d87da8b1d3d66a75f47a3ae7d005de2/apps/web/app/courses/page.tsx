"use client";

/** Ders listesi + ders açma (eğitmen). */

import Link from "next/link";
import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { useSession } from "@/lib/session";
import type { Course } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { AppShell } from "@/components/app-shell";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Button, Card, EmptyState, Input } from "@/components/ui";

export default function CoursesPage() {
  return (
    <AppShell>
      <CourseList />
    </AppShell>
  );
}

function CourseList() {
  const [creating, setCreating] = useState(false);
  const { isInstructor } = useSession();

  const fetchCourses = useCallback(() => api.get<Course[]>("/courses"), []);
  const { data: courses, error, loading, reload } = useResource(fetchCourses, []);

  if (error) return <ErrorNote message={error} />;
  if (loading || !courses) return <Loading />;

  return (
    <div>
      <PageHeader
        title="Derslerim"
        action={
          isInstructor && (
            <Button variant="secondary" onClick={() => setCreating((v) => !v)}>
              {creating ? "Vazgeç" : "Yeni ders"}
            </Button>
          )
        }
      />

      {creating && (
        <CreateCourseForm
          onCreated={() => {
            setCreating(false);
            reload();
          }}
        />
      )}

      {courses.length === 0 && !creating ? (
        <EmptyState
          title={
            isInstructor
              ? "Henüz dersiniz yok. Yeni ders açarak materyal yüklemeye başlayın."
              : "Henüz bir derse kayıtlı değilsiniz. Eğitmeninizin sizi eklemesini bekleyin."
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {courses.map((course, index) => (
            <Link
              key={course.id}
              href={`/courses/${course.id}`}
              className={`rise rise-${Math.min(index + 1, 3)}`}
            >
              <Card className="h-full transition-[border,box-shadow] duration-200 hover:border-border-strong hover:shadow-[0_2px_8px_rgba(28,25,23,0.04)]">
                <p className="font-mono text-xs tracking-wide text-fg-subtle">
                  {course.code}
                </p>
                <p className="mt-2 text-lg font-medium tracking-tight text-fg">
                  {course.title}
                </p>
                <p className="mt-4 text-xs text-fg-subtle">
                  {course.role === "instructor" ? "Eğitmen" : "Öğrenci"}
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function CreateCourseForm({ onCreated }: { onCreated: () => void }) {
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/courses", { code, title });
      onCreated();
    } catch (err) {
      setError(errorMessage(err, "İşlem tamamlanamadı."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mb-6">
      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
        <div className="sm:w-40">
          <Input
            placeholder="COME301"
            aria-label="Ders kodu"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
            minLength={2}
          />
        </div>
        <div className="flex-1">
          <Input
            placeholder="Ders adı, örn. İşletim Sistemleri"
            aria-label="Ders adı"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            minLength={2}
          />
        </div>
        <Button type="submit" disabled={busy}>
          {busy ? "Oluşturuluyor…" : "Oluştur"}
        </Button>
      </form>
      {error && (
        <div className="mt-2">
          <ErrorNote message={error} />
        </div>
      )}
    </Card>
  );
}
