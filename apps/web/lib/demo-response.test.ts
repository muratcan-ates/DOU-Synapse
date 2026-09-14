import { describe, expect, test } from "bun:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { DemoResponseNotice } from "@/components/demo-response-notice";
import { SocraticLadder } from "@/components/socratic-ladder";
import { fromAnswer, fromHistory, toBlocks } from "@/lib/chat";
import { DEMO_RESPONSE_LABEL, demoResponseText } from "@/lib/demo-response";
import type { ChatAnswer, ChatMessage } from "@/lib/types";

const citation = {
  chunk_id: "chunk-1", claim: "Süreçler birbirini bekler.", file_name: "Deadlock.md",
  location: "Bölüm 1", snippet: "Deadlock iki veya daha fazla sürecin birbirini beklemesidir.",
};
const body = "Süreçler birbirini bekler.";
const markedBody = `${DEMO_RESPONSE_LABEL}\n\n${body}`;
const answer: ChatAnswer = {
  session_id: "session-1", message_id: "message-1", status: "answered", mode: "qa",
  answer: markedBody, citations: [citation], hints: [], socratic_stage: null,
  cached: false, audience: "student", agent_profile: "student_coach", fixture: true,
  provider_attempts: 2,
};

describe("demo yanıtının doğrulanmış kökeni", () => {
  test("canlı QA gövdesi ve atıfları değişmeden kalır; blok demo bildirimini taşır", () => {
    const transcript = fromAnswer(answer);
    expect(transcript.content).toBe(markedBody);
    expect(transcript.fixture).toBe(true);
    const block = toBlocks([transcript], { mode: "qa" })[0];
    expect(block.kind).toBe("answer");
    if (block.kind !== "answer") throw new Error("Cevap bloğu bekleniyordu.");
    expect(block.fixture).toBe(true);
    expect(block.citations).toBe(answer.citations);
    expect(demoResponseText(block.text, block.fixture)).toBe(body);
    expect(block).not.toHaveProperty("provider_attempts");
  });

  test("Sokratik kademe etiketi, dosya adı ve konum korunur; demo açıklaması bir kez görünür", () => {
    const block = toBlocks([fromAnswer({ ...answer, mode: "socratic", socratic_stage: "diagnose" })], { mode: "socratic" })[0];
    expect(block.kind).toBe("ladder");
    if (block.kind !== "ladder") throw new Error("Merdiven bekleniyordu.");
    expect(block.rungs[0]).toMatchObject({ fixture: true, stage: "diagnose", text: markedBody,
      source: { fileName: citation.file_name, location: citation.location, quote: citation.snippet } });
    const html = renderToStaticMarkup(createElement(SocraticLadder, { rungs: block.rungs }));
    expect(html.split(DEMO_RESPONSE_LABEL)).toHaveLength(2);
    expect(html).toContain(citation.file_name);
    expect(html).toContain(citation.location);
    expect(html).toContain(body);
    expect(html).toContain("bg-info-bg text-info");
    expect(html).not.toContain('role="alert"');
  });

  test.each([undefined, null])("alan %s olduğunda etiket benzeri içerikten demo kararı verilmez", (fixture) => {
    const transcript = fromAnswer({ ...answer, fixture });
    expect(transcript).not.toHaveProperty("fixture");
    const block = toBlocks([transcript], { mode: "qa" })[0];
    expect(block).not.toHaveProperty("fixture");
    expect(demoResponseText(markedBody, fixture)).toBe(markedBody);
    expect(renderToStaticMarkup(createElement(DemoResponseNotice, { fixture }))).toBe("");
  });

  test("geçmiş, kalıcı gövde açıklamasını korur ve sunucunun vermediği köken alanını uydurmaz", () => {
    const history: ChatMessage = {
      id: answer.message_id, role: "assistant", content: markedBody, citations: [citation],
      status: "answered", socratic_stage: null, created_at: "2026-09-13T00:00:00Z", feedback: null,
    };
    const transcript = fromHistory([history])[0];
    expect(transcript.content).toBe(markedBody);
    expect(transcript).not.toHaveProperty("fixture");
    expect(demoResponseText(transcript.content, transcript.fixture)).toBe(markedBody);
  });

  test("doğrulanmış demo öneksiz metni kesmez; bilgi etiketi yine görünür", () => {
    expect(demoResponseText(body, true)).toBe(body);
    const html = renderToStaticMarkup(createElement(DemoResponseNotice, { fixture: true }));
    expect(html).toContain(DEMO_RESPONSE_LABEL);
    expect(html).not.toContain('role="alert"');
  });

  test("sunucu demo olarak işaretlediği ret gövdesinin açıklamasını da kaybetmez", () => {
    const block = toBlocks([fromAnswer({ ...answer, status: "insufficient_context", citations: [] })], { mode: "qa" })[0];
    expect(block).toMatchObject({ kind: "abstention", fixture: true, text: markedBody });
  });
});
