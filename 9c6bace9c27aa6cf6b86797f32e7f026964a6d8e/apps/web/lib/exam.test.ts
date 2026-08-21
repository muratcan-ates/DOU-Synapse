/**
 * Sınav mantığının testleri — `bun test lib/`, ek bağımlılık yok.
 *
 * Buradaki kuralların hepsi sessizce bozulabilir: bozuk bir payload ekranı
 * çökertse öğrenci sınavın ortasında kalır; `graded: false` gelen bir cevaba
 * "0 puan" yazılsa kimse fark etmez, çünkü ekran yine çalışıyor görünür.
 * Testin yakaladığı hata sınıfı bu — "çalışıyor ama yanlış şeyi söylüyor".
 *
 * Beklenen gövdeler uydurulmadı; canlı :8010'dan gözlenen yanıtlardan alındı
 * (bkz. `lib/exam.ts` başlığındaki gözlem kaydı).
 */

import { describe, expect, test } from "bun:test";
import { ApiError } from "./api";
import {
  ANSWER_MAX_LENGTH,
  answerVerdict,
  canSubmitAnswer,
  describeQuestion,
  describeSolution,
  examSessionKey,
  EXAM_MODE,
  formatClock,
  formatScore,
  HINT_MAX_LEVEL,
  isClosed,
  isEmptyPool,
  isLastMinute,
  nextHintLevel,
  shouldPoll,
  shownQuestions,
  showsHints,
  sourceInfo,
  tickRemaining,
  timeIsUp,
  timeNotice,
  VERDICT_LABEL,
} from "./exam";
import type { AnswerFeedback, ExamQuestion, ExamSession } from "./types";

const session = (overrides: Partial<ExamSession> = {}): ExamSession => ({
  id: "e1",
  course_id: "c1",
  mode: "practice",
  started_at: "2026-08-09T12:09:03Z",
  expires_at: null,
  remaining_seconds: null,
  expired: false,
  finished_at: null,
  score: null,
  question_count: 1,
  answered_count: 0,
  ...overrides,
});

const question = (overrides: Partial<ExamQuestion> = {}): ExamQuestion => ({
  id: "q1",
  type: "mcq",
  payload: {
    stem: "Mutex ile ikili semafor arasındaki temel fark hangisidir?",
    options: [
      { key: "A", text: "Mutex sahiplik zorlar; kilidi alan thread açar." },
      { key: "B", text: "İkili semafor yalnız çekirdek modunda çalışır." },
    ],
  },
  answered: false,
  ...overrides,
});

const feedback = (overrides: Partial<AnswerFeedback> = {}): AnswerFeedback => ({
  question_id: "q1",
  graded: true,
  ...overrides,
});

// ---------------------------------------------------------------------------

describe("süre — karar sunucunun, sayaç yalnız görsel", () => {
  test("süresiz oturumda sayaç hiç kurulmaz", () => {
    expect(tickRemaining(null)).toBeNull();
    expect(timeNotice(null)).toBe("");
    expect(isLastMinute(null)).toBe(false);
  });

  test("sayaç sıfırın altına inmez", () => {
    expect(tickRemaining(1)).toBe(0);
    expect(tickRemaining(0)).toBe(0);
  });

  test("saat biçimi dakikayı kırpmaz", () => {
    expect(formatClock(1200)).toBe("20:00");
    expect(formatClock(65)).toBe("1:05");
    expect(formatClock(9)).toBe("0:09");
    expect(formatClock(5400)).toBe("90:00");
    expect(formatClock(-3)).toBe("0:00");
  });

  test("duyuru yalnız eşiklerde değişir — sayaç ekran okuyucuyu boğmaz", () => {
    // Eşikler arasında metin AYNI kalmalı: canlı bölge aynı metni yeniden okumaz.
    expect(timeNotice(1200)).toBe("");
    expect(timeNotice(301)).toBe("");
    expect(timeNotice(300)).toBe("5 dakika kaldı.");
    expect(timeNotice(299)).toBe("5 dakika kaldı.");
    expect(timeNotice(61)).toBe("5 dakika kaldı.");
    expect(timeNotice(60)).toBe("1 dakika kaldı.");
    expect(timeNotice(31)).toBe("1 dakika kaldı.");
    expect(timeNotice(30)).toBe("30 saniye kaldı.");
    expect(timeNotice(1)).toBe("30 saniye kaldı.");
    expect(timeNotice(0)).toBe("Süre doldu.");
  });

  test("20 dakikalık sınavda dörtten fazla duyuru üretilmez", () => {
    const spoken = new Set<string>();
    for (let s = 1200; s >= 0; s -= 1) {
      const notice = timeNotice(s);
      if (notice !== "") spoken.add(notice);
    }
    expect(spoken.size).toBe(4);
  });

  test("son dakika eşiği", () => {
    expect(isLastMinute(61)).toBe(false);
    expect(isLastMinute(60)).toBe(true);
    expect(isLastMinute(0)).toBe(true);
  });

  test("sunucu 'doldu' derse yerel sayaç ne gösterirse göstersin kapanır", () => {
    expect(timeIsUp(session({ expired: true, remaining_seconds: 5 }), 5)).toBe(true);
  });

  test("yerel sayaç sıfırlandıysa sunucunun teyidi beklenmez", () => {
    expect(timeIsUp(session({ mode: "exam", remaining_seconds: 3 }), 0)).toBe(true);
  });

  test("süresiz oturum kendiliğinden kapanmaz", () => {
    expect(timeIsUp(session(), null)).toBe(false);
    expect(isClosed(session(), null)).toBe(false);
  });

  test("bitmiş oturum kapalıdır", () => {
    expect(isClosed(session({ finished_at: "2026-08-09T12:09:37Z" }), null)).toBe(true);
  });
});

describe("polling — durdurulmayan yoklama kusurdur", () => {
  test("süresiz (alıştırma) oturum yoklanmaz", () => {
    expect(shouldPoll(session({ remaining_seconds: null }))).toBe(false);
  });

  test("süreli ve açık oturum yoklanır", () => {
    expect(shouldPoll(session({ mode: "exam", remaining_seconds: 1200 }))).toBe(true);
  });

  test("süresi dolmuş oturum yoklanmaz", () => {
    expect(
      shouldPoll(session({ mode: "exam", remaining_seconds: 0, expired: true })),
    ).toBe(false);
  });

  test("bitirilmiş oturum yoklanmaz", () => {
    expect(
      shouldPoll(
        session({ mode: "exam", remaining_seconds: 900, finished_at: "2026-08-09T12:20:00Z" }),
      ),
    ).toBe(false);
  });
});

describe("payload daraltma — tanınmayan soru ekranı çökertmez", () => {
  test("mcq: kök ve şıklar", () => {
    const view = describeQuestion(question());
    expect(view.kind).toBe("mcq");
    if (view.kind !== "mcq") throw new Error("daraltma başarısız");
    expect(view.choices).toEqual([
      { key: "A", text: "Mutex sahiplik zorlar; kilidi alan thread açar." },
      { key: "B", text: "İkili semafor yalnız çekirdek modunda çalışır." },
    ]);
  });

  test("mcq: şıksız soru gösterilmez — körlemesine cevap istenmez", () => {
    expect(describeQuestion(question({ payload: { stem: "Soru?" } })).kind).toBe("unsupported");
    expect(
      describeQuestion(question({ payload: { stem: "Soru?", options: [] } })).kind,
    ).toBe("unsupported");
  });

  test("mcq: şıkkın metni eksikse soru bütünüyle düşer", () => {
    const broken = question({
      payload: { stem: "Soru?", options: [{ key: "A", text: "Tamam" }, { key: "B" }] },
    });
    expect(describeQuestion(broken).kind).toBe("unsupported");
  });

  test("open: short_answer tek satır, essay çok satır", () => {
    const short = describeQuestion(
      question({ type: "open", payload: { prompt: "Paylaşılan alan nedir?", format: "short_answer" } }),
    );
    expect(short).toEqual({ kind: "text", prompt: "Paylaşılan alan nedir?", multiline: false });

    const essay = describeQuestion(
      question({ type: "open", payload: { prompt: "Neden kilitlenir?", format: "essay" } }),
    );
    expect(essay).toEqual({ kind: "text", prompt: "Neden kilitlenir?", multiline: true });
  });

  test("open: biçim eksikse çok satırlı kutuya düşülür, soru yine gösterilir", () => {
    const view = describeQuestion(question({ type: "open", payload: { prompt: "Açıklayın." } }));
    expect(view).toEqual({ kind: "text", prompt: "Açıklayın.", multiline: true });
  });

  test("code_trace / bug_hunt: kod gövdesi taşınır", () => {
    const view = describeQuestion(
      question({
        type: "bug_hunt",
        payload: { prompt: "Hatayı bulun.", code: "with self._mutex:\n    ...", language: "python" },
      }),
    );
    expect(view).toEqual({
      kind: "code",
      prompt: "Hatayı bulun.",
      code: "with self._mutex:\n    ...",
      language: "python",
    });
  });

  test("kod sorusu kodsuz gösterilmez", () => {
    expect(
      describeQuestion(question({ type: "code_trace", payload: { prompt: "Çıktı nedir?" } })).kind,
    ).toBe("unsupported");
  });

  test("dil etiketi eksik olabilir — soru yine gösterilir", () => {
    const view = describeQuestion(
      question({ type: "code_trace", payload: { prompt: "Çıktı?", code: "print(1)" } }),
    );
    expect(view).toEqual({ kind: "code", prompt: "Çıktı?", code: "print(1)", language: "" });
  });

  test("sözleşmede olmayan tip: atlanır, atılmaz", () => {
    const alien = { id: "q9", type: "matching", payload: { prompt: "x" }, answered: false };
    expect(describeQuestion(alien as unknown as ExamQuestion).kind).toBe("unsupported");
  });

  test("payload hiç yoksa çökmez", () => {
    const empty = { id: "q9", type: "mcq", answered: false };
    expect(describeQuestion(empty as unknown as ExamQuestion).kind).toBe("unsupported");
  });

  test("soru listesi opsiyoneldir; yokluğu boş listedir", () => {
    expect(shownQuestions(session())).toEqual([]);
    const q = question();
    expect(shownQuestions(session({ questions: [q] }))).toEqual([q]);
  });
});

describe("cevap gönderimi — beş kapı", () => {
  const base = { session: session(), question: question(), localRemaining: null };

  test("dolu taslak gönderilebilir", () => {
    expect(canSubmitAnswer({ ...base, draft: "A" })).toBe(true);
  });

  test("boş ya da yalnız boşluk gönderilemez", () => {
    expect(canSubmitAnswer({ ...base, draft: "" })).toBe(false);
    expect(canSubmitAnswer({ ...base, draft: "   \n " })).toBe(false);
  });

  test("sunucu sınırını aşan cevap gönderilmez", () => {
    expect(canSubmitAnswer({ ...base, draft: "a".repeat(ANSWER_MAX_LENGTH) })).toBe(true);
    expect(canSubmitAnswer({ ...base, draft: "a".repeat(ANSWER_MAX_LENGTH + 1) })).toBe(false);
  });

  test("cevaplanmış soruya ikinci deneme yok (sunucu 409 verir)", () => {
    expect(canSubmitAnswer({ ...base, question: question({ answered: true }), draft: "A" })).toBe(
      false,
    );
  });

  test("süresi dolmuş oturumda cevap gönderilemez", () => {
    expect(
      canSubmitAnswer({
        ...base,
        session: session({ mode: "exam", remaining_seconds: 0, expired: true }),
        localRemaining: 0,
        draft: "A",
      }),
    ).toBe(false);
  });

  test("bitirilmiş oturumda cevap gönderilemez", () => {
    expect(
      canSubmitAnswer({
        ...base,
        session: session({ finished_at: "2026-08-09T12:09:37Z" }),
        draft: "A",
      }),
    ).toBe(false);
  });
});

describe("ipucu — mod farkı yüzeyde", () => {
  test("sınav modunda ipucu yüzeyi hiç çizilmez", () => {
    expect(showsHints("exam")).toBe(false);
    expect(showsHints("practice")).toBe(true);
  });

  test("merdiven sonunda düğme kalmaz", () => {
    expect(nextHintLevel(0)).toBe(1);
    expect(nextHintLevel(HINT_MAX_LEVEL - 1)).toBe(HINT_MAX_LEVEL);
    expect(nextHintLevel(HINT_MAX_LEVEL)).toBeNull();
  });
});

describe("geri bildirim — üç durum birbirine karışmaz", () => {
  test("değerlendirilemeyen cevap 'yanlış' değildir", () => {
    const ungraded = feedback({
      graded: false,
      is_correct: null,
      score: null,
      message: "Bu cevabın değerlendirmesi tamamlanamadı.",
    });
    expect(answerVerdict(ungraded)).toBe("ungraded");
    expect(formatScore(ungraded.score)).toBeNull();
  });

  test("sınav modunda puan gizlenir; bu da 'yanlış' değildir", () => {
    // Canlı gövde: graded true, is_correct null, score null, solution null.
    expect(answerVerdict(feedback({ graded: true, is_correct: null, score: null }))).toBe(
      "recorded",
    );
  });

  test("puanlanan cevap doğru/yanlış ayrımını korur", () => {
    expect(answerVerdict(feedback({ is_correct: true, score: 100 }))).toBe("correct");
    expect(answerVerdict(feedback({ is_correct: false, score: 0 }))).toBe("incorrect");
  });

  test("yanlış cevap danger tonunda gösterilmez — kırmızı hata rengi değildir", () => {
    expect(VERDICT_LABEL.incorrect.tone).toBe("warning");
    expect(VERDICT_LABEL.ungraded.tone).toBe("neutral");
    expect(VERDICT_LABEL.recorded.tone).toBe("neutral");
    expect(VERDICT_LABEL.correct.tone).toBe("success");
  });

  test("her sonucun metin etiketi vardır — renk tek başına bilgi taşımaz", () => {
    for (const spec of Object.values(VERDICT_LABEL)) {
      expect(spec.label.trim().length).toBeGreaterThan(0);
    }
  });
});

describe("puan — yoksa uydurulmaz", () => {
  test("puan yokluğu sıfıra çevrilmez", () => {
    expect(formatScore(null)).toBeNull();
    expect(formatScore(undefined)).toBeNull();
    expect(formatScore(Number.NaN)).toBeNull();
  });

  test("tam sayı ondalıksız, kesir tek basamak", () => {
    expect(formatScore(0)).toBe("0 / 100");
    expect(formatScore(50)).toBe("50 / 100");
    expect(formatScore(66.66)).toBe("66.7 / 100");
  });
});

describe("çözüm — bug_hunt'ın cevap anahtarı nesnedir", () => {
  test("metin cevap anahtarı ve açıklama", () => {
    expect(
      describeSolution({
        answer_key: "A",
        explanation: "Mutex sahiplidir: kilitleyen thread açar.",
      }),
    ).toEqual([
      { label: "Cevap anahtarı", value: "A" },
      { label: "Açıklama", value: "Mutex sahiplidir: kilitleyen thread açar." },
    ]);
  });

  test("nesne cevap anahtarı satırlara açılır, '[object Object]' basılmaz", () => {
    const lines = describeSolution({
      answer_key: { line: 3, bug_type: "kilit sırası hatası", fix_summary: "Önce full alınmalı." },
    });
    expect(lines).toEqual([
      { label: "Hatalı satır", value: "3" },
      { label: "Hata türü", value: "kilit sırası hatası" },
      { label: "Düzeltme", value: "Önce full alınmalı." },
    ]);
    expect(lines.some((line) => line.value.includes("object Object"))).toBe(false);
  });

  test("beklenen noktalar tek tek listelenir, boşlar düşer", () => {
    expect(
      describeSolution({ answer_key: "x", key_points: ["Üretici bloke olur", "", 7] }),
    ).toEqual([
      { label: "Cevap anahtarı", value: "x" },
      { label: "Beklenen nokta", value: "Üretici bloke olur" },
    ]);
  });

  test("rubrik ağırlıkları gösterilmez — olmayan puan kırılımı ima edilmez", () => {
    const lines = describeSolution({
      answer_key: "x",
      rubric: [{ point: "Kilit sırası", weight: 60 }],
    });
    expect(lines).toEqual([{ label: "Cevap anahtarı", value: "x" }]);
  });

  test("çözüm yoksa (sınav sürerken) satır üretilmez", () => {
    expect(describeSolution(null)).toEqual([]);
    expect(describeSolution(undefined)).toEqual([]);
    expect(describeSolution({})).toEqual([]);
  });
});

describe("kaynak — dosya adı ve konum taşınır, üretilmez", () => {
  test("SourceRef olduğu gibi karta geçer", () => {
    expect(
      sourceInfo({
        chunk_id: "93c8e336",
        file_name: "04-synchronization.pdf",
        location: "Sayfa 3",
        snippet: "Mutex sahiplikli bir kilittir…",
      }),
    ).toEqual({
      fileName: "04-synchronization.pdf",
      location: "Sayfa 3",
      quote: "Mutex sahiplikli bir kilittir…",
    });
  });
});

describe("boş havuz — arıza değil", () => {
  test("409 conflict boş havuzdur", () => {
    expect(isEmptyPool(new ApiError("Bu derste henüz onaylanmış soru yok.", "conflict", 409))).toBe(
      true,
    );
  });

  test("diğer hatalar hata olarak kalır", () => {
    expect(isEmptyPool(new ApiError("Ders bulunamadı.", "not_found", 404))).toBe(false);
    expect(isEmptyPool(new ApiError("Yetkiniz yok.", "permission_denied", 403))).toBe(false);
    expect(isEmptyPool(new TypeError("ağ koptu"))).toBe(false);
    expect(isEmptyPool(null)).toBe(false);
  });
});

describe("oturum kimliği ders başına saklanır", () => {
  test("iki dersin anahtarı çakışmaz", () => {
    expect(examSessionKey("c1")).not.toBe(examSessionKey("c2"));
    expect(examSessionKey("c1")).toContain("c1");
  });
});

describe("mod açıklamaları", () => {
  test("süre sayıyla iddia edilmez — sayıyı sunucu verir", () => {
    for (const spec of Object.values(EXAM_MODE)) {
      expect(spec.description).not.toMatch(/\d/);
      expect(spec.label.trim().length).toBeGreaterThan(0);
    }
  });
});
