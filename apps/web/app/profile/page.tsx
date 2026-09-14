"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronRightIcon, ShieldIcon, UserIcon } from "@/components/icons";
import { AppShell } from "@/components/app-shell";
import { Field } from "@/components/field";
import { ErrorNote, Loading } from "@/components/page-state";
import { usePortalProfile } from "@/components/portal/portal-profile-context";
import { Badge, Button, Input } from "@/components/ui";
import {
  normalizedProfileName,
  roleLabel,
  updateProfile,
  type Profile,
} from "@/lib/profile";
import { useSubmit } from "@/lib/use-submit";

const LINK_BUTTON_SM =
  "inline-flex min-h-11 shrink-0 items-center justify-center gap-1 rounded-lg px-3 text-sm font-semibold text-brand motion-safe:transition-colors hover:bg-brand-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

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
  const courseRoles = Array.from(
    new Set(profile.memberships.map((membership) => roleLabel(membership.role))),
  ).join(" · ");
  const nameParts = (profile.full_name ?? "").trim().split(/\s+/).filter(Boolean);
  const profileInitial = (
    (nameParts[0]?.charAt(0) ?? "H") +
    (nameParts.length > 1 ? nameParts.at(-1)!.charAt(0) : "")
  ).toLocaleUpperCase("tr-TR");
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
    <div className="mx-auto max-w-[820px] space-y-6">
      <section aria-labelledby="profile-identity-title" className="overflow-hidden rounded-[24px] bg-surface shadow-e1">
        <div className="relative h-28 border-b border-brand/10 bg-brand-subtle">
          <Link href="/dashboard" aria-label="Genel bakışa dön" className="absolute top-3 left-4 grid h-11 w-11 place-items-center rounded-full text-brand motion-safe:transition-colors hover:bg-surface/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
            <ChevronRightIcon size={23} className="rotate-180" />
          </Link>
          <h1 className="pt-5 text-center text-[1.4375rem] font-semibold tracking-tight text-fg">Profil</h1>
        </div>
        <div className="relative px-5 pb-1 sm:px-7">
          <span aria-hidden="true" className="relative mx-auto -mt-11 grid h-22 w-22 place-items-center rounded-full border-4 border-surface bg-brand-subtle text-[1.875rem] font-semibold tracking-tight text-brand">{profileInitial}</span>
          <div className="mt-4 text-center">
            <h2 id="profile-identity-title" className="min-w-0 text-[1.6875rem] leading-tight font-semibold tracking-tight text-fg [overflow-wrap:anywhere] sm:text-[1.875rem]">{profile.full_name || "Adsız profil"}</h2>
            {courseRoles && <p className="mt-2 text-base text-fg-muted">{courseRoles}</p>}
            <p className="mt-2 text-sm text-fg-muted [overflow-wrap:anywhere]">{profile.email}</p>
            {profile.is_platform_admin && <div className="mt-3"><Badge tone="info">Bilgi İşlem yöneticisi</Badge></div>}
            <Link href="#profile-settings" className="mt-3 inline-flex min-h-11 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold text-brand motion-safe:transition-colors hover:bg-brand-subtle focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"><UserIcon size={17} />Profili düzenle</Link>
          </div>
          <dl className="mt-4 border-t border-dashed border-border">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-4">
              <dt className="text-sm text-fg-muted">Hesap oluşturma</dt>
              <dd className="text-sm font-semibold text-fg">{createdAt}</dd>
            </div>
          </dl>
        </div>
      </section>

      {(notice || error) && (
        <div aria-live="polite">
          {notice && <p role="status" className="rounded-xl bg-success-bg px-5 py-4 text-base text-success">{notice}</p>}
          {error && <ErrorNote message={error} />}
        </div>
      )}

      <section id="profile-settings" aria-labelledby="profile-settings-title" className="scroll-mt-28 overflow-hidden rounded-[22px] bg-surface shadow-e1">
        <div className="px-5 pt-6 sm:px-7">
          <h2 id="profile-settings-title" className="text-[1.3125rem] font-semibold tracking-tight text-fg">Hesap bilgileri</h2>
        </div>
        <form onSubmit={save} className="px-5 pb-5 sm:px-7 sm:pb-6 [&_input]:text-base">
          <div className="border-b border-dashed border-border py-5">
            <Field label="Ad soyad">{(control) => <Input {...control} className="min-h-12 rounded-xl" value={fullName} onChange={(event) => setFullName(event.target.value)} autoComplete="name" minLength={2} maxLength={120} required />}</Field>
          </div>
          <div className="py-5">
            <Field label="E-posta" describedBy="profile-email-help">{(control) => <Input {...control} className="min-h-12 rounded-xl bg-surface-sunken text-fg-muted" value={profile.email} readOnly aria-readonly />}</Field>
            <p id="profile-email-help" className="mt-2 text-sm leading-6 text-fg-muted">E-posta kimlik sağlayıcından gelir ve burada değiştirilemez.</p>
          </div>
          <div className="flex justify-end border-t border-border pt-4"><Button type="submit" className="min-h-11 w-full rounded-xl sm:w-auto sm:px-6" aria-disabled={busy}>{busy ? "Kaydediliyor…" : "Profili kaydet"}</Button></div>
        </form>
      </section>

      <section aria-labelledby="profile-memberships-title" className="overflow-hidden rounded-[22px] bg-surface shadow-e1">
        <div className="px-5 pt-6 pb-4 sm:px-7">
          <h2 id="profile-memberships-title" className="text-[1.3125rem] font-semibold tracking-tight text-fg">Ders rolleri</h2>
          <p className="mt-2 text-sm leading-6 text-fg-muted">Her dersteki yetkilerin üyelik rolüne göre belirlenir.</p>
        </div>
        {profile.memberships.length === 0 ? (
          <p className="px-5 pt-1 pb-7 text-base text-fg-muted sm:px-7">Aktif ders üyeliğiniz bulunmuyor.</p>
        ) : (
          <ul className="px-5 pb-2 sm:px-7">
            {profile.memberships.map((membership) => (
              <li key={membership.course_id} className="flex items-center gap-3 border-t border-dashed border-border py-4">
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-fg-muted [overflow-wrap:anywhere]">{membership.course_code}</p>
                  <p className="mt-1 text-base font-semibold text-fg [overflow-wrap:anywhere]">{membership.course_title}</p>
                  <p className="mt-1.5 text-sm text-fg-muted">{roleLabel(membership.role)}</p>
                </div>
                <Link href={`/courses/${membership.course_id}`} className={LINK_BUTTON_SM}>Dersi aç<ChevronRightIcon size={17} /></Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="privacy-title" className="overflow-hidden rounded-[22px] bg-surface shadow-e1">
        <h2 id="privacy-title" className="px-5 pt-6 pb-4 text-[1.3125rem] font-semibold tracking-tight text-fg sm:px-7">Gizlilik ve hesap</h2>
        <div className="divide-y divide-border">
          {[
            { href: "/account", title: "Verilerimi indir veya sil", description: "Dışa aktarma, sohbet ve profil bilgileri" },
            { href: "/kvkk", title: "Kişisel veriler ve gizlilik", description: "İşlenen veri, saklama ve hakların" },
          ].map(({ href, title, description }) => (
            <Link key={href} href={href} className="group flex min-h-24 items-center gap-3 px-5 py-4 motion-safe:transition-colors hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand sm:gap-4 sm:px-7">
              <span aria-hidden="true" className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-brand-subtle text-brand"><ShieldIcon size={21} /></span>
              <span className="min-w-0 flex-1"><span className="block text-base font-semibold text-fg">{title}</span><span className="mt-1 block text-sm leading-6 text-fg-muted">{description}</span></span>
              <ChevronRightIcon size={18} className="shrink-0 text-brand motion-safe:transition-transform group-hover:translate-x-1" />
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
