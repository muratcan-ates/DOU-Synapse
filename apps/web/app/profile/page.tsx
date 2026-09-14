"use client";

import Link from "next/link";
import { useState } from "react";
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

/**
 * Satır içi bağlantı, `Button variant="secondary" size="sm"` kabuğunda.
 * `Button` bir `<button>` çizer; "Dersi aç" ise gerçek bir sayfa bağlantısıdır
 * ve `href`i korunmalıdır. Kabuk ui.tsx'teki secondary/sm ile aynı ölçüdedir.
 */
const LINK_BUTTON_SM =
  "inline-flex h-9 shrink-0 items-center justify-center rounded-xl border border-border-strong bg-surface px-3 text-[0.8125rem] font-medium text-fg transition-[color,background,border,transform] duration-200 hover:border-fg-subtle hover:bg-surface-sunken active:translate-y-px focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand";

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

      {/*
       * Hesap bilgileri tek yükselmiş kart: kimlik satırı, `dl` çiftleri ve ad
       * formu. Önceki hâl iki sütunlu, kırmızı zeminli, kenarlıklı bir paneldi
       * ve kırmızı mono avatar taşıyordu; kırmızı bu sayfada yalnız "Profili
       * kaydet"te kalır (DESIGN.md §Components "Aksan disiplini ve katman").
       */}
      <section aria-labelledby="profile-identity-title">
        <Card>
          <h2 id="profile-identity-title" className="text-lg font-semibold text-fg">
            Hesap bilgileri
          </h2>
          <p className="mt-1 text-sm text-fg-muted">
            E-posta kimlik sağlayıcınızdan gelir ve burada değiştirilemez.
          </p>

          <div className="mt-6 flex flex-wrap items-center gap-4">
            <span
              aria-hidden="true"
              className="grid h-14 w-14 shrink-0 place-items-center rounded-full bg-surface-sunken text-xl font-semibold text-fg"
            >
              {profileInitial}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-lg font-semibold text-fg">
                {profile.full_name || "Adsız profil"}
              </p>
              <p className="mt-0.5 truncate text-sm text-fg-muted">{profile.email}</p>
            </div>
            {profile.is_platform_admin && <Badge tone="info">Bilgi İşlem yöneticisi</Badge>}
          </div>

          <dl className="mt-6 divide-y divide-border border-t border-border">
            <ProfileDatum label="Hesap oluşturma" value={createdAt} />
            <ProfileDatum label="Toplam ders" value={profile.memberships.length} />
            <ProfileDatum label="Eğitmen olduğunuz ders" value={instructorCount} />
            <ProfileDatum label="Öğrenci olduğunuz ders" value={studentCount} />
          </dl>

          <form onSubmit={save} className="mt-6 max-w-2xl space-y-4 border-t border-border pt-6">
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
      </section>

      <section aria-labelledby="profile-memberships-title">
        <h2 id="profile-memberships-title" className="text-xl font-medium text-fg">
          Ders rolleri
        </h2>
        {profile.memberships.length === 0 ? (
          <p className="mt-3 text-sm text-fg-muted">Aktif ders üyeliğiniz bulunmuyor.</p>
        ) : (
          /* Satır listesi kartın içinde `divide-y`; dolgu satırlara devredilir.
             Dolgu `padding="none"` ile kapatılır — className ile `p-0` geçmek
             Tailwind çıktısında `.p-6`'ya yenilir (bkz. Card). */
          <Card padding="none" className="mt-4">
            <ul className="divide-y divide-border">
              {profile.memberships.map((membership) => (
                <li
                  key={membership.course_id}
                  className="flex flex-wrap items-center justify-between gap-3 px-6 py-4"
                >
                  <div className="min-w-0">
                    <p className="text-xs text-fg-muted">{membership.course_code}</p>
                    <p className="mt-1 text-sm font-medium text-fg">
                      {membership.course_title}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge tone={membership.role === "instructor" ? "info" : "neutral"}>
                      {roleLabel(membership.role)}
                    </Badge>
                    <Link href={`/courses/${membership.course_id}`} className={LINK_BUTTON_SM}>
                      Dersi aç
                    </Link>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </section>

      {/*
       * Görünüm tercihi profilde yaşar: ray yalnız masaüstünde görünür, dar
       * ekranda tercihe ulaşılabilecek tek yer burasıdır. Aynı kontrol iki
       * yerde de aynı depoyu yazar (lib/theme.ts), iki ayrı durum yoktur.
       * Tercih kontrolü çukur yüzeyde: bilgi kartlarıyla aynı katmanda değil.
       */}
      <section aria-labelledby="appearance-title">
        <h2 id="appearance-title" className="text-xl font-medium text-fg">
          Görünüm
        </h2>
        <Card variant="soft" className="mt-4">
          <p className="text-sm text-fg-muted">
            Tema seçiminiz yalnız bu tarayıcıda saklanır. &ldquo;Sistem&rdquo;
            seçiliyken cihazınızın gece modu ayarını izler.
          </p>
          <div className="mt-4 max-w-xs">
            <ThemeControl tone="canvas" />
          </div>
        </Card>
      </section>

      <section aria-labelledby="privacy-title">
        <h2 id="privacy-title" className="text-xl font-medium text-fg">
          Gizlilik ve hesap
        </h2>
        {/* `overflow-hidden`: satır vurgusu kartın yuvarlak köşesinden taşmasın. */}
        <Card padding="none" className="mt-4 overflow-hidden">
          <div className="divide-y divide-border">
            <Link
              href="/account"
              className="flex min-h-20 flex-col justify-center px-6 py-4 text-sm font-medium text-fg transition-colors duration-200 hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand"
            >
              Verilerimi indir veya sil
              <span className="mt-1 block text-xs font-normal text-fg-muted">
                Dışa aktarma, sohbet silme ve profil bilgilerini kaldırma
              </span>
            </Link>
            <Link
              href="/kvkk"
              className="flex min-h-20 flex-col justify-center px-6 py-4 text-sm font-medium text-fg transition-colors duration-200 hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-brand"
            >
              Kişisel veriler ve gizlilik
              <span className="mt-1 block text-xs font-normal text-fg-muted">
                İşlenen veri, saklama ve haklarınız
              </span>
            </Link>
          </div>
        </Card>
      </section>
    </div>
  );
}

/** `dl` satırı: etiket solda muted, değer sağda `font-medium` ve `tabular-nums`. */
function ProfileDatum({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3">
      <dt className="text-sm text-fg-muted">{label}</dt>
      <dd className="text-sm font-medium tabular-nums text-fg">{value}</dd>
    </div>
  );
}
