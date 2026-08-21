"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AdminDataTable,
  AdminPagination,
  type AdminColumn,
} from "@/components/portal/admin-data-table";
import { ErrorNote, Loading } from "@/components/page-state";
import { Badge, Button, Input } from "@/components/ui";
import {
  adminCollectorLabel,
  adminCollectorTone,
  adminApiEventRowKey,
  adminDate,
  adminLatency,
  adminWindowLabel,
  queryAdminApiEvents,
  type AdminApiEvent,
  type AdminApiEventsOut,
  type AdminApiMethod,
  type AdminApiRouteActivity,
  type AdminApiStatusClass,
  type AdminApiWindowMinutes,
} from "@/lib/admin";
import { useResource } from "@/lib/use-resource";
import { useSubmit } from "@/lib/use-submit";

const PAGE_SIZE = 25;
const LIVE_INTERVAL_MS = 15_000;
const LIVE_MAX_DURATION_MS = 10 * 60_000;

interface ApiFilters {
  windowMinutes: AdminApiWindowMinutes;
  method: AdminApiMethod | "";
  route: string;
  statusClass: AdminApiStatusClass | "";
  requestId: string;
}

const DEFAULT_FILTERS: ApiFilters = {
  windowMinutes: 60,
  method: "",
  route: "",
  statusClass: "",
  requestId: "",
};

export function AdminApiWorkbench({ active }: { active: boolean }) {
  const [draft, setDraft] = useState<ApiFilters>(DEFAULT_FILTERS);
  const [filters, setFilters] = useState<ApiFilters>(DEFAULT_FILTERS);
  const [offset, setOffset] = useState(0);
  const [live, setLive] = useState(false);
  const [queryRevision, setQueryRevision] = useState(0);
  const inFlightQueries = useRef(new Map<string, Promise<AdminApiEventsOut>>());
  const fetchEvents = useCallback(() => {
    const query = {
      window_minutes: filters.windowMinutes,
      limit: PAGE_SIZE,
      offset,
      method: filters.method || undefined,
      route: filters.route || undefined,
      status_class: filters.statusClass || undefined,
      request_id: filters.requestId || undefined,
    };
    const key = JSON.stringify(query);
    const current = inFlightQueries.current.get(key);
    if (current) return current;

    // Strict Mode, elle yenileme ve yoklama aynı snapshot'ı eşzamanlı isterse
    // tek POST'u paylaşır. Farklı filtreler kendi isteklerini başlatabilir;
    // useResource'ın sıra kapısı geç dönen eski sonucu yine reddeder.
    const request = queryAdminApiEvents(query);
    inFlightQueries.current.set(key, request);
    void request.then(
      () => clearInFlightQuery(inFlightQueries.current, key, request),
      () => clearInFlightQuery(inFlightQueries.current, key, request),
    );
    return request;
  }, [
    filters.method,
    filters.requestId,
    filters.route,
    filters.statusClass,
    filters.windowMinutes,
    offset,
  ]);
  const resource = useResource(
    fetchEvents,
    [
      filters.windowMinutes,
      filters.method,
      filters.route,
      filters.statusClass,
      filters.requestId,
      offset,
      queryRevision,
    ],
    {
      pollWhile: () => active && live,
      intervalMs: LIVE_INTERVAL_MS,
    },
  );
  const refresh = useSubmit(async () => {
    await resource.reload();
  });

  useEffect(() => {
    if (!live) return;
    const timeout = window.setTimeout(
      () => setLive(false),
      LIVE_MAX_DURATION_MS,
    );
    return () => window.clearTimeout(timeout);
  }, [live]);

  useEffect(() => {
    const total = resource.data?.total;
    if (total === undefined) return;
    if (total === 0 && offset !== 0) {
      setOffset(0);
      return;
    }
    if (total > 0 && offset >= total) {
      setOffset(Math.floor((total - 1) / PAGE_SIZE) * PAGE_SIZE);
    }
  }, [offset, resource.data?.total]);

  function resetFiltersAndRetry(): void {
    setDraft(DEFAULT_FILTERS);
    setFilters(DEFAULT_FILTERS);
    setOffset(0);
    setQueryRevision((current) => current + 1);
  }

  if (resource.error) {
    return (
      <section aria-labelledby="api-flow-error-title" className="space-y-4">
        <div>
          <h2 id="api-flow-error-title" className="text-xl font-medium text-fg">
            API akışı
          </h2>
          <p className="mt-1 text-sm text-fg-muted">
            Filtre doğrulanamadıysa güvenli başlangıç değerlerine
            dönebilirsiniz.
          </p>
        </div>
        <ErrorNote
          message={resource.error}
          kind={resource.errorKind}
          requestId={resource.errorRequestId}
        />
        <Button
          type="button"
          variant="secondary"
          onClick={resetFiltersAndRetry}
        >
          Filtreleri temizle ve yeniden dene
        </Button>
      </section>
    );
  }
  if (resource.loading || !resource.data) {
    return <Loading label="API akışı alınıyor…" />;
  }

  const data = resource.data;
  const routeColumns: AdminColumn<AdminApiRouteActivity>[] = [
    {
      key: "route",
      header: "API ucu",
      render: (item) => (
        <span className="block max-w-xl whitespace-normal">
          <span className="mr-2 font-mono text-xs font-medium text-fg">
            {item.method}
          </span>
          <span className="break-all font-mono text-xs text-fg-muted">
            {item.route_template}
          </span>
        </span>
      ),
    },
    { key: "requests", header: "İstek", render: (item) => item.requests_total },
    { key: "errors", header: "Hata", render: (item) => item.error_total },
    {
      key: "p95",
      header: "P95 gecikme",
      render: (item) => (
        <span className="font-mono text-xs">
          {adminLatency(item.p95_latency_ms)}
        </span>
      ),
    },
    {
      key: "last-seen",
      header: "Son gözlem",
      render: (item) => adminDate(item.last_seen_at),
    },
  ];
  const eventColumns: AdminColumn<AdminApiEvent>[] = [
    {
      key: "time",
      header: "Zaman",
      render: (item) => adminDate(item.created_at),
    },
    {
      key: "request",
      header: "Destek kodu",
      render: (item) => (
        <span className="block max-w-52 break-all font-mono text-xs">
          {item.request_id}
        </span>
      ),
    },
    {
      key: "route",
      header: "API ucu",
      render: (item) => (
        <span className="block max-w-xl whitespace-normal">
          <span className="mr-2 font-mono text-xs font-medium">
            {item.method}
          </span>
          <span className="break-all font-mono text-xs text-fg-muted">
            {item.route_template}
          </span>
        </span>
      ),
    },
    {
      key: "result",
      header: "Sonuç",
      render: (item) => (
        <span>
          <Badge tone={httpStatusTone(item.status_code)}>
            HTTP {item.status_code}
          </Badge>
          {item.outcome_code && (
            <span className="mt-1 block break-all font-mono text-xs text-fg-muted">
              {item.outcome_code}
            </span>
          )}
        </span>
      ),
    },
    {
      key: "duration",
      header: "Süre",
      render: (item) => (
        <span className="font-mono text-xs">
          {adminLatency(item.duration_ms)}
        </span>
      ),
    },
    {
      key: "runtime",
      header: "Çalışma ortamı",
      render: (item) => (
        <span>
          <span className="block">{item.service}</span>
          <span className="block text-xs text-fg-muted">
            {item.environment}
          </span>
          <span
            className="block max-w-40 truncate font-mono text-xs text-fg-subtle"
            title={item.release_revision}
          >
            {item.release_revision || "Sürüm yok"}
          </span>
        </span>
      ),
    },
  ];

  return (
    <section aria-labelledby="api-flow-title" className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id="api-flow-title" className="text-xl font-medium text-fg">
            API akışı
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-fg-muted">
            İçerik, kullanıcı ve ham adres taşımayan toplu API olaylarını
            inceleyin. Bu alan yeni bir API isteği çalıştırma konsolu değildir;
            yalnız kaydedilmiş işletim olaylarını gösterir.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="secondary"
            aria-disabled={refresh.busy}
            onClick={() => void refresh.submit()}
          >
            {refresh.busy ? "Yenileniyor…" : "Şimdi yenile"}
          </Button>
          <Button
            type="button"
            variant={live ? "secondary" : "ghost"}
            aria-pressed={live}
            onClick={() => setLive((current) => !current)}
          >
            Canlı izleme {live ? "açık" : "kapalı"}
          </Button>
          {live && (
            <span className="self-center text-xs text-fg-muted">
              10 dakika sonra otomatik kapanır.
            </span>
          )}
        </div>
      </div>

      {resource.refreshError && (
        <ErrorNote
          message={resource.refreshError}
          kind={resource.errorKind}
          requestId={resource.errorRequestId}
          onRetry={resource.reload}
        />
      )}

      <div className="flex flex-wrap items-center justify-between gap-4 border-y border-border bg-surface px-4 py-4 sm:px-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge
            tone={
              adminCollectorTone(data.collector.status) === "success" &&
              data.collector.dropped_total > 0
                ? "warning"
                : adminCollectorTone(data.collector.status)
            }
          >
            Toplayıcı: {adminCollectorLabel(data.collector.status)}
          </Badge>
          <Badge
            tone={
              data.collector.retention_status === "healthy"
                ? "success"
                : "warning"
            }
          >
            Saklama:{" "}
            {data.collector.retention_status === "healthy"
              ? "sağlıklı"
              : "aksıyor"}
          </Badge>
          <span className="font-mono text-xs text-fg-muted">
            Kuyruk {data.collector.queue_depth}/{data.collector.queue_capacity}
          </span>
          <span className="font-mono text-xs text-fg-muted">
            Yazılan {data.collector.persisted_total}
          </span>
          <span className="font-mono text-xs text-fg-muted">
            Düşürülen {data.collector.dropped_total}
          </span>
          <span className="font-mono text-xs text-fg-muted">
            Hata {data.collector.failure_total}
          </span>
        </div>
        <p className="font-mono text-xs text-fg-subtle" aria-live="polite">
          Ölçüm: {adminDate(data.measured_at)}
        </p>
      </div>
      <p className="border-b border-border bg-surface px-4 pb-4 text-xs text-fg-muted sm:px-5">
        Toplayıcı sayaçları yalnız bu API sürecini gösteren bir tanılama
        snapshot&apos;ıdır; çoklu sunucu toplamı, SLO veya error-budget kaynağı
        değildir.
      </p>

      <dl className="grid gap-px border-y border-border bg-border sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        <SummaryDatum
          label="Aralık"
          value={adminWindowLabel(data.window_minutes)}
        />
        <SummaryDatum label="İstek" value={data.summary.requests_total} />
        <SummaryDatum label="Başarılı" value={data.summary.successful_total} />
        <SummaryDatum label="Yönlendirme" value={data.summary.redirect_total} />
        <SummaryDatum
          label="İstemci hatası"
          value={data.summary.client_error_total}
        />
        <SummaryDatum
          label="Sunucu hatası"
          value={data.summary.server_error_total}
        />
        <SummaryDatum
          label="P50 / P95"
          value={`${adminLatency(data.summary.p50_latency_ms)} / ${adminLatency(data.summary.p95_latency_ms)}`}
        />
      </dl>

      <form
        className="grid gap-3 border-y border-border bg-bg py-5 sm:grid-cols-2 lg:grid-cols-5"
        onSubmit={(event) => {
          event.preventDefault();
          setOffset(0);
          setFilters(normalizeFilters(draft));
        }}
      >
        <ApiSelect
          label="Zaman aralığı"
          value={String(draft.windowMinutes)}
          onChange={(value) =>
            setDraft((current) => ({
              ...current,
              windowMinutes: Number(value) as AdminApiWindowMinutes,
            }))
          }
          options={[
            { value: "15", label: "Son 15 dakika" },
            { value: "60", label: "Son 1 saat" },
            { value: "1440", label: "Son 24 saat" },
          ]}
        />
        <ApiSelect
          label="HTTP metodu"
          value={draft.method}
          onChange={(value) =>
            setDraft((current) => ({
              ...current,
              method: value as AdminApiMethod | "",
            }))
          }
          options={[
            { value: "", label: "Tümü" },
            { value: "GET", label: "GET" },
            { value: "HEAD", label: "HEAD" },
            { value: "POST", label: "POST" },
            { value: "PATCH", label: "PATCH" },
            { value: "PUT", label: "PUT" },
            { value: "DELETE", label: "DELETE" },
          ]}
        />
        <ApiSelect
          label="Durum sınıfı"
          value={draft.statusClass}
          onChange={(value) =>
            setDraft((current) => ({
              ...current,
              statusClass: value as AdminApiStatusClass | "",
            }))
          }
          options={[
            { value: "", label: "Tümü" },
            { value: "2xx", label: "2xx başarılı" },
            { value: "3xx", label: "3xx yönlendirme" },
            { value: "4xx", label: "4xx istemci hatası" },
            { value: "5xx", label: "5xx sunucu hatası" },
          ]}
        />
        <label className="text-xs font-medium text-fg-muted">
          API ucu
          <Input
            value={draft.route}
            onChange={(event) =>
              setDraft((current) => ({ ...current, route: event.target.value }))
            }
            placeholder="/courses/{course_id}/chat"
            className="mt-2 font-mono"
          />
        </label>
        <label className="text-xs font-medium text-fg-muted">
          Destek kodu
          <Input
            value={draft.requestId}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                requestId: event.target.value,
              }))
            }
            placeholder="İstek destek kodu"
            className="mt-2 font-mono"
          />
        </label>
        <div className="flex flex-wrap gap-2 sm:col-span-2 lg:col-span-5">
          <Button type="submit" variant="secondary">
            Filtreleri uygula
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setDraft(DEFAULT_FILTERS);
              setFilters(DEFAULT_FILTERS);
              setOffset(0);
            }}
          >
            Filtreleri temizle
          </Button>
        </div>
      </form>

      <AdminDataTable
        title="Uç özeti"
        description="Adresler ham kimlik değil, sunucunun güvenli route şablonudur."
        items={data.routes}
        columns={routeColumns}
        rowKey={(item) => `${item.method}:${item.route_template}`}
        emptyMessage="Bu zaman aralığında API ucu gözlenmedi."
      />

      <AdminDataTable
        title="API olayları"
        description="Destek kodu teknik olayı bulur; kullanıcı, istek gövdesi ve akademik içerik gösterilmez."
        items={data.items}
        columns={eventColumns}
        rowKey={adminApiEventRowKey}
        emptyMessage="Bu filtrelere uyan API olayı bulunamadı. Zaman aralığını genişletebilirsiniz."
      />
      <AdminPagination
        total={data.total}
        offset={data.offset}
        limit={data.limit}
        busy={resource.loading || refresh.busy}
        onChange={setOffset}
      />

      <p className="text-xs text-fg-subtle">
        Son kalıcı kayıt: {adminDate(data.collector.last_persisted_at)}
        {data.collector.last_error_at
          ? ` · Son toplayıcı hatası: ${adminDate(data.collector.last_error_at)}`
          : ""}
      </p>
    </section>
  );
}

function normalizeFilters(filters: ApiFilters): ApiFilters {
  return {
    ...filters,
    method: filters.method.trim().toUpperCase() as AdminApiMethod | "",
    route: filters.route.trim(),
    requestId: filters.requestId.trim(),
  };
}

function clearInFlightQuery(
  queries: Map<string, Promise<AdminApiEventsOut>>,
  key: string,
  request: Promise<AdminApiEventsOut>,
): void {
  if (queries.get(key) === request) queries.delete(key);
}

function ApiSelect({
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
    <label className="text-xs font-medium text-fg-muted">
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

function SummaryDatum({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="flex min-h-20 flex-col-reverse gap-1 bg-bg px-4 py-4">
      <dt className="text-xs text-fg-muted">{label}</dt>
      <dd className="break-words font-mono text-base text-fg">{value}</dd>
    </div>
  );
}

function httpStatusTone(
  status: number,
): "success" | "info" | "warning" | "danger" {
  if (status >= 500) return "danger";
  if (status >= 400) return "warning";
  if (status >= 300) return "info";
  return "success";
}
