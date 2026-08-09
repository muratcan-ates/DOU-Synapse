/**
 * Sohbet ekranının saf mantığı — istek gövdesi kurma, kademe sözlüğü, dökümü
 * bloklara ayırma.
 *
 * Neden ayrı dosya: bu kuralların hepsi sözleşmeye bağlı ürün kararları ve
 * hiçbiri DOM istemiyor. Sayfanın içinde dururlarsa yalnız tarayıcıda
 * sınanabilirler; burada `bun test lib/` ile sınanıyorlar. Bir kural sessizce
 * bozulursa (ör. QA modunda `student_attempt` gönderilmesi) ekran çalışmaya
 * devam eder, sadece yanlış şeyi yapar — testin yakaladığı tam bu.
 */

import type {
  AnswerStatus,
  ChatAnswer,
  ChatMessage,
  ChatMode,
  ChatRequest,
  Citation,
  SocraticStage,
} from "@/lib/types";

/**
 * Arayüzün sunduğu modlar. `exam` bilinçli olarak yok: sohbet ucu sınav modunu
 * 422 ile reddeder (sınav etkileşimi sınav ekranından gider), dolayısıyla
 * seçilebilir yapmak etkin görünüp iş yapmayan bir kontrol olurdu.
 */
export type ChatUiMode = "qa" | "socratic";

export const CHAT_UI_MODES = ["qa", "socratic"] as const satisfies readonly ChatUiMode[];

/** Mod adları — oturum listesindeki `exam` de karşılıksız kalmasın diye tam. */
export const CHAT_MODE_LABEL: Record<ChatMode, string> = {
  qa: "Soru-cevap",
  socratic: "Sokratik",
  exam: "Sınav",
};

// ---------------------------------------------------------------------------
// Sokratik kademeler
// ---------------------------------------------------------------------------

/**
 * Kademe sırası sunucudaki state machine ile birebir (app/modules/assessment).
 * Sıra bir sunum tercihi değil: gösterge "nereye kadar gelindi"yi bu diziden
 * okuyor, karışırsa merdiven geriye gitmiş gibi görünür.
 */
export const SOCRATIC_STAGES = [
  "diagnose",
  "nudge",
  "concept_hint",
  "similar_example",
  "explain_with_source",
] as const satisfies readonly SocraticStage[];

export const SOCRATIC_STAGE_LABEL: Record<SocraticStage, string> = {
  diagnose: "Tanı",
  nudge: "Yönlendirme",
  concept_hint: "Kavram ipucu",
  similar_example: "Benzer örnek",
  explain_with_source: "Kaynaklı açıklama",
};

/** Kademesi bildirilmemiş ipucu de etiketsiz kalmaz — konum bilgisi gibi bu da hep görünür. */
export function stageLabel(stage: SocraticStage | null): string {
  return stage === null ? "İpucu" : SOCRATIC_STAGE_LABEL[stage];
}

/** Göstergedeki nokta sırası; kademe yoksa -1 (hiçbir nokta dolmaz). */
export function stageIndex(stage: SocraticStage | null): number {
  return stage === null ? -1 : SOCRATIC_STAGES.indexOf(stage);
}

// ---------------------------------------------------------------------------
// Abstention
// ---------------------------------------------------------------------------

/**
 * "Cevap yok"un iki ayrı sebebi. Karıştırılmamalı: `insufficient_context`
 * materyalde dayanak bulunamadığını, `out_of_scope` sorunun dersin konusu
 * olmadığını söyler. İkisi de HATA DEĞİLDİR (Anayasa VII).
 */
export type AbstentionStatus = Exclude<AnswerStatus, "answered">;

/**
 * Durum başlığı. Açıklayıcı cümle backend'den gelir (`answer`); burada yalnız
 * iki durumu birbirinden ayıran kısa başlık var — aksi hâlde iki farklı sonuç
 * ekranda aynı görünürdü.
 */
export const ABSTENTION_LABEL: Record<AbstentionStatus, string> = {
  insufficient_context: "Materyalde dayanak bulunamadı",
  out_of_scope: "Dersin kapsamı dışında",
};

export function isAbstention(status: AnswerStatus | null): status is AbstentionStatus {
  return status === "insufficient_context" || status === "out_of_scope";
}

// ---------------------------------------------------------------------------
// İstek gövdesi
// ---------------------------------------------------------------------------

/** Sözleşme sınırları (openapi.json ChatRequest): question 3..2000. */
export const QUESTION_MIN_LENGTH = 3;
export const QUESTION_MAX_LENGTH = 2000;

export interface DraftContext {
  mode: ChatUiMode;
  /** Girdi alanındaki metin. */
  draft: string;
  sessionId: string | null;
  /** Açık oturumu başlatan soru; oturum yoksa null. */
  openingQuestion: string | null;
}

/**
 * Bu tur bir Sokratik devam turu mu?
 *
 * Devam turunda öğrencinin yazdığı metin bir soru değil bir DENEMEdir ("sanırım
 * dört koşul", "hı"). Aramanın ona kaymaması gerekir; bkz. `buildChatRequest`.
 */
export function isSocraticFollowUp(context: {
  mode: ChatUiMode;
  sessionId: string | null;
  openingQuestion: string | null;
}): boolean {
  return (
    context.mode === "socratic" &&
    context.sessionId !== null &&
    context.openingQuestion !== null &&
    context.openingQuestion.trim().length > 0
  );
}

/**
 * Sunucuya gidecek gövde.
 *
 * İki kural pazarlıksız:
 *
 * 1. Sokratik devam turlarında `question` OTURUMU AÇAN sorudur, öğrencinin yeni
 *    yazdığı metin `student_attempt`'e gider. Arama açılış sorusuna bağlı
 *    kalmazsa "hı" ile arama yapılır, hiç parça bulunmaz ve merdiven ikinci
 *    turda kanıt eşiğine takılıp çöker (sunucuda birebir gözlenmiş).
 * 2. QA modunda `student_attempt` HİÇ gönderilmez.
 *
 * Şema `extra="forbid"`: tanınmayan tek bir alan bütün isteği 422 yapar, o
 * yüzden gövdeye yalnız dolu alanlar konur.
 */
export function buildChatRequest(context: DraftContext): ChatRequest {
  const text = context.draft.trim();
  const followUp = isSocraticFollowUp(context);

  const body: ChatRequest = {
    question: followUp ? (context.openingQuestion as string).trim() : text,
    mode: context.mode,
  };
  if (context.sessionId !== null) body.session_id = context.sessionId;
  if (followUp) body.student_attempt = text;
  return body;
}

/**
 * Gönderilebilir mi? Girdi boşsa ya da `question` alanına gidecek metin alt
 * sınırın altındaysa hayır.
 *
 * Devam turunda alt sınır uygulanmaz: oraya giden metin `student_attempt` ve
 * onun asgari uzunluğu yok — kısa bir deneme ("hı") geçerli bir denemedir.
 * Gönderilemeyen durumda buton kapalı kalır; arayüz kendi hata metnini
 * uydurmaz (Anayasa V).
 */
export function canSubmitDraft(draft: string, followUp: boolean): boolean {
  const text = draft.trim();
  if (text.length === 0) return false;
  if (text.length > QUESTION_MAX_LENGTH) return false;
  return followUp || text.length >= QUESTION_MIN_LENGTH;
}

/** Açık oturumun sayfa yenilemesinden sonra da bulunabilmesi için depo anahtarı. */
export function openSessionKey(courseId: string): string {
  return `dou-synapse-chat-session:${courseId}`;
}

// ---------------------------------------------------------------------------
// Döküm
// ---------------------------------------------------------------------------

/**
 * Döküm satırı. Canlı yanıt (`ChatAnswer`) ve yüklenen geçmiş (`ChatMessage`)
 * aynı biçime indirgenir; iki ayrı render yolu olsaydı biri er geç diğerinden
 * ayrışırdı (Anayasa XI).
 */
export interface TranscriptMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status: AnswerStatus | null;
  citations: Citation[];
  socraticStage: SocraticStage | null;
}

export function fromHistory(messages: ChatMessage[]): TranscriptMessage[] {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    status: message.status,
    citations: message.citations ?? [],
    socraticStage: message.socratic_stage,
  }));
}

/**
 * Canlı yanıtın asistan satırı.
 *
 * `hints[]` bilerek okunmuyor. Sunucuda doğrulandı (`schemas/chat.py`
 * `to_chat_response`): Sokratik ipucu ayrı bir metin değil, cevabın kendisidir
 * ve kaynağı `citations[0]`'dır. Geçmiş ucunda ise `hints` alanı hiç yok.
 * `hints`'i canlı yolda kullanmak, geçmişten farklı bir ikinci render yolu
 * açardı — aynı ekran iki kaynaktan beslenince ayrışır.
 */
export function fromAnswer(answer: ChatAnswer): TranscriptMessage {
  return {
    id: answer.message_id,
    role: "assistant",
    content: answer.answer,
    status: answer.status,
    citations: answer.citations ?? [],
    socraticStage: answer.socratic_stage,
  };
}

export function userMessage(id: string, content: string): TranscriptMessage {
  return { id, role: "user", content, status: null, citations: [], socraticStage: null };
}

/** Kaynak kartının beklediği biçim. Alıntı `snippet`'tir: chunk'tan birebir gelir. */
export function citationSource(citation: Citation): {
  fileName: string;
  location: string;
  quote: string;
} {
  return {
    fileName: citation.file_name,
    // Konum sunucudan "Sayfa 7" / "Slayt 3" olarak gelir; arayüz biçimlendirmez.
    location: citation.location,
    // `claim` model metnidir ve gösterilmez (Anayasa I: alıntı yeniden yazılmaz).
    quote: citation.snippet,
  };
}

export interface LadderRung {
  id: string;
  stage: SocraticStage | null;
  text: string;
  source: { fileName: string; location: string; quote: string };
  /** Bu kademeyi açan öğrenci denemesi; açılış turunda null. */
  attempt: string | null;
}

export type ChatBlock =
  | { kind: "question"; id: string; text: string }
  | { kind: "answer"; id: string; text: string; citations: Citation[] }
  | { kind: "abstention"; id: string; text: string; status: AbstentionStatus }
  | { kind: "ladder"; id: string; rungs: LadderRung[] };

/**
 * Düz mesaj listesini ekranın çizdiği bloklara çevirir.
 *
 * Tek kritik karar burada: ardışık Sokratik kademeler TEK merdivende toplanır,
 * aralarındaki öğrenci denemeleri kendi kademelerine iliştirilir. Her kademeyi
 * ayrı bir kart olarak çizmek "ipuçları üst üste birikir" kuralını görsel olarak
 * bozardı (DESIGN.md); denemeleri atmak ise "öğrenci ne denedi" sorusunu
 * cevapsız bırakırdı.
 *
 * Kademe olmayan bir tur (abstention) merdiveni keser: sonraki kademe yeni bir
 * merdivende başlar, ama önceki merdiven ekranda kalır — hiçbir ipucu silinmez.
 */
export function toBlocks(
  messages: TranscriptMessage[],
  options: { mode: ChatUiMode; pending?: string | null },
): ChatBlock[] {
  const blocks: ChatBlock[] = [];
  let waiting: TranscriptMessage | null = null;

  const flushWaiting = () => {
    if (waiting === null) return;
    blocks.push({ kind: "question", id: waiting.id, text: waiting.content });
    waiting = null;
  };

  for (const message of messages) {
    if (message.role === "user") {
      flushWaiting();
      waiting = message;
      continue;
    }

    const rung = options.mode === "socratic" ? toRung(message) : null;
    if (rung !== null) {
      const last = blocks[blocks.length - 1];
      if (last !== undefined && last.kind === "ladder") {
        // Merdivenin bir üst kademesi: denemeyi balon yapmak yerine kademeye iliştir.
        rung.attempt = waiting === null ? null : waiting.content;
        waiting = null;
        last.rungs.push(rung);
      } else {
        // Merdivenin ilk kademesi: açılış sorusu kendi balonunda kalır.
        flushWaiting();
        blocks.push({ kind: "ladder", id: message.id, rungs: [rung] });
      }
      continue;
    }

    flushWaiting();
    if (isAbstention(message.status)) {
      blocks.push({
        kind: "abstention",
        id: message.id,
        text: message.content,
        status: message.status,
      });
    } else {
      blocks.push({
        kind: "answer",
        id: message.id,
        text: message.content,
        citations: message.citations,
      });
    }
  }

  flushWaiting();

  const pending = options.pending?.trim();
  if (pending) blocks.push({ kind: "question", id: "pending", text: pending });

  return blocks;
}

/**
 * Bir asistan mesajı merdiven kademesi mi?
 *
 * Kaynaksız ipucu kademe SAYILMAZ (Anayasa I). Sunucu zaten kaynaksız ipucu
 * göndermiyor; burada da varsayılmıyor, kontrol ediliyor.
 */
function toRung(message: TranscriptMessage): LadderRung | null {
  if (message.status !== "answered") return null;
  const source = message.citations[0];
  if (source === undefined) return null;
  return {
    id: message.id,
    stage: message.socraticStage,
    text: message.content,
    source: citationSource(source),
    attempt: null,
  };
}
