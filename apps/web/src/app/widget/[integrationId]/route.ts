import { apiProxyUrl } from "../../../../dev-env";

export async function GET(
  _request: Request,
  context: { params: Promise<{ integrationId: string }> },
) {
  const { integrationId } = await context.params;
  let ancestors = "'none'";
  try {
    const response = await fetch(`${apiProxyUrl}/api/v1/widget/integrations/${integrationId}`, {
      cache: "no-store",
    });
    if (response.ok) {
      const body = (await response.json()) as { allowedOrigins?: string[] };
      const origins = (body.allowedOrigins ?? []).filter(
        (item) => item.startsWith("https://") || item.startsWith("http://localhost"),
      );
      if (origins.length > 0) {
        ancestors = origins.join(" ");
      }
    }
  } catch {
    ancestors = "'none'";
  }
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>Agent</title></head><body style="font-family:sans-serif;margin:24px"><h1>Agent</h1><p>Ask from this portal. Sign-in uses the host token.</p></body></html>`;
  return new Response(html, {
    headers: {
      "content-type": "text/html; charset=utf-8",
      "content-security-policy": `frame-ancestors ${ancestors}`,
    },
  });
}
