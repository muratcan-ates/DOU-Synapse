import { describe, expect, test } from "bun:test";
import { entraTenantId, isDevAuthEnabled } from "./auth-config";

describe("geliştirme ve Entra giriş kapıları", () => {
  test("dev yalnız tam true değeriyle açılır", () => {
    expect(isDevAuthEnabled("true")).toBe(true);
    for (const value of ["", "false", "TRUE", "1", " true "]) expect(isDevAuthEnabled(value)).toBe(false);
  });
  test("tenant yalnız somut UUID ise biçim kapısını açar", () => {
    for (const value of ["", "common", "organizations", "consumers", "dogus.edu.tr", "00000000-0000-0000-0000-000000000000"]) expect(entraTenantId(value)).toBeNull();
    expect(entraTenantId("11111111-1111-4111-8111-111111111111")).toBe("11111111-1111-4111-8111-111111111111");
  });
});
