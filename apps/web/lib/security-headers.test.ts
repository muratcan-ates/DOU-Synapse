import { describe, expect, test } from "bun:test";
import { webSecurityHeaders } from "./security-headers";

function asRecord(apiUrl = "https://api.example.edu/v1") {
  return Object.fromEntries(webSecurityHeaders(apiUrl).map(({ key, value }) => [key, value]));
}

/** Dev politikası ayrı okunur; üretim iddiaları yukarıdaki sıkı varsayılanı kullanır. */
function devHeaderMap(apiUrl?: string): Record<string, string> {
  return Object.fromEntries(
    webSecurityHeaders(apiUrl, true).map(({ key, value }) => [key, value]),
  );
}

describe("web güvenlik başlıkları", () => {
  test("temel tarayıcı politikalarının tamamı tek sözlükten gelir", () => {
    const headers = asRecord();

    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
    expect(headers["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["Permissions-Policy"]).toBe(
      "camera=(), microphone=(), geolocation=()",
    );
    expect(headers["X-Frame-Options"]).toBeUndefined();
  });

  test("CSP framing ve aktif içerik yüzeylerini fail-closed kapatır", () => {
    const csp = asRecord()["Content-Security-Policy"];

    for (const directive of [
      "default-src 'self'",
      "object-src 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
    ]) {
      expect(csp).toContain(directive);
    }
  });

  test("connect-src yalnız yapılandırılan API originini taşır", () => {
    const csp = asRecord()["Content-Security-Policy"];

    expect(csp).toContain("connect-src 'self' https://api.example.edu");
    expect(csp).not.toContain("/v1");
  });

  test("http dışı API protokolü derlemeyi fail-closed durdurur", () => {
    expect(() => webSecurityHeaders("javascript:alert(1)")).toThrow();
  });
});

// 10 Ağustos: üretim başlıkları dev sunucusunu kırmıştı (React dev modu eval
// ister, HMR WebSocket ister). Bu iki test o ayrımı çiviler: biri geri alırsa
// ya dev yine kırılır ya üretim gevşer — ikisi de kırmızı yanar.
test("dev politikası eval ve websocket'e izin verir", () => {
  const csp = devHeaderMap()["Content-Security-Policy"];
  expect(csp).toContain("'unsafe-eval'");
  expect(csp).toContain("ws:");
});

test("üretim politikası eval ve websocket İÇERMEZ", () => {
  const csp = asRecord()["Content-Security-Policy"];
  expect(csp).not.toContain("unsafe-eval");
  expect(csp).not.toContain("ws:");
});
