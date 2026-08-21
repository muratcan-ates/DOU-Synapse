"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { Field } from "@/components/field";
import { ErrorNote, Loading, MetricRow, PageHeader } from "@/components/page-state";
import { Badge, Button, Card, EmptyState, Input } from "@/components/ui";
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
  const { isInstructor, ready } = useSession();

  return (
    <AppShell>
      <CourseNav courseId={courseId} />
      <PageHeader
        title="Sınav planı"
        description="Önce öğrenme çıktıları ve dağılımı kurun; sonra AI taslakları üretin, onaylı sorulardan sürüm hazırlayıp yayınlayın."
      />
      {!ready ? (
        <Loading />
      ) : isInstructor ? (
        <BlueprintWorkspace courseId={courseId} />
      ) : (
        <EmptyState title="Sınav planı yalnızca dersin eğitmenine gösterilir." />
      )}
    </AppShell>
  );
}

function BlueprintWorkspace({ courseId }: { courseId: string }) {
  const fetchData = useCallback(async (): Promise<BlueprintWorkspaceData> => {
    const [outcomes, blueprints, topics, questions] = await Promise.all([
      api.get<LearningOutcome[]>(`/courses/${courseId}/learning-outcomes`),
      api.get<ExamBlueprint[]>(`/courses/${courseId}/blueprints`),
      api.get<Topic[]>(`/courses/${courseId}/topics`),
      api.get<Question[]>(`/courses/${courseId}/questions`),
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
    </Card>
  );
}

function BlueprintCreatePanel({
  courseId,
  outcomes,
  onCreated,
}: {
  courseId: string;
  outcomes: LearningOutcome[];
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

function BlueprintDetail({
  courseId,
  blueprint,
  outcomes,
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
  );
}
