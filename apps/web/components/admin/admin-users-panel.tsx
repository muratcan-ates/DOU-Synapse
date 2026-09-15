"use client";

import { useCallback, useState } from "react";
import {
  AdminDataTable,
  AdminPagination,
  type AdminColumn,
} from "@/components/portal/admin-data-table";
import { ErrorNote, Loading } from "@/components/page-state";
import { Badge } from "@/components/ui";
import { adminDate, getAdminUsers, type AdminUser } from "@/lib/admin";
import { useResource } from "@/lib/use-resource";
import { PAGE_SIZE, AdminListFrame, AdminTextFilter } from "@/components/admin/admin-list-primitives";

export function AdminUsersPanel() {
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
        item.is_platform_admin ? <Badge tone="info">Bilgi İşlem yöneticisi</Badge> : "Kullanıcı",
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
