"use client";

import { useCallback, useState } from "react";
import {
  AdminDataTable,
  AdminPagination,
  type AdminColumn,
} from "@/components/portal/admin-data-table";
import { ErrorNote, Loading } from "@/components/page-state";
import { adminDate, getAdminCourses, type AdminCourse } from "@/lib/admin";
import { useResource } from "@/lib/use-resource";
import { PAGE_SIZE, AdminListFrame, AdminTextFilter } from "@/components/admin/admin-list-primitives";

export function AdminCoursesPanel() {
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
