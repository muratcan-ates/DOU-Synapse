/**
 * Sınav ekranının saf mantığı — DOM'suz, sınanabilir.
 *
 * Ekranda kalan tek şey durum ve yerleşim olsun diye üç iş buraya alındı:
 *
 * 1. **`payload` daraltma.** Sunucu soruyu `jsonb` olarak taşır ve şekli tipine
 *    göre değişir (`app/schemas/assessment.py` → `_PUBLIC_PAYLOAD_KEYS`).
 *    Daraltma ekranın içinde yapılsaydı bozuk bir payload ya da ileride eklenen
 *    bir soru tipi bütün sınavı çökertirdi. Burada tanınmayan her şey
 *    `unsupported`'a düşer: soru atlanır, sınav ayakta kalır (Anayasa IV).
 *
 * 2. **Süre.** Kalan süre SUNUCUNUN kararıdır (`remaining_seconds`, `expired`);
 *    istemci sayacı yalnız görsel yumuşatmadır ve her sunucu turunda yeniden
 *    senkronlanır. Sayaç ekran okuyucuyu boğmasın diye duyuru yalnız eşiklerde
 *    değişir.
 *
 * 3. **Geri bildirim okuma.** `graded: false` "yanlış" DEĞİLDİR; puan yoktur ve
 *    arayüz puan UYDURMAZ (Anayasa III). `exam` modunda sunucu puanı bilerek
 *    gizler: `graded: true` gelip `is_correct`/`score` null kalabilir — bu da
 *    "yanlış" değildir, "şimdilik gösterilmiyor"dur. Üç durum ayrı ayrı
 *    adlandırılmazsa ekran er geç ikisini birbirine karıştırır.
 *
 * Gözlenmiş gövdeler (9 Ağustos 2026, :8010, ders c3b76077):
 *   practice başlangıç → expires_at: null, remaining_seconds: null
 *   exam başlangıç     → remaining_seconds: 1200, expired: false
 *   mcq yanlış         → graded: true, is_correct: false, score: 0, why_wrong: {...}
 *   essay (LLM yok)    → graded: false, is_correct: null, score: null, message: "..."
 *   exam modunda mcq   → graded: true, is_correct: null, score: null, solution: null
 */

import { ApiError } from "@/lib/api";
import type { SourceInfo } from "@/components/source-card";
import type { Tone } from "@/lib/labels";
import type {
  AnswerFeedback,
  ExamMode,
  ExamQuestion,
  ExamSession,
  SourceRef,
} from "@/lib/types";

/* -------------------------------------------------------------------------
 * Sabitler ve sözlükler
 * ---------------------------------------------------------------------- */

/** `AnswerSubmitRequest.given` sunucuda 1-8000 karakter (openapi.json). */
export const ANSWER_MAX_LENGTH = 8000;

/** İpucu merdiveninin son kademesi (`HintRequest.hint_level` ≤ 4). */
export const HINT_MAX_LEVEL = 4;

/**
 * Mod açıklamaları. Süre burada SAYIYLA yazılmaz: süreyi sunucu belirler
 * (`EXAM_DURATION_MINUTES`) ve oturum açılmadan istemcinin elinde o sayı yoktur.
 * "20 dakika" yazmak ölçülmemiş bir iddia olurdu (Anayasa III).
 */
export const EXAM_MODE: Record<ExamMode, { label: string; description: string }> = {
  practice: {
    label: "Alıştırma",
    description: "Süre yok. İpucu alabilirsiniz ve her cevaptan sonra geri bildirim gelir.",
  },
  exam: {
    label: "Sınav",
    description: "Süreli. İpucu kapalıdır; geri bildirim sınav bitiminde verilir.",
  },
};

/* -------------------------------------------------------------------------
 * Oturumun saklanması
 * ---------------------------------------------------------------------- */

/**
 * Açık oturumun kimliği tarayıcıda saklanır.
 *
 * Gerekli, çünkü öğrencinin oturumlarını listeleyen bir uç YOK: sayfa
 * yenilendiğinde kimlik kaybolursa öğrenci başlamış sınavına dönemez ve
 * cevapladığı sorular ona kapalı kalır (soru başına tek deneme; ikincisi 409).
 * Sunucu da bu dönüşü bekliyor: `GET /exams/{id}` docstring'i "bağlantı koparsa
 * öğrenci buraya döner ve kaldığı yerden devam eder" diyor.
 *
 * Anahtar ders başına ayrıdır; iki dersin sınavı birbirini ezmez.
 */
export function examSessionKey(courseId: string): string {
  return `dou-synapse-exam-session:${courseId}`;
}

/* -------------------------------------------------------------------------
 * Süre
 * ---------------------------------------------------------------------- */

/**
 * Süre duyuruları — eşikler ARTAN sırada; ilk eşleşen kazanır.
 *
 * Sayaç saniyede bir değişir ama duyurusu değişmez: iki eşik arasında metin aynı
 * kaldığı için canlı bölge yeniden okunmaz. Ekran okuyucu kullanan öğrenci 20
 * dakikalık sınavda 1200 duyuru yerine dört duyuru duyar — saniyede bir konuşan
 * bir sayaç sınavı yapılamaz kılar.
 */
export const TIME_NOTICES = [
  { at: 0, text: "Süre doldu." },
  { at: 30, text: "30 saniye kaldı." },
  { at: 60, text: "1 dakika kaldı." },
  { at: 300, text: "5 dakika kaldı." },
] as const;

export function timeNotice(remaining: number | null): string {
  if (remaining === null) return "";
  return TIME_NOTICES.find((notice) => remaining <= notice.at)?.text ?? "";
}

/** "12:05" — dakika sınırsız (uzun sınav 90:00 gösterebilmeli). */
export function formatClock(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(safe / 60);
  return `${minutes}:${String(safe % 60).padStart(2, "0")}`;
}

/**
 * Sayacın bir saniyelik ilerlemesi. Süresiz oturumda (`practice`) null kalır ve
 * hiç sayaç kurulmaz; sıfırın altına inmez.
 */
export function tickRemaining(remaining: number | null): number | null {
  return remaining === null ? null : Math.max(0, remaining - 1);
}

/** Son bir dakika: sayaç `--warning`'e döner. Yanıp sönme yok (DESIGN.md). */
export function isLastMinute(remaining: number | null): boolean {
  return remaining !== null && remaining <= 60;
}

/**
 * Süre bitti mi? Karar SUNUCUNUNDUR (`expired`); yerel sayacın sıfıra inmesi
 * yalnız erken kapanma sebebidir.
 *
 * İki yönlü olması bilinçli: sunucu "doldu" diyorsa istemci sayacı hâlâ 3
 * gösteriyor olsa bile cevap gönderilmez (fail-closed); yerel sayaç sıfırlandıysa
 * da ekran sunucunun teyidini beklemeden yazmayı durdurur — beklerken gönderilen
 * cevap zaten 409 alır ve öğrenciye boş yere hata gösterir.
 */
export function timeIsUp(session: ExamSession, localRemaining: number | null): boolean {
  if (session.expired) return true;
  return localRemaining !== null && localRemaining <= 0;
}

/** Oturum bitmiş mi (öğrenci bitirdi ya da süresi doldu). */
export function isClosed(session: ExamSession, localRemaining: number | null): boolean {
  return session.finished_at !== null || timeIsUp(session, localRemaining);
}

/**
 * Sunucudan süre tazelenmeli mi?
 *
 * Yalnız süreli ve hâlâ açık oturumda. Bitmiş ya da süresiz bir oturumu
 * yoklamak durdurulmayan polling'dir ve kusur sayılır (Anayasa XI).
 */
export function shouldPoll(session: ExamSession): boolean {
  return session.remaining_seconds !== null && !session.expired && session.finished_at === null;
}

/* -------------------------------------------------------------------------
 * Soru daraltma
 * ---------------------------------------------------------------------- */

export interface McqChoice {
  key: string;
  text: string;
}

/**
 * Sorunun gösterilebilir hâli.
 *
 * `unsupported` ölü dal değil: `payload` sunucuda jsonb'dir, beyaz listeden
 * geçer ve tip listesi ileride büyüyebilir. Tanınmayan bir soru ekranı
 * çökertmemeli; atlanmalı.
 */
export type QuestionView =
  | { kind: "mcq"; prompt: string; choices: McqChoice[] }
  | { kind: "text"; prompt: string; multiline: boolean }
  | { kind: "code"; prompt: string; language: string; code: string }
  | { kind: "unsupported" };

const UNSUPPORTED: QuestionView = { kind: "unsupported" };

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

function choices(value: unknown): McqChoice[] | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  const parsed: McqChoice[] = [];
  for (const item of value) {
    if (typeof item !== "object" || item === null) return null;
    const key = text((item as Record<string, unknown>).key);
    const label = text((item as Record<string, unknown>).text);
    if (key === null || label === null) return null;
    parsed.push({ key, text: label });
  }
  return parsed;
}

/**
 * `payload`'ı tipine göre daraltır. Şekil tutmuyorsa `unsupported` döner.
 *
 * Neden eksik alanda kapanıyoruz: şıksız bir çoktan seçmeli ya da kodsuz bir
 * kod sorusu, öğrencinin körlemesine cevap yazacağı bir tuzaktır. Gösterilemeyen
 * soruyu atlamak, yarısını gösterip cevap istemekten iyidir (Anayasa IV).
 *
 * `open` tipinde `format` eksikse çok satırlı girdiye düşülür: biçim yalnız
 * girdi kutusunun boyunu belirler, kısa cevap da çok satırlı kutuya yazılabilir.
 */
export function describeQuestion(question: ExamQuestion): QuestionView {
  const payload = question.payload ?? {};

  switch (question.type) {
    case "mcq": {
      const prompt = text(payload.stem);
      const options = choices(payload.options);
      return prompt && options ? { kind: "mcq", prompt, choices: options } : UNSUPPORTED;
    }
    case "open": {
      const prompt = text(payload.prompt);
      if (!prompt) return UNSUPPORTED;
      return { kind: "text", prompt, multiline: payload.format !== "short_answer" };
    }
    case "code_trace":
    case "bug_hunt": {
      const prompt = text(payload.prompt);
      const code = text(payload.code);
      if (!prompt || !code) return UNSUPPORTED;
      return { kind: "code", prompt, code, language: text(payload.language) ?? "" };
    }
    default:
      // Sözleşmede olmayan tip: derleyici buraya düşmez ama sunucu düşebilir.
      return UNSUPPORTED;
  }
}

/** Ekranda gösterilebilen sorular. Sayaç ve gezinme bu listeye göre kurulur. */
export function shownQuestions(session: ExamSession): ExamQuestion[] {
  return session.questions ?? [];
}

/* -------------------------------------------------------------------------
 * Cevap gönderimi
 * ---------------------------------------------------------------------- */

/**
 * Bu cevap gönderilebilir mi?
 *
 * Beş kapı: oturum kapalı değil, süre dolmadı, soru daha önce cevaplanmadı
 * (soru başına tek deneme — ikincisi 409), taslak boş değil, sunucunun sınırını
 * aşmıyor. Gönderilemeyecek bir cevabın düğmesi etkin görünürse buton yalan
 * söyler (Anayasa XI).
 */
export function canSubmitAnswer({
  session,
  question,
  draft,
  localRemaining,
}: {
  session: ExamSession;
  question: ExamQuestion;
  draft: string;
  localRemaining: number | null;
}): boolean {
  if (isClosed(session, localRemaining)) return false;
  if (question.answered) return false;
  const trimmed = draft.trim();
  return trimmed.length > 0 && trimmed.length <= ANSWER_MAX_LENGTH;
}

/* -------------------------------------------------------------------------
 * İpucu
 * ---------------------------------------------------------------------- */

/**
 * İpucu yüzeyi hiç çizilsin mi?
 *
 * Sınav modunda sunucu ipucunu 403 ile reddediyor (`request_hint`). Düğmeyi
 * devre dışı çizmek yetmez: etkin görünüp iş yapmayan yüzey kusurdur, devre dışı
 * görünen yüzey de öğrenciye "burada bir şey var ama sana kapalı" der ve sınav
 * sırasında dikkat çalar. Sınav modunda düğme HİÇ render edilmez.
 */
export function showsHints(mode: ExamMode): boolean {
  return mode === "practice";
}

/**
 * Bir sonraki ipucu kademesi; merdivenin sonundaysa null (düğme çizilmez).
 * Sunucu da kademeyi `socratic_max_stage` ile kırpar — aynı kademeyi ikinci kez
 * istemek merdivene aynı basamağı iki kez eklerdi.
 */
export function nextHintLevel(current: number): number | null {
  return current >= HINT_MAX_LEVEL ? null : current + 1;
}

/* -------------------------------------------------------------------------
 * Geri bildirim
 * ---------------------------------------------------------------------- */

/**
 * Cevabın gösterilebilir sonucu.
 *
 * - `correct` / `incorrect`: sunucu puanladı ve sonucu açtı (practice, ya da
 *   sınav bitince `/finish` sonuçları).
 * - `ungraded`: değerlendirme tamamlanamadı (`graded: false`). Puan YOKTUR ve
 *   uydurulmaz; sunucunun `message` alanı gösterilir.
 * - `recorded`: cevap kaydedildi ama sonucu şimdi açılmıyor (sınav modu). Bu bir
 *   arıza değildir; "yanlış" da değildir.
 */
export type AnswerVerdict = "correct" | "incorrect" | "ungraded" | "recorded";

export function answerVerdict(feedback: AnswerFeedback): AnswerVerdict {
  if (!feedback.graded) return "ungraded";
  if (feedback.is_correct === true) return "correct";
  if (feedback.is_correct === false) return "incorrect";
  return "recorded";
}

/**
 * Sonuç etiketleri.
 *
 * `incorrect` WARNING tonundadır, danger değil: yanlış cevap bir arıza değil
 * çalışma yönüdür — `masteryLevel`'ın "Geliştirilmeli"si de aynı tonda
 * (`lib/labels.ts`). Kırmızı bu üründe hata rengi değildir (DESIGN.md).
 * `ungraded` nötrdür: sistemin uydurmak yerine susması bir başarıdır.
 */
export const VERDICT_LABEL: Record<AnswerVerdict, { label: string; tone: Tone }> = {
  correct: { label: "Doğru", tone: "success" },
  incorrect: { label: "Yanlış", tone: "warning" },
  ungraded: { label: "Değerlendirilemedi", tone: "neutral" },
  recorded: { label: "Cevabınız kaydedildi", tone: "neutral" },
};

/**
 * Puan metni. Sunucu 0-100 arası verir (`grade_mcq` 0/100, LLM verdict'i 0-100).
 * Puan yoksa null döner — "0" yazmak "her şeyi yanlış yaptın" demektir ve
 * yanlıştır (backend `score_of` da bu yüzden None döndürüyor).
 */
export function formatScore(score: number | null | undefined): string | null {
  if (typeof score !== "number" || Number.isNaN(score)) return null;
  return Number.isInteger(score) ? `${score} / 100` : `${score.toFixed(1)} / 100`;
}

/* -------------------------------------------------------------------------
 * Çözüm
 * ---------------------------------------------------------------------- */

export interface SolutionLine {
  label: string;
  value: string;
}

/**
 * `solution` jsonb'sini okunur satırlara çevirir.
 *
 * Şekli tipe göre değişir: `bug_hunt`'ta `answer_key` bir NESNEDİR
 * (`{line, bug_type, fix_summary}`), diğerlerinde metindir. Düz metin varsayan
 * bir ekran orada "[object Object]" basar.
 *
 * `rubric` bilerek gösterilmiyor: ağırlıklar değerlendirmenin aracıdır ve
 * `graded: false` gelen bir cevapta hiçbir puan dağılımı yoktur — ağırlık
 * göstermek olmayan bir kırılımı ima eder (Anayasa III).
 */
export function describeSolution(solution: Record<string, unknown> | null | undefined): SolutionLine[] {
  if (!solution) return [];
  const lines: SolutionLine[] = [];

  const key = solution.answer_key;
  const keyText = text(key);
  if (keyText) {
    lines.push({ label: "Cevap anahtarı", value: keyText });
  } else if (typeof key === "object" && key !== null) {
    const bug = key as Record<string, unknown>;
    const line = typeof bug.line === "number" ? String(bug.line) : null;
    if (line) lines.push({ label: "Hatalı satır", value: line });
    const kind = text(bug.bug_type);
    if (kind) lines.push({ label: "Hata türü", value: kind });
    const fix = text(bug.fix_summary);
    if (fix) lines.push({ label: "Düzeltme", value: fix });
  }

  const explanation = text(solution.explanation);
  if (explanation) lines.push({ label: "Açıklama", value: explanation });

  if (Array.isArray(solution.key_points)) {
    for (const point of solution.key_points) {
      const value = text(point);
      if (value) lines.push({ label: "Beklenen nokta", value });
    }
  }

  return lines;
}

/* -------------------------------------------------------------------------
 * Kaynak
 * ---------------------------------------------------------------------- */

/**
 * `SourceRef` → kaynak kartı girdisi. Dosya adı ve konum chunk metadata'sından
 * gelir; arayüz hiçbirini üretmez, yalnız taşır (Anayasa I).
 */
export function sourceInfo(ref: SourceRef): SourceInfo {
  return { fileName: ref.file_name, location: ref.location, quote: ref.snippet };
}

/* -------------------------------------------------------------------------
 * Başlatma hatası
 * ---------------------------------------------------------------------- */

/**
 * Sınav kurulamadı ama bu bir ARIZA değil: havuzda onaylanmış soru yok.
 * Sunucu bunu 409 `conflict` ile söyler ("Bu derste henüz onaylanmış soru
 * yok…"). Kırmızı hata kutusu göstermek öğrenciye sistemin bozulduğunu
 * düşündürür; oysa yapılacak şey bellidir ve mesajı sunucu yazmıştır.
 *
 * Başlatma anında tek `conflict` sebebi budur (`start_exam`'da başka
 * `ConflictError` yok).
 */
export function isEmptyPool(error: unknown): boolean {
  return error instanceof ApiError && error.code === "conflict";
}
