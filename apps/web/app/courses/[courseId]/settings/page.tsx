"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/app-shell";
import { CourseNav } from "@/components/course-nav";
import { InstructorGate } from "@/components/instructor-gate";
import { ErrorNote, Loading, PageHeader } from "@/components/page-state";
import { Button, Card, EmptyState, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import {
  courseHardCapLabel,
  draftFromPolicy,
  payloadFromDraft,
  toggleMode,
  type CourseAiPolicy,
  type PolicyDraft,
} from "@/lib/policy";
import { useSession } from "@/lib/session";
import type { ChatMode, CourseDocument, Page } from "@/lib/types";

export default function AiPolicyPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const { isInstructor, ready } = useSession(courseId);

  return (
    <AppShell>
      <CourseNav courseId={courseId} />
      <PageHeader
        title="Ders AI politikası"
        description="Asistanın modlarını, kaynak sınırını, kanıt eşiğini, ipucu tavanını ve günlük sohbet bütçesini sunucu tarafında yönetin."
      />
      <InstructorGate
        ready={ready}
        isInstructor={isInstructor}
        fallback={<EmptyState title="AI politikası yalnızca dersin eğitmenine gösterilir." />}
      >
        <PolicyEditor courseId={courseId} />
      </InstructorGate>
    </AppShell>
  );
}

function PolicyEditor({ courseId }: { courseId: string }) {
  const [policy, setPolicy] = useState<CourseAiPolicy | null>(null);
  const [draft, setDraft] = useState<PolicyDraft | null>(null);
  const [documents, setDocuments] = useState<CourseDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [nextPolicy, nextDocuments] = await Promise.all([
        api.get<CourseAiPolicy>(`/courses/${courseId}/ai-policy`),
        api
          .get<Page<CourseDocument>>(`/courses/${courseId}/documents?limit=100`)
          .then((page) => page.items),
      ]);
      setPolicy(nextPolicy);
      setDraft(draftFromPolicy(nextPolicy));
      setDocuments(nextDocuments);
    } catch (cause) {
      setError(errorMessage(cause, "AI politikası yüklenemedi."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [courseId]);

  async function save() {
    if (!draft || saving) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await api.put<CourseAiPolicy>(
        `/courses/${courseId}/ai-policy`,
        payloadFromDraft(draft),
      );
      setPolicy(saved);
      setDraft(draftFromPolicy(saved));
      setNotice("AI politikası kaydedildi ve ilk yeni istekten itibaren uygulanacak.");
    } catch (cause) {
      setError(errorMessage(cause, "AI politikası kaydedilemedi."));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <Loading label="AI politikası yükleniyor…" />;
  if (error && (!policy || !draft)) return <ErrorNote message={error} onRetry={() => void load()} />;
  if (!policy || !draft) return null;

  return (
    <div className="space-y-5">
      {(error || notice) && (
        <div aria-live="polite">
          {error && <ErrorNote message={error} />}
          {notice && <p role="status" className="text-sm text-success">{notice}</p>}
        </div>
      )}

      <Card>
        <SectionTitle title="Asistan modları" description="Kapalı mod API tarafından da reddedilir; yalnız sekmeyi gizlemekle yetinilmez." />
        <DefaultToggle
          checked={draft.inheritModes}
          label="Global varsayılanı kullan"
          onChange={(checked) => setDraft({ ...draft, inheritModes: checked })}
        />
        {!draft.inheritModes && (
          <div className="mt-4 flex flex-wrap gap-5">
            <ModeCheckbox label="Soru ve cevap" mode="qa" draft={draft} setDraft={setDraft} />
            <ModeCheckbox label="Sokratik koç" mode="socratic" draft={draft} setDraft={setDraft} />
          </div>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <SectionTitle title="İpucu sınırı" description="Açılış sorusundan sonra verilebilecek en fazla ipucu sayısıdır." />
          <DefaultToggle checked={draft.inheritHints} label="Global üst sınırı kullan" onChange={(checked) => setDraft({ ...draft, inheritHints: checked })} />
          {!draft.inheritHints && (
            <div className="mt-4">
              <Input aria-label="İpucu sınırı" type="number" min={0} max={10} value={draft.hintLimit} onChange={(event) => setDraft({ ...draft, hintLimit: Number(event.target.value) })} />
            </div>
          )}
        </Card>
        <Card>
          <SectionTitle title="Kanıt eşiği" description="En iyi dense skor bu değerin altındaysa model çağrılmadan kaynak yetersizliği döner." />
          <DefaultToggle checked={draft.inheritEvidence} label="Global eşiği kullan" onChange={(checked) => setDraft({ ...draft, inheritEvidence: checked })} />
          {!draft.inheritEvidence && (
            <div className="mt-4">
              <Input aria-label="Kanıt eşiği" type="number" min={0} max={1} step={0.01} value={draft.evidenceThreshold} onChange={(event) => setDraft({ ...draft, evidenceThreshold: Number(event.target.value) })} />
            </div>
          )}
        </Card>
      </div>

      <Card>
        <SectionTitle title="Günlük sohbet token bütçesi" description={`Bugün ${policy.budget_used_today.toLocaleString("tr-TR")} token kullanıldı. Boş politika sınırsız değildir; platformun etkin ders üst sınırı uygulanır. Bu v1 bütçesi yalnız sohbet yanıtlarını kapsar.`} />
        <DefaultToggle checked={draft.useCourseHardCap} label={courseHardCapLabel(policy.daily_llm_budget, policy.effective.daily_llm_budget)} onChange={(checked) => setDraft({ ...draft, useCourseHardCap: checked })} />
        {!draft.useCourseHardCap && (
          <div className="mt-4 max-w-xs">
            <Input aria-label="Günlük token bütçesi" type="number" min={1} value={draft.dailyBudget} onChange={(event) => setDraft({ ...draft, dailyBudget: Number(event.target.value) })} />
          </div>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <SectionTitle title="Öğrenci günlük token sınırı" description={`Öğrenci başına sohbet tüketimini sınırlar. Sunucuda uygulanan etkin tavan: ${policy.effective.student_daily_token_budget.toLocaleString("tr-TR")} token/gün.`} />
          <Input aria-label="Öğrenci günlük token sınırı" type="number" min={256} max={1_000_000} value={draft.studentDailyTokenBudget} onChange={(event) => setDraft({ ...draft, studentDailyTokenBudget: Number(event.target.value) })} />
        </Card>
        <Card>
          <SectionTitle title="Öğretim elemanı günlük token sınırı" description={`Öğretim elemanı başına sohbet tüketimini sınırlar. Sunucuda uygulanan etkin tavan: ${policy.effective.instructor_daily_token_budget.toLocaleString("tr-TR")} token/gün.`} />
          <Input aria-label="Öğretim elemanı günlük token sınırı" type="number" min={256} max={1_000_000} value={draft.instructorDailyTokenBudget} onChange={(event) => setDraft({ ...draft, instructorDailyTokenBudget: Number(event.target.value) })} />
        </Card>
        <Card>
          <SectionTitle title="Yanıt başına token tavanı" description={`Her model yanıtının üst sınırıdır. Sunucuda uygulanan etkin tavan: ${policy.effective.max_output_tokens.toLocaleString("tr-TR")} token.`} />
          <Input aria-label="Yanıt başına token tavanı" type="number" min={64} max={4096} value={draft.maxOutputTokens} onChange={(event) => setDraft({ ...draft, maxOutputTokens: Number(event.target.value) })} />
        </Card>
        <Card>
          <SectionTitle title="Eşzamanlı istek tavanı" description={`Aynı kullanıcı için aynı anda çalışabilecek en fazla sohbet isteğidir. Sunucuda uygulanan değer: ${policy.effective.max_concurrent_requests}.`} />
          <Input aria-label="Eşzamanlı istek tavanı" type="number" min={1} max={4} value={draft.maxConcurrentRequests} onChange={(event) => setDraft({ ...draft, maxConcurrentRequests: Number(event.target.value) })} />
        </Card>
      </div>

      <Card>
        <SectionTitle title="İzin verilen kaynaklar" description="Seçilmeyen belgeler öğrencinin yanıt retrieval hattına hiç girmez. Boş seçim bütün kaynakları bilerek kapatır." />
        <DefaultToggle checked={draft.allSources} label="Tüm ders materyallerini kullan" onChange={(checked) => setDraft({ ...draft, allSources: checked })} />
        {!draft.allSources && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {documents.map((document) => (
              <label key={document.id} className="flex min-h-11 items-center gap-3 rounded-lg border border-border px-3 text-sm text-fg">
                <input type="checkbox" checked={draft.sourceDocumentIds.includes(document.id)} onChange={() => setDraft({ ...draft, sourceDocumentIds: draft.sourceDocumentIds.includes(document.id) ? draft.sourceDocumentIds.filter((id) => id !== document.id) : [...draft.sourceDocumentIds, document.id] })} />
                <span>{document.file_name}</span>
              </label>
            ))}
            {documents.length === 0 && <p className="text-sm text-fg-muted">Bu derste henüz materyal yok.</p>}
          </div>
        )}
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border pt-5">
        <p className="text-xs text-fg-muted">Son güncelleme: {policy.updated_at ? new Date(policy.updated_at).toLocaleString("tr-TR") : "Henüz özelleştirilmedi"}</p>
        <Button aria-disabled={saving} onClick={() => void save()}>{saving ? "Kaydediliyor…" : "Politikayı kaydet"}</Button>
      </div>
    </div>
  );
}

function SectionTitle({ title, description }: { title: string; description: string }) {
  return <div className="mb-4"><h2 className="text-lg font-medium text-fg">{title}</h2><p className="prose-tr mt-1 text-sm text-fg-muted">{description}</p></div>;
}

function DefaultToggle({ checked, label, onChange }: { checked: boolean; label: string; onChange: (checked: boolean) => void }) {
  return <label className="flex min-h-11 items-center gap-3 text-sm text-fg"><input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span>{label}</span></label>;
}

function ModeCheckbox({ label, mode, draft, setDraft }: { label: string; mode: ChatMode; draft: PolicyDraft; setDraft: (draft: PolicyDraft) => void }) {
  return <label className="flex min-h-11 items-center gap-3 text-sm text-fg"><input type="checkbox" checked={draft.allowedModes.includes(mode)} onChange={() => setDraft({ ...draft, allowedModes: toggleMode(draft.allowedModes, mode) })} /><span>{label}</span></label>;
}
