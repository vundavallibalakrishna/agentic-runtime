import { expect, test } from "vitest";

import { client } from "./index";
import { agentSchema } from "./schemas";

test("generated client is importable", () => {
  expect(client).toBeTruthy();
});

test("agent zod schema comes from the Pydantic JSON Schema", () => {
  const parsed = agentSchema.parse({
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
  });
  expect(parsed.persona.display_name).toBe("Ava");
});
