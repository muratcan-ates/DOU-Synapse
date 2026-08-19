"use client";

/**
 * Sınav blueprint'i kurma ekranı (T509). Uçlar:
 * `GET/POST /courses/{id}/learning-outcomes`, `GET/POST /courses/{id}/blueprints`,
 * `POST /courses/{id}/blueprints/{bid}` (güncelle),
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

import { useParams } from "next/navigation";
import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import {
  assessmentPoolQuestions,
  DIFFICULTIES,
  DIFFICULTY_LABEL,
  editingNoticeFor,
  readinessCounts,
  splitByShares,
  totalPoints,
  totalQuestions,
  VERSION_STATUS_LABEL,
  type Blueprint,
  type BlueprintCellInput,
  type Difficulty,
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
import { Field } from "@/components/field";
import { InstructorGate } from "@/components/instructor-gate";
import { ErrorNote, Loading, LoadMore, MetricRow, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, EmptyState, Input } from "@/components/ui";

const DEFAULT_TYPE = "mcq" as const;

export default function BlueprintsPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isInstructor, ready } = useSession(courseId);
  return (
    <AppShell>
      <CourseNav courseId={courseId} />
      <InstructorGate
        ready={ready}
        isInstructor={isInstructor}
        fallback={
          <EmptyState title="Sınav blueprint'i eğitmen aracıdır; bu sayfa sana kapalı." />
        }
      >
        <BlueprintWorkspace courseId={courseId} />
      </InstructorGate>
    </AppShell>
  );
}

/**
 * Eğitmen verisi rol doğrulanmadan önce mount edilmez. `useResource` ilk
 * mount'ta istek attığı için bu sınırın üstüne taşınması öğrenci doğrudan URL'yi
 * açtığında blueprint ve çıktı isteklerini başlatırdı.
 */
function BlueprintWorkspace({ courseId }: { courseId: string }) {
  const outcomes = useResource<LearningOutcome[]>(
    () => api.get(`/courses/${courseId}/learning-outcomes`),
    [courseId],
  );
  const blueprints = useResource<Blueprint[]>(
    () => api.get(`/courses/${courseId}/blueprints`),
    [courseId],
  );

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = blueprints.data?.find((item) => item.id === selectedId) ?? null;

  return (
    <>
      <PageHeader
        title="Sınav blueprint'i"
        description="Sınavın çatısını sorulardan önce çiz: hangi öğrenme çıktısından, hangi zorlukta, kaç soru."
      />

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

      <OutcomesCard courseId={courseId} outcomes={outcomes} />

      <BlueprintListCard
        courseId={courseId}
        blueprints={blueprints}
        outcomes={outcomes.data ?? []}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />

      {selected && (
        <BlueprintDetail
          courseId={courseId}
          blueprint={selected}
          outcomes={outcomes.data ?? []}
          onChanged={blueprints.reload}
        />
      )}
    </>
  );
}

/* -------------------------------------------------------------------------
 * Öğrenme çıktıları (FR-110)
 * ---------------------------------------------------------------------- */

function OutcomesCard({
  courseId,
  outcomes,
}: {
  courseId: string;
  outcomes: ReturnType<typeof useResource<LearningOutcome[]>>;
}) {
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");

  const { busy, error, submit } = useSubmit(async () => {
    await api.post(`/courses/${courseId}/learning-outcomes`, {
      code: code.trim(),
      description: description.trim(),
    });
    setCode("");
    setDescription("");
    outcomes.reload();
  });

  return (
    <Card className="mb-6">
      <h2 className="mb-1 text-lg font-semibold text-fg">Öğrenme çıktıları</h2>
      <p className="prose-tr mb-4 text-sm text-fg-muted">
        Dağılımın ekseni budur: her hücre bir çıktıya bağlanır. Konu dağılımı ayrıca
        girilmez, çıktının konusundan türetilir.
      </p>

      {outcomes.loading && !outcomes.data && <Loading label="Çıktılar yükleniyor…" />}
      {outcomes.error && (
        <ErrorNote
          message={outcomes.error}
          kind={outcomes.errorKind}
          requestId={outcomes.errorRequestId}
          onRetry={outcomes.reload}
        />
      )}

      {outcomes.data && outcomes.data.length > 0 && (
        <ul className="mb-4 flex flex-col gap-2">
          {outcomes.data.map((outcome) => (
            <li
              key={outcome.id}
              className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-lg border border-border px-3 py-2"
            >
              <span className="font-mono text-sm text-fg">{outcome.code}</span>
              <span className="prose-tr text-sm text-fg-muted">{outcome.description}</span>
              {outcome.topic_id === null && (
                <Badge tone="neutral">Konusuz — konu dağılımına girmez</Badge>
              )}
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <Field label="Kod">
          {(control) => (
            <Input
              {...control}
              value={code}
              onChange={(event) => setCode(event.target.value)}
              placeholder="CO1"
              className="w-28"
            />
          )}
        </Field>
        <Field label="Açıklama">
          {(control) => (
            <Input
              {...control}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Kilitlenmenin dört koşulunu sayar"
              className="w-80"
            />
          )}
        </Field>
        <Button
          onClick={submit}
          aria-disabled={busy || code.trim() === "" || description.trim() === ""}
        >
          {busy ? "Ekleniyor…" : "Çıktı ekle"}
        </Button>
      </div>

      {error && <div className="mt-3">{<ErrorNote message={error} />}</div>}
    </Card>
  );
}

/* -------------------------------------------------------------------------
 * Blueprint listesi ve kurma (FR-111, FR-112)
 * ---------------------------------------------------------------------- */

function BlueprintListCard({
  courseId,
  blueprints,
  outcomes,
  selectedId,
  onSelect,
}: {
  courseId: string;
  blueprints: ReturnType<typeof useResource<Blueprint[]>>;
  outcomes: LearningOutcome[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [creating, setCreating] = useState(false);

  return (
    <Card className="mb-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-fg">Sınavlar</h2>
        <Button
          variant="secondary"
          onClick={() => setCreating((value) => !value)}
          aria-disabled={outcomes.length === 0}
        >
          {creating ? "Vazgeç" : "Yeni sınav kur"}
        </Button>
      </div>

      {outcomes.length === 0 && (
        <p className="prose-tr mb-4 text-sm text-fg-muted">
          Önce en az bir öğrenme çıktısı tanımla: dağılım hücreleri çıktılara bağlanır.
        </p>
      )}

      {creating && (
        <CreateBlueprintForm
          courseId={courseId}
          outcomes={outcomes}
          onCreated={(id) => {
            setCreating(false);
            blueprints.reload();
            onSelect(id);
          }}
        />
      )}

      {blueprints.loading && !blueprints.data && <Loading label="Sınavlar yükleniyor…" />}
      {blueprints.error && (
        <ErrorNote
          message={blueprints.error}
          kind={blueprints.errorKind}
          requestId={blueprints.errorRequestId}
          onRetry={blueprints.reload}
        />
      )}

      {blueprints.data && blueprints.data.length === 0 && !creating && (
        <EmptyState title="Henüz sınav kurulmadı." />
      )}

      {blueprints.data && blueprints.data.length > 0 && (
        <ul className="flex flex-col gap-2">
          {blueprints.data.map((blueprint) => (
            <li key={blueprint.id}>
              <button
                type="button"
                onClick={() => onSelect(blueprint.id)}
                aria-current={blueprint.id === selectedId ? "true" : undefined}
                className={`flex w-full flex-wrap items-center gap-3 rounded-lg border px-4 py-3 text-left transition-colors ${
                  blueprint.id === selectedId
                    ? "border-border-strong bg-brand-subtle/30"
                    : "border-border hover:border-border-strong"
                }`}
              >
                <span className="font-medium text-fg">{blueprint.title}</span>
                <span className="text-sm text-fg-muted">
                  {blueprint.total_questions} soru · {blueprint.total_points} puan ·{" "}
                  {blueprint.duration_minutes} dk
                </span>
                {blueprint.published_version_no === null ? (
                  <Badge tone="neutral">Yayında değil</Badge>
                ) : (
                  <Badge tone="success">
                    {blueprint.published_version_no}. sürüm yayında
                  </Badge>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function CreateBlueprintForm({
  courseId,
  outcomes,
  onCreated,
}: {
  courseId: string;
  outcomes: LearningOutcome[];
  onCreated: (id: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [duration, setDuration] = useState("60");
  const [attempts, setAttempts] = useState("1");
  const [cells, setCells] = useState<BlueprintCellInput[]>([]);

  const { busy, error, submit } = useSubmit(async () => {
    const created = await api.post<Blueprint>(`/courses/${courseId}/blueprints`, {
      title: title.trim(),
      duration_minutes: Number(duration),
      max_attempts: Number(attempts),
      cells,
      // Sunucu ayrıca doğrulasın diye toplamı da gönderiyoruz: yuvarlamayı ekran
      // yaptı, ama tuttuğunu ekranın kendisi ilan etmemeli (Anayasa III).
      targets: { total_questions: totalQuestions(cells) },
    });
    onCreated(created.id);
  });

  return (
    <div className="mb-6 rounded-lg border border-border-strong p-4">
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Field label="Sınav adı">
          {(control) => (
            <Input
              {...control}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Vize"
              className="w-64"
            />
          )}
        </Field>
        <Field label="Süre (dakika)">
          {(control) => (
            <Input
              {...control}
              type="number"
              min={1}
              max={600}
              value={duration}
              onChange={(event) => setDuration(event.target.value)}
              className="w-28"
            />
          )}
        </Field>
        <Field label="Deneme hakkı">
          {(control) => (
            <Input
              {...control}
              type="number"
              min={1}
              value={attempts}
              onChange={(event) => setAttempts(event.target.value)}
              className="w-28"
            />
          )}
        </Field>
      </div>

      <CellEditor outcomes={outcomes} cells={cells} onChange={setCells} />

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button onClick={submit} aria-disabled={busy || title.trim() === "" || cells.length === 0}>
          {busy ? "Kaydediliyor…" : "Sınavı kur"}
        </Button>
        <span className="text-sm text-fg-muted">
          {totalQuestions(cells)} soru · {totalPoints(cells)} puan
        </span>
      </div>

      {error && <div className="mt-3">{<ErrorNote message={error} />}</div>}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Hücre düzenleyici — dağılımın atomik birimi
 * ---------------------------------------------------------------------- */

function CellEditor({
  outcomes,
  cells,
  onChange,
}: {
  outcomes: LearningOutcome[];
  cells: BlueprintCellInput[];
  onChange: (cells: BlueprintCellInput[]) => void;
}) {
  const [outcomeId, setOutcomeId] = useState(outcomes[0]?.id ?? "");
  const [total, setTotal] = useState("10");
  const [shares, setShares] = useState<Record<Difficulty, string>>({
    easy: "40",
    medium: "40",
    hard: "20",
  });

  const spread = useCallback(() => {
    const outcome = outcomeId || outcomes[0]?.id;
    if (!outcome) return;
    const counts = splitByShares(
      Number(total) || 0,
      DIFFICULTIES.map((level) => Number(shares[level]) || 0),
    );
    const fresh = DIFFICULTIES.map((level, index) => ({
      learning_outcome_id: outcome,
      difficulty: level,
      question_type: DEFAULT_TYPE,
      question_count: counts[index],
      points_per_question: 5,
    })).filter((cell) => cell.question_count > 0);

    const others = cells.filter((cell) => cell.learning_outcome_id !== outcome);
    onChange([...others, ...fresh]);
  }, [cells, onChange, outcomeId, outcomes, shares, total]);

  return (
    <div>
      <h3 className="mb-1 text-sm font-semibold text-fg">Dağılım</h3>
      <p className="prose-tr mb-3 text-sm text-fg-muted">
        Yüzde gir, adete çevrilsin. Saklanan gerçek adettir; yuvarlama artığı en büyük
        paya eklenir, böylece toplam her zaman tam tutar.
      </p>

      <div className="mb-3 flex flex-wrap items-end gap-3">
        <Field label="Öğrenme çıktısı">
          {(control) => (
            <select
              {...control}
              value={outcomeId}
              onChange={(event) => setOutcomeId(event.target.value)}
              className="h-11 rounded-lg border border-border-strong bg-surface px-3 text-sm text-fg"
            >
              {outcomes.map((outcome) => (
                <option key={outcome.id} value={outcome.id}>
                  {outcome.code}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Soru sayısı">
          {(control) => (
            <Input
              {...control}
              type="number"
              min={1}
              value={total}
              onChange={(event) => setTotal(event.target.value)}
              className="w-24"
            />
          )}
        </Field>
        {DIFFICULTIES.map((level) => (
          <Field key={level} label={`${DIFFICULTY_LABEL[level]} %`}>
            {(control) => (
              <Input
                {...control}
                type="number"
                min={0}
                max={100}
                value={shares[level]}
                onChange={(event) =>
                  setShares((current) => ({ ...current, [level]: event.target.value }))
                }
                className="w-20"
              />
            )}
          </Field>
        ))}
        <Button variant="secondary" onClick={spread}>
          Hücrelere aç
        </Button>
      </div>

      {cells.length === 0 ? (
        <p className="prose-tr text-sm text-fg-muted">Henüz hücre yok.</p>
      ) : (
        <ul className="flex flex-col gap-1">
          {cells.map((cell, index) => {
            const outcome = outcomes.find((item) => item.id === cell.learning_outcome_id);
            return (
              <li
                key={`${cell.learning_outcome_id}-${cell.difficulty}-${cell.question_type}`}
                className="flex flex-wrap items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm"
              >
                <span className="font-mono text-fg">{outcome?.code ?? "?"}</span>
                <span className="text-fg-muted">{DIFFICULTY_LABEL[cell.difficulty]}</span>
                <span className="text-fg-muted">{QUESTION_TYPE[cell.question_type]}</span>
                <span className="text-fg">{cell.question_count} soru</span>
                <span className="text-fg-muted">{cell.points_per_question} puan</span>
                <Button
                  variant="ghost"
                  className="ml-auto"
                  onClick={() => onChange(cells.filter((_, i) => i !== index))}
                >
                  Kaldır
                </Button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Seçili blueprint: sürümler, kapı, yayın (FR-114, FR-115)
 * ---------------------------------------------------------------------- */

function BlueprintDetail({
  courseId,
  blueprint,
  outcomes,
  onChanged,
}: {
  courseId: string;
  blueprint: Blueprint;
  outcomes: LearningOutcome[];
  onChanged: () => void;
}) {
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
      <Card className="mb-6">
        <h2 className="mb-1 text-lg font-semibold text-fg">{blueprint.title} · dağılım</h2>
        {notice && (
          <p className="prose-tr mb-3 rounded-lg border border-border bg-bg px-3 py-2 text-sm text-fg-muted">
            {notice}
          </p>
        )}

        <ul className="mb-4 flex flex-col gap-1">
          {blueprint.cells.map((cell) => (
            <li
              key={cell.id}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-border px-3 py-2 text-sm"
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
          <h2 className="text-lg font-semibold text-fg">Sürümler</h2>
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

        <ul className="flex flex-col gap-4">
          {(versions.data ?? []).map((version) => (
            <VersionRow
              key={version.id}
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
  courseId,
  blueprint,
  version,
  outcomes,
  onChanged,
}: {
  courseId: string;
  blueprint: Blueprint;
  version: ExamVersion;
  outcomes: LearningOutcome[];
  onChanged: () => void;
}) {
  const base = `/courses/${courseId}/blueprints/${blueprint.id}/versions/${version.id}`;
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [open, setOpen] = useState(false);

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
    await api.post(`${base}/publish`);
    onChanged();
  });
  const check = () => submit("check");
  const publish = () => submit("publish");

  return (
    <li className="rounded-lg border border-border p-4">
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
          {version.status === "draft" && (
            <Button variant="ghost" onClick={() => setOpen((value) => !value)}>
              {open ? "Kâğıdı kapat" : "Kâğıdı düzenle"}
            </Button>
          )}
          <Button variant="secondary" onClick={check} aria-disabled={busy}>
            Kapıyı denetle
          </Button>
          {version.status === "draft" && (
            <Button onClick={publish} aria-disabled={busy}>
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
                    className="prose-tr rounded-lg border border-border px-3 py-2 text-sm text-fg-muted"
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
              <p className="prose-tr mb-1 text-xs text-fg-muted">
                Bunlar hiçbir hücreye sayılmıyor. Havuzda öğrenme çıktısı ve zorluk
                atanmadan duran sorulardır.
              </p>
              <ul className="flex flex-col gap-1">
                {readiness.unclassified_items.map((item) => (
                  <li
                    key={item.question_id}
                    className="prose-tr rounded-lg border border-border px-3 py-2 text-sm text-fg-muted"
                  >
                    {item.label}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

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
    `/courses/${courseId}/questions?status=approved&purpose=assessment`,
    [courseId],
  );
  const items = useResource<ExamItem[]>(() => api.get(`${base}/items`), [base]);
  const [picked, setPicked] = useState<string[] | null>(null);

  const current = picked ?? (items.data ?? []).map((item) => item.question_id);
  const officialQuestions = assessmentPoolQuestions(pool.data ?? []);

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
    <div className="mt-4 rounded-lg border border-border-strong p-4">
      <h4 className="mb-1 text-sm font-semibold text-fg">Kâğıt</h4>
      <p className="prose-tr mb-3 text-sm text-fg-muted">
        Yalnız resmî sınav amacıyla üretilmiş ve onaylanmış sorular seçilebilir.
        Prova soruları bu listede gösterilmez ve resmî kâğıda eklenemez.
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

      {pool.data && officialQuestions.length === 0 && (
        <p className="prose-tr mb-3 rounded-lg border border-border bg-bg px-3 py-3 text-sm text-fg-muted">
          Onaylanmış resmî sınav sorusu yok. Soru havuzunda kullanım amacını
          “Resmî sınav” seçerek soru üretin; prova soruları burada bilinçli olarak
          gösterilmez.
        </p>
      )}

      <ul className="mb-3 flex max-h-80 flex-col gap-1 overflow-y-auto">
        {officialQuestions.map((question) => {
          const checked = current.includes(question.id);
          const outcome = outcomes.find((item) => item.id === question.learning_outcome_id);
          return (
            <li key={question.id}>
              <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-border px-3 py-2 text-sm">
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
                  <span className="flex flex-wrap gap-2 text-xs text-fg-muted">
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
