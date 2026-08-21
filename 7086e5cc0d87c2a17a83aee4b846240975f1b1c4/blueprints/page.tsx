"use client";

<<<<<<< HEAD
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
import { errorMessage } from "@/lib/errors";
import { QUESTION_TYPE } from "@/lib/labels";
import { useSession } from "@/lib/session";
import { useResource } from "@/lib/use-resource";
=======
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
>>>>>>> codex/production-completion
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { Field } from "@/components/field";
import { ErrorNote, Loading, MetricRow, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, EmptyState, Input } from "@/components/ui";
<<<<<<< HEAD

const DEFAULT_TYPE = "mcq" as const;

export default function BlueprintsPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isInstructor, ready } = useSession();

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

  if (ready && !isInstructor) {
    return (
      <AppShell>
        <CourseNav courseId={courseId} />
        <EmptyState title="Sınav blueprint'i eğitmen aracıdır; bu sayfa sana kapalı." />
      </AppShell>
    );
  }
=======
import { api } from "@/lib/api";
import {
  blueprintDraftTotals,
  DIFFICULTY_LABEL,
  eligibleQuestions,
  emptyBlueprintCell,
  QUESTION_TYPE_LABEL,
  questionStem,
  type BlueprintCellDraft,
} from "@/lib/blueprints";
import { errorMessage } from "@/lib/errors";
import { useSession } from "@/lib/session";
import type {
  BlueprintReadiness,
  ExamBlueprint,
  ExamItem,
  ExamVersion,
  LearningOutcome,
  Page,
  Question,
  QuestionDifficulty,
  QuestionGeneration,
  QuestionType,
  Topic,
} from "@/lib/types";
import { useResource } from "@/lib/use-resource";

const SELECT_CLASS =
  "h-11 w-full rounded-lg border border-border-strong bg-surface px-3 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand";

interface BlueprintWorkspaceData {
  outcomes: LearningOutcome[];
  blueprints: ExamBlueprint[];
  topics: Topic[];
  questions: Question[];
}

export default function BlueprintsPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isInstructor, ready } = useSession(courseId);
>>>>>>> codex/production-completion

  return (
    <AppShell>
      <CourseNav courseId={courseId} />
      <PageHeader
<<<<<<< HEAD
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
=======
        title="Sınav planı"
        description="Önce öğrenme çıktıları ve dağılımı kurun; sonra AI taslakları üretin, onaylı sorulardan sürüm hazırlayıp yayınlayın."
      />
      {!ready ? (
        <Loading />
      ) : isInstructor ? (
        <BlueprintWorkspace courseId={courseId} />
      ) : (
        <EmptyState title="Sınav planı yalnızca dersin eğitmenine gösterilir." />
>>>>>>> codex/production-completion
      )}
    </AppShell>
  );
}

<<<<<<< HEAD
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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/courses/${courseId}/learning-outcomes`, {
        code: code.trim(),
        description: description.trim(),
      });
      setCode("");
      setDescription("");
      outcomes.reload();
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setBusy(false);
    }
  }, [code, courseId, description, outcomes]);

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
=======
function BlueprintWorkspace({ courseId }: { courseId: string }) {
  const fetchData = useCallback(async (): Promise<BlueprintWorkspaceData> => {
    const [outcomes, blueprints, topics, questions] = await Promise.all([
      api.get<LearningOutcome[]>(`/courses/${courseId}/learning-outcomes`),
      api.get<ExamBlueprint[]>(`/courses/${courseId}/blueprints`),
      api.get<Topic[]>(`/courses/${courseId}/topics`),
      api
        .get<Page<Question>>(`/courses/${courseId}/questions?limit=100`)
        .then((page) => page.items),
    ]);
    return { outcomes, blueprints, topics, questions };
  }, [courseId]);
  const { data, error, reload } = useResource(fetchData, [courseId]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (error && !data) return <ErrorNote message={error} onRetry={reload} />;
  if (!data) return <Loading label="Sınav planları yükleniyor…" />;

  const selected =
    data.blueprints.find((blueprint) => blueprint.id === selectedId) ??
    data.blueprints[0] ??
    null;

  return (
    <div className="space-y-6">
      {error && <ErrorNote message={error} onRetry={reload} />}
      {notice && (
        <p role="status" className="text-sm text-success">
          {notice}
        </p>
      )}

      <MetricRow
        items={[
          { value: data.outcomes.length, label: "Öğrenme çıktısı" },
          { value: data.blueprints.length, label: "Sınav planı" },
          {
            value: data.blueprints.filter((blueprint) => blueprint.published_version_no).length,
            label: "Yayında",
          },
          {
            value: data.questions.filter((question) => question.status === "approved").length,
            label: "Onaylı soru",
          },
        ]}
      />

      <OutcomePanel
        courseId={courseId}
        outcomes={data.outcomes}
        topics={data.topics}
        onChanged={async (message) => {
          setNotice(message);
          await reload();
        }}
      />

      <BlueprintCreatePanel
        courseId={courseId}
        outcomes={data.outcomes}
        onCreated={async (blueprint) => {
          setSelectedId(blueprint.id);
          setNotice(`“${blueprint.title}” sınav planı taslak olarak oluşturuldu.`);
          await reload();
        }}
      />

      {data.blueprints.length > 0 && (
        <section aria-labelledby="saved-blueprints-title">
          <h2 id="saved-blueprints-title" className="mb-3 text-lg font-medium text-fg">
            Kayıtlı sınav planları
          </h2>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {data.blueprints.map((blueprint) => (
              <button
                type="button"
                key={blueprint.id}
                onClick={() => setSelectedId(blueprint.id)}
                aria-pressed={selected?.id === blueprint.id}
                className={`rounded-lg border bg-surface p-4 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
                  selected?.id === blueprint.id ? "border-brand" : "border-border"
                }`}
              >
                <span className="flex items-start justify-between gap-3">
                  <span className="font-medium text-fg">{blueprint.title}</span>
                  <Badge tone={blueprint.published_version_no ? "success" : "info"}>
                    {blueprint.published_version_no
                      ? `v${blueprint.published_version_no} yayında`
                      : "Taslak"}
                  </Badge>
                </span>
                <span className="mt-2 block text-xs text-fg-muted">
                  {blueprint.total_questions} soru · {blueprint.total_points} puan ·{" "}
                  {blueprint.duration_minutes} dakika
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      {selected && (
        <BlueprintDetail
          courseId={courseId}
          blueprint={selected}
          outcomes={data.outcomes}
          questions={data.questions}
          onChanged={async (message) => {
            setNotice(message);
            await reload();
          }}
        />
      )}
    </div>
  );
}

function OutcomePanel({
  courseId,
  outcomes,
  topics,
  onChanged,
}: {
  courseId: string;
  outcomes: LearningOutcome[];
  topics: Topic[];
  onChanged: (message: string) => Promise<void>;
}) {
  const [code, setCode] = useState("");
  const [description, setDescription] = useState("");
  const [topicId, setTopicId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const outcome = await api.post<LearningOutcome>(`/courses/${courseId}/learning-outcomes`, {
        code: code.trim(),
        description: description.trim(),
        topic_id: topicId || null,
      });
      setCode("");
      setDescription("");
      setTopicId("");
      await onChanged(`${outcome.code} öğrenme çıktısı eklendi.`);
    } catch (cause) {
      setError(errorMessage(cause, "Öğrenme çıktısı eklenemedi."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <div className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <div>
          <h2 className="text-lg font-medium text-fg">1. Öğrenme çıktıları</h2>
          <p className="prose-tr mt-1 text-sm text-fg-muted">
            Her soru tek, ölçülebilir bir çıktıya bağlanır. Konu bağı, AI üretiminde hangi
            materyalin aranacağını belirler.
          </p>
          {outcomes.length === 0 ? (
            <p className="mt-4 text-sm text-fg-muted">Henüz çıktı tanımlanmadı.</p>
          ) : (
            <ul className="mt-4 divide-y divide-border border-y border-border">
              {outcomes.map((outcome) => (
                <li key={outcome.id} className="py-3">
                  <p className="font-mono text-xs text-brand">{outcome.code}</p>
                  <p className="prose-tr mt-1 text-sm text-fg">{outcome.description}</p>
                  <p className="mt-1 text-xs text-fg-subtle">
                    {topics.find((topic) => topic.id === outcome.topic_id)?.name ??
                      "Konuya bağlanmadı"}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
        <form onSubmit={submit} className="space-y-4" aria-label="Öğrenme çıktısı ekle">
          <Field label="Çıktı kodu">
            {(control) => (
              <Input {...control} value={code} onChange={(event) => setCode(event.target.value)} required />
            )}
          </Field>
          <Field label="Ölçülebilir açıklama">
            {(control) => (
              <textarea
                {...control}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                required
                rows={3}
                className="w-full rounded-lg border border-border-strong bg-surface px-3 py-2 text-sm text-fg focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand"
              />
            )}
          </Field>
          <Field label="Bağlı konu">
            {(control) => (
              <select {...control} className={SELECT_CLASS} value={topicId} onChange={(event) => setTopicId(event.target.value)}>
                <option value="">Konuya bağlama</option>
                {topics.map((topic) => <option key={topic.id} value={topic.id}>{topic.name}</option>)}
              </select>
            )}
          </Field>
          {error && <ErrorNote message={error} />}
          <Button type="submit" aria-disabled={busy || !code.trim() || !description.trim()}>
            {busy ? "Ekleniyor…" : "Çıktıyı ekle"}
          </Button>
        </form>
      </div>
>>>>>>> codex/production-completion
    </Card>
  );
}

<<<<<<< HEAD
function CreateBlueprintForm({
=======
function BlueprintCreatePanel({
>>>>>>> codex/production-completion
  courseId,
  outcomes,
  onCreated,
}: {
  courseId: string;
  outcomes: LearningOutcome[];
<<<<<<< HEAD
  onCreated: (id: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [duration, setDuration] = useState("60");
  const [attempts, setAttempts] = useState("1");
  const [cells, setCells] = useState<BlueprintCellInput[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
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
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setBusy(false);
    }
  }, [attempts, cells, courseId, duration, onCreated, title]);

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

=======
  onCreated: (blueprint: ExamBlueprint) => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [duration, setDuration] = useState(60);
  const [attempts, setAttempts] = useState(1);
  const [opensAt, setOpensAt] = useState("");
  const [closesAt, setClosesAt] = useState("");
  const [cells, setCells] = useState<BlueprintCellDraft[]>([emptyBlueprintCell(outcomes)]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const totals = blueprintDraftTotals(cells);

  useEffect(() => {
    if (outcomes.length && cells.every((cell) => cell.learning_outcome_id === "")) {
      setCells([emptyBlueprintCell(outcomes)]);
    }
  }, [outcomes, cells]);

  function updateCell(index: number, patch: Partial<BlueprintCellDraft>) {
    setCells((current) => current.map((cell, position) => position === index ? { ...cell, ...patch } : cell));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy || !outcomes.length) return;
    setBusy(true);
    setError(null);
    try {
      const blueprint = await api.post<ExamBlueprint>(`/courses/${courseId}/blueprints`, {
        title: title.trim(),
        description: description.trim() || null,
        duration_minutes: duration,
        max_attempts: attempts,
        opens_at: opensAt ? new Date(opensAt).toISOString() : null,
        closes_at: closesAt ? new Date(closesAt).toISOString() : null,
        cells,
      });
      setTitle("");
      setDescription("");
      setCells([emptyBlueprintCell(outcomes)]);
      await onCreated(blueprint);
    } catch (cause) {
      setError(errorMessage(cause, "Sınav planı oluşturulamadı."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-medium text-fg">2. Dağılımı kur</h2>
          <p className="prose-tr mt-1 text-sm text-fg-muted">
            Her satır bir çıktı, zorluk ve soru tipi hücresidir. Yayın kapısı bu adetleri
            birebir arar.
          </p>
        </div>
        <p className="font-mono text-sm text-fg-muted">
          {totals.questions} soru · {totals.points} puan
        </p>
      </div>
      {outcomes.length === 0 ? (
        <EmptyState title="Önce en az bir öğrenme çıktısı ekleyin." />
      ) : (
        <form onSubmit={submit} className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Sınav adı">
              {(control) => <Input {...control} value={title} onChange={(event) => setTitle(event.target.value)} required />}
            </Field>
            <Field label="Açıklama">
              {(control) => <Input {...control} value={description} onChange={(event) => setDescription(event.target.value)} />}
            </Field>
            <Field label="Süre (dakika)">
              {(control) => <Input {...control} type="number" min={1} max={600} value={duration} onChange={(event) => setDuration(Number(event.target.value))} />}
            </Field>
            <Field label="En fazla deneme">
              {(control) => <Input {...control} type="number" min={1} max={100} value={attempts} onChange={(event) => setAttempts(Number(event.target.value))} />}
            </Field>
            <Field label="Açılış zamanı">
              {(control) => <Input {...control} type="datetime-local" value={opensAt} onChange={(event) => setOpensAt(event.target.value)} />}
            </Field>
            <Field label="Kapanış zamanı">
              {(control) => <Input {...control} type="datetime-local" value={closesAt} onChange={(event) => setClosesAt(event.target.value)} />}
            </Field>
          </div>

          <div className="space-y-3">
            {cells.map((cell, index) => (
              <div key={index} className="grid gap-3 rounded-lg border border-border p-4 lg:grid-cols-[1.4fr_1fr_1.2fr_.7fr_.7fr_auto]">
                <Field label="Öğrenme çıktısı">
                  {(control) => <select {...control} className={SELECT_CLASS} value={cell.learning_outcome_id} onChange={(event) => updateCell(index, { learning_outcome_id: event.target.value })}>{outcomes.map((outcome) => <option key={outcome.id} value={outcome.id}>{outcome.code}</option>)}</select>}
                </Field>
                <Field label="Zorluk">
                  {(control) => <select {...control} className={SELECT_CLASS} value={cell.difficulty} onChange={(event) => updateCell(index, { difficulty: event.target.value as QuestionDifficulty })}>{(Object.keys(DIFFICULTY_LABEL) as QuestionDifficulty[]).map((value) => <option key={value} value={value}>{DIFFICULTY_LABEL[value]}</option>)}</select>}
                </Field>
                <Field label="Soru tipi">
                  {(control) => <select {...control} className={SELECT_CLASS} value={cell.question_type} onChange={(event) => updateCell(index, { question_type: event.target.value as QuestionType })}>{(Object.keys(QUESTION_TYPE_LABEL) as QuestionType[]).map((value) => <option key={value} value={value}>{QUESTION_TYPE_LABEL[value]}</option>)}</select>}
                </Field>
                <Field label="Adet">
                  {(control) => <Input {...control} type="number" min={1} max={100} value={cell.question_count} onChange={(event) => updateCell(index, { question_count: Number(event.target.value) })} />}
                </Field>
                <Field label="Puan">
                  {(control) => <Input {...control} type="number" min={1} max={100} value={cell.points_per_question} onChange={(event) => updateCell(index, { points_per_question: Number(event.target.value) })} />}
                </Field>
                <Button type="button" variant="ghost" aria-label={`${index + 1}. hücreyi kaldır`} aria-disabled={cells.length === 1} onClick={() => setCells((current) => current.filter((_, position) => position !== index))}>Kaldır</Button>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Button type="button" variant="secondary" onClick={() => setCells((current) => [...current, emptyBlueprintCell(outcomes)])}>Hücre ekle</Button>
            <Button type="submit" aria-disabled={busy || !title.trim()}>{busy ? "Oluşturuluyor…" : "Sınav planını oluştur"}</Button>
          </div>
          {error && <ErrorNote message={error} />}
        </form>
      )}
    </Card>
  );
}

>>>>>>> codex/production-completion
function BlueprintDetail({
  courseId,
  blueprint,
  outcomes,
<<<<<<< HEAD
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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const notice = editingNoticeFor(blueprint);

  const createVersion = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/courses/${courseId}/blueprints/${blueprint.id}/versions`);
      versions.reload();
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setBusy(false);
    }
  }, [blueprint.id, courseId, versions]);

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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  const counts = readinessCounts(readiness);

  const check = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setReadiness(await api.get<Readiness>(`${base}/readiness`));
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setBusy(false);
    }
  }, [base]);

  const publish = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post(`${base}/publish`);
      onChanged();
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setBusy(false);
    }
  }, [base, onChanged]);

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
  const pool = useResource<PoolQuestion[]>(
    () => api.get(`/courses/${courseId}/questions?status=approved`),
    [courseId],
  );
  const items = useResource<ExamItem[]>(() => api.get(`${base}/items`), [base]);
  const [picked, setPicked] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const current = picked ?? (items.data ?? []).map((item) => item.question_id);

  const save = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post(
        `${base}/items`,
        current.map((questionId) => ({ question_id: questionId })),
      );
      setPicked(null);
      items.reload();
      onSaved();
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setBusy(false);
    }
  }, [base, current, items, onSaved]);

  return (
    <div className="mt-4 rounded-lg border border-border-strong p-4">
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

      <ul className="mb-3 flex max-h-80 flex-col gap-1 overflow-y-auto">
        {(pool.data ?? []).map((question) => {
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

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={save} aria-disabled={busy}>
          {busy ? "Kaydediliyor…" : "Kâğıdı kaydet"}
        </Button>
        <span className="text-sm text-fg-muted">{current.length} soru seçili</span>
      </div>

      {error && <div className="mt-3">{<ErrorNote message={error} />}</div>}
    </div>
=======
  questions,
  onChanged,
}: {
  courseId: string;
  blueprint: ExamBlueprint;
  outcomes: LearningOutcome[];
  questions: Question[];
  onChanged: (message: string) => Promise<void>;
}) {
  const [busyCell, setBusyCell] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function generate(cellId: string) {
    const cell = blueprint.cells.find((candidate) => candidate.id === cellId);
    const outcome = outcomes.find((candidate) => candidate.id === cell?.learning_outcome_id);
    if (!cell || !outcome?.topic_id) {
      setError("AI üretimi için öğrenme çıktısını bir konuya bağlayın.");
      return;
    }
    setBusyCell(cell.id);
    setError(null);
    try {
      const report = await api.post<QuestionGeneration>(`/courses/${courseId}/questions/generate`, {
        topic_id: outcome.topic_id,
        learning_outcome_id: outcome.id,
        difficulty: cell.difficulty,
        question_type: cell.question_type,
        count: cell.question_count,
      });
      await onChanged(
        `${cell.label} için ${report.accepted}/${report.requested} taslak üretildi. Onay için soru havuzuna gidin.`,
      );
    } catch (cause) {
      setError(errorMessage(cause, "Blueprint hücresinden soru üretilemedi."));
    } finally {
      setBusyCell(null);
    }
  }

  return (
    <section className="space-y-5" aria-labelledby="blueprint-detail-title">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 id="blueprint-detail-title" className="text-lg font-medium text-fg">3. {blueprint.title}</h2>
            <p className="mt-1 text-sm text-fg-muted">{blueprint.description || "Açıklama girilmedi."}</p>
          </div>
          <Link href={`/courses/${courseId}/questions`} className="inline-flex h-11 items-center rounded-lg border border-border-strong px-4 text-sm font-medium text-fg hover:border-fg-subtle">Soru havuzunu aç</Link>
        </div>
        <div className="mt-5 overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="border-b border-border text-xs text-fg-muted"><tr><th className="py-2 pr-4 font-medium">Hücre</th><th className="py-2 pr-4 font-medium">Adet</th><th className="py-2 pr-4 font-medium">Puan</th><th className="py-2 font-medium">AI taslak</th></tr></thead>
            <tbody className="divide-y divide-border">
              {blueprint.cells.map((cell) => (
                <tr key={cell.id}>
                  <td className="py-3 pr-4 text-fg">{cell.label}</td>
                  <td className="py-3 pr-4 font-mono text-fg">{cell.question_count}</td>
                  <td className="py-3 pr-4 font-mono text-fg">{cell.points_per_question}</td>
                  <td className="py-3"><Button variant="secondary" aria-disabled={busyCell !== null} onClick={() => void generate(cell.id)}>{busyCell === cell.id ? "Üretiliyor…" : "Bu hücreyi üret"}</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {error && <div className="mt-4"><ErrorNote message={error} /></div>}
      </Card>
      <VersionPanel courseId={courseId} blueprint={blueprint} questions={questions} onChanged={onChanged} />
    </section>
  );
}

function VersionPanel({
  courseId,
  blueprint,
  questions,
  onChanged,
}: {
  courseId: string;
  blueprint: ExamBlueprint;
  questions: Question[];
  onChanged: (message: string) => Promise<void>;
}) {
  const [versions, setVersions] = useState<ExamVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [selectedQuestionIds, setSelectedQuestionIds] = useState<string[]>([]);
  const [readiness, setReadiness] = useState<BlueprintReadiness | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const eligible = useMemo(() => eligibleQuestions(questions, blueprint.cells), [questions, blueprint.cells]);
  const selectedVersion = versions.find((version) => version.id === selectedVersionId) ?? versions[0] ?? null;

  const loadVersions = useCallback(async (preferredVersionId?: string) => {
    setLoading(true);
    setError(null);
    try {
      const next = await api.get<ExamVersion[]>(`/courses/${courseId}/blueprints/${blueprint.id}/versions`);
      setVersions(next);
      const versionId =
        next.find((version) => version.id === preferredVersionId)?.id ?? next[0]?.id ?? null;
      setSelectedVersionId(versionId);
      if (versionId) {
        const items = await api.get<ExamItem[]>(`/courses/${courseId}/blueprints/${blueprint.id}/versions/${versionId}/items`);
        setSelectedQuestionIds(items.map((item) => item.question_id));
      } else {
        setSelectedQuestionIds([]);
      }
    } catch (cause) {
      setError(errorMessage(cause, "Sınav sürümleri yüklenemedi."));
    } finally {
      setLoading(false);
    }
  }, [blueprint.id, courseId]);

  useEffect(() => { void loadVersions(); }, [loadVersions]);

  async function createVersion() {
    setBusy("create");
    setError(null);
    try {
      const version = await api.post<ExamVersion>(`/courses/${courseId}/blueprints/${blueprint.id}/versions`);
      setSelectedVersionId(version.id);
      setSelectedQuestionIds([]);
      setReadiness(null);
      await loadVersions(version.id);
      await onChanged(`v${version.version_no} taslak sınav sürümü oluşturuldu.`);
    } catch (cause) {
      setError(errorMessage(cause, "Sınav sürümü oluşturulamadı."));
    } finally {
      setBusy(null);
    }
  }

  async function savePaper() {
    if (!selectedVersion || selectedVersion.status !== "draft") return;
    setBusy("paper");
    setError(null);
    try {
      await api.put<ExamItem[]>(`/courses/${courseId}/blueprints/${blueprint.id}/versions/${selectedVersion.id}/items`, selectedQuestionIds.map((question_id, index) => ({ question_id, position: index + 1 })));
      setReadiness(null);
      await loadVersions(selectedVersion.id);
      await onChanged(`v${selectedVersion.version_no} soru listesi kaydedildi.`);
    } catch (cause) {
      setError(errorMessage(cause, "Soru listesi kaydedilemedi."));
    } finally {
      setBusy(null);
    }
  }

  async function checkReadiness() {
    if (!selectedVersion) return;
    setBusy("check");
    setError(null);
    try {
      setReadiness(await api.get<BlueprintReadiness>(`/courses/${courseId}/blueprints/${blueprint.id}/versions/${selectedVersion.id}/readiness`));
    } catch (cause) {
      setError(errorMessage(cause, "Yayın kontrolü çalıştırılamadı."));
    } finally {
      setBusy(null);
    }
  }

  async function publish() {
    if (!selectedVersion) return;
    setBusy("publish");
    setError(null);
    try {
      await api.post(`/courses/${courseId}/blueprints/${blueprint.id}/versions/${selectedVersion.id}/publish`);
      await loadVersions(selectedVersion.id);
      await onChanged(`v${selectedVersion.version_no} yayınlandı. Öğrenciler yalnız açık yayın penceresinde başlayabilir.`);
    } catch (cause) {
      setError(errorMessage(cause, "Sınav sürümü yayınlanamadı."));
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <Card><Loading label="Sınav sürümleri yükleniyor…" /></Card>;

  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><h2 className="text-lg font-medium text-fg">4. Kâğıdı hazırla ve yayınla</h2><p className="prose-tr mt-1 text-sm text-fg-muted">Yalnız onaylı ve hücre sınıflandırması tam sorular seçilebilir. Yayınlanan sürüm değişmez.</p></div>
        <Button variant="secondary" aria-disabled={busy !== null} onClick={() => void createVersion()}>Yeni taslak sürüm</Button>
      </div>
      {versions.length === 0 ? (
        <EmptyState title="Henüz sınav sürümü yok. Yeni taslak sürüm oluşturarak başlayın." />
      ) : (
        <div className="mt-5 space-y-5">
          <Field label="Sürüm">
            {(control) => <select {...control} className={SELECT_CLASS} value={selectedVersion?.id ?? ""} onChange={async (event) => { const id = event.target.value; setSelectedVersionId(id); setReadiness(null); const items = await api.get<ExamItem[]>(`/courses/${courseId}/blueprints/${blueprint.id}/versions/${id}/items`); setSelectedQuestionIds(items.map((item) => item.question_id)); }}>{versions.map((version) => <option key={version.id} value={version.id}>v{version.version_no} · {version.status} · {version.item_count} soru</option>)}</select>}
          </Field>
          {selectedVersion?.status === "draft" ? (
            <div>
              <p className="mb-2 text-sm font-medium text-fg">Onaylı soru seçimi</p>
              {eligible.length === 0 ? <p className="text-sm text-fg-muted">Blueprint hücreleriyle eşleşen onaylı soru yok. Önce AI taslaklarını üretip soru havuzunda onaylayın.</p> : <ul className="max-h-80 divide-y divide-border overflow-y-auto rounded-lg border border-border">{eligible.map((question) => <li key={question.id}><label className="flex min-h-11 items-start gap-3 p-3 text-sm text-fg"><input type="checkbox" className="mt-1" checked={selectedQuestionIds.includes(question.id)} onChange={() => setSelectedQuestionIds((current) => current.includes(question.id) ? current.filter((id) => id !== question.id) : [...current, question.id])} /><span><span className="block">{questionStem(question)}</span><span className="mt-1 block text-xs text-fg-subtle">{question.difficulty ? DIFFICULTY_LABEL[question.difficulty] : "Zorluk yok"} · {QUESTION_TYPE_LABEL[question.type]}{question.source_stale ? " · Kaynak sürümü değişti" : ""}</span></span></label></li>)}</ul>}
              <div className="mt-4 flex flex-wrap gap-3"><Button aria-disabled={busy !== null} onClick={() => void savePaper()}>{busy === "paper" ? "Kaydediliyor…" : "Soru listesini kaydet"}</Button><Button variant="secondary" aria-disabled={busy !== null} onClick={() => void checkReadiness()}>{busy === "check" ? "Kontrol ediliyor…" : "Yayın kontrolü"}</Button></div>
            </div>
          ) : <p className="text-sm text-fg-muted">Bu sürüm {selectedVersion?.status === "published" ? "yayında" : "yerine yeni sürüm yayınlandığı için arşivde"}; soru listesi değiştirilemez.</p>}
          {readiness && <div className="rounded-lg border border-border bg-bg p-4"><div className="flex items-center gap-3"><Badge tone={readiness.ready ? "success" : "warning"}>{readiness.ready ? "Yayına hazır" : "Eksikler var"}</Badge><p className="text-sm text-fg">{readiness.message}</p></div>{readiness.missing_cells.length > 0 && <ul className="mt-3 space-y-1 text-sm text-fg-muted">{readiness.missing_cells.map((cell) => <li key={`${cell.learning_outcome_id}-${cell.difficulty}-${cell.question_type}`}>{cell.label}: {cell.filled}/{cell.required}</li>)}</ul>}{readiness.unclassified_items.length > 0 && <ul className="mt-3 space-y-1 text-sm text-fg-muted">{readiness.unclassified_items.map((item) => <li key={item.question_id}>{item.label}</li>)}</ul>}{readiness.ready && selectedVersion?.status === "draft" && <Button className="mt-4" aria-disabled={busy !== null} onClick={() => void publish()}>{busy === "publish" ? "Yayınlanıyor…" : "Sürümü yayınla"}</Button>}</div>}
        </div>
      )}
      {error && <div className="mt-4"><ErrorNote message={error} /></div>}
    </Card>
>>>>>>> codex/production-completion
  );
}
