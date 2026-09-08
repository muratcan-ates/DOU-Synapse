export interface SecurityHeader {
  key: string;
  value: string;
}

const DEFAULT_API_URL = "http://localhost:8000";

function configuredOrigin(value: string, setting: string): string {
  if (
    !/^https?:\/\/[^/?#]+(?:\/[^?#]*)?$/i.test(value) ||
    /[\s\\\u0000-\u001f\u007f]/u.test(value)
  ) {
    throw new Error(`${setting} açık bir http veya https URL'si olmalıdır.`);
  }
  const parsed = new URL(value);
  const authority = value.split("/")[2];
  if (
    (parsed.protocol !== "http:" && parsed.protocol !== "https:") ||
    parsed.username || parsed.password || authority.includes("@") ||
    !/^([a-z0-9.-]+|\[[a-f0-9:.]+\])$/i.test(parsed.hostname) ||
    parsed.search || parsed.hash
  ) {
    throw new Error(`${setting} geçerli bir ana makine adı içermeli; kimlik bilgisi, wildcard, sorgu veya fragment içeremez.`);
  }
  return parsed.origin;
}

/**
 * HTML/JS yanıtlarının güvenlik politikası tek sözlükte tutulur.
 *
 * Next App Router üretim çıktısı nonce olmadan inline RSC betikleri kullandığı
 * için `unsafe-inline` bugün bilinçli bir sınırlamadır. Buna karşılık framing,
 * object, base ve form yüzeyleri fail-closed kapatılır.
 */
export function webSecurityHeaders(
  apiUrl = process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_URL,
  /**
   * Yalnız `next dev` gevşek politika alır. React dev modda hata ayıklama için
   * `eval()` kullanır ve HMR bir WebSocket açar; CSP ikisini de kestiğinde dev
   * sunucusu her sayfada konsol hatasıyla açılır (10 Ağustos'ta gözlendi —
   * üretim build'iyle doğrulanmış başlıklar dev'i kırdı). React üretimde
   * `eval()` kullanmaz; üretim politikası bu bayrakla bayt bayt aynı kalır.
   * Varsayılan `NODE_ENV === "development"`: `next build/start` 'production',
   * bun test 'test' gördüğü için ikisi de sıkı politikayı alır ve testler
   * üretim davranışını sabitlemeye devam eder.
   */
  dev = process.env.NODE_ENV === "development",
  supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL,
): SecurityHeader[] {
  const connectOrigins = new Set([configuredOrigin(apiUrl, "NEXT_PUBLIC_API_URL")]);
  // Boş değer gerçek auth'un yapılandırılmadığı yerel/demo ortamını korur.
  if (supabaseUrl !== undefined && supabaseUrl !== "") {
    connectOrigins.add(configuredOrigin(supabaseUrl, "NEXT_PUBLIC_SUPABASE_URL"));
  }
  const connections = [...connectOrigins].join(" ");
  const contentSecurityPolicy = [
    "default-src 'self'",
    dev
      ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
      : "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    dev
      ? `connect-src 'self' ${connections} ws:`
      : `connect-src 'self' ${connections}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");

  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    {
      key: "Permissions-Policy",
      value: "camera=(), microphone=(), geolocation=()",
    },
  ];
}
