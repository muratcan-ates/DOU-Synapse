export interface PolicyHistoryEntry {
  id: string;
  course_id: string;
  changed_by: string | null;
  changed_at: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
}

export const POLICY_HISTORY_PAGE_SIZE = 20;

const fields = {
  allowed_modes: "Asistan modları",
  max_hints: "İpucu sınırı",
  evidence_threshold: "Kanıt eşiği",
  daily_token_budget: "Günlük sohbet token bütçesi",
  source_document_ids: "İzin verilen kaynaklar",
  student_daily_token_budget: "Öğrenci günlük token sınırı",
  instructor_daily_token_budget: "Öğretim elemanı günlük token sınırı",
  max_output_tokens: "Yanıt başına token tavanı",
  max_concurrent_requests: "Eşzamanlı istek tavanı",
} as const;
type Field = keyof typeof fields;
export interface PolicyFieldChange { field: Field; label: string; before: string; after: string }

export function policyHistoryPath(courseId: string, offset: number): string {
  if (!Number.isSafeInteger(offset) || offset < 0) throw new Error("Geçersiz geçmiş konumu");
  return `/courses/${encodeURIComponent(courseId)}/ai-policy/history?limit=${POLICY_HISTORY_PAGE_SIZE + 1}&offset=${offset}`;
}

function comparable(value: unknown): string | undefined {
  // Kaynak/mod seçimlerinin sıra değiştirmesi davranış değişikliği değildir.
  return JSON.stringify(Array.isArray(value) ? [...value].sort() : value);
}

function valueLabel(snapshot: PolicyHistoryEntry["before"], key: Field, names: ReadonlyMap<string, string>): string {
  if (snapshot === null) return "Politika yok";
  if (!Object.hasOwn(snapshot, key)) return "Bu kayıtta yok";
  const value = snapshot[key];
  if (value === null) return key === "source_document_ids" ? "Tüm ders materyalleri" : "Varsayılan";
  if (key === "allowed_modes") {
    if (!Array.isArray(value) || !value.every((mode) => mode === "qa" || mode === "socratic")) return "Mod bilgisi okunamıyor";
    return value.length ? value.map((mode) => mode === "qa" ? "Soru ve cevap" : "Sokratik koç").join(", ") : "Asistan modları kapalı";
  }
  if (key === "source_document_ids") {
    if (!Array.isArray(value) || !value.every((id) => typeof id === "string")) return "Kaynak bilgisi okunamıyor";
    if (!value.length) return "Hiçbir kaynak seçilmedi";
    const known = value.flatMap((id) => names.has(id) ? [names.get(id)!] : []);
    const missing = value.length - known.length;
    return `${value.length} kaynak${known.length ? `: ${known.join(", ")}` : ""}${missing ? ` (${missing} kaynak adı bu listede yok)` : ""}`;
  }
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("tr-TR", { maximumFractionDigits: 6 }) : "Değer okunamıyor";
}

export function policyFieldChanges(entry: Pick<PolicyHistoryEntry, "before" | "after">, names: ReadonlyMap<string, string> = new Map()): PolicyFieldChange[] {
  return (Object.keys(fields) as Field[]).flatMap((field) => {
    const beforePresent = entry.before !== null && Object.hasOwn(entry.before, field);
    const afterPresent = entry.after !== null && Object.hasOwn(entry.after, field);
    if (!beforePresent && !afterPresent) return [];
    if (beforePresent === afterPresent && comparable(entry.before?.[field]) === comparable(entry.after?.[field])) return [];
    return [{ field, label: fields[field], before: valueLabel(entry.before, field, names), after: valueLabel(entry.after, field, names) }];
  });
}

export function policyHistoryTitle(entry: Pick<PolicyHistoryEntry, "before" | "after">): string {
  if (entry.before === null && entry.after !== null) return "Politika oluşturuldu";
  if (entry.after === null && entry.before !== null) return "Politika kaldırıldı";
  return "Politika kaydedildi";
}

export function policyHistoryActor(actor: string | null, viewerId: string | null): string {
  if (!actor) return "Hesap bilgisi yok";
  return actor === viewerId ? "Siz" : "Başka bir hesap";
}

export function policyHistoryDate(value: string): string {
  const date = new Date(value);
  return Number.isFinite(date.valueOf()) ? date.toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short" }) : "Tarih bilgisi yok";
}
