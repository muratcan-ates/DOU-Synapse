import { describe, expect, test } from "bun:test";
import { buildDraftRequest, changeCorrectOption, classificationComplete, codeRubricIssue, createDraftForm,
  draftSourceChoices, outcomesForTopic, rubricHasLegacyMetadata } from "@/lib/question-authoring";
import { buildGenerateRequest } from "@/lib/questions";
import type { Question } from "@/lib/types";

const question = (type: Question["type"], payload: Record<string, unknown>): Question => ({
  id: "q1", course_id: "c1", topic_id: "t1", type, payload, status: "draft",
  created_by: "teacher", reviewed_by: null, reviewed_at: null, created_at: "2026-09-04",
  source: { chunk_id: "primary", file_name: "Ders.pdf", location: "Sayfa 1", snippet: "Kanıt" },
});

describe("question authoring", () => {
  test("only course-wide or matching-topic outcomes are offered", () => {
    const outcomes = [null, "t1", "t2"].map((topic_id, index) => ({ id: `o${index}`,
      code: `LO${index}`, description: "Öğrenme çıktısı", topic_id, created_at: "2026-09-04" }));
    expect(outcomesForTopic(outcomes, "t1").map((outcome) => outcome.id)).toEqual(["o0", "o1"]);
  });

  test("classification permits both empty or both set, not a partial pair", () => {
    expect(classificationComplete({ learningOutcomeId: "", difficulty: "" })).toBe(true);
    expect(classificationComplete({ learningOutcomeId: "lo1", difficulty: "hard" })).toBe(true);
    expect(classificationComplete({ learningOutcomeId: "lo1", difficulty: "" })).toBe(false);
    expect(classificationComplete({ learningOutcomeId: "", difficulty: "easy" })).toBe(false);
  });

  test("classified generation sends exact pair, legacy request stays unchanged", () => {
    const form = { topicId: "t1", questionType: "mcq" as const, answerFormat: "essay" as const, count: 3, examplesText: "" };
    expect(buildGenerateRequest(form)).toEqual({ topic_id: "t1", question_type: "mcq", count: 3 });
    expect(buildGenerateRequest({ ...form, learningOutcomeId: "lo1", difficulty: "medium" })).toEqual({
      topic_id: "t1", question_type: "mcq", count: 3, learning_outcome_id: "lo1", difficulty: "medium",
    });
    expect(buildGenerateRequest({ ...form, learningOutcomeId: "lo1" }).difficulty).toBeNull();
  });

  test("MCQ answer changes keep wrong-option coverage and original metadata without mutation", () => {
    const source = question("mcq", { stem: "Hangi seçenek?", options: [
      { key: "A", text: "Bir", legacy: "keep" }, { key: "B", text: "İki" }, { key: "C", text: "Üç" },
    ], answer_key: "A", distractor_sources: { B: "chunk-b", C: "chunk-c" },
    source_chunk_id: "primary", provenance: { model: "recorded" } });
    const before = JSON.stringify(source);
    const draft = createDraftForm(source);
    const changed = changeCorrectOption(draft, "B", source.source?.chunk_id);
    const request = buildDraftRequest(source, { ...changed, learningOutcomeId: "lo1", difficulty: "easy" });
    expect(request.payload.distractor_sources).toEqual({ A: "primary", C: "chunk-c" });
    expect(request.payload.options).toEqual(source.payload.options);
    expect(request.payload.provenance).toEqual({ model: "recorded" });
    expect(request.payload.source_chunk_id).toBe("primary");
    expect(request.learning_outcome_id).toBe("lo1");
    expect(request.difficulty).toBe("easy");
    expect(JSON.stringify(source)).toBe(before);
    expect(buildDraftRequest(source, changeCorrectOption(changed, "A", source.source?.chunk_id)).payload.distractor_sources)
      .toEqual({ B: "chunk-b", C: "chunk-c" });
  });

  test("missing source is not invented for a newly wrong option", () => {
    const source = { ...question("mcq", { stem: "Soru?", options: [{ key: "A", text: "A" }, { key: "B", text: "B" }],
      answer_key: "A", distractor_sources: { B: "chunk-b" } }), source: null };
    expect(buildDraftRequest(source, changeCorrectOption(createDraftForm(source), "B", undefined)).payload.distractor_sources)
      .toEqual({ A: "" });
  });

  test("source choices use original references, deduplicate and expose labels instead of raw IDs", () => {
    const source = question("mcq", { distractor_sources: { B: "primary", C: "other", D: "other" } });
    expect(draftSourceChoices(source)).toEqual([{ id: "primary", label: "Ders.pdf · Sayfa 1" },
      { id: "other", label: "C şıkkının mevcut kaynağı" }]);
  });

  test("essay editing carries exact rubric weights and metadata for API validation", () => {
    const source = question("open", { prompt: "Açıklayın.", answer_key: "Cevap", format: "essay", key_points: ["A"],
      rubric: [{ point: "A", weight: 100, evidence: "keep" }], curriculum: "preserve" });
    const draft = { ...createDraftForm(source), keyPoints: "A\n\nB", rubric: [{ point: "A", weight: "60", evidence: "keep" }, { point: "B", weight: "40" }] };
    const payload = buildDraftRequest(source, draft).payload;
    expect(payload.key_points).toEqual(["A", "B"]);
    expect(payload.rubric).toEqual([{ point: "A", weight: 60, evidence: "keep" }, { point: "B", weight: 40 }]);
    expect(payload.curriculum).toBe("preserve");
  });

  test("short answer editing preserves its grading format and accepted alternatives", () => {
    const source = question("open", { prompt: "Kavram nedir?", answer_key: "CPU", format: "short_answer", accepted_answers: ["CPU"] });
    const payload = buildDraftRequest(source, { ...createDraftForm(source), acceptedAnswers: "CPU\nMerkezi işlem birimi" }).payload;
    expect(payload.format).toBe("short_answer");
    expect(payload.accepted_answers).toEqual(["CPU", "Merkezi işlem birimi"]);
  });

  test("code trace edits preserve source metadata and multiline code", () => {
    const source = question("code_trace", { prompt: "Çıktı nedir?", language: "python", code: "print(1)", answer_key: "1", source_chunk_id: "primary" });
    const payload = buildDraftRequest(source, { ...createDraftForm(source), code: "x = 2\nprint(x)", answerKey: "2" }).payload;
    expect(payload.code).toBe("x = 2\nprint(x)");
    expect(payload.answer_key).toBe("2");
    expect(payload.source_chunk_id).toBe("primary");
  });

  test("bug hunt edits structured answer without losing metadata", () => {
    const source = question("bug_hunt", { prompt: "Hatayı bulun.", language: "python", code: "x = 1", answer_key: {
      line: 1, bug_type: "Mantık", fix_summary: "Düzeltme", note: "keep",
    } });
    const payload = buildDraftRequest(source, { ...createDraftForm(source), bugLine: "2", bugType: "Sıralama", fixSummary: "Sırayı düzeltin." }).payload;
    expect(payload.answer_key).toEqual({ line: 2, bug_type: "Sıralama", fix_summary: "Sırayı düzeltin.", note: "keep" });
  });

  test("legacy rubric structural controls lock only when rows carry unknown metadata", () => {
    expect(rubricHasLegacyMetadata(question("open", { rubric: [{ point: "A", weight: 100 }] }))).toBe(false);
    expect(rubricHasLegacyMetadata(question("open", { rubric: [{ point: "A", weight: 100, evidence: "keep" }] }))).toBe(true);
    expect(rubricHasLegacyMetadata(question("open", {}))).toBe(false);
  });

  test("unclassified draft saves explicit nulls", () => {
    const source = question("code_trace", { prompt: "Çıktı nedir?", language: "python", code: "print(1)", answer_key: "1" });
    const request = buildDraftRequest(source, createDraftForm(source));
    expect(request.learning_outcome_id).toBeNull();
    expect(request.difficulty).toBeNull();
    expect(Object.keys(request).sort()).toEqual(["difficulty", "learning_outcome_id", "payload"]);
  });
});

describe("kod sorusu rubrik yazımı", () => {
  for (const type of ["code_trace", "bug_hunt"] as const) {
    test(`${type} ölçüt ve puan düzenlemesini API gövdesine taşır; kaynak ve eski alanlar korunur`, () => {
      const source = question(type, { prompt: "Kilit akışını açıklayın.", language: "pseudocode", code: "lock(A)",
        answer_key: type === "code_trace" ? "Bekler." : { line: 1, bug_type: "Sıralama", fix_summary: "Sırayı değiştirin." },
        rubric: [{ point: "Eski ölçüt", weight: 100, context: "keep" }], source_chunk_id: "primary", pedagogy: "preserve" });
      const before = JSON.stringify(source);
      const form = createDraftForm(source);
      form.rubric = [{ ...form.rubric[0], point: "Kilit sırası", weight: "60" }, { point: "Döngüsel bekleme", weight: "40" }];
      const payload = buildDraftRequest(source, form).payload;
      expect(payload.rubric).toEqual([{ point: "Kilit sırası", weight: 60, context: "keep" }, { point: "Döngüsel bekleme", weight: 40 }]);
      expect(payload.source_chunk_id).toBe("primary"); expect(payload.pedagogy).toBe("preserve");
      expect(payload.answer_key).toEqual(source.payload.answer_key); expect(JSON.stringify(source)).toBe(before);
    });
    test(`${type} eski rubriksiz kayıt okunur; yeni yazım öncesi tamamlanması gerekir`, () => {
      const form = createDraftForm(question(type, { code: "print(1)", prompt: "Çıktıyı açıklayın." }));
      expect(form.rubric).toEqual([]);
      expect(codeRubricIssue({ type }, form.rubric)).toBe("Kaydetmek için en az bir puanlama ölçütü ekleyin.");
      form.rubric = [{ point: "Çıktıyı açıklar", weight: "100" }];
      expect(codeRubricIssue({ type }, form.rubric)).toBeNull();
    });
  }
  test("eksik/tekrarlı ölçüt, geçersiz puan ve yanlış toplam sessizce düzeltilmez", () => {
    const source = { type: "code_trace" as const };
    for (const rubric of [
      [{ point: " ", weight: "100" }],
      [{ point: " Output ", weight: "60" }, { point: "output", weight: "40" }],
      [{ point: "A", weight: "0" }], [{ point: "A", weight: "101" }], [{ point: "A", weight: "NaN" }],
      [{ point: "A", weight: "50.5" }, { point: "B", weight: "49.5" }],
      [{ point: "A", weight: "60" }, { point: "B", weight: "20" }],
      Array.from({ length: 13 }, (_, i) => ({ point: String(i), weight: "1" })),
    ]) expect(codeRubricIssue(source, rubric)).not.toBeNull();
    expect(codeRubricIssue(source, [{ point: "Kilit sırası", weight: "60" }, { point: "Döngüsel bekleme", weight: "40" }])).toBeNull();
    expect(codeRubricIssue({ type: "open" }, [])).toBeNull();
  });
});
