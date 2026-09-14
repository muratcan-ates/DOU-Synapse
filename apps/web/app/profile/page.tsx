"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronRightIcon, ShieldIcon, UserIcon } from "@/components/icons";
import { AppShell } from "@/components/app-shell";
import { Field } from "@/components/field";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { ThemeControl } from "@/components/theme-control";
import { usePortalProfile } from "@/components/portal/portal-profile-context";
import { Badge, Button, Card, Input } from "@/components/ui";
import {
  normalizedProfileName,
  roleLabel,
  updateProfile,
  type Profile,
} from "@/lib/profile";
import { useSubmit } from "@/lib/use-submit";

const LINK_BUTTON_SM =
  "inline-flex min-h-11 shrink-0 items-center justify-center gap-1 rounded-xl border border-border-strong bg-surface px-4 text-sm font-medium text-fg motion-safe:transition-colors hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

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
  const createdAt = new Intl.DateTimeFormat("tr-TR", { dateStyle: "long" }).format(
    new Date(profile.created_at),
  );

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
    <div className="space-y-7">
      <PageHeader eyebrow="Hesabım" title="Profil" description="Kimlik bilgilerin, derslerin ve kişisel tercihlerin." />
      {(notice || error) && (
        <div aria-live="polite">
          {notice && <p role="status" className="rounded-xl bg-success-bg px-5 py-4 text-base text-success">{notice}</p>}
          {error && <ErrorNote message={error} />}
        </div>
      )}

      <section aria-labelledby="profile-identity-title" className="overflow-hidden rounded-[20px] border border-border bg-surface shadow-e1">
        <div className="flex min-h-14 flex-wrap items-center justify-between gap-2 bg-brand-subtle px-5 py-3 sm:px-7">
          <p className="text-sm font-semibold text-brand">DOU-Synapse · Doğuş Üniversitesi</p>
          {profile.is_platform_admin && <Badge tone="info">Bilgi İşlem yöneticisi</Badge>}
        </div>
        <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:p-7">
          <span aria-hidden="true" className="grid h-20 w-20 shrink-0 place-items-center rounded-full border-4 border-surface bg-brand-subtle text-[30px] font-semibold text-brand shadow-e1">{profileInitial}</span>
          <div className="min-w-0 flex-1">
            <h2 id="profile-identity-title" className="break-words text-[26px] leading-tight font-semibold tracking-tight text-fg">{profile.full_name || "Adsız profil"}</h2>
            <p className="mt-2 break-words text-base text-fg-muted">{profile.email}</p>
            <p className="mt-2 text-sm text-fg-muted">Hesap oluşturma: {createdAt}</p>
          </div>
          <Link href="#profile-settings" className={LINK_BUTTON_SM}><UserIcon size={18} />Profili düzenle</Link>
        </div>
        <dl className="grid grid-cols-3 border-t border-border bg-bg/50">
          {[
            { label: "Toplam ders", value: profile.memberships.length },
            { label: "Eğitmen olarak", value: instructorCount },
            { label: "Öğrenci olarak", value: studentCount },
          ].map(({ label, value }) => (
            <div key={label} className="px-3 py-5 text-center sm:px-6">
              <dt className="text-[13px] text-fg-muted sm:text-sm">{label}</dt>
              <dd className="mt-1 text-2xl font-semibold tabular-nums text-fg">{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <div className="grid items-start gap-7 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-7">
          <section id="profile-settings" aria-labelledby="profile-settings-title" className="scroll-mt-28">
            <Card>
              <h2 id="profile-settings-title" className="text-xl font-semibold text-fg">Hesap bilgileri</h2>
              <p className="mt-2 text-base leading-7 text-fg-muted">E-posta kimlik sağlayıcından gelir ve burada değiştirilemez.</p>
              <form onSubmit={save} className="mt-6 space-y-5">
                <Field label="Ad soyad">{(control) => <Input {...control} value={fullName} onChange={(event) => setFullName(event.target.value)} autoComplete="name" minLength={2} maxLength={120} required />}</Field>
                <Field label="E-posta">{(control) => <Input {...control} value={profile.email} readOnly aria-readonly />}</Field>
                <div className="border-t border-border pt-5"><Button type="submit" aria-disabled={busy}>{busy ? "Kaydediliyor…" : "Profili kaydet"}</Button></div>
              </form>
            </Card>
          </section>

          <section aria-labelledby="profile-memberships-title">
            <Card padding="none" className="overflow-hidden">
              <div className="border-b border-border px-5 py-5 sm:px-6">
                <h2 id="profile-memberships-title" className="text-xl font-semibold text-fg">Ders rolleri</h2>
                <p className="mt-1 text-sm leading-6 text-fg-muted">Her dersteki yetkilerin üyelik rolüne göre belirlenir.</p>
              </div>
              {profile.memberships.length === 0 ? (
                <p className="px-6 py-8 text-base text-fg-muted">Aktif ders üyeliğiniz bulunmuyor.</p>
              ) : (
                <ul className="divide-y divide-border">
                  {profile.memberships.map((membership) => (
                    <li key={membership.course_id} className="flex flex-wrap items-center justify-between gap-4 px-5 py-5 sm:px-6">
                      <div className="min-w-0 flex-1 basis-[180px]">
                        <p className="text-sm text-fg-muted">{membership.course_code}</p>
                        <p className="mt-1 break-words text-base font-semibold text-fg">{membership.course_title}</p>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge tone={membership.role === "instructor" ? "info" : "neutral"}>{roleLabel(membership.role)}</Badge>
                        <Link href={`/courses/${membership.course_id}`} className={LINK_BUTTON_SM}>Dersi aç<ChevronRightIcon size={16} /></Link>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </section>
        </div>

        <aside className="space-y-7">
          <section aria-labelledby="appearance-title">
            <Card>
              <h2 id="appearance-title" className="text-xl font-semibold text-fg">Görünüm</h2>
              <p className="mt-2 text-sm leading-6 text-fg-muted">Tema tercihin bu tarayıcıda saklanır. Sistem seçeneği cihazının görünümünü izler.</p>
              <div className="mt-5"><ThemeControl tone="canvas" /></div>
            </Card>
          </section>
          <section aria-labelledby="privacy-title">
            <Card padding="none" className="overflow-hidden">
              <div className="px-5 py-5 sm:px-6">
                <ShieldIcon className="mb-3 text-brand" size={24} />
                <h2 id="privacy-title" className="text-xl font-semibold text-fg">Gizlilik ve hesap</h2>
              </div>
              <div className="divide-y divide-border border-t border-border">
                {[
                  { href: "/account", title: "Verilerimi indir veya sil", description: "Dışa aktarma, sohbet ve profil bilgileri" },
                  { href: "/kvkk", title: "Kişisel veriler ve gizlilik", description: "İşlenen veri, saklama ve hakların" },
                ].map(({ href, title, description }) => (
                  <Link key={href} href={href} className="group flex min-h-24 items-center gap-3 px-5 py-4 motion-safe:transition-colors hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand sm:px-6">
                    <span className="min-w-0 flex-1"><span className="block text-base font-medium text-fg">{title}</span><span className="mt-1 block text-sm leading-6 text-fg-muted">{description}</span></span>
                    <ChevronRightIcon size={18} className="shrink-0 text-fg-muted" />
                  </Link>
                ))}
              </div>
            </Card>
          </section>
        </aside>
      </div>
    </div>
  );
}
