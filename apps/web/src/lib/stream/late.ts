import { createParser } from "eventsource-parser";

/**
 * What the assistant keeps from a turn is decided after the answer is complete, so
 * `memory.saved` is added to a run whose stream has already closed. A finished run's
 * stream replays what was added after `Last-Event-ID` and closes, so the client reads
 * it again a little later.
 */
export const LATE_MEMORY_WAITS_MS = [2500, 6000, 12000];

export type LateEvent = { type: string; seq: number; data?: Record<string, unknown> };

/** The `memory.saved` events in a replayed stream body, and the last sequence seen. */
export function lateMemoryEvents(body: string, from: number): { saved: LateEvent[]; seq: number } {
  const saved: LateEvent[] = [];
  let seq = from;
  const parser = createParser({
    onEvent(event) {
      let payload: LateEvent;
      try {
        payload = JSON.parse(event.data) as LateEvent;
      } catch {
        return;
      }
      if (typeof payload.seq === "number" && payload.seq > seq) {
        seq = payload.seq;
      }
      if (payload.type === "memory.saved") {
        saved.push(payload);
      }
    },
  });
  parser.feed(body);
  return { saved, seq };
}
