import type { NextConfig } from "next";
import { webSecurityHeaders } from "./lib/security-headers";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/:path*",
        headers: webSecurityHeaders(),
      },
    ];
  },
};

export default nextConfig;
