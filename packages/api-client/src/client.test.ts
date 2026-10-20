import { expect, test } from "vitest";

import { client } from "./index";
import { agentSchema } from "./schemas";

test("generated client is importable", () => {
  expect(client).toBeTruthy();
});

test("agent zod schema comes from the Pydantic JSON Schema", () => {
  const parsed = agentSchema.parse({
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
  });
  expect(parsed.persona.displayName).toBe("Ava");
});
