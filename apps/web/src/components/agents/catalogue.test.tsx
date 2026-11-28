import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { afterEach, expect, it, vi } from "vitest";

import { AgentCatalogue } from "@/components/agents/catalogue";
import messages from "@/messages/en.json";

const requests = vi.hoisted(() => ({ api: vi.fn() }));
vi.mock("@/lib/api", () => ({ api: requests.api }));
vi.mock("@/lib/session", () => ({ loadSession: () => Promise.resolve({ permissions: [] }) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

it("keeps a newer search result when an older request finishes later", async () => {
  let finishOld: (value: unknown) => void = () => undefined;
  const old = new Promise((resolve) => {
    finishOld = resolve;
  });
  requests.api.mockImplementation((path: string) => {
    if (path.includes("q=old")) return old;
    return Promise.resolve({
      items: [
        {
          id: path.includes("q=new") ? "new" : "initial",
          name: path.includes("q=new") ? "Latest agent" : "Initial agent",
        },
      ],
    });
  });
  render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <AgentCatalogue />
    </NextIntlClientProvider>,
  );
  await screen.findByRole("link", { name: "Initial agent" });
  fireEvent.change(screen.getByRole("textbox", { name: "Search agents" }), {
    target: { value: "old" },
  });
  await waitFor(() => expect(requests.api).toHaveBeenCalledWith("/api/v1/agents?q=old"));
  fireEvent.change(screen.getByRole("textbox", { name: "Search agents" }), {
    target: { value: "new" },
  });
  await screen.findByRole("link", { name: "Latest agent" });
  await act(async () => {
    finishOld({ items: [{ id: "old", name: "Stale agent" }] });
    await old;
  });
  expect(screen.getByRole("link", { name: "Latest agent" })).toBeTruthy();
  expect(screen.queryByRole("link", { name: "Stale agent" })).toBeNull();
});
