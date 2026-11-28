import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RoutinesScreen } from "@/components/routines/routines-screen";
import messages from "@/messages/en.json";
import { server } from "@/test/server";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  usePathname: () => "/routines",
  useRouter: () => ({ push }),
  useParams: () => ({}),
}));

function renderScreen() {
  return render(
    <NextIntlClientProvider locale="en" messages={messages}>
      <RoutinesScreen />
    </NextIntlClientProvider>,
  );
}

beforeEach(() => {
  push.mockClear();
  server.use(
    http.get("*/api/v1/auth/session", () =>
      HttpResponse.json({ permissions: ["routines:create"] }),
    ),
    http.get("*/api/v1/tenant/packs", () => HttpResponse.json({ items: [] })),
    http.get("*/api/v1/agents", () =>
      HttpResponse.json({
        items: [{ id: "agent", name: "Workspace assistant", status: "published", disabled: false }],
      }),
    ),
  );
});

describe("routine controls", () => {
  it("paginates after searching and filtering the loaded routines", async () => {
    server.use(
      http.get("*/api/v1/routines", () =>
        HttpResponse.json({
          items: Array.from({ length: 30 }, (_, i) => ({
            id: `routine-${i}`,
            name: `Work ${i}`,
            status: i === 29 ? "paused" : "active",
          })),
        }),
      ),
    );
    renderScreen();
    await screen.findByText("Work 0");
    expect(screen.queryByText("Work 29")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Work 29")).toBeTruthy();
    fireEvent.change(screen.getByLabelText(messages.routines.search), {
      target: { value: "Work 0" },
    });
    expect(screen.getByText("Work 0")).toBeTruthy();
    fireEvent.change(screen.getByLabelText(messages.routines.search), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "paused" } });
    expect(screen.getByText("Work 29")).toBeTruthy();
    expect(screen.queryByText("Work 0")).toBeNull();
  });

  it("saves the chosen schedule to chat without adding a fixed external destination", async () => {
    const writes: unknown[] = [];
    server.use(
      http.get("*/api/v1/routines", () => HttpResponse.json({ items: [] })),
      http.post("*/api/v1/routines", async ({ request }) => {
        writes.push(await request.json());
        return HttpResponse.json({ id: "created" });
      }),
    );
    renderScreen();
    await screen.findByRole("button", { name: "Agent: Workspace assistant" });
    const create = screen.getByRole("button", { name: "Create a routine" });
    expect(create.hasAttribute("disabled")).toBe(true);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "  Weekly summary  " } });
    fireEvent.change(screen.getByLabelText("Instructions"), {
      target: { value: "Summarise this week's work" },
    });
    fireEvent.click(create);
    await waitFor(() => expect(push).toHaveBeenCalledWith("/routines/created"));
    expect(writes).toEqual([
      {
        name: "Weekly summary",
        agentId: "agent",
        instructions: "Summarise this week's work",
        trigger: { type: "schedule", cron: "0 9 * * 1", timezone: "UTC" },
        delivery: [{ type: "conversation" }],
      },
    ]);
  });
  it("keeps a large agent catalogue bounded and uses the selected agent id in the create payload", async () => {
    const writes: Record<string, unknown>[] = [];
    server.use(
      http.get("*/api/v1/routines", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({
          items: Array.from({ length: 100_000 }, (_, index) => ({
            id: `agent-${index}`,
            name: `Worker ${index}`,
            status: "published",
            disabled: false,
          })),
        }),
      ),
      http.post("*/api/v1/routines", async ({ request }) => {
        writes.push((await request.json()) as Record<string, unknown>);
        return HttpResponse.json({ id: "created" });
      }),
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Agent: Worker 0" }));
    const picker = within(screen.getByRole("dialog", { name: "Agent" }));
    expect(picker.getAllByRole("listitem")).toHaveLength(25);
    expect(picker.getByRole("navigation", { name: "Pagination: Agent" })).toBeTruthy();
    fireEvent.click(picker.getByRole("button", { name: "Next" }));
    expect(picker.getByText("Worker 25")).toBeTruthy();
    fireEvent.change(picker.getByRole("searchbox"), { target: { value: "agent-99999" } });
    fireEvent.click(picker.getByRole("button", { name: /Worker 99999/ }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "Agent: Worker 99999" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Summary" } });
    fireEvent.change(screen.getByLabelText("Instructions"), {
      target: { value: "Summarise work" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create a routine" }));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]?.agentId).toBe("agent-99999");
  });
  it("explains an empty agent catalogue and prevents creating an unassigned routine", async () => {
    server.use(
      http.get("*/api/v1/routines", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () => HttpResponse.json({ items: [] })),
    );
    renderScreen();
    expect(await screen.findByText(messages.agentAvailability.empty)).toBeTruthy();
    expect(
      screen
        .getByRole("button", { name: `Agent: ${messages.referencePicker.choose}` })
        .matches(":disabled"),
    ).toBe(true);
    expect(screen.getByRole("button", { name: "Create a routine" }).matches(":disabled")).toBe(
      true,
    );
  });
  it("selects only a published enabled target and posts its actual id", async () => {
    const writes: Record<string, unknown>[] = [];
    server.use(
      http.get("*/api/v1/routines", () => HttpResponse.json({ items: [] })),
      http.get("*/api/v1/agents", () =>
        HttpResponse.json({
          items: [
            { id: "archived", name: "Archived", status: "archived", disabled: false },
            { id: "draft", name: "Draft", status: "draft", disabled: false },
            { id: "disabled", name: "Disabled", status: "published", disabled: true },
            { id: "unknown", name: "Missing metadata" },
            { id: "ready", name: "Ready", status: "published", disabled: false },
          ],
        }),
      ),
      http.post("*/api/v1/routines", async ({ request }) => {
        writes.push((await request.json()) as Record<string, unknown>);
        return HttpResponse.json({ id: "created" });
      }),
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Agent: Ready" }));
    expect(
      within(screen.getByRole("dialog", { name: "Agent" })).getAllByRole("listitem"),
    ).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Summary" } });
    fireEvent.change(screen.getByLabelText("Instructions"), {
      target: { value: "Summarise work" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create a routine" }));
    await waitFor(() => expect(writes[0]?.agentId).toBe("ready"));
  });
});
