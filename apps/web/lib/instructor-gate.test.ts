/**
 * `InstructorGate`'in saf karar çekirdeği. Bileşenin kendisi React'e bağlı
 * (bu paket DOM'suz `bun test` ile koşar), bu yüzden üç-yollu dal saf
 * fonksiyona çıkarıldı ve burada doğrudan sınanıyor — aynı gerekçe
 * `use-resource.test.ts`'in başında yazılı.
 *
 * Neden test edilmeli: kapının bozulması sessizdir. Fail-closed kural
 * (`ready` gelmeden eğitmen içeriği ASLA çizilmez, Anayasa IV) kırılırsa
 * öğrenciye bir kare eğitmen formu görünür ve hiçbir test kırmızıya düşmez;
 * `optimistic` varyantı yanlışlıkla varsayılan olursa da aynısı olur.
 */

import { describe, expect, test } from "bun:test";

import { instructorGateOutcome } from "../components/instructor-gate";

describe("instructorGateOutcome — fail-closed varsayılan", () => {
  test("rol çözülmeden içerik de kapak da çizilmez, yalnız yükleniyor", () => {
    expect(instructorGateOutcome(false, false, false)).toBe("loading");
    // isInstructor=true bile olsa ready beklenir: değer henüz güvenilir değil.
    expect(instructorGateOutcome(false, true, false)).toBe("loading");
  });

  test("rol çözülünce eğitmen içeriği, öğrenci kapağı görür", () => {
    expect(instructorGateOutcome(true, true, false)).toBe("content");
    expect(instructorGateOutcome(true, false, false)).toBe("fallback");
  });
});

describe("instructorGateOutcome — iyimser varyant (blueprints)", () => {
  test("rol çözülene kadar iskelet çizilir, sonra karar aynı", () => {
    expect(instructorGateOutcome(false, false, true)).toBe("content");
    expect(instructorGateOutcome(false, true, true)).toBe("content");
    expect(instructorGateOutcome(true, true, true)).toBe("content");
    // İyimserlik yalnız BEKLERKEN geçerli: rol "öğrenci" çıkarsa kapak iner.
    expect(instructorGateOutcome(true, false, true)).toBe("fallback");
  });
});
