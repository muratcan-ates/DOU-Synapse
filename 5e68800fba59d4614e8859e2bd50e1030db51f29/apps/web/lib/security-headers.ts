export interface SecurityHeader {
  key: string;
  value: string;
}

const DEFAULT_API_URL = "http://localhost:8000";

function apiOrigin(apiUrl: string): string {
  const parsed = new URL(apiUrl);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("NEXT_PUBLIC_API_URL http veya https kullanmalıdır.");
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
): SecurityHeader[] {
  const contentSecurityPolicy = [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    `connect-src 'self' ${apiOrigin(apiUrl)}`,
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
