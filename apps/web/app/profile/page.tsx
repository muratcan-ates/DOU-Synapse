"use client";

import Link from "next/link";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import { Field } from "@/components/field";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { usePortalProfile } from "@/components/portal/portal-profile-context";
import { Badge, Button, Input } from "@/components/ui";
import {
  normalizedProfileName,
  roleLabel,
  updateProfile,
  type Profile,
} from "@/lib/profile";
import { useSubmit } from "@/lib/use-submit";

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
  const [notice, setNotice] = useState<string | null>(null);
  const instructorCount = profile.memberships.filter(
    (membership) => membership.role === "instructor",
  ).length;
  const studentCount = profile.memberships.length - instructorCount;
  const profileInitial =
    (profile.full_name ?? "").trim().charAt(0).toLocaleUpperCase("tr-TR") || "H";

  const { busy, error, setError, submit } = useSubmit(async (normalized: string) => {
    setNotice(null);
    await updateProfile({ full_name: normalized });
    setFullName(normalized);
    await reload();
    setNotice("Profil adınız güncellendi.");
  }, "Profil güncellenemedi.");

  function save(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    // Doğrulama gönderim ÖNCESİ konuşur; kancanın hata satırını kullanır.
    const normalized = normalizedProfileName(fullName);
    if (normalized.length < 2) {
      setError("Ad soyad en az 2 karakter olmalıdır.");
      return;
    }
    void submit(normalized);
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Kimlik ve erişim"
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

      <section
        aria-labelledby="profile-identity-title"
        className="overflow-hidden rounded-xl border border-border bg-surface"
      >
        <div className="grid lg:grid-cols-[minmax(260px,0.65fr)_minmax(0,1.35fr)]">
          <div className="border-b border-border bg-brand-subtle px-5 py-6 sm:px-7 lg:border-b-0 lg:border-r">
            <div className="flex flex-wrap items-center gap-4">
              <span
                aria-hidden="true"
                className="grid h-14 w-14 place-items-center rounded-full bg-brand font-mono text-xl font-semibold text-bg"
              >
                {profileInitial}
              </span>
              <div className="min-w-0">
                <p className="truncate text-lg font-semibold text-fg">
                  {profile.full_name || "Adsız profil"}
                </p>
                <p className="mt-1 truncate text-xs text-fg-muted">{profile.email}</p>
              </div>
            </div>

            {profile.is_platform_admin && (
              <div className="mt-5">
                <Badge tone="info">Bilgi İşlem yöneticisi</Badge>
              </div>
            )}

            <div className="mt-6 border-t border-border pt-5">
              <h2 className="text-sm font-medium text-fg">Üyelik özeti</h2>
              <dl className="mt-4 grid grid-cols-3 gap-4">
                <ProfileDatum label="Toplam" value={profile.memberships.length} />
                <ProfileDatum label="Eğitmen" value={instructorCount} />
                <ProfileDatum label="Öğrenci" value={studentCount} />
              </dl>
              <p className="mt-5 text-xs text-fg-subtle">
                Hesap oluşturma: {new Intl.DateTimeFormat("tr-TR", { dateStyle: "long" }).format(new Date(profile.created_at))}
              </p>
            </div>
          </div>

          <div className="px-5 py-6 sm:px-8 sm:py-8">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 id="profile-identity-title" className="text-lg font-medium text-fg">
                  Hesap bilgileri
                </h2>
                <p className="mt-1 text-xs text-fg-muted">
                  E-posta kimlik sağlayıcınızdan gelir ve burada değiştirilemez.
                </p>
              </div>
            </div>

            <form onSubmit={save} className="mt-6 max-w-2xl space-y-4">
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
          </div>
        </div>
      </section>

      <section aria-labelledby="profile-memberships-title">
        <h2 id="profile-memberships-title" className="text-xl font-medium text-fg">
          Ders rolleri
        </h2>
        {profile.memberships.length === 0 ? (
          <p className="mt-3 text-sm text-fg-muted">Aktif ders üyeliğiniz bulunmuyor.</p>
        ) : (
          <ul className="mt-4 border-y border-border">
            {profile.memberships.map((membership) => (
              <li
                key={membership.course_id}
                className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-1 py-4 last:border-b-0 sm:px-3"
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
        <div className="mt-4 border-y border-border">
          <Link
            href="/account"
            className="flex min-h-20 flex-col justify-center border-b border-border px-1 py-4 text-sm font-medium text-fg hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand sm:px-3"
          >
            Verilerimi indir veya sil
            <span className="mt-1 block text-xs font-normal text-fg-muted">
              Dışa aktarma, sohbet silme ve anonimleştirme
            </span>
          </Link>
          <Link
            href="/kvkk"
            className="flex min-h-20 flex-col justify-center px-1 py-4 text-sm font-medium text-fg hover:bg-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand sm:px-3"
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
