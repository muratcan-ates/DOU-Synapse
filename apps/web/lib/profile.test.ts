import { describe, expect, test } from "bun:test";
import { normalizedProfileName, roleLabel } from "./profile";

describe("profil görünümü", () => {
  test("profil adı dış boşluklardan ve tekrar eden boşluklardan arınır", () => {
    expect(normalizedProfileName("  Ayşe   Karagül  ")).toBe("Ayşe Karagül");
  });

  test("ders rolleri Türkçe ve açık etiketlenir", () => {
    expect(roleLabel("instructor")).toBe("Eğitmen");
    expect(roleLabel("student")).toBe("Öğrenci");
  });
});
