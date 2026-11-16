import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { RunDetails } from "@/components/chat/run-details";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("Run details", () => {
  afterEach(() => cleanup());

  it("shows who answered, how long it took and the tools the run called", async () => {
    server.use(
      http.get("*/api/v1/runs/run-1", () =>
        HttpResponse.json({
          id: "run-1",
          status: "completed",
          agentId: "agent-1",
          answeredModel: "reasoning",
          startedAt: "2026-11-16T10:00:00Z",
          endedAt: "2026-11-16T10:00:31Z",
        }),
      ),
      http.get("*/api/v1/runs/run-1/steps", () =>
        HttpResponse.json({ items: [{ id: "s1", kind: "model" }] }),
      ),
      http.get("*/api/v1/runs/run-1/tool-calls", () =>
        HttpResponse.json({
          items: [{ id: "t1", qualifiedName: "documents.judge", status: "failed" }],
        }),
      ),
    );
    render(
      wrap(<RunDetails agents={[{ id: "agent-1", name: "Assistant" }]} runId="run-1" settled />),
    );
    await waitFor(() => expect(screen.getByText("Assistant")).toBeTruthy());
    expect(screen.getByText("reasoning")).toBeTruthy();
    expect(screen.getByText("31s")).toBeTruthy();
    expect(screen.getByText("completed").className).toContain("tone-success");
    expect(screen.getByText("documents.judge")).toBeTruthy();
    expect(screen.getByText("failed").className).toContain("tone-danger");
    expect(screen.getByRole("link", { name: "View trace" }).getAttribute("href")).toBe(
      "/runs/run-1",
    );
  });

  it("says so when the run called no tools", async () => {
    server.use(
      http.get("*/api/v1/runs/run-2", () => HttpResponse.json({ id: "run-2", status: "running" })),
      http.get("*/api/v1/runs/run-2/steps", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/runs/run-2/tool-calls", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<RunDetails agents={[]} runId="run-2" settled={false} />));
    await waitFor(() => expect(screen.getByText("This run called no tools.")).toBeTruthy());
    expect(screen.getByText("running").className).toContain("tone-info");
  });

  it("offers another try when the run cannot be read", async () => {
    server.use(
      http.get("*/api/v1/runs/run-3", () => HttpResponse.json({ detail: "gone" }, { status: 500 })),
      http.get("*/api/v1/runs/run-3/steps", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/runs/run-3/tool-calls", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<RunDetails agents={[]} runId="run-3" settled />));
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
