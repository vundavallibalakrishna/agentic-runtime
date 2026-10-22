import { describe, expect, it } from "vitest";

import { citationsOf } from "@/components/chat/citations";

describe("citationsOf", () => {
  it("reads citation parts and ignores everything else", () => {
    expect(citationsOf({ content: "plain" })).toEqual([]);
    expect(
      citationsOf({
        content: [
          null,
          { type: "text", text: "hello" },
          {
            type: "citation_ref",
            index: 2,
            citation: {
              index: 1,
              title: "Visitor guide",
              snippet: "08:30",
              uri: "sharepoint://visitor-guide",
            },
          },
        ],
      }),
    ).toEqual([
      {
        index: 1,
        title: "Visitor guide",
        snippet: "08:30",
        uri: "sharepoint://visitor-guide",
      },
    ]);
  });
});
