import { type NextRequest, NextResponse } from "next/server";
import { gateTtlMs, isPrefetch, SessionGate, type SessionProbe } from "@/lib/session-gate";
import { exactOrigins } from "@/lib/widget-origins";
import { apiProxyUrl } from "../dev-env";

// The embedding allowlist for the widget: a per-integration policy decides which origins
// may frame it; an unavailable policy fails closed.
async function widgetResponse(request: NextRequest): Promise<NextResponse> {
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

// The session gate: a workspace page is not sent to a browser that is not signed in
// (M38b-T05d). A missing session cookie is a hard redirect to sign-in. A present cookie
// is confirmed against the API at most once per AR_SESSION_GATE_TTL_S; concurrent
// requests share that confirmation. A Next.js prefetch does not start an API call.
// A 401 redirects. A 429, a 5xx, or an unreachable API fails open so the client can
// show a retry instead of treating the person as signed out.
const gate = new SessionGate(gateTtlMs(process.env.AR_SESSION_GATE_TTL_S));

function toLogin(request: NextRequest): NextResponse {
  return NextResponse.redirect(new URL("/login", request.url));
}

async function probeSession(request: NextRequest): Promise<SessionProbe> {
  const checked = await fetch(`${apiProxyUrl}/api/v1/auth/session`, {
    headers: { cookie: request.headers.get("cookie") ?? "" },
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
  });
  try {
    if (checked.status === 401) return "anonymous";
    if (checked.ok) return "valid";
    return "unknown";
  } finally {
    await checked.body?.cancel().catch(() => undefined);
  }
}

async function requireSession(request: NextRequest): Promise<NextResponse> {
  let verdict: "allow" | "login";
  try {
    verdict = await gate.decide(
      request.cookies.get("ar_session")?.value,
      isPrefetch(request.headers),
      () => probeSession(request),
    );
  } catch {
    // The API is unreachable; the client falls back to the error page rather than lock out.
    verdict = "allow";
  }
  if (verdict === "login") return toLogin(request);
  const response = NextResponse.next();
  response.headers.set("Cache-Control", "no-store");
  return response;
}

export async function proxy(request: NextRequest) {
  if (request.nextUrl.pathname.startsWith("/widget")) {
    return widgetResponse(request);
  }
  return requireSession(request);
}

// Gate every workspace page; leave the API, static files, the sign-in page, the public
// guest page and the health check alone. The widget is matched for its own headers above.
export const config = {
  matcher: ["/widget/:path*", "/((?!api|_next|favicon.ico|login|guest|healthz|widget|.*\\.).*)"],
};
