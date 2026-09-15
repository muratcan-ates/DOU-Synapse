"use client";

/**
 * Kavram haritası — dersin materyalinden çıkarılmış terimler ve bağlantıları.
 *
 * Tek uç: `GET /courses/{id}/concepts`. Model çağrılmaz, jeton harcanmaz;
 * gösterilen her satırın arkasında gerçek bir materyal pasajı vardır. İndirme
 * aynı veriyi sunucunun ürettiği Markdown biçiminde alır (`/concepts/export`),
 * böylece dosya biçimi iki yerde birden yaşamaz.
 *
 * Sınav kilidi sunucuda; ekran onu yalnız sebebini söylemek için okur.
 */

import { useCallback, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { occurrenceLabel, resolveSelection, termIndex, type ConceptMap } from "@/lib/concepts";
import { useChatAvailability, type ChatLock } from "@/lib/chat-availability";
import { useResource } from "@/lib/use-resource";
import { useSubmit } from "@/lib/use-submit";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { EdgeTable } from "@/components/concepts/edge-table";
import { TermDetail } from "@/components/concepts/term-detail";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Button, Card, EmptyState } from "@/components/ui";

export default function ConceptsPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const lock = useChatAvailability(courseId);
  return (
    <AppShell>
      <CourseNav courseId={courseId} lock={lock} />
      <ConceptsScreen courseId={courseId} lock={lock} />
    </AppShell>
  );
}

function ConceptsScreen({ courseId, lock }: { courseId: string; lock: ChatLock }) {
  const [selected, setSelected] = useState<string | null>(null);

  const fetchMap = useCallback(
    () => api.get<ConceptMap>(`/courses/${courseId}/concepts`),
    [courseId],
  );
  const map = useResource(fetchMap, [courseId]);

  const aktif = useMemo(
    () => (map.data ? resolveSelection(map.data, selected) : null),
    [map.data, selected],
  );
  const term = map.data && aktif ? termIndex(map.data).get(aktif) : undefined;

  /*
   * İndirme: `api.text` yetki başlığını ve hata zarfını aynı yoldan geçirir.
   * `<a download>` kullanılamaz — uç Bearer istiyor ve bağlantı başlık taşımaz.
   */
  const indir = useSubmit(async () => {
    const markdown = await api.text(`/courses/${courseId}/concepts/export`);
    const url = URL.createObjectURL(new Blob([markdown], { type: "text/markdown;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `kavram-haritasi-${courseId.slice(0, 8)}.md`;
    link.click();
    URL.revokeObjectURL(url);
  });

  const header = (
    <PageHeader
      title="Kavram haritası"
      description="Ders materyalinden çıkarılan anahtar terimler ve hangi terimlerin birlikte anlatıldığı. Yapay zekâ yorumu eklenmez; her terim materyaldeki yerine bağlıdır."
    />
  );

  if (lock.locked) {
    return (
      <>
        {header}
        <EmptyState title={lock.message ?? "Yürüyen bir sınav varken kavram haritası kapalıdır."} />
      </>
    );
  }
  if (map.loading) return <>{header}<Loading /></>;
  if (map.error) return <>{header}<ErrorNote message={map.error} onRetry={map.reload} /></>;
  if (map.data === null) return <>{header}<Loading /></>;

  if (map.data.terms.length === 0) {
    return (
      <>
        {header}
        <EmptyState title="Bu derste henüz işlenmiş materyal yok. Eğitmen belge yükleyip işleme tamamlanınca kavram haritası burada oluşur." />
      </>
    );
  }

  return (
    <>
      {header}

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-fg-muted">
          {map.data.terms.length} terim · {map.data.chunk_count} materyal pasajından çıkarıldı
          {map.data.truncated && " · materyalin bir kısmı okunmadı"}
        </p>
        <Button variant="secondary" onClick={indir.submit} aria-disabled={indir.busy}>
          {indir.busy ? "Hazırlanıyor…" : "Markdown indir"}
        </Button>
      </div>
      {indir.error && <div className="mb-5"><ErrorNote message={indir.error} /></div>}

      {/* Dar ekranda tek sütun: terim listesi üstte, seçilenin ayrıntısı altında. */}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
        <Card className="min-w-0 self-start">
          <h2 className="text-lg font-semibold text-fg">Parçalar</h2>
          <p className="mt-1 text-sm text-fg-muted">En çok pasajda geçenden aza.</p>
          <ul className="mt-4 space-y-1">
            {map.data.terms.map((entry) => {
              const active = entry.key === aktif;
              return (
                <li key={entry.key}>
                  <button
                    type="button"
                    onClick={() => setSelected(entry.key)}
                    aria-current={active ? "true" : undefined}
                    className={`flex w-full items-baseline justify-between gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition-colors focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand ${
                      active
                        ? "bg-brand-subtle font-semibold text-brand"
                        : "text-fg hover:bg-surface-sunken"
                    }`}
                  >
                    <span className="prose-tr min-w-0 break-words">{entry.term}</span>
                    <span className="shrink-0 text-xs tabular-nums text-fg-muted">
                      {entry.chunk_count}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="mt-4 text-xs leading-5 text-fg-subtle">
            Sağdaki sayı, terimin kaç materyal pasajında geçtiğini gösterir. Türkçe ekler
            yaklaşık olarak birleştirilir; aynı kavramın bazı çekimleri ayrı görünebilir.
          </p>
        </Card>

        <div className="min-w-0 space-y-5">
          {term ? (
            <TermDetail courseId={courseId} map={map.data} term={term} onSelect={setSelected} />
          ) : (
            <EmptyState title="Soldan bir terim seçin." />
          )}
          <EdgeTable map={map.data} />
        </div>
      </div>

      <p aria-live="polite" className="sr-only">
        {term ? `${term.term} seçildi, ${occurrenceLabel(term.chunk_count)}.` : ""}
      </p>
    </>
  );
}
