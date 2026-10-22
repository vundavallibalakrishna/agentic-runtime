import { describe, expect, it } from "vitest";

import { definitionToYaml, type JsonValue, yamlToDefinition } from "./agent-yaml";

const sample: JsonValue = {
  persona: { displayName: "Reviewer", greeting: "Tell me the report." },
  instructions: "Review the report and list the gaps.",
  starterPrompts: ["What is missing?"],
  model: { alias: "reasoning", fastAlias: "fast" },
  tools: [{ server: "files", version: "*", include: ["*"] }],
  budget: { maxSteps: 4, maxTokens: 1000 },
};

describe("agent yaml", () => {
  it("round-trips a definition both ways", () => {
    const text = definitionToYaml(sample);
    expect(text).toContain('instructions: "Review the report and list the gaps."');
    expect(text).toContain('server: "files"');
    expect(yamlToDefinition(text)).toEqual(sample);
  });

  it("rejects a broken line", () => {
    expect(() => yamlToDefinition("instructions hello")).toThrow(/YAML/);
  });
});
