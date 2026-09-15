"use client";

/**
 * Sınav blueprint'i kurma ekranı (T509). Uçlar:
 * `GET/POST /courses/{id}/learning-outcomes`, `GET/POST /courses/{id}/blueprints`,
 * `POST /courses/{id}/blueprints/{bid}` (güncelle), `DELETE .../blueprints/{bid}` (sil),
 * `GET/POST .../versions`, `POST .../versions/{vid}/items`,
 * `GET .../versions/{vid}/readiness`, `POST .../versions/{vid}/publish`.
 *
 * Ekranın anlattığı ürün kararı şu: **çatı önce çizilir, kâğıt sonra doldurulur.**
 * Blueprint sorulardan önce vardır; sürüm blueprint'ten sonra gelir; yayın en
 * sonda ve bir KAPIDAN geçer. Sıra ekranda da bu sırayla durur, çünkü öğretmen
 * hangi adımda olduğunu ekrandan okumalı.
 *
 * Üç şeyi ekran BİLMEZ, sunucudan okur (Anayasa V):
 *   - hücre adı (`cell.label`),
 *   - kapının reddettiği maddelerin metni (`missing_cells[].label`,
 *     `unclassified_items[].label`),
 *   - her hata cümlesi (`errorMessage`).
 * Burada üretilen tek metin, sunucunun hiç bilmediği şeydir: hangi adımda olduğun.
 *
 * Eksik hücre ile sınıflandırılmamış kalem AYRI başlıklar altında durur ve bu bir
 * karardır (data-model.md §8 madde 7): tek listede görünseydi öğretmen var olmayan
 * bir eksiği kovalar, kâğıdı uzatır ve gerçek sebep hiç söylenmemiş olurdu.
 *
 * Yüzde→adet açılımı `lib/blueprint.ts`'te ve saf: yuvarlamayı JSX'in ortasında
 * yapmak, yalnız tarayıcıda sınanabilir bir aritmetik bırakırdı
 * (bkz. `lib/blueprint.test.ts`).
 */

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import {
  DIFFICULTY_LABEL,
  editingNoticeFor,
  readinessCounts,
  VERSION_STATUS_LABEL,
  type Blueprint,
  type ExamItem,
  type ExamVersion,
  type LearningOutcome,
  type PoolQuestion,
  type Readiness,
} from "@/lib/blueprint";
import { QUESTION_TYPE } from "@/lib/labels";
import { useSession } from "@/lib/session";
import { usePagedResource } from "@/lib/use-paged-resource";
import { useResource } from "@/lib/use-resource";
import { useSubmit } from "@/lib/use-submit";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { PaperPreview } from "@/components/blueprint/paper-preview";
import { InstructorGate } from "@/components/instructor-gate";
import { ErrorNote, Loading, LoadMore, MetricRow, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, ConfirmAction, EmptyState } from "@/components/ui";
import { OutcomesCard } from "@/components/blueprint/outcomes-card";
import { BlueprintListCard } from "@/components/blueprint/blueprint-list-card";
import { BlueprintEditor } from "@/components/blueprint/blueprint-editor";

export default function BlueprintsPage() {
  return <Suspense fallback={<Loading />}><BlueprintScreen /></Suspense>;
}

function BlueprintScreen() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isInstructor, ready } = useSession(courseId);
  const search = useSearchParams();
  const queryKey = search.toString();
  const linkedBlueprintId = search.get("blueprint_id");
  const linkedVersionId = search.get("version_id");

  const outcomes = useResource<LearningOutcome[]>(
    () => api.get(`/courses/${courseId}/learning-outcomes`),
    [courseId],
  );
  const blueprints = useResource<Blueprint[]>(
    () => api.get(`/courses/${courseId}/blueprints`),
    [courseId],
  );

  const authoring = useResource<{ enabled: boolean }>(
    () => api.get(`/courses/${courseId}/questions/authoring`), [courseId],
  );

  const [selection, setSelection] = useState<{ queryKey: string; id: string } | null>(null);
  const selectedId = selection?.queryKey === queryKey ? selection.id : linkedBlueprintId;
  const setSelectedId = (id: string) => setSelection({ queryKey, id });
  const selected = blueprints.data?.find((item) => item.id === selectedId) ?? null;

  /*
   * Kapının iyimser varyantı: rol çözülene kadar `Loading` yerine sayfa
   * iskeleti çizilir (bu sayfanın eskiden beri davranışı — veri kancaları
   * zaten yukarıda, rolden bağımsız koşuyor). Rol netleşip "öğrenci" çıkarsa
   * kapak iner.
   */
  return (
    <AppShell>
      <CourseNav courseId={courseId} />
      <InstructorGate
        ready={ready}
        isInstructor={isInstructor}
        optimistic
        fallback={
          <EmptyState title="Sınav blueprint'i eğitmen aracıdır; bu sayfa sana kapalı." />
        }
      >
      <PageHeader
        title="Sınav blueprint'i"
        description="Sınavın çatısını sorulardan önce çiz: hangi öğrenme çıktısından, hangi zorlukta, kaç soru."
      />

      <nav aria-label="Sınav hazırlama aşamaları" className="mb-6 grid gap-2 sm:grid-cols-3">
        {[{ href: "#learning-outcomes", label: "Öğrenme çıktılarını belirle" },
          { href: "#exam-plans", label: "Sınav dağılımını kur" },
          { href: selected ? "#exam-paper" : "#exam-plans", label: "Soruları seç ve yayımla" }].map((step, index) => (
          <a key={step.label} href={step.href} className="group flex min-h-16 items-center gap-3 rounded-2xl border border-border bg-surface px-4 py-3 text-sm font-medium text-fg transition-colors duration-200 hover:border-border-strong hover:bg-surface-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand motion-reduce:transition-none">
            <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-sunken text-sm text-fg-muted">{index + 1}</span>
            {step.label}
          </a>
        ))}
      </nav>
      <MetricRow
        items={[
          { label: "Öğrenme çıktısı", value: String(outcomes.data?.length ?? 0) },
          { label: "Blueprint", value: String(blueprints.data?.length ?? 0) },
          {
            label: "Yayında sınav",
            value: String(
              blueprints.data?.filter((item) => item.published_version_no !== null).length ?? 0,
            ),
          },
          {
            label: "Toplam soru (seçili)",
            value: selected ? String(selected.total_questions) : "—",
          },
        ]}
      />

      <section id="learning-outcomes" className="scroll-mt-28"><OutcomesCard courseId={courseId} outcomes={outcomes} /></section>
      {(authoring.error ?? authoring.refreshError) && <ErrorNote
        message={authoring.error ?? authoring.refreshError ?? ""} kind={authoring.errorKind}
        requestId={authoring.errorRequestId} onRetry={authoring.reload} />}

      <section id="exam-plans" className="scroll-mt-28">
      <BlueprintListCard
        courseId={courseId}
        blueprints={blueprints}
        outcomes={outcomes.data ?? []}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />
      </section>

      {linkedBlueprintId && !selected && blueprints.data && (
        <p role="status" className="mb-4 text-sm text-fg-muted">Bağlantıdaki sınav bu listede bulunmuyor.</p>
      )}
      {selected && (
        <section id="exam-paper" className="scroll-mt-28">
        <BlueprintDetail
          courseId={courseId}
          blueprint={selected}
          authoringEnabled={authoring.data?.enabled ?? null}
          linkedVersionId={selected.id === linkedBlueprintId ? linkedVersionId : null}
          outcomes={outcomes.data ?? []}
          onChanged={blueprints.reload}
        />
        </section>
      )}
      </InstructorGate>
    </AppShell>
  );
}

/* -------------------------------------------------------------------------
 * Seçili blueprint: sürümler, kapı, yayın (FR-114, FR-115)
 * ---------------------------------------------------------------------- */

function BlueprintDetail({
  authoringEnabled,
  courseId,
  blueprint,
  outcomes,
  onChanged,
  linkedVersionId,
}: {
  courseId: string;
  blueprint: Blueprint;
  outcomes: LearningOutcome[];
  onChanged: () => void;
  linkedVersionId: string | null;
  authoringEnabled: boolean | null;
}) {
  const [editing, setEditing] = useState(false);
  const versions = useResource<ExamVersion[]>(
    () => api.get(`/courses/${courseId}/blueprints/${blueprint.id}/versions`),
    [courseId, blueprint.id],
  );
  const notice = editingNoticeFor(blueprint);

  const { busy, error, submit: createVersion } = useSubmit(async () => {
    await api.post(`/courses/${courseId}/blueprints/${blueprint.id}/versions`);
    versions.reload();
  });

  return (
    <>
      <Card className="mb-7">
        <div className="mb-1 flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-semibold text-fg">{blueprint.title} · dağılım</h2>
          {/*
            Düzenleme ve silme, uçları (POST/DELETE .../blueprints/{bid}) zaten
            varken ekranda yoktu; üstelik aşağıdaki `notice` öğretmene tam da bu
            düzenlemenin güvenli olduğunu ANLATIYORDU. Yanlış girilen bir dağılım
            ne düzeltilebiliyor ne silinebiliyordu.
          */}
          <div className="ml-auto flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              aria-disabled={editing}
              onClick={() => setEditing(true)}
            >
              Dağılımı düzenle
            </Button>
            <ConfirmAction
              label="Sınavı sil"
              confirmLabel="Kalıcı olarak sil"
              busyLabel="Siliniyor…"
              question="Bu blueprint ve tüm taslak sürümleri silinsin mi? Yayınlanmış sürümün oturumu varsa sunucu reddeder."
              ariaLabel={`${blueprint.title} blueprint'ini sil`}
              size="sm"
              onConfirm={async () => {
                await api.delete(`/courses/${courseId}/blueprints/${blueprint.id}`);
                onChanged();
              }}
            />
          </div>
        </div>
        {notice && (
          <p className="prose-tr mb-3 rounded-lg border border-border bg-bg px-3 py-2 text-sm text-fg-muted">
            {notice}
          </p>
        )}

        {editing && (
          <BlueprintEditor
            courseId={courseId}
            blueprint={blueprint}
            outcomes={outcomes}
            onCancel={() => setEditing(false)}
            onSaved={() => {
              setEditing(false);
              onChanged();
            }}
          />
        )}

        <ul className="mb-4 flex flex-col gap-1">
          {blueprint.cells.map((cell) => (
            <li
              key={cell.id}
              className="flex flex-wrap items-center gap-3 rounded-xl border border-border px-4 py-4 text-sm"
            >
              {/* Etiket sunucudan gelir; ekran kendi hücre adını kurmaz. */}
              <span className="text-fg">{cell.label}</span>
              <span className="ml-auto text-fg-muted">
                {cell.question_count} soru · {cell.points_per_question} puan
              </span>
            </li>
          ))}
        </ul>

        <h3 className="mb-2 text-sm font-semibold text-fg">Konu dağılımı (türetilmiş)</h3>
        <ul className="flex flex-wrap gap-2">
          {blueprint.topic_distribution.map((share) => (
            <li key={share.topic_id ?? "yok"}>
              <Badge tone={share.topic_id === null ? "warning" : "info"}>
                {share.topic_name ?? "Konusuz çıktıdan"}: {share.question_count} soru
              </Badge>
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold text-fg">Sürümler</h2>
          <Button variant="secondary" onClick={createVersion} aria-disabled={busy}>
            {busy ? "Açılıyor…" : "Yeni taslak sürüm"}
          </Button>
        </div>

        {error && <div className="mb-3">{<ErrorNote message={error} />}</div>}
        {versions.loading && !versions.data && <Loading label="Sürümler yükleniyor…" />}
        {versions.error && (
        <ErrorNote
          message={versions.error}
          kind={versions.errorKind}
          requestId={versions.errorRequestId}
          onRetry={versions.reload}
        />
      )}
        {versions.data && versions.data.length === 0 && (
          <EmptyState title="Henüz sürüm yok. Kâğıdı doldurmak için bir taslak sürüm aç." />
        )}

        {linkedVersionId && versions.data && !versions.data.some((version) => version.id === linkedVersionId) && (
          <p role="status" className="mb-4 text-sm text-fg-muted">Bağlantıdaki sürüm bu listede bulunmuyor.</p>
        )}
        <ul className="flex flex-col gap-4">
          {(versions.data ?? []).map((version) => (
            <VersionRow
              key={`${version.id}:${version.id === linkedVersionId}`}
              linked={version.id === linkedVersionId}
              authoringEnabled={authoringEnabled}
              courseId={courseId}
              blueprint={blueprint}
              version={version}
              outcomes={outcomes}
              onChanged={() => {
                versions.reload();
                onChanged();
              }}
            />
          ))}
        </ul>
      </Card>
    </>
  );
}

function VersionRow({
  authoringEnabled,
  courseId,
  blueprint,
  version,
  outcomes,
  onChanged,
  linked,
}: {
  courseId: string;
  blueprint: Blueprint;
  version: ExamVersion;
  outcomes: LearningOutcome[];
  onChanged: () => void;
  linked: boolean;
  authoringEnabled: boolean | null;
}) {
  const base = `/courses/${courseId}/blueprints/${blueprint.id}/versions/${version.id}`;
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState(linked);
  const versionRef = useRef<HTMLLIElement>(null);
  useEffect(() => { if (linked) versionRef.current?.focus(); }, [linked]);

  const counts = readinessCounts(readiness);

  /*
   * İki eylem tek kancada: `busy` ve hata satırı zaten ortaktı (iki düğme de
   * `aria-disabled={busy}` okur). Kancanın kapısı artık ikisini birden
   * kapsıyor: denetim sürerken yayın da başlatılamaz.
   */
  const { busy, error, submit } = useSubmit(async (task: "check" | "publish") => {
    if (task === "check") {
      setReadiness(await api.get<Readiness>(`${base}/readiness`));
      return;
    }
    // Yeniden denetleme güncel sunucu sonucunu gösterir; publish ucu da doğrular.
    const latest = await api.get<Readiness>(`${base}/readiness`);
    setReadiness(latest);
    if (!latest.ready) return;
    await api.post(`${base}/publish`);
    onChanged();
  });
  const check = () => submit("check");
  const publish = () => submit("publish");

  return (
    <li ref={versionRef} tabIndex={linked ? -1 : undefined} aria-label={`${blueprint.title} · ${version.version_no}. sürüm`} className="rounded-2xl border border-border p-5 sm:p-6 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand">
      <div className="flex flex-wrap items-center gap-3">
        <span className="font-medium text-fg">{version.version_no}. sürüm</span>
        <Badge
          tone={
            version.status === "published"
              ? "success"
              : version.status === "draft"
                ? "neutral"
                : "info"
          }
        >
          {VERSION_STATUS_LABEL[version.status]}
        </Badge>
        <span className="text-sm text-fg-muted">
          {version.item_count} soru · {version.total_points} puan
        </span>
        <div className="ml-auto flex flex-wrap gap-2">
          <Button variant="ghost" onClick={() => { setPreview((value) => !value); setOpen(false); }}>
            {preview ? "Önizlemeyi kapat" : "Kâğıdı görüntüle"}
          </Button>
          {version.status === "draft" && (
            <Button variant="ghost" onClick={() => { setOpen((value) => !value); setPreview(false); }}>
              {open ? "Kâğıdı kapat" : "Kâğıdı düzenle"}
            </Button>
          )}
          <Button variant="secondary" onClick={check} aria-disabled={busy}>
            Kapıyı denetle
          </Button>
          {version.status === "draft" && (
            <Button onClick={publish} aria-disabled={busy || readiness?.ready === false}>
              Yayınla
            </Button>
          )}
        </div>
      </div>

      {error && <div className="mt-3">{<ErrorNote message={error} />}</div>}

      {readiness && (
        <div className="mt-3 flex flex-col gap-3">
          <p
            className={`prose-tr rounded-lg px-3 py-2 text-sm ${
              readiness.ready ? "bg-success-bg text-success" : "bg-warning-bg text-warning"
            }`}
          >
            {readiness.message}
          </p>

          {counts.missing > 0 && (
            <div>
              <h4 className="mb-1 text-sm font-semibold text-fg">Blueprint'e uymayan hücreler</h4>
              <ul className="flex flex-col gap-1">
                {readiness.missing_cells.map((cell) => (
                  <li
                    key={`${cell.learning_outcome_id}-${cell.difficulty}-${cell.question_type}`}
                    className="prose-tr rounded-xl border border-border px-4 py-4 text-sm text-fg-muted"
                  >
                    {cell.label}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {counts.unclassified > 0 && (
            <div>
              {/*
               * Ayrı başlık BİR KARARDIR (data-model.md §8 madde 7): bu kalemler
               * hiçbir hücreye sayılmıyor, eksik hücre listesinde görünselerdi
               * öğretmen var olmayan bir eksiği kovalardı.
               */}
              <h4 className="mb-1 text-sm font-semibold text-fg">
                Sınıflandırılmamış sorular
              </h4>
              <p className="prose-tr mb-1 text-sm text-fg-muted">
                Bunlar hiçbir hücreye sayılmıyor. Havuzda öğrenme çıktısı ve zorluk
                atanmadan duran sorulardır.
              </p>
              <p className="prose-tr mb-2 text-sm text-fg-muted">
                {authoringEnabled === false
                  ? "Soru sınıflandırma şu anda kapalı. Mevcut sınıflandırılmış ve onaylı sorularla sınav yayınlanabilir. Kâğıdı düzenleyerek bu soruları değiştir."
                  : authoringEnabled === true
                    ? "Yeni bir taslak soruya öğrenme çıktısı ve zorluk atayıp onayla; ardından kâğıttaki sınıflandırılmamış soruyu değiştir."
                    : "Sınıflandırma kullanılabilirliği henüz doğrulanmadı. Mevcut sınıflandırılmış ve onaylı sorulardan seçim yapabilirsin."}
                {authoringEnabled === true && <> <Link href={`/courses/${courseId}/questions`}
                  className="font-medium text-fg underline underline-offset-4">Soru havuzunu aç</Link></>}
              </p>
              <ul className="flex flex-col gap-1">
                {readiness.unclassified_items.map((item) => (
                  <li
                    key={item.question_id}
                    className="prose-tr rounded-xl border border-border px-4 py-4 text-sm text-fg-muted"
                  >
                    {item.label}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {preview && <PaperPreview base={base} />}
      {open && version.status === "draft" && (
        <PaperEditor
          courseId={courseId}
          base={base}
          outcomes={outcomes}
          onSaved={() => {
            onChanged();
            void check();
          }}
        />
      )}
    </li>
  );
}

/* -------------------------------------------------------------------------
 * Kâğıt düzenleyici — onaylı havuzdan soru seçimi (FR-119 kapısı sunucuda)
 * ---------------------------------------------------------------------- */

function PaperEditor({
  courseId,
  base,
  outcomes,
  onSaved,
}: {
  courseId: string;
  base: string;
  outcomes: LearningOutcome[];
  onSaved: () => void;
}) {
  const pool = usePagedResource<PoolQuestion>(
    `/courses/${courseId}/questions?status=approved`,
    [courseId],
  );
  const items = useResource<ExamItem[]>(() => api.get(`${base}/items`), [base]);
  const [picked, setPicked] = useState<string[] | null>(null);

  const current = picked ?? (items.data ?? []).map((item) => item.question_id);

  const { busy, error, submit: save } = useSubmit(async () => {
    await api.post(
      `${base}/items`,
      current.map((questionId) => ({ question_id: questionId })),
    );
    setPicked(null);
    items.reload();
    onSaved();
  });

  return (
    <div className="mt-4 rounded-2xl border border-border bg-surface-sunken p-5 sm:p-6">
      <h4 className="mb-1 text-sm font-semibold text-fg">Kâğıt</h4>
      <p className="prose-tr mb-3 text-sm text-fg-muted">
        Yalnız onaylanmış sorular konulabilir. Onay kapısı sunucudadır; bu liste onu
        tekrarlamaz, yalnız onaylı havuzu gösterir.
      </p>

      {pool.loading && !pool.data && <Loading label="Havuz yükleniyor…" />}
      {pool.error && (
        <ErrorNote
          message={pool.error}
          kind={pool.errorKind}
          requestId={pool.errorRequestId}
          onRetry={pool.reload}
        />
      )}
      {pool.refreshError && (
        <ErrorNote
          message={pool.refreshError}
          kind={pool.errorKind}
          requestId={pool.errorRequestId}
          onRetry={pool.reload}
        />
      )}

      <ul className="mb-3 flex max-h-80 flex-col gap-1 overflow-y-auto">
        {(pool.data ?? []).map((question) => {
          const checked = current.includes(question.id);
          const outcome = outcomes.find((item) => item.id === question.learning_outcome_id);
          return (
            <li key={question.id}>
              <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border px-4 py-4 text-sm">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() =>
                    setPicked(
                      checked
                        ? current.filter((id) => id !== question.id)
                        : [...current, question.id],
                    )
                  }
                  className="mt-1"
                />
                <span className="flex flex-col gap-1">
                  <span className="text-fg">
                    {String(question.payload?.stem ?? question.payload?.prompt ?? question.id)}
                  </span>
                  <span className="flex flex-wrap gap-2 text-sm text-fg-muted">
                    <span>{QUESTION_TYPE[question.type]}</span>
                    {question.difficulty ? (
                      <span>{DIFFICULTY_LABEL[question.difficulty]}</span>
                    ) : (
                      <span className="text-warning">zorluk atanmamış</span>
                    )}
                    {outcome ? (
                      <span>{outcome.code}</span>
                    ) : (
                      <span className="text-warning">çıktı atanmamış</span>
                    )}
                  </span>
                </span>
              </label>
            </li>
          );
        })}
      </ul>

      <LoadMore
        hasMore={pool.nextCursor !== null}
        busy={pool.loadingMore}
        error={pool.pageError}
        onLoadMore={() => void pool.loadMore()}
      />

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={save} aria-disabled={busy}>
          {busy ? "Kaydediliyor…" : "Kâğıdı kaydet"}
        </Button>
        <span className="text-sm text-fg-muted">{current.length} soru seçili</span>
      </div>

      {error && <div className="mt-3">{<ErrorNote message={error} />}</div>}
    </div>
  );
}
