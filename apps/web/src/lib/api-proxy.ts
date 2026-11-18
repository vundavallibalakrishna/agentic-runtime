import { apiOrigin } from "@/lib/api-origin";

const HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

/** Forward one same-origin API request. The body is streamed, including SSE. */
export async function proxyApi(request: Request, path: string): Promise<Response> {
  const incoming = new URL(request.url);
  const target = `${apiOrigin()}${path}${incoming.search}`;
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP.has(key.toLowerCase())) {
      headers.set(key, value);
    }
  });
  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
    redirect: "manual",
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = request.body;
    init.duplex = "half";
  }
  let upstream: Response;
  try {
    upstream = await fetch(target, init);
  } catch {
    return Response.json(
      { error: { code: "bad_gateway", message: "API unavailable" } },
      { status: 502 },
    );
  }
  const out = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!HOP.has(key.toLowerCase())) {
      out.append(key, value);
    }
  });
  return new Response(upstream.body, { status: upstream.status, headers: out });
}
