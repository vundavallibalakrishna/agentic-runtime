import { describe, expect, it } from "vitest";

import { lateMemoryEvents } from "@/lib/stream/late";

function frame(seq: number, type: string, data: Record<string, unknown> = {}): string {
  return `id: ${seq}\nevent: ${type}\ndata: ${JSON.stringify({ type, seq, data })}\n\n`;
}

describe("events added to a finished run", () => {
  it("returns the memories saved after the answer and the last sequence", () => {
    const body =
      frame(12, "memory.saved", { factId: "f-1", content: "Has a daughter named Mira" }) +
      ": keep-alive\n\n" +
      frame(13, "memory.saved", { factId: "f-2", content: "Prefers short answers" });
    const found = lateMemoryEvents(body, 11);
    expect(found.seq).toBe(13);
    expect(found.saved.map((event) => event.data?.factId)).toEqual(["f-1", "f-2"]);
  });

  it("returns nothing when the run gained no memory", () => {
    expect(lateMemoryEvents("", 11)).toEqual({ saved: [], seq: 11 });
    expect(lateMemoryEvents(frame(12, "run.completed"), 11)).toEqual({ saved: [], seq: 12 });
    expect(lateMemoryEvents("data: not json\n\n", 11)).toEqual({ saved: [], seq: 11 });
  });
});
