/** How long a confirmed session satisfies the gate without another API call. */
export const DEFAULT_SESSION_GATE_TTL_MS = 15_000;

export type SessionProbe = "valid" | "anonymous" | "unknown";
export type GateVerdict = "allow" | "login";

type HeaderSource = { get(name: string): string | null };

/**
 * A Next.js prefetch. Header values are `1` (loading boundary), `2` (runtime) or `3` (shell).
 * A full document load and a real client navigation do not send these.
 */
export function isPrefetch(headers: HeaderSource): boolean {
  if (headers.get("next-router-prefetch")) return true;
  if (headers.get("next-router-segment-prefetch")) return true;
  const purpose = `${headers.get("purpose") ?? ""} ${headers.get("sec-purpose") ?? ""}`;
  return purpose.toLowerCase().includes("prefetch");
}

/** Read `AR_SESSION_GATE_TTL_S`. A blank or unusable value keeps the default. */
export function gateTtlMs(raw: string | undefined, fallback = DEFAULT_SESSION_GATE_TTL_MS): number {
  if (!raw?.trim()) return fallback;
  const seconds = Number(raw);
  if (!Number.isFinite(seconds) || seconds < 0) return fallback;
  return Math.round(seconds * 1000);
}

/**
 * The workspace gate's memory of one session id.
 *
 * A confirmed session is reused until the TTL. Concurrent checks share one probe.
 * A prefetch never starts a probe: the cookie's presence is enough until a real
 * navigation confirms it. A missing cookie is signed out. An anonymous probe
 * (HTTP 401) is signed out and not remembered. An unknown probe (429, 5xx, or
 * the API being unreachable) fails open and is not remembered, so a rate limit
 * is not stored as a sign-out.
 */
export class SessionGate {
  private readonly confirmed = new Map<string, number>();
  private readonly inflight = new Map<string, Promise<GateVerdict>>();

  constructor(
    private readonly ttlMs: number,
    private readonly now: () => number = Date.now,
  ) {}

  async decide(
    sessionId: string | undefined,
    prefetch: boolean,
    probe: (sessionId: string) => Promise<SessionProbe>,
  ): Promise<GateVerdict> {
    if (!sessionId) return "login";
    const confirmedAt = this.confirmed.get(sessionId);
    if (confirmedAt !== undefined && this.now() - confirmedAt < this.ttlMs) return "allow";
    const pending = this.inflight.get(sessionId);
    if (pending) return pending;
    if (prefetch) return "allow";
    const task = this.probe(sessionId, probe);
    this.inflight.set(sessionId, task);
    return task;
  }

  private async probe(
    sessionId: string,
    probe: (sessionId: string) => Promise<SessionProbe>,
  ): Promise<GateVerdict> {
    try {
      const result = await probe(sessionId);
      if (result === "valid") {
        this.confirmed.set(sessionId, this.now());
        return "allow";
      }
      if (result === "anonymous") return "login";
      return "allow";
    } finally {
      this.inflight.delete(sessionId);
    }
  }
}
