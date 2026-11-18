import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  output: "standalone",
  ...(process.env.AR_NEXT_DIST ? { distDir: process.env.AR_NEXT_DIST } : {}),
  agentRules: false,
  transpilePackages: ["@ar/api-client"],
  experimental: {
    // Next buffers every request body once a proxy exists, 10 MB by default, and cut a
    // larger upload short. This is the API's own limit for a route that takes a file:
    // the 25 MiB upload cap plus the multipart envelope (ar_domain.files.logic.UPLOAD_BODY_LIMIT).
    proxyClientMaxBodySize: 26_279_936,
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
        ],
      },
    ];
  },
};

export default withNextIntl(nextConfig);
