import { proxyApi } from "@/lib/api-proxy";

export function GET(request: Request) {
  return proxyApi(request, "/.well-known/agent-card.json");
}
