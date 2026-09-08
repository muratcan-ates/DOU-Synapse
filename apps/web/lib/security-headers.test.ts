import { describe, expect, test } from "bun:test";
import { webSecurityHeaders } from "./security-headers";

function asRecord(apiUrl = "https://api.example.edu/v1") {
  return Object.fromEntries(webSecurityHeaders(apiUrl, false, "").map(({ key, value }) => [key, value]));
}

/** Dev politikası ayrı okunur; üretim iddiaları yukarıdaki sıkı varsayılanı kullanır. */
function devHeaderMap(apiUrl?: string): Record<string, string> {
  return Object.fromEntries(
    webSecurityHeaders(apiUrl, true, "").map(({ key, value }) => [key, value]),
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

function connectSources(apiUrl: string, dev: boolean, supabaseUrl?: string): string {
  const csp = webSecurityHeaders(apiUrl, dev, supabaseUrl)
    .find((header) => header.key === "Content-Security-Policy")!.value;
  return csp.split("; ").find((directive) => directive.startsWith("connect-src "))!;
}

describe("Supabase bağlantı sınırı", () => {
  test.each([false, true])("yalnız açık API ve Supabase originleri eklenir, dev=%s", (dev) => {
    expect(connectSources("https://api.example.edu/v1", dev, "https://project.supabase.co/auth/v1"))
      .toBe(`connect-src 'self' https://api.example.edu https://project.supabase.co${dev ? " ws:" : ""}`);
  });

  test("yerel HTTP Supabase yapılandırması portuyla korunur", () => {
    expect(connectSources("http://localhost:8000", true, "http://127.0.0.1:54321"))
      .toBe("connect-src 'self' http://localhost:8000 http://127.0.0.1:54321 ws:");
  });

  test("yerel IPv6 origin yapılandırması korunur", () => {
    expect(connectSources("http://[::1]:8000", true, "http://[::1]:54321"))
      .toBe("connect-src 'self' http://[::1]:8000 http://[::1]:54321 ws:");
  });

  test("aynı origin yinelenmez", () => {
    expect(connectSources("https://api.example.edu/v1", false, "https://api.example.edu"))
      .toBe("connect-src 'self' https://api.example.edu");
  });

  test("boş Supabase değeri yeni origin eklemez", () => {
    expect(connectSources("https://api.example.edu/v1", false, ""))
      .toBe("connect-src 'self' https://api.example.edu");
  });

  test("ortamda yapılandırılan Supabase origin'i varsayılan başlığa girer", () => {
    const old = process.env.NEXT_PUBLIC_SUPABASE_URL;
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://auth.school.example.invalid";
    try {
      expect(connectSources("https://api.example.edu", false))
        .toBe("connect-src 'self' https://api.example.edu https://auth.school.example.invalid");
    } finally {
      if (old === undefined) delete process.env.NEXT_PUBLIC_SUPABASE_URL;
      else process.env.NEXT_PUBLIC_SUPABASE_URL = old;
    }
  });

  const invalidUrls = [
    "javascript:alert(1)", "data:text/plain,test", "ftp://project.supabase.co",
    "//project.supabase.co", "https:project.supabase.co", "https:///project.supabase.co",
    "https://user:secret@project.supabase.co", "https://@project.supabase.co",
    "https://*.supabase.co", "https://project.supabase.co?debug=1",
    "https://host;upgrade-insecure-requests", "https://host\"name", "https://host_name",
    "https://project.supabase.co#fragment", "https://project.supabase.co#",
    "https://project.supabase.co?", " https://project.supabase.co",
    "https://project.supabase.co ", "https://project.supabase.co\\evil", " ",
    "https://project.supabase.co:99999", "https://project.supabase.co\n",
  ];
  test.each(invalidUrls)("geçersiz Supabase URL'si reddedilir: %s", (value) => {
    expect(() => webSecurityHeaders("https://api.example.edu", false, value)).toThrow();
    expect(() => webSecurityHeaders("https://api.example.edu", true, value)).toThrow();
  });
  test.each(invalidUrls)("aynı dar doğrulama API URL'sine uygulanır: %s", (value) => {
    expect(() => webSecurityHeaders(value, false, "")).toThrow();
  });
});
