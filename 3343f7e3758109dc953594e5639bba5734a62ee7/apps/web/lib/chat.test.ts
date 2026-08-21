/**
 * Sohbet mantığının testleri — `bun test lib/`, ek bağımlılık yok.
 *
 * Neden bu dosya var: buradaki kuralların hepsi sessizce bozulabilir. QA modunda
 * `student_attempt` gönderilse ekran yine çalışır, sunucu 422 döndürene kadar
 * kimse fark etmez; Sokratik devam turunda `question` yerine denemenin metni
 * gönderilse ekran yine çalışır, sadece merdiven ikinci turda çöker. Testin
 * yakaladığı hata sınıfı bu: "çalışıyor ama yanlış şeyi yapıyor".
 */

import { describe, expect, test } from "bun:test";
import {
  ABSTENTION_LABEL,
  buildChatRequest,
  CACHED_ANSWER_NOTE,
  canSubmitDraft,
  CHAT_MODE_LABEL,
  CHAT_UI_MODES,
  citationSource,
  fromAnswer,
  fromHistory,
  isAbstention,
  isSocraticFollowUp,
  openSessionKey,
  QUESTION_MAX_LENGTH,
  QUESTION_MIN_LENGTH,
  sessionStageLabel,
  SOCRATIC_STAGES,
  SOCRATIC_STAGE_LABEL,
  stageIndex,
  stageLabel,
  toBlocks,
  userMessage,
  type TranscriptMessage,
} from "./chat";
import type { ChatAnswer, Citation, ChatMessage, SocraticStage } from "./types";

const citation = (overrides: Partial<Citation> = {}): Citation => ({
  chunk_id: "c1",
  claim: "model metni — gösterilmez",
  file_name: "05-deadlock-demo.pdf",
  location: "Sayfa 12",
  snippet: "Deadlock için dört Coffman koşulunun aynı anda sağlanması gerekir.",
  ...overrides,
});

const assistant = (
  id: string,
  overrides: Partial<TranscriptMessage> = {},
): TranscriptMessage => ({
  id,
  role: "assistant",
  content: "cevap",
  status: "answered",
  citations: [citation()],
  socraticStage: null,
  cached: false,
  ...overrides,
  feedback: overrides.feedback ?? null,
});

// ---------------------------------------------------------------------------

describe("Sokratik kademeler — sözleşme beş kademeli", () => {
  test("beş kademe, sunucudaki sırayla", () => {
    expect([...SOCRATIC_STAGES]).toEqual([
      "diagnose",
      "nudge",
      "concept_hint",
      "similar_example",
      "explain_with_source",
    ]);
  });

  test("her kademenin Türkçe karşılığı var", () => {
    for (const stage of SOCRATIC_STAGES) {
      expect(SOCRATIC_STAGE_LABEL[stage].length).toBeGreaterThan(0);
    }
  });

  test("etiketlerde büyük harf dönüşümü yok (Türkçe i/İ kuralı)", () => {
    const labels = [
      ...Object.values(SOCRATIC_STAGE_LABEL),
      ...Object.values(CHAT_MODE_LABEL),
      ...Object.values(ABSTENTION_LABEL),
    ];
    for (const label of labels) expect(label).not.toBe(label.toUpperCase());
  });

  test("kademe sırası göstergeye doğru yansır", () => {
    expect(stageIndex("diagnose")).toBe(0);
    expect(stageIndex("explain_with_source")).toBe(4);
    // Kademesiz ipucunda hiçbir nokta dolmaz.
    expect(stageIndex(null)).toBe(-1);
  });

  test("kademesi bildirilmeyen ipucu da etiketsiz kalmaz", () => {
    expect(stageLabel(null).length).toBeGreaterThan(0);
    expect(stageLabel("concept_hint")).toBe("Kavram ipucu");
  });
});

describe("abstention — üç durum ayrı ayrı adlandırılır", () => {
  test("üç durumun da başlığı var ve birbirinden farklı", () => {
    expect(ABSTENTION_LABEL.insufficient_context).not.toBe(ABSTENTION_LABEL.out_of_scope);
    expect(ABSTENTION_LABEL.budget_exhausted).not.toBe(ABSTENTION_LABEL.out_of_scope);
    expect(ABSTENTION_LABEL.insufficient_context.length).toBeGreaterThan(0);
    expect(ABSTENTION_LABEL.out_of_scope.length).toBeGreaterThan(0);
    expect(ABSTENTION_LABEL.budget_exhausted.length).toBeGreaterThan(0);
  });

  test("başlıklarda ünlem yok — abstention hata gibi görünmez", () => {
    for (const label of Object.values(ABSTENTION_LABEL)) {
      expect(label).not.toContain("!");
    }
  });

  test("answered abstention değildir", () => {
    expect(isAbstention("answered")).toBe(false);
    expect(isAbstention(null)).toBe(false);
    expect(isAbstention("insufficient_context")).toBe(true);
    expect(isAbstention("out_of_scope")).toBe(true);
    expect(isAbstention("budget_exhausted")).toBe(true);
  });
});

describe("buildChatRequest — sözleşme extra='forbid'", () => {
  const ALLOWED = ["question", "mode", "session_id", "student_attempt"];

  test("QA ilk tur: yalnız soru ve mod", () => {
    const body = buildChatRequest({
      mode: "qa",
      draft: "  Deadlock koşulları neler?  ",
      sessionId: null,
      openingQuestion: null,
    });
    expect(body).toEqual({ question: "Deadlock koşulları neler?", mode: "qa" });
  });

  test("QA devam turu: student_attempt HİÇ gönderilmez", () => {
    const body = buildChatRequest({
      mode: "qa",
      draft: "Peki circular wait nasıl kırılır?",
      sessionId: "s1",
      openingQuestion: "Deadlock koşulları neler?",
    });
    expect(body.student_attempt).toBeUndefined();
    expect(body.question).toBe("Peki circular wait nasıl kırılır?");
    expect(body.session_id).toBe("s1");
  });

  test("Sokratik ilk tur: student_attempt gönderilmez, soru öğrencinin sorusudur", () => {
    const body = buildChatRequest({
      mode: "socratic",
      draft: "FCFS ortalama bekleme süresi nasıl bulunur?",
      sessionId: null,
      openingQuestion: null,
    });
    expect(body).toEqual({
      question: "FCFS ortalama bekleme süresi nasıl bulunur?",
      mode: "socratic",
    });
  });

  test("Sokratik devam turu: soru AÇILIŞ sorusudur, yeni metin student_attempt'e gider", () => {
    // Bu testin koruduğu şey: arama açılış sorusuna bağlı kalmalı. "hı" ile
    // arama yapılırsa hiçbir parça bulunmaz ve merdiven kanıt eşiğinde çöker.
    const body = buildChatRequest({
      mode: "socratic",
      draft: "hı",
      sessionId: "s1",
      openingQuestion: "FCFS ortalama bekleme süresi nasıl bulunur?",
    });
    expect(body.question).toBe("FCFS ortalama bekleme süresi nasıl bulunur?");
    expect(body.student_attempt).toBe("hı");
    expect(body.session_id).toBe("s1");
    expect(body.mode).toBe("socratic");
  });

  test("gövdede sözleşme dışı alan yok", () => {
    const bodies = [
      buildChatRequest({ mode: "qa", draft: "soru", sessionId: null, openingQuestion: null }),
      buildChatRequest({
        mode: "socratic",
        draft: "deneme",
        sessionId: "s1",
        openingQuestion: "açılış sorusu",
      }),
    ];
    for (const body of bodies) {
      for (const key of Object.keys(body)) expect(ALLOWED).toContain(key);
    }
  });

  test("oturum yokken devam turu sayılmaz", () => {
    expect(
      isSocraticFollowUp({ mode: "socratic", sessionId: null, openingQuestion: "soru" }),
    ).toBe(false);
    expect(
      isSocraticFollowUp({ mode: "socratic", sessionId: "s1", openingQuestion: null }),
    ).toBe(false);
    expect(
      isSocraticFollowUp({ mode: "qa", sessionId: "s1", openingQuestion: "soru" }),
    ).toBe(false);
  });
});

describe("canSubmitDraft — 422'yi baştan önle", () => {
  test("boş girdi gönderilmez", () => {
    expect(canSubmitDraft("   ", false)).toBe(false);
    expect(canSubmitDraft("   ", true)).toBe(false);
  });

  test("yeni soru alt sınırın altındaysa gönderilmez", () => {
    expect(canSubmitDraft("ab", false)).toBe(false);
    expect(canSubmitDraft("abc", false)).toBe(true);
    expect(QUESTION_MIN_LENGTH).toBe(3);
  });

  test("Sokratik denemede alt sınır yok — kısa deneme geçerlidir", () => {
    expect(canSubmitDraft("hı", true)).toBe(true);
  });

  test("üst sınır aşılırsa gönderilmez", () => {
    expect(canSubmitDraft("a".repeat(QUESTION_MAX_LENGTH), false)).toBe(true);
    expect(canSubmitDraft("a".repeat(QUESTION_MAX_LENGTH + 1), false)).toBe(false);
    expect(QUESTION_MAX_LENGTH).toBe(2000);
  });
});

describe("citationSource — alıntı chunk'tan birebir gelir", () => {
  test("gösterilen metin snippet'tir, model metni (claim) değil", () => {
    const source = citationSource(citation());
    expect(source.quote).toBe(
      "Deadlock için dört Coffman koşulunun aynı anda sağlanması gerekir.",
    );
    expect(source.quote).not.toBe("model metni — gösterilmez");
  });

  test("konum sunucudan geldiği gibi taşınır — arayüz biçimlendirmez", () => {
    expect(citationSource(citation({ location: "Slayt 3" })).location).toBe("Slayt 3");
    expect(citationSource(citation()).fileName).toBe("05-deadlock-demo.pdf");
  });

  test("karta model metni sızmaz: dönen nesnede claim'e yer yok", () => {
    // Kararın gerekçesi `citationSource`'un başında. Bu test kararı sabitler:
    // biri `claim`'i karta eklemek isterse önce buradaki gerekçeyi okumak
    // zorunda kalır. Alan adı bile taşınmıyor — kart yalnız chunk'tan üretilir.
    expect(Object.keys(citationSource(citation())).sort()).toEqual([
      "fileName",
      "location",
      "quote",
    ]);
  });
});

describe("toBlocks — QA dökümü", () => {
  test("soru ve kaynaklı cevap ayrı bloklar", () => {
    const blocks = toBlocks(
      [userMessage("u1", "Deadlock koşulları?"), assistant("a1")],
      { mode: "qa" },
    );
    expect(blocks.map((b) => b.kind)).toEqual(["question", "answer"]);
  });

  test("abstention hata değil, kendi bloğu", () => {
    const blocks = toBlocks(
      [
        userMessage("u1", "Bugünkü dolar kuru?"),
        assistant("a1", {
          status: "out_of_scope",
          citations: [],
          content: "Bu konu dersin kapsamı dışında görünüyor.",
        }),
      ],
      { mode: "qa" },
    );
    expect(blocks[1]).toEqual({
      kind: "abstention",
      id: "a1",
      text: "Bu konu dersin kapsamı dışında görünüyor.",
      status: "out_of_scope",
    });
  });

  test("günlük bütçe sınırı hata bloğuna dönüşmez", () => {
    const blocks = toBlocks(
      [
        userMessage("u1", "Deadlock nedir?"),
        assistant("a1", {
          status: "budget_exhausted",
          citations: [],
          content: "Bu dersin günlük sohbet AI bütçesi doldu.",
        }),
      ],
      { mode: "qa" },
    );
    expect(blocks[1]).toEqual({
      kind: "abstention",
      id: "a1",
      text: "Bu dersin günlük sohbet AI bütçesi doldu.",
      status: "budget_exhausted",
    });
  });

  test("QA modunda merdiven kurulmaz", () => {
    const blocks = toBlocks(
      [userMessage("u1", "soru"), assistant("a1", { socraticStage: "nudge" })],
      { mode: "qa" },
    );
    expect(blocks.map((b) => b.kind)).toEqual(["question", "answer"]);
  });

  test("cevabı gelmemiş soru dökümde durur", () => {
    const blocks = toBlocks([], { mode: "qa", pending: "uçuştaki soru" });
    expect(blocks).toEqual([{ kind: "question", id: "pending", text: "uçuştaki soru" }]);
  });

  test("boş pending blok üretmez", () => {
    expect(toBlocks([], { mode: "qa", pending: "   " })).toEqual([]);
    expect(toBlocks([], { mode: "qa", pending: null })).toEqual([]);
  });
});

describe("toBlocks — Sokratik merdiven", () => {
  const stage = (name: SocraticStage) => ({ socraticStage: name });

  const transcript: TranscriptMessage[] = [
    userMessage("u1", "FCFS bekleme süresi nasıl bulunur?"),
    assistant("a1", { ...stage("diagnose"), content: "Neyi biliyorsun?" }),
    userMessage("u2", "hı"),
    assistant("a2", { ...stage("nudge"), content: "Varış sırasını yaz." }),
  ];

  test("kademeler TEK merdivende birikir, silinmez", () => {
    const blocks = toBlocks(transcript, { mode: "socratic" });
    expect(blocks.map((b) => b.kind)).toEqual(["question", "ladder"]);
    const ladder = blocks[1];
    if (ladder.kind !== "ladder") throw new Error("merdiven bekleniyordu");
    expect(ladder.rungs.map((r) => r.stage)).toEqual(["diagnose", "nudge"]);
  });

  test("açılış sorusu balonda kalır, sonraki denemeler kademeye iliştirilir", () => {
    const blocks = toBlocks(transcript, { mode: "socratic" });
    expect(blocks[0]).toEqual({
      kind: "question",
      id: "u1",
      text: "FCFS bekleme süresi nasıl bulunur?",
    });
    const ladder = blocks[1];
    if (ladder.kind !== "ladder") throw new Error("merdiven bekleniyordu");
    expect(ladder.rungs[0].attempt).toBeNull();
    expect(ladder.rungs[1].attempt).toBe("hı");
  });

  test("her kademe kaynağını taşır", () => {
    const blocks = toBlocks(transcript, { mode: "socratic" });
    const ladder = blocks[1];
    if (ladder.kind !== "ladder") throw new Error("merdiven bekleniyordu");
    for (const rung of ladder.rungs) {
      expect(rung.source.fileName.length).toBeGreaterThan(0);
      expect(rung.source.location.length).toBeGreaterThan(0);
    }
  });

  test("kaynaksız ipucu kademe sayılmaz (Anayasa I)", () => {
    const blocks = toBlocks(
      [
        userMessage("u1", "soru"),
        assistant("a1", { socraticStage: "nudge", citations: [] }),
      ],
      { mode: "socratic" },
    );
    expect(blocks.map((b) => b.kind)).toEqual(["question", "answer"]);
  });

  test("abstention merdiveni keser ama önceki kademeler ekranda kalır", () => {
    const blocks = toBlocks(
      [
        ...transcript,
        userMessage("u3", "bilmiyorum"),
        assistant("a3", {
          status: "insufficient_context",
          citations: [],
          socraticStage: "concept_hint",
          content: "Güvenle cevaplayamıyorum.",
        }),
        userMessage("u4", "peki şöyle mi"),
        assistant("a4", { ...stage("concept_hint"), content: "Bekleme süresi nedir?" }),
      ],
      { mode: "socratic" },
    );
    expect(blocks.map((b) => b.kind)).toEqual([
      "question",
      "ladder",
      "question",
      "abstention",
      "question",
      "ladder",
    ]);
    const first = blocks[1];
    if (first.kind !== "ladder") throw new Error("merdiven bekleniyordu");
    expect(first.rungs).toHaveLength(2);
  });
});

describe("canlı yanıt ile geçmiş aynı biçime iner", () => {
  const answer: ChatAnswer = {
    session_id: "s1",
    message_id: "m1",
    status: "answered",
    mode: "socratic",
    answer: "Varış sırasını yaz.",
    citations: [citation()],
    // Sunucuda doğrulandı: ipucu metni cevabın kendisidir, ayrı bir metin değil.
    hints: [
      {
        text: "Varış sırasını yaz.",
        chunk_id: "c1",
        file_name: "05-deadlock-demo.pdf",
        location: "Sayfa 12",
        stage: "nudge",
      },
    ],
    socratic_stage: "nudge",
    cached: false,
  };

  test("fromAnswer asistan satırını kurar", () => {
    expect(fromAnswer(answer)).toEqual({
      id: "m1",
      role: "assistant",
      content: "Varış sırasını yaz.",
      status: "answered",
      citations: [citation()],
      socraticStage: "nudge",
      cached: false,
      feedback: null,
    });
  });

  test("canlı yanıt ve geçmiş kaydı aynı merdiveni üretir", () => {
    const history: ChatMessage[] = [
      {
        id: "u1",
        role: "user",
        content: "soru",
        citations: [],
        status: null,
        socratic_stage: null,
        created_at: "2026-08-09T10:00:00Z",
        feedback: null,
      },
      {
        id: "m1",
        role: "assistant",
        content: "Varış sırasını yaz.",
        citations: [citation()],
        status: "answered",
        socratic_stage: "nudge",
        created_at: "2026-08-09T10:00:01Z",
        feedback: null,
      },
    ];
    const fromServerHistory = toBlocks(fromHistory(history), { mode: "socratic" });
    const fromLiveTurn = toBlocks([userMessage("u1", "soru"), fromAnswer(answer)], {
      mode: "socratic",
    });
    expect(fromLiveTurn).toEqual(fromServerHistory);
  });
});

describe("önbellek işareti — zarftaki `cached` ekrana ulaşır", () => {
  const cachedAnswer: ChatAnswer = {
    session_id: "s1",
    message_id: "m1",
    status: "answered",
    mode: "qa",
    answer: "Context switch maliyetlidir çünkü…",
    citations: [citation()],
    hints: [],
    socratic_stage: null,
    cached: true,
  };

  test("canlı yanıttaki cached satıra taşınır", () => {
    expect(fromAnswer(cachedAnswer).cached).toBe(true);
    expect(fromAnswer({ ...cachedAnswer, cached: false }).cached).toBe(false);
  });

  test("cevap bloğu işareti taşır — ekran zarfı okumadan çizemez", () => {
    const blocks = toBlocks([userMessage("u1", "soru"), fromAnswer(cachedAnswer)], {
      mode: "qa",
    });
    const answerBlock = blocks[1];
    if (answerBlock.kind !== "answer") throw new Error("cevap bloğu bekleniyordu");
    expect(answerBlock.cached).toBe(true);
  });

  test("geçmişten yüklenen tur işaretsizdir — sunucu söylemediğini arayüz söylemez", () => {
    // `GET /chat/sessions/{id}` zarfında `cached` yok. Yokluk "önbellekten
    // gelmedi" demek değil; işaret pozitif bir bildirimdir (Anayasa III).
    const history: ChatMessage[] = [
      {
        id: "m1",
        role: "assistant",
        content: "cevap",
        citations: [citation()],
        status: "answered",
        socratic_stage: null,
        created_at: "2026-08-09T10:00:00Z",
        feedback: null,
      },
    ];
    expect(fromHistory(history)[0].cached).toBe(false);
  });

  test("dipnot metni sakin: ünlem yok, büyük harf dönüşümü yok", () => {
    // Önbellek isabeti kusur değil tasarlanmış davranıştır (Anayasa VII).
    expect(CACHED_ANSWER_NOTE.length).toBeGreaterThan(0);
    expect(CACHED_ANSWER_NOTE).not.toContain("!");
    expect(CACHED_ANSWER_NOTE).not.toBe(CACHED_ANSWER_NOTE.toUpperCase());
  });
});

describe("sessionStageLabel — kademe yalnız Sokratik oturumda görünür", () => {
  test("Sokratik oturum kaldığı kademeyi gösterir", () => {
    // Canlı listede gözlenen biçim: mode "socratic", socratic_stage "nudge".
    expect(sessionStageLabel({ mode: "socratic", socratic_stage: "nudge" })).toBe(
      "Yönlendirme",
    );
    expect(
      sessionStageLabel({ mode: "socratic", socratic_stage: "explain_with_source" }),
    ).toBe("Kaynaklı açıklama");
  });

  test("QA oturumunda kademe yazılmaz", () => {
    expect(sessionStageLabel({ mode: "qa", socratic_stage: null })).toBeNull();
    // Sunucu QA'da kademe döndürmüyor; yine de dönerse listeye sızmaz.
    expect(sessionStageLabel({ mode: "qa", socratic_stage: "nudge" })).toBeNull();
    expect(sessionStageLabel({ mode: "exam", socratic_stage: "nudge" })).toBeNull();
  });

  test("kademesi bilinmeyen Sokratik oturum boş kalır, 'İpucu' yazmaz", () => {
    // `stageLabel(null)` merdivenin içinde "İpucu" der ve orada doğrudur; listede
    // aynı kelime "nerede kaldın" sorusuna cevap vermez, bilinmeyeni biliniyor
    // gibi gösterirdi.
    expect(sessionStageLabel({ mode: "socratic", socratic_stage: null })).toBeNull();
    expect(stageLabel(null)).toBe("İpucu");
  });
});

describe("açık oturum anahtarı ders bazlıdır", () => {
  test("iki ders aynı anahtarı paylaşmaz", () => {
    expect(openSessionKey("a")).not.toBe(openSessionKey("b"));
    expect(openSessionKey("a")).toContain("a");
  });
});

describe("mod sözlüğü", () => {
  test("arayüz yalnız qa ve socratic sunar — sınav modu bu uçta 422 döner", () => {
    expect([...CHAT_UI_MODES]).toEqual(["qa", "socratic"]);
  });

  test("oturum listesindeki her mod adlandırılabilir", () => {
    expect(CHAT_MODE_LABEL.qa.length).toBeGreaterThan(0);
    expect(CHAT_MODE_LABEL.socratic.length).toBeGreaterThan(0);
    expect(CHAT_MODE_LABEL.exam.length).toBeGreaterThan(0);
  });
});
