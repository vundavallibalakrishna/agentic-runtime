import { describe, expect, it } from "vitest";

import { emptyStream, reduceStream } from "./reducer";

describe("stage 13 stream", () => {
  it("keeps plan status, thinking, a fallback warning and a tool timeline", () => {
    let state = emptyStream;
    state = reduceStream(state, {
      type: "plan.updated",
      seq: 1,
      data: { items: [{ id: "1", title: "Read the file", status: "done" }] },
    });
    state = reduceStream(state, {
      type: "message.started",
      seq: 2,
      data: {},
    });
    state = reduceStream(state, { type: "reasoning.delta", seq: 3, data: { text: "Looking." } });
    state = reduceStream(state, {
      type: "tool_call.started",
      seq: 4,
      data: { qualifiedName: "general.chart", argumentsPreview: '{"kind":"bar"}' },
    });
    state = reduceStream(state, {
      type: "tool_call.failed",
      seq: 5,
      data: { qualifiedName: "general.chart", status: "failed", resultPreview: "retry" },
    });
    state = reduceStream(state, {
      type: "warning",
      seq: 6,
      data: { code: "model_fallback_used", message: "A fallback model answered this step." },
    });
    state = reduceStream(state, {
      type: "message.completed",
      seq: 7,
      data: {
        text: "Done",
        answeredModel: "tenant-model",
        content: [{ type: "followups", prompts: ["Show the table"] }] as unknown as string,
      },
    });
    expect(state.plan[0]).toMatchObject({ title: "Read the file", status: "done" });
    expect(state.reasoning).toBe("Looking.");
    expect(state.warnings[0]?.code).toBe("model_fallback_used");
    expect(state.answeredModel).toBe("tenant-model");
    expect(state.followups).toEqual(["Show the table"]);
    expect(state.tools[0]?.timeline.map((entry) => entry.kind)).toEqual(["arguments", "repair"]);
    expect(state.status).toBe("completed");
  });
});
