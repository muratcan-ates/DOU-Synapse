import { expect, test } from "bun:test";
import { metadata as blueprints } from "../app/courses/[courseId]/blueprints/layout";
import { metadata as quality } from "../app/courses/[courseId]/quality/layout";
import { metadata as forgotPassword } from "../app/forgot-password/layout";
import { metadata as resetPassword } from "../app/reset-password/layout";

test("yaprak rotalar kendi ayırt edici sekme başlığını taşır", () => {
  expect(blueprints.title).toBe("Sınav blueprint'i");
  expect(quality.title).toBe("AI kalite");
  expect(forgotPassword.title).toBe("Parola yenileme");
  expect(resetPassword.title).toBe("Yeni parola");
});
