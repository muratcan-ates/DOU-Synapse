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

/**
 * Oturum listesinde gösterilecek kademe etiketi; gösterilmeyecekse null.
 *
 * Sokratik bir oturuma dönen öğrencinin listeden görebilmesi gereken tek şey
 * "nerede kalmıştım". Zarf bunu `ChatSessionSummary.socratic_stage` olarak
 * taşıyor (canlı listede gözlendi: Sokratik oturumda `"nudge"`, QA'da `null`).
 *
 * `stageLabel` burada kullanılmıyor: o, kademesiz ipucuna "İpucu" der ve bu
 * merdivenin İÇİNDE doğrudur (satırın bir başlığı olmalı). Listede aynı kelime
 * "nerede kaldın" sorusuna hiçbir şey söylemez, üstelik kademe gerçekten
 * bilinmiyorken biliniyormuş gibi görünür. Bilinmeyen kademe için hiçbir şey
 * yazılmaz (Anayasa III); boş kalması hata değildir (Anayasa VII).
 */
export function sessionStageLabel(summary: {
  mode: ChatMode;
  socratic_stage: SocraticStage | null;
}): string | null {
  if (summary.mode !== "socratic") return null;
  if (summary.socratic_stage === null) return null;
  return SOCRATIC_STAGE_LABEL[summary.socratic_stage];
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
  budget_exhausted: "Dersin günlük AI sınırına ulaşıldı",
};

export function isAbstention(status: AnswerStatus | null): status is AbstentionStatus {
  return (
    status === "insufficient_context" ||
    status === "out_of_scope" ||
    status === "budget_exhausted"
  );
}

// ---------------------------------------------------------------------------
// Önbellek işareti
// ---------------------------------------------------------------------------

/**
 * Önbellekten dönen cevabın dipnotu (FR-034).
 *
 * Neden ekranda bir karşılığı olmalı: `answer_cache` bu ürünün çevrimdışı yedek
 * planıdır. Ağ ya da sağlayıcı giderse birebir eşleşen soru LLM'e HİÇ gitmeden
 * cevaplanır. Zarf bunu `cached` ile söylüyor ve arayüz bugüne kadar okumuyordu;
 * okumayan bir arayüzde "önbellek çalışıyor" iddiasının gözlenebilir hiçbir
 * karşılığı yok (Anayasa III).
 *
 * Ton kasten sessiz: önbellek isabeti bir kusur değil, tasarlanmış davranıştır.
 * Ne uyarı, ne ünlem, ne kırmızı. Cümle kendi kendini açıklıyor çünkü tek
 * başına "önbellekten" kelimesi öğrenciye bir şey anlatmaz; okuyan kişi
 * cevabının eski mi yoksa bozuk mu olduğunu merak eder.
 */
export const CACHED_ANSWER_NOTE =
  "Bu cevap önbellekten geldi: aynı soru daha önce sorulduğu için yeniden üretilmedi.";

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
  /**
   * Cevap birebir eşleşmeli önbellekten mi geldi (FR-034)?
   *
   * Yalnız CANLI turda bilinir: geçmiş ucu (`GET /chat/sessions/{id}`) bu alanı
   * taşımıyor, dolayısıyla yeniden açılan bir oturumda dipnot çizilmez. Bu bir
   * eksiklik gibi görünür ama doğru davranıştır: işaret POZİTİF bir bildirimdir,
   * yokluğu "önbellekten gelmedi" değil "sunucu söylemedi" demektir. Geçmişte
   * `false` yazmak, sunucunun vermediği bir bilgiyi uydurmak olurdu (Anayasa III).
   */
  cached: boolean;
}

export function fromHistory(messages: ChatMessage[]): TranscriptMessage[] {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    status: message.status,
    citations: message.citations ?? [],
    socraticStage: message.socratic_stage,
    cached: false,
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
    cached: answer.cached,
  };
}

export function userMessage(id: string, content: string): TranscriptMessage {
  return {
    id,
    role: "user",
    content,
    status: null,
    citations: [],
    socraticStage: null,
    cached: false,
  };
}

/**
 * Kaynak kartının beklediği biçim. Alıntı `snippet`'tir: chunk'tan birebir gelir.
 *
 * ## `claim` neden hâlâ gösterilmiyor (9 Ağustos kararı)
 *
 * Buradaki eski gerekçe YANLIŞTI: "alıntı yeniden yazılmaz" deniyordu, oysa
 * `claim` bir alıntı değil. Alıntı `snippet`'tir ve chunk metninden kesilir;
 * `claim` ise "bu atıf hangi iddiayı destekliyor" açıklamasıdır. İkisi ayrı
 * şeyler ve `claim` artık guardrail'in metne bakan halkasından da geçiyor
 * (R4, `guardrails/citation.py`), yani göstermek GÜVENLİ. Karar yine de
 * "gösterme", ama sebebi güvenlik değil; canlı hatta ölçülen üç şey:
 *
 * 1. **Önbellek yolunda alan her zaman boş.** `api/chat.py::_store_cache`
 *    atıfları `_citation_to_json(c)` ile, yani `claim` argümanı olmadan yazıyor;
 *    dönen her önbellek isabetinde `claim: ""` geliyor (aynı soru iki kez
 *    soruldu, ikinci yanıtta üç atıfın üçü de boştu). Önbellek bu ürünün
 *    çevrimdışı planı; tam da gösterime en çok ihtiyaç duyulan turda kaybolan
 *    bir alanın üstüne kart tasarlanmaz.
 * 2. **Çevrimdışı yığında alan, alıntının kopyası.** LLM anahtarı yokken devreye
 *    giren sahte üreteç `claim`'i chunk metninin ilk 90 karakteri olarak
 *    üretiyor (`generation/fake.py::_summarize`). Ölçüldü: dönen üç `claim`'in
 *    üçü de `snippet`'in birebir ön eki. Göstermek, aynı cümleyi tek kartta iki
 *    kez, ikincisini de yarıda kesilmiş hâlde yazmak olurdu.
 * 3. **Kartın otoritesi "içinde model metni yok"tan geliyor.** Dosya adı ve
 *    konum chunk metadata'sından üretilir (Anayasa I), alıntı chunk'tan kesilir.
 *    Modelin kendi cümlesi zaten kartın ÜSTÜNDE duruyor: cevabın kendisi. Aynı
 *    kutuya bir model cümlesi daha koymak, ürünün sattığı sınırı bulanıklaştırır.
 *
 * Karar değişirse (gerçek LLM'de `claim` anlamlı bir cümledir) iki şart:
 * `_store_cache` claim'i yazmalı ve boş `claim` hiçbir şey çizmemeli.
 */
export function citationSource(citation: Citation): {
  fileName: string;
  location: string;
  quote: string;
} {
  return {
    fileName: citation.file_name,
    // Konum sunucudan "Sayfa 7" / "Slayt 3" olarak gelir; arayüz biçimlendirmez.
    location: citation.location,
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
  | { kind: "answer"; id: string; text: string; citations: Citation[]; cached: boolean }
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
        cached: message.cached,
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
