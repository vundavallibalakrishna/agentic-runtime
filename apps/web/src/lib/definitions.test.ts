import { expect, test } from "vitest";

import { type AgentDefinition, agentSchema } from "./definitions";

const draft: AgentDefinition = {
  persona: { displayName: "Ava" },
  instructions: "Help the team.",
  model: { alias: "default", fastAlias: "fast" },
  budget: {
    maxSteps: 8,
    maxTokens: 1000,
    maxCostMicros: 0,
    maxWallClockS: 60,
    maxToolCalls: 4,
    maxParallelToolCalls: 2,
  },
};

test("frontend parses an AgentDefinition from the Pydantic schema", () => {
  const parsed = agentSchema.parse(draft);
  expect(parsed.instructions).toBe("Help the team.");
  expect(parsed.persona.displayName).toBe("Ava");
});
