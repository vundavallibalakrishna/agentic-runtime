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

  it("shows the approval sentence while the stream is still open", () => {
    const waiting = reduceStream(emptyStream, {
      type: "tool_call.approval_required",
      seq: 1,
      data: {
        qualifiedName: "petstore.create_pet",
        text: "Waiting for approval before this tool runs.",
      },
    });
    expect(waiting.status).toBe("streaming");
    expect(waiting.text).toBe("Waiting for approval before this tool runs.");
    expect(waiting.tools[0]?.preview).toBe("Waiting for approval before this tool runs.");
  });

  it("records cancel and failure", () => {
    expect(reduceStream(emptyStream, { type: "run.cancelled", seq: 1 }).status).toBe("cancelled");
    expect(reduceStream(emptyStream, { type: "run.failed", seq: 1 }).status).toBe("failed");
  });

  it("keeps a completed tool call on the stream", () => {
    const next = reduceStream(emptyStream, {
      type: "tool_call.completed",
      seq: 1,
      data: {
        qualifiedName: "tickets.create_ticket",
        status: "succeeded",
        resultPreview: "TCK-1001",
      },
    });
    expect(next.tools[0]?.name).toBe("tickets.create_ticket");
  });

  it("keeps a tool that is waiting for approval", () => {
    const next = reduceStream(emptyStream, {
      type: "tool_call.approval_required",
      seq: 1,
      data: { qualifiedName: "petstore.create_pet", status: "awaiting_approval" },
    });
    expect(next.tools[0]?.status).toBe("awaiting_approval");
  });

  it("keeps a saved fact, a recall count and compaction after the run starts", () => {
    let state = emptyStream;
    state = reduceStream(state, { type: "run.started", seq: 1 });
    state = reduceStream(state, { type: "memory.recalled", seq: 2, data: { count: 2 } });
    state = reduceStream(state, {
      type: "memory.saved",
      seq: 3,
      data: { factId: "fact-1", content: "Prefers bullets", scope: "user", status: "active" },
    });
    state = reduceStream(state, { type: "context.compacted", seq: 4 });
    expect(state.recalled).toBe(2);
    expect(state.memories).toEqual([
      { factId: "fact-1", content: "Prefers bullets", scope: "user", status: "active" },
    ]);
    expect(state.compacted).toBe(true);
    expect(state.status).toBe("streaming");
  });

  it("keeps a tool-failure notice and research progress", () => {
    let state = reduceStream(emptyStream, {
      type: "research.progress",
      seq: 1,
      data: { phase: "fanout", sourceCount: 2, queries: [{ id: "1", text: "notes" }] },
    });
    state = reduceStream(state, {
      type: "warning",
      seq: 2,
      data: { code: "tool_failed", message: "A tool call failed and was not recovered." },
    });
    expect(state.researchPhase).toBe("fanout");
    expect(state.researchQueries).toEqual([{ id: "1", text: "notes" }]);
    expect(state.sourceCount).toBe(2);
    expect(state.toolFailure).toContain("failed");
  });
});
