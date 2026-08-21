/**
 * Sınav blueprint'inin saf çekirdeği: tipler, türetmeler ve yüzde→adet açılımı.
 *
 * Kendi modülünde yaşar. `lib/questions.ts` soru havuzunun payload daraltmasını
 * taşıyor, blueprint ise ayrı bir eksen; aynı dosyaya yığmak iki şeridin aynı
 * dosyaya dokunmasını da gerektirirdi.
 *
 * **Bu dosya hata METNİ üretmez.** Dağılım tutarsızsa cümleyi sunucu kurar
 * (Anayasa V: "backend tek hata zarfı üretir; frontend kendi hata metnini
 * uydurmaz"). Buradaki tek doğrulama, isteğin gönderilebilir ŞEKİLDE olup
 * olmadığıdır — "hangi hücre tutmuyor" sorusunun cevabı sunucudan gelir.
 *
 * Her fonksiyon DOM'suz koşar; `blueprint.test.ts` bunları doğrudan sınar.
 */

/* -------------------------------------------------------------------------
 * Tipler — backend `schemas/blueprint.py`'ın aynası
 * ---------------------------------------------------------------------- */

export type Difficulty = "easy" | "medium" | "hard";
export type BlueprintQuestionType = "mcq" | "open" | "code_trace" | "bug_hunt";
export type VersionStatus = "draft" | "published" | "superseded";

export interface LearningOutcome {
  id: string;
  code: string;
  description: string;
  topic_id: string | null;
  created_at: string;
}

export interface BlueprintCellInput {
  learning_outcome_id: string;
  difficulty: Difficulty;
  question_type: BlueprintQuestionType;
  question_count: number;
  points_per_question: number;
}

export interface BlueprintCell extends BlueprintCellInput {
  id: string;
  /** Türkçe hücre adı. Sunucudan gelir; ekran kendi etiketini kurmaz. */
  label: string;
}

export interface TopicShare {
  topic_id: string | null;
  topic_name: string | null;
  question_count: number;
}

export interface Blueprint {
  id: string;
  course_id: string;
  title: string;
  description: string | null;
  duration_minutes: number;
  max_attempts: number;
  opens_at: string | null;
  closes_at: string | null;
  created_at: string;
  updated_at: string;
  cells: BlueprintCell[];
  total_questions: number;
  total_points: number;
  topic_distribution: TopicShare[];
  published_version_no: number | null;
}

export interface ExamVersion {
  id: string;
  blueprint_id: string;
  version_no: number;
  status: VersionStatus;
  published_at: string | null;
  superseded_at: string | null;
  created_at: string;
  item_count: number;
  total_points: number;
}

export interface ExamItem {
  id: string;
  position: number;
  question_id: string;
  points: number;
  question_type: BlueprintQuestionType;
  difficulty: Difficulty | null;
  learning_outcome_id: string | null;
  stem: string;
}

export interface MissingCell {
  learning_outcome_id: string;
  difficulty: Difficulty;
  question_type: BlueprintQuestionType;
  required: number;
  filled: number;
  label: string;
}

export interface UnclassifiedItem {
  question_id: string;
  position: number;
  missing_fields: string[];
  label: string;
}

export interface Readiness {
  ready: boolean;
  missing_cells: MissingCell[];
  unclassified_items: UnclassifiedItem[];
  message: string;
}

/**
 * Havuz sorusunun blueprint için gereken iki ek alanı.
 *
 * `lib/types.ts`'teki `Question` genişletilmedi: o dosya bütün ekranların ortak
 * sözleşmesi ve bu turda başka bir şerit de ona dokunuyor. Blueprint'e özgü
 * alanlar burada, kendi modülünde yaşıyor (görev tanımının "blueprint frontend
 * tiplerini kendi modülünde tut" kuralı).
 */
export interface PoolQuestion {
  id: string;
  type: BlueprintQuestionType;
  payload: Record<string, unknown>;
  learning_outcome_id: string | null;
  difficulty: Difficulty | null;
}

/* -------------------------------------------------------------------------
 * Etiketler — ürün sözlüğü, tek yer
 *
 * Backend'in `DIFFICULTY_TR` / `QUESTION_TYPE_TR` sözlüğünün ekran karşılığı.
 * `labels.ts` bu şeridin dosyası değil ve reliability şeridi ona dokunuyor;
 * blueprint'e özgü etiketler burada durur.
 * ---------------------------------------------------------------------- */

export const DIFFICULTY_LABEL: Record<Difficulty, string> = {
  easy: "Kolay",
  medium: "Orta",
  hard: "Zor",
};

export const DIFFICULTIES: Difficulty[] = ["easy", "medium", "hard"];

export const VERSION_STATUS_LABEL: Record<VersionStatus, string> = {
  draft: "Taslak",
  published: "Yayında",
  superseded: "Yerine yenisi geldi",
};

/* -------------------------------------------------------------------------
 * Türetmeler
 * ---------------------------------------------------------------------- */

export function totalQuestions(cells: readonly BlueprintCellInput[]): number {
  return cells.reduce((sum, cell) => sum + cell.question_count, 0);
}

export function totalPoints(cells: readonly BlueprintCellInput[]): number {
  return cells.reduce((sum, cell) => sum + cell.question_count * cell.points_per_question, 0);
}

/** Aynı hücrenin iki kez tanımlandığını ekranda göstermek için (kayıt kapısı sunucuda). */
export function cellKey(cell: BlueprintCellInput): string {
  return `${cell.learning_outcome_id}|${cell.difficulty}|${cell.question_type}`;
}

export function hasDuplicateCells(cells: readonly BlueprintCellInput[]): boolean {
  return new Set(cells.map(cellKey)).size !== cells.length;
}

/**
 * Yüzdeyi ADETE çevirir ve toplamı TAM tutturur (en büyük artık yöntemi).
 *
 * Neden burada: "%40 kolay / %40 orta / %20 zor" 7 soruda 2,8 eder ve yuvarlama
 * kuralı saklanan veride görünmezse SC-003'ün "birebir uyar" iddiası karar
 * verilemez hâle gelir. Saklanan gerçek ADETTİR; yuvarlamayı ekran yapar, ama
 * yaptığını sunucu ayrıca doğrular (`targets`).
 *
 * Basit `Math.round` yetmez: %33/%33/%34 ile 10 soru 3+3+3=9 verir ve bir soru
 * buharlaşır. En büyük artık yöntemi toplamı her zaman `total` tutar.
 */
export function splitByShares(total: number, shares: readonly number[]): number[] {
  if (total <= 0 || shares.length === 0) return shares.map(() => 0);
  const sum = shares.reduce((acc, share) => acc + share, 0);
  if (sum <= 0) return shares.map(() => 0);

  const exact = shares.map((share) => (share / sum) * total);
  const floors = exact.map(Math.floor);
  let remaining = total - floors.reduce((acc, value) => acc + value, 0);

  const order = exact
    .map((value, index) => ({ index, remainder: value - Math.floor(value) }))
    .sort((a, b) => b.remainder - a.remainder || a.index - b.index);

  const counts = [...floors];
  for (const { index } of order) {
    if (remaining <= 0) break;
    counts[index] += 1;
    remaining -= 1;
  }
  return counts;
}

/**
 * Kapının iki listesini tek bir "ne yapmalıyım" listesine çevirir.
 *
 * İki listeyi ayrı tutmak KARARDIR (data-model.md §8 madde 7): sınıflandırılmamış
 * kalem, eksik hücre gibi okunursa öğretmen yanlış hücreye soru ekler. Ekranda da
 * ayrı başlıklar altında dururlar; bu fonksiyon yalnız sayıları verir.
 */
export function readinessCounts(readiness: Readiness | null): {
  missing: number;
  unclassified: number;
  blocked: boolean;
} {
  if (!readiness) return { missing: 0, unclassified: 0, blocked: false };
  return {
    missing: readiness.missing_cells.length,
    unclassified: readiness.unclassified_items.length,
    blocked: !readiness.ready,
  };
}

/**
 * Yayınlanmış sürümü olan bir blueprint'in hücreleri DÜZENLENEBİLİR.
 *
 * Yayınlanmış sürümün dağılım kanıtı kendi `blueprint_snapshot`'ında donmuştur;
 * düzenleme onu etkilemez. Ekran bunu söylemek zorunda, yoksa öğretmen kanıtı
 * bozduğunu sanır ve düzenlemekten çekinir.
 */
export function editingNoticeFor(blueprint: Blueprint): string | null {
  if (blueprint.published_version_no === null) return null;
  return (
    `${blueprint.published_version_no}. sürüm yayında. Dağılımı değiştirmek yayındaki ` +
    "sınavı etkilemez: o sürüm yayın anındaki dağılımı kendi içinde dondurdu. " +
    "Değişiklik ancak yeni bir sürüm yayınlarsan öğrenciye ulaşır."
  );
}
