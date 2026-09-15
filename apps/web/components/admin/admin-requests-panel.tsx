"use client";

import { useCallback, useState } from "react";
import {
  AdminDataTable,
  AdminPagination,
  type AdminColumn,
} from "@/components/portal/admin-data-table";
import { ErrorNote, Loading } from "@/components/page-state";
import {
  adminDate,
  getAdminRequestLogs,
  type AdminRequestLog,
  type RequestStatus,
} from "@/lib/admin";
import { useResource } from "@/lib/use-resource";
import { PAGE_SIZE, AdminListFrame, AdminFilter, AdminTextFilter } from "@/components/admin/admin-list-primitives";

export function AdminRequestsPanel() {
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
function requestStatusLabel(status: RequestStatus | null): string {
  const labels: Record<RequestStatus, string> = {
    answered: "Yanıtlandı",
    insufficient_context: "Yetersiz bağlam",
    out_of_scope: "Kapsam dışı",
    budget_exhausted: "Bütçe tükendi",
  };
  return status ? labels[status] : "Durum yok";
}
