import { describe, expect, test } from "bun:test";

describe("ders asistanı dialog klavye sözleşmesi", () => {
  test("Escape açıkça kapatılır ve kapanış odağı tetikleyiciye döndürür", async () => {
    const source = await Bun.file(
      new URL("../components/course-assistant/course-assistant.tsx", import.meta.url),
    ).text();

    expect(source).toContain('if (event.key === "Tab")');
    expect(source).toContain("visibleDialogControls(event.currentTarget)");
    expect(source).toContain("last.focus();");
    expect(source).toContain("first.focus();");
    expect(source).toContain('if (event.key !== "Escape") return;');
    expect(source).toContain("event.preventDefault();\n          setOpen(false);");
    expect(source).toContain("triggerRef.current?.focus();");
  });
});
