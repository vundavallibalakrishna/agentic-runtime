import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

import { apiProxyUrl } from "./dev-env";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const apiOrigin = apiProxyUrl;

const nextConfig: NextConfig = {
  output: "standalone",
  agentRules: false,
  transpilePackages: ["@ar/api-client"],
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiOrigin}/api/:path*` }];
  },
};

export default withNextIntl(nextConfig);
