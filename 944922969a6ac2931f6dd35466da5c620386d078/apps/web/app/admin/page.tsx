"use client";

import { useCallback, useState } from "react";
import { AppShell } from "@/components/app-shell";
import {
  AdminDataTable,
  AdminPagination,
  type AdminColumn,
} from "@/components/portal/admin-data-table";
import { usePortalProfile } from "@/components/portal/portal-profile-context";
import { PortalMetrics } from "@/components/portal/portal-metrics";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, Input } from "@/components/ui";
import {
  adminDate,
  getAdminCourses,
  getAdminIngestionJobs,
  getAdminOverview,
  getAdminRequestLogs,
  getAdminUsers,
  type AdminCourse,
  type AdminIngestionJob,
  type AdminRequestLog,
  type AdminUser,
  type IngestionStatus,
  type RequestStatus,
} from "@/lib/admin";
import { useResource, type Resource } from "@/lib/use-resource";

const PAGE_SIZE = 25;
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
    return <Loading label="Yönetici yetkiniz doğrulanıyor…" />;
  }
  if (!profile.data.is_platform_admin) {
    return (
      <Card>
        <h1 className="text-xl font-medium text-fg">Bu alana erişiminiz yok</h1>
        <p className="mt-2 text-sm text-fg-muted">
          Sistem yönetimi yalnız platform yöneticilerine açıktır. Ders eğitmeni
          olmak platform yöneticisi yetkisi vermez.
        </p>
      </Card>
    );
  }

  return <AdminContent />;
}

function AdminContent() {
  const [activeTab, setActiveTab] = useState<AdminTab>("users");
  const tabs: Array<{ id: AdminTab; label: string }> = [
    { id: "users", label: "Kullanıcılar" },
    { id: "courses", label: "Dersler" },
    { id: "requests", label: "AI kullanım kayıtları" },
    { id: "ingestion", label: "İşleme işleri" },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Sistem yönetimi"
        description="Platform sağlığını ve işletim metriklerini salt okunur olarak izleyin."
      />

      <AdminOverviewSection />

      <section aria-labelledby="admin-data-title">
        <div className="mb-4">
          <h2 id="admin-data-title" className="text-xl font-medium text-fg">
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
          className="mb-4 flex flex-wrap gap-2 border-b border-border pb-3"
        >
          {tabs.map((tab) => (
            <button
              key={tab.id}
              id={`admin-tab-${tab.id}`}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls="admin-tab-panel"
              onClick={() => setActiveTab(tab.id)}
              className={
                activeTab === tab.id
                  ? "min-h-11 rounded-lg bg-brand-subtle px-4 text-sm font-medium text-brand focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                  : "min-h-11 rounded-lg px-4 text-sm font-medium text-fg-muted hover:bg-surface hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
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
          className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
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

function AdminOverviewSection() {
  const fetchOverview = useCallback(() => getAdminOverview(), []);
  const resource = useResource(fetchOverview, []);

  if (resource.error) {
    return (
      <ErrorNote
        message={resource.error}
        kind={resource.errorKind}
        requestId={resource.errorRequestId}
        onRetry={resource.reload}
      />
    );
  }
  if (resource.loading || !resource.data) {
    return <Loading label="Sistem özeti alınıyor…" />;
  }

  const data = resource.data;
  return (
    <section aria-labelledby="system-overview-title" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="system-overview-title" className="text-xl font-medium text-fg">
            Platform durumu
          </h2>
          <p className="mt-1 text-sm text-fg-muted">
            Son 24 saatlik kullanım ve anlık servis görünümü
          </p>
        </div>
        <p className="text-xs text-fg-subtle">
          Ölçüm: {adminDate(data.measured_at)}
        </p>
      </div>

      {resource.refreshError && (
        <ErrorNote
          message={resource.refreshError}
          kind={resource.errorKind}
          requestId={resource.errorRequestId}
          onRetry={resource.reload}
        />
      )}

      <div className="flex flex-wrap gap-2" aria-label="Servis sağlık durumları">
        <HealthBadge label="Uygulama" status={data.status} />
        <HealthBadge label="Veritabanı" status={data.database_status} />
        <HealthBadge label="Embedding" status={data.embedding_status} />
      </div>

      <PortalMetrics
        items={[
          { label: "Kullanıcı", value: data.users_total },
          { label: "Ders", value: data.courses_total },
          { label: "Kaynak", value: data.documents_total },
          { label: "Aktif üyelik", value: data.active_memberships_total },
        ]}
      />

      <Card>
        <dl className="grid gap-5 sm:grid-cols-2 lg:grid-cols-5">
          <OverviewDatum
            label="Sohbet turu"
            value={data.chat_turns_24h}
            detail="Son 24 saat"
          />
          <OverviewDatum
            label="P95 gecikme"
            value={data.p95_latency_ms === null ? "-" : `${Math.round(data.p95_latency_ms)} ms`}
          />
          <OverviewDatum label="Token" value={data.tokens_24h.toLocaleString("tr-TR")} />
          <OverviewDatum label="İşleniyor" value={data.ingestion_processing} />
          <OverviewDatum label="İşleme hatası" value={data.ingestion_failed} />
        </dl>
      </Card>
    </section>
  );
}

function HealthBadge({ label, status }: { label: string; status: string }) {
  const normalized = status.toLowerCase();
  const tone =
    normalized === "ok" || normalized === "ready" || normalized === "healthy"
      ? "success"
      : normalized === "warming" || normalized === "degraded" || normalized === "disabled"
        ? "warning"
        : "danger";
  return (
    <Badge tone={tone}>
      {label}: {healthStatusLabel(normalized)}
    </Badge>
  );
}

function healthStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    ok: "Hazır",
    ready: "Hazır",
    healthy: "Sağlıklı",
    warming: "Hazırlanıyor",
    degraded: "Kısıtlı",
    disabled: "Kapalı",
    failed: "Hata",
    unavailable: "Ulaşılamıyor",
  };
  return labels[status] ?? status;
}

function OverviewDatum({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <div className="flex flex-col-reverse gap-1">
      <dt className="text-xs text-fg-muted">
        {label}
        {detail ? ` (${detail})` : ""}
      </dt>
      <dd className="font-mono text-lg text-fg">{value}</dd>
    </div>
  );
}

function AdminUsersPanel() {
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const fetchUsers = useCallback(
    () => getAdminUsers({ limit: PAGE_SIZE, offset, search: search || undefined }),
    [offset, search],
  );
  const resource = useResource(fetchUsers, [offset, search]);

  if (resource.error) {
    return (
      <ErrorNote
        message={resource.error}
        kind={resource.errorKind}
        requestId={resource.errorRequestId}
        onRetry={resource.reload}
      />
    );
  }
  if (resource.loading || !resource.data) return <Loading label="Kullanıcılar alınıyor…" />;

  const columns: AdminColumn<AdminUser>[] = [
    {
      key: "name",
      header: "Kullanıcı",
      render: (item) => (
        <span>
          <span className="block font-medium">{item.full_name || "Adsız profil"}</span>
          <span className="block text-xs text-fg-muted">{item.masked_email}</span>
        </span>
      ),
    },
    {
      key: "admin",
      header: "Yetki",
      render: (item) =>
        item.is_platform_admin ? <Badge tone="info">Platform yöneticisi</Badge> : "Kullanıcı",
    },
    {
      key: "courses",
      header: "Aktif ders",
      render: (item) => item.active_course_count,
    },
    {
      key: "created",
      header: "Oluşturma",
      render: (item) => adminDate(item.created_at),
    },
  ];

  return (
    <AdminListFrame resource={resource}>
      <AdminTextFilter
        label="Kullanıcı ara"
        placeholder="Ad veya maskeli e-posta"
        appliedValue={search}
        onApply={(value) => {
          setOffset(0);
          setSearch(value);
        }}
      />
      <AdminDataTable
        title="Kullanıcılar"
        description="E-posta adresleri maskelidir; yetki değişikliği bu salt okunur ekrandan yapılamaz."
        items={resource.data.items}
        columns={columns}
        rowKey={(item) => item.id}
        emptyMessage="Kullanıcı kaydı bulunamadı."
      />
      <AdminPagination
        total={resource.data.total}
        offset={resource.data.offset}
        limit={resource.data.limit}
        busy={resource.loading}
        onChange={setOffset}
      />
    </AdminListFrame>
  );
}

function AdminCoursesPanel() {
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const fetchCourses = useCallback(
    () => getAdminCourses({ limit: PAGE_SIZE, offset, search: search || undefined }),
    [offset, search],
  );
  const resource = useResource(fetchCourses, [offset, search]);

  if (resource.error) {
    return (
      <ErrorNote
        message={resource.error}
        kind={resource.errorKind}
        requestId={resource.errorRequestId}
        onRetry={resource.reload}
      />
    );
  }
  if (resource.loading || !resource.data) return <Loading label="Dersler alınıyor…" />;

  const columns: AdminColumn<AdminCourse>[] = [
    {
      key: "course",
      header: "Ders",
      render: (item) => (
        <span>
          <span className="block font-mono text-xs text-fg-muted">{item.code}</span>
          <span className="block font-medium">{item.title}</span>
        </span>
      ),
    },
    { key: "creator", header: "Oluşturan", render: (item) => item.creator_name },
    { key: "members", header: "Aktif üye", render: (item) => item.active_member_count },
    {
      key: "documents",
      header: "Kaynak",
      render: (item) =>
        item.documents_failed > 0
          ? `${item.documents_total} (${item.documents_failed} hatalı)`
          : item.documents_total,
    },
    { key: "created", header: "Oluşturma", render: (item) => adminDate(item.created_at) },
  ];

  return (
    <AdminListFrame resource={resource}>
      <AdminTextFilter
        label="Ders ara"
        placeholder="Ders kodu veya adı"
        appliedValue={search}
        onApply={(value) => {
          setOffset(0);
          setSearch(value);
        }}
      />
      <AdminDataTable
        title="Dersler"
        description="Yalnız işletim metaverisi gösterilir; ders içeriği ve akademik yanıtlar açılmaz."
        items={resource.data.items}
        columns={columns}
        rowKey={(item) => item.id}
        emptyMessage="Ders kaydı bulunamadı."
      />
      <AdminPagination
        total={resource.data.total}
        offset={resource.data.offset}
        limit={resource.data.limit}
        busy={resource.loading}
        onChange={setOffset}
      />
    </AdminListFrame>
  );
}

function AdminRequestsPanel() {
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState<RequestStatus | "">("");
  const [route, setRoute] = useState("");
  const fetchRequests = useCallback(
    () =>
      getAdminRequestLogs({
        limit: PAGE_SIZE,
        offset,
        status: status || undefined,
        route: route || undefined,
      }),
    [offset, route, status],
  );
  const resource = useResource(fetchRequests, [offset, route, status]);

  if (resource.error) {
    return (
      <ErrorNote
        message={resource.error}
        kind={resource.errorKind}
        requestId={resource.errorRequestId}
        onRetry={resource.reload}
      />
    );
  }
  if (resource.loading || !resource.data) {
    return <Loading label="AI kullanım kayıtları alınıyor…" />;
  }

  const columns: AdminColumn<AdminRequestLog>[] = [
    { key: "time", header: "Zaman", render: (item) => adminDate(item.created_at) },
    {
      key: "route",
      header: "Uç",
      render: (item) => <span className="font-mono text-xs">{item.route}</span>,
    },
    {
      key: "context",
      header: "Bağlam",
      render: (item) => (
        <span>
          <span className="block">{item.course_code}</span>
          <span className="block font-mono text-xs text-fg-muted">
            {item.mode}
          </span>
        </span>
      ),
    },
    {
      key: "result",
      header: "Sonuç",
      render: (item) => (
        <span>
          <span className="block">{requestStatusLabel(item.status)}</span>
          <span className="block font-mono text-xs text-fg-muted">
            HTTP {item.http_status}
          </span>
        </span>
      ),
    },
    {
      key: "performance",
      header: "Performans",
      render: (item) => (
        <span className="font-mono text-xs">
          {Math.round(item.latency_ms)} ms
          <span className="block text-fg-muted">
            {item.token_count === null ? "Token yok" : `${item.token_count} token`}
          </span>
        </span>
      ),
    },
    {
      key: "cache",
      header: "Önbellek",
      render: (item) => (item.cache_hit ? "İsabet" : "Yok"),
    },
  ];

  return (
    <AdminListFrame resource={resource}>
      <div className="grid gap-3 sm:grid-cols-2">
        <AdminFilter
          label="Yanıt durumu"
          value={status}
          onChange={(value) => {
            setOffset(0);
            setStatus(value as RequestStatus | "");
          }}
          options={[
            { value: "", label: "Tümü" },
            { value: "answered", label: "Yanıtlandı" },
            { value: "insufficient_context", label: "Yetersiz bağlam" },
            { value: "out_of_scope", label: "Kapsam dışı" },
            { value: "budget_exhausted", label: "Bütçe tükendi" },
          ]}
        />
        <AdminTextFilter
          label="Uç filtresi"
          placeholder="/courses/.../chat"
          appliedValue={route}
          onApply={(value) => {
            setOffset(0);
            setRoute(value);
          }}
        />
      </div>
      <AdminDataTable
        title="AI kullanım kayıtları"
        description="Yalnız teknik performans görünür; kullanıcı, öğrenci sorusu, model yanıtı ve kaynak metni bu görünümde yer almaz."
        items={resource.data.items}
        columns={columns}
        rowKey={(item) => item.log_id}
        emptyMessage="Bu filtreye uyan AI kullanım kaydı bulunamadı."
      />
      <AdminPagination
        total={resource.data.total}
        offset={resource.data.offset}
        limit={resource.data.limit}
        busy={resource.loading}
        onChange={setOffset}
      />
    </AdminListFrame>
  );
}

function AdminIngestionPanel() {
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState<IngestionStatus | "">("");
  const fetchJobs = useCallback(
    () =>
      getAdminIngestionJobs({
        limit: PAGE_SIZE,
        offset,
        status: status || undefined,
      }),
    [offset, status],
  );
  const resource = useResource(fetchJobs, [offset, status]);

  if (resource.error) {
    return (
      <ErrorNote
        message={resource.error}
        kind={resource.errorKind}
        requestId={resource.errorRequestId}
        onRetry={resource.reload}
      />
    );
  }
  if (resource.loading || !resource.data) return <Loading label="İşleme işleri alınıyor…" />;

  const columns: AdminColumn<AdminIngestionJob>[] = [
    {
      key: "document",
      header: "Belge",
      render: (item) => (
        <span>
          <span className="block">Belge {item.document_id.slice(0, 8)}</span>
          <span className="block font-mono text-xs text-fg-muted">{item.course_code}</span>
        </span>
      ),
    },
    {
      key: "status",
      header: "Durum",
      render: (item) => (
        <Badge tone={ingestionTone(item.status)}>{ingestionStatusLabel(item.status)}</Badge>
      ),
    },
    { key: "attempt", header: "Deneme", render: (item) => item.attempt_count },
    { key: "started", header: "Başlama", render: (item) => adminDate(item.started_at) },
    { key: "completed", header: "Bitiş", render: (item) => adminDate(item.completed_at) },
  ];

  return (
    <AdminListFrame resource={resource}>
      <AdminFilter
        label="İşleme durumu"
        value={status}
        onChange={(value) => {
          setOffset(0);
          setStatus(value as IngestionStatus | "");
        }}
        options={[
          { value: "", label: "Tümü" },
          { value: "pending", label: "Bekliyor" },
          { value: "processing", label: "İşleniyor" },
          { value: "completed", label: "Tamamlandı" },
          { value: "failed", label: "Hata" },
        ]}
      />
      <AdminDataTable
        title="Kaynak işleme işleri"
        description="Belge yalnız teknik kimliğiyle görünür; dosya adı ve ders içeriği platform yöneticisine açılmaz."
        items={resource.data.items}
        columns={columns}
        rowKey={(item) => item.id}
        emptyMessage="Bu filtreye uyan işleme kaydı bulunamadı."
      />
      <AdminPagination
        total={resource.data.total}
        offset={resource.data.offset}
        limit={resource.data.limit}
        busy={resource.loading}
        onChange={setOffset}
      />
    </AdminListFrame>
  );
}

function AdminListFrame<T>({
  resource,
  children,
}: {
  resource: Resource<T>;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-4">
      {resource.refreshError && (
        <ErrorNote
          message={resource.refreshError}
          kind={resource.errorKind}
          requestId={resource.errorRequestId}
          onRetry={resource.reload}
        />
      )}
      {children}
    </div>
  );
}

function AdminFilter({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <label className="block max-w-xs text-xs font-medium text-fg-muted">
      {label}
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 h-11 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function AdminTextFilter({
  label,
  placeholder,
  appliedValue,
  onApply,
}: {
  label: string;
  placeholder: string;
  appliedValue: string;
  onApply: (value: string) => void;
}) {
  const [draft, setDraft] = useState(appliedValue);

  return (
    <form
      className="flex max-w-lg flex-wrap items-end gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        onApply(draft.trim());
      }}
    >
      <label className="min-w-52 flex-1 text-xs font-medium text-fg-muted">
        {label}
        <Input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={placeholder}
          className="mt-2"
        />
      </label>
      <Button type="submit" variant="secondary">
        Uygula
      </Button>
      {appliedValue && (
        <Button
          type="button"
          variant="ghost"
          onClick={() => {
            setDraft("");
            onApply("");
          }}
        >
          Temizle
        </Button>
      )}
    </form>
  );
}

function requestStatusLabel(status: RequestStatus | null): string {
  const labels: Record<RequestStatus, string> = {
    answered: "Yanıtlandı",
    insufficient_context: "Yetersiz bağlam",
    out_of_scope: "Kapsam dışı",
    budget_exhausted: "Bütçe tükendi",
  };
  return status ? labels[status] : "Durum yok";
}

function ingestionStatusLabel(status: IngestionStatus): string {
  return {
    pending: "Bekliyor",
    processing: "İşleniyor",
    completed: "Tamamlandı",
    failed: "Hata",
  }[status];
}

function ingestionTone(status: IngestionStatus) {
  return {
    pending: "neutral",
    processing: "info",
    completed: "success",
    failed: "danger",
  }[status] as "neutral" | "info" | "success" | "danger";
}
