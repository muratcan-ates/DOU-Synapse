"use client";

import { useRef, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { usePortalProfile } from "@/components/portal/portal-profile-context";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Card } from "@/components/ui";
import { adminTabIndexAfterKey } from "@/lib/admin";
import { AdminOverviewSection } from "@/components/admin/admin-overview";
import { AdminUsersPanel } from "@/components/admin/admin-users-panel";
import { AdminCoursesPanel } from "@/components/admin/admin-courses-panel";
import { AdminRequestsPanel } from "@/components/admin/admin-requests-panel";
import { AdminIngestionPanel } from "@/components/admin/admin-ingestion-panel";

type AdminTab = "users" | "courses" | "requests" | "ingestion";

export default function AdminPage() {
  return (
    <AppShell>
      <AdminGate />
    </AppShell>
  );
}

/**
 * Kritik kapı: profil sunucudan doğrulanmadan AdminContent mount olmaz.
 * Böylece yönetici olmayan tarayıcı dört liste isteğini kısa süreliğine bile atmaz.
 */
function AdminGate() {
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
    return <Loading label="Bilgi İşlem yetkiniz doğrulanıyor…" />;
  }
  if (!profile.data.is_platform_admin) {
    return (
      <Card variant="soft">
        <h1 className="text-xl font-semibold text-fg">Bu alana erişiminiz yok</h1>
        <p className="mt-2 text-sm text-fg-muted">
          Bilgi İşlem paneli yalnız platform yöneticilerine açıktır. Ders eğitmeni
          olmak Bilgi İşlem yetkisi vermez.
        </p>
      </Card>
    );
  }

  return <AdminContent />;
}

function AdminContent() {
  const [activeTab, setActiveTab] = useState<AdminTab>("users");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const tabs: Array<{ id: AdminTab; label: string }> = [
    { id: "users", label: "Kullanıcılar" },
    { id: "courses", label: "Dersler" },
    { id: "requests", label: "AI kullanım kayıtları" },
    { id: "ingestion", label: "İşleme işleri" },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        compact
        title="Bilgi İşlem"
        description="Platform sağlığını ve işletim metriklerini akademik içeriğe erişmeden izleyin."
      />

      <AdminOverviewSection />

      <AdminSecuritySection />

      <section aria-labelledby="admin-data-title">
        <div className="mb-4">
          <h2 id="admin-data-title" className="text-xl font-semibold text-fg">
            Teknik kayıtlar
          </h2>
          <p className="mt-1 text-sm text-fg-muted">
            Kayıtlarda soru, yanıt, kaynak metni veya kullanıcı bağlantısı
            gösterilmez. E-posta yalnız kullanıcı dizininde maskelenir.
          </p>
        </div>

        <div
          role="tablist"
          aria-label="Yönetim veri kümeleri"
          className="mb-6 flex gap-2 overflow-x-auto rounded-2xl border border-border bg-surface p-2 shadow-e1"
        >
          {tabs.map((tab, index) => (
            <button
              key={tab.id}
              ref={(element) => {
                tabRefs.current[index] = element;
              }}
              id={`admin-tab-${tab.id}`}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls="admin-tab-panel"
              tabIndex={activeTab === tab.id ? 0 : -1}
              onClick={() => setActiveTab(tab.id)}
              onKeyDown={(event) => {
                const next = adminTabIndexAfterKey(index, event.key, tabs.length);
                if (next === null) return;
                event.preventDefault();
                setActiveTab(tabs[next]!.id);
                tabRefs.current[next]?.focus();
              }}
              className={
                activeTab === tab.id
                  ? "min-h-11 shrink-0 rounded-xl bg-brand-subtle px-4 text-sm font-semibold text-brand transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  : "min-h-11 shrink-0 rounded-xl px-4 text-sm font-medium text-fg-muted transition-colors hover:bg-surface-sunken hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
              }
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div
          id="admin-tab-panel"
          role="tabpanel"
          aria-labelledby={`admin-tab-${activeTab}`}
          tabIndex={0}
          className="rise focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
        >
          {activeTab === "users" && <AdminUsersPanel />}
          {activeTab === "courses" && <AdminCoursesPanel />}
          {activeTab === "requests" && <AdminRequestsPanel />}
          {activeTab === "ingestion" && <AdminIngestionPanel />}
        </div>
      </section>
    </div>
  );
}

/** Mevcut erişim sınırları; olay akışı bağlıymış gibi durum üretmez. */
function AdminSecuritySection() {
  return (
    <section aria-labelledby="admin-security-title">
      <h2 id="admin-security-title" className="text-xl font-semibold text-fg">Güvenlik</h2>
      <div className="mt-4 overflow-hidden rounded-[20px] bg-surface shadow-e1">
        <dl className="divide-y divide-border px-5 sm:px-6">
          <div className="grid gap-2 py-4 sm:grid-cols-[12rem_1fr] sm:gap-6">
            <dt className="text-sm font-semibold text-fg">Yönetici erişimi</dt>
            <dd className="text-sm leading-6 text-fg-muted">Platform yöneticisi yetkisi, ders eğitmenliğinden bağımsız olarak sunucuda doğrulanır.</dd>
          </div>
          <div className="grid gap-2 py-4 sm:grid-cols-[12rem_1fr] sm:gap-6">
            <dt className="text-sm font-semibold text-fg">Kayıt gizliliği</dt>
            <dd className="text-sm leading-6 text-fg-muted">Kullanıcı dizininde e-postalar maskelenir. AI kullanım kayıtları soru, yanıt ve kaynak metni içermez.</dd>
          </div>
        </dl>
        <div className="border-t border-border bg-surface-sunken px-5 py-4 sm:px-6">
          <dl className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
            <dt className="text-sm font-semibold text-fg">Güvenlik olay akışı</dt>
            <dd className="text-sm font-medium text-fg-muted">Henüz bağlı değil</dd>
          </dl>
          <p className="mt-2 text-sm leading-6 text-fg-muted">Bu panelde güvenlik alarmları ve olay listesi henüz gösterilmiyor.</p>
        </div>
      </div>
    </section>
  );
}

