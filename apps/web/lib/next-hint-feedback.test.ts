import { describe, expect, test } from "bun:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FeedbackPanel } from "@/components/exam/feedback-panel";
import { groundedNextHint, sameSourceRef } from "@/lib/assessment-feedback";
import type { AnswerFeedback } from "@/lib/types";

const source = { chunk_id: "chunk/1", file_name: "Ders.md", location: "Bölüm 1", snippet: "Döngüsel bekleme bir bekleme zinciridir." };
const hint = { text: "Bekleme zincirindeki kaynak sırasını yeniden düşünün.", source };
const feedback: AnswerFeedback = { question_id: "q1", graded: true, is_correct: false, score: 0, why_wrong: source, next_hint: hint, evidence: source };
const render = (value: AnswerFeedback) => renderToStaticMarkup(createElement(FeedbackPanel, { courseId: "course/1", sessionId: "session/1", feedback: value }));

describe("kaynak kartının tam eşitliği", () => {
  test("ayrı nesnelerdeki aynı kaynak eşittir; eksik kaynak eşitlik oluşturmaz", () => {
    expect(sameSourceRef(source, { ...source })).toBe(true);
    expect(sameSourceRef(source, null)).toBe(false);
    expect(sameSourceRef(undefined, source)).toBe(false);
    expect(sameSourceRef(null, null)).toBe(false);
  });

  test.each(["chunk_id", "file_name", "location", "snippet"] as const)("%s farkı saklanmaz veya normalleştirilmez", (field) => {
    expect(sameSourceRef(source, { ...source, [field]: `${source[field]} ` })).toBe(false);
  });
});

describe("yanlış yanıttan sonraki kaynaklı ipucu", () => {
  test("gerçek panel üç özdeş kaynağı tek alıntı ve kaynak bağlamı bağlantısıyla gösterir", () => {
    const html = render(feedback);
    expect(html).toContain("Neden yanlış?");
    expect(html).toContain("Sonraki adım için ipucu");
    expect(html).toContain(hint.text);
    expect(html).toContain(source.snippet);
    expect(html).toContain('href="/courses/course%2F1/sources/chunk%2F1"');
    expect(html.match(/<blockquote\b/g)).toHaveLength(1);
    expect(html.match(/<a\b/g)).toHaveLength(1);
    expect(html).not.toContain("Değerlendirmenin dayanağı");
    expect(groundedNextHint(feedback)).toBe(hint);
  });

  test("kısmi puan doğru eşiğini geçse de doğrulanmış gelişim ipucu korunur", () => {
    const html = render({ ...feedback, score: 80, is_correct: true });
    expect(html).toContain("Sonraki adım için ipucu");
    expect(html).toContain("Yanıtını geliştirmek için kaynak");
    expect(html).not.toContain("Neden yanlış?");
    expect(html.match(/<blockquote\b/g)).toHaveLength(1);
  });

  test.each(["file_name", "location", "snippet"] as const)("ipucunun %s alanı farklıysa ikinci kaynak korunur", (field) => {
    const alternate = { ...source, [field]: `Farklı ${source[field]}` };
    const html = render({ ...feedback, next_hint: { ...hint, source: alternate }, evidence: alternate });
    expect(html.match(/<blockquote\b/g)).toHaveLength(2);
    expect(html).toContain(`Farklı ${source[field]}`);
    expect(html).not.toContain("Değerlendirmenin dayanağı");
  });

  test("farklı kanıt ve aynı parçadaki farklı alıntıların tümü görünür kalır", () => {
    const html = render({ ...feedback,
      next_hint: { ...hint, source: { ...source, snippet: "Süreçlerin kaynakları tutması bekleme zinciri oluşturur." } },
      evidence: { ...source, chunk_id: "chunk/2", snippet: "Başka bir parça bekleme zincirini açıklar." },
    });
    expect(html.match(/<blockquote\b/g)).toHaveLength(3);
    expect(html).toContain("Süreçlerin kaynakları tutması bekleme zinciri oluşturur.");
    expect(html).toContain("Başka bir parça bekleme zincirini açıklar.");
    expect(html).toContain('href="/courses/course%2F1/sources/chunk%2F2"');
    expect(html).toContain("Değerlendirmenin dayanağı");
  });

  test("yeni ipucu bulunmayan eski değerlendirmenin kaynak alanları ve başlığı korunur", () => {
    const html = render({ ...feedback, next_hint: null, score: 80, is_correct: true });
    expect(html.match(/<blockquote\b/g)).toHaveLength(2);
    expect(html).toContain("Neden yanlış?");
    expect(html).toContain("Değerlendirmenin dayanağı");
    expect(html).not.toContain("Yanıtını geliştirmek için kaynak");
  });

  test("kaynak veya sunucu ipucu yoksa istemci öneri üretmez", () => {
    for (const value of [
      { ...feedback, why_wrong: null }, { ...feedback, next_hint: null },
      { ...feedback, next_hint: { ...hint, text: " " } },
      { ...feedback, next_hint: { ...hint, source: { ...source, snippet: " " } } },
      { ...feedback, next_hint: { ...hint, source: { ...source, chunk_id: "" } } },
      { ...feedback, next_hint: { ...hint, source: { ...source, chunk_id: "other-chunk" } } },
    ]) expect(render(value)).not.toContain("Sonraki adım için ipucu");
  });

  test("değerlendirilemeyen veya puanı gizlenen yanıtta eski ipucu alanı çizilmez", () => {
    for (const value of [
      { ...feedback, graded: false }, { ...feedback, score: null, is_correct: null },
      { ...feedback, score: 0, is_correct: null }, { ...feedback, score: 100 },
    ]) expect(render(value)).not.toContain("Sonraki adım için ipucu");
  });

  test.each([NaN, Infinity, -1, 101])("geçersiz puan %s kaynaklı ipucunu açmaz", (score) => {
    expect(groundedNextHint({ ...feedback, score })).toBeNull();
  });

  test("sunucu metni HTML olarak çalıştırılmaz", () => {
    const html = render({ ...feedback, next_hint: { ...hint, text: '<script>alert("x")</script>' } });
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
  });
});
