import { describe, expect, it } from "vitest";

import { emptyStream, reduceStream } from "./reducer";

describe("reduceStream", () => {
  it("appends deltas once and ignores a replayed sequence", () => {
    const started = reduceStream(emptyStream, {
      type: "message.delta",
      seq: 1,
      data: { text: "Hi" },
    });
    const again = reduceStream(started, { type: "message.delta", seq: 1, data: { text: "Hi" } });
    const done = reduceStream(again, {
      type: "message.completed",
      seq: 2,
      data: { text: "Hi there" },
    });
    expect(again.text).toBe("Hi");
    expect(done).toMatchObject({ status: "completed", text: "Hi there", lastSeq: 2 });
  });

  it("records cancel and failure", () => {
    expect(reduceStream(emptyStream, { type: "run.cancelled", seq: 1 }).status).toBe("cancelled");
    expect(reduceStream(emptyStream, { type: "run.failed", seq: 1 }).status).toBe("failed");
  });
});
