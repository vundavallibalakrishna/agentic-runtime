import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { expect, test } from "vitest";

import messages from "@/messages/en.json";
import { server } from "@/test/server";

import { ExposePanel } from "./expose-panel";

function wrap(node: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {node}
    </NextIntlClientProvider>
  );
}

test("shows an empty key list and the public endpoints", async () => {
  server.use(
    http.get("*/api/v1/agents/:id/exposure", () =>
      HttpResponse.json({
        slug: "assistant",
        published: true,
        endpoints: {
          mcp: "/v1/mcp",
          agentCard: "/v1/agents/assistant/.well-known/agent-card.json",
        },
        keys: [],
      }),
    ),
  );
  render(wrap(<ExposePanel agentId="agent-1" canEdit slug="assistant" />));
  expect(await screen.findByText("No API keys yet.")).toBeTruthy();
  expect(screen.getByText("Test console")).toBeTruthy();
  expect(
    screen.getByText("Create a key to send a test message. The secret is shown once."),
  ).toBeTruthy();
});
