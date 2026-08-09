"use client";

/** Katılımcı yönetimi (yalnız eğitmen). API: GET/POST/DELETE /courses/{id}/members */

import { useParams } from "next/navigation";
import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { useSession } from "@/lib/session";
import type { Member } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, ConfirmAction, EmptyState, Input } from "@/components/ui";

export default function MembersPage() {
  return (
    <AppShell>
      <MembersView />
    </AppShell>
  );
}

function MembersView() {
  const { courseId } = useParams<{ courseId: string }>();
  const { user } = useSession();

  const fetchMembers = useCallback(
    () => api.get<Member[]>(`/courses/${courseId}/members`),
    [courseId],
  );
  const { data: members, error, loading, reload } = useResource(fetchMembers, [courseId]);

  return (
    <div>
      <CourseNav courseId={courseId} />

      <PageHeader
        title="Katılımcılar"
        description="Öğrenciler yalnızca kayıtlı oldukları dersin materyalini görür; asistan da yalnız o materyalden cevap verir."
      />

      <AddMemberForm courseId={courseId} onAdded={reload} />

      {error && <ErrorNote message={error} />}
      {loading && <Loading />}

      {members?.length === 0 && (
        <EmptyState title="Bu derste henüz katılımcı yok." />
      )}

      {members && members.length > 0 && (
        <ul className="rise rise-1 divide-y divide-border overflow-hidden rounded-xl border border-border bg-surface">
          {members.map((member) => (
            <li
              key={member.user_id}
              className="flex flex-wrap items-center justify-between gap-3 px-6 py-4"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-fg">
                  {member.full_name ?? member.email}
                  {member.user_id === user?.id && (
                    <span className="ml-2 text-xs text-fg-subtle">(siz)</span>
                  )}
                </p>
                <p className="mt-0.5 font-mono text-xs text-fg-subtle">
                  {member.email}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <Badge tone={member.role === "instructor" ? "info" : "neutral"}>
                  {member.role === "instructor" ? "Eğitmen" : "Öğrenci"}
                </Badge>
                {member.status === "revoked" ? (
                  <Badge tone="warning">Erişim kapalı</Badge>
                ) : (
                  // Kendini çıkarma yok: dersin son eğitmeni kendini atarsa
                  // ders sahipsiz kalır.
                  member.user_id !== user?.id && (
                    <ConfirmAction
                      label="Çıkar"
                      confirmLabel="Evet, çıkar"
                      busyLabel="Çıkarılıyor…"
                      question="Erişimi kapatılacak."
                      ariaLabel={`${member.email} kullanıcısını dersten çıkar`}
                      onConfirm={async () => {
                        await api.delete(
                          `/courses/${courseId}/members/${member.user_id}`,
                        );
                        await reload();
                      }}
                    />
                  )
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AddMemberForm({
  courseId,
  onAdded,
}: {
  courseId: string;
  onAdded: () => void;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"student" | "instructor">("student");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post(`/courses/${courseId}/members`, { email, role });
      setEmail("");
      onAdded();
    } catch (err) {
      setError(errorMessage(err, "İşlem tamamlanamadı."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="rise mb-6">
      <form onSubmit={submit} className="flex flex-col gap-3 sm:flex-row">
        <div className="flex-1">
          <Input
            type="email"
            placeholder="ogrenci@dogus.edu.tr"
            aria-label="Katılımcı e-postası"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <select
          aria-label="Rol"
          value={role}
          onChange={(e) => setRole(e.target.value as typeof role)}
          className="h-10 rounded-lg border border-border-strong bg-surface px-3 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
        >
          <option value="student">Öğrenci</option>
          <option value="instructor">Eğitmen</option>
        </select>
        <Button type="submit" disabled={busy}>
          {busy ? "Ekleniyor…" : "Derse ekle"}
        </Button>
      </form>
      <p className="mt-2 text-xs text-fg-subtle">
        Kullanıcının sisteme daha önce giriş yapmış olması gerekir.
      </p>
      {error && (
        <div className="mt-2">
          <ErrorNote message={error} />
        </div>
      )}
    </Card>
  );
}
