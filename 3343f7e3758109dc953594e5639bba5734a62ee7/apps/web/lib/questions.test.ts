/**
 * Soru havuzu çekirdeğinin testleri — `bun test lib/` ile koşar.
 *
 * Neden bu dosya var: `payload` backend'de `jsonb`'dir, yani derleyici onu
 * kontrol etmez. Yanlış daraltma tarayıcıda "undefined" yazan bir panel ya da
 * boş bir ekran olarak görünür, tip hatası olarak değil. Buradaki testler bu
 * yüzden iki şeyi birden sabitliyor: doğru payload'ın doğru okunduğunu ve
 * EKSİK payload'ın uydurulmadığını.
 *
 * Örnek payload'lar canlı `GET /courses/{id}/questions` yanıtından alındı
 * (eğitmen kimliğiyle, 9 Ağustos 2026); şekil `app/schemas/assessment.py`
 * içindeki payload modelleriyle birebir.
 */

import { describe, expect, test } from "bun:test";
import {
  buildGenerateRequest,
  countByStatus,
  filterQuestions,
  generationSummary,
  groupReasons,
  nextDraftId,
  parseExampleQuestions,
  toQuestionView,
} from "./questions";
import type { Question, QuestionGeneration, QuestionType } from "./types";

function question(
  id: string,
  type: QuestionType,
  payload: Record<string, unknown>,
  overrides: Partial<Question> = {},
): Question {
  return {
    id,
    course_id: "c1",
    topic_id: "t1",
    type,
    payload,
    status: "draft",
    created_by: "u1",
    reviewed_by: null,
    reviewed_at: null,
    created_at: "2026-08-09T12:00:00+03:00",
    source: null,
    ...overrides,
  };
}

const MCQ_PAYLOAD = {
  stem: "Context switch sırasında çekirdeğin kaydettiği bağlam hangisidir?",
  options: [
    { key: "A", text: "Yalnızca program sayacı" },
    { key: "B", text: "Program sayacı, yazmaç kümesi ve yığın işaretçisi" },
  ],
  answer_key: "B",
  explanation: "Zamanlayıcı bağlamı PCB'ye kaydeder.",
  distractor_sources: { A: "87cc9267-4534-4e8f-a818-7a69ded56c95" },
};

describe("toQuestionView — mcq", () => {
  const view = toQuestionView(question("q1", "mcq", MCQ_PAYLOAD));

  test("soru metni `stem` alanından gelir", () => {
    expect(view.stem).toBe(MCQ_PAYLOAD.stem);
  });

  test("doğru şık `answer_key` ile işaretlenir", () => {
    expect(view.options.map((o) => o.key)).toEqual(["A", "B"]);
    expect(view.options.map((o) => o.correct)).toEqual([false, true]);
    expect(view.correctOptionKey).toBe("B");
  });

  test("mcq'da düz metin cevap anahtarı yoktur; işaret şıkta durur", () => {
    // `answer_key` "B" bir şık anahtarıdır, cevabın kendisi değil. Panelde
    // "Cevap anahtarı: B" yazmak eğitmene hiçbir şey söylemez.
    expect(view.answerKey).toBeNull();
  });

  test("çeldirici kaynakları görünüme SIZMAZ", () => {
    // `distractor_sources` "neden yanlış?" için sunucuda kullanılır; onay
    // ekranında yeri yok ve görünüme taşınırsa er geç ekrana da düşer.
    expect(Object.keys(view)).not.toContain("distractorSources");
  });
});

describe("toQuestionView — open", () => {
  const essay = toQuestionView(
    question("q2", "open", {
      prompt: "Mutex ile semafor farkını açıklayın.",
      answer_key: "Mutex sahiplidir.",
      key_points: ["Sahiplik", "Sayaç"],
      rubric: [{ point: "Sahiplik farkı", weight: 50 }],
      format: "essay",
      accepted_answers: [],
    }),
  );

  test("soru metni `prompt` alanından gelir", () => {
    expect(essay.stem).toBe("Mutex ile semafor farkını açıklayın.");
  });

  test("rubrik ve anahtar noktalar okunur", () => {
    expect(essay.keyPoints).toEqual(["Sahiplik", "Sayaç"]);
    expect(essay.rubric).toEqual([{ point: "Sahiplik farkı", weight: 50 }]);
    expect(essay.answerFormat).toBe("essay");
  });

  test("kısa cevap biçiminde kabul edilen karşılıklar okunur", () => {
    const short = toQuestionView(
      question("q3", "open", {
        prompt: "Sayacı artıran işlem?",
        answer_key: "signal()",
        format: "short_answer",
        accepted_answers: ["signal", "V()", "release()"],
        key_points: [],
        rubric: [],
      }),
    );
    expect(short.answerFormat).toBe("short_answer");
    expect(short.acceptedAnswers).toEqual(["signal", "V()", "release()"]);
  });

  test("tanınmayan `format` değeri null olur, varsayılan UYDURULMAZ", () => {
    const odd = toQuestionView(
      question("q4", "open", { prompt: "Soru?", answer_key: "x", format: "sözlü" }),
    );
    expect(odd.answerFormat).toBeNull();
  });
});

describe("toQuestionView — code_trace ve bug_hunt", () => {
  test("code_trace kodu ve dili taşır", () => {
    const view = toQuestionView(
      question("q5", "code_trace", {
        language: "python",
        code: "print(1)",
        prompt: "Çıktı nedir?",
        answer_key: "1",
      }),
    );
    expect(view.code).toEqual({ language: "python", code: "print(1)" });
    expect(view.answerKey).toBe("1");
  });

  test("bug_hunt cevap anahtarı üç alana ayrılır", () => {
    const view = toQuestionView(
      question("q6", "bug_hunt", {
        language: "python",
        code: "mutex.acquire()",
        prompt: "Hatayı bulun.",
        answer_key: { line: 2, bug_type: "kilit sırası", fix_summary: "Sırayı çevir." },
      }),
    );
    expect(view.bugAnswer).toEqual({
      line: 2,
      bugType: "kilit sırası",
      fixSummary: "Sırayı çevir.",
    });
    // Nesne cevap anahtarı düz metin alanına DÜŞMEZ: "[object Object]" ekrana
    // yazılırsa eğitmen soruyu okumadan onaylar.
    expect(view.answerKey).toBeNull();
  });
});

describe("toQuestionView — eksik payload uydurulmaz", () => {
  test("boş payload'da her alan null ya da boş", () => {
    const view = toQuestionView(question("q7", "mcq", {}));
    expect(view.stem).toBeNull();
    expect(view.options).toEqual([]);
    expect(view.correctOptionKey).toBeNull();
    expect(view.explanation).toBeNull();
  });

  test("bozuk şık öğeleri düşer, geçerliler kalır", () => {
    const view = toQuestionView(
      question("q8", "mcq", {
        stem: "Soru?",
        answer_key: "A",
        options: [{ key: "A", text: "Doğru" }, "çöp", { key: "B" }, { text: "anahtarsız" }],
      }),
    );
    expect(view.options).toEqual([{ key: "A", text: "Doğru", correct: true }]);
  });

  test("boş metin dolu sayılmaz", () => {
    // "" bir cevap anahtarı değildir; boş bir kutu göstermek "cevap anahtarı
    // yok" demekten daha kötüdür.
    const view = toQuestionView(question("q9", "code_trace", { prompt: "  ", code: "" }));
    expect(view.stem).toBeNull();
    expect(view.code).toBeNull();
  });

  test("kaynak yoksa görünümde de yok (boş kart çizilmez)", () => {
    // Eşlemenin kendisi `lib/source.test.ts`te; buradaki iddia null korumasının
    // bu çağrı yerinde durduğu.
    expect(toQuestionView(question("q10", "mcq", {})).source).toBeNull();
    expect(toQuestionView(question("q11", "mcq", {}, { source: undefined })).source).toBeNull();
  });

  test("kaynak varsa karta hazır biçimde taşınır", () => {
    const view = toQuestionView(
      question(
        "q12",
        "mcq",
        {},
        {
          source: {
            chunk_id: "ch1",
            file_name: "01-processes.pdf",
            location: "Sayfa 3",
            snippet: "Context switch gerçekleşir.",
          },
        },
      ),
    );
    expect(view.source).toEqual({
      fileName: "01-processes.pdf",
      location: "Sayfa 3",
      quote: "Context switch gerçekleşir.",
    });
  });
});

describe("countByStatus", () => {
  test("üç durum ayrı ayrı sayılır", () => {
    const pool = [
      question("a", "mcq", {}),
      question("b", "mcq", {}, { status: "approved" }),
      question("c", "mcq", {}, { status: "rejected" }),
      question("d", "mcq", {}, { status: "approved" }),
    ];
    expect(countByStatus(pool)).toEqual({
      draft: 1,
      approved: 2,
      rejected: 1,
      total: 4,
    });
  });

  test("boş havuzda hepsi sıfır", () => {
    expect(countByStatus([])).toEqual({ draft: 0, approved: 0, rejected: 0, total: 0 });
  });
});

describe("filterQuestions", () => {
  const pool = [
    question("a", "mcq", {}, { topic_id: "t1" }),
    question("b", "mcq", {}, { topic_id: "t2", status: "approved" }),
    question("c", "mcq", {}, { topic_id: "t1", status: "approved" }),
  ];

  test("durum süzgeci", () => {
    expect(filterQuestions(pool, "approved", "all").map((q) => q.id)).toEqual(["b", "c"]);
  });

  test("konu süzgeci", () => {
    expect(filterQuestions(pool, "all", "t1").map((q) => q.id)).toEqual(["a", "c"]);
  });

  test("iki süzgeç birlikte VE'lenir", () => {
    expect(filterQuestions(pool, "approved", "t1").map((q) => q.id)).toEqual(["c"]);
  });

  test("'all' hiçbir şey elemez", () => {
    expect(filterQuestions(pool, "all", "all")).toHaveLength(3);
  });
});

describe("nextDraftId", () => {
  const pool = [
    question("a", "mcq", {}, { status: "approved" }),
    question("b", "mcq", {}),
    question("c", "mcq", {}, { status: "rejected" }),
    question("d", "mcq", {}),
  ];

  test("seçili sorudan SONRAKİ taslağı bulur", () => {
    expect(nextDraftId(pool, "b")).toBe("d");
  });

  test("listenin sonuna gelince başa döner", () => {
    expect(nextDraftId(pool, "d")).toBe("b");
  });

  test("kendisi tek taslaksa null döner (dönüp kendini göstermez)", () => {
    const single = [question("a", "mcq", {}, { status: "approved" }), question("b", "mcq", {})];
    expect(nextDraftId(single, "b")).toBeNull();
  });

  test("hiç taslak yoksa null", () => {
    expect(nextDraftId([question("a", "mcq", {}, { status: "approved" })], "a")).toBeNull();
  });
});

describe("groupReasons — tekrar yutulmaz, sayıya çevrilir", () => {
  test("aynı gerekçe tekrarlanınca tek satır + sayı olur", () => {
    // Canlı gövdedeki gerçek şekil: iki deneme de aynı duvara toslar ve
    // sunucu ikisini de ayrı ayrı yazar.
    expect(
      groupReasons(["yanıtta 'questions' dizisi yok", "yanıtta 'questions' dizisi yok"]),
    ).toEqual([{ text: "yanıtta 'questions' dizisi yok", count: 2 }]);
  });

  test("farklı gerekçeler ilk görülme sırasını korur", () => {
    expect(groupReasons(["b", "a", "b", "c"])).toEqual([
      { text: "b", count: 2 },
      { text: "a", count: 1 },
      { text: "c", count: 1 },
    ]);
  });

  test("metin birebir korunur, kısaltılmaz", () => {
    const reason = "kaynak uydurma: source_chunk_id retrieve edilmedi";
    expect(groupReasons([reason])).toEqual([{ text: reason, count: 1 }]);
  });

  test("boş ve boşluktan ibaret gerekçe düşer", () => {
    expect(groupReasons(["", "   ", "gerçek sebep"])).toEqual([
      { text: "gerçek sebep", count: 1 },
    ]);
  });

  test("boş dizi boş dizi kalır", () => {
    expect(groupReasons([])).toEqual([]);
  });
});

describe("generationSummary — üretim muhasebesi gizlenmez", () => {
  test("kısmi tur: dört sayı da cümlede", () => {
    const report: QuestionGeneration = {
      requested: 5,
      returned: 3,
      accepted: 2,
      rejected: 1,
      rejection_reasons: ["kaynak chunk_id retrieve edilmiş kümede yok"],
    };
    const summary = generationSummary(report);
    expect(summary.sentence).toBe(
      "5 soru istendi, 3 soru üretildi, 2 tanesi havuza taslak olarak eklendi, 1 tanesi kaynak doğrulamasından geçemedi.",
    );
    expect(summary.reasons).toEqual([
      { text: "kaynak chunk_id retrieve edilmiş kümede yok", count: 1 },
    ]);
    expect(summary.accepted).toBe(2);
  });

  test("tam tur: eleme cümlesi eklenmez, gerekçe listesi boş", () => {
    const summary = generationSummary({
      requested: 3,
      returned: 3,
      accepted: 3,
      rejected: 0,
    });
    expect(summary.sentence).toBe(
      "3 soru istendi, 3 soru üretildi, 3 tanesi havuza taslak olarak eklendi.",
    );
    expect(summary.reasons).toEqual([]);
  });

  test("boş tur: 'üretildi' iddiası yok, gerekçe tekrarı sayıya iner", () => {
    // Sağlayıcı şemaya uyan yanıt vermediğinde canlı gövde birebir bu:
    // returned 0, rejected 0, ama gerekçe iki kez.
    const summary = generationSummary({
      requested: 3,
      returned: 0,
      accepted: 0,
      rejected: 0,
      rejection_reasons: ["yanıtta 'questions' dizisi yok", "yanıtta 'questions' dizisi yok"],
    });
    expect(summary.sentence).toBe("3 soru istendi, 0 soru üretildi.");
    expect(summary.accepted).toBe(0);
    expect(summary.reasons).toEqual([
      { text: "yanıtta 'questions' dizisi yok", count: 2 },
    ]);
  });

  test("gerekçeler `rejected` sıfırken de gösterilir", () => {
    // Sunucu soru düzeyindeki redleri (returned - accepted) yanıt düzeyindeki
    // hatalardan ayrı sayıyor; gerekçeyi `rejected > 0` koşuluna bağlamak
    // bu turda kullanıcıya hiçbir sebep göstermezdi. Gövde canlı alındı
    // (materyalsiz ders, 9 Ağustos 2026).
    const summary = generationSummary({
      requested: 3,
      returned: 0,
      accepted: 0,
      rejected: 0,
      rejection_reasons: ["konuyla eşleşen ders materyali bulunamadı"],
    });
    expect(summary.reasons).toEqual([
      { text: "konuyla eşleşen ders materyali bulunamadı", count: 1 },
    ]);
  });

  test("sorular döndü ama hiçbiri kabul edilmedi: accepted 0 kalır", () => {
    // Ekrandaki "havuza soru eklenmedi" notu `accepted`'a bağlı; `returned`'a
    // bağlansaydı bu tur (3 üretildi, 3'ü elendi) sessiz geçerdi.
    const summary = generationSummary({
      requested: 3,
      returned: 3,
      accepted: 0,
      rejected: 3,
      rejection_reasons: ["kaynak uydurma: source_chunk_id retrieve edilmedi"],
    });
    expect(summary.accepted).toBe(0);
    expect(summary.sentence).toBe(
      "3 soru istendi, 3 soru üretildi, 0 tanesi havuza taslak olarak eklendi, 3 tanesi kaynak doğrulamasından geçemedi.",
    );
  });
});

describe("parseExampleQuestions", () => {
  test("satırlara böler, boşları atar, kırpar", () => {
    expect(parseExampleQuestions("  Soru bir  \n\n Soru iki\n")).toEqual([
      "Soru bir",
      "Soru iki",
    ]);
  });

  test("sözleşme sınırı beş: fazlası gönderilmez", () => {
    expect(parseExampleQuestions("a\nb\nc\nd\ne\nf\ng")).toHaveLength(5);
  });

  test("boş metin boş dizi", () => {
    expect(parseExampleQuestions("   \n  ")).toEqual([]);
  });
});

describe("buildGenerateRequest", () => {
  const base = {
    topicId: "t1",
    questionType: "mcq" as QuestionType,
    answerFormat: "essay" as const,
    count: 5,
    examplesText: "",
  };

  test("mcq'da answer_format GÖNDERİLMEZ (sunucu 422 döner)", () => {
    const request = buildGenerateRequest(base);
    expect(request).toEqual({ topic_id: "t1", question_type: "mcq", count: 5 });
    expect("answer_format" in request).toBe(false);
  });

  test("open'da answer_format gönderilir", () => {
    const request = buildGenerateRequest({
      ...base,
      questionType: "open",
      answerFormat: "short_answer",
    });
    expect(request.answer_format).toBe("short_answer");
  });

  test("örnek soru yoksa alan hiç eklenmez", () => {
    expect("example_questions" in buildGenerateRequest(base)).toBe(false);
  });

  test("örnek sorular satır satır taşınır", () => {
    const request = buildGenerateRequest({ ...base, examplesText: "Örnek 1\nÖrnek 2" });
    expect(request.example_questions).toEqual(["Örnek 1", "Örnek 2"]);
  });
});
