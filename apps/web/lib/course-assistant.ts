/**
 * Ders asistanının rol zarfı ve güvenli başlangıç önerileri.
 *
 * Burada YETKİ kararı yoktur. `audience` ve `agent_profile` yalnız sunucudan
 * gelir; bu dosya yalnız ikisinin birbiriyle tutarlı olup olmadığını denetler
 * ve görünür metne çevirir. Dashboard'daki `course.role` ya da bir rol seçici
 * asistan kimliği üretmek için kullanılmaz.
 */

import type { ChatUiMode } from "@/lib/chat";
import type {
  ChatAgentProfile,
  ChatAnswer,
  ChatAudience,
  ChatMode,
  ChatSessionSummary,
} from "@/lib/types";

export interface AssistantSuggestion {
  label: string;
  prompt: string;
  preferredMode: ChatUiMode;
}

export interface CourseAssistantIdentity {
  audience: ChatAudience;
  agentProfile: ChatAgentProfile;
  name: "Ders Koçu" | "Eğitmen Asistanı";
  eyebrow: "Öğrenci çalışma alanı" | "Eğitmen çalışma alanı";
  description: string;
  suggestions: readonly AssistantSuggestion[];
}

const STUDENT_IDENTITY: CourseAssistantIdentity = {
  audience: "student",
  agentProfile: "student_coach",
  name: "Ders Koçu",
  eyebrow: "Öğrenci çalışma alanı",
  description:
    "Ders kaynaklarına bağlı kalır; gerektiğinde cevabı vermek yerine adım adım düşündürür.",
  suggestions: [
    {
      label: "Konuyu adım adım çalış",
      prompt:
        "Bu konuyu doğrudan cevabı vermeden, ders kaynaklarına bağlı kalarak adım adım çalışmama yardım et.",
      preferredMode: "socratic",
    },
    {
      label: "Kaynaklı açıklama iste",
      prompt:
        "Ders materyallerindeki temel kavramları kaynaklarıyla ve kısa bir örnekle açıklar mısın?",
      preferredMode: "qa",
    },
    {
      label: "Yanlışımı bul",
      prompt:
        "Bu konuda nerede yanılabileceğimi anlamam için bana tek bir kontrol sorusu sor.",
      preferredMode: "socratic",
    },
  ],
};

const INSTRUCTOR_IDENTITY: CourseAssistantIdentity = {
  audience: "instructor",
  agentProfile: "instructor_assistant",
  name: "Eğitmen Asistanı",
  eyebrow: "Eğitmen çalışma alanı",
  description:
    "Yüklediğiniz ders kaynaklarını öğretim hazırlığı açısından inceler ve her bulguyu kaynağına bağlar.",
  suggestions: [
    {
      label: "Zor kavramları çıkar",
      prompt:
        "Bu dersin kaynaklarında öğrencilerin zorlanabileceği kavramları kaynaklarıyla özetle.",
      preferredMode: "qa",
    },
    {
      label: "Sokratik yönlendirme tasarla",
      prompt:
        "Bu konu için cevabı doğrudan vermeyen, kaynaklı bir Sokratik yönlendirme örneği oluştur.",
      // Eğitmen bir yönlendirme TASLAĞI ister. Sokratik state machine ise
      // konuşanı öğrenci kabul edip tek-ipucu turu açar; başlangıçta QA doğru
      // rol promptunu kullanır. Eğitmen isterse mod seçiciden ayrıca değiştirir.
      preferredMode: "qa",
    },
    {
      label: "Kaynak boşluklarını gör",
      prompt:
        "Yüklenen kaynaklarda öğrencinin yanlış anlayabileceği belirsiz veya eksik noktaları kaynaklarıyla listele.",
      preferredMode: "qa",
    },
  ],
};

/** Geçerli iki sunucu eşleşmesi dışında persona üretme — belirsizlikte kapan. */
export function resolveCourseAssistantIdentity(
  audience: ChatAudience | null,
  agentProfile: ChatAgentProfile | null,
): CourseAssistantIdentity | null {
  if (audience === "student" && agentProfile === "student_coach") {
    return STUDENT_IDENTITY;
  }
  if (audience === "instructor" && agentProfile === "instructor_assistant") {
    return INSTRUCTOR_IDENTITY;
  }
  return null;
}

/** Sohbet bestecisi sınav modunu hiçbir zaman sunmaz; sıra sunucudan gelir. */
export function allowedChatUiModes(modes: readonly ChatMode[]): ChatUiMode[] {
  const result: ChatUiMode[] = [];
  for (const mode of modes) {
    if ((mode === "qa" || mode === "socratic") && !result.includes(mode)) {
      result.push(mode);
    }
  }
  return result;
}

export function firstAllowedChatMode(modes: readonly ChatUiMode[]): ChatUiMode | null {
  return modes[0] ?? null;
}

/**
 * Canlı cevap availability ile aynı üyelik zarfını taşımak zorunda.
 * İstemci farklı bir zarfı kabul edip konuşmanın ortasında persona değiştirmez.
 */
export function answerMatchesAssistant(
  answer: Pick<ChatAnswer, "audience" | "agent_profile">,
  identity: CourseAssistantIdentity,
): boolean {
  return (
    answer.audience === identity.audience &&
    answer.agent_profile === identity.agentProfile
  );
}

/** Geçmiş oturum da mevcut üyelik/persona zarfıyla aynı olmak zorunda. */
export function sessionMatchesAssistant(
  session: Pick<ChatSessionSummary, "audience" | "agent_profile">,
  identity: CourseAssistantIdentity,
): boolean {
  return (
    session.audience === identity.audience &&
    session.agent_profile === identity.agentProfile
  );
}
