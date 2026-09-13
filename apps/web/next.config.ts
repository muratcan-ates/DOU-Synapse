import type { NextConfig } from "next";
import { webSecurityHeaders } from "./lib/security-headers";

const nextConfig: NextConfig = {
  async headers() {
    const enforcedHeaders = webSecurityHeaders();
    const enforcedCsp = enforcedHeaders.find((header) => header.key === "Content-Security-Policy");
    if (!enforcedCsp) throw new Error("Mevcut CSP başlığı bulunamadı.");
    // Inline betik engelini önce gözle: nonce eklemeden Next'in hydration
    // betiklerini zorla kesmek oturum ve sayfa etkileşimlerini bozabilir.
    const reportOnlyCsp = enforcedCsp.value.split("; ").map((directive) =>
      directive.startsWith("script-src ")
        ? directive.replace(/ 'unsafe-inline'| 'unsafe-eval'/g, "")
        : directive,
    ).join("; ");
    return [
      {
        source: "/:path*",
        headers: [
          ...enforcedHeaders,
          { key: "Content-Security-Policy-Report-Only", value: reportOnlyCsp },
        ],
      },
    ];
  },
};

export default nextConfig;
