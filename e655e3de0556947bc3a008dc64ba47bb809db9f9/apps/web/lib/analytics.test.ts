/**
 * Analitik sözlüğünün testleri — `bun test lib/` ile koşar, ek bağımlılık yok.
 *
 * Bu dosyanın koruduğu şey görünüm değil, bir DÜRÜSTLÜK kuralı: ölçülmemiş olan
 * ölçülmüş gibi gösterilemez. O kuralı bozan değişiklikler sessizdir — ekran
 * yine çalışır, sadece yanlış şeyi söyler. Örneğin `scoreText`'e `?? 0`
 * eklemek hiçbir hata üretmez, sadece hiç çalışılmamış öğrenciye "0,00" der.
 * Aşağıdaki testler tam olarak o değişikliği yakalamak için var.
 */

import { describe, expect, test } from "bun:test";
import {
  barPercent,
  isClassAnalytics,
  MASTERY_LEVEL,
  missedRateText,
  NOT_MEASURED,
  OUT_OF_SCOPE_SOURCE,
  outOfScopeCountsText,
  rateText,
  scoreText,
  topicRows,
  untrackedNote,
  volumeText,
} from "./analytics";
import type { ClassAnalytics, StudentAnalytics } from "./types";

const STUDENT: StudentAnalytics = {
  course_id: "c3b76077-20de-47e5-9fe1-4e770ffa64d2",
  topics: [
    {
      topic_id: "9dabeb2e-9944-4dd8-bf30-3a916d6c317d",
      name: "Deadlock",
      score: 0,
      level: "needs_work",
      answer_count: 2,
    },
    {
      topic_id: "5bf31775-f478-4c14-8bf3-0ec0c0beaada",
      name: "Senkronizasyon",
      score: 0.7,
      level: "medium",
      answer_count: 2,
    },
  ],
  average_score: 0.35,
  tracked_topics: 2,
  untracked_topics: 1,
  needs_work_topics: 1,
  answered_questions: 4,
};

const CLASS: ClassAnalytics = {
  course_id: "c3b76077-20de-47e5-9fe1-4e770ffa64d2",
  topics: [
    {
      topic_id: "9dabeb2e-9944-4dd8-bf30-3a916d6c317d",
      name: "Deadlock",
      average_score: 0,
      level: "needs_work",
      student_count: 1,
      answer_count: 2,
    },
  ],
  missed_questions: [],
  average_score: 0,
  tracked_topics: 1,
  untracked_topics: 2,
  student_count: 1,
  answered_questions: 2,
  out_of_scope: {
    source: "request_logs",
    rate: 0,
    out_of_scope_count: 0,
    insufficient_context_count: 6,
    answered_request_count: 11,
    note: "Oran, cevap üretilen istekler içinde kapsam dışı diye reddedilenlerin payıdır.",
  },
};

describe("scoreText — null ile 0 asla karışmaz", () => {
  test("null 'Ölçüm yok' der, sıfır demez", () => {
    expect(scoreText(null)).toBe(NOT_MEASURED);
  });

  test("ölçülmüş sıfır gerçek bir sayıdır ve yazılır", () => {
    expect(scoreText(0)).toBe("0,00");
    expect(scoreText(0)).not.toBe(NOT_MEASURED);
  });

  test("iki ondalık, Türkçe ayırıcı", () => {
    expect(scoreText(0.35)).toBe("0,35");
    expect(scoreText(0.7)).toBe("0,70");
    expect(scoreText(1)).toBe("1,00");
  });
});

describe("rateText — oran yoksa uydurulmaz", () => {
  test("null 'Ölçüm yok'", () => {
    expect(rateText(null)).toBe(NOT_MEASURED);
  });

  test("ölçülmüş sıfır oran %0 yazılır, gizlenmez", () => {
    expect(rateText(0)).toBe("%0");
  });

  test("yüzde işareti Türkçedeki gibi sayının önündedir", () => {
    expect(rateText(0.68)).toBe("%68");
    expect(rateText(1)).toBe("%100");
  });
});

describe("barPercent — çizim kırpılır, sayı kırpılmaz", () => {
  test("0-1 aralığı yüzdeye çevrilir", () => {
    expect(barPercent(0)).toBe(0);
    expect(barPercent(0.7)).toBe(70);
    expect(barPercent(1)).toBe(100);
  });

  test("aralık dışı değer kaba taşmaz", () => {
    expect(barPercent(-0.5)).toBe(0);
    expect(barPercent(1.4)).toBe(100);
  });

  test("sayı olmayan değer çubuğu boş bırakır (fail-closed)", () => {
    expect(barPercent(Number.NaN)).toBe(0);
  });
});

describe("untrackedNote — çalışılmamış konu sıfır puanla anılmaz", () => {
  test("çalışılmamış konu yoksa satır hiç çizilmez", () => {
    expect(untrackedNote(0)).toBeNull();
    expect(untrackedNote(-1)).toBeNull();
  });

  test("sayıyı söyler ve 'ölçüm yok' der", () => {
    const note = untrackedNote(3);
    expect(note).toContain("3 konu");
    expect(note).toContain("ölçüm yok");
  });
});

describe("MASTERY_LEVEL — seviye sunucudan gelir, eşik istemcide hesaplanmaz", () => {
  test("üç seviyenin de Türkçe etiketi vardır", () => {
    expect(MASTERY_LEVEL.needs_work.label).toBe("Geliştirilmeli");
    expect(MASTERY_LEVEL.medium.label).toBe("Orta");
    expect(MASTERY_LEVEL.good.label).toBe("İyi");
  });

  test("'Geliştirilmeli' uyarı tonudur, danger DEĞİL", () => {
    expect(MASTERY_LEVEL.needs_work.tone).toBe("warning");
    expect(MASTERY_LEVEL.needs_work.tone).not.toBe("danger");
  });

  test("hiçbir seviye danger tonuna boyanmaz (kırmızı hata rengi değildir)", () => {
    for (const level of Object.values(MASTERY_LEVEL)) {
      expect(level.tone).not.toBe("danger");
    }
  });
});

describe("isClassAnalytics — ayrım gövdeden, rolden değil", () => {
  test("sınıf yanıtı tanınır", () => {
    expect(isClassAnalytics(CLASS)).toBe(true);
  });

  test("öğrenci yanıtı sınıf sanılmaz", () => {
    expect(isClassAnalytics(STUDENT)).toBe(false);
  });
});

describe("topicRows — iki uç tek satır şekline iner", () => {
  test("öğrenci satırında öğrenci sayısı ölçülmez", () => {
    const rows = topicRows(STUDENT);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toEqual({
      topicId: "9dabeb2e-9944-4dd8-bf30-3a916d6c317d",
      name: "Deadlock",
      score: 0,
      level: "needs_work",
      answerCount: 2,
      studentCount: null,
    });
  });

  test("sınıf satırında skor ortalamadan gelir ve öğrenci sayısı taşınır", () => {
    const rows = topicRows(CLASS);
    expect(rows[0].score).toBe(0);
    expect(rows[0].studentCount).toBe(1);
  });

  test("sunucunun sırası korunur — istemci yeniden sıralamaz", () => {
    expect(topicRows(STUDENT).map((r) => r.name)).toEqual([
      "Deadlock",
      "Senkronizasyon",
    ]);
  });
});

describe("volumeText — skorun dayandığı hacim görünür", () => {
  test("öğrenci görünümünde yalnız cevap sayısı", () => {
    expect(volumeText(topicRows(STUDENT)[1])).toBe("2 cevap");
  });

  test("sınıf görünümünde öğrenci sayısı da yazılır", () => {
    expect(volumeText(topicRows(CLASS)[0])).toBe("2 cevap · 1 öğrenci");
  });
});

describe("missedRateText — oran paydasız gösterilmez", () => {
  test("payda tek cevap olsa bile yazılır", () => {
    expect(
      missedRateText({
        question_id: "3a000001-0000-4000-8000-000000000001",
        topic_name: "Senkronizasyon",
        stem: "Mutex ile semafor arasındaki sahiplik farkı nedir?",
        wrong_rate: 1,
        graded_answer_count: 1,
      }),
    ).toBe("%100 · 1 değerlendirilen cevap");
  });

  test("aynı oran farklı paydayla farklı okunur", () => {
    const few = missedRateText({
      question_id: "a",
      topic_name: "t",
      stem: "s",
      wrong_rate: 0.667,
      graded_answer_count: 3,
    });
    const many = missedRateText({
      question_id: "b",
      topic_name: "t",
      stem: "s",
      wrong_rate: 0.667,
      graded_answer_count: 300,
    });
    expect(few).toBe("%67 · 3 değerlendirilen cevap");
    expect(many).toBe("%67 · 300 değerlendirilen cevap");
    expect(few).not.toBe(many);
  });
});

describe("kapsam dışı ret — kaynak ve payda görünür", () => {
  test("kaynağın Türkçe karşılığı vardır ve ham adı da taşır", () => {
    expect(OUT_OF_SCOPE_SOURCE.request_logs).toContain("request_logs");
  });

  test("pay ve payda cümlede birlikte geçer", () => {
    const text = outOfScopeCountsText(CLASS.out_of_scope);
    expect(text).toContain("11");
    expect(text).toContain("0");
  });
});
