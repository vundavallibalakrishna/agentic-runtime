import { describe, expect, it } from "vitest";

import { buildTrace } from "./trace";

describe("buildTrace", () => {
  it("links a parent run to two children", () => {
    const graph = buildTrace({
      run: { id: "parent", status: "completed", trigger: "chat" },
      children: [
        { id: "one", agentName: "Researcher", status: "completed" },
        { id: "two", agentName: "Researcher", status: "completed" },
      ],
      steps: [{ id: "step", kind: "subagent", detail: { agent: "researcher" } }],
      tools: [{ id: "call", qualifiedName: "skills.load", status: "succeeded" }],
    });
    expect(graph.nodes.map((node) => node.label)).toEqual([
      "chat",
      "Researcher",
      "Researcher",
      "researcher",
      "skills.load",
    ]);
    expect(graph.edges).toHaveLength(4);
    expect(graph.edges.every((edge) => edge.source === "parent")).toBe(true);
  });
});
