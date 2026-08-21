/**
 * Soru havuzunun saf çekirdeği: `payload` daraltması, üretim muhasebesi, süzme.
 *
 * Neden ayrı dosya: `questions.payload` backend'de `jsonb`'dir ve şekli soru
 * tipine göre değişir (`app/schemas/assessment.py`). Bu daraltmayı ekranın
 * içinde yapmak iki kusur üretirdi: JSX'in ortasında tip kontrolü okunmaz olur
 * ve daraltma yalnız tarayıcıda, yalnız doğru veriyle sınanabilir hâle gelirdi.
 * Buradaki her fonksiyon DOM'suz koşar ve `questions.test.ts` bunları doğrudan
 * sınar.
 *
 * Dosyanın tek kuralı: **eksik alan uydurulmaz.** Payload beklenen alanı
 * taşımıyorsa sonuç `null` ya da boş dizidir; ekran o boşluğu "gösterilemiyor"
 * diye söyler. Ölçmeden iddia etmemenin (Anayasa III) veri katmanındaki
 * karşılığı budur: arayüz sunucunun vermediği bir metni ekrana yazamaz.
 */

import type { SourceInfo } from "@/components/source-card";
import { toSourceInfo } from "@/lib/source";
import type {
  AnswerFormat,
  Question,
  QuestionGeneration,
  QuestionGenerateRequest,
  QuestionStatus,
  QuestionType,
} from "@/lib/types";

/* -------------------------------------------------------------------------
 * Ham jsonb okuyucuları
 *
 * `payload` `Record<string, unknown>`; her okuma tip kontrolünden geçer.
 * Tek satırlık yardımcılar, çünkü aynı kontrolü her alanda elle yazmak
 * er geç birinde unutulur ve `undefined.length` ekranı düşürür.
 * ---------------------------------------------------------------------- */

function readString(payload: Record<string, unknown>, key: string): string | null {
  const value = payload[key];
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function readStringList(payload: Record<string, unknown>, key: string): string[] {
  const value = payload[key];
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/* -------------------------------------------------------------------------
 * Görüntü tipleri
 * ---------------------------------------------------------------------- */

export interface OptionView {
  key: string;
  text: string;
  /** `answer_key` ile eşleşen şık. Renk tek başına bilgi taşımaz; etiket de var. */
  correct: boolean;
}

export interface RubricItemView {
  point: string;
  weight: number;
}

export interface CodeView {
  language: string | null;
  code: string;
}

/** `bug_hunt` cevap anahtarı: üç alanı da payload'dan gelir, biçimlenmez. */
export interface BugAnswerView {
  line: number | null;
  bugType: string | null;
  fixSummary: string | null;
}

/**
 * Tek sorunun ekrana hazır hâli.
 *
 * Bileşen `question.type`'a bakıp payload eşelemez: hangi alanın hangi tipte
 * dolduğu burada bir kez karara bağlanır. Doldurulamayan her alan `null`
 * ya da boş dizidir.
 */
export interface QuestionView {
  id: string;
  type: QuestionType;
  status: QuestionStatus;
  topicId: string;
  /** `mcq` için `stem`, diğer üç tip için `prompt`. */
  stem: string | null;
  options: OptionView[];
  /** Düz metin cevap anahtarı (`mcq` hariç; `mcq`'da doğru şık işaretlidir). */
  answerKey: string | null;
  /** `mcq`: doğru şıkkın anahtarı ("B"). Şık listesinde işaretlemek için. */
  correctOptionKey: string | null;
  bugAnswer: BugAnswerView | null;
  code: CodeView | null;
  explanation: string | null;
  keyPoints: string[];
  rubric: RubricItemView[];
  acceptedAnswers: string[];
  answerFormat: AnswerFormat | null;
  source: SourceInfo | null;
}

/** `mcq` şıkları: `{key, text}` nesneleri; bozuk öğeler sessizce düşer. */
function readOptions(
  payload: Record<string, unknown>,
  correctKey: string | null,
): OptionView[] {
  const raw = payload.options;
  if (!Array.isArray(raw)) return [];
  const options: OptionView[] = [];
  for (const item of raw) {
    if (!isRecord(item)) continue;
    const key = readString(item, "key");
    const text = readString(item, "text");
    if (key === null || text === null) continue;
    options.push({ key, text, correct: correctKey !== null && key === correctKey });
  }
  return options;
}

function readRubric(payload: Record<string, unknown>): RubricItemView[] {
  const raw = payload.rubric;
  if (!Array.isArray(raw)) return [];
  const items: RubricItemView[] = [];
  for (const item of raw) {
    if (!isRecord(item)) continue;
    const point = readString(item, "point");
    const weight = item.weight;
    if (point === null || typeof weight !== "number") continue;
    items.push({ point, weight });
  }
  return items;
}

function readCode(payload: Record<string, unknown>): CodeView | null {
  const code = readString(payload, "code");
  if (code === null) return null;
  return { language: readString(payload, "language"), code };
}

function readBugAnswer(payload: Record<string, unknown>): BugAnswerView | null {
  const raw = payload.answer_key;
  if (!isRecord(raw)) return null;
  const line = raw.line;
  return {
    line: typeof line === "number" ? line : null,
    bugType: readString(raw, "bug_type"),
    fixSummary: readString(raw, "fix_summary"),
  };
}

function readAnswerFormat(payload: Record<string, unknown>): AnswerFormat | null {
  const value = payload.format;
  return value === "essay" || value === "short_answer" ? value : null;
}

/** Ham `Question` → ekrana hazır görünüm. Tip bazlı daraltmanın tek yeri. */
export function toQuestionView(question: Question): QuestionView {
  const payload = question.payload ?? {};
  const base = {
    id: question.id,
    type: question.type,
    status: question.status,
    topicId: question.topic_id,
    options: [] as OptionView[],
    answerKey: null as string | null,
    correctOptionKey: null as string | null,
    bugAnswer: null as BugAnswerView | null,
    code: null as CodeView | null,
    explanation: readString(payload, "explanation"),
    keyPoints: [] as string[],
    rubric: [] as RubricItemView[],
    acceptedAnswers: [] as string[],
    answerFormat: null as AnswerFormat | null,
    // Kaynaksız soru kart çizdirmez; null koruması eşlemenin değil bu çağrının
    // işi (bkz. `lib/source.ts`).
    source: question.source ? toSourceInfo(question.source) : null,
  };

  switch (question.type) {
    case "mcq": {
      const correctOptionKey = readString(payload, "answer_key");
      return {
        ...base,
        stem: readString(payload, "stem"),
        options: readOptions(payload, correctOptionKey),
        correctOptionKey,
      };
    }
    case "open":
      return {
        ...base,
        stem: readString(payload, "prompt"),
        answerKey: readString(payload, "answer_key"),
        keyPoints: readStringList(payload, "key_points"),
        rubric: readRubric(payload),
        acceptedAnswers: readStringList(payload, "accepted_answers"),
        answerFormat: readAnswerFormat(payload),
      };
    case "code_trace":
      return {
        ...base,
        stem: readString(payload, "prompt"),
        answerKey: readString(payload, "answer_key"),
        code: readCode(payload),
      };
    case "bug_hunt":
      return {
        ...base,
        stem: readString(payload, "prompt"),
        bugAnswer: readBugAnswer(payload),
        code: readCode(payload),
      };
  }
}

/* -------------------------------------------------------------------------
 * Havuz sayımı ve süzme
 * ---------------------------------------------------------------------- */

export interface PoolCounts {
  draft: number;
  approved: number;
  rejected: number;
  total: number;
}

/**
 * Havuz sayımı. Dört sayı da listeden SAYILIR; sunucu ayrı bir toplam
 * vermiyor ve arayüz vermediği sayıyı uydurmaz (Anayasa III).
 */
export function countByStatus(questions: readonly Question[]): PoolCounts {
  const counts: PoolCounts = { draft: 0, approved: 0, rejected: 0, total: questions.length };
  for (const question of questions) counts[question.status] += 1;
  return counts;
}

export type StatusFilter = QuestionStatus | "all";

/**
 * Süzme istemcide yapılır çünkü liste zaten tam çekildi: her sekme değişiminde
 * aynı veriyi ikinci kez istemek gereksiz iştir (Anayasa XI). Sunucudaki
 * `?status=` süzgeci duruyor ve öğrenci için hâlâ zorunlu; burada onu
 * kullanmamak yetkiyi gevşetmez, yalnız istek sayısını düşürür.
 */
export function filterQuestions(
  questions: readonly Question[],
  status: StatusFilter,
  topicId: string | "all",
): Question[] {
  return questions.filter(
    (question) =>
      (status === "all" || question.status === status) &&
      (topicId === "all" || question.topic_id === topicId),
  );
}

/**
 * Karardan sonraki taslak. Eğitmen otuz soruyu elden geçirirken listeye dönmek
 * zorunda kalmasın diye var, ama geçiş KENDİLİĞİNDEN yapılmaz: panel sessizce
 * başka soruya kayarsa ekranı görmeyen kullanıcı neyi onayladığını kaybeder
 * (bulgu 14). Bu yüzden fonksiyon yalnız "sıradaki taslak var mı" sorusunu
 * cevaplar; geçişi kullanıcı tetikler.
 */
export function nextDraftId(
  questions: readonly Question[],
  currentId: string,
): string | null {
  const index = questions.findIndex((question) => question.id === currentId);
  const ordered =
    index === -1
      ? questions
      : [...questions.slice(index + 1), ...questions.slice(0, index)];
  return ordered.find((question) => question.status === "draft")?.id ?? null;
}

/* -------------------------------------------------------------------------
 * Üretim muhasebesi
 * ---------------------------------------------------------------------- */

/** Bir eleme gerekçesi ve kaç kez geldiği. `text` sunucudan BİREBİR gelir. */
export interface ReasonCount {
  text: string;
  count: number;
}

/**
 * Eleme gerekçelerini tekrarına göre toplar; ilk görülme sırası korunur.
 *
 * Neden toplanıyor: sunucu gerekçeyi DENEME başına yazıyor, yani iki deneme de
 * aynı duvara toslarsa dizide birebir aynı cümle iki kez durur (canlı örnek:
 * `["yanıtta 'questions' dizisi yok", "yanıtta 'questions' dizisi yok"]`).
 * Aynı satırı iki kez alt alta çizmek arayüz hatası gibi okunur; tekrarı
 * silmek ise bilgi kaybıdır — "bir kez denendi" ile "iki kez denendi, ikisi de
 * aynı yerde düştü" farklı olaylardır. Sayı ekranda ayrıca yazılır, yani
 * tekrar YUTULMAZ, yalnız okunur hâle gelir.
 *
 * Boş/boşluktan ibaret gerekçe düşer: bu dosyanın "boş metin dolu sayılmaz"
 * kuralı (bkz. `readString`) burada da geçerli, boş bir madde işareti
 * kullanıcıya hiçbir şey söylemez.
 */
export function groupReasons(reasons: readonly string[]): ReasonCount[] {
  const order: string[] = [];
  const counts = new Map<string, number>();
  for (const raw of reasons) {
    const text = raw.trim();
    if (text === "") continue;
    const seen = counts.get(text);
    if (seen === undefined) {
      order.push(text);
      counts.set(text, 1);
    } else {
      counts.set(text, seen + 1);
    }
  }
  return order.map((text) => ({ text, count: counts.get(text) ?? 1 }));
}

export interface GenerationSummary {
  /** Okunur özet cümlesi: istenen / dönen / kabul / elenen. */
  sentence: string;
  /** Sunucunun eleme gerekçeleri; metin birebir, tekrar sayıya indirilmiş. */
  reasons: ReasonCount[];
  /** Havuza gerçekten eklenen soru sayısı. Sıfırsa ekran nötr bir not yazar. */
  accepted: number;
}

/**
 * Üretim turunun dürüst özeti.
 *
 * Dört sayı da gizlenmez (Anayasa III): "5 istendi" deyip 3 soru göstermek,
 * ikisinin neden düştüğünü kullanıcıdan saklamak olurdu. Cümle sayı ekiyle
 * oynamaz — "3 soru üretildi" her sayı için doğru okunur, "3'ü" ise değildir.
 *
 * `rejected` sıfırken de gerekçe gelebilir: sunucu soru düzeyindeki redleri
 * (`returned - accepted`) ile yanıt düzeyindeki hataları ("yanıtta 'questions'
 * dizisi yok", "konuyla eşleşen ders materyali bulunamadı") ayrı sayıyor ve
 * ikincisi hiç soru dönmediğinde de yazılıyor. Canlı doğrulandı (9 Ağustos
 * 2026, materyalsiz ders): `returned 0, rejected 0, rejection_reasons` tek
 * maddeli. Gerekçe listesi bu yüzden `rejected`'a DEĞİL kendi uzunluğuna
 * bağlanır; `rejected > 0` koşulu bu turu ekranda tümüyle sessizleştirirdi.
 */
export function generationSummary(report: QuestionGeneration): GenerationSummary {
  const parts = [
    `${report.requested} soru istendi`,
    `${report.returned} soru üretildi`,
  ];
  if (report.returned > 0) {
    parts.push(`${report.accepted} tanesi havuza taslak olarak eklendi`);
    if (report.rejected > 0) {
      parts.push(`${report.rejected} tanesi kaynak doğrulamasından geçemedi`);
    }
  }
  return {
    sentence: `${parts.join(", ")}.`,
    reasons: groupReasons(report.rejection_reasons ?? []),
    accepted: report.accepted,
  };
}

/* -------------------------------------------------------------------------
 * Üretim isteği
 * ---------------------------------------------------------------------- */

/** Eğitmenin kurduğu çerçeve (form durumu). */
export interface GenerateForm {
  topicId: string;
  questionType: QuestionType;
  answerFormat: AnswerFormat;
  count: number;
  /** Serbest metin: her satır bir örnek soru. */
  examplesText: string;
}

/**
 * Örnek soruları satırlara ayırır: boş satırlar düşer, en fazla beş tane kalır.
 * Sınır sözleşmeden gelir (`example_questions` maxItems 5); altıncı satırı
 * göndermek 422 ile geri döner ve kullanıcı neden reddedildiğini anlamaz.
 */
export function parseExampleQuestions(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "")
    .slice(0, 5);
}

/**
 * Form → istek gövdesi.
 *
 * `answer_format` yalnız `open` tipinde gönderilir: sunucu diğer tiplerde
 * bunu 422 ile reddediyor ("answer_format yalnızca 'open' tipi sorular için
 * verilebilir", canlı doğrulandı). Kural burada, tek yerde tutuluyor ki form
 * tipi değiştiğinde alanın temizlenmesi unutulmasın.
 */
export function buildGenerateRequest(form: GenerateForm): QuestionGenerateRequest {
  const request: QuestionGenerateRequest = {
    topic_id: form.topicId,
    question_type: form.questionType,
    count: form.count,
  };
  if (form.questionType === "open") request.answer_format = form.answerFormat;
  const examples = parseExampleQuestions(form.examplesText);
  if (examples.length > 0) request.example_questions = examples;
  return request;
}

/* -------------------------------------------------------------------------
 * Etiketler
 * ---------------------------------------------------------------------- */

/**
 * `open` tipinin cevap biçimi. Etiket sözlüğünün doğru evi `lib/labels.ts`;
 * o dosya bu görevde başka bir sahiplikte olduğu için sözlük şimdilik burada
 * duruyor (raporda taşınması isteniyor).
 */
export const ANSWER_FORMAT: Record<AnswerFormat, string> = {
  essay: "Klasik",
  short_answer: "Kısa cevap",
};

/** Üretimde sunulan adetler. Serbest metin yok: geçersiz sayı hiç oluşmaz. */
export const GENERATE_COUNTS = [1, 3, 5, 10, 20] as const;
