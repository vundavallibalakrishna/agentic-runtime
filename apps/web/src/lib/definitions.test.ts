import { expect, test } from "vitest";

import { type AgentDefinition, agentSchema } from "./definitions";

const draft: AgentDefinition = {
  persona: { display_name: "Ava" },
  instructions: "Help the team.",
  model: { alias: "default", fast_alias: "fast" },
  budget: {
    max_steps: 8,
    max_tokens: 1000,
    max_cost_micros: 0,
    max_wall_clock_s: 60,
    max_tool_calls: 4,
    max_parallel_tool_calls: 2,
  },
};

test("frontend parses an AgentDefinition from the Pydantic schema", () => {
  const parsed = agentSchema.parse(draft);
  expect(parsed.instructions).toBe("Help the team.");
  expect(parsed.persona.display_name).toBe("Ava");
});
