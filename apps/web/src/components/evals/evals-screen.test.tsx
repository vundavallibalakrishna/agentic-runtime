import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { EvalsScreen } from "@/components/evals/evals-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

vi.mock("next/navigation", () => ({
  usePathname: () => "/admin/evals",
  useRouter: () => ({ push: () => undefined }),
  useParams: () => ({ id: "agent" }),
}));

function wrap(children: ReactNode) {
  return (
    <NextIntlClientProvider locale="en" messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}

describe("evaluation screen", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows an empty library and the feedback inbox", async () => {
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["evals:manage"], user: { displayName: "Admin" } }),
      ),
      http.get("*/api/v1/eval-suites", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/feedback", () => HttpResponse.json({ items: [] })),
    );
    render(wrap(<EvalsScreen admin />));
    expect(await screen.findByRole("heading", { name: "Evaluation library" })).toBeTruthy();
    expect(await screen.findByText("No suites yet. Create one to start.")).toBeTruthy();
    expect(await screen.findByText("No feedback yet.")).toBeTruthy();
  });

  it("imports a case file as text and shows the judge's findings from the last run", async () => {
    let imported = "";
    server.use(
      http.get("*/api/v1/auth/session", () =>
        HttpResponse.json({ permissions: ["evals:manage"], user: { displayName: "Admin" } }),
      ),
      http.get("*/api/v1/eval-suites", () =>
        HttpResponse.json({
          items: [
            {
              id: "s1",
              name: "Website questions",
              kind: "functional",
              caseCount: 2,
              lastRun: { id: "r1", passRate: 0.5, status: "completed" },
            },
          ],
        }),
      ),
      http.get("*/api/v1/model-aliases", () =>
        HttpResponse.json({ items: [{ alias: "quick", kind: "chat" }] }),
      ),
      http.post("*/api/v1/eval-suites/s1/cases:import", async ({ request }) => {
        const body = (await request.json()) as { content?: string };
        imported = body.content ?? "";
        return HttpResponse.json({ imported: 1, errors: [] });
      }),
      http.get("*/api/v1/eval-runs/r1/results", () =>
        HttpResponse.json({
          items: [
            {
              case: { id: "c1", name: "support hours" },
              passed: false,
              outputText: "Premium support runs 24x7.",
              latencyMs: 4200,
              scores: {
                llmJudge0: {
                  passed: false,
                  items: [
                    {
                      kind: "must",
                      statement: "Premium lists 16x5 support.",
                      verdict: "not_stated",
                    },
                    {
                      kind: "must_not",
                      statement: "Says 24x7 support is available.",
                      verdict: "stated",
                      quote: "Premium support runs 24x7.",
                    },
                  ],
                },
              },
            },
          ],
        }),
      ),
    );
    render(wrap(<EvalsScreen />));
    expect(await screen.findByText("Website questions")).toBeTruthy();
    expect(await screen.findByLabelText("Model for this run")).toBeTruthy();

    const input = screen.getByLabelText("Import cases", { selector: "input" });
    const file = new File(['{"name":"a","input":{"messages":["hi"]}}'], "cases.jsonl");
    Object.defineProperty(file, "text", { value: () => Promise.resolve('{"name":"a"}') });
    fireEvent.change(input, { target: { files: [file] } });
    expect(await screen.findByText("1 case imported.")).toBeTruthy();
    expect(imported).toBe('{"name":"a"}');

    fireEvent.click(await screen.findByRole("button", { name: "Last results" }));
    expect(await screen.findByText("0 of 1 cases passed.")).toBeTruthy();
    await waitFor(() => expect(screen.getByText("Premium lists 16x5 support.")).toBeTruthy());
    expect(screen.getByText("Says 24x7 support is available.")).toBeTruthy();
    expect(screen.getByText("Claims it should not have made")).toBeTruthy();
  });
});
