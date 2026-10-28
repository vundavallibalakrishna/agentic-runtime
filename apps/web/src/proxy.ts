import { type NextRequest, NextResponse } from "next/server";
import { exactOrigins } from "@/lib/widget-origins";
import { apiProxyUrl } from "../dev-env";

export async function proxy(request: NextRequest) {
  const response = NextResponse.next();
  let origins: string[] = [];
  const integrationId = request.nextUrl.pathname.split("/")[2];
  if (integrationId && /^[0-9a-f-]{36}$/i.test(integrationId)) {
    try {
      const policy = await fetch(`${apiProxyUrl}/api/v1/widget/integrations/${integrationId}`, {
        cache: "no-store",
        signal: AbortSignal.timeout(5000),
      });
      if (policy.ok) origins = exactOrigins((await policy.json()).allowedOrigins);
    } catch {
      // An unavailable policy fails closed; it never widens the embedding allowlist.
    }
  }
  response.headers.set(
    "Content-Security-Policy",
    `frame-ancestors ${origins.join(" ") || "'none'"}`,
  );
  response.headers.set("Cache-Control", "no-store");
  response.headers.set("Referrer-Policy", "no-referrer");
  return response;
}

export const config = { matcher: "/widget/:path*" };
