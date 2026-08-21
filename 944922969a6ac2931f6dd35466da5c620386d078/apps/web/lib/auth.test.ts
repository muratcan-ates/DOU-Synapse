import { describe, expect, test } from "bun:test";
import { PASSWORD_MIN_LENGTH, passwordValidationError } from "./auth";

describe("parola kurtarma formu", () => {
  test("alt sınır görünür ve tek kaynaktan gelir", () => {
    expect(PASSWORD_MIN_LENGTH).toBe(8);
    expect(passwordValidationError("1234567", "1234567")).toContain("8");
  });

  test("iki alan eşleşmek zorundadır", () => {
    expect(passwordValidationError("guclu-parola", "farkli-parola")).toBe(
      "Parolalar birbiriyle eşleşmiyor.",
    );
  });

  test("geçerli parola hata üretmez", () => {
    expect(passwordValidationError("guclu-parola", "guclu-parola")).toBeNull();
  });
});

