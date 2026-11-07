import { type NextRequest, NextResponse } from "next/server";
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
// (M38b-T05d). A missing session cookie is a hard redirect to sign-in; a present cookie is
// checked against the API, which answers quickly now that tool calls no longer hold its
// event loop (M38-T09). The API being briefly unreachable does not lock the UI out: the
// page loads and the client session check and the error page (T05c) take over.
function toLogin(request: NextRequest): NextResponse {
  return NextResponse.redirect(new URL("/login", request.url));
}

async function requireSession(request: NextRequest): Promise<NextResponse> {
  if (!request.cookies.get("ar_session")) {
    return toLogin(request);
  }
  try {
    const checked = await fetch(`${apiProxyUrl}/api/v1/auth/session`, {
      headers: { cookie: request.headers.get("cookie") ?? "" },
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    if (checked.status === 401) {
      return toLogin(request);
    }
  } catch {
    // The API is unreachable; the client falls back to the error page rather than lock out.
  }
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
