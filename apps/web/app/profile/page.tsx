"use client";

import Link from "next/link";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Field } from "@/components/field";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { usePortalProfile } from "@/components/portal/portal-profile-context";
import { Badge, Button, Card, Input } from "@/components/ui";
import { errorMessage } from "@/lib/errors";
import {
  normalizedProfileName,
  roleLabel,
  updateProfile,
  type Profile,
} from "@/lib/profile";

export default function ProfilePage() {
  return (
    <AppShell>
      <ProfileGate />
    </AppShell>
  );
}

function ProfileGate() {
  const profile = usePortalProfile();

  if (profile.error) {
    return (
      <ErrorNote
        message={profile.error}
        kind={profile.errorKind}
        requestId={profile.errorRequestId}
        onRetry={profile.reload}
      />
    );
  }
  if (profile.loading || !profile.data) {
    return <Loading label="Profiliniz hazırlanıyor…" />;
  }

  return (
    <div className="space-y-4">
      {profile.refreshError && (
        <ErrorNote
          message={profile.refreshError}
          kind={profile.errorKind}
          requestId={profile.errorRequestId}
          onRetry={profile.reload}
        />
      )}
      <ProfileContent profile={profile.data} reload={profile.reload} />
    </div>
  );
}

function ProfileContent({
  profile,
  reload,
}: {
  profile: Profile;
  reload: () => Promise<void>;
}) {
  const [fullName, setFullName] = useState(profile.full_name ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const instructorCount = profile.memberships.filter(
    (membership) => membership.role === "instructor",
  ).length;
  const studentCount = profile.memberships.length - instructorCount;

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    const normalized = normalizedProfileName(fullName);
    if (normalized.length < 2) {
      setError("Ad soyad en az 2 karakter olmalıdır.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await updateProfile({ full_name: normalized });
      setFullName(normalized);
      await reload();
      setNotice("Profil adınız güncellendi.");
    } catch (cause) {
      setError(errorMessage(cause, "Profil güncellenemedi."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Profil"
        description="Hesap bilgilerinizi ve her dersteki rolünüzü tek yerde görün."
      />

      {(notice || error) && (
        <div aria-live="polite">
          {notice && (
            <p role="status" className="text-sm text-success">
              {notice}
            </p>
          )}
          {error && <ErrorNote message={error} />}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.7fr)]">
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-medium text-fg">Hesap bilgileri</h2>
              <p className="mt-1 text-xs text-fg-muted">
                E-posta kimlik sağlayıcınızdan gelir ve burada değiştirilemez.
              </p>
            </div>
            {profile.is_platform_admin && <Badge tone="info">Platform yöneticisi</Badge>}
          </div>

          <form onSubmit={save} className="mt-6 space-y-4">
            <Field label="Ad soyad">
              {(control) => (
                <Input
                  {...control}
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  autoComplete="name"
                  minLength={2}
                  maxLength={120}
                  required
                />
              )}
            </Field>
            <Field label="E-posta">
              {(control) => (
                <Input {...control} value={profile.email} readOnly aria-readonly />
              )}
            </Field>
            <Button type="submit" aria-disabled={busy}>
              {busy ? "Kaydediliyor…" : "Profili kaydet"}
            </Button>
          </form>
        </Card>

        <Card>
          <h2 className="text-lg font-medium text-fg">Üyelik özeti</h2>
          <dl className="mt-6 grid grid-cols-3 gap-4">
            <ProfileDatum label="Toplam" value={profile.memberships.length} />
            <ProfileDatum label="Eğitmen" value={instructorCount} />
            <ProfileDatum label="Öğrenci" value={studentCount} />
          </dl>
          <p className="mt-6 text-xs text-fg-subtle">
            Hesap oluşturma: {new Intl.DateTimeFormat("tr-TR", { dateStyle: "long" }).format(new Date(profile.created_at))}
          </p>
        </Card>
      </div>

      <section aria-labelledby="profile-memberships-title">
        <h2 id="profile-memberships-title" className="text-xl font-medium text-fg">
          Ders rolleri
        </h2>
        {profile.memberships.length === 0 ? (
          <p className="mt-3 text-sm text-fg-muted">Aktif ders üyeliğiniz bulunmuyor.</p>
        ) : (
          <ul className="mt-4 overflow-hidden rounded-lg border border-border bg-surface">
            {profile.memberships.map((membership) => (
              <li
                key={membership.course_id}
                className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4 last:border-b-0"
              >
                <div>
                  <p className="font-mono text-xs text-fg-subtle">
                    {membership.course_code}
                  </p>
                  <p className="mt-1 text-sm font-medium text-fg">
                    {membership.course_title}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Badge tone={membership.role === "instructor" ? "info" : "neutral"}>
                    {roleLabel(membership.role)}
                  </Badge>
                  <Link
                    href={`/courses/${membership.course_id}`}
                    className="inline-flex min-h-11 items-center rounded-lg px-3 text-sm font-medium text-brand hover:bg-brand-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  >
                    Dersi aç
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="privacy-title">
        <h2 id="privacy-title" className="text-xl font-medium text-fg">
          Gizlilik ve hesap
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <Link
            href="/account"
            className="rounded-lg border border-border bg-surface p-5 text-sm font-medium text-fg hover:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            Verilerimi indir veya sil
            <span className="mt-1 block text-xs font-normal text-fg-muted">
              Dışa aktarma, sohbet silme ve anonimleştirme
            </span>
          </Link>
          <Link
            href="/kvkk"
            className="rounded-lg border border-border bg-surface p-5 text-sm font-medium text-fg hover:border-border-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
          >
            KVKK aydınlatma metni
            <span className="mt-1 block text-xs font-normal text-fg-muted">
              İşlenen veri, saklama ve haklarınız
            </span>
          </Link>
        </div>
      </section>
    </div>
  );
}

function ProfileDatum({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col-reverse gap-1">
      <dt className="text-xs text-fg-muted">{label}</dt>
      <dd className="font-mono text-xl text-fg">{value}</dd>
    </div>
  );
}
