/**
 * `InstructorGate`'in saf karar çekirdeği. Bileşenin kendisi React'e bağlı
 * (bu paket DOM'suz `bun test` ile koşar), bu yüzden üç-yollu dal saf
 * fonksiyona çıkarıldı ve burada doğrudan sınanıyor — aynı gerekçe
 * `use-resource.test.ts`'in başında yazılı.
 *
 * Neden test edilmeli: kapının bozulması sessizdir. Fail-closed kural
 * (`ready` gelmeden eğitmen içeriği ASLA çizilmez, Anayasa IV) kırılırsa
 * öğrenciye bir kare eğitmen formu görünür ve hiçbir test kırmızıya düşmez.
 */

import { describe, expect, test } from "bun:test";

import { instructorGateOutcome } from "../components/instructor-gate";

describe("instructorGateOutcome — fail-closed varsayılan", () => {
  test("rol çözülmeden içerik de kapak da çizilmez, yalnız yükleniyor", () => {
    expect(instructorGateOutcome(false, false)).toBe("loading");
    // isInstructor=true bile olsa ready beklenir: değer henüz güvenilir değil.
    expect(instructorGateOutcome(false, true)).toBe("loading");
  });

  test("rol çözülünce eğitmen içeriği, öğrenci kapağı görür", () => {
    expect(instructorGateOutcome(true, true)).toBe("content");
    expect(instructorGateOutcome(true, false)).toBe("fallback");
  });
});
