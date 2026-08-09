/**
 * Durum etiketleri ve tonları — arayüzün ortak sözlüğü.
 *
 * Etiket haritaları üç ayrı sayfaya dağılmıştı. Dağınık olmalarının somut
 * riski şu: DESIGN.md "kırmızı ASLA hata rengi değildir" diyor, ama bu kural
 * her dosyada yeniden hatırlanmak zorunda kalırsa er geç biri "reddedildi"yi
 * kırmızıya boyar. Ton seçimi burada bir kez verilir.
 *
 * Kural: renk tek başına bilgi taşımaz — her girdinin bir `label` metni vardır.
 */

// Soru tipi/durumu SÖZLEŞME tipleridir (backend enum'ları), etiket sözlüğü değil:
// tanımları `types.ts`'te durur ve buradan yalnız yeniden dışa aktarılır. İkinci bir
// tanım, backend'e yeni bir soru tipi eklendiğinde birinin güncellenip diğerinin
// unutulacağı bir ayrışma açardı (Anayasa XI).
import type { DocumentStatus, QuestionStatus, QuestionType } from "@/lib/types";

export type { QuestionStatus, QuestionType };

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

export interface LabelSpec {
  label: string;
  tone: Tone;
}

/** Materyal işleme durumu. `failed` gerçek bir hatadır; danger meşrudur. */
export const DOCUMENT_STATUS: Record<DocumentStatus, LabelSpec> = {
  uploaded: { label: "Sırada", tone: "neutral" },
  processing: { label: "İşleniyor", tone: "warning" },
  completed: { label: "Hazır", tone: "success" },
  failed: { label: "Başarısız", tone: "danger" },
};


export const QUESTION_TYPE: Record<QuestionType, string> = {
  mcq: "Çoktan seçmeli",
  open: "Açık uçlu",
  code_trace: "Kod çıktısı",
  bug_hunt: "Hata bulma",
};

/**
 * Soru durumu. `rejected` NEUTRAL — danger değil: red bir hata değil,
 * eğitmenin kararıdır ve kırmızı bu üründe hata rengi olarak kullanılmaz.
 */
export const QUESTION_STATUS: Record<QuestionStatus, LabelSpec> = {
  draft: { label: "Taslak", tone: "info" },
  approved: { label: "Onaylandı", tone: "success" },
  rejected: { label: "Reddedildi", tone: "neutral" },
};

/**
 * Konu hâkimiyeti seviyeleri — eşikler spec FR-027 ile birebir:
 * <0.40 Geliştirilmeli · 0.40-0.74 Orta · >=0.75 İyi (sınırlar dahildir).
 *
 * "Geliştirilmeli" WARNING tonundadır, danger değil: düşük skor bir hata
 * değil, çalışma yönüdür.
 */
export const MASTERY_THRESHOLDS = { good: 0.75, medium: 0.4 } as const;

export function masteryLevel(score: number): LabelSpec {
  if (score >= MASTERY_THRESHOLDS.good) return { label: "İyi", tone: "success" };
  if (score >= MASTERY_THRESHOLDS.medium) return { label: "Orta", tone: "info" };
  return { label: "Geliştirilmeli", tone: "warning" };
}

/** Dosya boyutu — listede tek satırda okunur kalmalı, ondalık yok. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Parça konumu: "Sayfa 7" · "Slayt 3" · bölüm adı. Konum HER ZAMAN görünür. */
export function chunkLocation(chunk: {
  page_number: number | null;
  slide_number: number | null;
  section_title: string | null;
}): string {
  if (chunk.page_number != null) return `Sayfa ${chunk.page_number}`;
  if (chunk.slide_number != null) return `Slayt ${chunk.slide_number}`;
  return chunk.section_title ?? "Konum yok";
}
