import { describe, expect, it } from "vitest";

import {
  DEFAULT_SESSION_GATE_TTL_MS,
  gateTtlMs,
  isPrefetch,
  SessionGate,
  type SessionProbe,
} from "@/lib/session-gate";

function headers(values: Record<string, string>): { get(name: string): string | null } {
  const lower = new Map(Object.entries(values).map(([key, value]) => [key.toLowerCase(), value]));
  return { get: (name) => lower.get(name.toLowerCase()) ?? null };
}

describe("isPrefetch", () => {
  it("recognises every Next.js prefetch header and a browser prefetch", () => {
    expect(isPrefetch(headers({ "next-router-prefetch": "1" }))).toBe(true);
    expect(isPrefetch(headers({ "next-router-prefetch": "2" }))).toBe(true);
    expect(isPrefetch(headers({ "next-router-prefetch": "3" }))).toBe(true);
    expect(isPrefetch(headers({ "next-router-segment-prefetch": "/_tree" }))).toBe(true);
    expect(isPrefetch(headers({ purpose: "prefetch" }))).toBe(true);
    expect(isPrefetch(headers({ "sec-purpose": "prefetch;prerender" }))).toBe(true);
  });

  it("does not treat a document load or a client navigation as a prefetch", () => {
    expect(isPrefetch(headers({}))).toBe(false);
    expect(isPrefetch(headers({ rsc: "1", "next-url": "/chat" }))).toBe(false);
  });
});

describe("gateTtlMs", () => {
  it("keeps the default unless the setting is a non-negative number of seconds", () => {
    expect(gateTtlMs(undefined)).toBe(DEFAULT_SESSION_GATE_TTL_MS);
    expect(gateTtlMs("")).toBe(DEFAULT_SESSION_GATE_TTL_MS);
    expect(gateTtlMs("nope")).toBe(DEFAULT_SESSION_GATE_TTL_MS);
    expect(gateTtlMs("-1")).toBe(DEFAULT_SESSION_GATE_TTL_MS);
    expect(gateTtlMs("0")).toBe(0);
    expect(gateTtlMs("15")).toBe(15_000);
  });
});

describe("SessionGate", () => {
  it("sends a missing cookie to sign-in without a probe", async () => {
    let calls = 0;
    const gate = new SessionGate(15_000);
    const verdict = await gate.decide(undefined, false, async () => {
      calls += 1;
      return "valid";
    });
    expect(verdict).toBe("login");
    expect(calls).toBe(0);
  });

  it("does not probe for a prefetch", async () => {
    let calls = 0;
    const gate = new SessionGate(15_000);
    const verdict = await gate.decide("sid", true, async () => {
      calls += 1;
      return "valid";
    });
    expect(verdict).toBe("allow");
    expect(calls).toBe(0);
  });

  it("shares one probe across concurrent navigations and a prefetch", async () => {
    let calls = 0;
    let release: (result: SessionProbe) => void = () => undefined;
    const gate = new SessionGate(15_000, () => 0);
    const probe = (): Promise<SessionProbe> => {
      calls += 1;
      return new Promise((resolve) => {
        release = resolve;
      });
    };
    const first = gate.decide("sid", false, probe);
    const second = gate.decide("sid", false, probe);
    const prefetch = gate.decide("sid", true, probe);
    expect(calls).toBe(1);
    release("valid");
    await expect(Promise.all([first, second, prefetch])).resolves.toEqual([
      "allow",
      "allow",
      "allow",
    ]);
  });

  it("reuses a confirmed session until the TTL and then probes again", async () => {
    let now = 1_000;
    let calls = 0;
    const gate = new SessionGate(15_000, () => now);
    const probe = async (): Promise<SessionProbe> => {
      calls += 1;
      return "valid";
    };
    expect(await gate.decide("sid", false, probe)).toBe("allow");
    expect(await gate.decide("sid", false, probe)).toBe("allow");
    expect(await gate.decide("sid", true, probe)).toBe("allow");
    expect(calls).toBe(1);
    now += 15_000;
    expect(await gate.decide("sid", false, probe)).toBe("allow");
    expect(calls).toBe(2);
  });

  it("does not remember a rejected or an unknown session", async () => {
    const results: SessionProbe[] = ["anonymous", "unknown", "valid"];
    let calls = 0;
    const gate = new SessionGate(15_000, () => 0);
    const probe = async (): Promise<SessionProbe> => {
      const next = results[calls] ?? "valid";
      calls += 1;
      return next;
    };
    expect(await gate.decide("sid", false, probe)).toBe("login");
    expect(await gate.decide("sid", false, probe)).toBe("allow");
    expect(await gate.decide("sid", false, probe)).toBe("allow");
    expect(calls).toBe(3);
    expect(await gate.decide("sid", false, probe)).toBe("allow");
    expect(calls).toBe(3);
  });
});
