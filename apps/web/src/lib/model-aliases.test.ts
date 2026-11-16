import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { chatAliases } from "@/lib/model-aliases";
import { server } from "@/test/server";

describe("chatAliases", () => {
  it("offers each chat alias once and leaves out the other kinds", async () => {
    server.use(
      http.get("*/api/v1/model-aliases", () =>
        HttpResponse.json({
          items: [
            { alias: "reasoning", kind: "chat" },
            { alias: "reasoning", kind: "chat" },
            { alias: "house", kind: "chat" },
            { alias: "embed", kind: "embedding" },
            { alias: "", kind: "chat" },
          ],
        }),
      ),
    );
    expect(await chatAliases()).toEqual(["reasoning", "house"]);
  });

  it("gives an empty list when the read fails", async () => {
    server.use(http.get("*/api/v1/model-aliases", () => HttpResponse.json({}, { status: 500 })));
    expect(await chatAliases()).toEqual([]);
  });
});
