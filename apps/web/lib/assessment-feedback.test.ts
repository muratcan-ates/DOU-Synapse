import { describe, expect, test } from "bun:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FeedbackPanel } from "@/components/exam/feedback-panel";
import { groundedMissingCriterion } from "@/lib/assessment-feedback";
import type { AnswerFeedback } from "@/lib/types";

const criterion = "Döngüsel bekleme koşulunu açıklar";
const source = { chunk_id: "chunk/id", file_name: "Ders.md", location: "Bölüm 1", snippet: "İş parçacıkları birbirini bekler." };
const partial: AnswerFeedback = { question_id: "q1", graded: true, is_correct: true, score: 80,
  rubric_breakdown: [{ point: "Karşılıklı dışlamayı açıklar", weight: 60, score: 100, earned: 60 },
    { point: criterion, weight: 40, score: 50, earned: 20 }],
  grounded_missing_criterion: { criterion, source } };
const render = (feedback: AnswerFeedback) => renderToStaticMarkup(createElement(FeedbackPanel, { courseId: "course/id", feedback }));

describe("kaynaklı eksik ölçüt sunumu", () => {
  test("80 puanla doğru sayılan cevapta gerçek panel eksik ölçütü, alıntıyı ve kaynak yetki yolunu gösterir", () => {
    const html = render(partial);
    expect(html).toContain("Eksik ölçütün dayanağı"); expect(html).toContain(criterion);
    expect(html).toContain(source.snippet); expect(html).toContain("Rubrik ölçütleri");
    expect(html).toContain('href="/courses/course%2Fid/sources/chunk%2Fid"');
    expect(html).not.toContain("Neden yanlış?"); expect(html).not.toContain("kanıtlanmış");
    expect(groundedMissingCriterion(partial)).toBe(partial.grounded_missing_criterion!);
  });
  test("doğruluk eşiğinin altında kalan cevap aynı açıklanmış eksik ölçütü gösterir", () => {
    const html = render({ ...partial, is_correct: false, score: 40 });
    expect(html).toContain("Eksik ölçütün dayanağı"); expect(html).toContain(source.snippet);
  });
  test("sunucu alanı vermediyse eksik noktalardan veya genel kanıttan alıntı uydurulmaz", () => {
    const html = render({ ...partial, grounded_missing_criterion: null, missing_points: [criterion], evidence: source });
    expect(html).not.toContain("Eksik ölçütün dayanağı"); expect(html).toContain("Değerlendirmenin dayanağı");
  });
  test("gizli puanlı, puanlanmamış ve tüm ölçütleri tam olan cevap yeni kaynak ayrıntısını göstermez", () => {
    for (const feedback of [
      { ...partial, is_correct: null, score: null }, { ...partial, graded: false },
      { ...partial, score: 100, grounded_missing_criterion: null,
        rubric_breakdown: partial.rubric_breakdown!.map(row => ({ ...row, score: 100, earned: row.weight })) },
    ]) expect(render(feedback)).not.toContain("Eksik ölçütün dayanağı");
  });
  test.each([NaN, Infinity, -Infinity, -1, 101])("açıklanan toplam puan %s geçersizse kaynaklı ayrıntı göstermez", score => {
    expect(render({ ...partial, score })).not.toContain("Eksik ölçütün dayanağı");
  });
  test("yuvarlanmış toplam 100 olsa da 99 puanlık gerçek ölçütün sunucu dayanağını gösterir", () => {
    const rounded = { ...partial, score: 100, rubric_breakdown: [
      { point: "Karşılıklı dışlamayı açıklar", weight: 99, score: 100, earned: 99 },
      { point: criterion, weight: 1, score: 99, earned: 1 },
    ] };
    expect(render(rounded)).toContain("Eksik ölçütün dayanağı");
    expect(groundedMissingCriterion(rounded)).toBe(partial.grounded_missing_criterion!);
  });
  test("tanımlı ve eşsiz rubrik satırı yoksa sunucu iddiasından yeni ölçüt türetmez", () => {
    for (const rubric_breakdown of [undefined, [],
      [{ point: "Başka ölçüt", weight: 100, score: 50, earned: 50 }],
      [partial.rubric_breakdown![1], partial.rubric_breakdown![1]],
    ]) expect(render({ ...partial, rubric_breakdown })).not.toContain("Eksik ölçütün dayanağı");
  });
  test.each([NaN, Infinity, -Infinity, -1, 100, 101])("iddianın eşleştiği ölçüt puanı %s eksik ölçütü doğrulamıyorsa göstermez", score => {
    const rubric_breakdown = [{ point: criterion, weight: 100, score, earned: 80 }];
    expect(render({ ...partial, rubric_breakdown })).not.toContain("Eksik ölçütün dayanağı");
  });
  test("sıfır puanlık ölçütün sunucu dayanağını gösterir", () => {
    const feedback = { ...partial, rubric_breakdown: [{ point: criterion, weight: 100, score: 0, earned: 0 }] };
    expect(render(feedback)).toContain("Eksik ölçütün dayanağı");
  });
  test("ölçüt ve alıntı düz metin kalır; HTML veya kod çalıştırılabilir öğeye çevrilmez", () => {
    const literalCriterion = '<img src=x onerror="alert(1)">';
    const html = render({ ...partial,
      rubric_breakdown: [{ point: literalCriterion, weight: 100, score: 50, earned: 50 }],
      grounded_missing_criterion: {
        criterion: literalCriterion, source: { ...source, snippet: '<script>alert("x")</script>' },
      } });
    expect(html).toContain("&lt;img"); expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<img"); expect(html).not.toContain("<script>");
  });
  test("eski MCQ neden yanlış etiketi ayrı anlamını korur", () => {
    const html = render({ ...partial, grounded_missing_criterion: null, why_wrong: source });
    expect(html).toContain("Neden yanlış?"); expect(html).not.toContain("Eksik ölçütün dayanağı");
  });
});
