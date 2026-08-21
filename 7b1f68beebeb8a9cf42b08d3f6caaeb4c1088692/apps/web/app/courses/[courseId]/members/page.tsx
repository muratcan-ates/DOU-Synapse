"use client";

/** Katılımcı yönetimi (yalnız eğitmen). API: GET/POST/DELETE /courses/{id}/members */

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, getStoredUser } from "@/lib/api";
import type { Member } from "@/lib/types";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { Badge, Button, Card, EmptyState, Input } from "@/components/ui";

export default function MembersPage() {
  return (
    <AppShell>
      <MembersView />
    </AppShell>
  );
}

function MembersView() {
  const { courseId } = useParams<{ courseId: string }>();
  const [members, setMembers] = useState<Member[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const me = getStoredUser();

  const load = useCallback(() => {
    api
      .get<Member[]>(`/courses/${courseId}/members`)
      .then((data) => {
        setMembers(data);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : "Bağlantı kurulamadı."),
      );
  }, [courseId]);

  useEffect(load, [load]);

  return (
    <div>
      <CourseNav courseId={courseId} />

      <div className="rise mb-6">
        <h1 className="text-3xl font-semibold tracking-tight text-fg">
          Katılımcılar
        </h1>
        <p className="mt-1 text-sm text-fg-muted">
          Öğrenciler yalnızca kayıtlı oldukları dersin materyalini görür; asistan
          da yalnız o materyalden cevap verir.
        </p>
      </div>

      <AddMemberForm courseId={courseId} onAdded={load} />

      {error && <p className="mb-4 text-sm text-danger">{error}</p>}
      {members === null && !error && (
        <p className="text-sm text-fg-muted">Yükleniyor…</p>
      )}

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
                  {member.user_id === me?.id && (
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
                  member.user_id !== me?.id && (
                    <RevokeButton
                      courseId={courseId}
                      userId={member.user_id}
                      onRevoked={load}
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
      setError(err instanceof ApiError ? err.message : "İşlem tamamlanamadı.");
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
      {error && <p className="mt-2 text-sm text-danger">{error}</p>}
    </Card>
  );
}

function RevokeButton({
  courseId,
  userId,
  onRevoked,
}: {
  courseId: string;
  userId: string;
  onRevoked: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  if (!confirming) {
    return (
      <Button variant="ghost" onClick={() => setConfirming(true)}>
        Çıkar
      </Button>
    );
  }

  return (
    <span className="flex items-center gap-2">
      <span className="text-xs text-fg-muted">Emin misiniz?</span>
      <Button
        variant="danger"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await api.delete(`/courses/${courseId}/members/${userId}`);
            onRevoked();
          } finally {
            setBusy(false);
            setConfirming(false);
          }
        }}
      >
        Evet, çıkar
      </Button>
      <Button variant="ghost" onClick={() => setConfirming(false)}>
        Vazgeç
      </Button>
    </span>
  );
}
