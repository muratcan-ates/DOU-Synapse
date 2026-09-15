"use client";

import { useCallback, useState } from "react";
import {
  AdminDataTable,
  AdminPagination,
  type AdminColumn,
} from "@/components/portal/admin-data-table";
import { ErrorNote, Loading } from "@/components/page-state";
import { Badge } from "@/components/ui";
import {
  adminDate,
  getAdminIngestionJobs,
  type AdminIngestionJob,
  type IngestionStatus,
} from "@/lib/admin";
import { useResource } from "@/lib/use-resource";
import { PAGE_SIZE, AdminListFrame, AdminFilter } from "@/components/admin/admin-list-primitives";

export function AdminIngestionPanel() {
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
