"use client";

import { useCallback } from "react";
import { PortalMetrics } from "@/components/portal/portal-metrics";
import { ErrorNote, Loading } from "@/components/page-state";
import { Badge, Button } from "@/components/ui";
import { adminDate, getAdminOverview } from "@/lib/admin";
import { useResource } from "@/lib/use-resource";

export function AdminOverviewSection() {
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
    <section aria-labelledby="system-overview-title" className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 id="system-overview-title" className="text-xl font-semibold text-fg">
            Platform durumu
          </h2>
          <p className="mt-1 text-sm text-fg-muted">
            Son 24 saatlik kullanım ve anlık servis görünümü
          </p>
        </div>
        <Button variant="secondary" onClick={() => void resource.reload()}>Durumu yenile</Button>
      </div>

      {resource.refreshError && (
        <ErrorNote
          message={resource.refreshError}
          kind={resource.errorKind}
          requestId={resource.errorRequestId}
          onRetry={resource.reload}
        />
      )}

      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[20px] border border-border bg-surface px-5 py-5 shadow-e1 sm:px-6">
        <div className="flex flex-wrap gap-2" aria-label="Servis sağlık durumları">
          <HealthBadge label="Uygulama" status={data.status} />
          <HealthBadge label="Veritabanı" status={data.database_status} />
          <HealthBadge label="Vektör veritabanı" status={data.pgvector_status ?? "unknown"} />
          <HealthBadge label="İstek kotası" status={data.request_quota_status ?? "unknown"} />
          <HealthBadge label="Embedding" status={data.embedding_status} />
        </div>
        <p className="text-sm tabular-nums text-fg-subtle">
          Ölçüm: {adminDate(data.measured_at)}
        </p>
      </div>

      <PortalMetrics
        items={[
          { label: "Kullanıcı", value: data.users_total },
          { label: "Ders", value: data.courses_total },
          { label: "Kaynak", value: data.documents_total },
          { label: "Aktif üyelik", value: data.active_memberships_total },
        ]}
      />

      <div>
        <p className="mb-2 text-xs font-medium text-fg-muted">Son 24 saat</p>
        <p className="mb-3 text-sm text-fg-muted">
          Sohbet, gecikme ve token ölçümleri kaydedilmiş başarılı HTTP sohbet isteklerini
          kapsar. HTTP hata yanıtları ve kaydı oluşmayan istekler bu ölçümlere dahil değildir.
        </p>
        <dl className="grid gap-px overflow-hidden rounded-[20px] border border-border bg-border sm:grid-cols-2 xl:grid-cols-5">
          <OverviewDatum
            label="Başarılı sohbet turu"
            value={data.chat_turns_24h}
            detail="Son 24 saat"
          />
          <OverviewDatum
            label="P95 gecikme"
            value={data.p95_latency_ms === null ? "-" : `${Math.round(data.p95_latency_ms)} ms`}
            detail={`${data.chat_turns_24h.toLocaleString("tr-TR")} başarılı sohbet örneği`}
          />
          <OverviewDatum label="Token" value={data.tokens_24h.toLocaleString("tr-TR")} />
          <OverviewDatum label="İşleniyor" value={data.ingestion_processing} />
          <OverviewDatum label="İşleme hatası" value={data.ingestion_failed} />
        </dl>
      </div>
    </section>
  );
}

function HealthBadge({ label, status }: { label: string; status: string }) {
  const normalized = status.toLowerCase();
  const tone =
    normalized === "ok" || normalized === "ready" || normalized === "healthy"
      ? "success"
      : normalized === "warming" ||
          normalized === "degraded" ||
          normalized === "disabled" ||
          normalized === "unknown"
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
    error: "Hata",
    missing: "Eksik",
    unknown: "Ölçülemedi",
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
    <div className="flex min-h-28 flex-col-reverse gap-3 bg-surface px-5 py-5">
      <dt className="text-xs text-fg-muted">
        {label}
        {detail ? ` (${detail})` : ""}
      </dt>
      <dd className="text-2xl font-semibold tabular-nums text-fg">{value}</dd>
    </div>
  );
}
