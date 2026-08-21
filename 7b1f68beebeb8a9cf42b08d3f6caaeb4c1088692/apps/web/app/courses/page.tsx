"use client";

/** Ders listesi + ders açma (eğitmen). */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, getStoredUser } from "@/lib/api";
import type { Course } from "@/lib/types";
import { AppShell } from "@/components/app-shell";
import { Button, Card, EmptyState, Input } from "@/components/ui";

export default function CoursesPage() {
  return (
    <AppShell>
      <CourseList />
    </AppShell>
  );
}

function CourseList() {
  const [courses, setCourses] = useState<Course[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const user = getStoredUser();

  const load = useCallback(() => {
    api
      .get<Course[]>("/courses")
      .then(setCourses)
      .catch((e: unknown) => setError(e instanceof ApiError ? e.message : "Bağlantı kurulamadı."));
  }, []);

  useEffect(load, [load]);

  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (courses === null) return <p className="text-sm text-fg-muted">Yükleniyor…</p>;

  return (
    <div>
      <div className="rise mb-8 flex items-end justify-between gap-4">
        <h1 className="text-3xl font-semibold tracking-tight text-fg">Derslerim</h1>
        {user?.role === "instructor" && (
          <Button variant="secondary" onClick={() => setCreating((v) => !v)}>
            {creating ? "Vazgeç" : "Yeni ders"}
          </Button>
        )}
      </div>

      {creating && <CreateCourseForm onCreated={() => { setCreating(false); load(); }} />}

      {courses.length === 0 && !creating ? (
        <EmptyState
          title={
            user?.role === "instructor"
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
      setError(err instanceof ApiError ? err.message : "İşlem tamamlanamadı.");
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
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
    </Card>
  );
}
